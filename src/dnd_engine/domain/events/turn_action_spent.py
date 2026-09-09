from dataclasses import dataclass, replace
from datetime import datetime

from dnd_engine.domain.commands.attack import AttackCommand
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.state.combat import CombatState


_TURN_ACTION_SPENT_V1_PAYLOAD_FIELDS = frozenset({"combatId"})


@dataclass(frozen=True)
class TurnActionSpentPayloadV1:
    combat_id: str

    def __post_init__(self) -> None:
        if type(self.combat_id) is not str:
            raise TypeError("combat_id must be a str")


def build_turn_action_spent_v1(
    *,
    event_id: str,
    timestamp: datetime,
    command: AttackCommand,
    combat_id: str,
    caused_by: str,
) -> GameEvent:
    if not isinstance(command, AttackCommand):
        raise TypeError("command must be an AttackCommand")
    if type(caused_by) is not str:
        raise TypeError("caused_by must be a str")

    payload = TurnActionSpentPayloadV1(combat_id=combat_id)

    return GameEvent(
        event_id=event_id,
        command_id=command.command_id,
        type="TurnActionSpent",
        version=1,
        campaign_id=command.campaign_id,
        timestamp=timestamp,
        actor_id=command.actor_id,
        caused_by=caused_by,
        payload={"combatId": payload.combat_id},
    )


def _payload_str(value: object, field_name: str) -> str:
    if type(value) is not str:
        raise TypeError(f"payload {field_name} must be a str")
    return value


def apply_turn_action_spent_v1(
    combat: CombatState,
    event: GameEvent,
) -> CombatState:
    if not isinstance(combat, CombatState):
        raise TypeError("combat must be a CombatState")
    if not isinstance(event, GameEvent):
        raise TypeError("event must be a GameEvent")
    if event.type != "TurnActionSpent":
        raise ValueError("event type must be TurnActionSpent")
    if event.version != 1:
        raise ValueError("event version must be 1")
    if event.payload.keys() != _TURN_ACTION_SPENT_V1_PAYLOAD_FIELDS:
        raise ValueError("TurnActionSpent V1 payload has unexpected fields")

    decoded = TurnActionSpentPayloadV1(
        combat_id=_payload_str(event.payload["combatId"], "combatId"),
    )

    if decoded.combat_id != combat.id:
        raise ValueError("event combatId must match combat id")
    if event.actor_id != combat.active_creature_id:
        raise ValueError("event actor_id must match combat active creature")
    if combat.action_spent is not False:
        raise ValueError("combat action_spent must be False before TurnActionSpent")

    return replace(combat, action_spent=True)
