import itertools
import json

import pytest

from tools.autonomous_pr import catalog as catalog_module
from tools.autonomous_pr.catalog import (
    TaskCatalogError,
    TaskSelectionError,
    build_task_catalog,
    resolve_task_selection,
    select_task,
)
from tools.autonomous_pr.model import (
    NoEligibleTask,
    RunOutcome,
    SelectedTask,
    TaskFileRecord,
    TaskSelectionMode,
    TaskStatus,
    TerminalRegistry,
    TerminalTask,
)

SHA = "a" * 40


def _metadata(
    *,
    approval: str = "approved",
    priority: str = "P2",
    size: str = "M",
    depends_on: tuple[str, ...] = (),
) -> str:
    return json.dumps(
        {
            "execution_approval": approval,
            "priority": priority,
            "size": size,
            "roadmap_target": "Phase 3 / deterministic dispatch",
            "depends_on": list(depends_on),
            "group": "engineering",
        },
        indent=2,
    )


def _document(
    task_id: str,
    *,
    approval: str = "approved",
    priority: str = "P2",
    depends_on: tuple[str, ...] = (),
    body: str | None = "valid",
) -> str:
    parts = [
        f"# {task_id} — Task {task_id}",
        "",
        "## Task metadata",
        "",
        "```json",
        _metadata(
            approval=approval,
            priority=priority,
            size="L" if approval == "draft" else "M",
            depends_on=depends_on,
        ),
        "```",
        "",
    ]
    if body is None:
        return "\n".join(parts)
    if body == "partial":
        parts += ["## Goal", "", "Draft goal.", ""]
        return "\n".join(parts)
    checkpoint = (
        "### CP-1 — Step\n"
        "- Objective: Implement it.\n"
        "- Required result: It works.\n"
        "- Constraints: Stay in scope.\n"
        '- Verification: ["python", "-m", "pytest"]\n'
        "- Review focus: Determinism."
    )
    sections = [
        ("Goal", "Deliver deterministic selection."),
        ("Context / References", "Use the fixed contract."),
        ("Scope", "- catalog"),
        ("Out of scope", "- scheduling"),
        ("Approved implementation approach", "Use pure functions."),
        ("Acceptance criteria", "- deterministic result"),
        ("Execution checkpoints", checkpoint),
        ("Full verification", '["python", "-m", "pytest"]'),
        ("Known constraints / edge cases", "No fallback."),
    ]
    if body == "malformed":
        sections = sections[:-1]
    for name, content in sections:
        parts += [f"## {name}", "", content, ""]
    return "\n".join(parts)


def _record(task_id: str, **kwargs: object) -> TaskFileRecord:
    return TaskFileRecord(
        source_sha=SHA,
        path=f"docs/tasks/{task_id}.md",
        text=_document(task_id, **kwargs),  # type: ignore[arg-type]
    )


def _terminal(
    task_id: str,
    status: TaskStatus = TaskStatus.DONE,
) -> TerminalTask:
    return TerminalTask(
        task_id=task_id,
        status=status,
        evidence="PR #1",
        title=f"Terminal {task_id}",
    )


def _registry(*tasks: TerminalTask) -> TerminalRegistry:
    return TerminalRegistry(tasks=tasks, source_sha=SHA)


@pytest.mark.parametrize(
    "records",
    list(
        itertools.permutations(
            (
                _record("TSK-0100", priority="P1"),
                _record("TSK-0009", priority="P1"),
                _record("TSK-9000", priority="P0"),
            )
        )
    ),
)
def test_next_is_independent_of_catalog_order_and_sorts_priority_then_numeric_id(
    records: tuple[TaskFileRecord, ...],
) -> None:
    result = resolve_task_selection(SHA, records, _registry(), "NEXT")

    assert isinstance(result, SelectedTask)
    assert result.mode is TaskSelectionMode.NEXT
    assert result.document.task_id == "TSK-9000"

    without_p0 = tuple(record for record in records if "TSK-9000" not in record.path)
    result = resolve_task_selection(SHA, without_p0, _registry(), "NEXT")
    assert isinstance(result, SelectedTask)
    assert result.document.task_id == "TSK-0009"


def test_explicit_id_does_not_use_priority_order_or_fallback() -> None:
    records = (
        _record("TSK-0030", priority="P3"),
        _record("TSK-0031", priority="P0"),
    )

    result = resolve_task_selection(SHA, records, _registry(), "TSK-0030")

    assert isinstance(result, SelectedTask)
    assert result.mode is TaskSelectionMode.EXPLICIT
    assert result.document.task_id == "TSK-0030"


def test_empty_catalog_returns_no_eligible_task_with_exit_zero() -> None:
    result = resolve_task_selection(SHA, (), _registry(), "NEXT")

    assert isinstance(result, NoEligibleTask)
    assert result.outcome is RunOutcome.NO_ELIGIBLE_TASK
    assert result.exit_code == 0
    assert result.reasons[0].task_id is None
    assert "no task files" in result.reasons[0].reason


def test_draft_and_open_dependency_are_reported_as_no_work_reasons() -> None:
    records = (
        _record("TSK-0030", approval="draft", body="partial"),
        _record("TSK-0031", depends_on=("TSK-0030",)),
    )

    result = resolve_task_selection(SHA, records, _registry(), "NEXT")

    assert isinstance(result, NoEligibleTask)
    assert {(reason.task_id, reason.reason) for reason in result.reasons} == {
        ("TSK-0030", "execution approval is draft"),
        ("TSK-0031", "dependency TSK-0030 is not terminal Done"),
    }


