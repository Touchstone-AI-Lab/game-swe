from __future__ import annotations

import csv
import ctypes
import os
import queue
import subprocess
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Never


class GmodProcessError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProcessResult:
    process_id: int
    started_at_utc: str
    ended_at_utc: str
    exit_code: int | None
    forced_termination: bool
    timed_out: bool
    duration_seconds: float
    output: str
    job_active_processes: int


if os.name == "nt":
    _kernel32 = ctypes.WinDLL(  # type: ignore[attr-defined, unused-ignore]
        "kernel32", use_last_error=True
    )
    _ULONG_PTR = ctypes.c_size_t
    _INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

    class _SECURITY_ATTRIBUTES(ctypes.Structure):
        _fields_ = [
            ("nLength", wintypes.DWORD),
            ("lpSecurityDescriptor", wintypes.LPVOID),
            ("bInheritHandle", wintypes.BOOL),
        ]

    class _STARTUPINFOW(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("lpReserved", wintypes.LPWSTR),
            ("lpDesktop", wintypes.LPWSTR),
            ("lpTitle", wintypes.LPWSTR),
            ("dwX", wintypes.DWORD),
            ("dwY", wintypes.DWORD),
            ("dwXSize", wintypes.DWORD),
            ("dwYSize", wintypes.DWORD),
            ("dwXCountChars", wintypes.DWORD),
            ("dwYCountChars", wintypes.DWORD),
            ("dwFillAttribute", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("wShowWindow", wintypes.WORD),
            ("cbReserved2", wintypes.WORD),
            ("lpReserved2", ctypes.POINTER(ctypes.c_ubyte)),
            ("hStdInput", wintypes.HANDLE),
            ("hStdOutput", wintypes.HANDLE),
            ("hStdError", wintypes.HANDLE),
        ]

    class _PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("hProcess", wintypes.HANDLE),
            ("hThread", wintypes.HANDLE),
            ("dwProcessId", wintypes.DWORD),
            ("dwThreadId", wintypes.DWORD),
        ]

    class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", _ULONG_PTR),
            ("MaximumWorkingSetSize", _ULONG_PTR),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", _ULONG_PTR),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", _IO_COUNTERS),
            ("ProcessMemoryLimit", _ULONG_PTR),
            ("JobMemoryLimit", _ULONG_PTR),
            ("PeakProcessMemoryUsed", _ULONG_PTR),
            ("PeakJobMemoryUsed", _ULONG_PTR),
        ]

    class _JOBOBJECT_BASIC_ACCOUNTING_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("TotalUserTime", ctypes.c_longlong),
            ("TotalKernelTime", ctypes.c_longlong),
            ("ThisPeriodTotalUserTime", ctypes.c_longlong),
            ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
            ("TotalPageFaultCount", wintypes.DWORD),
            ("TotalProcesses", wintypes.DWORD),
            ("ActiveProcesses", wintypes.DWORD),
            ("TotalTerminatedProcesses", wintypes.DWORD),
        ]

    _kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    _kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    _kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    _kernel32.SetInformationJobObject.restype = wintypes.BOOL
    _kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    _kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    _kernel32.TerminateJobObject.restype = wintypes.BOOL
    _kernel32.QueryInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    _kernel32.QueryInformationJobObject.restype = wintypes.BOOL
    _kernel32.CreatePipe.argtypes = [
        ctypes.POINTER(wintypes.HANDLE),
        ctypes.POINTER(wintypes.HANDLE),
        ctypes.POINTER(_SECURITY_ATTRIBUTES),
        wintypes.DWORD,
    ]
    _kernel32.CreatePipe.restype = wintypes.BOOL
    _kernel32.SetHandleInformation.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD]
    _kernel32.SetHandleInformation.restype = wintypes.BOOL
    _kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(_SECURITY_ATTRIBUTES),
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    _kernel32.CreateFileW.restype = wintypes.HANDLE
    _kernel32.CreateProcessW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        ctypes.POINTER(_SECURITY_ATTRIBUTES),
        ctypes.POINTER(_SECURITY_ATTRIBUTES),
        wintypes.BOOL,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.LPCWSTR,
        ctypes.POINTER(_STARTUPINFOW),
        ctypes.POINTER(_PROCESS_INFORMATION),
    ]
    _kernel32.CreateProcessW.restype = wintypes.BOOL
    _kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
    _kernel32.ResumeThread.restype = wintypes.DWORD
    _kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    _kernel32.WaitForSingleObject.restype = wintypes.DWORD
    _kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    _kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL


