import dataclasses
import inspect

import pytest

from tools.autonomous_pr.model import TaskContext, TaskStatus
from tools.autonomous_pr.task_context import (
    TaskRevalidationError,
    revalidate_current_task,
)


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
