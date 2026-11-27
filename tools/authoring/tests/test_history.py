from __future__ import annotations

import io
import json
import tarfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import BaseModel, HttpUrl
from rhenium_authoring.history.agent import (
    AgentExhausted,
    AgentStep,
    RepositoryTools,
    native_tool_call,
    run_agent,
)
from rhenium_authoring.history.checkout import CheckoutError, kept, unpack
from rhenium_authoring.history.discovery import HistoryDiscovery, touches_frozen_build
from rhenium_authoring.history.engine import hunk_reverts, judge, tamper
from rhenium_authoring.history.leaks import exam_leaks
from rhenium_authoring.history.minecraft_build import (
    BuildRejected,
    frozen_paths,
    infer_build,
    is_test_path,
    reference_tree,
)
from rhenium_authoring.history.minecraft_checks import static_findings
from rhenium_authoring.history.minecraft_pack import HistoryTask, case_contracts, published_task_id, stage
from rhenium_authoring.history.models import (
    AuthoredTask,
    BuildProbe,
    CaseContract,
    HistoryFix,
    TriageDecision,
)
from rhenium_authoring.history.study_controls import clause_map
from rhenium_authoring.sources.github import GitHubSource
from rhenium_authoring.state import AuthoringStore

ROOT = Path(__file__).resolve().parents[3]
CORE_DEFAULTS = ("build.gradle", "settings.gradle", "gradle", "gradlew", "pom.xml", "src/test")
BASE_SHA = "a" * 40
FIX_SHA = "b" * 40

# -- discovery ------------------------------------------------------------------


def _pull(number: int, title: str, sha: str, *, merged: bool = True, login: str = "dev") -> dict[str, Any]:
    return {
        "number": number,
        "title": title,
        "body": "",
        "merge_commit_sha": sha,
        "merged_at": "2026-01-01T00:00:00Z" if merged else None,
        "user": {"login": login},
    }


def _commit(sha: str, files: list[dict[str, Any]], message: str = "Fix things") -> dict[str, Any]:
    return {"sha": sha, "parents": [{"sha": BASE_SHA}], "files": files, "commit": {"message": message}}


def _file(name: str, changes: int = 4) -> dict[str, Any]:
    return {"filename": name, "additions": changes, "deletions": 0, "patch": "@@ -1 +1 @@\n-a\n+b"}


def _github(handler: Callable[[httpx.Request], httpx.Response]) -> GitHubSource:
    client = httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(handler))
    return GitHubSource(None, client=client)


def test_discovery_walks_pulls_filters_fixes_and_advances_the_cursor(tmp_path: Path) -> None:
    good = "1" * 40
    frozen = "2" * 40
    big = "3" * 40
    commits = {
        good: _commit(good, [_file("src/main/java/a/Cmd.java"), _file("src/test/java/a/CmdTest.java")]),
        frozen: _commit(frozen, [_file("src/main/java/a/Cmd.java"), _file("build.gradle")]),
        big: _commit(big, [_file("src/main/java/a/Cmd.java", changes=400)]),
    }
    pages: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/pulls"):
            page = int(request.url.params["page"])
            pages.append(page)
            if page == 1:
                return httpx.Response(
                    200,
                    json=[
                        _pull(1, "Fix /cmd crash", good),
                        _pull(2, "Fix build", frozen),
                        _pull(3, "Fix everything", big),
                        _pull(4, "Add feature", "4" * 40),
                        _pull(5, "Fix unmerged", "5" * 40, merged=False),
                        _pull(6, "fix deps", "6" * 40, login="renovate[bot]"),
                    ],
                )
            return httpx.Response(200, json=[])
        if path.endswith("/commits"):
            return httpx.Response(200, json=[])
        sha = path.rsplit("/", 1)[-1]
        return httpx.Response(200, json=commits[sha])

    store = AuthoringStore(tmp_path / "authoring.sqlite")
    discovery = HistoryDiscovery(_github(handler), store, pages_per_run=2)
    fixes = list(
        discovery.fixes("o/plugin", "https://github.com/o/plugin", "MIT", "minecraft", limit=5, exclude=set())
    )
    assert [fix.fixed_sha for fix in fixes] == [good]
    fix = fixes[0]
    assert fix.base_sha == BASE_SHA and fix.pull_number == 1 and fix.candidate_id == f"plugin-{good[:10]}"
    assert discovery.stats.rejected["changes frozen build files"] == 1
    assert discovery.stats.rejected["fix too large"] == 1
    assert discovery.stats.rejected["not described as a fix"] == 1
    assert discovery.stats.rejected["not merged"] == 1 and discovery.stats.rejected["bot author"] == 1
    # The short first page exhausts the pull history; a later run never re-reads it.
    assert store.history_cursor("o/plugin", "pulls") == (2, True)
    assert list(discovery._walk("o/plugin", "pulls")) == [] and pages == [1]


