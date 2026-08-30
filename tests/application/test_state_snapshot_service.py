from dataclasses import replace

import pytest

from dnd_engine.application.services.state_snapshot import (
    replace_creature_in_snapshot,
)
from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.state.combat import CombatState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability_scores import AbilityScores


def make_creature(creature_id: str, *, current_hp: int = 7) -> CreatureState:
    return CreatureState(
        id=creature_id,
        definition_id="goblin",
        ability_scores=AbilityScores(8, 14, 10, 10, 8, 8),
        current_hp=current_hp,
        max_hp=7,
    )


def test_replaces_exactly_one_creature_and_preserves_snapshot_projections() -> None:
    campaign = CampaignState(
        id="campaign_001",
        ruleset_id="dnd_5e",
        ruleset_version="5.1",
    )
    character_creature = make_creature("character_001")
    target = make_creature("monster_001")
    other = make_creature("monster_002")
    character = CharacterState(
        id="character_001",
        total_level=1,
        saving_throw_proficiencies=frozenset(),
        skill_proficiencies=frozenset(),
    )
    combat = CombatState(
        id="combat_001",
        round=2,
        order=("monster_002", "character_001", "monster_001"),
        active_index=1,
    )
    snapshot = StateSnapshot(
        campaign=campaign,
        creatures=(other, target, character_creature),
        characters=(character,),
        combat=combat,
    )
    replacement = replace(target, current_hp=3)

    result = replace_creature_in_snapshot(snapshot, replacement)

    assert result is not snapshot
    assert result.campaign is campaign
    assert result.creatures == (other, replacement, character_creature)
    assert result.creatures[0] is other
    assert result.creatures[1] is replacement
    assert result.creatures[2] is character_creature
    assert result.characters is snapshot.characters
    assert result.characters[0] is character
    assert result.combat is combat
    assert snapshot.creatures == (other, target, character_creature)
    assert snapshot.campaign is campaign
    assert snapshot.characters == (character,)
    assert snapshot.combat is combat
    assert target.current_hp == 7


def test_rejects_replacement_without_matching_creature_and_does_not_append() -> None:
    target = make_creature("monster_001")
    snapshot = StateSnapshot(
        campaign=CampaignState(
            id="campaign_001",
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
        ),
        creatures=(target,),
    )
    missing = make_creature("monster_999")

    with pytest.raises(ValueError, match="must match exactly one"):
        replace_creature_in_snapshot(snapshot, missing)

    assert snapshot.creatures == (target,)


def test_rejects_invalid_inputs() -> None:
    creature = make_creature("monster_001")
    snapshot = StateSnapshot(
        campaign=CampaignState(
            id="campaign_001",
            ruleset_id="dnd_5e",
            ruleset_version="5.1",
        ),
        creatures=(creature,),
    )

    with pytest.raises(TypeError, match="snapshot must be"):
        replace_creature_in_snapshot(object(), creature)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="replacement must be"):
        replace_creature_in_snapshot(snapshot, object())  # type: ignore[arg-type]
