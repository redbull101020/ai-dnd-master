# AGENTS.md

Instructions for Codex and other coding agents working in this repository.

## Sources of truth

Use project documentation in this order:

1. `docs/ARCHITECTURE.md` — canonical architecture and contracts.
2. `docs/ROADMAP.md` — phase/capability scope, ordering, and completion status.
3. `docs/TASK.md` — current executable task and task-level `Current`/`Next` ordering.
4. `docs/DECISIONS.md` — append-only rationale/history; never an alternative contract.
5. `docs/DEFERRED.md` — subordinate Phase 2 closure companion and deferred-scope register; never an executable task queue.
6. `README.md` — project overview and developer workflow.
7. `CLAUDE.md` — supplementary condensed guidance.

`ARCHITECTURE.md = current canonical contract`; `DECISIONS.md = append-only rationale/history`.

Before non-trivial work, inspect the current repository state,
`docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/TASK.md`, the relevant
implementation/tests, and any `docs/DEFERRED.md` or `docs/DECISIONS.md`
context referenced by that work.

If code, documentation, Roadmap, Task, and task requirements conflict, do not choose silently. Report the conflict before changing a canonical architectural contract.

## Repository layout

* `src/dnd_engine/domain/` — Definitions, State, Commands, Events, rules, resolvers, value objects, domain services.
* `src/dnd_engine/application/` — use cases, command handlers, orchestration.
* `src/dnd_engine/api/` — presentation/API boundary.
* `src/dnd_engine/infrastructure/` — persistence, filesystem, RNG implementations, LLM integrations.
* `src/dnd_engine/resources/rulesets/` — packaged immutable/versioned ruleset Definitions (installed with the package; see `docs/ARCHITECTURE.md` §12.26). This is the single authoritative Definition dataset location; there is no separate top-level `rules/` copy.
* `campaigns/` — campaign-specific mutable state and event history.
* `tests/` — deterministic automated tests.
* `docs/ARCHITECTURE.md` — canonical contracts.
* `docs/ROADMAP.md` — development phase/capability scope, ordering, and completion status.
* `docs/TASK.md` — current executable task queue and short-term task ordering.
* `docs/DEFERRED.md` — detailed Phase 2 closure notes and deferred-scope register, subordinate to Architecture and Roadmap.

## Canonical architecture

Preserve these constraints unless an explicit architectural change is approved:

* Keep `Definitions / State / Commands / Events` separate.
* `Command` expresses intent; `Event` records an immutable fact.
* The Rule Engine is deterministic and authoritative.
* AI DM interprets intent and creates narration but never mutates authoritative State directly.
* Only Engine/application flows may perform authoritative State changes.
* Definitions are immutable during a session and are versioned rather than mutated.
* Events are immutable after publication and form the audit/history log.
* State changes must respect the State Owner defined in `docs/ARCHITECTURE.md`.
* All gameplay randomness goes through `DiceEngine`; direct `random` usage inside Rule Engine logic is forbidden.
* Domain must not depend on FastAPI, HTTP types, SQL/ORM implementations, filesystem implementations, or provider-specific LLM SDKs.
* Serialization and persistence stay outside domain rule resolution.
* Storage implementations depend on domain/application interfaces, never the reverse.
* The Engine is a system of modules/layers, not a single monolithic module.
* Do not add databases, brokers, cloud infrastructure, large frameworks, or production dependencies without explicit approval.

Canonical action flow:

`Player/AI DM → Command → Validation → Rule Engine → Result → Events → State update → Persistence → Narration`

Never introduce:

`AI DM → direct State mutation`

For exact envelopes, ID formats, ownership, serialization, error contracts, and event ordering, use `docs/ARCHITECTURE.md` rather than duplicating them here.

## Working method

For architecture changes, multi-file features, or ambiguous tasks:

1. Inspect the current implementation and documentation.
2. Identify affected contracts, modules, files, and tests.
3. Check compatibility with `docs/ARCHITECTURE.md`.
4. Propose or follow the smallest sufficient change.
5. Follow the phase/capability scope and order in `docs/ROADMAP.md`, then the concrete `Current`/`Next` task order in `docs/TASK.md`, unless the task explicitly changes priority.

