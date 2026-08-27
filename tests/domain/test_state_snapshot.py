from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.ability_scores import AbilityScores


def campaign_state() -> CampaignState:
    return CampaignState(
        id="campaign_001",
        ruleset_id="dnd_5e",
        ruleset_version="5.1",
    )


def creature_state(creature_id: str) -> CreatureState:
    return CreatureState(
        id=creature_id,
        definition_id="goblin",
        ability_scores=AbilityScores(8, 14, 10, 10, 8, 8),
        current_hp=7,
        max_hp=7,
    )


def character_state(character_id: str) -> CharacterState:
    return CharacterState(
        id=character_id,
        total_level=5,
        saving_throw_proficiencies=frozenset(
            {Ability.STRENGTH, Ability.CONSTITUTION}
        ),
        skill_proficiencies=frozenset(),
    )


def test_snapshot_accepts_campaign_and_zero_creatures() -> None:
    campaign = campaign_state()

    snapshot = StateSnapshot(campaign=campaign, creatures=())

    assert snapshot.campaign is campaign
    assert snapshot.creatures == ()
    assert snapshot.characters == ()


def test_snapshot_accepts_multiple_creatures_as_tuple() -> None:
    creatures = (creature_state("monster_002"), creature_state("monster_001"))

    snapshot = StateSnapshot(campaign=campaign_state(), creatures=creatures)

    assert snapshot.creatures is creatures
    assert type(snapshot.creatures) is tuple


def test_snapshot_rejects_non_tuple_creatures() -> None:
    with pytest.raises(TypeError):
        StateSnapshot(  # type: ignore[arg-type]
            campaign=campaign_state(),
            creatures=[creature_state("monster_001")],
        )


def test_snapshot_rejects_duplicate_creature_ids() -> None:
    with pytest.raises(ValueError):
        StateSnapshot(
            campaign=campaign_state(),
            creatures=(
                creature_state("monster_001"),
                creature_state("monster_001"),
            ),
        )


def test_snapshot_accepts_character_referencing_existing_creature() -> None:
    creature = creature_state("character_001")
    character = character_state("character_001")

    snapshot = StateSnapshot(
        campaign=campaign_state(),
        creatures=(creature,),
        characters=(character,),
    )

    assert snapshot.characters == (character,)


def test_snapshot_accepts_creature_without_character_state() -> None:
    snapshot = StateSnapshot(
        campaign=campaign_state(),
        creatures=(creature_state("monster_001"),),
        characters=(),
    )

    assert snapshot.characters == ()


def test_snapshot_rejects_non_tuple_characters() -> None:
    with pytest.raises(TypeError):
        StateSnapshot(  # type: ignore[arg-type]
            campaign=campaign_state(),
            creatures=(creature_state("character_001"),),
            characters=[character_state("character_001")],
        )


def test_snapshot_rejects_non_character_values() -> None:
    with pytest.raises(TypeError):
        StateSnapshot(  # type: ignore[arg-type]
            campaign=campaign_state(),
            creatures=(creature_state("character_001"),),
            characters=(creature_state("character_001"),),
        )


def test_snapshot_rejects_duplicate_character_ids() -> None:
    with pytest.raises(ValueError):
        StateSnapshot(
            campaign=campaign_state(),
            creatures=(creature_state("character_001"),),
            characters=(
                character_state("character_001"),
                character_state("character_001"),
            ),
        )


def test_snapshot_rejects_character_without_matching_creature() -> None:
    with pytest.raises(ValueError):
        StateSnapshot(
            campaign=campaign_state(),
            creatures=(creature_state("monster_001"),),
            characters=(character_state("character_001"),),
        )


def test_snapshot_is_a_frozen_grouping_not_a_state_owner() -> None:
    campaign = campaign_state()
    creature = creature_state("monster_001")
    snapshot = StateSnapshot(campaign=campaign, creatures=(creature,))

    with pytest.raises(FrozenInstanceError):
        snapshot.creatures = ()  # type: ignore[misc]

    campaign.ruleset_version = "5.2.2"
    creature.current_hp = 3

    assert snapshot.campaign is campaign
    assert snapshot.creatures[0] is creature
    assert tuple(field.name for field in fields(CampaignState)) == (
        "id",
        "ruleset_id",
        "ruleset_version",
    )


def test_snapshot_has_only_persistence_grouping_fields() -> None:
    assert tuple(field.name for field in fields(StateSnapshot)) == (
        "campaign",
        "creatures",
        "characters",
    )
