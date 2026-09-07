from dnd_engine.domain.state.combat import CombatPosition

DND_5E_FIRST_CONSUMER_MELEE_REACH_FEET = 5


def is_within_melee_reach(
    actor: CombatPosition,
    target: CombatPosition,
    effective_reach: int,
) -> bool:
    if not isinstance(actor, CombatPosition):
        raise TypeError("actor must be a CombatPosition")
    if not isinstance(target, CombatPosition):
        raise TypeError("target must be a CombatPosition")
    if type(effective_reach) is not int:
        raise TypeError("effective_reach must be an int")

    dx = actor.x - target.x
    dy = actor.y - target.y
    return dx * dx + dy * dy <= effective_reach * effective_reach
