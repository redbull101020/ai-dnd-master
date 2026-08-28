from copy import deepcopy
from datetime import datetime, timezone

import pytest

from dnd_engine.domain.commands.damage import ApplyDamageCommand, ApplyDamagePayload
from dnd_engine.domain.events.damage import apply_damage_applied_v1, build_damage_applied_v1
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.rules.damage import DamageResult
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.value_objects.ability_scores import AbilityScores


FIXED_TIMESTAMP = datetime(2026, 8, 28, 14, 0, tzinfo=timezone.utc)


def make_creature(
    *,
    creature_id: str = "monster_001",
    definition_id: str = "goblin",
    current_hp: int = 7,
    max_hp: int = 7,
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
        current_hp=current_hp,
        max_hp=max_hp,
    )


def make_valid_event(
    *,
    target_id: str = "monster_001",
    amount: int = 3,
    previous_hp: int = 7,
    new_hp: int = 4,
) -> GameEvent:
    command = ApplyDamageCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=ApplyDamagePayload(target_id=target_id, amount=amount),
    )
    outcome = DamageResult(
        target_id=target_id,
        amount=amount,
        previous_hp=previous_hp,
        new_hp=new_hp,
    )
    return build_damage_applied_v1(
        event_id="event_000001",
        timestamp=FIXED_TIMESTAMP,
        command=command,
        outcome=outcome,
    )


def make_raw_event(
    *,
    event_type: str = "DamageApplied",
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
    "amount": 3,
    "previousHp": 7,
    "newHp": 4,
}


# --- deterministic replacement -----------------------------------------


def test_same_event_and_creature_produce_same_replacement() -> None:
    event = make_valid_event(previous_hp=7, new_hp=4)

    first = apply_damage_applied_v1(make_creature(current_hp=7), event)
    second = apply_damage_applied_v1(make_creature(current_hp=7), event)

    assert first == second


def test_returned_creature_is_a_new_object() -> None:
    creature = make_creature(current_hp=7)
    event = make_valid_event(previous_hp=7, new_hp=4)

    replacement = apply_damage_applied_v1(creature, event)

    assert replacement is not creature


def test_source_creature_is_unchanged() -> None:
    creature = make_creature(current_hp=7)
    before = deepcopy(creature)
    event = make_valid_event(previous_hp=7, new_hp=4)

    apply_damage_applied_v1(creature, event)

    assert creature == before


def test_current_hp_changed_as_event_says() -> None:
    creature = make_creature(current_hp=7)
    event = make_valid_event(previous_hp=7, new_hp=4)

    replacement = apply_damage_applied_v1(creature, event)

    assert replacement.current_hp == 4


@pytest.mark.parametrize(
    "field_name", ["id", "definition_id", "ability_scores", "max_hp"]
)
def test_unrelated_fields_are_preserved(field_name: str) -> None:
    creature = make_creature(current_hp=7, max_hp=7)
    event = make_valid_event(previous_hp=7, new_hp=4)

    replacement = apply_damage_applied_v1(creature, event)

    assert getattr(replacement, field_name) == getattr(creature, field_name)


def test_replacement_satisfies_creature_state_invariants() -> None:
    creature = make_creature(current_hp=7, max_hp=7)
    event = make_valid_event(amount=7, previous_hp=7, new_hp=0)

    replacement = apply_damage_applied_v1(creature, event)

    assert 0 <= replacement.current_hp <= replacement.max_hp


# --- integrity rejection -------------------------------------------------


def test_wrong_target_is_rejected() -> None:
    creature = make_creature(creature_id="monster_001", current_hp=7)
    event = make_valid_event(target_id="monster_002", previous_hp=7, new_hp=4)

    with pytest.raises(ValueError, match="targetId"):
        apply_damage_applied_v1(creature, event)


def test_previous_hp_mismatch_is_rejected() -> None:
    creature = make_creature(current_hp=5)
    event = make_valid_event(previous_hp=7, new_hp=4)

    with pytest.raises(ValueError, match="previousHp"):
        apply_damage_applied_v1(creature, event)


def test_wrong_event_type_is_rejected() -> None:
    creature = make_creature(current_hp=7)
    event = make_raw_event(event_type="AttackResolved", payload=CANONICAL_PAYLOAD)

    with pytest.raises(ValueError, match="DamageApplied"):
        apply_damage_applied_v1(creature, event)


def test_wrong_event_version_is_rejected() -> None:
    creature = make_creature(current_hp=7)
    event = make_raw_event(version=2, payload=CANONICAL_PAYLOAD)

    with pytest.raises(ValueError, match="version"):
        apply_damage_applied_v1(creature, event)


@pytest.mark.parametrize(
    "payload",
    [
        {"targetId": "monster_001", "amount": 3, "previousHp": 7},
        {
            "targetId": "monster_001",
            "amount": 3,
            "previousHp": 7,
            "newHp": 4,
            "extra": True,
        },
        {"targetId": 1, "amount": 3, "previousHp": 7, "newHp": 4},
        {"targetId": "monster_001", "amount": "3", "previousHp": 7, "newHp": 4},
        {"targetId": "monster_001", "amount": True, "previousHp": 7, "newHp": 4},
    ],
)
def test_malformed_payload_is_rejected(payload: dict[str, object]) -> None:
    creature = make_creature(current_hp=7)
    event = make_raw_event(payload=payload)

    with pytest.raises((TypeError, ValueError)):
        apply_damage_applied_v1(creature, event)


def test_wrong_type_inputs_are_rejected() -> None:
    event = make_valid_event(previous_hp=7, new_hp=4)

    with pytest.raises(TypeError, match="CreatureState"):
        apply_damage_applied_v1(object(), event)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="GameEvent"):
        apply_damage_applied_v1(make_creature(), object())  # type: ignore[arg-type]


# --- replay limitation ----------------------------------------------------


def test_state_changing_event_cannot_silently_reapply_to_already_updated_creature() -> (
    None
):
    event = make_valid_event(previous_hp=7, new_hp=4)
    already_updated = make_creature(current_hp=4)

    with pytest.raises(ValueError, match="previousHp"):
        apply_damage_applied_v1(already_updated, event)


def test_no_op_zero_to_zero_event_is_accepted() -> None:
    creature = make_creature(current_hp=0, max_hp=7)
    event = make_valid_event(previous_hp=0, new_hp=0)

    replacement = apply_damage_applied_v1(creature, event)

    assert replacement.current_hp == 0


def test_no_op_zero_to_zero_duplicate_application_is_not_detected() -> None:
    # Narrow, documented limitation: without a State revision or an applied
    # Event ID registry, a canonical 0 -> 0 no-op Event is indistinguishable
    # from its own duplicate application. This is intentionally not guarded
    # against here (see docs/ARCHITECTURE.md §3.18 "Exact MVP atomicity
    # boundary", where replay is explicitly not guaranteed).
    event = make_valid_event(previous_hp=0, new_hp=0)
    creature = make_creature(current_hp=0, max_hp=7)

    first = apply_damage_applied_v1(creature, event)
    second = apply_damage_applied_v1(first, event)

    assert first.current_hp == 0
    assert second.current_hp == 0


# --- forbidden dependencies ----------------------------------------------


def test_applier_module_has_no_dice_definition_or_io_dependencies() -> None:
    import dnd_engine.domain.events.damage as damage_module

    source = damage_module.__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        contents = handle.read()

    for forbidden in ("DiceEngine", "DefinitionSource", "StateStore", "open(", "Path("):
        assert forbidden not in contents
