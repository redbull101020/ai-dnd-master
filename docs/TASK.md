# Task Queue

Operational task tracker for AI D&D Engine development.

`TASK.md` answers three practical questions:

```text
What are we doing now?
What should we do next?
Why is that the right next slice?
```

It is deliberately a thin planning layer. It must not become a second Roadmap,
Architecture document, Deferred register, Development Log, or issue tracker.

---

## 1. Document role and authority

Project documentation has the following responsibilities:

| Document | Responsibility |
| --- | --- |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Canonical architecture and behavior contracts |
| [`ROADMAP.md`](ROADMAP.md) | Phase/capability scope, phase ordering, and completion status |
| `TASK.md` | Current executable slice and short-term task ordering inside allowed Roadmap scope |
| [`DEFERRED.md`](DEFERRED.md) | Deferred concerns and continuation context |
| [`DECISIONS.md`](DECISIONS.md) | Append-only architectural rationale/history |
| [`DEVELOPMENT_LOG.md`](DEVELOPMENT_LOG.md) | Append-only factual history of completed development iterations |
| [`../AGENTS.md`](../AGENTS.md) | Agent workflow, authorization, testing, branches, commits, PRs, and Definition of Done |

Authority for implementation planning:

```text
ARCHITECTURE
    ↓
ROADMAP
    ↓
TASK
    ↓
implementation
```

`ROADMAP.md` decides what belongs to the active phase and any ordering or
dependencies that are explicitly fixed there.

`TASK.md` decides which concrete reviewable slice is `Current` and the short
order of executable work inside that permitted scope.

`TASK.md` must never:

- change canonical behavior;
- contradict `ARCHITECTURE.md`;
- move work across Roadmap phase boundaries without an explicit project decision;
- treat a deferred proposal as an approved contract;
- turn an audit finding into canonical behavior by itself;
- authorize editing, committing, pushing, opening a pull request, or merging.

Authorization remains governed exclusively by `AGENTS.md`.

If `TASK.md`, `ROADMAP.md`, `ARCHITECTURE.md`, code, or the requested task
conflict, report the conflict instead of resolving it silently.

---

## 2. Task model

A task is one coherent, independently reviewable delivery slice.

Normally:

```text
one TSK
→ one coherent implementation/documentation result
→ one review
→ one pull request
→ merge to main
```

A task is not:

- every prompt sent to an agent;
- every commit;
- every review checkpoint;
- every temporary implementation step;
- every Roadmap checkbox;
- every `DEF-*` concern.

Several sequential implementation checkpoints may remain inside one task when
they must land together as one coherent change.

If work is too large to be reviewed coherently as one result, split it before
execution.

A task should normally describe the smallest slice that:

1. advances the current Roadmap frontier;
2. can be reviewed as one coherent change;
3. can be verified independently;
4. does not require unrelated speculative architecture.

---

## 3. Task IDs

Task IDs use:

```text
TSK-0001
TSK-0002
TSK-0003
...
```

Rules:

1. IDs are allocated sequentially repository-wide.
2. IDs are never reused.
3. IDs do not encode phase, group, priority, status, or implementation type.
4. A task keeps the same ID if its priority or queue position changes.
5. Completed or superseded IDs remain permanently reserved.
6. Renaming or clarifying a task title does not change its ID.
7. `Next free ID` in `Current position` is the allocation source.

Do not use IDs such as:

```text
P3-COMBAT-01
WEAPON-P1-07
DOCS-004
```

Mutable planning attributes belong in fields, not identity.

---

## 4. Statuses

Allowed statuses:

```text
Backlog
Ready
Current
Blocked
Done
Superseded
```

### 4.1 Backlog

Known work that is not yet ready for execution.

Typical reasons:

- the task is too far from the current execution frontier;
- exact scope is not yet worth refining;
- a future consumer is still missing;
- the task is intentionally broad and needs later decomposition;
- canonical prerequisites are not yet settled.

Backlog tasks should remain compact until they approach execution.

### 4.2 Ready

A sufficiently specified, unblocked, reviewable task that may enter `Next`.

A task becomes `Ready` only after passing the readiness gate in §12.

### 4.3 Current

The single task selected as the project's current execution target.

Repository invariant:

```text
count(Status == Current) <= 1
```

When executable work exists in the current Roadmap scope, the normal state is:

```text
count(Status == Current) == 1
```

`Current` is a planning state only.

It does **not** mean:

- implementation has been authorized;
- a branch currently exists;
- an agent is currently modifying files;
- commit/push/PR/merge has been authorized.

Those controls remain in `AGENTS.md`.

### 4.4 Blocked

A task that would otherwise be relevant but cannot currently proceed.

Valid blockers include:

- unresolved canonical conflict;
- required architectural decision;
- unfinished task dependency;
- missing concrete evidence/consumer where the architecture explicitly requires it;
- a genuine external prerequisite.

Low priority is not a blocker.

Every blocked task must state:

```text
Blocker:
Unblock condition:
```

### 4.5 Done

A task is authoritatively `Done` only when **both** its accepted result
**and** the corresponding Task Closure (§18) exist on `main`. `main` is the
authoritative operational state of the Task Queue; nothing on a delivery
branch is a fact of the project until it lands there.

