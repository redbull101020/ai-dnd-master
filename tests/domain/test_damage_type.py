import pytest

from dnd_engine.domain.value_objects.damage_type import DamageType


CANONICAL_DAMAGE_TYPES = (
    ("ACID", "acid"),
    ("BLUDGEONING", "bludgeoning"),
    ("COLD", "cold"),
    ("FIRE", "fire"),
    ("FORCE", "force"),
    ("LIGHTNING", "lightning"),
    ("NECROTIC", "necrotic"),
    ("PIERCING", "piercing"),
    ("POISON", "poison"),
    ("PSYCHIC", "psychic"),
    ("RADIANT", "radiant"),
    ("SLASHING", "slashing"),
    ("THUNDER", "thunder"),
)


def test_damage_type_has_exact_canonical_members_and_values() -> None:
    assert tuple((member.name, member.value) for member in DamageType) == (
        CANONICAL_DAMAGE_TYPES
    )


def test_damage_type_rejects_non_canonical_value() -> None:
    with pytest.raises(ValueError):
        DamageType("untyped")


def test_damage_type_has_string_semantics() -> None:
    damage_type = DamageType.SLASHING

    assert isinstance(damage_type, str)
    assert damage_type == "slashing"
    assert str(damage_type) == "slashing"
