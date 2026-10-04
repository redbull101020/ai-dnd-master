import dataclasses
import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, replace
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
    BlockedReviewRationale,
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
    ReviewBlockerKind,
    ReviewVerdict,
    RunOutcome,
    RunResult,
    RoutingDecision,
    RoutingEscalationReason,
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


def test_verification_exact_python_uses_harness_interpreter_and_preserves_evidence(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _default_config(
        env,
        implementer_spec=_implementer_spec(env.work, ""),
        reviewer_spec=_reviewer_spec(env.work, ""),
    )
    original = ("python", "-m", "pytest", "tests/path with spaces.py", "-q")
    invocations: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(
        argv: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        invocations.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, stdout="passed", stderr="")

    monkeypatch.setattr(orch_module.subprocess, "run", fake_run)

    result = orch_module._run_one_verification_command(config, original)

    assert invocations == [
        (
            [sys.executable, *original[1:]],
            {
                "cwd": env.work,
                "capture_output": True,
                "text": True,
                "encoding": "utf-8",
                "timeout": config.verification_timeout_seconds,
                "check": False,
            },
        )
    ]
    assert result.command == original
    assert result.passed
    assert original == ("python", "-m", "pytest", "tests/path with spaces.py", "-q")
    formatted = orch_module._format_verification(
        VerificationEvidence(commands=(result,), passed=True, head_sha="head-sha")
    )
    assert "python -m pytest tests/path with spaces.py -q" in formatted
    assert sys.executable not in formatted


@pytest.mark.parametrize(
    "executable",
    ("python3", "python.exe", "py", str(Path(sys.executable).resolve()), "git"),
)
def test_verification_noncanonical_executables_are_not_rewritten(
    env: Env, monkeypatch: pytest.MonkeyPatch, executable: str
) -> None:
    config = _default_config(
        env,
        implementer_spec=_implementer_spec(env.work, ""),
        reviewer_spec=_reviewer_spec(env.work, ""),
    )
    original = (executable, "unchanged", "tail")
    invoked: list[list[str]] = []

    def fake_run(
        argv: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        invoked.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(orch_module.subprocess, "run", fake_run)

    result = orch_module._run_one_verification_command(config, original)

    assert invoked == [list(original)]
    assert result.command == original


@pytest.mark.parametrize("startup_error", (FileNotFoundError, PermissionError))
def test_verification_harness_interpreter_startup_failure_has_no_fallback(
    env: Env,
    monkeypatch: pytest.MonkeyPatch,
    startup_error: type[OSError],
) -> None:
    config = _default_config(
        env,
        implementer_spec=_implementer_spec(env.work, ""),
        reviewer_spec=_reviewer_spec(env.work, ""),
    )
    original = ("python", "-m", "pytest")
    attempted: list[tuple[list[str], dict[str, object]]] = []
    missing_interpreter = str(env.scratch / "missing-python")

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        attempted.append((argv, kwargs))
        raise startup_error("unusable harness interpreter")

    monkeypatch.setattr(orch_module.sys, "executable", missing_interpreter)
    monkeypatch.setattr(orch_module.subprocess, "run", fake_run)

    result = orch_module._run_one_verification_command(config, original)

    assert len(attempted) == 1
    assert attempted[0][0] == [missing_interpreter, "-m", "pytest"]
    assert "env" not in attempted[0][1]
    assert "shell" not in attempted[0][1]
    assert result.command == original
    assert result.returncode == -1
    assert not result.passed


def test_checkpoint_and_full_verification_share_python_materialization(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _default_config(
        env,
        implementer_spec=_implementer_spec(env.work, ""),
        reviewer_spec=_reviewer_spec(env.work, ""),
    )
    checkpoint_command = ("python", "-c", "print('checkpoint')")
    full_command = ("python", "-c", "print('full')")
    base_spec = _v2_spec()
    spec = dataclasses.replace(
        base_spec,
        checkpoints=(
            dataclasses.replace(
                base_spec.checkpoints[0], verification=(checkpoint_command,)
            ),
        ),
        full_verification=(full_command,),
    )
    runtime_commands: list[list[str]] = []

    def fake_run(
        argv: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        runtime_commands.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    fingerprint = repository.RepositoryFingerprint(
        branch="delivery", head_sha="head-sha", content_digest="content-digest"
    )
    monkeypatch.setattr(repository, "capture_fingerprint", lambda repo: fingerprint)
    monkeypatch.setattr(
        repository, "verify_fingerprint_unchanged", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(orch_module.subprocess, "run", fake_run)

    checkpoint_evidence = orch_module._run_verification_commands(
        config, spec.checkpoints[0].verification
    )
    full_evidence = orch_module._run_verification_commands(
        config, spec.full_verification
    )

    assert runtime_commands == [
        [sys.executable, *checkpoint_command[1:]],
        [sys.executable, *full_command[1:]],
    ]
    assert checkpoint_evidence.commands[0].command == checkpoint_command
    assert full_evidence.commands[0].command == full_command


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


def _public_dispatch_closure_validation_repair_implementer_code(
    task_id: str,
) -> str:
    return (
        "import pathlib, sys\n"
        "prompt = sys.stdin.read()\n"
        f"assert 'selected_task_id: {task_id}' in prompt\n"
        "if 'CURRENT_GATE: prospective Task Closure\\n' in prompt:\n"
        "    task = pathlib.Path('docs/TASK.md')\n"
        "    text = task.read_bytes().decode('utf-8')\n"
        "    eol = '\\r\\n' if '\\r\\n' in text else '\\n'\n"
        "    separator = ('| ID | Status | Evidence | Title |' + eol "
        "+ '| --- | --- | --- | --- |' + eol)\n"
        f"    wrong = '| `{task_id}` | `Done` | draft PR #1 | Public run integration |' + eol\n"
        f"    valid = '| `{task_id}` | `Done` | PR #1 | Public run integration |' + eol\n"
        "    if wrong in text:\n"
        "        assert 'CURRENT_CLOSURE_VALIDATION_FAILURE:\\n(none)' not in prompt\n"
        "        task.write_bytes(text.replace(wrong, valid, 1).encode('utf-8'))\n"
        "    else:\n"
        "        assert valid not in text and separator in text\n"
        "        assert 'CURRENT_CLOSURE_VALIDATION_FAILURE:\\n(none)' in prompt\n"
        "        task.write_bytes(text.replace(separator, separator + wrong, 1).encode('utf-8'))\n"
        "        log = pathlib.Path('docs/DEVELOPMENT_LOG.md')\n"
        "        log.write_text(log.read_text(encoding='utf-8') + "
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


def _fast_forward_public_work_to_origin_main(env: PublicDispatchEnv) -> None:
    _run_git(["fetch", "origin"], cwd=env.work)
    _run_git(["merge", "-q", "--ff-only", "origin/main"], cwd=env.work)


def _runtime_mismatch_result(
    env: PublicDispatchEnv, monkeypatch: pytest.MonkeyPatch
) -> RunResult:
    downstream_calls: list[str] = []

    def forbidden(name: str) -> Callable[..., object]:
        def fail(*args: object, **kwargs: object) -> object:
            downstream_calls.append(name)
            raise AssertionError(f"{name} must not be called")

        return fail

    monkeypatch.setattr(
        orch_module, "_resolve_file_based_target", forbidden("task selection")
    )
    for name in (
        "require_branch_name_available",
        "require_no_open_pr_for_task",
        "create_delivery_branch_from_sha",
        "commit_reviewed_checkpoint",
        "push_delivery_branch",
    ):
        monkeypatch.setattr(repository, name, forbidden(name))

    agent_marker = env.work / "runtime-mismatch-agent-called"
    gh_log = env.work.parent / "runtime-mismatch-gh.jsonl"
    fail_agent = (
        "import pathlib\n"
        f"pathlib.Path({str(agent_marker)!r}).write_text('called', encoding='utf-8')\n"
    )
    config = dataclasses.replace(
        _public_dispatch_config(env, selector=_TASK_ID),
        implementer_profiles=_profiles(_implementer_spec(env.work, fail_agent)),
        reviewer_profiles=_profiles(_reviewer_spec(env.work, fail_agent)),
        gh_command=_public_dispatch_gh_command(_TASK_ID, command_log=gh_log),
    )

    result = run(config)

    assert downstream_calls == []
    assert not agent_marker.exists()
    assert not gh_log.exists()
    assert result.task_id is None
    assert result.delivery_branch is None
    assert result.head_sha is None
    assert result.routing_decisions == ()
    assert result.review_metrics == ()
    assert _run_git(
        ["branch", "--list", f"autonomous-pr/{_TASK_ID.lower()}"], cwd=env.work
    ) == ""
    return result


def test_initial_runtime_preflight_blocks_clean_behind_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _make_public_dispatch_env(tmp_path)
    actual_sha = repository.head_sha(env.work)
    (env.seed / "README.md").write_text("advanced origin\n", encoding="utf-8")
    _commit_and_push_main(env.seed, "advance origin main", "README.md")
    expected_sha = repository.head_sha(env.seed)

    result = _runtime_mismatch_result(env, monkeypatch)

    assert result.outcome is RunOutcome.BLOCKED
    assert result.phase is Phase.PREFLIGHT
    assert result.blocked_reason is not None
    assert f"actual {actual_sha}" in result.blocked_reason
    assert f"expected {expected_sha}" in result.blocked_reason
    assert "update the selected local checkout outside this completed invocation" in (
        result.blocked_reason
    )
    assert "new explicit AUTONOMOUS_PR invocation" in result.blocked_reason
    assert repository.head_sha(env.work) == actual_sha
    assert repository.origin_main_sha(env.work) == expected_sha


def test_initial_runtime_preflight_blocks_clean_ahead_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _make_public_dispatch_env(tmp_path)
    expected_sha = repository.origin_main_sha(env.work)
    (env.work / "local-runtime-change.txt").write_text("ahead\n", encoding="utf-8")
    _run_git(["add", "local-runtime-change.txt"], cwd=env.work)
    _run_git(["commit", "-q", "-m", "local runtime ahead"], cwd=env.work)
    actual_sha = repository.head_sha(env.work)

    result = _runtime_mismatch_result(env, monkeypatch)

    assert result.outcome is RunOutcome.BLOCKED
    assert result.phase is Phase.PREFLIGHT
    assert result.blocked_reason is not None
    assert f"actual {actual_sha}" in result.blocked_reason
    assert f"expected {expected_sha}" in result.blocked_reason
    assert repository.head_sha(env.work) == actual_sha
    assert repository.origin_main_sha(env.work) == expected_sha


def test_initial_runtime_preflight_allows_differently_named_exact_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _make_public_dispatch_env(tmp_path)
    _run_git(["switch", "-q", "-c", "alternate-runtime"], cwd=env.work)
    selection_calls: list[tuple[str, str]] = []

    def stop_after_runtime_guard(
        config: OrchestratorConfig, selector: str, source_sha: str
    ) -> NoEligibleTask:
        selection_calls.append((selector, source_sha))
        raise repository.RepositoryError("controlled stop after runtime guard")

    monkeypatch.setattr(
        orch_module, "_resolve_file_based_target", stop_after_runtime_guard
    )

    result = run(_public_dispatch_config(env, selector=_TASK_ID))

    exact_sha = repository.head_sha(env.work)
    assert selection_calls == [(_TASK_ID, exact_sha)]
    assert result.outcome is RunOutcome.BLOCKED
    assert result.phase is Phase.PREFLIGHT
    assert result.blocked_reason == "controlled stop after runtime guard"
    assert repository.current_branch(env.work) == "alternate-runtime"
    assert repository.origin_main_sha(env.work) == exact_sha


def test_dirty_worktree_blocks_before_runtime_head_identity_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _make_public_dispatch_env(tmp_path)
    (env.work / "dirty.txt").write_text("dirty\n", encoding="utf-8")
    monkeypatch.setattr(
        repository,
        "head_sha",
        lambda repo: (_ for _ in ()).throw(
            AssertionError("HEAD must not be read for dirty preflight")
        ),
    )
    monkeypatch.setattr(
        orch_module,
        "_resolve_file_based_target",
        lambda *args: (_ for _ in ()).throw(
            AssertionError("task selection must not run for dirty preflight")
        ),
    )

    result = run(_public_dispatch_config(env, selector=_TASK_ID))

    assert result.outcome is RunOutcome.BLOCKED
    assert result.phase is Phase.PREFLIGHT
    assert result.blocked_reason == "working tree/index is not clean before v2 preflight"
    assert result.task_id is None
    assert result.delivery_branch is None
    assert result.routing_decisions == ()


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
    head_shas = iter((base_sha,))
    monkeypatch.setattr(
        repository, "head_sha", lambda repo: next(head_shas, head_sha)
    )
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


def test_public_run_repairs_pr129_closure_validation_incident_to_ready_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _make_public_dispatch_env(tmp_path)
    reviewer_code = "import sys\nsys.stdin.read()\nprint('APPROVED')\n"
    config = OrchestratorConfig(
        task_id=_TASK_ID,
        repo=env.work,
        implementer_profiles=_profiles(
            _implementer_spec(
                env.work,
                _public_dispatch_closure_validation_repair_implementer_code(
                    _TASK_ID
                ),
            )
        ),
        reviewer_profiles=_profiles(_reviewer_spec(env.work, reviewer_code)),
        delivery_branch="",
        gh_command=_public_dispatch_gh_command(_TASK_ID),
    )
    routed: list[tuple[AgentRole, AgentWorkKind, ComputeProfile]] = []
    implementer_prompts: list[str] = []
    reviewer_prompts: list[str] = []
    retained_histories: list[GateHistory] = []
    real_route_agent_work = orch_module.route_agent_work
    real_implementer = orch_module.run_implementer
    real_reviewer = orch_module.run_structured_reviewer
    real_retain = orch_module._retain_v2_gate_history

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
        routed.append((decision.role, decision.work_kind, decision.selected_profile))
        return decision

    def observe_implementer(
        spec: AgentInvocationSpec, prompt: str
    ) -> AgentInvocationResult:
        implementer_prompts.append(prompt)
        return real_implementer(spec, prompt)

    def observe_reviewer(
        spec: AgentInvocationSpec, prompt: str
    ) -> StructuredReviewResult:
        reviewer_prompts.append(prompt)
        return real_reviewer(spec, prompt)

    def observe_history(
        history: GateHistory, history_sink: list[GateHistory] | None
    ) -> GateHistory:
        retained_histories.append(history)
        return real_retain(history, history_sink)

    monkeypatch.setattr(orch_module, "route_agent_work", observe_route)
    monkeypatch.setattr(orch_module, "run_implementer", observe_implementer)
    monkeypatch.setattr(orch_module, "run_structured_reviewer", observe_reviewer)
    monkeypatch.setattr(orch_module, "_retain_v2_gate_history", observe_history)

    result = run(config)

    expected_routing = [
        (AgentRole.IMPLEMENTER, AgentWorkKind.CHECKPOINT_IMPLEMENTATION, ComputeProfile.ROUTINE),
        (AgentRole.REVIEWER, AgentWorkKind.CHECKPOINT_REVIEW, ComputeProfile.DELIBERATE),
        (AgentRole.REVIEWER, AgentWorkKind.PRE_CLOSURE_CUMULATIVE_REVIEW, ComputeProfile.CRITICAL),
        (AgentRole.IMPLEMENTER, AgentWorkKind.TASK_CLOSURE_PREPARATION, ComputeProfile.ROUTINE),
        (AgentRole.IMPLEMENTER, AgentWorkKind.TASK_CLOSURE_REPAIR, ComputeProfile.DELIBERATE),
        (AgentRole.REVIEWER, AgentWorkKind.TASK_CLOSURE_REVIEW, ComputeProfile.DELIBERATE),
        (AgentRole.REVIEWER, AgentWorkKind.MODE_C_REVIEW, ComputeProfile.CRITICAL),
    ]
    assert result.outcome is RunOutcome.STOP
    assert result.phase is Phase.READY_FOR_HUMAN_MERGE
    assert result.blocked_reason is None
    assert routed == expected_routing
    assert [
        (record.role, record.work_kind, record.selected_profile)
        for record in result.routing_decisions
    ] == expected_routing
    repair_record = next(
        record
        for record in result.routing_decisions
        if record.work_kind is AgentWorkKind.TASK_CLOSURE_REPAIR
    )
    assert (
        RoutingEscalationReason.REPEATED_VERIFICATION_REJECTION
        not in repair_record.escalation_reasons
    )

    closure_implementer_prompts = [
        prompt
        for prompt in implementer_prompts
        if "CURRENT_GATE: prospective Task Closure\n" in prompt
    ]
    closure_reviewer_prompts = [
        prompt
        for prompt in reviewer_prompts
        if "CURRENT_GATE: prospective Task Closure review\n" in prompt
    ]
    assert len(closure_implementer_prompts) == 2
    assert "CURRENT_CLOSURE_VALIDATION_FAILURE:\n(none)\n" in (
        closure_implementer_prompts[0]
    )
    assert "CURRENT_CLOSURE_VALIDATION_FAILURE:\n1. invalid terminal-only" in (
        closure_implementer_prompts[1]
    )
    assert len(closure_reviewer_prompts) == 1

    closure_history = next(
        history
        for history in retained_histories
        if history.context.gate_id == "prospective-task-closure"
    )
    assert closure_history.review_iteration == 1
    assert closure_history.previous_reviewed_candidate_identity is None
    assert closure_history.previous_reviewed_candidate_state is None
    assert len(closure_history.attempts) == 2
    rejected, approved = closure_history.attempts
    assert (
        rejected.rejection_basis
        is CandidateRejectionBasis.CLOSURE_VALIDATION_FAILURE
    )
    assert rejected.review_iteration is None
    assert rejected.reviewer_verdict is None
    assert approved.review_iteration == 1
    assert approved.reviewer_verdict is ReviewVerdict.APPROVED

    closure_metric = next(
        metric
        for metric in result.review_metrics
        if metric.gate_id == "prospective-task-closure"
    )
    assert closure_metric.review_iterations == 1
    assert closure_metric.verification_rejection_count == 0
    assert result.head_sha == _run_git(["rev-parse", "HEAD"], cwd=env.work).strip()
    assert result.head_sha == _run_git(
        ["rev-parse", f"origin/autonomous-pr/{_TASK_ID.lower()}"], cwd=env.work
    ).strip()
    terminal = task_context.parse_terminal_registry(
        (env.work / "docs" / "TASK.md").read_text(encoding="utf-8")
    )
    assert terminal.tasks[-1].evidence == "PR #1"


def test_public_run_preserves_metrics_on_explicit_reviewer_blocked(
    tmp_path: Path,
) -> None:
    env = _make_public_dispatch_env(tmp_path)
    rationale = json.dumps(
        {
            "binding_bases": ["task:scope"],
            "blocker_kind": "missing_scope",
            "problem": "The fixed scope omits a required boundary.",
            "evidence_reference": "Task Scope",
            "blocking_gap": "The required boundary is not specified.",
            "required_resolution": "Refine and approve the task scope.",
        }
    )
    reviewer_code = (
        "import sys\nsys.stdin.read()\nprint('BLOCKED')\n"
        f"print({rationale!r})\n"
    )
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
    assert metric.binding_bases_per_review == ((),)
    assert metric.last_reviewer_verdict is ReviewVerdict.BLOCKED
    assert len(result.blocked_reviews) == 1
    diagnostic = result.blocked_reviews[0]
    assert diagnostic.gate_id == "CP-1"
    assert diagnostic.review_iteration == 1
    assert diagnostic.rationale.blocker_kind is ReviewBlockerKind.MISSING_SCOPE
    assert diagnostic.rationale.binding_bases == ("task:scope",)
    assert [decision.sequence for decision in result.routing_decisions] == [1, 2]
    assert result.routing_decisions[-1].role is AgentRole.REVIEWER
    assert result.routing_decisions[-1].work_kind is AgentWorkKind.CHECKPOINT_REVIEW


@pytest.mark.parametrize(
    ("prompt_marker", "expected_gate", "expected_phase"),
    [
        (
            "REVIEW_PURPOSE: PRE_CLOSURE_CUMULATIVE_REVIEW",
            "pre-closure-cumulative-review",
            Phase.PRE_CLOSURE_CUMULATIVE_REVIEW,
        ),
        (
            "GATE_APPLICABILITY: PROSPECTIVE_TASK_CLOSURE",
            "prospective-task-closure",
            Phase.CLOSURE_REVIEW,
        ),
        (
            "REVIEW_PURPOSE: FINAL_CUMULATIVE_AUDIT",
            "mode-c-final-cumulative-audit",
            Phase.MODE_C_FINAL_AUDIT,
        ),
    ],
)
def test_public_run_preserves_blocked_rationale_from_late_operational_gates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    prompt_marker: str,
    expected_gate: str,
    expected_phase: Phase,
) -> None:
    env = _make_public_dispatch_env(tmp_path)
    blocked = _v2_explicit_blocked("late gate blocked")
    recorded = _capture_recorded_review_attempts(monkeypatch)

    def reviewer(
        spec: AgentInvocationSpec, prompt: str
    ) -> StructuredReviewResult:
        return blocked if prompt_marker in prompt else _v2_approved()

    monkeypatch.setattr(orch_module, "run_structured_reviewer", reviewer)

    result = run(_public_dispatch_config(env, selector=_TASK_ID))

    assert result.outcome is RunOutcome.BLOCKED
    assert result.phase is expected_phase
    assert len(result.blocked_reviews) == 1
    diagnostic = result.blocked_reviews[0]
    assert diagnostic.gate_id == expected_gate
    assert diagnostic.review_iteration == 1
    assert diagnostic.rationale is blocked.blocked_rationale
    blocked_attempts = [
        attempt
        for _, attempt in recorded
        if attempt.reviewer_verdict is ReviewVerdict.BLOCKED
    ]
    assert len(blocked_attempts) == 1
    assert diagnostic.candidate_identity == blocked_attempts[0].candidate_identity
    assert blocked_attempts[0].blocked_rationale is blocked.blocked_rationale
    assert not blocked_attempts[0].rejected
    assert blocked_attempts[0].rejection_basis is None
    assert blocked_attempts[0].findings == ()
    assert blocked_attempts[0].repair_packet is None
    metric = next(
        metric for metric in result.review_metrics if metric.gate_id == expected_gate
    )
    assert metric.findings_per_review == (0,)
    assert metric.binding_bases_per_review == ((),)
    if expected_gate == "mode-c-final-cumulative-audit":
        assert result.delivery_branch is not None
        assert result.head_sha != repository.remote_branch_sha(
            env.work, result.delivery_branch
        )


def test_public_run_discards_stale_explicit_blocked_before_canonical_recording(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _make_public_dispatch_env(tmp_path)
    blocked = _v2_explicit_blocked("stale cumulative review blocked")
    recorded = _capture_recorded_review_attempts(monkeypatch)
    cumulative_reviews = 0

    def reviewer(
        spec: AgentInvocationSpec, prompt: str
    ) -> StructuredReviewResult:
        nonlocal cumulative_reviews
        if "REVIEW_PURPOSE: PRE_CLOSURE_CUMULATIVE_REVIEW" in prompt:
            cumulative_reviews += 1
            if cumulative_reviews == 1:
                path = env.seed / "unrelated.txt"
                path.write_text("move after stale review\n", encoding="utf-8")
                _commit_and_push_main(
                    env.seed, "move after stale review", "unrelated.txt"
                )
                return blocked
        return _v2_approved()

    monkeypatch.setattr(orch_module, "run_structured_reviewer", reviewer)

    result = run(_public_dispatch_config(env, selector=_TASK_ID))

    assert result.outcome is RunOutcome.STOP
    assert cumulative_reviews == 2
    assert result.blocked_reviews == ()
    assert not any(
        attempt.reviewer_verdict is ReviewVerdict.BLOCKED
        for _, attempt in recorded
    )
    cumulative_metrics = [
        metric
        for metric in result.review_metrics
        if metric.gate_id == "pre-closure-cumulative-review"
    ]
    assert len(cumulative_metrics) == 1
    assert cumulative_metrics[0].review_iterations == 1
    assert cumulative_metrics[0].last_reviewer_verdict is ReviewVerdict.APPROVED


def test_public_run_preserves_post_publication_mode_c_blocked_rationale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _make_public_dispatch_env(tmp_path)
    blocked = _v2_explicit_blocked("post-publication Mode C blocked")
    recorded = _capture_recorded_review_attempts(monkeypatch)
    mode_c_reviews = 0

    def reviewer(
        spec: AgentInvocationSpec, prompt: str
    ) -> StructuredReviewResult:
        nonlocal mode_c_reviews
        if "REVIEW_PURPOSE: FINAL_CUMULATIVE_AUDIT" in prompt:
            mode_c_reviews += 1
            if mode_c_reviews == 2:
                return blocked
        return _v2_approved()

    real_checks = repository.pr_required_checks
    checks_count = 0

    def checks_then_move_main(
        repo: Path, pr_number: str, *, gh_command: tuple[str, ...]
    ) -> repository.RequiredChecksResult:
        nonlocal checks_count
        checks_count += 1
        result = real_checks(repo, pr_number, gh_command=gh_command)
        if checks_count == 1:
            path = env.seed / "unrelated.txt"
            path.write_text("post-publication main movement\n", encoding="utf-8")
            _commit_and_push_main(
                env.seed, "post-publication main movement", "unrelated.txt"
            )
        return result

    monkeypatch.setattr(orch_module, "run_structured_reviewer", reviewer)
    monkeypatch.setattr(repository, "pr_required_checks", checks_then_move_main)

    result = run(_public_dispatch_config(env, selector=_TASK_ID))

    assert result.outcome is RunOutcome.BLOCKED
    assert result.phase is Phase.MODE_C_FINAL_AUDIT
    assert mode_c_reviews == 2
    assert checks_count == 1
    assert len(result.blocked_reviews) == 1
    diagnostic = result.blocked_reviews[0]
    assert diagnostic.gate_id == "post-publication-mode-c-replay"
    assert diagnostic.review_iteration == 1
    assert diagnostic.rationale is blocked.blocked_rationale
    blocked_attempts = [
        attempt
        for context, attempt in recorded
        if context.gate_id == "post-publication-mode-c-replay"
        and attempt.reviewer_verdict is ReviewVerdict.BLOCKED
    ]
    assert len(blocked_attempts) == 1
    assert diagnostic.candidate_identity == blocked_attempts[0].candidate_identity
    assert result.delivery_branch is not None
    assert result.head_sha == repository.remote_branch_sha(
        env.work, result.delivery_branch
    )
    mode_c_decisions = [
        decision
        for decision in result.routing_decisions
        if decision.work_kind is AgentWorkKind.MODE_C_REVIEW
    ]
    assert len(mode_c_decisions) == 2
    assert result.routing_decisions[-1].work_kind is AgentWorkKind.MODE_C_REVIEW


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
    assert result.blocked_reviews == ()
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
    _fast_forward_public_work_to_origin_main(env)

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
    _fast_forward_public_work_to_origin_main(env)

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
    _fast_forward_public_work_to_origin_main(env)

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
    _fast_forward_public_work_to_origin_main(env)
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
    monkeypatch.setattr(repository, "head_sha", lambda repo: base_sha)
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


def _blocked_rationale() -> BlockedReviewRationale:
    return BlockedReviewRationale(
        binding_bases=("task:scope", "repo:AGENTS.md review authority"),
        blocker_kind=ReviewBlockerKind.MISSING_DECISION,
        problem="Two binding requirements require an absent decision.",
        evidence_reference="Task Scope and AGENTS.md review authority",
        blocking_gap="The fixed contract does not choose either behavior.",
        required_resolution="Refine and approve the task contract.",
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
        blocked_rationale=_blocked_rationale(),
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
    built_patches: list[str] = []

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
        built_patches.append(diff)
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
        assert spec.cwd is not None
        assert spec.cwd.resolve() != env.work.resolve()
        assert (spec.cwd / ".git").is_dir()
        assert _run_git(["remote"], cwd=spec.cwd) == ""
        reviewer_profiles.append(ComputeProfile(spec.args[-1].upper()))
        artifact = built_patches[-1]
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


def test_v2_checkpoint_rename_of_fixed_spec_blocks_before_review(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _v2_spec()
    spec_path = env.work / spec.path
    renamed_path = spec_path.with_name("renamed-task.md")
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text(spec.text, encoding="utf-8")
    _run_git(["add", spec.path], cwd=env.work)
    _run_git(["commit", "-q", "-m", "track fixed task spec"], cwd=env.work)
    original_head = _run_git(["rev-parse", "HEAD"], cwd=env.work).strip()
    reviewer_calls = 0
    acceptor_calls = 0

    def implement(*args: object, **kwargs: object) -> AgentInvocationResult:
        spec_path.rename(renamed_path)
        return AgentInvocationResult("done", "", 0, False)

    def review(*args: object, **kwargs: object) -> StructuredReviewResult:
        nonlocal reviewer_calls
        reviewer_calls += 1
        return _v2_approved()

    def accept(*args: object, **kwargs: object) -> str:
        nonlocal acceptor_calls
        acceptor_calls += 1
        return "unexpected"

    monkeypatch.setattr(orch_module, "_run_routed_v2_implementer", implement)
    monkeypatch.setattr(orch_module, "_run_routed_v2_designated_review", review)

    result = execute_v2_checkpoints(
        _cp3_config(env),
        spec,
        accepted_base_context_identity=original_head,
        checkpoint_acceptor=accept,
    )

    assert not result.completed
    assert "fixed Task Execution Spec" in (result.blocked_reason or "")
    assert repository.changed_paths(env.work) == (
        "docs/tasks/TSK-9001.md",
        "docs/tasks/renamed-task.md",
    )
    assert reviewer_calls == 0
    assert acceptor_calls == 0
    assert _run_git(["rev-parse", "HEAD"], cwd=env.work).strip() == original_head


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
    for prompt in (first, second):
        for field in (
            "binding_bases",
            "blocker_kind",
            "problem",
            "evidence_reference",
            "blocking_gap",
            "required_resolution",
        ):
            assert field in prompt
        for blocker_kind in (
            "missing_decision",
            "missing_scope",
            "missing_architecture_contract",
            "missing_dependency",
            "missing_information",
        ):
            assert blocker_kind in prompt
        assert "BLOCKED is terminal" in prompt
        assert "not a repairable CHANGES_REQUESTED" in prompt
        assert "Missing, unknown, or duplicate keys are invalid" in prompt
        assert "ordered list of 1 to 8 unique strings" in prompt
        assert "at most 1024 characters" in prompt
        assert "Leading or trailing whitespace is invalid" in prompt
        assert "not a place to copy the Task Execution Spec" in prompt


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
        execution_target, "closure diff", "{}\n", history
    )
    mode_c_prompt = orch_module._build_v2_mode_c_review_input(
        execution_target, candidate, patch, history, "{}\n"
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
        assert "BLOCKED must be followed by exactly one JSON object" in prompt
        assert "evidence_reference is a concise locator or description" in prompt
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
    assert "AUTHORITATIVE_MODE_C_EVIDENCE_JSON:\n{}\n" in mode_c_prompt
    assert "do not replace a fresh, independent Mode C material review" in mode_c_prompt


def test_v2_checkpoint_reviewer_uses_embedded_current_patch_as_authoritative() -> None:
    spec = _v2_spec()
    patch_text = "diff --git a/source.py b/source.py\n+embedded sentinel\n"
    verification = dataclasses.replace(_v2_verification(True), head_sha="h" * 40)

    prompt = orch_module._build_v2_reviewer_input(
        spec,
        spec.checkpoints[0],
        patch_text,
        verification,
        review_iteration=1,
        previous_packet=None,
        repair_delta=None,
        require_non_convergence=False,
    )

    assert f"CURRENT_PATCH:\n{patch_text}\n" in prompt
    assert "CURRENT_PATCH supplied in this prompt is the exact authoritative" in prompt
    assert "Review that supplied text directly" in prompt
    assert "do not require reopening repository-root review.patch" in prompt
    assert "Repository inspection commands are for contextual source" in prompt
    assert "orchestrator-owned audit artifact and byte-identity guard" in prompt
    assert "PASSING_VERIFICATION:" in prompt


@pytest.mark.parametrize(
    "review",
    [
        _v2_approved(),
        _v2_changes("repairable defect"),
        _v2_explicit_blocked("missing approved decision"),
        _v2_blocked("reviewer process exited with status 1"),
    ],
    ids=("approved", "changes-requested", "explicit-blocked", "process-failure"),
)
def test_v2_designated_review_uses_disposable_workspace_and_always_cleans_up(
    env: Env,
    monkeypatch: pytest.MonkeyPatch,
    review: StructuredReviewResult,
) -> None:
    candidate = env.work / "candidate.txt"
    candidate.write_text("authoritative candidate\n", encoding="utf-8")
    patch = repository.build_checkpoint_patch_uncommitted(env.work)
    reviewer_environment = {
        **_FAKE_AGENT_ENV,
        "GH_TOKEN": "must-not-reach-reviewer",
        "GITHUB_TOKEN": "must-not-reach-reviewer",
        "GIT_ASKPASS": "must-not-reach-reviewer",
        "GIT_CONFIG_PARAMETERS": "must-not-reach-reviewer",
        "GIT_SSH": "must-not-reach-reviewer",
        "GIT_SSH_COMMAND": "must-not-reach-reviewer",
        "SSH_AGENT_PID": "must-not-reach-reviewer",
        "SSH_AUTH_SOCK": "must-not-reach-reviewer",
        "CODEX_HOME": "preserved-codex-auth-home",
    }
    config = _default_config(
        env,
        implementer_spec=_implementer_spec(env.work, "print('unused')"),
        reviewer_spec=replace(
            _reviewer_spec(env.work, "print('unused')"),
            env=reviewer_environment,
        ),
    )
    authoritative_bytes = candidate.read_bytes()
    fingerprint_before = repository.capture_fingerprint(env.work)
    reviewer_workspaces: list[Path] = []
    fingerprint_guards: list[str] = []
    patch_guards: list[Path] = []
    real_verify_fingerprint = repository.verify_fingerprint_unchanged
    real_verify_patch = repository.verify_materialized_review_patch
    def verify_fingerprint(
        repo_path: Path,
        expected: repository.RepositoryFingerprint,
        *,
        context: str,
    ) -> None:
        fingerprint_guards.append(context)
        real_verify_fingerprint(repo_path, expected, context=context)

    def verify_patch(repo_path: Path, expected: repository.ReviewPatch) -> None:
        patch_guards.append(repo_path)
        real_verify_patch(repo_path, expected)

    def fake_reviewer(
        spec: AgentInvocationSpec, review_input: str
    ) -> StructuredReviewResult:
        assert spec.cwd is not None
        reviewer_workspaces.append(spec.cwd)
        assert spec.cwd.resolve() != env.work.resolve()
        assert (spec.cwd / ".git").is_dir()
        common_dir_value = Path(
            _run_git(["rev-parse", "--git-common-dir"], cwd=spec.cwd).strip()
        )
        common_dir = (
            common_dir_value
            if common_dir_value.is_absolute()
            else spec.cwd / common_dir_value
        ).resolve()
        assert common_dir.is_relative_to(spec.cwd.resolve())
        assert not common_dir.is_relative_to((env.work / ".git").resolve())
        assert _run_git(["remote"], cwd=spec.cwd) == ""
        assert spec.env is not None
        casefolded_env = {key.casefold(): value for key, value in spec.env.items()}
        for forbidden in (
            "gh_token",
            "github_token",
            "git_askpass",
            "git_config_parameters",
            "git_ssh",
            "git_ssh_command",
            "ssh_agent_pid",
            "ssh_auth_sock",
        ):
            assert forbidden not in casefolded_env
        assert casefolded_env["codex_home"] == "preserved-codex-auth-home"
        assert Path(casefolded_env["gh_config_dir"]).is_relative_to(spec.cwd)
        assert casefolded_env["gh_prompt_disabled"] == "1"
        assert casefolded_env["git_terminal_prompt"] == "0"
        assert casefolded_env["gcm_interactive"] == "Never"
        assert casefolded_env["git_config_nosystem"] == "1"
        assert casefolded_env["git_config_global"] == os.devnull
        assert casefolded_env["git_config_key_0"] == "credential.helper"
        assert casefolded_env["git_config_value_0"] == ""
        assert (spec.cwd / "candidate.txt").read_bytes() == authoritative_bytes
        assert f"CURRENT_PATCH:\n{patch.diff_text}\n" in review_input
        (spec.cwd / "candidate.txt").write_text(
            "disposable reviewer mutation\n", encoding="utf-8"
        )
        return review

    monkeypatch.setattr(repository, "verify_fingerprint_unchanged", verify_fingerprint)
    monkeypatch.setattr(repository, "verify_materialized_review_patch", verify_patch)
    monkeypatch.setattr(orch_module, "run_structured_reviewer", fake_reviewer)

    actual = orch_module._run_v2_designated_review(
        config,
        f"CURRENT_PATCH:\n{patch.diff_text}\n",
        patch,
        context="designated reviewer invocation",
    )

    assert actual is review
    assert len(reviewer_workspaces) == 1
    assert not reviewer_workspaces[0].parent.exists()
    assert candidate.read_bytes() == authoritative_bytes
    assert repository.capture_fingerprint(env.work) == fingerprint_before
    assert len(fingerprint_guards) == 2
    assert len(patch_guards) == 2


def test_v2_designated_review_preparation_and_cleanup_failures_are_fail_closed(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch = repository.build_checkpoint_patch_uncommitted(env.work)
    config = _default_config(
        env,
        implementer_spec=_implementer_spec(env.work, "print('unused')"),
        reviewer_spec=_reviewer_spec(env.work, "print('unused')"),
    )
    reviewer_calls: list[str] = []

    class FailingWorkspace:
        def __init__(self, failure_point: str) -> None:
            self.failure_point = failure_point

        def __enter__(self) -> Path:
            if self.failure_point == "preparation":
                raise repository.RepositoryError("workspace preparation failed")
            return env.scratch

        def __exit__(self, *args: object) -> None:
            raise repository.RepositoryError("workspace cleanup failed")

    monkeypatch.setattr(
        orch_module,
        "run_structured_reviewer",
        lambda *args: reviewer_calls.append("called") or _v2_approved(),
    )

    monkeypatch.setattr(
        repository,
        "isolated_reviewer_workspace",
        lambda repo: FailingWorkspace("preparation"),
    )
    with pytest.raises(repository.RepositoryError, match="preparation failed"):
        orch_module._run_v2_designated_review(
            config, "review input", patch, context="review"
        )
    assert reviewer_calls == []

    monkeypatch.setattr(
        repository,
        "isolated_reviewer_workspace",
        lambda repo: FailingWorkspace("cleanup"),
    )
    with pytest.raises(repository.RepositoryError, match="cleanup failed"):
        orch_module._run_v2_designated_review(
            config, "review input", patch, context="review"
        )
    assert reviewer_calls == ["called"]


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
        target, pre_closure, "108", "{}\n", None, None
    )
    closure_repair = orch_module._build_v2_closure_prompt(
        target, pre_closure, "108", "{}\n", None, packet
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
    assert blocked_metric.binding_bases_per_review == ((basis_a,), ())
    assert blocked_metric.last_reviewer_verdict is ReviewVerdict.BLOCKED
    blocked_diagnostics = orch_module._summarize_v2_blocked_reviews([blocked])
    assert len(blocked_diagnostics) == 1
    assert blocked_diagnostics[0].gate_id == "blocked-gate"
    assert blocked_diagnostics[0].review_iteration == 2
    assert blocked_diagnostics[0].candidate_identity == CandidateIdentity("candidate-2")
    assert blocked_diagnostics[0].rationale == _blocked_rationale()

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


def test_v2_blocked_review_diagnostics_preserve_history_and_attempt_order() -> None:
    def history(gate_id: str) -> GateHistory:
        return GateHistory(
            context=GateContext(
                gate_id=gate_id,
                spec_identity="spec",
                accepted_base_context_identity="base",
            )
        )

    first = history("first-gate")
    ignored = history("ignored-gate")
    second = history("second-gate")
    _record_metric_review(first, _v2_explicit_blocked("first"), "candidate-1")
    ignored.attempts.append(
        GateAttempt(
            candidate_identity=CandidateIdentity("synthetic"),
            candidate_state="synthetic",
            verification=None,
            rejected=False,
            rejection_basis=None,
            review_iteration=None,
            reviewer_verdict=None,
        )
    )
    _record_metric_review(second, _v2_explicit_blocked("second"), "candidate-2")

    diagnostics = orch_module._summarize_v2_blocked_reviews(
        [first, ignored, second]
    )

    assert [diagnostic.gate_id for diagnostic in diagnostics] == [
        "first-gate",
        "second-gate",
    ]
    assert [diagnostic.review_iteration for diagnostic in diagnostics] == [1, 1]
    assert [diagnostic.candidate_identity for diagnostic in diagnostics] == [
        CandidateIdentity("candidate-1"),
        CandidateIdentity("candidate-2"),
    ]


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


def test_v2_late_repair_upstream_packet_is_one_hop_reviewer_context(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    _run_git(["checkout", "-q", "-b", "delivery"], cwd=env.work)
    upstream = _v2_changes("upstream").repair_packet
    assert upstream is not None
    decisions: list[orch_module.RoutingDecisionRecord] = []
    config = dataclasses.replace(_cp3_config(env), _routing_decisions=decisions)
    _install_cp3_reviewer_sequence(
        env,
        monkeypatch,
        [
            _v2_changes("upstream"),
            _v2_approved(),
        ],
    )

    orch_module._execute_v2_late_repair(
        config,
        spec,
        gate_id="upstream-one-hop-review",
        accepted_base_context_identity=_run_git(
            ["rev-parse", "HEAD"], cwd=env.work
        ).strip(),
        initial_packet=upstream,
        verification_commands=spec.checkpoints[0].verification,
        repair_acceptor=_commit_late_repair(env, []),
    )

    reviewer_decisions = [
        decision for decision in decisions if decision.role is AgentRole.REVIEWER
    ]
    assert [decision.selected_profile for decision in reviewer_decisions] == [
        ComputeProfile.CRITICAL,
        ComputeProfile.CRITICAL,
    ]
    assert reviewer_decisions[0].escalation_reasons == (
        RoutingEscalationReason.DIRECT_UPSTREAM_REPAIR_PACKET,
    )
    assert reviewer_decisions[1].escalation_reasons == (
        RoutingEscalationReason.REPEAT_REVIEW,
    )


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
    verification = VerificationEvidence(
        commands=tuple(
            VerificationCommandResult(
                command=command,
                returncode=0,
                stdout="successful output is not closure evidence",
                stderr="",
                passed=True,
            )
            for command in spec.full_verification
        ),
        passed=True,
        head_sha=implementation_head,
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


def _corrupt_cp4_evidence(
    pre_closure: orch_module.V2PreClosureExecutionResult, case: str
) -> orch_module.V2PreClosureExecutionResult:
    evidence = pre_closure.evidence
    full = evidence.full_verification
    cumulative = evidence.cumulative_review
    assert full is not None and cumulative is not None
    if case == "incomplete":
        return dataclasses.replace(pre_closure, completed=False)
    if case == "missing_full":
        return dataclasses.replace(
            pre_closure, evidence=dataclasses.replace(evidence, full_verification=None)
        )
    if case == "missing_cumulative":
        return dataclasses.replace(
            pre_closure, evidence=dataclasses.replace(evidence, cumulative_review=None)
        )
    if case == "failed_full":
        failed_command = dataclasses.replace(
            full.verification.commands[0], returncode=1, passed=False
        )
        failed_verification = dataclasses.replace(
            full.verification,
            commands=(failed_command, *full.verification.commands[1:]),
            passed=False,
        )
        replacement = dataclasses.replace(full, verification=failed_verification)
        return dataclasses.replace(
            pre_closure,
            evidence=dataclasses.replace(evidence, full_verification=replacement),
        )
    if case == "wrong_spec":
        replacement = dataclasses.replace(full, spec_identity="wrong-spec")
        return dataclasses.replace(
            pre_closure,
            evidence=dataclasses.replace(evidence, full_verification=replacement),
        )
    if case == "wrong_base":
        replacement = dataclasses.replace(full, base_identity="wrong-base")
        return dataclasses.replace(
            pre_closure,
            evidence=dataclasses.replace(evidence, full_verification=replacement),
        )
    if case == "stale_full_head":
        stale_head = "f" * 40
        replacement = dataclasses.replace(
            full,
            candidate_identity=orch_module._committed_candidate_identity(stale_head),
            head_sha=stale_head,
            verification=dataclasses.replace(
                full.verification, head_sha=stale_head
            ),
        )
        return dataclasses.replace(
            pre_closure,
            evidence=dataclasses.replace(evidence, full_verification=replacement),
        )
    if case == "nested_head":
        replacement = dataclasses.replace(
            full,
            verification=dataclasses.replace(
                full.verification, head_sha="e" * 40
            ),
        )
        return dataclasses.replace(
            pre_closure,
            evidence=dataclasses.replace(evidence, full_verification=replacement),
        )
    if case == "cumulative_head":
        replacement = dataclasses.replace(
            cumulative,
            reviewed_head_sha="d" * 40,
            review_patch=dataclasses.replace(
                cumulative.review_patch, head_sha="d" * 40
            ),
        )
        return dataclasses.replace(
            pre_closure,
            evidence=dataclasses.replace(evidence, cumulative_review=replacement),
        )
    if case == "wrong_full_candidate":
        replacement = dataclasses.replace(
            full, candidate_identity=CandidateIdentity("wrong-full-candidate")
        )
        return dataclasses.replace(
            pre_closure,
            evidence=dataclasses.replace(evidence, full_verification=replacement),
        )
    if case == "wrong_cumulative_candidate":
        replacement = dataclasses.replace(
            cumulative,
            candidate_identity=CandidateIdentity("wrong-cumulative-candidate"),
        )
        return dataclasses.replace(
            pre_closure,
            evidence=dataclasses.replace(evidence, cumulative_review=replacement),
        )
    raise AssertionError(f"unknown evidence corruption case: {case}")


def test_v2_validated_closure_evidence_is_compact_original_argv_only(env: Env) -> None:
    approved_commands = (
        ("python", "-m", "pytest", "tests/tools/autonomous_pr"),
        ("git", "diff", "--check"),
    )
    spec = dataclasses.replace(_cp3_spec(), full_verification=approved_commands)
    target, _, pre_closure, implementation_head = _prepared_cp4_context(env, spec)

    formatted = orch_module._format_validated_v2_closure_evidence(
        target,
        pre_closure,
        pr_number="123",
        expected_published_head=implementation_head,
    )
    compact = json.loads(formatted)

    assert compact == {
        "accepted_implementation": {
            "base_identity": pre_closure.evidence.base_identity,
            "head_sha": implementation_head,
        },
        "cumulative_review": {
            "accepted_identity": (
                pre_closure.evidence.cumulative_review.candidate_identity.digest
            ),
            "base_identity": pre_closure.evidence.base_identity,
            "review_iteration": 1,
            "reviewed_head_sha": implementation_head,
        },
        "draft_pr_number": "123",
        "full_verification": {
            "commands": [
                {"argv": list(command), "passed": True, "returncode": 0}
                for command in approved_commands
            ],
            "overall_passed": True,
            "verified_head_sha": implementation_head,
        },
        "selected_task": {
            "spec_identity": spec.digest,
            "spec_path": spec.path,
            "task_id": spec.task_id,
        },
    }
    assert sys.executable not in formatted
    assert "successful output is not closure evidence" not in formatted
    assert "stdout" not in formatted and "stderr" not in formatted


def _mode_c_projection_context(
    env: Env,
    spec: TaskExecutionSpec,
) -> tuple[
    ExecutionTarget,
    orch_module.V2ImplementationEvidence,
    repository.UnpublishedCommitCandidate,
    repository.ReviewPatch,
    str,
]:
    target, _, pre_closure, implementation_head = _prepared_cp4_context(env, spec)
    audit_base = "a" * 40
    candidate = repository.UnpublishedCommitCandidate(
        branch="delivery",
        published_predecessor_sha=implementation_head,
        candidate_head_sha="c" * 40,
        tree_sha="t" * 40,
    )
    diff_text = "final cumulative implementation and closure diff\n"
    patch = repository.ReviewPatch(
        purpose=repository.ReviewPurpose.FINAL_CUMULATIVE_AUDIT,
        range_description="origin/main...HEAD",
        base_sha=audit_base,
        head_sha=candidate.candidate_head_sha,
        branch=candidate.branch,
        diff_text=diff_text,
        digest=orch_module._candidate_identity(diff_text).digest,
    )
    evidence = dataclasses.replace(pre_closure.evidence, base_identity=audit_base)
    return target, evidence, candidate, patch, audit_base


def test_v2_validated_mode_c_evidence_is_compact_and_keeps_two_bases(
    env: Env,
) -> None:
    approved_commands = (
        ("python", "-m", "pytest", "tests/tools/autonomous_pr"),
        ("git", "diff", "--check"),
    )
    spec = dataclasses.replace(_cp3_spec(), full_verification=approved_commands)
    target, evidence, candidate, patch, audit_base = _mode_c_projection_context(
        env, spec
    )
    full = evidence.full_verification
    cumulative = evidence.cumulative_review
    assert full is not None and cumulative is not None
    assert evidence.base_identity == audit_base
    assert full.base_identity != audit_base

    formatted = orch_module._format_validated_v2_mode_c_evidence(
        target,
        evidence,
        pr_number="123",
        mode_c_audit_base=audit_base,
        candidate=candidate,
        patch=patch,
    )
    compact = json.loads(formatted)

    assert compact == {
        "accepted_implementation": {
            "base_identity": full.base_identity,
            "head_sha": full.head_sha,
        },
        "candidate": {
            "published_predecessor_sha": candidate.published_predecessor_sha,
        },
        "cumulative_review": {
            "accepted_identity": cumulative.candidate_identity.digest,
            "base_identity": cumulative.base_identity,
            "review_iteration": cumulative.review_iteration,
            "reviewed_head_sha": cumulative.reviewed_head_sha,
        },
        "draft_pr_number": "123",
        "full_verification": {
            "commands": [
                {"argv": list(command), "passed": True, "returncode": 0}
                for command in approved_commands
            ],
            "overall_passed": True,
            "verified_head_sha": full.head_sha,
        },
        "mode_c_audit_base": audit_base,
        "selected_task": {
            "spec_identity": spec.digest,
            "spec_path": spec.path,
            "task_id": spec.task_id,
        },
    }
    assert sys.executable not in formatted
    assert "successful output is not closure evidence" not in formatted
    for excluded in ("stdout", "stderr", "test_count", "provider", "model"):
        assert excluded not in formatted


@pytest.mark.parametrize(
    "case",
    (
        "missing_full",
        "missing_cumulative",
        "failed_full",
        "outer_spec",
        "wrong_spec",
        "wrong_base",
        "nested_head",
        "cumulative_head",
        "wrong_commands",
        "unsuccessful_command",
        "wrong_full_candidate",
        "wrong_cumulative_candidate",
        "wrong_cumulative_purpose",
        "wrong_cumulative_patch_head",
        "wrong_cumulative_digest",
        "missing_review_iteration",
        "candidate_predecessor",
        "empty_pr_number",
        "mode_c_patch_base",
        "mode_c_patch_head",
        "mode_c_patch_branch",
        "mode_c_patch_digest",
    ),
)
def test_v2_mode_c_evidence_inconsistency_fails_closed(
    env: Env, case: str
) -> None:
    spec = _cp3_spec()
    target, evidence, candidate, patch, audit_base = _mode_c_projection_context(
        env, spec
    )
    full = evidence.full_verification
    cumulative = evidence.cumulative_review
    assert full is not None and cumulative is not None
    pr_number = "1"

    if case in {
        "missing_full",
        "missing_cumulative",
        "failed_full",
        "wrong_spec",
        "wrong_base",
        "nested_head",
        "cumulative_head",
        "wrong_full_candidate",
        "wrong_cumulative_candidate",
    }:
        corrupted = _corrupt_cp4_evidence(
            orch_module.V2PreClosureExecutionResult(
                completed=True,
                evidence=evidence,
                cumulative_history=GateHistory(
                    context=GateContext(
                        gate_id="test",
                        spec_identity=spec.digest,
                        accepted_base_context_identity=audit_base,
                    )
                ),
                replay_histories=(),
            ),
            case,
        )
        evidence = corrupted.evidence
    elif case == "outer_spec":
        evidence = dataclasses.replace(evidence, spec_identity="wrong-spec")
    elif case == "wrong_commands":
        changed = dataclasses.replace(
            full.verification.commands[0], command=("python", "-m", "pytest", "other")
        )
        evidence = dataclasses.replace(
            evidence,
            full_verification=dataclasses.replace(
                full,
                verification=dataclasses.replace(
                    full.verification,
                    commands=(changed, *full.verification.commands[1:]),
                ),
            ),
        )
    elif case == "unsuccessful_command":
        changed = dataclasses.replace(
            full.verification.commands[0], returncode=1, passed=False
        )
        evidence = dataclasses.replace(
            evidence,
            full_verification=dataclasses.replace(
                full,
                verification=dataclasses.replace(
                    full.verification,
                    commands=(changed, *full.verification.commands[1:]),
                    passed=True,
                ),
            ),
        )
    elif case == "wrong_cumulative_purpose":
        evidence = dataclasses.replace(
            evidence,
            cumulative_review=dataclasses.replace(
                cumulative,
                review_patch=dataclasses.replace(
                    cumulative.review_patch,
                    purpose=repository.ReviewPurpose.FINAL_CUMULATIVE_AUDIT,
                ),
            ),
        )
    elif case == "wrong_cumulative_patch_head":
        evidence = dataclasses.replace(
            evidence,
            cumulative_review=dataclasses.replace(
                cumulative,
                review_patch=dataclasses.replace(
                    cumulative.review_patch, head_sha="d" * 40
                ),
            ),
        )
    elif case == "wrong_cumulative_digest":
        evidence = dataclasses.replace(
            evidence,
            cumulative_review=dataclasses.replace(
                cumulative,
                review_patch=dataclasses.replace(
                    cumulative.review_patch, digest="wrong-digest"
                ),
            ),
        )
    elif case == "missing_review_iteration":
        evidence = dataclasses.replace(
            evidence,
            cumulative_review=dataclasses.replace(cumulative, review_iteration=0),
        )
    elif case == "candidate_predecessor":
        candidate = dataclasses.replace(candidate, published_predecessor_sha="d" * 40)
    elif case == "empty_pr_number":
        pr_number = "  "
    elif case == "mode_c_patch_base":
        patch = dataclasses.replace(patch, base_sha="d" * 40)
    elif case == "mode_c_patch_head":
        patch = dataclasses.replace(patch, head_sha="d" * 40)
    elif case == "mode_c_patch_branch":
        patch = dataclasses.replace(patch, branch="other-delivery")
    elif case == "mode_c_patch_digest":
        patch = dataclasses.replace(patch, digest="wrong-digest")
    else:
        raise AssertionError(case)

    with pytest.raises(orch_module._Blocked):
        orch_module._format_validated_v2_mode_c_evidence(
            target,
            evidence,
            pr_number=pr_number,
            mode_c_audit_base=audit_base,
            candidate=candidate,
            patch=patch,
        )


def test_v2_invalid_mode_c_evidence_blocks_before_reviewer_invocation(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    target, evidence, candidate, patch, audit_base = _mode_c_projection_context(
        env, spec
    )
    evidence = dataclasses.replace(evidence, full_verification=None)
    invoked: list[str] = []
    monkeypatch.setattr(
        repository, "verify_unpublished_commit_candidate", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        repository, "build_cumulative_patch_from_base", lambda *args, **kwargs: patch
    )
    monkeypatch.setattr(
        orch_module,
        "_run_routed_v2_designated_review",
        lambda *args, **kwargs: invoked.append("reviewer"),
    )
    history = GateHistory(
        context=GateContext(
            gate_id="mode-c-final-cumulative-audit",
            spec_identity=spec.digest,
            accepted_base_context_identity=candidate.published_predecessor_sha,
        )
    )

    with pytest.raises(orch_module._Blocked, match="Full Verification evidence"):
        orch_module._review_v2_mode_c_candidate(
            _cp3_config(env),
            target,
            candidate,
            audit_base,
            history,
            accepted_evidence=evidence,
            pr_number="1",
        )

    assert invoked == []


@pytest.mark.parametrize(
    "case",
    (
        "incomplete",
        "missing_full",
        "missing_cumulative",
        "failed_full",
        "wrong_spec",
        "wrong_base",
        "stale_full_head",
        "nested_head",
        "cumulative_head",
        "expected_head",
        "wrong_full_candidate",
        "wrong_cumulative_candidate",
    ),
)
def test_v2_closure_evidence_inconsistency_fails_closed(
    env: Env, case: str
) -> None:
    spec = _cp3_spec()
    target, _, pre_closure, implementation_head = _prepared_cp4_context(env, spec)
    expected_head = implementation_head
    if case == "expected_head":
        expected_head = "c" * 40
    else:
        pre_closure = _corrupt_cp4_evidence(pre_closure, case)

    with pytest.raises(orch_module._Blocked):
        orch_module._format_validated_v2_closure_evidence(
            target,
            pre_closure,
            pr_number="1",
            expected_published_head=expected_head,
        )


def test_v2_invalid_closure_evidence_blocks_before_agent_invocation(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    target, _, pre_closure, implementation_head = _prepared_cp4_context(env, spec)
    pre_closure = _corrupt_cp4_evidence(pre_closure, "missing_full")
    invoked: list[str] = []
    monkeypatch.setattr(
        orch_module,
        "_run_routed_v2_implementer",
        lambda *args, **kwargs: invoked.append("implementer"),
    )
    monkeypatch.setattr(
        orch_module,
        "_run_routed_v2_designated_review",
        lambda *args, **kwargs: invoked.append("reviewer"),
    )

    with pytest.raises(orch_module._Blocked, match="Full Verification evidence"):
        orch_module._prepare_v2_unpublished_closure(
            _cp3_config(env),
            target,
            pre_closure,
            pr_number="1",
            expected_published_head=implementation_head,
            task_md_baseline="unused because evidence validation fails first",
        )

    assert invoked == []


@pytest.mark.parametrize(
    ("task_md_baseline", "expected"),
    [
        ("not a terminal registry", "invalid authoritative Task Closure baseline"),
        (
            _v2_task_md_text(
                _TASK_ID, terminal_rows=((_TASK_ID, TaskStatus.DONE.value),)
            ),
            f"{_TASK_ID} is already terminal",
        ),
    ],
    ids=("malformed", "selected-task-already-terminal"),
)
def test_v2_invalid_authoritative_closure_baseline_blocks_before_implementer(
    env: Env,
    monkeypatch: pytest.MonkeyPatch,
    task_md_baseline: str,
    expected: str,
) -> None:
    spec = _cp3_spec()
    target, _, pre_closure, implementation_head = _prepared_cp4_context(env, spec)
    invoked: list[str] = []
    monkeypatch.setattr(
        orch_module,
        "_run_routed_v2_implementer",
        lambda *args, **kwargs: invoked.append("implementer"),
    )

    with pytest.raises(orch_module._Blocked, match=expected):
        orch_module._prepare_v2_unpublished_closure(
            _cp3_config(env),
            target,
            pre_closure,
            pr_number="1",
            expected_published_head=implementation_head,
            task_md_baseline=task_md_baseline,
        )

    assert invoked == []


def _write_test_closure_candidate(
    env: Env, *, evidence: str, log_text: str
) -> None:
    task_path = env.work / "docs" / "TASK.md"
    task_text = task_path.read_bytes().decode("utf-8")
    eol = "\r\n" if "\r\n" in task_text else "\n"
    separator = (
        f"| ID | Status | Evidence | Title |{eol}"
        f"| --- | --- | --- | --- |{eol}"
    )
    candidate_rows = tuple(
        f"| `{_TASK_ID}` | `Done` | {candidate_evidence} | Test task |{eol}"
        for candidate_evidence in ("draft PR #1", "PR #2", "PR #1")
    )
    desired_row = f"| `{_TASK_ID}` | `Done` | {evidence} | Test task |{eol}"
    existing_row = next((row for row in candidate_rows if row in task_text), None)
    if existing_row is not None:
        task_text = task_text.replace(existing_row, desired_row, 1)
    else:
        assert separator in task_text
        task_text = task_text.replace(separator, separator + desired_row, 1)
    task_path.write_bytes(task_text.encode("utf-8"))
    (env.work / "docs" / "DEVELOPMENT_LOG.md").write_text(
        log_text, encoding="utf-8"
    )


def test_v2_wrong_closure_evidence_repairs_before_review_with_distinct_handoff(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert (
        CandidateRejectionBasis.CLOSURE_VALIDATION_FAILURE.value
        == "closure_validation_failure"
    )
    spec = _cp3_spec()
    target, _, pre_closure, implementation_head = _prepared_cp4_context(env, spec)
    task_md_baseline = repository.read_utf8_file_at_ref_exact(
        env.work, target.base_sha, "docs/TASK.md"
    )
    prompts: list[str] = []
    work_kinds: list[AgentWorkKind] = []
    reviews = [
        _changes_with_paths(
            "closure prose defect", ("docs/DEVELOPMENT_LOG.md",)
        ),
        _v2_approved(),
    ]
    reviewer_calls = 0

    def implement(
        config: OrchestratorConfig,
        prompt: str,
        *,
        work_kind: AgentWorkKind,
        history: GateHistory,
        direct_upstream_repair_packet: RepairPacket | None = None,
        seed_verification_rejection_count: int = 0,
    ) -> AgentInvocationResult:
        prompts.append(prompt)
        work_kinds.append(work_kind)
        if len(prompts) == 1:
            _write_test_closure_candidate(
                env, evidence="draft PR #1", log_text="invalid closure\n"
            )
        elif len(prompts) == 2:
            _write_test_closure_candidate(
                env, evidence="PR #1", log_text="valid closure\n"
            )
        else:
            _write_test_closure_candidate(
                env, evidence="PR #1", log_text="review repair\n"
            )
        return AgentInvocationResult("done", "", 0, False)

    def review(
        config: OrchestratorConfig,
        review_input: str,
        patch: repository.ReviewPatch,
        *,
        context: str,
        work_kind: AgentWorkKind,
        history: GateHistory,
        direct_upstream_repair_packet: RepairPacket | None = None,
        seed_verification_rejection_count: int = 0,
    ) -> StructuredReviewResult:
        nonlocal reviewer_calls
        reviewer_calls += 1
        if reviewer_calls == 1:
            assert history.review_iteration == 0
            assert history.consecutive_changes_requested == 0
            assert history.previous_reviewed_candidate_identity is None
            assert history.previous_reviewed_candidate_state is None
            assert history.latest_valid_repair_packet is None
            assert len(history.attempts) == 1
        return reviews.pop(0)

    monkeypatch.setattr(orch_module, "_run_routed_v2_implementer", implement)
    monkeypatch.setattr(orch_module, "_run_routed_v2_designated_review", review)
    histories: list[GateHistory] = []

    candidate, history, _ = orch_module._prepare_v2_unpublished_closure(
        _cp3_config(env),
        target,
        pre_closure,
        pr_number="1",
        expected_published_head=implementation_head,
        task_md_baseline=task_md_baseline,
        history_sink=histories,
    )

    assert candidate.published_predecessor_sha == implementation_head
    assert history is histories[0]
    assert work_kinds == [
        AgentWorkKind.TASK_CLOSURE_PREPARATION,
        AgentWorkKind.TASK_CLOSURE_REPAIR,
        AgentWorkKind.TASK_CLOSURE_REPAIR,
    ]
    assert "CURRENT_CLOSURE_VALIDATION_FAILURE:\n(none)\n" in prompts[0]
    assert "CURRENT_CLOSURE_VALIDATION_FAILURE:\n1. invalid terminal-only" in (
        prompts[1]
    )
    assert "prospective closure must add exactly one selected-task terminal row" in (
        prompts[1]
    )
    assert "CURRENT_CLOSURE_VALIDATION_FAILURE:\n(none)\n" in prompts[2]
    first = history.attempts[0]
    assert first.rejected
    assert (
        first.rejection_basis
        is CandidateRejectionBasis.CLOSURE_VALIDATION_FAILURE
    )
    assert first.verification is None
    assert first.review_iteration is None
    assert first.reviewer_verdict is None
    assert first.findings == ()
    assert first.repair_packet is None
    assert first.blocked_rationale is None
    assert reviewer_calls == 2


def test_v2_repeated_invalid_closure_identity_blocks_before_reviewer(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    target, _, pre_closure, implementation_head = _prepared_cp4_context(env, spec)
    task_md_baseline = repository.read_utf8_file_at_ref_exact(
        env.work, target.base_sha, "docs/TASK.md"
    )
    implementer_calls = 0
    reviewer_calls = 0

    def implement(*args: object, **kwargs: object) -> AgentInvocationResult:
        nonlocal implementer_calls
        implementer_calls += 1
        if implementer_calls == 1:
            _write_test_closure_candidate(
                env, evidence="draft PR #1", log_text="same invalid closure\n"
            )
        return AgentInvocationResult("done", "", 0, False)

    def review(*args: object, **kwargs: object) -> StructuredReviewResult:
        nonlocal reviewer_calls
        reviewer_calls += 1
        return _v2_approved()

    monkeypatch.setattr(orch_module, "_run_routed_v2_implementer", implement)
    monkeypatch.setattr(orch_module, "_run_routed_v2_designated_review", review)
    histories: list[GateHistory] = []

    with pytest.raises(orch_module._Blocked, match="reproduced a rejected candidate"):
        orch_module._prepare_v2_unpublished_closure(
            _cp3_config(env),
            target,
            pre_closure,
            pr_number="1",
            expected_published_head=implementation_head,
            task_md_baseline=task_md_baseline,
            history_sink=histories,
        )

    history = histories[0]
    assert implementer_calls == 2
    assert reviewer_calls == 0
    assert len(history.attempts) == 2
    assert (
        history.attempts[0].rejection_basis
        is CandidateRejectionBasis.CLOSURE_VALIDATION_FAILURE
    )
    repeated = history.attempts[1]
    assert repeated.rejected
    assert repeated.rejection_basis is CandidateRejectionBasis.REPEATED_IDENTITY
    assert repeated.verification is None
    assert repeated.review_iteration is None
    assert repeated.reviewer_verdict is None


def test_v2_distinct_invalid_closure_candidates_continue_until_valid(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    target, _, pre_closure, implementation_head = _prepared_cp4_context(env, spec)
    task_md_baseline = repository.read_utf8_file_at_ref_exact(
        env.work, target.base_sha, "docs/TASK.md"
    )
    evidences = iter(("draft PR #1", "PR #2", "PR #1"))
    work_kinds: list[AgentWorkKind] = []
    reviewer_calls = 0

    def implement(
        *args: object, work_kind: AgentWorkKind, **kwargs: object
    ) -> AgentInvocationResult:
        work_kinds.append(work_kind)
        evidence = next(evidences)
        _write_test_closure_candidate(
            env, evidence=evidence, log_text=f"candidate {evidence}\n"
        )
        return AgentInvocationResult("done", "", 0, False)

    def review(*args: object, **kwargs: object) -> StructuredReviewResult:
        nonlocal reviewer_calls
        reviewer_calls += 1
        return _v2_approved()

    monkeypatch.setattr(orch_module, "_run_routed_v2_implementer", implement)
    monkeypatch.setattr(orch_module, "_run_routed_v2_designated_review", review)

    _, history, _ = orch_module._prepare_v2_unpublished_closure(
        _cp3_config(env),
        target,
        pre_closure,
        pr_number="1",
        expected_published_head=implementation_head,
        task_md_baseline=task_md_baseline,
    )

    assert work_kinds == [
        AgentWorkKind.TASK_CLOSURE_PREPARATION,
        AgentWorkKind.TASK_CLOSURE_REPAIR,
        AgentWorkKind.TASK_CLOSURE_REPAIR,
    ]
    assert reviewer_calls == 1
    assert [attempt.rejection_basis for attempt in history.attempts[:2]] == [
        CandidateRejectionBasis.CLOSURE_VALIDATION_FAILURE,
        CandidateRejectionBasis.CLOSURE_VALIDATION_FAILURE,
    ]
    assert history.review_iteration == 1


@pytest.mark.parametrize(
    "missing_path",
    ("docs/TASK.md", "docs/DEVELOPMENT_LOG.md"),
    ids=("task-tracker", "development-log"),
)
def test_v2_missing_required_closure_file_change_enters_repair(
    env: Env, monkeypatch: pytest.MonkeyPatch, missing_path: str
) -> None:
    spec = _cp3_spec()
    target, _, pre_closure, implementation_head = _prepared_cp4_context(env, spec)
    task_md_baseline = repository.read_utf8_file_at_ref_exact(
        env.work, target.base_sha, "docs/TASK.md"
    )
    prompts: list[str] = []
    work_kinds: list[AgentWorkKind] = []
    reviewer_calls = 0

    def implement(
        config: OrchestratorConfig,
        prompt: str,
        *,
        work_kind: AgentWorkKind,
        **kwargs: object,
    ) -> AgentInvocationResult:
        prompts.append(prompt)
        work_kinds.append(work_kind)
        if len(prompts) == 1 and missing_path == "docs/TASK.md":
            (env.work / "docs" / "DEVELOPMENT_LOG.md").write_text(
                "log-only candidate\n", encoding="utf-8"
            )
        else:
            _write_test_closure_candidate(
                env, evidence="PR #1", log_text="complete closure\n"
            )
            if len(prompts) == 1:
                (env.work / "docs" / "DEVELOPMENT_LOG.md").unlink()
        return AgentInvocationResult("done", "", 0, False)

    def review(*args: object, **kwargs: object) -> StructuredReviewResult:
        nonlocal reviewer_calls
        reviewer_calls += 1
        return _v2_approved()

    monkeypatch.setattr(orch_module, "_run_routed_v2_implementer", implement)
    monkeypatch.setattr(orch_module, "_run_routed_v2_designated_review", review)

    orch_module._prepare_v2_unpublished_closure(
        _cp3_config(env),
        target,
        pre_closure,
        pr_number="1",
        expected_published_head=implementation_head,
        task_md_baseline=task_md_baseline,
    )

    assert work_kinds == [
        AgentWorkKind.TASK_CLOSURE_PREPARATION,
        AgentWorkKind.TASK_CLOSURE_REPAIR,
    ]
    assert f"missing required closure-file change(s): {missing_path}" in prompts[1]
    assert reviewer_calls == 1


@pytest.mark.parametrize(
    "path",
    ("src/unsafe.py", "tests/unsafe.py", "tools/unsafe.py", "docs/OTHER.md"),
)
def test_v2_closure_disallowed_paths_remain_terminal(path: str) -> None:
    with pytest.raises(orch_module._Blocked, match="outside the canonical"):
        orch_module._require_canonical_closure_files_touched((path,))


def test_v2_closure_rename_from_disallowed_source_blocks_before_review(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    target, _, pre_closure, implementation_head = _prepared_cp4_context(env, spec)
    task_md_baseline = repository.read_utf8_file_at_ref_exact(
        env.work, target.base_sha, "docs/TASK.md"
    )
    reviewer_calls = 0
    unpublished_commit_calls = 0

    def implement(*args: object, **kwargs: object) -> AgentInvocationResult:
        (env.work / "README.md").rename(
            env.work / "docs" / "DEVELOPMENT_LOG.md"
        )
        return AgentInvocationResult("done", "", 0, False)

    def review(*args: object, **kwargs: object) -> StructuredReviewResult:
        nonlocal reviewer_calls
        reviewer_calls += 1
        return _v2_approved()

    def create_candidate(*args: object, **kwargs: object) -> object:
        nonlocal unpublished_commit_calls
        unpublished_commit_calls += 1
        raise AssertionError("disallowed rename must not create a closure commit")

    monkeypatch.setattr(orch_module, "_run_routed_v2_implementer", implement)
    monkeypatch.setattr(orch_module, "_run_routed_v2_designated_review", review)
    monkeypatch.setattr(
        repository, "create_unpublished_reviewed_commit", create_candidate
    )

    with pytest.raises(orch_module._Blocked, match="outside the canonical"):
        orch_module._prepare_v2_unpublished_closure(
            _cp3_config(env),
            target,
            pre_closure,
            pr_number="1",
            expected_published_head=implementation_head,
            task_md_baseline=task_md_baseline,
        )

    assert repository.changed_paths(env.work) == (
        "README.md",
        "docs/DEVELOPMENT_LOG.md",
    )
    assert reviewer_calls == 0
    assert unpublished_commit_calls == 0
    assert _run_git(["rev-parse", "HEAD"], cwd=env.work).strip() == implementation_head


def test_v2_closure_repository_error_during_exact_read_is_terminal(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    target, _, pre_closure, implementation_head = _prepared_cp4_context(env, spec)
    task_md_baseline = repository.read_utf8_file_at_ref_exact(
        env.work, target.base_sha, "docs/TASK.md"
    )
    reviewer_calls = 0

    def implement(*args: object, **kwargs: object) -> AgentInvocationResult:
        _write_test_closure_candidate(
            env, evidence="PR #1", log_text="closure candidate\n"
        )
        return AgentInvocationResult("done", "", 0, False)

    def fail_read(*args: object, **kwargs: object) -> str:
        raise repository.RepositoryError("isolated exact-read failure")

    def review(*args: object, **kwargs: object) -> StructuredReviewResult:
        nonlocal reviewer_calls
        reviewer_calls += 1
        return _v2_approved()

    monkeypatch.setattr(orch_module, "_run_routed_v2_implementer", implement)
    monkeypatch.setattr(repository, "read_worktree_utf8_file_exact", fail_read)
    monkeypatch.setattr(orch_module, "_run_routed_v2_designated_review", review)

    with pytest.raises(orch_module._Blocked, match="cannot safely read"):
        orch_module._prepare_v2_unpublished_closure(
            _cp3_config(env),
            target,
            pre_closure,
            pr_number="1",
            expected_published_head=implementation_head,
            task_md_baseline=task_md_baseline,
        )

    assert reviewer_calls == 0


@pytest.mark.parametrize(
    ("returncode", "timed_out"),
    ((7, False), (None, True)),
    ids=("non-zero", "timeout"),
)
def test_v2_closure_implementer_failure_remains_terminal(
    env: Env,
    monkeypatch: pytest.MonkeyPatch,
    returncode: int | None,
    timed_out: bool,
) -> None:
    spec = _cp3_spec()
    target, _, pre_closure, implementation_head = _prepared_cp4_context(env, spec)
    task_md_baseline = repository.read_utf8_file_at_ref_exact(
        env.work, target.base_sha, "docs/TASK.md"
    )
    reviewer_calls = 0
    monkeypatch.setattr(
        orch_module,
        "_run_routed_v2_implementer",
        lambda *args, **kwargs: AgentInvocationResult(
            "", "failed", returncode, timed_out
        ),
    )

    def review(*args: object, **kwargs: object) -> StructuredReviewResult:
        nonlocal reviewer_calls
        reviewer_calls += 1
        return _v2_approved()

    monkeypatch.setattr(orch_module, "_run_routed_v2_designated_review", review)

    with pytest.raises(orch_module._Blocked, match="implementer failed"):
        orch_module._prepare_v2_unpublished_closure(
            _cp3_config(env),
            target,
            pre_closure,
            pr_number="1",
            expected_published_head=implementation_head,
            task_md_baseline=task_md_baseline,
        )

    assert reviewer_calls == 0


def test_v2_closure_validation_collects_missing_file_and_terminal_row_defects(
    env: Env
) -> None:
    baseline = (env.work / "docs" / "TASK.md").read_text(encoding="utf-8")
    _write_test_closure_candidate(
        env, evidence="draft PR #1", log_text="not part of touched set\n"
    )

    failures = orch_module._collect_v2_closure_validation_failures(
        env.work,
        ("docs/TASK.md",),
        task_md_baseline=baseline,
        task_id=_TASK_ID,
        pr_number="1",
        title="Test task",
    )

    assert failures[0] == (
        "missing required closure-file change(s): docs/DEVELOPMENT_LOG.md"
    )
    assert failures[1].startswith("invalid terminal-only Task Closure:")


def test_v2_unchanged_readable_task_file_reports_missing_change_and_row(
    env: Env
) -> None:
    baseline = (env.work / "docs" / "TASK.md").read_text(encoding="utf-8")
    (env.work / "docs" / "DEVELOPMENT_LOG.md").write_text(
        "closure log only\n", encoding="utf-8"
    )

    failures = orch_module._collect_v2_closure_validation_failures(
        env.work,
        ("docs/DEVELOPMENT_LOG.md",),
        task_md_baseline=baseline,
        task_id=_TASK_ID,
        pr_number="1",
        title="Test task",
    )

    assert failures[0] == "missing required closure-file change(s): docs/TASK.md"
    assert failures[1].startswith("invalid terminal-only Task Closure:")
    assert "selected-task terminal row" in failures[1]


def test_v2_closure_evidence_is_revalidated_before_reviewer_invocation(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    target, _, pre_closure, implementation_head = _prepared_cp4_context(env, spec)
    _install_cp4_agents(env, monkeypatch, [])
    routed_implementer = orch_module._run_routed_v2_implementer
    reviewer_invocations: list[str] = []

    def invalidate_after_implementer(*args: object, **kwargs: object) -> object:
        result = routed_implementer(*args, **kwargs)  # type: ignore[arg-type]
        pre_closure.evidence.full_verification = None
        return result

    monkeypatch.setattr(
        orch_module, "_run_routed_v2_implementer", invalidate_after_implementer
    )
    monkeypatch.setattr(
        orch_module,
        "_run_routed_v2_designated_review",
        lambda *args, **kwargs: reviewer_invocations.append("reviewer"),
    )
    task_md_baseline = repository.read_utf8_file_at_ref_exact(
        env.work, target.base_sha, "docs/TASK.md"
    )

    with pytest.raises(orch_module._Blocked, match="Full Verification evidence"):
        orch_module._prepare_v2_unpublished_closure(
            _cp3_config(env),
            target,
            pre_closure,
            pr_number="1",
            expected_published_head=implementation_head,
            task_md_baseline=task_md_baseline,
        )

    assert reviewer_invocations == []


def _closure_evidence_from_prompt(prompt: str) -> tuple[str, dict[str, object]]:
    marker = "AUTHORITATIVE_CLOSURE_EVIDENCE_JSON:\n"
    payload = prompt.split(marker, 1)[1]
    parsed, end = json.JSONDecoder().raw_decode(payload)
    assert isinstance(parsed, dict)
    return payload[:end] + "\n", parsed


def _mode_c_evidence_from_prompt(prompt: str) -> dict[str, object]:
    marker = "AUTHORITATIVE_MODE_C_EVIDENCE_JSON:\n"
    payload = prompt.split(marker, 1)[1]
    parsed, _ = json.JSONDecoder().raw_decode(payload)
    assert isinstance(parsed, dict)
    return parsed


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
    implementer_prompts, reviewer_prompts = _install_cp4_agents(
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
    closure_implementer_prompt = next(
        prompt
        for prompt in implementer_prompts
        if "CURRENT_GATE: prospective Task Closure" in prompt
    )
    closure_reviewer_prompt = next(
        prompt
        for prompt in reviewer_prompts
        if "prospective Task Closure review" in prompt
    )
    implementer_evidence, compact = _closure_evidence_from_prompt(
        closure_implementer_prompt
    )
    reviewer_evidence, reviewer_compact = _closure_evidence_from_prompt(
        closure_reviewer_prompt
    )
    cumulative = pre_closure.evidence.cumulative_review
    assert cumulative is not None
    assert implementer_evidence == reviewer_evidence
    assert compact == reviewer_compact
    assert compact["draft_pr_number"] == "1"
    assert compact["accepted_implementation"] == {
        "base_identity": pre_closure.evidence.base_identity,
        "head_sha": implementation_head,
    }
    assert compact["full_verification"] == {
        "commands": [
            {"argv": list(command), "passed": True, "returncode": 0}
            for command in spec.full_verification
        ],
        "overall_passed": True,
        "verified_head_sha": implementation_head,
    }
    assert compact["cumulative_review"] == {
        "accepted_identity": cumulative.candidate_identity.digest,
        "base_identity": pre_closure.evidence.base_identity,
        "review_iteration": cumulative.review_iteration,
        "reviewed_head_sha": implementation_head,
    }
    implementation_patch = cumulative.review_patch.diff_text
    assert f"ACCEPTED_IMPLEMENTATION_PATCH:\n{implementation_patch}\n" in (
        closure_implementer_prompt
    )
    assert implementation_patch not in closure_reviewer_prompt
    assert "CURRENT_PATCH:\ndiff --git a/docs/" in closure_reviewer_prompt
    assert "Do not rerun verification merely to write closure prose" in (
        closure_implementer_prompt
    )
    assert "invent test counts" in closure_implementer_prompt
    assert "derive verification claims from your own self-check" in (
        closure_implementer_prompt
    )
    assert "subset of the recorded commands" in closure_implementer_prompt
    assert "Do not repeat the full implementation review" in closure_reviewer_prompt
    mode_c_prompt = next(
        prompt for prompt in reviewer_prompts if "FINAL_CUMULATIVE_AUDIT" in prompt
    )
    assert result.closure_candidate.candidate_head_sha in mode_c_prompt
    mode_c_compact = _mode_c_evidence_from_prompt(mode_c_prompt)
    assert mode_c_compact["draft_pr_number"] == "1"
    assert mode_c_compact["candidate"] == {
        "published_predecessor_sha": implementation_head,
    }
    assert mode_c_compact["mode_c_audit_base"] == result.mode_c_evidence.base_sha
    assert mode_c_compact["accepted_implementation"] == {
        "base_identity": pre_closure.evidence.full_verification.base_identity,
        "head_sha": implementation_head,
    }
    assert "Accepted Full Verification and cumulative-review facts establish" in (
        mode_c_prompt
    )
    assert "fresh, independent Mode C material review" in mode_c_prompt
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
    target, checkpoints, pre_closure, implementation_head = _prepared_cp4_context(
        env, spec
    )
    _mock_cp3_revalidated_target(monkeypatch, target)
    _, reviewer_prompts = _install_cp4_agents(
        env, monkeypatch, [_v2_approved(), _v2_approved()]
    )
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
    mode_c_prompt = next(
        prompt for prompt in reviewer_prompts if "FINAL_CUMULATIVE_AUDIT" in prompt
    )
    compact = _mode_c_evidence_from_prompt(mode_c_prompt)
    assert compact["accepted_implementation"] == {
        "base_identity": target.base_sha,
        "head_sha": implementation_head,
    }
    assert compact["mode_c_audit_base"] == moved_sha
    assert compact["candidate"] == {
        "published_predecessor_sha": implementation_head,
    }
    assert f"BASE_SHA: {moved_sha}\n" in mode_c_prompt
    assert result.mode_c_evidence.review_patch.base_sha == moved_sha
    assert (
        f"CURRENT_PATCH:\n{result.mode_c_evidence.review_patch.diff_text}\n"
        in mode_c_prompt
    )


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
    projected_candidates: list[
        tuple[str, str, orch_module.V2ImplementationEvidence]
    ] = []
    real_formatter = orch_module._format_validated_v2_mode_c_evidence

    def observe_fresh_projection(
        execution_target: ExecutionTarget,
        evidence: orch_module.V2ImplementationEvidence,
        *,
        pr_number: str,
        mode_c_audit_base: str,
        candidate: repository.UnpublishedCommitCandidate,
        patch: repository.ReviewPatch,
    ) -> str:
        projected_candidates.append(
            (candidate.candidate_head_sha, candidate.published_predecessor_sha, evidence)
        )
        return real_formatter(
            execution_target,
            evidence,
            pr_number=pr_number,
            mode_c_audit_base=mode_c_audit_base,
            candidate=candidate,
            patch=patch,
        )

    monkeypatch.setattr(
        orch_module,
        "_format_validated_v2_mode_c_evidence",
        observe_fresh_projection,
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
    assert len(projected_candidates) == 2
    assert projected_candidates[0][0] != projected_candidates[1][0]
    assert [item[1] for item in projected_candidates] == [
        implementation_head,
        implementation_head,
    ]
    assert all(item[2] is pre_closure.evidence for item in projected_candidates)
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
    implementer_prompts, reviewer_prompts = _install_cp4_agents(
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
    closure_implementer_prompts = [
        prompt
        for prompt in implementer_prompts
        if "CURRENT_GATE: prospective Task Closure" in prompt
    ]
    closure_reviews = [
        prompt
        for prompt in reviewer_prompts
        if "prospective Task Closure review" in prompt
    ]
    evidence_blocks = [
        _closure_evidence_from_prompt(prompt)[0]
        for prompt in (*closure_implementer_prompts, *closure_reviews)
    ]
    assert len(closure_implementer_prompts) == 2
    assert len(set(evidence_blocks)) == 1
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
    closure_prompts = [
        prompt
        for prompt in implementer_prompts
        if "CURRENT_GATE: prospective Task Closure" in prompt
    ]
    assert len(closure_prompts) == 2
    old_compact = _closure_evidence_from_prompt(closure_prompts[0])[1]
    new_compact = _closure_evidence_from_prompt(closure_prompts[1])[1]
    old_implementation = old_compact["accepted_implementation"]
    new_implementation = new_compact["accepted_implementation"]
    assert isinstance(old_implementation, dict)
    assert isinstance(new_implementation, dict)
    assert old_implementation["head_sha"] == implementation_head
    assert new_implementation["head_sha"] == (
        result.pre_closure_result.evidence.cumulative_review.reviewed_head_sha
    )
    assert new_implementation["head_sha"] != old_implementation["head_sha"]


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
    mode_c_compacts = [
        _mode_c_evidence_from_prompt(prompt)
        for prompt in reviewer_prompts
        if "FINAL_CUMULATIVE_AUDIT" in prompt
    ]
    old_accepted = mode_c_compacts[0]["accepted_implementation"]
    new_accepted = mode_c_compacts[1]["accepted_implementation"]
    assert isinstance(old_accepted, dict) and isinstance(new_accepted, dict)
    assert old_accepted["head_sha"] == implementation_head
    new_full = result.pre_closure_result.evidence.full_verification
    new_cumulative = result.pre_closure_result.evidence.cumulative_review
    assert new_full is not None and new_cumulative is not None
    assert new_full.head_sha != implementation_head
    assert new_full.head_sha == new_full.verification.head_sha
    assert new_full.head_sha == new_cumulative.reviewed_head_sha
    assert new_accepted["head_sha"] == new_full.head_sha
    assert result.closure_candidate.published_predecessor_sha == new_full.head_sha
    assert result.mode_c_evidence is not None
    with pytest.raises(orch_module._Blocked, match="candidate predecessor"):
        orch_module._format_validated_v2_mode_c_evidence(
            target,
            pre_closure.evidence,
            pr_number="1",
            mode_c_audit_base=result.mode_c_evidence.base_sha,
            candidate=result.closure_candidate,
            patch=result.mode_c_evidence.review_patch,
        )


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


def _ci_result(
    *buckets: str,
    returncode: int,
) -> repository.RequiredChecksResult:
    return repository.RequiredChecksResult(
        checks=[
            {"name": f"check-{index}", "state": bucket.upper(), "bucket": bucket}
            for index, bucket in enumerate(buckets)
        ],
        no_required_checks=False,
        returncode=returncode,
    )


@pytest.mark.parametrize(
    "observations",
    [
        [
            repository.RequiredChecksResult(
                checks=[], no_required_checks=True, returncode=1
            )
        ],
        [
            repository.RequiredChecksResult(
                checks=[],
                no_required_checks=False,
                returncode=1,
                no_checks_reported=True,
            ),
            repository.RequiredChecksResult(
                checks=[], no_required_checks=True, returncode=1
            ),
        ],
        [
            repository.RequiredChecksResult(
                checks=[],
                no_required_checks=False,
                returncode=1,
                no_checks_reported=True,
            ),
            _ci_result("pending", returncode=8),
            _ci_result("pass", returncode=0),
        ],
        [
            _ci_result("pending", returncode=8),
            _ci_result("pending", returncode=8),
            _ci_result("pass", returncode=0),
        ],
        [_ci_result("pass", "skipping", returncode=0)],
    ],
    ids=(
        "no-required-immediate",
        "no-checks-to-no-required",
        "no-checks-to-pending-to-pass",
        "pending-to-pending-to-pass",
        "pass-and-skipping",
    ),
)
def test_v2_required_ci_waits_boundedly_with_exact_head_guards(
    env: Env,
    monkeypatch: pytest.MonkeyPatch,
    observations: list[repository.RequiredChecksResult],
) -> None:
    candidate = "c" * 40
    queue = list(observations)
    events: list[str] = []
    sleeps: list[float] = []

    def head(
        repo: Path, pr_number: str, *, gh_command: tuple[str, ...]
    ) -> str:
        events.append("head")
        return candidate

    def checks(
        repo: Path, pr_number: str, *, gh_command: tuple[str, ...]
    ) -> repository.RequiredChecksResult:
        events.append("checks")
        return queue.pop(0)

    monkeypatch.setattr(repository, "pr_head_sha", head)
    monkeypatch.setattr(repository, "pr_required_checks", checks)
    monkeypatch.setattr(orch_module, "monotonic", lambda: 0.0)
    monkeypatch.setattr(orch_module, "sleep", sleeps.append)
    monkeypatch.setattr(
        orch_module,
        "run_implementer",
        lambda *args, **kwargs: pytest.fail("CI polling invoked implementer"),
    )
    monkeypatch.setattr(
        orch_module,
        "run_structured_reviewer",
        lambda *args, **kwargs: pytest.fail("CI polling invoked reviewer"),
    )
    monkeypatch.setattr(
        orch_module,
        "route_agent_work",
        lambda *args, **kwargs: pytest.fail("CI polling created routing activity"),
    )
    config = _cp3_config(env)

    orch_module._require_v2_published_candidate_ci(config, "1", candidate)

    assert queue == []
    assert events == ["head", "checks", "head"] * len(observations)
    assert sleeps == [10.0] * (len(observations) - 1)
    assert config._routing_decisions is None


@pytest.mark.parametrize(
    ("result", "expected_names"),
    [
        (_ci_result("fail", "pending", returncode=1), "failed=['check-0']"),
        (_ci_result("cancel", returncode=1), "cancelled=['check-0']"),
    ],
)
def test_v2_required_ci_terminal_non_success_precedes_pending(
    env: Env,
    monkeypatch: pytest.MonkeyPatch,
    result: repository.RequiredChecksResult,
    expected_names: str,
) -> None:
    candidate = "c" * 40
    head_calls = 0
    sleep_calls: list[float] = []

    def head(
        repo: Path, pr_number: str, *, gh_command: tuple[str, ...]
    ) -> str:
        nonlocal head_calls
        head_calls += 1
        return candidate

    monkeypatch.setattr(repository, "pr_head_sha", head)
    monkeypatch.setattr(repository, "pr_required_checks", lambda *a, **k: result)
    monkeypatch.setattr(orch_module, "monotonic", lambda: 0.0)
    monkeypatch.setattr(orch_module, "sleep", sleep_calls.append)

    with pytest.raises(orch_module._Blocked, match="failed or was cancelled") as exc:
        orch_module._require_v2_published_candidate_ci(
            _cp3_config(env), "1", candidate
        )

    assert expected_names in str(exc.value)
    assert head_calls == 2
    assert sleep_calls == []


@pytest.mark.parametrize(
    ("result", "reason"),
    [
        (
            repository.RequiredChecksResult(
                checks=[],
                no_required_checks=False,
                returncode=1,
                no_checks_reported=True,
            ),
            "persistent no checks reported",
        ),
        (_ci_result("pending", returncode=8), "persistent pending required checks"),
    ],
)
def test_v2_required_ci_transient_state_times_out_monotonically(
    env: Env,
    monkeypatch: pytest.MonkeyPatch,
    result: repository.RequiredChecksResult,
    reason: str,
) -> None:
    candidate = "c" * 40
    now = 100.0
    sleeps: list[float] = []
    head_calls = 0
    check_calls = 0

    def clock() -> float:
        return now

    def bounded_sleep(seconds: float) -> None:
        nonlocal now
        sleeps.append(seconds)
        now += seconds

    def head(
        repo: Path, pr_number: str, *, gh_command: tuple[str, ...]
    ) -> str:
        nonlocal head_calls
        head_calls += 1
        return candidate

    def checks(*args: object, **kwargs: object) -> repository.RequiredChecksResult:
        nonlocal check_calls
        check_calls += 1
        return result

    monkeypatch.setattr(repository, "pr_head_sha", head)
    monkeypatch.setattr(repository, "pr_required_checks", checks)
    monkeypatch.setattr(orch_module, "monotonic", clock)
    monkeypatch.setattr(orch_module, "sleep", bounded_sleep)
    config = replace(_cp3_config(env), required_ci_timeout_seconds=3.5)

    with pytest.raises(orch_module._Blocked, match=reason):
        orch_module._require_v2_published_candidate_ci(config, "1", candidate)

    assert sleeps == [3.5]
    assert all(delay <= config.required_ci_timeout_seconds for delay in sleeps)
    assert head_calls == 2
    assert check_calls == 1


def test_v2_required_ci_head_movement_during_observation_blocks_immediately(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = "c" * 40
    heads = iter((candidate, "d" * 40))
    checks_called = 0
    sleeps: list[float] = []

    def checks(*args: object, **kwargs: object) -> repository.RequiredChecksResult:
        nonlocal checks_called
        checks_called += 1
        return _ci_result("pending", returncode=8)

    monkeypatch.setattr(
        repository, "pr_head_sha", lambda *args, **kwargs: next(heads)
    )
    monkeypatch.setattr(repository, "pr_required_checks", checks)
    monkeypatch.setattr(orch_module, "monotonic", lambda: 0.0)
    monkeypatch.setattr(orch_module, "sleep", sleeps.append)

    with pytest.raises(orch_module._Blocked, match="head moved"):
        orch_module._require_v2_published_candidate_ci(
            _cp3_config(env), "1", candidate
        )

    assert checks_called == 1
    assert sleeps == []


@pytest.mark.parametrize(
    "result",
    [
        repository.RequiredChecksResult(
            checks=[], no_required_checks=False, returncode=0
        ),
        _ci_result("pass", returncode=1),
        _ci_result("pending", returncode=0),
        _ci_result("mystery", returncode=1),
    ],
    ids=("ordinary-empty", "success-wrong-exit", "pending-wrong-exit", "unknown"),
)
def test_v2_required_ci_impossible_results_fail_closed(
    env: Env,
    monkeypatch: pytest.MonkeyPatch,
    result: repository.RequiredChecksResult,
) -> None:
    candidate = "c" * 40
    monkeypatch.setattr(
        repository, "pr_head_sha", lambda *args, **kwargs: candidate
    )
    monkeypatch.setattr(repository, "pr_required_checks", lambda *a, **k: result)
    monkeypatch.setattr(orch_module, "monotonic", lambda: 0.0)

    with pytest.raises(orch_module._Blocked):
        orch_module._require_v2_published_candidate_ci(
            _cp3_config(env), "1", candidate
        )


def test_v2_required_ci_timeout_is_reported_in_required_ci_phase(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _cp3_spec()
    target, checkpoints, pre_closure, _ = _prepared_cp4_context(env, spec)
    implementer_prompts, reviewer_prompts = _install_cp4_agents(
        env, monkeypatch, [_v2_approved(), _v2_approved()]
    )
    now = 0.0
    checks_count = 0

    def clock() -> float:
        return now

    def advance(seconds: float) -> None:
        nonlocal now
        now += seconds

    def no_checks(
        repo: Path, pr_number: str, *, gh_command: tuple[str, ...]
    ) -> repository.RequiredChecksResult:
        nonlocal checks_count
        checks_count += 1
        return repository.RequiredChecksResult(
            checks=[],
            no_required_checks=False,
            returncode=1,
            no_checks_reported=True,
        )

    monkeypatch.setattr(repository, "pr_required_checks", no_checks)
    monkeypatch.setattr(orch_module, "monotonic", clock)
    monkeypatch.setattr(orch_module, "sleep", advance)

    result = orch_module.execute_v2_unpublished_closure(
        replace(_cp3_config(env), required_ci_timeout_seconds=2.0),
        target,
        checkpoints,
        pre_closure,
        repair_acceptor=_cp4_repair_acceptor(env),
    )

    assert not result.completed and result.published
    assert result.terminal_phase is Phase.REQUIRED_CI
    assert "persistent no checks reported" in (result.blocked_reason or "")
    assert checks_count == 1
    assert len(implementer_prompts) == 1
    assert len(reviewer_prompts) == 2


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
    _, reviewer_prompts = _install_cp4_agents(
        env,
        monkeypatch,
        [_v2_approved(), _v2_approved(), _v2_approved()],
        reviewer_profiles=reviewer_profiles,
    )
    recorded = _capture_recorded_review_attempts(monkeypatch)
    histories: list[GateHistory] = []
    checks_count = 0
    moved_sha: str | None = None
    ci_observations = [
        repository.RequiredChecksResult(
            checks=[],
            no_required_checks=False,
            returncode=1,
            no_checks_reported=True,
        ),
        repository.RequiredChecksResult(
            checks=[], no_required_checks=True, returncode=1
        ),
        _ci_result("pending", returncode=8),
        _ci_result("pass", returncode=0),
    ]
    ci_sleeps: list[float] = []

    def move_base_after_first_ci(
        repo: Path, pr_number: str, *, gh_command: tuple[str, ...]
    ) -> repository.RequiredChecksResult:
        nonlocal checks_count, moved_sha
        checks_count += 1
        if checks_count == 1:
            moved_sha = _advance_cp3_origin_main(env, "post-publication-base-move")
        return ci_observations.pop(0)

    monkeypatch.setattr(repository, "pr_required_checks", move_base_after_first_ci)
    monkeypatch.setattr(orch_module, "monotonic", lambda: 0.0)
    monkeypatch.setattr(orch_module, "sleep", ci_sleeps.append)

    result = orch_module.execute_v2_unpublished_closure(
        _cp3_config(env),
        target,
        checkpoints,
        pre_closure,
        repair_acceptor=_cp4_repair_acceptor(env),
        history_sink=histories,
    )

    assert result.completed and result.published
    assert checks_count == 4
    assert ci_observations == []
    assert ci_sleeps == [10.0, 10.0]
    assert moved_sha is not None
    assert result.mode_c_evidence is not None
    assert result.mode_c_evidence.base_sha == moved_sha
    assert result.closure_candidate is not None
    mode_c_prompts = [
        prompt for prompt in reviewer_prompts if "FINAL_CUMULATIVE_AUDIT" in prompt
    ]
    assert len(mode_c_prompts) == 2
    initial_compact, replay_compact = map(
        _mode_c_evidence_from_prompt, mode_c_prompts
    )
    for compact in (initial_compact, replay_compact):
        assert compact["accepted_implementation"] == {
            "base_identity": target.base_sha,
            "head_sha": result.closure_candidate.published_predecessor_sha,
        }
        assert compact["candidate"] == {
            "published_predecessor_sha": (
                result.closure_candidate.published_predecessor_sha
            ),
        }
    assert initial_compact["mode_c_audit_base"] == target.base_sha
    assert replay_compact["mode_c_audit_base"] == moved_sha
    assert f"BASE_SHA: {moved_sha}\n" in mode_c_prompts[1]
    assert f"CANDIDATE_HEAD_SHA: {result.closure_candidate.candidate_head_sha}" in (
        mode_c_prompts[0]
    )
    assert f"CANDIDATE_HEAD_SHA: {result.closure_candidate.candidate_head_sha}" in (
        mode_c_prompts[1]
    )
    assert (
        f"CURRENT_PATCH:\n{result.mode_c_evidence.review_patch.diff_text}\n"
        in mode_c_prompts[1]
    )
    post_publication = [
        attempt
        for context, attempt in recorded
        if context.gate_id == "post-publication-mode-c-replay"
    ]
    assert len(post_publication) == 1
    assert post_publication[0].reviewer_verdict is ReviewVerdict.APPROVED
    assert post_publication[0].findings == ()
    assert post_publication[0].verification is None
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
    _, reviewer_prompts = _install_cp4_agents(
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
    post_publication_prompt = [
        prompt for prompt in reviewer_prompts if "FINAL_CUMULATIVE_AUDIT" in prompt
    ][-1]
    assert "AUTHORITATIVE_MODE_C_EVIDENCE_JSON:" in post_publication_prompt
    assert _mode_c_evidence_from_prompt(post_publication_prompt)[
        "accepted_implementation"
    ]["base_identity"] == target.base_sha
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
