from dataclasses import replace
from datetime import datetime, timezone

import pytest

from dnd_engine.domain.commands.place_combatant import (
    PlaceCombatantCommand,
    PlaceCombatantPayload,
)
from dnd_engine.domain.events.place_combatant import (
    apply_combatant_placed_v1,
    build_combatant_placed_v1,
)
from dnd_engine.domain.rules.place_combatant import PlaceCombatantResult
from dnd_engine.domain.state.combat import CombatPosition, CombatState
from dnd_engine.infrastructure.persistence.json.event_serializer import (
    EventSerializer,
)


FIXED_TIMESTAMP = datetime(2026, 9, 13, 13, 0, tzinfo=timezone.utc)


def make_command(
    *,
    combat_id: str = "combat_001",
    creature_id: str = "character_001",
    actor_id: str = "character_gm",
    x: int = 5,
    y: int = 10,
) -> PlaceCombatantCommand:
    return PlaceCombatantCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id=actor_id,
        payload=PlaceCombatantPayload(
            combat_id=combat_id, creature_id=creature_id, x=x, y=y
        ),
    )


def make_outcome(
    *,
    combat_id: str = "combat_001",
    creature_id: str = "character_001",
    x: int = 5,
    y: int = 10,
) -> PlaceCombatantResult:
    return PlaceCombatantResult(
        combat_id=combat_id, creature_id=creature_id, x=x, y=y
    )


def make_combat(**overrides: object) -> CombatState:
    values: dict[str, object] = {
        "id": "combat_001",
        "round": 1,
        "order": ("character_001", "monster_001", "monster_002"),
        "active_index": 0,
    }
    values.update(overrides)
    return CombatState(**values)  # type: ignore[arg-type]


def build_event(
    command: PlaceCombatantCommand | None = None,
    outcome: PlaceCombatantResult | None = None,
) -> object:
    return build_combatant_placed_v1(
        event_id="event_000123",
        timestamp=FIXED_TIMESTAMP,
        command=command or make_command(),
        outcome=outcome or make_outcome(),
    )


# --- build_combatant_placed_v1 ------------------------------------------------


def test_builder_creates_exact_canonical_event() -> None:
    event = build_event()

    assert event.type == "CombatantPlaced"
    assert event.version == 1
    assert event.event_id == "event_000123"
    assert event.command_id == "command_000001"
    assert event.campaign_id == "campaign_001"
    assert event.timestamp is FIXED_TIMESTAMP
    assert event.actor_id == "character_gm"
    assert event.caused_by is None
    assert event.payload == {
        "combatId": "combat_001",
        "creatureId": "character_001",
        "x": 5,
        "y": 10,
    }


def test_canonical_event_is_json_serializable_round_trip() -> None:
    event = build_event()

    serialized = EventSerializer.serialize(event)
    assert EventSerializer.deserialize(serialized) == event


def test_builder_rejects_combat_id_mismatch() -> None:
    with pytest.raises(ValueError, match="combat_id"):
        build_combatant_placed_v1(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
            command=make_command(combat_id="combat_001"),
            outcome=make_outcome(combat_id="combat_002"),
        )


def test_builder_rejects_creature_id_mismatch() -> None:
    with pytest.raises(ValueError, match="creature_id"):
        build_combatant_placed_v1(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
            command=make_command(creature_id="character_001"),
            outcome=make_outcome(creature_id="monster_001"),
        )


def test_builder_rejects_x_mismatch() -> None:
    with pytest.raises(ValueError, match="outcome x"):
        build_combatant_placed_v1(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
            command=make_command(x=5),
            outcome=make_outcome(x=6),
        )


def test_builder_rejects_y_mismatch() -> None:
    with pytest.raises(ValueError, match="outcome y"):
        build_combatant_placed_v1(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
            command=make_command(y=10),
            outcome=make_outcome(y=11),
        )


def test_builder_rejects_wrong_types() -> None:
    with pytest.raises(TypeError, match="PlaceCombatantCommand"):
        build_combatant_placed_v1(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
            command=object(),  # type: ignore[arg-type]
            outcome=make_outcome(),
        )
    with pytest.raises(TypeError, match="PlaceCombatantResult"):
        build_combatant_placed_v1(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
            command=make_command(),
            outcome=object(),  # type: ignore[arg-type]
        )


# --- apply_combatant_placed_v1 -----------------------------------------------


