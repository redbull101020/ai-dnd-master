from dataclasses import dataclass

from dnd_engine.domain.value_objects.ability_scores import AbilityScores


@dataclass
class CreatureState:
    id: str
    definition_id: str
    ability_scores: AbilityScores
    current_hp: int
    max_hp: int

    def __post_init__(self) -> None:
        if type(self.current_hp) is not int:
            raise TypeError("current_hp must be an int")
        if type(self.max_hp) is not int:
            raise TypeError("max_hp must be an int")
        if self.max_hp < 1:
            raise ValueError("max_hp must be at least 1")
        if not 0 <= self.current_hp <= self.max_hp:
            raise ValueError("current_hp must be between 0 and max_hp")
