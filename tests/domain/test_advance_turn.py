from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.commands.advance_turn import (
    AdvanceTurnCommand,
    AdvanceTurnPayload,
)
from dnd_engine.domain.rules.advance_turn import (
    AdvanceTurnResult,
    resolve_advance_turn,
)
from dnd_engine.domain.state.combat import CombatState


def make_command(
    *, combat_id: str = "combat_001", actor_id: str = "character_001"
) -> AdvanceTurnCommand:
    return AdvanceTurnCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id=actor_id,
        payload=AdvanceTurnPayload(combat_id=combat_id),
    )


def make_combat(**overrides: object) -> CombatState:
    values: dict[str, object] = {
        "id": "combat_001",
        "round": 1,
        "order": ("character_001", "monster_001", "monster_002"),
        "active_index": 0,
    }
    values.update(overrides)
    return CombatState(**values)  # type: ignore[arg-type]


def test_resolver_advances_to_next_combatant_within_same_round() -> None:
    combat = make_combat(active_index=0)

    result = resolve_advance_turn(make_command(), combat)

    assert result.combat_id == "combat_001"
    assert result.previous_active_creature_id == "character_001"
    assert result.active_creature_id == "monster_001"
    assert result.previous_round == 1
    assert result.round == 1


def test_resolver_wraps_around_and_increments_round() -> None:
    combat = make_combat(active_index=2)

    result = resolve_advance_turn(make_command(), combat)

    assert result.previous_active_creature_id == "monster_002"
    assert result.active_creature_id == "character_001"
    assert result.previous_round == 1
    assert result.round == 2


def test_resolver_supports_single_combatant_self_wrap() -> None:
    combat = make_combat(order=("character_001",), active_index=0)

    result = resolve_advance_turn(make_command(), combat)

    assert result.active_creature_id == "character_001"
    assert result.round == 2


def test_resolver_rejects_wrong_types() -> None:
    with pytest.raises(TypeError, match="AdvanceTurnCommand"):
        resolve_advance_turn(object(), make_combat())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="CombatState"):
        resolve_advance_turn(make_command(), object())  # type: ignore[arg-type]


def test_resolver_rejects_combat_id_mismatch() -> None:
    with pytest.raises(ValueError, match="combat_id"):
        resolve_advance_turn(
            make_command(combat_id="combat_999"), make_combat()
        )


# --- AdvanceTurnResult invariants ------------------------------------------


def canonical_result(**overrides: object) -> AdvanceTurnResult:
    values: dict[str, object] = {
        "combat_id": "combat_001",
        "previous_active_creature_id": "character_001",
        "active_creature_id": "monster_001",
        "previous_round": 1,
        "round": 1,
    }
    values.update(overrides)
    return AdvanceTurnResult(**values)  # type: ignore[arg-type]


def test_result_has_exact_fields_and_is_immutable() -> None:
    result = canonical_result()

    assert tuple(field.name for field in fields(AdvanceTurnResult)) == (
        "combat_id",
        "previous_active_creature_id",
        "active_creature_id",
        "previous_round",
        "round",
    )
    with pytest.raises(FrozenInstanceError):
        result.round = 5  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("combat_id", 1),
        ("previous_active_creature_id", 1),
        ("active_creature_id", 1),
        ("previous_round", "1"),
        ("round", True),
    ],
)
def test_result_rejects_wrong_runtime_types(
    field_name: str, invalid_value: object
) -> None:
    with pytest.raises(TypeError):
        canonical_result(**{field_name: invalid_value})


def test_result_rejects_round_skipping_ahead() -> None:
    with pytest.raises(ValueError, match="round"):
        canonical_result(previous_round=1, round=3)


def test_result_rejects_round_going_backwards() -> None:
    with pytest.raises(ValueError, match="round"):
        canonical_result(previous_round=2, round=1)
