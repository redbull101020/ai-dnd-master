import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from tools.autonomous_pr import repository as repo_module
from tools.autonomous_pr.repository import (
    RepositoryError,
    ReviewPurpose,
    ReviewPatch,
)

_FAKE_GH_PR_CREATE = (
    "import sys\n"
    "args = sys.argv[1:]\n"
    "if args[:2] == ['pr', 'create']:\n"
    "    print('https://github.com/example/repo/pull/1')\n"
    "else:\n"
    "    raise SystemExit(1)\n"
)

_FAKE_GH_PR_CREATE_RECORDING = (
    "import sys, json\n"
    "args = sys.argv[1:]\n"
    "with open('gh_invocation.json', 'w', encoding='utf-8') as f:\n"
    "    json.dump(args, f)\n"
    "if args[:2] == ['pr', 'create']:\n"
    "    print('https://github.com/example/repo/pull/1')\n"
    "else:\n"
    "    raise SystemExit(1)\n"
)


def _run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"
    return result.stdout


def _configure_user(repo: Path) -> None:
    _run_git(["config", "user.email", "harness-test@example.com"], cwd=repo)
    _run_git(["config", "user.name", "Harness Test"], cwd=repo)


def _push_new_commit_to_origin_main(seed: Path, filename: str = "extra.txt") -> str:
    (seed / filename).write_text("extra\n", encoding="utf-8")
    _run_git(["add", filename], cwd=seed)
    _run_git(["commit", "-q", "-m", f"add {filename}"], cwd=seed)
    _run_git(["push", "-q", "origin", "main"], cwd=seed)
    return _run_git(["rev-parse", "HEAD"], cwd=seed).strip()


def _make_dirty(work: Path, kind: str) -> None:
    if kind == "untracked":
        (work / "dirty.txt").write_text("dirty\n", encoding="utf-8")
    elif kind == "unstaged":
        (work / "README.md").write_text("seed\nmodified\n", encoding="utf-8")
    elif kind == "staged":
        (work / "README.md").write_text("seed\nmodified\n", encoding="utf-8")
        _run_git(["add", "README.md"], cwd=work)
    else:
        raise AssertionError(kind)


@dataclass
class GitEnv:
    origin: Path
    seed: Path
    work: Path


@pytest.fixture
def git_env(tmp_path: Path) -> GitEnv:
    origin = tmp_path / "origin.git"
    _run_git(["init", "-q", "--bare", "-b", "main", str(origin)], cwd=tmp_path)

    seed = tmp_path / "seed"
    _run_git(["init", "-q", "-b", "main", str(seed)], cwd=tmp_path)
    _configure_user(seed)
    (seed / "README.md").write_text("seed\n", encoding="utf-8")
    _run_git(["add", "README.md"], cwd=seed)
    _run_git(["commit", "-q", "-m", "seed"], cwd=seed)
    _run_git(["remote", "add", "origin", str(origin)], cwd=seed)
    _run_git(["push", "-q", "origin", "main"], cwd=seed)

    work = tmp_path / "work"
    _run_git(["clone", "-q", str(origin), str(work)], cwd=tmp_path)
    _configure_user(work)

    return GitEnv(origin=origin, seed=seed, work=work)


def test_branch_created_from_exact_origin_main(git_env: GitEnv) -> None:
    work = git_env.work
    expected_base = repo_module.origin_main_sha(work)

    base_sha = repo_module.create_delivery_branch_from_origin_main(work, "delivery")

    assert base_sha == expected_base
    assert repo_module.current_branch(work) == "delivery"
    assert repo_module.resolve_sha(work, "delivery") == expected_base


def test_fetch_and_capture_origin_main_sha_matches_origin_main_sha(
    git_env: GitEnv,
) -> None:
    work = git_env.work

    captured = repo_module.fetch_and_capture_origin_main_sha(work)

    assert captured == repo_module.origin_main_sha(work)


def test_create_delivery_branch_from_sha_anchors_to_exact_sha_not_origin_main(
    git_env: GitEnv,
) -> None:
    """The branch must be created from the given SHA even if origin/main
    has since moved past it -- this function never re-fetches or
    re-resolves origin/main itself."""

    work = git_env.work
    seed = git_env.seed
    captured_sha = repo_module.fetch_and_capture_origin_main_sha(work)

    _push_new_commit_to_origin_main(seed, filename="moved-on.txt")

    repo_module.create_delivery_branch_from_sha(work, "delivery", captured_sha)

    assert repo_module.current_branch(work) == "delivery"
    assert repo_module.resolve_sha(work, "delivery") == captured_sha

    repo_module.fetch_origin(work)
    assert repo_module.resolve_sha(work, "delivery") != repo_module.origin_main_sha(work)


