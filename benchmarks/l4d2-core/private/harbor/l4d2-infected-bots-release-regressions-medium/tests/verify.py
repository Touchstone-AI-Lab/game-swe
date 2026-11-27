#!/usr/bin/env python3
from __future__ import annotations

import os
import hashlib
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


SUBMISSION = Path(os.environ.get("GCB_SUBMISSION", "/app/l4d1_2_plugins"))
TESTS = Path(os.environ.get("GCB_TESTS", "/tests"))
LOGS = Path(os.environ.get("GCB_LOGS", "/logs/verifier"))
RUNTIME = Path(os.environ.get("L4D2_ROOT", "/opt/l4d2"))
SM_ROOT = Path(os.environ.get("SOURCEMOD_ROOT", RUNTIME / "left4dead2/addons/sourcemod"))
COMPILER = SM_ROOT / "scripting/spcomp64"
PLUGIN_DIR = SM_ROOT / "plugins"
GAMEDATA_DIR = SM_ROOT / "gamedata"
DATA_DIR = SM_ROOT / "data"
TRANSLATIONS_DIR = SM_ROOT / "translations"
MARKER = "@@GCB_SM@@"

SUITES: dict[str, tuple[str, ...]] = {
    "capacity": (
        "capacity_library_loaded",
        "capacity_exact_runtime_slots",
        "capacity_unclamped_request_is_preserved",
    ),
    "config": (
        "config_library_and_single_survivor_guard",
        "config_settings_count_profile_overlays_all_types",
        "config_settings_count_omitted_keys_inherit_default",
        "config_admin_overrides_are_temporary",
        "config_reload_replaces_overrides_and_applies_map_profiles",
    ),
    "initial_timer": (
        "initial_timer_libraries_loaded",
        "initial_timer_victim_created",
        "initial_timer_not_overwritten_by_normal_delay",
        "initial_timer_eventually_replenishes",
        "initial_timer_normal_delay_resumes_after_window",
    ),
    "finale": (
        "finale_library_loaded",
        "finale_win_event_available",
        "finale_win_cancels_pending_replenishment",
    ),
}

SUITE_MODES = {
    "capacity": "coop",
    "config": "coop",
    "initial_timer": "versus",
    "finale": "coop",
}

FORBIDDEN_SUFFIXES = {
    ".smx", ".dll", ".exe", ".so", ".dylib", ".a", ".lib", ".o", ".obj", ".pdb",
    ".zip", ".7z", ".rar", ".vpk", ".tar", ".gz", ".tgz", ".bz2", ".xz",
    ".bsp", ".nav", ".ain", ".mdl", ".vtx", ".vvd", ".phy", ".ani",
    ".wav", ".mp3", ".ogg", ".vtf", ".vmt", ".pcf",
}
ALLOWED_SUFFIXES = {".cfg", ".inc", ".md", ".py", ".sp", ".txt"}
ALLOWED_UNSUFFIXED = {"LICENSE", "third_party/LEFT4DHOOKS-LICENSE", "third_party/MULTICOLORS-LICENSE"}
FORBIDDEN_MAGIC = (b"\x7fELF", b"MZ", b"FFPS", b"PK\x03\x04", b"7z\xbc\xaf\x27\x1c", b"Rar!", b"\x1f\x8b", b"\xfd7zXZ")
IMMUTABLE_HASHES = {
    "LICENSE": "3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986",
    "UPSTREAM.md": "b0bdafab025ba906e9f3a756850c7631f2cde1b81cd2e33379cd953beb591825",
    "third_party/LEFT4DHOOKS-LICENSE": "3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986",
    "third_party/MULTICOLORS-LICENSE": "589ed823e9a84c56feb95ac58e7cf384626b9cbf4fda2a907bc36e103de1bad2",
    "tools/smoke.py": "dea6d81fe58af59bd0c55f8bf5bb1d474814ea92fd0b74d89577265ecf83c5ac",
}
CREDENTIAL_PATTERNS = (
    re.compile(r"(?i)\bOPENAI_API_KEY\s*="),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
)
NETWORK_SOURCE_PATTERNS = (
    re.compile(r'(?im)^\s*#\s*(?:try)?include\s*[<"]\s*(?:socket|steamworks|ripext|curl|system2)(?:\.inc)?\s*[>"]'),
    re.compile(r"(?i)\b(?:SocketCreate|SocketConnect|SteamWorks_[A-Za-z0-9_]+|HTTPClient|HTTPRequest|Curl_[A-Za-z0-9_]+|System2_[A-Za-z0-9_]+)\b"),
)
REQUIRED = (
    "LICENSE",
    "UPSTREAM.md",
    "third_party/LEFT4DHOOKS-LICENSE",
    "third_party/MULTICOLORS-LICENSE",
    "l4dinfectedbots/scripting/l4dinfectedbots.sp",
    "l4dinfectedbots/scripting/include/l4dinfectedbots.inc",
    "l4dinfectedbots/gamedata/l4dinfectedbots.txt",
    "l4dinfectedbots/data/l4dinfectedbots/coop.cfg",
    "spawn_infected_nolimit/scripting/spawn_infected_nolimit.sp",
    "spawn_infected_nolimit/scripting/include/spawn_infected_nolimit.inc",
    "spawn_infected_nolimit/gamedata/spawn_infected_nolimit.txt",
    "third_party/include/multicolors.inc",
    "third_party/include/left4dhooks_bundle/left4dhooks.inc",
)


