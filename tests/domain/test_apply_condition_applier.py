from copy import deepcopy
from datetime import datetime, timezone

import pytest

from dnd_engine.domain.commands.apply_condition import (
    ApplyConditionCommand,
    ApplyConditionPayload,
)
from dnd_engine.domain.events.apply_condition import (
    apply_condition_applied_v1,
    build_condition_applied_v1,
)
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.rules.apply_condition import ConditionApplicationResult
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.domain.value_objects.condition import Condition


FIXED_TIMESTAMP = datetime(2026, 8, 28, 14, 0, tzinfo=timezone.utc)


def make_creature(
    *,
    creature_id: str = "monster_001",
    definition_id: str = "goblin",
    conditions: frozenset[Condition] = frozenset(),
) -> CreatureState:
    return CreatureState(
        id=creature_id,
        definition_id=definition_id,
        ability_scores=AbilityScores(
            strength=8,
            dexterity=14,
            constitution=10,
            intelligence=10,
            wisdom=8,
            charisma=8,
        ),
        current_hp=7,
        max_hp=7,
        conditions=conditions,
    )


def make_valid_event(
    *,
    target_id: str = "monster_001",
    condition: Condition = Condition.POISONED,
    previous_active: bool = False,
) -> GameEvent:
    command = ApplyConditionCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=ApplyConditionPayload(target_id=target_id, condition=condition),
    )
    outcome = ConditionApplicationResult(
        target_id=target_id,
        condition=condition,
        previous_active=previous_active,
        active=True,
    )
    return build_condition_applied_v1(
        event_id="event_000001",
        timestamp=FIXED_TIMESTAMP,
        command=command,
        outcome=outcome,
    )


def make_raw_event(
    *,
    event_type: str = "ConditionApplied",
    version: int = 1,
    payload: object,
) -> GameEvent:
    return GameEvent(
        event_id="event_000001",
        command_id="command_000001",
        type=event_type,
        version=version,
        campaign_id="campaign_001",
        timestamp=FIXED_TIMESTAMP,
        actor_id="character_001",
        caused_by=None,
        payload=payload,  # type: ignore[arg-type]
    )


CANONICAL_PAYLOAD: dict[str, object] = {
    "targetId": "monster_001",
    "condition": "poisoned",
    "previousActive": False,
    "active": True,
}


# --- deterministic replacement -------------------------------------------


def test_same_event_and_creature_produce_same_replacement() -> None:
    event = make_valid_event(previous_active=False)

    first = apply_condition_applied_v1(make_creature(conditions=frozenset()), event)
    second = apply_condition_applied_v1(make_creature(conditions=frozenset()), event)

    assert first == second


def test_returned_creature_is_a_new_object() -> None:
    creature = make_creature(conditions=frozenset())
    event = make_valid_event(previous_active=False)

    replacement = apply_condition_applied_v1(creature, event)

    assert replacement is not creature


def test_source_creature_is_unchanged() -> None:
    creature = make_creature(conditions=frozenset())
    before = deepcopy(creature)
    event = make_valid_event(previous_active=False)

    apply_condition_applied_v1(creature, event)

    assert creature == before


def test_condition_becomes_active() -> None:
    creature = make_creature(conditions=frozenset())
    event = make_valid_event(previous_active=False)

    replacement = apply_condition_applied_v1(creature, event)

    assert replacement.conditions == frozenset({Condition.POISONED})


@pytest.mark.parametrize(
    "field_name", ["id", "definition_id", "ability_scores", "current_hp", "max_hp"]
)
def test_unrelated_fields_are_preserved(field_name: str) -> None:
    creature = make_creature(conditions=frozenset())
    event = make_valid_event(previous_active=False)

    replacement = apply_condition_applied_v1(creature, event)

    assert getattr(replacement, field_name) == getattr(creature, field_name)


# --- integrity rejection --------------------------------------------------


def test_wrong_target_is_rejected() -> None:
    creature = make_creature(creature_id="monster_001", conditions=frozenset())
    event = make_valid_event(target_id="monster_002", previous_active=False)

    with pytest.raises(ValueError, match="targetId"):
        apply_condition_applied_v1(creature, event)


def test_previous_active_mismatch_is_rejected() -> None:
    creature = make_creature(conditions=frozenset({Condition.POISONED}))
    event = make_valid_event(previous_active=False)

    with pytest.raises(ValueError, match="previousActive"):
        apply_condition_applied_v1(creature, event)


