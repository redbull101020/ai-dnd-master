from copy import deepcopy

import pytest

from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
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

CANONICAL_V2_DATA: dict[str, object] = {
    "schemaVersion": 2,
    "campaignId": "campaign_001",
    "state": {
        "campaign": {
            "id": "campaign_001",
            "rulesetId": "dnd_5e",
            "rulesetVersion": "5.2.1",
        },
        "creatures": [CREATURE_DATA],
        "characters": [
            {
                "id": "character_001",
                "totalLevel": 5,
                "savingThrowProficiencies": ["constitution", "strength"],
            }
        ],
    },
}

LEGACY_V1_DATA: dict[str, object] = {
    "schemaVersion": 1,
    "campaignId": "campaign_001",
    "state": {
        "campaign": {
            "id": "campaign_001",
            "rulesetId": "dnd_5e",
            "rulesetVersion": "5.2.1",
        },
        "creatures": [CREATURE_DATA],
    },
}


def campaign_state() -> CampaignState:
    return CampaignState("campaign_001", "dnd_5e", "5.2.1")


def creature_state(creature_id: str = "character_001") -> CreatureState:
    return CreatureState(
        id=creature_id,
        definition_id="fighter",
        ability_scores=AbilityScores(16, 12, 14, 10, 10, 8),
        current_hp=28,
        max_hp=28,
    )


def character_state(character_id: str = "character_001") -> CharacterState:
    return CharacterState(
        id=character_id,
        total_level=5,
        saving_throw_proficiencies=frozenset(
            {Ability.STRENGTH, Ability.CONSTITUTION}
        ),
    )


def snapshot(
    *creatures: CreatureState,
    characters: tuple[CharacterState, ...] = (),
) -> StateSnapshot:
    return StateSnapshot(campaign_state(), tuple(creatures), characters)


def v2_data() -> dict[str, object]:
    return deepcopy(CANONICAL_V2_DATA)


def v1_data() -> dict[str, object]:
    return deepcopy(LEGACY_V1_DATA)


def nested(data: dict[str, object], *path: str | int) -> object:
    value: object = data
    for part in path:
        value = value[part]  # type: ignore[index]
    return value


def test_serialize_emits_exact_canonical_v2_mapping() -> None:
    serialized = StateSerializer.serialize(
        snapshot(creature_state(), characters=(character_state(),))
    )

    assert serialized == CANONICAL_V2_DATA
    assert serialized["schemaVersion"] == 2


def test_serialize_emits_empty_characters_in_v2() -> None:
    serialized = StateSerializer.serialize(snapshot())

    assert serialized == {
        "schemaVersion": 2,
        "campaignId": "campaign_001",
        "state": {
            "campaign": {
                "id": "campaign_001",
                "rulesetId": "dnd_5e",
                "rulesetVersion": "5.2.1",
            },
            "creatures": [],
            "characters": [],
        },
    }


def test_serialize_uses_exact_v2_state_and_character_fields() -> None:
    serialized = StateSerializer.serialize(
        snapshot(creature_state(), characters=(character_state(),))
    )
    state = serialized["state"]  # type: ignore[assignment]
    character = state["characters"][0]  # type: ignore[index]

    assert set(state) == {"campaign", "creatures", "characters"}
    assert set(character) == {
        "id",
        "totalLevel",
        "savingThrowProficiencies",
    }


