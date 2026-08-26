from dataclasses import dataclass
from enum import StrEnum


class RollMode(StrEnum):
    NORMAL = "normal"
    ADVANTAGE = "advantage"
    DISADVANTAGE = "disadvantage"


@dataclass(frozen=True)
class D20Roll:
    mode: RollMode
    rolls: tuple[int, ...]
    selected: int

    def __post_init__(self) -> None:
        if not isinstance(self.mode, RollMode):
            raise TypeError("mode must be a RollMode")
        if not isinstance(self.rolls, tuple):
            raise TypeError("rolls must be a tuple")
        for roll in self.rolls:
            if type(roll) is not int:
                raise TypeError("each roll must be an int")
            if not 1 <= roll <= 20:
                raise ValueError("each roll must be between 1 and 20")
        if type(self.selected) is not int:
            raise TypeError("selected must be an int")
        if not 1 <= self.selected <= 20:
            raise ValueError("selected must be between 1 and 20")

        if self.mode is RollMode.NORMAL:
            if len(self.rolls) != 1:
                raise ValueError("normal mode requires exactly one roll")
            expected_selected = self.rolls[0]
        elif self.mode is RollMode.ADVANTAGE:
            if len(self.rolls) != 2:
                raise ValueError("advantage mode requires exactly two rolls")
            expected_selected = max(self.rolls)
        else:
            if len(self.rolls) != 2:
                raise ValueError("disadvantage mode requires exactly two rolls")
            expected_selected = min(self.rolls)

        if self.selected != expected_selected:
            raise ValueError("selected must match the effective roll mode")
