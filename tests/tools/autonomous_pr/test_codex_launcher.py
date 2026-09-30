import argparse
import ast
import inspect
import os
import subprocess
from pathlib import Path

import pytest

from tools.autonomous_pr import codex_launcher as launcher
from tools.autonomous_pr.__main__ import _parse_args as parse_generic_args


def _repository(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    environment = repo / ".venv"
    environment.mkdir(parents=True)
    return repo, environment


def _namespace(repo: Path, **overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "selector": "TSK-0037",
        "repo": repo,
        "codex": None,
        "agent_timeout_seconds": 1800.0,
        "verify_timeout_seconds": 1800.0,
        "required_ci_timeout_seconds": 600.0,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _configuration(
    tmp_path: Path, *, generic_argv: tuple[str, ...] = ("delegated",)
) -> launcher.LauncherConfiguration:
    return launcher.LauncherConfiguration(
        selector="TSK-0037",
        repo=tmp_path / "repo",
        codex_executable=tmp_path / "codex.exe",
        temp_directory=tmp_path / "dedicated-temp",
        agent_timeout_seconds=1800.0,
        verify_timeout_seconds=1800.0,
        required_ci_timeout_seconds=600.0,
        generic_argv=generic_argv,
    )


def _expected_generic_argv(repo: Path, executable: Path) -> tuple[str, ...]:
    return (
        "TSK-0037",
        "--repo",
        os.fspath(repo),
        "--implementer",
        os.fspath(executable),
        "--implementer-arg=exec",
        "--implementer-arg=--ephemeral",
        "--implementer-arg=--ignore-user-config",
        "--implementer-arg=--ignore-rules",
        "--implementer-arg=--sandbox",
        "--implementer-arg=workspace-write",
        "--implementer-arg=-c",
        "--implementer-arg=approval_policy=never",
        "--implementer-arg=-c",
        "--implementer-arg=sandbox_workspace_write.network_access=false",
        "--implementer-routine-arg=-c",
        "--implementer-routine-arg=model_reasoning_effort=low",
        "--implementer-routine-arg=-",
        "--implementer-deliberate-arg=-c",
        "--implementer-deliberate-arg=model_reasoning_effort=medium",
        "--implementer-deliberate-arg=-",
        "--implementer-critical-arg=-c",
        "--implementer-critical-arg=model_reasoning_effort=high",
        "--implementer-critical-arg=-",
        "--reviewer",
        os.fspath(executable),
        "--reviewer-arg=exec",
        "--reviewer-arg=--ephemeral",
        "--reviewer-arg=--ignore-user-config",
        "--reviewer-arg=--ignore-rules",
        "--reviewer-arg=--sandbox",
        "--reviewer-arg=read-only",
        "--reviewer-arg=-c",
        "--reviewer-arg=approval_policy=never",
        "--reviewer-deliberate-arg=-c",
        "--reviewer-deliberate-arg=model_reasoning_effort=medium",
        "--reviewer-deliberate-arg=-",
        "--reviewer-critical-arg=-c",
        "--reviewer-critical-arg=model_reasoning_effort=high",
        "--reviewer-critical-arg=-",
        "--reviewer-fresh-context-capable",
        "--implementer-no-git-github-write-capability",
        "--reviewer-no-git-github-write-capability",
        "--agent-timeout-seconds",
        "1800.0",
        "--verify-timeout-seconds",
        "1800.0",
        "--required-ci-timeout-seconds",
        "600.0",
    )


@pytest.mark.parametrize("selector", ["NEXT", "TSK-0001", "TSK-9999"])
def test_parser_accepts_only_canonical_selectors(selector: str) -> None:
    assert launcher._parse_args([selector]).selector == selector


@pytest.mark.parametrize(
    "selector", ["next", "Next", "TSK-1", "TSK-00001", "tsk-0001", "TSK_0001"]
)
def test_parser_rejects_noncanonical_selectors(selector: str) -> None:
    with pytest.raises(SystemExit) as exc_info:
        launcher._parse_args([selector])
    assert exc_info.value.code == 2


def test_parser_public_option_surface_is_exact() -> None:
    parser = launcher._build_parser()
    public_options = {
        option
        for action in parser._actions
        for option in action.option_strings
        if option != "--help" and option != "-h"
    }
    assert public_options == {
        "--repo",
        "--codex",
        "--agent-timeout-seconds",
        "--verify-timeout-seconds",
        "--required-ci-timeout-seconds",
    }


def test_timeout_defaults_and_forward_values_are_unchanged() -> None:
    defaults = launcher._parse_args(["NEXT"])
    custom = launcher._parse_args(
        [
            "NEXT",
            "--agent-timeout-seconds",
            "1.25",
            "--verify-timeout-seconds",
            "2.5",
            "--required-ci-timeout-seconds",
            "3.75",
        ]
    )
    assert (
        defaults.agent_timeout_seconds,
        defaults.verify_timeout_seconds,
        defaults.required_ci_timeout_seconds,
    ) == (1800.0, 1800.0, 600.0)
    assert (
        custom.agent_timeout_seconds,
        custom.verify_timeout_seconds,
        custom.required_ci_timeout_seconds,
    ) == (1.25, 2.5, 3.75)


@pytest.mark.parametrize("option", ["agent", "verify", "required-ci"])
@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "-inf"])
def test_parser_rejects_nonpositive_or_nonfinite_timeouts(
    option: str, value: str
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        launcher._parse_args(["NEXT", f"--{option}-timeout-seconds", value])
    assert exc_info.value.code == 2


@pytest.mark.parametrize(
    "forbidden",
    [
        "--implementer-arg",
        "--reviewer-arg",
        "--model",
        "--provider",
        "--sandbox",
        "--ask-for-approval",
        "--add-dir",
        "--delivery-branch",
        "--verify",
        "--merge",
        "--auto-merge",
        "-c",
    ],
)
def test_parser_has_no_arbitrary_configuration_escape_hatches(forbidden: str) -> None:
    with pytest.raises(SystemExit) as exc_info:
        launcher._parse_args(["NEXT", forbidden, "value"])
    assert exc_info.value.code == 2


def test_repository_is_normalized_and_bound_to_exact_venv(tmp_path: Path) -> None:
    repo, environment = _repository(tmp_path)
    relative = repo / "child" / ".."
    (repo / "child").mkdir()

    assert launcher._validate_repository(relative, prefix=os.fspath(environment)) == repo


def test_repository_must_exist_as_directory(tmp_path: Path) -> None:
    with pytest.raises(launcher.LauncherConfigurationError, match="cannot resolve"):
        launcher._validate_repository(tmp_path / "missing", prefix="unused")


def test_repository_rejects_missing_or_wrong_venv(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(launcher.LauncherConfigurationError, match="is missing"):
        launcher._validate_repository(repo, prefix=os.fspath(tmp_path))

    environment = repo / ".venv"
    environment.mkdir()
    with pytest.raises(launcher.LauncherConfigurationError, match="must run under"):
        launcher._validate_repository(repo, prefix=os.fspath(tmp_path))


@pytest.mark.parametrize("kind", ["file", "directory"])
def test_repository_refuses_codex_file_or_directory(tmp_path: Path, kind: str) -> None:
    repo, environment = _repository(tmp_path)
    local_codex = repo / ".codex"
    if kind == "file":
        local_codex.write_text("config", encoding="utf-8")
    else:
        local_codex.mkdir()
    with pytest.raises(launcher.LauncherConfigurationError, match="not allowed"):
        launcher._validate_repository(repo, prefix=os.fspath(environment))


@pytest.mark.parametrize("entry_kind", ["symlink", "broken symlink"])
def test_repository_refuses_codex_symlink_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entry_kind: str
) -> None:
    repo, environment = _repository(tmp_path)
    local_codex = repo / ".codex"
    original_lexists = os.path.lexists
    monkeypatch.setattr(
        launcher.os.path,
        "lexists",
        lambda path: True if Path(path) == local_codex else original_lexists(path),
    )
    with pytest.raises(launcher.LauncherConfigurationError, match="not allowed"):
        launcher._validate_repository(repo, prefix=os.fspath(environment))


def test_codex_precedence_is_explicit_then_env_then_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected: list[tuple[str, str]] = []

    def concrete(candidate: str, *, source: str) -> Path:
        selected.append((candidate, source))
        return Path(candidate)

    monkeypatch.setattr(launcher, "_concrete_executable", concrete)
    monkeypatch.setattr(launcher.shutil, "which", lambda command: "/path/codex")
    assert launcher._resolve_codex(Path("/explicit"), environ={}) == Path("/explicit")
    assert launcher._resolve_codex(
        None, environ={"AUTONOMOUS_PR_CODEX_EXE": "/env"}
    ) == Path("/env")
    assert launcher._resolve_codex(None, environ={}) == Path("/path/codex")
    assert selected == [
        (os.fspath(Path("/explicit")), "--codex"),
        ("/env", "AUTONOMOUS_PR_CODEX_EXE"),
        ("/path/codex", "PATH"),
    ]


@pytest.mark.parametrize("source", ["explicit", "environment", "path"])
def test_invalid_selected_candidate_never_falls_through(
    monkeypatch: pytest.MonkeyPatch, source: str
) -> None:
    calls: list[str] = []

    def concrete(candidate: str, *, source: str) -> Path:
        calls.append(source)
        raise launcher.LauncherConfigurationError("invalid selected candidate")

    monkeypatch.setattr(launcher, "_concrete_executable", concrete)
    monkeypatch.setattr(
        launcher.shutil,
        "which",
        lambda command: "/path/codex" if source == "path" else None,
    )
    explicit = Path("/explicit") if source == "explicit" else None
    environment = (
        {"AUTONOMOUS_PR_CODEX_EXE": "/env"} if source == "environment" else {}
    )
    with pytest.raises(launcher.LauncherConfigurationError, match="invalid"):
        launcher._resolve_codex(explicit, environ=environment)
    assert len(calls) == 1


@pytest.mark.parametrize("count", [0, 1, 2])
def test_windows_fallback_requires_exactly_one_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, count: int
) -> None:
    candidates = tuple(tmp_path / f"install-{index}" / "codex.exe" for index in range(count))
    monkeypatch.setattr(launcher, "_is_windows", lambda: True)
    monkeypatch.setattr(launcher.shutil, "which", lambda command: None)
    monkeypatch.setattr(launcher, "_windows_fallback_candidates", lambda environ: candidates)
    monkeypatch.setattr(
        launcher,
        "_concrete_executable",
        lambda candidate, *, source: Path(candidate),
    )
    if count == 1:
        assert launcher._resolve_codex(None, environ={}) == candidates[0]
    else:
        expected = "not found" if count == 0 else "multiple"
        with pytest.raises(launcher.LauncherConfigurationError, match=expected):
            launcher._resolve_codex(None, environ={})


