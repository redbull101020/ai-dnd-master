from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.commands.healing import (
    ApplyHealingCommand,
    ApplyHealingPayload,
)


def make_command() -> ApplyHealingCommand:
    return ApplyHealingCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=ApplyHealingPayload(target_id="monster_001", amount=5),
    )


def test_healing_command_has_exact_fields_and_fixed_type() -> None:
    command = make_command()

    assert tuple(field.name for field in fields(ApplyHealingPayload)) == (
        "target_id",
        "amount",
    )
    assert tuple(field.name for field in fields(ApplyHealingCommand)) == (
        "command_id",
        "campaign_id",
        "actor_id",
        "payload",
        "type",
    )
    assert command.type == "ApplyHealingCommand"
    for absent_field in (
        "new_hp",
        "max_hp",
        "applied_amount",
        "source",
        "spell_id",
        "item_id",
        "resource_id",
    ):
        assert not hasattr(command, absent_field)

    with pytest.raises(TypeError):
        ApplyHealingCommand(
            command_id="command_000001",
            campaign_id="campaign_001",
            actor_id="character_001",
            payload=command.payload,
            type="OtherCommand",  # type: ignore[call-arg]
        )


def test_healing_command_and_payload_are_immutable() -> None:
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
        ApplyHealingPayload(target_id=target_id, amount=5)  # type: ignore[arg-type]


@pytest.mark.parametrize("amount", [1.0, "5", None])
def test_payload_requires_exact_integer_amount(amount: object) -> None:
    with pytest.raises(TypeError):
        ApplyHealingPayload(target_id="monster_001", amount=amount)  # type: ignore[arg-type]


def test_payload_rejects_bool_amount() -> None:
    with pytest.raises(TypeError):
        ApplyHealingPayload(target_id="monster_001", amount=True)  # type: ignore[arg-type]


def test_payload_accepts_amount_equal_to_one() -> None:
    payload = ApplyHealingPayload(target_id="monster_001", amount=1)

    assert payload.amount == 1


@pytest.mark.parametrize("amount", [0, -1])
def test_payload_rejects_non_positive_amount(amount: int) -> None:
    with pytest.raises(ValueError, match="amount"):
        ApplyHealingPayload(target_id="monster_001", amount=amount)


@pytest.mark.parametrize("field_name", ["command_id", "campaign_id", "actor_id"])
def test_command_requires_exact_string_ids(field_name: str) -> None:
    values: dict[str, object] = {
        "command_id": "command_000001",
        "campaign_id": "campaign_001",
        "actor_id": "character_001",
        "payload": ApplyHealingPayload(target_id="monster_001", amount=5),
    }
    values[field_name] = 1

    with pytest.raises(TypeError):
        ApplyHealingCommand(**values)  # type: ignore[arg-type]


def test_command_requires_typed_payload() -> None:
    with pytest.raises(TypeError):
        ApplyHealingCommand(
            command_id="command_000001",
            campaign_id="campaign_001",
            actor_id="character_001",
            payload={"target_id": "monster_001", "amount": 5},  # type: ignore[arg-type]
        )
