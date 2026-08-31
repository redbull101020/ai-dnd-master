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

A task becomes `Done` only when its accepted result exists on `main`.

The following are not sufficient:

- code was written;
- local tests passed;
- `review.patch` was reviewed;
- a commit exists;
- the branch was pushed;
- a pull request exists;
- review approved the pull request.

Until the accepted result is present on `main`, the task remains open.

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
13. `Done` means the accepted result exists on `main`.
14. `TASK.md` must not introduce or silently change canonical behavior.

---

## 18. Completion and history

When a task's accepted result lands on `main`:

1. mark it `Done`;
2. add it to `Recently completed`;
3. remove its full detail from `Open task details`;
4. append the required factual development entry with its `TSK-*` ID to
   `DEVELOPMENT_LOG.md`;
5. reconcile Roadmap/Deferred status if the delivered work changes them;
6. select the next `Current`;
7. recalculate `Next`;
8. update `Next free ID` and `Last reviewed`.

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
| `TSK-XXXX` | ... | PR #... / merge commit ... |

Preferred evidence:

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

- after a task is merged;
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
- **Current:** TSK-0001
- **Next:** TSK-0008 → TSK-0003
- **Hard blockers:** —
- **Next free ID:** TSK-0009
- **Last reviewed:** 2026-08-31

---

# Open task index

| ID | Status | P | Size | Group | Roadmap target | Title |
| --- | --- | --- | --- | --- | --- | --- |
| `TSK-0001` | `Current` | `P1` | `M` | `architecture` | Cross-cutting prerequisite for Phase 3 / Weapon attacks and Attack consequences | Define the minimal authoritative Character weapon source |
| `TSK-0003` | `Ready` | `P1` | `M` | `architecture` | Phase 3 / Zero-HP and combatant eligibility | Define zero-HP Attack eligibility by creature category |
| `TSK-0004` | `Backlog` | `P1` | `L` | `cross-cutting` | Cross-cutting prerequisite for Phase 3 / Weapon attacks | Implement the approved minimal Character weapon source and persistence |
| `TSK-0005` | `Backlog` | `P1` | `L` | `mechanics` | Phase 3 / Weapon attacks and Attack consequences | Implement the Character Dagger Attack → Damage → Monster HP continuation |
| `TSK-0006` | `Backlog` | `P1` | `M` | `mechanics` | Phase 3 / Turn/action economy | Implement active-turn Attack gating |
| `TSK-0007` | `Backlog` | `P1` | `L` | `mechanics` | Phase 3 / Zero-HP and combatant eligibility | Implement zero-HP Attack eligibility |
| `TSK-0008` | `Ready` | `P1` | `M` | `architecture` | Phase 3 / Targeting and Weapon attacks | Define minimal melee targeting and reach for the first Character Dagger attack |

---

# Open task details

## TSK-0001 — Define the minimal authoritative Character weapon source

**Status:** `Current`

**Priority:** `P1`

**Size:** `M`

**Group:** `architecture`

**Roadmap target:** Cross-cutting prerequisite for Phase 3 / Weapon attacks and
Attack consequences

**References:**

- `ROADMAP.md` — Phase 3 / Weapon attacks and Attack consequences; Equipment &
  Inventory cross-cutting continuation
- `ARCHITECTURE.md` §§3.1.1, 3.17, 3.27, 3.29, 10.5, 10.6, 12.12
- `DEF-0009`, `DEF-0011`, `DEF-0013`
- `DEC-0030`, `DEC-0031`, `DEC-0041`, `DEC-0042`, `DEC-0044`

**Depends on:** `—`

**Contract impact:** Defines the canonical Character weapon-source foundation
in Architecture §3.29 and DEC-0044; production implementation remains the
separate subsequent `TSK-0004` task

### Goal

Establish Architecture §3.29 and DEC-0044 as the accepted minimal canonical
authoritative weapon-source contract for the future Character Dagger consumer,
while preserving the existing ownership and staged resolution boundaries and
leaving production implementation to a separate subsequent task.

### Why now

G9 closes the narrow Goblin Scimitar consequence path and repeatedly identifies
the Character Weapon continuation as its remaining adjacent frontier. The
packaged Dagger and Attack/Damage foundations already exist, but implementation
cannot start until the minimum `InventoryState` / `EquipmentState` facts,
weapon proficiency, and the explicit Finesse choice are canonical.

### Scope

- define in Architecture §3.29 the minimum authoritative runtime
  Inventory/Equipment facts, Character weapon-proficiency membership, and
  explicit Strength/Dexterity Dagger Finesse intent required by the first
  Character weapon consumer;
- record the rationale and consequences in DEC-0044 without duplicating the
  full canonical contract in this planning layer;
- establish the State schema V6 compatibility, validation, failure, ownership,
  and staged Attack→Damage implementation boundaries required for the later
  production task;
- reconcile only documentation directly affected by the accepted contract.

### Out of scope

