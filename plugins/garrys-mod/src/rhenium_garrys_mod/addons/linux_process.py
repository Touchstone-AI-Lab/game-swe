"""Native Linux process-group lifetime control for trusted maintenance runs.

Like the Windows Job runner, this is not an untrusted-code security boundary.
The Hub's disposable evaluation-host requirement remains authoritative.
"""

from __future__ import annotations

import os
import selectors
import signal
import stat
import subprocess
import sys
import time
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

from .process import GmodProcessError, ProcessResult

MAX_OUTPUT_BYTES = 4 * 1024 * 1024


def _check_console(path: Path, *, required: bool = False) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        if required:
            raise GmodProcessError("native server console log is missing") from None
        return
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise GmodProcessError("native server console log is not a private regular file")
    if info.st_size > MAX_OUTPUT_BYTES:
        raise GmodProcessError("native server console log exceeded the bounded limit")


def read_console(path: Path) -> bytes:
    _check_console(path, required=True)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise GmodProcessError("native server console log changed to an unsafe file")
        value = handle.read(MAX_OUTPUT_BYTES + 1)
    if len(value) > MAX_OUTPUT_BYTES:
        raise GmodProcessError("native server console log exceeded the bounded limit")
    return value


def process_group_members(group: int) -> set[int]:
    """List live members of this runner's own group, never by command substring."""
    if sys.platform != "linux" or not Path("/proc/self/stat").is_file():
        raise GmodProcessError("native Linux process accounting requires procfs")
    members: set[int] = set()
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
        except (FileNotFoundError, ProcessLookupError):
            continue
        if len(fields) < 3:
            raise GmodProcessError("malformed native Linux process accounting")
        if int(fields[2]) == group and fields[0] not in {"Z", "X"}:
            members.add(int(entry.name))
    return members


def _signal_group(group: int, signum: int) -> None:
    if group <= 1 or group == os.getpgrp():
        raise GmodProcessError("refusing to signal an unowned process group")
    with suppress(ProcessLookupError):
        os.killpg(group, signum)


def run_process_group(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    timeout: float,
    console_log: Path | None = None,
) -> ProcessResult:
    if sys.platform != "linux":
        raise GmodProcessError("native Linux runner is only available on Linux")
    if not command or timeout <= 0:
        raise GmodProcessError("a command and positive timeout are required")
    if console_log is not None and os.path.lexists(console_log):
        raise GmodProcessError("native server console log must be fresh for this phase")
    started_at = datetime.now(UTC).isoformat()
    started = time.monotonic()
    deadline = started + timeout
    output = bytearray()
    forced = timed_out = False
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=environment,
        # Keep an owned, empty console pipe open until this phase exits rather
        # than delivering immediate stdin EOF; never inherit the
        # operator's terminal or feed it commands from a submission.
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    assert process.stdout is not None
    group = process.pid
    try:
        with selectors.DefaultSelector() as selector:
            os.set_blocking(process.stdout.fileno(), False)
            selector.register(process.stdout, selectors.EVENT_READ)
            cleanup_deadline: float | None = None
            while True:
                if console_log is not None:
                    _check_console(console_log)
                for key, _ in selector.select(timeout=0.05):
                    chunk = os.read(key.fd, 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                    else:
                        output.extend(chunk)
                        if len(output) > MAX_OUTPUT_BYTES:
                            raise GmodProcessError("native server output exceeded the bounded limit")
                now = time.monotonic()
                exited = process.poll() is not None
                members = process_group_members(group)
                if exited and not members and not selector.get_map():
                    break
                if exited and cleanup_deadline is None:
                    cleanup_deadline = min(deadline, now + 5.0)
                if now >= deadline or (cleanup_deadline is not None and now >= cleanup_deadline):
                    timed_out = now >= deadline
                    forced = True
                    break
    finally:
        # Handles timeout, excess output, reader failures and cancellation too.
        # Only the group created by start_new_session is ever signalled.
        _signal_group(group, signal.SIGKILL)
        process.wait(timeout=10)
        if process.stdin is not None:
            process.stdin.close()
        process.stdout.close()
    cleanup_deadline = time.monotonic() + 5.0
    members = process_group_members(group)
    while members and time.monotonic() < cleanup_deadline:
        time.sleep(0.05)
        members = process_group_members(group)
    if console_log is not None:
        # The stable Linux engine writes Lua console output here rather than
        # forwarding it to stdout. Preserve both streams: duplicate protocol
        # frames still fail the shared exact-one-marker check.
        output.extend(b"\n" + read_console(console_log))
    return ProcessResult(
        process_id=process.pid,
        started_at_utc=started_at,
        ended_at_utc=datetime.now(UTC).isoformat(),
        exit_code=process.returncode,
        forced_termination=forced,
        timed_out=timed_out,
        duration_seconds=round(time.monotonic() - started, 3),
        output=output.decode("utf-8", errors="replace"),
        job_active_processes=len(members),
    )
