from dataclasses import dataclass
from datetime import datetime

from dnd_engine.domain.commands.damage import ApplyDamageCommand
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.rules.damage import DamageResult


@dataclass(frozen=True)
class DamageAppliedPayloadV1:
    target_id: str
    amount: int
    previous_hp: int
    new_hp: int

    def __post_init__(self) -> None:
        if type(self.target_id) is not str:
            raise TypeError("target_id must be a str")
        for field_name in ("amount", "previous_hp", "new_hp"):
            if type(getattr(self, field_name)) is not int:
                raise TypeError(f"{field_name} must be an int")


def build_damage_applied_v1(
    *,
    event_id: str,
    timestamp: datetime,
    command: ApplyDamageCommand,
    outcome: DamageResult,
) -> GameEvent:
    if not isinstance(command, ApplyDamageCommand):
        raise TypeError("command must be an ApplyDamageCommand")
    if not isinstance(outcome, DamageResult):
        raise TypeError("outcome must be a DamageResult")
    if outcome.target_id != command.payload.target_id:
        raise ValueError("outcome target_id must match command payload target_id")
    if outcome.amount != command.payload.amount:
        raise ValueError("outcome amount must match command payload amount")

    payload = DamageAppliedPayloadV1(
        target_id=outcome.target_id,
        amount=outcome.amount,
        previous_hp=outcome.previous_hp,
        new_hp=outcome.new_hp,
    )

    return GameEvent(
        event_id=event_id,
        command_id=command.command_id,
        type="DamageApplied",
        version=1,
        campaign_id=command.campaign_id,
        timestamp=timestamp,
        actor_id=command.actor_id,
        caused_by=None,
        payload={
            "targetId": payload.target_id,
            "amount": payload.amount,
            "previousHp": payload.previous_hp,
            "newHp": payload.new_hp,
        },
    )
