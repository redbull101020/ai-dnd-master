# Task Queue

Thin operational lifecycle tracker for AI D&D Engine development.

`docs/TASK.md` owns task lifecycle and queue facts. Execution requirements for
an executable task live only in its stable Task Execution Spec at
`docs/tasks/TSK-NNNN.md`.

---

## 1. Authority

Sources of truth, in order:

1. `docs/ARCHITECTURE.md` — canonical product architecture.
2. `docs/ROADMAP.md` — phase and capability scope.
3. `docs/TASK.md` — task lifecycle, dependencies, and ordering.
4. `docs/tasks/TSK-NNNN.md` — fixed execution contract for one task.
5. `docs/DECISIONS.md` and `docs/DEFERRED.md` — rationale and deferred scope.

The tracker never grants commit, push, PR, merge, or `AUTONOMOUS_PR`
authority. Those permissions remain exclusively in `AGENTS.md`.

## 2. Task identity and lifecycle

Task IDs are immutable `TSK-NNNN` identifiers. The closed status set is:

- `Backlog`
- `Ready`
- `Current`
- `Blocked`
- `Done`
- `Superseded`

The Open task index contains only `Backlog`, `Ready`, `Current`, and
`Blocked`. The Terminal task index contains only `Done` and `Superseded` and
is never truncated. A task ID appears in exactly one index.

- `Backlog` records recognized work that is not yet execution-ready.
- `Ready` means the readiness gate is satisfied, but does not authorize work.
- `Current` is the one selected execution target.
- `Blocked` records work that cannot proceed until its stated dependency,
  decision, or external condition is resolved.
- `Done` is authoritative only after the implementation and Task Closure are
  accepted on `main` (or the fallback reconciliation of §18.2 lands).
- `Superseded` permanently reserves work that was replaced, absorbed,
  invalidated, or deliberately dropped; its durable reason belongs in
  terminal evidence and `docs/DEVELOPMENT_LOG.md`.

Task IDs are never reused. `Next free ID` must be greater than every allocated
Open or Terminal ID; gaps do not become reusable IDs.

## 3. Task Execution Spec

The stable spec path is a pure function of task identity:

```text
docs/tasks/TSK-NNNN.md
```

Spec lifecycle:

| Tracker status | Task Execution Spec |
| --- | --- |
| `Backlog` | optional |
| `Ready` | required and execution-ready |
| `Current` | required and execution-ready |
| `Blocked` | retained if it exists |
| `Done` / `Superseded` | retained if it exists |

The spec carries execution facts only. It must not duplicate mutable tracker
fields such as Status, Priority, Size, dependencies, or queue position.
The nine mandatory spec sections and their binding semantics are defined in
`docs/AUTONOMOUS_PR_HARNESS.md` §§22–24.

Goal, Scope, Out of scope, Approved implementation approach, Acceptance
criteria, execution checkpoints, and verification live in the Task Execution
Spec, not in this thin lifecycle tracker.

`TSK-0028` is the one transition task that began under operational v1 and is
completed manually by the activation change itself. It deliberately has no
`docs/tasks/TSK-0028.md`; this historical fact is not a runtime exception.

## 4. Open task index schema

The table has exactly these columns:

| ID | Status | P | Size | Group | Roadmap target | Depends on | Title |
| --- | --- | --- | --- | --- | --- | --- | --- |

- `P0` is correctness or a hard current-path blocker; `P1` is current
  critical-path work; `P2` is useful adjacent work; `P3` is future, optional,
  or cleanup work. Priority is not queue order and never overrides Roadmap
  scope, dependencies, or the explicit Current/Next selection.
- Size measures review complexity, not elapsed time: `S` is one narrow
  coherent slice, `M` is a larger but still cohesive reviewable slice, and
  `L` is too broad or insufficiently understood for execution as one task.
  Size `L` must be decomposed before `Ready` or `Current`.
- `Group` is one of `mechanics`, `cross-cutting`, `engineering`,
  `documentation`, `architecture`.
- `Depends on` is `—` or a comma-separated list of backtick-wrapped task IDs.
- every dependency of a `Ready` or `Current` task is a `Done` row in the
  Terminal task index.
- there is at most one `Current` row, and it must match Current position.

Full task detail is not stored in this file for `Ready` or `Current` tasks;
the Task Execution Spec is their complete execution target. A compact backlog
row is sufficient until refinement produces its spec.

## 5. Terminal task index schema

The durable table has exactly these columns:

| ID | Status | Evidence | Title |
| --- | --- | --- | --- |

`Evidence` identifies the accepted PR or the historical decomposition/closure
commit that proves the terminal state. Unlike the human-oriented recent view,
this index is authoritative and unbounded.

## 6. Readiness and selection

A task may become `Ready` only when its dependencies are terminal `Done`, its
Roadmap target is still active, its size is `S` or `M`, and its Task Execution
Spec exists and is execution-ready. The task must be one coherent,
independently reviewable and mergeable delivery slice. `Current` is selected
from eligible work in deliberate order; it is an execution target, not
authorization to start.

If no eligible task exists, Current is `—`. A task is never promoted merely to
avoid an empty Current position.

## 7. Progressive elaboration

Backlog tasks may remain compact. Refinement creates or completes the stable
Task Execution Spec before promotion to `Ready`. Once an autonomous invocation
starts, the accepted spec is fixed for that run; changing it is a fail-closed
condition, never an in-run repair technique.

## 8. Dependencies

