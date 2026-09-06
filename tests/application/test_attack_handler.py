from copy import deepcopy
from datetime import datetime, timezone

import pytest

from dnd_engine.application.handlers.attack import AttackHandler
from dnd_engine.application.services.event_metadata import EventMetadata
from dnd_engine.domain.commands.attack import AttackCommand, AttackPayload
from dnd_engine.domain.definitions.monster import MonsterDefinition
from dnd_engine.domain.definitions.monster_attack import MonsterAttackDefinition
from dnd_engine.domain.errors import ErrorCode
from dnd_engine.domain.services.definitions import (
    DefinitionNotFoundError,
    DefinitionTypeMismatchError,
)
from dnd_engine.domain.services.state_store import StateStoreError
from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.state.combat import CombatState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.domain.value_objects.condition import Condition
from dnd_engine.domain.value_objects.d20 import RollMode
from dnd_engine.domain.value_objects.damage_type import DamageType
from dnd_engine.domain.value_objects.dice_roll import DiceRoll
from dnd_engine.infrastructure.definitions.packaged import (
    InvalidPackagedDefinitionError,
)


FIXED_TIMESTAMP = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


class SpyStateStore:
    def __init__(self, snapshot: StateSnapshot, calls: list[str]) -> None:
        self.snapshot = snapshot
        self._calls = calls
        self.load_calls: list[str] = []
        self.save_calls: list[StateSnapshot] = []

    def load(self, campaign_id: str) -> StateSnapshot:
        self._calls.append("load")
        self.load_calls.append(campaign_id)
        return self.snapshot

    def save(self, snapshot: StateSnapshot) -> None:
        self._calls.append("save")
        self.save_calls.append(snapshot)


class FailingStateStore(SpyStateStore):
    def load(self, campaign_id: str) -> StateSnapshot:
        self._calls.append("load")
        self.load_calls.append(campaign_id)
        raise StateStoreError("state backend unavailable")


class SaveFailingStateStore(SpyStateStore):
    def save(self, snapshot: StateSnapshot) -> None:
        self._calls.append("save")
        self.save_calls.append(snapshot)
        raise StateStoreError("state backend unavailable")


class ScriptedDiceEngine:
    def __init__(
        self,
        raw_roll: int,
        calls: list[str],
        *,
        additional_rolls: tuple[int | tuple[int, ...], ...] = (),
        fail: bool = False,
    ) -> None:
        self._raw_rolls = iter((raw_roll, *additional_rolls))
        self._calls = calls
        self._fail = fail
        self.roll_calls: list[str] = []

    def roll(self, expression: str) -> DiceRoll:
        self._calls.append("dice")
        self.roll_calls.append(expression)
        if self._fail:
            raise RuntimeError("dice unavailable")
        raw_roll = next(self._raw_rolls)
        rolls = (raw_roll,) if type(raw_roll) is int else raw_roll
        return DiceRoll(
            expression=expression,
            rolls=rolls,
            total=sum(rolls),
        )


class SpyDefinitionSource:
    def __init__(
        self,
        definition: MonsterDefinition,
        calls: list[str],
        *,
        error: Exception | None = None,
    ) -> None:
        self._definition = definition
        self._calls = calls
        self._error = error
        self.get_calls: list[dict[str, object]] = []

    def get_definition(
        self,
        *,
        ruleset_id: str,
        ruleset_version: str,
        definition_id: str,
        expected_type: type[MonsterDefinition],
    ) -> MonsterDefinition:
        self._calls.append("definition")
        self.get_calls.append(
            {
                "ruleset_id": ruleset_id,
                "ruleset_version": ruleset_version,
                "definition_id": definition_id,
                "expected_type": expected_type,
            }
        )
        if self._error is not None:
            raise self._error
        return self._definition


class FixedEventMetadataProvider:
    def __init__(self, calls: list[str], *, fail: bool = False) -> None:
        self._calls = calls
        self._fail = fail
        self.next_calls: list[str] = []
        self._next_event_number = 123

    def next_metadata(self, campaign_id: str) -> EventMetadata:
        self._calls.append("metadata")
        self.next_calls.append(campaign_id)
        if self._fail:
            raise RuntimeError("metadata unavailable")
        metadata = EventMetadata(
            event_id=f"event_{self._next_event_number:06d}",
            timestamp=FIXED_TIMESTAMP,
        )
        self._next_event_number += 1
        return metadata


def make_creature(
    *,
    creature_id: str,
    definition_id: str,
    strength: int = 10,
    dexterity: int = 10,
    current_hp: int = 20,
    max_hp: int = 20,
    conditions: frozenset[Condition] = frozenset(),
) -> CreatureState:
    return CreatureState(
        id=creature_id,
        definition_id=definition_id,
        ability_scores=AbilityScores(
            strength=strength,
            dexterity=dexterity,
            constitution=10,
            intelligence=10,
            wisdom=10,
            charisma=10,
        ),
        current_hp=current_hp,
        max_hp=max_hp,
        conditions=conditions,
    )


def make_actor(
    *, conditions: frozenset[Condition] = frozenset(), current_hp: int = 20
) -> CreatureState:
    return make_creature(
        creature_id="character_001",
        definition_id="fighter",
        strength=16,
        conditions=conditions,
        current_hp=current_hp,
    )


def make_target() -> CreatureState:
    return make_creature(
        creature_id="monster_001",
        definition_id="goblin",
        dexterity=30,
        current_hp=7,
        max_hp=7,
    )


def make_character(
    *, character_id: str = "character_001", total_level: int = 5
) -> CharacterState:
    return CharacterState(
        id=character_id,
        total_level=total_level,
        saving_throw_proficiencies=frozenset(),
        skill_proficiencies=frozenset(),
        weapon_proficiencies=frozenset(),
    )


def make_monster_definition(
    *,
    armor_class: int = 15,
    attacks: tuple[MonsterAttackDefinition, ...] = (),
) -> MonsterDefinition:
    return MonsterDefinition(
        id="goblin",
        version=1,
        name="Goblin",
        ability_scores=AbilityScores(
            strength=8,
            dexterity=14,
            constitution=10,
            intelligence=10,
            wisdom=8,
            charisma=8,
        ),
        armor_class=armor_class,
        attacks=attacks,
    )


