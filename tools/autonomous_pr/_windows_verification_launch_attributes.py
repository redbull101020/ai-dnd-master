"""Dormant x64 startup/creation-attribute ABI (Architecture §13 / Harness §37).

Import is portable and loads no DLL. These checked primitives neither allocate
an attribute list nor own its lifetime or borrowed handles. A future transaction
must pin buffers, track successful initialization, and serialize use/retirement.
There is no process launcher or production integration here.
"""

from __future__ import annotations

import ctypes
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from . import _windows_verification_native as native
from ._windows_verification_native import (
    BOOL,
    DWORD,
    HANDLE,
    SIZE_T,
    WCHAR,
    Category,
    NativePlatform,
    Stage,
    WindowsVerificationError,
    sanitized_error,
)


WORD = ctypes.c_uint16
BYTE = ctypes.c_uint8
DWORD_PTR = ctypes.c_size_t
LPWSTR = ctypes.POINTER(WCHAR)
LPBYTE = ctypes.POINTER(BYTE)
LPPROC_THREAD_ATTRIBUTE_LIST = ctypes.c_void_p  # Opaque, not a guessed layout.

PROC_THREAD_ATTRIBUTE_HANDLE_LIST = 0x00020002
PROC_THREAD_ATTRIBUTE_JOB_LIST = 0x0002000D
EXTENDED_STARTUPINFO_PRESENT = 0x00080000
CREATE_SUSPENDED = 0x00000004
STARTF_USESTDHANDLES = 0x00000100
ERROR_INSUFFICIENT_BUFFER = 122
ATTRIBUTE_COUNT = 2
MAX_ATTRIBUTE_LIST_BYTES = 65_536


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", DWORD),
        ("lpReserved", LPWSTR),
        ("lpDesktop", LPWSTR),
        ("lpTitle", LPWSTR),
        ("dwX", DWORD),
        ("dwY", DWORD),
        ("dwXSize", DWORD),
        ("dwYSize", DWORD),
        ("dwXCountChars", DWORD),
        ("dwYCountChars", DWORD),
        ("dwFillAttribute", DWORD),
        ("dwFlags", DWORD),
        ("wShowWindow", WORD),
        ("cbReserved2", WORD),
        ("lpReserved2", LPBYTE),
        ("hStdInput", HANDLE),
        ("hStdOutput", HANDLE),
        ("hStdError", HANDLE),
    ]


class STARTUPINFOEXW(ctypes.Structure):
    _fields_ = [
        ("StartupInfo", STARTUPINFOW),
        ("lpAttributeList", LPPROC_THREAD_ATTRIBUTE_LIST),
    ]


LPSTARTUPINFOW = ctypes.POINTER(STARTUPINFOW)
LPSTARTUPINFOEXW = ctypes.POINTER(STARTUPINFOEXW)


