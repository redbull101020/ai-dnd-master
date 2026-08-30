from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.commands.start_combat import (
    StartCombatCommand,
    StartCombatPayload,
)


def make_command() -> StartCombatCommand:
    return StartCombatCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=StartCombatPayload(
            combat_id="combat_001",
            participant_ids=("character_001", "monster_001"),
        ),
    )


def test_start_combat_command_has_exact_fields_and_fixed_type() -> None:
    command = make_command()

    assert tuple(field.name for field in fields(StartCombatPayload)) == (
        "combat_id",
        "participant_ids",
    )
    assert tuple(field.name for field in fields(StartCombatCommand)) == (
        "command_id",
        "campaign_id",
        "actor_id",
        "payload",
        "type",
    )
    assert command.type == "StartCombatCommand"


def test_start_combat_command_and_payload_are_immutable() -> None:
    command = make_command()

    with pytest.raises(FrozenInstanceError):
        command.actor_id = "character_002"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        command.payload.combat_id = "combat_002"  # type: ignore[misc]


@pytest.mark.parametrize("combat_id", [1, True, 1.0, None])
def test_payload_requires_exact_string_combat_id(combat_id: object) -> None:
    with pytest.raises(TypeError):
        StartCombatPayload(  # type: ignore[arg-type]
            combat_id=combat_id, participant_ids=("character_001",)
        )


@pytest.mark.parametrize(
    "participant_ids",
    [
        ["character_001"],
        ("character_001", 1),
    ],
)
def test_payload_requires_tuple_of_strings(participant_ids: object) -> None:
    with pytest.raises(TypeError):
        StartCombatPayload(  # type: ignore[arg-type]
            combat_id="combat_001", participant_ids=participant_ids
        )


def test_payload_rejects_empty_participant_ids() -> None:
    with pytest.raises(ValueError, match="empty"):
        StartCombatPayload(combat_id="combat_001", participant_ids=())


def test_payload_rejects_duplicate_participant_ids() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        StartCombatPayload(
            combat_id="combat_001",
            participant_ids=("character_001", "character_001"),
        )


@pytest.mark.parametrize("field_name", ["command_id", "campaign_id", "actor_id"])
def test_command_requires_exact_string_ids(field_name: str) -> None:
    values: dict[str, object] = {
        "command_id": "command_000001",
        "campaign_id": "campaign_001",
        "actor_id": "character_001",
        "payload": StartCombatPayload(
            combat_id="combat_001", participant_ids=("character_001",)
        ),
    }
    values[field_name] = 1

    with pytest.raises(TypeError):
        StartCombatCommand(**values)  # type: ignore[arg-type]


def test_command_requires_typed_payload() -> None:
    with pytest.raises(TypeError):
        StartCombatCommand(
            command_id="command_000001",
            campaign_id="campaign_001",
            actor_id="character_001",
            payload={"combat_id": "combat_001"},  # type: ignore[arg-type]
        )
