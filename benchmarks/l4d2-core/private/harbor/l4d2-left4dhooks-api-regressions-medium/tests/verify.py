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
import sys
import tempfile
import threading
import time
import uuid
from contextlib import suppress
from pathlib import Path


SUBMISSION = Path(os.environ.get("GCB_SUBMISSION", "/app/left4dhooks"))
TESTS = Path(os.environ.get("GCB_TESTS", "/tests"))
LOGS = Path(os.environ.get("GCB_LOGS", "/logs/verifier"))
RUNTIME = Path(os.environ.get("L4D2_ROOT", "/opt/l4d2"))
SM_ROOT = Path(os.environ.get("SOURCEMOD_ROOT", RUNTIME / "left4dead2/addons/sourcemod"))
COMPILER = SM_ROOT / "scripting/spcomp64"
PLUGIN_DIR = SM_ROOT / "plugins"
GAMEDATA_DIR = SM_ROOT / "gamedata"
DATA_DIR = SM_ROOT / "data"
MARKER = "@@GCB_SM@@"

SUITES: dict[str, tuple[str, ...]] = {
    "ammo": (
        "runtime_ammo_library_loaded",
        "ammo_index_range_is_engine_valid",
        "ammo_names_are_nonempty",
        "ammo_name_roundtrips_to_index",
        "ammo_names_are_stable_and_unique",
        "ammo_getname_preserves_other_fields",
    ),
    "vomit": (
        "runtime_vomit_library_loaded",
        "vomit_pre_forward_once",
        "vomit_post_forward_once",
        "vomit_projectile_result_and_arguments",
        "vomit_changed_vectors_reach_creation_and_post",
        "vomit_handled_path_is_preserved",
    ),
    "molotov": (
        "molotov_forward_family_remains_functional",
        "vomit_creation_never_dispatches_molotov_family",
    ),
    "spawn": (
        "runtime_spawn_library_loaded",
        "spawn_timer_invalid_zero",
        "spawn_timer_invalid_above_max",
        "spawn_timer_returns_absolute_field",
        "spawn_timer_updates_and_relative_api_remains_distinct",
        "spawn_timer_read_preserves_adjacent_state",
    ),
    "weaponattr": (
        "runtime_weaponattr_library_loaded",
        "ordinary_float_weapon_attribute_roundtrips",
        "penetration_layers_store_integral_count",
        "penetration_layers_preserve_adjacent_power",
        "missing_float_weapon_attribute_returns_negative_one",
    ),
    "animhook": (
        "runtime_animhook_library_loaded",
        "two_client_animation_hooks_fire",
        "reenabled_animation_hook_not_duplicated",
        "peer_animation_hook_survives_other_client_cycle",
        "final_disable_removes_selected_client_callback",
    ),
    "pipebomb": (
        "runtime_pipebomb_library_loaded",
        "real_pipebomb_creation_forwards_once",
        "real_pipebomb_detonation_forwards_once",
        "breakable_prop_real_break_path_completes",
        "breakable_prop_never_dispatches_pipebomb_creation",
        "breakable_prop_never_dispatches_pipebomb_detonation",
    ),
    "campaignscores": (
        "runtime_campaign_scores_library_loaded",
        "campaign_scores_pre_forward_once",
        "campaign_scores_pre_receives_original_values",
        "campaign_scores_post_forward_once",
        "campaign_scores_changed_values_reach_post",
    ),
    "meleeinfo": (
        "runtime_melee_info_library_loaded",
        "melee_float_attribute_is_readable",
        "melee_int_attribute_is_readable",
        "melee_bool_attribute_is_stable",
        "melee_float_attribute_roundtrips_and_restores",
    ),
    "stagger": (
        "runtime_stagger_library_and_clients_ready",
        "initial_stagger_becomes_active",
        "same_frame_restagger_survives_cancel_window",
        "next_frame_restagger_survives_cancel_window",
        "completed_cancel_still_allows_later_stagger",
    ),
    "gascan": (
        "runtime_unpicked_gascan_fixture_ready",
        "unpicked_gascan_pre_forward_once",
        "unpicked_gascan_pre_forward_arguments",
        "unpicked_gascan_post_forward_once",
        "unpicked_gascan_post_forward_arguments",
        "weapon_gascan_path_dispatches_once",
        "weapon_gascan_path_preserves_arguments",
        "ordinary_physics_prop_never_dispatches_gascan_family",
    ),
    "entityaddress": (
        "runtime_entity_address_library_loaded",
        "entity_address_fixture_covers_engine_entities",
        "entity_addresses_roundtrip_for_all_live_entities",
        "non_edict_entity_addresses_roundtrip",
        "entity_address_lookup_is_stable",
        "null_entity_address_returns_negative_one",
    ),
    "lobbyreservation": (
        "runtime_lobby_reservation_library_loaded",
        "short_lobby_cookie_call_survives",
        "short_lobby_cookie_preserves_word_placement",
        "full_lobby_cookie_roundtrips",
        "lobby_cookie_can_be_restored",
    ),
}

