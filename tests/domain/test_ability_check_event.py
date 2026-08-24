from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timezone

import pytest

from dnd_engine.domain.commands.ability_check import (
    AbilityCheckCommand,
    AbilityCheckPayload,
)
from dnd_engine.domain.events.ability_check import (
    AbilityCheckResolvedPayloadV1,
    build_ability_check_resolved_v1,
)
from dnd_engine.domain.rules.ability_check import AbilityCheckResult
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.dice_roll import DiceRoll
from dnd_engine.infrastructure.persistence.json.event_serializer import EventSerializer


FIXED_TIMESTAMP = datetime(2026, 8, 24, 12, 30, tzinfo=timezone.utc)


def command(
    *,
    ability: Ability = Ability.STRENGTH,
    dc: int = 15,
) -> AbilityCheckCommand:
    return AbilityCheckCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=AbilityCheckPayload(ability=ability, dc=dc),
    )


def outcome(
    *,
    ability: Ability = Ability.STRENGTH,
    dc: int = 15,
) -> AbilityCheckResult:
    return AbilityCheckResult(
        ability=ability,
        dc=dc,
        roll=DiceRoll(expression="1d20", rolls=(7,), total=7),
        modifier=-1,
        total=6,
        succeeded=False,
    )


def test_typed_payload_has_exact_fields_and_is_immutable() -> None:
    payload = AbilityCheckResolvedPayloadV1(
        ability=Ability.STRENGTH,
        dc=15,
        roll=DiceRoll(expression="1d20", rolls=(7,), total=7),
        modifier=-1,
        total=6,
        succeeded=False,
    )

    assert tuple(field.name for field in fields(payload)) == (
        "ability",
        "dc",
        "roll",
        "modifier",
        "total",
        "succeeded",
    )
    with pytest.raises(FrozenInstanceError):
        payload.total = 7  # type: ignore[misc]


def test_builder_sets_exact_envelope_and_injected_metadata() -> None:
    event = build_ability_check_resolved_v1(
        event_id="event_000123",
        timestamp=FIXED_TIMESTAMP,
        command=command(),
        outcome=outcome(),
    )

    assert event.event_id == "event_000123"
    assert event.timestamp is FIXED_TIMESTAMP
    assert event.type == "AbilityCheckResolved"
    assert event.version == 1
    assert event.command_id == "command_000001"
    assert event.campaign_id == "campaign_001"
    assert event.actor_id == "character_001"
    assert event.caused_by is None


def test_builder_creates_exact_payload_from_outcome() -> None:
    result = outcome()

    event = build_ability_check_resolved_v1(
        event_id="event_000123",
        timestamp=FIXED_TIMESTAMP,
        command=command(),
        outcome=result,
    )

    assert event.payload == {
        "ability": "strength",
        "dc": 15,
        "roll": {
            "expression": "1d20",
            "rolls": (7,),
            "total": 7,
        },
        "modifier": -1,
        "total": 6,
        "succeeded": False,
    }
    assert event.payload["roll"]["rolls"] == result.roll.rolls  # type: ignore[index]


def test_builder_payload_uses_existing_event_serializer_shape() -> None:
    event = build_ability_check_resolved_v1(
        event_id="event_000123",
        timestamp=FIXED_TIMESTAMP,
        command=command(),
        outcome=outcome(),
    )

    assert EventSerializer.serialize(event)["payload"] == {
        "ability": "strength",
        "dc": 15,
        "roll": {
            "expression": "1d20",
            "rolls": [7],
            "total": 7,
        },
        "modifier": -1,
        "total": 6,
        "succeeded": False,
    }


@pytest.mark.parametrize(
    ("event_outcome", "message"),
    [
        (outcome(ability=Ability.DEXTERITY), "ability"),
        (outcome(dc=16), "dc"),
    ],
)
def test_builder_rejects_outcome_command_mismatch(
    event_outcome: AbilityCheckResult,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        build_ability_check_resolved_v1(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
            command=command(),
            outcome=event_outcome,
        )
