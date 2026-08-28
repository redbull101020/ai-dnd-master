import json
from datetime import datetime, timezone
from pathlib import Path

from dnd_engine.application.handlers.remove_condition import RemoveConditionHandler
from dnd_engine.application.services.event_metadata import EventMetadata
from dnd_engine.domain.commands.remove_condition import (
    RemoveConditionCommand,
    RemoveConditionPayload,
)
from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.domain.value_objects.condition import Condition
from dnd_engine.infrastructure.filesystem.state_store import FilesystemStateStore


FIXED_TIMESTAMP = datetime(2026, 8, 28, 19, 30, tzinfo=timezone.utc)


class CountingStateStore:
    """Thin call-counting wrapper around a real StateStore, for observing
    the RemoveConditionHandler's own save() call count without instrumenting
    the production FilesystemStateStore adapter itself."""

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


def test_remove_condition_handler_persists_through_real_filesystem_state_store(
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
    other_creature = CreatureState(
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
        conditions=frozenset({Condition.POISONED}),
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
    command = RemoveConditionCommand(
        command_id="command_000555",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=RemoveConditionPayload(
            target_id="monster_001", condition=Condition.POISONED
        ),
    )

    result = RemoveConditionHandler(
        state_store=store,
        event_metadata_provider=metadata,
    ).handle(command)

    assert metadata.calls == ["campaign_001"]
    assert result.success is True
    assert result.errors == ()
    assert result.outcome is not None
    assert result.outcome.previous_active is True
    assert result.outcome.active is False

    assert len(result.events) == 1
    event = result.events[0]
    assert event.type == "ConditionRemoved"
    assert event.version == 1
    assert event.payload == {
        "targetId": "monster_001",
        "condition": "poisoned",
        "previousActive": True,
        "active": False,
    }

    # persisted bytes actually changed
    state_after = state_path.read_bytes()
    assert state_after != state_before

    serialized_state = json.loads(state_path.read_text(encoding="utf-8"))
    serialized_target = next(
        creature
        for creature in serialized_state["state"]["creatures"]
        if creature["id"] == "monster_001"
    )
    assert serialized_target["conditions"] == []

    # fresh reload through a brand-new FilesystemStateStore instance, proving
    # persistence via the production V4 serializer path rather than through
    # any in-process cache
    reloaded = FilesystemStateStore(campaigns_root).load("campaign_001")
    reloaded_target = next(
        creature for creature in reloaded.creatures if creature.id == "monster_001"
    )
    assert reloaded_target.conditions == frozenset()

    # campaign unchanged
    assert reloaded.campaign == snapshot.campaign

    # other creatures unchanged (untouched target keeps its condition)
    reloaded_actor = next(
        creature for creature in reloaded.creatures if creature.id == "character_001"
    )
    reloaded_other = next(
        creature for creature in reloaded.creatures if creature.id == "monster_002"
    )
    assert reloaded_actor.conditions == frozenset()
    assert reloaded_other.conditions == frozenset({Condition.POISONED})

    # characters unchanged
    assert reloaded.characters == snapshot.characters

    # exactly one authoritative snapshot persisted through the observable
    # store seam, for this handler invocation
    assert len(store.save_calls) == 1
    assert store.save_calls[0] is not snapshot

    # no events.jsonl / Event history artifacts, no other files created
    assert sorted(
        path.relative_to(state_path.parent).as_posix()
        for path in state_path.parent.rglob("*")
        if path.is_file()
    ) == ["state.json"]
    assert list(state_path.parent.glob(".state-*.tmp")) == []
