# Task dispatch and terminal registry

This document defines task-file governance and stores the permanent terminal
registry. It is not an active-task queue. Open-task metadata belongs only to
Git-tracked regular files at `docs/tasks/TSK-NNNN.md`.

## 1. Standalone task documents

A task file has a filename/H1-matching immutable ID, one `## Task metadata`
section containing exactly one fenced JSON object, and either `draft` or
`approved` `execution_approval`. Required metadata are `execution_approval`,
`priority`, `size`, `roadmap_target`, and `depends_on`; `group` is optional and
is one of `mechanics`, `cross-cutting`, `engineering`, `documentation`, or
`architecture`.

Priority means: `P0` — correctness or a hard delivery-path blocker; `P1` —
current critical-path work; `P2` — useful adjacent work; `P3` — future,
optional, or cleanup work. It orders otherwise eligible `NEXT` candidates as
P0 → P1 → P2 → P3, but never overrides Roadmap scope or dependencies.

Size measures review complexity, not elapsed time: `S` is one narrow coherent
slice, `M` is larger but still cohesive and reviewable, and `L` is too broad
or insufficiently understood for execution as one task. Approved executable
work is S or M; L must be decomposed before approval. Every task must remain
independently reviewable and mergeable.

Draft documents have a valid envelope but need not have a complete execution
body and are never executable. Approved documents contain all nine execution
sections in the order shown by the template below, concrete CP-1…CP-N fields,
JSON-argv verification commands, and no unresolved execution requirement.
Approval and publication are execution input, not invocation authority.

For orchestration or tooling tasks, refinement must put every already-known
material boundary failure mode into binding task content — especially
checkpoint `Constraints`, Acceptance criteria, and/or deterministic
`Verification`, as appropriate. Advisory `Review focus` may direct attention
but does not make a requirement binding by itself.

### Task planning and refinement

Ordinary future planning and refinement should produce one or more
independently mergeable, execution-ready S/M Task Execution Specs that are
ordinarily suitable for `AUTONOMOUS_PR`. Execution readiness is a quality of
the task contract; `MANUAL` and `AUTONOMOUS_PR` are delivery and authority
modes. Choosing `MANUAL` therefore does not lower the execution-readiness
quality bar, and publication or approval remains distinct from the separate
explicit invocation required to activate `AUTONOMOUS_PR`.

Planning must inspect the current canonical sources and implementation and
resolve every applicable material decision before approval. A decision is
material when, without it, an implementer or reviewer would have to do any of
the following independently:

- expand or choose scope;
- create or change a canonical contract, or choose State ownership;
- invent a material Command, Event, or Result contract;
- choose material validation or error behaviour;
- choose persistence, schema, Event ordering, causality, or atomicity
  behaviour;
- change an observable required result or the dependency set; or
- add an unapproved production dependency.

This checklist is applicability-based: a task need not involve State, Events,
persistence, schema, or any other listed concern when that concern is outside
its scope. An unresolved material decision means that the work remains in
planning/refinement and cannot become an approved executable task. `draft` is
the sole existing state for a task file whose refinement is incomplete; this
policy adds no planning/refinement metadata or lifecycle status. Implementers
retain freedom over local, non-material coding choices within the boundaries
defined by `AUTONOMOUS_PR_HARNESS.md` §24.

Approved executable work remains S/M, and L work must be decomposed before
approval. Decomposition follows cohesion, independent mergeability,
independently observable acceptance, and independent review and verification
boundaries; file count, line count, or checkpoint count is not a mechanical
split threshold. Checkpoints remain internal review-risk boundaries within
one coherent mergeable TSK, not miniature task IDs.

A separate architecture-only TSK is an exception, not a mandatory
define-then-implement sequence. It is justified when the architecture or
documentation outcome is independently valuable and reviewable, or must be
accepted separately before publication of the implementation task. A new
canonical architecture decision must be published through the normal
canonical sources and procedure before autonomous execution relies on it. A
resolved task-specific decision that creates no new canonical contract may
instead live in the approved TSK's binding sections.

When one planning cycle resolves both a new canonical architecture decision
and the resulting implementation-ready task spec(s), the canonical
architecture/decision updates and resulting approved TSK file(s) may be
prepared and reviewed together in one `MANUAL` planning/publication PR,
subject to the existing document-ownership and authority rules. Architecture
work alone does not require a separate architecture-only TSK or a separate
architecture publication PR. The resulting approved task may rely on that
decision only after the canonical truth is published on `main`; publication
or approval still does not activate `AUTONOMOUS_PR`.

