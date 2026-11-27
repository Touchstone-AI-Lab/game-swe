"""Shared javac preflight for the Minecraft project and verifier check commands.

Standard library only: these scripts are trusted operator executables invoked by
``rhenium-author --project-check-command`` / ``--verifier-check-command``. They
read ``{"schema_version": 1, "files": {...}}`` on stdin and print
``{"schema_version": 1, "complete": bool, "findings": [...]}`` on stdout.
Compile errors are findings; a missing toolchain or classpath makes the check
incomplete (never a silent pass).

Classpath sources, in order:

* ``RHENIUM_MINECRAFT_CLASSPATH`` - a directory (every ``*.jar`` below it, or a
  directory of classes) or a colon-separated list of jars/directories;
* ``RHENIUM_MINECRAFT_CLASSPATH_IMAGE`` - a prepared verifier image whose
  ``/opt/gcb/classpath.txt`` jars and ``/opt/gcb/harness/gcb-harness.jar`` are
  copied out once with ``docker cp`` into ``.rhenium/authoring/minecraft-classpath/``.

The harness jar for suite compilation comes from ``RHENIUM_MINECRAFT_HARNESS_CLASSPATH``
when set, else from the image cache, else from a ``gcb-harness.jar`` found on the
classpath directories.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

SCHEMA_VERSION = 1
JAVA_RELEASE = "21"
MAX_FINDINGS = 40
MAX_FINDING_LENGTH = 1000
CLASSPATH_VARIABLE = "RHENIUM_MINECRAFT_CLASSPATH"
IMAGE_VARIABLE = "RHENIUM_MINECRAFT_CLASSPATH_IMAGE"
HARNESS_VARIABLE = "RHENIUM_MINECRAFT_HARNESS_CLASSPATH"
CACHE_VARIABLE = "RHENIUM_MINECRAFT_CLASSPATH_CACHE"
IMAGE_CLASSPATH_FILE = "/opt/gcb/classpath.txt"
IMAGE_HARNESS_JAR = "/opt/gcb/harness/gcb-harness.jar"
HARNESS_JAR_NAME = "gcb-harness.jar"
_PLUGIN_NAME_LINE = re.compile(r"^name:\s*['\"]?([A-Za-z0-9_.-]+)['\"]?\s*$", re.MULTILINE)
_PLUGIN_MAIN_LINE = re.compile(r"^main:\s*['\"]?([A-Za-z0-9_.]+)['\"]?\s*$", re.MULTILINE)


class CheckUnavailable(RuntimeError):
    """The check cannot run; the tool must fail closed."""


def read_request() -> dict[str, str]:
    try:
        request = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        raise CheckUnavailable(f"request is not valid JSON: {error}") from error
    if not isinstance(request, dict) or request.get("schema_version") != SCHEMA_VERSION:
        raise CheckUnavailable("unsupported request schema")
    files = request.get("files")
    if not isinstance(files, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in files.items()
    ):
        raise CheckUnavailable("request files must map paths to text")
    for raw in files:
        path = PurePosixPath(raw)
        if not raw or path.is_absolute() or ".." in path.parts or raw != path.as_posix():
            raise CheckUnavailable("request contains an unsafe file path")
    return files


def respond(complete: bool, findings: list[str]) -> int:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "complete": complete,
        "findings": [value[:MAX_FINDING_LENGTH] for value in findings[:MAX_FINDINGS]],
    }
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()
    return 0 if complete else 1


def project_root() -> Path:
    current = Path.cwd().resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "benchmarks").is_dir():
            return candidate
    return current


def javac() -> str:
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        candidate = Path(java_home) / "bin" / "javac"
        if candidate.is_file():
            return str(candidate)
    found = shutil.which("javac")
    if found is None:
        raise CheckUnavailable("javac is not installed; set JAVA_HOME or PATH to a JDK 21+")
    return found


def _jars_below(directory: Path) -> list[Path]:
    return sorted(path for path in directory.rglob("*.jar") if path.is_file())


def _expand(entry: str) -> list[str]:
    path = Path(entry).expanduser()
    if path.is_dir():
        jars = _jars_below(path)
        # A directory without jars is a directory of compiled classes.
        return [str(jar) for jar in jars] if jars else [str(path)]
    if path.is_file():
        return [str(path)]
    raise CheckUnavailable(f"classpath entry does not exist: {entry}")


def _image_cache_directory(image: str) -> Path:
    override = os.environ.get(CACHE_VARIABLE)
    base = (
        Path(override).expanduser()
        if override
        else project_root() / ".rhenium" / "authoring" / "minecraft-classpath"
    )
    key = hashlib.sha256(image.encode()).hexdigest()[:16]
    return base / key


def _docker() -> str:
    found = shutil.which("docker")
    if found is None:
        raise CheckUnavailable("docker is not installed; cannot export the image classpath")
    return found


IMAGE_COPY_ROOTS = ("/opt/paper/libraries",)


def copy_plan(entries: list[str]) -> list[str]:
    """Paths to `docker cp`: whole library roots that hold entries, then the rest."""
    plan: list[str] = []
    covered: set[str] = set()
    for root in IMAGE_COPY_ROOTS:
        below = [entry for entry in entries if entry.startswith(root.rstrip("/") + "/")]
        if below:
            plan.append(root)
            covered.update(below)
    plan.extend(entry for entry in entries if entry not in covered)
    return plan


def _export_from_image(image: str) -> Path:
    """Copy the verifier image's classpath jars and harness jar into the local cache once."""
    cache = _image_cache_directory(image)
    manifest = cache / "classpath.txt"
    if manifest.is_file():
        entries = [line.strip() for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
        if (
            entries
            and all((cache / entry.lstrip("/")).is_file() for entry in entries)
            and (cache / IMAGE_HARNESS_JAR.lstrip("/")).is_file()
        ):
            return cache
    docker = _docker()
    create = subprocess.run(
        [docker, "create", "--pull=never", image, "true"],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    container = create.stdout.strip()
    if create.returncode != 0 or re.fullmatch(r"[0-9a-f]{64}", container) is None:
        raise CheckUnavailable(f"could not create a container from {image}")
    # Stage beside the cache, never in TMPDIR: os.replace() below cannot cross a
    # filesystem, and a repository on a different device than /tmp fails with EXDEV.
    cache.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    staging = Path(tempfile.mkdtemp(prefix="minecraft-classpath-", dir=cache.parent))
    try:
        copied = subprocess.run(
            [docker, "cp", f"{container}:{IMAGE_CLASSPATH_FILE}", str(staging / "classpath.txt")],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        if copied.returncode != 0:
            raise CheckUnavailable(f"{image} has no {IMAGE_CLASSPATH_FILE}")
        entries = [
            line.strip()
            for line in (staging / "classpath.txt").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if not entries:
            raise CheckUnavailable(f"{image} recorded an empty classpath")
        wanted = [*entries, IMAGE_HARNESS_JAR]
        for entry in wanted:
            if not entry.startswith("/") or ".." in PurePosixPath(entry).parts:
                raise CheckUnavailable("image classpath contains an unsafe entry")
        # One `docker cp` per jar takes minutes for a hundred-odd library jars;
        # copy shared parent directories whole and only stragglers one by one.
        for source in copy_plan(wanted):
            target = staging / source.lstrip("/")
            target.parent.mkdir(parents=True, exist_ok=True)
            copied = subprocess.run(
                [docker, "cp", f"{container}:{source}", str(target)],
                capture_output=True,
                text=True,
                check=False,
                timeout=600,
            )
            if copied.returncode != 0:
                raise CheckUnavailable(f"could not copy {source} out of {image}")
        for entry in wanted:
            if not (staging / entry.lstrip("/")).is_file():
                raise CheckUnavailable(f"{entry} was not exported from {image}")
        if cache.exists():
            shutil.rmtree(cache)
        os.replace(staging, cache)
    finally:
        subprocess.run([docker, "rm", "--force", container], capture_output=True, check=False, timeout=60)
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
    return cache


def resolve_classpath() -> tuple[list[str], str | None]:
    """(server classpath entries, harness jar or None)."""
    entries: list[str] = []
    harness: str | None = None
    explicit = os.environ.get(CLASSPATH_VARIABLE, "").strip()
    image = os.environ.get(IMAGE_VARIABLE, "").strip()
    if explicit:
        for component in explicit.split(":"):
            if component.strip():
                entries.extend(_expand(component.strip()))
    elif image:
        cache = _export_from_image(image)
        manifest = cache / "classpath.txt"
        entries = [
            str(cache / line.strip().lstrip("/"))
            for line in manifest.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        harness = str(cache / IMAGE_HARNESS_JAR.lstrip("/"))
    else:
        raise CheckUnavailable(f"set {CLASSPATH_VARIABLE} or {IMAGE_VARIABLE} to the Paper server classpath")
    if not entries:
        raise CheckUnavailable("the resolved Paper classpath is empty")
    explicit_harness = os.environ.get(HARNESS_VARIABLE, "").strip()
    if explicit_harness:
        harness_entries: list[str] = []
        for component in explicit_harness.split(":"):
            if component.strip():
                harness_entries.extend(_expand(component.strip()))
        harness = ":".join(harness_entries)
    elif harness is None:
        found = [entry for entry in entries if PurePosixPath(entry).name == HARNESS_JAR_NAME]
        harness = found[0] if found else None
    entries = [entry for entry in entries if PurePosixPath(entry).name != HARNESS_JAR_NAME]
    return entries, harness


def write_tree(root: Path, files: dict[str, str]) -> None:
    for raw, content in files.items():
        destination = (root / raw).resolve()
        if not destination.is_relative_to(root.resolve()):
            raise CheckUnavailable("request file escaped the staging directory")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")


def compile_sources(sources: list[Path], classpath: list[str], output: Path, staging: Path) -> list[str]:
    """Run javac; return diagnostics with the staging prefix removed."""
    output.mkdir(parents=True, exist_ok=True)
    command = [
        javac(),
        "--release",
        JAVA_RELEASE,
        "-proc:none",
        "-Xlint:none",
        "-encoding",
        "UTF-8",
        "-Xmaxerrs",
        str(MAX_FINDINGS),
        "-cp",
        ":".join(classpath),
        "-d",
        str(output),
        *[str(path) for path in sources],
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=600)
    except subprocess.TimeoutExpired as error:
        raise CheckUnavailable("javac timed out") from error
    except OSError as error:
        raise CheckUnavailable(f"could not run javac: {error}") from error
    if result.returncode == 0:
        return []
    prefix = str(staging.resolve()) + os.sep
    findings: list[str] = []
    for line in (result.stdout + result.stderr).splitlines():
        text = line.replace(prefix, "").rstrip()
        if text and not text.startswith("Note:"):
            findings.append(text)
    if not findings:
        findings.append(f"javac failed with exit status {result.returncode}")
    return findings


def check_project(files: dict[str, str], classpath: list[str]) -> list[str]:
    """Compile a clean-room plugin tree and confirm its plugin.yml main class exists."""
    findings: list[str] = []
    metadata = files.get("src/main/resources/plugin.yml")
    if metadata is None:
        findings.append("src/main/resources/plugin.yml is missing")
    sources = sorted(path for path in files if path.startswith("src/main/java/") and path.endswith(".java"))
    if not sources:
        findings.append("no Java sources below src/main/java")
    if findings:
        return findings
    assert metadata is not None
    main_match = _PLUGIN_MAIN_LINE.search(metadata)
    if _PLUGIN_NAME_LINE.search(metadata) is None:
        findings.append("plugin.yml: name is missing or not a plain identifier")
    if main_match is None:
        findings.append("plugin.yml: main is missing or not a fully qualified class name")
    with tempfile.TemporaryDirectory(prefix="minecraft-project-check-") as raw:
        staging = Path(raw)
        write_tree(staging, files)
        output = staging / "classes"
        findings.extend(compile_sources([staging / path for path in sources], classpath, output, staging))
        if not findings and main_match is not None:
            main_class = output / (main_match.group(1).replace(".", "/") + ".class")
            if not main_class.is_file():
                findings.append(
                    f"plugin.yml: main class {main_match.group(1)} was not produced by the sources"
                )
    return findings


def check_verifier(files: dict[str, str], classpath: list[str], harness: str | None) -> list[str]:
    """Compile tests/TaskSuite.java against the server classpath and the harness only.

    The submission is deliberately absent from the classpath: the suite must reach
    the plugin through reflection, exactly as the verifier contract requires.
    """
    source = files.get("tests/TaskSuite.java")
    if source is None:
        return ["tests/TaskSuite.java is missing"]
    if harness is None:
        raise CheckUnavailable(
            f"the GcbHarness jar is unavailable; set {HARNESS_VARIABLE} or {IMAGE_VARIABLE}"
        )
    with tempfile.TemporaryDirectory(prefix="minecraft-verifier-check-") as raw:
        staging = Path(raw)
        suite = staging / "tests" / "TaskSuite.java"
        suite.parent.mkdir(parents=True)
        suite.write_text(source, encoding="utf-8")
        return compile_sources([suite], [*classpath, *harness.split(":")], staging / "classes", staging)


def main(mode: str) -> int:
    try:
        files = read_request()
        classpath, harness = resolve_classpath()
        if mode == "project":
            findings = check_project(files, classpath)
        else:
            findings = check_verifier(files, classpath, harness)
    except CheckUnavailable as error:
        sys.stderr.write(f"minecraft {mode} check unavailable: {error}\n")
        return respond(False, [])
    except (OSError, subprocess.SubprocessError) as error:
        sys.stderr.write(f"minecraft {mode} check failed: {type(error).__name__}\n")
        return respond(False, [])
    return respond(True, findings)