The following are not sufficient on their own to make a task authoritatively
`Done`:

- code was written;
- local tests passed;
- `review.patch` was reviewed;
- a commit exists;
- the branch was pushed;
- a pull request exists;
- review approved the pull request;
- a delivery branch/PR already writes `Done` for its own task;
- the accepted result exists on `main` but the corresponding Task Closure
  has not yet landed there (the §18.2 fallback is in progress but not yet
  merged).

Once implementation has been accepted (tests/checks passed, diff reviewed),
a delivery branch/PR may prepare its own Task Closure (§18.1) — including
writing `Done` for its task, in that same branch/PR — before merge. This
prepared state is **prospective**: it describes what `TASK.md` will become
true if and when that exact PR merges. It carries no operational authority
before merge: the task is not yet actually finished, implementation of the
task the branch shows as the next `Current` must not begin, and no new
delivery branch may be based on that prospective `Current`. If the PR is
never merged, the prospective `Done` never becomes a fact of the project.

Once the delivery PR lands on `main`, its prepared `Done`/closure becomes
authoritative as part of that same merge — no separate action is required,
because both halves of the condition (accepted result and Task Closure)
land together. If a task's accepted result instead lands on `main` without
a prepared closure, the task is **not yet** authoritatively `Done`: Task
Closure (§18.2) is mandatory as a fallback, and the tracker must be
reconciled — landing the closure on `main` — before implementation of the
next `Current` task begins.

### 4.6 Superseded

The task is no longer intended to be executed because its scope was:

- replaced by another task;
- absorbed into a different coherent slice;
- invalidated by a later design;
- deliberately dropped.

The ID remains reserved.

The durable reason belongs in `DEVELOPMENT_LOG.md`.

---

## 5. Task lifecycle

Normal lifecycle:

```text
Backlog
   ↓ refinement
Ready
   ↓ selection
Current
   ↓ implementation + review + merge
Done
```

Alternative transitions:

```text
Backlog → Blocked
Ready   → Blocked
Current → Blocked

Backlog → Superseded
Ready   → Superseded
Current → Superseded
```

A dependency boundary is normally also a merge boundary.

If:

```text
TSK-0043 depends on TSK-0042
```

then `TSK-0043` normally cannot become `Ready` until `TSK-0042` is `Done`
on `main`.

If multiple implementation steps must be completed sequentially before one
merge, they should normally remain checkpoints inside a single task rather than
becoming artificial dependent tasks.

Task Closure is an operational reconciliation step, not a new task
lifecycle status and not a separate delivery task. The normal path prepares
it before merge, in the same delivery branch/PR as the implementation:

```text
Current
→ implementation/review
→ prepared Task Closure (§18.1) in the same delivery branch/PR
→ review closure diff + revalidate current origin/main
→ one merge lands implementation + closure together
→ authoritative Done on main
→ next Current may begin implementation
```

Fallback, used only when implementation lands on `main` without a prepared
closure — by mistake or for an exceptional reason (§18.2):

```text
implementation lands on main without prepared closure
→ mandatory post-merge reconciliation
→ next task remains blocked from implementation until the tracker is
  reconciled
```

Task Closure never gets its own `TSK-*`, whether prepared before merge or
performed after. Do not create administrative recursion such as
`TSK-0011 — Close TSK-0010` whose only deliverable is updating the tracker;
that reconciliation is Task Closure itself, performed per §18.

---

## 6. Priority

Allowed priorities:

```text
P0
P1
P2
P3
```

### P0 — correctness or hard current-path blocker

Use only when the task:

- fixes a correctness problem in implemented/canonical behavior;
- resolves a contradiction between authoritative project sources;
- blocks the current Roadmap critical path;
- is a mandatory prerequisite for the nearest concrete vertical slice.

`P0` does not mean "important feature".

### P1 — current critical-path work

Normal active-phase work that directly advances the current Roadmap frontier.

Most executable feature work should be `P1`.

### P2 — useful adjacent work

Relevant and worthwhile, but not required for the nearest critical-path slice.

### P3 — future / optional / cleanup

Examples:

- optional tooling;
- non-blocking cleanup;
- speculative future capability;
- optimization without current evidence;
- distant maintenance.

Priority is not execution order.

A `P1` prerequisite may correctly execute before an unrelated `P0`, and a
future-phase task must not jump ahead of current Roadmap scope merely because it
was labelled `P0`.

Authoritative short-term sequencing is `Current` followed by `Next`.

---

## 7. Size

Size represents review complexity, not time.

Allowed values:

```text
S
M
L
```

### S

One narrow, coherent, reviewable delivery slice.

### M

A larger slice touching several tightly related modules/contracts while still
remaining independently reviewable and mergeable.

### L

Too broad or insufficiently understood to execute as one task.

A task with size `L` must be decomposed before becoming `Ready` or `Current`.

No hour/day estimates are tracked in this file.

Executable invariant:

```text
Ready or Current
    ⇒ Size ∈ {S, M}
```

---

## 8. Groups

Use exactly one group:

```text
mechanics
cross-cutting
engineering
documentation
architecture
```

### mechanics

Gameplay mechanics that directly advance Roadmap capability scope.

