import dataclasses
import hashlib

import pytest

from tools.autonomous_pr.model import ExecutionCheckpoint, TaskExecutionSpec
from tools.autonomous_pr.task_spec import (
    CHECKPOINT_FIELDS,
    SPEC_SECTIONS,
    TaskSpecError,
    parse_task_execution_spec,
    spec_digest,
    spec_is_unchanged,
    spec_path_for,
)

TASK_ID = "TSK-0030"
PATH = f"docs/tasks/{TASK_ID}.md"

_PYTEST_CMD = '["python", "-m", "pytest", "tests/foo.py"]'


def _checkpoint(
    number: int,
    *,
    name: str | None = None,
    drop_field: str | None = None,
    field_overrides: dict[str, str] | None = None,
) -> str:
    fields = {
        "Objective": f"Objective of checkpoint {number}.",
        "Required result": f"State left behind by checkpoint {number}.",
        "Constraints": "Touch nothing outside the checkpoint.",
        "Verification": _PYTEST_CMD,
        "Review focus": "Where to look first.",
    }
    fields.update(field_overrides or {})
    lines = [f"### CP-{number} — {name or f'Step {number}'}"]
    for label in CHECKPOINT_FIELDS:
        if label == drop_field:
            continue
        lines.append(f"- {label}: {fields[label]}")
    return "\n".join(lines)


def _default_sections() -> list[tuple[str, str]]:
    return [
        ("Goal", "Deliver the example result."),
        ("Context / References", "See the approved contract."),
        ("Scope", "- the change itself"),
        ("Out of scope", "- everything else"),
        ("Approved implementation approach", "Add one narrow module."),
        ("Acceptance criteria", "- the result is observable"),
        ("Execution checkpoints", _checkpoint(1) + "\n\n" + _checkpoint(2)),
        (
            "Full verification",
            '["python", "-m", "pytest"]\n["git", "diff", "--check"]',
        ),
        ("Known constraints / edge cases", "None beyond the above."),
    ]


def _render(
    sections: list[tuple[str, str]],
    *,
    h1: str | None = None,
    task_id: str = TASK_ID,
    preamble: str = "",
) -> str:
    parts = [h1 if h1 is not None else f"# {task_id} — Example task", ""]
    if preamble:
        parts += [preamble, ""]
    for name, body in sections:
        parts += [f"## {name}", "", body, ""]
    return "\n".join(parts)


def _replace(name: str, body: str) -> list[tuple[str, str]]:
    return [(n, body if n == name else b) for n, b in _default_sections()]


def _valid_text() -> str:
    return _render(_default_sections())


def _parse(text: str, path: str = PATH) -> TaskExecutionSpec:
    return parse_task_execution_spec(text, path)


def test_valid_spec_parses_into_typed_model() -> None:
    text = _valid_text()

    spec = _parse(text)

    assert spec.task_id == TASK_ID
    assert spec.path == PATH
    assert spec.title == "Example task"
    assert spec.goal == "Deliver the example result."
    assert spec.scope == "- the change itself"
    assert spec.known_constraints == "None beyond the above."
    assert [cp.checkpoint_id for cp in spec.checkpoints] == ["CP-1", "CP-2"]
    assert spec.checkpoints[0] == ExecutionCheckpoint(
        number=1,
        checkpoint_id="CP-1",
        name="Step 1",
        objective="Objective of checkpoint 1.",
        required_result="State left behind by checkpoint 1.",
        constraints="Touch nothing outside the checkpoint.",
        verification=(("python", "-m", "pytest", "tests/foo.py"),),
        review_focus="Where to look first.",
    )
    assert spec.full_verification == (
        ("python", "-m", "pytest"),
        ("git", "diff", "--check"),
    )


def test_spec_carries_exact_text_and_deterministic_digest() -> None:
    text = _valid_text()

    spec = _parse(text)

    assert spec.text == text
    assert spec.digest == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert spec.digest == spec_digest(text)
    assert _parse(text).digest == spec.digest