def make_scimitar_attack(
    *,
    action_id: str = "scimitar",
    damage_modifier: int = 2,
) -> MonsterAttackDefinition:
    return MonsterAttackDefinition(
        action_id=action_id,
        name="Scimitar",
        attack_bonus=4,
        damage_dice="1d6",
        damage_modifier=damage_modifier,
        damage_type=DamageType.SLASHING,
    )


def make_snapshot(
    *,
    creatures: tuple[CreatureState, ...] = (),
    characters: tuple[CharacterState, ...] = (),
    combat: CombatState | None = None,
) -> StateSnapshot:
    return StateSnapshot(
        campaign=CampaignState(
            id="campaign_001",
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
        ),
        creatures=creatures,
        characters=characters,
        combat=combat,
    )


def make_command() -> AttackCommand:
    return AttackCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=AttackPayload(target_id="monster_001"),
    )


def make_dependencies(
    snapshot: StateSnapshot,
    *,
    raw_roll: int = 9,
    additional_rolls: tuple[int, ...] = (),
    monster_armor_class: int = 15,
    monster_attacks: tuple[MonsterAttackDefinition, ...] = (),
    definition_error: Exception | None = None,
    dice_fail: bool = False,
    metadata_fail: bool = False,
) -> tuple[
    SpyStateStore,
    SpyDefinitionSource,
    ScriptedDiceEngine,
    FixedEventMetadataProvider,
    list[str],
]:
    calls: list[str] = []
    return (
        SpyStateStore(snapshot, calls),
        SpyDefinitionSource(
            make_monster_definition(
                armor_class=monster_armor_class, attacks=monster_attacks
            ),
            calls,
            error=definition_error,
        ),
        ScriptedDiceEngine(
            raw_roll,
            calls,
            additional_rolls=additional_rolls,
            fail=dice_fail,
        ),
        FixedEventMetadataProvider(calls, fail=metadata_fail),
        calls,
    )


def handle_with(
    store: SpyStateStore,
    definitions: SpyDefinitionSource,
    dice: ScriptedDiceEngine,
    metadata: FixedEventMetadataProvider,
):
    return AttackHandler(
        state_store=store,
        definition_source=definitions,
        dice=dice,
        event_metadata_provider=metadata,
    ).handle(make_command())


def test_ordinary_hit_uses_exact_lookup_order_and_returns_consistent_event() -> None:
    actor = make_actor()
    character = make_character()
    target = make_target()
    snapshot = make_snapshot(
        creatures=(
            make_creature(creature_id="character_002", definition_id="wizard"),
            target,
            actor,
        ),
        characters=(
            make_character(character_id="character_002", total_level=1),
            character,
        ),
    )
    before = deepcopy(snapshot)
    store, definitions, dice, metadata, calls = make_dependencies(snapshot)

    result = handle_with(store, definitions, dice, metadata)

    assert calls == ["load", "definition", "dice", "metadata"]
    assert store.load_calls == ["campaign_001"]
    assert definitions.get_calls == [
        {
            "ruleset_id": "dnd_5e",
            "ruleset_version": "5.1",
            "definition_id": "goblin",
            "expected_type": MonsterDefinition,
        }
    ]
    assert dice.roll_calls == ["1d20"]
    assert metadata.next_calls == ["campaign_001"]
    assert store.save_calls == []
    assert store.snapshot == before

    assert result.success is True
    assert result.command_id == "command_000001"
    assert result.errors == ()
    assert result.outcome is not None
    outcome = result.outcome
    assert outcome.target_id == "monster_001"
    assert outcome.roll.mode is RollMode.NORMAL
    assert outcome.roll.rolls == (9,)
    assert outcome.ability_modifier == 3
    assert outcome.proficiency_bonus == 3
    assert outcome.total == 15
    assert outcome.target_armor_class == 15
    assert target.ability_scores.dexterity == 30
    assert outcome.target_armor_class != 10 + 10
    assert outcome.hit is True
    assert outcome.critical_hit is False

    assert len(result.events) == 1
    event = result.events[0]
    assert event.event_id == "event_000123"
    assert event.command_id == result.command_id
    assert event.type == "AttackResolved"
    assert event.version == 1
    assert event.campaign_id == "campaign_001"
    assert event.timestamp == FIXED_TIMESTAMP
    assert event.actor_id == "character_001"
    assert event.caused_by is None
    assert event.payload == {
        "targetId": outcome.target_id,
        "roll": {
            "mode": outcome.roll.mode.value,
            "rolls": outcome.roll.rolls,
            "selected": outcome.roll.selected,
        },
        "ability": outcome.ability.value,
        "abilityModifier": outcome.ability_modifier,
        "proficiencyBonus": outcome.proficiency_bonus,
        "total": outcome.total,
        "targetArmorClass": outcome.target_armor_class,
        "hit": outcome.hit,
        "criticalHit": outcome.critical_hit,
    }


def test_poisoned_attacker_rolls_attack_with_disadvantage() -> None:
    snapshot = make_snapshot(
        creatures=(
            make_actor(conditions=frozenset({Condition.POISONED})),
            make_target(),
        ),
        characters=(make_character(),),
    )
    store, definitions, dice, metadata, calls = make_dependencies(
        snapshot,
        raw_roll=17,
        additional_rolls=(6,),
    )

    result = handle_with(store, definitions, dice, metadata)

    assert calls == ["load", "definition", "dice", "dice", "metadata"]
    assert dice.roll_calls == ["1d20", "1d20"]
    assert result.outcome is not None
    assert result.outcome.roll.mode is RollMode.DISADVANTAGE
    assert result.outcome.roll.rolls == (17, 6)
    assert result.outcome.roll.selected == 6
    assert result.events[0].payload["roll"] == {
        "mode": "disadvantage",
        "rolls": (17, 6),
        "selected": 6,
    }
    assert store.save_calls == []


def test_poisoned_target_does_not_disadvantage_unpoisoned_attacker() -> None:
    poisoned_target = make_creature(
        creature_id="monster_001",
        definition_id="goblin",
        dexterity=30,
        current_hp=7,
        max_hp=7,
        conditions=frozenset({Condition.POISONED}),
    )
    snapshot = make_snapshot(
        creatures=(make_actor(), poisoned_target),
        characters=(make_character(),),
    )
    store, definitions, dice, metadata, calls = make_dependencies(
        snapshot,
        raw_roll=17,
    )

    result = handle_with(store, definitions, dice, metadata)

    assert calls == ["load", "definition", "dice", "metadata"]
    assert dice.roll_calls == ["1d20"]
    assert result.outcome is not None
    assert result.outcome.roll.mode is RollMode.NORMAL
    assert result.outcome.roll.rolls == (17,)
    assert result.outcome.roll.selected == 17


