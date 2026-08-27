from copy import deepcopy

import pytest

from dnd_engine.domain.rules.armor_class import unarmored_character_armor_class
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.value_objects.ability_scores import AbilityScores


def creature_with_dexterity(dexterity: int) -> CreatureState:
    return CreatureState(
        id="character_001",
        definition_id="human_fighter",
        ability_scores=AbilityScores(
            strength=10,
            dexterity=dexterity,
            constitution=10,
            intelligence=10,
            wisdom=10,
            charisma=10,
        ),
        current_hp=10,
        max_hp=10,
    )


@pytest.mark.parametrize(
    ("dexterity", "expected_armor_class"),
    [
        (10, 10),
        (14, 12),
        (8, 9),
        (9, 9),
    ],
)
def test_unarmored_character_armor_class_uses_shared_dexterity_modifier(
    dexterity: int,
    expected_armor_class: int,
) -> None:
    creature = creature_with_dexterity(dexterity)

    assert unarmored_character_armor_class(creature) == expected_armor_class


def test_unarmored_character_armor_class_requires_only_creature_state() -> None:
    creature = creature_with_dexterity(12)

    armor_class = unarmored_character_armor_class(creature)

    assert armor_class == 11
    assert type(armor_class) is int


def test_unarmored_character_armor_class_does_not_mutate_creature() -> None:
    creature = creature_with_dexterity(16)
    original = deepcopy(creature)

    unarmored_character_armor_class(creature)

    assert creature == original
