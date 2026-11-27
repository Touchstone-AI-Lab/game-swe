from __future__ import annotations

import os
import platform
import re
import signal
import subprocess
from pathlib import Path
from typing import Any

from minisweagent.environments.local import LocalEnvironment
from minisweagent.utils.serialize import recursive_merge

_PASSTHROUGH_ENV = {
    "LANG",
    "LC_ALL",
    "NIX_SSL_CERT_FILE",
    "PATH",
    "SSL_CERT_FILE",
    "SYSTEMROOT",
    "TERM",
    "TMPDIR",
}
_SENSITIVE_NAME = re.compile(
    r"(?:^|_)(?:API_?KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIALS?|AUTH(?:ORIZATION)?|COOKIE)"
    r"(?:_|$)",
    re.IGNORECASE,
)
_PRIVATE_PREFIXES = ("RHENIUM_", "MSWEA_", "SSH_", "GPG_")


class WorkspaceEnvironment(LocalEnvironment):
    """A mini-swe-agent local environment that does not expose host credentials.

    It intentionally keeps mini-swe-agent's action and completion protocol while
    replacing LocalEnvironment's full ``os.environ`` inheritance with an allowlist.
    This is credential hygiene, not an operating-system sandbox.
    """

    def __init__(self, *, home: Path, **kwargs: Any):
        super().__init__(**kwargs)
        home.mkdir(parents=True, exist_ok=True)
        inherited = {key: value for key, value in os.environ.items() if key in _PASSTHROUGH_ENV}
        requested = {
            key: value
            for key, value in self.config.env.items()
            if key not in {"HOME", "PWD", "OLDPWD"}
            and not key.upper().startswith(_PRIVATE_PREFIXES)
            and not _SENSITIVE_NAME.search(key)
        }
        self._process_env = inherited | requested | {"HOME": str(home)}

    def execute(self, action: dict, cwd: str = "", *, timeout: int | None = None) -> dict[str, Any]:
        command = str(action.get("command", ""))
        working_directory = cwd or self.config.cwd or os.getcwd()
        try:
            result = _run(command, working_directory, self._process_env, timeout or self.config.timeout)
            output = {"output": result.stdout, "returncode": result.returncode, "exception_info": ""}
        except Exception as error:
            raw_output = getattr(error, "output", None)
            if isinstance(raw_output, bytes):
                raw_output = raw_output.decode("utf-8", errors="replace")
            output = {
                "output": raw_output or "",
                "returncode": -1,
                "exception_info": f"An error occurred while executing the command: {error}",
                "extra": {"exception_type": type(error).__name__, "exception": str(error)},
            }
        self._check_finished(output)
        return output

    def get_template_vars(self, **kwargs: Any) -> dict[str, Any]:
        return recursive_merge(
            self.config.model_dump(),
            platform.uname()._asdict(),
            {"workspace": self.config.cwd},
            kwargs,
        )


def _run(
    command: str,
    cwd: str,
    env: dict[str, str],
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        command,
        shell=True,
        executable="/bin/bash" if Path("/bin/bash").is_file() else None,
        text=True,
        cwd=cwd,
        env=env,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=os.name == "posix",
    )
    try:
        stdout, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:  # pragma: no cover - Windows fallback
            process.kill()
        stdout, _ = process.communicate()
        raise subprocess.TimeoutExpired(command, timeout, output=stdout) from None
    return subprocess.CompletedProcess(command, process.returncode, stdout=stdout)