def test_non_default_monster_definition_armor_class_reaches_outcome_and_event() -> None:
    snapshot = make_snapshot(
        creatures=(make_actor(), make_target()),
        characters=(make_character(),),
    )
    store, definitions, dice, metadata, calls = make_dependencies(
        snapshot,
        raw_roll=11,
        monster_armor_class=17,
    )

    result = handle_with(store, definitions, dice, metadata)

    assert result.outcome is not None
    assert result.outcome.total == 17
    assert result.outcome.target_armor_class == 17
    assert result.outcome.hit is True
    assert result.events[0].payload["targetArmorClass"] == 17
    assert calls == ["load", "definition", "dice", "metadata"]
    assert store.save_calls == []


@pytest.mark.parametrize(
    ("raw_roll", "expected_hit", "expected_critical"),
    [
        (8, False, False),
        (1, False, False),
        (20, True, True),
    ],
)
def test_gameplay_miss_natural_one_and_critical_are_successful_processing(
    raw_roll: int,
    expected_hit: bool,
    expected_critical: bool,
) -> None:
    snapshot = make_snapshot(
        creatures=(make_actor(), make_target()),
        characters=(make_character(),),
    )
    store, definitions, dice, metadata, calls = make_dependencies(
        snapshot, raw_roll=raw_roll
    )

    result = handle_with(store, definitions, dice, metadata)

    assert result.success is True
    assert result.outcome is not None
    assert result.outcome.hit is expected_hit
    assert result.outcome.critical_hit is expected_critical
    assert result.events[0].payload["hit"] is expected_hit
    assert result.events[0].payload["criticalHit"] is expected_critical
    assert result.errors == ()
    assert calls == ["load", "definition", "dice", "metadata"]
    assert store.save_calls == []


def test_missing_actor_stops_before_target_definition_resolution() -> None:
    snapshot = make_snapshot(
        creatures=(
            make_target(),
            make_creature(creature_id="character_002", definition_id="wizard"),
        ),
        characters=(make_character(character_id="character_002"),),
    )
    store, definitions, dice, metadata, calls = make_dependencies(snapshot)

    result = handle_with(store, definitions, dice, metadata)

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.ENTITY_NOT_FOUND
    assert result.errors[0].entity_id == "character_001"
    assert result.errors[0].field is None
    assert calls == ["load"]
    assert definitions.get_calls == []
    assert dice.roll_calls == []
    assert metadata.next_calls == []
    assert store.save_calls == []


def test_missing_character_routes_actor_to_monster_attack_path() -> None:
    # An actor with no matching CharacterState is no longer an unconditional
    # error: it is routed to the Monster-actor path (G8). With zero
    # supported attacks on the actor's MonsterDefinition, that path itself
    # reports ACTION_NOT_AVAILABLE rather than reaching AttackResolved.
    snapshot = make_snapshot(creatures=(make_actor(), make_target()))
    store, definitions, dice, metadata, calls = make_dependencies(snapshot)

    result = handle_with(store, definitions, dice, metadata)

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.ACTION_NOT_AVAILABLE
    assert result.errors[0].entity_id == "character_001"
    assert result.errors[0].field == "attacks"
    assert calls == ["load", "definition"]
    assert definitions.get_calls == [
        {
            "ruleset_id": "dnd_5e",
            "ruleset_version": "5.1",
            "definition_id": "fighter",
            "expected_type": MonsterDefinition,
        }
    ]
    assert dice.roll_calls == []
    assert metadata.next_calls == []
    assert store.save_calls == []


def test_missing_target_stops_before_definition_resolution() -> None:
    snapshot = make_snapshot(
        creatures=(make_actor(),),
        characters=(make_character(),),
    )
    store, definitions, dice, metadata, calls = make_dependencies(snapshot)

    result = handle_with(store, definitions, dice, metadata)

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.ENTITY_NOT_FOUND
    assert result.errors[0].entity_id == "monster_001"
    assert result.errors[0].field == "target_id"
    assert calls == ["load"]
    assert definitions.get_calls == []
    assert dice.roll_calls == []
    assert metadata.next_calls == []
    assert store.save_calls == []


@pytest.mark.parametrize(
    ("definition_error", "expected_code", "expected_entity_id"),
    [
        (
            DefinitionNotFoundError("missing definition"),
            ErrorCode.DEFINITION_NOT_FOUND,
            "goblin",
        ),
        (
            DefinitionTypeMismatchError("wrong definition type"),
            ErrorCode.INVALID_STATE,
            "monster_001",
        ),
    ],
)
def test_semantic_definition_failures_map_without_resolution_side_effects(
    definition_error: Exception,
    expected_code: ErrorCode,
    expected_entity_id: str,
) -> None:
    snapshot = make_snapshot(
        creatures=(make_actor(), make_target()),
        characters=(make_character(),),
    )
    store, definitions, dice, metadata, calls = make_dependencies(
        snapshot, definition_error=definition_error
    )

    result = handle_with(store, definitions, dice, metadata)

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is expected_code
    assert result.errors[0].entity_id == expected_entity_id
    assert result.errors[0].field == "definition_id"
    assert calls == ["load", "definition"]
    assert dice.roll_calls == []
    assert metadata.next_calls == []
    assert store.save_calls == []


def test_malformed_definition_adapter_failure_propagates() -> None:
    snapshot = make_snapshot(
        creatures=(make_actor(), make_target()),
        characters=(make_character(),),
    )
    store, definitions, dice, metadata, calls = make_dependencies(
        snapshot,
        definition_error=InvalidPackagedDefinitionError(
            "corrupt definition payload"
        ),
    )

    with pytest.raises(InvalidPackagedDefinitionError, match="corrupt"):
        handle_with(store, definitions, dice, metadata)

    assert calls == ["load", "definition"]
    assert dice.roll_calls == []
    assert metadata.next_calls == []
    assert store.save_calls == []


