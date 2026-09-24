import json
import sys

import pytest

from tools.autonomous_pr.agents import (
    AgentInvocationSpec,
    AgentRoleError,
    parse_reviewer_verdict,
    parse_structured_reviewer_output,
    run_implementer,
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
                "binding_basis": "checkpoint:CP-1:required_result",
                "problem": "wrong value",
                "evidence": "candidate.py:1",
                "failure_mode": "the candidate retains the wrong value",
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
    finding = result.repair_packet.findings[0]
    assert finding.binding_basis == "checkpoint:CP-1:required_result"
    assert finding.problem == "wrong value"
    assert finding.failure_mode == "the candidate retains the wrong value"
    assert finding.affected_paths == ("candidate.py",)
    assert result.repair_packet.non_convergence is not None


@pytest.mark.parametrize(
    "binding_basis",
    [
        "task:goal",
        "task:scope",
        "task:out_of_scope",
        "task:approved_implementation_approach",
        "task:acceptance_criteria",
        "task:full_verification",
        "checkpoint:CP-1:objective",
        "checkpoint:CP-23:required_result",
        "checkpoint:CP-2:constraints",
        "checkpoint:CP-9:verification",
        "repo:AGENTS.md#review-authority",
        "repo:docs/AUTONOMOUS_PR_HARNESS.md#25",
    ],
)
def test_parse_structured_reviewer_output_accepts_binding_basis_grammar(
    binding_basis: str,
) -> None:
    packet = json.loads(_repair_packet_json())
    packet["findings"][0]["binding_basis"] = binding_basis  # type: ignore[index]

    result = parse_structured_reviewer_output(
        f"CHANGES_REQUESTED\n{json.dumps(packet)}\n"
    )

    assert result.verdict is ReviewVerdict.CHANGES_REQUESTED
    assert result.repair_packet is not None
    assert result.repair_packet.findings[0].binding_basis == binding_basis


@pytest.mark.parametrize("field", ["binding_basis", "failure_mode"])
def test_parse_structured_reviewer_output_blocks_missing_grounding_fields(
    field: str,
) -> None:
    packet = json.loads(_repair_packet_json())
    del packet["findings"][0][field]  # type: ignore[index]

    result = parse_structured_reviewer_output(
        f"CHANGES_REQUESTED\n{json.dumps(packet)}\n"
    )

    assert result.verdict is ReviewVerdict.BLOCKED
    assert result.repair_packet is None
    assert "malformed" in (result.blocked_reason or "")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("binding_basis", None),
        ("binding_basis", "  "),
        ("binding_basis", "task:review_focus"),
        ("binding_basis", "checkpoint:CP-1:acceptance_criteria"),
        ("binding_basis", "checkpoint:CP-zero:objective"),
        ("binding_basis", "checkpoint:CP-0:objective"),
        ("binding_basis", "checkpoint:CP-01:objective"),
        ("binding_basis", "Review focus"),
        ("binding_basis", "repo:"),
        ("binding_basis", "repo:   "),
        ("failure_mode", None),
        ("failure_mode", " \t "),
    ],
)
def test_parse_structured_reviewer_output_blocks_invalid_grounding_fields(
    field: str, value: object
) -> None:
    packet = json.loads(_repair_packet_json())
    packet["findings"][0][field] = value  # type: ignore[index]

    result = parse_structured_reviewer_output(
        f"CHANGES_REQUESTED\n{json.dumps(packet)}\n"
    )

    assert result.verdict is ReviewVerdict.BLOCKED
    assert result.repair_packet is None
    assert "malformed" in (result.blocked_reason or "")


@pytest.mark.parametrize(
    "packet",
    [
        {},
        {"findings": []},
        {"findings": [{"problem": "only one field"}]},
        {
            "findings": [
                {
                    "binding_basis": "task:scope",
                    "problem": "p",
                    "evidence": "e",
                    "failure_mode": "f",
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
