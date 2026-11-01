"""Dormant prelaunch ownership gates: portable fakes, never native Windows APIs."""

from __future__ import annotations

import _ctypes
import ast
import ctypes
import gc
import importlib.util
import re
import weakref
from dataclasses import FrozenInstanceError, fields
from pathlib import Path
from threading import Barrier, Event, Lock, Thread
from types import SimpleNamespace
from typing import Any, Callable

import pytest


def forbidden_native(*args: object, **kwargs: object) -> Any:
    raise AssertionError("fake-only: native DLL/Win32 acquisition prohibited")


class ForbiddenLibraries:
    def __getattr__(self, name: str) -> Any:
        return forbidden_native(name)


def block_native(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("WinDLL", "OleDLL", "CDLL", "PyDLL", "get_last_error", "_dlopen"):
        monkeypatch.setattr(ctypes, name, forbidden_native, raising=False)
    for name in ("windll", "oledll", "cdll", "pydll"):
        monkeypatch.setattr(ctypes, name, ForbiddenLibraries(), raising=False)
    for name in ("LoadLibrary", "dlopen"):
        monkeypatch.setattr(_ctypes, name, forbidden_native, raising=False)


# Guard collection/import as well as test execution, including on Windows CI.
with pytest.MonkeyPatch.context() as import_guard:
    block_native(import_guard)
    from tools.autonomous_pr import _windows_verification_jobs as jobs
    from tools.autonomous_pr import _windows_verification_native as native


Phase = jobs._PrelaunchPhase
State = jobs.OwnershipState
Error = native.WindowsVerificationError
OPERATIONS = (
    jobs._reserve_prelaunch, jobs._abort_prelaunch_empty,
    jobs._fence_native_creation, jobs._prelaunch_snapshot,
)


@pytest.fixture(autouse=True)
def fake_only(monkeypatch: pytest.MonkeyPatch) -> None:
    block_native(monkeypatch)
    # Test-owned registry only. No product finalizer/automatic cleanup is added.
    monkeypatch.setattr(jobs, "_OWNER_PINS", weakref.WeakKeyDictionary())


class Interrupted(BaseException):
    winerror = 411


class FakeDLL:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int | None]] = []
        self.closes: list[int] = []
        self.created = 0
        self.closed: set[int] = set()
        self.outcomes: dict[int, object] = {}
        self.callback: Callable[[], None] | None = None
        self.owner_ref: Callable[[], Any] = lambda: None
        self.error = 0
        self.dll = SimpleNamespace(
            CreateJobObjectW=self.function("create"),
            SetInformationJobObject=self.function("configure"),
            QueryInformationJobObject=self.function("query"),
            CloseHandle=self.function("close"),
        )

    def function(self, name: str) -> Callable[..., object]:
        def call(*args: Any) -> object:
            owner = self.owner_ref()
            if owner is not None:
                assert not owner._state_lock.held, "native API called under the state mutex"
            if name == "create":
                assert args == (None, None)
                self.created += 1
                self.calls.append((name, None))
                return self.created * 0x1100
            handle = args[0]
            self.calls.append((name, handle))
            assert handle in (0x1100, 0x2200) and handle not in self.closed
            if name == "query":
                ctypes.cast(args[2], ctypes.POINTER(native.JOBOBJECT_EXTENDED_LIMIT_INFORMATION)
                            ).contents.BasicLimitInformation.LimitFlags = native.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                ctypes.cast(args[4], ctypes.POINTER(native.DWORD)).contents.value = 144
            if name == "close":
                self.closes.append(handle)
                self.error = 700 + len(self.closes)
                if self.callback is not None:
                    self.callback()
                outcome = self.outcomes.get(len(self.closes), 1)
                if isinstance(outcome, BaseException):
                    raise outcome
                if type(outcome) is int and outcome != 0 and -(1 << 31) <= outcome < (1 << 31):
                    self.closed.add(handle)
                return outcome
            return 1
        return call


class TrackingLock:
    """Deterministic lock/claim/exit faults; only the fake may rescue its mutex."""

    def __init__(self) -> None:
        self.lock = Lock()
        self.held = False
        self.entries = 0
        self.exits = 0
        self.fail_at = 0
        self.mode = ""
        self.error: BaseException = Interrupted("SECRET lock exception")
        self.on_exit: Callable[[], None] | None = None

    def __enter__(self) -> None:
        self.entries += 1
        if self.entries == self.fail_at and self.mode == "enter_before":
            raise self.error
        assert self.lock.acquire(timeout=5), "attempt to reacquire a poisoned mutex"
        self.held = True
        if self.entries == self.fail_at and self.mode == "enter_after":
            raise self.error

    def __exit__(self, *args: Any) -> None:
        self.exits += 1
        if self.on_exit is not None:
            callback, self.on_exit = self.on_exit, None
            callback()
        if self.entries == self.fail_at and self.mode == "exit_before":
            raise self.error
        self.held = False
        self.lock.release()
        if self.entries == self.fail_at and self.mode == "exit_after":
            raise self.error

    def rescue_test_mutex(self) -> None:
        if self.held:
            self.held = False
            self.lock.release()


def make_pair() -> tuple[jobs.PreassignmentJobs, FakeDLL]:
    dll = FakeDLL()
    pair = jobs.PreassignmentJobs(native.CheckedJobApi(dll.dll, lambda: dll.error))
    pair._state_lock = TrackingLock()
    dll.owner_ref = weakref.ref(pair)
    return pair, dll


