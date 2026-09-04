from datetime import datetime, timezone

import pytest

from dnd_engine.application.handlers.saving_throw import SavingThrowHandler
from dnd_engine.application.services.event_metadata import EventMetadata
from dnd_engine.domain.commands.saving_throw import (
    SavingThrowCommand,
    SavingThrowPayload,
)
from dnd_engine.domain.errors import ErrorCode
from dnd_engine.domain.services.state_store import StateStoreError
from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.domain.value_objects.condition import Condition
from dnd_engine.domain.value_objects.d20 import RollMode
from dnd_engine.domain.value_objects.dice_roll import DiceRoll


FIXED_TIMESTAMP = datetime(2026, 8, 26, 15, 30, tzinfo=timezone.utc)


class SpyStateStore:
    def __init__(self, snapshot: StateSnapshot) -> None:
        self._snapshot = snapshot
        self.load_calls: list[str] = []
        self.save_calls: list[StateSnapshot] = []

    def load(self, campaign_id: str) -> StateSnapshot:
        self.load_calls.append(campaign_id)
        return self._snapshot

    def save(self, snapshot: StateSnapshot) -> None:
        self.save_calls.append(snapshot)


class FailingStateStore(SpyStateStore):
    def load(self, campaign_id: str) -> StateSnapshot:
        self.load_calls.append(campaign_id)
        raise StateStoreError("state backend unavailable")


class ScriptedDiceEngine:
    def __init__(self, raw_roll: int) -> None:
        self._raw_roll = raw_roll
        self.calls: list[str] = []

    def roll(self, expression: str) -> DiceRoll:
        self.calls.append(expression)
        return DiceRoll(
            expression="1d20",
            rolls=(self._raw_roll,),
            total=self._raw_roll,
        )


class FailingDiceEngine(ScriptedDiceEngine):
    def roll(self, expression: str) -> DiceRoll:
        self.calls.append(expression)
        raise RuntimeError("dice unavailable")


class FixedEventMetadataProvider:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail
        self.calls: list[str] = []

    def next_metadata(self, campaign_id: str) -> EventMetadata:
        self.calls.append(campaign_id)
        if self._fail:
            raise RuntimeError("metadata unavailable")
        return EventMetadata(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
        )


def make_creature(
    *,
    creature_id: str = "character_001",
    conditions: frozenset[Condition] = frozenset(),
) -> CreatureState:
    return CreatureState(
        id=creature_id,
        definition_id="fighter",
        ability_scores=AbilityScores(
            strength=12,
            dexterity=10,
            constitution=14,
            intelligence=10,
            wisdom=10,
            charisma=10,
        ),
        current_hp=20,
        max_hp=20,
        conditions=conditions,
    )


def make_character(*, character_id: str = "character_001") -> CharacterState:
    return CharacterState(
        id=character_id,
        total_level=5,
        saving_throw_proficiencies=frozenset({Ability.CONSTITUTION}),
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
            ruleset_version="1.0.0",
        ),
        creatures=creatures,
        characters=characters,
    )


def make_command(*, dc: int = 15) -> SavingThrowCommand:
    return SavingThrowCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=SavingThrowPayload(ability=Ability.CONSTITUTION, dc=dc),
    )


def make_handler(
    store: SpyStateStore,
    dice: ScriptedDiceEngine,
    metadata: FixedEventMetadataProvider,
) -> SavingThrowHandler:
    return SavingThrowHandler(
        state_store=store,
        dice=dice,
        event_metadata_provider=metadata,
    )


def test_successful_proficient_save_returns_v1_event_without_saving_state() -> None:
    actor = make_creature()
    character = make_character()
    store = SpyStateStore(
        make_snapshot(
            creatures=(make_creature(creature_id="character_002"), actor),
            characters=(character,),
        )
    )
    dice = ScriptedDiceEngine(10)
    metadata = FixedEventMetadataProvider()

    result = make_handler(store, dice, metadata).handle(make_command())

    assert store.load_calls == ["campaign_001"]
    assert dice.calls == ["1d20"]
    assert metadata.calls == ["campaign_001"]
    assert store.save_calls == []
    assert result.success is True
    assert result.outcome is not None
    assert result.outcome.ability_modifier == 2
    assert result.outcome.proficiency_bonus == 3
    assert result.outcome.total == 15
    assert result.outcome.succeeded is True
    assert result.errors == ()
    assert len(result.events) == 1
    event = result.events[0]
    assert event.type == "SavingThrowResolved"
    assert event.version == 1
    assert event.payload["abilityModifier"] == 2
    assert event.payload["proficiencyBonus"] == 3


