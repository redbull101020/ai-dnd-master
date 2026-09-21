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
import json
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Sequence

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
class BranchHead:
    """The narrow (branch, HEAD SHA) pair the orchestrator checks around an
    implementer invocation.

    Deliberately narrower than :class:`RepositoryFingerprint`: an
    implementer is expected to edit working-tree content (that is its job),
    so only branch/HEAD movement — not working-tree content — is a
    violation for that role. Reviewer isolation stays covered by the
    stricter :class:`RepositoryFingerprint` check below, which also covers
    worktree content.
    """

    branch: str
    head_sha: str


@dataclass(frozen=True)
class UnpublishedCommitCandidate:
    """One reviewed local commit that must remain absent from the remote.

    ``published_predecessor_sha`` is both the implementation HEAD immediately
    before the local commit and the exact remote delivery-branch HEAD that must
    remain current until an accepted Mode C audit publishes the candidate.
    ``tree_sha`` detects any attempt to substitute different committed content.
    """

    branch: str
    published_predecessor_sha: str
    candidate_head_sha: str
    tree_sha: str


def capture_branch_head(repo: Path) -> BranchHead:
    return BranchHead(branch=current_branch(repo), head_sha=head_sha(repo))


def verify_branch_head_unchanged(
    repo: Path, expected: BranchHead, *, context: str
) -> None:
    """Fail closed if branch or HEAD moved since ``expected`` was captured.

    Used around an implementer invocation, which is given working-file
    write access but never Git/GitHub write access
    (``docs/AUTONOMOUS_PR_HARNESS.md`` §§5, 8, 14): any branch checkout or
    commit made by that process is a violation, detected here regardless of
    whether it left the working tree clean afterward.
    """

    current = capture_branch_head(repo)
    if current != expected:
        raise RepositoryError(
            f"branch/HEAD changed unexpectedly during {context}: expected "
            f"{expected!r}, found {current!r}"
        )


@dataclass(frozen=True)
class RepositoryFingerprint:
    """A snapshot of facts an external agent process — or a deterministic
    verification command — must never change.

    Used to detect an implementer/reviewer process moving the branch or
    HEAD it was never given Git/GitHub write access to, or leaving behind
    unexpected worktree mutation (``docs/AUTONOMOUS_PR_HARNESS.md`` §§5,
    14) — and, since a configured deterministic verification command is
    never trusted to be read-only by convention either, the identical
    guard around every verification command
    (:func:`.orchestrator._run_verification`).

    ``content_digest`` is content-sensitive, not merely status-sensitive:
    it covers the actual bytes of every tracked and untracked visible
    file (:func:`capture_fingerprint`), not just each path's porcelain
    status flag. A command that rewrites a file's *content* while leaving
    its status line unchanged — an already-untracked file staying
    untracked, or an already-modified tracked file staying modified with
    different bytes — is still detected; the porcelain status text alone
    cannot distinguish that from "nothing changed".
    """

    branch: str
    head_sha: str
    content_digest: str