During implementation:

* make the smallest change that satisfies the task;
* do not perform unrelated refactors;
* preserve existing contracts unless their change is explicitly approved;
* update canonical documentation when behavior or contracts change;
* by default, append one concise factual delivery entry to `docs/DEVELOPMENT_LOG.md` per substantive `TSK`/PR, briefly answering: what was delivered, what boundaries/limits were preserved, how it was verified, and what adjacent scope stays deferred/out of scope; an additional intermediate entry is justified only when it preserves durable information that would otherwise be lost — a distinct architectural decision, a significant post-review correction, an incident/failure worth remembering, a supersession/decomposition, or a comparable fact — not for an ordinary checkpoint commit; never enumerate every commit SHA, restate the full PR body, narrate the test implementation, or repeat an unchanged contract; never rewrite an existing append-only entry;
* add or update tests for changed behavior;
* do not overwrite or revert unrelated work.

Within one `TSK`, split execution checkpoints along independent review-risk boundaries, not mechanically by file set. Typical independent boundaries: State model/State schema, Command/Event contract, persistence/version compatibility, State ownership, Event ordering/causality, atomicity, non-trivial Application orchestration, and cross-layer integration that could surface a new contract risk. An ordinary regression addition, status documentation, or mechanical synchronization that directly completes already-reviewed behavior does not need its own checkpoint. A task may still use several sequential checkpoints.

Changes to canonical contracts such as Envelope fields, ID formats, State Ownership, serialization, or dependency direction require corresponding updates to `docs/ARCHITECTURE.md`.

`CLAUDE.md` reproduces a deliberately small set of canonical facts (DEC-0016): the names and section numbers of the implemented contracts, the `current_hp` / `max_hp` naming, the closed `DamageType` set, the Command lifecycle states, the deferred-abstraction list, and the current phase. After changing a canonical contract, reread `CLAUDE.md` and update it within the same change, in the same slice, if any reproduced fact changed. Updating `docs/ARCHITECTURE.md` alone is not sufficient: nothing detects the drift automatically, and an agent reads the summary before it reads the canon.

When making a new substantial architectural decision or changing an existing contract:

1. update the canonical contract in `docs/ARCHITECTURE.md`;
2. add a new entry in `docs/DECISIONS.md`;
3. do not rewrite an accepted historical entry;
4. when reversing a decision, add a new decision and mark the old one `Superseded`.

If the task requests analysis or planning only, do not modify files.

## Setup

Target runtime: Python 3.12+.

Create a virtual environment:

```bash
python -m venv .venv
```

Install the project and development dependencies on Linux/macOS:

```bash
.venv/bin/python -m pip install -e ".[dev]"
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

`pyproject.toml` is authoritative for package metadata and development dependencies.

Do not add dependencies merely to make a command succeed. New production dependencies require explicit approval.

## Testing

The canonical test framework is `pytest`.

Linux/macOS:

```bash
.venv/bin/python -m pytest
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Run the narrowest relevant tests first when possible. What "complete" requires beyond that depends on what kind of checkpoint is being closed:

* **Production/code checkpoint.** After the checkpoint: the narrow tests it affects. Before the whole production task is considered implementation-complete: broader affected suites where relevant, the full `pytest` run, the configured type checks, and `git diff --check`. The full suite is not required after every intermediate checkpoint.
* **Documentation/process-only checkpoint.** Locally, the narrow architecture/process tests directly tied to the change, plus `git diff --check`, are sufficient. Do not require a full gameplay `pytest` run after every Markdown/YAML-only checkpoint when no executable/test/tooling behavior changed.
* **A task that changes test or tooling executable behavior.** One full regression pass (full `pytest`, configured type checks) is required before that task is considered complete, even if individual checkpoints only ran narrow tests. CI remains a repository-wide guard and does not substitute for that final regression pass on a production task.

Rule Engine/domain tests must:

* be deterministic;
* run without an LLM;
* run without network access;
* control randomness through `DiceEngine`.

