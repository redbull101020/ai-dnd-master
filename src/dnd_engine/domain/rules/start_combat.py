from dataclasses import dataclass

from dnd_engine.domain.commands.start_combat import StartCombatCommand
from dnd_engine.domain.rules.ability import ability_modifier
from dnd_engine.domain.rules.d20 import resolve_d20_roll
from dnd_engine.domain.services.dice import DiceEngine
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.value_objects.d20 import D20Roll, RollMode


@dataclass(frozen=True)
class InitiativeEntry:
    creature_id: str
    roll: D20Roll
    modifier: int
    total: int

    def __post_init__(self) -> None:
        if type(self.creature_id) is not str:
            raise TypeError("creature_id must be a str")
        if not isinstance(self.roll, D20Roll):
            raise TypeError("roll must be a D20Roll")
        if type(self.modifier) is not int:
            raise TypeError("modifier must be an int")
        if type(self.total) is not int:
            raise TypeError("total must be an int")
        if self.total != self.roll.selected + self.modifier:
            raise ValueError("total must equal roll.selected plus modifier")


@dataclass(frozen=True)
class StartCombatResult:
    combat_id: str
    round: int
    order: tuple[str, ...]
    entries: tuple[InitiativeEntry, ...]

    def __post_init__(self) -> None:
        if type(self.combat_id) is not str:
            raise TypeError("combat_id must be a str")
        if type(self.round) is not int:
            raise TypeError("round must be an int")
        if self.round != 1:
            raise ValueError("round must be 1 for a freshly started combat")
        if type(self.order) is not tuple:
            raise TypeError("order must be a tuple")
        if type(self.entries) is not tuple:
            raise TypeError("entries must be a tuple")
        if not all(isinstance(entry, InitiativeEntry) for entry in self.entries):
            raise TypeError("entries must contain only InitiativeEntry values")
        if self.order != tuple(entry.creature_id for entry in self.entries):
            raise ValueError("order must match entries in the same sequence")
        if len(self.order) == 0:
            raise ValueError("order must not be empty")
        if len(set(self.order)) != len(self.order):
            raise ValueError("order must not contain duplicate creature ids")
        for previous, following in zip(self.entries, self.entries[1:]):
            if previous.total < following.total:
                raise ValueError("entries must be ordered by descending total")


def resolve_start_combat(
    command: StartCombatCommand,
    participants: tuple[CreatureState, ...],
    dice: DiceEngine,
    *,
    roll_modes: tuple[RollMode, ...],
) -> StartCombatResult:
    if not isinstance(command, StartCombatCommand):
        raise TypeError("command must be a StartCombatCommand")
    if type(participants) is not tuple:
        raise TypeError("participants must be a tuple")
    if not all(isinstance(participant, CreatureState) for participant in participants):
        raise TypeError("participants must contain only CreatureState values")
    if tuple(participant.id for participant in participants) != (
        command.payload.participant_ids
    ):
        raise ValueError(
            "participants must match command payload participant_ids in order"
        )
    if type(roll_modes) is not tuple:
        raise TypeError("roll_modes must be a tuple")
    if len(roll_modes) != len(participants):
        raise ValueError("roll_modes must have the same length as participants")
    if not all(isinstance(mode, RollMode) for mode in roll_modes):
        raise TypeError("roll_modes must contain only RollMode values")

    rolled_entries = []
    for participant, roll_mode in zip(participants, roll_modes):
        modifier = ability_modifier(participant.ability_scores.dexterity)
        roll = resolve_d20_roll(dice, roll_mode)
        rolled_entries.append(
            InitiativeEntry(
                creature_id=participant.id,
                roll=roll,
                modifier=modifier,
                total=roll.selected + modifier,
            )
        )

    dexterity_by_id = {
        participant.id: participant.ability_scores.dexterity
        for participant in participants
    }

    def sort_key(entry: InitiativeEntry) -> tuple[int, int, str]:
        return (-entry.total, -dexterity_by_id[entry.creature_id], entry.creature_id)

    ordered_entries = tuple(sorted(rolled_entries, key=sort_key))

    return StartCombatResult(
        combat_id=command.payload.combat_id,
        round=1,
        order=tuple(entry.creature_id for entry in ordered_entries),
        entries=ordered_entries,
    )
