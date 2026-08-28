from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timezone

import pytest

from dnd_engine.domain.commands.healing import (
    ApplyHealingCommand,
    ApplyHealingPayload,
)
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.events.healing import (
    HealingAppliedPayloadV1,
    build_healing_applied_v1,
)
from dnd_engine.domain.rules.healing import HealingResult
from dnd_engine.infrastructure.persistence.json.event_serializer import EventSerializer


FIXED_TIMESTAMP = datetime(2026, 8, 28, 16, 0, tzinfo=timezone.utc)
PAYLOAD_KEYS = {"targetId", "amount", "previousHp", "maxHp", "newHp"}


def make_command(
    *,
    target_id: str = "character_001",
    amount: int = 10,
) -> ApplyHealingCommand:
    return ApplyHealingCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_002",
        payload=ApplyHealingPayload(target_id=target_id, amount=amount),
    )


def make_outcome(
    *,
    target_id: str = "character_001",
    amount: int = 10,
    previous_hp: int = 18,
    max_hp: int = 20,
    new_hp: int = 20,
) -> HealingResult:
    return HealingResult(
        target_id=target_id,
        amount=amount,
        previous_hp=previous_hp,
        max_hp=max_hp,
        new_hp=new_hp,
    )


def make_payload(**overrides: object) -> HealingAppliedPayloadV1:
    values: dict[str, object] = {
        "target_id": "character_001",
        "amount": 10,
        "previous_hp": 18,
        "max_hp": 20,
        "new_hp": 20,
    }
    values.update(overrides)
    return HealingAppliedPayloadV1(**values)  # type: ignore[arg-type]


def build_event(
    command: ApplyHealingCommand | None = None,
    outcome: HealingResult | None = None,
) -> GameEvent:
    return build_healing_applied_v1(
        event_id="event_000123",
        timestamp=FIXED_TIMESTAMP,
        command=command or make_command(),
        outcome=outcome or make_outcome(),
    )


# --- canonical Event shape ---------------------------------------------


def test_builder_creates_exact_canonical_event() -> None:
    event = build_event()

    assert event.event_id == "event_000123"
    assert event.type == "HealingApplied"
    assert event.version == 1
    assert event.command_id == "command_000001"
    assert event.campaign_id == "campaign_001"
    assert event.timestamp is FIXED_TIMESTAMP
    assert event.actor_id == "character_002"
    assert event.caused_by is None
    assert set(event.payload) == PAYLOAD_KEYS
    assert event.payload == {
        "targetId": "character_001",
        "amount": 10,
        "previousHp": 18,
        "maxHp": 20,
        "newHp": 20,
    }


def test_event_payload_has_no_premature_fields() -> None:
    event = build_event()

    assert not {
        "requestedAmount",
        "appliedAmount",
        "effectiveAmount",
        "source",
        "spell",
        "item",
        "dice",
        "resource",
        "condition",
        "stateChanges",
    } & set(event.payload)


def test_builder_uses_supplied_metadata_and_command_correlation() -> None:
    command = make_command()
    outcome = make_outcome()

    event = build_healing_applied_v1(
        event_id="event_000999",
        timestamp=FIXED_TIMESTAMP,
        command=command,
        outcome=outcome,
    )

    assert event.event_id == "event_000999"
    assert event.command_id == command.command_id
    assert event.campaign_id == command.campaign_id
    assert event.actor_id == command.actor_id
    assert event.caused_by is None
    assert event.timestamp is FIXED_TIMESTAMP


@pytest.mark.parametrize(
    ("target_id", "amount", "previous_hp", "max_hp", "new_hp"),
    [
        ("monster_001", 8, 7, 20, 15),
        ("character_003", 8, 12, 20, 20),
        ("monster_002", 10, 18, 20, 20),
        ("character_004", 5, 0, 20, 5),
        ("monster_005", 10, 20, 20, 20),
    ],
)
def test_builder_preserves_exact_healing_values(
    target_id: str,
    amount: int,
    previous_hp: int,
    max_hp: int,
    new_hp: int,
) -> None:
    event = build_event(
        command=make_command(target_id=target_id, amount=amount),
        outcome=make_outcome(
            target_id=target_id,
            amount=amount,
            previous_hp=previous_hp,
            max_hp=max_hp,
            new_hp=new_hp,
        ),
    )

    assert event.payload == {
        "targetId": target_id,
        "amount": amount,
        "previousHp": previous_hp,
        "maxHp": max_hp,
        "newHp": new_hp,
    }


def test_canonical_event_round_trips_through_generic_serializer() -> None:
    event = build_event()

    serialized = EventSerializer.serialize(event)

    assert serialized["type"] == "HealingApplied"
    assert serialized["version"] == 1
    assert serialized["payload"] == {
        "targetId": "character_001",
        "amount": 10,
        "previousHp": 18,
        "maxHp": 20,
        "newHp": 20,
    }
    assert EventSerializer.deserialize(serialized) == event


# --- builder correlation guards ----------------------------------------


@pytest.mark.parametrize(
    ("command", "outcome", "error", "match"),
    [
        (object(), make_outcome(), TypeError, "ApplyHealingCommand"),
        (make_command(), object(), TypeError, "HealingResult"),
        (
            make_command(target_id="character_001"),
            make_outcome(target_id="character_002"),
            ValueError,
            "target_id",
        ),
        (
            make_command(amount=10),
            make_outcome(amount=11, previous_hp=8, new_hp=19),
            ValueError,
            "amount",
        ),
    ],
)
def test_builder_rejects_wrong_types_and_correlation_mismatch(
    command: object,
    outcome: object,
    error: type[Exception],
    match: str,
) -> None:
    with pytest.raises(error, match=match):
        build_healing_applied_v1(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
            command=command,  # type: ignore[arg-type]
            outcome=outcome,  # type: ignore[arg-type]
        )


# --- immutability -------------------------------------------------------


def test_built_event_preserves_generic_immutability() -> None:
    event = build_event()

    with pytest.raises(FrozenInstanceError):
        event.type = "HealingReverted"  # type: ignore[misc]
    with pytest.raises(TypeError):
        event.payload["amount"] = 0  # type: ignore[index]


def test_payload_has_exact_fields_and_is_immutable() -> None:
    payload = make_payload()

    assert tuple(field.name for field in fields(payload)) == (
        "target_id",
        "amount",
        "previous_hp",
        "max_hp",
        "new_hp",
    )
    with pytest.raises(FrozenInstanceError):
        payload.new_hp = 0  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("target_id", 1),
        ("amount", True),
        ("previous_hp", True),
        ("max_hp", True),
        ("new_hp", True),
        ("amount", 10.0),
        ("previous_hp", "18"),
        ("max_hp", None),
        ("new_hp", 20.0),
    ],
)
def test_payload_rejects_wrong_runtime_types(
    field_name: str,
    invalid_value: object,
) -> None:
    with pytest.raises(TypeError):
        make_payload(**{field_name: invalid_value})
