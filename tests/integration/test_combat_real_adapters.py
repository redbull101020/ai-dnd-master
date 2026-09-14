import json
import random
from datetime import datetime, timezone
from pathlib import Path

from dnd_engine.application.handlers.advance_turn import AdvanceTurnHandler
from dnd_engine.application.handlers.end_combat import EndCombatHandler
from dnd_engine.application.handlers.place_combatant import PlaceCombatantHandler
from dnd_engine.application.handlers.start_combat import StartCombatHandler
from dnd_engine.application.services.event_metadata import EventMetadata
from dnd_engine.domain.commands.advance_turn import (
    AdvanceTurnCommand,
    AdvanceTurnPayload,
)
from dnd_engine.domain.commands.end_combat import EndCombatCommand, EndCombatPayload
from dnd_engine.domain.commands.place_combatant import (
    PlaceCombatantCommand,
    PlaceCombatantPayload,
)
from dnd_engine.domain.commands.start_combat import (
    StartCombatCommand,
    StartCombatPayload,
)
from dnd_engine.domain.errors import ErrorCode
from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.state.combat import CombatPosition, CombatState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.equipment import EquipmentState
from dnd_engine.domain.state.inventory import InventoryItemState, InventoryState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.domain.value_objects.condition import Condition
from dnd_engine.infrastructure.filesystem.state_store import FilesystemStateStore
from dnd_engine.infrastructure.persistence.json.state_serializer import (
    SCHEMA_VERSION,
)
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
        dice=PythonDiceEngine(random.Random(1)),
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
        dice=PythonDiceEngine(random.Random(1)),
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
        dice=PythonDiceEngine(random.Random(1)),
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


