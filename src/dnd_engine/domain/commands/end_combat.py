from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class EndCombatPayload:
    combat_id: str

    def __post_init__(self) -> None:
        if type(self.combat_id) is not str:
            raise TypeError("combat_id must be a str")


@dataclass(frozen=True)
class EndCombatCommand:
    command_id: str
    campaign_id: str
    actor_id: str
    payload: EndCombatPayload
    type: Literal["EndCombatCommand"] = field(
        init=False,
        default="EndCombatCommand",
    )

    def __post_init__(self) -> None:
        for field_name in ("command_id", "campaign_id", "actor_id"):
            if type(getattr(self, field_name)) is not str:
                raise TypeError(f"{field_name} must be a str")
        if not isinstance(self.payload, EndCombatPayload):
            raise TypeError("payload must be an EndCombatPayload")