def test_discovery_skips_squashed_pull_commits_and_used_fixes(tmp_path: Path) -> None:
    direct = "7" * 40
    used = "8" * 40

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/pulls"):
            return httpx.Response(200, json=[])
        if path.endswith("/commits"):
            return httpx.Response(
                200,
                json=[
                    {"sha": "9" * 40, "parents": [{}], "commit": {"message": "Fix parser (#12)"}},
                    {"sha": used, "parents": [{}], "commit": {"message": "fix crash"}},
                    {"sha": direct, "parents": [{}], "commit": {"message": "Fix NPE on reload\n\ndetails"}},
                    {"sha": "a1" * 20, "parents": [{}, {}], "commit": {"message": "Merge fix"}},
                ],
            )
        return httpx.Response(200, json=_commit(direct, [_file("src/main/java/a/B.java")], "Fix NPE"))

    store = AuthoringStore(tmp_path / "authoring.sqlite")
    discovery = HistoryDiscovery(_github(handler), store)
    fixes = list(
        discovery.fixes(
            "o/plugin",
            "https://github.com/o/plugin",
            "MIT",
            "minecraft",
            limit=5,
            exclude={f"https://github.com/o/plugin@{used}"},
        )
    )
    assert [(fix.origin, fix.fixed_sha, fix.title) for fix in fixes] == [
        ("commit", direct, "Fix NPE on reload")
    ]
    assert fixes[0].commit_message == "details"
    assert discovery.stats.rejected["squash of a pull request"] == 1


