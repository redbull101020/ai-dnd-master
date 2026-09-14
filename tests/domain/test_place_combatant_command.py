from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.commands.place_combatant import (
    PlaceCombatantCommand,
    PlaceCombatantPayload,
)


def make_payload(**overrides: object) -> PlaceCombatantPayload:
    values: dict[str, object] = {
        "combat_id": "combat_001",
        "creature_id": "character_001",
        "x": 5,
        "y": 10,
    }
    values.update(overrides)
    return PlaceCombatantPayload(**values)  # type: ignore[arg-type]


def make_command(
    *, actor_id: str = "character_001", payload: PlaceCombatantPayload | None = None
) -> PlaceCombatantCommand:
    return PlaceCombatantCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id=actor_id,
        payload=payload or make_payload(),
    )


def test_place_combatant_command_has_exact_fields_and_fixed_type() -> None:
    command = make_command()

    assert tuple(field.name for field in fields(PlaceCombatantPayload)) == (
        "combat_id",
        "creature_id",
        "x",
        "y",
    )
    assert tuple(field.name for field in fields(PlaceCombatantCommand)) == (
        "command_id",
        "campaign_id",
        "actor_id",
        "payload",
        "type",
    )
    assert command.type == "PlaceCombatantCommand"


def test_place_combatant_command_and_payload_are_immutable() -> None:
    command = make_command()

    with pytest.raises(FrozenInstanceError):
        command.actor_id = "character_002"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        command.payload.x = 1  # type: ignore[misc]


@pytest.mark.parametrize("field_name", ["combat_id", "creature_id"])
@pytest.mark.parametrize("value", [1, True, 1.0, None])
def test_payload_requires_exact_string_ids(field_name: str, value: object) -> None:
    with pytest.raises(TypeError):
        make_payload(**{field_name: value})


@pytest.mark.parametrize("field_name", ["x", "y"])
@pytest.mark.parametrize("value", ["5", None, 1.0])
def test_payload_requires_exact_int_coordinates(
    field_name: str, value: object
) -> None:
    with pytest.raises(TypeError):
        make_payload(**{field_name: value})


@pytest.mark.parametrize("field_name", ["x", "y"])
def test_payload_rejects_bool_coordinates(field_name: str) -> None:
    with pytest.raises(TypeError):
        make_payload(**{field_name: True})


def test_payload_accepts_negative_coordinates() -> None:
    payload = make_payload(x=-5, y=-10)

    assert payload.x == -5
    assert payload.y == -10


@pytest.mark.parametrize("field_name", ["command_id", "campaign_id", "actor_id"])
def test_command_requires_exact_string_ids(field_name: str) -> None:
    values: dict[str, object] = {
        "command_id": "command_000001",
        "campaign_id": "campaign_001",
        "actor_id": "character_001",
        "payload": make_payload(),
    }
    values[field_name] = 1

    with pytest.raises(TypeError):
        PlaceCombatantCommand(**values)  # type: ignore[arg-type]


def test_command_requires_typed_payload() -> None:
    with pytest.raises(TypeError):
        PlaceCombatantCommand(
            command_id="command_000001",
            campaign_id="campaign_001",
            actor_id="character_001",
            payload={"combat_id": "combat_001"},  # type: ignore[arg-type]
        )


def test_actor_id_and_creature_id_may_differ() -> None:
    command = make_command(
        actor_id="character_gm",
        payload=make_payload(creature_id="monster_001"),
    )

    assert command.actor_id == "character_gm"
    assert command.payload.creature_id == "monster_001"
