from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from rhenium_authoring.game_adapters import game_spec
from rhenium_authoring.minecraft_runner import render_test_script, validate_case_ids
from rhenium_authoring.verifier_checks import validate_verifier_scripts

TRUSTED = Path(__file__).parents[3] / "benchmarks/minecraft-core/private/harbor/harness/test.sh"


def test_trusted_runner_is_the_reviewed_harness_flow_with_only_the_cases_replaced() -> None:
    script = render_test_script(("plugin is enabled", "regression: it's fixed"))
    validate_verifier_scripts({"tests/test.sh": script})
    assert "\nEXPECTED=2\n" in script
    assert "__EXPECTED_" not in script
    trusted = TRUSTED.read_text(encoding="utf-8")
    tail = trusted[trusted.index("python3 /tests/verify.py") :]
    assert script.endswith(tail)
    # The runner cross-checks the frozen task.json before delegating.
    assert '"/tests/task.json"' in script
    assert 'task.get("serverCases") != names' in script
    assert script.index("printf '0") < script.index("python3 /tests/verify.py")


def test_generated_case_names_cannot_become_shell_syntax(tmp_path: Path) -> None:
    hostile = ("$(touch pwned)", "`touch pwned`", "a; touch pwned; b", "it's $HOME")
    script = render_test_script(hostile)
    bash = shutil.which("bash")
    assert bash is not None
    declaration = script[script.index("declare -a EXPECTED_CASES=(") : script.index('[ "${#EXPECTED_CASES')]
    probe = declaration + 'printf "%s\\n" "${EXPECTED_CASES[@]}"\n'
    result = subprocess.run([bash, "-c", probe], cwd=tmp_path, capture_output=True, text=True, check=True)
    assert result.stdout.splitlines() == list(hostile)
    assert not (tmp_path / "pwned").exists()


@pytest.mark.parametrize(
    "names",
    [
        (),
        ("same", "same"),
        ("",),
        ("   ",),
        (" padded",),
        ("two\nlines",),
        ('quoted "name"',),
        ("back\\slash",),
    ],
)
def test_trusted_runner_rejects_invalid_cases(names: tuple[str, ...]) -> None:
    with pytest.raises(ValueError):
        validate_case_ids(names)
    with pytest.raises(ValueError):
        render_test_script(names)


def test_model_authors_only_the_suite() -> None:
    spec = game_spec("minecraft")
    assert spec.generated_verifier_requirements == ("tests/TaskSuite.java",)
    assert set(spec.verifier_requirements) == {"tests/test.sh", "tests/TaskSuite.java"}
    assert spec.trusted_shell_runner == "tests/test.sh"
    assert spec.project_path_prefixes == ("src/main/java/", "src/main/resources/")
    assert any("Do not generate tests/test.sh" in line for line in spec.verifier_contract)
    assert any("getPlugin(loader_identity)" in line for line in spec.verifier_contract)
    assert any("api-version is the quoted string '1.21'" in line for line in spec.generation_contract)
