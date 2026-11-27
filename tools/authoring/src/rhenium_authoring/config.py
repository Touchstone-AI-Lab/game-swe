from __future__ import annotations

import stat
import subprocess
import tomllib
import warnings
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ModelSecrets(_StrictModel):
    base_url: str = Field(min_length=1)
    api_key: SecretStr
    review_api_key: SecretStr | None = None
    model: str = Field(default="kimi-k3", min_length=1)
    protocol: Literal["openai", "anthropic"] = "openai"
    verify_tls: bool = True
    reasoning_effort: Literal["low", "medium", "high", "max", "xhigh"] = "low"
    max_tokens: int = Field(default=16_384, ge=1, le=131_072)
    # Read timeout for one model response. Slow reasoning endpoints can take
    # well over ten minutes for a large structured answer.
    timeout_seconds: int = Field(default=600, ge=30, le=3600)


class GitHubSecrets(_StrictModel):
    token: SecretStr | None = None


class CurseForgeSecrets(_StrictModel):
    api_key: SecretStr


class AuthoringSecrets(_StrictModel):
    model: ModelSecrets
    github: GitHubSecrets | None = None
    curseforge: CurseForgeSecrets | None = None

    @property
    def kimi(self) -> ModelSecrets:
        """Deprecated alias for the [model] section; remove after one release."""
        return self.model

    @classmethod
    def load(cls, project_root: Path) -> Self:
        root = project_root.resolve()
        path = root / ".rhenium" / "authoring-secrets.toml"
        if path.is_symlink():
            raise ValueError("authoring secret file must not be a symbolic link")
        if not path.is_file():
            raise ValueError("missing project-local .rhenium/authoring-secrets.toml")
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            raise ValueError("authoring secret file escaped the project root")
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode != 0o600:
            raise ValueError("authoring secret file permissions must be 0600")
        tracked = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "--error-unmatch",
                "--",
                ".rhenium/authoring-secrets.toml",
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if tracked.returncode == 0:
            raise ValueError("authoring secret file must not be tracked by Git")
        try:
            payload = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as error:
            raise ValueError("authoring secret file is unreadable or invalid") from error
        if "kimi" in payload:
            if "model" in payload:
                raise ValueError(
                    "configure either [model] or the deprecated [kimi] section, not both"
                )
            payload["model"] = payload.pop("kimi")
            warnings.warn(
                "the [kimi] secrets section is deprecated; rename it to [model]",
                DeprecationWarning,
                stacklevel=2,
            )
        return cls.model_validate(payload)


def find_project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists() and (candidate / "pyproject.toml").is_file():
            return candidate
    raise ValueError("rhenium-author must run inside a Rhenium repository")
