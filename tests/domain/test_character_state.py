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
    "death_save_successes",
    "death_save_failures",
    "death_save_stable",
    "dead",
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
    death_save_successes: int = 0,
    death_save_failures: int = 0,
    death_save_stable: bool = False,
    dead: bool = False,
) -> CharacterState:
    return CharacterState(
        id="character_001",
        total_level=total_level,
        saving_throw_proficiencies=saving_throw_proficiencies,
        skill_proficiencies=skill_proficiencies,
        weapon_proficiencies=weapon_proficiencies,
        death_save_successes=death_save_successes,
        death_save_failures=death_save_failures,
        death_save_stable=death_save_stable,
        dead=dead,
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
    assert character.death_save_successes == 0
    assert character.death_save_failures == 0
    assert character.death_save_stable is False
    assert character.dead is False


@pytest.mark.parametrize("death_save_successes", [0, 2])
def test_character_state_accepts_death_save_success_boundaries(
    death_save_successes: int,
) -> None:
    assert (
        character_state(death_save_successes=death_save_successes)
        .death_save_successes
        == death_save_successes
    )


@pytest.mark.parametrize("death_save_failures", [0, 3])
def test_character_state_accepts_death_save_failure_boundaries(
    death_save_failures: int,
) -> None:
    character = character_state(
        death_save_failures=death_save_failures,
        dead=death_save_failures == 3,
    )

    assert character.death_save_failures == death_save_failures


@pytest.mark.parametrize("field_name", ["death_save_successes", "death_save_failures"])
def test_character_state_rejects_bool_death_save_counter(field_name: str) -> None:
    with pytest.raises(TypeError):
        character_state(**{field_name: True})  # type: ignore[arg-type]


@pytest.mark.parametrize("death_save_successes", [-1, 3])
def test_character_state_rejects_out_of_range_death_save_successes(
    death_save_successes: int,
) -> None:
    with pytest.raises(ValueError):
        character_state(death_save_successes=death_save_successes)


@pytest.mark.parametrize("death_save_failures", [-1, 4])
def test_character_state_rejects_out_of_range_death_save_failures(
    death_save_failures: int,
) -> None:
    with pytest.raises(ValueError):
        character_state(death_save_failures=death_save_failures)


@pytest.mark.parametrize("field_name", ["death_save_stable", "dead"])
@pytest.mark.parametrize("value", [0, 1, "false", None])
def test_character_state_rejects_non_bool_lifecycle_flag(
    field_name: str,
    value: object,
) -> None:
    with pytest.raises(TypeError):
        character_state(**{field_name: value})  # type: ignore[arg-type]


def test_character_state_rejects_stable_and_dead() -> None:
    with pytest.raises(ValueError):
        character_state(death_save_stable=True, dead=True)


@pytest.mark.parametrize(
    ("death_save_successes", "death_save_failures"),
    [(1, 0), (0, 1)],
)
def test_character_state_rejects_stable_with_nonzero_counter(
    death_save_successes: int,
    death_save_failures: int,
) -> None:
    with pytest.raises(ValueError):
        character_state(
            death_save_successes=death_save_successes,
            death_save_failures=death_save_failures,
            death_save_stable=True,
        )


def test_character_state_requires_dead_at_three_failures() -> None:
    with pytest.raises(ValueError):
        character_state(death_save_failures=3)


@pytest.mark.parametrize("death_save_failures", [0, 1, 2])
def test_character_state_allows_dead_with_fewer_than_three_failures(
    death_save_failures: int,
) -> None:
    character = character_state(
        death_save_failures=death_save_failures,
        dead=True,
    )

    assert character.dead is True
    assert character.death_save_failures == death_save_failures


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