def test_serialize_orders_creatures_characters_and_proficiencies() -> None:
    first = character_state("character_001")
    first.saving_throw_proficiencies = frozenset(
        {Ability.WISDOM, Ability.DEXTERITY, Ability.CHARISMA}
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


def test_v2_round_trip_reconstructs_equivalent_current_snapshot() -> None:
    original = snapshot(creature_state(), characters=(character_state(),))

    reconstructed = StateSerializer.deserialize(StateSerializer.serialize(original))

    assert reconstructed == original


def test_deserialize_accepts_exact_legacy_v1_without_inventing_character_state() -> None:
    reconstructed = StateSerializer.deserialize(v1_data())

    assert reconstructed.campaign == campaign_state()
    assert reconstructed.creatures == (creature_state(),)
    assert reconstructed.characters == ()


def test_deserialize_rejects_characters_field_in_legacy_v1() -> None:
    data = v1_data()
    nested(data, "state")["characters"] = []  # type: ignore[index]

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
def test_v2_deserialize_rejects_unknown_fields(
    path: tuple[str | int, ...],
    field: str,
) -> None:
    data = v2_data()
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
    ],
)
def test_v2_deserialize_rejects_missing_required_fields(
    path: tuple[str | int, ...],
    field: str,
) -> None:
    data = v2_data()
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
    ],
)
def test_v2_deserialize_rejects_wrong_types_without_coercion(
    path: tuple[str | int, ...],
    value: object,
) -> None:
    data = v2_data()
    parent = nested(data, *path[:-1])
    parent[path[-1]] = value  # type: ignore[index]

    with pytest.raises(TypeError):
        StateSerializer.deserialize(data)


@pytest.mark.parametrize("total_level", [0, 21])
def test_v2_deserialize_rejects_out_of_range_total_level(total_level: int) -> None:
    data = v2_data()
    nested(data, "state", "characters", 0)["totalLevel"] = total_level  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v2_deserialize_rejects_invalid_ability_value() -> None:
    data = v2_data()
    nested(data, "state", "characters", 0)["savingThrowProficiencies"] = [  # type: ignore[index]
        "STR"
    ]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v2_deserialize_rejects_duplicate_serialized_proficiencies() -> None:
    data = v2_data()
    nested(data, "state", "characters", 0)["savingThrowProficiencies"] = [  # type: ignore[index]
        "strength",
        "strength",
    ]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v2_deserialize_rejects_duplicate_character_ids() -> None:
    data = v2_data()
    characters = nested(data, "state", "characters")
    characters.append(deepcopy(characters[0]))  # type: ignore[attr-defined,index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_v2_deserialize_rejects_character_without_corresponding_creature() -> None:
    data = v2_data()
    nested(data, "state", "characters", 0)["id"] = "character_002"  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_deserialize_rejects_campaign_id_mismatch() -> None:
    data = v2_data()
    data["campaignId"] = "campaign_002"

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_deserialize_rejects_missing_schema_version() -> None:
    data = v2_data()
    del data["schemaVersion"]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


@pytest.mark.parametrize("missing_field", ["campaignId", "state"])
def test_deserialize_rejects_other_missing_root_fields(
    missing_field: str,
) -> None:
    data = v2_data()
    del data[missing_field]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_deserialize_rejects_duplicate_creature_ids() -> None:
    data = v2_data()
    creatures = nested(data, "state", "creatures")
    creatures.append(deepcopy(creatures[0]))  # type: ignore[attr-defined,index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


@pytest.mark.parametrize("score", [0, 31])
def test_deserialize_rejects_invalid_ability_scores(score: int) -> None:
    data = v2_data()
    nested(data, "state", "creatures", 0, "abilityScores")["strength"] = score  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


@pytest.mark.parametrize(
    ("current_hp", "max_hp"),
    [(-1, 28), (29, 28), (0, 0)],
)
def test_deserialize_rejects_invalid_hp(current_hp: int, max_hp: int) -> None:
    data = v2_data()
    creature = nested(data, "state", "creatures", 0)
    creature["currentHp"] = current_hp  # type: ignore[index]
    creature["maxHp"] = max_hp  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


@pytest.mark.parametrize("schema_version", [0, 3, -1])
def test_deserialize_rejects_unsupported_schema_version(
    schema_version: int,
) -> None:
    data = v2_data()
    data["schemaVersion"] = schema_version

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_deserialize_rejects_bool_schema_version() -> None:
    data = v2_data()
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


def test_serialize_rejects_mutated_invalid_creature_state() -> None:
    creature = creature_state()
    creature.current_hp = 29

    with pytest.raises(ValueError):
        StateSerializer.serialize(snapshot(creature))
