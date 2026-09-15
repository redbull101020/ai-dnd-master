"""First executable deterministic orchestration slice (TSK-0026, Group 3).

Drives one already-authorized ``AUTONOMOUS_PR`` invocation through:

    preflight
    -> planning
    -> independent plan review
    -> delivery branch ready
    -> implementation checkpoint / deterministic verification / checkpoint
       review (bounded repair/re-review as required)
    -> accepted checkpoint commit/push

matching ``docs/AUTONOMOUS_PR_HARNESS.md`` §9's phase model and
``AGENTS.md`` "Autonomous flow" up to that point. It deliberately does
**not** implement the draft-PR / Task Closure / mode C / required-CI /
``READY_FOR_HUMAN_MERGE`` tail — that is Group 4. Accordingly
:func:`run` never returns :attr:`.model.RunOutcome.STOP`: only
:attr:`.model.RunOutcome.BLOCKED` (a genuine fail-closed terminal
condition) or ``None`` (this slice's phases completed normally and a later
slice continues the flow).

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
  was never revalidated;
- an empty or whitespace-only plan is never treated as a valid handoff
  artifact: even a successful, fingerprint-clean implementer invocation
  during planning is immediately terminal ``BLOCKED`` if it produced no
  real plan text, and the designated reviewer is never invoked for one;
- run state (:class:`_RunState`) and handoff artifacts
  (:class:`RunArtifacts`) live only for the lifetime of one :func:`run`
  call. There is no ``run.json``, database, or other persisted schema, and
  nothing here ever infers permission to resume a prior run from repository
  state (an existing branch, an existing artifacts directory) — every call
  to :func:`run` starts a brand-new :class:`_RunState` and a brand-new
  temporary artifacts directory (§9, §11).
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import repository, task_context
from .agents import AgentInvocationSpec, run_implementer, run_reviewer
from .model import (
    AgentRole,
    Phase,
    ReviewResult,
    ReviewVerdict,
    RunOutcome,
    RunResult,
    TaskContext,
    VerificationCommandResult,
    VerificationEvidence,
)
from .repository import RepositoryError
from .task_context import TaskRevalidationError


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


def run(config: OrchestratorConfig) -> RunResult:
    """Execute the Group 3 orchestration slice for one already-authorized task.

    Always returns a :class:`.model.RunResult` — an expected fail-closed
    condition (task revalidation failure, a repository invariant violation,
    a terminal reviewer verdict, an exhausted repair budget) is reported as
    ``outcome=RunOutcome.BLOCKED`` rather than raised, matching this
    package's existing style of representing expected failure as data
    (``agents.AgentInvocationResult``) rather than exceptions. An
    unexpected/programmer-error exception (e.g. a misconfigured
    :class:`OrchestratorConfig`, already rejected in ``__post_init__``) is
    not caught here and propagates normally.
    """

    artifacts = RunArtifacts.create()
    state = _RunState(task_id=config.task_id)
    try:
        task_ctx = _preflight(config, artifacts, state)
        plan_text = _planning(config, artifacts, state, task_ctx)
        task_ctx = _delivery_branch_ready(config, artifacts, state, task_ctx)
        return _checkpoint_cycle(config, artifacts, state, task_ctx, plan_text)
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
        config, artifacts, state, task_ctx
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
) -> tuple[TaskContext, str]:
    """Fail closed if ``origin/main`` moved since preflight in a way that
    invalidates the already-accepted plan; otherwise return the exact,
    already-fetched SHA the caller must anchor delivery-branch creation to.

    The plan was produced and reviewed against the exact task detail
    recorded in ``state.origin_main_sha`` at preflight. This performs the
    single fetch for that decision
    (:func:`.repository.fetch_and_capture_origin_main_sha`) and, if
    ``origin/main`` has moved, re-reads ``docs/TASK.md`` from that exact
    new SHA (never the mutable ``origin/main`` ref) and revalidates the
    named task again, requiring the resulting
    :class:`.model.TaskContext` to compare exactly equal to the one
    preflight produced (status, roadmap target, dependencies, and the full
    authoritative detail text) — the most positive form of "unchanged
    enough to still be valid" this module can mechanically establish.
    Unrelated ``origin/main`` movement (any change that leaves this task's
    authoritative detail byte-identical) is not itself a reason to block.
    The returned SHA is exactly the one this function just validated
    against — the caller must create the delivery branch from it directly,
    never by fetching or resolving ``origin/main`` again.
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
            "since preflight, and the task is no longer a valid execution "
            f"target on the fresh origin/main: {exc}"
        ) from exc

    if fresh_ctx != task_ctx:
        raise _Blocked(
            f"origin/main moved from {previous_sha!r} to {current_sha!r} "
            "since preflight, and the authoritative task context changed "
            "since the accepted plan was produced/reviewed; the already-"
            "accepted plan can no longer be safely assumed valid against "
            "it"
        )

    state.origin_main_sha = current_sha
    artifacts.write(
        "origin_main_revalidation.txt",
        f"origin/main moved from {previous_sha} to {current_sha}; "
        "authoritative task context confirmed unchanged\n",
    )
    return fresh_ctx, current_sha


# --------------------------------------------------------------------------
# Implementation checkpoint / deterministic verification / checkpoint review
# --------------------------------------------------------------------------


def _checkpoint_cycle(
    config: OrchestratorConfig,
    artifacts: RunArtifacts,
    state: _RunState,
    task_ctx: TaskContext,
    plan_text: str,
) -> RunResult:
    previous_findings: str | None = None

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
        "yourself. Do not rely on remembering the planning conversation; "
        "the authoritative task detail, accepted plan, and repository "
        "context are all reproduced here explicitly.\n"
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
    results: list[VerificationCommandResult] = []
    overall_passed = True
    for command in config.verification_commands:
        result = _run_one_verification_command(config, command)
        overall_passed = overall_passed and result.passed
        results.append(result)
    return VerificationEvidence(commands=tuple(results), passed=overall_passed)


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
    lines = [f"passed: {evidence.passed}"]
    for result in evidence.commands:
        lines.append(
            f"- {' '.join(result.command)!r}: returncode={result.returncode} "
            f"passed={result.passed}"
        )
        if not result.passed:
            lines.append(f"  stdout: {result.stdout.strip()}")
            lines.append(f"  stderr: {result.stderr.strip()}")
    return "\n".join(lines) + "\n"
