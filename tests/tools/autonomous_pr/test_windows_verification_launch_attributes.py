"""TSK-0049: pure ctypes and injected fake API, including on Windows."""

from __future__ import annotations

import ast
import ctypes
import gc
import importlib.util
import re
import sys
import _ctypes
import weakref
from dataclasses import FrozenInstanceError, fields
from itertools import combinations
from pathlib import Path
from threading import Barrier, Event, Lock, Thread
from types import SimpleNamespace
from typing import Any, get_type_hints

import pytest


def forbidden_native(*args: object, **kwargs: object) -> Any:
    raise AssertionError("A fake-only test attempted native DLL/Win32 acquisition")


class ForbiddenLibraries:
    def __getattr__(self, name: str) -> Any:
        return forbidden_native(name)


def block_native(monkeypatch: pytest.MonkeyPatch) -> None:
    # Guard both direct constructors and cached LibraryLoader entry points.
    for name in ("WinDLL", "OleDLL", "CDLL", "PyDLL", "get_last_error", "_dlopen"):
        monkeypatch.setattr(ctypes, name, forbidden_native, raising=False)
    for name in ("windll", "oledll", "cdll", "pydll"):
        monkeypatch.setattr(ctypes, name, ForbiddenLibraries(), raising=False)
    for name in ("LoadLibrary", "dlopen"):
        monkeypatch.setattr(_ctypes, name, forbidden_native, raising=False)


# Cover initial collection/import too: autouse fixtures start after collection.
with pytest.MonkeyPatch.context() as import_guard:
    block_native(import_guard)
    from tools.autonomous_pr import _windows_verification_launch_attributes as attributes
    from tools.autonomous_pr._windows_verification_native import (
        Category,
        NativePlatform,
        Stage,
        WindowsVerificationError,
    )


@pytest.fixture(autouse=True)
def forbid_real_native(monkeypatch: pytest.MonkeyPatch) -> None:
    block_native(monkeypatch)


def test_native_acquisition_guard_is_active() -> None:
    with pytest.raises(AssertionError, match="native DLL/Win32"):
        ctypes.WinDLL("kernel32.dll")  # type: ignore[attr-defined]
    with pytest.raises(AssertionError, match="native DLL/Win32"):
        ctypes.windll.kernel32.InitializeProcThreadAttributeList()  # type: ignore[attr-defined]


INITIALIZE = "InitializeProcThreadAttributeList"
UPDATE = "UpdateProcThreadAttribute"
DELETE = "DeleteProcThreadAttributeList"
FUNCTIONS = (INITIALIZE, UPDATE, DELETE)


class FakeFunction:
    def __init__(self, dll: FakeDLL, name: str) -> None:
        self.dll = dll
        self.name = name
        self.restype: Any = "unset"
        self.argtypes: Any = "unset"

    def __call__(self, *args: Any) -> Any:
        return self.dll.call(self.name, args)


class FakeDLL:
    def __init__(self) -> None:
        for name in FUNCTIONS:
            setattr(self, name, FakeFunction(self, name))
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.results: dict[str, Any] = {}
        self.error: Any = 122
        self.length = 128
        self.initialized_length: int | None = None

    def last_error(self) -> Any:
        self.calls.append(("last_error", ()))
        return self.error

    def call(self, name: str, args: tuple[Any, ...]) -> Any:
        self.calls.append((name, args))
        if name == INITIALIZE:
            assert args[1:3] == (2, 0)
            size = ctypes.cast(args[3], ctypes.POINTER(attributes.SIZE_T))
            if args[0] is None:
                assert size.contents.value == 0
                size.contents.value = self.length
            elif self.initialized_length is not None:
                size.contents.value = self.initialized_length
        if name == UPDATE:
            assert args[1] == 0
            assert args[5:] == (None, None)
        if name in self.results:
            result = self.results[name]
            if isinstance(result, BaseException):
                raise result
            return result
        if name == DELETE:
            return None
        return 0 if name == INITIALIZE and args[0] is None else 1


def api(dll: FakeDLL) -> attributes.CheckedAttributeApi:
    return attributes.CheckedAttributeApi(dll, dll.last_error)


def invoke(checked: attributes.CheckedAttributeApi, operation: str) -> None:
    # All addresses and storage here are Python-owned; only fake functions run.
    storage = (ctypes.c_uint64 * 16)()
    pointer = ctypes.cast(storage, ctypes.c_void_p)
    if operation == INITIALIZE:
        checked.initialize_attribute_list(pointer, attributes.SIZE_T(128))
    elif operation == UPDATE:
        values = (attributes.HANDLE * 1)(0x1100)
        checked.update_attribute(
            pointer, attributes.PROC_THREAD_ATTRIBUTE_JOB_LIST,
            ctypes.cast(values, ctypes.c_void_p), ctypes.sizeof(values),
        )
    else:
        checked.delete_attribute_list(pointer)


def test_complete_x64_layout_field_types_and_zero_initialization() -> None:
    attributes.validate_abi()
    expected = [
        ("cb", ctypes.c_uint32, 0),
        ("lpReserved", ctypes.POINTER(ctypes.c_uint16), 8),
        ("lpDesktop", ctypes.POINTER(ctypes.c_uint16), 16),
        ("lpTitle", ctypes.POINTER(ctypes.c_uint16), 24),
        ("dwX", ctypes.c_uint32, 32), ("dwY", ctypes.c_uint32, 36),
        ("dwXSize", ctypes.c_uint32, 40), ("dwYSize", ctypes.c_uint32, 44),
        ("dwXCountChars", ctypes.c_uint32, 48),
        ("dwYCountChars", ctypes.c_uint32, 52),
        ("dwFillAttribute", ctypes.c_uint32, 56), ("dwFlags", ctypes.c_uint32, 60),
        ("wShowWindow", ctypes.c_uint16, 64), ("cbReserved2", ctypes.c_uint16, 66),
        ("lpReserved2", ctypes.POINTER(ctypes.c_uint8), 72),
        ("hStdInput", ctypes.c_void_p, 80), ("hStdOutput", ctypes.c_void_p, 88),
        ("hStdError", ctypes.c_void_p, 96),
    ]
    assert attributes.STARTUPINFOW._fields_ == [(name, kind) for name, kind, _ in expected]
    assert [getattr(attributes.STARTUPINFOW, name).offset for name, _, _ in expected] == [
        offset for _, _, offset in expected
    ]
    assert attributes.STARTUPINFOEXW._fields_ == [
        ("StartupInfo", attributes.STARTUPINFOW), ("lpAttributeList", ctypes.c_void_p)
    ]
    assert attributes.STARTUPINFOEXW.StartupInfo.offset == 0
    assert attributes.STARTUPINFOEXW.lpAttributeList.offset == 104
    for structure, size in ((attributes.STARTUPINFOW, 104), (attributes.STARTUPINFOEXW, 112)):
        assert ctypes.sizeof(structure) == size
        assert ctypes.alignment(structure) == 8
        assert bytes(structure()) == bytes(size)
    # The future builder must explicitly use extended size, not base size.
    startup = attributes.STARTUPINFOEXW()
    startup.StartupInfo.cb = ctypes.sizeof(startup)
    assert startup.StartupInfo.cb == 112
    assert bytes(startup)[4:] == bytes(108)
    assert attributes.LPSTARTUPINFOW._type_ is attributes.STARTUPINFOW
    assert attributes.LPSTARTUPINFOEXW._type_ is attributes.STARTUPINFOEXW
    assert attributes.LPWSTR._type_ is attributes.WCHAR is ctypes.c_uint16
    assert attributes.LPWSTR is not ctypes.c_wchar_p


def test_scalar_width_alignment_signedness_and_constants() -> None:
    for scalar, size, signed in (
        (attributes.BOOL, 4, True), (attributes.DWORD, 4, False),
        (attributes.WORD, 2, False), (attributes.WCHAR, 2, False),
        (attributes.BYTE, 1, False), (attributes.SIZE_T, 8, False),
        (attributes.DWORD_PTR, 8, False),
    ):
        assert ctypes.sizeof(scalar) == ctypes.alignment(scalar) == size
        assert (scalar(-1).value == -1) is signed
    assert ctypes.sizeof(attributes.HANDLE) == ctypes.alignment(attributes.HANDLE) == 8
    assert attributes.HANDLE(-1).value == (1 << 64) - 1
    assert attributes.LPPROC_THREAD_ATTRIBUTE_LIST is ctypes.c_void_p
    assert attributes.PROC_THREAD_ATTRIBUTE_HANDLE_LIST == 0x20002
    assert attributes.PROC_THREAD_ATTRIBUTE_JOB_LIST == 0x2000D
    assert attributes.EXTENDED_STARTUPINFO_PRESENT == 0x80000
    assert attributes.CREATE_SUSPENDED == 4
    assert attributes.STARTF_USESTDHANDLES == 0x100
    assert attributes.ERROR_INSUFFICIENT_BUFFER == 122
    assert attributes.ATTRIBUTE_COUNT == 2
    assert attributes.MAX_ATTRIBUTE_LIST_BYTES == 65_536


@pytest.mark.parametrize("symbol", [
    "PROC_THREAD_ATTRIBUTE_HANDLE_LIST", "PROC_THREAD_ATTRIBUTE_JOB_LIST",
    "EXTENDED_STARTUPINFO_PRESENT", "CREATE_SUSPENDED", "STARTF_USESTDHANDLES",
    "ERROR_INSUFFICIENT_BUFFER", "ATTRIBUTE_COUNT", "MAX_ATTRIBUTE_LIST_BYTES",
])
def test_bad_constant_fails_before_loading_or_calling(monkeypatch: pytest.MonkeyPatch, symbol: str) -> None:
    monkeypatch.setattr(attributes, symbol, 0)
    assert_unsupported_abi()


def assert_unsupported_abi() -> None:
    dll = FakeDLL()
    for operation in (
        lambda: api(dll),
        lambda: attributes.load_native_api(
            _platform=NativePlatform("win32", "cpython", 10)
        ),
    ):
        with pytest.raises(WindowsVerificationError) as caught:
            operation()
        assert caught.value.stage is Stage.PREFLIGHT
        assert caught.value.category is Category.UNSUPPORTED_PLATFORM
        assert caught.value.cleanup_confirmed is True
    assert dll.calls == []


@pytest.mark.parametrize("scalar,replacement", [
    ("BOOL", ctypes.c_uint32), ("DWORD", ctypes.c_int32),
    ("WORD", ctypes.c_int16), ("WCHAR", ctypes.c_wchar),
    ("SIZE_T", ctypes.c_uint32), ("DWORD_PTR", ctypes.c_int64),
    ("HANDLE", ctypes.c_uint32), ("LPWSTR", ctypes.c_wchar_p),
])
def test_bad_scalar_is_rejected(monkeypatch: pytest.MonkeyPatch, scalar: str, replacement: Any) -> None:
    monkeypatch.setattr(attributes, scalar, replacement)
    assert_unsupported_abi()


