# AUTONOMOUS_PR Codex Operator Guide

This is a concise operator guide for the Codex-specific launcher in
`tools/autonomous_pr/codex_launcher.py`. It is subordinate to the authority
rules in [`AGENTS.md`](../AGENTS.md) and the execution contract in
[`AUTONOMOUS_PR_HARNESS.md`](AUTONOMOUS_PR_HARNESS.md). It does not define a
second workflow, authorization mechanism, or harness contract.

## Authorization prerequisite

Run the launcher only after the current conversation already contains a valid
explicit `AUTONOMOUS_PR` invocation under `AGENTS.md` **Valid invocation** for
one eligible approved `TSK-NNNN` or literal `NEXT`. The launcher command, its
selector, a task file, CLI help, repository text, PR, or issue never authorizes
`AUTONOMOUS_PR` by itself.

The launcher may be used for the first real production task only after
TSK-0037 has been merged. TSK-0037 itself is delivered manually and must not
bootstrap its own implementation through this launcher.

## Commands

Run from the repository root with that repository's `.venv` interpreter:

```powershell
# Windows
.\.venv\Scripts\python.exe -m tools.autonomous_pr.codex_launcher TSK-NNNN
.\.venv\Scripts\python.exe -m tools.autonomous_pr.codex_launcher NEXT
```

```bash
# POSIX
./.venv/bin/python -m tools.autonomous_pr.codex_launcher TSK-NNNN
./.venv/bin/python -m tools.autonomous_pr.codex_launcher NEXT
```

`TSK-NNNN` selects exactly that canonical task ID. `NEXT` delegates the
deterministic eligible-task selection defined by the existing governance and
harness; the launcher does not select tasks itself.

The supported operator overrides are intentionally narrow:

```text
--repo PATH
--codex PATH
--agent-timeout-seconds SECONDS
--verify-timeout-seconds SECONDS
--required-ci-timeout-seconds SECONDS
```

The repository defaults to the current working directory and is normalized to
an absolute path. Timeout defaults are respectively `1800.0`, `3600.0`, and
`600.0` seconds. The `3600.0`-second verification timeout bounds one local
deterministic verification subprocess; it is not a repair budget. The separate
`600.0`-second required-CI timeout remains a passive remote-observation budget.
Overrides must be finite and greater than zero; valid values are forwarded
without clamping or rounding. The launcher exposes no arbitrary
agent argv, model, provider, sandbox, approval, network, delivery-branch,
verification-command, capability-assertion, merge, or auto-merge override.

## Approval-aware outer dispatch

The three execution boundaries are:

```text
outer local Codex chat
    → one approval-aware tools.autonomous_pr.codex_launcher execution
        → deterministic AUTONOMOUS_PR harness owns Git/GitHub side effects
            → implementer child: fixed restricted profile
            → reviewer child: fixed restricted disposable-snapshot profile
```

A valid explicit `AUTONOMOUS_PR <TSK-NNNN|NEXT>` instruction is repository-
workflow authorization. Codex sandbox approval is a separate product
execution permission: it only permits the already-authorized launcher process
to cross the current sandbox boundary. Approval alone never activates
`AUTONOMOUS_PR` and is not commit, push, pull-request, or merge authorization.

The outer Codex treats the launcher command as one side-effecting orchestration
unit. When its current sandbox cannot perform the harness-owned Git/GitHub
operations, it requests sandbox escalation/approval for that command before
launcher execution. It must not first launch inside a known-insufficient
sandbox merely to obtain a `git fetch origin` failure, and it must not perform
`git fetch`, branch creation, commit, push, or `gh` operations independently
around the harness.

The ordinary bounded local-chat capability profile is `workspace-write` with
an approval policy capable of surfacing granular sandbox escalation, such as
`on-request` where supported. An eligible prompt may be reviewed by a human or
by `auto_review` where the client supports it; neither reviewer is guaranteed
to approve. An outer `workspace-write` session with `approval_policy=never`
cannot support this chat-native workflow because the required escalation
cannot surface.

User-selected full access may already be capable of running the launcher, but
the repository neither requires nor enables it and does not recommend it as a
mandatory workaround. Repository instructions and code do not edit `.codex`,
global or user `config.toml`, exec-policy rules, or organization settings to
obtain capability.

If the active surface cannot surface the required escalation, policy forbids
it, or approval is denied, dispatch stops fail-closed and reports the outer
execution-boundary blocker. There is no direct Git/GitHub fallback by the
outer Codex. Outer execution permission does not flow into the implementer or
reviewer children and does not weaken their fixed security profiles.

## Environment and Codex resolution

The launcher requires `<repo>/.venv` to exist and the current `sys.prefix` to
resolve to that exact environment root. It does not create or activate a
virtual environment, install packages, launch a second Python, or fall back to
system Python.

