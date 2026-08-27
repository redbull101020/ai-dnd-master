import json
from pathlib import Path

import pytest

from dnd_engine.domain.definitions.item import ItemDefinition
from dnd_engine.domain.definitions.monster import MonsterDefinition
from dnd_engine.domain.definitions.weapon import WeaponDefinition
from dnd_engine.domain.services.definitions import (
    DefinitionNotFoundError,
    DefinitionTypeMismatchError,
)
from dnd_engine.infrastructure.definitions.packaged import (
    InvalidPackagedDefinitionError,
    PackagedDefinitionSource,
)


GOBLIN_PAYLOAD: dict[str, object] = {
    "type": "monster",
    "id": "goblin",
    "version": 1,
    "name": "Goblin",
    "abilityScores": {
        "strength": 8,
        "dexterity": 14,
        "constitution": 10,
        "intelligence": 10,
        "wisdom": 8,
        "charisma": 8,
    },
    "armorClass": 15,
}


def write_definition(
    root: Path,
    *,
    ruleset_id: str = "dnd_5e",
    ruleset_version: str = "5.1",
    definition_id: str = "goblin",
    payload: object = None,
    raw_text: str | None = None,
) -> None:
    directory = root / "rulesets" / ruleset_id / ruleset_version / "definitions"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{definition_id}.json"
    if raw_text is not None:
        path.write_text(raw_text, encoding="utf-8")
        return
    path.write_text(json.dumps(payload if payload is not None else GOBLIN_PAYLOAD), encoding="utf-8")


def test_production_default_reads_packaged_goblin() -> None:
    source = PackagedDefinitionSource()

    monster = source.get_definition(
        ruleset_id="dnd_5e",
        ruleset_version="5.1",
        definition_id="goblin",
        expected_type=MonsterDefinition,
    )

    assert type(monster) is MonsterDefinition
    assert monster.id == "goblin"
    assert monster.version == 1
    assert monster.name == "Goblin"
    assert monster.armor_class == 15
    assert monster.ability_scores.strength == 8
    assert monster.ability_scores.dexterity == 14
    assert monster.ability_scores.constitution == 10
    assert monster.ability_scores.intelligence == 10
    assert monster.ability_scores.wisdom == 8
    assert monster.ability_scores.charisma == 8


def test_lookup_is_scoped_to_requested_ruleset_and_version(tmp_path: Path) -> None:
    write_definition(tmp_path, ruleset_version="5.1")
    source = PackagedDefinitionSource(resources_root=tmp_path)

    with pytest.raises(DefinitionNotFoundError):
        source.get_definition(
            ruleset_id="dnd_5e",
            ruleset_version="9.9",
            definition_id="goblin",
            expected_type=MonsterDefinition,
        )

    with pytest.raises(DefinitionNotFoundError):
        source.get_definition(
            ruleset_id="other_ruleset",
            ruleset_version="5.1",
            definition_id="goblin",
            expected_type=MonsterDefinition,
        )


def test_missing_definition_raises_not_found(tmp_path: Path) -> None:
    # A valid packaged root/scope with the specific Definition file absent
    # is an ordinary miss, distinct from a broken/missing resource root.
    write_definition(tmp_path)
    source = PackagedDefinitionSource(resources_root=tmp_path)

    with pytest.raises(DefinitionNotFoundError):
        source.get_definition(
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
            definition_id="does_not_exist",
            expected_type=MonsterDefinition,
        )


def test_wrong_type_raises_type_mismatch_not_not_found(tmp_path: Path) -> None:
    write_definition(
        tmp_path,
        definition_id="torch",
        payload={"type": "item", "id": "torch", "version": 1, "name": "Torch"},
    )
    source = PackagedDefinitionSource(resources_root=tmp_path)

    with pytest.raises(DefinitionTypeMismatchError):
        source.get_definition(
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
            definition_id="torch",
            expected_type=MonsterDefinition,
        )


def test_wrong_type_allows_isinstance_subtype_relation(tmp_path: Path) -> None:
    write_definition(
        tmp_path,
        definition_id="dagger",
        payload={
            "type": "weapon",
            "id": "dagger",
            "version": 1,
            "name": "Dagger",
            "damageDice": "1d4",
            "damageType": "piercing",
            "properties": ["finesse", "light", "thrown"],
        },
    )
    source = PackagedDefinitionSource(resources_root=tmp_path)

    weapon = source.get_definition(
        ruleset_id="dnd_5e",
        ruleset_version="5.1",
        definition_id="dagger",
        expected_type=ItemDefinition,
    )

    assert type(weapon) is WeaponDefinition
    assert weapon.damage_type.value == "piercing"
    assert weapon.properties == ("finesse", "light", "thrown")


