from collections.abc import Callable
from copy import deepcopy

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
from dnd_engine.domain.value_objects.condition import Condition
from dnd_engine.domain.value_objects.skill import Skill
from dnd_engine.infrastructure.persistence.json import state_serializer
from dnd_engine.infrastructure.persistence.json.state_serializer import (
    StateSerializer,
)


CREATURE_DATA: dict[str, object] = {
    "id": "character_001",
    "definitionId": "fighter",
    "abilityScores": {
        "strength": 16,
        "dexterity": 12,
        "constitution": 14,
        "intelligence": 10,
        "wisdom": 10,
        "charisma": 8,
    },
    "currentHp": 28,
    "maxHp": 28,
}

V4_CREATURE_DATA: dict[str, object] = {**CREATURE_DATA, "conditions": []}

CANONICAL_V4_DATA: dict[str, object] = {
    "schemaVersion": 4,
    "campaignId": "campaign_001",
    "state": {
        "campaign": {
            "id": "campaign_001",
            "rulesetId": "dnd_5e",
            "rulesetVersion": "5.1",
        },
        "creatures": [V4_CREATURE_DATA],
        "characters": [
            {
                "id": "character_001",
                "totalLevel": 5,
                "savingThrowProficiencies": ["constitution", "strength"],
                "skillProficiencies": ["athletics", "perception"],
            }
        ],
    },
}

COMBAT_DATA: dict[str, object] = {
    "id": "combat_001",
    "round": 2,
    "order": ["monster_001", "character_001"],
    "activeIndex": 1,
}

# Legacy V4: current V1-V4 state shape, no top-level `combat` key.
LEGACY_V4_DATA: dict[str, object] = deepcopy(CANONICAL_V4_DATA)

# Legacy V5: pre-V6 state shape. Adds top-level `combat`, but predates
# `inventories`, `equipment`, and Character `weaponProficiencies`.
LEGACY_V5_DATA: dict[str, object] = {
    "schemaVersion": 5,
    "campaignId": "campaign_001",
    "state": {
        "campaign": {
            "id": "campaign_001",
            "rulesetId": "dnd_5e",
            "rulesetVersion": "5.1",
        },
        "creatures": [V4_CREATURE_DATA],
        "characters": [
            {
                "id": "character_001",
                "totalLevel": 5,
                "savingThrowProficiencies": ["constitution", "strength"],
                "skillProficiencies": ["athletics", "perception"],
            }
        ],
        "combat": None,
    },
}

INVENTORY_ITEM_DATA: dict[str, object] = {"id": "item_001", "definitionId": "dagger"}

INVENTORY_DATA: dict[str, object] = {
    "ownerId": "character_001",
    "items": [INVENTORY_ITEM_DATA],
}

EQUIPMENT_DATA: dict[str, object] = {
    "ownerId": "character_001",
    "equippedWeaponId": "item_001",
}

# Current V6: exact state shape emitted by the current writer. Adds
# top-level `inventories`/`equipment` and Character `weaponProficiencies`.
CANONICAL_V6_DATA: dict[str, object] = {
    "schemaVersion": 6,
    "campaignId": "campaign_001",
    "state": {
        "campaign": {
            "id": "campaign_001",
            "rulesetId": "dnd_5e",
            "rulesetVersion": "5.1",
        },
        "creatures": [V4_CREATURE_DATA],
        "characters": [
            {
                "id": "character_001",
                "totalLevel": 5,
                "savingThrowProficiencies": ["constitution", "strength"],
                "skillProficiencies": ["athletics", "perception"],
                "weaponProficiencies": [],
            }
        ],
        "inventories": [],
        "equipment": [],
        "combat": None,
    },
}

# Legacy V3: current V1-V3 Character schema, no Creature `conditions` field.
LEGACY_V3_DATA: dict[str, object] = deepcopy(CANONICAL_V4_DATA)
LEGACY_V3_DATA["schemaVersion"] = 3
LEGACY_V3_DATA["state"]["creatures"] = [deepcopy(CREATURE_DATA)]  # type: ignore[index]

LEGACY_V2_DATA: dict[str, object] = deepcopy(LEGACY_V3_DATA)
LEGACY_V2_DATA["schemaVersion"] = 2
del LEGACY_V2_DATA["state"]["characters"][0][  # type: ignore[index]
    "skillProficiencies"
]

LEGACY_V1_DATA: dict[str, object] = {
    "schemaVersion": 1,
    "campaignId": "campaign_001",
    "state": {
        "campaign": {
            "id": "campaign_001",
            "rulesetId": "dnd_5e",
            "rulesetVersion": "5.1",
        },
        "creatures": [deepcopy(CREATURE_DATA)],
    },
}


def campaign_state() -> CampaignState:
    return CampaignState("campaign_001", "dnd_5e", "5.1")


def creature_state(
    creature_id: str = "character_001",
    *,
    conditions: frozenset[Condition] = frozenset(),
) -> CreatureState:
    return CreatureState(
        id=creature_id,
        definition_id="fighter",
        ability_scores=AbilityScores(16, 12, 14, 10, 10, 8),
        current_hp=28,
        max_hp=28,
        conditions=conditions,
    )


def character_state(
    character_id: str = "character_001",
    *,
    weapon_proficiencies: frozenset[str] = frozenset(),
) -> CharacterState:
    return CharacterState(
        id=character_id,
        total_level=5,
        saving_throw_proficiencies=frozenset(
            {Ability.STRENGTH, Ability.CONSTITUTION}
        ),
        skill_proficiencies=frozenset(
            {Skill.ATHLETICS, Skill.PERCEPTION}
        ),
        weapon_proficiencies=weapon_proficiencies,
    )


def combat_state(
    *order: str,
    combat_id: str = "combat_001",
    round: int = 2,
    active_index: int = 1,
) -> CombatState:
    return CombatState(
        id=combat_id, round=round, order=order, active_index=active_index
    )


def inventory_item_state(
    item_id: str = "item_001",
    definition_id: str = "dagger",
) -> InventoryItemState:
    return InventoryItemState(id=item_id, definition_id=definition_id)


def inventory_state(
    owner_id: str = "character_001",
    *items: InventoryItemState,
) -> InventoryState:
    return InventoryState(owner_id=owner_id, items=tuple(items))


def equipment_state(
    owner_id: str = "character_001",
    equipped_weapon_id: str | None = None,
) -> EquipmentState:
    return EquipmentState(owner_id=owner_id, equipped_weapon_id=equipped_weapon_id)


def snapshot(
    *creatures: CreatureState,
    characters: tuple[CharacterState, ...] = (),
    inventories: tuple[InventoryState, ...] = (),
    equipment: tuple[EquipmentState, ...] = (),
    combat: CombatState | None = None,
) -> StateSnapshot:
    return StateSnapshot(
        campaign=campaign_state(),
        creatures=tuple(creatures),
        characters=characters,
        inventories=inventories,
        equipment=equipment,
        combat=combat,
    )


def v6_data() -> dict[str, object]:
    return deepcopy(CANONICAL_V6_DATA)


def v6_data_with_inventory_and_equipment() -> dict[str, object]:
    data = v6_data()
    nested(data, "state")["inventories"] = [deepcopy(INVENTORY_DATA)]  # type: ignore[index]
    nested(data, "state")["equipment"] = [deepcopy(EQUIPMENT_DATA)]  # type: ignore[index]
    return data


