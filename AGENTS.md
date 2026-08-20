# AGENTS.md

Instructions for Codex and other coding agents working in this repository.

## Sources of truth

Use project documentation in this order:

1. `docs/ARCHITECTURE.md` — canonical architecture and contracts.
2. `docs/ROADMAP.md` — implementation order and current project status.
3. `README.md` — project overview and intended developer workflow.
4. `CLAUDE.md` — condensed agent guidance; not a replacement for `docs/ARCHITECTURE.md`.

Before non-trivial work, read `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, and the relevant source/test files.

If code, documentation, Roadmap, or task instructions conflict with a canonical architectural contract, do not choose silently. Report the conflict before implementing an architectural change.

## Repository layout

* `src/dnd_engine/domain/` — Definitions, State, Commands, Events, rules, resolvers, value objects, domain services.
* `src/dnd_engine/application/` — use cases, command handlers, orchestration.
* `src/dnd_engine/api/` — presentation/API boundary.
* `src/dnd_engine/infrastructure/` — persistence, filesystem, RNG implementations, LLM integrations.
* `rules/dnd_5e/` — immutable/versioned ruleset Definitions.
* `campaigns/` — campaign-specific mutable state and event history.
* `tests/` — deterministic automated tests.
* `docs/ARCHITECTURE.md` — canonical contracts.
* `docs/ROADMAP.md` — development phases and status.

## Canonical architecture

Preserve these constraints unless an explicit architectural change is approved:

* Keep `Definitions / State / Commands / Events` separate.

* `Command` expresses intent; `Event` records an immutable fact.

* The Rule Engine is deterministic and authoritative.

* AI DM may interpret intent and produce narration, but must never mutate authoritative State directly.

* Authoritative flow is:

  `Player/AI DM → Command → Validation → Rule Engine → Result → Events → State update → Persistence → Narration`

* State changes only through the owning domain/application flow defined by the architecture.

* Definitions are immutable during a session and are versioned rather than mutated.

* Events are immutable and append-only after publication.

* All gameplay randomness goes through `DiceEngine`; do not call `random` directly from Rule Engine logic.

* Domain must not depend on FastAPI, HTTP types, SQL/ORM implementations, filesystem implementations, or provider-specific LLM SDKs.

* Serialization and persistence stay outside Rule Engine/domain resolution logic.

* Storage implementations depend on domain interfaces, never the reverse.

* Do not add databases, brokers, cloud infrastructure, large frameworks, or new production dependencies without an explicit project decision.

For exact envelopes, IDs, ownership rules, serialization rules, and error contracts, reference `docs/ARCHITECTURE.md` rather than duplicating them here.

## Working method

For architecture changes, multi-file features, or ambiguous work:

* inspect the current implementation and documentation first;
* identify affected contracts, modules, tests, and documentation;
* plan the minimal change before editing;
* follow `docs/ROADMAP.md` unless the task explicitly changes priority.

During implementation:

* make the smallest change that satisfies the task;
* do not perform unrelated refactors;
* preserve existing contracts unless their change is explicitly approved;
* update canonical documentation when behavior or contracts change;
* add or update tests for changed behavior;
* do not overwrite or revert unrelated work.

If the task requests analysis or planning only, do not modify files.

## Setup

Target runtime: Python 3.12+.

Create a local environment with:

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows:

```powershell
.venv\Scripts\activate
```

Treat `pyproject.toml` as authoritative for package installation and development tooling.

When the project metadata and `dev` extra are configured, use:

```bash
python -m pip install -e ".[dev]"
```

If the required package/development configuration is absent, report that setup is not configured. Do not invent dependencies or modify `pyproject.toml` merely to make a command succeed unless the task explicitly requires it.

## Testing

The canonical test framework is `pytest`.

Run the narrowest relevant tests first, then the full suite when appropriate:

```bash
python -m pytest <relevant-test-path>
python -m pytest
```

Tests for Rule Engine/domain behavior must be deterministic and runnable without an LLM or network access.

When randomness is involved, inject/control `DiceEngine` rather than relying on uncontrolled randomness.

If the test toolchain is not installed/configured by the repository, report that explicitly instead of silently installing arbitrary dependencies.

## Formatting, linting, and typing

Use only formatter, linter, and type-check commands configured by the repository (`pyproject.toml`, CI, or another canonical project config).

If no formatter/linter/type checker is configured, report it as `not configured`; do not introduce one solely to satisfy this file.

Code conventions:

* use Python 3.12+ syntax and type hints;
* use domain `dataclass` models where appropriate;
* Definitions and immutable Value Objects should be frozen;
* keep Pydantic at system boundaries rather than embedding it into Rule Engine logic;
* prefer enums/value objects over duplicated string constants where the architecture defines a closed set;
* use canonical entity names from `docs/ARCHITECTURE.md`; do not invent synonyms for existing concepts.

## Definition of done

A change is complete only when:

* the requested behavior is implemented;
* canonical architectural constraints remain satisfied;
* affected contracts/documentation are updated;
* relevant tests are added or updated and pass;
* repository-configured formatting/lint/type checks pass, if configured;
* the final diff contains no unrelated changes;
* no direct AI/UI/API mutation of authoritative State was introduced;
* no uncontrolled randomness or forbidden Domain dependency was introduced;
* known limitations or unrun checks are reported explicitly.

## Branches and pull requests

Do not perform substantive development directly on `main`.

For implementation work:

* create a dedicated branch from the current intended base;
* keep the branch scoped to one coherent change;
* do not commit, push, create a PR, merge, or enable auto-merge unless explicitly requested;
* review the final diff before any commit or PR;
* do not include unrelated files or generated/runtime artifacts.

Unless explicitly requested otherwise, create pull requests as **draft**.

PR descriptions should state:

* what changed;
* affected architectural contracts/modules;
* tests and checks run;
* documentation changed;
* known risks, limitations, or follow-up work.

Do not merge a PR without explicit authorization.
