from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.commands.saving_throw import (
    SavingThrowCommand,
    SavingThrowPayload,
)
from dnd_engine.domain.value_objects.ability import Ability


def make_command() -> SavingThrowCommand:
    return SavingThrowCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=SavingThrowPayload(ability=Ability.CONSTITUTION, dc=15),
    )


def test_saving_throw_command_has_exact_fields_and_fixed_type() -> None:
    command = make_command()

    assert tuple(field.name for field in fields(SavingThrowPayload)) == (
        "ability",
        "dc",
    )
    assert tuple(field.name for field in fields(SavingThrowCommand)) == (
        "command_id",
        "campaign_id",
        "actor_id",
        "payload",
        "type",
    )
    assert command.type == "SavingThrowCommand"

    with pytest.raises(TypeError):
        SavingThrowCommand(
            command_id="command_000001",
            campaign_id="campaign_001",
            actor_id="character_001",
            payload=command.payload,
            type="OtherCommand",  # type: ignore[call-arg]
        )


def test_saving_throw_command_and_payload_are_immutable() -> None:
    command = make_command()

    with pytest.raises(FrozenInstanceError):
        command.actor_id = "character_002"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        command.payload.dc = 10  # type: ignore[misc]


def test_payload_requires_actual_ability() -> None:
    with pytest.raises(TypeError):
        SavingThrowPayload(ability="constitution", dc=15)  # type: ignore[arg-type]


@pytest.mark.parametrize("dc", [True, 15.0, "15", None])
def test_payload_requires_exact_integer_dc(dc: object) -> None:
    with pytest.raises(TypeError):
        SavingThrowPayload(ability=Ability.CONSTITUTION, dc=dc)  # type: ignore[arg-type]


def test_payload_adds_no_arbitrary_dc_range() -> None:
    assert SavingThrowPayload(ability=Ability.WISDOM, dc=-5).dc == -5
    assert SavingThrowPayload(ability=Ability.WISDOM, dc=100).dc == 100


@pytest.mark.parametrize("field_name", ["command_id", "campaign_id", "actor_id"])
def test_command_requires_exact_string_ids(field_name: str) -> None:
    values: dict[str, object] = {
        "command_id": "command_000001",
        "campaign_id": "campaign_001",
        "actor_id": "character_001",
        "payload": SavingThrowPayload(ability=Ability.CONSTITUTION, dc=15),
    }
    values[field_name] = 1

    with pytest.raises(TypeError):
        SavingThrowCommand(**values)  # type: ignore[arg-type]


def test_command_requires_typed_payload() -> None:
    with pytest.raises(TypeError):
        SavingThrowCommand(
            command_id="command_000001",
            campaign_id="campaign_001",
            actor_id="character_001",
            payload={"ability": "constitution", "dc": 15},  # type: ignore[arg-type]
        )