def test_spec_model_has_no_lifecycle_or_queue_fields() -> None:
    names = {field.name for field in dataclasses.fields(TaskExecutionSpec)}

    assert not names & {"status", "priority", "size", "depends_on", "queue_position"}


def test_spec_is_unchanged_detects_any_edit_and_removal() -> None:
    text = _valid_text()
    spec = _parse(text)

    assert spec_is_unchanged(spec, text)
    assert not spec_is_unchanged(spec, text + "\n")
    assert not spec_is_unchanged(spec, text.replace("Deliver", "Ship"))
    assert not spec_is_unchanged(spec, None)


def test_spec_path_is_a_function_of_the_task_id_alone() -> None:
    assert spec_path_for("TSK-0028") == "docs/tasks/TSK-0028.md"
    assert spec_path_for("TSK-10000") == "docs/tasks/TSK-10000.md"
    with pytest.raises(TaskSpecError):
        spec_path_for("TSK-XXXX")


@pytest.mark.parametrize(
    "path",
    [
        "docs/tasks/current/TSK-0030.md",
        "docs/tasks/TSK-0030.txt",
        "docs/TSK-0030.md",
        "docs/tasks/tsk-0030.md",
        "TSK-0030.md",
    ],
)
def test_non_canonical_spec_path_rejected(path: str) -> None:
    with pytest.raises(TaskSpecError, match="not a Task Execution Spec path"):
        _parse(_valid_text(), path)


def test_h1_task_id_must_match_filename_task_id() -> None:
    text = _render(_default_sections(), task_id="TSK-0031")

    with pytest.raises(TaskSpecError, match="does not match the file name"):
        _parse(text)


@pytest.mark.parametrize(
    "h1",
    ["# TSK-XXXX — Example task", "# Example task", "# TSK-0030 - Example task"],
)
def test_malformed_h1_rejected(h1: str) -> None:
    with pytest.raises(TaskSpecError, match="H1|first non-blank line"):
        _parse(_render(_default_sections(), h1=h1))


def test_second_level_one_heading_rejected() -> None:
    text = _valid_text() + "\n# Another title\n"

    with pytest.raises(TaskSpecError, match="exactly one level-1 heading"):
        _parse(text)


def test_empty_spec_rejected() -> None:
    with pytest.raises(TaskSpecError, match="empty"):
        _parse("\n\n")


@pytest.mark.parametrize("missing", SPEC_SECTIONS)
def test_missing_section_rejected(missing: str) -> None:
    sections = [(n, b) for n, b in _default_sections() if n != missing]

    with pytest.raises(TaskSpecError, match="missing required section"):
        _parse(_render(sections))


def test_wrong_section_order_rejected() -> None:
    sections = _default_sections()
    sections[2], sections[3] = sections[3], sections[2]

    with pytest.raises(TaskSpecError, match="out of order"):
        _parse(_render(sections))


def test_duplicate_section_rejected() -> None:
    sections = _default_sections()
    sections.insert(3, sections[2])

    with pytest.raises(TaskSpecError, match="duplicate section"):
        _parse(_render(sections))


def test_unexpected_extra_section_rejected() -> None:
    sections = _default_sections() + [("Appendix", "Extra.")]

    with pytest.raises(TaskSpecError, match="unexpected section"):
        _parse(_render(sections))


def test_content_between_h1_and_first_section_rejected() -> None:
    with pytest.raises(TaskSpecError, match="between the H1 and the first section"):
        _parse(_render(_default_sections(), preamble="A stray requirement."))


@pytest.mark.parametrize(
    "name", [n for n in SPEC_SECTIONS if n not in ("Execution checkpoints", "Full verification")]
)
def test_empty_prose_section_rejected(name: str) -> None:
    with pytest.raises(TaskSpecError, match=f"section '{name}' is empty"):
        _parse(_render(_replace(name, "")))


def test_heading_inside_code_fence_is_not_a_section() -> None:
    body = "Example layout:\n\n```markdown\n## Extra\n# Title\n```\n"

    spec = _parse(_render(_replace("Scope", body)))

    assert "## Extra" in spec.scope


