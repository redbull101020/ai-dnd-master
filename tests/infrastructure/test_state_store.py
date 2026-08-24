import json
import os
from pathlib import Path

import pytest

from dnd_engine.domain.services.state_store import (
    InvalidStateSnapshotError,
    StateNotFoundError,
    StateStoreError,
)
from dnd_engine.domain.state.campaign import CampaignState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.infrastructure.filesystem import state_store as state_store_module
from dnd_engine.infrastructure.filesystem.state_store import FilesystemStateStore


def snapshot(
    *,
    campaign_id: str = "campaign_001",
    ruleset_version: str = "5.2.1",
    current_hp: int = 7,
    definition_id: str = "goblin",
) -> StateSnapshot:
    return StateSnapshot(
        campaign=CampaignState(campaign_id, "dnd_5e", ruleset_version),
        creatures=(
            CreatureState(
                id="monster_001",
                definition_id=definition_id,
                ability_scores=AbilityScores(8, 14, 10, 10, 8, 8),
                current_hp=current_hp,
                max_hp=7,
            ),
        ),
    )


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def valid_data() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "campaignId": "campaign_001",
        "state": {
            "campaign": {
                "id": "campaign_001",
                "rulesetId": "dnd_5e",
                "rulesetVersion": "5.2.1",
            },
            "creatures": [],
        },
    }


def test_state_store_errors_have_stable_hierarchy() -> None:
    assert issubclass(StateNotFoundError, StateStoreError)
    assert issubclass(InvalidStateSnapshotError, StateStoreError)


def test_save_load_round_trip_and_exact_location(tmp_path: Path) -> None:
    store = FilesystemStateStore(tmp_path)
    original = snapshot()

    store.save(original)

    state_path = tmp_path / "campaign_001" / "state.json"
    assert state_path.is_file()
    assert store.load("campaign_001") == original
    serialized = state_path.read_text(encoding="utf-8")
    assert serialized.endswith("\n")
    assert json.loads(serialized)["schemaVersion"] == 1


def test_missing_state_raises_not_found(tmp_path: Path) -> None:
    with pytest.raises(StateNotFoundError):
        FilesystemStateStore(tmp_path).load("campaign_001")


@pytest.mark.parametrize("contents", ["{", "not json", ""])
def test_malformed_json_raises_invalid_snapshot(
    tmp_path: Path,
    contents: str,
) -> None:
    state_path = tmp_path / "campaign_001" / "state.json"
    state_path.parent.mkdir()
    state_path.write_text(contents, encoding="utf-8")

    with pytest.raises(InvalidStateSnapshotError):
        FilesystemStateStore(tmp_path).load("campaign_001")


def test_invalid_utf8_raises_invalid_state_snapshot(tmp_path: Path) -> None:
    state_path = tmp_path / "campaign_001" / "state.json"
    state_path.parent.mkdir()
    state_path.write_bytes(b"\xff\xfe")

    with pytest.raises(InvalidStateSnapshotError) as caught:
        FilesystemStateStore(tmp_path).load("campaign_001")

    assert isinstance(caught.value.__cause__, UnicodeDecodeError)


def test_invalid_snapshot_json_raises_invalid_snapshot(tmp_path: Path) -> None:
    data = valid_data()
    del data["state"]
    write_json(tmp_path / "campaign_001" / "state.json", data)

    with pytest.raises(InvalidStateSnapshotError):
        FilesystemStateStore(tmp_path).load("campaign_001")


def test_unsupported_schema_version_raises_invalid_snapshot(tmp_path: Path) -> None:
    data = valid_data()
    data["schemaVersion"] = 2
    write_json(tmp_path / "campaign_001" / "state.json", data)

    with pytest.raises(InvalidStateSnapshotError):
        FilesystemStateStore(tmp_path).load("campaign_001")


def test_requested_campaign_id_mismatch_raises_invalid_snapshot(tmp_path: Path) -> None:
    data = valid_data()
    data["campaignId"] = "campaign_002"
    data["state"]["campaign"]["id"] = "campaign_002"  # type: ignore[index]
    write_json(tmp_path / "campaign_001" / "state.json", data)

    with pytest.raises(InvalidStateSnapshotError):
        FilesystemStateStore(tmp_path).load("campaign_001")


def test_utf8_data_survives_save_and_load(tmp_path: Path) -> None:
    original = snapshot(
        ruleset_version="версия-один",
        definition_id="гоблин",
    )
    store = FilesystemStateStore(tmp_path)

    store.save(original)

    state_path = tmp_path / "campaign_001" / "state.json"
    serialized = state_path.read_text(encoding="utf-8")
    assert "версия-один" in serialized
    assert "гоблин" in serialized
    assert "\\u" not in serialized
    assert store.load("campaign_001") == original


def test_save_overwrites_existing_valid_snapshot(tmp_path: Path) -> None:
    store = FilesystemStateStore(tmp_path)
    store.save(snapshot(current_hp=7))

    store.save(snapshot(current_hp=3))

    assert store.load("campaign_001").creatures[0].current_hp == 3


