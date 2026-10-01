import re
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import unquote, urlsplit

from tools.autonomous_pr.model import ApprovedTaskDocument
from tools.autonomous_pr.task_spec import TaskSpecError, parse_task_document


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CURRENT_CONTRACT_DOCUMENTS = (
    REPOSITORY_ROOT / "AGENTS.md",
    REPOSITORY_ROOT / "README.md",
    REPOSITORY_ROOT / "CLAUDE.md",
    REPOSITORY_ROOT / "docs" / "TASK.md",
    REPOSITORY_ROOT / "docs" / "AUTONOMOUS_PR_HARNESS.md",
    REPOSITORY_ROOT / "docs" / "ROADMAP.md",
    REPOSITORY_ROOT / "docs" / "ARCHITECTURE.md",
    REPOSITORY_ROOT / "docs" / "DEFERRED.md",
)
ARCHITECTURE_REFERENCE_DOCUMENTS = (
    REPOSITORY_ROOT / "README.md",
    REPOSITORY_ROOT / "CLAUDE.md",
    REPOSITORY_ROOT / "docs" / "ROADMAP.md",
)
TASK_DOCUMENTS = REPOSITORY_ROOT / "docs" / "tasks"

MARKDOWN_LINK = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")
MARKDOWN_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$")
ARCHITECTURE_SECTION_HEADING = re.compile(
    r"^#{2,4}\s+(\d+(?:\.\d+)*)\.\s+"
)
ARCHITECTURE_SECTION_REFERENCE = re.compile(
    r"(?<![\w§])§(?P<section>\d+(?:\.\d+)*)"
)
ARCHITECTURE_REFERENCE_CONTEXT = re.compile(
    r"(?:ARCHITECTURE\.md|\bArchitecture\b)", re.IGNORECASE
)
DECISION_HEADING = re.compile(r"^##\s+(?P<decision>DEC-\d{4})\s+—\s+")
DECISION_REFERENCE = re.compile(
    r"(?<![\w-])(?P<decision>DEC-\d{4})(?!\d)"
)


def _outside_fenced_blocks(text: str) -> Iterator[str]:
    fence_character: str | None = None
    fence_length = 0
    for line in text.splitlines():
        fence = re.match(r"^\s*(`{3,}|~{3,})", line)
        if fence is not None:
            marker = fence.group(1)
            if fence_character is None:
                fence_character = marker[0]
                fence_length = len(marker)
            elif marker[0] == fence_character and len(marker) >= fence_length:
                fence_character = None
                fence_length = 0
            continue
        if fence_character is None:
            yield line


def _github_anchor(heading: str) -> str:
    without_links = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", heading)
    without_markup = without_links.replace("`", "").strip().lower()
    return re.sub(r"[^\w\- ]", "", without_markup).replace(" ", "-")


def _heading_anchors(document: Path) -> set[str]:
    anchors: set[str] = set()
    duplicate_counts: dict[str, int] = {}
    text = document.read_text(encoding="utf-8")
    for line in _outside_fenced_blocks(text):
        match = MARKDOWN_HEADING.match(line)
        if match is None:
            continue
        base_anchor = _github_anchor(match.group(1))
        duplicate_number = duplicate_counts.get(base_anchor, 0)
        anchor = (
            base_anchor
            if duplicate_number == 0
            else f"{base_anchor}-{duplicate_number}"
        )
        duplicate_counts[base_anchor] = duplicate_number + 1
        anchors.add(anchor)
    return anchors


def _markdown_hrefs(document: Path) -> Iterator[str]:
    text = document.read_text(encoding="utf-8")
    for line in _outside_fenced_blocks(text):
        for match in MARKDOWN_LINK.finditer(line):
            yield match.group(1).strip()


def _approved_task_reference_errors(
    source_name: str,
    task_text: str,
    *,
    architecture_sections: set[str],
    decisions: set[str],
) -> list[str]:
    try:
        document = parse_task_document(task_text, source_name)
    except TaskSpecError:
        return []
    if not isinstance(document, ApprovedTaskDocument):
        return []

    lines = tuple(_outside_fenced_blocks(task_text))
    text = "\n".join(lines)
    errors: list[str] = []
    for line in lines:
        if ARCHITECTURE_REFERENCE_CONTEXT.search(line) is None:
            continue
        for match in ARCHITECTURE_SECTION_REFERENCE.finditer(line):
            section = match.group("section")
            if section not in architecture_sections:
                errors.append(
                    f"{source_name}: broken reference §{section}; expected "
                    f"numbered section §{section} in docs/ARCHITECTURE.md"
                )
    for match in DECISION_REFERENCE.finditer(text):
        decision = match.group("decision")
        if decision not in decisions:
            errors.append(
                f"{source_name}: broken reference {decision}; expected "
                f"decision heading {decision} in docs/DECISIONS.md"
            )
    return errors


def _task_document(approval: str, references: str) -> str:
    return f'''# TSK-9999 — Reference fixture

## Task metadata

```json
{{
  "execution_approval": "{approval}",
  "priority": "P2",
  "size": "S",
  "roadmap_target": "Synthetic target",
  "depends_on": [],
  "group": "engineering"
}}
```

## Goal

Validate canonical references.

## Context / References

{references}

## Scope

- test scope

## Out of scope

- production behavior

## Approved implementation approach

Use existing canonical documents.

## Acceptance criteria

- references resolve

## Execution checkpoints

### CP-1 — Validate
- Objective: Validate references.
- Required result: References resolve.
- Constraints: No production writes.
- Verification: ["python", "-m", "pytest", "tests/architecture"]
- Review focus: Canonical references.

## Full verification

["python", "-m", "pytest", "tests/architecture"]

## Known constraints / edge cases

Synthetic only.
'''


