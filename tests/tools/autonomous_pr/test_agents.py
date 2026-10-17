import json
import subprocess
import sys

import pytest

from tools.autonomous_pr.agents import (
    AgentInvocationSpec,
    AgentProfileConfig,
    AgentRoleError,
    parse_reviewer_verdict,
    parse_structured_reviewer_output,
    run_implementer,
    run_structured_reviewer,
)
from tools.autonomous_pr import agents as agent_module
from tools.autonomous_pr.agents import AgentProcessFailureKind, run_agent
from tools.autonomous_pr.model import (
    AgentRole,
    ComputeProfile,
    ReviewBlockerKind,
    ReviewVerdict,
)


def _profile_args(role: AgentRole) -> dict[ComputeProfile, tuple[str, ...]]:
    if role is AgentRole.IMPLEMENTER:
        return {
            ComputeProfile.ROUTINE: ("--routine",),
            ComputeProfile.DELIBERATE: ("--deliberate",),
            ComputeProfile.CRITICAL: ("--critical",),
        }
    return {
        ComputeProfile.DELIBERATE: ("--deliberate",),
        ComputeProfile.CRITICAL: ("--critical",),
    }


def test_profile_config_requires_every_role_tier() -> None:
    spec = AgentInvocationSpec(role=AgentRole.IMPLEMENTER, executable="agent")
    mappings = _profile_args(AgentRole.IMPLEMENTER)
    del mappings[ComputeProfile.CRITICAL]

    with pytest.raises(ValueError, match="missing CRITICAL"):
        AgentProfileConfig(spec=spec, profile_args=mappings)


def test_profile_config_rejects_tier_unsupported_for_role() -> None:
    spec = AgentInvocationSpec(role=AgentRole.REVIEWER, executable="agent")
    mappings = _profile_args(AgentRole.REVIEWER)
    mappings[ComputeProfile.ROUTINE] = ("--routine",)

    with pytest.raises(ValueError, match="unsupported ROUTINE"):
        AgentProfileConfig(spec=spec, profile_args=mappings)


def test_profile_config_rejects_empty_and_indistinguishable_tiers() -> None:
    spec = AgentInvocationSpec(role=AgentRole.REVIEWER, executable="agent")
    with pytest.raises(ValueError, match="DELIBERATE.*non-empty"):
        AgentProfileConfig(
            spec=spec,
            profile_args={
                ComputeProfile.DELIBERATE: (),
                ComputeProfile.CRITICAL: ("--critical",),
            },
        )
    with pytest.raises(ValueError, match="distinct effective argv"):
        AgentProfileConfig(
            spec=spec,
            profile_args={
                ComputeProfile.DELIBERATE: ("--same",),
                ComputeProfile.CRITICAL: ("--same",),
            },
        )


@pytest.mark.parametrize("role", (AgentRole.IMPLEMENTER, AgentRole.REVIEWER))
def test_materialized_profile_preserves_role_and_capability_fields(
    role: AgentRole,
) -> None:
    spec = AgentInvocationSpec(
        role=role,
        executable="agent",
        args=("--common",),
        cwd=None,
        timeout_seconds=17.0,
        env={"KEY": "value"},
        fresh_context_capable=role is AgentRole.REVIEWER,
        can_edit_working_files=role is AgentRole.IMPLEMENTER,
        has_git_or_github_write_access=False,
    )
    profiles = AgentProfileConfig(spec=spec, profile_args=_profile_args(role))
    selected = (
        ComputeProfile.ROUTINE
        if role is AgentRole.IMPLEMENTER
        else ComputeProfile.DELIBERATE
    )

    materialized = profiles.materialize(selected)

    assert materialized.args == ("--common", f"--{selected.value.lower()}")
    assert materialized.role is spec.role
    assert materialized.executable == spec.executable
    assert materialized.cwd == spec.cwd
    assert materialized.timeout_seconds == spec.timeout_seconds
    assert materialized.env == spec.env
    assert materialized.fresh_context_capable == spec.fresh_context_capable
    assert materialized.can_edit_working_files == spec.can_edit_working_files
    assert (
        materialized.has_git_or_github_write_access
        == spec.has_git_or_github_write_access
    )


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