def test_plugin_layout_accepts_multi_module_java_and_rejects_kotlin(tmp_path: Path) -> None:
    trees = {
        "java": ["spigot/src/main/resources/plugin.yml", "build.gradle", "spigot/src/main/java/A.java"],
        "kotlin": ["src/main/resources/plugin.yml", "build.gradle.kts", "src/main/kotlin/A.kt", "B.kt"],
        "none": ["README.md", "build.gradle", "src/main/java/A.java"],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        name = request.url.path.split("/")[3]
        return httpx.Response(200, json={"tree": [{"type": "blob", "path": path} for path in trees[name]]})

    discovery = HistoryDiscovery(_github(handler), AuthoringStore(tmp_path / "a.sqlite"))
    assert discovery.plugin_layout("o/java", "main") is True
    assert discovery.plugin_layout("o/kotlin", "main") is False
    assert discovery.plugin_layout("o/none", "main") is False


@pytest.mark.parametrize(
    ("path", "frozen"),
    [
        ("pom.xml", True),
        ("spigot/build.gradle", True),
        ("gradle/wrapper/gradle-wrapper.properties", True),
        (".mvn/wrapper/maven-wrapper.properties", True),
        ("src/main/java/a/Build.java", False),
    ],
)
def test_frozen_build_paths(path: str, frozen: bool) -> None:
    assert touches_frozen_build(path) is frozen


# -- checkout -----------------------------------------------------------------------


def _tarball(entries: list[tuple[str, bytes | None, str]]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as bundle:
        for name, data, kind in entries:
            info = tarfile.TarInfo(name)
            if kind == "link":
                info.type = tarfile.SYMTYPE
                info.linkname = "/etc/passwd"
                bundle.addfile(info)
            elif kind == "dir":
                info.type = tarfile.DIRTYPE
                bundle.addfile(info)
            else:
                assert data is not None
                info.size = len(data)
                bundle.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def test_unpack_keeps_sources_and_drops_links_ci_build_output_and_archives(tmp_path: Path) -> None:
    archive = _tarball(
        [
            ("repo-sha/", None, "dir"),
            ("repo-sha/src/main/java/A.java", b"class A {}", "file"),
            ("repo-sha/gradle/wrapper/gradle-wrapper.jar", b"PK", "file"),
            ("repo-sha/libs/private.jar", b"PK", "file"),
            ("repo-sha/.github/workflows/ci.yml", b"on: push", "file"),
            ("repo-sha/build/classes/A.class", b"\xca\xfe", "file"),
            ("repo-sha/link", None, "link"),
        ]
    )
    summary = unpack(archive, tmp_path / "tree")
    files = sorted(
        path.relative_to(tmp_path / "tree").as_posix()
        for path in (tmp_path / "tree").rglob("*")
        if path.is_file()
    )
    assert files == ["gradle/wrapper/gradle-wrapper.jar", "src/main/java/A.java"]
    assert summary["files"] == 2 and summary["dropped"] == 4


def test_unpack_rejects_escaping_paths(tmp_path: Path) -> None:
    with pytest.raises(CheckoutError, match="escaping"):
        unpack(_tarball([("repo/../../evil", b"x", "file")]), tmp_path / "tree")


def test_kept_rules() -> None:
    from pathlib import PurePosixPath

    assert kept(PurePosixPath(".mvn/wrapper/maven-wrapper.jar"))
    assert not kept(PurePosixPath("module/target/app.jar"))
    assert not kept(PurePosixPath(".idea/workspace.xml"))


# -- build inference ----------------------------------------------------------------


def _write(root: Path, files: dict[str, str]) -> Path:
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


GRADLE_PLUGIN = {
    "LICENSE": "MIT",
    "gradlew": "#!/bin/sh\n",
    "gradle/wrapper/gradle-wrapper.properties": "distributionUrl=x\n",
    "settings.gradle": "include 'api', 'spigot'\n",
    "build.gradle": "plugins { id 'com.gradleup.shadow' }\n",
    "spigot/build.gradle": "dependencies { compileOnly 'io.papermc.paper:paper-api:1.21.4-R0.1-SNAPSHOT' }\n",
    "spigot/src/main/resources/plugin.yml": "name: Sample\nmain: a.Main\n",
    "spigot/src/main/java/a/Main.java": "class Main {}\n",
    "spigot/src/test/java/a/MainTest.java": "class MainTest {}\n",
}


def test_infer_gradle_multi_module_build(tmp_path: Path) -> None:
    guess = infer_build(_write(tmp_path, GRADLE_PLUGIN), core_defaults=CORE_DEFAULTS)
    assert (guess.tool, guess.wrapper, guess.assemble, guess.test) == ("gradle", True, "shadowJar", "test")
    assert guess.plugin_name == "Sample" and guess.plugin_root == "spigot"
    assert guess.paper_api == "1.21.4-R0.1-SNAPSHOT" and guess.license_file == "LICENSE"
    assert "spigot/build.gradle" in guess.frozen_paths and "spigot/src/test" in guess.frozen_paths


def test_infer_maven_without_wrapper_pins_the_maven_release(tmp_path: Path) -> None:
    tree = _write(
        tmp_path,
        {
            "LICENSE.md": "MIT",
            "pom.xml": "<artifactId>paper-api</artifactId>\n<version>1.20.4-R0.1-SNAPSHOT</version>"
            "<maven.compiler.release>17</maven.compiler.release>",
            "src/main/resources/plugin.yml": "name: 'Exporter'\n",
        },
    )
    guess = infer_build(tree, core_defaults=CORE_DEFAULTS)
    assert (guess.tool, guess.wrapper, guess.tool_version, guess.test) == ("maven", False, "3.9.11", None)
    assert guess.java_release == 17 and guess.plugin_root == ""


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"build.gradle": "plugins { id 'io.papermc.paperweight.userdev' }"}, "paperweight"),
        ({"gradlew": None}, "wrapper"),
        ({"LICENSE": None}, "licence"),
        ({"spigot/src/main/resources/plugin.yml": None}, "plugin.yml"),
    ],
)
def test_infer_build_rejections(tmp_path: Path, change: dict[str, str | None], message: str) -> None:
    tree = _write(tmp_path, GRADLE_PLUGIN)
    for relative, text in change.items():
        if text is None:
            (tree / relative).unlink()
        else:
            (tree / relative).write_text(text)
    with pytest.raises(BuildRejected, match=message):
        infer_build(tree, core_defaults=CORE_DEFAULTS)


