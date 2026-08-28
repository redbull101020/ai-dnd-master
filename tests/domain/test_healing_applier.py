from copy import deepcopy
from datetime import datetime, timezone

import pytest

from dnd_engine.domain.commands.healing import (
    ApplyHealingCommand,
    ApplyHealingPayload,
)
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.events.healing import (
    apply_healing_applied_v1,
    build_healing_applied_v1,
)
from dnd_engine.domain.rules.healing import HealingResult
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.value_objects.ability_scores import AbilityScores


FIXED_TIMESTAMP = datetime(2026, 8, 28, 16, 30, tzinfo=timezone.utc)


def make_creature(
    *,
    creature_id: str = "monster_001",
    definition_id: str = "goblin",
    current_hp: int = 7,
    max_hp: int = 20,
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
    amount: int = 8,
    previous_hp: int = 7,
    max_hp: int = 20,
    new_hp: int = 15,
) -> GameEvent:
    command = ApplyHealingCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=ApplyHealingPayload(target_id=target_id, amount=amount),
    )
    outcome = HealingResult(
        target_id=target_id,
        amount=amount,
        previous_hp=previous_hp,
        max_hp=max_hp,
        new_hp=new_hp,
    )
    return build_healing_applied_v1(
        event_id="event_000001",
        timestamp=FIXED_TIMESTAMP,
        command=command,
        outcome=outcome,
    )


def make_raw_event(
    *,
    event_type: str = "HealingApplied",
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
    "amount": 8,
    "previousHp": 7,
    "maxHp": 20,
    "newHp": 15,
}


# --- deterministic replacement -----------------------------------------


def test_same_event_and_creature_produce_same_replacement() -> None:
    event = make_valid_event()

    first = apply_healing_applied_v1(make_creature(), event)
    second = apply_healing_applied_v1(make_creature(), event)

    assert first == second


def test_returned_creature_is_a_new_object() -> None:
    creature = make_creature()
    event = make_valid_event()

    replacement = apply_healing_applied_v1(creature, event)

    assert replacement is not creature


def test_source_creature_is_unchanged() -> None:
    creature = make_creature()
    before = deepcopy(creature)
    event = make_valid_event()

    apply_healing_applied_v1(creature, event)

    assert creature == before


def test_current_hp_changed_as_event_says() -> None:
    creature = make_creature()
    event = make_valid_event()

    replacement = apply_healing_applied_v1(creature, event)

    assert replacement.current_hp == 15


@pytest.mark.parametrize(
    "field_name", ["id", "definition_id", "ability_scores", "max_hp"]
)
def test_unrelated_fields_are_preserved(field_name: str) -> None:
    creature = make_creature()
    event = make_valid_event()

    replacement = apply_healing_applied_v1(creature, event)

    assert getattr(replacement, field_name) == getattr(creature, field_name)


# --- integrity rejection ------------------------------------------------


def test_wrong_target_is_rejected() -> None:
    creature = make_creature(creature_id="monster_001")
    event = make_valid_event(target_id="monster_002")

    with pytest.raises(ValueError, match="targetId"):
        apply_healing_applied_v1(creature, event)


def test_previous_hp_mismatch_is_rejected() -> None:
    creature = make_creature(current_hp=8)
    event = make_valid_event(previous_hp=7)

    with pytest.raises(ValueError, match="previousHp"):
        apply_healing_applied_v1(creature, event)


def test_max_hp_mismatch_is_rejected() -> None:
    creature = make_creature(max_hp=21)
    event = make_valid_event(max_hp=20)

    with pytest.raises(ValueError, match="maxHp"):
        apply_healing_applied_v1(creature, event)


def test_wrong_event_type_is_rejected() -> None:
    creature = make_creature()
    event = make_raw_event(event_type="DamageApplied", payload=CANONICAL_PAYLOAD)

    with pytest.raises(ValueError, match="HealingApplied"):
        apply_healing_applied_v1(creature, event)


