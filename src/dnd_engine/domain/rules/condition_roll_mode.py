from dnd_engine.domain.value_objects.condition import Condition
from dnd_engine.domain.value_objects.d20 import RollMode


def ability_check_roll_mode_from_conditions(
    conditions: frozenset[Condition],
) -> RollMode:
    """Return the effective Ability Check roll mode from Condition membership."""
    if type(conditions) is not frozenset:
        raise TypeError("conditions must be a frozenset")
    if not all(isinstance(condition, Condition) for condition in conditions):
        raise TypeError("conditions must contain only Condition values")

    if Condition.POISONED in conditions:
        return RollMode.DISADVANTAGE
    return RollMode.NORMAL


def attack_roll_mode_from_conditions(
    conditions: frozenset[Condition],
) -> RollMode:
    """Return the effective Attack Roll mode from Condition membership."""
    if type(conditions) is not frozenset:
        raise TypeError("conditions must be a frozenset")
    if not all(isinstance(condition, Condition) for condition in conditions):
        raise TypeError("conditions must contain only Condition values")

    if Condition.POISONED in conditions:
        return RollMode.DISADVANTAGE
    return RollMode.NORMAL
