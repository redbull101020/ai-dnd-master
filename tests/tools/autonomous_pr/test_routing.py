from __future__ import annotations

import pytest

from tools.autonomous_pr.model import (
    AgentRole,
    AgentWorkKind,
    CandidateIdentity,
    CandidateRejectionBasis,
    ComputeProfile,
    GateAttempt,
    GateContext,
    GateHistory,
    RepairFinding,
    RepairPacket,
    ReviewVerdict,
    RoutingEscalationReason,
)
from tools.autonomous_pr.routing import baseline_profile, route_agent_work


BASELINE_CASES = (
    (
        AgentRole.IMPLEMENTER,
        AgentWorkKind.CHECKPOINT_IMPLEMENTATION,
        ComputeProfile.ROUTINE,
    ),
    (
        AgentRole.IMPLEMENTER,
        AgentWorkKind.IMPLEMENTATION_REPAIR,
        ComputeProfile.DELIBERATE,
    ),
    (
        AgentRole.IMPLEMENTER,
        AgentWorkKind.TASK_CLOSURE_PREPARATION,
        ComputeProfile.ROUTINE,
    ),
    (
        AgentRole.IMPLEMENTER,
        AgentWorkKind.TASK_CLOSURE_REPAIR,
        ComputeProfile.DELIBERATE,
    ),
    (
        AgentRole.REVIEWER,
        AgentWorkKind.CHECKPOINT_REVIEW,
        ComputeProfile.DELIBERATE,
    ),
    (
        AgentRole.REVIEWER,
        AgentWorkKind.IMPLEMENTATION_REPAIR_REVIEW,
        ComputeProfile.DELIBERATE,
    ),
    (
        AgentRole.REVIEWER,
        AgentWorkKind.PRE_CLOSURE_CUMULATIVE_REVIEW,
        ComputeProfile.CRITICAL,
    ),
    (
        AgentRole.REVIEWER,
        AgentWorkKind.TASK_CLOSURE_REVIEW,
        ComputeProfile.DELIBERATE,
    ),
    (
        AgentRole.REVIEWER,
        AgentWorkKind.MODE_C_REVIEW,
        ComputeProfile.CRITICAL,
    ),
)


def test_routing_vocabularies_are_closed_to_the_approved_values() -> None:
    assert tuple(profile.value for profile in ComputeProfile) == (
        "ROUTINE",
        "DELIBERATE",
        "CRITICAL",
    )
    assert tuple(work_kind.value for work_kind in AgentWorkKind) == (
        "checkpoint_implementation",
        "implementation_repair",
        "checkpoint_review",
        "implementation_repair_review",
        "pre_closure_cumulative_review",
        "task_closure_preparation",
        "task_closure_repair",
        "task_closure_review",
        "mode_c_review",
    )


@pytest.mark.parametrize(("role", "work_kind", "expected"), BASELINE_CASES)
def test_exact_baseline_matrix(
    role: AgentRole, work_kind: AgentWorkKind, expected: ComputeProfile
) -> None:
    decision = route_agent_work(role=role, work_kind=work_kind)

    assert baseline_profile(role, work_kind) is expected
    assert decision.baseline_profile is expected
    assert decision.selected_profile is expected
    assert decision.escalation_reasons == ()


def test_invalid_role_work_kind_pair_is_rejected() -> None:
    with pytest.raises(ValueError, match="not valid for role"):
        route_agent_work(
            role=AgentRole.REVIEWER,
            work_kind=AgentWorkKind.CHECKPOINT_IMPLEMENTATION,
        )


def test_repeated_basis_escalates_implementation_repair() -> None:
    history = _history_with_packets(_packet("repo:contract"), _packet("repo:contract"))

    decision = _implementation_repair(history)

    assert decision.selected_profile is ComputeProfile.CRITICAL
    assert decision.escalation_reasons == (
        RoutingEscalationReason.REPEATED_BINDING_BASIS,
    )


def test_non_adjacent_a_b_a_basis_escalates() -> None:
    history = _history_with_packets(
        _packet("task:scope"),
        _packet("repo:other"),
        _packet("task:scope"),
    )

    assert _implementation_repair(history).selected_profile is ComputeProfile.CRITICAL


def test_local_basis_repeated_from_direct_upstream_packet_escalates() -> None:
    upstream = _packet("task:scope")
    history = _history_with_packets(_packet("task:scope"))

    decision = route_agent_work(
        role=AgentRole.IMPLEMENTER,
        work_kind=AgentWorkKind.IMPLEMENTATION_REPAIR,
        history=history,
        direct_upstream_repair_packet=upstream,
    )

    assert decision.selected_profile is ComputeProfile.CRITICAL
    assert decision.escalation_reasons == (
        RoutingEscalationReason.REPEATED_BINDING_BASIS,
    )


def test_first_direct_seed_is_not_counted_twice_from_latest_packet() -> None:
    upstream = _packet("task:scope")
    history = _history()
    history.latest_valid_repair_packet = upstream

    decision = route_agent_work(
        role=AgentRole.IMPLEMENTER,
        work_kind=AgentWorkKind.IMPLEMENTATION_REPAIR,
        history=history,
        direct_upstream_repair_packet=upstream,
    )

    assert decision.selected_profile is ComputeProfile.DELIBERATE
    assert decision.escalation_reasons == ()


def test_second_verification_rejection_including_direct_seed_escalates() -> None:
    history = _history_with_verification_failures(1)

    decision = _implementation_repair(
        history, seed_verification_rejection_count=1
    )

    assert decision.selected_profile is ComputeProfile.CRITICAL
    assert decision.escalation_reasons == (
        RoutingEscalationReason.REPEATED_VERIFICATION_REJECTION,
    )