def test_wrong_event_version_is_rejected() -> None:
    creature = make_creature()
    event = make_raw_event(version=2, payload=CANONICAL_PAYLOAD)

    with pytest.raises(ValueError, match="version"):
        apply_healing_applied_v1(creature, event)


@pytest.mark.parametrize(
    "payload",
    [
        {
            "targetId": "monster_001",
            "amount": 8,
            "previousHp": 7,
            "maxHp": 20,
        },
        {
            "targetId": "monster_001",
            "amount": 8,
            "previousHp": 7,
            "maxHp": 20,
            "newHp": 15,
            "extra": True,
        },
    ],
)
def test_missing_or_extra_payload_field_is_rejected(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="unexpected fields"):
        apply_healing_applied_v1(make_creature(), make_raw_event(payload=payload))


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("targetId", 1),
        ("amount", "8"),
        ("previousHp", "7"),
        ("maxHp", "20"),
        ("newHp", "15"),
        ("amount", True),
        ("previousHp", True),
        ("maxHp", True),
        ("newHp", True),
    ],
)
def test_wrong_payload_field_type_is_rejected(
    field_name: str,
    invalid_value: object,
) -> None:
    payload = dict(CANONICAL_PAYLOAD)
    payload[field_name] = invalid_value

    with pytest.raises(TypeError):
        apply_healing_applied_v1(make_creature(), make_raw_event(payload=payload))


@pytest.mark.parametrize("new_hp", [-1, 21])
def test_invalid_replacement_is_rejected_by_creature_state_invariants(
    new_hp: int,
) -> None:
    payload = dict(CANONICAL_PAYLOAD)
    payload["newHp"] = new_hp

    with pytest.raises(ValueError, match="current_hp"):
        apply_healing_applied_v1(make_creature(), make_raw_event(payload=payload))


def test_wrong_type_inputs_are_rejected() -> None:
    event = make_valid_event()

    with pytest.raises(TypeError, match="CreatureState"):
        apply_healing_applied_v1(object(), event)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="GameEvent"):
        apply_healing_applied_v1(make_creature(), object())  # type: ignore[arg-type]


# --- replay limitation ---------------------------------------------------


def test_state_changing_event_cannot_silently_reapply() -> None:
    event = make_valid_event(previous_hp=7, new_hp=15)
    already_updated = make_creature(current_hp=15)

    with pytest.raises(ValueError, match="previousHp"):
        apply_healing_applied_v1(already_updated, event)


def test_full_hp_no_op_event_is_accepted() -> None:
    creature = make_creature(current_hp=20, max_hp=20)
    event = make_valid_event(
        amount=10,
        previous_hp=20,
        max_hp=20,
        new_hp=20,
    )

    replacement = apply_healing_applied_v1(creature, event)

    assert replacement is not creature
    assert replacement.current_hp == 20


def test_full_hp_no_op_duplicate_application_is_not_detected() -> None:
    # Narrow, documented limitation: without a State revision or an applied
    # Event ID registry, a canonical 20 -> 20 no-op Event is indistinguishable
    # from its own duplicate application. This is intentionally not guarded
    # against here (see docs/ARCHITECTURE.md §3.18 "Exact MVP atomicity
    # boundary", where replay is explicitly not guaranteed).
    event = make_valid_event(
        amount=10,
        previous_hp=20,
        max_hp=20,
        new_hp=20,
    )
    creature = make_creature(current_hp=20, max_hp=20)

    first = apply_healing_applied_v1(creature, event)
    second = apply_healing_applied_v1(first, event)

    assert first.current_hp == 20
    assert second.current_hp == 20


# --- forbidden dependencies and rule ownership -------------------------


def test_applier_module_has_no_forbidden_dependencies_or_healing_formula() -> None:
    import dnd_engine.domain.events.healing as healing_module

    source = healing_module.__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        contents = handle.read()

    for forbidden in (
        "DiceEngine",
        "DefinitionSource",
        "StateStore",
        "EventMetadataProvider",
        "Application",
        "filesystem",
        "open(",
        "Path(",
        "min(",
    ):
        assert forbidden not in contents
