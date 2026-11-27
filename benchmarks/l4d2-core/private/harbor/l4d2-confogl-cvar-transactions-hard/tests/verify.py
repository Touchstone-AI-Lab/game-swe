#!/usr/bin/env python3
from __future__ import annotations

import os
import pwd
import queue
import re
import shutil
import signal
import socket
import subprocess
import tempfile
import threading
import time
import uuid
from contextlib import suppress
from pathlib import Path


SUBMISSION = Path(os.environ.get("GCB_SUBMISSION", "/app/l4d2-competitive"))
TESTS = Path(os.environ.get("GCB_TESTS", "/tests"))
LOGS = Path(os.environ.get("GCB_LOGS", "/logs/verifier"))
RUNTIME = Path(os.environ.get("L4D2_ROOT", "/opt/l4d2"))
SM_ROOT = Path(os.environ.get("SOURCEMOD_ROOT", RUNTIME / "left4dead2/addons/sourcemod"))
COMPILER = SM_ROOT / "scripting/spcomp64"
PLUGIN_DIR = SM_ROOT / "plugins"
GAMEDATA_DIR = SM_ROOT / "gamedata"
DATA_DIR = SM_ROOT / "data"
SCRIPTING = SUBMISSION / "addons/sourcemod/scripting"
DEPENDENCY = TESTS / "deps/left4dhooks"
MARKER = "@@GCB_SM@@"
SERVER_REAP_SECONDS = 120
# Wall-clock budget for one boot to reach FINAL. A healthy boot needs 5-15 s; a congested
# host stalled plugin loading for over a minute, which must not become a verdict.
SUITE_DEADLINE_SECONDS = 240

SUITES = {
    name: tuple(re.findall(r'Case\("([^"\n]+)"', (TESTS / f"suite_{name}.sp").read_text()))
    for name in ("transactions",)
}
TARGETS = {name: "confoglcompmod.sp" for name in SUITES}

FORBIDDEN_SUFFIXES = {".smx", ".dll", ".exe", ".so", ".zip", ".7z", ".vpk", ".tar", ".gz"}
REQUIRED = (
    "LICENSE",
    "addons/sourcemod/scripting/confoglcompmod.sp",
    "addons/sourcemod/scripting/l4d2lib.sp",
)


class SubmissionFailure(RuntimeError):
    pass


class EnvironmentFailure(RuntimeError):
    pass


