from dataclasses import dataclass

from dnd_engine.domain.commands.healing import ApplyHealingCommand
from dnd_engine.domain.state.creature import CreatureState


@dataclass(frozen=True)
class HealingResult:
    target_id: str
    amount: int
    previous_hp: int
    max_hp: int
    new_hp: int

    def __post_init__(self) -> None:
        if type(self.target_id) is not str:
            raise TypeError("target_id must be a str")
        for field_name in ("amount", "previous_hp", "max_hp", "new_hp"):
            if type(getattr(self, field_name)) is not int:
                raise TypeError(f"{field_name} must be an int")
        if self.amount < 1:
            raise ValueError("amount must be at least 1")
        if self.max_hp < 1:
            raise ValueError("max_hp must be at least 1")
        if not 0 <= self.previous_hp <= self.max_hp:
            raise ValueError("previous_hp must be between 0 and max_hp")
        if self.new_hp != min(self.max_hp, self.previous_hp + self.amount):
            raise ValueError(
                "new_hp must equal min(max_hp, previous_hp + amount)"
            )


def resolve_healing(
    command: ApplyHealingCommand,
    target: CreatureState,
) -> HealingResult:
    if not isinstance(command, ApplyHealingCommand):
        raise TypeError("command must be an ApplyHealingCommand")
    if not isinstance(target, CreatureState):
        raise TypeError("target must be a CreatureState")
    if command.payload.target_id != target.id:
        raise ValueError("command payload target_id must match target id")

    previous_hp = target.current_hp
    max_hp = target.max_hp
    new_hp = min(max_hp, previous_hp + command.payload.amount)

    return HealingResult(
        target_id=command.payload.target_id,
        amount=command.payload.amount,
        previous_hp=previous_hp,
        max_hp=max_hp,
        new_hp=new_hp,
    )
