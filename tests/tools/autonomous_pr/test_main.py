from argparse import Namespace
from pathlib import Path

import pytest

from tools.autonomous_pr import __main__ as main_module
from tools.autonomous_pr.__main__ import _build_config, _parse_args
from tools.autonomous_pr.model import (
    AgentRole,
    AgentWorkKind,
    ComputeProfile,
    Phase,
    ReviewGateMetrics,
    ReviewVerdict,
    RunOutcome,
    RunResult,
    RoutingDecisionRecord,
    RoutingEscalationReason,
)


def _argv(*extra: str) -> list[str]:
    return [
        "TSK-9001",
        "--implementer",
        "implementer",
        "--reviewer",
        "reviewer",
        "--implementer-routine-arg=--routine",
        "--implementer-deliberate-arg=--deliberate",
        "--implementer-critical-arg=--critical",
        "--reviewer-deliberate-arg=--deliberate",
        "--reviewer-critical-arg=--critical",
        "--reviewer-fresh-context-capable",
        "--implementer-no-git-github-write-capability",
        "--reviewer-no-git-github-write-capability",
        *extra,
    ]


def test_cli_builds_v2_config_without_runtime_plan_or_verification_selectors() -> None:
    args = _parse_args(_argv("--delivery-branch", "codex/tsk-9001"))

    config = _build_config(args)

    assert config.task_id == "TSK-9001"
    assert config.delivery_branch == "codex/tsk-9001"
    assert not hasattr(config, "verification_commands")
    assert not hasattr(config, "max_repairs")


def test_cli_composes_common_and_profile_specific_argv() -> None:
    config = _build_config(
        _parse_args(
            _argv(
                "--implementer-arg=--common-implementer",
                "--reviewer-arg=--common-reviewer",
            )
        )
    )

    assert config.implementer_profiles.materialize(ComputeProfile.ROUTINE).args == (
        "--common-implementer",
        "--routine",
    )
    assert config.implementer_profiles.materialize(ComputeProfile.CRITICAL).args == (
        "--common-implementer",
        "--critical",
    )
    assert config.reviewer_profiles.materialize(ComputeProfile.DELIBERATE).args == (
        "--common-reviewer",
        "--deliberate",
    )


def test_cli_rejects_unconfigured_required_profile_before_run() -> None:
    argv = _argv()
    argv.remove("--implementer-critical-arg=--critical")

    with pytest.raises(ValueError, match="CRITICAL.*non-empty"):
        _build_config(_parse_args(argv))


def test_v2_phase_model_has_no_runtime_planning_phases() -> None:
    assert "planning" not in {phase.value for phase in Phase}
    assert "plan_review" not in {phase.value for phase in Phase}


@pytest.mark.parametrize("removed_flag", ["--verify", "--max-repairs"])
def test_cli_rejects_removed_v1_flag(removed_flag: str) -> None:
    with pytest.raises(SystemExit) as exc_info:
        _parse_args(_argv(removed_flag, "value"))

    assert exc_info.value.code == 2


def test_cli_keeps_capability_assertions_fail_closed() -> None:
    args = Namespace(
        task_id="TSK-9001",
        repo=Path.cwd(),
        implementer="implementer",
        implementer_args=[],
        implementer_routine_args=["--routine"],
        implementer_deliberate_args=["--deliberate"],
        implementer_critical_args=["--critical"],
        reviewer="reviewer",
        reviewer_args=[],
        reviewer_deliberate_args=["--deliberate"],
        reviewer_critical_args=["--critical"],
        reviewer_fresh_context_capable=False,
        implementer_no_git_github_write_capability=None,
        reviewer_no_git_github_write_capability=None,
        delivery_branch=None,
        agent_timeout_seconds=600.0,
        verify_timeout_seconds=600.0,
    )

    with pytest.raises(ValueError):
        _build_config(args)


def test_no_eligible_task_is_exit_zero_without_a_synthetic_task_id(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        main_module,
        "run",
        lambda config: RunResult(
            task_id=None,
            phase=Phase.PREFLIGHT,
            outcome=RunOutcome.NO_ELIGIBLE_TASK,
            delivery_branch=None,
            head_sha=None,
            blocked_reason=None,
        ),
    )

    assert main_module.main(_argv()) == 0
    output = capsys.readouterr().out
    assert "task_id: None" in output
    assert "outcome: NO_ELIGIBLE_TASK" in output


def test_cli_reports_review_metrics_as_deterministic_json_lines(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = RunResult(
        task_id="TSK-9001",
        phase=Phase.CHECKPOINT_REVIEW,
        outcome=RunOutcome.BLOCKED,
        delivery_branch="delivery",
        head_sha="a" * 40,
        blocked_reason="review blocked",
        review_metrics=(
            ReviewGateMetrics(
                gate_id="CP-1",
                review_iterations=2,
                changes_requested_count=1,
                verification_rejection_count=1,
                findings_per_review=(1, 0),
                binding_bases_per_review=(("task:scope",), ()),
                new_binding_bases_after_first_review=(),
                repeated_binding_bases=(),
                last_reviewer_verdict=ReviewVerdict.BLOCKED,
            ),
        ),
    )

    main_module._report(result)

    metric_lines = [
        line
        for line in capsys.readouterr().out.splitlines()
        if line.startswith("review_metric_json: ")
    ]
    assert metric_lines == [
        'review_metric_json: {"binding_bases_per_review":[["task:scope"],[]],'
        '"changes_requested_count":1,"findings_per_review":[1,0],'
        '"gate_id":"CP-1","last_reviewer_verdict":"BLOCKED",'
        '"new_binding_bases_after_first_review":[],"repeated_binding_bases":[],'
        '"review_iterations":2,"verification_rejection_count":1}'
    ]


def test_cli_reports_routing_decisions_as_safe_deterministic_json_lines(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = RunResult(
        task_id="TSK-9001",
        phase=Phase.CHECKPOINT_REVIEW,
        outcome=RunOutcome.BLOCKED,
        delivery_branch="delivery",
        head_sha="a" * 40,
        blocked_reason="agent output must stay private",
        routing_decisions=(
            RoutingDecisionRecord(
                sequence=1,
                role=AgentRole.IMPLEMENTER,
                work_kind=AgentWorkKind.IMPLEMENTATION_REPAIR,
                gate_id="repair:CP-1",
                baseline_profile=ComputeProfile.DELIBERATE,
                selected_profile=ComputeProfile.CRITICAL,
                escalation_reasons=(
                    RoutingEscalationReason.REPEATED_BINDING_BASIS,
                ),
            ),
        ),
    )

    main_module._report(result)

    output = capsys.readouterr().out
    decision_lines = [
        line
        for line in output.splitlines()
        if line.startswith("routing_decision_json: ")
    ]
    assert decision_lines == [
        'routing_decision_json: {"baseline_profile":"DELIBERATE",'
        '"escalation_reasons":["repeated_binding_basis"],'
        '"gate_id":"repair:CP-1","role":"implementer",'
        '"selected_profile":"CRITICAL","sequence":1,'
        '"work_kind":"implementation_repair"}'
    ]
    assert "--critical" not in decision_lines[0]
    assert "prompt" not in decision_lines[0]
    assert "agent output" not in decision_lines[0]
