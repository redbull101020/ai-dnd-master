from dataclasses import dataclass

from dnd_engine.domain.commands.ability_check import AbilityCheckCommand
from dnd_engine.domain.rules.ability import ability_modifier
from dnd_engine.domain.rules.d20 import resolve_d20_roll
from dnd_engine.domain.services.dice import DiceEngine
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.d20 import D20Roll, RollMode


@dataclass(frozen=True)
class AbilityCheckResult:
    ability: Ability
    dc: int
    roll: D20Roll
    modifier: int
    total: int
    succeeded: bool

    def __post_init__(self) -> None:
        if not isinstance(self.ability, Ability):
            raise TypeError("ability must be an Ability")
        for field_name in ("dc", "modifier", "total"):
            if type(getattr(self, field_name)) is not int:
                raise TypeError(f"{field_name} must be an int")
        if not isinstance(self.roll, D20Roll):
            raise TypeError("roll must be a D20Roll")
        if type(self.succeeded) is not bool:
            raise TypeError("succeeded must be a bool")
        if self.total != self.roll.selected + self.modifier:
            raise ValueError("total must equal roll.selected plus modifier")
        if self.succeeded is not (self.total >= self.dc):
            raise ValueError("succeeded must equal total >= dc")


def resolve_ability_check(
    command: AbilityCheckCommand,
    creature: CreatureState,
    dice: DiceEngine,
    *,
    roll_mode: RollMode = RollMode.NORMAL,
) -> AbilityCheckResult:
    if not isinstance(command, AbilityCheckCommand):
        raise TypeError("command must be an AbilityCheckCommand")
    if not isinstance(creature, CreatureState):
        raise TypeError("creature must be a CreatureState")

    score = getattr(creature.ability_scores, command.payload.ability.value)
    modifier = ability_modifier(score)
    roll = resolve_d20_roll(dice, roll_mode)
    total = roll.selected + modifier

    return AbilityCheckResult(
        ability=command.payload.ability,
        dc=command.payload.dc,
        roll=roll,
        modifier=modifier,
        total=total,
        succeeded=total >= command.payload.dc,
    )
