"""Mechanical build facts for a Minecraft (Paper plugin) history candidate.

Nothing here calls a model. The build specification is inferred from the
repository's own files, then proven the way the benchmark will use it: the
agent image of ``benchmarks/minecraft-core`` is built for the base tree with
the exact warm-up commands ``materialize.py`` renders (network allowed, then an
offline rerun), and the reference tree is built and tested again with no
network on top of that cache. Unit cases are frozen from the JUnit reports with
the verifier's own identity rule.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any

from .checkout import kept
from .models import BuildProbe

CORE_PACK = Path("benchmarks") / "minecraft-core"
MAVEN_VERSION = "3.9.11"
_PLUGIN_NAME = re.compile(r"^name:\s*['\"]?([A-Za-z0-9_.-]+)['\"]?\s*$", re.MULTILINE)
_SHADOW = re.compile(r"shadow", re.IGNORECASE)
# Builds that need the Minecraft server itself (paperweight, NMS, Mojang mappings).
# Kotlin in the build is fine: discovery already requires the fix to be Java.
_FORBIDDEN_BUILD = re.compile(r"paperweight|net\.minecraft:|mojang-mapped", re.IGNORECASE)
_PLACEHOLDER_NAME = re.compile(r"^name:\s*['\"]?\$\{[A-Za-z0-9_.-]+\}['\"]?\s*$", re.MULTILINE)
_PAPER_API = (
    re.compile(
        r"(?:io\.papermc\.paper|com\.destroystokyo\.paper|org\.spigotmc|org\.bukkit)"
        r"[:'\"\s]+(?:paper-api|spigot-api|bukkit)[:'\"\s]+([0-9][A-Za-z0-9.+_-]*)"
    ),
    re.compile(
        r"<artifactId>\s*(?:paper-api|spigot-api|bukkit)\s*</artifactId>\s*<version>\s*([^<\s]+)\s*</version>"
    ),
)
_JAVA_17 = re.compile(
    r"(?:JavaLanguageVersion\.of\(\s*17\s*\)|VERSION_17|release\s*[=(]\s*17|"
    r"<(?:maven\.compiler\.)?release>\s*17\s*<)"
)
_LICENSE_NAMES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE", "LICENSE.MD", "COPYING")
_REPORT_SCRIPT = r"""
import json, os, zipfile, base64
root = '/app/plugin'
reports, jars = {}, []
total = 0
for folder, dirs, files in os.walk(root):
    for name in files:
        path = os.path.join(folder, name)
        rel = os.path.relpath(path, root)
        if name.endswith('.xml') and ('/test-results/' in '/' + rel or '/surefire-reports/' in '/' + rel):
            if name.startswith('TEST-') or '/test-results/' in '/' + rel:
                data = open(path, 'rb').read()
                total += len(data)
                if total < 16 * 1024 * 1024:
                    reports[rel] = base64.b64encode(data).decode()
        elif name.endswith('.jar') and not rel.endswith(('gradle-wrapper.jar', 'maven-wrapper.jar')):
            # Checkout strips every vendored archive except the build-tool wrappers, so
            # any other jar is build output, wherever the build copies it.
            meta = None
            try:
                with zipfile.ZipFile(path) as archive:
                    for entry in ('plugin.yml', 'paper-plugin.yml'):
                        if entry in archive.namelist():
                            meta = archive.read(entry).decode('utf-8', 'replace')
                            break
            except zipfile.BadZipFile:
                pass
            jars.append({'path': rel, 'size': os.path.getsize(path), 'metadata': meta})
print(json.dumps({'reports': reports, 'jars': jars}))
"""


class BuildRejected(RuntimeError):
    """The candidate cannot become a repository task; the message is safe to record."""


def build_failure_reason(log: str) -> str:
    """The build tool's own one-line reason from a failed image build, if it printed one."""
    lines = [line.split(" ", 2)[-1] if line.startswith("#") else line for line in log.splitlines()]
    for index, line in enumerate(lines):
        if "What went wrong:" in line:
            for following in lines[index + 1 : index + 4]:
                text = following.strip()
                if text and not text.startswith(">"):
                    return text[:300]
    for line in lines:
        if "[ERROR]" in line and "Failed to execute goal" in line:
            return line.split("[ERROR]", 1)[1].strip()[:300]
    return ""


