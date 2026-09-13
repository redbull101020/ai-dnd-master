from dataclasses import dataclass

from dnd_engine.domain.commands.place_combatant import PlaceCombatantCommand
from dnd_engine.domain.state.combat import CombatState


@dataclass(frozen=True)
class PlaceCombatantResult:
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


def resolve_place_combatant(
    command: PlaceCombatantCommand,
    combat: CombatState,
) -> PlaceCombatantResult:
    if not isinstance(command, PlaceCombatantCommand):
        raise TypeError("command must be a PlaceCombatantCommand")
    if not isinstance(combat, CombatState):
        raise TypeError("combat must be a CombatState")
    if command.payload.combat_id != combat.id:
        raise ValueError("command payload combat_id must match combat id")

    return PlaceCombatantResult(
        combat_id=combat.id,
        creature_id=command.payload.creature_id,
        x=command.payload.x,
        y=command.payload.y,
    )
