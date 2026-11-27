from __future__ import annotations

import hashlib
import importlib
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def probe(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1]/'probes/interactive_client_v1'))
    return importlib.import_module('acquire_fixed_depot_v1')


def test_complete_requires_manifest_identity_and_terminal_success(probe: ModuleType) -> None:
    signal = {'phase':'console_complete','completeEvents':1,'failureEvents':0,
              'manifest':probe.MANIFEST,'pathMatches':True}
    assert probe.completion_matches(signal)
    for field,value in [('phase','waiting'),('completeEvents',2),('failureEvents',1),
                        ('manifest',int(probe.MANIFEST)),('manifest','other'),('pathMatches',False)]:
        assert not probe.completion_matches({**signal,field:value})


def test_source_hash_and_owner_boundary_are_independent_checks(probe: ModuleType, tmp_path: Path) -> None:
    source=tmp_path/'owned'/'depot'
    source.mkdir(parents=True)
    target=source/'Balatro.exe'
    target.write_bytes(b'fake-game-unit-test')
    expected=hashlib.sha256(target.read_bytes()).hexdigest()
    assert probe.verify_source(source,tmp_path/'owned',expected)['sha256']==expected
    with pytest.raises(RuntimeError,match='hash mismatch'):
        probe.verify_source(source,tmp_path/'owned','0'*64)
    with pytest.raises(RuntimeError,match='escaped'):
        probe.verify_source(source,tmp_path/'different',expected)
    target.unlink()
    target.symlink_to(tmp_path/'elsewhere')
    with pytest.raises(RuntimeError,match='unsafe'):
        probe.verify_source(source,tmp_path/'owned',expected)
