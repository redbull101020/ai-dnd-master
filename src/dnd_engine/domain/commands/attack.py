from dataclasses import dataclass, field
from typing import Literal

from dnd_engine.domain.value_objects.ability import Ability


@dataclass(frozen=True)
class AttackPayload:
    target_id: str
    weapon_item_id: str | None = None
    weapon_ability: Ability | None = None

    def __post_init__(self) -> None:
        if type(self.target_id) is not str:
            raise TypeError("target_id must be a str")
        if self.weapon_item_id is not None and type(self.weapon_item_id) is not str:
            raise TypeError("weapon_item_id must be a str or None")
        if self.weapon_ability is not None and not isinstance(
            self.weapon_ability, Ability
        ):
            raise TypeError("weapon_ability must be an Ability or None")


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
