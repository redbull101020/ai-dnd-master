"""Dormant x64 startup/creation-attribute ABI (Architecture §13 / Harness §37).

Import is portable and loads no DLL. The role-specific transaction owns only an
initialized attribute list and its pinned Python storage, never borrowed handles.
It exposes no process-use interface; future launch must serialize pointer use
against retirement. There is no process launcher or production integration here.
"""

from __future__ import annotations

import ctypes
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Literal, Protocol

from . import _windows_verification_native as native
from ._windows_verification_native import (
    BOOL,
    DWORD,
    HANDLE,
    SIZE_T,
    WCHAR,
    Category,
    FailureDiagnostic,
    NativePlatform,
    Stage,
    WindowsVerificationError,
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
    Only the trusted attribute transaction may borrow these private buffers; no
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

    Pure preparation leaves the private startup list pointer NULL. The checked
    transaction fills it only after both updates; values alone are no resource.
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
        self, attribute_list: ctypes.c_void_p, size: SIZE_T,
        *, _outcome: _InitializationOutcome | None = None,
    ) -> None: ...

    def update_attribute(
        self, attribute_list: ctypes.c_void_p, attribute: int,
        value: ctypes.c_void_p, size: int,
    ) -> None: ...

    def delete_attribute_list(self, attribute_list: ctypes.c_void_p) -> None: ...


def _checked_pointer(value: ctypes.c_void_p, stage: Stage) -> None:
    if type(value) is not ctypes.c_void_p or value.value is None:
        raise WindowsVerificationError(stage, Category.UNCERTAIN_STATE)


def _bounded_exception(
    error: BaseException, stage: Stage, category: Category,
) -> WindowsVerificationError:
    # Wrapper metadata is untrusted too: reading a property may itself raise a
    # BaseException. Never render the source exception or let accessors replace
    # the first failure. The existing error class applies the two numeric ranges.
    try:
        winerror = getattr(error, "winerror", None)
    except BaseException:
        winerror = None
    try:
        errno = getattr(error, "errno", None)
    except BaseException:
        errno = None
    return WindowsVerificationError(stage, category, winerror=winerror, errno=errno)


def _primary_exception(error: BaseException) -> WindowsVerificationError:
    if type(error) is not WindowsVerificationError:
        return _bounded_exception(
            error, Stage.PREFLIGHT,
            Category.RESOURCE if isinstance(error, MemoryError) else Category.UNCERTAIN_STATE,
        )
    # Preserve a canonical checked cause itself, but do not trust the class name
    # alone: injected wrappers can mutate its text, metadata, notes or ranges.
    # This boundary prepares attributes; a wrapper cannot attest another stage
    # or a timeout. No execution/deadline operation occurs here.
    stage = Stage.PREFLIGHT
    category = error.category if type(error.category) is Category else Category.UNCERTAIN_STATE
    bounded = _bounded_exception(error, stage, category)
    notes = getattr(error, "__notes__", None)
    if (error.stage is stage and error.category is category
            and type(error.args) is tuple and len(error.args) == 1
            and type(error.args[0]) is str and error.args == bounded.args
            and error.winerror is bounded.winerror and error.errno is bounded.errno
            and error.strerror is None and error.filename is None and error.filename2 is None
            and (notes is None or type(notes) is list and len(notes) == 0)
            and error.timed_out is False
            and type(error.cleanup_failures) is tuple and len(error.cleanup_failures) == 0
            and type(error.unresolved_jobs) is tuple and len(error.unresolved_jobs) == 0):
        return error
    return bounded


