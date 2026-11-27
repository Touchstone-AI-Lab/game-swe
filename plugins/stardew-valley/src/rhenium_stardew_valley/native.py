"""Explicit macOS maintenance diagnostics; never an eligible full benchmark pass."""

from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import shutil
import signal
import stat
import subprocess
import tempfile
import urllib.request
import zipfile
from contextlib import nullcontext, suppress
from pathlib import Path, PurePosixPath
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import (
    RuntimeActionRequired,
    RuntimeArtifact,
    RuntimeBuilder,
    RuntimeProgress,
    RuntimeSpec,
)
from rhenium.util import hash_tree

from .catalog import StardewCatalog, StardewTask
from .evaluator import StardewRuntime

NATIVE_ID = "stardew-1.6.15-smapi-4.1.10-macos-diagnostic"
GAME_SHA256 = "8937c582cad1c1127017944778c4102467bf299aea44869491f28ab0ec84cd73"
SDK_IMAGE = (
    "mcr.microsoft.com/dotnet/sdk:8.0-bookworm-slim@"
    "sha256:e2f26f26169fd10d6f1b426e01c97397717b32e9d5ab4ee4a7d5497ed9403007"
)
SMAPI_URL = "https://github.com/Pathoschild/SMAPI/releases/download/4.1.10/SMAPI-4.1.10-installer.zip"
SMAPI_SHA256 = "8c127148a76c890e485aea73910189dc41c80f822c2a0a5e3b0e762b4ee3a93e"


def safe_tree(root: Path) -> None:
    """Reject links/special files before copying or trusting a content identity."""
    for item in [root, *root.rglob("*")]:
        mode = item.lstat().st_mode
        if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise ValueError("native inputs must not contain links or special files")


def _relative(value: str) -> Path:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise ValueError("native input path is not a normalized relative path")
    return Path(value)


def sandbox_profile(writable: Path, readable: tuple[Path, ...]) -> str:
    def subpath(path: Path | str) -> str:
        return f"(subpath {json.dumps(str(path))})"

    system = (
        "/System",
        "/usr",
        "/bin",
        "/sbin",
        "/Library/Apple",
        "/Library/Preferences",
        "/private/etc",
        "/private/var/db",
        "/dev",
    )
    read_roots: tuple[str | Path, ...] = (*system, writable, *readable)
    reads = " ".join(subpath(path) for path in read_roots)
    return (
        "(version 1)\n(deny default)\n"
        "(allow process-exec process-fork sysctl-read mach-lookup iokit-open)\n"
        "(allow signal (target self))\n"
        "(allow process-info* (target self))\n"
        "(allow file-read-metadata)\n"
        # dyld/libignition opens the root directory as an openat anchor. This
        # permits reading that directory itself, not the files beneath it.
        '(allow file-read* (literal "/"))\n'
        f"(allow file-read* {reads})\n"
        f"(allow file-map-executable {reads})\n"
        f'(allow file-write* {subpath(writable)} (literal "/dev/null"))\n'
        "(allow ipc-posix-shm ipc-posix-sem)\n(deny network*)\n"
    )


def process_environment(work: Path, sdk: Path) -> dict[str, str]:
    # No inherited account/model credentials, shell startup settings, or global
    # NuGet config. XDG_CONFIG_HOME is .NET 6's ApplicationData/save location.
    return {
        "PATH": f"{sdk}:/usr/bin:/bin:/usr/sbin:/sbin",
        "LANG": "en_US.UTF-8",
        "TMPDIR": str(work / "tmp"),
        "XDG_CONFIG_HOME": str(work / "config"),
        "XDG_DATA_HOME": str(work / "data"),
        "DOTNET_CLI_HOME": str(work / "cli"),
        "CFFIXED_USER_HOME": str(work / "user"),
        "DOTNET_ROOT": str(sdk),
        "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
        "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
        "DOTNET_CLI_WORKLOAD_UPDATE_NOTIFY_DISABLE": "1",
        "NUGET_PACKAGES": str(work / "nuget"),
        "SMAPI_NO_TERMINAL": "true",
        "SMAPI_USE_CURRENT_SHELL": "true",
    }


