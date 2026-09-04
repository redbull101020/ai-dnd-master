from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.state.combat import CombatState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.equipment import EquipmentState
from dnd_engine.domain.state.inventory import InventoryItemState, InventoryState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.ability_scores import AbilityScores


def campaign_state() -> CampaignState:
    return CampaignState(
        id="campaign_001",
        ruleset_id="dnd_5e",
        ruleset_version="5.1",
    )


def creature_state(creature_id: str) -> CreatureState:
    return CreatureState(
        id=creature_id,
        definition_id="goblin",
        ability_scores=AbilityScores(8, 14, 10, 10, 8, 8),
        current_hp=7,
        max_hp=7,
    )


def combat_state(*order: str, active_index: int = 0) -> CombatState:
    return CombatState(
        id="combat_001",
        round=1,
        order=order,
        active_index=active_index,
    )


def character_state(character_id: str) -> CharacterState:
    return CharacterState(
        id=character_id,
        total_level=5,
        saving_throw_proficiencies=frozenset(
            {Ability.STRENGTH, Ability.CONSTITUTION}
        ),
        skill_proficiencies=frozenset(),
        weapon_proficiencies=frozenset(),
    )


def inventory_item_state(
    item_id: str,
    definition_id: str = "dagger",
) -> InventoryItemState:
    return InventoryItemState(id=item_id, definition_id=definition_id)


def inventory_state(
    owner_id: str,
    *items: InventoryItemState,
) -> InventoryState:
    return InventoryState(owner_id=owner_id, items=items)


def equipment_state(
    owner_id: str,
    equipped_weapon_id: str | None,
) -> EquipmentState:
    return EquipmentState(
        owner_id=owner_id,
        equipped_weapon_id=equipped_weapon_id,
    )


def test_snapshot_accepts_campaign_and_zero_creatures() -> None:
    campaign = campaign_state()

    snapshot = StateSnapshot(campaign=campaign, creatures=())

    assert snapshot.campaign is campaign
    assert snapshot.creatures == ()
    assert snapshot.characters == ()
    assert snapshot.inventories == ()
    assert snapshot.equipment == ()


def test_snapshot_accepts_multiple_creatures_as_tuple() -> None:
    creatures = (creature_state("monster_002"), creature_state("monster_001"))

    snapshot = StateSnapshot(campaign=campaign_state(), creatures=creatures)

    assert snapshot.creatures is creatures
    assert type(snapshot.creatures) is tuple


def test_snapshot_rejects_non_tuple_creatures() -> None:
    with pytest.raises(TypeError):
        StateSnapshot(  # type: ignore[arg-type]
            campaign=campaign_state(),
            creatures=[creature_state("monster_001")],
        )


def test_snapshot_rejects_duplicate_creature_ids() -> None:
    with pytest.raises(ValueError):
        StateSnapshot(
            campaign=campaign_state(),
            creatures=(
                creature_state("monster_001"),
                creature_state("monster_001"),
            ),
        )


def test_snapshot_accepts_character_referencing_existing_creature() -> None:
    creature = creature_state("character_001")
    character = character_state("character_001")

    snapshot = StateSnapshot(
        campaign=campaign_state(),
        creatures=(creature,),
        characters=(character,),
    )

    assert snapshot.characters == (character,)


def test_snapshot_accepts_creature_without_character_state() -> None:
    snapshot = StateSnapshot(
        campaign=campaign_state(),
        creatures=(creature_state("monster_001"),),
        characters=(),
    )

    assert snapshot.characters == ()


def test_snapshot_rejects_non_tuple_characters() -> None:
    with pytest.raises(TypeError):
        StateSnapshot(  # type: ignore[arg-type]
            campaign=campaign_state(),
            creatures=(creature_state("character_001"),),
            characters=[character_state("character_001")],
        )


def test_snapshot_rejects_non_character_values() -> None:
    with pytest.raises(TypeError):
        StateSnapshot(  # type: ignore[arg-type]
            campaign=campaign_state(),
            creatures=(creature_state("character_001"),),
            characters=(creature_state("character_001"),),
        )


