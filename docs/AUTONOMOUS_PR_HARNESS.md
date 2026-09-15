# AUTONOMOUS_PR Execution Harness — Minimal Contract

`TSK-0025`. This document defines the minimal, executable,
provider-neutral **execution mechanics** a future harness/orchestrator uses
to carry out an already-authorized `AUTONOMOUS_PR` invocation. It does not
implement a runner. No orchestrator, CLI, or `tools/autonomous_pr/` code
exists yet; this is a design contract only.

---

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

No harness tests are implemented by this task. A future v1 implementation
is expected to be testable under these conditions:

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
