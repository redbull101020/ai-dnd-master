from dataclasses import dataclass, field
from typing import Literal

from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.skill import Skill


@dataclass(frozen=True)
class SkillCheckPayload:
    skill: Skill
    ability: Ability
    dc: int

    def __post_init__(self) -> None:
        if not isinstance(self.skill, Skill):
            raise TypeError("skill must be a Skill")
        if not isinstance(self.ability, Ability):
            raise TypeError("ability must be an Ability")
        if type(self.dc) is not int:
            raise TypeError("dc must be an int")


@dataclass(frozen=True)
class SkillCheckCommand:
    command_id: str
    campaign_id: str
    actor_id: str
    payload: SkillCheckPayload
    type: Literal["SkillCheckCommand"] = field(
        init=False,
        default="SkillCheckCommand",
    )

    def __post_init__(self) -> None:
        for field_name in ("command_id", "campaign_id", "actor_id"):
            if type(getattr(self, field_name)) is not str:
                raise TypeError(f"{field_name} must be a str")
        if not isinstance(self.payload, SkillCheckPayload):
            raise TypeError("payload must be a SkillCheckPayload")