def test_item_definition_decodes(tmp_path: Path) -> None:
    write_definition(
        tmp_path,
        definition_id="torch",
        payload={"type": "item", "id": "torch", "version": 1, "name": "Torch"},
    )
    source = PackagedDefinitionSource(resources_root=tmp_path)

    item = source.get_definition(
        ruleset_id="dnd_5e",
        ruleset_version="5.1",
        definition_id="torch",
        expected_type=ItemDefinition,
    )

    assert type(item) is ItemDefinition
    assert item.name == "Torch"


def test_unknown_definition_type_raises_invalid_packaged(tmp_path: Path) -> None:
    write_definition(
        tmp_path,
        definition_id="mystery",
        payload={"type": "spell", "id": "mystery", "version": 1, "name": "Mystery"},
    )
    source = PackagedDefinitionSource(resources_root=tmp_path)

    with pytest.raises(InvalidPackagedDefinitionError):
        source.get_definition(
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
            definition_id="mystery",
            expected_type=MonsterDefinition,
        )


def test_missing_required_field_raises_invalid_packaged(tmp_path: Path) -> None:
    payload = dict(GOBLIN_PAYLOAD)
    del payload["armorClass"]
    write_definition(tmp_path, payload=payload)
    source = PackagedDefinitionSource(resources_root=tmp_path)

    with pytest.raises(InvalidPackagedDefinitionError):
        source.get_definition(
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
            definition_id="goblin",
            expected_type=MonsterDefinition,
        )


