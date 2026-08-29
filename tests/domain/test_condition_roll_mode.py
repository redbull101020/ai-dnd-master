import pytest

from dnd_engine.domain.rules.condition_roll_mode import (
    ability_check_roll_mode_from_conditions,
    attack_roll_mode_from_conditions,
)
from dnd_engine.domain.value_objects.condition import Condition
from dnd_engine.domain.value_objects.d20 import RollMode


@pytest.mark.parametrize(
    "policy",
    [
        ability_check_roll_mode_from_conditions,
        attack_roll_mode_from_conditions,
    ],
)
def test_poisoned_produces_disadvantage_for_supported_mechanics(policy) -> None:
    assert policy(frozenset({Condition.POISONED})) is RollMode.DISADVANTAGE


@pytest.mark.parametrize(
    "policy",
    [
        ability_check_roll_mode_from_conditions,
        attack_roll_mode_from_conditions,
    ],
)
def test_no_condition_produces_normal_for_supported_mechanics(policy) -> None:
    assert policy(frozenset()) is RollMode.NORMAL


@pytest.mark.parametrize(
    "policy",
    [
        ability_check_roll_mode_from_conditions,
        attack_roll_mode_from_conditions,
    ],
)
def test_condition_policy_rejects_non_frozenset_input(policy) -> None:
    with pytest.raises(TypeError, match="frozenset"):
        policy({Condition.POISONED})


@pytest.mark.parametrize(
    "policy",
    [
        ability_check_roll_mode_from_conditions,
        attack_roll_mode_from_conditions,
    ],
)
def test_condition_policy_rejects_raw_string_members(policy) -> None:
    with pytest.raises(TypeError, match="Condition values"):
        policy(frozenset({"poisoned"}))
