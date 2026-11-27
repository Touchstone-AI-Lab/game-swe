#!/usr/bin/env python3
from __future__ import annotations

import os
import queue
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from contextlib import suppress
from pathlib import Path


SUBMISSION = Path(os.environ.get("GCB_SUBMISSION", "/app/linge-hud"))
TESTS = Path(os.environ.get("GCB_TESTS", "/tests"))
LOGS = Path(os.environ.get("GCB_LOGS", "/logs/verifier"))
RUNTIME = Path(os.environ.get("L4D2_ROOT", "/opt/l4d2"))
SERVER_MARKER = "@@GCB_L4D2@@"
RESERVED_SUITE_PREFIX = "gcb_"
EXPECTED_CASES = 42
MAX_FILES = 500
MAX_FILE_BYTES = 2_000_000
MAX_TREE_BYTES = 20_000_000
FORBIDDEN_SUFFIXES = {".dll", ".exe", ".so", ".vpk", ".zip", ".7z", ".tar", ".gz"}
REQUIRED_FILES = (
    "LICENSE",
    "vscripts/LinGe/HUD.nut",
    "vscripts/LinGe/Base.nut",
    "vscripts/LinGe/VSLib.nut",
    "vscripts/director_base_addon.nut",
)


class SubmissionFailure(RuntimeError):
    pass


class EnvironmentFailure(RuntimeError):
    pass


def scan_squirrel(source: str) -> list[str]:
    """Conservative delimiter/string diagnostics; the real server remains authoritative."""

    errors: list[str] = []
    stack: list[tuple[str, int]] = []
    pairs = {")": "(", "]": "[", "}": "{"}
    line = 1
    index = 0
    state = "code"
    quote = ""
    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if char == "\n":
            line += 1
        if state == "line-comment":
            if char == "\n":
                state = "code"
        elif state == "block-comment":
            if char == "*" and following == "/":
                state = "code"
                index += 1
        elif state == "string":
            if char == "\\":
                index += 1
            elif char == quote:
                state = "code"
        elif state == "raw-string":
            if char == '"' and following == '"':
                index += 1
            elif char == '"':
                state = "code"
        elif char == "/" and following == "/":
            state = "line-comment"
            index += 1
        elif char == "/" and following == "*":
            state = "block-comment"
            index += 1
        elif char in {'"', "'"}:
            state = "raw-string" if char == '"' and index > 0 and source[index - 1] == "@" else "string"
            quote = char
        elif char in "([{":
            stack.append((char, line))
        elif char in ")]}":
            if not stack or stack[-1][0] != pairs[char]:
                errors.append(f"line {line}: unmatched {char}")
            else:
                stack.pop()
        index += 1
    if state == "block-comment":
        errors.append("unterminated block comment")
    elif state in {"string", "raw-string"}:
        errors.append(f"line {line}: unterminated string")
    errors.extend(f"line {opened_line}: unclosed {opened}" for opened, opened_line in stack)
    return errors


