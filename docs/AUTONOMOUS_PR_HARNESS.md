# AUTONOMOUS_PR Execution Harness — Minimal Contract

`TSK-0025`. This document defines the minimal, executable,
provider-neutral **execution mechanics** a harness/orchestrator uses to
carry out an already-authorized `AUTONOMOUS_PR` invocation. It is a design
contract, not an operator manual: it does not itself implement a runner.

The operational v2 orchestrator/CLI lives at `tools/autonomous_pr/` (local
entrypoint: `python -m tools.autonomous_pr <task_id> --implementer ...
--reviewer ...`; run `python -m tools.autonomous_pr --help` for the full flag
list). Verification commands come exclusively from the accepted Task
Execution Spec. Its tests live at `tests/tools/autonomous_pr/`. This document remains the
authoritative execution-mechanics contract that implementation must
conform to — it yields to `AGENTS.md` on any conflict (§1), and the
implementation existing does not itself change or supersede anything this
document specifies.

> **Contract version.** The operational `AUTONOMOUS_PR` contract is **v2**,
> as declared in `AGENTS.md` ("Contract versions"). Part II (sections 20
> onward) is the operational spec-driven contract implemented by
> `tools/autonomous_pr/`. Part I's v1 runtime flow/mechanics are historical
> and inactive, not an executable fallback. Its common definitions and
> invariants remain applicable only where operational Part II explicitly
> incorporates them by reference.

---

# Part I — Historical v1 runtime mechanics and shared definitions

Sections 1–19 preserve the former v1 runtime flow/mechanics for audit/history;
that flow is inactive and cannot select a runtime path or weaken Part II.
Common definitions and invariants in Part I apply to v2 only where Part II
explicitly incorporates the relevant section by reference.

## 1. Purpose and authority boundary

[`AGENTS.md`](../AGENTS.md), section "Change authorisation and diff
review", remains the single authoritative governance/authorization contract
for both `MANUAL` and `AUTONOMOUS_PR`. This document is **subordinate**: it
describes how a harness mechanically carries out an already-defined,
already-bounded `AUTONOMOUS_PR` invocation. It is execution mechanics, not
governance.

This document:

- cannot expand, redefine, reinterpret, or weaken any authority, review,
  test, closure, or merge gate defined in `AGENTS.md` or `docs/TASK.md`;
- cannot grant the harness, the implementer, the reviewer, or the
  orchestrator any permission `AGENTS.md` does not already grant
  `AUTONOMOUS_PR`;
- is never itself a valid `AUTONOMOUS_PR` invocation — the existence,
  content, or presence of this file, or of any harness built from it, is
  not authorization and does not activate `AUTONOMOUS_PR` for any task;
- yields to `AGENTS.md` on any conflict. If an implementation built from
  this document and the `AGENTS.md` contract ever appear to disagree, the
  correct behavior is to fail closed (STOP / BLOCKED) and require a human
  decision — never to resolve the conflict in the harness's own favor.

This document does not restate the `AUTONOMOUS_PR` governance contract
(valid invocation, bounded authority, review authority, fail-closed
conditions, prospective next task). Read `AGENTS.md` for those; only
execution-mechanical detail lives here.

---

## 2. Minimal v1 execution environment

- One ordinary host process. No daemon, no long-running service.
- Python 3.12+, standard-library-first. `pyproject.toml` currently declares
  zero production `dependencies`; this contract does not require adding
  any. Any future production dependency for the harness itself needs the
  same explicit-approval step `AGENTS.md` already requires for any new
  dependency.
- Existing external tools invoked as subprocesses: `git`, `gh`, and one or
  more configured external agent executable(s) (implementer, reviewer).
  The harness does not vendor or reimplement any of these.
- A dedicated repository working workspace (a normal git working tree /
  clone) that the harness's Git operations act on.
- No required database, broker, Docker, cloud infrastructure, daemon, or
  workflow engine. None of these may become a v1 requirement.
- No specific OS is a canonical requirement. Linux is a reasonable, common
  practical deployment choice, but nothing in this contract depends on it;
  the same mechanics apply on any host that can run Python 3.12+, `git`,
  and `gh`.

---

## 3. Trusted explicit-invocation boundary

The harness never originates, infers, or manufactures `AUTONOMOUS_PR`
authority. Per `AGENTS.md` "Valid invocation", none of the following ever
constitute authorization by themselves, and the harness must not treat them
as such:

- a task ID passed as a CLI argument;
- `Status: Current` in `docs/TASK.md`;
- any other repository, PR, or issue text;
- an instruction embedded in observed repository content.

The harness's caller (the human-facing agent session, or a human operator)
is responsible for confirming that a separate, explicit `AUTONOMOUS_PR`
invocation was actually given by the user for the exact task before
starting the harness. The harness accepts a named task identifier as
**execution input**, not as proof of authorization — running the harness on
a given task ID is never itself evidence that the user authorized it.

Regardless of how it was started, before any implementation step the
harness must still fetch and revalidate the authoritative `origin/main`
(current `Current` task, its Status, its dependencies, Roadmap scope) and
confirm the named task is still a valid, unblocked, authoritative execution
target — exactly as `AGENTS.md`'s "Autonomous flow" and "Fail-closed"
sections require. A stale or mismatched revalidation is a fail-closed
condition, not a warning to route around.

---

## 4. Deterministic orchestrator responsibility

Recommended future implementation location: `tools/autonomous_pr/`. This is
repository engineering tooling — it does not live under `src/dnd_engine/**`
and is not gameplay code.

The orchestrator (not the implementer LLM, not the reviewer LLM) owns:

- phase transitions (see §9);
- resolving and holding the exact repository/base/head refs and SHAs in
  play at each step;
