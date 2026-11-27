from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from rhenium_study import aggregate, attempts, cli, controls, deferred, e2, exclusions, paper_export
from rhenium_study.e1config import StudyConfig
from rhenium_study.exclusions import EXCLUSIONS_FILE
from rhenium_study.inventory import BY_KEY
from rhenium_study.paths import StudyPaths
from typer.testing import CliRunner

ROOT = Path(__file__).parents[3]
KEPT = (
    "slay-the-spire/core/basemod-dynamic-descriptions-r2",
    "slay-the-spire/core/stslib-block-ledger-r1",
)
# Not registered, like a task removed from the inventory: it must be excluded.
GONE = "example/core/removed-task"
# Registered but excluded all the same.
GONE_TOO = "slay-the-spire/core/stslib-icon-layout-r1"
CONFIG = f"""
study_id = "exclusion-test"
snapshot_commit = "{"0" * 40}"
scaffold = "test"
repeats = 2
schedule_seed = 11
agent_image = "agent:test"
tasks = {json.dumps([KEPT[0], GONE, KEPT[1], GONE_TOO])}
e2_selection_rule = "none"
e2_max_cases = 5

[budget]
step_limit = 1
command_timeout_seconds = 1
wall_time_limit_seconds = 60
request_timeout_seconds = 30

[[models]]
id = "m"
litellm_model = "x"
base_url = "https://a.example"
api_key_file = "k"

[[models]]
id = "n"
litellm_model = "y"
base_url = "https://b.example"
api_key_file = "k"
"""


def _study(tmp_path: Path) -> tuple[StudyPaths, StudyConfig, str, Path]:
    path = tmp_path / "study.toml"
    path.write_text(CONFIG, encoding="utf-8")
    config, digest = StudyConfig.load(path)
    return StudyPaths(project_root=ROOT, data_root=tmp_path / "data"), config, digest, path


def _amendment(*tasks: str) -> dict[str, Any]:
    return {
        "tasks": list(tasks),
        "reason": "tasks removed from the benchmark",
        "decidedAt": "2026-09-26",
        "decidedBy": "study owner",
    }


def _document(config: StudyConfig, digest: str, *amendments: dict[str, Any]) -> dict[str, Any]:
    return {
        "studyId": config.study_id,
        "configDigest": digest,
        "amendments": list(amendments) or [_amendment(GONE), _amendment(GONE_TOO)],
    }


def _declare(paths: StudyPaths, config: StudyConfig, document: dict[str, Any]) -> None:
    root = paths.data_root / "e1" / config.study_id
    root.mkdir(parents=True, exist_ok=True)
    (root / EXCLUSIONS_FILE).write_text(json.dumps(document), encoding="utf-8")


def test_declared_exclusions_return_the_task_set_and_the_amendments(tmp_path: Path) -> None:
    paths, config, digest, _path = _study(tmp_path)
    _declare(paths, config, _document(config, digest))
    loaded = exclusions.load(paths, config, digest)
    assert loaded.tasks == {GONE, GONE_TOO}
    assert loaded.public() == [_amendment(GONE), _amendment(GONE_TOO)]


def test_every_configured_task_must_be_registered_or_excluded(tmp_path: Path) -> None:
    paths, config, digest, _path = _study(tmp_path)
    assert GONE not in BY_KEY and GONE_TOO in BY_KEY
    with pytest.raises(ValueError, match=f"neither registered nor excluded .*{GONE}"):
        exclusions.load(paths, config, digest)  # no file at all
    _declare(paths, config, _document(config, digest, _amendment(GONE_TOO)))
    with pytest.raises(ValueError, match=f"neither registered nor excluded .*{GONE}"):
        exclusions.load(paths, config, digest)


@pytest.mark.parametrize("kind", ["directory", "dangling link"])
def test_anything_unreadable_at_the_declaration_path_is_refused(tmp_path: Path, kind: str) -> None:
    paths, config, digest, _path = _study(tmp_path)
    target = paths.e1_study(config.study_id) / EXCLUSIONS_FILE
    target.parent.mkdir(parents=True)
    if kind == "directory":
        target.mkdir()
    else:
        target.symlink_to(tmp_path / "missing.json")
    with pytest.raises(ValueError, match="cannot be read"):
        exclusions.load(paths, config, digest)


def _amend(field: str, value: object) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        document["amendments"][0][field] = value

    return change