def test_start_combat_then_end_combat_round_trips_through_fresh_reloads_and_reopens(
    tmp_path: Path,
) -> None:
    """End-to-end production proof for §3.35/TSK-0019: a real FilesystemStateStore
    and the production V9 StateSerializer take a Combat from absent, through a
    real StartCombatHandler (real DiceEngine initiative), to active, then a
    real EndCombatHandler returns it to absent -- each transition observed
    through its own fresh FilesystemStateStore instance and a fresh reload, so
    only what production persistence actually wrote to disk is being checked.
    Unrelated Creature/Character/Inventory/Equipment State, including existing
    Character death-save/lifecycle facts, is proven untouched by EndCombat, and
    a brand-new StartCombat succeeds again afterward using a fresh combat_id
    (an Instance ID is never reused after its Combat has ended, per the ID
    System rules in CLAUDE.md/§4)."""
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
        conditions=frozenset({Condition.POISONED}),
    )
    character_lifecycle = CharacterState(
        id="character_001",
        total_level=1,
        saving_throw_proficiencies=frozenset(),
        skill_proficiencies=frozenset(),
        weapon_proficiencies=frozenset(),
    )
    inventory = InventoryState(
        owner_id="character_001",
        items=(InventoryItemState(id="item_001", definition_id="dagger"),),
    )
    equipment = EquipmentState(owner_id="character_001", equipped_weapon_id="item_001")
    snapshot = StateSnapshot(
        campaign=CampaignState(
            id="campaign_001", ruleset_id="dnd_5e", ruleset_version="5.1"
        ),
        creatures=(character, monster),
        characters=(character_lifecycle,),
        inventories=(inventory,),
        equipment=(equipment,),
    )
    FilesystemStateStore(campaigns_root).save(snapshot)

    state_path = campaigns_root / "campaign_001" / "state.json"

    # --- initial persisted state: combat absent under the current V9 writer -

    initial_raw = json.loads(state_path.read_text(encoding="utf-8"))
    assert initial_raw["schemaVersion"] == SCHEMA_VERSION == 9
    assert initial_raw["state"]["combat"] is None

    # --- Start Combat -> save -> fresh reload -> CombatState present -------

    seed = 20260913
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

    started_raw = json.loads(state_path.read_text(encoding="utf-8"))
    assert started_raw["schemaVersion"] == SCHEMA_VERSION == 9
    assert started_raw["state"]["combat"] is not None

    # --- End Combat -> save -> fresh reload -> combat absent again ----------

    end_result = EndCombatHandler(
        state_store=FilesystemStateStore(campaigns_root),
        event_metadata_provider=FixedEventMetadataProvider(),
    ).handle(
        EndCombatCommand(
            command_id="command_end_001",
            campaign_id="campaign_001",
            actor_id="character_001",
            payload=EndCombatPayload(combat_id="combat_001"),
        )
    )

    assert end_result.success is True
    assert end_result.outcome is not None
    assert end_result.outcome.combat_id == "combat_001"
    assert len(end_result.events) == 1
    ended_event = end_result.events[0]
    assert ended_event.type == "CombatEnded"
    assert ended_event.version == 1
    assert ended_event.payload == {"combatId": "combat_001"}

    after_end = FilesystemStateStore(campaigns_root).load("campaign_001")
    assert after_end.combat is None

    # unrelated persisted State is untouched by EndCombat, including existing
    # Character death-save/lifecycle facts, Inventory, and Equipment
    assert after_end.creatures == after_start.creatures
    assert after_end.characters == after_start.characters
    assert after_end.inventories == after_start.inventories
    assert after_end.equipment == after_start.equipment
    reloaded_character = next(
        creature for creature in after_end.creatures if creature.id == "character_001"
    )
    reloaded_monster = next(
        creature for creature in after_end.creatures if creature.id == "monster_001"
    )
    assert (reloaded_character.current_hp, reloaded_character.max_hp) == (20, 20)
    assert (reloaded_monster.current_hp, reloaded_monster.max_hp) == (7, 7)
    assert Condition.POISONED in reloaded_monster.conditions
    reloaded_character_lifecycle = after_end.characters[0]
    assert reloaded_character_lifecycle.death_save_successes == 0
    assert reloaded_character_lifecycle.death_save_failures == 0
    assert reloaded_character_lifecycle.death_save_stable is False
    assert reloaded_character_lifecycle.dead is False
    assert after_end.inventories[0].items == inventory.items
    assert after_end.equipment[0].equipped_weapon_id == "item_001"

    # --- current production V9 persistence contract: no schema bump --------

    ended_raw = json.loads(state_path.read_text(encoding="utf-8"))
    assert ended_raw["schemaVersion"] == SCHEMA_VERSION == 9
    assert ended_raw["state"]["combat"] is None
    assert ended_raw.keys() == initial_raw.keys()
    assert ended_raw["state"].keys() == initial_raw["state"].keys()

    # --- a brand-new Combat can start again after EndCombat -----------------
    # (a fresh combat_id is used: Instance IDs are never reused after their
    # entity has been removed/ended, per CLAUDE.md's ID System rules)

    reopen_seed = 424242
    reopen_result = StartCombatHandler(
        state_store=FilesystemStateStore(campaigns_root),
        dice=PythonDiceEngine(random.Random(reopen_seed)),
        event_metadata_provider=FixedEventMetadataProvider(),
    ).handle(
        StartCombatCommand(
            command_id="command_start_002",
            campaign_id="campaign_001",
            actor_id="character_001",
            payload=StartCombatPayload(
                combat_id="combat_002",
                participant_ids=("character_001", "monster_001"),
            ),
        )
    )

    assert reopen_result.success is True

    after_reopen = FilesystemStateStore(campaigns_root).load("campaign_001")
    assert after_reopen.combat is not None
    assert after_reopen.combat.id == "combat_002"

    # no Event history/EventStore artifacts, no other files created
    assert sorted(
        path.relative_to(state_path.parent).as_posix()
        for path in state_path.parent.rglob("*")
        if path.is_file()
    ) == ["state.json"]