- running deterministic checks (tests, `git diff --check`, type checks);
- generating and selecting the exact `review.patch` range under the
  existing, unchanged A/B/C rules (`AGENTS.md` "review.patch and diff
  ranges");
- deciding whether a review gate passes, based only on the designated
  reviewer's returned verdict — never on the orchestrator's own judgment of
  the diff's quality;
- all commit/push/draft-PR side effects (§8);
- revalidation of `origin/main` and detection/handling of cumulative-audit
  staleness (§12);
- deciding and recording the run's terminal outcome (`STOP` / `BLOCKED`),
  including reaching the `READY_FOR_HUMAN_MERGE` runtime milestone
  immediately before the mandatory terminal `STOP` (§10).

The orchestrator never makes a gameplay or architecture decision. It has no
authority to choose an implementation approach, interpret ambiguous
requirements, or resolve a canonical conflict — those remain LLM
(implementer/reviewer) or human judgment calls, bounded by §15's
deterministic/LLM split. When a decision would require the orchestrator to
exercise gameplay/architecture judgment, that is a fail-closed condition
(§17), not a decision for it to make.

---

## 5. Implementer / designated-reviewer role and context isolation

Minimal contract, matching `AGENTS.md` "Review authority":

```text
implementer context != designated reviewer context
```

- the reviewer is selected by the orchestrator, never by the implementer or
  by the implementer's own output;
- the reviewer's context is fresh relative to the implementer: it does not
  inherit the implementer's conversation, reasoning trace, or unstated
  assumptions;
- the reviewer may use the same provider/model family as the implementer;
  a different provider is optional defense-in-depth, never a requirement —
  no provider or model family receives special canonical privilege;
- correctness of the review must never depend on hidden provider
  conversation state that isn't reflected in the explicit handoff artifacts
  (§6). If the reviewer needs information to judge the change, that
  information must be in the handoff, not assumed from a shared session;
- same-role continuation (e.g., the implementer continuing across
  checkpoints within one task) is allowed as an implementation
  optimization, but only when every load-bearing piece of information for
  the next step is still passed through an explicit handoff artifact
  rather than relied upon implicitly from prior turns.

---

## 6. Explicit handoff artifacts

No JSON schema is defined here — that is an implementation detail for the
future orchestrator, not part of this contract. The following pieces of
information must exist as explicit, inspectable artifacts at the
appropriate phase, not only as conversational context:

- authoritative task context (the named task's full `docs/TASK.md` detail,
  as revalidated against current `origin/main`);
- the plan, and its accepted/reviewed status;
- repository context: base ref/SHA, delivery branch name, current head SHA;
- deterministic verification evidence (which checks ran, and their
  pass/fail result);
- the exact `review.patch` handed to the reviewer for a given checkpoint;
- the reviewer's verdict and any findings (§7);
- Task Closure context, when the run reaches that phase (§18.1 inputs:
  PR number, accepted implementation diff, etc.).

A phase transition that depends on one of these artifacts must not proceed
without it. Missing or unreadable required handoff data is a fail-closed
condition (§17), not a case to proceed past optimistically.

---

## 7. Strict reviewer verdict contract

The reviewer's output must resolve to exactly one of three verdicts, each
with exactly one mechanical consequence:

- `APPROVED` → the review gate for that checkpoint passes; the orchestrator
  may proceed (e.g., commit, §8).
- `CHANGES_REQUESTED` → the checkpoint is not accepted; the orchestrator may
  enter a bounded repair/re-review cycle (§11), staying inside the
  already-approved task scope, and then re-submit for review.
- `BLOCKED` → terminal. The run ends immediately, exactly as `AGENTS.md`
  describes for a designated-reviewer `BLOCKED` verdict; resuming requires
  a new, separate, explicit user invocation.

Any verdict that is not one of these three literal tokens — a missing
verdict, free-form text without a recognized verdict token, a malformed or
ambiguous response, or a timeout/error/crash in the reviewer process itself
— is **not** a fourth kind of input to route into the bounded repair loop.
It is a fail-closed condition and is always treated as terminal `BLOCKED`:
the orchestrator does not attempt a repair/re-review cycle in response to
it, and does not guess at the reviewer's intent. Only an actual returned
`CHANGES_REQUESTED` verdict may trigger bounded repair (§11); a missing,
malformed, ambiguous, or failed-to-execute review never does. An
unparseable verdict is never silently upgraded to `APPROVED` either.

Per `AGENTS.md`, an `APPROVED` verdict from the designated reviewer is what
constitutes an accepted review checkpoint, and — after the final cumulative
implementation review — is what satisfies `docs/TASK.md` §18.1's
"implementation diff has been reviewed/accepted" prerequisite.

---

## 8. Repository / Git / `gh` ownership and forbidden side effects

Authoritative Git and GitHub side effects belong to the orchestrator, never
to the implementer or reviewer process directly:

- the implementer changes working files inside the workspace, but never
  performs its own `git commit` / `git push` to bypass the review gate;
- a checkpoint is committed by the orchestrator only after that checkpoint
  has been `APPROVED` by the designated reviewer;
- accepted commits are pushed by the orchestrator only to the invocation's
  own delivery branch — never to any other branch, and never to `main`;
- a draft pull request is created/updated only through the `gh` CLI;
- there is no GitHub REST API fallback if `gh` is unavailable — that is a
  fail-closed condition (missing required tool, §14), matching `AGENTS.md`;
- the harness never issues a merge or auto-merge command, under any
  condition, at any phase;
- the harness never performs a direct write to `main` — including edits
  that would otherwise be considered non-substantive;
- `review.patch` is a working artifact for review, never committed to the
  repository, matching the existing `.gitignore`d, uncommitted status of
  `*.patch`/`*.diff` files.

The existing A/B/C `review.patch` diff-range semantics (`AGENTS.md`
"review.patch and diff ranges") are unchanged by this document. The harness
selects among exactly those three ranges; it does not introduce a fourth.

**The pre-closure cumulative implementation review is explicitly not mode
C.** Per `docs/TASK.md` §18.1's "implementation diff has been
reviewed/accepted" prerequisite, the harness builds this review's input as
`origin/main...HEAD` — the same command shape as mode C — but this is not a
fourth diff-range mode and it is not mode C itself:

- its input is `origin/main...HEAD` taken *before* Task Closure exists on
  the delivery branch;
- it satisfies `docs/TASK.md` §18.1, not the mode C final cumulative branch
  audit;
- mode C is reserved exclusively for the *final* cumulative branch audit,
  and the harness only builds it after Task Closure itself has been
  reviewed, committed, and pushed on the delivery branch, and only after
  `origin/main` has been freshly re-fetched and revalidated (§12);
- mode C's `origin/main...HEAD` therefore includes the closure commit(s);
  the pre-closure review's `origin/main...HEAD` does not.

The harness must not conflate the two, must not skip the pre-closure
cumulative implementation review on the theory that mode C will cover it
later, and must not treat mode C's audit as satisfying §18.1's
implementation-review prerequisite retroactively.

---

## 9. Minimal in-memory run state and phase model

The harness holds a small amount of in-memory state describing one live
run: which delivery branch/task it is working on, which phase it is
currently in, and the handoff artifacts (§6) produced so far. This is
conceptual state for one process's lifetime, not a persisted schema — see
§11 for why no durable store is introduced.

The conceptual phases, matching the existing `AGENTS.md` "Autonomous flow"
sequence, are:

```text
preflight
  → planning
  → plan review
  → delivery branch ready
  → implementation checkpoint / deterministic verification / checkpoint review   (repeats)
  → full verification
  → pre-closure cumulative implementation review
  → draft PR
  → prospective Task Closure / closure review
  → origin/main revalidation
  → mode C final cumulative audit
  → required CI
  → READY_FOR_HUMAN_MERGE
  → STOP (or BLOCKED, from any phase)
```

This is a small, fixed set of conceptual phases tracking the already
governed flow — not a general workflow-engine state machine, and not a
license to invent additional lifecycle statuses beyond what `AGENTS.md` and
`docs/TASK.md` already define (in particular, no new `docs/TASK.md`
`Status` value is introduced by this document or by any harness built from
it).

---

## 10. `STOP`, `BLOCKED`, and `READY_FOR_HUMAN_MERGE` semantics

- `STOP` and `BLOCKED` are the run's only terminal outcomes. Both end the
  current `AUTONOMOUS_PR` invocation exactly as `AGENTS.md` describes:
  resuming requires a new, separate, explicit user invocation. Neither is
  automatically or implicitly resumed by the harness.
- `READY_FOR_HUMAN_MERGE` is a **runtime milestone**, reached after the
  draft PR, prospective Task Closure, revalidation, mode C audit, and
  required CI have all completed successfully — immediately before the
  mandatory terminal `STOP`. It is not a new `docs/TASK.md` task status and
  is never written into the tracker; it exists only as a run-time signal
  that the invocation has reached the point where a human is needed to
  review and merge.
- Reaching `READY_FOR_HUMAN_MERGE` does not authorize merge or auto-merge.
  The harness still stops immediately afterward; merge remains a
  separate, explicit human action outside the harness's authority.

---

## 11. Bounded repair/retry and no implicit cross-process resume

- Bounded repair loops (implementation fixes in response to
  `CHANGES_REQUESTED`, or CI-driven fixes) are allowed within one live
  invocation, exactly as `AGENTS.md`'s bounded-authority section allows,
  and must stay inside the already-approved task scope.
- Repair must not become unbounded: the run must have a finite
  fail-closed boundary rather than looping indefinitely. This contract
  does not fix exact numeric retry limits — those are an implementation
  detail an actual harness may tune, not a canonical rule enforced here.
- No persisted `run.json`, database, state store, or orchestration schema
  is introduced. Run state (§9) lives only in the orchestrator process's
  memory for the duration of that one run.
- A process crash, lost orchestration state, or an ambiguous partial side
  effect (e.g., it is unclear whether a push actually landed) must never
  cause the harness to implicitly and automatically resume or guess at the
  prior state. The first (v1) implementation is explicitly not required to
  reconstruct a run's state across process boundaries — it may simply fail
  closed and require a fresh, explicit invocation instead of attempting
  recovery.
- Continuing after a terminal `STOP` or `BLOCKED` always requires a new,
  separate, explicit user invocation per `AGENTS.md` — never an automatic
  restart by the harness itself, and never an inference from repository
  state (e.g., "the branch still exists, so keep going").

---

## 12. `origin/main` movement and cumulative-audit staleness

- Any movement of `origin/main` after a cumulative diff/audit was built
  (pre-closure cumulative implementation review or the mode C final
  cumulative branch audit) makes that specific audit stale. A stale audit
  must be rebuilt and re-reviewed before the run proceeds past the point
  that depended on it — this mirrors `AGENTS.md`'s mode C staleness rule
  exactly, including "no materiality exception" once mode C has run.
- Movement of `origin/main` is not, by itself, automatically a `BLOCKED`
  outcome. The harness's required reaction is: fetch, then revalidate the
  authoritative facts the current phase depends on (current `Current`
  task, its Status/dependencies, any fact the prepared implementation or
  closure relies on).
- The run becomes `BLOCKED` only when that revalidation finds that material
  facts have actually changed (e.g., a different task is now `Current`, a
  dependency is no longer `Done`, Roadmap scope shifted) or when safe
  continuation cannot be positively established from the revalidated
  state. An unchanged, successfully revalidated `origin/main` movement
  (e.g., unrelated work merged elsewhere on `main`) does not by itself
  block the run.

---

## 13. Provider-specific implementation boundary

This contract stays strictly provider-neutral, matching `AGENTS.md`
"Review authority". It does not define, and a v1 harness must not
introduce:

- a `BaseProvider` interface, adapter hierarchy, or provider
  registry/factory;
- any framework generalizing "providers" before a real second consumer
  exists.

Provider-specific detail is confined to the external process **invocation
boundary** only — i.e., how the orchestrator starts and talks to one
external agent executable — and may include:

- the executable name and command-line flags;
- the provider's own authentication mechanism (already configured in the
  environment, per §14 — the harness does not manage it);
