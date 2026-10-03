from dataclasses import dataclass
from math import isqrt

from dnd_engine.domain.commands.move_combatant import MoveCombatantCommand
from dnd_engine.domain.state.combat import CombatPosition, CombatState


def movement_segment_distance(from_x: int, from_y: int, to_x: int, to_y: int) -> int:
    for value in (from_x, from_y, to_x, to_y):
        if type(value) is not int:
            raise TypeError("segment coordinates must be ints")
    squared = (to_x - from_x) ** 2 + (to_y - from_y) ** 2
    root = isqrt(squared)
    return root if root * root == squared else root + 1


@dataclass(frozen=True)
class MoveCombatantResult:
    combat_id: str
    from_x: int
    from_y: int
    to_x: int
    to_y: int
    distance: int
    movement_spent: int

    def __post_init__(self) -> None:
        if type(self.combat_id) is not str:
            raise TypeError("combat_id must be a str")
        for name in ("from_x", "from_y", "to_x", "to_y", "distance", "movement_spent"):
            if type(getattr(self, name)) is not int:
                raise TypeError(f"{name} must be an int")
        expected = movement_segment_distance(self.from_x, self.from_y, self.to_x, self.to_y)
        if expected == 0 or self.distance != expected:
            raise ValueError("distance must equal the positive segment distance")
        if self.movement_spent < self.distance:
            raise ValueError("movement_spent must include segment distance")


def resolve_move_combatant(
    command: MoveCombatantCommand,
    combat: CombatState,
    position: CombatPosition,
) -> MoveCombatantResult:
    if not isinstance(command, MoveCombatantCommand):
        raise TypeError("command must be a MoveCombatantCommand")
    if not isinstance(combat, CombatState):
        raise TypeError("combat must be a CombatState")
    if not isinstance(position, CombatPosition):
        raise TypeError("position must be a CombatPosition")
    if command.payload.combat_id != combat.id:
        raise ValueError("command combat_id must match combat id")
    if command.actor_id != combat.active_creature_id:
        raise ValueError("command actor must be the active creature")
    if position.creature_id != command.actor_id or position not in combat.positions:
        raise ValueError("position must be the actor's current CombatPosition")
    distance = movement_segment_distance(position.x, position.y, command.payload.x, command.payload.y)
    return MoveCombatantResult(
        combat.id, position.x, position.y, command.payload.x, command.payload.y,
        distance, combat.movement_spent + distance,
    )