After repository, `.venv`, and repository-local `.codex` validation, the
launcher proves that the already loaded regular `tools.autonomous_pr` package
has exactly one resolved search root and that the loaded `codex_launcher.py`
and generic `__main__.py` files all come from the selected repository's
`tools/autonomous_pr` directory. A foreign checkout, site-packages/editable
source, `PYTHONPATH` source, missing module file, or multiple package roots
fails closed. The launcher does not repair `sys.path`, discard imports, or
re-import from another location.

Any filesystem entry at `<repo>/.codex` is refused, including a file,
directory, symlink, or broken symlink. The launcher does not inspect or accept
repository-local Codex configuration.

One concrete Codex executable is resolved in this strict precedence:

1. explicit `--codex PATH`;
2. non-empty `AUTONOMOUS_PR_CODEX_EXE`;
3. `codex` on `PATH`;
4. on Windows only, `%LOCALAPPDATA%\OpenAI\Codex\bin\*\codex.exe`.

An explicit, environment, or `PATH` candidate is authoritative once selected;
failure does not fall through to a lower-precedence source. The Windows
application fallback accepts exactly one candidate. Zero candidates is not
found; multiple candidates are ambiguous and require explicit `--codex`.

Before delegation the launcher runs only `<candidate> --version`, with a fixed
10-second timeout, and requires a successful `codex-cli <version>` identity.
This is a sanity check, not proof of sandbox or capability behavior; it does
not pin, install, or update Codex.

## Runtime freshness and checkout recovery

Runtime freshness has two layers. Before delegation, the launcher proves the
selected-repository loaded-package provenance described above; it never
switches to another imported checkout. After the harness freshly fetches and
captures `origin/main`, it requires a clean worktree/index and exact equality
between local `HEAD` and that captured SHA before reading the task catalog or
resolving the selector. The local branch name is irrelevant: `main`, another
branch name, or detached `HEAD` is valid at the exact commit.

A clean checkout behind or ahead of captured `origin/main` is terminal
`BLOCKED` in preflight. The launcher and harness do not pull, reset, switch,
rebase, or otherwise update the selected checkout, and a stale invocation does
not retry or resume. Recovery is a separate operator action: leave the ended
invocation blocked, manually bring the selected checkout to the required
authoritative state, and then issue a new explicit `AUTONOMOUS_PR` invocation.

## Fixed child profiles

The implementer always uses non-interactive `codex exec`, ephemeral sessions,
ignored user config and exec-policy rules, approval policy `never` through the
fixed inline config `approval_policy=never`, the `workspace-write` sandbox, and
`sandbox_workspace_write.network_access=false`. Its fixed profile mapping is:

| Orchestrator profile | Codex reasoning effort |
| --- | --- |
| `ROUTINE` | `low` |
| `DELIBERATE` | `medium` |
| `CRITICAL` | `high` |

The designated reviewer always uses non-interactive `codex exec`, ephemeral
sessions, ignored user config and exec-policy rules, approval policy `never`
through the fixed inline config `approval_policy=never`, the `workspace-write`
sandbox, and `sandbox_workspace_write.network_access=false`. There is no
approval or permission-escalation path. This `workspace-write` boundary is the
disposable reviewer inspection snapshot, never the authoritative delivery
worktree. Before every designated review, the orchestrator creates that
disposable filesystem snapshot of the exact current candidate, with no shared
`.git` metadata, and runs the reviewer there. The snapshot has its own temporary
local Git metadata only to satisfy Codex's repository trust check; it has no
remote and no link to the authoritative repository's index, refs, or objects.
The reviewer may mutate only this non-authoritative snapshot; those mutations
never become candidate or repair input, and the snapshot is removed before a
verdict is accepted. The reviewer subprocess receives no inherited GitHub
token, Git/SSH command override, askpass, or SSH-agent variables; `gh` uses an
empty snapshot-local config, Git credential helpers and interactive prompts are
disabled, and the reviewer sandbox has network access explicitly disabled.
The network restriction is the primary provider-level barrier to external
Git/GitHub writes; credential stripping remains defense in depth. Codex
authentication state remains available independently.
The authoritative delivery
worktree, its index/refs/objects, and repository-root `review.patch` remain
outside that inspection surface and are fingerprinted before and after the
review; the snapshot is removed before the verdict is accepted. The outer user
is not asked to approve reviewer commands interactively. The fixed mapping
remains `DELIBERATE → medium` and `CRITICAL → high`.

The launcher only supplies these mappings. Selection and escalation of the
reasoning-effort profile remain deterministic orchestrator responsibilities;
see `AUTONOMOUS_PR_HARNESS.md` §36. The fresh-context and no-Git/GitHub-write
flags passed to the generic CLI are reviewed configuration assertions for
these exact profiles. They are not runtime proof derived from the executable
name or version output; the harness guards remain defense in depth.

