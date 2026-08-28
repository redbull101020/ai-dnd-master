from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timezone

import pytest

from dnd_engine.domain.commands.attack import AttackCommand, AttackPayload
from dnd_engine.domain.events.attack import (
    AttackResolvedPayloadV1,
    build_attack_resolved_v1,
)
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.rules.attack import AttackResult
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.d20 import D20Roll, RollMode
from dnd_engine.infrastructure.persistence.json.event_serializer import EventSerializer


FIXED_TIMESTAMP = datetime(2026, 8, 28, 12, 30, tzinfo=timezone.utc)
PAYLOAD_KEYS = {
    "targetId",
    "roll",
    "ability",
    "abilityModifier",
    "proficiencyBonus",
    "total",
    "targetArmorClass",
    "hit",
    "criticalHit",
}


def make_command(*, target_id: str = "monster_001") -> AttackCommand:
    return AttackCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=AttackPayload(target_id=target_id),
    )


def make_outcome(
    *,
    target_id: str = "monster_001",
    roll: D20Roll | None = None,
    ability_modifier: int = 3,
    proficiency_bonus: int = 3,
    target_armor_class: int = 15,
    hit: bool = True,
    critical_hit: bool = False,
) -> AttackResult:
    effective_roll = roll or D20Roll(
        mode=RollMode.NORMAL,
        rolls=(9,),
        selected=9,
    )
    return AttackResult(
        target_id=target_id,
        roll=effective_roll,
        ability=Ability.STRENGTH,
        ability_modifier=ability_modifier,
        proficiency_bonus=proficiency_bonus,
        total=effective_roll.selected + ability_modifier + proficiency_bonus,
        target_armor_class=target_armor_class,
        hit=hit,
        critical_hit=critical_hit,
    )


def make_payload(**overrides: object) -> AttackResolvedPayloadV1:
    values: dict[str, object] = {
        "target_id": "monster_001",
        "roll": D20Roll(mode=RollMode.NORMAL, rolls=(9,), selected=9),
        "ability": Ability.STRENGTH,
        "ability_modifier": 3,
        "proficiency_bonus": 3,
        "total": 15,
        "target_armor_class": 15,
        "hit": True,
        "critical_hit": False,
    }
    values.update(overrides)
    return AttackResolvedPayloadV1(**values)  # type: ignore[arg-type]


def build_event(outcome: AttackResult | None = None) -> GameEvent:
    return build_attack_resolved_v1(
        event_id="event_000123",
        timestamp=FIXED_TIMESTAMP,
        command=make_command(),
        outcome=outcome or make_outcome(),
    )


def test_builder_creates_exact_canonical_hit_event() -> None:
    event = build_event()

    assert event.event_id == "event_000123"
    assert event.type == "AttackResolved"
    assert event.version == 1
    assert event.command_id == "command_000001"
    assert event.campaign_id == "campaign_001"
    assert event.timestamp is FIXED_TIMESTAMP
    assert event.actor_id == "character_001"
    assert event.caused_by is None
    assert set(event.payload) == PAYLOAD_KEYS
    assert set(event.payload["roll"]) == {"mode", "rolls", "selected"}
    assert event.payload == {
        "targetId": "monster_001",
        "roll": {"mode": "normal", "rolls": (9,), "selected": 9},
        "ability": "strength",
        "abilityModifier": 3,
        "proficiencyBonus": 3,
        "total": 15,
        "targetArmorClass": 15,
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
        "damageRoll",
        "weaponId",
        "attackBonus",
        "proficient",
    } & set(event.payload)


def test_canonical_event_is_json_serializable() -> None:
    event = build_event()

    serialized = EventSerializer.serialize(event)

    assert serialized["payload"] == {
        "targetId": "monster_001",
        "roll": {"mode": "normal", "rolls": [9], "selected": 9},
        "ability": "strength",
        "abilityModifier": 3,
        "proficiencyBonus": 3,
        "total": 15,
        "targetArmorClass": 15,
        "hit": True,
        "criticalHit": False,
    }