def test_snapshot_rejects_duplicate_character_ids() -> None:
    with pytest.raises(ValueError):
        StateSnapshot(
            campaign=campaign_state(),
            creatures=(creature_state("character_001"),),
            characters=(
                character_state("character_001"),
                character_state("character_001"),
            ),
        )


def test_snapshot_rejects_character_without_matching_creature() -> None:
    with pytest.raises(ValueError):
        StateSnapshot(
            campaign=campaign_state(),
            creatures=(creature_state("monster_001"),),
            characters=(character_state("character_001"),),
        )


def test_snapshot_is_a_frozen_grouping_not_a_state_owner() -> None:
    campaign = campaign_state()
    creature = creature_state("monster_001")
    snapshot = StateSnapshot(campaign=campaign, creatures=(creature,))

    with pytest.raises(FrozenInstanceError):
        snapshot.creatures = ()  # type: ignore[misc]

    campaign.ruleset_version = "5.2.2"
    creature.current_hp = 3

    assert snapshot.campaign is campaign
    assert snapshot.creatures[0] is creature
    assert tuple(field.name for field in fields(CampaignState)) == (
        "id",
        "ruleset_id",
        "ruleset_version",
    )


def test_snapshot_has_only_persistence_grouping_fields() -> None:
    assert tuple(field.name for field in fields(StateSnapshot)) == (
        "campaign",
        "creatures",
        "characters",
        "inventories",
        "equipment",
        "combat",
    )


def test_snapshot_accepts_authoritative_weapon_source_relations() -> None:
    character = character_state("character_001")
    item = inventory_item_state("item_001")
    inventory = inventory_state(character.id, item)
    equipment = equipment_state(character.id, item.id)

    snapshot = StateSnapshot(
        campaign=campaign_state(),
        creatures=(creature_state(character.id),),
        characters=(character,),
        inventories=(inventory,),
        equipment=(equipment,),
    )

    assert snapshot.inventories == (inventory,)
    assert snapshot.equipment == (equipment,)


def test_snapshot_accepts_absent_or_empty_weapon_source_projections() -> None:
    character = character_state("character_001")
    creature = creature_state(character.id)

    absent = StateSnapshot(
        campaign=campaign_state(),
        creatures=(creature,),
        characters=(character,),
    )
    empty_inventory = StateSnapshot(
        campaign=campaign_state(),
        creatures=(creature,),
        characters=(character,),
        inventories=(inventory_state(character.id),),
    )
    empty_equipment_without_inventory = StateSnapshot(
        campaign=campaign_state(),
        creatures=(creature,),
        characters=(character,),
        equipment=(equipment_state(character.id, None),),
    )

    assert absent.inventories == ()
    assert absent.equipment == ()
    assert empty_inventory.inventories[0].items == ()
    assert (
        empty_equipment_without_inventory.equipment[0].equipped_weapon_id
        is None
    )