### cross-cutting

Continuation work that spans mechanics or phases and is pulled forward by a
concrete current consumer.

Examples:

- Equipment & Inventory;
- Character Progression;
- Event History & Replay;
- other Roadmap-defined cross-cutting tracks.

### engineering

Tooling, packaging, CI, test infrastructure, repository quality, typing, or
other engineering work that does not define gameplay behavior.

### documentation

Documentation work whose primary deliverable is documentation consistency,
navigation, status, or process guidance.

### architecture

A focused unresolved contract/design question whose deliverable is a decision
or canonical clarification rather than implementation.

Groups are navigation labels only.

They do not determine:

- priority;
- dependencies;
- readiness;
- execution order;
- canonical authority.

Exact project placement belongs in `Roadmap target`.

---

## 9. Roadmap target

Every `Ready` or `Current` task must identify the Roadmap scope it advances.

Examples:

```text
Roadmap target: Phase 3 / Weapon attacks
```

```text
Roadmap target:
Cross-cutting prerequisite for Phase 3 / Weapon attacks
```

A `Current` task must never have:

```text
Roadmap target: —
```

This is the primary guard against accidental scope creep.

A task may originate from `DEFERRED.md`, an audit, or a planning discussion, but
it must still identify why it is allowed to execute now under the Roadmap.

---

## 10. Current position

- **Active Roadmap phase:** Phase 3 — Combat
- **Current:** —
- **Next:** —
- **Hard blockers:** —
- **Next free ID:** TSK-0001
- **Last reviewed:** —

`Active Roadmap phase` mirrors `ROADMAP.md`.

If they disagree, `ROADMAP.md` wins and the tracker must be reconciled.

`Current` contains zero or one task.

`Next` contains at most five `Ready` tasks in deliberate execution order.

Example:

```text
Current: TSK-0042
Next: TSK-0043 → TSK-0046 → TSK-0048
```

`Hard blockers` contains only blockers that affect the current execution
frontier. It is not a copy of every blocked task.

---

## 11. Open task index

The index owns compact metadata for live tasks.

| ID | Status | P | Size | Group | Roadmap target | Title |
| --- | --- | --- | --- | --- | --- | --- |
| `TSK-XXXX` | `Current` | `P1` | `S` | `mechanics` | Phase 3 / ... | ... |
| `TSK-XXXX` | `Ready` | `P1` | `M` | `mechanics` | Phase 3 / ... | ... |
| `TSK-XXXX` | `Blocked` | `P1` | `S` | `cross-cutting` | Phase 3 / ... | ... |
| `TSK-XXXX` | `Backlog` | `P2` | `L` | `mechanics` | Phase 3 / ... | ... |

The table is an index, not a second queue.

Execution order is defined only by:

```text
Current
Next
```

Do not infer execution order from table position.

---

## 12. Readiness gate

A task may become `Ready` only when all relevant conditions below are true:

1. It belongs to current Roadmap scope or is an explicit prerequisite for it.
2. All tasks in `Depends on` are `Done`.
3. No unresolved blocker or canonical conflict prevents execution.
4. `Goal`, `Scope`, `Out of scope`, `Acceptance criteria`, and `Verification`
   are concrete enough for implementation and review.
5. Size is `S` or `M`.
6. The result is independently mergeable as one coherent slice.

If implementation would require an unapproved architectural decision, the
implementation task is not `Ready`.

A task whose actual deliverable is to resolve that decision may itself become
`Ready` as an `architecture` task.

Do not use readiness as an excuse to fully design distant backlog work.

---

## 13. Dependencies and references

`Depends on` is the only task-to-task dependency relation.

It contains only `TSK-*` IDs.

Example:

```text
Depends on:
- TSK-0041
- TSK-0042
```

Do not manually maintain reverse fields such as:

```text
Blocks
Unlocks
Required by
```

They are derived from `Depends on`.

Rules:

1. Task dependencies reference only `TSK-*`.
2. A task never depends on a group.
3. A task never depends directly on a `DEF-*`.
4. An Architecture section is not a task dependency.
5. A Decision ID is not a task dependency.
6. Dependency cycles are forbidden.
7. A `Ready` or `Current` task must have all hard task dependencies `Done`.

`DEF-*`, Architecture sections, Decisions, audits, and Roadmap entries belong
under `References`.

Example:

```text
References:
- ROADMAP Phase 3 / Weapon attacks
- ARCHITECTURE §...
- DEF-0011

Depends on:
- TSK-0041
```

This preserves the distinction:

```text
DEF = concern / continuation context
TSK = executable delivery work
```

A `DEF-*` concern may lead to one task, several tasks, or no task until a real
consumer reaches it.

---

## 14. Contract impact

Use one compact field:

```text
Contract impact: none
```

or:

```text
Contract impact: Architecture §X.Y update
```

or:

```text
Contract impact: decision required before implementation
```

Do not reproduce the proposed canonical contract in this field.

Canonical behavior belongs in `ARCHITECTURE.md`.

If a task changes an accepted architectural contract, the repository rules in
`AGENTS.md` still apply, including the required documentation and Decision
updates.

If a task is itself intended to resolve an architectural question, state that
question in its `Goal` and keep the task in the `architecture` group.