def test_state_store_failure_propagates_before_all_other_dependencies() -> None:
    snapshot = make_snapshot(
        creatures=(make_actor(), make_target()),
        characters=(make_character(),),
    )
    store, definitions, dice, metadata, calls = make_dependencies(snapshot)
    failing_store = FailingStateStore(snapshot, calls)

    with pytest.raises(StateStoreError, match="backend unavailable"):
        handle_with(failing_store, definitions, dice, metadata)

    assert calls == ["load"]
    assert failing_store.load_calls == ["campaign_001"]
    assert definitions.get_calls == []
    assert dice.roll_calls == []
    assert metadata.next_calls == []
    assert failing_store.save_calls == []
    assert store.save_calls == []


def test_dice_failure_propagates_before_metadata_request() -> None:
    snapshot = make_snapshot(
        creatures=(make_actor(), make_target()),
        characters=(make_character(),),
    )
    store, definitions, dice, metadata, calls = make_dependencies(
        snapshot, dice_fail=True
    )

    with pytest.raises(RuntimeError, match="dice unavailable"):
        handle_with(store, definitions, dice, metadata)

    assert calls == ["load", "definition", "dice"]
    assert definitions.get_calls != []
    assert dice.roll_calls == ["1d20"]
    assert metadata.next_calls == []
    assert store.save_calls == []


def test_metadata_failure_propagates_after_resolution_without_save() -> None:
    snapshot = make_snapshot(
        creatures=(make_actor(), make_target()),
        characters=(make_character(),),
    )
    store, definitions, dice, metadata, calls = make_dependencies(
        snapshot, metadata_fail=True
    )

    with pytest.raises(RuntimeError, match="metadata unavailable"):
        handle_with(store, definitions, dice, metadata)

    assert calls == ["load", "definition", "dice", "metadata"]
    assert dice.roll_calls == ["1d20"]
    assert metadata.next_calls == ["campaign_001"]
    assert store.save_calls == []


# --- Monster actor -> Character target path (G8) -----------------------


def make_monster_actor(
    *, conditions: frozenset[Condition] = frozenset(), current_hp: int = 20
) -> CreatureState:
    return make_creature(
        creature_id="monster_001",
        definition_id="goblin",
        conditions=conditions,
        current_hp=current_hp,
    )


def make_character_target(
    *,
    dexterity: int = 14,
    current_hp: int = 11,
    max_hp: int = 11,
) -> CreatureState:
    return make_creature(
        creature_id="character_001",
        definition_id="fighter",
        dexterity=dexterity,
        current_hp=current_hp,
        max_hp=max_hp,
    )


def make_monster_attack_command() -> AttackCommand:
    return AttackCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="monster_001",
        payload=AttackPayload(target_id="character_001"),
    )


def handle_monster_attack_with(
    store: SpyStateStore,
    definitions: SpyDefinitionSource,
    dice: ScriptedDiceEngine,
    metadata: FixedEventMetadataProvider,
):
    return AttackHandler(
        state_store=store,
        definition_source=definitions,
        dice=dice,
        event_metadata_provider=metadata,
    ).handle(make_monster_attack_command())


def test_monster_attack_miss_emits_only_attack_event_without_save() -> None:
    target = make_character_target()
    snapshot = make_snapshot(
        creatures=(make_monster_actor(), target),
        characters=(make_character(),),
    )
    calls: list[str] = []
    store = SpyStateStore(snapshot, calls)
    definitions = SpyDefinitionSource(
        make_monster_definition(attacks=(make_scimitar_attack(),)), calls
    )
    dice = ScriptedDiceEngine(1, calls)
    metadata = FixedEventMetadataProvider(calls)

    result = handle_monster_attack_with(store, definitions, dice, metadata)

    assert calls == ["load", "definition", "dice", "metadata"]
    assert dice.roll_calls == ["1d20"]
    assert metadata.next_calls == ["campaign_001"]
    assert store.save_calls == []
    assert target.current_hp == 11
    assert result.success is True
    assert result.outcome is not None
    assert result.outcome.hit is False
    assert len(result.events) == 1
    assert result.events[0].type == "MonsterAttackResolved"
    assert result.events[0].caused_by is None


def test_monster_attack_hit_resolves_damage_and_persists_hp_mutation() -> None:
    # dexterity 14 -> modifier +2 -> unarmored Character AC 12 (no
    # Equipment/persisted AC source is consulted).
    actor = make_monster_actor()
    target = make_character_target(dexterity=14)
    snapshot = make_snapshot(
        creatures=(actor, target),
        characters=(make_character(),),
    )
    loaded_before = deepcopy(snapshot)
    calls: list[str] = []
    store = SpyStateStore(snapshot, calls)
    definitions = SpyDefinitionSource(
        make_monster_definition(attacks=(make_scimitar_attack(),)), calls
    )
    dice = ScriptedDiceEngine(10, calls, additional_rolls=(4,))
    metadata = FixedEventMetadataProvider(calls)

    result = handle_monster_attack_with(store, definitions, dice, metadata)

    assert calls == [
        "load",
        "definition",
        "dice",
        "dice",
        "metadata",
        "metadata",
        "metadata",
        "save",
    ]
    assert definitions.get_calls == [
        {
            "ruleset_id": "dnd_5e",
            "ruleset_version": "5.1",
            "definition_id": "goblin",
            "expected_type": MonsterDefinition,
        }
    ]
    assert dice.roll_calls == ["1d20", "1d6"]
    assert metadata.next_calls == ["campaign_001"] * 3
    assert snapshot == loaded_before
    assert target.current_hp == 11
    assert len(store.save_calls) == 1
    saved_snapshot = store.save_calls[0]
    saved_target = next(
        creature
        for creature in saved_snapshot.creatures
        if creature.id == "character_001"
    )
    assert saved_target.current_hp == 5
    assert saved_target is not target
    assert saved_snapshot.creatures[0] is actor

    assert result.success is True
    assert result.errors == ()
    outcome = result.outcome
    assert outcome is not None
    assert outcome.target_id == "character_001"
    assert outcome.action_id == "scimitar"
    assert outcome.roll.mode is RollMode.NORMAL
    assert outcome.roll.selected == 10
    assert outcome.attack_bonus == 4
    assert outcome.total == 14
    assert outcome.target_armor_class == 12
    assert outcome.hit is True
    assert outcome.critical_hit is False

    assert len(result.events) == 3
    attack_event, damage_event, applied_event = result.events
    assert [event.type for event in result.events] == [
        "MonsterAttackResolved",
        "MonsterAttackDamageResolved",
        "DamageApplied",
    ]
    assert [event.event_id for event in result.events] == [
        "event_000123",
        "event_000124",
        "event_000125",
    ]
    assert attack_event.caused_by is None
    assert damage_event.caused_by == attack_event.event_id
    assert applied_event.caused_by == damage_event.event_id
    assert all(event.command_id == "command_000001" for event in result.events)
    assert all(event.campaign_id == "campaign_001" for event in result.events)
    assert all(event.actor_id == "monster_001" for event in result.events)
    assert attack_event.payload == {
        "targetId": "character_001",
        "actionId": "scimitar",
        "roll": {"mode": "normal", "rolls": (10,), "selected": 10},
        "attackBonus": 4,
        "total": 14,
        "targetArmorClass": 12,
        "hit": True,
        "criticalHit": False,
    }
    assert damage_event.payload == {
        "targetId": "character_001",
        "actionId": "scimitar",
        "roll": {"expression": "1d6", "rolls": (4,), "total": 4},
        "damageModifier": 2,
        "damageType": "slashing",
        "criticalHit": False,
        "amount": 6,
    }
    assert applied_event.payload == {
        "targetId": "character_001",
        "amount": 6,
        "previousHp": 11,
        "newHp": 5,
    }