def test_wrong_event_type_is_rejected() -> None:
    creature = make_creature(conditions=frozenset())
    event = make_raw_event(event_type="ConditionRemoved", payload=CANONICAL_PAYLOAD)

    with pytest.raises(ValueError, match="ConditionApplied"):
        apply_condition_applied_v1(creature, event)


def test_wrong_event_version_is_rejected() -> None:
    creature = make_creature(conditions=frozenset())
    event = make_raw_event(version=2, payload=CANONICAL_PAYLOAD)

    with pytest.raises(ValueError, match="version"):
        apply_condition_applied_v1(creature, event)


@pytest.mark.parametrize(
    "payload",
    [
        {"targetId": "monster_001", "condition": "poisoned", "previousActive": False},
        {
            "targetId": "monster_001",
            "condition": "poisoned",
            "previousActive": False,
            "active": True,
            "extra": True,
        },
        {"targetId": 1, "condition": "poisoned", "previousActive": False, "active": True},
        {
            "targetId": "monster_001",
            "condition": 1,
            "previousActive": False,
            "active": True,
        },
        {
            "targetId": "monster_001",
            "condition": "blinded",
            "previousActive": False,
            "active": True,
        },
        {
            "targetId": "monster_001",
            "condition": "poisoned",
            "previousActive": 0,
            "active": True,
        },
        {
            "targetId": "monster_001",
            "condition": "poisoned",
            "previousActive": False,
            "active": 1,
        },
    ],
)
def test_malformed_payload_is_rejected(payload: dict[str, object]) -> None:
    creature = make_creature(conditions=frozenset())
    event = make_raw_event(payload=payload)

    with pytest.raises((TypeError, ValueError)):
        apply_condition_applied_v1(creature, event)


def test_event_with_active_false_is_rejected() -> None:
    creature = make_creature(conditions=frozenset())
    event = make_raw_event(
        payload={
            "targetId": "monster_001",
            "condition": "poisoned",
            "previousActive": False,
            "active": False,
        }
    )

    with pytest.raises(ValueError, match="active"):
        apply_condition_applied_v1(creature, event)


def test_wrong_type_inputs_are_rejected() -> None:
    event = make_valid_event(previous_active=False)

    with pytest.raises(TypeError, match="CreatureState"):
        apply_condition_applied_v1(object(), event)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="GameEvent"):
        apply_condition_applied_v1(make_creature(), object())  # type: ignore[arg-type]


# --- successful no-op and replay limitation --------------------------------


def test_no_op_apply_active_to_active_is_accepted() -> None:
    creature = make_creature(conditions=frozenset({Condition.POISONED}))
    event = make_valid_event(previous_active=True)

    replacement = apply_condition_applied_v1(creature, event)

    assert replacement.conditions == frozenset({Condition.POISONED})


def test_no_op_active_to_active_duplicate_application_is_not_detected() -> None:
    # Narrow, documented limitation mirroring G6A/G6B's 0 -> 0 / maxHp -> maxHp
    # no-op replay gap: without a State revision or an applied Event ID
    # registry, a canonical active -> active no-op Event is indistinguishable
    # from its own duplicate application (docs/ARCHITECTURE.md §3.18 "Exact
    # MVP atomicity boundary").
    event = make_valid_event(previous_active=True)
    creature = make_creature(conditions=frozenset({Condition.POISONED}))

    first = apply_condition_applied_v1(creature, event)
    second = apply_condition_applied_v1(first, event)

    assert first.conditions == frozenset({Condition.POISONED})
    assert second.conditions == frozenset({Condition.POISONED})


def test_state_changing_event_cannot_silently_reapply_to_already_updated_creature() -> (
    None
):
    event = make_valid_event(previous_active=False)
    already_updated = make_creature(conditions=frozenset({Condition.POISONED}))

    with pytest.raises(ValueError, match="previousActive"):
        apply_condition_applied_v1(already_updated, event)


# --- forbidden dependencies -------------------------------------------------


def test_applier_module_has_no_dice_definition_or_io_dependencies() -> None:
    import dnd_engine.domain.events.apply_condition as apply_condition_module

    source = apply_condition_module.__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        contents = handle.read()

    for forbidden in ("DiceEngine", "DefinitionSource", "StateStore", "open(", "Path("):
        assert forbidden not in contents