def validate_submission() -> None:
    if not SUBMISSION.is_dir():
        raise EnvironmentFailure(f"artifact missing: {SUBMISSION}")
    errors: list[str] = []
    files = 0
    total = 0
    sourcepawn = 0
    includes = 0
    for path in SUBMISSION.rglob("*"):
        logical = path.relative_to(SUBMISSION).as_posix()
        if path.is_symlink():
            errors.append(f"{logical}: symbolic links are not allowed")
            continue
        if path.name == ".git":
            errors.append(f"{logical}: Git metadata is not allowed")
        if not path.is_file():
            continue
        files += 1
        size = path.stat().st_size
        total += size
        if size > 3_000_000:
            errors.append(f"{logical}: file exceeds 3 MB")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"{logical}: compiled/archive artifact is not allowed")
        if path.suffix.lower() == ".sp":
            sourcepawn += 1
        if path.suffix.lower() == ".inc":
            includes += 1
        if path.suffix.lower() in {".sp", ".inc"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            if MARKER in text or "__GCB_NONCE__" in text:
                errors.append(f"{logical}: reserved verifier marker")
    if files > 2_500 or total > 30_000_000 or sourcepawn < 300 or includes < 50:
        errors.append(
            f"unexpected source tree shape: files={files} bytes={total} sp={sourcepawn} inc={includes}"
        )
    for relative in REQUIRED:
        if not (SUBMISSION / relative).is_file():
            errors.append(f"{relative}: required source is missing")
    license_text = (SUBMISSION / "LICENSE").read_text(encoding="utf-8", errors="replace") if (SUBMISSION / "LICENSE").is_file() else ""
    if "GNU GENERAL PUBLIC LICENSE" not in license_text:
        errors.append("LICENSE: upstream GPL attribution was removed")
    if errors:
        raise SubmissionFailure("source/package checks failed:\n- " + "\n- ".join(errors))
    print(f"source/package checks passed: files={files} bytes={total} sp={sourcepawn} inc={includes}")


def compile_plugin(source: Path, output: Path, includes: tuple[Path, ...]) -> None:
    command = [str(COMPILER)]
    for include in includes:
        command.extend(("-i", str(include)))
    command.extend(("-o", str(output), str(source)))
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode:
        raise SubmissionFailure(f"SourcePawn compile failed for {source.name}:\n{completed.stdout}{completed.stderr}")


def copy_tree(source: Path, destination: Path) -> None:
    for path in source.rglob("*"):
        if path.is_file():
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def prepare_runtime(temp: Path) -> tuple[Path, Path]:
    binary = RUNTIME / "srcds_run"
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise EnvironmentFailure("L4D2 dedicated-server binary is unavailable")
    if not COMPILER.is_file() or not os.access(COMPILER, os.X_OK):
        raise EnvironmentFailure("pinned SourceMod compiler is unavailable")
    if list(PLUGIN_DIR.rglob("*.smx")):
        raise EnvironmentFailure("verifier SourceMod plugin directory is not clean")
    dependency_source = DEPENDENCY / "sourcemod/scripting/left4dhooks.sp"
    if not dependency_source.is_file():
        raise EnvironmentFailure("verifier-only Left4DHooks source fixture is missing")
    dependency_binary = temp / "00_left4dhooks.smx"
    compile_plugin(
        dependency_source,
        dependency_binary,
        (SM_ROOT / "scripting/include", DEPENDENCY / "sourcemod/scripting/include"),
    )
    # Never overwrite pinned core SDKTools/SDKHooks/Left4DHooks gameconfigs.
    copy_tree(DEPENDENCY / "sourcemod/gamedata", GAMEDATA_DIR)
    copy_tree(DEPENDENCY / "sourcemod/data", DATA_DIR)
    copy_tree(TESTS / "deps/gcb/gamedata", GAMEDATA_DIR)
    (PLUGIN_DIR / "disabled").mkdir(exist_ok=True)
    copy_tree(SUBMISSION / "addons/sourcemod/configs/confogl", SM_ROOT / "configs/confogl")
    (SM_ROOT / "configs/confogl").mkdir(parents=True, exist_ok=True)
    shutil.copy2(SUBMISSION / "cfg/cfgogl/zonemod/mapinfo.txt", SM_ROOT / "configs/confogl/mapinfo.txt")
    copy_tree(SUBMISSION / "addons/sourcemod/translations", SM_ROOT / "translations")
    steam = pwd.getpwnam("steam")
    for root in (GAMEDATA_DIR, DATA_DIR):
        for path in root.rglob("*"):
            if path.exists():
                os.chown(path, steam.pw_uid, steam.pw_gid)
    return binary, dependency_binary


def available_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    with suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        reap_killed_server(process)


def reap_killed_server(process: subprocess.Popen[str]) -> None:
    # SIGKILL cannot be ignored, but a loaded host can take well over five seconds
    # to tear down the server's threads and memory. Waiting for that is not a
    # verdict; a server that is still not reaped is an environment failure.
    try:
        process.wait(timeout=SERVER_REAP_SECONDS)
    except subprocess.TimeoutExpired as error:
        raise EnvironmentFailure("dedicated server was not reaped after SIGKILL") from error


def collect(process: subprocess.Popen[str], final_prefix: str, timeout: int = SUITE_DEADLINE_SECONDS) -> str:
    assert process.stdout is not None
    lines: queue.Queue[str | None] = queue.Queue()
    output: list[str] = []

    def reader() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            lines.put(line)
        lines.put(None)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            try:
                line = lines.get(timeout=0.2)
            except queue.Empty:
                if process.poll() is not None:
                    break
                continue
            if line is None:
                break
            output.append(line)
            if final_prefix in line:
                break
    finally:
        stop_process(process)
        thread.join(timeout=2)
        while not lines.empty():
            line = lines.get_nowait()
            if line is not None:
                output.append(line)
    return "".join(output)


def parse_suite(log: str, suite: str, nonce: str) -> list[tuple[str, bool, str]]:
    prefix = f"{MARKER}{nonce}:"
    observed: dict[str, tuple[bool, str]] = {}
    duplicate: set[str] = set()
    finals: list[tuple[int, int]] = []
    for line in log.splitlines():
        if prefix not in line:
            continue
        fields = line.split(prefix, 1)[1].strip().split(":", 3)
        if len(fields) == 4 and fields[0] == "CASE" and fields[2] in {"PASS", "FAIL"}:
            if fields[1] in observed:
                duplicate.add(fields[1])
            observed[fields[1]] = (fields[2] == "PASS", fields[3])
        elif len(fields) == 3 and fields[0] == "FINAL":
            with suppress(ValueError):
                finals.append((int(fields[1]), int(fields[2])))
    expected = SUITES[suite]
    runtime_error = bool(re.search(
        r"\[SM\] Exception reported|Native is not bound|Plugin .* failed to load",
        log,
        re.I,
    ))
    valid = (
        not runtime_error
        and not duplicate
        and set(observed) == set(expected)
        and len(finals) == 1
        and finals[0][1] == len(expected)
        and finals[0][0] == sum(value[0] for value in observed.values())
    )
    if not valid:
        detail = failure_detail(log, reported_final=bool(finals))
        return [(name, False, detail) for name in expected]
    return [(name, *observed[name]) for name in expected]


def failure_detail(log: str, *, reported_final: bool = True) -> str:
    """Name the reason a suite was rejected; the text never changes a verdict.

    Engine start-up noise ("Invalid counterterrorist spawnpoint", "dlopen ... with
    error:", "breakpad crash handler") is present in every boot and is never reported.
    """
    lines = [line.strip() for line in log.splitlines()]
    for index, line in enumerate(lines):
        if re.search(r"\[SM\] Exception reported|Native is not bound|Plugin .* failed to load", line, re.I):
            if line.endswith(":"):
                reason = next((item for item in lines[index + 1:index + 4] if item.strip("=")), "")
                return f"{line} {reason}".strip()
            return line
    if not reported_final:
        return "server exited or timed out before the suite reported FINAL"
    return "suite did not complete its exact case contract"


def run_suite(binary: Path, dependency_binary: Path, temp: Path, suite: str) -> tuple[list[tuple[str, bool, str]], str]:
    nonce = uuid.uuid4().hex
    target_source = SCRIPTING / TARGETS[suite]
    target_plugin = PLUGIN_DIR / "disabled/02_confogl.smx"
    core_plugin = PLUGIN_DIR / dependency_binary.name
    suite_source_text = (TESTS / "common.inc").read_text(encoding="utf-8") + "\n" + (TESTS / f"suite_{suite}.sp").read_text(encoding="utf-8")
    if suite_source_text.count("__GCB_NONCE__") != 1:
        raise EnvironmentFailure(f"suite_{suite}.sp has an invalid nonce placeholder")
    suite_source = temp / f"suite_{suite}.sp"
    suite_source.write_text(suite_source_text.replace("__GCB_NONCE__", nonce), encoding="utf-8")
    suite_plugin = PLUGIN_DIR / f"99_gcb_{suite}.smx"
    target_binary = temp / "compiled-score.smx"
    if not target_binary.exists():
        compile_plugin(target_source, target_binary,
                       (SM_ROOT / "scripting/include", SCRIPTING / "include"))
    shutil.copy2(target_binary, target_plugin)
    shutil.copy2(dependency_binary, core_plugin)
    compile_plugin(
        suite_source,
        suite_plugin,
        (SM_ROOT / "scripting/include", DEPENDENCY / "sourcemod/scripting/include", SCRIPTING / "include"),
    )
    steam = pwd.getpwnam("steam")
    for plugin in (core_plugin, target_plugin, suite_plugin):
        os.chown(plugin, steam.pw_uid, steam.pw_gid)
    command = [
        str(binary), "-game", "left4dead2", "-console", "-insecure", "-norestart",
        "+sv_lan", "1", "+sv_hibernate_when_empty", "0", "+hostport", str(available_port()),
        "+map", "c1m1_hotel", "coop",
    ]
    environment = {
        "HOME": "/home/steam",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "SteamAppId": "550",
    }
    process = subprocess.Popen(
        command,
        cwd=RUNTIME,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        start_new_session=True,
        user=steam.pw_uid,
        group=steam.pw_gid,
        extra_groups=[],
    )
    try:
        log = collect(process, f"{MARKER}{nonce}:FINAL:")
    finally:
        for plugin in (suite_plugin, target_plugin, core_plugin):
            plugin.unlink(missing_ok=True)
    (LOGS / f"server-{suite}.log").write_text(log, encoding="utf-8")
    return parse_suite(log, suite, nonce), log


def main() -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    try:
        validate_submission()
        with tempfile.TemporaryDirectory(prefix="gcb-competitive-") as directory:
            temp = Path(directory)
            binary, dependency_binary = prepare_runtime(temp)
            all_results: list[tuple[str, bool, str]] = []
            selected = os.environ.get("GCB_DIAGNOSTIC_SUITE")
            suite_names = (selected,) if selected in SUITES else tuple(SUITES)
            for suite in suite_names:
                results, log = run_suite(binary, dependency_binary, temp, suite)
                (LOGS / f"server-{suite}.log").write_text(log, encoding="utf-8")
                all_results.extend(results)
        expected_count = sum(len(SUITES[suite]) for suite in suite_names)
        if len(all_results) != expected_count or len({name for name, _, _ in all_results}) != expected_count:
            raise EnvironmentFailure("verifier assembled an invalid global case set")
        for name, passed, detail in all_results:
            print(f"{'PASS' if passed else 'FAIL'} {name}: {detail}")
        passed_count = sum(passed for _, passed, _ in all_results)
        print(f"managed SourceMod cases passed: {passed_count}/{expected_count}")
        if passed_count != expected_count:
            raise SubmissionFailure("one or more private behavior cases failed")
    except EnvironmentFailure as error:
        print(f"INVALID_ENVIRONMENT: {error}")
        return 2
    except (SubmissionFailure, OSError) as error:
        print(f"SUBMISSION_FAILED: {error}")
        return 1
    print("VERIFICATION_PASSED: source checks, compile, and all real-server cases passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
