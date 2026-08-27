from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timedelta, timezone

import pytest

from dnd_engine.domain.commands.skill_check import (
    SkillCheckCommand,
    SkillCheckPayload,
)
from dnd_engine.domain.events.skill_check import (
    SkillCheckResolvedPayloadV1,
    build_skill_check_resolved_v1,
)
from dnd_engine.domain.rules.skill_check import SkillCheckResult
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.d20 import D20Roll, RollMode
from dnd_engine.domain.value_objects.skill import Skill
from dnd_engine.infrastructure.persistence.json.event_serializer import EventSerializer


FIXED_TIMESTAMP = datetime(2026, 8, 27, 10, 30, tzinfo=timezone.utc)


def make_command(
    *,
    skill: Skill = Skill.INTIMIDATION,
    ability: Ability = Ability.STRENGTH,
    dc: int = 15,
) -> SkillCheckCommand:
    return SkillCheckCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=SkillCheckPayload(skill=skill, ability=ability, dc=dc),
    )


def make_outcome(
    *,
    skill: Skill = Skill.INTIMIDATION,
    ability: Ability = Ability.STRENGTH,
    dc: int = 15,
) -> SkillCheckResult:
    return SkillCheckResult(
        skill=skill,
        ability=ability,
        dc=dc,
        roll=D20Roll(mode=RollMode.NORMAL, rolls=(9,), selected=9),
        ability_modifier=3,
        proficiency_bonus=3,
        total=15,
        succeeded=15 >= dc,
    )


def make_payload() -> SkillCheckResolvedPayloadV1:
    return SkillCheckResolvedPayloadV1(
        skill=Skill.INTIMIDATION,
        ability=Ability.STRENGTH,
        dc=15,
        roll=D20Roll(mode=RollMode.NORMAL, rolls=(9,), selected=9),
        ability_modifier=3,
        proficiency_bonus=3,
        total=15,
        succeeded=True,
    )


def test_payload_has_exact_fields_and_is_immutable() -> None:
    payload = make_payload()

    assert tuple(field.name for field in fields(payload)) == (
        "skill",
        "ability",
        "dc",
        "roll",
        "ability_modifier",
        "proficiency_bonus",
        "total",
        "succeeded",
    )
    with pytest.raises(FrozenInstanceError):
        payload.total = 14  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("skill", "intimidation"),
        ("ability", "strength"),
        ("dc", True),
        ("roll", object()),
        ("ability_modifier", True),
        ("proficiency_bonus", True),
        ("total", True),
        ("succeeded", 1),
    ],
)
def test_payload_rejects_wrong_runtime_types(
    field_name: str,
    invalid_value: object,
) -> None:
    values: dict[str, object] = {
        "skill": Skill.INTIMIDATION,
        "ability": Ability.STRENGTH,
        "dc": 15,
        "roll": D20Roll(mode=RollMode.NORMAL, rolls=(9,), selected=9),
        "ability_modifier": 3,
        "proficiency_bonus": 3,
        "total": 15,
        "succeeded": True,
    }
    values[field_name] = invalid_value

    with pytest.raises(TypeError):
        SkillCheckResolvedPayloadV1(**values)  # type: ignore[arg-type]


def test_payload_enforces_semantic_invariants() -> None:
    values: dict[str, object] = {
        "skill": Skill.INTIMIDATION,
        "ability": Ability.STRENGTH,
        "dc": 15,
        "roll": D20Roll(mode=RollMode.NORMAL, rolls=(9,), selected=9),
        "ability_modifier": 3,
        "proficiency_bonus": 3,
        "total": 15,
        "succeeded": True,
    }

    for field_name, invalid_value, match in (
        ("proficiency_bonus", -1, "negative"),
        ("total", 14, "total"),
        ("succeeded", False, "succeeded"),
    ):
        with pytest.raises(ValueError, match=match):
            SkillCheckResolvedPayloadV1(  # type: ignore[arg-type]
                **(values | {field_name: invalid_value})
            )


def test_builder_creates_exact_v1_event_and_serializable_payload() -> None:
    event = build_skill_check_resolved_v1(
        event_id="event_000123",
        timestamp=FIXED_TIMESTAMP,
        command=make_command(),
        outcome=make_outcome(),
    )

    assert event.type == "SkillCheckResolved"
    assert event.version == 1
    assert event.command_id == "command_000001"
    assert event.campaign_id == "campaign_001"
    assert event.actor_id == "character_001"
    assert event.caused_by is None
    assert event.payload == {
        "skill": "intimidation",
        "ability": "strength",
        "dc": 15,
        "roll": {"mode": "normal", "rolls": (9,), "selected": 9},
        "abilityModifier": 3,
        "proficiencyBonus": 3,
        "total": 15,
        "succeeded": True,
    }
    assert EventSerializer.serialize(event) == {
        "eventId": "event_000123",
        "commandId": "command_000001",
        "type": "SkillCheckResolved",
        "version": 1,
        "campaignId": "campaign_001",
        "timestamp": "2026-08-27T10:30:00Z",
        "actorId": "character_001",
        "causedBy": None,
        "payload": {
            "skill": "intimidation",
            "ability": "strength",
            "dc": 15,
            "roll": {"mode": "normal", "rolls": [9], "selected": 9},
            "abilityModifier": 3,
            "proficiencyBonus": 3,
            "total": 15,
            "succeeded": True,
        },
    }


@pytest.mark.parametrize(
    ("command", "outcome", "error", "match"),
    [
        (object(), make_outcome(), TypeError, "SkillCheckCommand"),
        (make_command(), object(), TypeError, "SkillCheckResult"),
        (
            make_command(),
            make_outcome(skill=Skill.ATHLETICS),
            ValueError,
            "skill",
        ),
        (
            make_command(),
            make_outcome(ability=Ability.CHARISMA),
            ValueError,
            "ability",
        ),
        (make_command(), make_outcome(dc=14), ValueError, "dc"),
    ],
)
def test_builder_rejects_wrong_types_and_command_outcome_mismatch(
    command: object,
    outcome: object,
    error: type[Exception],
    match: str,
) -> None:
    with pytest.raises(error, match=match):
        build_skill_check_resolved_v1(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
            command=command,  # type: ignore[arg-type]
            outcome=outcome,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("event_id", "timestamp", "error"),
    [
        (1, FIXED_TIMESTAMP, TypeError),
        ("event_000123", datetime(2026, 8, 27, 10, 30), ValueError),
        (
            "event_000123",
            datetime(
                2026,
                8,
                27,
                13,
                30,
                tzinfo=timezone(timedelta(hours=3)),
            ),
            ValueError,
        ),
    ],
)
def test_builder_preserves_intrinsic_game_event_validation(
    event_id: object,
    timestamp: datetime,
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        build_skill_check_resolved_v1(
            event_id=event_id,  # type: ignore[arg-type]
            timestamp=timestamp,
            command=make_command(),
            outcome=make_outcome(),
        )
