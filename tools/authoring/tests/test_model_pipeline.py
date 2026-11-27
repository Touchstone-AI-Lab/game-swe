from __future__ import annotations

import hashlib
import json
from pathlib import Path

import httpx
from pydantic import SecretStr
from rhenium_authoring.cleanroom import CleanRoomSynthesizer
from rhenium_authoring.config import ModelSecrets
from rhenium_authoring.model_client import ModelClient
from rhenium_authoring.models import (
    CandidateStatus,
    HistoricalFix,
    PublicationRecord,
    RunMode,
    RunStatus,
    SynthesisBundle,
    SynthInterfaceContract,
    ValidationReport,
)
from rhenium_authoring.pipeline import AuthoringPipeline
from rhenium_authoring.state import AuthoringStore


class PassingValidator:
    def validate(self, run_root: Path, bundle: SynthesisBundle) -> ValidationReport:
        del run_root
        return ValidationReport(
            candidate_id=bundle.candidate.id,
            complete=True,
            passed=True,
            base_failed=True,
            gold_passed=True,
            engine_backed=True,
        )


class RecordingPublisher:
    def __init__(self) -> None:
        self.candidates: list[str] = []

    def publish(
        self, bundle: SynthesisBundle, validation: ValidationReport
    ) -> PublicationRecord:
        del validation
        self.candidates.append(bundle.candidate.id)
        return PublicationRecord(
            candidate_id=bundle.candidate.id,
            task_key=f"dst/synth/{bundle.candidate.id}",
            catalog_version="1.0.0",
        )


def test_http_kimi_protocol_drives_complete_seeded_generation(
    tmp_path: Path, dst_bundle: SynthesisBundle, dst_interface_contract: SynthInterfaceContract
) -> None:
    capsules = {
        _capsule_id(fix): capsule.model_copy(update={"capsule_id": _capsule_id(fix)})
        for fix, capsule in zip(
            dst_bundle.provenance, dst_bundle.candidate.capsules, strict=True
        )
    }
    fixed = dst_bundle.fixed
    contract = dst_interface_contract.model_copy(
        update={
            "capsule_entrypoints": {
                new: old for new, old in zip(
                    sorted(capsules), dst_interface_contract.capsule_entrypoints.values(), strict=True
                )
            }
        }
    )
    contract_consumers: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        user = json.loads(body["messages"][1]["content"])
        if "behavior fact extractor" in system:
            output = capsules[user["required_capsule_id"]].model_dump(mode="json")
        elif "public-interface designer" in system:
            assert "private_sources" not in user
            assert "fixed_project" not in user
            output = contract.model_dump(mode="json")
        elif "fixed-project implementer" in system:
            output = fixed.model_dump(mode="json")
        elif "behavioral verifier author" in system:
            ids = [item["capsule_id"] for item in user["candidate"]["capsules"]]
            output = {
                "files": {
                    "hidden.lua": "return function() end\n",
                    "server.lua": "return function() end\n",
                },
                "case_ids": ["sentinel", "case_one", "case_two"],
                "capsule_cases": {ids[0]: ["case_one"], ids[1]: ["case_two"]},
            }
        elif "historical-defect injector" in system:
            ids = [item["capsule_id"] for item in user["candidate"]["capsules"]]
            base_files = dict(fixed.files)
            base_files["scripts/relay.lua"] = base_files["scripts/relay.lua"].replace(
                "return true", "return false"
            )
            base_files["scripts/capacity.lua"] = base_files[
                "scripts/capacity.lua"
            ].replace("return true", "return false")
            output = {
                "injections": [
                    {
                        "capsule_id": ids[0],
                        "symptom": "A repeated request is delivered twice.",
                        "replacements": {"scripts/relay.lua": base_files["scripts/relay.lua"]},
                    },
                    {
                        "capsule_id": ids[1],
                        "symptom": "A failed delivery consumes capacity.",
                        "replacements": {"scripts/capacity.lua": base_files["scripts/capacity.lua"]},
                    },
                ],
            }
        elif "symptom-only issue author" in system:
            output = {"markdown": "# Anonymous failures\n\nRepair all observed behaviors."}
        elif "contract reviewer" in system:
            output = {
                "approved": True,
                "leakage_findings": [],
                "contract_findings": [],
                "rationale": "The generated project is independent and fully specified.",
            }
        else:
            raise AssertionError(system)
        if any(stage in system for stage in (
            "fixed-project implementer", "behavioral verifier author",
            "historical-defect injector", "symptom-only issue author",
        )):
            assert user["interface_contract"] == contract.model_dump(mode="json")
            assert "private_sources" not in user
            contract_consumers.append(system)
        if "behavioral verifier author" in system:
            assert "fixed_project" not in user
            assert "load_submission" in str(user["instructions"])
            assert "context:case" in str(user["instructions"])
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(output)}}]},
        )

    http = httpx.Client(transport=httpx.MockTransport(handler))
    kimi = ModelClient(
        ModelSecrets(base_url="https://model.invalid/v1", api_key=SecretStr("test")), client=http
    )
    (tmp_path / ".rhenium").mkdir()
    store = AuthoringStore(tmp_path / ".rhenium/authoring/authoring.sqlite")
    publisher = RecordingPublisher()
    pipeline = AuthoringPipeline(
        tmp_path,
        store,
        CleanRoomSynthesizer(kimi),
        {},
        None,
        validator=PassingValidator(),  # type: ignore[arg-type]
        publisher=publisher,  # type: ignore[arg-type]
    )
    run_id = pipeline.run(
        mode=RunMode.YOLO,
        source_names=(),
        game_ids=("dst",),
        limit=2,
        seed_fixes=dst_bundle.provenance,
    )
    assert store.run(run_id)["status"] == RunStatus.COMPLETE.value
    assert store.candidates(run_id)[0]["status"] == CandidateStatus.PUBLISHED.value
    assert publisher.candidates
    assert len(contract_consumers) == 4
    checkpoint_root = tmp_path / ".rhenium" / "authoring" / "runs" / run_id / "checkpoints"
    assert len(list((checkpoint_root / "capsules").glob("*.json"))) == 2
    stages = list(checkpoint_root.glob("synthetic-*/*.json"))
    assert {path.stem for path in stages} == {
        "interface", "fixed", "verifier", "base", "prompt", "review", "validation",
    }
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in stages)


def _capsule_id(fix: HistoricalFix) -> str:
    digest = hashlib.sha256(
        f"{fix.game_id}\0{fix.base_sha}\0{fix.fixed_sha}".encode()
    ).hexdigest()[:16]
    return f"behavior-{digest}"
