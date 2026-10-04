import argparse
import ast
import inspect
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from tools.autonomous_pr import codex_launcher as launcher
from tools.autonomous_pr.__main__ import _parse_args as parse_generic_args


ROOT = Path(__file__).resolve().parents[3]


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
        "verify_timeout_seconds": 3600.0,
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
        pip_cache_directory=tmp_path / "dedicated-temp" / "pip-cache",
        agent_timeout_seconds=1800.0,
        verify_timeout_seconds=3600.0,
        required_ci_timeout_seconds=600.0,
        generic_argv=generic_argv,
    )


def _expected_generic_argv(
    repo: Path, executable: Path, *, windows: bool = False
) -> tuple[str, ...]:
    implementer_platform_args = (
        ("--implementer-arg=-c", "--implementer-arg=windows.sandbox=mxc")
        if windows
        else ()
    )
    reviewer_platform_args = (
        ("--reviewer-arg=-c", "--reviewer-arg=windows.sandbox=mxc")
        if windows
        else ()
    )
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
        *implementer_platform_args,
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
        "--reviewer-arg=workspace-write",
        "--reviewer-arg=-c",
        "--reviewer-arg=approval_policy=never",
        "--reviewer-arg=-c",
        "--reviewer-arg=sandbox_workspace_write.network_access=false",
        *reviewer_platform_args,
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
        "3600.0",
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
    ) == (1800.0, 3600.0, 600.0)
    assert (
        custom.agent_timeout_seconds,
        custom.verify_timeout_seconds,
        custom.required_ci_timeout_seconds,
    ) == (1.25, 2.5, 3.75)


def test_generic_cli_timeout_defaults_remain_provider_neutral(tmp_path: Path) -> None:
    argv = list(_expected_generic_argv(tmp_path, tmp_path / "codex.exe"))
    for option in (
        "--agent-timeout-seconds",
        "--verify-timeout-seconds",
        "--required-ci-timeout-seconds",
    ):
        index = argv.index(option)
        del argv[index : index + 2]

    generic = parse_generic_args(argv)

    assert (
        generic.agent_timeout_seconds,
        generic.verify_timeout_seconds,
        generic.required_ci_timeout_seconds,
    ) == (600.0, 600.0, 600.0)


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


def _loaded_package() -> object:
    return launcher.sys.modules[launcher.__package__]


def _provenance_tree(root: Path) -> Path:
    package_root = root / "tools" / "autonomous_pr"
    package_root.mkdir(parents=True)
    (package_root / "codex_launcher.py").write_text("", encoding="utf-8")
    (package_root / "__main__.py").write_text("", encoding="utf-8")
    return package_root


def _directory_alias(alias: Path, target: Path) -> None:
    try:
        alias.symlink_to(target, target_is_directory=True)
        return
    except OSError:
        if os.name != "nt":
            raise
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", os.fspath(alias), os.fspath(target)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        shell=False,
    )
    if completed.returncode != 0:
        raise OSError(completed.stderr or completed.stdout)


def test_selected_repository_package_provenance_passes() -> None:
    launcher._validate_loaded_package_provenance(ROOT)


@pytest.mark.skipif(os.name != "nt", reason="Windows case-folding contract")
def test_case_only_selected_repository_spelling_is_accepted() -> None:
    launcher._validate_loaded_package_provenance(Path(os.fspath(ROOT).swapcase()))


def test_foreign_package_root_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    foreign_root = _provenance_tree(tmp_path / "foreign")
    monkeypatch.setattr(_loaded_package(), "__path__", [os.fspath(foreign_root)])

    with pytest.raises(launcher.LauncherConfigurationError, match="package root"):
        launcher._validate_loaded_package_provenance(ROOT)


