from dataclasses import replace
from datetime import datetime, timezone

import pytest

from dnd_engine.domain.commands.advance_turn import (
    AdvanceTurnCommand,
    AdvanceTurnPayload,
)
from dnd_engine.domain.events.advance_turn import (
    apply_turn_advanced_v1,
    build_turn_advanced_v1,
)
from dnd_engine.domain.rules.advance_turn import AdvanceTurnResult
from dnd_engine.domain.state.combat import CombatState
from dnd_engine.infrastructure.persistence.json.event_serializer import (
    EventSerializer,
)


FIXED_TIMESTAMP = datetime(2026, 8, 30, 13, 0, tzinfo=timezone.utc)


def make_command(*, combat_id: str = "combat_001") -> AdvanceTurnCommand:
    return AdvanceTurnCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=AdvanceTurnPayload(combat_id=combat_id),
    )


def make_outcome(*, combat_id: str = "combat_001", round: int = 1) -> AdvanceTurnResult:
    return AdvanceTurnResult(
        combat_id=combat_id,
        previous_active_creature_id="character_001",
        active_creature_id="monster_001",
        previous_round=1,
        round=round,
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


def build_event(
    command: AdvanceTurnCommand | None = None,
    outcome: AdvanceTurnResult | None = None,
) -> object:
    return build_turn_advanced_v1(
        event_id="event_000123",
        timestamp=FIXED_TIMESTAMP,
        command=command or make_command(),
        outcome=outcome or make_outcome(),
    )


def test_builder_creates_exact_canonical_event() -> None:
    event = build_event()

    assert event.type == "TurnAdvanced"
    assert event.version == 1
    assert event.command_id == "command_000001"
    assert event.campaign_id == "campaign_001"
    assert event.timestamp is FIXED_TIMESTAMP
    assert event.actor_id == "character_001"
    assert event.caused_by is None
    assert event.payload == {
        "combatId": "combat_001",
        "previousActiveCreatureId": "character_001",
        "activeCreatureId": "monster_001",
        "previousRound": 1,
        "round": 1,
    }


def test_canonical_event_is_json_serializable_round_trip() -> None:
    event = build_event()

    serialized = EventSerializer.serialize(event)
    assert EventSerializer.deserialize(serialized) == event


def test_builder_rejects_combat_id_mismatch() -> None:
    with pytest.raises(ValueError, match="combat_id"):
        build_turn_advanced_v1(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
            command=make_command(combat_id="combat_001"),
            outcome=make_outcome(combat_id="combat_002"),
        )


def test_builder_rejects_wrong_types() -> None:
    with pytest.raises(TypeError, match="AdvanceTurnCommand"):
        build_turn_advanced_v1(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
            command=object(),  # type: ignore[arg-type]
            outcome=make_outcome(),
        )
    with pytest.raises(TypeError, match="AdvanceTurnResult"):
        build_turn_advanced_v1(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
            command=make_command(),
            outcome=object(),  # type: ignore[arg-type]
        )


# --- apply_turn_advanced_v1 -------------------------------------------------


def test_applier_advances_active_index_and_round() -> None:
    combat = make_combat(active_index=0, round=1)
    event = build_event()

    updated = apply_turn_advanced_v1(combat, event)

    assert updated == CombatState(
        id="combat_001",
        round=1,
        order=("character_001", "monster_001"),
        active_index=1,
    )


def test_applier_advances_round_on_wraparound() -> None:
    combat = make_combat(order=("character_001", "monster_001"), active_index=1, round=1)
    event = build_turn_advanced_v1(
        event_id="event_000123",
        timestamp=FIXED_TIMESTAMP,
        command=make_command(),
        outcome=AdvanceTurnResult(
            combat_id="combat_001",
            previous_active_creature_id="monster_001",
            active_creature_id="character_001",
            previous_round=1,
            round=2,
        ),
    )

    updated = apply_turn_advanced_v1(combat, event)

    assert updated.round == 2
    assert updated.active_index == 0


def test_applier_rejects_stale_previous_active_creature() -> None:
    combat = make_combat(active_index=1)  # already on monster_001's turn
    event = build_event()  # claims previous active was character_001

    with pytest.raises(ValueError, match="previousActiveCreatureId"):
        apply_turn_advanced_v1(combat, event)


def test_applier_rejects_stale_previous_round() -> None:
    combat = make_combat(round=3)
    event = build_event()  # claims previousRound == 1

    with pytest.raises(ValueError, match="previousRound"):
        apply_turn_advanced_v1(combat, event)


def test_applier_rejects_combat_id_mismatch() -> None:
    combat = make_combat(id="combat_999")
    event = build_event()

    with pytest.raises(ValueError, match="combatId"):
        apply_turn_advanced_v1(combat, event)


def test_applier_rejects_wrong_event_type_or_version() -> None:
    event = build_event()
    combat = make_combat()

    with pytest.raises(ValueError, match="type"):
        apply_turn_advanced_v1(combat, replace(event, type="OtherEvent"))
    with pytest.raises(ValueError, match="version"):
        apply_turn_advanced_v1(combat, replace(event, version=2))


def test_applier_rejects_wrong_types() -> None:
    with pytest.raises(TypeError, match="CombatState"):
        apply_turn_advanced_v1(object(), build_event())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="GameEvent"):
        apply_turn_advanced_v1(make_combat(), object())  # type: ignore[arg-type]
