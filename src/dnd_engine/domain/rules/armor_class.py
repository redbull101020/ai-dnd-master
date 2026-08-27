from dnd_engine.domain.rules.ability import ability_modifier
from dnd_engine.domain.state.creature import CreatureState


def unarmored_character_armor_class(creature: CreatureState) -> int:
    return 10 + ability_modifier(creature.ability_scores.dexterity)
