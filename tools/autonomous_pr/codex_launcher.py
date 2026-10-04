"""Deterministic Codex configuration for the AUTONOMOUS_PR generic CLI.

This module is a narrow provider-specific adapter.  It validates the local
operator environment, materializes the fixed Codex configuration, and
delegates in-process to the existing ``tools.autonomous_pr.__main__`` generic
CLI.  It deliberately contains no Git, GitHub, task-selection, or orchestrator
workflow logic.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from . import __main__ as generic_cli


DEFAULT_AGENT_TIMEOUT_SECONDS = 1800.0
DEFAULT_VERIFY_TIMEOUT_SECONDS = 3600.0
DEFAULT_REQUIRED_CI_TIMEOUT_SECONDS = 600.0
CODEX_IDENTITY_TIMEOUT_SECONDS = 10.0

IMPLEMENTER_COMMON_ARGS = (
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
IMPLEMENTER_PROFILE_ARGS = {
    "routine": ("-c", "model_reasoning_effort=low", "-"),
    "deliberate": ("-c", "model_reasoning_effort=medium", "-"),
    "critical": ("-c", "model_reasoning_effort=high", "-"),
}
REVIEWER_COMMON_ARGS = (
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
REVIEWER_PROFILE_ARGS = {
    "deliberate": ("-c", "model_reasoning_effort=medium", "-"),
    "critical": ("-c", "model_reasoning_effort=high", "-"),
}
WINDOWS_SANDBOX_ARGS = ("-c", "windows.sandbox=mxc")

_SELECTOR_PATTERN = re.compile(r"TSK-[0-9]{4}")
_CODEX_IDENTITY_PATTERN = re.compile(r"(?:^|\s)codex-cli\s+(\S+)")
_TEMP_DIRECTORY_NAME = "ai-dnd-autonomous"
_PIP_CACHE_DIRECTORY_NAME = "pip-cache"


class LauncherConfigurationError(ValueError):
    """The operator environment cannot safely materialize the fixed profile."""


@dataclass(frozen=True)
class LauncherConfiguration:
    """Validated inputs and their exact generic-CLI representation."""

    selector: str
    repo: Path
    codex_executable: Path
    temp_directory: Path
    pip_cache_directory: Path
    agent_timeout_seconds: float
    verify_timeout_seconds: float
    required_ci_timeout_seconds: float
    generic_argv: tuple[str, ...]


def _selector(value: str) -> str:
    if value != "NEXT" and _SELECTOR_PATTERN.fullmatch(value) is None:
        raise argparse.ArgumentTypeError(
            "selector must be literal NEXT or canonical TSK-NNNN"
        )
    return value


def _positive_finite_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a finite number greater than 0") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be a finite number greater than 0")
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.autonomous_pr.codex_launcher",
        allow_abbrev=False,
        description=(
            "Prepare the fixed Codex profile for one already-authorized "
            "AUTONOMOUS_PR task. The selector is execution input, not authorization."
        ),
    )
    parser.add_argument("selector", type=_selector)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--codex", type=Path)
    parser.add_argument(
        "--agent-timeout-seconds",
        type=_positive_finite_float,
        default=DEFAULT_AGENT_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--verify-timeout-seconds",
        type=_positive_finite_float,
        default=DEFAULT_VERIFY_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--required-ci-timeout-seconds",
        type=_positive_finite_float,
        default=DEFAULT_REQUIRED_CI_TIMEOUT_SECONDS,
    )
    return parser


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    return _build_parser().parse_args(argv)


def _normalized_path(path: Path, *, strict: bool) -> Path:
    try:
        return path.expanduser().resolve(strict=strict)
    except OSError as exc:
        raise LauncherConfigurationError(f"cannot resolve path {path}: {exc}") from exc


def _same_path(first: Path, second: Path) -> bool:
    return os.path.normcase(os.fspath(first)) == os.path.normcase(os.fspath(second))


def _validate_repository(repo_argument: Path, *, prefix: str | None = None) -> Path:
    repo = _normalized_path(repo_argument, strict=True)
    if not repo.is_dir():
        raise LauncherConfigurationError(f"repository path is not a directory: {repo}")

    expected_environment = repo / ".venv"
    if not expected_environment.is_dir():
        raise LauncherConfigurationError(
            f"repository virtual environment is missing: {expected_environment}"
        )
    actual_environment = _normalized_path(Path(prefix or sys.prefix), strict=True)
    normalized_expected = _normalized_path(expected_environment, strict=True)
    if not _same_path(actual_environment, normalized_expected):
        raise LauncherConfigurationError(
            "launcher must run under this repository's .venv "
            f"(expected {normalized_expected}, got {actual_environment})"
        )

    local_codex = repo / ".codex"
    if os.path.lexists(local_codex):
        raise LauncherConfigurationError(
            f"repository-local Codex configuration is not allowed: {local_codex}"
        )
    return repo


def _resolved_loaded_path(value: object, *, description: str) -> Path:
    if value is None:
        raise LauncherConfigurationError(f"loaded {description} has no __file__")
    try:
        path = Path(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise LauncherConfigurationError(
            f"loaded {description} has an invalid path: {value!r}"
        ) from exc
    return _normalized_path(path, strict=True)


def _validate_loaded_package_provenance(repo: Path) -> None:
    expected_package_root = _normalized_path(
        repo / "tools" / "autonomous_pr", strict=True
    )
    package = sys.modules.get(__package__)
    package_search_path = getattr(package, "__path__", None)
    if package_search_path is None:
        raise LauncherConfigurationError(
            "loaded tools.autonomous_pr package has no package search path"
        )
    try:
        package_roots = tuple(package_search_path)
    except TypeError as exc:
        raise LauncherConfigurationError(
            "loaded tools.autonomous_pr package search path is invalid"
        ) from exc
    if len(package_roots) != 1:
        raise LauncherConfigurationError(
            "loaded tools.autonomous_pr package must have exactly one search root "
            f"(got {len(package_roots)})"
        )

    actual_package_root = _resolved_loaded_path(
        package_roots[0], description="tools.autonomous_pr package root"
    )
    expected_launcher = _normalized_path(
        expected_package_root / "codex_launcher.py", strict=True
    )
    expected_generic_cli = _normalized_path(
        expected_package_root / "__main__.py", strict=True
    )
    actual_launcher = _resolved_loaded_path(
        globals().get("__file__"), description="codex_launcher module"
    )
    actual_generic_cli = _resolved_loaded_path(
        getattr(generic_cli, "__file__", None), description="generic_cli module"
    )

    comparisons = (
        ("tools.autonomous_pr package root", actual_package_root, expected_package_root),
        ("codex_launcher module", actual_launcher, expected_launcher),
        ("generic_cli module", actual_generic_cli, expected_generic_cli),
    )
    for description, actual, expected in comparisons:
        if not _same_path(actual, expected):
            raise LauncherConfigurationError(
                f"loaded {description} is not from the selected repository "
                f"(expected {expected}, got {actual})"
            )


def _concrete_executable(candidate: str, *, source: str) -> Path:
    resolved_by_path = shutil.which(candidate)
    if resolved_by_path is None:
        raise LauncherConfigurationError(
            f"Codex executable selected by {source} is not launchable: {candidate}"
        )
    executable = _normalized_path(Path(resolved_by_path), strict=True)
    if not executable.is_file():
        raise LauncherConfigurationError(
            f"Codex executable selected by {source} is not a file: {executable}"
        )
    return executable


def _windows_fallback_candidates(environ: Mapping[str, str]) -> tuple[Path, ...]:
    local_app_data = environ.get("LOCALAPPDATA", "")
    if not local_app_data:
        return ()
    root = Path(local_app_data) / "OpenAI" / "Codex" / "bin"
    return tuple(path for path in root.glob("*/codex.exe") if path.is_file())


def _is_windows() -> bool:
    return os.name == "nt"


def _resolve_codex(
    explicit: Path | None, *, environ: Mapping[str, str] | None = None
) -> Path:
    environment = os.environ if environ is None else environ
    if explicit is not None:
        return _concrete_executable(os.fspath(explicit), source="--codex")

    env_candidate = environment.get("AUTONOMOUS_PR_CODEX_EXE", "")
    if env_candidate:
        return _concrete_executable(
            env_candidate, source="AUTONOMOUS_PR_CODEX_EXE"
        )

    path_candidate = shutil.which("codex")
    if path_candidate is not None:
        return _concrete_executable(path_candidate, source="PATH")

    if not _is_windows():
        raise LauncherConfigurationError("Codex executable was not found")

    fallback_candidates = _windows_fallback_candidates(environment)
    if not fallback_candidates:
        raise LauncherConfigurationError(
            "Codex executable was not found in the Windows application location"
        )
    if len(fallback_candidates) > 1:
        raise LauncherConfigurationError(
            "multiple Windows Codex executables found; select one with --codex"
        )
    return _concrete_executable(
        os.fspath(fallback_candidates[0]), source="Windows application fallback"
    )


def _check_codex_identity(executable: Path) -> None:
    try:
        completed = subprocess.run(
            [os.fspath(executable), "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=CODEX_IDENTITY_TIMEOUT_SECONDS,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise LauncherConfigurationError("Codex --version timed out") from exc
    except OSError as exc:
        raise LauncherConfigurationError(f"Codex --version failed: {exc}") from exc

    if completed.returncode != 0:
        raise LauncherConfigurationError(
            f"Codex --version exited with status {completed.returncode}"
        )
    combined_output = f"{completed.stdout}\n{completed.stderr}"
    if _CODEX_IDENTITY_PATTERN.search(combined_output) is None:
        raise LauncherConfigurationError(
            "Codex --version output does not contain 'codex-cli <version>'"
        )


def _is_junction(path: Path) -> bool:
    predicate = getattr(path, "is_junction", None)
    return bool(predicate()) if predicate is not None else False


def _validate_launcher_owned_directory_entry(path: Path, *, description: str) -> None:
    try:
        if not os.path.lexists(path):
            raise LauncherConfigurationError(
                f"{description} was not created: {path}"
            )
        if path.is_symlink():
            raise LauncherConfigurationError(
                f"{description} must not be a symlink: {path}"
            )
        if _is_junction(path):
            raise LauncherConfigurationError(
                f"{description} must not be a junction: {path}"
            )
        if not path.is_dir():
            raise LauncherConfigurationError(
                f"{description} is not a directory: {path}"
            )
    except OSError as exc:
        raise LauncherConfigurationError(
            f"cannot inspect {description} {path}: {exc}"
        ) from exc


def _prepare_launcher_owned_directory(path: Path, *, description: str) -> Path:
    try:
        exists = os.path.lexists(path)
    except OSError as exc:
        raise LauncherConfigurationError(
            f"cannot inspect {description} {path}: {exc}"
        ) from exc
    if exists:
        _validate_launcher_owned_directory_entry(path, description=description)
    else:
        try:
            path.mkdir()
        except OSError as exc:
            raise LauncherConfigurationError(
                f"cannot create {description} {path}: {exc}"
            ) from exc
        _validate_launcher_owned_directory_entry(path, description=description)
    return _normalized_path(path, strict=True)


def _require_outside_repository(path: Path, repo: Path, *, description: str) -> None:
    if _same_path(path, repo) or path.is_relative_to(repo):
        raise LauncherConfigurationError(
            f"{description} must be outside repository: {path}"
        )


def _probe_launcher_owned_directory(path: Path, *, description: str) -> None:
    probe_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path, prefix="write-probe-", delete=False
        ) as probe:
            probe_path = Path(probe.name)
            probe.write(b"ok")
            probe.flush()
        probe_path.unlink()
    except OSError as exc:
        try:
            if probe_path is not None and os.path.lexists(probe_path):
                probe_path.unlink()
        except OSError:
            pass
        raise LauncherConfigurationError(
            f"{description} failed create/write/remove probe at {path}: {exc}"
        ) from exc


def _prepare_temp_directory(repo: Path) -> Path:
    lexical_path = Path(tempfile.gettempdir()) / _TEMP_DIRECTORY_NAME
    temp_directory = _prepare_launcher_owned_directory(
        lexical_path, description="dedicated runtime directory"
    )
    _require_outside_repository(
        temp_directory, repo, description="dedicated runtime directory"
    )
    _probe_launcher_owned_directory(
        temp_directory, description="dedicated runtime directory"
    )
    return temp_directory


def _prepare_pip_cache_directory(repo: Path, temp_directory: Path) -> Path:
    lexical_path = temp_directory / _PIP_CACHE_DIRECTORY_NAME
    pip_cache_directory = _prepare_launcher_owned_directory(
        lexical_path, description="dedicated pip cache directory"
    )
    _require_outside_repository(
        pip_cache_directory, repo, description="dedicated pip cache directory"
    )
    if pip_cache_directory.parent != temp_directory:
        raise LauncherConfigurationError(
            "dedicated pip cache directory must resolve as the exact direct child "
            f"of the runtime directory (runtime {temp_directory}, "
            f"cache {pip_cache_directory})"
        )
    _probe_launcher_owned_directory(
        pip_cache_directory, description="dedicated pip cache directory"
    )
    return pip_cache_directory


def _opaque_arguments(option: str, values: Sequence[str]) -> list[str]:
    return [f"{option}={value}" for value in values]


def _platform_child_args(
    common_args: Sequence[str], *, windows: bool
) -> tuple[str, ...]:
    if windows:
        return (*common_args, *WINDOWS_SANDBOX_ARGS)
    return tuple(common_args)


def _compose_generic_argv(
    *,
    selector: str,
    repo: Path,
    codex_executable: Path,
    agent_timeout_seconds: float,
    verify_timeout_seconds: float,
    required_ci_timeout_seconds: float,
    windows: bool | None = None,
) -> tuple[str, ...]:
    executable = os.fspath(codex_executable)
    native_windows = _is_windows() if windows is None else windows
    implementer_common_args = _platform_child_args(
        IMPLEMENTER_COMMON_ARGS, windows=native_windows
    )
    reviewer_common_args = _platform_child_args(
        REVIEWER_COMMON_ARGS, windows=native_windows
    )
    argv = [selector, "--repo", os.fspath(repo), "--implementer", executable]
    argv.extend(_opaque_arguments("--implementer-arg", implementer_common_args))
    for profile in ("routine", "deliberate", "critical"):
        argv.extend(
            _opaque_arguments(
                f"--implementer-{profile}-arg", IMPLEMENTER_PROFILE_ARGS[profile]
            )
        )
    argv.extend(("--reviewer", executable))
    argv.extend(_opaque_arguments("--reviewer-arg", reviewer_common_args))
    for profile in ("deliberate", "critical"):
        argv.extend(
            _opaque_arguments(
                f"--reviewer-{profile}-arg", REVIEWER_PROFILE_ARGS[profile]
            )
        )
    argv.extend(
        (
            "--reviewer-fresh-context-capable",
            "--implementer-no-git-github-write-capability",
            "--reviewer-no-git-github-write-capability",
            "--agent-timeout-seconds",
            str(agent_timeout_seconds),
            "--verify-timeout-seconds",
            str(verify_timeout_seconds),
            "--required-ci-timeout-seconds",
            str(required_ci_timeout_seconds),
        )
    )
    return tuple(argv)


def _prepare_configuration(
    args: argparse.Namespace,
    *,
    environ: Mapping[str, str] | None = None,
    prefix: str | None = None,
) -> LauncherConfiguration:
    repo = _validate_repository(args.repo, prefix=prefix)
    _validate_loaded_package_provenance(repo)
    codex_executable = _resolve_codex(args.codex, environ=environ)
    _check_codex_identity(codex_executable)
    temp_directory = _prepare_temp_directory(repo)
    pip_cache_directory = _prepare_pip_cache_directory(repo, temp_directory)
    generic_argv = _compose_generic_argv(
        selector=args.selector,
        repo=repo,
        codex_executable=codex_executable,
        agent_timeout_seconds=args.agent_timeout_seconds,
        verify_timeout_seconds=args.verify_timeout_seconds,
        required_ci_timeout_seconds=args.required_ci_timeout_seconds,
    )
    return LauncherConfiguration(
        selector=args.selector,
        repo=repo,
        codex_executable=codex_executable,
        temp_directory=temp_directory,
        pip_cache_directory=pip_cache_directory,
        agent_timeout_seconds=args.agent_timeout_seconds,
        verify_timeout_seconds=args.verify_timeout_seconds,
        required_ci_timeout_seconds=args.required_ci_timeout_seconds,
        generic_argv=generic_argv,
    )


def _delegate(configuration: LauncherConfiguration) -> int:
    temp_value = os.fspath(configuration.temp_directory)
    pip_cache_value = os.fspath(configuration.pip_cache_directory)
    scoped_values = {
        "TEMP": temp_value,
        "TMP": temp_value,
        "TMPDIR": temp_value,
        "PIP_CACHE_DIR": pip_cache_value,
    }
    previous_values = {
        name: (name in os.environ, os.environ[name] if name in os.environ else None)
        for name in scoped_values
    }
    previous_tempfile_tempdir = tempfile.tempdir
    try:
        for name, value in scoped_values.items():
            os.environ[name] = value
        tempfile.tempdir = temp_value
        return generic_cli.main(list(configuration.generic_argv))
    finally:
        tempfile.tempdir = previous_tempfile_tempdir
        for name, (was_present, previous_value) in previous_values.items():
            if was_present:
                assert previous_value is not None
                os.environ[name] = previous_value
            else:
                os.environ.pop(name, None)


def main(argv: Sequence[str] | None = None) -> int:
    parsed = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        configuration = _prepare_configuration(parsed)
    except LauncherConfigurationError as exc:
        print(f"codex launcher configuration error: {exc}", file=sys.stderr)
        return 2
    return _delegate(configuration)


if __name__ == "__main__":
    raise SystemExit(main())
