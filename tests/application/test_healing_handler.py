from copy import deepcopy
from dataclasses import fields
from datetime import datetime, timezone

import pytest

from dnd_engine.application.handlers.healing import HealingHandler
from dnd_engine.application.services.event_metadata import EventMetadata
from dnd_engine.domain.commands.healing import (
    ApplyHealingCommand,
    ApplyHealingPayload,
)
from dnd_engine.domain.errors import ErrorCode
from dnd_engine.domain.services.state_store import StateStoreError
from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability_scores import AbilityScores


FIXED_TIMESTAMP = datetime(2026, 8, 28, 17, 0, tzinfo=timezone.utc)


class SpyStateStore:
    def __init__(self, snapshot: StateSnapshot, calls: list[str]) -> None:
        self.snapshot = snapshot
        self._calls = calls
        self.load_calls: list[str] = []
        self.save_calls: list[StateSnapshot] = []

    def load(self, campaign_id: str) -> StateSnapshot:
        self._calls.append("load")
        self.load_calls.append(campaign_id)
        return self.snapshot

    def save(self, snapshot: StateSnapshot) -> None:
        self._calls.append("save")
        self.save_calls.append(snapshot)


class SaveFailingStateStore(SpyStateStore):
    def save(self, snapshot: StateSnapshot) -> None:
        self._calls.append("save")
        self.save_calls.append(snapshot)
        raise StateStoreError("state backend unavailable")


class FixedEventMetadataProvider:
    def __init__(self, calls: list[str], *, fail: bool = False) -> None:
        self._calls = calls
        self._fail = fail
        self.next_calls: list[str] = []

    def next_metadata(self, campaign_id: str) -> EventMetadata:
        self._calls.append("metadata")
        self.next_calls.append(campaign_id)
        if self._fail:
            raise RuntimeError("metadata unavailable")
        return EventMetadata(
            event_id="event_000789",
            timestamp=FIXED_TIMESTAMP,
        )


def make_creature(
    *,
    creature_id: str,
    definition_id: str,
    current_hp: int = 20,
    max_hp: int = 20,
) -> CreatureState:
    return CreatureState(
        id=creature_id,
        definition_id=definition_id,
        ability_scores=AbilityScores(
            strength=10,
            dexterity=10,
            constitution=10,
            intelligence=10,
            wisdom=10,
            charisma=10,
        ),
        current_hp=current_hp,
        max_hp=max_hp,
    )


def make_actor() -> CreatureState:
    return make_creature(creature_id="character_001", definition_id="cleric")


def make_target(
    *, current_hp: int = 7, max_hp: int = 20
) -> CreatureState:
    return make_creature(
        creature_id="monster_001",
        definition_id="goblin",
        current_hp=current_hp,
        max_hp=max_hp,
    )


def make_character(
    *, character_id: str = "character_001", total_level: int = 5
) -> CharacterState:
    return CharacterState(
        id=character_id,
        total_level=total_level,
        saving_throw_proficiencies=frozenset(),
        skill_proficiencies=frozenset(),
        weapon_proficiencies=frozenset(),
    )


def make_snapshot(
    *,
    creatures: tuple[CreatureState, ...] = (),
    characters: tuple[CharacterState, ...] = (),
) -> StateSnapshot:
    return StateSnapshot(
        campaign=CampaignState(
            id="campaign_001",
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
        ),
        creatures=creatures,
        characters=characters,
    )


def make_command(
    *,
    target_id: str = "monster_001",
    actor_id: str = "character_001",
    amount: int = 8,
) -> ApplyHealingCommand:
    return ApplyHealingCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id=actor_id,
        payload=ApplyHealingPayload(target_id=target_id, amount=amount),
    )


def make_dependencies(
    snapshot: StateSnapshot,
    *,
    metadata_fail: bool = False,
) -> tuple[SpyStateStore, FixedEventMetadataProvider, list[str]]:
    calls: list[str] = []
    return (
        SpyStateStore(snapshot, calls),
        FixedEventMetadataProvider(calls, fail=metadata_fail),
        calls,
    )


def handle_with(
    store: SpyStateStore,
    metadata: FixedEventMetadataProvider,
    command: ApplyHealingCommand | None = None,
):
    return HealingHandler(
        state_store=store,
        event_metadata_provider=metadata,
    ).handle(command or make_command())


