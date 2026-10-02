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
an absolute path. Timeout defaults are respectively `1800.0`, `1800.0`, and
`600.0` seconds. Overrides must be finite and greater than zero; valid values
are forwarded without clamping or rounding. The launcher exposes no arbitrary
agent argv, model, provider, sandbox, approval, network, delivery-branch,
verification-command, capability-assertion, merge, or auto-merge override.

## Environment and Codex resolution

The launcher requires `<repo>/.venv` to exist and the current `sys.prefix` to
resolve to that exact environment root. It does not create or activate a
virtual environment, install packages, launch a second Python, or fall back to
system Python.

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

The launcher creates and probes `<system-temp>/ai-dnd-autonomous`, which must
resolve outside the repository and be writable. Only around the in-process
generic CLI call it sets `TEMP`, `TMP`, and `TMPDIR` to that same directory;
all three variables are restored afterward, including after an exception.
This directory is temporary subprocess workspace, not persisted harness state.

The outer Codex host sandbox/permission boundary and each child Codex sandbox
are separate. The launcher fixes the child profiles described above, but it
does not bypass, broaden, or automatically escalate outer-host restrictions.
If the outer host cannot perform a harness-owned Git/GitHub operation, the run
must fail or stop under the existing contract rather than weakening a gate.

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
| Temp directory creation/write probe fails | Correct host temp-path permissions or configuration so the dedicated directory is outside the repository and writable. |
| Outer-host permissions are insufficient | Adjust the outer execution authorization separately if appropriate. The launcher does not request, bypass, or manufacture those permissions. |
