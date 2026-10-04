import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _section(text: str, heading: str, next_heading_level: int) -> str:
    marker = "#" * next_heading_level
    match = re.search(
        rf"(?ms)^{re.escape(heading)}\s*\n(?P<body>.*?)(?=^{marker}\s|\Z)",
        text,
    )
    assert match is not None
    return " ".join(match.group("body").split())


def test_agent_dispatch_requires_approval_before_launcher_execution() -> None:
    dispatch = _section(
        _read("AGENTS.md"),
        "#### Codex operator dispatch",
        4,
    )

    assert "valid `AUTONOMOUS_PR` invocation is the repository-workflow authorization" in dispatch
    assert "sandbox approval is only product execution permission" in dispatch
    assert "Approval alone never activates `AUTONOMOUS_PR`" in dispatch
    assert "request sandbox escalation/approval for the launcher command before starting it" in dispatch
    assert "Do not first run the launcher inside a known insufficient sandbox" in dispatch
    assert "stop fail-closed" in dispatch
    assert "must not independently" in dispatch
    assert "run `git fetch`" in dispatch
    assert "run `gh` pull-request operations" in dispatch


def test_operator_guide_preserves_three_boundaries_and_fails_closed() -> None:
    guide = _section(
        _read("docs/AUTONOMOUS_PR_OPERATOR.md"),
        "## Approval-aware outer dispatch",
        2,
    )

    assert "tools.autonomous_pr.codex_launcher" in guide
    assert "deterministic AUTONOMOUS_PR harness owns Git/GitHub side effects" in guide
    assert "implementer child: fixed restricted profile" in guide
    assert "reviewer child: fixed restricted disposable-snapshot profile" in guide
    assert "Approval alone never activates `AUTONOMOUS_PR`" in guide
    assert "before launcher execution" in guide
    assert "`workspace-write` with an approval policy capable of surfacing" in guide
    assert "`approval_policy=never` cannot support this chat-native workflow" in guide
    assert "neither reviewer is guaranteed to approve" in guide
    assert "repository neither requires nor enables" in guide
    assert "do not edit `.codex`" in guide
    assert "global or user `config.toml`" in guide
    assert "dispatch stops fail-closed" in guide
    assert "There is no direct Git/GitHub fallback" in guide
    assert "does not weaken their fixed security profiles" in guide


def test_operational_v2_keeps_fresh_fetch_and_parent_sandbox_boundary() -> None:
    lifecycle = _section(
        _read("docs/AUTONOMOUS_PR_HARNESS.md"),
        "## 30. Spec-driven lifecycle and preflight (operational v2)",
        2,
    )

    assert "outer operator execution context already capable" in lifecycle
    assert "does not escape or reconfigure its parent sandbox" in lifecycle
    assert "does not turn product execution permission into additional repository authority" in lifecycle
    assert "mandatory fresh `git fetch origin` remains required" in lifecycle
    assert "no cached-ref" in lifecycle
    assert "GitHub-API" in lifecycle
    assert "direct-caller Git/GitHub fallback" in lifecycle


def test_operational_v2_requires_exact_initial_runtime_base_before_selection() -> None:
    lifecycle = _section(
        _read("docs/AUTONOMOUS_PR_HARNESS.md"),
        "## 30. Spec-driven lifecycle and preflight (operational v2)",
        2,
    )

    assert "requires the worktree/index to be clean" in lifecycle
    assert "literal SHA equality" in lifecycle
    assert "before catalog/selector resolution" in lifecycle
    assert "not branch-name-based" in lifecycle
    assert "behind or ahead" in lifecycle
    assert "does not pull, reset, checkout, switch, merge, rebase" in lifecycle
    assert "start a new explicit invocation" in lifecycle
    assert "not reclassified as an initial-runtime mismatch" in lifecycle


def test_outer_approval_does_not_weaken_child_security_boundary() -> None:
    operator = _read("docs/AUTONOMOUS_PR_OPERATOR.md")
    child_profiles = _section(operator, "## Fixed child profiles", 2)

    assert child_profiles.count("approval_policy=never") >= 3
    assert child_profiles.count("sandbox_workspace_write.network_access=false") >= 3
    assert "no-Git/GitHub-write" in child_profiles
    assert "disposable filesystem snapshot" in child_profiles
    assert "it has no remote" in child_profiles


def test_operator_guide_documents_deterministic_verification_environment() -> None:
    operator = _read("docs/AUTONOMOUS_PR_OPERATOR.md")
    normalized_operator = " ".join(operator.split())
    environment = _section(
        operator, "## Temporary files, credentials, and host permissions", 2
    )

    assert "`1800.0`, `3600.0`, and `600.0`" in normalized_operator
    assert "not a repair budget" in normalized_operator
    assert "passive remote-observation budget" in normalized_operator
    assert "`<system-temp>/ai-dnd-autonomous`" in environment
    assert "fixed direct child `pip-cache`" in environment
    assert "broken symlink" in environment
    assert "supported Windows junction" in environment
    assert "resolved cache parent" in environment
    assert "create/write/flush/close/remove probe" in environment
    assert "`PIP_CACHE_DIR`" in environment
    assert "`tempfile.tempdir`" in environment
    assert "absent and empty" in environment
    assert "`CODEX_HOME`" in environment
    assert "network policy unchanged" in environment


def test_operator_guide_documents_two_layer_runtime_freshness_recovery() -> None:
    runtime = _section(
        _read("docs/AUTONOMOUS_PR_OPERATOR.md"),
        "## Runtime freshness and checkout recovery",
        2,
    )

    assert "two layers" in runtime
    assert "loaded-package provenance" in runtime
    assert "never switches to another imported checkout" in runtime
    assert "exact equality between local `HEAD`" in runtime
    assert "branch name is irrelevant" in runtime
    assert "behind or ahead" in runtime
    assert "does not retry or resume" in runtime
    assert "new explicit `AUTONOMOUS_PR` invocation" in runtime
