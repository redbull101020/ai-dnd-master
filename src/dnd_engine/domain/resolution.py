from dataclasses import dataclass
from typing import Generic, TypeVar

from dnd_engine.domain.errors import EngineError
from dnd_engine.domain.events.game_event import GameEvent


T = TypeVar("T")


@dataclass(frozen=True)
class ResolutionResult(Generic[T]):
    success: bool
    command_id: str
    outcome: T | None
    events: tuple[GameEvent, ...]
    errors: tuple[EngineError, ...]

    def __post_init__(self) -> None:
        if type(self.success) is not bool:
            raise TypeError("success must be a bool")
        if type(self.command_id) is not str:
            raise TypeError("command_id must be a str")
        if type(self.events) is not tuple:
            raise TypeError("events must be a tuple")
        if not all(isinstance(event, GameEvent) for event in self.events):
            raise TypeError("events must contain only GameEvent values")
        if type(self.errors) is not tuple:
            raise TypeError("errors must be a tuple")
        if not all(isinstance(error, EngineError) for error in self.errors):
            raise TypeError("errors must contain only EngineError values")

        if self.success:
            if self.outcome is None:
                raise ValueError("successful result must have an outcome")
            if self.errors:
                raise ValueError("successful result must not have errors")
        else:
            if self.outcome is not None:
                raise ValueError("failed result must not have an outcome")
            if self.events:
                raise ValueError("failed result must not have events")
            if not self.errors:
                raise ValueError("failed result must have at least one error")

        if any(event.command_id != self.command_id for event in self.events):
            raise ValueError("every event must match the result command_id")