def phase(pair: jobs.PreassignmentJobs) -> Phase:
    return jobs._prelaunch_snapshot(pair).phase


def pinned(pair: jobs.PreassignmentJobs) -> bool:
    return any(slot.owner is pair for slot in jobs._OWNER_PINS.values())


def assert_rejected(operation: Callable[[], Any]) -> Error:
    with pytest.raises(Error) as caught:
        operation()
    assert caught.value.category is native.Category.OWNERSHIP
    assert "SECRET" not in str(caught.value) + repr(caught.value.__dict__)
    return caught.value


def assert_no_empty_authority(pair: jobs.PreassignmentJobs, dll: FakeDLL) -> None:
    before = list(dll.calls)
    for operation in (pair.release_preassignment, lambda: jobs._abort_prelaunch_empty(pair),
                      lambda: jobs._reserve_prelaunch(pair), lambda: jobs._fence_native_creation(pair)):
        assert_rejected(operation)
    assert dll.calls == before


def test_reservation_fence_and_audit_have_no_native_effect_or_handle_output() -> None:
    pair, dll = make_pair()
    before = list(dll.calls)
    initial = jobs._prelaunch_snapshot(pair)
    assert initial.phase is Phase.EMPTY_READY and not initial.uncertain and not pinned(pair)
    assert jobs._reserve_prelaunch(pair) is None
    reserved = jobs._prelaunch_snapshot(pair)
    assert reserved.phase is Phase.RESERVED_EMPTY and pinned(pair)
    assert reserved.roles == (jobs.JobLabel.SUPERVISION, jobs.JobLabel.COMMAND)
    assert_rejected(pair.release_preassignment)
    assert_rejected(lambda: jobs._reserve_prelaunch(pair))
    assert jobs._fence_native_creation(pair) is None
    assert phase(pair) is Phase.NATIVE_CREATION_FENCED and pinned(pair)
    assert all(job.state is State.OWNED_PREASSIGNMENT for job in pair.ownership)
    assert_no_empty_authority(pair, dll)
    assert dll.calls == before
    assert phase(pair) is Phase.NATIVE_CREATION_FENCED
    assert tuple(field.name for field in fields(reserved)) == ("phase", "roles", "uncertain")
    with pytest.raises(FrozenInstanceError):
        reserved.phase = Phase.EMPTY_READY  # type: ignore[misc]
    assert initial.phase is Phase.EMPTY_READY  # An old snapshot grants nothing.
    assert "0x" not in repr(pair) + repr(reserved) + repr(pair.ownership) + repr(pair._pin)


@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize("invalid", [None, object(), 123, True, SimpleNamespace(), jobs.PreassignmentJobs.__new__(jobs.PreassignmentJobs)])
def test_foreign_and_partial_owners_are_rejected_without_any_api(operation: Callable[..., Any], invalid: Any) -> None:
    assert_rejected(lambda: operation(invalid))


@pytest.mark.parametrize("operation", OPERATIONS)
def test_exact_type_and_complete_initialization_are_required(operation: Callable[..., Any]) -> None:
    class Foreign(jobs.PreassignmentJobs):
        pass
    assert_rejected(lambda: operation(Foreign.__new__(Foreign)))
    partial = jobs.PreassignmentJobs.__new__(jobs.PreassignmentJobs)
    partial._initialized = jobs._INITIALIZED
    assert_rejected(lambda: operation(partial))


@pytest.mark.parametrize("reserved", [False, True])
def test_empty_release_remains_checked_reverse_order_and_one_shot(reserved: bool) -> None:
    pair, dll = make_pair()
    if reserved:
        jobs._reserve_prelaunch(pair)
        assert jobs._abort_prelaunch_empty(pair) is None
    else:
        assert_rejected(lambda: jobs._abort_prelaunch_empty(pair))
        assert_rejected(lambda: jobs._fence_native_creation(pair))
        pair.release_preassignment()
    assert dll.closes == [0x2200, 0x1100]
    assert phase(pair) is Phase.EMPTY_CLOSED and not pinned(pair)
    assert all(job.state is State.CONFIRMED_CLOSED for job in pair.ownership)
    assert_no_empty_authority(pair, dll)


@pytest.mark.parametrize("faults", [(1,), (2,), (1, 2)])
@pytest.mark.parametrize("outcome", [0, None, True, 1 << 32, OSError(5, "SECRET close"),
                                    MemoryError("SECRET allocation"), KeyboardInterrupt("SECRET interrupt"),
                                    Interrupted("SECRET wrapper")])
def test_checked_abort_faults_preserve_primary_remaining_attempt_and_pin(faults: tuple[int, ...], outcome: object) -> None:
    pair, dll = make_pair()
    jobs._reserve_prelaunch(pair)
    dll.outcomes.update({ordinal: outcome for ordinal in faults})
    with pytest.raises(Error) as caught:
        jobs._abort_prelaunch_empty(pair)
    failure = caught.value
    assert dll.closes == [0x2200, 0x1100]
    assert phase(pair) is Phase.EMPTY_UNCERTAIN and pinned(pair)
    assert not failure.cleanup_confirmed and len(failure.cleanup_failures) == len(faults) - 1
    if outcome == 0 and type(outcome) is int:
        assert failure.winerror == 700 + faults[0]
        assert [item.winerror for item in failure.cleanup_failures] == [700 + n for n in faults[1:]]
    expected = {
        jobs.JobLabel.COMMAND: State.UNCERTAIN_CLOSE if 1 in faults else State.CONFIRMED_CLOSED,
        jobs.JobLabel.SUPERVISION: State.UNCERTAIN_CLOSE if 2 in faults else State.CONFIRMED_CLOSED,
    }
    assert {job.label: job.state for job in pair.ownership} == expected
    assert set(failure.unresolved_jobs) == {label.value for label, state in expected.items() if state is State.UNCERTAIN_CLOSE}
    assert "SECRET" not in str(failure) + repr(failure.__dict__)
    assert_no_empty_authority(pair, dll)


