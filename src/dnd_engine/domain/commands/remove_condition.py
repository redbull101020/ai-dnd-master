from dataclasses import dataclass, field
from typing import Literal

from dnd_engine.domain.value_objects.condition import Condition


@dataclass(frozen=True)
class RemoveConditionPayload:
    target_id: str
    condition: Condition

    def __post_init__(self) -> None:
        if type(self.target_id) is not str:
            raise TypeError("target_id must be a str")
        if not isinstance(self.condition, Condition):
            raise TypeError("condition must be a Condition")


@dataclass(frozen=True)
class RemoveConditionCommand:
    command_id: str
    campaign_id: str
    actor_id: str
    payload: RemoveConditionPayload
    type: Literal["RemoveConditionCommand"] = field(
        init=False,
        default="RemoveConditionCommand",
    )

    def __post_init__(self) -> None:
        for field_name in ("command_id", "campaign_id", "actor_id"):
            if type(getattr(self, field_name)) is not str:
                raise TypeError(f"{field_name} must be a str")
        if not isinstance(self.payload, RemoveConditionPayload):
            raise TypeError("payload must be a RemoveConditionPayload")