@pytest.mark.parametrize("kind", ["size", "alignment", "field_type", "offset", "pointer_width"])
def test_every_abi_dimension_is_checked(monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    if kind in ("size", "alignment", "pointer_width"):
        operation = "alignment" if kind == "alignment" else "sizeof"
        original = getattr(ctypes, operation)
        target = ctypes.c_void_p if kind == "pointer_width" else attributes.STARTUPINFOEXW
        monkeypatch.setattr(ctypes, operation, lambda value: 4 if value is target else original(value))
    else:
        fields = list(attributes.STARTUPINFOW._fields_)
        if kind == "field_type":
            fields[5] = ("dwY", ctypes.c_int32)  # Same size/offset, wrong signedness.
        else:
            fields[4], fields[5] = fields[5], fields[4]
        class BadStartup(ctypes.Structure):
            _fields_ = fields
        monkeypatch.setattr(attributes, "STARTUPINFOW", BadStartup)
    assert_unsupported_abi()


def test_exact_three_native_signatures_no_call_during_binding() -> None:
    dll = FakeDLL()
    api(dll)
    expected = {
        INITIALIZE: (ctypes.c_int32, [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                                    ctypes.POINTER(ctypes.c_size_t)]),
        UPDATE: (ctypes.c_int32, [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_size_t,
                                ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p,
                                ctypes.POINTER(ctypes.c_size_t)]),
        DELETE: (None, [ctypes.c_void_p]),
    }
    for name, (result, arguments) in expected.items():
        function = getattr(dll, name)
        assert function.restype is result
        assert function.argtypes == arguments
    assert dll.calls == []


@pytest.mark.parametrize("symbol", FUNCTIONS)
@pytest.mark.parametrize("fault", ["missing", "not_callable", "restype", "argtypes"])
def test_unavailable_or_unbindable_function_fails_closed(symbol: str, fault: str) -> None:
    dll = FakeDLL()
    if fault == "missing":
        delattr(dll, symbol)
    elif fault == "not_callable":
        setattr(dll, symbol, None)
    else:
        class Unbindable(FakeFunction):
            def __setattr__(self, name: str, value: Any) -> None:
                if name == fault:
                    value = "incorrect signature"
                super().__setattr__(name, value)
        setattr(dll, symbol, Unbindable(dll, symbol))
    with pytest.raises(WindowsVerificationError) as caught:
        api(dll)
    assert caught.value.category is Category.OS_API
    assert caught.value.cleanup_confirmed is True
    assert dll.calls == []


@pytest.mark.parametrize("operation", [INITIALIZE, UPDATE])
@pytest.mark.parametrize("status", [1, 2, -1, -(1 << 31), (1 << 31) - 1])
def test_bool_accepts_each_signed_int32_nonzero(operation: str, status: int) -> None:
    dll = FakeDLL()
    dll.results[operation] = status
    invoke(api(dll), operation)
    assert [name for name, _ in dll.calls] == [operation]


@pytest.mark.parametrize("operation", [INITIALIZE, UPDATE])
@pytest.mark.parametrize("status", [None, True, False, 1.0, "secret", 1 << 31,
                                   -(1 << 31) - 1, ctypes.c_int32(1)])
def test_malformed_bool_is_never_coerced(operation: str, status: object) -> None:
    dll = FakeDLL()
    dll.results[operation] = status
    with pytest.raises(WindowsVerificationError) as caught:
        invoke(api(dll), operation)
    assert caught.value.category is Category.UNCERTAIN_STATE
    assert caught.value.winerror is None
    assert [name for name, _ in dll.calls] == [operation]
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize("operation", [INITIALIZE, UPDATE])
@pytest.mark.parametrize("code", [0, 5, 122, 0xFFFFFFFF])
def test_zero_bool_captures_error_immediately(operation: str, code: int) -> None:
    dll = FakeDLL()
    dll.results[operation] = 0
    dll.error = code
    with pytest.raises(WindowsVerificationError) as caught:
        invoke(api(dll), operation)
    assert caught.value.winerror == code
    assert caught.value.stage is Stage.PREFLIGHT
    assert caught.value.category is Category.OS_API
    assert [name for name, _ in dll.calls] == [operation, "last_error"]
    dll.error = 999  # Stored numeric cause does not follow later changes.
    assert caught.value.winerror == code


@pytest.mark.parametrize("code", [None, True, -1, 1 << 32, "secret", ctypes.c_uint32(122)])
def test_invalid_error_copy_is_terminal(code: object) -> None:
    dll = FakeDLL()
    dll.results[UPDATE] = 0
    dll.error = code
    with pytest.raises(WindowsVerificationError) as caught:
        invoke(api(dll), UPDATE)
    assert caught.value.category is Category.UNCERTAIN_STATE
    assert caught.value.winerror is None


def test_error_reader_failure_and_invalid_binding_are_bounded() -> None:
    dll = FakeDLL()
    dll.results[UPDATE] = 0
    def broken_reader() -> int:
        dll.calls.append(("last_error", ()))
        raise OSError("secret pointer/handle/path/argv/environment")
    checked = attributes.CheckedAttributeApi(dll, broken_reader)
    with pytest.raises(WindowsVerificationError) as caught:
        invoke(checked, UPDATE)
    assert caught.value.category is Category.UNCERTAIN_STATE
    assert "secret" not in str(caught.value)
    assert [name for name, _ in dll.calls] == [UPDATE, "last_error"]
    with pytest.raises(WindowsVerificationError) as caught:
        attributes.CheckedAttributeApi(dll, None)  # type: ignore[arg-type]
    assert caught.value.cleanup_confirmed is True


@pytest.mark.parametrize("length", [1, 128, 65_536])
def test_sizing_requires_exact_expected_failure_without_initializing(length: int) -> None:
    dll = FakeDLL()
    dll.length = length
    assert api(dll).required_size() == length
    assert [name for name, _ in dll.calls] == [INITIALIZE, "last_error"]
    assert dll.calls[0][1][0:3] == (None, 2, 0)


@pytest.mark.parametrize("length", [0, 65_537, (1 << 64) - 1])
def test_sizing_rejects_invalid_or_excessive_size(length: int) -> None:
    dll = FakeDLL()
    dll.length = length
    with pytest.raises(WindowsVerificationError) as caught:
        api(dll).required_size()
    assert caught.value.category is Category.RESOURCE
    assert [name for name, _ in dll.calls] == [INITIALIZE, "last_error"]


@pytest.mark.parametrize("status", [1, -1, True, None, 1 << 31])
def test_sizing_cannot_be_mistaken_for_successful_initialize(status: object) -> None:
    dll = FakeDLL()
    dll.results[INITIALIZE] = status
    with pytest.raises(WindowsVerificationError) as caught:
        api(dll).required_size()
    assert caught.value.category is Category.UNCERTAIN_STATE
    assert [name for name, _ in dll.calls] == [INITIALIZE]


def test_sizing_requires_error_122() -> None:
    dll = FakeDLL()
    dll.error = 5
    with pytest.raises(WindowsVerificationError) as caught:
        api(dll).required_size()
    assert caught.value.winerror == 5
    assert caught.value.category is Category.OS_API


def test_initialize_preserves_inout_size_for_future_owner_validation() -> None:
    dll = FakeDLL()
    dll.initialized_length = 120
    checked = api(dll)
    size = attributes.SIZE_T(128)
    storage = (ctypes.c_uint64 * 16)()
    pointer = ctypes.cast(storage, ctypes.c_void_p)
    checked.initialize_attribute_list(pointer, size)
    assert size.value == 120
    assert dll.calls[0][1][:3] == (pointer, 2, 0)
    assert [name for name, _ in dll.calls] == [INITIALIZE]


@pytest.mark.parametrize("size", [True, 128, None, attributes.SIZE_T(0), attributes.SIZE_T(65_537)])
def test_initialize_rejects_bad_input_size_before_call(size: Any) -> None:
    dll = FakeDLL()
    with pytest.raises(WindowsVerificationError):
        api(dll).initialize_attribute_list(ctypes.c_void_p(0x1000), size)
    assert dll.calls == []


@pytest.mark.parametrize("attribute", [0x20002, 0x2000D])
def test_update_uses_exact_value_pointer_size_and_reserved_nulls(attribute: int) -> None:
    dll = FakeDLL()
    values = (attributes.HANDLE * 2)(0x1100, 0x2200)
    storage = (ctypes.c_uint64 * 16)()
    pointer = ctypes.cast(storage, ctypes.c_void_p)
    value = ctypes.cast(values, ctypes.c_void_p)
    api(dll).update_attribute(pointer, attribute, value, 16)
    assert dll.calls == [(UPDATE, (pointer, 0, attribute, value, 16, None, None))]


@pytest.mark.parametrize("attribute,size", [(0, 8), (True, 8), (0x20002, True),
                                           (0x20002, 0), (0x20002, -1), (0x20002, 1 << 64)])
def test_update_rejects_invalid_key_or_size_before_call(attribute: Any, size: Any) -> None:
    dll = FakeDLL()
    with pytest.raises(WindowsVerificationError):
        api(dll).update_attribute(ctypes.c_void_p(0x1000), attribute, ctypes.c_void_p(0x2000), size)
    assert dll.calls == []


@pytest.mark.parametrize("operation", FUNCTIONS)
@pytest.mark.parametrize("pointer", [None, 0, True, ctypes.c_void_p()])
def test_null_or_untyped_pointer_is_rejected_before_call(operation: str, pointer: Any) -> None:
    dll = FakeDLL()
    checked = api(dll)
    with pytest.raises(WindowsVerificationError):
        if operation == INITIALIZE:
            checked.initialize_attribute_list(pointer, attributes.SIZE_T(128))
        elif operation == UPDATE:
            checked.update_attribute(pointer, 0x20002, ctypes.c_void_p(0x2000), 8)
        else:
            checked.delete_attribute_list(pointer)
    assert dll.calls == []


@pytest.mark.parametrize("result", [None, 0, 1, False, "not a BOOL"])
def test_delete_has_void_semantics_without_last_error_or_cleanup_claim(result: Any) -> None:
    dll = FakeDLL()
    dll.results[DELETE] = result
    assert invoke(api(dll), DELETE) is None
    assert getattr(dll, DELETE).restype is None
    assert [name for name, _ in dll.calls] == [DELETE]


@pytest.mark.parametrize("operation", FUNCTIONS)
@pytest.mark.parametrize("error", [OSError("secret native exception"), MemoryError("secret")])
def test_wrapper_exceptions_are_sanitized_without_retry(operation: str, error: Exception) -> None:
    dll = FakeDLL()
    dll.results[operation] = error
    with pytest.raises(WindowsVerificationError) as caught:
        invoke(api(dll), operation)
    assert caught.value.stage is (Stage.CLEANUP if operation == DELETE else Stage.PREFLIGHT)
    assert caught.value.category is (
        Category.UNCERTAIN_STATE if operation == DELETE else
        Category.RESOURCE if isinstance(error, MemoryError) else Category.OS_API
    )
    assert caught.value.cleanup_confirmed is False
    assert caught.value.__suppress_context__ is True
    assert "secret" not in str(caught.value) + repr(caught.value)
    assert [name for name, _ in dll.calls] == [operation]


@pytest.mark.parametrize("platform", [NativePlatform("linux", "cpython", 0),
    NativePlatform("darwin", "cpython", 0), NativePlatform("win32", "pypy", 10),
    NativePlatform("win32", "cpython", 6)])
def test_unsupported_host_never_loads_a_dll(platform: NativePlatform) -> None:
    with pytest.raises(WindowsVerificationError) as caught:
        attributes.load_native_api(_platform=platform)
    assert caught.value.category is Category.UNSUPPORTED_PLATFORM
    assert caught.value.cleanup_confirmed is True


def test_lazy_acquisition_uses_only_injected_loader_and_error_copy() -> None:
    dll = FakeDLL()
    calls = []
    def loader(name: str, *, use_last_error: bool) -> FakeDLL:
        calls.append((name, use_last_error))
        return dll
    checked = attributes.load_native_api(
        _platform=NativePlatform("win32", "cpython", 10),
        _dll_loader=loader, _last_error=dll.last_error,
    )
    assert isinstance(checked, attributes.CheckedAttributeApi)
    assert calls == [("kernel32.dll", True)]
    assert dll.calls == []


@pytest.mark.parametrize("major", [6, 10, 11])
def test_default_platform_detection_is_fake_and_version_gated(
    monkeypatch: pytest.MonkeyPatch, major: int,
) -> None:
    dll = FakeDLL()
    loads = []
    def loader(name: str, *, use_last_error: bool) -> FakeDLL:
        loads.append((name, use_last_error))
        return dll
    monkeypatch.setattr(attributes, "sys", SimpleNamespace(
        platform="win32", implementation=SimpleNamespace(name="cpython"),
        getwindowsversion=lambda: SimpleNamespace(major=major),
    ))
    if major < 10:
        with pytest.raises(WindowsVerificationError) as caught:
            attributes.load_native_api(_dll_loader=loader, _last_error=dll.last_error)
        assert caught.value.category is Category.UNSUPPORTED_PLATFORM
        assert loads == []
    else:
        attributes.load_native_api(_dll_loader=loader, _last_error=dll.last_error)
        assert loads == [("kernel32.dll", True)]
    assert dll.calls == []


def test_platform_detection_failure_is_bounded_before_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken_version() -> Any:
        raise OSError("secret platform data")
    monkeypatch.setattr(attributes, "sys", SimpleNamespace(
        platform="win32", implementation=SimpleNamespace(name="cpython"),
        getwindowsversion=broken_version,
    ))
    with pytest.raises(WindowsVerificationError) as caught:
        attributes.load_native_api()
    assert caught.value.stage is Stage.PREFLIGHT
    assert caught.value.category is Category.OS_API
    assert caught.value.cleanup_confirmed is True
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize("missing", FUNCTIONS)
def test_missing_symbol_during_lazy_acquisition_is_not_feature_support(missing: str) -> None:
    dll = FakeDLL()
    delattr(dll, missing)
    def loader(name: str, *, use_last_error: bool) -> FakeDLL:
        assert (name, use_last_error) == ("kernel32.dll", True)
        return dll
    with pytest.raises(WindowsVerificationError) as caught:
        attributes.load_native_api(
            _platform=NativePlatform("win32", "cpython", 10),
            _dll_loader=loader, _last_error=dll.last_error,
        )
    assert caught.value.category is Category.OS_API
    assert caught.value.cleanup_confirmed is True
    assert dll.calls == []


def test_loader_failure_sanitizes_numeric_errors() -> None:
    def loader(*args: object, **kwargs: object) -> Any:
        error = OSError("secret")
        error.winerror = 0xFFFFFFFF
        error.errno = (1 << 31) - 1
        raise error
    with pytest.raises(WindowsVerificationError) as caught:
        attributes.load_native_api(
            _platform=NativePlatform("win32", "cpython", 10),
            _dll_loader=loader, _last_error=lambda: 0,
        )
    assert caught.value.winerror == 0xFFFFFFFF
    assert caught.value.errno == (1 << 31) - 1
    assert caught.value.cleanup_confirmed is True
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize("dependency", ["WinDLL", "get_last_error"])
def test_missing_acquisition_dependency_fails_before_loading(monkeypatch: pytest.MonkeyPatch, dependency: str) -> None:
    monkeypatch.delattr(ctypes, dependency)
    with pytest.raises(WindowsVerificationError) as caught:
        attributes.load_native_api(_platform=NativePlatform("win32", "cpython", 10))
    assert caught.value.category is Category.OS_API
    assert caught.value.cleanup_confirmed is True


@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_fresh_import_with_blocked_loaders_and_no_windows_symbols(
    monkeypatch: pytest.MonkeyPatch, platform: str,
) -> None:
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.delattr(ctypes, "WinDLL")
    monkeypatch.delattr(ctypes, "get_last_error")
    name = "tools.autonomous_pr._windows_verification_launch_attributes_import_test"
    spec = importlib.util.spec_from_file_location(name, attributes.__file__)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    module.validate_abi()
    assert not hasattr(module.PreparedLaunchAttributes, "launch")
    assert not hasattr(module.PreparedLaunchAttributes, "pointer")


def test_dormant_boundary_and_native_symbol_surface() -> None:
    root = Path(__file__).resolve().parents[3]
    for directory in (root / "tools", root / "src"):
        for path in directory.rglob("*.py"):
            if path.resolve() == Path(attributes.__file__).resolve():
                continue
            source = path.read_text(encoding="utf-8")
            assert "_windows_verification_launch_attributes" not in source
    source = Path(attributes.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    native_symbols = {
        node.value for node in ast.walk(tree) if isinstance(node, ast.Constant)
        and isinstance(node.value, str) and node.value.endswith(("AttributeList", "ThreadAttribute"))
    }
    assert native_symbols == set(FUNCTIONS) | {"lpAttributeList"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            assert node.attr not in {"CreateProcessW", "ResumeThread", "AssignProcessToJobObject",
                                     "IsProcessInJob", "TerminateJobObject", "CloseHandle"}


WORKER_HANDLES = {"supervision_job": 0x1100, "bootstrap_mapping": 0x4400}
PAYLOAD_HANDLES = {
    "supervision_job": 0x1100, "command_job": 0x2200,
    "stdin": 0x5500, "stdout": 0x6600, "stderr": 0x7700,
}
ROLE_CASES = (
    (attributes.WorkerLaunchInputs, attributes.prepare_worker_values, WORKER_HANDLES),
    (attributes.PayloadLaunchInputs, attributes.prepare_payload_values, PAYLOAD_HANDLES),
)


@pytest.mark.parametrize("input_type,prepare,handles", ROLE_CASES)
def test_role_shapes_are_closed_keyword_only_frozen_and_redacted(
    input_type: Any, prepare: Any, handles: dict[str, int],
) -> None:
    inputs = input_type(**handles)
    assert {field.name for field in fields(inputs)} == set(handles)
    assert all(field.kw_only and not field.repr for field in fields(inputs))
    assert repr(inputs) == f"{input_type.__name__}()"
    assert not hasattr(inputs, "__dict__")
    for name in handles:
        with pytest.raises(FrozenInstanceError):
            setattr(inputs, name, 0x9900)
        with pytest.raises(FrozenInstanceError):
            delattr(inputs, name)
    prepared = prepare(inputs)
    assert repr(prepared) in (
        "_LaunchAttributeValues(role='worker')", "_LaunchAttributeValues(role='payload')",
    )
    assert not hasattr(prepared, "__dict__")
    with pytest.raises(FrozenInstanceError):
        prepared._job_values = None
    with pytest.raises(FrozenInstanceError):
        prepared.role = "other"


@pytest.mark.parametrize("input_type,prepare,handles", ROLE_CASES)
def test_missing_extra_and_unlabeled_fields_are_rejected(
    input_type: Any, prepare: Any, handles: dict[str, int],
) -> None:
    for missing in handles:
        incomplete = {name: value for name, value in handles.items() if name != missing}
        with pytest.raises(TypeError):
            input_type(**incomplete)
    for extra in ("other", "job_handles", "inherited_handles", "role"):
        with pytest.raises(TypeError) as caught:
            input_type(**handles, **{extra: 0x12345678})
        assert "305419896" not in str(caught.value)
    with pytest.raises(TypeError):
        input_type(*handles.values())
    with pytest.raises(TypeError):
        input_type(handles)


class IntegerSubclass(int):
    pass


class UntrustedHandle:
    def __bool__(self) -> bool:
        raise AssertionError("must not test handle truthiness")

    def __int__(self) -> int:
        raise AssertionError("must not coerce handles")

    def __repr__(self) -> str:
        raise AssertionError("must not render a rejected handle")


INVALID_HANDLE_VALUES = (
    0, -1, -2, -3, -4, -5, -(1 << 63),
    1 << 63, (1 << 64) - 1, 1 << 64, 1 << 200,
    None, True, False, 4352.0, "secret handle/argv/env", b"secret",
    ctypes.c_void_p(0x1100), ctypes.c_uint64(0x1100), IntegerSubclass(0x1100),
    [], {}, (0x1100,), UntrustedHandle(),
)


@pytest.mark.parametrize("input_type,prepare,handles", ROLE_CASES)
@pytest.mark.parametrize("bad", INVALID_HANDLE_VALUES)
def test_every_role_field_rejects_invalid_numbers_and_python_types(
    input_type: Any, prepare: Any, handles: dict[str, int], bad: Any,
) -> None:
    for name in handles:
        candidate = dict(handles)
        candidate[name] = bad
        with pytest.raises(WindowsVerificationError) as caught:
            input_type(**candidate)
        assert caught.value.stage is Stage.PREFLIGHT
        assert caught.value.category is Category.INVALID_HANDLE
        assert str(caught.value) == "preflight/invalid_handle"
        assert "secret" not in repr(caught.value)


@pytest.mark.parametrize("input_type,prepare,handles", ROLE_CASES)
def test_all_duplicate_and_cross_list_overlap_pairs_are_rejected(
    input_type: Any, prepare: Any, handles: dict[str, int],
) -> None:
    for first, second in combinations(handles, 2):
        candidate = dict(handles)
        candidate[second] = candidate[first]
        with pytest.raises(WindowsVerificationError) as caught:
            input_type(**candidate)
        assert caught.value.stage is Stage.PREFLIGHT
        assert caught.value.category is Category.OWNERSHIP
        assert str(caught.value) == "preflight/ownership"


@pytest.mark.parametrize("input_type,prepare,handles", ROLE_CASES)
def test_preparation_revalidates_before_ctypes_narrowing(
    input_type: Any, prepare: Any, handles: dict[str, int],
) -> None:
    for name in handles:
        inputs = input_type(**handles)
        # A forged/deserialized object must not make bool/overflow valid by
        # converting it to a HANDLE. This bypass is outside the normal API.
        object.__setattr__(inputs, name, True)
        with pytest.raises(WindowsVerificationError) as caught:
            prepare(inputs)
        assert caught.value.category is Category.INVALID_HANDLE
    inputs = input_type(**handles)
    names = list(handles)
    object.__setattr__(inputs, names[-1], handles[names[0]])
    with pytest.raises(WindowsVerificationError) as caught:
        prepare(inputs)
    assert caught.value.category is Category.OWNERSHIP


@pytest.mark.parametrize("input_type,prepare,handles", ROLE_CASES)
def test_prepare_does_not_accept_arbitrary_lists_mappings_objects_or_subclasses(
    input_type: Any, prepare: Any, handles: dict[str, int],
) -> None:
    class ExtraInputs(input_type):
        pass
    for candidate in (None, list(handles.values()), tuple(handles.values()), handles,
                      SimpleNamespace(**handles), ExtraInputs(**handles)):
        with pytest.raises(WindowsVerificationError) as caught:
            prepare(candidate)
        assert caught.value.stage is Stage.PREFLIGHT
        assert caught.value.category is Category.OWNERSHIP
    other = (attributes.PayloadLaunchInputs(**PAYLOAD_HANDLES)
             if input_type is attributes.WorkerLaunchInputs else
             attributes.WorkerLaunchInputs(**WORKER_HANDLES))
    with pytest.raises(WindowsVerificationError):
        prepare(other)


def test_worker_values_have_only_supervision_and_bootstrap_without_stdio_policy() -> None:
    prepared = attributes.prepare_worker_values(attributes.WorkerLaunchInputs(**WORKER_HANDLES))
    assert prepared.role == "worker"
    assert list(prepared._job_values) == [0x1100]
    assert list(prepared._inherited_values) == [0x4400]
    assert ctypes.sizeof(prepared._job_values) == 8
    assert ctypes.sizeof(prepared._inherited_values) == 8
    startup = prepared._startup_info
    expected = attributes.STARTUPINFOEXW()
    expected.StartupInfo.cb = 112
    assert bytes(startup) == bytes(expected)
    assert startup.lpAttributeList is None
    assert startup.StartupInfo.dwFlags == 0
    assert startup.StartupInfo.hStdInput is None
    assert startup.StartupInfo.hStdOutput is None
    assert startup.StartupInfo.hStdError is None


def test_payload_values_fix_job_stream_order_and_exact_stdio_fields() -> None:
    # Keyword insertion/numeric order must not define the two native orders.
    inputs = attributes.PayloadLaunchInputs(
        stderr=0x3300, command_job=0x2200, stdout=0x4400,
        stdin=0x5500, supervision_job=0x6600,
    )
    prepared = attributes.prepare_payload_values(inputs)
    assert prepared.role == "payload"
    assert list(prepared._job_values) == [0x6600, 0x2200]
    assert list(prepared._inherited_values) == [0x5500, 0x4400, 0x3300]
    assert ctypes.sizeof(prepared._job_values) == 16
    assert ctypes.sizeof(prepared._inherited_values) == 24
    expected = attributes.STARTUPINFOEXW()
    expected.StartupInfo.cb = 112
    expected.StartupInfo.dwFlags = 0x100
    expected.StartupInfo.hStdInput = 0x5500
    expected.StartupInfo.hStdOutput = 0x4400
    expected.StartupInfo.hStdError = 0x3300
    assert bytes(prepared._startup_info) == bytes(expected)
    assert prepared._startup_info.lpAttributeList is None


@pytest.mark.parametrize("input_type,prepare,handles", ROLE_CASES)
def test_value_storage_is_persistent_aligned_redacted_and_item_immutable(
    input_type: Any, prepare: Any, handles: dict[str, int],
) -> None:
    inputs = input_type(**handles)
    prepared = prepare(inputs)
    storage = (prepared._job_values, prepared._inherited_values, prepared._startup_info)
    refs = tuple(weakref.ref(value) for value in storage)
    snapshots = tuple(bytes(value) for value in storage)
    addresses = tuple(ctypes.addressof(value) for value in storage)
    assert all(address % 8 == 0 for address in addresses)
    for values in (prepared._job_values, prepared._inherited_values):
        assert repr(values) == "HandleValues()"
        assert values._type_ is attributes.HANDLE
        with pytest.raises(TypeError, match="immutable_handle_values"):
            values[0] = 0x9900
        with pytest.raises(TypeError, match="immutable_handle_values"):
            values[:] = [0x9900] * len(values)
    rendered = repr(inputs) + repr(prepared) + repr(prepared._job_values) + repr(prepared._inherited_values)
    assert "0x" not in rendered
    assert all(str(handle) not in rendered for handle in handles.values())
    del inputs, storage, values
    gc.collect()
    assert all(ref() is not None for ref in refs)
    assert tuple(bytes(ref()) for ref in refs) == snapshots
    assert tuple(ctypes.addressof(ref()) for ref in refs) == addresses


@pytest.mark.parametrize("input_type,prepare,handles", ROLE_CASES)
def test_each_preparation_owns_separate_python_storage_only(
    input_type: Any, prepare: Any, handles: dict[str, int],
) -> None:
    inputs = input_type(**handles)
    first = prepare(inputs)
    second = prepare(inputs)
    for name in ("_job_values", "_inherited_values", "_startup_info"):
        assert getattr(first, name) is not getattr(second, name)
        assert bytes(getattr(first, name)) == bytes(getattr(second, name))
    second._startup_info.StartupInfo.cb = 0
    assert first._startup_info.StartupInfo.cb == 112


def test_structurally_valid_labels_are_not_os_capability_proof(monkeypatch: pytest.MonkeyPatch) -> None:
    # Any path to checked native acquisition/operations is forbidden here too,
    # even if it would otherwise use this test module's fake DLL.
    monkeypatch.setattr(attributes, "load_native_api", forbidden_native)
    monkeypatch.setattr(attributes, "CheckedAttributeApi", forbidden_native)
    monkeypatch.setattr(attributes.native, "load_native_api", forbidden_native)
    monkeypatch.setattr(attributes.native, "CheckedJobApi", forbidden_native)
    # Numeric edge values are deliberately not claims about real OS objects.
    worker = attributes.prepare_worker_values(attributes.WorkerLaunchInputs(
        supervision_job=1, bootstrap_mapping=(1 << 63) - 1,
    ))
    assert list(worker._job_values) == [1]
    assert list(worker._inherited_values) == [(1 << 63) - 1]
    # Swapping valid labels cannot be detected without a trusted OS ledger.
    payload = attributes.prepare_payload_values(attributes.PayloadLaunchInputs(
        supervision_job=0x2200, command_job=0x1100,
        stdin=0x5500, stdout=0x6600, stderr=0x7700,
    ))
    assert list(payload._job_values) == [0x2200, 0x1100]
    for prepared in (worker, payload):
        assert prepared._startup_info.lpAttributeList is None
        assert not hasattr(prepared, "release")
        assert not hasattr(prepared, "launch")
    assert not isinstance(worker, attributes.PreparedLaunchAttributes)
    assert not isinstance(payload, attributes.PreparedLaunchAttributes)


class TransactionDLL(FakeDLL):
    """Inspect actual arguments/storage without retaining the borrowed buffers."""

    def __init__(self) -> None:
        super().__init__()
        self.counts: dict[str, int] = {}
        self.outcomes: dict[tuple[str, int], Any] = {}
        self.callbacks: dict[tuple[str, int], Any] = {}
        self.expected_jobs: list[int] = [0x1100]
        self.expected_inherited: list[int] = [0x4400]
        self.refs: tuple[Any, ...] = ()
        self.resource_ref: Any = None
        self.pointer: int | None = None
        self.update_values: list[tuple[int, list[int], int]] = []

    def inspect_live_storage(self) -> None:
        gc.collect()
        assert self.resource_ref() in attributes._PINNED_RESOURCES
        assert all(ref() is not None for ref in self.refs)
        assert list(self.refs[1]()) == self.expected_jobs
        assert list(self.refs[2]()) == self.expected_inherited

    def call(self, name: str, args: tuple[Any, ...]) -> Any:
        self.calls.append((name, args))
        count = self.counts.get(name, 0) + 1
        self.counts[name] = count
        self.error = 900  # The next native call would replace an uncopied error.
        if name == INITIALIZE:
            assert args[1:3] == (2, 0)
            size = ctypes.cast(args[3], ctypes.POINTER(attributes.SIZE_T))
            if args[0] is None:
                assert count == 1 and size.contents.value == 0
                size.contents.value = self.length
                self.error = 122
            else:
                assert count == 2 and size.contents.value == self.length
                self.pointer = args[0].value
                assert self.pointer is not None and self.pointer % 8 == 0
                resources = [resource for resource in attributes._PINNED_RESOURCES
                             if resource.buffer is not None
                             and ctypes.addressof(resource.buffer) == self.pointer]
                assert len(resources) == 1, "storage was not pinned before Initialize"
                resource = resources[0]
                assert resource.initialization_attempted
                assert resource.outcome.state == "pending"
                assert resource.state.value == "building"
                assert resource.values is not None
                # No strong references in the fake ledger: quarantine tests must
                # prove that the production registry itself pins native storage.
                self.refs = tuple(weakref.ref(value) for value in (
                    resource.buffer, resource.values._job_values,
                    resource.values._inherited_values, resource.values._startup_info,
                ))
                self.resource_ref = weakref.ref(resource)
                assert not any(bytes(resource.buffer))
                assert ctypes.sizeof(resource.buffer) >= self.length
                assert resource.values._startup_info.lpAttributeList is None
                self.inspect_live_storage()
                if self.initialized_length is not None:
                    size.contents.value = self.initialized_length
        elif name == UPDATE:
            assert args[0].value == self.pointer
            assert args[1] == 0 and args[5:] == (None, None)
            assert count in (1, 2)
            expected_key = 0x2000D if count == 1 else 0x20002
            expected_values = self.expected_jobs if count == 1 else self.expected_inherited
            assert args[2] == expected_key
            assert args[3].value == ctypes.addressof(self.refs[count]())
            assert args[4] == len(expected_values) * 8
            actual = list(ctypes.cast(args[3], ctypes.POINTER(attributes.HANDLE * len(expected_values))).contents)
            assert actual == expected_values
            self.update_values.append((args[2], actual, args[4]))
            assert self.resource_ref().outcome.state == "initialized"
            self.inspect_live_storage()
        elif name == DELETE:
            assert args[0].value == self.pointer
            assert self.resource_ref().state.value == "retiring"
            assert self.resource_ref().outcome.state == "initialized"
            self.inspect_live_storage()
        else:
            raise AssertionError("unexpected native operation")
        callback = self.callbacks.get((name, count))
        if callback is not None:
            callback()
        if (name, count) in self.outcomes:
            self.error = 700 + count
            result = self.outcomes[(name, count)]
            if isinstance(result, BaseException):
                raise result
            return result
        return (0 if args[0] is None else 1) if name == INITIALIZE else None if name == DELETE else 1


TRANSACTION_CASES = (
    (attributes.WorkerLaunchInputs, attributes.prepare_worker_attributes, WORKER_HANDLES,
     [0x1100], [0x4400]),
    (attributes.PayloadLaunchInputs, attributes.prepare_payload_attributes, PAYLOAD_HANDLES,
     [0x1100, 0x2200], [0x5500, 0x6600, 0x7700]),
)


def transaction_dll(jobs: list[int], inherited: list[int]) -> TransactionDLL:
    dll = TransactionDLL()
    dll.expected_jobs = jobs
    dll.expected_inherited = inherited
    return dll


@pytest.mark.parametrize("input_type,prepare,handles,jobs,inherited", TRANSACTION_CASES)
@pytest.mark.parametrize("length", [128, 129, 65_536])
def test_transaction_success_exact_call_order_arguments_storage_and_void_retirement(
    input_type: Any, prepare: Any, handles: dict[str, int],
    jobs: list[int], inherited: list[int], length: int,
) -> None:
    before = set(attributes._PINNED_RESOURCES)
    dll = transaction_dll(jobs, inherited)
    dll.length = length
    owner = prepare(input_type(**handles), api(dll))
    assert owner.ownership.value == "ready"
    assert repr(owner) == "PreparedLaunchAttributes()"
    assert [name for name, _ in dll.calls] == [INITIALIZE, "last_error", INITIALIZE, UPDATE, UPDATE]
    assert dll.update_values == [(0x2000D, jobs, len(jobs) * 8), (0x20002, inherited, len(inherited) * 8)]
    assert len(attributes._PINNED_RESOURCES - before) == 1
    dll.inspect_live_storage()
    startup = dll.refs[3]()
    expected = attributes.STARTUPINFOEXW()
    expected.StartupInfo.cb = 112
    expected.lpAttributeList = dll.pointer
    if len(inherited) == 3:
        expected.StartupInfo.dwFlags = 0x100
        expected.StartupInfo.hStdInput, expected.StartupInfo.hStdOutput, expected.StartupInfo.hStdError = inherited
    assert bytes(startup) == bytes(expected)
    assert not hasattr(owner, "pointer") and not hasattr(owner, "handles")
    assert not hasattr(owner, "launch") and not hasattr(owner, "__enter__")
    assert "0x" not in repr(attributes._PINNED_RESOURCES)
    owner.release()
    assert owner.ownership.value == "retired"
    assert attributes._PINNED_RESOURCES == before
    assert startup.lpAttributeList is None and startup.StartupInfo.cb == 0
    assert dll.resource_ref().buffer is None and dll.resource_ref().values is None
    assert [name for name, _ in dll.calls] == [INITIALIZE, "last_error", INITIALIZE, UPDATE, UPDATE, DELETE]
    with pytest.raises(WindowsVerificationError) as caught:
        owner.release()
    assert caught.value.category is Category.OWNERSHIP and caught.value.cleanup_confirmed
    assert dll.counts[DELETE] == 1


@pytest.mark.parametrize("count,status", [(1, 1), (1, True), (1, None), (2, 0)])
def test_transaction_initialize_failure_never_updates_or_deletes_uninitialized_list(count: int, status: Any) -> None:
    before = set(attributes._PINNED_RESOURCES)
    dll = TransactionDLL()
    dll.outcomes[(INITIALIZE, count)] = status
    with pytest.raises(WindowsVerificationError) as caught:
        attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
    assert caught.value.cleanup_confirmed
    assert attributes._PINNED_RESOURCES == before
    assert UPDATE not in dll.counts and DELETE not in dll.counts
    if count == 2:
        assert caught.value.winerror == 702
        assert [name for name, _ in dll.calls] == [INITIALIZE, "last_error", INITIALIZE, "last_error"]
    else:
        assert [name for name, _ in dll.calls] == [INITIALIZE]


@pytest.mark.parametrize("count", [1, 2])
@pytest.mark.parametrize("status", [0, None, True, 1 << 31])
def test_failed_update_deletes_once_preserving_first_numeric_cause(count: int, status: Any) -> None:
    before = set(attributes._PINNED_RESOURCES)
    dll = TransactionDLL()
    dll.outcomes[(UPDATE, count)] = status
    with pytest.raises(WindowsVerificationError) as caught:
        attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
    assert caught.value.cleanup_confirmed
    assert caught.value.winerror == (700 + count if status == 0 and type(status) is int else None)
    assert caught.value.category is (Category.OS_API if type(status) is int and status == 0 else Category.UNCERTAIN_STATE)
    expected = [INITIALIZE, "last_error", INITIALIZE] + [UPDATE] * count
    if type(status) is int and status == 0:
        expected += ["last_error"]
    assert [name for name, _ in dll.calls] == expected + [DELETE]
    assert dll.counts[DELETE] == 1 and attributes._PINNED_RESOURCES == before


@pytest.mark.parametrize("length", [0, 127, 129, 65_537])
def test_second_initialize_unexpected_length_retires_before_any_update(length: int) -> None:
    before = set(attributes._PINNED_RESOURCES)
    dll = TransactionDLL()
    dll.initialized_length = length
    with pytest.raises(WindowsVerificationError) as caught:
        attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
    assert caught.value.category is Category.UNCERTAIN_STATE
    assert caught.value.cleanup_confirmed
    assert UPDATE not in dll.counts and dll.counts[DELETE] == 1
    assert attributes._PINNED_RESOURCES == before


@pytest.mark.parametrize("status", [-1, -(1 << 31), (1 << 31) - 1])
def test_transaction_accepts_signed_nonzero_initialize_and_update(status: int) -> None:
    dll = TransactionDLL()
    for name, count in ((INITIALIZE, 2), (UPDATE, 1), (UPDATE, 2)):
        dll.outcomes[(name, count)] = status
    owner = attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
    owner.release()
    assert dll.counts[DELETE] == 1


@pytest.mark.parametrize("point", ["startup", "publication", "first_update", "second_update"])
@pytest.mark.parametrize("fault", [MemoryError, KeyboardInterrupt, SystemExit])
def test_post_initialize_python_failure_uses_the_same_one_shot_cleanup(
    monkeypatch: pytest.MonkeyPatch, point: str, fault: Any,
) -> None:
    before = set(attributes._PINNED_RESOURCES)
    dll = TransactionDLL()
    def fail(*args: Any, **kwargs: Any) -> Any:
        raise fault("secret source error/argv/env/pointer")
    if point == "startup":
        monkeypatch.setattr(attributes, "_complete_startup", fail)
    elif point == "publication":
        monkeypatch.setattr(attributes, "PreparedLaunchAttributes", fail)
    else:
        dll.callbacks[(UPDATE, 1 if point == "first_update" else 2)] = fail
    with pytest.raises(WindowsVerificationError) as caught:
        attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
    assert caught.value.category is (Category.RESOURCE if fault is MemoryError else Category.UNCERTAIN_STATE)
    assert caught.value.cleanup_confirmed
    assert "secret" not in str(caught.value) + repr(caught.value)
    assert dll.counts[DELETE] == 1
    assert attributes._PINNED_RESOURCES == before


@pytest.mark.parametrize("point", ["first_update", "second_update", "publication"])
@pytest.mark.parametrize("fault", [OSError, KeyboardInterrupt, MemoryError])
def test_uncertain_delete_quarantines_buffers_even_after_constructor_failure(
    monkeypatch: pytest.MonkeyPatch, point: str, fault: Any,
) -> None:
    before = set(attributes._PINNED_RESOURCES)
    dll = TransactionDLL()
    cleanup = fault("secret cleanup pointer/argv")
    cleanup.winerror = 0xFFFFFFFF
    cleanup.errno = (1 << 31) - 1
    dll.outcomes[(DELETE, 1)] = cleanup
    if point == "publication":
        def fail(*args: Any) -> Any:
            raise MemoryError("secret constructor")
        monkeypatch.setattr(attributes, "PreparedLaunchAttributes", fail)
    else:
        dll.outcomes[(UPDATE, 1 if point == "first_update" else 2)] = 0
    with pytest.raises(WindowsVerificationError) as caught:
        attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
    failure = caught.value
    assert failure.cleanup_confirmed is False
    assert failure.winerror == (None if point == "publication" else 701 if point == "first_update" else 702)
    assert len(failure.cleanup_failures) == 1
    secondary = failure.cleanup_failures[0]
    assert secondary.stage is Stage.CLEANUP and secondary.category is Category.UNCERTAIN_STATE
    assert secondary.winerror == 0xFFFFFFFF and secondary.errno == (1 << 31) - 1
    assert "secret" not in str(failure) + repr(failure.cleanup_failures)
    assert dll.counts[DELETE] == 1
    # Remove exception traceback roots: the registry must retain storage itself.
    failure.__traceback__ = None
    failure.__context__ = None
    failure.__cause__ = None
    cleanup.__traceback__ = None
    cleanup.__context__ = None
    cleanup.__cause__ = None
    gc.collect()
    assert len(attributes._PINNED_RESOURCES - before) == 1
    assert dll.resource_ref().state.value == "uncertain"
    dll.inspect_live_storage()


@pytest.mark.parametrize("status", [None, True, 1 << 31, KeyboardInterrupt("secret init")])
def test_unknown_initialization_never_deletes_or_unpins_an_unproven_list(status: Any) -> None:
    before = set(attributes._PINNED_RESOURCES)
    dll = TransactionDLL()
    dll.outcomes[(INITIALIZE, 2)] = status
    with pytest.raises(WindowsVerificationError) as caught:
        attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
    assert caught.value.cleanup_confirmed is False
    assert DELETE not in dll.counts and UPDATE not in dll.counts
    assert len(attributes._PINNED_RESOURCES - before) == 1
    assert dll.resource_ref().state.value == "uncertain"
    dll.inspect_live_storage()


def test_release_wrapper_failure_is_terminal_and_cannot_be_retried() -> None:
    dll = TransactionDLL()
    owner = attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
    dll.outcomes[(DELETE, 1)] = OSError("secret cleanup")
    with pytest.raises(WindowsVerificationError) as caught:
        owner.release()
    assert not caught.value.cleanup_confirmed and caught.value.category is Category.UNCERTAIN_STATE
    assert owner.ownership.value == "uncertain"
    dll.inspect_live_storage()
    with pytest.raises(WindowsVerificationError) as caught:
        owner.release()
    assert caught.value.category is Category.OWNERSHIP and not caught.value.cleanup_confirmed
    assert dll.counts[DELETE] == 1


def test_release_claim_prevents_concurrent_and_reentrant_double_delete() -> None:
    dll = TransactionDLL()
    owner = attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
    entered, resume = Event(), Event()
    failures = []
    def deletion_callback() -> None:
        with pytest.raises(WindowsVerificationError) as caught:
            owner.release()
        assert not caught.value.cleanup_confirmed
        entered.set()
        assert resume.wait(5)
    dll.callbacks[(DELETE, 1)] = deletion_callback
    def release() -> None:
        try:
            owner.release()
        except BaseException as error:
            failures.append(error)
    thread = Thread(target=release, daemon=True)
    thread.start()
    try:
        assert entered.wait(5)
        assert owner.ownership.value == "retiring"
        with pytest.raises(WindowsVerificationError) as caught:
            owner.release()
        assert caught.value.category is Category.OWNERSHIP
        assert not caught.value.cleanup_confirmed
    finally:
        resume.set()
        thread.join(5)
    assert not thread.is_alive() and failures == []
    assert owner.ownership.value == "retired" and dll.counts[DELETE] == 1


@pytest.mark.parametrize("length", [0, 65_537, (1 << 64) - 1])
def test_transaction_rejects_sizing_length_before_allocation_or_initialization(length: int) -> None:
    before = set(attributes._PINNED_RESOURCES)
    dll = TransactionDLL()
    dll.length = length
    with pytest.raises(WindowsVerificationError) as caught:
        attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
    assert caught.value.category is Category.RESOURCE and caught.value.cleanup_confirmed
    assert [name for name, _ in dll.calls] == [INITIALIZE, "last_error"]
    assert attributes._PINNED_RESOURCES == before


def test_transaction_rejects_unexpected_sizing_error_before_allocation() -> None:
    dll = TransactionDLL()
    dll.outcomes[(INITIALIZE, 1)] = 0  # Injected error is 701, not expected 122.
    with pytest.raises(WindowsVerificationError) as caught:
        attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
    assert caught.value.winerror == 701 and caught.value.cleanup_confirmed
    assert [name for name, _ in dll.calls] == [INITIALIZE, "last_error"]


@pytest.mark.parametrize("fault", ["memory", "unaligned", "short", "oversized", "nonzero", "wrong_type"])
def test_allocation_faults_stop_before_native_initialize(monkeypatch: pytest.MonkeyPatch, fault: str) -> None:
    before = set(attributes._PINNED_RESOURCES)
    dll = TransactionDLL()
    def allocate(size: int) -> Any:
        if fault == "memory":
            raise MemoryError("secret allocation")
        if fault == "unaligned":
            return (ctypes.c_ubyte * size).from_buffer((ctypes.c_uint64 * 17)(), 1)
        if fault == "short":
            return (ctypes.c_uint64 * 1)()
        if fault == "oversized":
            return (ctypes.c_uint64 * 8193)()
        if fault == "wrong_type":
            return None
        return (ctypes.c_uint64 * 16)(1)
    monkeypatch.setattr(attributes, "_allocate_attribute_buffer", allocate)
    with pytest.raises(WindowsVerificationError) as caught:
        attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
    assert caught.value.category is Category.RESOURCE and caught.value.cleanup_confirmed
    assert "secret" not in str(caught.value)
    assert [name for name, _ in dll.calls] == [INITIALIZE, "last_error"]
    assert attributes._PINNED_RESOURCES == before


@pytest.mark.parametrize("after_registration", [False, True])
def test_registration_fault_precedes_initialization_and_leaves_no_native_resource(
    monkeypatch: pytest.MonkeyPatch, after_registration: bool,
) -> None:
    before = set(attributes._PINNED_RESOURCES)
    original = attributes._register_resource
    def fail(resource: Any) -> None:
        if after_registration:
            original(resource)
        raise MemoryError("secret ledger")
    monkeypatch.setattr(attributes, "_register_resource", fail)
    dll = TransactionDLL()
    with pytest.raises(WindowsVerificationError) as caught:
        attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
    assert caught.value.cleanup_confirmed
    assert [name for name, _ in dll.calls] == [INITIALIZE, "last_error"]
    assert attributes._PINNED_RESOURCES == before


def test_transaction_rejects_bad_role_input_or_api_before_sizing() -> None:
    dll = TransactionDLL()
    checked = api(dll)
    with pytest.raises(WindowsVerificationError):
        attributes.prepare_worker_attributes(attributes.PayloadLaunchInputs(**PAYLOAD_HANDLES), checked)
    inputs = attributes.WorkerLaunchInputs(**WORKER_HANDLES)
    object.__setattr__(inputs, "supervision_job", True)
    with pytest.raises(WindowsVerificationError):
        attributes.prepare_worker_attributes(inputs, checked)
    with pytest.raises(WindowsVerificationError):
        attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), object())
    assert dll.calls == []


@pytest.mark.parametrize("fault", [MemoryError, KeyboardInterrupt])
def test_initialization_success_is_recorded_before_checked_wrapper_returns(fault: Any) -> None:
    class InterruptedApi(attributes.CheckedAttributeApi):
        def initialize_attribute_list(self, *args: Any, **kwargs: Any) -> None:
            super().initialize_attribute_list(*args, **kwargs)
            raise fault("secret after successful initialize")
    before = set(attributes._PINNED_RESOURCES)
    dll = TransactionDLL()
    checked = InterruptedApi(dll, dll.last_error)
    with pytest.raises(WindowsVerificationError) as caught:
        attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), checked)
    assert caught.value.cleanup_confirmed
    assert [name for name, _ in dll.calls] == [INITIALIZE, "last_error", INITIALIZE, DELETE]
    assert attributes._PINNED_RESOURCES == before


