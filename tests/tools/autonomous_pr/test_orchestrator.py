import dataclasses
import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from tools.autonomous_pr import orchestrator as orch_module
from tools.autonomous_pr import repository
from tools.autonomous_pr import task_context
from tools.autonomous_pr.agents import (
    AgentInvocationResult,
    AgentInvocationSpec,
    AgentProfileConfig,
)
from tools.autonomous_pr.model import (
    AgentRole,
    AgentWorkKind,
    ApprovedTaskDocument,
    CandidateIdentity,
    CandidateRejectionBasis,
    ComputeProfile,
    ExecutionCheckpoint,
    ExecutionApproval,
    ExecutionTarget,
    GateAttempt,
    GateContext,
    GateHistory,
    NonConvergenceDiagnosis,
    NoEligibleTask,
    Phase,
    RepairFinding,
    RepairPacket,
    ReviewVerdict,
    RunOutcome,
    RunResult,
    RoutingDecision,
    SelectedTask,
    StructuredReviewResult,
    TaskExecutionSpec,
    TaskMetadata,
    TaskSelectionMode,
    TaskStatus,
    TerminalTask,
    TrackerTask,
    VerificationCommandResult,
    VerificationEvidence,
)
from tools.autonomous_pr.orchestrator import (
    OrchestratorConfig,
    execute_v2_checkpoints,
    run,
)

_TASK_ID = "TSK-9001"

_GOAL_MARKER = "GOAL_MARKER_TEXT"
_SCOPE_MARKER = "SCOPE_MARKER_TEXT"
_OUT_OF_SCOPE_MARKER = "OUT_OF_SCOPE_MARKER_TEXT"
_ACCEPTANCE_MARKER = "ACCEPTANCE_CRITERIA_MARKER_TEXT"
_VERIFICATION_MARKER = "VERIFICATION_MARKER_TEXT"


def _profiles(spec: AgentInvocationSpec) -> AgentProfileConfig:
    if spec.role is AgentRole.IMPLEMENTER:
        profile_args = {
            ComputeProfile.ROUTINE: ("routine",),
            ComputeProfile.DELIBERATE: ("deliberate",),
            ComputeProfile.CRITICAL: ("critical",),
        }
    else:
        profile_args = {
            ComputeProfile.DELIBERATE: ("deliberate",),
            ComputeProfile.CRITICAL: ("critical",),
        }
    return AgentProfileConfig(spec=spec, profile_args=profile_args)


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
        "# Terminal task index\n"
        "\n"
        "| ID | Status | Evidence | Title |\n"
        "| --- | --- | --- | --- |\n"
        "| `TSK-9000` | `Done` | PR #7 | Existing prerequisite |\n"
        "\n"
        "---\n"
        "\n"
        "# Recently completed\n"
        "\n"
        "| ID | Title |\n"
        "| --- | --- |\n"
    )


def _v2_task_md_text(
    task_id: str,
    *,
    terminal_rows: tuple[tuple[str, str], ...] = (),
) -> str:
    terminal = "".join(
        f"| `{terminal_id}` | `{status}` | PR #1 | Terminal task |\n"
        for terminal_id, status in terminal_rows
    )
    return (
        "# Task tracker\n\n"
        "Standalone files own open task metadata and selection.\n\n"
        "# Terminal task index\n\n"
        "| ID | Status | Evidence | Title |\n"
        "| --- | --- | --- | --- |\n"
        f"{terminal}\n"
        "---\n\n"
        "# Recently completed\n\n"
        "| ID | Title | Evidence |\n"
        "| --- | --- | --- |\n"
    )


