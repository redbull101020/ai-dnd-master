"""Dormant, checked Job-object ABI boundary (Architecture §13 / Harness §37).

Importing this module loads no DLL. Tests use a fake DLL and last-error reader;
real acquisition is lazy and restricted to native 64-bit CPython on Windows 10+.
This is neither a process launcher nor evidence of runtime containment.
"""

from __future__ import annotations

import ctypes
import sys
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol


BOOL = ctypes.c_int32
DWORD = ctypes.c_uint32
WCHAR = ctypes.c_uint16
LARGE_INTEGER = ctypes.c_int64
SIZE_T = ctypes.c_size_t
ULONG_PTR = ctypes.c_size_t
HANDLE = ctypes.c_void_p
JOBOBJECTINFOCLASS = ctypes.c_int32

JobObjectExtendedLimitInformation = 9
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", LARGE_INTEGER),
        ("PerJobUserTimeLimit", LARGE_INTEGER),
        ("LimitFlags", DWORD),
        ("MinimumWorkingSetSize", SIZE_T),
        ("MaximumWorkingSetSize", SIZE_T),
        ("ActiveProcessLimit", DWORD),
        ("Affinity", ULONG_PTR),
        ("PriorityClass", DWORD),
        ("SchedulingClass", DWORD),
    ]


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", SIZE_T),
        ("JobMemoryLimit", SIZE_T),
        ("PeakProcessMemoryUsed", SIZE_T),
        ("PeakJobMemoryUsed", SIZE_T),
    ]


class Stage(str, Enum):
    PREFLIGHT = "preflight"
    JOBS = "jobs"
    CLOSE = "close"
    CLEANUP = "cleanup"


class Category(str, Enum):
    UNSUPPORTED_PLATFORM = "unsupported_platform"
    OS_API = "os_api"
    OWNERSHIP = "ownership"
    INVALID_HANDLE = "invalid_handle"
    RESOURCE = "resource"
    UNCERTAIN_STATE = "uncertain_state"


def _winerror_number(value: object) -> int | None:
    # Do not accept bools, arbitrary objects, or unbounded exception payloads.
    return value if type(value) is int and 0 <= value <= 0xFFFFFFFF else None


def _errno_number(value: object) -> int | None:
    return value if type(value) is int and 0 <= value <= 0x7FFFFFFF else None


@dataclass(frozen=True)
class FailureDiagnostic:
    stage: Stage
    category: Category
    winerror: int | None
    errno: int | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "winerror", _winerror_number(self.winerror))
        object.__setattr__(self, "errno", _errno_number(self.errno))


class WindowsVerificationError(OSError):
    """Bounded internal uncertainty; never contains native text or handles."""

    # OSError's stub assumes a present Windows error is always numeric; this
    # internal cross-platform contract also represents an unavailable error.
    winerror: int | None  # type: ignore[assignment]

    def __init__(
        self,
        stage: Stage,
        category: Category,
        *,
        winerror: int | None = None,
        errno: int | None = None,
        cleanup_confirmed: bool = False,
    ) -> None:
        # Enum conversion rejects non-allowlisted diagnostic strings.
        self.stage = Stage(stage)
        self.category = Category(category)
        super().__init__(f"{self.stage.value}/{self.category.value}")
        self.winerror = _winerror_number(winerror)
        self.errno = _errno_number(errno)
        self.timed_out = False
        self.cleanup_confirmed = cleanup_confirmed
        self.cleanup_failures: tuple[FailureDiagnostic, ...] = ()
        # Filled by the owner on failure; labels/states only, never raw handles.
        self.unresolved_jobs: tuple[str, ...] = ()

    def diagnostic(self) -> FailureDiagnostic:
        return FailureDiagnostic(self.stage, self.category, self.winerror, self.errno)


def sanitized_error(
    error: BaseException, stage: Stage, category: Category
) -> WindowsVerificationError:
    return WindowsVerificationError(
        stage,
        category,
        winerror=getattr(error, "winerror", None),
        errno=getattr(error, "errno", None),
    )


