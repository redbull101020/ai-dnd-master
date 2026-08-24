import json
import os
import tempfile
from pathlib import Path

from dnd_engine.domain.services.state_store import (
    InvalidStateSnapshotError,
    StateNotFoundError,
    StateStoreError,
)
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.infrastructure.persistence.json.state_serializer import (
    StateSerializer,
)


class FilesystemStateStore:
    def __init__(self, root: Path) -> None:
        if not isinstance(root, Path):
            raise TypeError("root must be a Path")
        self._root = root

    def load(self, campaign_id: str) -> StateSnapshot:
        state_path = self._state_path(campaign_id)
        try:
            serialized = state_path.read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise StateNotFoundError(
                f"state snapshot not found for campaign {campaign_id!r}"
            ) from error
        except UnicodeDecodeError as error:
            raise InvalidStateSnapshotError(
                f"invalid UTF-8 state snapshot for campaign {campaign_id!r}"
            ) from error
        except OSError as error:
            raise StateStoreError(
                f"failed to read state snapshot for campaign {campaign_id!r}"
            ) from error

        try:
            data = json.loads(serialized)
            snapshot = StateSerializer.deserialize(data)
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise InvalidStateSnapshotError(
                f"invalid state snapshot for campaign {campaign_id!r}"
            ) from error

        if snapshot.campaign.id != campaign_id:
            raise InvalidStateSnapshotError(
                "requested campaign ID does not match the persisted snapshot"
            )
        return snapshot

    def save(self, snapshot: StateSnapshot) -> None:
        try:
            data = StateSerializer.serialize(snapshot)
            serialized = json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ) + "\n"
        except (TypeError, ValueError) as error:
            raise InvalidStateSnapshotError("invalid state snapshot") from error

        state_path = self._state_path(snapshot.campaign.id)
        campaign_directory = state_path.parent
        try:
            campaign_directory.mkdir(parents=True, exist_ok=True)
            self._atomic_replace(state_path, serialized)
        except OSError as error:
            raise StateStoreError(
                f"failed to save state snapshot for campaign {snapshot.campaign.id!r}"
            ) from error

    def _state_path(self, campaign_id: str) -> Path:
        if type(campaign_id) is not str:
            raise StateStoreError("campaign_id must be a str")
        try:
            root = self._root.resolve()
            campaign_directory = (root / campaign_id).resolve()
        except (OSError, ValueError, RuntimeError) as error:
            raise StateStoreError("failed to resolve campaign state path") from error
        if campaign_directory.parent != root:
            raise StateStoreError(
                "campaign_id must identify a direct child of the State Store root"
            )

        state_path = campaign_directory / "state.json"
        try:
            resolved_state_path = state_path.resolve()
        except (OSError, ValueError, RuntimeError) as error:
            raise StateStoreError("failed to resolve campaign state path") from error
        if resolved_state_path.parent != campaign_directory:
            raise StateStoreError(
                "state.json must remain inside the resolved campaign directory"
            )
        return state_path

    @staticmethod
    def _atomic_replace(state_path: Path, serialized: str) -> None:
        descriptor: int | None = None
        temporary_path: Path | None = None
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                dir=state_path.parent,
                prefix=".state-",
                suffix=".tmp",
            )
            temporary_path = Path(temporary_name)
            stream = os.fdopen(
                descriptor,
                mode="w",
                encoding="utf-8",
                newline="\n",
            )
            descriptor = None
            with stream:
                stream.write(serialized)
            os.replace(temporary_path, state_path)
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass
