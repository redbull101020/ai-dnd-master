from dataclasses import dataclass


@dataclass(frozen=True)
class DiceRoll:
    expression: str
    rolls: tuple[int, ...]
    total: int

    def __post_init__(self) -> None:
        if type(self.expression) is not str:
            raise TypeError("expression must be a str")
        if not isinstance(self.rolls, tuple):
            raise TypeError("rolls must be a tuple")
        if not self.rolls:
            raise ValueError("rolls must not be empty")
        for roll in self.rolls:
            if type(roll) is not int:
                raise TypeError("each roll must be an int")
            if roll <= 0:
                raise ValueError("each roll must be positive")
        if type(self.total) is not int:
            raise TypeError("total must be an int")
        if self.total != sum(self.rolls):
            raise ValueError("total must equal the sum of rolls")