def test_unterminated_code_fence_rejected() -> None:
    with pytest.raises(TaskSpecError, match="unterminated fenced code block"):
        _parse(_render(_replace("Scope", "```markdown\n## Extra")))


def test_checkpoint_gap_rejected() -> None:
    body = _checkpoint(1) + "\n\n" + _checkpoint(3)

    with pytest.raises(TaskSpecError, match="expected CP-2, found CP-3"):
        _parse(_render(_replace("Execution checkpoints", body)))


def test_checkpoint_order_rejected() -> None:
    body = _checkpoint(2) + "\n\n" + _checkpoint(1)

    with pytest.raises(TaskSpecError, match="expected CP-1, found CP-2"):
        _parse(_render(_replace("Execution checkpoints", body)))


def test_duplicate_checkpoint_rejected() -> None:
    body = _checkpoint(1) + "\n\n" + _checkpoint(2) + "\n\n" + _checkpoint(1)

    with pytest.raises(TaskSpecError, match="duplicate checkpoint CP-1"):
        _parse(_render(_replace("Execution checkpoints", body)))


def test_checkpoints_must_start_at_cp_1() -> None:
    with pytest.raises(TaskSpecError, match="expected CP-1, found CP-2"):
        _parse(_render(_replace("Execution checkpoints", _checkpoint(2))))


def test_no_checkpoint_rejected() -> None:
    with pytest.raises(TaskSpecError, match="declares no checkpoint"):
        _parse(_render(_replace("Execution checkpoints", "")))
    with pytest.raises(TaskSpecError, match="found content before CP-1"):
        _parse(_render(_replace("Execution checkpoints", "Nothing declared.")))


@pytest.mark.parametrize("heading", ["### CP-01 — Step", "### CP-1 - Step", "### Step one"])
def test_malformed_checkpoint_heading_rejected(heading: str) -> None:
    body = heading + "\n" + "\n".join(_checkpoint(1).splitlines()[1:])

    with pytest.raises(TaskSpecError, match="malformed checkpoint heading"):
        _parse(_render(_replace("Execution checkpoints", body)))


def test_content_before_first_checkpoint_rejected() -> None:
    body = "Intro prose.\n\n" + _checkpoint(1)

    with pytest.raises(TaskSpecError, match="found content before CP-1"):
        _parse(_render(_replace("Execution checkpoints", body)))


@pytest.mark.parametrize("field", CHECKPOINT_FIELDS)
def test_missing_checkpoint_field_rejected(field: str) -> None:
    body = _checkpoint(1, drop_field=field) + "\n\n" + _checkpoint(2)

    with pytest.raises(TaskSpecError, match=f"CP-1 is missing required field '{field}'"):
        _parse(_render(_replace("Execution checkpoints", body)))


@pytest.mark.parametrize("field", CHECKPOINT_FIELDS)
def test_empty_checkpoint_field_rejected(field: str) -> None:
    body = _checkpoint(1, field_overrides={field: ""}) + "\n\n" + _checkpoint(2)

    with pytest.raises(TaskSpecError, match=f"CP-1 field '{field}' is empty"):
        _parse(_render(_replace("Execution checkpoints", body)))


def test_duplicate_checkpoint_field_rejected() -> None:
    body = _checkpoint(1) + "\n- Objective: Again."

    with pytest.raises(TaskSpecError, match="declares 'Objective' more than once"):
        _parse(_render(_replace("Execution checkpoints", body)))


def test_multiline_checkpoint_field_continues_until_next_field() -> None:
    body = (
        "### CP-1 — Step\n"
        "- Objective: First line.\n"
        "  Second line.\n"
        "  - a nested bullet\n"
        "- Required result: Result.\n"
        "- Constraints: Constraint.\n"
        f"- Verification:\n  {_PYTEST_CMD}\n"
        "- Review focus: Focus."
    )

    spec = _parse(_render(_replace("Execution checkpoints", body)))

    assert spec.checkpoints[0].objective == "First line.\n  Second line.\n  - a nested bullet"
    assert spec.checkpoints[0].verification == (("python", "-m", "pytest", "tests/foo.py"),)


