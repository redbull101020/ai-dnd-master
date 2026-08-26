from dataclasses import dataclass

from dnd_engine.domain.commands.saving_throw import SavingThrowCommand
from dnd_engine.domain.rules.ability import ability_modifier
from dnd_engine.domain.rules.d20 import resolve_d20_roll
from dnd_engine.domain.rules.proficiency import character_proficiency_bonus
from dnd_engine.domain.services.dice import DiceEngine
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.d20 import D20Roll, RollMode


@dataclass(frozen=True)
class SavingThrowResult:
    ability: Ability
    dc: int
    roll: D20Roll
    ability_modifier: int
    proficiency_bonus: int
    total: int
    succeeded: bool

    def __post_init__(self) -> None:
        if not isinstance(self.ability, Ability):
            raise TypeError("ability must be an Ability")
        if type(self.dc) is not int:
            raise TypeError("dc must be an int")
        if not isinstance(self.roll, D20Roll):
            raise TypeError("roll must be a D20Roll")
        for field_name in ("ability_modifier", "proficiency_bonus", "total"):
            if type(getattr(self, field_name)) is not int:
                raise TypeError(f"{field_name} must be an int")
        if self.proficiency_bonus < 0:
            raise ValueError("proficiency_bonus must not be negative")
        if type(self.succeeded) is not bool:
            raise TypeError("succeeded must be a bool")
        if self.total != (
            self.roll.selected + self.ability_modifier + self.proficiency_bonus
        ):
            raise ValueError(
                "total must equal roll.selected plus ability_modifier "
                "plus proficiency_bonus"
            )
        if self.succeeded is not (self.total >= self.dc):
            raise ValueError("succeeded must equal total >= dc")


def resolve_character_saving_throw(
    command: SavingThrowCommand,
    creature: CreatureState,
    character: CharacterState,
    dice: DiceEngine,
    *,
    roll_mode: RollMode = RollMode.NORMAL,
) -> SavingThrowResult:
    if not isinstance(command, SavingThrowCommand):
        raise TypeError("command must be a SavingThrowCommand")
    if not isinstance(creature, CreatureState):
        raise TypeError("creature must be a CreatureState")
    if not isinstance(character, CharacterState):
        raise TypeError("character must be a CharacterState")
    if command.actor_id != creature.id:
        raise ValueError("command actor_id must match creature id")
    if command.actor_id != character.id:
        raise ValueError("command actor_id must match character id")

    ability = command.payload.ability
    score = getattr(creature.ability_scores, ability.value)
    ability_mod = ability_modifier(score)
    proficiency_bonus = (
        character_proficiency_bonus(character.total_level)
        if ability in character.saving_throw_proficiencies
        else 0
    )
    roll = resolve_d20_roll(dice, roll_mode)
    total = roll.selected + ability_mod + proficiency_bonus

    return SavingThrowResult(
        ability=ability,
        dc=command.payload.dc,
        roll=roll,
        ability_modifier=ability_mod,
        proficiency_bonus=proficiency_bonus,
        total=total,
        succeeded=total >= command.payload.dc,
    )
