from copy import deepcopy
from datetime import datetime, timezone

import pytest

from dnd_engine.application.handlers.skill_check import SkillCheckHandler
from dnd_engine.application.services.event_metadata import EventMetadata
from dnd_engine.domain.commands.skill_check import (
    SkillCheckCommand,
    SkillCheckPayload,
)
from dnd_engine.domain.errors import ErrorCode
from dnd_engine.domain.services.state_store import StateStoreError
from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.domain.value_objects.condition import Condition
from dnd_engine.domain.value_objects.d20 import RollMode
from dnd_engine.domain.value_objects.dice_roll import DiceRoll
from dnd_engine.domain.value_objects.skill import Skill


FIXED_TIMESTAMP = datetime(2026, 8, 27, 11, 30, tzinfo=timezone.utc)


class SpyStateStore:
    def __init__(self, snapshot: StateSnapshot) -> None:
        self.snapshot = snapshot
        self.load_calls: list[str] = []
        self.save_calls: list[StateSnapshot] = []

    def load(self, campaign_id: str) -> StateSnapshot:
        self.load_calls.append(campaign_id)
        return self.snapshot

    def save(self, snapshot: StateSnapshot) -> None:
        self.save_calls.append(snapshot)


class FailingStateStore(SpyStateStore):
    def load(self, campaign_id: str) -> StateSnapshot:
        self.load_calls.append(campaign_id)
        raise StateStoreError("state backend unavailable")


class ScriptedDiceEngine:
    def __init__(self, raw_roll: int, *additional_rolls: int) -> None:
        self._raw_rolls = iter((raw_roll, *additional_rolls))
        self.calls: list[str] = []

    def roll(self, expression: str) -> DiceRoll:
        self.calls.append(expression)
        raw_roll = next(self._raw_rolls)
        return DiceRoll(
            expression="1d20",
            rolls=(raw_roll,),
            total=raw_roll,
        )


class FailingDiceEngine(ScriptedDiceEngine):
    def roll(self, expression: str) -> DiceRoll:
        self.calls.append(expression)
        raise RuntimeError("dice unavailable")


class FixedEventMetadataProvider:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail
        self.calls: list[str] = []

    def next_metadata(self, campaign_id: str) -> EventMetadata:
        self.calls.append(campaign_id)
        if self._fail:
            raise RuntimeError("metadata unavailable")
        return EventMetadata(
            event_id="event_000123",
            timestamp=FIXED_TIMESTAMP,
        )


def make_creature(
    *,
    creature_id: str = "character_001",
    conditions: frozenset[Condition] = frozenset(),
) -> CreatureState:
    return CreatureState(
        id=creature_id,
        definition_id="fighter",
        ability_scores=AbilityScores(
            strength=16,
            dexterity=12,
            constitution=14,
            intelligence=10,
            wisdom=10,
            charisma=8,
        ),
        current_hp=20,
        max_hp=20,
        conditions=conditions,
    )


def make_character(
    *,
    character_id: str = "character_001",
    proficiencies: frozenset[Skill] = frozenset({Skill.INTIMIDATION}),
) -> CharacterState:
    return CharacterState(
        id=character_id,
        total_level=5,
        saving_throw_proficiencies=frozenset(),
        skill_proficiencies=proficiencies,
        weapon_proficiencies=frozenset(),
    )


def make_snapshot(
    *,
    creatures: tuple[CreatureState, ...] = (),
    characters: tuple[CharacterState, ...] = (),
) -> StateSnapshot:
    return StateSnapshot(
        campaign=CampaignState(
            id="campaign_001",
            ruleset_id="dnd_5e",
            ruleset_version="1.0.0",
        ),
        creatures=creatures,
        characters=characters,
    )


def make_command(
    *,
    skill: Skill = Skill.INTIMIDATION,
    ability: Ability = Ability.STRENGTH,
    dc: int = 15,
) -> SkillCheckCommand:
    return SkillCheckCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=SkillCheckPayload(skill=skill, ability=ability, dc=dc),
    )


def make_handler(
    store: SpyStateStore,
    dice: ScriptedDiceEngine,
    metadata: FixedEventMetadataProvider,
) -> SkillCheckHandler:
    return SkillCheckHandler(
        state_store=store,
        dice=dice,
        event_metadata_provider=metadata,
    )


def test_successful_proficient_check_returns_v1_event_without_saving_state() -> None:
    actor = make_creature()
    character = make_character()
    store = SpyStateStore(
        make_snapshot(
            creatures=(make_creature(creature_id="character_002"), actor),
            characters=(character,),
        )
    )
    dice = ScriptedDiceEngine(9)
    metadata = FixedEventMetadataProvider()

    result = make_handler(store, dice, metadata).handle(make_command())

    assert store.load_calls == ["campaign_001"]
    assert dice.calls == ["1d20"]
    assert metadata.calls == ["campaign_001"]
    assert store.save_calls == []
    assert result.success is True
    assert result.outcome is not None
    assert result.outcome.skill is Skill.INTIMIDATION
    assert result.outcome.ability is Ability.STRENGTH
    assert result.outcome.ability_modifier == 3
    assert result.outcome.proficiency_bonus == 3
    assert result.outcome.total == 15
    assert result.outcome.succeeded is True
    assert result.errors == ()
    assert len(result.events) == 1
    event = result.events[0]
    assert event.type == "SkillCheckResolved"
    assert event.version == 1
    assert event.payload["skill"] == "intimidation"
    assert event.payload["ability"] == "strength"
    assert event.payload["abilityModifier"] == 3
    assert event.payload["proficiencyBonus"] == 3


