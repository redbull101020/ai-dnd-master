"""Deterministic Git/GitHub repository boundary for the AUTONOMOUS_PR harness.

This module owns every Git/GitHub side effect the orchestrator is
responsible for per ``AGENTS.md`` "Change authorisation and diff review"
and ``docs/AUTONOMOUS_PR_HARNESS.md`` §§4, 8: fetching, ref/SHA reads,
clean-worktree/branch/HEAD checks, delivery-branch creation from a freshly
fetched ``origin/main``, ``review.patch`` generation under the existing
A/B/C semantics, commit, push, and draft-PR/CI-check operations through
``gh``. Nothing in this module makes a gameplay, authorization, or review
decision — it only carries out already-decided, already-approved side
effects, and fails closed the moment a fact it depends on cannot be
positively established.

Hard prohibitions, enforced here rather than merely documented:

- never a direct write to ``main``/``master``;
- never a push of ``main``/``master``;
- never a push of any branch other than the invocation's own delivery
  branch;
- never a merge or auto-merge command, under any condition;
- no GitHub REST API fallback — a missing/unusable ``gh`` fails closed;
- never reads ``git credential``, ``.git-credentials``, or any other
  credential store;
- ``review.patch`` is never committed.

This module intentionally does not introduce a ``GitRepository`` interface
hierarchy, a provider framework, a workflow/event-bus framework, a generic
command-runner framework, or persisted orchestration state — none of those
are needed yet, and inventing them ahead of a second concrete need would
violate the same phase discipline the rest of this harness follows.
"""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Sequence

_PROTECTED_BRANCHES = frozenset({"main", "master"})
_DEFAULT_GH_COMMAND: tuple[str, ...] = ("gh",)
_DEFAULT_TIMEOUT_SECONDS = 60.0


class RepositoryError(Exception):
    """A deterministic repository/git/gh operation could not be completed safely.

    Raised for every fail-closed condition this module checks: missing or
    unusable required tooling, an operation that would touch a protected
    branch, a branch/ref fact that does not match what the caller expected,
    an ambiguous side effect (e.g. a timeout where success or failure
    cannot be distinguished), or a reviewed diff that no longer matches the
    working tree. The caller must treat this exactly like an ``AGENTS.md``
    "Fail-closed" condition — stop and require a human decision — and must
    never retry or guess at the outcome instead.
    """


class ReviewPurpose(Enum):
    """What one review.patch is being used for.

    Two purposes can share the identical ``origin/main...HEAD`` diff RANGE
    (``AGENTS.md`` "review.patch and diff ranges") while meaning different
    things: this enum keeps that distinction explicit in code rather than
    inventing a fourth diff range/mode to encode it.
    """

    CHECKPOINT = "checkpoint"
    PRE_CLOSURE_CUMULATIVE_REVIEW = "pre_closure_cumulative_review"
    FINAL_CUMULATIVE_AUDIT = "final_cumulative_audit"


_CUMULATIVE_PURPOSES = frozenset(
    {ReviewPurpose.PRE_CLOSURE_CUMULATIVE_REVIEW, ReviewPurpose.FINAL_CUMULATIVE_AUDIT}
)


@dataclass(frozen=True)
class ReviewPatch:
    """Evidence for exactly which diff was produced and what it covers.

    Proves which ``origin/main`` SHA (``base_sha``, when the range has
    one), branch, HEAD SHA, and diff text one review checkpoint
    corresponds to. ``digest`` is a narrow implementation detail — a plain
    sha256 of ``diff_text`` used only to detect whether the exact reviewed
    diff has since changed (:func:`verify_patch_unchanged`) — not an
    artifact-signing framework and not a new governance rule.
    """

    purpose: ReviewPurpose
    range_description: str
    base_sha: str | None
    head_sha: str
    branch: str
    diff_text: str
    digest: str


@dataclass(frozen=True)
class RepositoryFingerprint:
    """A snapshot of facts an external agent process must never change.

    Used to detect an implementer/reviewer process moving the branch or
    HEAD it was never given Git/GitHub write access to, or leaving behind
    unexpected worktree mutation (``docs/AUTONOMOUS_PR_HARNESS.md`` §§5,
    14). ``status_digest`` covers the full working-tree/index state, not
    just HEAD, so a mutation that never advances HEAD (e.g. an uncommitted
    stray edit) is still detected.
    """

    branch: str
    head_sha: str
    status_digest: str


