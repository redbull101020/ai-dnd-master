"""Pure deterministic task catalog and selector for TSK-0029 CP-2.

Git access belongs to :mod:`.repository`. This module consumes immutable file
records and terminal facts already read from one exact commit; it never reads
the filesystem, invokes Git, creates a branch, calls an agent, or writes a PR.
It resolves exactly one explicit ID or ``NEXT`` and is not a queue/scheduler.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from .model import (
    ApprovedTaskDocument,
    DraftTaskDocument,
    NoEligibleTask,
    SelectedTask,
    TaskCatalog,
    TaskFileRecord,
    TaskSelectionMode,
    TaskSelectionReason,
    TaskSelectionResult,
    TaskStatus,
    TerminalRegistry,
    TerminalTask,
)
from .task_spec import TaskSpecError, parse_task_document

_EXACT_SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
_TASK_PATH = re.compile(r"docs/tasks/(TSK-\d{4,})\.md")
_TASK_ID = re.compile(r"TSK-\d{4,}")
_PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


class TaskCatalogError(Exception):
    """The snapshot catalog or its dependency graph is invalid."""


class TaskSelectionError(Exception):
    """An explicit selector is missing, invalid, or not executable."""


def build_task_catalog(
    source_sha: str,
    records: Sequence[TaskFileRecord],
    terminal: TerminalRegistry,
) -> TaskCatalog:
    """Validate nonterminal task files and their dependency graph.

    Terminal IDs are identified from canonical paths and excluded before any
    document body is parsed. Thus a retained terminal file may use a legacy
    schema or be malformed without becoming executable again. Every remaining
    envelope is parsed; approved documents additionally undergo the complete
    execution-readiness validation owned by :func:`parse_task_document`.
    """

    if _EXACT_SHA.fullmatch(source_sha) is None:
        raise TaskCatalogError(f"{source_sha!r} is not an exact commit SHA")
    if terminal.source_sha != source_sha:
        raise TaskCatalogError(
            "terminal facts and task-file records must belong to the same "
            f"captured snapshot {source_sha}; terminal source is "
            f"{terminal.source_sha!r}"
        )

    terminal_by_id = _terminal_by_id(terminal)
    records_by_id: dict[str, TaskFileRecord] = {}
    for record in sorted(records, key=lambda item: item.path):
        if record.source_sha != source_sha:
            raise TaskCatalogError(
                f"{record.path} belongs to {record.source_sha}, not captured "
                f"snapshot {source_sha}"
            )
        match = _TASK_PATH.fullmatch(record.path)
        if match is None:
            raise TaskCatalogError(
                f"tracked task path {record.path!r} is not canonical "
                "docs/tasks/TSK-NNNN.md"
            )
        task_id = match.group(1)
        if task_id in records_by_id:
            raise TaskCatalogError(f"catalog contains duplicate identity {task_id}")
        records_by_id[task_id] = record

    documents: dict[str, DraftTaskDocument | ApprovedTaskDocument] = {}
    exclusions: list[TaskSelectionReason] = []
    for task_id, record in sorted(records_by_id.items(), key=lambda item: _id_number(item[0])):
        terminal_task = terminal_by_id.get(task_id)
        if terminal_task is not None:
            exclusions.append(
                TaskSelectionReason(
                    task_id=task_id,
                    reason=f"terminal status is {terminal_task.status.value}",
                )
            )
            continue
        try:
            document = parse_task_document(record.text, record.path)
        except TaskSpecError as exc:
            raise TaskCatalogError(f"invalid task document {record.path}: {exc}") from exc
        documents[task_id] = document

    _validate_dependencies(documents, terminal_by_id)
    _reject_dependency_cycles(documents)

    return TaskCatalog(
        source_sha=source_sha,
        documents=tuple(
            documents[task_id]
            for task_id in sorted(documents, key=_id_number)
        ),
        terminal_tasks=tuple(
            sorted(terminal.tasks, key=lambda task: _id_number(task.task_id))
        ),
        exclusions=tuple(exclusions),
    )


def select_task(catalog: TaskCatalog, selector: str | None) -> TaskSelectionResult:
    """Resolve one explicit ID or ``NEXT`` without fallback or side effects."""

    if selector is None or not selector.strip():
        raise TaskSelectionError("a task selector is required; NEXT is never implicit")
    if selector == "NEXT":
        return _select_next(catalog)
    if _TASK_ID.fullmatch(selector) is None:
        raise TaskSelectionError(
            f"selector {selector!r} must be literal 'NEXT' or a TSK-NNNN ID"
        )
    return _select_explicit(catalog, selector)


def resolve_task_selection(
    source_sha: str,
    records: Sequence[TaskFileRecord],
    terminal: TerminalRegistry,
    selector: str | None,
) -> TaskSelectionResult:
    """Convenience composition of the two pure CP-2 operations."""

    return select_task(build_task_catalog(source_sha, records, terminal), selector)


def _terminal_by_id(terminal: TerminalRegistry) -> dict[str, TerminalTask]:
    result: dict[str, TerminalTask] = {}
    for task in terminal.tasks:
        if task.status not in (TaskStatus.DONE, TaskStatus.SUPERSEDED):
            raise TaskCatalogError(
                f"terminal record {task.task_id} has nonterminal status "
                f"{task.status.value}"
            )
        if task.task_id in result:
            raise TaskCatalogError(
                f"terminal registry contains duplicate identity {task.task_id}"
            )
        result[task.task_id] = task
    return result


def _validate_dependencies(
    documents: dict[str, DraftTaskDocument | ApprovedTaskDocument],
    terminal_by_id: dict[str, TerminalTask],
) -> None:
    known_ids = set(documents) | set(terminal_by_id)
    for task_id, document in documents.items():
        for dependency in document.metadata.depends_on:
            if dependency not in known_ids:
                raise TaskCatalogError(
                    f"{task_id} has unknown dependency {dependency}; it is neither "
                    "a task document nor a terminal record"
                )


def _reject_dependency_cycles(
    documents: dict[str, DraftTaskDocument | ApprovedTaskDocument],
) -> None:
    visiting: list[str] = []
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visited:
            return
        if task_id in visiting:
            start = visiting.index(task_id)
            cycle = visiting[start:] + [task_id]
            raise TaskCatalogError(
                f"task dependency cycle detected: {' -> '.join(cycle)}"
            )
        visiting.append(task_id)
        for dependency in documents[task_id].metadata.depends_on:
            if dependency in documents:
                visit(dependency)
        visiting.pop()
        visited.add(task_id)

    for task_id in sorted(documents, key=_id_number):
        visit(task_id)


def _select_explicit(catalog: TaskCatalog, task_id: str) -> SelectedTask:
    terminal = {task.task_id: task for task in catalog.terminal_tasks}
    if task_id in terminal:
        raise TaskSelectionError(
            f"explicit target {task_id} is terminal ({terminal[task_id].status.value})"
        )
    document = next(
        (item for item in catalog.documents if item.task_id == task_id), None
    )
    if document is None:
        raise TaskSelectionError(f"explicit target {task_id} does not exist")
    reason = _ineligibility_reason(document, catalog)
    if reason is not None:
        raise TaskSelectionError(f"explicit target {task_id} is not eligible: {reason}")
    assert isinstance(document, ApprovedTaskDocument)
    return SelectedTask(
        source_sha=catalog.source_sha,
        mode=TaskSelectionMode.EXPLICIT,
        document=document,
        basis=f"explicit selector {task_id}",
    )


def _select_next(catalog: TaskCatalog) -> TaskSelectionResult:
    eligible: list[ApprovedTaskDocument] = []
    reasons = list(catalog.exclusions)
    for document in catalog.documents:
        reason = _ineligibility_reason(document, catalog)
        if reason is None:
            assert isinstance(document, ApprovedTaskDocument)
            eligible.append(document)
        else:
            reasons.append(TaskSelectionReason(document.task_id, reason))

    if not eligible:
        if not reasons:
            reasons.append(TaskSelectionReason(None, "catalog contains no task files"))
        return NoEligibleTask(
            reasons=tuple(
                sorted(
                    reasons,
                    key=lambda item: (
                        item.task_id is None,
                        _id_number(item.task_id) if item.task_id is not None else 0,
                        item.reason,
                    ),
                )
            )
        )

    selected = min(
        eligible,
        key=lambda document: (
            _PRIORITY_ORDER[document.metadata.priority],
            _id_number(document.task_id),
        ),
    )
    return SelectedTask(
        source_sha=catalog.source_sha,
        mode=TaskSelectionMode.NEXT,
        document=selected,
        basis=(
            f"highest eligible priority {selected.metadata.priority}, then numeric "
            f"task ID {_id_number(selected.task_id)}"
        ),
    )


def _ineligibility_reason(
    document: DraftTaskDocument | ApprovedTaskDocument,
    catalog: TaskCatalog,
) -> str | None:
    if isinstance(document, DraftTaskDocument):
        return "execution approval is draft"

    terminal = {task.task_id: task for task in catalog.terminal_tasks}
    open_ids = {item.task_id for item in catalog.documents}
    waiting: list[str] = []
    for dependency in document.metadata.depends_on:
        terminal_task = terminal.get(dependency)
        if terminal_task is not None:
            if terminal_task.status is TaskStatus.DONE:
                continue
            waiting.append(f"dependency {dependency} is Superseded, not Done")
        elif dependency in open_ids:
            waiting.append(f"dependency {dependency} is not terminal Done")
        else:  # Defensive: build_task_catalog rejects this before selection.
            raise TaskCatalogError(f"{document.task_id} has unknown dependency {dependency}")
    return "; ".join(waiting) if waiting else None


def _id_number(task_id: str) -> int:
    return int(task_id.removeprefix("TSK-"))
