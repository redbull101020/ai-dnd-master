from dataclasses import dataclass

from dnd_engine.domain.definitions.base import Definition
from dnd_engine.domain.value_objects.ability_scores import AbilityScores


@dataclass(frozen=True)
class MonsterDefinition(Definition):
    name: str
    ability_scores: AbilityScores
    armor_class: int

    def __post_init__(self) -> None:
        if type(self.armor_class) is not int:
            raise TypeError("armor_class must be an int")