def validate_abi() -> None:
    """Validate field types as well as the complete portable x64 C layout."""
    native.validate_abi()
    scalar_layouts = (
        (BOOL, 4, 4, True), (DWORD, 4, 4, False),
        (WORD, 2, 2, False), (WCHAR, 2, 2, False),
        (BYTE, 1, 1, False), (SIZE_T, 8, 8, False),
        (DWORD_PTR, 8, 8, False),
    )
    fields = (
        ("cb", DWORD),
        ("lpReserved", ctypes.POINTER(WCHAR)),
        ("lpDesktop", ctypes.POINTER(WCHAR)),
        ("lpTitle", ctypes.POINTER(WCHAR)),
        ("dwX", DWORD), ("dwY", DWORD),
        ("dwXSize", DWORD), ("dwYSize", DWORD),
        ("dwXCountChars", DWORD), ("dwYCountChars", DWORD),
        ("dwFillAttribute", DWORD), ("dwFlags", DWORD),
        ("wShowWindow", WORD), ("cbReserved2", WORD),
        ("lpReserved2", ctypes.POINTER(BYTE)),
        ("hStdInput", HANDLE), ("hStdOutput", HANDLE), ("hStdError", HANDLE),
    )
    layouts = (
        (STARTUPINFOW, 104, fields,
         (0, 8, 16, 24, 32, 36, 40, 44, 48, 52, 56, 60, 64, 66, 72, 80, 88, 96)),
        (STARTUPINFOEXW, 112,
         (("StartupInfo", STARTUPINFOW), ("lpAttributeList", ctypes.c_void_p)),
         (0, 104)),
    )
    valid = (
        ctypes.sizeof(HANDLE) == ctypes.sizeof(ctypes.c_void_p) == 8
        and ctypes.alignment(HANDLE) == 8
        and HANDLE(-1).value == (1 << 64) - 1
        and LPWSTR is ctypes.POINTER(WCHAR)
        and LPBYTE is ctypes.POINTER(BYTE)
        and LPPROC_THREAD_ATTRIBUTE_LIST is ctypes.c_void_p
        and LPSTARTUPINFOW is ctypes.POINTER(STARTUPINFOW)
        and LPSTARTUPINFOEXW is ctypes.POINTER(STARTUPINFOEXW)
        and PROC_THREAD_ATTRIBUTE_HANDLE_LIST == 0x00020002
        and PROC_THREAD_ATTRIBUTE_JOB_LIST == 0x0002000D
        and EXTENDED_STARTUPINFO_PRESENT == 0x00080000
        and CREATE_SUSPENDED == 0x00000004
        and STARTF_USESTDHANDLES == 0x00000100
        and ERROR_INSUFFICIENT_BUFFER == 122
        and ATTRIBUTE_COUNT == 2
        and MAX_ATTRIBUTE_LIST_BYTES == 65_536
    )
    for scalar, size, alignment, signed in scalar_layouts:
        valid = valid and (
            ctypes.sizeof(scalar) == size
            and ctypes.alignment(scalar) == alignment
            and (scalar(-1).value == -1) == signed
        )
    for structure, size, expected_fields, offsets in layouts:
        valid = valid and (
            tuple(structure._fields_) == expected_fields
            and ctypes.sizeof(structure) == size
            and ctypes.alignment(structure) == 8
            and tuple(getattr(structure, name).offset for name, _ in expected_fields)
            == offsets
        )
    if not valid:
        raise WindowsVerificationError(
            Stage.PREFLIGHT, Category.UNSUPPORTED_PLATFORM, cleanup_confirmed=True
        )


def _validate_distinct_handles(values: tuple[int, ...]) -> None:
    # Numeric/structural checks only; these are borrowed values, not OS evidence.
    for value in values:
        native.checked_handle(value, Stage.PREFLIGHT)
    if len(set(values)) != len(values):
        raise WindowsVerificationError(Stage.PREFLIGHT, Category.OWNERSHIP)


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkerLaunchInputs:
    """Closed W input labels; no provenance, rights or membership attestation."""

    supervision_job: int = field(repr=False)
    bootstrap_mapping: int = field(repr=False)

    def __post_init__(self) -> None:
        _validate_distinct_handles((self.supervision_job, self.bootstrap_mapping))


@dataclass(frozen=True, slots=True, kw_only=True)
class PayloadLaunchInputs:
    """Closed payload labels; stream and Job roles remain caller assertions."""

    supervision_job: int = field(repr=False)
    command_job: int = field(repr=False)
    stdin: int = field(repr=False)
    stdout: int = field(repr=False)
    stderr: int = field(repr=False)

    def __post_init__(self) -> None:
        _validate_distinct_handles((
            self.supervision_job, self.command_job, self.stdin, self.stdout, self.stderr,
        ))


class _HandleValues(ctypes.Array):
    """Private persistent HANDLE storage with no Python item-write interface.

    ctypes memory is not a security boundary against arbitrary pointer writes.
    Only the future trusted transaction may borrow these private buffers; no
    public pointer/use interface or initialized attribute resource exists here.
    """

    _type_ = HANDLE
    _length_ = 0

    def __setitem__(self, index: Any, value: Any) -> None:
        raise TypeError("immutable_handle_values")

    def __repr__(self) -> str:
        return "HandleValues()"


class _OneHandleValues(_HandleValues):
    _length_ = 1


class _TwoHandleValues(_HandleValues):
    _length_ = 2


class _ThreeHandleValues(_HandleValues):
    _length_ = 3


@dataclass(frozen=True, slots=True)
class _LaunchAttributeValues:
    """Pins Python storage only; does not own, configure or close OS handles.

    The startup structure is private writable transaction storage. In CP-2a
    its list pointer remains NULL: this is not a prepared attribute resource.
    """

    role: Literal["worker", "payload"]
    _job_values: _HandleValues = field(repr=False)
    _inherited_values: _HandleValues = field(repr=False)
    _startup_info: STARTUPINFOEXW = field(repr=False)


