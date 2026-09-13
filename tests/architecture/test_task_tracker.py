import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TASK_QUEUE = REPOSITORY_ROOT / "docs" / "TASK.md"
TASK_QUEUE_TEXT = TASK_QUEUE.read_text(encoding="utf-8")

ALLOWED_STATUSES = {"Backlog", "Ready", "Current", "Blocked", "Done", "Superseded"}
ALLOWED_PRIORITIES = {"P0", "P1", "P2", "P3"}
ALLOWED_SIZES = {"S", "M", "L"}
ALLOWED_GROUPS = {
    "mechanics",
    "cross-cutting",
    "engineering",
    "documentation",
    "architecture",
}
READY_CURRENT_SIZES = {"S", "M"}
FULL_DETAIL_STATUSES = {"Current", "Ready", "Blocked"}
REQUIRED_CURRENT_POSITION_FIELDS = ("Current", "Next", "Next free ID")

TASK_ID = re.compile(r"^TSK-(\d{4,})$")
SECTION_HEADING = re.compile(r"^# (.+?)\s*$")
DETAIL_HEADING = re.compile(r"^##\s+(TSK-\d{4,})\s+—")
TABLE_ROW = re.compile(r"^\|(.+)\|\s*$")
TABLE_SEPARATOR_CELL = re.compile(r"^:?-+:?$")
FIELD_LINE = re.compile(r"^-\s*\*\*(?P<name>[^*]+):\*\*\s*(?P<value>.+?)\s*$")


