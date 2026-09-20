import dataclasses
import inspect
import subprocess
from pathlib import Path

import pytest

from tools.autonomous_pr import repository
from tools.autonomous_pr.model import (
    ExactBaseInput,
    ExecutionTarget,
    TaskContext,
    TaskStatus,
    TerminalTask,
    TrackerTask,
)
from tools.autonomous_pr.task_context import (
    TaskPreflightError,
    TaskRevalidationError,
    TaskTrackerError,
    load_exact_base_input,
    parse_thin_tracker,
    preflight_execution_target,
    revalidate_current_task,
)
from tools.autonomous_pr.task_spec import spec_digest, spec_is_unchanged


def _detail_block(
    *,
    task_id: str,
    detail_status: str,
    roadmap_target: str,
    depends_on: tuple[str, ...],
    depends_on_present: bool,
    depends_on_raw: str | None,
    duplicate_status_field: bool,
    duplicate_roadmap_field: bool,
    duplicate_depends_on_field: bool,
) -> str:
    if depends_on_raw is not None:
        depends_on_text = depends_on_raw
    else:
        depends_on_text = ", ".join(f"`{dep}`" for dep in depends_on) or "—"

    status_field = f"**Status:** `{detail_status}`"
    if duplicate_status_field:
        status_field += f"\n\n**Status:** `{detail_status}`"

    roadmap_field = f"**Roadmap target:** {roadmap_target}"
    if duplicate_roadmap_field:
        roadmap_field += f"\n\n**Roadmap target:** {roadmap_target}"

    lines = [
        f"## {task_id} — Example task",
        "",
        status_field,
        "",
        "**Priority:** `P2`",
        "",
        roadmap_field,
    ]
    if depends_on_present:
        depends_field = f"**Depends on:** {depends_on_text}"
        if duplicate_depends_on_field:
            depends_field += f"\n\n**Depends on:** {depends_on_text}"
        lines += ["", depends_field]
    lines += ["", "**Contract impact:** `none`", "", "### Goal", "", "Deliver it."]
    return "\n".join(lines)


def _task_queue_text(
    *,
    current_id: str = "TSK-0026",
    task_id: str = "TSK-0026",
    include_detail: bool = True,
    detail_status: str = "Current",
    roadmap_target: str = "Phase 3 / Combat",
    depends_on: tuple[str, ...] = (),
    depends_on_present: bool = True,
    depends_on_raw: str | None = None,
    done_ids: tuple[str, ...] = (),
    include_index_row: bool = True,
    index_status: str = "Current",
    duplicate_index_row: bool = False,
    decoy_detail_heading: bool = False,
    duplicate_current_line: bool = False,
    duplicate_detail_heading: bool = False,
    duplicate_status_field: bool = False,
    duplicate_roadmap_field: bool = False,
    duplicate_depends_on_field: bool = False,
) -> str:
    detail_section = ""
    if include_detail:
        block = _detail_block(
            task_id=task_id,
            detail_status=detail_status,
            roadmap_target=roadmap_target,
            depends_on=depends_on,
            depends_on_present=depends_on_present,
            depends_on_raw=depends_on_raw,
            duplicate_status_field=duplicate_status_field,
            duplicate_roadmap_field=duplicate_roadmap_field,
            duplicate_depends_on_field=duplicate_depends_on_field,
        )
        detail_section = "\n" + block
        if duplicate_detail_heading:
            detail_section += "\n\n" + block

    index_row = (
        f"| `{task_id}` | `{index_status}` | `P2` | `M` | `engineering` | "
        f"{roadmap_target} | Example task |"
    )
    index_rows = index_row if include_index_row else ""
    if duplicate_index_row:
        index_rows = f"{index_row}\n{index_row}"

    done_rows = "\n".join(f"| `{done_id}` | Example | PR #1 |" for done_id in done_ids)

    decoy_section = ""
    if decoy_detail_heading:
        decoy_section = f"""
---

# Appendix — decoy

## {task_id} — Decoy heading outside Open task details

**Status:** `Current`

**Roadmap target:** Somewhere else entirely

**Depends on:** —
"""

    current_line = f"- **Current:** {current_id}"
    if duplicate_current_line:
        current_line += f"\n- **Current:** {current_id}"

    return f"""# Task Queue

# Current position

- **Active Roadmap phase:** Phase 3 — Combat
{current_line}
- **Next:** —
- **Hard blockers:** —
- **Next free ID:** TSK-0027
- **Last reviewed:** 2026-09-15

---

# Open task index

| ID | Status | P | Size | Group | Roadmap target | Title |
| --- | --- | --- | --- | --- | --- | --- |
{index_rows}

---

# Open task details
{detail_section}
---

# Recently completed

| ID | Title | Evidence |
| --- | --- | --- |
{done_rows}
{decoy_section}
"""


