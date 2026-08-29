from datetime import datetime, timezone
from pathlib import Path

from dnd_engine.application.handlers.ability_check import AbilityCheckHandler
from dnd_engine.application.handlers.apply_condition import ApplyConditionHandler
from dnd_engine.application.handlers.remove_condition import RemoveConditionHandler
from dnd_engine.application.services.event_metadata import EventMetadata
from dnd_engine.domain.commands.ability_check import (
    AbilityCheckCommand,
    AbilityCheckPayload,
)
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
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.domain.value_objects.condition import Condition
from dnd_engine.domain.value_objects.d20 import RollMode
from dnd_engine.domain.value_objects.dice_roll import DiceRoll
from dnd_engine.infrastructure.filesystem.state_store import FilesystemStateStore


FIXED_TIMESTAMP = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


class FixedEventMetadataProvider:
    def next_metadata(self, campaign_id: str) -> EventMetadata:
        return EventMetadata(
            event_id="event_000999",
            timestamp=FIXED_TIMESTAMP,
        )


class ScriptedDiceEngine:
    def __init__(self, *raw_rolls: int) -> None:
        self._raw_rolls = iter(raw_rolls)
        self.calls: list[str] = []

    def roll(self, expression: str) -> DiceRoll:
        self.calls.append(expression)
        raw_roll = next(self._raw_rolls)
        return DiceRoll(
            expression="1d20",
            rolls=(raw_roll,),
            total=raw_roll,
        )


def ability_check_command(command_id: str) -> AbilityCheckCommand:
    return AbilityCheckCommand(
        command_id=command_id,
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=AbilityCheckPayload(ability=Ability.STRENGTH, dc=15),
    )


def test_persisted_poisoned_membership_drives_later_ability_check_behavior(
    tmp_path: Path,
) -> None:
    campaigns_root = tmp_path / "campaigns"
    initial_actor = CreatureState(
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
    )
    FilesystemStateStore(campaigns_root).save(
        StateSnapshot(
            campaign=CampaignState(
                id="campaign_001",
                ruleset_id="dnd_5e",
                ruleset_version="5.1",
            ),
            creatures=(initial_actor,),
        )
    )

    baseline_dice = ScriptedDiceEngine(13)
    baseline_result = AbilityCheckHandler(
        state_store=FilesystemStateStore(campaigns_root),
        dice=baseline_dice,
        event_metadata_provider=FixedEventMetadataProvider(),
    ).handle(ability_check_command("command_check_baseline_001"))

    assert baseline_dice.calls == ["1d20"]
    assert baseline_result.outcome is not None
    assert baseline_result.outcome.roll.mode is RollMode.NORMAL
    assert baseline_result.outcome.roll.rolls == (13,)
    assert baseline_result.outcome.roll.selected == 13
    assert baseline_result.events[0].payload["roll"] == {
        "mode": "normal",
        "rolls": (13,),
        "selected": 13,
    }

    apply_result = ApplyConditionHandler(
        state_store=FilesystemStateStore(campaigns_root),
        event_metadata_provider=FixedEventMetadataProvider(),
    ).handle(
        ApplyConditionCommand(
            command_id="command_apply_001",
            campaign_id="campaign_001",
            actor_id="character_001",
            payload=ApplyConditionPayload(
                target_id="character_001",
                condition=Condition.POISONED,
            ),
        )
    )
    assert apply_result.success is True

    poisoned_dice = ScriptedDiceEngine(17, 6)
    poisoned_result = AbilityCheckHandler(
        state_store=FilesystemStateStore(campaigns_root),
        dice=poisoned_dice,
        event_metadata_provider=FixedEventMetadataProvider(),
    ).handle(ability_check_command("command_check_poisoned_001"))

    assert poisoned_dice.calls == ["1d20", "1d20"]
    assert poisoned_result.outcome is not None
    assert poisoned_result.outcome.roll.mode is RollMode.DISADVANTAGE
    assert poisoned_result.outcome.roll.rolls == (17, 6)
    assert poisoned_result.outcome.roll.selected == 6
    assert poisoned_result.events[0].payload["roll"] == {
        "mode": "disadvantage",
        "rolls": (17, 6),
        "selected": 6,
    }

    remove_result = RemoveConditionHandler(
        state_store=FilesystemStateStore(campaigns_root),
        event_metadata_provider=FixedEventMetadataProvider(),
    ).handle(
        RemoveConditionCommand(
            command_id="command_remove_001",
            campaign_id="campaign_001",
            actor_id="character_001",
            payload=RemoveConditionPayload(
                target_id="character_001",
                condition=Condition.POISONED,
            ),
        )
    )
    assert remove_result.success is True

    normal_dice = ScriptedDiceEngine(11)
    normal_result = AbilityCheckHandler(
        state_store=FilesystemStateStore(campaigns_root),
        dice=normal_dice,
        event_metadata_provider=FixedEventMetadataProvider(),
    ).handle(ability_check_command("command_check_normal_001"))

    assert normal_dice.calls == ["1d20"]
    assert normal_result.outcome is not None
    assert normal_result.outcome.roll.mode is RollMode.NORMAL
    assert normal_result.outcome.roll.rolls == (11,)
    assert normal_result.outcome.roll.selected == 11
    assert normal_result.events[0].payload["roll"] == {
        "mode": "normal",
        "rolls": (11,),
        "selected": 11,
    }

    final_snapshot = FilesystemStateStore(campaigns_root).load("campaign_001")
    assert final_snapshot.creatures[0].conditions == frozenset()