def test_successful_healing_follows_canonical_lifecycle_and_persists() -> None:
    actor = make_actor()
    target = make_target()
    other_creature = make_creature(
        creature_id="character_002", definition_id="wizard"
    )
    character = make_character()
    other_character = make_character(character_id="character_002", total_level=3)
    snapshot = make_snapshot(
        creatures=(other_creature, target, actor),
        characters=(other_character, character),
    )
    loaded_before = deepcopy(snapshot)
    target_before = deepcopy(target)
    store, metadata, calls = make_dependencies(snapshot)

    result = handle_with(store, metadata)

    assert calls == ["load", "metadata", "save"]
    assert store.load_calls == ["campaign_001"]
    assert metadata.next_calls == ["campaign_001"]

    assert store.snapshot == loaded_before
    assert target == target_before

    assert len(store.save_calls) == 1
    saved_snapshot = store.save_calls[0]
    assert saved_snapshot is not snapshot
    assert saved_snapshot.campaign is snapshot.campaign
    assert saved_snapshot.characters is snapshot.characters

    saved_target = next(
        creature for creature in saved_snapshot.creatures if creature.id == "monster_001"
    )
    assert saved_target is not target
    assert saved_target.current_hp == 15
    assert [
        field.name
        for field in fields(target)
        if getattr(saved_target, field.name) != getattr(target, field.name)
    ] == ["current_hp"]

    saved_other = next(
        creature
        for creature in saved_snapshot.creatures
        if creature.id == "character_002"
    )
    saved_actor = next(
        creature
        for creature in saved_snapshot.creatures
        if creature.id == "character_001"
    )
    assert saved_other is other_creature
    assert saved_actor is actor
    assert [creature.id for creature in saved_snapshot.creatures] == [
        creature.id for creature in snapshot.creatures
    ]

    assert result.success is True
    assert result.command_id == "command_000001"
    assert result.errors == ()
    assert result.outcome is not None
    assert result.outcome.target_id == "monster_001"
    assert result.outcome.amount == 8
    assert result.outcome.previous_hp == 7
    assert result.outcome.max_hp == 20
    assert result.outcome.new_hp == 15

    assert len(result.events) == 1
    event = result.events[0]
    assert event.event_id == "event_000789"
    assert event.type == "HealingApplied"
    assert event.version == 1
    assert event.payload == {
        "targetId": "monster_001",
        "amount": 8,
        "previousHp": 7,
        "maxHp": 20,
        "newHp": 15,
    }


def test_full_hp_no_op_still_emits_event_saves_and_returns_success() -> None:
    target = make_target(current_hp=20, max_hp=20)
    snapshot = make_snapshot(creatures=(target,))
    store, metadata, calls = make_dependencies(snapshot)

    result = handle_with(
        store,
        metadata,
        make_command(
            target_id="monster_001",
            actor_id="monster_001",
            amount=10,
        ),
    )

    assert calls == ["load", "metadata", "save"]
    assert len(store.save_calls) == 1
    saved_target = store.save_calls[0].creatures[0]
    assert saved_target is not target
    assert saved_target.current_hp == 20
    assert result.success is True
    assert result.outcome is not None
    assert result.outcome.new_hp == 20
    assert len(result.events) == 1
    assert result.events[0].type == "HealingApplied"
    assert result.events[0].payload == {
        "targetId": "monster_001",
        "amount": 10,
        "previousHp": 20,
        "maxHp": 20,
        "newHp": 20,
    }


def test_missing_actor_returns_structured_failure_without_metadata_or_save() -> None:
    snapshot = make_snapshot(creatures=(make_target(),))
    store, metadata, calls = make_dependencies(snapshot)

    result = handle_with(store, metadata)

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.ENTITY_NOT_FOUND
    assert result.errors[0].entity_id == "character_001"
    assert result.errors[0].field is None
    assert calls == ["load"]
    assert metadata.next_calls == []
    assert store.save_calls == []


def test_missing_target_returns_structured_failure_without_metadata_or_save() -> None:
    snapshot = make_snapshot(creatures=(make_actor(),))
    store, metadata, calls = make_dependencies(snapshot)

    result = handle_with(store, metadata)

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.ENTITY_NOT_FOUND
    assert result.errors[0].entity_id == "monster_001"
    assert result.errors[0].field == "target_id"
    assert calls == ["load"]
    assert metadata.next_calls == []
    assert store.save_calls == []


def test_applier_invariant_failure_prevents_save(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import dnd_engine.application.handlers.healing as healing_handler_module

    snapshot = make_snapshot(creatures=(make_actor(), make_target()))
    store, metadata, calls = make_dependencies(snapshot)

    def failing_applier(creature: CreatureState, event: object) -> CreatureState:
        raise ValueError("simulated applier invariant failure")

    monkeypatch.setattr(
        healing_handler_module,
        "apply_healing_applied_v1",
        failing_applier,
    )

    with pytest.raises(ValueError, match="simulated applier invariant failure"):
        handle_with(store, metadata)

    assert calls == ["load", "metadata"]
    assert store.save_calls == []


def test_metadata_failure_propagates_without_save() -> None:
    snapshot = make_snapshot(creatures=(make_actor(), make_target()))
    store, metadata, calls = make_dependencies(snapshot, metadata_fail=True)

    with pytest.raises(RuntimeError, match="metadata unavailable"):
        handle_with(store, metadata)

    assert calls == ["load", "metadata"]
    assert store.save_calls == []


def test_save_failure_propagates_and_leaves_loaded_snapshot_unchanged() -> None:
    target = make_target()
    snapshot = make_snapshot(creatures=(make_actor(), target))
    loaded_before = deepcopy(snapshot)
    calls: list[str] = []
    store = SaveFailingStateStore(snapshot, calls)
    metadata = FixedEventMetadataProvider(calls)

    with pytest.raises(StateStoreError, match="backend unavailable"):
        handle_with(store, metadata)

    assert calls == ["load", "metadata", "save"]
    assert len(store.save_calls) == 1
    assert store.snapshot == loaded_before
    assert target.current_hp == 7


def test_save_is_attempted_exactly_once_on_save_failure() -> None:
    snapshot = make_snapshot(creatures=(make_actor(), make_target()))
    calls: list[str] = []
    store = SaveFailingStateStore(snapshot, calls)
    metadata = FixedEventMetadataProvider(calls)

    with pytest.raises(StateStoreError):
        handle_with(store, metadata)

    assert len(store.save_calls) == 1
    assert calls.count("save") == 1