def test_current_contract_local_markdown_links_resolve() -> None:
    errors: list[str] = []
    anchor_cache: dict[Path, set[str]] = {}

    for source in CURRENT_CONTRACT_DOCUMENTS:
        for href in _markdown_hrefs(source):
            parsed = urlsplit(href)
            if parsed.scheme in {"http", "https", "mailto"}:
                continue
            if parsed.scheme or parsed.netloc:
                continue

            target = (
                source
                if not parsed.path
                else (source.parent / unquote(parsed.path)).resolve()
            )
            source_name = source.relative_to(REPOSITORY_ROOT).as_posix()
            expected_target = target.relative_to(REPOSITORY_ROOT).as_posix()
            if not target.is_file():
                errors.append(
                    f"{source_name}: broken link {href!r}; "
                    f"expected file {expected_target}"
                )
                continue

            if parsed.fragment:
                anchors = anchor_cache.setdefault(target, _heading_anchors(target))
                fragment = unquote(parsed.fragment)
                if fragment not in anchors:
                    errors.append(
                        f"{source_name}: broken link {href!r}; expected heading "
                        f"#{fragment} in {expected_target}"
                    )

    assert errors == [], "\n" + "\n".join(errors)


def test_current_architecture_section_references_exist() -> None:
    architecture = REPOSITORY_ROOT / "docs" / "ARCHITECTURE.md"
    sections = {
        match.group(1)
        for line in _outside_fenced_blocks(architecture.read_text(encoding="utf-8"))
        if (match := ARCHITECTURE_SECTION_HEADING.match(line)) is not None
    }
    errors: list[str] = []

    for source in ARCHITECTURE_REFERENCE_DOCUMENTS:
        source_name = source.relative_to(REPOSITORY_ROOT).as_posix()
        text = "\n".join(_outside_fenced_blocks(source.read_text(encoding="utf-8")))
        for match in ARCHITECTURE_SECTION_REFERENCE.finditer(text):
            section = match.group("section")
            if section not in sections:
                errors.append(
                    f"{source_name}: broken reference §{section}; expected "
                    f"numbered section §{section} in docs/ARCHITECTURE.md"
                )

    assert errors == [], "\n" + "\n".join(errors)


def test_approved_task_canonical_references_exist() -> None:
    architecture_text = (
        REPOSITORY_ROOT / "docs" / "ARCHITECTURE.md"
    ).read_text(encoding="utf-8")
    architecture_sections = {
        match.group(1)
        for line in _outside_fenced_blocks(architecture_text)
        if (match := ARCHITECTURE_SECTION_HEADING.match(line)) is not None
    }
    decisions_text = (
        REPOSITORY_ROOT / "docs" / "DECISIONS.md"
    ).read_text(encoding="utf-8")
    decisions = {
        match.group("decision")
        for line in _outside_fenced_blocks(decisions_text)
        if (match := DECISION_HEADING.match(line)) is not None
    }
    errors: list[str] = []

    for source in sorted(TASK_DOCUMENTS.glob("TSK-*.md")):
        source_name = source.relative_to(REPOSITORY_ROOT).as_posix()
        errors.extend(
            _approved_task_reference_errors(
                source_name,
                source.read_text(encoding="utf-8"),
                architecture_sections=architecture_sections,
                decisions=decisions,
            )
        )

    assert errors == [], "\n" + "\n".join(errors)


def test_approved_task_rejects_missing_architecture_section() -> None:
    errors = _approved_task_reference_errors(
        "docs/tasks/TSK-9999.md",
        _task_document("approved", "Architecture §3.37 and DEC-0052."),
        architecture_sections={"3.36"},
        decisions={"DEC-0052"},
    )

    assert errors == [
        "docs/tasks/TSK-9999.md: broken reference §3.37; expected "
        "numbered section §3.37 in docs/ARCHITECTURE.md"
    ]


def test_approved_task_rejects_missing_decision() -> None:
    errors = _approved_task_reference_errors(
        "docs/tasks/TSK-9999.md",
        _task_document("approved", "Architecture §3.37 and DEC-0053."),
        architecture_sections={"3.37"},
        decisions={"DEC-0052"},
    )

    assert errors == [
        "docs/tasks/TSK-9999.md: broken reference DEC-0053; expected "
        "decision heading DEC-0053 in docs/DECISIONS.md"
    ]


def test_approved_task_accepts_existing_canonical_references() -> None:
    errors = _approved_task_reference_errors(
        "docs/tasks/TSK-9999.md",
        _task_document("approved", "Architecture §3.37 and DEC-0053."),
        architecture_sections={"3.37"},
        decisions={"DEC-0053"},
    )

    assert errors == []


def test_draft_task_may_reference_future_canonical_records() -> None:
    errors = _approved_task_reference_errors(
        "docs/tasks/TSK-9999.md",
        _task_document("draft", "Future Architecture §9.99 and DEC-9999."),
        architecture_sections=set(),
        decisions=set(),
    )

    assert errors == []


def test_autonomous_pr_documents_declare_one_operational_v2_contract() -> None:
    agents = (REPOSITORY_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    harness = (REPOSITORY_ROOT / "docs" / "AUTONOMOUS_PR_HARNESS.md").read_text(
        encoding="utf-8"
    )
    claude = (REPOSITORY_ROOT / "CLAUDE.md").read_text(encoding="utf-8")

    assert "Operational `AUTONOMOUS_PR` contract: v2" in agents
    assert "# Part II — Operational v2 contract" in harness
    assert "v1 runtime flow/mechanics are historical" in harness
    assert "incorporates them by reference" in harness
    assert "только v2" in claude
    assert "Operational `AUTONOMOUS_PR` contract: v1" not in agents
    assert "approved, inactive" not in harness