def test_concrete_executable_is_resolved_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    executable = tmp_path / "bin" / "codex.exe"
    executable.parent.mkdir()
    executable.write_bytes(b"binary")
    monkeypatch.setattr(launcher.shutil, "which", lambda candidate: os.fspath(executable))
    assert launcher._concrete_executable("codex", source="PATH") == executable.resolve()


def _completed(
    *, stdout: str = "codex-cli 1.2.3\n", stderr: str = "", returncode: int = 0
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["codex", "--version"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_version_identity_uses_only_bounded_shell_false_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed["args"] = args
        observed.update(kwargs)
        return _completed(stderr="codex-cli 9.0")

    monkeypatch.setattr(launcher.subprocess, "run", run)
    executable = Path("/resolved/codex")
    launcher._check_codex_identity(executable)
    assert observed["args"] == ([os.fspath(executable), "--version"],)
    assert observed["timeout"] == 10.0
    assert observed["shell"] is False


@pytest.mark.parametrize(
    ("result", "message"),
    [
        (_completed(returncode=1), "status 1"),
        (_completed(stdout="codex-cli"), "does not contain"),
        (_completed(stdout="other-cli 1.0"), "does not contain"),
    ],
)
def test_version_identity_rejects_nonzero_or_malformed_output(
    monkeypatch: pytest.MonkeyPatch,
    result: subprocess.CompletedProcess[str],
    message: str,
) -> None:
    monkeypatch.setattr(launcher.subprocess, "run", lambda *args, **kwargs: result)
    with pytest.raises(launcher.LauncherConfigurationError, match=message):
        launcher._check_codex_identity(Path("codex"))


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        (subprocess.TimeoutExpired("codex", 10), "timed out"),
        (OSError("cannot launch"), "cannot launch"),
    ],
)
def test_version_identity_translates_launch_failures(
    monkeypatch: pytest.MonkeyPatch, failure: BaseException, message: str
) -> None:
    def fail(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise failure

    monkeypatch.setattr(launcher.subprocess, "run", fail)
    with pytest.raises(launcher.LauncherConfigurationError, match=message):
        launcher._check_codex_identity(Path("codex"))


def test_temp_directory_is_outside_repo_and_probed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    system_temp = tmp_path / "system-temp"
    system_temp.mkdir()
    monkeypatch.setattr(launcher.tempfile, "gettempdir", lambda: os.fspath(system_temp))

    prepared = launcher._prepare_temp_directory(repo)

    assert prepared == system_temp / "ai-dnd-autonomous"
    assert not prepared.is_relative_to(repo)
    assert list(prepared.iterdir()) == []


def test_temp_directory_inside_repo_or_probe_failure_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(launcher.tempfile, "gettempdir", lambda: os.fspath(repo))
    with pytest.raises(launcher.LauncherConfigurationError, match="outside"):
        launcher._prepare_temp_directory(repo)

    system_temp = tmp_path / "system-temp"
    system_temp.mkdir()
    monkeypatch.setattr(launcher.tempfile, "gettempdir", lambda: os.fspath(system_temp))

    def fail_probe(*args: object, **kwargs: object) -> object:
        raise OSError("read only")

    monkeypatch.setattr(launcher.tempfile, "NamedTemporaryFile", fail_probe)
    with pytest.raises(launcher.LauncherConfigurationError, match="not writable"):
        launcher._prepare_temp_directory(repo)


def test_fixed_common_and_profile_arrays_are_exact() -> None:
    assert launcher.IMPLEMENTER_COMMON_ARGS == (
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--sandbox",
        "workspace-write",
        "-c",
        "approval_policy=never",
        "-c",
        "sandbox_workspace_write.network_access=false",
    )
    assert launcher.IMPLEMENTER_PROFILE_ARGS == {
        "routine": ("-c", "model_reasoning_effort=low", "-"),
        "deliberate": ("-c", "model_reasoning_effort=medium", "-"),
        "critical": ("-c", "model_reasoning_effort=high", "-"),
    }
    assert launcher.REVIEWER_COMMON_ARGS == (
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--sandbox",
        "read-only",
        "-c",
        "approval_policy=never",
    )
    assert launcher.REVIEWER_PROFILE_ARGS == {
        "deliberate": ("-c", "model_reasoning_effort=medium", "-"),
        "critical": ("-c", "model_reasoning_effort=high", "-"),
    }


def test_generic_argv_uses_equals_form_and_required_assertions(tmp_path: Path) -> None:
    argv = launcher._compose_generic_argv(
        selector="TSK-0037",
        repo=tmp_path,
        codex_executable=tmp_path / "codex.exe",
        agent_timeout_seconds=1.25,
        verify_timeout_seconds=2.5,
        required_ci_timeout_seconds=3.75,
    )
    generic = parse_generic_args(list(argv))

    assert generic.task_id == "TSK-0037"
    assert generic.implementer_args == list(launcher.IMPLEMENTER_COMMON_ARGS)
    assert generic.implementer_routine_args == ["-c", "model_reasoning_effort=low", "-"]
    assert generic.reviewer_critical_args == ["-c", "model_reasoning_effort=high", "-"]
    assert generic.reviewer_fresh_context_capable is True
    assert generic.implementer_no_git_github_write_capability is True
    assert generic.reviewer_no_git_github_write_capability is True
    assert generic.agent_timeout_seconds == 1.25
    assert generic.verify_timeout_seconds == 2.5
    assert generic.required_ci_timeout_seconds == 3.75
    opaque = [token for token in argv if "-arg=" in token]
    assert opaque
    assert all(token.startswith("--") and "=" in token for token in opaque)


def test_fixed_child_args_use_inline_approval_policy_without_legacy_flag() -> None:
    for common in (launcher.IMPLEMENTER_COMMON_ARGS, launcher.REVIEWER_COMMON_ARGS):
        assert "--ask-for-approval" not in common
        assert common.count("approval_policy=never") == 1
        policy_index = common.index("approval_policy=never")
        assert common[policy_index - 1] == "-c"

    assert launcher.IMPLEMENTER_COMMON_ARGS[
        launcher.IMPLEMENTER_COMMON_ARGS.index("--sandbox") + 1
    ] == "workspace-write"
    assert launcher.REVIEWER_COMMON_ARGS[
        launcher.REVIEWER_COMMON_ARGS.index("--sandbox") + 1
    ] == "read-only"
    assert "sandbox_workspace_write.network_access=false" in (
        launcher.IMPLEMENTER_COMMON_ARGS
    )


def test_generic_argv_is_exact_including_all_forwarded_values(tmp_path: Path) -> None:
    repo = (tmp_path / "repo").resolve()
    executable = (tmp_path / "codex.exe").resolve()

    argv = launcher._compose_generic_argv(
        selector="TSK-0037",
        repo=repo,
        codex_executable=executable,
        agent_timeout_seconds=1800.0,
        verify_timeout_seconds=1800.0,
        required_ci_timeout_seconds=600.0,
    )

    assert argv == _expected_generic_argv(repo, executable)
    assert "--delivery-branch" not in argv


def test_composed_argv_has_no_dangerous_or_public_escape_tokens(tmp_path: Path) -> None:
    argv = launcher._compose_generic_argv(
        selector="NEXT",
        repo=tmp_path,
        codex_executable=tmp_path / "codex.exe",
        agent_timeout_seconds=1800.0,
        verify_timeout_seconds=1800.0,
        required_ci_timeout_seconds=600.0,
    )
    joined = "\n".join(argv)
    for forbidden in (
        "--dangerously-bypass-approvals-and-sandbox",
        "--yolo",
        "danger-full-access",
        "network_access=true",
        "--add-dir",
        "--delivery-branch",
        "--model",
        "--provider",
        "--merge",
        "--auto-merge",
        "--ask-for-approval",
    ):
        assert forbidden not in joined


@pytest.mark.parametrize("initial", [{}, {"CODEX_HOME": "exact-auth-home"}])
def test_configuration_preserves_codex_home_semantics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, initial: dict[str, str]
) -> None:
    repo, _ = _repository(tmp_path)
    environment = dict(initial)
    executable = tmp_path / "codex.exe"
    temp_directory = tmp_path / "temp" / "ai-dnd-autonomous"
    monkeypatch.setattr(launcher, "_validate_repository", lambda repo, prefix=None: repo.resolve())
    monkeypatch.setattr(
        launcher, "_resolve_codex", lambda explicit, environ=None: executable
    )
    monkeypatch.setattr(launcher, "_check_codex_identity", lambda executable: None)
    monkeypatch.setattr(launcher, "_prepare_temp_directory", lambda repo: temp_directory)

    config = launcher._prepare_configuration(
        _namespace(repo), environ=environment, prefix="ignored"
    )

    assert config.codex_executable == executable
    assert environment == initial
    assert ("CODEX_HOME" in environment) == ("CODEX_HOME" in initial)


