from copy import deepcopy
from datetime import datetime, timezone

import pytest

from dnd_engine.application.handlers.advance_turn import AdvanceTurnHandler
from dnd_engine.application.services.event_metadata import EventMetadata
from dnd_engine.domain.commands.advance_turn import (
    AdvanceTurnCommand,
    AdvanceTurnPayload,
)
from dnd_engine.domain.errors import ErrorCode
from dnd_engine.domain.services.state_store import StateStoreError
from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.combat import CombatState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability_scores import AbilityScores


FIXED_TIMESTAMP = datetime(2026, 8, 30, 15, 0, tzinfo=timezone.utc)


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
        return EventMetadata(event_id="event_000789", timestamp=FIXED_TIMESTAMP)


def make_creature(*, creature_id: str) -> CreatureState:
    return CreatureState(
        id=creature_id,
        definition_id="fighter",
        ability_scores=AbilityScores(10, 10, 10, 10, 10, 10),
        current_hp=10,
        max_hp=10,
    )


def make_combat(**overrides: object) -> CombatState:
    values: dict[str, object] = {
        "id": "combat_001",
        "round": 1,
        "order": ("character_001", "monster_001"),
        "active_index": 0,
    }
    values.update(overrides)
    return CombatState(**values)  # type: ignore[arg-type]


def make_snapshot(
    *,
    creatures: tuple[CreatureState, ...],
    combat: CombatState | None,
) -> StateSnapshot:
    return StateSnapshot(
        campaign=CampaignState(
            id="campaign_001", ruleset_id="dnd_5e", ruleset_version="5.1"
        ),
        creatures=creatures,
        combat=combat,
    )


def make_command(
    *, combat_id: str = "combat_001", actor_id: str = "character_001"
) -> AdvanceTurnCommand:
    return AdvanceTurnCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id=actor_id,
        payload=AdvanceTurnPayload(combat_id=combat_id),
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
    command: AdvanceTurnCommand | None = None,
):
    return AdvanceTurnHandler(
        state_store=store, event_metadata_provider=metadata
    ).handle(command or make_command())


def default_creatures() -> tuple[CreatureState, ...]:
    return (
        make_creature(creature_id="character_001"),
        make_creature(creature_id="monster_001"),
    )


def test_successful_advance_turn_persists_new_active_combatant() -> None:
    combat = make_combat(active_index=0, round=1)
    snapshot = make_snapshot(creatures=default_creatures(), combat=combat)
    loaded_before = deepcopy(snapshot)
    store, metadata, calls = make_dependencies(snapshot)

    result = handle_with(store, metadata)

    assert calls == ["load", "metadata", "save"]
    assert store.load_calls == ["campaign_001"]
    assert metadata.next_calls == ["campaign_001"]
    assert store.snapshot == loaded_before

    assert len(store.save_calls) == 1
    saved_snapshot = store.save_calls[0]
    assert saved_snapshot is not snapshot
    assert saved_snapshot.creatures == snapshot.creatures
    assert saved_snapshot.combat == CombatState(
        id="combat_001",
        round=1,
        order=("character_001", "monster_001"),
        active_index=1,
    )

    assert result.success is True
    assert result.errors == ()
    assert result.outcome is not None
    assert result.outcome.active_creature_id == "monster_001"

    assert len(result.events) == 1
    event = result.events[0]
    assert event.type == "TurnAdvanced"
    assert event.version == 1
    assert event.payload == {
        "combatId": "combat_001",
        "previousActiveCreatureId": "character_001",
        "activeCreatureId": "monster_001",
        "previousRound": 1,
        "round": 1,
    }


def test_advance_turn_wraps_to_next_round_when_persisted() -> None:
    combat = make_combat(active_index=1, round=1)
    snapshot = make_snapshot(creatures=default_creatures(), combat=combat)
    store, metadata, calls = make_dependencies(snapshot)

    result = handle_with(store, metadata, make_command(actor_id="monster_001"))

    assert result.success is True
    assert result.outcome.round == 2
    saved_snapshot = store.save_calls[0]
    assert saved_snapshot.combat.round == 2
    assert saved_snapshot.combat.active_index == 0


def test_no_combat_in_progress_returns_entity_not_found() -> None:
    snapshot = make_snapshot(creatures=default_creatures(), combat=None)
    store, metadata, calls = make_dependencies(snapshot)

    result = handle_with(store, metadata)

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.ENTITY_NOT_FOUND
    assert result.errors[0].entity_id == "combat_001"
    assert result.errors[0].field == "combat_id"
    assert calls == ["load"]
    assert metadata.next_calls == []
    assert store.save_calls == []


def test_combat_id_mismatch_returns_entity_not_found() -> None:
    combat = make_combat(id="combat_other")
    snapshot = make_snapshot(creatures=default_creatures(), combat=combat)
    store, metadata, calls = make_dependencies(snapshot)

    result = handle_with(store, metadata)

    assert result.success is False
    assert result.errors[0].code is ErrorCode.ENTITY_NOT_FOUND
    assert calls == ["load"]
    assert store.save_calls == []


def test_actor_not_active_combatant_returns_action_not_available() -> None:
    combat = make_combat(active_index=0)
    snapshot = make_snapshot(creatures=default_creatures(), combat=combat)
    store, metadata, calls = make_dependencies(snapshot)

    result = handle_with(store, metadata, make_command(actor_id="monster_001"))

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.ACTION_NOT_AVAILABLE
    assert result.errors[0].entity_id == "monster_001"
    assert calls == ["load"]
    assert metadata.next_calls == []
    assert store.save_calls == []


def test_metadata_failure_propagates_without_save() -> None:
    combat = make_combat()
    snapshot = make_snapshot(creatures=default_creatures(), combat=combat)
    store, metadata, calls = make_dependencies(snapshot, metadata_fail=True)

    with pytest.raises(RuntimeError, match="metadata unavailable"):
        handle_with(store, metadata)

    assert calls == ["load", "metadata"]
    assert store.save_calls == []


def test_save_failure_propagates_and_is_attempted_exactly_once() -> None:
    combat = make_combat()
    snapshot = make_snapshot(creatures=default_creatures(), combat=combat)
    calls: list[str] = []
    store = SaveFailingStateStore(snapshot, calls)
    metadata = FixedEventMetadataProvider(calls)

    with pytest.raises(StateStoreError, match="backend unavailable"):
        handle_with(store, metadata)

    assert calls == ["load", "metadata", "save"]
    assert len(store.save_calls) == 1