def test_place_combatant_persists_new_position_through_fresh_reload(
    tmp_path: Path,
) -> None:
    """Real-adapter production proof for §3.36/TSK-0022: a real
    FilesystemStateStore and the production V9 StateSerializer persist a new
    CombatPosition written by a real PlaceCombatantHandler, visible after a
    fresh reload, alongside an existing pre-populated CombatPosition. The
    writer canonically sorts combat.positions by creature_id on serialize, so
    this test checks persisted position values/identity rather than assuming
    input tuple order survives a save/reload. No schema bump or unrelated
    wire-shape change occurs: schemaVersion stays 9 and the raw JSON top-level
    and state keys are unchanged before and after placement."""
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
    existing_position = CombatPosition(creature_id="monster_001", x=2, y=3)
    combat = CombatState(
        id="combat_001",
        round=1,
        order=("character_001", "monster_001"),
        active_index=0,
        positions=(existing_position,),
    )
    snapshot = StateSnapshot(
        campaign=CampaignState(
            id="campaign_001", ruleset_id="dnd_5e", ruleset_version="5.1"
        ),
        creatures=(character, monster),
        combat=combat,
    )
    FilesystemStateStore(campaigns_root).save(snapshot)

    state_path = campaigns_root / "campaign_001" / "state.json"
    before_raw = json.loads(state_path.read_text(encoding="utf-8"))
    assert before_raw["schemaVersion"] == SCHEMA_VERSION == 9

    # --- Place Combatant -> save -> fresh reload -> new position present ---

    place_result = PlaceCombatantHandler(
        state_store=FilesystemStateStore(campaigns_root),
        event_metadata_provider=FixedEventMetadataProvider(),
    ).handle(
        PlaceCombatantCommand(
            command_id="command_place_001",
            campaign_id="campaign_001",
            actor_id="character_001",
            payload=PlaceCombatantPayload(
                combat_id="combat_001",
                creature_id="character_001",
                x=5,
                y=10,
            ),
        )
    )

    assert place_result.success is True
    assert place_result.outcome is not None
    assert place_result.outcome.creature_id == "character_001"
    assert place_result.outcome.x == 5
    assert place_result.outcome.y == 10
    assert len(place_result.events) == 1
    placed_event = place_result.events[0]
    assert placed_event.type == "CombatantPlaced"
    assert placed_event.version == 1
    assert placed_event.payload == {
        "combatId": "combat_001",
        "creatureId": "character_001",
        "x": 5,
        "y": 10,
    }

    after_place = FilesystemStateStore(campaigns_root).load("campaign_001")
    assert after_place.combat is not None
    positions_by_creature_id = {
        position.creature_id: position for position in after_place.combat.positions
    }
    assert positions_by_creature_id.keys() == {"character_001", "monster_001"}
    assert positions_by_creature_id["character_001"] == CombatPosition(
        creature_id="character_001", x=5, y=10
    )
    # pre-existing position value survived unchanged
    assert positions_by_creature_id["monster_001"] == existing_position

    # unrelated Combat facts untouched
    assert after_place.combat.id == "combat_001"
    assert after_place.combat.round == 1
    assert after_place.combat.order == ("character_001", "monster_001")
    assert after_place.combat.active_index == 0
    assert after_place.combat.action_spent is False

    # unrelated Creature state untouched
    assert after_place.creatures == snapshot.creatures

    # --- current production V9 persistence contract: no schema bump --------

    after_raw = json.loads(state_path.read_text(encoding="utf-8"))
    assert after_raw["schemaVersion"] == SCHEMA_VERSION == 9
    assert after_raw.keys() == before_raw.keys()
    assert after_raw["state"].keys() == before_raw["state"].keys()
    assert after_raw["state"]["combat"].keys() == before_raw["state"]["combat"].keys()

    # positions are persisted sorted by creatureId, not necessarily input order
    persisted_positions = after_raw["state"]["combat"]["positions"]
    assert {
        (position["creatureId"], position["x"], position["y"])
        for position in persisted_positions
    } == {("character_001", 5, 10), ("monster_001", 2, 3)}
    assert [position["creatureId"] for position in persisted_positions] == sorted(
        position["creatureId"] for position in persisted_positions
    )

    # no Event history/EventStore artifacts, no other files created
    assert sorted(
        path.relative_to(state_path.parent).as_posix()
        for path in state_path.parent.rglob("*")
        if path.is_file()
    ) == ["state.json"]
