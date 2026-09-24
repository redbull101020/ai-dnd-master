import hashlib
import re
from pathlib import Path

import pytest

from tools.autonomous_pr.catalog import (
    TaskCatalogError,
    build_task_catalog,
    select_task,
)
from tools.autonomous_pr.model import (
    ApprovedTaskDocument,
    DraftTaskDocument,
    NoEligibleTask,
    SelectedTask,
    TaskFileRecord,
    TaskStatus,
    TerminalRegistry,
    TerminalTask,
)
from tools.autonomous_pr.task_context import parse_terminal_registry
from tools.autonomous_pr.task_spec import parse_task_document


ROOT = Path(__file__).resolve().parents[2]
TASK_MD = ROOT / "docs" / "TASK.md"
TASKS = ROOT / "docs" / "tasks"
SHA = "a" * 40


def _metadata(
    approval: str,
    *,
    priority: str = "P2",
    size: str = "S",
    depends_on: tuple[str, ...] = (),
) -> str:
    dependencies = ", ".join(f'"{item}"' for item in depends_on)
    return f'''## Task metadata

```json
{{
  "execution_approval": "{approval}",
  "priority": "{priority}",
  "size": "{size}",
  "roadmap_target": "Synthetic target",
  "depends_on": [{dependencies}],
  "group": "engineering"
}}
```
'''


def _approved(task_id: str, *, priority: str = "P2", depends_on: tuple[str, ...] = ()) -> str:
    return f'''# {task_id} — Synthetic task

{_metadata("approved", priority=priority, depends_on=depends_on)}
## Goal

Deliver the fixture.

## Context / References

Use repository contracts.

## Scope

- synthetic scope

## Out of scope

- production behavior

## Approved implementation approach

Use one checkpoint.

## Acceptance criteria

- fixture passes

## Execution checkpoints

### CP-1 — Fixture
- Objective: Exercise selection.
- Required result: Selection is deterministic.
- Constraints: No production writes.
- Verification: ["python", "-m", "pytest", "tests/architecture"]
- Review focus: Catalog identity.

## Full verification

["python", "-m", "pytest", "tests/architecture"]

## Known constraints / edge cases

Synthetic only.
'''


def _draft(task_id: str, *, size: str = "L") -> str:
    return f"# {task_id} — Draft task\n\n{_metadata('draft', size=size)}"


def _record(task_id: str, text: str) -> TaskFileRecord:
    return TaskFileRecord(SHA, f"docs/tasks/{task_id}.md", text)


def _terminal(*tasks: TerminalTask) -> TerminalRegistry:
    return TerminalRegistry(tasks=tasks, source_sha=SHA)


def _allocated_identities(
    standalone_ids: list[str], terminal: TerminalRegistry
) -> set[str]:
    return set(standalone_ids) | {task.task_id for task in terminal.tasks}


def test_live_tracker_is_only_normative_guidance_and_terminal_registry() -> None:
    text = TASK_MD.read_text(encoding="utf-8")
    registry = parse_terminal_registry(text)

    assert "# Current position" not in text
    assert "# Open task index" not in text
    assert "# Recently completed" not in text
    assert "Next free ID" not in text
    assert len(registry.tasks) == len({task.task_id for task in registry.tasks})
    assert all(
        task.status in {TaskStatus.DONE, TaskStatus.SUPERSEDED}
        and task.evidence
        and task.title
        for task in registry.tasks
    )
    assert {task.task_id: task.status for task in registry.tasks}["TSK-0005"] is TaskStatus.SUPERSEDED
    assert {task.task_id: task.status for task in registry.tasks}["TSK-0028"] is TaskStatus.DONE


def test_id_allocation_uses_all_standalone_and_terminal_identities() -> None:
    terminal = parse_terminal_registry(TASK_MD.read_text(encoding="utf-8"))
    standalone_ids = [path.stem for path in TASKS.glob("TSK-*.md")]
    allocated = _allocated_identities(standalone_ids, terminal)
    numbers = [int(task_id.removeprefix("TSK-")) for task_id in allocated]

    assert f"TSK-{max(numbers) + 1:04d}" not in allocated
    guidance = TASK_MD.read_text(encoding="utf-8")
    assert "Task IDs are never reused" in guidance
    assert "gaps remain allocated" in guidance