def two_character_v6_data() -> dict[str, object]:
    data = v6_data()
    state = nested(data, "state")
    creature_two = deepcopy(V4_CREATURE_DATA)
    creature_two["id"] = "character_002"
    state["creatures"].append(creature_two)  # type: ignore[index,union-attr]
    character_two = deepcopy(state["characters"][0])  # type: ignore[index]
    character_two["id"] = "character_002"  # type: ignore[index]
    state["characters"].append(character_two)  # type: ignore[index,union-attr]
    return data


def v5_data() -> dict[str, object]:
    return deepcopy(LEGACY_V5_DATA)


def v4_data() -> dict[str, object]:
    return deepcopy(LEGACY_V4_DATA)


def v3_data() -> dict[str, object]:
    return deepcopy(LEGACY_V3_DATA)


def v2_data() -> dict[str, object]:
    return deepcopy(LEGACY_V2_DATA)


def v1_data() -> dict[str, object]:
    return deepcopy(LEGACY_V1_DATA)


def nested(data: dict[str, object], *path: str | int) -> object:
    value: object = data
    for part in path:
        value = value[part]  # type: ignore[index]
    return value


# --- V6 writer: exact shape, ordering, and field sets -----------------------


def test_serialize_emits_exact_canonical_v6_mapping() -> None:
    serialized = StateSerializer.serialize(
        snapshot(creature_state(), characters=(character_state(),))
    )

    assert serialized == CANONICAL_V6_DATA
    assert serialized["schemaVersion"] == 6


def test_serialize_emits_empty_projections_in_v6() -> None:
    serialized = StateSerializer.serialize(snapshot())

    assert serialized == {
        "schemaVersion": 6,
        "campaignId": "campaign_001",
        "state": {
            "campaign": {
                "id": "campaign_001",
                "rulesetId": "dnd_5e",
                "rulesetVersion": "5.1",
            },
            "creatures": [],
            "characters": [],
            "inventories": [],
            "equipment": [],
            "combat": None,
        },
    }


def test_serialize_uses_exact_v6_state_and_nested_fields() -> None:
    serialized = StateSerializer.serialize(
        snapshot(
            creature_state(),
            characters=(character_state(),),
            inventories=(inventory_state("character_001", inventory_item_state()),),
            equipment=(equipment_state("character_001", "item_001"),),
        )
    )
    state = serialized["state"]  # type: ignore[assignment]
    creature = state["creatures"][0]  # type: ignore[index]
    character = state["characters"][0]  # type: ignore[index]
    inventory = state["inventories"][0]  # type: ignore[index]
    item = inventory["items"][0]  # type: ignore[index]
    equipment = state["equipment"][0]  # type: ignore[index]

    assert set(state) == {
        "campaign",
        "creatures",
        "characters",
        "inventories",
        "equipment",
        "combat",
    }
    assert set(creature) == {
        "id",
        "definitionId",
        "abilityScores",
        "currentHp",
        "maxHp",
        "conditions",
    }
    assert set(character) == {
        "id",
        "totalLevel",
        "savingThrowProficiencies",
        "skillProficiencies",
        "weaponProficiencies",
    }
    assert set(inventory) == {"ownerId", "items"}
    assert set(item) == {"id", "definitionId"}
    assert set(equipment) == {"ownerId", "equippedWeaponId"}


def test_serialize_emits_exact_combat_fields() -> None:
    serialized = StateSerializer.serialize(
        snapshot(
            creature_state("character_001"),
            creature_state("monster_001"),
            combat=combat_state("monster_001", "character_001"),
        )
    )

    assert serialized["state"]["combat"] == {  # type: ignore[index]
        "id": "combat_001",
        "round": 2,
        "order": ["monster_001", "character_001"],
        "activeIndex": 1,
    }


def test_serialize_orders_creatures_characters_and_proficiencies() -> None:
    first = character_state("character_001")
    first.saving_throw_proficiencies = frozenset(
        {Ability.WISDOM, Ability.DEXTERITY, Ability.CHARISMA}
    )
    first.skill_proficiencies = frozenset(
        {Skill.STEALTH, Skill.ACROBATICS, Skill.PERCEPTION}
    )
    serialized = StateSerializer.serialize(
        snapshot(
            creature_state("character_002"),
            creature_state("character_001"),
            characters=(character_state("character_002"), first),
        )
    )
    state = serialized["state"]  # type: ignore[assignment]

    assert [entry["id"] for entry in state["creatures"]] == [  # type: ignore[index]
        "character_001",
        "character_002",
    ]
    assert [entry["id"] for entry in state["characters"]] == [  # type: ignore[index]
        "character_001",
        "character_002",
    ]
    assert state["characters"][0]["savingThrowProficiencies"] == [  # type: ignore[index]
        "charisma",
        "dexterity",
        "wisdom",
    ]
    assert state["characters"][0]["skillProficiencies"] == [  # type: ignore[index]
        "acrobatics",
        "perception",
        "stealth",
    ]


def test_serialize_orders_conditions_by_value() -> None:
    serialized = StateSerializer.serialize(
        snapshot(creature_state(conditions=frozenset({Condition.POISONED})))
    )

    assert serialized["state"]["creatures"][0]["conditions"] == [  # type: ignore[index]
        "poisoned"
    ]


def test_serialize_orders_weapon_proficiencies_lexicographically() -> None:
    character = character_state(
        weapon_proficiencies=frozenset({"shortsword", "dagger", "longsword"})
    )

    serialized = StateSerializer.serialize(
        snapshot(creature_state(), characters=(character,))
    )

    assert serialized["state"]["characters"][0]["weaponProficiencies"] == [  # type: ignore[index]
        "dagger",
        "longsword",
        "shortsword",
    ]


def test_serialize_orders_inventories_by_owner_id() -> None:
    serialized = StateSerializer.serialize(
        snapshot(
            creature_state("character_001"),
            creature_state("character_002"),
            characters=(
                character_state("character_001"),
                character_state("character_002"),
            ),
            inventories=(
                inventory_state("character_002"),
                inventory_state("character_001"),
            ),
        )
    )

    assert [
        entry["ownerId"] for entry in serialized["state"]["inventories"]  # type: ignore[index]
    ] == ["character_001", "character_002"]


def test_serialize_orders_inventory_items_by_id() -> None:
    serialized = StateSerializer.serialize(
        snapshot(
            creature_state(),
            characters=(character_state(),),
            inventories=(
                inventory_state(
                    "character_001",
                    inventory_item_state("item_002", "longsword"),
                    inventory_item_state("item_001", "dagger"),
                ),
            ),
        )
    )

    assert [
        item["id"]
        for item in serialized["state"]["inventories"][0]["items"]  # type: ignore[index]
    ] == ["item_001", "item_002"]


def test_serialize_orders_equipment_by_owner_id() -> None:
    serialized = StateSerializer.serialize(
        snapshot(
            creature_state("character_001"),
            creature_state("character_002"),
            characters=(
                character_state("character_001"),
                character_state("character_002"),
            ),
            equipment=(
                equipment_state("character_002"),
                equipment_state("character_001"),
            ),
        )
    )

    assert [
        entry["ownerId"] for entry in serialized["state"]["equipment"]  # type: ignore[index]
    ] == ["character_001", "character_002"]


