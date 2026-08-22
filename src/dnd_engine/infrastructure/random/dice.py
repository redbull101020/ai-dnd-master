import random
import re

from dnd_engine.domain.value_objects.dice_roll import DiceRoll


_DICE_EXPRESSION = re.compile(r"([1-9][0-9]*)d([1-9][0-9]*)")


class PythonDiceEngine:
    def __init__(self, rng: random.Random) -> None:
        if not isinstance(rng, random.Random):
            raise TypeError("rng must be a random.Random instance")
        self._rng = rng

    def roll(self, expression: str) -> DiceRoll:
        count, sides = self._parse_expression(expression)
        rolls = tuple(self._rng.randint(1, sides) for _ in range(count))
        return DiceRoll(expression=expression, rolls=rolls, total=sum(rolls))

    @staticmethod
    def _parse_expression(expression: str) -> tuple[int, int]:
        if type(expression) is not str:
            raise TypeError("expression must be a str")

        match = _DICE_EXPRESSION.fullmatch(expression)
        if match is None:
            raise ValueError("invalid dice expression")

        count, sides = (int(value) for value in match.groups())
        if sides < 2:
            raise ValueError("dice must have at least two sides")

        return count, sides