def validate_submission() -> None:
    if not SUBMISSION.is_dir():
        raise EnvironmentFailure(f"submission directory is missing: {SUBMISSION}")
    if SUBMISSION.resolve() != SUBMISSION:
        raise SubmissionFailure("submission path resolves outside the expected workspace")

    errors: list[str] = []
    files: list[Path] = []
    total_bytes = 0
    nut_lines = 0
    for path in SUBMISSION.rglob("*"):
        logical = path.relative_to(SUBMISSION).as_posix()
        if path.is_symlink():
            errors.append(f"{logical}: symbolic links are not allowed")
            continue
        if path.name == ".git":
            errors.append(f"{logical}: Git metadata is not allowed in the submission")
        if not path.is_file():
            continue
        files.append(path)
        size = path.stat().st_size
        total_bytes += size
        if size > MAX_FILE_BYTES:
            errors.append(f"{logical}: file exceeds the 2 MB limit")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"{logical}: compiled or archive files are not allowed")
        if path.suffix.lower() != ".nut":
            continue
        raw = path.read_bytes()
        if b"\x00" in raw:
            errors.append(f"{logical}: NUL byte in Squirrel source")
            continue
        try:
            source = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            errors.append(f"{logical}: source is not UTF-8: {error}")
            continue
        nut_lines += len(source.splitlines())
        errors.extend(f"{logical}: {message}" for message in scan_squirrel(source))

    if len(files) > MAX_FILES:
        errors.append(f"project has {len(files)} files; maximum is {MAX_FILES}")
    if total_bytes > MAX_TREE_BYTES:
        errors.append(f"project has {total_bytes} bytes; maximum is {MAX_TREE_BYTES}")
    if nut_lines < 5000:
        errors.append(f"project has {nut_lines} Squirrel lines; expected at least 5000")
    for relative in REQUIRED_FILES:
        candidate = SUBMISSION / relative
        if not candidate.is_file() or candidate.is_symlink():
            errors.append(f"{relative}: required regular file is missing")

    license_path = SUBMISSION / "LICENSE"
    if license_path.is_file():
        license_text = license_path.read_text(encoding="utf-8", errors="replace")
        if "MIT License" not in license_text or "Copyright (c) 2021 LinGe" not in license_text:
            errors.append("LICENSE: upstream MIT attribution was removed or altered")

    focus_path = SUBMISSION / "vscripts/LinGe/HUD.nut"
    if focus_path.is_file():
        focus = focus_path.read_text(encoding="utf-8", errors="replace")
        forbidden_patterns = (
            r"GCB_L4D2",
            r"@@GCB_L4D2@@",
            r"__GCB_NONCE__",
            r"gcb_[0-9a-fA-F]",
        )
        for pattern in forbidden_patterns:
            if re.search(pattern, focus):
                errors.append(f"vscripts/LinGe/HUD.nut: forbidden verifier probe ({pattern})")

    scripts = SUBMISSION / "vscripts"
    if scripts.is_dir():
        for path in scripts.rglob("*"):
            if path.name.lower().startswith(RESERVED_SUITE_PREFIX):
                errors.append(f"{path.relative_to(SUBMISSION).as_posix()}: reserved verifier prefix")

    if errors:
        raise SubmissionFailure("source/package checks failed:\n- " + "\n- ".join(errors))
    print(f"source/package checks passed: files={len(files)} bytes={total_bytes} nut_lines={nut_lines}")


def runtime_paths() -> tuple[Path, Path, Path]:
    binary_names = ("srcds.exe",) if os.name == "nt" else ("srcds_run", "srcds_linux")
    binary = next(
        (candidate for candidate in (RUNTIME / name for name in binary_names) if candidate.is_file()),
        None,
    )
    game_dir = RUNTIME / "left4dead2"
    addons = game_dir / "addons"
    if binary is None or not os.access(binary, os.X_OK):
        raise EnvironmentFailure("L4D2 dedicated-server binary is missing or not executable")
    if not game_dir.is_dir() or not addons.is_dir():
        raise EnvironmentFailure("L4D2 game/addons directory is missing")
    allowed_infrastructure = {"readme.txt", "metamod", "metamod.vdf", "sourcemod"}
    foreign = sorted(
        path.name for path in addons.iterdir()
        if path.name.lower() not in allowed_infrastructure
    )
    if foreign:
        raise EnvironmentFailure(f"dedicated-server addon directory is not clean: {foreign}")
    return binary, game_dir, addons


