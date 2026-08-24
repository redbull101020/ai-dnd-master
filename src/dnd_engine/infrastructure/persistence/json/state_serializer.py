from collections.abc import Mapping

from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability_scores import AbilityScores


SCHEMA_VERSION = 1

_ROOT_FIELDS = {"schemaVersion", "campaignId", "state"}
_STATE_FIELDS = {"campaign", "creatures"}
_CAMPAIGN_FIELDS = {"id", "rulesetId", "rulesetVersion"}
_CREATURE_FIELDS = {
    "id",
    "definitionId",
    "abilityScores",
    "currentHp",
    "maxHp",
}
_ABILITY_SCORE_FIELDS = {
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
}


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

        creatures = sorted(snapshot.creatures, key=lambda creature: creature.id)
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
            },
        }

    @staticmethod
    def deserialize(data: Mapping[str, object]) -> StateSnapshot:
        root = _require_mapping(data, "State snapshot")
        _require_exact_fields(root, _ROOT_FIELDS, "State snapshot")

        schema_version = _require_int(root["schemaVersion"], "schemaVersion")
        if schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schemaVersion: {schema_version}")

        campaign_id = _require_str(root["campaignId"], "campaignId")
        state = _require_mapping(root["state"], "state")
        _require_exact_fields(state, _STATE_FIELDS, "state")

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
            StateSerializer._deserialize_creature(creature_data, index)
            for index, creature_data in enumerate(creatures_data)
        )
        return StateSnapshot(campaign=campaign, creatures=creatures)

    @staticmethod
    def _deserialize_creature(data: object, index: int) -> CreatureState:
        creature = _require_mapping(data, f"state.creatures[{index}]")
        _require_exact_fields(creature, _CREATURE_FIELDS, "creature")

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
        return CreatureState(
            id=_require_str(creature["id"], "creature.id"),
            definition_id=_require_str(
                creature["definitionId"], "creature.definitionId"
            ),
            ability_scores=ability_scores,
            current_hp=_require_int(creature["currentHp"], "creature.currentHp"),
            max_hp=_require_int(creature["maxHp"], "creature.maxHp"),
        )