Planning conversation, chat, and history are not durable project sources of
truth. Before execution, load-bearing decisions must be transferred to
repository sources. In particular, a load-bearing task-specific decision
cannot exist only in informational `Context / References` or `Known
constraints / edge cases`, or in advisory `Review focus`; it must also appear
in an applicable binding section under the existing §24 boundary. The
existing nine-section Task Execution Spec and metadata schema remain
unchanged.

## 2. Identity, dependencies, and deterministic selection

Task IDs are never reused. Allocate `max(standalone IDs, terminal IDs) + 1`;
gaps remain allocated. Concurrent allocation conflicts are reconciled before
merge. Before deleting a cancelled nonterminal file, record its identity as
`Superseded` in the terminal registry.

Dependencies are task IDs. Unknown, self, duplicate, and cyclic dependencies
are invalid. Only authoritative `Done` satisfies a dependency; `Superseded`
does not. A known nonterminal dependency makes a task wait.

An invocation supplies exactly one explicit `TSK-NNNN` or literal `NEXT`.
Explicit selection does not fall back. `NEXT` considers approved eligible S/M
tasks from one exact `origin/main` snapshot and orders them by priority, then
numeric ID. Draft, terminal, and waiting tasks are excluded. A valid catalog
without an eligible candidate returns `NO_ELIGIBLE_TASK` without branch,
agent, or PR writes. Initial catalog validation is strict; after selection,
fixed-target revalidation checks only the selected document, its approval,
terminal outcome, dependencies, and repository safety facts. It never
reselects because an unrelated file changed.

## 3. Workflow and authority

```text
Roadmap capability / requested change
→ planning and refinement
→ inspect current canonical sources and implementation
→ resolve applicable material decisions
→ persist new canonical decisions when required
→ decompose L / independently mergeable work
→ approve and publish reviewed execution-ready S/M task spec(s) on main
→ separate explicit AUTONOMOUS_PR <ID|NEXT> invocation
→ fixed task / checkpoints / independent review / adaptive repair
→ Full verification
→ accepted cumulative implementation review
→ reviewed draft PR
→ unpublished prospective Task Closure and Closure Review
→ fresh revalidation and Mode C
→ publish exact audited candidate
→ required CI
→ READY_FOR_HUMAN_MERGE → STOP
→ human merge
→ optional separate reviewed removal of a terminal spec
```

A chat instruction is not the configured CLI. A real run additionally needs
actual implementer/reviewer executables, a fresh independent reviewer context,
and verified sandboxes without direct Git/GitHub write capability. No provider
integration is implied by this document. Merge remains human-only. `STOP`,
`BLOCKED`, and `NO_ELIGIBLE_TASK` never start another task or perform cleanup.

Task Closure appends only the selected task's `Done` row with real PR evidence
and one factual Development Log entry. It preserves all other terminal rows
and does not delete the task file. After authoritative `Done` or `Superseded`
on main, that file may be removed by a separate reviewed change; terminal
facts remain sufficient without it.

If a delivery merges without its closure, `Done` is not inferred from the
merged code or PR. A separate reviewed **MANUAL** reconciliation must add the
terminal row with factual evidence and the factual Development Log entry.
Until that reconciliation reaches authoritative `main`, the task is not
`Done` and no dependency on it is satisfied.

## 4. Future approved task template

````markdown
# TSK-NNNN — Task title

## Task metadata

```json
{
  "execution_approval": "approved",
  "priority": "P2",
  "size": "M",
  "roadmap_target": "Phase / approved capability slice",
  "depends_on": [],
  "group": "engineering"
}
```

## Goal

Concrete observable outcome with no unresolved material design choice.

## Context / References

Authoritative references.

## Scope

- Exact bounded execution scope.

## Out of scope

- Explicit scope exclusions.

## Approved implementation approach

Binding approach and resolved task-specific decisions. Cite canonical
architecture; do not create a new canonical contract here.

## Acceptance criteria

- Observable deterministic completion conditions.

## Execution checkpoints

### CP-1 — Checkpoint name
- Objective: Why this checkpoint exists.
- Required result: Observable result.
- Constraints: Scope and safety limits.
- Verification: ["python", "-m", "pytest", "tests/relevant"]
- Review focus: Highest-risk review area.

## Full verification

["python", "-m", "pytest"]
["python", "-m", "mypy", "src", "tools/autonomous_pr"]
["git", "diff", "--check"]

## Known constraints / edge cases

Concrete known constraints.
````

# Terminal task index