## Formatting, linting, and typing

Use only formatter, linter, and type-check tools configured by the repository.

If no such tool is configured, report it as `not configured`. Do not introduce Ruff, Black, mypy, or another tool solely because this file mentions formatting or linting.

Code conventions:

* use Python 3.12+;
* use type hints;
* use domain `dataclass` models where appropriate;
* Definitions and immutable Value Objects should be frozen;
* keep Pydantic at system boundaries rather than inside Rule Engine logic;
* prefer enums/value objects for canonical closed sets;
* use canonical entity names from `docs/ARCHITECTURE.md`; do not invent synonyms for existing concepts.

## Definition of done

A change is complete only when:

* requested behavior is implemented;
* canonical architecture remains satisfied;
* affected documentation/contracts are updated;
* relevant tests are added or updated;
* relevant tests pass;
* configured formatting/lint/type checks pass, if configured;
* the final diff contains no unrelated changes;
* no direct AI/UI/API mutation of authoritative State was introduced;
* no uncontrolled gameplay randomness was introduced;
* no forbidden Domain dependency was introduced;
* known limitations and unrun checks are reported explicitly.

## Branches and pull requests

Do not perform substantive development directly on `main`.

For implementation work:

* create a dedicated branch from the intended base;
* keep the branch scoped to one coherent change;
* inspect `git status` and the final diff before committing;
* never include unrelated files, `.venv`, caches, packaging artifacts, or runtime-generated files.

Authorisation for commit, push, pull request creation, and merge is governed by the section "Change authorisation and diff review" below. Do not restate those rules here.

PR descriptions should state:

* what changed;
* affected contracts/modules;
* tests and checks run;
* documentation changed;
* known risks, limitations, or follow-up work.

## Change authorisation and diff review

Commit, push, opening a pull request, and merging are four separate actions. Each requires its own authorisation from the user, and that authorisation is given after the user has seen the diff.

Authorisation embedded in the task description itself does not count. A task that says "commit and open a pull request" is not sufficient authorisation to do so. Finish the edits, run the checks, produce the patch, report, and stop. Wait for a separate instruction.

After finishing the edits for a slice, always write `review.patch` in the repository root and give its path in the report. `review.patch` must show exactly the slice the user is being asked to review right now — no more, no less. Which diff produces that depends on where the slice currently sits:

**A. Fresh, uncommitted checkpoint** — nothing in it has been committed yet:

```bash
git diff HEAD > review.patch
```

This covers both staged and unstaged changes since the last commit. A brand-new file stays untracked and invisible to `git diff` until it is at least intent-to-added:

```bash
git add -N path/to/new_file
```

`git add -N` only makes the file's content visible in the diff; it is not authorisation to stage or commit that content. Never let a new/untracked file silently drop out of `review.patch`.

**B. Fresh, already-committed checkpoint** — this checkpoint's commit(s) already landed under a separate, explicit authorisation, and `review.patch` is being (re)built for review of that same checkpoint:

```bash
git diff <previous-reviewed-checkpoint-sha>..HEAD > review.patch
```

Diff from the previously reviewed/accepted checkpoint, not from `origin/main`: a checkpoint may span more than one technical commit, so `HEAD~1` is not a safe universal substitute either.

**C. Final cumulative audit** — used at the final task/PR review boundary, to review the entire branch-scope diff; not the default patch after every checkpoint. Fetch `origin/main` first so the audit is against its current state:

```bash
git fetch origin
git diff origin/main...HEAD > review.patch
```

If the branch changes after this audit — a new commit, a rebase, or `origin/main` moving — the cumulative audit is stale and must be rebuilt before the task/PR is considered complete.

`*.patch` and `*.diff` are gitignored. Never stage or commit the patch file, and never include it in the list of changed files.

Pull requests are opened as drafts unless the user explicitly asks otherwise. Merge and auto-merge always require explicit authorisation and are never inferred.

If the `gh` CLI is not available in the environment, stop and report it. Do not open a pull request through the REST API, and do not read `git credential`, `.git-credentials`, or any other credential store to obtain a token.
