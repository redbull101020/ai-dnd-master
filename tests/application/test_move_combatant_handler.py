from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import inspect

import pytest

from dnd_engine.application.handlers.move_combatant import MoveCombatantHandler
from dnd_engine.application.services.event_metadata import EventMetadata
from dnd_engine.domain.commands.move_combatant import MoveCombatantCommand, MoveCombatantPayload
from dnd_engine.domain.definitions.monster import MonsterDefinition
from dnd_engine.domain.errors import ErrorCode
from dnd_engine.domain.services.definitions import DefinitionNotFoundError, DefinitionTypeMismatchError
from dnd_engine.domain.services.state_store import StateStoreError
from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.state.combat import CombatPosition, CombatState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.infrastructure.definitions.packaged import PackagedDefinitionSource


class Store:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.saves = []
        self.failure = None

    def load(self, campaign_id):
        assert campaign_id == "campaign_001"
        return self.snapshot

    def save(self, snapshot):
        self.saves.append(snapshot)
        if self.failure:
            raise self.failure
        self.snapshot = snapshot


class Definitions:
    def __init__(self):
        self.calls = []
        self.failure = None
        self.definition = PackagedDefinitionSource().get_definition(
            ruleset_id="dnd_5e", ruleset_version="5.1", definition_id="goblin",
            expected_type=MonsterDefinition,
        )

    def get_definition(self, **kwargs):
        self.calls.append(kwargs)
        if self.failure:
            raise self.failure
        return self.definition


class Metadata:
    def __init__(self):
        self.calls = []
        self.failure = None

    def next_metadata(self, campaign_id):
        self.calls.append(campaign_id)
        if self.failure:
            raise self.failure
        return EventMetadata(event_id=f"event_{len(self.calls):06d}",
                             timestamp=datetime(2026, 10, 3, tzinfo=timezone.utc))


def setup():
    actor = CreatureState("monster_001", "goblin", AbilityScores(10,10,10,10,10,10), 7, 7)
    snapshot = StateSnapshot(
        campaign=CampaignState("campaign_001", "dnd_5e", "5.1"), creatures=(actor,),
        combat=CombatState("combat_001", 1, (actor.id,), 0,
                           (CombatPosition(actor.id, 0, 0),)),
    )
    store, definitions, metadata = Store(snapshot), Definitions(), Metadata()
    handler = MoveCombatantHandler(state_store=store, definition_source=definitions,
                                   event_metadata_provider=metadata)
    return store, definitions, metadata, handler


def command(x=3, y=4, actor_id="monster_001", combat_id="combat_001"):
    return MoveCombatantCommand("command_001", "campaign_001", actor_id,
                               MoveCombatantPayload(combat_id, x, y))