def test_new_basis_without_second_verification_rejection_stays_deliberate() -> None:
    history = _history_with_packets(_packet("task:scope"), _packet("repo:new"))

    decision = _implementation_repair(history)

    assert decision.selected_profile is ComputeProfile.DELIBERATE
    assert decision.escalation_reasons == ()


def test_second_review_iteration_escalates() -> None:
    history = _history()
    history.review_iteration = 1

    decision = route_agent_work(
        role=AgentRole.REVIEWER,
        work_kind=AgentWorkKind.CHECKPOINT_REVIEW,
        history=history,
    )

    assert decision.selected_profile is ComputeProfile.CRITICAL
    assert decision.escalation_reasons == (RoutingEscalationReason.REPEAT_REVIEW,)


def test_first_child_repair_review_with_upstream_packet_escalates() -> None:
    decision = route_agent_work(
        role=AgentRole.REVIEWER,
        work_kind=AgentWorkKind.IMPLEMENTATION_REPAIR_REVIEW,
        history=_history(),
        direct_upstream_repair_packet=_packet("task:scope"),
    )

    assert decision.selected_profile is ComputeProfile.CRITICAL
    assert decision.escalation_reasons == (
        RoutingEscalationReason.DIRECT_UPSTREAM_REPAIR_PACKET,
    )


def test_seeded_verification_only_does_not_escalate_first_repair_review() -> None:
    decision = route_agent_work(
        role=AgentRole.REVIEWER,
        work_kind=AgentWorkKind.IMPLEMENTATION_REPAIR_REVIEW,
        history=_history(),
        seed_verification_rejection_count=1,
    )

    assert decision.selected_profile is ComputeProfile.DELIBERATE
    assert decision.escalation_reasons == ()


@pytest.mark.parametrize(
    "work_kind",
    (
        AgentWorkKind.PRE_CLOSURE_CUMULATIVE_REVIEW,
        AgentWorkKind.MODE_C_REVIEW,
    ),
)
def test_critical_baseline_saturates_without_inherited_escalation(
    work_kind: AgentWorkKind,
) -> None:
    history = _history()
    history.review_iteration = 7

    decision = route_agent_work(
        role=AgentRole.REVIEWER,
        work_kind=work_kind,
        history=history,
        direct_upstream_repair_packet=_packet("repo:contract"),
    )

    assert decision.baseline_profile is ComputeProfile.CRITICAL
    assert decision.selected_profile is ComputeProfile.CRITICAL
    assert decision.escalation_reasons == ()


def test_independent_decisions_do_not_inherit_critical_profile() -> None:
    escalated = _implementation_repair(
        _history_with_packets(_packet("task:scope"), _packet("task:scope"))
    )
    independent = route_agent_work(
        role=AgentRole.IMPLEMENTER,
        work_kind=AgentWorkKind.CHECKPOINT_IMPLEMENTATION,
        history=_history(),
    )

    assert escalated.selected_profile is ComputeProfile.CRITICAL
    assert independent.selected_profile is ComputeProfile.ROUTINE


def test_closure_repair_uses_the_same_local_escalation_policy() -> None:
    history = _history_with_packets(_packet("repo:closure"), _packet("repo:closure"))

    decision = route_agent_work(
        role=AgentRole.IMPLEMENTER,
        work_kind=AgentWorkKind.TASK_CLOSURE_REPAIR,
        history=history,
    )

    assert decision.baseline_profile is ComputeProfile.DELIBERATE
    assert decision.selected_profile is ComputeProfile.CRITICAL


def _implementation_repair(
    history: GateHistory,
    *,
    seed_verification_rejection_count: int = 0,
):
    return route_agent_work(
        role=AgentRole.IMPLEMENTER,
        work_kind=AgentWorkKind.IMPLEMENTATION_REPAIR,
        history=history,
        seed_verification_rejection_count=seed_verification_rejection_count,
    )


def _history() -> GateHistory:
    return GateHistory(
        context=GateContext(
            gate_id="CP-1",
            spec_identity="spec",
            accepted_base_context_identity="base",
        )
    )


def _packet(binding_basis: str) -> RepairPacket:
    return RepairPacket(
        findings=(
            RepairFinding(
                binding_basis=binding_basis,
                problem="problem",
                evidence="evidence",
                failure_mode="failure mode",
                required_outcome="required outcome",
                recommended_repair="recommended repair",
                verification_focus="verification focus",
            ),
        )
    )


def _history_with_packets(*packets: RepairPacket) -> GateHistory:
    history = _history()
    for index, packet in enumerate(packets, start=1):
        history.attempts.append(
            GateAttempt(
                candidate_identity=CandidateIdentity(f"candidate-{index}"),
                candidate_state=f"state-{index}",
                verification=None,
                rejected=True,
                rejection_basis=CandidateRejectionBasis.CHANGES_REQUESTED,
                review_iteration=index,
                reviewer_verdict=ReviewVerdict.CHANGES_REQUESTED,
                findings=packet.findings,
                repair_packet=packet,
            )
        )
        history.latest_valid_repair_packet = packet
    return history


def _history_with_verification_failures(count: int) -> GateHistory:
    history = _history()
    for index in range(count):
        history.attempts.append(
            GateAttempt(
                candidate_identity=CandidateIdentity(f"candidate-{index}"),
                candidate_state=f"state-{index}",
                verification=None,
                rejected=True,
                rejection_basis=CandidateRejectionBasis.VERIFICATION_FAILURE,
                review_iteration=None,
                reviewer_verdict=None,
            )
        )
    return history
