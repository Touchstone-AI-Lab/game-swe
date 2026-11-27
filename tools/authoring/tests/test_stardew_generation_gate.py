from __future__ import annotations

import json
from typing import Any

import pytest
from rhenium_authoring.cleanroom import CleanRoomSynthesizer
from rhenium_authoring.models import SynthesisBundle, SynthInterfaceContract


@pytest.mark.parametrize("bad", [
    {"tests/TaskSuite.cs": "helper.ModRegistry.GetApi<object>(id);"},
    {"tests/TaskSuite.cs": "public class TaskSuite {}", "tests/test.sh": "exit 0"},
])
def test_model_cannot_use_invalid_generic_api_or_replace_trusted_runner(
    dst_bundle: SynthesisBundle, dst_interface_contract: SynthInterfaceContract, bad: dict[str, str],
) -> None:
    calls: list[dict[str, Any]] = []
    responses = [
        dst_bundle.verifier.model_copy(update={"files": bad}),
        dst_bundle.verifier.model_copy(update={"files": {"tests/TaskSuite.cs": "public class TaskSuite {}"}}),
    ]

    class Model:
        on_event = staticmethod(lambda _: None)

        def complete(self, *args: Any, **kwargs: Any) -> Any:
            calls.append(json.loads(json.dumps(kwargs["payload"])))
            return responses.pop(0)

    candidate = dst_bundle.candidate.model_copy(update={"game_id": "stardew-valley"})
    result = CleanRoomSynthesizer(Model()).generate_verifier(  # type: ignore[arg-type]
        candidate, dst_interface_contract, case_contract=dst_bundle.verifier,
    )
    assert len(calls) == 2
    assert calls[0]["required_verifier_files"] == ["tests/TaskSuite.cs"]
    assert set(result.files) == {"tests/TaskSuite.cs", "tests/test.sh"}
    assert "set -euo pipefail" in result.files["tests/test.sh"]
    assert "validation_feedback" in calls[1]
