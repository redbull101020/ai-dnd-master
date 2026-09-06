from dataclasses import fields

import pytest

from dnd_engine.domain.state.inventory import InventoryItemState, InventoryState


class StringSubclass(str):
    pass


def item_state(
    *,
    item_id: str = "item_001",
    definition_id: str = "dagger",
) -> InventoryItemState:
    return InventoryItemState(id=item_id, definition_id=definition_id)


def test_inventory_item_state_has_exact_canonical_fields() -> None:
    assert tuple(field.name for field in fields(InventoryItemState)) == (
        "id",
        "definition_id",
    )


def test_inventory_item_state_accepts_canonical_values() -> None:
    item = item_state()

    assert item.id == "item_001"
    assert item.definition_id == "dagger"


@pytest.mark.parametrize("value", [1, True, None, StringSubclass("item_001")])
def test_inventory_item_state_rejects_non_exact_string_id(value: object) -> None:
    with pytest.raises(TypeError):
        item_state(item_id=value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [1, True, None, StringSubclass("dagger")])
def test_inventory_item_state_rejects_non_exact_string_definition_id(
    value: object,
) -> None:
    with pytest.raises(TypeError):
        item_state(definition_id=value)  # type: ignore[arg-type]


def test_inventory_state_has_exact_canonical_fields() -> None:
    assert tuple(field.name for field in fields(InventoryState)) == (
        "owner_id",
        "items",
    )


def test_inventory_state_accepts_items_and_empty_membership() -> None:
    item = item_state()

    populated = InventoryState(owner_id="character_001", items=(item,))
    empty = InventoryState(owner_id="character_001", items=())

    assert populated.owner_id == "character_001"
    assert populated.items == (item,)
    assert empty.items == ()


@pytest.mark.parametrize(
    "value", [1, True, None, StringSubclass("character_001")]
)
def test_inventory_state_rejects_non_exact_string_owner_id(value: object) -> None:
    with pytest.raises(TypeError):
        InventoryState(owner_id=value, items=())  # type: ignore[arg-type]


@pytest.mark.parametrize("items", [[item_state()], {item_state().id}, None])
def test_inventory_state_rejects_non_tuple_items(items: object) -> None:
    with pytest.raises(TypeError):
        InventoryState(
            owner_id="character_001",
            items=items,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("value", ["item_001", object(), None])
def test_inventory_state_rejects_non_item_members(value: object) -> None:
    with pytest.raises(TypeError):
        InventoryState(
            owner_id="character_001",
            items=(value,),  # type: ignore[arg-type]
        )
