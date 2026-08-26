import random
from datetime import datetime, timezone
from pathlib import Path

from dnd_engine.application.handlers.ability_check import AbilityCheckHandler
from dnd_engine.application.services.event_metadata import EventMetadata
from dnd_engine.domain.commands.ability_check import (
    AbilityCheckCommand,
    AbilityCheckPayload,
)
from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.domain.value_objects.d20 import RollMode
from dnd_engine.infrastructure.filesystem.state_store import FilesystemStateStore
from dnd_engine.infrastructure.random.dice import PythonDiceEngine


FIXED_TIMESTAMP = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)


class FixedEventMetadataProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def next_metadata(self, campaign_id: str) -> EventMetadata:
        self.calls.append(campaign_id)
        return EventMetadata(
            event_id="event_000321",
            timestamp=FIXED_TIMESTAMP,
        )


def test_ability_check_uses_real_adapters_without_persisting_state(
    tmp_path: Path,
) -> None:
    campaigns_root = tmp_path / "campaigns"
    snapshot = StateSnapshot(
        campaign=CampaignState(
            id="campaign_001",
            ruleset_id="dnd_5e",
            ruleset_version="1.0.0",
        ),
        creatures=(
            CreatureState(
                id="character_001",
                definition_id="fighter",
                ability_scores=AbilityScores(
                    strength=14,
                    dexterity=12,
                    constitution=16,
                    intelligence=10,
                    wisdom=8,
                    charisma=13,
                ),
                current_hp=18,
                max_hp=20,
            ),
        ),
    )
    FilesystemStateStore(campaigns_root).save(snapshot)

    state_path = campaigns_root / "campaign_001" / "state.json"
    state_before = state_path.read_bytes()
    metadata_provider = FixedEventMetadataProvider()
    handler = AbilityCheckHandler(
        state_store=FilesystemStateStore(campaigns_root),
        dice=PythonDiceEngine(random.Random(20260826)),
        event_metadata_provider=metadata_provider,
    )
    command = AbilityCheckCommand(
        command_id="command_000123",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=AbilityCheckPayload(ability=Ability.STRENGTH, dc=15),
    )

    result = handler.handle(command)

    assert metadata_provider.calls == ["campaign_001"]
    assert result.success is True
    assert result.command_id == command.command_id
    assert result.outcome is not None
    assert result.errors == ()

    outcome = result.outcome
    assert outcome.ability is Ability.STRENGTH
    assert outcome.dc == 15
    assert outcome.roll.mode is RollMode.NORMAL
    assert len(outcome.roll.rolls) == 1
    raw_roll = outcome.roll.rolls[0]
    assert 1 <= raw_roll <= 20
    assert outcome.roll.selected == raw_roll
    assert outcome.modifier == 2
    assert outcome.total == raw_roll + outcome.modifier
    assert outcome.succeeded is (outcome.total >= outcome.dc)

    assert len(result.events) == 1
    event = result.events[0]
    assert event.event_id == "event_000321"
    assert event.command_id == command.command_id
    assert event.type == "AbilityCheckResolved"
    assert event.version == 2
    assert event.campaign_id == command.campaign_id
    assert event.timestamp == FIXED_TIMESTAMP
    assert event.actor_id == command.actor_id
    assert event.caused_by is None
    assert event.payload == {
        "ability": outcome.ability.value,
        "dc": outcome.dc,
        "roll": {
            "mode": outcome.roll.mode.value,
            "rolls": outcome.roll.rolls,
            "selected": outcome.roll.selected,
        },
        "modifier": outcome.modifier,
        "total": outcome.total,
        "succeeded": outcome.succeeded,
    }

    assert state_path.read_bytes() == state_before
    assert sorted(
        path.relative_to(state_path.parent).as_posix()
        for path in state_path.parent.rglob("*")
        if path.is_file()
    ) == ["state.json"]
    assert list(state_path.parent.glob(".state-*.tmp")) == []
