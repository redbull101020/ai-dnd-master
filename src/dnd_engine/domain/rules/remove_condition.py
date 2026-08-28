from dataclasses import dataclass

from dnd_engine.domain.commands.remove_condition import RemoveConditionCommand
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.value_objects.condition import Condition


@dataclass(frozen=True)
class ConditionRemovalResult:
    target_id: str
    condition: Condition
    previous_active: bool
    active: bool

    def __post_init__(self) -> None:
        if type(self.target_id) is not str:
            raise TypeError("target_id must be a str")
        if not isinstance(self.condition, Condition):
            raise TypeError("condition must be a Condition")
        if type(self.previous_active) is not bool:
            raise TypeError("previous_active must be a bool")
        if type(self.active) is not bool:
            raise TypeError("active must be a bool")
        if self.active is not False:
            raise ValueError(
                "active must be False for a Condition removal result"
            )


def resolve_condition_removal(
    command: RemoveConditionCommand,
    target: CreatureState,
) -> ConditionRemovalResult:
    if not isinstance(command, RemoveConditionCommand):
        raise TypeError("command must be a RemoveConditionCommand")
    if not isinstance(target, CreatureState):
        raise TypeError("target must be a CreatureState")
    if command.payload.target_id != target.id:
        raise ValueError("command payload target_id must match target id")

    previous_active = command.payload.condition in target.conditions

    return ConditionRemovalResult(
        target_id=command.payload.target_id,
        condition=command.payload.condition,
        previous_active=previous_active,
        active=False,
    )