class SubmissionFailure(RuntimeError):
    pass


class EnvironmentFailure(RuntimeError):
    pass


def canonical_sha256(path: Path) -> str:
    payload = path.read_bytes()
    try:
        payload = payload.decode("utf-8").replace("\r\n", "\n").encode("utf-8")
    except UnicodeDecodeError:
        pass
    return hashlib.sha256(payload).hexdigest()


def executable_source(source: str) -> str:
    return re.sub(
        r'''(?s)/\*.*?\*/|//[^\r\n]*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*' ''',
        " ",
        source,
    )


def validate_submission() -> tuple[str, bool, str]:
    if not SUBMISSION.is_dir():
        raise EnvironmentFailure(f"artifact missing: {SUBMISSION}")
    errors: list[str] = []
    files = 0
    total = 0
    source_lines = 0
    target_source_lines = 0
    spawn_source_lines = 0
    for path in SUBMISSION.rglob("*"):
        logical = path.relative_to(SUBMISSION).as_posix()
        if path.is_symlink():
            errors.append(f"{logical}: symbolic links are not allowed")
            continue
        if path.name == ".git":
            errors.append(f"{logical}: Git metadata is not allowed")
        if path.is_dir():
            continue
        if not path.is_file():
            errors.append(f"{logical}: non-regular filesystem entries are not allowed")
            continue
        files += 1
        size = path.stat().st_size
        total += size
        if size > 2_000_000:
            errors.append(f"{logical}: file exceeds 2 MB")
        suffix = path.suffix.lower()
        if (suffix not in ALLOWED_SUFFIXES and logical not in ALLOWED_UNSUFFIXED) or suffix in FORBIDDEN_SUFFIXES:
            errors.append(f"{logical}: non-source/package artifact is not allowed")
        payload = path.read_bytes()
        header = payload[:8]
        if any(header.startswith(magic) for magic in FORBIDDEN_MAGIC):
            errors.append(f"{logical}: binary/archive file content is not allowed")
        try:
            decoded = payload.decode("utf-8")
        except UnicodeDecodeError:
            errors.append(f"{logical}: public-source files must be UTF-8 text")
            decoded = ""
        if "\x00" in decoded:
            errors.append(f"{logical}: NUL bytes are not allowed in public-source text")
        if suffix == ".py" and logical != "tools/smoke.py":
            errors.append(f"{logical}: additional executable Python helpers are not allowed")
        if logical != "tools/smoke.py" and any(pattern.search(decoded) for pattern in CREDENTIAL_PATTERNS):
            errors.append(f"{logical}: credential-like material is not allowed")
        if path.suffix.lower() in {".sp", ".inc"}:
            lines = len(decoded.splitlines())
            source_lines += lines
            if logical.startswith("l4dinfectedbots/"):
                target_source_lines += lines
            elif logical.startswith("spawn_infected_nolimit/"):
                spawn_source_lines += lines
            if MARKER in decoded or "__GCB_NONCE__" in decoded:
                errors.append(f"{logical}: reserved verifier marker")
            if any(pattern.search(executable_source(decoded)) for pattern in NETWORK_SOURCE_PATTERNS):
                errors.append(f"{logical}: executable network-client code is not allowed")
    for relative in REQUIRED:
        if not (SUBMISSION / relative).is_file():
            errors.append(f"{relative}: required source is missing")
    manifest_path = TESTS / "source-manifest.txt"
    if not manifest_path.is_file():
        raise EnvironmentFailure("verifier source manifest is missing")
    for relative in manifest_path.read_text(encoding="utf-8").splitlines():
        if relative and not (SUBMISSION / relative).is_file():
            errors.append(f"{relative}: frozen public-source snapshot file is missing")
    for relative, expected in IMMUTABLE_HASHES.items():
        immutable = SUBMISSION / relative
        if immutable.is_file() and canonical_sha256(immutable) != expected:
            errors.append(f"{relative}: frozen license/provenance text was modified")
    if files > 180 or total > 20_000_000 or source_lines < 12_000:
        errors.append(f"unexpected source tree shape: files={files} bytes={total} source_lines={source_lines}")
    if target_source_lines < 5_200 or spawn_source_lines < 700:
        errors.append(
            "project-owned source tree was replaced or truncated: "
            f"target_lines={target_source_lines} spawn_lines={spawn_source_lines}"
        )
    if errors:
        raise SubmissionFailure("source/package checks failed:\n- " + "\n- ".join(errors))
    return (
        "package_complete_public_source",
        True,
        f"files={files} bytes={total} source_lines={source_lines} "
        f"target_lines={target_source_lines} spawn_lines={spawn_source_lines}",
    )


