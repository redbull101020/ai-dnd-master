"""Pure ABI and fake-DLL tests only: no real Windows Job or process calls."""

from __future__ import annotations

import ast
import ctypes
import importlib.util
import sys
from pathlib import Path
from threading import Event, Thread
from typing import Any

import pytest

from tools.autonomous_pr import _windows_verification_native as native
from tools.autonomous_pr._windows_verification_native import (
    Category,
    Stage,
    WindowsVerificationError,
)
from tools.autonomous_pr._windows_verification_jobs import (
    JobLabel,
    OwnershipState,
    PreassignmentJobs,
)


@pytest.fixture(autouse=True)
def forbid_real_native(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("A fake-only test tried to acquire a real Windows API")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", forbidden, raising=False)


class FakeFunction:
    def __init__(self, dll: FakeDLL, name: str) -> None:
        self.dll = dll
        self.name = name
        self.restype: Any = None
        self.argtypes: Any = None

    def __call__(self, *args: Any) -> Any:
        return self.dll.call(self.name, args)


class FakeDLL:
    """Record arguments, limits and ownership, with per-call fault injection."""

    def __init__(self) -> None:
        for name in (
            "CreateJobObjectW", "SetInformationJobObject",
            "QueryInformationJobObject", "CloseHandle",
        ):
            setattr(self, name, FakeFunction(self, name))
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.counts: dict[str, int] = {}
        self.results: dict[tuple[str, int], Any] = {}
        self.error = 0
        self.handles: list[Any] = [0x1100, 0x2200]
        self.owned: set[int] = set()
        self.closed: list[int] = []
        self.limits: dict[int, bytes] = {}
        self.query_flags: dict[int, int] = {}
        self.query_lengths: dict[int, int] = {}

    def last_error(self) -> int:
        self.calls.append(("last_error", ()))
        return self.error

    def call(self, name: str, args: tuple[Any, ...]) -> Any:
        self.calls.append((name, args))
        count = self.counts.get(name, 0) + 1
        self.counts[name] = count
        if (name, count) in self.results:
            result = self.results[(name, count)]
            self.error = 700 + count
            if isinstance(result, BaseException):
                raise result
            return result
        self.error = 900  # Any next API call would destroy the failure code.
        if name == "CreateJobObjectW":
            assert args == (None, None)
            handle = self.handles[count - 1]
            if type(handle) is int and 0 < handle < (1 << 63):
                self.owned.add(handle)
            return handle
        handle = args[0]
        assert handle in self.owned, "attempted native call on foreign/closed handle"
        if name == "CloseHandle":
            assert handle not in self.closed, "attempted double close"
            self.closed.append(handle)
            self.owned.remove(handle)
            return 1
        assert args[1] == 9
        assert args[3] == 144
        pointer = ctypes.cast(args[2], ctypes.POINTER(native.JOBOBJECT_EXTENDED_LIMIT_INFORMATION))
        if name == "SetInformationJobObject":
            self.limits[handle] = bytes(pointer.contents)
        else:
            ctypes.memmove(args[2], self.limits[handle], 144)
            pointer.contents.BasicLimitInformation.LimitFlags = self.query_flags.get(handle, 0x2000)
            ctypes.cast(args[4], ctypes.POINTER(native.DWORD)).contents.value = self.query_lengths.get(handle, 144)
        return 1


def api(dll: FakeDLL) -> native.CheckedJobApi:
    return native.CheckedJobApi(dll, dll.last_error)


def test_exact_portable_win32_layouts_and_signedness() -> None:
    native.validate_abi()
    for scalar, size, signed in (
        (native.BOOL, 4, True), (native.DWORD, 4, False),
        (native.WCHAR, 2, False), (native.LARGE_INTEGER, 8, True),
        (native.SIZE_T, 8, False), (native.ULONG_PTR, 8, False),
        (native.JOBOBJECTINFOCLASS, 4, True),
    ):
        assert ctypes.sizeof(scalar) == size
        assert (scalar(-1).value == -1) is signed
    assert ctypes.sizeof(native.HANDLE) == ctypes.sizeof(ctypes.c_void_p) == 8
    for structure, size, offsets in (
        (native.JOBOBJECT_BASIC_LIMIT_INFORMATION, 64, (0, 8, 16, 24, 32, 40, 48, 56, 60)),
        (native.IO_COUNTERS, 48, (0, 8, 16, 24, 32, 40)),
        (native.JOBOBJECT_EXTENDED_LIMIT_INFORMATION, 144, (0, 64, 112, 120, 128, 136)),
    ):
        assert ctypes.sizeof(structure) == size
        assert ctypes.alignment(structure) == 8
        assert tuple(getattr(structure, name).offset for name, _ in structure._fields_) == offsets
    assert native.JobObjectExtendedLimitInformation == 9
    assert native.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE == 0x2000


def test_all_four_function_signatures_and_full_zero_initialized_buffer() -> None:
    dll = FakeDLL()
    checked = api(dll)
    expected = {
        "CreateJobObjectW": (native.HANDLE, [ctypes.c_void_p, ctypes.POINTER(native.WCHAR)]),
        "SetInformationJobObject": (native.BOOL, [native.HANDLE, native.JOBOBJECTINFOCLASS, ctypes.c_void_p, native.DWORD]),
        "QueryInformationJobObject": (native.BOOL, [native.HANDLE, native.JOBOBJECTINFOCLASS, ctypes.c_void_p, native.DWORD, ctypes.POINTER(native.DWORD)]),
        "CloseHandle": (native.BOOL, [native.HANDLE]),
    }
    for name, (result, arguments) in expected.items():
        assert getattr(dll, name).restype is result
        assert getattr(dll, name).argtypes == arguments
    handle = checked.create_job()
    checked.configure_job(handle)
    assert checked.query_job_flags(handle) == 0x2000
    limits = native.JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    limits.BasicLimitInformation.LimitFlags = 0x2000
    assert dll.limits[handle] == bytes(limits)
    assert dll.limits[handle][:16] == bytes(16)
    assert dll.limits[handle][20:] == bytes(124)
    checked.close_handle(handle)
    assert dll.owned == set()


@pytest.mark.parametrize("function", ["CreateJobObjectW", "SetInformationJobObject", "QueryInformationJobObject", "CloseHandle"])
def test_failure_captures_ctypes_error_copy_immediately(function: str) -> None:
    dll = FakeDLL()
    checked = api(dll)
    if function == "CreateJobObjectW":
        operation = checked.create_job
    else:
        handle = checked.create_job()
        checked.configure_job(handle)
        operation = lambda: {
            "SetInformationJobObject": checked.configure_job,
            "QueryInformationJobObject": checked.query_job_flags,
            "CloseHandle": checked.close_handle,
        }[function](handle)
    ordinal = dll.counts.get(function, 0) + 1
    dll.results[(function, ordinal)] = 0
    with pytest.raises(WindowsVerificationError) as caught:
        operation()
    assert caught.value.winerror == 700 + ordinal
    assert [call[0] for call in dll.calls[-2:]] == [function, "last_error"]
    assert caught.value.timed_out is False


@pytest.mark.parametrize("status", [None, True, "secret native transcript", 1 << 32, -(1 << 32)])
def test_unexpected_bool_status_is_terminal(status: object) -> None:
    dll = FakeDLL()
    checked = api(dll)
    handle = checked.create_job()
    dll.results[("SetInformationJobObject", 1)] = status
    with pytest.raises(WindowsVerificationError) as caught:
        checked.configure_job(handle)
    assert caught.value.category is Category.UNCERTAIN_STATE
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize("status", [1, 2, -1, (1 << 31) - 1])
def test_win32_bool_accepts_any_valid_nonzero_int(status: int) -> None:
    dll = FakeDLL()
    checked = api(dll)
    handle = checked.create_job()
    dll.results[("SetInformationJobObject", 1)] = status
    checked.configure_job(handle)


@pytest.mark.parametrize("length", [0, 64, 143, 145, 0xFFFFFFFF])
def test_query_return_length_must_cover_exact_extended_structure(length: int) -> None:
    dll = FakeDLL()
    checked = api(dll)
    handle = checked.create_job()
    checked.configure_job(handle)
    dll.query_lengths[handle] = length
    with pytest.raises(WindowsVerificationError) as caught:
        checked.query_job_flags(handle)
    assert caught.value.category is Category.UNCERTAIN_STATE


@pytest.mark.parametrize("platform", [
    native.NativePlatform("linux", "cpython", 0),
    native.NativePlatform("darwin", "cpython", 0),
    native.NativePlatform("win32", "pypy", 10),
    native.NativePlatform("win32", "cpython", 6),
])
def test_unsupported_platform_fails_before_dll_acquisition(platform: native.NativePlatform) -> None:
    with pytest.raises(WindowsVerificationError) as caught:
        native.load_native_api(_platform=platform)
    assert caught.value.stage is Stage.PREFLIGHT
    assert caught.value.category is Category.UNSUPPORTED_PLATFORM
    assert caught.value.cleanup_confirmed is True


def test_lazy_windows_loader_is_entirely_fake_and_uses_error_copy() -> None:
    dll = FakeDLL()
    calls = []

    def loader(name: str, *, use_last_error: bool) -> FakeDLL:
        calls.append((name, use_last_error))
        return dll

    checked = native.load_native_api(
        _platform=native.NativePlatform("win32", "cpython", 10),
        _dll_loader=loader, _last_error=dll.last_error,
    )
    assert isinstance(checked, native.CheckedJobApi)
    assert calls == [("kernel32.dll", True)]
    assert dll.calls == []


@pytest.mark.parametrize("missing", ["CreateJobObjectW", "SetInformationJobObject", "QueryInformationJobObject", "CloseHandle"])
def test_missing_function_fails_without_any_job_call(missing: str) -> None:
    dll = FakeDLL()
    delattr(dll, missing)
    with pytest.raises(WindowsVerificationError) as caught:
        api(dll)
    assert caught.value.stage is Stage.PREFLIGHT
    assert caught.value.cleanup_confirmed is True
    assert dll.calls == []


@pytest.mark.parametrize("bad_constant", ["JobObjectExtendedLimitInformation", "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE"])
def test_abi_and_flag_rejection_precedes_any_native_call(monkeypatch: pytest.MonkeyPatch, bad_constant: str) -> None:
    dll = FakeDLL()
    monkeypatch.setattr(native, bad_constant, 0)
    with pytest.raises(WindowsVerificationError):
        api(dll)
    assert dll.calls == []


def test_injected_pointer_width_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    original = ctypes.sizeof
    monkeypatch.setattr(ctypes, "sizeof", lambda value: 4 if value is ctypes.c_void_p else original(value))
    dll = FakeDLL()
    with pytest.raises(WindowsVerificationError):
        api(dll)
    assert dll.calls == []


def test_non_windows_import_has_no_dll_or_error_reader_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(ctypes, "WinDLL", raising=False)
    monkeypatch.delattr(ctypes, "get_last_error", raising=False)
    # A fresh module namespace tests actual import without reloading the classes
    # used by the rest of this test suite.
    name = "tools.autonomous_pr._windows_verification_native_import_test"
    spec = importlib.util.spec_from_file_location(name, native.__file__)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    module.validate_abi()
    with pytest.raises(OSError):
        module.load_native_api(_platform=module.NativePlatform("linux", "cpython", 0))


def test_dormant_modules_are_not_imported_by_production_dispatch() -> None:
    root = Path(__file__).resolve().parents[3] / "tools" / "autonomous_pr"
    for path in root.glob("*.py"):
        if path.name.startswith("_windows_verification_"):
            continue
        source = path.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                assert "_windows_verification_" not in ast.get_source_segment(source, node)


def close_attempts(dll: FakeDLL) -> list[int]:
    return [args[0] for name, args in dll.calls if name == "CloseHandle"]


def test_owned_pair_success_is_ordered_unnamed_empty_and_retired_once() -> None:
    dll = FakeDLL()
    pair = PreassignmentJobs(api(dll))
    assert [(job.label, job.state) for job in pair.ownership] == [
        (JobLabel.SUPERVISION, OwnershipState.OWNED_PREASSIGNMENT),
        (JobLabel.COMMAND, OwnershipState.OWNED_PREASSIGNMENT),
    ]
    assert not hasattr(pair, "close")
    assert not hasattr(pair, "handles")
    assert all(not hasattr(job, "handle") for job in pair.ownership)
    assert dll.owned == {0x1100, 0x2200}
    assert list(dll.limits) == [0x1100, 0x2200]
    pair.release_preassignment()
    assert [name for name, _ in dll.calls] == [
        "CreateJobObjectW", "SetInformationJobObject", "QueryInformationJobObject",
        "CreateJobObjectW", "SetInformationJobObject", "QueryInformationJobObject",
        "CloseHandle", "CloseHandle",
    ]
    assert close_attempts(dll) == [0x2200, 0x1100]
    assert dll.owned == set()
    assert all(job.state is OwnershipState.CONFIRMED_CLOSED for job in pair.ownership)
    with pytest.raises(WindowsVerificationError) as caught:
        pair.release_preassignment()
    assert caught.value.category is Category.OWNERSHIP
    assert caught.value.cleanup_confirmed is True
    assert close_attempts(dll) == [0x2200, 0x1100]


ACQUISITION_FAILURES = [
    ("CreateJobObjectW", 1, []),
    ("SetInformationJobObject", 1, [0x1100]),
    ("QueryInformationJobObject", 1, [0x1100]),
    ("CreateJobObjectW", 2, [0x1100]),
    ("SetInformationJobObject", 2, [0x2200, 0x1100]),
    ("QueryInformationJobObject", 2, [0x2200, 0x1100]),
]


@pytest.mark.parametrize("function,ordinal,owned,close_faults", [
    (function, ordinal, owned, faults)
    for function, ordinal, owned in ACQUISITION_FAILURES
    for faults in ((), (1,), (2,), (1, 2))
    if all(index <= len(owned) for index in faults)
])
def test_every_failed_stage_and_cleanup_partial_order(
    function: str, ordinal: int, owned: list[int], close_faults: tuple[int, ...],
) -> None:
    dll = FakeDLL()
    dll.results[(function, ordinal)] = 0
    for index in close_faults:
        dll.results[("CloseHandle", index)] = 0
    with pytest.raises(WindowsVerificationError) as caught:
        PreassignmentJobs(api(dll))
    primary = caught.value
    assert primary.stage is Stage.JOBS
    assert primary.category is (
        Category.INVALID_HANDLE if function == "CreateJobObjectW" else Category.OS_API
    )
    assert primary.winerror == 700 + ordinal  # Cleanup did not replace the cause.
    assert primary.cleanup_confirmed is (not close_faults)
    assert close_attempts(dll) == owned
    assert dll.closed == [handle for index, handle in enumerate(owned, 1) if index not in close_faults]
    assert dll.owned == {handle for index, handle in enumerate(owned, 1) if index in close_faults}
    assert [failure.winerror for failure in primary.cleanup_failures] == [700 + index for index in close_faults]
    assert all(failure.stage is Stage.CLEANUP for failure in primary.cleanup_failures)
    assert len(primary.unresolved_jobs) == len(close_faults)
    for index, (name, _) in enumerate(dll.calls):
        if name == "last_error":
            assert dll.calls[index - 1][0] in {function, "CloseHandle"}


@pytest.mark.parametrize("faults", [(1,), (2,), (1, 2)])
def test_close_uncertainty_retains_unresolved_owner_and_never_retries(faults: tuple[int, ...]) -> None:
    dll = FakeDLL()
    pair = PreassignmentJobs(api(dll))
    for index in faults:
        dll.results[("CloseHandle", index)] = 0
    with pytest.raises(WindowsVerificationError) as caught:
        pair.release_preassignment()
    primary = caught.value
    assert primary.stage is Stage.CLOSE
    assert primary.category is Category.UNCERTAIN_STATE
    assert primary.winerror == 700 + faults[0]
    assert primary.cleanup_confirmed is False
    assert [error.winerror for error in primary.cleanup_failures] == [700 + index for index in faults[1:]]
    assert close_attempts(dll) == [0x2200, 0x1100]
    expected = {
        JobLabel.COMMAND: OwnershipState.UNCERTAIN_CLOSE if 1 in faults else OwnershipState.CONFIRMED_CLOSED,
        JobLabel.SUPERVISION: OwnershipState.UNCERTAIN_CLOSE if 2 in faults else OwnershipState.CONFIRMED_CLOSED,
    }
    assert {job.label: job.state for job in pair.ownership} == expected
    assert set(primary.unresolved_jobs) == {label.value for label, state in expected.items() if state is OwnershipState.UNCERTAIN_CLOSE}
    with pytest.raises(WindowsVerificationError) as repeated:
        pair.release_preassignment()
    assert repeated.value.category is Category.OWNERSHIP
    assert repeated.value.cleanup_confirmed is False
    assert close_attempts(dll) == [0x2200, 0x1100]


@pytest.mark.parametrize("invalid", [None, 0, -1, -2, (1 << 64) - 1, 1 << 64, 1 << 63, True, "native secret", 1.5])
@pytest.mark.parametrize("ordinal", [1, 2])
def test_invalid_handle_never_becomes_an_owner_or_gets_closed(invalid: object, ordinal: int) -> None:
    dll = FakeDLL()
    dll.handles[ordinal - 1] = invalid
    with pytest.raises(WindowsVerificationError) as caught:
        PreassignmentJobs(api(dll))
    assert caught.value.category is Category.INVALID_HANDLE
    assert caught.value.cleanup_confirmed is True
    assert close_attempts(dll) == ([] if ordinal == 1 else [0x1100])
    assert dll.owned == set()
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize("close_fails", [False, True])
def test_duplicate_handle_keeps_original_owner_and_closes_alias_only_once(close_fails: bool) -> None:
    dll = FakeDLL()
    dll.handles = [0x1100, 0x1100]
    if close_fails:
        dll.results[("CloseHandle", 1)] = 0
    with pytest.raises(WindowsVerificationError) as caught:
        PreassignmentJobs(api(dll))
    assert caught.value.category is Category.OWNERSHIP
    assert close_attempts(dll) == [0x1100]
    assert dll.counts["SetInformationJobObject"] == 1
    assert caught.value.cleanup_confirmed is (not close_fails)
    assert caught.value.unresolved_jobs == (("J_supervision",) if close_fails else ())


@pytest.mark.parametrize("handle", [0x1100, 0x2200])
@pytest.mark.parametrize("flags", [0, 0x800, 0x1000, 0x2800, 0x3000, 0x2001, 0xFFFFFFFF])
def test_readback_must_have_exact_kill_on_close_and_no_breakaway(handle: int, flags: int) -> None:
    dll = FakeDLL()
    dll.query_flags[handle] = flags
    with pytest.raises(WindowsVerificationError) as caught:
        PreassignmentJobs(api(dll))
    assert caught.value.category is Category.UNCERTAIN_STATE
    assert close_attempts(dll) == ([0x1100] if handle == 0x1100 else [0x2200, 0x1100])
    assert caught.value.cleanup_confirmed is True
    assert dll.owned == set()


@pytest.mark.parametrize("handle", [0x1100, 0x2200])
def test_incomplete_query_rolls_back_all_acquired_handles(handle: int) -> None:
    dll = FakeDLL()
    dll.query_lengths[handle] = 64
    with pytest.raises(WindowsVerificationError) as caught:
        PreassignmentJobs(api(dll))
    assert caught.value.category is Category.UNCERTAIN_STATE
    assert caught.value.cleanup_confirmed is True
    assert close_attempts(dll) == ([0x1100] if handle == 0x1100 else [0x2200, 0x1100])


def test_original_checked_primary_is_preserved_when_cleanup_fails() -> None:
    dll = FakeDLL()
    original = WindowsVerificationError(Stage.JOBS, Category.OS_API, winerror=87)

    class FailingApi(native.CheckedJobApi):
        def configure_job(self, handle: int) -> None:
            raise original

    dll.results[("CloseHandle", 1)] = 0
    with pytest.raises(WindowsVerificationError) as caught:
        PreassignmentJobs(FailingApi(dll, dll.last_error))
    assert caught.value is original
    assert original.winerror == 87
    assert original.cleanup_failures[0].winerror == 701
    assert original.cleanup_confirmed is False


@pytest.mark.parametrize("function,ordinal,owned", ACQUISITION_FAILURES[1:])
def test_unexpected_exception_is_sanitized_and_owned_handles_still_retire(
    function: str, ordinal: int, owned: list[int],
) -> None:
    dll = FakeDLL()
    dll.results[(function, ordinal)] = OSError(5, "SECRET argv/path/env/handle transcript")
    with pytest.raises(WindowsVerificationError) as caught:
        PreassignmentJobs(api(dll))
    assert "SECRET" not in str(caught.value)
    assert "SECRET" not in repr(caught.value.diagnostic())
    assert caught.value.errno == 5
    assert caught.value.cleanup_confirmed is True
    assert close_attempts(dll) == owned


def test_exception_during_close_does_not_prevent_remaining_attempt() -> None:
    dll = FakeDLL()
    pair = PreassignmentJobs(api(dll))
    dll.results[("CloseHandle", 1)] = OSError(6, "SECRET close transcript")
    with pytest.raises(WindowsVerificationError) as caught:
        pair.release_preassignment()
    assert caught.value.errno == 6
    assert caught.value.cleanup_confirmed is False
    assert close_attempts(dll) == [0x2200, 0x1100]
    assert dll.closed == [0x1100]
    assert "SECRET" not in str(caught.value)


def test_reentrant_release_cannot_repeat_a_close_attempt() -> None:
    dll = FakeDLL()
    checked = api(dll)
    pair = PreassignmentJobs(checked)
    original = checked.close_handle

    def reentrant(handle: int) -> None:
        assert any(job.state is OwnershipState.CLOSE_ATTEMPTED for job in pair.ownership)
        with pytest.raises(WindowsVerificationError) as caught:
            pair.release_preassignment()
        assert caught.value.category is Category.OWNERSHIP
        original(handle)

    checked.close_handle = reentrant
    pair.release_preassignment()
    assert close_attempts(dll) == [0x2200, 0x1100]


def test_native_call_surface_stays_limited_to_the_four_reviewed_functions() -> None:
    source = Path(native.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = {"CreateProcessW", "ResumeThread", "AssignProcessToJobObject", "TerminateJobObject", "IsProcessInJob", "DuplicateHandle"}
    assert not any(isinstance(node, ast.Attribute) and node.attr in forbidden for node in ast.walk(tree))
    pair_source = Path(sys.modules[PreassignmentJobs.__module__].__file__).read_text(encoding="utf-8")
    assert "subprocess" not in pair_source
    assert "load_native_api" not in pair_source


@pytest.mark.parametrize("missing", ["WinDLL", "get_last_error"])
def test_missing_ctypes_windows_facility_fails_before_loading_dll(
    monkeypatch: pytest.MonkeyPatch, missing: str,
) -> None:
    monkeypatch.delattr(ctypes, missing)
    with pytest.raises(WindowsVerificationError) as caught:
        native.load_native_api(_platform=native.NativePlatform("win32", "cpython", 10))
    assert caught.value.stage is Stage.PREFLIGHT
    assert caught.value.category is Category.OS_API
    assert caught.value.cleanup_confirmed is True


def test_loader_exception_is_bounded_and_has_no_acquired_resources() -> None:
    def failed_loader(*args: object, **kwargs: object) -> None:
        raise OSError(5, "SECRET loader path")

    with pytest.raises(WindowsVerificationError) as caught:
        native.load_native_api(
            _platform=native.NativePlatform("win32", "cpython", 10),
            _dll_loader=failed_loader, _last_error=lambda: 0,
        )
    assert caught.value.errno == 5
    assert caught.value.cleanup_confirmed is True
    assert caught.value.__suppress_context__ is True
    assert "SECRET" not in str(caught.value)


@pytest.mark.parametrize("symbol,replacement", [
    ("BOOL", ctypes.c_uint32), ("DWORD", ctypes.c_int32),
    ("WCHAR", ctypes.c_uint32), ("LARGE_INTEGER", ctypes.c_uint64),
])
def test_incorrect_scalar_width_or_signedness_blocks_binding(
    monkeypatch: pytest.MonkeyPatch, symbol: str, replacement: type,
) -> None:
    monkeypatch.setattr(native, symbol, replacement)
    dll = FakeDLL()
    with pytest.raises(WindowsVerificationError):
        api(dll)
    assert dll.calls == []


def test_incorrect_structure_alignment_blocks_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    class Misaligned(ctypes.Structure):
        _fields_ = [("bytes", ctypes.c_uint8 * 144)]

    monkeypatch.setattr(native, "JOBOBJECT_EXTENDED_LIMIT_INFORMATION", Misaligned)
    dll = FakeDLL()
    with pytest.raises(WindowsVerificationError):
        api(dll)
    assert dll.calls == []


def test_binding_that_does_not_retain_signature_fails_preflight() -> None:
    class BrokenFunction:
        def __call__(self, *args: object) -> None:
            pytest.fail("A function with an invalid signature was invoked")

        def __setattr__(self, name: str, value: object) -> None:
            pass

    dll = FakeDLL()
    dll.CreateJobObjectW = BrokenFunction()
    with pytest.raises(WindowsVerificationError) as caught:
        api(dll)
    assert caught.value.stage is Stage.PREFLIGHT
    assert dll.calls == []


@pytest.mark.parametrize("reader_result", [None, True, -1, 1 << 40, "SECRET", OSError("SECRET")])
def test_unavailable_or_invalid_last_error_keeps_failure_and_still_cleans_up(reader_result: object) -> None:
    dll = FakeDLL()
    dll.results[("SetInformationJobObject", 1)] = 0

    def reader() -> Any:
        if isinstance(reader_result, Exception):
            raise reader_result
        return reader_result

    with pytest.raises(WindowsVerificationError) as caught:
        PreassignmentJobs(native.CheckedJobApi(dll, reader))
    assert caught.value.category is Category.UNCERTAIN_STATE
    assert caught.value.winerror is None
    assert caught.value.cleanup_confirmed is True
    assert close_attempts(dll) == [0x1100]
    assert "SECRET" not in str(caught.value)


@pytest.mark.parametrize("status", [None, True, "SECRET", 1 << 32])
def test_unexpected_close_status_is_uncertain_and_does_not_stop_other_retirement(status: object) -> None:
    dll = FakeDLL()
    pair = PreassignmentJobs(api(dll))
    dll.results[("CloseHandle", 1)] = status
    with pytest.raises(WindowsVerificationError) as caught:
        pair.release_preassignment()
    assert caught.value.cleanup_confirmed is False
    assert caught.value.unresolved_jobs == ("J_command",)
    assert close_attempts(dll) == [0x2200, 0x1100]
    assert dll.closed == [0x1100]
    assert "SECRET" not in str(caught.value)


@pytest.mark.parametrize("operation", ["configure_job", "query_job_flags", "close_handle"])
def test_invalid_input_handle_is_rejected_before_calling_any_api(operation: str) -> None:
    dll = FakeDLL()
    checked = api(dll)
    with pytest.raises(WindowsVerificationError) as caught:
        getattr(checked, operation)(native.INVALID_HANDLE_VALUE)
    assert caught.value.category is Category.INVALID_HANDLE
    assert dll.calls == []


def test_error_numeric_fields_are_bounded_and_non_numeric_payloads_are_omitted() -> None:
    failure = WindowsVerificationError(
        Stage.JOBS, Category.OS_API,
        winerror="SECRET raw handle/environment", errno=1 << 50,
    )
    assert failure.winerror is None
    assert failure.errno is None
    assert failure.timed_out is False
    assert len(str(failure)) < 100
    assert "SECRET" not in str(failure)
    assert "SECRET" not in repr(failure.diagnostic())


@pytest.mark.parametrize("value,winerror,errno", [
    (None, None, None), (0, 0, 0), (1, 1, 1),
    (0x7FFFFFFE, 0x7FFFFFFE, 0x7FFFFFFE),
    (0x7FFFFFFF, 0x7FFFFFFF, 0x7FFFFFFF),
    (0x80000000, 0x80000000, None),
    (0xFFFFFFFE, 0xFFFFFFFE, None),
    (0xFFFFFFFF, 0xFFFFFFFF, None),
    (0x100000000, None, None),
    (-1, None, None), (-0x80000000, None, None),
    (False, None, None), (True, None, None),
    ("1", None, None), ("SECRET", None, None),
    (b"1", None, None), (0.0, None, None), (1.0, None, None),
])
@pytest.mark.parametrize("factory", ["error", "sanitized", "diagnostic"])
def test_diagnostic_numeric_ranges_are_distinct_and_never_coerce(
    value: object, winerror: int | None, errno: int | None, factory: str,
) -> None:
    if factory == "error":
        result = WindowsVerificationError(
            Stage.JOBS, Category.OS_API, winerror=value, errno=value,
        )
    elif factory == "sanitized":
        original = OSError("SECRET native transcript")
        original.winerror = value
        original.errno = value
        result = native.sanitized_error(original, Stage.JOBS, Category.OS_API)
    else:
        result = native.FailureDiagnostic(Stage.JOBS, Category.OS_API, value, value)
    assert result.winerror == winerror
    assert result.errno == errno
    if isinstance(result, WindowsVerificationError):
        diagnostic = result.diagnostic()
        assert diagnostic.winerror == winerror
        assert diagnostic.errno == errno
        assert "SECRET" not in str(result)
    assert "SECRET" not in repr(result)


@pytest.mark.parametrize("pause", ["before_retirement", "command_close", "supervision_close"])
@pytest.mark.parametrize("close_faults", [(), (1,), (2,), (1, 2)])
def test_concurrent_release_has_one_owner_and_no_false_success_or_second_close(
    monkeypatch: pytest.MonkeyPatch, pause: str, close_faults: tuple[int, ...],
) -> None:
    dll = FakeDLL()
    checked = api(dll)
    pair = PreassignmentJobs(checked)
    for ordinal in close_faults:
        dll.results[("CloseHandle", ordinal)] = 0
    owner_paused = Event()
    resume_owner = Event()
    contender_finished = Event()
    outcomes: dict[str, BaseException | None] = {}
    original_retire = pair._retire
    original_close = checked.close_handle

    def pause_owner() -> None:
        owner_paused.set()
        assert resume_owner.wait(5), "test did not release fake owner"

    def retire() -> Any:
        # Force the old check/claim race, without sleeps or scheduler guesses.
        if pause == "before_retirement" and not owner_paused.is_set():
            pause_owner()
        return original_retire()

    def close(handle: int) -> None:
        if ((pause == "command_close" and handle == 0x2200)
                or (pause == "supervision_close" and handle == 0x1100)):
            pause_owner()
        original_close(handle)

    def release(name: str) -> None:
        try:
            pair.release_preassignment()
        except BaseException as error:
            outcomes[name] = error
        else:
            outcomes[name] = None
        finally:
            if name == "contender":
                contender_finished.set()

    monkeypatch.setattr(pair, "_retire", retire)
    monkeypatch.setattr(checked, "close_handle", close)
    owner = Thread(target=release, args=("owner",), daemon=True)
    contender = Thread(target=release, args=("contender",), daemon=True)
    owner.start()
    try:
        assert owner_paused.wait(5), "owner did not reach controlled boundary"
        contender.start()
        assert contender_finished.wait(5), "state mutex was held across the external call"
        rejected = outcomes["contender"]
        assert isinstance(rejected, WindowsVerificationError)
        assert rejected.stage is Stage.CLOSE
        assert rejected.category is Category.OWNERSHIP
        assert rejected.cleanup_confirmed is False
        unresolved = ("J_supervision", "J_command")
        if pause == "supervision_close" and 1 not in close_faults:
            unresolved = ("J_supervision",)
        assert rejected.unresolved_jobs == unresolved
        assert "owner" not in outcomes
    finally:
        resume_owner.set()
        owner.join(5)
        if contender.ident is not None:
            contender.join(5)
    assert not owner.is_alive() and not contender.is_alive()
    assert close_attempts(dll) == [0x2200, 0x1100]
    assert dll.closed == [handle for ordinal, handle in enumerate([0x2200, 0x1100], 1) if ordinal not in close_faults]
    result = outcomes["owner"]
    if close_faults:
        assert isinstance(result, WindowsVerificationError)
        assert result.stage is Stage.CLOSE
        assert result.category is Category.UNCERTAIN_STATE
        assert result.winerror == 700 + close_faults[0]
        assert result.cleanup_confirmed is False
        assert [error.winerror for error in result.cleanup_failures] == [700 + ordinal for ordinal in close_faults[1:]]
    else:
        assert result is None
        assert all(job.state is OwnershipState.CONFIRMED_CLOSED for job in pair.ownership)
    previous_calls = list(dll.calls)
    with pytest.raises(WindowsVerificationError) as repeated:
        pair.release_preassignment()
    assert repeated.value.category is Category.OWNERSHIP
    assert repeated.value.cleanup_confirmed is (not close_faults)
    assert dll.calls == previous_calls
