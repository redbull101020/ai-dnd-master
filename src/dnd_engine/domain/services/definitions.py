from typing import Protocol, TypeVar

from dnd_engine.domain.definitions.base import Definition


TDefinition = TypeVar("TDefinition", bound=Definition)


class DefinitionSourceError(Exception):
    """Stable boundary error for Definition access failures."""


class DefinitionNotFoundError(DefinitionSourceError):
    """Raised when no Definition exists for the requested ruleset and definition_id."""


class DefinitionTypeMismatchError(DefinitionSourceError):
    """Raised when a Definition exists but is not an instance of the expected type."""


class DefinitionSource(Protocol):
    def get_definition(
        self,
        *,
        ruleset_id: str,
        ruleset_version: str,
        definition_id: str,
        expected_type: type[TDefinition],
    ) -> TDefinition: ...
