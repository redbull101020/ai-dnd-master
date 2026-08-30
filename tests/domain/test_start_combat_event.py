from datetime import datetime, timezone

import pytest

from dnd_engine.domain.commands.start_combat import (
    StartCombatCommand,
    StartCombatPayload,
)
from dnd_engine.domain.events.start_combat import (
    apply_combat_started_v1,
    build_combat_started_v1,
)
from dnd_engine.domain.rules.start_combat import InitiativeEntry, StartCombatResult
from dnd_engine.domain.state.combat import CombatState
from dnd_engine.domain.value_objects.d20 import D20Roll, RollMode
from dnd_engine.infrastructure.persistence.json.event_serializer import (
    EventSerializer,
)


FIXED_TIMESTAMP = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def make_command(*, combat_id: str = "combat_001") -> StartCombatCommand:
    return StartCombatCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=StartCombatPayload(
            combat_id=combat_id,
            participant_ids=("character_001", "monster_001"),
        ),
    )


def make_outcome(*, combat_id: str = "combat_001") -> StartCombatResult:
    entries = (
        InitiativeEntry(
            creature_id="monster_001",
            roll=D20Roll(mode=RollMode.NORMAL, rolls=(15,), selected=15),
            modifier=2,
            total=17,
        ),
        InitiativeEntry(
            creature_id="character_001",
            roll=D20Roll(mode=RollMode.NORMAL, rolls=(8,), selected=8),
            modifier=0,
            total=8,
        ),
    )
    return StartCombatResult(
        combat_id=combat_id,
        round=1,
        order=("monster_001", "character_001"),
        entries=entries,
    )


def build_event(
    command: StartCombatCommand | None = None,
    outcome: StartCombatResult | None = None,
) -> object:
    return build_combat_started_v1(
        event_id="event_000123",
        timestamp=FIXED_TIMESTAMP,
        command=command or make_command(),
        outcome=outcome or make_outcome(),
    )


def test_builder_creates_exact_canonical_event() -> None:
    event = build_event()

    assert event.event_id == "event_000123"
    assert event.type == "CombatStarted"
    assert event.version == 1
    assert event.command_id == "command_000001"
    assert event.campaign_id == "campaign_001"
    assert event.timestamp is FIXED_TIMESTAMP
    assert event.actor_id == "character_001"
    assert event.caused_by is None
    assert set(event.payload) == {"combatId", "round", "order", "entries"}
    assert event.payload["combatId"] == "combat_001"
    assert event.payload["round"] == 1
    assert event.payload["order"] == ("monster_001", "character_001")
    assert event.payload["entries"] == (
        {
            "creatureId": "monster_001",
            "roll": {"mode": "normal", "rolls": (15,), "selected": 15},
            "modifier": 2,
            "total": 17,
        },
        {
            "creatureId": "character_001",
            "roll": {"mode": "normal", "rolls": (8,), "selected": 8},
            "modifier": 0,
            "total": 8,
        },
    )


def test_canonical_event_is_json_serializable_round_trip() -> None:
    event = build_event()

    serialized = EventSerializer.serialize(event)
    assert EventSerializer.deserialize(serialized) == event


def test_builder_rejects_combat_id_mismatch() -> None:
    with pytest.raises(ValueError, match="combat_id"):
        build_combat_started_v1(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
            command=make_command(combat_id="combat_001"),
            outcome=make_outcome(combat_id="combat_002"),
        )


def test_builder_rejects_wrong_types() -> None:
    with pytest.raises(TypeError, match="StartCombatCommand"):
        build_combat_started_v1(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
            command=object(),  # type: ignore[arg-type]
            outcome=make_outcome(),
        )
    with pytest.raises(TypeError, match="StartCombatResult"):
        build_combat_started_v1(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
            command=make_command(),
            outcome=object(),  # type: ignore[arg-type]
        )


# --- apply_combat_started_v1 -----------------------------------------------


def test_applier_creates_fresh_combat_state_at_round_one_active_first() -> None:
    event = build_event()

    combat = apply_combat_started_v1(event)

    assert combat == CombatState(
        id="combat_001",
        round=1,
        order=("monster_001", "character_001"),
        active_index=0,
    )


def test_applier_rejects_wrong_event_type_or_version() -> None:
    from dataclasses import replace

    event = build_event()

    with pytest.raises(ValueError, match="type"):
        apply_combat_started_v1(replace(event, type="OtherEvent"))
    with pytest.raises(ValueError, match="version"):
        apply_combat_started_v1(replace(event, version=2))


def test_applier_rejects_unexpected_payload_fields() -> None:
    from dataclasses import replace

    event = build_event()
    mutated_payload = dict(event.payload)
    mutated_payload["extra"] = "unexpected"

    with pytest.raises(ValueError, match="unexpected fields"):
        apply_combat_started_v1(replace(event, payload=mutated_payload))


def test_applier_rejects_non_gameevent() -> None:
    with pytest.raises(TypeError, match="GameEvent"):
        apply_combat_started_v1(object())  # type: ignore[arg-type]
