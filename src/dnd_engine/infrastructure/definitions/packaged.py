import json
import re
from importlib import resources
from importlib.resources.abc import Traversable
from typing import Any

from dnd_engine.domain.definitions.base import Definition
from dnd_engine.domain.definitions.item import ItemDefinition
from dnd_engine.domain.definitions.monster import MonsterDefinition
from dnd_engine.domain.definitions.weapon import WeaponDefinition
from dnd_engine.domain.services.definitions import (
    DefinitionNotFoundError,
    DefinitionTypeMismatchError,
    TDefinition,
)
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.domain.value_objects.damage_type import DamageType


DEFAULT_RESOURCES_PACKAGE = "dnd_engine.resources"

_ABILITY_SCORE_FIELDS = (
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
)
_MONSTER_FIELDS = frozenset(
    {"type", "id", "version", "name", "abilityScores", "armorClass"}
)
_ITEM_FIELDS = frozenset({"type", "id", "version", "name"})
_WEAPON_FIELDS = frozenset(
    {"type", "id", "version", "name", "damageDice", "damageType", "properties"}
)

# One resource path segment for ruleset_id/definition_id, matching the
# canonical lowercase snake_case Definition/Ruleset ID contract (§4.1, §4.6).
# Deliberately excludes "/", "\\", "." and any other character that could
# change directory-traversal meaning when joined into a resource path.
_CANONICAL_ID_SEGMENT = re.compile(r"^[a-z][a-z0-9_]*$")

# One resource path segment for ruleset_version (e.g. "5.1"): a single
# path component, not a path. Must not start with "." (rules out "." and
# ".." as a whole segment) and must not contain "/" or "\\".
_CANONICAL_VERSION_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class InvalidPackagedDefinitionError(Exception):
    """Raised when packaged Definition content is malformed or unsupported.

    Distinct from DefinitionNotFoundError: this signals infrastructure/content
    corruption (bad JSON, unknown type, wrong shape), not a legitimate missing
    reference.
    """


class PackagedDefinitionSource:
    """Production DefinitionSource backed by packaged ruleset JSON resources."""

    def __init__(self, *, resources_root: Traversable | None = None) -> None:
        self._resources_root = (
            resources_root
            if resources_root is not None
            else resources.files(DEFAULT_RESOURCES_PACKAGE)
        )

    def get_definition(
        self,
        *,
        ruleset_id: str,
        ruleset_version: str,
        definition_id: str,
        expected_type: type[TDefinition],
    ) -> TDefinition:
        payload = self._read_payload(ruleset_id, ruleset_version, definition_id)
        definition = _decode_definition(payload, definition_id)
        if not isinstance(definition, expected_type):
            raise DefinitionTypeMismatchError(
                f"Definition {definition_id!r} in ruleset {ruleset_id!r} "
                f"version {ruleset_version!r} is {type(definition).__name__}, "
                f"expected {expected_type.__name__}"
            )
        return definition

    def _read_payload(
        self,
        ruleset_id: str,
        ruleset_version: str,
        definition_id: str,
    ) -> dict[str, Any]:
        ruleset_root = self._resources_root.joinpath("rulesets")
        if not ruleset_root.is_dir():
            raise InvalidPackagedDefinitionError(
                "Packaged ruleset resource root is missing or not a "
                f"directory: {ruleset_root}"
            )

        _require_resource_segment(ruleset_id, _CANONICAL_ID_SEGMENT, "ruleset_id")
        _require_resource_segment(
            ruleset_version, _CANONICAL_VERSION_SEGMENT, "ruleset_version"
        )
        _require_resource_segment(
            definition_id, _CANONICAL_ID_SEGMENT, "definition_id"
        )

        resource = (
            ruleset_root.joinpath(ruleset_id)
            .joinpath(ruleset_version)
            .joinpath("definitions")
            .joinpath(f"{definition_id}.json")
        )

        if not resource.is_file():
            raise DefinitionNotFoundError(
                f"No Definition {definition_id!r} for ruleset {ruleset_id!r} "
                f"version {ruleset_version!r}"
            )

        text = resource.read_text(encoding="utf-8")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as error:
            raise InvalidPackagedDefinitionError(
                f"Malformed JSON for Definition {definition_id!r}: {error}"
            ) from error

        if type(payload) is not dict:
            raise InvalidPackagedDefinitionError(
                f"Definition {definition_id!r} payload must be a JSON object"
            )

        return payload


def _require_resource_segment(
    value: str,
    pattern: re.Pattern[str],
    field_name: str,
) -> str:
    """Reject any value that is not one canonical resource path segment.

    Must run before the value is ever passed to Traversable.joinpath():
    a value containing "..", "/", "\\", or an absolute-path prefix would
    otherwise let a caller escape the packaged rulesets/ resource root.
    A non-canonical identity cannot resolve to any packaged Definition, so
    this is a DefinitionNotFoundError, not a new exception type.
    """
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise DefinitionNotFoundError(
            f"{field_name} {value!r} is not a canonical resource identity "
            "segment"
        )
    return value


def _require_str(payload: dict[str, Any], key: str, definition_id: str) -> str:
    value = payload.get(key)
    if type(value) is not str:
        raise InvalidPackagedDefinitionError(
            f"Definition {definition_id!r} field {key!r} must be a string"
        )
    return value