FORBIDDEN_SUFFIXES = {".smx", ".dll", ".exe", ".so", ".zip", ".7z", ".vpk", ".tar", ".gz", ".rej", ".orig"}
REQUIRED = (
    "LICENSE",
    "sourcemod/scripting/left4dhooks.sp",
    "sourcemod/scripting/l4dd/l4dd_natives.sp",
    "sourcemod/scripting/l4dd/l4dd_forwards.sp",
    "sourcemod/scripting/include/left4dhooks.inc",
    "sourcemod/gamedata/left4dhooks.l4d2.txt",
)


class SubmissionFailure(RuntimeError):
    pass


class EnvironmentFailure(RuntimeError):
    pass


def validate_submission() -> None:
    if not SUBMISSION.is_dir():
        raise EnvironmentFailure(f"artifact missing: {SUBMISSION}")
    errors: list[str] = []
    total = 0
    source_lines = 0
    files = 0
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
        if size > 2_000_000:
            errors.append(f"{logical}: file exceeds 2 MB")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"{logical}: compiled/archive artifact is not allowed")
        if path.suffix.lower() in {".sp", ".inc"}:
            payload = path.read_bytes()
            if b"\x00" in payload:
                errors.append(f"{logical}: NUL byte is not allowed in SourcePawn source")
            if b"\r" in payload.replace(b"\r\n", b""):
                errors.append(f"{logical}: lone CR line ending is not allowed")
            if b"\r\n" in payload and b"\n" in payload.replace(b"\r\n", b""):
                errors.append(f"{logical}: mixed LF/CRLF line endings are not allowed")
            try:
                text = payload.decode("utf-8")
            except UnicodeDecodeError:
                errors.append(f"{logical}: source must be valid UTF-8")
                text = payload.decode("utf-8", errors="replace")
            source_lines += len(text.splitlines())
            if MARKER in text or "__GCB_NONCE__" in text:
                errors.append(f"{logical}: reserved verifier marker")
    if files > 200 or total > 20_000_000 or source_lines < 30_000:
        errors.append(f"unexpected source tree shape: files={files} bytes={total} source_lines={source_lines}")
    for relative in REQUIRED:
        if not (SUBMISSION / relative).is_file():
            errors.append(f"{relative}: required source is missing")
    license_text = (SUBMISSION / "LICENSE").read_text(encoding="utf-8", errors="replace") if (SUBMISSION / "LICENSE").is_file() else ""
    if "GNU GENERAL PUBLIC LICENSE" not in license_text:
        errors.append("LICENSE: upstream GPL attribution was removed")
    if errors:
        raise SubmissionFailure("source/package checks failed:\n- " + "\n- ".join(errors))
    print(f"source/package checks passed: files={files} bytes={total} source_lines={source_lines}")


def compile_plugin(source: Path, output: Path, includes: tuple[Path, ...]) -> None:
    command = [str(COMPILER)]
    for include in includes:
        command.extend(("-i", str(include)))
    command.extend(("-o", str(output), str(source)))
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode:
        raise SubmissionFailure(f"SourcePawn compile failed for {source.name}:\n{completed.stdout}{completed.stderr}")


