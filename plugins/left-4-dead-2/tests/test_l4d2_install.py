from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (Path(__file__).parents[3] / "benchmarks/l4d2-core/private/runtime/"
          "l4d2-harbor-runtime/install-server.sh")


def test_sourcemod_download_uses_the_official_dotted_release_tag() -> None:
    dockerfile = SCRIPT.with_name("Dockerfile").read_text()
    assert "ARG SOURCEMOD_VERSION=1.12.0-git7246" in dockerfile
    assert "https://sm.alliedmods.net/smdrop/1.12/sourcemod-${SOURCEMOD_VERSION}-linux.tar.gz" in dockerfile
    assert "releases/download/${SOURCEMOD_VERSION/-git/.}/sourcemod-${SOURCEMOD_VERSION}" in dockerfile
    assert "5f5a7a021ba231e03d6698ae4f0dc8c50fca4884b7f399c892b8e964c4754b1c" in dockerfile


@pytest.mark.parametrize("scenario", ["fresh", "permanent", "wrong-build"])
def test_server_install_retries_same_platform_and_never_relaxes_pin(tmp_path: Path, scenario: str) -> None:
    install = tmp_path / "server"
    install.mkdir()
    fake = tmp_path / "steamcmd"
    fake.write_text(f"#!{sys.executable}\n" + """
import json
import os
import sys
from pathlib import Path
assert sys.argv[1::2][:2] == ['+@sSteamCmdForcePlatformType', '+force_install_dir']
assert sys.argv[5:] == ['+login', 'anonymous', '+app_update', '222860', 'validate', '+quit']
root = Path(sys.argv[4])
receipt = root / 'calls.json'
calls = json.loads(receipt.read_text()) if receipt.exists() else []
calls.append(sys.argv[2])
receipt.write_text(json.dumps(calls))
scenario = os.environ['FAKE_SCENARIO']
if scenario == 'permanent' or (scenario == 'fresh' and len(calls) == 1):
    raise SystemExit(8)
(root / 'steamapps').mkdir(exist_ok=True)
build = '1' if scenario == 'wrong-build' else '23990100'
(root / 'steamapps/appmanifest_222860.acf').write_text('"buildid" "' + build + '"')
(root / 'srcds_run').touch()
(root / 'srcds_run').chmod(0o755)
""")
    fake.chmod(0o755)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    sleep = fake_bin / "sleep"
    sleep.write_text("#!/bin/sh\nexit 0\n")
    sleep.chmod(0o755)
    bash = shutil.which("bash")
    assert bash is not None
    env = {**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}", "FAKE_SCENARIO": scenario}
    result = subprocess.run([bash, str(SCRIPT), str(fake), str(install), "23990100"],
                            env=env, capture_output=True, text=True, check=False)
    calls = json.loads((install / "calls.json").read_text())
    if scenario == "fresh":
        assert result.returncode == 0, result.stderr
        assert calls == ["windows", "windows", "linux"]
    elif scenario == "permanent":
        assert result.returncode != 0 and calls == ["windows"] * 3
    else:
        assert result.returncode != 0 and calls == ["windows", "linux"]
