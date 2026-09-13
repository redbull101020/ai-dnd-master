from dataclasses import dataclass
from datetime import datetime

from dnd_engine.domain.commands.end_combat import EndCombatCommand
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.rules.end_combat import EndCombatResult
from dnd_engine.domain.state.combat import CombatState


_COMBAT_ENDED_V1_PAYLOAD_FIELDS = frozenset({"combatId"})


@dataclass(frozen=True)
class CombatEndedPayloadV1:
    combat_id: str

    def __post_init__(self) -> None:
        if type(self.combat_id) is not str:
            raise TypeError("combat_id must be a str")


def build_combat_ended_v1(
    *,
    event_id: str,
    timestamp: datetime,
    command: EndCombatCommand,
    outcome: EndCombatResult,
) -> GameEvent:
    if not isinstance(command, EndCombatCommand):
        raise TypeError("command must be an EndCombatCommand")
    if not isinstance(outcome, EndCombatResult):
        raise TypeError("outcome must be an EndCombatResult")
    if outcome.combat_id != command.payload.combat_id:
        raise ValueError("outcome combat_id must match command payload combat_id")

    payload = CombatEndedPayloadV1(combat_id=outcome.combat_id)

    return GameEvent(
        event_id=event_id,
        command_id=command.command_id,
        type="CombatEnded",
        version=1,
        campaign_id=command.campaign_id,
        timestamp=timestamp,
        actor_id=command.actor_id,
        caused_by=None,
        payload={"combatId": payload.combat_id},
    )


def _payload_str(value: object, field_name: str) -> str:
    if type(value) is not str:
        raise TypeError(f"payload {field_name} must be a str")
    return value


def apply_combat_ended_v1(
    combat: CombatState,
    event: GameEvent,
) -> None:
    if not isinstance(combat, CombatState):
        raise TypeError("combat must be a CombatState")
    if not isinstance(event, GameEvent):
        raise TypeError("event must be a GameEvent")
    if event.type != "CombatEnded":
        raise ValueError("event type must be CombatEnded")
    if event.version != 1:
        raise ValueError("event version must be 1")
    if event.payload.keys() != _COMBAT_ENDED_V1_PAYLOAD_FIELDS:
        raise ValueError("CombatEnded V1 payload has unexpected fields")

    decoded = CombatEndedPayloadV1(
        combat_id=_payload_str(event.payload["combatId"], "combatId"),
    )

    if decoded.combat_id != combat.id:
        raise ValueError("event combatId must match combat id")

    return None
