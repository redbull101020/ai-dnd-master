import json
import random
from datetime import datetime, timezone
from pathlib import Path

from dnd_engine.application.handlers.advance_turn import AdvanceTurnHandler
from dnd_engine.application.handlers.damage import DamageHandler
from dnd_engine.application.services.event_metadata import EventMetadata
from dnd_engine.domain.commands.advance_turn import (
    AdvanceTurnCommand,
    AdvanceTurnPayload,
)
from dnd_engine.domain.commands.damage import ApplyDamageCommand, ApplyDamagePayload
from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.state.combat import CombatState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.infrastructure.filesystem.state_store import FilesystemStateStore
from dnd_engine.infrastructure.random.dice import PythonDiceEngine


FIXED_TIMESTAMP = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)


class CountingStateStore:
    """Observe handler saves while delegating to the real StateStore."""

    def __init__(self, delegate: FilesystemStateStore) -> None:
        self._delegate = delegate
        self.save_calls: list[StateSnapshot] = []

    def load(self, campaign_id: str) -> StateSnapshot:
        return self._delegate.load(campaign_id)

    def save(self, snapshot: StateSnapshot) -> None:
        self.save_calls.append(snapshot)
        self._delegate.save(snapshot)


class SequentialEventMetadataProvider:
    """Distinct event_id per call, analogous to
    tests/integration/test_attack_real_adapters.py's
    SequentialEventMetadataProvider, so a multi-Event causedBy chain can be
    checked exactly rather than trivially matching a single shared
    event_id."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self._next_event_number = 999

    def next_metadata(self, campaign_id: str) -> EventMetadata:
        self.calls.append(campaign_id)
        event_id = f"event_{self._next_event_number:06d}"
        self._next_event_number += 1
        return EventMetadata(event_id=event_id, timestamp=FIXED_TIMESTAMP)


def make_creature(
    *, creature_id: str, definition_id: str, current_hp: int, max_hp: int
) -> CreatureState:
    return CreatureState(
        id=creature_id,
        definition_id=definition_id,
        ability_scores=AbilityScores(
            strength=12,
            dexterity=12,
            constitution=14,
            intelligence=10,
            wisdom=10,
            charisma=10,
        ),
        current_hp=current_hp,
        max_hp=max_hp,
    )


def test_v9_state_store_round_trip_preserves_character_lifecycle_state(
    tmp_path: Path,
) -> None:
    """Part A (TSK-0017): a StateSnapshot carrying valid, non-default
    Character death-save/lifecycle facts survives one exact save -> load
    round-trip through the real FilesystemStateStore/StateSerializer, and
    the on-disk JSON is exact production State schema V9 (§3.34, §12.13)."""
    campaigns_root = tmp_path / "campaigns"
    creature = make_creature(
        creature_id="character_001",
        definition_id="fighter",
        current_hp=0,
        max_hp=20,
    )
    character = CharacterState(
        id="character_001",
        total_level=3,
        saving_throw_proficiencies=frozenset(),
        skill_proficiencies=frozenset(),
        weapon_proficiencies=frozenset(),
        death_save_successes=1,
        death_save_failures=1,
        death_save_stable=False,
        dead=False,
    )
    original = StateSnapshot(
        campaign=CampaignState(
            id="campaign_001", ruleset_id="dnd_5e", ruleset_version="5.1"
        ),
        creatures=(creature,),
        characters=(character,),
    )

    FilesystemStateStore(campaigns_root).save(original)

    # fresh StateStore instance: only what production V9 actually wrote to
    # disk is being observed
    loaded = FilesystemStateStore(campaigns_root).load("campaign_001")

    assert loaded == original
    loaded_character = loaded.characters[0]
    assert loaded_character.death_save_successes == 1
    assert loaded_character.death_save_failures == 1
    assert loaded_character.death_save_stable is False
    assert loaded_character.dead is False

    state_path = campaigns_root / "campaign_001" / "state.json"
    data = json.loads(state_path.read_text(encoding="utf-8"))
    assert data["schemaVersion"] == 9
    assert data["state"]["characters"][0]["deathSaveSuccesses"] == 1
    assert data["state"]["characters"][0]["deathSaveFailures"] == 1
    assert data["state"]["characters"][0]["deathSaveStable"] is False
    assert data["state"]["characters"][0]["dead"] is False


def test_advance_turn_rolls_automatic_death_save_and_persists_through_real_filesystem(
    tmp_path: Path,
) -> None:
    """Part B (TSK-0017): the automatic turn-start Death Save (§3.34) fires
    from a real AdvanceTurnHandler through a real DiceEngine/StateStore, and
    the resulting Character lifecycle facts are visible after a fresh
    reload. One representative (ordinary success) roll is exercised here;
    the full success/failure/natural-1/natural-20 matrix is already covered
    by the Application unit tests."""
    campaigns_root = tmp_path / "campaigns"
    monster = make_creature(
        creature_id="monster_001", definition_id="goblin", current_hp=7, max_hp=7
    )
    down_creature = make_creature(
        creature_id="character_001",
        definition_id="fighter",
        current_hp=0,
        max_hp=20,
    )
    down_character = CharacterState(
        id="character_001",
        total_level=3,
        saving_throw_proficiencies=frozenset(),
        skill_proficiencies=frozenset(),
        weapon_proficiencies=frozenset(),
    )
    combat = CombatState(
        id="combat_001",
        round=1,
        order=("monster_001", "character_001"),
        active_index=0,
    )
    snapshot = StateSnapshot(
        campaign=CampaignState(
            id="campaign_001", ruleset_id="dnd_5e", ruleset_version="5.1"
        ),
        creatures=(monster, down_creature),
        characters=(down_character,),
        combat=combat,
    )
    FilesystemStateStore(campaigns_root).save(snapshot)

    store = CountingStateStore(FilesystemStateStore(campaigns_root))
    metadata = SequentialEventMetadataProvider()
    # random.Random(7).randint(1, 20) == 11: a deterministic ordinary
    # (non-critical) Death Save success.
    result = AdvanceTurnHandler(
        state_store=store,
        dice=PythonDiceEngine(random.Random(7)),
        event_metadata_provider=metadata,
    ).handle(
        AdvanceTurnCommand(
            command_id="command_advance_001",
            campaign_id="campaign_001",
            actor_id="monster_001",
            payload=AdvanceTurnPayload(combat_id="combat_001"),
        )
    )

    assert result.success is True
    assert result.outcome is not None
    assert result.outcome.active_creature_id == "character_001"
    assert [event.type for event in result.events] == [
        "TurnAdvanced",
        "CharacterDeathSaveResolved",
    ]
    turn_advanced_event = result.events[0]
    death_save_event = result.events[1]
    assert death_save_event.payload["roll"]["selected"] == 11
    assert death_save_event.payload["successes"] == 1
    assert death_save_event.payload["failures"] == 0
    assert death_save_event.payload["stable"] is False
    assert death_save_event.payload["dead"] is False

    # distinct, deterministic Event IDs: causedBy actually proves causation
    # rather than trivially matching a single shared event_id
    assert death_save_event.event_id != turn_advanced_event.event_id
    assert death_save_event.caused_by == turn_advanced_event.event_id
    assert metadata.calls == ["campaign_001", "campaign_001"]

    # exactly one authoritative snapshot persisted for this Command
    assert len(store.save_calls) == 1

    reloaded = FilesystemStateStore(campaigns_root).load("campaign_001")
    reloaded_character = reloaded.characters[0]
    assert reloaded_character.death_save_successes == 1
    assert reloaded_character.death_save_failures == 0
    assert reloaded_character.death_save_stable is False
    assert reloaded_character.dead is False
    reloaded_creature = next(
        creature for creature in reloaded.creatures if creature.id == "character_001"
    )
    # ordinary success does not regain HP
    assert reloaded_creature.current_hp == 0
    assert reloaded.combat is not None
    assert reloaded.combat.active_creature_id == "character_001"

    state_path = campaigns_root / "campaign_001" / "state.json"
    data = json.loads(state_path.read_text(encoding="utf-8"))
    assert data["schemaVersion"] == 9


def test_damage_at_zero_hp_records_death_save_failure_through_real_filesystem(
    tmp_path: Path,
) -> None:
    """Part C (TSK-0017): direct ApplyDamageCommand Damage against a
    Character already at zero HP (§3.34 "Damage at zero HP") records exactly
    one Death Save failure and persists it through the real StateStore,
    without changing current_hp (already floored at 0) or death_save_successes."""
    campaigns_root = tmp_path / "campaigns"
    actor = make_creature(
        creature_id="monster_001", definition_id="goblin", current_hp=7, max_hp=7
    )
    down_creature = make_creature(
        creature_id="character_001",
        definition_id="fighter",
        current_hp=0,
        max_hp=20,
    )
    down_character = CharacterState(
        id="character_001",
        total_level=3,
        saving_throw_proficiencies=frozenset(),
        skill_proficiencies=frozenset(),
        weapon_proficiencies=frozenset(),
        death_save_successes=1,
    )
    snapshot = StateSnapshot(
        campaign=CampaignState(
            id="campaign_001", ruleset_id="dnd_5e", ruleset_version="5.1"
        ),
        creatures=(actor, down_creature),
        characters=(down_character,),
    )
    FilesystemStateStore(campaigns_root).save(snapshot)

    store = CountingStateStore(FilesystemStateStore(campaigns_root))
    metadata = SequentialEventMetadataProvider()
    result = DamageHandler(
        state_store=store,
        event_metadata_provider=metadata,
    ).handle(
        ApplyDamageCommand(
            command_id="command_damage_001",
            campaign_id="campaign_001",
            actor_id="monster_001",
            payload=ApplyDamagePayload(target_id="character_001", amount=4),
        )
    )

    assert result.success is True
    assert result.outcome is not None
    assert result.outcome.previous_hp == 0
    assert result.outcome.new_hp == 0
    assert [event.type for event in result.events] == [
        "DamageApplied",
        "CharacterDeathSaveFailureRecorded",
    ]
    damage_applied_event = result.events[0]
    failure_event = result.events[1]
    assert failure_event.payload["previousFailures"] == 0
    assert failure_event.payload["failures"] == 1
    assert failure_event.payload["criticalHit"] is False
    assert failure_event.payload["dead"] is False

    # distinct, deterministic Event IDs: causedBy actually proves causation
    # rather than trivially matching a single shared event_id
    assert failure_event.event_id != damage_applied_event.event_id
    assert failure_event.caused_by == damage_applied_event.event_id
    assert metadata.calls == ["campaign_001", "campaign_001"]

    assert len(store.save_calls) == 1

    reloaded = FilesystemStateStore(campaigns_root).load("campaign_001")
    reloaded_creature = next(
        creature for creature in reloaded.creatures if creature.id == "character_001"
    )
    assert reloaded_creature.current_hp == 0
    reloaded_character = reloaded.characters[0]
    assert reloaded_character.death_save_successes == 1
    assert reloaded_character.death_save_failures == 1
    assert reloaded_character.death_save_stable is False
    assert reloaded_character.dead is False