def validate_abi() -> None:
    """Check the complete supported layout without loading any native library."""
    scalar_layouts = (
        (BOOL, 4, 4, True),
        (DWORD, 4, 4, False),
        (WCHAR, 2, 2, False),
        (LARGE_INTEGER, 8, 8, True),
        (SIZE_T, 8, 8, False),
        (ULONG_PTR, 8, 8, False),
        (JOBOBJECTINFOCLASS, 4, 4, True),
        (ctypes.c_uint64, 8, 8, False),
    )
    layouts = (
        (JOBOBJECT_BASIC_LIMIT_INFORMATION, 64, (0, 8, 16, 24, 32, 40, 48, 56, 60)),
        (IO_COUNTERS, 48, (0, 8, 16, 24, 32, 40)),
        (JOBOBJECT_EXTENDED_LIMIT_INFORMATION, 144, (0, 64, 112, 120, 128, 136)),
    )
    valid = (
        ctypes.sizeof(ctypes.c_void_p) == 8
        and ctypes.sizeof(HANDLE) == 8
        and ctypes.alignment(HANDLE) == 8
        and HANDLE(-1).value == (1 << 64) - 1
        and INVALID_HANDLE_VALUE == (1 << 64) - 1
        and JobObjectExtendedLimitInformation == 9
        and JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE == 0x00002000
    )
    for scalar, size, alignment, signed in scalar_layouts:
        valid = valid and (
            ctypes.sizeof(scalar) == size
            and ctypes.alignment(scalar) == alignment
            and (scalar(-1).value == -1) == signed
        )
    for structure, size, offsets in layouts:
        valid = valid and (
            ctypes.sizeof(structure) == size
            and ctypes.alignment(structure) == 8
            and tuple(getattr(structure, field[0]).offset for field in structure._fields_)
            == offsets
        )
    if not valid:
        raise WindowsVerificationError(
            Stage.PREFLIGHT, Category.UNSUPPORTED_PLATFORM, cleanup_confirmed=True
        )


def checked_handle(value: object, stage: Stage) -> int:
    # Fail closed on NULL, signed/pseudo handles, non-integers and overflow.
    if type(value) is not int or not 0 < value < (1 << 63):
        raise WindowsVerificationError(stage, Category.INVALID_HANDLE)
    return value


class JobNativeApi(Protocol):
    def create_job(self) -> int: ...

    def configure_job(self, handle: int) -> None: ...

    def query_job_flags(self, handle: int) -> int: ...

    def close_handle(self, handle: int) -> None: ...


