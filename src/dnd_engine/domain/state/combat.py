from dataclasses import dataclass


@dataclass
class CombatState:
    id: str
    round: int
    order: tuple[str, ...]
    active_index: int

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

    @property
    def active_creature_id(self) -> str:
        return self.order[self.active_index]