class CheckedAttributeApi:
    """Exactly three native symbols, injected independently of the Job API.

    These are low-level primitives, not an allocation/ownership transaction.
    Callers must retain every buffer and arrange deletion after initialization.
    """

    def __init__(self, dll: Any, last_error: Callable[[], int]) -> None:
        validate_abi()
        signatures: tuple[tuple[str, Any, list[Any]], ...] = (
            ("InitializeProcThreadAttributeList", BOOL,
             [LPPROC_THREAD_ATTRIBUTE_LIST, DWORD, DWORD, ctypes.POINTER(SIZE_T)]),
            ("UpdateProcThreadAttribute", BOOL,
             [LPPROC_THREAD_ATTRIBUTE_LIST, DWORD, DWORD_PTR, ctypes.c_void_p,
              SIZE_T, ctypes.c_void_p, ctypes.POINTER(SIZE_T)]),
            ("DeleteProcThreadAttributeList", None, [LPPROC_THREAD_ATTRIBUTE_LIST]),
        )
        self._last_error = last_error
        functions: list[Any] = []
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
            self._bindings: tuple[tuple[Any, Any, tuple[Any, ...]], ...] = tuple(
                (function, result, tuple(arguments))
                for function, (_, result, arguments) in zip(functions, signatures)
            )
        except BaseException as error:
            failure = _bounded_exception(error, Stage.PREFLIGHT, Category.OS_API)
            failure.cleanup_confirmed = True
            raise failure from None
        self._initialize, self._update, self._delete = functions

    def _failure(self) -> WindowsVerificationError:
        # First operation after zero BOOL: copy the thread-local error before
        # any further native call (including a future owner's cleanup).
        try:
            code = self._last_error()
        except BaseException:
            return WindowsVerificationError(Stage.PREFLIGHT, Category.UNCERTAIN_STATE)
        if type(code) is not int or not 0 <= code <= 0xFFFFFFFF:
            return WindowsVerificationError(Stage.PREFLIGHT, Category.UNCERTAIN_STATE)
        return WindowsVerificationError(Stage.PREFLIGHT, Category.OS_API, winerror=code)

    def _invoke(self, function: Any, stage: Stage, *args: Any) -> Any:
        try:
            # ctypes function signatures are mutable. Check the captured symbol
            # again at each call, against an independent immutable signature.
            for bound, result, arguments in self._bindings:
                if function is bound:
                    actual = function.argtypes
                    if (not callable(function) or function.restype is not result
                            or type(actual) not in (list, tuple)
                            or len(actual) != len(arguments)
                            or any(given is not expected for given, expected in zip(actual, arguments))):
                        raise TypeError
                    break
            else:
                raise TypeError
            return function(*args)
        except BaseException as error:
            category = (
                Category.UNCERTAIN_STATE if stage is Stage.CLEANUP else
                Category.RESOURCE if isinstance(error, MemoryError) else
                Category.OS_API if isinstance(error, Exception) else Category.UNCERTAIN_STATE
            )
            raise _bounded_exception(error, stage, category) from None

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
        self, attribute_list: ctypes.c_void_p, size: SIZE_T,
        *, _outcome: _InitializationOutcome | None = None,
    ) -> None:
        """On return initialization succeeded; size remains an in/out scalar.

        An owned transaction preregisters _outcome; record valid native success
        before returning to fallible Python-side size/setup/publication work.
        """
        _checked_pointer(attribute_list, Stage.PREFLIGHT)
        if type(size) is not SIZE_T or not 0 < size.value <= MAX_ATTRIBUTE_LIST_BYTES:
            raise WindowsVerificationError(Stage.PREFLIGHT, Category.RESOURCE)
        status = self._invoke(
            self._initialize, Stage.PREFLIGHT,
            attribute_list, ATTRIBUTE_COUNT, 0, ctypes.byref(size),
        )
        if type(status) is int and status == 0:
            failure = self._failure()
            if _outcome is not None:
                _outcome.state = "failed"
            raise failure
        if type(status) is int and -(1 << 31) <= status < (1 << 31):
            if _outcome is not None:
                _outcome.state = "initialized"
            return
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
        except BaseException as error:
            failure = _bounded_exception(error, Stage.PREFLIGHT, Category.OS_API)
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
    except BaseException as error:
        failure = _bounded_exception(error, Stage.PREFLIGHT, Category.OS_API)
        failure.cleanup_confirmed = True
        raise failure from None
    return CheckedAttributeApi(dll, reader)


@dataclass(slots=True)
class _InitializationOutcome:
    # Written at the checked native boundary, before returning to the builder.
    # An interrupted/malformed wrapper return cannot prove initialization failed.
    state: Literal["pending", "failed", "initialized"] = "pending"