def test_terminal_file_is_filtered_before_body_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = TaskFileRecord(
        source_sha=SHA,
        path="docs/tasks/TSK-0001.md",
        text="legacy or malformed content",
    )

    def forbidden_parse(text: str, path: str) -> object:
        raise AssertionError(f"terminal body was parsed: {path}: {text}")

    monkeypatch.setattr(catalog_module, "parse_task_document", forbidden_parse)

    result = resolve_task_selection(
        SHA, (record,), _registry(_terminal("TSK-0001")), "NEXT"
    )

    assert isinstance(result, NoEligibleTask)
    assert result.reasons[0].task_id == "TSK-0001"


@pytest.mark.parametrize("include_terminal_file", [False, True])
def test_done_dependency_needs_terminal_fact_not_terminal_spec(
    include_terminal_file: bool,
) -> None:
    records = [_record("TSK-0030", depends_on=("TSK-0001",))]
    if include_terminal_file:
        records.append(
            TaskFileRecord(
                source_sha=SHA,
                path="docs/tasks/TSK-0001.md",
                text="old retained format",
            )
        )

    result = resolve_task_selection(
        SHA, records, _registry(_terminal("TSK-0001")), "NEXT"
    )

    assert isinstance(result, SelectedTask)
    assert result.document.task_id == "TSK-0030"


@pytest.mark.parametrize(
    "record, message",
    [
        (
            TaskFileRecord(
                source_sha=SHA,
                path="docs/tasks/TSK-invalid.md",
                text="anything",
            ),
            "not canonical",
        ),
        (
            _record("TSK-0030", body="malformed"),
            "invalid task document",
        ),
        (
            TaskFileRecord(
                source_sha=SHA,
                path="docs/tasks/TSK-0030.md",
                text=_document("TSK-0030").replace('"priority": "P2"', '"priority": "P9"'),
            ),
            "invalid task document",
        ),
    ],
)
def test_invalid_identity_metadata_or_approved_body_is_catalog_error(
    record: TaskFileRecord, message: str
) -> None:
    with pytest.raises(TaskCatalogError, match=message):
        build_task_catalog(SHA, (record,), _registry())


def test_superseded_dependency_is_known_but_not_satisfied() -> None:
    result = resolve_task_selection(
        SHA,
        (_record("TSK-0030", depends_on=("TSK-0001",)),),
        _registry(_terminal("TSK-0001", TaskStatus.SUPERSEDED)),
        "NEXT",
    )

    assert isinstance(result, NoEligibleTask)
    assert "Superseded, not Done" in result.reasons[0].reason


def test_unknown_dependency_is_invalid_catalog_input() -> None:
    with pytest.raises(TaskCatalogError, match="unknown dependency TSK-9999"):
        build_task_catalog(
            SHA,
            (_record("TSK-0030", depends_on=("TSK-9999",)),),
            _registry(),
        )


@pytest.mark.parametrize(
    "dependencies, message",
    [
        (("TSK-0030",), "cannot depend on itself"),
        (("TSK-0001", "TSK-0001"), "duplicate task ID"),
    ],
)
def test_self_and_duplicate_dependencies_are_invalid_catalog_input(
    dependencies: tuple[str, ...], message: str
) -> None:
    with pytest.raises(TaskCatalogError, match=message):
        build_task_catalog(
            SHA,
            (_record("TSK-0030", depends_on=dependencies),),
            _registry(_terminal("TSK-0001")),
        )


def test_dependency_cycles_use_draft_metadata_without_parsing_draft_body() -> None:
    records = (
        _record(
            "TSK-0030",
            approval="draft",
            depends_on=("TSK-0031",),
            body="partial",
        ),
        _record(
            "TSK-0031",
            approval="draft",
            depends_on=("TSK-0030",),
            body=None,
        ),
    )

    with pytest.raises(TaskCatalogError, match="dependency cycle"):
        build_task_catalog(SHA, records, _registry())


@pytest.mark.parametrize("selector", [None, "", "next", "TSK-3"])
def test_missing_or_malformed_selector_is_configuration_error(
    selector: str | None,
) -> None:
    catalog = build_task_catalog(SHA, (_record("TSK-0030"),), _registry())

    with pytest.raises(TaskSelectionError):
        select_task(catalog, selector)


@pytest.mark.parametrize(
    "selector, records, terminal, message",
    [
        ("TSK-0039", (), _registry(), "does not exist"),
        (
            "TSK-0030",
            (_record("TSK-0030", approval="draft", body=None),),
            _registry(),
            "approval is draft",
        ),
        (
            "TSK-0030",
            (),
            _registry(_terminal("TSK-0030")),
            "is terminal",
        ),
    ],
)
def test_invalid_explicit_target_never_falls_back(
    selector: str,
    records: tuple[TaskFileRecord, ...],
    terminal: TerminalRegistry,
    message: str,
) -> None:
    catalog = build_task_catalog(
        SHA,
        records + (_record("TSK-0040", priority="P0"),),
        terminal,
    )

    with pytest.raises(TaskSelectionError, match=message):
        select_task(catalog, selector)


def test_catalog_rejects_mixed_source_shas_and_duplicate_identities() -> None:
    record = _record("TSK-0030")
    with pytest.raises(TaskCatalogError, match="belongs to"):
        build_task_catalog(
            SHA,
            (
                TaskFileRecord(
                    source_sha="b" * 40,
                    path=record.path,
                    text=record.text,
                ),
            ),
            _registry(),
        )

    with pytest.raises(TaskCatalogError, match="duplicate identity"):
        build_task_catalog(SHA, (record, record), _registry())

    with pytest.raises(TaskCatalogError, match="same captured snapshot"):
        build_task_catalog(
            SHA,
            (record,),
            TerminalRegistry(tasks=(), source_sha="b" * 40),
        )
