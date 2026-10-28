"""H-owned, empty Job pair; dormant pre-assignment foundation only.

No owned handles escape this object, and no assignment/transfer API exists.
Future atomic launch must introduce its own reviewed lifecycle. Successful
release here confirms handle retirement only, never process quiescence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import Lock

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


class PreassignmentJobs:
    """Create/configure/read back two unnamed Jobs using a checked injected API.

    Deliberately has no generic close, context manager, finalizer, raw-handle
    getter or ownership transfer. The only release is guarded by this object's
    exclusively pre-assignment lifetime and consumes every close attempt once.
    """

    def __init__(self, api: JobNativeApi) -> None:
        self._state_lock = Lock()
        self._api = api
        self._jobs = (_OwnedJob(JobLabel.SUPERVISION), _OwnedJob(JobLabel.COMMAND))
        self._ready = False
        self._retirement_started = False
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
        except BaseException as error:
            # Retain a checked primary failure, even when retirement also fails.
            primary = error if isinstance(error, WindowsVerificationError) else sanitized_error(
                error, Stage.JOBS,
                Category.RESOURCE if isinstance(error, MemoryError) else Category.UNCERTAIN_STATE,
            )
            with self._state_lock:
                self._ready = False
                self._retirement_started = True
            primary.cleanup_failures = self._retire()
            self._record_cleanup(primary)
            raise primary from None

    @property
    def ownership(self) -> tuple[JobOwnership, ...]:
        """Immutable accounting snapshots intentionally omit native handles."""
        with self._state_lock:
            return tuple(JobOwnership(job.label, job.state) for job in self._jobs)

    def _record_cleanup(self, failure: WindowsVerificationError) -> None:
        with self._state_lock:
            failure.unresolved_jobs = tuple(
                job.label.value for job in self._jobs
                if job.state not in (OwnershipState.NEVER_ACQUIRED, OwnershipState.CONFIRMED_CLOSED)
            )
            failure.cleanup_confirmed = not failure.unresolved_jobs

    def _retire(self) -> tuple[FailureDiagnostic, ...]:
        failures = []
        for job in reversed(self._jobs):
            with self._state_lock:
                if job.state is not OwnershipState.OWNED_PREASSIGNMENT:
                    continue
                # Consume the attempt under the state mutex, then release it
                # before calling external code (which may itself reenter).
                job.state = OwnershipState.CLOSE_ATTEMPTED
                handle = job.handle
            try:
                if handle is None:
                    raise WindowsVerificationError(Stage.CLOSE, Category.OWNERSHIP)
                self._api.close_handle(handle)
            except BaseException as error:
                with self._state_lock:
                    job.state = OwnershipState.UNCERTAIN_CLOSE
                failure = sanitized_error(error, Stage.CLEANUP, Category.UNCERTAIN_STATE)
                failures.append(failure.diagnostic())
            else:
                with self._state_lock:
                    job.state = OwnershipState.CONFIRMED_CLOSED
        return tuple(failures)

    def release_preassignment(self) -> None:
        """One checked, reverse-order retirement of this still-empty owned pair."""
        failure: WindowsVerificationError | None = None
        with self._state_lock:
            if (not self._ready or self._retirement_started
                    or any(job.state is not OwnershipState.OWNED_PREASSIGNMENT for job in self._jobs)):
                failure = WindowsVerificationError(Stage.CLOSE, Category.OWNERSHIP)
            else:
                # The check and irreversible claim are one atomic transition.
                # Only this caller may retire handles after dropping the mutex.
                self._ready = False
                self._retirement_started = True
        if failure is not None:
            self._record_cleanup(failure)
            raise failure
        failures = self._retire()
        if failures:
            first = failures[0]
            primary = WindowsVerificationError(
                Stage.CLOSE, Category.UNCERTAIN_STATE,
                winerror=first.winerror, errno=first.errno,
            )
            primary.cleanup_failures = failures[1:]
            self._record_cleanup(primary)
            raise primary
