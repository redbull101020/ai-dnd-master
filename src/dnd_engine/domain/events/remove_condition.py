from dataclasses import dataclass, replace
from datetime import datetime

from dnd_engine.domain.commands.remove_condition import RemoveConditionCommand
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.rules.remove_condition import ConditionRemovalResult
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.value_objects.condition import Condition


_CONDITION_REMOVED_V1_PAYLOAD_FIELDS = frozenset(
    {"targetId", "condition", "previousActive", "active"}
)


@dataclass(frozen=True)
class ConditionRemovedPayloadV1:
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
        if self.active is not False:
            raise ValueError("active must be False for ConditionRemoved")


def build_condition_removed_v1(
    *,
    event_id: str,
    timestamp: datetime,
    command: RemoveConditionCommand,
    outcome: ConditionRemovalResult,
) -> GameEvent:
    if not isinstance(command, RemoveConditionCommand):
        raise TypeError("command must be a RemoveConditionCommand")
    if not isinstance(outcome, ConditionRemovalResult):
        raise TypeError("outcome must be a ConditionRemovalResult")
    if outcome.target_id != command.payload.target_id:
        raise ValueError("outcome target_id must match command payload target_id")
    if outcome.condition != command.payload.condition:
        raise ValueError("outcome condition must match command payload condition")

    payload = ConditionRemovedPayloadV1(
        target_id=outcome.target_id,
        condition=outcome.condition,
        previous_active=outcome.previous_active,
        active=outcome.active,
    )

    return GameEvent(
        event_id=event_id,
        command_id=command.command_id,
        type="ConditionRemoved",
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


def apply_condition_removed_v1(
    creature: CreatureState,
    event: GameEvent,
) -> CreatureState:
    if not isinstance(creature, CreatureState):
        raise TypeError("creature must be a CreatureState")
    if not isinstance(event, GameEvent):
        raise TypeError("event must be a GameEvent")
    if event.type != "ConditionRemoved":
        raise ValueError("event type must be ConditionRemoved")
    if event.version != 1:
        raise ValueError("event version must be 1")
    if event.payload.keys() != _CONDITION_REMOVED_V1_PAYLOAD_FIELDS:
        raise ValueError("ConditionRemoved V1 payload has unexpected fields")

    decoded = ConditionRemovedPayloadV1(
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

    return replace(creature, conditions=creature.conditions - {decoded.condition})