- sandbox/tool-access flags passed to that executable;
- the mechanics of injecting context via stdin, a file, or another
  provider-specific channel.

No provider or model family receives special governance privilege as a
result of this boundary. Whatever provider is used as implementer or
reviewer, it must be capable of having the required role/context isolation
(§5) and tool boundaries (§14) enforced around it; if a given provider
integration cannot support that, the run must fail closed rather than
proceed with a weakened isolation guarantee.

---

## 14. Secrets, credentials, and tool-access assumptions

- Authentication for `git`, `gh`, and any configured agent executable is
  assumed to already be provisioned in the external execution environment
  before the harness starts. The harness does not set up, provision, or
  manage credentials.
- The harness never reads `git credential`, `.git-credentials`, or any
  other credential store to obtain a token — matching the existing
  `AGENTS.md` prohibition on this for PR creation, generalized here to the
  whole harness.
- The harness never writes secrets into repository content, run artifacts,
  or logs.
- A missing or unusable required tool, authentication, or capability (for
  example, `gh` not installed, or an agent executable failing to
  authenticate) is a fail-closed condition (§17), not something the
  harness works around with a fallback path.
- The implementer and reviewer processes are given only the tool
  capabilities they need to do their respective jobs, to the extent the
  provider boundary (§13) allows the orchestrator to constrain them; the
  orchestrator does not grant either role Git/GitHub write access directly
  (§8 keeps that with the orchestrator itself).

---

## 15. Deterministic orchestration vs. LLM decision-making boundary

Deterministic (owned by the orchestrator, never delegated to an LLM):

- phase transitions (§9);
- SHA/ref validation and `origin/main` revalidation (§3, §12);
- exact `review.patch` range selection under the unchanged A/B/C rules
  (§8);
- running verification commands (tests, `git diff --check`, type checks)
  and interpreting their pass/fail exit status;
- whether a review gate has been satisfied — based solely on the
  reviewer's returned verdict (§7), never on the orchestrator's own
  re-judgment of the diff;
- commit/push/PR eligibility (§8);
- staleness detection (§12);
- the run's terminal outcome (`STOP` / `BLOCKED`), and reaching the
  `READY_FOR_HUMAN_MERGE` runtime milestone that immediately precedes the
  mandatory terminal `STOP` (§10).

LLM-owned (implementer and/or reviewer):

- producing the plan;
- implementation choices within the already-approved task scope;
- semantic code/documentation review and findings;
- bounded repair content (§11) — what to change in response to
  `CHANGES_REQUESTED` or CI feedback;
- wording of PR descriptions and Task Closure text.

An LLM (implementer or reviewer) can never expand the task's authorized
scope, grant itself a permission `AGENTS.md` does not grant
`AUTONOMOUS_PR`, or weaken/skip a gate the orchestrator is responsible for
enforcing. If an LLM's output would require doing so, the orchestrator's
deterministic gate must refuse it — that refusal is what "the LLM cannot
expand authority" means mechanically.

---

## 16. CI feedback / repair replay rule

`AGENTS.md`'s bounded CI repair semantics for `AUTONOMOUS_PR` are preserved
unchanged; this document does not introduce a blanket "any CI failure is
automatically `BLOCKED`" rule, since bounded repair in response to CI
feedback is already explicitly allowed within approved scope.

- A repair commit made in response to review or CI feedback invalidates any
  downstream cumulative review/audit evidence that was built before that
  commit (the pre-closure cumulative implementation review and/or the mode
  C final cumulative branch audit, §12).
