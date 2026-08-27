from typing import get_type_hints

from dnd_engine.domain.definitions.base import Definition
from dnd_engine.domain.definitions.monster import MonsterDefinition
from dnd_engine.domain.services.definitions import (
    DefinitionNotFoundError,
    DefinitionSource,
    DefinitionSourceError,
    DefinitionTypeMismatchError,
)
from dnd_engine.domain.value_objects.ability_scores import AbilityScores


def goblin() -> MonsterDefinition:
    return MonsterDefinition(
        id="goblin",
        version=1,
        name="Goblin",
        ability_scores=AbilityScores(8, 14, 10, 10, 8, 8),
        armor_class=15,
    )


class FakeDefinitionSource:
    def __init__(self, definitions: dict[tuple[str, str, str], Definition]) -> None:
        self._definitions = definitions

    def get_definition(
        self,
        *,
        ruleset_id: str,
        ruleset_version: str,
        definition_id: str,
        expected_type: type,
    ):
        key = (ruleset_id, ruleset_version, definition_id)
        if key not in self._definitions:
            raise DefinitionNotFoundError(f"no Definition for {key!r}")
        definition = self._definitions[key]
        if not isinstance(definition, expected_type):
            raise DefinitionTypeMismatchError(
                f"{definition_id!r} is {type(definition).__name__}, "
                f"expected {expected_type.__name__}"
            )
        return definition


def test_error_hierarchy_is_stable() -> None:
    assert issubclass(DefinitionNotFoundError, DefinitionSourceError)
    assert issubclass(DefinitionTypeMismatchError, DefinitionSourceError)
    assert issubclass(DefinitionSourceError, Exception)


def test_definition_source_is_a_runtime_checkable_shape() -> None:
    source = FakeDefinitionSource({("dnd_5e", "5.1", "goblin"): goblin()})

    result: MonsterDefinition = source.get_definition(
        ruleset_id="dnd_5e",
        ruleset_version="5.1",
        definition_id="goblin",
        expected_type=MonsterDefinition,
    )

    assert result == goblin()


def test_missing_definition_raises_not_found() -> None:
    source = FakeDefinitionSource({})

    try:
        source.get_definition(
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
            definition_id="does_not_exist",
            expected_type=MonsterDefinition,
        )
    except DefinitionNotFoundError:
        pass
    else:
        raise AssertionError("expected DefinitionNotFoundError")


def test_wrong_type_raises_type_mismatch_not_not_found() -> None:
    from dnd_engine.domain.definitions.item import ItemDefinition

    item = ItemDefinition(id="torch", version=1, name="Torch")
    source = FakeDefinitionSource({("dnd_5e", "5.1", "torch"): item})

    try:
        source.get_definition(
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
            definition_id="torch",
            expected_type=MonsterDefinition,
        )
    except DefinitionTypeMismatchError:
        pass
    else:
        raise AssertionError("expected DefinitionTypeMismatchError")


def test_get_definition_signature_declares_expected_return_type() -> None:
    hints = get_type_hints(DefinitionSource.get_definition)

    assert set(hints) == {
        "ruleset_id",
        "ruleset_version",
        "definition_id",
        "expected_type",
        "return",
    }
    assert hints["ruleset_id"] is str
    assert hints["ruleset_version"] is str
    assert hints["definition_id"] is str
