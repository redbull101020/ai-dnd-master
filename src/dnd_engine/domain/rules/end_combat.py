from dataclasses import dataclass

from dnd_engine.domain.commands.end_combat import EndCombatCommand
from dnd_engine.domain.state.combat import CombatState


@dataclass(frozen=True)
class EndCombatResult:
    combat_id: str

    def __post_init__(self) -> None:
        if type(self.combat_id) is not str:
            raise TypeError("combat_id must be a str")


def resolve_end_combat(
    command: EndCombatCommand,
    combat: CombatState,
) -> EndCombatResult:
    if not isinstance(command, EndCombatCommand):
        raise TypeError("command must be an EndCombatCommand")
    if not isinstance(combat, CombatState):
        raise TypeError("combat must be a CombatState")
    if command.payload.combat_id != combat.id:
        raise ValueError("command payload combat_id must match combat id")

    return EndCombatResult(combat_id=combat.id)
