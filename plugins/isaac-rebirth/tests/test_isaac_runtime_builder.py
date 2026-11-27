from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from rhenium_isaac_rebirth.catalog import IsaacCatalog
from rhenium_isaac_rebirth.evaluator import VERIFIER_IMAGE
from rhenium_isaac_rebirth.runtime_builder import IsaacRuntimeBuilder

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeActionRequired, RuntimeCatalog

ROOT = Path(__file__).parents[3]
PACK = ROOT / "benchmarks" / "isaac-core"
SYNTH_PACK = ROOT / "benchmarks" / "isaac-synth"


def _context(tmp_path: Path) -> BenchmarkContext:
    return BenchmarkContext(
        project_root=ROOT,
        pack_root=PACK,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )


def _spec() -> Any:
    catalog = RuntimeCatalog.model_validate_json(
        (PACK / "runtimes.json").read_text(encoding="utf-8")
    )
    return catalog.runtimes[0]


class FakeDocker:
    """Record Docker calls and emulate the profile container's file handover."""

    def __init__(
        self,
        *,
        profile_writes_options: bool = True,
        profile_exit_code: int = 0,
        profile_stdout: str = "",
        profile_stderr: str = "",
        profile_stages_client_update: bool = False,
        removal_times_out: bool = False,
    ) -> None:
        self.calls: list[list[str]] = []
        self.removal_times_out = removal_times_out
        self.profile_writes_options = profile_writes_options
        self.profile_stages_client_update = profile_stages_client_update
        self.profile_exit_code = profile_exit_code
        self.profile_stdout = profile_stdout
        self.profile_stderr = profile_stderr
        self.verifier_built = False
        self.construct_images: set[str] = set()

    def __call__(self, arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        del timeout
        self.calls.append(arguments)
        if arguments[0] == "build" and VERIFIER_IMAGE in arguments:
            self.verifier_built = True
        if arguments[:2] == ["image", "inspect"] and arguments[2] == VERIFIER_IMAGE:
            # The verifier image only exists once this prepare run has built it.
            if not self.verifier_built:
                return subprocess.CompletedProcess([], 1, "", "no such image")
            return subprocess.CompletedProcess([], 0, "sha256:" + "b" * 64, "")
        if arguments[:2] == ["image", "inspect"] and arguments[2].startswith("gcb-isaac-verifier:"):
            # A construct task's verifier image, built by this prepare run under its own tag.
            built = any(call[0] == "build" and arguments[2] in call for call in self.calls)
            if not built:
                return subprocess.CompletedProcess([], 1, "", "no such image")
            image_id = "sha256:" + hashlib.sha256(arguments[2].encode()).hexdigest()
            self.construct_images.add(image_id)
            return subprocess.CompletedProcess([], 0, image_id, "")
        if arguments[:2] == ["image", "inspect"] and arguments[2] in self.construct_images:
            return subprocess.CompletedProcess([], 0, arguments[2], "")
        if arguments[0] == "create":
            return subprocess.CompletedProcess([], 0, "profile-container", "")
        if arguments[:2] == ["rm", "--force"] and self.removal_times_out:
            raise subprocess.TimeoutExpired(arguments, 300)
        if arguments[:2] == ["start", "--attach"]:
            return subprocess.CompletedProcess(
                [], self.profile_exit_code, self.profile_stdout, self.profile_stderr
            )
        if arguments[0] == "cp" and self.profile_writes_options:
            target = Path(arguments[2])
            if arguments[1].endswith("/."):
                # Copying the client state back out of the profile container.
                target.mkdir(parents=True, exist_ok=True)
                if self.profile_stages_client_update:
                    # An online client downloads its own update and applies it on the next start.
                    package = target / "package"
                    package.mkdir(exist_ok=True)
                    for name in ("steam_client_ubuntu12.manifest", "steam_client_ubuntu12.installed",
                                 "steam_client_ubuntu12", "runtime_scout_ubuntu12.zip.a37e"):
                        (package / name).write_text(name, encoding="utf-8")
                return subprocess.CompletedProcess([], 0, "", "")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("[Options]\nEnableMods=0\n", encoding="utf-8")
            return subprocess.CompletedProcess([], 0, "", "")
        if arguments[0] == "cp":
            return subprocess.CompletedProcess([], 1, "", "no such file")
        return subprocess.CompletedProcess([], 0, "", "")

    def command_after(self, name: str) -> list[str]:
        return next(call for call in self.calls if call[0] == name)


def _source(tmp_path: Path, *, client: bool = True, linux_runtime: bool = True) -> Path:
    source = tmp_path / "source"
    (source / "lib64").mkdir(parents=True)
    for name in ("isaac.x64", "isaac.i386", "run-x64.sh"):
        target = source / name
        target.write_text("binary", encoding="utf-8")
        target.chmod(0o644)
    if client:
        home = source / ".official-client/steam-home/debian-installation"
        (home / "config").mkdir(parents=True)
        (home / "steam.sh").write_text("#!/bin/sh\n", encoding="utf-8")
        if linux_runtime:
            for name in ("SteamLinuxRuntime", "SteamLinuxRuntime_soldier"):
                (home / "steamapps/common" / name).mkdir(parents=True)
        (home / "userdata/318853164/config").mkdir(parents=True, exist_ok=True)
        library = home / "steamapps/libraryfolders.vdf"
        library.parent.mkdir(parents=True, exist_ok=True)
        library.write_text(
            '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"/home/azureuser"\n'
            '\t\t"apps"\n\t\t{\n\t\t\t"1070560"\t\t"222685392"\n\t\t}\n\t}\n}\n',
            encoding="utf-8",
        )
    return source


def _builder(tmp_path: Path, docker: FakeDocker, pack: Path = PACK) -> IsaacRuntimeBuilder:
    context = BenchmarkContext(
        project_root=ROOT,
        pack_root=pack,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )
    builder = IsaacRuntimeBuilder(context, IsaacCatalog.load(pack))
    builder.runtime._docker = docker  # type: ignore[method-assign]
    builder.runtime.docker = "docker"
    return builder


def _synth_spec() -> Any:
    catalog = RuntimeCatalog.model_validate_json(
        (SYNTH_PACK / "runtimes.json").read_text(encoding="utf-8")
    )
    return catalog.runtimes[0]


def test_construct_prepare_creates_the_profile_once_and_builds_one_image_per_task(
    tmp_path: Path,
) -> None:
    """The construct runtime needs the same ticketed client and fresh options.ini as the
    Exodus runtime, so its preparation runs the profile container before building the
    per-task private and verifier images, and records one immutable image id per task."""
    docker = FakeDocker()
    builder = _builder(tmp_path, docker, SYNTH_PACK)
    destination = tmp_path / "runtime"
    spec = _synth_spec()
    catalog = IsaacCatalog.load(SYNTH_PACK)
    source = _source(tmp_path)

    artifact = builder.prepare(spec, source, destination, progress=lambda _value, _phase: None)

    assert (destination / "isaac-data/options.ini").is_file()
    create = docker.command_after("create")
    assert "[GCB_PROFILE] profile_created" in create[-1]
    first_task = catalog.tasks[0].id
    profile_build = docker.command_after("build")
    assert profile_build[profile_build.index("--file") + 1].endswith(
        f"private/harbor/{first_task}/scripts/private-runtime.Dockerfile"
    )
    assert docker.calls.index(create) > docker.calls.index(profile_build)
    builds = [call for call in docker.calls if call[0] == "build"]
    # One profile image, then a private and a verifier image per catalog task.
    assert len(builds) == 1 + 2 * len(catalog.tasks)
    for task in catalog.tasks:
        private_tag = f"gcb-isaac-private-runtime:{task.id}-{catalog.version}"
        verifier_tag = f"gcb-isaac-verifier:{task.id}-{catalog.version}"
        private_build = next(call for call in builds if private_tag in call)
        verifier_build = next(call for call in builds if verifier_tag in call)
        assert f"PRIVATE_IMAGE={private_tag}" in verifier_build
        assert "--network=none" in verifier_build
        assert docker.calls.index(private_build) < docker.calls.index(verifier_build)
        assert docker.calls.index(create) < docker.calls.index(private_build)
    assert artifact.kind == "docker-images"
    assert artifact.runtime_key == "isaac-rebirth/afterbirth-plus-1.06.t1-synth"
    images = artifact.metadata["images"]
    assert set(images) == {task.id for task in catalog.tasks}
    assert all(str(value).startswith("sha256:") for value in images.values())
    assert builder.verify(spec, artifact)["available"] is True

    # A second preparation with the profile present skips the online profile run.
    again = FakeDocker()
    builder_again = _builder(tmp_path, again, SYNTH_PACK)
    builder_again.prepare(spec, source, destination, progress=lambda _value, _phase: None)
    assert not any(call[0] == "create" for call in again.calls)


def test_prepare_uses_the_acquired_client_and_stages_runnable_game_files(tmp_path: Path) -> None:
    docker = FakeDocker()
    builder = _builder(tmp_path, docker)
    destination = tmp_path / "runtime"

    artifact = builder.prepare(
        _spec(), _source(tmp_path), destination, progress=lambda _value, _phase: None
    )

    game = destination / "steam-home/debian-installation/steamapps/common/The Binding of Isaac Rebirth"
    assert (destination / "steam-home/debian-installation/steam.sh").is_file()
    assert not (game / ".official-client").exists()
    assert game.joinpath("isaac.x64").stat().st_mode & 0o111
    assert game.joinpath("run-x64.sh").stat().st_mode & 0o111
    assert (destination / "isaac-data/options.ini").is_file()
    assert artifact.metadata["clientBootstrap"] == "managed"


def test_prepare_records_the_staged_game_as_installed(tmp_path: Path) -> None:
    """Without an install record the offline client refuses to launch the app."""
    builder = _builder(tmp_path, FakeDocker())
    destination = tmp_path / "runtime"

    builder.prepare(
        _spec(), _source(tmp_path), destination, progress=lambda _value, _phase: None
    )

    steamapps = destination / "steam-home/debian-installation/steamapps"
    manifest = (steamapps / "appmanifest_250900.acf").read_text(encoding="utf-8")
    library = (steamapps / "libraryfolders.vdf").read_text(encoding="utf-8")
    assert '"StateFlags"\t\t"4"' in manifest
    assert '"installdir"\t\t"The Binding of Isaac Rebirth"' in manifest
    assert '"buildid"\t\t"22878971"' in manifest
    # The offline client matches the recorded owner against the signed-in account.
    assert '"LastOwner"\t\t"76561198279118892"' in manifest
    # Every pinned depot the provider acquired is recorded as installed.
    for depot, depot_manifest in (
        ("250903", "367036646469636831"),
        ("250906", "274330258716671855"),
        ("250909", "5041024818858406088"),
    ):
        assert f'"{depot}"' in manifest
        assert depot_manifest in manifest
    assert '"250900"' in library
    # The runtimes the client already had stay in the index.
    assert '"1070560"' in library


def test_prepare_creates_the_profile_and_keeps_the_ticketed_client(tmp_path: Path) -> None:
    docker = FakeDocker()
    builder = _builder(tmp_path, docker)

    builder.prepare(
        _spec(), _source(tmp_path), tmp_path / "runtime", progress=lambda _value, _phase: None
    )

    create = docker.command_after("create")
    # The single profile run is online only so the client can cache the DRM ticket.
    assert "--network" in create and create[create.index("--network") + 1] == "bridge"
    assert "-offline" not in create[-1]
    assert '"WantsOfflineMode"' in create[-1]
    assert "seccomp=unconfined" in create
    script = create[-1]
    assert '[GCB_PROFILE] script_exit=${profile_status} line=${LINENO}' in script
    assert "-applaunch 250900" in script
    assert "[GCB_PROFILE] profile_created" in script
    assert "[GCB_PROFILE] options_ini_missing" in script
    assert "tail -40 /tmp/steam.log" not in script
    # A launch request sent while the client is still logging on and registering its
    # runtime tools stalls for good, so the script must wait for both before launching.
    launch = script.index("-applaunch 250900")
    assert 0 < script.index("RecvMsgClientLogOnResponse() : processing complete") < launch
    assert 0 < script.index("Posting tool registration callback 1070560") < launch
    assert 0 < script.index("Posting tool registration callback 1391110") < launch
    assert 0 < script.index("sleep 60") < launch
    assert ["rm", "--force", "profile-container"] in docker.calls
    # The ticket lives in the client state, so it has to come back out of the container.
    assert any(
        call[0] == "cp" and call[1].endswith("/.steam/debian-installation/.")
        for call in docker.calls
    )


def test_prepare_drops_a_client_update_the_profile_run_staged(tmp_path: Path) -> None:
    builder = _builder(tmp_path, FakeDocker(profile_stages_client_update=True))

    builder.prepare(
        _spec(), _source(tmp_path), tmp_path / "runtime", progress=lambda _value, _phase: None
    )

    # A networkless client cannot finish a staged update and shuts down instead of launching
    # the game, so only the bare staged manifest goes; the installed client stays.
    package = tmp_path / "runtime/steam-home/debian-installation/package"
    assert sorted(path.name for path in package.iterdir()) == [
        "runtime_scout_ubuntu12.zip.a37e",
        "steam_client_ubuntu12.installed",
        "steam_client_ubuntu12.manifest",
    ]


def test_a_slow_profile_container_removal_does_not_fail_preparation(tmp_path: Path) -> None:
    docker = FakeDocker(removal_times_out=True)
    builder = _builder(tmp_path, docker)

    builder.prepare(
        _spec(), _source(tmp_path), tmp_path / "runtime", progress=lambda _value, _phase: None
    )

    # The profile and client state were copied out before the removal was attempted.
    assert (tmp_path / "runtime/isaac-data/options.ini").is_file()
    assert ["rm", "--force", "profile-container"] in docker.calls


def test_prepare_drops_a_staged_client_update_left_by_an_earlier_preparation(tmp_path: Path) -> None:
    docker = FakeDocker()
    builder = _builder(tmp_path, docker)
    runtime = tmp_path / "runtime"
    installation = runtime / "steam-home/debian-installation"
    shutil.copytree(_source(tmp_path) / ".official-client/steam-home", runtime / "steam-home")
    (runtime / "isaac-data").mkdir(parents=True)
    (runtime / "isaac-data/options.ini").write_text("[Options]\n", encoding="utf-8")
    (installation / "package").mkdir()
    (installation / "package/steam_client_ubuntu12").write_text("staged", encoding="utf-8")
    (installation / "package/steam_client_ubuntu12.manifest").write_text("installed", encoding="utf-8")

    builder.prepare(_spec(), tmp_path / "source", runtime, progress=lambda _value, _phase: None)

    # No new profile run happened, and the staged update still went.
    assert not any(call[0] == "create" for call in docker.calls)
    assert [path.name for path in (installation / "package").iterdir()] == [
        "steam_client_ubuntu12.manifest"
    ]


def test_prepare_requires_a_signed_in_client(tmp_path: Path) -> None:
    builder = _builder(tmp_path, FakeDocker())

    with pytest.raises(RuntimeActionRequired) as error:
        builder.prepare(
            _spec(),
            _source(tmp_path, client=False),
            tmp_path / "runtime",
            progress=lambda _value, _phase: None,
        )

    assert error.value.kind == "steam-client-bootstrap"
    assert "rhenium auth login steam" in str(error.value)


def test_prepare_requires_the_steam_linux_runtime_for_the_offline_profile(tmp_path: Path) -> None:
    builder = _builder(tmp_path, FakeDocker())

    with pytest.raises(RuntimeActionRequired) as error:
        builder.prepare(
            _spec(),
            _source(tmp_path, linux_runtime=False),
            tmp_path / "runtime",
            progress=lambda _value, _phase: None,
        )

    assert "Steam Linux Runtime" in str(error.value)


def test_prepare_fails_closed_when_the_profile_run_produces_nothing(tmp_path: Path) -> None:
    builder = _builder(tmp_path, FakeDocker(profile_writes_options=False))

    with pytest.raises(RuntimeError, match="options.ini"):
        builder.prepare(
            _spec(), _source(tmp_path), tmp_path / "runtime", progress=lambda _value, _phase: None
        )


def test_prepare_reports_safe_profile_failure_markers_and_cleans_up(tmp_path: Path) -> None:
    docker = FakeDocker(
        profile_exit_code=21,
        profile_stdout="private steam log contains access_token=do-not-expose\n",
        profile_stderr=(
            "[GCB_PROFILE] script_exit=21 line=88\n"
            "diagnostic access_token=still-do-not-expose\n"
        ),
    )
    builder = _builder(tmp_path, docker)

    with pytest.raises(RuntimeError) as error:
        builder.prepare(
            _spec(), _source(tmp_path), tmp_path / "runtime", progress=lambda _value, _phase: None
        )

    message = str(error.value)
    assert "exit 21" in message
    assert "[GCB_PROFILE] script_exit=21 line=88" in message
    assert "access_token" not in message
    assert ["rm", "--force", "profile-container"] in docker.calls
