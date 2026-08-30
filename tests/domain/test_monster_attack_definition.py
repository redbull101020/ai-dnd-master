from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.definitions.monster_attack import MonsterAttackDefinition
from dnd_engine.domain.value_objects.damage_type import DamageType


CANONICAL_FIELDS = (
    "action_id",
    "name",
    "attack_bonus",
    "damage_dice",
    "damage_modifier",
    "damage_type",
)


def scimitar() -> MonsterAttackDefinition:
    return MonsterAttackDefinition(
        action_id="scimitar",
        name="Scimitar",
        attack_bonus=4,
        damage_dice="1d6",
        damage_modifier=2,
        damage_type=DamageType.SLASHING,
    )


def test_monster_attack_definition_accepts_canonical_fields() -> None:
    attack = scimitar()

    assert attack.action_id == "scimitar"
    assert attack.name == "Scimitar"
    assert attack.attack_bonus == 4
    assert attack.damage_dice == "1d6"
    assert attack.damage_modifier == 2
    assert attack.damage_type is DamageType.SLASHING


def test_monster_attack_definition_is_immutable() -> None:
    attack = scimitar()

    with pytest.raises(FrozenInstanceError):
        attack.attack_bonus = 5  # type: ignore[misc]


def test_monster_attack_definition_has_only_canonical_fields() -> None:
    assert (
        tuple(field.name for field in fields(MonsterAttackDefinition))
        == CANONICAL_FIELDS
    )


def test_monster_attack_definition_does_not_accept_runtime_fields() -> None:
    with pytest.raises(TypeError):
        MonsterAttackDefinition(  # type: ignore[call-arg]
            action_id="scimitar",
            name="Scimitar",
            attack_bonus=4,
            damage_dice="1d6",
            damage_modifier=2,
            damage_type=DamageType.SLASHING,
            range=5,
        )


def replace(**overrides: object) -> MonsterAttackDefinition:
    values: dict[str, object] = {
        "action_id": "scimitar",
        "name": "Scimitar",
        "attack_bonus": 4,
        "damage_dice": "1d6",
        "damage_modifier": 2,
        "damage_type": DamageType.SLASHING,
    }
    values.update(overrides)
    return MonsterAttackDefinition(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("action_id", [1, None, True])
def test_rejects_non_str_action_id(action_id: object) -> None:
    with pytest.raises(TypeError, match="action_id"):
        replace(action_id=action_id)


def test_rejects_empty_action_id() -> None:
    with pytest.raises(ValueError, match="action_id"):
        replace(action_id="")


@pytest.mark.parametrize("action_id", ["scimitar", "shortbow", "claw_attack", "a1"])
def test_accepts_canonical_local_action_id(action_id: str) -> None:
    assert replace(action_id=action_id).action_id == action_id


@pytest.mark.parametrize(
    "action_id",
    [
        "Scimitar",
        "scimitar attack",
        " scimitar",
        "scimitar ",
        "scimitar/attack",
        "scimitar\\attack",
        "1scimitar",
        "_scimitar",
        "scimitar-attack",
        "scimitar.attack",
        "../scimitar",
    ],
)
def test_rejects_non_canonical_local_action_id(action_id: str) -> None:
    with pytest.raises(ValueError, match="action_id"):
        replace(action_id=action_id)


@pytest.mark.parametrize("name", [1, None, True])
def test_rejects_non_str_name(name: object) -> None:
    with pytest.raises(TypeError, match="name"):
        replace(name=name)


@pytest.mark.parametrize("attack_bonus", ["4", None, True, 4.0])
def test_rejects_non_int_attack_bonus(attack_bonus: object) -> None:
    with pytest.raises(TypeError, match="attack_bonus"):
        replace(attack_bonus=attack_bonus)


def test_accepts_negative_attack_bonus() -> None:
    assert replace(attack_bonus=-1).attack_bonus == -1


@pytest.mark.parametrize("damage_dice", [None, 6, True])
def test_rejects_non_str_damage_dice(damage_dice: object) -> None:
    with pytest.raises(TypeError):
        replace(damage_dice=damage_dice)


@pytest.mark.parametrize(
    "damage_dice",
    ["", "foo", "d6", "1d", "1D6", " 1d6", "1d6 ", "1d6+2", "2d6kh1"],
)
def test_rejects_malformed_damage_dice(damage_dice: str) -> None:
    with pytest.raises(ValueError):
        replace(damage_dice=damage_dice)


@pytest.mark.parametrize("damage_modifier", ["2", None, True, 2.0])
def test_rejects_non_int_damage_modifier(damage_modifier: object) -> None:
    with pytest.raises(TypeError, match="damage_modifier"):
        replace(damage_modifier=damage_modifier)


def test_accepts_zero_and_negative_damage_modifier() -> None:
    assert replace(damage_modifier=0).damage_modifier == 0
    assert replace(damage_modifier=-1).damage_modifier == -1


@pytest.mark.parametrize("damage_type", ["slashing", None, 1])
def test_rejects_non_damage_type_damage_type(damage_type: object) -> None:
    with pytest.raises(TypeError, match="damage_type"):
        replace(damage_type=damage_type)