def stage_addon(addons: Path, suite: Path, nonce: str) -> Path:
    source_scripts = SUBMISSION / "vscripts"
    director = source_scripts / "director_base_addon.nut"
    if not source_scripts.is_dir() or not director.is_file():
        raise SubmissionFailure("vscripts/director_base_addon.nut is required for server assertions")
    suite_source = suite.read_text(encoding="utf-8")
    if suite_source.count("__GCB_NONCE__") != 1:
        raise EnvironmentFailure("private server suite has an invalid nonce placeholder")

    addon = addons / f"gcb_{nonce[:16]}.vpk"
    if addon.exists():
        raise EnvironmentFailure("private addon staging path unexpectedly exists")
    staging_root = Path(tempfile.mkdtemp(prefix="gcb-l4d2-addon-"))
    unpacked = staging_root / "addon"
    try:
        scripts = unpacked / "scripts/vscripts"
        scripts.mkdir(parents=True)
        # Source normalizes VPK lookups to lower case on Linux. Preserve the
        # submitted tree, but case-fold every path in the temporary archive.
        for source in source_scripts.rglob("*"):
            if not source.is_file():
                continue
            relative = source.relative_to(source_scripts)
            destination = scripts.joinpath(*(part.lower() for part in relative.parts))
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        addon_info = SUBMISSION / "release/LinGe_VScripts-addoninfo.txt"
        if addon_info.is_file() and not addon_info.is_symlink():
            shutil.copy2(addon_info, unpacked / "addoninfo.txt")
        else:
            (unpacked / "addoninfo.txt").write_text(
                '"AddonInfo"\n{\n addonSteamAppID 550\n addontitle "GCB runtime"\n '
                'addonauthor "GameCodeBench"\n addonContent_Script 1\n}\n',
                encoding="utf-8",
            )
        with (scripts / "director_base_addon.nut").open("a", encoding="utf-8") as handle:
            handle.write(
                "\n// Injected only into the verifier's temporary addon copy.\n"
                + suite_source.replace("__GCB_NONCE__", nonce)
                + "\n"
            )
        try:
            import vpk
        except ImportError as error:
            raise EnvironmentFailure("VPK v1 packer is missing from the verifier image") from error
        package = vpk.new(str(unpacked))
        package.version = 1
        package.save(str(addon))
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)
    if not addon.is_file() or addon.stat().st_size == 0:
        raise EnvironmentFailure("private addon VPK was not created")
    addon.chmod(0o644)
    return addon


def available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "posix":
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
    else:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait(timeout=5)


def collect_server(process: subprocess.Popen[str], nonce: str, timeout: int) -> str:
    assert process.stdout is not None
    output: list[str] = []
    lines: queue.Queue[str | None] = queue.Queue()

    def read_output() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            lines.put(line)
        lines.put(None)

    reader = threading.Thread(target=read_output, name="gcb-l4d2-log", daemon=True)
    reader.start()
    deadline = time.monotonic() + timeout
    final_prefix = f"{SERVER_MARKER}{nonce}:FINAL:"
    try:
        while time.monotonic() < deadline:
            try:
                line = lines.get(timeout=min(0.1, max(0.01, deadline - time.monotonic())))
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
        reader.join(timeout=2)
        while not lines.empty():
            line = lines.get_nowait()
            if line is not None:
                output.append(line)
        process.stdout.close()
    return "".join(output)