def test_monster_attack_critical_doubles_dice_count_and_applies_modifier_once() -> None:
    target = make_character_target()
    snapshot = make_snapshot(
        creatures=(make_monster_actor(), target),
        characters=(make_character(),),
    )
    calls: list[str] = []
    store = SpyStateStore(snapshot, calls)
    definitions = SpyDefinitionSource(
        make_monster_definition(attacks=(make_scimitar_attack(),)), calls
    )
    dice = ScriptedDiceEngine(20, calls, additional_rolls=((3, 4),))
    metadata = FixedEventMetadataProvider(calls)

    result = handle_monster_attack_with(store, definitions, dice, metadata)

    assert dice.roll_calls == ["1d20", "2d6"]
    assert len(result.events) == 3
    assert result.events[1].payload["roll"] == {
        "expression": "2d6",
        "rolls": (3, 4),
        "total": 7,
    }
    assert result.events[1].payload["damageModifier"] == 2
    assert result.events[1].payload["amount"] == 9
    assert result.events[2].payload["newHp"] == 2
    assert len(store.save_calls) == 1


def test_monster_attack_lethal_damage_floors_hp_at_zero() -> None:
    target = make_character_target(current_hp=5, max_hp=11)
    snapshot = make_snapshot(
        creatures=(make_monster_actor(), target),
        characters=(make_character(),),
    )
    calls: list[str] = []
    store = SpyStateStore(snapshot, calls)
    definitions = SpyDefinitionSource(
        make_monster_definition(attacks=(make_scimitar_attack(),)), calls
    )
    dice = ScriptedDiceEngine(10, calls, additional_rolls=(6,))
    metadata = FixedEventMetadataProvider(calls)

    result = handle_monster_attack_with(store, definitions, dice, metadata)

    assert len(result.events) == 3
    assert result.events[2].payload == {
        "targetId": "character_001",
        "amount": 8,
        "previousHp": 5,
        "newHp": 0,
    }
    saved_target = next(
        creature
        for creature in store.save_calls[0].creatures
        if creature.id == target.id
    )
    assert saved_target.current_hp == 0
    assert len(store.save_calls) == 1


def test_monster_attack_zero_source_damage_emits_two_events_without_save() -> None:
    target = make_character_target()
    snapshot = make_snapshot(
        creatures=(make_monster_actor(), target),
        characters=(make_character(),),
    )
    calls: list[str] = []
    store = SpyStateStore(snapshot, calls)
    definitions = SpyDefinitionSource(
        make_monster_definition(
            attacks=(make_scimitar_attack(damage_modifier=-2),)
        ),
        calls,
    )
    dice = ScriptedDiceEngine(10, calls, additional_rolls=(1,))
    metadata = FixedEventMetadataProvider(calls)

    result = handle_monster_attack_with(store, definitions, dice, metadata)

    assert result.success is True
    assert result.outcome is not None and result.outcome.hit is True
    assert dice.roll_calls == ["1d20", "1d6"]
    assert metadata.next_calls == ["campaign_001"] * 2
    assert [event.type for event in result.events] == [
        "MonsterAttackResolved",
        "MonsterAttackDamageResolved",
    ]
    assert result.events[1].caused_by == result.events[0].event_id
    assert result.events[1].payload["amount"] == 0
    assert store.save_calls == []
    assert target.current_hp == 11


def test_monster_attack_positive_damage_at_zero_hp_still_applies_and_saves() -> None:
    target = make_character_target(current_hp=0, max_hp=11)
    snapshot = make_snapshot(
        creatures=(make_monster_actor(), target),
        characters=(make_character(),),
    )
    calls: list[str] = []
    store = SpyStateStore(snapshot, calls)
    definitions = SpyDefinitionSource(
        make_monster_definition(attacks=(make_scimitar_attack(),)), calls
    )
    dice = ScriptedDiceEngine(10, calls, additional_rolls=(4,))
    metadata = FixedEventMetadataProvider(calls)

    result = handle_monster_attack_with(store, definitions, dice, metadata)

    assert len(result.events) == 3
    assert result.events[2].payload["previousHp"] == 0
    assert result.events[2].payload["newHp"] == 0
    assert len(store.save_calls) == 1


def test_monster_attack_damage_preserves_existing_combat_state() -> None:
    actor = make_monster_actor()
    target = make_character_target()
    combat = CombatState(
        id="combat_001",
        round=2,
        order=(actor.id, target.id),
        active_index=0,
    )
    snapshot = make_snapshot(
        creatures=(actor, target),
        characters=(make_character(),),
        combat=combat,
    )
    calls: list[str] = []
    store = SpyStateStore(snapshot, calls)
    definitions = SpyDefinitionSource(
        make_monster_definition(attacks=(make_scimitar_attack(),)), calls
    )
    dice = ScriptedDiceEngine(10, calls, additional_rolls=(4,))
    metadata = FixedEventMetadataProvider(calls)

    result = handle_monster_attack_with(store, definitions, dice, metadata)

    assert result.success is True
    assert len(store.save_calls) == 1
    assert store.save_calls[0].combat is combat
    assert snapshot.combat is combat
    saved_target = next(
        creature
        for creature in store.save_calls[0].creatures
        if creature.id == target.id
    )
    assert saved_target.current_hp == 5
    assert target.current_hp == 11