def test_correct_current_task_accepted() -> None:
    depends_on = ("TSK-0025",)
    roadmap_target = "Cross-cutting engineering prerequisite"
    text = _task_queue_text(
        current_id="TSK-0026",
        task_id="TSK-0026",
        depends_on=depends_on,
        done_ids=depends_on,
        roadmap_target=roadmap_target,
    )

    context = revalidate_current_task(text, "TSK-0026")

    expected_detail_text = _detail_block(
        task_id="TSK-0026",
        detail_status="Current",
        roadmap_target=roadmap_target,
        depends_on=depends_on,
        depends_on_present=True,
        depends_on_raw=None,
        duplicate_status_field=False,
        duplicate_roadmap_field=False,
        duplicate_depends_on_field=False,
    )
    assert context == TaskContext(
        task_id="TSK-0026",
        status=TaskStatus.CURRENT,
        roadmap_target=roadmap_target,
        depends_on=depends_on,
        detail_text=expected_detail_text,
    )


def test_detail_text_captures_full_section_stopping_before_separator() -> None:
    """``detail_text`` must carry the exact authoritative section verbatim
    (heading through Goal) but stop before the following '---' section
    separator and '# Recently completed' -- the common real case where a
    task's detail is the only (or last) one inside '# Open task details'
    has nothing else to mark where its own content ends."""

    text = _task_queue_text(current_id="TSK-0026", task_id="TSK-0026")

    context = revalidate_current_task(text, "TSK-0026")

    assert context.detail_text.startswith("## TSK-0026 — Example task")
    assert "### Goal" in context.detail_text
    assert "Deliver it." in context.detail_text
    assert "---" not in context.detail_text
    assert "Recently completed" not in context.detail_text


def test_wrong_task_id_rejected() -> None:
    text = _task_queue_text(current_id="TSK-0026", task_id="TSK-0026")

    with pytest.raises(TaskRevalidationError):
        revalidate_current_task(text, "TSK-0099")


def test_task_no_longer_current_rejected() -> None:
    text = _task_queue_text(
        current_id="TSK-0026", task_id="TSK-0026", detail_status="Blocked"
    )

    with pytest.raises(TaskRevalidationError):
        revalidate_current_task(text, "TSK-0026")


def test_current_pointer_moved_on_rejected() -> None:
    text = _task_queue_text(current_id="TSK-0027", task_id="TSK-0026")

    with pytest.raises(TaskRevalidationError):
        revalidate_current_task(text, "TSK-0026")


def test_missing_task_detail_rejected() -> None:
    text = _task_queue_text(
        current_id="TSK-0026", task_id="TSK-0026", include_detail=False
    )

    with pytest.raises(TaskRevalidationError):
        revalidate_current_task(text, "TSK-0026")


def test_missing_roadmap_target_rejected() -> None:
    text = _task_queue_text(
        current_id="TSK-0026", task_id="TSK-0026", roadmap_target="—"
    )

    with pytest.raises(TaskRevalidationError):
        revalidate_current_task(text, "TSK-0026")


def test_normal_roadmap_target_accepted() -> None:
    text = _task_queue_text(roadmap_target="Phase 3 / Combat")

    context = revalidate_current_task(text, "TSK-0026")

    assert context.roadmap_target == "Phase 3 / Combat"


def test_blank_roadmap_target_rejected_without_consuming_next_field() -> None:
    """A Roadmap target left blank on its own line must fail closed as
    missing, never by silently capturing the following field's content —
    regression for `\\s*` greedily crossing the line/field boundary."""

    text = _task_queue_text(roadmap_target="", depends_on=())

    with pytest.raises(TaskRevalidationError) as excinfo:
        revalidate_current_task(text, "TSK-0026")

    message = str(excinfo.value)
    assert "missing a required Roadmap target" in message
    assert "Depends on" not in message


def test_unmet_dependency_rejected() -> None:
    text = _task_queue_text(
        current_id="TSK-0026",
        task_id="TSK-0026",
        depends_on=("TSK-0025",),
        done_ids=(),
    )

    with pytest.raises(TaskRevalidationError) as excinfo:
        revalidate_current_task(text, "TSK-0026")

    message = str(excinfo.value)
    assert "could not be positively established" in message
    assert "not authoritative Done" not in message


