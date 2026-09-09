from collections.abc import Mapping

from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.state.combat import CombatPosition, CombatState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.equipment import EquipmentState
from dnd_engine.domain.state.inventory import InventoryItemState, InventoryState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.domain.value_objects.condition import Condition
from dnd_engine.domain.value_objects.skill import Skill


LEGACY_SCHEMA_VERSION = 1
LEGACY_SCHEMA_V2_VERSION = 2
LEGACY_SCHEMA_V3_VERSION = 3
# Fixed identity of the V4 Creature shape (exact fields, `conditions`
# decoding). Historical V4 semantics must not be keyed off mutable
# SCHEMA_VERSION: once a future schema bump moves SCHEMA_VERSION past 4,
# `schema_version == SCHEMA_VERSION` would stop matching legacy V4 payloads
# and silently mis-decode them as pre-V4 (§3.21, DEC-0035).
SCHEMA_V4_VERSION = 4
# Fixed identity of the V5 state shape (adds the top-level `combat` key,
# §3.25/DEC-0040). Same rationale as SCHEMA_V4_VERSION above: historical V5
# semantics compare against this fixed sentinel, never against the mutable
# SCHEMA_VERSION below.
SCHEMA_V5_VERSION = 5
# Fixed identity of the V6 state shape (adds the top-level `inventories` and
# `equipment` keys plus Character `weaponProficiencies`, §3.29/§12.13). Same
# rationale as SCHEMA_V4_VERSION/SCHEMA_V5_VERSION above: historical V6
# semantics compare against this fixed sentinel, never against the mutable
# SCHEMA_VERSION below.
SCHEMA_V6_VERSION = 6
# Fixed identity of the V7 state shape (adds Combat `positions`,
# §3.30/DEC-0045). Same rationale as SCHEMA_V4_VERSION/SCHEMA_V5_VERSION/
# SCHEMA_V6_VERSION above: historical V7 semantics compare against this
# fixed sentinel, never against the mutable SCHEMA_VERSION below. V7 is
# strictly additive over V6 (§12.13): every other V6 shape/field-set is
# unchanged and reused as-is by V7.
SCHEMA_V7_VERSION = 7
# Fixed identity of the V8 state shape (adds Combat `actionSpent`,
# §3.33/DEC-0049). Same rationale as SCHEMA_V4_VERSION/SCHEMA_V5_VERSION/
# SCHEMA_V6_VERSION/SCHEMA_V7_VERSION above: historical V8 semantics compare
# against this fixed sentinel, never against the mutable SCHEMA_VERSION
# below. V8 is strictly additive over V7 (§12.13): every other V7
# shape/field-set is unchanged and reused as-is by V8.
SCHEMA_V8_VERSION = 8
SCHEMA_VERSION = SCHEMA_V8_VERSION
# The V4 Creature shape (with `conditions`) is unchanged by the V5 state-level
# `combat` addition, the V6 weapon-source additions, the V7 Combat
# `positions` addition, and the V8 Combat `actionSpent` addition; all five
# versions decode Creature payloads the same way.
_CREATURE_SCHEMA_VERSIONS_WITH_CONDITIONS = {
    SCHEMA_V4_VERSION,
    SCHEMA_V5_VERSION,
    SCHEMA_V6_VERSION,
    SCHEMA_V7_VERSION,
    SCHEMA_V8_VERSION,
}