@pytest.mark.parametrize("outcome", [0, False, True, object()])
def test_malformed_checked_close_wrapper_return_is_not_confirmed(outcome: object, monkeypatch: pytest.MonkeyPatch) -> None:
    pair, dll = make_pair()
    jobs._reserve_prelaunch(pair)
    monkeypatch.setattr(pair._api, "close_handle", lambda handle: outcome)
    with pytest.raises(Error):
        jobs._abort_prelaunch_empty(pair)
    assert phase(pair) is Phase.EMPTY_UNCERTAIN and pinned(pair)
    assert all(job.state is State.UNCERTAIN_CLOSE for job in pair.ownership)
    assert not dll.closes


@pytest.mark.parametrize("reserved", [False, True])
def test_private_retirement_helper_cannot_bypass_the_phase_claim(reserved: bool) -> None:
    pair, dll = make_pair()
    if reserved:
        jobs._reserve_prelaunch(pair)
        jobs._fence_native_creation(pair)
    assert_rejected(pair._retire)
    assert not dll.closes and pinned(pair)
    assert_no_empty_authority(pair, dll)
    if reserved:
        assert phase(pair) is Phase.NATIVE_CREATION_FENCED


@pytest.mark.parametrize("point", ["before", "after"])
@pytest.mark.parametrize("error", [MemoryError("SECRET"), KeyboardInterrupt("SECRET"), Interrupted("SECRET")])
def test_failed_registration_never_claims_or_disables_old_release(point: str, error: BaseException, monkeypatch: pytest.MonkeyPatch) -> None:
    pair, dll = make_pair()
    register = jobs._register_owner
    def fail(owner: jobs.PreassignmentJobs) -> None:
        if point == "after":
            register(owner)
        raise error
    monkeypatch.setattr(jobs, "_register_owner", fail)
    with pytest.raises(Error):
        jobs._reserve_prelaunch(pair)
    assert phase(pair) is Phase.EMPTY_READY and not pinned(pair) and not dll.closes
    # Even an ongoing registry helper failure cannot disable original release.
    pair.release_preassignment()
    assert dll.closes == [0x2200, 0x1100] and phase(pair) is Phase.EMPTY_CLOSED


@pytest.mark.parametrize("mode", ["enter_before", "enter_after", "exit_before", "exit_after"])
@pytest.mark.parametrize("operation", ["reserve", "release", "fence", "abort", "snapshot", "ownership"])
def test_unknown_lock_outcomes_pin_and_never_reacquire(mode: str, operation: str) -> None:
    pair, dll = make_pair()
    if operation in ("fence", "abort"):
        jobs._reserve_prelaunch(pair)
    lock = pair._state_lock
    lock.fail_at, lock.mode = lock.entries + 1, mode
    action = {
        "reserve": lambda: jobs._reserve_prelaunch(pair), "release": pair.release_preassignment,
        "fence": lambda: jobs._fence_native_creation(pair), "abort": lambda: jobs._abort_prelaunch_empty(pair),
        "snapshot": lambda: jobs._prelaunch_snapshot(pair), "ownership": lambda: pair.ownership,
    }[operation]
    try:
        with pytest.raises(Error) as caught:
            action()
        assert caught.value.winerror == 411 and pinned(pair)
        entries = lock.entries
        assert_no_empty_authority(pair, dll)
        snapshot = jobs._prelaunch_snapshot(pair)
        assert snapshot.uncertain
        fenced = operation == "fence" and mode.startswith("exit")
        assert snapshot.phase is (Phase.NATIVE_CREATION_FENCED if fenced else Phase.EMPTY_UNCERTAIN)
        assert lock.entries == entries and not dll.closes
    finally:
        lock.rescue_test_mutex()


@pytest.mark.parametrize("index", range(1, 7))
@pytest.mark.parametrize("mode", ["enter_before", "enter_after", "exit_before", "exit_after"])
@pytest.mark.parametrize("error", [MemoryError("SECRET"), KeyboardInterrupt("SECRET"), Interrupted("SECRET")])
def test_abort_claim_close_and_bookkeeping_lock_failures_never_retry(index: int, mode: str, error: BaseException) -> None:
    pair, dll = make_pair()
    jobs._reserve_prelaunch(pair)
    lock = pair._state_lock
    lock.fail_at, lock.mode, lock.error = lock.entries + index, mode, error
    try:
        with pytest.raises(Error):
            jobs._abort_prelaunch_empty(pair)
        assert pinned(pair) and jobs._prelaunch_snapshot(pair).uncertain
        entries, closes = lock.entries, list(dll.closes)
        assert len(closes) <= 2 and len(set(closes)) == len(closes)
        assert_no_empty_authority(pair, dll)
        assert lock.entries == entries and dll.closes == closes
    finally:
        lock.rescue_test_mutex()