@pytest.mark.parametrize(
    ("module", "filename", "description"),
    [
        (launcher, "codex_launcher.py", "codex_launcher module"),
        (launcher.generic_cli, "__main__.py", "generic_cli module"),
    ],
)
def test_foreign_loaded_module_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    module: object,
    filename: str,
    description: str,
) -> None:
    foreign_file = tmp_path / "foreign" / filename
    foreign_file.parent.mkdir()
    foreign_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(module, "__file__", os.fspath(foreign_file))

    with pytest.raises(launcher.LauncherConfigurationError, match=description):
        launcher._validate_loaded_package_provenance(ROOT)


@pytest.mark.parametrize("module", [launcher, launcher.generic_cli])
def test_missing_loaded_module_file_fails(
    monkeypatch: pytest.MonkeyPatch, module: object
) -> None:
    monkeypatch.delattr(module, "__file__")

    with pytest.raises(launcher.LauncherConfigurationError, match="has no __file__"):
        launcher._validate_loaded_package_provenance(ROOT)


@pytest.mark.parametrize("package_roots", [None, (), ("same", "same")])
def test_missing_empty_or_multiple_package_roots_fail(
    monkeypatch: pytest.MonkeyPatch, package_roots: object
) -> None:
    package = _loaded_package()
    if package_roots is None:
        monkeypatch.delattr(package, "__path__")
        expected = "no package search path"
    else:
        monkeypatch.setattr(package, "__path__", package_roots)
        expected = "exactly one search root"

    with pytest.raises(launcher.LauncherConfigurationError, match=expected):
        launcher._validate_loaded_package_provenance(ROOT)


def test_unresolvable_loaded_path_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "missing-package-root"
    monkeypatch.setattr(_loaded_package(), "__path__", [os.fspath(missing)])

    with pytest.raises(launcher.LauncherConfigurationError, match="cannot resolve"):
        launcher._validate_loaded_package_provenance(ROOT)


def test_resolved_alias_of_selected_repository_is_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    alias = tmp_path / "selected-package-alias"
    _directory_alias(alias, ROOT / "tools" / "autonomous_pr")
    monkeypatch.setattr(_loaded_package(), "__path__", [os.fspath(alias)])
    monkeypatch.setattr(launcher, "__file__", os.fspath(alias / "codex_launcher.py"))
    monkeypatch.setattr(
        launcher.generic_cli, "__file__", os.fspath(alias / "__main__.py")
    )

    launcher._validate_loaded_package_provenance(ROOT)


def test_symlink_alias_to_foreign_source_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected_package = _provenance_tree(tmp_path / "selected")
    foreign_package = _provenance_tree(tmp_path / "foreign")
    alias = tmp_path / "foreign-package-alias"
    _directory_alias(alias, foreign_package)
    monkeypatch.setattr(_loaded_package(), "__path__", [os.fspath(alias)])
    monkeypatch.setattr(launcher, "__file__", os.fspath(alias / "codex_launcher.py"))
    monkeypatch.setattr(
        launcher.generic_cli, "__file__", os.fspath(alias / "__main__.py")
    )

    with pytest.raises(launcher.LauncherConfigurationError, match="package root"):
        launcher._validate_loaded_package_provenance(selected_package.parents[1])


def test_provenance_failure_precedes_all_later_launcher_actions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    repo = tmp_path / "repo"

    def repository(*args: object, **kwargs: object) -> Path:
        calls.append("repository")
        return repo

    def provenance(candidate: Path) -> None:
        calls.append("provenance")
        raise launcher.LauncherConfigurationError("foreign package")

    def forbidden(name: str) -> object:
        def fail(*args: object, **kwargs: object) -> object:
            calls.append(name)
            raise AssertionError(f"{name} must not be called")

        return fail

    monkeypatch.setattr(launcher, "_validate_repository", repository)
    monkeypatch.setattr(launcher, "_validate_loaded_package_provenance", provenance)
    monkeypatch.setattr(launcher, "_resolve_codex", forbidden("resolve Codex"))
    monkeypatch.setattr(launcher, "_check_codex_identity", forbidden("Codex identity"))
    monkeypatch.setattr(launcher, "_prepare_temp_directory", forbidden("temp directory"))
    monkeypatch.setattr(
        launcher, "_prepare_pip_cache_directory", forbidden("pip cache directory")
    )
    monkeypatch.setattr(launcher, "_delegate", forbidden("generic delegation"))

    assert launcher.main(["NEXT", "--repo", os.fspath(repo)]) == 2
    assert calls == ["repository", "provenance"]


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


