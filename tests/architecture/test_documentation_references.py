import re
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import unquote, urlsplit


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CURRENT_CONTRACT_DOCUMENTS = (
    REPOSITORY_ROOT / "README.md",
    REPOSITORY_ROOT / "CLAUDE.md",
    REPOSITORY_ROOT / "docs" / "ROADMAP.md",
    REPOSITORY_ROOT / "docs" / "ARCHITECTURE.md",
    REPOSITORY_ROOT / "docs" / "DEFERRED.md",
)
ARCHITECTURE_REFERENCE_DOCUMENTS = CURRENT_CONTRACT_DOCUMENTS[:3]

MARKDOWN_LINK = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")
MARKDOWN_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$")
ARCHITECTURE_SECTION_HEADING = re.compile(
    r"^#{2,4}\s+(\d+(?:\.\d+)*)\.\s+"
)
ARCHITECTURE_SECTION_REFERENCE = re.compile(
    r"(?<![\w§])§(?P<section>\d+(?:\.\d+)*)"
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