@pytest.mark.parametrize("index", [1, 2])
def test_native_cause_survives_a_later_bookkeeping_lock_failure(index: int) -> None:
    pair, dll = make_pair()
    jobs._reserve_prelaunch(pair)
    dll.outcomes[1] = 0
    lock = pair._state_lock
    # Fail committing the failed first close or claiming the second handle.
    lock.fail_at, lock.mode = lock.entries + index + 2, "enter_after"
    try:
        with pytest.raises(Error) as caught:
            jobs._abort_prelaunch_empty(pair)
        assert caught.value.winerror == 701
        assert caught.value.cleanup_failures[0].winerror == 411
        assert dll.closes == [0x2200] and pinned(pair)
        assert_no_empty_authority(pair, dll)
    finally:
        lock.rescue_test_mutex()


@pytest.mark.parametrize("point", ["retire", "unpin_before", "unpin_after"])
@pytest.mark.parametrize("error", [MemoryError("SECRET"), KeyboardInterrupt("SECRET"), Interrupted("SECRET")])
def test_postclaim_and_registry_retirement_failures_keep_owner(point: str, error: BaseException, monkeypatch: pytest.MonkeyPatch) -> None:
    pair, dll = make_pair()
    jobs._reserve_prelaunch(pair)
    discard = jobs._discard_pin
    def fail(*args: Any) -> Any:
        if point == "unpin_after":
            discard(*args)
        raise error
    monkeypatch.setattr(pair if point == "retire" else jobs,
                        "_retire" if point == "retire" else "_discard_pin", fail)
    with pytest.raises(Error):
        jobs._abort_prelaunch_empty(pair)
    assert pinned(pair) and phase(pair) is Phase.EMPTY_UNCERTAIN
    assert dll.closes == ([] if point == "retire" else [0x2200, 0x1100])
    assert_no_empty_authority(pair, dll)


def test_diagnostic_failures_are_bounded_and_do_not_hide_remaining_close(monkeypatch: pytest.MonkeyPatch) -> None:
    pair, dll = make_pair()
    jobs._reserve_prelaunch(pair)
    dll.outcomes[1] = dll.outcomes[2] = Interrupted("SECRET native exception")
    def fail(*args: Any, **kwargs: Any) -> Any:
        raise MemoryError("SECRET diagnostic construction")
    monkeypatch.setattr(jobs, "sanitized_error", fail)
    monkeypatch.setattr(Error, "diagnostic", fail)
    with pytest.raises(Error) as caught:
        jobs._abort_prelaunch_empty(pair)
    assert caught.value.winerror is None
    assert caught.value.cleanup_failures == (jobs._UNKNOWN_CLEANUP,)
    assert dll.closes == [0x2200, 0x1100] and pinned(pair)
    assert "SECRET" not in str(caught.value) + repr(caught.value.__dict__)