def _run(
    args: Sequence[str], *, cwd: Path, timeout: float = _DEFAULT_TIMEOUT_SECONDS
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(args),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RepositoryError(f"required tool not found: {args[0]!r}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RepositoryError(
            f"{' '.join(args)!r} timed out after {timeout}s — treated as an "
            "ambiguous side effect: never retried and never assumed to "
            "have succeeded"
        ) from exc


def _git(repo: Path, args: Sequence[str], *, timeout: float = _DEFAULT_TIMEOUT_SECONDS) -> str:
    result = _run(["git", *args], cwd=repo, timeout=timeout)
    if result.returncode != 0:
        raise RepositoryError(
            f"git {' '.join(args)} failed (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )
    return result.stdout


def _gh(
    repo: Path,
    args: Sequence[str],
    *,
    gh_command: Sequence[str] = _DEFAULT_GH_COMMAND,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
) -> str:
    result = _run([*gh_command, *args], cwd=repo, timeout=timeout)
    if result.returncode != 0:
        raise RepositoryError(
            f"gh {' '.join(args)} failed (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )
    return result.stdout


def fetch_origin(repo: Path) -> None:
    """``git fetch origin``."""

    _git(repo, ["fetch", "origin"])


def resolve_sha(repo: Path, ref: str) -> str:
    """Resolve any ref/expression to its exact commit SHA."""

    return _git(repo, ["rev-parse", ref]).strip()


def head_sha(repo: Path) -> str:
    return resolve_sha(repo, "HEAD")


def origin_main_sha(repo: Path) -> str:
    return resolve_sha(repo, "origin/main")


def current_branch(repo: Path) -> str:
    return _git(repo, ["rev-parse", "--abbrev-ref", "HEAD"]).strip()


def is_worktree_clean(repo: Path) -> bool:
    return _git(repo, ["status", "--porcelain=v1"]).strip() == ""


def _require_clean_state(repo: Path, *, context: str) -> None:
    """Fail closed unless the worktree/index has no staged, unstaged, or
    untracked content.

    ``git diff <a>..<b>`` and ``git diff a...b`` are commit-to-commit
    ranges: unlike mode A, ``git add -N`` cannot make uncommitted content
    appear in them, so a dirty state here would silently produce an
    incomplete review artifact rather than fail loudly.
    """

    if not is_worktree_clean(repo):
        raise RepositoryError(
            f"working tree/index is not clean; refusing to build a "
            f"commit-to-commit diff ({context}) — uncommitted content "
            "would be silently excluded from the range rather than shown"
        )


def _ref_exists(repo: Path, ref: str) -> bool:
    """``git show-ref --verify --quiet <ref>``, interpreted strictly.

    Exit ``0`` means found, exit ``1`` means cleanly not-found. Any other
    exit code (a tool error, a malformed ref, etc.) is never silently
    treated as "not found" — it fails closed instead, since a branch
    existence check that can be fooled by a tool error is not a safe
    fail-closed guard.
    """

    result = _run(["git", "show-ref", "--verify", "--quiet", ref], cwd=repo)
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    raise RepositoryError(
        f"git show-ref --verify --quiet {ref} exited {result.returncode} "
        f"(neither a clean found nor not-found result): "
        f"{result.stderr.strip()}"
    )


def _branch_collision_exists(repo: Path, branch: str) -> bool:
    """True if ``branch`` already exists locally or on ``origin``.

    An existing remote branch is never treated as something to resume or
    reuse: a lost/crashed previous run must not be reconstructed from
    branch existence alone (``docs/AUTONOMOUS_PR_HARNESS.md`` §11) — both
    cases fail closed identically here.
    """

    return _ref_exists(repo, f"refs/heads/{branch}") or _ref_exists(
        repo, f"refs/remotes/origin/{branch}"
    )


def create_delivery_branch_from_origin_main(repo: Path, branch: str) -> str:
    """Fetch origin, require a clean worktree, then create ``branch`` from
    the freshly fetched ``origin/main``. Returns the base ``origin/main``
    SHA the branch was created from.

    Never touches ``main``/``master`` itself — it only ever creates a new
    branch pointing at ``origin/main``'s tip, and refuses to run at all if
    ``branch`` is itself a protected name, the worktree is not clean, or a
    branch of that name already exists either locally or on ``origin``
    (checked only after the fresh fetch, so a just-pushed remote branch is
    seen too).
    """

    if branch in _PROTECTED_BRANCHES:
        raise RepositoryError(f"refusing to use protected branch name {branch!r}")
    fetch_origin(repo)
    if not is_worktree_clean(repo):
        raise RepositoryError(
            "working tree is not clean; refusing to create a delivery branch"
        )
    if _branch_collision_exists(repo, branch):
        raise RepositoryError(
            f"branch {branch!r} already exists locally or on origin; "
            "refusing to reuse or resume a possibly stale or crashed prior "
            "run"
        )
    base_sha = origin_main_sha(repo)
    _git(repo, ["checkout", "-b", branch, "origin/main"])
    return base_sha


def intent_to_add_untracked_files(repo: Path) -> tuple[str, ...]:
    """Run ``git add -N`` for every currently untracked file.

    Without this, a brand-new file stays invisible to every diff range
    below (``AGENTS.md`` "review.patch and diff ranges", mode A) and would
    silently disappear from ``review.patch``. This marks content visible
    only — it is never authorization to stage or commit it.
    """

    status = _git(repo, ["status", "--porcelain=v1"])
    untracked: list[str] = []
    for line in status.splitlines():
        if not line.startswith("??"):
            continue
        path = line[3:].strip()
        if path.startswith('"') and path.endswith('"'):
            path = path[1:-1]
        untracked.append(path)
    for path in untracked:
        _git(repo, ["add", "-N", "--", path])
    return tuple(untracked)


def _build_review_patch(
    repo: Path,
    *,
    purpose: ReviewPurpose,
    range_description: str,
    base_sha: str | None,
    diff_text: str,
) -> ReviewPatch:
    return ReviewPatch(
        purpose=purpose,
        range_description=range_description,
        base_sha=base_sha,
        head_sha=head_sha(repo),
        branch=current_branch(repo),
        diff_text=diff_text,
        digest=hashlib.sha256(diff_text.encode("utf-8")).hexdigest(),
    )


def build_checkpoint_patch_uncommitted(repo: Path) -> ReviewPatch:
    """Mode A (``AGENTS.md``): a fresh, uncommitted checkpoint — ``git diff HEAD``."""

    intent_to_add_untracked_files(repo)
    diff_text = _git(repo, ["diff", "HEAD"])
    return _build_review_patch(
        repo,
        purpose=ReviewPurpose.CHECKPOINT,
        range_description="HEAD (uncommitted)",
        base_sha=None,
        diff_text=diff_text,
    )


def build_checkpoint_patch_committed(
    repo: Path, previous_checkpoint_sha: str
) -> ReviewPatch:
    """Mode B (``AGENTS.md``): a fresh, already-committed checkpoint —
    ``git diff <previous-reviewed-checkpoint-sha>..HEAD``.

    Requires a clean worktree/index first: this is a commit-to-commit
    range, so any staged/unstaged/untracked content would be silently
    excluded from it rather than shown.
    """

    _require_clean_state(repo, context="mode B")
    diff_text = _git(repo, ["diff", f"{previous_checkpoint_sha}..HEAD"])
    return _build_review_patch(
        repo,
        purpose=ReviewPurpose.CHECKPOINT,
        range_description=f"{previous_checkpoint_sha}..HEAD",
        base_sha=previous_checkpoint_sha,
        diff_text=diff_text,
    )


def build_cumulative_patch(repo: Path, purpose: ReviewPurpose) -> ReviewPatch:
    """``origin/main...HEAD``, freshly fetched first (``AGENTS.md`` mode C).

    The identical range serves two distinct purposes that must never be
    conflated: :attr:`ReviewPurpose.PRE_CLOSURE_CUMULATIVE_REVIEW` (built
    before Task Closure exists on the delivery branch, satisfies
    ``docs/TASK.md`` §18.1) and :attr:`ReviewPurpose.FINAL_CUMULATIVE_AUDIT`
    (mode C itself — built only after Task Closure is reviewed, committed,
    and pushed, and only after ``origin/main`` is freshly revalidated).
    This function refuses :attr:`ReviewPurpose.CHECKPOINT` — that purpose
    never uses this range, and this function never introduces a fourth
    range/mode to tell the two cumulative purposes apart.

    Requires a clean worktree/index after the fetch: this is a
    commit-to-commit range (``origin/main...HEAD``), so unlike mode A,
    ``git add -N`` cannot make uncommitted content appear in it — a dirty
    state would silently produce an incomplete review artifact rather than
    fail loudly, so this never calls
    :func:`intent_to_add_untracked_files` and fails closed instead.
    """

    if purpose not in _CUMULATIVE_PURPOSES:
        raise RepositoryError(
            f"build_cumulative_patch requires a cumulative ReviewPurpose, "
            f"got {purpose!r}"
        )
    fetch_origin(repo)
    _require_clean_state(repo, context=purpose.value)
    diff_text = _git(repo, ["diff", "origin/main...HEAD"])
    return _build_review_patch(
        repo,
        purpose=purpose,
        range_description="origin/main...HEAD",
        base_sha=origin_main_sha(repo),
        diff_text=diff_text,
    )


def verify_patch_unchanged(repo: Path, reviewed_patch: ReviewPatch) -> None:
    """Fail closed if the working diff no longer matches what was reviewed.

    Only meaningful for a :attr:`ReviewPurpose.CHECKPOINT` patch, checked
    immediately before it is committed — this is the mechanical check
    behind ``AGENTS.md``'s requirement that ``review.patch`` "must show
    exactly the slice being reviewed right now".

    Checks HEAD first, and independently of the diff digest: if HEAD has
    moved since ``reviewed_patch`` was built, the checkpoint is stale even
    if ``git diff HEAD`` happens to produce byte-identical text against the
    new HEAD (e.g. an unrelated external commit landed while the reviewed
    uncommitted content was untouched). This is never weakened to
    digest-only equivalence.
    """

    if reviewed_patch.purpose is not ReviewPurpose.CHECKPOINT:
        raise RepositoryError(
            "verify_patch_unchanged expects a CHECKPOINT-purpose ReviewPatch"
        )
    current_head = head_sha(repo)
    if current_head != reviewed_patch.head_sha:
        raise RepositoryError(
            f"HEAD has moved since review.patch was reviewed (reviewed "
            f"{reviewed_patch.head_sha!r}, now {current_head!r}); a stale "
            "checkpoint is never valid even if the working diff looks "
            "identical — rebuild and re-review review.patch before "
            "committing"
        )
    current = build_checkpoint_patch_uncommitted(repo)
    if current.digest != reviewed_patch.digest:
        raise RepositoryError(
            "the working diff has changed since review.patch was reviewed; "
            "rebuild and re-review review.patch before committing"
        )


def capture_fingerprint(repo: Path) -> RepositoryFingerprint:
    status = _git(repo, ["status", "--porcelain=v1"])
    return RepositoryFingerprint(
        branch=current_branch(repo),
        head_sha=head_sha(repo),
        status_digest=hashlib.sha256(status.encode("utf-8")).hexdigest(),
    )


def verify_fingerprint_unchanged(
    repo: Path, expected: RepositoryFingerprint, *, context: str
) -> None:
    """Fail closed if branch/HEAD/worktree moved since ``expected`` was captured.

    ``context`` names what just ran (e.g. ``"reviewer invocation"``) so the
    error is actionable. An implementer/reviewer process is never given
    Git/GitHub write access by this module, so any movement detected here
    means something outside this module's control mutated the repository.
    """

    current = capture_fingerprint(repo)
    if current != expected:
        raise RepositoryError(
            f"repository state changed unexpectedly during {context}: "
            f"expected {expected!r}, found {current!r}"
        )


def commit_reviewed_checkpoint(
    repo: Path,
    *,
    reviewed_patch: ReviewPatch,
    message: str,
    paths: Sequence[str],
) -> str:
    """Commit exactly the reviewed checkpoint. Returns the new commit SHA.

    Fails closed unless: the current branch matches what was reviewed and
    is not a protected branch; HEAD and the working diff still exactly
    match ``reviewed_patch`` (nothing changed since review, see
    :func:`verify_patch_unchanged`); ``review.patch`` is not among
    ``paths`` (an early, caller-facing error); the repository-root
    ``review.patch`` is not present in the *factual staged path set* after
    staging — checked directly against the index via
    ``git diff --cached --name-only HEAD`` rather than trusted from
    ``paths``, since a ``review.patch`` staged by something else entirely
    (e.g. an out-of-band ``git add -f review.patch``) would otherwise slip
    through even though it was never named in ``paths``; and, after
    staging ``paths``, the staged diff is byte-identical to
    ``reviewed_patch.diff_text`` with nothing left unstaged. That last
    check is what stops ``paths`` from silently committing a different
    composition than what was reviewed — a subset (an omitted reviewed
    file), a superset (an extra unreviewed file), or anything left behind
    uncommitted.
    """

    branch = current_branch(repo)
    if branch in _PROTECTED_BRANCHES:
        raise RepositoryError(
            f"refusing to commit directly to protected branch {branch!r}"
        )
    if branch != reviewed_patch.branch:
        raise RepositoryError(
            f"current branch {branch!r} does not match the reviewed branch "
            f"{reviewed_patch.branch!r}"
        )
    if any(Path(path).name == "review.patch" for path in paths):
        raise RepositoryError("refusing to commit review.patch")
    verify_patch_unchanged(repo, reviewed_patch)

    _git(repo, ["add", "--", *paths])

    staged_paths = _git(
        repo, ["diff", "--cached", "--name-only", "HEAD"]
    ).splitlines()
    if "review.patch" in staged_paths:
        raise RepositoryError(
            "refusing to commit: repository-root 'review.patch' is present "
            "in the staged commit composition, even though it was not "
            "named in `paths` — review.patch must never be committed, "
            "regardless of how it came to be staged (e.g. a pre-staged or "
            "force-added review.patch)"
        )

    staged_diff = _git(repo, ["diff", "--cached", "HEAD"])
    if staged_diff != reviewed_patch.diff_text:
        raise RepositoryError(
            "the staged diff does not exactly match the reviewed "
            "checkpoint; refusing to commit a different composition "
            "(an omitted reviewed file or an extra unreviewed file) than "
            "what was reviewed"
        )
    total_diff = _git(repo, ["diff", "HEAD"])
    if total_diff != staged_diff:
        raise RepositoryError(
            "unstaged or untracked content remains beyond the reviewed "
            "checkpoint after staging; refusing to commit a partial "
            "composition"
        )

    _git(repo, ["commit", "-m", message])
    return head_sha(repo)


def push_delivery_branch(repo: Path, *, branch: str, expected_branch: str) -> None:
    """Push ``branch`` to origin.

    Never pushes ``main``/``master``, and never pushes anything other than
    the invocation's own delivery branch (``expected_branch``). A push
    whose outcome cannot be positively confirmed (timeout, tool failure)
    raises :class:`RepositoryError` rather than being retried or assumed
    to have succeeded.
    """

    if branch in _PROTECTED_BRANCHES:
        raise RepositoryError(f"refusing to push protected branch {branch!r}")
    if branch != expected_branch:
        raise RepositoryError(
            f"refusing to push {branch!r}; only the delivery branch "
            f"{expected_branch!r} may be pushed"
        )
    if current_branch(repo) != branch:
        raise RepositoryError(
            f"current branch {current_branch(repo)!r} does not match "
            f"{branch!r}; refusing to push"
        )
    _git(repo, ["push", "origin", branch])


def create_draft_pull_request(
    repo: Path,
    *,
    title: str,
    body: str,
    head: str,
    expected_branch: str,
    base: str = "main",
    gh_command: Sequence[str] = _DEFAULT_GH_COMMAND,
) -> str:
    """Create a draft PR via ``gh pr create --draft``. Returns the PR URL.

    Restricted exactly like :func:`push_delivery_branch`: ``head`` must
    equal ``expected_branch`` — the invocation's own delivery branch — and
    the current local branch must match it too; a protected branch is
    refused as ``head`` either way. ``base`` must be exactly ``"main"``:
    v1 never opens a PR against a caller-selected base. No GitHub REST API
    fallback exists anywhere in this module: a missing or unusable ``gh``
    fails closed (``AGENTS.md`` "Pull requests and merge").
    """

    if head in _PROTECTED_BRANCHES:
        raise RepositoryError(f"refusing to open a PR from protected branch {head!r}")
    if head != expected_branch:
        raise RepositoryError(
            f"refusing to open a PR for {head!r}; only the delivery branch "
            f"{expected_branch!r} may be used"
        )
    if current_branch(repo) != expected_branch:
        raise RepositoryError(
            f"current branch {current_branch(repo)!r} does not match "
            f"{expected_branch!r}; refusing to open a PR"
        )
    if base != "main":
        raise RepositoryError(
            f"refusing to open a PR against base {base!r}; v1 only ever "
            "targets 'main'"
        )
    output = _gh(
        repo,
        [
            "pr",
            "create",
            "--draft",
            "--base",
            base,
            "--head",
            head,
            "--title",
            title,
            "--body",
            body,
        ],
        gh_command=gh_command,
    )
    return output.strip()


def pr_checks(
    repo: Path, pr_number: str, *, gh_command: Sequence[str] = _DEFAULT_GH_COMMAND
) -> str:
    """Raw ``gh pr checks <number>`` output.

    Deliberately unparsed: structured CI-driven repair/replay logic is out
    of scope for this checkpoint. This is only the narrow ``gh``-invocation
    hook a later orchestrator builds on when it needs it.
    """

    return _gh(repo, ["pr", "checks", pr_number], gh_command=gh_command)
