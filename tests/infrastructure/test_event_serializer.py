import json
from datetime import datetime, timezone

import pytest

from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.infrastructure.persistence.json.event_serializer import EventSerializer


FIXED_TIMESTAMP = datetime(2026, 8, 20, 18, 42, 10, tzinfo=timezone.utc)
CANONICAL_DATA: dict[str, object] = {
    "eventId": "event_000124",
    "commandId": "command_000001",
    "type": "DamageApplied",
    "version": 1,
    "campaignId": "campaign_001",
    "timestamp": "2026-08-20T18:42:10Z",
    "actorId": "character_001",
    "causedBy": "event_000123",
    "payload": {
        "targetId": "monster_001",
        "amount": 10,
        "details": {"rolls": [4, 6], "critical": False, "note": None},
    },
}
CANONICAL_FIELDS = set(CANONICAL_DATA)
REQUIRED_FIELDS = CANONICAL_FIELDS - {"actorId", "causedBy"}


def make_event(**overrides: object) -> GameEvent:
    values: dict[str, object] = {
        "event_id": "event_000124",
        "command_id": "command_000001",
        "type": "DamageApplied",
        "version": 1,
        "campaign_id": "campaign_001",
        "timestamp": FIXED_TIMESTAMP,
        "actor_id": "character_001",
        "caused_by": "event_000123",
        "payload": CANONICAL_DATA["payload"],
    }
    values.update(overrides)
    return GameEvent(**values)  # type: ignore[arg-type]


def test_serialize_uses_exact_canonical_envelope() -> None:
    serialized = EventSerializer.serialize(make_event())

    assert serialized == CANONICAL_DATA
    assert set(serialized) == CANONICAL_FIELDS
    assert not any("_" in key for key in serialized)


def test_serialize_converts_immutable_domain_collections() -> None:
    serialized = EventSerializer.serialize(make_event())
    payload = serialized["payload"]

    assert isinstance(payload, dict)
    assert isinstance(payload["details"], dict)
    assert isinstance(payload["details"]["rolls"], list)
    assert json.loads(json.dumps(serialized)) == CANONICAL_DATA


def test_serialize_emits_nullable_fields_as_null() -> None:
    serialized = EventSerializer.serialize(make_event(actor_id=None, caused_by=None))

    assert "actorId" in serialized and serialized["actorId"] is None
    assert "causedBy" in serialized and serialized["causedBy"] is None


def test_deserialize_accepts_explicit_null_actor_and_causation() -> None:
    data = dict(CANONICAL_DATA)
    data["actorId"] = None
    data["causedBy"] = None

    event = EventSerializer.deserialize(data)

    assert event.actor_id is None
    assert event.caused_by is None


def test_round_trip_reconstructs_equivalent_immutable_event() -> None:
    original = make_event()

    reconstructed = EventSerializer.deserialize(EventSerializer.serialize(original))

    assert reconstructed == original
    with pytest.raises(TypeError):
        reconstructed.payload["new"] = "value"  # type: ignore[index]


def test_round_trip_preserves_canonical_fractional_microseconds() -> None:
    original = make_event(
        timestamp=datetime(
            2026,
            8,
            20,
            18,
            42,
            10,
            123456,
            tzinfo=timezone.utc,
        )
    )

    serialized = EventSerializer.serialize(original)
    reconstructed = EventSerializer.deserialize(serialized)

    assert serialized["timestamp"] == "2026-08-20T18:42:10.123456Z"
    assert reconstructed == original


def test_deserialize_accepts_missing_nullable_fields() -> None:
    data = {
        key: value
        for key, value in CANONICAL_DATA.items()
        if key not in {"actorId", "causedBy"}
    }

    event = EventSerializer.deserialize(data)

    assert event.actor_id is None
    assert event.caused_by is None


@pytest.mark.parametrize("missing_field", sorted(REQUIRED_FIELDS))
def test_deserialize_rejects_missing_required_field(missing_field: str) -> None:
    data = dict(CANONICAL_DATA)
    del data[missing_field]

    with pytest.raises(ValueError):
        EventSerializer.deserialize(data)


@pytest.mark.parametrize(
    "timestamp",
    [
        "not-a-timestamp",
        "2026-08-20T18:42:10",
        "2026-08-20T21:42:10+03:00",
        "2026-08-20 18:42:10Z",
        "2026-W34-4T18:42:10Z",
        "20260820T184210Z",
        "2026-08-20T18:42Z",
        "2026-08-20T18:42:10,5Z",
        None,
    ],
)
def test_deserialize_rejects_invalid_timestamp(timestamp: object) -> None:
    data = dict(CANONICAL_DATA)
    data["timestamp"] = timestamp

    with pytest.raises((TypeError, ValueError)):
        EventSerializer.deserialize(data)


def test_deserialize_rejects_non_object_payload() -> None:
    data = dict(CANONICAL_DATA)
    data["payload"] = [1, 2, 3]

    with pytest.raises(TypeError):
        EventSerializer.deserialize(data)


def test_deserialize_rejects_unsupported_nested_json_value() -> None:
    data = dict(CANONICAL_DATA)
    data["payload"] = {"unsupported": object()}

    with pytest.raises(TypeError):
        EventSerializer.deserialize(data)


def test_deserialize_rejects_unknown_envelope_field() -> None:
    data = dict(CANONICAL_DATA)
    data["sequence"] = 124

    with pytest.raises(ValueError):
        EventSerializer.deserialize(data)
