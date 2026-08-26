from dnd_engine.domain.services.dice import DiceEngine
from dnd_engine.domain.value_objects.d20 import D20Roll, RollMode
from dnd_engine.domain.value_objects.dice_roll import DiceRoll


def resolve_d20_roll(dice: DiceEngine, mode: RollMode) -> D20Roll:
    if not isinstance(mode, RollMode):
        raise TypeError("mode must be a RollMode")

    roll_count = 1 if mode is RollMode.NORMAL else 2
    raw_rolls = tuple(_roll_one_d20(dice) for _ in range(roll_count))

    if mode is RollMode.NORMAL:
        selected = raw_rolls[0]
    elif mode is RollMode.ADVANTAGE:
        selected = max(raw_rolls)
    else:
        selected = min(raw_rolls)

    return D20Roll(mode=mode, rolls=raw_rolls, selected=selected)


def _roll_one_d20(dice: DiceEngine) -> int:
    roll = dice.roll("1d20")
    if not isinstance(roll, DiceRoll):
        raise TypeError("dice.roll must return a DiceRoll")
    if roll.expression != "1d20":
        raise ValueError('dice.roll response expression must be "1d20"')
    if len(roll.rolls) != 1:
        raise ValueError("dice.roll response must contain exactly one roll")
    return roll.rolls[0]