class _AttributeState(str, Enum):
    BUILDING = "building"
    READY = "ready"
    RETIRING = "retiring"
    RETIRED = "retired"
    UNCERTAIN = "uncertain"


@dataclass(eq=False, slots=True, weakref_slot=True, repr=False)
class _AttributeResource:
    api: AttributeNativeApi
    buffer: ctypes.Array | None
    values: _LaunchAttributeValues | None
    outcome: _InitializationOutcome = field(default_factory=_InitializationOutcome)
    _state: _AttributeState = _AttributeState.BUILDING
    quarantined: bool = False
    lock_failure: FailureDiagnostic | None = None
    initialization_attempted: bool = False
    lock: Any = field(default_factory=Lock)

    @property
    def state(self) -> _AttributeState:
        # A monotonic fail-closed latch is readable without a damaged mutex.
        # Keep the last locked state/claim intact rather than overwriting it
        # unsafely while another caller may still be completing retirement.
        return _AttributeState.UNCERTAIN if self.quarantined else self._state

    @state.setter
    def state(self, state: _AttributeState) -> None:
        self._state = state

    def __repr__(self) -> str:
        return f"AttributeResource(state='{self.state.value}')"


# Register BEFORE initialization, so retaining an uncertain resource never needs
# a fallible insertion during error handling. UNCERTAIN entries are the private
# process-lifetime quarantine; no finalizer, retry or public drain exists.
_RESOURCE_LOCK = Lock()
_PINNED_RESOURCES: set[_AttributeResource] = set()
_UNKNOWN_CLEANUP = FailureDiagnostic(Stage.CLEANUP, Category.UNCERTAIN_STATE, None, None)


def _cleanup_diagnostic(error: BaseException) -> FailureDiagnostic:
    try:
        return _bounded_exception(error, Stage.CLEANUP, Category.UNCERTAIN_STATE).diagnostic()
    except BaseException:
        # A second failure while building secondary diagnostics cannot replace
        # the primary error. This immutable fallback is allocated on import.
        return _UNKNOWN_CLEANUP


@contextmanager
def _resource_guard(resource: _AttributeResource) -> Iterator[None]:
    if resource.quarantined:
        failure = resource.lock_failure or _UNKNOWN_CLEANUP
        raise WindowsVerificationError(
            Stage.CLEANUP, Category.UNCERTAIN_STATE,
            winerror=failure.winerror, errno=failure.errno,
        )
    try:
        leave = resource.lock.__exit__
        resource.lock.__enter__()
    except BaseException as error:
        # Acquisition may have succeeded before the wrapper raised. Never
        # guess lock ownership, release it, or attempt another acquisition.
        resource.quarantined = True
        resource.lock_failure = _cleanup_diagnostic(error)
        raise
    try:
        if resource.quarantined:
            raise WindowsVerificationError(Stage.CLEANUP, Category.UNCERTAIN_STATE)
        yield
    except BaseException as primary:
        try:
            leave(type(primary), primary, primary.__traceback__)
        except BaseException as error:
            resource.quarantined = True
            resource.lock_failure = _cleanup_diagnostic(error)
        # Preserve the body error even if mutex exit failed as well.
        raise
    else:
        try:
            leave(None, None, None)
        except BaseException as error:
            resource.quarantined = True
            resource.lock_failure = _cleanup_diagnostic(error)
            raise


def _register_resource(resource: _AttributeResource) -> None:
    try:
        with _RESOURCE_LOCK:
            _PINNED_RESOURCES.add(resource)
    except BaseException as error:
        resource.quarantined = True
        resource.lock_failure = _cleanup_diagnostic(error)
        raise


def _discard_resource(resource: _AttributeResource) -> None:
    # Used only after confirmed unsuccessful Initialize or normally returned VOID
    # Delete (or before initialization was attempted). No native resource is live.
    with _resource_guard(resource):
        _invalidate_startup(resource)
        resource.buffer = None
        resource.values = None
        resource.state = _AttributeState.RETIRED
    with _RESOURCE_LOCK:
        _PINNED_RESOURCES.discard(resource)