def test_task_id_never_acts_as_authorization_proof() -> None:
    field_names = {f.name for f in dataclasses.fields(TaskContext)}
    assert not any("author" in name.lower() for name in field_names)

    parameters = inspect.signature(revalidate_current_task).parameters
    assert set(parameters) == {"task_queue_text", "task_id"}
    assert not any("author" in name.lower() for name in parameters)


def test_open_task_index_row_backlog_rejected() -> None:
    text = _task_queue_text(
        current_id="TSK-0026",
        task_id="TSK-0026",
        detail_status="Current",
        index_status="Backlog",
    )

    with pytest.raises(TaskRevalidationError):
        revalidate_current_task(text, "TSK-0026")


def test_open_task_index_row_missing_rejected() -> None:
    text = _task_queue_text(
        current_id="TSK-0026",
        task_id="TSK-0026",
        include_index_row=False,
    )

    with pytest.raises(TaskRevalidationError):
        revalidate_current_task(text, "TSK-0026")


def test_open_task_index_duplicate_row_rejected() -> None:
    text = _task_queue_text(
        current_id="TSK-0026",
        task_id="TSK-0026",
        duplicate_index_row=True,
    )

    with pytest.raises(TaskRevalidationError):
        revalidate_current_task(text, "TSK-0026")


def test_detail_heading_outside_open_task_details_is_not_accepted() -> None:
    """A same-named '## TSK-0026 — ...' heading elsewhere in TASK.md must
    never satisfy live task-detail revalidation; only a heading inside the
    real '# Open task details' section counts."""

    text = _task_queue_text(
        current_id="TSK-0026",
        task_id="TSK-0026",
        include_detail=False,
        decoy_detail_heading=True,
    )

    with pytest.raises(TaskRevalidationError):
        revalidate_current_task(text, "TSK-0026")


def test_missing_depends_on_field_rejected() -> None:
    """A Current task detail with its Depends on field removed entirely
    must fail closed rather than being read as 'no dependencies'."""

    text = _task_queue_text(
        current_id="TSK-0026",
        task_id="TSK-0026",
        depends_on_present=False,
    )

    with pytest.raises(TaskRevalidationError) as excinfo:
        revalidate_current_task(text, "TSK-0026")

    assert "Depends on" in str(excinfo.value)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"duplicate_current_line": True},
        {"duplicate_detail_heading": True},
        {"duplicate_status_field": True},
        {"duplicate_roadmap_field": True},
        {"duplicate_depends_on_field": True},
    ],
)
def test_ambiguous_duplicate_execution_fact_rejected(kwargs: dict[str, bool]) -> None:
    text = _task_queue_text(current_id="TSK-0026", task_id="TSK-0026", **kwargs)

    with pytest.raises(TaskRevalidationError) as excinfo:
        revalidate_current_task(text, "TSK-0026")

    assert "ambiguous" in str(excinfo.value)


def test_five_digit_current_task_id_accepted() -> None:
    """The Open task index row and detail heading for a 5+ digit task id
    must parse correctly, matching the tracker's own `TSK-(\\d{4,})` format."""

    text = _task_queue_text(current_id="TSK-10000", task_id="TSK-10000")

    context = revalidate_current_task(text, "TSK-10000")

    assert context.task_id == "TSK-10000"


def test_depends_on_dash_accepted_as_empty() -> None:
    text = _task_queue_text(depends_on=())

    context = revalidate_current_task(text, "TSK-0026")

    assert context.depends_on == ()


def test_depends_on_valid_id_parsed() -> None:
    text = _task_queue_text(depends_on=("TSK-0025",), done_ids=("TSK-0025",))

    context = revalidate_current_task(text, "TSK-0026")

    assert context.depends_on == ("TSK-0025",)


def test_depends_on_five_digit_id_parsed() -> None:
    """A 5+ digit dependency id must resolve through Depends on parsing and
    the Recently completed evidence lookup, matching the tracker format."""

    text = _task_queue_text(depends_on=("TSK-10000",), done_ids=("TSK-10000",))

    context = revalidate_current_task(text, "TSK-0026")

    assert context.depends_on == ("TSK-10000",)


