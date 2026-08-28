from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.commands.attack import AttackCommand, AttackPayload


def make_command() -> AttackCommand:
    return AttackCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=AttackPayload(target_id="monster_001"),
    )


def test_attack_command_has_exact_fields_and_fixed_type() -> None:
    command = make_command()

    assert tuple(field.name for field in fields(AttackPayload)) == ("target_id",)
    assert tuple(field.name for field in fields(AttackCommand)) == (
        "command_id",
        "campaign_id",
        "actor_id",
        "payload",
        "type",
    )
    assert command.type == "AttackCommand"
    assert not hasattr(command, "weapon_id")
    assert not hasattr(command, "attack_bonus")
    assert not hasattr(command, "roll_mode")

    with pytest.raises(TypeError):
        AttackCommand(
            command_id="command_000001",
            campaign_id="campaign_001",
            actor_id="character_001",
            payload=command.payload,
            type="OtherCommand",  # type: ignore[call-arg]
        )


def test_attack_command_and_payload_are_immutable() -> None:
    command = make_command()

    with pytest.raises(FrozenInstanceError):
        command.actor_id = "character_002"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        command.payload.target_id = "monster_002"  # type: ignore[misc]


@pytest.mark.parametrize("target_id", [1, True, 1.0, None])
def test_payload_requires_exact_string_target_id(target_id: object) -> None:
    with pytest.raises(TypeError):
        AttackPayload(target_id=target_id)  # type: ignore[arg-type]


@pytest.mark.parametrize("field_name", ["command_id", "campaign_id", "actor_id"])
def test_command_requires_exact_string_ids(field_name: str) -> None:
    values: dict[str, object] = {
        "command_id": "command_000001",
        "campaign_id": "campaign_001",
        "actor_id": "character_001",
        "payload": AttackPayload(target_id="monster_001"),
    }
    values[field_name] = 1

    with pytest.raises(TypeError):
        AttackCommand(**values)  # type: ignore[arg-type]


def test_command_requires_typed_payload() -> None:
    with pytest.raises(TypeError):
        AttackCommand(
            command_id="command_000001",
            campaign_id="campaign_001",
            actor_id="character_001",
            payload={"target_id": "monster_001"},  # type: ignore[arg-type]
        )