def test_frozen_paths_add_every_sub_project(tmp_path: Path) -> None:
    tree = _write(tmp_path, {"pom.xml": "", "Plugin/pom.xml": "", "Plugin/src/test/java/A.java": ""})
    paths = frozen_paths(tree, core_defaults=("pom.xml", "src/test"))
    assert paths == ("pom.xml", "src/test", "Plugin/pom.xml", "Plugin/src/test")


def test_reference_tree_applies_main_changes_and_skips_tests(tmp_path: Path) -> None:
    base = _write(tmp_path / "base", {"src/main/java/A.java": "old", "src/test/java/T.java": "old test"})
    fixed = _write(tmp_path / "fixed", {"src/main/java/A.java": "new", "src/test/java/T.java": "new test"})
    applied = reference_tree(
        base, fixed, ("src/main/java/A.java", "src/test/java/T.java"), tmp_path / "reference"
    )
    assert applied == ["src/main/java/A.java"]
    assert (tmp_path / "reference/src/main/java/A.java").read_text() == "new"
    assert (tmp_path / "reference/src/test/java/T.java").read_text() == "old test"
    assert is_test_path("module/src/test/java/T.java") and not is_test_path("src/main/java/test/X.java")
    (fixed / "src/main/java/A.java").unlink()
    with pytest.raises(BuildRejected, match="deletes"):
        reference_tree(base, fixed, ("src/main/java/A.java",), tmp_path / "again")


# -- agent loop -----------------------------------------------------------------------


class _Answer(BaseModel):
    answer: str


class _ScriptedClient:
    def __init__(self, steps: list[dict[str, Any]]):
        self.steps = steps
        self.histories: list[list[dict[str, str]]] = []

    def complete(
        self,
        output: type[Any],
        *,
        role: str,
        payload: dict[str, object],
        history: Any = None,
        pipeline: str = "clean-room",
        salvage: Any = None,
    ) -> Any:
        assert salvage is not None
        del role, payload
        assert pipeline == "project-history"
        self.histories.append(list(history or []))
        return output.model_validate(self.steps.pop(0))


def test_agent_reads_the_tree_and_retries_a_rejected_finish(tmp_path: Path) -> None:
    tree = _write(tmp_path / "base", {"src/A.java": "class A {\n  int x;\n}\n"})
    client = _ScriptedClient(
        [
            {"tool": "list_dir", "arguments": {"tree": "base", "path": "src"}},
            {"tool": "grep", "arguments": {"tree": "base", "pattern": "int x"}},
            {"tool": "read_file", "arguments": {"tree": "base", "path": "../../etc/passwd"}},
            {"tool": "finish", "arguments": {"wrong": 1}},
            {"tool": "finish", "arguments": {"answer": "bad"}},
            {"tool": "finish", "arguments": {"answer": "good"}},
        ]
    )
    result = run_agent(
        client,  # type: ignore[arg-type]
        _Answer,
        role="test",
        brief={},
        tools=RepositoryTools({"base": tree}),
        check=lambda value: [] if value.answer == "good" else ["answer must be good"],
        transcript=tmp_path / "transcript.json",
    )
    assert result.answer == "good"
    observations = [turn["content"] for turn in client.histories[-1] if turn["role"] == "user"]
    assert observations[0].startswith("src:\nA.java")
    assert observations[1] == "src/A.java:2: int x;"
    assert observations[2].startswith("error: paths must stay inside the tree")
    assert observations[3].startswith("finish rejected by the schema")
    assert observations[4] == "finish rejected: answer must be good"
    assert json.loads((tmp_path / "transcript.json").read_text())


def test_agent_hides_the_fix_from_roles_without_it_and_stops_at_the_budget(tmp_path: Path) -> None:
    tree = _write(tmp_path / "base", {"A.java": ""})
    tools = RepositoryTools({"base": tree})
    assert tools.call(AgentStep(tool="show_fix")) == "error: show_fix is not available to this role"
    client = _ScriptedClient([{"tool": "list_dir", "arguments": {}} for _ in range(3)])
    with pytest.raises(AgentExhausted):
        run_agent(client, _Answer, role="t", brief={}, tools=tools, max_turns=3)  # type: ignore[arg-type]
    assert client.histories[-1][-1]["content"].startswith("Turn budget exhausted")


# -- exam leaks and suite checks ----------------------------------------------------


