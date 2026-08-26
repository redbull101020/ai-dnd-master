import pytest

from dnd_engine.domain.rules.proficiency import character_proficiency_bonus


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        (1, 2),
        (4, 2),
        (5, 3),
        (8, 3),
        (9, 4),
        (12, 4),
        (13, 5),
        (16, 5),
        (17, 6),
        (20, 6),
    ],
)
def test_character_proficiency_bonus_progression(
    level: int,
    expected: int,
) -> None:
    assert character_proficiency_bonus(level) == expected


@pytest.mark.parametrize("level", [True, 1.0, "1", None])
def test_character_proficiency_bonus_rejects_non_exact_integer(
    level: object,
) -> None:
    with pytest.raises(TypeError):
        character_proficiency_bonus(level)  # type: ignore[arg-type]


@pytest.mark.parametrize("level", [0, -1, 21])
def test_character_proficiency_bonus_rejects_levels_outside_character_range(
    level: int,
) -> None:
    with pytest.raises(ValueError):
        character_proficiency_bonus(level)
