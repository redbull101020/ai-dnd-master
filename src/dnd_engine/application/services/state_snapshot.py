from dataclasses import replace

from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.snapshot import StateSnapshot


def replace_creature_in_snapshot(
    snapshot: StateSnapshot,
    replacement: CreatureState,
) -> StateSnapshot:
    if not isinstance(snapshot, StateSnapshot):
        raise TypeError("snapshot must be a StateSnapshot")
    if not isinstance(replacement, CreatureState):
        raise TypeError("replacement must be a CreatureState")

    matching_creatures = sum(
        creature.id == replacement.id for creature in snapshot.creatures
    )
    if matching_creatures != 1:
        raise ValueError(
            "replacement CreatureState id must match exactly one CreatureState "
            "in snapshot"
        )

    replacement_creatures = tuple(
        replacement if creature.id == replacement.id else creature
        for creature in snapshot.creatures
    )

    return replace(snapshot, creatures=replacement_creatures)
