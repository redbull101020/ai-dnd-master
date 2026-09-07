from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timezone

import pytest

from dnd_engine.domain.commands.attack import AttackCommand, AttackPayload
from dnd_engine.domain.events.character_weapon_attack_damage import (
    CharacterWeaponAttackDamageResolvedPayloadV1,
    build_character_weapon_attack_damage_resolved_v1,
)
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.rules.character_weapon_attack_damage import (
    CharacterWeaponAttackDamageResult,
)
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.damage_type import DamageType
from dnd_engine.domain.value_objects.dice_roll import DiceRoll
from dnd_engine.infrastructure.persistence.json.event_serializer import EventSerializer


FIXED_TIMESTAMP = datetime(2026, 9, 7, 12, 45, tzinfo=timezone.utc)
PAYLOAD_KEYS = {
    "targetId",
    "weaponItemId",
    "weaponDefinitionId",
    "roll",
    "ability",
    "abilityModifier",
    "damageType",
    "criticalHit",
    "amount",
}


def make_command(
    *,
    target_id: str = "monster_001",
    weapon_item_id: str | None = "item_001",
) -> AttackCommand:
    return AttackCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=AttackPayload(
            target_id=target_id,
            weapon_item_id=weapon_item_id,
        ),
    )


def make_outcome(
    *,
    target_id: str = "monster_001",
    weapon_item_id: str = "item_001",
    weapon_definition_id: str = "dagger",
    roll: DiceRoll | None = None,
    ability: Ability = Ability.STRENGTH,
    ability_modifier: int = 3,
    damage_type: DamageType = DamageType.PIERCING,
    critical_hit: bool = False,
    amount: int | None = None,
) -> CharacterWeaponAttackDamageResult:
    effective_roll = roll or DiceRoll(expression="1d4", rolls=(3,), total=3)
    effective_amount = (
        amount
        if amount is not None
        else max(0, effective_roll.total + ability_modifier)
    )
    return CharacterWeaponAttackDamageResult(
        target_id=target_id,
        weapon_item_id=weapon_item_id,
        weapon_definition_id=weapon_definition_id,
        roll=effective_roll,
        ability=ability,
        ability_modifier=ability_modifier,
        damage_type=damage_type,
        critical_hit=critical_hit,
        amount=effective_amount,
    )


def make_payload(
    **overrides: object,
) -> CharacterWeaponAttackDamageResolvedPayloadV1:
    values: dict[str, object] = {
        "target_id": "monster_001",
        "weapon_item_id": "item_001",
        "weapon_definition_id": "dagger",
        "roll": DiceRoll(expression="1d4", rolls=(3,), total=3),
        "ability": Ability.STRENGTH,
        "ability_modifier": 3,
        "damage_type": DamageType.PIERCING,
        "critical_hit": False,
        "amount": 6,
    }
    values.update(overrides)
    return CharacterWeaponAttackDamageResolvedPayloadV1(**values)  # type: ignore[arg-type]


def build_event(
    outcome: CharacterWeaponAttackDamageResult | None = None,
    *,
    command: AttackCommand | None = None,
    caused_by: str = "event_000123",
) -> GameEvent:
    return build_character_weapon_attack_damage_resolved_v1(
        event_id="event_000124",
        timestamp=FIXED_TIMESTAMP,
        command=command or make_command(),
        outcome=outcome or make_outcome(),
        caused_by=caused_by,
    )


def test_builder_creates_exact_canonical_event_and_causation() -> None:
    event = build_event()

    assert event.event_id == "event_000124"
    assert event.type == "CharacterWeaponAttackDamageResolved"
    assert event.version == 1
    assert event.command_id == "command_000001"
    assert event.campaign_id == "campaign_001"
    assert event.timestamp is FIXED_TIMESTAMP
    assert event.actor_id == "character_001"
    assert event.caused_by == "event_000123"
    assert set(event.payload) == PAYLOAD_KEYS
    assert set(event.payload["roll"]) == {"expression", "rolls", "total"}
    assert event.payload == {
        "targetId": "monster_001",
        "weaponItemId": "item_001",
        "weaponDefinitionId": "dagger",
        "roll": {"expression": "1d4", "rolls": (3,), "total": 3},
        "ability": "strength",
        "abilityModifier": 3,
        "damageType": "piercing",
        "criticalHit": False,
        "amount": 6,
    }
    assert not {"previousHp", "newHp", "proficiencyBonus"} & set(event.payload)


