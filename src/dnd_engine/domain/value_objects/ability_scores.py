from dataclasses import dataclass, fields


@dataclass(frozen=True)
class AbilityScores:
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int

    def __post_init__(self) -> None:
        for field in fields(self):
            score = getattr(self, field.name)
            if type(score) is not int:
                raise TypeError(f"{field.name} must be an int")
            if not 1 <= score <= 30:
                raise ValueError(f"{field.name} must be between 1 and 30")
