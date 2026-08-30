from dataclasses import dataclass
from datetime import datetime

from dnd_engine.domain.commands.attack import AttackCommand
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.rules.monster_attack import MonsterAttackResult
from dnd_engine.domain.value_objects.d20 import D20Roll


@dataclass(frozen=True)
class MonsterAttackResolvedPayloadV1:
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


def build_monster_attack_resolved_v1(
    *,
    event_id: str,
    timestamp: datetime,
    command: AttackCommand,
    outcome: MonsterAttackResult,
) -> GameEvent:
    if not isinstance(command, AttackCommand):
        raise TypeError("command must be an AttackCommand")
    if not isinstance(outcome, MonsterAttackResult):
        raise TypeError("outcome must be a MonsterAttackResult")
    if outcome.target_id != command.payload.target_id:
        raise ValueError("outcome target_id must match command payload target_id")

    payload = MonsterAttackResolvedPayloadV1(
        target_id=outcome.target_id,
        action_id=outcome.action_id,
        roll=outcome.roll,
        attack_bonus=outcome.attack_bonus,
        total=outcome.total,
        target_armor_class=outcome.target_armor_class,
        hit=outcome.hit,
        critical_hit=outcome.critical_hit,
    )

    return GameEvent(
        event_id=event_id,
        command_id=command.command_id,
        type="MonsterAttackResolved",
        version=1,
        campaign_id=command.campaign_id,
        timestamp=timestamp,
        actor_id=command.actor_id,
        caused_by=None,
        payload={
            "targetId": payload.target_id,
            "actionId": payload.action_id,
            "roll": {
                "mode": payload.roll.mode.value,
                "rolls": payload.roll.rolls,
                "selected": payload.roll.selected,
            },
            "attackBonus": payload.attack_bonus,
            "total": payload.total,
            "targetArmorClass": payload.target_armor_class,
            "hit": payload.hit,
            "criticalHit": payload.critical_hit,
        },
    )
