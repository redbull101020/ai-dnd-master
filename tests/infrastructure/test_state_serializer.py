from copy import deepcopy

import pytest

from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.infrastructure.persistence.json.state_serializer import (
    StateSerializer,
)


CANONICAL_DATA: dict[str, object] = {
    "schemaVersion": 1,
    "campaignId": "campaign_001",
    "state": {
        "campaign": {
            "id": "campaign_001",
            "rulesetId": "dnd_5e",
            "rulesetVersion": "5.2.1",
        },
        "creatures": [
            {
                "id": "monster_001",
                "definitionId": "goblin",
                "abilityScores": {
                    "strength": 8,
                    "dexterity": 14,
                    "constitution": 10,
                    "intelligence": 10,
                    "wisdom": 8,
                    "charisma": 8,
                },
                "currentHp": 7,
                "maxHp": 7,
            }
        ],
    },
}


def campaign_state() -> CampaignState:
    return CampaignState("campaign_001", "dnd_5e", "5.2.1")


def creature_state(creature_id: str = "monster_001") -> CreatureState:
    return CreatureState(
        id=creature_id,
        definition_id="goblin",
        ability_scores=AbilityScores(8, 14, 10, 10, 8, 8),
        current_hp=7,
        max_hp=7,
    )


def snapshot(*creatures: CreatureState) -> StateSnapshot:
    return StateSnapshot(campaign_state(), tuple(creatures))


def state_data() -> dict[str, object]:
    return deepcopy(CANONICAL_DATA)


def nested(data: dict[str, object], *path: str | int) -> object:
    value: object = data
    for part in path:
        value = value[part]  # type: ignore[index]
    return value


def test_serialize_emits_exact_canonical_phase_1_mapping() -> None:
    serialized = StateSerializer.serialize(snapshot(creature_state()))

    assert serialized == CANONICAL_DATA
    assert serialized["schemaVersion"] == 1
    assert serialized["campaignId"] == "campaign_001"


def test_serialize_uses_canonical_camel_case_fields() -> None:
    serialized = StateSerializer.serialize(snapshot(creature_state()))
    state = serialized["state"]
    campaign = state["campaign"]  # type: ignore[index]
    creature = state["creatures"][0]  # type: ignore[index]

    assert set(campaign) == {"id", "rulesetId", "rulesetVersion"}
    assert set(creature) == {
        "id",
        "definitionId",
        "abilityScores",
        "currentHp",
        "maxHp",
    }


def test_serialize_supports_empty_creatures() -> None:
    serialized = StateSerializer.serialize(snapshot())

    assert serialized["state"]["creatures"] == []  # type: ignore[index]


def test_serialize_orders_multiple_creatures_by_id() -> None:
    serialized = StateSerializer.serialize(
        snapshot(creature_state("monster_002"), creature_state("monster_001"))
    )
    creatures = serialized["state"]["creatures"]  # type: ignore[index]

    assert [creature["id"] for creature in creatures] == [  # type: ignore[index]
        "monster_001",
        "monster_002",
    ]


def test_round_trip_reconstructs_equivalent_snapshot() -> None:
    original = snapshot(creature_state("monster_002"), creature_state("monster_001"))

    reconstructed = StateSerializer.deserialize(StateSerializer.serialize(original))

    assert reconstructed.campaign == original.campaign
    assert reconstructed.creatures == tuple(
        sorted(original.creatures, key=lambda creature: creature.id)
    )


def test_deserialize_accepts_empty_creatures() -> None:
    data = state_data()
    nested(data, "state")["creatures"] = []  # type: ignore[index]

    assert StateSerializer.deserialize(data).creatures == ()


def test_deserialize_rejects_missing_schema_version() -> None:
    data = state_data()
    del data["schemaVersion"]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


@pytest.mark.parametrize("missing_field", ["campaignId", "state"])
def test_deserialize_rejects_other_missing_root_fields(
    missing_field: str,
) -> None:
    data = state_data()
    del data[missing_field]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


@pytest.mark.parametrize("schema_version", [2, 0, -1])
def test_deserialize_rejects_unsupported_schema_version(
    schema_version: int,
) -> None:
    data = state_data()
    data["schemaVersion"] = schema_version

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_deserialize_rejects_bool_schema_version() -> None:
    data = state_data()
    data["schemaVersion"] = True

    with pytest.raises(TypeError):
        StateSerializer.deserialize(data)


@pytest.mark.parametrize(
    ("path", "field"),
    [
        ((), "revision"),
        (("state",), "world"),
        (("state", "campaign"), "metadata"),
        (("state", "creatures", 0), "conditions"),
        (("state", "creatures", 0, "abilityScores"), "luck"),
    ],
)
def test_deserialize_rejects_unknown_fields(
    path: tuple[str | int, ...],
    field: str,
) -> None:
    data = state_data()
    nested(data, *path)[field] = "unexpected"  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


@pytest.mark.parametrize(
    ("path", "field"),
    [
        (("state",), "creatures"),
        (("state", "campaign"), "rulesetVersion"),
        (("state", "creatures", 0), "definitionId"),
        (("state", "creatures", 0), "currentHp"),
        (("state", "creatures", 0, "abilityScores"), "wisdom"),
    ],
)
def test_deserialize_rejects_missing_required_nested_fields(
    path: tuple[str | int, ...],
    field: str,
) -> None:
    data = state_data()
    del nested(data, *path)[field]  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("campaignId",), None),
        (("state", "campaign", "rulesetId"), 5),
        (("state", "creatures"), ()),
        (("state", "creatures", 0, "id"), 1),
        (("state", "creatures", 0, "currentHp"), 7.0),
        (("state", "creatures", 0, "maxHp"), True),
        (("state", "creatures", 0, "abilityScores", "strength"), "8"),
    ],
)
def test_deserialize_rejects_wrong_types_without_coercion(
    path: tuple[str | int, ...],
    value: object,
) -> None:
    data = state_data()
    parent = nested(data, *path[:-1])
    parent[path[-1]] = value  # type: ignore[index]

    with pytest.raises(TypeError):
        StateSerializer.deserialize(data)


def test_deserialize_rejects_campaign_id_mismatch() -> None:
    data = state_data()
    data["campaignId"] = "campaign_002"

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_deserialize_rejects_duplicate_creature_ids() -> None:
    data = state_data()
    creatures = nested(data, "state", "creatures")
    creatures.append(deepcopy(creatures[0]))  # type: ignore[attr-defined,index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


@pytest.mark.parametrize("score", [0, 31])
def test_deserialize_rejects_invalid_ability_scores(score: int) -> None:
    data = state_data()
    nested(data, "state", "creatures", 0, "abilityScores")["strength"] = score  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


@pytest.mark.parametrize(
    ("current_hp", "max_hp"),
    [(-1, 7), (8, 7), (0, 0)],
)
def test_deserialize_rejects_invalid_hp(current_hp: int, max_hp: int) -> None:
    data = state_data()
    creature = nested(data, "state", "creatures", 0)
    creature["currentHp"] = current_hp  # type: ignore[index]
    creature["maxHp"] = max_hp  # type: ignore[index]

    with pytest.raises(ValueError):
        StateSerializer.deserialize(data)


def test_serialize_rejects_mutated_invalid_nested_state() -> None:
    creature = creature_state()
    creature.current_hp = 8

    with pytest.raises(ValueError):
        StateSerializer.serialize(snapshot(creature))
