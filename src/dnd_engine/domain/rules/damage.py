from dataclasses import dataclass

from dnd_engine.domain.commands.damage import ApplyDamageCommand
from dnd_engine.domain.state.creature import CreatureState


@dataclass(frozen=True)
class DamageResult:
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
        if self.amount < 1:
            raise ValueError("amount must be at least 1")
        if self.previous_hp < 0:
            raise ValueError("previous_hp must not be negative")
        if self.new_hp != max(0, self.previous_hp - self.amount):
            raise ValueError("new_hp must equal max(0, previous_hp - amount)")


def resolve_damage(
    command: ApplyDamageCommand,
    target: CreatureState,
) -> DamageResult:
    if not isinstance(command, ApplyDamageCommand):
        raise TypeError("command must be an ApplyDamageCommand")
    if not isinstance(target, CreatureState):
        raise TypeError("target must be a CreatureState")
    if command.payload.target_id != target.id:
        raise ValueError("command payload target_id must match target id")

    previous_hp = target.current_hp
    new_hp = max(0, previous_hp - command.payload.amount)

    return DamageResult(
        target_id=command.payload.target_id,
        amount=command.payload.amount,
        previous_hp=previous_hp,
        new_hp=new_hp,
    )