def test_depends_on_malformed_text_rejected() -> None:
    text = _task_queue_text(depends_on_raw="unknown")

    with pytest.raises(TaskRevalidationError) as excinfo:
        revalidate_current_task(text, "TSK-0026")

    assert "malformed" in str(excinfo.value)


def test_depends_on_valid_id_mixed_with_garbage_rejected() -> None:
    """A valid id mixed with unrelated text must not be silently reduced to
    just the valid id — the whole field fails closed."""

    text = _task_queue_text(depends_on_raw="`TSK-0025` unrelated garbage")

    with pytest.raises(TaskRevalidationError) as excinfo:
        revalidate_current_task(text, "TSK-0026")

    assert "malformed" in str(excinfo.value)


# --------------------------------------------------------------------------
# Prospective v2: thin tracker parsing, exact-base input, preflight primitives
# --------------------------------------------------------------------------

_V2_TASK_ID = "TSK-0030"
_V2_OPEN_HEADER = (
    "| ID | Status | P | Size | Group | Roadmap target | Depends on | Title |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- |"
)
_V2_TERMINAL_HEADER = (
    "| ID | Status | Evidence | Title |\n| --- | --- | --- | --- |"
)


def _open_row(
    task_id: str = _V2_TASK_ID,
    *,
    status: str = "Current",
    priority: str = "P2",
    size: str = "M",
    group: str = "engineering",
    roadmap_target: str = "Phase 3 / Combat",
    depends_on: str = "`TSK-0001`",
    title: str = "Example task",
) -> str:
    return (
        f"| `{task_id}` | `{status}` | `{priority}` | `{size}` | `{group}` | "
        f"{roadmap_target} | {depends_on} | {title} |"
    )


def _terminal_row(
    task_id: str, status: str = "Done", evidence: str = "PR #1", title: str = "Old task"
) -> str:
    return f"| `{task_id}` | `{status}` | {evidence} | {title} |"


def _v2_tracker_text(
    *,
    current: str = _V2_TASK_ID,
    open_rows: tuple[str, ...] | None = None,
    terminal_rows: tuple[str, ...] | None = None,
    recent_ids: tuple[str, ...] = ("TSK-0026",),
    include_terminal_section: bool = True,
    duplicate_terminal_section: bool = False,
    open_section_extra: str = "",
) -> str:
    if open_rows is None:
        open_rows = (_open_row(),)
    if terminal_rows is None:
        terminal_rows = (
            _terminal_row("TSK-0001"),
            _terminal_row("TSK-0026"),
            _terminal_row("TSK-0027", evidence="PR #104"),
        )
    terminal = f"# Terminal task index\n\n{_V2_TERMINAL_HEADER}\n" + "\n".join(
        terminal_rows
    )
    sections = [
        "# Task Queue",
        f"# Current position\n\n- **Current:** {current}\n- **Next:** —\n"
        "- **Next free ID:** TSK-0031",
        f"# Open task index\n\n{_V2_OPEN_HEADER}\n" + "\n".join(open_rows)
        + open_section_extra,
    ]
    if include_terminal_section:
        sections.append(terminal)
        if duplicate_terminal_section:
            sections.append(terminal)
    sections.append(
        "# Recently completed\n\n| ID | Title | Evidence |\n| --- | --- | --- |\n"
        + "\n".join(f"| `{task_id}` | Old | PR #1 |" for task_id in recent_ids)
    )
    return "\n\n---\n\n".join(sections) + "\n"


def _spec_text(task_id: str = _V2_TASK_ID, *, scope: str = "- the change itself") -> str:
    checkpoint = (
        "### CP-1 — Only step\n"
        "- Objective: Do the thing.\n"
        "- Required result: The thing is done.\n"
        "- Constraints: Nothing else.\n"
        '- Verification: ["python", "-m", "pytest", "tests/foo.py"]\n'
        "- Review focus: The thing."
    )
    sections = [
        ("Goal", "Deliver the example result."),
        ("Context / References", "See the approved contract."),
        ("Scope", scope),
        ("Out of scope", "- everything else"),
        ("Approved implementation approach", "Add one narrow module."),
        ("Acceptance criteria", "- the result is observable"),
        ("Execution checkpoints", checkpoint),
        ("Full verification", '["git", "diff", "--check"]'),
        ("Known constraints / edge cases", "None beyond the above."),
    ]
    parts = [f"# {task_id} — Example task", ""]
    for name, body in sections:
        parts += [f"## {name}", "", body, ""]
    return "\n".join(parts)


_BASE_SHA = "a" * 40


