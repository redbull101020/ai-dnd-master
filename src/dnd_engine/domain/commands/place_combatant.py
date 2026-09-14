from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class PlaceCombatantPayload:
    combat_id: str
    creature_id: str
    x: int
    y: int

    def __post_init__(self) -> None:
        for field_name in ("combat_id", "creature_id"):
            if type(getattr(self, field_name)) is not str:
                raise TypeError(f"{field_name} must be a str")
        for field_name in ("x", "y"):
            if type(getattr(self, field_name)) is not int:
                raise TypeError(f"{field_name} must be an int")


@dataclass(frozen=True)
class PlaceCombatantCommand:
    command_id: str
    campaign_id: str
    actor_id: str
    payload: PlaceCombatantPayload
    type: Literal["PlaceCombatantCommand"] = field(
        init=False,
        default="PlaceCombatantCommand",
    )

    def __post_init__(self) -> None:
        for field_name in ("command_id", "campaign_id", "actor_id"):
            if type(getattr(self, field_name)) is not str:
                raise TypeError(f"{field_name} must be a str")
        if not isinstance(self.payload, PlaceCombatantPayload):
            raise TypeError("payload must be a PlaceCombatantPayload")