def _fix(**overrides: Any) -> HistoryFix:
    values: dict[str, Any] = {
        "game_id": "minecraft",
        "repository": "o/plugin",
        "repository_url": HttpUrl("https://github.com/o/plugin"),
        "license_spdx": "MIT",
        "base_sha": BASE_SHA,
        "fixed_sha": FIX_SHA,
        "origin": "pull",
        "pull_number": 7,
        "title": "Clamp help page numbers to the available range",
        "description": "Page zero threw an exception because the index went negative",
        "changed_files": ("src/main/java/a/HelpCommand.java",),
        "patch": "+  int page = Math.max(1, Math.min(requested, maxPage)); // clamp into the real range",
        "changed_lines": 2,
    }
    values.update(overrides)
    return HistoryFix(**values)


def test_published_task_ids_name_the_defect_and_never_the_commit() -> None:
    fix = _fix()
    assert fix.candidate_id.endswith(FIX_SHA[:10])
    assert published_task_id(fix, "plugin-help-page-bounds") == "plugin-help-page-bounds"
    for bad in ("Plugin-Help", "help", "plugin--help-page", f"plugin-{FIX_SHA[:7]}", f"x-{BASE_SHA[:9]}"):
        with pytest.raises(ValueError):
            published_task_id(fix, bad)


@pytest.mark.parametrize(
    ("exam", "finding"),
    [
        ("See https://github.com/o/plugin for details.", "URL"),
        ("Regressed in 1a2b3c4d.", "commit hash"),
        ("Reported in #42.", "issue or pull-request number"),
        ("The upstream fix changes one line.", "upstream fix"),
        ("Title: clamp help page numbers to the available range now", "title"),
        ("On a server, page zero threw an exception because the index went negative.", "commit text"),
        ("int page = Math.max(1, Math.min(requested, maxPage)); // clamp into the real range", "diff"),
    ],
)
def test_exam_leak_gate(exam: str, finding: str) -> None:
    assert any(finding in item for item in exam_leaks(exam, _fix()))


def test_exam_leak_gate_accepts_a_maintainer_style_exam() -> None:
    exam = (
        "`plugin/` is the Sample Paper plugin at an upstream commit. Running `/sample help 0` from "
        "the console prints an internal error; pages past the end print an empty page."
    )
    assert exam_leaks(exam, _fix()) == []


def _authored(**overrides: Any) -> AuthoredTask:
    suite = (
        "import io.gamecodebench.harness.*;\n"
        "public final class SampleSuite implements GcbSuite {\n"
        '  @GcbCase("plugin is enabled") public void enabled() {}\n'
        '  @GcbCase(value = "page zero shows the first page", order = 1) public void zero() {}\n'
        '  @GcbCase("valid pages keep working") public void valid() {}\n'
        "}\n"
    )
    values: dict[str, Any] = {
        "title": "Sample: help pager crashes on page zero",
        "summary": "Repair the help pager so out-of-range pages clamp to a real page.",
        "exam": "# Sample\n\n## Context\n\n" + "x " * 120,
        "suite": {"SampleSuite.java": suite},
        "cases": (
            CaseContract(case="plugin is enabled", role="sentinel", public_report="plugin loads"),
            CaseContract(case="page zero shows the first page", role="target", public_report="page 0 -> 1"),
            CaseContract(case="valid pages keep working", role="preserved", public_report="valid pages"),
        ),
        "notes": "## Defect\n\n" + "notes " * 30,
    }
    values.update(overrides)
    return AuthoredTask(**values)


def test_static_suite_checks_match_cases_and_annotations() -> None:
    assert static_findings(_authored()) == []
    broken = _authored(
        suite={
            "Other.java": 'public class SampleSuite implements GcbSuite { @GcbCase("extra") void x() '
            "{ System.exit(1); } }"
        }
    )
    findings = static_findings(broken)
    assert any("must live in SampleSuite.java" in item for item in findings)
    assert any("exit the JVM" in item for item in findings)
    assert any("'plugin is enabled' must be annotated exactly once" in item for item in findings)
    assert any("@GcbCase('extra') is not listed" in item for item in findings)


