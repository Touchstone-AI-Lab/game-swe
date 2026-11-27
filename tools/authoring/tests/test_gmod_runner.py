from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from rhenium_authoring.game_adapters import game_spec
from rhenium_authoring.gmod_runner import render_test_script
from rhenium_authoring.verifier_checks import validate_verifier_scripts

TRUSTED = (
    Path(__file__).parents[3]
    / "benchmarks/darkrp-core/private/harbor/darkrp-release-regressions-v3/tests/test.sh"
)


def test_trusted_runner_is_the_reviewed_darkrp_flow_with_only_the_cases_replaced() -> None:
    script = render_test_script(("sentinel", "regression: it's fixed"))
    validate_verifier_scripts({"tests/test.sh": script})
    assert "\nEXPECTED=2\n" in script
    assert "__EXPECTED_" not in script
    trusted = TRUSTED.read_text(encoding="utf-8")
    tail = trusted[trusted.index('[ "${#EXPECTED_CASES[@]}" -eq "$EXPECTED" ]') :]
    assert script.endswith(tail)
    for required in ("trusted_collector.py patch", "trusted_collector.py collect", "--nonce"):
        assert required in script


def test_generated_case_names_cannot_become_shell_syntax(tmp_path: Path) -> None:
    hostile = ('$(touch pwned)', "`touch pwned`", 'a"; touch pwned; "', "it's $HOME")
    script = render_test_script(hostile)
    bash = shutil.which("bash")
    assert bash is not None
    declaration = script[script.index("declare -a EXPECTED_CASES=(") : script.index("[ \"${#EXPECTED_CASES")]
    probe = declaration + 'printf "%s\\n" "${EXPECTED_CASES[@]}"\n'
    result = subprocess.run([bash, "-c", probe], cwd=tmp_path, capture_output=True, text=True, check=True)
    assert result.stdout.splitlines() == list(hostile)
    assert not (tmp_path / "pwned").exists()


@pytest.mark.parametrize("names", [(), ("same", "same"), ("",), ("   ",), ("two\nlines",), ("tab\there",)])
def test_trusted_runner_rejects_invalid_cases(names: tuple[str, ...]) -> None:
    with pytest.raises(ValueError):
        render_test_script(names)


def test_model_authors_only_the_suite() -> None:
    spec = game_spec("garrys-mod")
    assert spec.generated_verifier_requirements == ("tests/suite.lua",)
    assert set(spec.verifier_requirements) == {"tests/test.sh", "tests/suite.lua"}
    assert any("Do not generate tests/test.sh" in line for line in spec.verifier_contract)