def _v2_spec_text(
    task_id: str,
    *,
    approval: str = "approved",
    priority: str = "P2",
    depends_on: tuple[str, ...] = (),
) -> str:
    verification = json.dumps([sys.executable, "-c", "raise SystemExit(0)"])
    metadata = json.dumps(
        {
            "execution_approval": approval,
            "priority": priority,
            "size": "M",
            "roadmap_target": "Test roadmap target",
            "depends_on": list(depends_on),
            "group": "engineering",
        },
        indent=2,
    )
    return (
        f"# {task_id} — Public run integration\n\n"
        f"## Task metadata\n\n```json\n{metadata}\n```\n\n"
        "## Goal\n\nDeliver the integration marker.\n\n"
        "## Context / References\n\nUse the approved v2 harness contract.\n\n"
        "## Scope\n\n- add the integration marker\n\n"
        "## Out of scope\n\n- unrelated changes\n\n"
        "## Approved implementation approach\n\n"
        "Create one deterministic marker file.\n\n"
        "## Acceptance criteria\n\n- the marker is committed and published\n\n"
        "## Execution checkpoints\n\n"
        "### CP-1 — Marker\n"
        "- Objective: Create the marker.\n"
        "- Required result: The marker file exists.\n"
        "- Constraints: Do not edit lifecycle files.\n"
        f"- Verification: {verification}\n"
        "- Review focus: Marker scope and content.\n\n"
        "## Full verification\n\n"
        f"{verification}\n\n"
        "## Known constraints / edge cases\n\nNone beyond the declared scope.\n"
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
    (seed / ".gitignore").write_text("*.patch\n", encoding="utf-8")
    (seed / "docs").mkdir()
    (seed / "docs" / "TASK.md").write_text(_task_md_text(_TASK_ID), encoding="utf-8")
    _run_git(["add", ".gitignore", "README.md", "docs/TASK.md"], cwd=seed)
    _run_git(["commit", "-q", "-m", "seed"], cwd=seed)
    _run_git(["remote", "add", "origin", str(origin)], cwd=seed)
    _run_git(["push", "-q", "origin", "main"], cwd=seed)

    work = tmp_path / "work"
    _run_git(["clone", "-q", str(origin), str(work)], cwd=tmp_path)
    _configure_user(work)

    scratch = tmp_path / "scratch"
    scratch.mkdir()

    return Env(origin=origin, seed=seed, work=work, scratch=scratch)


# Forces the fake implementer/reviewer child Python process to decode its
# own stdin (and encode its own stdout) as UTF-8, regardless of the host's
# console codepage. run_agent already sends/receives bytes as UTF-8
# (tools/autonomous_pr/agents.py), but that only controls the PARENT side
# of the pipe -- a bare `sys.executable -c <code>` child still falls back
# to Python's own platform-default text encoding for its `sys.stdin`/
# `sys.stdout` on Windows, which is not UTF-8 and would otherwise silently
# mangle any non-ASCII character (e.g. the canonical "—" docs/TASK.md
# uses for "none"/empty) into U+FFFD on the way through these test fakes.
_FAKE_AGENT_ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


def _implementer_spec(work: Path, code: str, timeout: float = 10.0) -> AgentInvocationSpec:
    return AgentInvocationSpec(
        role=AgentRole.IMPLEMENTER,
        executable=sys.executable,
        args=("-c", code),
        cwd=work,
        timeout_seconds=timeout,
        env=_FAKE_AGENT_ENV,
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
        env=_FAKE_AGENT_ENV,
        fresh_context_capable=True,
        has_git_or_github_write_access=False,
    )


def _verify_true() -> tuple[str, ...]:
    return (sys.executable, "-c", "raise SystemExit(0)")


# Fake `gh`: handles `pr create --draft ...` (prints a fixed PR URL), `pr
# view <number> --json headRefOid` (reports the actual local HEAD of the
# repo it is invoked in, so the required-CI PR-head-SHA binding sees a
# match), and `pr checks <number> --required --json name,state,bucket`
# (always reports one required check passing, exit 0). Used as
# _default_config's default gh_command so every existing test that now
# naturally runs the full lifecycle (Group 4) gets a working fake gh
# without per-test wiring; tests that specifically exercise CI behavior
# override gh_command with a more elaborate fake.
_FAKE_GH_ALWAYS_PASS = (
    "import sys, json, subprocess\n"
    "args = sys.argv[1:]\n"
    "if args[:2] == ['pr', 'list']:\n"
    "    assert args[args.index('--state') + 1] == 'open'\n"
    "    assert '--base' not in args\n"
    "    assert int(args[args.index('--limit') + 1]) == 100\n"
    "    print('[]')\n"
    "elif args[:2] == ['pr', 'create']:\n"
    "    print('https://github.com/example/repo/pull/1')\n"
    "elif args[:2] == ['pr', 'view']:\n"
    "    sha = subprocess.run(\n"
    "        ['git', 'rev-parse', 'HEAD'], capture_output=True, text=True\n"
    "    ).stdout.strip()\n"
    "    print(json.dumps({'headRefOid': sha}))\n"
    "elif args[:2] == ['pr', 'checks']:\n"
    "    print(json.dumps([{'name': 'build', 'state': 'SUCCESS', 'bucket': 'pass'}]))\n"
    "else:\n"
    "    raise SystemExit(1)\n"
)


def _default_gh_command() -> tuple[str, ...]:
    return (sys.executable, "-c", _FAKE_GH_ALWAYS_PASS)


def _public_dispatch_gh_command(
    task_id: str,
    *,
    open_prs: tuple[dict[str, object], ...] = (),
    fail_list: bool = False,
    command_log: Path | None = None,
) -> tuple[str, ...]:
    open_prs_json = json.dumps(open_prs)
    log_statement = (
        ""
        if command_log is None
        else (
            f"pathlib.Path({str(command_log)!r}).open('a', encoding='utf-8').write("
            "json.dumps(args) + '\\n')\n"
        )
    )
    code = (
        "import sys, json, pathlib, subprocess\n"
        "args = sys.argv[1:]\n"
        + log_statement
        + "if args[:2] == ['pr', 'list']:\n"
        "    assert args[args.index('--state') + 1] == 'open'\n"
        "    assert '--base' not in args\n"
        "    limit = int(args[args.index('--limit') + 1])\n"
        + (
            "    raise SystemExit(7)\n"
            if fail_list
            else (
                f"    records = json.loads({open_prs_json!r})\n"
                "    print(json.dumps(records[:limit]))\n"
            )
        )
        + "elif args[:2] == ['pr', 'create']:\n"
        "    body = args[args.index('--body') + 1]\n"
        f"    assert 'selected_task_id: {task_id}' in body\n"
        "    assert 'original_source_sha:' in body\n"
        f"    assert 'canonical_path: docs/tasks/{task_id}.md' in body\n"
        "    assert 'full_document_digest:' in body\n"
        "    print('https://github.com/example/repo/pull/1')\n"
        "elif args[:2] == ['pr', 'view']:\n"
        "    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], "
        "text=True).strip()\n"
        "    print(json.dumps({'headRefOid': head}))\n"
        "elif args[:2] == ['pr', 'checks']:\n"
        "    print(json.dumps([{'name': 'required', 'state': 'SUCCESS', "
        "'bucket': 'pass'}]))\n"
        "else:\n"
        "    raise SystemExit(1)\n"
    )
    return (sys.executable, "-c", code)


def _default_config(
    env: Env,
    *,
    implementer_spec: AgentInvocationSpec,
    reviewer_spec: AgentInvocationSpec,
    max_repairs: int | None = None,
    verification_commands: tuple[tuple[str, ...], ...] | None = None,
    delivery_branch: str = "delivery",
    gh_command: tuple[str, ...] | None = None,
) -> OrchestratorConfig:
    return OrchestratorConfig(
        task_id=_TASK_ID,
        repo=env.work,
        implementer_profiles=_profiles(implementer_spec),
        reviewer_profiles=_profiles(reviewer_spec),
        delivery_branch=delivery_branch,
        gh_command=gh_command if gh_command is not None else _default_gh_command(),
    )


@dataclass
class PublicDispatchEnv:
    origin: Path
    seed: Path
    work: Path


def _make_public_dispatch_env(
    tmp_path: Path,
    *,
    task_text: str | None = None,
    task_md_text: str | None = None,
) -> PublicDispatchEnv:
    origin = tmp_path / "dispatch-origin.git"
    _run_git(["init", "-q", "--bare", "-b", "main", str(origin)], cwd=tmp_path)
    seed = tmp_path / "dispatch-seed"
    _run_git(["init", "-q", "-b", "main", str(seed)], cwd=tmp_path)
    _configure_user(seed)
    _run_git(["config", "core.autocrlf", "false"], cwd=seed)
    (seed / ".gitignore").write_text("*.patch\n", encoding="utf-8")
    (seed / "docs" / "tasks").mkdir(parents=True)
    (seed / "docs" / "TASK.md").write_text(
        task_md_text or _v2_task_md_text(_TASK_ID), encoding="utf-8"
    )
    (seed / "docs" / "DEVELOPMENT_LOG.md").write_text(
        "# Development log\n", encoding="utf-8"
    )
    (seed / "docs" / "tasks" / f"{_TASK_ID}.md").write_text(
        task_text or _v2_spec_text(_TASK_ID), encoding="utf-8", newline=""
    )
    _run_git(["add", ".gitignore", "docs"], cwd=seed)
    _run_git(["commit", "-q", "-m", "seed file dispatch target"], cwd=seed)
    _run_git(["remote", "add", "origin", str(origin)], cwd=seed)
    _run_git(["push", "-q", "origin", "main"], cwd=seed)
    work = tmp_path / "dispatch-work"
    _run_git(
        ["-c", "core.autocrlf=false", "clone", "-q", str(origin), str(work)],
        cwd=tmp_path,
    )
    _configure_user(work)
    _run_git(["config", "core.autocrlf", "false"], cwd=work)
    return PublicDispatchEnv(origin=origin, seed=seed, work=work)


def _public_dispatch_implementer_code(task_id: str) -> str:
    return (
        "import pathlib, sys\n"
        "prompt = sys.stdin.read()\n"
        f"assert 'selected_task_id: {task_id}' in prompt\n"
        "assert 'original_source_sha:' in prompt\n"
        f"assert 'canonical_path: docs/tasks/{task_id}.md' in prompt\n"
        "assert 'full_document_digest:' in prompt\n"
        "if 'CURRENT_GATE: prospective Task Closure\\n' in prompt:\n"
        "    task = pathlib.Path('docs/TASK.md')\n"
        "    text = task.read_bytes().decode('utf-8')\n"
        "    eol = '\\r\\n' if '\\r\\n' in text else '\\n'\n"
        "    separator = ('| ID | Status | Evidence | Title |' + eol "
        "+ '| --- | --- | --- | --- |' + eol)\n"
        f"    row = '| `{task_id}` | `Done` | PR #1 | Public run integration |' + eol\n"
        "    assert separator in text and row not in text\n"
        "    task.write_bytes(text.replace(separator, separator + row, 1).encode('utf-8'))\n"
        "    log = pathlib.Path('docs/DEVELOPMENT_LOG.md')\n"
        "    log.write_text(log.read_text(encoding='utf-8') + "
        "'\\n- Public run integration closure.\\n', encoding='utf-8')\n"
        "elif 'CURRENT_CHECKPOINT:\\nid: CP-1\\n' in prompt:\n"
        "    pathlib.Path('integration-marker.txt').write_text("
        "'accepted v2 checkpoint\\n', encoding='utf-8')\n"
        "else:\n"
        "    raise SystemExit('unexpected implementer handoff')\n"
    )


def _public_dispatch_config(
    env: PublicDispatchEnv,
    *,
    selector: str,
    expected_task_id: str = _TASK_ID,
) -> OrchestratorConfig:
    reviewer_code = "import sys\nsys.stdin.read()\nprint('APPROVED')\n"
    return OrchestratorConfig(
        task_id=selector,
        repo=env.work,
        implementer_profiles=_profiles(
            _implementer_spec(
                env.work, _public_dispatch_implementer_code(expected_task_id)
            )
        ),
        reviewer_profiles=_profiles(_reviewer_spec(env.work, reviewer_code)),
        delivery_branch="",
        gh_command=_public_dispatch_gh_command(expected_task_id),
    )


def _commit_and_push_main(seed: Path, message: str, *paths: str) -> None:
    _run_git(["add", *paths], cwd=seed)
    _run_git(["commit", "-q", "-m", message], cwd=seed)
    _run_git(["push", "-q", "origin", "main"], cwd=seed)


def _mutate_main_before_first_acceptance(
    monkeypatch: pytest.MonkeyPatch,
    mutation: Callable[[], None],
) -> None:
    real_fetch = repository.fetch_and_capture_origin_main_sha
    calls = 0

    def fetch(repo: Path) -> str:
        nonlocal calls
        calls += 1
        if calls == 2:
            mutation()
        return real_fetch(repo)

    monkeypatch.setattr(repository, "fetch_and_capture_origin_main_sha", fetch)




# --- TSK-0028 CP-2: spec-driven adaptive checkpoint primitives ---------------


def test_public_run_selects_only_v2_spec_driven_pipeline(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _default_config(
        env,
        implementer_spec=_implementer_spec(env.work, "print('unused')"),
        reviewer_spec=_reviewer_spec(env.work, "print('unused')"),
    )
    base_sha = "a" * 40
    head_sha = "b" * 40
    spec = _v2_spec()
    target = _cp3_target(base_sha, spec)
    selected = _selected_from_target(target)
    checkpoint_result = orch_module.V2CheckpointExecutionResult(
        completed=True,
        accepted_candidates=(),
        gate_histories=(),
        checkpoint_evidence=(),
    )
    refreshed_candidate = _accepted_test_candidate(spec, head_sha)
    refreshed_checkpoint = orch_module.AcceptedCheckpointEvidence(
        candidate=refreshed_candidate,
        predecessor_review_boundary_sha=base_sha,
        accepted_head_sha=head_sha,
        accepted_base_context_identity=head_sha,
    )
    evidence = orch_module.V2ImplementationEvidence(
        spec_identity=spec.digest,
        base_identity=base_sha,
        accepted_checkpoints=[refreshed_checkpoint],
    )
    history = GateHistory(
        context=GateContext(
            gate_id="pre-closure-cumulative-review",
            spec_identity=spec.digest,
            accepted_base_context_identity=base_sha,
        )
    )
    pre_closure = orch_module.V2PreClosureExecutionResult(
        completed=True,
        evidence=evidence,
        cumulative_history=history,
        replay_histories=(),
    )
    closure = orch_module.V2ClosureExecutionResult(
        completed=True,
        published=True,
        pre_closure_result=pre_closure,
        pr_url="https://github.com/example/repo/pull/1",
    )
    calls: list[str] = []

    monkeypatch.setattr(repository, "fetch_and_capture_origin_main_sha", lambda repo: base_sha)
    monkeypatch.setattr(repository, "is_worktree_clean", lambda repo: True)
    monkeypatch.setattr(repository, "head_sha", lambda repo: head_sha)
    monkeypatch.setattr(
        repository,
        "create_delivery_branch_from_sha",
        lambda repo, branch, sha: calls.append(f"branch:{sha}"),
    )
    monkeypatch.setattr(
        orch_module,
        "_resolve_file_based_target",
        lambda config, selector, sha: calls.append(f"select:{selector}:{sha}")
        or selected,
    )
    monkeypatch.setattr(
        orch_module,
        "execute_v2_checkpoints",
        lambda *args, **kwargs: calls.append("checkpoints") or checkpoint_result,
    )
    monkeypatch.setattr(
        orch_module,
        "execute_v2_pre_closure_review",
        lambda *args, **kwargs: calls.append("pre-closure") or pre_closure,
    )
    def closure_with_latest_checkpoints(*args: object, **kwargs: object) -> object:
        current = args[2]
        assert isinstance(current, orch_module.V2CheckpointExecutionResult)
        assert current.checkpoint_evidence == (refreshed_checkpoint,)
        calls.append("closure-mode-c")
        return closure

    monkeypatch.setattr(
        orch_module, "execute_v2_unpublished_closure", closure_with_latest_checkpoints
    )

    result = run(config)

    assert result.outcome is RunOutcome.STOP
    assert result.phase is Phase.READY_FOR_HUMAN_MERGE
    assert calls == [
        f"select:{_TASK_ID}:{base_sha}",
        f"branch:{base_sha}",
        "checkpoints",
        "pre-closure",
        "closure-mode-c",
    ]
    assert not hasattr(config, "max_repairs")
    assert not hasattr(config, "verification_commands")


@pytest.mark.parametrize(
    "selector, expected_mode",
    [
        (_TASK_ID, TaskSelectionMode.EXPLICIT),
        ("NEXT", TaskSelectionMode.NEXT),
    ],
)
def test_public_run_executes_real_file_dispatch_pipeline_to_ready_stop(
    tmp_path: Path,
    selector: str,
    expected_mode: TaskSelectionMode,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin = tmp_path / "public-origin.git"
    _run_git(["init", "-q", "--bare", "-b", "main", str(origin)], cwd=tmp_path)

    seed = tmp_path / "public-seed"
    _run_git(["init", "-q", "-b", "main", str(seed)], cwd=tmp_path)
    _configure_user(seed)
    (seed / ".gitignore").write_text("*.patch\n", encoding="utf-8")
    (seed / "docs" / "tasks").mkdir(parents=True)
    (seed / "docs" / "TASK.md").write_text(
        _v2_task_md_text(_TASK_ID), encoding="utf-8"
    )
    (seed / "docs" / "DEVELOPMENT_LOG.md").write_text(
        "# Development log\n", encoding="utf-8"
    )
    (seed / "docs" / "tasks" / f"{_TASK_ID}.md").write_text(
        _v2_spec_text(_TASK_ID), encoding="utf-8"
    )
    _run_git(["add", ".gitignore", "docs"], cwd=seed)
    _run_git(["commit", "-q", "-m", "seed v2 execution target"], cwd=seed)
    _run_git(["remote", "add", "origin", str(origin)], cwd=seed)
    _run_git(["push", "-q", "origin", "main"], cwd=seed)

    work = tmp_path / "public-work"
    _run_git(["clone", "-q", str(origin), str(work)], cwd=tmp_path)
    _configure_user(work)

    implementer_code = _public_dispatch_implementer_code(_TASK_ID)
    reviewer_code = "import sys\nsys.stdin.read()\nprint('APPROVED')\n"
    config = OrchestratorConfig(
        task_id=selector,
        repo=work,
        implementer_profiles=_profiles(_implementer_spec(work, implementer_code)),
        reviewer_profiles=_profiles(_reviewer_spec(work, reviewer_code)),
        delivery_branch="",
        gh_command=_public_dispatch_gh_command(_TASK_ID),
    )
    routed: list[tuple[AgentRole, AgentWorkKind, ComputeProfile]] = []
    real_route_agent_work = orch_module.route_agent_work

    def observe_route(
        *,
        role: AgentRole,
        work_kind: AgentWorkKind,
        history: GateHistory | None = None,
        direct_upstream_repair_packet: RepairPacket | None = None,
        seed_verification_rejection_count: int = 0,
    ) -> RoutingDecision:
        decision = real_route_agent_work(
            role=role,
            work_kind=work_kind,
            history=history,
            direct_upstream_repair_packet=direct_upstream_repair_packet,
            seed_verification_rejection_count=seed_verification_rejection_count,
        )
        routed.append(
            (decision.role, decision.work_kind, decision.selected_profile)
        )
        return decision

    monkeypatch.setattr(orch_module, "route_agent_work", observe_route)

    result = run(config)

    assert result.outcome is RunOutcome.STOP
    assert result.phase is Phase.READY_FOR_HUMAN_MERGE
    assert result.blocked_reason is None
    assert result.task_id == _TASK_ID
    assert result.selection_mode is expected_mode
    assert result.spec_source_sha is not None
    assert result.spec_path == f"docs/tasks/{_TASK_ID}.md"
    assert result.spec_digest is not None
    assert result.pr_url == "https://github.com/example/repo/pull/1"
    assert tuple(metric.gate_id for metric in result.review_metrics) == (
        "CP-1",
        "pre-closure-cumulative-review",
        "prospective-task-closure",
        "mode-c-final-cumulative-audit",
    )
    assert all(metric.review_iterations == 1 for metric in result.review_metrics)
    assert all(
        metric.last_reviewer_verdict is ReviewVerdict.APPROVED
        for metric in result.review_metrics
    )
    assert routed == [
        (
            AgentRole.IMPLEMENTER,
            AgentWorkKind.CHECKPOINT_IMPLEMENTATION,
            ComputeProfile.ROUTINE,
        ),
        (
            AgentRole.REVIEWER,
            AgentWorkKind.CHECKPOINT_REVIEW,
            ComputeProfile.DELIBERATE,
        ),
        (
            AgentRole.REVIEWER,
            AgentWorkKind.PRE_CLOSURE_CUMULATIVE_REVIEW,
            ComputeProfile.CRITICAL,
        ),
        (
            AgentRole.IMPLEMENTER,
            AgentWorkKind.TASK_CLOSURE_PREPARATION,
            ComputeProfile.ROUTINE,
        ),
        (
            AgentRole.REVIEWER,
            AgentWorkKind.TASK_CLOSURE_REVIEW,
            ComputeProfile.DELIBERATE,
        ),
        (
            AgentRole.REVIEWER,
            AgentWorkKind.MODE_C_REVIEW,
            ComputeProfile.CRITICAL,
        ),
    ]
    assert [decision.sequence for decision in result.routing_decisions] == list(
        range(1, len(routed) + 1)
    )
    assert [
        (decision.role, decision.work_kind, decision.selected_profile)
        for decision in result.routing_decisions
    ] == routed
    assert [decision.gate_id for decision in result.routing_decisions] == [
        "CP-1",
        "CP-1",
        "pre-closure-cumulative-review",
        "prospective-task-closure",
        "prospective-task-closure",
        "mode-c-final-cumulative-audit",
    ]
    assert result.head_sha == _run_git(["rev-parse", "HEAD"], cwd=work).strip()
    assert result.head_sha == _run_git(
        ["rev-parse", f"origin/autonomous-pr/{_TASK_ID.lower()}"], cwd=work
    ).strip()
    assert _run_git(["status", "--porcelain"], cwd=work) == ""
    assert (work / "integration-marker.txt").read_text(encoding="utf-8") == (
        "accepted v2 checkpoint\n"
    )
    terminal = task_context.parse_terminal_registry(
        (work / "docs" / "TASK.md").read_text(encoding="utf-8")
    )
    assert terminal.tasks[-1] == TerminalTask(
        task_id=_TASK_ID,
        status=TaskStatus.DONE,
        evidence="PR #1",
        title="Public run integration",
    )
    assert (work / "docs" / "tasks" / f"{_TASK_ID}.md").is_file()
    assert (work / "docs" / "DEVELOPMENT_LOG.md").read_text(
        encoding="utf-8"
    ).splitlines() == [
        "# Development log",
        "",
        "- Public run integration closure.",
    ]


def test_public_run_preserves_metrics_on_explicit_reviewer_blocked(
    tmp_path: Path,
) -> None:
    env = _make_public_dispatch_env(tmp_path)
    reviewer_code = "import sys\nsys.stdin.read()\nprint('BLOCKED')\n"
    config = OrchestratorConfig(
        task_id=_TASK_ID,
        repo=env.work,
        implementer_profiles=_profiles(
            _implementer_spec(
                env.work, _public_dispatch_implementer_code(_TASK_ID)
            )
        ),
        reviewer_profiles=_profiles(_reviewer_spec(env.work, reviewer_code)),
        delivery_branch="",
        gh_command=_public_dispatch_gh_command(_TASK_ID),
    )

    result = run(config)

    assert result.outcome is RunOutcome.BLOCKED
    assert result.phase is Phase.CHECKPOINT_REVIEW
    assert len(result.review_metrics) == 1
    metric = result.review_metrics[0]
    assert metric.gate_id == "CP-1"
    assert metric.review_iterations == 1
    assert metric.findings_per_review == (0,)
    assert metric.last_reviewer_verdict is ReviewVerdict.BLOCKED
    assert [decision.sequence for decision in result.routing_decisions] == [1, 2]
    assert result.routing_decisions[-1].role is AgentRole.REVIEWER
    assert result.routing_decisions[-1].work_kind is AgentWorkKind.CHECKPOINT_REVIEW


def test_public_runs_reset_routing_sequence_and_record_failed_agent_invocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = (tmp_path / "first", tmp_path / "second")
    for root in roots:
        root.mkdir()
    environments = tuple(_make_public_dispatch_env(root) for root in roots)
    invocations = 0

    def failed_implementer(
        spec: AgentInvocationSpec, prompt: str
    ) -> AgentInvocationResult:
        nonlocal invocations
        assert spec.role is AgentRole.IMPLEMENTER
        assert prompt
        invocations += 1
        return AgentInvocationResult("", "process failed", 9, False)

    monkeypatch.setattr(orch_module, "run_implementer", failed_implementer)

    results = tuple(
        run(_public_dispatch_config(env, selector=_TASK_ID))
        for env in environments
    )

    assert invocations == 2
    for result in results:
        assert result.outcome is RunOutcome.BLOCKED
        assert result.phase is Phase.IMPLEMENTATION_CHECKPOINT
        assert len(result.routing_decisions) == 1
        decision = result.routing_decisions[0]
        assert decision.sequence == 1
        assert decision.role is AgentRole.IMPLEMENTER
        assert decision.work_kind is AgentWorkKind.CHECKPOINT_IMPLEMENTATION
        assert decision.selected_profile is ComputeProfile.ROUTINE


def test_public_next_no_work_stops_before_branch_agents_or_pr(tmp_path: Path) -> None:
    origin = tmp_path / "no-work-origin.git"
    _run_git(["init", "-q", "--bare", "-b", "main", str(origin)], cwd=tmp_path)
    seed = tmp_path / "no-work-seed"
    _run_git(["init", "-q", "-b", "main", str(seed)], cwd=tmp_path)
    _configure_user(seed)
    (seed / "docs" / "tasks").mkdir(parents=True)
    (seed / "docs" / "TASK.md").write_text(
        _v2_task_md_text(_TASK_ID), encoding="utf-8"
    )
    (seed / "docs" / "tasks" / f"{_TASK_ID}.md").write_text(
        _v2_spec_text(_TASK_ID, approval="draft"), encoding="utf-8"
    )
    _run_git(["add", "docs"], cwd=seed)
    _run_git(["commit", "-q", "-m", "seed draft catalog"], cwd=seed)
    _run_git(["remote", "add", "origin", str(origin)], cwd=seed)
    _run_git(["push", "-q", "origin", "main"], cwd=seed)
    work = tmp_path / "no-work-work"
    _run_git(["clone", "-q", str(origin), str(work)], cwd=tmp_path)
    _configure_user(work)
    initial_head = _run_git(["rev-parse", "HEAD"], cwd=work).strip()

    fail_if_invoked = "raise SystemExit('agent must not be invoked')"
    result = run(
        OrchestratorConfig(
            task_id="NEXT",
            repo=work,
            implementer_profiles=_profiles(
                _implementer_spec(work, fail_if_invoked)
            ),
            reviewer_profiles=_profiles(_reviewer_spec(work, fail_if_invoked)),
            delivery_branch="",
            gh_command=(sys.executable, "-c", fail_if_invoked),
        )
    )

    assert result.outcome is RunOutcome.NO_ELIGIBLE_TASK
    assert result.task_id is None
    assert result.delivery_branch is None
    assert result.phase is Phase.PREFLIGHT
    assert result.no_work_reasons[0].task_id == _TASK_ID
    assert result.review_metrics == ()
    assert result.routing_decisions == ()
    assert _run_git(["branch", "--show-current"], cwd=work).strip() == "main"
    assert _run_git(["rev-parse", "HEAD"], cwd=work).strip() == initial_head
    assert _run_git(["status", "--porcelain"], cwd=work) == ""


def test_public_explicit_id_runs_outside_next_priority_order(tmp_path: Path) -> None:
    env = _make_public_dispatch_env(tmp_path)
    higher_id = "TSK-9002"
    higher_path = env.seed / "docs" / "tasks" / f"{higher_id}.md"
    higher_path.write_text(
        _v2_spec_text(higher_id, priority="P0"), encoding="utf-8"
    )
    _commit_and_push_main(
        env.seed, "add higher priority approved task", f"docs/tasks/{higher_id}.md"
    )

    result = run(_public_dispatch_config(env, selector=_TASK_ID))

    assert result.outcome is RunOutcome.STOP
    assert result.task_id == _TASK_ID
    assert result.selection_mode is TaskSelectionMode.EXPLICIT


def test_public_next_changes_when_approved_file_is_added_without_tracker_edit(
    tmp_path: Path,
) -> None:
    env = _make_public_dispatch_env(tmp_path)
    before_sha = repository.fetch_and_capture_origin_main_sha(env.work)
    before = orch_module._resolve_file_based_target(
        _public_dispatch_config(env, selector="NEXT"), "NEXT", before_sha
    )
    assert isinstance(before, SelectedTask)
    assert before.document.task_id == _TASK_ID

    tracker_before = (env.seed / "docs" / "TASK.md").read_bytes()
    higher_id = "TSK-9002"
    higher_path = env.seed / "docs" / "tasks" / f"{higher_id}.md"
    higher_path.write_text(
        _v2_spec_text(higher_id, priority="P0"), encoding="utf-8"
    )
    _commit_and_push_main(
        env.seed, "add higher priority approved task", f"docs/tasks/{higher_id}.md"
    )
    assert (env.seed / "docs" / "TASK.md").read_bytes() == tracker_before

    result = run(
        _public_dispatch_config(
            env, selector="NEXT", expected_task_id=higher_id
        )
    )

    assert result.outcome is RunOutcome.STOP
    assert result.task_id == higher_id
    assert result.selection_mode is TaskSelectionMode.NEXT


def test_same_task_branch_collision_cannot_be_bypassed_with_alternate_name(
    tmp_path: Path,
) -> None:
    env = _make_public_dispatch_env(tmp_path)
    canonical = f"autonomous-pr/{_TASK_ID.lower()}"
    _run_git(["branch", canonical], cwd=env.seed)
    _run_git(["push", "-q", "origin", canonical], cwd=env.seed)
    config = dataclasses.replace(
        _public_dispatch_config(env, selector=_TASK_ID),
        delivery_branch="codex/alternate-name",
    )

    result = run(config)

    assert result.outcome is RunOutcome.BLOCKED
    assert result.phase is Phase.PREFLIGHT
    assert result.delivery_branch is None
    assert result.routing_decisions == ()
    assert "implicit resume/reuse is forbidden" in (result.blocked_reason or "")
    assert _run_git(["branch", "--list", "codex/alternate-name"], cwd=env.work) == ""


def _open_pr_record(
    task_id: str,
    head: str = "legacy/custom-head",
    *,
    base: str = "main",
) -> dict[str, object]:
    return {
        "number": 77,
        "url": "https://github.com/example/repo/pull/77",
        "headRefName": head,
        "baseRefName": base,
        "title": f"{task_id}: Existing task delivery",
        "body": (
            "AUTONOMOUS_PR v2 draft\n\n"
            "Selected task provenance:\n"
            f"selected_task_id: {task_id}\n"
            "selection_mode: explicit\n"
        ),
    }


@pytest.mark.parametrize("delivery_branch", ["", "codex/another-custom-name"])
def test_open_same_task_pr_on_custom_branch_blocks_before_side_effects(
    tmp_path: Path,
    delivery_branch: str,
) -> None:
    env = _make_public_dispatch_env(tmp_path)
    agent_marker = env.work / "agent-was-called"
    gh_log = tmp_path / "gh-commands.jsonl"
    agent_code = (
        "import pathlib\n"
        f"pathlib.Path({str(agent_marker)!r}).write_text('called', encoding='utf-8')\n"
        "raise SystemExit(3)\n"
    )
    config = dataclasses.replace(
        _public_dispatch_config(env, selector=_TASK_ID),
        delivery_branch=delivery_branch,
        implementer_profiles=_profiles(_implementer_spec(env.work, agent_code)),
        reviewer_profiles=_profiles(_reviewer_spec(env.work, agent_code)),
        gh_command=_public_dispatch_gh_command(
            _TASK_ID,
            open_prs=(_open_pr_record(_TASK_ID, base="release"),),
            command_log=gh_log,
        ),
    )

    result = run(config)

    assert result.outcome is RunOutcome.BLOCKED
    assert result.phase is Phase.PREFLIGHT
    assert result.delivery_branch is None
    assert "MANUAL reconciliation is required" in (result.blocked_reason or "")
    assert not agent_marker.exists()
    assert [json.loads(line)[:2] for line in gh_log.read_text().splitlines()] == [
        ["pr", "list"]
    ]
    assert _run_git(["branch", "--show-current"], cwd=env.work).strip() == "main"
    assert _run_git(
        ["branch", "--list", f"autonomous-pr/{_TASK_ID.lower()}"], cwd=env.work
    ) == ""
    if delivery_branch:
        assert _run_git(["branch", "--list", delivery_branch], cwd=env.work) == ""


def test_open_pr_for_other_exact_task_does_not_block_selected_task(
    tmp_path: Path,
) -> None:
    env = _make_public_dispatch_env(tmp_path)
    other_pr = _open_pr_record("TSK-9999")
    other_pr["body"] = f"{other_pr['body']}Unstructured mention: {_TASK_ID}\n"
    config = dataclasses.replace(
        _public_dispatch_config(env, selector=_TASK_ID),
        gh_command=_public_dispatch_gh_command(
            _TASK_ID, open_prs=(other_pr,)
        ),
    )

    result = run(config)

    assert result.outcome is RunOutcome.STOP
    assert result.phase is Phase.READY_FOR_HUMAN_MERGE


def test_open_pr_collision_read_failure_blocks_before_side_effects(
    tmp_path: Path,
) -> None:
    env = _make_public_dispatch_env(tmp_path)
    agent_marker = env.work / "agent-was-called"
    gh_log = tmp_path / "gh-commands.jsonl"
    agent_code = (
        "import pathlib\n"
        f"pathlib.Path({str(agent_marker)!r}).write_text('called', encoding='utf-8')\n"
    )
    config = dataclasses.replace(
        _public_dispatch_config(env, selector=_TASK_ID),
        implementer_profiles=_profiles(_implementer_spec(env.work, agent_code)),
        reviewer_profiles=_profiles(_reviewer_spec(env.work, agent_code)),
        gh_command=_public_dispatch_gh_command(
            _TASK_ID, fail_list=True, command_log=gh_log
        ),
    )

    result = run(config)

    assert result.outcome is RunOutcome.BLOCKED
    assert result.phase is Phase.PREFLIGHT
    assert result.delivery_branch is None
    assert "gh pr list" in (result.blocked_reason or "")
    assert not agent_marker.exists()
    assert [json.loads(line)[:2] for line in gh_log.read_text().splitlines()] == [
        ["pr", "list"]
    ]
    assert _run_git(["branch", "--show-current"], cwd=env.work).strip() == "main"
    assert _run_git(
        ["branch", "--list", f"autonomous-pr/{_TASK_ID.lower()}"], cwd=env.work
    ) == ""


def _assert_open_pr_guard_blocks_without_writes(
    tmp_path: Path,
    open_prs: tuple[dict[str, object], ...],
) -> RunResult:
    env = _make_public_dispatch_env(tmp_path)
    agent_marker = env.work / "agent-was-called"
    gh_log = tmp_path / "gh-commands.jsonl"
    agent_code = (
        "import pathlib\n"
        f"pathlib.Path({str(agent_marker)!r}).write_text('called', encoding='utf-8')\n"
    )
    config = dataclasses.replace(
        _public_dispatch_config(env, selector=_TASK_ID),
        implementer_profiles=_profiles(_implementer_spec(env.work, agent_code)),
        reviewer_profiles=_profiles(_reviewer_spec(env.work, agent_code)),
        gh_command=_public_dispatch_gh_command(
            _TASK_ID, open_prs=open_prs, command_log=gh_log
        ),
    )

    result = run(config)

    assert result.outcome is RunOutcome.BLOCKED
    assert result.phase is Phase.PREFLIGHT
    assert result.delivery_branch is None
    assert not agent_marker.exists()
    assert [json.loads(line)[:2] for line in gh_log.read_text().splitlines()] == [
        ["pr", "list"]
    ]
    assert _run_git(["branch", "--show-current"], cwd=env.work).strip() == "main"
    assert _run_git(
        ["branch", "--list", f"autonomous-pr/{_TASK_ID.lower()}"], cwd=env.work
    ) == ""
    return result


def test_open_pr_scan_blocks_when_limit_may_have_truncated_results(
    tmp_path: Path,
) -> None:
    records = tuple(
        {
            **_open_pr_record(f"TSK-{index + 1000}"),
            "number": index + 1,
            "url": f"https://github.com/example/repo/pull/{index + 1}",
            "headRefName": f"other/{index + 1}",
        }
        for index in range(100)
    )

    result = _assert_open_pr_guard_blocks_without_writes(tmp_path, records)

    assert "may be truncated" in (result.blocked_reason or "")


@pytest.mark.parametrize("identity_source", ["title-only", "body-only"])
def test_exact_title_or_body_identity_blocks_legacy_or_structured_pr(
    tmp_path: Path,
    identity_source: str,
) -> None:
    record = _open_pr_record(_TASK_ID, base="release")
    if identity_source == "title-only":
        record["body"] = "Legacy PR without structured provenance.\n"
    else:
        record["title"] = "File-based task dispatch"

    result = _assert_open_pr_guard_blocks_without_writes(tmp_path, (record,))

    assert "already owns selected task" in (result.blocked_reason or "")


@pytest.mark.parametrize(
    "body,title,expected_error",
    [
        (
            "Selected task provenance:\n"
            f"selected_task_id: {_TASK_ID}\n"
            "selected_task_id: TSK-9999\n",
            "Unstructured PR",
            "exactly one selected_task_id",
        ),
        (
            "Selected task provenance:\n"
            f"selected_task_id: {_TASK_ID}\n\n"
            "Selected task provenance:\n"
            f"selected_task_id: {_TASK_ID}\n",
            "Unstructured PR",
            "at most one Selected task provenance block",
        ),
        (
            "Selected task provenance:\nselected_task_id: TSK-9999\n",
            f"{_TASK_ID}: Conflicting title",
            "conflicting structured task identities",
        ),
    ],
)
def test_malformed_or_conflicting_pr_identity_blocks_without_first_value_wins(
    tmp_path: Path,
    body: str,
    title: str,
    expected_error: str,
) -> None:
    record = _open_pr_record(_TASK_ID)
    record["body"] = body
    record["title"] = title

    result = _assert_open_pr_guard_blocks_without_writes(tmp_path, (record,))

    assert expected_error in (result.blocked_reason or "")


@pytest.mark.parametrize(
    "change", ["metadata", "approval", "line-endings", "deleted"]
)
def test_public_run_blocks_selected_document_change_before_checkpoint_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    env = _make_public_dispatch_env(tmp_path)
    selected_path = env.seed / "docs" / "tasks" / f"{_TASK_ID}.md"
    initial_head = _run_git(["rev-parse", "HEAD"], cwd=env.work).strip()

    def mutate() -> None:
        blob = selected_path.read_bytes()
        if change == "metadata":
            blob = blob.replace(b'"priority": "P2"', b'"priority": "P1"', 1)
        elif change == "approval":
            blob = blob.replace(
                b'"execution_approval": "approved"',
                b'"execution_approval": "draft"',
                1,
            )
        elif change == "deleted":
            selected_path.unlink()
            _commit_and_push_main(
                env.seed,
                "delete selected active document",
                f"docs/tasks/{_TASK_ID}.md",
            )
            return
        else:
            assert b"\r\n" not in blob
            blob = blob.replace(b"\n", b"\r\n")
        selected_path.write_bytes(blob)
        _commit_and_push_main(
            env.seed,
            f"change selected document {change}",
            f"docs/tasks/{_TASK_ID}.md",
        )

    _mutate_main_before_first_acceptance(monkeypatch, mutate)

    result = run(_public_dispatch_config(env, selector=_TASK_ID))

    assert result.outcome is RunOutcome.BLOCKED
    assert result.phase is Phase.ORIGIN_MAIN_REVALIDATION
    expected = (
        "no longer approved"
        if change == "approval"
        else "expected exactly one tracked task file"
        if change == "deleted"
        else "changed the fixed selected task document"
    )
    assert expected in (result.blocked_reason or "")
    assert _run_git(["rev-parse", "HEAD"], cwd=env.work).strip() == initial_head
    assert _run_git(
        ["ls-remote", "--heads", "origin", f"autonomous-pr/{_TASK_ID.lower()}"],
        cwd=env.work,
    ) == ""


def test_public_run_blocks_lost_done_dependency_before_checkpoint_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dependency = "TSK-0001"
    env = _make_public_dispatch_env(
        tmp_path,
        task_text=_v2_spec_text(_TASK_ID, depends_on=(dependency,)),
        task_md_text=_v2_task_md_text(
            _TASK_ID, terminal_rows=((dependency, "Done"),)
        ),
    )

    def mutate() -> None:
        tracker = env.seed / "docs" / "TASK.md"
        tracker.write_text(
            tracker.read_text(encoding="utf-8").replace("`Done`", "`Superseded`"),
            encoding="utf-8",
        )
        _commit_and_push_main(env.seed, "supersede dependency", "docs/TASK.md")

    _mutate_main_before_first_acceptance(monkeypatch, mutate)

    result = run(_public_dispatch_config(env, selector=_TASK_ID))

    assert result.outcome is RunOutcome.BLOCKED
    assert result.phase is Phase.ORIGIN_MAIN_REVALIDATION
    assert "Superseded, not Done" in (result.blocked_reason or "")
    assert _run_git(
        ["ls-remote", "--heads", "origin", f"autonomous-pr/{_TASK_ID.lower()}"],
        cwd=env.work,
    ) == ""


def test_public_run_blocks_concurrent_terminal_outcome_before_checkpoint_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = _make_public_dispatch_env(tmp_path)

    def mutate() -> None:
        tracker = env.seed / "docs" / "TASK.md"
        text = tracker.read_text(encoding="utf-8")
        separator = "| --- | --- | --- | --- |\n\n---"
        terminal_row = f"| `{_TASK_ID}` | `Done` | PR #99 | Concurrent result |"
        assert separator in text
        tracker.write_text(
            text.replace(separator, f"| --- | --- | --- | --- |\n{terminal_row}\n\n---", 1),
            encoding="utf-8",
        )
        _commit_and_push_main(env.seed, "record concurrent terminal", "docs/TASK.md")

    _mutate_main_before_first_acceptance(monkeypatch, mutate)

    result = run(_public_dispatch_config(env, selector=_TASK_ID))

    assert result.outcome is RunOutcome.BLOCKED
    assert result.phase is Phase.ORIGIN_MAIN_REVALIDATION
    assert "is terminal (Done)" in (result.blocked_reason or "")
    assert _run_git(
        ["ls-remote", "--heads", "origin", f"autonomous-pr/{_TASK_ID.lower()}"],
        cwd=env.work,
    ) == ""


def test_public_next_does_not_reselect_after_higher_priority_task_appears(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = _make_public_dispatch_env(tmp_path)
    later_id = "TSK-8000"

    def mutate() -> None:
        later_path = env.seed / "docs" / "tasks" / f"{later_id}.md"
        later_path.write_text(
            _v2_spec_text(later_id, priority="P0"), encoding="utf-8"
        )
        _commit_and_push_main(
            env.seed, "add later higher priority task", f"docs/tasks/{later_id}.md"
        )

    _mutate_main_before_first_acceptance(monkeypatch, mutate)

    result = run(_public_dispatch_config(env, selector="NEXT"))

    assert result.outcome is RunOutcome.STOP
    assert result.task_id == _TASK_ID
    assert result.selection_mode is TaskSelectionMode.NEXT
    assert result.delivery_branch == f"autonomous-pr/{_TASK_ID.lower()}"
    assert _run_git(
        ["branch", "--list", f"autonomous-pr/{later_id.lower()}"], cwd=env.work
    ) == ""


def test_fixed_target_revalidation_ignores_new_unrelated_malformed_document(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = _make_public_dispatch_env(tmp_path)
    unrelated_id = "TSK-8000"

    def mutate() -> None:
        unrelated_path = env.seed / "docs" / "tasks" / f"{unrelated_id}.md"
        unrelated_path.write_text(
            f"# {unrelated_id} — Malformed unrelated draft\n\nnot metadata\n",
            encoding="utf-8",
        )
        _commit_and_push_main(
            env.seed,
            "add malformed unrelated document",
            f"docs/tasks/{unrelated_id}.md",
        )

    _mutate_main_before_first_acceptance(monkeypatch, mutate)

    result = run(_public_dispatch_config(env, selector="NEXT"))

    assert result.outcome is RunOutcome.STOP
    assert result.task_id == _TASK_ID
    assert result.phase is Phase.READY_FOR_HUMAN_MERGE


def test_new_invocation_still_rejects_same_malformed_catalog(
    tmp_path: Path,
) -> None:
    env = _make_public_dispatch_env(tmp_path)
    unrelated_id = "TSK-8000"
    unrelated_path = env.seed / "docs" / "tasks" / f"{unrelated_id}.md"
    unrelated_path.write_text(
        f"# {unrelated_id} — Malformed unrelated draft\n\nnot metadata\n",
        encoding="utf-8",
    )
    _commit_and_push_main(
        env.seed,
        "add malformed unrelated document",
        f"docs/tasks/{unrelated_id}.md",
    )

    result = run(_public_dispatch_config(env, selector=_TASK_ID))

    assert result.outcome is RunOutcome.BLOCKED
    assert result.phase is Phase.PREFLIGHT
    assert result.delivery_branch is None
    assert "invalid task document" in (result.blocked_reason or "")
    assert _run_git(["branch", "--show-current"], cwd=env.work).strip() == "main"


def test_selection_and_done_dependency_survive_terminal_spec_deletion(
    tmp_path: Path,
) -> None:
    dependency = "TSK-8000"
    env = _make_public_dispatch_env(
        tmp_path,
        task_text=_v2_spec_text(_TASK_ID, depends_on=(dependency,)),
        task_md_text=_v2_task_md_text(
            _TASK_ID, terminal_rows=((dependency, "Done"),)
        ),
    )
    legacy_path = env.seed / "docs" / "tasks" / f"{dependency}.md"
    legacy_path.write_bytes(b"retained terminal prefix\n\xff\xfe\n")
    _commit_and_push_main(
        env.seed,
        "retain invalid utf8 terminal spec",
        f"docs/tasks/{dependency}.md",
    )
    before_sha = repository.fetch_and_capture_origin_main_sha(env.work)

    before = orch_module._resolve_file_based_target(
        _public_dispatch_config(env, selector="NEXT"), "NEXT", before_sha
    )
    assert isinstance(before, SelectedTask)
    with pytest.raises(orch_module._Blocked, match=r"is terminal \(Done\)"):
        orch_module._resolve_file_based_target(
            _public_dispatch_config(env, selector=dependency),
            dependency,
            before_sha,
        )

    legacy_path.unlink()
    _commit_and_push_main(
        env.seed, "remove terminal spec", f"docs/tasks/{dependency}.md"
    )
    after_sha = repository.fetch_and_capture_origin_main_sha(env.work)
    after = orch_module._resolve_file_based_target(
        _public_dispatch_config(env, selector="NEXT"), "NEXT", after_sha
    )

    assert isinstance(after, SelectedTask)
    assert after.document == before.document
    assert after.mode is before.mode is TaskSelectionMode.NEXT
    with pytest.raises(orch_module._Blocked, match=r"is terminal \(Done\)"):
        orch_module._resolve_file_based_target(
            _public_dispatch_config(env, selector=dependency), dependency, after_sha
        )
    with pytest.raises(orch_module._Blocked, match="does not exist"):
        orch_module._resolve_file_based_target(
            _public_dispatch_config(env, selector="TSK-8999"),
            "TSK-8999",
            after_sha,
        )


@pytest.mark.parametrize("status", ["Done", "Superseded"])
def test_invalid_utf8_terminal_spec_is_filtered_before_decode_and_deletion(
    tmp_path: Path,
    status: str,
) -> None:
    terminal_id = "TSK-8000"
    env = _make_public_dispatch_env(tmp_path)
    selected_path = env.seed / "docs" / "tasks" / f"{_TASK_ID}.md"
    selected_path.unlink()
    terminal_path = env.seed / "docs" / "tasks" / f"{terminal_id}.md"
    terminal_path.write_bytes(b"retained terminal prefix\n\xff\xfe\n")
    (env.seed / "docs" / "TASK.md").write_text(
        _v2_task_md_text(_TASK_ID, terminal_rows=((terminal_id, status),)),
        encoding="utf-8",
    )
    _commit_and_push_main(
        env.seed,
        f"retain invalid utf8 {status} spec",
        "docs/TASK.md",
        f"docs/tasks/{_TASK_ID}.md",
        f"docs/tasks/{terminal_id}.md",
    )
    retained_sha = repository.fetch_and_capture_origin_main_sha(env.work)

    retained = orch_module._resolve_file_based_target(
        _public_dispatch_config(env, selector="NEXT"), "NEXT", retained_sha
    )
    assert isinstance(retained, NoEligibleTask)
    with pytest.raises(
        orch_module._Blocked, match=rf"is terminal \({status}\)"
    ):
        orch_module._resolve_file_based_target(
            _public_dispatch_config(env, selector=terminal_id),
            terminal_id,
            retained_sha,
        )

    terminal_path.unlink()
    _commit_and_push_main(
        env.seed,
        f"remove {status} spec",
        f"docs/tasks/{terminal_id}.md",
    )
    removed_sha = repository.fetch_and_capture_origin_main_sha(env.work)
    removed = orch_module._resolve_file_based_target(
        _public_dispatch_config(env, selector="NEXT"), "NEXT", removed_sha
    )

    assert isinstance(removed, NoEligibleTask)
    assert removed.reasons == retained.reasons


def test_public_run_rejects_invalid_utf8_nonterminal_before_side_effects(
    tmp_path: Path,
) -> None:
    env = _make_public_dispatch_env(tmp_path)
    selected_path = env.seed / "docs" / "tasks" / f"{_TASK_ID}.md"
    selected_path.write_bytes(b"nonterminal prefix\n\xff\xfe\n")
    _commit_and_push_main(
        env.seed,
        "make nonterminal task invalid utf8",
        f"docs/tasks/{_TASK_ID}.md",
    )
    agent_marker = env.work / "agent-was-called"
    gh_log = tmp_path / "gh-commands.jsonl"
    fail_if_invoked = (
        "import pathlib\n"
        f"pathlib.Path({str(agent_marker)!r}).write_text('called', encoding='utf-8')\n"
        "raise SystemExit(3)\n"
    )
    config = dataclasses.replace(
        _public_dispatch_config(env, selector=_TASK_ID),
        implementer_profiles=_profiles(
            _implementer_spec(env.work, fail_if_invoked)
        ),
        reviewer_profiles=_profiles(_reviewer_spec(env.work, fail_if_invoked)),
        gh_command=_public_dispatch_gh_command(_TASK_ID, command_log=gh_log),
    )

    result = run(config)

    assert result.outcome is RunOutcome.BLOCKED
    assert result.phase is Phase.PREFLIGHT
    assert result.delivery_branch is None
    assert "not valid UTF-8" in (result.blocked_reason or "")
    assert not agent_marker.exists()
    assert not gh_log.exists()
    assert _run_git(["branch", "--show-current"], cwd=env.work).strip() == "main"
    assert _run_git(
        ["branch", "--list", f"autonomous-pr/{_TASK_ID.lower()}"], cwd=env.work
    ) == ""


def test_public_run_reports_no_delivery_branch_when_branch_creation_fails(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_sha = "a" * 40
    target = _cp3_target(base_sha, _v2_spec())
    selected = _selected_from_target(target)
    config = _default_config(
        env,
        implementer_spec=_implementer_spec(env.work, "print('unused')"),
        reviewer_spec=_reviewer_spec(env.work, "print('unused')"),
    )
    monkeypatch.setattr(repository, "fetch_and_capture_origin_main_sha", lambda repo: base_sha)
    monkeypatch.setattr(repository, "is_worktree_clean", lambda repo: True)
    monkeypatch.setattr(
        orch_module, "_resolve_file_based_target", lambda *args: selected
    )

    def fail_branch(*args: object, **kwargs: object) -> None:
        raise repository.RepositoryError("branch creation failed")

    monkeypatch.setattr(repository, "create_delivery_branch_from_sha", fail_branch)

    result = run(config)

    assert result.outcome is RunOutcome.BLOCKED
    assert result.phase is Phase.DELIVERY_BRANCH_READY
    assert result.delivery_branch is None
    assert result.head_sha is None
    assert result.routing_decisions == ()


def test_public_run_reports_local_commit_head_when_push_fails(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_sha = "a" * 40
    committed_sha = "c" * 40
    spec = _v2_spec()
    target = _cp3_target(base_sha, spec)
    selected = _selected_from_target(target)
    candidate = _accepted_test_candidate(spec, base_sha)
    config = _default_config(
        env,
        implementer_spec=_implementer_spec(env.work, "print('unused')"),
        reviewer_spec=_reviewer_spec(env.work, "print('unused')"),
    )
    monkeypatch.setattr(repository, "fetch_and_capture_origin_main_sha", lambda repo: base_sha)
    monkeypatch.setattr(repository, "is_worktree_clean", lambda repo: True)
    monkeypatch.setattr(
        orch_module, "_resolve_file_based_target", lambda *args: selected
    )
    monkeypatch.setattr(repository, "create_delivery_branch_from_sha", lambda *args: None)
    monkeypatch.setattr(repository, "head_sha", lambda repo: base_sha)
    monkeypatch.setattr(repository, "changed_paths", lambda repo: ("candidate.txt",))
    monkeypatch.setattr(
        repository, "commit_reviewed_checkpoint", lambda *args, **kwargs: committed_sha
    )

    def fail_push(*args: object, **kwargs: object) -> None:
        raise repository.RepositoryError("push failed after local commit")

    monkeypatch.setattr(repository, "push_delivery_branch", fail_push)

    def checkpoint_with_failed_acceptance(*args: object, **kwargs: object) -> object:
        acceptor = kwargs["checkpoint_acceptor"]
        acceptor(candidate)
        raise AssertionError("push failure must stop checkpoint execution")

    monkeypatch.setattr(
        orch_module, "execute_v2_checkpoints", checkpoint_with_failed_acceptance
    )

    result = run(config)

    assert result.outcome is RunOutcome.BLOCKED
    assert result.delivery_branch == "delivery"
    assert result.head_sha == committed_sha
    assert "push failed after local commit" in (result.blocked_reason or "")


def test_checkpoint_acceptance_revalidates_changed_target_before_commit(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_sha, moved_sha = "a" * 40, "b" * 40
    spec = _v2_spec()
    target = _cp3_target(base_sha, spec)
    fetches = iter((base_sha, moved_sha))
    commits: list[str] = []
    pushes: list[str] = []
    config = _default_config(
        env,
        implementer_spec=_implementer_spec(env.work, "print('unused')"),
        reviewer_spec=_reviewer_spec(env.work, "print('unused')"),
    )
    monkeypatch.setattr(
        repository, "fetch_and_capture_origin_main_sha", lambda repo: next(fetches)
    )
    monkeypatch.setattr(repository, "is_worktree_clean", lambda repo: True)
    monkeypatch.setattr(
        orch_module,
        "_resolve_file_based_target",
        lambda *args: _selected_from_target(target),
    )
    monkeypatch.setattr(
        orch_module,
        "_revalidate_file_selected_target_at_sha",
        lambda *args: (_ for _ in ()).throw(
            orch_module._Blocked(
                "origin/main moved and changed the fixed selected task document"
            )
        ),
    )
    monkeypatch.setattr(repository, "create_delivery_branch_from_sha", lambda *args: None)
    monkeypatch.setattr(repository, "head_sha", lambda repo: base_sha)
    monkeypatch.setattr(
        repository,
        "commit_reviewed_checkpoint",
        lambda *args, **kwargs: commits.append("commit") or "c" * 40,
    )
    monkeypatch.setattr(
        repository,
        "push_delivery_branch",
        lambda *args, **kwargs: pushes.append("push"),
    )

    def invoke_acceptor(*args: object, **kwargs: object) -> object:
        kwargs["checkpoint_acceptor"](_accepted_test_candidate(spec, base_sha))
        raise AssertionError("changed execution target must block acceptance")

    monkeypatch.setattr(orch_module, "execute_v2_checkpoints", invoke_acceptor)

    result = run(config)

    assert result.outcome is RunOutcome.BLOCKED
    assert result.phase is Phase.ORIGIN_MAIN_REVALIDATION
    assert "changed the fixed selected task document" in (result.blocked_reason or "")
    assert commits == []
    assert pushes == []


def test_checkpoint_acceptance_allows_unrelated_origin_movement_after_revalidation(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_sha, moved_sha, committed_sha = "a" * 40, "b" * 40, "c" * 40
    spec = _v2_spec()
    target = _cp3_target(base_sha, spec)
    fetches = iter((base_sha, moved_sha))
    commits: list[str] = []
    pushes: list[str] = []
    config = _default_config(
        env,
        implementer_spec=_implementer_spec(env.work, "print('unused')"),
        reviewer_spec=_reviewer_spec(env.work, "print('unused')"),
    )
    monkeypatch.setattr(
        repository, "fetch_and_capture_origin_main_sha", lambda repo: next(fetches)
    )
    monkeypatch.setattr(repository, "is_worktree_clean", lambda repo: True)
    monkeypatch.setattr(
        orch_module,
        "_resolve_file_based_target",
        lambda *args: _selected_from_target(target),
    )
    monkeypatch.setattr(
        orch_module, "_revalidate_file_selected_target_at_sha", lambda *args: None
    )
    monkeypatch.setattr(repository, "create_delivery_branch_from_sha", lambda *args: None)
    monkeypatch.setattr(repository, "head_sha", lambda repo: base_sha)
    monkeypatch.setattr(repository, "changed_paths", lambda repo: ("candidate.txt",))
    monkeypatch.setattr(
        repository,
        "commit_reviewed_checkpoint",
        lambda *args, **kwargs: commits.append("commit") or committed_sha,
    )
    monkeypatch.setattr(
        repository,
        "push_delivery_branch",
        lambda *args, **kwargs: pushes.append("push"),
    )

    def invoke_acceptor(*args: object, **kwargs: object) -> object:
        kwargs["checkpoint_acceptor"](_accepted_test_candidate(spec, base_sha))
        return orch_module.V2CheckpointExecutionResult(
            completed=False,
            accepted_candidates=(),
            gate_histories=(),
            blocked_reason="intentional stop after acceptance",
        )

    monkeypatch.setattr(orch_module, "execute_v2_checkpoints", invoke_acceptor)

    result = run(config)

    assert result.outcome is RunOutcome.BLOCKED
    assert commits == ["commit"]
    assert pushes == ["push"]
    assert result.head_sha == committed_sha


def test_late_repair_acceptance_revalidates_target_before_commit(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_sha, moved_sha = "a" * 40, "b" * 40
    spec = _v2_spec()
    target = _cp3_target(base_sha, spec)
    fetches = iter((base_sha, moved_sha))
    commits: list[str] = []
    pushes: list[str] = []
    config = _default_config(
        env,
        implementer_spec=_implementer_spec(env.work, "print('unused')"),
        reviewer_spec=_reviewer_spec(env.work, "print('unused')"),
    )
    monkeypatch.setattr(
        repository, "fetch_and_capture_origin_main_sha", lambda repo: next(fetches)
    )
    monkeypatch.setattr(repository, "is_worktree_clean", lambda repo: True)
    monkeypatch.setattr(
        orch_module,
        "_resolve_file_based_target",
        lambda *args: _selected_from_target(target),
    )
    monkeypatch.setattr(
        orch_module,
        "_revalidate_file_selected_target_at_sha",
        lambda *args: (_ for _ in ()).throw(
            orch_module._Blocked(
                "origin/main moved and changed the fixed selected task document"
            )
        ),
    )
    monkeypatch.setattr(repository, "create_delivery_branch_from_sha", lambda *args: None)
    monkeypatch.setattr(repository, "head_sha", lambda repo: base_sha)
    monkeypatch.setattr(
        repository,
        "commit_reviewed_checkpoint",
        lambda *args, **kwargs: commits.append("commit") or "c" * 40,
    )
    monkeypatch.setattr(
        repository,
        "push_delivery_branch",
        lambda *args, **kwargs: pushes.append("push"),
    )
    monkeypatch.setattr(
        orch_module,
        "execute_v2_checkpoints",
        lambda *args, **kwargs: orch_module.V2CheckpointExecutionResult(
            completed=True, accepted_candidates=(), gate_histories=()
        ),
    )

    def invoke_repair_acceptor(*args: object, **kwargs: object) -> object:
        kwargs["repair_acceptor"](_accepted_test_repair_candidate(spec, base_sha))
        raise AssertionError("changed spec must block late repair acceptance")

    monkeypatch.setattr(
        orch_module, "execute_v2_pre_closure_review", invoke_repair_acceptor
    )

    result = run(config)

    assert result.outcome is RunOutcome.BLOCKED
    assert result.phase is Phase.ORIGIN_MAIN_REVALIDATION
    assert "changed the fixed selected task document" in (result.blocked_reason or "")
    assert commits == []
    assert pushes == []


def _v2_spec(checkpoint_count: int = 1) -> TaskExecutionSpec:
    checkpoints = tuple(
        ExecutionCheckpoint(
            number=number,
            checkpoint_id=f"CP-{number}",
            name=f"Checkpoint {number}",
            objective=f"Objective {number}",
            required_result=f"Required result {number}",
            constraints=f"Constraints {number}",
            verification=(_verify_true(),),
            review_focus=f"Review focus {number}",
        )
        for number in range(1, checkpoint_count + 1)
    )
    return TaskExecutionSpec(
        task_id=_TASK_ID,
        path=f"docs/tasks/{_TASK_ID}.md",
        title="V2 test task",
        goal="Goal",
        context_references="Context",
        scope="Scope",
        out_of_scope="Out of scope",
        approved_implementation_approach="Approach",
        acceptance_criteria="Acceptance",
        checkpoints=checkpoints,
        full_verification=(_verify_true(),),
        known_constraints="Constraints",
        text="# fixed spec\n",
        digest="fixed-spec-digest",
    )


def _accepted_test_candidate(
    spec: TaskExecutionSpec, base_sha: str
) -> orch_module.AcceptedCheckpointCandidate:
    checkpoint = spec.checkpoints[0]
    patch_text = "diff --git a/candidate.txt b/candidate.txt\n"
    patch = repository.ReviewPatch(
        purpose=repository.ReviewPurpose.CHECKPOINT,
        range_description="HEAD",
        base_sha=None,
        head_sha=base_sha,
        branch="delivery",
        diff_text=patch_text,
        digest="reviewed-patch-digest",
    )
    return orch_module.AcceptedCheckpointCandidate(
        checkpoint=checkpoint,
        gate_context=GateContext(
            gate_id=checkpoint.checkpoint_id,
            spec_identity=spec.digest,
            accepted_base_context_identity=base_sha,
        ),
        candidate_identity=CandidateIdentity("candidate-digest"),
        review_patch=patch,
        verification=_v2_verification(True),
        review_iteration=1,
    )


def _accepted_test_repair_candidate(
    spec: TaskExecutionSpec, base_sha: str
) -> orch_module.AcceptedImplementationRepairCandidate:
    checkpoint_candidate = _accepted_test_candidate(spec, base_sha)
    return orch_module.AcceptedImplementationRepairCandidate(
        gate_context=GateContext(
            gate_id="late-repair",
            spec_identity=spec.digest,
            accepted_base_context_identity=base_sha,
        ),
        candidate_identity=checkpoint_candidate.candidate_identity,
        review_patch=checkpoint_candidate.review_patch,
        verification=checkpoint_candidate.verification,
        review_iteration=1,
    )


def _v2_verification(passed: bool) -> VerificationEvidence:
    command = VerificationCommandResult(
        command=_verify_true(),
        returncode=0 if passed else 1,
        stdout="ok" if passed else "failed",
        stderr="",
        passed=passed,
    )
    return VerificationEvidence(commands=(command,), passed=passed, head_sha="head-sha")


def _finding(problem: str) -> RepairFinding:
    return RepairFinding(
        binding_basis="checkpoint:CP-1:required_result",
        problem=problem,
        evidence=f"evidence for {problem}",
        failure_mode=f"failure mode for {problem}",
        required_outcome=f"required outcome for {problem}",
        recommended_repair=f"repair for {problem}",
        verification_focus=f"verify {problem}",
    )


def _diagnosis() -> NonConvergenceDiagnosis:
    return NonConvergenceDiagnosis(
        previous_requirement="previous requirement",
        actual_change="actual change",
        why_unsatisfied="why unsatisfied",
        misunderstanding="misunderstanding",
        remaining_required_outcome="remaining outcome",
        recommended_corrective_approach="corrective approach",
    )


def _v2_approved() -> StructuredReviewResult:
    return StructuredReviewResult(
        verdict=ReviewVerdict.APPROVED,
        repair_packet=None,
        raw_output="APPROVED\n",
        verdict_is_explicit=True,
    )


def _v2_changes(problem: str, *, diagnosis: bool = False) -> StructuredReviewResult:
    packet = RepairPacket(
        findings=(_finding(problem),),
        non_convergence=_diagnosis() if diagnosis else None,
    )
    return StructuredReviewResult(
        verdict=ReviewVerdict.CHANGES_REQUESTED,
        repair_packet=packet,
        raw_output="CHANGES_REQUESTED\n{}\n",
        verdict_is_explicit=True,
    )


def _v2_blocked(reason: str) -> StructuredReviewResult:
    return StructuredReviewResult(
        verdict=ReviewVerdict.BLOCKED,
        repair_packet=None,
        raw_output="",
        blocked_reason=reason,
    )


def _v2_explicit_blocked(reason: str) -> StructuredReviewResult:
    return StructuredReviewResult(
        verdict=ReviewVerdict.BLOCKED,
        repair_packet=None,
        raw_output="BLOCKED\n",
        blocked_reason=reason,
        verdict_is_explicit=True,
    )


def _capture_recorded_review_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[GateContext, GateAttempt]]:
    captured: list[tuple[GateContext, GateAttempt]] = []
    real_record = orch_module._record_v2_interpreted_review_attempt

    def capture(
        history: GateHistory,
        review: StructuredReviewResult,
        **kwargs: object,
    ) -> int | None:
        iteration = real_record(history, review, **kwargs)
        if iteration is not None:
            captured.append((history.context, history.attempts[-1]))
        return iteration

    monkeypatch.setattr(orch_module, "_record_v2_interpreted_review_attempt", capture)
    return captured


def _v2_changes_for_bases(*bases: str) -> StructuredReviewResult:
    return StructuredReviewResult(
        verdict=ReviewVerdict.CHANGES_REQUESTED,
        repair_packet=RepairPacket(
            findings=tuple(
                dataclasses.replace(
                    _finding(f"problem-{index}"), binding_basis=basis
                )
                for index, basis in enumerate(bases, start=1)
            )
        ),
        raw_output="CHANGES_REQUESTED\n{}\n",
        verdict_is_explicit=True,
    )


def _record_metric_review(
    history: GateHistory, review: StructuredReviewResult, candidate: str
) -> None:
    iteration = orch_module._record_v2_interpreted_review_attempt(
        history,
        review,
        candidate_identity=CandidateIdentity(candidate),
        candidate_state=candidate,
        verification=None,
    )
    assert iteration is not None


@dataclass
class _V2Scenario:
    result: object
    implementer_prompts: list[str]
    reviewer_prompts: list[str]
    implementer_profiles: list[ComputeProfile]
    reviewer_profiles: list[ComputeProfile]


def _default_v2_checkpoint_acceptor(
    candidate: orch_module.AcceptedCheckpointCandidate,
) -> str:
    return f"accepted-{candidate.checkpoint.checkpoint_id}-{candidate.candidate_identity.digest}"


def _execute_v2_scenario(
    env: Env,
    monkeypatch: pytest.MonkeyPatch,
    *,
    candidates: list[str],
    verifications: list[VerificationEvidence],
    reviews: list[StructuredReviewResult],
    checkpoint_count: int = 1,
    checkpoint_acceptor: Callable[
        [orch_module.AcceptedCheckpointCandidate], str
    ]
    | None = _default_v2_checkpoint_acceptor,
    mutate_review_patch: bool = False,
) -> _V2Scenario:
    candidate_queue = list(candidates)
    verification_queue = list(verifications)
    review_queue = list(reviews)
    implementer_prompts: list[str] = []
    reviewer_prompts: list[str] = []
    implementer_profiles: list[ComputeProfile] = []
    reviewer_profiles: list[ComputeProfile] = []

    def fake_implementer(
        spec: AgentInvocationSpec, prompt_text: str
    ) -> AgentInvocationResult:
        assert spec.role is AgentRole.IMPLEMENTER
        implementer_profiles.append(ComputeProfile(spec.args[-1].upper()))
        implementer_prompts.append(prompt_text)
        return AgentInvocationResult(
            stdout="implemented", stderr="", returncode=0, timed_out=False
        )

    def fake_patch(repo_path: Path) -> repository.ReviewPatch:
        assert repo_path == env.work
        assert candidate_queue, "test scenario exhausted candidate states"
        diff = candidate_queue.pop(0)
        return repository.ReviewPatch(
            purpose=repository.ReviewPurpose.CHECKPOINT,
            range_description="HEAD",
            base_sha=None,
            head_sha=_run_git(["rev-parse", "HEAD"], cwd=env.work).strip(),
            branch=_run_git(["branch", "--show-current"], cwd=env.work).strip(),
            diff_text=diff,
            digest=f"patch-{len(implementer_prompts)}",
        )

    def fake_verification(
        config: OrchestratorConfig, commands: tuple[tuple[str, ...], ...]
    ) -> VerificationEvidence:
        assert commands == (_verify_true(),)
        assert verification_queue, "test scenario exhausted verification results"
        return verification_queue.pop(0)

    def fake_reviewer(
        spec: AgentInvocationSpec, review_input_text: str
    ) -> StructuredReviewResult:
        assert spec.role is AgentRole.REVIEWER
        reviewer_profiles.append(ComputeProfile(spec.args[-1].upper()))
        artifact = (env.work / "review.patch").read_text(encoding="utf-8")
        assert f"CURRENT_PATCH:\n{artifact}\n" in review_input_text
        if mutate_review_patch:
            (env.work / "review.patch").write_text(
                "mutated by reviewer\n", encoding="utf-8"
            )
        reviewer_prompts.append(review_input_text)
        assert review_queue, "test scenario exhausted review results"
        return review_queue.pop(0)

    monkeypatch.setattr(orch_module, "run_implementer", fake_implementer)
    monkeypatch.setattr(
        orch_module.repository, "build_checkpoint_patch_uncommitted", fake_patch
    )
    monkeypatch.setattr(orch_module.repository, "changed_paths", lambda repo: ())
    monkeypatch.setattr(orch_module, "_run_verification_commands", fake_verification)
    monkeypatch.setattr(orch_module, "run_structured_reviewer", fake_reviewer)

    config = _default_config(
        env,
        implementer_spec=_implementer_spec(env.work, "print('unused')"),
        reviewer_spec=_reviewer_spec(env.work, "print('unused')"),
        # Proves the v2 helper does not treat the retained v1 numeric setting
        # as a gate input: scenarios below exceed this value freely.
        max_repairs=0,
    )
    result = execute_v2_checkpoints(
        config,
        _v2_spec(checkpoint_count),
        accepted_base_context_identity="accepted-base",
        checkpoint_acceptor=checkpoint_acceptor,
    )
    assert not candidate_queue
    assert not verification_queue
    assert not review_queue
    return _V2Scenario(
        result,
        implementer_prompts,
        reviewer_prompts,
        implementer_profiles,
        reviewer_profiles,
    )


def test_v2_checkpoint_first_candidate_approved(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    scenario = _execute_v2_scenario(
        env,
        monkeypatch,
        candidates=["candidate-A"],
        verifications=[_v2_verification(True)],
        reviews=[_v2_approved()],
    )

    result = scenario.result
    assert isinstance(result, orch_module.V2CheckpointExecutionResult)
    assert result.completed
    assert result.blocked_reason is None
    assert len(result.accepted_candidates) == 1
    assert result.gate_histories[0].review_iteration == 1
    assert result.gate_histories[0].consecutive_changes_requested == 0
    assert "PREVIOUS_REVIEWER_FINDINGS:" not in scenario.reviewer_prompts[0]
    assert "REPAIR_DELTA_SINCE_LAST_REVIEWED_CANDIDATE:" not in scenario.reviewer_prompts[0]
    assert scenario.implementer_profiles == [ComputeProfile.ROUTINE]
    assert scenario.reviewer_profiles == [ComputeProfile.DELIBERATE]


def test_v2_checkpoint_review_blocks_if_reviewer_mutates_review_patch(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario = _execute_v2_scenario(
        env,
        monkeypatch,
        candidates=["candidate-A"],
        verifications=[_v2_verification(True)],
        reviews=[_v2_approved()],
        mutate_review_patch=True,
    )

    result = scenario.result
    assert isinstance(result, orch_module.V2CheckpointExecutionResult)
    assert not result.completed
    assert "no longer byte-identical" in (result.blocked_reason or "")


def test_v2_multiple_checkpoints_block_without_acceptance_boundary(env: Env) -> None:
    config = _default_config(
        env,
        implementer_spec=_implementer_spec(env.work, "raise AssertionError('unused')"),
        reviewer_spec=_reviewer_spec(env.work, "raise AssertionError('unused')"),
        max_repairs=0,
    )

    result = execute_v2_checkpoints(
        config,
        _v2_spec(checkpoint_count=2),
        accepted_base_context_identity="accepted-base",
        checkpoint_acceptor=None,
    )

    assert not result.completed
    assert result.accepted_candidates == ()
    assert result.gate_histories == ()
    assert "checkpoint acceptor" in (result.blocked_reason or "")
    assert "committed and pushed" in (result.blocked_reason or "")


def test_v2_checkpoint_one_change_then_approved_has_bounded_fresh_handoff(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario = _execute_v2_scenario(
        env,
        monkeypatch,
        candidates=["candidate-A", "candidate-B"],
        verifications=[_v2_verification(True), _v2_verification(True)],
        reviews=[_v2_changes("problem-1"), _v2_approved()],
    )

    result = scenario.result
    assert isinstance(result, orch_module.V2CheckpointExecutionResult)
    assert result.completed
    assert len(scenario.reviewer_prompts) == 2
    assert "PREVIOUS_REVIEWER_FINDINGS:" not in scenario.reviewer_prompts[0]
    assert "problem-1" in scenario.reviewer_prompts[1]
    assert "REPAIR_DELTA_SINCE_LAST_REVIEWED_CANDIDATE:" in scenario.reviewer_prompts[1]
    assert "CURRENT_REPAIR_PACKET:" in scenario.implementer_prompts[1]
    assert "problem-1" in scenario.implementer_prompts[1]
    assert scenario.implementer_profiles == [
        ComputeProfile.ROUTINE,
        ComputeProfile.DELIBERATE,
    ]
    assert scenario.reviewer_profiles == [
        ComputeProfile.DELIBERATE,
        ComputeProfile.CRITICAL,
    ]


def test_v2_checkpoint_repeated_basis_routes_next_repair_critical(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario = _execute_v2_scenario(
        env,
        monkeypatch,
        candidates=["A", "B", "C"],
        verifications=[_v2_verification(True)] * 3,
        reviews=[
            _v2_changes("first"),
            _v2_changes("same basis", diagnosis=True),
            _v2_approved(),
        ],
    )

    assert scenario.result.completed
    assert scenario.implementer_profiles == [
        ComputeProfile.ROUTINE,
        ComputeProfile.DELIBERATE,
        ComputeProfile.CRITICAL,
    ]


def test_v2_checkpoint_second_verification_rejection_routes_repair_critical(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario = _execute_v2_scenario(
        env,
        monkeypatch,
        candidates=["A", "B", "C"],
        verifications=[
            _v2_verification(False),
            _v2_verification(False),
            _v2_verification(True),
        ],
        reviews=[_v2_approved()],
    )

    assert scenario.result.completed
    assert scenario.implementer_profiles == [
        ComputeProfile.ROUTINE,
        ComputeProfile.DELIBERATE,
        ComputeProfile.CRITICAL,
    ]
    assert scenario.reviewer_profiles == [ComputeProfile.DELIBERATE]


def test_v2_next_checkpoint_restarts_at_routine_after_critical_episode(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario = _execute_v2_scenario(
        env,
        monkeypatch,
        candidates=["A", "B", "C", "D"],
        verifications=[_v2_verification(True)] * 4,
        reviews=[
            _v2_changes("first"),
            _v2_changes("same basis", diagnosis=True),
            _v2_approved(),
            _v2_approved(),
        ],
        checkpoint_count=2,
    )

    assert scenario.result.completed
    assert scenario.implementer_profiles == [
        ComputeProfile.ROUTINE,
        ComputeProfile.DELIBERATE,
        ComputeProfile.CRITICAL,
        ComputeProfile.ROUTINE,
    ]
    assert scenario.reviewer_profiles[-1] is ComputeProfile.DELIBERATE


def test_v2_reviewer_handoff_declares_complete_structured_output_contract(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario = _execute_v2_scenario(
        env,
        monkeypatch,
        candidates=["A", "B"],
        verifications=[_v2_verification(True), _v2_verification(True)],
        reviews=[_v2_changes("first"), _v2_approved()],
    )

    first, second = scenario.reviewer_prompts
    assert "non_convergence_required: false" in first
    assert "non_convergence_required: true" in second
    for field in (
        "binding_basis",
        "problem",
        "evidence",
        "failure_mode",
        "required_outcome",
        "recommended_repair",
        "verification_focus",
    ):
        assert field in first
    for binding_basis_fragment in (
        "task:approved_implementation_approach",
        "checkpoint:CP-N:<field>",
        "objective, required_result, constraints, verification",
        "repo:<non-empty trimmed reference>",
        "Review focus is advisory",
        "recommended_repair is required but advisory",
    ):
        assert binding_basis_fragment in first
    for field in (
        "previous_requirement",
        "actual_change",
        "why_unsatisfied",
        "misunderstanding",
        "remaining_required_outcome",
        "recommended_corrective_approach",
    ):
        assert field in second


def test_v2_designated_review_builders_declare_material_pass_and_applicability() -> None:
    spec = _v2_spec(checkpoint_count=2)
    verification = dataclasses.replace(_v2_verification(True), head_sha="h" * 40)
    patch = repository.ReviewPatch(
        purpose=repository.ReviewPurpose.PRE_CLOSURE_CUMULATIVE_REVIEW,
        range_description="origin/main...HEAD",
        base_sha="b" * 40,
        head_sha="h" * 40,
        branch="delivery",
        diff_text="current diff",
        digest="patch-digest",
    )
    previous_packet = RepairPacket(findings=(_finding("previous defect"),))
    history = GateHistory(
        context=GateContext(
            gate_id="test-gate",
            spec_identity=spec.digest,
            accepted_base_context_identity="b" * 40,
        ),
        review_iteration=1,
        consecutive_changes_requested=1,
        latest_valid_repair_packet=previous_packet,
        previous_reviewed_candidate_state="previous diff",
    )
    full_verification = orch_module.V2FullVerificationEvidence(
        spec_identity=spec.digest,
        base_identity="b" * 40,
        candidate_identity=CandidateIdentity("candidate"),
        head_sha="h" * 40,
        verification=verification,
    )
    execution_target = _cp3_target("b" * 40, spec)
    candidate = repository.UnpublishedCommitCandidate(
        branch="delivery",
        published_predecessor_sha="h" * 40,
        candidate_head_sha="c" * 40,
        tree_sha="t" * 40,
    )

    checkpoint_prompt = orch_module._build_v2_reviewer_input(
        spec,
        spec.checkpoints[0],
        "current diff",
        verification,
        review_iteration=2,
        previous_packet=previous_packet,
        repair_delta="repair delta",
        require_non_convergence=True,
    )
    cumulative_prompt = orch_module._build_v2_cumulative_review_input(
        spec, patch, full_verification, history
    )
    late_repair_prompt = orch_module._build_v2_late_repair_review_input(
        spec, "late-repair", patch, verification, history
    )
    closure_prompt = orch_module._build_v2_closure_review_input(
        execution_target, "closure diff", history
    )
    mode_c_prompt = orch_module._build_v2_mode_c_review_input(
        execution_target, candidate, patch, history
    )

    prompts = (
        checkpoint_prompt,
        cumulative_prompt,
        late_repair_prompt,
        closure_prompt,
        mode_c_prompt,
    )
    for prompt in prompts:
        assert "determine the binding requirements applicable to this gate" in prompt
        assert "complete current review artifact" in prompt
        assert "all supplied deterministic evidence" in prompt
        assert "first re-evaluate the previous reviewer findings" in prompt
        assert "fresh material pass over every remaining applicable" in prompt
        assert "all independent material defects" in prompt
        assert "only when it has a concrete binding_basis" in prompt
        assert "advisory Review focus are non-blocking" in prompt
        assert "APPROVED: the applicable material pass is complete" in prompt
        assert "CHANGES_REQUESTED: one or more proven repairable" in prompt
        assert "BLOCKED: correct continuation requires a missing decision" in prompt
        assert "PRE_RETURN_CONFORMANCE_PASS:" not in prompt
        assert "self-review artifact" not in prompt

    assert "GATE_APPLICABILITY: ORDINARY_CHECKPOINT" in checkpoint_prompt
    assert "task:goal, task:scope, task:out_of_scope" in checkpoint_prompt
    assert "checkpoint:CP-1:objective" in checkpoint_prompt
    assert "checkpoint:CP-1:verification" in checkpoint_prompt
    assert "checkpoint:CP-2:required_result" not in checkpoint_prompt
    assert (
        "task:acceptance_criteria and task:full_verification are not independent"
        in checkpoint_prompt
    )
    assert "do not demand future-checkpoint results early" in checkpoint_prompt

    assert (
        "GATE_APPLICABILITY: PRE_CLOSURE_CUMULATIVE_IMPLEMENTATION_REVIEW"
        in cumulative_prompt
    )
    assert "every binding Task Execution Spec section" in cumulative_prompt
    assert "every declared checkpoint objective" in cumulative_prompt
    assert "Full verification" in cumulative_prompt
    assert "complete origin/main...HEAD implementation diff" in cumulative_prompt

    assert "GATE_APPLICABILITY: LATE_IMPLEMENTATION_REPAIR" in late_repair_prompt
    assert "First review the original/current repair findings" in late_repair_prompt
    assert "required_outcome values" in late_repair_prompt
    assert "task-wide binding boundaries" in late_repair_prompt
    assert "does not replace required downstream checkpoint/evidence replay" in late_repair_prompt

    assert "GATE_APPLICABILITY: PROSPECTIVE_TASK_CLOSURE" in closure_prompt
    assert "exact closure candidate diff" in closure_prompt
    assert "factual closure evidence" in closure_prompt
    assert "terminal-registry" in closure_prompt
    assert "Do not repeat the full implementation review" in closure_prompt

    assert "GATE_APPLICABILITY: MODE_C_FINAL_CUMULATIVE_AUDIT" in mode_c_prompt
    assert "implementation plus the unpublished Task Closure" in mode_c_prompt
    assert "complete applicable Task Execution Spec" in mode_c_prompt
    assert "every checkpoint, Full verification" in mode_c_prompt
    assert "closure/governance boundaries" in mode_c_prompt


def test_v2_candidate_changing_handoffs_require_internal_conformance_pass() -> None:
    spec = _v2_spec()
    checkpoint = spec.checkpoints[0]
    packet = RepairPacket(findings=(_finding("binding defect"),))
    patch = repository.ReviewPatch(
        purpose=repository.ReviewPurpose.PRE_CLOSURE_CUMULATIVE_REVIEW,
        range_description="origin/main...HEAD",
        base_sha="b" * 40,
        head_sha="h" * 40,
        branch="delivery",
        diff_text="implementation diff",
        digest="implementation-patch",
    )
    cumulative = orch_module.V2CumulativeReviewEvidence(
        spec_identity=spec.digest,
        base_identity="b" * 40,
        candidate_identity=CandidateIdentity("implementation"),
        reviewed_head_sha="h" * 40,
        review_patch=patch,
        review_iteration=1,
    )
    pre_closure = orch_module.V2PreClosureExecutionResult(
        completed=True,
        evidence=orch_module.V2ImplementationEvidence(
            spec_identity=spec.digest,
            base_identity="b" * 40,
            accepted_checkpoints=[],
            cumulative_review=cumulative,
        ),
        cumulative_history=GateHistory(
            context=GateContext(
                gate_id="pre-closure-cumulative-review",
                spec_identity=spec.digest,
                accepted_base_context_identity="b" * 40,
            )
        ),
        replay_histories=(),
    )
    target = _cp3_target("b" * 40, spec)

    initial_checkpoint = orch_module._build_v2_implementer_prompt(
        spec, checkpoint, None, None, "repository facts"
    )
    checkpoint_repair = orch_module._build_v2_implementer_prompt(
        spec,
        checkpoint,
        packet,
        "deterministic checkpoint verification failed",
        "repository facts",
    )
    late_repair = orch_module._build_v2_late_repair_prompt(
        spec,
        "late-repair",
        packet,
        "deterministic late verification failed",
        "repository facts",
    )
    initial_closure = orch_module._build_v2_closure_prompt(
        target, pre_closure, "108", None, None
    )
    closure_repair = orch_module._build_v2_closure_prompt(
        target, pre_closure, "108", None, packet
    )

    for prompt in (
        initial_checkpoint,
        checkpoint_repair,
        late_repair,
        initial_closure,
        closure_repair,
    ):
        assert "PRE_RETURN_CONFORMANCE_PASS:" in prompt
        assert "Correct every violation you find before returning" in prompt
        assert "do not create a separate self-review artifact" in prompt
        assert "verdict, confidence claim, or reviewer anchoring statement" in prompt

    for prompt in (initial_checkpoint, checkpoint_repair):
        assert "task-wide Scope, Out of scope, and Approved implementation" in prompt
        assert "current checkpoint Required result and Constraints" in prompt
        assert "negative and fail-closed cases" in prompt
        assert "deterministic verification failure evidence when present" in prompt
    assert "binding defect" not in initial_checkpoint
    assert "binding defect" in checkpoint_repair
    assert "required outcome for binding defect" in checkpoint_repair
    assert "deterministic checkpoint verification failed" in checkpoint_repair

    assert "each current binding finding and its required_outcome" in late_repair
    assert "deterministic late verification failed" in late_repair
    assert "applicable existing repository constraints" in late_repair
    assert "recommended_repair is an advisory implementation suggestion" in late_repair
    assert "binding_basis and required_outcome are the actual repair target" in late_repair

    for prompt in (initial_closure, closure_repair):
        assert "canonical closure content, factual evidence" in prompt
        assert "terminal-registry and governance boundaries" in prompt
        assert "allowed closure files and content" in prompt
        assert "Do not re-review the implementation" in prompt
        assert "task-wide Scope" not in prompt
    assert "binding defect" not in initial_closure
    assert "binding defect" in closure_repair


def test_v2_checkpoint_distinct_candidates_continue_without_numeric_limit(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario = _execute_v2_scenario(
        env,
        monkeypatch,
        candidates=["A", "B", "C", "D", "E"],
        verifications=[_v2_verification(True)] * 5,
        reviews=[
            _v2_changes("problem-1"),
            _v2_changes("problem-2", diagnosis=True),
            _v2_changes("problem-3", diagnosis=True),
            _v2_changes("problem-4", diagnosis=True),
            _v2_approved(),
        ],
    )

    result = scenario.result
    assert isinstance(result, orch_module.V2CheckpointExecutionResult)
    assert result.completed
    assert result.gate_histories[0].review_iteration == 5
    assert len(result.gate_histories[0].attempts) == 5
    # The third fresh reviewer gets only the latest previous findings, not
    # the gate's full first+second review history.
    assert "problem-2" in scenario.reviewer_prompts[2]
    assert "problem-1" not in scenario.reviewer_prompts[2]
    previous_findings = scenario.reviewer_prompts[2].split(
        "PREVIOUS_REVIEWER_FINDINGS:\n", 1
    )[1].split("REPAIR_DELTA_SINCE_LAST_REVIEWED_CANDIDATE:\n", 1)[0]
    assert "non_convergence" not in previous_findings
    assert "previous requirement" not in previous_findings
    assert (
        result.gate_histories[0].attempts[1].repair_packet is not None
    )
    assert (
        result.gate_histories[0].attempts[1].repair_packet.non_convergence
        is not None
    )


def test_v2_checkpoint_malformed_repair_output_is_terminal_blocked(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario = _execute_v2_scenario(
        env,
        monkeypatch,
        candidates=["A"],
        verifications=[_v2_verification(True)],
        reviews=[_v2_blocked("malformed CHANGES_REQUESTED repair packet")],
    )

    result = scenario.result
    assert isinstance(result, orch_module.V2CheckpointExecutionResult)
    assert not result.completed
    assert "malformed" in (result.blocked_reason or "")
    assert result.gate_histories[0].review_iteration == 0
    assert result.gate_histories[0].attempts[0].review_iteration is None
    assert result.gate_histories[0].attempts[0].reviewer_verdict is None


def test_v2_review_gate_metrics_are_pure_deterministic_history_derivatives() -> None:
    basis_a = "task:scope"
    basis_b = "repo:AGENTS.md review authority"

    def history(gate_id: str = "shared-gate") -> GateHistory:
        return GateHistory(
            context=GateContext(
                gate_id=gate_id,
                spec_identity="spec",
                accepted_base_context_identity="base",
            )
        )

    cr_then_approved = history()
    _record_metric_review(
        cr_then_approved, _v2_changes_for_bases(basis_a), "candidate-1"
    )
    _record_metric_review(cr_then_approved, _v2_approved(), "candidate-2")
    first = orch_module._summarize_v2_gate_history(cr_then_approved)
    assert first.review_iterations == 2
    assert first.changes_requested_count == 1
    assert first.findings_per_review == (1, 0)
    assert first.binding_bases_per_review == ((basis_a,), ())
    assert first.new_binding_bases_after_first_review == ()
    assert first.repeated_binding_bases == ()
    assert first.last_reviewer_verdict is ReviewVerdict.APPROVED

    repeated = history()
    _record_metric_review(repeated, _v2_changes_for_bases(basis_a), "candidate-1")
    _record_metric_review(repeated, _v2_changes_for_bases(basis_a), "candidate-2")
    _record_metric_review(repeated, _v2_approved(), "candidate-3")
    repeated_metric = orch_module._summarize_v2_gate_history(repeated)
    assert repeated_metric.changes_requested_count == 2
    assert repeated_metric.repeated_binding_bases == (basis_a,)
    assert repeated_metric.new_binding_bases_after_first_review == ()

    late_basis = history()
    _record_metric_review(late_basis, _v2_changes_for_bases(basis_a), "candidate-1")
    _record_metric_review(late_basis, _v2_changes_for_bases(basis_b), "candidate-2")
    _record_metric_review(late_basis, _v2_approved(), "candidate-3")
    late_metric = orch_module._summarize_v2_gate_history(late_basis)
    assert late_metric.new_binding_bases_after_first_review == (basis_b,)
    assert late_metric.repeated_binding_bases == ()

    verification_then_review = history("verification-gate")
    verification_then_review.attempts.append(
        GateAttempt(
            candidate_identity=CandidateIdentity("verification-failure"),
            candidate_state="verification-failure",
            verification=_v2_verification(False),
            rejected=True,
            rejection_basis=CandidateRejectionBasis.VERIFICATION_FAILURE,
            review_iteration=None,
            reviewer_verdict=None,
        )
    )
    _record_metric_review(
        verification_then_review,
        _v2_changes_for_bases(basis_a),
        "reviewed-candidate",
    )
    verification_metric = orch_module._summarize_v2_gate_history(
        verification_then_review
    )
    assert verification_metric.review_iterations == 1
    assert verification_metric.verification_rejection_count == 1

    blocked = history("blocked-gate")
    _record_metric_review(blocked, _v2_changes_for_bases(basis_a), "candidate-1")
    _record_metric_review(
        blocked, _v2_explicit_blocked("missing decision"), "candidate-2"
    )
    blocked_metric = orch_module._summarize_v2_gate_history(blocked)
    assert blocked_metric.findings_per_review == (1, 0)
    assert blocked_metric.last_reviewer_verdict is ReviewVerdict.BLOCKED

    duplicate_in_one_packet = history("duplicate-basis-packet")
    _record_metric_review(
        duplicate_in_one_packet,
        _v2_changes_for_bases(basis_a, basis_a),
        "candidate-1",
    )
    duplicate_metric = orch_module._summarize_v2_gate_history(
        duplicate_in_one_packet
    )
    assert duplicate_metric.repeated_binding_bases == ()

    same_id_metrics = orch_module._summarize_v2_review_histories(
        [cr_then_approved, repeated]
    )
    assert len(same_id_metrics) == 2
    assert [metric.gate_id for metric in same_id_metrics] == [
        "shared-gate",
        "shared-gate",
    ]
    assert orch_module._summarize_v2_review_histories([history("no-review")]) == ()


def test_v2_checkpoint_second_change_requires_non_convergence_diagnosis(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario = _execute_v2_scenario(
        env,
        monkeypatch,
        candidates=["A", "B"],
        verifications=[_v2_verification(True), _v2_verification(True)],
        reviews=[_v2_changes("first"), _v2_changes("second")],
    )

    result = scenario.result
    assert isinstance(result, orch_module.V2CheckpointExecutionResult)
    assert not result.completed
    assert "non_convergence" in (result.blocked_reason or "")
    assert result.gate_histories[0].review_iteration == 2
    assert result.gate_histories[0].consecutive_changes_requested == 2


def test_v2_checkpoint_second_change_with_diagnosis_continues(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario = _execute_v2_scenario(
        env,
        monkeypatch,
        candidates=["A", "B", "C"],
        verifications=[_v2_verification(True)] * 3,
        reviews=[
            _v2_changes("first"),
            _v2_changes("second", diagnosis=True),
            _v2_approved(),
        ],
    )

    result = scenario.result
    assert isinstance(result, orch_module.V2CheckpointExecutionResult)
    assert result.completed
    assert result.gate_histories[0].review_iteration == 3


def test_v2_verification_failure_is_not_reviewed_and_does_not_advance_counters(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario = _execute_v2_scenario(
        env,
        monkeypatch,
        candidates=["A", "B"],
        verifications=[_v2_verification(False), _v2_verification(True)],
        reviews=[_v2_approved()],
    )

    result = scenario.result
    assert isinstance(result, orch_module.V2CheckpointExecutionResult)
    assert result.completed
    history = result.gate_histories[0]
    assert len(scenario.reviewer_prompts) == 1
    assert history.review_iteration == 1
    assert history.consecutive_changes_requested == 0
    assert history.attempts[0].review_iteration is None
    assert history.attempts[0].reviewer_verdict is None
    assert (
        history.attempts[0].rejection_basis
        is CandidateRejectionBasis.VERIFICATION_FAILURE
    )
    assert "CURRENT_VERIFICATION_FAILURE:" in scenario.implementer_prompts[1]
    assert "passed: False" in scenario.implementer_prompts[1]


def test_v2_verification_rejected_identity_repeated_by_repair_is_blocked(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario = _execute_v2_scenario(
        env,
        monkeypatch,
        candidates=["A", "A"],
        verifications=[_v2_verification(False)],
        reviews=[],
    )

    result = scenario.result
    assert isinstance(result, orch_module.V2CheckpointExecutionResult)
    assert not result.completed
    assert len(scenario.reviewer_prompts) == 0
    assert result.gate_histories[0].review_iteration == 0
    assert "repeats a previously rejected identity" in (result.blocked_reason or "")


@pytest.mark.parametrize(
    ("candidates", "verifications", "reviews"),
    [
        (
            ["A", "A"],
            [_v2_verification(True)],
            [_v2_changes("first")],
        ),
        (
            ["A", "B", "C", "B"],
            [_v2_verification(True)] * 3,
            [
                _v2_changes("first"),
                _v2_changes("second", diagnosis=True),
                _v2_changes("third", diagnosis=True),
            ],
        ),
    ],
)
def test_v2_repeated_rejected_identity_blocks_no_progress_or_cycle(
    env: Env,
    monkeypatch: pytest.MonkeyPatch,
    candidates: list[str],
    verifications: list[VerificationEvidence],
    reviews: list[StructuredReviewResult],
) -> None:
    scenario = _execute_v2_scenario(
        env,
        monkeypatch,
        candidates=candidates,
        verifications=verifications,
        reviews=reviews,
    )

    result = scenario.result
    assert isinstance(result, orch_module.V2CheckpointExecutionResult)
    assert not result.completed
    assert "repeats a previously rejected identity" in (result.blocked_reason or "")
    history = result.gate_histories[0]
    assert history.attempts[-1].verification is None
    assert (
        history.attempts[-1].rejection_basis
        is CandidateRejectionBasis.REPEATED_IDENTITY
    )


def test_v2_checkpoints_execute_exactly_in_declared_order_and_reset_gate_state(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    accepted_in_order: list[str] = []

    def accept_checkpoint(candidate: orch_module.AcceptedCheckpointCandidate) -> str:
        accepted_in_order.append(candidate.checkpoint.checkpoint_id)
        return f"accepted-base-{candidate.checkpoint.checkpoint_id}"

    scenario = _execute_v2_scenario(
        env,
        monkeypatch,
        candidates=["CP1-A", "CP1-B", "CP2-A"],
        verifications=[_v2_verification(True)] * 3,
        reviews=[_v2_changes("cp1 repair"), _v2_approved(), _v2_approved()],
        checkpoint_count=2,
        checkpoint_acceptor=accept_checkpoint,
    )

    result = scenario.result
    assert isinstance(result, orch_module.V2CheckpointExecutionResult)
    assert result.completed
    assert [item.checkpoint.checkpoint_id for item in result.accepted_candidates] == [
        "CP-1",
        "CP-2",
    ]
    assert accepted_in_order == ["CP-1", "CP-2"]
    assert [history.review_iteration for history in result.gate_histories] == [2, 1]
    assert result.gate_histories[1].consecutive_changes_requested == 0
    assert (
        result.accepted_candidates[1].gate_context.accepted_base_context_identity
        == "accepted-base-CP-1"
    )


def test_v2_next_checkpoint_handoff_uses_head_created_by_previous_acceptance(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial_head = _run_git(["rev-parse", "HEAD"], cwd=env.work).strip()
    accepted_heads: list[str] = []

    def commit_checkpoint(candidate: orch_module.AcceptedCheckpointCandidate) -> str:
        _run_git(
            [
                "commit",
                "--allow-empty",
                "-m",
                f"accept {candidate.checkpoint.checkpoint_id}",
            ],
            cwd=env.work,
        )
        accepted_head = _run_git(["rev-parse", "HEAD"], cwd=env.work).strip()
        accepted_heads.append(accepted_head)
        return accepted_head

    scenario = _execute_v2_scenario(
        env,
        monkeypatch,
        candidates=["CP1", "CP2"],
        verifications=[_v2_verification(True), _v2_verification(True)],
        reviews=[_v2_approved(), _v2_approved()],
        checkpoint_count=2,
        checkpoint_acceptor=commit_checkpoint,
    )

    result = scenario.result
    assert isinstance(result, orch_module.V2CheckpointExecutionResult)
    assert result.completed
    assert len(accepted_heads) == 2
    first_context = scenario.implementer_prompts[0].split(
        "REPOSITORY_CONTEXT:\n", 1
    )[1]
    second_context = scenario.implementer_prompts[1].split(
        "REPOSITORY_CONTEXT:\n", 1
    )[1]
    assert f"head_sha: {initial_head}" in first_context
    assert f"head_sha: {accepted_heads[0]}" in second_context
    assert f"head_sha: {initial_head}" not in second_context
    assert (
        f"accepted_base_context_identity: {accepted_heads[0]}" in second_context
    )


def test_v2_checkpoint_execution_creates_no_persisted_run_state(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = {path.relative_to(env.work) for path in env.work.rglob("*")}
    scenario = _execute_v2_scenario(
        env,
        monkeypatch,
        candidates=["A"],
        verifications=[_v2_verification(True)],
        reviews=[_v2_approved()],
    )
    after = {path.relative_to(env.work) for path in env.work.rglob("*")}

    result = scenario.result
    assert isinstance(result, orch_module.V2CheckpointExecutionResult)
    assert result.completed
    assert after == before | {Path("review.patch")}
    assert (env.work / "review.patch").read_text(encoding="utf-8") == "A"
    assert not any(path.name == "run.json" for path in env.work.rglob("*"))


# --- TSK-0028 CP-3: late repair invalidation and conservative replay ----------


def _prepared_v2_checkpoint_result(
    env: Env, spec: TaskExecutionSpec
) -> tuple[str, object]:
    base_sha = _run_git(["rev-parse", "origin/main"], cwd=env.work).strip()
    _run_git(["checkout", "-q", "-b", "delivery"], cwd=env.work)
    evidence: list[orch_module.AcceptedCheckpointEvidence] = []
    candidates: list[orch_module.AcceptedCheckpointCandidate] = []
    predecessor = base_sha
    for checkpoint in spec.checkpoints:
        path = env.work / f"cp_{checkpoint.number}.txt"
        path.write_text(f"accepted {checkpoint.checkpoint_id}\n", encoding="utf-8")
        _run_git(["add", path.name], cwd=env.work)
        _run_git(["commit", "-q", "-m", f"accept {checkpoint.checkpoint_id}"], cwd=env.work)
        accepted_head = _run_git(["rev-parse", "HEAD"], cwd=env.work).strip()
        diff = _run_git(["diff", f"{predecessor}..{accepted_head}"], cwd=env.work)
        patch = repository.ReviewPatch(
            purpose=repository.ReviewPurpose.CHECKPOINT,
            range_description=f"{predecessor}..{accepted_head}",
            base_sha=predecessor,
            head_sha=predecessor,
            branch="delivery",
            diff_text=diff,
            digest=f"accepted-{checkpoint.number}",
        )
        candidate = orch_module.AcceptedCheckpointCandidate(
            checkpoint=checkpoint,
            gate_context=GateContext(
                gate_id=checkpoint.checkpoint_id,
                spec_identity=spec.digest,
                accepted_base_context_identity=predecessor,
            ),
            candidate_identity=orch_module._candidate_identity(diff),
            review_patch=patch,
            verification=_v2_verification(True),
            review_iteration=1,
        )
        candidates.append(candidate)
        evidence.append(
            orch_module.AcceptedCheckpointEvidence(
                candidate=candidate,
                predecessor_review_boundary_sha=predecessor,
                accepted_head_sha=accepted_head,
                accepted_base_context_identity=accepted_head,
            )
        )
        predecessor = accepted_head
    return base_sha, orch_module.V2CheckpointExecutionResult(
        completed=True,
        accepted_candidates=tuple(candidates),
        gate_histories=(),
        checkpoint_evidence=tuple(evidence),
    )


def _cp3_spec() -> TaskExecutionSpec:
    spec = _v2_spec(checkpoint_count=2)
    return dataclasses.replace(
        spec,
        full_verification=(
            (sys.executable, "-c", "print('FULL_VERIFICATION_ONLY')"),
        ),
    )


def _cp3_target(base_sha: str, spec: TaskExecutionSpec) -> ExecutionTarget:
    legacy_target = ExecutionTarget(
        base_sha=base_sha,
        task=TrackerTask(
            task_id=spec.task_id,
            priority="P2",
            size="M",
            group="engineering",
            roadmap_target="Test roadmap target",
            depends_on=("TSK-9000",),
            title="Test task",
        ),
        spec=spec,
    )
    return orch_module._execution_target_from_selection(
        _selected_from_target(legacy_target)
    )


def _selected_from_target(
    target: ExecutionTarget,
    *,
    mode: TaskSelectionMode = TaskSelectionMode.EXPLICIT,
) -> SelectedTask:
    metadata = TaskMetadata(
        execution_approval=ExecutionApproval.APPROVED,
        priority=target.task.priority,
        size=target.task.size,
        roadmap_target=target.task.roadmap_target,
        depends_on=target.task.depends_on,
        group=target.task.group,
    )
    document = ApprovedTaskDocument(
        task_id=target.task.task_id,
        path=target.spec.path,
        title=target.task.title,
        metadata=metadata,
        execution_spec=target.spec,
        text=target.spec.text,
        digest=target.spec.digest,
    )
    return SelectedTask(
        source_sha=target.base_sha,
        mode=mode,
        document=document,
        basis=(
            f"explicit selector {target.task.task_id}"
            if mode is TaskSelectionMode.EXPLICIT
            else "highest eligible priority P2, then numeric task ID 9001"
        ),
    )


def _changes_with_paths(
    problem: str,
    paths: tuple[str, ...],
    *,
    diagnosis: bool = False,
    binding_basis: str | None = None,
) -> StructuredReviewResult:
    finding = dataclasses.replace(_finding(problem), affected_paths=paths)
    if binding_basis is not None:
        finding = dataclasses.replace(finding, binding_basis=binding_basis)
    return StructuredReviewResult(
        verdict=ReviewVerdict.CHANGES_REQUESTED,
        repair_packet=RepairPacket(
            findings=(finding,),
            non_convergence=_diagnosis() if diagnosis else None,
        ),
        raw_output="CHANGES_REQUESTED\n{}\n",
        verdict_is_explicit=True,
    )


def _install_cp3_reviewer_sequence(
    env: Env,
    monkeypatch: pytest.MonkeyPatch,
    reviews: list[StructuredReviewResult],
    *,
    implementer_profiles: list[ComputeProfile] | None = None,
    reviewer_profiles: list[ComputeProfile] | None = None,
) -> tuple[list[str], list[str], list[tuple[tuple[str, ...], ...]], list[str]]:
    review_queue = list(reviews)
    reviewer_prompts: list[str] = []
    implementer_prompts: list[str] = []
    verification_commands: list[tuple[tuple[str, ...], ...]] = []
    committed_ranges: list[str] = []
    repair_number = 0

    def fake_implementer(
        spec: AgentInvocationSpec, prompt_text: str
    ) -> AgentInvocationResult:
        nonlocal repair_number
        repair_number += 1
        if implementer_profiles is not None:
            implementer_profiles.append(ComputeProfile(spec.args[-1].upper()))
        implementer_prompts.append(prompt_text)
        (env.work / "late_repair.txt").write_text(
            f"repair {repair_number}\n", encoding="utf-8"
        )
        return AgentInvocationResult("repaired", "", 0, False)

    def fake_reviewer(
        spec: AgentInvocationSpec, review_input_text: str
    ) -> StructuredReviewResult:
        if reviewer_profiles is not None:
            reviewer_profiles.append(ComputeProfile(spec.args[-1].upper()))
        artifact = (env.work / "review.patch").read_text(encoding="utf-8")
        assert f"CURRENT_PATCH:\n{artifact}\n" in review_input_text
        reviewer_prompts.append(review_input_text)
        assert review_queue, "test exhausted CP-3 reviewer sequence"
        return review_queue.pop(0)

    real_run_verification = orch_module._run_verification_commands
    real_build_committed = repository.build_checkpoint_patch_committed

    def spy_verification(
        config: OrchestratorConfig, commands: tuple[tuple[str, ...], ...]
    ) -> VerificationEvidence:
        verification_commands.append(commands)
        return real_run_verification(config, commands)

    def spy_committed(repo_path: Path, predecessor: str) -> repository.ReviewPatch:
        committed_ranges.append(predecessor)
        return real_build_committed(repo_path, predecessor)

    monkeypatch.setattr(orch_module, "run_implementer", fake_implementer)
    monkeypatch.setattr(orch_module, "run_structured_reviewer", fake_reviewer)
    monkeypatch.setattr(orch_module, "_run_verification_commands", spy_verification)
    monkeypatch.setattr(
        orch_module.repository, "build_checkpoint_patch_committed", spy_committed
    )
    assert env.work.exists()
    return reviewer_prompts, implementer_prompts, verification_commands, committed_ranges


def _cp3_config(env: Env) -> OrchestratorConfig:
    return _default_config(
        env,
        implementer_spec=_implementer_spec(env.work, "print('unused')"),
        reviewer_spec=_reviewer_spec(env.work, "print('unused')"),
        max_repairs=0,
    )


def _commit_late_repair(
    env: Env, accepted_heads: list[str]
) -> Callable[[orch_module.AcceptedImplementationRepairCandidate], str]:
    def accept(candidate: orch_module.AcceptedImplementationRepairCandidate) -> str:
        _run_git(["add", "-A"], cwd=env.work)
        _run_git(
            ["commit", "-m", f"accept {candidate.gate_context.gate_id}"],
            cwd=env.work,
        )
        head = _run_git(["rev-parse", "HEAD"], cwd=env.work).strip()
        accepted_heads.append(head)
        return head

    return accept


def _advance_cp3_origin_main(env: Env, marker: str) -> str:
    (env.seed / "README.md").write_text(f"seed\n{marker}\n", encoding="utf-8")
    _run_git(["add", "README.md"], cwd=env.seed)
    _run_git(["commit", "-q", "-m", marker], cwd=env.seed)
    _run_git(["push", "-q", "origin", "main"], cwd=env.seed)
    return _run_git(["rev-parse", "HEAD"], cwd=env.seed).strip()


def _advance_cp3_origin_main_tracker(env: Env, marker: str, tracker_fact: str) -> str:
    task_path = env.seed / "docs" / "TASK.md"
    task_path.write_text(
        task_path.read_text(encoding="utf-8") + f"\n{tracker_fact}\n",
        encoding="utf-8",
    )
    _run_git(["add", "docs/TASK.md"], cwd=env.seed)
    _run_git(["commit", "-q", "-m", marker], cwd=env.seed)
    _run_git(["push", "-q", "origin", "main"], cwd=env.seed)
    return _run_git(["rev-parse", "HEAD"], cwd=env.seed).strip()


def _mock_cp3_revalidated_target(
    monkeypatch: pytest.MonkeyPatch,
    target: ExecutionTarget,
) -> list[str]:
    loaded_shas: list[str] = []

    def fake_revalidate(
        config: OrchestratorConfig,
        accepted: ExecutionTarget,
        fresh_sha: str,
    ) -> None:
        assert config.repo
        loaded_shas.append(fresh_sha)
        if accepted.task != target.task or accepted.spec != target.spec:
            raise orch_module._Blocked(
                "origin/main changed the accepted v2 execution target"
            )

    monkeypatch.setattr(
        orch_module, "_revalidate_file_selected_target_at_sha", fake_revalidate
    )
    return loaded_shas


def test_v2_cumulative_repair_replays_checkpoints_full_verification_and_review(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    base_sha, checkpoint_result = _prepared_v2_checkpoint_result(env, spec)
    assert isinstance(checkpoint_result, orch_module.V2CheckpointExecutionResult)
    old_full_head = _run_git(["rev-parse", "HEAD"], cwd=env.work).strip()
    accepted_heads: list[str] = []
    reviewer_profiles: list[ComputeProfile] = []
    prompts, _, commands, ranges = _install_cp3_reviewer_sequence(
        env,
        monkeypatch,
        [
            _changes_with_paths("late defect", ("cp_2.txt",)),
            _v2_approved(),  # mode-A repair
            _v2_approved(),  # conservative replay CP-1
            _v2_approved(),  # conservative replay CP-2
            _v2_approved(),  # rebuilt cumulative review
        ],
        reviewer_profiles=reviewer_profiles,
    )

    result = orch_module.execute_v2_pre_closure_review(
        _cp3_config(env),
        _cp3_target(base_sha, spec),
        checkpoint_result,
        repair_acceptor=_commit_late_repair(env, accepted_heads),
    )

    assert result.completed
    assert result.blocked_reason is None
    assert len(accepted_heads) == 1
    assert result.evidence.full_verification is not None
    assert result.evidence.full_verification.head_sha == accepted_heads[0]
    assert result.evidence.full_verification.head_sha != old_full_head
    assert result.evidence.full_verification.candidate_identity == (
        orch_module._committed_candidate_identity(accepted_heads[0])
    )
    assert tuple(
        item.command for item in result.evidence.full_verification.verification.commands
    ) == spec.full_verification
    assert result.evidence.cumulative_review is not None
    assert result.evidence.cumulative_review.review_iteration == 2
    assert result.evidence.cumulative_review.reviewed_head_sha == accepted_heads[0]
    assert (
        result.evidence.cumulative_review.review_patch.purpose
        is repository.ReviewPurpose.PRE_CLOSURE_CUMULATIVE_REVIEW
    )
    assert result.evidence.cumulative_review.review_patch.range_description.endswith(
        "...HEAD"
    )
    assert (env.work / "review.patch").read_text(encoding="utf-8") == (
        result.evidence.cumulative_review.review_patch.diff_text
    )
    assert [item.candidate.checkpoint.checkpoint_id for item in result.evidence.accepted_checkpoints] == [
        "CP-1",
        "CP-2",
    ]
    assert result.evidence.accepted_checkpoints[0] is not checkpoint_result.checkpoint_evidence[0]
    assert ranges == [
        checkpoint_result.checkpoint_evidence[0].predecessor_review_boundary_sha,
        checkpoint_result.checkpoint_evidence[1].predecessor_review_boundary_sha,
    ]
    assert commands.count(spec.full_verification) == 2
    assert all(
        "FINAL_CUMULATIVE_AUDIT" not in prompt for prompt in prompts
    )
    assert [
        profile
        for prompt, profile in zip(prompts, reviewer_profiles, strict=True)
        if "PRE_CLOSURE_CUMULATIVE_REVIEW" in prompt
    ] == [ComputeProfile.CRITICAL, ComputeProfile.CRITICAL]
    assert {
        purpose.value for purpose in repository.ReviewPurpose
    } == {
        "checkpoint",
        "pre_closure_cumulative_review",
        "final_cumulative_audit",
    }


def test_v2_replayed_gate_changes_requested_repairs_and_restarts_from_cp1(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    base_sha, checkpoint_result = _prepared_v2_checkpoint_result(env, spec)
    assert isinstance(checkpoint_result, orch_module.V2CheckpointExecutionResult)
    accepted_heads: list[str] = []
    prompts, implementer_prompts, _, ranges = _install_cp3_reviewer_sequence(
        env,
        monkeypatch,
        [
            _v2_changes("cumulative defect"),
            _v2_approved(),  # cumulative repair
            _v2_changes("replay CP-1 defect"),
            _v2_approved(),  # replay repair
            _v2_approved(),  # restarted replay CP-1
            _v2_approved(),  # restarted replay CP-2
            _v2_approved(),  # rebuilt cumulative review
        ],
    )

    result = orch_module.execute_v2_pre_closure_review(
        _cp3_config(env),
        _cp3_target(base_sha, spec),
        checkpoint_result,
        repair_acceptor=_commit_late_repair(env, accepted_heads),
    )

    assert result.completed
    assert len(accepted_heads) == 2
    cp1_boundary = checkpoint_result.checkpoint_evidence[0].predecessor_review_boundary_sha
    assert ranges.count(cp1_boundary) == 2
    assert any(
        "CURRENT_REPAIR_GATE: replay-repair:CP-1" in prompt
        for prompt in implementer_prompts
    )
    assert all("choose workflow transitions" not in prompt for prompt in prompts)
    assert len(result.evidence.accepted_checkpoints) == 2


def test_v2_origin_main_movement_with_same_target_revalidates_and_rebuilds(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    base_sha, checkpoint_result = _prepared_v2_checkpoint_result(env, spec)
    assert isinstance(checkpoint_result, orch_module.V2CheckpointExecutionResult)
    target = _cp3_target(base_sha, spec)
    moved_sha = _advance_cp3_origin_main(env, "unrelated-main-movement")
    loaded_shas = _mock_cp3_revalidated_target(monkeypatch, target)
    prompts, _, commands, _ = _install_cp3_reviewer_sequence(
        env, monkeypatch, [_v2_approved()]
    )

    result = orch_module.execute_v2_pre_closure_review(
        _cp3_config(env),
        target,
        checkpoint_result,
        repair_acceptor=lambda candidate: "unused",
    )

    assert result.completed
    assert loaded_shas == [moved_sha]
    assert result.evidence.base_identity == moved_sha
    assert result.evidence.full_verification is not None
    assert result.evidence.full_verification.base_identity == moved_sha
    assert result.evidence.cumulative_review is not None
    assert result.evidence.cumulative_review.base_identity == moved_sha
    assert result.evidence.cumulative_review.review_patch.base_sha == moved_sha
    assert len(prompts) == 1
    assert commands.count(spec.full_verification) == 1


@pytest.mark.parametrize(
    "changed_fact",
    ["spec", "dependencies", "priority", "size", "group", "title"],
)
def test_v2_origin_main_movement_blocks_changed_execution_target(
    env: Env, monkeypatch: pytest.MonkeyPatch, changed_fact: str
) -> None:
    spec = _cp3_spec()
    base_sha, checkpoint_result = _prepared_v2_checkpoint_result(env, spec)
    assert isinstance(checkpoint_result, orch_module.V2CheckpointExecutionResult)
    target = _cp3_target(base_sha, spec)
    moved_sha = _advance_cp3_origin_main(env, f"changed-{changed_fact}")
    if changed_fact == "spec":
        changed_spec = dataclasses.replace(
            spec, text=spec.text + "\nchanged\n", digest="changed-spec-digest"
        )
        changed_target = dataclasses.replace(target, spec=changed_spec)
    elif changed_fact == "dependencies":
        changed_task = dataclasses.replace(
            target.task, depends_on=target.task.depends_on + ("TSK-9002",)
        )
        changed_target = dataclasses.replace(target, task=changed_task)
    else:
        replacements = {
            "priority": {"priority": "P1"},
            "size": {"size": "S"},
            "group": {"group": "documentation"},
            "title": {"title": "Changed task title"},
        }
        changed_task = dataclasses.replace(target.task, **replacements[changed_fact])
        changed_target = dataclasses.replace(target, task=changed_task)
    loaded_shas = _mock_cp3_revalidated_target(monkeypatch, changed_target)

    result = orch_module.execute_v2_pre_closure_review(
        _cp3_config(env),
        target,
        checkpoint_result,
        repair_acceptor=lambda candidate: "unused",
    )

    assert not result.completed
    assert loaded_shas == [moved_sha]
    assert "changed the accepted v2 execution target" in (result.blocked_reason or "")
    assert result.evidence.cumulative_review is None
    assert result.terminal_phase is Phase.ORIGIN_MAIN_REVALIDATION


def test_v2_origin_main_movement_after_review_discards_stale_approval_and_history(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    base_sha, checkpoint_result = _prepared_v2_checkpoint_result(env, spec)
    assert isinstance(checkpoint_result, orch_module.V2CheckpointExecutionResult)
    target = _cp3_target(base_sha, spec)
    loaded_shas = _mock_cp3_revalidated_target(monkeypatch, target)
    prompts, _, commands, _ = _install_cp3_reviewer_sequence(
        env, monkeypatch, [_v2_approved(), _v2_approved()]
    )
    sequenced_reviewer = orch_module.run_structured_reviewer
    review_count = 0
    moved_sha: str | None = None

    def move_after_first_review(
        agent_spec: AgentInvocationSpec, review_input: str
    ) -> StructuredReviewResult:
        nonlocal review_count, moved_sha
        review_count += 1
        review = sequenced_reviewer(agent_spec, review_input)
        if review_count == 1:
            moved_sha = _advance_cp3_origin_main(env, "move-after-review")
        return review

    monkeypatch.setattr(
        orch_module, "run_structured_reviewer", move_after_first_review
    )

    result = orch_module.execute_v2_pre_closure_review(
        _cp3_config(env),
        target,
        checkpoint_result,
        repair_acceptor=lambda candidate: "unused",
    )

    assert result.completed
    assert moved_sha is not None
    assert loaded_shas == [moved_sha]
    assert len(prompts) == 2
    assert commands.count(spec.full_verification) == 2
    assert result.evidence.cumulative_review is not None
    assert result.evidence.cumulative_review.base_identity == moved_sha
    assert result.evidence.cumulative_review.review_iteration == 1
    assert result.cumulative_history.context.accepted_base_context_identity == moved_sha
    assert len(result.cumulative_history.attempts) == 1


def test_v2_origin_main_movement_resets_rejected_candidate_cycle_context(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    base_sha, checkpoint_result = _prepared_v2_checkpoint_result(env, spec)
    assert isinstance(checkpoint_result, orch_module.V2CheckpointExecutionResult)
    target = _cp3_target(base_sha, spec)
    _mock_cp3_revalidated_target(monkeypatch, target)
    prompts, implementer_prompts, _, _ = _install_cp3_reviewer_sequence(
        env, monkeypatch, [_v2_changes("stale rejection"), _v2_approved()]
    )
    sequenced_reviewer = orch_module.run_structured_reviewer
    review_count = 0

    def move_after_stale_rejection(
        agent_spec: AgentInvocationSpec, review_input: str
    ) -> StructuredReviewResult:
        nonlocal review_count
        review_count += 1
        review = sequenced_reviewer(agent_spec, review_input)
        if review_count == 1:
            _advance_cp3_origin_main(env, "move-after-stale-rejection")
        return review

    monkeypatch.setattr(
        orch_module, "run_structured_reviewer", move_after_stale_rejection
    )

    result = orch_module.execute_v2_pre_closure_review(
        _cp3_config(env),
        target,
        checkpoint_result,
        repair_acceptor=lambda candidate: "unused",
    )

    assert result.completed
    assert len(prompts) == 2
    assert implementer_prompts == []
    assert result.cumulative_history.review_iteration == 1
    assert result.cumulative_history.rejected_candidate_identities == set()
    assert len(result.cumulative_history.attempts) == 1


def test_v2_evidence_invalidation_discards_old_cumulative_approval_and_downstream() -> None:
    spec = _cp3_spec()
    evidence = orch_module.V2ImplementationEvidence(
        spec_identity=spec.digest,
        base_identity="base",
        accepted_checkpoints=[],
    )
    evidence.full_verification = orch_module.V2FullVerificationEvidence(
        spec_identity=spec.digest,
        base_identity="base",
        candidate_identity=CandidateIdentity("candidate"),
        head_sha="head",
        verification=_v2_verification(True),
    )
    patch = repository.ReviewPatch(
        purpose=repository.ReviewPurpose.PRE_CLOSURE_CUMULATIVE_REVIEW,
        range_description="origin/main...HEAD",
        base_sha="base",
        head_sha="head",
        branch="delivery",
        diff_text="diff",
        digest="digest",
    )
    evidence.cumulative_review = orch_module.V2CumulativeReviewEvidence(
        spec_identity=spec.digest,
        base_identity="base",
        candidate_identity=CandidateIdentity("candidate"),
        reviewed_head_sha="head",
        review_patch=patch,
        review_iteration=1,
    )

    evidence.invalidate_from_checkpoint(0)

    assert evidence.accepted_checkpoints == []
    assert evidence.full_verification is None
    assert evidence.cumulative_review is None


def test_v2_late_repair_has_no_numeric_repair_limit(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    _run_git(["checkout", "-q", "-b", "delivery"], cwd=env.work)
    accepted_heads: list[str] = []
    _install_cp3_reviewer_sequence(
        env,
        monkeypatch,
        [
            _v2_changes("repair-1"),
            _v2_changes("repair-2", diagnosis=True),
            _v2_changes("repair-3", diagnosis=True),
            _v2_approved(),
        ],
    )
    initial = _v2_changes("initial").repair_packet
    assert initial is not None

    accepted, history, accepted_base = orch_module._execute_v2_late_repair(
        _cp3_config(env),
        spec,
        gate_id="late-repair-no-budget",
        accepted_base_context_identity=_run_git(
            ["rev-parse", "HEAD"], cwd=env.work
        ).strip(),
        initial_packet=initial,
        verification_commands=spec.checkpoints[0].verification,
        repair_acceptor=_commit_late_repair(env, accepted_heads),
    )

    assert accepted.review_iteration == 4
    assert history.review_iteration == 4
    assert len(history.attempts) == 4
    assert accepted_base == accepted_heads[0]


def test_v2_late_repair_upstream_packet_routes_first_review_critical(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    _run_git(["checkout", "-q", "-b", "delivery"], cwd=env.work)
    implementer_profiles: list[ComputeProfile] = []
    reviewer_profiles: list[ComputeProfile] = []
    _install_cp3_reviewer_sequence(
        env,
        monkeypatch,
        [_v2_approved()],
        implementer_profiles=implementer_profiles,
        reviewer_profiles=reviewer_profiles,
    )
    upstream = _v2_changes("upstream").repair_packet
    assert upstream is not None

    orch_module._execute_v2_late_repair(
        _cp3_config(env),
        spec,
        gate_id="upstream-child-repair",
        accepted_base_context_identity=_run_git(
            ["rev-parse", "HEAD"], cwd=env.work
        ).strip(),
        initial_packet=upstream,
        verification_commands=spec.checkpoints[0].verification,
        repair_acceptor=_commit_late_repair(env, []),
    )

    assert implementer_profiles == [ComputeProfile.DELIBERATE]
    assert reviewer_profiles == [ComputeProfile.CRITICAL]


def test_v2_seeded_verification_episode_escalates_repair_not_first_review(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    _run_git(["checkout", "-q", "-b", "delivery"], cwd=env.work)
    implementer_profiles: list[ComputeProfile] = []
    reviewer_profiles: list[ComputeProfile] = []
    _install_cp3_reviewer_sequence(
        env,
        monkeypatch,
        [_v2_approved()],
        implementer_profiles=implementer_profiles,
        reviewer_profiles=reviewer_profiles,
    )
    verification_queue = [_v2_verification(False), _v2_verification(True)]

    def verification(
        config: OrchestratorConfig, commands: tuple[tuple[str, ...], ...]
    ) -> VerificationEvidence:
        assert config.repo == env.work
        assert commands == spec.checkpoints[0].verification
        return verification_queue.pop(0)

    monkeypatch.setattr(orch_module, "_run_verification_commands", verification)

    orch_module._execute_v2_late_repair(
        _cp3_config(env),
        spec,
        gate_id="seeded-verification-child-repair",
        accepted_base_context_identity=_run_git(
            ["rev-parse", "HEAD"], cwd=env.work
        ).strip(),
        initial_packet=None,
        initial_verification_failure="upstream verification failed",
        initial_verification_rejection_count=1,
        verification_commands=spec.checkpoints[0].verification,
        repair_acceptor=_commit_late_repair(env, []),
    )

    assert not verification_queue
    assert implementer_profiles == [
        ComputeProfile.DELIBERATE,
        ComputeProfile.CRITICAL,
    ]
    assert reviewer_profiles == [ComputeProfile.DELIBERATE]


def test_v2_late_repair_records_explicit_blocked_before_terminal_transition(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    _run_git(["checkout", "-q", "-b", "delivery"], cwd=env.work)
    _install_cp3_reviewer_sequence(
        env, monkeypatch, [_v2_explicit_blocked("late repair blocked")]
    )
    recorded = _capture_recorded_review_attempts(monkeypatch)
    initial = _v2_changes("initial").repair_packet
    assert initial is not None

    with pytest.raises(orch_module._Blocked, match="late repair blocked"):
        orch_module._execute_v2_late_repair(
            _cp3_config(env),
            spec,
            gate_id="late-repair-blocked",
            accepted_base_context_identity=_run_git(
                ["rev-parse", "HEAD"], cwd=env.work
            ).strip(),
            initial_packet=initial,
            verification_commands=spec.checkpoints[0].verification,
            repair_acceptor=lambda candidate: pytest.fail(
                f"blocked candidate was accepted: {candidate}"
            ),
        )

    assert len(recorded) == 1
    context, attempt = recorded[0]
    assert context.gate_id == "late-repair-blocked"
    assert attempt.review_iteration == 1
    assert attempt.reviewer_verdict is ReviewVerdict.BLOCKED
    assert attempt.findings == ()
    assert not attempt.rejected and attempt.rejection_basis is None


def test_v2_replayed_checkpoint_records_explicit_blocked(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    _, checkpoint_result = _prepared_v2_checkpoint_result(env, spec)
    assert isinstance(checkpoint_result, orch_module.V2CheckpointExecutionResult)
    original = checkpoint_result.checkpoint_evidence[0]
    history = GateHistory(
        context=GateContext(
            gate_id=f"replay:{original.candidate.checkpoint.checkpoint_id}",
            spec_identity=spec.digest,
            accepted_base_context_identity=original.predecessor_review_boundary_sha,
        )
    )
    reviewer_profiles: list[ComputeProfile] = []
    _install_cp3_reviewer_sequence(
        env,
        monkeypatch,
        [_v2_explicit_blocked("checkpoint replay blocked")],
        reviewer_profiles=reviewer_profiles,
    )

    with pytest.raises(orch_module._Blocked, match="checkpoint replay blocked"):
        orch_module._review_v2_replayed_checkpoint(
            _cp3_config(env), spec, original, history
        )

    assert history.review_iteration == 1
    assert len(history.attempts) == 1
    attempt = history.attempts[0]
    assert attempt.reviewer_verdict is ReviewVerdict.BLOCKED
    assert attempt.findings == ()
    assert not attempt.rejected and attempt.rejection_basis is None
    assert reviewer_profiles == [ComputeProfile.DELIBERATE]


# --- TSK-0028 CP-4: unpublished Task Closure and Mode C ordering ------------


def _prepared_cp4_context(
    env: Env, spec: TaskExecutionSpec
) -> tuple[
    ExecutionTarget,
    orch_module.V2CheckpointExecutionResult,
    orch_module.V2PreClosureExecutionResult,
    str,
]:
    base_sha, checkpoint_result = _prepared_v2_checkpoint_result(env, spec)
    assert isinstance(checkpoint_result, orch_module.V2CheckpointExecutionResult)
    _run_git(["push", "-q", "-u", "origin", "delivery"], cwd=env.work)
    implementation_head = _run_git(["rev-parse", "HEAD"], cwd=env.work).strip()
    patch = repository.build_cumulative_patch_from_base(
        env.work,
        repository.ReviewPurpose.PRE_CLOSURE_CUMULATIVE_REVIEW,
        base_sha,
    )
    verification = dataclasses.replace(
        _v2_verification(True), head_sha=implementation_head
    )
    evidence = orch_module.V2ImplementationEvidence(
        spec_identity=spec.digest,
        base_identity=base_sha,
        accepted_checkpoints=list(checkpoint_result.checkpoint_evidence),
        full_verification=orch_module.V2FullVerificationEvidence(
            spec_identity=spec.digest,
            base_identity=base_sha,
            candidate_identity=orch_module._committed_candidate_identity(
                implementation_head
            ),
            head_sha=implementation_head,
            verification=verification,
        ),
        cumulative_review=orch_module.V2CumulativeReviewEvidence(
            spec_identity=spec.digest,
            base_identity=base_sha,
            candidate_identity=orch_module._candidate_identity(patch.diff_text),
            reviewed_head_sha=implementation_head,
            review_patch=patch,
            review_iteration=1,
        ),
    )
    pre_closure = orch_module.V2PreClosureExecutionResult(
        completed=True,
        evidence=evidence,
        cumulative_history=GateHistory(
            context=GateContext(
                gate_id="pre-closure-cumulative-review",
                spec_identity=spec.digest,
                accepted_base_context_identity=base_sha,
            )
        ),
        replay_histories=(),
    )
    return _cp3_target(base_sha, spec), checkpoint_result, pre_closure, implementation_head


def _install_cp4_agents(
    env: Env,
    monkeypatch: pytest.MonkeyPatch,
    reviews: list[StructuredReviewResult],
    *,
    source_during_second_closure: bool = False,
    implementer_profiles: list[ComputeProfile] | None = None,
    reviewer_profiles: list[ComputeProfile] | None = None,
) -> tuple[list[str], list[str]]:
    queue = list(reviews)
    implementer_prompts: list[str] = []
    reviewer_prompts: list[str] = []
    closure_count = 0
    repair_count = 0

    def fake_implementer(
        spec: AgentInvocationSpec, prompt: str
    ) -> AgentInvocationResult:
        nonlocal closure_count, repair_count
        if implementer_profiles is not None:
            implementer_profiles.append(ComputeProfile(spec.args[-1].upper()))
        implementer_prompts.append(prompt)
        if "CURRENT_GATE: prospective Task Closure" in prompt:
            closure_count += 1
            task_path = env.work / "docs" / "TASK.md"
            task_text = task_path.read_bytes().decode("utf-8")
            eol = "\r\n" if "\r\n" in task_text else "\n"
            separator = (
                f"| ID | Status | Evidence | Title |{eol}"
                f"| --- | --- | --- | --- |{eol}"
            )
            row = f"| `{_TASK_ID}` | `Done` | PR #1 | Test task |{eol}"
            if row not in task_text:
                assert separator in task_text
                task_path.write_bytes(
                    task_text.replace(separator, separator + row, 1).encode("utf-8")
                )
            (env.work / "docs" / "DEVELOPMENT_LOG.md").write_text(
                f"closure log {closure_count}\n", encoding="utf-8"
            )
            if source_during_second_closure and closure_count == 2:
                (env.work / "unsafe_source.py").write_text(
                    "unsafe = True\n", encoding="utf-8"
                )
        elif (
            "CURRENT_REPAIR_GATE: mode-c-implementation-repair" in prompt
            or "CURRENT_REPAIR_GATE: closure-review-implementation-repair" in prompt
        ):
            repair_count += 1
            (env.work / "late_repair.txt").write_text(
                f"implementation repair {repair_count}\n", encoding="utf-8"
            )
        else:
            raise AssertionError(f"unexpected CP-4 implementer prompt: {prompt[:100]}")
        return AgentInvocationResult("done", "", 0, False)

    def fake_reviewer(
        spec: AgentInvocationSpec, prompt: str
    ) -> StructuredReviewResult:
        if reviewer_profiles is not None:
            reviewer_profiles.append(ComputeProfile(spec.args[-1].upper()))
        artifact = (env.work / "review.patch").read_text(encoding="utf-8")
        assert f"CURRENT_PATCH:\n{artifact}\n" in prompt
        reviewer_prompts.append(prompt)
        assert queue, "CP-4 reviewer sequence exhausted"
        return queue.pop(0)

    monkeypatch.setattr(orch_module, "run_implementer", fake_implementer)
    monkeypatch.setattr(orch_module, "run_structured_reviewer", fake_reviewer)
    return implementer_prompts, reviewer_prompts


def _cp4_repair_acceptor(
    env: Env,
) -> Callable[[orch_module.AcceptedImplementationRepairCandidate], str]:
    def accept(candidate: orch_module.AcceptedImplementationRepairCandidate) -> str:
        _run_git(["add", "-A"], cwd=env.work)
        _run_git(
            ["commit", "-q", "-m", f"accept {candidate.gate_context.gate_id}"],
            cwd=env.work,
        )
        _run_git(["push", "-q", "origin", "delivery"], cwd=env.work)
        return _run_git(["rev-parse", "HEAD"], cwd=env.work).strip()

    return accept


def test_v2_mode_c_reviews_local_closure_then_publishes_exact_candidate_before_ci(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    target, checkpoints, pre_closure, implementation_head = _prepared_cp4_context(
        env, spec
    )
    _, reviewer_prompts = _install_cp4_agents(
        env, monkeypatch, [_v2_approved(), _v2_approved()]
    )
    sequenced_reviewer = orch_module.run_structured_reviewer
    mode_c_remote_heads: list[str] = []

    def observe_unpublished_mode_c(
        agent_spec: AgentInvocationSpec, prompt: str
    ) -> StructuredReviewResult:
        if "FINAL_CUMULATIVE_AUDIT" in prompt:
            mode_c_remote_heads.append(repository.remote_branch_sha(env.work, "delivery"))
        return sequenced_reviewer(agent_spec, prompt)

    monkeypatch.setattr(
        orch_module, "run_structured_reviewer", observe_unpublished_mode_c
    )
    real_checks = repository.pr_required_checks
    ci_remote_heads: list[str] = []
    commands: list[list[str]] = []
    real_run = repository._run

    def record_commands(
        args: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        commands.append(args)
        return real_run(args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(repository, "_run", record_commands)

    def checks_after_publish(
        repo: Path, pr_number: str, *, gh_command: tuple[str, ...]
    ) -> repository.RequiredChecksResult:
        repository.fetch_origin(repo)
        ci_remote_heads.append(repository.remote_branch_sha(repo, "delivery"))
        assert ci_remote_heads[-1] == repository.head_sha(repo)
        return real_checks(repo, pr_number, gh_command=gh_command)

    monkeypatch.setattr(repository, "pr_required_checks", checks_after_publish)

    result = orch_module.execute_v2_unpublished_closure(
        _cp3_config(env),
        target,
        checkpoints,
        pre_closure,
        repair_acceptor=_cp4_repair_acceptor(env),
    )

    assert result.completed and result.published
    assert result.closure_candidate is not None
    assert result.mode_c_evidence is not None
    assert result.mode_c_evidence.candidate_head_sha == result.closure_candidate.candidate_head_sha
    assert result.closure_candidate.published_predecessor_sha == implementation_head
    assert mode_c_remote_heads == [implementation_head]
    assert ci_remote_heads == [result.closure_candidate.candidate_head_sha]
    mode_c_prompt = next(
        prompt for prompt in reviewer_prompts if "FINAL_CUMULATIVE_AUDIT" in prompt
    )
    assert result.closure_candidate.candidate_head_sha in mode_c_prompt
    assert (env.work / "review.patch").read_bytes() == (
        result.mode_c_evidence.review_patch.diff_text.encode("utf-8")
    )
    assert "review.patch" not in _run_git(
        ["show", "--format=", "--name-only", result.closure_candidate.candidate_head_sha],
        cwd=env.work,
    ).splitlines()
    assert "prospective Task Closure" in _run_git(
        ["log", "-1", "--format=%s"], cwd=env.work
    )
    assert task_context.parse_terminal_registry(
        (env.work / "docs" / "TASK.md").read_text(encoding="utf-8")
    ).tasks == (
        TerminalTask(
            task_id=_TASK_ID,
            status=TaskStatus.DONE,
            evidence="PR #1",
            title="Test task",
        ),
        TerminalTask(
            task_id="TSK-9000",
            status=TaskStatus.DONE,
            evidence="PR #7",
            title="Existing prerequisite",
        ),
    )
    assert not any(command[:2] == ["git", "merge"] for command in commands)
    assert not any("--auto" in command for command in commands)


@pytest.mark.parametrize(
    "tracker_fact",
    [
        "- **Next free ID:** TSK-9003",
        "- **Next:** TSK-9010",
    ],
    ids=["next-free-id", "other-queue-fact"],
)
def test_v2_closure_material_tracker_movement_blocks_stale_closure_publication(
    env: Env,
    monkeypatch: pytest.MonkeyPatch,
    tracker_fact: str,
) -> None:
    spec = _cp3_spec()
    target, checkpoints, pre_closure, implementation_head = _prepared_cp4_context(
        env, spec
    )
    _mock_cp3_revalidated_target(monkeypatch, target)
    _install_cp4_agents(env, monkeypatch, [_v2_approved()])
    sequenced_reviewer = orch_module.run_structured_reviewer
    moved = False

    def move_tracker_after_closure_review(
        agent_spec: AgentInvocationSpec, prompt: str
    ) -> StructuredReviewResult:
        nonlocal moved
        review = sequenced_reviewer(agent_spec, prompt)
        if "prospective Task Closure review" in prompt and not moved:
            _advance_cp3_origin_main_tracker(
                env, "closure-material-move", tracker_fact
            )
            moved = True
        return review

    monkeypatch.setattr(
        orch_module, "run_structured_reviewer", move_tracker_after_closure_review
    )

    result = orch_module.execute_v2_unpublished_closure(
        _cp3_config(env),
        target,
        checkpoints,
        pre_closure,
        repair_acceptor=_cp4_repair_acceptor(env),
    )

    assert moved
    assert not result.completed and not result.published
    assert "prepared Task Closure is stale" in (result.blocked_reason or "")
    assert result.terminal_phase is Phase.ORIGIN_MAIN_REVALIDATION
    repository.fetch_origin(env.work)
    assert repository.remote_branch_sha(env.work, "delivery") == implementation_head


def test_v2_closure_material_newline_only_tracker_movement_is_stale(
    env: Env,
) -> None:
    base_sha = repository.origin_main_sha(env.work)
    baseline = orch_module._capture_v2_closure_material_baseline(env.work, base_sha)
    tracker = env.seed / "docs" / "TASK.md"
    baseline_text = dict(baseline.texts)["docs/TASK.md"]
    assert baseline_text is not None
    baseline_bytes = baseline_text.encode("utf-8")
    _run_git(["config", "core.autocrlf", "false"], cwd=env.seed)
    if b"\r\n" in baseline_bytes:
        changed = baseline_bytes.replace(b"\r\n", b"\n")
    else:
        changed = baseline_bytes.replace(b"\n", b"\r\n")
    assert changed != baseline_bytes
    tracker.write_bytes(changed)
    _run_git(["add", "docs/TASK.md"], cwd=env.seed)
    _run_git(["commit", "-q", "-m", "change tracker newlines"], cwd=env.seed)
    _run_git(["push", "-q", "origin", "main"], cwd=env.seed)
    repository.fetch_origin(env.work)
    moved_sha = repository.origin_main_sha(env.work)

    with pytest.raises(orch_module._Blocked, match="prepared Task Closure is stale"):
        orch_module._require_v2_closure_material_unchanged(
            env.work, baseline, moved_sha
        )


def test_v2_unrelated_origin_movement_revalidates_and_allows_mode_c(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    target, checkpoints, pre_closure, _ = _prepared_cp4_context(env, spec)
    _mock_cp3_revalidated_target(monkeypatch, target)
    _install_cp4_agents(env, monkeypatch, [_v2_approved(), _v2_approved()])
    sequenced_reviewer = orch_module.run_structured_reviewer
    moved_sha: str | None = None

    def move_readme_after_closure_review(
        agent_spec: AgentInvocationSpec, prompt: str
    ) -> StructuredReviewResult:
        nonlocal moved_sha
        review = sequenced_reviewer(agent_spec, prompt)
        if "prospective Task Closure review" in prompt and moved_sha is None:
            moved_sha = _advance_cp3_origin_main(env, "readme-only-before-mode-c")
        return review

    monkeypatch.setattr(
        orch_module, "run_structured_reviewer", move_readme_after_closure_review
    )

    result = orch_module.execute_v2_unpublished_closure(
        _cp3_config(env),
        target,
        checkpoints,
        pre_closure,
        repair_acceptor=_cp4_repair_acceptor(env),
    )

    assert result.completed and result.published
    assert moved_sha is not None
    assert result.mode_c_evidence is not None
    assert result.mode_c_evidence.base_sha == moved_sha


def test_v2_mode_c_closure_only_repair_replaces_local_candidate_without_rewrite(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    target, checkpoints, pre_closure, implementation_head = _prepared_cp4_context(
        env, spec
    )
    implementer_prompts, reviewer_prompts = _install_cp4_agents(
        env,
        monkeypatch,
        [
            _v2_approved(),
            _changes_with_paths("closure defect", ("docs/TASK.md",)),
            _v2_approved(),
            _v2_approved(),
        ],
    )

    result = orch_module.execute_v2_unpublished_closure(
        _cp3_config(env),
        target,
        checkpoints,
        pre_closure,
        repair_acceptor=_cp4_repair_acceptor(env),
    )

    assert result.completed
    assert len([p for p in implementer_prompts if "prospective Task Closure" in p]) == 2
    assert result.closure_candidate is not None
    assert result.closure_candidate.published_predecessor_sha == implementation_head
    assert _run_git(["rev-list", "--count", f"{implementation_head}..HEAD"], cwd=env.work).strip() == "1"
    closure_reviews = [
        prompt
        for prompt in reviewer_prompts
        if "prospective Task Closure review" in prompt
    ]
    mode_c_reviews = [
        prompt for prompt in reviewer_prompts if "FINAL_CUMULATIVE_AUDIT" in prompt
    ]
    assert "PREVIOUS_REVIEWER_FINDINGS" not in closure_reviews[0]
    assert "REPAIR_DELTA_SINCE_LAST_REVIEWED_CANDIDATE" not in closure_reviews[0]
    assert "PREVIOUS_REVIEWER_FINDINGS" not in closure_reviews[1]
    assert "REPAIR_DELTA_SINCE_LAST_REVIEWED_CANDIDATE" not in closure_reviews[1]
    assert "PREVIOUS_REVIEWER_FINDINGS" not in mode_c_reviews[0]
    assert "REPAIR_DELTA_SINCE_LAST_REVIEWED_CANDIDATE" not in mode_c_reviews[0]
    assert "PREVIOUS_REVIEWER_FINDINGS" in mode_c_reviews[1]
    assert "REPAIR_DELTA_SINCE_LAST_REVIEWED_CANDIDATE" in mode_c_reviews[1]


def test_v2_closure_review_repair_handoff_contains_gate_local_delta_only(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    target, checkpoints, pre_closure, _ = _prepared_cp4_context(env, spec)
    implementer_profiles: list[ComputeProfile] = []
    reviewer_profiles: list[ComputeProfile] = []
    _, reviewer_prompts = _install_cp4_agents(
        env,
        monkeypatch,
        [
            _changes_with_paths("closure review defect", ("docs/TASK.md",)),
            _v2_approved(),
            _v2_approved(),
        ],
        implementer_profiles=implementer_profiles,
        reviewer_profiles=reviewer_profiles,
    )

    result = orch_module.execute_v2_unpublished_closure(
        _cp3_config(env),
        target,
        checkpoints,
        pre_closure,
        repair_acceptor=_cp4_repair_acceptor(env),
    )

    assert result.completed
    closure_reviews = [
        prompt
        for prompt in reviewer_prompts
        if "prospective Task Closure review" in prompt
    ]
    assert len(closure_reviews) == 2
    assert "PREVIOUS_REVIEWER_FINDINGS" not in closure_reviews[0]
    assert "REPAIR_DELTA_SINCE_LAST_REVIEWED_CANDIDATE" not in closure_reviews[0]
    assert "PREVIOUS_REVIEWER_FINDINGS" in closure_reviews[1]
    assert "closure review defect" in closure_reviews[1]
    assert "REPAIR_DELTA_SINCE_LAST_REVIEWED_CANDIDATE" in closure_reviews[1]
    assert implementer_profiles == [
        ComputeProfile.ROUTINE,
        ComputeProfile.DELIBERATE,
    ]
    assert reviewer_profiles == [
        ComputeProfile.DELIBERATE,
        ComputeProfile.CRITICAL,
        ComputeProfile.CRITICAL,
    ]


def test_v2_repeated_closure_basis_escalates_second_repair(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    target, checkpoints, pre_closure, _ = _prepared_cp4_context(env, spec)
    implementer_profiles: list[ComputeProfile] = []
    reviewer_profiles: list[ComputeProfile] = []
    _install_cp4_agents(
        env,
        monkeypatch,
        [
            _changes_with_paths("closure defect", ("docs/TASK.md",)),
            _changes_with_paths(
                "closure defect persists", ("docs/TASK.md",), diagnosis=True
            ),
            _v2_approved(),
            _v2_approved(),
        ],
        implementer_profiles=implementer_profiles,
        reviewer_profiles=reviewer_profiles,
    )

    result = orch_module.execute_v2_unpublished_closure(
        _cp3_config(env),
        target,
        checkpoints,
        pre_closure,
        repair_acceptor=_cp4_repair_acceptor(env),
    )

    assert result.completed
    assert implementer_profiles == [
        ComputeProfile.ROUTINE,
        ComputeProfile.DELIBERATE,
        ComputeProfile.CRITICAL,
    ]
    assert reviewer_profiles == [
        ComputeProfile.DELIBERATE,
        ComputeProfile.CRITICAL,
        ComputeProfile.CRITICAL,
        ComputeProfile.CRITICAL,
    ]


@pytest.mark.parametrize(
    ("local_basis", "expected_second_repair_profile"),
    [
        ("checkpoint:CP-1:required_result", ComputeProfile.CRITICAL),
        ("repo:independent closure requirement", ComputeProfile.DELIBERATE),
    ],
    ids=["repeated-upstream-basis", "new-local-basis"],
)
def test_v2_upstream_closure_seed_controls_later_implementer_routing(
    env: Env,
    monkeypatch: pytest.MonkeyPatch,
    local_basis: str,
    expected_second_repair_profile: ComputeProfile,
) -> None:
    spec = _cp3_spec()
    target, _, pre_closure, implementation_head = _prepared_cp4_context(env, spec)
    upstream = _changes_with_paths(
        "upstream closure defect", ("docs/TASK.md",)
    ).repair_packet
    assert upstream is not None
    implementer_profiles: list[ComputeProfile] = []
    reviewer_profiles: list[ComputeProfile] = []
    _install_cp4_agents(
        env,
        monkeypatch,
        [
            _changes_with_paths(
                "local closure defect",
                ("docs/TASK.md",),
                binding_basis=local_basis,
            ),
            _v2_approved(),
        ],
        implementer_profiles=implementer_profiles,
        reviewer_profiles=reviewer_profiles,
    )
    task_md_baseline = repository.read_utf8_file_at_ref_exact(
        env.work, target.base_sha, "docs/TASK.md"
    )

    candidate, _, _ = orch_module._prepare_v2_unpublished_closure(
        _cp3_config(env),
        target,
        pre_closure,
        pr_number="1",
        expected_published_head=implementation_head,
        task_md_baseline=task_md_baseline,
        initial_packet=upstream,
    )

    assert candidate.published_predecessor_sha == implementation_head
    assert implementer_profiles == [
        ComputeProfile.DELIBERATE,
        expected_second_repair_profile,
    ]
    assert reviewer_profiles == [
        ComputeProfile.CRITICAL,
        ComputeProfile.CRITICAL,
    ]


def test_v2_closure_review_implementation_repair_uses_cp3_replay(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    target, checkpoints, pre_closure, implementation_head = _prepared_cp4_context(
        env, spec
    )
    implementer_prompts, _ = _install_cp4_agents(
        env,
        monkeypatch,
        [
            _v2_changes("closure review found implementation defect"),
            _v2_approved(),
            _v2_approved(),
            _v2_approved(),
            _v2_approved(),
            _v2_approved(),
            _v2_approved(),
        ],
    )
    histories: list[GateHistory] = []

    result = orch_module.execute_v2_unpublished_closure(
        _cp3_config(env),
        target,
        checkpoints,
        pre_closure,
        repair_acceptor=_cp4_repair_acceptor(env),
        history_sink=histories,
    )

    assert result.completed
    assert any(
        "closure-review-implementation-repair" in prompt
        for prompt in implementer_prompts
    )
    assert result.pre_closure_result.replay_histories
    closure_metrics = [
        metric
        for metric in orch_module._summarize_v2_review_histories(histories)
        if metric.gate_id == "prospective-task-closure"
    ]
    assert closure_metrics[0].changes_requested_count == 1
    assert closure_metrics[0].binding_bases_per_review == (
        ("checkpoint:CP-1:required_result",),
    )
    assert result.closure_candidate is not None
    assert result.closure_candidate.published_predecessor_sha != implementation_head


def test_v2_closure_implementation_cr_is_recorded_before_repair_transition(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    target, _, pre_closure, implementation_head = _prepared_cp4_context(env, spec)
    review = _v2_changes("closure review found implementation defect")
    _install_cp4_agents(env, monkeypatch, [review])
    recorded = _capture_recorded_review_attempts(monkeypatch)
    histories: list[GateHistory] = []
    task_md_baseline = repository.read_utf8_file_at_ref_exact(
        env.work, target.base_sha, "docs/TASK.md"
    )

    with pytest.raises(orch_module._ImplementationRepairRequired) as raised:
        orch_module._prepare_v2_unpublished_closure(
            _cp3_config(env),
            target,
            pre_closure,
            pr_number="1",
            expected_published_head=implementation_head,
            task_md_baseline=task_md_baseline,
            history_sink=histories,
        )

    assert raised.value.packet is review.repair_packet
    assert review.repair_packet is not None
    assert len(recorded) == 1
    context, attempt = recorded[0]
    assert context.gate_id == "prospective-task-closure"
    assert attempt.reviewer_verdict is ReviewVerdict.CHANGES_REQUESTED
    assert attempt.rejection_basis is CandidateRejectionBasis.CHANGES_REQUESTED
    assert attempt.findings == review.repair_packet.findings
    closure_metrics = orch_module._summarize_v2_review_histories(histories)
    assert len(closure_metrics) == 1
    assert closure_metrics[0].gate_id == "prospective-task-closure"
    assert closure_metrics[0].changes_requested_count == 1


def test_v2_mode_c_missing_paths_uses_implementation_repair_and_cp3_replay(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    target, checkpoints, pre_closure, implementation_head = _prepared_cp4_context(
        env, spec
    )
    implementer_prompts, reviewer_prompts = _install_cp4_agents(
        env,
        monkeypatch,
        [
            _v2_approved(),
            _v2_changes("ambiguous Mode C defect"),
            _v2_approved(),
            _v2_approved(),
            _v2_approved(),
            _v2_approved(),
            _v2_approved(),
            _v2_approved(),
        ],
    )

    result = orch_module.execute_v2_unpublished_closure(
        _cp3_config(env),
        target,
        checkpoints,
        pre_closure,
        repair_acceptor=_cp4_repair_acceptor(env),
    )

    assert result.completed
    assert any("mode-c-implementation-repair" in p for p in implementer_prompts)
    assert result.pre_closure_result.replay_histories
    assert result.closure_candidate is not None
    assert result.closure_candidate.published_predecessor_sha != implementation_head
    assert sum("FINAL_CUMULATIVE_AUDIT" in p for p in reviewer_prompts) == 2


def test_preclosure_repair_evidence_is_used_by_later_mode_c_repair(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    base_sha, original_checkpoints = _prepared_v2_checkpoint_result(env, spec)
    target = _cp3_target(base_sha, spec)
    _install_cp3_reviewer_sequence(
        env,
        monkeypatch,
        [
            _v2_changes("pre-closure implementation defect"),
            _v2_approved(),
            _v2_approved(),
            _v2_approved(),
            _v2_approved(),
        ],
    )
    pre_closure = orch_module.execute_v2_pre_closure_review(
        _cp3_config(env),
        target,
        original_checkpoints,
        repair_acceptor=_cp4_repair_acceptor(env),
    )
    assert pre_closure.completed
    current_checkpoints = orch_module._checkpoint_result_from_evidence(
        original_checkpoints, pre_closure.evidence
    )

    implementer_prompts, _ = _install_cp4_agents(
        env,
        monkeypatch,
        [
            _v2_approved(),
            _v2_changes("later Mode C implementation defect"),
            _v2_approved(),
            _v2_approved(),
            _v2_approved(),
            _v2_approved(),
            _v2_approved(),
            _v2_approved(),
        ],
    )

    result = orch_module.execute_v2_unpublished_closure(
        _cp3_config(env),
        target,
        current_checkpoints,
        pre_closure,
        repair_acceptor=_cp4_repair_acceptor(env),
    )

    assert result.completed
    assert any("mode-c-implementation-repair" in p for p in implementer_prompts)
    assert len(result.pre_closure_result.evidence.accepted_checkpoints) == 2


def test_v2_two_sequential_mode_c_implementation_repairs_advance_checkpoint_state(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    target, checkpoints, pre_closure, implementation_head = _prepared_cp4_context(
        env, spec
    )
    implementer_prompts, reviewer_prompts = _install_cp4_agents(
        env,
        monkeypatch,
        [
            _v2_approved(),
            _v2_changes("first implementation defect"),
            _v2_approved(),
            _v2_approved(),
            _v2_approved(),
            _v2_approved(),
            _v2_approved(),
            _v2_changes("second distinct implementation defect"),
            _v2_approved(),
            _v2_approved(),
            _v2_approved(),
            _v2_approved(),
            _v2_approved(),
            _v2_approved(),
        ],
    )

    result = orch_module.execute_v2_unpublished_closure(
        _cp3_config(env),
        target,
        checkpoints,
        pre_closure,
        repair_acceptor=_cp4_repair_acceptor(env),
    )

    assert result.completed
    repair_prompts = [
        prompt
        for prompt in implementer_prompts
        if "CURRENT_REPAIR_GATE: mode-c-implementation-repair" in prompt
    ]
    assert len(repair_prompts) == 2
    assert sum("FINAL_CUMULATIVE_AUDIT" in p for p in reviewer_prompts) == 3
    assert result.closure_candidate is not None
    assert result.closure_candidate.published_predecessor_sha != implementation_head
    assert len(result.pre_closure_result.evidence.accepted_checkpoints) == 2


def test_v2_closure_only_repair_touching_source_blocks_unsafe_narrow_path(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    target, checkpoints, pre_closure, implementation_head = _prepared_cp4_context(
        env, spec
    )
    _install_cp4_agents(
        env,
        monkeypatch,
        [
            _v2_approved(),
            _changes_with_paths("closure defect", ("docs/TASK.md",)),
        ],
        source_during_second_closure=True,
    )

    result = orch_module.execute_v2_unpublished_closure(
        _cp3_config(env),
        target,
        checkpoints,
        pre_closure,
        repair_acceptor=_cp4_repair_acceptor(env),
    )

    assert not result.completed and not result.published
    assert "changed implementation content" in (result.blocked_reason or "")
    assert result.terminal_phase is Phase.CLOSURE_REVIEW
    repository.fetch_origin(env.work)
    assert repository.remote_branch_sha(env.work, "delivery") == implementation_head


def test_v2_required_ci_failure_blocks_only_after_exact_candidate_publication(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    target, checkpoints, pre_closure, _ = _prepared_cp4_context(env, spec)
    _install_cp4_agents(env, monkeypatch, [_v2_approved(), _v2_approved()])

    def failing_checks(
        repo: Path, pr_number: str, *, gh_command: tuple[str, ...]
    ) -> repository.RequiredChecksResult:
        repository.fetch_origin(repo)
        assert repository.remote_branch_sha(repo, "delivery") == repository.head_sha(repo)
        return repository.RequiredChecksResult(
            checks=[{"name": "build", "state": "FAILURE", "bucket": "fail"}],
            no_required_checks=False,
            returncode=1,
        )

    monkeypatch.setattr(repository, "pr_required_checks", failing_checks)

    result = orch_module.execute_v2_unpublished_closure(
        _cp3_config(env),
        target,
        checkpoints,
        pre_closure,
        repair_acceptor=_cp4_repair_acceptor(env),
    )

    assert not result.completed and result.published
    assert "required CI failed" in (result.blocked_reason or "")
    assert result.terminal_phase is Phase.REQUIRED_CI
    assert result.closure_candidate is not None
    assert repository.remote_branch_sha(env.work, "delivery") == result.closure_candidate.candidate_head_sha


def test_v2_post_publication_origin_move_reaudits_same_candidate_and_replays_ci(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    target, checkpoints, pre_closure, _ = _prepared_cp4_context(env, spec)
    _mock_cp3_revalidated_target(monkeypatch, target)
    reviewer_profiles: list[ComputeProfile] = []
    _install_cp4_agents(
        env,
        monkeypatch,
        [_v2_approved(), _v2_approved(), _v2_approved()],
        reviewer_profiles=reviewer_profiles,
    )
    recorded = _capture_recorded_review_attempts(monkeypatch)
    histories: list[GateHistory] = []
    real_checks = repository.pr_required_checks
    checks_count = 0
    moved_sha: str | None = None

    def move_base_after_first_ci(
        repo: Path, pr_number: str, *, gh_command: tuple[str, ...]
    ) -> repository.RequiredChecksResult:
        nonlocal checks_count, moved_sha
        checks_count += 1
        result = real_checks(repo, pr_number, gh_command=gh_command)
        if checks_count == 1:
            moved_sha = _advance_cp3_origin_main(env, "post-publication-base-move")
        return result

    monkeypatch.setattr(repository, "pr_required_checks", move_base_after_first_ci)

    result = orch_module.execute_v2_unpublished_closure(
        _cp3_config(env),
        target,
        checkpoints,
        pre_closure,
        repair_acceptor=_cp4_repair_acceptor(env),
        history_sink=histories,
    )

    assert result.completed and result.published
    assert checks_count == 2
    assert moved_sha is not None
    assert result.mode_c_evidence is not None
    assert result.mode_c_evidence.base_sha == moved_sha
    post_publication = [
        attempt
        for context, attempt in recorded
        if context.gate_id == "post-publication-mode-c-replay"
    ]
    assert len(post_publication) == 1
    assert post_publication[0].reviewer_verdict is ReviewVerdict.APPROVED
    assert post_publication[0].findings == ()
    post_publication_metrics = [
        metric
        for metric in orch_module._summarize_v2_review_histories(histories)
        if metric.gate_id == "post-publication-mode-c-replay"
    ]
    assert len(post_publication_metrics) == 1
    assert post_publication_metrics[0].last_reviewer_verdict is ReviewVerdict.APPROVED
    assert reviewer_profiles == [
        ComputeProfile.DELIBERATE,
        ComputeProfile.CRITICAL,
        ComputeProfile.CRITICAL,
    ]


def test_v2_post_publication_mode_c_cr_is_recorded_before_terminal_limitation(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    target, checkpoints, pre_closure, _ = _prepared_cp4_context(env, spec)
    _mock_cp3_revalidated_target(monkeypatch, target)
    review = _v2_changes("post-publication binding defect")
    _install_cp4_agents(
        env, monkeypatch, [_v2_approved(), _v2_approved(), review]
    )
    recorded = _capture_recorded_review_attempts(monkeypatch)
    histories: list[GateHistory] = []
    real_checks = repository.pr_required_checks
    checks_count = 0

    def move_base_after_first_ci(
        repo: Path, pr_number: str, *, gh_command: tuple[str, ...]
    ) -> repository.RequiredChecksResult:
        nonlocal checks_count
        checks_count += 1
        result = real_checks(repo, pr_number, gh_command=gh_command)
        if checks_count == 1:
            _advance_cp3_origin_main(env, "post-publication-cr-base-move")
        return result

    monkeypatch.setattr(repository, "pr_required_checks", move_base_after_first_ci)

    result = orch_module.execute_v2_unpublished_closure(
        _cp3_config(env),
        target,
        checkpoints,
        pre_closure,
        repair_acceptor=_cp4_repair_acceptor(env),
        history_sink=histories,
    )

    assert not result.completed and result.published
    assert "candidate-changing repair" in (result.blocked_reason or "")
    post_publication = [
        attempt
        for context, attempt in recorded
        if context.gate_id == "post-publication-mode-c-replay"
    ]
    assert len(post_publication) == 1
    attempt = post_publication[0]
    assert attempt.reviewer_verdict is ReviewVerdict.CHANGES_REQUESTED
    assert attempt.rejection_basis is CandidateRejectionBasis.CHANGES_REQUESTED
    assert review.repair_packet is not None
    assert attempt.findings == review.repair_packet.findings
    post_publication_metrics = [
        metric
        for metric in orch_module._summarize_v2_review_histories(histories)
        if metric.gate_id == "post-publication-mode-c-replay"
    ]
    assert len(post_publication_metrics) == 1
    assert post_publication_metrics[0].changes_requested_count == 1
    assert (
        post_publication_metrics[0].last_reviewer_verdict
        is ReviewVerdict.CHANGES_REQUESTED
    )


def test_v2_post_publication_tracker_movement_blocks_ready_for_human_merge(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    target, checkpoints, pre_closure, _ = _prepared_cp4_context(env, spec)
    _mock_cp3_revalidated_target(monkeypatch, target)
    _install_cp4_agents(env, monkeypatch, [_v2_approved(), _v2_approved()])
    real_checks = repository.pr_required_checks
    checks_count = 0

    def move_tracker_after_publication_ci(
        repo: Path, pr_number: str, *, gh_command: tuple[str, ...]
    ) -> repository.RequiredChecksResult:
        nonlocal checks_count
        checks_count += 1
        result = real_checks(repo, pr_number, gh_command=gh_command)
        if checks_count == 1:
            _advance_cp3_origin_main_tracker(
                env,
                "post-publication-tracker-move",
                "- **Next free ID:** TSK-9003",
            )
        return result

    monkeypatch.setattr(
        repository, "pr_required_checks", move_tracker_after_publication_ci
    )

    result = orch_module.execute_v2_unpublished_closure(
        _cp3_config(env),
        target,
        checkpoints,
        pre_closure,
        repair_acceptor=_cp4_repair_acceptor(env),
    )

    assert not result.completed and result.published
    assert checks_count == 1
    assert "prepared Task Closure is stale" in (result.blocked_reason or "")
    assert result.terminal_phase is Phase.ORIGIN_MAIN_REVALIDATION
