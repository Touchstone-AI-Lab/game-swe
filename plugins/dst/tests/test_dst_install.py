from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (Path(__file__).parents[3] / "benchmarks/dst/private/runtime/"
          "dst-harbor-runtime/install-server.sh")


@pytest.mark.parametrize("scenario", ["fresh", "permanent", "wrong-build", "no-binary"])
def test_server_install_retries_and_never_relaxes_the_build_pin(tmp_path: Path, scenario: str) -> None:
    install = tmp_path / "server"
    install.mkdir()
    fake = tmp_path / "steamcmd"
    fake.write_text(f"#!{sys.executable}\n" + """
import json
import os
import sys
from pathlib import Path
assert sys.argv[1:5] == ['+@ShutdownOnFailedCommand', '1', '+@NoPromptForPassword', '1']
assert sys.argv[5] == '+force_install_dir'
assert sys.argv[7:] == ['+login', 'anonymous', '+app_update', '343050', 'validate', '+quit']
root = Path(sys.argv[6])
receipt = root / 'calls.json'
calls = json.loads(receipt.read_text()) if receipt.exists() else []
calls.append('install')
receipt.write_text(json.dumps(calls))
scenario = os.environ['FAKE_SCENARIO']
if scenario == 'permanent' or (scenario == 'fresh' and len(calls) == 1):
    raise SystemExit(8)
(root / 'steamapps').mkdir(exist_ok=True)
build = '1' if scenario == 'wrong-build' else '24700372'
(root / 'steamapps/appmanifest_343050.acf').write_text('"buildid"\\t\\t"' + build + '"')
(root / 'mods').mkdir(exist_ok=True)
if scenario != 'no-binary':
    (root / 'bin64').mkdir(exist_ok=True)
    binary = root / 'bin64/dontstarve_dedicated_server_nullrenderer_x64'
    binary.touch()
    binary.chmod(0o755)
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
    result = subprocess.run([bash, str(SCRIPT), str(fake), str(install), "24700372"],
                            env=env, capture_output=True, text=True, check=False)
    calls = json.loads((install / "calls.json").read_text())
    if scenario == "fresh":
        assert result.returncode == 0, result.stderr
        assert len(calls) == 2
    elif scenario == "permanent":
        assert result.returncode != 0 and len(calls) == 3
    else:
        assert result.returncode != 0 and len(calls) == 1


def test_install_rejects_relative_paths_and_non_numeric_builds(tmp_path: Path) -> None:
    bash = shutil.which("bash")
    assert bash is not None
    for arguments in (["steamcmd", str(tmp_path), "1"], ["/steamcmd", "relative", "1"],
                      ["/steamcmd", str(tmp_path), "latest"]):
        result = subprocess.run([bash, str(SCRIPT), *arguments], capture_output=True, text=True, check=False)
        assert result.returncode == 2
