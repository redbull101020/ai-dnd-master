from copy import deepcopy
from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.definitions.weapon import WeaponDefinition
from dnd_engine.domain.rules.attack import AttackResult
from dnd_engine.domain.rules.character_weapon_attack_damage import (
    CharacterWeaponAttackDamageResult,
    resolve_character_weapon_attack_damage,
)
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.d20 import D20Roll, RollMode
from dnd_engine.domain.value_objects.damage_type import DamageType
from dnd_engine.domain.value_objects.dice_roll import DiceRoll


class ScriptedDiceEngine:
    def __init__(self, *rolls: DiceRoll) -> None:
        self._rolls = iter(rolls)
        self.calls: list[str] = []

    def roll(self, expression: str) -> DiceRoll:
        self.calls.append(expression)
        return next(self._rolls)


def make_weapon(
    *,
    definition_id: str = "dagger",
    damage_dice: str = "1d4",
    damage_type: DamageType = DamageType.PIERCING,
) -> WeaponDefinition:
    return WeaponDefinition(
        id=definition_id,
        version=1,
        name="Dagger",
        damage_dice=damage_dice,
        damage_type=damage_type,
        properties=("finesse", "light", "thrown"),
    )


def make_attack_result(
    *,
    target_id: str = "creature_001",
    ability: Ability = Ability.STRENGTH,
    ability_modifier: int = 3,
    proficiency_bonus: int = 2,
    hit: bool = True,
    critical_hit: bool = False,
) -> AttackResult:
    selected = 20 if critical_hit else (15 if hit else 5)
    roll = D20Roll(mode=RollMode.NORMAL, rolls=(selected,), selected=selected)
    total = selected + ability_modifier + proficiency_bonus
    target_armor_class = total if hit else total + 1

    return AttackResult(
        target_id=target_id,
        roll=roll,
        ability=ability,
        ability_modifier=ability_modifier,
        proficiency_bonus=proficiency_bonus,
        total=total,
        target_armor_class=target_armor_class,
        hit=hit,
        critical_hit=critical_hit,
    )


