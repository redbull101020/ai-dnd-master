import random

import pytest

from dnd_engine.domain.value_objects.dice_roll import DiceRoll
from dnd_engine.infrastructure.random.dice import PythonDiceEngine


def test_python_dice_engine_rejects_module_global_random() -> None:
    with pytest.raises(TypeError):
        PythonDiceEngine(random)  # type: ignore[arg-type]


def test_python_dice_engine_accepts_system_random() -> None:
    PythonDiceEngine(random.SystemRandom())


@pytest.mark.parametrize(
    ("expression", "count", "sides"),
    [
        ("1d2", 1, 2),
        ("1d20", 1, 20),
        ("2d6", 2, 6),
        ("10d100", 10, 100),
        ("1d7", 1, 7),
    ],
)
def test_python_dice_engine_rolls_valid_expression(
    expression: str,
    count: int,
    sides: int,
) -> None:
    engine = PythonDiceEngine(random.Random(42))

    result = engine.roll(expression)

    assert isinstance(result, DiceRoll)
    assert result.expression == expression
    assert len(result.rolls) == count
    assert all(1 <= roll <= sides for roll in result.rolls)
    assert result.total == sum(result.rolls)


def test_same_seed_engines_produce_equal_sequences() -> None:
    expressions = ("1d20", "2d6", "1d8", "3d4")
    first_engine = PythonDiceEngine(random.Random(8675309))
    second_engine = PythonDiceEngine(random.Random(8675309))

    first_sequence = tuple(first_engine.roll(value) for value in expressions)
    second_sequence = tuple(second_engine.roll(value) for value in expressions)

    assert first_sequence == second_sequence


def test_engine_uses_its_injected_rng_state() -> None:
    rng = random.Random(31)
    reference_rng = random.Random(31)
    engine = PythonDiceEngine(rng)

    result = engine.roll("3d8")
    expected_rolls = tuple(reference_rng.randint(1, 8) for _ in range(3))

    assert result.rolls == expected_rolls
    assert rng.getstate() == reference_rng.getstate()


def test_engine_does_not_modify_module_global_rng_state() -> None:
    global_state = random.getstate()
    engine = PythonDiceEngine(random.Random(7))

    engine.roll("4d6")

    assert random.getstate() == global_state


@pytest.mark.parametrize(
    "expression",
    [
        "",
        "foo",
        "d20",
        "1d",
        "0d20",
        "-1d20",
        "1d0",
        "1d1",
        "1D20",
        " 1d20",
        "1d20 ",
        "1d20+5",
        "2d20kh1",
        "2d20kl1",
        "4d6d1",
        "1d6!",
    ],
)
def test_python_dice_engine_rejects_invalid_expression(expression: str) -> None:
    engine = PythonDiceEngine(random.Random(42))

    with pytest.raises(ValueError):
        engine.roll(expression)


class Expression(str):
    pass


@pytest.mark.parametrize("expression", [None, 20, True, Expression("1d20")])
def test_python_dice_engine_rejects_non_exact_string_expression(
    expression: object,
) -> None:
    engine = PythonDiceEngine(random.Random(42))

    with pytest.raises(TypeError):
        engine.roll(expression)  # type: ignore[arg-type]
