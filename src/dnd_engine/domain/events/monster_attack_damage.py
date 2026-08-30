from dataclasses import dataclass
from datetime import datetime

from dnd_engine.domain.commands.attack import AttackCommand
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.rules.monster_attack_damage import MonsterAttackDamageResult
from dnd_engine.domain.value_objects.damage_type import DamageType
from dnd_engine.domain.value_objects.dice_roll import DiceRoll


@dataclass(frozen=True)
class MonsterAttackDamageResolvedPayloadV1:
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


def build_monster_attack_damage_resolved_v1(
    *,
    event_id: str,
    timestamp: datetime,
    command: AttackCommand,
    outcome: MonsterAttackDamageResult,
    caused_by: str,
) -> GameEvent:
    if not isinstance(command, AttackCommand):
        raise TypeError("command must be an AttackCommand")
    if not isinstance(outcome, MonsterAttackDamageResult):
        raise TypeError("outcome must be a MonsterAttackDamageResult")
    if type(caused_by) is not str:
        raise TypeError("caused_by must be a str")
    if outcome.target_id != command.payload.target_id:
        raise ValueError("outcome target_id must match command payload target_id")

    payload = MonsterAttackDamageResolvedPayloadV1(
        target_id=outcome.target_id,
        action_id=outcome.action_id,
        roll=outcome.roll,
        damage_modifier=outcome.damage_modifier,
        damage_type=outcome.damage_type,
        critical_hit=outcome.critical_hit,
        amount=outcome.amount,
    )

    return GameEvent(
        event_id=event_id,
        command_id=command.command_id,
        type="MonsterAttackDamageResolved",
        version=1,
        campaign_id=command.campaign_id,
        timestamp=timestamp,
        actor_id=command.actor_id,
        caused_by=caused_by,
        payload={
            "targetId": payload.target_id,
            "actionId": payload.action_id,
            "roll": {
                "expression": payload.roll.expression,
                "rolls": payload.roll.rolls,
                "total": payload.roll.total,
            },
            "damageModifier": payload.damage_modifier,
            "damageType": payload.damage_type.value,
            "criticalHit": payload.critical_hit,
            "amount": payload.amount,
        },
    )
