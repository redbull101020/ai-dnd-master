import inspect
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from dnd_engine.application.handlers.place_combatant import PlaceCombatantHandler
from dnd_engine.application.services.event_metadata import EventMetadata
from dnd_engine.domain.commands.place_combatant import (
    PlaceCombatantCommand,
    PlaceCombatantPayload,
)
from dnd_engine.domain.errors import ErrorCode
from dnd_engine.domain.services.state_store import StateStoreError
from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.combat import CombatPosition, CombatState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability_scores import AbilityScores


FIXED_TIMESTAMP = datetime(2026, 9, 13, 18, 0, tzinfo=timezone.utc)


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
            event_id=f"event_{789 + len(self.next_calls) - 1:06d}",
            timestamp=FIXED_TIMESTAMP,
        )


def make_creature(*, creature_id: str, current_hp: int = 10) -> CreatureState:
    return CreatureState(
        id=creature_id,
        definition_id="fighter",
        ability_scores=AbilityScores(10, 10, 10, 10, 10, 10),
        current_hp=current_hp,
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
    *,
    combat_id: str = "combat_001",
    creature_id: str = "character_001",
    actor_id: str = "character_gm",
    x: int = 5,
    y: int = 10,
) -> PlaceCombatantCommand:
    return PlaceCombatantCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id=actor_id,
        payload=PlaceCombatantPayload(
            combat_id=combat_id, creature_id=creature_id, x=x, y=y
        ),
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
    command: PlaceCombatantCommand | None = None,
):
    return PlaceCombatantHandler(
        state_store=store, event_metadata_provider=metadata
    ).handle(command or make_command())


def default_creatures() -> tuple[CreatureState, ...]:
    return (
        make_creature(creature_id="character_gm"),
        make_creature(creature_id="character_001"),
        make_creature(creature_id="monster_001"),
    )


def assert_source_snapshot_unchanged(
    store: SpyStateStore, loaded_before: StateSnapshot
) -> None:
    assert store.snapshot == loaded_before


# --- dependency shape ---------------------------------------------------------


def test_handler_has_no_dice_or_definition_dependency() -> None:
    parameters = inspect.signature(PlaceCombatantHandler.__init__).parameters
    assert "dice" not in parameters
    assert "definition_source" not in parameters


# --- successful placement ------------------------------------------------------


def test_successful_placement_persists_new_position() -> None:
    existing_position = CombatPosition(creature_id="monster_001", x=1, y=1)
    combat = make_combat(positions=(existing_position,))
    snapshot = make_snapshot(creatures=default_creatures(), combat=combat)
    loaded_before = deepcopy(snapshot)
    store, metadata, calls = make_dependencies(snapshot)

    result = handle_with(store, metadata, make_command(creature_id="character_001"))

    assert calls == ["load", "metadata", "save"]
    assert store.load_calls == ["campaign_001"]
    assert metadata.next_calls == ["campaign_001"]
    assert store.snapshot == loaded_before

    assert result.success is True
    assert result.errors == ()
    assert result.outcome is not None
    assert result.outcome.combat_id == "combat_001"
    assert result.outcome.creature_id == "character_001"
    assert result.outcome.x == 5
    assert result.outcome.y == 10

    assert len(result.events) == 1
    event = result.events[0]
    assert event.type == "CombatantPlaced"
    assert event.version == 1
    assert event.caused_by is None
    assert event.payload == {
        "combatId": "combat_001",
        "creatureId": "character_001",
        "x": 5,
        "y": 10,
    }

    assert len(store.save_calls) == 1
    saved_snapshot = store.save_calls[0]
    assert saved_snapshot is not snapshot
    saved_combat = saved_snapshot.combat
    assert saved_combat is not None
    assert saved_combat is not combat
    assert saved_combat.positions == (
        existing_position,
        CombatPosition(creature_id="character_001", x=5, y=10),
    )
    assert saved_combat.id == combat.id
    assert saved_combat.round == combat.round
    assert saved_combat.order == combat.order
    assert saved_combat.active_index == combat.active_index
    assert saved_combat.action_spent == combat.action_spent
    assert saved_snapshot.creatures == snapshot.creatures


# --- validation precedence -----------------------------------------------------


