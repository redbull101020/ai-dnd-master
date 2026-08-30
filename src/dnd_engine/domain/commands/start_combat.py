from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class StartCombatPayload:
    combat_id: str
    participant_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.combat_id) is not str:
            raise TypeError("combat_id must be a str")
        if type(self.participant_ids) is not tuple:
            raise TypeError("participant_ids must be a tuple")
        if not all(type(pid) is str for pid in self.participant_ids):
            raise TypeError("participant_ids must contain only str values")
        if len(self.participant_ids) == 0:
            raise ValueError("participant_ids must not be empty")
        if len(set(self.participant_ids)) != len(self.participant_ids):
            raise ValueError("participant_ids must not contain duplicates")


@dataclass(frozen=True)
class StartCombatCommand:
    command_id: str
    campaign_id: str
    actor_id: str
    payload: StartCombatPayload
    type: Literal["StartCombatCommand"] = field(
        init=False,
        default="StartCombatCommand",
    )

    def __post_init__(self) -> None:
        for field_name in ("command_id", "campaign_id", "actor_id"):
            if type(getattr(self, field_name)) is not str:
                raise TypeError(f"{field_name} must be a str")
        if not isinstance(self.payload, StartCombatPayload):
            raise TypeError("payload must be a StartCombatPayload")
