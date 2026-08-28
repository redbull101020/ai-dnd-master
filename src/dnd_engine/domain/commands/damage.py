from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class ApplyDamagePayload:
    target_id: str
    amount: int

    def __post_init__(self) -> None:
        if type(self.target_id) is not str:
            raise TypeError("target_id must be a str")
        if type(self.amount) is not int:
            raise TypeError("amount must be an int")
        if self.amount < 1:
            raise ValueError("amount must be at least 1")


@dataclass(frozen=True)
class ApplyDamageCommand:
    command_id: str
    campaign_id: str
    actor_id: str
    payload: ApplyDamagePayload
    type: Literal["ApplyDamageCommand"] = field(
        init=False,
        default="ApplyDamageCommand",
    )

    def __post_init__(self) -> None:
        for field_name in ("command_id", "campaign_id", "actor_id"):
            if type(getattr(self, field_name)) is not str:
                raise TypeError(f"{field_name} must be a str")
        if not isinstance(self.payload, ApplyDamagePayload):
            raise TypeError("payload must be an ApplyDamagePayload")
