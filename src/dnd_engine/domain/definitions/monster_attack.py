import re
from dataclasses import dataclass

from dnd_engine.domain.dice import parse_ndm
from dnd_engine.domain.value_objects.damage_type import DamageType


# Local semantic identity scoped to the owning MonsterDefinition (§3.26),
# not a Definition ID and not a runtime `action_NNN` Instance ID (§4.13):
# this is a narrow field-level format rule, not a shared ID-format
# abstraction.
_LOCAL_ACTION_ID = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class MonsterAttackDefinition:
    action_id: str
    name: str
    attack_bonus: int
    damage_dice: str
    damage_modifier: int
    damage_type: DamageType

    def __post_init__(self) -> None:
        if type(self.action_id) is not str:
            raise TypeError("action_id must be a str")
        if _LOCAL_ACTION_ID.fullmatch(self.action_id) is None:
            raise ValueError(
                "action_id must be a lowercase snake_case local identifier "
                "matching ^[a-z][a-z0-9_]*$"
            )
        if type(self.name) is not str:
            raise TypeError("name must be a str")
        if type(self.attack_bonus) is not int:
            raise TypeError("attack_bonus must be an int")
        if type(self.damage_dice) is not str:
            raise TypeError("damage_dice must be a str")
        parse_ndm(self.damage_dice)
        if type(self.damage_modifier) is not int:
            raise TypeError("damage_modifier must be an int")
        if not isinstance(self.damage_type, DamageType):
            raise TypeError("damage_type must be a DamageType")
