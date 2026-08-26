from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timezone
from typing import Callable

import pytest

from dnd_engine.domain.commands.ability_check import (
    AbilityCheckCommand,
    AbilityCheckPayload,
)
from dnd_engine.domain.events.ability_check import (
    AbilityCheckResolvedPayloadV1,
    AbilityCheckResolvedPayloadV2,
    build_ability_check_resolved_v1,
    build_ability_check_resolved_v2,
)
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.rules.ability_check import AbilityCheckResult
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.d20 import D20Roll, RollMode
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
    mode: RollMode = RollMode.NORMAL,
) -> AbilityCheckResult:
    rolls = (7,) if mode is RollMode.NORMAL else (7, 16)
    selected = 16 if mode is RollMode.ADVANTAGE else 7
    total = selected - 1
    return AbilityCheckResult(
        ability=ability,
        dc=dc,
        roll=D20Roll(mode=mode, rolls=rolls, selected=selected),
        modifier=-1,
        total=total,
        succeeded=total >= dc,
    )


def test_v1_typed_payload_has_exact_legacy_fields_and_is_immutable() -> None:
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


def test_v1_builder_sets_exact_envelope_and_injected_metadata() -> None:
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


def test_v1_builder_preserves_exact_legacy_normal_payload() -> None:
    event = build_ability_check_resolved_v1(
        event_id="event_000123",
        timestamp=FIXED_TIMESTAMP,
        command=command(),
        outcome=outcome(),
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


@pytest.mark.parametrize("mode", [RollMode.ADVANTAGE, RollMode.DISADVANTAGE])
def test_v1_builder_rejects_non_normal_roll_modes(mode: RollMode) -> None:
    with pytest.raises(ValueError, match="only normal"):
        build_ability_check_resolved_v1(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
            command=command(),
            outcome=outcome(mode=mode),
        )


def test_v2_typed_payload_has_exact_fields_and_is_immutable() -> None:
    result = outcome(mode=RollMode.ADVANTAGE)
    payload = AbilityCheckResolvedPayloadV2(
        ability=result.ability,
        dc=result.dc,
        roll=result.roll,
        modifier=result.modifier,
        total=result.total,
        succeeded=result.succeeded,
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
        payload.total = 16  # type: ignore[misc]


def test_v2_builder_creates_canonical_payload_and_serializer_shape() -> None:
    result = outcome(mode=RollMode.ADVANTAGE)
    event = build_ability_check_resolved_v2(
        event_id="event_000123",
        timestamp=FIXED_TIMESTAMP,
        command=command(),
        outcome=result,
    )

    assert event.type == "AbilityCheckResolved"
    assert event.version == 2
    assert event.payload == {
        "ability": "strength",
        "dc": 15,
        "roll": {
            "mode": "advantage",
            "rolls": (7, 16),
            "selected": 16,
        },
        "modifier": -1,
        "total": 15,
        "succeeded": True,
    }
    assert EventSerializer.serialize(event)["payload"] == {
        "ability": "strength",
        "dc": 15,
        "roll": {
            "mode": "advantage",
            "rolls": [7, 16],
            "selected": 16,
        },
        "modifier": -1,
        "total": 15,
        "succeeded": True,
    }


@pytest.mark.parametrize(
    ("event_outcome", "message"),
    [
        (outcome(ability=Ability.DEXTERITY), "ability"),
        (outcome(dc=16), "dc"),
    ],
)
@pytest.mark.parametrize(
    "builder",
    [build_ability_check_resolved_v1, build_ability_check_resolved_v2],
)
def test_builders_reject_outcome_command_mismatch(
    event_outcome: AbilityCheckResult,
    message: str,
    builder: Callable[..., GameEvent],
) -> None:
    with pytest.raises(ValueError, match=message):
        builder(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
            command=command(),
            outcome=event_outcome,
        )