def test_main_delegates_exact_argv_once_and_returns_exit_code_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = (tmp_path / "repo").resolve()
    executable = (tmp_path / "codex.exe").resolve()
    expected = _expected_generic_argv(repo, executable)
    configuration = _configuration(tmp_path, generic_argv=expected)
    calls: list[list[str]] = []
    monkeypatch.setattr(
        launcher, "_prepare_configuration", lambda parsed: configuration
    )

    def generic_main(argv: list[str]) -> int:
        calls.append(argv)
        return 73

    monkeypatch.setattr(launcher.generic_cli, "main", generic_main)

    assert launcher.main(["TSK-0037"]) == 73
    assert calls == [list(expected)]


def test_generic_stdout_and_stderr_are_untouched(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configuration = _configuration(tmp_path)
    monkeypatch.setattr(
        launcher, "_prepare_configuration", lambda parsed: configuration
    )

    def generic_main(argv: list[str]) -> int:
        print("generic stdout")
        print("generic stderr", file=launcher.sys.stderr)
        return 0

    monkeypatch.setattr(launcher.generic_cli, "main", generic_main)

    assert launcher.main(["NEXT"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "generic stdout\n"
    assert captured.err == "generic stderr\n"


def test_delegate_sets_temp_variables_and_restores_environment_after_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configuration = _configuration(tmp_path)
    original = {"TEMP": "old-temp", "TMP": None, "TMPDIR": "old-tmpdir"}
    monkeypatch.setenv("TEMP", original["TEMP"] or "")
    monkeypatch.delenv("TMP", raising=False)
    monkeypatch.setenv("TMPDIR", original["TMPDIR"] or "")
    observed: dict[str, str | None] = {}

    def generic_main(argv: list[str]) -> int:
        observed.update({name: os.environ.get(name) for name in ("TEMP", "TMP", "TMPDIR")})
        return 11

    monkeypatch.setattr(launcher.generic_cli, "main", generic_main)

    assert launcher._delegate(configuration) == 11
    target = os.fspath(configuration.temp_directory)
    assert observed == {"TEMP": target, "TMP": target, "TMPDIR": target}
    assert os.environ["TEMP"] == "old-temp"
    assert "TMP" not in os.environ
    assert os.environ["TMPDIR"] == "old-tmpdir"


def test_delegate_restores_environment_after_generic_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configuration = _configuration(tmp_path)
    monkeypatch.delenv("TEMP", raising=False)
    monkeypatch.setenv("TMP", "old-tmp")
    monkeypatch.delenv("TMPDIR", raising=False)

    def generic_main(argv: list[str]) -> int:
        raise RuntimeError("generic failure")

    monkeypatch.setattr(launcher.generic_cli, "main", generic_main)

    with pytest.raises(RuntimeError, match="generic failure"):
        launcher._delegate(configuration)
    assert "TEMP" not in os.environ
    assert os.environ["TMP"] == "old-tmp"
    assert "TMPDIR" not in os.environ


@pytest.mark.parametrize("codex_home", [None, "exact-auth-home"])
def test_delegation_never_changes_codex_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, codex_home: str | None
) -> None:
    configuration = _configuration(tmp_path)
    if codex_home is None:
        monkeypatch.delenv("CODEX_HOME", raising=False)
    else:
        monkeypatch.setenv("CODEX_HOME", codex_home)
    observed: list[str | None] = []
    monkeypatch.setattr(
        launcher.generic_cli,
        "main",
        lambda argv: observed.append(os.environ.get("CODEX_HOME")) or 0,
    )

    launcher._delegate(configuration)

    assert observed == [codex_home]
    assert os.environ.get("CODEX_HOME") == codex_home
    assert ("CODEX_HOME" in os.environ) == (codex_home is not None)


@pytest.mark.parametrize(
    "message",
    [
        "invalid repository",
        "wrong virtual environment",
        "repository .codex is present",
        "Codex executable not found",
        "Codex identity mismatch",
        "temp directory is not writable",
    ],
)
def test_launcher_configuration_failures_return_two_without_delegation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    message: str,
) -> None:
    calls: list[list[str]] = []

    def fail(parsed: argparse.Namespace) -> launcher.LauncherConfiguration:
        raise launcher.LauncherConfigurationError(message)

    monkeypatch.setattr(launcher, "_prepare_configuration", fail)
    monkeypatch.setattr(
        launcher.generic_cli, "main", lambda argv: calls.append(argv) or 0
    )

    assert launcher.main(["NEXT"]) == 2
    assert calls == []
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"codex launcher configuration error: {message}\n"


def test_argparse_failure_never_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(
        launcher.generic_cli, "main", lambda argv: calls.append(argv) or 0
    )
    with pytest.raises(SystemExit) as exc_info:
        launcher.main(["not-a-selector"])
    assert exc_info.value.code == 2
    assert calls == []


def test_launcher_has_no_direct_orchestrator_import_or_workflow_calls() -> None:
    tree = ast.parse(inspect.getsource(launcher))
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert not any(module.endswith("orchestrator") for module in imported_modules)
    assert "run" not in called_names
    assert "OrchestratorConfig" not in called_names
    assert "git" not in called_names
    assert "gh" not in called_names
