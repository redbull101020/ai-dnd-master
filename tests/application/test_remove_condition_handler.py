from copy import deepcopy
from datetime import datetime, timezone

import pytest

from dnd_engine.application.handlers.remove_condition import RemoveConditionHandler
from dnd_engine.application.services.event_metadata import EventMetadata
from dnd_engine.domain.commands.remove_condition import (
    RemoveConditionCommand,
    RemoveConditionPayload,
)
from dnd_engine.domain.errors import ErrorCode
from dnd_engine.domain.services.state_store import StateStoreError
from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.domain.value_objects.condition import Condition


FIXED_TIMESTAMP = datetime(2026, 8, 28, 18, 30, tzinfo=timezone.utc)


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
    conditions: frozenset[Condition] = frozenset(),
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
        current_hp=20,
        max_hp=20,
        conditions=conditions,
    )


def make_actor() -> CreatureState:
    return make_creature(creature_id="character_001", definition_id="fighter")


def make_target(*, conditions: frozenset[Condition] = frozenset()) -> CreatureState:
    return make_creature(
        creature_id="monster_001", definition_id="goblin", conditions=conditions
    )


def make_character(
    *, character_id: str = "character_001", total_level: int = 5
) -> CharacterState:
    return CharacterState(
        id=character_id,
        total_level=total_level,
        saving_throw_proficiencies=frozenset(),
        skill_proficiencies=frozenset(),
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
    condition: Condition = Condition.POISONED,
) -> RemoveConditionCommand:
    return RemoveConditionCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=RemoveConditionPayload(target_id=target_id, condition=condition),
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
    command: RemoveConditionCommand | None = None,
):
    return RemoveConditionHandler(
        state_store=store,
        event_metadata_provider=metadata,
    ).handle(command or make_command())


# --- lifecycle order -----------------------------------------------------


def test_successful_condition_removal_follows_canonical_lifecycle_and_persists() -> (
    None
):
    actor = make_actor()
    character = make_character()
    target = make_target(conditions=frozenset({Condition.POISONED}))
    other_creature = make_creature(creature_id="character_002", definition_id="wizard")
    other_character = make_character(character_id="character_002", total_level=3)
    snapshot = make_snapshot(
        creatures=(other_creature, target, actor),
        characters=(other_character, character),
    )
    loaded_before = deepcopy(snapshot)
    store, metadata, calls = make_dependencies(snapshot)

    result = handle_with(store, metadata, make_command())

    assert calls == ["load", "metadata", "save"]
    assert store.load_calls == ["campaign_001"]
    assert metadata.next_calls == ["campaign_001"]

    # loaded snapshot/object graph observationally unchanged
    assert store.snapshot == loaded_before
    assert target.conditions == frozenset({Condition.POISONED})

    assert len(store.save_calls) == 1
    saved_snapshot = store.save_calls[0]
    assert saved_snapshot is not snapshot
    assert saved_snapshot.campaign == snapshot.campaign
    assert saved_snapshot.characters == snapshot.characters

    saved_target = next(
        creature for creature in saved_snapshot.creatures if creature.id == "monster_001"
    )
    assert saved_target.conditions == frozenset()
    assert saved_target is not target

    saved_other = next(
        creature for creature in saved_snapshot.creatures if creature.id == "character_002"
    )
    assert saved_other is other_creature

    saved_actor = next(
        creature for creature in saved_snapshot.creatures if creature.id == "character_001"
    )
    assert saved_actor is actor

    # ordering preserved
    assert [creature.id for creature in saved_snapshot.creatures] == [
        creature.id for creature in snapshot.creatures
    ]

    assert result.success is True
    assert result.command_id == "command_000001"
    assert result.errors == ()
    assert result.outcome is not None
    assert result.outcome.target_id == "monster_001"
    assert result.outcome.condition is Condition.POISONED
    assert result.outcome.previous_active is True
    assert result.outcome.active is False

    assert len(result.events) == 1
    event = result.events[0]
    assert event.event_id == "event_000789"
    assert event.type == "ConditionRemoved"
    assert event.version == 1
    assert event.payload == {
        "targetId": "monster_001",
        "condition": "poisoned",
        "previousActive": True,
        "active": False,
    }