def _runtime_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    system_temp = tmp_path / "system-temp"
    system_temp.mkdir()
    root = system_temp / "ai-dnd-autonomous"
    cache = root / "pip-cache"
    monkeypatch.setattr(launcher.tempfile, "gettempdir", lambda: os.fspath(system_temp))
    return repo, system_temp, root, cache


def _symlink_or_skip(alias: Path, target: Path, *, directory: bool = True) -> None:
    try:
        alias.symlink_to(target, target_is_directory=directory)
    except OSError as exc:
        pytest.skip(f"filesystem symlink primitive unavailable: {exc}")


def _junction_or_skip(alias: Path, target: Path) -> None:
    if os.name != "nt" or not hasattr(Path, "is_junction"):
        pytest.skip("Windows junction predicate unavailable")
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", os.fspath(alias), os.fspath(target)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        shell=False,
    )
    if completed.returncode != 0:
        pytest.skip(f"Windows junction primitive unavailable: {completed.stderr}")


def test_runtime_root_and_cache_are_real_probed_directories_outside_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, expected_root, expected_cache = _runtime_paths(tmp_path, monkeypatch)

    root = launcher._prepare_temp_directory(repo)
    cache = launcher._prepare_pip_cache_directory(repo, root)

    assert root == expected_root.resolve()
    assert cache == expected_cache.resolve()
    assert root.is_dir() and not root.is_symlink() and not launcher._is_junction(root)
    assert cache.is_dir() and not cache.is_symlink() and not launcher._is_junction(cache)
    assert not root.is_relative_to(repo.resolve())
    assert not cache.is_relative_to(repo.resolve())
    assert cache.parent == root
    assert list(cache.iterdir()) == []


@pytest.mark.parametrize("entry", ["root", "cache"])
def test_launcher_owned_directory_rejects_preexisting_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entry: str
) -> None:
    repo, _, root_path, cache_path = _runtime_paths(tmp_path, monkeypatch)
    if entry == "root":
        root_path.write_text("not a directory", encoding="utf-8")
        with pytest.raises(launcher.LauncherConfigurationError, match="not a directory"):
            launcher._prepare_temp_directory(repo)
    else:
        root = launcher._prepare_temp_directory(repo)
        cache_path.write_text("not a directory", encoding="utf-8")
        with pytest.raises(launcher.LauncherConfigurationError, match="not a directory"):
            launcher._prepare_pip_cache_directory(repo, root)


@pytest.mark.parametrize("entry", ["root", "cache"])
def test_launcher_owned_directory_rejects_broken_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entry: str
) -> None:
    repo, _, root_path, cache_path = _runtime_paths(tmp_path, monkeypatch)
    if entry == "cache":
        root = launcher._prepare_temp_directory(repo)
        alias = cache_path
        prepare = lambda: launcher._prepare_pip_cache_directory(repo, root)
    else:
        alias = root_path
        prepare = lambda: launcher._prepare_temp_directory(repo)
    _symlink_or_skip(alias, tmp_path / "missing-target")

    with pytest.raises(launcher.LauncherConfigurationError, match="symlink"):
        prepare()


