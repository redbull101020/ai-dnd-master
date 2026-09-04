from dataclasses import dataclass


@dataclass
class EquipmentState:
    owner_id: str
    equipped_weapon_id: str | None

    def __post_init__(self) -> None:
        if type(self.owner_id) is not str:
            raise TypeError("owner_id must be a str")
        if (
            self.equipped_weapon_id is not None
            and type(self.equipped_weapon_id) is not str
        ):
            raise TypeError("equipped_weapon_id must be a str or None")
