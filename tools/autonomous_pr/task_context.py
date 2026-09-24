"""Pure terminal-registry and terminal-only closure validation.

Open task metadata lives exclusively in standalone ``docs/tasks/TSK-NNNN.md``
documents and is handled by :mod:`.task_spec` and :mod:`.catalog`.  This module
therefore reads only the permanent terminal registry in ``docs/TASK.md``; it
contains no Current/Open-index execution path or fallback.
"""

from __future__ import annotations

import re

from .model import TaskStatus, TerminalRegistry, TerminalTask

_TASK_ID = r"TSK-\d{4,}"
_LEVEL_ONE_HEADING = re.compile(r"^#\s", re.MULTILINE)
_TERMINAL_TASK_INDEX_HEADING = re.compile(
    r"^#\s+Terminal task index\s*$", re.MULTILINE
)
_TERMINAL_TASK_INDEX_HEADER = ["ID", "Status", "Evidence", "Title"]
_TERMINAL_STATUSES = frozenset({TaskStatus.DONE, TaskStatus.SUPERSEDED})
_BACKTICKED = re.compile(r"`([^`]+)`")
_TABLE_SEPARATOR_CELL = re.compile(r":?-{3,}:?")
_TABLE_RULE = re.compile(r"-{3,}")


class TaskTrackerError(Exception):
    """The permanent terminal registry is malformed or ambiguous."""


def parse_terminal_registry(
    task_queue_text: str, *, source_sha: str | None = None
) -> TerminalRegistry:
    """Parse the required durable terminal table independently of task files."""

    tasks = tuple(
        _terminal_task_from_cells(cells)
        for cells in _table_rows(
            _unique_section(
                task_queue_text, _TERMINAL_TASK_INDEX_HEADING, "Terminal task index"
            ),
            _TERMINAL_TASK_INDEX_HEADER,
            "Terminal task index",
        )
    )
    task_ids = [task.task_id for task in tasks]
    duplicated = sorted(
        {task_id for task_id in task_ids if task_ids.count(task_id) > 1}
    )
    if duplicated:
        raise TaskTrackerError(
            "task ID(s) appear more than once in the Terminal task index: "
            f"{', '.join(duplicated)}"
        )
    return TerminalRegistry(tasks=tasks, source_sha=source_sha)


def validate_terminal_only_closure(
    baseline_text: str,
    candidate_text: str,
    *,
    task_id: str,
    pr_number: str,
    title: str,
) -> None:
    """Require a closure to insert exactly one semantically correct row."""

    baseline = parse_terminal_registry(baseline_text)
    candidate = parse_terminal_registry(candidate_text)
    if any(task.task_id == task_id for task in baseline.tasks):
        raise TaskTrackerError(
            f"{task_id} was already terminal in the authoritative closure baseline"
        )
    expected = TerminalTask(
        task_id=task_id,
        status=TaskStatus.DONE,
        evidence=f"PR #{pr_number}",
        title=title,
    )
    own_rows = tuple(task for task in candidate.tasks if task.task_id == task_id)
    if own_rows != (expected,):
        raise TaskTrackerError(
            "prospective closure must add exactly one selected-task terminal "
            f"row equal to {expected!r}"
        )
    preserved = tuple(task for task in candidate.tasks if task.task_id != task_id)
    if preserved != baseline.tasks:
        raise TaskTrackerError(
            "prospective closure changed existing terminal rows, order, or evidence"
        )

    terminal_section = _unique_section(
        candidate_text, _TERMINAL_TASK_INDEX_HEADING, "Terminal task index"
    )
    matching_lines: list[str] = []
    for raw_line in terminal_section.splitlines(keepends=True):
        line = raw_line.strip()
        if not (line.startswith("|") and line.endswith("|")):
            continue
        cells = _split_cells(line)
        if len(cells) != len(_TERMINAL_TASK_INDEX_HEADER):
            continue
        try:
            parsed = _terminal_task_from_cells(cells)
        except TaskTrackerError:
            continue
        if parsed == expected:
            matching_lines.append(raw_line)
    if len(matching_lines) != 1:
        raise TaskTrackerError(
            "prospective closure must contain one identifiable selected-task "
            "terminal row"
        )

    actual_line = matching_lines[0]
    line_body = actual_line.rstrip("\r\n")
    removable_insertions = [line_body, actual_line]
    for eol in ("\n", "\r\n"):
        removable_insertions.extend((eol + line_body, eol + actual_line))
    if not any(
        fragment in candidate_text
        and candidate_text.replace(fragment, "", 1) == baseline_text
        for fragment in removable_insertions
    ):
        raise TaskTrackerError(
            "prospective closure must change docs/TASK.md only by inserting "
            "the selected task's terminal row"
        )