def test_serialize_emits_exact_inventory_and_equipment_values() -> None:
    serialized = StateSerializer.serialize(
        snapshot(
            creature_state(),
            characters=(character_state(),),
            inventories=(
                inventory_state(
                    "character_001", inventory_item_state("item_001", "dagger")
                ),
            ),
            equipment=(equipment_state("character_001", "item_001"),),
        )
    )

    assert serialized["state"]["inventories"] == [  # type: ignore[index]
        {
            "ownerId": "character_001",
            "items": [{"id": "item_001", "definitionId": "dagger"}],
        }
    ]
    assert serialized["state"]["equipment"] == [  # type: ignore[index]
        {"ownerId": "character_001", "equippedWeaponId": "item_001"}
    ]


def test_serialize_emits_null_equipped_weapon_id() -> None:
    serialized = StateSerializer.serialize(
        snapshot(
            creature_state(),
            characters=(character_state(),),
            equipment=(equipment_state("character_001", None),),
        )
    )

    assert (
        serialized["state"]["equipment"][0]["equippedWeaponId"]  # type: ignore[index]
        is None
    )


def test_v6_round_trip_reconstructs_equivalent_current_snapshot() -> None:
    original = snapshot(
        creature_state(conditions=frozenset({Condition.POISONED})),
        characters=(character_state(),),
    )

    reconstructed = StateSerializer.deserialize(StateSerializer.serialize(original))

    assert reconstructed == original


def test_v6_round_trip_with_empty_conditions() -> None:
    original = snapshot(creature_state())

    reconstructed = StateSerializer.deserialize(StateSerializer.serialize(original))

    assert reconstructed == original
    assert reconstructed.creatures[0].conditions == frozenset()


def test_v6_round_trip_with_poisoned_condition() -> None:
    original = snapshot(creature_state(conditions=frozenset({Condition.POISONED})))

    reconstructed = StateSerializer.deserialize(StateSerializer.serialize(original))

    assert reconstructed == original
    assert reconstructed.creatures[0].conditions == frozenset({Condition.POISONED})


def test_v6_round_trip_with_combat() -> None:
    original = snapshot(
        creature_state("character_001"),
        creature_state("monster_001"),
        combat=combat_state("monster_001", "character_001"),
    )

    reconstructed = StateSerializer.deserialize(StateSerializer.serialize(original))

    assert reconstructed == original
    assert reconstructed.combat == combat_state("monster_001", "character_001")


def test_v6_round_trip_without_combat() -> None:
    original = snapshot(creature_state())

    reconstructed = StateSerializer.deserialize(StateSerializer.serialize(original))

    assert reconstructed.combat is None


def test_v6_round_trip_with_weapon_proficiencies() -> None:
    original = snapshot(
        creature_state(),
        characters=(
            character_state(weapon_proficiencies=frozenset({"dagger", "shortsword"})),
        ),
    )

    reconstructed = StateSerializer.deserialize(StateSerializer.serialize(original))

    assert reconstructed == original
    assert reconstructed.characters[0].weapon_proficiencies == frozenset(
        {"dagger", "shortsword"}
    )


def test_v6_round_trip_with_inventory_and_equipment() -> None:
    original = snapshot(
        creature_state(),
        characters=(character_state(),),
        inventories=(inventory_state("character_001", inventory_item_state()),),
        equipment=(equipment_state("character_001", "item_001"),),
    )

    reconstructed = StateSerializer.deserialize(StateSerializer.serialize(original))

    assert reconstructed == original
    assert reconstructed.inventories == (
        InventoryState(
            owner_id="character_001",
            items=(InventoryItemState(id="item_001", definition_id="dagger"),),
        ),
    )
    assert reconstructed.equipment == (
        EquipmentState(owner_id="character_001", equipped_weapon_id="item_001"),
    )


def test_serialize_emits_empty_skill_membership_as_array() -> None:
    character = character_state()
    character.skill_proficiencies = frozenset()

    serialized = StateSerializer.serialize(
        snapshot(creature_state(), characters=(character,))
    )

    assert serialized["state"]["characters"][0][  # type: ignore[index]
        "skillProficiencies"
    ] == []


def test_deserialize_accepts_legacy_v2_with_empty_skill_membership() -> None:
    reconstructed = StateSerializer.deserialize(v2_data())

    assert reconstructed.characters[0].skill_proficiencies == frozenset()
    assert reconstructed.creatures[0].conditions == frozenset()


@pytest.mark.parametrize("data_factory", [v2_data, v3_data, v4_data, v5_data])
def test_v2_to_v5_deserialize_migrates_empty_weapon_source_state(
    data_factory: Callable[[], dict[str, object]],
) -> None:
    reconstructed = StateSerializer.deserialize(data_factory())

    assert reconstructed.characters[0].weapon_proficiencies == frozenset()
    assert reconstructed.inventories == ()
    assert reconstructed.equipment == ()


def test_deserialize_v3_restores_skill_membership_and_empty_conditions() -> None:
    """Critical migration gate: a realistic V3 payload with non-empty
    skillProficiencies must still decode correctly under the V4 implementation,
    and must not invent any Condition membership."""
    reconstructed = StateSerializer.deserialize(v3_data())

    assert reconstructed.characters[0].skill_proficiencies == frozenset(
        {Skill.ATHLETICS, Skill.PERCEPTION}
    )
    assert reconstructed.creatures[0].conditions == frozenset()


def test_legacy_v2_reserializes_as_current_v6() -> None:
    serialized = StateSerializer.serialize(StateSerializer.deserialize(v2_data()))

    assert serialized["schemaVersion"] == 6
    assert serialized["state"]["characters"][0][  # type: ignore[index]
        "skillProficiencies"
    ] == []
    assert serialized["state"]["characters"][0][  # type: ignore[index]
        "weaponProficiencies"
    ] == []
    assert serialized["state"]["creatures"][0]["conditions"] == []  # type: ignore[index]
    assert serialized["state"]["inventories"] == []  # type: ignore[index]
    assert serialized["state"]["equipment"] == []  # type: ignore[index]
    assert serialized["state"]["combat"] is None  # type: ignore[index]


def test_legacy_v3_reserializes_as_current_v6() -> None:
    serialized = StateSerializer.serialize(StateSerializer.deserialize(v3_data()))

    assert serialized["schemaVersion"] == 6
    assert serialized["state"]["characters"][0][  # type: ignore[index]
        "skillProficiencies"
    ] == ["athletics", "perception"]
    assert serialized["state"]["characters"][0][  # type: ignore[index]
        "weaponProficiencies"
    ] == []
    assert serialized["state"]["creatures"][0]["conditions"] == []  # type: ignore[index]
    assert serialized["state"]["inventories"] == []  # type: ignore[index]
    assert serialized["state"]["equipment"] == []  # type: ignore[index]
    assert serialized["state"]["combat"] is None  # type: ignore[index]


def test_legacy_v4_reserializes_as_current_v6() -> None:
    serialized = StateSerializer.serialize(StateSerializer.deserialize(v4_data()))

    assert serialized["schemaVersion"] == 6
    assert serialized["state"]["characters"][0][  # type: ignore[index]
        "skillProficiencies"
    ] == ["athletics", "perception"]
    assert serialized["state"]["characters"][0][  # type: ignore[index]
        "weaponProficiencies"
    ] == []
    assert serialized["state"]["creatures"][0]["conditions"] == []  # type: ignore[index]
    assert serialized["state"]["inventories"] == []  # type: ignore[index]
    assert serialized["state"]["equipment"] == []  # type: ignore[index]
    assert serialized["state"]["combat"] is None  # type: ignore[index]


