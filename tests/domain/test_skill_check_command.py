from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.commands.skill_check import (
    SkillCheckCommand,
    SkillCheckPayload,
)
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.skill import Skill


def make_command() -> SkillCheckCommand:
    return SkillCheckCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=SkillCheckPayload(
            skill=Skill.INTIMIDATION,
            ability=Ability.STRENGTH,
            dc=15,
        ),
    )


def test_skill_check_command_has_exact_fields_and_fixed_type() -> None:
    command = make_command()

    assert tuple(field.name for field in fields(SkillCheckPayload)) == (
        "skill",
        "ability",
        "dc",
    )
    assert tuple(field.name for field in fields(SkillCheckCommand)) == (
        "command_id",
        "campaign_id",
        "actor_id",
        "payload",
        "type",
    )
    assert command.type == "SkillCheckCommand"

    with pytest.raises(TypeError):
        SkillCheckCommand(
            command_id="command_000001",
            campaign_id="campaign_001",
            actor_id="character_001",
            payload=command.payload,
            type="OtherCommand",  # type: ignore[call-arg]
        )


def test_skill_check_command_and_payload_are_immutable() -> None:
    command = make_command()

    with pytest.raises(FrozenInstanceError):
        command.actor_id = "character_002"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        command.payload.dc = 10  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [("skill", "intimidation"), ("ability", "strength"), ("dc", True)],
)
def test_payload_requires_canonical_runtime_types(
    field_name: str,
    invalid_value: object,
) -> None:
    values: dict[str, object] = {
        "skill": Skill.INTIMIDATION,
        "ability": Ability.STRENGTH,
        "dc": 15,
    }
    values[field_name] = invalid_value

    with pytest.raises(TypeError):
        SkillCheckPayload(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("dc", [15.0, "15", None])
def test_payload_requires_exact_integer_dc(dc: object) -> None:
    with pytest.raises(TypeError):
        SkillCheckPayload(
            skill=Skill.ATHLETICS,
            ability=Ability.STRENGTH,
            dc=dc,  # type: ignore[arg-type]
        )


def test_payload_adds_no_arbitrary_dc_range() -> None:
    assert SkillCheckPayload(Skill.ARCANA, Ability.INTELLIGENCE, -5).dc == -5
    assert SkillCheckPayload(Skill.ARCANA, Ability.INTELLIGENCE, 100).dc == 100


@pytest.mark.parametrize("field_name", ["command_id", "campaign_id", "actor_id"])
def test_command_requires_exact_string_ids(field_name: str) -> None:
    values: dict[str, object] = {
        "command_id": "command_000001",
        "campaign_id": "campaign_001",
        "actor_id": "character_001",
        "payload": SkillCheckPayload(
            Skill.INTIMIDATION,
            Ability.STRENGTH,
            15,
        ),
    }
    values[field_name] = 1

    with pytest.raises(TypeError):
        SkillCheckCommand(**values)  # type: ignore[arg-type]


def test_command_requires_typed_payload() -> None:
    with pytest.raises(TypeError):
        SkillCheckCommand(
            command_id="command_000001",
            campaign_id="campaign_001",
            actor_id="character_001",
            payload={  # type: ignore[arg-type]
                "skill": "intimidation",
                "ability": "strength",
                "dc": 15,
            },
        )
