from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from rhenium_container.provider import ContainerImageProvider

from rhenium.core.auth import AuthSession

DIGEST = "sha256:" + "a" * 64
IMAGE_ID = "sha256:" + "b" * 64
REFERENCE = f"ghcr.io/example/image@{DIGEST}"


def test_only_digest_pinned_public_images_are_accepted() -> None:
    reference = ContainerImageProvider._pinned_reference(
        {"kind": "container-image", "image": f"ghcr.io/example/image@{DIGEST}"}
    )
    assert reference.endswith(DIGEST)


@pytest.mark.parametrize(
    "source",
    [
        {"kind": "steam-depots", "image": f"ghcr.io/example/image@{DIGEST}"},
        {"kind": "container-image", "image": "ghcr.io/example/image:latest"},
        {"kind": "container-image", "image": "ghcr.io/example/image@sha256:short"},
        {"kind": "container-image", "image": f"@{DIGEST}"},
        {"kind": "container-image"},
    ],
)
def test_floating_or_malformed_references_are_refused(source: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        ContainerImageProvider._pinned_reference(source)


def test_login_mints_an_anonymous_session_without_prompting() -> None:
    provider = ContainerImageProvider(docker="/bin/true")
    recorded: list[tuple[int, str]] = []

    session = provider.login(
        "default",
        challenge=lambda _challenge: pytest.fail("a public image must not raise a challenge"),
        progress=lambda value, phase: recorded.append((value, phase)),
    )

    assert session.principal == "anonymous"
    assert session.secret == {}
    assert recorded and recorded[-1][0] == 100


def _session() -> AuthSession:
    return AuthSession(
        provider_id="container",
        account_alias="default",
        principal="anonymous",
        secret={},
    )


def test_acquire_records_the_exact_reference_and_immutable_image_id(tmp_path: Path) -> None:
    provider = ContainerImageProvider(docker="docker")
    calls: list[list[str]] = []

    def fake_run(arguments: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
        del timeout
        calls.append(arguments)
        if arguments[:2] == ["image", "inspect"] and arguments[-1] == "{{json .RepoDigests}}":
            return subprocess.CompletedProcess(arguments, 0, json.dumps([REFERENCE]), "")
        if arguments[:2] == ["image", "inspect"] and arguments[-1] == "{{.Id}}":
            return subprocess.CompletedProcess(arguments, 0, IMAGE_ID + "\n", "")
        return subprocess.CompletedProcess(arguments, 0, "", "")

    provider._run = fake_run  # type: ignore[method-assign]
    destination = tmp_path / "source"
    provider.acquire(
        {"kind": "container-image", "image": REFERENCE},
        _session(),
        destination,
        progress=lambda _value, _phase: None,
    )

    record = json.loads((destination / "image.json").read_text(encoding="utf-8"))
    assert record == {
        "schemaVersion": 1,
        "image": REFERENCE,
        "imageId": IMAGE_ID,
        "repoDigests": [REFERENCE],
    }
    assert calls[0] == ["pull", REFERENCE]


def test_acquire_rejects_a_daemon_digest_mismatch(tmp_path: Path) -> None:
    provider = ContainerImageProvider(docker="docker")

    def fake_run(arguments: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
        del timeout
        if arguments[:2] == ["image", "inspect"]:
            other = "ghcr.io/example/image@sha256:" + "c" * 64
            return subprocess.CompletedProcess(arguments, 0, json.dumps([other]), "")
        return subprocess.CompletedProcess(arguments, 0, "", "")

    provider._run = fake_run  # type: ignore[method-assign]
    destination = tmp_path / "source"

    with pytest.raises(RuntimeError, match="does not carry the pinned digest"):
        provider.acquire(
            {"kind": "container-image", "image": REFERENCE},
            _session(),
            destination,
            progress=lambda _value, _phase: None,
        )

    assert not (destination / "image.json").exists()
