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


SUBMISSION = Path(os.environ.get("GCB_SUBMISSION", "/app/mutant-tanks"))
TESTS = Path(os.environ.get("GCB_TESTS", "/tests"))
LOGS = Path(os.environ.get("GCB_LOGS", "/logs/verifier"))
RUNTIME = Path(os.environ.get("L4D2_ROOT", "/opt/l4d2"))
SM_ROOT = Path(os.environ.get("SOURCEMOD_ROOT", RUNTIME / "left4dead2/addons/sourcemod"))
COMPILER = SM_ROOT / "scripting/spcomp64"
PLUGIN_DIR = SM_ROOT / "plugins"
SCRIPTING = SUBMISSION / "addons/sourcemod/scripting"
MARKER = "@@GCB_SM@@"
CASES = (
    "runtime_core_loaded",
    "runtime_primary_ability_module_loaded",
    "runtime_warp_module_loaded",
    "config_reload_dispatches_callbacks",
    "config_forward_preserves_basic_arguments",
    "config_forward_preserves_special_context",
    "health_smoker_mutation_completes",
    "health_type_explicit_si_override_remains",
    "health_plugin_si_fallback_beats_generic_defaults",
    "warp_unpinned_survivor_still_moves",
    "warp_smoker_pin_is_preserved",
    "warp_hunter_pin_is_preserved",
    "warp_jockey_pin_is_preserved",
    "warp_charger_pin_is_preserved",
    "boss_four_stage_evolution_completes",
    "boss_final_stage_timer_remains_healthy",
    "reward_ab_two_real_tank_rewards_observed",
    "reward_ab_stacked_damage_before_replacement",
    "reward_ab_stacked_ammo_before_replacement",
    "reward_ab_replacement_target_keeps_damage",
    "reward_ab_replacement_old_owner_loses_damage",
    "reward_ab_replacement_target_keeps_ammo",
    "reward_ab_replacement_old_owner_loses_ammo",
    "reward_ab_public_expiry_forward_observed",
    "reward_ab_expiry_restores_baseline_damage",
    "reward_ab_expiry_stops_ammo_regeneration",
    "reward_ba_two_real_tank_rewards_observed",
    "reward_ba_stacked_damage_before_replacement",
    "reward_ba_stacked_ammo_before_replacement",
    "reward_ba_replacement_target_keeps_damage",
    "reward_ba_replacement_old_owner_loses_damage",
    "reward_ba_replacement_target_keeps_ammo",
    "reward_ba_replacement_old_owner_loses_ammo",
    "reward_ba_public_expiry_forward_observed",
    "reward_ba_expiry_restores_baseline_damage",
    "reward_ba_expiry_stops_ammo_regeneration",
    "hypno_view1_disabled_spawns_one_shield",
    "hypno_tank_removal_cleans_shield",
    "hypno_respawn_uses_new_shield_entref",
    "hypno_view0_never_spawns_shield",
    "hypno_view0_gameplay_hit_still_applies",
    "hypno_view1_enabled_activation_does_not_duplicate",
    "hypno_round_and_plugin_cleanup_leave_no_orphans",
    "panic_explicit_uncommon_type_guard_works",
    "panic_empty_type_spawns_one_uncommon",
    "panic_fallback_uncommon_uses_allowed_model",
    "rainbow_reward_animates_before_takeover",
    "rainbow_bot_to_player_migrates_animation",
    "rainbow_old_bot_stops_after_takeover",
    "rainbow_player_to_bot_migrates_animation",
    "rainbow_old_player_stops_after_idle",
    "acid_melee_cooldown_blocks_window_repeat",
    "ammo_melee_cooldown_blocks_window_repeat",
    "acid_melee_cooldown_recovers_after_expiry",
    "ammo_melee_cooldown_recovers_after_expiry",
    "acid_zero_cooldown_allows_cross_second_repeat",
    "ammo_zero_cooldown_allows_cross_second_repeat",
)
GROUP_CASES = {
    "config": CASES[:6],
    "health": CASES[6:9],
    "warp": CASES[9:14],
    "boss": CASES[14:16],
    "reward_stacking": CASES[16:36],
    "hypno": CASES[36:43],
    "panic_fallback": CASES[43:46],
    "rainbow_transfer": CASES[46:51],
    "cooldown": CASES[51:57],
}
BOOT_CASES = {
    **{group: cases for group, cases in GROUP_CASES.items() if group != "reward_stacking"},
    "reward_ab": CASES[16:26],
    "reward_ba": CASES[26:36],
}
GROUP_BOOTS = {
    **{group: (group,) for group in GROUP_CASES if group != "reward_stacking"},
    "reward_stacking": ("reward_ab", "reward_ba"),
}
FORBIDDEN = {
    ".smx", ".dll", ".exe", ".so", ".dylib", ".a", ".lib", ".o", ".obj", ".pdb",
    ".zip", ".7z", ".rar", ".vpk", ".tar", ".gz", ".tgz", ".bz2", ".xz",
    ".bsp", ".nav", ".ain", ".mdl", ".vtx", ".vvd", ".phy", ".ani",
    ".wav", ".mp3", ".ogg", ".vtf", ".vmt", ".pcf",
}
ALLOWED_SUFFIXES = {".cfg", ".inc", ".md", ".py", ".sp", ".txt"}
ALLOWED_UNSUFFIXED = {"LICENSE"}
FORBIDDEN_MAGIC = (b"\x7fELF", b"MZ", b"FFPS", b"PK\x03\x04", b"7z\xbc\xaf\x27\x1c", b"Rar!", b"\x1f\x8b", b"\xfd7zXZ")
IMMUTABLE_HASHES = {
    "LICENSE": "8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903",
    "UPSTREAM.md": "851046a045d2c95f46e8d9a5a2f50dfc965ee1fc548dc7742e80dfc882c04fb7",
    "tools/smoke.py": "c928efa6aee9f52c12afecbe58723275d1e48f859b74dd3f8578c04a35937ac3",
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
SPDX_GPL_PATTERN = re.compile(
    r"(?im)^\s*(?://|/\*+|\*)\s*SPDX-License-Identifier:\s*GPL-3\.0(?:-or-later|\+)?\s*(?:\*/)?\s*$"
)
REQUIRED = (
    "LICENSE",
    "UPSTREAM.md",
    "tools/smoke.py",
    "addons/sourcemod/scripting/include/mutant_tanks.inc",
    "addons/sourcemod/scripting/mutant_tanks/mutant_tanks.sp",
    "addons/sourcemod/scripting/mutant_tanks/mt_abilities.sp",
    "addons/sourcemod/scripting/mutant_tanks/mt_abilities2.sp",
    "addons/sourcemod/scripting/mutant_tanks/abilities/mt_acid.sp",
    "addons/sourcemod/scripting/mutant_tanks/abilities/mt_ammo.sp",
    "addons/sourcemod/scripting/mutant_tanks/abilities/mt_hypno.sp",
    "addons/sourcemod/scripting/mutant_tanks/abilities2/mt_panic.sp",
    "addons/sourcemod/scripting/mutant_tanks/abilities2/mt_warp.sp",
    "addons/sourcemod/gamedata/mutant_tanks.txt",
    "addons/sourcemod/data/mutant_tanks/mutant_tanks.cfg",
    "cfg/sourcemod/mutant_tanks.cfg",
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


def has_gpl_attribution(source: str) -> bool:
    return "GNU General Public License" in source or SPDX_GPL_PATTERN.search(source) is not None


def has_consistent_line_endings(payload: bytes) -> bool:
    without_crlf = payload.replace(b"\r\n", b"")
    has_crlf = len(without_crlf) != len(payload)
    has_bare_lf = b"\n" in without_crlf
    has_lone_cr = b"\r" in without_crlf
    return not has_lone_cr and not (has_crlf and has_bare_lf)


def validate_submission() -> None:
    if not SUBMISSION.is_dir():
        raise EnvironmentFailure(f"artifact missing: {SUBMISSION}")
    errors: list[str] = []
    files = bytes_total = sourcepawn = includes = 0
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
        bytes_total += path.stat().st_size
        if path.stat().st_size > 3_000_000:
            errors.append(f"{logical}: file exceeds 3 MB")
        suffix = path.suffix.lower()
        if (suffix not in ALLOWED_SUFFIXES and logical not in ALLOWED_UNSUFFIXED) or suffix in FORBIDDEN:
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
        sourcepawn += path.suffix.lower() == ".sp"
        includes += path.suffix.lower() == ".inc"
        if path.suffix.lower() in {".sp", ".inc"}:
            if not has_consistent_line_endings(payload):
                errors.append(f"{logical}: mixed or invalid line endings are not allowed")
            if MARKER in decoded or "__GCB_NONCE__" in decoded:
                errors.append(f"{logical}: reserved verifier marker")
            if not has_gpl_attribution(decoded):
                errors.append(f"{logical}: GPL attribution is missing")
            if any(pattern.search(executable_source(decoded)) for pattern in NETWORK_SOURCE_PATTERNS):
                errors.append(f"{logical}: executable network-client code is not allowed")
    if files < 75 or files > 250 or bytes_total < 9_000_000 or bytes_total > 20_000_000 or sourcepawn < 60 or includes < 2:
        errors.append(
            f"unexpected source tree shape: files={files} bytes={bytes_total} sp={sourcepawn} inc={includes}"
        )
    for relative in REQUIRED:
        if not (SUBMISSION / relative).is_file():
            errors.append(f"{relative}: required source is missing")
    for relative, expected in IMMUTABLE_HASHES.items():
        immutable = SUBMISSION / relative
        if immutable.is_file() and canonical_sha256(immutable) != expected:
            errors.append(f"{relative}: frozen license/provenance text was modified")
    if errors:
        raise SubmissionFailure("source/package checks failed:\n- " + "\n- ".join(errors))
    print(f"source/package checks passed: files={files} bytes={bytes_total} sp={sourcepawn} inc={includes}")


def compile_plugin(source: Path, output: Path, includes: tuple[Path, ...]) -> None:
    command = [str(COMPILER)]
    for include in includes:
        command.extend(("-i", str(include)))
    command.extend(("-o", str(output), str(source)))
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode:
        raise SubmissionFailure(f"SourcePawn compile failed for {source.name}:\n{completed.stdout}{completed.stderr}")


def copy_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        return
    for path in source.rglob("*"):
        if path.is_file():
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def prepare_runtime(temp: Path, nonces: dict[str, str]) -> tuple[Path, dict[str, Path]]:
    binary = RUNTIME / "srcds_run"
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise EnvironmentFailure("L4D2 dedicated-server binary is unavailable")
    if not COMPILER.is_file() or not os.access(COMPILER, os.X_OK):
        raise EnvironmentFailure("pinned SourceMod compiler is unavailable")
    if list(PLUGIN_DIR.rglob("*.smx")):
        raise EnvironmentFailure("verifier SourceMod plugin directory is not clean")

    include_paths = (SM_ROOT / "scripting/include", SCRIPTING / "include", SCRIPTING)
    core = temp / "00_mutant_tanks.smx"
    abilities = temp / "10_mt_abilities.smx"
    abilities2 = temp / "11_mt_abilities2.smx"
    compile_plugin(SCRIPTING / "mutant_tanks/mutant_tanks.sp", core, include_paths)
    compile_plugin(SCRIPTING / "mutant_tanks/mt_abilities.sp", abilities, include_paths)
    compile_plugin(SCRIPTING / "mutant_tanks/mt_abilities2.sp", abilities2, include_paths)

    suite_texts = {
        "default": (TESTS / "suite.sp").read_text(encoding="utf-8"),
        "reward": (TESTS / "reward_suite.sp").read_text(encoding="utf-8"),
    }
    if any(text.count("__GCB_NONCE__") != 1 or text.count("__GCB_GROUP__") != 1
           for text in suite_texts.values()):
        raise EnvironmentFailure("a private suite has invalid placeholders")
    suites: dict[str, Path] = {}
    suite_sources: dict[str, Path] = {}
    for group, nonce in nonces.items():
        suite_text = suite_texts["reward" if group in {"reward_ab", "reward_ba"} else "default"]
        suite_source = temp / f"suite-{group}.sp"
        suite_source.write_text(
            suite_text.replace("__GCB_NONCE__", nonce).replace("__GCB_GROUP__", group),
            encoding="utf-8",
        )
        suite_sources[group] = suite_source
        suites[group] = temp / f"99_gcb_mutant_tanks_{group}.smx"
        # The runnable verifier must not trust a candidate-controlled include:
        # it links against the frozen public contract copied into /tests.
        compile_plugin(suite_source, suites[group], (SM_ROOT / "scripting/include", TESTS / "include"))

    # Separately compile a public consumer against the submitted include.  This
    # closes accidental ABI breakage, but the untrusted artifact is never
    # installed or executed by the dedicated server.
    compile_plugin(
        next(iter(suite_sources.values())),
        temp / "candidate-public-api-consumer.smx",
        (SM_ROOT / "scripting/include", SCRIPTING / "include"),
    )

    # Copy only Mutant Tanks-owned runtime assets.  The dedicated-server image
    # owns SourceMod's core gamedata/configuration, so a candidate must not be
    # able to replace files such as core.games.txt or sdkhooks.games.txt.
    gamedata_source = SUBMISSION / "addons/sourcemod/gamedata/mutant_tanks.txt"
    gamedata_target = SM_ROOT / "gamedata/mutant_tanks.txt"
    gamedata_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(gamedata_source, gamedata_target)

    copy_tree(
        SUBMISSION / "addons/sourcemod/data/mutant_tanks",
        SM_ROOT / "data/mutant_tanks",
    )

    translations_source = SUBMISSION / "addons/sourcemod/translations"
    if translations_source.is_dir():
        for path in translations_source.rglob("mutant_tanks*.phrases.txt"):
            if path.is_file():
                target = SM_ROOT / "translations" / path.relative_to(translations_source)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)

    cfg_source = SUBMISSION / "cfg/sourcemod/mutant_tanks.cfg"
    cfg_target = RUNTIME / "left4dead2/cfg/sourcemod/mutant_tanks.cfg"
    cfg_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cfg_source, cfg_target)

    # The private fixture is verifier-owned and is always installed last.
    config_dir = SM_ROOT / "data/mutant_tanks"
    config_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TESTS / "mutant_tanks.cfg", config_dir / "mutant_tanks.cfg")
    for plugin in (core, abilities, abilities2):
        shutil.copy2(plugin, PLUGIN_DIR / plugin.name)

    steam = pwd.getpwnam("steam")
    for root in (SM_ROOT / "gamedata", SM_ROOT / "data", SM_ROOT / "translations", RUNTIME / "left4dead2/cfg", PLUGIN_DIR):
        for path in root.rglob("*"):
            if path.exists():
                os.chown(path, steam.pw_uid, steam.pw_gid)
    return binary, suites