@pytest.mark.parametrize("field_name", ["inventories", "equipment"])
def test_snapshot_rejects_non_tuple_weapon_source_projections(
    field_name: str,
) -> None:
    character = character_state("character_001")
    kwargs: dict[str, object] = {
        "campaign": campaign_state(),
        "creatures": (creature_state(character.id),),
        "characters": (character,),
        field_name: [],
    }

    with pytest.raises(TypeError):
        StateSnapshot(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("field_name", ["inventories", "equipment"])
def test_snapshot_rejects_wrong_weapon_source_projection_members(
    field_name: str,
) -> None:
    character = character_state("character_001")
    kwargs: dict[str, object] = {
        "campaign": campaign_state(),
        "creatures": (creature_state(character.id),),
        "characters": (character,),
        field_name: (object(),),
    }

    with pytest.raises(TypeError):
        StateSnapshot(**kwargs)  # type: ignore[arg-type]


def test_snapshot_rejects_inventory_owner_without_character() -> None:
    with pytest.raises(ValueError):
        StateSnapshot(
            campaign=campaign_state(),
            creatures=(creature_state("monster_001"),),
            inventories=(inventory_state("character_001"),),
        )


def test_snapshot_rejects_equipment_owner_without_character() -> None:
    with pytest.raises(ValueError):
        StateSnapshot(
            campaign=campaign_state(),
            creatures=(creature_state("monster_001"),),
            equipment=(equipment_state("character_001", None),),
        )


def test_snapshot_rejects_duplicate_inventory_owner() -> None:
    character = character_state("character_001")

    with pytest.raises(ValueError):
        StateSnapshot(
            campaign=campaign_state(),
            creatures=(creature_state(character.id),),
            characters=(character,),
            inventories=(
                inventory_state(character.id),
                inventory_state(character.id),
            ),
        )


def test_snapshot_rejects_duplicate_equipment_owner() -> None:
    character = character_state("character_001")

    with pytest.raises(ValueError):
        StateSnapshot(
            campaign=campaign_state(),
            creatures=(creature_state(character.id),),
            characters=(character,),
            equipment=(
                equipment_state(character.id, None),
                equipment_state(character.id, None),
            ),
        )


def test_snapshot_rejects_campaign_wide_duplicate_item_id() -> None:
    first_character = character_state("character_001")
    second_character = character_state("character_002")

    with pytest.raises(ValueError):
        StateSnapshot(
            campaign=campaign_state(),
            creatures=(
                creature_state(first_character.id),
                creature_state(second_character.id),
            ),
            characters=(first_character, second_character),
            inventories=(
                inventory_state(
                    first_character.id,
                    inventory_item_state("item_001"),
                ),
                inventory_state(
                    second_character.id,
                    inventory_item_state("item_001"),
                ),
            ),
        )


def test_snapshot_rejects_equipped_item_missing_from_owner_inventory() -> None:
    character = character_state("character_001")

    with pytest.raises(ValueError):
        StateSnapshot(
            campaign=campaign_state(),
            creatures=(creature_state(character.id),),
            characters=(character,),
            inventories=(inventory_state(character.id),),
            equipment=(equipment_state(character.id, "item_001"),),
        )


def test_snapshot_rejects_equipped_item_owned_by_another_character() -> None:
    first_character = character_state("character_001")
    second_character = character_state("character_002")

    with pytest.raises(ValueError):
        StateSnapshot(
            campaign=campaign_state(),
            creatures=(
                creature_state(first_character.id),
                creature_state(second_character.id),
            ),
            characters=(first_character, second_character),
            inventories=(
                inventory_state(first_character.id),
                inventory_state(
                    second_character.id,
                    inventory_item_state("item_001"),
                ),
            ),
            equipment=(equipment_state(first_character.id, "item_001"),),
        )


def test_snapshot_does_not_dereference_inventory_item_definition_id() -> None:
    character = character_state("character_001")
    item = inventory_item_state("item_001", definition_id="does_not_exist")

    snapshot = StateSnapshot(
        campaign=campaign_state(),
        creatures=(creature_state(character.id),),
        characters=(character,),
        inventories=(inventory_state(character.id, item),),
        equipment=(equipment_state(character.id, item.id),),
    )

    assert snapshot.inventories[0].items[0].definition_id == "does_not_exist"


def test_snapshot_defaults_to_no_combat() -> None:
    snapshot = StateSnapshot(
        campaign=campaign_state(),
        creatures=(creature_state("monster_001"),),
    )

    assert snapshot.combat is None


def test_snapshot_accepts_combat_referencing_existing_creatures() -> None:
    creature = creature_state("monster_001")
    combat = combat_state("monster_001")

    snapshot = StateSnapshot(
        campaign=campaign_state(),
        creatures=(creature,),
        combat=combat,
    )

    assert snapshot.combat is combat


def test_snapshot_rejects_non_combat_state_value() -> None:
    with pytest.raises(TypeError):
        StateSnapshot(  # type: ignore[arg-type]
            campaign=campaign_state(),
            creatures=(creature_state("monster_001"),),
            combat={"id": "combat_001"},
        )


def test_snapshot_rejects_combat_participant_without_matching_creature() -> None:
    with pytest.raises(ValueError):
        StateSnapshot(
            campaign=campaign_state(),
            creatures=(creature_state("monster_001"),),
            combat=combat_state("monster_002"),
        )
