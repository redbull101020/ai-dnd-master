"""Typed values for one live AUTONOMOUS_PR harness run.

Deliberately minimal: only the values needed by ``task_context.py`` and
``agents.py`` to describe one in-memory run live here. No persisted state
schema, no ``run.json``, no workflow-engine abstraction, no generic Gate
hierarchy, and no provider class/registry/factory — those are explicitly
out of scope per ``docs/AUTONOMOUS_PR_HARNESS.md`` §§2, 9, 11, 13.

``Phase`` and ``RunOutcome`` are conceptual, in-process run vocabulary only.
Neither introduces or implies a new ``docs/TASK.md`` ``Status`` value
(``docs/AUTONOMOUS_PR_HARNESS.md`` §9).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TaskStatus(Enum):
    """The closed set of ``docs/TASK.md`` task statuses (``TASK.md`` §4)."""

    BACKLOG = "Backlog"
    READY = "Ready"
    CURRENT = "Current"
    BLOCKED = "Blocked"
    DONE = "Done"
    SUPERSEDED = "Superseded"


class Phase(Enum):
    """Conceptual run phases matching ``AGENTS.md`` "Autonomous flow" and
    ``docs/AUTONOMOUS_PR_HARNESS.md`` §9. Not a ``docs/TASK.md`` Status."""

    PREFLIGHT = "preflight"
    PLANNING = "planning"
    PLAN_REVIEW = "plan_review"
    DELIVERY_BRANCH_READY = "delivery_branch_ready"
    IMPLEMENTATION_CHECKPOINT = "implementation_checkpoint"
    DETERMINISTIC_VERIFICATION = "deterministic_verification"
    CHECKPOINT_REVIEW = "checkpoint_review"
    FULL_VERIFICATION = "full_verification"
    PRE_CLOSURE_CUMULATIVE_REVIEW = "pre_closure_cumulative_review"
    DRAFT_PR = "draft_pr"
    PROSPECTIVE_TASK_CLOSURE = "prospective_task_closure"
    CLOSURE_REVIEW = "closure_review"
    ORIGIN_MAIN_REVALIDATION = "origin_main_revalidation"
    MODE_C_FINAL_AUDIT = "mode_c_final_audit"
    REQUIRED_CI = "required_ci"
    READY_FOR_HUMAN_MERGE = "ready_for_human_merge"


class RunOutcome(Enum):
    """The run's only two terminal outcomes (``AUTONOMOUS_PR_HARNESS.md`` §10)."""

    STOP = "STOP"
    BLOCKED = "BLOCKED"


class ReviewVerdict(Enum):
    """The strict three-token designated-reviewer verdict contract (§7)."""

    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    BLOCKED = "BLOCKED"


class AgentRole(Enum):
    """Distinct implementer/reviewer invocation roles (§5)."""

    IMPLEMENTER = "implementer"
    REVIEWER = "reviewer"


@dataclass(frozen=True)
class TaskContext:
    """Revalidated facts about the named authoritative ``Current`` task.

    Returned only once every readiness fact this harness can mechanically
    check has already passed (``task_context.revalidate_current_task``);
    this is descriptive execution input, never proof of user authorization
    for ``AUTONOMOUS_PR`` (``docs/AUTONOMOUS_PR_HARNESS.md`` §3).
    """

    task_id: str
    status: TaskStatus
    roadmap_target: str
    depends_on: tuple[str, ...]


@dataclass(frozen=True)
class ReviewResult:
    """One designated-reviewer checkpoint outcome, as explicit handoff data."""

    verdict: ReviewVerdict
    findings: str
    raw_output: str