@pytest.mark.parametrize("result", [None, 0, 1, False])
def test_transaction_void_retirement_has_no_invented_bool_check(result: Any) -> None:
    dll = TransactionDLL()
    owner = attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
    dll.outcomes[(DELETE, 1)] = result
    owner.release()
    assert owner.ownership.value == "retired"
    assert [name for name, _ in dll.calls][-1] == DELETE
    assert dll.counts[DELETE] == 1


@pytest.mark.parametrize("size", [True, None, "128", 0, -1, 65_537])
def test_injected_sizing_result_cannot_bypass_resource_limit(size: Any) -> None:
    class BadSizingApi:
        def required_size(self) -> Any:
            return size
        initialize_attribute_list = staticmethod(forbidden_native)
        update_attribute = staticmethod(forbidden_native)
        delete_attribute_list = staticmethod(forbidden_native)
    before = set(attributes._PINNED_RESOURCES)
    with pytest.raises(WindowsVerificationError) as caught:
        attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), BadSizingApi())
    assert caught.value.category is Category.RESOURCE and caught.value.cleanup_confirmed
    assert attributes._PINNED_RESOURCES == before


class AuditInterruption(BaseException):
    pass


class UnreadableDiagnostic(AuditInterruption):
    @property
    def winerror(self) -> Any:
        raise MemoryError("secret winerror accessor")

    @property
    def errno(self) -> Any:
        raise KeyboardInterrupt("secret errno accessor")

    def __str__(self) -> str:
        raise AssertionError("exception text must not be read")


