"""Deterministic Codex configuration for the AUTONOMOUS_PR generic CLI.

This module is a narrow provider-specific adapter.  It validates the local
operator environment and composes the reviewed Codex argv consumed by
``tools.autonomous_pr.__main__``.  Repository workflow delegation is added by
the next TSK-0037 checkpoint; this module deliberately contains no Git,
GitHub, task-selection, or orchestrator logic.
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
DEFAULT_VERIFY_TIMEOUT_SECONDS = 1800.0
DEFAULT_REQUIRED_CI_TIMEOUT_SECONDS = 600.0
CODEX_IDENTITY_TIMEOUT_SECONDS = 10.0

IMPLEMENTER_COMMON_ARGS = (
    "exec",
    "--ephemeral",
    "--ignore-user-config",
    "--ignore-rules",
    "--ask-for-approval",
    "never",
    "--sandbox",
    "workspace-write",
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
    "--ask-for-approval",
    "never",
    "--sandbox",
    "read-only",
)
REVIEWER_PROFILE_ARGS = {
    "deliberate": ("-c", "model_reasoning_effort=medium", "-"),
    "critical": ("-c", "model_reasoning_effort=high", "-"),
}

_SELECTOR_PATTERN = re.compile(r"TSK-[0-9]{4}")
_CODEX_IDENTITY_PATTERN = re.compile(r"(?:^|\s)codex-cli\s+(\S+)")
_TEMP_DIRECTORY_NAME = "ai-dnd-autonomous"


class LauncherConfigurationError(ValueError):
    """The operator environment cannot safely materialize the fixed profile."""


@dataclass(frozen=True)
class LauncherConfiguration:
    """Validated inputs and their exact generic-CLI representation."""

    selector: str
    repo: Path
    codex_executable: Path
    temp_directory: Path
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


def _prepare_temp_directory(repo: Path) -> Path:
    temp_directory = _normalized_path(
        Path(tempfile.gettempdir()) / _TEMP_DIRECTORY_NAME, strict=False
    )
    if temp_directory == repo or temp_directory.is_relative_to(repo):
        raise LauncherConfigurationError(
            f"dedicated temp directory must be outside repository: {temp_directory}"
        )
    try:
        temp_directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=temp_directory, prefix="write-probe-", delete=False
        ) as probe:
            probe_path = Path(probe.name)
            probe.write(b"ok")
            probe.flush()
        probe_path.unlink()
    except OSError as exc:
        try:
            if "probe_path" in locals() and probe_path.exists():
                probe_path.unlink()
        except OSError:
            pass
        raise LauncherConfigurationError(
            f"dedicated temp directory is not writable: {temp_directory}: {exc}"
        ) from exc
    return temp_directory


def _opaque_arguments(option: str, values: Sequence[str]) -> list[str]:
    return [f"{option}={value}" for value in values]


def _compose_generic_argv(
    *,
    selector: str,
    repo: Path,
    codex_executable: Path,
    agent_timeout_seconds: float,
    verify_timeout_seconds: float,
    required_ci_timeout_seconds: float,
) -> tuple[str, ...]:
    executable = os.fspath(codex_executable)
    argv = [selector, "--repo", os.fspath(repo), "--implementer", executable]
    argv.extend(_opaque_arguments("--implementer-arg", IMPLEMENTER_COMMON_ARGS))
    for profile in ("routine", "deliberate", "critical"):
        argv.extend(
            _opaque_arguments(
                f"--implementer-{profile}-arg", IMPLEMENTER_PROFILE_ARGS[profile]
            )
        )
    argv.extend(("--reviewer", executable))
    argv.extend(_opaque_arguments("--reviewer-arg", REVIEWER_COMMON_ARGS))
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
    codex_executable = _resolve_codex(args.codex, environ=environ)
    _check_codex_identity(codex_executable)
    temp_directory = _prepare_temp_directory(repo)
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
        agent_timeout_seconds=args.agent_timeout_seconds,
        verify_timeout_seconds=args.verify_timeout_seconds,
        required_ci_timeout_seconds=args.required_ci_timeout_seconds,
        generic_argv=generic_argv,
    )


def _delegate(configuration: LauncherConfiguration) -> int:
    temp_value = os.fspath(configuration.temp_directory)
    variable_names = ("TEMP", "TMP", "TMPDIR")
    previous_values = {
        name: (name in os.environ, os.environ.get(name)) for name in variable_names
    }
    try:
        for name in variable_names:
            os.environ[name] = temp_value
        return generic_cli.main(list(configuration.generic_argv))
    finally:
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
