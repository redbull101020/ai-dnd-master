from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.commands.place_combatant import (
    PlaceCombatantCommand,
    PlaceCombatantPayload,
)
from dnd_engine.domain.rules.place_combatant import (
    PlaceCombatantResult,
    resolve_place_combatant,
)
from dnd_engine.domain.state.combat import CombatState


def make_command(
    *,
    combat_id: str = "combat_001",
    creature_id: str = "character_001",
    actor_id: str = "character_001",
    x: int = 5,
    y: int = 10,
) -> PlaceCombatantCommand:
    return PlaceCombatantCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id=actor_id,
        payload=PlaceCombatantPayload(
            combat_id=combat_id, creature_id=creature_id, x=x, y=y
        ),
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


def test_resolver_returns_minimal_result() -> None:
    combat = make_combat()

    result = resolve_place_combatant(
        make_command(creature_id="monster_001", x=3, y=-4), combat
    )

    assert result == PlaceCombatantResult(
        combat_id="combat_001", creature_id="monster_001", x=3, y=-4
    )


def test_resolver_rejects_wrong_types() -> None:
    with pytest.raises(TypeError, match="PlaceCombatantCommand"):
        resolve_place_combatant(object(), make_combat())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="CombatState"):
        resolve_place_combatant(make_command(), object())  # type: ignore[arg-type]


def test_resolver_rejects_combat_id_mismatch() -> None:
    with pytest.raises(ValueError, match="combat_id"):
        resolve_place_combatant(
            make_command(combat_id="combat_999"), make_combat()
        )


def test_resolver_does_not_require_actor_id_to_match_creature_id() -> None:
    combat = make_combat()

    result = resolve_place_combatant(
        make_command(actor_id="character_gm", creature_id="monster_001"), combat
    )

    assert result.creature_id == "monster_001"


# --- PlaceCombatantResult invariants -----------------------------------------


def canonical_result(**overrides: object) -> PlaceCombatantResult:
    values: dict[str, object] = {
        "combat_id": "combat_001",
        "creature_id": "character_001",
        "x": 5,
        "y": 10,
    }
    values.update(overrides)
    return PlaceCombatantResult(**values)  # type: ignore[arg-type]


def test_result_has_exact_fields_and_is_immutable() -> None:
    result = canonical_result()

    assert tuple(field.name for field in fields(PlaceCombatantResult)) == (
        "combat_id",
        "creature_id",
        "x",
        "y",
    )
    with pytest.raises(FrozenInstanceError):
        result.x = 1  # type: ignore[misc]


@pytest.mark.parametrize("field_name", ["combat_id", "creature_id"])
@pytest.mark.parametrize("value", [1, True, 1.0, None])
def test_result_rejects_wrong_string_types(field_name: str, value: object) -> None:
    with pytest.raises(TypeError):
        canonical_result(**{field_name: value})


@pytest.mark.parametrize("field_name", ["x", "y"])
@pytest.mark.parametrize("value", ["5", None, 1.0, True])
def test_result_rejects_wrong_coordinate_types(
    field_name: str, value: object
) -> None:
    with pytest.raises(TypeError):
        canonical_result(**{field_name: value})
