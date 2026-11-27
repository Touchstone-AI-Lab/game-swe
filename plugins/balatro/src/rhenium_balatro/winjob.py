"""Owned child-process cleanup on Windows; not an untrusted-code sandbox.

Microsoft API reference: https://learn.microsoft.com/windows/win32/procthread/job-objects
No breakaway flags are enabled. The child waits on stdin until assignment succeeds.
"""

from __future__ import annotations

import ctypes
import subprocess
import sys
from ctypes import wintypes as w
from typing import Any


def hidden_creation_flags() -> int:
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW
    raise OSError("native Windows required")


def _kernel32() -> Any:
    if sys.platform == "win32":
        return ctypes.WinDLL("kernel32", use_last_error=True)
    raise OSError("native Windows required")


def _last_error() -> int:
    if sys.platform == "win32":
        return ctypes.get_last_error()
    raise OSError("native Windows required")


def _windows_error(code: int) -> OSError:
    if sys.platform == "win32":
        return ctypes.WinError(code)
    return OSError("native Windows required")


class BasicLimits(ctypes.Structure):
    _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                ("flags", w.DWORD), ("min_ws", ctypes.c_size_t), ("max_ws", ctypes.c_size_t),
                ("active_limit", w.DWORD), ("affinity", ctypes.c_size_t),
                ("priority", w.DWORD), ("scheduling", w.DWORD)]


class IOCounts(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in
                ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]


class ExtendedLimits(ctypes.Structure):
    _fields_ = [("basic", BasicLimits), ("io", IOCounts), ("process_mem", ctypes.c_size_t),
                ("job_mem", ctypes.c_size_t), ("peak_process", ctypes.c_size_t),
                ("peak_job", ctypes.c_size_t)]


class Accounting(ctypes.Structure):
    _fields_ = [(name, ctypes.c_longlong) for name in ("user", "kernel", "period_user", "period_kernel")]
    _fields_ += [(name, w.DWORD) for name in ("faults", "total", "active", "terminated")]


class OwnedJob:
    def __init__(self) -> None:
        self.api: Any = _kernel32()
        signatures = {
            "CreateJobObjectW": ([ctypes.c_void_p, w.LPCWSTR], w.HANDLE),
            "SetInformationJobObject": ([w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD], w.BOOL),
            "AssignProcessToJobObject": ([w.HANDLE, w.HANDLE], w.BOOL),
            "QueryInformationJobObject": ([w.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                           w.DWORD, ctypes.c_void_p], w.BOOL),
            "TerminateJobObject": ([w.HANDLE, w.UINT], w.BOOL),
            "CloseHandle": ([w.HANDLE], w.BOOL),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.api, name)
            function.argtypes, function.restype = args, result
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise _windows_error(_last_error())
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            code = _last_error()
            self.close()
            raise _windows_error(code)

    def assign(self, process_handle: int) -> None:
        if not self.api.AssignProcessToJobObject(self.handle, w.HANDLE(process_handle)):
            raise _windows_error(_last_error())

    def active(self) -> int:
        info = Accounting()
        ok = self.api.QueryInformationJobObject(self.handle, 1, ctypes.byref(info), ctypes.sizeof(info), None)
        if not ok:
            raise _windows_error(_last_error())
        return int(info.active)

    def terminate(self) -> None:
        if not self.api.TerminateJobObject(self.handle, 2):
            raise _windows_error(_last_error())

    def close(self) -> None:
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None
