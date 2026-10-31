"""H-owned, empty Job pair; dormant pre-assignment foundation only.

No owned handles escape this object, and no assignment/transfer API exists.
Future atomic launch must introduce its own reviewed lifecycle. Successful
release here confirms handle retirement only, never process quiescence.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from weakref import WeakKeyDictionary

from ._windows_verification_native import (
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    Category,
    FailureDiagnostic,
    JobNativeApi,
    Stage,
    WindowsVerificationError,
    checked_handle,
    sanitized_error,
)


class JobLabel(str, Enum):
    SUPERVISION = "J_supervision"
    COMMAND = "J_command"


class OwnershipState(str, Enum):
    NEVER_ACQUIRED = "never_acquired"
    OWNED_PREASSIGNMENT = "owned_preassignment"
    CLOSE_ATTEMPTED = "close_attempted"
    CONFIRMED_CLOSED = "confirmed_closed"
    UNCERTAIN_CLOSE = "uncertain_close"


@dataclass(frozen=True)
class JobOwnership:
    label: JobLabel
    state: OwnershipState


@dataclass
class _OwnedJob:
    label: JobLabel
    state: OwnershipState = OwnershipState.NEVER_ACQUIRED
    handle: int | None = field(default=None, repr=False)


class _PrelaunchPhase(str, Enum):
    EMPTY_READY = "EMPTY_READY"
    RESERVED_EMPTY = "RESERVED_EMPTY"
    NATIVE_CREATION_FENCED = "NATIVE_CREATION_FENCED"
    EMPTY_CLOSE_CLAIMED = "EMPTY_CLOSE_CLAIMED"
    EMPTY_CLOSED = "EMPTY_CLOSED"
    EMPTY_UNCERTAIN = "EMPTY_UNCERTAIN"


@dataclass(frozen=True)
class _PrelaunchSnapshot:
    phase: _PrelaunchPhase
    roles: tuple[JobLabel, ...]
    uncertain: bool


@dataclass(eq=False, repr=False)
class _OwnerPin:
    # A registry reference to the SAME owner, never a handle custodian. Allocate
    # the slot before acquiring Jobs so emergency retention needs no allocation.
    _owner: PreassignmentJobs | None = None
    quarantined_owner: PreassignmentJobs | None = None

    @property
    def owner(self) -> PreassignmentJobs | None:
        return self.quarantined_owner if self.quarantined_owner is not None else self._owner

    def __repr__(self) -> str:
        return "_OwnerPin()"


# Keys are weak, values are STRONG. A pinned value keeps its exact owner (and
# therefore its key) alive. An empty value is removed only once no caller,
# in-flight guard or traceback retains that owner. No explicit slot removal can
# race a late quarantine store, and the weak-key callback performs no OS cleanup.
_OWNER_PINS: WeakKeyDictionary[PreassignmentJobs, _OwnerPin] = WeakKeyDictionary()
_INITIALIZED = object()
_UNKNOWN_CLEANUP = FailureDiagnostic(Stage.CLEANUP, Category.UNCERTAIN_STATE, None, None)
_ROLES = (JobLabel.SUPERVISION, JobLabel.COMMAND)


def _bounded_error(error: BaseException, stage: Stage) -> WindowsVerificationError:
    try:
        return sanitized_error(
            error, stage,
            Category.RESOURCE if isinstance(error, MemoryError) else Category.UNCERTAIN_STATE,
        )
    except BaseException:
        return WindowsVerificationError(stage, Category.UNCERTAIN_STATE)


def _cleanup_diagnostic(error: BaseException) -> FailureDiagnostic:
    try:
        return _bounded_error(error, Stage.CLEANUP).diagnostic()
    except BaseException:
        return _UNKNOWN_CLEANUP


def _quarantine(pair: PreassignmentJobs) -> None:
    # Never reacquire a mutex whose outcome is unknown. The slot is registered
    # before Jobs exist; retaining the owner is a plain reference assignment.
    # This reference is NEVER cleared, including by an already in-flight normal
    # unpin. A damaged mutex may have raised in a competing thread while the
    # original claimant still held it; a check-then-clear would lose that owner.
    # The reference IS the uncertainty latch: no interruptible second flag store.
    pair._pin.quarantined_owner = pair


@contextmanager
def _state_guard(pair: PreassignmentJobs) -> Iterator[None]:
    if pair._pin.quarantined_owner is not None:
        raise WindowsVerificationError(Stage.CLEANUP, Category.OWNERSHIP)
    try:
        lock = pair._state_lock
        enter, leave = type(lock).__enter__, type(lock).__exit__
        enter(lock)
    except BaseException:
        _quarantine(pair)
        raise
    try:
        if pair._pin.quarantined_owner is not None:
            raise WindowsVerificationError(Stage.CLEANUP, Category.UNCERTAIN_STATE)
        yield
    except BaseException:
        _quarantine(pair)
        try:
            leave(lock, None, None, None)
        except BaseException:
            pass  # Preserve the body cause; the lock is already quarantined.
        raise
    else:
        try:
            leave(lock, None, None, None)
        except BaseException:
            _quarantine(pair)
            raise
        if pair._pin.quarantined_owner is not None:
            raise WindowsVerificationError(Stage.CLEANUP, Category.UNCERTAIN_STATE)


def _checked_owner(pair: object) -> PreassignmentJobs:
    if type(pair) is not PreassignmentJobs or getattr(pair, "_initialized", None) is not _INITIALIZED:
        raise WindowsVerificationError(Stage.PREFLIGHT, Category.OWNERSHIP)
    try:
        invalid = (
            type(getattr(pair, "_pin", None)) is not _OwnerPin or _OWNER_PINS.get(pair) is not pair._pin
            or type(getattr(pair, "_jobs", None)) is not tuple or len(pair._jobs) != 2
            or any(type(job) is not _OwnedJob or job.label is not label
                   for job, label in zip(pair._jobs, _ROLES))
            or type(getattr(pair, "_phase", None)) is not _PrelaunchPhase
            or not hasattr(pair, "_state_lock")
        )
    except BaseException as error:
        # Read-only preclaim validation cannot consume release authority. A
        # reserved/fenced owner is already pinned; never print registry errors.
        raise _bounded_error(error, Stage.PREFLIGHT) from None
    if invalid:
        raise WindowsVerificationError(Stage.PREFLIGHT, Category.OWNERSHIP)
    return pair


def _register_owner(pair: PreassignmentJobs) -> None:
    # One identity slot, preallocated before native acquisition. No handle/hash
    # registration or owning handoff; concurrent reference stores are idempotent.
    pair._pin._owner = pair


def _discard_pin(pair: PreassignmentJobs) -> None:
    # Only under the state mutex on known rejection or confirmed empty closes.
    # A pending reservation must recheck its pin under that SAME mutex.
    pair._pin._owner = None


class PreassignmentJobs:
    """Create/configure/read back two unnamed Jobs using a checked injected API.

    Deliberately has no generic close, context manager, finalizer, raw-handle
    getter or ownership transfer. The only release is guarded by this object's
    empty prelaunch phase and consumes every close attempt once.
    """

    def __init__(self, api: JobNativeApi) -> None:
        self._state_lock = Lock()
        self._api = api
        self._jobs = (_OwnedJob(JobLabel.SUPERVISION), _OwnedJob(JobLabel.COMMAND))
        self._ready = False
        self._retirement_started = False
        self._phase = _PrelaunchPhase.EMPTY_READY
        self._initialized: object | None = None
        try:
            self._pin = _OwnerPin()
            # The initially empty slot owns no Jobs or owner. Registration
            # allocation precedes acquisition, never an irreversible claim.
            _OWNER_PINS[self] = self._pin
        except BaseException as error:
            primary = _bounded_error(error, Stage.JOBS)
            primary.cleanup_confirmed = True  # No native acquisition attempted.
            raise primary from None
        try:
            for job in self._jobs:
                handle = checked_handle(api.create_job(), Stage.JOBS)
                # A duplicate numeric value aliases the already-owned entry;
                # retain that owner and retire it once, never create a second.
                if any(previous.handle == handle for previous in self._jobs):
                    raise WindowsVerificationError(Stage.JOBS, Category.OWNERSHIP)
                job.handle = handle
                job.state = OwnershipState.OWNED_PREASSIGNMENT
                api.configure_job(handle)
                flags = api.query_job_flags(handle)
                if type(flags) is not int or flags != JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE:
                    raise WindowsVerificationError(Stage.JOBS, Category.UNCERTAIN_STATE)
            self._ready = True
            self._initialized = _INITIALIZED
        except BaseException as error:
            # The failed constructor cannot return this owner. Pin it BEFORE
            # fallible projection/rollback, and clear only after checked cleanup
            # and bookkeeping both finish. Tracebacks are not lifetime custody.
            self._pin._owner = self
            self._initialized = None
            # Retain a checked primary failure, even when retirement also fails.
            primary = error if isinstance(error, WindowsVerificationError) else _bounded_error(error, Stage.JOBS)
            try:
                with _state_guard(self):
                    self._ready = False
                    self._retirement_started = True
                primary.cleanup_failures = self._retire()
                self._record_cleanup(primary)
                if primary.cleanup_confirmed:
                    with _state_guard(self):
                        _discard_pin(self)
            except BaseException as cleanup_error:
                _quarantine(self)
                primary.cleanup_confirmed = False
                secondary: tuple[FailureDiagnostic, ...] = (_cleanup_diagnostic(cleanup_error),)
                if isinstance(cleanup_error, WindowsVerificationError):
                    secondary += cleanup_error.cleanup_failures[:2]
                primary.cleanup_failures = (*primary.cleanup_failures, *secondary)[:3]
                primary.unresolved_jobs = tuple(
                    job.label.value for job in self._jobs
                    if job.state not in (OwnershipState.NEVER_ACQUIRED, OwnershipState.CONFIRMED_CLOSED)
                )
            raise primary from None

    def __repr__(self) -> str:
        return "PreassignmentJobs()"

    @property
    def ownership(self) -> tuple[JobOwnership, ...]:
        """Immutable accounting snapshots intentionally omit native handles."""
        if self._pin.quarantined_owner is not None:
            # Audit only, with conservative unresolved states, never permission.
            return tuple(JobOwnership(job.label, (
                job.state if job.state in (OwnershipState.NEVER_ACQUIRED, OwnershipState.CONFIRMED_CLOSED)
                else OwnershipState.UNCERTAIN_CLOSE
            )) for job in self._jobs)
        try:
            with _state_guard(self):
                snapshot = tuple(JobOwnership(job.label, job.state) for job in self._jobs)
            return snapshot
        except BaseException as error:
            raise _bounded_error(error, Stage.CLEANUP) from None

    def _record_cleanup(self, failure: WindowsVerificationError) -> None:
        if self._pin.quarantined_owner is not None:
            failure.unresolved_jobs = tuple(
                job.label.value for job in self._jobs
                if job.state not in (OwnershipState.NEVER_ACQUIRED, OwnershipState.CONFIRMED_CLOSED)
            )
            failure.cleanup_confirmed = False
            return
        with _state_guard(self):
            failure.unresolved_jobs = tuple(
                job.label.value for job in self._jobs
                if job.state not in (OwnershipState.NEVER_ACQUIRED, OwnershipState.CONFIRMED_CLOSED)
            )
            failure.cleanup_confirmed = not failure.unresolved_jobs

    def _retire(self) -> tuple[FailureDiagnostic, ...]:
        failures: list[FailureDiagnostic] = []
        try:
            for job in reversed(self._jobs):
                with _state_guard(self):
                    # The original private helper is not an alternate release
                    # route. Only a claimed cleanup (or constructor rollback)
                    # may consume an actual close attempt, even after fencing.
                    if (not self._retirement_started or (
                            self._initialized is _INITIALIZED
                            and self._phase is not _PrelaunchPhase.EMPTY_CLOSE_CLAIMED)):
                        raise WindowsVerificationError(Stage.CLOSE, Category.OWNERSHIP)
                    if job.state is not OwnershipState.OWNED_PREASSIGNMENT:
                        continue
                    job.state = OwnershipState.CLOSE_ATTEMPTED
                    handle = job.handle
                try:
                    if handle is None:
                        raise WindowsVerificationError(Stage.CLOSE, Category.OWNERSHIP)
                    # Check malformed injected wrappers as well as checked APIs.
                    result = self._api.close_handle(handle)  # type: ignore[func-returns-value]
                    if result is not None:
                        raise WindowsVerificationError(Stage.CLOSE, Category.UNCERTAIN_STATE)
                except BaseException as error:
                    failures.append(_cleanup_diagnostic(error))
                    with _state_guard(self):
                        job.state = OwnershipState.UNCERTAIN_CLOSE
                else:
                    with _state_guard(self):
                        job.state = OwnershipState.CONFIRMED_CLOSED
        except BaseException as error:
            _quarantine(self)
            if failures:
                primary = _retirement_error(tuple(failures))
                primary.cleanup_failures += (_cleanup_diagnostic(error),)
                raise primary from None
            raise
        return tuple(failures)

    def release_preassignment(self) -> None:
        """One checked, reverse-order retirement of this still-empty owned pair."""
        _claim_empty_retirement(self, _PrelaunchPhase.EMPTY_READY)
        _finish_empty_retirement(self)


def _rejection(pair: PreassignmentJobs, stage: Stage) -> WindowsVerificationError:
    failure = WindowsVerificationError(stage, Category.OWNERSHIP)
    try:
        pair._record_cleanup(failure)
    except BaseException:
        # This is already an ownership rejection, never acquire a damaged lock.
        failure.cleanup_confirmed = False
        failure.unresolved_jobs = tuple(label.value for label in _ROLES)
    return failure


def _empty_ready(pair: PreassignmentJobs) -> bool:
    return (
        pair._ready and not pair._retirement_started
        and all(job.state is OwnershipState.OWNED_PREASSIGNMENT for job in pair._jobs)
    )


def _reserve_prelaunch(pair: PreassignmentJobs) -> None:
    """Claim the existing owner, without returning any native capability."""
    pair = _checked_owner(pair)
    if pair._pin.quarantined_owner is not None:
        raise _rejection(pair, Stage.PREFLIGHT)
    try:
        _register_owner(pair)
    except BaseException as error:
        # No claim was attempted. Remove only this known, unnecessary pin;
        # another reservation/uncertainty must retain the exact same owner.
        try:
            with _state_guard(pair):
                if pair._phase in (_PrelaunchPhase.EMPTY_READY, _PrelaunchPhase.EMPTY_CLOSED):
                    _discard_pin(pair)
        except BaseException:
            _quarantine(pair)
        raise _bounded_error(error, Stage.PREFLIGHT) from None
    try:
        with _state_guard(pair):
            accepted = (
                pair._phase is _PrelaunchPhase.EMPTY_READY and _empty_ready(pair)
                and pair._pin._owner is pair
            )
            if accepted:
                pair._phase = _PrelaunchPhase.RESERVED_EMPTY
            elif pair._phase in (_PrelaunchPhase.EMPTY_READY, _PrelaunchPhase.EMPTY_CLOSED):
                _discard_pin(pair)
    except BaseException as error:
        raise _bounded_error(error, Stage.PREFLIGHT) from None
    if not accepted:
        raise _rejection(pair, Stage.PREFLIGHT)


def _fence_native_creation(pair: PreassignmentJobs) -> None:
    """Irreversible risk marker only: no process/native call or assignment."""
    pair = _checked_owner(pair)
    if pair._pin.quarantined_owner is not None:
        raise _rejection(pair, Stage.PREFLIGHT)
    try:
        with _state_guard(pair):
            accepted = pair._phase is _PrelaunchPhase.RESERVED_EMPTY and _empty_ready(pair)
            if accepted:
                pair._phase = _PrelaunchPhase.NATIVE_CREATION_FENCED
    except BaseException as error:
        raise _bounded_error(error, Stage.PREFLIGHT) from None
    if not accepted:
        raise _rejection(pair, Stage.PREFLIGHT)


def _prelaunch_snapshot(pair: PreassignmentJobs) -> _PrelaunchSnapshot:
    """Immutable phase/role audit, never a launch or cleanup permission."""
    pair = _checked_owner(pair)
    if pair._pin.quarantined_owner is not None:
        phase = (pair._phase if pair._phase is _PrelaunchPhase.NATIVE_CREATION_FENCED
                 else _PrelaunchPhase.EMPTY_UNCERTAIN)
        return _PrelaunchSnapshot(phase, _ROLES, True)
    try:
        with _state_guard(pair):
            snapshot = _PrelaunchSnapshot(
                pair._phase, _ROLES, pair._phase is _PrelaunchPhase.EMPTY_UNCERTAIN,
            )
        return snapshot
    except BaseException as error:
        raise _bounded_error(error, Stage.PREFLIGHT) from None


def _claim_empty_retirement(pair: PreassignmentJobs, expected: _PrelaunchPhase) -> None:
    if pair._pin.quarantined_owner is not None:
        raise _rejection(pair, Stage.CLOSE)
    try:
        with _state_guard(pair):
            accepted = pair._phase is expected and _empty_ready(pair)
            if accepted:
                # Also retain the original unreserved release across an
                # interruption between its claim and the _retire call.
                pair._pin._owner = pair
                pair._phase = _PrelaunchPhase.EMPTY_CLOSE_CLAIMED
                pair._ready = False
                pair._retirement_started = True
    except BaseException as error:
        raise _bounded_error(error, Stage.CLOSE) from None
    if not accepted:
        raise _rejection(pair, Stage.CLOSE)


def _retirement_error(failures: tuple[FailureDiagnostic, ...]) -> WindowsVerificationError:
    first = failures[0]
    primary = WindowsVerificationError(
        Stage.CLOSE, Category.UNCERTAIN_STATE, winerror=first.winerror, errno=first.errno,
    )
    primary.cleanup_failures = failures[1:3]
    return primary


def _finish_empty_retirement(pair: PreassignmentJobs) -> None:
    primary: WindowsVerificationError | None = None
    try:
        failures = pair._retire()  # Keep the original monkeypatchable boundary.
        if failures:
            primary = _retirement_error(failures)
        with _state_guard(pair):
            closed = all(job.state is OwnershipState.CONFIRMED_CLOSED for job in pair._jobs)
            if closed and primary is None:
                pair._phase = _PrelaunchPhase.EMPTY_CLOSED
                _discard_pin(pair)
            else:
                pair._phase = _PrelaunchPhase.EMPTY_UNCERTAIN
                pair._pin._owner = pair
        if not closed and primary is None:
            primary = WindowsVerificationError(Stage.CLOSE, Category.UNCERTAIN_STATE)
    except BaseException as error:
        _quarantine(pair)
        if primary is None:
            primary = error if isinstance(error, WindowsVerificationError) else _bounded_error(error, Stage.CLOSE)
        else:
            primary.cleanup_failures = (*primary.cleanup_failures[:1], _cleanup_diagnostic(error))
    if primary is not None:
        try:
            pair._record_cleanup(primary)
        except BaseException as error:
            _quarantine(pair)
            primary.cleanup_confirmed = False
            primary.unresolved_jobs = tuple(label.value for label in _ROLES)
            primary.cleanup_failures = (*primary.cleanup_failures[:1], _cleanup_diagnostic(error))
        raise primary from None


def _abort_prelaunch_empty(pair: PreassignmentJobs) -> None:
    """Consume exactly one reserved-empty cleanup claim, before the fence."""
    pair = _checked_owner(pair)
    _claim_empty_retirement(pair, _PrelaunchPhase.RESERVED_EMPTY)
    _finish_empty_retirement(pair)