def test_poisoned_actor_saving_throw_stays_normal_with_one_actual_roll() -> None:
    store = SpyStateStore(
        make_snapshot(
            creatures=(
                make_creature(conditions=frozenset({Condition.POISONED})),
            ),
            characters=(make_character(),),
        )
    )
    dice = ScriptedDiceEngine(17)

    result = make_handler(
        store,
        dice,
        FixedEventMetadataProvider(),
    ).handle(make_command())

    assert dice.calls == ["1d20"]
    assert result.outcome is not None
    assert result.outcome.roll.mode is RollMode.NORMAL
    assert result.outcome.roll.rolls == (17,)
    assert result.outcome.roll.selected == 17
    assert result.events[0].payload["roll"] == {
        "mode": "normal",
        "rolls": (17,),
        "selected": 17,
    }
    assert store.save_calls == []


def test_failed_gameplay_save_is_successful_processing() -> None:
    store = SpyStateStore(
        make_snapshot(
            creatures=(make_creature(),),
            characters=(make_character(),),
        )
    )

    result = make_handler(
        store,
        ScriptedDiceEngine(1),
        FixedEventMetadataProvider(),
    ).handle(make_command())

    assert result.success is True
    assert result.outcome is not None
    assert result.outcome.succeeded is False
    assert result.errors == ()
    assert len(result.events) == 1
    assert store.save_calls == []


def test_missing_creature_returns_entity_not_found_without_side_effects() -> None:
    store = SpyStateStore(make_snapshot())
    dice = ScriptedDiceEngine(20)
    metadata = FixedEventMetadataProvider()

    result = make_handler(store, dice, metadata).handle(make_command())

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.ENTITY_NOT_FOUND
    assert result.errors[0].entity_id == "character_001"
    assert dice.calls == []
    assert metadata.calls == []
    assert store.save_calls == []


def test_missing_character_returns_invalid_state_without_invented_defaults() -> None:
    store = SpyStateStore(make_snapshot(creatures=(make_creature(),)))
    dice = ScriptedDiceEngine(20)
    metadata = FixedEventMetadataProvider()

    result = make_handler(store, dice, metadata).handle(make_command())

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.INVALID_STATE
    assert result.errors[0].entity_id == "character_001"
    assert result.errors[0].field == "characters"
    assert dice.calls == []
    assert metadata.calls == []
    assert store.save_calls == []


def test_state_store_load_failure_propagates() -> None:
    store = FailingStateStore(make_snapshot())
    dice = ScriptedDiceEngine(20)
    metadata = FixedEventMetadataProvider()

    with pytest.raises(StateStoreError, match="unavailable"):
        make_handler(store, dice, metadata).handle(make_command())

    assert dice.calls == []
    assert metadata.calls == []
    assert store.save_calls == []


def test_dice_failure_propagates_before_metadata_request() -> None:
    store = SpyStateStore(
        make_snapshot(
            creatures=(make_creature(),),
            characters=(make_character(),),
        )
    )
    dice = FailingDiceEngine(20)
    metadata = FixedEventMetadataProvider()

    with pytest.raises(RuntimeError, match="dice unavailable"):
        make_handler(store, dice, metadata).handle(make_command())

    assert dice.calls == ["1d20"]
    assert metadata.calls == []
    assert store.save_calls == []


def test_metadata_failure_propagates_after_resolution_without_save() -> None:
    store = SpyStateStore(
        make_snapshot(
            creatures=(make_creature(),),
            characters=(make_character(),),
        )
    )
    dice = ScriptedDiceEngine(10)
    metadata = FixedEventMetadataProvider(fail=True)

    with pytest.raises(RuntimeError, match="metadata unavailable"):
        make_handler(store, dice, metadata).handle(make_command())

    assert dice.calls == ["1d20"]
    assert metadata.calls == ["campaign_001"]
    assert store.save_calls == []
