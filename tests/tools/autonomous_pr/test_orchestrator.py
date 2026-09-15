import dataclasses
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from tools.autonomous_pr import orchestrator as orch_module
from tools.autonomous_pr.agents import AgentInvocationSpec
from tools.autonomous_pr.model import Phase, ReviewResult, RunOutcome, AgentRole
from tools.autonomous_pr.orchestrator import OrchestratorConfig, run

_TASK_ID = "TSK-9001"

_GOAL_MARKER = "GOAL_MARKER_TEXT"
_SCOPE_MARKER = "SCOPE_MARKER_TEXT"
_OUT_OF_SCOPE_MARKER = "OUT_OF_SCOPE_MARKER_TEXT"
_ACCEPTANCE_MARKER = "ACCEPTANCE_CRITERIA_MARKER_TEXT"
_VERIFICATION_MARKER = "VERIFICATION_MARKER_TEXT"


def _run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"
    return result.stdout


def _configure_user(repo: Path) -> None:
    _run_git(["config", "user.email", "harness-test@example.com"], cwd=repo)
    _run_git(["config", "user.name", "Harness Test"], cwd=repo)


def _task_md_text(task_id: str, roadmap_target: str = "Test roadmap target") -> str:
    return (
        "# Current position\n"
        "\n"
        f"- **Current:** {task_id}\n"
        "\n"
        "---\n"
        "\n"
        "# Open task index\n"
        "\n"
        "| ID | Status | P | Size | Group | Roadmap target | Title |\n"
        "| --- | --- | --- | --- | --- | --- | --- |\n"
        f"| `{task_id}` | `Current` | `P2` | `M` | `engineering` | {roadmap_target} | Test task |\n"
        "\n"
        "---\n"
        "\n"
        "# Open task details\n"
        "\n"
        f"## {task_id} — Test task\n"
        "\n"
        "**Status:** `Current`\n"
        "\n"
        "**Priority:** `P2`\n"
        "\n"
        "**Size:** `M`\n"
        "\n"
        "**Group:** `engineering`\n"
        "\n"
        f"**Roadmap target:** {roadmap_target}\n"
        "\n"
        "**Depends on:** —\n"
        "\n"
        "**Contract impact:** `none`\n"
        "\n"
        "### Goal\n"
        "\n"
        f"{_GOAL_MARKER}.\n"
        "\n"
        "### Scope\n"
        "\n"
        f"- {_SCOPE_MARKER}\n"
        "\n"
        "### Out of scope\n"
        "\n"
        f"- {_OUT_OF_SCOPE_MARKER}\n"
        "\n"
        "### Acceptance criteria\n"
        "\n"
        f"- {_ACCEPTANCE_MARKER}\n"
        "\n"
        "### Verification\n"
        "\n"
        f"- {_VERIFICATION_MARKER}\n"
        "\n"
        "---\n"
        "\n"
        "# Recently completed\n"
        "\n"
        "| ID | Title |\n"
        "| --- | --- |\n"
    )


@dataclass
class Env:
    origin: Path
    seed: Path
    work: Path
    scratch: Path


@pytest.fixture
def env(tmp_path: Path) -> Env:
    origin = tmp_path / "origin.git"
    _run_git(["init", "-q", "--bare", "-b", "main", str(origin)], cwd=tmp_path)

    seed = tmp_path / "seed"
    _run_git(["init", "-q", "-b", "main", str(seed)], cwd=tmp_path)
    _configure_user(seed)
    (seed / "README.md").write_text("seed\n", encoding="utf-8")
    (seed / "docs").mkdir()
    (seed / "docs" / "TASK.md").write_text(_task_md_text(_TASK_ID), encoding="utf-8")
    _run_git(["add", "README.md", "docs/TASK.md"], cwd=seed)
    _run_git(["commit", "-q", "-m", "seed"], cwd=seed)
    _run_git(["remote", "add", "origin", str(origin)], cwd=seed)
    _run_git(["push", "-q", "origin", "main"], cwd=seed)

    work = tmp_path / "work"
    _run_git(["clone", "-q", str(origin), str(work)], cwd=tmp_path)
    _configure_user(work)

    scratch = tmp_path / "scratch"
    scratch.mkdir()

    return Env(origin=origin, seed=seed, work=work, scratch=scratch)


def _implementer_spec(work: Path, code: str, timeout: float = 10.0) -> AgentInvocationSpec:
    return AgentInvocationSpec(
        role=AgentRole.IMPLEMENTER,
        executable=sys.executable,
        args=("-c", code),
        cwd=work,
        timeout_seconds=timeout,
        can_edit_working_files=True,
        has_git_or_github_write_access=False,
    )


def _reviewer_spec(work: Path, code: str, timeout: float = 10.0) -> AgentInvocationSpec:
    return AgentInvocationSpec(
        role=AgentRole.REVIEWER,
        executable=sys.executable,
        args=("-c", code),
        cwd=work,
        timeout_seconds=timeout,
        fresh_context_capable=True,
        has_git_or_github_write_access=False,
    )


def _verify_true() -> tuple[str, ...]:
    return (sys.executable, "-c", "raise SystemExit(0)")


def _default_config(
    env: Env,
    *,
    implementer_spec: AgentInvocationSpec,
    reviewer_spec: AgentInvocationSpec,
    max_repairs: int = 2,
    verification_commands: tuple[tuple[str, ...], ...] = (_verify_true(),),
    delivery_branch: str = "delivery",
) -> OrchestratorConfig:
    return OrchestratorConfig(
        task_id=_TASK_ID,
        repo=env.work,
        implementer_spec=implementer_spec,
        reviewer_spec=reviewer_spec,
        verification_commands=verification_commands,
        delivery_branch=delivery_branch,
        max_repairs=max_repairs,
    )


def _origin_branch_sha(env: Env, branch: str) -> str:
    return _run_git(
        ["--git-dir", str(env.origin), "rev-parse", f"refs/heads/{branch}"],
        cwd=env.origin,
    ).strip()


# --- fake agent scripts ------------------------------------------------------
#
# OrchestratorConfig carries exactly one implementer_spec and one
# reviewer_spec for the whole run (matching the real contract: one
# orchestrator-selected reviewer per invocation, never one per phase). Every
# fake script below is therefore invoked for BOTH the planning phase and the
# implementation-checkpoint phase and must behave sensibly for both: the
# planning prompt never contains a literal "PLAN:" line, while the
# implementation-checkpoint prompt always does
# (orchestrator._build_implementation_prompt); the checkpoint review input
# always contains a literal "REVIEW_PATCH:" line
# (orchestrator._build_checkpoint_review_input), while the plan review input
# never does. Scripts use these two markers to tell the phases apart.


