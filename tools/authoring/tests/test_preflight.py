from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from rhenium_authoring.cleanroom import CleanRoomSynthesizer
from rhenium_authoring.models import (
    DefectInjection,
    DefectInjections,
    SynthesisBundle,
    SynthInterfaceContract,
)
from rhenium_authoring.preflight import CommandVerifierCheck


def test_compiler_feedback_retries_only_verifier_and_preserves_case_contract(
    dst_bundle: SynthesisBundle,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    requests: list[dict[str, Any]] = []
    checks: list[int] = []

    class Model:
        on_event = staticmethod(lambda event: None)

        def complete(self, output: Any, *, role: str, payload: dict[str, object]) -> Any:
            requests.append(json.loads(json.dumps(payload)))
            return dst_bundle.verifier

    def check(verifier: Any) -> tuple[str, ...]:
        checks.append(1)
        return ("compiler: readonly API property",) if len(checks) == 1 else ()

    synth = CleanRoomSynthesizer(Model(), verifier_check=check)  # type: ignore[arg-type]
    result = synth.generate_verifier(
        dst_bundle.candidate,
        dst_interface_contract,
        case_contract=dst_bundle.verifier,
    )
    assert result == dst_bundle.verifier and len(requests) == 2
    assert "readonly API property" in str(requests[1]["validation_feedback"])
    assert requests[1]["previous_verifier"] == dst_bundle.verifier.model_dump(mode="json")
    assert requests[0]["required_case_contract"]["case_ids"] == list(dst_bundle.verifier.case_ids)
    assert all("fixed_project" not in request and "base" not in request for request in requests)


def test_compiler_rejection_never_becomes_a_pass(
    dst_bundle: SynthesisBundle,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    class Model:
        on_event = staticmethod(lambda event: None)

        def complete(self, *args: Any, **kwargs: Any) -> Any:
            return dst_bundle.verifier

    synth = CleanRoomSynthesizer(Model(), verifier_check=lambda _: ("CS1503",))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="three attempts"):
        synth.generate_verifier(dst_bundle.candidate, dst_interface_contract)


@pytest.mark.parametrize(
    "response",
    [
        {"schema_version": 1, "complete": False, "findings": []},
        {"schema_version": 2, "complete": True, "findings": []},
        {"schema_version": 1, "complete": True, "findings": [], "unknown": "field"},
    ],
)
def test_preflight_fails_closed_and_omits_credentials(
    tmp_path: Path,
    monkeypatch: Any,
    dst_bundle: SynthesisBundle,
    response: dict[str, Any],
) -> None:
    executable = tmp_path / "checker"
    executable.touch()
    executable.chmod(0o700)
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "do-not-forward")

    def invoke(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert "ANTHROPIC_AUTH_TOKEN" not in kwargs["env"]
        assert "do-not-forward" not in kwargs["input"]
        return subprocess.CompletedProcess([], 0, json.dumps(response), "")

    monkeypatch.setattr(subprocess, "run", invoke)
    checker = CommandVerifierCheck(executable, tmp_path / "receipts")
    with pytest.raises(RuntimeError, match="no unchecked verifier"):
        checker(dst_bundle.verifier)
    receipt = next((tmp_path / "receipts").glob("*.json"))
    assert json.loads(receipt.read_text())["complete"] is False
    assert receipt.stat().st_mode & 0o777 == 0o600


def test_synthetic_docker_creates_absolute_application_data_before_smapi() -> None:
    root = Path(__file__).resolve().parents[1]
    template = (root / "src/rhenium_authoring/assets/stardew.Dockerfile").read_text()
    assert "ENV XDG_CONFIG_HOME=/opt/gcb/user-config" in template
    assert template.index(
        'mkdir -p /opt/stardew/Mods/GcbHarness /logs/verifier "$XDG_CONFIG_HOME"'
    ) < template.index("GCB_MODE=gen-save")
    assert '"$XDG_CONFIG_HOME/StardewValley/Saves"' in template


def test_project_compiler_repairs_without_leaking_verifier_or_source(
    dst_bundle: SynthesisBundle, dst_interface_contract: SynthInterfaceContract,
) -> None:
    requests: list[dict[str, Any]] = []
    checks: list[dict[str, str]] = []

    class Model:
        on_event = staticmethod(lambda _: None)

        def complete(self, *args: Any, **kwargs: Any) -> Any:
            requests.append(json.loads(json.dumps(kwargs["payload"])))
            return dst_bundle.fixed

    def check(files: dict[str, str]) -> tuple[str, ...]:
        checks.append(files)
        return ("CS0428: invoke the static method",) if len(checks) == 1 else ()

    synth = CleanRoomSynthesizer(Model(), project_check=check)  # type: ignore[arg-type]
    assert synth.generate_fixed(dst_bundle.candidate, dst_interface_contract) == dst_bundle.fixed
    assert len(requests) == 2
    assert requests[1]["previous_project"] == dst_bundle.fixed.model_dump(mode="json")
    assert "CS0428" in str(requests[1]["validation_feedback"])
    assert all("verifier" not in item and "private_sources" not in item for item in requests)


def test_project_compiler_checks_every_defect_control(
    dst_bundle: SynthesisBundle, dst_interface_contract: SynthInterfaceContract,
) -> None:
    checks: list[dict[str, str]] = []
    requests: list[dict[str, Any]] = []

    class Model:
        on_event = staticmethod(lambda _: None)

        def complete(self, *args: Any, **kwargs: Any) -> Any:
            requests.append(json.loads(json.dumps(kwargs["payload"])))
            return DefectInjections(injections=tuple(
                DefectInjection(capsule_id=report.capsule_id, symptom=report.symptom,
                                replacements={path: dst_bundle.base.files[path]
                                              for path in report.affected_files})
                for report in dst_bundle.base.defects
            ))

    def check(files: dict[str, str]) -> tuple[str, ...]:
        checks.append(files)
        return ("CS0220: constant overflow",) if len(checks) == 2 else ()

    synth = CleanRoomSynthesizer(Model(), project_check=check)  # type: ignore[arg-type]
    result = synth.inject_defects(dst_bundle.candidate, dst_bundle.fixed, dst_interface_contract)
    assert result == dst_bundle.base
    assert len(checks) == 6 and len(requests) == 2
    assert checks[:3] == [dst_bundle.base.files, *[dst_bundle.base.ablations[key]
                                                 for key in sorted(dst_bundle.base.ablations)]]
    assert "CS0220" in str(requests[1]["validation_feedback"])


def test_fixed_compiler_never_accepts_repeated_failure(
    dst_bundle: SynthesisBundle, dst_interface_contract: SynthInterfaceContract,
) -> None:
    class Model:
        on_event = staticmethod(lambda _: None)

        def complete(self, *args: Any, **kwargs: Any) -> Any:
            return dst_bundle.fixed

    synth = CleanRoomSynthesizer(Model(), project_check=lambda _: ("CS0103",))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="three attempts"):
        synth.generate_fixed(dst_bundle.candidate, dst_interface_contract)


def test_checker_environment_forwards_java_toolchain_but_never_model_secrets() -> None:
    from rhenium_authoring.preflight import _checker_environment

    environment = {
        "PATH": "/usr/bin",
        "JAVA_HOME": "/opt/jdk",
        "RHENIUM_MINECRAFT_CLASSPATH": "/opt/paper/libraries",
        "RHENIUM_MINECRAFT_HARNESS_CLASSPATH": "/opt/gcb/harness/gcb-harness.jar",
        "RHENIUM_DATABASE_URL": "sqlite:///private.sqlite",
        "ANTHROPIC_AUTH_TOKEN": "do-not-forward",
        "OPENAI_API_KEY": "do-not-forward",
        "HOME": "/home/operator",
    }
    forwarded = _checker_environment(environment)
    assert forwarded == {
        "PATH": "/usr/bin",
        "JAVA_HOME": "/opt/jdk",
        "RHENIUM_MINECRAFT_CLASSPATH": "/opt/paper/libraries",
        "RHENIUM_MINECRAFT_HARNESS_CLASSPATH": "/opt/gcb/harness/gcb-harness.jar",
    }