class CheckedJobApi:
    """The four checked calls, with an injectable DLL and ctypes error copy."""

    def __init__(self, dll: Any, last_error: Callable[[], int]) -> None:
        validate_abi()
        signatures = (
            ("CreateJobObjectW", HANDLE, [ctypes.c_void_p, ctypes.POINTER(WCHAR)]),
            ("SetInformationJobObject", BOOL,
             [HANDLE, JOBOBJECTINFOCLASS, ctypes.c_void_p, DWORD]),
            ("QueryInformationJobObject", BOOL,
             [HANDLE, JOBOBJECTINFOCLASS, ctypes.c_void_p, DWORD, ctypes.POINTER(DWORD)]),
            ("CloseHandle", BOOL, [HANDLE]),
        )
        self._last_error = last_error
        try:
            if not callable(last_error):
                raise TypeError
            for name, result, arguments in signatures:
                function = getattr(dll, name)
                if not callable(function):
                    raise TypeError
                function.restype = result
                function.argtypes = arguments
                if function.restype is not result or function.argtypes != arguments:
                    raise TypeError
            self._create = dll.CreateJobObjectW
            self._set = dll.SetInformationJobObject
            self._query = dll.QueryInformationJobObject
            self._close = dll.CloseHandle
        except Exception as error:
            failure = sanitized_error(error, Stage.PREFLIGHT, Category.OS_API)
            failure.cleanup_confirmed = True
            raise failure from None

    def _failure(self, stage: Stage, category: Category) -> WindowsVerificationError:
        # Must be the first operation following a failed native return, before
        # another API/cleanup call can replace ctypes' thread-local error copy.
        try:
            code = self._last_error()
        except Exception:
            return WindowsVerificationError(stage, Category.UNCERTAIN_STATE)
        if _winerror_number(code) is None:
            return WindowsVerificationError(stage, Category.UNCERTAIN_STATE)
        return WindowsVerificationError(stage, category, winerror=code)

    def _invoke(self, function: Any, stage: Stage, *args: Any) -> Any:
        try:
            return function(*args)
        except Exception as error:
            category = Category.UNCERTAIN_STATE if stage is Stage.CLOSE else Category.OS_API
            raise sanitized_error(error, stage, category) from None

    def _check_status(self, status: object, stage: Stage) -> None:
        if type(status) is int and status == 0:
            raise self._failure(
                stage, Category.UNCERTAIN_STATE if stage is Stage.CLOSE else Category.OS_API
            )
        if type(status) is not int or not -(1 << 31) <= status < (1 << 31):
            raise WindowsVerificationError(stage, Category.UNCERTAIN_STATE)

    def create_job(self) -> int:
        value = self._invoke(self._create, Stage.JOBS, None, None)
        try:
            return checked_handle(value, Stage.JOBS)
        except WindowsVerificationError:
            raise self._failure(Stage.JOBS, Category.INVALID_HANDLE)

    def configure_job(self, handle: int) -> None:
        checked_handle(handle, Stage.JOBS)
        limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        status = self._invoke(
            self._set, Stage.JOBS,
            handle, JobObjectExtendedLimitInformation, ctypes.byref(limits),
            ctypes.sizeof(limits),
        )
        self._check_status(status, Stage.JOBS)

    def query_job_flags(self, handle: int) -> int:
        checked_handle(handle, Stage.JOBS)
        limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        returned = DWORD()
        status = self._invoke(
            self._query, Stage.JOBS,
            handle, JobObjectExtendedLimitInformation, ctypes.byref(limits),
            ctypes.sizeof(limits), ctypes.byref(returned),
        )
        self._check_status(status, Stage.JOBS)
        if returned.value != ctypes.sizeof(limits):
            raise WindowsVerificationError(Stage.JOBS, Category.UNCERTAIN_STATE)
        return limits.BasicLimitInformation.LimitFlags

    def close_handle(self, handle: int) -> None:
        checked_handle(handle, Stage.CLOSE)
        self._check_status(self._invoke(self._close, Stage.CLOSE, handle), Stage.CLOSE)


@dataclass(frozen=True)
class NativePlatform:
    platform: str
    implementation: str
    windows_major: int


def load_native_api(
    *,
    _platform: NativePlatform | None = None,
    _dll_loader: Callable[..., Any] | None = None,
    _last_error: Callable[[], int] | None = None,
) -> CheckedJobApi:
    """Acquire bindings only; the private injections allow fake-only preflight."""
    host = _platform
    if host is None:
        version = getattr(sys, "getwindowsversion", None)
        host = NativePlatform(
            sys.platform, sys.implementation.name,
            version().major if sys.platform == "win32" and version is not None else 0,
        )
    if (host.platform != "win32" or host.implementation != "cpython"
            or host.windows_major < 10):
        raise WindowsVerificationError(
            Stage.PREFLIGHT, Category.UNSUPPORTED_PLATFORM, cleanup_confirmed=True
        )
    validate_abi()
    loader = _dll_loader if _dll_loader is not None else getattr(ctypes, "WinDLL", None)
    reader = _last_error if _last_error is not None else getattr(ctypes, "get_last_error", None)
    if not callable(loader) or not callable(reader):
        raise WindowsVerificationError(
            Stage.PREFLIGHT, Category.OS_API, cleanup_confirmed=True
        )
    try:
        dll = loader("kernel32.dll", use_last_error=True)
    except Exception as error:
        failure = sanitized_error(error, Stage.PREFLIGHT, Category.OS_API)
        failure.cleanup_confirmed = True
        raise failure from None
    return CheckedJobApi(dll, reader)
