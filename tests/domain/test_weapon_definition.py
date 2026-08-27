from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.definitions.item import ItemDefinition
from dnd_engine.domain.definitions.weapon import WeaponDefinition
from dnd_engine.domain.value_objects.damage_type import DamageType


CANONICAL_FIELDS = (
    "id",
    "version",
    "name",
    "damage_dice",
    "damage_type",
    "properties",
)


def longsword() -> WeaponDefinition:
    return WeaponDefinition(
        id="longsword",
        version=1,
        name="Longsword",
        damage_dice="1d8",
        damage_type=DamageType.SLASHING,
        properties=("versatile",),
    )


def test_weapon_definition_accepts_canonical_fields() -> None:
    weapon = longsword()

    assert weapon.id == "longsword"
    assert weapon.version == 1
    assert weapon.name == "Longsword"
    assert weapon.damage_dice == "1d8"
    assert weapon.damage_type is DamageType.SLASHING
    assert weapon.properties == ("versatile",)


def test_weapon_definition_is_an_item_definition() -> None:
    assert isinstance(longsword(), ItemDefinition)


def test_weapon_definition_damage_type_uses_canonical_type() -> None:
    assert isinstance(longsword().damage_type, DamageType)


def test_weapon_definition_properties_have_tuple_semantics() -> None:
    weapon = longsword()

    assert isinstance(weapon.properties, tuple)
    with pytest.raises(TypeError):
        weapon.properties[0] = "finesse"  # type: ignore[index]


def test_weapon_definition_is_immutable() -> None:
    weapon = longsword()

    with pytest.raises(FrozenInstanceError):
        weapon.damage_dice = "1d10"  # type: ignore[misc]


def test_weapon_definition_has_only_canonical_fields() -> None:
    assert tuple(field.name for field in fields(WeaponDefinition)) == CANONICAL_FIELDS


def test_weapon_definition_does_not_accept_runtime_fields() -> None:
    with pytest.raises(TypeError):
        WeaponDefinition(  # type: ignore[call-arg]
            id="longsword",
            version=1,
            name="Longsword",
            damage_dice="1d8",
            damage_type=DamageType.SLASHING,
            properties=("versatile",),
            equipped=True,
        )


def weapon_with_damage_dice(damage_dice: object) -> WeaponDefinition:
    return WeaponDefinition(
        id="longsword",
        version=1,
        name="Longsword",
        damage_dice=damage_dice,  # type: ignore[arg-type]
        damage_type=DamageType.SLASHING,
        properties=("versatile",),
    )


def test_weapon_definition_accepts_valid_damage_dice() -> None:
    weapon = weapon_with_damage_dice("1d8")

    assert weapon.damage_dice == "1d8"


class DamageDiceString(str):
    pass


@pytest.mark.parametrize(
    "damage_dice",
    [
        "",
        "foo",
        "d20",
        "1d",
        "1d1",
        "1D8",
        " 1d8",
        "1d8 ",
        "01d8",
        "1d08",
        "1d8+2",
        "2d8kh1",
    ],
)
def test_weapon_definition_rejects_malformed_damage_dice(damage_dice: str) -> None:
    with pytest.raises(ValueError):
        weapon_with_damage_dice(damage_dice)


@pytest.mark.parametrize(
    "damage_dice",
    [None, 8, True, DamageDiceString("1d8")],
)
def test_weapon_definition_rejects_non_exact_string_damage_dice(
    damage_dice: object,
) -> None:
    with pytest.raises(TypeError):
        weapon_with_damage_dice(damage_dice)