def test_multiple_verification_commands_with_optional_bullets() -> None:
    verification = (
        '\n  ["python", "-m", "pytest"]\n'
        '  - ["git", "diff", "--check"]\n'
        '  ["python", "-m", "mypy", "src"]'
    )
    body = _checkpoint(1, field_overrides={"Verification": verification})

    spec = _parse(_render(_replace("Execution checkpoints", body)))

    assert spec.checkpoints[0].verification == (
        ("python", "-m", "pytest"),
        ("git", "diff", "--check"),
        ("python", "-m", "mypy", "src"),
    )


@pytest.mark.parametrize(
    "command",
    [
        "python -m pytest tests/foo.py",
        '"python -m pytest tests/foo.py"',
        "[]",
        '[""]',
        '["", "x"]',
        '[" "]',
        '["   ", "x"]',
        '["\\t", "x"]',
        '["python", "a\\u0000b"]',
        '["py\\u0000thon", "x"]',
        '["\\u0000"]',
        '[1, "x"]',
        '["python", null]',
        '{"argv": ["python"]}',
        '["python", "-m"',
        "Run the tests and check they pass.",
    ],
)
def test_invalid_checkpoint_verification_command_rejected(command: str) -> None:
    body = _checkpoint(1, field_overrides={"Verification": command})

    with pytest.raises(TaskSpecError):
        _parse(_render(_replace("Execution checkpoints", body)))


def test_prose_mixed_into_valid_verification_rejected() -> None:
    verification = f"\n  {_PYTEST_CMD}\n  then check the output by hand"
    body = _checkpoint(1, field_overrides={"Verification": verification})

    with pytest.raises(TaskSpecError, match="not a JSON argv array"):
        _parse(_render(_replace("Execution checkpoints", body)))


@pytest.mark.parametrize(
    "body",
    [
        "python -m pytest",
        "",
        "[]",
        '[" "]',
        '["python", "a\\u0000b"]',
        '["python", 3]',
        "Run everything.",
        '["python", "-m", "pytest"]\nand then look at it',
    ],
)
def test_invalid_full_verification_rejected(body: str) -> None:
    with pytest.raises(TaskSpecError):
        _parse(_render(_replace("Full verification", body)))


@pytest.mark.parametrize(
    "command",
    [
        '[" "]',
        '["   ", "x"]',
        '["\\t", "x"]',
        '["\\n"]',
    ],
)
def test_blank_executable_rejected_for_that_reason(command: str) -> None:
    for text in (
        _render(_replace("Full verification", command)),
        _render(
            _replace(
                "Execution checkpoints",
                _checkpoint(1, field_overrides={"Verification": command}),
            )
        ),
    ):
        with pytest.raises(TaskSpecError, match="whitespace-only executable"):
            _parse(text)


@pytest.mark.parametrize(
    "command",
    [
        '["python", "a\\u0000b"]',
        '["py\\u0000thon", "x"]',
        '["\\u0000"]',
    ],
)
def test_nul_character_in_any_argv_element_rejected_for_that_reason(
    command: str,
) -> None:
    for text in (
        _render(_replace("Full verification", command)),
        _render(
            _replace(
                "Execution checkpoints",
                _checkpoint(1, field_overrides={"Verification": command}),
            )
        ),
    ):
        with pytest.raises(TaskSpecError, match="NUL character"):
            _parse(text)


def test_whitespace_in_later_argv_elements_is_plain_data() -> None:
    """Only the executable must be non-blank: later elements are opaque
    argument data, blanks included."""

    command = '["python", " ", "a b", ""]'

    spec = _parse(_render(_replace("Full verification", command)))

    assert spec.full_verification == (("python", " ", "a b", ""),)


def test_shell_metacharacters_are_plain_argv_data_never_interpreted() -> None:
    command = '["python", "-c", "print($HOME); x = 1 < 2 && 3"]'

    spec = _parse(_render(_replace("Full verification", command)))

    assert spec.full_verification == (("python", "-c", "print($HOME); x = 1 < 2 && 3"),)


