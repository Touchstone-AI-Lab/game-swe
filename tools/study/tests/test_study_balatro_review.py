from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from rhenium_study import balatro_review, controls
from rhenium_study.balatro_review import LexError, scan_lua, scan_tree, tokenize

ROOT = Path(__file__).parents[3]
STARTERS = sorted((ROOT / "benchmarks" / "balatro" / "public" / "v02").glob("*/starter"))
FILES = frozenset({"main.lua", "lib/rules.lua"})
ART = "sha256:artifact-one"


def _rules(source: str, files: frozenset[str] = FILES) -> list[str]:
    return [rule for _, rule, _ in scan_lua(source, files)]


def test_comments_and_strings_are_not_code() -> None:
    source = (
        "-- io.open and require in a line comment\n"
        "--[==[ os.execute('rm') and _G ]==]\n"
        "local text = 'require io.open' .. [[load(_G)]] .. \"os.remove\"\n"
        "local n = 0x1F + 3.5e2\n"
    )
    assert _rules(source) == []
    names = [token.value for token in tokenize(source) if token.kind == "name"]
    assert names == ["local", "text", "local", "n"]
    assert [token.line for token in tokenize(source) if token.kind == "number"] == [4, 4]


def test_unterminated_source_is_a_lex_error() -> None:
    for source in ("local s = 'open\n", "--[[ never closed", "local s = [==[ never ]=]"):
        with pytest.raises(LexError):
            tokenize(source)


def test_ordinary_mod_code_passes() -> None:
    source = (
        "local R = assert(SMODS.load_file('lib/rules.lua', id))()\n"
        "local started = os.time()\n"
        "if os and os.clock then started = os.clock() end\n"
        "local t = love.timer.getTime()\n"
        "SMODS.Joker({key = 'growth', calculate = function(self, card, context)\n"
        "  if context.end_of_round then card.ability.extra.growth = card.ability.extra.growth + 2 end\n"
        "end})\n"
        "local previous = G.FUNCS.end_consumeable\n"
        "G.FUNCS.end_consumeable = function(...) return previous(...) end\n"
        "local value = rawget(card.ability, 'extra')\n"
        "local ok, err = pcall(function() error('x') end)\n"
    )
    assert _rules(source) == []


@pytest.mark.parametrize(
    ("source", "rule"),
    [
        ("local f = io.open('x')", "capability"),
        ("os.execute('ls')", "capability"),
        ("os.remove('save')", "capability"),
        ("local o = os", "capability"),
        ("local o = os['execute']", "capability"),
        ("local m = require('socket')", "capability"),
        ("load('return 1')()", "capability"),
        ("loadstring(code)()", "capability"),
        ("dofile('x.lua')", "capability"),
        ("local g = _G['BB_' .. 'SERVER']", "capability"),
        ("setfenv(1, {})", "capability"),
        ("debug.sethook()", "capability"),
        ("local fs = love.filesystem.read('x')", "capability"),
        ("love.update = function() end", "capability"),
        ("function love.draw() end", "capability"),
        ("local s = string.dump(f)", "capability"),
        ("local s = f:dump()", "capability"),
        ("local e = x.getenv('HOME')", "capability"),
        ("local mt = getmetatable('')", "capability"),
        ("G.FUNCS.setup_run = nil", "capability"),
        ("local s = string['du' .. 'mp']", "dynamic-code"),
        ("local l = SMODS['load_file']", "dynamic-code"),
        ("local f = SMODS.load_file(path)", "dynamic-code"),
        ("local f = SMODS.load_file('lib/other.lua')", "dynamic-code"),
        ("local f = SMODS.load_file('..\\\\x.lua')", "dynamic-code"),
        ("local s = SMODS; s.load_file('lib/rules.lua')", "dynamic-code"),
        ("BB_DISPATCHER.register({})", "harness"),
        ("local n = POC_NONCE", "harness"),
        ("local r = call('poc.runtime')", "harness"),
        ("local d = 'mods/poc_guard/guard.lua'", "harness"),
    ],
)
def test_capabilities_and_harness_references_are_found(source: str, rule: str) -> None:
    assert rule in _rules(source)