def _base(
    *,
    tracker: str | None = None,
    spec: str | None = "default",
) -> ExactBaseInput:
    return ExactBaseInput(
        base_sha=_BASE_SHA,
        task_md_text=_v2_tracker_text() if tracker is None else tracker,
        spec_text=_spec_text() if spec == "default" else spec,
    )


def test_thin_tracker_parses_open_and_terminal_indexes() -> None:
    text = _v2_tracker_text(
        open_rows=(
            _open_row(depends_on="`TSK-0001`, `TSK-0026`"),
            _open_row(
                "TSK-0031",
                status="Backlog",
                priority="P3",
                size="L",
                group="mechanics",
                depends_on="—",
                title="Later task",
            ),
        )
    )

    tracker = parse_thin_tracker(text)

    assert tracker.current_task_id == _V2_TASK_ID
    assert tracker.open_tasks == (
        TrackerTask(
            task_id=_V2_TASK_ID,
            status=TaskStatus.CURRENT,
            priority="P2",
            size="M",
            group="engineering",
            roadmap_target="Phase 3 / Combat",
            depends_on=("TSK-0001", "TSK-0026"),
            title="Example task",
        ),
        TrackerTask(
            task_id="TSK-0031",
            status=TaskStatus.BACKLOG,
            priority="P3",
            size="L",
            group="mechanics",
            roadmap_target="Phase 3 / Combat",
            depends_on=(),
            title="Later task",
        ),
    )
    assert tracker.terminal_tasks[2] == TerminalTask(
        task_id="TSK-0027",
        status=TaskStatus.DONE,
        evidence="PR #104",
        title="Old task",
    )


def test_thin_tracker_current_none_is_accepted() -> None:
    text = _v2_tracker_text(
        current="—", open_rows=(_open_row(status="Backlog", size="L"),)
    )

    assert parse_thin_tracker(text).current_task_id is None


def test_thin_tracker_never_reads_recently_completed() -> None:
    """Dropping or filling '# Recently completed' must not change the
    parsed lifecycle facts: it is only a recent view."""

    with_recent = parse_thin_tracker(_v2_tracker_text(recent_ids=("TSK-0026",)))
    without_recent = parse_thin_tracker(_v2_tracker_text(recent_ids=()))
    text_without_section = _v2_tracker_text().split("# Recently completed")[0]

    assert with_recent == without_recent
    assert parse_thin_tracker(text_without_section) == with_recent


@pytest.mark.parametrize(
    "text",
    [
        # v1-format index (seven columns, no Depends on, no Terminal index)
        "# Current position\n\n- **Current:** TSK-0030\n\n---\n\n# Open task index\n\n"
        "| ID | Status | P | Size | Group | Roadmap target | Title |\n"
        "| --- | --- | --- | --- | --- | --- | --- |\n"
        "| `TSK-0030` | `Current` | `P2` | `M` | `engineering` | T | Title |\n",
        _v2_tracker_text(include_terminal_section=False),
        _v2_tracker_text(duplicate_terminal_section=True),
    ],
    ids=["v1-format", "missing-terminal-section", "duplicate-terminal-section"],
)
def test_thin_tracker_rejects_non_v2_layout(text: str) -> None:
    with pytest.raises(TaskTrackerError):
        parse_thin_tracker(text)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {"open_rows": (_open_row(status="Done"),)},
            "not allowed in this index",
        ),
        (
            {"terminal_rows": (_terminal_row("TSK-0001", status="Blocked"),)},
            "not allowed in this index",
        ),
        ({"open_rows": (_open_row(priority="P9"),)}, "unknown Priority"),
        ({"open_rows": (_open_row(size="XL"),)}, "unknown Size"),
        ({"open_rows": (_open_row(group="misc"),)}, "unknown Group"),
        ({"open_rows": (_open_row(roadmap_target=""),)}, "empty Roadmap target"),
        ({"open_rows": (_open_row(title=""),)}, "empty Title"),
        ({"open_rows": (_open_row(depends_on="unknown"),)}, "Depends on"),
        (
            {"open_rows": (_open_row(depends_on="`TSK-0030`"),)},
            "depends on itself",
        ),
        (
            {"open_rows": (_open_row(depends_on="`TSK-0001`, `TSK-0001`"),)},
            "more than once",
        ),
        (
            {"terminal_rows": (_terminal_row("TSK-0001", evidence=""),)},
            "empty Evidence",
        ),
        (
            {"terminal_rows": (_terminal_row("TSK-0001"), _terminal_row("TSK-0001"))},
            "more than once",
        ),
        (
            {"terminal_rows": (_terminal_row(_V2_TASK_ID),)},
            "more than once",
        ),
        (
            {"open_section_extra": "\nA stray sentence."},
            "may contain only its table",
        ),
        (
            {"open_section_extra": "\n| `TSK-0031` | `Backlog` |"},
            "cells",
        ),
    ],
)
def test_thin_tracker_rejects_malformed_or_ambiguous_content(
    kwargs: dict[str, object], message: str
) -> None:
    with pytest.raises(TaskTrackerError, match=message):
        parse_thin_tracker(_v2_tracker_text(**kwargs))  # type: ignore[arg-type]


