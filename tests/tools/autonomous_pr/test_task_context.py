import pytest

from tools.autonomous_pr.model import TaskStatus
from tools.autonomous_pr.task_context import (
    TaskTrackerError,
    parse_terminal_registry,
    validate_terminal_only_closure,
)


HEADER = "| ID | Status | Evidence | Title |\n| --- | --- | --- | --- |"


def _tracker(*rows: str, eol: str = "\n", eof: bool = True) -> str:
    text = "# Terminal task index\n\n" + HEADER
    if rows:
        text += "\n" + "\n".join(rows)
    text = text.replace("\n", eol)
    return text + (eol if eof else "")


def _row(
    task_id: str,
    status: str = "Done",
    evidence: str = "PR #1",
    title: str = "Delivered task",
) -> str:
    return f"| `{task_id}` | `{status}` | {evidence} | {title} |"


def test_terminal_registry_preserves_done_and_superseded_records() -> None:
    registry = parse_terminal_registry(
        _tracker(
            _row("TSK-0001"),
            _row("TSK-0002", "Superseded", "DEC-1", "Old direction"),
        ),
        source_sha="a" * 40,
    )

    assert registry.source_sha == "a" * 40
    assert [task.task_id for task in registry.tasks] == ["TSK-0001", "TSK-0002"]
    assert registry.tasks[0].status is TaskStatus.DONE
    assert registry.tasks[1].status is TaskStatus.SUPERSEDED
    assert registry.tasks[1].evidence == "DEC-1"


@pytest.mark.parametrize(
    "text, message",
    [
        ("# Instructions\n", "exactly one '# Terminal task index'"),
        (
            _tracker() + "\n# Terminal task index\n\n" + HEADER + "\n",
            "exactly one '# Terminal task index'",
        ),
        ("# Terminal task index\n", "has no table header"),
        (
            _tracker(_row("TSK-0001"), _row("TSK-0001")),
            "appear more than once",
        ),
        (_tracker(_row("TSK-0001", "Ready")), "unrecognized Status"),
        (_tracker("| broken | row |"), "expected 4"),
    ],
)
def test_terminal_registry_rejects_missing_or_malformed_facts(
    text: str, message: str
) -> None:
    with pytest.raises(TaskTrackerError, match=message):
        parse_terminal_registry(text)


def test_terminal_only_closure_adds_one_done_row_and_preserves_history() -> None:
    baseline = _tracker(
        _row("TSK-0001", title="Earlier delivery"),
        _row("TSK-0002", "Superseded", "DEC-2", "Cancelled direction"),
    )
    candidate = baseline + _row("TSK-0030", title="New delivery") + "\n"

    validate_terminal_only_closure(
        baseline,
        candidate,
        task_id="TSK-0030",
        pr_number="1",
        title="New delivery",
    )


@pytest.mark.parametrize("eol", ["\n", "\r\n"])
@pytest.mark.parametrize("baseline_has_eof_newline", [False, True])
def test_terminal_only_closure_accepts_empty_table_with_or_without_eof_newline(
    eol: str, baseline_has_eof_newline: bool
) -> None:
    baseline = _tracker(eol=eol, eof=False).rstrip("\r\n")
    if baseline_has_eof_newline:
        baseline += eol
    assert baseline.endswith(("\n", "\r")) is baseline_has_eof_newline
    candidate = baseline + ("" if baseline.endswith(("\n", "\r")) else eol)
    candidate += _row("TSK-0030", title="New delivery") + eol

    validate_terminal_only_closure(
        baseline,
        candidate,
        task_id="TSK-0030",
        pr_number="1",
        title="New delivery",
    )


@pytest.mark.parametrize(
    "inserted",
    [
        "|`TSK-0030`|`Done`|PR #1|New delivery|",
        "| `TSK-0030`  | `Done` | PR #1 | New delivery |",
        r"| `TSK-0030` | `Done` | PR #1 | Handle A \| B |",
    ],
)
def test_terminal_only_closure_accepts_parser_valid_row_formatting(
    inserted: str,
) -> None:
    title = "Handle A | B" if r"\|" in inserted else "New delivery"
    baseline = _tracker(_row("TSK-0001"))
    candidate = baseline + inserted + "\n"

    validate_terminal_only_closure(
        baseline,
        candidate,
        task_id="TSK-0030",
        pr_number="1",
        title=title,
    )


@pytest.mark.parametrize(
    "candidate, message",
    [
        (
            _tracker(_row("TSK-0001", evidence="PR #changed"), _row("TSK-0030")),
            "changed existing terminal rows",
        ),
        (
            _tracker(_row("TSK-0001"), _row("TSK-0030", evidence="PR #2")),
            "exactly one selected-task terminal row",
        ),
        (
            _tracker(_row("TSK-0001"), _row("TSK-0030")) + "extra\n",
            "may contain only its table",
        ),
    ],
)
def test_terminal_only_closure_rejects_non_terminal_or_wrong_changes(
    candidate: str, message: str
) -> None:
    baseline = _tracker(_row("TSK-0001"))
    with pytest.raises(TaskTrackerError, match=message):
        validate_terminal_only_closure(
            baseline,
            candidate,
            task_id="TSK-0030",
            pr_number="1",
            title="Delivered task",
        )


@pytest.mark.parametrize(
    ("baseline_eol", "candidate_eol"),
    [("\n", "\r\n"), ("\r\n", "\n")],
)
def test_terminal_only_closure_rejects_foreign_newline_rewrite_with_valid_own_row(
    baseline_eol: str,
    candidate_eol: str,
) -> None:
    baseline = (
        "# Instructions\n\nPreserve this text.\n\n"
        + _tracker(_row("TSK-0001"), eof=False)
        + "\n"
    ).replace("\n", baseline_eol)
    candidate = baseline.replace(baseline_eol, candidate_eol)
    candidate += _row("TSK-0030", title="New delivery") + candidate_eol

    with pytest.raises(TaskTrackerError, match="must change docs/TASK.md only"):
        validate_terminal_only_closure(
            baseline,
            candidate,
            task_id="TSK-0030",
            pr_number="1",
            title="New delivery",
        )


def test_terminal_only_closure_rejects_instruction_change_with_valid_own_row() -> None:
    baseline = "# Instructions\n\nOriginal rule.\n\n" + _tracker(
        _row("TSK-0001")
    )
    candidate = baseline.replace("Original rule.", "Changed rule.")
    candidate += _row("TSK-0030", title="New delivery") + "\n"

    with pytest.raises(TaskTrackerError, match="must change docs/TASK.md only"):
        validate_terminal_only_closure(
            baseline,
            candidate,
            task_id="TSK-0030",
            pr_number="1",
            title="New delivery",
        )