@pytest.mark.parametrize("entry", ["root", "cache"])
@pytest.mark.parametrize("escape", [False, True])
def test_launcher_owned_directory_rejects_symlink_including_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, escape: bool, entry: str
) -> None:
    repo, system_temp, root_path, cache_path = _runtime_paths(tmp_path, monkeypatch)
    if entry == "cache":
        root = launcher._prepare_temp_directory(repo)
        alias = cache_path
        prepare = lambda: launcher._prepare_pip_cache_directory(repo, root)
    else:
        alias = root_path
        prepare = lambda: launcher._prepare_temp_directory(repo)
    target = (tmp_path / "foreign") if escape else (system_temp / "local-target")
    target.mkdir()
    _symlink_or_skip(alias, target)

    with pytest.raises(launcher.LauncherConfigurationError, match="symlink"):
        prepare()


@pytest.mark.parametrize("entry", ["root", "cache"])
@pytest.mark.parametrize("escape", [False, True])
def test_launcher_owned_directory_rejects_windows_junction_including_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, escape: bool, entry: str
) -> None:
    repo, system_temp, root_path, cache_path = _runtime_paths(tmp_path, monkeypatch)
    if entry == "cache":
        root = launcher._prepare_temp_directory(repo)
        alias = cache_path
        prepare = lambda: launcher._prepare_pip_cache_directory(repo, root)
    else:
        alias = root_path
        prepare = lambda: launcher._prepare_temp_directory(repo)
    target = (tmp_path / "foreign") if escape else (system_temp / "local-target")
    target.mkdir()
    _junction_or_skip(alias, target)

    with pytest.raises(launcher.LauncherConfigurationError, match="junction"):
        prepare()


@pytest.mark.parametrize("entry", ["root", "cache"])
def test_launcher_owned_directory_is_rechecked_after_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entry: str
) -> None:
    repo, _, root_path, cache_path = _runtime_paths(tmp_path, monkeypatch)
    if entry == "cache":
        root = launcher._prepare_temp_directory(repo)
        target = cache_path
        prepare = lambda: launcher._prepare_pip_cache_directory(repo, root)
    else:
        target = root_path
        prepare = lambda: launcher._prepare_temp_directory(repo)
    observed: list[tuple[Path, bool]] = []
    original = launcher._validate_launcher_owned_directory_entry

    def record(path: Path, *, description: str) -> None:
        observed.append((path, os.path.lexists(path)))
        original(path, description=description)

    monkeypatch.setattr(launcher, "_validate_launcher_owned_directory_entry", record)

    prepare()

    assert observed == [(target, True)]


