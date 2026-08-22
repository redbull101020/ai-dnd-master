from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.definitions.base import Definition
from dnd_engine.domain.definitions.item import ItemDefinition


CANONICAL_FIELDS = ("id", "version", "name")


def test_item_definition_accepts_canonical_fields() -> None:
    item = ItemDefinition(id="healing_potion", version=1, name="Healing Potion")

    assert item.id == "healing_potion"
    assert item.version == 1
    assert item.name == "Healing Potion"


def test_item_definition_is_a_definition() -> None:
    item = ItemDefinition(id="healing_potion", version=1, name="Healing Potion")

    assert isinstance(item, Definition)


def test_item_definition_is_immutable() -> None:
    item = ItemDefinition(id="healing_potion", version=1, name="Healing Potion")

    with pytest.raises(FrozenInstanceError):
        item.name = "Greater Healing Potion"  # type: ignore[misc]


def test_item_definition_has_only_canonical_fields() -> None:
    assert tuple(field.name for field in fields(ItemDefinition)) == CANONICAL_FIELDS


def test_item_definition_does_not_accept_runtime_fields() -> None:
    with pytest.raises(TypeError):
        ItemDefinition(  # type: ignore[call-arg]
            id="healing_potion",
            version=1,
            name="Healing Potion",
            quantity=2,
        )
