from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.value_objects.dice_roll import DiceRoll


CANONICAL_FIELDS = ("expression", "rolls", "total")


def test_dice_roll_accepts_valid_values() -> None:
    result = DiceRoll(expression="2d6", rolls=(3, 5), total=8)

    assert result.expression == "2d6"
    assert result.rolls == (3, 5)
    assert result.total == 8


def test_dice_roll_has_only_canonical_fields() -> None:
    assert tuple(field.name for field in fields(DiceRoll)) == CANONICAL_FIELDS


def test_dice_roll_is_immutable() -> None:
    result = DiceRoll(expression="1d20", rolls=(14,), total=14)

    with pytest.raises(FrozenInstanceError):
        result.total = 15  # type: ignore[misc]


def test_dice_roll_uses_tuple_roll_semantics() -> None:
    result = DiceRoll(expression="2d6", rolls=(3, 5), total=8)

    assert isinstance(result.rolls, tuple)
    with pytest.raises(TypeError):
        result.rolls[0] = 4  # type: ignore[index]


def test_dice_roll_total_equals_sum_of_rolls() -> None:
    result = DiceRoll(expression="3d4", rolls=(1, 2, 4), total=7)

    assert result.total == sum(result.rolls)


class Expression(str):
    pass


@pytest.mark.parametrize("expression", [None, 20, True, Expression("1d20")])
def test_dice_roll_rejects_non_exact_string_expression(expression: object) -> None:
    with pytest.raises(TypeError):
        DiceRoll(expression=expression, rolls=(1,), total=1)  # type: ignore[arg-type]


def test_dice_roll_rejects_list_rolls() -> None:
    with pytest.raises(TypeError):
        DiceRoll(expression="2d6", rolls=[3, 5], total=8)  # type: ignore[arg-type]


def test_dice_roll_rejects_empty_rolls() -> None:
    with pytest.raises(ValueError):
        DiceRoll(expression="1d20", rolls=(), total=0)


@pytest.mark.parametrize("roll", [1.0, "1", None, True])
def test_dice_roll_rejects_non_exact_integer_rolls(roll: object) -> None:
    with pytest.raises(TypeError):
        DiceRoll(expression="1d20", rolls=(roll,), total=1)  # type: ignore[arg-type]


@pytest.mark.parametrize("roll", [0, -1])
def test_dice_roll_rejects_non_positive_rolls(roll: int) -> None:
    with pytest.raises(ValueError):
        DiceRoll(expression="1d20", rolls=(roll,), total=roll)


@pytest.mark.parametrize("total", [1.0, "1", None, True])
def test_dice_roll_rejects_non_exact_integer_total(total: object) -> None:
    with pytest.raises(TypeError):
        DiceRoll(expression="1d20", rolls=(1,), total=total)  # type: ignore[arg-type]


def test_dice_roll_rejects_inconsistent_total() -> None:
    with pytest.raises(ValueError):
        DiceRoll(expression="2d6", rolls=(3, 5), total=7)


def test_dice_roll_does_not_validate_results_against_die_size() -> None:
    result = DiceRoll(expression="1d2", rolls=(20,), total=20)

    assert result.rolls == (20,)
