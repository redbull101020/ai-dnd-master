from dataclasses import fields

import pytest

from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.skill import Skill


CANONICAL_FIELDS = (
    "id",
    "total_level",
    "saving_throw_proficiencies",
    "skill_proficiencies",
    "weapon_proficiencies",
)


def character_state(
    *,
    total_level: int = 5,
    saving_throw_proficiencies: frozenset[Ability] = frozenset(
        {Ability.STRENGTH, Ability.CONSTITUTION}
    ),
    skill_proficiencies: frozenset[Skill] = frozenset(
        {Skill.ATHLETICS, Skill.PERCEPTION}
    ),
    weapon_proficiencies: frozenset[str] = frozenset({"dagger"}),
) -> CharacterState:
    return CharacterState(
        id="character_001",
        total_level=total_level,
        saving_throw_proficiencies=saving_throw_proficiencies,
        skill_proficiencies=skill_proficiencies,
        weapon_proficiencies=weapon_proficiencies,
    )


def test_character_state_has_exact_canonical_fields() -> None:
    assert tuple(field.name for field in fields(CharacterState)) == CANONICAL_FIELDS


def test_character_state_requires_explicit_skill_membership() -> None:
    with pytest.raises(TypeError):
        CharacterState(  # type: ignore[call-arg]
            id="character_001",
            total_level=5,
            saving_throw_proficiencies=frozenset(),
            weapon_proficiencies=frozenset(),
        )


def test_character_state_requires_explicit_weapon_membership() -> None:
    with pytest.raises(TypeError):
        CharacterState(  # type: ignore[call-arg]
            id="character_001",
            total_level=5,
            saving_throw_proficiencies=frozenset(),
            skill_proficiencies=frozenset(),
        )


def test_character_state_accepts_canonical_values() -> None:
    character = character_state()

    assert character.id == "character_001"
    assert character.total_level == 5
    assert character.saving_throw_proficiencies == frozenset(
        {Ability.STRENGTH, Ability.CONSTITUTION}
    )
    assert character.skill_proficiencies == frozenset(
        {Skill.ATHLETICS, Skill.PERCEPTION}
    )
    assert character.weapon_proficiencies == frozenset({"dagger"})


@pytest.mark.parametrize("total_level", [True, 5.0, "5", None])
def test_character_state_rejects_non_exact_int_total_level(
    total_level: object,
) -> None:
    with pytest.raises(TypeError):
        character_state(total_level=total_level)  # type: ignore[arg-type]


@pytest.mark.parametrize("total_level", [0, -1, 21, 100])
def test_character_state_rejects_out_of_range_total_level(
    total_level: int,
) -> None:
    with pytest.raises(ValueError):
        character_state(total_level=total_level)


@pytest.mark.parametrize(
    "proficiencies",
    [
        {Ability.STRENGTH},
        (Ability.STRENGTH,),
        [Ability.STRENGTH],
    ],
)
def test_character_state_rejects_non_frozenset_membership(
    proficiencies: object,
) -> None:
    with pytest.raises(TypeError):
        character_state(  # type: ignore[arg-type]
            saving_throw_proficiencies=proficiencies,
        )


@pytest.mark.parametrize("value", ["strength", 1, None])
def test_character_state_rejects_non_ability_members(value: object) -> None:
    with pytest.raises(TypeError):
        character_state(
            saving_throw_proficiencies=frozenset({value}),  # type: ignore[arg-type]
        )


def test_character_state_accepts_empty_membership() -> None:
    character = character_state(
        saving_throw_proficiencies=frozenset(),
        skill_proficiencies=frozenset(),
        weapon_proficiencies=frozenset(),
    )

    assert character.saving_throw_proficiencies == frozenset()
    assert character.skill_proficiencies == frozenset()
    assert character.weapon_proficiencies == frozenset()


def test_character_state_does_not_limit_effective_membership_count() -> None:
    all_abilities = frozenset(Ability)

    assert (
        character_state(saving_throw_proficiencies=all_abilities)
        .saving_throw_proficiencies
        == all_abilities
    )


@pytest.mark.parametrize(
    "proficiencies",
    [
        {Skill.ATHLETICS},
        (Skill.ATHLETICS,),
        [Skill.ATHLETICS],
    ],
)
def test_character_state_rejects_non_frozenset_skill_membership(
    proficiencies: object,
) -> None:
    with pytest.raises(TypeError):
        character_state(  # type: ignore[arg-type]
            skill_proficiencies=proficiencies,
        )


@pytest.mark.parametrize("value", ["athletics", 1, None])
def test_character_state_rejects_non_skill_members(value: object) -> None:
    with pytest.raises(TypeError):
        character_state(
            skill_proficiencies=frozenset({value}),  # type: ignore[arg-type]
        )


def test_character_state_does_not_limit_skill_membership_count() -> None:
    all_skills = frozenset(Skill)

    assert (
        character_state(skill_proficiencies=all_skills).skill_proficiencies
        == all_skills
    )


@pytest.mark.parametrize(
    "proficiencies",
    [
        {"dagger"},
        ("dagger",),
        ["dagger"],
    ],
)
def test_character_state_rejects_non_frozenset_weapon_membership(
    proficiencies: object,
) -> None:
    with pytest.raises(TypeError):
        character_state(  # type: ignore[arg-type]
            weapon_proficiencies=proficiencies,
        )


@pytest.mark.parametrize("value", [1, True, None, Ability.STRENGTH])
def test_character_state_rejects_non_string_weapon_members(value: object) -> None:
    with pytest.raises(TypeError):
        character_state(
            weapon_proficiencies=frozenset({value}),  # type: ignore[arg-type]
        )


def test_character_state_does_not_limit_weapon_membership_count() -> None:
    proficiencies = frozenset({"dagger", "longsword", "shortbow"})

    assert (
        character_state(weapon_proficiencies=proficiencies).weapon_proficiencies
        == proficiencies
    )