def _strip_backticks(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
        return value[1:-1].strip()
    return value


def _section(text: str, heading: str) -> str:
    # The numbered specification text and Appendix A/B contain example or
    # placeholder task IDs (TSK-0042, TSK-XXXX, TSK-0087, ...); scoping every
    # extraction to its own top-level "# ..." section keeps those out of the
    # live tracker data this file actually validates.
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        match = SECTION_HEADING.match(line)
        if match is not None and match.group(1) == heading:
            start = index + 1
            break
    assert start is not None, f"docs/TASK.md: no top-level '# {heading}' heading found"

    end = len(lines)
    for index in range(start, len(lines)):
        if SECTION_HEADING.match(lines[index]) is not None:
            end = index
            break

    return "\n".join(lines[start:end])


def _table_rows(section_text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in section_text.splitlines():
        match = TABLE_ROW.match(line.strip())
        if match is None:
            continue
        cells = [cell.strip() for cell in match.group(1).split("|")]
        if all(TABLE_SEPARATOR_CELL.match(cell) for cell in cells):
            continue
        rows.append(cells)
    return rows[1:] if rows else []


def _current_position_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in _section(text, "Current position").splitlines():
        match = FIELD_LINE.match(line.strip())
        if match is not None:
            fields[match.group("name").strip()] = match.group("value").strip()
    return fields


def _open_task_index_rows(text: str) -> list[dict[str, str]]:
    rows = _table_rows(_section(text, "Open task index"))
    parsed: list[dict[str, str]] = []
    for cells in rows:
        assert len(cells) == 7, f"Open task index: expected 7 columns, got {cells!r}"
        task_id, status, priority, size, group, roadmap_target, title = cells
        parsed.append(
            {
                "id": _strip_backticks(task_id),
                "status": _strip_backticks(status),
                "priority": _strip_backticks(priority),
                "size": _strip_backticks(size),
                "group": _strip_backticks(group),
                "roadmap_target": _strip_backticks(roadmap_target),
                "title": title.strip(),
            }
        )
    return parsed


def _recently_completed_ids(text: str) -> list[str]:
    return [
        _strip_backticks(cells[0])
        for cells in _table_rows(_section(text, "Recently completed"))
        if cells
    ]


def _open_task_detail_ids(text: str) -> list[str]:
    return [
        match.group(1)
        for line in _section(text, "Open task details").splitlines()
        if (match := DETAIL_HEADING.match(line.strip())) is not None
    ]


def _next_ids(current_position: dict[str, str]) -> list[str]:
    raw = current_position.get("Next", "—")
    if raw == "—":
        return []
    return [item.strip() for item in raw.split("→") if item.strip()]


def test_current_position_declares_required_fields() -> None:
    current_position = _current_position_fields(TASK_QUEUE_TEXT)
    missing = [
        name for name in REQUIRED_CURRENT_POSITION_FIELDS if name not in current_position
    ]
    assert missing == [], (
        f"Current position is missing required field(s): {missing}; a "
        "missing field is not the same as a declared `—`"
    )


def test_open_task_index_has_at_most_one_current_row() -> None:
    current_rows = [
        row for row in _open_task_index_rows(TASK_QUEUE_TEXT) if row["status"] == "Current"
    ]
    assert len(current_rows) <= 1, (
        "Open task index must contain at most one `Current` row, found: "
        f"{[row['id'] for row in current_rows]}"
    )


def test_current_position_matches_open_task_index_current() -> None:
    current_position = _current_position_fields(TASK_QUEUE_TEXT)
    current_rows = [
        row for row in _open_task_index_rows(TASK_QUEUE_TEXT) if row["status"] == "Current"
    ]
    declared_current = current_position.get("Current", "—")

    if declared_current == "—":
        assert not current_rows, (
            "Current position.Current is `—` but Open task index still "
            f"contains a `Current` row: {current_rows[0]['id']}"
        )
        return

    assert current_rows, (
        f"Current position.Current is `{declared_current}` but no Open task "
        "index row has Status `Current`"
    )
    assert current_rows[0]["id"] == declared_current, (
        f"Current position.Current (`{declared_current}`) does not match the "
        f"single `Current` row in Open task index (`{current_rows[0]['id']}`)"
    )


def test_next_contains_at_most_five_ids() -> None:
    next_ids = _next_ids(_current_position_fields(TASK_QUEUE_TEXT))
    assert len(next_ids) <= 5, f"Next lists {len(next_ids)} tasks, expected at most 5: {next_ids}"


def test_next_ids_have_no_duplicates() -> None:
    next_ids = _next_ids(_current_position_fields(TASK_QUEUE_TEXT))
    duplicates = sorted({task_id for task_id in next_ids if next_ids.count(task_id) > 1})
    assert duplicates == [], f"Next lists duplicate task ID(s): {duplicates}"


def test_next_ids_exist_in_open_task_index_and_are_ready() -> None:
    next_ids = _next_ids(_current_position_fields(TASK_QUEUE_TEXT))
    index_by_id = {row["id"]: row for row in _open_task_index_rows(TASK_QUEUE_TEXT)}

    errors = []
    for task_id in next_ids:
        row = index_by_id.get(task_id)
        if row is None:
            errors.append(f"Next lists `{task_id}` but it has no Open task index row")
        elif row["status"] != "Ready":
            errors.append(
                f"Next lists `{task_id}` with Status `{row['status']}`, expected `Ready`"
            )
    assert errors == [], "\n" + "\n".join(errors)


def test_ready_and_current_tasks_have_allowed_size_and_roadmap_target() -> None:
    errors = []
    for row in _open_task_index_rows(TASK_QUEUE_TEXT):
        if row["status"] not in {"Ready", "Current"}:
            continue
        if row["size"] not in READY_CURRENT_SIZES:
            errors.append(
                f"{row['id']}: Status {row['status']} requires Size in "
                f"{sorted(READY_CURRENT_SIZES)}, found `{row['size']}`"
            )
        if not row["roadmap_target"] or row["roadmap_target"] == "—":
            errors.append(
                f"{row['id']}: Status {row['status']} requires a non-empty "
                "Roadmap target other than `—`"
            )
    assert errors == [], "\n" + "\n".join(errors)


def test_open_task_index_values_use_closed_enum_sets() -> None:
    errors = []
    for row in _open_task_index_rows(TASK_QUEUE_TEXT):
        if row["status"] not in ALLOWED_STATUSES:
            errors.append(f"{row['id']}: unknown Status `{row['status']}`")
        if row["priority"] not in ALLOWED_PRIORITIES:
            errors.append(f"{row['id']}: unknown Priority `{row['priority']}`")
        if row["size"] not in ALLOWED_SIZES:
            errors.append(f"{row['id']}: unknown Size `{row['size']}`")
        if row["group"] not in ALLOWED_GROUPS:
            errors.append(f"{row['id']}: unknown Group `{row['group']}`")
    assert errors == [], "\n" + "\n".join(errors)


def test_open_task_index_ids_are_unique() -> None:
    ids = [row["id"] for row in _open_task_index_rows(TASK_QUEUE_TEXT)]
    duplicates = sorted({task_id for task_id in ids if ids.count(task_id) > 1})
    assert duplicates == [], f"duplicate Open task index rows: {duplicates}"


def test_open_task_detail_headings_are_unique() -> None:
    detail_ids = _open_task_detail_ids(TASK_QUEUE_TEXT)
    duplicates = sorted(
        {task_id for task_id in detail_ids if detail_ids.count(task_id) > 1}
    )
    assert duplicates == [], f"duplicate Open task details headings: {duplicates}"


def test_open_task_details_correspond_to_open_task_index_rows() -> None:
    index_ids = {row["id"] for row in _open_task_index_rows(TASK_QUEUE_TEXT)}
    detail_ids = set(_open_task_detail_ids(TASK_QUEUE_TEXT))

    orphaned = sorted(detail_ids - index_ids)
    assert orphaned == [], (
        "Open task details contains a heading with no matching Open task "
        f"index row: {orphaned}"
    )


def test_current_ready_and_blocked_tasks_have_full_detail() -> None:
    detail_ids = _open_task_detail_ids(TASK_QUEUE_TEXT)

    errors = []
    for row in _open_task_index_rows(TASK_QUEUE_TEXT):
        if row["status"] not in FULL_DETAIL_STATUSES:
            continue
        matches = detail_ids.count(row["id"])
        if matches != 1:
            errors.append(
                f"{row['id']} (Status {row['status']}) has {matches} Open task "
                "details headings; expected exactly 1 (§15)"
            )
    assert errors == [], "\n" + "\n".join(errors)


def test_next_free_id_has_valid_format() -> None:
    next_free_id = _current_position_fields(TASK_QUEUE_TEXT).get("Next free ID", "")
    assert TASK_ID.match(next_free_id), (
        f"Current position.Next free ID `{next_free_id}` is not a valid "
        "TSK-NNNN identifier"
    )


def test_next_free_id_exceeds_every_allocated_task_id() -> None:
    next_free_id = _current_position_fields(TASK_QUEUE_TEXT).get("Next free ID", "")
    match = TASK_ID.match(next_free_id)
    assert match is not None, (
        f"Current position.Next free ID `{next_free_id}` is not a valid "
        "TSK-NNNN identifier"
    )
    next_free_number = int(match.group(1))

    allocated_ids = [row["id"] for row in _open_task_index_rows(TASK_QUEUE_TEXT)]
    allocated_ids += _recently_completed_ids(TASK_QUEUE_TEXT)

    errors = []
    for task_id in allocated_ids:
        allocated_match = TASK_ID.match(task_id)
        if allocated_match is None:
            errors.append(f"allocated ID `{task_id}` is not a valid TSK-NNNN identifier")
            continue
        if int(allocated_match.group(1)) >= next_free_number:
            errors.append(
                f"allocated ID `{task_id}` is not smaller than "
                f"Next free ID `{next_free_id}`"
            )
    assert errors == [], "\n" + "\n".join(errors)