Dependencies are lifecycle facts in the Open task index. They are not inferred
from prose or from the bounded Recently completed view. A missing terminal row
cannot be interpreted as `Done`. Every dependency names an existing Open or
Terminal task, self-dependencies and dependency cycles are forbidden, and only
`Ready`/`Current` require every dependency to be Terminal `Done`.
`Backlog`/`Blocked` may depend on unfinished Open tasks.

## 9. Review triggers

Revalidate the queue after task closure, dependency changes, Roadmap changes,
new blockers, task decomposition, or any change to Current/Next selection.

## 10. Current position

The authoritative live values are in the unnumbered section below. `Next`
lists at most five `Ready` tasks in deliberate order. `Next free ID` is the
allocation source and does not imply that every lower number is an active task.
Current followed by Next is the only authoritative queue order; Open index row
order has no scheduling meaning.

## 11. Open task index

The authoritative live table is in the unnumbered section below. It is the
only source for mutable facts about open tasks.

## 12. Readiness gate

Promotion to `Ready` or `Current` requires all mechanical conditions in §§3,
4, 6, and 8 plus an approved, internally consistent execution spec. A task
requiring a new architectural decision or production dependency remains
ineligible until that decision or dependency is separately approved.

## 13. Task references

Architecture and Roadmap references belong in the Task Execution Spec. The
tracker keeps only the Roadmap target needed for lifecycle validation.

## 14. Contract impact

Contract-impact analysis belongs in the Task Execution Spec and its review,
not in duplicated tracker detail.

## 15. Task details

Operational v2 has no Open task details section. `Ready` and `Current` details
live in `docs/tasks/TSK-NNNN.md`; Backlog uses its compact index row.

## 16. Queue selection

Selection follows Roadmap scope, dependencies, priority, review risk, and
smallest coherent delivery slices. It never silently changes architecture.

## 17. Current and Next invariants

1. At most one task is `Current`.
2. Current position matches the single Current row.
3. Every task in Next is `Ready`.
4. Every `Ready`/`Current` task has an execution-ready spec and all
   dependencies terminal `Done`.
5. Size `L` is never `Ready` or `Current`.
6. Open and terminal IDs are unique and disjoint.

## 18. Task closure and history

Closure atomically moves the completed task from the Open task index to the
Terminal task index as `Done`, records evidence, updates the recent view,
reconciles Current/Next/blockers, and appends one concise factual entry to
`docs/DEVELOPMENT_LOG.md`. The accepted spec remains at its stable path.
Prepared closure is prospective: neither `Done` nor a represented next
`Current` becomes authoritative until the delivery PR merges to `main`.

### 18.1 Normal path — closure prepared before merge

Before prospective closure, deterministic Full verification is green and the
complete implementation diff has been reviewed and accepted. In v2 the closure
candidate stays unpublished while Closure Review and Mode C audit it. Only the
exact audited candidate is then pushed. Its tracker changes are prospective
until the delivery PR merges.

### 18.1.1 Prospective immediate-dependent representation

The same closure may represent one immediate dependent as the prospective next
`Current` only when its sole unfinished dependency is the task becoming `Done`
in that closure and every other readiness condition already holds. No work on
that next task starts before merge and a fresh authoritative preflight.

### 18.2 Fallback path — post-merge reconciliation

If closure was not prepared in the delivery PR, a separate reviewed
reconciliation change records the terminal state before another task begins.

## 19. Recently completed

This is a bounded human-readable view, not dependency truth. The Terminal task
index is authoritative.

## 20. Operational principles

- one operational `AUTONOMOUS_PR` contract: v2;
- lifecycle in this tracker, execution in Task Execution Specs;
- deterministic orchestration owns all transitions;
- no LLM-selected gate transition;
- no numeric repair limit;
- no merge or auto-merge authority.

---

# Current position

- **Current:** TSK-0028
- **Next:** —
- **Hard blockers:** —
- **Next free ID:** TSK-0029
- **Last reviewed:** 2026-09-21

---

# Open task index

| ID | Status | P | Size | Group | Roadmap target | Depends on | Title |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `TSK-0028` | `Current` | `P2` | `M` | `engineering` | Cross-cutting engineering prerequisite for continued Phase 3 delivery: activate the approved `AUTONOMOUS_PR` v2 workflow | `TSK-0027` | Implement and atomically activate spec-driven adaptive `AUTONOMOUS_PR` v2 |
| `TSK-0023` | `Backlog` | `P2` | `L` | `mechanics` | Phase 3 / Reactions + Opportunity attacks | — | Opportunity Attack / Reaction continuation |

---

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

---

# Recently completed

| ID | Title | Evidence |
| --- | --- | --- |
| `TSK-0027` | Define Task Execution Spec and adaptive `AUTONOMOUS_PR` v2 contract | PR #104 |
| `TSK-0026` | Implement minimal local `AUTONOMOUS_PR` execution harness | PR #103 |
| `TSK-0025` | Define minimal `AUTONOMOUS_PR` execution-harness contract | PR #102 |
| `TSK-0024` | Define bounded `AUTONOMOUS_PR` development-governance contract | PR #101 |
| `TSK-0022` | Implement initial Combat tactical placement vertical slice | PR #98 |
| `TSK-0021` | Define minimal Combat Movement and placement-boundary contract | PR #97 |
| `TSK-0020` | Tighten development workflow and task-governance automation | PR #95 |
| `TSK-0019` | Implement minimal CombatEnded vertical slice | PR #94 |
| `TSK-0018` | Define minimal Combat end lifecycle contract | PR #93 |
| `TSK-0017` | Implement minimal Character Death Save vertical slice | PR #92 |