def test_authored_task_requires_one_sentinel_and_a_target() -> None:
    with pytest.raises(ValueError, match="sentinel"):
        _authored(
            cases=(
                CaseContract(case="first case here", role="target", public_report="x"),
                CaseContract(case="second case here", role="preserved", public_report="x"),
                CaseContract(case="third case here", role="preserved", public_report="x"),
            )
        )


# -- engine judgement and mechanical controls ----------------------------------------


def _result(outcomes: dict[str, bool], *, complete: bool = True) -> dict[str, Any]:
    return {
        "complete": complete,
        "passed": complete and all(outcomes.values()),
        "runtime": {"caseOutcomes": outcomes if complete else {}},
    }


CASES = {"sentinel", "target", "kept", "unit"}


@pytest.mark.parametrize(
    ("kind", "failed", "admissible"),
    [
        ("starter", {"target"}, True),
        ("starter", {"target", "kept"}, False),
        ("reference", set(), True),
        ("reference", {"kept"}, False),
        ("target-negative", {"target"}, True),
        ("target-negative", {"unit"}, False),
        ("compat-negative", {"kept"}, True),
        ("compat-negative", {"kept", "target"}, False),
        ("compat-negative", set(), False),
    ],
)
def test_judge_applies_the_admission_rules(kind: str, failed: set[str], admissible: bool) -> None:
    result = _result({name: name not in failed for name in CASES})
    ok, _reason, observed = judge(kind, result, cases=CASES, targets={"target"}, preserved={"kept", "unit"})
    assert ok is admissible and set(observed) == failed


def test_judge_rejects_incomplete_or_mismatched_case_sets() -> None:
    assert (
        judge("reference", _result({}, complete=False), cases=CASES, targets=set(), preserved=set())[0]
        is False
    )
    partial = _result({"sentinel": True})
    assert "differs" in judge("reference", partial, cases=CASES, targets=set(), preserved=set())[1]


def test_hunk_reverts_undo_one_hunk_each(tmp_path: Path) -> None:
    base = _write(tmp_path / "base", {"A.java": "a\nb\nc\nd\ne\nf\ng\n"})
    reference = _write(tmp_path / "ref", {"A.java": "a\nB\nc\nd\ne\nF\ng\n"})
    variants = hunk_reverts(base, reference, ["A.java"])
    assert variants == [{"A.java": "a\nb\nc\nd\ne\nF\ng\n"}, {"A.java": "a\nB\nc\nd\ne\nf\ng\n"}]
    single = _write(tmp_path / "single", {"A.java": "a\nB\nc\nd\ne\nf\ng\n"})
    assert hunk_reverts(base, single, ["A.java"]) == []


def test_tamper_breaks_build_files_and_deletes_one_test(tmp_path: Path) -> None:
    tree = _write(tmp_path, {"pom.xml": "<project/>", "src/test/java/T.java": "class T {}", "README": "x"})
    changes = tamper(tree, ("pom.xml", "src/test", "gradle"))
    assert changes["src/test/java/T.java"] is None
    assert str(changes["pom.xml"]).endswith("THIS IS NOT A BUILD FILE\n")
    assert set(changes) == {"pom.xml", "src/test/java/T.java"}


# -- pack writing ------------------------------------------------------------------------


def _task(tmp_path: Path) -> HistoryTask:
    base = _write(
        tmp_path / "base", {**GRADLE_PLUGIN, "spigot/src/main/java/a/Help.java": "class Help { }\n"}
    )
    reference = _write(
        tmp_path / "reference",
        {**GRADLE_PLUGIN, "spigot/src/main/java/a/Help.java": "class Help { int p; }\n"},
    )
    probe = BuildProbe(
        tool="gradle",
        wrapper=True,
        assemble="shadowJar",
        test="test",
        artifact="spigot/build/libs/Sample.jar",
        frozen_paths=(
            "build.gradle",
            "settings.gradle",
            "gradle",
            "gradlew",
            "spigot/build.gradle",
            "src/test",
            "spigot/src/test",
        ),
        plugin_name="Sample",
        license_file="LICENSE",
        paper_api="1.21.4-R0.1-SNAPSHOT",
        unit_cases=("a.MainTest.works()",),
    )
    triage = TriageDecision(reproducible=True, reason="console command", entry_points=("/sample help",))
    return HistoryTask(
        _fix(), probe, triage, _authored(), base, reference, ["spigot/src/main/java/a/Help.java"]
    )


