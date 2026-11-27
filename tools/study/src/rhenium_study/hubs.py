from __future__ import annotations

import fcntl
import os
import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from rhenium.config import Settings
from rhenium.hub import BenchmarkHub

from .inventory import TASKS
from .paths import StudyPaths


@contextmanager
def interprocess_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


@contextmanager
def engine_slot(directory: Path, name: str, slots: int | None = None) -> Iterator[int]:
    """Hold one of ``slots`` evaluation slots for a runtime, waiting when all are taken.

    ``slots`` defaults to ``RHENIUM_STUDY_ENGINE_SLOTS`` (4 when unset); processes that
    share a lock directory should use the same value.

    Every study runtime is a networkless container, so evaluations of one pack do
    not interfere; the slots only bound how many engines run at once.
    """
    if slots is None:
        slots = int(os.environ.get("RHENIUM_STUDY_ENGINE_SLOTS", "4"))
    if slots < 1:
        raise ValueError("an engine needs at least one evaluation slot")
    directory.mkdir(parents=True, exist_ok=True)
    handles = [(directory / f"engine-{name}-{index}.lock").open("a") for index in range(slots)]
    try:
        while True:
            for index, handle in enumerate(handles):
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    continue
                try:
                    yield index
                finally:
                    fcntl.flock(handle, fcntl.LOCK_UN)
                return
            time.sleep(2)
    finally:
        for handle in handles:
            handle.close()


def study_settings(paths: StudyPaths) -> Settings:
    packs = sorted({paths.pack_root(task.pack_dir) for task in TASKS})
    return Settings(
        root=paths.project_root,
        state_dir=paths.state_dir,
        cache_dir=paths.state_dir / "cache",
        # Many lanes write evaluation rows at once; wait for the writer instead of failing.
        database_url=f"sqlite:///{paths.state_dir / 'state.sqlite'}?timeout=300",
        benchmark_paths=tuple(packs),
        web_dist=None,
    )


# The study Hub of this process, per study data directory; see open_hub.
_HUBS: dict[StudyPaths, BenchmarkHub] = {}
_HUBS_GUARD = threading.Lock()


@contextmanager
def starter_lock(paths: StudyPaths) -> Iterator[None]:
    """Hold the host-wide lock under which a study Hub rebuilds the shared starters.

    Constructing a Hub deletes and re-materializes every starter workspace under
    ``hub-state/packs/<game>/<pack>/workspaces/``, and any study process on the host may
    construct one at any time. Code that reads those workspaces, or prepares an attempt
    from its task's starter, holds this lock so it never sees a half-written rebuild.
    It is not reentrant: never call ``open_hub`` while holding it.
    """
    paths.ensure()
    with interprocess_lock(paths.locks / "hub-startup.lock"):
        yield


def open_hub(paths: StudyPaths) -> BenchmarkHub:
    """This process's study Hub, constructed on first use and then reused.

    Construction re-materializes and hashes every starter workspace (tens of seconds)
    under a thread-local lock only, so it runs under ``starter_lock``. Every later
    prepare and evaluation in the process reuses the Hub instead of rebuilding the
    starters under the host-wide lock again. A process therefore loads the task catalogs
    (and the prompts in them) once; the benchmark packs must not change while study
    processes run, and a rebuild by another process writes the same starters.
    """
    with _HUBS_GUARD:
        hub = _HUBS.get(paths)
        if hub is None:
            with starter_lock(paths):
                hub = BenchmarkHub(settings=study_settings(paths))
            _HUBS[paths] = hub
        return hub


def seed_runtime_records(paths: StudyPaths, operator_database: Path) -> list[str]:
    """Copy prepared-runtime records, and nothing else, from the operator Hub.

    A runtime record names immutable local image IDs. Provider sessions are
    never copied: the study evaluates, it does not acquire or prepare.
    """
    open_hub(paths)
    target = paths.state_dir / "state.sqlite"
    source = sqlite3.connect(f"file:{operator_database}?mode=ro", uri=True)
    try:
        rows = source.execute(
            "select runtime_key, fingerprint, provider_id, account_alias, status, artifact_json, "
            "error, created_at, updated_at from runtime_artifacts where status = 'ready'"
        ).fetchall()
    finally:
        source.close()
    destination = sqlite3.connect(target)
    try:
        with destination:
            destination.executemany(
                "insert or replace into runtime_artifacts (runtime_key, fingerprint, provider_id, "
                "account_alias, status, artifact_json, error, created_at, updated_at) "
                "values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
    finally:
        destination.close()
    return sorted(str(row[0]) for row in rows)
