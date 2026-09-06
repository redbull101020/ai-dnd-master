from dataclasses import dataclass

from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.state.combat import CombatState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.equipment import EquipmentState
from dnd_engine.domain.state.inventory import InventoryState


@dataclass(frozen=True)
class StateSnapshot:
    campaign: CampaignState
    creatures: tuple[CreatureState, ...]
    characters: tuple[CharacterState, ...] = ()
    inventories: tuple[InventoryState, ...] = ()
    equipment: tuple[EquipmentState, ...] = ()
    combat: CombatState | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.campaign, CampaignState):
            raise TypeError("campaign must be a CampaignState")
        if type(self.creatures) is not tuple:
            raise TypeError("creatures must be a tuple")
        if not all(isinstance(creature, CreatureState) for creature in self.creatures):
            raise TypeError("creatures must contain only CreatureState values")
        if type(self.characters) is not tuple:
            raise TypeError("characters must be a tuple")
        if not all(
            isinstance(character, CharacterState) for character in self.characters
        ):
            raise TypeError("characters must contain only CharacterState values")
        if type(self.inventories) is not tuple:
            raise TypeError("inventories must be a tuple")
        if not all(
            isinstance(inventory, InventoryState) for inventory in self.inventories
        ):
            raise TypeError("inventories must contain only InventoryState values")
        if type(self.equipment) is not tuple:
            raise TypeError("equipment must be a tuple")
        if not all(
            isinstance(equipment, EquipmentState) for equipment in self.equipment
        ):
            raise TypeError("equipment must contain only EquipmentState values")
        if self.combat is not None and not isinstance(self.combat, CombatState):
            raise TypeError("combat must be a CombatState or None")

        creature_ids = [creature.id for creature in self.creatures]
        if len(creature_ids) != len(set(creature_ids)):
            raise ValueError("creature IDs must be unique within a StateSnapshot")

        character_ids = [character.id for character in self.characters]
        if len(character_ids) != len(set(character_ids)):
            raise ValueError("character IDs must be unique within a StateSnapshot")
        if not set(character_ids).issubset(creature_ids):
            raise ValueError(
                "every CharacterState must have a corresponding CreatureState"
            )

        inventory_owner_ids = [
            inventory.owner_id for inventory in self.inventories
        ]
        if len(inventory_owner_ids) != len(set(inventory_owner_ids)):
            raise ValueError("at most one InventoryState is allowed per owner")
        if not set(inventory_owner_ids).issubset(character_ids):
            raise ValueError(
                "every InventoryState owner must have a corresponding CharacterState"
            )

        equipment_owner_ids = [
            equipment.owner_id for equipment in self.equipment
        ]
        if len(equipment_owner_ids) != len(set(equipment_owner_ids)):
            raise ValueError("at most one EquipmentState is allowed per owner")
        if not set(equipment_owner_ids).issubset(character_ids):
            raise ValueError(
                "every EquipmentState owner must have a corresponding CharacterState"
            )

        item_ids = [
            item.id for inventory in self.inventories for item in inventory.items
        ]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError(
                "InventoryItemState IDs must be unique within a StateSnapshot"
            )

        inventories_by_owner = {
            inventory.owner_id: inventory for inventory in self.inventories
        }
        for equipment in self.equipment:
            if equipment.equipped_weapon_id is None:
                continue
            owner_inventory = inventories_by_owner.get(equipment.owner_id)
            if owner_inventory is None or not any(
                item.id == equipment.equipped_weapon_id
                for item in owner_inventory.items
            ):
                raise ValueError(
                    "equipped_weapon_id must reference an item in the same owner's "
                    "InventoryState"
                )

        if self.combat is not None and not set(self.combat.order).issubset(
            creature_ids
        ):
            raise ValueError(
                "every CombatState participant must have a corresponding CreatureState"
            )
