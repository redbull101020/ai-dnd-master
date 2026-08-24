from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timezone

import pytest

from dnd_engine.domain.errors import EngineError, ErrorCode
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.resolution import ResolutionResult
from dnd_engine.domain.rules.ability_check import AbilityCheckResult
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.dice_roll import DiceRoll


def outcome(*, succeeded: bool = True) -> AbilityCheckResult:
    return AbilityCheckResult(
        ability=Ability.STRENGTH,
        dc=10 if succeeded else 20,
        roll=DiceRoll(expression="1d20", rolls=(10,), total=10),
        modifier=0,
        total=10,
        succeeded=succeeded,
    )


def event(*, command_id: str = "command_000001") -> GameEvent:
    return GameEvent(
        event_id="event_000001",
        command_id=command_id,
        type="AbilityCheckResolved",
        version=1,
        campaign_id="campaign_001",
        timestamp=datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc),
        actor_id="character_001",
        caused_by=None,
        payload={"succeeded": True},
    )


def error() -> EngineError:
    return EngineError(
        code=ErrorCode.ENTITY_NOT_FOUND,
        message="Actor was not found.",
        entity_id="character_001",
    )


def test_error_code_has_exact_closed_values() -> None:
    assert tuple(member.value for member in ErrorCode) == (
        "INVALID_COMMAND",
        "ENTITY_NOT_FOUND",
        "DEFINITION_NOT_FOUND",
        "ACTION_NOT_AVAILABLE",
        "INVALID_TARGET",
        "OUT_OF_RANGE",
        "NOT_VISIBLE",
        "RESOURCE_NOT_AVAILABLE",
        "INVALID_STATE",
        "RULE_VIOLATION",
    )


def test_engine_error_is_typed_and_immutable() -> None:
    value = error()

    assert value.field is None
    with pytest.raises(FrozenInstanceError):
        value.message = "changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        EngineError(code="ENTITY_NOT_FOUND", message="bad")  # type: ignore[arg-type]


def test_resolution_result_has_only_canonical_fields() -> None:
    assert tuple(field.name for field in fields(ResolutionResult)) == (
        "success",
        "command_id",
        "outcome",
        "events",
        "errors",
    )
    assert not hasattr(
        ResolutionResult(
            success=True,
            command_id="command_000001",
            outcome=outcome(),
            events=(),
            errors=(),
        ),
        "rolls",
    )


@pytest.mark.parametrize("gameplay_succeeded", [True, False])
def test_successful_processing_allows_either_gameplay_outcome(
    gameplay_succeeded: bool,
) -> None:
    result = ResolutionResult(
        success=True,
        command_id="command_000001",
        outcome=outcome(succeeded=gameplay_succeeded),
        events=(event(),),
        errors=(),
    )

    assert result.success is True
    assert result.outcome is not None
    assert result.outcome.succeeded is gameplay_succeeded


def test_successful_processing_does_not_require_an_event() -> None:
    result = ResolutionResult(
        success=True,
        command_id="command_000001",
        outcome=outcome(),
        events=(),
        errors=(),
    )

    assert result.events == ()


def test_processing_failure_has_only_structured_errors() -> None:
    result: ResolutionResult[AbilityCheckResult] = ResolutionResult(
        success=False,
        command_id="command_000001",
        outcome=None,
        events=(),
        errors=(error(),),
    )

    assert result.outcome is None
    assert result.events == ()
    assert result.errors == (error(),)


@pytest.mark.parametrize(
    "values",
    [
        {
            "success": True,
            "command_id": "command_000001",
            "outcome": None,
            "events": (),
            "errors": (),
        },
        {
            "success": True,
            "command_id": "command_000001",
            "outcome": outcome(),
            "events": (),
            "errors": (error(),),
        },
        {
            "success": False,
            "command_id": "command_000001",
            "outcome": outcome(),
            "events": (),
            "errors": (error(),),
        },
        {
            "success": False,
            "command_id": "command_000001",
            "outcome": None,
            "events": (event(),),
            "errors": (error(),),
        },
        {
            "success": False,
            "command_id": "command_000001",
            "outcome": None,
            "events": (),
            "errors": (),
        },
    ],
)
def test_resolution_result_rejects_invalid_success_failure_combinations(
    values: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        ResolutionResult(**values)  # type: ignore[arg-type]


def test_resolution_result_rejects_mismatched_event_command_id() -> None:
    with pytest.raises(ValueError):
        ResolutionResult(
            success=True,
            command_id="command_000001",
            outcome=outcome(),
            events=(event(command_id="command_000002"),),
            errors=(),
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [("success", 1), ("command_id", 1), ("events", []), ("errors", [])],
)
def test_resolution_result_rejects_invalid_container_and_scalar_types(
    field_name: str,
    value: object,
) -> None:
    values: dict[str, object] = {
        "success": True,
        "command_id": "command_000001",
        "outcome": outcome(),
        "events": (),
        "errors": (),
    }
    values[field_name] = value

    with pytest.raises(TypeError):
        ResolutionResult(**values)  # type: ignore[arg-type]


def test_resolution_result_is_immutable() -> None:
    result = ResolutionResult(
        success=True,
        command_id="command_000001",
        outcome=outcome(),
        events=(),
        errors=(),
    )

    with pytest.raises(FrozenInstanceError):
        result.success = False  # type: ignore[misc]
