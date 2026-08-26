from dataclasses import dataclass, field
from typing import Literal

from dnd_engine.domain.value_objects.ability import Ability


@dataclass(frozen=True)
class SavingThrowPayload:
    ability: Ability
    dc: int

    def __post_init__(self) -> None:
        if not isinstance(self.ability, Ability):
            raise TypeError("ability must be an Ability")
        if type(self.dc) is not int:
            raise TypeError("dc must be an int")


@dataclass(frozen=True)
class SavingThrowCommand:
    command_id: str
    campaign_id: str
    actor_id: str
    payload: SavingThrowPayload
    type: Literal["SavingThrowCommand"] = field(
        init=False,
        default="SavingThrowCommand",
    )

    def __post_init__(self) -> None:
        for field_name in ("command_id", "campaign_id", "actor_id"):
            if type(getattr(self, field_name)) is not str:
                raise TypeError(f"{field_name} must be a str")
        if not isinstance(self.payload, SavingThrowPayload):
            raise TypeError("payload must be a SavingThrowPayload")
