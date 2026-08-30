from copy import deepcopy
from datetime import datetime, timezone

import pytest

from dnd_engine.application.handlers.start_combat import StartCombatHandler
from dnd_engine.application.services.event_metadata import EventMetadata
from dnd_engine.domain.commands.start_combat import (
    StartCombatCommand,
    StartCombatPayload,
)
from dnd_engine.domain.errors import ErrorCode
from dnd_engine.domain.services.state_store import StateStoreError
from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.combat import CombatState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.domain.value_objects.condition import Condition
from dnd_engine.domain.value_objects.d20 import RollMode
from dnd_engine.domain.value_objects.dice_roll import DiceRoll


FIXED_TIMESTAMP = datetime(2026, 8, 30, 14, 0, tzinfo=timezone.utc)


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


class ScriptedDiceEngine:
    def __init__(self, *raw_rolls: int, calls: list[str]) -> None:
        self._rolls = iter(raw_rolls)
        self._calls = calls
        self.roll_calls: list[str] = []

    def roll(self, expression: str) -> DiceRoll:
        self._calls.append("dice")
        self.roll_calls.append(expression)
        raw = next(self._rolls)
        return DiceRoll(expression="1d20", rolls=(raw,), total=raw)


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


def make_creature(
    *,
    creature_id: str,
    dexterity: int = 10,
    conditions: frozenset[Condition] = frozenset(),
) -> CreatureState:
    return CreatureState(
        id=creature_id,
        definition_id="fighter",
        ability_scores=AbilityScores(
            strength=10,
            dexterity=dexterity,
            constitution=10,
            intelligence=10,
            wisdom=10,
            charisma=10,
        ),
        current_hp=10,
        max_hp=10,
        conditions=conditions,
    )


def make_snapshot(
    *,
    creatures: tuple[CreatureState, ...] = (),
    combat: CombatState | None = None,
) -> StateSnapshot:
    return StateSnapshot(
        campaign=CampaignState(
            id="campaign_001", ruleset_id="dnd_5e", ruleset_version="5.1"
        ),
        creatures=creatures,
        combat=combat,
    )


def make_command(
    *, participant_ids: tuple[str, ...] = ("character_001", "monster_001")
) -> StartCombatCommand:
    return StartCombatCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=StartCombatPayload(
            combat_id="combat_001", participant_ids=participant_ids
        ),
    )


def make_dependencies(
    snapshot: StateSnapshot,
    *,
    raw_rolls: tuple[int, ...] = (8, 15),
    metadata_fail: bool = False,
) -> tuple[SpyStateStore, ScriptedDiceEngine, FixedEventMetadataProvider, list[str]]:
    calls: list[str] = []
    return (
        SpyStateStore(snapshot, calls),
        ScriptedDiceEngine(*raw_rolls, calls=calls),
        FixedEventMetadataProvider(calls, fail=metadata_fail),
        calls,
    )


def handle_with(
    store: SpyStateStore,
    dice: ScriptedDiceEngine,
    metadata: FixedEventMetadataProvider,
    command: StartCombatCommand | None = None,
):
    return StartCombatHandler(
        state_store=store, dice=dice, event_metadata_provider=metadata
    ).handle(command or make_command())


def test_successful_start_combat_persists_new_combat_state() -> None:
    character = make_creature(creature_id="character_001", dexterity=10)
    monster = make_creature(creature_id="monster_001", dexterity=14)
    snapshot = make_snapshot(creatures=(character, monster))
    loaded_before = deepcopy(snapshot)
    store, dice, metadata, calls = make_dependencies(snapshot, raw_rolls=(8, 15))

    result = handle_with(store, dice, metadata)

    assert calls == ["load", "dice", "dice", "metadata", "save"]
    assert store.load_calls == ["campaign_001"]
    assert dice.roll_calls == ["1d20", "1d20"]
    assert metadata.next_calls == ["campaign_001"]

    # loaded snapshot unchanged
    assert store.snapshot == loaded_before
    assert store.snapshot.combat is None

    assert len(store.save_calls) == 1
    saved_snapshot = store.save_calls[0]
    assert saved_snapshot is not snapshot
    assert saved_snapshot.creatures == snapshot.creatures
    assert saved_snapshot.combat == CombatState(
        id="combat_001",
        round=1,
        order=("monster_001", "character_001"),
        active_index=0,
    )

    assert result.success is True
    assert result.errors == ()
    assert result.outcome is not None
    assert result.outcome.order == ("monster_001", "character_001")

    assert len(result.events) == 1
    event = result.events[0]
    assert event.type == "CombatStarted"
    assert event.version == 1
    assert event.payload["combatId"] == "combat_001"
    assert event.payload["order"] == ("monster_001", "character_001")


def test_missing_actor_returns_structured_failure_before_anything_else() -> None:
    snapshot = make_snapshot(
        creatures=(
            make_creature(creature_id="monster_001"),
            make_creature(creature_id="monster_002"),
        )
    )
    store, dice, metadata, calls = make_dependencies(snapshot)

    result = handle_with(
        store,
        dice,
        metadata,
        StartCombatCommand(
            command_id="command_000001",
            campaign_id="campaign_001",
            actor_id="character_001",
            payload=StartCombatPayload(
                combat_id="combat_001",
                participant_ids=("monster_001", "monster_002"),
            ),
        ),
    )

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.ENTITY_NOT_FOUND
    assert result.errors[0].entity_id == "character_001"
    assert result.errors[0].field is None
    assert calls == ["load"]
    assert dice.roll_calls == []
    assert metadata.next_calls == []
    assert store.save_calls == []


