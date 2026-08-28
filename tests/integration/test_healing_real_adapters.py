import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dnd_engine.application.handlers.healing import HealingHandler
from dnd_engine.application.services.event_metadata import EventMetadata
from dnd_engine.domain.commands.healing import (
    ApplyHealingCommand,
    ApplyHealingPayload,
)
from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.infrastructure.filesystem.state_store import FilesystemStateStore


FIXED_TIMESTAMP = datetime(2026, 8, 28, 17, 30, tzinfo=timezone.utc)


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


class FixedEventMetadataProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def next_metadata(self, campaign_id: str) -> EventMetadata:
        self.calls.append(campaign_id)
        return EventMetadata(
            event_id="event_000999",
            timestamp=FIXED_TIMESTAMP,
        )


def make_creature(
    *,
    creature_id: str,
    definition_id: str,
    current_hp: int,
    max_hp: int,
) -> CreatureState:
    return CreatureState(
        id=creature_id,
        definition_id=definition_id,
        ability_scores=AbilityScores(
            strength=10,
            dexterity=10,
            constitution=10,
            intelligence=10,
            wisdom=10,
            charisma=10,
        ),
        current_hp=current_hp,
        max_hp=max_hp,
    )


@pytest.mark.parametrize(
    ("initial_hp", "amount", "expected_hp"),
    [
        (7, 8, 15),
        (18, 10, 20),
    ],
    ids=("normal", "capped"),
)
def test_healing_handler_persists_hp_through_real_filesystem_state_store(
    tmp_path: Path,
    initial_hp: int,
    amount: int,
    expected_hp: int,
) -> None:
    campaigns_root = tmp_path / "campaigns"
    actor = make_creature(
        creature_id="character_001",
        definition_id="cleric",
        current_hp=20,
        max_hp=20,
    )
    target = make_creature(
        creature_id="monster_001",
        definition_id="goblin",
        current_hp=initial_hp,
        max_hp=20,
    )
    other_creature = make_creature(
        creature_id="monster_002",
        definition_id="goblin",
        current_hp=11,
        max_hp=20,
    )
    character = CharacterState(
        id="character_001",
        total_level=5,
        saving_throw_proficiencies=frozenset(),
        skill_proficiencies=frozenset(),
    )
    snapshot = StateSnapshot(
        campaign=CampaignState(
            id="campaign_001",
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
        ),
        creatures=(actor, target, other_creature),
        characters=(character,),
    )
    real_store = FilesystemStateStore(campaigns_root)
    real_store.save(snapshot)

    state_path = campaigns_root / "campaign_001" / "state.json"
    state_before = state_path.read_bytes()

    store = CountingStateStore(real_store)
    metadata = FixedEventMetadataProvider()
    command = ApplyHealingCommand(
        command_id="command_000555",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=ApplyHealingPayload(target_id="monster_001", amount=amount),
    )

    result = HealingHandler(
        state_store=store,
        event_metadata_provider=metadata,
    ).handle(command)

    assert metadata.calls == ["campaign_001"]
    assert result.success is True
    assert result.errors == ()
    assert result.outcome is not None
    assert result.outcome.previous_hp == initial_hp
    assert result.outcome.max_hp == 20
    assert result.outcome.new_hp == expected_hp

    assert len(result.events) == 1
    event = result.events[0]
    assert event.type == "HealingApplied"
    assert event.version == 1
    assert event.payload == {
        "targetId": "monster_001",
        "amount": amount,
        "previousHp": initial_hp,
        "maxHp": 20,
        "newHp": expected_hp,
    }

    state_after = state_path.read_bytes()
    assert state_after != state_before

    serialized_state = json.loads(state_path.read_text(encoding="utf-8"))
    serialized_target = next(
        creature
        for creature in serialized_state["state"]["creatures"]
        if creature["id"] == "monster_001"
    )
    assert serialized_target["currentHp"] == expected_hp
    assert serialized_target["maxHp"] == 20

    reloaded = real_store.load("campaign_001")
    reloaded_target = next(
        creature for creature in reloaded.creatures if creature.id == "monster_001"
    )
    assert reloaded_target.current_hp == expected_hp
    assert reloaded_target.max_hp == 20
    assert reloaded.campaign == snapshot.campaign

    reloaded_actor = next(
        creature for creature in reloaded.creatures if creature.id == "character_001"
    )
    reloaded_other = next(
        creature for creature in reloaded.creatures if creature.id == "monster_002"
    )
    assert (reloaded_actor.current_hp, reloaded_actor.max_hp) == (20, 20)
    assert (reloaded_other.current_hp, reloaded_other.max_hp) == (11, 20)
    assert reloaded.characters == snapshot.characters

    assert len(store.save_calls) == 1
    assert store.save_calls[0] is not snapshot

    assert not (state_path.parent / "events.jsonl").exists()
    assert sorted(
        path.relative_to(state_path.parent).as_posix()
        for path in state_path.parent.rglob("*")
        if path.is_file()
    ) == ["state.json"]
    assert list(state_path.parent.glob(".state-*.tmp")) == []
