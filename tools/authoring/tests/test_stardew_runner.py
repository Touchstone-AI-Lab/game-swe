from __future__ import annotations

import pytest
from rhenium_authoring.stardew_runner import render_test_script
from rhenium_authoring.verifier_checks import validate_verifier_scripts


def test_trusted_runner_is_syntactically_valid_and_fails_closed() -> None:
    script = render_test_script(("sentinel", "regression"))
    validate_verifier_scripts({"tests/test.sh": script})
    assert "EXPECTED=2" in script
    assert script.index("printf '0") < script.index("dotnet build")
    assert "type(result.get(\"passed\")) is not int" in script
    assert 'set(actual_names) != set(names)' in script
    assert "game_status" in script
    assert "__EXPECTED_" not in script


@pytest.mark.parametrize("names", [(), ("same", "same"), ("",)])
def test_trusted_runner_rejects_invalid_cases(names: tuple[str, ...]) -> None:
    with pytest.raises(ValueError):
        render_test_script(names)
