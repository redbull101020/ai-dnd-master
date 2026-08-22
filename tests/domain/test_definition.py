from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.definitions.base import Definition


def test_definition_accepts_canonical_fields() -> None:
    definition = Definition(id="longsword", version=1)

    assert definition.id == "longsword"
    assert definition.version == 1


def test_definition_is_immutable() -> None:
    definition = Definition(id="longsword", version=1)

    with pytest.raises(FrozenInstanceError):
        definition.version = 2  # type: ignore[misc]


def test_definition_has_only_canonical_fields() -> None:
    assert tuple(field.name for field in fields(Definition)) == ("id", "version")


def test_definition_does_not_accept_future_fields() -> None:
    with pytest.raises(TypeError):
        Definition(id="longsword", version=1, name="Longsword")  # type: ignore[call-arg]
