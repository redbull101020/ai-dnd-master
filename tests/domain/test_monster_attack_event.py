from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timezone

import pytest

from dnd_engine.domain.commands.attack import AttackCommand, AttackPayload
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.events.monster_attack import (
    MonsterAttackResolvedPayloadV1,
    build_monster_attack_resolved_v1,
)
from dnd_engine.domain.rules.monster_attack import MonsterAttackResult
from dnd_engine.domain.value_objects.d20 import D20Roll, RollMode
from dnd_engine.infrastructure.persistence.json.event_serializer import EventSerializer


FIXED_TIMESTAMP = datetime(2026, 8, 30, 12, 30, tzinfo=timezone.utc)
PAYLOAD_KEYS = {
    "targetId",
    "actionId",
    "roll",
    "attackBonus",
    "total",
    "targetArmorClass",
    "hit",
    "criticalHit",
}


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
    roll: D20Roll | None = None,
    attack_bonus: int = 4,
    target_armor_class: int = 12,
    hit: bool = True,
    critical_hit: bool = False,
) -> MonsterAttackResult:
    effective_roll = roll or D20Roll(mode=RollMode.NORMAL, rolls=(10,), selected=10)
    return MonsterAttackResult(
        target_id=target_id,
        action_id=action_id,
        roll=effective_roll,
        attack_bonus=attack_bonus,
        total=effective_roll.selected + attack_bonus,
        target_armor_class=target_armor_class,
        hit=hit,
        critical_hit=critical_hit,
    )


def make_payload(**overrides: object) -> MonsterAttackResolvedPayloadV1:
    values: dict[str, object] = {
        "target_id": "character_001",
        "action_id": "scimitar",
        "roll": D20Roll(mode=RollMode.NORMAL, rolls=(10,), selected=10),
        "attack_bonus": 4,
        "total": 14,
        "target_armor_class": 12,
        "hit": True,
        "critical_hit": False,
    }
    values.update(overrides)
    return MonsterAttackResolvedPayloadV1(**values)  # type: ignore[arg-type]


def build_event(outcome: MonsterAttackResult | None = None) -> GameEvent:
    return build_monster_attack_resolved_v1(
        event_id="event_000123",
        timestamp=FIXED_TIMESTAMP,
        command=make_command(),
        outcome=outcome or make_outcome(),
    )


def test_builder_creates_exact_canonical_hit_event() -> None:
    event = build_event()

    assert event.event_id == "event_000123"
    assert event.type == "MonsterAttackResolved"
    assert event.version == 1
    assert event.command_id == "command_000001"
    assert event.campaign_id == "campaign_001"
    assert event.timestamp is FIXED_TIMESTAMP
    assert event.actor_id == "monster_001"
    assert event.caused_by is None
    assert set(event.payload) == PAYLOAD_KEYS
    assert set(event.payload["roll"]) == {"mode", "rolls", "selected"}
    assert event.payload == {
        "targetId": "character_001",
        "actionId": "scimitar",
        "roll": {"mode": "normal", "rolls": (10,), "selected": 10},
        "attackBonus": 4,
        "total": 14,
        "targetArmorClass": 12,
        "hit": True,
        "criticalHit": False,
    }
    assert not {
        "eventId",
        "commandId",
        "campaignId",
        "timestamp",
        "actorId",
        "damage",
        "damageDice",
        "damageModifier",
        "damageType",
        "previousHp",
        "newHp",
        "ability",
        "abilityModifier",
        "proficiencyBonus",
    } & set(event.payload)


def test_canonical_event_is_json_serializable() -> None:
    event = build_event()

    serialized = EventSerializer.serialize(event)

    assert serialized["payload"] == {
        "targetId": "character_001",
        "actionId": "scimitar",
        "roll": {"mode": "normal", "rolls": [10], "selected": 10},
        "attackBonus": 4,
        "total": 14,
        "targetArmorClass": 12,
        "hit": True,
        "criticalHit": False,
    }


def test_builder_records_canonical_miss() -> None:
    outcome = make_outcome(
        roll=D20Roll(mode=RollMode.NORMAL, rolls=(6,), selected=6),
        hit=False,
    )

    event = build_event(outcome)

    assert event.payload["total"] == 10
    assert event.payload["hit"] is False
    assert event.payload["criticalHit"] is False


def test_builder_records_natural_twenty_as_one_critical_outcome() -> None:
    outcome = make_outcome(
        roll=D20Roll(mode=RollMode.NORMAL, rolls=(20,), selected=20),
        target_armor_class=100,
        hit=True,
        critical_hit=True,
    )

    event = build_event(outcome)

    assert event.payload["total"] == 24
    assert event.payload["hit"] is True
    assert event.payload["criticalHit"] is True


def test_payload_has_exact_fields_and_is_immutable() -> None:
    payload = make_payload()

    assert tuple(field.name for field in fields(payload)) == (
        "target_id",
        "action_id",
        "roll",
        "attack_bonus",
        "total",
        "target_armor_class",
        "hit",
        "critical_hit",
    )
    with pytest.raises(FrozenInstanceError):
        payload.total = 15  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("target_id", 1),
        ("action_id", 1),
        ("roll", object()),
        ("attack_bonus", True),
        ("total", True),
        ("target_armor_class", True),
        ("hit", 1),
        ("critical_hit", 0),
    ],
)
def test_payload_rejects_wrong_runtime_types(
    field_name: str,
    invalid_value: object,
) -> None:
    with pytest.raises(TypeError):
        make_payload(**{field_name: invalid_value})


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"total": 15}, "total"),
        (
            {
                "roll": D20Roll(mode=RollMode.NORMAL, rolls=(1,), selected=1),
                "total": 5,
                "target_armor_class": 5,
                "hit": True,
            },
            "natural 1",
        ),
        (
            {
                "roll": D20Roll(mode=RollMode.NORMAL, rolls=(20,), selected=20),
                "total": 24,
                "target_armor_class": 100,
                "hit": False,
                "critical_hit": True,
            },
            "natural 20",
        ),
        ({"hit": False}, "hit"),
        ({"critical_hit": True}, "natural 20"),
    ],
)
def test_payload_enforces_attack_outcome_invariants(
    overrides: dict[str, object],
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        make_payload(**overrides)


@pytest.mark.parametrize(
    ("command", "outcome", "error", "match"),
    [
        (object(), make_outcome(), TypeError, "AttackCommand"),
        (make_command(), object(), TypeError, "MonsterAttackResult"),
        (
            make_command(),
            make_outcome(target_id="character_002"),
            ValueError,
            "target_id",
        ),
    ],
)
def test_builder_rejects_wrong_types_and_target_mismatch(
    command: object,
    outcome: object,
    error: type[Exception],
    match: str,
) -> None:
    with pytest.raises(error, match=match):
        build_monster_attack_resolved_v1(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
            command=command,  # type: ignore[arg-type]
            outcome=outcome,  # type: ignore[arg-type]
        )


def test_built_event_preserves_generic_immutability() -> None:
    event = build_event()

    with pytest.raises(FrozenInstanceError):
        event.type = "MonsterAttackHit"  # type: ignore[misc]
    with pytest.raises(TypeError):
        event.payload["hit"] = False  # type: ignore[index]