def _mod(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def test_tree_reports_every_file_and_rejects_other_types(tmp_path: Path) -> None:
    root = _mod(
        tmp_path / "starter",
        {
            "main.lua": "local R = assert(SMODS.load_file('lib/rules.lua'))()\n",
            "lib/rules.lua": "return {}\n",
            "mod.json": json.dumps({"id": "x", "dependencies": ["Steamodded"]}),
            "lovely.toml": "[manifest]\n",
        },
    )
    report = scan_tree(root)
    assert [f["name"] for f in report["files"]] == ["lib/rules.lua", "lovely.toml", "main.lua", "mod.json"]
    assert [(f["file"], f["rule"]) for f in report["findings"]] == [("lovely.toml", "file")]

    (root / "lovely.toml").unlink()
    (root / "mod.json").write_text(json.dumps({"dependencies": ["BalatroBot"]}), encoding="utf-8")
    assert [(f["file"], f["rule"]) for f in scan_tree(root)["findings"]] == [("mod.json", "harness")]
    (root / "mod.json").write_text("{", encoding="utf-8")
    (root / "main.lua").write_text("local s = 'open\n", encoding="utf-8")
    assert sorted((f["file"], f["rule"]) for f in scan_tree(root)["findings"]) == [
        ("main.lua", "file"),
        ("mod.json", "file"),
    ]


@pytest.mark.parametrize("starter", STARTERS, ids=[path.parent.name for path in STARTERS])
def test_every_public_starter_passes(starter: Path) -> None:
    assert scan_tree(starter)["findings"] == []


class FakeOperator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, list[str]]] = []

    def __call__(self, operation: str, submission: Path, task: str, extra: list[str]) -> dict[str, Any]:
        self.calls.append((operation, task, extra))
        if operation == "inspect":
            files = sorted(
                p.relative_to(submission / "starter").as_posix()
                for p in (submission / "starter").rglob("*")
                if p.is_file()
            )
            return {"submissionSha256": "seal-" + task, "files": files}
        return {"review_recorded": True}


