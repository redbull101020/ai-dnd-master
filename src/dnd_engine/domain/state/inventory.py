from dataclasses import dataclass


@dataclass
class InventoryItemState:
    id: str
    definition_id: str

    def __post_init__(self) -> None:
        if type(self.id) is not str:
            raise TypeError("id must be a str")
        if type(self.definition_id) is not str:
            raise TypeError("definition_id must be a str")


@dataclass
class InventoryState:
    owner_id: str
    items: tuple[InventoryItemState, ...]

    def __post_init__(self) -> None:
        if type(self.owner_id) is not str:
            raise TypeError("owner_id must be a str")
        if type(self.items) is not tuple:
            raise TypeError("items must be a tuple")
        if not all(isinstance(item, InventoryItemState) for item in self.items):
            raise TypeError("items must contain only InventoryItemState values")