def test_applier_appends_exactly_one_position_and_preserves_the_rest() -> None:
    existing = CombatPosition(creature_id="monster_001", x=1, y=1)
    combat = make_combat(positions=(existing,))
    event = build_event(
        command=make_command(creature_id="monster_002", x=5, y=10),
        outcome=make_outcome(creature_id="monster_002", x=5, y=10),
    )

    replacement = apply_combatant_placed_v1(combat, event)

    assert replacement is not combat
    assert replacement.positions == (
        existing,
        CombatPosition(creature_id="monster_002", x=5, y=10),
    )
    # input CombatState must not be mutated in place
    assert combat.positions == (existing,)


def test_applier_preserves_unrelated_combat_facts() -> None:
    combat = make_combat(round=3, active_index=1, action_spent=True)
    event = build_event(
        command=make_command(creature_id="monster_001"),
        outcome=make_outcome(creature_id="monster_001"),
    )

    replacement = apply_combatant_placed_v1(combat, event)

    assert replacement.id == combat.id
    assert replacement.round == combat.round
    assert replacement.order == combat.order
    assert replacement.active_index == combat.active_index
    assert replacement.action_spent == combat.action_spent


def test_applier_allows_duplicate_coordinates_across_combatants() -> None:
    existing = CombatPosition(creature_id="monster_001", x=5, y=10)
    combat = make_combat(positions=(existing,))
    event = build_event(
        command=make_command(creature_id="monster_002", x=5, y=10),
        outcome=make_outcome(creature_id="monster_002", x=5, y=10),
    )

    replacement = apply_combatant_placed_v1(combat, event)

    assert replacement.positions == (
        existing,
        CombatPosition(creature_id="monster_002", x=5, y=10),
    )


def test_applier_rejects_wrong_event_type_or_version() -> None:
    event = build_event()
    combat = make_combat()

    with pytest.raises(ValueError, match="type"):
        apply_combatant_placed_v1(combat, replace(event, type="OtherEvent"))
    with pytest.raises(ValueError, match="version"):
        apply_combatant_placed_v1(combat, replace(event, version=2))


def test_applier_rejects_missing_or_extra_payload_fields() -> None:
    combat = make_combat()
    event = build_event()

    missing = replace(
        event,
        payload={"combatId": "combat_001", "creatureId": "character_001", "x": 5},
    )
    with pytest.raises(ValueError, match="unexpected fields"):
        apply_combatant_placed_v1(combat, missing)

    extra = replace(
        event,
        payload={
            "combatId": "combat_001",
            "creatureId": "character_001",
            "x": 5,
            "y": 10,
            "extra": "x",
        },
    )
    with pytest.raises(ValueError, match="unexpected fields"):
        apply_combatant_placed_v1(combat, extra)


@pytest.mark.parametrize(
    "field_name,value",
    [
        ("combatId", 1),
        ("creatureId", 1),
        ("x", "5"),
        ("y", "10"),
        ("x", True),
        ("y", True),
    ],
)
def test_applier_rejects_wrong_primitive_payload_types(
    field_name: str, value: object
) -> None:
    combat = make_combat()
    event = build_event()
    tampered_payload = dict(event.payload)
    tampered_payload[field_name] = value
    tampered = replace(event, payload=tampered_payload)

    with pytest.raises(TypeError):
        apply_combatant_placed_v1(combat, tampered)


def test_applier_rejects_wrong_combat_id() -> None:
    combat = make_combat(id="combat_999")
    event = build_event()

    with pytest.raises(ValueError, match="combatId"):
        apply_combatant_placed_v1(combat, event)


def test_applier_rejects_creature_absent_from_combat_order() -> None:
    combat = make_combat(order=("character_001", "monster_001"))
    event = build_event(
        command=make_command(creature_id="monster_999"),
        outcome=make_outcome(creature_id="monster_999"),
    )

    with pytest.raises(ValueError, match="order"):
        apply_combatant_placed_v1(combat, event)


def test_applier_rejects_creature_already_positioned() -> None:
    existing = CombatPosition(creature_id="monster_001", x=1, y=1)
    combat = make_combat(positions=(existing,))
    event = build_event(
        command=make_command(creature_id="monster_001", x=9, y=9),
        outcome=make_outcome(creature_id="monster_001", x=9, y=9),
    )

    with pytest.raises(ValueError, match="already"):
        apply_combatant_placed_v1(combat, event)


def test_applier_rejects_wrong_types() -> None:
    with pytest.raises(TypeError, match="CombatState"):
        apply_combatant_placed_v1(object(), build_event())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="GameEvent"):
        apply_combatant_placed_v1(make_combat(), object())  # type: ignore[arg-type]