---

## 15. Task details

Full detail is required for:

```text
Current
Ready
Blocked
```

Distant `Backlog` tasks normally need only their row in the open-task index.

Do not fully design future Commands, Events, abstractions, schemas, storage
contracts, or APIs merely to make backlog records appear complete.

Use this structure:

## TSK-XXXX — <title>

**Status:** `Ready`

**Priority:** `P1`

**Size:** `S`

**Group:** `mechanics`

**Roadmap target:** Phase 3 / ...

**References:**

- `ROADMAP.md` — Phase ... / ...
- `ARCHITECTURE.md` §..., when relevant
- `DEF-XXXX`, when relevant
- `DEC-XXXX`, when relevant
- reviewed audit/finding, when relevant

**Depends on:** `TSK-XXXX` or `—`

**Contract impact:** `none`

### Goal

State one concrete delivery result.

The Goal should answer:

> What must exist after this task is delivered?

Do not write an architectural essay.

### Why now

Explain why this task is correctly positioned relative to other eligible work.

Typical reasons:

- closes a current Roadmap frontier;
- unblocks the next vertical slice;
- provides a concrete consumer for an existing foundation;
- resolves a correctness/canonical blocker;
- closes already-known partial scope;
- avoids premature abstraction by following the next real consumer.

Keep this short.

### Scope

Explicitly include:

- behavior/change delivered by this task;
- affected modules/contracts;
- required tests;
- required documentation directly caused by the change;
- compatibility/migration work if the current contract requires it.

Do not restate whole Architecture sections.

### Out of scope

Name nearby work that must not be pulled into the slice.

This is especially important for:

- future Roadmap mechanics;
- broader `DEF-*` concerns;
- generic frameworks;
- speculative abstractions;
- unrelated refactoring;
- unrelated documentation cleanup;
- production infrastructure not required by the current phase.

### Acceptance criteria

Use objective, reviewable completion conditions.

Good criteria describe observable results such as:

- a specific Command/Result/Event path exists;
- a defined state transition is persisted;
- a concrete error is returned for a named invalid case;
- the real adapter round-trip succeeds;
- a canonical invariant remains true;
- relevant deterministic tests pass.

Acceptance criteria must describe already-approved behavior.

They must not silently create new canonical rules.

If a criterion requires a new architecture contract, change `Contract impact`
and resolve the contract first.

### Verification

List only task-specific verification beyond the global `AGENTS.md` Definition
of Done.

Examples:

- narrow deterministic resolver tests;
- handler/application tests;
- real filesystem round-trip;
- serializer backward-compatibility test;
- packaged Definition lookup;
- explicit regression for an architecture invariant.

Do not copy the full global test/DoD checklist into every task.

### Expected touchpoints

Optional planning aid.

Examples:

```text
src/dnd_engine/domain/...
src/dnd_engine/application/...
src/dnd_engine/infrastructure/...
tests/...
docs/...
```

This is not a contract. The actual file list may change when current repository
structure requires it.

### Execution checkpoints

Optional.

Use only when one mergeable task benefits from staged review.

Example:

1. Domain contract / pure resolver
2. Application orchestration
3. real-adapter integration
4. documentation and regression pass

Checkpoints are not independent task statuses and do not receive separate
`TSK-*` IDs unless they become independently mergeable slices.

### Evidence / trigger

Optional.

Use only when execution legitimately depends on concrete consumer evidence or a
known trigger.

Examples:

```text
Evidence / trigger:
Second real production consumer required before extracting a shared abstraction.
```

```text
Evidence / trigger:
Durable Event reader becomes a current production requirement.
```

Do not add this field mechanically to ordinary tasks.

### Blocker

Include only while `Status: Blocked`.

```text
Blocker: <exact blocker>
Unblock condition: <observable condition>
```

---

## 16. Queue selection

When selecting `Current` and recalculating `Next`, use these principles in
order:

1. Stay inside current Roadmap scope and obey explicit Roadmap dependencies.
2. Exclude blocked tasks and tasks with unfinished dependencies.
3. Exclude implementation work that requires an unresolved architectural decision.
4. Resolve correctness or canonical blockers before building on them.
5. Prefer work that unblocks the nearest concrete vertical slice.
6. Prefer completing an existing concrete consumer over starting unrelated scope.
7. Prefer work that gives a real consumer to an existing foundation.
8. Prefer existing narrow contracts over speculative shared abstractions.
9. Prefer closing known partial scope over inventing unrelated new scope.
10. Prefer the smallest coherent reviewable slice when several options are
    otherwise equivalent.

Do not mechanically sort the queue by priority alone.

`Why now` records any sequencing choice that is not obvious from Roadmap scope
or dependencies.

`Next` should be curated, not generated as a full project backlog.

---

## 17. Current and Next invariants

1. At most one task may have status `Current`.
2. When executable current-phase work exists, normally exactly one task should
   be `Current`.