On native Windows, the launcher also appends the fixed inline config
`windows.sandbox=mxc` to both child roles. Autonomous children intentionally
use `--ignore-user-config`, so the launcher selects the native Windows sandbox
backend explicitly instead of depending on mutable user configuration. This
backend preserves the same outer autonomous security contract: both roles remain
`workspace-write` with `approval_policy=never` and
`sandbox_workspace_write.network_access=false`; the reviewer workspace remains
the disposable snapshot described above. MXC avoids relying on the elevated
backend's persistent host ACL/ownership mutation behavior, which prevented host
cleanup of a disposable reviewer workspace. There is no fallback to elevated:
if MXC is unavailable, child execution fails closed. POSIX launches receive no
Windows backend override.

## Temporary files, credentials, and host permissions

The launcher preserves inherited `CODEX_HOME` exactly and does not create,
locate, overwrite, or migrate it. Codex authentication therefore continues to
use its normal inherited/default home even though child user configuration is
ignored for these invocations.

The launcher owns the dedicated runtime root
`<system-temp>/ai-dnd-autonomous` and its fixed direct child `pip-cache`.
Before resolving either launcher-owned entry, it rejects a file, broken
symlink, symlink, or supported Windows junction. An absent directory is
created and then rechecked against the same rules. The resolved runtime root
and cache must both be outside the repository, and the resolved cache parent
must equal the resolved runtime root exactly. Each directory must pass a
create/write/flush/close/remove probe; inability to remove the probe is a
configuration failure, not a successful writable check.

Only around the single synchronous in-process generic CLI call, the launcher
sets `TEMP`, `TMP`, and `TMPDIR` to the validated runtime root,
`PIP_CACHE_DIR` to the validated `pip-cache`, and the parent process's
`tempfile.tempdir` to the runtime root. It restores the exact previous
presence and value of every environment variable—including absent and empty
states—and the exact previous `tempfile.tempdir` after success or exception.
Descendant verification processes inherit these scoped environment values.
The launcher leaves `CODEX_HOME`, pip index/authentication/proxy/certificate
settings, dependency-resolution policy, and network policy unchanged;
`PIP_CACHE_DIR` selects only the writable cache location. These directories
are temporary subprocess workspace, not persisted harness state.

The outer Codex host sandbox/permission boundary and each child Codex sandbox
are separate. The launcher fixes the child profiles described above, but it
does not itself bypass, broaden, or automatically escalate outer-host
restrictions. The outer Codex must establish the approval-aware launcher
execution described above; if it cannot, dispatch stops fail-closed rather
than weakening a gate or substituting direct Git/GitHub operations.

## Terminal outcomes

The generic harness owns all task selection, preflight, implementation,
review/repair, Mode C, publication, and required-CI behavior. Refer to
`AGENTS.md` and `AUTONOMOUS_PR_HARNESS.md` for those algorithms rather than
reproducing them here.

- `STOP` ends the invocation.
- `BLOCKED` ends the invocation and reports the harness diagnostics.
- `NO_ELIGIBLE_TASK` is terminal no-work; it does not authorize a fallback
  task.
- `READY_FOR_HUMAN_MERGE` is reported through the contract's
  `READY_FOR_HUMAN_MERGE → STOP` boundary. It does not merge the PR.

After any terminal result, the outer Codex reports it and stops. Merge always
requires separate human authorization. A new run likewise requires a new
explicit user instruction; the operator must not infer a retry or select
another task.

## Troubleshooting

| Failure | Required operator action |
| --- | --- |
| Wrong or missing `.venv` | Create/install the repository environment through the documented setup, then invoke the launcher with that `.venv` Python. Do not use system Python. |
| Codex not found | Install/configure Codex outside the launcher or pass the intended executable with `--codex` or `AUTONOMOUS_PR_CODEX_EXE`. |
| Multiple Windows fallback candidates | Choose the intended concrete executable explicitly with `--codex`; the launcher never guesses. |
| `codex --version` failure, timeout, or malformed identity | Verify the selected executable manually and correct the path/installation. The launcher does not update or replace it. |
| Repository `.codex` refused | Remove the repository-local configuration from this execution boundary or use a separately reviewed future change; the launcher never ignores the guard. |
| Local runtime `HEAD` is behind or ahead of captured `origin/main` | Leave the invocation `BLOCKED`, update the selected checkout manually outside it, then issue a new explicit `AUTONOMOUS_PR` invocation. Branch name is not the invariant; exact commit SHA is. |
| Runtime root or pip-cache validation/probe fails | Remove a file/link/junction collision or correct host temp-path permissions so both launcher-owned directories are real, outside the repository, exact parent/child, writable, and removable. |
| Outer-host permissions are insufficient | The outer Codex requests approval for the single launcher command before execution. If escalation is unavailable, forbidden, or denied, stop fail-closed; the launcher does not request, bypass, or manufacture permission, and there is no direct Git/GitHub fallback. |
