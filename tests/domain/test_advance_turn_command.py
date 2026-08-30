from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.commands.advance_turn import (
    AdvanceTurnCommand,
    AdvanceTurnPayload,
)


def make_command() -> AdvanceTurnCommand:
    return AdvanceTurnCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=AdvanceTurnPayload(combat_id="combat_001"),
    )


def test_advance_turn_command_has_exact_fields_and_fixed_type() -> None:
    command = make_command()

    assert tuple(field.name for field in fields(AdvanceTurnPayload)) == (
        "combat_id",
    )
    assert tuple(field.name for field in fields(AdvanceTurnCommand)) == (
        "command_id",
        "campaign_id",
        "actor_id",
        "payload",
        "type",
    )
    assert command.type == "AdvanceTurnCommand"


def test_advance_turn_command_and_payload_are_immutable() -> None:
    command = make_command()

    with pytest.raises(FrozenInstanceError):
        command.actor_id = "character_002"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        command.payload.combat_id = "combat_002"  # type: ignore[misc]


@pytest.mark.parametrize("combat_id", [1, True, 1.0, None])
def test_payload_requires_exact_string_combat_id(combat_id: object) -> None:
    with pytest.raises(TypeError):
        AdvanceTurnPayload(combat_id=combat_id)  # type: ignore[arg-type]


@pytest.mark.parametrize("field_name", ["command_id", "campaign_id", "actor_id"])
def test_command_requires_exact_string_ids(field_name: str) -> None:
    values: dict[str, object] = {
        "command_id": "command_000001",
        "campaign_id": "campaign_001",
        "actor_id": "character_001",
        "payload": AdvanceTurnPayload(combat_id="combat_001"),
    }
    values[field_name] = 1

    with pytest.raises(TypeError):
        AdvanceTurnCommand(**values)  # type: ignore[arg-type]


def test_command_requires_typed_payload() -> None:
    with pytest.raises(TypeError):
        AdvanceTurnCommand(
            command_id="command_000001",
            campaign_id="campaign_001",
            actor_id="character_001",
            payload={"combat_id": "combat_001"},  # type: ignore[arg-type]
        )
