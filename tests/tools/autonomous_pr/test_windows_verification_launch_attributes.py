"""CP-1 / CP-2a: pure ctypes and injected fake API, including on Windows."""

from __future__ import annotations

import ast
import ctypes
import gc
import importlib.util
import sys
import _ctypes
import weakref
from dataclasses import FrozenInstanceError, fields
from itertools import combinations
from pathlib import Path
from types import SimpleNamespace
from typing import Any

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


def test_fresh_import_with_blocked_loaders_and_no_windows_symbols(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(ctypes, "WinDLL")
    monkeypatch.delattr(ctypes, "get_last_error")
    name = "tools.autonomous_pr._windows_verification_launch_attributes_import_test"
    spec = importlib.util.spec_from_file_location(name, attributes.__file__)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    module.validate_abi()
    assert not hasattr(module, "PreparedLaunchAttributes")


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
    assert not hasattr(attributes, "PreparedLaunchAttributes")