def _raise_last_error(action: str) -> Never:
    error = ctypes.get_last_error()  # type: ignore[attr-defined, unused-ignore]
    message = ctypes.FormatError(error)  # type: ignore[attr-defined, unused-ignore]
    raise GmodProcessError(f"{action} failed with Win32 error {error}: {message}")


class WindowsJob:
    """Windows process-tree lifetime control; this is not a security sandbox."""

    _EXTENDED_LIMIT_INFORMATION = 9
    _BASIC_ACCOUNTING_INFORMATION = 1
    _KILL_ON_JOB_CLOSE = 0x00002000

    def __init__(self) -> None:
        if os.name != "nt":
            raise GmodProcessError("Windows Job Objects are only available on Windows")
        self.handle = _kernel32.CreateJobObjectW(None, None)
        if not self.handle:
            _raise_last_error("CreateJobObjectW")
        limits = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        limits.BasicLimitInformation.LimitFlags = self._KILL_ON_JOB_CLOSE
        if not _kernel32.SetInformationJobObject(
            self.handle,
            self._EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        ):
            self.close()
            _raise_last_error("SetInformationJobObject")

    def assign(self, process: wintypes.HANDLE) -> None:
        if not _kernel32.AssignProcessToJobObject(self.handle, process):
            _raise_last_error("AssignProcessToJobObject")

    def terminate(self, exit_code: int = 124) -> None:
        if not _kernel32.TerminateJobObject(self.handle, exit_code):
            _raise_last_error("TerminateJobObject")

    def active_processes(self) -> int:
        value = _JOBOBJECT_BASIC_ACCOUNTING_INFORMATION()
        returned = wintypes.DWORD()
        if not _kernel32.QueryInformationJobObject(
            self.handle,
            self._BASIC_ACCOUNTING_INFORMATION,
            ctypes.byref(value),
            ctypes.sizeof(value),
            ctypes.byref(returned),
        ):
            _raise_last_error("QueryInformationJobObject")
        return int(value.ActiveProcesses)

    def close(self) -> None:
        if getattr(self, "handle", None):
            _kernel32.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self) -> WindowsJob:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def _environment_block(environment: dict[str, str]) -> ctypes.Array[Any]:
    ordered = sorted(environment.items(), key=lambda item: item[0].upper())
    entries = [f"{key}={value}" for key, value in ordered]
    return ctypes.create_unicode_buffer("\0".join(entries) + "\0\0")


