import random
from datetime import datetime, timezone
from pathlib import Path

from dnd_engine.application.handlers.saving_throw import SavingThrowHandler
from dnd_engine.application.services.event_metadata import EventMetadata
from dnd_engine.domain.commands.saving_throw import (
    SavingThrowCommand,
    SavingThrowPayload,
)
from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.domain.value_objects.d20 import RollMode
from dnd_engine.infrastructure.filesystem.state_store import FilesystemStateStore
from dnd_engine.infrastructure.random.dice import PythonDiceEngine


FIXED_TIMESTAMP = datetime(2026, 8, 26, 16, 0, tzinfo=timezone.utc)


class FixedEventMetadataProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def next_metadata(self, campaign_id: str) -> EventMetadata:
        self.calls.append(campaign_id)
        return EventMetadata(
            event_id="event_000456",
            timestamp=FIXED_TIMESTAMP,
        )


def test_saving_throw_uses_real_adapters_without_persisting_artifacts(
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
                    strength=12,
                    dexterity=10,
                    constitution=14,
                    intelligence=10,
                    wisdom=10,
                    charisma=10,
                ),
                current_hp=20,
                max_hp=20,
            ),
        ),
        characters=(
            CharacterState(
                id="character_001",
                total_level=5,
                saving_throw_proficiencies=frozenset({Ability.CONSTITUTION}),
                skill_proficiencies=frozenset(),
            ),
        ),
    )
    FilesystemStateStore(campaigns_root).save(snapshot)

    state_path = campaigns_root / "campaign_001" / "state.json"
    state_before = state_path.read_bytes()
    metadata = FixedEventMetadataProvider()
    command = SavingThrowCommand(
        command_id="command_000123",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=SavingThrowPayload(ability=Ability.CONSTITUTION, dc=15),
    )
    result = SavingThrowHandler(
        state_store=FilesystemStateStore(campaigns_root),
        dice=PythonDiceEngine(random.Random(20260826)),
        event_metadata_provider=metadata,
    ).handle(command)

    assert metadata.calls == ["campaign_001"]
    assert result.success is True
    assert result.outcome is not None
    assert result.errors == ()
    outcome = result.outcome
    assert outcome.ability is Ability.CONSTITUTION
    assert outcome.roll.mode is RollMode.NORMAL
    assert len(outcome.roll.rolls) == 1
    assert outcome.roll.selected == outcome.roll.rolls[0]
    assert outcome.ability_modifier == 2
    assert outcome.proficiency_bonus == 3
    assert outcome.total == outcome.roll.selected + 2 + 3
    assert outcome.succeeded is (outcome.total >= 15)

    assert len(result.events) == 1
    event = result.events[0]
    assert event.event_id == "event_000456"
    assert event.type == "SavingThrowResolved"
    assert event.version == 1
    assert event.command_id == command.command_id
    assert event.campaign_id == command.campaign_id
    assert event.timestamp == FIXED_TIMESTAMP
    assert event.actor_id == command.actor_id
    assert event.caused_by is None
    assert event.payload == {
        "ability": "constitution",
        "dc": 15,
        "roll": {
            "mode": "normal",
            "rolls": outcome.roll.rolls,
            "selected": outcome.roll.selected,
        },
        "abilityModifier": 2,
        "proficiencyBonus": 3,
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