def test_legacy_v5_reserializes_as_current_v6() -> None:
    serialized = StateSerializer.serialize(StateSerializer.deserialize(v5_data()))

    assert serialized["schemaVersion"] == 6
    assert serialized["state"]["characters"][0][  # type: ignore[index]
        "weaponProficiencies"
    ] == []
    assert serialized["state"]["inventories"] == []  # type: ignore[index]
    assert serialized["state"]["equipment"] == []  # type: ignore[index]
    assert serialized["state"]["combat"] is None  # type: ignore[index]


def test_legacy_v1_reserializes_as_current_v6() -> None:
    reconstructed = StateSerializer.deserialize(v1_data())

    serialized = StateSerializer.serialize(reconstructed)

    assert serialized["schemaVersion"] == 6
    assert serialized["state"]["characters"] == []  # type: ignore[index]
    assert serialized["state"]["creatures"][0]["conditions"] == []  # type: ignore[index]
    assert serialized["state"]["inventories"] == []  # type: ignore[index]
    assert serialized["state"]["equipment"] == []  # type: ignore[index]
    assert serialized["state"]["combat"] is None  # type: ignore[index]


def test_deserialize_v4_legacy_produces_no_combat() -> None:
    """G7 regression: a real, on-disk legacy V4 snapshot (predating the
    state-level `combat` field) must still load with `combat=None`, not just
    through the isolated legacy-read tests above."""
    reconstructed = StateSerializer.deserialize(v4_data())

    assert reconstructed.combat is None


def test_deserialize_accepts_exact_legacy_v1_without_inventing_character_state() -> None:
    reconstructed = StateSerializer.deserialize(v1_data())

    assert reconstructed.campaign == campaign_state()
    assert reconstructed.creatures == (creature_state(),)
    assert reconstructed.characters == ()
    assert reconstructed.inventories == ()
    assert reconstructed.equipment == ()
    assert reconstructed.creatures[0].conditions == frozenset()


def test_deserialize_rejects_characters_field_in_legacy_v1() -> None:
    data = v1_data()
    nested(data, "state")["characters"] = []  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_legacy_v2_rejects_v3_skill_field() -> None:
    data = v2_data()
    character = nested(data, "state", "characters", 0)
    character["skillProficiencies"] = []  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_legacy_v3_rejects_conditions_field() -> None:
    """Legacy V3 predates the Creature `conditions` field: even an empty
    list is an unknown field under the strict V3 Creature schema."""
    data = v3_data()
    creature = nested(data, "state", "creatures", 0)
    creature["conditions"] = []  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_legacy_v5_rejects_v6_only_character_field() -> None:
    """Legacy V5 predates `weaponProficiencies`: old Character shapes are
    not retroactively widened to accept it, even as an empty list."""
    data = v5_data()
    nested(data, "state", "characters", 0)["weaponProficiencies"] = []  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_legacy_v5_rejects_v6_only_state_fields() -> None:
    """Legacy V5 predates the state-level `inventories`/`equipment` keys."""
    data = v5_data()
    nested(data, "state")["inventories"] = []  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


@pytest.mark.parametrize(
    ("path", "field"),
    [
        ((), "revision"),
        (("state",), "world"),
        (("state", "campaign"), "metadata"),
        (("state", "creatures", 0), "conditions"),
        (("state", "creatures", 0, "abilityScores"), "luck"),
        (("state", "characters", 0), "classLevels"),
    ],
)
def test_v3_deserialize_rejects_unknown_fields(
    path: tuple[str | int, ...],
    field: str,
) -> None:
    data = v3_data()
    nested(data, *path)[field] = "unexpected"  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


@pytest.mark.parametrize(
    ("path", "field"),
    [
        ((), "revision"),
        (("state",), "world"),
        (("state", "campaign"), "metadata"),
        (("state", "creatures", 0), "effects"),
        (("state", "creatures", 0, "abilityScores"), "luck"),
        (("state", "characters", 0), "classLevels"),
    ],
)
def test_v4_deserialize_rejects_unknown_fields(
    path: tuple[str | int, ...],
    field: str,
) -> None:
    data = v4_data()
    nested(data, *path)[field] = "unexpected"  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


@pytest.mark.parametrize(
    ("path", "field"),
    [
        (("state",), "characters"),
        (("state",), "creatures"),
        (("state", "campaign"), "rulesetVersion"),
        (("state", "creatures", 0), "definitionId"),
        (("state", "creatures", 0, "abilityScores"), "wisdom"),
        (("state", "characters", 0), "id"),
        (("state", "characters", 0), "totalLevel"),
        (("state", "characters", 0), "savingThrowProficiencies"),
        (("state", "characters", 0), "skillProficiencies"),
    ],
)
def test_v3_deserialize_rejects_missing_required_fields(
    path: tuple[str | int, ...],
    field: str,
) -> None:
    data = v3_data()
    del nested(data, *path)[field]  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


@pytest.mark.parametrize(
    ("path", "field"),
    [
        (("state",), "characters"),
        (("state",), "creatures"),
        (("state", "campaign"), "rulesetVersion"),
        (("state", "creatures", 0), "definitionId"),
        (("state", "creatures", 0), "conditions"),
        (("state", "creatures", 0, "abilityScores"), "wisdom"),
        (("state", "characters", 0), "id"),
        (("state", "characters", 0), "totalLevel"),
        (("state", "characters", 0), "savingThrowProficiencies"),
        (("state", "characters", 0), "skillProficiencies"),
    ],
)
def test_v4_deserialize_rejects_missing_required_fields(
    path: tuple[str | int, ...],
    field: str,
) -> None:
    data = v4_data()
    del nested(data, *path)[field]  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("campaignId",), None),
        (("state", "creatures"), ()),
        (("state", "creatures", 0, "id"), 1),
        (("state", "creatures", 0, "currentHp"), 28.0),
        (("state", "characters"), ()),
        (("state", "characters", 0, "id"), 1),
        (("state", "characters", 0, "totalLevel"), True),
        (("state", "characters", 0, "totalLevel"), 5.0),
        (("state", "characters", 0, "totalLevel"), "5"),
        (("state", "characters", 0, "savingThrowProficiencies"), ()),
        (("state", "characters", 0, "savingThrowProficiencies", 0), 1),
        (("state", "characters", 0, "skillProficiencies"), ()),
        (("state", "characters", 0, "skillProficiencies", 0), 1),
    ],
)
def test_v3_deserialize_rejects_wrong_types_without_coercion(
    path: tuple[str | int, ...],
    value: object,
) -> None:
    data = v3_data()
    parent = nested(data, *path[:-1])
    parent[path[-1]] = value  # type: ignore[index]

    with pytest.raises(TypeError):
        StateSerializer.deserialize(data)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("campaignId",), None),
        (("state", "creatures"), ()),
        (("state", "creatures", 0, "id"), 1),
        (("state", "creatures", 0, "currentHp"), 28.0),
        (("state", "creatures", 0, "conditions"), "poisoned"),
        (("state", "creatures", 0, "conditions"), {}),
        (("state", "creatures", 0, "conditions"), None),
        (("state", "characters"), ()),
        (("state", "characters", 0, "id"), 1),
        (("state", "characters", 0, "totalLevel"), True),
        (("state", "characters", 0, "totalLevel"), 5.0),
        (("state", "characters", 0, "totalLevel"), "5"),
        (("state", "characters", 0, "savingThrowProficiencies"), ()),
        (("state", "characters", 0, "savingThrowProficiencies", 0), 1),
        (("state", "characters", 0, "skillProficiencies"), ()),
        (("state", "characters", 0, "skillProficiencies", 0), 1),
    ],
)
def test_v4_deserialize_rejects_wrong_types_without_coercion(
    path: tuple[str | int, ...],
    value: object,
) -> None:
    data = v4_data()
    parent = nested(data, *path[:-1])
    parent[path[-1]] = value  # type: ignore[index]

    with pytest.raises(TypeError):
        StateSerializer.deserialize(data)