def install_suite(suite: Path) -> Path:
    target = PLUGIN_DIR / "99_gcb_mutant_tanks.smx"
    shutil.copy2(suite, target)
    steam = pwd.getpwnam("steam")
    os.chown(target, steam.pw_uid, steam.pw_gid)
    return target


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


def run_server(binary: Path, nonce: str) -> str:
    command = [
        str(binary), "-game", "left4dead2", "-console", "-insecure", "-norestart",
        "+sv_lan", "1", "+sv_hibernate_when_empty", "0", "+hostport", str(available_port()),
        "+map", "c1m1_hotel", "coop",
    ]
    steam = pwd.getpwnam("steam")
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
    deadline = time.monotonic() + 165
    final_prefix = f"{MARKER}{nonce}:FINAL:"
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


def parse_results(log: str, nonce: str, expected: tuple[str, ...]) -> list[tuple[str, bool, str]]:
    prefix = f"{MARKER}{nonce}:"
    observed: dict[str, tuple[bool, str]] = {}
    duplicate: set[str] = set()
    case_line_indices: list[int] = []
    finals: list[tuple[int, int]] = []
    lines = log.splitlines()
    final_line_index: int | None = None
    for line_index, line in enumerate(lines):
        if prefix not in line:
            continue
        fields = line.split(prefix, 1)[1].strip().split(":", 3)
        if len(fields) == 4 and fields[0] == "CASE" and fields[2] in {"PASS", "FAIL"}:
            case_line_indices.append(line_index)
            if fields[1] in observed:
                duplicate.add(fields[1])
            observed[fields[1]] = (fields[2] == "PASS", fields[3])
        elif len(fields) == 3 and fields[0] == "FINAL":
            with suppress(ValueError):
                finals.append((int(fields[1]), int(fields[2])))
                if final_line_index is None:
                    final_line_index = line_index
    fatal_pattern = re.compile(
        r"(?:\[SM\]\s*)?Exception reported:|Native\s+.+?\s+is not bound|"
        r"Plugin .* failed to load|PreMinidumpCallback|Segmentation fault|SIGSEGV|signal 11",
        re.I,
    )
    # FINAL is the suite's terminal boundary.  The verifier intentionally
    # terminates srcds after it sees that nonce, and SourceMod may emit
    # unrelated plugin-unload errors while processing the resulting quit.
    # Functional cleanup (including Hypno aggregate unload) occurs before
    # FINAL and therefore remains inside the fatal scan.  The complete log is
    # still used above to fail closed on duplicate/missing cases and FINALs.
    fatal_lines = lines if final_line_index is None else lines[: final_line_index + 1]
    runtime_errors = [line.strip() for line in fatal_lines if fatal_pattern.search(line)]
    unknown_runtime_error = bool(runtime_errors)
    valid = (
        not unknown_runtime_error and not duplicate and set(observed) == set(expected) and len(finals) == 1
        and final_line_index is not None and all(index < final_line_index for index in case_line_indices)
        and finals[0][1] == len(expected) and finals[0][0] == sum(value[0] for value in observed.values())
    )
    if not valid:
        detail = runtime_errors[-1] if runtime_errors else "server suite did not complete its exact case contract"
        return [(name, False, detail) for name in expected]
    return [(name, *observed[name]) for name in expected]


