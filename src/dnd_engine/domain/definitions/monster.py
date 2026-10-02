from dataclasses import dataclass

from dnd_engine.domain.definitions.base import Definition
from dnd_engine.domain.definitions.monster_attack import MonsterAttackDefinition
from dnd_engine.domain.value_objects.ability_scores import AbilityScores


@dataclass(frozen=True)
class MonsterDefinition(Definition):
    name: str
    ability_scores: AbilityScores
    armor_class: int
    attacks: tuple[MonsterAttackDefinition, ...] = ()
    walking_speed: int | None = None

    def __post_init__(self) -> None:
        if self.walking_speed is not None:
            if type(self.walking_speed) is not int:
                raise TypeError("walking_speed must be an int or None")
            if self.walking_speed < 0:
                raise ValueError("walking_speed must be non-negative")
        if type(self.armor_class) is not int:
            raise TypeError("armor_class must be an int")
        if type(self.attacks) is not tuple:
            raise TypeError("attacks must be a tuple")
        if not all(
            isinstance(attack, MonsterAttackDefinition) for attack in self.attacks
        ):
            raise TypeError("attacks must contain only MonsterAttackDefinition values")
        action_ids = [attack.action_id for attack in self.attacks]
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("attacks action_id must be unique within a MonsterDefinition")
