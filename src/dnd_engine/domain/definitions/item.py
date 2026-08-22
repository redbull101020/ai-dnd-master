from dataclasses import dataclass

from dnd_engine.domain.definitions.base import Definition


@dataclass(frozen=True)
class ItemDefinition(Definition):
    name: str