def _invalidate_startup(resource: _AttributeResource) -> None:
    # Invalidate Python-visible startup storage at the irreversible retirement
    # claim, even if Delete later fails. Backing memory itself stays pinned.
    if resource.values is not None:
        resource.values._startup_info.lpAttributeList = None
        resource.values._startup_info.StartupInfo.cb = 0


def _resource_pointer(resource: _AttributeResource) -> ctypes.c_void_p:
    if resource.buffer is None or resource.state not in (
        _AttributeState.BUILDING, _AttributeState.READY, _AttributeState.RETIRING,
    ):
        raise WindowsVerificationError(Stage.PREFLIGHT, Category.OWNERSHIP)
    # Unlike cast(buffer), this pointer creates no independent buffer owner.
    return ctypes.c_void_p(ctypes.addressof(resource.buffer))


def _retire_resource(
    resource: _AttributeResource, *, only_ready: bool,
) -> WindowsVerificationError | None:
    if resource.quarantined:
        return WindowsVerificationError(Stage.CLOSE, Category.OWNERSHIP)
    claimed = False
    try:
        with _resource_guard(resource):
            eligible = resource.state is _AttributeState.READY or (
                not only_ready and resource.state is _AttributeState.BUILDING
            )
            if not eligible or resource.outcome.state != "initialized":
                return WindowsVerificationError(
                    Stage.CLOSE, Category.OWNERSHIP,
                    cleanup_confirmed=resource.state is _AttributeState.RETIRED,
                )
            # Claim and invalidation belong inside the exception boundary too.
            # Release the lock before external code; contenders cannot repeat
            # Delete or mistake an in-flight call for confirmed cleanup.
            claimed = True
            resource.state = _AttributeState.RETIRING
            _invalidate_startup(resource)
        resource.api.delete_attribute_list(_resource_pointer(resource))
        _discard_resource(resource)
    except BaseException as error:
        if claimed:
            resource.quarantined = True
            # Do not reenter fallible invalidation after an invalidation fault.
            # The irreversible state claim blocks use; all storage stays pinned.
        return _bounded_exception(error, Stage.CLEANUP, Category.UNCERTAIN_STATE)
    return None


class PreparedLaunchAttributes:
    """Opaque, fully configured attribute-list owner; no process-use interface.

    Owns only initialized list storage and its Python backing buffers. Job and
    stream handles remain borrowed. Future launch must serialize use against
    retirement explicitly; no pointer, handle getter or transfer exists here.
    """

    __slots__ = ("_resource",)

    def __init__(self, resource: _AttributeResource) -> None:
        if type(resource) is not _AttributeResource:
            raise WindowsVerificationError(Stage.PREFLIGHT, Category.OWNERSHIP)
        if resource.quarantined:
            raise WindowsVerificationError(Stage.PREFLIGHT, Category.OWNERSHIP)
        with _resource_guard(resource):
            if resource.state is not _AttributeState.READY:
                raise WindowsVerificationError(Stage.PREFLIGHT, Category.OWNERSHIP)
        self._resource = resource

    def __repr__(self) -> str:
        return "PreparedLaunchAttributes()"

    @property
    def ownership(self) -> _AttributeState:
        if self._resource.quarantined:
            return _AttributeState.UNCERTAIN
        try:
            with _resource_guard(self._resource):
                return self._resource.state
        except BaseException:
            self._resource.quarantined = True
            return _AttributeState.UNCERTAIN

    def release(self) -> None:
        """One explicit VOID deletion attempt; no OS quiescence claim."""
        failure = _retire_resource(self._resource, only_ready=True)
        if failure is not None:
            raise failure from None