- After such a repair commit, the harness must replay the affected
  deterministic verification, review, revalidation, and audit gates — it
  does not carry forward an audit result that predates the repair.
- If the v1 implementation cannot provably and safely perform the required
  rewind/replay for a given repair (for example, because it cannot
  establish which downstream evidence the repair actually invalidates), it
  must fail closed rather than proceed on stale or unverifiable evidence.
- No implementation of this rule may weaken a CI, test, or review gate to
  make a repair "pass" — the gate itself is never adjusted to fit the
  repair.

---

## 17. Hard-stop cases

In addition to the fail-closed conditions already listed in `AGENTS.md`
("Fail-closed"), which this document does not repeat or narrow, the
following harness-level situations end the run exactly like a terminal
`STOP`/`BLOCKED`, requiring a new explicit user invocation to resume:

- a required handoff artifact (§6) is missing or unreadable at the phase
  that needs it;
- the reviewer returns a missing, malformed, or unrecognized verdict, or
  the reviewer process itself fails to execute (§7) — always terminal
  `BLOCKED`, never routed into the bounded repair loop;
- a required tool, credential, or capability is missing or unusable (§14);
- `origin/main` revalidation (§3, §12) finds a material fact has changed
  that the implementation or prepared closure depends on;
- a repair commit's downstream evidence cannot be safely replayed (§16);
- the process loses track of run state (crash, ambiguous side effect) and
  cannot safely resume in-process (§11);
- any condition that would otherwise require expanding scope, weakening a
  gate, or making a decision `AGENTS.md` reserves for a human or for a
  separate architectural decision (mirroring `AGENTS.md`'s own
  fail-closed list in full).

---

## 18. Minimal harness test contract

No harness tests are implemented by this document (`TSK-0025` is
design/contract only). The `TSK-0026` v1 implementation's tests, at
`tests/tools/autonomous_pr/`, satisfy the conditions below using fakes/
stubs and disposable local Git fixtures — this section remains the
contract that implementation must conform to, not a description generated
from it. A v1 implementation is expected to be testable under these
conditions:

- a fake/stub implementer and a fake/stub reviewer, so tests do not require
  a real LLM;
- temporary, disposable Git repositories/workspaces created per test, not
  the real project repository;
- fake or stubbed process boundaries for `gh` and the agent executable(s),
  so tests do not require real network access or a real GitHub remote;
- no real provider or network access required for the core test suite.

Required regression coverage (behavioral, not implementation-prescriptive):

- happy path: preflight through `READY_FOR_HUMAN_MERGE` and `STOP`;
- `CHANGES_REQUESTED` triggers a bounded repair cycle and re-review;
- a `BLOCKED` reviewer verdict ends the run as terminal `BLOCKED`;
- a missing, malformed, ambiguous, or unrecognized verdict, and a
  timeout/error/crash of the reviewer process itself, is never treated as
  approval and never enters the bounded repair loop (§11) — it ends the run
  as terminal `BLOCKED` directly, the same as an explicit `BLOCKED`
  verdict, never as a variant of the `CHANGES_REQUESTED` repair path;
- a commit is never produced before the corresponding checkpoint has an
  `APPROVED` verdict;
- no push to any branch other than the invocation's own delivery branch,
  no write to `main`, no merge/auto-merge command is ever issued;
- `review.patch` is generated using the correct A/B/C range for each
  situation, unchanged from the existing `AGENTS.md` rules;
- a cumulative audit becomes stale after a new commit or after
  `origin/main` moves, and is rebuilt/re-reviewed before proceeding;
- task revalidation failure (task no longer `Current`, dependency no
  longer `Done`, etc.) ends the run instead of proceeding;
- missing required tools/auth end the run instead of degrading gracefully;
- an ambiguous side-effect result (e.g., push outcome unclear) does not
  cause the harness to guess and continue;
- no implicit cross-process resume occurs after a crash or lost run state;
- Task Closure and the mode C final cumulative audit occur in the correct
  order (closure reviewed/committed/pushed and `origin/main` revalidated
  *before* the mode C audit is built), matching `AGENTS.md`'s explicit
  distinction between the pre-closure cumulative review and mode C.

---

## 19. Explicit v1 out-of-scope list

This document (`TSK-0025`) is design/contract only and does not itself
implement a runner/orchestrator. `TSK-0026` is explicitly the task that
implements the minimal v1 runner/orchestrator described here.

Beyond that, this document, and any v1 implementation built from it
(including `TSK-0026`), explicitly does **not** include:

- refinement of `TSK-0023`;
- a real autonomous pilot run;
- a GitHub Actions autonomous runner;
- Docker, cloud, or container orchestration;
- a database, message broker, or dashboard;
- a persisted `run.json` or any orchestration schema;
- a provider SDK;
- a provider adapter framework or `BaseProvider` hierarchy;
- prompt-file or prompt-architecture design;
- automatic task discovery or queue traversal;
- parallel execution of multiple `TSK`s;
- autonomous merge or auto-merge of any kind;
- repository settings or branch-protection changes;
- new production dependencies;
- any change to gameplay Architecture or gameplay code;
- exact numeric retry-count tuning.

---

# Part II — Operational v2 contract

Sections 20 onward define the operational, spec-driven `AUTONOMOUS_PR` v2.
Read §20 before any other section of this Part.

---

## 20. Status and completed transition boundary (operational v2)

`TSK-0028` atomically activated Part II, the v2 public entrypoint, the thin
tracker, and the `AGENTS.md` declaration. Therefore:

- v2 is the only operational version; there is no mixed mode, version flag,
  per-task version selection, v1 fallback, runtime planning/plan-review, or
  numeric repair budget;
- the thin `docs/TASK.md` tracker and the exact-base Task Execution Spec are
  the only execution inputs;
- Part I records how v1 operated before activation and supplies no v1 runtime
  path; its common definitions/invariants apply only where Part II explicitly
  incorporates them by reference;
- `TSK-0027` and `TSK-0028` ran under `MANUAL` as transition work. That fact
  is historical, not a permanent runtime exception.

This document never grants invocation authority; `AGENTS.md` remains the
authoritative boundary.

---

## 21. Document ownership (operational v2)

| Document | Owns |
| --- | --- |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | canonical system behavior and contracts |
| [`ROADMAP.md`](ROADMAP.md) | capability and phase scope and ordering |
| [`TASK.md`](TASK.md) | task lifecycle: Status, Priority, Size, dependencies, `Current`/`Next`, queue order, task allocation |
| `docs/tasks/TSK-XXXX.md` | the approved execution target of one task |
| [`../AGENTS.md`](../AGENTS.md) | authority, Git, review, and merge governance |
| this document | subordinate execution mechanics |
| [`DEVELOPMENT_LOG.md`](DEVELOPMENT_LOG.md) | factual delivery history |

A Task Execution Spec cannot:

- redefine or override `ARCHITECTURE.md`;
- expand `ROADMAP.md` scope;
- itself grant commit, push, pull-request, or merge authorization;
- introduce an architectural decision that is not already recorded through
  the normal change procedure — a spec may cite an approved decision, never
  make one;
- replace or reinterpret `AGENTS.md`.

