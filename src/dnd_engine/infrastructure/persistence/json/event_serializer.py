from collections.abc import Mapping
from datetime import datetime

from dnd_engine.domain.events.game_event import GameEvent, JSONValue


_ENVELOPE_FIELDS = {
    "eventId",
    "commandId",
    "type",
    "version",
    "campaignId",
    "timestamp",
    "actorId",
    "causedBy",
    "payload",
}
_REQUIRED_FIELDS = _ENVELOPE_FIELDS - {"actorId", "causedBy"}


def _to_json_value(value: JSONValue) -> object:
    if isinstance(value, Mapping):
        return {key: _to_json_value(nested) for key, nested in value.items()}
    if isinstance(value, tuple):
        return [_to_json_value(item) for item in value]
    return value


def _serialize_timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


class EventSerializer:
    @staticmethod
    def serialize(event: GameEvent) -> dict[str, object]:
        if not isinstance(event, GameEvent):
            raise TypeError("event must be a GameEvent")

        return {
            "eventId": event.event_id,
            "commandId": event.command_id,
            "type": event.type,
            "version": event.version,
            "campaignId": event.campaign_id,
            "timestamp": _serialize_timestamp(event.timestamp),
            "actorId": event.actor_id,
            "causedBy": event.caused_by,
            "payload": _to_json_value(event.payload),
        }

    @staticmethod
    def deserialize(data: Mapping[str, object]) -> GameEvent:
        if not isinstance(data, Mapping):
            raise TypeError("event data must be a mapping")

        missing = _REQUIRED_FIELDS - data.keys()
        if missing:
            raise ValueError(f"missing required Event fields: {sorted(missing)}")
        unknown = data.keys() - _ENVELOPE_FIELDS
        if unknown:
            raise ValueError(f"unknown Event fields: {sorted(unknown, key=repr)}")

        timestamp = EventSerializer._deserialize_timestamp(data["timestamp"])

        return GameEvent(
            event_id=data["eventId"],  # type: ignore[arg-type]
            command_id=data["commandId"],  # type: ignore[arg-type]
            type=data["type"],  # type: ignore[arg-type]
            version=data["version"],  # type: ignore[arg-type]
            campaign_id=data["campaignId"],  # type: ignore[arg-type]
            timestamp=timestamp,
            actor_id=data.get("actorId"),  # type: ignore[arg-type]
            caused_by=data.get("causedBy"),  # type: ignore[arg-type]
            payload=data["payload"],  # type: ignore[arg-type]
        )

    @staticmethod
    def _deserialize_timestamp(value: object) -> datetime:
        if type(value) is not str:
            raise TypeError("timestamp must be an ISO 8601 string")
        if not value.endswith("Z"):
            raise ValueError("timestamp must use the canonical UTC Z suffix")
        try:
            parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
        except ValueError as error:
            raise ValueError("timestamp must be valid ISO 8601 UTC") from error

        if _serialize_timestamp(parsed) != value:
            raise ValueError("timestamp must use the canonical Event format")
        return parsed