@pytest.mark.parametrize("entry", ["root", "cache"])
@pytest.mark.parametrize(
    "failure", ["directory-create", "probe-create", "write", "flush", "close", "remove"]
)
def test_runtime_directory_create_write_remove_failures_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entry: str,
    failure: str,
) -> None:
    repo, _, root_path, cache_path = _runtime_paths(tmp_path, monkeypatch)
    if entry == "cache":
        root = launcher._prepare_temp_directory(repo)
        target = cache_path
        prepare = lambda: launcher._prepare_pip_cache_directory(repo, root)
    else:
        target = root_path
        prepare = lambda: launcher._prepare_temp_directory(repo)

    if failure == "directory-create":
        original_mkdir = Path.mkdir

        def fail_mkdir(path: Path, *args: object, **kwargs: object) -> None:
            if path == target:
                raise OSError("create denied")
            original_mkdir(path, *args, **kwargs)

        monkeypatch.setattr(Path, "mkdir", fail_mkdir)
        expected = "cannot create"
    elif failure == "probe-create":
        original_named_temporary_file = tempfile.NamedTemporaryFile

        def fail_probe_create(*args: object, **kwargs: object) -> object:
            if Path(kwargs["dir"]) == target:
                raise OSError("probe create denied")
            return original_named_temporary_file(*args, **kwargs)

        monkeypatch.setattr(
            launcher.tempfile, "NamedTemporaryFile", fail_probe_create
        )
        expected = "create/write/remove probe"
    elif failure in {"write", "flush", "close"}:
        original_named_temporary_file = tempfile.NamedTemporaryFile

        class FailingProbe:
            def __init__(self, wrapped: object) -> None:
                self.wrapped = wrapped
                self.name = wrapped.name  # type: ignore[attr-defined]

            def __enter__(self) -> "FailingProbe":
                return self

            def __exit__(self, *args: object) -> None:
                self.wrapped.close()  # type: ignore[attr-defined]
                if failure == "close":
                    raise OSError("close denied")

            def write(self, value: bytes) -> object:
                if failure == "write":
                    raise OSError("write denied")
                return self.wrapped.write(value)  # type: ignore[attr-defined,no-any-return]

            def flush(self) -> object:
                if failure == "flush":
                    raise OSError("flush denied")
                return self.wrapped.flush()  # type: ignore[attr-defined,no-any-return]

        def fail_probe_stage(*args: object, **kwargs: object) -> object:
            wrapped = original_named_temporary_file(*args, **kwargs)
            if Path(kwargs["dir"]) == target:
                return FailingProbe(wrapped)
            return wrapped

        monkeypatch.setattr(launcher.tempfile, "NamedTemporaryFile", fail_probe_stage)
        expected = "create/write/remove probe"
    else:
        original_unlink = Path.unlink

        def fail_remove(path: Path, *args: object, **kwargs: object) -> None:
            if path.parent == target and path.name.startswith("write-probe-"):
                raise OSError("remove denied")
            original_unlink(path, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", fail_remove)
        expected = "create/write/remove probe"

    with pytest.raises(launcher.LauncherConfigurationError, match=expected):
        prepare()


def test_runtime_root_inside_repo_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(launcher.tempfile, "gettempdir", lambda: os.fspath(repo))

    with pytest.raises(launcher.LauncherConfigurationError, match="outside"):
        launcher._prepare_temp_directory(repo)


def test_cache_resolved_parent_must_be_exact_runtime_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    root = tmp_path / "runtime"
    root.mkdir()
    foreign_cache = tmp_path / "foreign" / "pip-cache"
    foreign_cache.mkdir(parents=True)
    monkeypatch.setattr(
        launcher,
        "_prepare_launcher_owned_directory",
        lambda path, *, description: foreign_cache,
    )

    with pytest.raises(launcher.LauncherConfigurationError, match="exact direct child"):
        launcher._prepare_pip_cache_directory(repo, root)


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
        "workspace-write",
        "-c",
        "approval_policy=never",
        "-c",
        "sandbox_workspace_write.network_access=false",
    )
    assert launcher.REVIEWER_PROFILE_ARGS == {
        "deliberate": ("-c", "model_reasoning_effort=medium", "-"),
        "critical": ("-c", "model_reasoning_effort=high", "-"),
    }
    assert launcher.WINDOWS_SANDBOX_ARGS == ("-c", "windows.sandbox=mxc")


@pytest.mark.parametrize("windows", [False, True])
def test_platform_materialization_is_native_windows_only(
    tmp_path: Path, windows: bool
) -> None:
    argv = launcher._compose_generic_argv(
        selector="TSK-0037",
        repo=tmp_path,
        codex_executable=tmp_path / "codex.exe",
        agent_timeout_seconds=1.0,
        verify_timeout_seconds=2.0,
        required_ci_timeout_seconds=3.0,
        windows=windows,
    )
    generic = parse_generic_args(list(argv))

    for child_args in (generic.implementer_args, generic.reviewer_args):
        assert child_args[: len(launcher.IMPLEMENTER_COMMON_ARGS)] == list(
            launcher.IMPLEMENTER_COMMON_ARGS
        )
        if windows:
            assert child_args[-2:] == ["-c", "windows.sandbox=mxc"]
            assert child_args.count("windows.sandbox=mxc") == 1
            assert "windows.sandbox=elevated" not in child_args
        else:
            assert "windows.sandbox=mxc" not in child_args
            assert "windows.sandbox=elevated" not in child_args


