from dataclasses import dataclass, replace
from datetime import datetime

from dnd_engine.domain.commands.apply_condition import ApplyConditionCommand
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.rules.apply_condition import ConditionApplicationResult
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.value_objects.condition import Condition


_CONDITION_APPLIED_V1_PAYLOAD_FIELDS = frozenset(
    {"targetId", "condition", "previousActive", "active"}
)


@dataclass(frozen=True)
class ConditionAppliedPayloadV1:
    target_id: str
    condition: Condition
    previous_active: bool
    active: bool

    def __post_init__(self) -> None:
        if type(self.target_id) is not str:
            raise TypeError("target_id must be a str")
        if not isinstance(self.condition, Condition):
            raise TypeError("condition must be a Condition")
        if type(self.previous_active) is not bool:
            raise TypeError("previous_active must be a bool")
        if type(self.active) is not bool:
            raise TypeError("active must be a bool")
        if self.active is not True:
            raise ValueError("active must be True for ConditionApplied")


def build_condition_applied_v1(
    *,
    event_id: str,
    timestamp: datetime,
    command: ApplyConditionCommand,
    outcome: ConditionApplicationResult,
) -> GameEvent:
    if not isinstance(command, ApplyConditionCommand):
        raise TypeError("command must be an ApplyConditionCommand")
    if not isinstance(outcome, ConditionApplicationResult):
        raise TypeError("outcome must be a ConditionApplicationResult")
    if outcome.target_id != command.payload.target_id:
        raise ValueError("outcome target_id must match command payload target_id")
    if outcome.condition != command.payload.condition:
        raise ValueError("outcome condition must match command payload condition")

    payload = ConditionAppliedPayloadV1(
        target_id=outcome.target_id,
        condition=outcome.condition,
        previous_active=outcome.previous_active,
        active=outcome.active,
    )

    return GameEvent(
        event_id=event_id,
        command_id=command.command_id,
        type="ConditionApplied",
        version=1,
        campaign_id=command.campaign_id,
        timestamp=timestamp,
        actor_id=command.actor_id,
        caused_by=None,
        payload={
            "targetId": payload.target_id,
            "condition": payload.condition.value,
            "previousActive": payload.previous_active,
            "active": payload.active,
        },
    )


def _payload_str(value: object, field_name: str) -> str:
    if type(value) is not str:
        raise TypeError(f"payload {field_name} must be a str")
    return value


def _payload_bool(value: object, field_name: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"payload {field_name} must be a bool")
    return value


def _payload_condition(value: object, field_name: str) -> Condition:
    if type(value) is not str:
        raise TypeError(f"payload {field_name} must be a str")
    try:
        return Condition(value)
    except ValueError as error:
        raise ValueError(
            f"payload {field_name} has unknown Condition value: {value!r}"
        ) from error


def apply_condition_applied_v1(
    creature: CreatureState,
    event: GameEvent,
) -> CreatureState:
    if not isinstance(creature, CreatureState):
        raise TypeError("creature must be a CreatureState")
    if not isinstance(event, GameEvent):
        raise TypeError("event must be a GameEvent")
    if event.type != "ConditionApplied":
        raise ValueError("event type must be ConditionApplied")
    if event.version != 1:
        raise ValueError("event version must be 1")
    if event.payload.keys() != _CONDITION_APPLIED_V1_PAYLOAD_FIELDS:
        raise ValueError("ConditionApplied V1 payload has unexpected fields")

    decoded = ConditionAppliedPayloadV1(
        target_id=_payload_str(event.payload["targetId"], "targetId"),
        condition=_payload_condition(event.payload["condition"], "condition"),
        previous_active=_payload_bool(
            event.payload["previousActive"], "previousActive"
        ),
        active=_payload_bool(event.payload["active"], "active"),
    )

    if decoded.target_id != creature.id:
        raise ValueError("event targetId must match creature id")
    if decoded.previous_active != (decoded.condition in creature.conditions):
        raise ValueError(
            "event previousActive must match creature condition membership"
        )

    return replace(creature, conditions=creature.conditions | {decoded.condition})
