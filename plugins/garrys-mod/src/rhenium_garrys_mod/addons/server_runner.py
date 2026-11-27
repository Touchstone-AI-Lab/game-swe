from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Never

from .contracts import GmodTaskRuntimeSpec
from .installation import (
    MARKER,
    MARKER_END,
    available_udp_port,
    build_command,
    clone_server_tree,
    content_tree_digest,
    create_directory_junction,
    linux_server_binary,
    metadata_tree_digest,
    read_build_id,
    remove_directory_junction,
    replace_placeholders,
)
from .linux_process import process_group_members, run_process_group
from .process import ProcessResult, run_process_in_job, srcds_process_ids
from .runtime import GmodRuntimeConfig
from .submission import copy_submission_tree, validate_submission_tree

_HASH = re.compile(r"[0-9a-f]{64}")
_RUN_PREFIX = "gmod-run-"
_INSTALLED_SUITE_LUA = Path("lua/autorun/server/rhenium_private_suite.lua")


class GmodServerRunnerError(RuntimeError):
    pass


@dataclass(frozen=True)
class GmodPhaseResult:
    phase: str
    nonce: str
    process_id: int | None
    started_at_utc: str
    ended_at_utc: str
    duration_seconds: float
    exit_code: int | None
    forced_termination: bool
    timed_out: bool
    protocol_accepted: bool
    nonce_valid: bool
    marker_count: int
    payload: dict[str, Any] | None
    evidence_hash_valid: bool
    evidence: dict[str, Any] | None
    command: list[str]
    job_active_processes: int
    residual_processes: list[int]
    error: str
    output_tail: str


@dataclass(frozen=True)
class GmodRuntimeResult:
    run_id: str
    status: str
    server_build: str
    server_branch: str
    declared_timeout_seconds: float
    effective_timeout_seconds: float
    submission_hash: str
    phase_a: GmodPhaseResult
    phase_b: GmodPhaseResult | None
    phase_b_started: bool
    pids_distinct: bool
    data_directory_reused: bool
    only_data_reused: bool
    state_hash_valid: bool
    evidence_groups_complete: bool
    cleanup: dict[str, bool]
    residual_processes: list[int]
    submission_unchanged: bool
    suite_unchanged: bool
    server_install_unchanged: bool
    error: str


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _strict_json_loads(raw: str | bytes) -> Any:
    """Decode protocol JSON while rejecting ambiguous duplicate object keys."""

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise GmodServerRunnerError(f"protocol JSON contains duplicate field: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> Never:
        raise GmodServerRunnerError(f"protocol JSON contains non-finite number: {value}")

    return json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)


def _selected_files_digest(paths: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: str(item).lower()):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _data_file(shared: Path, relative: PurePosixPath) -> Path:
    candidate = (shared / Path(*relative.parts)).resolve()
    if not candidate.is_relative_to(shared.resolve()):
        raise GmodServerRunnerError("runtime data path escaped the shared data directory")
    return candidate