def test_v4_deserialize_rejects_non_string_condition_entry() -> None:
    data = v4_data()
    nested(data, "state", "creatures", 0)["conditions"] = [1]  # type: ignore[index]

    with pytest.raises(TypeError):
        StateSerializer.deserialize(data)


def test_v4_deserialize_rejects_unknown_condition_value() -> None:
    data = v4_data()
    nested(data, "state", "creatures", 0)["conditions"] = [  # type: ignore[index]
        "blinded"
    ]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v4_deserialize_rejects_duplicate_condition_values() -> None:
    data = v4_data()
    nested(data, "state", "creatures", 0)["conditions"] = [  # type: ignore[index]
        "poisoned",
        "poisoned",
    ]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v4_deserialize_accepts_poisoned_condition() -> None:
    data = v4_data()
    nested(data, "state", "creatures", 0)["conditions"] = [  # type: ignore[index]
        "poisoned"
    ]

    reconstructed = StateSerializer.deserialize(data)

    assert reconstructed.creatures[0].conditions == frozenset({Condition.POISONED})


def test_v4_creature_shape_is_fixed_and_survives_future_schema_version_bump(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: V4 Creature field/`conditions` decoding must be keyed to
    the fixed `SCHEMA_V4_VERSION` identity, not the mutable current-writer
    `SCHEMA_VERSION`. The V5 and V6 bumps (adding top-level `combat`, then
    `inventories`/`equipment`/`weaponProficiencies`) already happened for
    real; this simulates the *next* hypothetical schema bump
    (`SCHEMA_VERSION = 7`) and asserts a historical, already-persisted V4
    snapshot with `conditions` still decodes exactly as V4 -- it must not be
    silently misread against the pre-V4 Creature field set."""
    monkeypatch.setattr(state_serializer, "SCHEMA_VERSION", 7)
    data = v4_data()
    nested(data, "state", "creatures", 0)["conditions"] = [  # type: ignore[index]
        "poisoned"
    ]

    reconstructed = StateSerializer.deserialize(data)

    assert reconstructed.creatures[0].conditions == frozenset({Condition.POISONED})
    assert reconstructed.characters[0].skill_proficiencies == frozenset(
        {Skill.ATHLETICS, Skill.PERCEPTION}
    )
    assert reconstructed.combat is None


def test_v5_state_shape_is_fixed_and_survives_future_schema_version_bump(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same regression as above for the V5 state-level `combat` addition:
    historical V5 semantics must be keyed to the fixed `SCHEMA_V5_VERSION`
    identity, not the mutable current-writer `SCHEMA_VERSION`. This simulates
    the *next* hypothetical schema bump beyond the real V6 (`SCHEMA_VERSION =
    7`)."""
    monkeypatch.setattr(state_serializer, "SCHEMA_VERSION", 7)
    data = v5_data()
    nested(data, "state")["combat"] = {  # type: ignore[index]
        "id": "combat_001",
        "round": 1,
        "order": ["character_001"],
        "activeIndex": 0,
    }

    reconstructed = StateSerializer.deserialize(data)

    assert reconstructed.combat == combat_state(
        "character_001", round=1, active_index=0
    )


def test_v6_state_shape_is_fixed_and_survives_future_schema_version_bump(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same regression as above for the V6 weapon-source additions:
    historical V6 semantics must be keyed to the fixed `SCHEMA_V6_VERSION`
    identity, not the mutable current-writer `SCHEMA_VERSION`. This simulates
    the *next* hypothetical schema bump (`SCHEMA_VERSION = 7`) and asserts a
    historical, already-persisted V6 snapshot with real inventory, equipment,
    and weapon-proficiency content still decodes exactly as V6."""
    monkeypatch.setattr(state_serializer, "SCHEMA_VERSION", 7)
    data = v6_data()
    nested(data, "state", "characters", 0)["weaponProficiencies"] = [  # type: ignore[index]
        "dagger"
    ]
    nested(data, "state")["inventories"] = [deepcopy(INVENTORY_DATA)]  # type: ignore[index]
    nested(data, "state")["equipment"] = [deepcopy(EQUIPMENT_DATA)]  # type: ignore[index]

    reconstructed = StateSerializer.deserialize(data)

    assert reconstructed.characters[0].weapon_proficiencies == frozenset({"dagger"})
    assert reconstructed.inventories == (
        InventoryState(
            owner_id="character_001",
            items=(InventoryItemState(id="item_001", definition_id="dagger"),),
        ),
    )
    assert reconstructed.equipment == (
        EquipmentState(owner_id="character_001", equipped_weapon_id="item_001"),
    )


@pytest.mark.parametrize("total_level", [0, 21])
def test_v3_deserialize_rejects_out_of_range_total_level(total_level: int) -> None:
    data = v3_data()
    nested(data, "state", "characters", 0)["totalLevel"] = total_level  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v3_deserialize_rejects_invalid_ability_value() -> None:
    data = v3_data()
    nested(data, "state", "characters", 0)["savingThrowProficiencies"] = [  # type: ignore[index]
        "STR"
    ]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v3_deserialize_rejects_duplicate_serialized_proficiencies() -> None:
    data = v3_data()
    nested(data, "state", "characters", 0)["savingThrowProficiencies"] = [  # type: ignore[index]
        "strength",
        "strength",
    ]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v3_deserialize_rejects_invalid_skill_value() -> None:
    data = v3_data()
    nested(data, "state", "characters", 0)["skillProficiencies"] = [  # type: ignore[index]
        "acrobatics_check"
    ]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v3_deserialize_rejects_duplicate_skill_proficiencies() -> None:
    data = v3_data()
    nested(data, "state", "characters", 0)["skillProficiencies"] = [  # type: ignore[index]
        "stealth",
        "stealth",
    ]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v4_deserialize_rejects_duplicate_character_ids() -> None:
    data = v4_data()
    characters = nested(data, "state", "characters")
    characters.append(deepcopy(characters[0]))  # type: ignore[attr-defined,index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v4_deserialize_rejects_character_without_corresponding_creature() -> None:
    data = v4_data()
    nested(data, "state", "characters", 0)["id"] = "character_002"  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_deserialize_rejects_campaign_id_mismatch() -> None:
    data = v4_data()
    data["campaignId"] = "campaign_002"

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_deserialize_rejects_missing_schema_version() -> None:
    data = v4_data()
    del data["schemaVersion"]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


@pytest.mark.parametrize("missing_field", ["campaignId", "state"])
def test_deserialize_rejects_other_missing_root_fields(
    missing_field: str,
) -> None:
    data = v4_data()
    del data[missing_field]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_deserialize_rejects_duplicate_creature_ids() -> None:
    data = v4_data()
    creatures = nested(data, "state", "creatures")
    creatures.append(deepcopy(creatures[0]))  # type: ignore[attr-defined,index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


@pytest.mark.parametrize("score", [0, 31])
def test_deserialize_rejects_invalid_ability_scores(score: int) -> None:
    data = v4_data()
    nested(data, "state", "creatures", 0, "abilityScores")["strength"] = score  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


@pytest.mark.parametrize(
    ("current_hp", "max_hp"),
    [(-1, 28), (29, 28), (0, 0)],
)
def test_deserialize_rejects_invalid_hp(current_hp: int, max_hp: int) -> None:
    data = v4_data()
    creature = nested(data, "state", "creatures", 0)
    creature["currentHp"] = current_hp  # type: ignore[index]
    creature["maxHp"] = max_hp  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


@pytest.mark.parametrize("schema_version", [0, 7, -1])
def test_deserialize_rejects_unsupported_schema_version(
    schema_version: int,
) -> None:
    data = v4_data()
    data["schemaVersion"] = schema_version

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_deserialize_rejects_bool_schema_version() -> None:
    data = v4_data()
    data["schemaVersion"] = True

    with pytest.raises(TypeError):
        StateSerializer.deserialize(data)


def test_legacy_v1_remains_strict_for_unknown_and_missing_fields() -> None:
    unknown = v1_data()
    nested(unknown, "state")["world"] = {}  # type: ignore[index]
    missing = v1_data()
    del nested(missing, "state")["creatures"]  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(unknown)
    with pytest.raises(ValueError):
        StateSerializer.deserialize(missing)


def test_serialize_rejects_mutated_invalid_character_state() -> None:
    character = character_state()
    character.total_level = 21

    with pytest.raises(ValueError):
        StateSerializer.serialize(
            snapshot(creature_state(), characters=(character,))
        )


def test_serialize_rejects_mutated_invalid_skill_membership() -> None:
    character = character_state()
    character.skill_proficiencies = frozenset(  # type: ignore[arg-type]
        {"athletics"}
    )

    with pytest.raises(TypeError):
        StateSerializer.serialize(
            snapshot(creature_state(), characters=(character,))
        )


def test_serialize_rejects_mutated_invalid_weapon_proficiency_membership() -> None:
    character = character_state()
    character.weapon_proficiencies = frozenset({1})  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        StateSerializer.serialize(
            snapshot(creature_state(), characters=(character,))
        )


def test_serialize_rejects_mutated_invalid_creature_state() -> None:
    creature = creature_state()
    creature.current_hp = 29

    with pytest.raises(ValueError):
        StateSerializer.serialize(snapshot(creature))


def test_serialize_rejects_mutated_invalid_creature_conditions() -> None:
    creature = creature_state()
    creature.conditions = {"poisoned"}  # type: ignore[assignment]

    with pytest.raises(TypeError):
        StateSerializer.serialize(snapshot(creature))


def test_serialize_rejects_mutated_invalid_inventory_item_state() -> None:
    item = inventory_item_state()
    item.id = 1  # type: ignore[assignment]
    inventory = inventory_state("character_001", item)

    with pytest.raises(TypeError):
        StateSerializer.serialize(
            snapshot(
                creature_state(),
                characters=(character_state(),),
                inventories=(inventory,),
            )
        )


class _StrLike(str):
    """A `str` subclass used only to prove the writer rejects non-exact str
    types (no subclass coercion) even when set/subset equality lets the
    mutated value slip past StateSnapshot's cross-object relation checks."""


def test_serialize_rejects_mutated_invalid_equipment_owner_id_type() -> None:
    equipment = equipment_state("character_001")
    equipment.owner_id = _StrLike("character_001")  # type: ignore[assignment]

    with pytest.raises(TypeError):
        StateSerializer.serialize(
            snapshot(
                creature_state(),
                characters=(character_state(),),
                equipment=(equipment,),
            )
        )


# --- V6 writer: cross-snapshot weapon-source relation regressions ----------
#
# `StateSnapshot.__post_init__` checks these relations, but only once, at
# construction. Its nested Inventory/Equipment dataclasses are mutable, so
# each test below builds a *valid* StateSnapshot first and then mutates a
# nested State object in place -- proving the writer independently re-checks
# these relations using the current values before ever emitting V6.


def test_serialize_rejects_inventory_owner_mutated_to_nonexistent_character() -> None:
    inventory = inventory_state("character_001")
    original = snapshot(
        creature_state(),
        characters=(character_state(),),
        inventories=(inventory,),
    )

    inventory.owner_id = "character_999"

    with pytest.raises(ValueError):
        StateSerializer.serialize(original)


def test_serialize_rejects_equipment_owner_mutated_to_nonexistent_character() -> None:
    equipment = equipment_state("character_001")
    original = snapshot(
        creature_state(),
        characters=(character_state(),),
        equipment=(equipment,),
    )

    equipment.owner_id = "character_999"

    with pytest.raises(ValueError):
        StateSerializer.serialize(original)


def test_serialize_rejects_inventories_mutated_to_share_owner() -> None:
    inventory_one = inventory_state("character_001")
    inventory_two = inventory_state("character_002")
    original = snapshot(
        creature_state("character_001"),
        creature_state("character_002"),
        characters=(
            character_state("character_001"),
            character_state("character_002"),
        ),
        inventories=(inventory_one, inventory_two),
    )

    inventory_two.owner_id = "character_001"

    with pytest.raises(ValueError):
        StateSerializer.serialize(original)


def test_serialize_rejects_equipment_entries_mutated_to_share_owner() -> None:
    equipment_one = equipment_state("character_001")
    equipment_two = equipment_state("character_002")
    original = snapshot(
        creature_state("character_001"),
        creature_state("character_002"),
        characters=(
            character_state("character_001"),
            character_state("character_002"),
        ),
        equipment=(equipment_one, equipment_two),
    )

    equipment_two.owner_id = "character_001"

    with pytest.raises(ValueError):
        StateSerializer.serialize(original)


def test_serialize_rejects_inventory_items_mutated_to_share_id() -> None:
    item_one = inventory_item_state("item_001", "dagger")
    item_two = inventory_item_state("item_002", "shortsword")
    inventory = inventory_state("character_001", item_one, item_two)
    original = snapshot(
        creature_state(),
        characters=(character_state(),),
        inventories=(inventory,),
    )

    item_two.id = "item_001"

    with pytest.raises(ValueError):
        StateSerializer.serialize(original)


def test_serialize_rejects_equipped_weapon_id_mutated_to_missing_item() -> None:
    item = inventory_item_state("item_001", "dagger")
    inventory = inventory_state("character_001", item)
    equipment = equipment_state("character_001", "item_001")
    original = snapshot(
        creature_state(),
        characters=(character_state(),),
        inventories=(inventory,),
        equipment=(equipment,),
    )

    equipment.equipped_weapon_id = "item_999"

    with pytest.raises(ValueError):
        StateSerializer.serialize(original)


def test_serialize_rejects_equipped_weapon_id_mutated_to_item_owned_by_another_character() -> None:
    item_one = inventory_item_state("item_001", "dagger")
    item_two = inventory_item_state("item_002", "shortsword")
    inventory_one = inventory_state("character_001", item_one)
    inventory_two = inventory_state("character_002", item_two)
    equipment = equipment_state("character_001", "item_001")
    original = snapshot(
        creature_state("character_001"),
        creature_state("character_002"),
        characters=(
            character_state("character_001"),
            character_state("character_002"),
        ),
        inventories=(inventory_one, inventory_two),
        equipment=(equipment,),
    )

    equipment.equipped_weapon_id = "item_002"

    with pytest.raises(ValueError):
        StateSerializer.serialize(original)


# --- V5 `combat` field (legacy strictness) ----------------------------------


def test_serialize_rejects_combat_referencing_missing_creature() -> None:
    with pytest.raises(ValueError):
        StateSerializer.serialize(
            snapshot(
                creature_state("character_001"),
                combat=combat_state("character_001", "monster_001"),
            )
        )


def test_serialize_rejects_mutated_invalid_combat_state() -> None:
    combat = combat_state("character_001", active_index=0)
    combat.round = 0  # type: ignore[assignment]

    with pytest.raises(ValueError):
        StateSerializer.serialize(snapshot(creature_state("character_001"), combat=combat))


def test_serialize_rejects_mutated_duplicate_combat_order() -> None:
    """CombatState.order intrinsically requires unique IDs at construction,
    but CombatState is a mutable dataclass; the serializer must independently
    reject a mutated instance whose order was corrupted into duplicates
    before ever writing it as V6."""
    combat = combat_state("character_001", "monster_001")
    combat.order = ("character_001", "character_001")  # type: ignore[assignment]

    with pytest.raises(ValueError, match="duplicate"):
        StateSerializer.serialize(
            snapshot(
                creature_state("character_001"),
                creature_state("monster_001"),
                combat=combat,
            )
        )


@pytest.mark.parametrize(
    ("path", "field"),
    [
        (("state", "combat"), "id"),
        (("state", "combat"), "round"),
        (("state", "combat"), "order"),
        (("state", "combat"), "activeIndex"),
    ],
)
def test_v5_deserialize_rejects_missing_combat_fields(
    path: tuple[str | int, ...],
    field: str,
) -> None:
    data = v5_data()
    nested(data, "state")["combat"] = deepcopy(COMBAT_DATA)  # type: ignore[index]
    del nested(data, *path)[field]  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v5_deserialize_rejects_unknown_combat_field() -> None:
    data = v5_data()
    combat = deepcopy(COMBAT_DATA)
    combat["extra"] = "unexpected"
    nested(data, "state")["combat"] = combat  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v5_deserialize_requires_combat_key() -> None:
    data = v5_data()
    del nested(data, "state")["combat"]  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v5_deserialize_rejects_combat_referencing_missing_creature() -> None:
    data = v5_data()
    combat = deepcopy(COMBAT_DATA)
    combat["order"] = ["does_not_exist"]
    combat["activeIndex"] = 0
    nested(data, "state")["combat"] = combat  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("state", "combat", "id"), 1),
        (("state", "combat", "round"), "1"),
        (("state", "combat", "round"), True),
        (("state", "combat", "order"), ()),
        (("state", "combat", "order", 0), 1),
        (("state", "combat", "activeIndex"), "0"),
        (("state", "combat", "activeIndex"), True),
    ],
)
def test_v5_deserialize_rejects_wrong_combat_types(
    path: tuple[str | int, ...],
    value: object,
) -> None:
    data = v5_data()
    combat = deepcopy(COMBAT_DATA)
    combat["order"] = ["character_001"]
    nested(data, "state")["combat"] = combat  # type: ignore[index]
    parent = nested(data, *path[:-1])
    parent[path[-1]] = value  # type: ignore[index]

    with pytest.raises(TypeError):
        StateSerializer.deserialize(data)


