from dataclasses import FrozenInstanceError, fields, replace

import pytest

from dnd_engine.domain.commands.move_combatant import MoveCombatantCommand, MoveCombatantPayload


def test_exact_shape_and_immutability():
    payload = MoveCombatantPayload("combat", -3, -4)
    command = MoveCombatantCommand("command", "campaign", "monster", payload)
    assert [f.name for f in fields(payload)] == ["combat_id", "x", "y"]
    assert command.type == "MoveCombatantCommand"
    with pytest.raises(FrozenInstanceError):
        payload.x = 2
    with pytest.raises(FrozenInstanceError):
        command.actor_id = "other"


@pytest.mark.parametrize("name", ["combat_id", "x", "y"])
@pytest.mark.parametrize("value", [True, None, 1.5, (), "3"])
def test_payload_strict_types(name, value):
    if name == "combat_id" and type(value) is str:
        return
    with pytest.raises(TypeError):
        replace(MoveCombatantPayload("combat", 0, 0), **{name: value})


@pytest.mark.parametrize("name", ["command_id", "campaign_id", "actor_id", "payload"])
def test_command_strict_types(name):
    with pytest.raises(TypeError):
        replace(MoveCombatantCommand("c", "p", "a", MoveCombatantPayload("b", 0, 0)), **{name: None})
