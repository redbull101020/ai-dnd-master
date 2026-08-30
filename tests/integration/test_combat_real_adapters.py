import random
from datetime import datetime, timezone
from pathlib import Path

from dnd_engine.application.handlers.advance_turn import AdvanceTurnHandler
from dnd_engine.application.handlers.start_combat import StartCombatHandler
from dnd_engine.application.services.event_metadata import EventMetadata
from dnd_engine.domain.commands.advance_turn import (
    AdvanceTurnCommand,
    AdvanceTurnPayload,
)
from dnd_engine.domain.commands.start_combat import (
    StartCombatCommand,
    StartCombatPayload,
)
from dnd_engine.domain.errors import ErrorCode
from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.infrastructure.filesystem.state_store import FilesystemStateStore
from dnd_engine.infrastructure.random.dice import PythonDiceEngine


FIXED_TIMESTAMP = datetime(2026, 8, 30, 16, 0, tzinfo=timezone.utc)


class FixedEventMetadataProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def next_metadata(self, campaign_id: str) -> EventMetadata:
        self.calls.append(campaign_id)
        return EventMetadata(event_id="event_000999", timestamp=FIXED_TIMESTAMP)


def test_start_combat_then_advance_turn_round_trips_through_fresh_reloads(
    tmp_path: Path,
) -> None:
    """End-to-end production proof for G7: initiative is rolled through a real
    DiceEngine and the resulting CombatState is visible after a fresh reload,
    then advancing the turn (gated by actor eligibility) persists the new
    active combatant and round, also visible after a fresh reload. Each step
    uses its own fresh FilesystemStateStore instance, so only what the
    production V5 serializer actually wrote to disk is being observed."""
    campaigns_root = tmp_path / "campaigns"
    character = CreatureState(
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
    monster = CreatureState(
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
            id="campaign_001", ruleset_id="dnd_5e", ruleset_version="5.1"
        ),
        creatures=(character, monster),
    )
    FilesystemStateStore(campaigns_root).save(snapshot)

    # --- Start Combat -> save -> fresh reload -> CombatState present -------

    seed = 20260830
    rng = random.Random(seed)
    expected_rng = random.Random(seed)
    expected_character_roll = expected_rng.randint(1, 20)
    expected_monster_roll = expected_rng.randint(1, 20)

    start_result = StartCombatHandler(
        state_store=FilesystemStateStore(campaigns_root),
        dice=PythonDiceEngine(rng),
        event_metadata_provider=FixedEventMetadataProvider(),
    ).handle(
        StartCombatCommand(
            command_id="command_start_001",
            campaign_id="campaign_001",
            actor_id="character_001",
            payload=StartCombatPayload(
                combat_id="combat_001",
                participant_ids=("character_001", "monster_001"),
            ),
        )
    )

    assert start_result.success is True
    assert start_result.outcome is not None
    character_total = expected_character_roll + 0
    monster_total = expected_monster_roll + 2
    expected_order = (
        ("monster_001", "character_001")
        if monster_total >= character_total
        else ("character_001", "monster_001")
    )
    assert start_result.outcome.order == expected_order

    after_start = FilesystemStateStore(campaigns_root).load("campaign_001")
    assert after_start.combat is not None
    assert after_start.combat.id == "combat_001"
    assert after_start.combat.round == 1
    assert after_start.combat.order == expected_order
    assert after_start.combat.active_creature_id == expected_order[0]

    # unrelated Creature state untouched by combat start
    reloaded_character = next(
        creature for creature in after_start.creatures if creature.id == "character_001"
    )
    reloaded_monster = next(
        creature for creature in after_start.creatures if creature.id == "monster_001"
    )
    assert (reloaded_character.current_hp, reloaded_character.max_hp) == (20, 20)
    assert (reloaded_monster.current_hp, reloaded_monster.max_hp) == (7, 7)

    # --- Advance Turn -> save -> fresh reload -> new active combatant ------

    first_active = after_start.combat.active_creature_id
    second_active = expected_order[1]

    advance_result = AdvanceTurnHandler(
        state_store=FilesystemStateStore(campaigns_root),
        event_metadata_provider=FixedEventMetadataProvider(),
    ).handle(
        AdvanceTurnCommand(
            command_id="command_advance_001",
            campaign_id="campaign_001",
            actor_id=first_active,
            payload=AdvanceTurnPayload(combat_id="combat_001"),
        )
    )

    assert advance_result.success is True
    assert advance_result.outcome.active_creature_id == second_active
    assert advance_result.outcome.round == 1

    after_advance = FilesystemStateStore(campaigns_root).load("campaign_001")
    assert after_advance.combat is not None
    assert after_advance.combat.active_creature_id == second_active
    assert after_advance.combat.round == 1

    # --- Advance Turn again wraps to round 2 and is rejected for the wrong actor

    wrong_actor_result = AdvanceTurnHandler(
        state_store=FilesystemStateStore(campaigns_root),
        event_metadata_provider=FixedEventMetadataProvider(),
    ).handle(
        AdvanceTurnCommand(
            command_id="command_advance_002",
            campaign_id="campaign_001",
            actor_id=first_active,
            payload=AdvanceTurnPayload(combat_id="combat_001"),
        )
    )

    assert wrong_actor_result.success is False
    assert wrong_actor_result.errors[0].code is ErrorCode.ACTION_NOT_AVAILABLE

    final_advance_result = AdvanceTurnHandler(
        state_store=FilesystemStateStore(campaigns_root),
        event_metadata_provider=FixedEventMetadataProvider(),
    ).handle(
        AdvanceTurnCommand(
            command_id="command_advance_003",
            campaign_id="campaign_001",
            actor_id=second_active,
            payload=AdvanceTurnPayload(combat_id="combat_001"),
        )
    )

    assert final_advance_result.success is True
    assert final_advance_result.outcome.round == 2
    assert final_advance_result.outcome.active_creature_id == first_active

    after_final = FilesystemStateStore(campaigns_root).load("campaign_001")
    assert after_final.combat is not None
    assert after_final.combat.round == 2
    assert after_final.combat.active_creature_id == first_active

    # no Event history/EventStore artifacts, no other files created
    state_path = campaigns_root / "campaign_001" / "state.json"
    assert sorted(
        path.relative_to(state_path.parent).as_posix()
        for path in state_path.parent.rglob("*")
        if path.is_file()
    ) == ["state.json"]
