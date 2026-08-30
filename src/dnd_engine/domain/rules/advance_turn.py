from dataclasses import dataclass

from dnd_engine.domain.commands.advance_turn import AdvanceTurnCommand
from dnd_engine.domain.state.combat import CombatState


@dataclass(frozen=True)
class AdvanceTurnResult:
    combat_id: str
    previous_active_creature_id: str
    active_creature_id: str
    previous_round: int
    round: int

    def __post_init__(self) -> None:
        if type(self.combat_id) is not str:
            raise TypeError("combat_id must be a str")
        if type(self.previous_active_creature_id) is not str:
            raise TypeError("previous_active_creature_id must be a str")
        if type(self.active_creature_id) is not str:
            raise TypeError("active_creature_id must be a str")
        if type(self.previous_round) is not int:
            raise TypeError("previous_round must be an int")
        if type(self.round) is not int:
            raise TypeError("round must be an int")
        if self.round not in (self.previous_round, self.previous_round + 1):
            raise ValueError("round must equal previous_round or previous_round + 1")


def resolve_advance_turn(
    command: AdvanceTurnCommand,
    combat: CombatState,
) -> AdvanceTurnResult:
    if not isinstance(command, AdvanceTurnCommand):
        raise TypeError("command must be an AdvanceTurnCommand")
    if not isinstance(combat, CombatState):
        raise TypeError("combat must be a CombatState")
    if command.payload.combat_id != combat.id:
        raise ValueError("command payload combat_id must match combat id")

    next_index = (combat.active_index + 1) % len(combat.order)
    next_round = combat.round + 1 if next_index == 0 else combat.round

    return AdvanceTurnResult(
        combat_id=combat.id,
        previous_active_creature_id=combat.active_creature_id,
        active_creature_id=combat.order[next_index],
        previous_round=combat.round,
        round=next_round,
    )
