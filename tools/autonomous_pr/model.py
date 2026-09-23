"""Typed values for one live AUTONOMOUS_PR v2 harness run.

Deliberately minimal: only the values needed by ``task_context.py``,
``agents.py``, and the orchestrator's v2 checkpoint primitive to describe one
in-memory run live here. No persisted state
schema, no ``run.json``, no workflow-engine abstraction, no generic Gate
hierarchy, and no provider class/registry/factory — those are explicitly
out of scope per ``docs/AUTONOMOUS_PR_HARNESS.md`` §§2, 9, 11, 13.

``Phase`` and ``RunOutcome`` are conceptual, in-process run vocabulary only.
Neither introduces or implies a new ``docs/TASK.md`` ``Status`` value
(``docs/AUTONOMOUS_PR_HARNESS.md`` §9).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TaskStatus(Enum):
    """The closed set of ``docs/TASK.md`` task statuses (``TASK.md`` §4)."""

    BACKLOG = "Backlog"
    READY = "Ready"
    CURRENT = "Current"
    BLOCKED = "Blocked"
    DONE = "Done"
    SUPERSEDED = "Superseded"


class ExecutionApproval(Enum):
    """Approval state carried by a prospective standalone task document."""

    DRAFT = "draft"
    APPROVED = "approved"


class Phase(Enum):
    """Conceptual run phases matching ``AGENTS.md`` "Autonomous flow" and
    ``docs/AUTONOMOUS_PR_HARNESS.md`` §9. Not a ``docs/TASK.md`` Status."""

    PREFLIGHT = "preflight"
    DELIVERY_BRANCH_READY = "delivery_branch_ready"
    IMPLEMENTATION_CHECKPOINT = "implementation_checkpoint"
    DETERMINISTIC_VERIFICATION = "deterministic_verification"
    CHECKPOINT_REVIEW = "checkpoint_review"
    FULL_VERIFICATION = "full_verification"
    PRE_CLOSURE_CUMULATIVE_REVIEW = "pre_closure_cumulative_review"
    DRAFT_PR = "draft_pr"
    UNPUBLISHED_TASK_CLOSURE = "unpublished_task_closure"
    CLOSURE_REVIEW = "closure_review"
    ORIGIN_MAIN_REVALIDATION = "origin_main_revalidation"
    MODE_C_FINAL_AUDIT = "mode_c_final_audit"
    REQUIRED_CI = "required_ci"
    READY_FOR_HUMAN_MERGE = "ready_for_human_merge"


class RunOutcome(Enum):
    """Terminal run outcomes, distinct from designated-reviewer verdicts."""

    STOP = "STOP"
    BLOCKED = "BLOCKED"
    NO_ELIGIBLE_TASK = "NO_ELIGIBLE_TASK"


class ReviewVerdict(Enum):
    """The strict three-token designated-reviewer verdict contract (§7)."""

    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    BLOCKED = "BLOCKED"


class CandidateRejectionBasis(Enum):
    """Why one v2 gate candidate became ineligible for another review."""

    VERIFICATION_FAILURE = "verification_failure"
    CHANGES_REQUESTED = "changes_requested"
    REPEATED_IDENTITY = "repeated_identity"


class AgentRole(Enum):
    """Distinct implementer/reviewer invocation roles (§5)."""

    IMPLEMENTER = "implementer"
    REVIEWER = "reviewer"


@dataclass(frozen=True)
class RepairFinding:
    """One complete, provider-neutral v2 repair finding (Harness §25)."""

    problem: str
    evidence: str
    required_outcome: str
    recommended_repair: str
    verification_focus: str
    affected_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class NonConvergenceDiagnosis:
    """Mandatory diagnosis from the second consecutive v2 rejection (§26)."""

    previous_requirement: str
    actual_change: str
    why_unsatisfied: str
    misunderstanding: str
    remaining_required_outcome: str
    recommended_corrective_approach: str


@dataclass(frozen=True)
class RepairPacket:
    """Machine-validated repair data returned with ``CHANGES_REQUESTED``."""

    findings: tuple[RepairFinding, ...]
    non_convergence: NonConvergenceDiagnosis | None = None


@dataclass(frozen=True)
class StructuredReviewResult:
    """One v2 reviewer result after verdict and repair-packet validation."""

    verdict: ReviewVerdict
    repair_packet: RepairPacket | None
    raw_output: str
    blocked_reason: str | None = None
    verdict_is_explicit: bool = False


@dataclass(frozen=True)
class VerificationCommandResult:
    """The outcome of one orchestrator-owned deterministic verification subprocess.

    Pass/fail is derived only from ``returncode`` — the LLM never decides
    whether a failing check is "good enough" (``docs/AUTONOMOUS_PR_HARNESS.md``
    §15).
    """

    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    passed: bool


@dataclass(frozen=True)
class VerificationEvidence:
    """Explicit handoff evidence for one deterministic verification run (§6).

    ``head_sha`` is the exact commit this evidence was produced against —
    the repository ``HEAD`` at the moment the verification commands ran.
    Binding evidence to an exact SHA lets a later consumer (prospective
    Task Closure's handoff) positively prove it is presenting verification
    evidence for the same commit as the accepted implementation diff it is
    handed alongside, rather than silently reusing stale evidence from an
    earlier commit a since-repaired checkpoint invalidated.
    """

    commands: tuple[VerificationCommandResult, ...]
    passed: bool
    head_sha: str


@dataclass(frozen=True)
class GateContext:
    """The comparison scope for candidate identities at one v2 gate.

    A candidate digest alone never identifies this context: the gate, fixed
    spec, and accepted base are explicit, separate values (Harness §28).
    """

    gate_id: str
    spec_identity: str
    accepted_base_context_identity: str


@dataclass(frozen=True)
class CandidateIdentity:
    """A deterministic fingerprint of review-relevant candidate content."""

    digest: str


@dataclass(frozen=True)
class GateAttempt:
    """Audit record for one candidate produced at a v2 gate (Harness §29)."""

    candidate_identity: CandidateIdentity
    candidate_state: str
    verification: VerificationEvidence | None
    rejected: bool
    rejection_basis: CandidateRejectionBasis | None
    review_iteration: int | None
    reviewer_verdict: ReviewVerdict | None
    findings: tuple[RepairFinding, ...] = ()
    repair_packet: RepairPacket | None = None
    repair_delta_digest: str | None = None


@dataclass
class GateHistory:
    """Minimal mutable, in-memory-only state for one v2 review gate.

    This type is never serialized and is never used as resumable run state.
    """

    context: GateContext
    review_iteration: int = 0
    consecutive_changes_requested: int = 0
    rejected_candidate_identities: set[CandidateIdentity] = field(default_factory=set)
    attempts: list[GateAttempt] = field(default_factory=list)
    latest_valid_repair_packet: RepairPacket | None = None
    previous_reviewed_candidate_identity: CandidateIdentity | None = None
    previous_reviewed_candidate_state: str | None = None


VerificationArgv = tuple[str, ...]
"""One shell-free verification command: a non-empty ``argv`` tuple.

The approved Task Execution Spec representation is a JSON argv array
(``["python", "-m", "pytest", "tests/foo.py"]``), decoded by
:mod:`.task_spec` into this tuple. It is never a shell string: nothing in
this harness runs it through a shell, expands variables in it, or applies
``shlex`` semantics to it.
"""


@dataclass(frozen=True)
class ExecutionCheckpoint:
    """One declared ``CP-N`` checkpoint of a Task Execution Spec (Harness §23).

    ``number`` is the sequential integer in ``checkpoint_id`` (``CP-3`` ->
    ``3``). A checkpoint has no ``TSK-*`` ID and no status of its own.
    """

    number: int
    checkpoint_id: str
    name: str
    objective: str
    required_result: str
    constraints: str
    verification: tuple[VerificationArgv, ...]
    review_focus: str


@dataclass(frozen=True)
class TaskExecutionSpec:
    """A parsed, structurally valid, execution-ready Task Execution Spec.

    Provider-neutral and lifecycle-free (Harness §22): it carries no Status,
    Priority, Size, dependency, or queue position — those live only in
    ``docs/TASK.md``.

    ``text`` is the exact spec text as read, and ``digest`` its
    deterministic sha256. Together they are the spec's identity in the live
    run input, so a later step can prove the spec is unchanged
    (:func:`.task_spec.spec_is_unchanged`; Harness §30 "Spec immutability").
    ``digest`` is not a signing framework.
    """

    task_id: str
    path: str
    title: str
    goal: str
    context_references: str
    scope: str
    out_of_scope: str
    approved_implementation_approach: str
    acceptance_criteria: str
    checkpoints: tuple[ExecutionCheckpoint, ...]
    full_verification: tuple[VerificationArgv, ...]
    known_constraints: str
    text: str
    digest: str


@dataclass(frozen=True)
class TaskMetadata:
    """Immutable metadata envelope for one prospective standalone task."""

    execution_approval: ExecutionApproval
    priority: str
    size: str
    roadmap_target: str
    depends_on: tuple[str, ...]
    group: str | None = None


@dataclass(frozen=True)
class DraftTaskDocument:
    """A valid draft envelope, optionally with an unvalidated execution body."""

    task_id: str
    path: str
    title: str
    metadata: TaskMetadata
    text: str
    digest: str


@dataclass(frozen=True)
class ApprovedTaskDocument:
    """An approved standalone task with a complete execution body."""

    task_id: str
    path: str
    title: str
    metadata: TaskMetadata
    execution_spec: TaskExecutionSpec
    text: str
    digest: str


TaskDocument = DraftTaskDocument | ApprovedTaskDocument
"""One parsed prospective standalone task document."""


@dataclass(frozen=True)
class TaskFileRecord:
    """One regular, Git-tracked task file read from one exact commit."""

    source_sha: str
    path: str
    text: str


@dataclass(frozen=True)
class TaskCatalog:
    """Validated nonterminal task documents from one immutable Git snapshot."""

    source_sha: str
    documents: tuple[TaskDocument, ...]
    terminal_tasks: tuple[TerminalTask, ...]
    exclusions: tuple[TaskSelectionReason, ...]


@dataclass(frozen=True)
class TaskSelectionReason:
    """Why one catalog record is excluded or waiting rather than eligible."""

    task_id: str | None
    reason: str


class TaskSelectionMode(Enum):
    """The two explicit selector forms supported by file-based dispatch."""

    EXPLICIT = "explicit"
    NEXT = "NEXT"


@dataclass(frozen=True)
class SelectedTask:
    """One deterministic target resolved from a fixed catalog snapshot."""

    source_sha: str
    mode: TaskSelectionMode
    document: ApprovedTaskDocument
    basis: str


@dataclass(frozen=True)
class NoEligibleTask:
    """Successful no-work result for ``NEXT``; never a reviewer verdict."""

    reasons: tuple[TaskSelectionReason, ...]
    outcome: RunOutcome = RunOutcome.NO_ELIGIBLE_TASK
    exit_code: int = 0


TaskSelectionResult = SelectedTask | NoEligibleTask
"""Pure selector result: one target or a successful no-work outcome."""


@dataclass(frozen=True)
class TrackerTask:
    """One row of the operational v2 ``# Open task index``.

    The v2 index owns every mutable lifecycle fact of an open task,
    including ``depends_on`` (Harness §22): the Task Execution Spec never
    carries any of them.
    """

    task_id: str
    status: TaskStatus
    priority: str
    size: str
    group: str
    roadmap_target: str
    depends_on: tuple[str, ...]
    title: str


@dataclass(frozen=True)
class TerminalTask:
    """One row of the operational v2 durable ``# Terminal task index``.

    ``status`` is only ever :attr:`TaskStatus.DONE` or
    :attr:`TaskStatus.SUPERSEDED`. Unlike ``# Recently completed`` this index
    is not a bounded window, so a dependency's ``Done`` status stays
    positively confirmable after the task leaves the recent view.
    """

    task_id: str
    status: TaskStatus
    evidence: str
    title: str


@dataclass(frozen=True)
class TerminalRegistry:
    """Immutable terminal lifecycle facts parsed independently of an open queue."""

    tasks: tuple[TerminalTask, ...]
    source_sha: str | None = None


@dataclass(frozen=True)
class ThinTracker:
    """The lifecycle facts parsed from a v2-format ``docs/TASK.md``."""

    current_task_id: str | None
    open_tasks: tuple[TrackerTask, ...]
    terminal_tasks: tuple[TerminalTask, ...]


@dataclass(frozen=True)
class ExactBaseInput:
    """``docs/TASK.md`` and the task spec, both read from one exact SHA.

    ``base_sha`` is the caller-captured exact ``origin/main`` SHA, and the one
    SHA both texts belong to (Harness §30): the only producer,
    :func:`.task_context.load_exact_base_input`, reads both at exactly that
    SHA, without fetching. ``spec_text`` is ``None`` when the spec file does
    not exist at ``base_sha``.
    """

    base_sha: str
    task_md_text: str
    spec_text: str | None


@dataclass(frozen=True)
class ExecutionTarget:
    """The validated execution target produced by v2 preflight.

    Descriptive execution input only, never proof that the user gave a
    separate explicit ``AUTONOMOUS_PR`` invocation (Harness §3).
    """

    base_sha: str
    task: TrackerTask
    spec: TaskExecutionSpec
    document: ApprovedTaskDocument | None = None
    spec_source_sha: str | None = None
    selection_mode: TaskSelectionMode | None = None
    selection_basis: str | None = None


@dataclass(frozen=True)
class RunResult:
    """The outcome of one orchestrator run, returned to the CLI caller.

    ``outcome`` is :attr:`RunOutcome.BLOCKED` for any genuine fail-closed
    terminal condition, :attr:`RunOutcome.NO_ELIGIBLE_TASK` for the successful
    no-work ``NEXT`` result, :attr:`RunOutcome.STOP` once the run has actually
    reached ``READY_FOR_HUMAN_MERGE`` (``docs/AUTONOMOUS_PR_HARNESS.md`` §10)
    — the full ``preflight`` through draft-PR / prospective Task Closure /
    mode C final cumulative audit / required-CI tail — or ``None`` if a caller
    obtained this value from an internal phase helper before the run reached a
    terminal state (only :func:`.orchestrator.run` itself should ever observe
    ``None`` in practice). ``STOP`` is never manufactured before every required
    gate — closure review, post-closure origin/main revalidation, a fresh mode C
    audit, and green required CI — has actually passed.

    ``task_id`` is the resolved concrete identity. It is ``None`` when ``NEXT``
    found no eligible task; the selector token is never reported as a task ID.

    ``pr_url`` is populated once the draft PR exists (``None`` before that
    phase, or on any run that never reaches it).
    """

    task_id: str | None
    phase: Phase
    outcome: RunOutcome | None
    delivery_branch: str | None
    head_sha: str | None
    blocked_reason: str | None
    pr_url: str | None = None
    selection_mode: TaskSelectionMode | None = None
    spec_source_sha: str | None = None
    spec_path: str | None = None
    spec_digest: str | None = None
    no_work_reasons: tuple[TaskSelectionReason, ...] = ()
