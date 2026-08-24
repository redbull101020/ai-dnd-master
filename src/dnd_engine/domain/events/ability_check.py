from dataclasses import dataclass
from datetime import datetime

from dnd_engine.domain.commands.ability_check import AbilityCheckCommand
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.rules.ability_check import AbilityCheckResult
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.dice_roll import DiceRoll


@dataclass(frozen=True)
class AbilityCheckResolvedPayloadV1:
    ability: Ability
    dc: int
    roll: DiceRoll
    modifier: int
    total: int
    succeeded: bool

    def __post_init__(self) -> None:
        if not isinstance(self.ability, Ability):
            raise TypeError("ability must be an Ability")
        for field_name in ("dc", "modifier", "total"):
            if type(getattr(self, field_name)) is not int:
                raise TypeError(f"{field_name} must be an int")
        if not isinstance(self.roll, DiceRoll):
            raise TypeError("roll must be a DiceRoll")
        if type(self.succeeded) is not bool:
            raise TypeError("succeeded must be a bool")
        if self.total != self.roll.total + self.modifier:
            raise ValueError("total must equal roll.total plus modifier")
        if self.succeeded is not (self.total >= self.dc):
            raise ValueError("succeeded must equal total >= dc")


def build_ability_check_resolved_v1(
    *,
    event_id: str,
    timestamp: datetime,
    command: AbilityCheckCommand,
    outcome: AbilityCheckResult,
) -> GameEvent:
    if not isinstance(command, AbilityCheckCommand):
        raise TypeError("command must be an AbilityCheckCommand")
    if not isinstance(outcome, AbilityCheckResult):
        raise TypeError("outcome must be an AbilityCheckResult")
    if outcome.ability != command.payload.ability:
        raise ValueError("outcome ability must match command payload ability")
    if outcome.dc != command.payload.dc:
        raise ValueError("outcome dc must match command payload dc")

    payload = AbilityCheckResolvedPayloadV1(
        ability=outcome.ability,
        dc=outcome.dc,
        roll=outcome.roll,
        modifier=outcome.modifier,
        total=outcome.total,
        succeeded=outcome.succeeded,
    )

    return GameEvent(
        event_id=event_id,
        command_id=command.command_id,
        type="AbilityCheckResolved",
        version=1,
        campaign_id=command.campaign_id,
        timestamp=timestamp,
        actor_id=command.actor_id,
        caused_by=None,
        payload={
            "ability": payload.ability.value,
            "dc": payload.dc,
            "roll": {
                "expression": payload.roll.expression,
                "rolls": payload.roll.rolls,
                "total": payload.roll.total,
            },
            "modifier": payload.modifier,
            "total": payload.total,
            "succeeded": payload.succeeded,
        },
    )