def test_thin_tracker_current_pointer_must_agree_with_the_index() -> None:
    with pytest.raises(TaskTrackerError, match="does not have exactly that task"):
        parse_thin_tracker(_v2_tracker_text(current="TSK-0031"))
    with pytest.raises(TaskTrackerError, match="records no Current task"):
        parse_thin_tracker(_v2_tracker_text(current="—"))
    with pytest.raises(TaskTrackerError, match="more than one Current row"):
        parse_thin_tracker(
            _v2_tracker_text(open_rows=(_open_row(), _open_row("TSK-0031")))
        )


def test_preflight_accepts_valid_current_task_with_matching_spec() -> None:
    spec_text = _spec_text()

    target = preflight_execution_target(_base(spec=spec_text), _V2_TASK_ID)

    assert isinstance(target, ExecutionTarget)
    assert target.base_sha == _BASE_SHA
    assert target.task.task_id == _V2_TASK_ID
    assert target.task.depends_on == ("TSK-0001",)
    assert target.spec.task_id == _V2_TASK_ID
    assert target.spec.text == spec_text
    assert target.spec.digest == spec_digest(spec_text)
    assert spec_is_unchanged(target.spec, spec_text)


def test_dependency_done_is_confirmed_by_terminal_index_not_recently_completed() -> None:
    """TSK-0001 is Done in the durable Terminal task index but absent from
    the bounded '# Recently completed' view: v2 must accept it (v1 cannot)."""

    text = _v2_tracker_text(recent_ids=("TSK-0026",))
    assert "`TSK-0001`" in text.split("# Terminal task index")[1].split("# Recently")[0]
    assert "`TSK-0001`" not in text.split("# Recently completed")[1]

    target = preflight_execution_target(_base(tracker=text), _V2_TASK_ID)

    assert target.task.depends_on == ("TSK-0001",)


def test_dependency_listed_only_in_recently_completed_is_not_done() -> None:
    text = _v2_tracker_text(
        terminal_rows=(_terminal_row("TSK-0026"),), recent_ids=("TSK-0001",)
    )

    with pytest.raises(TaskPreflightError, match="not in the Terminal task index"):
        preflight_execution_target(_base(tracker=text), _V2_TASK_ID)


def test_missing_dependency_rejected() -> None:
    text = _v2_tracker_text(
        open_rows=(_open_row(depends_on="`TSK-0099`"),)
    )

    with pytest.raises(TaskPreflightError, match="TSK-0099.*not in the Terminal"):
        preflight_execution_target(_base(tracker=text), _V2_TASK_ID)


def test_superseded_dependency_is_not_done() -> None:
    text = _v2_tracker_text(
        terminal_rows=(_terminal_row("TSK-0001", status="Superseded"),)
    )

    with pytest.raises(TaskPreflightError, match="Superseded, not Done"):
        preflight_execution_target(_base(tracker=text), _V2_TASK_ID)


def test_still_open_dependency_is_not_done() -> None:
    text = _v2_tracker_text(
        open_rows=(
            _open_row(depends_on="`TSK-0031`"),
            _open_row("TSK-0031", status="Blocked", depends_on="—"),
        ),
    )

    with pytest.raises(TaskPreflightError, match="is still open"):
        preflight_execution_target(_base(tracker=text), _V2_TASK_ID)


def test_task_that_is_not_the_authoritative_current_is_rejected() -> None:
    text = _v2_tracker_text(
        current="TSK-0031", open_rows=(_open_row("TSK-0031"), _open_row(status="Ready"))
    )

    with pytest.raises(TaskPreflightError, match="not the authoritative Current"):
        preflight_execution_target(_base(tracker=text), _V2_TASK_ID)


