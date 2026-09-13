from dataclasses import replace
from datetime import datetime, timezone

import pytest

from dnd_engine.domain.commands.end_combat import (
    EndCombatCommand,
    EndCombatPayload,
)
from dnd_engine.domain.events.end_combat import (
    apply_combat_ended_v1,
    build_combat_ended_v1,
)
from dnd_engine.domain.rules.end_combat import EndCombatResult
from dnd_engine.domain.state.combat import CombatState
from dnd_engine.infrastructure.persistence.json.event_serializer import (
    EventSerializer,
)


FIXED_TIMESTAMP = datetime(2026, 9, 13, 13, 0, tzinfo=timezone.utc)


def make_command(*, combat_id: str = "combat_001") -> EndCombatCommand:
    return EndCombatCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=EndCombatPayload(combat_id=combat_id),
    )


def make_outcome(*, combat_id: str = "combat_001") -> EndCombatResult:
    return EndCombatResult(combat_id=combat_id)


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
    command: EndCombatCommand | None = None,
    outcome: EndCombatResult | None = None,
) -> object:
    return build_combat_ended_v1(
        event_id="event_000123",
        timestamp=FIXED_TIMESTAMP,
        command=command or make_command(),
        outcome=outcome or make_outcome(),
    )


def test_builder_creates_exact_canonical_event() -> None:
    event = build_event()

    assert event.type == "CombatEnded"
    assert event.version == 1
    assert event.command_id == "command_000001"
    assert event.campaign_id == "campaign_001"
    assert event.timestamp is FIXED_TIMESTAMP
    assert event.actor_id == "character_001"
    assert event.caused_by is None
    assert event.payload == {"combatId": "combat_001"}


def test_canonical_event_is_json_serializable_round_trip() -> None:
    event = build_event()

    serialized = EventSerializer.serialize(event)
    assert EventSerializer.deserialize(serialized) == event


def test_builder_rejects_combat_id_mismatch() -> None:
    with pytest.raises(ValueError, match="combat_id"):
        build_combat_ended_v1(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
            command=make_command(combat_id="combat_001"),
            outcome=make_outcome(combat_id="combat_002"),
        )


def test_builder_rejects_wrong_types() -> None:
    with pytest.raises(TypeError, match="EndCombatCommand"):
        build_combat_ended_v1(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
            command=object(),  # type: ignore[arg-type]
            outcome=make_outcome(),
        )
    with pytest.raises(TypeError, match="EndCombatResult"):
        build_combat_ended_v1(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
            command=make_command(),
            outcome=object(),  # type: ignore[arg-type]
        )


# --- apply_combat_ended_v1 ---------------------------------------------------


def test_applier_returns_none_as_replacement_combat_projection() -> None:
    combat = make_combat()
    event = build_event()

    replacement = apply_combat_ended_v1(combat, event)

    assert replacement is None


def test_applier_rejects_combat_id_mismatch() -> None:
    combat = make_combat(id="combat_999")
    event = build_event()

    with pytest.raises(ValueError, match="combatId"):
        apply_combat_ended_v1(combat, event)


def test_applier_rejects_wrong_event_type_or_version() -> None:
    event = build_event()
    combat = make_combat()

    with pytest.raises(ValueError, match="type"):
        apply_combat_ended_v1(combat, replace(event, type="OtherEvent"))
    with pytest.raises(ValueError, match="version"):
        apply_combat_ended_v1(combat, replace(event, version=2))


def test_applier_rejects_unexpected_payload_fields() -> None:
    combat = make_combat()
    event = build_event()
    tampered = replace(event, payload={"combatId": "combat_001", "extra": "x"})

    with pytest.raises(ValueError, match="unexpected fields"):
        apply_combat_ended_v1(combat, tampered)


def test_applier_rejects_wrong_types() -> None:
    with pytest.raises(TypeError, match="CombatState"):
        apply_combat_ended_v1(object(), build_event())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="GameEvent"):
        apply_combat_ended_v1(make_combat(), object())  # type: ignore[arg-type]
