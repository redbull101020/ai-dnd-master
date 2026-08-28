import random
from datetime import datetime, timezone
from pathlib import Path

from dnd_engine.application.handlers.attack import AttackHandler
from dnd_engine.application.services.event_metadata import EventMetadata
from dnd_engine.domain.commands.attack import AttackCommand, AttackPayload
from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.character import CharacterState
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