def compile_plugin(source: Path, output: Path, includes: tuple[Path, ...]) -> None:
    command = [str(COMPILER)]
    for include in includes:
        command.extend(("-i", str(include)))
    command.extend(("-o", str(output), str(source)))
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode:
        raise SubmissionFailure(f"SourcePawn compile failed for {source.name}:\n{completed.stdout}{completed.stderr}")


def copy_tree_files(source: Path, destination: Path) -> None:
    for path in source.rglob("*"):
        if path.is_file():
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def prepare_runtime(temp: Path) -> tuple[Path, tuple[str, bool, str]]:
    binary = RUNTIME / "srcds_run"
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise EnvironmentFailure("L4D2 dedicated-server binary is unavailable")
    if not COMPILER.is_file() or not os.access(COMPILER, os.X_OK):
        raise EnvironmentFailure("pinned SourceMod compiler is unavailable")
    foreign = list(PLUGIN_DIR.rglob("*.smx"))
    if foreign:
        raise EnvironmentFailure("verifier SourceMod plugin directory is not clean")

    base_include = SM_ROOT / "scripting/include"
    left_root = TESTS / "deps/left4dhooks"
    left_include = left_root / "sourcemod/scripting/include"
    target_left_include = SUBMISSION / "third_party/include/left4dhooks_bundle"
    multicolors_include = SUBMISSION / "third_party/include"
    spawn_include = SUBMISSION / "spawn_infected_nolimit/scripting/include"
    target_include = SUBMISSION / "l4dinfectedbots/scripting/include"

    adminmenu_binary = temp / "00_adminmenu.smx"
    left_binary = temp / "01_left4dhooks.smx"
    spawn_binary = temp / "02_spawn_infected_nolimit.smx"
    target_binary = temp / "03_l4dinfectedbots.smx"
    consumer_binary = temp / "public_api_consumer.smx"
    compile_plugin(
        SM_ROOT / "scripting/adminmenu.sp",
        adminmenu_binary,
        (base_include,),
    )
    compile_plugin(
        left_root / "sourcemod/scripting/left4dhooks.sp",
        left_binary,
        (base_include, left_include),
    )
    compile_plugin(
        SUBMISSION / "spawn_infected_nolimit/scripting/spawn_infected_nolimit.sp",
        spawn_binary,
        (base_include, target_left_include),
    )
    compile_plugin(
        SUBMISSION / "l4dinfectedbots/scripting/l4dinfectedbots.sp",
        target_binary,
        (base_include, target_left_include, multicolors_include, spawn_include, target_include),
    )
    compile_plugin(
        TESTS / "public_api_consumer.sp",
        consumer_binary,
        (base_include, target_include),
    )
    shutil.copy2(adminmenu_binary, PLUGIN_DIR / adminmenu_binary.name)
    shutil.copy2(left_binary, PLUGIN_DIR / left_binary.name)
    disabled = PLUGIN_DIR / "disabled"
    disabled.mkdir(parents=True, exist_ok=True)
    shutil.copy2(spawn_binary, disabled / spawn_binary.name)
    shutil.copy2(target_binary, disabled / target_binary.name)

    # Install only the candidate files named by the public project contract.
    # Verifier-owned core/Left4DHooks files are copied last so an added
    # candidate path cannot shadow the trusted runtime dependency.
    shutil.copy2(
        SUBMISSION / "spawn_infected_nolimit/gamedata/spawn_infected_nolimit.txt",
        GAMEDATA_DIR / "spawn_infected_nolimit.txt",
    )
    shutil.copy2(
        SUBMISSION / "l4dinfectedbots/gamedata/l4dinfectedbots.txt",
        GAMEDATA_DIR / "l4dinfectedbots.txt",
    )
    copy_tree_files(
        SUBMISSION / "l4dinfectedbots/data/l4dinfectedbots",
        DATA_DIR / "l4dinfectedbots",
    )
    shutil.copy2(
        SUBMISSION / "l4dinfectedbots/translations/l4dinfectedbots.phrases.txt",
        TRANSLATIONS_DIR / "l4dinfectedbots.phrases.txt",
    )
    copy_tree_files(left_root / "sourcemod/gamedata", GAMEDATA_DIR)
    copy_tree_files(left_root / "sourcemod/data", DATA_DIR)
    fixture_destination = DATA_DIR / "l4dinfectedbots"
    fixture_destination.mkdir(parents=True, exist_ok=True)
    for fixture in (TESTS / "fixtures").glob("*.cfg"):
        shutil.copy2(fixture, fixture_destination / fixture.name)
    server_cfg = RUNTIME / "left4dead2/cfg/server.cfg"
    shutil.copy2(TESTS / "runtime/server.cfg", server_cfg)

    steam = pwd.getpwnam("steam")
    installed = [
        *(PLUGIN_DIR.glob("*.smx")),
        *GAMEDATA_DIR.rglob("*"),
        *DATA_DIR.rglob("*"),
        *TRANSLATIONS_DIR.rglob("*"),
        server_cfg,
    ]
    for path in installed:
        if path.is_file():
            os.chown(path, steam.pw_uid, steam.pw_gid)
    return binary, (
        "submitted_plugins_compile",
        True,
        "target, public spawn dependency, and external public-API consumer compile with pinned SourceMod",
    )


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
        process.wait(timeout=5)


