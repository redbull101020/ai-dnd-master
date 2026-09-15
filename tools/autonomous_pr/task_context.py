"""Narrow, deterministic ``docs/TASK.md`` parsing/revalidation support.

This module answers exactly one question: is the named task still a valid,
unblocked, authoritative execution target on a freshly fetched
``docs/TASK.md``? It is deliberately not a general Markdown AST/parser and
not a permanent historical task database — it reads the specific fields
``docs/TASK.md`` §§10, 11, 15, 19 already define a fixed textual shape for,
and nothing else. Semantic implementation-plan judgement (whether the task
makes sense to implement, how to implement it) remains for the
implementer/reviewer roles, never for this parser.

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

from . import repository
from .model import TaskContext, TaskStatus

_TASK_ID = r"TSK-\d{4,}"

_ANY_HEADING = re.compile(r"^#{1,2}\s", re.MULTILINE)
_LEVEL_ONE_HEADING = re.compile(r"^#\s", re.MULTILINE)
_HORIZONTAL_RULE = re.compile(r"^-{3,}\s*$", re.MULTILINE)
_CURRENT_POSITION_HEADING = re.compile(r"^#\s+Current position\s*$", re.MULTILINE)
_OPEN_TASK_INDEX_HEADING = re.compile(r"^#\s+Open task index\s*$", re.MULTILINE)
_OPEN_TASK_DETAILS_HEADING = re.compile(r"^#\s+Open task details\s*$", re.MULTILINE)
_RECENTLY_COMPLETED_HEADING = re.compile(r"^#\s+Recently completed\s*$", re.MULTILINE)
_CURRENT_LINE = re.compile(r"^-\s*\*\*Current:\*\*\s*(.+?)\s*$", re.MULTILINE)
_STATUS_FIELD = re.compile(r"\*\*Status:\*\*\s*`(\w+)`")
_ROADMAP_TARGET_FIELD = re.compile(
    r"^\*\*Roadmap target:\*\*[ \t]*([^\r\n]*)$", re.MULTILINE
)
_DEPENDS_ON_FIELD = re.compile(r"\*\*Depends on:\*\*(.*?)(?:\n\s*\n|\Z)", re.DOTALL)
_DEPENDS_ON_NONE = "—"
_DEPENDS_ON_TOKEN = re.compile(rf"`({_TASK_ID})`")
_OPEN_TASK_INDEX_ROW = re.compile(
    rf"^\|\s*`({_TASK_ID})`\s*\|\s*`(\w+)`\s*\|", re.MULTILINE
)
_RECENTLY_COMPLETED_ROW = re.compile(rf"^\|\s*`({_TASK_ID})`\s*\|", re.MULTILINE)


class TaskRevalidationError(Exception):
    """The named task is not currently a valid execution target.

    Raised for every mechanically determinable fail-closed condition this
    module checks: wrong/missing Current pointer, a missing/duplicate/
    inconsistent Open task index row, missing/duplicated/inconsistent task
    detail, a missing or duplicated Roadmap target or Depends on field, or
    a dependency whose Done status cannot be positively established from
    current v1 evidence. A single-valued execution fact this module relies
    on is never resolved by silently taking the first regex match when more
    than one authoritative value is present — ambiguity fails closed the
    same as absence. The caller must treat this exactly like an
    ``AGENTS.md`` "Fail-closed" condition — stop and require a human
    decision — never route around it.
    """


def load_task_queue_text_at_ref(repo: Path, ref: str) -> str:
    """Read the authoritative ``docs/TASK.md`` text as it exists at ``ref``.

    Delegates to :func:`.repository.read_file_at_ref` (``git show
    <ref>:docs/TASK.md``) rather than reading the local working tree: a
    clean local branch can still be stale or different from
    ``origin/main``, so preflight revalidation must never trust the local
    filesystem's ``docs/TASK.md`` (``docs/AUTONOMOUS_PR_HARNESS.md`` §3). No
    parsing happens here.
    """

    return repository.read_file_at_ref(repo, ref, "docs/TASK.md")


def revalidate_current_task(task_queue_text: str, task_id: str) -> TaskContext:
    """Revalidate that ``task_id`` is the authoritative ``Current`` task.

    Raises :class:`TaskRevalidationError` unless all of the following hold
    on ``task_queue_text``, each checked only against its real, unnumbered,
    authoritative section (``docs/TASK.md`` repeats these heading texts as
    illustrative prose inside numbered documentation sections too — those
    never count):

    - the ``# Current position`` section has exactly one ``**Current:**``
      field, and it names exactly ``task_id``;
    - the ``# Open task index`` table contains exactly one row for
      ``task_id``, and that row's Status reads ``Current`` (§11);
    - exactly one ``## <task_id> — ...`` section exists inside ``# Open
      task details`` for it — a same-named heading anywhere else, or a
      duplicated heading inside that section, does not count;
    - that section has exactly one ``**Status:**`` field, and it reads
      ``Current``;
    - that section has exactly one non-empty ``**Roadmap target:**`` field;
    - that section has exactly one ``**Depends on:**`` field — a missing
      field fails closed rather than being read as "no dependencies" — and
      its content is narrowly valid: either the literal ``—`` (no
      dependencies) or one or more comma-separated, backtick-wrapped
      ``TSK-*`` ids; anything else (unrelated text, or an id mixed with
      extra content) fails closed instead of being silently reduced to
      whatever ``TSK-*`` substrings happen to be findable in it;
    - every dependency id found that way can be positively confirmed
      authoritative ``Done`` from the ``# Recently completed`` table. That
      table retains only the last ten completions (§19), so a dependency's
      *absence* there does not prove it is not Done historically — v1 is
      deliberately conservative and fails closed whenever it cannot
      positively confirm Done, rather than inferring "not Done" from
      absence.

    Every field above that this module relies on for a single value fails
    closed on ambiguity too: finding more than one authoritative value
    raises :class:`TaskRevalidationError` rather than silently accepting
    the first regex match.
    """

    current_task_id = _current_pointer(task_queue_text)
    if current_task_id != task_id:
        raise TaskRevalidationError(
            f"{task_id!r} is not the authoritative Current task "
            f"(Current position records {current_task_id!r})"
        )

    _require_current_index_row(task_queue_text, task_id)

    detail_section = _find_detail_section(task_queue_text, task_id)
    if detail_section is None:
        raise TaskRevalidationError(
            f"no '{task_id}' section found inside the authoritative "
            "'# Open task details'"
        )
    detail_text, detail_block = detail_section

    status = _require_current_status(detail_block, task_id)
    roadmap_target = _require_roadmap_target(detail_block, task_id)
    depends_on = _require_depends_on(detail_block, task_id)
    _require_dependencies_done(task_queue_text, task_id, depends_on)

    return TaskContext(
        task_id=task_id,
        status=status,
        roadmap_target=roadmap_target,
        depends_on=depends_on,
        detail_text=detail_text,
    )


def _section_after(
    text: str, heading: re.Pattern[str], boundary: re.Pattern[str] = _ANY_HEADING
) -> str:
    """Slice the text between one exact heading and the next ``boundary`` heading.

    ``docs/TASK.md`` repeats several heading texts verbatim: once as
    illustrative prose inside a numbered documentation section (e.g.
    ``## 10. Current position``), and once as the real, unnumbered,
    authoritative section near the end of the file (``# Current position``).
    Only the latter carries live facts, so every lookup here is scoped to
    one exact heading match rather than searched globally.

    ``boundary`` defaults to the next heading of level 1 or 2. ``# Open
    task details`` is the one authoritative section that legitimately
    contains its own level-2 (``## TSK-XXXX``) subheadings as content, so
    its caller passes :data:`_LEVEL_ONE_HEADING` instead — stopping only at
    the next level-1 heading — so the section body is not truncated at its
    own first task subheading.
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
    with the caller. Raises :class:`TaskRevalidationError` when more than
    one match exists: an ambiguous single-valued execution fact must fail
    closed rather than silently resolve to the first match found.
    """

    matches = list(pattern.finditer(text))
    if len(matches) > 1:
        raise TaskRevalidationError(
            f"{description} is ambiguous: found {len(matches)} matches, "
            "expected at most one"
        )
    return matches[0] if matches else None


def _current_pointer(task_queue_text: str) -> str | None:
    section = _section_after(task_queue_text, _CURRENT_POSITION_HEADING)
    match = _require_single_match(
        _CURRENT_LINE, section, "the '# Current position' Current field"
    )
    if match is None:
        return None
    return match.group(1).strip()


def _require_current_index_row(task_queue_text: str, task_id: str) -> None:
    section = _section_after(task_queue_text, _OPEN_TASK_INDEX_HEADING)
    rows = [
        (found_id, found_status)
        for found_id, found_status in _OPEN_TASK_INDEX_ROW.findall(section)
        if found_id == task_id
    ]
    if not rows:
        raise TaskRevalidationError(
            f"{task_id!r} has no row in the authoritative Open task index"
        )
    if len(rows) > 1:
        raise TaskRevalidationError(
            f"{task_id!r} has {len(rows)} rows in the authoritative Open "
            "task index; expected exactly one"
        )
    raw_status = rows[0][1]
    try:
        index_status = TaskStatus(raw_status)
    except ValueError as exc:
        raise TaskRevalidationError(
            f"{task_id!r} Open task index row has an unrecognized Status "
            f"value {raw_status!r}"
        ) from exc
    if index_status is not TaskStatus.CURRENT:
        raise TaskRevalidationError(
            f"{task_id!r} Open task index row Status reads "
            f"{index_status.value!r}, not 'Current'"
        )


def _find_detail_section(
    task_queue_text: str, task_id: str
) -> tuple[str, str] | None:
    """Locate the task's authoritative detail section.

    Returns ``(full_text, body_text)`` — ``full_text`` is the exact
    heading-and-body text (``## <task_id> — ...`` through its Goal, Scope,
    Out of scope, Acceptance criteria, Verification, and anything else the
    section happens to contain), used verbatim as explicit handoff evidence
    (:attr:`.model.TaskContext.detail_text`, §6). ``body_text`` is the
    heading-less remainder the narrow field extractors below search within,
    unchanged from before this field was added. Returns ``None`` when no
    such section exists.

    The section ends at the next heading (as before) or at the next
    ``docs/TASK.md`` horizontal-rule section separator (``---`` alone on
    its line), whichever comes first: when a task's detail is the last one
    inside ``# Open task details`` (the common case — real usage currently
    has exactly one), nothing but that separator marks where its own
    content ends before ``# Recently completed`` begins, so without this
    the captured text would trail off into the next section's separator
    rather than stopping at the task's own content.
    """

    section = _section_after(
        task_queue_text, _OPEN_TASK_DETAILS_HEADING, boundary=_LEVEL_ONE_HEADING
    )
    heading = re.compile(rf"^##\s+{re.escape(task_id)}\s+—.*$", re.MULTILINE)
    match = _require_single_match(
        heading, section, f"{task_id!r} detail heading inside '# Open task details'"
    )
    if match is None:
        return None
    start_of_heading = match.start()
    start_of_body = match.end()
    end = len(section)
    next_heading = _ANY_HEADING.search(section, pos=start_of_body)
    if next_heading is not None:
        end = min(end, next_heading.start())
    horizontal_rule = _HORIZONTAL_RULE.search(section, pos=start_of_body)
    if horizontal_rule is not None:
        end = min(end, horizontal_rule.start())
    full_text = section[start_of_heading:end].strip("\n")
    body_text = section[start_of_body:end]
    return full_text, body_text


def _require_current_status(detail_block: str, task_id: str) -> TaskStatus:
    match = _require_single_match(
        _STATUS_FIELD, detail_block, f"{task_id!r} detail Status field"
    )
    if match is None:
        raise TaskRevalidationError(
            f"{task_id!r} detail is missing a required Status field"
        )
    raw_status = match.group(1)
    try:
        status = TaskStatus(raw_status)
    except ValueError as exc:
        raise TaskRevalidationError(
            f"{task_id!r} detail has an unrecognized Status value "
            f"{raw_status!r}"
        ) from exc
    if status is not TaskStatus.CURRENT:
        raise TaskRevalidationError(
            f"{task_id!r} detail Status reads {status.value!r}, not 'Current'"
        )
    return status


def _require_roadmap_target(detail_block: str, task_id: str) -> str:
    match = _require_single_match(
        _ROADMAP_TARGET_FIELD, detail_block, f"{task_id!r} detail Roadmap target field"
    )
    roadmap_target = match.group(1).strip() if match is not None else ""
    if not roadmap_target or roadmap_target == "—":
        raise TaskRevalidationError(
            f"{task_id!r} detail is missing a required Roadmap target"
        )
    return roadmap_target


def _require_depends_on(detail_block: str, task_id: str) -> tuple[str, ...]:
    """Require exactly one ``**Depends on:**`` field with narrowly valid content.

    Only two forms count, matching ``docs/TASK.md``'s own template
    (``**Depends on:** \\`TSK-XXXX\\` or \\`—\\``) and real usage
    (``**Depends on:** \\`TSK-0025\\```): the literal ``—`` (no
    dependencies), or one or more comma-separated, backtick-wrapped
    ``TSK-*`` ids. Anything else — unrelated text, or a valid id mixed with
    extra content — is rejected outright rather than silently reduced to
    whatever ``TSK-*`` substrings happen to be findable in it: a
    ``re.findall``-style extraction would treat malformed content
    (e.g. ``unknown``) the same as an explicit empty dependency list, which
    is unsafe for a preflight gate.
    """

    match = _require_single_match(
        _DEPENDS_ON_FIELD, detail_block, f"{task_id!r} detail Depends on field"
    )
    if match is None:
        raise TaskRevalidationError(
            f"{task_id!r} detail is missing a required Depends on field "
            "(a missing field is never read as 'no dependencies')"
        )

    raw_value = match.group(1).strip()
    if raw_value == _DEPENDS_ON_NONE:
        return ()

    dependency_ids: list[str] = []
    for token in raw_value.split(","):
        token_match = _DEPENDS_ON_TOKEN.fullmatch(token.strip())
        if token_match is None:
            raise TaskRevalidationError(
                f"{task_id!r} detail Depends on field has malformed content "
                f"{raw_value!r}; expected {_DEPENDS_ON_NONE!r} or one or "
                "more comma-separated `TSK-*` ids in backticks"
            )
        dependency_ids.append(token_match.group(1))
    return tuple(dependency_ids)


def _require_dependencies_done(
    task_queue_text: str, task_id: str, depends_on: tuple[str, ...]
) -> None:
    """Fail closed unless every dependency's Done status is positively confirmed.

    ``docs/TASK.md`` §19 keeps only the last ten completions in ``#
    Recently completed``, so a dependency id's *absence* from that table
    never proves the dependency is not Done — it only means v1's current
    evidence cannot positively confirm it. Either way the mechanical result
    here is the same: fail closed, since correct behaviour cannot be
    determined from already-approved contracts (``AGENTS.md``
    "Fail-closed"). Resolving a dependency against fuller history (e.g.
    Git/``DEVELOPMENT_LOG.md``) is explicitly out of scope for this
    checkpoint.
    """

    section = _section_after(task_queue_text, _RECENTLY_COMPLETED_HEADING)
    confirmed_done_ids = frozenset(_RECENTLY_COMPLETED_ROW.findall(section))
    unconfirmed = tuple(dep for dep in depends_on if dep not in confirmed_done_ids)
    if unconfirmed:
        raise TaskRevalidationError(
            f"{task_id!r} has dependencies whose authoritative Done status "
            "could not be positively established from current v1 "
            "docs/TASK.md evidence (not found in the last-ten-completions "
            f"'# Recently completed' table): {', '.join(unconfirmed)}"
        )
