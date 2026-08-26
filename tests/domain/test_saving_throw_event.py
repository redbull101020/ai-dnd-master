from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timezone

import pytest

from dnd_engine.domain.commands.saving_throw import (
    SavingThrowCommand,
    SavingThrowPayload,
)
from dnd_engine.domain.events.saving_throw import (
    SavingThrowResolvedPayloadV1,
    build_saving_throw_resolved_v1,
)
from dnd_engine.domain.rules.saving_throw import SavingThrowResult
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.d20 import D20Roll, RollMode
from dnd_engine.infrastructure.persistence.json.event_serializer import EventSerializer


FIXED_TIMESTAMP = datetime(2026, 8, 26, 14, 30, tzinfo=timezone.utc)


def make_command(
    *,
    ability: Ability = Ability.CONSTITUTION,
    dc: int = 15,
) -> SavingThrowCommand:
    return SavingThrowCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=SavingThrowPayload(ability=ability, dc=dc),
    )


def make_outcome(
    *,
    ability: Ability = Ability.CONSTITUTION,
    dc: int = 15,
) -> SavingThrowResult:
    return SavingThrowResult(
        ability=ability,
        dc=dc,
        roll=D20Roll(mode=RollMode.NORMAL, rolls=(10,), selected=10),
        ability_modifier=2,
        proficiency_bonus=3,
        total=15,
        succeeded=15 >= dc,
    )


def make_payload() -> SavingThrowResolvedPayloadV1:
    return SavingThrowResolvedPayloadV1(
        ability=Ability.CONSTITUTION,
        dc=15,
        roll=D20Roll(mode=RollMode.NORMAL, rolls=(10,), selected=10),
        ability_modifier=2,
        proficiency_bonus=3,
        total=15,
        succeeded=True,
    )


def test_payload_has_exact_fields_and_is_immutable() -> None:
    payload = make_payload()

    assert tuple(field.name for field in fields(payload)) == (
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
        ("ability", "constitution"),
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
        "ability": Ability.CONSTITUTION,
        "dc": 15,
        "roll": D20Roll(mode=RollMode.NORMAL, rolls=(10,), selected=10),
        "ability_modifier": 2,
        "proficiency_bonus": 3,
        "total": 15,
        "succeeded": True,
    }
    values[field_name] = invalid_value

    with pytest.raises(TypeError):
        SavingThrowResolvedPayloadV1(**values)  # type: ignore[arg-type]


def test_payload_enforces_semantic_invariants() -> None:
    values: dict[str, object] = {
        "ability": Ability.CONSTITUTION,
        "dc": 15,
        "roll": D20Roll(mode=RollMode.NORMAL, rolls=(10,), selected=10),
        "ability_modifier": 2,
        "proficiency_bonus": 3,
        "total": 15,
        "succeeded": True,
    }

    for field_name, invalid_value, match in (
        ("proficiency_bonus", -1, "negative"),
        ("total", 14, "total"),
        ("succeeded", False, "succeeded"),
    ):
        invalid = values | {field_name: invalid_value}
        with pytest.raises(ValueError, match=match):
            SavingThrowResolvedPayloadV1(**invalid)  # type: ignore[arg-type]


def test_builder_creates_exact_v1_event_and_serializable_payload() -> None:
    event = build_saving_throw_resolved_v1(
        event_id="event_000123",
        timestamp=FIXED_TIMESTAMP,
        command=make_command(),
        outcome=make_outcome(),
    )

    assert event.type == "SavingThrowResolved"
    assert event.version == 1
    assert event.command_id == "command_000001"
    assert event.campaign_id == "campaign_001"
    assert event.actor_id == "character_001"
    assert event.caused_by is None
    assert event.payload == {
        "ability": "constitution",
        "dc": 15,
        "roll": {"mode": "normal", "rolls": (10,), "selected": 10},
        "abilityModifier": 2,
        "proficiencyBonus": 3,
        "total": 15,
        "succeeded": True,
    }
    assert EventSerializer.serialize(event) == {
        "eventId": "event_000123",
        "commandId": "command_000001",
        "type": "SavingThrowResolved",
        "version": 1,
        "campaignId": "campaign_001",
        "timestamp": "2026-08-26T14:30:00Z",
        "actorId": "character_001",
        "causedBy": None,
        "payload": {
            "ability": "constitution",
            "dc": 15,
            "roll": {"mode": "normal", "rolls": [10], "selected": 10},
            "abilityModifier": 2,
            "proficiencyBonus": 3,
            "total": 15,
            "succeeded": True,
        },
    }


@pytest.mark.parametrize(
    ("command", "outcome", "error"),
    [
        (object(), make_outcome(), TypeError),
        (make_command(), object(), TypeError),
        (make_command(), make_outcome(ability=Ability.WISDOM), ValueError),
        (make_command(), make_outcome(dc=14), ValueError),
    ],
)
def test_builder_rejects_wrong_types_and_command_outcome_mismatch(
    command: object,
    outcome: object,
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        build_saving_throw_resolved_v1(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
            command=command,  # type: ignore[arg-type]
            outcome=outcome,  # type: ignore[arg-type]
        )
