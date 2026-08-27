from dnd_engine.domain.definitions.monster import MonsterDefinition
from dnd_engine.domain.rules.ability import ability_modifier
from dnd_engine.domain.services.definitions import DefinitionSource
from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.infrastructure.definitions.packaged import PackagedDefinitionSource


def test_monster_baseline_armor_class_comes_from_packaged_definition() -> None:
    campaign = CampaignState(
        id="campaign_001",
        ruleset_id="dnd_5e",
        ruleset_version="5.1",
    )
    creature = CreatureState(
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
    source: DefinitionSource = PackagedDefinitionSource()

    monster_definition = source.get_definition(
        ruleset_id=campaign.ruleset_id,
        ruleset_version=campaign.ruleset_version,
        definition_id=creature.definition_id,
        expected_type=MonsterDefinition,
    )
    baseline_armor_class = monster_definition.armor_class
    dexterity_based_armor_class = 10 + ability_modifier(
        creature.ability_scores.dexterity
    )

    assert isinstance(monster_definition, MonsterDefinition)
    assert baseline_armor_class == monster_definition.armor_class
    assert baseline_armor_class != dexterity_based_armor_class
