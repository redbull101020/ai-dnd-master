import random
from datetime import datetime, timezone
from pathlib import Path

from dnd_engine.application.handlers.attack import AttackHandler
from dnd_engine.application.services.event_metadata import EventMetadata
from dnd_engine.domain.commands.attack import AttackCommand, AttackPayload
from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.state.combat import CombatState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.domain.value_objects.d20 import RollMode
from dnd_engine.infrastructure.definitions.packaged import PackagedDefinitionSource
from dnd_engine.infrastructure.filesystem.state_store import FilesystemStateStore
from dnd_engine.infrastructure.random.dice import PythonDiceEngine


FIXED_TIMESTAMP = datetime(2026, 8, 28, 13, 0, tzinfo=timezone.utc)


class FixedEventMetadataProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def next_metadata(self, campaign_id: str) -> EventMetadata:
        self.calls.append(campaign_id)
        return EventMetadata(
            event_id="event_000456",
            timestamp=FIXED_TIMESTAMP,
        )


def test_attack_uses_real_state_definition_and_dice_adapters_read_only(
    tmp_path: Path,
) -> None:
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
            dexterity=30,
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
        characters=(
            CharacterState(
                id="character_001",
                total_level=5,
                saving_throw_proficiencies=frozenset(),
                skill_proficiencies=frozenset(),
            ),
        ),
    )
    store = FilesystemStateStore(campaigns_root)
    store.save(snapshot)

    state_path = campaigns_root / "campaign_001" / "state.json"
    state_before = state_path.read_bytes()
    metadata = FixedEventMetadataProvider()
    seed = 20260828
    rng = random.Random(seed)
    expected_rng = random.Random(seed)
    expected_roll = expected_rng.randint(1, 20)
    command = AttackCommand(
        command_id="command_000123",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=AttackPayload(target_id="monster_001"),
    )

    result = AttackHandler(
        state_store=store,
        definition_source=PackagedDefinitionSource(),
        dice=PythonDiceEngine(rng),
        event_metadata_provider=metadata,
    ).handle(command)

    assert expected_roll == 12
    assert rng.getstate() == expected_rng.getstate()
    assert metadata.calls == ["campaign_001"]
    assert result.success is True
    assert result.outcome is not None
    assert result.errors == ()
    outcome = result.outcome
    assert outcome.roll.mode is RollMode.NORMAL
    assert outcome.roll.rolls == (expected_roll,)
    assert outcome.ability_modifier == 3
    assert outcome.proficiency_bonus == 3
    assert outcome.total == 18
    assert outcome.target_armor_class == 15
    assert 10 + 10 != outcome.target_armor_class
    assert outcome.hit is True
    assert outcome.critical_hit is False

    assert len(result.events) == 1
    event = result.events[0]
    assert event.event_id == "event_000456"
    assert event.command_id == command.command_id
    assert event.type == "AttackResolved"
    assert event.version == 1
    assert event.campaign_id == command.campaign_id
    assert event.timestamp == FIXED_TIMESTAMP
    assert event.actor_id == command.actor_id
    assert event.caused_by is None
    assert event.payload == {
        "targetId": "monster_001",
        "roll": {
            "mode": "normal",
            "rolls": (expected_roll,),
            "selected": expected_roll,
        },
        "ability": "strength",
        "abilityModifier": 3,
        "proficiencyBonus": 3,
        "total": 18,
        "targetArmorClass": 15,
        "hit": True,
        "criticalHit": False,
    }

    assert state_path.read_bytes() == state_before
    persisted = store.load("campaign_001")
    persisted_actor = next(
        creature for creature in persisted.creatures if creature.id == "character_001"
    )
    persisted_target = next(
        creature for creature in persisted.creatures if creature.id == "monster_001"
    )
    assert (persisted_actor.current_hp, persisted_actor.max_hp) == (20, 20)
    assert (persisted_target.current_hp, persisted_target.max_hp) == (7, 7)
    assert sorted(
        path.relative_to(state_path.parent).as_posix()
        for path in state_path.parent.rglob("*")
        if path.is_file()
    ) == ["state.json"]
    assert list(state_path.parent.glob(".state-*.tmp")) == []


