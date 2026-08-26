import pytest

from dnd_engine.domain.rules.ability import ability_modifier
from dnd_engine.domain.rules.ability_check import (
    ability_modifier as ability_check_modifier,
)


@pytest.mark.parametrize(
    ("score", "expected"),
    [(1, -5), (8, -1), (9, -1), (10, 0), (11, 0), (12, 1), (20, 5), (30, 10)],
)
def test_ability_modifier_uses_canonical_formula(score: int, expected: int) -> None:
    assert ability_modifier(score) == expected


@pytest.mark.parametrize("score", [True, 1.0, "10", None])
def test_ability_modifier_rejects_non_exact_integer(score: object) -> None:
    with pytest.raises(TypeError):
        ability_modifier(score)  # type: ignore[arg-type]


def test_ability_modifier_adds_no_score_range() -> None:
    assert ability_modifier(0) == -5
    assert ability_modifier(31) == 10


def test_ability_check_import_path_reexports_shared_function() -> None:
    assert ability_check_modifier is ability_modifier