3. `Current position.Current` must reference the single `Current` task.
4. `Next` contains at most five tasks.
5. Every task in `Next` must have status `Ready`.
6. `Next` order is the authoritative short-term execution order.
7. Priority is an input to sequencing, not sequencing itself.
8. `Depends on` is the only task-to-task dependency relation.
9. Dependency cycles are forbidden.
10. A task with unfinished dependencies cannot be `Ready` or `Current`.
11. A size `L` task cannot be `Ready` or `Current`.
12. Every `Ready` or `Current` task must identify a current Roadmap target or
    explicit prerequisite for it.
13. `Done` means both the accepted result and the corresponding Task
    Closure exist on `main` (§4.5).
14. `TASK.md` must not introduce or silently change canonical behavior.

See §18 for the mandatory Task Closure reconciliation step — normally
prepared before merge in the same delivery branch/PR, with post-merge
reconciliation as a fallback.

---

## 18. Task closure and history

Task Closure is mandatory delivery reconciliation, not optional bookkeeping.
It is normally prepared after implementation acceptance and before merge,
becoming authoritative once the delivery PR lands on `main`; post-merge
reconciliation remains a mandatory fallback for the exceptional case where
closure was not prepared in time. Closure does not receive its own `TSK-*`
either way.

The closure procedure itself, performed either pre-merge (§18.1, normal) or
post-merge (§18.2, fallback):

1. mark the completed task `Done`;
2. add it to `Recently completed`;
3. remove its full detail from `Open task details`;
4. append the required factual development entry with its `TSK-*` ID to
   `DEVELOPMENT_LOG.md`;
5. reconcile Roadmap/Deferred status if the delivered work changes them;
6. select the next `Current`;
7. recalculate `Next` and `Hard blockers`;
8. update `Next free ID` and `Last reviewed` — `Next free ID` changes only
   when allocation state actually changed, not on every closure.

### 18.1 Normal path — closure prepared before merge

Preparing Task Closure in the same delivery branch/PR as the implementation
is allowed once all of the following hold:

- the task's implementation is complete;
- relevant tests/checks have passed;
- the implementation diff has been reviewed/accepted;
- the delivery PR already exists, so its PR number is already known and
  usable as `Recently completed` evidence (§19) — do not invent a
  placeholder merge SHA to fill that field early;
- the closure edit lives in that same delivery branch/PR;
- implementation and closure are intended for one atomic merge.

```text
Current
→ implementation/review
→ prepared Task Closure in the same delivery branch/PR
→ review closure diff + revalidate current origin/main
→ one merge lands implementation + closure together
→ authoritative Done on main
→ next Current may begin implementation
```

Prepared closure is **prospective** until merge (§4.5): the `Done` status,
`Recently completed` row, next-`Current` selection, and updated `Current
position` written on the branch describe what `TASK.md` will become true if
and when that exact PR merges. Before merge, `main` remains authoritative,
the task is not actually finished, and no implementation may begin against
the branch's prospective next `Current`.

The closure diff itself must be reviewed before merge, exactly like the
implementation diff — it is not exempt from review merely because it is
tracker bookkeeping. As part of that review, before the final merge,
re-check that `origin/main` has not materially changed Current/Next
ordering, Roadmap scope, blockers, or any other fact the prepared closure
depends on. If it has, the prepared closure is stale and must be
reconciled against current `origin/main` before merging.

### 18.2 Fallback path — post-merge reconciliation

If a task's accepted result lands on `main` without a prepared closure — by
mistake, or for an exceptional reason — reconciliation remains mandatory:
perform the same closure procedure above, starting from current
`origin/main`, through the normal branch/review/authorization workflow
`AGENTS.md` establishes for any other change. This section does not
authorize a direct commit or other substantive work on `main`; the
reconciliation itself is prepared on a dedicated branch and reviewed/merged
like any other change. Implementation of the next `Current` task must not
begin until the tracker is reconciled.

```text
accepted result on main without prepared closure
→ branch from current origin/main (normal AGENTS.md workflow)
→ close/reconcile that task in TASK.md
→ select/reconcile Current + Next + blockers
→ review + merge the reconciliation
→ only then begin implementation of the next task
```

An implementation PR must not assert its task as authoritatively `Done`
before its accepted result exists on `main` (§4.5); a prepared pre-merge
closure is prospective, not an assertion of present fact. Task Closure —
prepared pre-merge or performed post-merge as fallback — is part of the
project workflow, not a new gameplay delivery task.

Only the ten most recent completed tasks stay in this file.

Durable history belongs to:

```text
Git history
pull requests
DEVELOPMENT_LOG.md
ARCHITECTURE.md / DECISIONS.md where contracts changed
```

Do not preserve full completed task records indefinitely.

---

## 19. Recently completed

Last ten completions only.

| ID | Title | Evidence |
| --- | --- | --- |
| `TSK-XXXX` | ... | PR #... |

`PR #123` alone is sufficient durable evidence. Task Closure is normally
prepared after the delivery PR already exists and its implementation has
been accepted (§18.1), so the PR number is already known at that point; a
merge commit SHA is not required and no placeholder merge SHA should be
written. Once merged, the merge commit SHA may be added as optional
enrichment, but doing so is not required and never justifies a second
post-merge edit on its own:

```text
PR #123 / merge commit abcdef1
```

If no pull request was used:

```text
commit abcdef1 on main
```

`DEVELOPMENT_LOG.md` remains the durable human-readable history of development
iterations.