def test_monster_attack_save_failure_propagates_and_keeps_loaded_state() -> None:
    actor = make_monster_actor()
    target = make_character_target()
    snapshot = make_snapshot(
        creatures=(actor, target),
        characters=(make_character(),),
    )
    loaded_before = deepcopy(snapshot)
    calls: list[str] = []
    store = SaveFailingStateStore(snapshot, calls)
    definitions = SpyDefinitionSource(
        make_monster_definition(attacks=(make_scimitar_attack(),)), calls
    )
    dice = ScriptedDiceEngine(10, calls, additional_rolls=(4,))
    metadata = FixedEventMetadataProvider(calls)

    with pytest.raises(StateStoreError, match="backend unavailable"):
        handle_monster_attack_with(store, definitions, dice, metadata)

    assert calls.count("save") == 1
    assert len(store.save_calls) == 1
    assert store.snapshot == loaded_before
    assert target.current_hp == 11


def test_monster_attack_poisoned_actor_rolls_with_disadvantage() -> None:
    snapshot = make_snapshot(
        creatures=(
            make_monster_actor(conditions=frozenset({Condition.POISONED})),
            make_character_target(),
        ),
        characters=(make_character(),),
    )
    calls: list[str] = []
    store = SpyStateStore(snapshot, calls)
    definitions = SpyDefinitionSource(
        make_monster_definition(attacks=(make_scimitar_attack(),)), calls
    )
    dice = ScriptedDiceEngine(17, calls, additional_rolls=(6,))
    metadata = FixedEventMetadataProvider(calls)

    result = handle_monster_attack_with(store, definitions, dice, metadata)

    assert calls == ["load", "definition", "dice", "dice", "metadata"]
    assert dice.roll_calls == ["1d20", "1d20"]
    outcome = result.outcome
    assert outcome is not None
    assert outcome.roll.mode is RollMode.DISADVANTAGE
    assert outcome.roll.rolls == (17, 6)
    assert outcome.roll.selected == 6
    assert result.events[0].payload["roll"] == {
        "mode": "disadvantage",
        "rolls": (17, 6),
        "selected": 6,
    }


@pytest.mark.parametrize(
    ("raw_roll", "expected_hit", "expected_critical"),
    [
        (1, False, False),
        (20, True, True),
    ],
)
def test_monster_attack_natural_one_and_twenty_are_automatic(
    raw_roll: int,
    expected_hit: bool,
    expected_critical: bool,
) -> None:
    snapshot = make_snapshot(
        creatures=(make_monster_actor(), make_character_target(dexterity=30)),
        characters=(make_character(),),
    )
    calls: list[str] = []
    store = SpyStateStore(snapshot, calls)
    definitions = SpyDefinitionSource(
        make_monster_definition(attacks=(make_scimitar_attack(),)), calls
    )
    damage_rolls: tuple[int | tuple[int, ...], ...] = (
        ((3, 4),) if expected_hit else ()
    )
    dice = ScriptedDiceEngine(
        raw_roll,
        calls,
        additional_rolls=damage_rolls,
    )
    metadata = FixedEventMetadataProvider(calls)

    result = handle_monster_attack_with(store, definitions, dice, metadata)

    assert result.success is True
    outcome = result.outcome
    assert outcome is not None
    assert outcome.hit is expected_hit
    assert outcome.critical_hit is expected_critical
    assert result.events[0].payload["hit"] is expected_hit
    assert result.events[0].payload["criticalHit"] is expected_critical
    assert dice.roll_calls == (["1d20", "2d6"] if expected_hit else ["1d20"])


@pytest.mark.parametrize(
    ("definition_error", "expected_code", "expected_entity_id"),
    [
        (
            DefinitionNotFoundError("missing definition"),
            ErrorCode.DEFINITION_NOT_FOUND,
            "goblin",
        ),
        (
            DefinitionTypeMismatchError("wrong definition type"),
            ErrorCode.INVALID_STATE,
            "monster_001",
        ),
    ],
)
def test_monster_attack_actor_definition_failures_stop_before_rolling(
    definition_error: Exception,
    expected_code: ErrorCode,
    expected_entity_id: str,
) -> None:
    snapshot = make_snapshot(
        creatures=(make_monster_actor(), make_character_target()),
        characters=(make_character(),),
    )
    calls: list[str] = []
    store = SpyStateStore(snapshot, calls)
    definitions = SpyDefinitionSource(
        make_monster_definition(attacks=(make_scimitar_attack(),)),
        calls,
        error=definition_error,
    )
    dice = ScriptedDiceEngine(10, calls)
    metadata = FixedEventMetadataProvider(calls)

    result = handle_monster_attack_with(store, definitions, dice, metadata)

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is expected_code
    assert result.errors[0].entity_id == expected_entity_id
    assert result.errors[0].field == "definition_id"
    assert calls == ["load", "definition"]
    assert dice.roll_calls == []
    assert metadata.next_calls == []
    assert store.save_calls == []


@pytest.mark.parametrize(
    "attacks",
    [
        (),
        (make_scimitar_attack(action_id="scimitar"), make_scimitar_attack(action_id="bite")),
    ],
)
def test_monster_attack_requires_exactly_one_supported_attack(
    attacks: tuple[MonsterAttackDefinition, ...],
) -> None:
    # Neither zero nor multiple supported attacks is a Definition-shape
    # error: the Definition itself stays valid, but this narrow Command
    # cannot select among them, so no dice are rolled and no Event is built.
    snapshot = make_snapshot(creatures=(make_monster_actor(),))
    calls: list[str] = []
    store = SpyStateStore(snapshot, calls)
    definitions = SpyDefinitionSource(make_monster_definition(attacks=attacks), calls)
    dice = ScriptedDiceEngine(10, calls)
    metadata = FixedEventMetadataProvider(calls)

    result = handle_monster_attack_with(store, definitions, dice, metadata)

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.ACTION_NOT_AVAILABLE
    assert result.errors[0].entity_id == "monster_001"
    assert result.errors[0].field == "attacks"
    assert calls == ["load", "definition"]
    assert dice.roll_calls == []
    assert metadata.next_calls == []
    assert store.save_calls == []