def test_lifecycle_audit_metadata_accessor_failure_cannot_replace_primary_error() -> None:
    dll = TransactionDLL()
    dll.outcomes[(UPDATE, 1)] = 0
    dll.outcomes[(DELETE, 1)] = UnreadableDiagnostic()
    with pytest.raises(WindowsVerificationError) as caught:
        attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
    assert caught.value.stage is Stage.PREFLIGHT
    assert caught.value.category is Category.OS_API and caught.value.winerror == 701
    assert not caught.value.cleanup_confirmed
    assert len(caught.value.cleanup_failures) == 1
    secondary = caught.value.cleanup_failures[0]
    assert secondary.stage is Stage.CLEANUP and secondary.category is Category.UNCERTAIN_STATE
    assert secondary.winerror is None and secondary.errno is None
    assert dll.counts[DELETE] == 1
    dll.inspect_live_storage()


def test_lifecycle_audit_claim_exit_exception_is_bounded_pinned_and_not_retried() -> None:
    dll = TransactionDLL()
    owner = attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
    resource = owner._resource
    original = resource.lock
    class InterruptedClaim:
        failed = False
        def __enter__(self) -> None:
            original.acquire()
        def __exit__(self, *args: Any) -> None:
            original.release()
            if not self.failed and resource.state.value == "retiring":
                self.failed = True
                raise AuditInterruption("secret after claim")
    resource.lock = InterruptedClaim()
    with pytest.raises(WindowsVerificationError) as caught:
        owner.release()
    assert caught.value.category is Category.UNCERTAIN_STATE
    assert not caught.value.cleanup_confirmed
    assert owner.ownership.value == "uncertain"
    dll.inspect_live_storage()
    with pytest.raises(WindowsVerificationError):
        owner.release()
    assert DELETE not in dll.counts


