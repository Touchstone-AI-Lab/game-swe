from __future__ import annotations

import os
import sqlite3
import warnings
from pathlib import Path

import pytest
from rhenium_authoring.config import AuthoringSecrets, find_project_root
from rhenium_authoring.models import RunMode, RunStatus
from rhenium_authoring.state import AuthoringStore


def _repository(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    (tmp_path / "pyproject.toml").write_text("[project]\nname='fixture'\n", encoding="utf-8")
    (tmp_path / ".rhenium").mkdir()
    return tmp_path


def test_project_local_secrets_require_exact_permissions(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    path = root / ".rhenium" / "authoring-secrets.toml"
    path.write_text(
        '[kimi]\nbase_url="https://model.invalid/v1"\napi_key="secret"\nmodel="kimi-k3"\n'
        'review_api_key="review-credential"\n'
        '\n[github]\ntoken="github-secret"\n',
        encoding="utf-8",
    )
    path.chmod(0o600)
    with pytest.warns(DeprecationWarning, match=r"\[kimi\] .* deprecated"):
        loaded = AuthoringSecrets.load(root)
    assert loaded.kimi.api_key.get_secret_value() == "secret"
    assert loaded.kimi.review_api_key is not None
    assert loaded.kimi.review_api_key.get_secret_value() == "review-credential"
    assert "secret" not in repr(loaded)
    assert "review-credential" not in repr(loaded)
    assert "review-credential" not in loaded.model_dump_json()
    assert find_project_root(root / ".rhenium") == root

    path.chmod(0o644)
    with pytest.raises(ValueError, match="0600"):
        AuthoringSecrets.load(root)


def test_authoring_store_has_versioned_reopenable_schema(tmp_path: Path) -> None:
    path = tmp_path / "state.sqlite"
    store = AuthoringStore(path)
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    run_id = store.create_run(RunMode.REVIEW)
    store.update_run(run_id, RunStatus.HARVESTING)
    assert AuthoringStore(path).run(run_id)["status"] == RunStatus.HARVESTING.value

    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 999")
    with pytest.raises(RuntimeError, match="newer"):
        AuthoringStore(path)


def test_store_writers_wait_for_the_lock_instead_of_failing(tmp_path: Path) -> None:
    store = AuthoringStore(tmp_path / "authoring.sqlite")
    with store.connect() as connection:
        waited = connection.execute("PRAGMA busy_timeout").fetchone()[0]
    assert waited == AuthoringStore.BUSY_TIMEOUT_SECONDS * 1000 >= 60_000


def test_secret_symlink_is_rejected(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    outside = tmp_path.parent / f"{tmp_path.name}-secret"
    outside.write_text('[kimi]\nbase_url="https://x.invalid"\napi_key="x"\n', encoding="utf-8")
    outside.chmod(0o600)
    os.symlink(outside, root / ".rhenium" / "authoring-secrets.toml")
    with pytest.raises(ValueError, match="symbolic"):
        AuthoringSecrets.load(root)


def test_model_section_loads_without_deprecation(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    path = root / ".rhenium" / "authoring-secrets.toml"
    path.write_text(
        '[model]\nbase_url="https://model.invalid/v1"\napi_key="secret"\nmodel="any"\n',
        encoding="utf-8",
    )
    path.chmod(0o600)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        loaded = AuthoringSecrets.load(root)
    assert loaded.model.model == "any"
    # The deprecated attribute stays available and points at the same object.
    assert loaded.kimi is loaded.model


def test_both_model_sections_are_rejected(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    path = root / ".rhenium" / "authoring-secrets.toml"
    path.write_text(
        '[model]\nbase_url="https://model.invalid/v1"\napi_key="secret"\n'
        '[kimi]\nbase_url="https://model.invalid/v1"\napi_key="secret"\n',
        encoding="utf-8",
    )
    path.chmod(0o600)
    with pytest.raises(ValueError, match="not both"):
        AuthoringSecrets.load(root)


def test_reasoning_effort_accepts_max(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    path = root / ".rhenium" / "authoring-secrets.toml"
    path.write_text(
        '[model]\nbase_url="https://model.invalid/v1"\napi_key="secret"\n'
        'reasoning_effort="max"\n',
        encoding="utf-8",
    )
    path.chmod(0o600)
    assert AuthoringSecrets.load(root).model.reasoning_effort == "max"


def test_reasoning_effort_accepts_xhigh(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    path = root / ".rhenium" / "authoring-secrets.toml"
    path.write_text(
        '[model]\nbase_url="https://model.invalid/v1"\napi_key="secret"\n'
        'reasoning_effort="xhigh"\n',
        encoding="utf-8",
    )
    path.chmod(0o600)
    assert AuthoringSecrets.load(root).model.reasoning_effort == "xhigh"


def test_model_timeout_is_configurable_and_bounded() -> None:
    from pydantic import SecretStr, ValidationError
    from rhenium_authoring.config import ModelSecrets

    base = {"base_url": "https://model.invalid/v1", "api_key": SecretStr("k")}
    assert ModelSecrets(**base).timeout_seconds == 600  # type: ignore[arg-type]
    assert ModelSecrets(**base, timeout_seconds=1800).timeout_seconds == 1800  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        ModelSecrets(**base, timeout_seconds=5)  # type: ignore[arg-type]
