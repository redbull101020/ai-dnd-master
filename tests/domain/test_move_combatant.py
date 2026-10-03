from dataclasses import FrozenInstanceError, replace

import pytest

from dnd_engine.domain.commands.move_combatant import MoveCombatantCommand, MoveCombatantPayload
from dnd_engine.domain.rules.move_combatant import resolve_move_combatant
from dnd_engine.domain.state.combat import CombatPosition, CombatState


def setup_move(x=3, y=4):
    position = CombatPosition("monster", 0, 0)
    combat = CombatState("combat", 3, ("monster", "other"), 0, (position,), True, 7)
    command = MoveCombatantCommand("command", "campaign", "monster", MoveCombatantPayload("combat", x, y))
    return command, combat, position


@pytest.mark.parametrize("x,y,distance", [(3,4,5), (1,1,2), (0,5,5), (-3,-4,5), (10**100,1,10**100+1)])
def test_exact_segment_and_cumulative_result(x, y, distance):
    command, combat, position = setup_move(x, y)
    outcome = resolve_move_combatant(command, combat, position)
    assert (outcome.from_x, outcome.from_y, outcome.to_x, outcome.to_y) == (0,0,x,y)
    assert outcome.distance == distance
    assert outcome.movement_spent == 7 + distance
    assert combat.movement_spent == 7
    with pytest.raises(FrozenInstanceError):
        outcome.distance = 0


def test_no_op_is_not_a_result():
    with pytest.raises(ValueError):
        resolve_move_combatant(*setup_move(0, 0))


@pytest.mark.parametrize("case", ["combat", "actor", "stale", "subject", "missing"])
def test_resolver_rejects_bad_correlations(case):
    command, combat, position = setup_move()
    if case == "combat":
        command = replace(command, payload=replace(command.payload, combat_id="wrong"))
    elif case == "actor":
        command = replace(command, actor_id="other")
    elif case == "stale":
        position = replace(position, x=1)
    elif case == "subject":
        position = replace(position, creature_id="other")
    else:
        combat = replace(combat, positions=())
    with pytest.raises(ValueError):
        resolve_move_combatant(command, combat, position)


@pytest.mark.parametrize("index", [0,1,2])
def test_resolver_rejects_wrong_types(index):
    args = list(setup_move())
    args[index] = object()
    with pytest.raises(TypeError):
        resolve_move_combatant(*args)


@pytest.mark.parametrize("field", ["combat_id", "from_x", "from_y", "to_x", "to_y", "distance", "movement_spent"])
def test_result_strict_types(field):
    outcome = resolve_move_combatant(*setup_move())
    with pytest.raises(TypeError):
        replace(outcome, **{field: True})


@pytest.mark.parametrize("changes", [{"distance": 4}, {"movement_spent": -1}, {"to_x": 0, "to_y": 0, "distance": 0}])
def test_result_rejects_invalid_segment(changes):
    with pytest.raises(ValueError):
        replace(resolve_move_combatant(*setup_move()), **changes)