def collect(process: subprocess.Popen[str], final_prefix: str, timeout: int = 38) -> str:
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
            value = (fields[2] == "PASS", fields[3])
            if fields[1] in observed:
                duplicate.add(fields[1])
            observed[fields[1]] = value
        elif len(fields) == 3 and fields[0] == "FINAL":
            with suppress(ValueError):
                finals.append((int(fields[1]), int(fields[2])))

    expected = SUITES[suite]
    fatal_runtime = [
        line.strip()
        for line in log.splitlines()
        if re.search(
            r"\[SM\]\s+Exception reported|Exception reported:|Native .* is not bound|"
            r"Plugin .* failed to load|PreMinidumpCallback|Segmentation fault|\bsegfault\b",
            line,
            re.I,
        )
    ]
    valid = (
        not fatal_runtime
        and not duplicate
        and set(observed) == set(expected)
        and len(finals) == 1
        and finals[0][1] == len(expected)
        and finals[0][0] == sum(value[0] for value in observed.values())
    )
    if not valid:
        lines = [line.strip() for line in log.splitlines() if line.strip()]
        errors = [
            line for line in lines
            if ("[SM]" in line or any(word in line.lower() for word in ("exception", "unable to load", "failed to load", "crash", "segmentation")))
            and line.lower() != "with error:"
        ]
        detail = fatal_runtime[-1] if fatal_runtime else (
            errors[-1] if errors else (lines[-1] if lines else "suite produced no server output")
        )
        return [(name, False, detail) for name in expected]
    return [(name, *observed[name]) for name in expected]


