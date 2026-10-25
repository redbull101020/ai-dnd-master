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

Windows verification containment has a separately defined, not yet implemented
contract in [§37](#37-windows-verification-containment-contract-runtime-not-implemented),
under [Architecture §13](ARCHITECTURE.md#13-windows-verification-containment).
Its publication and native-validation gates do not activate a runtime backend.

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
- for each Mode C transition, the accepted Full Verification and cumulative-
  review provenance carried from typed in-memory orchestration state, including
  its historical implementation base/HEAD and the current audit base;
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
- every designated reviewer runs in a disposable snapshot of the exact
  candidate, outside the authoritative worktree, with independent temporary
  Git metadata that has no remote and shares no index, refs, or objects with
  the authoritative repository; inherited GitHub tokens, askpass/SSH-agent
  variables, Git credential helpers, and interactive credential prompts are
  removed or disabled for the reviewer subprocess; snapshot mutation is
  discarded before the verdict can be accepted, and preparation or cleanup
  uncertainty fails closed;
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

Candidate mutation paths used for deterministic scope enforcement, bounded
staging handoff, and rejected-candidate discard come from complete,
machine-readable Git worktree status, not human-oriented pathname quoting,
textual `PATH1 -> PATH2` rendering, or newline-delimited parsing. A rename
`A` to `B` contributes both `A` and `B` as mutations; a copy `A` to `B`
contributes `B` as the mutation while `A` is lineage only; and an independent
deletion plus addition contributes both paths. This invariant is confined to
candidate worktree mutation discovery and does not claim that every Git
pathname operation in the harness shares one parser.

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

`TSK-0028` activated Part II and `TSK-0029` completed its file-based dispatch
revision. Therefore:

- v2 is the only operational version; there is no mixed mode, version flag,
  per-task version selection, v1 fallback, runtime planning/plan-review, or
  numeric repair budget;
- the permanent terminal registry and standalone task documents read from one
  exact base are the only task-state execution inputs;
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
| [`TASK.md`](TASK.md) | standalone-task rules and permanent `Done`/`Superseded` registry |
| `docs/tasks/TSK-NNNN.md` | identity and metadata of each open task; for approved tasks, the fixed execution contract |
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

- **Path.** Exactly `docs/tasks/TSK-NNNN.md`, a function of the immutable
  task ID alone. One spec per task; the ID in the file must match its
  filename. There are no status-based directories (`current/`, `done/`,
  `backlog/`): a file that moved when the task's status changed would break
  stable references and turn the directory layout into a second lifecycle
  record.
- **Envelope.** H1 is followed by exactly one `## Task metadata` section with
  one fenced JSON object. Required keys are `execution_approval`, `priority`,
  `size`, `roadmap_target`, and `depends_on`; optional `group` uses the closed
  repository vocabulary. Unknown fields, duplicate JSON keys, malformed
  types, and filename/H1 mismatch are invalid.
- **Draft and approved.** `execution_approval` is explicit and has no default.
  A `draft` owns valid metadata but is never executable; its body may be absent,
  partial, or complete. An `approved` task is executable only when every
  required section is present and
  concrete, its checkpoints declare every required field (§23), no
  unresolved placeholder or open decision blocks execution, nothing in it
  conflicts with a higher-level source (§21), and no requirement that
  constrains execution appears only in an informational section (§24). Specs
  are not written
  mechanically for distant backlog, and none is written retroactively for
  completed tasks (`TSK-0001`–`TSK-0026`).
- **Terminal tasks.** `Done` and `Superseded` live only in the permanent
  `docs/TASK.md` registry. A retained terminal file is filtered before body
  parsing and may later be removed by a separate reviewed change. Cancellation
  is recorded as `Superseded` before removal.
- **Provider neutrality.** A spec is never stored as a provider-specific
  prompt or prompt sequence (for example "Prompt 1 for provider X"). The
  orchestrator derives any runtime handoff from the provider-neutral spec.

---

## 23. Task Execution Spec: structure (operational v2)

After H1 and Task metadata, an approved task has these sections, in this order:

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

Verification commands remain provider-neutral shell-free argv arrays. At the
verification subprocess boundary only, an exact first token `"python"` is
materialized as the current harness `sys.executable`; every remaining argv
element is unchanged. The approved argv and recorded evidence retain the
original `"python"` identity: the execution-only absolute interpreter path
never replaces it in the Task Execution Spec or verification evidence. No
other executable token (including `python3`, `python.exe`, `py`, or an explicit
path) is normalized, and there is no PATH mutation, executable discovery, or
fallback interpreter chain. An OS-level failure to start the materialized
interpreter produces the existing failed verification result after exactly one
attempt and therefore fails closed without retrying another executable.

Checkpoints are steps inside one mergeable task. They have no `TSK-*` ID and
no status of their own. As `AGENTS.md` ("Working method") requires, they are
drawn along independent review-risk boundaries rather than mechanically by
file set.

Skeleton:

````markdown
# TSK-NNNN — <title>

## Task metadata
```json
{
  "execution_approval": "approved",
  "priority": "P2",
  "size": "S",
  "roadmap_target": "<concrete target>",
  "depends_on": [],
  "group": "engineering"
}
```

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
````

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

### File-based dispatch, revalidation, and terminal-only closure

The public selector is one explicit `TSK-NNNN` or literal `NEXT`; omission is
a configuration error. One captured `origin/main` SHA supplies the strict
terminal registry and every regular Git-tracked task blob. Terminal identities
are excluded before body parsing. Every remaining envelope is validated and
the dependency graph is checked; drafts are valid catalog members but never
eligible. `NEXT` chooses eligible approved work by `P0` through `P3`, then
numeric task ID. An empty or waiting-only catalog returns run-level
`NO_ELIGIBLE_TASK` with exit code 0 before any branch, agent, or PR write.

Selection happens once. The run keeps the concrete ID plus original source
SHA, canonical path, exact full-document text and digest; a default delivery
branch is derived only after selection. Fixed-target revalidation never
recalculates `NEXT`: from one fresh exact SHA it checks the strict terminal
registry, the selected document and approval, and that selected task's `Done`
dependencies. Unrelated catalog additions or malformed unrelated bodies do
not replace or invalidate the fixed target, while a new invocation still
performs full strict catalog validation. Open same-task PR provenance and
branch collisions fail closed; there is no implicit resume.

Ordinary Task Closure is terminal-only. Against exact accepted `docs/TASK.md`
bytes, the candidate inserts exactly one parser-valid row for the selected
task with `Done`, actual draft PR evidence, and its unchanged title, and
appends one factual Development Log entry. It preserves every foreign terminal
row, order, and evidence byte-for-byte; it creates no next task and does not
edit, archive, or delete any task document. Strict UTF-8, exact LF/CRLF bytes,
escaped `\|` titles, Git attributes, and clean filters are checked against the
same bytes a normal address-specific staging would produce, using an isolated
temporary index that does not mutate the user's index.

The accepted cumulative review → draft PR → unpublished prospective closure →
Closure Review → local unpublished commit → fresh revalidation → Mode C →
publication of the exact audited candidate → required CI sequence is
unchanged. Any candidate, delivery-branch, or base movement makes completed
Mode C stale. A retained terminal spec is ignored before body validation; its
later deletion is optional separate reviewed work. Deletion of the active
selected document blocks the current run. After terminal `STOP` the harness
does not select another task or perform automatic cleanup.

---

## 25. Review verdicts and repair flow (operational v2)

The reviewer returns exactly one of `APPROVED`, `CHANGES_REQUESTED`, or
`BLOCKED`, as in v1 (§7). The set is unchanged.

- **Terminal `BLOCKED`.** A valid explicit `BLOCKED` verdict ends the run and
  requires the bounded structured rationale defined below. A missing or
  malformed rationale is a fail-closed non-explicit `BLOCKED`, as is a
  missing, malformed, ambiguous, or unrecognized verdict or a reviewer
  timeout, crash, or execution error. None of these ever starts a repair
  episode, and none is upgraded to `APPROVED`.
- **`APPROVED`.** The current review gate passes and the orchestrator may
  move to the next deterministic phase only after completing the applicable
  material pass with no proven binding defect remaining. The approval criteria
  are identical at every iteration: they are never weakened by how many times
  the gate has already returned `CHANGES_REQUESTED`.
- **`CHANGES_REQUESTED`.** Not terminal. It starts a repair episode, provided
  the reviewer's output contains a complete repair packet proving one or more
  repairable binding defects inside the fixed spec.
- **`BLOCKED`.** Correct continuation requires a missing decision, scope,
  architecture contract, dependency, or other information not supplied by
  the fixed approved contract. It is not a substitute for a repairable
  finding.

A valid explicit `BLOCKED` has exactly one following JSON object with exactly
these required fields: `binding_bases`, `blocker_kind`, `problem`,
`evidence_reference`, `blocking_gap`, and `required_resolution`. The closed
`blocker_kind` taxonomy is `missing_decision`, `missing_scope`,
`missing_architecture_contract`, `missing_dependency`, and
`missing_information`.

`binding_bases` is an ordered list of 1..8 unique strings. Every entry is
non-empty, already trimmed, single-line, at most 512 characters, and valid
under the provider-neutral binding-basis grammar below. `problem`,
`blocking_gap`, and `required_resolution` are each non-empty, already trimmed,
single-line, and at most 1024 characters; `evidence_reference` has the same
requirements with a 512-character limit and is a concise locator or
description, not an evidence-body copy. Validation never normalizes whitespace.
Missing or unknown fields, duplicate JSON keys, wrong types, duplicate or
invalid bases, invalid taxonomy values, and empty, untrimmed, multiline, or
oversized text make the rationale malformed and therefore non-explicit.

`BlockedReviewRationale` is terminal diagnostic evidence, not a
`RepairFinding` or `RepairPacket`. It never starts repair, retry, or candidate
rejection and does not change routing, convergence, or phase transitions.

A repair packet holds one or more findings. Each finding has at least these
required fields, and they are part of the repair handoff contract, not an
advisory format:

- **Binding basis** — the exact binding task section, checkpoint field, or
  repository-contract reference that makes the defect material;
- **Problem** — what is wrong with the candidate;
- **Evidence** — where and how the problem shows in the candidate;
- **Failure mode** — how the candidate violates the binding basis;
- **Required outcome** — the condition the next candidate must satisfy;
- **Recommended repair** — an advisory suggested way to reach it; the binding
  requirement and required outcome, not this suggestion, control the repair;
- **Verification focus** — what the next deterministic verification and
  review should check.

`binding_basis` uses only this provider-neutral grammar:

- `task:goal`, `task:scope`, `task:out_of_scope`,
  `task:approved_implementation_approach`, `task:acceptance_criteria`, or
  `task:full_verification`;
- `checkpoint:CP-N:<field>`, where `N >= 1` and `<field>` is exactly
  `objective`, `required_result`, `constraints`, or `verification`;
- `repo:<non-empty trimmed reference>`.

The `repo:*` form receives syntactic validation only; it introduces no path,
anchor, or requirement registry. `Review focus` is advisory and cannot be a
binding basis. Missing, blank, or malformed `binding_basis` or `failure_mode`
is malformed output under the same fail-closed rule as any other missing
required finding field.

A `CHANGES_REQUESTED` verdict with no finding, or with a finding that lacks
any required field, is malformed reviewer output and ends the run as
`BLOCKED`. Additional provider-neutral structured metadata may accompany a
finding; it never substitutes for a required field.

The operational v2 repair flow is:

```text
review → CHANGES_REQUESTED → implementer repair → deterministic verification → fresh review
```

At the deterministic verification subprocess boundary, only a process that
successfully starts, completes, and supplies strict UTF-8 stdout/stderr
produces a verification-command result. A
real return code of zero passes that command; every real non-zero return code,
including a negative operating-system/process return code, is an ordinary
deterministic candidate-verification rejection. A launch or execution
`OSError`, expiration of the configured timeout, or semantic-output decode
failure is instead verification
execution uncertainty and fails closed terminally. Those exceptions never
become a synthetic verification-command result with return code `-1`.
A deterministic completed failure creates or implies no synthetic reviewer
result.

### External-process semantic and diagnostic output (TSK-0046)

Process status precedes output interpretation. Agent stdin is strict UTF-8
bytes; stdout/stderr are captured as bytes before role-specific decoding.
Only a completed-zero reviewer stdout is semantic protocol input and must
decode as strict UTF-8 before verdict/JSON parsing. Its stderr is diagnostic
only and may be replacement-decoded. Implementer stdout/stderr are also
diagnostic only: malformed diagnostic bytes alone do not reject a completed-
zero implementer candidate, which still must pass repository scope,
verification, and designated review gates.

Agent timeout, launch failure, and successful-reviewer stdout decode failure
are internal process failures (`TIMEOUT`, `LAUNCH_ERROR`,
`OUTPUT_DECODE_ERROR`) with no return code. Completed non-zero exits retain
their actual integer return code. Timeout/non-zero partial output, even an
`APPROVED` token or valid-looking JSON, never reaches the semantic parser.
These failures produce non-explicit terminal `BLOCKED`, without synthetic
reviewer rationale, repair packet, review iteration, retry, or profile fallback.

Git/GitHub stdout and stderr remain strict UTF-8, including required-CI
special-state recognition from stderr. Parsing sees full semantic strings;
invalid decoding or launch `OSError` raises `RepositoryError`. The isolated
index and exact Git blob reader preserve their staging and exact-byte
contracts. Deterministic verification decode failure is terminal uncertainty,
never lossy repair evidence; completed non-zero valid UTF-8 retains the existing
repair behavior. Codex identity decode failure is a launcher configuration
error before delegation.

Diagnostic-only streams may use best-effort UTF-8 replacement decoding.
Each external-output excerpt retained as an agent diagnostic or projected
into a repository error keeps at most 4096 source characters: first 2048
and last 2048 with a fixed truncation marker when oversized. The marker is
outside that source-character budget. Successful semantic reviewer output
is never truncated before parsing. This bounds diagnostic projection, not
subprocess capture, pipe buffers, memory, tokens, or repair work. Concise
agent failure reasons and existing CLI diagnostic allowlists do not expose
raw process transcripts, prompts, argv, environment, or credentials.

Timeout does not prove descendant-process quiescence. Process-tree
containment remains outside this task; timeout, launch, and semantic decode
failures never authorize automatic retry, repair, cleanup, or resume.

A **repair episode** starts with a `CHANGES_REQUESTED` verdict, an initial
implementation before a gate's first review, or a completed deterministic
verification rejection that directly creates a child repair gate. It ends when
a candidate that passed deterministic verification is actually reviewed.

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

The reviewer never edits the authoritative working tree. A provider integration
may permit commands to mutate only its disposable, non-authoritative inspection
snapshot; that snapshot is removed before the verdict is accepted and never
becomes repair input or a source of truth. The repair stays inside the fixed spec
and the approved scope; a repair that would need more than that is a fail-closed
condition (§27).

### Complete material review and gate applicability

Before every verdict, a designated reviewer determines the binding
requirements applicable to that gate, reviews the complete current
`CURRENT_PATCH` embedded in its explicit handoff and supplied deterministic
evidence, and reports all independent material defects found in one
`CHANGES_REQUESTED`. That embedded text is byte-identical to the orchestrator-
owned repository-root `review.patch`; the latter remains the audit artifact and
identity guard rather than a file the reviewer must reopen. A blocking finding
requires a concrete binding basis. Style preferences, optional improvements,
speculative abstraction or generalization, future scope, and advisory
`Review focus` are non-blocking unless a separate binding requirement makes
them material.

On a second-or-later review at the same gate, the reviewer first re-evaluates
the previous findings against the current candidate and repair delta, then
performs a fresh pass over every remaining applicable requirement. The new
repair packet contains defects still material on the current candidate plus
new independent material defects; already-corrected findings need not be
repeated. Fresh reviewer context and the explicit previous-findings/delta
handoff of §29 remain mandatory.

Applicability is gate-specific:

- an ordinary checkpoint review covers task Goal, Scope, Out of scope,
  Approved implementation approach, the current checkpoint's Objective,
  Required result, Constraints and Verification, and applicable repository
  contracts. Final Acceptance criteria and Full verification do not by
  themselves demand future-checkpoint results early;
- the pre-closure cumulative implementation review covers the complete Task
  Execution Spec, every checkpoint, Full verification, and applicable
  repository contracts;
- a late implementation-repair review first checks the current binding
  findings and required outcomes against the repair, then performs a fresh
  task-wide and repository-contract pass. It does not replace downstream
  replay;
- prospective Task Closure review is limited to the exact closure candidate
  diff, factual closure evidence, and closure/terminal/governance requirements;
  it does not repeat the full implementation review;
- Mode C reviews the full final cumulative candidate — implementation plus
  unpublished closure — against the complete applicable task and repository
  contract.

Every candidate-changing implementer handoff also requires an internal,
context-appropriate pre-return conformance pass. Checkpoint and implementation
repair passes cover the binding task boundaries, current checkpoint or repair
requirements, directly implied negative/fail-closed cases, verification
failure evidence, and applicable repository constraints. Closure preparation
and repair use a closure-scoped pass only. The implementer corrects violations
it finds before returning, but this creates no new agent call, gate, verdict,
artifact, authoritative evidence, or reviewer input; designated review stays
fresh and independent.

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
- **Rejected candidate.** A candidate that received `CHANGES_REQUESTED`,
  failed required deterministic verification, or was positively classified
  as failing deterministic prospective Task Closure candidate validation at a
  gate. Rejection by verification or prospective-closure validation involves
  no reviewer verdict.
- **Comparison scope.** Identities are compared only within the same gate,
  fixed spec, and accepted base context. A candidate seen under a different
  context is a different candidate.
- **Direct verification-triggered child repair.** When a completed
  verification failure directly creates a child late-repair gate, the
  unchanged candidate is seeded in that child gate's accepted-base-relative
  candidate space before the first repair attempt. For a mode-A child repair,
  the unchanged candidate is the empty uncommitted delta. This seed exists
  only for no-progress and cycle detection: it creates no synthetic local
  attempt, verification rejection, reviewer verdict, review iteration,
  finding, or repair packet. The fingerprint algorithm and the concrete digest
  of the empty delta remain implementation details, not governance constants.
- **Rule.** When a repair produces a candidate whose identity equals that of
  any candidate already rejected at the same gate and context, the run ends
  as `BLOCKED`: an exact repair cycle, or no progress. This applies equally to
  a repair made after a verification failure or a deterministic prospective-
  closure validation failure. The latter stays in the same Task Closure gate,
  fixed spec, and accepted-base comparison context.

| Sequence at one gate | Outcome |
| --- | --- |
| `A → repair → A` | `BLOCKED` — no progress |
| `A → B → C → B`, with `B` already rejected | `BLOCKED` — exact repair cycle |
| `A → B → C → D → …`, all distinct | not blocked, however many iterations |

Iteration count alone never triggers this rule; only a repeated rejected
identity does. Deterministic prospective-closure validation repair has no
numeric repair limit.

---

## 29. Repair history, reviewer handoff, and freshness (operational v2)

The orchestrator owns the audit history of a gate. For every candidate or
repair attempt it records the orchestration facts that apply to it:

- the gate or checkpoint;
- the candidate's fingerprint or identity;
- the verification evidence;
- whether the candidate was rejected, and on what basis (a reviewer
  `CHANGES_REQUESTED`, a verification failure, or a positively classified
  deterministic prospective-closure validation failure);
- for an attempt produced by a repair, the repair delta or its fingerprint and
  the resulting candidate state.

Only when a designated review actually took place for the attempt does the
record also hold the review iteration, the reviewer verdict, and the findings.
An attempt rejected by verification or deterministic prospective-closure
validation has no reviewer iteration, verdict, findings, or `RepairPacket`,
and no synthetic reviewer result stands in for them.

For a valid explicit reviewer `BLOCKED`, `GateAttempt` also stores the typed
`BlockedReviewRationale`. That attempt has no findings or repair packet, is not
marked rejected, and has no rejection basis. Malformed reviewer output and
orchestrator-owned blockers never receive synthetic rationale.

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

`previous_reviewed_candidate_identity` and
`previous_reviewed_candidate_state` retain their literal meaning: they refer
only to a candidate actually seen by the designated reviewer. A deterministic
prospective-closure validation rejection does not populate them. Its dedicated
closure-validation-failure handoff is mechanical candidate-validation input
for the next Task Closure implementer invocation, not reviewer feedback,
findings, deterministic command-verification evidence, or a replacement for a
reviewer `RepairPacket`.

For the gate's first review, none of the last two items exists: the handoff is
the fixed Task Execution Spec, the current gate or checkpoint, the current
candidate patch, and the passing deterministic verification result, with
review iteration number 1. No synthetic previous findings and no synthetic
delta are created to fill the missing items.

Every designated review stays fresh and independent: `implementer context !=
designated reviewer context` (§5) holds at every review. Adaptive repair
never continues an earlier reviewer conversation, and review correctness never
depends on hidden reviewer state that is absent from this explicit handoff.

### Review-convergence diagnostics

For every gate history that reached an explicit designated-reviewer verdict,
the orchestrator derives one immutable in-memory `ReviewGateMetrics` value.
Distinct histories remain distinct even when they share a gate ID; occurrence
order is preserved. A run with no designated review activity has no metrics.
Each metric contains:

- gate ID;
- total designated-review iterations;
- total `CHANGES_REQUESTED` review iterations;
- count of attempts rejected by deterministic verification;
- finding counts and ordered binding-basis strings per review iteration;
- binding bases first seen in a `CHANGES_REQUESTED` after review iteration 1;
- binding bases present in `CHANGES_REQUESTED` on more than one distinct
  review iteration, ignoring duplicates within one packet;
- the last actual explicit reviewer verdict.

`APPROVED` and explicit `BLOCKED` review iterations have zero findings.
Verification failures have no synthetic reviewer verdict but remain visible in
their gate's verification-rejection count. Derived basis collections use
deterministic first-seen order. The CLI emits one stable
`review_metric_json: ` JSON line per metric, with the verdict token or `null`,
and never emits prompts, patches, secrets, hidden reasoning, or full evidence.

These diagnostics are a pure read-only projection of existing in-memory
history. They add no persistence or timestamps and are never input to verdict,
retry, no-progress, replay, phase-transition, or merge-readiness decisions.

### Explicit-BLOCKED diagnostics

The orchestrator derives one immutable `BlockedReviewDiagnostic` for every
valid explicit `BLOCKED` attempt retained in `GateHistory`, preserving history
and attempt occurrence order. It contains the gate ID, actual review iteration,
exact candidate identity, and typed rationale. `RunResult.blocked_reviews` is
the default-empty ordered tuple of those diagnostics. A syntactically valid
review invalidated by freshness or revalidation before canonical
`GateAttempt` recording is discarded and cannot become terminal diagnostic
evidence.

The CLI emits one compact deterministic `review_blocked_json: ` line per
diagnostic. It manually projects exactly `gate_id`, `review_iteration`,
`candidate_digest`, `binding_bases`, `blocker_kind`, `problem`,
`evidence_reference`, `blocking_gap`, and `required_resolution`, where
`candidate_digest` is the exact `CandidateIdentity.digest`. Keys are sorted and
compact JSON separators are used. The existing generic `blocked_reason`
remains a separate control-level line.

This projection is diagnostic-only and has no control-flow ownership. It does
not serialize `StructuredReviewResult`, `GateAttempt`, or other internal
objects wholesale and never projects raw reviewer output, stdout/stderr,
prompts, patches, the Task Execution Spec, Mode C evidence bodies, argv,
model/provider arguments, environment, credentials, or hidden reasoning.

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
preflight (fresh fetch/capture origin/main SHA → clean worktree/index
  → exact local HEAD == captured SHA → terminal registry + task catalog
  → selector)
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

**Outer execution prerequisite.** Harness-owned mandatory Git/GitHub
operations require an outer operator execution context already capable of
performing those operations. The harness does not escape or reconfigure its
parent sandbox and does not turn product execution permission into additional
repository authority. The mandatory fresh `git fetch origin` remains required:
an unavailable or denied outer capability fails closed, with no cached-ref,
caller-supplied-SHA, GitHub-API, or direct-caller Git/GitHub fallback.

**Preflight.** The orchestrator freshly fetches and captures one exact
`origin/main` SHA, requires the worktree/index to be clean, reads the exact
local `HEAD`, and requires literal SHA equality between that local runtime and
the captured base. Only after those checks does it read from the captured SHA
the strict terminal registry and every regular Git-tracked canonical task blob,
validate all nonterminal envelopes/bodies and their dependency graph, and
resolve exactly one explicit ID or `NEXT`.

The runtime identity invariant is commit-based, not branch-name-based: local
`main`, a differently named branch, or detached `HEAD` is acceptable at the
exact captured SHA. A clean checkout behind or ahead of the freshly captured
base fails closed in `PREFLIGHT` before catalog/selector resolution or delivery
side effects. The harness does not pull, reset, checkout, switch, merge,
rebase, update refs, restart/re-exec Python, retry, or resume automatically.
The operator must update the selected checkout outside the ended invocation and
start a new explicit invocation. Once initial equality succeeds, later
`origin/main` movement continues to use the existing fixed-target
revalidation, cumulative-review, Mode C, publication, and required-CI rules;
it is not reclassified as an initial-runtime mismatch.

Dependencies must be terminal `Done`; `Superseded`, open, unknown, self,
duplicate, or cyclic dependencies do not permit execution. The selected task
must be approved, execution-ready (§22), and inside permitted Roadmap scope.
Missing selector is configuration error; invalid/draft/terminal explicit ID
has no fallback. `NO_ELIGIBLE_TASK` is a successful no-work result, not a
reviewer verdict.

A failed check ends the run as `BLOCKED`. Later revalidation rereads only the
strict terminal registry, exact selected document, and its dependencies from
one fresh exact SHA. It never recalculates `NEXT` or rejects the fixed target
because an unrelated document changed. Selected document/approval changes,
lost `Done` dependencies, or a concurrent terminal outcome fail closed.

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
before Task Closure exists on the branch, it satisfies the pre-closure
implementation-review prerequisite, and it is not Mode C.

Full verification has one repair-aware pre-closure control path. A completed
non-zero result rejects the current implementation candidate and enters the
existing implementation-repair machinery; it does not synthesize reviewer
findings or a verdict. Each distinct repair candidate must pass the exact Full
verification commands and then receive a fresh implementation-repair review.
Only `APPROVED` reaches the existing acceptance commit/push boundary. The
accepted repair then starts conservative replay at CP-1; after every declared
checkpoint has fresh accepted evidence, the orchestrator runs a fresh
authoritative Full verification on the resulting accepted HEAD, rebuilds
`origin/main...HEAD`, and obtains a fresh cumulative implementation review.

An `OSError` or timeout while executing Full verification is execution
uncertainty, not candidate evidence. It remains terminal fail-closed in the
Full Verification phase and invokes no Full Verification repair implementer
or reviewer.

A `CHANGES_REQUESTED` from the cumulative review follows the adaptive repair
contract (§25–§29). A repair invalidates evidence built against the old
candidate (§33). Once such a repair is made, at least the following happens
before approval can be reached: deterministic verification and review of the
repair; commit and push of the accepted repair to the delivery branch; the
conservative checkpoint replay required by §33; return to the same top-level
Full verification control point; a rebuilt cumulative diff over
`origin/main...HEAD`; and a fresh cumulative review. An earlier cumulative
approval is never carried over to a new candidate.

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
→ deterministic closure-evidence consistency validation
→ prepare prospective Task Closure
→ closure review APPROVED
→ create the local closure commit (the unpublished closure candidate)
→ fresh origin/main revalidation
→ Mode C
```

Before any prospective-closure implementer or reviewer invocation, the
orchestrator deterministically validates that successful Full Verification and
the accepted cumulative review belong to the fixed spec, one accepted base and
the exact expected published implementation HEAD. It also checks the nested
verified HEAD, candidate identities, cumulative patch identity and original
Full Verification argv/results. Missing, failed, stale, or inconsistent
evidence fails closed before an LLM can infer freshness. The same validation
produces one compact in-memory representation containing the selected
task/spec, actual draft PR number, accepted base/HEAD, per-command original
argv/returncode/pass facts, and cumulative-review identity/iteration; it is not
a persisted lifecycle schema and excludes successful stdout/stderr, parsed
test counts, runtime interpreter materialization, and provider/model identity.
That freshly recomputed representation is handed unchanged to both the Closure
implementer and the fresh Closure reviewer. The implementer additionally keeps
the accepted implementation patch as the factual delivery-summary source; the
reviewer receives only the exact prospective closure diff as `CURRENT_PATCH`
plus the compact evidence; the full accepted implementation patch is never
included in that reviewer handoff, and Closure Review does not repeat the
pre-closure cumulative implementation review. Closure-only repair may reuse
the still-current typed evidence only after deterministic revalidation and
fresh formatting. An implementation-affecting repair invalidates the stale
downstream Full Verification and cumulative-review evidence, completes the
existing conservative replay, and produces new Full Verification and a new
accepted cumulative review before another closure handoff is built.

Before a prospective-closure defect can be classified as candidate-local and
sent to Task Closure repair, the orchestrator positively parses the immutable
authoritative `docs/TASK.md` baseline and proves that the selected task is not
already terminal there. Baseline parse failure, an already-terminal selected
task, any disallowed changed path, and any repository read/staging/integrity
failure remain terminal `BLOCKED`. Once baseline validity and the closure-only
path boundary are established, deterministic candidate-local defects — such as
missing required closure-file changes or strict terminal-only row validation
failure — reject that candidate inside the existing Task Closure repair
episode. A distinct repaired candidate that passes deterministic validation
still requires fresh independent Closure Review. After that review approves,
the existing local unpublished closure commit → fresh `origin/main`
revalidation → Mode C → exact publication → required CI sequence is unchanged.

Before every Mode C reviewer invocation, including a rebuilt pre-publication
candidate and a post-publication replay, the orchestrator freshly validates and
projects the accepted Full Verification and cumulative-review provenance from
typed in-memory state. The nested evidence's historical accepted implementation
base and the fresh Mode C audit base have different roles and need not be equal:
after successful unrelated `origin/main` revalidation, the former may remain
`A` while the latter becomes `B`. The exact candidate's
`published_predecessor_sha` must still equal the Full Verification HEAD, its
nested verified HEAD, and the cumulative reviewed implementation HEAD. The
compact projection is ephemeral and rebuilt for each invocation; no earlier
Closure or Mode C prompt string is authoritative state. It includes the actual
draft PR context and original verification argv/result facts, but no successful
stdout/stderr, machine-specific interpreter path, parsed test counts, raw agent
output, or provider/model identity. The accepted provenance proves prerequisite
identity and freshness facts but never replaces the fresh independent Mode C
material review. Mode C receives no duplicate accepted-implementation patch:
its exact `CURRENT_PATCH` remains the final cumulative implementation plus Task
Closure patch from the current audit base to the exact candidate HEAD.

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
  automatically under this general rule. A more specific conservative replay
  rule can require an earlier boundary: the accepted implementation repair
  directly triggered by Full verification rejection below invalidates and
  replays from CP-1. If the repair changes the result of a previously approved
  upstream checkpoint, that checkpoint's approval is stale too, and it and
  every checkpoint and gate after it are replayed.
- When the orchestrator cannot establish deterministically the earliest
  checkpoint a repair affects, it chooses the broader conservative replay, up to
  all relevant checkpoints.
- No approval is carried over merely because it was `APPROVED` earlier.
- The orchestrator may replay more gates than the minimum. It may never replay
  fewer than needed to exclude stale evidence.
- If safe replay is impossible, the run ends as `BLOCKED` (§27).

An accepted implementation repair triggered directly by Full verification is
always treated conservatively as task-wide: all previously accepted
checkpoint evidence is invalidated from CP-1, together with downstream Full
verification and cumulative-review evidence. Every declared checkpoint is
then replayed in order. The passing verification of the uncommitted repair
candidate establishes eligibility for its fresh repair review only; after the
repair is accepted and committed and checkpoint replay completes, that earlier
result is not final accepted Full Verification evidence. Only a new passing
Full verification bound to the post-replay accepted HEAD may be promoted for
downstream closure and Mode C.

For an implementation-affecting repair made from a late gate — the
pre-closure cumulative review, the closure review, or Mode C — the current
implementation uses the broader conservative replay from CP-1:

```text
repair
→ deterministic verification and review of the repair (§25–§29)
→ APPROVED
→ commit and push the accepted repair to the delivery branch
→ replay every declared checkpoint from CP-1 with fresh verification and review
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
repair after publication. A real required-CI failure or cancellation is
therefore terminal `BLOCKED`, as is a Mode C `CHANGES_REQUESTED` obtained by
rebuilding Mode C after `origin/main` moved post-publication (§32). If it cannot
yet perform a safe post-publication replay, it ends the run as `BLOCKED`. This
is an implementation limitation, not a governance rule. Safe post-push replay
and persisted resume are a separate future task.

A rebuilt Mode C that approves the same published candidate needs no repair and
does not by itself stop the run.

That post-publication rebuild carries the same historical accepted Full
Verification/cumulative-review provenance for the unchanged exact published
candidate, while constructing a fresh `FINAL_CUMULATIVE_AUDIT` patch and Mode C
projection from the newly revalidated current audit base. It repeats the same
candidate-predecessor/verified-HEAD validation as initial Mode C and then
replays the same required-CI observation path under the existing ordering.

Required CI is observed through the one-shot structured repository boundary,
but bounded waiting belongs to the orchestrator. The outcomes have distinct,
fail-closed meanings:

- `no checks reported on the '<branch>' branch` is a transient registration
  observation. It is not evidence that the required set is empty and never
  satisfies the gate directly.
- `no required checks reported on the '<branch>' branch` is the separately,
  positively recognized empty required set. It satisfies the gate immediately;
  optional workflows do not thereby become mandatory.
- Real required checks containing `fail` or `cancel` are terminal, including
  when another required check is still `pending`. Otherwise pending required
  checks are observed again boundedly; only a consistent successful result
  containing `pass`/`skipping` satisfies the real-check path.
- Every observation is bound to the exact published candidate: the draft PR
  head must equal that candidate SHA both before and after the one-shot checks
  query. Head movement fails closed, and evidence read for the old head is not
  reused.

The bounded loop uses one monotonic deadline from the separate finite
required-CI observation timeout. The first observation is immediate; after a
transient result, sleep is capped by the remaining deadline, and no further
head/check observation begins once that deadline has expired. Persistent
check-registration and pending states produce distinguishable `BLOCKED`
diagnostics. This timeout is a safety boundary for passive observation, not a
numeric repair budget. Polling creates no implementer or reviewer invocation,
repair packet, review iteration, routing decision, compute escalation, or
candidate mutation, and it does not change review/routing metrics.

After required CI succeeds (including the recognized empty-required-set
outcome), the existing fresh `origin/main` revalidation still runs. Safe
post-publication movement rebuilds Mode C for the same exact published
candidate and then uses this same bounded required-CI path again. The
orchestrator does not poll `origin/main` in parallel with CI and adds no REST,
branch-protection, or ruleset-discovery semantics to infer repository policy.

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

---

## 36. Deterministic adaptive compute routing (operational v2)

Every operational implementer and designated-reviewer invocation is routed by
the orchestrator through one of three closed, provider-neutral compute
profiles: `ROUTINE`, `DELIBERATE`, or `CRITICAL`. These names express relative
reasoning budget only. They do not name a provider, model, executable, or
entitlement, and the agent cannot select or alter its own profile.

The baseline profile is determined only by role and explicit work kind:

| Role | Work kind | Baseline |
| --- | --- | --- |
| Implementer | initial ordinary checkpoint | `ROUTINE` |
| Implementer | implementation repair | `DELIBERATE` |
| Implementer | initial Task Closure preparation | `ROUTINE` |
| Implementer | Task Closure repair | `DELIBERATE` |
| Reviewer | ordinary or replayed checkpoint review | `DELIBERATE` |
| Reviewer | implementation-repair review | `DELIBERATE` |
| Reviewer | pre-closure cumulative implementation review | `CRITICAL` |
| Reviewer | Task Closure review | `DELIBERATE` |
| Reviewer | Mode C, including post-publication replay | `CRITICAL` |

Each decision is recomputed from that baseline and structured local facts; the
orchestrator stores no mutable current profile and has no upgrade/downgrade
state machine. For an implementation or closure repair, the selected profile
becomes `CRITICAL` when either:

- the cumulative deterministic verification-rejection count in the current
  causal repair episode is at least two, including a directly seeded upstream
  verification failure; or
- an exact `binding_basis` in the packet controlling the next repair occurred
  in an earlier packet of that causal episode, including a direct upstream
  seed. Non-adjacent repetition such as `A → B → A` therefore escalates, while
  a new basis alone does not.

A direct upstream verification failure contributes exactly one existing
`seed_verification_rejection_count` to the child repair episode. The rejected-
identity seed used for no-progress detection (§28) is separate state and does
not add to that count. The upstream failure is not also inserted into the child
history as a local `VERIFICATION_FAILURE` attempt; doing so would double-count
one causal rejection. A later completed non-zero verification of a distinct
local repair candidate is the first local verification-rejection attempt and
combines with the single upstream seed under the unchanged threshold above.
The routing baselines and escalation thresholds are otherwise unchanged.

A deterministic prospective Task Closure validation rejection is not a
verification rejection and does not increment the verification-rejection
count or create `REPEATED_VERIFICATION_REJECTION`. It selects the existing
`TASK_CLOSURE_REPAIR` work kind, whose baseline remains `DELIBERATE`; the
baseline routing table above and its verification-specific escalation policy
are unchanged.

For a reviewer whose baseline is not already `CRITICAL`, review iteration 2 or
later in the same gate is `CRITICAL`. The first review of a repair candidate
created directly from an upstream `RepairPacket` is also `CRITICAL`. A seeded
verification failure without an upstream packet does not by itself escalate
that first repair review. `CRITICAL` is saturating but is never a repair limit
or a terminal condition.

A direct upstream packet or verification failure crosses only into the child
repair episode it causally creates. Local review and verification rejections
then extend that episode. Acceptance ends the lineage: the next independent
checkpoint, replay gate, closure preparation, or new run starts from its own
baseline unless it receives a new explicit direct causal seed. In particular,
a `CRITICAL` cumulative review does not make initial closure preparation more
than `ROUTINE`.

### External-process profile boundary

Each role retains exactly one configured executable and one role-common argv.
Required profile-specific argv are appended to that common argv to materialize
the selected invocation. Implementer configuration supplies distinct mappings
for all three profiles; reviewer configuration supplies distinct mappings for
`DELIBERATE` and `CRITICAL`. Missing, empty, or indistinguishable required
mappings fail configuration before the first agent invocation.

Materialization preserves the role, executable, working directory, timeout,
environment, fresh-context assertion, edit capability, and Git/GitHub
write-capability assertion. Routing never switches provider or executable and
never weakens the reviewer isolation or no-write requirements of §5 and §8.
Failure of the selected external profile follows the existing fail-closed
agent-failure path; there is no fallback to another profile, executable,
provider, or model.

### Routing diagnostics

Immediately after a deterministic decision and before its subprocess starts,
the orchestrator appends one immutable `RoutingDecisionRecord` to the current
run's in-memory sequence. A record contains only:

- monotonic per-run sequence;
- role and work kind;
- gate ID;
- baseline and selected profiles;
- closed-set escalation reasons.

Consequently a timeout, launch error, or non-zero result from the selected
process does not erase its routing record. Successful, blocked, and partially
progressed run results retain records already made. `NO_ELIGIBLE_TASK` and a
failure before the first routed invocation have an empty tuple, and every new
`run()` starts its sequence again at one.

The CLI emits one deterministic, sorted-key `routing_decision_json: ` JSON line
per record. It never includes prompts, patches, agent stdout/stderr, full or
profile argv, environment values, credentials, provider-sensitive values, or
hidden reasoning. Records are append-only in-memory diagnostics: they are not
persisted or resumable state, the router never reads them, and neither they nor
`ReviewGateMetrics` affect routing, verdicts, retry, no-progress detection,
replay, phase transitions, publication, CI, or merge readiness.

---

## 37. Windows Verification Containment (contract; runtime not implemented)

### 37.1. Authority, scope, and delivery status

This is the normative Windows deterministic-verification process contract
under [Architecture §13](ARCHITECTURE.md#13-windows-verification-containment)
and [DEC-0055](DECISIONS.md#dec-0055--windows-deterministic-verification-has-an-owned-containment-boundary).
It specifies a future backend; C0 contains no production implementation or
activation. A proposed documentation diff is not publication on `main`.
Implementation must follow separately reviewed and authorized MANUAL work
after canonical C0 publication. Native validation and production wiring have
the additional gates in §37.11. No new dependency is authorized.

The sole integration point is `_run_one_verification_command()` for checkpoint
and Full verification commands. Use an isolated Windows adapter for H-side
ownership/lifecycle and a private worker module for W-side capture; neither is
imported on non-Windows. No general subprocess framework is introduced.
`run_agent()`, Codex/MXC, Git/GitHub subprocesses, repository mutation guards,
Task dispatch, acceptance, reviewer parsing, repair, routing, CI and merge
authority retain their contracts. The public result and lifecycle vocabulary
are unchanged. This section grants no `AUTONOMOUS_PR` invocation authority.

Part I and §25's TSK-0046 record remain unchanged. TSK-0045's distinction
between completed rejection and terminal execution uncertainty still binds.
TSK-0046 did not deliver descendant containment or authorize cleanup following
its process failures. This new contract adds only the explicitly owned-resource
cleanup below when the future backend is delivered; it never authorizes
automatic retry, resumed runs, candidate repair or reviewer/profile fallback
on uncertainty. Until then the existing `subprocess.run` behavior remains.

### 37.2. Ownership and atomic launch

For each verification command invocation, the roles and ownership are:

| Role/object | Owner and permitted capability |
| --- | --- |
| H | Existing orchestrator process; sole authoritative lifecycle, deadline and result owner; outside both newly created Jobs |
| W | Exactly one additional subordinate watcher process; owns capture operations, their buffers/events and its transferred capabilities |
| Payload | Original verification command; receives only whitelisted standard-stream handles |
| `J_supervision` | Fresh dedicated unnamed Job containing W, payload and ordinary descendants; its main handles remain exclusively in H |
| `J_command` | Fresh dedicated unnamed nested Job containing payload and ordinary descendants, excluding W; H owns main handles; W receives only `JOB_OBJECT_TERMINATE` |

H sets and verifies `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` on both Jobs. Neither
Job permits breakaway, including silent breakaway. No external Job is queried
for accounting, reconfigured, terminated or given new limits. Existing outer
Job constraints must either permit validated nesting or cause failure before
payload resume. There is no elevation, breakaway, alternate launcher,
post-launch `AssignProcessToJobObject`, uncontained fallback, arbitrary-PID or
executable-name termination, existing ACL mutation, or third supervisor.

H retains worker/root process and primary-thread handles, Job handles, main
IPC references, temporary writers and deadline state with one explicit owner
per handle-table entry. Process/thread references are retained until verified
exit/code facts are cached, then checked-closed before the relevant final Job
samples as specified in §37.8; simultaneous retention and zero accounting is
not required. W's retained H-process handle has only `SYNCHRONIZE |
PROCESS_QUERY_LIMITED_INFORMATION` for liveness and identity, not termination
or mutation rights. W cannot configure either Job, assign processes, or retain
a `J_supervision` handle. No escaped reference may defeat H-crash kill-on-close.

Use checked `STARTUPINFOEX` attribute-list setup with
`EXTENDED_STARTUPINFO_PRESENT`, `CREATE_SUSPENDED` and
`PROC_THREAD_ATTRIBUTE_JOB_LIST`. W is atomically assigned to `J_supervision`
at creation. Payload is atomically assigned to ordered
`[J_supervision, J_command]` at creation. H verifies W membership before W
resume and verifies both payload memberships before payload resume. Failed
ABI/API/Job/attribute-list/creation/duplication/membership/close/resume checks
are terminal; a suspended process is cleaned up through its owned Job, never
resumed to make cleanup easier. Resume is checked and attempted at most once
per process; an unexpected suspension state is failure.

Only supported native Windows with `PROC_THREAD_ATTRIBUTE_JOB_LIST` is
eligible (Windows 10 / Windows Server 2016 or newer). The initial implementation
must validate its 64-bit CPython/Win32 ABI: pointer widths, structure sizes,
alignment, API signatures, flags and return/error conventions. An unverified
ABI or unavailable feature fails closed before payload resume. A successful
version check alone is not native proof.

### 37.3. One-shot worker bootstrap and capability confinement

H creates a private unnamed 4096-byte pagefile-backed bootstrap file mapping
and keeps a writable view. W's creation handle whitelist contains only one
read-only inheritable bootstrap mapping handle. This is the sole bootstrap
exception to non-inheritable working-capability transfer. Its process-local
numeric identity may appear in worker argv; secrets, environment, full payload
argv, tokens and transcripts must not. No pseudo handle is inherited.

After W creation, while W is suspended, H duplicates the required capabilities
into W's handle table as restricted **non-inheritable** entries. Every
`DuplicateHandle` result and granted-access provenance must be checked. The
closed role set is `command_job`, `parent_process`, `stdout_server`,
`stderr_server`, `h_to_w_mapping`, `h_to_w_free`, `h_to_w_ready`,
`w_to_h_mapping`, `w_to_h_free`, `w_to_h_ready`. The Job and process rights are
as in §37.2; pipe capabilities are inbound/read-only; the H→W mapping is
read-only in W and W→H mapping permits W publication. W can release H→W `free`
and wait on its `ready`, wait on W→H `free` and release its `ready`; semaphore
rights are limited to those operations. No working capability is passed by
environment, object-name reopening, unrestricted inheritance or runtime frame.

The bootstrap representation is fixed: bytes 0–3 are ASCII `WVB1`, bytes 4–7
are a little-endian uint32 JSON byte length in 1..4088, followed by that many
strict UTF-8 bytes and zero padding to 4096 bytes. The exact JSON keys are `version` (exact
integer 1), `run_uuid` (canonical lowercase hyphenated UUID), `parent_pid`,
`worker_pid` (nonzero uint32), `deadline_ns` (monotonic uint64),
`capability_count` (exact integer 10), and `capabilities` (an object with exactly
the ten roles above, each a nonzero uint64 worker-local handle value fitting
the validated ABI). Duplicate keys, unknown roles, duplicate handle entries,
missing/uninitialized entries, nonzero padding, invalid lengths/types or
provenance mismatch fail closed. This is bounded metadata, not a third runtime
SPSC ring. The bootstrap deadline lets W monitor execution before INIT arrives;
INIT must agree with it and the fixed cleanup budget.

H completes and validates the final record only after all duplications
succeed and before W resume. H checked-closes temporary inheritable copies
before resume. W immediately validates magic, version, length, UUID, its own
PID and H identity via the retained handle, capability count/types, expected
access and creation/duplication provenance. Capability validation combines H's
checked creation/duplication ledger (including exact requested access masks)
with W's sealed-role, handle-flag, parent/pipe identity and mapping/use checks.
Provenance is the trusted H-to-W transfer, not independent attestation of H by
W. W must not destructively probe a termination capability, add Job query rights
or use undocumented native introspection merely to re-derive the grant mask.
A failed required availability/use check is terminal. W clears bootstrap-handle
inheritability with a checked call, then unmaps and checked-closes bootstrap
resources after successful receipt. H also retires its view/handles with
checked operations. W must not infer rights merely from a numeric handle or
open H by PID to replace the retained identity.

Payload's separate `PROC_THREAD_ATTRIBUTE_HANDLE_LIST` contains only temporary
inheritable stdin/stdout/stderr duplicates, with `STARTF_USESTDHANDLES` and
the required explicit inheritance setting. It never contains bootstrap, Job,
IPC, W-control or parent-process handles. Preserve inherited stdin semantics
without changing the caller's stdin handle, adding an input protocol or
opening a substitute device on failure. W creation must not inherit payload
writers. H checked-closes every extra writer reference before payload resume.

The controlled boundary must not perform concurrent broad-inheritance launches.
Temporary inheritable handles in multithreaded H can still be inherited by a
foreign concurrent broad launch; minimize the interval and record this residual
risk. Absolute isolation from arbitrary unrelated H threads is not claimed.

### 37.4. Private two-stream capture and command compatibility

H creates exactly two private named-pipe server instances, one per stream:

- `CreateNamedPipeW` open mode is `PIPE_ACCESS_INBOUND |
  FILE_FLAG_OVERLAPPED | FILE_FLAG_FIRST_PIPE_INSTANCE`;
- pipe mode is `PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT |
  PIPE_REJECT_REMOTE_CLIENTS`, maximum instances 1, nominal input buffer
  65536 bytes, output buffer 0, non-inheritable server handle;
- names have the form `\\.\pipe\wvc.<run_uuid>.<nonce>.<stdout|stderr>`,
  generated once per invocation; an explicit security descriptor grants the
  required access only to the current logon SID. This secures new objects,
  without changing any existing filesystem/object ACL;
- H opens each write-only client exactly once with synchronous `CreateFileW`,
  `OPEN_EXISTING`, no `FILE_FLAG_OVERLAPPED`, non-inheritable handle and
  anonymous security QoS. Busy, collision, access denial or unexpected peer
  is terminal, without name retry, reconnect or fallback.

H transfers server ownership to W through checked duplication and checked
closure of H's server copies. W validates `GetFileType`, `GetNamedPipeInfo`,
endpoint provenance and `GetNamedPipeClientProcessId == H` before READY.
Each stream has its own manual-reset event, OVERLAPPED and live read buffer.
`ConnectNamedPipe` must use non-null OVERLAPPED: TRUE means completed;
`ERROR_PIPE_CONNECTED` means the client connected before the wait and is not
an unsignaled pending operation; `ERROR_IO_PENDING` requires finite completion
or cancellation. Both connection orders must work. Anonymous `CreatePipe`
and synchronous read endpoints cannot implement this contract. No blocking
NULL-OVERLAPPED connect, `WaitNamedPipe`, `CallNamedPipe` or
`FlushFileBuffers`-as-EOF gate is allowed.

W services stdout/stderr independently and fairly. A zero-byte successful
read or zero-length write is not EOF. EOF requires a verified pipe-end condition
consistent with closure of all write-side references, including descendants;
`ERROR_MORE_DATA` on a byte pipe is not manufactured EOF. Root exit alone does
not close a descendant's writer. No bytes are discarded or replacement-decoded.

Execution retains shell-free argv, `cwd=config.repo`, inherited effective
environment and stdin, CPython Windows quoting and executable resolution.
Only exact argv[0] `"python"` is materialized as `sys.executable` by the
orchestrator; approved argv and evidence retain the original token. No other
token, PATH, interpreter discovery or fallback chain changes. In particular,
setting `lpApplicationName=argv[0]` is not presumed equivalent to existing
CPython behavior. Empty/spaced/quoted/Unicode arguments and executable search
must receive explicit compatibility proof; unsupported parity fails closed.

### 37.5. WVC1 runtime transport and wire grammar

There are exactly two unnamed pagefile-backed runtime SPSC queues, H→W and
W→H. Each has eight slots of `64 + 65536` bytes and two semaphores, `free=8`,
`ready=0`, each with maximum count 8. Total slot storage is **1,049,600 bytes**,
excluding mapping/synchronization/runtime overhead. Producer and consumer keep
local monotonically advancing slot indices modulo eight; no third runtime
queue is permitted. Bootstrap is separate (§37.3).

Producer waits finitely for `free`, writes the complete header/body, then
checked-releases `ready`. Consumer waits finitely for `ready`, validates and
consumes the complete slot, then checked-releases `free`. Semaphore ordering
must provide publication visibility; no half-written slot is accepted. Every
`ReleaseSemaphore`, including a returned free slot, is checked. Failed wait,
publication, release or peer death is terminal, never a successful empty queue.

The header has no native padding; all integers are little-endian:

| Byte offset | Field | Bytes |
| --- | --- | --- |
| 0 | Magic ASCII `WVC1` | 4 |
| 4 | Version uint16, exactly 1 | 2 |
| 6 | Type uint16 | 2 |
| 8 | Run UUID, RFC UUID byte order (`UUID.bytes`, not `bytes_le`) | 16 |
| 24 | Per-direction sequence uint64 | 8 |
| 32 | Stream offset uint64 | 8 |
| 40 | Payload length uint32 | 4 |
| 44 | Stream ID uint8 | 1 |
| 45 | Flags uint8, exactly 0 | 1 |
| 46 | Reserved, all zero | 18 |

Type IDs are closed: `INIT=1`, `READY=2`, `ROOT_CREATED=3`, `DATA=4`, `EOF=5`,
`FINISH=6`, `ACK=7`, `ERROR=8`, `CANCEL=9`. Streams are `control=0`, `stdout=1`,
`stderr=2`. H→W allows only INIT, ROOT_CREATED, FINISH, CANCEL. W→H allows only
READY, DATA, EOF, ACK, ERROR. DATA/EOF require stream 1 or 2; every other type
requires control and offset 0. Sequence starts at zero independently in each
direction, increases exactly by one for every frame and never wraps.

DATA is 1..65536 raw output bytes, never JSON. Each stream begins at offset 0;
the next DATA offset equals its previous end, independently of interleaving.
EOF uses a strict UTF-8 JSON body of at most 4096 bytes with exactly
`total_bytes` (uint64) and `sha256` (64 lowercase hexadecimal characters).
Its header offset equals `total_bytes`. H recomputes length/hash over raw DATA;
empty streams require length zero and the empty-byte SHA256. Exactly one EOF
per stream is required. Duplicate EOF, hash/length mismatch, missing bytes,
DATA after EOF, ERROR/CANCEL-as-EOF and offsets overflowing uint64 are invalid.

All control bodies are strict UTF-8 JSON objects, at most 4096 bytes, with
exactly these keys and types:

| Type | Required fields |
| --- | --- |
| INIT | `run_uuid`: canonical lowercase hyphenated UUID matching header/bootstrap; `deadline_ns`: uint64; `cleanup_budget_ns`: uint64 exactly 5000000000; `worker_pid`: nonzero uint32 matching W |
| READY | `worker_pid`: matching nonzero uint32; `stdout_ready`, `stderr_ready`: bool, both true |
| ROOT_CREATED | `root_pid`: nonzero uint32 matching retained root; `created_suspended`: bool true |
| FINISH | `root_pid`: matching nonzero uint32; `root_exit_code`: uint32; `command_quiet`: bool true |
| ACK | `pending_io_zero`, `capture_handles_closed`: bool, both true |
| ERROR | `stage`, `category`: closed strings below; `winerror`: uint32 or null; `errno`: nonnegative int32 or null; `timed_out`, `cleanup_confirmed`: bool |
| CANCEL | `reason`: closed string below |

Reject duplicate, unknown or missing keys, coercion, boolean-as-integer,
non-integral/negative/out-of-range numbers, unknown version/type/UUID/stream,
flags, nonzero reserved data, malformed lengths, invalid UTF-8 and sequence
gaps/duplicates/reordering. Timing values are shared-clock monotonic uint64
nanoseconds, never wall-clock timestamps. Expected capabilities are conveyed
only in bootstrap; INIT verifies that accepted bootstrap and its deadline,
not an additional runtime capability list.

The following enum sets are exhaustive, not suggested examples:

- `stage`: `preflight`, `jobs`, `bootstrap`, `pipes`, `worker`, `payload`,
  `stream`, `ipc`, `deadline`, `quiescence`, `cancel`, `cleanup`, `close`, `decode`;
- `category`: `os_api`, `unsupported_platform`, `ownership`, `invalid_handle`,
  `invalid_peer`, `protocol`, `timeout`, `capture`, `decode`, `resource`,
  `unexpected_exit`, `uncertain_state`;
- CANCEL `reason`: `execution_timeout`, `failure`, `worker_failure`, `cleanup`.

No control body contains raw handles, paths, full argv, transcripts, prompts,
environment, credentials, tokens or exception text. DATA alone carries semantic
output, which never becomes diagnostic metadata. Frames assert protocol state;
they are never authoritative proof of Job membership, root exit or quiescence.
W cannot confirm whole-lifecycle cleanup with its limited capabilities:
its ERROR `cleanup_confirmed` must be false. H determines final cleanup status.

### 37.6. Lifecycle and acceptance transaction

Normal ordering is binding:

1. H records `t0` immediately before entering the Windows backend, then prepares
   Jobs, pipes, IPC, bootstrap and suspended W, verifies membership/transfers,
   retires temporary bootstrap inheritance and resumes W once.
2. H publishes INIT after W resume, without waiting for a separate bootstrap
   acknowledgement. W first accepts bootstrap, then validates INIT, both capture
   endpoints and independent read readiness, then publishes READY once.
3. Only after valid READY, H creates payload suspended in both Jobs, confirms
   both memberships, and checked-closes all H writer copies.
4. H publishes ROOT_CREATED before resume, checks remaining deadline, then
   checked-resumes payload at most once. W accepts its identity once.
5. W publishes interleaved DATA and exactly one EOF per stream. H validates full
   raw length/hash, then strict UTF-8 and universal newline semantics on both
   streams. Multibyte characters and CRLF/CR split across chunks must survive.
6. H independently confirms root-handle exit, caches the actual code and
   identity-bound exit facts, checked-retires its relevant process/thread
   references, then confirms sealed `J_command` quiescence under §37.8.
   Once all semantic checks are complete, it records
   semantic completion timestamp `E`, which must be strictly before execution
   deadline. Root nonzero follows exactly the same completion requirements.
7. H publishes FINISH as its own verified assertion, not a fact supplied by W.
   W must fully validate and accept it after both EOFs **strictly before
   D_execution**, with no earlier failure or forced-termination attempt.
   H's E or timely publication alone does not establish timely W acceptance.
   After acceptance W enters bounded finalization: all pending capture I/O
   must retire, and all safety-critical capture resources (server/read handles,
   events, OVERLAPPED and buffers) must be safely released with checked closes
   where applicable before ACK is published as its last frame. ACK asserts
   those protocol preconditions; its fields do not change.
   W checked-releases its remaining bootstrap/IPC/Job/parent capabilities
   and exits 0; ACK does not attest resources still needed to publish itself.
   A mandatory close failure after ACK requires nonzero W exit, never exit 0.
8. H validates ACK, independently confirms W exit/code 0, caches the verified
   W exit facts and checked-retires its W process/thread references, then
   confirms sealed `J_supervision` quiescence and remaining checked closes
   before cleanup deadline. Only then may it construct `VerificationCommandResult`.

INIT, READY, ROOT_CREATED, FINISH and ACK are single-use; wrong-phase, duplicate
or missing frames fail closed. Before INIT/READY there is no accepted output;
DATA/EOF are valid only after W receives ROOT_CREATED and before FINISH. ERROR
may terminate any initialized W phase before ACK; CANCEL may terminate any
initialized H phase before successful finalization. An error before usable IPC
is signaled by worker failure and checked owned cleanup, without invented frames.
Once failure/cancellation starts, further frames cannot restore success.
Any own forced-termination attempt irreversibly excludes every completed
`VerificationCommandResult`, including an ordinary nonzero rejection (§37.9).
No semantic output bytes are accepted after E. Extra frames after ACK, missing
ACK, W nonzero/crash, or failed final close reject even a root exit code 0.
W exit code 0 alone never proves timely FINISH, capture retirement, normal
worker finalization or successful cleanup; all independent gates still bind.

The unchanged completed shape is
`VerificationCommandResult(command=<original approved argv>,
returncode=<actual root code>, stdout=<full normalized text>,
stderr=<full normalized text>, passed=(returncode == 0))`.
W's code never substitutes for root code. Complete nonzero is ordinary rejected
candidate evidence under §25; this section does not change that repair path.
It introduces no output truncation or total semantic-output limit. Fixed rings
bound transport only; H's complete capture memory remains unbounded in aggregate.
Memory/resource exhaustion is terminal uncertainty, never partial success.

### 37.7. Execution deadline, cleanup cutoff, and fairness

`D_execution = t0 + verification_timeout_seconds`, expressed in monotonic
nanoseconds without extending the configured interval through rounding. It
includes preflight, ABI/API checks, bootstrap, W startup/connect, payload
creation/execution, descendants, transport, full capture/decode and command Job
quiescence. Check the clock before/after native calls, before resume and after
each bounded event-loop iteration. E includes verified root exit, both complete
semantic streams and both command quiet samples; require `E < D_execution`.
Separately require W's FINISH acceptance timestamp `F < D_execution`. F is
recorded at W's acceptance transition after full frame/phase validation, not
when H sends FINISH or W begins reading it. Deadline handling, FINISH acceptance
and the forced-termination latch have one ordered W-side transition discipline;
an earlier timeout/termination decision cannot be undone by later FINISH.
Equality, a late second sample or absent/late FINISH acceptance is terminal
uncertainty, even if H already recorded a timely E. No FINISH/ACK fields change.

The fixed cleanup budget is 5000000000 ns:

| Trigger | Absolute H cleanup cutoff |
| --- | --- |
| Normal semantic completion | `D_cleanup = E + 5 seconds` |
| Execution timeout | `D_cleanup = D_execution + 5 seconds`, including late discovery |
| Other failure | `D_cleanup = first_failure_timestamp + 5 seconds` |

Here `first_failure_timestamp` is H's first monotonic observation of the
failure (including receipt of W's ERROR or observed W death), recorded once.
W records its own first observation for its independent non-renewing cleanup
attempts; a later H message cannot restart W's exhausted budget. No ERROR
timestamp or extra JSON key is inferred from the closed wire schema.

Once selected, the cutoff never advances for progress, a secondary error or a
new cleanup action. A failure during normal finalization cannot restart E's
budget. If an earlier applicable cutoff already exists it remains binding.
Normal cleanup allows only protocol/worker finalization, retirement, close and
final supervision checks; it cannot extend semantic execution or allow new bytes.

Each managed wait is finite and bounded by the remaining applicable budget;
no `INFINITE`, unbounded `join`/`communicate`, blocking pipe read, semaphore
wait or endless cancellation loop is allowed. H and W service clock, peer
liveness and control between bounded batches of stream work. W maintains at
most one pending capture read per stream plus bounded transport staging; full
rings pause further reads rather than accumulating unbounded W-side buffers.
This permits pipe backpressure without starving stderr, control or deadline
monitoring. H also bounds each drain iteration, regardless of output volume.

IPC waits must multiplex peer liveness and the earliest applicable cutoff, or
use finite service slices when an API cannot multiplex. Waiting solely on a
saturated queue until a distant deadline cannot suspend independent peer and
deadline monitoring.

W independently monitors D_execution and the retained H-process handle even
when H stops advancing or runtime queues saturate. If FINISH has not been
accepted strictly before D_execution, W irreversibly enters timeout failure
and requests checked `TerminateJobObject(J_command)` with the reserved nonzero
code (§37.9), without waiting for H or a free IPC slot, even if command
membership is already empty. After timely accepted FINISH, W retires resources
under bounded finalization without a repeated execution-timeout termination
merely because D_execution passes. Parent death and other finalization faults
still follow the terminal failure/cleanup path. FINISH never renews a budget.
H owns E and its exact finalization cutoff; W's independent finalization waits
must additionally end no later than `D_execution + 5 seconds`. This ceiling
does not extend H's earlier cutoff, and no wire field pretends to convey E.
A timeout/error observed by W remains terminal even if FINISH later arrives.

An application-managed deadline is not preemption of synchronous native calls.
If H is already stuck in an unpreventable native call, return within T+5 seconds
is not guaranteed. W can request owned command termination; neither API return
nor kernel termination/cancellation completion is hard-real-time. A responsive
H observes W crash/stall and initiates supervision cleanup. If both stop
progressing, no successful cleanup or bounded OS completion may be claimed.

### 37.8. Sealed quiescence and real process status

Before final sampling H logically seals creation/assignment: all launches have
returned, no `CreateProcessW` or assignment is in flight, no owned root remains
unaccounted/suspended, no future assignment will occur and no assignment
capability was exported. A late launch cannot be ignored because an earlier
query was empty. Ordinary descendants stay subject to nested Job membership.

H performs the following ordered reference-retirement and observation sequence
for the processes relevant to each Job:

1. While a process handle is retained, confirm it is signaled without
   `WAIT_FAILED`, then successfully obtain its final DWORD with
   `GetExitCodeProcess`. A live handle is not exit evidence; a signaled handle
   with unknown code is also insufficient. WAIT_FAILED or a failed code query
   is terminal and must not be hidden by closing the handle.
2. Cache the verified exit/code and observation time, bound to run UUID, process
   role and its creation/handle provenance. Preserve these facts after release;
   PID alone and reopening a PID cannot replace the original observation.
3. Checked-close all harness-owned relevant process-handle copies and primary-
   thread references only after those facts are cached. Mark each reference
   retired only on confirmed close. Unknown, failed or incomplete retirement
   blocks acceptance; no cached fact manufactures successful close.
4. Only then take two consecutive complete Job-accounting samples, each with
   an initial query showing `ActiveProcesses == 0`, validation of cached
   verified exit facts and completed reference retirement, and a repeat query
   still showing zero. No live/unknown retained relevant handle may be ignored.
   If a reference is discovered or retired during sampling, invalidate both
   samples and restart after its verified retirement within the same budget.

Windows accounting may remain nonzero while terminated process objects still
have references. The contract therefore does not require all original process
handles to remain open simultaneously with `ActiveProcesses == 0`, nor infer
that a signaled process must already have disappeared from accounting. Lingering
references outside harness control may still prevent quiescence before the
deadline; that is terminal uncertainty, not permission to subtract processes
from the reported count or weaken a quiet sample.

Both full samples must complete strictly before the applicable deadline, with
stable `TotalProcesses` within and across them. Unknown, failed, incomplete or
inconsistent accounting, missing cached facts, and membership/counter changes
invalidate stability. H checks `J_command` by E under execution deadline using
the cached root facts; it separately confirms W exit/code and checked reference
retirement before `J_supervision` samples under cleanup deadline. Error cleanup
uses its fixed cutoff for both Jobs and never creates completed evidence.

Real code 259 is final after a confirmed signaled handle; it is not pending
merely because it equals `STILL_ACTIVE`. Preserve Windows DWORD codes as actual
unsigned values, without invented POSIX signal conversion. Non-Windows real
negative codes keep their existing meaning. Checked close never substitutes
for prior exit observation. PID, a single empty sample, EOF, root exit,
completion-port notice or successful `TerminateJobObject` alone never proves
quiescence. Two samples remain a conservative observation protocol under the
creation seal, not absolute proof of future OS state. Separately approved
native evidence must prove the signal → code/cache → checked reference close
→ two-accounting-samples sequence and accounting behavior with retained and
released process references on the supported runtime; mocks alone cannot do so.

### 37.9. Cancellation, retirement, failure mapping, and diagnostics

Every own H/W forced-termination attempt irreversibly makes the invocation
terminally uncertain and ineligible for **any** completed result. Each actor
sets a monotonic local `forced_termination_attempted` latch before the native
call, including attempts against an empty/already-quiet Job or calls that fail.
All own `TerminateJobObject` calls use the reserved nonzero uint32 exit code
`WVC_FORCED_TERMINATION = 0x57564301`; zero is forbidden. The code is internal,
not a new public error/status or a substitute for the latch. An ordinary payload
may naturally return the same numeric code; absent a forced attempt it remains
an ordinary completed nonzero rejection after all other gates pass.

W must not publish ACK or exit 0 after its own attempt; if an attempt occurs
after ACK, it must still exit nonzero. H's own latch forbids acceptance even
if it previously received ACK and observed W/root code 0. No later quiescence,
successful close, FINISH or zero code clears a latch. Deliberate kill-on-close
of a not-yet-proven-quiet Job likewise disqualifies completion; ordinary checked
closure of an already verified quiet Job is not a forced-termination attempt.
No new FINISH/ACK field is introduced.

On timeout/error H and independently W terminate only owned Job membership.
H requests bounded cooperative cancellation via CANCEL when IPC is usable;
W requests command termination and `CancelIoEx` for each outstanding connect/read.
At the first cooperative attempt, fix its cutoff at that attempt's timestamp
plus at most half of the then-remaining cleanup budget; it is never renewed.
Fatal ownership fault or peer crash causes immediate escalation;
otherwise unconfirmed cooperation escalates to H's `J_supervision` termination.
Checked `TerminateJobObject` failure preserves uncertainty, not guessed success.

`CancelIoEx` requests cancellation; it does not retire I/O. OVERLAPPED, event
and buffer remain live and unreused until confirmed completion/retirement.
Normal completion racing with cancellation, `ERROR_OPERATION_ABORTED`,
`ERROR_NOT_FOUND` and `ERROR_IO_INCOMPLETE` must be distinguished. In particular,
NOT_FOUND is not proof that a previously pending operation's buffers are safe;
observe its completion using finite event waits and nonblocking
`GetOverlappedResult(..., bWait=False)`. Unanswered cancellation, peer crash,
failed capture close and native-resource retirement uncertainty forbid ACK/success.
W must not unwind/free pending Python/native buffers as normal cleanup. It
reports failure when possible and remains subject to H's owned supervisory Job
abort, which terminates W without normal buffer unwinding; H must not wait
indefinitely for W. If H cannot progress, the stall limitation in §37.7 applies,
without fabricated retirement or successful API-return guarantees.

H-crash closure of its last owning `J_supervision` reference must initiate
kill-on-close for W and payload membership. No other process receives a
reference that can keep that Job alive. W also watches retained H identity and
requests command termination on parent death. Kill-on-close initiates cleanup;
it alone proves neither completed termination nor quiescence.

Exit code 0 is necessary for normal W acceptance, never standalone proof of
cleanup. Safety-critical capture retirement/closure precedes ACK (§37.6).
Observed external forced termination is also terminal uncertainty. However,
a foreign process able to terminate W can choose code 0: after a valid ACK,
that may be observationally indistinguishable from normal W exit under this
protocol. No guarantee of detecting arbitrary foreign termination or proving
W's remaining user-space finalization from code 0 is claimed. H still requires
valid ACK, verified exit/code facts, checked owned-reference retirement, sealed
Job quiescence and its own closes; the local-attempt guarantee covers H/W's
own actions, not hostile external attestation. Missing ACK or an observable
failure never becomes success under this limitation.

Every timeout, launch/Job/assignment/query/wait/bootstrap/IPC/pipe/ownership/
capture/decode/cancel/close uncertainty maps terminally to existing
`RepositoryError`. Internal `WindowsVerificationError(OSError)` carries only
the closed stage/category, nullable numeric WinError/errno, timeout/cleanup
flags and monotonic timestamps. Timeout preserves `subprocess.TimeoutExpired`
as the primary cause even if cleanup also fails; secondary cleanup diagnostics
cannot replace that cause or smuggle partial output into evidence. Other failures
retain their checked causal error. No synthetic code/result, accepted evidence,
review, candidate repair, automatic retry/resume or alternate profile follows.

Public failure diagnostics are bounded, allowlisted stage/category/numeric
status, timeout/cleanup flags, run identity and monotonic timing metadata only.
No raw stdout/stderr, full argv, environment, prompts, credentials, tokens,
provider/MXC internals or arbitrary exception strings are projected. These
metadata remain within the existing 4096-source-character diagnostic budget;
they do not authorize transcript excerpts for this boundary. Complete valid
semantic output in a completed result remains available to ordinary verification
consumers; it is not an uncertainty diagnostic.

### 37.10. Platform parity and security limits

On non-Windows retain the existing `subprocess.run(runtime_command,
cwd=config.repo, capture_output=True, text=True, encoding="utf-8",
timeout=config.verification_timeout_seconds, check=False)` behavior and
failure mapping, including inherited environment/stdin and original evidence.
The Windows branch must never fall back to it after containment failure.
Both captured streams use strict UTF-8 plus universal newline normalization
(`CRLF` and lone `CR` to `LF`), not raw `.decode()` alone; integrity hashes
cover pre-normalization raw bytes. Lossy decode or incomplete text never passes.

This boundary covers only processes actually assigned to the dedicated Jobs.
It cannot contain a foreign broker's out-of-Job processes, undo filesystem or
network effects, guarantee total capture memory, or promise kernel/API latency.
No agent/MXC safety claim follows. The one Probe B descendant-survival account
in draft TSK-0047 motivates this design but does not prove this backend, Probe A,
MXC or a separate interactive-shell baseline. No probe rerun is authorized.

### 37.11. Independent native-validation and integration gates

Unit/pure-state/fault-injection tests may validate grammar, ownership, ABI
declarations, deadlines and all negative transitions without native payload
execution. Every real Windows Job/pipe/process containment test requires
separate explicit approval of the **exact native runtime plan**, after independent
review of the native layer. A task approval, C0 publication, mocked PASS or
earlier checkpoint PASS does not grant that approval.

The approved plan must identify environment and exact command, independent
safety owner, bounded deadlines, an unrelated-process sentinel that cannot be
terminated by tested Jobs, expected failure outcomes, cleanup/rollback and
retained evidence of actual non-skipped native execution and limitations.
No Probe A/B, Codex/MXC experiment, live `AUTONOMOUS_PR` pilot, elevation or
external destructive cleanup is implicitly included. A test safety supervisor
is outside the production H/W boundary; it does not authorize a third runtime
supervisor or unsafe crash experiment without independent protection.

Dangerous native tests must use separate opt-in discovery excluded from default
full pytest and unapproved CI, not default collection followed merely by skips.
The future implementation must provide that explicit mechanism. Native tests
must prove real Job/pipe/handle/cancel semantics and sentinel survival; skipped
tests and mocked API success are not native proof. Any required invariant left
unproven blocks production wiring. Separately authorized MANUAL integration
must follow native acceptance, focused/full pytest, configured mypy, relevant
documentation checks, diff review and factual reviewed closure. C0 publication
authorizes no native experiment, implementation or production integration.

Native reference semantics:
[nested Jobs](https://learn.microsoft.com/en-us/windows/win32/procthread/nested-jobs),
[creation attributes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute),
[overlapped pipe connection](https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-connectnamedpipe),
[cancellation and buffer lifetime](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-cancelioex),
and [CPython subprocess behavior](https://docs.python.org/3.12/library/subprocess.html).
These sources constrain implementation; reading them is not native validation.

### 37.12. Binding coverage and acceptance traceability

The following obligations preserve all 19 numbered acceptance cases of draft
TSK-0047, in their original order. A subsequent execution spec must carry them
across decomposed slices; it cannot omit a cross-slice case because C0 is
documentation-only. For each case evidence records expected outcome, actual
test type (unit/fault injection, Windows native, cross-platform), fail-closed
gate, safety deadline and cleanup. Required native facts need native proof.

| Case | Binding acceptance obligation | Contract |
| --- | --- | --- |
| 1 | Completed zero/nonzero preserves full text, real root code and approved identity, including exact python substitution/newlines | §37.4–§37.6, §37.8, §37.10 |
| 2 | Timeout with descendants yields terminal RepositoryError caused by TimeoutExpired; no downstream evidence/review/repair/retry | §37.7, §37.9 |
| 3 | Descendant-held writer cannot cause unbounded capture/waits or accepted partial output | §37.4, §37.7, §37.9 |
| 4 | Pipe-free background descendant still delays acceptance until command quiescence; natural timely exit may succeed | §37.6–§37.8 |
| 5 | Failed native/pre-resume stages never run an uncontained payload | §37.2–§37.4, §37.6 |
| 6 | Failed Job termination remains terminal uncertainty | §37.9 |
| 7 | Failed/incomplete/inconsistent accounting prevents acceptance | §37.8 |
| 8 | WAIT_FAILED or unknown retained-handle exit/code prevents acceptance | §37.8 |
| 9 | Empty accounting plus live retained handle is not quiet | §37.8 |
| 10 | Second sample completing at/after deadline is insufficient | §37.7–§37.8 |
| 11 | Membership changes reset stability; creation seal and stable TotalProcesses required | §37.8 |
| 12 | Close/cancel/finalization uncertainty after root zero prevents success; buffers remain live until retirement or W abort | §37.6, §37.9 |
| 13 | Large interleaved streams, inherited stdin and saturated transport preserve bytes/order without deadlock or partial success | §37.3–§37.7 |
| 14 | Invalid UTF-8 in either stream is terminal, never lossy repair evidence | §37.6, §37.9–§37.10 |
| 15 | Protected H-crash test verifies owned kill-on-close and unrelated-process survival, with stall limitations | §37.7, §37.9–§37.11 |
| 16 | Outer Job supports validated nesting or blocks before resume, without outer mutation/breakaway/fallback | §37.2 |
| 17 | Non-Windows subprocess kwargs and failure mapping retain direct regressions | §37.10 |
| 18 | Diagnostics and control bodies carry only bounded allowlisted metadata | §37.3, §37.5, §37.9 |
| 19 | Static call-site/docs checks prove verification-only scope, unchanged run_agent/security profiles and no Probe A authority | §37.1, §37.10–§37.11 |

Additional mandatory regressions cover exact pipe modes and security/QoS,
wrong client identity, collision/access denial without retries, both connect
races, no W/Job/IPC handles in payload, every pre-resume writer close and the
documented cross-thread inheritance risk. Exercise zero-byte reads/writes and
descendant-held EOF; malformed/duplicate/wrong-state IPC, offsets/sequences,
length/hash/EOF corruption, missing/corrupt ACK and W nonzero; fair interleaved
streams under saturated queues; the complete cancel/completion/error/peer-crash
matrix, pinned-buffer W abort and independent deadline monitoring under H stall.
Also cover non-renewed cleanup cutoffs, in-flight/late/suspended assignments,
both full quiet samples, Windows argv/search/env/stdin, split UTF-8 and CRLF/CR,
real root code 259 versus W code, outer nesting, terminal redaction and
non-Windows parity. Native evidence remains separately approved under §37.11;
none of these requirements authorizes running a new native test in C0.

Targeted regressions must also cover retained-reference accounting and cached
exit facts after checked closes; FINISH acceptance before, at and after
D_execution (including timely E with late FINISH); no execution-timeout kill
after timely FINISH; and irreversible failed/empty-Job/post-ACK own termination
attempts using the reserved nonzero code. Verify safety-critical capture close
before ACK and explicitly record the limit of foreign forced-zero exit detection.
These refine the existing 19 cases and retain the separate native-proof gate.
