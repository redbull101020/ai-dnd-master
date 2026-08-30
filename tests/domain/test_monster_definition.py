from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.definitions.base import Definition
from dnd_engine.domain.definitions.monster import MonsterDefinition
from dnd_engine.domain.definitions.monster_attack import MonsterAttackDefinition
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.domain.value_objects.damage_type import DamageType


CANONICAL_FIELDS = (
    "id",
    "version",
    "name",
    "ability_scores",
    "armor_class",
    "attacks",
)


def scimitar(*, action_id: str = "scimitar") -> MonsterAttackDefinition:
    return MonsterAttackDefinition(
        action_id=action_id,
        name="Scimitar",
        attack_bonus=4,
        damage_dice="1d6",
        damage_modifier=2,
        damage_type=DamageType.SLASHING,
    )


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
        armor_class=15,
    )


def test_monster_definition_accepts_canonical_fields() -> None:
    monster = goblin()

    assert monster.id == "goblin"
    assert monster.version == 1
    assert monster.name == "Goblin"
    assert monster.ability_scores.dexterity == 14
    assert monster.armor_class == 15


def test_monster_definition_is_a_definition() -> None:
    assert isinstance(goblin(), Definition)


def test_monster_definition_uses_ability_scores() -> None:
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
            armor_class=15,
            current_hp=7,
        )


def test_monster_definition_armor_class_is_exact_int() -> None:
    monster = goblin()

    assert type(monster.armor_class) is int


def test_monster_definition_rejects_bool_armor_class() -> None:
    with pytest.raises(TypeError):
        MonsterDefinition(
            id="goblin",
            version=1,
            name="Goblin",
            ability_scores=goblin().ability_scores,
            armor_class=True,  # type: ignore[arg-type]
        )


def test_monster_definition_rejects_non_int_armor_class() -> None:
    with pytest.raises(TypeError):
        MonsterDefinition(
            id="goblin",
            version=1,
            name="Goblin",
            ability_scores=goblin().ability_scores,
            armor_class="15",  # type: ignore[arg-type]
        )


def test_monster_definition_attacks_default_to_empty_tuple() -> None:
    assert goblin().attacks == ()


def test_monster_definition_accepts_one_attack() -> None:
    monster = MonsterDefinition(
        id="goblin",
        version=1,
        name="Goblin",
        ability_scores=goblin().ability_scores,
        armor_class=15,
        attacks=(scimitar(),),
    )

    assert monster.attacks == (scimitar(),)


def test_monster_definition_rejects_non_tuple_attacks() -> None:
    with pytest.raises(TypeError, match="attacks"):
        MonsterDefinition(
            id="goblin",
            version=1,
            name="Goblin",
            ability_scores=goblin().ability_scores,
            armor_class=15,
            attacks=[scimitar()],  # type: ignore[arg-type]
        )


def test_monster_definition_rejects_non_monster_attack_elements() -> None:
    with pytest.raises(TypeError, match="attacks"):
        MonsterDefinition(
            id="goblin",
            version=1,
            name="Goblin",
            ability_scores=goblin().ability_scores,
            armor_class=15,
            attacks=(object(),),  # type: ignore[arg-type]
        )


def test_monster_definition_rejects_duplicate_action_id() -> None:
    with pytest.raises(ValueError, match="action_id"):
        MonsterDefinition(
            id="goblin",
            version=1,
            name="Goblin",
            ability_scores=goblin().ability_scores,
            armor_class=15,
            attacks=(scimitar(), scimitar()),
        )


def test_monster_definition_allows_multiple_distinct_action_ids() -> None:
    monster = MonsterDefinition(
        id="goblin",
        version=1,
        name="Goblin",
        ability_scores=goblin().ability_scores,
        armor_class=15,
        attacks=(scimitar(), scimitar(action_id="bite")),
    )

    assert len(monster.attacks) == 2