_ROOT_FIELDS = {"schemaVersion", "campaignId", "state"}
_V1_STATE_FIELDS = {"campaign", "creatures"}
_V2_STATE_FIELDS = {"campaign", "creatures", "characters"}
_V5_STATE_FIELDS = _V2_STATE_FIELDS | {"combat"}
# Neither V7 nor V8 adds a new top-level state key: `positions` and
# `actionSpent` both live inside the existing `combat` key (see
# _V7_COMBAT_FIELDS/_V8_COMBAT_FIELDS below), so V6, V7, and V8 share this
# exact top-level state field set.
_V6_STATE_FIELDS = _V5_STATE_FIELDS | {"inventories", "equipment"}
_CAMPAIGN_FIELDS = {"id", "rulesetId", "rulesetVersion"}
_CREATURE_FIELDS = {
    "id",
    "definitionId",
    "abilityScores",
    "currentHp",
    "maxHp",
}
_V4_CREATURE_FIELDS = _CREATURE_FIELDS | {"conditions"}
_V2_CHARACTER_FIELDS = {
    "id",
    "totalLevel",
    "savingThrowProficiencies",
}
_V3_CHARACTER_FIELDS = _V2_CHARACTER_FIELDS | {"skillProficiencies"}
_V6_CHARACTER_FIELDS = _V3_CHARACTER_FIELDS | {"weaponProficiencies"}
_ABILITY_SCORE_FIELDS = {
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
}
_COMBAT_FIELDS = {"id", "round", "order", "activeIndex"}
# V7 adds `positions` to the existing exact V5/V6 Combat wire shape; V5/V6
# combat payloads must keep rejecting it (§3.30/DEC-0045, §12.13).
_V7_COMBAT_FIELDS = _COMBAT_FIELDS | {"positions"}
# V8 adds `actionSpent` to the existing exact V5/V6/V7 Combat wire shape;
# V5/V6/V7 combat payloads must keep rejecting it (§3.33/DEC-0049, §12.13).
_V8_COMBAT_FIELDS = _V7_COMBAT_FIELDS | {"actionSpent"}
_COMBAT_POSITION_FIELDS = {"creatureId", "x", "y"}
_INVENTORY_FIELDS = {"ownerId", "items"}
_INVENTORY_ITEM_FIELDS = {"id", "definitionId"}
_EQUIPMENT_FIELDS = {"ownerId", "equippedWeaponId"}