@pytest.mark.parametrize("attribute", ["restype", "argtypes"])
def test_lifecycle_audit_damaged_binding_is_rejected_before_native_call(attribute: str) -> None:
    dll = TransactionDLL()
    checked = api(dll)
    setattr(getattr(dll, UPDATE), attribute, None)
    owner = None
    try:
        with pytest.raises(WindowsVerificationError) as caught:
            owner = attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), checked)
        assert caught.value.category is Category.OS_API and caught.value.cleanup_confirmed
        assert UPDATE not in dll.counts
        assert dll.counts[DELETE] == 1
    finally:
        if owner is not None:
            owner.release()


def test_lifecycle_audit_cleanup_bookkeeping_failure_preserves_preinit_cause(monkeypatch: pytest.MonkeyPatch) -> None:
    dll = TransactionDLL()
    dll.outcomes[(INITIALIZE, 2)] = 0
    def fail(resource: Any) -> None:
        raise AuditInterruption("secret bookkeeping")
    monkeypatch.setattr(attributes, "_discard_resource", fail)
    with pytest.raises(WindowsVerificationError) as caught:
        attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
    assert caught.value.category is Category.OS_API and caught.value.winerror == 702
    assert not caught.value.cleanup_confirmed
    assert len(caught.value.cleanup_failures) == 1
    assert caught.value.cleanup_failures[0].category is Category.UNCERTAIN_STATE
    assert DELETE not in dll.counts
    dll.inspect_live_storage()


def test_lifecycle_audit_retirement_attempt_invalidates_stale_startup_reference() -> None:
    dll = TransactionDLL()
    owner = attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
    startup = dll.refs[3]()
    assert startup.StartupInfo.cb == 112 and startup.lpAttributeList is not None
    dll.outcomes[(DELETE, 1)] = AuditInterruption("secret delete")
    with pytest.raises(WindowsVerificationError):
        owner.release()
    assert startup.lpAttributeList is None and startup.StartupInfo.cb == 0
    dll.inspect_live_storage()


