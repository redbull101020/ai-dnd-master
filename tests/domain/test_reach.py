import pytest

from dnd_engine.domain.rules.reach import (
    DND_5E_FIRST_CONSUMER_MELEE_REACH_FEET,
    is_within_melee_reach,
)
from dnd_engine.domain.state.combat import CombatPosition


def make_position(*, creature_id: str, x: int, y: int) -> CombatPosition:
    return CombatPosition(creature_id=creature_id, x=x, y=y)


def test_dnd_5e_melee_reach_constant_is_five_feet() -> None:
    assert DND_5E_FIRST_CONSUMER_MELEE_REACH_FEET == 5


@pytest.mark.parametrize(
    ("actor_xy", "target_xy", "expected"),
    [
        ((0, 0), (3, 4), True),
        ((0, 0), (5, 0), True),
        ((0, 0), (0, 5), True),
        ((0, 0), (4, 4), False),
        ((0, 0), (6, 0), False),
        ((-3, -4), (0, 0), True),
        ((-5, 0), (0, 0), True),
        ((-6, 0), (0, 0), False),
        ((2, 2), (2, 2), True),
    ],
)
def test_is_within_melee_reach_uses_squared_integer_distance(
    actor_xy: tuple[int, int],
    target_xy: tuple[int, int],
    expected: bool,
) -> None:
    actor = make_position(creature_id="character_001", x=actor_xy[0], y=actor_xy[1])
    target = make_position(creature_id="monster_001", x=target_xy[0], y=target_xy[1])

    result = is_within_melee_reach(
        actor, target, effective_reach=DND_5E_FIRST_CONSUMER_MELEE_REACH_FEET
    )

    assert result is expected


def test_is_within_melee_reach_exact_boundary_at_effective_reach() -> None:
    actor = make_position(creature_id="character_001", x=0, y=0)
    target = make_position(creature_id="monster_001", x=3, y=4)

    assert is_within_melee_reach(actor, target, effective_reach=5) is True


def test_is_within_melee_reach_rejects_point_beyond_reach() -> None:
    actor = make_position(creature_id="character_001", x=0, y=0)
    target = make_position(creature_id="monster_001", x=4, y=4)

    assert is_within_melee_reach(actor, target, effective_reach=5) is False


def test_is_within_melee_reach_is_symmetric() -> None:
    actor = make_position(creature_id="character_001", x=1, y=-2)
    target = make_position(creature_id="monster_001", x=-2, y=2)

    forward = is_within_melee_reach(actor, target, effective_reach=5)
    backward = is_within_melee_reach(target, actor, effective_reach=5)

    assert forward == backward is True


def test_is_within_melee_reach_uses_only_integer_arithmetic() -> None:
    actor = make_position(creature_id="character_001", x=0, y=0)
    target = make_position(creature_id="monster_001", x=1, y=1)

    result = is_within_melee_reach(actor, target, effective_reach=5)

    assert result is True
    assert isinstance(result, bool)


@pytest.mark.parametrize(
    ("actor", "target", "effective_reach", "match"),
    [
        (object(), make_position(creature_id="character_001", x=0, y=0), 5, "actor"),
        (
            make_position(creature_id="character_001", x=0, y=0),
            object(),
            5,
            "target",
        ),
    ],
)
def test_is_within_melee_reach_rejects_wrong_position_types(
    actor: object,
    target: object,
    effective_reach: int,
    match: str,
) -> None:
    with pytest.raises(TypeError, match=match):
        is_within_melee_reach(actor, target, effective_reach=effective_reach)  # type: ignore[arg-type]


@pytest.mark.parametrize("effective_reach", [True, 5.0, "5", None])
def test_is_within_melee_reach_requires_exact_integer_effective_reach(
    effective_reach: object,
) -> None:
    actor = make_position(creature_id="character_001", x=0, y=0)
    target = make_position(creature_id="monster_001", x=0, y=0)

    with pytest.raises(TypeError, match="effective_reach"):
        is_within_melee_reach(
            actor, target, effective_reach=effective_reach  # type: ignore[arg-type]
        )