def test_monster_attack_missing_target_creature() -> None:
    snapshot = make_snapshot(creatures=(make_monster_actor(),))
    calls: list[str] = []
    store = SpyStateStore(snapshot, calls)
    definitions = SpyDefinitionSource(
        make_monster_definition(attacks=(make_scimitar_attack(),)), calls
    )
    dice = ScriptedDiceEngine(10, calls)
    metadata = FixedEventMetadataProvider(calls)

    result = handle_monster_attack_with(store, definitions, dice, metadata)

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.ENTITY_NOT_FOUND
    assert result.errors[0].entity_id == "character_001"
    assert result.errors[0].field == "target_id"
    assert calls == ["load", "definition"]
    assert dice.roll_calls == []
    assert metadata.next_calls == []
    assert store.save_calls == []


def test_monster_attack_target_without_character_state_is_invalid_target() -> None:
    snapshot = make_snapshot(
        creatures=(make_monster_actor(), make_character_target()),
    )
    calls: list[str] = []
    store = SpyStateStore(snapshot, calls)
    definitions = SpyDefinitionSource(
        make_monster_definition(attacks=(make_scimitar_attack(),)), calls
    )
    dice = ScriptedDiceEngine(10, calls)
    metadata = FixedEventMetadataProvider(calls)

    result = handle_monster_attack_with(store, definitions, dice, metadata)

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.INVALID_TARGET
    assert result.errors[0].entity_id == "character_001"
    assert result.errors[0].field == "target_id"
    assert calls == ["load", "definition"]
    assert dice.roll_calls == []
    assert metadata.next_calls == []
    assert store.save_calls == []


# --- Active-turn eligibility gating (§3.28, TSK-0006) -------------------


def test_missing_actor_is_rejected_before_active_turn_gate_when_combat_exists() -> None:
    # Combat is active for an existing participant that is not the command's
    # actor, and the actor itself has no CreatureState at all. Missing-actor
    # precedence must still win over Combat eligibility.
    target = make_target()
    combat = CombatState(
        id="combat_001",
        round=1,
        order=(target.id,),
        active_index=0,
    )
    snapshot = make_snapshot(creatures=(target,), combat=combat)
    store, definitions, dice, metadata, calls = make_dependencies(snapshot)

    result = handle_with(store, definitions, dice, metadata)

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.ENTITY_NOT_FOUND
    assert result.errors[0].entity_id == "character_001"
    assert result.errors[0].field is None
    assert calls == ["load"]
    assert definitions.get_calls == []
    assert dice.roll_calls == []
    assert metadata.next_calls == []
    assert store.save_calls == []


def test_active_character_inside_combat_reaches_existing_attack_path() -> None:
    actor = make_actor()
    target = make_target()
    combat = CombatState(
        id="combat_001",
        round=1,
        order=(actor.id, target.id),
        active_index=0,
    )
    snapshot = make_snapshot(
        creatures=(actor, target),
        characters=(make_character(),),
        combat=combat,
    )
    store, definitions, dice, metadata, calls = make_dependencies(snapshot)

    result = handle_with(store, definitions, dice, metadata)

    assert calls == ["load", "definition", "dice", "metadata"]
    assert store.save_calls == []
    assert result.success is True
    assert result.outcome is not None
    assert result.outcome.target_id == "monster_001"
    assert len(result.events) == 1
    assert result.events[0].type == "AttackResolved"


def test_inactive_character_inside_combat_is_rejected_before_routing() -> None:
    actor = make_actor()
    target = make_target()
    combat = CombatState(
        id="combat_001",
        round=1,
        order=(target.id, actor.id),
        active_index=0,
    )
    snapshot = make_snapshot(
        creatures=(actor, target),
        characters=(make_character(),),
        combat=combat,
    )
    store, definitions, dice, metadata, calls = make_dependencies(snapshot)

    result = handle_with(store, definitions, dice, metadata)

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.ACTION_NOT_AVAILABLE
    assert result.errors[0].entity_id == "character_001"
    assert result.errors[0].field is None
    assert calls == ["load"]
    assert definitions.get_calls == []
    assert dice.roll_calls == []
    assert metadata.next_calls == []
    assert store.save_calls == []


def test_actor_absent_from_combat_order_is_rejected_same_as_inactive() -> None:
    # A valid StateSnapshot where the actor exists but was never part of
    # combat.order. §3.28 uses one equality against active_creature_id, so
    # this must produce the exact same rejection as an inactive-but-present
    # actor, with no separate membership-specific error.
    actor = make_actor()
    target = make_target()
    combat = CombatState(
        id="combat_001",
        round=1,
        order=(target.id,),
        active_index=0,
    )
    snapshot = make_snapshot(
        creatures=(actor, target),
        characters=(make_character(),),
        combat=combat,
    )
    store, definitions, dice, metadata, calls = make_dependencies(snapshot)

    result = handle_with(store, definitions, dice, metadata)

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.ACTION_NOT_AVAILABLE
    assert result.errors[0].entity_id == "character_001"
    assert result.errors[0].field is None
    assert calls == ["load"]
    assert definitions.get_calls == []
    assert dice.roll_calls == []
    assert metadata.next_calls == []
    assert store.save_calls == []


# --- Zero-HP Attack eligibility gating (§3.31, TSK-0007) ----------------


def test_character_zero_hp_outside_combat_is_rejected_before_target_processing() -> None:
    actor = make_actor(current_hp=0)
    target = make_target()
    snapshot = make_snapshot(
        creatures=(actor, target),
        characters=(make_character(),),
    )
    store, definitions, dice, metadata, calls = make_dependencies(snapshot)

    result = handle_with(store, definitions, dice, metadata)

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.ACTION_NOT_AVAILABLE
    assert result.errors[0].entity_id == "character_001"
    assert result.errors[0].field is None
    assert calls == ["load"]
    assert definitions.get_calls == []
    assert dice.roll_calls == []
    assert metadata.next_calls == []
    assert store.save_calls == []


