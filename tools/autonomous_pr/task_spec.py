"""Deterministic Task Execution Spec parsing for operational v2.

``docs/AUTONOMOUS_PR_HARNESS.md`` Part II §§22–24 define the Task Execution
Spec: the approved, provider-neutral execution target of one task, stored at
exactly ``docs/tasks/TSK-XXXX.md``. This module turns spec text into a typed
:class:`.model.TaskExecutionSpec` and fails closed on everything it can
check mechanically. It is pure — no Git, no filesystem, no LLM judgment —
and is the only execution-spec parser used by the public v2 orchestrator.

What "execution-ready" means here (§22) is limited to what a deterministic
parser can decide:

- exactly the nine §23 sections, in order, once each, each non-empty;
- one ``# TSK-NNNN — <title>`` H1 whose ID equals the ID in the file name;
- ``CP-1``, ``CP-2``, ... strictly sequential, each declaring Objective,
  Required result, Constraints, Verification, and Review focus exactly once;
- every verification command a JSON argv array (below);
- no lifecycle field (Status, Priority, Size, Depends on, Queue position)
  as a label in the spec;
- no machine-detectable unresolved placeholder or open-decision marker.

What it deliberately does not decide: whether the spec is *good*, whether a
requirement hides in an informational section (§24), or whether it conflicts
with a higher-level source (§21). Those stay governance/review questions.

Layout the parser accepts (the §23 skeleton, made exact):

- The H1 is the first non-blank line; every other level-1 heading is
  rejected. Level-2 headings are exactly the nine section names. Headings
  inside fenced code blocks are ordinary text.
- ``## Execution checkpoints`` holds only ``### CP-N — <name>`` blocks. A
  checkpoint field starts with ``- <Label>:`` at column 0; every other line
  up to the next field belongs to the previous field.
- Verification representation (approved for TSK-0028): a checkpoint's
  ``Verification`` field and the ``## Full verification`` section contain
  only shell-free commands, one JSON array of strings per line, optionally
  behind a ``- `` list marker, e.g. ``["python", "-m", "pytest", "tests/x.py"]``.
  Each decodes to a non-empty ``tuple[str, ...]`` whose first element is
  neither empty nor whitespace-only and in which no element contains a NUL
  character. A shell command string, prose, or an empty list is rejected;
  nothing here uses ``shell=True``, variable expansion, or ``shlex``.
- Unresolved markers (``TBD``, ``TODO``, ``FIXME``, ``XXX``, ``OPEN DECISION``,
  ``OPEN QUESTION``, and the template placeholders ``<title>``/``<name>``)
  and the lifecycle labels are matched case-insensitively in prose, never
  inside verification commands. A spec that must mention one of these words
  must phrase it differently.
"""

from __future__ import annotations

import hashlib
import json
import re

from .model import (
    ApprovedTaskDocument,
    DraftTaskDocument,
    ExecutionApproval,
    ExecutionCheckpoint,
    TaskDocument,
    TaskExecutionSpec,
    TaskMetadata,
    VerificationArgv,
)

SPEC_SECTIONS: tuple[str, ...] = (
    "Goal",
    "Context / References",
    "Scope",
    "Out of scope",
    "Approved implementation approach",
    "Acceptance criteria",
    "Execution checkpoints",
    "Full verification",
    "Known constraints / edge cases",
)

CHECKPOINT_FIELDS: tuple[str, ...] = (
    "Objective",
    "Required result",
    "Constraints",
    "Verification",
    "Review focus",
)

_PROSE_SECTIONS: tuple[str, ...] = tuple(
    name
    for name in SPEC_SECTIONS
    if name not in ("Execution checkpoints", "Full verification")
)

