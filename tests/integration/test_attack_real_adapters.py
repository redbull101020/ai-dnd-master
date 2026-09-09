import random
from datetime import datetime, timezone
from pathlib import Path

from dnd_engine.application.handlers.attack import AttackHandler
from dnd_engine.application.services.event_metadata import EventMetadata
from dnd_engine.domain.commands.attack import AttackCommand, AttackPayload
from dnd_engine.domain.errors import ErrorCode
from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.state.combat import CombatPosition, CombatState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.equipment import EquipmentState
from dnd_engine.domain.state.inventory import InventoryItemState, InventoryState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability import Ability
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
                weapon_proficiencies=frozenset(),
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
                weapon_proficiencies=frozenset(),
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
    adapters end to end. Also carries the TSK-0015 §3.33 real-adapter
    evidence: the same reload proves `combat.action_spent is True`
    alongside the HP change from one combined save, and a second Attack
    by the same still-active actor is then rejected purely from that
    reloaded persisted fact."""
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
        weapon_proficiencies=frozenset(),
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
        weapon_proficiencies=frozenset(),
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

    assert metadata.calls == ["campaign_001"] * 4
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
    # -> DamageApplied -> TurnActionSpent (§3.33/TSK-0015).
    assert [event.type for event in result.events] == [
        "MonsterAttackResolved",
        "MonsterAttackDamageResolved",
        "DamageApplied",
        "TurnActionSpent",
    ]
    attack_event, damage_event, applied_event, action_spent_event = result.events

    # (7) causedBy chain is exact; TurnActionSpent is caused by the Attack
    # resolution Event, never by the Damage chain.
    assert attack_event.caused_by is None
    assert damage_event.caused_by == attack_event.event_id
    assert applied_event.caused_by == damage_event.event_id
    assert action_spent_event.caused_by == attack_event.event_id
    assert action_spent_event.payload == {"combatId": "combat_001"}
    assert (
        len(
            {
                attack_event.event_id,
                damage_event.event_id,
                applied_event.event_id,
                action_spent_event.event_id,
            }
        )
        == 4
    )

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

    # (3)/(4) CombatState still exists and is otherwise unchanged, except for
    # the Action this successful in-Combat Attack spent.
    assert reloaded.combat is not None
    assert reloaded.combat.id == combat.id
    assert reloaded.combat.round == combat.round
    assert reloaded.combat.order == combat.order
    assert reloaded.combat.active_index == combat.active_index
    # State schema V8 (`actionSpent`, §3.33/DEC-0049) persists Action
    # expenditure through a real filesystem reload.
    assert reloaded.combat.action_spent is True

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

    # (9) TSK-0015 end-to-end persisted-eligibility proof: the
    # `action_spent=True` fact just reloaded from real V8 JSON (not the
    # in-memory result above) is what gates a second Attack by the same
    # still-active actor, rejected before any Definition/dice/Event/save
    # side effect. The exact side-effect boundary itself is already proven
    # by the Application unit tests (Group 2); this proves the real
    # writer/reader round trip actually feeds that gate.
    second_result = AttackHandler(
        state_store=FilesystemStateStore(campaigns_root),
        definition_source=PackagedDefinitionSource(),
        dice=PythonDiceEngine(rng),
        event_metadata_provider=metadata,
    ).handle(command)

    assert second_result.success is False
    assert second_result.outcome is None
    assert second_result.events == ()
    assert len(second_result.errors) == 1
    assert second_result.errors[0].code is ErrorCode.ACTION_NOT_AVAILABLE
    assert second_result.errors[0].entity_id == "monster_001"
    assert metadata.calls == ["campaign_001"] * 4
    assert state_path.read_bytes() == state_after


# --- Character Dagger weapon Attack (TSK-0012/TSK-0013 Group 4) -------


def test_character_dagger_hit_applies_damage_and_persists_through_real_adapters(
    tmp_path: Path,
) -> None:
    """TSK-0013 Group 4 production-real integration evidence: a Character
    Dagger weapon Attack that hits rolls its own authoritative source Damage
    and applies it to the Goblin target's current_hp, durably visible after
    a fresh FilesystemStateStore reload -- alongside untouched Character/
    Inventory/Equipment/Combat projections -- using the real
    FilesystemStateStore (State schema V7), StateSerializer, real
    PackagedDefinitionSource (packaged dnd_5e/5.1 Dagger and Goblin
    Definitions), and PythonDiceEngine adapters end to end. Evolves the
    former TSK-0012 read-only variant of this same deterministic setup now
    that TSK-0013 continues the Attack into source Damage and Damage
    Application."""
    campaigns_root = tmp_path / "campaigns"

    actor = CreatureState(
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
    character = CharacterState(
        id="character_001",
        total_level=5,
        saving_throw_proficiencies=frozenset(),
        skill_proficiencies=frozenset(),
        weapon_proficiencies=frozenset({"dagger"}),
    )
    inventory = InventoryState(
        owner_id="character_001",
        items=(InventoryItemState(id="item_001", definition_id="dagger"),),
    )
    equipment = EquipmentState(
        owner_id="character_001", equipped_weapon_id="item_001"
    )
    combat = CombatState(
        id="combat_001",
        round=1,
        order=("character_001", "monster_001"),
        active_index=0,
        positions=(
            CombatPosition(creature_id="character_001", x=0, y=0),
            CombatPosition(creature_id="monster_001", x=3, y=4),
        ),
    )
    snapshot = StateSnapshot(
        campaign=CampaignState(
            id="campaign_001",
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
        ),
        creatures=(actor, target),
        characters=(character,),
        inventories=(inventory,),
        equipment=(equipment,),
        combat=combat,
    )
    real_store = FilesystemStateStore(campaigns_root)
    real_store.save(snapshot)

    state_path = campaigns_root / "campaign_001" / "state.json"
    state_before = state_path.read_bytes()

    store = CountingStateStore(real_store)
    metadata = SequentialEventMetadataProvider()

    # seed 20260901: 1d20 == 15 (Attack), then 1d4 == 1 (Dagger Damage).
    seed = 20260901
    rng = random.Random(seed)
    expected_rng = random.Random(seed)
    expected_attack_roll = expected_rng.randint(1, 20)
    expected_damage_roll = expected_rng.randint(1, 4)
    assert (expected_attack_roll, expected_damage_roll) == (15, 1)

    expected_ability_modifier = 2  # dexterity 14 -> modifier +2.
    expected_damage_amount = expected_damage_roll + expected_ability_modifier
    expected_previous_hp = target.current_hp
    expected_new_hp = expected_previous_hp - expected_damage_amount

    command = AttackCommand(
        command_id="command_000501",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=AttackPayload(
            target_id="monster_001",
            weapon_item_id="item_001",
            weapon_ability=Ability.DEXTERITY,
        ),
    )

    result = AttackHandler(
        state_store=store,
        definition_source=PackagedDefinitionSource(),
        dice=PythonDiceEngine(rng),
        event_metadata_provider=metadata,
    ).handle(command)

    # exactly the expected 1d20 + 1d4 sequence was consumed -- no hidden
    # additional RNG calls.
    assert rng.getstate() == expected_rng.getstate()
    assert metadata.calls == ["campaign_001"] * 4

    assert result.success is True
    assert result.errors == ()
    outcome = result.outcome
    assert outcome is not None
    assert outcome.target_id == "monster_001"
    assert outcome.roll.mode is RollMode.NORMAL
    assert outcome.roll.rolls == (expected_attack_roll,)
    assert outcome.roll.selected == expected_attack_roll
    assert outcome.ability is Ability.DEXTERITY
    # dexterity 14 -> modifier +2; strength 16 -> modifier +3 would leak
    # through here if Finesse silently fell back to the unarmed Strength
    # path, so this pins the explicit choice is honoured.
    assert outcome.ability_modifier == expected_ability_modifier
    assert outcome.proficiency_bonus == 3
    assert outcome.total == 20
    assert outcome.target_armor_class == 15
    assert outcome.hit is True
    assert outcome.critical_hit is False

    # exact Event order: CharacterWeaponAttackResolved ->
    # CharacterWeaponAttackDamageResolved -> DamageApplied ->
    # TurnActionSpent (§3.33/TSK-0015).
    assert [event.type for event in result.events] == [
        "CharacterWeaponAttackResolved",
        "CharacterWeaponAttackDamageResolved",
        "DamageApplied",
        "TurnActionSpent",
    ]
    attack_event, damage_event, applied_event, action_spent_event = result.events

    # exact immediate causedBy chain; DamageApplied never skips the
    # source-Damage Event; TurnActionSpent is caused by the Attack
    # resolution Event, never by the Damage chain.
    assert attack_event.caused_by is None
    assert damage_event.caused_by == attack_event.event_id
    assert applied_event.caused_by == damage_event.event_id
    assert action_spent_event.caused_by == attack_event.event_id
    assert action_spent_event.payload == {"combatId": "combat_001"}
    assert (
        len(
            {
                attack_event.event_id,
                damage_event.event_id,
                applied_event.event_id,
                action_spent_event.event_id,
            }
        )
        == 4
    )
    assert all(event.command_id == command.command_id for event in result.events)
    assert all(event.campaign_id == "campaign_001" for event in result.events)
    assert all(event.actor_id == "character_001" for event in result.events)
    assert all(event.timestamp == FIXED_TIMESTAMP for event in result.events)

    assert attack_event.version == 1
    assert attack_event.payload == {
        "targetId": "monster_001",
        "weaponItemId": "item_001",
        "weaponDefinitionId": "dagger",
        "roll": {
            "mode": "normal",
            "rolls": (expected_attack_roll,),
            "selected": expected_attack_roll,
        },
        "ability": "dexterity",
        "abilityModifier": expected_ability_modifier,
        "proficiencyBonus": 3,
        "total": 20,
        "targetArmorClass": 15,
        "hit": True,
        "criticalHit": False,
    }
    assert damage_event.version == 1
    assert damage_event.payload == {
        "targetId": "monster_001",
        "weaponItemId": "item_001",
        "weaponDefinitionId": "dagger",
        "roll": {
            "expression": "1d4",
            "rolls": (expected_damage_roll,),
            "total": expected_damage_roll,
        },
        "ability": "dexterity",
        "abilityModifier": expected_ability_modifier,
        "damageType": "piercing",
        "criticalHit": False,
        "amount": expected_damage_amount,
    }
    assert applied_event.version == 1
    assert applied_event.payload == {
        "targetId": "monster_001",
        "amount": expected_damage_amount,
        "previousHp": expected_previous_hp,
        "newHp": expected_new_hp,
    }

    # exactly one State snapshot save; the state file is no longer
    # byte-identical after the positive hit.
    assert len(store.save_calls) == 1
    assert store.save_calls[0] is not snapshot
    state_after = state_path.read_bytes()
    assert state_after != state_before

    # fresh reload through a brand new FilesystemStateStore instance --
    # proves a real filesystem round trip, not just the in-memory save arg.
    reloaded = FilesystemStateStore(campaigns_root).load("campaign_001")
    reloaded_actor = next(
        creature for creature in reloaded.creatures if creature.id == "character_001"
    )
    reloaded_target = next(
        creature for creature in reloaded.creatures if creature.id == "monster_001"
    )
    assert (reloaded_actor.current_hp, reloaded_actor.max_hp) == (20, 20)
    assert reloaded_target.current_hp == expected_new_hp
    assert reloaded_target.current_hp == expected_previous_hp - expected_damage_amount
    assert reloaded_target.max_hp == target.max_hp
    reloaded_character = next(
        candidate
        for candidate in reloaded.characters
        if candidate.id == "character_001"
    )
    assert reloaded_character.weapon_proficiencies == frozenset({"dagger"})
    reloaded_inventory = next(
        candidate
        for candidate in reloaded.inventories
        if candidate.owner_id == "character_001"
    )
    assert reloaded_inventory.items == (
        InventoryItemState(id="item_001", definition_id="dagger"),
    )
    reloaded_equipment = next(
        candidate
        for candidate in reloaded.equipment
        if candidate.owner_id == "character_001"
    )
    assert reloaded_equipment.equipped_weapon_id == "item_001"
    assert reloaded.combat is not None
    assert reloaded.combat.id == combat.id
    assert reloaded.combat.round == combat.round
    assert reloaded.combat.order == combat.order
    assert reloaded.combat.active_index == combat.active_index
    assert reloaded.combat.positions == combat.positions
    # State schema V8 (`actionSpent`, §3.33/DEC-0049) persists Action
    # expenditure through a real filesystem reload.
    assert reloaded.combat.action_spent is True

    # no Event history artifacts, no other files, no leftover temp files.
    assert sorted(
        path.relative_to(state_path.parent).as_posix()
        for path in state_path.parent.rglob("*")
        if path.is_file()
    ) == ["state.json"]
    assert list(state_path.parent.glob(".state-*.tmp")) == []


def test_character_dagger_attack_out_of_range_via_real_adapters_rejects_before_roll(
    tmp_path: Path,
) -> None:
    """TSK-0012 Group 4: a representative real-adapter pre-resolution
    failure. A Character with a valid authoritative Dagger source and a
    valid explicit Finesse choice, positioned outside the canonical 5-ft
    melee reach, is rejected with OUT_OF_RANGE before any RNG consumption,
    Event metadata allocation, or State save."""
    campaigns_root = tmp_path / "campaigns"

    actor = CreatureState(
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
    character = CharacterState(
        id="character_001",
        total_level=5,
        saving_throw_proficiencies=frozenset(),
        skill_proficiencies=frozenset(),
        weapon_proficiencies=frozenset({"dagger"}),
    )
    inventory = InventoryState(
        owner_id="character_001",
        items=(InventoryItemState(id="item_001", definition_id="dagger"),),
    )
    equipment = EquipmentState(
        owner_id="character_001", equipped_weapon_id="item_001"
    )
    combat = CombatState(
        id="combat_001",
        round=1,
        order=("character_001", "monster_001"),
        active_index=0,
        positions=(
            CombatPosition(creature_id="character_001", x=0, y=0),
            CombatPosition(creature_id="monster_001", x=0, y=6),
        ),
    )
    snapshot = StateSnapshot(
        campaign=CampaignState(
            id="campaign_001",
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
        ),
        creatures=(actor, target),
        characters=(character,),
        inventories=(inventory,),
        equipment=(equipment,),
        combat=combat,
    )
    real_store = FilesystemStateStore(campaigns_root)
    real_store.save(snapshot)

    state_path = campaigns_root / "campaign_001" / "state.json"
    state_before = state_path.read_bytes()

    store = CountingStateStore(real_store)
    metadata = FixedEventMetadataProvider()

    seed = 20260901
    rng = random.Random(seed)
    rng_state_before = rng.getstate()

    command = AttackCommand(
        command_id="command_000502",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=AttackPayload(
            target_id="monster_001",
            weapon_item_id="item_001",
            weapon_ability=Ability.DEXTERITY,
        ),
    )

    result = AttackHandler(
        state_store=store,
        definition_source=PackagedDefinitionSource(),
        dice=PythonDiceEngine(rng),
        event_metadata_provider=metadata,
    ).handle(command)

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.OUT_OF_RANGE
    assert result.errors[0].entity_id == "monster_001"
    assert result.errors[0].field is None

    # no RNG state consumption, no Event metadata allocation, no State save.
    assert rng.getstate() == rng_state_before
    assert metadata.calls == []
    assert store.save_calls == []
    assert state_path.read_bytes() == state_before

    assert sorted(
        path.relative_to(state_path.parent).as_posix()
        for path in state_path.parent.rglob("*")
        if path.is_file()
    ) == ["state.json"]
    assert list(state_path.parent.glob(".state-*.tmp")) == []