@pytest.mark.parametrize("corruption", ["args", "stage", "numeric", "notes", "secondary"])
def test_lifecycle_audit_injected_checked_error_cannot_smuggle_diagnostics(corruption: str) -> None:
    dll = TransactionDLL()
    checked = api(dll)
    primary = WindowsVerificationError(Stage.PREFLIGHT, Category.OS_API, winerror=55, errno=2)
    if corruption == "args":
        primary.args = ("secret argv/cwd/environment/transcript",)
    elif corruption == "stage":
        primary.stage = "secret stage/pointer"  # type: ignore[assignment]
    elif corruption == "numeric":
        primary.winerror = True
        primary.errno = 1 << 31
    elif corruption == "notes":
        primary.add_note("secret note/handle/pointer")
    else:
        primary.cleanup_failures = ("secret transcript",)  # type: ignore[assignment]
    class InjectedApi:
        required_size = checked.required_size
        initialize_attribute_list = checked.initialize_attribute_list
        delete_attribute_list = checked.delete_attribute_list
        def update_attribute(self, *args: Any) -> None:
            raise primary
    with pytest.raises(WindowsVerificationError) as caught:
        attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), InjectedApi())
    failure = caught.value
    assert type(failure.stage) is Stage and type(failure.category) is Category
    assert "secret" not in str(failure) + repr(failure) + repr(failure.cleanup_failures)
    assert not getattr(failure, "__notes__", ())
    assert failure.winerror == (None if corruption == "numeric" else 55)
    assert failure.errno == (None if corruption == "numeric" else 2)
    assert failure.cleanup_confirmed and dll.counts[DELETE] == 1


@pytest.mark.parametrize("input_type,prepare,handles,jobs,inherited", TRANSACTION_CASES)
@pytest.mark.parametrize("point", [1, 2])
@pytest.mark.parametrize("fault", ["zero", "bool", "none", "overflow", "memory", "keyboard", "base"])
@pytest.mark.parametrize("delete_fails", [False, True])
def test_audited_update_failure_matrix_for_both_roles(
    input_type: Any, prepare: Any, handles: dict[str, int], jobs: list[int], inherited: list[int],
    point: int, fault: str, delete_fails: bool,
) -> None:
    before = set(attributes._PINNED_RESOURCES)
    dll = transaction_dll(jobs, inherited)
    statuses = {"zero": 0, "bool": False, "none": None, "overflow": -(1 << 31) - 1,
                "memory": MemoryError("secret allocation"), "keyboard": KeyboardInterrupt("secret argv"),
                "base": AuditInterruption("secret transcript")}
    dll.outcomes[(UPDATE, point)] = statuses[fault]
    if delete_fails:
        dll.outcomes[(DELETE, 1)] = UnreadableDiagnostic()
    with pytest.raises(WindowsVerificationError) as caught:
        prepare(input_type(**handles), api(dll))
    failure = caught.value
    assert failure.stage is Stage.PREFLIGHT
    expected_category = (Category.OS_API if fault == "zero" else
                         Category.RESOURCE if fault == "memory" else Category.UNCERTAIN_STATE)
    assert failure.category is expected_category
    assert failure.winerror == (700 + point if fault == "zero" else None)
    assert failure.cleanup_confirmed is not delete_fails
    assert len(failure.cleanup_failures) == int(delete_fails)
    assert dll.counts[UPDATE] == point and dll.counts[DELETE] == 1
    assert "secret" not in str(failure) + repr(failure.cleanup_failures)
    expected_calls = [INITIALIZE, "last_error", INITIALIZE] + [UPDATE] * point
    if fault == "zero":
        expected_calls += ["last_error"]
    assert [name for name, _ in dll.calls] == expected_calls + [DELETE]
    assert len(attributes._PINNED_RESOURCES - before) == int(delete_fails)
    if delete_fails:
        dll.inspect_live_storage()
        assert dll.refs[3]().lpAttributeList is None
        assert attributes._retire_resource(dll.resource_ref(), only_ready=False).category is Category.OWNERSHIP
        assert dll.counts[DELETE] == 1


@pytest.mark.parametrize("function", FUNCTIONS)
@pytest.mark.parametrize("damage", ["restype", "argtypes", "missing", "in_place"])
def test_audited_binding_damage_matrix_before_each_native_operation(function: str, damage: str) -> None:
    before = set(attributes._PINNED_RESOURCES)
    dll = TransactionDLL()
    checked = api(dll)
    owner = (attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), checked)
             if function == DELETE else None)
    binding = getattr(dll, function)
    if damage == "restype":
        binding.restype = ctypes.c_int64
    elif damage == "argtypes":
        binding.argtypes = None
    elif damage == "missing":
        del binding.restype
    else:
        binding.argtypes[0] = ctypes.c_uint32
    with pytest.raises(WindowsVerificationError) as caught:
        if owner is None:
            attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), checked)
        else:
            owner.release()
    if function == DELETE:
        assert caught.value.category is Category.UNCERTAIN_STATE and not caught.value.cleanup_confirmed
        assert DELETE not in dll.counts and owner.ownership.value == "uncertain"
        dll.inspect_live_storage()
        with pytest.raises(WindowsVerificationError):
            owner.release()
        assert len(attributes._PINNED_RESOURCES - before) == 1
    else:
        assert caught.value.category is Category.OS_API and caught.value.cleanup_confirmed
        assert attributes._PINNED_RESOURCES == before
        if function == INITIALIZE:
            assert dll.calls == []
        else:
            assert UPDATE not in dll.counts and dll.counts[DELETE] == 1


@pytest.mark.parametrize("count", [1, 2])
@pytest.mark.parametrize("bad_status", [False, None, "secret status", 0.0, 1 << 31, -(1 << 31) - 1])
def test_audited_initialize_malformed_status_never_grants_a_resource(count: int, bad_status: Any) -> None:
    before = set(attributes._PINNED_RESOURCES)
    dll = TransactionDLL()
    dll.outcomes[(INITIALIZE, count)] = bad_status
    with pytest.raises(WindowsVerificationError) as caught:
        attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
    assert caught.value.category is Category.UNCERTAIN_STATE
    assert caught.value.cleanup_confirmed is (count == 1)
    assert UPDATE not in dll.counts and DELETE not in dll.counts
    assert dll.counts[INITIALIZE] == count
    assert len(attributes._PINNED_RESOURCES - before) == int(count == 2)
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize("count", [1, 2])
@pytest.mark.parametrize("bad_error", [None, True, -1, 1 << 32, "secret WinError", KeyboardInterrupt("secret reader")])
def test_audited_invalid_error_copy_cannot_turn_zero_bool_into_success(count: int, bad_error: Any) -> None:
    dll = TransactionDLL()
    def reader() -> Any:
        dll.calls.append(("last_error", ()))
        if dll.counts[INITIALIZE] != count:
            return 122
        if isinstance(bad_error, BaseException):
            raise bad_error
        return bad_error
    if count == 2:
        dll.outcomes[(INITIALIZE, 2)] = 0
    checked = attributes.CheckedAttributeApi(dll, reader)
    with pytest.raises(WindowsVerificationError) as caught:
        attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), checked)
    assert caught.value.category is Category.UNCERTAIN_STATE
    assert caught.value.winerror is None and caught.value.cleanup_confirmed
    assert [name for name, _ in dll.calls][-2:] == [INITIALIZE, "last_error"]
    assert UPDATE not in dll.counts and DELETE not in dll.counts


@pytest.mark.parametrize("winerror,errno", [
    (0, 0), (0xFFFFFFFF, 0x7FFFFFFF), (0x80000000, 0x80000000),
    (0x100000000, 0xFFFFFFFF), (-1, -1), (True, False), (None, None),
    ("secret", 1.0), (ctypes.c_uint32(5), ctypes.c_int32(6)),
])
def test_audited_diagnostic_ranges_and_redaction_for_primary_and_cleanup(winerror: Any, errno: Any) -> None:
    dll = TransactionDLL()
    marker = "secret handle=44556677 pointer=0xabcdef argv cwd environment transcript"
    primary = OSError(marker)
    primary.winerror, primary.errno = winerror, errno
    cleanup = AuditInterruption(marker)
    cleanup.winerror, cleanup.errno = winerror, errno
    dll.outcomes[(UPDATE, 1)] = primary
    dll.outcomes[(DELETE, 1)] = cleanup
    with pytest.raises(WindowsVerificationError) as caught:
        attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
    failure = caught.value
    expected_winerror = winerror if type(winerror) is int and 0 <= winerror <= 0xFFFFFFFF else None
    expected_errno = errno if type(errno) is int and 0 <= errno <= 0x7FFFFFFF else None
    assert failure.winerror == expected_winerror and failure.errno == expected_errno
    assert not failure.cleanup_confirmed and failure.timed_out is False
    secondary = failure.cleanup_failures[0]
    assert secondary.winerror == expected_winerror and secondary.errno == expected_errno
    assert type(failure.stage) is Stage and type(failure.category) is Category
    assert type(secondary.stage) is Stage and type(secondary.category) is Category
    rendered = str(failure) + repr(failure) + repr(secondary) + repr(dll.resource_ref())
    assert all(part not in rendered for part in marker.split())
    assert "0x" not in repr(attributes._PINNED_RESOURCES)


@pytest.mark.parametrize("delete_fails", [False, True])
def test_audited_simultaneous_reentrant_retirement_has_one_claim(delete_fails: bool) -> None:
    before = set(attributes._PINNED_RESOURCES)
    dll = TransactionDLL()
    owner = attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
    start = Barrier(3)
    entered, loser_done, allow_return = Event(), Event(), Event()
    result_lock = Lock()
    results: dict[str, BaseException | None] = {}
    if delete_fails:
        dll.outcomes[(DELETE, 1)] = AuditInterruption("secret concurrent Delete")
    def blocked_delete() -> None:
        with pytest.raises(WindowsVerificationError) as caught:
            owner.release()
        assert caught.value.category is Category.OWNERSHIP
        assert not caught.value.cleanup_confirmed
        entered.set()
        assert allow_return.wait(5)  # Deadlock guard only, never a timing oracle.
    dll.callbacks[(DELETE, 1)] = blocked_delete
    def contender(name: str) -> None:
        try:
            start.wait(5)
            owner.release()
        except BaseException as error:
            with result_lock:
                results[name] = error
            loser_done.set()
        else:
            with result_lock:
                results[name] = None
    threads = [Thread(target=contender, args=(name,), daemon=True) for name in ("a", "b")]
    for thread in threads:
        thread.start()
    try:
        start.wait(5)
        assert entered.wait(5) and loser_done.wait(5)
        # Winner cannot have returned: the fake has not been allowed to return.
        assert len(results) == 1
        loser = next(iter(results.values()))
        assert isinstance(loser, WindowsVerificationError)
        assert loser.category is Category.OWNERSHIP and not loser.cleanup_confirmed
        assert owner.ownership.value == "retiring" and dll.counts[DELETE] == 1
        dll.inspect_live_storage()
        assert dll.refs[3]().lpAttributeList is None and dll.refs[3]().StartupInfo.cb == 0
    finally:
        allow_return.set()
        for thread in threads:
            thread.join(5)
    assert all(not thread.is_alive() for thread in threads)
    assert len(results) == 2 and dll.counts[DELETE] == 1
    assert all(result is None or isinstance(result, WindowsVerificationError) for result in results.values())
    assert sum(result is None for result in results.values()) == int(not delete_fails)
    assert owner.ownership.value == ("uncertain" if delete_fails else "retired")
    assert len(attributes._PINNED_RESOURCES - before) == int(delete_fails)
    with pytest.raises(WindowsVerificationError) as caught:
        owner.release()
    assert caught.value.cleanup_confirmed is not delete_fails and dll.counts[DELETE] == 1