def run_suite(binary: Path, temp: Path, suite: str) -> tuple[list[tuple[str, bool, str]], str]:
    nonce = uuid.uuid4().hex
    source_text = (TESTS / f"suite_{suite}.sp").read_text(encoding="utf-8")
    harness_text = (TESTS / "include/gcb_harness.inc").read_text(encoding="utf-8")
    if harness_text.count("__GCB_NONCE__") != 1:
        raise EnvironmentFailure("test harness has an invalid nonce placeholder")
    suite_include = temp / f"include-{suite}"
    shutil.copytree(TESTS / "include", suite_include)
    (suite_include / "gcb_harness.inc").write_text(harness_text.replace("__GCB_NONCE__", nonce), encoding="utf-8")
    source = temp / f"suite_{suite}.sp"
    source.write_text(source_text, encoding="utf-8")
    plugin = PLUGIN_DIR / f"99_gcb_{suite}.smx"
    compile_plugin(source, plugin, (SM_ROOT / "scripting/include", suite_include))
    steam = pwd.getpwnam("steam")
    os.chown(plugin, steam.pw_uid, steam.pw_gid)

    port = available_port()
    command = [
        str(binary), "-game", "left4dead2", "-console", "-insecure", "-norestart",
        "+sv_lan", "1", "+hostport", str(port),
        "+mp_gamemode", SUITE_MODES[suite],
        "+map", "c1m1_hotel",
    ]
    environment = {
        "HOME": "/home/steam",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "SteamAppId": "550",
    }
    for old_log in (SM_ROOT / "logs").glob("*.log"):
        old_log.unlink(missing_ok=True)
    process = subprocess.Popen(
        command,
        cwd=RUNTIME,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        start_new_session=True,
        user=steam.pw_uid,
        group=steam.pw_gid,
        extra_groups=[],
    )
    log = collect(process, f"{MARKER}{nonce}:FINAL:")
    for source_log in sorted((SM_ROOT / "logs").glob("*.log")):
        with suppress(OSError):
            log += "\n--- sourcemod log ---\n" + source_log.read_text(encoding="utf-8", errors="replace")
    plugin.unlink(missing_ok=True)
    return parse_suite(log, suite, nonce), log


def main() -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    try:
        package_result = validate_submission()
        only_suite = os.environ.get("GCB_ONLY_SUITE", "")
        if only_suite and only_suite not in SUITES:
            raise EnvironmentFailure(f"unknown focused suite: {only_suite}")
        suite_names = (only_suite,) if only_suite else tuple(SUITES)
        with tempfile.TemporaryDirectory(prefix="gcb-infectedbots-") as directory:
            temp = Path(directory)
            binary, compile_result = prepare_runtime(temp)
            all_results = [package_result, compile_result]
            for suite in suite_names:
                results, log = run_suite(binary, temp, suite)
                (LOGS / f"server-{suite}.log").write_text(log, encoding="utf-8")
                all_results.extend(results)
        expected_count = 2 + sum(len(SUITES[name]) for name in suite_names)
        if len(all_results) != expected_count or len({name for name, _, _ in all_results}) != expected_count:
            raise EnvironmentFailure("verifier assembled an invalid global case set")
        for name, passed, detail in all_results:
            print(f"{'PASS' if passed else 'FAIL'} {name}: {detail}")
        passed_count = sum(passed for _, passed, _ in all_results)
        print(f"source plus managed SourceMod cases passed: {passed_count}/{expected_count}")
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
