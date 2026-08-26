from dataclasses import dataclass

from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.state.creature import CreatureState


@dataclass(frozen=True)
class StateSnapshot:
    campaign: CampaignState
    creatures: tuple[CreatureState, ...]
    characters: tuple[CharacterState, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.campaign, CampaignState):
            raise TypeError("campaign must be a CampaignState")
        if type(self.creatures) is not tuple:
            raise TypeError("creatures must be a tuple")
        if not all(isinstance(creature, CreatureState) for creature in self.creatures):
            raise TypeError("creatures must contain only CreatureState values")
        if type(self.characters) is not tuple:
            raise TypeError("characters must be a tuple")
        if not all(
            isinstance(character, CharacterState) for character in self.characters
        ):
            raise TypeError("characters must contain only CharacterState values")

        creature_ids = [creature.id for creature in self.creatures]
        if len(creature_ids) != len(set(creature_ids)):
            raise ValueError("creature IDs must be unique within a StateSnapshot")

        character_ids = [character.id for character in self.characters]
        if len(character_ids) != len(set(character_ids)):
            raise ValueError("character IDs must be unique within a StateSnapshot")
        if not set(character_ids).issubset(creature_ids):
            raise ValueError(
                "every CharacterState must have a corresponding CreatureState"
            )