def test_staged_pack_loads_through_the_minecraft_catalog(tmp_path: Path) -> None:
    from rhenium_minecraft.catalog import MinecraftCatalog

    task = _task(tmp_path)
    pack = stage(tmp_path / "stage", ROOT, task)
    catalog = MinecraftCatalog.load(pack)
    (loaded,) = catalog.tasks
    assert catalog.id == "rhenium-minecraft-history-v1" and loaded.id == task.task_id
    assert loaded.upstream is not None and loaded.upstream.fix_commit == FIX_SHA
    assert loaded.server_cases == task.authored.server_cases and loaded.unit_cases == task.probe.unit_cases
    harbor = pack / "private" / "harbor" / task.task_id
    assert (
        harbor / "solution/after/spigot/src/main/java/a/Help.java"
    ).read_text() == "class Help { int p; }\n"
    assert (harbor / "tests/suite/SampleSuite.java").is_file()
    assert 'content_reference_pack = "rhenium-minecraft-history-v1"' in (harbor / "task.toml").read_text()
    assert json.loads((pack / "runtimes.json").read_text())["task_bindings"] == {
        task.task_id: ["paper-1.21.11-132-history"]
    }
    assert (
        case_contracts(task).splitlines()[1]
        == "a.MainTest.works()\tunit\tpreserved\tupstream unit test must keep passing"
    )


def test_clause_map_draft_is_valid_for_the_study_tooling(tmp_path: Path) -> None:
    clausemap = pytest.importorskip("rhenium_study.clausemap")
    document = clause_map(_task(tmp_path))
    parsed = clausemap.ClauseMap.model_validate(document)
    assert parsed.case_ids("target") == ["server:page zero shows the first page"]
    assert "unit:a.MainTest.works()" in parsed.case_ids("preserved")


@pytest.mark.parametrize(
    ("content", "step"),
    [
        (
            "I'll start by reading the upstream fix.\n\n<\uff5cDSML\uff5c calls>\n"
            '<\uff5cDSML\uff5c invoke name="show_fix">\n\n</\uff5cDSML\uff5c invoke>\n'
            "</\uff5cDSML\uff5c calls>",
            {"tool": "show_fix", "arguments": {}},
        ),
        (
            '<|DSML| invoke name="list_dir">\n<|DSML| parameter name="arguments" string="false">'
            '{"path": "spigot/src", "tree": "base"}</|DSML| parameter>\n</|DSML| invoke>',
            {"tool": "list_dir", "arguments": {"path": "spigot/src", "tree": "base"}},
        ),
        (
            '<|DSML| invoke name="grep"><|DSML| parameter name="pattern" string="true">a"b</|DSML| parameter>'
            '<|DSML| parameter name="tree" string="true">base</|DSML| parameter></|DSML| invoke>',
            {"tool": "grep", "arguments": {"pattern": 'a"b', "tree": "base"}},
        ),
    ],
)
def test_native_tool_markup_is_translated_into_a_step(content: str, step: dict[str, Any]) -> None:
    translated = native_tool_call(content)
    assert translated is not None and json.loads(translated) == step
    assert AgentStep.model_validate_json(translated).tool == step["tool"]


@pytest.mark.parametrize(
    "content",
    [
        '<|DSML| calls>\n<|DSML| invoke name="read_file","arguments":'
        '{"tree":"base","path":"A.java"},"note":"x"}',
        '<|DSML| invoke name="read_file">\n<|DSML| parameter name="arguments":'
        '{"tree":"base","path":"A.java"},"note":"x"}</|DSML| parameter>\n</|DSML| invoke>',
    ],
)
def test_mixed_native_markup_takes_the_first_json_object(content: str) -> None:
    translated = native_tool_call(content)
    assert translated is not None
    assert json.loads(translated) == {"tool": "read_file", "arguments": {"tree": "base", "path": "A.java"}}


def test_text_without_native_markup_is_not_salvaged() -> None:
    assert native_tool_call("I think the answer is yes.") is None


