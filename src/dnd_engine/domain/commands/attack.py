from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class AttackPayload:
    target_id: str

    def __post_init__(self) -> None:
        if type(self.target_id) is not str:
            raise TypeError("target_id must be a str")


@dataclass(frozen=True)
class AttackCommand:
    command_id: str
    campaign_id: str
    actor_id: str
    payload: AttackPayload
    type: Literal["AttackCommand"] = field(
        init=False,
        default="AttackCommand",
    )

    def __post_init__(self) -> None:
        for field_name in ("command_id", "campaign_id", "actor_id"):
            if type(getattr(self, field_name)) is not str:
                raise TypeError(f"{field_name} must be a str")
        if not isinstance(self.payload, AttackPayload):
            raise TypeError("payload must be an AttackPayload")
