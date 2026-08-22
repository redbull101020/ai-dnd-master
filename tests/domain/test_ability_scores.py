from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.value_objects.ability_scores import AbilityScores


CANONICAL_FIELDS = (
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
)


def ability_scores(**overrides: int) -> AbilityScores:
    values = dict.fromkeys(CANONICAL_FIELDS, 10)
    values.update(overrides)
    return AbilityScores(**values)


def test_ability_scores_accept_valid_values() -> None:
    scores = AbilityScores(
        strength=8,
        dexterity=14,
        constitution=12,
        intelligence=16,
        wisdom=10,
        charisma=18,
    )

    assert scores.strength == 8
    assert scores.dexterity == 14
    assert scores.constitution == 12
    assert scores.intelligence == 16
    assert scores.wisdom == 10
    assert scores.charisma == 18


@pytest.mark.parametrize("score", [1, 30])
def test_ability_scores_accept_boundaries(score: int) -> None:
    scores = ability_scores(**dict.fromkeys(CANONICAL_FIELDS, score))

    assert all(getattr(scores, field) == score for field in CANONICAL_FIELDS)


@pytest.mark.parametrize("field", CANONICAL_FIELDS)
@pytest.mark.parametrize("score", [0, 31])
def test_ability_scores_reject_out_of_range_values(field: str, score: int) -> None:
    with pytest.raises(ValueError):
        ability_scores(**{field: score})


@pytest.mark.parametrize("field", CANONICAL_FIELDS)
@pytest.mark.parametrize("score", [10.5, True])
def test_ability_scores_reject_non_int_values(field: str, score: object) -> None:
    with pytest.raises(TypeError):
        ability_scores(**{field: score})  # type: ignore[arg-type]


def test_ability_scores_are_immutable() -> None:
    scores = ability_scores()

    with pytest.raises(FrozenInstanceError):
        scores.strength = 12  # type: ignore[misc]


def test_ability_scores_have_only_canonical_fields() -> None:
    assert tuple(field.name for field in fields(AbilityScores)) == CANONICAL_FIELDS