@dataclass(frozen=True)
class BuildGuess:
    tool: str
    wrapper: bool
    tool_version: str | None
    module: str | None
    assemble: str
    test: str | None
    java_release: int
    frozen_paths: tuple[str, ...]
    plugin_name: str
    plugin_root: str
    license_file: str
    paper_api: str


def load_core_script(project_root: Path, relative: str, name: str) -> ModuleType:
    """Import a pack script (materialize.py, verify.py) by path; one source of truth."""
    path = project_root / CORE_PACK / "private" / "harbor" / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _build_files(tree: Path) -> list[Path]:
    names = {"build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts", "pom.xml"}
    found = [path for path in tree.glob("*") if path.name in names]
    found += [path for path in tree.glob("*/*") if path.name in names]
    return sorted(found)


def _plugin_metadata(tree: Path) -> Path | None:
    for pattern in ("src/main/resources/{}", "*/src/main/resources/{}", "*/*/src/main/resources/{}"):
        for name in ("plugin.yml", "paper-plugin.yml"):
            matches = sorted(tree.glob(pattern.format(name)))
            if matches:
                return matches[0]
    return None


def frozen_paths(tree: Path, *, core_defaults: tuple[str, ...]) -> tuple[str, ...]:
    """The pack defaults plus every sub-project's build file and test tree."""
    paths = list(core_defaults)
    for build in _build_files(tree):
        relative = build.relative_to(tree)
        if len(relative.parts) == 2:
            module = relative.parts[0]
            for item in (relative.as_posix(), f"{module}/src/test"):
                if item not in paths:
                    paths.append(item)
    for directory in sorted(path for path in tree.glob("*/src/test") if path.is_dir()):
        item = directory.relative_to(tree).as_posix()
        if item not in paths:
            paths.append(item)
    return tuple(paths)


def infer_build(tree: Path, *, core_defaults: tuple[str, ...]) -> BuildGuess:
    """Static inference from the repository's files; rejects unsupported builds."""
    build_files = _build_files(tree)
    text = "\n".join(_read(path) for path in build_files)
    if not build_files:
        raise BuildRejected("no Gradle or Maven build at the repository root")
    if (tree / ".gitmodules").is_file():
        # GitHub tarballs omit submodule contents, so such a build cannot succeed.
        raise BuildRejected("the repository uses git submodules, which tarball checkouts do not include")
    if _FORBIDDEN_BUILD.search(text):
        raise BuildRejected("build needs paperweight, Kotlin or Minecraft server internals")
    metadata = _plugin_metadata(tree)
    if metadata is None:
        raise BuildRejected("no plugin.yml or paper-plugin.yml in the repository")
    metadata_text = _read(metadata)
    match = _PLUGIN_NAME.search(metadata_text)
    if match is None and _PLACEHOLDER_NAME.search(metadata_text) is None:
        raise BuildRejected("plugin metadata declares no name")
    plugin_root = metadata.parents[3].relative_to(tree).as_posix()
    license_file = next((name for name in _LICENSE_NAMES if (tree / name).is_file()), None)
    if license_file is None:
        raise BuildRejected("the base commit has no licence file at the repository root")
    gradle = any(
        (tree / name).is_file()
        for name in ("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts")
    )
    maven = (tree / "pom.xml").is_file()
    if gradle:
        if not (tree / "gradlew").is_file() or not (tree / "gradle" / "wrapper").is_dir():
            raise BuildRejected("Gradle build without a committed wrapper cannot be pinned")
        tool, wrapper, tool_version = "gradle", True, None
        assemble = "shadowJar" if _SHADOW.search(text) else "assemble"
    elif maven:
        tool = "maven"
        wrapper = (tree / "mvnw").is_file() and (tree / ".mvn" / "wrapper").is_dir()
        tool_version = None if wrapper else MAVEN_VERSION
        assemble = "package"
    else:
        raise BuildRejected("build files are not at the repository root")
    has_tests = any(tree.glob("src/test/java")) or any(tree.glob("*/src/test/java"))
    paper_api = next((m.group(1) for pattern in _PAPER_API if (m := pattern.search(text))), "unspecified")
    return BuildGuess(
        tool=tool,
        wrapper=wrapper,
        tool_version=tool_version,
        module=None,
        assemble=assemble,
        test="test" if has_tests else None,
        java_release=17 if _JAVA_17.search(text) else 21,
        frozen_paths=frozen_paths(tree, core_defaults=core_defaults),
        # Empty when the build fills the name in; it is then read from the built jar.
        plugin_name=match.group(1) if match is not None else "",
        plugin_root=plugin_root if plugin_root != "." else "",
        license_file=license_file,
        paper_api=paper_api,
    )


