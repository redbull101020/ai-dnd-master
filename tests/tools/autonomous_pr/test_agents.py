import sys

import pytest

from tools.autonomous_pr.agents import (
    AgentInvocationSpec,
    AgentRoleError,
    parse_reviewer_verdict,
    run_implementer,
    run_reviewer,
)
from tools.autonomous_pr.model import AgentRole, ReviewVerdict


def _python_reviewer(code: str, timeout_seconds: float = 10.0) -> AgentInvocationSpec:
    return AgentInvocationSpec(
        role=AgentRole.REVIEWER,
        executable=sys.executable,
        args=("-c", code),
        timeout_seconds=timeout_seconds,
    )


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("APPROVED\n", ReviewVerdict.APPROVED),
        ("CHANGES_REQUESTED\n", ReviewVerdict.CHANGES_REQUESTED),
        ("BLOCKED\n", ReviewVerdict.BLOCKED),
        ("some findings\nAPPROVED\n", ReviewVerdict.APPROVED),
    ],
)
def test_parse_reviewer_verdict_accepts_exact_tokens(
    output: str, expected: ReviewVerdict
) -> None:
    assert parse_reviewer_verdict(output) is expected


def test_parse_reviewer_verdict_empty_is_blocked() -> None:
    assert parse_reviewer_verdict("") is ReviewVerdict.BLOCKED


def test_parse_reviewer_verdict_malformed_is_blocked() -> None:
    assert parse_reviewer_verdict("Verdict: APPROVED\n") is ReviewVerdict.BLOCKED
    assert parse_reviewer_verdict("approved\n") is ReviewVerdict.BLOCKED


def test_parse_reviewer_verdict_ambiguous_is_blocked() -> None:
    assert (
        parse_reviewer_verdict("APPROVED\nBLOCKED\n") is ReviewVerdict.BLOCKED
    )


def test_parse_reviewer_verdict_unknown_token_is_blocked() -> None:
    assert parse_reviewer_verdict("MAYBE\n") is ReviewVerdict.BLOCKED


def test_run_reviewer_approved() -> None:
    spec = _python_reviewer("print('APPROVED')")

    result = run_reviewer(spec, review_patch_text="diff --git a b\n")

    assert result.verdict is ReviewVerdict.APPROVED


def test_run_reviewer_changes_requested() -> None:
    spec = _python_reviewer(
        "print('needs work'); print('CHANGES_REQUESTED')"
    )

    result = run_reviewer(spec, review_patch_text="diff --git a b\n")

    assert result.verdict is ReviewVerdict.CHANGES_REQUESTED
    assert "needs work" in result.findings


def test_run_reviewer_blocked() -> None:
    spec = _python_reviewer("print('BLOCKED')")

    result = run_reviewer(spec, review_patch_text="diff --git a b\n")

    assert result.verdict is ReviewVerdict.BLOCKED


def test_run_reviewer_non_zero_exit_is_blocked() -> None:
    spec = _python_reviewer("print('APPROVED'); raise SystemExit(1)")

    result = run_reviewer(spec, review_patch_text="diff --git a b\n")

    assert result.verdict is ReviewVerdict.BLOCKED


def test_run_reviewer_timeout_is_blocked() -> None:
    spec = _python_reviewer(
        "import time; time.sleep(5); print('APPROVED')", timeout_seconds=0.2
    )

    result = run_reviewer(spec, review_patch_text="diff --git a b\n")

    assert result.verdict is ReviewVerdict.BLOCKED
    assert "timed out" in result.findings


def test_run_reviewer_process_launch_failure_is_blocked() -> None:
    spec = AgentInvocationSpec(
        role=AgentRole.REVIEWER,
        executable="this-executable-does-not-exist-anywhere",
        args=(),
        timeout_seconds=5.0,
    )

    result = run_reviewer(spec, review_patch_text="diff --git a b\n")

    assert result.verdict is ReviewVerdict.BLOCKED


def test_run_reviewer_rejects_implementer_spec() -> None:
    spec = AgentInvocationSpec(
        role=AgentRole.IMPLEMENTER,
        executable=sys.executable,
        args=("-c", "print('APPROVED')"),
    )

    with pytest.raises(AgentRoleError):
        run_reviewer(spec, review_patch_text="diff --git a b\n")


def test_run_implementer_rejects_reviewer_spec() -> None:
    spec = AgentInvocationSpec(
        role=AgentRole.REVIEWER,
        executable=sys.executable,
        args=("-c", "print('ok')"),
    )

    with pytest.raises(AgentRoleError):
        run_implementer(spec, prompt_text="do the task")


def test_run_implementer_returns_raw_result() -> None:
    spec = AgentInvocationSpec(
        role=AgentRole.IMPLEMENTER,
        executable=sys.executable,
        args=("-c", "print('implementation notes')"),
    )

    result = run_implementer(spec, prompt_text="do the task")

    assert result.returncode == 0
    assert "implementation notes" in result.stdout