def test_missing_actor_takes_priority_over_combat_already_in_progress() -> None:
    existing_combat = CombatState(
        id="combat_existing",
        round=1,
        order=("monster_001",),
        active_index=0,
    )
    snapshot = make_snapshot(
        creatures=(make_creature(creature_id="monster_001"),),
        combat=existing_combat,
    )
    store, dice, metadata, calls = make_dependencies(snapshot)

    result = handle_with(store, dice, metadata)

    assert result.success is False
    assert result.errors[0].code is ErrorCode.ENTITY_NOT_FOUND
    assert result.errors[0].entity_id == "character_001"
    assert calls == ["load"]
    assert store.save_calls == []


def test_actor_does_not_need_to_be_a_participant() -> None:
    # command.actor_id "character_001" is not in participant_ids below;
    # no canonical contract requires the initiating actor to also fight.
    actor = make_creature(creature_id="character_001")
    monster_one = make_creature(creature_id="monster_001", dexterity=10)
    monster_two = make_creature(creature_id="monster_002", dexterity=14)
    snapshot = make_snapshot(creatures=(actor, monster_one, monster_two))
    store, dice, metadata, calls = make_dependencies(snapshot, raw_rolls=(8, 15))

    result = handle_with(
        store,
        dice,
        metadata,
        StartCombatCommand(
            command_id="command_000001",
            campaign_id="campaign_001",
            actor_id="character_001",
            payload=StartCombatPayload(
                combat_id="combat_001",
                participant_ids=("monster_001", "monster_002"),
            ),
        ),
    )

    assert result.success is True
    assert result.outcome.order == ("monster_002", "monster_001")


def test_poisoned_participant_rolls_initiative_with_disadvantage() -> None:
    normal_participant = make_creature(creature_id="character_001", dexterity=10)
    poisoned_participant = make_creature(
        creature_id="monster_001",
        dexterity=10,
        conditions=frozenset({Condition.POISONED}),
    )
    snapshot = make_snapshot(creatures=(normal_participant, poisoned_participant))
    # character_001 (normal): one roll of 9
    # monster_001 (poisoned): two rolls, 17 and 6 -> selected 6
    store, dice, metadata, calls = make_dependencies(snapshot, raw_rolls=(9, 17, 6))

    result = handle_with(store, dice, metadata)

    assert calls == ["load", "dice", "dice", "dice", "metadata", "save"]
    assert dice.roll_calls == ["1d20", "1d20", "1d20"]
    assert result.success is True
    entries_by_id = {entry.creature_id: entry for entry in result.outcome.entries}
    assert entries_by_id["character_001"].roll.mode is RollMode.NORMAL
    assert entries_by_id["character_001"].roll.rolls == (9,)
    assert entries_by_id["monster_001"].roll.mode is RollMode.DISADVANTAGE
    assert entries_by_id["monster_001"].roll.rolls == (17, 6)
    assert entries_by_id["monster_001"].roll.selected == 6
    # poisoned participant's lower effective total sorts it second
    assert result.outcome.order == ("character_001", "monster_001")


def test_combat_already_in_progress_returns_rule_violation() -> None:
    existing_combat = CombatState(
        id="combat_existing",
        round=2,
        order=("character_001",),
        active_index=0,
    )
    snapshot = make_snapshot(
        creatures=(make_creature(creature_id="character_001"),),
        combat=existing_combat,
    )
    store, dice, metadata, calls = make_dependencies(snapshot)

    result = handle_with(store, dice, metadata)

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.RULE_VIOLATION
    assert result.errors[0].entity_id == "combat_existing"
    assert calls == ["load"]
    assert dice.roll_calls == []
    assert metadata.next_calls == []
    assert store.save_calls == []


def test_missing_participant_returns_structured_failure_without_dice_or_save() -> None:
    snapshot = make_snapshot(creatures=(make_creature(creature_id="character_001"),))
    store, dice, metadata, calls = make_dependencies(snapshot)

    result = handle_with(store, dice, metadata)

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.ENTITY_NOT_FOUND
    assert result.errors[0].entity_id == "monster_001"
    assert result.errors[0].field == "participant_ids"
    assert calls == ["load"]
    assert dice.roll_calls == []
    assert metadata.next_calls == []
    assert store.save_calls == []


def test_metadata_failure_propagates_without_save() -> None:
    snapshot = make_snapshot(
        creatures=(
            make_creature(creature_id="character_001"),
            make_creature(creature_id="monster_001"),
        )
    )
    store, dice, metadata, calls = make_dependencies(snapshot, metadata_fail=True)

    with pytest.raises(RuntimeError, match="metadata unavailable"):
        handle_with(store, dice, metadata)

    assert calls == ["load", "dice", "dice", "metadata"]
    assert store.save_calls == []


def test_save_failure_propagates_and_is_attempted_exactly_once() -> None:
    snapshot = make_snapshot(
        creatures=(
            make_creature(creature_id="character_001"),
            make_creature(creature_id="monster_001"),
        )
    )
    calls: list[str] = []
    store = SaveFailingStateStore(snapshot, calls)
    dice = ScriptedDiceEngine(8, 15, calls=calls)
    metadata = FixedEventMetadataProvider(calls)

    with pytest.raises(StateStoreError, match="backend unavailable"):
        handle_with(store, dice, metadata)

    assert calls == ["load", "dice", "dice", "metadata", "save"]
    assert len(store.save_calls) == 1
