"""Minimal external-process boundary for the implementer/reviewer roles.

Scope, matching ``docs/AUTONOMOUS_PR_HARNESS.md`` §§5, 7, 13, 14:

- one generic subprocess invocation primitive (:func:`run_agent`), used by
  both roles — not a ``BaseProvider``/adapter hierarchy/registry;
- a role-checked implementer wrapper (:func:`run_implementer`) and a
  role-checked, verdict-parsing reviewer wrapper (:func:`run_reviewer`);
- the strict three-token reviewer verdict contract (:func:`parse_reviewer_verdict`).

Role isolation. ``AgentInvocationSpec`` carries an explicit :class:`.model.AgentRole`,
and :func:`run_implementer`/:func:`run_reviewer` each refuse a spec of the
wrong role. Nothing in this module ever builds a reviewer's
``AgentInvocationSpec`` from an implementer's spec or result — there is no
"resume the implementer's session for review" helper, and there must never
be one: a separate OS process alone does not prove a fresh provider
context, and reviewer selection/configuration stays the orchestrator's
responsibility, never the implementer's own output. If a configured
external tool cannot guarantee a fresh reviewer context, the caller must
fail closed rather than invoke it.

This module performs no Git/GitHub side effects: it only invokes configured
external executables and parses their output.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from .model import AgentRole, ReviewResult, ReviewVerdict

_VERDICT_TOKENS: frozenset[str] = frozenset(verdict.value for verdict in ReviewVerdict)


@dataclass(frozen=True)
class AgentInvocationSpec:
    """How to start one external agent process for one role.

    Provider-specific detail (executable, flags, sandbox/tool-access flags,
    how context is injected) is confined to this invocation boundary per
    §13; this dataclass does not interpret any of it.

    Deliberately carries no session/resume-identifier field, and
    :func:`run_agent` never generates one — every invocation is a plain,
    independent ``subprocess.run`` call with the fixed ``args`` given here.
    That structurally guarantees two things: the orchestrator can never
    forward an implementer session/resume reference to the reviewer (there
    is nowhere to put one), and every call is its own separate OS process.

    It does **not** by itself guarantee that the external executable named
    by ``executable`` is internally stateless/one-shot — an opaque
    configured CLI could, for example, default to resuming its own last
    conversation regardless of being launched as a fresh process each time.
    Whether the configured reviewer integration is genuinely one-shot/
    fresh-context capable is a property of that external command, verified
    by whoever configures it (per ``docs/AUTONOMOUS_PR_HARNESS.md`` §13's
    "the run must fail closed rather than proceed with a weakened isolation
    guarantee" if it is not) — this module has no way to inspect an
    arbitrary executable's internal behavior and does not claim to.

    ``fresh_context_capable``, ``can_edit_working_files``, and
    ``has_git_or_github_write_access`` are explicit **operator/
    configuration assertions** about how the external command named by
    ``executable`` is itself sandboxed or configured — never user
    authorization for ``AUTONOMOUS_PR`` (``AGENTS.md`` "Valid invocation"),
    and never inferred, derived, or verified by this module. Generic Python
    cannot inspect an opaque external process and prove any of these
    properties true; declaring them here is a narrow, provider-neutral
    precondition ``.orchestrator.OrchestratorConfig`` checks before any
    agent invocation (fail closed if a required one was not positively
    declared as required for that role), not a runtime capability
    negotiation protocol, a provider registry, or an SDK. Whoever configures
    a spec is responsible for these being true of the actual integration —
    e.g. that a reviewer executable really does start fresh each call, and
    that neither role's configured command/sandbox is actually able to
    write to Git/GitHub directly. The post-invocation fingerprint/branch-
    head guards elsewhere in this package remain defense-in-depth
    regardless of what is declared here.

    ``has_git_or_github_write_access`` is deliberately three-valued
    (``bool | None``, default ``None``) rather than a plain ``bool``
    defaulting to ``False``: a plain boolean defaulting to ``False`` would
    make "nobody positively declared this command sandboxed away from
    ``git push``/``gh``/GitHub credentials" indistinguishable from "an
    operator explicitly asserted it is" — exactly the silent, unearned
    safety claim this precondition exists to prevent, especially since a
    real external command typically inherits the host environment/PATH and
    this module has no way to confirm it cannot reach Git/GitHub directly.
    ``None`` means "not positively declared" and is refused exactly like
    ``True``; only an explicit ``False`` — an operator's positive assertion
    that the configured command/sandbox has no direct Git/GitHub write
    capability — satisfies the precondition.
    """

    role: AgentRole
    executable: str
    args: tuple[str, ...] = ()
    cwd: Path | None = None
    timeout_seconds: float = 600.0
    env: Mapping[str, str] | None = field(default=None)
    fresh_context_capable: bool = False
    can_edit_working_files: bool = False
    has_git_or_github_write_access: bool | None = None


@dataclass(frozen=True)
class AgentInvocationResult:
    """The raw outcome of one :func:`run_agent` call.

    Expected failure modes (timeout, non-zero exit, failure to launch) are
    represented here rather than raised, so callers can apply the strict
    fail-closed handling §7/§17 require without a fragile exception-based
    control flow.
    """

    stdout: str
    stderr: str
    returncode: int | None
    timed_out: bool


class AgentRoleError(Exception):
    """An ``AgentInvocationSpec`` was used for a role it does not declare."""


def _require_role(spec: AgentInvocationSpec, expected: AgentRole) -> None:
    if spec.role is not expected:
        raise AgentRoleError(
            f"expected an AgentInvocationSpec with role {expected!r}, got "
            f"{spec.role!r}"
        )


def run_agent(spec: AgentInvocationSpec, input_text: str) -> AgentInvocationResult:
    """Invoke one external agent process and capture its result.

    Never raises for an expected failure mode (timeout, non-zero exit,
    failure to launch the executable) — those become part of the returned
    :class:`AgentInvocationResult` instead, so the strict, fail-closed
    verdict handling in :func:`run_reviewer` never has to guess whether a
    caught exception means "no verdict" or something else.

    stdin/stdout/stderr are all encoded/decoded as UTF-8 explicitly —
    ``text=True`` alone decodes using the platform's default locale
    encoding, which on Windows is a codepage other than UTF-8 and would
    otherwise corrupt any non-ASCII content passed in ``input_text`` (task
    detail, plan text) or produced by the external process.
    """

    env = dict(spec.env) if spec.env is not None else None
    try:
        completed = subprocess.run(
            [spec.executable, *spec.args],
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=spec.cwd,
            env=env,
            timeout=spec.timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return AgentInvocationResult(
            stdout=exc.stdout if isinstance(exc.stdout, str) else "",
            stderr=exc.stderr if isinstance(exc.stderr, str) else "",
            returncode=None,
            timed_out=True,
        )
    except OSError as exc:
        return AgentInvocationResult(
            stdout="",
            stderr=str(exc),
            returncode=None,
            timed_out=False,
        )
    return AgentInvocationResult(
        stdout=completed.stdout,
        stderr=completed.stderr,
        returncode=completed.returncode,
        timed_out=False,
    )


def run_implementer(
    spec: AgentInvocationSpec, prompt_text: str
) -> AgentInvocationResult:
    """Invoke the implementer role. Raw result only — no verdict semantics."""

    _require_role(spec, AgentRole.IMPLEMENTER)
    return run_agent(spec, prompt_text)


def parse_reviewer_verdict(output: str) -> ReviewVerdict:
    """Parse the strict three-token verdict contract from reviewer output.

    A verdict token counts only when it is the entire, whitespace-stripped
    content of one line. If zero or more than one *distinct* token is
    found this way — missing, malformed, ambiguous, or an unrecognized
    token — the result is ``ReviewVerdict.BLOCKED``: never a fourth kind of
    outcome, and never silently upgraded to ``APPROVED`` (§7).
    """

    matches = {
        line.strip() for line in output.splitlines() if line.strip() in _VERDICT_TOKENS
    }
    if len(matches) == 1:
        return ReviewVerdict(next(iter(matches)))
    return ReviewVerdict.BLOCKED


def _extract_findings(output: str, verdict: ReviewVerdict) -> str:
    remaining = [line for line in output.splitlines() if line.strip() != verdict.value]
    return "\n".join(remaining).strip()


def run_reviewer(spec: AgentInvocationSpec, review_patch_text: str) -> ReviewResult:
    """Invoke the designated reviewer and resolve its verdict.

    Any process-level failure — timeout, failure to launch, or a non-zero
    exit status — is always terminal ``BLOCKED``, exactly like a missing or
    malformed verdict (§7): it is never routed into the bounded repair
    loop, and reviewer stdout is not trusted for a verdict once the process
    itself did not succeed cleanly.
    """

    _require_role(spec, AgentRole.REVIEWER)
    result = run_agent(spec, review_patch_text)
    combined_output = result.stdout + result.stderr

    if result.timed_out:
        return ReviewResult(
            verdict=ReviewVerdict.BLOCKED,
            findings="reviewer process timed out",
            raw_output=combined_output,
        )
    if result.returncode is None:
        return ReviewResult(
            verdict=ReviewVerdict.BLOCKED,
            findings=f"reviewer process failed to execute: {result.stderr}".strip(),
            raw_output=combined_output,
        )
    if result.returncode != 0:
        return ReviewResult(
            verdict=ReviewVerdict.BLOCKED,
            findings=f"reviewer process exited with status {result.returncode}",
            raw_output=combined_output,
        )

    verdict = parse_reviewer_verdict(result.stdout)
    findings = _extract_findings(result.stdout, verdict)
    return ReviewResult(verdict=verdict, findings=findings, raw_output=result.stdout)
