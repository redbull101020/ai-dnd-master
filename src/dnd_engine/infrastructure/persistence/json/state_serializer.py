from collections.abc import Mapping

from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.ability_scores import AbilityScores


LEGACY_SCHEMA_VERSION = 1
SCHEMA_VERSION = 2

_ROOT_FIELDS = {"schemaVersion", "campaignId", "state"}
_V1_STATE_FIELDS = {"campaign", "creatures"}
_V2_STATE_FIELDS = {"campaign", "creatures", "characters"}
_CAMPAIGN_FIELDS = {"id", "rulesetId", "rulesetVersion"}
_CREATURE_FIELDS = {
    "id",
    "definitionId",
    "abilityScores",
    "currentHp",
    "maxHp",
}
_CHARACTER_FIELDS = {
    "id",
    "totalLevel",
    "savingThrowProficiencies",
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

        creatures = sorted(snapshot.creatures, key=lambda creature: creature.id)
        characters = sorted(snapshot.characters, key=lambda character: character.id)
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
            },
        }

    @staticmethod
    def deserialize(data: Mapping[str, object]) -> StateSnapshot:
        root = _require_mapping(data, "State snapshot")
        _require_exact_fields(root, _ROOT_FIELDS, "State snapshot")

        schema_version = _require_int(root["schemaVersion"], "schemaVersion")
        if schema_version not in {LEGACY_SCHEMA_VERSION, SCHEMA_VERSION}:
            raise ValueError(f"unsupported schemaVersion: {schema_version}")

        campaign_id = _require_str(root["campaignId"], "campaignId")
        state = _require_mapping(root["state"], "state")
        state_fields = (
            _V1_STATE_FIELDS
            if schema_version == LEGACY_SCHEMA_VERSION
            else _V2_STATE_FIELDS
        )
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
            StateSerializer._deserialize_creature(creature_data, index)
            for index, creature_data in enumerate(creatures_data)
        )
        if schema_version == LEGACY_SCHEMA_VERSION:
            characters: tuple[CharacterState, ...] = ()
        else:
            characters_data = state["characters"]
            if type(characters_data) is not list:
                raise TypeError("state.characters must be a list")
            characters = tuple(
                StateSerializer._deserialize_character(character_data, index)
                for index, character_data in enumerate(characters_data)
            )
        return StateSnapshot(
            campaign=campaign,
            creatures=creatures,
            characters=characters,
        )

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

    @staticmethod
    def _deserialize_character(data: object, index: int) -> CharacterState:
        character = _require_mapping(data, f"state.characters[{index}]")
        _require_exact_fields(character, _CHARACTER_FIELDS, "character")

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

        return CharacterState(
            id=_require_str(character["id"], f"state.characters[{index}].id"),
            total_level=total_level,
            saving_throw_proficiencies=frozenset(proficiencies),
        )