---

## 20. Review triggers

Review and reconcile `TASK.md`:

- before merging a `Current` task's delivery PR, so Task Closure can be
  prepared in that same PR (§18.1); or, as fallback, immediately after an
  already-merged task is found unreconciled, before implementation of the
  next task begins (§18.2);
- when Roadmap scope/status materially changes;
- when a relevant Deferred concern changes state;
- when a blocker or prerequisite changes;
- when a new accepted correctness/canonical blocker appears;
- when the user explicitly changes project priority;
- when the project moves to another Roadmap phase;
- on explicit task-review request.

During review:

1. reconcile task statuses with `main`;
2. re-check dependencies and blockers;
3. re-check whether `Ready` tasks still satisfy the readiness gate;
4. select or confirm `Current`;
5. rebuild `Next`;
6. update `Hard blockers`;
7. update `Next free ID`;
8. update `Last reviewed`.

Task Closure is normally prepared in the same delivery PR that lands the
implementation (§18.1), so reconciliation normally lands in the very merge
that delivers the task; that pre-merge preparation is prospective, not
false, because it only becomes authoritative once the PR actually merges
(§4.5). When closure was not prepared before merge, reconciliation is still
mandatory as a fallback (§18.2) before implementation of the next task
begins. A task merge must never leave `TASK.md` pointing indefinitely at an
already-completed task as `Current`.

Do not churn the queue after every commit or minor implementation detail.

---

## 21. Progressive elaboration

Do not fully specify distant work prematurely.

Expected progression:

```text
Backlog
   ↓ approaches current frontier
refinement / decomposition
   ↓
Ready
   ↓
Next
   ↓
Current
   ↓
Done
```

A distant backlog entry may remain as small as:

```text
| TSK-0087 | Backlog | P2 | L | mechanics | Phase 3 / Reactions | Opportunity attack continuation |
```

Do not pre-invent:

- Commands;
- Events;
- abstractions;
- modifier systems;
- storage contracts;
- APIs;
- data-model fields;

until the task approaches a real consumer and the repository provides enough
evidence to refine it safely.

---

## 22. Initial population policy

Do not populate `TASK.md` by mechanically converting every unchecked Roadmap
item and every open `DEF-*` concern into fully specified tasks.

Initial adoption should:

1. inspect current `ROADMAP.md`;
2. inspect relevant `DEFERRED.md` concerns;
3. inspect current Architecture and implementation evidence;
4. identify the current execution frontier;
5. create one `Current` task when executable work exists;
6. create up to five `Ready` tasks in `Next`;
7. add only a small number of justified near-frontier `Backlog` entries;
8. leave distant scope in Roadmap/Deferred until it approaches execution.

A good initial state looks like:

```text
Phase 3 — Combat
    ↓
TSK-00XX Current
    ↓
TSK-00YY Ready
    ↓
TSK-00ZZ Ready
```

not a speculative task inventory of the entire future D&D ruleset.

---

## 23. Operational principles

Keep `TASK.md` a thin planning layer.

Prefer:

- one authoritative field per concept;
- stable IDs;
- one current task;
- short queue horizon;
- mergeable delivery slices;
- explicit scope boundaries;
- repository-backed `Done`;
- progressive elaboration;
- concrete consumer evidence before abstraction;
- explicit reasons for non-obvious sequencing.

Avoid:

- duplicate Roadmap status;
- duplicate Architecture contracts;
- duplicate dependency directions;
- hour estimates;
- branch-state simulation in `main`;
- speculative future design;
- copying global `AGENTS.md` workflow into each task;
- turning every checkpoint into a separate `TSK-*`;
- converting every `DEF-*` into executable work prematurely;
- using priority as a substitute for sequencing judgment;
- creating generic abstractions only because several files contain similar code.

The intended model is:

```text
ARCHITECTURE tells us what the system is allowed to mean.

ROADMAP tells us where the project is going
and what capability scope is currently open.

TASK tells us which concrete reviewable slice goes next.

DEFERRED tells us what known broader concerns remain outside
the implemented slice.

DEVELOPMENT_LOG and Git tell us what actually happened.
```

---

# Current position

- **Active Roadmap phase:** Phase 3 — Combat
- **Current:** TSK-0017
- **Next:** —
- **Hard blockers:** —
- **Next free ID:** TSK-0018
- **Last reviewed:** 2026-09-11

---

# Open task index

| ID | Status | P | Size | Group | Roadmap target | Title |
| --- | --- | --- | --- | --- | --- | --- |
| `TSK-0017` | `Current` | `P1` | `M` | `mechanics` | Phase 3 / Zero-HP and combatant eligibility | Implement minimal Character Death Save vertical slice |

---

# Open task details

## TSK-0017 — Implement minimal Character Death Save vertical slice

**Status:** `Current`

**Priority:** `P1`

**Size:** `M`

**Group:** `mechanics`

**Roadmap target:** Phase 3 / Zero-HP and combatant eligibility

**References:**

- `ROADMAP.md` — Phase 3 / Zero-HP and combatant eligibility
- `ARCHITECTURE.md` §3.25
- `ARCHITECTURE.md` §3.31
- `ARCHITECTURE.md` §3.34
- `DEFERRED.md` — `DEF-0005`
- `DEFERRED.md` — `DEF-0015`
- `DEC-0050`

