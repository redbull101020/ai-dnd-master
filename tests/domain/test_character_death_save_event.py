from datetime import datetime, timezone

import pytest

from dnd_engine.domain.events.character_death_save import (
    apply_character_death_save_failure_recorded_v1,
    apply_character_death_save_resolved_v1,
    build_character_death_save_failure_recorded_v1,
    build_character_death_save_resolved_v1,
)
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.rules.character_death_save import (
    CharacterDeathSaveFailureResult,
    CharacterDeathSaveResult,
)
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.value_objects.d20 import D20Roll, RollMode


NOW = datetime(2026, 9, 11, tzinfo=timezone.utc)


def character(**overrides: object) -> CharacterState:
    values: dict[str, object] = {"id": "character_001", "total_level": 4, "saving_throw_proficiencies": frozenset(), "skill_proficiencies": frozenset(), "weapon_proficiencies": frozenset({"dagger"}), "death_save_successes": 1, "death_save_failures": 1}
    values.update(overrides)
    return CharacterState(**values)  # type: ignore[arg-type]


def resolved_event() -> GameEvent:
    return build_character_death_save_resolved_v1(event_id="event_2", timestamp=NOW, command_id="command_1", campaign_id="campaign_1", actor_id="character_001", caused_by="event_1", outcome=CharacterDeathSaveResult("character_001", D20Roll(RollMode.NORMAL, (10,), 10), 1, 1, False, False, 2, 1, False, False, 0))


def failure_event() -> GameEvent:
    return build_character_death_save_failure_recorded_v1(event_id="event_3", timestamp=NOW, command_id="command_1", campaign_id="campaign_1", actor_id="monster_001", caused_by="event_2", outcome=CharacterDeathSaveFailureResult("character_001", 1, False, False, True, 3, False, True))


def test_resolved_builder_copies_exact_payload_and_correlation() -> None:
    event = resolved_event()
    assert (event.command_id, event.campaign_id, event.actor_id, event.caused_by) == ("command_1", "campaign_1", "character_001", "event_1")
    assert event.payload == {"characterId": "character_001", "roll": {"mode": "normal", "rolls": (10,), "selected": 10}, "previousSuccesses": 1, "previousFailures": 1, "previousStable": False, "previousDead": False, "successes": 2, "failures": 1, "stable": False, "dead": False}


@pytest.mark.parametrize(
    ("builder", "outcome"),
    [
        (
            build_character_death_save_resolved_v1,
            CharacterDeathSaveResult("character_001", D20Roll(RollMode.NORMAL, (10,), 10), 1, 1, False, False, 2, 1, False, False, 0),
        ),
        (
            build_character_death_save_failure_recorded_v1,
            CharacterDeathSaveFailureResult("character_001", 1, False, False, True, 3, False, True),
        ),
    ],
)
@pytest.mark.parametrize("field_name", ["actor_id", "caused_by"])
def test_automatic_consequence_builders_require_string_correlation(
    builder: object,
    outcome: object,
    field_name: str,
) -> None:
    arguments: dict[str, object] = {
        "event_id": "event_2", "timestamp": NOW, "command_id": "command_1",
        "campaign_id": "campaign_1", "actor_id": "character_001",
        "caused_by": "event_1", "outcome": outcome,
    }
    arguments[field_name] = None
    with pytest.raises(TypeError, match=field_name):
        builder(**arguments)  # type: ignore[operator]


def test_resolved_applier_replaces_only_lifecycle_fields() -> None:
    before = character()
    after = apply_character_death_save_resolved_v1(before, resolved_event())
    assert (after.death_save_successes, after.death_save_failures) == (2, 1)
    assert (after.id, after.total_level, after.weapon_proficiencies) == (before.id, before.total_level, before.weapon_proficiencies)


def test_failure_event_preserves_successes_and_has_exact_payload() -> None:
    event = failure_event()
    after = apply_character_death_save_failure_recorded_v1(character(), event)
    assert after.death_save_successes == 1
    assert event.payload == {"characterId": "character_001", "previousFailures": 1, "failures": 3, "previousStable": False, "stable": False, "previousDead": False, "dead": True, "criticalHit": True}


@pytest.mark.parametrize(("event", "apply"), [(resolved_event(), apply_character_death_save_resolved_v1), (failure_event(), apply_character_death_save_failure_recorded_v1)])
def test_appliers_reject_wrong_type_version_extra_fields_and_stale_state(event: GameEvent, apply: object) -> None:
    applier = apply  # type: ignore[assignment]
    for replacement in (
        {**event.__dict__, "version": 2},
        {**event.__dict__, "type": "Other"},
        {**event.__dict__, "payload": {**event.payload, "extra": 1}},
    ):
        with pytest.raises(ValueError):
            applier(character(), GameEvent(**replacement))  # type: ignore[operator,arg-type]
    with pytest.raises(ValueError, match="stale"):
        applier(character(death_save_failures=2), event)  # type: ignore[operator]
