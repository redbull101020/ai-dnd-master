from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.commands.damage import ApplyDamageCommand, ApplyDamagePayload


def make_command() -> ApplyDamageCommand:
    return ApplyDamageCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=ApplyDamagePayload(target_id="monster_001", amount=5),
    )


def test_damage_command_has_exact_fields_and_fixed_type() -> None:
    command = make_command()

    assert tuple(field.name for field in fields(ApplyDamagePayload)) == (
        "target_id",
        "amount",
    )
    assert tuple(field.name for field in fields(ApplyDamageCommand)) == (
        "command_id",
        "campaign_id",
        "actor_id",
        "payload",
        "type",
    )
    assert command.type == "ApplyDamageCommand"
    assert not hasattr(command, "new_hp")
    assert not hasattr(command, "damage_type")
    assert not hasattr(command, "weapon_id")
    assert not hasattr(command, "attack_id")
    assert not hasattr(command, "critical")
    assert not hasattr(command, "source")
    assert not hasattr(command, "rolls")

    with pytest.raises(TypeError):
        ApplyDamageCommand(
            command_id="command_000001",
            campaign_id="campaign_001",
            actor_id="character_001",
            payload=command.payload,
            type="OtherCommand",  # type: ignore[call-arg]
        )


def test_damage_command_and_payload_are_immutable() -> None:
    command = make_command()

    with pytest.raises(FrozenInstanceError):
        command.actor_id = "character_002"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        command.payload.target_id = "monster_002"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        command.payload.amount = 10  # type: ignore[misc]


@pytest.mark.parametrize("target_id", [1, True, 1.0, None])
def test_payload_requires_exact_string_target_id(target_id: object) -> None:
    with pytest.raises(TypeError):
        ApplyDamagePayload(target_id=target_id, amount=5)  # type: ignore[arg-type]


@pytest.mark.parametrize("amount", [1.0, "5", None])
def test_payload_requires_exact_integer_amount(amount: object) -> None:
    with pytest.raises(TypeError):
        ApplyDamagePayload(target_id="monster_001", amount=amount)  # type: ignore[arg-type]


def test_payload_rejects_bool_amount() -> None:
    with pytest.raises(TypeError):
        ApplyDamagePayload(target_id="monster_001", amount=True)  # type: ignore[arg-type]


def test_payload_accepts_amount_equal_to_one() -> None:
    payload = ApplyDamagePayload(target_id="monster_001", amount=1)

    assert payload.amount == 1


def test_payload_rejects_zero_amount() -> None:
    with pytest.raises(ValueError, match="amount"):
        ApplyDamagePayload(target_id="monster_001", amount=0)


def test_payload_rejects_negative_amount() -> None:
    with pytest.raises(ValueError, match="amount"):
        ApplyDamagePayload(target_id="monster_001", amount=-1)


@pytest.mark.parametrize("field_name", ["command_id", "campaign_id", "actor_id"])
def test_command_requires_exact_string_ids(field_name: str) -> None:
    values: dict[str, object] = {
        "command_id": "command_000001",
        "campaign_id": "campaign_001",
        "actor_id": "character_001",
        "payload": ApplyDamagePayload(target_id="monster_001", amount=5),
    }
    values[field_name] = 1

    with pytest.raises(TypeError):
        ApplyDamageCommand(**values)  # type: ignore[arg-type]


def test_command_requires_typed_payload() -> None:
    with pytest.raises(TypeError):
        ApplyDamageCommand(
            command_id="command_000001",
            campaign_id="campaign_001",
            actor_id="character_001",
            payload={"target_id": "monster_001", "amount": 5},  # type: ignore[arg-type]
        )
