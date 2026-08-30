from dataclasses import fields

import pytest

from dnd_engine.domain.state.combat import CombatState


def make_combat(**overrides: object) -> CombatState:
    values: dict[str, object] = {
        "id": "combat_001",
        "round": 1,
        "order": ("character_001", "monster_001"),
        "active_index": 0,
    }
    values.update(overrides)
    return CombatState(**values)  # type: ignore[arg-type]


def test_combat_state_has_exact_fields() -> None:
    assert tuple(field.name for field in fields(CombatState)) == (
        "id",
        "round",
        "order",
        "active_index",
    )


def test_active_creature_id_indexes_into_order() -> None:
    combat = make_combat(order=("a", "b", "c"), active_index=1)

    assert combat.active_creature_id == "b"


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("id", 1),
        ("round", "1"),
        ("round", True),
        ("order", ["character_001"]),
        ("active_index", "0"),
        ("active_index", True),
    ],
)
def test_rejects_wrong_runtime_types(field_name: str, invalid_value: object) -> None:
    with pytest.raises(TypeError):
        make_combat(**{field_name: invalid_value})


def test_rejects_non_string_order_entries() -> None:
    with pytest.raises(TypeError):
        make_combat(order=("character_001", 1))


def test_rejects_round_below_one() -> None:
    with pytest.raises(ValueError, match="round"):
        make_combat(round=0)


def test_rejects_empty_order() -> None:
    with pytest.raises(ValueError, match="order"):
        make_combat(order=())


def test_rejects_duplicate_order_entries() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        make_combat(order=("character_001", "character_001"))


@pytest.mark.parametrize("active_index", [-1, 2])
def test_rejects_out_of_range_active_index(active_index: int) -> None:
    with pytest.raises(ValueError, match="active_index"):
        make_combat(order=("a", "b"), active_index=active_index)
