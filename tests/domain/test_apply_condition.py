from copy import deepcopy
from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.commands.apply_condition import (
    ApplyConditionCommand,
    ApplyConditionPayload,
)
from dnd_engine.domain.rules.apply_condition import (
    ConditionApplicationResult,
    resolve_condition_application,
)
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.domain.value_objects.condition import Condition


def make_creature(
    *,
    creature_id: str = "monster_001",
    conditions: frozenset[Condition] = frozenset(),
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
        current_hp=7,
        max_hp=7,
        conditions=conditions,
    )


def make_command(
    *,
    target_id: str = "monster_001",
    condition: Condition = Condition.POISONED,
) -> ApplyConditionCommand:
    return ApplyConditionCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=ApplyConditionPayload(target_id=target_id, condition=condition),
    )


def canonical_result(**overrides: object) -> ConditionApplicationResult:
    values: dict[str, object] = {
        "target_id": "monster_001",
        "condition": Condition.POISONED,
        "previous_active": False,
        "active": True,
    }
    values.update(overrides)
    return ConditionApplicationResult(**values)  # type: ignore[arg-type]


# --- resolve_condition_application: gameplay behaviour ------------------


def test_applying_absent_condition_becomes_active() -> None:
    result = resolve_condition_application(
        make_command(), make_creature(conditions=frozenset())
    )

    assert result == ConditionApplicationResult(
        target_id="monster_001",
        condition=Condition.POISONED,
        previous_active=False,
        active=True,
    )


def test_applying_already_active_condition_is_a_successful_no_op() -> None:
    result = resolve_condition_application(
        make_command(), make_creature(conditions=frozenset({Condition.POISONED}))
    )

    assert result.previous_active is True
    assert result.active is True


def test_resolver_target_identity_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="target_id"):
        resolve_condition_application(
            make_command(target_id="monster_002"),
            make_creature(creature_id="monster_001"),
        )


def test_resolver_does_not_mutate_target() -> None:
    target = make_creature(conditions=frozenset())
    target_before = deepcopy(target)

    resolve_condition_application(make_command(), target)

    assert target == target_before


def test_same_command_and_target_produce_same_result() -> None:
    command = make_command()
    target = make_creature(conditions=frozenset())

    first = resolve_condition_application(command, target)
    second = resolve_condition_application(command, target)

    assert first == second


@pytest.mark.parametrize(
    ("command", "target", "match"),
    [
        (object(), make_creature(), "ApplyConditionCommand"),
        (make_command(), object(), "CreatureState"),
    ],
)
def test_resolver_rejects_wrong_domain_input_types(
    command: object,
    target: object,
    match: str,
) -> None:
    with pytest.raises(TypeError, match=match):
        resolve_condition_application(command, target)  # type: ignore[arg-type]


# --- ConditionApplicationResult: shape and invariants --------------------


def test_condition_application_result_has_exact_fields() -> None:
    assert tuple(field.name for field in fields(ConditionApplicationResult)) == (
        "target_id",
        "condition",
        "previous_active",
        "active",
    )
    result = canonical_result()
    for absent_field in (
        "source",
        "duration",
        "save_dc",
        "spell_id",
        "item_id",
        "feature_id",
        "stacks",
        "condition_instance_id",
    ):
        assert not hasattr(result, absent_field)


def test_condition_application_result_is_immutable() -> None:
    result = canonical_result()

    with pytest.raises(FrozenInstanceError):
        result.active = False  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("target_id", 1),
        ("condition", "poisoned"),
        ("previous_active", 1),
        ("active", 1),
        ("previous_active", None),
        ("active", None),
    ],
)
def test_condition_application_result_rejects_wrong_runtime_types(
    field_name: str,
    invalid_value: object,
) -> None:
    with pytest.raises(TypeError):
        canonical_result(**{field_name: invalid_value})


def test_condition_application_result_requires_active_true() -> None:
    with pytest.raises(ValueError, match="active"):
        canonical_result(active=False)