def prepare_worker_values(inputs: WorkerLaunchInputs) -> _LaunchAttributeValues:
    """Prepare W's fixed one-Job/one-mapping values without any native call."""
    if type(inputs) is not WorkerLaunchInputs:
        raise WindowsVerificationError(Stage.PREFLIGHT, Category.OWNERSHIP)
    # Revalidate at the preparation boundary, before narrowing into ctypes,
    # even if a caller bypassed the frozen input object's normal constructor.
    _validate_distinct_handles((inputs.supervision_job, inputs.bootstrap_mapping))
    validate_abi()
    jobs = _OneHandleValues.from_buffer_copy(HANDLE(inputs.supervision_job))
    inherited = _OneHandleValues.from_buffer_copy(HANDLE(inputs.bootstrap_mapping))
    startup = STARTUPINFOEXW()
    startup.StartupInfo.cb = ctypes.sizeof(STARTUPINFOEXW)
    # W has no invented standard-I/O policy; reserved fields/list stay zero.
    return _LaunchAttributeValues("worker", jobs, inherited, startup)


def prepare_payload_values(inputs: PayloadLaunchInputs) -> _LaunchAttributeValues:
    """Prepare fixed supervision/command and stdin/stdout/stderr order only."""
    if type(inputs) is not PayloadLaunchInputs:
        raise WindowsVerificationError(Stage.PREFLIGHT, Category.OWNERSHIP)
    _validate_distinct_handles((
        inputs.supervision_job, inputs.command_job, inputs.stdin, inputs.stdout, inputs.stderr,
    ))
    validate_abi()
    jobs = _TwoHandleValues.from_buffer_copy(
        (HANDLE * 2)(inputs.supervision_job, inputs.command_job)
    )
    inherited = _ThreeHandleValues.from_buffer_copy(
        (HANDLE * 3)(inputs.stdin, inputs.stdout, inputs.stderr)
    )
    startup = STARTUPINFOEXW()
    startup.StartupInfo.cb = ctypes.sizeof(STARTUPINFOEXW)
    startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES
    startup.StartupInfo.hStdInput = inputs.stdin
    startup.StartupInfo.hStdOutput = inputs.stdout
    startup.StartupInfo.hStdError = inputs.stderr
    return _LaunchAttributeValues("payload", jobs, inherited, startup)


class AttributeNativeApi(Protocol):
    def required_size(self) -> int: ...

    def initialize_attribute_list(
        self, attribute_list: ctypes.c_void_p, size: SIZE_T
    ) -> None: ...

    def update_attribute(
        self, attribute_list: ctypes.c_void_p, attribute: int,
        value: ctypes.c_void_p, size: int,
    ) -> None: ...

    def delete_attribute_list(self, attribute_list: ctypes.c_void_p) -> None: ...


def _checked_pointer(value: ctypes.c_void_p, stage: Stage) -> None:
    if type(value) is not ctypes.c_void_p or value.value is None:
        raise WindowsVerificationError(stage, Category.UNCERTAIN_STATE)