- production or test implementation;
- broad inventory management, containers, currency, encumbrance, loot, or a
  generic item-instance framework;
- armor/shield AC, dual wielding, thrown/ranged attacks, ammunition, or action
  economy;
- targeting, distance, and reach legality; these remain separate prerequisites
  for the eventual Dagger Attack implementation;
- generic attack-source, modifier, equipment-slot, or Event orchestration
  abstractions;
- changing the implemented Goblin Scimitar path.

### Acceptance criteria

- Architecture §3.29 and DEC-0044 identify every authoritative weapon-source
  input needed by the future Character Dagger consumer and its owning State or
  Definition source;
- weapon proficiency and the Finesse choice have explicit, non-derived sources
  without embedding computed attack bonuses in the Command;
- State schema V6 impact, compatibility policy, validation order, failure
  boundaries, and the later production implementation boundary are explicit;
- the accepted contract does not silently add ranged, armor,
  inventory-management, or generic-framework scope;
- all directly affected planning and deferred-scope references agree with
  Architecture §3.29, DEC-0044, Roadmap, and the still-deferred broader
  `DEF-*` concerns;
- production implementation remains a separate subsequent task and is not
  claimed by this architecture-only result.

### Verification

- documentation-reference tests;
- targeted reference/anchor search for the changed contracts and Decision;
- consistency review against the existing Character unarmed, Monster
  Scimitar, packaged Dagger, State ownership, and serialization contracts.

### Expected touchpoints

```text
docs/ARCHITECTURE.md
docs/DECISIONS.md
docs/DEFERRED.md
docs/ROADMAP.md
docs/TASK.md
docs/DEVELOPMENT_LOG.md
CLAUDE.md (only if a reproduced canonical fact changes)
```

---

## TSK-0003 — Define zero-HP Attack eligibility by creature category

**Status:** `Ready`

**Priority:** `P1`

**Size:** `M`

**Group:** `architecture`

**Roadmap target:** Phase 3 / Zero-HP and combatant eligibility

**References:**

- `ROADMAP.md` — Phase 3 / Zero-HP and combatant eligibility
- `ARCHITECTURE.md` §§3.19, 3.20, 3.25, 3.27, 3.28
- `DEF-0005`, `DEF-0015`
- `DEC-0033`, `DEC-0034`, `DEC-0040`, `DEC-0042`, `DEC-0043`

**Depends on:** `TSK-0002`

**Contract impact:** Architecture update and new Decision required before
implementation

### Goal

Define separately whether a Character or Monster at authoritative
`current_hp == 0` may use the existing `AttackCommand`, and define the narrow
validation relationship between zero-HP eligibility and the canonical
active-turn gate established by `TSK-0002`, without predesigning the broader
life-state, death-save, or action-economy system.

### Why now

The implemented Monster consequence path can now reduce a real target to zero
HP, while Attack and turn advancement are concrete Phase 3 consumers. That is
the evidence trigger `DEF-0015` required for a narrow eligibility decision.

The decision must follow the active-turn contract rather than independently
inventing a second Attack eligibility boundary whose failure precedence would
otherwise remain undefined.

### Scope

- decide Character and Monster zero-HP Attack eligibility separately;
- determine whether existing `current_hp` is sufficient for this gate or a
  narrower category-specific fact is demonstrably required;
- define the relative validation boundary between the active-turn gate
  established by `TSK-0002` and zero-HP Attack eligibility;
- define failure semantics before dice, Event metadata, State mutation, or
  persistence;
- clarify the unchanged boundary with the rule that a zero-HP combatant's turn
  may still be advanced;
- preserve the current arithmetic Damage/Healing contracts and their valid
  zero-HP transitions;
- update the canonical Architecture, append one Decision, and reconcile
  directly affected Roadmap/Deferred/summary documentation.

### Out of scope

- action, bonus-action, or reaction resource budgets;
- death saves, unconscious/stable/dead counters, or a universal `LifeState`;
- stabilization, targetability, further-Damage consequences, Healing recovery
  semantics, or automatic combat ending;
- weapon-source, equipment, targeting-distance, or movement rules;
- implementation.

### Acceptance criteria

- Character and Monster Attack eligibility at zero HP is explicit and not
  conflated into an unsupported universal lifecycle model;
- the decision states whether additional authoritative State is required and
  rejects it unless this concrete consumer provides evidence;
- the interaction and deterministic failure precedence between active-turn
  eligibility and zero-HP Attack eligibility is explicit;
- rejected attacks reach neither DiceEngine nor Event metadata, State
  mutation, or persistence;
- Damage, Healing, Attack, and turn-advancement boundaries remain mutually
  consistent;
- `DEF-0005` remains deferred unless its separate death-save prerequisites are
  actually resolved.

### Verification

- documentation-reference tests;
- consistency review against the accepted `TSK-0002` active-turn contract;
- consistency review against zero-HP Damage/Healing tests, Monster lethal-
  damage tests, and turn-advancement tests.

