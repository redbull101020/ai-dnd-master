from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.state.combat import CombatPosition, CombatState


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
        "positions",
        "action_spent",
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


def test_combat_position_has_exact_fields() -> None:
    assert tuple(field.name for field in fields(CombatPosition)) == (
        "creature_id",
        "x",
        "y",
    )


def test_combat_position_is_frozen() -> None:
    position = CombatPosition(creature_id="character_001", x=0, y=0)

    with pytest.raises(FrozenInstanceError):
        position.x = 1  # type: ignore[misc]


@pytest.mark.parametrize(
    ("x", "y"),
    [
        (0, 0),
        (5, 10),
        (-5, -10),
        (-1, 1),
    ],
)
def test_combat_position_accepts_positive_zero_and_negative_coordinates(
    x: int, y: int
) -> None:
    position = CombatPosition(creature_id="character_001", x=x, y=y)

    assert position.x == x
    assert position.y == y


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("creature_id", 1),
        ("x", "0"),
        ("y", "0"),
        ("x", True),
        ("y", False),
        ("x", 1.0),
        ("y", 1.0),
    ],
)
def test_combat_position_rejects_wrong_runtime_types(
    field_name: str, invalid_value: object
) -> None:
    values: dict[str, object] = {"creature_id": "character_001", "x": 0, "y": 0}
    values[field_name] = invalid_value

    with pytest.raises(TypeError):
        CombatPosition(**values)  # type: ignore[arg-type]


def test_combat_state_defaults_to_empty_positions() -> None:
    combat = make_combat()

    assert combat.positions == ()


def test_combat_state_rejects_non_tuple_positions() -> None:
    with pytest.raises(TypeError):
        make_combat(
            positions=[CombatPosition(creature_id="character_001", x=0, y=0)]
        )


def test_combat_state_rejects_wrong_position_member_type() -> None:
    with pytest.raises(TypeError):
        make_combat(positions=({"creature_id": "character_001", "x": 0, "y": 0},))


def test_combat_state_rejects_duplicate_position_creature_ids() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        make_combat(
            positions=(
                CombatPosition(creature_id="character_001", x=0, y=0),
                CombatPosition(creature_id="character_001", x=1, y=1),
            )
        )


def test_combat_state_rejects_positioned_creature_outside_order() -> None:
    with pytest.raises(ValueError, match="order"):
        make_combat(
            order=("character_001", "monster_001"),
            positions=(CombatPosition(creature_id="monster_002", x=0, y=0),),
        )


def test_combat_state_accepts_empty_positions() -> None:
    combat = make_combat(positions=())

    assert combat.positions == ()


def test_combat_state_accepts_partial_positions() -> None:
    combat = make_combat(
        order=("character_001", "monster_001"),
        positions=(CombatPosition(creature_id="character_001", x=0, y=0),),
    )

    assert combat.positions == (
        CombatPosition(creature_id="character_001", x=0, y=0),
    )


def test_combat_state_accepts_full_positions() -> None:
    combat = make_combat(
        order=("character_001", "monster_001"),
        positions=(
            CombatPosition(creature_id="character_001", x=0, y=0),
            CombatPosition(creature_id="monster_001", x=5, y=5),
        ),
    )

    assert len(combat.positions) == 2


def test_combat_state_defaults_action_spent_to_false() -> None:
    combat = make_combat()

    assert combat.action_spent is False


def test_combat_state_accepts_explicit_action_spent_true() -> None:
    combat = make_combat(action_spent=True)

    assert combat.action_spent is True


@pytest.mark.parametrize("invalid_value", [1, 0, "True", "", None])
def test_combat_state_rejects_non_bool_action_spent(invalid_value: object) -> None:
    with pytest.raises(TypeError, match="action_spent"):
        make_combat(action_spent=invalid_value)
