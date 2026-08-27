from dataclasses import dataclass

from dnd_engine.domain.definitions.item import ItemDefinition
from dnd_engine.domain.dice import parse_ndm
from dnd_engine.domain.value_objects.damage_type import DamageType


@dataclass(frozen=True)
class WeaponDefinition(ItemDefinition):
    damage_dice: str
    damage_type: DamageType
    properties: tuple[str, ...]

    def __post_init__(self) -> None:
        parse_ndm(self.damage_dice)
