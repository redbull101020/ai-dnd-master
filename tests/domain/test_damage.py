from copy import deepcopy
from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.commands.damage import ApplyDamageCommand, ApplyDamagePayload
from dnd_engine.domain.rules.damage import (
    DamageResult,
    resolve_damage,
    resolve_damage_amount,
)
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.value_objects.ability_scores import AbilityScores


def make_creature(
    *,
    creature_id: str = "monster_001",
    current_hp: int = 12,
    max_hp: int = 12,
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
    amount: int = 5,
) -> ApplyDamageCommand:
    return ApplyDamageCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=ApplyDamagePayload(target_id=target_id, amount=amount),
    )


def canonical_result(**overrides: object) -> DamageResult:
    values: dict[str, object] = {
        "target_id": "monster_001",
        "amount": 5,
        "previous_hp": 12,
        "new_hp": 7,
    }
    values.update(overrides)
    return DamageResult(**values)  # type: ignore[arg-type]


# --- resolve_damage: gameplay behaviour -------------------------------


def test_resolve_damage_amount_reduces_hp_by_positive_amount() -> None:
    result = resolve_damage_amount(make_creature(current_hp=12), amount=5)

    assert result == DamageResult(
        target_id="monster_001",
        amount=5,
        previous_hp=12,
        new_hp=7,
    )


def test_resolve_damage_amount_accepts_positive_damage_at_zero_hp() -> None:
    result = resolve_damage_amount(
        make_creature(current_hp=0, max_hp=12),
        amount=5,
    )

    assert result.previous_hp == 0
    assert result.new_hp == 0


@pytest.mark.parametrize("amount", [0, -1])
def test_resolve_damage_amount_rejects_non_positive_amount(amount: int) -> None:
    with pytest.raises(ValueError, match="amount"):
        resolve_damage_amount(make_creature(), amount=amount)


@pytest.mark.parametrize("amount", [True, 5.0, "5", None])
def test_resolve_damage_amount_requires_exact_integer_amount(amount: object) -> None:
    with pytest.raises(TypeError, match="amount"):
        resolve_damage_amount(make_creature(), amount=amount)  # type: ignore[arg-type]


def test_resolve_damage_amount_rejects_wrong_target_type() -> None:
    with pytest.raises(TypeError, match="CreatureState"):
        resolve_damage_amount(object(), amount=5)  # type: ignore[arg-type]


def test_resolve_damage_amount_does_not_mutate_target() -> None:
    target = make_creature(current_hp=12)
    target_before = deepcopy(target)

    resolve_damage_amount(target, amount=5)

    assert target == target_before


def test_ordinary_damage_reduces_hp_by_amount() -> None:
    result = resolve_damage(make_command(amount=5), make_creature(current_hp=12))

    assert result == DamageResult(
        target_id="monster_001",
        amount=5,
        previous_hp=12,
        new_hp=7,
    )


def test_damage_exactly_equal_to_current_hp_reaches_zero() -> None:
    result = resolve_damage(make_command(amount=12), make_creature(current_hp=12))

    assert result.previous_hp == 12
    assert result.new_hp == 0


def test_overkill_damage_clamps_to_zero() -> None:
    result = resolve_damage(make_command(amount=999), make_creature(current_hp=12))

    assert result.previous_hp == 12
    assert result.new_hp == 0


def test_damage_to_target_already_at_zero_stays_at_zero() -> None:
    result = resolve_damage(
        make_command(amount=5),
        make_creature(current_hp=0, max_hp=12),
    )

    assert result.previous_hp == 0
    assert result.new_hp == 0


def test_amount_of_one_is_accepted() -> None:
    result = resolve_damage(make_command(amount=1), make_creature(current_hp=12))

    assert result.amount == 1
    assert result.new_hp == 11


def test_resolver_target_identity_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="target_id"):
        resolve_damage(
            make_command(target_id="monster_002"),
            make_creature(creature_id="monster_001"),
        )


def test_resolver_does_not_mutate_target() -> None:
    target = make_creature(current_hp=12)
    target_before = deepcopy(target)

    resolve_damage(make_command(amount=5), target)

    assert target == target_before


def test_same_command_and_target_produce_same_result() -> None:
    command = make_command(amount=5)
    target = make_creature(current_hp=12)

    first = resolve_damage(command, target)
    second = resolve_damage(command, target)

    assert first == second


@pytest.mark.parametrize(
    ("command", "target", "match"),
    [
        (object(), make_creature(), "ApplyDamageCommand"),
        (make_command(), object(), "CreatureState"),
    ],
)
def test_resolver_rejects_wrong_domain_input_types(
    command: object,
    target: object,
    match: str,
) -> None:
    with pytest.raises(TypeError, match=match):
        resolve_damage(command, target)  # type: ignore[arg-type]


# --- DamageResult: shape and invariants --------------------------------


def test_damage_result_has_exact_fields() -> None:
    assert tuple(field.name for field in fields(DamageResult)) == (
        "target_id",
        "amount",
        "previous_hp",
        "new_hp",
    )
    result = canonical_result()
    for absent_field in (
        "overkill",
        "effective_hp_loss",
        "damage_type",
        "resisted",
        "immune",
        "vulnerable",
        "temporary_hp",
        "dropped_to_zero",
        "defeated",
    ):
        assert not hasattr(result, absent_field)


def test_damage_result_is_immutable() -> None:
    result = canonical_result()

    with pytest.raises(FrozenInstanceError):
        result.new_hp = 0  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("target_id", 1),
        ("amount", True),
        ("previous_hp", True),
        ("new_hp", True),
        ("amount", 5.0),
        ("previous_hp", "12"),
        ("new_hp", None),
    ],
)
def test_damage_result_rejects_wrong_runtime_types(
    field_name: str,
    invalid_value: object,
) -> None:
    with pytest.raises(TypeError):
        canonical_result(**{field_name: invalid_value})


def test_damage_result_rejects_zero_amount() -> None:
    with pytest.raises(ValueError, match="amount"):
        canonical_result(amount=0, new_hp=12)


def test_damage_result_rejects_negative_amount() -> None:
    with pytest.raises(ValueError, match="amount"):
        canonical_result(amount=-1, new_hp=13)


def test_damage_result_rejects_negative_previous_hp() -> None:
    with pytest.raises(ValueError, match="previous_hp"):
        canonical_result(previous_hp=-1, new_hp=0)


def test_damage_result_enforces_formula_invariant() -> None:
    with pytest.raises(ValueError, match="new_hp"):
        canonical_result(previous_hp=12, amount=5, new_hp=6)


def test_damage_result_formula_clamps_overkill_to_zero() -> None:
    result = canonical_result(previous_hp=5, amount=10, new_hp=0)

    assert result.new_hp == 0
