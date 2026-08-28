from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timezone

import pytest

from dnd_engine.domain.commands.apply_condition import (
    ApplyConditionCommand,
    ApplyConditionPayload,
)
from dnd_engine.domain.events.apply_condition import (
    ConditionAppliedPayloadV1,
    build_condition_applied_v1,
)
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.rules.apply_condition import ConditionApplicationResult
from dnd_engine.domain.value_objects.condition import Condition
from dnd_engine.infrastructure.persistence.json.event_serializer import EventSerializer


FIXED_TIMESTAMP = datetime(2026, 8, 28, 12, 30, tzinfo=timezone.utc)
PAYLOAD_KEYS = {"targetId", "condition", "previousActive", "active"}


def make_command(
    *,
    target_id: str = "monster_001",
    condition: Condition = Condition.POISONED,
) -> ApplyConditionCommand:
    return ApplyConditionCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=ApplyConditionPayload(target_id=target_id, condition=condition),
    )


def make_outcome(
    *,
    target_id: str = "monster_001",
    condition: Condition = Condition.POISONED,
    previous_active: bool = False,
) -> ConditionApplicationResult:
    return ConditionApplicationResult(
        target_id=target_id,
        condition=condition,
        previous_active=previous_active,
        active=True,
    )


def make_payload(**overrides: object) -> ConditionAppliedPayloadV1:
    values: dict[str, object] = {
        "target_id": "monster_001",
        "condition": Condition.POISONED,
        "previous_active": False,
        "active": True,
    }
    values.update(overrides)
    return ConditionAppliedPayloadV1(**values)  # type: ignore[arg-type]


def build_event(
    command: ApplyConditionCommand | None = None,
    outcome: ConditionApplicationResult | None = None,
) -> GameEvent:
    return build_condition_applied_v1(
        event_id="event_000123",
        timestamp=FIXED_TIMESTAMP,
        command=command or make_command(),
        outcome=outcome or make_outcome(),
    )


# --- canonical Event shape ------------------------------------------------


def test_builder_creates_exact_canonical_event() -> None:
    event = build_event()

    assert event.event_id == "event_000123"
    assert event.type == "ConditionApplied"
    assert event.version == 1
    assert event.command_id == "command_000001"
    assert event.campaign_id == "campaign_001"
    assert event.timestamp is FIXED_TIMESTAMP
    assert event.actor_id == "character_001"
    assert event.caused_by is None
    assert set(event.payload) == PAYLOAD_KEYS
    assert event.payload == {
        "targetId": "monster_001",
        "condition": "poisoned",
        "previousActive": False,
        "active": True,
    }


def test_event_payload_has_no_premature_fields() -> None:
    event = build_event()

    assert not {
        "source",
        "duration",
        "saveDc",
        "spellId",
        "itemId",
        "featureId",
        "stacks",
        "conditionInstanceId",
        "previousConditions",
        "newConditions",
        "stateChanges",
    } & set(event.payload)


def test_builder_uses_supplied_metadata_and_command_correlation() -> None:
    command = make_command()
    outcome = make_outcome()

    event = build_condition_applied_v1(
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


def test_no_op_application_still_builds_full_event() -> None:
    event = build_event(outcome=make_outcome(previous_active=True))

    assert event.payload == {
        "targetId": "monster_001",
        "condition": "poisoned",
        "previousActive": True,
        "active": True,
    }


def test_canonical_event_is_json_serializable() -> None:
    event = build_event()

    serialized = EventSerializer.serialize(event)

    assert serialized["type"] == "ConditionApplied"
    assert serialized["version"] == 1
    assert serialized["payload"] == {
        "targetId": "monster_001",
        "condition": "poisoned",
        "previousActive": False,
        "active": True,
    }
    assert EventSerializer.deserialize(serialized) == event


# --- builder correlation guards -------------------------------------------


@pytest.mark.parametrize(
    ("command", "outcome", "error", "match"),
    [
        (object(), make_outcome(), TypeError, "ApplyConditionCommand"),
        (make_command(), object(), TypeError, "ConditionApplicationResult"),
        (
            make_command(target_id="monster_001"),
            make_outcome(target_id="monster_002"),
            ValueError,
            "target_id",
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
        build_condition_applied_v1(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
            command=command,  # type: ignore[arg-type]
            outcome=outcome,  # type: ignore[arg-type]
        )


def test_builder_rejects_condition_mismatch() -> None:
    command = ApplyConditionCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=ApplyConditionPayload(
            target_id="monster_001", condition=Condition.POISONED
        ),
    )
    outcome = ConditionApplicationResult(
        target_id="monster_001",
        condition=Condition.POISONED,
        previous_active=False,
        active=True,
    )
    object.__setattr__(outcome, "condition", None)

    with pytest.raises(ValueError, match="condition"):
        build_condition_applied_v1(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
            command=command,
            outcome=outcome,
        )


# --- malformed result contract rejected -----------------------------------


def test_builder_rejects_result_with_active_false() -> None:
    with pytest.raises(ValueError, match="active"):
        # A ConditionApplicationResult with active=False cannot even be
        # constructed (its own __post_init__ forbids it); this proves the
        # event builder never has to guard against it separately.
        ConditionApplicationResult(
            target_id="monster_001",
            condition=Condition.POISONED,
            previous_active=True,
            active=False,
        )


# --- immutability -----------------------------------------------------------


def test_built_event_preserves_generic_immutability() -> None:
    event = build_event()

    with pytest.raises(FrozenInstanceError):
        event.type = "ConditionRemoved"  # type: ignore[misc]
    with pytest.raises(TypeError):
        event.payload["active"] = False  # type: ignore[index]


def test_payload_has_exact_fields_and_is_immutable() -> None:
    payload = make_payload()

    assert tuple(field.name for field in fields(payload)) == (
        "target_id",
        "condition",
        "previous_active",
        "active",
    )
    with pytest.raises(FrozenInstanceError):
        payload.active = False  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("target_id", 1),
        ("condition", "poisoned"),
        ("previous_active", 1),
        ("active", 1),
    ],
)
def test_payload_rejects_wrong_runtime_types(
    field_name: str,
    invalid_value: object,
) -> None:
    with pytest.raises(TypeError):
        make_payload(**{field_name: invalid_value})


def test_payload_requires_active_true() -> None:
    with pytest.raises(ValueError, match="active"):
        make_payload(active=False)