### Expected touchpoints

```text
docs/ARCHITECTURE.md
docs/DECISIONS.md
docs/DEFERRED.md
docs/ROADMAP.md
docs/TASK.md
docs/DEVELOPMENT_LOG.md
CLAUDE.md (only if a reproduced canonical fact changes)
```

---

## TSK-0008 — Define minimal melee targeting and reach for the first Character Dagger attack

**Status:** `Ready`

**Priority:** `P1`

**Size:** `M`

**Group:** `architecture`

**Roadmap target:** Phase 3 / Targeting and Weapon attacks

**References:**

- `ROADMAP.md` — Phase 3 / Targeting, Weapon attacks, Movement
- `ARCHITECTURE.md` §§3.17, 3.25, 3.26, 3.27, 10.4, 10.7
- `P2-ATTACK-ROLLS`
- `DEF-0011`
- `DEC-0031`, `DEC-0041`, `DEC-0042`

**Depends on:** `—`

**Contract impact:** Architecture update and new Decision required before implementation

### Goal

Define the smallest authoritative targeting and spatial contract needed to
determine whether the first Character Dagger attack against a Monster is a
legal melee target, without designing the broader Movement system or a generic
targeting/geometry framework.

### Why now

The Character Dagger is now a concrete next Weapon Attack consumer.

The existing Character unarmed and Goblin Scimitar consumers prove the Attack
and consequence boundaries, while the Character weapon-source task explicitly
leaves targeting, distance, and reach as separate prerequisites.

`DEF-0011` also requires necessary targeting/distance facts and melee reach
before the broader Character Weapon attack continuation can be completed. The
consumer evidence therefore exists; this is no longer speculative spatial
architecture.

### Scope

- define the minimum authoritative facts required to decide whether the
  intended Monster target is legal for the first Character Dagger melee
  attack;
- decide whether existing State is sufficient and, if not, define only the
  minimum additional spatial State required by this consumer;
- identify the State Owner for any new authoritative spatial fact;
- define the authoritative source of the Dagger's melee reach requirement;
- define where Application obtains the required State/Definition inputs and
  where deterministic target/reach validation occurs;
- define rejection semantics before Attack dice, Event metadata, State
  mutation, or persistence;
- define any StateSnapshot serialization/version compatibility consequence if
  additional authoritative State is required;
- preserve the existing separation between target legality and attack-roll /
  damage resolution;
- update the canonical Architecture, append one Decision, and reconcile only
  directly affected planning/summary documentation.

### Out of scope

- production or test implementation;
- movement Commands, movement expenditure, creature speed, Dash, Disengage, or
  forced movement;
- grid/hex representation, pathfinding, collision, terrain, difficult terrain,
  elevation, or line-of-effect systems;
- opportunity attacks and reactions;
- ranged or thrown attacks, normal/long range, ammunition, or generic reach
  support for arbitrary weapons;
- cover and visibility;
- Character weapon ownership, proficiency, or Finesse choice covered by
  `TSK-0001`;
- action-resource budgets or zero-HP eligibility;
- retrofitting the existing Goblin Scimitar path merely to create a shared
  targeting abstraction;
- a generic `TargetingEngine`, geometry service, spatial query framework, or
  shared Attack-validation pipeline without additional concrete consumers.

### Acceptance criteria

- the first Character Dagger → Monster consumer has one explicit authoritative
  source for every fact needed to accept or reject its melee target;
- ownership of any spatial State is explicit and does not give AI, API, Attack
  resolution, or another non-owner direct mutation authority;
- Dagger melee reach is derived from authoritative Definition/State facts
  rather than caller-supplied computed legality;
- invalid target/reach attempts are rejected deterministically before
  DiceEngine, Event allocation, State mutation, or persistence;
- the contract does not require a general Movement, geometry, ranged-attack,
  or targeting framework;
- any State/serialization compatibility impact is explicit;
- the existing Character unarmed and Monster Scimitar contracts remain
  unchanged unless an actual canonical conflict is discovered and reported
  rather than silently resolved.

### Verification

- documentation-reference tests;
- consistency review against the existing `AttackCommand` / `AttackHandler`
  target boundary;
- consistency review against Creature and Combat State ownership;
- consistency review against the packaged Dagger Definition and existing
  Character-unarmed / Goblin-Scimitar Attack consumers;
- targeted reference search confirming no generic movement/targeting framework
  was made canonical accidentally.

### Expected touchpoints

```text
docs/ARCHITECTURE.md
docs/DECISIONS.md
docs/DEFERRED.md
docs/ROADMAP.md
docs/TASK.md
docs/DEVELOPMENT_LOG.md
CLAUDE.md (only if a reproduced canonical fact changes)
```

---

# Recently completed

| ID | Title | Evidence |
| --- | --- | --- |
| `TSK-0002` | Define active-turn gating for `AttackCommand` | PR #68 / merge commit `d8f86ed` |

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