def _run(
    args: Sequence[str], *, cwd: Path, timeout: float = _DEFAULT_TIMEOUT_SECONDS
) -> subprocess.CompletedProcess[str]:
    """Run ``args`` and decode stdout/stderr as UTF-8 explicitly.

    ``text=True`` alone decodes using the platform's default locale
    encoding, which on Windows is a codepage other than UTF-8 — silently
    corrupting any non-ASCII byte ``git``/``gh`` output (e.g. the em dash
    ``docs/TASK.md`` uses for "no dependencies"). Every Git/GitHub
    interaction here is UTF-8 (this repository's canonical text encoding),
    so decoding must never depend on the host's locale.
    """

    try:
        return subprocess.run(
            list(args),
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
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


def fetch_and_capture_origin_main_sha(repo: Path) -> str:
    """Fetch origin and immediately return the resulting exact
    ``origin/main`` SHA.

    This is the single authoritative fetch point for one revalidation
    decision. A caller that captures the SHA this way — instead of
    re-resolving the mutable ``origin/main`` ref again later — can make one
    decision (revalidate the task, then create a delivery branch from
    exactly that commit) that stays valid even if ``origin/main`` moves
    again immediately afterward (``docs/AUTONOMOUS_PR_HARNESS.md`` §3,
    §12): nothing about a later, unrelated fetch elsewhere can move the
    base out from under an already-made decision, because nothing after
    this call re-fetches or re-resolves the symbolic ref on that decision's
    behalf.
    """

    fetch_origin(repo)
    return origin_main_sha(repo)


def read_file_at_ref(repo: Path, ref: str, path: str) -> str:
    """Read ``path`` as it exists at ``ref``, via ``git show <ref>:<path>``.

    Never checks out, resets, or otherwise moves the working tree or the
    currently checked-out branch — this reads one blob's content directly
    out of Git's object store. This is the narrow mechanism preflight uses
    to revalidate the authoritative ``docs/TASK.md`` against a freshly
    fetched ``origin/main`` regardless of what the local working tree or
    currently checked-out branch happens to contain
    (``docs/AUTONOMOUS_PR_HARNESS.md`` §3): a clean local branch can still
    be stale or different from ``origin/main``.
    """

    return _git(repo, ["show", f"{ref}:{path}"])


def file_exists_at_ref(repo: Path, ref: str, path: str) -> bool:
    """Whether ``path`` exists as a file at ``ref`` (``git ls-tree``).

    Lets a caller tell "this file does not exist at that commit" apart from
    a genuine Git failure: a missing path is ``False``, while a bad ref or a
    failed ``git`` invocation still raises :class:`RepositoryError` and is
    never read as "missing". Like :func:`read_file_at_ref` it reads Git's
    object store only and never touches the working tree.
    """

    listing = _git(repo, ["ls-tree", "--name-only", ref, "--", path])
    return path in listing.splitlines()


def resolve_sha(repo: Path, ref: str) -> str:
    """Resolve any ref/expression to its exact commit SHA."""

    return _git(repo, ["rev-parse", ref]).strip()


def head_sha(repo: Path) -> str:
    return resolve_sha(repo, "HEAD")


def origin_main_sha(repo: Path) -> str:
    return resolve_sha(repo, "origin/main")


def current_branch(repo: Path) -> str:
    return _git(repo, ["rev-parse", "--abbrev-ref", "HEAD"]).strip()


def remote_branch_sha(repo: Path, branch: str) -> str:
    """Return the exact remote-tracking SHA for one already-fetched branch."""

    ref = f"refs/remotes/origin/{branch}"
    if not _ref_exists(repo, ref):
        raise RepositoryError(f"remote delivery branch {branch!r} does not exist")
    return resolve_sha(repo, ref)


def fetch_and_capture_remote_branch_sha(repo: Path, branch: str) -> str:
    """Fetch once, then capture one delivery branch's exact remote SHA."""

    fetch_origin(repo)
    return remote_branch_sha(repo, branch)


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


def create_delivery_branch_from_sha(repo: Path, branch: str, base_sha: str) -> None:
    """Create ``branch`` pointing at exactly ``base_sha``.

    Unlike :func:`create_delivery_branch_from_origin_main`, this never
    fetches and never re-resolves the mutable ``origin/main`` ref itself —
    it anchors the checkout to the exact commit the caller already decided
    to use (typically one captured with
    :func:`fetch_and_capture_origin_main_sha` and then positively
    revalidated). This is what closes the fetch race a two-step
    fetch-then-create flow would otherwise have: nothing between an earlier
    revalidation decision and this call can silently move the base out from
    under it, because this function performs no fetch of its own and never
    resolves ``origin/main`` again.

    Same hard guards as :func:`create_delivery_branch_from_origin_main` —
    refuses a protected branch name, requires a clean worktree, and refuses
    a local/remote branch-name collision (against whatever remote-tracking
    state is already present; the caller is responsible for having fetched
    before deciding on ``base_sha``). ``base_sha`` itself is trusted as
    already authoritative and revalidated — this function's job is only to
    anchor the checkout to it exactly, never to re-derive or re-validate
    it.
    """

    if branch in _PROTECTED_BRANCHES:
        raise RepositoryError(f"refusing to use protected branch name {branch!r}")
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
    _git(repo, ["checkout", "-b", branch, base_sha])


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


def changed_paths(repo: Path) -> tuple[str, ...]:
    """Every path with a staged, unstaged, or untracked change.

    Reads ``git status --porcelain=v1`` directly rather than deriving paths
    from a diff, so it stays correct after
    :func:`intent_to_add_untracked_files` has run. This is the narrow
    "what am I about to commit" input :func:`commit_reviewed_checkpoint`
    needs as its ``paths`` argument for an accepted checkpoint — it is
    never itself authorization to stage or commit anything.
    """

    status = _git(repo, ["status", "--porcelain=v1"])
    paths: list[str] = []
    for line in status.splitlines():
        if not line:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path.startswith('"') and path.endswith('"'):
            path = path[1:-1]
        paths.append(path)
    return tuple(paths)


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


def build_cumulative_patch_from_base(
    repo: Path, purpose: ReviewPurpose, base_sha: str
) -> ReviewPatch:
    """``git diff <base_sha>...HEAD`` against an exact, already-validated
    base — never fetches, never resolves the mutable ``origin/main`` ref
    itself.

    Same purpose restriction, range shape, and canonical-A/B/C semantics as
    :func:`build_cumulative_patch` (still the "C" range; this is not a
    fourth diff mode) — the only difference is anchoring to a caller-
    supplied exact commit rather than resolving ``origin/main`` internally.
    This closes the same revalidation/fetch race
    :func:`create_delivery_branch_from_sha` already closes for branch
    creation: a caller that has just fetched and positively revalidated
    ``origin/main`` at a specific SHA can build the cumulative diff against
    that exact commit, immune to ``origin/main`` moving again in between.

    Requires a clean worktree/index first: this is a commit-to-commit
    range, so unlike mode A, ``git add -N`` cannot make uncommitted content
    appear in it — a dirty state would silently produce an incomplete
    review artifact rather than fail loudly.
    """

    if purpose not in _CUMULATIVE_PURPOSES:
        raise RepositoryError(
            f"build_cumulative_patch_from_base requires a cumulative "
            f"ReviewPurpose, got {purpose!r}"
        )
    _require_clean_state(repo, context=purpose.value)
    diff_text = _git(repo, ["diff", f"{base_sha}...HEAD"])
    return _build_review_patch(
        repo,
        purpose=purpose,
        range_description=f"{base_sha}...HEAD",
        base_sha=base_sha,
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
    """Capture a content-sensitive fingerprint of branch/HEAD/full
    worktree+index state.

    ``content_digest`` folds together, in this fixed order:

    - the porcelain status line set (``git status --porcelain=v1``), so
      each path's status flag is still covered;
    - the byte-for-byte tracked worktree diff against HEAD (``git diff
      --binary HEAD``), which alone already reflects both staged and
      unstaged tracked-file content changes;
    - the byte-for-byte staged diff against HEAD (``git diff --cached
      --binary HEAD``) as well — defense-in-depth for the rare case index
      and worktree content diverge from HEAD in a way the worktree-vs-HEAD
      diff alone would not fully surface;
    - for every currently untracked-but-visible file (``git ls-files
      --others --exclude-standard``, in deterministic sorted-path order),
      that path together with a hash of its actual current bytes. Git
      diff output never covers untracked files at all, so without this a
      command that rewrites an untracked file's content in place (e.g. a
      checkpoint's own freshly-written ``work_output.txt``, still
      untracked before and after) would leave a porcelain-status-only
      fingerprint falsely claiming nothing changed.
    """

    hasher = hashlib.sha256()
    hasher.update(b"STATUS\x00")
    hasher.update(_git(repo, ["status", "--porcelain=v1"]).encode("utf-8"))
    hasher.update(b"\x00WORKTREE_DIFF\x00")
    hasher.update(_git(repo, ["diff", "--binary", "HEAD"]).encode("utf-8"))
    hasher.update(b"\x00STAGED_DIFF\x00")
    hasher.update(_git(repo, ["diff", "--cached", "--binary", "HEAD"]).encode("utf-8"))
    hasher.update(b"\x00UNTRACKED\x00")
    untracked_output = _git(repo, ["ls-files", "--others", "--exclude-standard", "-z"])
    untracked_paths = sorted(path for path in untracked_output.split("\x00") if path)
    for path in untracked_paths:
        hasher.update(path.encode("utf-8"))
        hasher.update(b"\x00")
        try:
            content = (repo / path).read_bytes()
        except OSError:
            # A path git just reported as untracked but that can no
            # longer be read as a plain file (deleted, or replaced by a
            # directory, in the instant between the two commands) is
            # itself a worktree change -- fold a fixed sentinel into the
            # digest rather than silently treating it as empty content.
            content = b"\x00UNREADABLE\x00"
        hasher.update(hashlib.sha256(content).digest())
        hasher.update(b"\x00")
    return RepositoryFingerprint(
        branch=current_branch(repo),
        head_sha=head_sha(repo),
        content_digest=hasher.hexdigest(),
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


def create_unpublished_reviewed_commit(
    repo: Path,
    *,
    reviewed_patch: ReviewPatch,
    message: str,
    paths: Sequence[str],
    expected_branch: str,
    expected_published_head: str,
) -> UnpublishedCommitCandidate:
    """Commit a reviewed closure locally while proving it is unpublished."""

    if expected_branch in _PROTECTED_BRANCHES:
        raise RepositoryError(
            f"refusing unpublished candidate on protected branch {expected_branch!r}"
        )
    if current_branch(repo) != expected_branch:
        raise RepositoryError(
            f"current branch does not match expected delivery branch {expected_branch!r}"
        )
    if head_sha(repo) != expected_published_head:
        raise RepositoryError(
            "local HEAD is not the exact expected published implementation HEAD"
        )
    remote_head = fetch_and_capture_remote_branch_sha(repo, expected_branch)
    if remote_head != expected_published_head:
        raise RepositoryError(
            "remote delivery branch is not at the exact expected published "
            "implementation HEAD"
        )
    candidate_head = commit_reviewed_checkpoint(
        repo, reviewed_patch=reviewed_patch, message=message, paths=paths
    )
    if not is_worktree_clean(repo):
        raise RepositoryError("unpublished candidate commit left a dirty repository")
    if remote_branch_sha(repo, expected_branch) != expected_published_head:
        raise RepositoryError(
            "remote delivery branch moved while the unpublished candidate was created"
        )
    return UnpublishedCommitCandidate(
        branch=expected_branch,
        published_predecessor_sha=expected_published_head,
        candidate_head_sha=candidate_head,
        tree_sha=resolve_sha(repo, f"{candidate_head}^{{tree}}"),
    )


def discard_reviewed_uncommitted_candidate(
    repo: Path,
    *,
    reviewed_patch: ReviewPatch,
    paths: Sequence[str],
    expected_branch: str,
    expected_head: str,
    expected_remote_head: str,
) -> None:
    """Discard one exact reviewed-but-rejected worktree candidate safely.

    This is intentionally narrower than a generic cleanup/reset primitive. It
    accepts only a still-current mode-A patch, proves its complete changed-path
    set, branch, local HEAD, and freshly fetched remote HEAD, then restores the
    exact committed predecessor and removes only the explicitly reviewed
    untracked files. Any unrelated dirty state changes the patch/path set and
    fails closed before the destructive operation.
    """

    if expected_branch in _PROTECTED_BRANCHES:
        raise RepositoryError("refusing discard on a protected branch")
    if current_branch(repo) != expected_branch:
        raise RepositoryError("current branch differs from expected delivery branch")
    if head_sha(repo) != expected_head or reviewed_patch.head_sha != expected_head:
        raise RepositoryError("local HEAD differs from rejected candidate predecessor")
    verify_patch_unchanged(repo, reviewed_patch)
    factual_paths = changed_paths(repo)
    if set(factual_paths) != set(paths):
        raise RepositoryError("rejected candidate path set changed before discard")
    fetch_origin(repo)
    if remote_branch_sha(repo, expected_branch) != expected_remote_head:
        raise RepositoryError("remote delivery branch moved before candidate discard")
    _git(repo, ["reset", "--hard", expected_head])
    if paths:
        _git(repo, ["clean", "-f", "--", *paths])
    if head_sha(repo) != expected_head or not is_worktree_clean(repo):
        raise RepositoryError("failed to restore clean rejected-candidate predecessor")
    if remote_branch_sha(repo, expected_branch) != expected_remote_head:
        raise RepositoryError("remote delivery branch changed during candidate discard")


def verify_unpublished_commit_candidate(
    repo: Path,
    candidate: UnpublishedCommitCandidate,
    *,
    expected_branch: str,
    fetch: bool = True,
) -> None:
    """Prove exact local candidate/content and unchanged remote predecessor."""

    if candidate.branch != expected_branch or expected_branch in _PROTECTED_BRANCHES:
        raise RepositoryError("unpublished candidate belongs to an unexpected branch")
    if fetch:
        fetch_origin(repo)
    _require_clean_state(repo, context="unpublished closure candidate")
    if current_branch(repo) != expected_branch:
        raise RepositoryError("current branch differs from unpublished candidate branch")
    if head_sha(repo) != candidate.candidate_head_sha:
        raise RepositoryError("local HEAD differs from unpublished candidate HEAD")
    if resolve_sha(repo, f"HEAD^{{tree}}") != candidate.tree_sha:
        raise RepositoryError("unpublished candidate content/tree changed")
    if remote_branch_sha(repo, expected_branch) != candidate.published_predecessor_sha:
        raise RepositoryError(
            "remote delivery branch moved past the expected published predecessor"
        )


def discard_unpublished_commit_candidate(
    repo: Path,
    candidate: UnpublishedCommitCandidate,
    *,
    expected_branch: str,
) -> str:
    """Discard exactly one known-unpublished local commit without remote rewrite."""

    verify_unpublished_commit_candidate(
        repo, candidate, expected_branch=expected_branch, fetch=True
    )
    _git(repo, ["reset", "--hard", candidate.published_predecessor_sha])
    if head_sha(repo) != candidate.published_predecessor_sha or not is_worktree_clean(repo):
        raise RepositoryError("failed to restore the exact published predecessor")
    if remote_branch_sha(repo, expected_branch) != candidate.published_predecessor_sha:
        raise RepositoryError("remote delivery branch changed during local discard")
    return candidate.published_predecessor_sha


def verify_published_commit_candidate(
    repo: Path,
    candidate: UnpublishedCommitCandidate,
    *,
    expected_branch: str,
    fetch: bool = True,
) -> None:
    """Prove the same exact local candidate is now the remote branch HEAD."""

    if candidate.branch != expected_branch or expected_branch in _PROTECTED_BRANCHES:
        raise RepositoryError("published candidate belongs to an unexpected branch")
    if fetch:
        fetch_origin(repo)
    _require_clean_state(repo, context="published closure candidate")
    if current_branch(repo) != expected_branch:
        raise RepositoryError("current branch differs from published candidate branch")
    if head_sha(repo) != candidate.candidate_head_sha:
        raise RepositoryError("local HEAD differs from published candidate HEAD")
    if resolve_sha(repo, "HEAD^{tree}") != candidate.tree_sha:
        raise RepositoryError("published candidate content/tree changed")
    if remote_branch_sha(repo, expected_branch) != candidate.candidate_head_sha:
        raise RepositoryError("remote delivery branch differs from published candidate")


def publish_audited_unpublished_candidate(
    repo: Path,
    candidate: UnpublishedCommitCandidate,
    *,
    audited_patch: ReviewPatch,
    expected_branch: str,
    expected_origin_main_sha: str,
) -> None:
    """Publish exactly the unchanged candidate approved by Mode C."""

    fetch_origin(repo)
    verify_unpublished_commit_candidate(
        repo, candidate, expected_branch=expected_branch, fetch=False
    )
    if origin_main_sha(repo) != expected_origin_main_sha:
        raise RepositoryError("origin/main moved after Mode C; refusing publication")
    if audited_patch.purpose is not ReviewPurpose.FINAL_CUMULATIVE_AUDIT:
        raise RepositoryError("publication requires a Mode C audit patch")
    if (
        audited_patch.branch != expected_branch
        or audited_patch.base_sha != expected_origin_main_sha
        or audited_patch.head_sha != candidate.candidate_head_sha
    ):
        raise RepositoryError("Mode C audit does not identify this exact candidate/base")
    current_patch = build_cumulative_patch_from_base(
        repo, ReviewPurpose.FINAL_CUMULATIVE_AUDIT, expected_origin_main_sha
    )
    if current_patch.digest != audited_patch.digest:
        raise RepositoryError("candidate content differs from the accepted Mode C audit")
    push_delivery_branch(
        repo, branch=expected_branch, expected_branch=expected_branch
    )
    fetch_origin(repo)
    if remote_branch_sha(repo, expected_branch) != candidate.candidate_head_sha:
        raise RepositoryError("published remote HEAD does not equal audited candidate HEAD")


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

    Deliberately unparsed. This is only the narrow ``gh``-invocation hook;
    :func:`pr_checks_json` is what an orchestrator uses for CI-driven
    repair/replay decisions.
    """

    return _gh(repo, ["pr", "checks", pr_number], gh_command=gh_command)


_PR_CHECKS_JSON_FIELDS = "name,state,bucket"

# gh pr checks's own documented exit codes: 0 all required checks passed,
# 8 checks are still pending, 1 checks failed/incomplete (or, narrowly,
# "no required checks configured" -- see _looks_like_no_required_checks_stderr).
# Any other exit code is a genuine tool error, never a checks result.
_PR_CHECKS_KNOWN_EXIT_CODES = frozenset({0, 1, 8})

# The fields --json name,state,bucket is expected to produce for every
# check object. A check object missing any of these, or carrying a
# non-string/empty value for one, is malformed and can never satisfy the
# required-CI gate -- see _validate_check_item.
_REQUIRED_CHECK_FIELDS = ("name", "state", "bucket")

# gh's own documented summary buckets for a PR check. A bucket value
# outside this set is malformed/unrecognized output, never silently
# treated as any particular outcome.
_KNOWN_CHECK_BUCKETS = frozenset({"pass", "fail", "pending", "skipping", "cancel"})

# Buckets GitHub itself treats as a successful status-check conclusion --
# a plain pass, and a skipped/neutral check GitHub does not block merges
# on. Only "fail"/"pending"/"cancel" are non-successful. This is what
# lets `_required_ci` accept `gh pr checks`'s own exit 0 (every required
# check already succeeded) even when one or more of those successful
# checks happens to carry bucket "skipping" rather than "pass" --
# reinterpreting a genuinely successful gh outcome as failing/pending
# would itself be a fail-*open* bug in the opposite direction.
_SUCCESSFUL_CHECK_BUCKETS = frozenset({"pass", "skipping"})

# The specific, narrow phrase gh's own "no required checks" result is
# recognized by (case-insensitive substring match against stderr only --
# never stdout/the parsed checks JSON, so a real check whose own name
# happens to contain this phrase, e.g. "No Required Checks Policy", can
# never be misclassified this way). Deliberately narrow: this module does
# not attempt to recognize every possible phrasing, only this positively-
# known one -- anything else at exit 1 falls through to the existing
# ambiguous/inconsistent-result handling below, which fails closed.
_NO_REQUIRED_CHECKS_MARKER = "no required checks"

# A small defensive guard against misclassifying a genuine tool/auth/
# network error that happens to also mention "no required checks" in
# passing -- gh's own message for this condition is never also an
# authentication/HTTP/connectivity failure in practice.
_ERROR_MARKERS_THAT_OVERRIDE_NO_REQUIRED_CHECKS = (
    "authentic",
    "http ",
    "could not resolve",
    "connection",
    "rate limit",
)


@dataclass(frozen=True)
class RequiredChecksResult:
    """The outcome of querying ``gh``'s ``--required`` PR checks.

    ``no_required_checks=True`` is a narrow, explicit, positively
    recognized result: ``gh`` reported that this PR/repository has no
    required status checks configured at all — the required set is empty,
    which satisfies (not blocks) a required-CI gate. This is never
    conflated with an ordinary (possibly incidentally empty-looking)
    checks list, a failing/pending state, or a genuine tool/auth/network/
    malformed-output error — each of those still raises
    :class:`RepositoryError` or returns ``no_required_checks=False`` with
    the actual parsed checks, exactly as before this distinction existed.
    When ``no_required_checks`` is ``True``, ``checks`` is always empty.

    ``returncode`` retains ``gh``'s own validated exit code (``0``, ``1``,
    or ``8``) so the caller can key its accept/reject decision off gh's
    own already-computed, already-consistency-checked outcome rather than
    re-deriving it from ``checks`` — in particular, exit ``0`` ("every
    required check succeeded") is always the gate-satisfied outcome
    regardless of *which* successful bucket (``pass`` or ``skipping``)
    each individual check happens to carry.
    """

    checks: list[dict[str, Any]]
    no_required_checks: bool
    returncode: int


def _run_gh_pr_checks_required(
    repo: Path, pr_number: str, *, gh_command: Sequence[str]
) -> subprocess.CompletedProcess[str]:
    return _run(
        [
            *gh_command,
            "pr",
            "checks",
            pr_number,
            "--required",
            "--json",
            _PR_CHECKS_JSON_FIELDS,
        ],
        cwd=repo,
    )


def _validate_check_item(item: dict[str, Any]) -> bool:
    """A well-formed check object has a non-empty string for each of
    ``name``/``state``/``bucket`` — a malformed entry (e.g. ``{"bucket":
    "pass"}`` alone) can never satisfy the required-CI gate — and
    ``bucket`` must additionally be one of gh's own known summary buckets
    (:data:`_KNOWN_CHECK_BUCKETS`); an unrecognized bucket value is
    malformed output too, never silently treated as any particular
    outcome."""

    for field_name in _REQUIRED_CHECK_FIELDS:
        value = item.get(field_name)
        if not isinstance(value, str) or not value:
            return False
    if item["bucket"] not in _KNOWN_CHECK_BUCKETS:
        return False
    return True


def _try_parse_checks_json(stdout: str) -> list[dict[str, Any]] | None:
    """The parsed checks list, or ``None`` if ``stdout`` is not valid,
    well-formed, **non-empty** checks JSON.

    Returns ``None`` for: invalid JSON; the wrong shape; an entry missing
    a required non-empty ``name``/``state``/``bucket`` field; and — this
    is load-bearing, not incidental — an empty JSON array ``[]``. An empty
    array is ambiguous evidence (zero checks reported is never
    distinguishable here from a tool that printed nothing meaningful) and
    must never be treated as an ordinary, decidable checks result; callers
    (:func:`pr_required_checks`) only ever reach the positively recognized
    "no required checks configured" diagnostic, or fail closed, for it —
    never the ordinary bucket-consistency path.
    """

    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list) or not all(
        isinstance(item, dict) and _validate_check_item(item) for item in parsed
    ):
        return None
    if not parsed:
        return None
    return parsed


def _looks_like_no_required_checks_stderr(stderr: str) -> bool:
    lowered = stderr.lower()
    if _NO_REQUIRED_CHECKS_MARKER not in lowered:
        return False
    return not any(
        marker in lowered for marker in _ERROR_MARKERS_THAT_OVERRIDE_NO_REQUIRED_CHECKS
    )


def pr_required_checks(
    repo: Path, pr_number: str, *, gh_command: Sequence[str] = _DEFAULT_GH_COMMAND
) -> RequiredChecksResult:
    """``gh pr checks <number> --required --json name,state,bucket``,
    distinguishing "no required checks configured" from every other
    outcome.

    Used for the required-CI gate and CI-driven repair/replay decisions
    (``docs/AUTONOMOUS_PR_HARNESS.md`` §16): each returned entry's
    ``bucket`` is expected to be one of ``gh``'s own summary buckets (e.g.
    ``pass``, ``fail``, ``pending``, ``skipping``, ``cancel``) — this
    module does not interpret those values itself, only parses and returns
    them. ``--required`` restricts the query to checks GitHub actually
    marks required: an unrelated optional check must never be able to
    block (or silently satisfy) this harness's required-CI gate.

    Deliberately does **not** call the generic strict :func:`_gh` — ``gh
    pr checks`` documents a non-zero exit for its own pending (``8``) and
    failing/incomplete (``1``) outcomes, which :func:`_gh` would otherwise
    treat identically to a genuine tool error and raise before this
    function ever sees the JSON body. This is a narrow, local exception for
    this one call site only; :func:`_gh` itself is not weakened, so ``gh
    pr create`` and every other ``gh`` side effect in this module keep
    their strict non-zero-is-an-error behavior.

    Decision order (load-bearing — never reversed): stdout is checked for
    being valid, well-formed checks JSON *first*. A valid, non-empty
    checks array is always treated as a real checks result and can
    **never** be reclassified as "no required checks" because of text
    inside it — a check literally named ``"No Required Checks Policy"``
    with ``bucket: "fail"`` still counts as a real, failing required
    check. Only when stdout is *not* valid, well-formed, non-empty checks
    JSON does this function even look at ``stderr`` for the positively
    recognized "no required checks configured" diagnostic
    (:func:`_looks_like_no_required_checks_stderr`) — never at stdout for
    that purpose.

    Exit-code handling:

    - ``0``/``8``/``1`` with valid, well-formed checks JSON: parsed and
      returned (``no_required_checks=False``, ``returncode`` retained),
      subject to bucket-aware consistency checks that never quietly
      resolve an ambiguous result in either direction: exit ``0`` ("every
      required check succeeded") is inconsistent if any check carries a
      non-successful bucket (``fail``/``pending``/``cancel`` —
      ``pass``/``skipping`` both count as successful, since GitHub itself
      treats a skipped/neutral check as a successful conclusion); exit
      ``1`` (failed/incomplete) or exit ``8`` (pending) are each
      inconsistent if *no* check carries a non-successful bucket (i.e.
      the JSON claims everything already succeeded).
    - ``1`` with stdout that is *not* valid, well-formed, non-empty checks
      JSON, and ``stderr`` positively matches gh's known "no required
      checks configured/reported" phrasing: a real repository/PR with no
      required status checks at all — returns
      ``RequiredChecksResult(checks=[], no_required_checks=True,
      returncode=1)``.
    - anything else (an unrecognized exit code, a missing ``gh``, a
      timeout, malformed/empty output with no recognized "no required
      checks" diagnostic, or a malformed individual check object —
      including an unrecognized ``bucket`` value) always raises
      :class:`RepositoryError`. An unparseable or ambiguous CI status is
      never silently treated as passing or as an empty required set.
    """

    result = _run_gh_pr_checks_required(repo, pr_number, gh_command=gh_command)
    parsed = _try_parse_checks_json(result.stdout)

    if parsed is not None:
        # Valid, well-formed, NON-EMPTY checks JSON (_try_parse_checks_json
        # itself rejects an empty array as ambiguous evidence) -- a real
        # checks result, decided entirely by exit code/bucket consistency,
        # never reclassified as "no required checks" based on anything
        # inside it.
        if result.returncode not in _PR_CHECKS_KNOWN_EXIT_CODES:
            raise RepositoryError(
                f"gh pr checks --required --json exited {result.returncode}, "
                f"not one of gh's documented outcomes "
                f"{sorted(_PR_CHECKS_KNOWN_EXIT_CODES)!r}: {result.stderr.strip()}"
            )
        non_successful_present = any(
            item["bucket"] not in _SUCCESSFUL_CHECK_BUCKETS for item in parsed
        )
        if result.returncode == 0 and non_successful_present:
            raise RepositoryError(
                "gh pr checks --required --json exited 0 (required checks "
                "succeeded) but its own JSON output shows a check whose "
                "bucket is not itself a successful outcome (pass/"
                "skipping); an inconsistent/ambiguous checks result is "
                f"never silently resolved in either direction: "
                f"{result.stdout!r}"
            )
        if result.returncode == 1 and not non_successful_present:
            raise RepositoryError(
                "gh pr checks --required --json exited 1 (checks not all "
                "successful) but its own JSON output does not show any "
                "non-successful check; an inconsistent/ambiguous checks "
                f"result is never silently resolved in either direction: "
                f"{result.stdout!r}"
            )
        if result.returncode == 8 and not non_successful_present:
            raise RepositoryError(
                "gh pr checks --required --json exited 8 (checks pending) "
                "but its own JSON output does not show any pending/"
                "non-successful check; an inconsistent/ambiguous checks "
                f"result is never silently resolved in either direction: "
                f"{result.stdout!r}"
            )
        return RequiredChecksResult(
            checks=parsed, no_required_checks=False, returncode=result.returncode
        )

    # stdout was not valid, well-formed, non-empty checks JSON (invalid
    # JSON, the wrong shape, an empty array, or a malformed entry). Only
    # now consider the positively recognized "no required checks
    # configured" diagnostic -- and only from stderr, a genuine
    # non-check-result channel, never from stdout/parsed check content.
    if result.returncode == 1 and _looks_like_no_required_checks_stderr(result.stderr):
        return RequiredChecksResult(
            checks=[], no_required_checks=True, returncode=result.returncode
        )

    raise RepositoryError(
        f"gh pr checks --required --json output (exit {result.returncode}) "
        "was not valid, well-formed, non-empty checks JSON, and no "
        "recognized 'no required checks' diagnostic was present either: "
        f"stdout={result.stdout!r} stderr={result.stderr.strip()!r}"
    )


def pr_checks_json(
    repo: Path, pr_number: str, *, gh_command: Sequence[str] = _DEFAULT_GH_COMMAND
) -> list[dict[str, Any]]:
    """Structured ``gh pr checks <number> --required --json
    name,state,bucket`` output, as a plain list.

    A thin, backward-compatible wrapper over :func:`pr_required_checks`
    for callers that only ever want a definite checks list or a raised
    error — it has no way to represent "no required checks configured"
    distinctly from an ambiguous result, so it raises
    :class:`RepositoryError` for that case too (a caller that needs to
    tell the two apart must call :func:`pr_required_checks` directly,
    which is what the required-CI gate does).
    """

    result = pr_required_checks(repo, pr_number, gh_command=gh_command)
    if result.no_required_checks:
        raise RepositoryError(
            "gh reported no required checks configured for this PR; "
            "pr_checks_json has no way to represent that distinctly from "
            "an ambiguous/empty result -- call pr_required_checks directly "
            "to observe RequiredChecksResult.no_required_checks"
        )
    return result.checks


def pr_head_sha(
    repo: Path, pr_number: str, *, gh_command: Sequence[str] = _DEFAULT_GH_COMMAND
) -> str:
    """The draft PR's exact current head commit SHA, via ``gh pr view
    <number> --json headRefOid``.

    Used to positively bind required-CI evidence to the exact pushed
    delivery-branch commit this run's closure actually reviewed and
    committed (``docs/AUTONOMOUS_PR_HARNESS.md`` §16): checks reported
    against an older or newer PR head must never be accepted as evidence
    for a different commit than the one this run is actually closing on.
    No REST API fallback — uses the generic strict :func:`_gh`, since ``gh
    pr view`` has no documented non-zero "successful" exit the way ``gh pr
    checks`` does.
    """

    output = _gh(
        repo,
        ["pr", "view", pr_number, "--json", "headRefOid"],
        gh_command=gh_command,
    )
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError as exc:
        raise RepositoryError(
            f"gh pr view --json headRefOid output was not valid JSON: {exc}"
        ) from exc
    if not isinstance(parsed, dict):
        raise RepositoryError(
            "gh pr view --json headRefOid output was not a JSON object"
        )
    head_ref_oid = parsed.get("headRefOid")
    if not isinstance(head_ref_oid, str) or not head_ref_oid:
        raise RepositoryError(
            "gh pr view --json headRefOid output did not contain a "
            "non-empty string 'headRefOid'"
        )
    return head_ref_oid
