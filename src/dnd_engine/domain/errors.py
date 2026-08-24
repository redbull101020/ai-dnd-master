from dataclasses import dataclass
from enum import StrEnum


class ErrorCode(StrEnum):
    INVALID_COMMAND = "INVALID_COMMAND"
    ENTITY_NOT_FOUND = "ENTITY_NOT_FOUND"
    DEFINITION_NOT_FOUND = "DEFINITION_NOT_FOUND"
    ACTION_NOT_AVAILABLE = "ACTION_NOT_AVAILABLE"
    INVALID_TARGET = "INVALID_TARGET"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    NOT_VISIBLE = "NOT_VISIBLE"
    RESOURCE_NOT_AVAILABLE = "RESOURCE_NOT_AVAILABLE"
    INVALID_STATE = "INVALID_STATE"
    RULE_VIOLATION = "RULE_VIOLATION"


@dataclass(frozen=True)
class EngineError:
    code: ErrorCode
    message: str
    entity_id: str | None = None
    field: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, ErrorCode):
            raise TypeError("code must be an ErrorCode")
        if type(self.message) is not str:
            raise TypeError("message must be a str")
        for field_name in ("entity_id", "field"):
            value = getattr(self, field_name)
            if value is not None and type(value) is not str:
                raise TypeError(f"{field_name} must be a str or None")