@pytest.mark.parametrize("reserved", [False, True])
def test_interruption_after_cleanup_claim_keeps_the_original_owner(reserved: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    pair, dll = make_pair()
    if reserved:
        jobs._reserve_prelaunch(pair)
    def fail(owner: jobs.PreassignmentJobs) -> None:
        raise KeyboardInterrupt("SECRET before retirement dispatch")
    monkeypatch.setattr(jobs, "_finish_empty_retirement", fail)
    with pytest.raises(KeyboardInterrupt):
        jobs._abort_prelaunch_empty(pair) if reserved else pair.release_preassignment()
    assert pinned(pair) and phase(pair) is Phase.EMPTY_CLOSE_CLAIMED and not dll.closes
    assert_no_empty_authority(pair, dll)
    reference = weakref.ref(pair)
    del pair
    gc.collect()
    assert reference() is not None


@pytest.mark.parametrize("operation", ["reserve", "release"])
def test_registration_callback_can_reenter_without_deadlock_or_restoring_authority(operation: str, monkeypatch: pytest.MonkeyPatch) -> None:
    pair, dll = make_pair()
    register = jobs._register_owner
    entered = False
    def reenter(owner: jobs.PreassignmentJobs) -> None:
        nonlocal entered
        register(owner)
        if not entered:
            entered = True
            jobs._reserve_prelaunch(owner) if operation == "reserve" else owner.release_preassignment()
    monkeypatch.setattr(jobs, "_register_owner", reenter)
    assert_rejected(lambda: jobs._reserve_prelaunch(pair))
    assert phase(pair) is (Phase.RESERVED_EMPTY if operation == "reserve" else Phase.EMPTY_CLOSED)
    assert pinned(pair) is (operation == "reserve")
    assert dll.closes == ([] if operation == "reserve" else [0x2200, 0x1100])


def test_snapshot_allocation_failure_quarantines_without_reentering_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    pair, dll = make_pair()
    snapshot = jobs._PrelaunchSnapshot
    def fail(*args: Any, **kwargs: Any) -> Any:
        raise MemoryError("SECRET audit allocation")
    monkeypatch.setattr(jobs, "_PrelaunchSnapshot", fail)
    with pytest.raises(Error):
        jobs._prelaunch_snapshot(pair)
    entries = pair._state_lock.entries
    monkeypatch.setattr(jobs, "_PrelaunchSnapshot", snapshot)
    assert jobs._prelaunch_snapshot(pair).uncertain and pinned(pair)
    assert_no_empty_authority(pair, dll)
    assert pair._state_lock.entries == entries and not dll.closes


def test_competing_lock_failure_cannot_be_erased_by_an_inflight_unpin(monkeypatch: pytest.MonkeyPatch) -> None:
    pair, dll = make_pair()
    jobs._reserve_prelaunch(pair)
    paused, resume = Event(), Event()
    discard = jobs._discard_pin
    def paused_unpin(owner: jobs.PreassignmentJobs) -> None:
        paused.set()
        assert resume.wait(5)
        discard(owner)
    monkeypatch.setattr(jobs, "_discard_pin", paused_unpin)
    results: list[Any] = []
    original_lock = pair._state_lock
    thread = run_thread(lambda: jobs._abort_prelaunch_empty(pair), results)
    try:
        assert paused.wait(5)
        broken = TrackingLock()
        broken.fail_at, broken.mode = 1, "enter_before"
        pair._state_lock = broken
        with pytest.raises(Error):
            jobs._prelaunch_snapshot(pair)
        assert pinned(pair)
    finally:
        resume.set()
        thread.join(5)
    assert not thread.is_alive() and len(results) == 1 and isinstance(results[0], Error)
    assert not original_lock.held and broken.entries == 1
    assert pinned(pair) and jobs._prelaunch_snapshot(pair).uncertain
    assert pair._pin._owner is None and pair._pin.quarantined_owner is pair
    assert dll.closes == [0x2200, 0x1100]
    assert_no_empty_authority(pair, dll)
    # A weak registry key must still survive after both the caller and the
    # racing error/tracebacks disappear; the quarantine value is the custody.
    reference = weakref.ref(pair)
    results.clear()
    del pair
    gc.collect()
    assert reference() is not None and pinned(reference())


@pytest.mark.parametrize("reserved", [False, True])
def test_emergency_reference_is_itself_the_irreversible_uncertainty_latch(reserved: bool) -> None:
    pair, dll = make_pair()
    if reserved:
        jobs._reserve_prelaunch(pair)
    # Simulate interruption immediately after the emergency reference store.
    # No separate Boolean/bookkeeping assignment is required to revoke authority.
    pair._pin.quarantined_owner = pair
    entries = pair._state_lock.entries
    assert_no_empty_authority(pair, dll)
    assert jobs._prelaunch_snapshot(pair).uncertain and pinned(pair)
    assert pair._state_lock.entries == entries and not dll.closes


@pytest.mark.parametrize("operation", [jobs._abort_prelaunch_empty, jobs._fence_native_creation])
def test_concurrent_duplicate_reserved_claim_has_one_winner(operation: Callable[..., Any], monkeypatch: pytest.MonkeyPatch) -> None:
    pair, dll = make_pair()
    jobs._reserve_prelaunch(pair)
    paused, resume = Event(), Event()
    original = jobs._state_guard
    from contextlib import contextmanager
    first = True
    @contextmanager
    def guard(owner: jobs.PreassignmentJobs) -> Any:
        nonlocal first
        with original(owner):
            yield
        if first:
            first = False
            paused.set()
            assert resume.wait(5)
    monkeypatch.setattr(jobs, "_state_guard", guard)
    results: list[Any] = []
    thread = run_thread(lambda: operation(pair), results)
    try:
        assert paused.wait(5)
        assert_rejected(lambda: operation(pair))
        assert not dll.closes
    finally:
        resume.set()
        thread.join(5)
    assert not thread.is_alive() and results == [None]
    assert dll.closes == ([0x2200, 0x1100] if operation is jobs._abort_prelaunch_empty else [])


def test_reentrant_operations_and_audits_cannot_take_another_claim() -> None:
    pair, dll = make_pair()
    jobs._reserve_prelaunch(pair)
    observations = []
    def reenter() -> None:
        observations.append(jobs._prelaunch_snapshot(pair))
        assert any(item.state is State.CLOSE_ATTEMPTED for item in pair.ownership)
        assert_no_empty_authority(pair, dll)
    dll.callback = reenter
    jobs._abort_prelaunch_empty(pair)
    assert dll.closes == [0x2200, 0x1100]
    assert len(observations) == 2 and all(item.phase is Phase.EMPTY_CLOSE_CLAIMED for item in observations)
    assert phase(pair) is Phase.EMPTY_CLOSED and not pinned(pair)


def run_thread(action: Callable[[], Any], outcomes: list[Any]) -> Thread:
    def run() -> None:
        try:
            outcomes.append(action())
        except BaseException as error:
            outcomes.append(error)
    thread = Thread(target=run, daemon=True)
    thread.start()
    return thread


@pytest.mark.parametrize("winner", ["reserve", "release", "abort", "fence"])
def test_both_linearized_race_outcomes_without_sleeps(winner: str, monkeypatch: pytest.MonkeyPatch) -> None:
    pair, dll = make_pair()
    if winner in ("abort", "fence"):
        jobs._reserve_prelaunch(pair)
    paused, resume = Event(), Event()
    original_guard = jobs._state_guard
    first = True
    def pause_after_claim(owner: jobs.PreassignmentJobs) -> Any:
        # Wrap the real guard, after its successful mutex exit, before the winner
        # returns or starts native retirement. The other operation runs fully.
        from contextlib import contextmanager
        @contextmanager
        def guard() -> Any:
            nonlocal first
            with original_guard(owner):
                yield
            if first:
                first = False
                paused.set()
                assert resume.wait(5)
        return guard()
    monkeypatch.setattr(jobs, "_state_guard", pause_after_claim)
    actions = {
        "reserve": lambda: jobs._reserve_prelaunch(pair), "release": pair.release_preassignment,
        "abort": lambda: jobs._abort_prelaunch_empty(pair), "fence": lambda: jobs._fence_native_creation(pair),
    }
    loser = {"reserve": "release", "release": "reserve", "abort": "fence", "fence": "abort"}[winner]
    results: list[Any] = []
    thread = run_thread(actions[winner], results)
    try:
        assert paused.wait(5)
        assert_rejected(actions[loser])
        assert not dll.closes
    finally:
        resume.set()
        thread.join(5)
    assert not thread.is_alive() and results == [None]
    assert dll.closes == ([0x2200, 0x1100] if winner in ("release", "abort") else [])
    assert phase(pair) is {
        "reserve": Phase.RESERVED_EMPTY, "release": Phase.EMPTY_CLOSED,
        "abort": Phase.EMPTY_CLOSED, "fence": Phase.NATIVE_CREATION_FENCED,
    }[winner]


def test_concurrent_duplicate_reserve_has_one_claim_one_identity_pin(monkeypatch: pytest.MonkeyPatch) -> None:
    pair, dll = make_pair()
    register = jobs._register_owner
    registered = Barrier(3)
    def synchronized(owner: jobs.PreassignmentJobs) -> None:
        register(owner)
        registered.wait(5)
    monkeypatch.setattr(jobs, "_register_owner", synchronized)
    results: list[Any] = []
    threads = [run_thread(lambda: jobs._reserve_prelaunch(pair), results) for _ in range(2)]
    registered.wait(5)
    for thread in threads:
        thread.join(5)
        assert not thread.is_alive()
    assert results.count(None) == 1
    assert sum(isinstance(result, Error) for result in results) == 1
    assert sum(slot.owner is pair for slot in jobs._OWNER_PINS.values()) == 1
    assert phase(pair) is Phase.RESERVED_EMPTY and not dll.closes
    jobs._abort_prelaunch_empty(pair)


def test_reservation_can_return_after_abort_but_never_authorizes_fence(monkeypatch: pytest.MonkeyPatch) -> None:
    pair, dll = make_pair()
    paused, resume = Event(), Event()
    original = jobs._state_guard
    from contextlib import contextmanager
    @contextmanager
    def guard(owner: jobs.PreassignmentJobs) -> Any:
        with original(owner):
            yield
        if owner._phase is Phase.RESERVED_EMPTY and not paused.is_set():
            paused.set()
            assert resume.wait(5)
    monkeypatch.setattr(jobs, "_state_guard", guard)
    results: list[Any] = []
    thread = run_thread(lambda: jobs._reserve_prelaunch(pair), results)
    try:
        assert paused.wait(5)
        jobs._abort_prelaunch_empty(pair)
    finally:
        resume.set()
        thread.join(5)
    assert not thread.is_alive() and results == [None]
    assert_rejected(lambda: jobs._fence_native_creation(pair))
    assert phase(pair) is Phase.EMPTY_CLOSED and not pinned(pair)
    assert dll.closes == [0x2200, 0x1100]


@pytest.mark.parametrize("terminal", ["reserve", "fence", "uncertain", "closed"])
def test_registry_reachability_outlives_caller_reference(terminal: str) -> None:
    pair, dll = make_pair()
    jobs._reserve_prelaunch(pair)
    if terminal == "fence":
        jobs._fence_native_creation(pair)
        try:
            raise Interrupted("SECRET simulated future wrapper failure")
        except Interrupted:
            pass
    elif terminal in ("uncertain", "closed"):
        if terminal == "uncertain":
            dll.outcomes[1] = 0
        try:
            jobs._abort_prelaunch_empty(pair)
        except Error:
            pass
    reference = weakref.ref(pair)
    del pair
    gc.collect()
    if terminal == "closed":
        assert reference() is None
    else:
        assert reference() is not None and pinned(reference())
        assert_no_empty_authority(reference(), dll) if terminal != "reserve" else None


def test_registration_allocation_precedes_all_native_acquisition(monkeypatch: pytest.MonkeyPatch) -> None:
    dll = FakeDLL()
    class BrokenRegistry(weakref.WeakKeyDictionary):
        def __setitem__(self, key: object, value: object) -> None:
            raise MemoryError("SECRET registry allocation")
    monkeypatch.setattr(jobs, "_OWNER_PINS", BrokenRegistry())
    with pytest.raises(Error) as caught:
        jobs.PreassignmentJobs(native.CheckedJobApi(dll.dll, lambda: 0))
    assert not dll.calls and caught.value.cleanup_confirmed
    assert caught.value.category is native.Category.RESOURCE
    assert "SECRET" not in str(caught.value)


@pytest.mark.parametrize("prior", [Phase.EMPTY_READY, Phase.RESERVED_EMPTY, Phase.NATIVE_CREATION_FENCED])
def test_registry_read_failures_are_redacted_and_cannot_consume_or_restore_authority(prior: Phase, monkeypatch: pytest.MonkeyPatch) -> None:
    pair, dll = make_pair()
    if prior is not Phase.EMPTY_READY:
        jobs._reserve_prelaunch(pair)
    if prior is Phase.NATIVE_CREATION_FENCED:
        jobs._fence_native_creation(pair)
    class BrokenRegistry(weakref.WeakKeyDictionary):
        def get(self, key: object, default: object = None) -> Any:
            raise Interrupted("SECRET registry read")
    original = jobs._OWNER_PINS
    monkeypatch.setattr(jobs, "_OWNER_PINS", BrokenRegistry(original))
    for operation in OPERATIONS:
        with pytest.raises(Error) as caught:
            operation(pair)
        assert caught.value.winerror == 411 and "SECRET" not in str(caught.value)
    assert pair._phase is prior and not dll.closes
    monkeypatch.setattr(jobs, "_OWNER_PINS", original)
    assert pinned(pair) is (prior is not Phase.EMPTY_READY)
    if prior is Phase.EMPTY_READY:
        pair.release_preassignment()
        assert dll.closes == [0x2200, 0x1100]
    else:
        assert_rejected(pair.release_preassignment)


@pytest.mark.parametrize("owned", [1, 2])
@pytest.mark.parametrize("uncertain", [False, True])
def test_failed_constructor_retains_only_unresolved_owner_after_exception_collection(
    owned: int, uncertain: bool, monkeypatch: pytest.MonkeyPatch,
) -> None:
    dll = FakeDLL()
    checked = native.CheckedJobApi(dll.dll, lambda: dll.error)
    initialize = jobs.PreassignmentJobs.__init__
    configure = checked.configure_job
    references = []
    def observe(owner: jobs.PreassignmentJobs, api: Any) -> None:
        references.append(weakref.ref(owner))
        dll.owner_ref = references[-1]
        initialize(owner, api)
    def fail_setup(handle: int) -> None:
        if handle == owned * 0x1100:
            raise Error(native.Stage.JOBS, native.Category.OS_API, winerror=87)
        configure(handle)
    monkeypatch.setattr(jobs.PreassignmentJobs, "__init__", observe)
    monkeypatch.setattr(jobs, "Lock", TrackingLock)
    monkeypatch.setattr(checked, "configure_job", fail_setup)
    if uncertain:
        dll.outcomes[1] = 0
    def construct_and_drop_error() -> None:
        try:
            jobs.PreassignmentJobs(checked)
        except Error as error:
            assert error.stage is native.Stage.JOBS and error.winerror == 87
            assert error.cleanup_confirmed is not uncertain
            assert len(error.cleanup_failures) == int(uncertain)
        else:
            pytest.fail("setup unexpectedly succeeded")
    construct_and_drop_error()
    gc.collect()
    owner = references[0]()
    assert (owner is not None) is uncertain
    if uncertain:
        assert pinned(owner)
        assert any(item.state is State.UNCERTAIN_CLOSE for item in owner.ownership)
        assert_no_empty_authority(owner, dll)
    assert len(jobs._OWNER_PINS) == int(uncertain)
    assert dll.closes == ([0x2200, 0x1100] if owned == 2 else [0x1100])


@pytest.mark.parametrize("point", ["retire", "record", "unpin_before", "unpin_after"])
@pytest.mark.parametrize("fault_type", [MemoryError, KeyboardInterrupt, Interrupted])
def test_constructor_rollback_internal_failures_preserve_primary_and_reachable_owner(
    point: str, fault_type: type[BaseException], monkeypatch: pytest.MonkeyPatch,
) -> None:
    dll = FakeDLL()
    checked = native.CheckedJobApi(dll.dll, lambda: dll.error)
    initialize = jobs.PreassignmentJobs.__init__
    discard = jobs._discard_pin
    references, failures = [], []
    def observe(owner: jobs.PreassignmentJobs, api: Any) -> None:
        references.append(weakref.ref(owner))
        dll.owner_ref = references[-1]
        initialize(owner, api)
    def fail_setup(handle: int) -> None:
        raise Error(native.Stage.JOBS, native.Category.OS_API, winerror=87)
    def fail_rollback(owner: jobs.PreassignmentJobs, *args: Any) -> Any:
        failures.append(point)
        if point == "unpin_after":
            discard(owner)
        raise fault_type("SECRET rollback bookkeeping")
    monkeypatch.setattr(jobs.PreassignmentJobs, "__init__", observe)
    monkeypatch.setattr(jobs, "Lock", TrackingLock)
    monkeypatch.setattr(checked, "configure_job", fail_setup)
    if point == "retire":
        monkeypatch.setattr(jobs.PreassignmentJobs, "_retire", fail_rollback)
    elif point == "record":
        monkeypatch.setattr(jobs.PreassignmentJobs, "_record_cleanup", fail_rollback)
    else:
        monkeypatch.setattr(jobs, "_discard_pin", fail_rollback)
    def construct_and_drop_error() -> None:
        try:
            jobs.PreassignmentJobs(checked)
        except Error as error:
            assert error.stage is native.Stage.JOBS and error.winerror == 87
            assert not error.cleanup_confirmed and len(error.cleanup_failures) == 1
            assert error.unresolved_jobs == (("J_supervision",) if point == "retire" else ())
            assert "SECRET" not in str(error) + repr(error.__dict__)
        else:
            pytest.fail("setup unexpectedly succeeded")
    construct_and_drop_error()
    gc.collect()
    owner = references[0]()
    assert owner is not None and pinned(owner) and owner._pin.quarantined_owner is owner
    assert len(jobs._OWNER_PINS) == 1 and failures == [point]
    assert dll.closes == ([] if point == "retire" else [0x1100])
    entries = owner._state_lock.entries
    assert_rejected(owner.release_preassignment)
    assert owner._state_lock.entries == entries


@pytest.mark.parametrize("mode", ["enter_before", "enter_after", "exit_before", "exit_after"])
def test_constructor_rollback_lock_uncertainty_preserves_cause_without_reacquiring(
    mode: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    dll = FakeDLL()
    checked = native.CheckedJobApi(dll.dll, lambda: dll.error)
    initialize = jobs.PreassignmentJobs.__init__
    references = []
    def observe(owner: jobs.PreassignmentJobs, api: Any) -> None:
        references.append(weakref.ref(owner))
        dll.owner_ref = references[-1]
        initialize(owner, api)
    def fail_setup(handle: int) -> None:
        lock = references[0]()._state_lock
        lock.fail_at, lock.mode = 1, mode
        raise Error(native.Stage.JOBS, native.Category.OS_API, winerror=87)
    monkeypatch.setattr(jobs.PreassignmentJobs, "__init__", observe)
    monkeypatch.setattr(jobs, "Lock", TrackingLock)
    monkeypatch.setattr(checked, "configure_job", fail_setup)
    def construct_and_drop_error() -> None:
        try:
            jobs.PreassignmentJobs(checked)
        except Error as error:
            assert error.stage is native.Stage.JOBS and error.winerror == 87
            assert not error.cleanup_confirmed and error.unresolved_jobs == ("J_supervision",)
            assert len(error.cleanup_failures) == 1 and error.cleanup_failures[0].winerror == 411
        else:
            pytest.fail("setup unexpectedly succeeded")
    construct_and_drop_error()
    gc.collect()
    owner = references[0]()
    assert owner is not None and pinned(owner) and owner._pin.quarantined_owner is owner
    try:
        assert not dll.closes and owner._state_lock.entries == 1
        assert_rejected(owner.release_preassignment)
        assert owner._state_lock.entries == 1
    finally:
        owner._state_lock.rescue_test_mutex()


@pytest.mark.parametrize("reserved", [False, True])
def test_completed_owner_cycles_do_not_accumulate_empty_registry_slots(reserved: bool) -> None:
    baseline = len(jobs._OWNER_PINS)
    references = []
    for _ in range(32):
        pair, dll = make_pair()
        references.append(weakref.ref(pair))
        if reserved:
            jobs._reserve_prelaunch(pair)
            jobs._abort_prelaunch_empty(pair)
        else:
            pair.release_preassignment()
        assert not pinned(pair) and dll.closes == [0x2200, 0x1100]
        del pair, dll
    gc.collect()
    assert all(reference() is None for reference in references)
    assert len(jobs._OWNER_PINS) == baseline


def test_import_and_all_native_acquisition_entrypoints_are_guarded() -> None:
    spec = importlib.util.spec_from_file_location(jobs.__name__, jobs.__file__)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for namespace, names in ((ctypes, ("WinDLL", "OleDLL", "CDLL", "PyDLL", "get_last_error", "_dlopen")),
                             (_ctypes, ("LoadLibrary", "dlopen"))):
        for name in names:
            with pytest.raises(AssertionError, match="native DLL/Win32"):
                getattr(namespace, name)("kernel32.dll")
    for name in ("windll", "oledll", "cdll", "pydll"):
        with pytest.raises(AssertionError, match="native DLL/Win32"):
            getattr(ctypes, name).kernel32


def test_narrow_public_api_and_no_launch_assignment_or_production_wiring() -> None:
    assert {name for name in vars(jobs.PreassignmentJobs) if not name.startswith("_")} == {
        "ownership", "release_preassignment",
    }
    source = Path(jobs.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = {
        "CreateProcessW", "ResumeThread", "AssignProcessToJobObject", "TerminateJobObject",
        "DuplicateHandle", "IsProcessInJob", "TerminateProcess", "load_native_api", "subprocess",
        "PreparedLaunchAttributes", "_resource_pointer", "__del__", "mark_assigned",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            assert node.id not in forbidden
        elif isinstance(node, ast.Attribute):
            assert node.attr not in forbidden
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert node.value not in forbidden
    for path in Path(jobs.__file__).parent.glob("*.py"):
        if path.name.startswith("_windows_verification_"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").endswith("_windows_verification_jobs")
            elif isinstance(node, ast.Import):
                assert not any(alias.name.endswith("_windows_verification_jobs") for alias in node.names)
            elif isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
                assert name not in {operation.__name__ for operation in OPERATIONS}


def test_all_nineteen_cases_and_native_proof_obligations_remain_open() -> None:
    root = Path(__file__).resolve().parents[3]
    harness = (root / "docs/AUTONOMOUS_PR_HARNESS.md").read_text(encoding="utf-8")
    coverage = harness.split("### 37.12. Binding coverage and acceptance traceability\n", 1)[1]
    assert [int(value) for value in re.findall(r"^\| (\d+) \|", coverage, re.M)] == list(range(1, 20))
    assert "Required native facts need native proof." in coverage
    assert "Every real Windows Job/pipe/process containment test requires\nseparate explicit approval" in harness