def test_agent_bytes_boundary_preserves_input_and_invocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = AgentInvocationSpec(
        role=AgentRole.IMPLEMENTER, executable="agent", args=("--fixed",),
        timeout_seconds=17.0, env={"KEY": "value"},
    )
    calls = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, b"notes\xff", b"diagnostic\xfe")

    monkeypatch.setattr(agent_module.subprocess, "run", fake_run)
    result = run_agent(spec, "Задача")
    assert calls == [(["agent", "--fixed"], {
        "input": "Задача".encode("utf-8"), "capture_output": True,
        "cwd": spec.cwd, "env": {"KEY": "value"}, "timeout": 17.0,
    })]
    assert result.stdout == "notes\ufffd"
    assert result.stderr == "diagnostic\ufffd"
    assert result.returncode == 0 and result.failure_kind is None
    assert not result.timed_out


@pytest.mark.parametrize("partial", [
    b"APPROVED\xff", "APPROVED", None,
    b'CHANGES_REQUESTED\n{"findings": []}', b'BLOCKED\n{}',
])
def test_agent_timeout_retains_partial_diagnostics_without_parsing(
    monkeypatch: pytest.MonkeyPatch, partial: bytes | str | None,
) -> None:
    def timeout(argv: list[str], **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(argv, 1, output=partial, stderr=partial)

    def forbidden_parser(output: str) -> None:
        pytest.fail("timeout output reached semantic parser")

    monkeypatch.setattr(agent_module.subprocess, "run", timeout)
    monkeypatch.setattr(agent_module, "parse_structured_reviewer_output", forbidden_parser)
    spec = _python_reviewer("")
    result = run_agent(spec, "prompt")
    expected = "" if partial is None else (
        partial.decode("utf-8", errors="replace") if isinstance(partial, bytes) else partial
    )
    assert result.stdout == result.stderr == expected
    assert result.returncode is None and result.timed_out
    assert result.failure_kind is AgentProcessFailureKind.TIMEOUT
    review = run_structured_reviewer(spec, "prompt")
    assert review.verdict is ReviewVerdict.BLOCKED
    assert not review.verdict_is_explicit
    assert review.blocked_reason == "reviewer process timed out"
    assert review.repair_packet is None and review.blocked_rationale is None


@pytest.mark.parametrize("error", [PermissionError, FileNotFoundError, OSError])
def test_agent_launch_failure_classification_and_no_transcript_reason(
    monkeypatch: pytest.MonkeyPatch, error: type[OSError],
) -> None:
    def failed_launch(argv: list[str], **kwargs: object) -> None:
        raise error("launch diagnostic " * 1000)

    monkeypatch.setattr(agent_module.subprocess, "run", failed_launch)
    spec = _python_reviewer("")
    result = run_agent(spec, "prompt")
    assert result.failure_kind is AgentProcessFailureKind.LAUNCH_ERROR
    assert result.returncode is None and not result.timed_out
    assert len(result.stderr) == 4096 + len(agent_module._DIAGNOSTIC_TRUNCATION_MARKER)
    review = run_structured_reviewer(spec, "prompt")
    assert not review.verdict_is_explicit
    assert "failed to execute" in review.blocked_reason
    assert "launch diagnostic" not in review.blocked_reason


@pytest.mark.parametrize("returncode, stdout, kind", [
    (0, b"APPROVED\xff", AgentProcessFailureKind.OUTPUT_DECODE_ERROR),
    (3, b"APPROVED", None),
    (3, b"APPROVED\xff", None),
])
def test_reviewer_failure_status_precedes_semantic_parser(
    monkeypatch: pytest.MonkeyPatch, returncode: int, stdout: bytes,
    kind: AgentProcessFailureKind | None,
) -> None:
    monkeypatch.setattr(agent_module.subprocess, "run", lambda argv, **kw:
        subprocess.CompletedProcess(argv, returncode, stdout, b"stderr\xff"))
    monkeypatch.setattr(agent_module, "parse_structured_reviewer_output", lambda output:
        pytest.fail("failed process output reached parser"))
    spec = _python_reviewer("")
    result = run_agent(spec, "prompt")
    assert result.failure_kind is kind and not result.timed_out
    assert result.returncode == (None if kind else returncode)
    review = run_structured_reviewer(spec, "prompt")
    assert review.verdict is ReviewVerdict.BLOCKED
    assert not review.verdict_is_explicit
    assert review.repair_packet is None and review.blocked_rationale is None


def test_successful_reviewer_parses_full_stdout_despite_invalid_stderr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdout = b" \n" * 3000 + b"APPROVED\n"
    monkeypatch.setattr(agent_module.subprocess, "run", lambda argv, **kw:
        subprocess.CompletedProcess(argv, 0, stdout, b"diagnostic\xff"))
    observed = []
    original = parse_structured_reviewer_output

    def parse(output: str) -> agent_module.StructuredReviewResult:
        observed.append(output)
        return original(output)

    monkeypatch.setattr(agent_module, "parse_structured_reviewer_output", parse)
    review = run_structured_reviewer(_python_reviewer(""), "prompt")
    assert observed == [stdout.decode("utf-8")]
    assert review.verdict is ReviewVerdict.APPROVED and review.verdict_is_explicit


@pytest.mark.parametrize("size", [4095, 4096, 4097, 20000])
def test_terminal_agent_diagnostics_keep_exact_source_budget(
    monkeypatch: pytest.MonkeyPatch, size: int,
) -> None:
    source = "a" * 2048 + "middle" * 4000 + "z" * 2048
    source = source[:size] if size <= 4096 else source[:size - 2048] + "z" * 2048
    monkeypatch.setattr(agent_module.subprocess, "run", lambda argv, **kw:
        subprocess.CompletedProcess(argv, 3, source.encode(), source.encode()))
    result = run_agent(_python_reviewer(""), "prompt")
    expected = source if len(source) <= 4096 else (
        source[:2048] + agent_module._DIAGNOSTIC_TRUNCATION_MARKER + source[-2048:]
    )
    assert result.stdout == result.stderr == expected
    assert result.returncode == 3 and result.failure_kind is None


def test_agent_failure_kinds_are_internal_process_failures_only() -> None:
    assert {kind.value for kind in AgentProcessFailureKind} == {
        "TIMEOUT", "LAUNCH_ERROR", "OUTPUT_DECODE_ERROR",
    }


def test_timeout_bytes_diagnostics_keep_head_and_tail(monkeypatch: pytest.MonkeyPatch) -> None:
    output = b"head\xff" + b"x" * 10000 + b"tail\xfe"
    def timeout(argv: list[str], **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(argv, 1, output=output, stderr=output)

    monkeypatch.setattr(agent_module.subprocess, "run", timeout)
    result = run_agent(_python_reviewer(""), "prompt")
    source = output.decode("utf-8", errors="replace")
    assert result.stdout == result.stderr == (
        source[:2048] + agent_module._DIAGNOSTIC_TRUNCATION_MARKER + source[-2048:]
    )
    assert result.failure_kind is AgentProcessFailureKind.TIMEOUT


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


def _blocked_rationale(
    *, blocker_kind: str = "missing_decision"
) -> dict[str, object]:
    return {
        "binding_bases": ["task:scope", "repo:docs/TASK.md#task-authority"],
        "blocker_kind": blocker_kind,
        "problem": "Two binding requirements require an absent decision.",
        "evidence_reference": "Task Scope and repository task authority",
        "blocking_gap": "The fixed contract does not choose either behavior.",
        "required_resolution": "Approve one behavior in a refined task spec.",
    }


def _blocked_output(payload: dict[str, object] | None = None) -> str:
    rationale = _blocked_rationale() if payload is None else payload
    return f"BLOCKED\n{json.dumps(rationale)}\n"


def test_review_blocker_kind_is_exact_closed_set() -> None:
    assert {verdict.value for verdict in ReviewVerdict} == {
        "APPROVED",
        "CHANGES_REQUESTED",
        "BLOCKED",
    }
    assert {kind.value for kind in ReviewBlockerKind} == {
        "missing_decision",
        "missing_scope",
        "missing_architecture_contract",
        "missing_dependency",
        "missing_information",
    }


def test_parse_structured_reviewer_output_preserves_approved_semantics() -> None:
    result = parse_structured_reviewer_output("APPROVED\nexisting trailing notes\n")

    assert result.verdict is ReviewVerdict.APPROVED
    assert result.verdict_is_explicit
    assert result.repair_packet is None
    assert result.blocked_rationale is None
    assert result.blocked_reason is None


@pytest.mark.parametrize("blocker_kind", [kind.value for kind in ReviewBlockerKind])
def test_parse_structured_reviewer_output_accepts_bounded_blocked_rationale(
    blocker_kind: str,
) -> None:
    result = parse_structured_reviewer_output(
        _blocked_output(_blocked_rationale(blocker_kind=blocker_kind))
    )

    assert result.verdict is ReviewVerdict.BLOCKED
    assert result.verdict_is_explicit
    assert result.repair_packet is None
    assert result.blocked_reason == "designated reviewer returned BLOCKED"
    assert result.blocked_rationale is not None
    assert result.blocked_rationale.blocker_kind is ReviewBlockerKind(blocker_kind)
    assert result.blocked_rationale.binding_bases == (
        "task:scope",
        "repo:docs/TASK.md#task-authority",
    )


@pytest.mark.parametrize(
    ("output", "reason_fragment"),
    [
        ("BLOCKED\n", "missing rationale"),
        ("BLOCKED\n{not-json}\n", "invalid JSON"),
        ("BLOCKED\n[]\n", "one JSON object"),
        (
            'BLOCKED\n{"binding_bases": [], "binding_bases": []}\n',
            "duplicate JSON key",
        ),
        (" BLOCKED \n{}\n", "verdict line is not exact"),
    ],
)
def test_parse_structured_reviewer_output_blocks_invalid_blocked_envelope(
    output: str, reason_fragment: str
) -> None:
    result = parse_structured_reviewer_output(output)

    assert result.verdict is ReviewVerdict.BLOCKED
    assert not result.verdict_is_explicit
    assert result.blocked_rationale is None
    assert reason_fragment in (result.blocked_reason or "")


@pytest.mark.parametrize("mutation", ["missing", "unknown"])
def test_parse_structured_reviewer_output_requires_exact_blocked_keys(
    mutation: str,
) -> None:
    payload = _blocked_rationale()
    if mutation == "missing":
        del payload["problem"]
    else:
        payload["unknown"] = "SENSITIVE_REVIEWER_VALUE"

    result = parse_structured_reviewer_output(_blocked_output(payload))

    assert not result.verdict_is_explicit
    assert result.blocked_rationale is None
    assert "invalid top-level keys" in (result.blocked_reason or "")
    assert "SENSITIVE_REVIEWER_VALUE" not in (result.blocked_reason or "")


@pytest.mark.parametrize(
    ("field", "value", "reason_fragment"),
    [
        ("binding_bases", "task:scope", "invalid binding_bases type"),
        ("blocker_kind", 7, "invalid blocker_kind type"),
        ("problem", 7, "invalid problem type"),
        ("evidence_reference", [], "invalid evidence_reference type"),
        ("blocking_gap", {}, "invalid blocking_gap type"),
        ("required_resolution", None, "invalid required_resolution type"),
    ],
)
def test_parse_structured_reviewer_output_blocks_wrong_blocked_json_types(
    field: str, value: object, reason_fragment: str
) -> None:
    payload = _blocked_rationale()
    payload[field] = value

    result = parse_structured_reviewer_output(_blocked_output(payload))

    assert not result.verdict_is_explicit
    assert result.blocked_rationale is None
    assert reason_fragment in (result.blocked_reason or "")


@pytest.mark.parametrize(
    ("binding_bases", "reason_fragment"),
    [
        ([], "invalid binding_bases count"),
        (["task:scope"] * 9, "invalid binding_bases count"),
        (["task:scope", "task:scope"], "duplicate binding basis"),
        (["task:review_focus"], "invalid binding basis"),
        ([""], "invalid binding_bases entry whitespace"),
        ([" task:scope"], "invalid binding_bases entry whitespace"),
        (["task:scope "], "invalid binding_bases entry whitespace"),
        (["repo:line\nbreak"], "invalid binding_bases entry line structure"),
        (["repo:" + "x" * 508], "oversized binding_bases entry"),
    ],
)
def test_parse_structured_reviewer_output_validates_blocked_binding_bases(
    binding_bases: list[str], reason_fragment: str
) -> None:
    payload = _blocked_rationale()
    payload["binding_bases"] = binding_bases

    result = parse_structured_reviewer_output(_blocked_output(payload))

    assert not result.verdict_is_explicit
    assert result.blocked_rationale is None
    assert reason_fragment in (result.blocked_reason or "")


@pytest.mark.parametrize(
    ("field", "value", "reason_fragment"),
    [
        ("problem", " leading", "invalid problem whitespace"),
        ("problem", "trailing ", "invalid problem whitespace"),
        ("evidence_reference", "line\nbreak", "line structure"),
        ("blocking_gap", "x" * 1025, "oversized blocking_gap"),
        ("evidence_reference", "x" * 513, "oversized evidence_reference"),
        ("required_resolution", "x" * 1025, "oversized required_resolution"),
        ("problem", "x" * 1025, "oversized problem"),
    ],
)
def test_parse_structured_reviewer_output_validates_blocked_prose(
    field: str, value: str, reason_fragment: str
) -> None:
    payload = _blocked_rationale()
    payload[field] = value

    result = parse_structured_reviewer_output(_blocked_output(payload))

    assert not result.verdict_is_explicit
    assert result.blocked_rationale is None
    assert reason_fragment in (result.blocked_reason or "")


@pytest.mark.parametrize(
    "field",
    ("problem", "evidence_reference", "blocking_gap", "required_resolution"),
)
@pytest.mark.parametrize("value", ("", " leading", "trailing ", "line\nbreak"))
def test_parse_structured_reviewer_output_does_not_normalize_blocked_prose(
    field: str, value: str
) -> None:
    payload = _blocked_rationale()
    payload[field] = value

    result = parse_structured_reviewer_output(_blocked_output(payload))

    assert not result.verdict_is_explicit
    assert result.blocked_rationale is None
    assert "malformed BLOCKED rationale" in (result.blocked_reason or "")


def test_parse_structured_reviewer_output_blocks_unknown_blocker_kind_without_echo() -> None:
    payload = _blocked_rationale(blocker_kind="SENSITIVE_REVIEWER_VALUE")

    result = parse_structured_reviewer_output(_blocked_output(payload))

    assert not result.verdict_is_explicit
    assert result.blocked_rationale is None
    assert result.blocked_reason == "malformed BLOCKED rationale: unknown blocker_kind"
    assert "SENSITIVE_REVIEWER_VALUE" not in result.blocked_reason


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
        f"print({_blocked_output()!r}); "
        "raise SystemExit(2)"
    )

    result = run_structured_reviewer(spec, "bounded handoff")

    assert result.verdict is ReviewVerdict.BLOCKED
    assert result.repair_packet is None
    assert result.blocked_rationale is None
    assert not result.verdict_is_explicit
    assert "status 2" in (result.blocked_reason or "")


def test_run_structured_reviewer_timeout_is_terminal_blocked() -> None:
    spec = _python_reviewer(
        f"import time; print({_blocked_output()!r}, flush=True); time.sleep(5)",
        timeout_seconds=0.2,
    )

    result = run_structured_reviewer(spec, "bounded handoff")

    assert result.verdict is ReviewVerdict.BLOCKED
    assert result.blocked_rationale is None
    assert not result.verdict_is_explicit
    assert "timed out" in (result.blocked_reason or "")


def test_run_structured_reviewer_launch_failure_is_terminal_blocked() -> None:
    spec = AgentInvocationSpec(
        role=AgentRole.REVIEWER,
        executable="this-executable-does-not-exist-anywhere",
        args=(),
    )

    result = run_structured_reviewer(spec, "bounded handoff")

    assert result.verdict is ReviewVerdict.BLOCKED
    assert result.blocked_rationale is None
    assert not result.verdict_is_explicit
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
