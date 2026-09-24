"""Deterministic AUTONOMOUS_PR v2 orchestration.

The public :func:`run` is the only production lifecycle. It performs exact-base
Task Execution Spec preflight, spec-declared checkpoint execution, adaptive
review repair, conservative evidence replay, unpublished Task Closure and
Mode C, exact publication, required CI, and then mandatory ``STOP`` at
``READY_FOR_HUMAN_MERGE``. It never merges or auto-merges.

The orchestrator alone selects deterministic transitions, verification input,
review.patch mode/range, commit/push boundaries, and evidence invalidation.
Implementer and reviewer processes receive explicit handoffs, have no direct
Git/GitHub write capability, and cannot select agents or workflow transitions.
There is no runtime plan, plan-review phase, v1 fallback, verification
override, or numeric repair budget.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Callable

from . import catalog, repository, task_context
from .agents import (
    AgentInvocationSpec,
    run_implementer,
    run_structured_reviewer,
)
from .model import (
    AgentRole,
    ApprovedTaskDocument,
    CandidateIdentity,
    CandidateRejectionBasis,
    ExecutionCheckpoint,
    ExecutionTarget,
    GateAttempt,
    GateContext,
    GateHistory,
    NoEligibleTask,
    Phase,
    RepairPacket,
    ReviewVerdict,
    RunOutcome,
    RunResult,
    StructuredReviewResult,
    SelectedTask,
    TaskExecutionSpec,
    TaskSelectionMode,
    TaskStatus,
    TrackerTask,
    VerificationCommandResult,
    VerificationEvidence,
)
from .repository import RepositoryError
from .task_context import TaskTrackerError
from .task_spec import TaskSpecError, parse_task_document

# Post-closure origin/main-movement replay is bounded to this many rounds
# (fetch/revalidate -> mode C -> required CI -> re-fetch to confirm
# stability) -- a small finite implementation-level value, not a canonical
# numeric governance limit (docs/AUTONOMOUS_PR_HARNESS.md §11, §19).
_POST_CLOSURE_MAX_ROUNDS = 2

# The canonical closure file set docs/TASK.md §18 actually requires:
# docs/TASK.md and docs/DEVELOPMENT_LOG.md every time, docs/ROADMAP.md and
# docs/DEFERRED.md only when this task's delivered work legitimately
# reconciles Roadmap/Deferred status. No other file is ever permitted in a
# prospective Task Closure diff.
_CLOSURE_REQUIRED_FILES = frozenset({"docs/TASK.md", "docs/DEVELOPMENT_LOG.md"})
_CLOSURE_OPTIONAL_FILES = frozenset({"docs/ROADMAP.md", "docs/DEFERRED.md"})
_CLOSURE_ALLOWED_FILES = _CLOSURE_REQUIRED_FILES | _CLOSURE_OPTIONAL_FILES
_CLOSURE_BASELINE_FILES = (
    "docs/TASK.md",
    "docs/ROADMAP.md",
    "docs/DEFERRED.md",
)


class _Blocked(Exception):
    """Internal control-flow signal: this run has reached a fail-closed condition.

    Never escapes :func:`run` — it is always caught there and converted into
    a terminal :class:`.model.RunResult` with
    ``outcome=RunOutcome.BLOCKED``. Kept narrow and private to this module:
    it is not a generic exception hierarchy, only the one signal this
    module's own control flow needs to unwind a nested bounded-repair loop
    to :func:`run`'s single outcome-reporting point.
    """


@dataclass(frozen=True)
class OrchestratorConfig:
    """Everything one :func:`run` call needs, supplied entirely by the caller.

    Nothing here is ever derived from implementer output. Verification is
    sourced exclusively from the accepted Task Execution Spec, and adaptive
    repair has no caller-configurable numeric limit.

    ``__post_init__`` also fails closed before any agent invocation unless
    ``implementer_spec``/``reviewer_spec`` positively declare the narrow
    external-agent capability preconditions
    (:class:`.agents.AgentInvocationSpec`'s ``fresh_context_capable``,
    ``can_edit_working_files``, ``has_git_or_github_write_access``) this
    role requires. ``has_git_or_github_write_access`` must be explicitly
    ``False`` for both roles — an undeclared (``None``) value fails closed
    exactly like ``True``, since "nobody positively asserted this command
    has no Git/GitHub write capability" is never treated as though someone
    had. As those fields' own docstring stresses: this is an operator/
    configuration assertion about the external integration, never
    ``AUTONOMOUS_PR`` authorization and never something this module
    verifies about an opaque process itself.
    """

    task_id: str
    repo: Path
    implementer_spec: AgentInvocationSpec
    reviewer_spec: AgentInvocationSpec
    delivery_branch: str
    verification_timeout_seconds: float = 600.0
    gh_command: tuple[str, ...] = ("gh",)
    selected_task_context: str | None = None

    def __post_init__(self) -> None:
        if self.implementer_spec.role is not AgentRole.IMPLEMENTER:
            raise ValueError(
                "OrchestratorConfig.implementer_spec must have role "
                "AgentRole.IMPLEMENTER"
            )
        if self.reviewer_spec.role is not AgentRole.REVIEWER:
            raise ValueError(
                "OrchestratorConfig.reviewer_spec must have role "
                "AgentRole.REVIEWER"
            )
        if self.verification_timeout_seconds <= 0:
            raise ValueError(
                "OrchestratorConfig.verification_timeout_seconds must be > 0"
            )
        if not self.reviewer_spec.fresh_context_capable:
            raise ValueError(
                "OrchestratorConfig.reviewer_spec must declare "
                "fresh_context_capable=True — an explicit operator/"
                "configuration assertion that the configured reviewer "
                "integration is one-shot/fresh-context relative to the "
                "implementer. This is not AUTONOMOUS_PR authorization and "
                "is never verified by this module for an opaque external "
                "command; declaring it is the operator's responsibility."
            )
        if self.reviewer_spec.has_git_or_github_write_access is not False:
            raise ValueError(
                "OrchestratorConfig.reviewer_spec must explicitly declare "
                "has_git_or_github_write_access=False — an unset (None) "
                "value is never treated as an implicit safe default, and "
                "True is refused outright. The designated reviewer is "
                "never given direct Git/GitHub write capability; declaring "
                "this False is the operator's positive assertion that the "
                "configured command/sandbox actually has none, not "
                "something this module can verify for an opaque process."
            )
        if not self.implementer_spec.can_edit_working_files:
            raise ValueError(
                "OrchestratorConfig.implementer_spec must declare "
                "can_edit_working_files=True"
            )
        if self.implementer_spec.has_git_or_github_write_access is not False:
            raise ValueError(
                "OrchestratorConfig.implementer_spec must explicitly "
                "declare has_git_or_github_write_access=False — an unset "
                "(None) value is never treated as an implicit safe "
                "default, and True is refused outright. The implementer is "
                "never given direct commit/push/GitHub-write capability; "
                "declaring this False is the operator's positive assertion "
                "that the configured command/sandbox actually has none, "
                "not something this module can verify for an opaque "
                "process."
            )


@dataclass(frozen=True)
class AcceptedCheckpointCandidate:
    """One v2 checkpoint candidate ready for outer commit/push orchestration."""

    checkpoint: ExecutionCheckpoint
    gate_context: GateContext
    candidate_identity: CandidateIdentity
    review_patch: repository.ReviewPatch
    verification: VerificationEvidence
    review_iteration: int


@dataclass(frozen=True)
class AcceptedCheckpointEvidence:
    """Accepted evidence and immutable review boundaries for one checkpoint."""

    candidate: AcceptedCheckpointCandidate
    predecessor_review_boundary_sha: str
    accepted_head_sha: str
    accepted_base_context_identity: str


@dataclass(frozen=True)
class V2CheckpointExecutionResult:
    """Result of the CP-only v2 primitive, before full-run integration.

    ``completed`` means every checkpoint declared by the fixed spec reached
    ``APPROVED`` in order. It deliberately does not mean the complete
    AUTONOMOUS_PR run reached ``STOP``: commit/push, cumulative review, Task
    Closure, Mode C, and CI remain later orchestration phases.
    """

    completed: bool
    accepted_candidates: tuple[AcceptedCheckpointCandidate, ...]
    gate_histories: tuple[GateHistory, ...]
    blocked_reason: str | None = None
    checkpoint_evidence: tuple[AcceptedCheckpointEvidence, ...] = ()
    terminal_phase: Phase = Phase.CHECKPOINT_REVIEW


@dataclass(frozen=True)
class V2FullVerificationEvidence:
    """Full verification bound to one exact committed v2 candidate."""

    spec_identity: str
    base_identity: str
    candidate_identity: CandidateIdentity
    head_sha: str
    verification: VerificationEvidence


@dataclass(frozen=True)
class V2CumulativeReviewEvidence:
    """Accepted pre-closure cumulative review; explicitly not Mode C."""

    spec_identity: str
    base_identity: str
    candidate_identity: CandidateIdentity
    reviewed_head_sha: str
    review_patch: repository.ReviewPatch
    review_iteration: int


@dataclass(frozen=True)
class AcceptedImplementationRepairCandidate:
    """A late implementation repair approved under mode A before acceptance."""

    gate_context: GateContext
    candidate_identity: CandidateIdentity
    review_patch: repository.ReviewPatch
    verification: VerificationEvidence
    review_iteration: int


@dataclass
class V2ImplementationEvidence:
    """Mutable in-memory evidence ledger for pre-closure v2 execution."""

    spec_identity: str
    base_identity: str
    accepted_checkpoints: list[AcceptedCheckpointEvidence]
    full_verification: V2FullVerificationEvidence | None = None
    cumulative_review: V2CumulativeReviewEvidence | None = None

    def invalidate_from_checkpoint(self, checkpoint_index: int) -> None:
        """Discard one affected checkpoint and every downstream evidence item."""

        if checkpoint_index < 0 or checkpoint_index > len(self.accepted_checkpoints):
            raise ValueError("checkpoint_index is outside accepted checkpoint order")
        del self.accepted_checkpoints[checkpoint_index:]
        self.full_verification = None
        self.cumulative_review = None


@dataclass(frozen=True)
class V2PreClosureExecutionResult:
    """Outcome of CP-3 through accepted pre-closure cumulative review."""

    completed: bool
    evidence: V2ImplementationEvidence
    cumulative_history: GateHistory
    replay_histories: tuple[GateHistory, ...]
    blocked_reason: str | None = None
    terminal_phase: Phase = Phase.PRE_CLOSURE_CUMULATIVE_REVIEW


@dataclass(frozen=True)
class V2ModeCAuditEvidence:
    """One accepted Mode C audit bound to an exact candidate and base."""

    base_sha: str
    candidate_head_sha: str
    candidate_tree_sha: str
    review_patch: repository.ReviewPatch
    review_iteration: int


@dataclass(frozen=True)
class V2ClosureExecutionResult:
    """Outcome of CP-4 through exact publication and required CI."""

    completed: bool
    published: bool
    pre_closure_result: V2PreClosureExecutionResult
    closure_candidate: repository.UnpublishedCommitCandidate | None = None
    mode_c_evidence: V2ModeCAuditEvidence | None = None
    pr_url: str | None = None
    blocked_reason: str | None = None
    terminal_phase: Phase = Phase.CLOSURE_REVIEW


def _checkpoint_result_from_evidence(
    previous: V2CheckpointExecutionResult,
    evidence: V2ImplementationEvidence,
) -> V2CheckpointExecutionResult:
    """Carry the latest accepted checkpoint ledger into downstream gates."""

    current = tuple(evidence.accepted_checkpoints)
    return V2CheckpointExecutionResult(
        completed=True,
        accepted_candidates=tuple(item.candidate for item in current),
        gate_histories=previous.gate_histories,
        checkpoint_evidence=current,
    )


class _ImplementationRepairRequired(Exception):
    """Internal transition selected deterministically from a repair packet."""

    def __init__(self, packet: RepairPacket) -> None:
        super().__init__("implementation-affecting repair required")
        self.packet = packet


@dataclass(frozen=True)
class _V2ClosureMaterialBaseline:
    """Exact authoritative texts a prospective closure was prepared against."""

    base_sha: str
    texts: tuple[tuple[str, str | None], ...]
    material_paths: frozenset[str]


def _run_v2_designated_review(
    config: OrchestratorConfig,
    review_input: str,
    patch: repository.ReviewPatch,
    *,
    context: str,
) -> StructuredReviewResult:
    """Materialize and protect the exact patch supplied to one reviewer."""

    repository.materialize_review_patch(config.repo, patch)
    fingerprint = repository.capture_fingerprint(config.repo)
    review = run_structured_reviewer(config.reviewer_spec, review_input)
    repository.verify_fingerprint_unchanged(
        config.repo, fingerprint, context=context
    )
    repository.verify_materialized_review_patch(config.repo, patch)
    return review


def _resolve_file_based_target(
    config: OrchestratorConfig,
    selector: str,
    source_sha: str,
) -> SelectedTask | NoEligibleTask:
    """Resolve one selector entirely from a single immutable main snapshot."""

    try:
        task_md_text = repository.read_utf8_file_at_ref_exact(
            config.repo, source_sha, "docs/TASK.md"
        )
        terminal = task_context.parse_terminal_registry(
            task_md_text, source_sha=source_sha
        )
        records = repository.list_task_files_at_commit(
            config.repo,
            source_sha,
            excluded_task_ids=frozenset(task.task_id for task in terminal.tasks),
        )
        return catalog.resolve_task_selection(
            source_sha, records, terminal, selector
        )
    except (
        TaskTrackerError,
        catalog.TaskCatalogError,
        catalog.TaskSelectionError,
    ) as exc:
        raise _Blocked(f"file-based task selection failed: {exc}") from exc


def _execution_target_from_selection(selection: SelectedTask) -> ExecutionTarget:
    document = selection.document
    metadata = document.metadata
    return ExecutionTarget(
        base_sha=selection.source_sha,
        task=TrackerTask(
            task_id=document.task_id,
            priority=metadata.priority,
            size=metadata.size,
            group=metadata.group or "",
            roadmap_target=metadata.roadmap_target,
            depends_on=metadata.depends_on,
            title=document.title,
        ),
        spec=document.execution_spec,
        document=document,
        spec_source_sha=selection.source_sha,
        selection_mode=selection.mode,
        selection_basis=selection.basis,
    )


def _selected_task_context(execution_target: ExecutionTarget) -> str:
    document = execution_target.document
    if document is None or execution_target.spec_source_sha is None:
        return ""
    mode = execution_target.selection_mode
    return (
        f"selected_task_id: {document.task_id}\n"
        f"selection_mode: {mode.value if mode is not None else 'unknown'}\n"
        f"selection_basis: {execution_target.selection_basis or '(none)'}\n"
        f"original_source_sha: {execution_target.spec_source_sha}\n"
        f"canonical_path: {document.path}\n"
        f"full_document_digest: {document.digest}\n"
    )


def run(config: OrchestratorConfig) -> RunResult:
    """Execute the full AUTONOMOUS_PR orchestration for one already-
    authorized task.

    Always returns a :class:`.model.RunResult` — an expected fail-closed
    condition (task revalidation failure, a repository invariant violation,
    a terminal reviewer verdict, or deterministic no-progress) is reported as
    ``outcome=RunOutcome.BLOCKED`` rather than raised, matching this
    package's existing style of representing expected failure as data
    (``agents.AgentInvocationResult``) rather than exceptions. An
    unexpected/programmer-error exception (e.g. a misconfigured
    :class:`OrchestratorConfig`, already rejected in ``__post_init__``) is
    not caught here and propagates normally. ``outcome=RunOutcome.STOP`` is
    returned only once every phase below has actually completed.
    """

    phase = Phase.PREFLIGHT
    delivery_branch: str | None = None
    head_sha: str | None = None
    pr_url: str | None = None
    selected_task_id: str | None = None
    selection_mode: TaskSelectionMode | None = None
    spec_source_sha: str | None = None
    spec_path: str | None = None
    spec_digest: str | None = None
    acceptance_revalidation_failed = False
    try:
        base_sha = repository.fetch_and_capture_origin_main_sha(config.repo)
        if not repository.is_worktree_clean(config.repo):
            raise _Blocked("working tree/index is not clean before v2 preflight")
        selection = _resolve_file_based_target(config, config.task_id, base_sha)
        if isinstance(selection, NoEligibleTask):
            return RunResult(
                task_id=None,
                phase=Phase.PREFLIGHT,
                outcome=RunOutcome.NO_ELIGIBLE_TASK,
                delivery_branch=None,
                head_sha=None,
                blocked_reason=None,
                no_work_reasons=selection.reasons,
            )
        execution_target = _execution_target_from_selection(selection)
        selected_task_id = selection.document.task_id
        selection_mode = selection.mode
        spec_source_sha = selection.source_sha
        spec_path = selection.document.path
        spec_digest = selection.document.digest
        delivery_branch_name = config.delivery_branch or (
            f"autonomous-pr/{selected_task_id.lower()}"
        )
        canonical_delivery_branch = f"autonomous-pr/{selected_task_id.lower()}"
        repository.require_branch_name_available(
            config.repo, canonical_delivery_branch
        )
        if delivery_branch_name != canonical_delivery_branch:
            repository.require_branch_name_available(
                config.repo, delivery_branch_name
            )
        repository.require_no_open_pr_for_task(
            config.repo,
            selected_task_id,
            gh_command=config.gh_command,
        )
        config = replace(
            config,
            task_id=selected_task_id,
            delivery_branch=delivery_branch_name,
            selected_task_context=_selected_task_context(execution_target),
        )

        phase = Phase.DELIVERY_BRANCH_READY
        repository.create_delivery_branch_from_sha(
            config.repo, delivery_branch_name, base_sha
        )
        delivery_branch = delivery_branch_name
        head_sha = repository.head_sha(config.repo)
        accepted_origin_base_sha = execution_target.base_sha

        def accept_candidate(
            candidate: AcceptedCheckpointCandidate | AcceptedImplementationRepairCandidate,
        ) -> str:
            nonlocal acceptance_revalidation_failed
            nonlocal accepted_origin_base_sha, head_sha, phase
            phase = Phase.ORIGIN_MAIN_REVALIDATION
            try:
                revalidated, _ = _revalidate_v2_execution_target(
                    config, execution_target, accepted_origin_base_sha
                )
            except (_Blocked, RepositoryError):
                acceptance_revalidation_failed = True
                raise
            accepted_origin_base_sha = revalidated.base_sha
            phase = Phase.CHECKPOINT_REVIEW
            paths = repository.changed_paths(config.repo)
            accepted_head = repository.commit_reviewed_checkpoint(
                config.repo,
                reviewed_patch=candidate.review_patch,
                message=_v2_commit_message(config.task_id, candidate.gate_context.gate_id),
                paths=paths,
            )
            # A local commit is already a material side effect even if the
            # immediately following push fails. Preserve that exact fact in
            # the public result rather than reporting the older HEAD.
            head_sha = accepted_head
            repository.push_delivery_branch(
                config.repo,
                branch=config.delivery_branch,
                expected_branch=config.delivery_branch,
            )
            return accepted_head

        phase = Phase.IMPLEMENTATION_CHECKPOINT
        checkpoint_result = execute_v2_checkpoints(
            config,
            execution_target.spec,
            accepted_base_context_identity=base_sha,
            checkpoint_acceptor=accept_candidate,
        )
        if not checkpoint_result.completed:
            phase = (
                Phase.ORIGIN_MAIN_REVALIDATION
                if acceptance_revalidation_failed
                else checkpoint_result.terminal_phase
            )
            raise _Blocked(
                checkpoint_result.blocked_reason or "v2 checkpoint execution failed"
            )
        head_sha = repository.head_sha(config.repo)

        phase = Phase.PRE_CLOSURE_CUMULATIVE_REVIEW
        pre_closure_result = execute_v2_pre_closure_review(
            config,
            execution_target,
            checkpoint_result,
            repair_acceptor=accept_candidate,
        )
        if not pre_closure_result.completed:
            phase = (
                Phase.ORIGIN_MAIN_REVALIDATION
                if acceptance_revalidation_failed
                else pre_closure_result.terminal_phase
            )
            raise _Blocked(
                pre_closure_result.blocked_reason
                or "v2 pre-closure cumulative review failed"
            )
        head_sha = repository.head_sha(config.repo)
        checkpoint_result = _checkpoint_result_from_evidence(
            checkpoint_result, pre_closure_result.evidence
        )

        phase = Phase.UNPUBLISHED_TASK_CLOSURE
        closure_result = execute_v2_unpublished_closure(
            config,
            execution_target,
            checkpoint_result,
            pre_closure_result,
            repair_acceptor=accept_candidate,
        )
        pr_url = closure_result.pr_url
        head_sha = repository.head_sha(config.repo)
        if not closure_result.completed or not closure_result.published:
            phase = (
                Phase.ORIGIN_MAIN_REVALIDATION
                if acceptance_revalidation_failed
                else closure_result.terminal_phase
            )
            raise _Blocked(
                closure_result.blocked_reason or "v2 closure/Mode C execution failed"
            )

        return RunResult(
            task_id=selected_task_id,
            phase=Phase.READY_FOR_HUMAN_MERGE,
            outcome=RunOutcome.STOP,
            delivery_branch=delivery_branch,
            head_sha=head_sha,
            blocked_reason=None,
            pr_url=pr_url,
            selection_mode=selection_mode,
            spec_source_sha=spec_source_sha,
            spec_path=spec_path,
            spec_digest=spec_digest,
        )
    except (_Blocked, RepositoryError) as exc:
        return RunResult(
            task_id=selected_task_id,
            phase=phase,
            outcome=RunOutcome.BLOCKED,
            delivery_branch=delivery_branch,
            head_sha=head_sha,
            blocked_reason=str(exc),
            pr_url=pr_url,
            selection_mode=selection_mode,
            spec_source_sha=spec_source_sha,
            spec_path=spec_path,
            spec_digest=spec_digest,
        )
def _v2_commit_message(task_id: str, gate_id: str) -> str:
    """Return a deterministic, gate-labelled message for accepted v2 work."""

    label = re.sub(r"[^a-z0-9]+", " ", gate_id.lower()).strip()
    return f"feat(tools): {task_id.lower()} {label}"






# --------------------------------------------------------------------------
# Preflight
# --------------------------------------------------------------------------








# --------------------------------------------------------------------------
# Delivery branch ready
# --------------------------------------------------------------------------










# --------------------------------------------------------------------------
# Implementation checkpoint / deterministic verification / checkpoint review
# --------------------------------------------------------------------------


def _candidate_identity(candidate_state: str) -> CandidateIdentity:
    """Fingerprint only review-relevant candidate content (Harness §28)."""

    return CandidateIdentity(
        digest=hashlib.sha256(candidate_state.encode("utf-8")).hexdigest()
    )


def _repair_packet_json(packet: RepairPacket | None) -> str:
    if packet is None:
        return "(none)"
    return json.dumps(asdict(packet), ensure_ascii=False, sort_keys=True, indent=2)


def _repair_findings_json(packet: RepairPacket) -> str:
    return json.dumps(
        [asdict(finding) for finding in packet.findings],
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )


def _repair_delta(previous: str, current: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            previous.splitlines(),
            current.splitlines(),
            fromfile="previous-reviewed-candidate",
            tofile="current-candidate",
            lineterm="",
        )
    )


def _build_v2_implementer_prompt(
    spec: TaskExecutionSpec,
    checkpoint: ExecutionCheckpoint,
    repair_packet: RepairPacket | None,
    verification_failure: str | None,
    repository_context_text: str,
) -> str:
    repair_text = _repair_packet_json(repair_packet)
    verification_text = verification_failure or "(none)"
    return (
        f"TASK_EXECUTION_SPEC:\n{spec.text}\n"
        "CURRENT_CHECKPOINT:\n"
        f"id: {checkpoint.checkpoint_id}\n"
        f"name: {checkpoint.name}\n"
        f"objective: {checkpoint.objective}\n"
        f"required_result: {checkpoint.required_result}\n"
        f"constraints: {checkpoint.constraints}\n"
        "ROLE: Implement only this declared checkpoint in the current working "
        "tree. Do not add, drop, reorder, or merge checkpoints. Do not edit "
        f"the fixed task spec at {spec.path}. Do not commit, push, or perform "
        "Git/GitHub writes.\n"
        f"CURRENT_REPAIR_PACKET:\n{repair_text}\n"
        f"CURRENT_VERIFICATION_FAILURE:\n{verification_text}\n"
        f"REPOSITORY_CONTEXT:\n{repository_context_text}"
    )


def _build_v2_reviewer_input(
    spec: TaskExecutionSpec,
    checkpoint: ExecutionCheckpoint,
    patch_text: str,
    verification: VerificationEvidence,
    review_iteration: int,
    previous_packet: RepairPacket | None,
    repair_delta: str | None,
    require_non_convergence: bool,
) -> str:
    protocol = _v2_designated_review_protocol(
        "ORDINARY_CHECKPOINT",
        (
            "Applicable task binding bases: task:goal, task:scope, "
            "task:out_of_scope, task:approved_implementation_approach.\n"
            f"Applicable current-checkpoint binding bases: checkpoint:"
            f"{checkpoint.checkpoint_id}:objective, checkpoint:"
            f"{checkpoint.checkpoint_id}:required_result, checkpoint:"
            f"{checkpoint.checkpoint_id}:constraints, checkpoint:"
            f"{checkpoint.checkpoint_id}:verification.\n"
            "Applicable repository contracts may be used through concrete "
            "repo:<reference> bases. task:acceptance_criteria and "
            "task:full_verification are not independent bases at this gate; "
            "do not demand future-checkpoint results early.\n"
        ),
    )
    contract = _v2_structured_output_contract(require_non_convergence)
    text = (
        f"TASK_EXECUTION_SPEC:\n{spec.text}\n"
        "CURRENT_GATE:\n"
        f"checkpoint_id: {checkpoint.checkpoint_id}\n"
        f"name: {checkpoint.name}\n"
        f"review_focus: {checkpoint.review_focus}\n"
        f"REVIEW_ITERATION: {review_iteration}\n"
        "ROLE: Review this checkpoint in a fresh, independent context. "
        f"{protocol}{contract}"
        f"CURRENT_PATCH:\n{patch_text}\n"
        f"PASSING_VERIFICATION:\n{_format_verification(verification)}"
    )
    if previous_packet is not None:
        text += (
            "PREVIOUS_REVIEWER_FINDINGS:\n"
            f"{_repair_findings_json(previous_packet)}\n"
        )
    if repair_delta is not None:
        text += f"REPAIR_DELTA_SINCE_LAST_REVIEWED_CANDIDATE:\n{repair_delta}\n"
    return text


def _v2_designated_review_protocol(gate_name: str, applicability: str) -> str:
    """Shared semantic protocol for every operational designated review."""

    return (
        "DESIGNATED_REVIEW_PROTOCOL:\n"
        "Before returning a verdict, determine the binding requirements "
        "applicable to this gate. Review the complete current review artifact "
        "and all supplied deterministic evidence. On a repeat review, first "
        "re-evaluate the previous reviewer findings against the current candidate, "
        "then perform a fresh material pass over every remaining applicable "
        "requirement. Already-corrected findings need not be repeated. Return "
        "one CHANGES_REQUESTED containing all independent material defects that "
        "remain or are newly discovered by that pass. Use a blocking finding "
        "only when it has a concrete binding_basis. Style preferences, optional "
        "improvements, speculative abstraction or generalization, future scope, "
        "and advisory Review focus are non-blocking unless a separate binding "
        "requirement makes them material.\n"
        "VERDICT_SEMANTICS:\n"
        "APPROVED: the applicable material pass is complete and no proven "
        "binding defect remains.\n"
        "CHANGES_REQUESTED: one or more proven repairable binding defects exist "
        "inside the fixed spec.\n"
        "BLOCKED: correct continuation requires a missing decision, scope, "
        "architecture contract, dependency, or other information not supplied "
        "by the fixed approved contract.\n"
        f"GATE_APPLICABILITY: {gate_name}\n"
        f"{applicability}"
    )


def _v2_structured_output_contract(require_non_convergence: bool) -> str:
    non_convergence_requirement = (
        "true — this review can produce the second or later consecutive "
        "CHANGES_REQUESTED at this gate"
        if require_non_convergence
        else "false — this is the first possible consecutive "
        "CHANGES_REQUESTED at this gate"
    )
    return (
        "Return "
        "exactly APPROVED, CHANGES_REQUESTED, or BLOCKED on the first non-empty "
        "line. CHANGES_REQUESTED must be followed by one machine-readable JSON "
        "repair object with a non-empty findings array. Every finding must "
        "contain these non-empty string fields: binding_basis, problem, "
        "evidence, failure_mode, required_outcome, recommended_repair, "
        "verification_focus. binding_basis must be exactly an approved "
        "task:<section>, checkpoint:CP-N:<field>, or non-empty trimmed "
        "repo:<reference>; Review focus is advisory and is not a valid "
        "binding basis. recommended_repair is required but advisory; the "
        "binding requirement and required_outcome control the repair. "
        "affected_paths is optional metadata and never replaces a required "
        "field.\n"
        "MACHINE_READABLE_OUTPUT_CONTRACT:\n"
        "finding_required_fields: binding_basis, problem, evidence, "
        "failure_mode, required_outcome, recommended_repair, "
        "verification_focus\n"
        "binding_basis_allowed_task_values: task:goal, task:scope, "
        "task:out_of_scope, task:approved_implementation_approach, "
        "task:acceptance_criteria, task:full_verification\n"
        "binding_basis_checkpoint_form: checkpoint:CP-N:<field>, where N >= 1\n"
        "binding_basis_allowed_checkpoint_fields: objective, required_result, "
        "constraints, verification\n"
        "binding_basis_repository_form: repo:<non-empty trimmed reference>\n"
        f"non_convergence_required: {non_convergence_requirement}\n"
        "non_convergence_required_fields: previous_requirement, actual_change, "
        "why_unsatisfied, misunderstanding, remaining_required_outcome, "
        "recommended_corrective_approach\n"
        "When non_convergence_required is true, CHANGES_REQUESTED must include "
        "a complete non_convergence object with every field listed above.\n"
    )


def _require_v2_checkpoint_scope(
    touched: tuple[str, ...], spec: TaskExecutionSpec
) -> None:
    _require_no_task_md_in_ordinary_checkpoint(touched)
    normalized = {path.replace("\\", "/") for path in touched}
    if spec.path.replace("\\", "/") in normalized:
        raise _Blocked(
            f"checkpoint candidate edits its fixed Task Execution Spec {spec.path}; "
            "spec mutation during an invocation is a terminal scope violation"
        )


def _format_v2_repository_context(
    branch_head: repository.BranchHead,
    accepted_base_context_identity: str,
    selected_task_context: str | None = None,
) -> str:
    """Current repository facts for one v2 implementer invocation.

    ``branch_head`` is captured immediately before the invocation and reused
    by the post-invocation mutation guard. This keeps the explicit handoff and
    the enforced repository boundary tied to the same actual state, including
    repairs and the first checkpoint after an accepted commit/push transition.
    """

    context = (
        f"delivery_branch: {branch_head.branch}\n"
        f"accepted_base_context_identity: {accepted_base_context_identity}\n"
        f"head_sha: {branch_head.head_sha}\n"
    )
    if selected_task_context:
        context += f"SELECTED_TASK_CONTEXT:\n{selected_task_context}"
    return context


def execute_v2_checkpoints(
    config: OrchestratorConfig,
    spec: TaskExecutionSpec,
    *,
    accepted_base_context_identity: str,
    checkpoint_acceptor: Callable[[AcceptedCheckpointCandidate], str] | None,
) -> V2CheckpointExecutionResult:
    """Execute the fixed spec's checkpoint gates in declared order.

    This is the checkpoint primitive composed by public :func:`run`.
    It has no numeric repair budget.
    Accepted candidates are returned with their exact reviewed patches. The
    caller must supply the orchestrator-owned ``checkpoint_acceptor`` boundary,
    which commits and pushes immediately after approval and returns the new
    accepted-base identity. Missing or unsuccessful acceptance is terminal;
    the helper can never enter the next checkpoint while the approved one is
    still only an uncommitted candidate. Gate history is never persisted.
    """

    accepted: list[AcceptedCheckpointCandidate] = []
    checkpoint_evidence: list[AcceptedCheckpointEvidence] = []
    histories: list[GateHistory] = []
    terminal_phase = Phase.IMPLEMENTATION_CHECKPOINT

    def blocked(reason: str) -> V2CheckpointExecutionResult:
        return V2CheckpointExecutionResult(
            completed=False,
            accepted_candidates=tuple(accepted),
            gate_histories=tuple(histories),
            blocked_reason=reason,
            checkpoint_evidence=tuple(checkpoint_evidence),
            terminal_phase=terminal_phase,
        )

    if spec.task_id != config.task_id:
        return blocked(
            f"fixed spec task {spec.task_id} does not match invocation task "
            f"{config.task_id}"
        )
    if not accepted_base_context_identity.strip():
        return blocked("accepted base context identity must be non-empty")
    if checkpoint_acceptor is None:
        return blocked(
            "v2 checkpoint execution requires an orchestrator-owned "
            "checkpoint acceptor; APPROVED checkpoints must be committed and "
            "pushed before execution can continue"
        )

    expected_numbers = tuple(range(1, len(spec.checkpoints) + 1))
    if tuple(checkpoint.number for checkpoint in spec.checkpoints) != expected_numbers:
        return blocked("fixed spec checkpoints are not CP-1..CP-N in strict order")

    base_context_identity = accepted_base_context_identity
    for checkpoint in spec.checkpoints:
        context = GateContext(
            gate_id=checkpoint.checkpoint_id,
            spec_identity=spec.digest,
            accepted_base_context_identity=base_context_identity,
        )
        history = GateHistory(context=context)
        histories.append(history)
        verification_failure: str | None = None

        while True:
            terminal_phase = Phase.IMPLEMENTATION_CHECKPOINT
            before = repository.capture_branch_head(config.repo)
            repository_context_text = _format_v2_repository_context(
                before,
                context.accepted_base_context_identity,
                config.selected_task_context,
            )
            prompt = _build_v2_implementer_prompt(
                spec,
                checkpoint,
                history.latest_valid_repair_packet,
                verification_failure,
                repository_context_text,
            )
            impl_result = run_implementer(config.implementer_spec, prompt)
            try:
                repository.verify_branch_head_unchanged(
                    config.repo, before, context="v2 checkpoint implementer invocation"
                )
            except RepositoryError as exc:
                return blocked(str(exc))
            if impl_result.timed_out or impl_result.returncode != 0:
                return blocked(
                    "implementer failed during v2 checkpoint "
                    f"{checkpoint.checkpoint_id}: "
                    f"returncode={impl_result.returncode!r} "
                    f"timed_out={impl_result.timed_out!r}"
                )

            try:
                patch = repository.build_checkpoint_patch_uncommitted(config.repo)
                touched = repository.changed_paths(config.repo)
                _require_v2_checkpoint_scope(touched, spec)
            except (RepositoryError, _Blocked) as exc:
                return blocked(str(exc))

            identity = _candidate_identity(patch.diff_text)
            repair_delta = (
                _repair_delta(
                    history.previous_reviewed_candidate_state, patch.diff_text
                )
                if history.previous_reviewed_candidate_state is not None
                else None
            )
            delta_digest = (
                hashlib.sha256(repair_delta.encode("utf-8")).hexdigest()
                if repair_delta is not None
                else None
            )

            if identity in history.rejected_candidate_identities:
                history.attempts.append(
                    GateAttempt(
                        candidate_identity=identity,
                        candidate_state=patch.diff_text,
                        verification=None,
                        rejected=True,
                        rejection_basis=CandidateRejectionBasis.REPEATED_IDENTITY,
                        review_iteration=None,
                        reviewer_verdict=None,
                        repair_delta_digest=delta_digest,
                    )
                )
                return blocked(
                    f"candidate {identity.digest} repeats a previously rejected "
                    f"identity in gate {checkpoint.checkpoint_id} for the same "
                    "fixed spec and accepted base context"
                )

            try:
                terminal_phase = Phase.DETERMINISTIC_VERIFICATION
                verification = _run_verification_commands(
                    config,
                    checkpoint.verification,
                )
            except RepositoryError as exc:
                return blocked(str(exc))
            if not verification.passed:
                history.rejected_candidate_identities.add(identity)
                history.attempts.append(
                    GateAttempt(
                        candidate_identity=identity,
                        candidate_state=patch.diff_text,
                        verification=verification,
                        rejected=True,
                        rejection_basis=CandidateRejectionBasis.VERIFICATION_FAILURE,
                        review_iteration=None,
                        reviewer_verdict=None,
                        repair_delta_digest=delta_digest,
                    )
                )
                verification_failure = _format_verification(verification)
                continue

            verification_failure = None
            next_review_iteration = history.review_iteration + 1
            terminal_phase = Phase.CHECKPOINT_REVIEW
            review_input = _build_v2_reviewer_input(
                spec,
                checkpoint,
                patch.diff_text,
                verification,
                next_review_iteration,
                history.latest_valid_repair_packet,
                repair_delta,
                history.consecutive_changes_requested >= 1,
            )
            try:
                review = _run_v2_designated_review(
                    config,
                    review_input,
                    patch,
                    context="v2 checkpoint review",
                )
            except RepositoryError as exc:
                return blocked(str(exc))

            if review.verdict_is_explicit:
                history.review_iteration = next_review_iteration

            packet = review.repair_packet
            findings = packet.findings if packet is not None else ()
            if review.verdict is ReviewVerdict.APPROVED:
                history.attempts.append(
                    GateAttempt(
                        candidate_identity=identity,
                        candidate_state=patch.diff_text,
                        verification=verification,
                        rejected=False,
                        rejection_basis=None,
                        review_iteration=next_review_iteration,
                        reviewer_verdict=ReviewVerdict.APPROVED,
                        repair_delta_digest=delta_digest,
                    )
                )
                history.previous_reviewed_candidate_identity = identity
                history.previous_reviewed_candidate_state = patch.diff_text
                history.consecutive_changes_requested = 0
                accepted_candidate = AcceptedCheckpointCandidate(
                    checkpoint=checkpoint,
                    gate_context=context,
                    candidate_identity=identity,
                    review_patch=patch,
                    verification=verification,
                    review_iteration=next_review_iteration,
                )
                try:
                    next_base = checkpoint_acceptor(accepted_candidate)
                except RepositoryError as exc:
                    return blocked(str(exc))
                if not next_base.strip():
                    return blocked(
                        "checkpoint acceptor returned an empty accepted-base "
                        "context identity after the required commit/push transition"
                    )
                if next_base == context.accepted_base_context_identity:
                    return blocked(
                        "checkpoint acceptor did not advance the accepted-base "
                        "context identity after the required commit/push transition"
                    )
                accepted.append(accepted_candidate)
                checkpoint_evidence.append(
                    AcceptedCheckpointEvidence(
                        candidate=accepted_candidate,
                        predecessor_review_boundary_sha=patch.head_sha,
                        accepted_head_sha=repository.head_sha(config.repo),
                        accepted_base_context_identity=next_base,
                    )
                )
                base_context_identity = next_base
                break

            if review.verdict is ReviewVerdict.CHANGES_REQUESTED and packet is not None:
                history.consecutive_changes_requested += 1
                history.rejected_candidate_identities.add(identity)
                history.attempts.append(
                    GateAttempt(
                        candidate_identity=identity,
                        candidate_state=patch.diff_text,
                        verification=verification,
                        rejected=True,
                        rejection_basis=CandidateRejectionBasis.CHANGES_REQUESTED,
                        review_iteration=next_review_iteration,
                        reviewer_verdict=ReviewVerdict.CHANGES_REQUESTED,
                        findings=findings,
                        repair_packet=packet,
                        repair_delta_digest=delta_digest,
                    )
                )
                history.previous_reviewed_candidate_identity = identity
                history.previous_reviewed_candidate_state = patch.diff_text
                if (
                    history.consecutive_changes_requested >= 2
                    and packet.non_convergence is None
                ):
                    return blocked(
                        "second or later consecutive CHANGES_REQUESTED at gate "
                        f"{checkpoint.checkpoint_id} is missing a complete "
                        "non_convergence diagnosis"
                    )
                history.latest_valid_repair_packet = packet
                continue

            history.attempts.append(
                GateAttempt(
                    candidate_identity=identity,
                    candidate_state=patch.diff_text,
                    verification=verification,
                    rejected=False,
                    rejection_basis=None,
                    review_iteration=(
                        next_review_iteration if review.verdict_is_explicit else None
                    ),
                    reviewer_verdict=(
                        ReviewVerdict.BLOCKED if review.verdict_is_explicit else None
                    ),
                    repair_delta_digest=delta_digest,
                )
            )
            return blocked(
                review.blocked_reason
                or f"designated reviewer returned BLOCKED for {checkpoint.checkpoint_id}"
            )

    return V2CheckpointExecutionResult(
        completed=True,
        accepted_candidates=tuple(accepted),
        gate_histories=tuple(histories),
        checkpoint_evidence=tuple(checkpoint_evidence),
        terminal_phase=Phase.CHECKPOINT_REVIEW,
    )


def _committed_candidate_identity(head_sha: str) -> CandidateIdentity:
    return _candidate_identity(f"committed-head:{head_sha}")


def _all_checkpoint_verification_commands(
    spec: TaskExecutionSpec,
) -> tuple[tuple[str, ...], ...]:
    return tuple(
        command
        for checkpoint in spec.checkpoints
        for command in checkpoint.verification
    )


def _same_v2_execution_target(
    accepted: ExecutionTarget, revalidated: ExecutionTarget
) -> bool:
    """Compare every §30 load-bearing execution-target fact."""

    if accepted.document is not None:
        return (
            revalidated.document is not None
            and revalidated.document == accepted.document
            and revalidated.task == accepted.task
            and revalidated.spec.digest == accepted.spec.digest
            and revalidated.spec.text == accepted.spec.text
        )
    return (
        revalidated.task == accepted.task
        and revalidated.spec.digest == accepted.spec.digest
        and revalidated.spec.text == accepted.spec.text
    )


def _revalidate_file_selected_target_at_sha(
    config: OrchestratorConfig,
    accepted: ExecutionTarget,
    fresh_sha: str,
) -> None:
    document = accepted.document
    if document is None:
        raise AssertionError("file-selected revalidation requires a full document")

    tracker_text = repository.read_utf8_file_at_ref_exact(
        config.repo, fresh_sha, "docs/TASK.md"
    )
    terminal = task_context.parse_terminal_registry(
        tracker_text, source_sha=fresh_sha
    )
    terminal_by_id = {task.task_id: task for task in terminal.tasks}
    terminal_outcome = terminal_by_id.get(document.task_id)
    if terminal_outcome is not None:
        raise _Blocked(
            f"selected task {document.task_id} is terminal "
            f"({terminal_outcome.status.value})"
        )

    record = repository.read_task_file_at_commit(
        config.repo, fresh_sha, document.task_id
    )
    revalidated_document = parse_task_document(record.text, record.path)
    if not isinstance(revalidated_document, ApprovedTaskDocument):
        raise _Blocked(f"selected task {document.task_id} is no longer approved")
    if revalidated_document != document:
        raise _Blocked(
            "origin/main moved and changed the fixed selected task document "
            "(metadata, approval, exact text, or digest)"
        )
    for dependency in revalidated_document.metadata.depends_on:
        terminal_dependency = terminal_by_id.get(dependency)
        if (
            terminal_dependency is None
            or terminal_dependency.status is not TaskStatus.DONE
        ):
            actual = (
                "not terminal"
                if terminal_dependency is None
                else terminal_dependency.status.value
            )
            raise _Blocked(
                f"selected task dependency {dependency} is {actual}, not Done"
            )


def _revalidate_v2_execution_target(
    config: OrchestratorConfig,
    accepted: ExecutionTarget,
    current_base_sha: str,
) -> tuple[ExecutionTarget, bool]:
    """Freshly capture origin/main and revalidate a moved exact base.

    An unchanged SHA needs no second read. For a file-selected target, a moved
    SHA revalidates only the strict terminal registry, the exact selected
    document, its approval, and its ``Done`` dependencies. It deliberately
    does not rebuild the initial catalog: unrelated task bodies cannot change
    an already-fixed target. The returned boolean records a base-context
    transition; callers must invalidate cumulative evidence and gate history
    before using it.
    """

    fresh_sha = repository.fetch_and_capture_origin_main_sha(config.repo)
    if fresh_sha == current_base_sha:
        return replace(accepted, base_sha=fresh_sha), False
    if accepted.document is None:
        raise _Blocked(
            "execution target has no standalone selected task document; "
            "Current-based revalidation is not supported"
        )
    try:
        _revalidate_file_selected_target_at_sha(config, accepted, fresh_sha)
    except (RepositoryError, TaskTrackerError, TaskSpecError) as exc:
        raise _Blocked(
            "origin/main moved and selected task revalidation failed: "
            f"{exc}"
        ) from exc
    return replace(accepted, base_sha=fresh_sha), True


def _capture_v2_closure_material_baseline(
    repo: Path, base_sha: str
) -> _V2ClosureMaterialBaseline:
    """Capture closure-sensitive authoritative texts before closure preparation."""

    texts: list[tuple[str, str | None]] = []
    for path in _CLOSURE_BASELINE_FILES:
        if path == "docs/TASK.md" or repository.file_exists_at_ref(
            repo, base_sha, path
        ):
            text: str | None = repository.read_utf8_file_at_ref_exact(
                repo, base_sha, path
            )
        else:
            text = None
        texts.append((path, text))
    return _V2ClosureMaterialBaseline(
        base_sha=base_sha,
        texts=tuple(texts),
        material_paths=frozenset({"docs/TASK.md"}),
    )


def _select_v2_closure_material_paths(
    baseline: _V2ClosureMaterialBaseline, touched: tuple[str, ...]
) -> _V2ClosureMaterialBaseline:
    normalized = {path.replace("\\", "/") for path in touched}
    material_paths = {"docs/TASK.md"}
    material_paths.update(normalized & _CLOSURE_OPTIONAL_FILES)
    return _V2ClosureMaterialBaseline(
        base_sha=baseline.base_sha,
        texts=baseline.texts,
        material_paths=frozenset(material_paths),
    )


def _require_v2_closure_material_unchanged(
    repo: Path,
    baseline: _V2ClosureMaterialBaseline,
    revalidated_base_sha: str,
) -> None:
    """Reject a prepared closure whose authoritative inputs became stale."""

    expected_by_path = dict(baseline.texts)
    for path in sorted(baseline.material_paths):
        exists = repository.file_exists_at_ref(repo, revalidated_base_sha, path)
        current = (
            repository.read_utf8_file_at_ref_exact(
                repo, revalidated_base_sha, path
            )
            if exists
            else None
        )
        if current != expected_by_path[path]:
            raise _Blocked(
                "origin/main moved and changed closure-material authoritative "
                f"content in {path}; the prepared Task Closure is stale and "
                "must be reconciled and rebuilt before Mode C or publication"
            )


def _run_v2_full_verification(
    config: OrchestratorConfig,
    spec: TaskExecutionSpec,
    base_identity: str,
) -> V2FullVerificationEvidence:
    """Run only ``TaskExecutionSpec.full_verification`` at the exact HEAD."""

    verification = _run_verification_commands(config, spec.full_verification)
    if not verification.passed:
        raise _Blocked("v2 Full verification from the fixed spec failed")
    current_head = repository.head_sha(config.repo)
    if verification.head_sha != current_head:
        raise _Blocked(
            "v2 Full verification evidence is not bound to the current exact HEAD"
        )
    return V2FullVerificationEvidence(
        spec_identity=spec.digest,
        base_identity=base_identity,
        candidate_identity=_committed_candidate_identity(current_head),
        head_sha=current_head,
        verification=verification,
    )


def _build_v2_cumulative_review_input(
    spec: TaskExecutionSpec,
    patch: repository.ReviewPatch,
    full_verification: V2FullVerificationEvidence,
    history: GateHistory,
) -> str:
    protocol = _v2_designated_review_protocol(
        "PRE_CLOSURE_CUMULATIVE_IMPLEMENTATION_REVIEW",
        (
            "Review the complete implementation contract: every binding Task "
            "Execution Spec section, every declared checkpoint objective, "
            "required result, constraint, and verification, Full verification, "
            "and all applicable repository contracts. The current artifact is "
            "the complete origin/main...HEAD implementation diff before Task "
            "Closure.\n"
        ),
    )
    contract = _v2_structured_output_contract(
        history.consecutive_changes_requested >= 1
    )
    text = (
        f"TASK_EXECUTION_SPEC:\n{spec.text}\n"
        "CURRENT_GATE: pre-closure cumulative implementation review\n"
        "REVIEW_PURPOSE: PRE_CLOSURE_CUMULATIVE_REVIEW\n"
        "RANGE: origin/main...HEAD before Task Closure; this is not Mode C and "
        "satisfies the pre-closure implementation-diff review prerequisite.\n"
        f"REVIEW_ITERATION: {history.review_iteration + 1}\n"
        "ROLE: Review the complete implementation diff in a fresh, independent "
        f"context. {protocol}{contract}"
        f"SPEC_IDENTITY: {spec.digest}\n"
        f"BASE_IDENTITY: {patch.base_sha}\n"
        f"REVIEWED_HEAD_SHA: {patch.head_sha}\n"
        f"FULL_VERIFICATION_HEAD_SHA: {full_verification.head_sha}\n"
        f"FULL_VERIFICATION_CANDIDATE_IDENTITY: "
        f"{full_verification.candidate_identity.digest}\n"
        f"FULL_VERIFICATION:\n"
        f"{_format_verification(full_verification.verification)}"
        f"CURRENT_PATCH:\n{patch.diff_text}\n"
    )
    if history.latest_valid_repair_packet is not None:
        text += (
            "PREVIOUS_REVIEWER_FINDINGS:\n"
            f"{_repair_findings_json(history.latest_valid_repair_packet)}\n"
        )
    if history.previous_reviewed_candidate_state is not None:
        text += (
            "REPAIR_DELTA_SINCE_LAST_REVIEWED_CANDIDATE:\n"
            f"{_repair_delta(history.previous_reviewed_candidate_state, patch.diff_text)}\n"
        )
    return text


def _build_v2_late_repair_prompt(
    spec: TaskExecutionSpec,
    gate_id: str,
    repair_packet: RepairPacket | None,
    verification_failure: str | None,
    repository_context: str,
) -> str:
    return (
        f"TASK_EXECUTION_SPEC:\n{spec.text}\n"
        f"CURRENT_REPAIR_GATE: {gate_id}\n"
        "ROLE: Perform only the implementation repair required by the fixed "
        "spec and structured findings. Do not choose workflow transitions, "
        "commit, push, edit docs/TASK.md, or edit the fixed task spec.\n"
        f"CURRENT_REPAIR_PACKET:\n{_repair_packet_json(repair_packet)}\n"
        f"CURRENT_VERIFICATION_FAILURE:\n"
        f"{verification_failure or '(none)'}\n"
        f"REPOSITORY_CONTEXT:\n{repository_context}"
    )


def _build_v2_late_repair_review_input(
    spec: TaskExecutionSpec,
    gate_id: str,
    patch: repository.ReviewPatch,
    verification: VerificationEvidence,
    history: GateHistory,
) -> str:
    protocol = _v2_designated_review_protocol(
        "LATE_IMPLEMENTATION_REPAIR",
        (
            "First review the original/current repair findings and their "
            "required_outcome values against the current repaired candidate. "
            "Then perform a fresh material pass over the task-wide binding "
            "boundaries and applicable repository contracts. This review does "
            "not replace required downstream checkpoint/evidence replay.\n"
        ),
    )
    contract = _v2_structured_output_contract(
        history.consecutive_changes_requested >= 1
    )
    text = (
        f"TASK_EXECUTION_SPEC:\n{spec.text}\n"
        f"CURRENT_GATE: {gate_id}\n"
        "REVIEW_PURPOSE: CHECKPOINT (mode A implementation repair)\n"
        f"REVIEW_ITERATION: {history.review_iteration + 1}\n"
        "ROLE: Review this implementation repair in a fresh, independent "
        f"context. {protocol}{contract}"
        f"CURRENT_PATCH:\n{patch.diff_text}\n"
        f"PASSING_VERIFICATION:\n{_format_verification(verification)}"
    )
    if history.latest_valid_repair_packet is not None:
        text += (
            "PREVIOUS_REVIEWER_FINDINGS:\n"
            f"{_repair_findings_json(history.latest_valid_repair_packet)}\n"
        )
    if history.previous_reviewed_candidate_state is not None:
        text += (
            "REPAIR_DELTA_SINCE_LAST_REVIEWED_CANDIDATE:\n"
            f"{_repair_delta(history.previous_reviewed_candidate_state, patch.diff_text)}\n"
        )
    return text


def _execute_v2_late_repair(
    config: OrchestratorConfig,
    spec: TaskExecutionSpec,
    *,
    gate_id: str,
    accepted_base_context_identity: str,
    initial_packet: RepairPacket | None,
    verification_commands: tuple[tuple[str, ...], ...],
    repair_acceptor: Callable[[AcceptedImplementationRepairCandidate], str],
    initial_verification_failure: str | None = None,
) -> tuple[AcceptedImplementationRepairCandidate, GateHistory, str]:
    """Adaptive mode-A repair with CP-2 no-progress semantics and no budget."""

    history = GateHistory(
        context=GateContext(
            gate_id=gate_id,
            spec_identity=spec.digest,
            accepted_base_context_identity=accepted_base_context_identity,
        ),
        latest_valid_repair_packet=initial_packet,
    )
    verification_failure = initial_verification_failure

    while True:
        before = repository.capture_branch_head(config.repo)
        prompt = _build_v2_late_repair_prompt(
            spec,
            gate_id,
            history.latest_valid_repair_packet or initial_packet,
            verification_failure,
            _format_v2_repository_context(
                before,
                history.context.accepted_base_context_identity,
                config.selected_task_context,
            ),
        )
        result = run_implementer(config.implementer_spec, prompt)
        repository.verify_branch_head_unchanged(
            config.repo, before, context=f"{gate_id} implementer repair"
        )
        if result.timed_out or result.returncode != 0:
            raise _Blocked(
                f"implementer failed during {gate_id}: "
                f"returncode={result.returncode!r} timed_out={result.timed_out!r}"
            )

        patch = repository.build_checkpoint_patch_uncommitted(config.repo)
        _require_v2_checkpoint_scope(repository.changed_paths(config.repo), spec)
        identity = _candidate_identity(patch.diff_text)
        repair_delta = (
            _repair_delta(history.previous_reviewed_candidate_state, patch.diff_text)
            if history.previous_reviewed_candidate_state is not None
            else None
        )
        delta_digest = (
            hashlib.sha256(repair_delta.encode("utf-8")).hexdigest()
            if repair_delta is not None
            else None
        )
        if identity in history.rejected_candidate_identities:
            history.attempts.append(
                GateAttempt(
                    candidate_identity=identity,
                    candidate_state=patch.diff_text,
                    verification=None,
                    rejected=True,
                    rejection_basis=CandidateRejectionBasis.REPEATED_IDENTITY,
                    review_iteration=None,
                    reviewer_verdict=None,
                    repair_delta_digest=delta_digest,
                )
            )
            raise _Blocked(
                f"{gate_id} reproduced rejected candidate {identity.digest}"
            )

        verification = _run_verification_commands(config, verification_commands)
        if not verification.passed:
            history.rejected_candidate_identities.add(identity)
            history.attempts.append(
                GateAttempt(
                    candidate_identity=identity,
                    candidate_state=patch.diff_text,
                    verification=verification,
                    rejected=True,
                    rejection_basis=CandidateRejectionBasis.VERIFICATION_FAILURE,
                    review_iteration=None,
                    reviewer_verdict=None,
                    repair_delta_digest=delta_digest,
                )
            )
            verification_failure = _format_verification(verification)
            continue

        verification_failure = None
        review_input = _build_v2_late_repair_review_input(
            spec, gate_id, patch, verification, history
        )
        review = _run_v2_designated_review(
            config,
            review_input,
            patch,
            context=f"{gate_id} review",
        )
        next_iteration = history.review_iteration + 1
        if review.verdict_is_explicit:
            history.review_iteration = next_iteration

        packet = review.repair_packet
        if review.verdict is ReviewVerdict.APPROVED:
            history.consecutive_changes_requested = 0
            history.attempts.append(
                GateAttempt(
                    candidate_identity=identity,
                    candidate_state=patch.diff_text,
                    verification=verification,
                    rejected=False,
                    rejection_basis=None,
                    review_iteration=next_iteration,
                    reviewer_verdict=ReviewVerdict.APPROVED,
                    repair_delta_digest=delta_digest,
                )
            )
            accepted = AcceptedImplementationRepairCandidate(
                gate_context=history.context,
                candidate_identity=identity,
                review_patch=patch,
                verification=verification,
                review_iteration=next_iteration,
            )
            next_base = repair_acceptor(accepted)
            if not next_base.strip() or next_base == accepted_base_context_identity:
                raise _Blocked(
                    f"{gate_id} repair acceptance did not produce a new "
                    "committed/pushed base identity"
                )
            return accepted, history, next_base

        if review.verdict is ReviewVerdict.CHANGES_REQUESTED and packet is not None:
            history.consecutive_changes_requested += 1
            history.rejected_candidate_identities.add(identity)
            history.attempts.append(
                GateAttempt(
                    candidate_identity=identity,
                    candidate_state=patch.diff_text,
                    verification=verification,
                    rejected=True,
                    rejection_basis=CandidateRejectionBasis.CHANGES_REQUESTED,
                    review_iteration=next_iteration,
                    reviewer_verdict=ReviewVerdict.CHANGES_REQUESTED,
                    findings=packet.findings,
                    repair_packet=packet,
                    repair_delta_digest=delta_digest,
                )
            )
            history.previous_reviewed_candidate_identity = identity
            history.previous_reviewed_candidate_state = patch.diff_text
            if (
                history.consecutive_changes_requested >= 2
                and packet.non_convergence is None
            ):
                raise _Blocked(
                    f"{gate_id} second consecutive CHANGES_REQUESTED omitted "
                    "non_convergence diagnosis"
                )
            history.latest_valid_repair_packet = packet
            continue

        raise _Blocked(
            review.blocked_reason or f"designated reviewer blocked {gate_id}"
        )


def _review_v2_replayed_checkpoint(
    config: OrchestratorConfig,
    spec: TaskExecutionSpec,
    original: AcceptedCheckpointEvidence,
    history: GateHistory,
) -> tuple[
    ReviewVerdict | None,
    RepairPacket | None,
    AcceptedCheckpointEvidence | None,
    str | None,
]:
    checkpoint = original.candidate.checkpoint
    patch = repository.build_checkpoint_patch_committed(
        config.repo, original.predecessor_review_boundary_sha
    )
    identity = _candidate_identity(patch.diff_text)
    if identity in history.rejected_candidate_identities:
        raise _Blocked(
            f"replayed {checkpoint.checkpoint_id} repeated rejected candidate "
            f"{identity.digest}"
        )
    verification = _run_verification_commands(config, checkpoint.verification)
    if not verification.passed:
        history.rejected_candidate_identities.add(identity)
        history.attempts.append(
            GateAttempt(
                candidate_identity=identity,
                candidate_state=patch.diff_text,
                verification=verification,
                rejected=True,
                rejection_basis=CandidateRejectionBasis.VERIFICATION_FAILURE,
                review_iteration=None,
                reviewer_verdict=None,
            )
        )
        return None, None, None, _format_verification(verification)
    review_input = _build_v2_reviewer_input(
        spec,
        checkpoint,
        patch.diff_text,
        verification,
        history.review_iteration + 1,
        history.latest_valid_repair_packet,
        (
            _repair_delta(history.previous_reviewed_candidate_state, patch.diff_text)
            if history.previous_reviewed_candidate_state is not None
            else None
        ),
        history.consecutive_changes_requested >= 1,
    )
    review = _run_v2_designated_review(
        config,
        review_input,
        patch,
        context=f"replayed {checkpoint.checkpoint_id} review",
    )
    next_iteration = history.review_iteration + 1
    if review.verdict_is_explicit:
        history.review_iteration = next_iteration

    packet = review.repair_packet
    if review.verdict is ReviewVerdict.APPROVED:
        history.consecutive_changes_requested = 0
        history.attempts.append(
            GateAttempt(
                candidate_identity=identity,
                candidate_state=patch.diff_text,
                verification=verification,
                rejected=False,
                rejection_basis=None,
                review_iteration=next_iteration,
                reviewer_verdict=ReviewVerdict.APPROVED,
            )
        )
        current_head = repository.head_sha(config.repo)
        candidate = AcceptedCheckpointCandidate(
            checkpoint=checkpoint,
            gate_context=history.context,
            candidate_identity=identity,
            review_patch=patch,
            verification=verification,
            review_iteration=next_iteration,
        )
        return (
            ReviewVerdict.APPROVED,
            None,
            AcceptedCheckpointEvidence(
                candidate=candidate,
                predecessor_review_boundary_sha=original.predecessor_review_boundary_sha,
                accepted_head_sha=current_head,
                accepted_base_context_identity=current_head,
            ),
            None,
        )

    if review.verdict is ReviewVerdict.CHANGES_REQUESTED and packet is not None:
        history.consecutive_changes_requested += 1
        history.rejected_candidate_identities.add(identity)
        history.attempts.append(
            GateAttempt(
                candidate_identity=identity,
                candidate_state=patch.diff_text,
                verification=verification,
                rejected=True,
                rejection_basis=CandidateRejectionBasis.CHANGES_REQUESTED,
                review_iteration=next_iteration,
                reviewer_verdict=ReviewVerdict.CHANGES_REQUESTED,
                findings=packet.findings,
                repair_packet=packet,
            )
        )
        history.previous_reviewed_candidate_identity = identity
        history.previous_reviewed_candidate_state = patch.diff_text
        if (
            history.consecutive_changes_requested >= 2
            and packet.non_convergence is None
        ):
            raise _Blocked(
                f"replayed {checkpoint.checkpoint_id} second consecutive "
                "CHANGES_REQUESTED omitted non_convergence diagnosis"
            )
        history.latest_valid_repair_packet = packet
        return ReviewVerdict.CHANGES_REQUESTED, packet, None, None

    raise _Blocked(
        review.blocked_reason
        or f"designated reviewer blocked replayed {checkpoint.checkpoint_id}"
    )


def _replay_v2_checkpoints_conservatively(
    config: OrchestratorConfig,
    spec: TaskExecutionSpec,
    originals: tuple[AcceptedCheckpointEvidence, ...],
    evidence: V2ImplementationEvidence,
    repair_acceptor: Callable[[AcceptedImplementationRepairCandidate], str],
) -> tuple[GateHistory, ...]:
    """Replay from CP-1, preserving every original predecessor boundary."""

    histories = {
        item.candidate.checkpoint.checkpoint_id: GateHistory(
            context=GateContext(
                gate_id=f"replay:{item.candidate.checkpoint.checkpoint_id}",
                spec_identity=spec.digest,
                accepted_base_context_identity=item.predecessor_review_boundary_sha,
            )
        )
        for item in originals
    }

    while True:
        evidence.invalidate_from_checkpoint(0)
        restart = False
        for original in originals:
            checkpoint = original.candidate.checkpoint
            history = histories[checkpoint.checkpoint_id]
            verdict, packet, accepted, verification_failure = (
                _review_v2_replayed_checkpoint(
                    config, spec, original, history
                )
            )
            if verdict is ReviewVerdict.APPROVED:
                assert accepted is not None
                evidence.accepted_checkpoints.append(accepted)
                continue

            if verdict is ReviewVerdict.CHANGES_REQUESTED:
                assert packet is not None
            else:
                assert verdict is None
                assert verification_failure is not None
            _, repair_history, _ = _execute_v2_late_repair(
                config,
                spec,
                gate_id=f"replay-repair:{checkpoint.checkpoint_id}",
                accepted_base_context_identity=repository.head_sha(config.repo),
                initial_packet=packet,
                verification_commands=checkpoint.verification,
                repair_acceptor=repair_acceptor,
                initial_verification_failure=verification_failure,
            )
            histories[f"repair:{checkpoint.checkpoint_id}:{len(histories)}"] = (
                repair_history
            )
            # Impact cannot be localized deterministically: discard the
            # repaired gate and every downstream approval, then restart at CP-1.
            evidence.invalidate_from_checkpoint(0)
            restart = True
            break
        if not restart:
            return tuple(histories.values())


def execute_v2_pre_closure_review(
    config: OrchestratorConfig,
    execution_target: ExecutionTarget,
    checkpoint_result: V2CheckpointExecutionResult,
    *,
    repair_acceptor: Callable[[AcceptedImplementationRepairCandidate], str] | None,
    initial_repair_packet: RepairPacket | None = None,
    initial_repair_gate_id: str = "mode-c-implementation-repair",
) -> V2PreClosureExecutionResult:
    """Run CP-3 Full verification, cumulative review, repair, and replay.

    This stops at accepted pre-closure cumulative implementation evidence. It
    deliberately implements no Task Closure or Mode C mechanics.
    """

    spec = execution_target.spec
    current_target = execution_target
    evidence = V2ImplementationEvidence(
        spec_identity=spec.digest,
        base_identity=execution_target.base_sha,
        accepted_checkpoints=list(checkpoint_result.checkpoint_evidence),
    )

    def new_cumulative_history(base_sha: str) -> GateHistory:
        return GateHistory(
            context=GateContext(
                gate_id="pre-closure-cumulative-review",
                spec_identity=spec.digest,
                accepted_base_context_identity=base_sha,
            )
        )

    cumulative_history = new_cumulative_history(execution_target.base_sha)
    replay_histories: list[GateHistory] = []
    terminal_phase = Phase.FULL_VERIFICATION

    def result(completed: bool, reason: str | None = None) -> V2PreClosureExecutionResult:
        return V2PreClosureExecutionResult(
            completed=completed,
            evidence=evidence,
            cumulative_history=cumulative_history,
            replay_histories=tuple(replay_histories),
            blocked_reason=reason,
            terminal_phase=terminal_phase,
        )

    try:
        if execution_target.task.task_id != config.task_id:
            raise _Blocked(
                f"accepted execution target {execution_target.task.task_id} does "
                f"not match invocation task {config.task_id}"
            )
        if spec.task_id != config.task_id:
            raise _Blocked(
                f"fixed spec task {spec.task_id} does not match invocation task "
                f"{config.task_id}"
            )
        if not checkpoint_result.completed:
            raise _Blocked("v2 checkpoints are not all accepted")
        if not spec.checkpoints:
            raise _Blocked("fixed v2 spec declares no checkpoints")
        if len(checkpoint_result.checkpoint_evidence) != len(spec.checkpoints):
            raise _Blocked("accepted checkpoint evidence is incomplete or out of order")
        if tuple(
            item.candidate.checkpoint.checkpoint_id
            for item in checkpoint_result.checkpoint_evidence
        ) != tuple(item.checkpoint_id for item in spec.checkpoints):
            raise _Blocked("accepted checkpoint evidence order differs from fixed spec")
        if any(
            item.candidate.gate_context.spec_identity != spec.digest
            for item in checkpoint_result.checkpoint_evidence
        ):
            raise _Blocked("accepted checkpoint evidence belongs to another fixed spec")
        if (
            checkpoint_result.checkpoint_evidence[-1].accepted_head_sha
            != repository.head_sha(config.repo)
        ):
            raise _Blocked(
                "accepted checkpoint evidence is stale for the current exact HEAD"
            )
        if repair_acceptor is None:
            raise _Blocked(
                "v2 pre-closure repair requires an orchestrator-owned "
                "commit/push acceptance boundary"
            )

        originals = tuple(checkpoint_result.checkpoint_evidence)

        if initial_repair_packet is not None:
            terminal_phase = Phase.ORIGIN_MAIN_REVALIDATION
            current_target, base_moved = _revalidate_v2_execution_target(
                config, execution_target, current_target.base_sha
            )
            if base_moved:
                evidence.base_identity = current_target.base_sha
                cumulative_history = new_cumulative_history(current_target.base_sha)
            evidence.invalidate_from_checkpoint(0)
            terminal_phase = Phase.CHECKPOINT_REVIEW
            _, repair_history, _ = _execute_v2_late_repair(
                config,
                spec,
                gate_id=initial_repair_gate_id,
                accepted_base_context_identity=repository.head_sha(config.repo),
                initial_packet=initial_repair_packet,
                verification_commands=_all_checkpoint_verification_commands(spec),
                repair_acceptor=repair_acceptor,
            )
            replay_histories.append(repair_history)
            replay_histories.extend(
                _replay_v2_checkpoints_conservatively(
                    config, spec, originals, evidence, repair_acceptor
                )
            )

        while True:
            terminal_phase = Phase.ORIGIN_MAIN_REVALIDATION
            revalidated_target, base_moved = _revalidate_v2_execution_target(
                config, execution_target, current_target.base_sha
            )
            current_target = revalidated_target
            if base_moved:
                evidence.base_identity = current_target.base_sha
                evidence.full_verification = None
                evidence.cumulative_review = None
                cumulative_history = new_cumulative_history(current_target.base_sha)

            full = evidence.full_verification
            current_head = repository.head_sha(config.repo)
            if (
                full is None
                or full.head_sha != current_head
                or full.base_identity != current_target.base_sha
            ):
                terminal_phase = Phase.FULL_VERIFICATION
                evidence.full_verification = _run_v2_full_verification(
                    config, spec, current_target.base_sha
                )
                full = evidence.full_verification
            terminal_phase = Phase.PRE_CLOSURE_CUMULATIVE_REVIEW
            patch = repository.build_cumulative_patch_from_base(
                config.repo,
                repository.ReviewPurpose.PRE_CLOSURE_CUMULATIVE_REVIEW,
                current_target.base_sha,
            )
            identity = _candidate_identity(patch.diff_text)
            if identity in cumulative_history.rejected_candidate_identities:
                raise _Blocked(
                    "pre-closure cumulative repair reproduced a rejected candidate"
                )
            review_input = _build_v2_cumulative_review_input(
                spec, patch, full, cumulative_history
            )
            review = _run_v2_designated_review(
                config,
                review_input,
                patch,
                context="pre-closure cumulative review",
            )
            terminal_phase = Phase.ORIGIN_MAIN_REVALIDATION
            post_review_target, base_moved = _revalidate_v2_execution_target(
                config, execution_target, current_target.base_sha
            )
            current_target = post_review_target
            if base_moved:
                # The review belongs to the old base context. Discard it before
                # interpreting even APPROVED, rerun Full verification, rebuild
                # the cumulative range, and invoke a fresh reviewer.
                evidence.base_identity = current_target.base_sha
                evidence.full_verification = None
                evidence.cumulative_review = None
                cumulative_history = new_cumulative_history(current_target.base_sha)
                continue
            terminal_phase = Phase.PRE_CLOSURE_CUMULATIVE_REVIEW
            next_iteration = cumulative_history.review_iteration + 1
            if review.verdict_is_explicit:
                cumulative_history.review_iteration = next_iteration

            packet = review.repair_packet
            if review.verdict is ReviewVerdict.APPROVED:
                terminal_phase = Phase.PRE_CLOSURE_CUMULATIVE_REVIEW
                cumulative_history.consecutive_changes_requested = 0
                cumulative_history.attempts.append(
                    GateAttempt(
                        candidate_identity=identity,
                        candidate_state=patch.diff_text,
                        verification=full.verification,
                        rejected=False,
                        rejection_basis=None,
                        review_iteration=next_iteration,
                        reviewer_verdict=ReviewVerdict.APPROVED,
                    )
                )
                evidence.cumulative_review = V2CumulativeReviewEvidence(
                    spec_identity=spec.digest,
                    base_identity=current_target.base_sha,
                    candidate_identity=identity,
                    reviewed_head_sha=patch.head_sha,
                    review_patch=patch,
                    review_iteration=next_iteration,
                )
                return result(True)

            if review.verdict is ReviewVerdict.CHANGES_REQUESTED and packet is not None:
                cumulative_history.consecutive_changes_requested += 1
                cumulative_history.rejected_candidate_identities.add(identity)
                cumulative_history.attempts.append(
                    GateAttempt(
                        candidate_identity=identity,
                        candidate_state=patch.diff_text,
                        verification=full.verification,
                        rejected=True,
                        rejection_basis=CandidateRejectionBasis.CHANGES_REQUESTED,
                        review_iteration=next_iteration,
                        reviewer_verdict=ReviewVerdict.CHANGES_REQUESTED,
                        findings=packet.findings,
                        repair_packet=packet,
                    )
                )
                cumulative_history.previous_reviewed_candidate_identity = identity
                cumulative_history.previous_reviewed_candidate_state = patch.diff_text
                if (
                    cumulative_history.consecutive_changes_requested >= 2
                    and packet.non_convergence is None
                ):
                    raise _Blocked(
                        "second consecutive cumulative CHANGES_REQUESTED omitted "
                        "non_convergence diagnosis"
                    )
                cumulative_history.latest_valid_repair_packet = packet

                # A cumulative finding does not prove an earliest affected CP.
                # Always choose the approved conservative boundary: CP-1.
                evidence.invalidate_from_checkpoint(0)
                terminal_phase = Phase.CHECKPOINT_REVIEW
                _, repair_history, _ = _execute_v2_late_repair(
                    config,
                    spec,
                    gate_id="pre-closure-cumulative-repair",
                    accepted_base_context_identity=patch.head_sha,
                    initial_packet=packet,
                    verification_commands=_all_checkpoint_verification_commands(spec),
                    repair_acceptor=repair_acceptor,
                )
                replay_histories.append(repair_history)
                replay_histories.extend(
                    _replay_v2_checkpoints_conservatively(
                        config, spec, originals, evidence, repair_acceptor
                    )
                )
                terminal_phase = Phase.FULL_VERIFICATION
                evidence.full_verification = _run_v2_full_verification(
                    config, spec, current_target.base_sha
                )
                # Loop rebuilds origin/main...HEAD and invokes a fresh reviewer.
                continue

            raise _Blocked(
                review.blocked_reason
                or "designated reviewer blocked pre-closure cumulative review"
            )
    except (_Blocked, RepositoryError) as exc:
        evidence.cumulative_review = None
        return result(False, str(exc))


def _v2_repair_is_proven_closure_only(packet: RepairPacket) -> bool:
    """Return true only for explicit, unambiguous canonical closure paths."""

    if not packet.findings:
        return False
    for finding in packet.findings:
        if not finding.affected_paths:
            return False
        paths = {path.replace("\\", "/") for path in finding.affected_paths}
        if not paths or not paths <= _CLOSURE_ALLOWED_FILES:
            return False
    return True


def _build_v2_closure_prompt(
    execution_target: ExecutionTarget,
    pre_closure: V2PreClosureExecutionResult,
    pr_number: str,
    upstream_packet: RepairPacket | None,
    closure_gate_packet: RepairPacket | None,
) -> str:
    cumulative = pre_closure.evidence.cumulative_review
    if cumulative is None:
        raise _Blocked("accepted cumulative evidence is required for Task Closure")
    return (
        f"TASK_EXECUTION_SPEC:\n{execution_target.spec.text}\n"
        "SELECTED_TASK_CONTEXT:\n"
        f"{_selected_task_context(execution_target)}"
        "CURRENT_GATE: prospective Task Closure\n"
        "ROLE: Prepare or repair only the canonical Task Closure content. "
        "In docs/TASK.md insert exactly one terminal row for the selected task: "
        "Status Done, the real draft PR evidence below, and its existing title. "
        "Preserve every other terminal row, order, and evidence; do not create or "
        "select a next task, change another task, or edit/delete any task spec. "
        "Append exactly one concise factual delivery entry to "
        "docs/DEVELOPMENT_LOG.md. Edit docs/ROADMAP.md or docs/DEFERRED.md only "
        "when required by the delivered task. Do not commit, push, merge, or "
        "change implementation files.\n"
        f"DRAFT_PR_NUMBER: {pr_number}\n"
        f"ACCEPTED_IMPLEMENTATION_BASE: {cumulative.base_identity}\n"
        f"ACCEPTED_IMPLEMENTATION_HEAD: {cumulative.reviewed_head_sha}\n"
        f"ACCEPTED_IMPLEMENTATION_PATCH:\n{cumulative.review_patch.diff_text}\n"
        "UPSTREAM_REPAIR_CONTEXT (source only; not a previous Closure Review):\n"
        f"{_repair_packet_json(upstream_packet)}\n"
        "CURRENT_CLOSURE_REVIEW_REPAIR_PACKET:\n"
        f"{_repair_packet_json(closure_gate_packet)}\n"
    )


def _build_v2_closure_review_input(
    execution_target: ExecutionTarget,
    diff_text: str,
    history: GateHistory,
) -> str:
    protocol = _v2_designated_review_protocol(
        "PROSPECTIVE_TASK_CLOSURE",
        (
            "Review only the exact closure candidate diff, its factual closure "
            "evidence, and applicable closure, terminal-registry, and governance "
            "requirements. Do not repeat the full implementation review.\n"
        ),
    )
    contract = _v2_structured_output_contract(
        history.consecutive_changes_requested >= 1
    )
    text = (
        f"TASK_EXECUTION_SPEC:\n{execution_target.spec.text}\n"
        "CURRENT_GATE: prospective Task Closure review\n"
        "REVIEW_PURPOSE: CHECKPOINT (mode A closure candidate)\n"
        f"REVIEW_ITERATION: {history.review_iteration + 1}\n"
        "ROLE: Review only the canonical prospective Task Closure diff. "
        f"{protocol}{contract}"
        f"CURRENT_PATCH:\n{diff_text}\n"
    )
    if history.latest_valid_repair_packet is not None:
        text += (
            "PREVIOUS_REVIEWER_FINDINGS:\n"
            f"{_repair_findings_json(history.latest_valid_repair_packet)}\n"
        )
    if history.previous_reviewed_candidate_state is not None:
        text += (
            "REPAIR_DELTA_SINCE_LAST_REVIEWED_CANDIDATE:\n"
            f"{_repair_delta(history.previous_reviewed_candidate_state, diff_text)}\n"
        )
    return text


def _prepare_v2_unpublished_closure(
    config: OrchestratorConfig,
    execution_target: ExecutionTarget,
    pre_closure: V2PreClosureExecutionResult,
    *,
    pr_number: str,
    expected_published_head: str,
    task_md_baseline: str,
    initial_packet: RepairPacket | None = None,
    strict_closure_only_repair: bool = False,
) -> tuple[
    repository.UnpublishedCommitCandidate,
    GateHistory,
    tuple[str, ...],
]:
    """Adaptively review Task Closure, then create one local-only commit."""

    upstream_packet = initial_packet
    history = GateHistory(
        context=GateContext(
            gate_id="prospective-task-closure",
            spec_identity=execution_target.spec.digest,
            accepted_base_context_identity=expected_published_head,
        )
    )
    while True:
        before = repository.capture_branch_head(config.repo)
        prompt = _build_v2_closure_prompt(
            execution_target,
            pre_closure,
            pr_number,
            upstream_packet,
            history.latest_valid_repair_packet,
        )
        impl_result = run_implementer(config.implementer_spec, prompt)
        repository.verify_branch_head_unchanged(
            config.repo, before, context="v2 Task Closure implementer invocation"
        )
        if impl_result.timed_out or impl_result.returncode != 0:
            raise _Blocked("implementer failed while preparing v2 Task Closure")
        patch = repository.build_checkpoint_patch_uncommitted(config.repo)
        touched = repository.changed_paths(config.repo)
        if strict_closure_only_repair and not set(touched) <= _CLOSURE_ALLOWED_FILES:
            raise _Blocked(
                "supposed closure-only repair changed implementation content; "
                "unsafe narrow continuation is refused"
            )
        _require_canonical_closure_files_touched(touched)
        try:
            task_context.validate_terminal_only_closure(
                task_md_baseline,
                repository.read_worktree_utf8_file_exact(
                    config.repo, "docs/TASK.md"
                ),
                task_id=execution_target.task.task_id,
                pr_number=pr_number,
                title=execution_target.task.title,
            )
        except (RepositoryError, TaskTrackerError) as exc:
            raise _Blocked(f"invalid terminal-only Task Closure: {exc}") from exc
        identity = _candidate_identity(patch.diff_text)
        if identity in history.rejected_candidate_identities:
            raise _Blocked("Task Closure repair reproduced a rejected candidate")
        review_input = _build_v2_closure_review_input(
            execution_target, patch.diff_text, history
        )
        review = _run_v2_designated_review(
            config,
            review_input,
            patch,
            context="v2 Task Closure review",
        )
        next_iteration = history.review_iteration + 1
        if review.verdict_is_explicit:
            history.review_iteration = next_iteration
        packet = review.repair_packet
        if review.verdict is ReviewVerdict.APPROVED:
            history.consecutive_changes_requested = 0
            history.attempts.append(
                GateAttempt(
                    candidate_identity=identity,
                    candidate_state=patch.diff_text,
                    verification=None,
                    rejected=False,
                    rejection_basis=None,
                    review_iteration=next_iteration,
                    reviewer_verdict=ReviewVerdict.APPROVED,
                )
            )
            candidate = repository.create_unpublished_reviewed_commit(
                config.repo,
                reviewed_patch=patch,
                message=(
                    f"{execution_target.task.task_id}: prospective Task Closure "
                    f"(PR #{pr_number})"
                ),
                paths=touched,
                expected_branch=config.delivery_branch,
                expected_published_head=expected_published_head,
            )
            return candidate, history, touched
        if review.verdict is ReviewVerdict.CHANGES_REQUESTED and packet is not None:
            if not _v2_repair_is_proven_closure_only(packet):
                repository.discard_reviewed_uncommitted_candidate(
                    config.repo,
                    reviewed_patch=patch,
                    paths=touched,
                    expected_branch=config.delivery_branch,
                    expected_head=expected_published_head,
                    expected_remote_head=expected_published_head,
                )
                raise _ImplementationRepairRequired(packet)
            history.consecutive_changes_requested += 1
            history.rejected_candidate_identities.add(identity)
            history.attempts.append(
                GateAttempt(
                    candidate_identity=identity,
                    candidate_state=patch.diff_text,
                    verification=None,
                    rejected=True,
                    rejection_basis=CandidateRejectionBasis.CHANGES_REQUESTED,
                    review_iteration=next_iteration,
                    reviewer_verdict=ReviewVerdict.CHANGES_REQUESTED,
                    findings=packet.findings,
                    repair_packet=packet,
                )
            )
            history.previous_reviewed_candidate_identity = identity
            history.previous_reviewed_candidate_state = patch.diff_text
            if (
                history.consecutive_changes_requested >= 2
                and packet.non_convergence is None
            ):
                raise _Blocked(
                    "second consecutive Task Closure CHANGES_REQUESTED omitted "
                    "non_convergence diagnosis"
                )
            history.latest_valid_repair_packet = packet
            upstream_packet = None
            continue
        raise _Blocked(review.blocked_reason or "designated closure reviewer blocked")


def _build_v2_mode_c_review_input(
    execution_target: ExecutionTarget,
    candidate: repository.UnpublishedCommitCandidate,
    patch: repository.ReviewPatch,
    history: GateHistory,
) -> str:
    protocol = _v2_designated_review_protocol(
        "MODE_C_FINAL_CUMULATIVE_AUDIT",
        (
            "Review the full final cumulative candidate — implementation plus "
            "the unpublished Task Closure — against the complete applicable "
            "Task Execution Spec and repository contract, including every "
            "checkpoint, Full verification, and closure/governance boundaries.\n"
        ),
    )
    contract = _v2_structured_output_contract(
        history.consecutive_changes_requested >= 1
    )
    text = (
        f"TASK_EXECUTION_SPEC:\n{execution_target.spec.text}\n"
        "CURRENT_GATE: Mode C final cumulative branch audit\n"
        "REVIEW_PURPOSE: FINAL_CUMULATIVE_AUDIT\n"
        "ROLE: Review the exact local unpublished closure candidate. Report "
        "semantic findings only; the orchestrator chooses every transition. "
        f"{protocol}{contract}"
        f"BASE_SHA: {patch.base_sha}\n"
        f"CANDIDATE_HEAD_SHA: {candidate.candidate_head_sha}\n"
        f"CANDIDATE_TREE_SHA: {candidate.tree_sha}\n"
        f"CURRENT_PATCH:\n{patch.diff_text}\n"
    )
    if history.latest_valid_repair_packet is not None:
        text += (
            "PREVIOUS_REVIEWER_FINDINGS:\n"
            f"{_repair_findings_json(history.latest_valid_repair_packet)}\n"
        )
    if history.previous_reviewed_candidate_state is not None:
        text += (
            "REPAIR_DELTA_SINCE_LAST_REVIEWED_CANDIDATE:\n"
            f"{_repair_delta(history.previous_reviewed_candidate_state, patch.diff_text)}\n"
        )
    return text


def _review_v2_mode_c_candidate(
    config: OrchestratorConfig,
    execution_target: ExecutionTarget,
    candidate: repository.UnpublishedCommitCandidate,
    base_sha: str,
    history: GateHistory,
    *,
    published: bool = False,
) -> tuple[StructuredReviewResult, repository.ReviewPatch]:
    if published:
        repository.verify_published_commit_candidate(
            config.repo,
            candidate,
            expected_branch=config.delivery_branch,
            fetch=False,
        )
    else:
        repository.verify_unpublished_commit_candidate(
            config.repo,
            candidate,
            expected_branch=config.delivery_branch,
            fetch=False,
        )
    patch = repository.build_cumulative_patch_from_base(
        config.repo, repository.ReviewPurpose.FINAL_CUMULATIVE_AUDIT, base_sha
    )
    review_input = _build_v2_mode_c_review_input(
        execution_target, candidate, patch, history
    )
    review = _run_v2_designated_review(
        config,
        review_input,
        patch,
        context="v2 Mode C final cumulative audit",
    )
    return review, patch


def _require_v2_published_candidate_ci(
    config: OrchestratorConfig, pr_number: str, candidate_head_sha: str
) -> None:
    before = repository.pr_head_sha(
        config.repo, pr_number, gh_command=config.gh_command
    )
    if before != candidate_head_sha:
        raise _Blocked("draft PR head does not equal the published audited candidate")
    result = repository.pr_required_checks(
        config.repo, pr_number, gh_command=config.gh_command
    )
    after = repository.pr_head_sha(
        config.repo, pr_number, gh_command=config.gh_command
    )
    if after != candidate_head_sha:
        raise _Blocked("draft PR head moved while required CI was read")
    if result.no_required_checks or result.returncode == 0:
        return
    failing = [item.get("name") for item in result.checks if item.get("bucket") == "fail"]
    if failing:
        raise _Blocked(
            f"required CI failed for the published v2 candidate: {failing!r}; "
            "initial v2 does not perform post-publication candidate repair"
        )
    raise _Blocked("required CI is pending or incomplete for the published candidate")


def _stabilize_v2_published_candidate(
    config: OrchestratorConfig,
    execution_target: ExecutionTarget,
    candidate: repository.UnpublishedCommitCandidate,
    pr_number: str,
    initial_base_sha: str,
    closure_baseline: _V2ClosureMaterialBaseline,
    set_phase: Callable[[Phase], None],
) -> V2ModeCAuditEvidence | None:
    """Keep Mode C fresh through CI without changing the published candidate."""

    base_sha = initial_base_sha
    replacement_audit: V2ModeCAuditEvidence | None = None
    while True:
        set_phase(Phase.REQUIRED_CI)
        _require_v2_published_candidate_ci(config, pr_number, candidate.candidate_head_sha)
        set_phase(Phase.ORIGIN_MAIN_REVALIDATION)
        revalidated, moved = _revalidate_v2_execution_target(
            config, execution_target, base_sha
        )
        if not moved:
            return replacement_audit
        base_sha = revalidated.base_sha
        _require_v2_closure_material_unchanged(
            config.repo, closure_baseline, base_sha
        )
        history = GateHistory(
            context=GateContext(
                gate_id="post-publication-mode-c-replay",
                spec_identity=execution_target.spec.digest,
                accepted_base_context_identity=base_sha,
            )
        )
        while True:
            set_phase(Phase.MODE_C_FINAL_AUDIT)
            review, patch = _review_v2_mode_c_candidate(
                config,
                execution_target,
                candidate,
                base_sha,
                history,
                published=True,
            )
            set_phase(Phase.ORIGIN_MAIN_REVALIDATION)
            post_review_target, moved_after_review = _revalidate_v2_execution_target(
                config, execution_target, base_sha
            )
            if moved_after_review:
                base_sha = post_review_target.base_sha
                _require_v2_closure_material_unchanged(
                    config.repo, closure_baseline, base_sha
                )
                history = GateHistory(
                    context=GateContext(
                        gate_id="post-publication-mode-c-replay",
                        spec_identity=execution_target.spec.digest,
                        accepted_base_context_identity=base_sha,
                    )
                )
                continue
            set_phase(Phase.MODE_C_FINAL_AUDIT)
            if review.verdict is ReviewVerdict.APPROVED:
                replacement_audit = V2ModeCAuditEvidence(
                    base_sha=base_sha,
                    candidate_head_sha=candidate.candidate_head_sha,
                    candidate_tree_sha=candidate.tree_sha,
                    review_patch=patch,
                    review_iteration=1,
                )
                break
            if review.verdict is ReviewVerdict.CHANGES_REQUESTED:
                raise _Blocked(
                    "rebuilt post-publication Mode C requires candidate-changing "
                    "repair; initial v2 blocks instead of rewriting remote history"
                )
            raise _Blocked(
                review.blocked_reason
                or "designated reviewer blocked post-publication Mode C replay"
            )


def execute_v2_unpublished_closure(
    config: OrchestratorConfig,
    execution_target: ExecutionTarget,
    checkpoint_result: V2CheckpointExecutionResult,
    pre_closure_result: V2PreClosureExecutionResult,
    *,
    repair_acceptor: Callable[[AcceptedImplementationRepairCandidate], str],
) -> V2ClosureExecutionResult:
    """Run isolated CP-4: local closure, Mode C, exact publish, required CI."""

    current_pre_closure = pre_closure_result
    current_checkpoint_result = checkpoint_result
    candidate: repository.UnpublishedCommitCandidate | None = None
    accepted_audit: V2ModeCAuditEvidence | None = None
    closure_baseline: _V2ClosureMaterialBaseline | None = None
    pr_url: str | None = None
    published = False
    terminal_phase = Phase.CLOSURE_REVIEW

    def set_phase(value: Phase) -> None:
        nonlocal terminal_phase
        terminal_phase = value

    def outcome(completed: bool, reason: str | None = None) -> V2ClosureExecutionResult:
        return V2ClosureExecutionResult(
            completed=completed,
            published=published,
            pre_closure_result=current_pre_closure,
            closure_candidate=candidate,
            mode_c_evidence=accepted_audit,
            pr_url=pr_url,
            blocked_reason=reason,
            terminal_phase=terminal_phase,
        )

    try:
        if not current_pre_closure.completed:
            raise _Blocked("accepted CP-3 evidence is required before Task Closure")
        cumulative = current_pre_closure.evidence.cumulative_review
        if cumulative is None:
            raise _Blocked("accepted cumulative implementation review is missing")
        if cumulative.reviewed_head_sha != repository.head_sha(config.repo):
            raise _Blocked("accepted implementation evidence is stale before closure")
        implementation_head = cumulative.reviewed_head_sha
        remote_head = repository.fetch_and_capture_remote_branch_sha(
            config.repo, config.delivery_branch
        )
        if remote_head != implementation_head:
            raise _Blocked(
                "remote delivery branch does not contain the accepted implementation HEAD"
            )
        terminal_phase = Phase.DRAFT_PR
        pr_body = (
            "AUTONOMOUS_PR v2 draft; unpublished Task Closure follows Mode C.\n\n"
            "Selected task provenance:\n"
            f"{_selected_task_context(execution_target)}"
        )
        pr_url = repository.create_draft_pull_request(
            config.repo,
            title=f"{execution_target.task.task_id}: {execution_target.task.title}",
            body=pr_body,
            head=config.delivery_branch,
            expected_branch=config.delivery_branch,
            gh_command=config.gh_command,
        )
        pr_number = _extract_pr_number(pr_url)

        pending_closure_packet: RepairPacket | None = None
        strict_closure_only = False
        mode_history: GateHistory | None = None
        mode_history_context: tuple[str, str] | None = None
        while True:
            captured_baseline = _capture_v2_closure_material_baseline(
                config.repo, current_pre_closure.evidence.base_identity
            )
            task_md_baseline = dict(captured_baseline.texts)["docs/TASK.md"]
            if task_md_baseline is None:
                raise _Blocked("authoritative closure baseline has no docs/TASK.md")
            try:
                terminal_phase = Phase.CLOSURE_REVIEW
                candidate, _, closure_touched = _prepare_v2_unpublished_closure(
                    config,
                    execution_target,
                    current_pre_closure,
                    pr_number=pr_number,
                    expected_published_head=implementation_head,
                    task_md_baseline=task_md_baseline,
                    initial_packet=pending_closure_packet,
                    strict_closure_only_repair=strict_closure_only,
                )
                closure_baseline = _select_v2_closure_material_paths(
                    captured_baseline, closure_touched
                )
            except _ImplementationRepairRequired as transition:
                terminal_phase = Phase.CHECKPOINT_REVIEW
                current_pre_closure = execute_v2_pre_closure_review(
                    config,
                    execution_target,
                    current_checkpoint_result,
                    repair_acceptor=repair_acceptor,
                    initial_repair_packet=transition.packet,
                    initial_repair_gate_id="closure-review-implementation-repair",
                )
                if not current_pre_closure.completed:
                    terminal_phase = current_pre_closure.terminal_phase
                    raise _Blocked(
                        current_pre_closure.blocked_reason
                        or "implementation-affecting Closure Review repair failed"
                    ) from transition
                cumulative = current_pre_closure.evidence.cumulative_review
                if cumulative is None:
                    raise _Blocked("replayed CP-3 cumulative evidence is missing")
                current_checkpoint_result = _checkpoint_result_from_evidence(
                    current_checkpoint_result, current_pre_closure.evidence
                )
                implementation_head = cumulative.reviewed_head_sha
                pending_closure_packet = None
                strict_closure_only = False
                mode_history = None
                mode_history_context = None
                continue
            pending_closure_packet = None
            strict_closure_only = False

            while True:
                terminal_phase = Phase.ORIGIN_MAIN_REVALIDATION
                current_target, moved = _revalidate_v2_execution_target(
                    config,
                    execution_target,
                    current_pre_closure.evidence.base_identity,
                )
                if moved:
                    if closure_baseline is None:
                        raise _Blocked(
                            "prepared Task Closure has no authoritative baseline"
                        )
                    _require_v2_closure_material_unchanged(
                        config.repo, closure_baseline, current_target.base_sha
                    )
                    current_pre_closure.evidence.base_identity = current_target.base_sha
                base_sha = current_target.base_sha
                context_key = (base_sha, implementation_head)
                if mode_history is None or mode_history_context != context_key:
                    mode_history = GateHistory(
                        context=GateContext(
                            gate_id="mode-c-final-cumulative-audit",
                            spec_identity=execution_target.spec.digest,
                            accepted_base_context_identity=implementation_head,
                        )
                    )
                    mode_history_context = context_key
                identity = _candidate_identity(
                    repository.build_cumulative_patch_from_base(
                        config.repo,
                        repository.ReviewPurpose.FINAL_CUMULATIVE_AUDIT,
                        base_sha,
                    ).diff_text
                )
                if identity in mode_history.rejected_candidate_identities:
                    raise _Blocked(
                        "Mode C repair reproduced a previously rejected candidate"
                    )
                terminal_phase = Phase.MODE_C_FINAL_AUDIT
                review, patch = _review_v2_mode_c_candidate(
                    config, execution_target, candidate, base_sha, mode_history
                )
                terminal_phase = Phase.ORIGIN_MAIN_REVALIDATION
                post_target, moved_after_review = _revalidate_v2_execution_target(
                    config, execution_target, base_sha
                )
                if moved_after_review:
                    if closure_baseline is None:
                        raise _Blocked(
                            "prepared Task Closure has no authoritative baseline"
                        )
                    _require_v2_closure_material_unchanged(
                        config.repo, closure_baseline, post_target.base_sha
                    )
                    current_pre_closure.evidence.base_identity = post_target.base_sha
                    mode_history = GateHistory(
                        context=GateContext(
                            gate_id="mode-c-final-cumulative-audit",
                            spec_identity=execution_target.spec.digest,
                            accepted_base_context_identity=implementation_head,
                        )
                    )
                    mode_history_context = (
                        post_target.base_sha,
                        implementation_head,
                    )
                    continue
                terminal_phase = Phase.MODE_C_FINAL_AUDIT
                next_iteration = mode_history.review_iteration + 1
                if review.verdict_is_explicit:
                    mode_history.review_iteration = next_iteration
                packet = review.repair_packet
                if review.verdict is ReviewVerdict.APPROVED:
                    mode_history.consecutive_changes_requested = 0
                    mode_history.attempts.append(
                        GateAttempt(
                            candidate_identity=identity,
                            candidate_state=patch.diff_text,
                            verification=None,
                            rejected=False,
                            rejection_basis=None,
                            review_iteration=next_iteration,
                            reviewer_verdict=ReviewVerdict.APPROVED,
                        )
                    )
                    accepted_audit = V2ModeCAuditEvidence(
                        base_sha=base_sha,
                        candidate_head_sha=candidate.candidate_head_sha,
                        candidate_tree_sha=candidate.tree_sha,
                        review_patch=patch,
                        review_iteration=next_iteration,
                    )
                    repository.publish_audited_unpublished_candidate(
                        config.repo,
                        candidate,
                        audited_patch=patch,
                        expected_branch=config.delivery_branch,
                        expected_origin_main_sha=base_sha,
                    )
                    published = True
                    if closure_baseline is None:
                        raise _Blocked(
                            "published Task Closure has no authoritative baseline"
                        )
                    replacement_audit = _stabilize_v2_published_candidate(
                        config,
                        execution_target,
                        candidate,
                        pr_number,
                        base_sha,
                        closure_baseline,
                        set_phase,
                    )
                    if replacement_audit is not None:
                        accepted_audit = replacement_audit
                    return outcome(True)
                if review.verdict is ReviewVerdict.CHANGES_REQUESTED and packet is not None:
                    mode_history.consecutive_changes_requested += 1
                    mode_history.rejected_candidate_identities.add(identity)
                    mode_history.attempts.append(
                        GateAttempt(
                            candidate_identity=identity,
                            candidate_state=patch.diff_text,
                            verification=None,
                            rejected=True,
                            rejection_basis=CandidateRejectionBasis.CHANGES_REQUESTED,
                            review_iteration=next_iteration,
                            reviewer_verdict=ReviewVerdict.CHANGES_REQUESTED,
                            findings=packet.findings,
                            repair_packet=packet,
                        )
                    )
                    mode_history.previous_reviewed_candidate_identity = identity
                    mode_history.previous_reviewed_candidate_state = patch.diff_text
                    if (
                        mode_history.consecutive_changes_requested >= 2
                        and packet.non_convergence is None
                    ):
                        raise _Blocked(
                            "second consecutive Mode C CHANGES_REQUESTED omitted "
                            "non_convergence diagnosis"
                        )
                    mode_history.latest_valid_repair_packet = packet
                    repository.discard_unpublished_commit_candidate(
                        config.repo, candidate, expected_branch=config.delivery_branch
                    )
                    candidate = None
                    accepted_audit = None
                    if _v2_repair_is_proven_closure_only(packet):
                        pending_closure_packet = packet
                        strict_closure_only = True
                        break
                    current_pre_closure = execute_v2_pre_closure_review(
                        config,
                        execution_target,
                        current_checkpoint_result,
                        repair_acceptor=repair_acceptor,
                        initial_repair_packet=packet,
                    )
                    if not current_pre_closure.completed:
                        terminal_phase = current_pre_closure.terminal_phase
                        raise _Blocked(
                            current_pre_closure.blocked_reason
                            or "implementation-affecting Mode C repair failed"
                        )
                    cumulative = current_pre_closure.evidence.cumulative_review
                    if cumulative is None:
                        raise _Blocked("replayed CP-3 cumulative evidence is missing")
                    implementation_head = cumulative.reviewed_head_sha
                    current_checkpoint_result = _checkpoint_result_from_evidence(
                        current_checkpoint_result, current_pre_closure.evidence
                    )
                    mode_history = None
                    mode_history_context = None
                    break
                raise _Blocked(review.blocked_reason or "designated Mode C reviewer blocked")
    except (_Blocked, RepositoryError) as exc:
        return outcome(False, str(exc))


def _require_no_task_md_in_ordinary_checkpoint(touched: tuple[str, ...]) -> None:
    normalized = {path.replace("\\", "/") for path in touched}
    if "docs/TASK.md" in normalized:
        raise _Blocked(
            "the implementation checkpoint diff touches docs/TASK.md; "
            "AUTONOMOUS_PR permits docs/TASK.md mutation only during "
            "prospective Task Closure (AGENTS.md 'Bounded authority'), "
            "never during an ordinary implementation checkpoint or its "
            "repairs"
        )










# --------------------------------------------------------------------------
# Deterministic verification
# --------------------------------------------------------------------------




def _run_verification_commands(
    config: OrchestratorConfig, commands: tuple[tuple[str, ...], ...]
) -> VerificationEvidence:
    """Run exactly the supplied shell-free argv commands.

    Every caller supplies commands from the accepted Task Execution Spec.
    """

    if not commands or any(not command for command in commands):
        raise RepositoryError(
            "deterministic verification requires at least one non-empty argv command"
        )
    fingerprint = repository.capture_fingerprint(config.repo)
    results: list[VerificationCommandResult] = []
    overall_passed = True
    for command in commands:
        result = _run_one_verification_command(config, command)
        repository.verify_fingerprint_unchanged(
            config.repo,
            fingerprint,
            context=f"deterministic verification command {' '.join(command)!r}",
        )
        overall_passed = overall_passed and result.passed
        results.append(result)
    return VerificationEvidence(
        commands=tuple(results), passed=overall_passed, head_sha=fingerprint.head_sha
    )


def _run_one_verification_command(
    config: OrchestratorConfig, command: tuple[str, ...]
) -> VerificationCommandResult:
    try:
        completed = subprocess.run(
            list(command),
            cwd=config.repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=config.verification_timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        return VerificationCommandResult(
            command=command, returncode=-1, stdout="", stderr=str(exc), passed=False
        )
    except subprocess.TimeoutExpired as exc:
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return VerificationCommandResult(
            command=command,
            returncode=-1,
            stdout="",
            stderr=f"verification command timed out: {stderr}",
            passed=False,
        )
    return VerificationCommandResult(
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        passed=completed.returncode == 0,
    )


def _format_verification(evidence: VerificationEvidence) -> str:
    lines = [f"verified_head_sha: {evidence.head_sha}", f"passed: {evidence.passed}"]
    for result in evidence.commands:
        lines.append(
            f"- {' '.join(result.command)!r}: returncode={result.returncode} "
            f"passed={result.passed}"
        )
        if not result.passed:
            lines.append(f"  stdout: {result.stdout.strip()}")
            lines.append(f"  stderr: {result.stderr.strip()}")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# Full verification
# --------------------------------------------------------------------------




# --------------------------------------------------------------------------
# Pre-closure cumulative implementation review / mode C final cumulative audit
# --------------------------------------------------------------------------










# --------------------------------------------------------------------------
# Draft PR
# --------------------------------------------------------------------------






def _extract_pr_number(pr_url: str) -> str:
    match = re.search(r"/pull/(\d+)\s*$", pr_url.strip())
    if match is None:
        raise _Blocked(
            f"could not determine the draft PR number from its URL "
            f"{pr_url!r}; the harness must retain the actual PR number for "
            "prospective Task Closure"
        )
    return match.group(1)


# --------------------------------------------------------------------------
# Prepare for closure / prospective Task Closure / independent closure review
# --------------------------------------------------------------------------








def _require_canonical_closure_files_touched(touched: tuple[str, ...]) -> None:
    """Prospective Task Closure may touch only the canonical closure file
    set ``docs/TASK.md`` §18 defines: ``docs/TASK.md`` and
    ``docs/DEVELOPMENT_LOG.md`` are required every time; ``docs/ROADMAP.md``
    and ``docs/DEFERRED.md`` are optional, included only when this task's
    delivered work legitimately changes Roadmap/Deferred status (the
    designated closure reviewer is responsible for judging whether an
    included optional file is actually justified — this guard only
    enforces the mechanical file-set boundary). No source file, arbitrary
    doc, or governance-contract edit is ever permitted here —
    ``AUTONOMOUS_PR``'s ``docs/TASK.md``-mutation restriction (``AGENTS.md``
    "Bounded authority") is the floor, not the entire closure procedure.
    """

    normalized = {path.replace("\\", "/") for path in touched}
    disallowed = normalized - _CLOSURE_ALLOWED_FILES
    if disallowed:
        raise _Blocked(
            "prospective Task Closure diff touches files outside the "
            f"canonical closure file set {sorted(_CLOSURE_ALLOWED_FILES)!r}: "
            f"{sorted(disallowed)!r}"
        )
    missing_required = _CLOSURE_REQUIRED_FILES - normalized
    if missing_required:
        raise _Blocked(
            "prospective Task Closure diff must touch every required "
            f"canonical closure file {sorted(_CLOSURE_REQUIRED_FILES)!r}; "
            f"missing: {sorted(missing_required)!r}"
        )
