import json
import sys

import pytest

from tools.autonomous_pr.agents import (
    AgentInvocationSpec,
    AgentRoleError,
    parse_reviewer_verdict,
    parse_structured_reviewer_output,
    run_implementer,
    run_reviewer,
    run_structured_reviewer,
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


def _repair_packet_json(*, diagnosis: bool = False) -> str:
    packet: dict[str, object] = {
        "findings": [
            {
                "problem": "wrong value",
                "evidence": "candidate.py:1",
                "required_outcome": "use the required value",
                "recommended_repair": "replace it",
                "verification_focus": "assert the exact value",
                "affected_paths": ["candidate.py"],
            }
        ]
    }
    if diagnosis:
        packet["non_convergence"] = {
            "previous_requirement": "use the required value",
            "actual_change": "changed a different value",
            "why_unsatisfied": "the original value remains",
            "misunderstanding": "the wrong field was selected",
            "remaining_required_outcome": "replace the original value",
            "recommended_corrective_approach": "edit candidate.py:1",
        }
    return json.dumps(packet)


def test_parse_structured_reviewer_output_accepts_complete_repair_packet() -> None:
    result = parse_structured_reviewer_output(
        f"CHANGES_REQUESTED\n{_repair_packet_json(diagnosis=True)}\n"
    )

    assert result.verdict is ReviewVerdict.CHANGES_REQUESTED
    assert result.blocked_reason is None
    assert result.repair_packet is not None
    assert result.repair_packet.findings[0].problem == "wrong value"
    assert result.repair_packet.findings[0].affected_paths == ("candidate.py",)
    assert result.repair_packet.non_convergence is not None


@pytest.mark.parametrize(
    "packet",
    [
        {},
        {"findings": []},
        {"findings": [{"problem": "only one field"}]},
        {
            "findings": [
                {
                    "problem": "p",
                    "evidence": "e",
                    "required_outcome": "r",
                    "recommended_repair": "fix",
                    "verification_focus": "v",
                }
            ],
            "non_convergence": {"previous_requirement": "incomplete"},
        },
    ],
)
def test_parse_structured_reviewer_output_blocks_malformed_packets(
    packet: dict[str, object],
) -> None:
    result = parse_structured_reviewer_output(
        f"CHANGES_REQUESTED\n{json.dumps(packet)}\n"
    )

    assert result.verdict is ReviewVerdict.BLOCKED
    assert result.repair_packet is None
    assert "malformed" in (result.blocked_reason or "")


def test_parse_structured_reviewer_output_blocks_missing_or_ambiguous_verdict() -> None:
    missing = parse_structured_reviewer_output(_repair_packet_json())
    ambiguous = parse_structured_reviewer_output("APPROVED\nBLOCKED\n")

    assert missing.verdict is ReviewVerdict.BLOCKED
    assert ambiguous.verdict is ReviewVerdict.BLOCKED
    assert "ambiguous" in (ambiguous.blocked_reason or "")


def test_run_structured_reviewer_non_zero_exit_is_terminal_blocked() -> None:
    spec = _python_reviewer(
        f"print('CHANGES_REQUESTED'); print({_repair_packet_json()!r}); "
        "raise SystemExit(2)"
    )

    result = run_structured_reviewer(spec, "bounded handoff")

    assert result.verdict is ReviewVerdict.BLOCKED
    assert result.repair_packet is None
    assert "status 2" in (result.blocked_reason or "")


def test_run_structured_reviewer_timeout_is_terminal_blocked() -> None:
    spec = _python_reviewer(
        "import time; time.sleep(5); print('APPROVED')", timeout_seconds=0.2
    )

    result = run_structured_reviewer(spec, "bounded handoff")

    assert result.verdict is ReviewVerdict.BLOCKED
    assert "timed out" in (result.blocked_reason or "")


def test_run_structured_reviewer_launch_failure_is_terminal_blocked() -> None:
    spec = AgentInvocationSpec(
        role=AgentRole.REVIEWER,
        executable="this-executable-does-not-exist-anywhere",
        args=(),
    )

    result = run_structured_reviewer(spec, "bounded handoff")

    assert result.verdict is ReviewVerdict.BLOCKED
    assert "failed to execute" in (result.blocked_reason or "")


def test_run_structured_reviewer_uses_a_fresh_process_for_every_review() -> None:
    spec = _python_reviewer(
        "import builtins\n"
        "if hasattr(builtins, '_v2_review_seen'):\n"
        "    print('BLOCKED')\n"
        "else:\n"
        "    builtins._v2_review_seen = True\n"
        "    print('APPROVED')\n"
    )

    first = run_structured_reviewer(spec, "first bounded handoff")
    second = run_structured_reviewer(spec, "second bounded handoff")

    assert first.verdict is ReviewVerdict.APPROVED
    assert second.verdict is ReviewVerdict.APPROVED
