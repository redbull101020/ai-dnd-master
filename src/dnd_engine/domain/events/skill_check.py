from dataclasses import dataclass
from datetime import datetime

from dnd_engine.domain.commands.skill_check import SkillCheckCommand
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.rules.skill_check import SkillCheckResult
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.d20 import D20Roll
from dnd_engine.domain.value_objects.skill import Skill


@dataclass(frozen=True)
class SkillCheckResolvedPayloadV1:
    skill: Skill
    ability: Ability
    dc: int
    roll: D20Roll
    ability_modifier: int
    proficiency_bonus: int
    total: int
    succeeded: bool

    def __post_init__(self) -> None:
        if not isinstance(self.skill, Skill):
            raise TypeError("skill must be a Skill")
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


def build_skill_check_resolved_v1(
    *,
    event_id: str,
    timestamp: datetime,
    command: SkillCheckCommand,
    outcome: SkillCheckResult,
) -> GameEvent:
    if not isinstance(command, SkillCheckCommand):
        raise TypeError("command must be a SkillCheckCommand")
    if not isinstance(outcome, SkillCheckResult):
        raise TypeError("outcome must be a SkillCheckResult")
    if outcome.skill != command.payload.skill:
        raise ValueError("outcome skill must match command payload skill")
    if outcome.ability != command.payload.ability:
        raise ValueError("outcome ability must match command payload ability")
    if outcome.dc != command.payload.dc:
        raise ValueError("outcome dc must match command payload dc")

    payload = SkillCheckResolvedPayloadV1(
        skill=outcome.skill,
        ability=outcome.ability,
        dc=outcome.dc,
        roll=outcome.roll,
        ability_modifier=outcome.ability_modifier,
        proficiency_bonus=outcome.proficiency_bonus,
        total=outcome.total,
        succeeded=outcome.succeeded,
    )

    return GameEvent(
        event_id=event_id,
        command_id=command.command_id,
        type="SkillCheckResolved",
        version=1,
        campaign_id=command.campaign_id,
        timestamp=timestamp,
        actor_id=command.actor_id,
        caused_by=None,
        payload={
            "skill": payload.skill.value,
            "ability": payload.ability.value,
            "dc": payload.dc,
            "roll": {
                "mode": payload.roll.mode.value,
                "rolls": payload.roll.rolls,
                "selected": payload.roll.selected,
            },
            "abilityModifier": payload.ability_modifier,
            "proficiencyBonus": payload.proficiency_bonus,
            "total": payload.total,
            "succeeded": payload.succeeded,
        },
    )