def run_process(
    args: list[str],
    work: Path,
    sdk: Path,
    log: Path,
    *,
    cwd: Path | None = None,
    extra: dict[str, str] | None = None,
    timeout: float = 900,
) -> subprocess.CompletedProcess[str]:
    if platform.system() != "Darwin" or not Path("/usr/bin/sandbox-exec").is_file():
        raise RuntimeError("macOS diagnostics require sandbox-exec on a logged-in macOS desktop")
    for name in ("tmp", "config", "data", "cli", "user", "nuget"):
        (work / name).mkdir(parents=True, exist_ok=True)
    env = process_environment(work, sdk)
    env.update(extra or {})
    policy = sandbox_profile(work.resolve(), (sdk.resolve(),))
    command = ["/usr/bin/sandbox-exec", "-p", policy, *args]
    log.parent.mkdir(parents=True, exist_ok=True)
    timed_out = False
    with log.open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(
            command,
            cwd=cwd or work,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stream,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        try:
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        finally:
            # Only this command's new group, never other running game instances.
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
    output = log.read_text(encoding="utf-8", errors="replace")
    code = 124 if timed_out else process.returncode
    log.write_text(f"exit_code={code}\n{output}", encoding="utf-8")
    return subprocess.CompletedProcess(args, code, output, "")


def _download(url: str, destination: Path, expected: str, algorithm: str) -> None:
    if destination.is_file() and hashlib.new(algorithm, destination.read_bytes()).hexdigest() == expected:
        return
    with urllib.request.urlopen(url, timeout=60) as response:
        payload = response.read()
    if hashlib.new(algorithm, payload).hexdigest() != expected:
        raise RuntimeError("native dependency download checksum mismatch")
    destination.write_bytes(payload)


def _extract_zip(archive: zipfile.ZipFile, target: Path) -> None:
    for info in archive.infolist():
        relative = _relative(info.filename.rstrip("/"))
        if stat.S_ISLNK(info.external_attr >> 16):
            raise ValueError("native dependency archive contains a symlink")
        path = target / relative
        if info.is_dir():
            path.mkdir(parents=True, exist_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(info))
            path.chmod(0o755 if info.external_attr >> 16 & 0o111 else 0o644)


def read_cases(path: Path) -> tuple[str, ...]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not value or not all(isinstance(v, str) and v for v in value):
        raise ValueError("native diagnostic requires an explicit nonempty case-name list")
    if len(set(value)) != len(value):
        raise ValueError("native diagnostic case names must be unique")
    return tuple(value)


def read_verdict(path: Path, expected: tuple[str, ...]) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("native verdict must be an object")
    cases = value.get("cases")
    if not isinstance(cases, list) or len(cases) != len(expected):
        raise ValueError("native verdict did not run every requested case")
    if not all(isinstance(case, dict) and type(case.get("Passed")) is bool for case in cases):
        raise ValueError("native verdict case outcomes must be booleans")
    names = [case.get("Name") for case in cases]
    if any(not isinstance(name, str) for name in names) or set(names) != set(expected):
        raise ValueError("native verdict has unexpected, duplicate, or missing case names")
    passed = sum(case["Passed"] for case in cases)
    if value.get("fatal") is not None or any(
        type(value.get(key)) is not int or value[key] != count
        for key, count in (("passed", passed), ("failed", len(cases) - passed))
    ):
        raise ValueError("native verdict has fatal errors or inconsistent counts")
    return {
        "engineComplete": True,
        "assertionsPassed": passed == len(cases),
        "passedAssertions": passed,
        "failedAssertions": len(cases) - passed,
        "cases": cases,
    }


def require_native_launcher(game: Path, returncode: int) -> None:
    if not (game / "StardewModdingAPI").is_file():
        raise RuntimeActionRequired(
            "macos-native-launcher-removed",
            "macOS native launcher disappeared during startup; review the host security event before retry",
            {
                "exitCode": returncode,
                "gameCopy": str(game),
                "message": "No security policy was disabled and no binary was re-signed. "
                "Review the macOS warning or choose a separately reviewed loader version.",
            },
        )


class StardewNativeBuilder(RuntimeBuilder):
    def __init__(self, context: BenchmarkContext, catalog: StardewCatalog):
        self.context, self.catalog = context, catalog
        self.compiler = StardewRuntime(context, catalog)

    def doctor(self, spec: RuntimeSpec) -> dict[str, Any]:
        del spec
        available = platform.system() == "Darwin" and Path("/usr/bin/sandbox-exec").is_file()
        if available:
            try:
                probe = subprocess.run(
                    ["/usr/bin/arch", "-x86_64", "/usr/bin/true"],
                    capture_output=True,
                    timeout=10,
                    check=False,
                )
                available = probe.returncode == 0
            except (OSError, subprocess.SubprocessError):
                available = False
        if available:
            available = bool(self.compiler.status()["available"])
        return {
            "available": available,
            "id": "stardew-macos-diagnostic",
            "completeEligible": False,
            "reason": None if available else "requires macOS, sandbox-exec, x86_64 execution and Docker",
            "desktopRequired": True,
            "gameVersion": "1.6.15.24356",
            "smapiVersion": "4.1.10",
        }

    def prepare(
        self,
        spec: RuntimeSpec,
        source: Path,
        destination: Path,
        *,
        progress: RuntimeProgress,
    ) -> RuntimeArtifact:
        if not self.doctor(spec)["available"]:
            raise RuntimeError("macOS native prerequisites are unavailable; no installer was run")
        if not all(task.clean_room_synthetic for task in self.catalog.tasks):
            raise ValueError("native maintenance runtime currently accepts only clean-room synthetic packs")
        safe_tree(source)
        expected = spec.source.get("expectedFiles", [])
        if not isinstance(expected, list) or not all(isinstance(item, str) for item in expected):
            raise ValueError("invalid native expectedFiles")
        for item in ["MacOS/Stardew Valley.dll", "MacOS/Stardew Valley", "Resources/Content", *expected]:
            if not (source / _relative(item)).exists():
                raise ValueError("local source is missing required native game files")
        if spec.source.get("sha256") is not None and spec.source["sha256"] != hash_tree(source):
            raise ValueError("local source SHA-256 mismatch")
        if hashlib.sha256((source / "MacOS/Stardew Valley.dll").read_bytes()).hexdigest() != GAME_SHA256:
            raise ValueError("native diagnostics require the reviewed macOS 1.6.15.24356 assembly")
        if (source / "MacOS/Stardew Valley").read_bytes()[:4] != b"\xcf\xfa\xed\xfe":
            raise ValueError("local source is not the macOS x86_64 game")
        destination.mkdir(parents=True, exist_ok=True, mode=0o700)
        artifacts = destination / "artifacts"
        artifacts.mkdir(exist_ok=True)
        progress(5, "acquiring pinned compilation image and macOS SMAPI archive")
        pull = self.compiler._docker(["pull", SDK_IMAGE], timeout=900)
        if pull.returncode:
            raise RuntimeError("pinned compiler image acquisition failed")
        inspect = self.compiler._docker(["image", "inspect", SDK_IMAGE, "--format", "{{.Id}}"], timeout=30)
        compiler_image = inspect.stdout.strip()
        if inspect.returncode or not compiler_image.startswith("sha256:"):
            raise RuntimeError("compiler image has no immutable local identity")
        _download(SMAPI_URL, artifacts / "smapi.zip", SMAPI_SHA256, "sha256")
        # Keep unsuccessful preparations and their logs in owned local state.
        # Runtime prune removes them; no user installation is touched.
        with nullcontext(tempfile.mkdtemp(prefix="native-prepare-", dir=destination)) as raw:
            work = Path(raw)
            # Fetch only the trusted empty project's targeting packs, before any
            # game or generated MSBuild input is copied into this writable sandbox.
            restore = work / "restore"
            restore.mkdir()
            (restore / "Restore.csproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup>'
                "<TargetFramework>net6.0</TargetFramework></PropertyGroup></Project>",
                encoding="utf-8",
            )
            config = work / "NuGet.Config"
            config.write_text(
                "<configuration><packageSources><clear />"
                '<add key="nuget" value="https://api.nuget.org/v3/index.json" />'
                "</packageSources></configuration>",
                encoding="utf-8",
            )
            result = self.compile(
                ["restore", "/work/restore/Restore.csproj", "--configfile", "/work/NuGet.Config"],
                work,
                compiler_image,
                destination / "restore.log",
                network=True,
            )
            if result.returncode:
                raise RuntimeError("native SDK targeting-pack preparation failed; inspect restore.log")
            config.write_text(
                "<configuration><packageSources><clear /></packageSources></configuration>", encoding="utf-8"
            )
            progress(35, "copying local game and unpacking SMAPI without modifying the installation")
            game = work / "game/Contents/MacOS"
            shutil.copytree(source, work / "game/Contents")
            with zipfile.ZipFile(artifacts / "smapi.zip") as archive:
                data = archive.read("SMAPI 4.1.10 installer/internal/macOS/install.dat")
            with zipfile.ZipFile(io.BytesIO(data)) as payload:
                _extract_zip(payload, game)
            (game / "StardewModdingAPI").chmod(0o755)
            (game / "smapi-internal/config.user.json").write_text(
                '{"CheckForUpdates": false}', encoding="utf-8"
            )
            # No personal/user-provided Mods are acquired. Only the trusted fixture
            # harness is deployed while preparing the deterministic save.
            task = self.catalog.tasks[0]
            harness = work / "harness"
            shutil.copytree(
                self.context.pack_root / "private/harbor" / task.id / "environment/gcb-harness", harness
            )
            progress(50, "building fixture harness without network")
            result = self.build(
                harness / "GcbHarness.csproj", game, work, compiler_image, destination / "build-harness.log"
            )
            if result.returncode:
                raise RuntimeError("native fixture harness build failed; inspect build-harness.log")
            mod = game / "Mods/GcbHarness"
            mod.mkdir()
            shutil.copy2(harness / "bin/Release/GcbHarness.dll", mod)
            shutil.copy2(harness / "manifest.json", mod)
            progress(65, "starting real macOS game to create a disposable fixture save")
            result = run_process(
                [str(game / "StardewModdingAPI"), "--no-terminal"],
                work,
                game,
                destination / "fixture-game.log",
                cwd=game,
                extra={
                    "GCB_MODE": "gen-save",
                    "GCB_RESULT_PATH": str(work / "fixture-result.json"),
                    "COREHOST_TRACE": "1",
                    "COREHOST_TRACEFILE": str(work / "host.trace"),
                },
            )
            require_native_launcher(game, result.returncode)
            saves = list((work / "config/StardewValley/Saves").glob("*_*"))
            if result.returncode or len(saves) != 1 or not (saves[0] / "SaveGameInfo").is_file():
                raise RuntimeError("native real-game fixture did not complete; inspect fixture-game.log")
            shutil.rmtree(mod)
            payload_root = work / "payload"
            payload_root.mkdir()
            for name in ("game", "config", "nuget"):
                shutil.move(work / name, payload_root / name)
            (payload_root / "compiler-image.txt").write_text(compiler_image, encoding="utf-8")
            shutil.copy2(config, payload_root / "NuGet.Config")
            (payload_root / "save-name.txt").write_text(saves[0].name, encoding="utf-8")
            safe_tree(payload_root)
            identity = hash_tree(payload_root)
            target = destination / identity
            if target.exists():
                raise ValueError("native immutable artifact already exists; verify it before re-preparing")
            shutil.move(payload_root, target)
        progress(100, "native diagnostic runtime prepared; not eligible for full benchmark scoring")
        return RuntimeArtifact(
            runtime_key=f"stardew-valley/{spec.id}",
            fingerprint=spec.fingerprint(plugin_id="stardew-valley", plugin_version="0.6.0"),
            kind="macos-diagnostic",
            identity=f"sha256:{identity}",
            location=str(target),
            metadata={
                "network": "denied-by-seatbelt",
                "completeEligible": False,
                "gameVersion": "1.6.15.24356",
                "compilerImage": compiler_image,
            },
        )

    def build(
        self, project: Path, game: Path, work: Path, compiler_image: str, log: Path
    ) -> subprocess.CompletedProcess[str]:
        return self.compile(
            [
                "build",
                "/work/" + project.relative_to(work).as_posix(),
                "-c",
                "Release",
                "--nologo",
                "-p:GamePath=/work/" + game.relative_to(work).as_posix(),
                "-p:EnableModDeploy=false",
                "-p:EnableModZip=false",
                "-p:RestoreConfigFile=/work/NuGet.Config",
                "-p:UseSharedCompilation=false",
            ],
            work,
            compiler_image,
            log,
        )

    def compile(
        self,
        args: list[str],
        work: Path,
        image: str,
        log: Path,
        *,
        network: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        result = self.compiler._docker(
            [
                "run",
                "--rm",
                "--pull=never",
                f"--network={'bridge' if network else 'none'}",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges:true",
                "--pids-limit=512",
                "--cpus=4",
                "--memory=8g",
                "--mount",
                f"type=bind,source={work},target=/work",
                "--workdir",
                "/work",
                "--env",
                "NUGET_PACKAGES=/work/nuget",
                "--env",
                "DOTNET_CLI_HOME=/work/cli",
                "--env",
                "DOTNET_CLI_TELEMETRY_OPTOUT=1",
                image,
                "dotnet",
                *args,
            ],
            timeout=300,
        )
        log.write_text(f"exit_code={result.returncode}\n{result.stdout}{result.stderr}", encoding="utf-8")
        return result

    def verify(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> dict[str, Any]:
        try:
            if artifact.kind != "macos-diagnostic" or not artifact.location:
                raise ValueError("wrong native artifact kind")
            if (
                artifact.runtime_key != f"stardew-valley/{spec.id}"
                or artifact.fingerprint
                != spec.fingerprint(
                    plugin_id="stardew-valley",
                    plugin_version="0.6.0",
                )
            ):
                raise ValueError("native artifact fingerprint mismatch")
            root = Path(artifact.location)
            safe_tree(root)
            if artifact.identity != f"sha256:{hash_tree(root)}":
                raise ValueError("native artifact content changed")
            if not (root / "compiler-image.txt").is_file() or not (root / "save-name.txt").is_file():
                raise ValueError("native artifact is incomplete")
            game = root / "game/Contents/MacOS"
            save = _relative((root / "save-name.txt").read_text().strip())
            if (
                len(save.parts) != 1
                or not (root / "config/StardewValley/Saves" / save / "SaveGameInfo").is_file()
            ):
                raise ValueError("native fixture save is incomplete")
            if (
                not os.access(game / "StardewModdingAPI", os.X_OK)
                or not (game.parent / "Resources/Content").is_dir()
            ):
                raise ValueError("native game is incomplete")
            if hashlib.sha256((game / "Stardew Valley.dll").read_bytes()).hexdigest() != GAME_SHA256:
                raise ValueError("native game assembly is not the pinned build")
            compiler_image = (root / "compiler-image.txt").read_text()
            if artifact.metadata.get("compilerImage") != compiler_image:
                raise ValueError("native compiler identity mismatch")
            inspected = self.compiler._docker(
                ["image", "inspect", compiler_image, "--format", "{{.Id}}"], timeout=30
            )
            if inspected.returncode or inspected.stdout.strip() != compiler_image:
                raise ValueError("native compiler is unavailable")
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
            return {"available": False, "reason": "native artifact is missing, changed, or invalid"}
        return {"available": True, "completeEligible": False, "network": "denied-by-seatbelt"}

    def prune(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> None:
        # No external resources: RuntimeManager deletes only its owned cache after
        # this hook. Never recursively delete an artifact-supplied location here.
        del spec, artifact


def evaluate_native(
    context: BenchmarkContext,
    task: StardewTask,
    submission: Path,
    artifact: RuntimeArtifact | None,
) -> dict[str, Any]:
    diagnostic: dict[str, Any] = {
        "status": "incomplete",
        "engineComplete": False,
        "assertionsPassed": False,
        "passedAssertions": 0,
        "failedAssertions": 0,
    }
    log = ""
    try:
        if not task.clean_room_synthetic or artifact is None or artifact.kind != "macos-diagnostic":
            raise ValueError("explicitly prepare the macOS diagnostic runtime for a synthetic pack")
        if not artifact.location:
            raise ValueError("native runtime has no location")
        root = Path(artifact.location)
        safe_tree(root)
        if artifact.identity != f"sha256:{hash_tree(root)}":
            raise ValueError("native runtime content identity mismatch")
        task_root = context.pack_root / "private/harbor" / task.id
        expected = read_cases(task_root / "tests/native-cases.json")
        safe_tree(submission)
        context.cache_dir.mkdir(parents=True, exist_ok=True)
        # Retain state-local logs and disposable copies for diagnosis. Never run a
        # submitted project in the real installation or the immutable artifact.
        work = Path(tempfile.mkdtemp(prefix="native-run-", dir=context.cache_dir))
        for name in ("game", "config", "nuget"):
            shutil.copytree(root / name, work / name)
        shutil.copy2(root / "NuGet.Config", work)
        game = work / "game/Contents/MacOS"
        compiler_image = (root / "compiler-image.txt").read_text()
        builder = StardewNativeBuilder(context, StardewCatalog.load(context.pack_root))
        shutil.copytree(submission / task.starter_name, work / "mod")
        shutil.copytree(task_root / "environment/gcb-harness", work / "harness")
        suite = task_root / "tests/TaskSuite.cs"
        if suite.is_symlink() or not suite.is_file():
            raise ValueError("native diagnostic requires a regular TaskSuite.cs")
        shutil.copy2(suite, work / "harness/TaskSuite.cs")
        log = f"native diagnostic logs: {work}\nimage=none\nnetwork=denied-by-seatbelt\n"
        for relative, name in (("mod/Synthetic.sln", "submission"), ("harness/GcbHarness.csproj", "harness")):
            result = builder.build(work / relative, game, work, compiler_image, work / f"build-{name}.log")
            log += result.stdout[-16000:]
            if result.returncode:
                raise RuntimeError(f"native {name} compilation failed")
        for source, name in ((work / "mod", "SyntheticTarget"), (work / "harness", "GcbHarness")):
            target = game / "Mods" / name
            target.mkdir()
            output = source / "bin/Release"
            for dll in output.glob("*.dll"):
                shutil.copy2(dll, target)
            shutil.copy2(source / "manifest.json", target)
        result_path = work / "result.json"
        result = run_process(
            [str(game / "StardewModdingAPI"), "--no-terminal"],
            work,
            game,
            work / "game.log",
            cwd=game,
            extra={
                "GCB_MODE": "run-suite",
                "GCB_SAVE_NAME": (root / "save-name.txt").read_text(),
                "GCB_RESULT_PATH": str(result_path),
            },
        )
        require_native_launcher(game, result.returncode)
        log += result.stdout[-16000:]
        if result.returncode:
            raise RuntimeError("native game exited abnormally or timed out")
        diagnostic.update(read_verdict(result_path, expected))
        diagnostic["status"] = "diagnostic-passed" if diagnostic["assertionsPassed"] else "diagnostic-failed"
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        log += f"\n{error}\n"
    # Native C# suite diagnostics do not execute Linux test.sh's extra steps and
    # are deliberately never equivalent to the frozen container-backed full gate.
    return {
        "score": 0.0,
        "complete": False,
        "passed": False,
        "runtime": diagnostic,
        "checks": [
            {
                "id": "native-game-diagnostic",
                "status": "incomplete",
                "score": 0.0,
                "maximum": 100.0,
                "message": "macOS maintenance diagnostic, not a full benchmark result",
            }
        ],
        "runtime_log": log,
    }