def run_process_in_job(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    timeout: float,
) -> ProcessResult:
    """Start suspended, assign to a Job, and consume combined output asynchronously."""
    if os.name != "nt":
        raise GmodProcessError("the GMod process runner requires Windows")
    if not command:
        raise GmodProcessError("process command must not be empty")
    if timeout <= 0:
        raise GmodProcessError("timeout must be positive")

    inherit = _SECURITY_ATTRIBUTES(ctypes.sizeof(_SECURITY_ATTRIBUTES), None, True)
    read_handle = wintypes.HANDLE()
    write_handle = wintypes.HANDLE()
    if not _kernel32.CreatePipe(
        ctypes.byref(read_handle), ctypes.byref(write_handle), ctypes.byref(inherit), 0
    ):
        _raise_last_error("CreatePipe")
    if not _kernel32.SetHandleInformation(read_handle, 1, 0):
        _kernel32.CloseHandle(read_handle)
        _kernel32.CloseHandle(write_handle)
        _raise_last_error("SetHandleInformation")

    console_input = _kernel32.CreateFileW(
        "CONIN$", 0x80000000 | 0x40000000, 3, ctypes.byref(inherit), 3, 0x80, None
    )
    if console_input == _INVALID_HANDLE_VALUE:
        _kernel32.CloseHandle(read_handle)
        _kernel32.CloseHandle(write_handle)
        _raise_last_error("CreateFileW(CONIN$)")

    startup = _STARTUPINFOW()
    startup.cb = ctypes.sizeof(startup)
    startup.dwFlags = 0x00000100
    startup.hStdInput = console_input
    startup.hStdOutput = write_handle
    startup.hStdError = write_handle
    process = _PROCESS_INFORMATION()
    command_line = ctypes.create_unicode_buffer(subprocess.list2cmdline(command))
    environment_buffer = _environment_block(environment)
    flags = 0x00000004 | 0x08000000 | 0x00000400
    started_at_utc = datetime.now(UTC).isoformat()
    created = _kernel32.CreateProcessW(
        command[0],
        command_line,
        None,
        None,
        True,
        flags,
        ctypes.cast(environment_buffer, wintypes.LPVOID),
        str(cwd),
        ctypes.byref(startup),
        ctypes.byref(process),
    )
    _kernel32.CloseHandle(write_handle)
    _kernel32.CloseHandle(console_input)
    if not created:
        _kernel32.CloseHandle(read_handle)
        _raise_last_error("CreateProcessW")

    import msvcrt

    raw_read_handle = read_handle.value
    if raw_read_handle is None:
        _kernel32.TerminateProcess(process.hProcess, 1)
        _kernel32.CloseHandle(process.hThread)
        _kernel32.CloseHandle(process.hProcess)
        _raise_last_error("CreatePipe returned a null read handle")
    binary_flag = getattr(os, "O_BINARY", 0)
    descriptor = msvcrt.open_osfhandle(  # type: ignore[attr-defined, unused-ignore]
        int(raw_read_handle), os.O_RDONLY | binary_flag
    )
    stream = os.fdopen(descriptor, "rb", buffering=0)
    output_queue: queue.SimpleQueue[bytes] = queue.SimpleQueue()

    def read_output() -> None:
        try:
            while chunk := stream.read(65536):
                output_queue.put(chunk)
        finally:
            stream.close()

    reader = threading.Thread(target=read_output, name="gmod-output", daemon=True)
    started = time.monotonic()
    forced = False
    timed_out = False
    exit_code: int | None = None
    active_processes = -1
    try:
        with WindowsJob() as job:
            try:
                job.assign(process.hProcess)
                resumed = _kernel32.ResumeThread(process.hThread)
                if resumed == 0xFFFFFFFF:
                    _raise_last_error("ResumeThread")
                _kernel32.CloseHandle(process.hThread)
                process.hThread = None
                reader.start()

                deadline = started + timeout
                while True:
                    wait_result = _kernel32.WaitForSingleObject(process.hProcess, 50)
                    if wait_result == 0:
                        break
                    if wait_result != 258:
                        raise GmodProcessError(f"WaitForSingleObject returned {wait_result}")
                    if time.monotonic() >= deadline:
                        timed_out = True
                        forced = True
                        job.terminate(124)
                        if _kernel32.WaitForSingleObject(process.hProcess, 10000) != 0:
                            raise GmodProcessError("Job terminated but primary process did not exit")
                        break

                code = wintypes.DWORD()
                if not _kernel32.GetExitCodeProcess(process.hProcess, ctypes.byref(code)):
                    _raise_last_error("GetExitCodeProcess")
                exit_code = int(code.value)
                # srcds can let a short-lived helper outlive the primary process by a few
                # scheduler ticks. Give every process in the Job a bounded opportunity to
                # exit naturally before recording cleanup integrity or closing the Job.
                cleanup_deadline = min(deadline, time.monotonic() + 5.0)
                while job.active_processes() > 0 and time.monotonic() < cleanup_deadline:
                    time.sleep(0.05)
                active_processes = job.active_processes()
            except BaseException:
                if job.active_processes() > 0:
                    forced = True
                    job.terminate(125)
                    _kernel32.WaitForSingleObject(process.hProcess, 10000)
                raise
    finally:
        if process.hThread:
            _kernel32.CloseHandle(process.hThread)
        if process.hProcess:
            _kernel32.CloseHandle(process.hProcess)
        reader.join(timeout=10)
        if reader.is_alive():
            raise GmodProcessError("output reader did not reach EOF after process termination")

    chunks: list[bytes] = []
    while not output_queue.empty():
        chunks.append(output_queue.get())
    output = b"".join(chunks).decode("utf-8", errors="replace")
    return ProcessResult(
        process_id=int(process.dwProcessId),
        started_at_utc=started_at_utc,
        ended_at_utc=datetime.now(UTC).isoformat(),
        exit_code=exit_code,
        forced_termination=forced,
        timed_out=timed_out,
        duration_seconds=round(time.monotonic() - started, 3),
        output=output,
        job_active_processes=active_processes,
    )


def srcds_process_ids() -> set[int]:
    completed = subprocess.run(
        ["tasklist.exe", "/NH", "/FO", "CSV"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )
    result: set[int] = set()
    for row in csv.reader(completed.stdout.splitlines()):
        if len(row) < 2 or not row[0].lower().startswith("srcds"):
            continue
        try:
            result.add(int(row[1]))
        except ValueError:
            continue
    return result