**Depends on:** `TSK-0016`

**Contract impact:** `none`

### Goal

Implement the canonical minimal Character zero-HP turn / Death Save
contract defined by `ARCHITECTURE.md` §3.34 (DEC-0050) through
deterministic Domain/Application/Event/State/persistence behavior and
automated tests.

TSK-0017 must implement the already-fixed semantic/Event/State/schema
contracts §3.34 defines — no external `DeathSaveCommand`, the automatic
`CombatStarted`/`TurnAdvanced` trigger, `CharacterDeathSaveResult`,
`CharacterDeathSaveFailureResult`, `CharacterDeathSaveResolved` V1,
`CharacterDeathSaveFailureRecorded` V1, the Character lifecycle State
facts, and the target State schema V9 Character wire fields/compatibility
semantics — rather than redefine them. Exact Python module placement,
concrete helper/function names, and other implementation details §3.34
deliberately does not fix remain for the TSK-0017 implementation pass.

### Why now

TSK-0016 has completed the architectural prerequisite. `ARCHITECTURE.md`
§3.34 and DEC-0050 now fully fix the mechanic, Event, State, and schema
semantics, making TSK-0017 the next concrete Phase 3 vertical slice. No new
architectural decision is required before implementation starts.

### Scope

- Extend `CharacterState` with `death_save_successes`,
  `death_save_failures`, `death_save_stable`, and `dead`, enforcing all
  canonical intrinsic invariants from §3.34: exact non-boolean integer ranges
  `0..2` and `0..3`, exact booleans, stable/dead mutual exclusion, stable
  implying reset counters, and three failures implying dead.
- Enforce the §3.34 `StateSnapshot` Character↔Creature relational lifecycle
  invariants: stable or dead implies zero HP; positive HP implies reset
  counters and both lifecycle flags false.
- Implement exact State schema V9 persistence for the four Character wire
  fields, canonical `0`/`0`/`False`/`False` defaults when reading V1–V8,
  strict V9 read/write, and no retroactive widening of legacy wire schemas.
- Add the pure Domain `CharacterDeathSaveResult` and
  `CharacterDeathSaveFailureResult`, normal-d20 Death Save resolution, and
  Damage-at-zero failure resolution.
- Add `CharacterDeathSaveResolved` V1 and
  `CharacterDeathSaveFailureRecorded` V1 with concrete builders and appliers.
- Orchestrate the automatic Death Save after `CombatStarted` or
  `TurnAdvanced` establishes a new active creature; natural-20 recovery via
  unchanged `HealingApplied` V1; ordinary-Healing lifecycle reset and
  rejection for a dead Character; and Damage-at-zero consequences for both
  direct `ApplyDamageCommand` and existing Attack-origin Damage paths.
- For every successful root Command transaction that mutates authoritative
  State as part of this slice, perform exactly one final `StateStore.save()`
  after all in-memory consequences are assembled; preserve existing no-save
  behavior for successful read-only branches.
- Keep existing root Command outcome types and public Command contracts
  unchanged.

### Out of scope

- `DeathSaveCommand` or any other external Death Save intent.
- Monster Death Saves.
- Monster death or lifecycle policy.
- A universal `LifeState`.
- A generic unconscious/dead hierarchy.
- Broader zero-HP targetability.
- Combat removal.
- Automatic turn skipping.
- `CombatEnded`.
- Medicine or external stabilization.
- Stable 1d4-hour recovery.
- Resurrection or revivification.
- Temporary HP.
- Massive-damage or instant-death rules.
- Movement.
- Reactions.
- Opportunity Attacks.
- Character Dagger → Character targetability expansion.
- A generic lifecycle framework.
- A generic consequence pipeline.
- A generic State mutation framework.
- `UnitOfWork`, `TransactionManager`, or `WorkingState`.
- An Event dispatcher or registry.
- A generic `DamageSource`/`CriticalDamage` abstraction.

### Acceptance criteria

- `CharacterState` contains all four lifecycle fields and enforces every
  intrinsic §3.34 invariant; `StateSnapshot` enforces every corresponding
  Character↔Creature relational invariant.
- State schema V9 reads and writes the four Character fields exactly, rejects
  invalid V9 State, reads V1–V8 with canonical `0`/`0`/`False`/`False`
  defaults, and does not accept V9-only fields in legacy schemas.
- A newly active eligible Character receives exactly one automatic normal-d20
  Death Save. No Death Save die is rolled for a Monster, positive-HP
  Character, stable Character, or dead Character.
- Death Save rolls resolve exactly as §3.34 defines: natural 1 records two
  failures capped at three; 2..9 records one failure; 10..19 records one
  success; natural 20 signals one HP of recovery without an ordinary success
  increment.
- A third success stabilizes the Character and resets both counters; a third
  failure kills the Character and leaves stabilization false.
- Natural 20 emits `CharacterDeathSaveResolved` followed by unchanged
  `HealingApplied` V1, changes HP from 0 to 1, resets Death Save progression,
  and does not spend the Character's Action.