def _require_mapping(value: object, location: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{location} must be a mapping")
    return value  # type: ignore[return-value]


def _require_exact_fields(
    data: Mapping[str, object],
    expected: set[str],
    location: str,
) -> None:
    missing = expected - data.keys()
    if missing:
        raise ValueError(f"missing required {location} fields: {sorted(missing)}")
    unknown = data.keys() - expected
    if unknown:
        raise ValueError(
            f"unknown {location} fields: {sorted(unknown, key=repr)}"
        )


def _require_str(value: object, location: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{location} must be a str")
    return value


def _require_int(value: object, location: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{location} must be an int")
    return value


def _require_bool(value: object, location: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{location} must be a bool")
    return value


def _validate_campaign(campaign: CampaignState) -> None:
    if not isinstance(campaign, CampaignState):
        raise TypeError("snapshot campaign must be a CampaignState")
    _require_str(campaign.id, "campaign.id")
    _require_str(campaign.ruleset_id, "campaign.ruleset_id")
    _require_str(campaign.ruleset_version, "campaign.ruleset_version")


def _validate_ability_scores(ability_scores: AbilityScores) -> None:
    if not isinstance(ability_scores, AbilityScores):
        raise TypeError("creature ability_scores must be AbilityScores")
    for field_name in _ABILITY_SCORE_FIELDS:
        score = _require_int(
            getattr(ability_scores, field_name),
            f"ability_scores.{field_name}",
        )
        if not 1 <= score <= 30:
            raise ValueError(f"ability_scores.{field_name} must be between 1 and 30")


def _validate_creature(creature: CreatureState) -> None:
    if not isinstance(creature, CreatureState):
        raise TypeError("snapshot creatures must contain only CreatureState values")
    _require_str(creature.id, "creature.id")
    _require_str(creature.definition_id, "creature.definition_id")
    _validate_ability_scores(creature.ability_scores)
    current_hp = _require_int(creature.current_hp, "creature.current_hp")
    max_hp = _require_int(creature.max_hp, "creature.max_hp")
    if max_hp < 1:
        raise ValueError("creature.max_hp must be at least 1")
    if not 0 <= current_hp <= max_hp:
        raise ValueError("creature.current_hp must be between 0 and max_hp")
    if type(creature.conditions) is not frozenset:
        raise TypeError("creature conditions must be a frozenset")
    if not all(
        isinstance(condition, Condition) for condition in creature.conditions
    ):
        raise TypeError("creature conditions must contain only Condition values")


def _validate_character(character: CharacterState) -> None:
    if not isinstance(character, CharacterState):
        raise TypeError("snapshot characters must contain only CharacterState values")
    _require_str(character.id, "character.id")
    total_level = _require_int(character.total_level, "character.total_level")
    if not 1 <= total_level <= 20:
        raise ValueError("character.total_level must be between 1 and 20")
    if type(character.saving_throw_proficiencies) is not frozenset:
        raise TypeError("character saving_throw_proficiencies must be a frozenset")
    if not all(
        isinstance(ability, Ability)
        for ability in character.saving_throw_proficiencies
    ):
        raise TypeError(
            "character saving_throw_proficiencies must contain only Ability values"
        )
    if type(character.skill_proficiencies) is not frozenset:
        raise TypeError("character skill_proficiencies must be a frozenset")
    if not all(
        isinstance(skill, Skill) for skill in character.skill_proficiencies
    ):
        raise TypeError(
            "character skill_proficiencies must contain only Skill values"
        )
    if type(character.weapon_proficiencies) is not frozenset:
        raise TypeError("character weapon_proficiencies must be a frozenset")
    if not all(
        type(proficiency) is str
        for proficiency in character.weapon_proficiencies
    ):
        raise TypeError(
            "character weapon_proficiencies must contain only str values"
        )


def _validate_inventory_item(item: InventoryItemState, location: str) -> None:
    if not isinstance(item, InventoryItemState):
        raise TypeError(f"{location} must be an InventoryItemState")
    _require_str(item.id, f"{location}.id")
    _require_str(item.definition_id, f"{location}.definition_id")


def _validate_inventory(inventory: InventoryState) -> None:
    if not isinstance(inventory, InventoryState):
        raise TypeError("snapshot inventories must contain only InventoryState values")
    _require_str(inventory.owner_id, "inventory.owner_id")
    if type(inventory.items) is not tuple:
        raise TypeError("inventory.items must be a tuple")
    for item_index, item in enumerate(inventory.items):
        _validate_inventory_item(item, f"inventory.items[{item_index}]")


def _validate_equipment(equipment: EquipmentState) -> None:
    if not isinstance(equipment, EquipmentState):
        raise TypeError("snapshot equipment must contain only EquipmentState values")
    _require_str(equipment.owner_id, "equipment.owner_id")
    if (
        equipment.equipped_weapon_id is not None
        and type(equipment.equipped_weapon_id) is not str
    ):
        raise TypeError("equipment.equipped_weapon_id must be a str or None")


def _validate_weapon_source_relations(
    snapshot: StateSnapshot, character_ids: set[str]
) -> None:
    """`StateSnapshot.__post_init__` checks these same relations, but only
    once, at construction. Its nested Inventory/Equipment dataclasses are
    mutable, so a snapshot that was valid when built can be mutated into a
    relationally invalid one before this write; re-check independently here
    using the current values, mirroring the canonical Domain invariants
    exactly rather than introducing a new validation abstraction."""
    inventory_owner_ids = [inventory.owner_id for inventory in snapshot.inventories]
    if len(inventory_owner_ids) != len(set(inventory_owner_ids)):
        raise ValueError("at most one InventoryState is allowed per owner")
    if not set(inventory_owner_ids).issubset(character_ids):
        raise ValueError(
            "every InventoryState owner must have a corresponding CharacterState"
        )

    equipment_owner_ids = [equipment.owner_id for equipment in snapshot.equipment]
    if len(equipment_owner_ids) != len(set(equipment_owner_ids)):
        raise ValueError("at most one EquipmentState is allowed per owner")
    if not set(equipment_owner_ids).issubset(character_ids):
        raise ValueError(
            "every EquipmentState owner must have a corresponding CharacterState"
        )

    item_ids = [
        item.id for inventory in snapshot.inventories for item in inventory.items
    ]
    if len(item_ids) != len(set(item_ids)):
        raise ValueError(
            "InventoryItemState IDs must be unique within a StateSnapshot"
        )

    inventories_by_owner = {
        inventory.owner_id: inventory for inventory in snapshot.inventories
    }
    for equipment in snapshot.equipment:
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


def _serialize_ability_scores(ability_scores: AbilityScores) -> dict[str, object]:
    return {
        "strength": ability_scores.strength,
        "dexterity": ability_scores.dexterity,
        "constitution": ability_scores.constitution,
        "intelligence": ability_scores.intelligence,
        "wisdom": ability_scores.wisdom,
        "charisma": ability_scores.charisma,
    }


def _serialize_creature(creature: CreatureState) -> dict[str, object]:
    return {
        "id": creature.id,
        "definitionId": creature.definition_id,
        "abilityScores": _serialize_ability_scores(creature.ability_scores),
        "currentHp": creature.current_hp,
        "maxHp": creature.max_hp,
        "conditions": [
            condition.value
            for condition in sorted(
                creature.conditions,
                key=lambda condition: condition.value,
            )
        ],
    }


def _serialize_character(character: CharacterState) -> dict[str, object]:
    return {
        "id": character.id,
        "totalLevel": character.total_level,
        "savingThrowProficiencies": [
            ability.value
            for ability in sorted(
                character.saving_throw_proficiencies,
                key=lambda ability: ability.value,
            )
        ],
        "skillProficiencies": [
            skill.value
            for skill in sorted(
                character.skill_proficiencies,
                key=lambda skill: skill.value,
            )
        ],
        "weaponProficiencies": sorted(character.weapon_proficiencies),
    }


def _serialize_inventory_item(item: InventoryItemState) -> dict[str, object]:
    return {
        "id": item.id,
        "definitionId": item.definition_id,
    }


def _serialize_inventory(inventory: InventoryState) -> dict[str, object]:
    items = sorted(inventory.items, key=lambda item: item.id)
    return {
        "ownerId": inventory.owner_id,
        "items": [_serialize_inventory_item(item) for item in items],
    }


def _serialize_equipment(equipment: EquipmentState) -> dict[str, object]:
    return {
        "ownerId": equipment.owner_id,
        "equippedWeaponId": equipment.equipped_weapon_id,
    }


def _validate_combat(combat: CombatState | None, creature_ids: set[str]) -> None:
    if combat is None:
        return
    if not isinstance(combat, CombatState):
        raise TypeError("snapshot combat must be a CombatState or None")
    _require_str(combat.id, "combat.id")
    round_ = _require_int(combat.round, "combat.round")
    if round_ < 1:
        raise ValueError("combat.round must be at least 1")
    if type(combat.order) is not tuple or len(combat.order) == 0:
        raise TypeError("combat.order must be a non-empty tuple")
    if not all(type(creature_id) is str for creature_id in combat.order):
        raise TypeError("combat.order must contain only str values")
    if len(set(combat.order)) != len(combat.order):
        raise ValueError("combat.order must not contain duplicate creature ids")
    if not set(combat.order).issubset(creature_ids):
        raise ValueError(
            "every CombatState participant must have a corresponding CreatureState"
        )
    active_index = _require_int(combat.active_index, "combat.active_index")
    if not 0 <= active_index < len(combat.order):
        raise ValueError("combat.active_index must be a valid index into combat.order")

    if type(combat.positions) is not tuple:
        raise TypeError("combat.positions must be a tuple")
    position_creature_ids: list[str] = []
    for position in combat.positions:
        if not isinstance(position, CombatPosition):
            raise TypeError(
                "combat.positions must contain only CombatPosition values"
            )
        _require_str(position.creature_id, "combat.positions[].creatureId")
        _require_int(position.x, "combat.positions[].x")
        _require_int(position.y, "combat.positions[].y")
        position_creature_ids.append(position.creature_id)
    if len(set(position_creature_ids)) != len(position_creature_ids):
        raise ValueError("combat.positions must not contain duplicate creature ids")
    if not set(position_creature_ids).issubset(combat.order):
        raise ValueError(
            "every positioned creature must be present in combat.order"
        )
    _require_bool(combat.action_spent, "combat.action_spent")


def _serialize_combat_position(position: CombatPosition) -> dict[str, object]:
    return {
        "creatureId": position.creature_id,
        "x": position.x,
        "y": position.y,
    }


def _serialize_combat(combat: CombatState | None) -> dict[str, object] | None:
    if combat is None:
        return None
    positions = sorted(combat.positions, key=lambda position: position.creature_id)
    return {
        "id": combat.id,
        "round": combat.round,
        "order": list(combat.order),
        "activeIndex": combat.active_index,
        "positions": [
            _serialize_combat_position(position) for position in positions
        ],
        "actionSpent": combat.action_spent,
    }


class StateSerializer:
    @staticmethod
    def serialize(snapshot: StateSnapshot) -> dict[str, object]:
        if not isinstance(snapshot, StateSnapshot):
            raise TypeError("snapshot must be a StateSnapshot")

        _validate_campaign(snapshot.campaign)
        creature_ids: set[str] = set()
        for creature in snapshot.creatures:
            _validate_creature(creature)
            if creature.id in creature_ids:
                raise ValueError("creature IDs must be unique within a StateSnapshot")
            creature_ids.add(creature.id)

        character_ids: set[str] = set()
        for character in snapshot.characters:
            _validate_character(character)
            if character.id in character_ids:
                raise ValueError("character IDs must be unique within a StateSnapshot")
            if character.id not in creature_ids:
                raise ValueError(
                    "every CharacterState must have a corresponding CreatureState"
                )
            character_ids.add(character.id)

        for inventory in snapshot.inventories:
            _validate_inventory(inventory)
        for equipment in snapshot.equipment:
            _validate_equipment(equipment)
        _validate_weapon_source_relations(snapshot, character_ids)

        _validate_combat(snapshot.combat, creature_ids)

        creatures = sorted(snapshot.creatures, key=lambda creature: creature.id)
        characters = sorted(snapshot.characters, key=lambda character: character.id)
        inventories = sorted(snapshot.inventories, key=lambda inventory: inventory.owner_id)
        equipment_entries = sorted(
            snapshot.equipment, key=lambda equipment: equipment.owner_id
        )
        return {
            "schemaVersion": SCHEMA_VERSION,
            "campaignId": snapshot.campaign.id,
            "state": {
                "campaign": {
                    "id": snapshot.campaign.id,
                    "rulesetId": snapshot.campaign.ruleset_id,
                    "rulesetVersion": snapshot.campaign.ruleset_version,
                },
                "creatures": [
                    _serialize_creature(creature) for creature in creatures
                ],
                "characters": [
                    _serialize_character(character) for character in characters
                ],
                "inventories": [
                    _serialize_inventory(inventory) for inventory in inventories
                ],
                "equipment": [
                    _serialize_equipment(equipment) for equipment in equipment_entries
                ],
                "combat": _serialize_combat(snapshot.combat),
            },
        }

    @staticmethod
    def deserialize(data: Mapping[str, object]) -> StateSnapshot:
        root = _require_mapping(data, "State snapshot")
        _require_exact_fields(root, _ROOT_FIELDS, "State snapshot")

        schema_version = _require_int(root["schemaVersion"], "schemaVersion")
        if schema_version not in {
            LEGACY_SCHEMA_VERSION,
            LEGACY_SCHEMA_V2_VERSION,
            LEGACY_SCHEMA_V3_VERSION,
            SCHEMA_V4_VERSION,
            SCHEMA_V5_VERSION,
            SCHEMA_V6_VERSION,
            SCHEMA_V7_VERSION,
            SCHEMA_V8_VERSION,
        }:
            raise ValueError(f"unsupported schemaVersion: {schema_version}")

        campaign_id = _require_str(root["campaignId"], "campaignId")
        state = _require_mapping(root["state"], "state")
        if schema_version == LEGACY_SCHEMA_VERSION:
            state_fields = _V1_STATE_FIELDS
        elif schema_version in {SCHEMA_V6_VERSION, SCHEMA_V7_VERSION, SCHEMA_V8_VERSION}:
            state_fields = _V6_STATE_FIELDS
        elif schema_version == SCHEMA_V5_VERSION:
            state_fields = _V5_STATE_FIELDS
        else:
            state_fields = _V2_STATE_FIELDS
        _require_exact_fields(state, state_fields, "state")

        campaign_data = _require_mapping(state["campaign"], "state.campaign")
        _require_exact_fields(campaign_data, _CAMPAIGN_FIELDS, "campaign")
        campaign = CampaignState(
            id=_require_str(campaign_data["id"], "campaign.id"),
            ruleset_id=_require_str(
                campaign_data["rulesetId"], "campaign.rulesetId"
            ),
            ruleset_version=_require_str(
                campaign_data["rulesetVersion"], "campaign.rulesetVersion"
            ),
        )
        if campaign_id != campaign.id:
            raise ValueError("campaignId must match state.campaign.id")

        creatures_data = state["creatures"]
        if type(creatures_data) is not list:
            raise TypeError("state.creatures must be a list")
        creatures = tuple(
            StateSerializer._deserialize_creature(
                creature_data,
                index,
                schema_version,
            )
            for index, creature_data in enumerate(creatures_data)
        )
        if schema_version == LEGACY_SCHEMA_VERSION:
            characters: tuple[CharacterState, ...] = ()
        else:
            characters_data = state["characters"]
            if type(characters_data) is not list:
                raise TypeError("state.characters must be a list")
            characters = tuple(
                StateSerializer._deserialize_character(
                    character_data,
                    index,
                    schema_version,
                )
                for index, character_data in enumerate(characters_data)
            )
        if schema_version in {
            SCHEMA_V5_VERSION,
            SCHEMA_V6_VERSION,
            SCHEMA_V7_VERSION,
            SCHEMA_V8_VERSION,
        }:
            combat = StateSerializer._deserialize_combat(state["combat"], schema_version)
        else:
            combat = None

        if schema_version in {SCHEMA_V6_VERSION, SCHEMA_V7_VERSION, SCHEMA_V8_VERSION}:
            inventories_data = state["inventories"]
            if type(inventories_data) is not list:
                raise TypeError("state.inventories must be a list")
            inventories: tuple[InventoryState, ...] = tuple(
                StateSerializer._deserialize_inventory(inventory_data, index)
                for index, inventory_data in enumerate(inventories_data)
            )

            equipment_data = state["equipment"]
            if type(equipment_data) is not list:
                raise TypeError("state.equipment must be a list")
            equipment: tuple[EquipmentState, ...] = tuple(
                StateSerializer._deserialize_equipment(entry_data, index)
                for index, entry_data in enumerate(equipment_data)
            )
        else:
            inventories = ()
            equipment = ()

        return StateSnapshot(
            campaign=campaign,
            creatures=creatures,
            characters=characters,
            inventories=inventories,
            equipment=equipment,
            combat=combat,
        )

    @staticmethod
    def _deserialize_creature(
        data: object,
        index: int,
        schema_version: int,
    ) -> CreatureState:
        creature = _require_mapping(data, f"state.creatures[{index}]")
        creature_fields = (
            _V4_CREATURE_FIELDS
            if schema_version in _CREATURE_SCHEMA_VERSIONS_WITH_CONDITIONS
            else _CREATURE_FIELDS
        )
        _require_exact_fields(creature, creature_fields, "creature")

        ability_data = _require_mapping(
            creature["abilityScores"],
            f"state.creatures[{index}].abilityScores",
        )
        _require_exact_fields(
            ability_data,
            _ABILITY_SCORE_FIELDS,
            "abilityScores",
        )
        ability_scores = AbilityScores(
            strength=_require_int(ability_data["strength"], "strength"),
            dexterity=_require_int(ability_data["dexterity"], "dexterity"),
            constitution=_require_int(
                ability_data["constitution"], "constitution"
            ),
            intelligence=_require_int(
                ability_data["intelligence"], "intelligence"
            ),
            wisdom=_require_int(ability_data["wisdom"], "wisdom"),
            charisma=_require_int(ability_data["charisma"], "charisma"),
        )

        conditions: list[Condition] = []
        if schema_version in _CREATURE_SCHEMA_VERSIONS_WITH_CONDITIONS:
            conditions_data = creature["conditions"]
            if type(conditions_data) is not list:
                raise TypeError(
                    f"state.creatures[{index}].conditions must be a list"
                )
            for condition_index, value in enumerate(conditions_data):
                condition_value = _require_str(
                    value,
                    f"state.creatures[{index}].conditions[{condition_index}]",
                )
                try:
                    condition = Condition(condition_value)
                except ValueError as error:
                    raise ValueError(
                        f"invalid condition: {condition_value!r}"
                    ) from error
                if condition in conditions:
                    raise ValueError("conditions must not contain duplicates")
                conditions.append(condition)

        return CreatureState(
            id=_require_str(creature["id"], "creature.id"),
            definition_id=_require_str(
                creature["definitionId"], "creature.definitionId"
            ),
            ability_scores=ability_scores,
            current_hp=_require_int(creature["currentHp"], "creature.currentHp"),
            max_hp=_require_int(creature["maxHp"], "creature.maxHp"),
            conditions=frozenset(conditions),
        )

    @staticmethod
    def _deserialize_character(
        data: object,
        index: int,
        schema_version: int,
    ) -> CharacterState:
        character = _require_mapping(data, f"state.characters[{index}]")
        if schema_version == LEGACY_SCHEMA_V2_VERSION:
            character_fields = _V2_CHARACTER_FIELDS
        elif schema_version in {
            SCHEMA_V6_VERSION,
            SCHEMA_V7_VERSION,
            SCHEMA_V8_VERSION,
        }:
            character_fields = _V6_CHARACTER_FIELDS
        else:
            character_fields = _V3_CHARACTER_FIELDS
        _require_exact_fields(character, character_fields, "character")

        total_level = _require_int(
            character["totalLevel"],
            f"state.characters[{index}].totalLevel",
        )
        if not 1 <= total_level <= 20:
            raise ValueError(
                f"state.characters[{index}].totalLevel must be between 1 and 20"
            )

        proficiencies_data = character["savingThrowProficiencies"]
        if type(proficiencies_data) is not list:
            raise TypeError(
                f"state.characters[{index}].savingThrowProficiencies must be a list"
            )
        proficiencies: list[Ability] = []
        for proficiency_index, value in enumerate(proficiencies_data):
            ability_value = _require_str(
                value,
                "state.characters"
                f"[{index}].savingThrowProficiencies[{proficiency_index}]",
            )
            try:
                ability = Ability(ability_value)
            except ValueError as error:
                raise ValueError(
                    "invalid saving throw proficiency: "
                    f"{ability_value!r}"
                ) from error
            if ability in proficiencies:
                raise ValueError(
                    "savingThrowProficiencies must not contain duplicates"
                )
            proficiencies.append(ability)

        # V1 has no Character projection at all; V2 predates skillProficiencies.
        # V3 and V4 share the same Character schema (§3.2.4 is unaffected by
        # the V4 Creature-only schema bump), so both decode skillProficiencies.
        skill_proficiencies: list[Skill] = []
        if schema_version != LEGACY_SCHEMA_V2_VERSION:
            skill_proficiencies_data = character["skillProficiencies"]
            if type(skill_proficiencies_data) is not list:
                raise TypeError(
                    f"state.characters[{index}].skillProficiencies must be a list"
                )
            for proficiency_index, value in enumerate(
                skill_proficiencies_data
            ):
                skill_value = _require_str(
                    value,
                    "state.characters"
                    f"[{index}].skillProficiencies[{proficiency_index}]",
                )
                try:
                    skill = Skill(skill_value)
                except ValueError as error:
                    raise ValueError(
                        f"invalid skill proficiency: {skill_value!r}"
                    ) from error
                if skill in skill_proficiencies:
                    raise ValueError(
                        "skillProficiencies must not contain duplicates"
                    )
                skill_proficiencies.append(skill)

        # V1-V5 predate `weaponProficiencies`; legacy migration always yields
        # empty weapon-source membership (§12.13), never a synthesized value.
        weapon_proficiencies: list[str] = []
        if schema_version in {
            SCHEMA_V6_VERSION,
            SCHEMA_V7_VERSION,
            SCHEMA_V8_VERSION,
        }:
            weapon_proficiencies_data = character["weaponProficiencies"]
            if type(weapon_proficiencies_data) is not list:
                raise TypeError(
                    f"state.characters[{index}].weaponProficiencies must be a list"
                )
            for proficiency_index, value in enumerate(weapon_proficiencies_data):
                weapon_value = _require_str(
                    value,
                    "state.characters"
                    f"[{index}].weaponProficiencies[{proficiency_index}]",
                )
                if weapon_value in weapon_proficiencies:
                    raise ValueError(
                        "weaponProficiencies must not contain duplicates"
                    )
                weapon_proficiencies.append(weapon_value)

        return CharacterState(
            id=_require_str(character["id"], f"state.characters[{index}].id"),
            total_level=total_level,
            saving_throw_proficiencies=frozenset(proficiencies),
            skill_proficiencies=frozenset(skill_proficiencies),
            weapon_proficiencies=frozenset(weapon_proficiencies),
        )

    @staticmethod
    def _deserialize_inventory_item(
        data: object,
        inventory_index: int,
        item_index: int,
    ) -> InventoryItemState:
        item = _require_mapping(
            data, f"state.inventories[{inventory_index}].items[{item_index}]"
        )
        _require_exact_fields(item, _INVENTORY_ITEM_FIELDS, "inventory item")
        return InventoryItemState(
            id=_require_str(
                item["id"],
                f"state.inventories[{inventory_index}].items[{item_index}].id",
            ),
            definition_id=_require_str(
                item["definitionId"],
                f"state.inventories[{inventory_index}].items[{item_index}]"
                ".definitionId",
            ),
        )

    @staticmethod
    def _deserialize_inventory(data: object, index: int) -> InventoryState:
        inventory = _require_mapping(data, f"state.inventories[{index}]")
        _require_exact_fields(inventory, _INVENTORY_FIELDS, "inventory")

        items_data = inventory["items"]
        if type(items_data) is not list:
            raise TypeError(f"state.inventories[{index}].items must be a list")
        items = tuple(
            StateSerializer._deserialize_inventory_item(item_data, index, item_index)
            for item_index, item_data in enumerate(items_data)
        )

        return InventoryState(
            owner_id=_require_str(
                inventory["ownerId"], f"state.inventories[{index}].ownerId"
            ),
            items=items,
        )

    @staticmethod
    def _deserialize_equipment(data: object, index: int) -> EquipmentState:
        equipment = _require_mapping(data, f"state.equipment[{index}]")
        _require_exact_fields(equipment, _EQUIPMENT_FIELDS, "equipment")

        equipped_weapon_id_value = equipment["equippedWeaponId"]
        if equipped_weapon_id_value is not None:
            equipped_weapon_id_value = _require_str(
                equipped_weapon_id_value,
                f"state.equipment[{index}].equippedWeaponId",
            )

        return EquipmentState(
            owner_id=_require_str(
                equipment["ownerId"], f"state.equipment[{index}].ownerId"
            ),
            equipped_weapon_id=equipped_weapon_id_value,
        )

    @staticmethod
    def _deserialize_combat(
        data: object, schema_version: int
    ) -> CombatState | None:
        if data is None:
            return None
        combat = _require_mapping(data, "state.combat")
        if schema_version == SCHEMA_V8_VERSION:
            combat_fields = _V8_COMBAT_FIELDS
        elif schema_version == SCHEMA_V7_VERSION:
            combat_fields = _V7_COMBAT_FIELDS
        else:
            combat_fields = _COMBAT_FIELDS
        _require_exact_fields(combat, combat_fields, "combat")

        order_data = combat["order"]
        if type(order_data) is not list:
            raise TypeError("state.combat.order must be a list")
        order = tuple(
            _require_str(value, f"state.combat.order[{index}]")
            for index, value in enumerate(order_data)
        )

        positions: tuple[CombatPosition, ...] = ()
        if schema_version in {SCHEMA_V7_VERSION, SCHEMA_V8_VERSION}:
            positions_data = combat["positions"]
            if type(positions_data) is not list:
                raise TypeError("state.combat.positions must be a list")
            positions = tuple(
                StateSerializer._deserialize_combat_position(position_data, index)
                for index, position_data in enumerate(positions_data)
            )

        # V5-V7 predate `actionSpent`; a legacy active Combat always decodes
        # to an unspent Action -- a compatibility default, not a recovered
        # historical fact (§3.33/DEC-0049, §12.13).
        action_spent = False
        if schema_version == SCHEMA_V8_VERSION:
            action_spent = _require_bool(combat["actionSpent"], "combat.actionSpent")

        return CombatState(
            id=_require_str(combat["id"], "combat.id"),
            round=_require_int(combat["round"], "combat.round"),
            order=order,
            active_index=_require_int(combat["activeIndex"], "combat.activeIndex"),
            positions=positions,
            action_spent=action_spent,
        )

    @staticmethod
    def _deserialize_combat_position(data: object, index: int) -> CombatPosition:
        position = _require_mapping(data, f"state.combat.positions[{index}]")
        _require_exact_fields(position, _COMBAT_POSITION_FIELDS, "combat position")
        return CombatPosition(
            creature_id=_require_str(
                position["creatureId"],
                f"state.combat.positions[{index}].creatureId",
            ),
            x=_require_int(position["x"], f"state.combat.positions[{index}].x"),
            y=_require_int(position["y"], f"state.combat.positions[{index}].y"),
        )
