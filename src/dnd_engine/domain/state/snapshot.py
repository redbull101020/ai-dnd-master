from dataclasses import dataclass

from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.creature import CreatureState


@dataclass(frozen=True)
class StateSnapshot:
    campaign: CampaignState
    creatures: tuple[CreatureState, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.campaign, CampaignState):
            raise TypeError("campaign must be a CampaignState")
        if type(self.creatures) is not tuple:
            raise TypeError("creatures must be a tuple")
        if not all(isinstance(creature, CreatureState) for creature in self.creatures):
            raise TypeError("creatures must contain only CreatureState values")

        creature_ids = [creature.id for creature in self.creatures]
        if len(creature_ids) != len(set(creature_ids)):
            raise ValueError("creature IDs must be unique within a StateSnapshot")