_TASK_ID = re.compile(r"TSK-\d{4,}")
_SPEC_PATH = re.compile(r"docs/tasks/(TSK-\d{4,})\.md")
_H1_TASK = re.compile(r"(TSK-\d{4,}) — (\S.*)")
_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_CHECKPOINT_HEADING = re.compile(r"^### CP-([1-9]\d*) — (\S.*?)[ \t]*$")
_CHECKPOINT_FIELD = re.compile(
    r"^- (" + "|".join(re.escape(name) for name in CHECKPOINT_FIELDS) + r"):[ \t]*(.*)$"
)
_LIFECYCLE_LABEL = re.compile(
    r"^\s*(?:[-*+]\s+)?(?:\*\*|__)?"
    r"(Status|Priority|Size|Depends on|Queue position)"
    r"(?:\*\*|__)?\s*:",
    re.IGNORECASE,
)
_UNRESOLVED_MARKER = re.compile(
    r"\b(?:TBD|TODO|FIXME|XXX)\b|\bOPEN DECISION\b|\bOPEN QUESTION\b|<title>|<name>",
    re.IGNORECASE,
)
_METADATA_SECTION = "Task metadata"
_METADATA_REQUIRED_KEYS = frozenset(
    {"execution_approval", "priority", "size", "roadmap_target", "depends_on"}
)
_METADATA_OPTIONAL_KEYS = frozenset({"group"})
_PRIORITIES = frozenset({"P0", "P1", "P2", "P3"})
_SIZES = frozenset({"S", "M", "L"})
_EXECUTABLE_SIZES = frozenset({"S", "M"})
_GROUPS = frozenset(
    {"mechanics", "cross-cutting", "engineering", "documentation", "architecture"}
)
_STANDALONE_METADATA_LABEL = re.compile(
    r"^\s*(?:[-*+]\s+)?(?:\*\*|__)?"
    r"(execution[_ ]approval|priority|size|roadmap[_ ]target|depends[_ ]on|group)"
    r"(?:\*\*|__)?\s*:",
    re.IGNORECASE,
)


class TaskSpecError(Exception):
    """A Task Execution Spec is not a valid, execution-ready spec.

    Every mechanically determinable defect raises this. The caller treats it
    like any ``AGENTS.md`` "Fail-closed" condition: the run ends ``BLOCKED``
    for refinement or a human decision; it never edits the spec to make the
    check pass (Harness §30 "Spec immutability").
    """


def spec_path_for(task_id: str) -> str:
    """The one stable spec path, a function of the immutable task ID alone."""

    if _TASK_ID.fullmatch(task_id) is None:
        raise TaskSpecError(f"{task_id!r} is not a valid TSK-NNNN task ID")
    return f"docs/tasks/{task_id}.md"