def test_missing_actor_returns_entity_not_found() -> None:
    snapshot = make_snapshot(
        creatures=default_creatures(),
        combat=make_combat(),
    )
    loaded_before = deepcopy(snapshot)
    store, metadata, calls = make_dependencies(snapshot)

    result = handle_with(store, metadata, make_command(actor_id="character_999"))

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.ENTITY_NOT_FOUND
    assert result.errors[0].entity_id == "character_999"
    assert result.errors[0].field is None
    assert calls == ["load"]
    assert metadata.next_calls == []
    assert store.save_calls == []
    assert_source_snapshot_unchanged(store, loaded_before)


def test_missing_actor_takes_priority_over_invalid_combat() -> None:
    snapshot = make_snapshot(creatures=default_creatures(), combat=None)
    loaded_before = deepcopy(snapshot)
    store, metadata, calls = make_dependencies(snapshot)

    result = handle_with(store, metadata, make_command(actor_id="character_999"))

    assert result.success is False
    assert result.errors[0].code is ErrorCode.ENTITY_NOT_FOUND
    assert result.errors[0].entity_id == "character_999"
    assert result.errors[0].field is None
    assert calls == ["load"]
    assert store.save_calls == []
    assert_source_snapshot_unchanged(store, loaded_before)


def test_missing_combat_returns_entity_not_found() -> None:
    snapshot = make_snapshot(creatures=default_creatures(), combat=None)
    loaded_before = deepcopy(snapshot)
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
    assert_source_snapshot_unchanged(store, loaded_before)


def test_combat_id_mismatch_returns_entity_not_found() -> None:
    combat = make_combat(id="combat_other")
    snapshot = make_snapshot(creatures=default_creatures(), combat=combat)
    loaded_before = deepcopy(snapshot)
    store, metadata, calls = make_dependencies(snapshot)

    result = handle_with(store, metadata)

    assert result.success is False
    assert result.errors[0].code is ErrorCode.ENTITY_NOT_FOUND
    assert result.errors[0].entity_id == "combat_001"
    assert result.errors[0].field == "combat_id"
    assert calls == ["load"]
    assert store.save_calls == []
    assert_source_snapshot_unchanged(store, loaded_before)


def test_invalid_combat_takes_priority_over_missing_subject() -> None:
    snapshot = make_snapshot(
        creatures=(make_creature(creature_id="character_gm"),), combat=None
    )
    loaded_before = deepcopy(snapshot)
    store, metadata, calls = make_dependencies(snapshot)

    result = handle_with(
        store, metadata, make_command(creature_id="character_999")
    )

    assert result.success is False
    assert result.errors[0].code is ErrorCode.ENTITY_NOT_FOUND
    assert result.errors[0].entity_id == "combat_001"
    assert result.errors[0].field == "combat_id"
    assert calls == ["load"]
    assert store.save_calls == []
    assert_source_snapshot_unchanged(store, loaded_before)


def test_missing_subject_returns_entity_not_found() -> None:
    snapshot = make_snapshot(
        creatures=(
            make_creature(creature_id="character_gm"),
            make_creature(creature_id="monster_001"),
        ),
        combat=make_combat(order=("monster_001",), active_index=0),
    )
    loaded_before = deepcopy(snapshot)
    store, metadata, calls = make_dependencies(snapshot)

    result = handle_with(
        store, metadata, make_command(creature_id="character_999")
    )

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.ENTITY_NOT_FOUND
    assert result.errors[0].entity_id == "character_999"
    assert result.errors[0].field == "creature_id"
    assert calls == ["load"]
    assert metadata.next_calls == []
    assert store.save_calls == []
    assert_source_snapshot_unchanged(store, loaded_before)


def test_subject_not_in_order_returns_action_not_available() -> None:
    snapshot = make_snapshot(
        creatures=default_creatures(),
        combat=make_combat(order=("monster_001",), active_index=0),
    )
    loaded_before = deepcopy(snapshot)
    store, metadata, calls = make_dependencies(snapshot)

    result = handle_with(
        store, metadata, make_command(creature_id="character_001")
    )

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.ACTION_NOT_AVAILABLE
    assert result.errors[0].entity_id == "character_001"
    assert result.errors[0].field == "creature_id"
    assert calls == ["load"]
    assert metadata.next_calls == []
    assert store.save_calls == []
    assert_source_snapshot_unchanged(store, loaded_before)