def test_v5_deserialize_rejects_out_of_range_active_index() -> None:
    data = v5_data()
    combat = deepcopy(COMBAT_DATA)
    combat["order"] = ["character_001"]
    combat["activeIndex"] = 1
    nested(data, "state")["combat"] = combat  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v5_deserialize_rejects_empty_combat_order() -> None:
    data = v5_data()
    combat = deepcopy(COMBAT_DATA)
    combat["order"] = []
    combat["activeIndex"] = 0
    nested(data, "state")["combat"] = combat  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v5_deserialize_accepts_present_combat() -> None:
    data = v5_data()
    combat = deepcopy(COMBAT_DATA)
    combat["order"] = ["character_001"]
    combat["activeIndex"] = 0
    nested(data, "state")["combat"] = combat  # type: ignore[index]

    reconstructed = StateSerializer.deserialize(data)

    assert reconstructed.combat == CombatState(
        id="combat_001", round=2, order=("character_001",), active_index=0
    )


# --- V6 state schema: strict reader -----------------------------------------


def test_v6_deserialize_rejects_missing_inventories_key() -> None:
    data = v6_data()
    del nested(data, "state")["inventories"]  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v6_deserialize_rejects_missing_equipment_key() -> None:
    data = v6_data()
    del nested(data, "state")["equipment"]  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v6_deserialize_rejects_missing_weapon_proficiencies_field() -> None:
    data = v6_data()
    del nested(data, "state", "characters", 0)["weaponProficiencies"]  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v6_deserialize_rejects_null_weapon_proficiencies() -> None:
    data = v6_data()
    nested(data, "state", "characters", 0)["weaponProficiencies"] = None  # type: ignore[index]

    with pytest.raises(TypeError):
        StateSerializer.deserialize(data)


