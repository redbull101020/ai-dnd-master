from copy import deepcopy
from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.commands.healing import (
    ApplyHealingCommand,
    ApplyHealingPayload,
)
from dnd_engine.domain.rules.healing import HealingResult, resolve_healing
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.value_objects.ability_scores import AbilityScores


def make_creature(
    *,
    creature_id: str = "monster_001",
    current_hp: int = 7,
    max_hp: int = 20,
) -> CreatureState:
    return CreatureState(
        id=creature_id,
        definition_id="goblin",
        ability_scores=AbilityScores(
            strength=8,
            dexterity=14,
            constitution=10,
            intelligence=10,
            wisdom=8,
            charisma=8,
        ),
        current_hp=current_hp,
        max_hp=max_hp,
    )


def make_command(
    *,
    target_id: str = "monster_001",
    amount: int = 8,
) -> ApplyHealingCommand:
    return ApplyHealingCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=ApplyHealingPayload(target_id=target_id, amount=amount),
    )


def canonical_result(**overrides: object) -> HealingResult:
    values: dict[str, object] = {
        "target_id": "monster_001",
        "amount": 8,
        "previous_hp": 7,
        "max_hp": 20,
        "new_hp": 15,
    }
    values.update(overrides)
    return HealingResult(**values)  # type: ignore[arg-type]


# --- resolve_healing: gameplay behaviour ------------------------------


def test_normal_healing_increases_hp_by_amount() -> None:
    result = resolve_healing(make_command(amount=8), make_creature(current_hp=7))

    assert result == HealingResult(
        target_id="monster_001",
        amount=8,
        previous_hp=7,
        max_hp=20,
        new_hp=15,
    )


def test_healing_exactly_to_max_hp_reaches_maximum() -> None:
    result = resolve_healing(make_command(amount=8), make_creature(current_hp=12))

    assert result.previous_hp == 12
    assert result.max_hp == 20
    assert result.new_hp == 20


def test_overhealing_clamps_to_max_hp() -> None:
    result = resolve_healing(make_command(amount=10), make_creature(current_hp=18))

    assert result.previous_hp == 18
    assert result.new_hp == 20


def test_healing_from_zero_increases_hp() -> None:
    result = resolve_healing(make_command(amount=5), make_creature(current_hp=0))

    assert result.previous_hp == 0
    assert result.new_hp == 5


def test_healing_at_full_hp_is_successful_no_op() -> None:
    result = resolve_healing(make_command(amount=5), make_creature(current_hp=20))

    assert result.amount == 5
    assert result.previous_hp == 20
    assert result.new_hp == 20


def test_resolver_target_identity_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="target_id"):
        resolve_healing(
            make_command(target_id="monster_002"),
            make_creature(creature_id="monster_001"),
        )


def test_resolver_does_not_mutate_target() -> None:
    target = make_creature(current_hp=7)
    target_before = deepcopy(target)

    resolve_healing(make_command(amount=8), target)

    assert target == target_before


def test_same_command_and_target_produce_same_result() -> None:
    command = make_command(amount=8)
    target = make_creature(current_hp=7)

    first = resolve_healing(command, target)
    second = resolve_healing(command, target)

    assert first == second


@pytest.mark.parametrize(
    ("command", "target", "match"),
    [
        (object(), make_creature(), "ApplyHealingCommand"),
        (make_command(), object(), "CreatureState"),
    ],
)
def test_resolver_rejects_wrong_domain_input_types(
    command: object,
    target: object,
    match: str,
) -> None:
    with pytest.raises(TypeError, match=match):
        resolve_healing(command, target)  # type: ignore[arg-type]


# --- HealingResult: shape and invariants -------------------------------


def test_healing_result_has_exact_fields() -> None:
    assert tuple(field.name for field in fields(HealingResult)) == (
        "target_id",
        "amount",
        "previous_hp",
        "max_hp",
        "new_hp",
    )
    result = canonical_result()
    for absent_field in ("requested_amount", "applied_amount", "effective_amount"):
        assert not hasattr(result, absent_field)


def test_healing_result_is_immutable() -> None:
    result = canonical_result()

    with pytest.raises(FrozenInstanceError):
        result.new_hp = 20  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("target_id", 1),
        ("amount", True),
        ("previous_hp", True),
        ("max_hp", True),
        ("new_hp", True),
        ("amount", 8.0),
        ("previous_hp", "7"),
        ("max_hp", 20.0),
        ("new_hp", None),
    ],
)
def test_healing_result_rejects_wrong_runtime_types(
    field_name: str,
    invalid_value: object,
) -> None:
    with pytest.raises(TypeError):
        canonical_result(**{field_name: invalid_value})


@pytest.mark.parametrize("amount", [0, -1])
def test_healing_result_rejects_non_positive_amount(amount: int) -> None:
    with pytest.raises(ValueError, match="amount"):
        canonical_result(amount=amount)


@pytest.mark.parametrize("max_hp", [0, -1])
def test_healing_result_rejects_non_positive_max_hp(max_hp: int) -> None:
    with pytest.raises(ValueError, match="max_hp"):
        canonical_result(max_hp=max_hp)


@pytest.mark.parametrize("previous_hp", [-1, 21])
def test_healing_result_rejects_previous_hp_outside_range(
    previous_hp: int,
) -> None:
    with pytest.raises(ValueError, match="previous_hp"):
        canonical_result(previous_hp=previous_hp)


def test_healing_result_enforces_formula_invariant() -> None:
    with pytest.raises(ValueError, match="new_hp"):
        canonical_result(new_hp=14)


def test_healing_result_formula_clamps_overhealing_to_max_hp() -> None:
    result = canonical_result(amount=10, previous_hp=18, new_hp=20)

    assert result.new_hp == result.max_hp
