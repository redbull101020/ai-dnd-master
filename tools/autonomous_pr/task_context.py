"""Narrow, deterministic operational-v2 tracker/preflight support.

This module answers exactly one question: is the named task still a valid,
unblocked, authoritative execution target on a freshly fetched
``docs/TASK.md``? It is deliberately not a general Markdown AST/parser and
not a general Markdown AST. Public execution uses the thin tracker, durable
terminal index, exact-base input, and Task Execution Spec primitives below.

Critically: a ``task_id`` accepted here is execution input only. Neither
this module nor any function in it ever treats a task_id, or a successful
revalidation, as evidence that the user gave a separate, explicit
``AUTONOMOUS_PR`` invocation (``AGENTS.md`` "Valid invocation";
``docs/AUTONOMOUS_PR_HARNESS.md`` §3). That confirmation is the caller's
responsibility and happens outside this module entirely.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import repository, task_spec
from .model import (
    ExactBaseInput,
    ExecutionTarget,
    TaskStatus,
    TerminalRegistry,
    TerminalTask,
    ThinTracker,
    TrackerTask,
)

_TASK_ID = r"TSK-\d{4,}"

_ANY_HEADING = re.compile(r"^#{1,2}\s", re.MULTILINE)
_LEVEL_ONE_HEADING = re.compile(r"^#\s", re.MULTILINE)
_CURRENT_POSITION_HEADING = re.compile(r"^#\s+Current position\s*$", re.MULTILINE)
_OPEN_TASK_INDEX_HEADING = re.compile(r"^#\s+Open task index\s*$", re.MULTILINE)
_CURRENT_LINE = re.compile(r"^-\s*\*\*Current:\*\*\s*(.+?)\s*$", re.MULTILINE)
_DEPENDS_ON_NONE = "—"
_DEPENDS_ON_TOKEN = re.compile(rf"`({_TASK_ID})`")






def _section_after(
    text: str, heading: re.Pattern[str], boundary: re.Pattern[str] = _ANY_HEADING
) -> str:
    """Slice the text between one exact heading and the next ``boundary`` heading.

    Numbered documentation may mention the same heading text, so lookups are
    scoped to the exact unnumbered authoritative heading.
    """

    match = heading.search(text)
    if match is None:
        return ""
    start = match.end()
    next_heading = boundary.search(text, pos=start)
    end = next_heading.start() if next_heading is not None else len(text)
    return text[start:end]


def _require_single_match(
    pattern: re.Pattern[str], text: str, description: str
) -> re.Match[str] | None:
    """Return the sole match of ``pattern`` in ``text``.

    Returns ``None`` — never raises — when there is no match at all, since
    whether "no match" is itself an error differs by field (e.g. a missing
    Current pointer vs. a missing Depends on field): that decision stays
    with the caller. Raises :class:`TaskTrackerError` when more than
    one match exists: an ambiguous single-valued execution fact must fail
    closed rather than silently resolve to the first match found.
    """

    matches = list(pattern.finditer(text))
    if len(matches) > 1:
        raise TaskTrackerError(
            f"{description} is ambiguous: found {len(matches)} matches, "
            "expected at most one"
        )
    return matches[0] if matches else None
















# --------------------------------------------------------------------------
# Operational v2: thin tracker parsing, exact-base input, preflight primitives
#
# Everything below is the deterministic INPUT model for the approved,
# spec-driven v2 (``docs/AUTONOMOUS_PR_HARNESS.md`` Part II §§22, 30). It is
# wired into the public orchestrator. No full-detail v1 parser or fallback is
# present in production execution.
#
# The parser reads the v2 layout of the fixed sections below. It is a narrow
# reader like the v1 one, not a Markdown AST or a Roadmap framework, and it
# makes no semantic judgement: whether a Roadmap target is *right* was
# decided when the task became ``Current``; here it is only checked to be
# present.
# --------------------------------------------------------------------------

_OPEN_TASK_INDEX_V2_HEADER = [
    "ID",
    "Status",
    "P",
    "Size",
    "Group",
    "Roadmap target",
    "Depends on",
    "Title",
]
_TERMINAL_TASK_INDEX_HEADER = ["ID", "Status", "Evidence", "Title"]
_OPEN_STATUSES = frozenset(
    {TaskStatus.BACKLOG, TaskStatus.READY, TaskStatus.CURRENT, TaskStatus.BLOCKED}
)
_TERMINAL_STATUSES = frozenset({TaskStatus.DONE, TaskStatus.SUPERSEDED})
_PRIORITIES = frozenset({"P0", "P1", "P2", "P3"})
_SIZES = frozenset({"S", "M", "L"})
_GROUPS = frozenset(
    {"mechanics", "cross-cutting", "engineering", "documentation", "architecture"}
)
_TERMINAL_TASK_INDEX_HEADING = re.compile(r"^#\s+Terminal task index\s*$", re.MULTILINE)
_BACKTICKED = re.compile(r"`([^`]+)`")
_TABLE_SEPARATOR_CELL = re.compile(r":?-{3,}:?")
_TABLE_RULE = re.compile(r"-{3,}")
_EXACT_SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


class TaskTrackerError(Exception):
    """A v2-format ``docs/TASK.md`` is not a valid, unambiguous tracker."""


class TaskPreflightError(Exception):
    """The named task is not a valid v2 execution target at the captured SHA.

    Covers every mechanically determinable preflight failure (Harness §30):
    tracker, dependency, Roadmap-target, spec, and same-SHA facts. The caller
    ends the run ``BLOCKED``; it never edits the tracker or the spec to make
    a check pass.
    """


def parse_thin_tracker(task_queue_text: str) -> ThinTracker:
    """Parse the v2 lifecycle facts of ``docs/TASK.md``.

    Reads exactly ``# Current position`` (the ``Current`` pointer),
    ``# Open task index`` (eight columns, including ``Depends on``), and the
    durable ``# Terminal task index`` (``Done``/``Superseded`` tasks with
    Evidence). ``# Recently completed`` is a short human-readable recent
    view: it is never read here and is not lifecycle truth. Each of the three
    headings must occur exactly once, and an index section may contain only
    its table.

    Fails closed (:class:`TaskTrackerError`) on: a missing or duplicated
    heading; an unexpected table header; a malformed cell; a status outside
    the index's allowed set; a task ID appearing twice, or in both indexes;
    a self-dependency; more than one ``Current`` row; and a ``Current``
    pointer that disagrees with the index.
    """

    pointer = _parse_current_pointer(task_queue_text)
    open_tasks = tuple(
        _open_task_from_cells(cells)
        for cells in _table_rows(
            _unique_section(task_queue_text, _OPEN_TASK_INDEX_HEADING, "Open task index"),
            _OPEN_TASK_INDEX_V2_HEADER,
            "Open task index",
        )
    )
    terminal_tasks = parse_terminal_registry(task_queue_text).tasks

    all_ids = [task.task_id for task in open_tasks] + [
        task.task_id for task in terminal_tasks
    ]
    duplicated = sorted({task_id for task_id in all_ids if all_ids.count(task_id) > 1})
    if duplicated:
        raise TaskTrackerError(
            "task ID(s) appear more than once across the Open task index and "
            f"the Terminal task index: {', '.join(duplicated)}"
        )

    current_rows = [task for task in open_tasks if task.status is TaskStatus.CURRENT]
    if len(current_rows) > 1:
        raise TaskTrackerError(
            "the Open task index has more than one Current row: "
            f"{', '.join(task.task_id for task in current_rows)}"
        )
    if pointer is None and current_rows:
        raise TaskTrackerError(
            f"Current position records no Current task but {current_rows[0].task_id} "
            "is Current in the Open task index"
        )
    if pointer is not None and [task.task_id for task in current_rows] != [pointer]:
        raise TaskTrackerError(
            f"Current position records {pointer} but the Open task index does "
            "not have exactly that task as its Current row"
        )

    return ThinTracker(
        current_task_id=pointer, open_tasks=open_tasks, terminal_tasks=terminal_tasks
    )


def parse_terminal_registry(task_queue_text: str) -> TerminalRegistry:
    """Parse the durable terminal table without requiring an open-task queue.

    This pure CP-1 primitive reads only the exact ``# Terminal task index``
    section and therefore also works with the prospective TSK-0029 tracker,
    where ``Current`` and the Open task index no longer exist. It deliberately
    does not inspect task files: catalog-level terminal filtering before body
    parsing belongs to CP-2.
    """

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
    return TerminalRegistry(tasks=tasks)


def load_exact_base_input(repo: Path, task_id: str, base_sha: str) -> ExactBaseInput:
    """Read ``docs/TASK.md`` and ``docs/tasks/<task_id>.md`` at ONE exact SHA.

    ``base_sha`` is the caller-captured exact commit SHA (normally from
    :func:`.repository.fetch_and_capture_origin_main_sha`). This function
    never fetches and never resolves a symbolic ref: a branch or
    ``origin/main`` is rejected, so both reads are anchored to a commit that
    cannot move between them; the returned input carries that one SHA as
    ``base_sha``. A missing spec is reported as ``spec_text=None`` rather than an
    exception, so preflight can name it; a missing ``docs/TASK.md`` or any
    other Git failure raises :class:`.repository.RepositoryError`.
    """

    _require_exact_sha(base_sha)
    try:
        spec_path = task_spec.spec_path_for(task_id)
    except task_spec.TaskSpecError as exc:
        raise TaskPreflightError(str(exc)) from exc
    if repository.resolve_sha(repo, f"{base_sha}^{{commit}}") != base_sha:
        raise TaskPreflightError(f"{base_sha!r} is not the exact SHA of a commit")
    task_md_text = repository.read_file_at_ref(repo, base_sha, "docs/TASK.md")
    spec_text = (
        repository.read_file_at_ref(repo, base_sha, spec_path)
        if repository.file_exists_at_ref(repo, base_sha, spec_path)
        else None
    )
    return ExactBaseInput(
        base_sha=base_sha, task_md_text=task_md_text, spec_text=spec_text
    )


def preflight_execution_target(base: ExactBaseInput, task_id: str) -> ExecutionTarget:
    """Deterministic v2 preflight of ``task_id`` against one captured SHA.

    Raises :class:`TaskPreflightError` unless all of the following hold
    (Harness §30):

    - ``base.base_sha`` is an exact commit SHA (never a symbolic ref); both
      texts belong to it, as :func:`load_exact_base_input` guarantees;
    - the tracker parses (:func:`parse_thin_tracker`) and ``task_id`` is its
      authoritative ``Current`` task, with size ``S`` or ``M``;
    - the task has a non-empty Roadmap target (presence only — no semantic
      judgement of whether it is the right one, which was settled when the
      task became ``Current``);
    - every dependency is a ``Done`` row of the durable Terminal task index
      (not ``Superseded``, not still open, not merely absent, and not read
      from the bounded ``# Recently completed`` view);
    - the spec exists at ``docs/tasks/<task_id>.md``, that path's ID equals
      the H1's, and it is execution-ready
      (:func:`.task_spec.parse_task_execution_spec`), including having no
      machine-detectable unresolved placeholder or open-decision marker.

    Returns the validated :class:`.model.ExecutionTarget`, whose spec keeps the
    exact text and digest so a later step can prove it is unchanged. Success
    is execution input only, never proof of a user ``AUTONOMOUS_PR``
    invocation (Harness §3).
    """

    _require_exact_sha(base.base_sha)

    try:
        spec_path = task_spec.spec_path_for(task_id)
        tracker = parse_thin_tracker(base.task_md_text)
    except (TaskTrackerError, task_spec.TaskSpecError) as exc:
        raise TaskPreflightError(str(exc)) from exc

    if tracker.current_task_id != task_id:
        raise TaskPreflightError(
            f"{task_id} is not the authoritative Current task (Current "
            f"position records {tracker.current_task_id!r})"
        )
    task = next(row for row in tracker.open_tasks if row.task_id == task_id)
    if task.size == "L":
        raise TaskPreflightError(f"{task_id} has size L and cannot be Current")
    if task.roadmap_target == _DEPENDS_ON_NONE:
        raise TaskPreflightError(f"{task_id} has no Roadmap target")

    _require_dependencies_done_in_terminal_index(tracker, task)

    if base.spec_text is None:
        raise TaskPreflightError(
            f"{task_id} is Current but its Task Execution Spec {spec_path} does "
            f"not exist at {base.base_sha}"
        )
    try:
        spec = task_spec.parse_task_execution_spec(base.spec_text, spec_path)
    except task_spec.TaskSpecError as exc:
        raise TaskPreflightError(str(exc)) from exc

    return ExecutionTarget(base_sha=base.base_sha, task=task, spec=spec)


def _require_exact_sha(sha: str) -> None:
    if _EXACT_SHA.fullmatch(sha) is None:
        raise TaskPreflightError(
            f"{sha!r} is not an exact commit SHA (a full lowercase hex object "
            "name); a branch or symbolic ref such as origin/main is not "
            "accepted because it can move between reads"
        )


def _require_dependencies_done_in_terminal_index(
    tracker: ThinTracker, task: TrackerTask
) -> None:
    terminal = {row.task_id: row for row in tracker.terminal_tasks}
    open_ids = {row.task_id for row in tracker.open_tasks}
    for dependency in task.depends_on:
        row = terminal.get(dependency)
        if row is None:
            where = (
                "is still open"
                if dependency in open_ids
                else "is not in the Terminal task index"
            )
            raise TaskPreflightError(
                f"{task.task_id} depends on {dependency}, which {where}; "
                "authoritative Done cannot be established"
            )
        if row.status is not TaskStatus.DONE:
            raise TaskPreflightError(
                f"{task.task_id} depends on {dependency}, whose Terminal task "
                f"index status is {row.status.value}, not Done"
            )


def _unique_section(text: str, heading: re.Pattern[str], name: str) -> str:
    count = len(heading.findall(text))
    if count != 1:
        raise TaskTrackerError(f"expected exactly one '# {name}' section, found {count}")
    return _section_after(text, heading, boundary=_LEVEL_ONE_HEADING)


def _parse_current_pointer(text: str) -> str | None:
    if len(_CURRENT_POSITION_HEADING.findall(text)) != 1:
        raise TaskTrackerError("expected exactly one '# Current position' section")
    match = _require_single_match(
        _CURRENT_LINE,
        _section_after(text, _CURRENT_POSITION_HEADING, boundary=_LEVEL_ONE_HEADING),
        "the '# Current position' Current field",
    )
    if match is None:
        raise TaskTrackerError("'# Current position' has no Current field")
    value = match.group(1).strip()
    if value == _DEPENDS_ON_NONE:
        return None
    if re.fullmatch(_TASK_ID, value) is None:
        raise TaskTrackerError(
            f"the Current field {value!r} is neither '{_DEPENDS_ON_NONE}' nor a "
            "TSK-NNNN task ID"
        )
    return value


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
    return [cell.strip() for cell in line[1:-1].split("|")]


def _backticked_value(cell: str, what: str) -> str:
    match = _BACKTICKED.fullmatch(cell)
    if match is None:
        raise TaskTrackerError(f"{what} {cell!r} must be a single backtick-wrapped value")
    return match.group(1)


def _task_id_cell(cell: str) -> str:
    value = _backticked_value(cell, "task ID")
    if re.fullmatch(_TASK_ID, value) is None:
        raise TaskTrackerError(f"{value!r} is not a TSK-NNNN task ID")
    return value


def _status_cell(cell: str, allowed: frozenset[TaskStatus], task_id: str) -> TaskStatus:
    raw = _backticked_value(cell, f"{task_id} Status")
    try:
        status = TaskStatus(raw)
    except ValueError as exc:
        raise TaskTrackerError(f"{task_id} has an unrecognized Status {raw!r}") from exc
    if status not in allowed:
        raise TaskTrackerError(
            f"{task_id} Status {status.value!r} is not allowed in this index"
        )
    return status


def _required_text(cell: str, what: str, task_id: str) -> str:
    if not cell:
        raise TaskTrackerError(f"{task_id} has an empty {what}")
    return cell


def _open_task_from_cells(cells: list[str]) -> TrackerTask:
    task_id = _task_id_cell(cells[0])
    status = _status_cell(cells[1], _OPEN_STATUSES, task_id)
    priority = _backticked_value(cells[2], f"{task_id} Priority")
    size = _backticked_value(cells[3], f"{task_id} Size")
    group = _backticked_value(cells[4], f"{task_id} Group")
    for value, allowed, what in (
        (priority, _PRIORITIES, "Priority"),
        (size, _SIZES, "Size"),
        (group, _GROUPS, "Group"),
    ):
        if value not in allowed:
            raise TaskTrackerError(f"{task_id} has an unknown {what} {value!r}")
    return TrackerTask(
        task_id=task_id,
        status=status,
        priority=priority,
        size=size,
        group=group,
        roadmap_target=_required_text(cells[5], "Roadmap target", task_id),
        depends_on=_depends_on_cell(cells[6], task_id),
        title=_required_text(cells[7], "Title", task_id),
    )


def _terminal_task_from_cells(cells: list[str]) -> TerminalTask:
    task_id = _task_id_cell(cells[0])
    return TerminalTask(
        task_id=task_id,
        status=_status_cell(cells[1], _TERMINAL_STATUSES, task_id),
        evidence=_required_text(cells[2], "Evidence", task_id),
        title=_required_text(cells[3], "Title", task_id),
    )


def _depends_on_cell(cell: str, task_id: str) -> tuple[str, ...]:
    if cell == _DEPENDS_ON_NONE:
        return ()
    dependencies: list[str] = []
    for token in cell.split(","):
        token_match = _DEPENDS_ON_TOKEN.fullmatch(token.strip())
        if token_match is None:
            raise TaskTrackerError(
                f"{task_id} Depends on {cell!r} must be '{_DEPENDS_ON_NONE}' or "
                "comma-separated backtick-wrapped TSK-NNNN IDs"
            )
        dependencies.append(token_match.group(1))
    if task_id in dependencies:
        raise TaskTrackerError(f"{task_id} depends on itself")
    if len(set(dependencies)) != len(dependencies):
        raise TaskTrackerError(f"{task_id} lists a dependency more than once")
    return tuple(dependencies)
