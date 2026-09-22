from argparse import Namespace
from pathlib import Path

import pytest

from tools.autonomous_pr import __main__ as main_module
from tools.autonomous_pr.__main__ import _build_config, _parse_args
from tools.autonomous_pr.model import Phase, RunOutcome, RunResult


def _argv(*extra: str) -> list[str]:
    return [
        "TSK-9001",
        "--implementer",
        "implementer",
        "--reviewer",
        "reviewer",
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
        reviewer="reviewer",
        reviewer_args=[],
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