def test_subject_already_positioned_returns_action_not_available() -> None:
    existing_position = CombatPosition(creature_id="character_001", x=1, y=1)
    combat = make_combat(positions=(existing_position,))
    snapshot = make_snapshot(creatures=default_creatures(), combat=combat)
    loaded_before = deepcopy(snapshot)
    store, metadata, calls = make_dependencies(snapshot)

    result = handle_with(
        store, metadata, make_command(creature_id="character_001")
    )

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.ACTION_NOT_AVAILABLE
    assert result.errors[0].entity_id == "character_001"
    assert result.errors[0].field == "creature_id"
    assert calls == ["load"]
    assert metadata.next_calls == []
    assert store.save_calls == []
    assert_source_snapshot_unchanged(store, loaded_before)


# --- boundary/atomicity ---------------------------------------------------------


def test_metadata_failure_propagates_without_save() -> None:
    combat = make_combat()
    snapshot = make_snapshot(creatures=default_creatures(), combat=combat)
    store, metadata, calls = make_dependencies(snapshot, metadata_fail=True)

    with pytest.raises(RuntimeError, match="metadata unavailable"):
        handle_with(store, metadata, make_command(creature_id="character_001"))

    assert calls == ["load", "metadata"]
    assert store.save_calls == []


def test_save_failure_propagates_and_is_attempted_exactly_once() -> None:
    combat = make_combat()
    snapshot = make_snapshot(creatures=default_creatures(), combat=combat)
    loaded_before = deepcopy(snapshot)
    calls: list[str] = []
    store = SaveFailingStateStore(snapshot, calls)
    metadata = FixedEventMetadataProvider(calls)

    with pytest.raises(StateStoreError, match="backend unavailable"):
        handle_with(store, metadata, make_command(creature_id="character_001"))

    assert calls == ["load", "metadata", "save"]
    assert len(store.save_calls) == 1
    # the originally loaded snapshot is not mutated in place
    assert store.snapshot == loaded_before


# --- focused regressions: things that must remain permitted ---------------------


def test_actor_id_may_differ_from_creature_id() -> None:
    combat = make_combat()
    snapshot = make_snapshot(creatures=default_creatures(), combat=combat)
    store, metadata, calls = make_dependencies(snapshot)

    result = handle_with(
        store,
        metadata,
        make_command(actor_id="character_gm", creature_id="character_001"),
    )

    assert result.success is True


def test_subject_need_not_be_active_combatant() -> None:
    combat = make_combat(
        order=("character_001", "monster_001"), active_index=0
    )
    snapshot = make_snapshot(creatures=default_creatures(), combat=combat)
    store, metadata, calls = make_dependencies(snapshot)

    result = handle_with(
        store, metadata, make_command(creature_id="monster_001")
    )

    assert result.success is True
    assert combat.active_creature_id == "character_001"


def test_zero_hp_subject_may_be_placed() -> None:
    combat = make_combat(order=("character_gm", "monster_001"), active_index=0)
    creatures = (
        make_creature(creature_id="character_gm"),
        make_creature(creature_id="monster_001", current_hp=0),
    )
    snapshot = make_snapshot(creatures=creatures, combat=combat)
    store, metadata, calls = make_dependencies(snapshot)

    result = handle_with(
        store, metadata, make_command(creature_id="monster_001")
    )

    assert result.success is True


def test_action_spent_true_does_not_block_placement() -> None:
    combat = make_combat(action_spent=True)
    snapshot = make_snapshot(creatures=default_creatures(), combat=combat)
    store, metadata, calls = make_dependencies(snapshot)

    result = handle_with(
        store, metadata, make_command(creature_id="character_001")
    )

    assert result.success is True
    saved_combat = store.save_calls[0].combat
    assert saved_combat is not None
    assert saved_combat.action_spent is True


def test_duplicate_coordinates_across_combatants_are_allowed() -> None:
    existing_position = CombatPosition(creature_id="monster_001", x=5, y=10)
    combat = make_combat(positions=(existing_position,))
    snapshot = make_snapshot(creatures=default_creatures(), combat=combat)
    store, metadata, calls = make_dependencies(snapshot)

    result = handle_with(
        store,
        metadata,
        make_command(creature_id="character_001", x=5, y=10),
    )

    assert result.success is True
    saved_combat = store.save_calls[0].combat
    assert saved_combat is not None
    assert saved_combat.positions == (
        existing_position,
        CombatPosition(creature_id="character_001", x=5, y=10),
    )