def test_character_zero_hp_precedes_missing_target_lookup() -> None:
    # A missing target would normally fail with ENTITY_NOT_FOUND(target_id).
    # Once Character category is established, zero-HP eligibility must be
    # evaluated first, so the observed failure is the zero-HP rejection, not
    # the target-lookup error a bypassed gate would produce.
    actor = make_actor(current_hp=0)
    snapshot = make_snapshot(
        creatures=(actor,),
        characters=(make_character(),),
    )
    store, definitions, dice, metadata, calls = make_dependencies(snapshot)

    result = handle_with(store, definitions, dice, metadata)

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.ACTION_NOT_AVAILABLE
    assert result.errors[0].entity_id == "character_001"
    assert result.errors[0].field is None
    assert calls == ["load"]
    assert definitions.get_calls == []
    assert dice.roll_calls == []
    assert metadata.next_calls == []
    assert store.save_calls == []


def test_active_turn_gate_precedes_zero_hp_for_inactive_monster_actor() -> None:
    # DefinitionSource is configured to raise if ever reached, so if §3.28
    # did not return before Monster category establishment, this test would
    # fail loudly via a propagated exception rather than silently passing.
    actor = make_monster_actor(current_hp=0)
    target = make_character_target()
    combat = CombatState(
        id="combat_001",
        round=1,
        order=(target.id, actor.id),
        active_index=0,
    )
    snapshot = make_snapshot(
        creatures=(actor, target),
        characters=(make_character(),),
        combat=combat,
    )
    calls: list[str] = []
    store = SpyStateStore(snapshot, calls)
    definitions = SpyDefinitionSource(
        make_monster_definition(attacks=(make_scimitar_attack(),)),
        calls,
        error=DefinitionNotFoundError("must not be reached"),
    )
    dice = ScriptedDiceEngine(10, calls)
    metadata = FixedEventMetadataProvider(calls)

    result = handle_monster_attack_with(store, definitions, dice, metadata)

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.ACTION_NOT_AVAILABLE
    assert result.errors[0].entity_id == "monster_001"
    assert result.errors[0].field is None
    assert calls == ["load"]
    assert definitions.get_calls == []
    assert dice.roll_calls == []
    assert metadata.next_calls == []
    assert store.save_calls == []


@pytest.mark.parametrize(
    ("definition_error", "expected_code", "expected_entity_id"),
    [
        (
            DefinitionNotFoundError("missing definition"),
            ErrorCode.DEFINITION_NOT_FOUND,
            "goblin",
        ),
        (
            DefinitionTypeMismatchError("wrong definition type"),
            ErrorCode.INVALID_STATE,
            "monster_001",
        ),
    ],
)
def test_monster_actor_definition_failures_take_precedence_over_zero_hp(
    definition_error: Exception,
    expected_code: ErrorCode,
    expected_entity_id: str,
) -> None:
    actor = make_monster_actor(current_hp=0)
    target = make_character_target()
    snapshot = make_snapshot(
        creatures=(actor, target),
        characters=(make_character(),),
    )
    calls: list[str] = []
    store = SpyStateStore(snapshot, calls)
    definitions = SpyDefinitionSource(
        make_monster_definition(attacks=(make_scimitar_attack(),)),
        calls,
        error=definition_error,
    )
    dice = ScriptedDiceEngine(10, calls)
    metadata = FixedEventMetadataProvider(calls)

    result = handle_monster_attack_with(store, definitions, dice, metadata)

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is expected_code
    assert result.errors[0].entity_id == expected_entity_id
    assert result.errors[0].field == "definition_id"
    assert calls == ["load", "definition"]
    assert dice.roll_calls == []
    assert metadata.next_calls == []
    assert store.save_calls == []


def test_monster_zero_hp_takes_precedence_over_attacks_count_validation() -> None:
    actor = make_monster_actor(current_hp=0)
    snapshot = make_snapshot(creatures=(actor,))
    calls: list[str] = []
    store = SpyStateStore(snapshot, calls)
    definitions = SpyDefinitionSource(make_monster_definition(attacks=()), calls)
    dice = ScriptedDiceEngine(10, calls)
    metadata = FixedEventMetadataProvider(calls)

    result = handle_monster_attack_with(store, definitions, dice, metadata)

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.ACTION_NOT_AVAILABLE
    assert result.errors[0].entity_id == "monster_001"
    assert result.errors[0].field is None
    assert calls == ["load", "definition"]
    assert dice.roll_calls == []
    assert metadata.next_calls == []
    assert store.save_calls == []


def test_monster_zero_hp_outside_combat_is_rejected_before_target_processing() -> None:
    actor = make_monster_actor(current_hp=0)
    target = make_character_target()
    snapshot = make_snapshot(
        creatures=(actor, target),
        characters=(make_character(),),
    )
    calls: list[str] = []
    store = SpyStateStore(snapshot, calls)
    definitions = SpyDefinitionSource(
        make_monster_definition(attacks=(make_scimitar_attack(),)), calls
    )
    dice = ScriptedDiceEngine(10, calls)
    metadata = FixedEventMetadataProvider(calls)

    result = handle_monster_attack_with(store, definitions, dice, metadata)

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.ACTION_NOT_AVAILABLE
    assert result.errors[0].entity_id == "monster_001"
    assert result.errors[0].field is None
    assert calls == ["load", "definition"]
    assert dice.roll_calls == []
    assert metadata.next_calls == []
    assert store.save_calls == []


def test_inactive_monster_actor_is_rejected_before_monster_routing() -> None:
    actor = make_monster_actor()
    target = make_character_target()
    combat = CombatState(
        id="combat_001",
        round=1,
        order=(target.id, actor.id),
        active_index=0,
    )
    snapshot = make_snapshot(
        creatures=(actor, target),
        characters=(make_character(),),
        combat=combat,
    )
    calls: list[str] = []
    store = SpyStateStore(snapshot, calls)
    definitions = SpyDefinitionSource(
        make_monster_definition(attacks=(make_scimitar_attack(),)), calls
    )
    dice = ScriptedDiceEngine(10, calls)
    metadata = FixedEventMetadataProvider(calls)

    result = handle_monster_attack_with(store, definitions, dice, metadata)

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.ACTION_NOT_AVAILABLE
    assert result.errors[0].entity_id == "monster_001"
    assert result.errors[0].field is None
    assert calls == ["load"]
    assert definitions.get_calls == []
    assert dice.roll_calls == []
    assert metadata.next_calls == []
    assert store.save_calls == []
