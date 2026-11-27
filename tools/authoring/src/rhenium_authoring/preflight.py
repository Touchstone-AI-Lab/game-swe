"""Operator-supplied compiler checks, isolated from model credentials and gold code."""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from .models import VerifierBundle


class CheckResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: int
    complete: bool
    findings: list[str]


# Environment forwarded to the trusted checker: process basics plus the
# toolchain locations a Minecraft javac preflight needs. Model credentials
# and every other variable stay out of the child environment.
_FORWARDED_VARIABLES = ("PATH", "LANG", "LC_ALL", "TMPDIR", "SSH_AUTH_SOCK", "JAVA_HOME")
_FORWARDED_PREFIXES = ("RHENIUM_MINECRAFT_",)


def _checker_environment(environ: dict[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in environ.items()
        if key in _FORWARDED_VARIABLES or key.startswith(_FORWARDED_PREFIXES)
    }


class CommandVerifierCheck:
    """JSON stdin/stdout contract; the executable is trusted operator configuration."""

    def __init__(self, executable: Path, receipts: Path, *, timeout: float = 300):
        if executable.is_symlink() or not executable.is_file():
            raise ValueError("verifier check command must be a regular executable file")
        self.executable = executable.resolve()
        self.receipts = receipts
        self.timeout = timeout

    def __call__(self, verifier: VerifierBundle) -> tuple[str, ...]:
        return self.check_files(verifier.files)

    def check_files(self, files: dict[str, str]) -> tuple[str, ...]:
        self.receipts.mkdir(parents=True, exist_ok=True, mode=0o700)
        receipt = self.receipts / f"check-{uuid.uuid4().hex}.json"
        request = {"schema_version": 1, "files": files}
        env = _checker_environment(dict(os.environ))
        try:
            result = subprocess.run(
                [str(self.executable)],
                input=json.dumps(request),
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
                env=env,
            )
            if result.returncode:
                raise RuntimeError("verifier compiler service failed")
            parsed = CheckResponse.model_validate_json(result.stdout)
            if parsed.schema_version != 1 or not parsed.complete:
                raise RuntimeError("verifier compiler service could not complete its check")
            findings = tuple(value[:1000] for value in parsed.findings[:40])
        except (OSError, subprocess.SubprocessError, ValueError, RuntimeError) as error:
            self._save(receipt, {"request": request, "complete": False, "error": type(error).__name__})
            raise RuntimeError("verifier preflight unavailable; no unchecked verifier was accepted") from None
        self._save(receipt, {"request": request, "complete": True, "findings": findings})
        return findings

    @staticmethod
    def _save(path: Path, value: dict[str, object]) -> None:
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        path.chmod(0o600)
