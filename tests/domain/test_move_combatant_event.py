from dataclasses import replace
from datetime import datetime, timezone

import pytest

from dnd_engine.domain.commands.move_combatant import MoveCombatantCommand, MoveCombatantPayload
from dnd_engine.domain.events.move_combatant import apply_combatant_moved_v1, build_combatant_moved_v1
from dnd_engine.domain.rules.move_combatant import resolve_move_combatant
from dnd_engine.domain.state.combat import CombatPosition, CombatState
from dnd_engine.infrastructure.persistence.json.event_serializer import EventSerializer


def setup_event():
    positions = (CombatPosition("first", 3, 4), CombatPosition("monster", 0, 0), CombatPosition("last", 9, 9))
    combat = CombatState("combat", 3, ("first", "monster", "last"), 1, positions, True, 40)
    command = MoveCombatantCommand("command", "campaign", "monster", MoveCombatantPayload("combat", 3, 4))
    outcome = resolve_move_combatant(command, combat, positions[1])
    event = build_combatant_moved_v1(event_id="event", timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), command=command, outcome=outcome)
    return combat, command, outcome, event


def test_exact_event_and_roundtrip():
    _, command, _, event = setup_event()
    assert (event.type, event.version, event.actor_id, event.caused_by) == ("CombatantMoved", 1, "monster", None)
    assert (event.command_id, event.campaign_id) == (command.command_id, command.campaign_id)
    assert event.payload == {"combatId": "combat", "fromX": 0, "fromY": 0, "toX": 3, "toY": 4, "distance": 5}
    assert EventSerializer.deserialize(EventSerializer.serialize(event)) == event


def test_same_index_replacement_preserves_every_other_fact_and_allows_occupancy():
    combat, _, _, event = setup_event()
    updated = apply_combatant_moved_v1(combat, event)
    assert updated == replace(combat, positions=(combat.positions[0], CombatPosition("monster", 3, 4), combat.positions[2]), movement_spent=45)
    assert updated.positions[0] is combat.positions[0]
    assert updated.positions[2] is combat.positions[2]
    assert combat.positions[1] == CombatPosition("monster", 0, 0)
    assert combat.movement_spent == 40


@pytest.mark.parametrize("field", ["combatId", "fromX", "fromY", "toX", "toY", "distance"])
@pytest.mark.parametrize("value", [True, None, 1.5, ()])
def test_payload_primitive_types(field, value):
    combat, _, _, event = setup_event()
    with pytest.raises(TypeError):
        apply_combatant_moved_v1(combat, replace(event, payload={**event.payload, field: value}))


@pytest.mark.parametrize("field", ["fromX", "fromY", "toX", "toY", "distance"])
def test_string_coordinates_rejected(field):
    combat, _, _, event = setup_event()
    with pytest.raises(TypeError):
        apply_combatant_moved_v1(combat, replace(event, payload={**event.payload, field: "1"}))


@pytest.mark.parametrize("changes", [{"combatId": "wrong"}, {"fromX": 1}, {"fromY": 1}, {"distance": 4}, {"distance": -5}, {"toX": 0, "toY": 0, "distance": 0}, {"movementSpent": 45}])
def test_bad_payload_integrity(changes):
    combat, _, _, event = setup_event()
    with pytest.raises(ValueError):
        apply_combatant_moved_v1(combat, replace(event, payload={**event.payload, **changes}))


@pytest.mark.parametrize("field", ["combatId", "fromX", "fromY", "toX", "toY", "distance"])
def test_missing_field(field):
    combat, _, _, event = setup_event()
    payload = dict(event.payload)
    del payload[field]
    with pytest.raises(ValueError):
        apply_combatant_moved_v1(combat, replace(event, payload=payload))


@pytest.mark.parametrize("changes", [{"type": "Other"}, {"version": 2}, {"actor_id": "first"}, {"actor_id": None}])
def test_bad_envelope(changes):
    combat, _, _, event = setup_event()
    with pytest.raises(ValueError):
        apply_combatant_moved_v1(combat, replace(event, **changes))


def test_missing_position():
    combat, _, _, event = setup_event()
    with pytest.raises(ValueError):
        apply_combatant_moved_v1(replace(combat, positions=()), event)


@pytest.mark.parametrize("field", ["combat_id", "to_x", "to_y"])
def test_builder_correlation(field):
    _, command, outcome, _ = setup_event()
    payload_field = {"combat_id": "combat_id", "to_x": "x", "to_y": "y"}[field]
    value = "wrong" if field == "combat_id" else 10
    command = replace(command, payload=replace(command.payload, **{payload_field: value}))
    with pytest.raises(ValueError):
        build_combatant_moved_v1(event_id="e", timestamp=datetime(2026,1,1,tzinfo=timezone.utc), command=command, outcome=outcome)


@pytest.mark.parametrize("argument", ["command", "outcome"])
def test_builder_wrong_types(argument):
    _, command, outcome, event = setup_event()
    args = dict(event_id="e", timestamp=event.timestamp, command=command, outcome=outcome)
    args[argument] = object()
    with pytest.raises(TypeError):
        build_combatant_moved_v1(**args)


@pytest.mark.parametrize("index", [0, 1])
def test_applier_wrong_types(index):
    combat, _, _, event = setup_event()
    args = [combat, event]
    args[index] = object()
    with pytest.raises(TypeError):
        apply_combatant_moved_v1(*args)