def test_builder_records_canonical_miss() -> None:
    outcome = make_outcome(
        roll=D20Roll(mode=RollMode.NORMAL, rolls=(8,), selected=8),
        hit=False,
    )

    event = build_event(outcome)

    assert event.payload["total"] == 14
    assert event.payload["targetArmorClass"] == 15
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

    assert event.type == "AttackResolved"
    assert event.payload["total"] == 26
    assert event.payload["targetArmorClass"] == 100
    assert event.payload["hit"] is True
    assert event.payload["criticalHit"] is True


@pytest.mark.parametrize(
    ("mode", "rolls", "selected", "target_ac", "hit"),
    [
        (RollMode.NORMAL, (12,), 12, 18, True),
        (RollMode.ADVANTAGE, (4, 15), 15, 21, True),
        (RollMode.DISADVANTAGE, (12, 5), 5, 12, False),
    ],
)
def test_builder_preserves_exact_d20_mode_and_audit_values(
    mode: RollMode,
    rolls: tuple[int, ...],
    selected: int,
    target_ac: int,
    hit: bool,
) -> None:
    event = build_event(
        make_outcome(
            roll=D20Roll(mode=mode, rolls=rolls, selected=selected),
            target_armor_class=target_ac,
            hit=hit,
        )
    )

    assert event.payload["roll"] == {
        "mode": mode.value,
        "rolls": rolls,
        "selected": selected,
    }
    assert event.payload["ability"] == "strength"
    assert event.payload["abilityModifier"] == 3
    assert event.payload["proficiencyBonus"] == 3
    assert event.payload["total"] == selected + 3 + 3
    assert event.payload["targetArmorClass"] == target_ac
    assert event.payload["hit"] is hit
    assert event.payload["criticalHit"] is False


def test_payload_has_exact_fields_and_is_immutable() -> None:
    payload = make_payload()

    assert tuple(field.name for field in fields(payload)) == (
        "target_id",
        "roll",
        "ability",
        "ability_modifier",
        "proficiency_bonus",
        "total",
        "target_armor_class",
        "hit",
        "critical_hit",
    )
    with pytest.raises(FrozenInstanceError):
        payload.total = 14  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("target_id", 1),
        ("roll", object()),
        ("ability", "strength"),
        ("ability_modifier", True),
        ("proficiency_bonus", True),
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


def test_payload_accepts_authoritative_armor_class_without_arbitrary_range() -> None:
    low_ac = make_payload(target_armor_class=-100)
    high_ac = make_payload(target_armor_class=1000, hit=False)

    assert low_ac.target_armor_class == -100
    assert high_ac.target_armor_class == 1000


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"proficiency_bonus": -1, "total": 11, "hit": False}, "negative"),
        ({"total": 14}, "total"),
        (
            {
                "roll": D20Roll(mode=RollMode.NORMAL, rolls=(1,), selected=1),
                "total": 7,
                "target_armor_class": 5,
                "hit": True,
            },
            "natural 1",
        ),
        (
            {
                "roll": D20Roll(mode=RollMode.NORMAL, rolls=(1,), selected=1),
                "total": 7,
                "target_armor_class": 5,
                "hit": False,
                "critical_hit": True,
            },
            "natural 1",
        ),
        (
            {
                "roll": D20Roll(mode=RollMode.NORMAL, rolls=(20,), selected=20),
                "total": 26,
                "target_armor_class": 100,
                "hit": False,
                "critical_hit": True,
            },
            "natural 20",
        ),
        (
            {
                "roll": D20Roll(mode=RollMode.NORMAL, rolls=(20,), selected=20),
                "total": 26,
                "target_armor_class": 100,
                "hit": True,
                "critical_hit": False,
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
        (make_command(), object(), TypeError, "AttackResult"),
        (
            make_command(),
            make_outcome(target_id="monster_002"),
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
        build_attack_resolved_v1(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
            command=command,  # type: ignore[arg-type]
            outcome=outcome,  # type: ignore[arg-type]
        )


def test_built_event_preserves_generic_immutability() -> None:
    event = build_event()

    with pytest.raises(FrozenInstanceError):
        event.type = "AttackHit"  # type: ignore[misc]
    with pytest.raises(TypeError):
        event.payload["hit"] = False  # type: ignore[index]
