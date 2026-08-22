from typing import Protocol

from dnd_engine.domain.value_objects.dice_roll import DiceRoll


class DiceEngine(Protocol):
    def roll(self, expression: str) -> DiceRoll:
        ...