def _implementer_wip_then_done(counter_path: Path) -> str:
    """Planning: prints a harmless plan. Checkpoint: writes 'wip' on ATTEMPT
    0 and 'done' from ATTEMPT 1 onward -- a realistic bounded-repair
    fixture. Every invocation (either phase) appends one 'x' to
    ``counter_path``."""

    counter = counter_path.as_posix()
    return (
        "import sys\n"
        f"with open('{counter}', 'a', encoding='utf-8') as c:\n"
        "    c.write('x')\n"
        "data = sys.stdin.read()\n"
        "if 'PLAN:' not in data:\n"
        "    print('PLAN: implement the thing')\n"
        "else:\n"
        "    attempt = 0\n"
        "    for line in data.splitlines():\n"
        "        line = line.strip()\n"
        "        if line.startswith('ATTEMPT:'):\n"
        "            attempt = int(line.split(':', 1)[1].strip())\n"
        "    content = 'done\\n' if attempt >= 1 else 'wip\\n'\n"
        "    with open('work_output.txt', 'w', encoding='utf-8') as f:\n"
        "        f.write(content)\n"
        "    print('implemented attempt', attempt)\n"
    )


def _implementer_always_done(counter_path: Path | None = None) -> str:
    """Planning: prints a harmless plan (writes nothing to the worktree, so
    it is safe under the strict planning fingerprint guard). Checkpoint:
    always writes 'done' immediately, regardless of attempt."""

    counter_lines = ""
    if counter_path is not None:
        counter = counter_path.as_posix()
        counter_lines = (
            f"with open('{counter}', 'a', encoding='utf-8') as c:\n"
            "    c.write('x')\n"
        )
    return (
        "import sys\n"
        f"{counter_lines}"
        "data = sys.stdin.read()\n"
        "if 'PLAN:' not in data:\n"
        "    print('PLAN: implement the thing')\n"
        "else:\n"
        "    with open('work_output.txt', 'w', encoding='utf-8') as f:\n"
        "        f.write('done\\n')\n"
        "    print('implemented')\n"
    )


_IMPLEMENTER_MUTATES_BRANCH_HEAD_DURING_CHECKPOINT_ONLY = (
    "import sys, subprocess\n"
    "data = sys.stdin.read()\n"
    "if 'PLAN:' not in data:\n"
    "    print('PLAN: implement the thing')\n"
    "else:\n"
    "    subprocess.run(\n"
    "        ['git', 'commit', '--allow-empty', '-m', 'sneaky commit'],\n"
    "        check=True,\n"
    "    )\n"
    "    with open('work_output.txt', 'w', encoding='utf-8') as f:\n"
    "        f.write('done\\n')\n"
    "    print('implemented')\n"
)

_IMPLEMENTER_MUTATES_WORKTREE_DURING_PLANNING = (
    "with open('stray_during_planning.txt', 'w', encoding='utf-8') as f:\n"
    "    f.write('stray\\n')\n"
    "print('PLAN: implement the thing')\n"
)

_PLAN_IMPLEMENTER_WITH_FORGED_APPROVAL = (
    "print('PLAN: implement the thing')\n"
    "print('this plan text even says APPROVED, which must not matter')\n"
)
_PLAN_IMPLEMENTER_OK = "print('PLAN: implement the thing')\n"

_PLAN_REVIEWER_APPROVE = "print('APPROVED')\n"
_PLAN_REVIEWER_CHANGES = "print('rework please'); print('CHANGES_REQUESTED')\n"
_PLAN_REVIEWER_BLOCKED = "print('BLOCKED')\n"

# Reviewer scripts below always approve a plan review (no 'REVIEW_PATCH:'
# marker present) and apply the behavior under test only to a checkpoint
# review (marker present) -- see the module note above.

_REVIEWER_PLAN_OK_DONE_CHECKPOINT = (
    "import sys\n"
    "data = sys.stdin.read()\n"
    "if 'REVIEW_PATCH:' not in data:\n"
    "    print('APPROVED')\n"
    "elif 'done' in data:\n"
    "    print('APPROVED')\n"
    "else:\n"
    "    print('missing final content')\n"
    "    print('CHANGES_REQUESTED')\n"
)

_REVIEWER_PLAN_OK_ALWAYS_CHANGES_CHECKPOINT = (
    "import sys\n"
    "data = sys.stdin.read()\n"
    "if 'REVIEW_PATCH:' not in data:\n"
    "    print('APPROVED')\n"
    "else:\n"
    "    print('always needs work')\n"
    "    print('CHANGES_REQUESTED')\n"
)

_REVIEWER_PLAN_OK_ALWAYS_BLOCKED_CHECKPOINT = (
    "import sys\n"
    "data = sys.stdin.read()\n"
    "if 'REVIEW_PATCH:' not in data:\n"
    "    print('APPROVED')\n"
    "else:\n"
    "    print('BLOCKED')\n"
)

_REVIEWER_PLAN_OK_MALFORMED_CHECKPOINT = (
    "import sys\n"
    "data = sys.stdin.read()\n"
    "if 'REVIEW_PATCH:' not in data:\n"
    "    print('APPROVED')\n"
    "else:\n"
    "    print('sure, looks fine to me')\n"
)

_REVIEWER_PLAN_OK_CRASHES_ON_CHECKPOINT = (
    "import sys\n"
    "data = sys.stdin.read()\n"
    "if 'REVIEW_PATCH:' not in data:\n"
    "    print('APPROVED')\n"
    "else:\n"
    "    print('APPROVED')\n"
    "    raise SystemExit(3)\n"
)

_REVIEWER_PLAN_OK_TIMES_OUT_ON_CHECKPOINT = (
    "import sys, time\n"
    "data = sys.stdin.read()\n"
    "if 'REVIEW_PATCH:' not in data:\n"
    "    print('APPROVED')\n"
    "else:\n"
    "    time.sleep(5)\n"
    "    print('APPROVED')\n"
)

_REVIEWER_PLAN_OK_MUTATES_WORKTREE_ON_CHECKPOINT = (
    "import sys\n"
    "data = sys.stdin.read()\n"
    "if 'REVIEW_PATCH:' not in data:\n"
    "    print('APPROVED')\n"
    "else:\n"
    "    with open('sneaky.txt', 'w', encoding='utf-8') as f:\n"
    "        f.write('mutated by reviewer\\n')\n"
    "    print('APPROVED')\n"
)


def _recording_plan_implementer(log_path: Path) -> str:
    """Planning: appends the exact received stdin to ``log_path`` (outside
    the repo, so it never trips the strict planning fingerprint guard),
    then prints a harmless plan. Checkpoint: always writes 'done'."""

    log = log_path.as_posix()
    return (
        "import sys\n"
        "data = sys.stdin.read()\n"
        "if 'PLAN:' not in data:\n"
        f"    with open('{log}', 'a', encoding='utf-8') as f:\n"
        "        f.write(data)\n"
        "    print('PLAN: implement the thing')\n"
        "else:\n"
        "    with open('work_output.txt', 'w', encoding='utf-8') as f:\n"
        "        f.write('done\\n')\n"
        "    print('implemented')\n"
    )


def _recording_plan_reviewer(log_path: Path) -> str:
    """Plan review: appends the exact received stdin to ``log_path``
    (outside the repo), then approves. Checkpoint review: approves iff
    'done' is present."""

    log = log_path.as_posix()
    return (
        "import sys\n"
        "data = sys.stdin.read()\n"
        "if 'REVIEW_PATCH:' not in data:\n"
        f"    with open('{log}', 'a', encoding='utf-8') as f:\n"
        "        f.write(data)\n"
        "    print('APPROVED')\n"
        "elif 'done' in data:\n"
        "    print('APPROVED')\n"
        "else:\n"
        "    print('missing final content')\n"
        "    print('CHANGES_REQUESTED')\n"
    )