def parse_framed_marker(
    output: str,
    *,
    spec: GmodTaskRuntimeSpec,
    nonce: str,
    run_id: str,
    build: str,
    phase: str,
) -> tuple[dict[str, Any], int]:
    if phase not in spec.phases:
        raise GmodServerRunnerError("marker phase is not declared by this task")
    marker_count = output.count(MARKER)
    end_count = output.count(MARKER_END)
    if marker_count != 1 or end_count != 1:
        raise GmodServerRunnerError(f"expected exactly one framed marker, found {marker_count}")
    start = output.find(MARKER)
    end = output.find(MARKER_END, start)
    prefix = f"{MARKER}{nonce}:"
    envelope = output[start:end]
    if not envelope.startswith(prefix):
        raise GmodServerRunnerError("marker nonce does not match this phase")
    try:
        payload = _strict_json_loads(envelope[len(prefix) :])
    except json.JSONDecodeError as error:
        raise GmodServerRunnerError("marker payload is not valid JSON") from error
    if not isinstance(payload, dict):
        raise GmodServerRunnerError("marker payload must be an object")
    expected = {
        "runId": run_id,
        "phase": phase,
        "serverBuild": build,
        "suiteId": spec.suite_id,
        "runtimeNamespace": spec.runtime_namespace,
        "taskVersion": spec.task_version,
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            raise GmodServerRunnerError(f"marker {key} is inconsistent")
    cases = payload.get("cases")
    names = [item.get("name") for item in cases if isinstance(item, dict)] if isinstance(cases, list) else []
    if not isinstance(cases, list) or names != list(spec.expected_cases):
        raise GmodServerRunnerError("marker cases do not match the task contract")
    if not all(isinstance(item, dict) and isinstance(item.get("passed"), bool) for item in cases):
        raise GmodServerRunnerError("marker contains a malformed case")
    actual = "passed" if all(item["passed"] for item in cases) else "failed"
    if payload.get("status") != actual:
        raise GmodServerRunnerError("marker status is inconsistent with cases")
    digest_fields = ("stateHash", "evidenceHash") if phase == "A" else ("inputHash", "evidenceHash")
    for field in digest_fields:
        if not isinstance(payload.get(field), str) or _HASH.fullmatch(payload[field]) is None:
            raise GmodServerRunnerError(f"marker {field} is not a SHA-256 digest")
    return payload, marker_count


def runtime_payload_matches_contract(
    payload: object,
    *,
    spec: GmodTaskRuntimeSpec,
    phase: str,
) -> bool:
    if not isinstance(payload, dict):
        return False
    cases = payload.get("cases")
    if not isinstance(cases, list):
        return False
    if not all(isinstance(item, dict) and isinstance(item.get("passed"), bool) for item in cases):
        return False
    names = [item.get("name") for item in cases]
    return bool(
        phase in spec.phases
        and payload.get("phase") == phase
        and payload.get("suiteId") == spec.suite_id
        and payload.get("runtimeNamespace") == spec.runtime_namespace
        and payload.get("taskVersion") == spec.task_version
        and names == list(spec.expected_cases)
        and payload.get("status")
        == ("passed" if cases and all(item["passed"] for item in cases) else "failed")
    )


def runtime_result_integrity(
    runtime: object,
    *,
    spec: GmodTaskRuntimeSpec,
    pinned_build: str,
) -> bool:
    """Revalidate the runner envelope before the evaluator awards runtime points."""

    if not isinstance(runtime, dict) or runtime.get("server_build") != pinned_build:
        return False
    phase_payloads: list[dict[str, Any]] = []
    for phase in spec.phases:
        record = runtime.get(f"phase_{phase.lower()}")
        if not isinstance(record, dict):
            return False
        payload = record.get("payload")
        if not (
            record.get("phase") == phase
            and record.get("protocol_accepted") is True
            and record.get("nonce_valid") is True
            and record.get("marker_count") == 1
            and record.get("evidence_hash_valid") is True
            and record.get("timed_out") is False
            and record.get("forced_termination") is False
            and record.get("exit_code") == 0
            and record.get("job_active_processes") == 0
            and record.get("residual_processes") == []
            and not record.get("error")
            and runtime_payload_matches_contract(payload, spec=spec, phase=phase)
        ):
            return False
        assert isinstance(payload, dict)
        phase_payloads.append(payload)
    expected_status = (
        "passed" if all(payload.get("status") == "passed" for payload in phase_payloads) else "failed"
    )
    if runtime.get("status") != expected_status:
        return False
    requires_phase_b = "B" in spec.phases
    if requires_phase_b and not (
        runtime.get("phase_b_started") is True
        and runtime.get("pids_distinct") is True
        and runtime.get("data_directory_reused") is True
        and runtime.get("only_data_reused") is True
    ):
        return False
    cleanup = runtime.get("cleanup")
    return bool(
        runtime.get("state_hash_valid") is True
        and runtime.get("evidence_groups_complete") is True
        and isinstance(cleanup, dict)
        and cleanup
        and all(value is True for value in cleanup.values())
        and runtime.get("residual_processes") == []
        and runtime.get("submission_unchanged") is True
        and runtime.get("suite_unchanged") is True
        and runtime.get("server_install_unchanged") is True
        and not runtime.get("error")
    )


def _validate_evidence(
    value: object,
    *,
    spec: GmodTaskRuntimeSpec,
    run_id: str,
    phase: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GmodServerRunnerError("server evidence must be an object")
    expected = {
        "runId": run_id,
        "phase": phase,
        "suiteId": spec.suite_id,
        "runtimeNamespace": spec.runtime_namespace,
        "taskVersion": spec.task_version,
    }
    if any(value.get(key) != expected_value for key, expected_value in expected.items()):
        raise GmodServerRunnerError("server evidence identity is inconsistent")
    assertions = value.get("assertions")
    if not isinstance(assertions, list) or not assertions:
        raise GmodServerRunnerError("server evidence has no assertions")
    grouped: dict[str, list[bool]] = {}
    for item in assertions:
        if (
            not isinstance(item, dict)
            or item.get("group") not in spec.expected_cases
            or not isinstance(item.get("name"), str)
            or not item["name"].strip()
            or not isinstance(item.get("passed"), bool)
        ):
            raise GmodServerRunnerError("server evidence contains a malformed assertion")
        grouped.setdefault(item["group"], []).append(item["passed"])
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise GmodServerRunnerError("marker cases are unavailable for evidence validation")
    case_status = {item["name"]: item["passed"] for item in cases}
    if any(case_status[group] != all(values) for group, values in grouped.items()):
        raise GmodServerRunnerError("server evidence group status is inconsistent with the marker")
    assertions_passed = all(item["passed"] for item in assertions)
    if assertions_passed != (payload.get("status") == "passed"):
        raise GmodServerRunnerError("server evidence status is inconsistent with the marker")
    return value


def install_task_addons(
    submission: Path,
    spec: GmodTaskRuntimeSpec,
    submission_target: Path,
    suite_target: Path,
    *,
    nonce: str,
    run_id: str,
    build: str,
    phase: str,
    state_hash: str,
) -> None:
    tree = validate_submission_tree(submission)
    copy_submission_tree(tree, submission_target)
    suite_target.mkdir(parents=True)
    shutil.copy2(spec.addon_manifest, suite_target / "addon.json")
    script_target = suite_target / _INSTALLED_SUITE_LUA
    script_target.parent.mkdir(parents=True)
    shutil.copy2(spec.lua_entry, script_target)
    replace_placeholders(
        script_target,
        {
            "__RHENIUM_NONCE__": nonce,
            "__RHENIUM_RUN_ID__": run_id,
            "__RHENIUM_SERVER_BUILD__": build,
            "__RHENIUM_PHASE__": phase,
            "__RHENIUM_STATE_HASH__": state_hash,
            "__RHENIUM_SUITE_ID__": spec.suite_id,
            "__RHENIUM_RUNTIME_NAMESPACE__": spec.runtime_namespace,
            "__RHENIUM_TASK_VERSION__": spec.task_version,
            "__RHENIUM_DATA_DIRECTORY__": spec.data_directory.as_posix(),
            "__RHENIUM_STATE_PATH__": spec.state_path(run_id).as_posix(),
            "__RHENIUM_EVIDENCE_PATH__": spec.evidence_path(run_id, phase).as_posix(),
        },
    )


def task_scoped_run_id(spec: GmodTaskRuntimeSpec) -> str:
    task_scope = _sha256(f"{spec.task_id}\0{spec.suite_id}".encode())[:12]
    return f"{_RUN_PREFIX}{task_scope}-{uuid.uuid4().hex[:16]}"


def _command(binary: Path, run_id: str, phase: str) -> list[str]:
    command = build_command(binary, run_id, available_udp_port())
    command[command.index("+hostname") + 1] = f"Rhenium GMod Phase {phase} {run_id}"
    return command


_SERVER_ENV_ALLOWLIST = {
    "COMSPEC",
    "NUMBER_OF_PROCESSORS",
    "OS",
    "PATH",
    "PATHEXT",
    "PROCESSOR_ARCHITECTURE",
    "SYSTEMDRIVE",
    "SYSTEMROOT",
    "WINDIR",
}


def _environment(temp: Path, linux_root: Path | None = None) -> dict[str, str]:
    value = {key: item for key, item in os.environ.items() if key.upper() in _SERVER_ENV_ALLOWLIST}
    value.update(
        {
            "TEMP": str(temp),
            "TMP": str(temp),
            "SteamAppId": "4000",
            "SteamGameId": "4000",
        }
    )
    if linux_root is not None:
        value.update({
            "HOME": str(temp), "TMPDIR": str(temp), "LANG": "C.UTF-8",
            "LD_LIBRARY_PATH": f"{linux_root / 'bin'}:{linux_root}",
        })
    return value


def _phase_record(
    phase: str,
    nonce: str,
    process: ProcessResult | None,
    payload: dict[str, Any] | None,
    evidence: dict[str, Any] | None,
    evidence_hash_valid: bool,
    command: list[str],
    nonce_valid: bool,
    marker_count: int,
    residual: list[int],
    error: str,
) -> GmodPhaseResult:
    return GmodPhaseResult(
        phase=phase,
        nonce=nonce,
        process_id=process.process_id if process else None,
        started_at_utc=process.started_at_utc if process else "",
        ended_at_utc=process.ended_at_utc if process else "",
        duration_seconds=process.duration_seconds if process else 0.0,
        exit_code=process.exit_code if process else None,
        forced_termination=process.forced_termination if process else False,
        timed_out=process.timed_out if process else False,
        protocol_accepted=payload is not None and evidence is not None and not error,
        nonce_valid=nonce_valid,
        marker_count=marker_count,
        payload=payload,
        evidence_hash_valid=evidence_hash_valid,
        evidence=evidence,
        command=command,
        job_active_processes=process.job_active_processes if process else -1,
        residual_processes=residual,
        error=error,
        output_tail=process.output[-8000:] if process else "",
    )


def _normal(process: ProcessResult | None) -> bool:
    return bool(
        process
        and process.exit_code == 0
        and not process.timed_out
        and not process.forced_termination
        and process.job_active_processes == 0
    )


def _phase_process(phase: GmodPhaseResult | None) -> ProcessResult | None:
    if phase is None:
        return None
    return ProcessResult(
        phase.process_id or 0,
        phase.started_at_utc,
        phase.ended_at_utc,
        phase.exit_code,
        phase.forced_termination,
        phase.timed_out,
        phase.duration_seconds,
        "",
        phase.job_active_processes,
    )


def _cleanup(
    run_root: Path,
    runs_root: Path,
    links: list[tuple[Path, Path]],
    tracked: dict[str, Path],
) -> dict[str, bool]:
    root = run_root.resolve()
    if root.parent != runs_root.resolve() or not root.name.startswith(_RUN_PREFIX):
        raise GmodServerRunnerError(f"refusing to clean unexpected path: {root}")
    for link, target in reversed(links):
        remove_directory_junction(link, target)
    for attempt in range(5):
        try:
            shutil.rmtree(root)
        except FileNotFoundError:
            break
        except OSError:
            if attempt == 4:
                break
            time.sleep(0.25 * (attempt + 1))
        else:
            break
    return {name: not path.exists() for name, path in tracked.items()} | {"run_root": not root.exists()}


def run_gmod_task_once(
    *,
    server_root: Path,
    submission: Path,
    spec: GmodTaskRuntimeSpec,
    runs_root: Path,
    pinned_build: str,
    server_branch: str,
    timeout: float | None = None,
    platform: str = "windows-x86_64",
) -> GmodRuntimeResult:
    server_root = server_root.resolve(strict=True)
    submission = submission.resolve(strict=True)
    build = read_build_id(server_root)
    if platform not in {"windows-x86_64", "linux-x86_64"}:
        raise GmodServerRunnerError("unsupported native server platform")
    if platform == "linux-x86_64":
        linux_server_binary(server_root)
    if build != pinned_build:
        raise GmodServerRunnerError(f"GMod scoring requires pinned build {pinned_build}, found {build}")
    if timeout is not None and timeout < spec.timeout_seconds:
        raise GmodServerRunnerError(
            f"GMod global timeout ceiling {timeout} is below the task contract {spec.timeout_seconds}"
        )
    effective_timeout = spec.timeout_seconds
    runs_root.mkdir(parents=True, exist_ok=True)
    runs_root = runs_root.resolve(strict=True)
    run_id = task_scoped_run_id(spec)
    run_root = runs_root / run_id
    shared = run_root / "shared-data"
    phase_roots = {phase: run_root / f"phase-{phase.lower()}" for phase in spec.phases}
    server_roots = {phase: phase_roots[phase] / "server" for phase in spec.phases}
    data_links = {phase: server_roots[phase] / "garrysmod" / "data" for phase in spec.phases}
    tracked = {
        "shared_data": shared,
        **{f"phase_{phase.lower()}": phase_roots[phase] for phase in spec.phases},
    }
    install_before = metadata_tree_digest(server_root)
    submission_before = content_tree_digest(submission)
    suite_assets = (spec.addon_manifest, spec.lua_entry)
    suite_before = _selected_files_digest(suite_assets)
    baseline = srcds_process_ids() if platform == "windows-x86_64" else set()
    links: list[tuple[Path, Path]] = []
    records: dict[str, GmodPhaseResult] = {}
    state_hash = ""
    state_hash_valid = False
    phase_b_started = False
    overall_error = ""
    try:
        run_root.mkdir()
        shared.mkdir()
        for phase in spec.phases:
            if phase == "B":
                phase_b_started = True
            root = phase_roots[phase]
            temp = root / "temp"
            logs = root / "logs"
            temp.mkdir(parents=True)
            logs.mkdir()
            clone_server_tree(server_root, server_roots[phase])
            create_directory_junction(data_links[phase], shared)
            links.append((data_links[phase], shared))
            addons = server_roots[phase] / "garrysmod" / "addons"
            submission_target = addons / spec.submission_addon_name
            suite_target = addons / spec.private_suite_addon_name
            nonce = uuid.uuid4().hex
            install_task_addons(
                submission,
                spec,
                submission_target,
                suite_target,
                nonce=nonce,
                run_id=run_id,
                build=build,
                phase=phase,
                state_hash=state_hash or "0" * 64,
            )
            linux_root = server_roots[phase] if platform == "linux-x86_64" else None
            binary = linux_server_binary(linux_root) if linux_root else server_roots[phase] / "srcds.exe"
            command = _command(binary, run_id, phase)
            if linux_root:
                console_log = linux_root / "garrysmod" / "console.log"
                # Unlink only this newly cloned view's copy of an operator log,
                # never the original installation's hard-linked file.
                console_log.unlink(missing_ok=True)
                command.insert(1, "-condebug")
                process = run_process_group(
                    command, cwd=linux_root, environment=_environment(temp, linux_root),
                    timeout=effective_timeout, console_log=console_log,
                )
            else:
                process = run_process_in_job(
                    command, cwd=server_roots[phase], environment=_environment(temp),
                    timeout=effective_timeout,
                )
            marker_count = process.output.count(MARKER)
            nonce_valid = marker_count == 1 and f"{MARKER}{nonce}:" in process.output
            payload = None
            evidence = None
            evidence_valid = False
            error = ""
            try:
                payload, marker_count = parse_framed_marker(
                    process.output,
                    spec=spec,
                    nonce=nonce,
                    run_id=run_id,
                    build=build,
                    phase=phase,
                )
                evidence_file = _data_file(shared, spec.evidence_path(run_id, phase))
                raw_evidence = evidence_file.read_bytes()
                evidence_valid = _sha256(raw_evidence) == payload["evidenceHash"]
                if not evidence_valid:
                    raise GmodServerRunnerError("evidence hash mismatch")
                evidence = _validate_evidence(
                    _strict_json_loads(raw_evidence),
                    spec=spec,
                    run_id=run_id,
                    phase=phase,
                    payload=payload,
                )
                if phase == "A":
                    raw_state = _data_file(shared, spec.state_path(run_id)).read_bytes()
                    state_hash = _sha256(raw_state)
                    state_hash_valid = state_hash == payload["stateHash"]
                    if not state_hash_valid:
                        raise GmodServerRunnerError("state hash mismatch")
                elif payload["inputHash"] != state_hash:
                    raise GmodServerRunnerError("Phase B input hash mismatch")
            except (OSError, json.JSONDecodeError, GmodServerRunnerError) as phase_error:
                error = str(phase_error)
            residual = sorted(
                process_group_members(process.process_id) if linux_root else srcds_process_ids() - baseline
            )
            records[phase] = _phase_record(
                phase,
                nonce,
                process,
                payload,
                evidence,
                evidence_valid,
                command,
                nonce_valid,
                marker_count,
                residual,
                error,
            )
            remove_directory_junction(data_links[phase], shared)
            links.pop()
            if not (
                _normal(process)
                and records[phase].protocol_accepted
                and payload
                and payload.get("status") == "passed"
                and not residual
            ):
                if phase == "A":
                    phase_b_started = False
                break
    except BaseException as error:
        overall_error = str(error) or type(error).__name__
    submission_unchanged = content_tree_digest(submission) == submission_before
    suite_unchanged = _selected_files_digest(suite_assets) == suite_before
    install_unchanged = metadata_tree_digest(server_root) == install_before
    residual = sorted(
        {pid for record in records.values() if record.process_id
         for pid in process_group_members(record.process_id)}
        if platform == "linux-x86_64" else srcds_process_ids() - baseline
    )
    cleanup = _cleanup(run_root, runs_root, links, tracked)
    phase_a = records.get("A") or _phase_record(
        "A", "", None, None, None, False, [], False, 0, [], "Phase A did not run"
    )
    phase_b = records.get("B")
    requires_phase_b = "B" in spec.phases
    pids_distinct = bool(phase_b and phase_a.process_id != phase_b.process_id) if requires_phase_b else True
    evidenced_groups = {
        item["group"]
        for record in records.values()
        if isinstance(record.evidence, dict)
        for item in record.evidence.get("assertions", [])
        if isinstance(item, dict) and isinstance(item.get("group"), str)
    }
    evidence_groups_complete = evidenced_groups == set(spec.expected_cases)
    final_phase = records.get(spec.phases[-1])
    all_phases_completed = all(phase in records for phase in spec.phases)
    successful = bool(
        final_phase
        and all_phases_completed
        and all(record.protocol_accepted for record in records.values())
        and all(record.payload and record.payload.get("status") == "passed" for record in records.values())
        and _normal(_phase_process(final_phase))
        and pids_distinct
        and state_hash_valid
        and evidence_groups_complete
        and not residual
        and submission_unchanged
        and suite_unchanged
        and install_unchanged
        and all(cleanup.values())
        and not overall_error
    )
    return GmodRuntimeResult(
        run_id=run_id,
        status="passed" if successful else "failed",
        server_build=build,
        server_branch=server_branch,
        declared_timeout_seconds=spec.timeout_seconds,
        effective_timeout_seconds=effective_timeout,
        submission_hash=submission_before,
        phase_a=phase_a,
        phase_b=phase_b,
        phase_b_started=phase_b_started,
        pids_distinct=pids_distinct,
        data_directory_reused=requires_phase_b and phase_b_started,
        only_data_reused=requires_phase_b and phase_b_started,
        state_hash_valid=state_hash_valid,
        evidence_groups_complete=evidence_groups_complete,
        cleanup=cleanup,
        residual_processes=residual,
        submission_unchanged=submission_unchanged,
        suite_unchanged=suite_unchanged,
        server_install_unchanged=install_unchanged,
        error=overall_error,
    )


def result_dict(result: GmodRuntimeResult) -> dict[str, Any]:
    return asdict(result)


class GmodDedicatedServerRunner:
    """Production GMod Dedicated Server backend for validated task contracts."""

    def __init__(self, config: GmodRuntimeConfig):
        self.config = config

    def status(self) -> dict[str, Any]:
        root = self.config.server_root
        available = bool(root and (root / "srcds.exe").is_file())
        build = None
        reason = None
        if root is not None and self.config.platform == "linux-x86_64":
            try:
                linux_server_binary(root)
                available = True
            except (OSError, RuntimeError) as error:
                available = False
                reason = str(error)
        if available and root is not None:
            try:
                build = read_build_id(root)
            except (OSError, RuntimeError) as error:
                available = False
                reason = str(error)
        if available and build != self.config.pinned_build:
            available = False
            reason = "Dedicated Server build does not match the pinned benchmark build"
        if available and root is not None:
            server_drive = root.resolve().drive.lower()
            runs_drive = self.config.runs_root.resolve().drive.lower()
            if server_drive != runs_drive:
                available = False
                reason = "Rhenium state and the Dedicated Server must use the same Windows volume"
            if self.config.platform == "linux-x86_64":
                ancestor = self.config.runs_root.resolve()
                while not ancestor.exists() and ancestor.parent != ancestor:
                    ancestor = ancestor.parent
                if ancestor.stat().st_dev != root.stat().st_dev:
                    available = False
                    reason = "Rhenium state and the Dedicated Server must use the same Linux filesystem"
        return {
            "id": "gmod-dedicated-server",
            "available": available,
            "reason": reason,
            "root": str(root) if root else None,
            "runsRoot": str(self.config.runs_root),
            "build": build,
            "pinnedBuild": self.config.pinned_build,
            "branch": self.config.server_branch,
            "appId": self.config.app_id,
            "platform": self.config.platform,
            "globalTimeoutSeconds": self.config.timeout_seconds,
        }

    def run(self, submission: Path, spec: GmodTaskRuntimeSpec) -> dict[str, Any]:
        if not self.status()["available"] or self.config.server_root is None:
            return {
                "status": "unavailable",
                "message": "Pinned GMod Dedicated Server is unavailable",
            }
        result = run_gmod_task_once(
            server_root=self.config.server_root,
            submission=submission,
            spec=spec,
            runs_root=self.config.runs_root,
            pinned_build=self.config.pinned_build,
            server_branch=self.config.server_branch,
            timeout=self.config.timeout_seconds,
            platform=self.config.platform,
        )
        return result_dict(result)