def test_poisoned_actor_rolls_skill_check_with_ability_check_disadvantage() -> None:
    store = SpyStateStore(
        make_snapshot(
            creatures=(
                make_creature(conditions=frozenset({Condition.POISONED})),
            ),
            characters=(make_character(),),
        )
    )
    dice = ScriptedDiceEngine(17, 6)

    result = make_handler(
        store,
        dice,
        FixedEventMetadataProvider(),
    ).handle(make_command())

    assert dice.calls == ["1d20", "1d20"]
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


def test_successful_non_proficient_check_uses_zero_bonus() -> None:
    store = SpyStateStore(
        make_snapshot(
            creatures=(make_creature(),),
            characters=(make_character(proficiencies=frozenset()),),
        )
    )

    result = make_handler(
        store,
        ScriptedDiceEngine(12),
        FixedEventMetadataProvider(),
    ).handle(make_command())

    assert result.success is True
    assert result.outcome is not None
    assert result.outcome.proficiency_bonus == 0
    assert result.outcome.total == 15
    assert store.save_calls == []


def test_failed_gameplay_check_is_successful_processing() -> None:
    store = SpyStateStore(
        make_snapshot(
            creatures=(make_creature(),),
            characters=(make_character(),),
        )
    )

    result = make_handler(
        store,
        ScriptedDiceEngine(1),
        FixedEventMetadataProvider(),
    ).handle(make_command())

    assert result.success is True
    assert result.outcome is not None
    assert result.outcome.succeeded is False
    assert result.errors == ()
    assert len(result.events) == 1
    assert store.save_calls == []


def test_alternative_ability_survives_end_to_end() -> None:
    store = SpyStateStore(
        make_snapshot(
            creatures=(make_creature(),),
            characters=(make_character(),),
        )
    )

    result = make_handler(
        store,
        ScriptedDiceEngine(9),
        FixedEventMetadataProvider(),
    ).handle(
        make_command(skill=Skill.INTIMIDATION, ability=Ability.STRENGTH)
    )

    assert result.outcome is not None
    assert result.outcome.ability is Ability.STRENGTH
    assert result.outcome.ability_modifier == 3
    assert result.outcome.proficiency_bonus == 3
    assert result.events[0].payload["ability"] == "strength"
    assert result.events[0].payload["skill"] == "intimidation"


def test_missing_creature_wins_lookup_order_without_side_effects() -> None:
    unrelated_creature = make_creature(creature_id="character_002")
    unrelated_character = make_character(character_id="character_002")
    store = SpyStateStore(
        make_snapshot(
            creatures=(unrelated_creature,),
            characters=(unrelated_character,),
        )
    )
    dice = ScriptedDiceEngine(20)
    metadata = FixedEventMetadataProvider()

    result = make_handler(store, dice, metadata).handle(make_command())

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.ENTITY_NOT_FOUND
    assert result.errors[0].entity_id == "character_001"
    assert dice.calls == []
    assert metadata.calls == []
    assert store.save_calls == []


def test_missing_character_returns_invalid_state_without_side_effects() -> None:
    store = SpyStateStore(make_snapshot(creatures=(make_creature(),)))
    dice = ScriptedDiceEngine(20)
    metadata = FixedEventMetadataProvider()

    result = make_handler(store, dice, metadata).handle(make_command())

    assert result.success is False
    assert result.outcome is None
    assert result.events == ()
    assert len(result.errors) == 1
    assert result.errors[0].code is ErrorCode.INVALID_STATE
    assert result.errors[0].entity_id == "character_001"
    assert result.errors[0].field == "characters"
    assert dice.calls == []
    assert metadata.calls == []
    assert store.save_calls == []


def test_handler_does_not_mutate_loaded_state() -> None:
    snapshot = make_snapshot(
        creatures=(make_creature(),),
        characters=(make_character(),),
    )
    before = deepcopy(snapshot)
    store = SpyStateStore(snapshot)

    make_handler(
        store,
        ScriptedDiceEngine(9),
        FixedEventMetadataProvider(),
    ).handle(make_command())

    assert store.snapshot == before
    assert store.save_calls == []


def test_state_store_load_failure_propagates() -> None:
    store = FailingStateStore(make_snapshot())
    dice = ScriptedDiceEngine(20)
    metadata = FixedEventMetadataProvider()

    with pytest.raises(StateStoreError, match="unavailable"):
        make_handler(store, dice, metadata).handle(make_command())

    assert dice.calls == []
    assert metadata.calls == []
    assert store.save_calls == []


def test_dice_failure_propagates_before_metadata_request() -> None:
    store = SpyStateStore(
        make_snapshot(
            creatures=(make_creature(),),
            characters=(make_character(),),
        )
    )
    dice = FailingDiceEngine(20)
    metadata = FixedEventMetadataProvider()

    with pytest.raises(RuntimeError, match="dice unavailable"):
        make_handler(store, dice, metadata).handle(make_command())

    assert dice.calls == ["1d20"]
    assert metadata.calls == []
    assert store.save_calls == []


def test_metadata_failure_propagates_after_resolution_without_save() -> None:
    store = SpyStateStore(
        make_snapshot(
            creatures=(make_creature(),),
            characters=(make_character(),),
        )
    )
    dice = ScriptedDiceEngine(9)
    metadata = FixedEventMetadataProvider(fail=True)

    with pytest.raises(RuntimeError, match="metadata unavailable"):
        make_handler(store, dice, metadata).handle(make_command())

    assert dice.calls == ["1d20"]
    assert metadata.calls == ["campaign_001"]
    assert store.save_calls == []