def test_agent_is_told_to_finish_while_turns_remain_for_corrections(tmp_path: Path) -> None:
    tree = _write(tmp_path / "base", {"A.java": ""})
    steps = [{"tool": "list_dir", "arguments": {}} for _ in range(7)]
    steps += [
        {"tool": "finish", "arguments": {"answer": "bad"}},
        {"tool": "finish", "arguments": {"answer": "good"}},
    ]
    client = _ScriptedClient(steps)
    result = run_agent(
        client,  # type: ignore[arg-type]
        _Answer,
        role="t",
        brief={},
        tools=RepositoryTools({"base": tree}),
        max_turns=10,
        check=lambda value: [] if value.answer == "good" else ["no"],
    )
    assert result.answer == "good"
    nudges = [turn for turn in client.histories[-1] if turn["content"].startswith("Only 3 turns are left")]
    assert len(nudges) == 1


def test_examples_tree_excludes_the_candidates_own_repository(tmp_path: Path) -> None:
    from rhenium_authoring.history.pipeline import examples_tree

    tree = examples_tree(ROOT, tmp_path / "examples", "booksaw/BetterTeams")
    assert (tree / "README.md").read_text().startswith("# Writing live-server suites")
    assert (tree / "harness" / "io" / "gamecodebench" / "harness" / "GcbSuite.java").is_file()
    suites = {path.name for path in (tree / "suites").iterdir()}
    assert not any(name.startswith("betterteams-") for name in suites)
    assert "chatty-bad-channel-disables-plugin" in suites
    assert (tree / "suites" / "chatty-bad-channel-disables-plugin" / "live-server-design.md").is_file()


def test_tools_stop_executing_once_the_reserve_starts(tmp_path: Path) -> None:
    tree = _write(tmp_path / "base", {"A.java": ""})
    steps = [{"tool": "list_dir", "arguments": {}} for _ in range(9)]
    steps.append({"tool": "finish", "arguments": {"answer": "good"}})
    client = _ScriptedClient(steps)
    result = run_agent(
        client,  # type: ignore[arg-type]
        _Answer,
        role="t",
        brief={},
        tools=RepositoryTools({"base": tree}),
        max_turns=10,
    )
    assert result.answer == "good"
    observations = [turn["content"] for turn in client.histories[-1] if turn["role"] == "user"]
    assert observations.count("Exploration is closed: answer with tool finish now.") == 2


def test_build_failure_reason_reads_gradle_and_maven_output() -> None:
    from rhenium_authoring.history.minecraft_build import build_failure_reason

    gradle = (
        "#9 61.88 FAILURE: Build failed\n#9 61.88 * What went wrong:\n"
        "#9 61.88 Included build 'api' does not exist.\n"
    )
    assert build_failure_reason(gradle) == "Included build 'api' does not exist."
    maven = "[ERROR] Failed to execute goal org.apache:plugin:1.0:compile (default) on project x: boom\n"
    assert build_failure_reason(maven).startswith("Failed to execute goal")
    assert build_failure_reason("nothing useful") == ""


def test_submodule_repositories_are_rejected_before_building(tmp_path: Path) -> None:
    tree = _write(tmp_path, {**GRADLE_PLUGIN, ".gitmodules": '[submodule "api"]\n'})
    with pytest.raises(BuildRejected, match="submodules"):
        infer_build(tree, core_defaults=CORE_DEFAULTS)


def test_templated_plugin_names_and_kotlin_builds_are_accepted(tmp_path: Path) -> None:
    tree = _write(
        tmp_path,
        {
            **GRADLE_PLUGIN,
            "build.gradle": "plugins { id 'com.gradleup.shadow'; id 'org.jetbrains.kotlin.jvm' }\n",
            "spigot/src/main/resources/plugin.yml": "name: ${project.name}\nmain: a.Main\n",
        },
    )
    guess = infer_build(tree, core_defaults=CORE_DEFAULTS)
    assert guess.plugin_name == ""  # read from the built jar instead


def test_artifact_resolves_a_templated_name_from_the_built_jar() -> None:
    from rhenium_authoring.history.minecraft_build import DockerProbe

    facts = {
        "jars": [
            {"path": "target/original-FastLogin.jar", "size": 10, "metadata": "name: FastLogin\n"},
            {"path": "bukkit/target/FastLoginBukkit.jar", "size": 900, "metadata": "name: FastLogin\n"},
            {"path": "core/target/core.jar", "size": 50, "metadata": None},
        ]
    }
    assert DockerProbe._artifact(facts, "") == ("bukkit/target/FastLoginBukkit.jar", "FastLogin")
    with pytest.raises(BuildRejected):
        DockerProbe._artifact(facts, "Other")