class CheckedAttributeApi:
    """Exactly three native symbols, injected independently of the Job API.

    These are low-level primitives, not an allocation/ownership transaction.
    Callers must retain every buffer and arrange deletion after initialization.
    """

    def __init__(self, dll: Any, last_error: Callable[[], int]) -> None:
        validate_abi()
        signatures = (
            ("InitializeProcThreadAttributeList", BOOL,
             [LPPROC_THREAD_ATTRIBUTE_LIST, DWORD, DWORD, ctypes.POINTER(SIZE_T)]),
            ("UpdateProcThreadAttribute", BOOL,
             [LPPROC_THREAD_ATTRIBUTE_LIST, DWORD, DWORD_PTR, ctypes.c_void_p,
              SIZE_T, ctypes.c_void_p, ctypes.POINTER(SIZE_T)]),
            ("DeleteProcThreadAttributeList", None, [LPPROC_THREAD_ATTRIBUTE_LIST]),
        )
        self._last_error = last_error
        functions = []
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
                functions.append(function)
        except Exception as error:
            failure = sanitized_error(error, Stage.PREFLIGHT, Category.OS_API)
            failure.cleanup_confirmed = True
            raise failure from None
        self._initialize, self._update, self._delete = functions

    def _failure(self) -> WindowsVerificationError:
        # First operation after zero BOOL: copy the thread-local error before
        # any further native call (including a future owner's cleanup).
        try:
            code = self._last_error()
        except Exception:
            return WindowsVerificationError(Stage.PREFLIGHT, Category.UNCERTAIN_STATE)
        if type(code) is not int or not 0 <= code <= 0xFFFFFFFF:
            return WindowsVerificationError(Stage.PREFLIGHT, Category.UNCERTAIN_STATE)
        return WindowsVerificationError(Stage.PREFLIGHT, Category.OS_API, winerror=code)

    def _invoke(self, function: Any, stage: Stage, *args: Any) -> Any:
        try:
            return function(*args)
        except Exception as error:
            category = (
                Category.UNCERTAIN_STATE if stage is Stage.CLEANUP else
                Category.RESOURCE if isinstance(error, MemoryError) else Category.OS_API
            )
            raise sanitized_error(error, stage, category) from None

    def _check_status(self, status: object) -> None:
        if type(status) is int and status == 0:
            raise self._failure()
        if type(status) is not int or not -(1 << 31) <= status < (1 << 31):
            raise WindowsVerificationError(Stage.PREFLIGHT, Category.UNCERTAIN_STATE)

    def required_size(self) -> int:
        """Expected sizing failure is not successful initialization."""
        size = SIZE_T()
        status = self._invoke(
            self._initialize, Stage.PREFLIGHT, None, ATTRIBUTE_COUNT, 0, ctypes.byref(size)
        )
        if type(status) is int and status == 0:
            failure = self._failure()
            if failure.winerror != ERROR_INSUFFICIENT_BUFFER:
                raise failure
        else:
            self._check_status(status)
            raise WindowsVerificationError(Stage.PREFLIGHT, Category.UNCERTAIN_STATE)
        if not 0 < size.value <= MAX_ATTRIBUTE_LIST_BYTES:
            raise WindowsVerificationError(Stage.PREFLIGHT, Category.RESOURCE)
        return size.value

    def initialize_attribute_list(
        self, attribute_list: ctypes.c_void_p, size: SIZE_T
    ) -> None:
        """On return initialization succeeded; size remains an in/out scalar.

        The future owner must record that fact BEFORE validating the returned
        size or doing other fallible work, so those failures still delete once.
        """
        _checked_pointer(attribute_list, Stage.PREFLIGHT)
        if type(size) is not SIZE_T or not 0 < size.value <= MAX_ATTRIBUTE_LIST_BYTES:
            raise WindowsVerificationError(Stage.PREFLIGHT, Category.RESOURCE)
        status = self._invoke(
            self._initialize, Stage.PREFLIGHT,
            attribute_list, ATTRIBUTE_COUNT, 0, ctypes.byref(size),
        )
        self._check_status(status)

    def update_attribute(
        self, attribute_list: ctypes.c_void_p, attribute: int,
        value: ctypes.c_void_p, size: int,
    ) -> None:
        _checked_pointer(attribute_list, Stage.PREFLIGHT)
        _checked_pointer(value, Stage.PREFLIGHT)
        if (type(attribute) is not int or attribute not in (
                PROC_THREAD_ATTRIBUTE_JOB_LIST, PROC_THREAD_ATTRIBUTE_HANDLE_LIST)
                or type(size) is not int or not 0 < size < (1 << 64)):
            raise WindowsVerificationError(Stage.PREFLIGHT, Category.UNCERTAIN_STATE)
        status = self._invoke(
            self._update, Stage.PREFLIGHT,
            attribute_list, 0, attribute, value, size, None, None,
        )
        self._check_status(status)

    def delete_attribute_list(self, attribute_list: ctypes.c_void_p) -> None:
        """VOID completion only; no BOOL, last-error query, retry or cleanup claim."""
        _checked_pointer(attribute_list, Stage.CLEANUP)
        self._invoke(self._delete, Stage.CLEANUP, attribute_list)


def load_native_api(
    *,
    _platform: NativePlatform | None = None,
    _dll_loader: Callable[..., Any] | None = None,
    _last_error: Callable[[], int] | None = None,
) -> CheckedAttributeApi:
    """Lazy acquisition only; injectable dependencies keep tests fake on Windows."""
    host = _platform
    if host is None:
        try:
            version = getattr(sys, "getwindowsversion", None)
            host = NativePlatform(
                sys.platform, sys.implementation.name,
                version().major if sys.platform == "win32" and version is not None else 0,
            )
        except Exception as error:
            failure = sanitized_error(error, Stage.PREFLIGHT, Category.OS_API)
            failure.cleanup_confirmed = True
            raise failure from None
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
    return CheckedAttributeApi(dll, reader)