def test_current_none_blocks_an_invocation() -> None:
    text = _v2_tracker_text(
        current="—", open_rows=(_open_row(status="Ready"),)
    )

    with pytest.raises(TaskPreflightError, match="not the authoritative Current"):
        preflight_execution_target(_base(tracker=text), _V2_TASK_ID)


@pytest.mark.parametrize("roadmap_target", ["—"])
def test_missing_roadmap_target_rejected(roadmap_target: str) -> None:
    text = _v2_tracker_text(open_rows=(_open_row(roadmap_target=roadmap_target),))

    with pytest.raises(TaskPreflightError, match="no Roadmap target"):
        preflight_execution_target(_base(tracker=text), _V2_TASK_ID)


def test_roadmap_target_is_checked_for_presence_only() -> None:
    """Any non-empty target passes: the harness makes no semantic judgement
    of whether the target is 'permitted'."""

    text = _v2_tracker_text(
        open_rows=(_open_row(roadmap_target="Something the harness cannot judge"),)
    )

    target = preflight_execution_target(_base(tracker=text), _V2_TASK_ID)

    assert target.task.roadmap_target == "Something the harness cannot judge"


def test_size_l_current_task_rejected() -> None:
    text = _v2_tracker_text(open_rows=(_open_row(size="L"),))

    with pytest.raises(TaskPreflightError, match="size L"):
        preflight_execution_target(_base(tracker=text), _V2_TASK_ID)


def test_current_task_without_required_spec_rejected() -> None:
    """Uses TSK-0028 deliberately: no spec exists (or is assumed) for it."""

    text = _v2_tracker_text(
        current="TSK-0028", open_rows=(_open_row("TSK-0028"),)
    )

    with pytest.raises(TaskPreflightError, match="docs/tasks/TSK-0028.md does not exist"):
        preflight_execution_target(_base(tracker=text, spec=None), "TSK-0028")


def test_spec_whose_h1_belongs_to_another_task_is_rejected() -> None:
    other_spec = _spec_text("TSK-0031")

    with pytest.raises(TaskPreflightError, match="does not match the file name"):
        preflight_execution_target(_base(spec=other_spec), _V2_TASK_ID)


def test_spec_that_is_not_execution_ready_is_rejected() -> None:
    with pytest.raises(TaskPreflightError, match="unresolved placeholder/open-decision"):
        preflight_execution_target(
            _base(spec=_spec_text(scope="- decide the format TBD")), _V2_TASK_ID
        )
    with pytest.raises(TaskPreflightError, match="lifecycle field"):
        preflight_execution_target(
            _base(spec=_spec_text(scope="- the change\nStatus: Current")), _V2_TASK_ID
        )


def test_exact_base_input_carries_one_sha_for_both_texts() -> None:
    """There is a single SHA for metadata and spec: no per-read SHA fields
    that a caller could set independently of ``base_sha``."""

    assert {field.name for field in dataclasses.fields(ExactBaseInput)} == {
        "base_sha",
        "task_md_text",
        "spec_text",
    }


@pytest.mark.parametrize(
    "sha", ["origin/main", "HEAD", "main", "abc1234", "A" * 40, "a" * 39, ""]
)
def test_preflight_rejects_a_base_that_is_not_an_exact_sha(sha: str) -> None:
    base = dataclasses.replace(_base(), base_sha=sha)

    with pytest.raises(TaskPreflightError, match="not an exact commit SHA"):
        preflight_execution_target(base, _V2_TASK_ID)


def test_tracker_defect_surfaces_as_preflight_error() -> None:
    with pytest.raises(TaskPreflightError):
        preflight_execution_target(_base(tracker="# Task Queue\n"), _V2_TASK_ID)


# --- exact-SHA reads from a real (disposable) Git repository ---------------


def _git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8"
    )
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"
    return result.stdout


def _commit_all(repo: Path, message: str) -> None:
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", message], cwd=repo)


@dataclasses.dataclass
class _GitEnv:
    seed: Path
    work: Path