def test_create_delivery_branch_from_sha_never_fetches(
    git_env: GitEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = git_env.work
    base_sha = repo_module.fetch_and_capture_origin_main_sha(work)
    real_run = repo_module.subprocess.run

    def fail_if_fetch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if args[:2] == ["git", "fetch"]:
            raise AssertionError("create_delivery_branch_from_sha must never fetch")
        return real_run(args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(repo_module.subprocess, "run", fail_if_fetch)

    repo_module.create_delivery_branch_from_sha(work, "delivery", base_sha)

    assert repo_module.resolve_sha(work, "delivery") == base_sha


def test_create_delivery_branch_from_sha_refuses_protected_name(
    git_env: GitEnv,
) -> None:
    work = git_env.work
    base_sha = repo_module.fetch_and_capture_origin_main_sha(work)

    with pytest.raises(RepositoryError):
        repo_module.create_delivery_branch_from_sha(work, "main", base_sha)


def test_create_delivery_branch_from_sha_refuses_dirty_worktree(
    git_env: GitEnv,
) -> None:
    work = git_env.work
    base_sha = repo_module.fetch_and_capture_origin_main_sha(work)
    (work / "dirty.txt").write_text("dirty\n", encoding="utf-8")

    with pytest.raises(RepositoryError):
        repo_module.create_delivery_branch_from_sha(work, "delivery", base_sha)


def test_create_delivery_branch_from_sha_refuses_collision(git_env: GitEnv) -> None:
    work = git_env.work
    base_sha = repo_module.fetch_and_capture_origin_main_sha(work)
    repo_module.create_delivery_branch_from_sha(work, "delivery", base_sha)
    _run_git(["checkout", "-q", "main"], cwd=work)

    with pytest.raises(RepositoryError):
        repo_module.create_delivery_branch_from_sha(work, "delivery", base_sha)


def test_create_delivery_branch_refuses_dirty_worktree(git_env: GitEnv) -> None:
    work = git_env.work
    (work / "dirty.txt").write_text("dirty\n", encoding="utf-8")

    with pytest.raises(RepositoryError):
        repo_module.create_delivery_branch_from_origin_main(work, "delivery")


def test_create_delivery_branch_refuses_existing_branch(git_env: GitEnv) -> None:
    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")
    _run_git(["checkout", "-q", "main"], cwd=work)

    with pytest.raises(RepositoryError):
        repo_module.create_delivery_branch_from_origin_main(work, "delivery")


def test_refuses_to_create_delivery_branch_named_main(git_env: GitEnv) -> None:
    work = git_env.work

    with pytest.raises(RepositoryError):
        repo_module.create_delivery_branch_from_origin_main(work, "main")


def test_create_delivery_branch_refuses_remote_only_collision(git_env: GitEnv) -> None:
    """A branch that exists only on origin (e.g. from a lost/crashed prior
    run) must never be treated as something to resume or reuse."""

    work = git_env.work
    seed = git_env.seed
    _run_git(["checkout", "-q", "-b", "delivery"], cwd=seed)
    (seed / "seed-delivery.txt").write_text("seed delivery\n", encoding="utf-8")
    _run_git(["add", "seed-delivery.txt"], cwd=seed)
    _run_git(["commit", "-q", "-m", "seed delivery branch"], cwd=seed)
    _run_git(["push", "-q", "origin", "delivery"], cwd=seed)
    _run_git(["checkout", "-q", "main"], cwd=seed)

    with pytest.raises(RepositoryError):
        repo_module.create_delivery_branch_from_origin_main(work, "delivery")


def test_show_ref_unexpected_exit_code_fails_closed(
    git_env: GitEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = git_env.work
    real_run = subprocess.run

    def flaky_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if args[:3] == ["git", "show-ref", "--verify"]:
            return subprocess.CompletedProcess(
                args=args, returncode=129, stdout="", stderr="fatal: tool error"
            )
        return real_run(args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(repo_module.subprocess, "run", flaky_run)

    with pytest.raises(RepositoryError):
        repo_module.create_delivery_branch_from_origin_main(work, "delivery")


def test_refuses_to_commit_on_main(git_env: GitEnv) -> None:
    """Refusal to operate authoritatively on main."""

    work = git_env.work
    assert repo_module.current_branch(work) == "main"
    dummy_patch = ReviewPatch(
        purpose=ReviewPurpose.CHECKPOINT,
        range_description="HEAD (uncommitted)",
        base_sha=None,
        head_sha=repo_module.head_sha(work),
        branch="main",
        diff_text="",
        digest="deadbeef",
    )

    with pytest.raises(RepositoryError):
        repo_module.commit_reviewed_checkpoint(
            work, reviewed_patch=dummy_patch, message="nope", paths=["README.md"]
        )


def test_refuses_to_push_main(git_env: GitEnv) -> None:
    work = git_env.work

    with pytest.raises(RepositoryError):
        repo_module.push_delivery_branch(work, branch="main", expected_branch="main")


def test_push_restricted_to_delivery_branch(git_env: GitEnv) -> None:
    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")

    with pytest.raises(RepositoryError):
        repo_module.push_delivery_branch(
            work, branch="some-other-branch", expected_branch="delivery"
        )


def test_push_refuses_when_current_branch_differs(git_env: GitEnv) -> None:
    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")
    _run_git(["checkout", "-q", "-b", "another"], cwd=work)

    with pytest.raises(RepositoryError):
        repo_module.push_delivery_branch(
            work, branch="delivery", expected_branch="delivery"
        )


def test_mode_a_exact_diff(git_env: GitEnv) -> None:
    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")
    (work / "README.md").write_text("seed\nmodified\n", encoding="utf-8")

    patch = repo_module.build_checkpoint_patch_uncommitted(work)

    assert patch.purpose is ReviewPurpose.CHECKPOINT
    assert "diff --git a/README.md b/README.md" in patch.diff_text
    assert "+modified" in patch.diff_text


def test_mode_a_includes_new_untracked_file(git_env: GitEnv) -> None:
    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")
    (work / "brand_new.txt").write_text("hello world\n", encoding="utf-8")

    patch = repo_module.build_checkpoint_patch_uncommitted(work)

    assert "brand_new.txt" in patch.diff_text
    assert "+hello world" in patch.diff_text


def test_mode_b_exact_range(git_env: GitEnv) -> None:
    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")

    (work / "a.txt").write_text("a\n", encoding="utf-8")
    patch_a = repo_module.build_checkpoint_patch_uncommitted(work)
    sha_a = repo_module.commit_reviewed_checkpoint(
        work, reviewed_patch=patch_a, message="add a", paths=["a.txt"]
    )

    (work / "b.txt").write_text("b\n", encoding="utf-8")
    patch_b = repo_module.build_checkpoint_patch_uncommitted(work)
    repo_module.commit_reviewed_checkpoint(
        work, reviewed_patch=patch_b, message="add b", paths=["b.txt"]
    )

    mode_b_patch = repo_module.build_checkpoint_patch_committed(work, sha_a)

    assert "b.txt" in mode_b_patch.diff_text
    assert "a.txt" not in mode_b_patch.diff_text
    assert mode_b_patch.base_sha == sha_a
    assert mode_b_patch.range_description == f"{sha_a}..HEAD"


@pytest.mark.parametrize("kind", ["unstaged", "staged", "untracked"])
def test_mode_b_rejects_dirty_state(git_env: GitEnv, kind: str) -> None:
    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")
    (work / "a.txt").write_text("a\n", encoding="utf-8")
    patch_a = repo_module.build_checkpoint_patch_uncommitted(work)
    sha_a = repo_module.commit_reviewed_checkpoint(
        work, reviewed_patch=patch_a, message="add a", paths=["a.txt"]
    )

    _make_dirty(work, kind)

    with pytest.raises(RepositoryError):
        repo_module.build_checkpoint_patch_committed(work, sha_a)


def test_cumulative_patch_purposes_share_range(git_env: GitEnv) -> None:
    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")
    (work / "c.txt").write_text("c\n", encoding="utf-8")
    patch = repo_module.build_checkpoint_patch_uncommitted(work)
    repo_module.commit_reviewed_checkpoint(
        work, reviewed_patch=patch, message="add c", paths=["c.txt"]
    )

    pre_closure = repo_module.build_cumulative_patch(
        work, ReviewPurpose.PRE_CLOSURE_CUMULATIVE_REVIEW
    )
    final_audit = repo_module.build_cumulative_patch(
        work, ReviewPurpose.FINAL_CUMULATIVE_AUDIT
    )

    assert pre_closure.range_description == "origin/main...HEAD"
    assert final_audit.range_description == "origin/main...HEAD"
    assert pre_closure.purpose is ReviewPurpose.PRE_CLOSURE_CUMULATIVE_REVIEW
    assert final_audit.purpose is ReviewPurpose.FINAL_CUMULATIVE_AUDIT
    assert "c.txt" in pre_closure.diff_text
    assert "c.txt" in final_audit.diff_text


def test_cumulative_patch_rejects_checkpoint_purpose(git_env: GitEnv) -> None:
    work = git_env.work

    with pytest.raises(RepositoryError):
        repo_module.build_cumulative_patch(work, ReviewPurpose.CHECKPOINT)


def test_cumulative_patch_from_base_uses_exact_sha_not_origin_main(
    git_env: GitEnv,
) -> None:
    """The whole point of the exact-base variant: it must anchor to the
    caller-supplied SHA even when origin/main has since moved past it."""

    work = git_env.work
    seed = git_env.seed
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")
    captured_base = repo_module.origin_main_sha(work)
    (work / "c.txt").write_text("c\n", encoding="utf-8")
    patch = repo_module.build_checkpoint_patch_uncommitted(work)
    repo_module.commit_reviewed_checkpoint(
        work, reviewed_patch=patch, message="add c", paths=["c.txt"]
    )

    _push_new_commit_to_origin_main(seed, filename="moved-on.txt")
    repo_module.fetch_origin(work)
    assert repo_module.origin_main_sha(work) != captured_base

    cumulative = repo_module.build_cumulative_patch_from_base(
        work, ReviewPurpose.PRE_CLOSURE_CUMULATIVE_REVIEW, captured_base
    )

    assert cumulative.base_sha == captured_base
    assert cumulative.range_description == f"{captured_base}...HEAD"
    assert "c.txt" in cumulative.diff_text
    assert "moved-on.txt" not in cumulative.diff_text


def test_cumulative_patch_from_base_never_fetches(
    git_env: GitEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")
    base_sha = repo_module.origin_main_sha(work)
    real_run = repo_module.subprocess.run

    def fail_if_fetch(
        args: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if args[:2] == ["git", "fetch"]:
            raise AssertionError(
                "build_cumulative_patch_from_base must never fetch"
            )
        return real_run(args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(repo_module.subprocess, "run", fail_if_fetch)

    patch = repo_module.build_cumulative_patch_from_base(
        work, ReviewPurpose.FINAL_CUMULATIVE_AUDIT, base_sha
    )

    assert patch.base_sha == base_sha


def test_cumulative_patch_from_base_rejects_checkpoint_purpose(
    git_env: GitEnv,
) -> None:
    work = git_env.work
    base_sha = repo_module.origin_main_sha(work)

    with pytest.raises(RepositoryError):
        repo_module.build_cumulative_patch_from_base(
            work, ReviewPurpose.CHECKPOINT, base_sha
        )


@pytest.mark.parametrize(
    "purpose",
    [ReviewPurpose.PRE_CLOSURE_CUMULATIVE_REVIEW, ReviewPurpose.FINAL_CUMULATIVE_AUDIT],
)
def test_cumulative_patch_from_base_rejects_dirty_state(
    git_env: GitEnv, purpose: ReviewPurpose
) -> None:
    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")
    base_sha = repo_module.origin_main_sha(work)
    (work / "dirty.txt").write_text("dirty\n", encoding="utf-8")

    with pytest.raises(RepositoryError):
        repo_module.build_cumulative_patch_from_base(work, purpose, base_sha)


@pytest.mark.parametrize(
    "purpose",
    [ReviewPurpose.PRE_CLOSURE_CUMULATIVE_REVIEW, ReviewPurpose.FINAL_CUMULATIVE_AUDIT],
)
def test_cumulative_patch_rejects_dirty_state(
    git_env: GitEnv, purpose: ReviewPurpose
) -> None:
    """`git diff origin/main...HEAD` is a commit-to-commit range: `git add
    -N` cannot make uncommitted content appear in it, so both cumulative
    purposes must fail closed on any dirty/untracked state."""

    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")
    (work / "dirty.txt").write_text("dirty\n", encoding="utf-8")

    with pytest.raises(RepositoryError):
        repo_module.build_cumulative_patch(work, purpose)


def test_review_patch_never_committed(git_env: GitEnv) -> None:
    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")
    (work / "d.txt").write_text("d\n", encoding="utf-8")
    (work / "review.patch").write_text("not real\n", encoding="utf-8")
    patch = repo_module.build_checkpoint_patch_uncommitted(work)

    with pytest.raises(RepositoryError):
        repo_module.commit_reviewed_checkpoint(
            work,
            reviewed_patch=patch,
            message="oops",
            paths=["d.txt", "review.patch"],
        )


def test_commit_rejects_pre_staged_review_patch_even_when_not_in_paths(
    git_env: GitEnv,
) -> None:
    """review.patch must never be committed even if it was already staged
    out-of-band (e.g. `git add -f review.patch`) *before* the reviewed
    checkpoint was even built — so review.patch is itself part of the
    reviewed diff — and the caller's `paths` never names it at all. This
    ordering is deliberate: staging review.patch only after the patch is
    built would instead make `verify_patch_unchanged()` fail first (a
    digest mismatch), which would not actually exercise the factual
    staged-path guard this test targets."""

    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")
    (work / "ordinary.txt").write_text("ordinary\n", encoding="utf-8")
    (work / "review.patch").write_text("not a real diff\n", encoding="utf-8")

    # Force-stage review.patch first, then build the reviewed checkpoint —
    # so review.patch is genuinely part of what was reviewed.
    _run_git(["add", "-f", "review.patch"], cwd=work)

    reviewed_patch = repo_module.build_checkpoint_patch_uncommitted(work)
    assert "review.patch" in reviewed_patch.diff_text

    head_before = repo_module.head_sha(work)

    with pytest.raises(RepositoryError) as excinfo:
        repo_module.commit_reviewed_checkpoint(
            work,
            reviewed_patch=reviewed_patch,
            message="sneaky review.patch",
            paths=["ordinary.txt"],
        )

    assert "staged commit composition" in str(excinfo.value)
    assert repo_module.head_sha(work) == head_before


def test_commit_rejects_stale_head_even_with_identical_diff_text(
    git_env: GitEnv,
) -> None:
    """HEAD moving invalidates a reviewed checkpoint even when the working
    diff text happens to still be byte-identical — this must never be
    weakened to digest-only equivalence."""

    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")
    (work / "g.txt").write_text("g\n", encoding="utf-8")
    reviewed_patch = repo_module.build_checkpoint_patch_uncommitted(work)

    # An external commit unrelated to g.txt advances HEAD without touching
    # the reviewed uncommitted content, so the working diff text stays
    # byte-for-byte identical — yet the checkpoint must still be stale.
    (work / "unrelated.txt").write_text("unrelated\n", encoding="utf-8")
    _run_git(["add", "unrelated.txt"], cwd=work)
    _run_git(["commit", "-q", "-m", "external commit"], cwd=work)

    fresh = repo_module.build_checkpoint_patch_uncommitted(work)
    assert fresh.digest == reviewed_patch.digest
    assert fresh.head_sha != reviewed_patch.head_sha

    with pytest.raises(RepositoryError):
        repo_module.commit_reviewed_checkpoint(
            work, reviewed_patch=reviewed_patch, message="stale head", paths=["g.txt"]
        )


def test_fingerprint_detects_head_movement(git_env: GitEnv) -> None:
    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")
    fingerprint = repo_module.capture_fingerprint(work)

    (work / "external.txt").write_text("external\n", encoding="utf-8")
    _run_git(["add", "external.txt"], cwd=work)
    _run_git(["commit", "-q", "-m", "external mutation"], cwd=work)

    with pytest.raises(RepositoryError):
        repo_module.verify_fingerprint_unchanged(
            work, fingerprint, context="reviewer invocation"
        )


def test_fingerprint_detects_worktree_mutation_without_commit(git_env: GitEnv) -> None:
    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")
    fingerprint = repo_module.capture_fingerprint(work)

    (work / "stray.txt").write_text("stray\n", encoding="utf-8")

    with pytest.raises(RepositoryError):
        repo_module.verify_fingerprint_unchanged(
            work, fingerprint, context="reviewer invocation"
        )


def test_fingerprint_detects_untracked_file_content_rewrite_with_unchanged_status(
    git_env: GitEnv,
) -> None:
    """A porcelain-status-only fingerprint cannot distinguish "an
    already-untracked file's content changed" from "nothing changed",
    since its status line (``?? work_output.txt``) is byte-identical
    before and after -- only a content-sensitive fingerprint catches
    this."""

    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")
    (work / "work_output.txt").write_text("original\n", encoding="utf-8")
    fingerprint = repo_module.capture_fingerprint(work)

    status_before = _run_git(["status", "--porcelain=v1"], cwd=work)
    (work / "work_output.txt").write_text("rewritten\n", encoding="utf-8")
    status_after = _run_git(["status", "--porcelain=v1"], cwd=work)

    assert status_before == status_after  # structurally unchanged

    with pytest.raises(RepositoryError):
        repo_module.verify_fingerprint_unchanged(
            work, fingerprint, context="deterministic verification"
        )


def test_fingerprint_detects_already_modified_tracked_file_further_content_rewrite(
    git_env: GitEnv,
) -> None:
    """The same problem exists for an already-dirty tracked file:
    'M file.py' can have its content rewritten again while retaining
    exactly the same porcelain status flag."""

    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")
    (work / "README.md").write_text("seed\nfirst change\n", encoding="utf-8")
    fingerprint = repo_module.capture_fingerprint(work)

    status_before = _run_git(["status", "--porcelain=v1"], cwd=work)
    (work / "README.md").write_text(
        "seed\nsecond, different change\n", encoding="utf-8"
    )
    status_after = _run_git(["status", "--porcelain=v1"], cwd=work)

    assert status_before == status_after  # structurally unchanged (still "M README.md")

    with pytest.raises(RepositoryError):
        repo_module.verify_fingerprint_unchanged(
            work, fingerprint, context="deterministic verification"
        )


def test_changed_reviewed_diff_prevents_commit(git_env: GitEnv) -> None:
    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")
    (work / "e.txt").write_text("e\n", encoding="utf-8")
    patch = repo_module.build_checkpoint_patch_uncommitted(work)

    (work / "e.txt").write_text("e\nmore\n", encoding="utf-8")

    with pytest.raises(RepositoryError):
        repo_module.commit_reviewed_checkpoint(
            work, reviewed_patch=patch, message="stale", paths=["e.txt"]
        )


def test_commit_rejects_omitted_reviewed_file(git_env: GitEnv) -> None:
    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")
    (work / "a.txt").write_text("a\n", encoding="utf-8")
    (work / "b.txt").write_text("b\n", encoding="utf-8")
    reviewed_patch = repo_module.build_checkpoint_patch_uncommitted(work)

    with pytest.raises(RepositoryError):
        repo_module.commit_reviewed_checkpoint(
            work, reviewed_patch=reviewed_patch, message="partial", paths=["a.txt"]
        )


def test_commit_rejects_unreviewed_extra_staged_file(git_env: GitEnv) -> None:
    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")
    (work / "a.txt").write_text("a\n", encoding="utf-8")
    reviewed_patch = repo_module.build_checkpoint_patch_uncommitted(work)

    (work / "b.txt").write_text("b\n", encoding="utf-8")

    with pytest.raises(RepositoryError):
        repo_module.commit_reviewed_checkpoint(
            work,
            reviewed_patch=reviewed_patch,
            message="sneaky",
            paths=["a.txt", "b.txt"],
        )


def test_commit_succeeds_with_exact_reviewed_file_set(git_env: GitEnv) -> None:
    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")
    (work / "a.txt").write_text("a\n", encoding="utf-8")
    (work / "b.txt").write_text("b\n", encoding="utf-8")
    reviewed_patch = repo_module.build_checkpoint_patch_uncommitted(work)

    sha = repo_module.commit_reviewed_checkpoint(
        work, reviewed_patch=reviewed_patch, message="full", paths=["a.txt", "b.txt"]
    )

    assert sha == repo_module.head_sha(work)
    assert repo_module.is_worktree_clean(work)


def test_origin_main_movement_detectable(git_env: GitEnv) -> None:
    work = git_env.work
    before = repo_module.origin_main_sha(work)

    _push_new_commit_to_origin_main(git_env.seed)

    repo_module.fetch_origin(work)
    after = repo_module.origin_main_sha(work)

    assert after != before


def test_missing_gh_fails_closed_on_pr_create(git_env: GitEnv) -> None:
    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")

    with pytest.raises(RepositoryError):
        repo_module.create_draft_pull_request(
            work,
            title="t",
            body="b",
            head="delivery",
            expected_branch="delivery",
            gh_command=("this-executable-does-not-exist-anywhere",),
        )


def test_missing_gh_fails_closed_on_pr_checks(git_env: GitEnv) -> None:
    work = git_env.work

    with pytest.raises(RepositoryError):
        repo_module.pr_checks(
            work, "1", gh_command=("this-executable-does-not-exist-anywhere",)
        )


def test_missing_gh_fails_closed_on_pr_checks_json(git_env: GitEnv) -> None:
    work = git_env.work

    with pytest.raises(RepositoryError):
        repo_module.pr_checks_json(
            work, "1", gh_command=("this-executable-does-not-exist-anywhere",)
        )


def test_pr_checks_json_parses_structured_output(git_env: GitEnv) -> None:
    work = git_env.work
    fake_gh = (
        "import sys, json\n"
        "args = sys.argv[1:]\n"
        "if args[:2] == ['pr', 'checks']:\n"
        "    assert args[2] == '1'\n"
        "    assert '--json' in args\n"
        "    print(json.dumps([\n"
        "        {'name': 'build', 'state': 'SUCCESS', 'bucket': 'pass'},\n"
        "        {'name': 'lint', 'state': 'FAILURE', 'bucket': 'fail'},\n"
        "    ]))\n"
        # A mixed pass/fail result is gh's exit-1 outcome, never exit 0 --
        # realistic exit semantics, matching gh's own documented behavior.
        "    sys.exit(1)\n"
        "else:\n"
        "    raise SystemExit(1)\n"
    )

    checks = repo_module.pr_checks_json(
        work, "1", gh_command=(sys.executable, "-c", fake_gh)
    )

    assert checks == [
        {"name": "build", "state": "SUCCESS", "bucket": "pass"},
        {"name": "lint", "state": "FAILURE", "bucket": "fail"},
    ]


def test_pr_checks_json_rejects_non_json_output(git_env: GitEnv) -> None:
    work = git_env.work
    fake_gh = (
        "import sys\n"
        "args = sys.argv[1:]\n"
        "if args[:2] == ['pr', 'checks']:\n"
        "    print('not json at all')\n"
        "else:\n"
        "    raise SystemExit(1)\n"
    )

    with pytest.raises(RepositoryError):
        repo_module.pr_checks_json(
            work, "1", gh_command=(sys.executable, "-c", fake_gh)
        )


def test_pr_checks_json_rejects_non_array_json_output(git_env: GitEnv) -> None:
    work = git_env.work
    fake_gh = (
        "import sys\n"
        "args = sys.argv[1:]\n"
        "if args[:2] == ['pr', 'checks']:\n"
        "    print('{\"not\": \"a list\"}')\n"
        "else:\n"
        "    raise SystemExit(1)\n"
    )

    with pytest.raises(RepositoryError):
        repo_module.pr_checks_json(
            work, "1", gh_command=(sys.executable, "-c", fake_gh)
        )


def test_pr_checks_json_invokes_required_flag(git_env: GitEnv) -> None:
    """The required-CI gate must query only checks GitHub actually marks
    required -- an unrelated optional check must never be able to block or
    satisfy it."""

    work = git_env.work
    fake_gh = (
        "import sys, json\n"
        "args = sys.argv[1:]\n"
        "if args[:2] == ['pr', 'checks']:\n"
        "    assert '--required' in args, args\n"
        "    print(json.dumps([{'name': 'build', 'state': 'SUCCESS', 'bucket': 'pass'}]))\n"
        "else:\n"
        "    raise SystemExit(1)\n"
    )

    checks = repo_module.pr_checks_json(
        work, "1", gh_command=(sys.executable, "-c", fake_gh)
    )

    assert checks == [{"name": "build", "state": "SUCCESS", "bucket": "pass"}]


_FAKE_GH_CHECKS_EXIT_CODE_TEMPLATE = (
    "import sys, json\n"
    "args = sys.argv[1:]\n"
    "if args[:2] == ['pr', 'checks']:\n"
    "    sys.stdout.write({body!r})\n"
    "    sys.exit({exit_code})\n"
    "else:\n"
    "    raise SystemExit(1)\n"
)


def test_pr_checks_json_exit_0_with_passing_json(git_env: GitEnv) -> None:
    work = git_env.work
    body = json.dumps([{"name": "build", "state": "SUCCESS", "bucket": "pass"}])
    fake_gh = _FAKE_GH_CHECKS_EXIT_CODE_TEMPLATE.format(body=body, exit_code=0)

    checks = repo_module.pr_checks_json(
        work, "1", gh_command=(sys.executable, "-c", fake_gh)
    )

    assert checks == [{"name": "build", "state": "SUCCESS", "bucket": "pass"}]


def test_pr_checks_json_exit_8_pending_is_parsed_not_raised(git_env: GitEnv) -> None:
    """``gh pr checks`` documents exit 8 for still-pending checks -- the
    generic strict ``_gh()`` would raise on this before ever parsing the
    JSON body; ``pr_checks_json`` must not route through it."""

    work = git_env.work
    body = json.dumps([{"name": "build", "state": "PENDING", "bucket": "pending"}])
    fake_gh = _FAKE_GH_CHECKS_EXIT_CODE_TEMPLATE.format(body=body, exit_code=8)

    checks = repo_module.pr_checks_json(
        work, "1", gh_command=(sys.executable, "-c", fake_gh)
    )

    assert checks == [{"name": "build", "state": "PENDING", "bucket": "pending"}]


def test_pr_checks_json_exit_1_with_failing_json_is_parsed_not_raised(
    git_env: GitEnv,
) -> None:
    """``gh pr checks`` documents exit 1 for failing/incomplete checks --
    valid structured JSON consistent with a non-passing result is accepted
    rather than treated as a bare tool error."""

    work = git_env.work
    body = json.dumps([{"name": "build", "state": "FAILURE", "bucket": "fail"}])
    fake_gh = _FAKE_GH_CHECKS_EXIT_CODE_TEMPLATE.format(body=body, exit_code=1)

    checks = repo_module.pr_checks_json(
        work, "1", gh_command=(sys.executable, "-c", fake_gh)
    )

    assert checks == [{"name": "build", "state": "FAILURE", "bucket": "fail"}]


def test_pr_checks_json_exit_1_with_all_passing_json_is_inconsistent(
    git_env: GitEnv,
) -> None:
    """An exit 1 (gh's own failing/incomplete signal) whose JSON body
    claims every check passed is an inconsistent, ambiguous result --
    never silently resolved in either direction."""

    work = git_env.work
    body = json.dumps([{"name": "build", "state": "SUCCESS", "bucket": "pass"}])
    fake_gh = _FAKE_GH_CHECKS_EXIT_CODE_TEMPLATE.format(body=body, exit_code=1)

    with pytest.raises(RepositoryError):
        repo_module.pr_checks_json(
            work, "1", gh_command=(sys.executable, "-c", fake_gh)
        )


def test_pr_checks_json_exit_1_with_malformed_output_raises(git_env: GitEnv) -> None:
    work = git_env.work
    fake_gh = _FAKE_GH_CHECKS_EXIT_CODE_TEMPLATE.format(
        body="not json at all", exit_code=1
    )

    with pytest.raises(RepositoryError):
        repo_module.pr_checks_json(
            work, "1", gh_command=(sys.executable, "-c", fake_gh)
        )


def test_pr_checks_json_exit_1_with_empty_output_raises(git_env: GitEnv) -> None:
    work = git_env.work
    fake_gh = _FAKE_GH_CHECKS_EXIT_CODE_TEMPLATE.format(body="[]", exit_code=1)

    with pytest.raises(RepositoryError):
        repo_module.pr_checks_json(
            work, "1", gh_command=(sys.executable, "-c", fake_gh)
        )


def test_pr_checks_json_unexpected_exit_code_raises(git_env: GitEnv) -> None:
    work = git_env.work
    body = json.dumps([{"name": "build", "state": "SUCCESS", "bucket": "pass"}])
    fake_gh = _FAKE_GH_CHECKS_EXIT_CODE_TEMPLATE.format(body=body, exit_code=2)

    with pytest.raises(RepositoryError):
        repo_module.pr_checks_json(
            work, "1", gh_command=(sys.executable, "-c", fake_gh)
        )


def test_pr_head_sha_parses_head_ref_oid(git_env: GitEnv) -> None:
    work = git_env.work
    fake_gh = (
        "import sys, json\n"
        "args = sys.argv[1:]\n"
        "if args[:2] == ['pr', 'view']:\n"
        "    assert args[2] == '1'\n"
        "    assert '--json' in args and 'headRefOid' in args\n"
        "    print(json.dumps({'headRefOid': 'abc123'}))\n"
        "else:\n"
        "    raise SystemExit(1)\n"
    )

    sha = repo_module.pr_head_sha(work, "1", gh_command=(sys.executable, "-c", fake_gh))

    assert sha == "abc123"


def test_pr_head_sha_rejects_missing_field(git_env: GitEnv) -> None:
    work = git_env.work
    fake_gh = (
        "import sys, json\n"
        "args = sys.argv[1:]\n"
        "if args[:2] == ['pr', 'view']:\n"
        "    print(json.dumps({'somethingElse': 'x'}))\n"
        "else:\n"
        "    raise SystemExit(1)\n"
    )

    with pytest.raises(RepositoryError):
        repo_module.pr_head_sha(work, "1", gh_command=(sys.executable, "-c", fake_gh))


def test_pr_head_sha_rejects_non_json_output(git_env: GitEnv) -> None:
    work = git_env.work
    fake_gh = (
        "import sys\n"
        "args = sys.argv[1:]\n"
        "if args[:2] == ['pr', 'view']:\n"
        "    print('not json')\n"
        "else:\n"
        "    raise SystemExit(1)\n"
    )

    with pytest.raises(RepositoryError):
        repo_module.pr_head_sha(work, "1", gh_command=(sys.executable, "-c", fake_gh))


def test_missing_gh_fails_closed_on_pr_head_sha(git_env: GitEnv) -> None:
    work = git_env.work

    with pytest.raises(RepositoryError):
        repo_module.pr_head_sha(
            work, "1", gh_command=("this-executable-does-not-exist-anywhere",)
        )


# --- pr_required_checks: "no required checks configured" is the empty set -----


def test_pr_required_checks_recognizes_no_required_checks_configured(
    git_env: GitEnv,
) -> None:
    work = git_env.work
    fake_gh = (
        "import sys\n"
        "args = sys.argv[1:]\n"
        "if args[:2] == ['pr', 'checks']:\n"
        "    sys.stderr.write('no required checks reported on the \"main\" branch\\n')\n"
        "    sys.exit(1)\n"
        "else:\n"
        "    raise SystemExit(1)\n"
    )

    result = repo_module.pr_required_checks(
        work, "1", gh_command=(sys.executable, "-c", fake_gh)
    )

    assert result.no_required_checks is True
    assert result.checks == []


def test_pr_required_checks_exit_1_auth_error_raises(git_env: GitEnv) -> None:
    """A genuine auth/tool error must never be misclassified as "no
    required checks configured", even if its message happens to also
    mention required checks."""

    work = git_env.work
    fake_gh = (
        "import sys\n"
        "args = sys.argv[1:]\n"
        "if args[:2] == ['pr', 'checks']:\n"
        "    sys.stderr.write(\n"
        "        'authentication failed: no required checks could be reached\\n'\n"
        "    )\n"
        "    sys.exit(1)\n"
        "else:\n"
        "    raise SystemExit(1)\n"
    )

    with pytest.raises(RepositoryError):
        repo_module.pr_required_checks(
            work, "1", gh_command=(sys.executable, "-c", fake_gh)
        )


def test_pr_required_checks_exit_1_unrecognized_empty_output_raises(
    git_env: GitEnv,
) -> None:
    work = git_env.work
    fake_gh = (
        "import sys\n"
        "args = sys.argv[1:]\n"
        "if args[:2] == ['pr', 'checks']:\n"
        "    sys.exit(1)\n"
        "else:\n"
        "    raise SystemExit(1)\n"
    )

    with pytest.raises(RepositoryError):
        repo_module.pr_required_checks(
            work, "1", gh_command=(sys.executable, "-c", fake_gh)
        )


# --- an empty JSON array "[]" is never an ordinary checks result -------------


def test_pr_required_checks_exit_0_with_empty_array_raises(git_env: GitEnv) -> None:
    """Ambiguous/empty CI evidence must never silently satisfy the gate:
    exit 0 with stdout "[]" is not a decidable checks result."""

    work = git_env.work
    fake_gh = _FAKE_GH_CHECKS_EXIT_CODE_TEMPLATE.format(body="[]", exit_code=0)

    with pytest.raises(RepositoryError):
        repo_module.pr_required_checks(
            work, "1", gh_command=(sys.executable, "-c", fake_gh)
        )


def test_pr_required_checks_exit_8_with_empty_array_raises(git_env: GitEnv) -> None:
    work = git_env.work
    fake_gh = _FAKE_GH_CHECKS_EXIT_CODE_TEMPLATE.format(body="[]", exit_code=8)

    with pytest.raises(RepositoryError):
        repo_module.pr_required_checks(
            work, "1", gh_command=(sys.executable, "-c", fake_gh)
        )


def test_pr_required_checks_exit_1_with_empty_array_and_recognized_diagnostic_is_no_required_checks(
    git_env: GitEnv,
) -> None:
    """An empty JSON array at exit 1 must fall through to the
    positively-recognized "no required checks configured" stderr
    diagnostic, rather than being consumed by the ordinary (now
    non-empty-only) checks-JSON path and raising an inconsistency error
    before that diagnostic is ever consulted."""

    work = git_env.work
    fake_gh = (
        "import sys\n"
        "args = sys.argv[1:]\n"
        "if args[:2] == ['pr', 'checks']:\n"
        "    sys.stdout.write('[]')\n"
        "    sys.stderr.write('no required checks reported on the \"main\" branch\\n')\n"
        "    sys.exit(1)\n"
        "else:\n"
        "    raise SystemExit(1)\n"
    )

    result = repo_module.pr_required_checks(
        work, "1", gh_command=(sys.executable, "-c", fake_gh)
    )

    assert result.no_required_checks is True
    assert result.checks == []
    assert result.returncode == 1


def test_pr_required_checks_exit_1_with_empty_array_and_no_diagnostic_raises(
    git_env: GitEnv,
) -> None:
    work = git_env.work
    fake_gh = _FAKE_GH_CHECKS_EXIT_CODE_TEMPLATE.format(body="[]", exit_code=1)

    with pytest.raises(RepositoryError):
        repo_module.pr_required_checks(
            work, "1", gh_command=(sys.executable, "-c", fake_gh)
        )


def test_pr_required_checks_pass_pending_fail_unchanged(git_env: GitEnv) -> None:
    """Existing exit 0/8/1 pass/pending/fail behavior is unaffected by the
    "no required checks" distinction -- it only ever applies for the
    positively recognized signal."""

    work = git_env.work

    passing = json.dumps([{"name": "build", "state": "SUCCESS", "bucket": "pass"}])
    fake_gh_pass = _FAKE_GH_CHECKS_EXIT_CODE_TEMPLATE.format(body=passing, exit_code=0)
    result = repo_module.pr_required_checks(
        work, "1", gh_command=(sys.executable, "-c", fake_gh_pass)
    )
    assert result.no_required_checks is False
    assert result.checks == [{"name": "build", "state": "SUCCESS", "bucket": "pass"}]

    pending = json.dumps([{"name": "build", "state": "PENDING", "bucket": "pending"}])
    fake_gh_pending = _FAKE_GH_CHECKS_EXIT_CODE_TEMPLATE.format(body=pending, exit_code=8)
    result = repo_module.pr_required_checks(
        work, "1", gh_command=(sys.executable, "-c", fake_gh_pending)
    )
    assert result.no_required_checks is False
    assert result.checks == [{"name": "build", "state": "PENDING", "bucket": "pending"}]

    failing = json.dumps([{"name": "build", "state": "FAILURE", "bucket": "fail"}])
    fake_gh_fail = _FAKE_GH_CHECKS_EXIT_CODE_TEMPLATE.format(body=failing, exit_code=1)
    result = repo_module.pr_required_checks(
        work, "1", gh_command=(sys.executable, "-c", fake_gh_fail)
    )
    assert result.no_required_checks is False
    assert result.checks == [{"name": "build", "state": "FAILURE", "bucket": "fail"}]


def test_pr_required_checks_failing_check_named_no_required_checks_is_never_misclassified(
    git_env: GitEnv,
) -> None:
    """A real, valid, non-empty checks JSON array is ALWAYS a real checks
    result -- never reclassified as "no required checks configured"
    because of text inside it. A required check literally named "No
    Required Checks Policy" that is failing must still be reported as a
    failing check, not silently discarded as an empty required set."""

    work = git_env.work
    failing = json.dumps(
        [{"name": "No Required Checks Policy", "state": "FAILURE", "bucket": "fail"}]
    )
    fake_gh = _FAKE_GH_CHECKS_EXIT_CODE_TEMPLATE.format(body=failing, exit_code=1)

    result = repo_module.pr_required_checks(
        work, "1", gh_command=(sys.executable, "-c", fake_gh)
    )

    assert result.no_required_checks is False
    assert result.checks == [
        {"name": "No Required Checks Policy", "state": "FAILURE", "bucket": "fail"}
    ]


def test_pr_required_checks_exit_8_with_all_passing_json_is_inconsistent(
    git_env: GitEnv,
) -> None:
    """Exit 8 (gh's own "pending" signal) whose JSON body claims every
    check already passed is inconsistent -- never silently accepted as
    success."""

    work = git_env.work
    body = json.dumps([{"name": "build", "state": "SUCCESS", "bucket": "pass"}])
    fake_gh = _FAKE_GH_CHECKS_EXIT_CODE_TEMPLATE.format(body=body, exit_code=8)

    with pytest.raises(RepositoryError):
        repo_module.pr_required_checks(
            work, "1", gh_command=(sys.executable, "-c", fake_gh)
        )


def test_pr_required_checks_malformed_check_object_cannot_satisfy_ci(
    git_env: GitEnv,
) -> None:
    """A check entry missing ``name``/``state`` (only ``bucket`` present)
    is malformed and must never be accepted as valid checks evidence."""

    work = git_env.work
    body = json.dumps([{"bucket": "pass"}])
    fake_gh = _FAKE_GH_CHECKS_EXIT_CODE_TEMPLATE.format(body=body, exit_code=0)

    with pytest.raises(RepositoryError):
        repo_module.pr_required_checks(
            work, "1", gh_command=(sys.executable, "-c", fake_gh)
        )


def test_pr_required_checks_unrecognized_bucket_value_cannot_satisfy_ci(
    git_env: GitEnv,
) -> None:
    """A ``bucket`` value outside gh's own known set (pass/fail/pending/
    skipping/cancel) is malformed output -- never silently treated as any
    particular outcome."""

    work = git_env.work
    body = json.dumps([{"name": "build", "state": "SOMETHING", "bucket": "unknown"}])
    fake_gh = _FAKE_GH_CHECKS_EXIT_CODE_TEMPLATE.format(body=body, exit_code=0)

    with pytest.raises(RepositoryError):
        repo_module.pr_required_checks(
            work, "1", gh_command=(sys.executable, "-c", fake_gh)
        )


def test_pr_required_checks_exit_0_with_skipping_bucket_satisfies_gate(
    git_env: GitEnv,
) -> None:
    """GitHub treats a skipped/neutral required check as a successful
    conclusion -- gh's own exit 0 ("every required check succeeded") must
    be accepted even when the only check present carries bucket
    "skipping" rather than "pass"."""

    work = git_env.work
    body = json.dumps([{"name": "docs", "state": "SKIPPED", "bucket": "skipping"}])
    fake_gh = _FAKE_GH_CHECKS_EXIT_CODE_TEMPLATE.format(body=body, exit_code=0)

    result = repo_module.pr_required_checks(
        work, "1", gh_command=(sys.executable, "-c", fake_gh)
    )

    assert result.no_required_checks is False
    assert result.returncode == 0
    assert result.checks == [{"name": "docs", "state": "SKIPPED", "bucket": "skipping"}]


def test_pr_required_checks_exit_0_mixed_pass_and_skipping_satisfies_gate(
    git_env: GitEnv,
) -> None:
    work = git_env.work
    body = json.dumps(
        [
            {"name": "build", "state": "SUCCESS", "bucket": "pass"},
            {"name": "docs", "state": "SKIPPED", "bucket": "skipping"},
        ]
    )
    fake_gh = _FAKE_GH_CHECKS_EXIT_CODE_TEMPLATE.format(body=body, exit_code=0)

    result = repo_module.pr_required_checks(
        work, "1", gh_command=(sys.executable, "-c", fake_gh)
    )

    assert result.no_required_checks is False
    assert result.returncode == 0
    assert len(result.checks) == 2


def test_pr_required_checks_exit_0_with_fail_bucket_is_inconsistent(
    git_env: GitEnv,
) -> None:
    """gh's own exit 0 ("every required check succeeded") whose JSON body
    contains a failing check is inconsistent -- never silently accepted
    as success."""

    work = git_env.work
    body = json.dumps([{"name": "build", "state": "FAILURE", "bucket": "fail"}])
    fake_gh = _FAKE_GH_CHECKS_EXIT_CODE_TEMPLATE.format(body=body, exit_code=0)

    with pytest.raises(RepositoryError):
        repo_module.pr_required_checks(
            work, "1", gh_command=(sys.executable, "-c", fake_gh)
        )


def test_pr_required_checks_exit_0_with_pending_bucket_is_inconsistent(
    git_env: GitEnv,
) -> None:
    work = git_env.work
    body = json.dumps([{"name": "build", "state": "PENDING", "bucket": "pending"}])
    fake_gh = _FAKE_GH_CHECKS_EXIT_CODE_TEMPLATE.format(body=body, exit_code=0)

    with pytest.raises(RepositoryError):
        repo_module.pr_required_checks(
            work, "1", gh_command=(sys.executable, "-c", fake_gh)
        )


def test_create_draft_pull_request_returns_url(git_env: GitEnv) -> None:
    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")

    url = repo_module.create_draft_pull_request(
        work,
        title="Test PR",
        body="body",
        head="delivery",
        expected_branch="delivery",
        gh_command=(sys.executable, "-c", _FAKE_GH_PR_CREATE),
    )

    assert url == "https://github.com/example/repo/pull/1"


def test_create_draft_pull_request_refuses_protected_head(git_env: GitEnv) -> None:
    work = git_env.work

    with pytest.raises(RepositoryError):
        repo_module.create_draft_pull_request(
            work,
            title="t",
            body="b",
            head="main",
            expected_branch="main",
            gh_command=(sys.executable, "-c", _FAKE_GH_PR_CREATE),
        )


def test_create_draft_pull_request_rejects_head_not_expected_branch(
    git_env: GitEnv,
) -> None:
    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")

    with pytest.raises(RepositoryError):
        repo_module.create_draft_pull_request(
            work,
            title="t",
            body="b",
            head="some-other-branch",
            expected_branch="delivery",
            gh_command=(sys.executable, "-c", _FAKE_GH_PR_CREATE),
        )


def test_create_draft_pull_request_rejects_current_branch_mismatch(
    git_env: GitEnv,
) -> None:
    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")
    _run_git(["checkout", "-q", "-b", "another"], cwd=work)

    with pytest.raises(RepositoryError):
        repo_module.create_draft_pull_request(
            work,
            title="t",
            body="b",
            head="delivery",
            expected_branch="delivery",
            gh_command=(sys.executable, "-c", _FAKE_GH_PR_CREATE),
        )


def test_create_draft_pull_request_rejects_non_main_base(git_env: GitEnv) -> None:
    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")

    with pytest.raises(RepositoryError):
        repo_module.create_draft_pull_request(
            work,
            title="t",
            body="b",
            head="delivery",
            expected_branch="delivery",
            base="develop",
            gh_command=(sys.executable, "-c", _FAKE_GH_PR_CREATE),
        )


def test_create_draft_pull_request_valid_sends_expected_gh_args(
    git_env: GitEnv,
) -> None:
    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")

    url = repo_module.create_draft_pull_request(
        work,
        title="Test PR",
        body="body",
        head="delivery",
        expected_branch="delivery",
        gh_command=(sys.executable, "-c", _FAKE_GH_PR_CREATE_RECORDING),
    )

    assert url == "https://github.com/example/repo/pull/1"
    received_args = json.loads(
        (work / "gh_invocation.json").read_text(encoding="utf-8")
    )
    assert received_args[:3] == ["pr", "create", "--draft"]
    assert received_args[received_args.index("--base") + 1] == "main"
    assert received_args[received_args.index("--head") + 1] == "delivery"


def test_ambiguous_push_timeout_fails_closed_without_retry(
    git_env: GitEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = git_env.work
    repo_module.create_delivery_branch_from_origin_main(work, "delivery")
    (work / "f.txt").write_text("f\n", encoding="utf-8")
    patch = repo_module.build_checkpoint_patch_uncommitted(work)
    repo_module.commit_reviewed_checkpoint(
        work, reviewed_patch=patch, message="add f", paths=["f.txt"]
    )

    push_call_count = 0
    real_run = subprocess.run

    def flaky_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal push_call_count
        if "push" in args:
            push_call_count += 1
            raise subprocess.TimeoutExpired(cmd=args, timeout=1)
        return real_run(args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(repo_module.subprocess, "run", flaky_run)

    with pytest.raises(RepositoryError):
        repo_module.push_delivery_branch(
            work, branch="delivery", expected_branch="delivery"
        )

    assert push_call_count == 1


def test_forbidden_merge_commands_never_emitted(
    git_env: GitEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    real_run = subprocess.run

    def recording_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(list(args))
        return real_run(args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(repo_module.subprocess, "run", recording_run)

    work = git_env.work
    branch = "delivery-guard"
    repo_module.create_delivery_branch_from_origin_main(work, branch)
    (work / "file.txt").write_text("content\n", encoding="utf-8")
    patch = repo_module.build_checkpoint_patch_uncommitted(work)
    repo_module.commit_reviewed_checkpoint(
        work, reviewed_patch=patch, message="test commit", paths=["file.txt"]
    )
    repo_module.push_delivery_branch(work, branch=branch, expected_branch=branch)
    repo_module.create_draft_pull_request(
        work,
        title="t",
        body="b",
        head=branch,
        expected_branch=branch,
        gh_command=(sys.executable, "-c", _FAKE_GH_PR_CREATE),
    )

    assert calls, "expected at least one recorded subprocess invocation"
    for call in calls:
        joined = " ".join(call).lower()
        assert "merge" not in joined
