from dataclasses import replace
from datetime import datetime, timezone

import pytest

from dnd_engine.domain.commands.attack import AttackCommand, AttackPayload
from dnd_engine.domain.events.turn_action_spent import (
    apply_turn_action_spent_v1,
    build_turn_action_spent_v1,
)
from dnd_engine.domain.state.combat import CombatState


FIXED_TIMESTAMP = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)


def make_command(*, actor_id: str = "character_001") -> AttackCommand:
    return AttackCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id=actor_id,
        payload=AttackPayload(target_id="monster_001"),
    )


def build_event(
    command: AttackCommand | None = None,
    *,
    combat_id: str = "combat_001",
    caused_by: str = "event_attack_resolved",
) -> object:
    return build_turn_action_spent_v1(
        event_id="event_000123",
        timestamp=FIXED_TIMESTAMP,
        command=command or make_command(),
        combat_id=combat_id,
        caused_by=caused_by,
    )


def make_combat(**overrides: object) -> CombatState:
    values: dict[str, object] = {
        "id": "combat_001",
        "round": 1,
        "order": ("character_001", "monster_001"),
        "active_index": 0,
    }
    values.update(overrides)
    return CombatState(**values)  # type: ignore[arg-type]


# --- build_turn_action_spent_v1 --------------------------------------------


def test_builder_creates_exact_canonical_event() -> None:
    event = build_event()

    assert event.type == "TurnActionSpent"
    assert event.version == 1
    assert event.payload == {"combatId": "combat_001"}


def test_builder_correlates_to_originating_attack_command() -> None:
    command = make_command()
    event = build_event(command)

    assert event.command_id == command.command_id
    assert event.campaign_id == command.campaign_id


def test_builder_sets_actor_to_attack_actor() -> None:
    command = make_command(actor_id="monster_002")
    event = build_event(command)

    assert event.actor_id == "monster_002"


def test_builder_sets_caused_by_to_attack_resolution_event() -> None:
    event = build_event(caused_by="event_attack_resolved_999")

    assert event.caused_by == "event_attack_resolved_999"


def test_builder_rejects_wrong_command_type() -> None:
    with pytest.raises(TypeError, match="AttackCommand"):
        build_turn_action_spent_v1(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
            command=object(),  # type: ignore[arg-type]
            combat_id="combat_001",
            caused_by="event_attack_resolved",
        )


def test_builder_rejects_non_string_caused_by() -> None:
    with pytest.raises(TypeError, match="caused_by"):
        build_turn_action_spent_v1(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
            command=make_command(),
            combat_id="combat_001",
            caused_by=None,  # type: ignore[arg-type]
        )


# --- apply_turn_action_spent_v1 --------------------------------------------


def test_applier_marks_action_spent_true() -> None:
    combat = make_combat(action_spent=False)
    event = build_event()

    updated = apply_turn_action_spent_v1(combat, event)

    assert updated.action_spent is True


def test_applier_does_not_mutate_source_combat() -> None:
    combat = make_combat(action_spent=False)
    event = build_event()

    apply_turn_action_spent_v1(combat, event)

    assert combat.action_spent is False


def test_applier_preserves_other_fields() -> None:
    combat = make_combat(action_spent=False, round=2, active_index=0)
    event = build_event()

    updated = apply_turn_action_spent_v1(combat, event)

    assert updated.id == combat.id
    assert updated.round == combat.round
    assert updated.order == combat.order
    assert updated.active_index == combat.active_index
    assert updated.positions == combat.positions


def test_applier_rejects_wrong_event_type_or_version() -> None:
    combat = make_combat()
    event = build_event()

    with pytest.raises(ValueError, match="type"):
        apply_turn_action_spent_v1(combat, replace(event, type="OtherEvent"))
    with pytest.raises(ValueError, match="version"):
        apply_turn_action_spent_v1(combat, replace(event, version=2))


def test_applier_rejects_missing_payload_field() -> None:
    combat = make_combat()
    event = build_event()

    with pytest.raises(ValueError, match="unexpected fields"):
        apply_turn_action_spent_v1(combat, replace(event, payload={}))


def test_applier_rejects_extra_payload_field() -> None:
    combat = make_combat()
    event = build_event()
    mutated_payload = dict(event.payload)
    mutated_payload["extra"] = "unexpected"

    with pytest.raises(ValueError, match="unexpected fields"):
        apply_turn_action_spent_v1(combat, replace(event, payload=mutated_payload))


def test_applier_rejects_non_string_combat_id() -> None:
    combat = make_combat()
    event = build_event()

    with pytest.raises(TypeError, match="combatId"):
        apply_turn_action_spent_v1(
            combat, replace(event, payload={"combatId": 1})
        )


def test_applier_rejects_mismatched_combat_id() -> None:
    combat = make_combat(id="combat_999")
    event = build_event(combat_id="combat_001")

    with pytest.raises(ValueError, match="combatId"):
        apply_turn_action_spent_v1(combat, event)


def test_applier_rejects_actor_not_active_creature() -> None:
    combat = make_combat(order=("character_001", "monster_001"), active_index=0)
    event = build_event(make_command(actor_id="monster_001"))

    with pytest.raises(ValueError, match="actor_id"):
        apply_turn_action_spent_v1(combat, event)


def test_applier_rejects_already_spent_action() -> None:
    combat = make_combat(action_spent=True)
    event = build_event()

    with pytest.raises(ValueError, match="action_spent"):
        apply_turn_action_spent_v1(combat, event)


def test_applier_rejects_wrong_types() -> None:
    with pytest.raises(TypeError, match="CombatState"):
        apply_turn_action_spent_v1(object(), build_event())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="GameEvent"):
        apply_turn_action_spent_v1(make_combat(), object())  # type: ignore[arg-type]
