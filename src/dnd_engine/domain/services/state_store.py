from typing import Protocol

from dnd_engine.domain.state.snapshot import StateSnapshot


class StateStoreError(Exception):
    """Stable boundary error for State Store failures."""


class StateNotFoundError(StateStoreError):
    """Raised when the requested campaign has no persisted state snapshot."""


class InvalidStateSnapshotError(StateStoreError):
    """Raised when persisted or supplied snapshot data violates the contract."""


class StateStore(Protocol):
    def load(self, campaign_id: str) -> StateSnapshot: ...

    def save(self, snapshot: StateSnapshot) -> None: ...