def test_v6_deserialize_rejects_weapon_proficiencies_wrong_container() -> None:
    data = v6_data()
    nested(data, "state", "characters", 0)["weaponProficiencies"] = ()  # type: ignore[index]

    with pytest.raises(TypeError):
        StateSerializer.deserialize(data)


def test_v6_deserialize_rejects_duplicate_weapon_proficiencies() -> None:
    data = v6_data()
    nested(data, "state", "characters", 0)["weaponProficiencies"] = [  # type: ignore[index]
        "dagger",
        "dagger",
    ]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v6_deserialize_rejects_non_string_weapon_proficiency() -> None:
    data = v6_data()
    nested(data, "state", "characters", 0)["weaponProficiencies"] = [1]  # type: ignore[index]

    with pytest.raises(TypeError):
        StateSerializer.deserialize(data)


def test_v6_deserialize_accepts_weapon_proficiencies() -> None:
    data = v6_data()
    nested(data, "state", "characters", 0)["weaponProficiencies"] = [  # type: ignore[index]
        "dagger",
        "shortsword",
    ]

    reconstructed = StateSerializer.deserialize(data)

    assert reconstructed.characters[0].weapon_proficiencies == frozenset(
        {"dagger", "shortsword"}
    )


def test_v6_deserialize_rejects_unknown_state_field() -> None:
    data = v6_data()
    nested(data, "state")["positions"] = {}  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v6_deserialize_rejects_unknown_character_field() -> None:
    data = v6_data()
    nested(data, "state", "characters", 0)["classLevels"] = {}  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v6_deserialize_rejects_inventories_wrong_container() -> None:
    data = v6_data()
    nested(data, "state")["inventories"] = {}  # type: ignore[index]

    with pytest.raises(TypeError):
        StateSerializer.deserialize(data)