def main() -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    try:
        validate_submission()
        only_group = os.environ.get("GCB_ONLY_GROUP", "").strip()
        if only_group and only_group not in GROUP_CASES:
            raise EnvironmentFailure(f"unknown focused group: {only_group}")
        selected_groups = {only_group: GROUP_CASES[only_group]} if only_group else GROUP_CASES
        expected_cases = tuple(name for expected in selected_groups.values() for name in expected)
        selected_boots = {
            boot: BOOT_CASES[boot]
            for group in selected_groups
            for boot in GROUP_BOOTS[group]
        }
        nonces = {boot: uuid.uuid4().hex for boot in selected_boots}
        results: list[tuple[str, bool, str]] = []
        with tempfile.TemporaryDirectory(prefix="gcb-mutant-tanks-") as directory:
            binary, suites = prepare_runtime(Path(directory), nonces)
            fixture_names = {
                "warp": "mutant_tanks-warp.cfg",
                "boss": "mutant_tanks-lifecycle.cfg",
                "reward_ab": "mutant_tanks-reward-stack.cfg",
                "reward_ba": "mutant_tanks-reward-stack.cfg",
                "hypno": "mutant_tanks-hypno.cfg",
                "panic_fallback": "mutant_tanks-panic-fallback.cfg",
                "rainbow_transfer": "mutant_tanks-rainbow.cfg",
                "cooldown": "mutant_tanks-cooldown.cfg",
            }
            for group, expected in selected_boots.items():
                config_source = TESTS / fixture_names.get(group, "mutant_tanks.cfg")
                shutil.copy2(config_source, SM_ROOT / "data/mutant_tanks/mutant_tanks.cfg")
                installed = install_suite(suites[group])
                try:
                    log = run_server(binary, nonces[group])
                finally:
                    installed.unlink(missing_ok=True)
                (LOGS / f"server-{group}.log").write_text(log, encoding="utf-8")
                results.extend(parse_results(log, nonces[group], expected))
        for name, passed, detail in results:
            print(f"{'PASS' if passed else 'FAIL'} {name}: {detail}")
        passed_count = sum(passed for _, passed, _ in results)
        print(f"managed SourceMod cases passed: {passed_count}/{len(expected_cases)}")
        if passed_count != len(expected_cases):
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