@pytest.mark.parametrize("delete_fails", [False, True])
def test_audited_constructor_failure_during_inflight_retirement_never_confirms_cleanup(
    monkeypatch: pytest.MonkeyPatch, delete_fails: bool,
) -> None:
    before = set(attributes._PINNED_RESOURCES)
    dll = TransactionDLL()
    original = attributes.PreparedLaunchAttributes
    entered, allow_return = Event(), Event()
    threads: list[Thread] = []
    background_errors: list[BaseException] = []
    owners = []
    primary = WindowsVerificationError(Stage.PREFLIGHT, Category.RESOURCE, winerror=55, errno=2)
    if delete_fails:
        dll.outcomes[(DELETE, 1)] = AuditInterruption("secret asynchronous Delete")
    def blocked_delete() -> None:
        entered.set()
        assert allow_return.wait(5)
    dll.callbacks[(DELETE, 1)] = blocked_delete
    def abort_publication(resource: Any) -> Any:
        owner = original(resource)
        owners.append(owner)
        def retire() -> None:
            try:
                owner.release()
            except BaseException as error:
                background_errors.append(error)
        thread = Thread(target=retire, daemon=True)
        threads.append(thread)
        thread.start()
        assert entered.wait(5)
        raise primary
    monkeypatch.setattr(attributes, "PreparedLaunchAttributes", abort_publication)
    try:
        with pytest.raises(WindowsVerificationError) as caught:
            attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
        assert caught.value is primary
        assert primary.winerror == 55 and primary.errno == 2
        assert not primary.cleanup_confirmed
        assert len(primary.cleanup_failures) == 1
        assert primary.cleanup_failures[0].category is Category.OWNERSHIP
        assert owners[0].ownership.value == "retiring" and dll.counts[DELETE] == 1
        dll.inspect_live_storage()
    finally:
        allow_return.set()
        for thread in threads:
            thread.join(5)
    assert threads and all(not thread.is_alive() for thread in threads)
    assert len(background_errors) == int(delete_fails)
    assert all(isinstance(error, WindowsVerificationError) for error in background_errors)
    assert owners[0].ownership.value == ("uncertain" if delete_fails else "retired")
    # Earlier uncertainty diagnostics are facts at return time, not a live flag.
    assert not primary.cleanup_confirmed and dll.counts[DELETE] == 1
    assert len(attributes._PINNED_RESOURCES - before) == int(delete_fails)


@pytest.mark.parametrize("point", ["registered", "initialized", "startup", "publication"])
@pytest.mark.parametrize("fault", [MemoryError, KeyboardInterrupt, AuditInterruption])
def test_audited_exception_windows_between_registration_and_publication(
    monkeypatch: pytest.MonkeyPatch, point: str, fault: Any,
) -> None:
    before = set(attributes._PINNED_RESOURCES)
    dll = TransactionDLL()
    checked = api(dll)
    def fail() -> None:
        raise fault("secret fault window")
    if point == "registered":
        original_register = attributes._register_resource
        def register(resource: Any) -> None:
            original_register(resource)
            fail()
        monkeypatch.setattr(attributes, "_register_resource", register)
    elif point == "initialized":
        class InterruptedApi(attributes.CheckedAttributeApi):
            def initialize_attribute_list(self, *args: Any, **kwargs: Any) -> None:
                super().initialize_attribute_list(*args, **kwargs)
                fail()
        checked = InterruptedApi(dll, dll.last_error)
    elif point == "startup":
        original_complete = attributes._complete_startup
        def complete(resource: Any) -> None:
            original_complete(resource)
            fail()
        monkeypatch.setattr(attributes, "_complete_startup", complete)
    else:
        original_owner = attributes.PreparedLaunchAttributes
        class InterruptedOwner(original_owner):
            def __init__(self, resource: Any) -> None:
                super().__init__(resource)
                fail()
        monkeypatch.setattr(attributes, "PreparedLaunchAttributes", InterruptedOwner)
    with pytest.raises(WindowsVerificationError) as caught:
        attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), checked)
    assert caught.value.cleanup_confirmed
    assert caught.value.category is (Category.RESOURCE if fault is MemoryError else Category.UNCERTAIN_STATE)
    assert dll.counts.get(DELETE, 0) == int(point != "registered")
    assert attributes._PINNED_RESOURCES == before


def test_audited_retired_owner_cannot_republish_or_produce_native_pointer() -> None:
    dll = TransactionDLL()
    owner = attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
    resource = owner._resource
    startup = dll.refs[3]()
    owner.release()
    assert resource.buffer is None and resource.values is None
    assert startup.StartupInfo.cb == 0 and startup.lpAttributeList is None
    for operation in (owner.release, lambda: attributes.PreparedLaunchAttributes(resource),
                      lambda: attributes._resource_pointer(resource)):
        with pytest.raises(WindowsVerificationError) as caught:
            operation()
        assert caught.value.category is Category.OWNERSHIP
    assert dll.counts[DELETE] == 1


@pytest.mark.parametrize("during_construction", [False, True])
def test_audited_invalidation_fault_cannot_reenter_cleanup_or_expose_attributes(
    monkeypatch: pytest.MonkeyPatch, during_construction: bool,
) -> None:
    dll = TransactionDLL()
    checked = api(dll)
    owner = None if during_construction else attributes.prepare_worker_attributes(
        attributes.WorkerLaunchInputs(**WORKER_HANDLES), checked,
    )
    if during_construction:
        dll.outcomes[(UPDATE, 1)] = 0
    attempts = []
    def fail(resource: Any) -> None:
        attempts.append(resource.state.value)
        raise AuditInterruption("secret invalidation")
    monkeypatch.setattr(attributes, "_invalidate_startup", fail)
    with pytest.raises(WindowsVerificationError) as caught:
        if owner is None:
            attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), checked)
        else:
            owner.release()
    assert caught.value.winerror == (701 if during_construction else None)
    assert not caught.value.cleanup_confirmed and len(attempts) == 1
    resource = dll.resource_ref()
    assert resource.state.value == "uncertain"
    dll.inspect_live_storage()
    with pytest.raises(WindowsVerificationError):
        attributes._resource_pointer(resource)
    with pytest.raises(WindowsVerificationError):
        attributes.PreparedLaunchAttributes(resource)
    assert attributes._retire_resource(resource, only_ready=False).category is Category.OWNERSHIP
    assert DELETE not in dll.counts and len(attempts) == 1


@pytest.mark.parametrize("function", FUNCTIONS)
@pytest.mark.parametrize("fault", [MemoryError, KeyboardInterrupt, AuditInterruption])
def test_audited_binding_wrapper_baseexceptions_are_bounded_before_any_operation(function: str, fault: Any) -> None:
    dll = TransactionDLL()
    class InterruptedBinding(FakeFunction):
        def __setattr__(self, name: str, value: Any) -> None:
            if name == "argtypes" and type(value) is list:
                raise fault("secret binding/argv/environment")
            super().__setattr__(name, value)
    setattr(dll, function, InterruptedBinding(dll, function))
    with pytest.raises(WindowsVerificationError) as caught:
        api(dll)
    assert caught.value.stage is Stage.PREFLIGHT and caught.value.category is Category.OS_API
    assert caught.value.cleanup_confirmed and dll.calls == []
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize("broken_field", ["winerror", "errno"])
def test_audited_diagnostic_accessor_fault_does_not_drop_the_other_numeric_field(broken_field: str) -> None:
    class PartlyReadable(AuditInterruption):
        @property
        def winerror(self) -> Any:
            if broken_field == "winerror":
                raise AuditInterruption("secret metadata")
            return 0xFFFFFFFF
        @property
        def errno(self) -> Any:
            if broken_field == "errno":
                raise MemoryError("secret metadata")
            return 0x7FFFFFFF
    dll = TransactionDLL()
    dll.outcomes[(UPDATE, 1)] = PartlyReadable()
    with pytest.raises(WindowsVerificationError) as caught:
        attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
    assert caught.value.winerror == (None if broken_field == "winerror" else 0xFFFFFFFF)
    assert caught.value.errno == (None if broken_field == "errno" else 0x7FFFFFFF)
    assert caught.value.cleanup_confirmed and dll.counts[DELETE] == 1


@pytest.mark.parametrize("reported_stage", [Stage.PREFLIGHT, Stage.JOBS, Stage.CLOSE, Stage.CLEANUP])
@pytest.mark.parametrize("reported_timeout", [False, True])
def test_repair_setup_diagnostic_uses_actual_stage_and_never_invents_timeout(
    reported_stage: Stage, reported_timeout: bool,
) -> None:
    dll = TransactionDLL()
    checked = api(dll)
    source = WindowsVerificationError(reported_stage, Category.OS_API, winerror=55, errno=2)
    source.timed_out = reported_timeout
    class InjectedApi:
        required_size = checked.required_size
        initialize_attribute_list = checked.initialize_attribute_list
        delete_attribute_list = checked.delete_attribute_list
        def update_attribute(self, *args: Any) -> None:
            raise source
    with pytest.raises(WindowsVerificationError) as caught:
        attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), InjectedApi())
    failure = caught.value
    assert failure.stage is Stage.PREFLIGHT and failure.category is Category.OS_API
    assert failure.timed_out is False
    assert failure.winerror == 55 and failure.errno == 2
    assert str(failure) == "preflight/os_api"
    assert failure.cleanup_confirmed and dll.counts[DELETE] == 1


class BrokenResourceLock:
    """Faults never block: any dangerous reacquisition fails immediately too."""

    def __init__(self, original: Any, mode: str) -> None:
        self.original = original
        self.mode = mode
        self.entries = 0
        self.exits = 0
        self.held = False

    def _failure(self, code: int) -> Any:
        error = AuditInterruption("secret broken-lock context")
        error.winerror = code
        error.errno = 9
        raise error

    def __enter__(self) -> None:
        self.entries += 1
        if self.entries > 1:
            self._failure(402)
        if self.mode == "enter_before":
            self._failure(401)
        assert self.original.acquire(blocking=False), "unsafe reacquisition must never wait"
        self.held = True
        if self.mode == "enter_after":
            self._failure(401)

    def __exit__(self, *args: Any) -> None:
        self.exits += 1
        if self.mode == "exit_before":
            self._failure(401)
        self.original.release()
        self.held = False
        self._failure(401)

    def release_test_lock(self) -> None:
        # Only the fake knows whether it acquired this test-owned mutex. The
        # production owner must neither infer ownership nor retry this release.
        if self.held:
            self.original.release()
            self.held = False


@pytest.mark.parametrize("mode", ["enter_before", "enter_after", "exit_before", "exit_after"])
def test_repair_retirement_lock_fault_never_reacquires_or_loses_claim(mode: str) -> None:
    dll = TransactionDLL()
    owner = attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
    resource = owner._resource
    broken = BrokenResourceLock(resource.lock, mode)
    resource.lock = broken
    try:
        with pytest.raises(WindowsVerificationError) as caught:
            owner.release()
        assert caught.value.stage is Stage.CLEANUP
        assert caught.value.category is Category.UNCERTAIN_STATE
        assert caught.value.winerror == 401 and not caught.value.cleanup_confirmed
        assert resource.state.value == "uncertain"
        assert owner.ownership.value == "uncertain"
        dll.inspect_live_storage()
        with pytest.raises(WindowsVerificationError) as caught:
            owner.release()
        assert caught.value.category is Category.OWNERSHIP
        assert not caught.value.cleanup_confirmed
        assert broken.entries == 1 and DELETE not in dll.counts
        with pytest.raises(WindowsVerificationError):
            attributes._resource_pointer(resource)
    finally:
        broken.release_test_lock()


@pytest.mark.parametrize("point", ["before_claim", "after_claim", "during_delete"])
def test_repair_double_cleanup_lock_fault_preserves_original_setup_error(point: str) -> None:
    dll = TransactionDLL()
    locks = []
    def break_lock() -> None:
        resource = dll.resource_ref()
        broken = BrokenResourceLock(resource.lock, "exit_before" if point == "after_claim" else "enter_after")
        locks.append(broken)
        resource.lock = broken
    if point == "before_claim":
        dll.outcomes[(INITIALIZE, 2)] = 0
        dll.callbacks[(INITIALIZE, 2)] = break_lock
    else:
        dll.outcomes[(UPDATE, 1)] = 0
        dll.callbacks[(UPDATE if point == "after_claim" else DELETE, 1)] = break_lock
        if point == "during_delete":
            error = AuditInterruption("secret Delete wrapper")
            error.winerror = 440
            dll.outcomes[(DELETE, 1)] = error
    try:
        with pytest.raises(WindowsVerificationError) as caught:
            attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
        primary = caught.value
        assert primary.stage is Stage.PREFLIGHT and primary.category is Category.OS_API
        assert primary.winerror == (702 if point == "before_claim" else 701)
        assert not primary.cleanup_confirmed and primary.timed_out is False
        assert len(primary.cleanup_failures) == 1
        secondary = primary.cleanup_failures[0]
        assert secondary.stage is Stage.CLEANUP and secondary.category is Category.UNCERTAIN_STATE
        assert secondary.winerror == (440 if point == "during_delete" else 401)
        resource = dll.resource_ref()
        assert resource.state.value == "uncertain"
        dll.inspect_live_storage()
        assert attributes._retire_resource(resource, only_ready=False).category is Category.OWNERSHIP
        assert dll.counts.get(DELETE, 0) == int(point == "during_delete")
        assert locks[0].entries == int(point != "during_delete")
        assert "secret" not in str(primary) + repr(primary.cleanup_failures)
    finally:
        for broken in locks:
            broken.release_test_lock()


