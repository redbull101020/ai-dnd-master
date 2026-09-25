"""Minimal local CLI entrypoint for the AUTONOMOUS_PR orchestrator.

Executes :func:`tools.autonomous_pr.orchestrator.run` for one explicit
``TSK-NNNN`` selector or literal ``NEXT``, using configured external
implementer/reviewer commands, through the
full lifecycle to ``READY_FOR_HUMAN_MERGE``/``STOP`` or a fail-closed
``BLOCKED``. Per ``docs/AUTONOMOUS_PR_HARNESS.md`` §3, the task ID accepted
here is execution input only, never proof of authorization — running this
CLI is never itself evidence that the user gave a separate, explicit
``AUTONOMOUS_PR`` invocation for the named task, and this CLI intentionally
has no "authorization proof" flag. Confirming that a real invocation was
given is the caller's responsibility, outside this module entirely. This
CLI never merges or auto-merges anything.

Every external command is invoked as an explicit argv list
(``subprocess.run([...], ...)``, never ``shell=True``); no provider SDK is
used. Verification commands come only from the accepted Task Execution
Spec; the CLI has no verification-command override or fallback.

``--reviewer-fresh-context-capable``, ``--implementer-no-git-github-write-capability``,
and ``--reviewer-no-git-github-write-capability`` are all required: omitting
any of them fails configuration (exit 2) before any agent is invoked, per
:class:`.orchestrator.OrchestratorConfig`'s capability preconditions. These
are operator/configuration assertions about the external
implementer/reviewer commands — never ``AUTONOMOUS_PR`` authorization, and
never verified by this module for an opaque external command; see
:class:`.agents.AgentInvocationSpec`'s docstring. In particular, omitting a
``--*-no-git-github-write-capability`` flag is never silently treated as
though the command had been positively asserted safe — this CLI never
manufactures that assertion on the operator's behalf, and never offers a
way to grant Git/GitHub write access to either role.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agents import AgentInvocationSpec
from .model import AgentRole, RunOutcome, RunResult
from .orchestrator import OrchestratorConfig, run


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m tools.autonomous_pr",
        allow_abbrev=False,
        description=(
            "Execute the deterministic AUTONOMOUS_PR orchestrator (preflight "
            "through READY_FOR_HUMAN_MERGE/STOP, or a fail-closed BLOCKED) "
            "for one already-authorized task."
        ),
    )
    parser.add_argument(
        "task_id",
        help=(
            "An explicit TSK-NNNN id or literal NEXT. Execution input only "
            "-- not authorization; omitting it is a configuration error."
        ),
    )
    parser.add_argument(
        "--repo", type=Path, default=Path.cwd(), help="Repository working tree path."
    )
    parser.add_argument("--implementer", required=True, help="Implementer executable.")
    parser.add_argument(
        "--implementer-arg",
        action="append",
        default=[],
        dest="implementer_args",
        help="One implementer argv entry; may repeat.",
    )
    parser.add_argument(
        "--reviewer", required=True, help="Designated reviewer executable."
    )
    parser.add_argument(
        "--reviewer-arg",
        action="append",
        default=[],
        dest="reviewer_args",
        help="One reviewer argv entry; may repeat.",
    )
    parser.add_argument(
        "--reviewer-fresh-context-capable",
        action="store_true",
        help=(
            "Required: an explicit operator/configuration assertion that "
            "the configured reviewer command starts a fresh, one-shot "
            "context on every invocation and never resumes a prior "
            "session. This is a configuration precondition, never "
            "AUTONOMOUS_PR authorization -- the harness cannot inspect an "
            "opaque external command's internal behavior and proves "
            "nothing about it by itself; omitting this flag fails "
            "configuration before any agent is invoked."
        ),
    )
    parser.add_argument(
        "--implementer-no-git-github-write-capability",
        dest="implementer_no_git_github_write_capability",
        action="store_true",
        default=None,
        help=(
            "Required: an explicit operator/configuration assertion that "
            "the configured implementer command/sandbox has no direct "
            "Git/GitHub write capability (no git push, no gh, no reachable "
            "GitHub API credentials) -- not that this CLI grants or "
            "manages that; it never does. A configuration/sandbox "
            "assertion, never AUTONOMOUS_PR authorization, and never "
            "verified by this module for an opaque external command. "
            "Omitting this flag fails configuration before any agent is "
            "invoked -- it is never silently treated as though the "
            "command had been positively asserted safe."
        ),
    )
    parser.add_argument(
        "--reviewer-no-git-github-write-capability",
        dest="reviewer_no_git_github_write_capability",
        action="store_true",
        default=None,
        help=(
            "Required: the same explicit no-write-capability assertion as "
            "--implementer-no-git-github-write-capability, but for the "
            "designated reviewer command."
        ),
    )
    parser.add_argument(
        "--delivery-branch",
        default=None,
        help=(
            "Delivery branch name; after selection defaults to "
            "autonomous-pr/<actual selected task id lowercased>."
        ),
    )
    parser.add_argument("--agent-timeout-seconds", type=float, default=600.0)
    parser.add_argument("--verify-timeout-seconds", type=float, default=600.0)
    return parser.parse_args(argv)


def _build_config(args: argparse.Namespace) -> OrchestratorConfig:
    # A --*-no-git-github-write-capability flag being present is the
    # operator's positive assertion that that command has none (spec
    # field False); absent, the assertion was never made and the field
    # stays undeclared (None) -- OrchestratorConfig refuses None exactly
    # like True, so this CLI never manufactures a safe default on the
    # operator's behalf. This CLI itself never offers any way to grant
    # Git/GitHub write access to either role.
    implementer_has_write_access = (
        False if args.implementer_no_git_github_write_capability else None
    )
    reviewer_has_write_access = (
        False if args.reviewer_no_git_github_write_capability else None
    )

    implementer_spec = AgentInvocationSpec(
        role=AgentRole.IMPLEMENTER,
        executable=args.implementer,
        args=tuple(args.implementer_args),
        cwd=args.repo,
        timeout_seconds=args.agent_timeout_seconds,
        # This CLI exists specifically to run an implementer that edits
        # working files.
        can_edit_working_files=True,
        has_git_or_github_write_access=implementer_has_write_access,
    )
    reviewer_spec = AgentInvocationSpec(
        role=AgentRole.REVIEWER,
        executable=args.reviewer,
        args=tuple(args.reviewer_args),
        cwd=args.repo,
        timeout_seconds=args.agent_timeout_seconds,
        fresh_context_capable=args.reviewer_fresh_context_capable,
        has_git_or_github_write_access=reviewer_has_write_access,
    )
    return OrchestratorConfig(
        task_id=args.task_id,
        repo=args.repo,
        implementer_spec=implementer_spec,
        reviewer_spec=reviewer_spec,
        delivery_branch=args.delivery_branch or "",
        verification_timeout_seconds=args.verify_timeout_seconds,
    )


def _report(result: RunResult) -> None:
    outcome = result.outcome.value if result.outcome is not None else "IN_PROGRESS"
    print(f"task_id: {result.task_id}")
    print(f"phase: {result.phase.value}")
    print(f"outcome: {outcome}")
    print(f"delivery_branch: {result.delivery_branch}")
    print(f"head_sha: {result.head_sha}")
    if result.pr_url is not None:
        print(f"pr_url: {result.pr_url}")
    if result.selection_mode is not None:
        print(f"selection_mode: {result.selection_mode.value}")
    if result.spec_source_sha is not None:
        print(f"spec_source_sha: {result.spec_source_sha}")
    if result.spec_path is not None:
        print(f"spec_path: {result.spec_path}")
    if result.spec_digest is not None:
        print(f"spec_digest: {result.spec_digest}")
    for reason in result.no_work_reasons:
        print(f"no_work_reason: {reason.task_id or '(catalog)'}: {reason.reason}")
    for metric in result.review_metrics:
        payload = {
            "binding_bases_per_review": metric.binding_bases_per_review,
            "changes_requested_count": metric.changes_requested_count,
            "findings_per_review": metric.findings_per_review,
            "gate_id": metric.gate_id,
            "last_reviewer_verdict": (
                metric.last_reviewer_verdict.value
                if metric.last_reviewer_verdict is not None
                else None
            ),
            "new_binding_bases_after_first_review": (
                metric.new_binding_bases_after_first_review
            ),
            "repeated_binding_bases": metric.repeated_binding_bases,
            "review_iterations": metric.review_iterations,
            "verification_rejection_count": metric.verification_rejection_count,
        }
        print(
            "review_metric_json: "
            + json.dumps(payload, sort_keys=True, separators=(",", ":"))
        )
    if result.blocked_reason is not None:
        print(f"blocked_reason: {result.blocked_reason}")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        config = _build_config(args)
    except ValueError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2
    result = run(config)
    _report(result)
    return (
        0
        if result.outcome in (RunOutcome.STOP, RunOutcome.NO_ELIGIBLE_TASK, None)
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
