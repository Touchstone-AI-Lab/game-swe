"""Regenerate the Minecraft (Paper plugin) Harbor task packages.

Canonical task content is ``catalog.json``, ``exams/<task>.md``, each task's
``environment/plugin`` starter, ``tests/suite`` grader sources, ``tests/unit``
overlays, ``solution/after`` and ``NOTES.md``. This script derives everything
else a Harbor 1.4 package needs (``task.toml``, ``instruction.md``, both
Dockerfiles, ``tests/{test.sh,verify.py,task.json,frozen}``, ``solution/solve.sh``)
so an authoring change is followed by one regeneration and a deterministic
diff. It never writes a starter, a suite or a reference.

Run from anywhere::

    python benchmarks/minecraft-core/private/harbor/scripts/materialize.py
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parent
HARBOR_ROOT = SCRIPT_ROOT.parent
PACK_ROOT = HARBOR_ROOT.parents[1]
CATALOG_PATH = PACK_ROOT / "catalog.json"
EXAMS_ROOT = PACK_ROOT / "exams"
HARNESS_ROOT = HARBOR_ROOT / "harness"
HARBOR_REVISION = "9a2e3b135cc8fb1e41131020f83370cb2f12ae93"
PAPER_VERSION = "1.21.11"
PAPER_BUILD = "132"
INSTRUCTION_HEADER = (
    "# Harbor workspace\n\n"
    "Complete this task in `/app/plugin`; the repository's build files, dependency "
    "declarations and upstream tests are frozen and restored by the verifier.\n\n"
)


def _quoted_list(values: list[str] | tuple[str, ...]) -> str:
    return "[" + ", ".join(json.dumps(value, ensure_ascii=False) for value in values) + "]"


def _exam_body(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    if source.startswith("---\n"):
        _opening, _front_matter, body = source.split("---", 2)
        return body.lstrip()
    return source


def _task_manifest(task: dict[str, object]) -> dict[str, object]:
    build = task["build"]
    assert isinstance(build, dict)
    return {
        "schemaVersion": 1,
        "taskId": task["id"],
        "pluginName": task["plugin_name"],
        "build": {
            "tool": build["tool"],
            "wrapper": build.get("wrapper", True),
            "toolVersion": build.get("tool_version"),
            "module": build.get("module"),
            "assemble": build.get("assemble", "assemble"),
            "test": (
                build.get("test", "test") if "test" in build else ("test" if task.get("unit_cases") else None)
            ),
            "artifact": build["artifact"],
            "javaRelease": build.get("java_release", 21),
            "frozenPaths": list(build.get("frozen_paths", DEFAULT_FROZEN_PATHS)),
        },
        "unitCases": list(task.get("unit_cases", [])),
        "serverCases": list(task["server_cases"]),
        "hiddenUnitOverlay": bool(task.get("hidden_unit_overlay", False)),
    }


DEFAULT_FROZEN_PATHS = (
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
    "gradle.properties",
    "gradle",
    "gradlew",
    "gradlew.bat",
    "pom.xml",
    ".mvn",
    "mvnw",
    "mvnw.cmd",
    "src/test",
)


def _warm_commands(manifest: dict[str, object], *, agent: bool) -> str:
    """Docker RUN lines that warm the dependency cache with network, then prove it offline."""
    build = manifest["build"]
    assert isinstance(build, dict)
    tool = build["tool"]
    module = build.get("module")
    workdir = "/app/plugin" if agent else "/opt/gcb/warm-build"
    install = ""
    if tool == "javac":
        return ""
    if tool == "gradle":
        prefix = f"{module}:" if module else ""
        wrapper = "./gradlew" if build.get("wrapper", True) else "gradle"
        assemble = " ".join(f"{prefix}{part}" for part in str(build["assemble"]).split())
        test_task = build.get("test")
        # Gradle resolves the JUnit platform launcher and other test-runtime
        # artifacts only while executing tests, so the warm-up must run the
        # upstream tests once online; the offline rerun proves the cache is whole.
        tests = f" {prefix}{test_task}" if test_task else ""
        warm = (
            f"{wrapper} --no-daemon --console=plain -q dependencies {assemble}{tests} "
            "&& " + f"{wrapper} --offline --no-daemon --console=plain -q clean {assemble}{tests}"
        )
        prelude = (
            "mkdir -p /opt/gradle-cache && printf 'org.gradle.java.installations.auto-download=false\\n' "
            "> /opt/gradle-cache/gradle.properties && "
        )
    else:
        wrapper = "./mvnw" if build.get("wrapper", True) else "mvn"
        scope = f" -pl {module} -am" if module else ""
        if not build.get("wrapper", True):
            install = _maven_install(str(build.get("toolVersion") or ""))
        # Surefire providers are resolved only while tests execute: run them once.
        test_goal = " test" if build.get("test") else " -DskipTests"
        warm = (
            f"{wrapper} -B -q -Dmaven.repo.local=/opt/m2{scope} dependency:go-offline{test_goal} "
            f"&& {wrapper} -o -B -q -Dmaven.repo.local=/opt/m2{scope} clean{test_goal} "
            + str(build["assemble"])
        )
        prelude = "mkdir -p /opt/m2 && "
    if agent:
        return f"{install}RUN cd {workdir} && {prelude}chmod +x {wrapper} 2>/dev/null || true; {warm}\n"
    # The verifier warms on a scratch copy of the starter, then removes it; only
    # the dependency cache survives in the image.
    return (
        f"{install}RUN mkdir -p {workdir} && cp -a /opt/gcb/starter/. {workdir}/ "
        f"&& cd {workdir} && {prelude}chmod +x {wrapper} 2>/dev/null || true; {warm} "
        f"&& cd / && rm -rf {workdir}\n"
    )


# Apache Maven binary distributions pinned by SHA-512 (archive.apache.org). A
# repository without a committed Maven wrapper declares build.tool_version and
# both images install exactly that release before warming the dependency cache.
MAVEN_SHA512 = {
    "3.9.11": (
        "bcfe4fe305c962ace56ac7b5fc7a08b87d5abd8b7e89027ab251069faebee516b0ded8961445d6d91ec1985dfe30f8153"
        "268843c89aa392733d1a3ec956c9978"
    ),
}


def _maven_install(version: str) -> str:
    """Docker RUN line that installs a pinned Apache Maven release as /usr/local/bin/mvn."""
    digest = MAVEN_SHA512.get(version)
    if digest is None:
        raise ValueError(f"no pinned SHA-512 for Apache Maven {version!r}; add it to MAVEN_SHA512")
    url = (
        f"https://archive.apache.org/dist/maven/maven-3/{version}/binaries/apache-maven-{version}-bin.tar.gz"
    )
    fetch = (
        "import hashlib, sys, urllib.request; "
        f"data = urllib.request.urlopen({url!r}, timeout=300).read(); "
        f"sys.exit('maven checksum mismatch') if hashlib.sha512(data).hexdigest() != {digest!r} else None; "
        "open('/tmp/maven.tgz', 'wb').write(data)"
    )
    return (
        f'RUN mkdir -p /opt/maven && python3 -c "{fetch}" '
        "&& tar -xzf /tmp/maven.tgz -C /opt/maven --strip-components=1 && rm -f /tmp/maven.tgz "
        "&& ln -s /opt/maven/bin/mvn /usr/local/bin/mvn && mvn -v\n"
    )


def _task_toml(task: dict[str, object], manifest: dict[str, object], catalog_id: str) -> str:
    task_id = str(task["id"])
    upstream = task.get("upstream")
    if task.get("clean_room_synthetic"):
        provenance = "clean-room synthetic"
        upstream = {"repository": provenance, "base_commit": provenance, "license_spdx": "Apache-2.0"}
    if not isinstance(upstream, dict):
        raise TypeError(f"{task_id} lacks upstream provenance")
    estimated_minutes = task["estimated_minutes"]
    if not isinstance(estimated_minutes, int):
        raise TypeError(f"{task_id} estimated_minutes must be an integer")
    keywords = (
        "minecraft",
        "paper",
        "java",
        "game-modding",
        "repository-debugging",
        *[str(item) for item in task.get("domains", [])],
    )
    tags = ("game-modding", "minecraft", "java", "repository-debugging")
    build = manifest["build"]
    assert isinstance(build, dict)
    return f'''schema_version = "1.4"

artifacts = ["/app/plugin"]

[task]
name = "gamecodebench/minecraft-{task_id}"
version = "1.0.0"
description = {json.dumps(str(task["summary"]["en"]) if isinstance(task["summary"], dict) else "")}
authors = [{{ name = "GameCodeBench" }}]
keywords = {_quoted_list(keywords)}

[metadata]
category = "programming"
difficulty = {json.dumps(str(task["difficulty"]))}
tags = {_quoted_list(tags)}
task_kind = "repository-debugging"
game = "Minecraft (Paper dedicated server)"
game_version = "Paper {PAPER_VERSION} build {PAPER_BUILD}"
language = "Java 21"
build_tool = {json.dumps(str(build["tool"]))}
plugin_name = {json.dumps(str(task["plugin_name"]))}
source_repo = {json.dumps(str(upstream["repository"]))}
base_commit = {json.dumps(str(upstream["base_commit"]))}
source_license = {json.dumps(str(upstream["license_spdx"]))}
expected_unit_cases = {len(manifest["unitCases"]) if isinstance(manifest["unitCases"], list) else 0}
expected_server_cases = {len(manifest["serverCases"]) if isinstance(manifest["serverCases"], list) else 0}
content_reference = {json.dumps(f"benchmarks/{PACK_ROOT.name}/exams/{task_id}.md")}
content_reference_pack = {json.dumps(catalog_id)}
harbor_reference_repository = "https://github.com/harbor-framework/harbor"
harbor_reference_revision = "{HARBOR_REVISION}"
verification_profile = "rhenium-minecraft-full"
real_server_validation = "in-verifier; Paper {PAPER_VERSION} build {PAPER_BUILD}"

[verifier]
network_mode = "no-network"
timeout_sec = 2400.0
user = "root"
environment_mode = "separate"

[verifier.environment]
network_mode = "no-network"

[agent]
# The image contains mini-swe-agent. A Harbor job supplies only the model
# endpoint hostname through agents[].extra_allowed_hosts.
network_mode = "allowlist"
allowed_hosts = []
timeout_sec = {estimated_minutes * 60}.0
user = "agent"

[environment]
network_mode = "no-network"
build_timeout_sec = 3600.0
cpus = 4
memory_mb = 8192
storage_mb = 16384
gpus = 0
mcp_servers = []

[verifier.env]

[environment.env]

[solution.env]
'''


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def _copy_starter(starter: Path, target: Path) -> None:
    """Mirror the starter tree into tests/starter.

    The verifier restores only the declared frozen paths from this copy, but the
    whole tree is needed so the verifier image can warm the dependency cache with
    a real build and test run (Gradle and Maven resolve test-runtime artifacts
    only while executing tests).
    """
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(
        starter,
        target,
        symlinks=False,
        ignore=shutil.ignore_patterns("build", "target", ".gradle", "out", ".git"),
    )


def materialize() -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    for task in catalog["tasks"]:
        task_id = str(task["id"])
        root = HARBOR_ROOT / task_id
        manifest = _task_manifest(task)
        starter = root / "environment" / "plugin"
        if not starter.is_dir():
            raise FileNotFoundError(f"starter is missing: {starter}")
        _write(root / "task.toml", _task_toml(task, manifest, str(catalog["id"])))
        _write(root / "instruction.md", INSTRUCTION_HEADER + _exam_body(EXAMS_ROOT / f"{task_id}.md"))
        agent_dockerfile = (HARNESS_ROOT / "agent.Dockerfile.tmpl").read_text(encoding="utf-8")
        _write(
            root / "environment" / "Dockerfile",
            agent_dockerfile.replace("__WARM__\n", _warm_commands(manifest, agent=True)),
        )
        tests = root / "tests"
        build = manifest["build"]
        assert isinstance(build, dict)
        _copy_starter(starter, tests / "starter")
        suite_lines = ["COPY suite /tests/suite"] if (tests / "suite").is_dir() else []
        if (tests / "TaskSuite.java").is_file():
            suite_lines.append("COPY TaskSuite.java /tests/TaskSuite.java")
        if (tests / "unit").is_dir():
            suite_lines.append("COPY unit /tests/unit")
        if (tests / "seed").is_dir():
            # Pre-seeded plugin data folders (tests/seed/<PluginName>/...) that
            # verify.py copies into plugins/ before the server starts.
            suite_lines.append("COPY seed /tests/seed")
        verifier_dockerfile = (HARNESS_ROOT / "verifier.Dockerfile.tmpl").read_text(encoding="utf-8")
        _write(
            tests / "Dockerfile",
            verifier_dockerfile.replace("__WARM__\n", _warm_commands(manifest, agent=False)).replace(
                "__SUITE__\n", "".join(f"{line}\n" for line in suite_lines)
            ),
        )
        _copy(HARNESS_ROOT / "test.sh", tests / "test.sh")
        _copy(HARNESS_ROOT / "verify.py", tests / "verify.py")
        _write(tests / "task.json", json.dumps(manifest, indent=2, sort_keys=False) + "\n")
        _copy(HARNESS_ROOT / "solve.sh", root / "solution" / "solve.sh")
        (tests / "test.sh").chmod(0o755)
        (root / "solution" / "solve.sh").chmod(0o755)


if __name__ == "__main__":
    materialize()