@pytest.mark.parametrize("retain_terminal_spec", [False, True])
def test_allocation_identity_union_allows_retained_or_deleted_terminal_spec(
    retain_terminal_spec: bool,
) -> None:
    done = TerminalTask("TSK-0100", TaskStatus.DONE, "PR #1", "Delivered")
    standalone = ["TSK-0101"]
    if retain_terminal_spec:
        standalone.append("TSK-0100")

    allocated = _allocated_identities(standalone, _terminal(done))

    assert allocated == {"TSK-0100", "TSK-0101"}
    assert max(int(task_id.removeprefix("TSK-")) for task_id in allocated) + 1 == 102


def test_generic_metadata_invariant_allows_reviewed_draft_refinement() -> None:
    draft = parse_task_document(
        _draft("TSK-0100"), "docs/tasks/TSK-0100.md"
    )
    approved = parse_task_document(
        _approved("TSK-0100", priority="P1"), "docs/tasks/TSK-0100.md"
    )

    assert isinstance(draft, DraftTaskDocument)
    assert isinstance(approved, ApprovedTaskDocument)
    assert approved.metadata.priority == "P1"


def test_empty_catalog_and_draft_l_produce_no_work() -> None:
    empty = build_task_catalog(SHA, (), _terminal())
    assert isinstance(select_task(empty, "NEXT"), NoEligibleTask)

    draft = build_task_catalog(
        SHA, (_record("TSK-0100", _draft("TSK-0100")),), _terminal()
    )
    assert isinstance(select_task(draft, "NEXT"), NoEligibleTask)


def test_adding_and_removing_files_changes_next_without_tracker_queue() -> None:
    lower = _record("TSK-0100", _approved("TSK-0100", priority="P2"))
    higher = _record("TSK-0101", _approved("TSK-0101", priority="P1"))

    selected = select_task(build_task_catalog(SHA, (lower,), _terminal()), "NEXT")
    assert isinstance(selected, SelectedTask)
    assert selected.document.task_id == "TSK-0100"

    selected = select_task(
        build_task_catalog(SHA, (lower, higher), _terminal()), "NEXT"
    )
    assert isinstance(selected, SelectedTask)
    assert selected.document.task_id == "TSK-0101"

    selected = select_task(build_task_catalog(SHA, (higher,), _terminal()), "NEXT")
    assert isinstance(selected, SelectedTask)
    assert selected.document.task_id == "TSK-0101"


def test_terminal_identity_is_excluded_with_retained_or_removed_spec() -> None:
    done = TerminalTask("TSK-0100", TaskStatus.DONE, "PR #1", "Synthetic task")
    retained = build_task_catalog(
        SHA,
        (_record("TSK-0100", "legacy terminal body that is not parseable"),),
        _terminal(done),
    )
    removed = build_task_catalog(SHA, (), _terminal(done))

    assert isinstance(select_task(retained, "NEXT"), NoEligibleTask)
    assert isinstance(select_task(removed, "NEXT"), NoEligibleTask)


def test_done_dependency_works_without_spec_but_open_and_superseded_do_not() -> None:
    dependent = _record(
        "TSK-0101", _approved("TSK-0101", depends_on=("TSK-0100",))
    )
    done = TerminalTask("TSK-0100", TaskStatus.DONE, "PR #1", "Dependency")
    selected = select_task(
        build_task_catalog(SHA, (dependent,), _terminal(done)), "NEXT"
    )
    assert isinstance(selected, SelectedTask)

    open_dependency = _record("TSK-0100", _draft("TSK-0100"))
    waiting = select_task(
        build_task_catalog(SHA, (open_dependency, dependent), _terminal()), "NEXT"
    )
    assert isinstance(waiting, NoEligibleTask)

    superseded = TerminalTask(
        "TSK-0100", TaskStatus.SUPERSEDED, "DEC-1", "Dependency"
    )
    assert isinstance(
        select_task(build_task_catalog(SHA, (dependent,), _terminal(superseded)), "NEXT"),
        NoEligibleTask,
    )


def test_malformed_nonterminal_document_is_not_ignored() -> None:
    malformed = _record("TSK-0100", "# TSK-0100 — Missing metadata\n")
    with pytest.raises(TaskCatalogError, match="invalid task document"):
        build_task_catalog(SHA, (malformed,), _terminal())


def test_task_document_digest_covers_exact_text() -> None:
    text = _draft("TSK-0100")
    document = parse_task_document(text, "docs/tasks/TSK-0100.md")
    assert document.text == text
    assert document.digest == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert re.fullmatch(r"[0-9a-f]{64}", document.digest)
