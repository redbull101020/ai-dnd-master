from datetime import datetime, timedelta, timezone

import pytest

from dnd_engine.application.handlers.ability_check import AbilityCheckHandler
from dnd_engine.application.services.event_metadata import EventMetadata
from dnd_engine.domain.commands.ability_check import (
    AbilityCheckCommand,
    AbilityCheckPayload,
)
from dnd_engine.domain.errors import ErrorCode
from dnd_engine.domain.services.state_store import StateStoreError
from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.domain.value_objects.dice_roll import DiceRoll


FIXED_TIMESTAMP = datetime(2026, 8, 24, 15, 30, tzinfo=timezone.utc)


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
        self._roll = DiceRoll(
            expression="1d20",
            rolls=(raw_roll,),
            total=raw_roll,
        )
        self.calls: list[str] = []

    def roll(self, expression: str) -> DiceRoll:
        self.calls.append(expression)
        return self._roll


class FixedEventMetadataProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def next_metadata(self, campaign_id: str) -> EventMetadata:
        self.calls.append(campaign_id)
        return EventMetadata(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
        )


def make_creature(
    *,
    creature_id: str = "character_001",
    strength: int = 14,
) -> CreatureState:
    return CreatureState(
        id=creature_id,
        definition_id="fighter",
        ability_scores=AbilityScores(
            strength=strength,
            dexterity=12,
            constitution=16,
            intelligence=10,
            wisdom=8,
            charisma=13,
        ),
        current_hp=18,
        max_hp=20,
    )


def make_snapshot(*creatures: CreatureState) -> StateSnapshot:
    return StateSnapshot(
        campaign=CampaignState(
            id="campaign_001",
            ruleset_id="dnd_5e",
            ruleset_version="1.0.0",
        ),
        creatures=creatures,
    )


def make_command(*, actor_id: str = "character_001", dc: int = 15) -> AbilityCheckCommand:
    return AbilityCheckCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id=actor_id,
        payload=AbilityCheckPayload(ability=Ability.STRENGTH, dc=dc),
    )


def make_handler(
    *,
    state_store: SpyStateStore,
    dice: ScriptedDiceEngine,
    metadata_provider: FixedEventMetadataProvider,
) -> AbilityCheckHandler:
    return AbilityCheckHandler(
        state_store=state_store,
        dice=dice,
        event_metadata_provider=metadata_provider,
    )


def test_successful_gameplay_check_orchestrates_read_only_result_and_event() -> None:
    other = make_creature(creature_id="character_002", strength=8)
    actor = make_creature(strength=14)
    store = SpyStateStore(make_snapshot(other, actor))
    dice = ScriptedDiceEngine(raw_roll=13)
    metadata_provider = FixedEventMetadataProvider()

    result = make_handler(
        state_store=store,
        dice=dice,
        metadata_provider=metadata_provider,
    ).handle(make_command(dc=15))

    assert store.load_calls == ["campaign_001"]
    assert dice.calls == ["1d20"]
    assert metadata_provider.calls == ["campaign_001"]
    assert result.success is True
    assert result.command_id == "command_000001"
    assert result.outcome is not None
    assert result.outcome.ability is Ability.STRENGTH
    assert result.outcome.roll.total == 13
    assert result.outcome.modifier == 2
    assert result.outcome.total == 15
    assert result.outcome.succeeded is True
    assert result.errors == ()
    assert len(result.events) == 1

    event = result.events[0]
    assert event.event_id == "event_000123"
    assert event.timestamp is FIXED_TIMESTAMP
    assert event.type == "AbilityCheckResolved"
    assert event.version == 1
    assert event.command_id == result.command_id
    assert event.campaign_id == "campaign_001"
    assert event.actor_id == "character_001"
    assert event.caused_by is None
    assert event.payload == {
        "ability": result.outcome.ability.value,
        "dc": result.outcome.dc,
        "roll": {
            "expression": result.outcome.roll.expression,
            "rolls": result.outcome.roll.rolls,
            "total": result.outcome.roll.total,
        },
        "modifier": result.outcome.modifier,
        "total": result.outcome.total,
        "succeeded": result.outcome.succeeded,
    }
    assert store.save_calls == []


def test_failed_gameplay_check_is_successful_processing_with_event() -> None:
    store = SpyStateStore(make_snapshot(make_creature(strength=8)))
    dice = ScriptedDiceEngine(raw_roll=7)
    metadata_provider = FixedEventMetadataProvider()

    result = make_handler(
        state_store=store,
        dice=dice,
        metadata_provider=metadata_provider,
    ).handle(make_command(dc=15))

    assert result.success is True
    assert result.outcome is not None
    assert result.outcome.succeeded is False
    assert result.errors == ()
    assert len(result.events) == 1
    assert result.events[0].payload["succeeded"] is False
    assert store.save_calls == []


def test_missing_actor_returns_processing_failure_without_side_effects() -> None:
    store = SpyStateStore(make_snapshot(make_creature(creature_id="character_002")))
    dice = ScriptedDiceEngine(raw_roll=20)
    metadata_provider = FixedEventMetadataProvider()

    result = make_handler(
        state_store=store,
        dice=dice,
        metadata_provider=metadata_provider,
    ).handle(make_command())

    assert store.load_calls == ["campaign_001"]
    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.ENTITY_NOT_FOUND
    assert result.errors[0].entity_id == "character_001"
    assert dice.calls == []
    assert metadata_provider.calls == []
    assert store.save_calls == []


def test_handler_does_not_mutate_creature_state() -> None:
    actor = make_creature()
    before = (
        actor.id,
        actor.definition_id,
        actor.ability_scores,
        actor.current_hp,
        actor.max_hp,
    )
    store = SpyStateStore(make_snapshot(actor))

    make_handler(
        state_store=store,
        dice=ScriptedDiceEngine(raw_roll=10),
        metadata_provider=FixedEventMetadataProvider(),
    ).handle(make_command())

    assert (
        actor.id,
        actor.definition_id,
        actor.ability_scores,
        actor.current_hp,
        actor.max_hp,
    ) == before
    assert store.save_calls == []


def test_state_store_exception_propagates() -> None:
    store = FailingStateStore(make_snapshot(make_creature()))
    dice = ScriptedDiceEngine(raw_roll=20)
    metadata_provider = FixedEventMetadataProvider()

    with pytest.raises(StateStoreError, match="state backend unavailable"):
        make_handler(
            state_store=store,
            dice=dice,
            metadata_provider=metadata_provider,
        ).handle(make_command())

    assert dice.calls == []
    assert metadata_provider.calls == []
    assert store.save_calls == []


@pytest.mark.parametrize(
    ("event_id", "timestamp", "error"),
    [
        (1, FIXED_TIMESTAMP, TypeError),
        ("event_000123", "2026-08-24T15:30:00Z", TypeError),
        ("event_000123", datetime(2026, 8, 24, 15, 30), ValueError),
        (
            "event_000123",
            datetime(2026, 8, 24, 18, 30, tzinfo=timezone(timedelta(hours=3))),
            ValueError,
        ),
    ],
)
def test_event_metadata_rejects_invalid_intrinsic_values(
    event_id: object,
    timestamp: object,
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        EventMetadata(event_id=event_id, timestamp=timestamp)  # type: ignore[arg-type]
