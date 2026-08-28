from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timezone

import pytest

from dnd_engine.domain.commands.damage import ApplyDamageCommand, ApplyDamagePayload
from dnd_engine.domain.events.damage import (
    DamageAppliedPayloadV1,
    build_damage_applied_v1,
)
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.rules.damage import DamageResult
from dnd_engine.infrastructure.persistence.json.event_serializer import EventSerializer


FIXED_TIMESTAMP = datetime(2026, 8, 28, 12, 30, tzinfo=timezone.utc)
PAYLOAD_KEYS = {"targetId", "amount", "previousHp", "newHp"}


def make_command(
    *,
    target_id: str = "monster_001",
    amount: int = 5,
) -> ApplyDamageCommand:
    return ApplyDamageCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=ApplyDamagePayload(target_id=target_id, amount=amount),
    )


def make_outcome(
    *,
    target_id: str = "monster_001",
    amount: int = 5,
    previous_hp: int = 12,
    new_hp: int = 7,
) -> DamageResult:
    return DamageResult(
        target_id=target_id,
        amount=amount,
        previous_hp=previous_hp,
        new_hp=new_hp,
    )


def make_payload(**overrides: object) -> DamageAppliedPayloadV1:
    values: dict[str, object] = {
        "target_id": "monster_001",
        "amount": 5,
        "previous_hp": 12,
        "new_hp": 7,
    }
    values.update(overrides)
    return DamageAppliedPayloadV1(**values)  # type: ignore[arg-type]


def build_event(
    command: ApplyDamageCommand | None = None,
    outcome: DamageResult | None = None,
) -> GameEvent:
    return build_damage_applied_v1(
        event_id="event_000123",
        timestamp=FIXED_TIMESTAMP,
        command=command or make_command(),
        outcome=outcome or make_outcome(),
    )


# --- canonical Event shape ---------------------------------------------


def test_builder_creates_exact_canonical_event() -> None:
    event = build_event()

    assert event.event_id == "event_000123"
    assert event.type == "DamageApplied"
    assert event.version == 1
    assert event.command_id == "command_000001"
    assert event.campaign_id == "campaign_001"
    assert event.timestamp is FIXED_TIMESTAMP
    assert event.actor_id == "character_001"
    assert event.caused_by is None
    assert set(event.payload) == PAYLOAD_KEYS
    assert event.payload == {
        "targetId": "monster_001",
        "amount": 5,
        "previousHp": 12,
        "newHp": 7,
    }


def test_event_payload_has_no_premature_fields() -> None:
    event = build_event()

    assert not {
        "damageType",
        "weaponId",
        "attackId",
        "critical",
        "overkill",
        "effectiveHpLoss",
        "condition",
        "stateChanges",
    } & set(event.payload)


def test_builder_uses_supplied_metadata_and_command_correlation() -> None:
    command = make_command()
    outcome = make_outcome()

    event = build_damage_applied_v1(
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
    ("target_id", "amount", "previous_hp", "new_hp"),
    [
        ("monster_001", 12, 12, 0),
        ("monster_002", 999, 12, 0),
        ("character_003", 1, 1, 0),
    ],
)
def test_builder_preserves_exact_damage_values(
    target_id: str,
    amount: int,
    previous_hp: int,
    new_hp: int,
) -> None:
    event = build_event(
        command=make_command(target_id=target_id, amount=amount),
        outcome=make_outcome(
            target_id=target_id,
            amount=amount,
            previous_hp=previous_hp,
            new_hp=new_hp,
        ),
    )

    assert event.payload == {
        "targetId": target_id,
        "amount": amount,
        "previousHp": previous_hp,
        "newHp": new_hp,
    }


def test_canonical_event_is_json_serializable() -> None:
    event = build_event()

    serialized = EventSerializer.serialize(event)

    assert serialized["type"] == "DamageApplied"
    assert serialized["version"] == 1
    assert serialized["payload"] == {
        "targetId": "monster_001",
        "amount": 5,
        "previousHp": 12,
        "newHp": 7,
    }
    assert EventSerializer.deserialize(serialized) == event


# --- builder correlation guards -----------------------------------------


@pytest.mark.parametrize(
    ("command", "outcome", "error", "match"),
    [
        (object(), make_outcome(), TypeError, "ApplyDamageCommand"),
        (make_command(), object(), TypeError, "DamageResult"),
        (
            make_command(target_id="monster_001"),
            make_outcome(target_id="monster_002"),
            ValueError,
            "target_id",
        ),
        (
            make_command(amount=5),
            make_outcome(amount=6, previous_hp=12, new_hp=6),
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
        build_damage_applied_v1(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
            command=command,  # type: ignore[arg-type]
            outcome=outcome,  # type: ignore[arg-type]
        )


# --- immutability ---------------------------------------------------------


def test_built_event_preserves_generic_immutability() -> None:
    event = build_event()

    with pytest.raises(FrozenInstanceError):
        event.type = "DamageReverted"  # type: ignore[misc]
    with pytest.raises(TypeError):
        event.payload["amount"] = 0  # type: ignore[index]


def test_payload_has_exact_fields_and_is_immutable() -> None:
    payload = make_payload()

    assert tuple(field.name for field in fields(payload)) == (
        "target_id",
        "amount",
        "previous_hp",
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
        ("new_hp", True),
        ("amount", 5.0),
        ("previous_hp", "12"),
        ("new_hp", None),
    ],
)
def test_payload_rejects_wrong_runtime_types(
    field_name: str,
    invalid_value: object,
) -> None:
    with pytest.raises(TypeError):
        make_payload(**{field_name: invalid_value})
