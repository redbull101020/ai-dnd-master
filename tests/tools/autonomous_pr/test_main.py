import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from tools.autonomous_pr.__main__ import main

_TASK_ID = "TSK-9001"


def _run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"
    return result.stdout


def _configure_user(repo: Path) -> None:
    _run_git(["config", "user.email", "harness-test@example.com"], cwd=repo)
    _run_git(["config", "user.name", "Harness Test"], cwd=repo)


def _task_md_text(task_id: str) -> str:
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
        f"| `{task_id}` | `Current` | `P2` | `M` | `engineering` | Test roadmap target | Test task |\n"
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
        "**Roadmap target:** Test roadmap target\n"
        "\n"
        "**Depends on:** —\n"
        "\n"
        "**Contract impact:** `none`\n"
        "\n"
        "### Goal\n"
        "\n"
        "CLI smoke test.\n"
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

    return Env(origin=origin, seed=seed, work=work)


_IMPLEMENTER_SCRIPT = (
    "import sys\n"
    "data = sys.stdin.read()\n"
    "if 'PLAN:' not in data:\n"
    "    print('PLAN: implement the thing')\n"
    "else:\n"
    "    with open('work_output.txt', 'w', encoding='utf-8') as f:\n"
    "        f.write('done\\n')\n"
    "    print('implemented')\n"
)

_REVIEWER_SCRIPT = (
    "import sys\n"
    "data = sys.stdin.read()\n"
    "if 'REVIEW_PATCH:' not in data:\n"
    "    print('APPROVED')\n"
    "elif 'done' in data:\n"
    "    print('APPROVED')\n"
    "else:\n"
    "    print('CHANGES_REQUESTED')\n"
)


def _base_argv(env: Env, *, extra: list[str]) -> list[str]:
    # "--flag=value" form throughout: a bare "-c" value after a separate
    # "--implementer-arg" token looks like an option string to argparse and
    # is rejected, so every value that could itself start with "-" is
    # joined with "=" instead.
    #
    # --verify is shlex-split by the CLI, and shlex's default POSIX mode
    # treats "\" as an escape character -- it would mangle a Windows
    # executable path. Forward slashes are accepted by Windows path APIs
    # too, so using them here sidesteps that without needing a real
    # executable found on PATH.
    verify_python = sys.executable.replace("\\", "/")
    return [
        _TASK_ID,
        "--repo",
        str(env.work),
        "--implementer",
        sys.executable,
        "--implementer-arg=-c",
        f"--implementer-arg={_IMPLEMENTER_SCRIPT}",
        "--reviewer",
        sys.executable,
        "--reviewer-arg=-c",
        f"--reviewer-arg={_REVIEWER_SCRIPT}",
        f"--verify={verify_python} -c \"raise SystemExit(0)\"",
        "--max-repairs",
        "1",
        "--delivery-branch",
        "delivery",
        *extra,
    ]


_ALL_CAPABILITY_FLAGS = [
    "--reviewer-fresh-context-capable",
    "--implementer-no-git-github-write-capability",
    "--reviewer-no-git-github-write-capability",
]


def _origin_branch_exists(env: Env, branch: str) -> bool:
    result = subprocess.run(
        ["git", "--git-dir", str(env.origin), "rev-parse", f"refs/heads/{branch}"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


# --- capability preconditions fail closed before any agent runs ---------------


def test_cli_fails_configuration_when_implementer_no_write_flag_omitted(
    env: Env,
) -> None:
    argv = _base_argv(
        env,
        extra=[
            "--reviewer-fresh-context-capable",
            "--reviewer-no-git-github-write-capability",
            # --implementer-no-git-github-write-capability omitted
        ],
    )

    exit_code = main(argv)

    assert exit_code == 2
    assert not (env.work / "work_output.txt").exists()  # implementer never ran
    assert not _origin_branch_exists(env, "delivery")


def test_cli_fails_configuration_when_reviewer_no_write_flag_omitted(env: Env) -> None:
    argv = _base_argv(
        env,
        extra=[
            "--reviewer-fresh-context-capable",
            "--implementer-no-git-github-write-capability",
            # --reviewer-no-git-github-write-capability omitted
        ],
    )

    exit_code = main(argv)

    assert exit_code == 2
    assert not (env.work / "work_output.txt").exists()
    assert not _origin_branch_exists(env, "delivery")


def test_cli_fails_configuration_when_reviewer_fresh_context_flag_omitted(
    env: Env,
) -> None:
    argv = _base_argv(
        env,
        extra=[
            "--implementer-no-git-github-write-capability",
            "--reviewer-no-git-github-write-capability",
            # --reviewer-fresh-context-capable omitted
        ],
    )

    exit_code = main(argv)

    assert exit_code == 2
    assert not (env.work / "work_output.txt").exists()


# --- happy path with all required capability assertions supplied --------------


def test_cli_happy_path_with_all_required_capability_flags(env: Env) -> None:
    argv = _base_argv(env, extra=list(_ALL_CAPABILITY_FLAGS))

    exit_code = main(argv)

    assert exit_code == 0
    assert _origin_branch_exists(env, "delivery")
    log = _run_git(["log", "-1", "--format=%s"], cwd=env.work).strip()
    assert log.startswith(_TASK_ID)
