from dataclasses import dataclass, replace
from datetime import datetime

from dnd_engine.domain.commands.place_combatant import PlaceCombatantCommand
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.rules.place_combatant import PlaceCombatantResult
from dnd_engine.domain.state.combat import CombatPosition, CombatState


_COMBATANT_PLACED_V1_PAYLOAD_FIELDS = frozenset(
    {"combatId", "creatureId", "x", "y"}
)


@dataclass(frozen=True)
class CombatantPlacedPayloadV1:
    combat_id: str
    creature_id: str
    x: int
    y: int

    def __post_init__(self) -> None:
        for field_name in ("combat_id", "creature_id"):
            if type(getattr(self, field_name)) is not str:
                raise TypeError(f"{field_name} must be a str")
        for field_name in ("x", "y"):
            if type(getattr(self, field_name)) is not int:
                raise TypeError(f"{field_name} must be an int")


def build_combatant_placed_v1(
    *,
    event_id: str,
    timestamp: datetime,
    command: PlaceCombatantCommand,
    outcome: PlaceCombatantResult,
) -> GameEvent:
    if not isinstance(command, PlaceCombatantCommand):
        raise TypeError("command must be a PlaceCombatantCommand")
    if not isinstance(outcome, PlaceCombatantResult):
        raise TypeError("outcome must be a PlaceCombatantResult")
    if outcome.combat_id != command.payload.combat_id:
        raise ValueError("outcome combat_id must match command payload combat_id")
    if outcome.creature_id != command.payload.creature_id:
        raise ValueError(
            "outcome creature_id must match command payload creature_id"
        )
    if outcome.x != command.payload.x:
        raise ValueError("outcome x must match command payload x")
    if outcome.y != command.payload.y:
        raise ValueError("outcome y must match command payload y")

    payload = CombatantPlacedPayloadV1(
        combat_id=outcome.combat_id,
        creature_id=outcome.creature_id,
        x=outcome.x,
        y=outcome.y,
    )

    return GameEvent(
        event_id=event_id,
        command_id=command.command_id,
        type="CombatantPlaced",
        version=1,
        campaign_id=command.campaign_id,
        timestamp=timestamp,
        actor_id=command.actor_id,
        caused_by=None,
        payload={
            "combatId": payload.combat_id,
            "creatureId": payload.creature_id,
            "x": payload.x,
            "y": payload.y,
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


def apply_combatant_placed_v1(
    combat: CombatState,
    event: GameEvent,
) -> CombatState:
    if not isinstance(combat, CombatState):
        raise TypeError("combat must be a CombatState")
    if not isinstance(event, GameEvent):
        raise TypeError("event must be a GameEvent")
    if event.type != "CombatantPlaced":
        raise ValueError("event type must be CombatantPlaced")
    if event.version != 1:
        raise ValueError("event version must be 1")
    if event.payload.keys() != _COMBATANT_PLACED_V1_PAYLOAD_FIELDS:
        raise ValueError("CombatantPlaced V1 payload has unexpected fields")

    decoded = CombatantPlacedPayloadV1(
        combat_id=_payload_str(event.payload["combatId"], "combatId"),
        creature_id=_payload_str(event.payload["creatureId"], "creatureId"),
        x=_payload_int(event.payload["x"], "x"),
        y=_payload_int(event.payload["y"], "y"),
    )

    if decoded.combat_id != combat.id:
        raise ValueError("event combatId must match combat id")
    if decoded.creature_id not in combat.order:
        raise ValueError("event creatureId must be a member of combat order")
    if any(
        position.creature_id == decoded.creature_id
        for position in combat.positions
    ):
        raise ValueError("event creatureId must not already have a CombatPosition")

    new_position = CombatPosition(
        creature_id=decoded.creature_id,
        x=decoded.x,
        y=decoded.y,
    )

    return replace(combat, positions=combat.positions + (new_position,))
