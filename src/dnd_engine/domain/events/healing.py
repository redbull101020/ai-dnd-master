from dataclasses import dataclass, replace
from datetime import datetime

from dnd_engine.domain.commands.healing import ApplyHealingCommand
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.rules.healing import HealingResult
from dnd_engine.domain.state.creature import CreatureState


_HEALING_APPLIED_V1_PAYLOAD_FIELDS = frozenset(
    {"targetId", "amount", "previousHp", "maxHp", "newHp"}
)


@dataclass(frozen=True)
class HealingAppliedPayloadV1:
    target_id: str
    amount: int
    previous_hp: int
    max_hp: int
    new_hp: int

    def __post_init__(self) -> None:
        if type(self.target_id) is not str:
            raise TypeError("target_id must be a str")
        for field_name in ("amount", "previous_hp", "max_hp", "new_hp"):
            if type(getattr(self, field_name)) is not int:
                raise TypeError(f"{field_name} must be an int")


def build_healing_applied_v1(
    *,
    event_id: str,
    timestamp: datetime,
    command: ApplyHealingCommand,
    outcome: HealingResult,
) -> GameEvent:
    if not isinstance(command, ApplyHealingCommand):
        raise TypeError("command must be an ApplyHealingCommand")
    if not isinstance(outcome, HealingResult):
        raise TypeError("outcome must be a HealingResult")
    if outcome.target_id != command.payload.target_id:
        raise ValueError("outcome target_id must match command payload target_id")
    if outcome.amount != command.payload.amount:
        raise ValueError("outcome amount must match command payload amount")

    payload = HealingAppliedPayloadV1(
        target_id=outcome.target_id,
        amount=outcome.amount,
        previous_hp=outcome.previous_hp,
        max_hp=outcome.max_hp,
        new_hp=outcome.new_hp,
    )

    return GameEvent(
        event_id=event_id,
        command_id=command.command_id,
        type="HealingApplied",
        version=1,
        campaign_id=command.campaign_id,
        timestamp=timestamp,
        actor_id=command.actor_id,
        caused_by=None,
        payload={
            "targetId": payload.target_id,
            "amount": payload.amount,
            "previousHp": payload.previous_hp,
            "maxHp": payload.max_hp,
            "newHp": payload.new_hp,
        },
    )


def _payload_str(value: object, field_name: str) -> str:
    if type(value) is not str:
        raise TypeError(f"payload {field_name} must be a str")
    return value


def _payload_int(value: object, field_name: str) -> int:
    if type(value) is not int:
        raise TypeError(f"payload {field_name} must be an int")
    return value


def apply_healing_applied_v1(
    creature: CreatureState,
    event: GameEvent,
) -> CreatureState:
    if not isinstance(creature, CreatureState):
        raise TypeError("creature must be a CreatureState")
    if not isinstance(event, GameEvent):
        raise TypeError("event must be a GameEvent")
    if event.type != "HealingApplied":
        raise ValueError("event type must be HealingApplied")
    if event.version != 1:
        raise ValueError("event version must be 1")
    if event.payload.keys() != _HEALING_APPLIED_V1_PAYLOAD_FIELDS:
        raise ValueError("HealingApplied V1 payload has unexpected fields")

    decoded = HealingAppliedPayloadV1(
        target_id=_payload_str(event.payload["targetId"], "targetId"),
        amount=_payload_int(event.payload["amount"], "amount"),
        previous_hp=_payload_int(event.payload["previousHp"], "previousHp"),
        max_hp=_payload_int(event.payload["maxHp"], "maxHp"),
        new_hp=_payload_int(event.payload["newHp"], "newHp"),
    )

    if decoded.target_id != creature.id:
        raise ValueError("event targetId must match creature id")
    if decoded.previous_hp != creature.current_hp:
        raise ValueError("event previousHp must match creature current_hp")
    if decoded.max_hp != creature.max_hp:
        raise ValueError("event maxHp must match creature max_hp")

    return replace(creature, current_hp=decoded.new_hp)