def _recording_dual_phase_implementer(plan_log: Path, checkpoint_log: Path) -> str:
    """Records the exact received stdin to a *different* log file per
    phase (planning vs. implementation checkpoint), so a test can inspect
    each phase's handoff content independently. Both logs live outside the
    repo, so recording never trips the fingerprint/branch-head guards."""

    plan_path = plan_log.as_posix()
    checkpoint_path = checkpoint_log.as_posix()
    return (
        "import sys\n"
        "data = sys.stdin.read()\n"
        "if 'PLAN:' not in data:\n"
        f"    with open('{plan_path}', 'a', encoding='utf-8') as f:\n"
        "        f.write(data)\n"
        "    print('PLAN: implement the thing')\n"
        "else:\n"
        f"    with open('{checkpoint_path}', 'a', encoding='utf-8') as f:\n"
        "        f.write(data)\n"
        "    with open('work_output.txt', 'w', encoding='utf-8') as f:\n"
        "        f.write('done\\n')\n"
        "    print('implemented')\n"
    )


def _recording_dual_phase_reviewer(plan_log: Path, checkpoint_log: Path) -> str:
    """Records the exact received stdin to a *different* log file per
    phase (plan review vs. checkpoint review)."""

    plan_path = plan_log.as_posix()
    checkpoint_path = checkpoint_log.as_posix()
    return (
        "import sys\n"
        "data = sys.stdin.read()\n"
        "if 'REVIEW_PATCH:' not in data:\n"
        f"    with open('{plan_path}', 'a', encoding='utf-8') as f:\n"
        "        f.write(data)\n"
        "    print('APPROVED')\n"
        "else:\n"
        f"    with open('{checkpoint_path}', 'a', encoding='utf-8') as f:\n"
        "        f.write(data)\n"
        "    if 'done' in data:\n"
        "        print('APPROVED')\n"
        "    else:\n"
        "        print('CHANGES_REQUESTED')\n"
    )


def _reviewer_changes_task_detail_on_origin_then_approves(seed: Path) -> str:
    """During plan review only: edits+commits+pushes a change to
    origin/main's docs/TASK.md that changes this task's own authoritative
    Roadmap target, then approves. Never reached for checkpoint review in
    the scenario this fixture is used for (the run is expected to block at
    delivery-branch-ready before getting there)."""

    seed_str = repr(str(seed))
    return (
        "import subprocess, sys\n"
        "data = sys.stdin.read()\n"
        "if 'REVIEW_PATCH:' not in data:\n"
        f"    seed = {seed_str}\n"
        "    target = seed + '/docs/TASK.md'\n"
        "    with open(target, 'r', encoding='utf-8') as f:\n"
        "        content = f.read()\n"
        "    content = content.replace('Test roadmap target', 'CHANGED roadmap target')\n"
        "    with open(target, 'w', encoding='utf-8') as f:\n"
        "        f.write(content)\n"
        "    subprocess.run(['git', 'add', 'docs/TASK.md'], cwd=seed, check=True)\n"
        "    subprocess.run(\n"
        "        ['git', 'commit', '-m', 'change roadmap target'], cwd=seed, check=True\n"
        "    )\n"
        "    subprocess.run(['git', 'push', 'origin', 'main'], cwd=seed, check=True)\n"
        "    print('APPROVED')\n"
        "else:\n"
        "    print('APPROVED')\n"
    )


def _reviewer_pushes_unrelated_origin_change_then_approves(seed: Path) -> str:
    """During plan review only: pushes an unrelated change (README.md) to
    origin/main, then approves. Also handles checkpoint review normally
    (approve iff 'done' present), since this fixture's scenario expects the
    run to continue all the way to an accepted checkpoint."""

    seed_str = repr(str(seed))
    return (
        "import subprocess, sys\n"
        "data = sys.stdin.read()\n"
        "if 'REVIEW_PATCH:' not in data:\n"
        f"    seed = {seed_str}\n"
        "    target = seed + '/README.md'\n"
        "    with open(target, 'a', encoding='utf-8') as f:\n"
        "        f.write('unrelated change\\n')\n"
        "    subprocess.run(['git', 'add', 'README.md'], cwd=seed, check=True)\n"
        "    subprocess.run(['git', 'commit', '-m', 'unrelated change'], cwd=seed, check=True)\n"
        "    subprocess.run(['git', 'push', 'origin', 'main'], cwd=seed, check=True)\n"
        "    print('APPROVED')\n"
        "elif 'done' in data:\n"
        "    print('APPROVED')\n"
        "else:\n"
        "    print('missing final content')\n"
        "    print('CHANGES_REQUESTED')\n"
    )


def _recording_reviewer_pid_and_stdin(pid_log: Path, stdin_log: Path) -> str:
    pid_path = pid_log.as_posix()
    stdin_path = stdin_log.as_posix()
    return (
        "import os, sys\n"
        "data = sys.stdin.read()\n"
        f"with open('{pid_path}', 'a', encoding='utf-8') as f:\n"
        "    f.write(str(os.getpid()) + '\\n')\n"
        f"with open('{stdin_path}', 'a', encoding='utf-8') as f:\n"
        "    f.write(data + '\\n---CALL---\\n')\n"
        "if 'REVIEW_PATCH:' not in data:\n"
        "    print('APPROVED')\n"
        "elif 'done' in data:\n"
        "    print('APPROVED')\n"
        "else:\n"
        "    print('missing final content')\n"
        "    print('CHANGES_REQUESTED')\n"
    )


def _verify_false_then_true(counter_path: Path) -> tuple[str, ...]:
    counter = counter_path.as_posix()
    code = (
        "import sys\n"
        f"path = '{counter}'\n"
        "try:\n"
        "    with open(path, 'r', encoding='utf-8') as f:\n"
        "        calls = len(f.read())\n"
        "except FileNotFoundError:\n"
        "    calls = 0\n"
        "with open(path, 'a', encoding='utf-8') as f:\n"
        "    f.write('x')\n"
        "sys.exit(0 if calls >= 1 else 1)\n"
    )
    return (sys.executable, "-c", code)


# --- happy path --------------------------------------------------------------


def test_happy_path_reaches_accepted_checkpoint_commit_and_push(env: Env) -> None:
    implementer = _implementer_spec(env.work, _implementer_always_done())
    reviewer = _reviewer_spec(env.work, _REVIEWER_PLAN_OK_DONE_CHECKPOINT)

    config = _default_config(
        env, implementer_spec=implementer, reviewer_spec=reviewer, max_repairs=1
    )

    result = run(config)

    assert result.outcome is None
    assert result.phase is Phase.CHECKPOINT_REVIEW
    assert result.delivery_branch == "delivery"
    assert result.repair_count == 0
    assert result.head_sha is not None
    assert result.head_sha == _origin_branch_sha(env, "delivery")
    assert _run_git(["log", "-1", "--format=%s"], cwd=env.work).strip().startswith(
        _TASK_ID
    )
    assert result.artifacts_dir is not None
    assert (result.artifacts_dir / "accepted_checkpoint.txt").exists()