def _allocate_attribute_buffer(size: int) -> ctypes.Array:
    # uint64 storage supplies alignment without guessing the opaque native layout.
    return (ctypes.c_uint64 * ((size + 7) // 8))()


def _complete_startup(resource: _AttributeResource) -> None:
    if resource.values is None:
        raise WindowsVerificationError(Stage.PREFLIGHT, Category.OWNERSHIP)
    startup = resource.values._startup_info
    startup.StartupInfo.cb = ctypes.sizeof(STARTUPINFOEXW)
    startup.lpAttributeList = _resource_pointer(resource).value


def _build_attributes(
    inputs: WorkerLaunchInputs | PayloadLaunchInputs, api: AttributeNativeApi,
    *, role: Literal["worker", "payload"],
) -> PreparedLaunchAttributes:
    resource: _AttributeResource | None = None
    try:
        if role == "worker":
            values = prepare_worker_values(inputs)  # type: ignore[arg-type]
        else:
            values = prepare_payload_values(inputs)  # type: ignore[arg-type]
        for name in ("required_size", "initialize_attribute_list", "update_attribute", "delete_attribute_list"):
            if not callable(getattr(api, name, None)):
                raise WindowsVerificationError(Stage.PREFLIGHT, Category.OS_API)
        required = api.required_size()
        if type(required) is not int or not 0 < required <= MAX_ATTRIBUTE_LIST_BYTES:
            raise WindowsVerificationError(Stage.PREFLIGHT, Category.RESOURCE)
        buffer = _allocate_attribute_buffer(required)
        if (not isinstance(buffer, ctypes.Array)
                or not required <= ctypes.sizeof(buffer) <= MAX_ATTRIBUTE_LIST_BYTES
                or ctypes.addressof(buffer) % 8 != 0
                or any(bytes(buffer))):
            raise WindowsVerificationError(Stage.PREFLIGHT, Category.RESOURCE)
        resource = _AttributeResource(api, buffer, values)
        _register_resource(resource)
        size = SIZE_T(required)
        resource.initialization_attempted = True
        api.initialize_attribute_list(
            _resource_pointer(resource), size, _outcome=resource.outcome,
        )
        if resource.outcome.state != "initialized" or size.value != required:
            raise WindowsVerificationError(Stage.PREFLIGHT, Category.UNCERTAIN_STATE)
        api.update_attribute(
            _resource_pointer(resource), PROC_THREAD_ATTRIBUTE_JOB_LIST,
            ctypes.c_void_p(ctypes.addressof(values._job_values)),
            ctypes.sizeof(values._job_values),
        )
        api.update_attribute(
            _resource_pointer(resource), PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
            ctypes.c_void_p(ctypes.addressof(values._inherited_values)),
            ctypes.sizeof(values._inherited_values),
        )
        _complete_startup(resource)
        with _resource_guard(resource):
            resource.state = _AttributeState.READY
        return PreparedLaunchAttributes(resource)
    except BaseException as error:
        primary = _primary_exception(error)
        try:
            if resource is None:
                primary.cleanup_confirmed = True
            elif resource.quarantined:
                primary.cleanup_failures = (resource.lock_failure or _UNKNOWN_CLEANUP,)
                primary.cleanup_confirmed = False
            elif resource.outcome.state == "initialized":
                secondary = _retire_resource(resource, only_ready=False)
                if secondary is not None:
                    primary.cleanup_failures = (secondary.diagnostic(),)
                primary.cleanup_confirmed = resource.state is _AttributeState.RETIRED
            elif resource.outcome.state == "failed" or not resource.initialization_attempted:
                _discard_resource(resource)
                primary.cleanup_confirmed = True
            else:
                # No confirmed initialization outcome: do not Delete or unpin.
                resource.quarantined = True
                _invalidate_startup(resource)
                primary.cleanup_confirmed = False
        except BaseException as cleanup_error:
            # A bookkeeping/lock-wrapper fault is secondary, including before
            # Initialize. The preregistered resource remains conservatively held.
            if resource is not None:
                resource.quarantined = True
            primary.cleanup_failures = (_cleanup_diagnostic(cleanup_error),)
            primary.cleanup_confirmed = False
        raise primary from None


def prepare_worker_attributes(
    inputs: WorkerLaunchInputs, api: AttributeNativeApi,
) -> PreparedLaunchAttributes:
    return _build_attributes(inputs, api, role="worker")


def prepare_payload_attributes(
    inputs: PayloadLaunchInputs, api: AttributeNativeApi,
) -> PreparedLaunchAttributes:
    return _build_attributes(inputs, api, role="payload")
