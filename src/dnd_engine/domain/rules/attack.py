from dataclasses import dataclass

from dnd_engine.domain.commands.attack import AttackCommand
from dnd_engine.domain.rules.ability import ability_modifier
from dnd_engine.domain.rules.d20 import resolve_d20_roll
from dnd_engine.domain.rules.proficiency import character_proficiency_bonus
from dnd_engine.domain.services.dice import DiceEngine
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.d20 import D20Roll, RollMode


@dataclass(frozen=True)
class AttackResult:
    target_id: str
    roll: D20Roll
    ability: Ability
    ability_modifier: int
    proficiency_bonus: int
    total: int
    target_armor_class: int
    hit: bool
    critical_hit: bool

    def __post_init__(self) -> None:
        if type(self.target_id) is not str:
            raise TypeError("target_id must be a str")
        if not isinstance(self.roll, D20Roll):
            raise TypeError("roll must be a D20Roll")
        if not isinstance(self.ability, Ability):
            raise TypeError("ability must be an Ability")
        for field_name in (
            "ability_modifier",
            "proficiency_bonus",
            "total",
            "target_armor_class",
        ):
            if type(getattr(self, field_name)) is not int:
                raise TypeError(f"{field_name} must be an int")
        if self.proficiency_bonus < 0:
            raise ValueError("proficiency_bonus must not be negative")
        if type(self.hit) is not bool:
            raise TypeError("hit must be a bool")
        if type(self.critical_hit) is not bool:
            raise TypeError("critical_hit must be a bool")
        if self.total != (
            self.roll.selected + self.ability_modifier + self.proficiency_bonus
        ):
            raise ValueError(
                "total must equal roll.selected plus ability_modifier "
                "plus proficiency_bonus"
            )

        if self.roll.selected == 1:
            if self.hit or self.critical_hit:
                raise ValueError(
                    "natural 1 must be a miss and must not be a critical hit"
                )
        elif self.roll.selected == 20:
            if not self.hit or not self.critical_hit:
                raise ValueError("natural 20 must be a hit and a critical hit")
        else:
            if self.hit is not (self.total >= self.target_armor_class):
                raise ValueError("hit must equal total >= target_armor_class")
            if self.critical_hit:
                raise ValueError("only a natural 20 can be a critical hit")


def resolve_character_unarmed_attack(
    command: AttackCommand,
    creature: CreatureState,
    character: CharacterState,
    dice: DiceEngine,
    *,
    target_armor_class: int,
    roll_mode: RollMode = RollMode.NORMAL,
) -> AttackResult:
    if not isinstance(command, AttackCommand):
        raise TypeError("command must be an AttackCommand")
    if not isinstance(creature, CreatureState):
        raise TypeError("creature must be a CreatureState")
    if not isinstance(character, CharacterState):
        raise TypeError("character must be a CharacterState")
    if type(target_armor_class) is not int:
        raise TypeError("target_armor_class must be an int")
    if command.actor_id != creature.id:
        raise ValueError("command actor_id must match creature id")
    if command.actor_id != character.id:
        raise ValueError("command actor_id must match character id")

    ability = Ability.STRENGTH
    ability_mod = ability_modifier(creature.ability_scores.strength)
    proficiency_bonus = character_proficiency_bonus(character.total_level)
    roll = resolve_d20_roll(dice, roll_mode)
    total = roll.selected + ability_mod + proficiency_bonus

    if roll.selected == 1:
        hit = False
        critical_hit = False
    elif roll.selected == 20:
        hit = True
        critical_hit = True
    else:
        hit = total >= target_armor_class
        critical_hit = False

    return AttackResult(
        target_id=command.payload.target_id,
        roll=roll,
        ability=ability,
        ability_modifier=ability_mod,
        proficiency_bonus=proficiency_bonus,
        total=total,
        target_armor_class=target_armor_class,
        hit=hit,
        critical_hit=critical_hit,
    )