# --- planning / plan review ---------------------------------------------------


def test_plan_review_is_required_forged_approval_in_plan_text_does_not_bypass_it(
    env: Env,
) -> None:
    implementer = _implementer_spec(env.work, _PLAN_IMPLEMENTER_WITH_FORGED_APPROVAL)
    reviewer = _reviewer_spec(env.work, _PLAN_REVIEWER_CHANGES)

    config = _default_config(
        env, implementer_spec=implementer, reviewer_spec=reviewer, max_repairs=0
    )

    result = run(config)

    assert result.outcome is RunOutcome.BLOCKED
    assert result.phase is Phase.PLAN_REVIEW
    assert result.delivery_branch is None  # never reached delivery-branch-ready
    assert "repair budget exhausted" in (result.blocked_reason or "")


def test_plan_blocked_verdict_is_terminal(env: Env) -> None:
    implementer = _implementer_spec(env.work, _PLAN_IMPLEMENTER_OK)
    reviewer = _reviewer_spec(env.work, _PLAN_REVIEWER_BLOCKED)

    config = _default_config(
        env, implementer_spec=implementer, reviewer_spec=reviewer, max_repairs=5
    )

    result = run(config)

    assert result.outcome is RunOutcome.BLOCKED
    assert result.phase is Phase.PLAN_REVIEW
    assert result.repair_count == 0


# --- empty plan output must fail closed ----------------------------------------