def test_v6_deserialize_rejects_equipment_wrong_container() -> None:
    data = v6_data()
    nested(data, "state")["equipment"] = {}  # type: ignore[index]

    with pytest.raises(TypeError):
        StateSerializer.deserialize(data)


def test_v6_deserialize_rejects_inventory_items_wrong_container() -> None:
    data = v6_data_with_inventory_and_equipment()
    nested(data, "state", "inventories", 0)["items"] = {}  # type: ignore[index]

    with pytest.raises(TypeError):
        StateSerializer.deserialize(data)


def test_v6_deserialize_rejects_missing_inventory_owner_id() -> None:
    data = v6_data_with_inventory_and_equipment()
    del nested(data, "state", "inventories", 0)["ownerId"]  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v6_deserialize_rejects_unknown_inventory_field() -> None:
    data = v6_data_with_inventory_and_equipment()
    nested(data, "state", "inventories", 0)["weight"] = 1  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v6_deserialize_rejects_inventory_owner_id_wrong_type() -> None:
    data = v6_data_with_inventory_and_equipment()
    nested(data, "state", "inventories", 0)["ownerId"] = 1  # type: ignore[index]

    with pytest.raises(TypeError):
        StateSerializer.deserialize(data)


@pytest.mark.parametrize("field", ["id", "definitionId"])
def test_v6_deserialize_rejects_missing_inventory_item_field(field: str) -> None:
    data = v6_data_with_inventory_and_equipment()
    del nested(data, "state", "inventories", 0, "items", 0)[field]  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v6_deserialize_rejects_unknown_inventory_item_field() -> None:
    data = v6_data_with_inventory_and_equipment()
    nested(data, "state", "inventories", 0, "items", 0)["quantity"] = 1  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


@pytest.mark.parametrize("field", ["id", "definitionId"])
def test_v6_deserialize_rejects_inventory_item_wrong_type(field: str) -> None:
    data = v6_data_with_inventory_and_equipment()
    nested(data, "state", "inventories", 0, "items", 0)[field] = 1  # type: ignore[index]

    with pytest.raises(TypeError):
        StateSerializer.deserialize(data)


@pytest.mark.parametrize("field", ["ownerId", "equippedWeaponId"])
def test_v6_deserialize_rejects_missing_equipment_field(field: str) -> None:
    data = v6_data_with_inventory_and_equipment()
    del nested(data, "state", "equipment", 0)[field]  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v6_deserialize_rejects_unknown_equipment_field() -> None:
    data = v6_data_with_inventory_and_equipment()
    nested(data, "state", "equipment", 0)["offHandItemId"] = None  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v6_deserialize_rejects_equipment_owner_id_wrong_type() -> None:
    data = v6_data_with_inventory_and_equipment()
    nested(data, "state", "equipment", 0)["ownerId"] = 1  # type: ignore[index]

    with pytest.raises(TypeError):
        StateSerializer.deserialize(data)


def test_v6_deserialize_rejects_equipped_weapon_id_bool_coercion() -> None:
    data = v6_data_with_inventory_and_equipment()
    nested(data, "state", "equipment", 0)["equippedWeaponId"] = True  # type: ignore[index]

    with pytest.raises(TypeError):
        StateSerializer.deserialize(data)


def test_v6_deserialize_rejects_equipped_weapon_id_int() -> None:
    data = v6_data_with_inventory_and_equipment()
    nested(data, "state", "equipment", 0)["equippedWeaponId"] = 1  # type: ignore[index]

    with pytest.raises(TypeError):
        StateSerializer.deserialize(data)


def test_v6_deserialize_accepts_null_equipped_weapon_id() -> None:
    data = v6_data()
    nested(data, "state")["inventories"] = [  # type: ignore[index]
        {"ownerId": "character_001", "items": []}
    ]
    nested(data, "state")["equipment"] = [  # type: ignore[index]
        {"ownerId": "character_001", "equippedWeaponId": None}
    ]

    reconstructed = StateSerializer.deserialize(data)

    assert reconstructed.equipment == (
        EquipmentState(owner_id="character_001", equipped_weapon_id=None),
    )


def test_v6_deserialize_rejects_duplicate_inventory_owner_id() -> None:
    data = two_character_v6_data()
    nested(data, "state")["inventories"] = [  # type: ignore[index]
        {"ownerId": "character_001", "items": []},
        {"ownerId": "character_001", "items": []},
    ]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v6_deserialize_rejects_duplicate_equipment_owner_id() -> None:
    data = two_character_v6_data()
    nested(data, "state")["equipment"] = [  # type: ignore[index]
        {"ownerId": "character_001", "equippedWeaponId": None},
        {"ownerId": "character_001", "equippedWeaponId": None},
    ]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v6_deserialize_rejects_inventory_owner_without_character() -> None:
    data = v6_data()
    inventory = deepcopy(INVENTORY_DATA)
    inventory["items"] = []
    inventory["ownerId"] = "character_999"
    nested(data, "state")["inventories"] = [inventory]  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v6_deserialize_rejects_equipment_owner_without_character() -> None:
    data = v6_data()
    equipment = {"ownerId": "character_999", "equippedWeaponId": None}
    nested(data, "state")["equipment"] = [equipment]  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v6_deserialize_rejects_equipped_weapon_id_without_matching_item() -> None:
    data = v6_data()
    nested(data, "state")["inventories"] = [  # type: ignore[index]
        {"ownerId": "character_001", "items": []}
    ]
    nested(data, "state")["equipment"] = [deepcopy(EQUIPMENT_DATA)]  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v6_deserialize_rejects_duplicate_item_ids_across_inventories() -> None:
    data = two_character_v6_data()
    nested(data, "state")["inventories"] = [  # type: ignore[index]
        {"ownerId": "character_001", "items": [deepcopy(INVENTORY_ITEM_DATA)]},
        {"ownerId": "character_002", "items": [deepcopy(INVENTORY_ITEM_DATA)]},
    ]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v6_deserialize_rejects_combat_positions_field() -> None:
    """State schema V6 emits exactly the existing V5 Combat wire shape; it
    does not add `positions` (that is the later, additive State schema V7
    contract)."""
    data = v6_data()
    combat = deepcopy(COMBAT_DATA)
    combat["order"] = ["character_001"]
    combat["activeIndex"] = 0
    combat["positions"] = {}
    nested(data, "state")["combat"] = combat  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v6_deserialize_accepts_present_combat() -> None:
    data = v6_data()
    combat = deepcopy(COMBAT_DATA)
    combat["order"] = ["character_001"]
    combat["activeIndex"] = 0
    nested(data, "state")["combat"] = combat  # type: ignore[index]

    reconstructed = StateSerializer.deserialize(data)

    assert reconstructed.combat == CombatState(
        id="combat_001", round=2, order=("character_001",), active_index=0
    )


def test_v6_deserialize_accepts_inventory_and_equipment() -> None:
    reconstructed = StateSerializer.deserialize(v6_data_with_inventory_and_equipment())

    assert reconstructed.inventories == (
        InventoryState(
            owner_id="character_001",
            items=(InventoryItemState(id="item_001", definition_id="dagger"),),
        ),
    )
    assert reconstructed.equipment == (
        EquipmentState(owner_id="character_001", equipped_weapon_id="item_001"),
    )