@pytest.mark.parametrize("case,code,entity,field,lookup", [
    ("actor", ErrorCode.ENTITY_NOT_FOUND, "monster_absent", None, False),
    ("combat", ErrorCode.ENTITY_NOT_FOUND, "combat_001", "combat_id", False),
    ("mismatch", ErrorCode.ENTITY_NOT_FOUND, "combat_absent", "combat_id", False),
    ("inactive", ErrorCode.ACTION_NOT_AVAILABLE, "monster_001", None, False),
    ("character", ErrorCode.ACTION_NOT_AVAILABLE, "monster_001", None, False),
    ("missing_definition", ErrorCode.DEFINITION_NOT_FOUND, "goblin", "definition_id", True),
    ("wrong_definition", ErrorCode.INVALID_STATE, "monster_001", "definition_id", True),
    ("hp", ErrorCode.ACTION_NOT_AVAILABLE, "monster_001", None, True),
    ("speed", ErrorCode.ACTION_NOT_AVAILABLE, "monster_001", "walking_speed", True),
    ("position", ErrorCode.ACTION_NOT_AVAILABLE, "monster_001", "position", True),
    ("noop", ErrorCode.INVALID_COMMAND, "monster_001", "position", True),
    ("budget", ErrorCode.OUT_OF_RANGE, "monster_001", "position", True),
    ("zero_speed", ErrorCode.OUT_OF_RANGE, "monster_001", "position", True),
    ("spent_above_speed", ErrorCode.OUT_OF_RANGE, "monster_001", "position", True),
])
def test_rejections_and_precedence(case, code, entity, field, lookup):
    store, definitions, metadata, handler = setup()
    cmd = command()
    s = store.snapshot
    if case == "actor":
        cmd = command(actor_id="monster_absent")
        s = replace(s, combat=None)
    elif case == "combat":
        s = replace(s, combat=None)
    elif case == "mismatch":
        cmd = command(combat_id="combat_absent")
    elif case == "inactive":
        other = replace(s.creatures[0], id="monster_002")
        s = replace(s, creatures=(*s.creatures, other),
                    combat=replace(s.combat, order=(other.id, "monster_001")))
    elif case == "character":
        s = replace(s, characters=(CharacterState("monster_001", 1, frozenset(), frozenset(), frozenset()),))
    elif case == "missing_definition":
        definitions.failure = DefinitionNotFoundError("missing")
        s = replace(s, creatures=(replace(s.creatures[0], current_hp=0),))
    elif case == "wrong_definition":
        definitions.failure = DefinitionTypeMismatchError("wrong")
        s = replace(s, creatures=(replace(s.creatures[0], current_hp=0),))
    elif case == "hp":
        s = replace(s, creatures=(replace(s.creatures[0], current_hp=0),))
        definitions.definition = replace(definitions.definition, walking_speed=None)
    elif case == "speed":
        definitions.definition = replace(definitions.definition, walking_speed=None)
        s = replace(s, combat=replace(s.combat, positions=()))
    elif case == "position":
        cmd = command(0, 0)
        s = replace(s, combat=replace(s.combat, positions=()))
    elif case == "noop":
        cmd = command(0, 0)
        definitions.definition = replace(definitions.definition, walking_speed=0)
    elif case == "budget":
        s = replace(s, combat=replace(s.combat, movement_spent=26))
    elif case == "zero_speed":
        definitions.definition = replace(definitions.definition, walking_speed=0)
    elif case == "spent_above_speed":
        s = replace(s, combat=replace(s.combat, movement_spent=100))
    store.snapshot = s
    before = deepcopy(s)
    result = handler.handle(cmd)
    assert not result.success and result.events == () and result.outcome is None
    assert (result.errors[0].code, result.errors[0].entity_id, result.errors[0].field) == (code, entity, field)
    assert bool(definitions.calls) == lookup
    assert metadata.calls == [] and store.saves == [] and store.snapshot == before


@pytest.mark.parametrize("action_spent", [False, True])
def test_split_movement_exact_budget_and_action_independence(action_spent):
    store, definitions, metadata, handler = setup()
    store.snapshot = replace(store.snapshot, combat=replace(store.snapshot.combat, action_spent=action_spent))
    before = deepcopy(store.snapshot)
    for x, y, spent in [(3,4,5), (0,0,10), (-20,0,30)]:
        result = handler.handle(command(x,y))
        assert result.success and len(result.events) == 1
        assert result.outcome.movement_spent == spent
        assert store.snapshot.combat.movement_spent == spent
        assert store.snapshot.combat.action_spent is action_spent
    assert before.combat.movement_spent == 0
    assert len(store.saves) == len(metadata.calls) == 3
    assert definitions.calls[0] == dict(ruleset_id="dnd_5e", ruleset_version="5.1",
                                      definition_id="goblin", expected_type=MonsterDefinition)
    assert handler.handle(command(-21,0)).errors[0].code is ErrorCode.OUT_OF_RANGE
    assert len(store.saves) == len(metadata.calls) == 3


@pytest.mark.parametrize("boundary", ["load", "definition", "metadata", "save"])
def test_failures_propagate_unchanged(boundary):
    store, definitions, metadata, handler = setup()
    before = deepcopy(store.snapshot)
    failure = StateStoreError("unavailable") if boundary in ("load", "save") else RuntimeError("unavailable")
    if boundary == "load":
        def fail_load(campaign_id):
            raise failure
        store.load = fail_load
    else:
        {"definition": definitions, "metadata": metadata, "save": store}[boundary].failure = failure
    with pytest.raises(type(failure)) as exc:
        handler.handle(command())
    assert exc.value is failure
    assert len(store.saves) == (1 if boundary == "save" else 0)
    assert store.snapshot == before
    if boundary == "save":
        assert store.saves[0].combat.movement_spent == 5
        assert store.saves[0].combat.positions == (CombatPosition("monster_001",3,4),)


def test_dependency_shape():
    assert set(inspect.signature(MoveCombatantHandler).parameters) == {
        "state_store", "definition_source", "event_metadata_provider",
    }