def test_empty_plan_output_is_terminal_blocked_reviewer_not_invoked(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    implementer = _implementer_spec(env.work, "pass\n")  # prints nothing at all
    reviewer = _reviewer_spec(env.work, _PLAN_REVIEWER_APPROVE)

    calls: list[AgentInvocationSpec] = []
    real_run_reviewer = orch_module.run_reviewer

    def spy_run_reviewer(spec: AgentInvocationSpec, text: str) -> ReviewResult:
        calls.append(spec)
        return real_run_reviewer(spec, text)

    monkeypatch.setattr(orch_module, "run_reviewer", spy_run_reviewer)

    config = _default_config(
        env, implementer_spec=implementer, reviewer_spec=reviewer, max_repairs=1
    )

    result = run(config)

    assert result.outcome is RunOutcome.BLOCKED
    assert result.phase is Phase.PLANNING
    assert "empty" in (result.blocked_reason or "").lower()
    assert calls == []  # the designated reviewer was never invoked


def test_whitespace_only_plan_output_is_terminal_blocked_reviewer_not_invoked(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    implementer = _implementer_spec(env.work, "print('   \\n\\t  \\n')\n")
    reviewer = _reviewer_spec(env.work, _PLAN_REVIEWER_APPROVE)

    calls: list[AgentInvocationSpec] = []
    real_run_reviewer = orch_module.run_reviewer

    def spy_run_reviewer(spec: AgentInvocationSpec, text: str) -> ReviewResult:
        calls.append(spec)
        return real_run_reviewer(spec, text)

    monkeypatch.setattr(orch_module, "run_reviewer", spy_run_reviewer)

    config = _default_config(
        env, implementer_spec=implementer, reviewer_spec=reviewer, max_repairs=1
    )

    result = run(config)

    assert result.outcome is RunOutcome.BLOCKED
    assert result.phase is Phase.PLANNING
    assert calls == []


def test_normal_non_empty_plan_is_unaffected_by_the_empty_plan_guard(env: Env) -> None:
    implementer = _implementer_spec(env.work, _implementer_always_done())
    reviewer = _reviewer_spec(env.work, _REVIEWER_PLAN_OK_DONE_CHECKPOINT)

    config = _default_config(
        env, implementer_spec=implementer, reviewer_spec=reviewer, max_repairs=1
    )

    result = run(config)

    assert result.outcome is None


# --- origin/main revalidation (item 1) -----------------------------------------


def test_stale_local_task_md_cannot_override_origin_main(env: Env) -> None:
    """A clean, committed local docs/TASK.md that diverges from origin/main
    must never be trusted -- preflight must revalidate against a freshly
    fetched origin/main, not the local worktree."""

    stale_text = _task_md_text("TSK-9099")
    (env.work / "docs" / "TASK.md").write_text(stale_text, encoding="utf-8")
    _run_git(["add", "docs/TASK.md"], cwd=env.work)
    _run_git(["commit", "-q", "-m", "stale local divergence"], cwd=env.work)

    implementer = _implementer_spec(env.work, _implementer_always_done())
    reviewer = _reviewer_spec(env.work, _REVIEWER_PLAN_OK_DONE_CHECKPOINT)

    config = _default_config(
        env, implementer_spec=implementer, reviewer_spec=reviewer, max_repairs=1
    )

    result = run(config)

    assert result.outcome is None
    assert result.artifacts_dir is not None
    task_context_text = (result.artifacts_dir / "task_context.txt").read_text(
        encoding="utf-8"
    )
    assert "Test roadmap target" in task_context_text
    assert "TSK-9099" not in task_context_text


def test_different_local_branch_cannot_override_origin_main(env: Env) -> None:
    """Revalidation must not depend on which branch happens to be checked
    out locally -- even one with no docs/TASK.md at all."""

    _run_git(["checkout", "-q", "-b", "unrelated-local-branch"], cwd=env.work)
    (env.work / "docs" / "TASK.md").unlink()
    _run_git(["add", "-A"], cwd=env.work)
    _run_git(["commit", "-q", "-m", "remove docs/TASK.md on this branch"], cwd=env.work)

    implementer = _implementer_spec(env.work, _implementer_always_done())
    reviewer = _reviewer_spec(env.work, _REVIEWER_PLAN_OK_DONE_CHECKPOINT)

    config = _default_config(
        env, implementer_spec=implementer, reviewer_spec=reviewer, max_repairs=1
    )

    result = run(config)

    assert result.outcome is None
    assert result.artifacts_dir is not None
    task_context_text = (result.artifacts_dir / "task_context.txt").read_text(
        encoding="utf-8"
    )
    assert "Test roadmap target" in task_context_text


def test_origin_main_movement_with_changed_task_detail_blocks_execution(
    env: Env,
) -> None:
    implementer = _implementer_spec(env.work, _implementer_always_done())
    reviewer = _reviewer_spec(
        env.work, _reviewer_changes_task_detail_on_origin_then_approves(env.seed)
    )

    config = _default_config(
        env, implementer_spec=implementer, reviewer_spec=reviewer, max_repairs=0
    )

    result = run(config)

    assert result.outcome is RunOutcome.BLOCKED
    assert result.phase is Phase.DELIVERY_BRANCH_READY
    assert result.delivery_branch is None  # branch was never created
    reason = result.blocked_reason or ""
    assert "origin/main moved" in reason
    assert "authoritative task context changed" in reason


def test_unrelated_origin_main_movement_with_unchanged_task_detail_may_continue(
    env: Env,
) -> None:
    implementer = _implementer_spec(env.work, _implementer_always_done())
    reviewer = _reviewer_spec(
        env.work, _reviewer_pushes_unrelated_origin_change_then_approves(env.seed)
    )

    config = _default_config(
        env, implementer_spec=implementer, reviewer_spec=reviewer, max_repairs=0
    )

    result = run(config)

    assert result.outcome is None
    assert result.phase is Phase.CHECKPOINT_REVIEW
    assert result.artifacts_dir is not None
    assert (result.artifacts_dir / "origin_main_revalidation.txt").exists()


def test_delivery_branch_anchored_to_exact_validated_sha_immune_to_late_fetch_race(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression for the fetch race between origin/main revalidation and
    delivery-branch creation. Under the old two-fetch design,
    create_delivery_branch_from_origin_main performed its own internal
    fetch and resolved the mutable origin/main ref itself, so origin/main
    advancing again between the revalidation fetch and that second fetch
    could hand the branch a base commit that was never revalidated. The
    fixed design performs exactly one fetch for this decision
    (repository.fetch_and_capture_origin_main_sha, inside
    _revalidate_against_fresh_origin_main) and creates the branch from
    that exact captured SHA (repository.create_delivery_branch_from_sha,
    which never fetches or re-resolves origin/main itself) -- so a late,
    out-of-band origin/main advance immediately before branch creation must
    never change the base the branch actually gets. This test would have
    failed under the old double-fetch ordering: it advances origin/main
    exactly at the branch-creation boundary."""

    implementer = _implementer_spec(env.work, _implementer_always_done())
    reviewer = _reviewer_spec(env.work, _REVIEWER_PLAN_OK_DONE_CHECKPOINT)

    config = _default_config(
        env, implementer_spec=implementer, reviewer_spec=reviewer, max_repairs=1
    )

    real_create = orch_module.repository.create_delivery_branch_from_sha
    captured: dict[str, str] = {}

    def spy_create(repo: Path, branch: str, base_sha: str) -> None:
        captured["validated_sha"] = base_sha
        # Simulate origin/main advancing again exactly at the
        # branch-creation boundary: AFTER the orchestrator already fetched
        # and positively revalidated base_sha, but immediately before the
        # branch is actually created from it.
        (env.seed / "README.md").write_text(
            "late unvalidated origin move\n", encoding="utf-8"
        )
        _run_git(["add", "README.md"], cwd=env.seed)
        _run_git(["commit", "-q", "-m", "late unvalidated origin move"], cwd=env.seed)
        _run_git(["push", "-q", "origin", "main"], cwd=env.seed)
        real_create(repo, branch, base_sha)
        captured["branch_head_immediately_after_creation"] = _run_git(
            ["rev-parse", branch], cwd=repo
        ).strip()

    monkeypatch.setattr(
        orch_module.repository, "create_delivery_branch_from_sha", spy_create
    )

    result = run(config)

    assert result.outcome is None
    assert (
        captured["branch_head_immediately_after_creation"]
        == captured["validated_sha"]
    )

    # Confirm origin/main really did move past what the branch used -- this
    # is what makes the assertion above meaningful, not a tautology.
    _run_git(["fetch", "origin"], cwd=env.work)
    current_origin_main = _run_git(["rev-parse", "origin/main"], cwd=env.work).strip()
    assert current_origin_main != captured["validated_sha"]


# --- full task-detail handoff (item 2) -----------------------------------------


def test_full_task_detail_reaches_context_artifact_and_plan_prompts(env: Env) -> None:
    plan_implementer_log = env.scratch / "plan_implementer_stdin.txt"
    plan_reviewer_log = env.scratch / "plan_reviewer_stdin.txt"
    implementer = _implementer_spec(
        env.work, _recording_plan_implementer(plan_implementer_log)
    )
    reviewer = _reviewer_spec(env.work, _recording_plan_reviewer(plan_reviewer_log))

    config = _default_config(
        env, implementer_spec=implementer, reviewer_spec=reviewer, max_repairs=1
    )

    result = run(config)

    assert result.outcome is None
    assert result.artifacts_dir is not None
    task_context_text = (result.artifacts_dir / "task_context.txt").read_text(
        encoding="utf-8"
    )
    plan_implementer_text = plan_implementer_log.read_text(encoding="utf-8")
    plan_reviewer_text = plan_reviewer_log.read_text(encoding="utf-8")

    markers = (
        _GOAL_MARKER,
        _SCOPE_MARKER,
        _OUT_OF_SCOPE_MARKER,
        _ACCEPTANCE_MARKER,
        _VERIFICATION_MARKER,
    )
    for marker in markers:
        assert marker in task_context_text, f"{marker} missing from task_context.txt"
        assert marker in plan_implementer_text, f"{marker} missing from plan implementer input"
        assert marker in plan_reviewer_text, f"{marker} missing from plan reviewer input"


def test_full_task_detail_and_repository_context_reach_checkpoint_handoffs(
    env: Env,
) -> None:
    """Full authoritative task detail must not disappear after planning:
    the implementation-checkpoint implementer prompt and the checkpoint-
    review reviewer input must both carry it, plus explicit repository
    context (delivery branch, base SHA, HEAD)."""

    plan_impl_log = env.scratch / "plan_impl.txt"
    checkpoint_impl_log = env.scratch / "checkpoint_impl.txt"
    plan_rev_log = env.scratch / "plan_rev.txt"
    checkpoint_rev_log = env.scratch / "checkpoint_rev.txt"

    implementer = _implementer_spec(
        env.work, _recording_dual_phase_implementer(plan_impl_log, checkpoint_impl_log)
    )
    reviewer = _reviewer_spec(
        env.work, _recording_dual_phase_reviewer(plan_rev_log, checkpoint_rev_log)
    )

    config = _default_config(
        env, implementer_spec=implementer, reviewer_spec=reviewer, max_repairs=1
    )

    result = run(config)

    assert result.outcome is None
    assert result.artifacts_dir is not None
    repository_context_text = (
        result.artifacts_dir / "repository_context.txt"
    ).read_text(encoding="utf-8")
    base_sha_line = next(
        line for line in repository_context_text.splitlines() if line.startswith("base_sha:")
    )
    branch_line = next(
        line
        for line in repository_context_text.splitlines()
        if line.startswith("delivery_branch:")
    )

    checkpoint_impl_text = checkpoint_impl_log.read_text(encoding="utf-8")
    checkpoint_rev_text = checkpoint_rev_log.read_text(encoding="utf-8")

    markers = (
        _GOAL_MARKER,
        _SCOPE_MARKER,
        _OUT_OF_SCOPE_MARKER,
        _ACCEPTANCE_MARKER,
        _VERIFICATION_MARKER,
    )
    for marker in markers:
        assert marker in checkpoint_impl_text, f"{marker} missing from checkpoint implementer input"
        assert marker in checkpoint_rev_text, f"{marker} missing from checkpoint reviewer input"

    assert "ACCEPTED_PLAN:" in checkpoint_impl_text
    assert "ACCEPTED_PLAN:" in checkpoint_rev_text
    assert branch_line in checkpoint_impl_text
    assert branch_line in checkpoint_rev_text
    assert base_sha_line in checkpoint_impl_text
    assert base_sha_line in checkpoint_rev_text
    assert "head_sha:" in checkpoint_impl_text
    assert "head_sha:" in checkpoint_rev_text


# --- planning must not mutate repository state (item 3) -----------------------


def test_planning_implementer_worktree_mutation_is_terminal_before_plan_review(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    implementer = _implementer_spec(env.work, _IMPLEMENTER_MUTATES_WORKTREE_DURING_PLANNING)
    reviewer = _reviewer_spec(env.work, _REVIEWER_PLAN_OK_DONE_CHECKPOINT)

    calls: list[AgentInvocationSpec] = []
    real_run_reviewer = orch_module.run_reviewer

    def spy_run_reviewer(spec: AgentInvocationSpec, text: str) -> ReviewResult:
        calls.append(spec)
        return real_run_reviewer(spec, text)

    monkeypatch.setattr(orch_module, "run_reviewer", spy_run_reviewer)

    config = _default_config(
        env, implementer_spec=implementer, reviewer_spec=reviewer, max_repairs=1
    )

    result = run(config)

    assert result.outcome is RunOutcome.BLOCKED
    assert result.phase is Phase.PLANNING
    assert "changed unexpectedly" in (result.blocked_reason or "")
    assert calls == []  # the designated reviewer was never invoked


# --- deterministic verification configuration (item 4) ------------------------


def _minimal_specs(work: Path) -> tuple[AgentInvocationSpec, AgentInvocationSpec]:
    return (
        _implementer_spec(work, "pass\n"),
        _reviewer_spec(work, "pass\n"),
    )


def test_config_rejects_empty_verification_commands(env: Env) -> None:
    implementer, reviewer = _minimal_specs(env.work)

    with pytest.raises(ValueError):
        OrchestratorConfig(
            task_id=_TASK_ID,
            repo=env.work,
            implementer_spec=implementer,
            reviewer_spec=reviewer,
            verification_commands=(),
            delivery_branch="delivery",
        )


def test_config_rejects_empty_individual_verification_command(env: Env) -> None:
    implementer, reviewer = _minimal_specs(env.work)

    with pytest.raises(ValueError):
        OrchestratorConfig(
            task_id=_TASK_ID,
            repo=env.work,
            implementer_spec=implementer,
            reviewer_spec=reviewer,
            verification_commands=((),),
            delivery_branch="delivery",
        )


def test_config_rejects_non_positive_verification_timeout(env: Env) -> None:
    implementer, reviewer = _minimal_specs(env.work)

    with pytest.raises(ValueError):
        OrchestratorConfig(
            task_id=_TASK_ID,
            repo=env.work,
            implementer_spec=implementer,
            reviewer_spec=reviewer,
            verification_commands=(_verify_true(),),
            delivery_branch="delivery",
            verification_timeout_seconds=0,
        )


def test_real_successful_verification_command_passes(env: Env) -> None:
    implementer = _implementer_spec(env.work, _implementer_always_done())
    reviewer = _reviewer_spec(env.work, _REVIEWER_PLAN_OK_DONE_CHECKPOINT)

    config = _default_config(
        env,
        implementer_spec=implementer,
        reviewer_spec=reviewer,
        max_repairs=0,
        verification_commands=(_verify_true(),),
    )

    result = run(config)

    assert result.outcome is None


# --- external-agent capability preconditions ------------------------------------


def test_config_rejects_reviewer_without_fresh_context_capability_declared(
    env: Env,
) -> None:
    implementer = _implementer_spec(env.work, "pass\n")
    reviewer = AgentInvocationSpec(
        role=AgentRole.REVIEWER,
        executable=sys.executable,
        args=("-c", "pass"),
        cwd=env.work,
        fresh_context_capable=False,
        has_git_or_github_write_access=False,
    )

    with pytest.raises(ValueError, match="fresh_context_capable"):
        OrchestratorConfig(
            task_id=_TASK_ID,
            repo=env.work,
            implementer_spec=implementer,
            reviewer_spec=reviewer,
            verification_commands=(_verify_true(),),
            delivery_branch="delivery",
        )


def test_config_rejects_reviewer_with_git_or_github_write_access_true(
    env: Env,
) -> None:
    implementer = _implementer_spec(env.work, "pass\n")
    reviewer = AgentInvocationSpec(
        role=AgentRole.REVIEWER,
        executable=sys.executable,
        args=("-c", "pass"),
        cwd=env.work,
        fresh_context_capable=True,
        has_git_or_github_write_access=True,
    )

    with pytest.raises(ValueError, match="has_git_or_github_write_access"):
        OrchestratorConfig(
            task_id=_TASK_ID,
            repo=env.work,
            implementer_spec=implementer,
            reviewer_spec=reviewer,
            verification_commands=(_verify_true(),),
            delivery_branch="delivery",
        )


def test_config_rejects_reviewer_with_git_or_github_write_access_undeclared(
    env: Env,
) -> None:
    """An unset (``None``) ``has_git_or_github_write_access`` must never be
    treated as an implicit safe default -- it is refused exactly like
    ``True``, since nobody positively asserted the reviewer command has no
    direct Git/GitHub write capability."""

    implementer = _implementer_spec(env.work, "pass\n")
    reviewer = AgentInvocationSpec(
        role=AgentRole.REVIEWER,
        executable=sys.executable,
        args=("-c", "pass"),
        cwd=env.work,
        fresh_context_capable=True,
        # has_git_or_github_write_access left undeclared (None).
    )

    with pytest.raises(ValueError, match="has_git_or_github_write_access"):
        OrchestratorConfig(
            task_id=_TASK_ID,
            repo=env.work,
            implementer_spec=implementer,
            reviewer_spec=reviewer,
            verification_commands=(_verify_true(),),
            delivery_branch="delivery",
        )


def test_config_rejects_implementer_with_git_or_github_write_access_true(
    env: Env,
) -> None:
    implementer = AgentInvocationSpec(
        role=AgentRole.IMPLEMENTER,
        executable=sys.executable,
        args=("-c", "pass"),
        cwd=env.work,
        can_edit_working_files=True,
        has_git_or_github_write_access=True,
    )
    reviewer = _reviewer_spec(env.work, "pass\n")

    with pytest.raises(ValueError, match="has_git_or_github_write_access"):
        OrchestratorConfig(
            task_id=_TASK_ID,
            repo=env.work,
            implementer_spec=implementer,
            reviewer_spec=reviewer,
            verification_commands=(_verify_true(),),
            delivery_branch="delivery",
        )


def test_config_rejects_implementer_with_git_or_github_write_access_undeclared(
    env: Env,
) -> None:
    """An unset (``None``) ``has_git_or_github_write_access`` must never be
    treated as an implicit safe default -- it is refused exactly like
    ``True``, since nobody positively asserted the implementer command has
    no direct Git/GitHub write capability. This matters in practice: a
    real implementer command typically inherits the host environment/PATH,
    and this module cannot mechanically confirm it is actually sandboxed
    away from ``git push``/``gh``/GitHub credentials."""

    implementer = AgentInvocationSpec(
        role=AgentRole.IMPLEMENTER,
        executable=sys.executable,
        args=("-c", "pass"),
        cwd=env.work,
        can_edit_working_files=True,
        # has_git_or_github_write_access left undeclared (None).
    )
    reviewer = _reviewer_spec(env.work, "pass\n")

    with pytest.raises(ValueError, match="has_git_or_github_write_access"):
        OrchestratorConfig(
            task_id=_TASK_ID,
            repo=env.work,
            implementer_spec=implementer,
            reviewer_spec=reviewer,
            verification_commands=(_verify_true(),),
            delivery_branch="delivery",
        )


def test_config_rejects_implementer_without_edit_capability_declared(env: Env) -> None:
    implementer = AgentInvocationSpec(
        role=AgentRole.IMPLEMENTER,
        executable=sys.executable,
        args=("-c", "pass"),
        cwd=env.work,
        can_edit_working_files=False,
        has_git_or_github_write_access=False,
    )
    reviewer = _reviewer_spec(env.work, "pass\n")

    with pytest.raises(ValueError, match="can_edit_working_files"):
        OrchestratorConfig(
            task_id=_TASK_ID,
            repo=env.work,
            implementer_spec=implementer,
            reviewer_spec=reviewer,
            verification_commands=(_verify_true(),),
            delivery_branch="delivery",
        )


def test_config_accepts_valid_narrow_capability_declarations(env: Env) -> None:
    """Valid, narrowly-declared capabilities (the ``_implementer_spec``/
    ``_reviewer_spec`` helper defaults used throughout this file) allow the
    existing flow through to an accepted checkpoint."""

    implementer = _implementer_spec(env.work, _implementer_always_done())
    reviewer = _reviewer_spec(env.work, _REVIEWER_PLAN_OK_DONE_CHECKPOINT)

    config = _default_config(
        env, implementer_spec=implementer, reviewer_spec=reviewer, max_repairs=1
    )

    result = run(config)

    assert result.outcome is None


def test_capability_fields_are_never_named_or_treated_as_authorization() -> None:
    """These capability fields are an external-process configuration
    precondition, never AUTONOMOUS_PR authorization
    (``AGENTS.md`` "Valid invocation") -- mirrors the same guarantee
    ``TaskContext``/``revalidate_current_task`` already make for the task
    id (``test_task_context.py::test_task_id_never_acts_as_authorization_proof``)."""

    field_names = {f.name for f in dataclasses.fields(AgentInvocationSpec)}
    assert not any("author" in name.lower() for name in field_names)


# --- checkpoint bounded repair -------------------------------------------------


def test_changes_requested_causes_repair_verification_rerun_and_re_review(
    env: Env,
) -> None:
    impl_counter = env.scratch / "impl_calls.txt"
    implementer = _implementer_spec(env.work, _implementer_wip_then_done(impl_counter))
    reviewer = _reviewer_spec(env.work, _REVIEWER_PLAN_OK_DONE_CHECKPOINT)

    config = _default_config(
        env,
        implementer_spec=implementer,
        reviewer_spec=reviewer,
        max_repairs=1,
        verification_commands=(_verify_true(),),
    )

    result = run(config)

    assert result.outcome is None
    assert result.repair_count == 1
    # one planning call plus two checkpoint attempts
    assert impl_counter.read_text(encoding="utf-8") == "xxx"
    assert result.artifacts_dir is not None
    assert (result.artifacts_dir / "verification_attempt_0.txt").exists()
    assert (result.artifacts_dir / "verification_attempt_1.txt").exists()
    assert (result.artifacts_dir / "checkpoint_review_attempt_0.txt").exists()
    assert (result.artifacts_dir / "checkpoint_review_attempt_1.txt").exists()


def test_verification_failure_triggers_repair_before_any_review(env: Env) -> None:
    verify_counter = env.scratch / "verify_calls.txt"
    implementer = _implementer_spec(env.work, _implementer_always_done())
    reviewer = _reviewer_spec(env.work, _REVIEWER_PLAN_OK_DONE_CHECKPOINT)

    config = _default_config(
        env,
        implementer_spec=implementer,
        reviewer_spec=reviewer,
        max_repairs=1,
        verification_commands=(_verify_false_then_true(verify_counter),),
    )

    result = run(config)

    assert result.outcome is None
    assert result.repair_count == 1


def test_repair_budget_exhaustion_is_blocked(env: Env) -> None:
    implementer = _implementer_spec(env.work, _implementer_always_done())
    reviewer = _reviewer_spec(env.work, _REVIEWER_PLAN_OK_ALWAYS_CHANGES_CHECKPOINT)

    config = _default_config(
        env, implementer_spec=implementer, reviewer_spec=reviewer, max_repairs=1
    )
    initial_head = _run_git(["rev-parse", "HEAD"], cwd=env.work).strip()

    result = run(config)

    assert result.outcome is RunOutcome.BLOCKED
    assert result.phase is Phase.CHECKPOINT_REVIEW
    assert result.repair_count == 1
    assert "repair budget exhausted" in (result.blocked_reason or "")
    assert result.head_sha == initial_head


# --- terminal-without-repair reviewer outcomes --------------------------------


@pytest.mark.parametrize(
    "reviewer_code",
    [
        _REVIEWER_PLAN_OK_ALWAYS_BLOCKED_CHECKPOINT,
        _REVIEWER_PLAN_OK_MALFORMED_CHECKPOINT,
        _REVIEWER_PLAN_OK_CRASHES_ON_CHECKPOINT,
    ],
)
def test_blocked_malformed_and_crashed_reviewer_are_terminal_without_repair(
    env: Env, reviewer_code: str
) -> None:
    impl_counter = env.scratch / "impl_calls.txt"
    implementer = _implementer_spec(env.work, _implementer_wip_then_done(impl_counter))
    reviewer = _reviewer_spec(env.work, reviewer_code)

    config = _default_config(
        env, implementer_spec=implementer, reviewer_spec=reviewer, max_repairs=5
    )

    result = run(config)

    assert result.outcome is RunOutcome.BLOCKED
    assert result.repair_count == 0
    # one planning call plus exactly one checkpoint attempt -- never
    # re-invoked for a repair that must never happen.
    assert impl_counter.read_text(encoding="utf-8") == "xx"


def test_reviewer_timeout_is_terminal_without_repair(env: Env) -> None:
    implementer = _implementer_spec(env.work, _implementer_always_done())
    reviewer = _reviewer_spec(
        env.work, _REVIEWER_PLAN_OK_TIMES_OUT_ON_CHECKPOINT, timeout=0.2
    )

    config = _default_config(
        env, implementer_spec=implementer, reviewer_spec=reviewer, max_repairs=5
    )

    result = run(config)

    assert result.outcome is RunOutcome.BLOCKED
    assert result.repair_count == 0


# --- repository invariant violations -------------------------------------------


def test_implementer_branch_or_head_mutation_during_checkpoint_is_terminal(
    env: Env,
) -> None:
    implementer = _implementer_spec(
        env.work, _IMPLEMENTER_MUTATES_BRANCH_HEAD_DURING_CHECKPOINT_ONLY
    )
    reviewer = _reviewer_spec(env.work, _REVIEWER_PLAN_OK_DONE_CHECKPOINT)

    config = _default_config(
        env, implementer_spec=implementer, reviewer_spec=reviewer, max_repairs=1
    )

    result = run(config)

    assert result.outcome is RunOutcome.BLOCKED
    assert result.phase is Phase.IMPLEMENTATION_CHECKPOINT
    assert "branch/HEAD changed" in (result.blocked_reason or "")


def test_reviewer_worktree_mutation_is_terminal(env: Env) -> None:
    implementer = _implementer_spec(env.work, _implementer_always_done())
    reviewer = _reviewer_spec(env.work, _REVIEWER_PLAN_OK_MUTATES_WORKTREE_ON_CHECKPOINT)

    config = _default_config(
        env, implementer_spec=implementer, reviewer_spec=reviewer, max_repairs=1
    )

    result = run(config)

    assert result.outcome is RunOutcome.BLOCKED
    assert result.phase is Phase.CHECKPOINT_REVIEW
    assert "changed unexpectedly" in (result.blocked_reason or "")


# --- committed HEAD recorded before push (item 5) ------------------------------


def test_push_failure_reports_actual_committed_head_and_does_not_retry(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    implementer = _implementer_spec(env.work, _implementer_always_done())
    reviewer = _reviewer_spec(env.work, _REVIEWER_PLAN_OK_DONE_CHECKPOINT)

    config = _default_config(
        env, implementer_spec=implementer, reviewer_spec=reviewer, max_repairs=1
    )
    initial_head = _run_git(["rev-parse", "HEAD"], cwd=env.work).strip()

    push_calls: list[tuple[str, str]] = []

    def fake_push(repo: Path, *, branch: str, expected_branch: str) -> None:
        push_calls.append((branch, expected_branch))
        raise orch_module.repository.RepositoryError("simulated push failure")

    monkeypatch.setattr(orch_module.repository, "push_delivery_branch", fake_push)

    result = run(config)

    assert result.outcome is RunOutcome.BLOCKED
    assert len(push_calls) == 1  # no retry

    new_local_head = _run_git(["rev-parse", "delivery"], cwd=env.work).strip()
    assert new_local_head != initial_head  # the commit actually landed locally
    assert result.head_sha == new_local_head  # not the pre-commit SHA
    assert "simulated push failure" in (result.blocked_reason or "")


# --- no implicit resume ---------------------------------------------------------


def test_lost_run_state_never_resumes_implicitly_across_separate_run_calls(
    env: Env,
) -> None:
    impl_counter = env.scratch / "impl_calls.txt"
    implementer = _implementer_spec(env.work, _implementer_wip_then_done(impl_counter))
    reviewer = _reviewer_spec(env.work, _REVIEWER_PLAN_OK_DONE_CHECKPOINT)

    config = _default_config(
        env, implementer_spec=implementer, reviewer_spec=reviewer, max_repairs=1
    )

    first = run(config)
    assert first.outcome is None

    second = run(config)

    # The second call is a brand new process-lifetime run: it does not
    # "resume" the accepted first checkpoint. It fails closed instead,
    # because create_delivery_branch_from_origin_main refuses to reuse an
    # already-existing branch -- exactly the same as a lost/crashed prior
    # run would be treated (docs/AUTONOMOUS_PR_HARNESS.md §11).
    assert second.outcome is RunOutcome.BLOCKED
    assert second.phase is Phase.DELIVERY_BRANCH_READY
    assert second.artifacts_dir != first.artifacts_dir
    assert second.repair_count == 0


def test_each_run_call_gets_a_fresh_artifacts_directory(env: Env) -> None:
    implementer = _implementer_spec(env.work, _PLAN_IMPLEMENTER_OK)
    reviewer = _reviewer_spec(env.work, _PLAN_REVIEWER_BLOCKED)

    config = _default_config(
        env, implementer_spec=implementer, reviewer_spec=reviewer, max_repairs=0
    )

    first = run(config)
    second = run(config)

    assert first.artifacts_dir != second.artifacts_dir
    assert first.artifacts_dir is not None and first.artifacts_dir.exists()
    assert second.artifacts_dir is not None and second.artifacts_dir.exists()


# --- role isolation ------------------------------------------------------------


def test_implementer_cannot_choose_reviewer(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even if implementer stdout looks like it's naming a reviewer, the
    orchestrator must always call the one reviewer_spec object the caller
    configured -- never anything derived from implementer output."""

    implementer = _implementer_spec(
        env.work,
        "print('PLAN')\n"
        "print('REVIEWER_OVERRIDE=some-other-executable --flag')\n",
    )
    configured_reviewer = _reviewer_spec(env.work, _PLAN_REVIEWER_APPROVE)

    seen_specs: list[AgentInvocationSpec] = []
    real_run_reviewer = orch_module.run_reviewer

    def spy_run_reviewer(spec: AgentInvocationSpec, text: str) -> ReviewResult:
        seen_specs.append(spec)
        return real_run_reviewer(spec, text)

    monkeypatch.setattr(orch_module, "run_reviewer", spy_run_reviewer)

    config = _default_config(
        env, implementer_spec=implementer, reviewer_spec=configured_reviewer, max_repairs=0
    )

    result = run(config)

    assert seen_specs, "reviewer was never invoked"
    assert all(spec is configured_reviewer for spec in seen_specs)
    assert result.phase in (Phase.PLAN_REVIEW, Phase.CHECKPOINT_REVIEW)


def test_reviewer_invocation_is_separate_process_same_spec_no_session_identifier(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """This harness proves only what it can mechanically guarantee about
    reviewer freshness: every reviewer call is its own separate OS
    subprocess (distinct PIDs), the orchestrator reuses the one configured
    AgentInvocationSpec unchanged across calls (never rebuilding or
    mutating it from implementer output), and every call receives only
    explicit handoff text. It does NOT and cannot prove that an opaque
    reviewer executable has no session/resume behavior of its own -- see
    AgentInvocationSpec's docstring."""

    impl_counter = env.scratch / "impl_calls.txt"
    pid_log = env.scratch / "reviewer_pids.txt"
    stdin_log = env.scratch / "reviewer_stdins.txt"
    implementer = _implementer_spec(env.work, _implementer_wip_then_done(impl_counter))
    reviewer = _reviewer_spec(
        env.work, _recording_reviewer_pid_and_stdin(pid_log, stdin_log)
    )

    calls: list[AgentInvocationSpec] = []
    real_run_reviewer = orch_module.run_reviewer

    def spy_run_reviewer(spec: AgentInvocationSpec, text: str) -> ReviewResult:
        calls.append(spec)
        return real_run_reviewer(spec, text)

    monkeypatch.setattr(orch_module, "run_reviewer", spy_run_reviewer)

    config = _default_config(
        env, implementer_spec=implementer, reviewer_spec=reviewer, max_repairs=1
    )

    result = run(config)

    assert result.outcome is None
    assert len(calls) >= 2
    # the orchestrator never rebuilds/mutates the configured reviewer spec
    assert all(spec is reviewer for spec in calls)

    pids = [line.strip() for line in pid_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(pids) == len(calls)
    assert len(set(pids)) == len(pids)  # every call was a genuinely separate OS process

    stdin_text = stdin_log.read_text(encoding="utf-8")
    assert "TASK_ID" in stdin_text  # explicit handoff content, not a hidden reference