@pytest.mark.parametrize(
    "line",
    [
        "Status: Current",
        "status: current",
        "STATUS: Current",
        "- Status: Current",
        "**Status:** `Current`",
        "**Status**: Current",
        "Priority: P1",
        "priority: p1",
        "- Size: M",
        "size: m",
        "Depends on: TSK-0027",
        "depends on: TSK-0027",
        "**Depends on:** `TSK-0027`",
        "Queue position: 1",
        "QUEUE POSITION: 1",
    ],
)
def test_lifecycle_metadata_inside_spec_rejected(line: str) -> None:
    with pytest.raises(TaskSpecError, match="lifecycle field"):
        _parse(_render(_replace("Scope", f"- the change\n{line}")))


def test_lifecycle_metadata_inside_checkpoint_field_rejected() -> None:
    body = _checkpoint(1, field_overrides={"Constraints": "Keep it small.\n  Status: Done"})

    with pytest.raises(TaskSpecError, match="CP-1 Constraints carries the lifecycle field"):
        _parse(_render(_replace("Execution checkpoints", body)))


def test_prose_that_merely_mentions_a_lifecycle_word_is_accepted() -> None:
    text = _render(
        _replace("Scope", "The status of the run and its size are reported elsewhere.")
    )

    assert _parse(text).scope.startswith("The status of the run")


@pytest.mark.parametrize(
    "marker",
    [
        "TBD",
        "tbd",
        "TODO: decide the format",
        "Todo: decide the format",
        "todo",
        "FIXME later",
        "fixme later",
        "XXX",
        "xxx",
        "OPEN DECISION: which format",
        "open decision: which format",
        "OPEN QUESTION about retries",
        "Open Question about retries",
        "<title>",
        "<TITLE>",
        "<name>",
        "<Name>",
    ],
)
def test_unresolved_placeholder_or_open_decision_rejected(marker: str) -> None:
    with pytest.raises(TaskSpecError, match="unresolved placeholder/open-decision"):
        _parse(_render(_replace("Approved implementation approach", f"Use {marker}.")))


@pytest.mark.parametrize(
    ("where", "field"),
    [("CP-1 Objective", "Objective"), ("CP-1 Review focus", "Review focus")],
)
def test_unresolved_marker_inside_checkpoint_rejected(where: str, field: str) -> None:
    body = _checkpoint(1, field_overrides={field: "Decide this TBD."})

    with pytest.raises(TaskSpecError, match=where):
        _parse(_render(_replace("Execution checkpoints", body)))


def test_unresolved_marker_in_checkpoint_name_and_title_rejected() -> None:
    body = _checkpoint(1, name="<NAME>")
    with pytest.raises(TaskSpecError, match="unresolved"):
        _parse(_render(_replace("Execution checkpoints", body)))
    with pytest.raises(TaskSpecError, match="unresolved"):
        _parse(_render(_default_sections(), h1=f"# {TASK_ID} — <TITLE>"))


def test_verification_commands_are_not_scanned_for_unresolved_markers() -> None:
    body = _checkpoint(
        1, field_overrides={"Verification": '["grep", "-rn", "TODO", "src"]'}
    )
    sections = _replace("Execution checkpoints", body)
    sections = [
        (n, '["grep", "-rn", "todo", "src"]' if n == "Full verification" else b)
        for n, b in sections
    ]

    spec = _parse(_render(sections))

    assert spec.checkpoints[0].verification == (("grep", "-rn", "TODO", "src"),)
    assert spec.full_verification == (("grep", "-rn", "todo", "src"),)


def test_parser_is_path_driven_and_reads_no_file() -> None:
    """The parser only ever sees the text and path it is given: any task ID
    works, and nothing assumes a spec file exists for a particular task
    (in particular none is assumed for TSK-0028)."""

    for task_id in ("TSK-0028", "TSK-0099", "TSK-10000"):
        spec = parse_task_execution_spec(
            _render(_default_sections(), task_id=task_id), f"docs/tasks/{task_id}.md"
        )
        assert spec.task_id == task_id