@pytest.mark.parametrize("before_claim", [False, True])
def test_repair_cleanup_body_and_lock_exit_failures_keep_the_first_cause(
    monkeypatch: pytest.MonkeyPatch, before_claim: bool,
) -> None:
    dll = TransactionDLL()
    locks = []
    def break_lock() -> None:
        resource = dll.resource_ref()
        broken = BrokenResourceLock(resource.lock, "exit_before")
        locks.append(broken)
        resource.lock = broken
    if before_claim:
        dll.outcomes[(INITIALIZE, 2)] = 0
        dll.callbacks[(INITIALIZE, 2)] = break_lock
    else:
        dll.outcomes[(UPDATE, 1)] = 0
        dll.callbacks[(UPDATE, 1)] = break_lock
    def fail_invalidation(resource: Any) -> None:
        error = AuditInterruption("secret cleanup body")
        error.winerror = 410
        raise error
    monkeypatch.setattr(attributes, "_invalidate_startup", fail_invalidation)
    try:
        with pytest.raises(WindowsVerificationError) as caught:
            attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
        assert caught.value.winerror == (702 if before_claim else 701)
        assert not caught.value.cleanup_confirmed
        assert caught.value.cleanup_failures[0].winerror == 410
        resource = dll.resource_ref()
        assert resource.lock_failure.winerror == 401
        assert resource.state.value == "uncertain"
        assert resource._state.value == ("building" if before_claim else "retiring")
        assert locks[0].entries == 1 and locks[0].exits == 1
        assert DELETE not in dll.counts
        dll.inspect_live_storage()
    finally:
        for broken in locks:
            broken.release_test_lock()


def test_repair_repeated_failure_inside_cleanup_diagnostic_handler_preserves_primary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dll = TransactionDLL()
    dll.outcomes[(UPDATE, 1)] = 0
    dll.outcomes[(DELETE, 1)] = AuditInterruption("secret cleanup wrapper")
    original = attributes._bounded_exception
    failures = []
    def broken_diagnostic(error: BaseException, stage: Stage, category: Category) -> Any:
        if stage is Stage.CLEANUP:
            failures.append(stage)
            raise MemoryError("secret secondary diagnostic construction")
        return original(error, stage, category)
    monkeypatch.setattr(attributes, "_bounded_exception", broken_diagnostic)
    with pytest.raises(WindowsVerificationError) as caught:
        attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
    assert caught.value.stage is Stage.PREFLIGHT and caught.value.category is Category.OS_API
    assert caught.value.winerror == 701 and not caught.value.cleanup_confirmed
    assert len(failures) >= 2  # Both the first cleanup projection and handler failed.
    assert caught.value.cleanup_failures == (attributes._UNKNOWN_CLEANUP,)
    assert dll.counts[DELETE] == 1
    assert dll.resource_ref().state.value == "uncertain"
    dll.inspect_live_storage()


def test_repair_lock_failure_during_another_delete_cannot_clear_its_claim() -> None:
    dll = TransactionDLL()
    owner = attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
    resource = owner._resource
    entered, allow_return = Event(), Event()
    errors = []
    def blocked_delete() -> None:
        entered.set()
        assert allow_return.wait(5)
    dll.callbacks[(DELETE, 1)] = blocked_delete
    def retire() -> None:
        try:
            owner.release()
        except BaseException as error:
            errors.append(error)
    thread = Thread(target=retire, daemon=True)
    thread.start()
    broken = None
    try:
        assert entered.wait(5)
        assert resource._state.value == "retiring"
        broken = BrokenResourceLock(resource.lock, "enter_after")
        resource.lock = broken
        with pytest.raises(WindowsVerificationError) as caught:
            owner.release()
        assert caught.value.winerror == 401 and not caught.value.cleanup_confirmed
        assert resource._state.value == "retiring"  # Never overwrite the other claim.
        assert owner.ownership.value == "uncertain"
        assert broken.entries == 1 and dll.counts[DELETE] == 1
        dll.inspect_live_storage()
    finally:
        allow_return.set()
        thread.join(5)
        if broken is not None:
            broken.release_test_lock()
    assert not thread.is_alive() and len(errors) == 1
    assert isinstance(errors[0], WindowsVerificationError) and not errors[0].cleanup_confirmed
    assert resource._state.value == "retiring" and resource.state.value == "uncertain"
    assert broken.entries == 1 and dll.counts[DELETE] == 1
    dll.inspect_live_storage()


@pytest.mark.parametrize("mode", ["enter_before", "enter_after", "exit_before", "exit_after"])
def test_repair_publication_lock_fault_keeps_initialized_storage_without_reacquiring(mode: str) -> None:
    dll = TransactionDLL()
    locks = []
    def break_lock() -> None:
        resource = dll.resource_ref()
        broken = BrokenResourceLock(resource.lock, mode)
        locks.append(broken)
        resource.lock = broken
    dll.callbacks[(UPDATE, 2)] = break_lock
    try:
        with pytest.raises(WindowsVerificationError) as caught:
            attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
        assert caught.value.stage is Stage.PREFLIGHT and caught.value.winerror == 401
        assert caught.value.timed_out is False and not caught.value.cleanup_confirmed
        assert caught.value.cleanup_failures[0].winerror == 401
        resource = dll.resource_ref()
        assert resource.state.value == "uncertain"
        assert resource.outcome.state == "initialized"
        dll.inspect_live_storage()
        with pytest.raises(WindowsVerificationError):
            attributes.PreparedLaunchAttributes(resource)
        assert locks[0].entries == 1 and DELETE not in dll.counts
    finally:
        for broken in locks:
            broken.release_test_lock()


@pytest.mark.parametrize("mode", ["enter_before", "enter_after", "exit_before", "exit_after"])
def test_repair_registration_lock_fault_does_not_retry_during_cleanup(
    monkeypatch: pytest.MonkeyPatch, mode: str,
) -> None:
    dll = TransactionDLL()
    broken = BrokenResourceLock(attributes._RESOURCE_LOCK, mode)
    monkeypatch.setattr(attributes, "_RESOURCE_LOCK", broken)
    try:
        with pytest.raises(WindowsVerificationError) as caught:
            attributes.prepare_worker_attributes(attributes.WorkerLaunchInputs(**WORKER_HANDLES), api(dll))
        assert caught.value.stage is Stage.PREFLIGHT and caught.value.winerror == 401
        assert not caught.value.cleanup_confirmed
        assert caught.value.cleanup_failures[0].winerror == 401
        assert [name for name, _ in dll.calls] == [INITIALIZE, "last_error"]
        assert broken.entries == 1
    finally:
        broken.release_test_lock()


# CP-3 checks contracts and isolation, without freezing production source text.
# The task's cumulative changed-file allowlist is audited separately through Git.
@pytest.mark.parametrize("filename", [
    "orchestrator.py", "agents.py", "repository.py", "codex_launcher.py",
])
def test_cp3_production_dispatch_does_not_activate_native_containment(filename: str) -> None:
    source = Path(attributes.__file__).with_name(filename).read_text(encoding="utf-8")
    forbidden_calls = {
        "CreateProcessW", "CreateProcessA", "ResumeThread", "AssignProcessToJobObject",
        "TerminateJobObject", "TerminateProcess", "IsProcessInJob",
        "CreateJobObjectW", "SetInformationJobObject", "QueryInformationJobObject",
        *FUNCTIONS,
    }
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            assert "_windows_verification_" not in ast.get_source_segment(source, node)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                assert node.func.attr not in forbidden_calls
            elif isinstance(node.func, ast.Name):
                assert node.func.id not in forbidden_calls


def test_cp3_public_verification_result_and_error_contracts_are_compatible() -> None:
    from tools.autonomous_pr.agents import AgentRoleError
    from tools.autonomous_pr.model import VerificationCommandResult
    from tools.autonomous_pr.repository import RepositoryError

    expected_types = {
        "command": tuple[str, ...], "returncode": int,
        "stdout": str, "stderr": str, "passed": bool,
    }
    assert tuple(field.name for field in fields(VerificationCommandResult)) == tuple(expected_types)
    assert get_type_hints(VerificationCommandResult) == expected_types
    result = VerificationCommandResult(("python", "-V"), 7, "stdout", "stderr", False)
    assert (result.command, result.returncode, result.stdout, result.stderr, result.passed) == (
        ("python", "-V"), 7, "stdout", "stderr", False,
    )
    with pytest.raises(FrozenInstanceError):
        result.passed = True  # type: ignore[misc]
    assert issubclass(RepositoryError, Exception)
    assert issubclass(AgentRoleError, Exception)
    assert issubclass(WindowsVerificationError, OSError)
    error = WindowsVerificationError(Stage.PREFLIGHT, Category.OS_API, winerror=5)
    assert error.diagnostic().winerror == 5
    assert error.stage is Stage.PREFLIGHT and error.category is Category.OS_API
    assert error.timed_out is False


def test_cp3_attribute_foundation_preserves_the_narrow_job_ownership_api() -> None:
    from tools.autonomous_pr._windows_verification_jobs import PreassignmentJobs
    from tools.autonomous_pr._windows_verification_native import CheckedJobApi, JobNativeApi

    operations = {"create_job", "configure_job", "query_job_flags", "close_handle"}
    assert {name for name in vars(JobNativeApi) if not name.startswith("_")} == operations
    assert {name for name in vars(CheckedJobApi) if not name.startswith("_")} == operations
    assert {name for name in vars(PreassignmentJobs) if not name.startswith("_")} == {
        "ownership", "release_preassignment",
    }


def test_cp3_attribute_module_has_only_private_and_standard_library_imports() -> None:
    tree = ast.parse(Path(attributes.__file__).read_text(encoding="utf-8"))
    absolute = set()
    relative = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            absolute.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                relative.add((node.level, node.module, tuple(alias.name for alias in node.names)))
            else:
                absolute.add(node.module)
    assert absolute == {
        "__future__", "ctypes", "sys", "collections.abc", "contextlib",
        "dataclasses", "enum", "threading", "typing",
    }
    assert relative == {
        (1, None, ("_windows_verification_native",)),
        (1, "_windows_verification_native", (
            "BOOL", "DWORD", "HANDLE", "SIZE_T", "WCHAR", "Category",
            "FailureDiagnostic", "NativePlatform", "Stage", "WindowsVerificationError",
        )),
    }


def test_cp3_no_process_containment_capability_probe_or_job_ownership_bridge() -> None:
    tree = ast.parse(Path(attributes.__file__).read_text(encoding="utf-8"))
    forbidden = {
        "CreateProcessW", "CreateProcessA", "ResumeThread", "TerminateProcess",
        "AssignProcessToJobObject", "TerminateJobObject", "IsProcessInJob",
        "CreateJobObjectW", "SetInformationJobObject", "QueryInformationJobObject",
        "GetProcessId", "GetThreadId", "GetHandleInformation", "SetHandleInformation",
        "DuplicateHandle", "OpenProcess", "CloseHandle", "WaitForSingleObject",
        "WaitForMultipleObjects", "CreateNamedPipeW", "CreatePipe", "ReadFile",
        "WriteFile", "CancelIoEx", "PreassignmentJobs", "release_preassignment",
        "subprocess", "importlib", "__import__", "eval", "exec",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            assert node.id not in forbidden
        elif isinstance(node, ast.Attribute):
            assert node.attr not in forbidden
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert node.value not in forbidden
    owner = next(node for node in tree.body
                 if isinstance(node, ast.ClassDef) and node.name == "PreparedLaunchAttributes")
    assert {node.name for node in owner.body
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")} == {
        "ownership", "release",
    }


@pytest.mark.parametrize("namespace,name", [
    (ctypes, "WinDLL"), (ctypes, "OleDLL"), (ctypes, "CDLL"), (ctypes, "PyDLL"),
    (ctypes, "get_last_error"), (ctypes, "_dlopen"),
    (_ctypes, "LoadLibrary"), (_ctypes, "dlopen"),
])
def test_cp3_every_native_constructor_and_error_reader_is_blocked(namespace: Any, name: str) -> None:
    assert getattr(namespace, name) is forbidden_native
    with pytest.raises(AssertionError, match="native DLL/Win32"):
        getattr(namespace, name)("kernel32.dll")


@pytest.mark.parametrize("name", ["windll", "oledll", "cdll", "pydll"])
def test_cp3_every_cached_native_library_loader_is_blocked(name: str) -> None:
    assert isinstance(getattr(ctypes, name), ForbiddenLibraries)
    with pytest.raises(AssertionError, match="native DLL/Win32"):
        getattr(ctypes, name).kernel32


def test_cp3_all_nineteen_harness_acceptance_obligations_remain_traceable() -> None:
    root = Path(__file__).resolve().parents[3]
    # Canonical obligations outlive any standalone task's metadata and closure.
    harness = (root / "docs/AUTONOMOUS_PR_HARNESS.md").read_text(encoding="utf-8")
    traceability = harness.split("### 37.12. Binding coverage and acceptance traceability\n", 1)[1]
    rows = [line.strip("| ").split("|") for line in traceability.splitlines()
            if re.match(r"^\| \d+ \|", line)]
    assert [int(row[0]) for row in rows] == list(range(1, 20))
    assert all(len(row) == 3 and all(cell.strip() for cell in row) for row in rows)
    assert "Required native facts need native proof." in traceability
    assert "Every real Windows Job/pipe/process containment test requires\nseparate explicit approval" in harness
