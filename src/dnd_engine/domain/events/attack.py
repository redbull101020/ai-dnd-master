from dataclasses import dataclass
from datetime import datetime

from dnd_engine.domain.commands.attack import AttackCommand
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.rules.attack import AttackResult
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.d20 import D20Roll


@dataclass(frozen=True)
class AttackResolvedPayloadV1:
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


def build_attack_resolved_v1(
    *,
    event_id: str,
    timestamp: datetime,
    command: AttackCommand,
    outcome: AttackResult,
) -> GameEvent:
    if not isinstance(command, AttackCommand):
        raise TypeError("command must be an AttackCommand")
    if not isinstance(outcome, AttackResult):
        raise TypeError("outcome must be an AttackResult")
    if outcome.target_id != command.payload.target_id:
        raise ValueError("outcome target_id must match command payload target_id")

    payload = AttackResolvedPayloadV1(
        target_id=outcome.target_id,
        roll=outcome.roll,
        ability=outcome.ability,
        ability_modifier=outcome.ability_modifier,
        proficiency_bonus=outcome.proficiency_bonus,
        total=outcome.total,
        target_armor_class=outcome.target_armor_class,
        hit=outcome.hit,
        critical_hit=outcome.critical_hit,
    )

    return GameEvent(
        event_id=event_id,
        command_id=command.command_id,
        type="AttackResolved",
        version=1,
        campaign_id=command.campaign_id,
        timestamp=timestamp,
        actor_id=command.actor_id,
        caused_by=None,
        payload={
            "targetId": payload.target_id,
            "roll": {
                "mode": payload.roll.mode.value,
                "rolls": payload.roll.rolls,
                "selected": payload.roll.selected,
            },
            "ability": payload.ability.value,
            "abilityModifier": payload.ability_modifier,
            "proficiencyBonus": payload.proficiency_bonus,
            "total": payload.total,
            "targetArmorClass": payload.target_armor_class,
            "hit": payload.hit,
            "criticalHit": payload.critical_hit,
        },
    )