def sourcepawn_code_only(text: str) -> str:
    """Blank comments and quoted literals while preserving every source offset."""
    chars = list(text)
    index = 0
    state = "code"
    quote = ""
    while index < len(chars):
        current = chars[index]
        following = chars[index + 1] if index + 1 < len(chars) else ""
        if state == "code":
            if current == "/" and following == "/":
                chars[index] = chars[index + 1] = " "
                index += 2
                state = "line"
                continue
            if current == "/" and following == "*":
                chars[index] = chars[index + 1] = " "
                index += 2
                state = "block"
                continue
            if current in {'"', "'"}:
                quote = current
                chars[index] = " "
                index += 1
                state = "quoted"
                continue
        elif state == "line":
            if current in "\r\n":
                state = "code"
            else:
                chars[index] = " "
        elif state == "block":
            if current == "*" and following == "/":
                chars[index] = chars[index + 1] = " "
                index += 2
                state = "code"
                continue
            if current not in "\r\n":
                chars[index] = " "
        else:
            if current == "\\" and following:
                chars[index] = " "
                if following not in "\r\n":
                    chars[index + 1] = " "
                index += 2
                continue
            chars[index] = " " if current not in "\r\n" else current
            if current == quote:
                state = "code"
        index += 1
    return "".join(chars)


def evaluate_public_include(temp: Path) -> list[tuple[str, bool, str]]:
    source = temp / "public_spawn_abi_consumer.sp"
    source.write_text(
        """#pragma semicolon 1
#pragma newdecls required
#include <sourcemod>
#include <left4dhooks>
public Plugin myinfo = { name = "GCB ABI consumer", author = "GameCodeBench", description = "", version = "1" };
float ReadAbsoluteSpawnTime(int client)
{
    float value = L4D2Direct_GetSpawnTimer(client);
    return value + 0.0;
}
""",
        encoding="utf-8",
    )
    output = temp / "public_spawn_abi_consumer.smx"
    command = [
        str(COMPILER),
        "-i", str(SM_ROOT / "scripting/include"),
        "-i", str(SUBMISSION / "sourcemod/scripting/include"),
        "-o", str(output),
        str(source),
    ]
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    include_path = SUBMISSION / "sourcemod/scripting/include/left4dhooks.inc"
    include_text = include_path.read_text(encoding="utf-8", errors="replace")
    declaration = re.search(
        r"\bnative\s+float\s+L4D2Direct_GetSpawnTimer\s*\(\s*int\s+[A-Za-z_]\w*\s*\)\s*;",
        sourcepawn_code_only(include_text),
    )
    abi_ok = completed.returncode == 0 and declaration is not None
    abi_detail = "submitted public include declares float and compiles a float ABI consumer" if abi_ok else "submitted public include does not expose the required float declaration"
    # Prose accuracy is an author/reviewer check, not a keyword classifier.
    # Real-server cases below verify absolute-time and invalid-index behavior.
    return [("spawn_timer_public_include_abi_matches_runtime", abi_ok, abi_detail)]


def prepare_runtime(temp: Path) -> Path:
    binary = RUNTIME / "srcds_run"
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise EnvironmentFailure("L4D2 dedicated-server binary is unavailable")
    if not COMPILER.is_file() or not os.access(COMPILER, os.X_OK):
        raise EnvironmentFailure("pinned SourceMod compiler is unavailable")
    foreign = [path for path in PLUGIN_DIR.rglob("*.smx")]
    if foreign:
        raise EnvironmentFailure("verifier SourceMod plugin directory is not clean")

    core = temp / "00_left4dhooks.smx"
    compile_plugin(
        SUBMISSION / "sourcemod/scripting/left4dhooks.sp",
        core,
        (SM_ROOT / "scripting/include", SUBMISSION / "sourcemod/scripting/include"),
    )
    shutil.copy2(core, PLUGIN_DIR / core.name)
    for source_root, destination_root in (
        (SUBMISSION / "sourcemod/gamedata", GAMEDATA_DIR),
        (SUBMISSION / "sourcemod/data", DATA_DIR),
    ):
        for path in source_root.rglob("*"):
            if path.is_file():
                destination = destination_root / path.relative_to(source_root)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
    steam = pwd.getpwnam("steam")
    for path in (PLUGIN_DIR / core.name, *GAMEDATA_DIR.rglob("*"), *DATA_DIR.rglob("*")):
        if path.exists():
            os.chown(path, steam.pw_uid, steam.pw_gid)
    return binary


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