| ID | Status | Evidence | Title |
| --- | --- | --- | --- |
| `TSK-0001` | `Done` | PR #69 / merge commit `f4dbc50` | Define the minimal authoritative Character weapon source |
| `TSK-0002` | `Done` | PR #68 / merge commit `d8f86ed` | Define active-turn gating for `AttackCommand` |
| `TSK-0003` | `Done` | PR #72 / merge commit `7ac97f6` | Define zero-HP Attack eligibility by creature category |
| `TSK-0004` | `Done` | PR #80 / merge commit `d1b23de` | Implement the approved minimal Character weapon source and persistence |
| `TSK-0005` | `Superseded` | decomposed into TSK-0010..TSK-0013 by commit `c4db43d` | Implement the Character Dagger Attack → Damage → Monster HP continuation |
| `TSK-0006` | `Done` | PR #75 / merge commit `d590056` | Implement active-turn Attack gating |
| `TSK-0007` | `Done` | PR #77 / merge commit `7798ed7` | Implement zero-HP Attack eligibility |
| `TSK-0008` | `Done` | PR #70 / merge commit `24da875` | Define minimal melee targeting and reach for the first Character Dagger attack |
| `TSK-0009` | `Done` | PR #71 / merge commit `e99d0dc` | Deduplicate README/CLAUDE and remove redundant current data-flow projection |
| `TSK-0010` | `Done` | PR #83 | Implement Combat-owned positioning and State schema V7 |
| `TSK-0011` | `Done` | PR #84 | Define exact Character Dagger Attack and Damage contracts |
| `TSK-0012` | `Done` | PR #85 | Implement Character Dagger weapon Attack resolution |
| `TSK-0013` | `Done` | PR #86 | Implement Character Dagger Attack → Damage → Monster HP consequence |
| `TSK-0014` | `Done` | PR #88 | Define the minimal ordinary-Action resource contract for existing `AttackCommand` consumers |
| `TSK-0015` | `Done` | PR #89 | Implement minimal current-turn Action expenditure for existing `AttackCommand` consumers |
| `TSK-0016` | `Done` | PR #91 | Define minimal Character zero-HP turn and Death Save contract |
| `TSK-0017` | `Done` | PR #92 | Implement minimal Character Death Save vertical slice |
| `TSK-0018` | `Done` | PR #93 | Define minimal Combat end lifecycle contract |
| `TSK-0019` | `Done` | PR #94 | Implement minimal CombatEnded vertical slice |
| `TSK-0020` | `Done` | PR #95 | Tighten development workflow and task-governance automation |
| `TSK-0021` | `Done` | PR #97 | Define minimal Combat Movement and placement-boundary contract |
| `TSK-0022` | `Done` | PR #98 | Implement initial Combat tactical placement vertical slice |
| `TSK-0024` | `Done` | PR #101 | Define bounded `AUTONOMOUS_PR` development-governance contract |
| `TSK-0025` | `Done` | PR #102 | Define minimal `AUTONOMOUS_PR` execution-harness contract |
| `TSK-0026` | `Done` | PR #103 | Implement minimal local `AUTONOMOUS_PR` execution harness |
| `TSK-0027` | `Done` | PR #104 | Define Task Execution Spec and adaptive `AUTONOMOUS_PR` v2 contract |
| `TSK-0028` | `Done` | PR #106 | Implement and atomically activate spec-driven adaptive `AUTONOMOUS_PR` v2 |
| `TSK-0029` | `Done` | PR #108 | File-based task dispatch, deterministic NEXT and removable completed specs |
| `TSK-0030` | `Done` | PR #109 | Harden AUTONOMOUS_PR review convergence, finding grounding and diagnostics |
| `TSK-0031` | `Done` | PR #110 | Add deterministic adaptive compute-profile routing to AUTONOMOUS_PR |
| `TSK-0032` | `Done` | PR #119 | Remove retained terminal task specs as the first production AUTONOMOUS_PR pilot |
| `TSK-0033` | `Done` | PR #112 | Harden AUTONOMOUS_PR verification runtime binding and prospective closure evidence handoff |
| `TSK-0034` | `Done` | PR #114 | Harden AUTONOMOUS_PR Mode C authoritative evidence handoff and replay freshness |
| `TSK-0035` | `Done` | PR #116 | Stabilize AUTONOMOUS_PR required-CI observation across check registration and pending states |
| `TSK-0036` | `Done` | PR #118 | Preserve bounded structured rationale for explicit AUTONOMOUS_PR reviewer BLOCKED verdicts |
| `TSK-0037` | `Done` | PR #120 | Add a deterministic Codex operator launcher for one-command AUTONOMOUS_PR execution |