def _section_after(text: str, heading: re.Pattern[str]) -> str:
    match = heading.search(text)
    if match is None:
        return ""
    start = match.end()
    next_heading = _LEVEL_ONE_HEADING.search(text, pos=start)
    end = next_heading.start() if next_heading is not None else len(text)
    return text[start:end]


def _unique_section(text: str, heading: re.Pattern[str], name: str) -> str:
    count = len(heading.findall(text))
    if count != 1:
        raise TaskTrackerError(f"expected exactly one '# {name}' section, found {count}")
    return _section_after(text, heading)


def _table_rows(section: str, header: list[str], name: str) -> list[list[str]]:
    table_lines: list[str] = []
    for raw in section.splitlines():
        line = raw.strip()
        if not line or _TABLE_RULE.fullmatch(line):
            continue
        if not (line.startswith("|") and line.endswith("|")):
            raise TaskTrackerError(f"'{name}' may contain only its table; found {line!r}")
        table_lines.append(line)
    if len(table_lines) < 2:
        raise TaskTrackerError(f"'{name}' has no table header and separator")
    found_header = _split_cells(table_lines[0])
    if found_header != header:
        raise TaskTrackerError(
            f"'{name}' table header must be {header}, found {found_header}"
        )
    separator = _split_cells(table_lines[1])
    if len(separator) != len(header) or not all(
        _TABLE_SEPARATOR_CELL.fullmatch(cell) for cell in separator
    ):
        raise TaskTrackerError(f"'{name}' table has no valid separator row")
    rows: list[list[str]] = []
    for line in table_lines[2:]:
        cells = _split_cells(line)
        if len(cells) != len(header):
            raise TaskTrackerError(
                f"'{name}' row has {len(cells)} cells, expected {len(header)}: {line!r}"
            )
        rows.append(cells)
    return rows


def _split_cells(line: str) -> list[str]:
    cells: list[str] = []
    cell: list[str] = []
    index = 1
    while index < len(line) - 1:
        character = line[index]
        if character == "\\" and index + 1 < len(line) - 1 and line[index + 1] == "|":
            cell.append("|")
            index += 2
            continue
        if character == "|":
            cells.append("".join(cell).strip())
            cell = []
        else:
            cell.append(character)
        index += 1
    cells.append("".join(cell).strip())
    return cells


def _backticked_value(cell: str, what: str) -> str:
    match = _BACKTICKED.fullmatch(cell)
    if match is None:
        raise TaskTrackerError(f"{what} {cell!r} must be a single backtick-wrapped value")
    return match.group(1)


def _terminal_task_from_cells(cells: list[str]) -> TerminalTask:
    task_id = _backticked_value(cells[0], "task ID")
    if re.fullmatch(_TASK_ID, task_id) is None:
        raise TaskTrackerError(f"{task_id!r} is not a TSK-NNNN task ID")
    raw_status = _backticked_value(cells[1], f"{task_id} Status")
    try:
        status = TaskStatus(raw_status)
    except ValueError as exc:
        raise TaskTrackerError(
            f"{task_id} has an unrecognized Status {raw_status!r}"
        ) from exc
    if status not in _TERMINAL_STATUSES:
        raise TaskTrackerError(
            f"{task_id} Status {status.value!r} is not allowed in this index"
        )
    evidence = cells[2]
    title = cells[3]
    if not evidence:
        raise TaskTrackerError(f"{task_id} has an empty Evidence")
    if not title:
        raise TaskTrackerError(f"{task_id} has an empty Title")
    return TerminalTask(task_id, status, evidence, title)
