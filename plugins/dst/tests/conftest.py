from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def sample_mod(tmp_path: Path) -> Path:
    root = tmp_path / "sample-mod"
    root.mkdir()
    (root / "modinfo.lua").write_text(
        'name = "Static Sword"\napi_version = 10\ndst_compatible = true\n'
        "all_clients_require_mod = true\nclient_only_mod = false\n",
        encoding="utf-8",
    )
    (root / "modmain.lua").write_text(
        'local DAMAGE = 68\nAddPrefabPostInit("spear", function(inst)\n'
        '    inst:AddTag("rhenium_sword")\nend)\n',
        encoding="utf-8",
    )
    return root