def test_generic_argv_uses_equals_form_and_required_assertions(tmp_path: Path) -> None:
    argv = launcher._compose_generic_argv(
        selector="TSK-0037",
        repo=tmp_path,
        codex_executable=tmp_path / "codex.exe",
        agent_timeout_seconds=1.25,
        verify_timeout_seconds=2.5,
        required_ci_timeout_seconds=3.75,
        windows=False,
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
    implementer = launcher.IMPLEMENTER_COMMON_ARGS
    reviewer = launcher.REVIEWER_COMMON_ARGS

    for common in (implementer, reviewer):
        assert "--ask-for-approval" not in common

    assert implementer.count("approval_policy=never") == 1
    assert implementer[implementer.index("approval_policy=never") - 1] == "-c"
    assert "approval_policy=on-request" not in implementer
    assert "approvals_reviewer=auto_review" not in implementer

    assert reviewer.count("approval_policy=never") == 1
    assert reviewer[reviewer.index("approval_policy=never") - 1] == "-c"
    assert "approval_policy=on-request" not in reviewer
    assert "approvals_reviewer=auto_review" not in reviewer

    assert implementer[implementer.index("--sandbox") + 1] == "workspace-write"
    assert reviewer[reviewer.index("--sandbox") + 1] == "workspace-write"
    for common in (implementer, reviewer):
        assert common.count("sandbox_workspace_write.network_access=false") == 1
        assert common[common.index("sandbox_workspace_write.network_access=false") - 1] == "-c"


def test_generic_argv_is_exact_including_all_forwarded_values(tmp_path: Path) -> None:
    repo = (tmp_path / "repo").resolve()
    executable = (tmp_path / "codex.exe").resolve()

    argv = launcher._compose_generic_argv(
        selector="TSK-0037",
        repo=repo,
        codex_executable=executable,
        agent_timeout_seconds=1800.0,
        verify_timeout_seconds=3600.0,
        required_ci_timeout_seconds=600.0,
        windows=False,
    )

    assert argv == _expected_generic_argv(repo, executable)
    assert "--delivery-branch" not in argv


def test_windows_generic_argv_is_exact_including_platform_suffix(
    tmp_path: Path,
) -> None:
    repo = (tmp_path / "repo").resolve()
    executable = (tmp_path / "codex.exe").resolve()

    argv = launcher._compose_generic_argv(
        selector="TSK-0037",
        repo=repo,
        codex_executable=executable,
        agent_timeout_seconds=1800.0,
        verify_timeout_seconds=3600.0,
        required_ci_timeout_seconds=600.0,
        windows=True,
    )

    assert argv == _expected_generic_argv(repo, executable, windows=True)


def test_composed_argv_has_no_dangerous_or_public_escape_tokens(tmp_path: Path) -> None:
    argv = launcher._compose_generic_argv(
        selector="NEXT",
        repo=tmp_path,
        codex_executable=tmp_path / "codex.exe",
        agent_timeout_seconds=1800.0,
        verify_timeout_seconds=1800.0,
        required_ci_timeout_seconds=600.0,
        windows=True,
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
    pip_cache_directory = temp_directory / "pip-cache"
    monkeypatch.setattr(launcher, "_validate_repository", lambda repo, prefix=None: repo.resolve())
    monkeypatch.setattr(launcher, "_validate_loaded_package_provenance", lambda repo: None)
    monkeypatch.setattr(
        launcher, "_resolve_codex", lambda explicit, environ=None: executable
    )
    monkeypatch.setattr(launcher, "_check_codex_identity", lambda executable: None)
    monkeypatch.setattr(launcher, "_prepare_temp_directory", lambda repo: temp_directory)
    monkeypatch.setattr(
        launcher,
        "_prepare_pip_cache_directory",
        lambda repo, runtime_root: pip_cache_directory,
    )

    config = launcher._prepare_configuration(
        _namespace(repo), environ=environment, prefix="ignored"
    )

    assert config.codex_executable == executable
    assert config.pip_cache_directory == pip_cache_directory
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
    original = {
        "TEMP": (True, "old-temp"),
        "TMP": (False, None),
        "TMPDIR": (True, ""),
        "PIP_CACHE_DIR": (True, "old-pip-cache"),
    }
    monkeypatch.setenv("TEMP", "old-temp")
    monkeypatch.delenv("TMP", raising=False)
    monkeypatch.setenv("TMPDIR", "")
    monkeypatch.setenv("PIP_CACHE_DIR", "old-pip-cache")
    observed: dict[str, str | None] = {}

    def generic_main(argv: list[str]) -> int:
        observed.update(
            {
                name: os.environ.get(name)
                for name in ("TEMP", "TMP", "TMPDIR", "PIP_CACHE_DIR")
            }
        )
        return 11

    monkeypatch.setattr(launcher.generic_cli, "main", generic_main)

    assert launcher._delegate(configuration) == 11
    target = os.fspath(configuration.temp_directory)
    assert observed == {
        "TEMP": target,
        "TMP": target,
        "TMPDIR": target,
        "PIP_CACHE_DIR": os.fspath(configuration.pip_cache_directory),
    }
    for name, (was_present, value) in original.items():
        assert (name in os.environ) is was_present
        if was_present:
            assert os.environ[name] == value


def test_delegate_restores_environment_after_generic_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configuration = _configuration(tmp_path)
    monkeypatch.delenv("TEMP", raising=False)
    monkeypatch.setenv("TMP", "old-tmp")
    monkeypatch.setenv("TMPDIR", "")
    monkeypatch.delenv("PIP_CACHE_DIR", raising=False)
    previous_tempfile_tempdir = tempfile.tempdir

    def generic_main(argv: list[str]) -> int:
        assert tempfile.gettempdir() == os.fspath(configuration.temp_directory)
        raise RuntimeError("generic failure")

    monkeypatch.setattr(launcher.generic_cli, "main", generic_main)

    with pytest.raises(RuntimeError, match="generic failure"):
        launcher._delegate(configuration)
    assert "TEMP" not in os.environ
    assert os.environ["TMP"] == "old-tmp"
    assert os.environ["TMPDIR"] == ""
    assert "PIP_CACHE_DIR" not in os.environ
    assert tempfile.tempdir is previous_tempfile_tempdir


def test_delegate_overrides_prewarmed_tempfile_cache_and_restores_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configuration = _configuration(tmp_path)
    previous_location = tmp_path / "prewarmed-temp"
    previous_location.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", os.fspath(previous_location))
    assert tempfile.gettempdir() == os.fspath(previous_location)
    previous_tempfile_tempdir = tempfile.tempdir
    observed: list[str] = []
    monkeypatch.setattr(
        launcher.generic_cli,
        "main",
        lambda argv: observed.append(tempfile.gettempdir()) or 0,
    )

    assert launcher._delegate(configuration) == 0

    assert observed == [os.fspath(configuration.temp_directory)]
    assert tempfile.tempdir is previous_tempfile_tempdir


def test_delegated_child_process_inherits_runtime_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configuration = _configuration(tmp_path)
    observed: dict[str, str] = {}

    def generic_main(argv: list[str]) -> int:
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import json, os; "
                    "print(json.dumps({name: os.environ[name] for name in "
                    "('TEMP', 'TMP', 'TMPDIR', 'PIP_CACHE_DIR')}))"
                ),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            shell=False,
        )
        observed.update(json.loads(completed.stdout))
        return 0

    monkeypatch.setattr(launcher.generic_cli, "main", generic_main)

    assert launcher._delegate(configuration) == 0

    root = os.fspath(configuration.temp_directory)
    assert observed == {
        "TEMP": root,
        "TMP": root,
        "TMPDIR": root,
        "PIP_CACHE_DIR": os.fspath(configuration.pip_cache_directory),
    }


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