def test_unknown_field_raises_invalid_packaged(tmp_path: Path) -> None:
    payload = dict(GOBLIN_PAYLOAD)
    payload["challengeRating"] = "1/4"
    write_definition(tmp_path, payload=payload)
    source = PackagedDefinitionSource(resources_root=tmp_path)

    with pytest.raises(InvalidPackagedDefinitionError):
        source.get_definition(
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
            definition_id="goblin",
            expected_type=MonsterDefinition,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("armorClass", "15"),
        ("armorClass", True),
        ("version", "1"),
        ("name", 5),
    ],
)
def test_wrong_primitive_type_raises_invalid_packaged(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    payload = dict(GOBLIN_PAYLOAD)
    payload[field] = value
    write_definition(tmp_path, payload=payload)
    source = PackagedDefinitionSource(resources_root=tmp_path)

    with pytest.raises(InvalidPackagedDefinitionError):
        source.get_definition(
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
            definition_id="goblin",
            expected_type=MonsterDefinition,
        )


@pytest.mark.parametrize(
    "ability_scores",
    [
        {"strength": 8, "dexterity": 14, "constitution": 10, "intelligence": 10, "wisdom": 8},
        {
            "strength": 8,
            "dexterity": 14,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 8,
            "charisma": "8",
        },
        "not-a-mapping",
    ],
)
def test_malformed_ability_scores_raises_invalid_packaged(
    tmp_path: Path,
    ability_scores: object,
) -> None:
    payload = dict(GOBLIN_PAYLOAD)
    payload["abilityScores"] = ability_scores
    write_definition(tmp_path, payload=payload)
    source = PackagedDefinitionSource(resources_root=tmp_path)

    with pytest.raises(InvalidPackagedDefinitionError):
        source.get_definition(
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
            definition_id="goblin",
            expected_type=MonsterDefinition,
        )


def test_intrinsic_domain_invariant_violation_raises_invalid_packaged(
    tmp_path: Path,
) -> None:
    payload = dict(GOBLIN_PAYLOAD)
    payload["abilityScores"] = {
        "strength": 8,
        "dexterity": 14,
        "constitution": 10,
        "intelligence": 10,
        "wisdom": 8,
        "charisma": 99,
    }
    write_definition(tmp_path, payload=payload)
    source = PackagedDefinitionSource(resources_root=tmp_path)

    with pytest.raises(InvalidPackagedDefinitionError):
        source.get_definition(
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
            definition_id="goblin",
            expected_type=MonsterDefinition,
        )


def test_requested_id_mismatch_raises_invalid_packaged_not_not_found(
    tmp_path: Path,
) -> None:
    payload = dict(GOBLIN_PAYLOAD)
    payload["id"] = "hobgoblin"
    write_definition(tmp_path, payload=payload)
    source = PackagedDefinitionSource(resources_root=tmp_path)

    with pytest.raises(InvalidPackagedDefinitionError):
        source.get_definition(
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
            definition_id="goblin",
            expected_type=MonsterDefinition,
        )


def test_malformed_json_raises_invalid_packaged_not_not_found(tmp_path: Path) -> None:
    write_definition(tmp_path, raw_text="{not valid json")
    source = PackagedDefinitionSource(resources_root=tmp_path)

    with pytest.raises(InvalidPackagedDefinitionError):
        source.get_definition(
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
            definition_id="goblin",
            expected_type=MonsterDefinition,
        )


def test_non_object_json_root_raises_invalid_packaged(tmp_path: Path) -> None:
    write_definition(tmp_path, raw_text="[1, 2, 3]")
    source = PackagedDefinitionSource(resources_root=tmp_path)

    with pytest.raises(InvalidPackagedDefinitionError):
        source.get_definition(
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
            definition_id="goblin",
            expected_type=MonsterDefinition,
        )


def test_content_corruption_is_distinct_from_missing(tmp_path: Path) -> None:
    write_definition(tmp_path, raw_text="not json at all")
    source = PackagedDefinitionSource(resources_root=tmp_path)

    with pytest.raises(InvalidPackagedDefinitionError):
        source.get_definition(
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
            definition_id="goblin",
            expected_type=MonsterDefinition,
        )

    with pytest.raises(DefinitionNotFoundError):
        source.get_definition(
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
            definition_id="totally_absent",
            expected_type=MonsterDefinition,
        )


@pytest.mark.parametrize(
    "definition_id",
    ["../goblin", "foo/bar", "foo\\bar", "..", "", "Goblin", "goblin.json"],
)
def test_traversal_definition_id_raises_not_found(
    tmp_path: Path,
    definition_id: str,
) -> None:
    write_definition(tmp_path)
    source = PackagedDefinitionSource(resources_root=tmp_path)

    with pytest.raises(DefinitionNotFoundError):
        source.get_definition(
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
            definition_id=definition_id,
            expected_type=MonsterDefinition,
        )


@pytest.mark.parametrize(
    "ruleset_id",
    ["../dnd_5e", "foo/bar", "foo\\bar", "..", "", "Dnd_5e"],
)
def test_traversal_ruleset_id_raises_not_found(
    tmp_path: Path,
    ruleset_id: str,
) -> None:
    write_definition(tmp_path)
    source = PackagedDefinitionSource(resources_root=tmp_path)

    with pytest.raises(DefinitionNotFoundError):
        source.get_definition(
            ruleset_id=ruleset_id,
            ruleset_version="5.1",
            definition_id="goblin",
            expected_type=MonsterDefinition,
        )


@pytest.mark.parametrize(
    "ruleset_version",
    ["../5.1", "5.1/other", "5.1\\other", "..", ".", "", "/5.1"],
)
def test_traversal_ruleset_version_raises_not_found(
    tmp_path: Path,
    ruleset_version: str,
) -> None:
    write_definition(tmp_path)
    source = PackagedDefinitionSource(resources_root=tmp_path)

    with pytest.raises(DefinitionNotFoundError):
        source.get_definition(
            ruleset_id="dnd_5e",
            ruleset_version=ruleset_version,
            definition_id="goblin",
            expected_type=MonsterDefinition,
        )


def test_traversal_definition_id_cannot_read_fixture_outside_definitions_dir(
    tmp_path: Path,
) -> None:
    write_definition(tmp_path)

    # Adversarial fixture sitting one level above `definitions/`, i.e.
    # exactly where `definitions/../secret.json` would resolve to. If the
    # traversal guard were missing, `definition_id="../secret"` would read
    # this file successfully and return a real MonsterDefinition.
    secret_path = tmp_path / "rulesets" / "dnd_5e" / "5.1" / "secret.json"
    secret_path.write_text(json.dumps(GOBLIN_PAYLOAD), encoding="utf-8")
    assert secret_path.is_file()

    source = PackagedDefinitionSource(resources_root=tmp_path)

    with pytest.raises(DefinitionNotFoundError):
        source.get_definition(
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
            definition_id="../secret",
            expected_type=MonsterDefinition,
        )


def test_missing_packaged_rulesets_root_raises_invalid_packaged(
    tmp_path: Path,
) -> None:
    # `tmp_path` itself has no "rulesets" subdirectory at all: this is a
    # broken/incomplete packaged resource root, not an ordinary missing
    # Definition.
    source = PackagedDefinitionSource(resources_root=tmp_path)

    with pytest.raises(InvalidPackagedDefinitionError):
        source.get_definition(
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
            definition_id="goblin",
            expected_type=MonsterDefinition,
        )


def test_rulesets_root_as_file_not_directory_raises_invalid_packaged(
    tmp_path: Path,
) -> None:
    (tmp_path / "rulesets").write_text("not a directory", encoding="utf-8")
    source = PackagedDefinitionSource(resources_root=tmp_path)

    with pytest.raises(InvalidPackagedDefinitionError):
        source.get_definition(
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
            definition_id="goblin",
            expected_type=MonsterDefinition,
        )


def test_unsupported_scope_under_valid_root_remains_not_found(
    tmp_path: Path,
) -> None:
    # Same semantics as before: a valid packaged rulesets root with an
    # unsupported (but canonically-shaped) ruleset/version scope is an
    # ordinary DefinitionNotFoundError, not packaged-root corruption.
    write_definition(tmp_path)
    source = PackagedDefinitionSource(resources_root=tmp_path)

    with pytest.raises(DefinitionNotFoundError):
        source.get_definition(
            ruleset_id="dnd_5e",
            ruleset_version="9.9",
            definition_id="goblin",
            expected_type=MonsterDefinition,
        )
