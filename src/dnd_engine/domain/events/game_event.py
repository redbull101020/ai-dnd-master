from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import isfinite
from types import MappingProxyType
from typing import TypeAlias


JSONScalar: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONScalar | Mapping[str, "JSONValue"] | tuple["JSONValue", ...]


def _freeze_json_value(value: object) -> JSONValue:
    if value is None or type(value) in (str, int, bool):
        return value  # type: ignore[return-value]
    if type(value) is float:
        if not isfinite(value):
            raise ValueError("payload float values must be finite")
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, JSONValue] = {}
        for key, nested_value in value.items():
            if type(key) is not str:
                raise TypeError("payload mapping keys must be strings")
            frozen[key] = _freeze_json_value(nested_value)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json_value(item) for item in value)
    raise TypeError("payload values must be JSON-compatible")


@dataclass(frozen=True)
class GameEvent:
    event_id: str
    command_id: str
    type: str
    version: int
    campaign_id: str
    timestamp: datetime
    actor_id: str | None
    caused_by: str | None
    payload: Mapping[str, JSONValue]

    def __post_init__(self) -> None:
        for field_name in ("event_id", "command_id", "type", "campaign_id"):
            if type(getattr(self, field_name)) is not str:
                raise TypeError(f"{field_name} must be a str")
        if type(self.version) is not int:
            raise TypeError("version must be an int")
        for field_name in ("actor_id", "caused_by"):
            value = getattr(self, field_name)
            if value is not None and type(value) is not str:
                raise TypeError(f"{field_name} must be a str or None")
        if type(self.timestamp) is not datetime:
            raise TypeError("timestamp must be a datetime")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        if self.timestamp.utcoffset() != timedelta(0):
            raise ValueError("timestamp must be UTC")
        if not isinstance(self.payload, Mapping):
            raise TypeError("payload must be a mapping")

        frozen_payload = _freeze_json_value(self.payload)
        object.__setattr__(self, "payload", frozen_payload)