def test_successful_no_op_removal_when_already_absent_still_persists() -> None:
    actor = make_actor()
    target = make_target()
    snapshot = make_snapshot(creatures=(actor, target))
    store, metadata, calls = make_dependencies(snapshot)

    result = handle_with(store, metadata, make_command())

    # no-op is not short-circuited: full lifecycle still runs
    assert calls == ["load", "metadata", "save"]
    assert len(store.save_calls) == 1

    saved_snapshot = store.save_calls[0]
    saved_target = next(
        creature for creature in saved_snapshot.creatures if creature.id == "monster_001"
    )
    assert saved_target.conditions == frozenset()

    assert result.success is True
    assert result.outcome.previous_active is False
    assert result.outcome.active is False

    assert len(result.events) == 1
    event = result.events[0]
    assert event.payload == {
        "targetId": "monster_001",
        "condition": "poisoned",
        "previousActive": False,
        "active": False,
    }


# --- missing actor / target -----------------------------------------------


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


# --- resolver failure -------------------------------------------------


def test_resolver_failure_prevents_save(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import dnd_engine.application.handlers.remove_condition as handler_module

    snapshot = make_snapshot(creatures=(make_actor(), make_target()))
    store, metadata, calls = make_dependencies(snapshot)

    def failing_resolver(command: object, target: object) -> None:
        raise ValueError("simulated resolver failure")

    monkeypatch.setattr(
        handler_module, "resolve_condition_removal", failing_resolver
    )

    with pytest.raises(ValueError, match="simulated resolver failure"):
        handle_with(store, metadata)

    assert calls == ["load"]
    assert metadata.next_calls == []
    assert store.save_calls == []


# --- Event builder failure ----------------------------------------------


def test_event_builder_failure_prevents_save(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import dnd_engine.application.handlers.remove_condition as handler_module

    snapshot = make_snapshot(creatures=(make_actor(), make_target()))
    store, metadata, calls = make_dependencies(snapshot)

    def failing_builder(**kwargs: object) -> None:
        raise RuntimeError("simulated event builder failure")

    monkeypatch.setattr(
        handler_module, "build_condition_removed_v1", failing_builder
    )

    with pytest.raises(RuntimeError, match="simulated event builder failure"):
        handle_with(store, metadata)

    assert calls == ["load", "metadata"]
    assert store.save_calls == []


# --- applier / invariant failure ------------------------------------------


def test_applier_invariant_failure_prevents_save(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import dnd_engine.application.handlers.remove_condition as handler_module

    snapshot = make_snapshot(creatures=(make_actor(), make_target()))
    store, metadata, calls = make_dependencies(snapshot)

    def failing_applier(creature: CreatureState, event: object) -> CreatureState:
        raise ValueError("simulated applier invariant failure")

    monkeypatch.setattr(
        handler_module, "apply_condition_removed_v1", failing_applier
    )

    with pytest.raises(ValueError, match="simulated applier invariant failure"):
        handle_with(store, metadata)

    assert calls == ["load", "metadata"]
    assert store.save_calls == []


# --- metadata failure -------------------------------------------------


def test_metadata_failure_propagates_without_save() -> None:
    snapshot = make_snapshot(creatures=(make_actor(), make_target()))
    store, metadata, calls = make_dependencies(snapshot, metadata_fail=True)

    with pytest.raises(RuntimeError, match="metadata unavailable"):
        handle_with(store, metadata)

    assert calls == ["load", "metadata"]
    assert store.save_calls == []


# --- save failure -------------------------------------------------------


def test_save_failure_propagates_and_leaves_no_successful_result() -> None:
    snapshot = make_snapshot(creatures=(make_actor(), make_target()))
    calls: list[str] = []
    store = SaveFailingStateStore(snapshot, calls)
    metadata = FixedEventMetadataProvider(calls)
    target_before = deepcopy(make_target())

    with pytest.raises(StateStoreError, match="backend unavailable"):
        handle_with(store, metadata)

    assert calls == ["load", "metadata", "save"]
    assert len(store.save_calls) == 1
    assert store.snapshot.creatures[
        next(
            index
            for index, creature in enumerate(store.snapshot.creatures)
            if creature.id == "monster_001"
        )
    ] == target_before


def test_save_is_attempted_exactly_once_on_save_failure() -> None:
    snapshot = make_snapshot(creatures=(make_actor(), make_target()))
    calls: list[str] = []
    store = SaveFailingStateStore(snapshot, calls)
    metadata = FixedEventMetadataProvider(calls)

    with pytest.raises(StateStoreError):
        handle_with(store, metadata)

    assert len(store.save_calls) == 1
    assert calls.count("save") == 1
