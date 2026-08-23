from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timedelta, timezone
from types import MappingProxyType

import pytest

from dnd_engine.domain.events.game_event import GameEvent


CANONICAL_FIELDS = (
    "event_id",
    "command_id",
    "type",
    "version",
    "campaign_id",
    "timestamp",
    "actor_id",
    "caused_by",
    "payload",
)
FIXED_TIMESTAMP = datetime(2026, 8, 20, 18, 42, 10, tzinfo=timezone.utc)


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
        "payload": {"amount": 10},
    }
    values.update(overrides)
    return GameEvent(**values)  # type: ignore[arg-type]


def test_game_event_has_only_canonical_fields() -> None:
    assert tuple(field.name for field in fields(GameEvent)) == CANONICAL_FIELDS
    assert not {"sequence", "revision", "session_id", "correlation_id"} & set(
        CANONICAL_FIELDS
    )


def test_game_event_accepts_canonical_values() -> None:
    event = make_event()

    assert event.event_id == "event_000124"
    assert event.command_id == "command_000001"
    assert event.type == "DamageApplied"
    assert event.version == 1
    assert event.campaign_id == "campaign_001"
    assert event.timestamp == FIXED_TIMESTAMP
    assert event.actor_id == "character_001"
    assert event.caused_by == "event_000123"
    assert event.payload == {"amount": 10}


def test_game_event_accepts_null_actor_and_causation() -> None:
    event = make_event(actor_id=None, caused_by=None)

    assert event.actor_id is None
    assert event.caused_by is None


def test_game_event_is_frozen() -> None:
    event = make_event()

    with pytest.raises(FrozenInstanceError):
        event.type = "HealingApplied"  # type: ignore[misc]


def test_game_event_accepts_timezone_aware_utc_timestamp() -> None:
    timestamp = datetime(2026, 8, 20, 18, 42, 10, tzinfo=timezone.utc)

    assert make_event(timestamp=timestamp).timestamp is timestamp


@pytest.mark.parametrize("timestamp", [None, "2026-08-20T18:42:10Z", 42])
def test_game_event_rejects_non_datetime_timestamp(timestamp: object) -> None:
    with pytest.raises(TypeError):
        make_event(timestamp=timestamp)


def test_game_event_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError):
        make_event(timestamp=datetime(2026, 8, 20, 18, 42, 10))


def test_game_event_rejects_non_utc_timestamp() -> None:
    non_utc = datetime(
        2026,
        8,
        20,
        21,
        42,
        10,
        tzinfo=timezone(timedelta(hours=3)),
    )

    with pytest.raises(ValueError):
        make_event(timestamp=non_utc)


def test_payload_accepts_nested_json_values() -> None:
    payload = {
        "string": "value",
        "integer": 10,
        "number": 2.5,
        "boolean": True,
        "nothing": None,
        "object": {"values": [1, 2, 3]},
    }

    event = make_event(payload=payload)

    assert event.payload == {
        "string": "value",
        "integer": 10,
        "number": 2.5,
        "boolean": True,
        "nothing": None,
        "object": {"values": (1, 2, 3)},
    }


def test_payload_is_defensively_copied_and_deeply_immutable() -> None:
    values = [1, 2, 3]
    details = {"values": values}
    source = {"targetId": "monster_001", "details": details}

    event = make_event(payload=source)
    source["targetId"] = "monster_002"
    details["added"] = True
    values.append(4)

    assert event.payload == {
        "targetId": "monster_001",
        "details": {"values": (1, 2, 3)},
    }
    assert isinstance(event.payload, MappingProxyType)
    assert isinstance(event.payload["details"], MappingProxyType)
    assert isinstance(event.payload["details"]["values"], tuple)  # type: ignore[index]


def test_stored_payload_cannot_be_mutated() -> None:
    event = make_event(payload={"details": {"values": [1, 2, 3]}})

    with pytest.raises(TypeError):
        event.payload["added"] = True  # type: ignore[index]
    with pytest.raises(TypeError):
        event.payload["details"]["added"] = True  # type: ignore[index]
    with pytest.raises(TypeError):
        event.payload["details"]["values"][0] = 9  # type: ignore[index]


def test_game_event_rejects_non_mapping_payload() -> None:
    with pytest.raises(TypeError):
        make_event(payload=[("amount", 10)])


def test_game_event_rejects_non_string_payload_key() -> None:
    with pytest.raises(TypeError):
        make_event(payload={1: "value"})


@pytest.mark.parametrize("value", [object(), {1, 2}, b"bytes", datetime.now])
def test_game_event_rejects_unsupported_payload_value(value: object) -> None:
    with pytest.raises(TypeError):
        make_event(payload={"unsupported": value})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_game_event_rejects_non_finite_payload_float(value: float) -> None:
    with pytest.raises(ValueError):
        make_event(payload={"number": value})