def test_goblin_scimitar_attacks_character_using_real_packaged_adapters(
    tmp_path: Path,
) -> None:
    campaigns_root = tmp_path / "campaigns"
    goblin_actor = CreatureState(
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
    character_target = CreatureState(
        id="character_001",
        definition_id="fighter",
        ability_scores=AbilityScores(
            strength=16,
            dexterity=14,
            constitution=14,
            intelligence=10,
            wisdom=10,
            charisma=10,
        ),
        current_hp=20,
        max_hp=20,
    )
    snapshot = StateSnapshot(
        campaign=CampaignState(
            id="campaign_001",
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
        ),
        creatures=(goblin_actor, character_target),
        characters=(
            CharacterState(
                id="character_001",
                total_level=5,
                saving_throw_proficiencies=frozenset(),
                skill_proficiencies=frozenset(),
            ),
        ),
    )
    store = FilesystemStateStore(campaigns_root)
    store.save(snapshot)

    state_path = campaigns_root / "campaign_001" / "state.json"
    state_before = state_path.read_bytes()
    metadata = FixedEventMetadataProvider()
    seed = 20260830
    rng = random.Random(seed)
    expected_rng = random.Random(seed)
    expected_roll = expected_rng.randint(1, 20)
    command = AttackCommand(
        command_id="command_000789",
        campaign_id="campaign_001",
        actor_id="monster_001",
        payload=AttackPayload(target_id="character_001"),
    )

    result = AttackHandler(
        state_store=store,
        definition_source=PackagedDefinitionSource(),
        dice=PythonDiceEngine(rng),
        event_metadata_provider=metadata,
    ).handle(command)

    # dexterity 14 -> modifier +2 -> unarmored Character AC 12.
    expected_ac = 12
    expected_total = expected_roll + 4

    assert metadata.calls == ["campaign_001"]
    assert result.success is True
    assert result.errors == ()
    outcome = result.outcome
    assert outcome is not None
    assert outcome.target_id == "character_001"
    assert outcome.action_id == "scimitar"
    assert outcome.roll.mode is RollMode.NORMAL
    assert outcome.roll.rolls == (expected_roll,)
    assert outcome.attack_bonus == 4
    assert outcome.total == expected_total
    assert outcome.target_armor_class == expected_ac

    assert len(result.events) == 1
    event = result.events[0]
    assert event.event_id == "event_000456"
    assert event.command_id == command.command_id
    assert event.type == "MonsterAttackResolved"
    assert event.version == 1
    assert event.campaign_id == command.campaign_id
    assert event.timestamp == FIXED_TIMESTAMP
    assert event.actor_id == "monster_001"
    assert event.caused_by is None
    assert event.payload == {
        "targetId": "character_001",
        "actionId": "scimitar",
        "roll": {
            "mode": "normal",
            "rolls": (expected_roll,),
            "selected": expected_roll,
        },
        "attackBonus": 4,
        "total": expected_total,
        "targetArmorClass": expected_ac,
        "hit": outcome.hit,
        "criticalHit": outcome.critical_hit,
    }

    assert state_path.read_bytes() == state_before
    persisted = store.load("campaign_001")
    persisted_actor = next(
        creature for creature in persisted.creatures if creature.id == "monster_001"
    )
    persisted_target = next(
        creature for creature in persisted.creatures if creature.id == "character_001"
    )
    assert (persisted_actor.current_hp, persisted_actor.max_hp) == (7, 7)
    assert (persisted_target.current_hp, persisted_target.max_hp) == (20, 20)


class CountingStateStore:
    """Thin call-counting wrapper around a real StateStore, for observing
    the AttackHandler's own save() call count without instrumenting the
    production FilesystemStateStore adapter itself."""

    def __init__(self, delegate: FilesystemStateStore) -> None:
        self._delegate = delegate
        self.save_calls: list[StateSnapshot] = []

    def load(self, campaign_id: str) -> StateSnapshot:
        return self._delegate.load(campaign_id)

    def save(self, snapshot: StateSnapshot) -> None:
        self.save_calls.append(snapshot)
        self._delegate.save(snapshot)


class SequentialEventMetadataProvider:
    """Distinct event_id per call, so the causedBy chain produced by the
    Attack -> Damage -> HP application pipeline can be checked exactly
    rather than trivially matching a single shared event_id."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self._next_event_number = 801

    def next_metadata(self, campaign_id: str) -> EventMetadata:
        self.calls.append(campaign_id)
        event_id = f"event_{self._next_event_number:06d}"
        self._next_event_number += 1
        return EventMetadata(event_id=event_id, timestamp=FIXED_TIMESTAMP)


def test_goblin_scimitar_hit_applies_damage_and_persists_through_real_adapters(
    tmp_path: Path,
) -> None:
    """G9 Group 4 production-real integration evidence: a Goblin Scimitar
    attack that hits rolls its own damage, applies it to the Character
    target's current_hp, and is durably visible after a fresh
    FilesystemStateStore reload -- alongside an untouched CombatState and
    untouched unrelated Creature/Character projections -- using the real
    FilesystemStateStore, PackagedDefinitionSource, and PythonDiceEngine
    adapters end to end."""
    campaigns_root = tmp_path / "campaigns"

    goblin_actor = CreatureState(
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
    character_target = CreatureState(
        id="character_001",
        definition_id="fighter",
        ability_scores=AbilityScores(
            strength=16,
            dexterity=14,
            constitution=14,
            intelligence=10,
            wisdom=10,
            charisma=10,
        ),
        current_hp=20,
        max_hp=20,
    )
    character_target_projection = CharacterState(
        id="character_001",
        total_level=5,
        saving_throw_proficiencies=frozenset(),
        skill_proficiencies=frozenset(),
    )
    bystander_monster = CreatureState(
        id="monster_002",
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
    bystander_character_creature = CreatureState(
        id="character_002",
        definition_id="fighter",
        ability_scores=AbilityScores(
            strength=12,
            dexterity=12,
            constitution=12,
            intelligence=12,
            wisdom=12,
            charisma=12,
        ),
        current_hp=15,
        max_hp=18,
    )
    bystander_character_projection = CharacterState(
        id="character_002",
        total_level=3,
        saving_throw_proficiencies=frozenset(),
        skill_proficiencies=frozenset(),
    )
    combat = CombatState(
        id="combat_001",
        round=3,
        order=("character_001", "monster_001"),
        active_index=1,
    )
    assert combat.active_creature_id == "monster_001"

    snapshot = StateSnapshot(
        campaign=CampaignState(
            id="campaign_001",
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
        ),
        creatures=(
            goblin_actor,
            character_target,
            bystander_monster,
            bystander_character_creature,
        ),
        characters=(character_target_projection, bystander_character_projection),
        combat=combat,
    )
    real_store = FilesystemStateStore(campaigns_root)
    real_store.save(snapshot)

    state_path = campaigns_root / "campaign_001" / "state.json"
    state_before = state_path.read_bytes()

    store = CountingStateStore(real_store)
    metadata = SequentialEventMetadataProvider()

    # dexterity 14 -> modifier +2 -> unarmored Character AC 12.
    # seed 20260838: 1d20 == 12 (attack), then 1d6 == 5 (Scimitar damage).
    seed = 20260838
    rng = random.Random(seed)
    expected_rng = random.Random(seed)
    expected_attack_roll = expected_rng.randint(1, 20)
    expected_damage_roll = expected_rng.randint(1, 6)
    assert (expected_attack_roll, expected_damage_roll) == (12, 5)

    expected_ac = 12
    expected_total = expected_attack_roll + 4
    expected_damage_amount = expected_damage_roll + 2
    expected_previous_hp = character_target.current_hp
    expected_new_hp = expected_previous_hp - expected_damage_amount

    command = AttackCommand(
        command_id="command_000901",
        campaign_id="campaign_001",
        actor_id="monster_001",
        payload=AttackPayload(target_id="character_001"),
    )

    result = AttackHandler(
        state_store=store,
        definition_source=PackagedDefinitionSource(),
        dice=PythonDiceEngine(rng),
        event_metadata_provider=metadata,
    ).handle(command)

    assert metadata.calls == ["campaign_001"] * 3
    assert result.success is True
    assert result.errors == ()
    outcome = result.outcome
    assert outcome is not None
    assert outcome.target_id == "character_001"
    assert outcome.action_id == "scimitar"
    assert outcome.total == expected_total
    assert outcome.target_armor_class == expected_ac
    assert outcome.hit is True
    assert outcome.critical_hit is False

    # (6) Events are ordered MonsterAttackResolved -> MonsterAttackDamageResolved
    # -> DamageApplied.
    assert [event.type for event in result.events] == [
        "MonsterAttackResolved",
        "MonsterAttackDamageResolved",
        "DamageApplied",
    ]
    attack_event, damage_event, applied_event = result.events

    # (7) causedBy chain is exact.
    assert attack_event.caused_by is None
    assert damage_event.caused_by == attack_event.event_id
    assert applied_event.caused_by == damage_event.event_id
    assert len({attack_event.event_id, damage_event.event_id, applied_event.event_id}) == 3

    assert attack_event.payload == {
        "targetId": "character_001",
        "actionId": "scimitar",
        "roll": {
            "mode": "normal",
            "rolls": (expected_attack_roll,),
            "selected": expected_attack_roll,
        },
        "attackBonus": 4,
        "total": expected_total,
        "targetArmorClass": expected_ac,
        "hit": True,
        "criticalHit": False,
    }
    assert damage_event.payload == {
        "targetId": "character_001",
        "actionId": "scimitar",
        "roll": {
            "expression": "1d6",
            "rolls": (expected_damage_roll,),
            "total": expected_damage_roll,
        },
        "damageModifier": 2,
        "damageType": "slashing",
        "criticalHit": False,
        "amount": expected_damage_amount,
    }
    assert applied_event.payload == {
        "targetId": "character_001",
        "amount": expected_damage_amount,
        "previousHp": expected_previous_hp,
        "newHp": expected_new_hp,
    }

    # (8) one successful attack invocation results in one State snapshot save.
    assert len(store.save_calls) == 1
    assert store.save_calls[0] is not snapshot
    state_after = state_path.read_bytes()
    assert state_after != state_before

    # fresh reload through a brand new FilesystemStateStore instance.
    reloaded = FilesystemStateStore(campaigns_root).load("campaign_001")

    # (1)/(2) Character current_hp decreased by the authoritative applied
    # amount, and the reloaded State matches the saved HP result.
    reloaded_target = next(
        creature for creature in reloaded.creatures if creature.id == "character_001"
    )
    assert reloaded_target.current_hp == expected_new_hp
    assert reloaded_target.current_hp == expected_previous_hp - expected_damage_amount
    assert reloaded_target.max_hp == character_target.max_hp

    # (3)/(4) CombatState still exists and is byte-for-byte unchanged.
    assert reloaded.combat is not None
    assert reloaded.combat.id == combat.id
    assert reloaded.combat.round == combat.round
    assert reloaded.combat.order == combat.order
    assert reloaded.combat.active_index == combat.active_index

    # (5) no unrelated Creature/Character projection changed.
    reloaded_actor = next(
        creature for creature in reloaded.creatures if creature.id == "monster_001"
    )
    reloaded_bystander_monster = next(
        creature for creature in reloaded.creatures if creature.id == "monster_002"
    )
    reloaded_bystander_character_creature = next(
        creature for creature in reloaded.creatures if creature.id == "character_002"
    )
    assert reloaded_actor == goblin_actor
    assert reloaded_bystander_monster == bystander_monster
    assert reloaded_bystander_character_creature == bystander_character_creature
    assert reloaded.campaign == snapshot.campaign
    assert sorted(reloaded.characters, key=lambda character: character.id) == sorted(
        (character_target_projection, bystander_character_projection),
        key=lambda character: character.id,
    )

    # no Event history artifacts, no other files, no leftover temp files.
    assert sorted(
        path.relative_to(state_path.parent).as_posix()
        for path in state_path.parent.rglob("*")
        if path.is_file()
    ) == ["state.json"]
    assert list(state_path.parent.glob(".state-*.tmp")) == []
