import re
from pathlib import Path

import pytest

from tools.autonomous_pr.model import ExactBaseInput
from tools.autonomous_pr.model import TaskStatus
from tools.autonomous_pr.task_context import (
    TaskPreflightError,
    parse_thin_tracker,
    preflight_execution_target,
)


ROOT = Path(__file__).resolve().parents[2]
TASK_MD = ROOT / "docs" / "TASK.md"
POSITION_FIELD = re.compile(r"^- \*\*(Current|Next|Next free ID):\*\*\s*(.+)$")
TASK_ID = re.compile(r"^TSK-(\d{4,})$")


def _tracker(text: str | None = None):
    return parse_thin_tracker(
        TASK_MD.read_text(encoding="utf-8") if text is None else text
    )


def _position_fields(text: str | None = None) -> dict[str, str]:
    fields: dict[str, str] = {}
    source = TASK_MD.read_text(encoding="utf-8") if text is None else text
    for line in source.splitlines():
        match = POSITION_FIELD.match(line)
        if match is not None:
            fields[match.group(1)] = match.group(2).strip()
    return fields


def _next_ids(fields: dict[str, str]) -> list[str]:
    if fields["Next"] == "—":
        return []
    return [item.strip().strip("`") for item in fields["Next"].split("→")]


def _queue_order(text: str) -> list[str]:
    fields = _position_fields(text)
    current = [] if fields["Current"] == "—" else [fields["Current"]]
    return [*current, *_next_ids(fields)]


def _assert_dependency_invariants(text: str) -> None:
    tracker = _tracker(text)
    open_by_id = {task.task_id: task for task in tracker.open_tasks}
    terminal_by_id = {task.task_id: task for task in tracker.terminal_tasks}
    known_ids = open_by_id.keys() | terminal_by_id.keys()

    for task in tracker.open_tasks:
        for dependency in task.depends_on:
            assert dependency in known_ids
            if task.status in {TaskStatus.READY, TaskStatus.CURRENT}:
                assert terminal_by_id[dependency].status is TaskStatus.DONE


def test_live_task_tracker_is_valid_v2_thin_tracker() -> None:
    tracker = _tracker()

    assert tracker.current_task_id == "TSK-0028"
    assert {task.task_id for task in tracker.open_tasks} == {"TSK-0023", "TSK-0028"}
    assert all(
        task.status in {TaskStatus.DONE, TaskStatus.SUPERSEDED}
        for task in tracker.terminal_tasks
    )
    assert "# Open task details" not in TASK_MD.read_text(encoding="utf-8")


def test_terminal_history_is_durable_and_dependency_complete() -> None:
    text = TASK_MD.read_text(encoding="utf-8")
    tracker = _tracker()
    terminal = {task.task_id: task for task in tracker.terminal_tasks}

    assert terminal["TSK-0005"].status is TaskStatus.SUPERSEDED
    assert terminal["TSK-0022"].status is TaskStatus.DONE
    assert terminal["TSK-0027"].status is TaskStatus.DONE
    assert all(task.evidence.strip() for task in tracker.terminal_tasks)
    _assert_dependency_invariants(text)


def test_backlog_task_may_depend_on_an_existing_open_task() -> None:
    text = TASK_MD.read_text(encoding="utf-8")
    synthetic = text.replace(
        "| — | Opportunity Attack / Reaction continuation |",
        "| `TSK-0028` | Opportunity Attack / Reaction continuation |",
        1,
    )
    assert synthetic != text

    tracker = _tracker(synthetic)
    backlog = next(task for task in tracker.open_tasks if task.task_id == "TSK-0023")
    assert backlog.status is TaskStatus.BACKLOG
    assert backlog.depends_on == ("TSK-0028",)
    _assert_dependency_invariants(synthetic)


def test_current_position_preserves_thin_tracker_queue_invariants() -> None:
    tracker = _tracker()
    fields = _position_fields()

    assert {"Current", "Next", "Next free ID"} <= fields.keys()
    next_ids = _next_ids(fields)
    assert len(next_ids) <= 5
    assert len(next_ids) == len(set(next_ids))

    open_by_id = {task.task_id: task for task in tracker.open_tasks}
    assert all(task_id in open_by_id for task_id in next_ids)
    assert all(open_by_id[task_id].status is TaskStatus.READY for task_id in next_ids)

    assert _queue_order(TASK_MD.read_text(encoding="utf-8")) == [
        tracker.current_task_id,
        *next_ids,
    ]


def test_open_index_row_order_does_not_define_execution_order() -> None:
    text = TASK_MD.read_text(encoding="utf-8")
    lines = text.splitlines()
    current_index = next(i for i, line in enumerate(lines) if line.startswith("| `TSK-0028`"))
    backlog_index = next(i for i, line in enumerate(lines) if line.startswith("| `TSK-0023`"))
    lines[current_index], lines[backlog_index] = lines[backlog_index], lines[current_index]
    reordered = "\n".join(lines) + "\n"

    assert [task.task_id for task in _tracker(reordered).open_tasks] == [
        "TSK-0023",
        "TSK-0028",
    ]
    assert _queue_order(reordered) == _queue_order(text) == ["TSK-0028"]


def test_next_free_id_exceeds_every_allocated_thin_tracker_id() -> None:
    tracker = _tracker()
    next_free = _position_fields()["Next free ID"]
    match = TASK_ID.fullmatch(next_free)
    assert match is not None

    allocated = [task.task_id for task in tracker.open_tasks]
    allocated.extend(task.task_id for task in tracker.terminal_tasks)
    allocated_numbers = []
    for task_id in allocated:
        allocated_match = TASK_ID.fullmatch(task_id)
        assert allocated_match is not None
        allocated_numbers.append(int(allocated_match.group(1)))
    assert int(match.group(1)) > max(allocated_numbers)


def test_live_preclosure_tsk_0028_without_spec_blocks_v2_preflight() -> None:
    base = ExactBaseInput(
        base_sha="a" * 40,
        task_md_text=TASK_MD.read_text(encoding="utf-8"),
        spec_text=None,
    )

    with pytest.raises(
        TaskPreflightError, match="docs/tasks/TSK-0028.md does not exist"
    ):
        preflight_execution_target(base, "TSK-0028")