@pytest.mark.parametrize(
    "change,match",
    [
        (lambda document: document.update(studyId="another-study"), "declared for study"),
        (lambda document: document.update(configDigest="f" * 64), "declared for configuration"),
        (_amend("tasks", [GONE, "slay-the-spire/core/not-in-the-config"]), "does not list"),
        (_amend("tasks", [GONE, GONE_TOO, GONE]), f"excludes {GONE} twice"),
        (lambda document: document["amendments"].append(_amendment(GONE)), f"excludes {GONE} twice"),
        (lambda document: document.update(unexpected=True), "Extra inputs"),
        (lambda document: document.update(amendments=[]), "at least 1 item"),
        (_amend("tasks", []), "at least 1 item"),
        (_amend("reason", "  "), "needs a reason"),
        (_amend("decidedAt", "2026-02-30"), "day is out of range"),
        (_amend("decidedAt", "26 September 2026"), "pattern"),
        (lambda document: document["amendments"][0].pop("decidedBy"), "Field required"),
        (lambda document: document.update(configDigest="short"), "pattern"),
    ],
)
def test_a_declaration_that_does_not_check_out_is_refused(
    tmp_path: Path, change: Callable[[dict[str, Any]], None], match: str
) -> None:
    paths, config, digest, _path = _study(tmp_path)
    document = _document(config, digest)
    change(document)
    _declare(paths, config, document)
    with pytest.raises(ValueError, match=match):
        exclusions.load(paths, config, digest)


RUNNER = CliRunner()


def _said(output: str) -> str:
    """CLI output with colours, the error box and its line wrapping removed.

    Typer forces a colour terminal under GitHub Actions, so the escapes must go.
    """
    return " ".join(re.sub(r"\x1b\[[0-9;]*m", "", output).replace("│", " ").split())


def _cli(monkeypatch: pytest.MonkeyPatch, paths: StudyPaths) -> None:
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv("RHENIUM_STUDY_DIR", str(paths.data_root))


def test_every_study_command_refuses_a_configuration_whose_exclusions_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, config, digest, path = _study(tmp_path)
    _cli(monkeypatch, paths)
    _declare(paths, config, _document(config, "f" * 64))
    for command in (["e1", "plan"], ["e1", "report"], ["e2", "select"]):
        result = RUNNER.invoke(cli.app, [*command, "--config", str(path)])
        assert result.exit_code == 2 and "is declared for configuration" in _said(result.output)


def test_plan_reports_excluded_and_remaining_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, config, digest, path = _study(tmp_path)
    _cli(monkeypatch, paths)
    _declare(paths, config, _document(config, digest))
    result = RUNNER.invoke(cli.app, ["e1", "plan", "--config", str(path)])
    assert result.exit_code == 0, result.output
    plan = json.loads(result.output)
    assert (plan["configDigest"], plan["attempts"], plan["excludedTasks"]) == (digest, 16, 2)
    assert (plan["excludedAttempts"], plan["remainingAttempts"]) == (8, 8)
    assert all(
        attempt_id.split("--")[1] in {key.rsplit("/", 1)[1] for key in KEPT} for attempt_id in plan["first"]
    )


