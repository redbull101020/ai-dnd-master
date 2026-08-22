# Development Log

```text
ARCHITECTURE.md = canonical current contract
DECISIONS.md = architectural rationale/history
ROADMAP.md = implementation status/order
DEVELOPMENT_LOG.md = execution history only
```

This is an append-only journal of completed development iterations. It is not
canonical architecture, a Roadmap, a Decision Log, or a source of truth for
contracts.

## 2026-08-22 — Phase 1 Core contracts A

### Initial state

- Phase 0 implementation and checks were complete, but README/Roadmap status still said it was only prepared for completion.
- The first Phase 1 `AbilityScores`, Definition, and `CreatureState` shapes were not yet canonical, and examples mixed `hp` with `current_hp`.
- `docs/DEVELOPMENT_LOG.md` did not exist.

### Decisions

- Start Phase 1 Core with minimal data contracts only.
- Define `AbilityScores` as an immutable six-score Value Object with values in `1..30`.
- Use `current_hp` / `max_hp` in Python and `currentHp` / `maxHp` in JSON.
- Keep Phase 1 Definitions immutable, minimal, and separate from runtime State; make `WeaponDefinition` a specialization of `ItemDefinition`.
- Defer fields owned by later Roadmap phases.

### Changed files

- `docs/ARCHITECTURE.md` — canonical Phase 1 contracts and consistent HP naming.
- `docs/DECISIONS.md` — append-only `DEC-0008`.
- `README.md` and `docs/ROADMAP.md` — completed Phase 0/current Phase 1 status; README developer-log links.
- `AGENTS.md` — factual developer-log update rule for substantive iterations.
- `docs/DEVELOPMENT_LOG.md` — initial execution-history entry.

### Verification

- Fetched `origin/main` at `a155514d9feccc039be09c5bcd7b5769a1d86898`; no open pull requests were found before branching.
- `git diff --check` passed.
- The PATH `python` command and pre-existing `.venv` were unavailable/broken. The declared `.[dev]` extra was installed into a temporary directory and the full suite was run with bundled Python 3.12.13 plus a test-only `PYTHONPATH`: 2 tests passed.

### Intentionally deferred

- Concrete `CampaignState` model.
- Domain representation of Event timestamps.
- Dice Engine.
- Exact `StateStore` / `EventStore` responsibility boundary.
- All Phase 1 Python implementation.

## 2026-08-22 — Phase 1 AbilityScores and base Definition implementation

### Initial state

- Phase 1 canonical contracts existed in `docs/ARCHITECTURE.md` and DEC-0008,
  but `AbilityScores` and the base `Definition` had no Python implementation.
- The Domain packages contained only package placeholders, and no Domain unit
  tests covered these contracts.

### Implemented

- Added the immutable six-field `AbilityScores` Value Object with exact `int`
  type and the canonical `1..30` invariant enforced for every score.
- Added the immutable base `Definition` with only `id` and `version`.
- Added deterministic unit tests for valid construction, score boundaries,
  per-field invalid values and types, immutability, and exact canonical
  dataclass fields.

### Changed files

- `src/dnd_engine/domain/value_objects/ability_scores.py` — `AbilityScores`.
- `src/dnd_engine/domain/definitions/base.py` — base `Definition`.
- `tests/domain/test_ability_scores.py` — `AbilityScores` unit tests.
- `tests/domain/test_definition.py` — base `Definition` unit tests.
- `docs/ROADMAP.md` — marked only `AbilityScores` complete in Phase 1.
- `docs/DEVELOPMENT_LOG.md` — this factual iteration entry.

### Verification

- Fetched `origin/main` at `f02d6c2163775cdd01f420f05357090183b80486`
  and created the feature branch from that commit.
- The repository `.venv` was broken and the Windows Python launcher had no
  installed runtime. Tests used bundled Python 3.12.13 and pytest 9.1.1 from a
  temporary dependency directory outside the repository, with `src` supplied
  through a test-only `PYTHONPATH`.
- Narrow `AbilityScores` suite: 29 tests passed.
- Full pytest suite with the cache provider disabled: 35 tests passed.
- `git diff --check` passed; Git emitted only the existing Windows checkout
  warning that LF would be converted to CRLF if Git rewrites the files.

### Intentionally deferred

- `ItemDefinition`, `WeaponDefinition`, and `MonsterDefinition`.
- `CreatureState` and `CampaignState`.
- Dice Engine and Event model.
- `StateStore` / persistence.
- Serialization, registries, factories, repositories, and derived rule
  calculations.
