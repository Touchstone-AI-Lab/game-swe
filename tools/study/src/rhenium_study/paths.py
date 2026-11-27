from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def find_project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists() and (candidate / "pyproject.toml").is_file():
            return candidate
    raise ValueError("rhenium-study must run inside a Rhenium repository")


@dataclass(frozen=True)
class StudyPaths:
    """Where study data lives. It is always outside the repository: attempts,
    trajectories, logs and the Hub state are local records, never source."""

    project_root: Path
    data_root: Path

    @classmethod
    def load(cls, project_root: Path | None = None) -> StudyPaths:
        root = find_project_root(project_root)
        configured = os.environ.get("RHENIUM_STUDY_DIR")
        data = Path(configured).expanduser() if configured else Path.home() / "Projects" / "game-swe-study"
        data = data.resolve()
        if data == root or data.is_relative_to(root):
            raise ValueError("study data must live outside the repository")
        return cls(project_root=root, data_root=data)

    @property
    def state_dir(self) -> Path:
        return self.data_root / "hub-state"

    @property
    def locks(self) -> Path:
        return self.data_root / "locks"

    @property
    def controls(self) -> Path:
        return self.data_root / "e0" / "controls"

    @property
    def e0_records(self) -> Path:
        return self.data_root / "e0" / "records"

    def e1_study(self, study_id: str) -> Path:
        """The directory of one E1 study: its ``attempts/`` and study-level records."""
        return self.data_root / "e1" / study_id

    def ensure(self) -> None:
        for directory in (self.data_root, self.state_dir, self.locks, self.controls, self.e0_records):
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)

    def pack_root(self, pack_dir: str) -> Path:
        return self.project_root / "benchmarks" / pack_dir

    def study_controls(self, pack_dir: str, task: str) -> Path:
        return self.pack_root(pack_dir) / "private" / "study-controls" / task