@pytest.fixture
def git_env(tmp_path: Path) -> _GitEnv:
    origin = tmp_path / "origin.git"
    _git(["init", "-q", "--bare", "-b", "main", str(origin)], cwd=tmp_path)
    seed = tmp_path / "seed"
    _git(["init", "-q", "-b", "main", str(seed)], cwd=tmp_path)
    _git(["config", "user.email", "harness-test@example.com"], cwd=seed)
    _git(["config", "user.name", "Harness Test"], cwd=seed)
    (seed / "docs" / "tasks").mkdir(parents=True)
    (seed / "docs" / "TASK.md").write_text(_v2_tracker_text(), encoding="utf-8")
    (seed / "docs" / "tasks" / f"{_V2_TASK_ID}.md").write_text(
        _spec_text(), encoding="utf-8"
    )
    _commit_all(seed, "seed")
    _git(["remote", "add", "origin", str(origin)], cwd=seed)
    _git(["push", "-q", "origin", "main"], cwd=seed)
    work = tmp_path / "work"
    _git(["clone", "-q", str(origin), str(work)], cwd=tmp_path)
    return _GitEnv(seed=seed, work=work)


def test_load_exact_base_input_reads_metadata_and_spec_from_the_captured_sha(
    git_env: _GitEnv,
) -> None:
    work = git_env.work
    captured = repository.fetch_and_capture_origin_main_sha(work)
    original_tracker = (git_env.seed / "docs" / "TASK.md").read_text(encoding="utf-8")
    original_spec = _spec_text()

    (git_env.seed / "docs" / "TASK.md").write_text(
        original_tracker.replace("Example task", "Moved on"), encoding="utf-8"
    )
    (git_env.seed / "docs" / "tasks" / f"{_V2_TASK_ID}.md").write_text(
        _spec_text(scope="- a different scope"), encoding="utf-8"
    )
    _commit_all(git_env.seed, "origin/main moves")
    _git(["push", "-q", "origin", "main"], cwd=git_env.seed)
    repository.fetch_origin(work)
    assert repository.origin_main_sha(work) != captured

    base = load_exact_base_input(work, _V2_TASK_ID, captured)

    assert base == ExactBaseInput(
        base_sha=captured, task_md_text=original_tracker, spec_text=original_spec
    )
    target = preflight_execution_target(base, _V2_TASK_ID)
    assert target.base_sha == captured
    assert target.spec.scope == "- the change itself"


def test_load_exact_base_input_never_fetches(
    git_env: _GitEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = git_env.work
    captured = repository.fetch_and_capture_origin_main_sha(work)
    real_run = repository.subprocess.run

    def fail_if_fetch(
        args: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if args[:2] == ["git", "fetch"]:
            raise AssertionError("load_exact_base_input must never fetch")
        return real_run(args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(repository.subprocess, "run", fail_if_fetch)

    base = load_exact_base_input(work, _V2_TASK_ID, captured)

    assert base.base_sha == captured
    assert base.spec_text is not None


def test_load_exact_base_input_reports_a_missing_spec_as_none(
    git_env: _GitEnv,
) -> None:
    work = git_env.work
    captured = repository.fetch_and_capture_origin_main_sha(work)

    base = load_exact_base_input(work, "TSK-0028", captured)

    assert base.spec_text is None
    assert base.task_md_text == (git_env.seed / "docs" / "TASK.md").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("ref", ["origin/main", "HEAD", "main", "abc1234"])
def test_load_exact_base_input_rejects_a_symbolic_or_short_ref(
    git_env: _GitEnv, ref: str
) -> None:
    with pytest.raises(TaskPreflightError, match="not an exact commit SHA"):
        load_exact_base_input(git_env.work, _V2_TASK_ID, ref)


def test_load_exact_base_input_rejects_an_unknown_commit(git_env: _GitEnv) -> None:
    with pytest.raises(repository.RepositoryError):
        load_exact_base_input(git_env.work, _V2_TASK_ID, "d" * 40)


def test_load_exact_base_input_rejects_an_invalid_task_id(git_env: _GitEnv) -> None:
    captured = repository.fetch_and_capture_origin_main_sha(git_env.work)

    with pytest.raises(TaskPreflightError, match="not a valid TSK-NNNN"):
        load_exact_base_input(git_env.work, "TSK-XXXX", captured)


def test_load_then_preflight_end_to_end_from_one_captured_sha(
    git_env: _GitEnv,
) -> None:
    work = git_env.work
    captured = repository.fetch_and_capture_origin_main_sha(work)

    target = preflight_execution_target(
        load_exact_base_input(work, _V2_TASK_ID, captured), _V2_TASK_ID
    )

    assert target.task.task_id == _V2_TASK_ID
    assert target.spec.path == f"docs/tasks/{_V2_TASK_ID}.md"
    assert not (work / "docs" / "tasks" / "TSK-0028.md").exists()
