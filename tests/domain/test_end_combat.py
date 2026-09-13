from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.commands.end_combat import (
    EndCombatCommand,
    EndCombatPayload,
)
from dnd_engine.domain.rules.end_combat import (
    EndCombatResult,
    resolve_end_combat,
)
from dnd_engine.domain.state.combat import CombatState


def make_command(
    *, combat_id: str = "combat_001", actor_id: str = "character_001"
) -> EndCombatCommand:
    return EndCombatCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id=actor_id,
        payload=EndCombatPayload(combat_id=combat_id),
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


def test_resolver_returns_result_with_matching_combat_id() -> None:
    combat = make_combat()

    result = resolve_end_combat(make_command(), combat)

    assert result.combat_id == "combat_001"


def test_resolver_rejects_wrong_types() -> None:
    with pytest.raises(TypeError, match="EndCombatCommand"):
        resolve_end_combat(object(), make_combat())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="CombatState"):
        resolve_end_combat(make_command(), object())  # type: ignore[arg-type]


def test_resolver_rejects_combat_id_mismatch() -> None:
    with pytest.raises(ValueError, match="combat_id"):
        resolve_end_combat(
            make_command(combat_id="combat_999"), make_combat()
        )


# --- EndCombatResult invariants ---------------------------------------------


def canonical_result(**overrides: object) -> EndCombatResult:
    values: dict[str, object] = {"combat_id": "combat_001"}
    values.update(overrides)
    return EndCombatResult(**values)  # type: ignore[arg-type]


def test_result_has_exact_fields_and_is_immutable() -> None:
    result = canonical_result()

    assert tuple(field.name for field in fields(EndCombatResult)) == (
        "combat_id",
    )
    with pytest.raises(FrozenInstanceError):
        result.combat_id = "combat_002"  # type: ignore[misc]


@pytest.mark.parametrize("combat_id", [1, True, 1.0, None])
def test_result_rejects_wrong_runtime_types(combat_id: object) -> None:
    with pytest.raises(TypeError):
        canonical_result(combat_id=combat_id)
