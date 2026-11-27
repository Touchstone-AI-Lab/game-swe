from __future__ import annotations

import json
from pathlib import Path

from rhenium_authoring.artifacts import materialize_bundle, write_validation
from rhenium_authoring.export import export_training_data
from rhenium_authoring.models import SynthesisBundle, ValidationReport


def test_training_export_contains_only_validated_anonymous_data(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    passing_validation: ValidationReport,
) -> None:
    run_root = tmp_path / "run"
    candidate = materialize_bundle(run_root, dst_bundle)
    write_validation(candidate, passing_validation)
    output = export_training_data(run_root, tmp_path / "export")
    record = json.loads(output.read_text(encoding="utf-8"))
    assert record["clean_room_synthetic"] is True
    assert record["instance_id"] == dst_bundle.candidate.id
    assert "github.com" not in output.read_text(encoding="utf-8")
    assert "historical patch" not in output.read_text(encoding="utf-8")
    assert (output.parent / record["base_archive"]).is_file()
