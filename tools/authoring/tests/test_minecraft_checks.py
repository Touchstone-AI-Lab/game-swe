"""Contract tests for the operator javac preflight scripts under tools/authoring/checks."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

CHECKS = Path(__file__).resolve().parents[1] / "checks"
PROJECT_CHECK = CHECKS / "minecraft-project-check"
VERIFIER_CHECK = CHECKS / "minecraft-verifier-check"
JAVAC = shutil.which("javac")


def _javac_supports_release_21() -> bool:
    """The scripts compile with --release 21; older JDKs on CI runners cannot."""
    if JAVAC is None:
        return False
    import subprocess

    probe = subprocess.run([JAVAC, "-version"], capture_output=True, text=True, check=False)
    version = (probe.stdout + probe.stderr).strip().split()
    try:
        major = int(version[1].split(".")[0]) if len(version) > 1 else 0
    except ValueError:
        major = 0
    return major >= 21


pytestmark = pytest.mark.skipif(not _javac_supports_release_21(), reason="javac 21+ is not installed")

_BUKKIT_STUBS = {
    "org/bukkit/plugin/java/JavaPlugin.java": (
        "package org.bukkit.plugin.java;\npublic abstract class JavaPlugin {\n"
        '    public void onEnable() {}\n    public String getName() { return "stub"; }\n}\n'
    ),
    "org/bukkit/Bukkit.java": (
        "package org.bukkit;\npublic final class Bukkit {\n"
        "    public static org.bukkit.plugin.PluginManager getPluginManager() { return null; }\n}\n"
    ),
    "org/bukkit/plugin/PluginManager.java": (
        "package org.bukkit.plugin;\npublic interface PluginManager {\n"
        "    boolean isPluginEnabled(String name);\n    Object getPlugin(String name);\n}\n"
    ),
}
_HARNESS_STUBS = {
    "io/gamecodebench/harness/GcbSuite.java": (
        "package io.gamecodebench.harness;\npublic interface GcbSuite {}\n"
    ),
    "io/gamecodebench/harness/GcbCase.java": (
        "package io.gamecodebench.harness;\nimport java.lang.annotation.*;\n"
        "@Retention(RetentionPolicy.RUNTIME) @Target(ElementType.METHOD)\n"
        "public @interface GcbCase { String value(); }\n"
    ),
    "io/gamecodebench/harness/GcbAssert.java": (
        "package io.gamecodebench.harness;\npublic final class GcbAssert {\n"
        "    public static void isTrue(boolean condition, String message) {}\n}\n"
    ),
}


def _compile_stubs(root: Path, stubs: dict[str, str]) -> Path:
    sources = root / "src"
    classes = root / "classes"
    for relative, content in stubs.items():
        path = sources / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    classes.mkdir()
    assert JAVAC is not None
    subprocess.run(
        [JAVAC, "--release", "21", "-d", str(classes), *map(str, sources.rglob("*.java"))],
        check=True,
        capture_output=True,
    )
    return classes


@pytest.fixture(scope="module")
def toolchain(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    root = tmp_path_factory.mktemp("minecraft-stubs")
    bukkit = _compile_stubs(root / "bukkit", _BUKKIT_STUBS)
    harness = _compile_stubs(root / "harness", _HARNESS_STUBS)
    return {
        "RHENIUM_MINECRAFT_CLASSPATH": str(bukkit),
        "RHENIUM_MINECRAFT_HARNESS_CLASSPATH": str(harness),
    }


def _run(
    script: Path, files: dict[str, str], environment: dict[str, str]
) -> tuple[int, dict[str, object], str]:
    env = {"PATH": os.environ.get("PATH", ""), **environment}
    if "JAVA_HOME" in os.environ:
        env["JAVA_HOME"] = os.environ["JAVA_HOME"]
    result = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps({"schema_version": 1, "files": files}),
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=300,
    )
    return result.returncode, json.loads(result.stdout), result.stderr


def _project(main_body: str = "") -> dict[str, str]:
    return {
        "src/main/resources/plugin.yml": (
            "name: NeutralRelay\nmain: neutral.relay.RelayPlugin\nversion: 0.1.0\napi-version: '1.21'\n"
        ),
        "src/main/java/neutral/relay/RelayPlugin.java": (
            "package neutral.relay;\n\n"
            "public final class RelayPlugin extends org.bukkit.plugin.java.JavaPlugin {\n"
            f"    public boolean deliverOnce() {{ return true; }}\n{main_body}}}\n"
        ),
    }


def test_project_check_compiles_a_valid_plugin(toolchain: dict[str, str]) -> None:
    status, response, _stderr = _run(PROJECT_CHECK, _project(), toolchain)
    assert status == 0
    assert response == {"schema_version": 1, "complete": True, "findings": []}


def test_project_check_reports_compile_errors_as_findings(toolchain: dict[str, str]) -> None:
    status, response, _stderr = _run(PROJECT_CHECK, _project('    int broken = "text";\n'), toolchain)
    assert status == 0 and response["complete"] is True
    findings = response["findings"]
    assert findings and any("incompatible types" in item for item in findings)
    assert all("/tmp/" not in item for item in findings)


def test_project_check_requires_the_declared_main_class(toolchain: dict[str, str]) -> None:
    files = _project()
    files["src/main/resources/plugin.yml"] = files["src/main/resources/plugin.yml"].replace(
        "neutral.relay.RelayPlugin", "neutral.relay.Missing"
    )
    _status, response, _stderr = _run(PROJECT_CHECK, files, toolchain)
    assert response["complete"] is True
    assert any("neutral.relay.Missing" in item for item in response["findings"])


def test_checks_fail_closed_without_a_classpath() -> None:
    status, response, stderr = _run(PROJECT_CHECK, _project(), {})
    assert status == 1 and response == {"schema_version": 1, "complete": False, "findings": []}
    assert "RHENIUM_MINECRAFT_CLASSPATH" in stderr


def test_verifier_check_compiles_a_suite_against_the_harness_only(toolchain: dict[str, str]) -> None:
    from conftest import minecraft_suite

    files = {"tests/TaskSuite.java": minecraft_suite(("plugin is enabled",)), "tests/test.sh": "EXPECTED=1\n"}
    status, response, _stderr = _run(VERIFIER_CHECK, files, toolchain)
    assert status == 0 and response == {"schema_version": 1, "complete": True, "findings": []}
    # The submission is not on the classpath: naming its classes is a compile finding.
    coupled = files["tests/TaskSuite.java"].replace(
        "public final class TaskSuite implements GcbSuite {",
        "public final class TaskSuite implements GcbSuite {\n    neutral.relay.RelayPlugin plugin;\n",
    )
    _status, response, _stderr = _run(VERIFIER_CHECK, {**files, "tests/TaskSuite.java": coupled}, toolchain)
    assert response["complete"] is True and any("neutral.relay" in item for item in response["findings"])
    _status, response, stderr = _run(
        VERIFIER_CHECK, files, {"RHENIUM_MINECRAFT_CLASSPATH": toolchain["RHENIUM_MINECRAFT_CLASSPATH"]}
    )
    assert response["complete"] is False and "GcbHarness" in stderr


def test_copy_plan_copies_library_root_once() -> None:
    import importlib.util
    from pathlib import Path

    script = Path(__file__).resolve().parents[1] / "checks" / "_javac_check.py"
    spec = importlib.util.spec_from_file_location("javac_check_plan", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    entries = [
        "/opt/paper/versions/1.21.11/paper-1.21.11.jar",
        "/opt/paper/libraries/io/papermc/paper/paper-api/1.21.11-R0.1-SNAPSHOT/paper-api.jar",
        "/opt/paper/libraries/com/google/guava/guava/33.jar",
        "/opt/gcb/harness/gcb-harness.jar",
    ]
    assert module.copy_plan(entries) == [
        "/opt/paper/libraries",
        "/opt/paper/versions/1.21.11/paper-1.21.11.jar",
        "/opt/gcb/harness/gcb-harness.jar",
    ]
    assert module.copy_plan(["/opt/gcb/harness/gcb-harness.jar"]) == ["/opt/gcb/harness/gcb-harness.jar"]