def is_test_path(relative: str) -> bool:
    """Whether a repository path is inside a ``src/test`` tree."""
    parts = PurePosixPath(relative).parts
    return any(parts[index : index + 2] == ("src", "test") for index in range(len(parts)))


def reference_tree(base: Path, fixed: Path, changed: tuple[str, ...], destination: Path) -> list[str]:
    """Base plus the fix's non-test changes; returns the changed main-source paths."""
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(base, destination, symlinks=False)
    applied: list[str] = []
    for relative in changed:
        if is_test_path(relative) or not kept(PurePosixPath(relative)):
            continue  # upstream tests are frozen at the base commit
        source = fixed / relative
        target = destination / relative
        if source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            applied.append(relative)
        elif target.is_file():
            # The Harbor oracle copies solution/after over the starter and cannot delete.
            raise BuildRejected("the fix deletes a main source file")
    if not applied:
        raise BuildRejected("the fix changes no main source file of the repository")
    return applied


class DockerProbe:
    """Build the real agent image for the base tree, then the reference offline."""

    def __init__(self, project_root: Path, *, docker: str | None = None):
        self.project_root = project_root
        self.docker = docker or shutil.which("docker") or ""
        self.materialize = load_core_script(project_root, "scripts/materialize.py", "history_materialize")
        self.verify = load_core_script(project_root, "harness/verify.py", "history_verify")

    def _run(self, arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        if not self.docker:
            raise BuildRejected("docker is not installed")
        return subprocess.run(
            [self.docker, *arguments], capture_output=True, text=True, timeout=timeout, check=False
        )

    def manifest(self, guess: BuildGuess, artifact: str) -> dict[str, Any]:
        task = {
            "id": "probe",
            "plugin_name": guess.plugin_name,
            "server_cases": ["probe"],
            "unit_cases": ["probe"] if guess.test else [],
            "build": {
                "tool": guess.tool,
                "wrapper": guess.wrapper,
                "tool_version": guess.tool_version,
                "module": guess.module,
                "assemble": guess.assemble,
                "test": guess.test,
                "artifact": artifact,
                "java_release": guess.java_release,
                "frozen_paths": list(guess.frozen_paths),
            },
        }
        return dict(self.materialize._task_manifest(task))

    def probe(
        self, label: str, base: Path, reference: Path, applied: list[str], guess: BuildGuess, log_dir: Path
    ) -> BuildProbe:
        manifest = self.manifest(guess, "probe.jar")
        warm = str(self.materialize._warm_commands(manifest, agent=True))
        offline = warm.rstrip().rsplit("&& ", 1)[1]
        harness = self.project_root / CORE_PACK / "private" / "harbor" / "harness"
        template = (harness / "agent.Dockerfile.tmpl").read_text(encoding="utf-8")
        base_tag = f"rhenium-history-probe:{label}-base"
        fixed_tag = f"rhenium-history-probe:{label}-reference"
        log_dir.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(prefix="history-probe-") as raw:
                context = Path(raw)
                shutil.copytree(base, context / "plugin", symlinks=False)
                (context / "Dockerfile").write_text(template.replace("__WARM__\n", warm))
                started = time.monotonic()
                built = self._run(["build", "--pull=false", "--tag", base_tag, str(context)], timeout=3600)
                base_seconds = time.monotonic() - started
                (log_dir / "probe-base.log").write_text((built.stdout + built.stderr)[-200_000:])
                if built.returncode != 0:
                    reason = build_failure_reason(built.stdout + built.stderr)
                    raise BuildRejected(
                        "the base tree does not build and test offline after a warm-up"
                        + (f": {reason}" if reason else "")
                    )
                base_facts = self._facts(base_tag)
                base_artifact, plugin_name = self._artifact(base_facts, guess.plugin_name)
                self._copy_out(base_tag, base_artifact, log_dir / "base-plugin.jar")
            with tempfile.TemporaryDirectory(prefix="history-probe-") as raw:
                context = Path(raw)
                for relative in applied:
                    target = context / "after" / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(reference / relative, target)
                lines = [f"FROM {base_tag}", "USER root", "COPY after/ /app/plugin/"]
                lines.append(f"RUN cd /app/plugin && {offline}")
                (context / "Dockerfile").write_text("\n".join(lines) + "\n")
                started = time.monotonic()
                built = self._run(
                    ["build", "--pull=false", "--network=none", "--tag", fixed_tag, str(context)],
                    timeout=3600,
                )
                fixed_seconds = time.monotonic() - started
                (log_dir / "probe-reference.log").write_text((built.stdout + built.stderr)[-200_000:])
                if built.returncode != 0:
                    reason = build_failure_reason(built.stdout + built.stderr)
                    raise BuildRejected(
                        "the reference does not build or pass the upstream tests offline"
                        + (f": {reason}" if reason else "")
                    )
                fixed_facts = self._facts(fixed_tag)
        finally:
            # The base image (warmed dependency cache) is kept for patch compile checks
            # and removed by ``release`` when the candidate is finished.
            self._run(["image", "rm", "--force", fixed_tag], timeout=300)
        artifact = base_artifact
        if self._artifact(fixed_facts, plugin_name) != (artifact, plugin_name):
            raise BuildRejected("the reference builds its plugin jar at a different path")
        base_cases = self._cases(base_facts)
        fixed_cases = self._cases(fixed_facts)
        if base_cases != fixed_cases:
            raise BuildRejected("the upstream test set differs between base and reference")
        passing = tuple(sorted(name for name, passed in base_cases.items() if passed))
        if len(passing) != len(base_cases) or not all(fixed_cases.values()):
            raise BuildRejected("an upstream test fails on the base or the reference")
        return BuildProbe(
            tool=guess.tool,  # type: ignore[arg-type]
            wrapper=guess.wrapper,
            tool_version=guess.tool_version,
            module=guess.module,
            assemble=guess.assemble,
            test=guess.test if passing else None,
            artifact=artifact,
            java_release=guess.java_release,  # type: ignore[arg-type]
            frozen_paths=guess.frozen_paths,
            plugin_name=plugin_name,
            license_file=guess.license_file,
            paper_api=guess.paper_api,
            unit_cases=passing,
            base_seconds=round(base_seconds, 1),
            fixed_seconds=round(fixed_seconds, 1),
        )

    @staticmethod
    def base_tag(label: str) -> str:
        return f"rhenium-history-probe:{label}-base"

    def release(self, label: str) -> None:
        """Remove a candidate's kept probe image; idempotent."""
        if self.docker:
            self._run(["image", "rm", "--force", self.base_tag(label)], timeout=300)

    def ensure_base_image(self, label: str, base: Path, probe: BuildProbe) -> str | None:
        """The warmed agent image of a candidate's base tree (rebuilt from cache if gone)."""
        tag = self.base_tag(label)
        if not self.docker:
            return None
        if self._run(["image", "inspect", tag], timeout=60).returncode == 0:
            return tag
        guess = BuildGuess(
            tool=probe.tool,
            wrapper=probe.wrapper,
            tool_version=probe.tool_version,
            module=probe.module,
            assemble=probe.assemble,
            test=probe.test,
            java_release=probe.java_release,
            frozen_paths=probe.frozen_paths,
            plugin_name=probe.plugin_name,
            plugin_root="",
            license_file=probe.license_file,
            paper_api=probe.paper_api,
        )
        warm = str(self.materialize._warm_commands(self.manifest(guess, probe.artifact), agent=True))
        harness = self.project_root / CORE_PACK / "private" / "harbor" / "harness"
        template = (harness / "agent.Dockerfile.tmpl").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory(prefix="history-probe-") as raw:
            context = Path(raw)
            shutil.copytree(base, context / "plugin", symlinks=False)
            (context / "Dockerfile").write_text(template.replace("__WARM__\n", warm))
            built = self._run(["build", "--pull=false", "--tag", tag, str(context)], timeout=3600)
        return tag if built.returncode == 0 else None

    def compile_findings(self, tag: str, probe: BuildProbe, files: dict[str, str]) -> list[str]:
        """Offline compile of the base tree with ``files`` replaced, inside the warmed image."""
        if probe.tool == "gradle":
            command = "./gradlew --offline --no-daemon --console=plain -q compileJava"
        else:
            maven = "./mvnw" if probe.wrapper else "mvn"
            command = f"{maven} -o -B -q -Dmaven.repo.local=/opt/m2 compile"
        with tempfile.TemporaryDirectory(prefix="history-patch-") as raw:
            patch = Path(raw) / "patch"
            for relative, text in files.items():
                target = patch / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
            Path(raw).chmod(0o755)
            for path in patch.rglob("*"):
                path.chmod(0o755 if path.is_dir() else 0o644)
            completed = self._run(
                [
                    "run",
                    "--rm",
                    "--network=none",
                    "--pull=never",
                    "--mount",
                    f"type=bind,source={patch},target=/patch,readonly",
                    "--entrypoint",
                    "bash",
                    tag,
                    "-c",
                    f"cp -R /patch/. /app/plugin/ && cd /app/plugin && {command}",
                ],
                timeout=900,
            )
        if completed.returncode == 0:
            return []
        output = (completed.stdout + completed.stderr).strip()
        return ["the change does not compile offline:\n" + output[-6000:]]

    def _copy_out(self, tag: str, relative: str, destination: Path) -> None:
        """Copy one built file out of a probe image (the plugin jar for suite compilation)."""
        created = self._run(["create", tag], timeout=120)
        if created.returncode != 0:
            raise BuildRejected("the probe image could not be opened")
        container = created.stdout.strip()
        try:
            copied = self._run(["cp", f"{container}:/app/plugin/{relative}", str(destination)], timeout=300)
            if copied.returncode != 0:
                raise BuildRejected("the built plugin jar could not be copied out")
        finally:
            self._run(["rm", "--force", container], timeout=120)

    def _facts(self, tag: str) -> dict[str, Any]:
        listed = self._run(
            ["run", "--rm", "--network=none", "--entrypoint", "python3", tag, "-c", _REPORT_SCRIPT],
            timeout=600,
        )
        if listed.returncode != 0:
            raise BuildRejected("build reports could not be read from the probe image")
        try:
            facts = json.loads(listed.stdout)
        except json.JSONDecodeError:
            raise BuildRejected("build reports could not be read from the probe image") from None
        return facts if isinstance(facts, dict) else {}

    @staticmethod
    def _artifact(facts: dict[str, Any], plugin_name: str) -> tuple[str, str]:
        """The built plugin jar and its declared name (any name when ``plugin_name`` is empty)."""
        matches = []
        for jar in facts.get("jars") or []:
            metadata = jar.get("metadata") if isinstance(jar, dict) else None
            path = str(jar.get("path") or "") if isinstance(jar, dict) else ""
            name = path.rsplit("/", 1)[-1]
            if not isinstance(metadata, str) or name.startswith("original-"):
                continue
            if any(marker in name for marker in ("-sources", "-javadoc", "-plain")):
                continue
            found = _PLUGIN_NAME.search(metadata)
            if found and (not plugin_name or found.group(1) == plugin_name):
                matches.append((int(jar.get("size") or 0), path, found.group(1)))
        if not matches:
            raise BuildRejected("the build produced no jar carrying the plugin metadata")
        _size, path, name = max(matches)
        return path, name

    def _cases(self, facts: dict[str, Any]) -> dict[str, bool]:
        reports = facts.get("reports") or {}
        with tempfile.TemporaryDirectory(prefix="history-junit-") as raw:
            paths = []
            for index, (_name, encoded) in enumerate(sorted(reports.items())):
                path = Path(raw) / f"{index}.xml"
                path.write_bytes(base64.b64decode(encoded))
                paths.append(path)
            # Duplicated identities (parameterized tests reported under one name) are
            # dropped here exactly as the verifier drops them: they are never frozen.
            cases, _duplicates = self.verify.parse_junit_reports(paths)
        return {str(case["name"]): bool(case["passed"]) for case in cases}