def canonical_result(**overrides: object) -> CharacterWeaponAttackDamageResult:
    values: dict[str, object] = {
        "target_id": "creature_001",
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
    return CharacterWeaponAttackDamageResult(**values)  # type: ignore[arg-type]


def test_normal_hit_rolls_authoritative_expression_once_and_composes_result() -> None:
    dice = ScriptedDiceEngine(DiceRoll(expression="1d4", rolls=(3,), total=3))

    result = resolve_character_weapon_attack_damage(
        make_attack_result(),
        "item_001",
        make_weapon(),
        dice,
    )

    assert result == canonical_result()
    assert dice.calls == ["1d4"]


def test_explicit_strength_ability_and_modifier_propagate_unchanged() -> None:
    dice = ScriptedDiceEngine(DiceRoll(expression="1d4", rolls=(2,), total=2))

    result = resolve_character_weapon_attack_damage(
        make_attack_result(ability=Ability.STRENGTH, ability_modifier=4),
        "item_001",
        make_weapon(),
        dice,
    )

    assert result.ability is Ability.STRENGTH
    assert result.ability_modifier == 4
    assert result.amount == 6


def test_explicit_dexterity_finesse_ability_and_modifier_propagate_unchanged() -> None:
    dice = ScriptedDiceEngine(DiceRoll(expression="1d4", rolls=(2,), total=2))

    result = resolve_character_weapon_attack_damage(
        make_attack_result(ability=Ability.DEXTERITY, ability_modifier=1),
        "item_001",
        make_weapon(),
        dice,
    )

    assert result.ability is Ability.DEXTERITY
    assert result.ability_modifier == 1
    assert result.amount == 3


def test_weapon_definition_damage_dice_is_authoritative() -> None:
    dice = ScriptedDiceEngine(DiceRoll(expression="1d8", rolls=(5,), total=5))

    result = resolve_character_weapon_attack_damage(
        make_attack_result(),
        "item_001",
        make_weapon(damage_dice="1d8"),
        dice,
    )

    assert dice.calls == ["1d8"]
    assert result.roll.expression == "1d8"


def test_weapon_definition_damage_type_is_authoritative() -> None:
    dice = ScriptedDiceEngine(DiceRoll(expression="1d4", rolls=(3,), total=3))

    result = resolve_character_weapon_attack_damage(
        make_attack_result(),
        "item_001",
        make_weapon(damage_type=DamageType.SLASHING),
        dice,
    )

    assert result.damage_type is DamageType.SLASHING


def test_runtime_weapon_item_identity_propagates() -> None:
    dice = ScriptedDiceEngine(DiceRoll(expression="1d4", rolls=(3,), total=3))

    result = resolve_character_weapon_attack_damage(
        make_attack_result(),
        "item_009",
        make_weapon(),
        dice,
    )

    assert result.weapon_item_id == "item_009"


def test_weapon_definition_identity_propagates() -> None:
    dice = ScriptedDiceEngine(DiceRoll(expression="1d4", rolls=(3,), total=3))

    result = resolve_character_weapon_attack_damage(
        make_attack_result(),
        "item_001",
        make_weapon(definition_id="dagger"),
        dice,
    )

    assert result.weapon_definition_id == "dagger"


def test_critical_hit_doubles_only_dice_count_and_applies_modifier_once() -> None:
    dice = ScriptedDiceEngine(
        DiceRoll(expression="2d4", rolls=(2, 3), total=5)
    )

    result = resolve_character_weapon_attack_damage(
        make_attack_result(critical_hit=True, ability_modifier=3),
        "item_001",
        make_weapon(),
        dice,
    )

    assert dice.calls == ["2d4"]
    assert result.roll.total == 5
    assert result.ability_modifier == 3
    assert result.amount == 8
    assert result.critical_hit is True


def test_negative_ability_modifier_may_clamp_source_amount_to_zero() -> None:
    dice = ScriptedDiceEngine(DiceRoll(expression="1d4", rolls=(1,), total=1))

    result = resolve_character_weapon_attack_damage(
        make_attack_result(ability_modifier=-5),
        "item_001",
        make_weapon(),
        dice,
    )

    assert result.amount == 0


def test_resolver_rejects_miss_without_rolling_damage() -> None:
    dice = ScriptedDiceEngine(DiceRoll(expression="1d4", rolls=(3,), total=3))

    with pytest.raises(ValueError, match="hit"):
        resolve_character_weapon_attack_damage(
            make_attack_result(hit=False),
            "item_001",
            make_weapon(),
            dice,
        )

    assert dice.calls == []


def test_resolver_rejects_dice_engine_response_expression_mismatch() -> None:
    dice = ScriptedDiceEngine(DiceRoll(expression="1d6", rolls=(4,), total=4))

    with pytest.raises(ValueError, match="expression"):
        resolve_character_weapon_attack_damage(
            make_attack_result(),
            "item_001",
            make_weapon(),
            dice,
        )


def test_resolver_rejects_dice_engine_response_wrong_type() -> None:
    class BrokenDiceEngine:
        def roll(self, expression: str) -> object:
            return object()

    with pytest.raises(TypeError, match="DiceRoll"):
        resolve_character_weapon_attack_damage(
            make_attack_result(),
            "item_001",
            make_weapon(),
            BrokenDiceEngine(),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("attack_outcome", "weapon_item_id", "weapon", "match"),
    [
        (object(), "item_001", make_weapon(), "AttackResult"),
        (make_attack_result(), 1, make_weapon(), "weapon_item_id"),
        (make_attack_result(), "item_001", object(), "WeaponDefinition"),
    ],
)
def test_resolver_rejects_wrong_domain_input_types(
    attack_outcome: object,
    weapon_item_id: object,
    weapon: object,
    match: str,
) -> None:
    dice = ScriptedDiceEngine(DiceRoll(expression="1d4", rolls=(3,), total=3))

    with pytest.raises(TypeError, match=match):
        resolve_character_weapon_attack_damage(
            attack_outcome,  # type: ignore[arg-type]
            weapon_item_id,  # type: ignore[arg-type]
            weapon,  # type: ignore[arg-type]
            dice,
        )

    assert dice.calls == []


def test_resolver_does_not_mutate_attack_outcome_or_weapon_definition() -> None:
    attack_outcome = make_attack_result()
    weapon = make_weapon()
    attack_outcome_before = deepcopy(attack_outcome)
    weapon_before = deepcopy(weapon)

    resolve_character_weapon_attack_damage(
        attack_outcome,
        "item_001",
        weapon,
        ScriptedDiceEngine(DiceRoll(expression="1d4", rolls=(3,), total=3)),
    )

    assert attack_outcome == attack_outcome_before
    assert weapon == weapon_before


def test_result_has_exact_fields_and_is_immutable() -> None:
    result = canonical_result()

    assert tuple(field.name for field in fields(result)) == (
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
        result.amount = 7  # type: ignore[misc]


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
def test_result_rejects_wrong_runtime_types(
    field_name: str,
    invalid_value: object,
) -> None:
    with pytest.raises(TypeError):
        canonical_result(**{field_name: invalid_value})


def test_result_rejects_inconsistent_amount() -> None:
    with pytest.raises(ValueError, match="amount"):
        canonical_result(amount=5)
