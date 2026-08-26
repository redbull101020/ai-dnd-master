from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.rules.d20 import resolve_d20_roll
from dnd_engine.domain.value_objects.d20 import D20Roll, RollMode
from dnd_engine.domain.value_objects.dice_roll import DiceRoll


class ScriptedDiceEngine:
    def __init__(self, *responses: object) -> None:
        self._responses = iter(responses)
        self.calls: list[str] = []

    def roll(self, expression: str) -> DiceRoll:
        self.calls.append(expression)
        return next(self._responses)  # type: ignore[return-value]


def dice_roll(
    raw: int,
    *,
    expression: str = "1d20",
) -> DiceRoll:
    return DiceRoll(expression=expression, rolls=(raw,), total=raw)


def test_roll_mode_has_exact_closed_values_and_order() -> None:
    assert tuple(RollMode) == (
        RollMode.NORMAL,
        RollMode.ADVANTAGE,
        RollMode.DISADVANTAGE,
    )
    assert tuple(mode.value for mode in RollMode) == (
        "normal",
        "advantage",
        "disadvantage",
    )


@pytest.mark.parametrize(
    ("mode", "rolls", "selected"),
    [
        (RollMode.NORMAL, (12,), 12),
        (RollMode.ADVANTAGE, (7, 16), 16),
        (RollMode.DISADVANTAGE, (7, 16), 7),
        (RollMode.ADVANTAGE, (12, 12), 12),
        (RollMode.DISADVANTAGE, (12, 12), 12),
    ],
)
def test_d20_roll_accepts_canonical_values(
    mode: RollMode,
    rolls: tuple[int, ...],
    selected: int,
) -> None:
    result = D20Roll(mode=mode, rolls=rolls, selected=selected)

    assert tuple(field.name for field in fields(result)) == (
        "mode",
        "rolls",
        "selected",
    )
    assert result == D20Roll(mode=mode, rolls=rolls, selected=selected)


def test_d20_roll_is_immutable() -> None:
    result = D20Roll(mode=RollMode.NORMAL, rolls=(12,), selected=12)

    with pytest.raises(FrozenInstanceError):
        result.selected = 13  # type: ignore[misc]


def test_d20_roll_rejects_arbitrary_mode_string() -> None:
    with pytest.raises(TypeError):
        D20Roll(mode="advantage", rolls=(7, 16), selected=16)  # type: ignore[arg-type]


def test_d20_roll_rejects_non_tuple_rolls() -> None:
    with pytest.raises(TypeError):
        D20Roll(mode=RollMode.NORMAL, rolls=[12], selected=12)  # type: ignore[arg-type]


@pytest.mark.parametrize("roll", [True, 1.0, "1", None])
def test_d20_roll_rejects_non_exact_integer_rolls(roll: object) -> None:
    with pytest.raises(TypeError):
        D20Roll(mode=RollMode.NORMAL, rolls=(roll,), selected=1)  # type: ignore[arg-type]


@pytest.mark.parametrize("roll", [0, 21])
def test_d20_roll_rejects_rolls_outside_d20_range(roll: int) -> None:
    with pytest.raises(ValueError):
        D20Roll(mode=RollMode.NORMAL, rolls=(roll,), selected=1)


@pytest.mark.parametrize("selected", [True, 1.0, "1", None])
def test_d20_roll_rejects_non_exact_integer_selected(selected: object) -> None:
    with pytest.raises(TypeError):
        D20Roll(mode=RollMode.NORMAL, rolls=(1,), selected=selected)  # type: ignore[arg-type]


@pytest.mark.parametrize("selected", [0, 21])
def test_d20_roll_rejects_selected_outside_d20_range(selected: int) -> None:
    with pytest.raises(ValueError):
        D20Roll(mode=RollMode.NORMAL, rolls=(1,), selected=selected)


@pytest.mark.parametrize(
    ("mode", "rolls", "selected"),
    [
        (RollMode.NORMAL, (7, 16), 7),
        (RollMode.ADVANTAGE, (7,), 7),
        (RollMode.DISADVANTAGE, (7,), 7),
        (RollMode.ADVANTAGE, (7, 16), 7),
        (RollMode.DISADVANTAGE, (7, 16), 16),
    ],
)
def test_d20_roll_rejects_invalid_mode_shape_or_selection(
    mode: RollMode,
    rolls: tuple[int, ...],
    selected: int,
) -> None:
    with pytest.raises(ValueError):
        D20Roll(mode=mode, rolls=rolls, selected=selected)


@pytest.mark.parametrize(
    ("mode", "raws", "expected_selected", "expected_calls"),
    [
        (RollMode.NORMAL, (12,), 12, ["1d20"]),
        (RollMode.ADVANTAGE, (7, 16), 16, ["1d20", "1d20"]),
        (RollMode.DISADVANTAGE, (7, 16), 7, ["1d20", "1d20"]),
    ],
)
def test_resolve_d20_roll_uses_independent_primitive_rolls(
    mode: RollMode,
    raws: tuple[int, ...],
    expected_selected: int,
    expected_calls: list[str],
) -> None:
    dice = ScriptedDiceEngine(*(dice_roll(raw) for raw in raws))

    result = resolve_d20_roll(dice, mode)

    assert dice.calls == expected_calls
    assert result == D20Roll(mode=mode, rolls=raws, selected=expected_selected)


def test_resolve_d20_roll_rejects_non_dice_roll_response() -> None:
    with pytest.raises(TypeError, match="DiceRoll"):
        resolve_d20_roll(ScriptedDiceEngine(object()), RollMode.NORMAL)


def test_resolve_d20_roll_rejects_wrong_expression_response() -> None:
    response = DiceRoll(expression="1d12", rolls=(7,), total=7)

    with pytest.raises(ValueError, match="expression"):
        resolve_d20_roll(ScriptedDiceEngine(response), RollMode.NORMAL)


def test_resolve_d20_roll_rejects_non_primitive_response_shape() -> None:
    response = DiceRoll(expression="1d20", rolls=(7, 16), total=23)

    with pytest.raises(ValueError, match="exactly one"):
        resolve_d20_roll(ScriptedDiceEngine(response), RollMode.NORMAL)
