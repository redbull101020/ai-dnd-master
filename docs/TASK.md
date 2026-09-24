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
discussion and approval
→ publish one reviewed task file on main
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

Concrete outcome.

## Context / References

Authoritative references.

## Scope

- Included work.

## Out of scope

- Explicit exclusions.

## Approved implementation approach

Approved approach and binding decisions.

## Acceptance criteria

- Observable acceptance result.

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
