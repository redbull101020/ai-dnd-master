from copy import deepcopy
from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.definitions.monster_attack import MonsterAttackDefinition
from dnd_engine.domain.rules.monster_attack import MonsterAttackResult
from dnd_engine.domain.rules.monster_attack_damage import (
    MonsterAttackDamageResult,
    resolve_monster_attack_damage,
)
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


def make_attack(
    *,
    action_id: str = "scimitar",
    damage_dice: str = "1d6",
    damage_modifier: int = 2,
    damage_type: DamageType = DamageType.SLASHING,
) -> MonsterAttackDefinition:
    return MonsterAttackDefinition(
        action_id=action_id,
        name="Scimitar",
        attack_bonus=4,
        damage_dice=damage_dice,
        damage_modifier=damage_modifier,
        damage_type=damage_type,
    )


def make_attack_outcome(
    *,
    target_id: str = "character_001",
    action_id: str = "scimitar",
    hit: bool = True,
    critical_hit: bool = False,
) -> MonsterAttackResult:
    if critical_hit:
        roll = D20Roll(mode=RollMode.NORMAL, rolls=(20,), selected=20)
        target_armor_class = 100
    elif hit:
        roll = D20Roll(mode=RollMode.NORMAL, rolls=(10,), selected=10)
        target_armor_class = 12
    else:
        roll = D20Roll(mode=RollMode.NORMAL, rolls=(5,), selected=5)
        target_armor_class = 12

    return MonsterAttackResult(
        target_id=target_id,
        action_id=action_id,
        roll=roll,
        attack_bonus=4,
        total=roll.selected + 4,
        target_armor_class=target_armor_class,
        hit=hit,
        critical_hit=critical_hit,
    )


def canonical_result(**overrides: object) -> MonsterAttackDamageResult:
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
    return MonsterAttackDamageResult(**values)  # type: ignore[arg-type]


def test_normal_hit_rolls_original_expression_once_and_composes_result() -> None:
    dice = ScriptedDiceEngine(DiceRoll(expression="1d6", rolls=(4,), total=4))

    result = resolve_monster_attack_damage(
        make_attack_outcome(),
        make_attack(),
        dice,
    )

    assert result == canonical_result()
    assert dice.calls == ["1d6"]


def test_critical_hit_doubles_only_dice_count_and_applies_modifier_once() -> None:
    dice = ScriptedDiceEngine(
        DiceRoll(expression="4d8", rolls=(4, 5, 6, 7), total=22)
    )

    result = resolve_monster_attack_damage(
        make_attack_outcome(critical_hit=True),
        make_attack(damage_dice="2d8", damage_modifier=3),
        dice,
    )

    assert dice.calls == ["4d8"]
    assert result.roll.total == 22
    assert result.damage_modifier == 3
    assert result.amount == 25
    assert result.critical_hit is True


def test_damage_type_target_and_action_propagate() -> None:
    dice = ScriptedDiceEngine(DiceRoll(expression="1d4", rolls=(3,), total=3))

    result = resolve_monster_attack_damage(
        make_attack_outcome(target_id="character_009", action_id="acid_claw"),
        make_attack(
            action_id="acid_claw",
            damage_dice="1d4",
            damage_type=DamageType.ACID,
        ),
        dice,
    )

    assert result.target_id == "character_009"
    assert result.action_id == "acid_claw"
    assert result.damage_type is DamageType.ACID


def test_negative_modifier_may_produce_zero_source_damage() -> None:
    dice = ScriptedDiceEngine(DiceRoll(expression="1d4", rolls=(1,), total=1))

    result = resolve_monster_attack_damage(
        make_attack_outcome(action_id="weak_strike"),
        make_attack(
            action_id="weak_strike",
            damage_dice="1d4",
            damage_modifier=-5,
        ),
        dice,
    )

    assert result.amount == 0


def test_resolver_rejects_miss_without_rolling_damage() -> None:
    dice = ScriptedDiceEngine(DiceRoll(expression="1d6", rolls=(4,), total=4))

    with pytest.raises(ValueError, match="hit"):
        resolve_monster_attack_damage(
            make_attack_outcome(hit=False),
            make_attack(),
            dice,
        )

    assert dice.calls == []


def test_resolver_rejects_action_mismatch_without_rolling_damage() -> None:
    dice = ScriptedDiceEngine(DiceRoll(expression="1d6", rolls=(4,), total=4))

    with pytest.raises(ValueError, match="action_id"):
        resolve_monster_attack_damage(
            make_attack_outcome(action_id="scimitar"),
            make_attack(action_id="claw"),
            dice,
        )

    assert dice.calls == []


@pytest.mark.parametrize(
    ("attack_outcome", "attack", "match"),
    [
        (object(), make_attack(), "MonsterAttackResult"),
        (make_attack_outcome(), object(), "MonsterAttackDefinition"),
    ],
)
def test_resolver_rejects_wrong_domain_input_types(
    attack_outcome: object,
    attack: object,
    match: str,
) -> None:
    dice = ScriptedDiceEngine(DiceRoll(expression="1d6", rolls=(4,), total=4))

    with pytest.raises(TypeError, match=match):
        resolve_monster_attack_damage(
            attack_outcome,  # type: ignore[arg-type]
            attack,  # type: ignore[arg-type]
            dice,
        )

    assert dice.calls == []


def test_resolver_does_not_mutate_attack_outcome_or_definition() -> None:
    attack_outcome = make_attack_outcome()
    attack = make_attack()
    attack_outcome_before = deepcopy(attack_outcome)
    attack_before = deepcopy(attack)

    resolve_monster_attack_damage(
        attack_outcome,
        attack,
        ScriptedDiceEngine(DiceRoll(expression="1d6", rolls=(4,), total=4)),
    )

    assert attack_outcome == attack_outcome_before
    assert attack == attack_before


def test_result_has_exact_fields_and_is_immutable() -> None:
    result = canonical_result()

    assert tuple(field.name for field in fields(result)) == (
        "target_id",
        "action_id",
        "roll",
        "damage_modifier",
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
        ("action_id", 1),
        ("roll", object()),
        ("damage_modifier", True),
        ("damage_type", "slashing"),
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