def _require_int(payload: dict[str, Any], key: str, definition_id: str) -> int:
    value = payload.get(key)
    if type(value) is not int:
        raise InvalidPackagedDefinitionError(
            f"Definition {definition_id!r} field {key!r} must be an integer"
        )
    return value


def _require_matching_id(payload: dict[str, Any], definition_id: str) -> str:
    payload_id = _require_str(payload, "id", definition_id)
    if payload_id != definition_id:
        raise InvalidPackagedDefinitionError(
            f"Definition {definition_id!r} payload id {payload_id!r} does not "
            "match the requested definition_id"
        )
    return payload_id


def _require_ability_scores(payload: dict[str, Any], definition_id: str) -> AbilityScores:
    raw = payload.get("abilityScores")
    if type(raw) is not dict or set(raw) != set(_ABILITY_SCORE_FIELDS):
        raise InvalidPackagedDefinitionError(
            f"Definition {definition_id!r} field 'abilityScores' is malformed"
        )
    scores: dict[str, int] = {}
    for field_name in _ABILITY_SCORE_FIELDS:
        value = raw[field_name]
        if type(value) is not int:
            raise InvalidPackagedDefinitionError(
                f"Definition {definition_id!r} abilityScores.{field_name} "
                "must be an integer"
            )
        scores[field_name] = value
    try:
        return AbilityScores(**scores)
    except (TypeError, ValueError) as error:
        raise InvalidPackagedDefinitionError(
            f"Definition {definition_id!r} has invalid abilityScores: {error}"
        ) from error


def _decode_monster(payload: dict[str, Any], definition_id: str) -> MonsterDefinition:
    if set(payload) != _MONSTER_FIELDS:
        raise InvalidPackagedDefinitionError(
            f"Definition {definition_id!r} has unexpected monster fields"
        )
    payload_id = _require_matching_id(payload, definition_id)
    version = _require_int(payload, "version", definition_id)
    name = _require_str(payload, "name", definition_id)
    ability_scores = _require_ability_scores(payload, definition_id)
    armor_class = _require_int(payload, "armorClass", definition_id)
    try:
        return MonsterDefinition(
            id=payload_id,
            version=version,
            name=name,
            ability_scores=ability_scores,
            armor_class=armor_class,
        )
    except (TypeError, ValueError) as error:
        raise InvalidPackagedDefinitionError(
            f"Definition {definition_id!r} failed Domain validation: {error}"
        ) from error


def _decode_item(payload: dict[str, Any], definition_id: str) -> ItemDefinition:
    if set(payload) != _ITEM_FIELDS:
        raise InvalidPackagedDefinitionError(
            f"Definition {definition_id!r} has unexpected item fields"
        )
    payload_id = _require_matching_id(payload, definition_id)
    version = _require_int(payload, "version", definition_id)
    name = _require_str(payload, "name", definition_id)
    try:
        return ItemDefinition(id=payload_id, version=version, name=name)
    except (TypeError, ValueError) as error:
        raise InvalidPackagedDefinitionError(
            f"Definition {definition_id!r} failed Domain validation: {error}"
        ) from error


def _decode_weapon(payload: dict[str, Any], definition_id: str) -> WeaponDefinition:
    if set(payload) != _WEAPON_FIELDS:
        raise InvalidPackagedDefinitionError(
            f"Definition {definition_id!r} has unexpected weapon fields"
        )
    payload_id = _require_matching_id(payload, definition_id)
    version = _require_int(payload, "version", definition_id)
    name = _require_str(payload, "name", definition_id)
    damage_dice = _require_str(payload, "damageDice", definition_id)
    damage_type_raw = _require_str(payload, "damageType", definition_id)
    try:
        damage_type = DamageType(damage_type_raw)
    except ValueError as error:
        raise InvalidPackagedDefinitionError(
            f"Definition {definition_id!r} has invalid damageType "
            f"{damage_type_raw!r}"
        ) from error
    properties_raw = payload.get("properties")
    if type(properties_raw) is not list or not all(
        type(item) is str for item in properties_raw
    ):
        raise InvalidPackagedDefinitionError(
            f"Definition {definition_id!r} field 'properties' must be a list "
            "of strings"
        )
    try:
        return WeaponDefinition(
            id=payload_id,
            version=version,
            name=name,
            damage_dice=damage_dice,
            damage_type=damage_type,
            properties=tuple(properties_raw),
        )
    except (TypeError, ValueError) as error:
        raise InvalidPackagedDefinitionError(
            f"Definition {definition_id!r} failed Domain validation: {error}"
        ) from error


def _decode_definition(payload: dict[str, Any], definition_id: str) -> Definition:
    definition_type = payload.get("type")
    if type(definition_type) is not str:
        raise InvalidPackagedDefinitionError(
            f"Definition {definition_id!r} is missing a string 'type'"
        )

    if definition_type == "monster":
        return _decode_monster(payload, definition_id)
    if definition_type == "item":
        return _decode_item(payload, definition_id)
    if definition_type == "weapon":
        return _decode_weapon(payload, definition_id)

    raise InvalidPackagedDefinitionError(
        f"Definition {definition_id!r} has unknown type {definition_type!r}"
    )
