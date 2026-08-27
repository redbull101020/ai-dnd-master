import random

from dnd_engine.domain.dice import parse_ndm
from dnd_engine.domain.value_objects.dice_roll import DiceRoll


class PythonDiceEngine:
    def __init__(self, rng: random.Random) -> None:
        if not isinstance(rng, random.Random):
            raise TypeError("rng must be a random.Random instance")
        self._rng = rng

    def roll(self, expression: str) -> DiceRoll:
        count, sides = parse_ndm(expression)
        rolls = tuple(self._rng.randint(1, sides) for _ in range(count))
        return DiceRoll(expression=expression, rolls=rolls, total=sum(rolls))