def test_save_leaves_unrelated_and_event_files_unchanged(tmp_path: Path) -> None:
    campaign_directory = tmp_path / "campaign_001"
    events_path = campaign_directory / "events" / "events.jsonl"
    unrelated_path = campaign_directory / "notes.txt"
    events_bytes = b'{"eventId":"event_000001"}\n'
    events_path.parent.mkdir(parents=True)
    events_path.write_bytes(events_bytes)
    unrelated_path.write_text("keep me", encoding="utf-8")

    FilesystemStateStore(tmp_path).save(snapshot())

    assert events_path.read_bytes() == events_bytes
    assert unrelated_path.read_text(encoding="utf-8") == "keep me"
    assert sorted(
        path.relative_to(campaign_directory).as_posix()
        for path in campaign_directory.rglob("*")
        if path.is_file()
    ) == ["events/events.jsonl", "notes.txt", "state.json"]


def test_save_does_not_create_event_store_artifacts(tmp_path: Path) -> None:
    FilesystemStateStore(tmp_path).save(snapshot())

    campaign_directory = tmp_path / "campaign_001"
    assert not (campaign_directory / "events.jsonl").exists()
    assert not (campaign_directory / "events").exists()


def test_load_io_error_uses_stable_state_store_boundary(tmp_path: Path) -> None:
    state_path = tmp_path / "campaign_001" / "state.json"
    state_path.mkdir(parents=True)

    with pytest.raises(StateStoreError) as caught:
        FilesystemStateStore(tmp_path).load("campaign_001")

    assert not isinstance(caught.value, StateNotFoundError)
    assert not isinstance(caught.value, InvalidStateSnapshotError)


def test_save_io_error_uses_stable_state_store_boundary(tmp_path: Path) -> None:
    root_file = tmp_path / "campaigns"
    root_file.write_text("not a directory", encoding="utf-8")

    with pytest.raises(StateStoreError):
        FilesystemStateStore(root_file).save(snapshot())


def test_atomic_save_uses_os_replace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[Path, Path]] = []
    real_replace = os.replace

    def recording_replace(source: Path, destination: Path) -> None:
        calls.append((Path(source), Path(destination)))
        real_replace(source, destination)

    monkeypatch.setattr(state_store_module.os, "replace", recording_replace)

    FilesystemStateStore(tmp_path).save(snapshot())

    assert len(calls) == 1
    temporary_path, state_path = calls[0]
    assert temporary_path.parent == state_path.parent
    assert state_path == tmp_path / "campaign_001" / "state.json"


def test_failure_before_replace_leaves_old_state_and_cleans_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FilesystemStateStore(tmp_path)
    store.save(snapshot(current_hp=7))
    state_path = tmp_path / "campaign_001" / "state.json"
    old_contents = state_path.read_bytes()

    def failing_fdopen(*args: object, **kwargs: object) -> object:
        raise OSError("simulated write setup failure")

    monkeypatch.setattr(state_store_module.os, "fdopen", failing_fdopen)

    with pytest.raises(StateStoreError):
        store.save(snapshot(current_hp=3))

    assert state_path.read_bytes() == old_contents
    assert list(state_path.parent.glob(".state-*.tmp")) == []


def test_replace_failure_leaves_old_state_and_cleans_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FilesystemStateStore(tmp_path)
    store.save(snapshot(current_hp=7))
    state_path = tmp_path / "campaign_001" / "state.json"
    old_contents = state_path.read_bytes()

    def failing_replace(source: Path, destination: Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(state_store_module.os, "replace", failing_replace)

    with pytest.raises(StateStoreError):
        store.save(snapshot(current_hp=3))

    assert state_path.read_bytes() == old_contents
    assert list(state_path.parent.glob(".state-*.tmp")) == []


@pytest.mark.parametrize("campaign_id", ["../outside", "nested/campaign", ".."])
def test_campaign_path_cannot_escape_or_add_levels(
    tmp_path: Path,
    campaign_id: str,
) -> None:
    store = FilesystemStateStore(tmp_path)

    with pytest.raises(StateStoreError):
        store.load(campaign_id)

    assert not (tmp_path.parent / "outside" / "state.json").exists()


def test_external_state_symlink_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaign_directory = tmp_path / "campaign_001"
    campaign_directory.mkdir()
    state_path = campaign_directory / "state.json"
    external_state_path = tmp_path.parent / f"{tmp_path.name}-external-state.json"
    write_json(external_state_path, valid_data())

    try:
        state_path.symlink_to(external_state_path)
    except (NotImplementedError, OSError):
        real_resolve = Path.resolve

        def resolve_external_state(
            path: Path,
            *args: object,
            **kwargs: object,
        ) -> Path:
            if path == state_path:
                return external_state_path
            return real_resolve(path, *args, **kwargs)

        monkeypatch.setattr(Path, "resolve", resolve_external_state)

    with pytest.raises(StateStoreError):
        FilesystemStateStore(tmp_path).load("campaign_001")


def test_invalid_campaign_path_uses_state_store_error_boundary(
    tmp_path: Path,
) -> None:
    with pytest.raises(StateStoreError) as caught:
        FilesystemStateStore(tmp_path).load("bad\0id")

    assert not isinstance(caught.value, ValueError)
