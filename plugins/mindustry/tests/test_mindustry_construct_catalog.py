import tomllib
from pathlib import Path

from rhenium_mindustry.construct_catalog import MindustryConstructCatalog, MindustryConstructTask


def test_task_defaults() -> None:
    assert MindustryConstructTask.model_fields["task_kind"].default == "generation"
    assert MindustryConstructTask.model_fields["game_version"].default == "159"


def test_required_files_match_task_prompts() -> None:
    pack_root = Path(__file__).resolve().parents[3] / "benchmarks" / "mindustry-construct"
    catalog = MindustryConstructCatalog.load(pack_root)
    assert len(catalog.tasks) == 10

    for task in catalog.tasks:
        source = pack_root / "private" / "harbor" / task.id / "instruction.md"
        prompt = source.read_text(encoding="utf-8")
        required = prompt.split("## Required files\n", 1)[1].split("```text\n", 1)[1]
        public_files = required.split("\n```", 1)[0].splitlines()
        assert task.required_files == public_files, task.id


def test_harbor_tasks_use_separate_networkless_verifiers() -> None:
    pack_root = Path(__file__).resolve().parents[3] / "benchmarks" / "mindustry-construct"
    catalog = MindustryConstructCatalog.load(pack_root)

    for task in catalog.tasks:
        config_path = pack_root / "private" / "harbor" / task.id / "task.toml"
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))

        assert config["schema_version"] == "1.4", task.id
        assert config["artifacts"] == ["/workspace/mindustry"], task.id
        assert config["verifier"]["environment_mode"] == "separate", task.id
        assert config["verifier"]["network_mode"] == "no-network", task.id
        assert config["agent"]["network_mode"] == "no-network", task.id
        assert (config_path.parent / "tests" / "Dockerfile").is_file(), task.id


def test_each_harbor_task_has_one_single_defect_ablation() -> None:
    pack_root = Path(__file__).resolve().parents[3] / "benchmarks" / "mindustry-construct"
    catalog = MindustryConstructCatalog.load(pack_root)

    for task in catalog.tasks:
        ablations = pack_root / "private" / "harbor" / task.id / "validation" / "ablations"
        rows = (ablations / "manifest.tsv").read_text(encoding="utf-8").splitlines()
        assert rows[0] == "ablation\tpatch\texpected_failed_case", task.id
        assert len(rows) == 2, task.id
        _, patch_name, expected_failed_case = rows[1].split("\t")
        assert expected_failed_case, task.id
        patch = (ablations / patch_name).read_text(encoding="utf-8")
        assert patch.startswith("--- a/solution/"), task.id
        assert "\n+++ b/solution/" in patch, task.id


def test_public_attempt_material_never_contains_the_task_id() -> None:
    # The Hub refuses to prepare an anonymous attempt whose exam or scaffold names its task.
    pack_root = Path(__file__).resolve().parents[3] / "benchmarks" / "mindustry-construct"
    catalog = MindustryConstructCatalog.load(pack_root)

    for task in catalog.tasks:
        scaffold = pack_root / "private" / "harbor" / task.id / "environment" / "mindustry"
        public = [pack_root / "exams" / f"{task.id}.md", *(p for p in scaffold.rglob("*") if p.is_file())]
        assert len(public) > 1, task.id
        for path in public:
            assert task.id not in path.read_text(encoding="utf-8"), f"{task.id}: {path.name}"
