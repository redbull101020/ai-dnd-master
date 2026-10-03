from dataclasses import replace
from datetime import datetime

from dnd_engine.domain.commands.move_combatant import MoveCombatantCommand
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.rules.move_combatant import MoveCombatantResult, movement_segment_distance
from dnd_engine.domain.state.combat import CombatPosition, CombatState


_PAYLOAD_FIELDS = frozenset({"combatId", "fromX", "fromY", "toX", "toY", "distance"})


def build_combatant_moved_v1(
    *, event_id: str, timestamp: datetime,
    command: MoveCombatantCommand, outcome: MoveCombatantResult,
) -> GameEvent:
    if not isinstance(command, MoveCombatantCommand):
        raise TypeError("command must be a MoveCombatantCommand")
    if not isinstance(outcome, MoveCombatantResult):
        raise TypeError("outcome must be a MoveCombatantResult")
    if outcome.combat_id != command.payload.combat_id:
        raise ValueError("outcome combat_id must match command combat_id")
    if (outcome.to_x, outcome.to_y) != (command.payload.x, command.payload.y):
        raise ValueError("outcome destination must match command destination")
    return GameEvent(
        event_id=event_id, command_id=command.command_id, type="CombatantMoved",
        version=1, campaign_id=command.campaign_id, timestamp=timestamp,
        actor_id=command.actor_id, caused_by=None,
        payload={"combatId": outcome.combat_id, "fromX": outcome.from_x,
                 "fromY": outcome.from_y, "toX": outcome.to_x,
                 "toY": outcome.to_y, "distance": outcome.distance},
    )


def _payload_int(value: object) -> int:
    if type(value) is not int:
        raise TypeError("Movement payload coordinates and distance must be ints")
    return value


def apply_combatant_moved_v1(combat: CombatState, event: GameEvent) -> CombatState:
    if not isinstance(combat, CombatState):
        raise TypeError("combat must be a CombatState")
    if not isinstance(event, GameEvent):
        raise TypeError("event must be a GameEvent")
    if event.type != "CombatantMoved" or event.version != 1:
        raise ValueError("event must be CombatantMoved version 1")
    if event.payload.keys() != _PAYLOAD_FIELDS:
        raise ValueError("CombatantMoved V1 payload has unexpected fields")
    if type(event.payload["combatId"]) is not str:
        raise TypeError("payload combatId must be a str")
    if event.payload["combatId"] != combat.id:
        raise ValueError("event combatId must match combat id")
    from_x, from_y, to_x, to_y, distance = (
        _payload_int(event.payload[name])
        for name in ("fromX", "fromY", "toX", "toY", "distance")
    )
    if event.actor_id != combat.active_creature_id:
        raise ValueError("event actor must be the active creature")
    matches = [(index, position) for index, position in enumerate(combat.positions)
               if position.creature_id == event.actor_id]
    if len(matches) != 1:
        raise ValueError("actor must have exactly one existing CombatPosition")
    index, position = matches[0]
    if (position.x, position.y) != (from_x, from_y):
        raise ValueError("event source must match current position")
    expected = movement_segment_distance(from_x, from_y, to_x, to_y)
    if expected == 0 or distance != expected:
        raise ValueError("event distance must equal positive segment distance")
    positions = list(combat.positions)
    positions[index] = CombatPosition(position.creature_id, to_x, to_y)
    return replace(combat, positions=tuple(positions), movement_spent=combat.movement_spent + distance)
