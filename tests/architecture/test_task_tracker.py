import re
from pathlib import Path

import pytest

from tools.autonomous_pr.model import TaskStatus
from tools.autonomous_pr.task_context import parse_thin_tracker
from tools.autonomous_pr.task_spec import (
    TaskSpecError,
    parse_task_execution_spec,
    spec_path_for,
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


def _assert_ready_and_current_specs(text: str, root: Path) -> None:
    tracker = _tracker(text)
    for task in tracker.open_tasks:
        if task.status not in {TaskStatus.READY, TaskStatus.CURRENT}:
            continue
        spec_rel_path = spec_path_for(task.task_id)
        path = root / spec_rel_path
        assert path.is_file(), f"{task.task_id} has no Task Execution Spec"
        spec = parse_task_execution_spec(
            path.read_text(encoding="utf-8"),
            spec_rel_path,
        )
        assert spec.task_id == task.task_id


def _synthetic_tracker(
    *open_rows: str,
    current: str = "—",
    next_tasks: str = "—",
    next_free_id: str = "TSK-0100",
) -> str:
    rows = "\n".join(open_rows)
    return f"""# Current position

- **Current:** {current}
- **Next:** {next_tasks}
- **Hard blockers:** —
- **Next free ID:** {next_free_id}

# Open task index

| ID | Status | P | Size | Group | Roadmap target | Depends on | Title |
| --- | --- | --- | --- | --- | --- | --- | --- |
{rows}

# Terminal task index

| ID | Status | Evidence | Title |
| --- | --- | --- | --- |
| `TSK-0027` | `Done` | PR #104 | Synthetic completed dependency |
"""


def _synthetic_executable_tracker(status: TaskStatus) -> str:
    row = (
        f"| `TSK-0030` | `{status.value}` | `P2` | `S` | `engineering` | "
        "Test target | `TSK-0027` | Synthetic executable task |"
    )
    return _synthetic_tracker(
        row,
        current="TSK-0030" if status is TaskStatus.CURRENT else "—",
    )


def _synthetic_execution_ready_spec(task_id: str = "TSK-0030") -> str:
    return f"""# {task_id} — Synthetic executable task

## Goal

Exercise the repository architecture invariant.

## Context / References

Use the approved v2 harness contract.

## Scope

- synthetic architecture-test scope

## Out of scope

- production changes

## Approved implementation approach

Use one deterministic synthetic checkpoint.

## Acceptance criteria

- the synthetic invariant is exercised

## Execution checkpoints

### CP-1 — Synthetic checkpoint
- Objective: Exercise the invariant.
- Required result: The fixture is accepted.
- Constraints: Do not change production files.
- Verification: ["python", "-m", "pytest", "tests/architecture"]
- Review focus: Spec identity and execution readiness.

## Full verification

["python", "-m", "pytest", "tests/architecture"]

## Known constraints / edge cases

This fixture is not an allocated repository task.
"""


def test_live_task_tracker_is_valid_v2_thin_tracker() -> None:
    tracker = _tracker()

    current_rows = [
        task for task in tracker.open_tasks if task.status is TaskStatus.CURRENT
    ]
    assert len(current_rows) <= 1
    assert tracker.current_task_id == (
        current_rows[0].task_id if current_rows else None
    )
    assert all(
        task.status
        in {
            TaskStatus.BACKLOG,
            TaskStatus.READY,
            TaskStatus.CURRENT,
            TaskStatus.BLOCKED,
        }
        for task in tracker.open_tasks
    )
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
    assert terminal["TSK-0028"].status is TaskStatus.DONE
    assert all(task.evidence.strip() for task in tracker.terminal_tasks)
    _assert_dependency_invariants(text)


def test_backlog_task_may_depend_on_an_existing_open_task() -> None:
    synthetic = _synthetic_tracker(
        (
            "| `TSK-0030` | `Backlog` | `P3` | `S` | `engineering` | "
            "Test target | `TSK-0031` | Synthetic dependent task |"
        ),
        (
            "| `TSK-0031` | `Backlog` | `P3` | `S` | `engineering` | "
            "Test target | — | Synthetic open dependency |"
        ),
    )

    tracker = _tracker(synthetic)
    backlog = next(task for task in tracker.open_tasks if task.task_id == "TSK-0030")
    assert backlog.status is TaskStatus.BACKLOG
    assert backlog.depends_on == ("TSK-0031",)
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

    expected_current = (
        [] if tracker.current_task_id is None else [tracker.current_task_id]
    )
    assert _queue_order(TASK_MD.read_text(encoding="utf-8")) == [
        *expected_current,
        *next_ids,
    ]


def test_open_index_row_order_does_not_define_execution_order() -> None:
    current_row = (
        "| `TSK-0030` | `Current` | `P1` | `S` | `engineering` | "
        "Test target | `TSK-0027` | Synthetic current task |"
    )
    ready_row = (
        "| `TSK-0031` | `Ready` | `P2` | `S` | `engineering` | "
        "Test target | `TSK-0027` | Synthetic ready task |"
    )
    backlog_row = (
        "| `TSK-0032` | `Backlog` | `P3` | `S` | `engineering` | "
        "Test target | — | Synthetic backlog task |"
    )
    synthetic = _synthetic_tracker(
        current_row,
        ready_row,
        backlog_row,
        current="TSK-0030",
        next_tasks="TSK-0031",
    )
    lines = synthetic.splitlines()
    ready_index = next(
        i for i, line in enumerate(lines) if line.startswith("| `TSK-0031`")
    )
    backlog_index = next(
        i for i, line in enumerate(lines) if line.startswith("| `TSK-0032`")
    )
    lines[ready_index], lines[backlog_index] = lines[backlog_index], lines[ready_index]
    reordered = "\n".join(lines) + "\n"

    assert [task.task_id for task in _tracker(reordered).open_tasks] == [
        "TSK-0030",
        "TSK-0032",
        "TSK-0031",
    ]
    assert _queue_order(reordered) == _queue_order(synthetic) == [
        "TSK-0030",
        "TSK-0031",
    ]


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


def test_every_ready_or_current_task_has_execution_ready_spec() -> None:
    _assert_ready_and_current_specs(TASK_MD.read_text(encoding="utf-8"), ROOT)


@pytest.mark.parametrize("status", [TaskStatus.READY, TaskStatus.CURRENT])
def test_executable_task_with_matching_execution_ready_spec_passes(
    tmp_path: Path, status: TaskStatus
) -> None:
    spec_rel_path = spec_path_for("TSK-0030")
    path = tmp_path / spec_rel_path
    path.parent.mkdir(parents=True)
    path.write_text(_synthetic_execution_ready_spec(), encoding="utf-8")

    _assert_ready_and_current_specs(_synthetic_executable_tracker(status), tmp_path)


def test_executable_task_without_spec_fails(tmp_path: Path) -> None:
    with pytest.raises(AssertionError, match="TSK-0030 has no Task Execution Spec"):
        _assert_ready_and_current_specs(
            _synthetic_executable_tracker(TaskStatus.CURRENT), tmp_path
        )


def test_executable_task_with_malformed_spec_fails(tmp_path: Path) -> None:
    spec_rel_path = spec_path_for("TSK-0030")
    path = tmp_path / spec_rel_path
    path.parent.mkdir(parents=True)
    path.write_text("# TSK-0030 — malformed\n", encoding="utf-8")

    with pytest.raises(TaskSpecError):
        _assert_ready_and_current_specs(
            _synthetic_executable_tracker(TaskStatus.READY), tmp_path
        )