def collect(process: subprocess.Popen[str], final_prefix: str, timeout: int = 35) -> str:
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
    case_positions: list[int] = []
    duplicate: set[str] = set()
    finals: list[tuple[int, int, int]] = []
    lines = log.splitlines()
    for position, line in enumerate(lines):
        if prefix not in line:
            continue
        fields = line.split(prefix, 1)[1].strip().split(":", 3)
        if len(fields) == 4 and fields[0] == "CASE" and fields[2] in {"PASS", "FAIL"}:
            if fields[1] in observed:
                duplicate.add(fields[1])
            observed[fields[1]] = (fields[2] == "PASS", fields[3])
            case_positions.append(position)
        elif len(fields) == 3 and fields[0] == "FINAL":
            with suppress(ValueError):
                finals.append((int(fields[1]), int(fields[2]), position))

    expected = SUITES[suite]
    final_position = finals[0][2] if len(finals) == 1 else len(lines)
    fatal_pattern = re.compile(
        r"(?:\[SM\]\s+Exception|Plugin encountered error|Native .* reported|"
        r"Invalid memory access|Segmentation fault|stack trace|array index out of bounds|"
        r"Could not load plugin|failed to load plugin)",
        re.I,
    )
    fatal = [line.strip() for line in lines[: final_position + 1] if fatal_pattern.search(line)]
    valid = (
        not duplicate
        and set(observed) == set(expected)
        and len(finals) == 1
        and finals[0][1] == len(expected)
        and finals[0][0] == sum(value[0] for value in observed.values())
        and all(position < final_position for position in case_positions)
        and not fatal
    )
    if not valid:
        detail = fatal[-1] if fatal else "suite did not complete its exact case contract"
        return [(name, False, detail) for name in expected]
    return [(name, *observed[name]) for name in expected]


def run_suite(binary: Path, temp: Path, suite: str) -> tuple[list[tuple[str, bool, str]], str]:
    nonce = uuid.uuid4().hex
    source_text = (TESTS / f"suite_{suite}.sp").read_text(encoding="utf-8")
    if source_text.count("__GCB_NONCE__") != 1:
        raise EnvironmentFailure(f"suite_{suite}.sp has an invalid nonce placeholder")
    source = temp / f"suite_{suite}.sp"
    source.write_text(source_text.replace("__GCB_NONCE__", nonce), encoding="utf-8")
    plugin = PLUGIN_DIR / f"99_gcb_{suite}.smx"
    compile_plugin(source, plugin, (SM_ROOT / "scripting/include", TESTS / "include"))
    steam = pwd.getpwnam("steam")
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
    log = collect(process, f"{MARKER}{nonce}:FINAL:")
    plugin.unlink(missing_ok=True)
    return parse_suite(log, suite, nonce), log


def main() -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    try:
        validate_submission()
        with tempfile.TemporaryDirectory(prefix="gcb-left4dhooks-") as directory:
            temp = Path(directory)
            binary = prepare_runtime(temp)
            all_results: list[tuple[str, bool, str]] = evaluate_public_include(temp)
            for suite in SUITES:
                results, log = run_suite(binary, temp, suite)
                (LOGS / f"server-{suite}.log").write_text(log, encoding="utf-8")
                all_results.extend(results)
        if len(all_results) != 71 or len({name for name, _, _ in all_results}) != 71:
            raise EnvironmentFailure("verifier assembled an invalid global case set")
        for name, passed, detail in all_results:
            print(f"{'PASS' if passed else 'FAIL'} {name}: {detail}")
        passed_count = sum(passed for _, passed, _ in all_results)
        print(f"public ABI plus managed SourceMod cases passed: {passed_count}/71")
        if passed_count != 71:
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