def spec_digest(text: str) -> str:
    """Deterministic identity of exact spec text (sha256 of its UTF-8 bytes)."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def spec_is_unchanged(spec: TaskExecutionSpec, current_text: str | None) -> bool:
    """Whether ``current_text`` is exactly the spec text the run started with.

    ``None`` (the spec no longer exists) is a change. Not a signing
    mechanism: it only lets a later step prove the run's spec was not
    edited (Harness §30).
    """

    return (
        current_text is not None
        and current_text == spec.text
        and spec_digest(current_text) == spec.digest
    )


def parse_task_document(text: str, path: str) -> TaskDocument:
    """Parse a prospective standalone task document without activating it.

    The document starts with the canonical H1 and exactly one ``Task metadata``
    fenced JSON object. A draft may omit the execution body or carry a partial
    or complete body; it remains non-executable and that body is not checked
    for approved readiness. An approved document must contain the existing
    nine-section execution body, which is delegated to
    :func:`parse_task_execution_spec` after the metadata section is removed.
    The returned document always retains the exact original text and digest.

    This CP-1 primitive is intentionally not wired into public preflight or
    selection yet; atomic activation belongs to TSK-0029 CP-5.
    """

    filename_id = _task_id_from_path(path)
    raw_lines = text.splitlines()
    lines = _classify_lines(raw_lines, path)
    title = _read_h1(lines, filename_id, path)

    metadata_headings = [
        index
        for index, (line, inside_fence) in enumerate(lines)
        if not inside_fence
        and (heading := _HEADING.fullmatch(line)) is not None
        and heading.group(1) == "##"
        and heading.group(2) == _METADATA_SECTION
    ]
    if len(metadata_headings) != 1:
        raise TaskSpecError(
            f"{path}: expected exactly one '## {_METADATA_SECTION}' section, "
            f"found {len(metadata_headings)}"
    )
    metadata_index = metadata_headings[0]
    h1_index = next(index for index, (line, _) in enumerate(lines) if line.strip())
    if any(line.strip() for line, _ in lines[h1_index + 1 : metadata_index]):
        raise TaskSpecError(
            f"{path}: only blank lines are allowed between the H1 and "
            f"'## {_METADATA_SECTION}'"
        )

    next_h2_index = next(
        (
            index
            for index, (line, inside_fence) in enumerate(
                lines[metadata_index + 1 :], start=metadata_index + 1
            )
            if not inside_fence
            and (heading := _HEADING.fullmatch(line)) is not None
            and heading.group(1) == "##"
        ),
        None,
    )
    metadata_end = next_h2_index if next_h2_index is not None else len(lines)
    metadata = _parse_task_metadata(
        [line for line, _ in lines[metadata_index + 1 : metadata_end]],
        filename_id,
        path,
    )
    digest = spec_digest(text)
    body_text: str | None = None
    if next_h2_index is not None:
        body_lines = raw_lines[:metadata_index] + raw_lines[next_h2_index:]
        body_text = "\n".join(body_lines) + ("\n" if text.endswith("\n") else "")
        _reject_metadata_duplicates_in_body(body_text, path)

    if metadata.execution_approval is ExecutionApproval.DRAFT:
        return DraftTaskDocument(
            task_id=filename_id,
            path=path,
            title=title,
            metadata=metadata,
            text=text,
            digest=digest,
        )

    if next_h2_index is None:
        raise TaskSpecError(
            f"{path}: approved task document has no execution sections"
        )
    assert body_text is not None
    execution_spec = parse_task_execution_spec(body_text, path)
    return ApprovedTaskDocument(
        task_id=filename_id,
        path=path,
        title=title,
        metadata=metadata,
        execution_spec=execution_spec,
        text=text,
        digest=digest,
    )


def parse_task_execution_spec(text: str, path: str) -> TaskExecutionSpec:
    """Parse and validate ``text``, read from ``path``, as a Task Execution Spec.

    ``path`` must be exactly ``docs/tasks/TSK-NNNN.md``; its task ID must
    equal the H1's. Raises :class:`TaskSpecError` for any defect listed in
    the module docstring.
    """

    filename_id = _task_id_from_path(path)

    lines = _classify_lines(text.splitlines(), path)
    title = _read_h1(lines, filename_id, path)
    section_bodies = _split_sections(lines, path)

    for name in _PROSE_SECTIONS:
        if not _joined(section_bodies[name]):
            raise TaskSpecError(f"{path}: section '{name}' is empty")
    checkpoints = _parse_checkpoints(section_bodies["Execution checkpoints"], path)
    full_verification = _parse_commands(
        _joined(section_bodies["Full verification"]), path, "section 'Full verification'"
    )

    scanned: list[tuple[str, str]] = [("the H1 title", title)]
    scanned += [
        (f"section '{name}'", _joined(section_bodies[name])) for name in _PROSE_SECTIONS
    ]
    for checkpoint in checkpoints:
        label = checkpoint.checkpoint_id
        scanned += [
            (f"{label} name", checkpoint.name),
            (f"{label} Objective", checkpoint.objective),
            (f"{label} Required result", checkpoint.required_result),
            (f"{label} Constraints", checkpoint.constraints),
            (f"{label} Review focus", checkpoint.review_focus),
        ]
    for label, piece in scanned:
        _reject_lifecycle_and_unresolved(piece, label, path)

    return TaskExecutionSpec(
        task_id=filename_id,
        path=path,
        title=title,
        goal=_joined(section_bodies["Goal"]),
        context_references=_joined(section_bodies["Context / References"]),
        scope=_joined(section_bodies["Scope"]),
        out_of_scope=_joined(section_bodies["Out of scope"]),
        approved_implementation_approach=_joined(
            section_bodies["Approved implementation approach"]
        ),
        acceptance_criteria=_joined(section_bodies["Acceptance criteria"]),
        checkpoints=checkpoints,
        full_verification=full_verification,
        known_constraints=_joined(section_bodies["Known constraints / edge cases"]),
        text=text,
        digest=spec_digest(text),
    )


def _task_id_from_path(path: str) -> str:
    path_match = _SPEC_PATH.fullmatch(path)
    if path_match is None:
        raise TaskSpecError(
            f"{path!r} is not a Task Execution Spec path; expected exactly "
            "'docs/tasks/TSK-NNNN.md'"
        )
    return path_match.group(1)


class _DuplicateJsonKey(ValueError):
    pass


def _json_object_without_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey(key)
        result[key] = value
    return result


def _parse_task_metadata(lines: list[str], task_id: str, path: str) -> TaskMetadata:
    nonblank = [line.strip() for line in lines if line.strip()]
    if len(nonblank) < 3 or nonblank[0] != "```json" or nonblank[-1] != "```":
        raise TaskSpecError(
            f"{path}: '## {_METADATA_SECTION}' must contain exactly one fenced "
            "JSON object using ```json"
        )
    json_text = "\n".join(nonblank[1:-1])
    try:
        value = json.loads(
            json_text,
            object_pairs_hook=_json_object_without_duplicate_keys,
        )
    except _DuplicateJsonKey as exc:
        raise TaskSpecError(
            f"{path}: Task metadata contains duplicate JSON key {exc.args[0]!r}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise TaskSpecError(f"{path}: Task metadata is not valid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise TaskSpecError(f"{path}: Task metadata JSON must be an object")

    keys = set(value)
    missing = sorted(_METADATA_REQUIRED_KEYS - keys)
    unknown = sorted(keys - _METADATA_REQUIRED_KEYS - _METADATA_OPTIONAL_KEYS)
    if missing:
        raise TaskSpecError(
            f"{path}: Task metadata is missing required field(s): {', '.join(missing)}"
        )
    if unknown:
        raise TaskSpecError(
            f"{path}: Task metadata has unknown field(s): {', '.join(unknown)}"
        )

    approval_raw = _metadata_string(value, "execution_approval", path)
    try:
        approval = ExecutionApproval(approval_raw)
    except ValueError as exc:
        raise TaskSpecError(
            f"{path}: execution_approval must be 'draft' or 'approved', found "
            f"{approval_raw!r}"
        ) from exc
    priority = _metadata_choice(value, "priority", _PRIORITIES, path)
    size = _metadata_choice(value, "size", _SIZES, path)
    roadmap_target = _metadata_string(value, "roadmap_target", path)
    group = (
        _metadata_choice(value, "group", _GROUPS, path)
        if "group" in value
        else None
    )

    raw_dependencies = value["depends_on"]
    if not isinstance(raw_dependencies, list):
        raise TaskSpecError(f"{path}: depends_on must be a JSON array")
    dependencies: list[str] = []
    for dependency in raw_dependencies:
        if not isinstance(dependency, str) or _TASK_ID.fullmatch(dependency) is None:
            raise TaskSpecError(
                f"{path}: every depends_on item must be a TSK-NNNN string"
            )
        dependencies.append(dependency)
    if task_id in dependencies:
        raise TaskSpecError(f"{path}: {task_id} cannot depend on itself")
    if len(set(dependencies)) != len(dependencies):
        raise TaskSpecError(f"{path}: depends_on contains a duplicate task ID")

    if approval is ExecutionApproval.APPROVED:
        if size not in _EXECUTABLE_SIZES:
            raise TaskSpecError(
                f"{path}: approved task size must be S or M, found {size!r}"
            )
        if not roadmap_target.strip() or roadmap_target.strip() == "—":
            raise TaskSpecError(
                f"{path}: approved task must have a substantive roadmap_target"
            )
        unresolved = _UNRESOLVED_MARKER.search(roadmap_target)
        if unresolved is not None:
            raise TaskSpecError(
                f"{path}: approved task roadmap_target contains unresolved marker "
                f"{unresolved.group(0)!r}"
            )

    return TaskMetadata(
        execution_approval=approval,
        priority=priority,
        size=size,
        roadmap_target=roadmap_target,
        depends_on=tuple(dependencies),
        group=group,
    )


def _metadata_string(value: dict[str, object], key: str, path: str) -> str:
    item = value[key]
    if not isinstance(item, str):
        raise TaskSpecError(f"{path}: {key} must be a JSON string")
    return item


def _metadata_choice(
    value: dict[str, object], key: str, allowed: frozenset[str], path: str
) -> str:
    item = _metadata_string(value, key, path)
    if item not in allowed:
        raise TaskSpecError(
            f"{path}: {key} has unknown value {item!r}; expected one of "
            f"{', '.join(sorted(allowed))}"
        )
    return item


def _reject_metadata_duplicates_in_body(body_text: str, path: str) -> None:
    for line, inside_fence in _classify_lines(body_text.splitlines(), path):
        if inside_fence:
            continue
        match = _STANDALONE_METADATA_LABEL.match(line)
        if match is not None:
            raise TaskSpecError(
                f"{path}: execution body duplicates Task metadata field "
                f"{match.group(1)!r}"
            )


_Line = tuple[str, bool]


def _joined(lines: list[_Line]) -> str:
    return "\n".join(line for line, _ in lines).strip()


def _classify_lines(raw_lines: list[str], path: str) -> list[_Line]:
    """Mark each line as inside/outside a fenced code block.

    Headings and checkpoint fields are only recognised outside fences. An
    unterminated fence would silently swallow every following heading, so it
    fails closed.
    """

    classified: list[_Line] = []
    fence: tuple[str, int] | None = None
    for line in raw_lines:
        match = _FENCE.match(line)
        if fence is None:
            if match is not None:
                marker = match.group(1)
                fence = (marker[0], len(marker))
                classified.append((line, True))
            else:
                classified.append((line, False))
            continue
        classified.append((line, True))
        if (
            match is not None
            and match.group(1)[0] == fence[0]
            and len(match.group(1)) >= fence[1]
            and line.strip().strip(fence[0]) == ""
        ):
            fence = None
    if fence is not None:
        raise TaskSpecError(f"{path}: unterminated fenced code block")
    return classified


def _read_h1(lines: list[_Line], filename_id: str, path: str) -> str:
    first = next((i for i, (line, _) in enumerate(lines) if line.strip()), None)
    if first is None:
        raise TaskSpecError(f"{path}: spec is empty")
    first_text, first_fenced = lines[first]
    heading = None if first_fenced else _HEADING.match(first_text)
    if heading is None or len(heading.group(1)) != 1:
        raise TaskSpecError(
            f"{path}: the first non-blank line must be the H1 "
            "'# TSK-NNNN — <title>'"
        )
    h1 = _H1_TASK.fullmatch(heading.group(2))
    if h1 is None:
        raise TaskSpecError(
            f"{path}: H1 {heading.group(2)!r} does not match "
            "'TSK-NNNN — <title>' (a placeholder ID such as TSK-XXXX is not a "
            "task ID)"
        )
    if h1.group(1) != filename_id:
        raise TaskSpecError(
            f"{path}: H1 task ID {h1.group(1)} does not match the file name "
            f"task ID {filename_id}"
        )
    for line, fenced in lines[first + 1 :]:
        other = None if fenced else _HEADING.match(line)
        if other is not None and len(other.group(1)) == 1:
            raise TaskSpecError(
                f"{path}: a spec has exactly one level-1 heading; found "
                f"another: {line.strip()!r}"
            )
    return h1.group(2).strip()


def _split_sections(lines: list[_Line], path: str) -> dict[str, list[_Line]]:
    first = next(i for i, (line, _) in enumerate(lines) if line.strip())
    headings: list[tuple[int, str]] = []
    for index in range(first + 1, len(lines)):
        line, fenced = lines[index]
        match = None if fenced else _HEADING.match(line)
        if match is not None and len(match.group(1)) == 2:
            headings.append((index, match.group(2)))

    names = [name for _, name in headings]
    unknown = [name for name in names if name not in SPEC_SECTIONS]
    if unknown:
        raise TaskSpecError(
            f"{path}: unexpected section(s) {unknown}; a spec has exactly "
            f"these sections, in order: {list(SPEC_SECTIONS)}"
        )
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise TaskSpecError(f"{path}: duplicate section(s) {duplicates}")
    missing = [name for name in SPEC_SECTIONS if name not in names]
    if missing:
        raise TaskSpecError(f"{path}: missing required section(s) {missing}")
    if names != list(SPEC_SECTIONS):
        raise TaskSpecError(
            f"{path}: sections are out of order; expected {list(SPEC_SECTIONS)}, "
            f"found {names}"
        )

    if any(line.strip() for line, _ in lines[first + 1 : headings[0][0]]):
        raise TaskSpecError(
            f"{path}: content between the H1 and the first section is not "
            "part of any section"
        )

    bodies: dict[str, list[_Line]] = {}
    for position, (index, name) in enumerate(headings):
        end = headings[position + 1][0] if position + 1 < len(headings) else len(lines)
        bodies[name] = lines[index + 1 : end]
    return bodies


def _parse_checkpoints(body: list[_Line], path: str) -> tuple[ExecutionCheckpoint, ...]:
    blocks: list[tuple[int, str, list[_Line]]] = []
    for line, fenced in body:
        heading = None if fenced else _HEADING.match(line)
        if heading is not None and len(heading.group(1)) == 3:
            match = _CHECKPOINT_HEADING.match(line)
            if match is None:
                raise TaskSpecError(
                    f"{path}: malformed checkpoint heading {line.strip()!r}; "
                    "expected '### CP-N — <name>' with N sequential from 1"
                )
            blocks.append((int(match.group(1)), match.group(2), []))
            continue
        if not blocks:
            if line.strip():
                raise TaskSpecError(
                    f"{path}: 'Execution checkpoints' may contain only "
                    "'### CP-N' checkpoint blocks; found content before CP-1"
                )
            continue
        blocks[-1][2].append((line, fenced))

    if not blocks:
        raise TaskSpecError(f"{path}: 'Execution checkpoints' declares no checkpoint")
    seen: set[int] = set()
    for position, (number, _, _) in enumerate(blocks, start=1):
        if number in seen:
            raise TaskSpecError(f"{path}: duplicate checkpoint CP-{number}")
        seen.add(number)
        if number != position:
            raise TaskSpecError(
                f"{path}: checkpoints must be CP-1, CP-2, ... in order; "
                f"expected CP-{position}, found CP-{number}"
            )

    return tuple(
        _build_checkpoint(number, name, block, path) for number, name, block in blocks
    )


def _build_checkpoint(
    number: int, name: str, block: list[_Line], path: str
) -> ExecutionCheckpoint:
    label = f"CP-{number}"
    fields: dict[str, list[str]] = {}
    current: str | None = None
    for line, fenced in block:
        match = None if fenced else _CHECKPOINT_FIELD.match(line)
        if match is not None:
            current = match.group(1)
            if current in fields:
                raise TaskSpecError(f"{path}: {label} declares '{current}' more than once")
            fields[current] = [match.group(2)]
        elif current is None:
            if line.strip():
                raise TaskSpecError(
                    f"{path}: {label} has content before its first field; "
                    f"expected '- {CHECKPOINT_FIELDS[0]}:'"
                )
        else:
            fields[current].append(line)

    texts: dict[str, str] = {}
    for field in CHECKPOINT_FIELDS:
        if field not in fields:
            raise TaskSpecError(f"{path}: {label} is missing required field '{field}'")
        texts[field] = "\n".join(fields[field]).strip()
        if not texts[field]:
            raise TaskSpecError(f"{path}: {label} field '{field}' is empty")

    return ExecutionCheckpoint(
        number=number,
        checkpoint_id=label,
        name=name,
        objective=texts["Objective"],
        required_result=texts["Required result"],
        constraints=texts["Constraints"],
        verification=_parse_commands(texts["Verification"], path, f"{label} Verification"),
        review_focus=texts["Review focus"],
    )


def _parse_commands(text: str, path: str, where: str) -> tuple[VerificationArgv, ...]:
    commands: list[VerificationArgv] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("- "):
            line = line[2:].strip()
        try:
            decoded = json.loads(line)
        except json.JSONDecodeError as exc:
            raise TaskSpecError(
                f"{path}: {where} line {raw.strip()!r} is not a JSON argv array "
                "(shell command strings and prose are not accepted)"
            ) from exc
        if not isinstance(decoded, list) or not decoded:
            raise TaskSpecError(
                f"{path}: {where} command {raw.strip()!r} must be a non-empty "
                "JSON array of strings"
            )
        if not all(isinstance(item, str) for item in decoded):
            raise TaskSpecError(
                f"{path}: {where} command {raw.strip()!r} must contain only strings"
            )
        if not decoded[0].strip():
            raise TaskSpecError(
                f"{path}: {where} command {raw.strip()!r} has an empty or "
                "whitespace-only executable"
            )
        if any("\x00" in item for item in decoded):
            raise TaskSpecError(
                f"{path}: {where} command {raw.strip()!r} contains a NUL "
                "character, which no argv element may hold"
            )
        commands.append(tuple(decoded))
    if not commands:
        raise TaskSpecError(f"{path}: {where} declares no verification command")
    return tuple(commands)


def _reject_lifecycle_and_unresolved(piece: str, where: str, path: str) -> None:
    for line in piece.splitlines():
        label = _LIFECYCLE_LABEL.match(line)
        if label is not None:
            raise TaskSpecError(
                f"{path}: {where} carries the lifecycle field "
                f"'{label.group(1)}'; lifecycle facts live only in docs/TASK.md "
                "(Harness §22)"
            )
    marker = _UNRESOLVED_MARKER.search(piece)
    if marker is not None:
        raise TaskSpecError(
            f"{path}: {where} contains the unresolved placeholder/open-decision "
            f"marker {marker.group(0)!r}; the spec is not execution-ready"
        )
