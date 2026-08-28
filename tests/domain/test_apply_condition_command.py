from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.commands.apply_condition import (
    ApplyConditionCommand,
    ApplyConditionPayload,
)
from dnd_engine.domain.value_objects.condition import Condition


def make_command() -> ApplyConditionCommand:
    return ApplyConditionCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=ApplyConditionPayload(
            target_id="monster_001", condition=Condition.POISONED
        ),
    )


def test_apply_condition_command_has_exact_fields_and_fixed_type() -> None:
    command = make_command()

    assert tuple(field.name for field in fields(ApplyConditionPayload)) == (
        "target_id",
        "condition",
    )
    assert tuple(field.name for field in fields(ApplyConditionCommand)) == (
        "command_id",
        "campaign_id",
        "actor_id",
        "payload",
        "type",
    )
    assert command.type == "ApplyConditionCommand"
    assert not hasattr(command, "source")
    assert not hasattr(command, "duration")
    assert not hasattr(command, "save_dc")
    assert not hasattr(command, "spell_id")
    assert not hasattr(command, "item_id")
    assert not hasattr(command, "feature_id")
    assert not hasattr(command, "stacks")
    assert not hasattr(command, "condition_instance_id")

    with pytest.raises(TypeError):
        ApplyConditionCommand(
            command_id="command_000001",
            campaign_id="campaign_001",
            actor_id="character_001",
            payload=command.payload,
            type="OtherCommand",  # type: ignore[call-arg]
        )


def test_apply_condition_command_and_payload_are_immutable() -> None:
    command = make_command()

    with pytest.raises(FrozenInstanceError):
        command.actor_id = "character_002"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        command.payload.target_id = "monster_002"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        command.payload.condition = Condition.POISONED  # type: ignore[misc]


@pytest.mark.parametrize("target_id", [1, True, 1.0, None])
def test_payload_requires_exact_string_target_id(target_id: object) -> None:
    with pytest.raises(TypeError):
        ApplyConditionPayload(  # type: ignore[arg-type]
            target_id=target_id, condition=Condition.POISONED
        )


@pytest.mark.parametrize("condition", ["poisoned", 1, None, object()])
def test_payload_rejects_non_condition_values(condition: object) -> None:
    with pytest.raises(TypeError):
        ApplyConditionPayload(  # type: ignore[arg-type]
            target_id="monster_001", condition=condition
        )


def test_payload_accepts_actual_condition() -> None:
    payload = ApplyConditionPayload(
        target_id="monster_001", condition=Condition.POISONED
    )

    assert payload.condition is Condition.POISONED


@pytest.mark.parametrize("field_name", ["command_id", "campaign_id", "actor_id"])
def test_command_requires_exact_string_ids(field_name: str) -> None:
    values: dict[str, object] = {
        "command_id": "command_000001",
        "campaign_id": "campaign_001",
        "actor_id": "character_001",
        "payload": ApplyConditionPayload(
            target_id="monster_001", condition=Condition.POISONED
        ),
    }
    values[field_name] = 1

    with pytest.raises(TypeError):
        ApplyConditionCommand(**values)  # type: ignore[arg-type]


def test_command_requires_typed_payload() -> None:
    with pytest.raises(TypeError):
        ApplyConditionCommand(
            command_id="command_000001",
            campaign_id="campaign_001",
            actor_id="character_001",
            payload={"target_id": "monster_001", "condition": "poisoned"},  # type: ignore[arg-type]
        )