A conflict between a spec and any higher-level source is `BLOCKED / human
decision`. Neither the orchestrator nor an agent resolves it by silently
choosing a source, and none edits either side within the invocation to make
them agree.

---

## 22. Task Execution Spec: identity, storage, and lifecycle (operational v2)

- **Path.** Exactly `docs/tasks/TSK-XXXX.md`, a function of the immutable
  task ID alone. One spec per task; the ID in the file must match its
  filename. There are no status-based directories (`current/`, `done/`,
  `backlog/`): a file that moved when the task's status changed would break
  stable references and turn the directory layout into a second lifecycle
  record.
- **Responsibility split.** The spec is the approved execution contract of
  one task. `docs/TASK.md` keeps every mutable fact about that task. The
  spec never carries a Status, Priority, Size, dependency, or queue-position
  field; a second authoritative copy of any of them is a defect.
- **Progressive elaboration.** Applies to activated v2 only:

  | Task status | Spec |
  | --- | --- |
  | `Backlog` | optional |
  | `Ready` | required |
  | `Current` | required and execution-ready |

  A spec is execution-ready when every required section is present and
  concrete, its checkpoints declare every required field (§23), no
  unresolved placeholder or open decision blocks execution, nothing in it
  conflicts with a higher-level source (§21), and no requirement that
  constrains execution appears only in an informational section (§24). Specs
  are not written
  mechanically for distant backlog, and none is written retroactively for
  completed tasks (`TSK-0001`–`TSK-0026`).
- **Completed specs.** After a task is `Done` its spec stays in place as the
  historical record of what was approved for implementation. It is not
  current canonical Architecture. Task Closure does not edit it, and the
  task's `Done` status is recorded only through `docs/TASK.md`.
- **Provider neutrality.** A spec is never stored as a provider-specific
  prompt or prompt sequence (for example "Prompt 1 for provider X"). The
  orchestrator derives any runtime handoff from the provider-neutral spec.

---

## 23. Task Execution Spec: structure (operational v2)

A spec has these sections, in this order:

1. Goal
2. Context / References
3. Scope
4. Out of scope
5. Approved implementation approach
6. Acceptance criteria
7. Execution checkpoints
8. Full verification
9. Known constraints / edge cases

Every checkpoint in *Execution checkpoints* is identified `CP-1`, `CP-2`, ...
in execution order and declares:

- **Objective** — what the checkpoint is for;
- **Required result** — the observable state it must leave behind;
- **Constraints** — what it must not do or change;
- **Verification** — the deterministic checks that must pass for it;
- **Review focus** — where the reviewer is asked to look first.

Checkpoints are steps inside one mergeable task. They have no `TSK-*` ID and
no status of their own. As `AGENTS.md` ("Working method") requires, they are
drawn along independent review-risk boundaries rather than mechanically by
file set.

Skeleton:

```markdown
# TSK-XXXX — <title>

## Goal
## Context / References
## Scope
## Out of scope
## Approved implementation approach
## Acceptance criteria
## Execution checkpoints
### CP-1 — <name>
- Objective:
- Required result:
- Constraints:
- Verification:
- Review focus:
## Full verification
## Known constraints / edge cases
```

---

## 24. Binding and advisory content (operational v2)

| Binding | Advisory |
| --- | --- |
| Goal | Expected touchpoints |
| Scope | Suggested internal decomposition |
| Out of scope | Naming suggestions |
| Approved implementation approach, including its approved contractual and architectural decisions and invariants | Implementation notes |
| Acceptance criteria | Review focus |
| Declared checkpoints, and each checkpoint's Objective, Required result, Constraints, and Verification | |
| Full verification | |

Within *Approved implementation approach*, the approach and its decisions and
invariants are binding. Expected touchpoints, suggested decomposition, naming
suggestions, and implementation notes belong in a clearly labelled advisory
sub-block of that section and stay advisory.

