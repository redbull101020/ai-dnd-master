from dataclasses import fields

import pytest

from dnd_engine.domain.state.equipment import EquipmentState


class StringSubclass(str):
    pass


def test_equipment_state_has_exact_canonical_fields() -> None:
    assert tuple(field.name for field in fields(EquipmentState)) == (
        "owner_id",
        "equipped_weapon_id",
    )


@pytest.mark.parametrize("equipped_weapon_id", ["item_001", None])
def test_equipment_state_accepts_canonical_values(
    equipped_weapon_id: str | None,
) -> None:
    equipment = EquipmentState(
        owner_id="character_001",
        equipped_weapon_id=equipped_weapon_id,
    )

    assert equipment.owner_id == "character_001"
    assert equipment.equipped_weapon_id == equipped_weapon_id


@pytest.mark.parametrize(
    "value", [1, True, None, StringSubclass("character_001")]
)
def test_equipment_state_rejects_non_exact_string_owner_id(value: object) -> None:
    with pytest.raises(TypeError):
        EquipmentState(  # type: ignore[arg-type]
            owner_id=value,
            equipped_weapon_id=None,
        )


@pytest.mark.parametrize("value", [1, True, (), StringSubclass("item_001")])
def test_equipment_state_rejects_invalid_equipped_weapon_id(value: object) -> None:
    with pytest.raises(TypeError):
        EquipmentState(  # type: ignore[arg-type]
            owner_id="character_001",
            equipped_weapon_id=value,
        )
