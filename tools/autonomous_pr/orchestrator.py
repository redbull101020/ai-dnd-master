"""Deterministic AUTONOMOUS_PR orchestration primitives.

The public :func:`run` remains the operational v1 lifecycle until TSK-0028's
atomic CP-5 activation. :func:`execute_v2_checkpoints` and
:func:`execute_v2_pre_closure_review` are the isolated CP-2/CP-3
spec-driven/adaptive primitives and are deliberately not wired into that
public path yet.

Drives one already-authorized ``AUTONOMOUS_PR`` invocation through the full
``docs/AUTONOMOUS_PR_HARNESS.md`` §9 / ``AGENTS.md`` "Autonomous flow"
sequence:

    preflight
    -> planning -> independent plan review
    -> delivery branch ready
    -> implementation checkpoint / deterministic verification / checkpoint
       review (bounded repair/re-review as required)
    -> full verification
    -> pre-closure cumulative implementation review (satisfies
       docs/TASK.md §18.1)
    -> draft PR
    -> prospective Task Closure / independent closure review
    -> commit/push closure
    -> fresh origin/main revalidation
    -> mode C final cumulative branch audit
    -> required CI
    -> READY_FOR_HUMAN_MERGE
    -> mandatory STOP

:func:`run` returns :attr:`.model.RunOutcome.STOP` only once every gate
above has actually passed, and :attr:`.model.RunOutcome.BLOCKED` for any
genuine fail-closed terminal condition. It never merges or auto-merges
anything, under any condition, at any phase.

Ownership boundaries this module enforces, not merely documents:

- this module is the only place that decides phase transitions, selects
  the review.patch range, runs deterministic verification, and performs
  commit/push — never the implementer or reviewer process (§4, §15);
- the reviewer is always the orchestrator's own configured
  :class:`.agents.AgentInvocationSpec`, never anything derived from
  implementer output — nothing here ever reads implementer stdout to
  choose or configure the reviewer (§5);
- every value the reviewer needs is passed as literal input text built
  from explicit handoff artifacts (task context, plan, review.patch,
  verification evidence) — never from hidden conversational state (§5, §6,
  §13). What this module can actually guarantee about reviewer freshness is
  narrower than "fresh": every reviewer call is its own separate OS
  subprocess (:func:`.agents.run_agent`); the same orchestrator-owned
  :class:`.agents.AgentInvocationSpec` is reused unchanged call to call,
  never rebuilt or mutated from implementer output; and
  :class:`.agents.AgentInvocationSpec` carries no session/resume-identifier
  field, so nothing here ever creates, receives from the implementer, or
  forwards one. It does **not** and cannot mechanically prove that an
  opaque configured reviewer executable has no session/resume behavior of
  its own (e.g. a CLI that defaults to continuing its last conversation) —
  that a configured reviewer integration is one-shot/fresh-context capable
  is an operator configuration responsibility (see
  :class:`.agents.AgentInvocationSpec`'s docstring), not something this
  provider-neutral module can verify for an arbitrary executable.
  :class:`OrchestratorConfig` does, however, fail closed before any agent
  invocation unless that responsibility was positively discharged as an
  explicit configuration assertion (``reviewer_spec.fresh_context_capable``,
  and neither spec declaring ``has_git_or_github_write_access``) — an
  unset/false declaration is refused rather than silently proceeding with a
  weakened isolation guarantee (§13);
- an implementer invocation during **planning** is checked before/after
  with the strict :func:`.repository.verify_fingerprint_unchanged`
  (branch, HEAD, *and* worktree/index status) — planning is plan
  production, not implementation, so any file/index mutation there is a
  violation, not expected behavior. An implementer invocation during the
  **implementation checkpoint** is checked with the narrower
  :func:`.repository.verify_branch_head_unchanged` (branch/HEAD only),
  since editing working-tree content is its job there. A reviewer
  invocation, at either phase, is always checked with the stricter
  :func:`.repository.verify_fingerprint_unchanged`, since the reviewer is
  never given write access to anything;
- a commit is only ever produced after that exact checkpoint's
  ``review.patch`` was ``APPROVED`` (§7, §8);
- a missing, malformed, ambiguous, or unrecognized reviewer verdict, or a
  reviewer process crash/timeout, is always terminal — :func:`.agents.run_reviewer`
  already collapses all of these to :attr:`.model.ReviewVerdict.BLOCKED`,
  and this module never routes a ``BLOCKED`` verdict into the repair loop
  (§7, §17);
- preflight revalidates the named task against ``docs/TASK.md`` as it
  exists at an exact, freshly captured ``origin/main`` SHA
  (:func:`.repository.fetch_and_capture_origin_main_sha` then
  :func:`.repository.read_file_at_ref` via ``git show <sha>:docs/TASK.md``)
  — never the local working tree or currently checked-out branch, either
  of which can be stale or simply different from ``origin/main`` even
  while clean, and never the mutable ``origin/main`` symbolic ref itself
  (which could resolve to a different commit than the one just validated
  if anything fetched again in between). If ``origin/main`` moves again
  between the accepted plan and delivery-branch creation, the task is
  revalidated a second time against that newly captured SHA and the
  resulting :class:`.model.TaskContext` must compare exactly equal to the
  one the accepted plan was built against — otherwise the run fails closed
  rather than silently carrying on with the old plan against new facts
  (§3, §12). The delivery branch is then created from that exact validated
  SHA (:func:`.repository.create_delivery_branch_from_sha`, which performs
  no fetch of its own) rather than by fetching and resolving
  ``origin/main`` a second time — closing the race a separate
  fetch-then-create step would otherwise leave open, where ``origin/main``
  moving between the two fetches could hand the branch a base commit that
  was never revalidated. The identical exact-SHA-binding pattern is reused
  for both cumulative review ranges below
  (:func:`.repository.build_cumulative_patch_from_base`);
- an empty or whitespace-only plan is never treated as a valid handoff
  artifact: even a successful, fingerprint-clean implementer invocation
  during planning is immediately terminal ``BLOCKED`` if it produced no
  real plan text, and the designated reviewer is never invoked for one;
- ``docs/TASK.md`` may be mutated only by prospective Task Closure
  (:func:`_prospective_task_closure`), never by an ordinary implementation
  checkpoint or its repairs (:func:`_checkpoint_cycle`): every checkpoint
  attempt mechanically refuses a diff that touches ``docs/TASK.md`` before
  the reviewer ever sees it (§ AGENTS.md "Bounded authority");
- prospective Task Closure's diff is mechanically restricted to the
  canonical closure file set ``docs/TASK.md`` §18 actually requires —
  ``docs/TASK.md`` and ``docs/DEVELOPMENT_LOG.md`` (both required every
  time), plus ``docs/ROADMAP.md``/``docs/DEFERRED.md`` (optional, only
  when this task's delivered work legitimately changes Roadmap/Deferred
  status) — never source files, arbitrary docs, or governance-contract
  edits (:func:`_require_canonical_closure_files_touched`). The designated
  closure reviewer remains responsible for judging whether an included
  optional file is actually justified; this guard only enforces the
  mechanical file-set boundary. Within that mechanical boundary, the §18
  tracker reconciliation itself (marking the task Done, Recently completed
  evidence with the real PR number, removing its Open task detail,
  recalculating Next/Hard blockers, Last reviewed, and Next free ID) is
  what the closure implementer/reviewer prompts explicitly authorize and
  require — never "queue traversal" in the sense that remains prohibited,
  which is any task allocation/refinement/decomposition/reselection beyond
  exactly what §18 needs, and never any implementation of the
  newly-selected next Current task. Selecting the next Current is itself
  conditional, never unconditional: it happens only under exactly one of
  two canonical rules, judged against ``CLOSURE_BASELINE_TASK_MD`` (below)
  — an ordinarily eligible, already-executable task qualifying under
  ``docs/TASK.md``'s normal queue/readiness invariants, or the narrow
  ``docs/TASK.md`` §18.1.1 prospective immediate-dependent case (a single
  task whose only not-yet-Done dependency is the task just closed, which
  becomes prospectively Done in this same atomic closure, with every
  other readiness condition already satisfied and no other unfinished
  dependency). Otherwise the closure explicitly leaves ``Current: —``; no
  ineligible Backlog/Blocked/oversized task, and no §18.1.1 candidate with
  any other unfinished dependency, is ever promoted merely to make
  Current non-empty; and no implementation of a §18.1.1-represented task
  begins before this PR actually merges;
- prospective Task Closure's implementer/reviewer handoff includes the
  exact accepted pre-closure cumulative implementation diff, its evidence
  metadata (base SHA, reviewed HEAD SHA, review purpose, accepted status),
  the mandatory deterministic-verification evidence that gated it
  (``docs/AUTONOMOUS_PR_HARNESS.md`` §6), and the exact authoritative
  ``docs/TASK.md`` baseline text closure was prepared against
  (``CLOSURE_BASELINE_TASK_MD``, from ``state.closure_baseline_task_md_text``) —
  :func:`_pre_closure_cumulative_review` retains the accepted
  :class:`.repository.ReviewPatch` on ``state.accepted_implementation_patch``
  (replacing, never merging with, whatever was retained before) and
  :func:`_full_verification` retains ``state.full_verification_evidence``,
  **replayed** after every pre-closure repair commit so it is never stale
  relative to the diff it accompanies (:func:`_format_accepted_implementation_handoff`
  positively asserts the two share the same commit SHA);
  :func:`_format_accepted_implementation_handoff` and
  :func:`_format_closure_baseline_task_md` reproduce all of this literally
  into both prompts so closure preparation/review — including the
  Current/Next/Hard-blocker decision — never depends on hidden
  prior-process state or an independent re-read of ``docs/TASK.md``;
- the pre-closure cumulative implementation review
  (:func:`_pre_closure_cumulative_review`,
  :attr:`.repository.ReviewPurpose.PRE_CLOSURE_CUMULATIVE_REVIEW`) and the
  mode C final cumulative branch audit (:func:`_mode_c_audit`,
  :attr:`.repository.ReviewPurpose.FINAL_CUMULATIVE_AUDIT`) share the
  identical diff *range shape* (an exact base SHA through HEAD) but are
  never conflated: the former runs before Task Closure exists on the
  delivery branch and satisfies ``docs/TASK.md`` §18.1; mode C runs only
  after Task Closure has itself been reviewed, committed, pushed, and
  ``origin/main`` freshly revalidated, so its range necessarily includes
  the closure commit. Each reviewer call states its own ``REVIEW_PURPOSE``
  explicitly rather than leaving the distinction implicit. Both are always
  anchored to an exact, already-revalidated ``origin/main`` SHA
  (:func:`.repository.build_cumulative_patch_from_base`) — never a second,
  independent fetch/resolution of the mutable ``origin/main`` ref;
- once prospective Task Closure has been committed and pushed, this module
  never creates a new implementation checkpoint again in response to mode
  C ``CHANGES_REQUESTED`` or a failing required CI check. The repair
  commit that would require is created *after* full verification,
  pre-closure cumulative acceptance, and closure preparation/review/commit
  — replaying every one of those downstream gates safely is exactly the
  "safe rewind/replay" ``docs/AUTONOMOUS_PR_HARNESS.md`` §16 requires
  before a repair commit may land, and v1 does not attempt it. Both gates
  fail closed instead, explicitly, rather than inventing a force-push,
  history-rewrite, or hidden closure-reconstruction recovery, or silently
  treating the old closure review as though it had covered a later
  implementation change. (Bounded repair remains fully supported *before*
  closure is committed: the checkpoint cycle itself, and a
  ``CHANGES_REQUESTED`` pre-closure cumulative review, both still repair
  and re-review normally.);
- immediately before prospective Task Closure begins, if ``origin/main``
  has moved since the pre-closure cumulative review was last accepted,
  that evidence is stale and is rebuilt/re-reviewed against the new exact
  SHA before closure proceeds (:func:`_prepare_for_closure`). The exact
  authoritative ``docs/TASK.md`` text at that point becomes the closure
  baseline;
- post-closure revalidation proves more than "this task's own parsed
  :class:`.model.TaskContext` is unchanged": prepared Task Closure can also
  depend on Current position, Next ordering, Hard blockers, Roadmap scope,
  or other tracker facts a narrower per-task check would miss. So, in
  addition to the existing named-task revalidation,
  :func:`_revalidate_closure_relevant_state` requires the *entire*
  authoritative ``docs/TASK.md`` text to compare byte-identical to the
  closure baseline whenever ``origin/main`` has moved — any
  ``docs/TASK.md`` movement on ``origin/main`` after closure preparation is
  conservatively treated as potentially closure-material in v1 (no
  semantic reconciliation is attempted); unrelated non-``docs/TASK.md``
  ``origin/main`` movement (README, source, etc.) does not by itself block;
- a completed mode C audit becomes stale the instant anything commits,
  rebases, or moves ``origin/main`` afterward, with no materiality
  exception (``AGENTS.md`` "review.patch and diff ranges"). Immediately
  after required CI passes, this module re-fetches ``origin/main`` once
  more and, if it moved again, rebuilds/re-reviews mode C (and re-checks
  CI) against the new state before proceeding — bounded to a small fixed
  number of replay rounds (:func:`_post_closure_gate`); if ``origin/main``
  keeps moving faster than that can stabilize, the run fails closed rather
  than looping forever or declaring ``READY_FOR_HUMAN_MERGE`` against
  evidence that might already be stale again.
  :func:`_verify_mode_c_still_fresh` separately fails closed if anything
  ever moved ``HEAD`` past the exact commit the accepted mode C audit
  covers;
- required CI (:func:`_required_ci`) checks
  :func:`.repository.pr_required_checks` exactly once, restricted to
  GitHub-required checks (``--required`` — an unrelated optional check can
  never block or satisfy this gate), and never polls/sleeps waiting for it
  to finish. It positively binds the checks it reads to the exact commit
  this run pushed: :func:`.repository.pr_head_sha` (``gh pr view --json
  headRefOid``) must equal ``state.head_sha`` both immediately before and
  immediately after the checks read (:func:`_require_pr_head_matches_closure_commit`)
  — checks for a different PR head, or a head that moved during the read
  itself, are never accepted as evidence for this closure commit. A
  positively recognized "no required checks configured for this PR"
  result satisfies the gate (an empty required set has nothing left to
  block on) but is never inferred from an ordinary empty or ambiguous
  checks body — see :class:`.repository.RequiredChecksResult`. A
  still-pending result (nothing failing, but not everything passing yet)
  fails closed rather than blocking the process indefinitely, consistent
  with this module's "no implicit resume" design — the existing delivery
  branch/PR is never treated as resumable run state, only as descriptive
  context; a fresh, separate, explicit invocation is what actually
  re-checks once CI has finished;
- run state (:class:`_RunState`) and handoff artifacts
  (:class:`RunArtifacts`) live only for the lifetime of one :func:`run`
  call. There is no ``run.json``, database, or other persisted schema, and
  nothing here ever infers permission to resume a prior run from repository
  state (an existing branch, an existing artifacts directory) — every call
  to :func:`run` starts a brand-new :class:`_RunState` and a brand-new
  temporary artifacts directory (§9, §11).
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from . import repository, task_context
from .agents import (
    AgentInvocationSpec,
    run_implementer,
    run_reviewer,
    run_structured_reviewer,
)
from .model import (
    AgentRole,
    CandidateIdentity,
    CandidateRejectionBasis,
    ExecutionCheckpoint,
    ExecutionTarget,
    GateAttempt,
    GateContext,
    GateHistory,
    Phase,
    RepairPacket,
    ReviewResult,
    ReviewVerdict,
    RunOutcome,
    RunResult,
    TaskContext,
    TaskExecutionSpec,
    VerificationCommandResult,
    VerificationEvidence,
)
from .repository import RepositoryError
from .task_context import TaskPreflightError, TaskRevalidationError

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

    Nothing here is ever derived from implementer output. ``max_repairs`` is
    a small finite implementation-level value, not a canonical numeric
    governance limit (``docs/AUTONOMOUS_PR_HARNESS.md`` §11, §19) — callers
    may tune it.

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
    verification_commands: tuple[tuple[str, ...], ...]
    delivery_branch: str
    max_repairs: int = 2
    verification_timeout_seconds: float = 600.0
    gh_command: tuple[str, ...] = ("gh",)

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
        if self.max_repairs < 0:
            raise ValueError("OrchestratorConfig.max_repairs must be >= 0")
        if not self.verification_commands:
            raise ValueError(
                "OrchestratorConfig.verification_commands must contain at "
                "least one command; an empty deterministic-verification set "
                "is never treated as vacuously passed"
            )
        for command in self.verification_commands:
            if not command:
                raise ValueError(
                    "OrchestratorConfig.verification_commands must not "
                    "contain an empty command"
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


@dataclass
class RunArtifacts:
    """Explicit, inspectable handoff artifacts for one live run.

    A plain directory of named text files, not a schema or a resumable
    store: nothing reads this directory back to reconstruct run state, and
    no file in it is named or indexed in a way that would let a later
    process treat it as something to resume from
    (``docs/AUTONOMOUS_PR_HARNESS.md`` §11).
    """

    directory: Path

    @classmethod
    def create(cls) -> "RunArtifacts":
        return cls(directory=Path(tempfile.mkdtemp(prefix="autonomous_pr_run_")))

    def write(self, name: str, content: str) -> Path:
        path = self.directory / name
        path.write_text(content, encoding="utf-8")
        return path


@dataclass
class _RunState:
    """The minimum in-memory facts for one live run (§9).

    Mutated only inside :func:`run` and the phase helpers it calls
    directly; never persisted, never read back from a prior process.
    """

    task_id: str
    phase: Phase = Phase.PREFLIGHT
    origin_main_sha: str | None = None
    base_sha: str | None = None
    delivery_branch: str | None = None
    head_sha: str | None = None
    repair_count: int = 0
    outcome: RunOutcome | None = None
    pr_url: str | None = None
    pr_number: str | None = None
    # The exact authoritative docs/TASK.md text prospective Task Closure
    # was prepared against — set by _prepare_for_closure immediately before
    # closure begins, compared against on every post-closure revalidation
    # (_revalidate_closure_relevant_state).
    closure_baseline_task_md_text: str | None = None
    mode_c_base_sha: str | None = None
    mode_c_head_sha: str | None = None
    # Explicit deterministic-verification evidence for the mandatory
    # verification gate (§6) -- set by _full_verification, once verified
    # green, and handed to prospective Task Closure so closure preparation
    # never depends on hidden prior-process state.
    full_verification_evidence: VerificationEvidence | None = None
    # The accepted pre-closure cumulative implementation review.patch --
    # set by _pre_closure_cumulative_review on APPROVED, and replaced (not
    # merely re-set) every time origin/main staleness forces
    # _prepare_for_closure to rebuild/re-review it. This is the exact
    # accepted implementation diff docs/AUTONOMOUS_PR_HARNESS.md §6
    # requires prospective Task Closure's handoff to include.
    accepted_implementation_patch: repository.ReviewPatch | None = None


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


def run(config: OrchestratorConfig) -> RunResult:
    """Execute the full AUTONOMOUS_PR orchestration for one already-
    authorized task.

    Always returns a :class:`.model.RunResult` — an expected fail-closed
    condition (task revalidation failure, a repository invariant violation,
    a terminal reviewer verdict, an exhausted repair budget) is reported as
    ``outcome=RunOutcome.BLOCKED`` rather than raised, matching this
    package's existing style of representing expected failure as data
    (``agents.AgentInvocationResult``) rather than exceptions. An
    unexpected/programmer-error exception (e.g. a misconfigured
    :class:`OrchestratorConfig`, already rejected in ``__post_init__``) is
    not caught here and propagates normally. ``outcome=RunOutcome.STOP`` is
    returned only once every phase below has actually completed.
    """

    artifacts = RunArtifacts.create()
    state = _RunState(task_id=config.task_id)
    try:
        task_ctx = _preflight(config, artifacts, state)
        plan_text = _planning(config, artifacts, state, task_ctx)
        task_ctx = _delivery_branch_ready(config, artifacts, state, task_ctx)
        _checkpoint_cycle(config, artifacts, state, task_ctx, plan_text)

        _full_verification(config, artifacts, state)

        task_ctx, pre_closure_sha = _revalidate_against_fresh_origin_main(
            config, artifacts, state, task_ctx, label="pre_closure"
        )
        _pre_closure_cumulative_review(
            config, artifacts, state, task_ctx, plan_text, pre_closure_sha
        )
        pr_number = _draft_pr(config, artifacts, state, task_ctx)

        task_ctx = _prepare_for_closure(config, artifacts, state, task_ctx, plan_text)
        _require_delivery_head_matches_accepted_evidence(config, state)
        _prospective_task_closure(
            config, artifacts, state, task_ctx, plan_text, pr_number
        )

        _post_closure_gate(config, artifacts, state, task_ctx, plan_text)
        _verify_mode_c_still_fresh(config, state)

        return _ready_for_human_merge_result(config, artifacts, state)
    except (_Blocked, RepositoryError, TaskRevalidationError) as exc:
        return _blocked_result(config, artifacts, state, reason=str(exc))


def _blocked_result(
    config: OrchestratorConfig, artifacts: RunArtifacts, state: _RunState, *, reason: str
) -> RunResult:
    artifacts.write("blocked_reason.txt", reason)
    return RunResult(
        task_id=config.task_id,
        phase=state.phase,
        outcome=RunOutcome.BLOCKED,
        delivery_branch=state.delivery_branch,
        head_sha=state.head_sha,
        repair_count=state.repair_count,
        blocked_reason=reason,
        artifacts_dir=artifacts.directory,
        pr_url=state.pr_url,
    )


def _ready_for_human_merge_result(
    config: OrchestratorConfig, artifacts: RunArtifacts, state: _RunState
) -> RunResult:
    state.phase = Phase.READY_FOR_HUMAN_MERGE
    artifacts.write(
        "ready_for_human_merge.txt",
        f"pr_url: {state.pr_url}\nhead_sha: {state.head_sha}\n",
    )
    return RunResult(
        task_id=config.task_id,
        phase=Phase.READY_FOR_HUMAN_MERGE,
        outcome=RunOutcome.STOP,
        delivery_branch=state.delivery_branch,
        head_sha=state.head_sha,
        repair_count=state.repair_count,
        blocked_reason=None,
        artifacts_dir=artifacts.directory,
        pr_url=state.pr_url,
    )


# --------------------------------------------------------------------------
# Preflight
# --------------------------------------------------------------------------


def _preflight(
    config: OrchestratorConfig, artifacts: RunArtifacts, state: _RunState
) -> TaskContext:
    state.phase = Phase.PREFLIGHT
    origin_main_sha = repository.fetch_and_capture_origin_main_sha(config.repo)
    if not repository.is_worktree_clean(config.repo):
        raise _Blocked(
            "working tree/index is not clean before preflight; refusing to "
            "start a new AUTONOMOUS_PR run against an already-dirty "
            "workspace"
        )
    # Anchored to the exact captured SHA, never the mutable "origin/main"
    # symbolic ref, so this read can never observe a different commit than
    # the one origin_main_sha above just captured.
    queue_text = task_context.load_task_queue_text_at_ref(config.repo, origin_main_sha)
    task_ctx = _revalidate_or_blocked(queue_text, config.task_id)
    state.origin_main_sha = origin_main_sha
    artifacts.write(
        "task_context.txt", _format_task_context(task_ctx, origin_main_sha)
    )
    return task_ctx


def _revalidate_or_blocked(queue_text: str, task_id: str) -> TaskContext:
    try:
        return task_context.revalidate_current_task(queue_text, task_id)
    except TaskRevalidationError as exc:
        raise _Blocked(f"task revalidation failed: {exc}") from exc


def _format_task_context(task_ctx: TaskContext, origin_main_sha: str) -> str:
    depends_on = ", ".join(task_ctx.depends_on) if task_ctx.depends_on else "(none)"
    return (
        f"task_id: {task_ctx.task_id}\n"
        f"origin_main_sha: {origin_main_sha}\n"
        f"status: {task_ctx.status.value}\n"
        f"roadmap_target: {task_ctx.roadmap_target}\n"
        f"depends_on: {depends_on}\n"
        "authoritative_detail:\n"
        f"{task_ctx.detail_text}\n"
    )


# --------------------------------------------------------------------------
# Planning + independent plan review
# --------------------------------------------------------------------------


def _planning(
    config: OrchestratorConfig,
    artifacts: RunArtifacts,
    state: _RunState,
    task_ctx: TaskContext,
) -> str:
    state.phase = Phase.PLANNING
    previous_findings: str | None = None

    for attempt in range(config.max_repairs + 1):
        fingerprint = repository.capture_fingerprint(config.repo)
        prompt = _build_plan_prompt(task_ctx, attempt, previous_findings)
        impl_result = run_implementer(config.implementer_spec, prompt)
        repository.verify_fingerprint_unchanged(
            config.repo, fingerprint, context="implementer invocation (planning)"
        )
        if impl_result.timed_out or impl_result.returncode != 0:
            raise _Blocked(
                f"implementer failed to produce a plan (attempt {attempt}): "
                f"returncode={impl_result.returncode!r} "
                f"timed_out={impl_result.timed_out!r}"
            )
        plan_text = impl_result.stdout
        artifacts.write(f"plan_attempt_{attempt}.txt", plan_text)
        if not plan_text.strip():
            raise _Blocked(
                f"implementer returned an empty/whitespace-only plan "
                f"(attempt {attempt}); an absent plan is never a valid "
                "handoff artifact, and the designated reviewer is not "
                "invoked for one"
            )

        state.phase = Phase.PLAN_REVIEW
        review_input = _build_plan_review_input(task_ctx, plan_text)
        fingerprint = repository.capture_fingerprint(config.repo)
        review_result = run_reviewer(config.reviewer_spec, review_input)
        repository.verify_fingerprint_unchanged(
            config.repo, fingerprint, context="plan review"
        )
        artifacts.write(f"plan_review_attempt_{attempt}.txt", _format_review(review_result))

        if review_result.verdict is ReviewVerdict.APPROVED:
            state.phase = Phase.PLANNING
            return plan_text
        if review_result.verdict is ReviewVerdict.CHANGES_REQUESTED:
            if attempt == config.max_repairs:
                raise _Blocked(
                    "plan repair budget exhausted without an APPROVED "
                    "designated-reviewer verdict"
                )
            state.repair_count += 1
            previous_findings = review_result.findings
            continue
        raise _Blocked(
            f"designated reviewer returned {review_result.verdict.value} for "
            f"the plan: {review_result.findings}"
        )

    raise _Blocked("plan repair budget exhausted")  # pragma: no cover - defensive


def _build_plan_prompt(
    task_ctx: TaskContext, attempt: int, previous_findings: str | None
) -> str:
    return (
        f"TASK_ID: {task_ctx.task_id}\n"
        f"ATTEMPT: {attempt}\n"
        "ROLE: Produce an implementation plan for this task, strictly "
        "within the already-approved scope of the authoritative task "
        "detail below. Do not expand scope. Do not rely on independently "
        "re-reading docs/TASK.md from the repository; the exact "
        "authoritative detail is reproduced here.\n"
        "TASK_DETAIL:\n"
        f"{task_ctx.detail_text}\n"
        f"PREVIOUS_REVIEWER_FINDINGS:\n{previous_findings or '(none)'}\n"
    )


def _build_plan_review_input(task_ctx: TaskContext, plan_text: str) -> str:
    return (
        f"TASK_ID: {task_ctx.task_id}\n"
        "ROLE: Review the following implementation plan against the "
        "authoritative task detail below. Respond with exactly one of "
        "APPROVED, CHANGES_REQUESTED, or BLOCKED on its own line.\n"
        "TASK_DETAIL:\n"
        f"{task_ctx.detail_text}\n"
        "PLAN:\n"
        f"{plan_text}\n"
    )


def _format_review(result: ReviewResult) -> str:
    return f"verdict: {result.verdict.value}\nfindings:\n{result.findings}\n"


# --------------------------------------------------------------------------
# Delivery branch ready
# --------------------------------------------------------------------------


def _delivery_branch_ready(
    config: OrchestratorConfig,
    artifacts: RunArtifacts,
    state: _RunState,
    task_ctx: TaskContext,
) -> TaskContext:
    """Revalidate against a freshly captured ``origin/main`` SHA, then
    create the delivery branch from exactly that same SHA.

    These two steps deliberately share exactly one fetch
    (:func:`_revalidate_against_fresh_origin_main` is the only caller of
    :func:`.repository.fetch_and_capture_origin_main_sha` in this
    function), and branch creation
    (:func:`.repository.create_delivery_branch_from_sha`) never fetches or
    re-resolves ``origin/main`` itself. This closes the race a two-fetch
    design would otherwise have: under a design where revalidation fetches
    once and branch creation fetches again independently, ``origin/main``
    moving in between would let the branch get created from a commit that
    was never revalidated. Anchoring branch creation to the exact SHA this
    function already positively validated makes that impossible.
    """

    state.phase = Phase.DELIVERY_BRANCH_READY
    task_ctx, base_sha = _revalidate_against_fresh_origin_main(
        config, artifacts, state, task_ctx, label="pre_branch_creation"
    )
    repository.create_delivery_branch_from_sha(
        config.repo, config.delivery_branch, base_sha
    )
    state.delivery_branch = config.delivery_branch
    state.base_sha = base_sha
    state.head_sha = repository.head_sha(config.repo)
    artifacts.write(
        "repository_context.txt", _format_repository_context(state=state)
    )
    return task_ctx


def _format_repository_context(
    *, state: _RunState, head_sha_override: str | None = None
) -> str:
    """Explicit branch/base/HEAD repository-context text.

    Shared by the ``repository_context.txt`` artifact and the
    implementation-checkpoint/checkpoint-review handoff prompts (§6), so
    the implementer/reviewer never have to infer which branch/commit they
    are working against. ``head_sha_override`` lets checkpoint review
    report the exact reviewed HEAD (:attr:`.repository.ReviewPatch.head_sha`)
    rather than ``state.head_sha``, which is only the same value before any
    checkpoint commit has landed.
    """

    head_sha = head_sha_override if head_sha_override is not None else state.head_sha
    return (
        f"delivery_branch: {state.delivery_branch}\n"
        f"base_sha: {state.base_sha}\n"
        f"head_sha: {head_sha}\n"
    )


def _revalidate_against_fresh_origin_main(
    config: OrchestratorConfig,
    artifacts: RunArtifacts,
    state: _RunState,
    task_ctx: TaskContext,
    *,
    label: str,
) -> tuple[TaskContext, str]:
    """Fail closed if ``origin/main`` moved since the last revalidation in
    a way that invalidates the already-accepted plan/implementation;
    otherwise return the exact, already-fetched SHA the caller must anchor
    its next step to.

    Called at more than one point in the flow (before delivery-branch
    creation, before the pre-closure cumulative review, immediately before
    closure preparation, and at the start of every post-closure gate round)
    — ``label`` names the call site so each gets its own artifact file
    rather than overwriting a shared one. This performs the single fetch
    for its own decision (:func:`.repository.fetch_and_capture_origin_main_sha`)
    and, if ``origin/main`` has moved since ``state.origin_main_sha`` was
    last recorded, re-reads ``docs/TASK.md`` from that exact new SHA
    (never the mutable ``origin/main`` ref) and revalidates the named task
    again, requiring the resulting :class:`.model.TaskContext` to compare
    exactly equal to the one already in hand (status, roadmap target,
    dependencies, and the full authoritative detail text) — the most
    positive form of "unchanged enough to still be valid" this module can
    mechanically establish. Unrelated ``origin/main`` movement (any change
    that leaves this task's authoritative detail byte-identical) is not
    itself a reason to block. The returned SHA is exactly the one this
    function just validated against — the caller must anchor its next step
    to it directly, never by fetching or resolving ``origin/main`` again.
    """

    current_sha = repository.fetch_and_capture_origin_main_sha(config.repo)
    if current_sha == state.origin_main_sha:
        return task_ctx, current_sha

    previous_sha = state.origin_main_sha
    fresh_text = task_context.load_task_queue_text_at_ref(config.repo, current_sha)
    try:
        fresh_ctx = task_context.revalidate_current_task(fresh_text, config.task_id)
    except TaskRevalidationError as exc:
        raise _Blocked(
            f"origin/main moved from {previous_sha!r} to {current_sha!r} "
            f"since the last revalidation ({label}), and the task is no "
            f"longer a valid execution target on the fresh origin/main: "
            f"{exc}"
        ) from exc

    if fresh_ctx != task_ctx:
        raise _Blocked(
            f"origin/main moved from {previous_sha!r} to {current_sha!r} "
            f"since the last revalidation ({label}), and the authoritative "
            "task context changed since the accepted plan/implementation "
            "was produced/reviewed; safe continuation can no longer be "
            "positively established"
        )

    state.origin_main_sha = current_sha
    artifacts.write(
        f"origin_main_revalidation_{label}.txt",
        f"origin/main moved from {previous_sha} to {current_sha}; "
        "authoritative task context confirmed unchanged\n",
    )
    return fresh_ctx, current_sha


def _revalidate_closure_relevant_state(
    config: OrchestratorConfig,
    artifacts: RunArtifacts,
    state: _RunState,
    task_ctx: TaskContext,
    *,
    label: str,
) -> tuple[TaskContext, str]:
    """Post-closure revalidation must prove more than "this task's own
    parsed :class:`.model.TaskContext` is unchanged": a prepared Task
    Closure can also depend on Current position, Next ordering, Hard
    blockers, Roadmap scope, or other tracker facts a narrower per-task
    check would miss.

    Reuses :func:`_revalidate_against_fresh_origin_main` for the existing
    named-task-level check (one fetch, shared with this function), then —
    only when ``origin/main`` actually moved — additionally requires the
    *entire* authoritative ``docs/TASK.md`` text to compare byte-identical
    to the exact text closure was prepared against
    (``state.closure_baseline_task_md_text``, set by
    :func:`_prepare_for_closure`). This is intentionally conservative: any
    ``docs/TASK.md`` movement on ``origin/main`` after closure preparation
    is treated as potentially closure-material in v1, with no semantic
    reconciliation attempted. Unrelated non-``docs/TASK.md`` ``origin/main``
    movement (README, source, etc.) does not by itself block.
    """

    previous_sha = state.origin_main_sha
    task_ctx, sha = _revalidate_against_fresh_origin_main(
        config, artifacts, state, task_ctx, label=label
    )
    if sha != previous_sha:
        if state.closure_baseline_task_md_text is None:
            raise _Blocked(
                "no closure-baseline authoritative docs/TASK.md text is on "
                "record; post-closure revalidation cannot proceed without "
                "the baseline _prepare_for_closure must set first"
            )
        fresh_task_md_text = task_context.load_task_queue_text_at_ref(
            config.repo, sha
        )
        if fresh_task_md_text != state.closure_baseline_task_md_text:
            raise _Blocked(
                "authoritative docs/TASK.md changed on origin/main since "
                "prospective Task Closure was prepared (Current position, "
                "Next, Hard blockers, Roadmap scope, or another tracker "
                "fact may have moved); prepared closure requires "
                "reconciliation against changed tracker state, which this "
                "module does not attempt automatically"
            )
    return task_ctx, sha


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
    contract = _v2_structured_output_contract(require_non_convergence)
    text = (
        f"TASK_EXECUTION_SPEC:\n{spec.text}\n"
        "CURRENT_GATE:\n"
        f"checkpoint_id: {checkpoint.checkpoint_id}\n"
        f"name: {checkpoint.name}\n"
        f"review_focus: {checkpoint.review_focus}\n"
        f"REVIEW_ITERATION: {review_iteration}\n"
        "ROLE: Review this checkpoint in a fresh, independent context. "
        f"{contract}"
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
        "contain these non-empty string fields: problem, evidence, "
        "required_outcome, recommended_repair, verification_focus. "
        "affected_paths is optional metadata and never replaces a required "
        "field.\n"
        "MACHINE_READABLE_OUTPUT_CONTRACT:\n"
        "finding_required_fields: problem, evidence, required_outcome, "
        "recommended_repair, verification_focus\n"
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
) -> str:
    """Current repository facts for one v2 implementer invocation.

    ``branch_head`` is captured immediately before the invocation and reused
    by the post-invocation mutation guard. This keeps the explicit handoff and
    the enforced repository boundary tied to the same actual state, including
    repairs and the first checkpoint after an accepted commit/push transition.
    """

    return (
        f"delivery_branch: {branch_head.branch}\n"
        f"accepted_base_context_identity: {accepted_base_context_identity}\n"
        f"head_sha: {branch_head.head_sha}\n"
    )


def execute_v2_checkpoints(
    config: OrchestratorConfig,
    spec: TaskExecutionSpec,
    *,
    accepted_base_context_identity: str,
    checkpoint_acceptor: Callable[[AcceptedCheckpointCandidate], str] | None,
) -> V2CheckpointExecutionResult:
    """Execute the fixed spec's checkpoint gates in declared order.

    This is the CP-2 primitive, intentionally separate from legacy :func:`run`.
    It has no numeric repair budget and never reads ``config.max_repairs``.
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

    def blocked(reason: str) -> V2CheckpointExecutionResult:
        return V2CheckpointExecutionResult(
            completed=False,
            accepted_candidates=tuple(accepted),
            gate_histories=tuple(histories),
            blocked_reason=reason,
            checkpoint_evidence=tuple(checkpoint_evidence),
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
            before = repository.capture_branch_head(config.repo)
            repository_context_text = _format_v2_repository_context(
                before, context.accepted_base_context_identity
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
            fingerprint = repository.capture_fingerprint(config.repo)
            review = run_structured_reviewer(config.reviewer_spec, review_input)
            try:
                repository.verify_fingerprint_unchanged(
                    config.repo, fingerprint, context="v2 checkpoint review"
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

    return (
        revalidated.task == accepted.task
        and revalidated.spec.digest == accepted.spec.digest
        and revalidated.spec.text == accepted.spec.text
    )


def _revalidate_v2_execution_target(
    config: OrchestratorConfig,
    accepted: ExecutionTarget,
    current_base_sha: str,
) -> tuple[ExecutionTarget, bool]:
    """Freshly capture origin/main and revalidate a moved exact base.

    An unchanged SHA needs no second read. A moved SHA is loaded through the
    Group-2 exact-base primitives, preflighted again, and accepted only when
    every §30 load-bearing fact is unchanged. The returned boolean records a
    base-context transition; callers must invalidate cumulative evidence and
    gate history before using it.
    """

    fresh_sha = repository.fetch_and_capture_origin_main_sha(config.repo)
    if fresh_sha == current_base_sha:
        return ExecutionTarget(
            base_sha=fresh_sha, task=accepted.task, spec=accepted.spec
        ), False
    try:
        exact_input = task_context.load_exact_base_input(
            config.repo, accepted.task.task_id, fresh_sha
        )
        revalidated = task_context.preflight_execution_target(
            exact_input, accepted.task.task_id
        )
    except TaskPreflightError as exc:
        raise _Blocked(
            "origin/main moved and v2 execution-target revalidation failed: "
            f"{exc}"
        ) from exc
    if not _same_v2_execution_target(accepted, revalidated):
        raise _Blocked(
            "origin/main moved and changed the accepted v2 execution target "
            "(authoritative task entry or fixed spec)"
        )
    return revalidated, True


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
    contract = _v2_structured_output_contract(
        history.consecutive_changes_requested >= 1
    )
    text = (
        f"TASK_EXECUTION_SPEC:\n{spec.text}\n"
        "CURRENT_GATE: pre-closure cumulative implementation review\n"
        "REVIEW_PURPOSE: PRE_CLOSURE_CUMULATIVE_REVIEW\n"
        "RANGE: origin/main...HEAD before Task Closure; this is not Mode C and "
        "satisfies docs/TASK.md §18.1's implementation-diff review prerequisite.\n"
        f"REVIEW_ITERATION: {history.review_iteration + 1}\n"
        "ROLE: Review the complete implementation diff in a fresh, independent "
        f"context. {contract}"
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
    contract = _v2_structured_output_contract(
        history.consecutive_changes_requested >= 1
    )
    text = (
        f"TASK_EXECUTION_SPEC:\n{spec.text}\n"
        f"CURRENT_GATE: {gate_id}\n"
        "REVIEW_PURPOSE: CHECKPOINT (mode A implementation repair)\n"
        f"REVIEW_ITERATION: {history.review_iteration + 1}\n"
        "ROLE: Review this implementation repair in a fresh, independent "
        f"context. {contract}"
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
                before, history.context.accepted_base_context_identity
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
        fingerprint = repository.capture_fingerprint(config.repo)
        review = run_structured_reviewer(config.reviewer_spec, review_input)
        repository.verify_fingerprint_unchanged(
            config.repo, fingerprint, context=f"{gate_id} review"
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
    fingerprint = repository.capture_fingerprint(config.repo)
    review = run_structured_reviewer(config.reviewer_spec, review_input)
    repository.verify_fingerprint_unchanged(
        config.repo, fingerprint, context=f"replayed {checkpoint.checkpoint_id} review"
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

    def result(completed: bool, reason: str | None = None) -> V2PreClosureExecutionResult:
        return V2PreClosureExecutionResult(
            completed=completed,
            evidence=evidence,
            cumulative_history=cumulative_history,
            replay_histories=tuple(replay_histories),
            blocked_reason=reason,
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

        while True:
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
                evidence.full_verification = _run_v2_full_verification(
                    config, spec, current_target.base_sha
                )
                full = evidence.full_verification
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
            fingerprint = repository.capture_fingerprint(config.repo)
            review = run_structured_reviewer(config.reviewer_spec, review_input)
            repository.verify_fingerprint_unchanged(
                config.repo, fingerprint, context="pre-closure cumulative review"
            )
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
            next_iteration = cumulative_history.review_iteration + 1
            if review.verdict_is_explicit:
                cumulative_history.review_iteration = next_iteration

            packet = review.repair_packet
            if review.verdict is ReviewVerdict.APPROVED:
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


def _checkpoint_cycle(
    config: OrchestratorConfig,
    artifacts: RunArtifacts,
    state: _RunState,
    task_ctx: TaskContext,
    plan_text: str,
    *,
    initial_findings: str | None = None,
) -> RunResult:
    """Run one bounded implementer/verify/review/commit/push cycle.

    ``initial_findings`` seeds the first attempt's ``PREVIOUS_FINDINGS``
    field — used when this function is called again after the first
    accepted checkpoint (a ``CHANGES_REQUESTED`` pre-closure cumulative
    review, which is the only caller that still repairs after the first
    checkpoint — never after Task Closure has been committed; see the
    module docstring). Each such call is a self-contained cycle: it reads
    whatever the current ``HEAD`` happens to be (via mode A, ``git diff
    HEAD``) and, on ``APPROVED``, commits and pushes exactly one more
    checkpoint on top of it. ``docs/TASK.md`` may never be part of that
    diff — AUTONOMOUS_PR permits mutating it only during prospective Task
    Closure — so every attempt mechanically refuses one that touches it,
    before the reviewer ever sees it.
    """

    previous_findings: str | None = initial_findings

    for attempt in range(config.max_repairs + 1):
        state.phase = Phase.IMPLEMENTATION_CHECKPOINT
        before = repository.capture_branch_head(config.repo)
        prompt = _build_implementation_prompt(
            task_ctx,
            plan_text,
            attempt,
            previous_findings,
            _format_repository_context(state=state),
        )
        impl_result = run_implementer(config.implementer_spec, prompt)
        repository.verify_branch_head_unchanged(
            config.repo, before, context="implementer invocation"
        )
        if impl_result.timed_out or impl_result.returncode != 0:
            raise _Blocked(
                f"implementer failed during the implementation checkpoint "
                f"(attempt {attempt}): returncode={impl_result.returncode!r} "
                f"timed_out={impl_result.timed_out!r}"
            )

        state.phase = Phase.DETERMINISTIC_VERIFICATION
        verification = _run_verification(config)
        artifacts.write(
            f"verification_attempt_{attempt}.txt", _format_verification(verification)
        )
        if not verification.passed:
            if attempt == config.max_repairs:
                raise _Blocked(
                    "deterministic verification never passed within the "
                    "repair budget"
                )
            state.repair_count += 1
            previous_findings = _format_verification(verification)
            continue

        review_patch = repository.build_checkpoint_patch_uncommitted(config.repo)
        artifacts.write(f"review_patch_attempt_{attempt}.patch", review_patch.diff_text)

        touched = repository.changed_paths(config.repo)
        _require_no_task_md_in_ordinary_checkpoint(touched)

        state.phase = Phase.CHECKPOINT_REVIEW
        review_input = _build_checkpoint_review_input(
            task_ctx,
            plan_text,
            review_patch.diff_text,
            verification,
            _format_repository_context(
                state=state, head_sha_override=review_patch.head_sha
            ),
        )
        fingerprint = repository.capture_fingerprint(config.repo)
        review_result = run_reviewer(config.reviewer_spec, review_input)
        repository.verify_fingerprint_unchanged(
            config.repo, fingerprint, context="checkpoint review"
        )
        artifacts.write(
            f"checkpoint_review_attempt_{attempt}.txt", _format_review(review_result)
        )

        if review_result.verdict is ReviewVerdict.APPROVED:
            return _commit_and_push_checkpoint(
                config, artifacts, state, task_ctx, attempt, review_patch
            )
        if review_result.verdict is ReviewVerdict.CHANGES_REQUESTED:
            if attempt == config.max_repairs:
                raise _Blocked(
                    "checkpoint repair budget exhausted without an "
                    "APPROVED designated-reviewer verdict"
                )
            state.repair_count += 1
            previous_findings = review_result.findings
            continue
        raise _Blocked(
            f"designated reviewer returned {review_result.verdict.value} for "
            f"the checkpoint: {review_result.findings}"
        )

    raise _Blocked("checkpoint repair budget exhausted")  # pragma: no cover - defensive


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


def _commit_and_push_checkpoint(
    config: OrchestratorConfig,
    artifacts: RunArtifacts,
    state: _RunState,
    task_ctx: TaskContext,
    attempt: int,
    review_patch: repository.ReviewPatch,
) -> RunResult:
    paths = repository.changed_paths(config.repo)
    new_head = repository.commit_reviewed_checkpoint(
        config.repo,
        reviewed_patch=review_patch,
        message=_commit_message(task_ctx, attempt),
        paths=paths,
    )
    # Record the actual local committed HEAD before attempting the push, so
    # that an ambiguous/failed push still reports the real local state (the
    # commit that landed) rather than the pre-commit SHA — and so a push
    # failure is never retried against a HEAD the caller can't see.
    state.head_sha = new_head
    assert state.delivery_branch is not None  # set in _delivery_branch_ready
    repository.push_delivery_branch(
        config.repo, branch=state.delivery_branch, expected_branch=state.delivery_branch
    )
    artifacts.write(
        "accepted_checkpoint.txt",
        f"branch: {state.delivery_branch}\nhead_sha: {new_head}\nattempt: {attempt}\n",
    )
    return RunResult(
        task_id=config.task_id,
        phase=Phase.CHECKPOINT_REVIEW,
        outcome=None,
        delivery_branch=state.delivery_branch,
        head_sha=new_head,
        repair_count=state.repair_count,
        blocked_reason=None,
        artifacts_dir=artifacts.directory,
    )


def _commit_message(task_ctx: TaskContext, attempt: int) -> str:
    return f"{task_ctx.task_id}: accepted implementation checkpoint (attempt {attempt})"


def _build_implementation_prompt(
    task_ctx: TaskContext,
    plan_text: str,
    attempt: int,
    previous_findings: str | None,
    repository_context_text: str,
) -> str:
    return (
        f"TASK_ID: {task_ctx.task_id}\n"
        f"ATTEMPT: {attempt}\n"
        "ROLE: Implement the accepted plan below in the current working "
        "tree, within the already-approved scope of the authoritative task "
        "detail below. Do not commit, push, or run any Git/GitHub command "
        "yourself. Do not edit docs/TASK.md here -- AUTONOMOUS_PR permits "
        "that mutation only during prospective Task Closure, and any "
        "docs/TASK.md change in this diff will be refused mechanically "
        "before review. Do not rely on remembering the planning "
        "conversation; the authoritative task detail, accepted plan, and "
        "repository context are all reproduced here explicitly.\n"
        "TASK_DETAIL:\n"
        f"{task_ctx.detail_text}\n"
        "ACCEPTED_PLAN:\n"
        f"{plan_text}\n"
        "REPOSITORY_CONTEXT:\n"
        f"{repository_context_text}"
        f"PREVIOUS_FINDINGS:\n{previous_findings or '(none)'}\n"
    )


def _build_checkpoint_review_input(
    task_ctx: TaskContext,
    plan_text: str,
    diff_text: str,
    verification: VerificationEvidence,
    repository_context_text: str,
) -> str:
    return (
        f"TASK_ID: {task_ctx.task_id}\n"
        "ROLE: Review the following implementation checkpoint against the "
        "authoritative task detail, the accepted plan, the repository "
        "context, and the deterministic verification evidence below — "
        "everything needed to judge scope/compliance is reproduced "
        "explicitly here. Respond with exactly one of APPROVED, "
        "CHANGES_REQUESTED, or BLOCKED on its own line.\n"
        "TASK_DETAIL:\n"
        f"{task_ctx.detail_text}\n"
        "ACCEPTED_PLAN:\n"
        f"{plan_text}\n"
        "REPOSITORY_CONTEXT:\n"
        f"{repository_context_text}"
        "VERIFICATION:\n"
        f"{_format_verification(verification)}\n"
        "REVIEW_PATCH:\n"
        f"{diff_text}\n"
    )


# --------------------------------------------------------------------------
# Deterministic verification
# --------------------------------------------------------------------------


def _run_verification(config: OrchestratorConfig) -> VerificationEvidence:
    """Run every configured verification command and prove — never merely
    assume — that none of them mutated the repository.

    Deterministic verification commands are given no Git/GitHub write
    access declaration and are never trusted to be read-only by
    convention alone: :func:`.repository.capture_fingerprint` snapshots
    branch/HEAD/full worktree+index state (status digest, so this works
    correctly even when the implementation worktree is intentionally
    dirty — the exact dirty state is simply the expected one) once before
    the first command, and :func:`.repository.verify_fingerprint_unchanged`
    checks it again after *every* command against that same original
    snapshot, before the next command (or the caller) ever proceeds. A
    command that commits, checks out a different branch/commit, or
    changes any tracked/untracked visible worktree content — even one
    that itself exits ``0`` — fails this closed immediately
    (:class:`.repository.RepositoryError`) rather than silently becoming
    an implementation/Git side-effect mechanism.

    ``VerificationEvidence.head_sha`` is the fingerprint's ``head_sha``,
    captured *before* running anything — since every command is positively
    proven not to have moved it, this is exactly the commit the evidence
    actually describes, never an assumption.
    """

    return _run_verification_commands(config, config.verification_commands)


def _run_verification_commands(
    config: OrchestratorConfig, commands: tuple[tuple[str, ...], ...]
) -> VerificationEvidence:
    """Run exactly the supplied shell-free argv commands.

    The v2 checkpoint primitive supplies ``ExecutionCheckpoint.verification``;
    legacy :func:`_run_verification` delegates with its configured v1 commands.
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


def _full_verification(
    config: OrchestratorConfig, artifacts: RunArtifacts, state: _RunState
) -> None:
    state.phase = Phase.FULL_VERIFICATION
    verification = _run_verification(config)
    artifacts.write("full_verification.txt", _format_verification(verification))
    if not verification.passed:
        raise _Blocked(
            "full verification failed; mandatory checks cannot be brought "
            "to green inside the task's approved scope"
        )
    state.full_verification_evidence = verification


# --------------------------------------------------------------------------
# Pre-closure cumulative implementation review / mode C final cumulative audit
# --------------------------------------------------------------------------


def _pre_closure_cumulative_review(
    config: OrchestratorConfig,
    artifacts: RunArtifacts,
    state: _RunState,
    task_ctx: TaskContext,
    plan_text: str,
    base_sha: str,
) -> None:
    """Get a fresh designated-reviewer verdict on ``<base_sha>...HEAD``,
    built before Task Closure exists on the delivery branch — satisfies
    ``docs/TASK.md`` §18.1's "the implementation diff has been
    reviewed/accepted" prerequisite. This is explicitly **not** mode C: it
    is the same diff range *shape* used for a different purpose at a
    different point in the flow, and
    :func:`.repository.build_cumulative_patch_from_base` keeps the two
    distinct via :class:`.repository.ReviewPurpose`. ``base_sha`` must be
    an exact, already-fetched-and-revalidated ``origin/main`` SHA (the
    caller's responsibility — see :func:`_revalidate_against_fresh_origin_main`
    and :func:`_prepare_for_closure`); this function never fetches itself.

    Only ``APPROVED`` permits closure preparation/draft-PR progression.
    ``CHANGES_REQUESTED`` enters the same bounded repair policy as every
    other *pre-closure* review gate here, reusing :func:`_checkpoint_cycle`
    for the actual repair mechanics (one more implementer/verify/review/
    commit/push cycle) before rebuilding and re-reviewing this cumulative
    diff against the SAME ``base_sha`` (only ``HEAD`` moved from the
    repair; ``origin/main`` did not). This bounded repair is never
    available once Task Closure has been committed — see the module
    docstring and :func:`_mode_c_audit`.

    Every repair commit here moves ``HEAD``, which stales the mandatory
    ``FULL_VERIFICATION`` gate's evidence (``state.full_verification_evidence``
    still describes the pre-repair commit). :func:`_full_verification` is
    therefore replayed immediately after each successful repair, before
    the cumulative diff is rebuilt/re-reviewed — never leaving
    ``state.full_verification_evidence`` bound to a commit older than the
    one it will be handed alongside at closure
    (:func:`_format_accepted_implementation_handoff` asserts the two
    match).
    """

    state.phase = Phase.PRE_CLOSURE_CUMULATIVE_REVIEW
    for attempt in range(config.max_repairs + 1):
        patch = repository.build_cumulative_patch_from_base(
            config.repo, repository.ReviewPurpose.PRE_CLOSURE_CUMULATIVE_REVIEW, base_sha
        )
        artifacts.write(
            f"pre_closure_cumulative_review_attempt_{attempt}.patch", patch.diff_text
        )
        review_input = _build_cumulative_review_input(task_ctx, plan_text, patch)
        fingerprint = repository.capture_fingerprint(config.repo)
        review_result = run_reviewer(config.reviewer_spec, review_input)
        repository.verify_fingerprint_unchanged(
            config.repo,
            fingerprint,
            context="pre-closure cumulative implementation review",
        )
        artifacts.write(
            f"pre_closure_cumulative_review_verdict_attempt_{attempt}.txt",
            _format_review(review_result),
        )

        if review_result.verdict is ReviewVerdict.APPROVED:
            # Retained verbatim as the accepted implementation-diff
            # evidence prospective Task Closure's handoff requires
            # (docs/AUTONOMOUS_PR_HARNESS.md §6) -- replaces (not merges
            # with) whatever was previously retained, so a stale-base
            # rebuild here always leaves the newly accepted patch, never
            # the old one, as what closure actually receives.
            state.accepted_implementation_patch = patch
            state.phase = Phase.PRE_CLOSURE_CUMULATIVE_REVIEW
            return
        if review_result.verdict is ReviewVerdict.CHANGES_REQUESTED:
            if attempt == config.max_repairs:
                raise _Blocked(
                    "pre-closure cumulative implementation review repair "
                    "budget exhausted without an APPROVED verdict"
                )
            state.repair_count += 1
            _checkpoint_cycle(
                config,
                artifacts,
                state,
                task_ctx,
                plan_text,
                initial_findings=review_result.findings,
            )
            # The repair just committed a new HEAD -- replay the mandatory
            # full-verification gate against it before this cumulative
            # diff is rebuilt/re-reviewed, so the evidence retained for
            # closure is never stale (see this function's docstring).
            _full_verification(config, artifacts, state)
            state.phase = Phase.PRE_CLOSURE_CUMULATIVE_REVIEW
            continue
        raise _Blocked(
            f"designated reviewer returned {review_result.verdict.value} for "
            f"the pre-closure cumulative implementation review: "
            f"{review_result.findings}"
        )

    raise _Blocked(
        "pre-closure cumulative implementation review repair budget exhausted"
    )  # pragma: no cover - defensive


def _mode_c_audit(
    config: OrchestratorConfig,
    artifacts: RunArtifacts,
    state: _RunState,
    task_ctx: TaskContext,
    plan_text: str,
    base_sha: str,
    round_index: int,
) -> None:
    """Build and get a fresh reviewer verdict on ``<base_sha>...HEAD`` —
    actual mode C (``AGENTS.md`` "review.patch and diff ranges") — only
    ever called after Task Closure has itself been reviewed, committed,
    pushed, and ``origin/main`` freshly revalidated, so its range
    necessarily includes the closure commit. ``base_sha`` must be an
    exact, already-fetched-and-revalidated ``origin/main`` SHA; this
    function never fetches itself
    (:func:`.repository.build_cumulative_patch_from_base`). Records
    ``state.mode_c_base_sha``/``state.mode_c_head_sha`` on success so
    :func:`_post_closure_gate`/:func:`_verify_mode_c_still_fresh` can later
    detect ``origin/main``/``HEAD`` movement this accepted audit did not
    cover.

    Unlike the pre-closure cumulative review, ``CHANGES_REQUESTED`` here is
    always terminal: Task Closure is already committed/pushed by this
    point, and this module cannot safely replay a post-closure
    implementation repair without invalidating/rebuilding that
    already-accepted closure evidence (``docs/AUTONOMOUS_PR_HARNESS.md``
    §16) — see the module docstring.
    """

    state.phase = Phase.MODE_C_FINAL_AUDIT
    patch = repository.build_cumulative_patch_from_base(
        config.repo, repository.ReviewPurpose.FINAL_CUMULATIVE_AUDIT, base_sha
    )
    artifacts.write(f"mode_c_audit_attempt_{round_index}.patch", patch.diff_text)
    review_input = _build_cumulative_review_input(task_ctx, plan_text, patch)
    fingerprint = repository.capture_fingerprint(config.repo)
    review_result = run_reviewer(config.reviewer_spec, review_input)
    repository.verify_fingerprint_unchanged(
        config.repo, fingerprint, context="mode C final cumulative audit"
    )
    artifacts.write(
        f"mode_c_audit_verdict_attempt_{round_index}.txt",
        _format_review(review_result),
    )

    if review_result.verdict is ReviewVerdict.APPROVED:
        state.mode_c_base_sha = base_sha
        state.mode_c_head_sha = patch.head_sha
        return
    if review_result.verdict is ReviewVerdict.CHANGES_REQUESTED:
        raise _Blocked(
            "mode C final cumulative audit returned CHANGES_REQUESTED "
            "after prospective Task Closure was already committed/pushed; "
            "this module cannot safely replay a post-closure "
            "implementation repair without invalidating/rebuilding "
            "already-accepted Task Closure evidence "
            "(docs/AUTONOMOUS_PR_HARNESS.md §16) -- a new, separate, "
            "explicit invocation is required after addressing this"
        )
    raise _Blocked(
        f"designated reviewer returned {review_result.verdict.value} for "
        f"the mode C final cumulative audit: {review_result.findings}"
    )


def _verify_mode_c_still_fresh(config: OrchestratorConfig, state: _RunState) -> None:
    """Fail closed if anything moved ``HEAD`` past the exact commit the
    accepted mode C audit covers, with no materiality exception
    (``AGENTS.md`` "review.patch and diff ranges"). ``origin/main``
    movement is separately handled by :func:`_post_closure_gate`'s own
    replay loop before this ever runs; this is the final HEAD-only defense
    for movement this module did not itself cause.
    """

    current_head = repository.head_sha(config.repo)
    if current_head != state.mode_c_head_sha:
        raise _Blocked(
            "the accepted mode C final cumulative audit was built against "
            f"HEAD {state.mode_c_head_sha!r}, but HEAD is now "
            f"{current_head!r}; that audit is stale and must be rebuilt "
            "and re-reviewed before the task/PR is considered complete"
        )


def _build_cumulative_review_input(
    task_ctx: TaskContext, plan_text: str, patch: repository.ReviewPatch
) -> str:
    return (
        f"TASK_ID: {task_ctx.task_id}\n"
        f"REVIEW_PURPOSE: {patch.purpose.value}\n"
        f"RANGE: {patch.range_description}\n"
        "ROLE: Review the following cumulative implementation diff against "
        "the authoritative task detail and the accepted plan. Respond with "
        "exactly one of APPROVED, CHANGES_REQUESTED, or BLOCKED on its own "
        "line.\n"
        "TASK_DETAIL:\n"
        f"{task_ctx.detail_text}\n"
        "ACCEPTED_PLAN:\n"
        f"{plan_text}\n"
        "CUMULATIVE_REVIEW_PATCH:\n"
        f"{patch.diff_text}\n"
    )


# --------------------------------------------------------------------------
# Draft PR
# --------------------------------------------------------------------------


def _draft_pr(
    config: OrchestratorConfig,
    artifacts: RunArtifacts,
    state: _RunState,
    task_ctx: TaskContext,
) -> str:
    """Create the draft PR through ``gh`` (never REST, never non-draft,
    never merge/auto-merge — enforced in :mod:`.repository`) and retain the
    actual PR number for prospective Task Closure. Fails closed if the PR
    number cannot be positively determined from the returned URL.
    """

    state.phase = Phase.DRAFT_PR
    assert state.delivery_branch is not None  # set in _delivery_branch_ready
    title, body = _build_pr_title_and_body(task_ctx)
    pr_url = repository.create_draft_pull_request(
        config.repo,
        title=title,
        body=body,
        head=state.delivery_branch,
        expected_branch=state.delivery_branch,
        gh_command=config.gh_command,
    )
    pr_number = _extract_pr_number(pr_url)
    state.pr_url = pr_url
    state.pr_number = pr_number
    artifacts.write("draft_pr.txt", f"url: {pr_url}\nnumber: {pr_number}\n")
    return pr_number


def _build_pr_title_and_body(task_ctx: TaskContext) -> tuple[str, str]:
    title = f"{task_ctx.task_id}: {task_ctx.roadmap_target}"
    body = (
        f"Draft PR opened by the AUTONOMOUS_PR harness for {task_ctx.task_id}. "
        "Never merged or auto-merged by this harness -- merge remains a "
        "separate, explicit human action.\n\n"
        "## Task detail\n\n"
        f"{task_ctx.detail_text}\n"
    )
    return title, body


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


def _prepare_for_closure(
    config: OrchestratorConfig,
    artifacts: RunArtifacts,
    state: _RunState,
    task_ctx: TaskContext,
    plan_text: str,
) -> TaskContext:
    """Immediately before prospective Task Closure begins: if
    ``origin/main`` has moved since the pre-closure cumulative review was
    last accepted, that evidence is stale — rebuild and re-review it
    against the new exact SHA before closure proceeds (still pre-closure,
    so the bounded repair policy still applies normally). Then record the
    exact authoritative ``docs/TASK.md`` text at that point as the closure
    baseline :func:`_revalidate_closure_relevant_state` compares against
    afterward.
    """

    previous_sha = state.origin_main_sha
    task_ctx, sha = _revalidate_against_fresh_origin_main(
        config, artifacts, state, task_ctx, label="pre_closure_recheck"
    )
    if sha != previous_sha:
        _pre_closure_cumulative_review(
            config, artifacts, state, task_ctx, plan_text, sha
        )
    state.closure_baseline_task_md_text = task_context.load_task_queue_text_at_ref(
        config.repo, sha
    )
    return task_ctx


def _require_delivery_head_matches_accepted_evidence(
    config: OrchestratorConfig, state: _RunState
) -> None:
    """Immediately before prospective Task Closure begins (after
    :func:`_prepare_for_closure`'s own origin/main revalidation/rebuild):
    fail closed unless the delivery branch's current local ``HEAD`` is
    still exactly the commit the accepted pre-closure cumulative
    implementation review covers, and the mandatory full-verification
    evidence describes that same commit.

    ``_prepare_for_closure`` only rebuilds/re-reviews the pre-closure
    cumulative diff in response to ``origin/main`` moving — it has no way
    to detect an out-of-band *local* commit advancing the delivery branch
    past the reviewed/verified commit in between. If that happened, the
    accepted implementation review/verification evidence is stale for
    ``docs/TASK.md`` §18.1's purposes: v1 fails closed here rather than
    treating a later mode C final cumulative audit as retroactive
    satisfaction of that prerequisite. A fresh, separate, explicit
    invocation (which will produce a fresh pre-closure cumulative review
    against the new HEAD) is required instead.
    """

    patch = state.accepted_implementation_patch
    if patch is None:
        raise _Blocked(
            "no accepted pre-closure cumulative implementation review is "
            "on record; prospective Task Closure cannot proceed without "
            "the docs/TASK.md §18.1 prerequisite it satisfies"
        )
    verification = state.full_verification_evidence
    if verification is None:
        raise _Blocked(
            "no mandatory full-verification evidence is on record; "
            "prospective Task Closure cannot proceed without it"
        )
    current_head = repository.head_sha(config.repo)
    if current_head != patch.head_sha:
        raise _Blocked(
            f"the delivery branch HEAD ({current_head!r}) has moved past "
            "the exact commit the accepted pre-closure cumulative "
            f"implementation review covers ({patch.head_sha!r}); that "
            "acceptance is stale for docs/TASK.md §18.1's purposes and a "
            "later mode C final cumulative audit is never treated as "
            "retroactive satisfaction of it -- a fresh, separate, "
            "explicit invocation is required to review the new HEAD "
            "before closure can proceed"
        )
    if verification.head_sha != current_head:
        raise _Blocked(
            "mandatory full-verification evidence "
            f"({verification.head_sha!r}) does not describe the current "
            f"delivery branch HEAD ({current_head!r}); prospective Task "
            "Closure cannot proceed without verification evidence for the "
            "exact commit being closed"
        )


def _prospective_task_closure(
    config: OrchestratorConfig,
    artifacts: RunArtifacts,
    state: _RunState,
    task_ctx: TaskContext,
    plan_text: str,
    pr_number: str,
) -> None:
    """Prepare, review, and (once ``APPROVED``) commit/push the one
    ``docs/TASK.md`` mutation an ``AUTONOMOUS_PR`` invocation is ever
    authorised to make (``AGENTS.md`` "Bounded authority"; ``docs/TASK.md``
    §18.1) — using the canonical closure file set §18 actually requires,
    not ``docs/TASK.md`` alone. Mechanically restricted, not just prompted
    for: the diff must touch exactly the canonical closure files
    (:func:`_require_canonical_closure_files_touched`) before it is even
    shown to the designated reviewer.
    """

    state.phase = Phase.PROSPECTIVE_TASK_CLOSURE
    previous_findings: str | None = None
    accepted_implementation_handoff = _format_accepted_implementation_handoff(state)
    closure_baseline_task_md = _format_closure_baseline_task_md(state)

    for attempt in range(config.max_repairs + 1):
        before = repository.capture_branch_head(config.repo)
        prompt = _build_closure_prompt(
            task_ctx,
            plan_text,
            pr_number,
            _format_repository_context(state=state),
            accepted_implementation_handoff,
            closure_baseline_task_md,
            attempt,
            previous_findings,
        )
        impl_result = run_implementer(config.implementer_spec, prompt)
        repository.verify_branch_head_unchanged(
            config.repo, before, context="implementer invocation (closure)"
        )
        if impl_result.timed_out or impl_result.returncode != 0:
            raise _Blocked(
                f"implementer failed during prospective Task Closure "
                f"(attempt {attempt}): returncode={impl_result.returncode!r} "
                f"timed_out={impl_result.timed_out!r}"
            )

        closure_patch = repository.build_checkpoint_patch_uncommitted(config.repo)
        artifacts.write(
            f"closure_patch_attempt_{attempt}.patch", closure_patch.diff_text
        )
        touched = repository.changed_paths(config.repo)
        _require_canonical_closure_files_touched(touched)

        state.phase = Phase.CLOSURE_REVIEW
        review_input = _build_closure_review_input(
            task_ctx,
            plan_text,
            pr_number,
            _format_repository_context(state=state),
            accepted_implementation_handoff,
            closure_baseline_task_md,
            closure_patch.diff_text,
        )
        fingerprint = repository.capture_fingerprint(config.repo)
        review_result = run_reviewer(config.reviewer_spec, review_input)
        repository.verify_fingerprint_unchanged(
            config.repo, fingerprint, context="closure review"
        )
        artifacts.write(
            f"closure_review_attempt_{attempt}.txt", _format_review(review_result)
        )

        if review_result.verdict is ReviewVerdict.APPROVED:
            new_head = repository.commit_reviewed_checkpoint(
                config.repo,
                reviewed_patch=closure_patch,
                message=f"{task_ctx.task_id}: prospective Task Closure (PR #{pr_number})",
                paths=touched,
            )
            state.head_sha = new_head
            assert state.delivery_branch is not None
            repository.push_delivery_branch(
                config.repo,
                branch=state.delivery_branch,
                expected_branch=state.delivery_branch,
            )
            artifacts.write(
                "closure_accepted.txt",
                f"head_sha: {new_head}\nattempt: {attempt}\n",
            )
            return
        if review_result.verdict is ReviewVerdict.CHANGES_REQUESTED:
            if attempt == config.max_repairs:
                raise _Blocked(
                    "prospective Task Closure repair budget exhausted "
                    "without an APPROVED verdict"
                )
            state.repair_count += 1
            previous_findings = review_result.findings
            state.phase = Phase.PROSPECTIVE_TASK_CLOSURE
            continue
        raise _Blocked(
            f"designated reviewer returned {review_result.verdict.value} for "
            f"prospective Task Closure: {review_result.findings}"
        )

    raise _Blocked(
        "prospective Task Closure repair budget exhausted"
    )  # pragma: no cover - defensive


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


# The §18 tracker reconciliation actions prospective Task Closure both
# authorizes and requires -- shared verbatim between the closure
# implementer prompt and the closure reviewer input so the two roles are
# judging the diff against the identical checklist.
_CLOSURE_REQUIRED_RECONCILIATION_ACTIONS = (
    "mark the just-completed task Done; "
    "add its Recently completed evidence using the actual draft PR number "
    "given below; "
    "remove the completed task's full Open task detail section; "
    "append the factual TSK entry to docs/DEVELOPMENT_LOG.md; "
    "reconcile docs/ROADMAP.md/docs/DEFERRED.md only when this task's "
    "delivered work legitimately changes Roadmap/Deferred status; "
    "select the next Current strictly against the authoritative baseline "
    "below under EXACTLY one of two canonical rules -- (a) an "
    "already-eligible, already-executable task qualifies under "
    "docs/TASK.md's own normal queue/readiness invariants, OR (b) the "
    "narrow docs/TASK.md §18.1.1 prospective immediate-dependent case "
    "applies: a single task whose ONLY not-yet-authoritative-Done "
    "dependency is the task just closed here, where that dependency "
    "becomes prospectively Done in this same atomic closure, every other "
    "readiness condition it needs is already independently satisfied, and "
    "it has no other unfinished dependency -- if NEITHER (a) nor (b) "
    "applies, explicitly leave Current: — (no task is ever promoted "
    "merely to make Current non-empty, and §18.1.1 never licenses "
    "promoting an unrelated Backlog/Blocked/oversized task or one with "
    "any other unfinished dependency); "
    "recalculate Next and Hard blockers consistently with whichever Current "
    "decision was actually made; "
    "update Last reviewed; "
    "and update Next free ID only if the allocation state actually changed"
)

_CLOSURE_PROHIBITED_ACTIONS = (
    "any task allocation, refinement, decomposition, or reselection beyond "
    "exactly what §18 (including the narrow §18.1.1 prospective "
    "immediate-dependent case) requires for closing this one task and "
    "selecting the next Current when one actually qualifies under either "
    "canonical rule; "
    "promoting an ineligible Backlog/Blocked/oversized (e.g. size-L) task, "
    "or a §18.1.1 candidate that has any other unfinished dependency "
    "besides the task just closed, to Current merely to make Current "
    "non-empty when neither canonical rule actually qualifies -- "
    "Current: — is the canonically correct outcome in that case, never an "
    "invented or premature promotion; "
    "and beginning implementation of the newly-selected (or §18.1.1 "
    "prospectively represented) next Current task before this PR actually "
    "merges, which is separate future work this invocation never performs"
)


def _format_accepted_implementation_handoff(state: _RunState) -> str:
    """The explicit prospective-Task-Closure handoff
    ``docs/AUTONOMOUS_PR_HARNESS.md`` §6 requires: the exact accepted
    pre-closure cumulative implementation diff, its evidence metadata, and
    the mandatory deterministic-verification evidence that gated it —
    reproduced literally so closure preparation/review never depends on
    hidden prior-process state. Not a schema framework: this is one
    explicit text block built from values already carried on
    :class:`_RunState`.

    Positively checks (never merely hopes, and never via a bare ``assert``
    that could vanish under ``python -O``) that the retained verification
    evidence actually covers the same commit as the retained accepted
    implementation diff: :func:`_pre_closure_cumulative_review` replays
    :func:`_full_verification` after every repair commit, and
    :func:`_require_delivery_head_matches_accepted_evidence` checks this
    same invariant again immediately before closure begins, precisely so
    this can never diverge in practice — but a missing or mismatched value
    here always fails closed (:class:`_Blocked`) rather than raising an
    uncaught ``AssertionError``, since this is mandatory handoff evidence,
    not an internal type-narrowing convenience. The resulting text block
    shows both SHAs together (``reviewed_head_sha`` from the diff,
    ``verified_head_sha`` from :func:`_format_verification`) so a human or
    reviewer can also positively confirm the match without re-deriving it.
    """

    patch = state.accepted_implementation_patch
    if patch is None:
        raise _Blocked(
            "no accepted pre-closure cumulative implementation review is "
            "on record; prospective Task Closure cannot proceed without "
            "the docs/AUTONOMOUS_PR_HARNESS.md §6 handoff it requires"
        )
    verification = state.full_verification_evidence
    if verification is None:
        raise _Blocked(
            "no mandatory full-verification evidence is on record; "
            "prospective Task Closure cannot proceed without it"
        )
    if verification.head_sha != patch.head_sha:
        raise _Blocked(
            "mandatory verification evidence "
            f"({verification.head_sha!r}) must cover the exact same commit "
            f"as the accepted implementation diff ({patch.head_sha!r}) it "
            "is handed alongside"
        )
    return (
        "ACCEPTED_IMPLEMENTATION_DIFF:\n"
        f"{patch.diff_text}\n"
        "ACCEPTED_IMPLEMENTATION_DIFF_EVIDENCE:\n"
        f"base_sha: {patch.base_sha}\n"
        f"reviewed_head_sha: {patch.head_sha}\n"
        f"review_purpose: {patch.purpose.value}\n"
        "review_status: APPROVED\n"
        "MANDATORY_VERIFICATION_EVIDENCE:\n"
        f"{_format_verification(verification)}\n"
    )


def _format_closure_baseline_task_md(state: _RunState) -> str:
    """The exact authoritative ``docs/TASK.md`` text closure was prepared
    against (``state.closure_baseline_task_md_text``, set by
    :func:`_prepare_for_closure`), reproduced literally for both closure
    roles.

    This is what makes the Current/Next/Hard-blocker reconciliation
    decision self-contained: both the closure implementer and the closure
    designated reviewer judge that decision from the identical
    authoritative tracker snapshot, never from hidden session memory or an
    independent re-read of ``docs/TASK.md`` that could disagree with what
    this run actually revalidated against.

    A missing baseline fails closed (:class:`_Blocked`) rather than
    raising an uncaught ``AssertionError`` — this is mandatory handoff
    evidence, not an internal type-narrowing convenience.
    """

    baseline = state.closure_baseline_task_md_text
    if baseline is None:
        raise _Blocked(
            "no closure-baseline authoritative docs/TASK.md text is on "
            "record; prospective Task Closure cannot proceed without the "
            "baseline _prepare_for_closure must set first"
        )
    return f"CLOSURE_BASELINE_TASK_MD:\n{baseline}\n"


def _build_closure_prompt(
    task_ctx: TaskContext,
    plan_text: str,
    pr_number: str,
    repository_context_text: str,
    accepted_implementation_handoff: str,
    closure_baseline_task_md: str,
    attempt: int,
    previous_findings: str | None,
) -> str:
    return (
        f"TASK_ID: {task_ctx.task_id}\n"
        f"ATTEMPT: {attempt}\n"
        "ROLE: Perform the ONE prospective Task Closure mutation permitted "
        "by AUTONOMOUS_PR governance (AGENTS.md 'Bounded authority'; "
        "docs/TASK.md §18/§18.1). This is the ONLY docs/TASK.md mutation "
        "you are authorized to make, and it REQUIRES the full §18 tracker "
        "reconciliation for the just-completed task below -- not merely "
        "appending a marker. Judge the Current/Next/Hard-blocker "
        "reconciliation decision strictly from CLOSURE_BASELINE_TASK_MD "
        "below (the authoritative docs/TASK.md text this closure was "
        "prepared against) -- never from memory of the planning/"
        "implementation conversation and never by independently "
        "re-deriving queue facts. You MUST: "
        f"{_CLOSURE_REQUIRED_RECONCILIATION_ACTIONS}. These §18 "
        "reconciliation actions ARE authorized and required as part of "
        "this one closure -- they are not 'queue traversal' or 'refinement' "
        "in the prohibited sense below. What remains PROHIBITED: "
        f"{_CLOSURE_PROHIBITED_ACTIONS}. Edit ONLY the canonical closure "
        "files: docs/TASK.md and docs/DEVELOPMENT_LOG.md are REQUIRED (the "
        "factual TSK entry belongs in DEVELOPMENT_LOG.md); "
        "docs/ROADMAP.md and docs/DEFERRED.md are OPTIONAL and must be "
        "included only if this task's delivered work legitimately changes "
        "Roadmap/Deferred status. Any other file change will be refused "
        "mechanically before review.\n"
        f"DRAFT_PR_NUMBER: {pr_number}\n"
        "TASK_DETAIL:\n"
        f"{task_ctx.detail_text}\n"
        "ACCEPTED_PLAN:\n"
        f"{plan_text}\n"
        f"{accepted_implementation_handoff}"
        f"{closure_baseline_task_md}"
        "REPOSITORY_CONTEXT:\n"
        f"{repository_context_text}"
        f"PREVIOUS_FINDINGS:\n{previous_findings or '(none)'}\n"
    )


def _build_closure_review_input(
    task_ctx: TaskContext,
    plan_text: str,
    pr_number: str,
    repository_context_text: str,
    accepted_implementation_handoff: str,
    closure_baseline_task_md: str,
    diff_text: str,
) -> str:
    return (
        f"TASK_ID: {task_ctx.task_id}\n"
        "ROLE: Review the following prospective Task Closure diff. It must "
        "touch only the canonical closure files -- docs/TASK.md and "
        "docs/DEVELOPMENT_LOG.md required, docs/ROADMAP.md/docs/DEFERRED.md "
        "optional and only when this task's delivered work legitimately "
        "reconciles Roadmap/Deferred status. It must perform the full "
        "docs/TASK.md §18 tracker reconciliation for the just-completed "
        "task -- REQUIRE that it: "
        f"{_CLOSURE_REQUIRED_RECONCILIATION_ACTIONS}. These reconciliation "
        "actions are REQUIRED, not 'queue traversal' or prohibited "
        "'refinement'. Judge the Current/Next/Hard-blocker reconciliation "
        "decision strictly against CLOSURE_BASELINE_TASK_MD below (the "
        "authoritative docs/TASK.md text this closure was prepared "
        "against), not from memory or an independent re-read. REJECT "
        f"(CHANGES_REQUESTED or BLOCKED) a diff that instead performs: "
        f"{_CLOSURE_PROHIBITED_ACTIONS}; that touches any file outside the "
        "canonical closure file set; or that omits any of the required "
        "reconciliation actions above. Judge whether any included optional "
        "Roadmap/Deferred edit is actually justified by this task. Respond "
        "with exactly one of APPROVED, CHANGES_REQUESTED, or BLOCKED on "
        "its own line.\n"
        f"DRAFT_PR_NUMBER: {pr_number}\n"
        "TASK_DETAIL:\n"
        f"{task_ctx.detail_text}\n"
        "ACCEPTED_PLAN:\n"
        f"{plan_text}\n"
        f"{accepted_implementation_handoff}"
        f"{closure_baseline_task_md}"
        "REPOSITORY_CONTEXT:\n"
        f"{repository_context_text}"
        "CLOSURE_DIFF:\n"
        f"{diff_text}\n"
    )


# --------------------------------------------------------------------------
# Post-closure gate: mode C final cumulative audit + required CI
# --------------------------------------------------------------------------


def _post_closure_gate(
    config: OrchestratorConfig,
    artifacts: RunArtifacts,
    state: _RunState,
    task_ctx: TaskContext,
    plan_text: str,
) -> None:
    """Bind mode C to an exact, freshly revalidated ``origin/main`` SHA,
    check required CI, then re-fetch once more to confirm ``origin/main``
    did not move again while that was happening — rebuilding/re-reviewing
    mode C and re-checking CI against the new state if it did.

    Bounded to :data:`_POST_CLOSURE_MAX_ROUNDS`: if ``origin/main`` keeps
    moving faster than this can stabilize, fails closed rather than
    looping forever or declaring ``READY_FOR_HUMAN_MERGE`` against
    evidence that might already be stale again. Neither mode C
    ``CHANGES_REQUESTED`` nor a failing CI check ever triggers a new
    implementation checkpoint here — see :func:`_mode_c_audit` and
    :func:`_required_ci`.
    """

    for round_index in range(_POST_CLOSURE_MAX_ROUNDS):
        state.phase = Phase.ORIGIN_MAIN_REVALIDATION
        task_ctx, sha = _revalidate_closure_relevant_state(
            config, artifacts, state, task_ctx, label=f"post_closure_round_{round_index}"
        )
        _mode_c_audit(config, artifacts, state, task_ctx, plan_text, sha, round_index)
        _required_ci(config, artifacts, state, round_index)
        recheck_sha = repository.fetch_and_capture_origin_main_sha(config.repo)
        if recheck_sha == sha:
            return
        # origin/main moved again while mode C/CI were being checked --
        # loop and rebuild/re-review against the new state.

    raise _Blocked(
        "origin/main kept moving faster than mode C and required CI could "
        "stabilize within the bounded number of replay rounds; safe "
        "continuation to READY_FOR_HUMAN_MERGE cannot be positively "
        "established"
    )


def _required_ci(
    config: OrchestratorConfig,
    artifacts: RunArtifacts,
    state: _RunState,
    round_index: int,
) -> None:
    """Check required PR CI through the existing ``gh`` boundary
    (:func:`.repository.pr_required_checks`, restricted to GitHub-required
    checks via ``--required`` — an unrelated optional check can never
    block or satisfy this gate).

    Positively binds the checks it reads to the exact commit this run
    actually pushed: :func:`.repository.pr_head_sha` (``gh pr view --json
    headRefOid``) must equal ``state.head_sha`` both immediately before and
    immediately after reading checks. Checks reported for a different PR
    head are never accepted as evidence for this closure commit, and the
    second (post-read) check catches a concurrent head change during the
    read itself from producing a mixed, falsely-valid snapshot.

    A positively recognized "no required checks configured for this PR"
    result (:attr:`.repository.RequiredChecksResult.no_required_checks`)
    satisfies this gate — an empty required set has nothing left to block
    on — but is never inferred from an ordinary empty/ambiguous checks
    body; see :func:`.repository.pr_required_checks`. The gate-satisfied
    decision otherwise keys off ``gh``'s own already-validated
    ``returncode`` (``0`` — every required check succeeded), never off
    re-deriving "every bucket says pass" here: a successful check may
    legitimately carry bucket ``skipping`` (GitHub's own
    success/skipped/neutral conclusions), and this module must not
    reinterpret ``gh``'s genuine success as pending merely because of
    that.

    Performs exactly one checks read — it never polls or sleeps waiting for
    CI to finish. A still-pending result (nothing failing, but not
    everything passing yet) fails closed rather than blocking the process
    indefinitely: this module never implicitly resumes (§11) and never
    infers permission to continue from the existing delivery branch/PR's
    mere presence — that state is descriptive only, never resumable run
    state. Addressing this requires a new, separate, explicit
    ``AUTONOMOUS_PR`` invocation once CI has actually finished; this
    process never waits for or retries that on its own.

    A genuine CI failure is always terminal here too: Task Closure is
    already committed/pushed by this point, and this module cannot safely
    replay a post-closure implementation repair without invalidating/
    rebuilding already-accepted closure evidence
    (``docs/AUTONOMOUS_PR_HARNESS.md`` §16) — see the module docstring.
    """

    state.phase = Phase.REQUIRED_CI
    assert state.pr_number is not None  # set in _draft_pr
    assert state.head_sha is not None  # set by _prospective_task_closure

    _require_pr_head_matches_closure_commit(config, state, when="before reading checks")

    result = repository.pr_required_checks(
        config.repo, state.pr_number, gh_command=config.gh_command
    )

    _require_pr_head_matches_closure_commit(config, state, when="after reading checks")

    if result.no_required_checks:
        artifacts.write(
            f"ci_checks_attempt_{round_index}.txt",
            "(gh reported no required checks configured for this PR; the "
            "required-CI gate is satisfied because the required set is "
            "empty)\n",
        )
        return

    checks = result.checks
    artifacts.write(f"ci_checks_attempt_{round_index}.txt", _format_ci_checks(checks))

    if result.returncode == 0:
        # gh's own "every required check succeeded" outcome -- already
        # validated by repository.pr_required_checks to mean every check
        # carries a successful bucket (pass or skipping; GitHub itself
        # treats a skipped/neutral check as a successful conclusion).
        # Reinterpreting this as "pending" merely because a successful
        # check happens to carry bucket "skipping" rather than "pass"
        # would itself be a fail-*open* bug in the opposite direction.
        return

    failing = [check for check in checks if check.get("bucket") == "fail"]
    if failing:
        raise _Blocked(
            "required CI reported failing checks after prospective Task "
            "Closure was already committed/pushed: "
            f"{[check.get('name') for check in failing]!r}; this module "
            "cannot safely replay a post-closure implementation repair "
            "without invalidating/rebuilding already-accepted Task "
            "Closure evidence (docs/AUTONOMOUS_PR_HARNESS.md §16) -- a "
            "new, separate, explicit invocation is required after "
            "addressing this"
        )
    raise _Blocked(
        "required CI has not completed (no required check reported "
        "failure, but not every required check has reported passing); "
        "this module never polls or waits for CI completion and never "
        "resumes this run implicitly. v1 stops here: the existing "
        "delivery branch and draft PR are never treated as resumable run "
        "state, only as descriptive context -- getting past this point "
        "requires a new, separate, explicit AUTONOMOUS_PR invocation once "
        "required CI has actually finished, not an automatic retry of "
        "this one"
    )


def _require_pr_head_matches_closure_commit(
    config: OrchestratorConfig, state: _RunState, *, when: str
) -> None:
    assert state.pr_number is not None
    assert state.head_sha is not None
    pr_head = repository.pr_head_sha(
        config.repo, state.pr_number, gh_command=config.gh_command
    )
    if pr_head != state.head_sha:
        raise _Blocked(
            f"the draft PR's head commit ({pr_head!r}, checked {when}) "
            f"does not match the exact closure-reviewed commit this run "
            f"pushed ({state.head_sha!r}); this required-CI evidence is "
            "stale for a different commit than the one this closure "
            "actually covers, and is never accepted as evidence for it"
        )


def _format_ci_checks(checks: list[dict[str, object]]) -> str:
    if not checks:
        return "(no checks reported)\n"
    lines = [
        f"- {check.get('name')!r}: state={check.get('state')!r} "
        f"bucket={check.get('bucket')!r}"
        for check in checks
    ]
    return "\n".join(lines) + "\n"