*Context / References* and *Known constraints / edge cases* are
informational. They may refer to binding constraints or decisions, but no
binding requirement exists only inside them: any requirement that actually
constrains execution must also appear in the corresponding binding section
(Scope, Out of scope, Approved implementation approach, Acceptance criteria, a
checkpoint's Constraints, or Full verification). A requirement stated only in
an informational section is not binding, and its presence there alone leaves
the spec not execution-ready (§22).

Advisory content is guidance, never a requirement, and never a limit on
what a reviewer may report. In particular, **Review focus** tells the
reviewer where to look first; a reviewer reports any defect it finds,
inside or outside that focus.

An implementer may take local coding decisions that the spec leaves open,
provided a decision does not:

- expand scope;
- change a canonical contract;
- violate the approved implementation approach;
- change a checkpoint's required result;
- require a new architectural decision;
- add a production dependency without explicit permission.

A decision that would do any of these is not the implementer's to take: it
ends the run as `BLOCKED` for refinement or a human decision.

### Prospective TSK-0029 CP-1 input model (inactive)

TSK-0029 CP-1 introduces pure, fixture-tested parsing primitives for its
future standalone task format. A prospective document has the canonical
`docs/tasks/TSK-NNNN.md` path and matching H1, followed by one `## Task
metadata` fenced JSON object. That envelope explicitly carries
`execution_approval`, `priority`, `size`, `roadmap_target`, and `depends_on`;
`group` is optional. An approved document additionally carries the existing
nine execution sections. A draft may omit the execution body or carry a
partial or complete body, but remains non-executable and is not checked for
approved readiness. The parsed document retains its exact source text and
digest.

The same slice exposes the durable `ID | Status | Evidence | Title` terminal
registry independently of `Current` and the Open task index. It does not yet
list or select task files, filter terminal IDs from a catalog, or connect the
new input model to public preflight/CLI. The Current-based operational contract
in §§20–35 remains active until TSK-0029's atomic CP-5 activation; this note is
prospective documentation, not a selectable partial runtime or fallback.

TSK-0029 CP-2 adds the still-prospective deterministic input boundary for that
activation. The repository boundary lists regular Git-tracked task blobs at
one exact commit; the pure catalog excludes terminal identities before body
parsing, validates every remaining document and dependency graph, and resolves
one explicit ID or `NEXT`. `NEXT` orders eligible approved documents by
priority and numeric task ID. An empty or waiting-only catalog produces the
run-level `NO_ELIGIBLE_TASK` no-work result with exit code 0, not a reviewer
verdict or a selected task ID. These primitives perform no branch, agent, PR,
queue, or scheduler action and remain disconnected from the public CLI/run
until the atomic CP-5 activation.

TSK-0029 CP-3 prospectively connects that selector to the existing concrete
v2 lifecycle without adding a second runtime or fallback. The public input is
one explicit `TSK-NNNN` or literal `NEXT`; selection occurs once against one
captured `origin/main` commit, and every later gate is bound to the selected
ID and the original full-document source SHA/path/text digest. The default
delivery branch is derived only after selection. `NO_ELIGIBLE_TASK` exits
before branch, agent, or PR writes. Acceptance revalidation rereads that same
selected ID (never `NEXT`) from a fresh exact base and blocks changed document
bytes/metadata/approval, lost `Done` dependencies, or a concurrent terminal
outcome, while unrelated catalog additions cannot switch the run to another
task. This remains prospective on the TSK-0029 delivery branch until the
single atomic activation merges. Before branch creation, Git branch-name
guards and a structured `selected_task_id` provenance check across open PRs
reject prior same-task work even when it used a custom head branch or targets
a non-`main` base. The structured block and field must each be unique; exact
task identity in the conventional PR title is the compatibility fallback,
while free-form mentions are not identity. An unreadable, malformed, or
potentially truncated PR listing fails closed. After selection, moved-base
revalidation is intentionally narrower than initial catalog validation: it
checks the strict terminal registry, exact selected document/approval, and
that selected task's `Done` dependencies, without reparsing unrelated task
bodies. A later invocation still performs the complete strict catalog
preflight.

---

## 25. Review verdicts and repair flow (operational v2)

The reviewer returns exactly one of `APPROVED`, `CHANGES_REQUESTED`, or
`BLOCKED`, as in v1 (§7). The set is unchanged.

- **Terminal `BLOCKED`.** An explicit `BLOCKED` verdict ends the run. So does
  a missing, malformed, ambiguous, or unrecognized verdict, and a reviewer
  timeout, crash, or execution error. None of these ever starts a repair
  episode, and none is upgraded to `APPROVED`.
- **`APPROVED`.** The current review gate passes and the orchestrator may
  move to the next deterministic phase. The approval criteria are identical
  at every iteration: they are never weakened by how many times the gate has
  already returned `CHANGES_REQUESTED`.
- **`CHANGES_REQUESTED`.** Not terminal. It starts a repair episode, provided
  the reviewer's output contains a complete repair packet.

A repair packet holds one or more findings. Each finding has at least these
required fields, and they are part of the repair handoff contract, not an
advisory format:

- **Problem** — what is wrong with the candidate;
- **Evidence** — where and how the problem shows in the candidate;
- **Required outcome** — the condition the next candidate must satisfy;
- **Recommended repair** — a suggested way to reach it;
- **Verification focus** — what the next deterministic verification and
  review should check.

A `CHANGES_REQUESTED` verdict with no finding, or with a finding that lacks
any required field, is malformed reviewer output and ends the run as
`BLOCKED`. Additional provider-neutral structured metadata may accompany a
finding; it never substitutes for a required field.

The operational v2 repair flow is:

```text
review → CHANGES_REQUESTED → implementer repair → deterministic verification → fresh review
```

A **repair episode** starts with a `CHANGES_REQUESTED` verdict (or, before a
gate's first review, with the initial implementation) and ends when a
candidate that passed deterministic verification is actually reviewed.

If the deterministic verification of a candidate fails, that candidate is not
sent to review until verification succeeds. It counts as a rejected candidate
for no-progress and cycle detection (§28), and the failure is handed back to
the implementer for a further repair. That further repair stays in the current
repair episode, and is governed by:

- the latest repair packet, when the episode began with a
  `CHANGES_REQUESTED`;
- the fixed Task Execution Spec and the deterministic verification failure
  evidence, when the initial candidate failed verification before the gate's
  first review, since no repair packet exists yet.

No reviewer verdict is recorded or synthesized for it, and it advances neither
the consecutive `CHANGES_REQUESTED` count nor the review iteration number of
§26 until a review actually takes place.

The reviewer never edits the working tree. The repair stays inside the fixed
spec and the approved scope; a repair that would need more than that is a
fail-closed condition (§27).

---

## 26. Gate counter and non-convergence diagnosis (operational v2)

A **gate** is one designated review point — for example a checkpoint review
or a cumulative review — for one fixed Task Execution Spec and one accepted
base context. The orchestrator keeps, per gate, the count of *consecutive*
`CHANGES_REQUESTED` verdicts, and the review iteration number: how many
designated reviews have actually taken place at that gate. The iteration number
advances with every verdict a designated review returns, and the consecutive
count advances with every `CHANGES_REQUESTED`. A candidate rejected by
deterministic verification (§25) advances neither. Both start again after that
gate returns `APPROVED` and when the run moves on to the next gate.

From the second consecutive `CHANGES_REQUESTED` at the same gate, the
reviewer must add a non-convergence diagnosis to the repair packet, stating:

- what the previous review required;
- what the implementer actually changed;
- why the candidate still does not satisfy the fixed spec;
- what was misunderstood;
- which exact required outcome remains;
- which corrective approach is recommended.

A `CHANGES_REQUESTED` that omits the required diagnosis is malformed and ends
the run as `BLOCKED` (§25).

The number of `CHANGES_REQUESTED` verdicts is never, by itself, a ground for
`BLOCKED`. The diagnosis exists to improve the repair guidance. It does not
oblige the reviewer to approve: a candidate that does not satisfy the approved
target stays `CHANGES_REQUESTED` however many reviews have passed.

---

## 27. Repair limit and finite safety (operational v2)

v2 has no numeric repair limit. There is no rule of the form "N repairs
exceeded → `BLOCKED`", and no canonical value such as "at most 2 repairs" or
"at most 5 repairs". A repair count may exist as telemetry and audit
information; it is never an input to a gate decision.

The production configuration and CLI expose no repair-limit field or flag.
Historical v1's bounded behavior in Part I is inactive.

Removing the numeric budget does not remove fail-closed safety. Every one of
these still ends the run as `BLOCKED`:

- an agent or reviewer timeout;
- malformed reviewer output, including an incomplete repair packet;
- a reviewer `BLOCKED` verdict;
- a missing tool or capability;
- an ambiguous Git or GitHub side effect;
- lost in-memory run state;
- a required revalidation that cannot be performed;
- a required scope expansion;
- a new architectural decision being needed;
- a new production dependency being needed;
- stale evidence that cannot be safely replayed;
- any other deterministic fail-closed condition in `AGENTS.md` or Part I.

Finite guards that are not a repair budget may be kept — for example, one
protecting a run from a constantly moving `origin/main`. Otherwise a run ends
by these fail-closed conditions and by deterministic no-progress detection
(§28), not by an iteration count.

---

## 28. Deterministic no-progress and cycle detection (operational v2)

No-progress is decided by an objective candidate identity, never by an LLM
judgment such as "the agent is not making enough progress".

- **Candidate identity.** A deterministic fingerprint of the
  *review-relevant candidate state* — the candidate content that is, or would
  be, submitted for review at that gate. It does not depend on the iteration
  number, timestamps, reviewer prose, temporary artifact paths, or the
  formatting of verification logs. This contract does not choose a fingerprint algorithm;
  that is an implementation detail of the later task.
- **Rejected candidate.** A candidate that received `CHANGES_REQUESTED`, or
  failed required deterministic verification, at a gate. Rejection by
  verification involves no reviewer verdict.
- **Comparison scope.** Identities are compared only within the same gate,
  fixed spec, and accepted base context. A candidate seen under a different
  context is a different candidate.
- **Rule.** When a repair produces a candidate whose identity equals that of
  any candidate already rejected at the same gate and context, the run ends
  as `BLOCKED`: an exact repair cycle, or no progress. This applies equally to
  a repair made after a verification failure.

| Sequence at one gate | Outcome |
| --- | --- |
| `A → repair → A` | `BLOCKED` — no progress |
| `A → B → C → B`, with `B` already rejected | `BLOCKED` — exact repair cycle |
| `A → B → C → D → …`, all distinct | not blocked, however many iterations |

Iteration count alone never triggers this rule; only a repeated rejected
identity does.

---

## 29. Repair history, reviewer handoff, and freshness (operational v2)

The orchestrator owns the audit history of a gate. For every candidate or
repair attempt it records the orchestration facts that apply to it:

- the gate or checkpoint;
- the candidate's fingerprint or identity;
- the verification evidence;
- whether the candidate was rejected, and on what basis (a reviewer
  `CHANGES_REQUESTED` or a verification failure);
- for an attempt produced by a repair, the repair delta or its fingerprint and
  the resulting candidate state.

Only when a designated review actually took place for the attempt does the
record also hold the review iteration, the reviewer verdict, and the findings.
An attempt rejected by verification has none of the three, and no synthetic
verdict stands in for them.

The full history serves audit, diagnostics, and cycle detection (§28). It
lives in the run's in-memory state (§9, §11); this section introduces no
persisted store.

A fresh reviewer is not handed the whole history. Its ordinary handoff is:

- the Task Execution Spec;
- the current checkpoint or gate;
- the current patch;
- the passing deterministic verification result of the current candidate;
- the review iteration number of this review;
- the previous reviewer findings, only if a previous review exists;
- the repair delta since the last reviewed candidate, spanning any repairs made
  after verification failures, and the resulting candidate — only if a
  reviewed candidate exists.

For the gate's first review, none of the last two items exists: the handoff is
the fixed Task Execution Spec, the current gate or checkpoint, the current
candidate patch, and the passing deterministic verification result, with
review iteration number 1. No synthetic previous findings and no synthetic
delta are created to fill the missing items.

Every designated review stays fresh and independent: `implementer context !=
designated reviewer context` (§5) holds at every review. Adaptive repair
never continues an earlier reviewer conversation, and review correctness never
depends on hidden reviewer state that is absent from this explicit handoff.

---

## 30. Spec-driven lifecycle and preflight (operational v2)

Where v1 runs `planning → independent plan review → implementation`, v2 runs
`approved Task Execution Spec → deterministic checkpoint execution`. v2 has no
runtime generative implementation planning and no plan-review gate: the
execution target is designed and approved, in the spec (§22–§24), before the
invocation starts. The orchestrator derives every runtime handoff from that
spec. The planning and plan-review phases of Part I are v1-only.

The operational v2 lifecycle is:

```text
preflight (one captured origin/main SHA: docs/TASK.md and the task spec)
  → delivery branch
  → for each declared checkpoint, in order:
      implement → verify → review/repair* → APPROVED → commit/push
  → full verification
  → pre-closure cumulative implementation review (repair* as needed)
  → draft PR
  → prospective Task Closure preparation → closure review
  → unpublished closure candidate
  → fresh origin/main revalidation
  → Mode C final cumulative audit
  → publish exactly the audited candidate
  → required CI
  → READY_FOR_HUMAN_MERGE
  → STOP (or BLOCKED, from any phase)
```

The orchestrator, not an LLM, owns every transition (§4, §15). The terminal
outcomes and `READY_FOR_HUMAN_MERGE` keep the meaning given in §10. Mode C must
remain fresh from the moment it is built through `READY_FOR_HUMAN_MERGE` and the
mandatory `STOP`; `STOP` does not make it permanently valid (§32).

**Preflight.** The orchestrator fetches, captures one exact `origin/main` SHA,
and reads both `docs/TASK.md` and `docs/tasks/TSK-XXXX.md` from that SHA — not
from the working tree, and never from two different SHAs. At minimum it
checks that:

- the named task is the authoritative `Current` task;
- every dependency is `Done`;
- the task's Roadmap target is permitted;
- the spec exists and belongs to that same task;
- the spec is execution-ready (§22);
- no unresolved placeholder or open decision blocks execution;
- the task metadata and the spec were read from the same captured SHA.

A failed check ends the run as `BLOCKED`. If `origin/main` later moves and the
named task's `docs/TASK.md` entry, its dependencies, its Roadmap target, or its
spec changed, the run fails closed; it never continues on a stale execution
target. A movement that changes none of these is handled by revalidation as in
§12 and is not by itself `BLOCKED`.

**Spec immutability.** Within one invocation the Task Execution Spec is fixed.
No implementation or repair may change the task's own
`docs/tasks/TSK-XXXX.md`; a candidate that does is a scope violation and ends
the run as `BLOCKED`. If a successful implementation would require changing the
spec, that is `BLOCKED` for normal refinement or a human decision, never an
edit made inside the run.

---

## 31. Checkpoints and pre-closure cumulative review (operational v2)

The checkpoints declared in the spec (§23) are executed exactly as declared and
in order. A checkpoint is not a separate task and has no status of its own; it
remains part of one mergeable task. The orchestrator cannot add, drop,
reorder, or merge declared checkpoints; needing to is `BLOCKED` for refinement.

For each checkpoint:

- the implementer works against the fixed spec and that checkpoint's
  Objective, Required result, and Constraints;
- the orchestrator runs the checkpoint's Verification;
- the designated reviewer reviews the checkpoint under the unchanged A/B/C
  `review.patch` rules, with its Review focus as advisory guidance (§24);
- a `CHANGES_REQUESTED` follows the adaptive repair contract (§25–§29);
- only after `APPROVED` does the orchestrator commit and push, and only to the
  invocation's own delivery branch (§8).

After every declared checkpoint is approved, the orchestrator runs the spec's
Full verification and then the pre-closure cumulative implementation review.
That review keeps its v1 definition (§8): its input is `origin/main...HEAD`
before Task Closure exists on the branch, it satisfies `docs/TASK.md` §18.1,
and it is not Mode C.

A `CHANGES_REQUESTED` from the cumulative review follows the adaptive repair
contract (§25–§29). A repair invalidates evidence built against the old
candidate (§33). Once such a repair is made, at least the following happens
before approval can be reached: deterministic verification and review of the
repair; commit and push of the accepted repair to the delivery branch; the Full
verification again; a rebuilt cumulative diff over `origin/main...HEAD`; and a
fresh cumulative review. An earlier cumulative approval is never carried over
to a new candidate.

---

## 32. Unpublished closure candidate and Mode C ordering (operational v2)

**Historical v1 limitation.** Under v1 the prospective Task Closure was committed
and pushed before Mode C runs. A Mode C `CHANGES_REQUESTED` therefore cannot be
repaired safely, and the v1 orchestrator fails closed on it (`BLOCKED`). v2 is
designed to remove this limitation.

**Invariant.** A rejected Mode C candidate must never require a remote history
rewrite in order to be repaired. Consequently the closure candidate stays
unpublished until Mode C has approved exactly that candidate. This contract
fixes the invariant, not a Git command for achieving it.

The operational v2 order is:

```text
accepted implementation
→ draft PR
→ prepare prospective Task Closure
→ closure review APPROVED
→ create the local closure commit (the unpublished closure candidate)
→ fresh origin/main revalidation
→ Mode C
```

**Closure candidate as a local commit.** After closure review returns
`APPROVED`, the orchestrator creates a local closure commit. That commit
becomes the new `HEAD`, and it is not pushed before Mode C approves it. Mode C
is built with `origin/main...HEAD` and therefore includes exactly this closure
commit. This contract does not fix a Git command for creating, discarding, or
replacing the commit.

- **Mode C `APPROVED`.** The orchestrator confirms that the candidate is still
  exactly the one audited and that the `origin/main` SHA is still exactly the
  one the audit was built against. Only then does it push exactly this audited
  `HEAD`, and then run required CI (§34). If the `origin/main` SHA already
  differs, it does not publish (see the staleness rule below).
- **Mode C `CHANGES_REQUESTED`.** The unpublished local closure commit is
  discarded or replaced, without any remote history rewrite. What follows
  depends on the repair, decided by the deterministic criterion of §33 (a repair
  that cannot be established as closure-only is treated as implementation-
  affecting):
  - *Implementation-affecting repair.* Repair, then deterministic verification
    and designated review, then `APPROVED`; the accepted implementation repair
    is committed and pushed to the delivery branch; the affected implementation
    and downstream gates are replayed (§33); Task Closure is rebuilt; then a
    new unpublished closure candidate, fresh `origin/main` revalidation, and a
    fresh Mode C.
  - *Closure-only repair.* Only Task Closure is corrected, locally, then closure
    review, a new unpublished closure candidate, fresh `origin/main`
    revalidation, and a fresh Mode C. The closure is not pushed before Mode C
    approves it.

The reviewer only reports the semantic defect. It does not choose the workflow
transition; the orchestrator does (§15).

**Exact audited-candidate rule.** After Mode C approves a candidate, any change
to the candidate's `HEAD` or content before publication makes that audit stale.
An audit of X is never used to publish Y.

**Mode C staleness.** The `AGENTS.md` rule is preserved unchanged: once Mode C
has been built, any movement of `origin/main` makes that audit stale, with no
materiality exception. A movement is not by itself `BLOCKED`. The orchestrator
fetches, revalidates the facts the run depends on (§12), and rebuilds and
re-reviews Mode C against the new `origin/main` SHA. The run is `BLOCKED` only
where §12 says so: a material fact changed, or safe continuation cannot be
established.

- **Before publication.** A stale audit is rebuilt and re-reviewed first. The
  candidate is never published on an audit built against a different
  `origin/main` SHA.
- **After publication.** Mode C must stay fresh through required CI and up to
  `READY_FOR_HUMAN_MERGE` and the mandatory `STOP`. If `origin/main` moves after
  publication, the orchestrator fetches, revalidates, rebuilds and re-reviews
  Mode C against the same published candidate, and replays the downstream
  required gates that depend on it, including required CI where applicable. If
  that new Mode C requires a candidate-changing repair, §34 applies.
- **After `STOP`.** `STOP` ends only the autonomous invocation; it does not make
  the Mode C audit valid indefinitely. If `origin/main` moves after `STOP` and
  before the human merge, the completed audit is stale again under `AGENTS.md`.
  The stopped harness does not resume, and does not detect or act on this. A
  reached `READY_FOR_HUMAN_MERGE` never permits merging on a stale Mode C audit.
  Before the merge, the audit must be rebuilt and re-reviewed through a new
  explicit autonomous invocation or through the `MANUAL` workflow, as
  governance permits.

Mode C keeps its definition of a final cumulative branch audit built with
`origin/main...HEAD`; in v2 that `HEAD` is the unpublished local closure
commit. Moving
Task Closure to before publication changes the v1 order stated in `AGENTS.md`,
so the activation task (§20) must update that text together with the
implementation.

---

## 33. Evidence invalidation and replay (operational v2)

The rule is conservative and deterministic. The orchestrator does not judge
which evidence a repair "probably" leaves valid.

- A candidate-changing repair makes stale the evidence of the gate at which it
  was made, and of every downstream gate built on the replaced candidate:
  verification results, review approvals, closure review, revalidation, and
  any Mode C audit.
- Upstream checkpoints that were already completed are not invalidated
  automatically. If the repair changes the result of a previously approved
  upstream checkpoint, however, that checkpoint's approval is stale too, and it
  and every checkpoint and gate after it are replayed.
- When the orchestrator cannot establish deterministically the earliest
  checkpoint a repair affects, it chooses the broader conservative replay, up to
  all relevant checkpoints.
- No approval is carried over merely because it was `APPROVED` earlier.
- The orchestrator may replay more gates than the minimum. It may never replay
  fewer than needed to exclude stale evidence.
- If safe replay is impossible, the run ends as `BLOCKED` (§27).

For an implementation-affecting repair made from a late gate — the
pre-closure cumulative review, the closure review, or Mode C — that does not
change the result of an earlier approved checkpoint, the conservative replay
sequence is:

```text
repair
→ deterministic verification and review of the repair (§25–§29)
→ APPROVED
→ commit and push the accepted repair to the delivery branch
→ full verification
→ pre-closure cumulative implementation review (origin/main...HEAD)
→ closure preparation
→ closure review
→ new unpublished closure candidate
→ fresh origin/main revalidation
→ Mode C
```

Only the accepted implementation repair is committed and pushed. Task Closure
keeps its separate semantics: the reviewed closure forms a local, unpublished
closure candidate that is not pushed before Mode C approves it (§32). The
`review.patch` diff ranges of each step remain the unchanged A/B/C rules.

Where the repair does change the result of an earlier approved checkpoint, that
checkpoint and every later one are replayed (§25–§29) before the rest of this
sequence.

A repair that changed only closure content may replay from closure preparation
onward, but only when the orchestrator can establish deterministically that it
changed no implementation content; otherwise the full sequence above applies.
Such a closure-only repair replaces the unpublished local closure commit and is
never pushed before Mode C approves it.

---

## 34. Post-publication repair boundary and required CI (operational v2)

`AGENTS.md` allows adaptive repair in response to review or CI feedback, with
no numeric repair limit, and neither this Part nor `TSK-0027` forbids any
repair after publication. There is no blanket rule that a post-publication
failure is always `BLOCKED`, and none that forbids future post-publication
repair.

The initial v2 implementation is not required to make any candidate-changing
repair after publication. That covers a required CI failure and a Mode C
`CHANGES_REQUESTED` obtained by rebuilding Mode C after `origin/main` moved
post-publication (§32). If it cannot yet perform a safe post-publication
replay, it ends the run as `BLOCKED`. This is an implementation limitation, not
a governance rule. Safe post-push replay and persisted resume are a separate
future task.

A rebuilt Mode C that approves the same published candidate needs no repair and
does not by itself stop the run.

A post-publication repair, once implemented, follows the evidence-invalidation
and replay rule of §33 and never weakens a gate to make a check pass.

---

## 35. First v2 trial (operational v2)

No task is designated by this contract as the first real v2 trial, and
`TSK-0023` is not implied. A good first trial is a small or medium task with:

- a clear, execution-ready spec;
- no unresolved architectural question;
- objective, deterministic tests;
- limited cross-layer risk.
