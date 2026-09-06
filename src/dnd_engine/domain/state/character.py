from dataclasses import dataclass

from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.skill import Skill


@dataclass
class CharacterState:
    id: str
    total_level: int
    saving_throw_proficiencies: frozenset[Ability]
    skill_proficiencies: frozenset[Skill]
    weapon_proficiencies: frozenset[str]

    def __post_init__(self) -> None:
        if type(self.total_level) is not int:
            raise TypeError("total_level must be an int")
        if not 1 <= self.total_level <= 20:
            raise ValueError("total_level must be between 1 and 20")
        if type(self.saving_throw_proficiencies) is not frozenset:
            raise TypeError("saving_throw_proficiencies must be a frozenset")
        if not all(
            isinstance(ability, Ability)
            for ability in self.saving_throw_proficiencies
        ):
            raise TypeError(
                "saving_throw_proficiencies must contain only Ability values"
            )
        if type(self.skill_proficiencies) is not frozenset:
            raise TypeError("skill_proficiencies must be a frozenset")
        if not all(
            isinstance(skill, Skill) for skill in self.skill_proficiencies
        ):
            raise TypeError(
                "skill_proficiencies must contain only Skill values"
            )
        if type(self.weapon_proficiencies) is not frozenset:
            raise TypeError("weapon_proficiencies must be a frozenset")
        if not all(
            type(proficiency) is str
            for proficiency in self.weapon_proficiencies
        ):
            raise TypeError(
                "weapon_proficiencies must contain only str values"
            )
