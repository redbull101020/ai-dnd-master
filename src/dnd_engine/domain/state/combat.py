from dataclasses import dataclass


@dataclass(frozen=True)
class CombatPosition:
    creature_id: str
    x: int
    y: int

    def __post_init__(self) -> None:
        if type(self.creature_id) is not str:
            raise TypeError("creature_id must be a str")
        if type(self.x) is not int:
            raise TypeError("x must be an int")
        if type(self.y) is not int:
            raise TypeError("y must be an int")


@dataclass
class CombatState:
    id: str
    round: int
    order: tuple[str, ...]
    active_index: int
    positions: tuple[CombatPosition, ...] = ()

    def __post_init__(self) -> None:
        if type(self.id) is not str:
            raise TypeError("id must be a str")
        if type(self.round) is not int:
            raise TypeError("round must be an int")
        if self.round < 1:
            raise ValueError("round must be at least 1")
        if type(self.order) is not tuple:
            raise TypeError("order must be a tuple")
        if not all(type(creature_id) is str for creature_id in self.order):
            raise TypeError("order must contain only str values")
        if len(self.order) == 0:
            raise ValueError("order must not be empty")
        if len(set(self.order)) != len(self.order):
            raise ValueError("order must not contain duplicate creature ids")
        if type(self.active_index) is not int:
            raise TypeError("active_index must be an int")
        if not 0 <= self.active_index < len(self.order):
            raise ValueError("active_index must be a valid index into order")
        if type(self.positions) is not tuple:
            raise TypeError("positions must be a tuple")
        if not all(
            isinstance(position, CombatPosition) for position in self.positions
        ):
            raise TypeError("positions must contain only CombatPosition values")
        position_creature_ids = [position.creature_id for position in self.positions]
        if len(position_creature_ids) != len(set(position_creature_ids)):
            raise ValueError("positions must not contain duplicate creature ids")
        if not set(position_creature_ids).issubset(self.order):
            raise ValueError(
                "every positioned creature must be present in order"
            )

    @property
    def active_creature_id(self) -> str:
        return self.order[self.active_index]
