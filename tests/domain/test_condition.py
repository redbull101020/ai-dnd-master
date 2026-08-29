import pytest

from dnd_engine.domain.value_objects.condition import Condition


CANONICAL_CONDITIONS = (("POISONED", "poisoned"),)


def test_condition_has_exact_canonical_members_and_values() -> None:
    assert tuple((member.name, member.value) for member in Condition) == (
        CANONICAL_CONDITIONS
    )


def test_condition_rejects_non_canonical_value() -> None:
    with pytest.raises(ValueError):
        Condition("blinded")


def test_condition_has_string_semantics() -> None:
    condition = Condition.POISONED

    assert isinstance(condition, str)
    assert condition == "poisoned"
    assert str(condition) == "poisoned"
