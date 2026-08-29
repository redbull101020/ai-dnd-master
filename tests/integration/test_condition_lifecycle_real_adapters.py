from datetime import datetime, timezone
from pathlib import Path

from dnd_engine.application.handlers.apply_condition import ApplyConditionHandler
from dnd_engine.application.handlers.remove_condition import RemoveConditionHandler
from dnd_engine.application.services.event_metadata import EventMetadata
from dnd_engine.domain.commands.apply_condition import (
    ApplyConditionCommand,
    ApplyConditionPayload,
)
from dnd_engine.domain.commands.remove_condition import (
    RemoveConditionCommand,
    RemoveConditionPayload,
)
from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.domain.value_objects.condition import Condition
from dnd_engine.infrastructure.filesystem.state_store import FilesystemStateStore


FIXED_TIMESTAMP = datetime(2026, 8, 28, 20, 0, tzinfo=timezone.utc)


class FixedEventMetadataProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def next_metadata(self, campaign_id: str) -> EventMetadata:
        self.calls.append(campaign_id)
        return EventMetadata(
            event_id="event_000999",
            timestamp=FIXED_TIMESTAMP,
        )


def test_apply_then_remove_condition_round_trips_through_fresh_reloads(
    tmp_path: Path,
) -> None:
    """End-to-end production proof for G6C1 Group 3: Apply POISONED persists
    and is visible after a fresh reload, then Remove POISONED persists and
    is likewise absent after a fresh reload. Each step uses its own fresh
    FilesystemStateStore instance, so no in-process state is being observed
    -- only what the production V4 serializer actually wrote to disk."""
    campaigns_root = tmp_path / "campaigns"
    actor = CreatureState(
        id="character_001",
        definition_id="fighter",
        ability_scores=AbilityScores(
            strength=16,
            dexterity=10,
            constitution=14,
            intelligence=10,
            wisdom=10,
            charisma=10,
        ),
        current_hp=20,
        max_hp=20,
    )
    target = CreatureState(
        id="monster_001",
        definition_id="goblin",
        ability_scores=AbilityScores(
            strength=8,
            dexterity=14,
            constitution=10,
            intelligence=10,
            wisdom=8,
            charisma=8,
        ),
        current_hp=7,
        max_hp=7,
    )
    snapshot = StateSnapshot(
        campaign=CampaignState(
            id="campaign_001",
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
        ),
        creatures=(actor, target),
    )
    FilesystemStateStore(campaigns_root).save(snapshot)

    # --- Apply POISONED -> save -> fresh reload -> present ----------------

    apply_result = ApplyConditionHandler(
        state_store=FilesystemStateStore(campaigns_root),
        event_metadata_provider=FixedEventMetadataProvider(),
    ).handle(
        ApplyConditionCommand(
            command_id="command_apply_001",
            campaign_id="campaign_001",
            actor_id="character_001",
            payload=ApplyConditionPayload(
                target_id="monster_001", condition=Condition.POISONED
            ),
        )
    )

    assert apply_result.success is True
    assert apply_result.outcome.previous_active is False
    assert apply_result.outcome.active is True

    after_apply = FilesystemStateStore(campaigns_root).load("campaign_001")
    after_apply_target = next(
        creature for creature in after_apply.creatures if creature.id == "monster_001"
    )
    assert Condition.POISONED in after_apply_target.conditions

    # --- Remove POISONED -> save -> fresh reload -> absent -----------------

    remove_result = RemoveConditionHandler(
        state_store=FilesystemStateStore(campaigns_root),
        event_metadata_provider=FixedEventMetadataProvider(),
    ).handle(
        RemoveConditionCommand(
            command_id="command_remove_001",
            campaign_id="campaign_001",
            actor_id="character_001",
            payload=RemoveConditionPayload(
                target_id="monster_001", condition=Condition.POISONED
            ),
        )
    )

    assert remove_result.success is True
    assert remove_result.outcome.previous_active is True
    assert remove_result.outcome.active is False

    after_remove = FilesystemStateStore(campaigns_root).load("campaign_001")
    after_remove_target = next(
        creature for creature in after_remove.creatures if creature.id == "monster_001"
    )
    assert Condition.POISONED not in after_remove_target.conditions
    assert after_remove_target.conditions == frozenset()

    # unrelated HP untouched by either condition mutation
    assert after_remove_target.current_hp == 7
    assert after_remove_target.max_hp == 7
