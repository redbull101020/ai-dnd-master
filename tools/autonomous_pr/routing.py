"""Pure deterministic compute-profile routing for AUTONOMOUS_PR v2.

This module deliberately has no repository, filesystem, subprocess, provider,
prompt, or agent-output boundary.  Each decision is recomputed from its work
kind's baseline and the structured facts of one causal gate episode.
"""

from __future__ import annotations

from collections.abc import Iterable

from .model import (
    AgentRole,
    AgentWorkKind,
    CandidateRejectionBasis,
    ComputeProfile,
    GateHistory,
    RepairPacket,
    ReviewVerdict,
    RoutingDecision,
    RoutingEscalationReason,
)


_BASELINE_PROFILES: dict[tuple[AgentRole, AgentWorkKind], ComputeProfile] = {
    (AgentRole.IMPLEMENTER, AgentWorkKind.CHECKPOINT_IMPLEMENTATION): (
        ComputeProfile.ROUTINE
    ),
    (AgentRole.IMPLEMENTER, AgentWorkKind.IMPLEMENTATION_REPAIR): (
        ComputeProfile.DELIBERATE
    ),
    (AgentRole.IMPLEMENTER, AgentWorkKind.TASK_CLOSURE_PREPARATION): (
        ComputeProfile.ROUTINE
    ),
    (AgentRole.IMPLEMENTER, AgentWorkKind.TASK_CLOSURE_REPAIR): (
        ComputeProfile.DELIBERATE
    ),
    (AgentRole.REVIEWER, AgentWorkKind.CHECKPOINT_REVIEW): (
        ComputeProfile.DELIBERATE
    ),
    (AgentRole.REVIEWER, AgentWorkKind.IMPLEMENTATION_REPAIR_REVIEW): (
        ComputeProfile.DELIBERATE
    ),
    (AgentRole.REVIEWER, AgentWorkKind.PRE_CLOSURE_CUMULATIVE_REVIEW): (
        ComputeProfile.CRITICAL
    ),
    (AgentRole.REVIEWER, AgentWorkKind.TASK_CLOSURE_REVIEW): (
        ComputeProfile.DELIBERATE
    ),
    (AgentRole.REVIEWER, AgentWorkKind.MODE_C_REVIEW): ComputeProfile.CRITICAL,
}

_REPAIR_WORK_KINDS = frozenset(
    {AgentWorkKind.IMPLEMENTATION_REPAIR, AgentWorkKind.TASK_CLOSURE_REPAIR}
)


def baseline_profile(role: AgentRole, work_kind: AgentWorkKind) -> ComputeProfile:
    """Return the exact approved baseline for a valid role/work-kind pair."""

    try:
        return _BASELINE_PROFILES[(role, work_kind)]
    except KeyError as exc:
        raise ValueError(
            f"{work_kind.value!r} is not valid for role {role.value!r}"
        ) from exc


def route_agent_work(
    *,
    role: AgentRole,
    work_kind: AgentWorkKind,
    history: GateHistory | None = None,
    direct_upstream_repair_packet: RepairPacket | None = None,
    seed_verification_rejection_count: int = 0,
) -> RoutingDecision:
    """Recompute one routing decision from baseline and local causal facts.

    ``history`` belongs only to the gate about to invoke the agent.  A direct
    upstream packet or verification count is an explicit causal handoff, not
    inherited history.  Callers end an episode by routing the next independent
    gate with a new history and no direct seed.
    """

    if seed_verification_rejection_count < 0:
        raise ValueError("seed verification rejection count cannot be negative")

    baseline = baseline_profile(role, work_kind)
    reasons: list[RoutingEscalationReason] = []

    if role is AgentRole.IMPLEMENTER and work_kind in _REPAIR_WORK_KINDS:
        if _verification_rejection_count(
            history, seed_verification_rejection_count
        ) >= 2:
            reasons.append(RoutingEscalationReason.REPEATED_VERIFICATION_REJECTION)
        if _has_repeated_controlling_basis(
            history, direct_upstream_repair_packet
        ):
            reasons.append(RoutingEscalationReason.REPEATED_BINDING_BASIS)

    if role is AgentRole.REVIEWER and baseline is not ComputeProfile.CRITICAL:
        if history is not None and history.review_iteration + 1 >= 2:
            reasons.append(RoutingEscalationReason.REPEAT_REVIEW)
        if direct_upstream_repair_packet is not None:
            reasons.append(RoutingEscalationReason.DIRECT_UPSTREAM_REPAIR_PACKET)

    selected = ComputeProfile.CRITICAL if reasons else baseline
    return RoutingDecision(
        role=role,
        work_kind=work_kind,
        baseline_profile=baseline,
        selected_profile=selected,
        escalation_reasons=tuple(reasons),
    )


def _verification_rejection_count(
    history: GateHistory | None, seed_count: int
) -> int:
    local_count = 0
    if history is not None:
        local_count = sum(
            attempt.rejection_basis is CandidateRejectionBasis.VERIFICATION_FAILURE
            for attempt in history.attempts
        )
    return seed_count + local_count


def _has_repeated_controlling_basis(
    history: GateHistory | None,
    direct_upstream_repair_packet: RepairPacket | None,
) -> bool:
    """Compare the controlling packet with all causally earlier packets."""

    lineage = (
        ((direct_upstream_repair_packet,) if direct_upstream_repair_packet else ())
        + tuple(_local_repair_packets(history))
    )
    if not lineage:
        return False

    controlling = lineage[-1]
    earlier = lineage[:-1]

    earlier_bases = {
        finding.binding_basis
        for packet in earlier
        for finding in packet.findings
    }
    return any(
        finding.binding_basis in earlier_bases for finding in controlling.findings
    )


def _local_repair_packets(history: GateHistory | None) -> Iterable[RepairPacket]:
    if history is None:
        return ()
    return (
        attempt.repair_packet
        for attempt in history.attempts
        if attempt.rejection_basis is CandidateRejectionBasis.CHANGES_REQUESTED
        and attempt.reviewer_verdict is ReviewVerdict.CHANGES_REQUESTED
        and attempt.repair_packet is not None
    )