def test_event_is_json_serializable_with_exact_payload() -> None:
    serialized = EventSerializer.serialize(build_event())

    assert serialized["payload"] == {
        "targetId": "monster_001",
        "weaponItemId": "item_001",
        "weaponDefinitionId": "dagger",
        "roll": {"expression": "1d4", "rolls": [3], "total": 3},
        "ability": "strength",
        "abilityModifier": 3,
        "damageType": "piercing",
        "criticalHit": False,
        "amount": 6,
    }


def test_builder_records_runtime_weapon_item_and_definition_identity() -> None:
    event = build_event(
        make_outcome(weapon_item_id="item_042", weapon_definition_id="dagger"),
        command=make_command(weapon_item_id="item_042"),
    )

    assert event.payload["weaponItemId"] == "item_042"
    assert event.payload["weaponDefinitionId"] == "dagger"


def test_builder_serializes_dexterity_finesse_ability_by_value() -> None:
    event = build_event(
        make_outcome(ability=Ability.DEXTERITY, ability_modifier=1)
    )

    assert event.payload["ability"] == "dexterity"
    assert event.payload["abilityModifier"] == 1


def test_builder_serializes_damage_type_by_value() -> None:
    event = build_event(make_outcome(damage_type=DamageType.SLASHING))

    assert event.payload["damageType"] == "slashing"


def test_builder_preserves_critical_hit_and_doubled_roll_amount() -> None:
    event = build_event(
        make_outcome(
            roll=DiceRoll(expression="2d4", rolls=(2, 3), total=5),
            ability_modifier=3,
            critical_hit=True,
        )
    )

    assert event.payload["roll"] == {"expression": "2d4", "rolls": (2, 3), "total": 5}
    assert event.payload["criticalHit"] is True
    assert event.payload["amount"] == 8


def test_builder_records_zero_source_amount_as_a_valid_event() -> None:
    event = build_event(
        make_outcome(
            roll=DiceRoll(expression="1d4", rolls=(1,), total=1),
            ability_modifier=-5,
        )
    )

    assert event.payload["amount"] == 0


def test_builder_rejects_target_mismatch() -> None:
    with pytest.raises(ValueError, match="target_id"):
        build_event(
            make_outcome(target_id="monster_002"),
            command=make_command(target_id="monster_001"),
        )


def test_builder_rejects_weapon_item_mismatch() -> None:
    with pytest.raises(ValueError, match="weapon_item_id"):
        build_event(
            make_outcome(weapon_item_id="item_002"),
            command=make_command(weapon_item_id="item_001"),
        )


def test_builder_rejects_command_without_weapon_selection() -> None:
    with pytest.raises(ValueError, match="weapon_item_id"):
        build_event(command=make_command(weapon_item_id=None))


@pytest.mark.parametrize(
    ("command", "outcome", "caused_by", "error", "match"),
    [
        (object(), make_outcome(), "event_000123", TypeError, "AttackCommand"),
        (
            make_command(),
            object(),
            "event_000123",
            TypeError,
            "CharacterWeaponAttackDamageResult",
        ),
        (make_command(), make_outcome(), None, TypeError, "caused_by"),
        (make_command(), make_outcome(), 1, TypeError, "caused_by"),
    ],
)
def test_builder_rejects_wrong_domain_input_types(
    command: object,
    outcome: object,
    caused_by: object,
    error: type[Exception],
    match: str,
) -> None:
    with pytest.raises(error, match=match):
        build_character_weapon_attack_damage_resolved_v1(
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
        "weapon_item_id",
        "weapon_definition_id",
        "roll",
        "ability",
        "ability_modifier",
        "damage_type",
        "critical_hit",
        "amount",
    )
    with pytest.raises(FrozenInstanceError):
        payload.amount = 7  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("target_id", 1),
        ("weapon_item_id", 1),
        ("weapon_definition_id", 1),
        ("roll", object()),
        ("ability", "strength"),
        ("ability_modifier", True),
        ("damage_type", "piercing"),
        ("critical_hit", 1),
        ("amount", True),
    ],
)
def test_payload_rejects_wrong_runtime_types(
    field_name: str,
    invalid_value: object,
) -> None:
    with pytest.raises(TypeError):
        make_payload(**{field_name: invalid_value})


def test_payload_rejects_inconsistent_amount() -> None:
    with pytest.raises(ValueError, match="amount"):
        make_payload(amount=5)


def test_built_event_preserves_generic_immutability() -> None:
    event = build_event()

    with pytest.raises(FrozenInstanceError):
        event.type = "AttackHit"  # type: ignore[misc]
    with pytest.raises(TypeError):
        event.payload["amount"] = 0  # type: ignore[index]