def parse_results(log: str, nonce: str) -> tuple[list[tuple[str, bool, str]], tuple[str, int, int]]:
    prefix = f"{SERVER_MARKER}{nonce}:"
    cases: list[tuple[str, bool, str]] = []
    finals: list[tuple[str, int, int]] = []
    for line in log.splitlines():
        if prefix not in line:
            continue
        payload = line.split(prefix, 1)[1].strip()
        fields = payload.split(":")
        if len(fields) >= 4 and fields[0] == "CASE" and fields[2] in {"PASS", "FAIL"}:
            cases.append((fields[1], fields[2] == "PASS", ":".join(fields[3:])))
        elif len(fields) == 4 and fields[0] == "FINAL":
            try:
                finals.append((fields[1], int(fields[2]), int(fields[3])))
            except ValueError:
                pass

    final_counts: dict[tuple[str, int, int], int] = {}
    for value in finals:
        final_counts[value] = final_counts.get(value, 0) + 1
    final_winners = [value for value, count in final_counts.items() if count >= 2]
    if len(final_winners) != 1:
        script_errors = [
            line.strip()
            for line in log.splitlines()
            if "SCRIPT ERROR" in line.upper() or "AN ERROR HAS OCCURED" in line.upper()
        ]
        detail = script_errors[-1] if script_errors else "server suite emitted no unique final marker"
        raise SubmissionFailure(detail)
    final = final_winners[0]
    grouped_cases: dict[str, dict[tuple[bool, str], int]] = {}
    for name, case_passed, message in cases:
        values = grouped_cases.setdefault(name, {})
        key = (case_passed, message)
        values[key] = values.get(key, 0) + 1
    winners: dict[str, tuple[bool, str]] = {}
    conflicting = []
    for name, values in grouped_cases.items():
        majority = [value for value, count in values.items() if count >= 2]
        if len(majority) != 1:
            conflicting.append(name)
        else:
            winners[name] = majority[0]
    conflicting.sort()
    if conflicting:
        raise SubmissionFailure("conflicting duplicate server markers: " + ", ".join(conflicting))
    cases = [
        (name, value[0], value[1])
        for name, value in winners.items()
    ]
    declared, passed, total = final
    unique_names = {name for name, _, _ in cases}
    actual_passed = sum(case_passed for _, case_passed, _ in cases)
    valid = (
        total == EXPECTED_CASES
        and len(cases) == EXPECTED_CASES
        and len(unique_names) == EXPECTED_CASES
        and actual_passed == passed
        and declared in {"passed", "failed"}
        and declared == ("passed" if passed == total else "failed")
    )
    if not valid:
        raise SubmissionFailure(
            "inconsistent server markers: "
            f"declared={declared} passed={passed} total={total} "
            f"cases={len(cases)} unique={len(unique_names)} actual_passed={actual_passed}"
        )
    return cases, final


def run_server_suite() -> None:
    binary, _, addons = runtime_paths()
    suite = TESTS / "suite.nut"
    if not suite.is_file():
        raise EnvironmentFailure("private suite is missing from the verifier mount")
    nonce = uuid.uuid4().hex
    addon: Path | None = None
    try:
        addon = stage_addon(addons, suite, nonce)
        command = [
            str(binary),
            "-game",
            "left4dead2",
            "-console",
            "-insecure",
            "-enable_addons",
            "-norestart",
            "+sv_lan",
            "1",
            "+hostport",
            str(available_port()),
            "+map",
            "c1m1_hotel",
            "coop",
        ]
        environment = {
            "HOME": "/home/steam" if os.name == "posix" else os.environ.get("USERPROFILE", ""),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
            "PATH": os.environ.get("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"),
            "SteamAppId": "550",
        }
        for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP"):
            if key in os.environ:
                environment[key] = os.environ[key]
        popen_options: dict[str, object] = {"start_new_session": os.name == "posix"}
        if os.name == "posix":
            import pwd

            steam = pwd.getpwnam("steam")
            popen_options.update(user=steam.pw_uid, group=steam.pw_gid, extra_groups=[])
        try:
            process = subprocess.Popen(
                command,
                cwd=RUNTIME,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                **popen_options,
            )
        except OSError as error:
            raise EnvironmentFailure(f"could not launch managed L4D2 server: {error}") from error
        log = collect_server(process, nonce, timeout=180)
        (LOGS / "server.log").write_text(log, encoding="utf-8")
        cases, (_, passed, total) = parse_results(log, nonce)
        for name, case_passed, message in cases:
            print(f"{'PASS' if case_passed else 'FAIL'} {name}: {message}")
        if passed != total:
            raise SubmissionFailure(f"managed L4D2 cases passed: {passed}/{total}")
        print(f"managed L4D2 cases passed: {passed}/{total}")
    finally:
        if addon is not None:
            if addon.is_dir():
                shutil.rmtree(addon, ignore_errors=True)
            else:
                addon.unlink(missing_ok=True)


def main() -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    try:
        validate_submission()
        run_server_suite()
    except EnvironmentFailure as error:
        print(f"INVALID_ENVIRONMENT: {error}")
        return 2
    except (SubmissionFailure, OSError) as error:
        print(f"SUBMISSION_FAILED: {error}")
        return 1
    print("VERIFICATION_PASSED: source/package checks and all private server cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