- Positive direct Damage against a living Character already at zero HP records
  one failure. Ordinary Attack-origin Damage at zero records one failure, and
  critical Attack-origin Damage at zero records two failures. Positive-HP →
  zero-HP Damage alone records no Death Save failure.
- Ordinary Healing from zero to positive HP resets both counters and
  stabilization. Ordinary Healing against a dead Character returns
  `INVALID_TARGET` before resolution, Event metadata allocation, or save.
- `TurnActionSpent` remains the final Event for every successful in-Combat
  Attack transaction; its existing `causedBy` remains the Attack-resolution
  Event and is not repointed to `DamageApplied` or
  `CharacterDeathSaveFailureRecorded`. When
  `CharacterDeathSaveFailureRecorded` is emitted, its `causedBy` equals the
  originating `DamageApplied.eventId`.
- Every successful State-mutating root Command transaction affected by this
  slice performs exactly one final `StateStore.save()` after all in-memory
  consequences are assembled; successful read-only branches preserve their
  existing no-save behavior, and no intermediate save occurs.
- Root `ResolutionResult.outcome` types and public Command contracts remain
  unchanged.
- No generic lifecycle, consequence, or State-mutation framework is
  introduced.

### Verification

- Focused deterministic Domain tests for lifecycle invariants, both Results,
  both resolvers, and both Event builders/appliers.
- Focused Application tests for turn-start eligibility, roll outcomes,
  event ordering/causation, Damage/Healing interactions, rejection
  precedence, root outcomes, and single-save atomicity.
- State serializer/store tests for exact V9 persistence, strict validation,
  and V1–V8 compatibility defaults.
- Attack regression tests, including Damage-at-zero critical provenance and
  the final-`TurnActionSpent` invariant.
- Representative integration/real-adapter tests proving V9 persistence and
  selected end-to-end Death Save/HP lifecycle paths; combinatorial mechanic
  behavior remains covered by focused Domain/Application tests.
- Full `python -m pytest`.
- `python -m mypy src/dnd_engine`.
- `git diff --check`.

### Expected touchpoints

- `CharacterState` / `StateSnapshot`.
- `StateSerializer`.
- New concrete Death Save rule and Event modules.
- `StartCombatHandler` / `AdvanceTurnHandler`.
- `DamageHandler` / `HealingHandler` / `AttackHandler`.
- The existing snapshot replacement service, only if actual duplication
  justifies its reuse or narrow extension.
- Domain, Application, Infrastructure, Integration, and Attack regression
  tests.
- Final factual documentation synchronization.

### Execution checkpoints

1. State + V9 persistence.
2. Pure Domain Results/rules/Events.
3. Turn-start Death Save + natural-20 Healing.
4. Damage/Healing/Attack lifecycle interactions.
5. Integration/regression/documentation.

---

# Recently completed

| ID | Title | Evidence |
| --- | --- | --- |
| `TSK-0006` | Implement active-turn Attack gating | PR #75 / merge commit `d590056` |
| `TSK-0007` | Implement zero-HP Attack eligibility | PR #77 / merge commit `7798ed7` |
| `TSK-0004` | Implement the approved minimal Character weapon source and persistence | PR #80 / merge commit `d1b23de` |
| `TSK-0010` | Implement Combat-owned positioning and State schema V7 | PR #83 |
| `TSK-0011` | Define exact Character Dagger Attack and Damage contracts | PR #84 |
| `TSK-0012` | Implement Character Dagger weapon Attack resolution | PR #85 |
| `TSK-0013` | Implement Character Dagger Attack → Damage → Monster HP consequence | PR #86 |
| `TSK-0014` | Define the minimal ordinary-Action resource contract for existing `AttackCommand` consumers | PR #88 |
| `TSK-0015` | Implement minimal current-turn Action expenditure for existing `AttackCommand` consumers | PR #89 |
| `TSK-0016` | Define minimal Character zero-HP turn and Death Save contract | PR #91 |

---

# Appendix A — detailed task template

```markdown
## TSK-XXXX — <Title>

**Status:** `Ready`

**Priority:** `P1`

**Size:** `S`

**Group:** `mechanics`

**Roadmap target:** Phase ... / ...

**References:**

- `ROADMAP.md` — Phase ... / ...
- `ARCHITECTURE.md` §...
- `DEF-XXXX`
- `DEC-XXXX`

**Depends on:** —

**Contract impact:** `none`

### Goal

...

### Why now

...

### Scope

- ...

### Out of scope

- ...

### Acceptance criteria

- ...

### Verification

- ...

### Expected touchpoints

Optional.

- `src/dnd_engine/...`
- `tests/...`
- `docs/...`

### Execution checkpoints

Optional.

1. ...
2. ...

### Evidence / trigger

Optional.

...

### Blocker

Only when `Status: Blocked`.

Blocker: ...
Unblock condition: ...
```

---

# Appendix B — compact backlog example

```markdown
| ID | Status | P | Size | Group | Roadmap target | Title |
| --- | --- | --- | --- | --- | --- | --- |
| `TSK-0087` | `Backlog` | `P2` | `L` | `mechanics` | Phase 3 / Reactions | Opportunity attack continuation |
```

No detailed section is required until the task approaches the execution
frontier.
