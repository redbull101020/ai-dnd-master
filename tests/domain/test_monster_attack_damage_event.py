from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timezone

import pytest

from dnd_engine.domain.commands.attack import AttackCommand, AttackPayload
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.events.monster_attack_damage import (
    MonsterAttackDamageResolvedPayloadV1,
    build_monster_attack_damage_resolved_v1,
)
from dnd_engine.domain.rules.monster_attack_damage import MonsterAttackDamageResult
from dnd_engine.domain.value_objects.damage_type import DamageType
from dnd_engine.domain.value_objects.dice_roll import DiceRoll
from dnd_engine.infrastructure.persistence.json.event_serializer import EventSerializer


FIXED_TIMESTAMP = datetime(2026, 8, 30, 14, 0, tzinfo=timezone.utc)


def make_command(*, target_id: str = "character_001") -> AttackCommand:
    return AttackCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="monster_001",
        payload=AttackPayload(target_id=target_id),
    )


def make_outcome(
    *,
    target_id: str = "character_001",
    action_id: str = "scimitar",
) -> MonsterAttackDamageResult:
    return MonsterAttackDamageResult(
        target_id=target_id,
        action_id=action_id,
        roll=DiceRoll(expression="1d6", rolls=(4,), total=4),
        damage_modifier=2,
        damage_type=DamageType.SLASHING,
        critical_hit=False,
        amount=6,
    )


def make_payload(
    **overrides: object,
) -> MonsterAttackDamageResolvedPayloadV1:
    values: dict[str, object] = {
        "target_id": "character_001",
        "action_id": "scimitar",
        "roll": DiceRoll(expression="1d6", rolls=(4,), total=4),
        "damage_modifier": 2,
        "damage_type": DamageType.SLASHING,
        "critical_hit": False,
        "amount": 6,
    }
    values.update(overrides)
    return MonsterAttackDamageResolvedPayloadV1(**values)  # type: ignore[arg-type]


def build_event(
    *,
    command: AttackCommand | None = None,
    outcome: MonsterAttackDamageResult | None = None,
) -> GameEvent:
    return build_monster_attack_damage_resolved_v1(
        event_id="event_000124",
        timestamp=FIXED_TIMESTAMP,
        command=command or make_command(),
        outcome=outcome or make_outcome(),
        caused_by="event_000123",
    )


def test_builder_creates_exact_canonical_event_and_causation() -> None:
    event = build_event()

    assert event.event_id == "event_000124"
    assert event.type == "MonsterAttackDamageResolved"
    assert event.version == 1
    assert event.command_id == "command_000001"
    assert event.campaign_id == "campaign_001"
    assert event.timestamp is FIXED_TIMESTAMP
    assert event.actor_id == "monster_001"
    assert event.caused_by == "event_000123"
    assert event.payload == {
        "targetId": "character_001",
        "actionId": "scimitar",
        "roll": {
            "expression": "1d6",
            "rolls": (4,),
            "total": 4,
        },
        "damageModifier": 2,
        "damageType": "slashing",
        "criticalHit": False,
        "amount": 6,
    }
    assert not {"previousHp", "newHp"} & set(event.payload)


def test_event_is_json_serializable_with_exact_payload() -> None:
    serialized = EventSerializer.serialize(build_event())

    assert serialized["payload"] == {
        "targetId": "character_001",
        "actionId": "scimitar",
        "roll": {"expression": "1d6", "rolls": [4], "total": 4},
        "damageModifier": 2,
        "damageType": "slashing",
        "criticalHit": False,
        "amount": 6,
    }


@pytest.mark.parametrize(
    ("command", "outcome", "caused_by", "error", "match"),
    [
        (object(), make_outcome(), "event_1", TypeError, "AttackCommand"),
        (make_command(), object(), "event_1", TypeError, "MonsterAttackDamageResult"),
        (make_command(), make_outcome(), None, TypeError, "caused_by"),
        (
            make_command(target_id="character_001"),
            make_outcome(target_id="character_002"),
            "event_1",
            ValueError,
            "target_id",
        ),
    ],
)
def test_builder_rejects_wrong_types_and_target_mismatch(
    command: object,
    outcome: object,
    caused_by: object,
    error: type[Exception],
    match: str,
) -> None:
    with pytest.raises(error, match=match):
        build_monster_attack_damage_resolved_v1(
            event_id="event_000124",
            timestamp=FIXED_TIMESTAMP,
            command=command,  # type: ignore[arg-type]
            outcome=outcome,  # type: ignore[arg-type]
            caused_by=caused_by,  # type: ignore[arg-type]
        )


def test_payload_has_exact_fields_and_is_immutable() -> None:
    payload = make_payload()

    assert tuple(field.name for field in fields(payload)) == (
        "target_id",
        "action_id",
        "roll",
        "damage_modifier",
        "damage_type",
        "critical_hit",
        "amount",
    )
    with pytest.raises(FrozenInstanceError):
        payload.amount = 7  # type: ignore[misc]


def test_payload_rejects_inconsistent_amount() -> None:
    with pytest.raises(ValueError, match="amount"):
        make_payload(amount=5)