def _kit(tmp_path: Path, sources: dict[str, str]) -> tuple[Path, dict[str, Any]]:
    kit = tmp_path / "kit"
    entries = []
    for task, source in sources.items():
        attempt = f"m--{task}--r1"
        submission = kit / "attempts" / attempt / "submission"
        _mod(submission / "starter", {"main.lua": source})
        (submission / "EXAM.md").write_text("exam\n", encoding="utf-8")
        entries.append(
            {
                "attemptId": attempt,
                "task": f"balatro/core/{task}",
                "submissionDigest": controls.tree_digest(submission),
                "submission": f"attempts/{attempt}/submission",
            }
        )
    entries.append(
        {
            "attemptId": "m--other--r1",
            "task": "palworld/core/other",
            "submissionDigest": "x",
            "submission": "attempts/m--other--r1/submission",
        }
    )
    manifest = {"studyId": "s", "configDigest": "d", "attempts": entries}
    (kit / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return kit, manifest


def test_only_a_clean_submission_is_sealed(tmp_path: Path) -> None:
    kit, manifest = _kit(tmp_path, {"growth-v2": "return 1\n", "shop": "local f = io.open('x')\n"})
    operator = FakeOperator()
    reports = balatro_review.review_kit(kit, manifest, operator, ART)
    assert [r["decision"] for r in reports] == [balatro_review.SEALED, balatro_review.NEEDS_OPERATOR]
    assert operator.calls == [
        ("inspect", "growth-v2", []),
        ("review", "growth-v2", ["--source-reviewed", "--reviewed-sha", "seal-growth-v2"]),
        ("inspect", "shop", []),
    ]
    stored = json.loads((kit / "attempts" / "m--shop--r1" / "auto-review.json").read_text(encoding="utf-8"))
    assert stored["policy"] == balatro_review.POLICY and stored["findings"][0]["file"] == "main.lua"
    assert stored["artifactIdentity"] == ART

    # A sealed attempt is kept; the flagged one is scanned again.
    again = FakeOperator()
    balatro_review.review_kit(kit, manifest, again, ART)
    assert again.calls == [("inspect", "shop", [])]
    assert balatro_review.kit_manifest(kit, "s", "d") == manifest
    with pytest.raises(ValueError, match="different study"):
        balatro_review.kit_manifest(kit, "s", "other")


def test_a_changed_submission_or_seal_set_is_refused(tmp_path: Path) -> None:
    kit, manifest = _kit(tmp_path, {"growth-v2": "return 1\n"})
    (kit / "attempts" / "m--growth-v2--r1" / "submission" / "starter" / "main.lua").write_text("return 2\n")
    with pytest.raises(ValueError, match="does not match its digest"):
        balatro_review.review_kit(kit, manifest, FakeOperator(), ART)

    kit, manifest = _kit(tmp_path / "second", {"growth-v2": "return 1\n"})

    def narrow(operation: str, submission: Path, task: str, extra: list[str]) -> dict[str, Any]:
        return {"submissionSha256": "seal", "files": []}

    with pytest.raises(ValueError, match="other files"):
        balatro_review.review_kit(kit, manifest, narrow, ART)


def test_file_sets_are_compared_as_names(tmp_path: Path) -> None:
    # Path order puts a/b.lua first, name order a-b/x.lua: the comparison must not care.
    kit, manifest = _kit(tmp_path, {"growth-v2": "return 1\n"})
    starter = kit / "attempts" / "m--growth-v2--r1" / "submission" / "starter"
    _mod(starter, {"a-b/x.lua": "return 1\n", "a/b.lua": "return 1\n"})
    manifest["attempts"][0]["submissionDigest"] = controls.tree_digest(starter.parent)
    report = balatro_review.review_kit(kit, manifest, FakeOperator(), ART)[0]
    assert report["decision"] == balatro_review.SEALED


def test_evaluation_runs_sealed_attempts_once_and_stops_at_an_incomplete_run(tmp_path: Path) -> None:
    kit, manifest = _kit(
        tmp_path, {"a": "return 1\n", "b": "return 1\n", "c": "return 1\n", "d": "os.exit()\n"}
    )
    balatro_review.review_kit(kit, manifest, FakeOperator(), ART)
    outcomes = {"balatro/core/a": True, "balatro/core/b": None, "balatro/core/c": True}
    evaluated: list[str] = []

    def evaluator(task: str, submission: Path) -> dict[str, Any]:
        evaluated.append(task)
        passed = outcomes[task]
        return {"taskKey": task, "result": {"complete": passed is not None, "passed": bool(passed)}}

    runs = balatro_review.evaluate_sealed(kit, manifest, evaluator, ART)
    assert runs == [
        {"attemptId": "m--a--r1", "complete": True, "passed": True},
        {"attemptId": "m--b--r1", "complete": False, "passed": None},
    ]
    assert evaluated == ["balatro/core/a", "balatro/core/b"]
    assert (kit / "attempts" / "m--b--r1" / "result-1.json").is_file()

    # The next batch skips both results and never evaluates the unsealed attempt.
    outcomes["balatro/core/b"] = True
    evaluated.clear()
    assert balatro_review.evaluate_sealed(kit, manifest, evaluator, ART) == [
        {"attemptId": "m--c--r1", "complete": True, "passed": True}
    ]
    assert evaluated == ["balatro/core/c"]


def test_a_new_artifact_reseals_only_unevaluated_attempts(tmp_path: Path) -> None:
    # A halt replaces the artifact, and the plugin keeps seals in the artifact's own state.
    kit, manifest = _kit(tmp_path, {"a": "return 1\n", "b": "return 1\n"})
    balatro_review.review_kit(kit, manifest, FakeOperator(), ART)
    balatro_review.evaluate_sealed(
        kit, manifest, lambda task, sub: {"result": {"complete": task.endswith("/a"), "passed": False}}, ART
    )
    calls: list[str] = []

    def evaluator(task: str, submission: Path) -> dict[str, Any]:
        calls.append(task)
        return {"result": {"complete": True, "passed": True}}

    # Nothing is left to evaluate on the halted artifact, and nothing sealed elsewhere runs.
    assert balatro_review.evaluate_sealed(kit, manifest, evaluator, "sha256:artifact-two") == []
    operator = FakeOperator()
    reports = balatro_review.review_kit(kit, manifest, operator, "sha256:artifact-two")
    assert [r["artifactIdentity"] for r in reports] == [ART, ART]
    assert operator.calls == []  # both have a result: an evaluated attempt is never sealed again

    kit, manifest = _kit(tmp_path / "second", {"a": "return 1\n", "b": "return 1\n"})
    balatro_review.review_kit(kit, manifest, FakeOperator(), ART)
    (kit / "attempts" / "m--a--r1" / "result-1.json").write_text("{}\n", encoding="utf-8")
    operator = FakeOperator()
    reports = balatro_review.review_kit(kit, manifest, operator, "sha256:artifact-two")
    assert [r["artifactIdentity"] for r in reports] == [ART, "sha256:artifact-two"]
    assert [call[:2] for call in operator.calls] == [("inspect", "b"), ("review", "b")]
    assert balatro_review.evaluate_sealed(kit, manifest, evaluator, "sha256:artifact-two") == [
        {"attemptId": "m--b--r1", "complete": True, "passed": True}
    ]
    assert calls == ["balatro/core/b"]


def test_artifact_identity_reads_a_verify_output(tmp_path: Path) -> None:
    path = tmp_path / "verify.json"
    path.write_text(json.dumps({"ready": True, "artifact": {"identity": "sha256:abc"}}), encoding="utf-8")
    assert balatro_review.artifact_identity(path) == "sha256:abc"
    path.write_text(json.dumps({"identity": "sha256:def"}), encoding="utf-8")
    assert balatro_review.artifact_identity(path) == "sha256:def"
    path.write_text(json.dumps({"ready": False, "artifact": None}), encoding="utf-8")
    with pytest.raises(ValueError, match="no runtime artifact identity"):
        balatro_review.artifact_identity(path)
