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
    death_save_successes: int = 0
    death_save_failures: int = 0
    death_save_stable: bool = False
    dead: bool = False

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
        if type(self.death_save_successes) is not int:
            raise TypeError("death_save_successes must be an int")
        if not 0 <= self.death_save_successes <= 2:
            raise ValueError("death_save_successes must be between 0 and 2")
        if type(self.death_save_failures) is not int:
            raise TypeError("death_save_failures must be an int")
        if not 0 <= self.death_save_failures <= 3:
            raise ValueError("death_save_failures must be between 0 and 3")
        if type(self.death_save_stable) is not bool:
            raise TypeError("death_save_stable must be a bool")
        if type(self.dead) is not bool:
            raise TypeError("dead must be a bool")
        if self.death_save_stable and self.dead:
            raise ValueError("death_save_stable and dead cannot both be true")
        if self.death_save_stable and (
            self.death_save_successes != 0 or self.death_save_failures != 0
        ):
            raise ValueError(
                "a stable CharacterState must have reset death save counters"
            )
        if self.death_save_failures == 3 and not self.dead:
            raise ValueError("three death save failures require dead to be true")
