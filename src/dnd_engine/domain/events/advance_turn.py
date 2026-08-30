from dataclasses import dataclass, replace
from datetime import datetime

from dnd_engine.domain.commands.advance_turn import AdvanceTurnCommand
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.rules.advance_turn import AdvanceTurnResult
from dnd_engine.domain.state.combat import CombatState


_TURN_ADVANCED_V1_PAYLOAD_FIELDS = frozenset(
    {
        "combatId",
        "previousActiveCreatureId",
        "activeCreatureId",
        "previousRound",
        "round",
    }
)


@dataclass(frozen=True)
class TurnAdvancedPayloadV1:
    combat_id: str
    previous_active_creature_id: str
    active_creature_id: str
    previous_round: int
    round: int

    def __post_init__(self) -> None:
        for field_name in (
            "combat_id",
            "previous_active_creature_id",
            "active_creature_id",
        ):
            if type(getattr(self, field_name)) is not str:
                raise TypeError(f"{field_name} must be a str")
        for field_name in ("previous_round", "round"):
            if type(getattr(self, field_name)) is not int:
                raise TypeError(f"{field_name} must be an int")


def build_turn_advanced_v1(
    *,
    event_id: str,
    timestamp: datetime,
    command: AdvanceTurnCommand,
    outcome: AdvanceTurnResult,
) -> GameEvent:
    if not isinstance(command, AdvanceTurnCommand):
        raise TypeError("command must be an AdvanceTurnCommand")
    if not isinstance(outcome, AdvanceTurnResult):
        raise TypeError("outcome must be an AdvanceTurnResult")
    if outcome.combat_id != command.payload.combat_id:
        raise ValueError("outcome combat_id must match command payload combat_id")

    payload = TurnAdvancedPayloadV1(
        combat_id=outcome.combat_id,
        previous_active_creature_id=outcome.previous_active_creature_id,
        active_creature_id=outcome.active_creature_id,
        previous_round=outcome.previous_round,
        round=outcome.round,
    )

    return GameEvent(
        event_id=event_id,
        command_id=command.command_id,
        type="TurnAdvanced",
        version=1,
        campaign_id=command.campaign_id,
        timestamp=timestamp,
        actor_id=command.actor_id,
        caused_by=None,
        payload={
            "combatId": payload.combat_id,
            "previousActiveCreatureId": payload.previous_active_creature_id,
            "activeCreatureId": payload.active_creature_id,
            "previousRound": payload.previous_round,
            "round": payload.round,
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


def apply_turn_advanced_v1(
    combat: CombatState,
    event: GameEvent,
) -> CombatState:
    if not isinstance(combat, CombatState):
        raise TypeError("combat must be a CombatState")
    if not isinstance(event, GameEvent):
        raise TypeError("event must be a GameEvent")
    if event.type != "TurnAdvanced":
        raise ValueError("event type must be TurnAdvanced")
    if event.version != 1:
        raise ValueError("event version must be 1")
    if event.payload.keys() != _TURN_ADVANCED_V1_PAYLOAD_FIELDS:
        raise ValueError("TurnAdvanced V1 payload has unexpected fields")

    decoded = TurnAdvancedPayloadV1(
        combat_id=_payload_str(event.payload["combatId"], "combatId"),
        previous_active_creature_id=_payload_str(
            event.payload["previousActiveCreatureId"], "previousActiveCreatureId"
        ),
        active_creature_id=_payload_str(
            event.payload["activeCreatureId"], "activeCreatureId"
        ),
        previous_round=_payload_int(event.payload["previousRound"], "previousRound"),
        round=_payload_int(event.payload["round"], "round"),
    )

    if decoded.combat_id != combat.id:
        raise ValueError("event combatId must match combat id")
    if decoded.previous_active_creature_id != combat.active_creature_id:
        raise ValueError(
            "event previousActiveCreatureId must match combat active creature"
        )
    if decoded.previous_round != combat.round:
        raise ValueError("event previousRound must match combat round")

    new_active_index = combat.order.index(decoded.active_creature_id)
    return replace(combat, round=decoded.round, active_index=new_active_index)
