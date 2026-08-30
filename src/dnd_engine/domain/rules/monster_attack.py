from dataclasses import dataclass

from dnd_engine.domain.commands.attack import AttackCommand
from dnd_engine.domain.definitions.monster_attack import MonsterAttackDefinition
from dnd_engine.domain.rules.d20 import resolve_d20_roll
from dnd_engine.domain.services.dice import DiceEngine
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.value_objects.d20 import D20Roll, RollMode


@dataclass(frozen=True)
class MonsterAttackResult:
    target_id: str
    action_id: str
    roll: D20Roll
    attack_bonus: int
    total: int
    target_armor_class: int
    hit: bool
    critical_hit: bool

    def __post_init__(self) -> None:
        if type(self.target_id) is not str:
            raise TypeError("target_id must be a str")
        if type(self.action_id) is not str:
            raise TypeError("action_id must be a str")
        if not isinstance(self.roll, D20Roll):
            raise TypeError("roll must be a D20Roll")
        for field_name in ("attack_bonus", "total", "target_armor_class"):
            if type(getattr(self, field_name)) is not int:
                raise TypeError(f"{field_name} must be an int")
        if type(self.hit) is not bool:
            raise TypeError("hit must be a bool")
        if type(self.critical_hit) is not bool:
            raise TypeError("critical_hit must be a bool")
        if self.total != self.roll.selected + self.attack_bonus:
            raise ValueError("total must equal roll.selected plus attack_bonus")

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


def resolve_monster_attack(
    command: AttackCommand,
    creature: CreatureState,
    action: MonsterAttackDefinition,
    dice: DiceEngine,
    *,
    target_armor_class: int,
    roll_mode: RollMode = RollMode.NORMAL,
) -> MonsterAttackResult:
    if not isinstance(command, AttackCommand):
        raise TypeError("command must be an AttackCommand")
    if not isinstance(creature, CreatureState):
        raise TypeError("creature must be a CreatureState")
    if not isinstance(action, MonsterAttackDefinition):
        raise TypeError("action must be a MonsterAttackDefinition")
    if type(target_armor_class) is not int:
        raise TypeError("target_armor_class must be an int")
    if command.actor_id != creature.id:
        raise ValueError("command actor_id must match creature id")

    roll = resolve_d20_roll(dice, roll_mode)
    total = roll.selected + action.attack_bonus

    if roll.selected == 1:
        hit = False
        critical_hit = False
    elif roll.selected == 20:
        hit = True
        critical_hit = True
    else:
        hit = total >= target_armor_class
        critical_hit = False

    return MonsterAttackResult(
        target_id=command.payload.target_id,
        action_id=action.action_id,
        roll=roll,
        attack_bonus=action.attack_bonus,
        total=total,
        target_armor_class=target_armor_class,
        hit=hit,
        critical_hit=critical_hit,
    )