def test_run_skips_excluded_attempts_and_every_other_attempt_keeps_its_order_and_lane(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, config, digest, path = _study(tmp_path)
    _cli(monkeypatch, paths)
    _declare(paths, config, _document(config, digest))
    before = path.read_bytes()
    calls: list[tuple[int, attempts.Scheduled, str]] = []
    lane_now = [0]

    def run_attempt(
        _paths: StudyPaths, _config: StudyConfig, stamped: str, item: attempts.Scheduled, _harness: object
    ) -> dict[str, Any]:
        calls.append((lane_now[0], item, stamped))
        return {"attempt_id": item.attempt_id, "outcome": "failed", "score": 0} | {
            key: "unknown" for key in ("targetOutcome", "preservedOutcome", "jointOutcome")
        }

    monkeypatch.setattr(attempts, "harness_revision", lambda _paths: {"commit": "c" * 40, "dirty": False})
    monkeypatch.setattr(attempts, "run_attempt", run_attempt)
    for lane in range(3):
        lane_now[0] = lane
        result = RUNNER.invoke(
            cli.app, ["e1", "run", "--config", str(path), "--lane", str(lane), "--lanes", "3"]
        )
        assert result.exit_code == 0, result.output

    full = attempts.schedule(config)
    remaining = [item for item in full if item.task not in {GONE, GONE_TOO}]
    assert len(full) == 16 and len(remaining) == 8
    # Each remaining attempt runs once, in its lane, with the order number of the full schedule.
    assert sorted((item for _lane, item, _digest in calls), key=lambda item: item.order) == remaining
    assert all(item.order % 3 == lane for lane, item, _digest in calls)
    assert {stamped for _lane, _item, stamped in calls} == {digest, hashlib.sha256(before).hexdigest()}
    assert path.read_bytes() == before

    excluded_attempt = next(item.attempt_id for item in full if item.task == GONE)
    result = RUNNER.invoke(cli.app, ["e1", "run", "--config", str(path), "--only", excluded_attempt])
    assert result.exit_code == 2 and "is an attempt of an excluded task" in _said(result.output)
    assert len(calls) == 8


def _record(item: attempts.Scheduled, outcome: str = "failed", **fields: Any) -> dict[str, Any]:
    return {
        "attempt_id": item.attempt_id,
        "model": item.model,
        "task": item.task,
        "repeat": item.repeat,
        "order": item.order,
        "kind": "repair",
        "sourceFamily": "family",
        "outcome": outcome,
        "auditedOutcome": outcome,
        "complete": outcome != "unattributed",
        "cases": {},
        "targetOutcome": "satisfied",
        "preservedOutcome": "violated",
        "jointOutcome": "target-only",
        "usage": {"calls": 1, "prompt_tokens": 10, "completion_tokens": 5},
        "generation": {"durationSeconds": 2},
        **fields,
    }


def _write_ledger(paths: StudyPaths, config: StudyConfig, records: list[dict[str, Any]]) -> Path:
    root = paths.data_root / "e1" / config.study_id
    for record in records:
        directory = root / "attempts" / record["attempt_id"]
        directory.mkdir(parents=True)
        (directory / "attempt.json").write_text(json.dumps(record), encoding="utf-8")
    return root


def test_the_ledger_drops_excluded_attempts_before_adjudication(tmp_path: Path) -> None:
    paths, config, _digest, _path = _study(tmp_path)
    full = attempts.schedule(config)
    kept = [item for item in full if item.task in KEPT]
    gone = [item for item in full if item.task not in KEPT]
    records = [
        _record(kept[0], "unattributed"),
        _record(kept[1]),
        _record(kept[2], attempts.PENDING),
        _record(gone[0], "unattributed"),
        _record(gone[1]),
        _record(gone[2], attempts.PENDING),
    ]
    root = _write_ledger(paths, config, records)
    decisions = [
        {"attempt_id": item.attempt_id, "rule": "r", "from": "unattributed", "to": "failed", "evidence": {}}
        for item in (kept[0], gone[0])
    ]
    (root / "adjudication.json").write_text(json.dumps(decisions), encoding="utf-8")
    excluded = {GONE, GONE_TOO}

    ledger = aggregate.load_ledger(root, excluded=excluded)
    assert [item["attempt_id"] for item in ledger] == sorted(item.attempt_id for item in kept[:2])
    assert {item["attempt_id"]: item.get("nativeOutcome") for item in ledger}[
        kept[0].attempt_id
    ] == "unattributed"
    assert aggregate.pending_evaluation(root, excluded=excluded) == [kept[2].attempt_id]
    assert len(aggregate.load_ledger(root, excluded=())) == 4
    # The records of excluded tasks stay on disk untouched.
    for item in gone[:3]:
        stored = json.loads(
            (root / "attempts" / item.attempt_id / "attempt.json").read_text(encoding="utf-8")
        )
        assert stored == next(record for record in records if record["attempt_id"] == item.attempt_id)


def test_commands_on_one_attempt_refuse_an_excluded_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, config, digest, path = _study(tmp_path)
    full = attempts.schedule(config)
    kept = next(item for item in full if item.task in KEPT)
    gone = next(item for item in full if item.task == GONE)
    records = []
    for item in (kept, gone):
        record = _record(item, attempts.PENDING)
        submission = paths.data_root / "e1" / config.study_id / "attempts" / item.attempt_id / "submission"
        submission.mkdir(parents=True)
        (submission / "Main.java").write_text("class Main {}\n", encoding="utf-8")
        record["submissionDigest"] = controls.tree_digest(submission)
        records.append(record)
    for record in records:
        target = paths.data_root / "e1" / config.study_id / "attempts" / record["attempt_id"] / "attempt.json"
        target.write_text(json.dumps(record), encoding="utf-8")
    excluded = {GONE, GONE_TOO}

    with pytest.raises(ValueError, match=f"{gone.attempt_id} is an attempt of {GONE}"):
        attempts.rescore(paths, config, gone.attempt_id, excluded=excluded)
    with pytest.raises(ValueError, match="excludes"):
        attempts.reevaluate(paths, config, gone.attempt_id, excluded=excluded)
    with pytest.raises(ValueError, match="excludes"):
        e2.replay(paths, config, gone.attempt_id, None, excluded=excluded)
    assert not (paths.data_root / "e2").exists()

    # A kit leaves excluded tasks out, and a kit that names one is refused before any write.
    kit = tmp_path / "kit"
    assert deferred.export(paths, config, digest, kit, excluded=excluded)["attempts"] == 1
    manifest = json.loads((kit / "manifest.json").read_text(encoding="utf-8"))
    assert [entry["attemptId"] for entry in manifest["attempts"]] == [kept.attempt_id]
    manifest["attempts"].append(
        {
            "attemptId": gone.attempt_id,
            "task": GONE,
            "submissionDigest": records[1]["submissionDigest"],
            "submission": f"attempts/{gone.attempt_id}/submission",
        }
    )
    (kit / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = {"id": "run-x", "taskKey": kept.task, "result": {"complete": True, "passed": True, "checks": []}}
    (kit / "attempts" / kept.attempt_id / "result-1.json").write_text(json.dumps(result), encoding="utf-8")
    with pytest.raises(ValueError, match="excludes"):
        deferred.import_results(paths, config, digest, kit, "win11", excluded=excluded)
    ledger = aggregate.attempt_records(paths.data_root / "e1" / config.study_id, excluded=())
    assert {record["outcome"] for record in ledger} == {attempts.PENDING}

    # On the command line, a named attempt of an excluded task is refused before any is touched.
    _cli(monkeypatch, paths)
    _declare(paths, config, _document(config, digest))
    walked: list[str] = []
    monkeypatch.setattr(
        attempts, "reevaluate", lambda _paths, _config, attempt_id, *, excluded: walked.append(attempt_id)
    )
    for command in (
        ["e1", "rescore", "--attempt", gone.attempt_id],
        ["e1", "reevaluate", "--attempt", kept.attempt_id, "--attempt", gone.attempt_id],
        ["e2", "replay", "--attempt", gone.attempt_id],
    ):
        outcome = RUNNER.invoke(cli.app, [*command, "--config", str(path)])
        assert outcome.exit_code == 2, outcome.output
        assert f"{gone.attempt_id} is an attempt of {GONE}" in _said(outcome.output)
    assert walked == [] and not (paths.data_root / "e2").exists()

    # Without named attempts, reevaluate walks only the attempts of tasks still in the study.
    outcome = RUNNER.invoke(cli.app, ["e1", "reevaluate", "--config", str(path)])
    assert outcome.exit_code == 0, outcome.output
    assert walked == [kept.attempt_id]


def test_the_paper_export_omits_excluded_tasks_everywhere(tmp_path: Path) -> None:
    paths, config, digest, _path = _study(tmp_path)
    _declare(paths, config, _document(config, digest))
    loaded = exclusions.load(paths, config, digest)
    full = attempts.schedule(config)
    kept = [item for item in full if item.task in KEPT]
    gone = [item for item in full if item.task not in KEPT]
    # One kept attempt is missing; an excluded task's attempt of an unregistered task would
    # fail the clause-map lookup if it reached it.
    records = [_record(item, "resolved" if item.repeat == 1 else "failed") for item in kept[1:]]
    records += [_record(item) for item in gone]
    records[0]["outcome"], records[0]["nativeOutcome"], records[0]["adjudication"] = (
        "failed",
        "unattributed",
        "r",
    )
    root = _write_ledger(paths, config, records)
    for item in (kept[0], gone[0]):
        (root / "out-of-scope-attempts" / item.attempt_id).mkdir(parents=True)
        (root / "out-of-scope-attempts" / item.attempt_id / "attempt.json").write_text("{}", encoding="utf-8")
    (root / "voided-attempts").mkdir()
    netpool = {"attempts": [kept[0].attempt_id, gone[1].attempt_id]}
    (root / "voided-attempts" / "VOIDED-netpool.json").write_text(json.dumps(netpool), encoding="utf-8")

    out = tmp_path / "export"
    paper_export.export(paths, config, digest, out, exclusions=loaded)
    e1 = json.loads((out / "e1-results.json").read_text(encoding="utf-8"))
    assert e1["scheduledAttempts"] == 2 * 2 * 2
    assert e1["recordedAttempts"] == len(e1["attempts"]) == len(kept) - 1
    assert e1["exclusions"] == loaded.public()
    deviations = e1["deviations"]
    assert (deviations["excludedTasks"], deviations["excludedRecordedAttempts"]) == (2, len(gone))
    assert deviations["outOfScopeAfterAmendment"] == 1
    assert deviations["voidedBeforeAnyModelRequest"]["networkPoolExhausted"] == 1
    assert {item["task"] for item in e1["attempts"]} == {row["task"] for row in e1["perTask"]} == set(KEPT)
    for row in e1["perTask"]:
        cell = [
            item for item in e1["attempts"] if (item["model"], item["task"]) == (row["model"], row["task"])
        ]
        assert row["recorded"] == len(cell) and row["scheduled"] == config.repeats
    # The paper's merge recomputes each summary view from the exported per-task rows.
    for key, view in e1["summary"].items():
        model, kind = key.split("/")
        rows = [row for row in e1["perTask"] if row["model"] == model and row["kind"] == kind]
        assert aggregate._view(rows) == view
    # E0 walks the registry, not the study configuration or its exclusions.
    e0 = json.loads((out / "e0-admission.json").read_text(encoding="utf-8"))
    assert {task["task"] for task in e0["tasks"]} == set(BY_KEY)

    only_m = paper_export._e1(paths, config, digest, loaded, {i.attempt_id for i in gone}, ("m",))
    assert only_m["scheduledAttempts"] == 1 * 2 * 2
    assert only_m["deviations"]["excludedRecordedAttempts"] == sum(item.model == "m" for item in gone)


def test_the_paper_export_refuses_an_e2_selection_that_names_an_excluded_attempt(tmp_path: Path) -> None:
    paths, config, digest, _path = _study(tmp_path)
    _declare(paths, config, _document(config, digest))
    loaded = exclusions.load(paths, config, digest)
    full = attempts.schedule(config)
    kept = next(item for item in full if item.task in KEPT)
    gone = next(item for item in full if item.task == GONE)
    e2_root = paths.data_root / "e2" / config.study_id
    e2_root.mkdir(parents=True)
    selection = {"rule": "none", "eligible": [kept.attempt_id, gone.attempt_id], "selected": []}
    (e2_root / "selection.json").write_text(
        json.dumps(selection | {"successfulControls": {}}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="run e2 select again"):
        paper_export.export(paths, config, digest, tmp_path / "export", exclusions=loaded)
    assert not (tmp_path / "export").exists()

    # A selection recorded without successful controls is still checked and exported.
    (e2_root / "selection.json").write_text(json.dumps(selection), encoding="utf-8")
    with pytest.raises(ValueError, match="run e2 select again"):
        paper_export._e2(paths, config, loaded, {gone.attempt_id})
    selection["eligible"] = [kept.attempt_id]
    (e2_root / "selection.json").write_text(json.dumps(selection), encoding="utf-8")
    assert paper_export._e2(paths, config, loaded, {gone.attempt_id})["selection"] == selection

    selection = {"rule": "none", "eligible": [kept.attempt_id], "selected": [kept.attempt_id]}
    (e2_root / "selection.json").write_text(
        json.dumps(selection | {"successfulControls": {kept.attempt_id: None}}), encoding="utf-8"
    )
    for item in (kept, gone):
        replay = {"attempt": item.attempt_id, "task": item.task, "replay": "original", "score": 0}
        replay |= {"complete": True, "passed": False, "cases": {"case:a": "F"}}
        (e2_root / item.attempt_id / "original").mkdir(parents=True)
        (e2_root / item.attempt_id / "original" / "replay.json").write_text(
            json.dumps(replay), encoding="utf-8"
        )
    result = paper_export._e2(paths, config, loaded, {gone.attempt_id})
    assert [replay["attempt"] for replay in result["replays"]] == [kept.attempt_id]
