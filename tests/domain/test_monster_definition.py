from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.definitions.base import Definition
from dnd_engine.domain.definitions.monster import MonsterDefinition
from dnd_engine.domain.value_objects.ability_scores import AbilityScores


CANONICAL_FIELDS = ("id", "version", "name", "ability_scores")


def goblin() -> MonsterDefinition:
    return MonsterDefinition(
        id="goblin",
        version=1,
        name="Goblin",
        ability_scores=AbilityScores(
            strength=8,
            dexterity=14,
            constitution=10,
            intelligence=10,
            wisdom=8,
            charisma=8,
        ),
    )


def test_monster_definition_accepts_canonical_fields() -> None:
    monster = goblin()

    assert monster.id == "goblin"
    assert monster.version == 1
    assert monster.name == "Goblin"
    assert monster.ability_scores.dexterity == 14


def test_monster_definition_is_a_definition() -> None:
    assert isinstance(goblin(), Definition)


def test_monster_definition_uses_ability_scores() -> None:
    ability_scores_field = next(
        field for field in fields(MonsterDefinition) if field.name == "ability_scores"
    )

    assert ability_scores_field.type is AbilityScores
    assert isinstance(goblin().ability_scores, AbilityScores)


def test_monster_definition_is_immutable() -> None:
    monster = goblin()

    with pytest.raises(FrozenInstanceError):
        monster.name = "Goblin Boss"  # type: ignore[misc]


def test_monster_definition_embeds_immutable_ability_scores() -> None:
    monster = goblin()

    with pytest.raises(FrozenInstanceError):
        monster.ability_scores.dexterity = 12  # type: ignore[misc]


def test_monster_definition_has_only_canonical_fields() -> None:
    assert tuple(field.name for field in fields(MonsterDefinition)) == CANONICAL_FIELDS


def test_monster_definition_does_not_accept_runtime_fields() -> None:
    with pytest.raises(TypeError):
        MonsterDefinition(  # type: ignore[call-arg]
            id="goblin",
            version=1,
            name="Goblin",
            ability_scores=goblin().ability_scores,
            current_hp=7,
        )
