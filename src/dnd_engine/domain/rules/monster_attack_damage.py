from dataclasses import dataclass

from dnd_engine.domain.definitions.monster_attack import MonsterAttackDefinition
from dnd_engine.domain.dice import parse_ndm
from dnd_engine.domain.rules.monster_attack import MonsterAttackResult
from dnd_engine.domain.services.dice import DiceEngine
from dnd_engine.domain.value_objects.damage_type import DamageType
from dnd_engine.domain.value_objects.dice_roll import DiceRoll


@dataclass(frozen=True)
class MonsterAttackDamageResult:
    target_id: str
    action_id: str
    roll: DiceRoll
    damage_modifier: int
    damage_type: DamageType
    critical_hit: bool
    amount: int

    def __post_init__(self) -> None:
        if type(self.target_id) is not str:
            raise TypeError("target_id must be a str")
        if type(self.action_id) is not str:
            raise TypeError("action_id must be a str")
        if not isinstance(self.roll, DiceRoll):
            raise TypeError("roll must be a DiceRoll")
        if type(self.damage_modifier) is not int:
            raise TypeError("damage_modifier must be an int")
        if not isinstance(self.damage_type, DamageType):
            raise TypeError("damage_type must be a DamageType")
        if type(self.critical_hit) is not bool:
            raise TypeError("critical_hit must be a bool")
        if type(self.amount) is not int:
            raise TypeError("amount must be an int")
        if self.amount != max(0, self.roll.total + self.damage_modifier):
            raise ValueError(
                "amount must equal max(0, roll.total plus damage_modifier)"
            )


def resolve_monster_attack_damage(
    attack_outcome: MonsterAttackResult,
    attack: MonsterAttackDefinition,
    dice: DiceEngine,
) -> MonsterAttackDamageResult:
    if not isinstance(attack_outcome, MonsterAttackResult):
        raise TypeError("attack_outcome must be a MonsterAttackResult")
    if not isinstance(attack, MonsterAttackDefinition):
        raise TypeError("attack must be a MonsterAttackDefinition")
    if not attack_outcome.hit:
        raise ValueError("attack_outcome must be a hit")
    if attack_outcome.action_id != attack.action_id:
        raise ValueError("attack_outcome action_id must match attack action_id")

    count, sides = parse_ndm(attack.damage_dice)
    expression = (
        f"{2 * count}d{sides}" if attack_outcome.critical_hit else attack.damage_dice
    )
    roll = dice.roll(expression)
    if not isinstance(roll, DiceRoll):
        raise TypeError("dice.roll must return a DiceRoll")
    if roll.expression != expression:
        raise ValueError("dice.roll response expression must match requested expression")

    return MonsterAttackDamageResult(
        target_id=attack_outcome.target_id,
        action_id=attack.action_id,
        roll=roll,
        damage_modifier=attack.damage_modifier,
        damage_type=attack.damage_type,
        critical_hit=attack_outcome.critical_hit,
        amount=max(0, roll.total + attack.damage_modifier),
    )
