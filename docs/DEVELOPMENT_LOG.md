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

## 2026-08-22 — Phase 1 core Definition slice

### Initial state

- `AbilityScores` and the base `Definition` were implemented, but the three
  minimal Phase 1 Definition contracts remained documented-only Roadmap items.
- `WeaponDefinition.damage_type` was still documented as `str`, with the exact
  Domain type and closed set intentionally deferred until code implementation.

### Implemented

- Added the closed 13-value `DamageType` Domain `StrEnum`.
- Added immutable `ItemDefinition`, `WeaponDefinition`, and
  `MonsterDefinition` dataclasses using the existing base `Definition` and
  `AbilityScores` contracts.
- Added deterministic unit tests covering exact members, values, dataclass
  fields, inheritance, frozen semantics, tuple properties, and exclusion of
  runtime State fields.

### Canonical contract updates

- `WeaponDefinition.damage_type` now uses `DamageType` rather than arbitrary
  `str`; its canonical lowercase domain/serialized values are documented.
- DEC-0009 records the closed `DamageType` decision without introducing damage
  calculation, resistance, immunity, or vulnerability mechanics.
- Only `ItemDefinition`, `WeaponDefinition`, and `MonsterDefinition` were marked
  complete in the Phase 1 Roadmap.

### Changed files

- `src/dnd_engine/domain/value_objects/damage_type.py` — `DamageType`.
- `src/dnd_engine/domain/definitions/item.py` — `ItemDefinition`.
- `src/dnd_engine/domain/definitions/weapon.py` — `WeaponDefinition`.
- `src/dnd_engine/domain/definitions/monster.py` — `MonsterDefinition`.
- `tests/domain/test_damage_type.py` — `DamageType` unit tests.
- `tests/domain/test_item_definition.py` — `ItemDefinition` unit tests.
- `tests/domain/test_weapon_definition.py` — `WeaponDefinition` unit tests.
- `tests/domain/test_monster_definition.py` — `MonsterDefinition` unit tests.
- `docs/ARCHITECTURE.md` — canonical `DamageType` and updated weapon contract.
- `docs/DECISIONS.md` — append-only DEC-0009.
- `docs/ROADMAP.md` — three completed Definition items.
- `docs/DEVELOPMENT_LOG.md` — this factual iteration entry.

### Verification

- Fetched `origin/main` and created `feat/phase-1-core-definitions` directly at
  `7b882c5d75fe908dcdd32fc35086a28bd0062619`.
- The PATH `python` command and pre-existing `.venv` remained unavailable. Tests
  used bundled Python 3.12.13 with the existing temporary pytest 9.1.1
  dependency directory outside the repository.
- Narrow new Domain suite: 22 tests passed.
- Full pytest suite with the cache provider disabled: 57 tests passed.
- `git diff --check` passed; Git emitted only the existing Windows checkout
  warnings that LF would be converted to CRLF if Git rewrites changed files.

### Intentionally deferred

- `CreatureState`, `CampaignState`, Dice Engine, Event model, and State Store.
- Serializers, persistence, registries, factories, repositories, and ruleset
  datasets.
- Dice parsing, attack and damage calculations, HP changes, and weapon
  mechanics.
- Resistance, immunity, vulnerability, and runtime inventory/equipment State.

## 2026-08-22 — Phase 1 CreatureState slice

### Initial state

- PR #21 was merged into `origin/main` at commit
  `02e941fbc158448d11ddc0cea0afbd6026ef313e`; the feature branch was created
  directly from that commit with a clean working tree.
- The minimal `CreatureState` contract was canonical in
  `docs/ARCHITECTURE.md` and DEC-0008, but had no Python implementation or
  Domain unit tests.

### Implemented

- Added mutable campaign-scoped `CreatureState` with exactly `id`,
  `definition_id`, `ability_scores`, `current_hp`, and `max_hp`.
- Reused the immutable `AbilityScores` Value Object without adding Definition
  lookup, ID validation, coercion, serialization, or State transitions.
- Enforced exact Python `int` types for both HP fields, including rejection of
  `bool`, and the canonical `max_hp >= 1` and
  `0 <= current_hp <= max_hp` invariants.
- Added deterministic Domain unit tests for the canonical fields and types,
  mutable State and immutable embedded Value Object semantics, distinct runtime
  and Definition IDs, HP boundaries and invalid values, and exclusion of future
  phase fields.

### Changed files

- `src/dnd_engine/domain/state/creature.py` — minimal `CreatureState` model.
- `tests/domain/test_creature_state.py` — deterministic unit tests.
- `docs/ROADMAP.md` — marked only `CreatureState` complete in Phase 1.
- `docs/DEVELOPMENT_LOG.md` — this factual iteration entry.

### Verification

- The repository `.venv` remained broken because its launcher referenced an
  unavailable Python installation. Tests used bundled Python 3.12.13 with the
  existing temporary pytest 9.1.1 dependency directory outside the repository.
- Narrow `CreatureState` suite with the cache provider disabled: 22 tests
  passed.
- Full pytest suite with the cache provider disabled: 79 tests passed.
- `git diff --check` passed.
- No formatter, linter, or type checker is configured in the repository.

### Intentionally deferred

- `CampaignState`, Dice Engine, Event model, Commands, resolvers, Event
  handlers, and State Store.
- Damage, healing, and all other State transition mechanics.
- Serialization, JSON persistence, registries, repositories, factories, ID
  validators, Definition lookup, and ruleset datasets.
- Conditions, effects, movement, position, combat State, inventory, equipment,
  and all other future-phase fields.

## 2026-08-22 — Phase 1 CampaignState slice

### Initial state

- Fetched `origin/main` and created `codex/feat/phase-1-campaign-state`
  directly from commit `6ce02c0e3161a53b4f12506f3687e3016e1109c1` with a clean working tree.
- `CreatureState` was already merged and marked complete in the Phase 1
  Roadmap. Campaign ownership was documented, but no concrete minimal
  `CampaignState` Python schema existed.

### Implemented

- Added mutable campaign-scoped `CampaignState` with exactly `id`,
  `ruleset_id`, and `ruleset_version`, all typed as `str`.
- Kept Campaign identity and the Ruleset identity/version reference separate,
  without runtime validation, coercion, lookup, or custom mutation methods.
- Added deterministic Domain unit tests for construction, exact fields and
  types, mutable State semantics, separate identities, separate Ruleset ID and
  version, and exclusion of cross-domain and future fields.
- Added the canonical minimal contract to Architecture, including ownership,
  deferred Campaign fields, World State ownership of world/game time, and the
  distinction between snapshot containment and State Ownership.
- Added append-only DEC-0010 and marked only `CampaignState` complete in the
  Phase 1 Roadmap.

### Changed files

- `src/dnd_engine/domain/state/campaign.py` — minimal `CampaignState` model.
- `tests/domain/test_campaign_state.py` — deterministic unit tests.
- `docs/ARCHITECTURE.md` — canonical Phase 1 `CampaignState` contract.
- `docs/DECISIONS.md` — append-only DEC-0010.
- `docs/ROADMAP.md` — marked only `CampaignState` complete in Phase 1.
- `docs/DEVELOPMENT_LOG.md` — this factual iteration entry.

### Verification

- The repository `.venv` was verified functional with Python 3.12.9 and
  pytest 9.1.1. The full suite was run through
  `.venv\Scripts\python.exe -m pytest`; no project dependency was added.
- Narrow `CampaignState` suite with the cache provider disabled: 7 tests
  passed.
- Full pytest suite: 86 tests passed.
- `git diff --check` passed.
- No formatter, linter, or type checker is configured in the repository.

### Intentionally deferred

- Campaign Engine, CampaignStateManager, repositories, command/event handlers,
  serialization, persistence, registries, factories, ID validation, and
  Ruleset lookup or migration behavior.
- Campaign metadata, session state, lifecycle/status fields, and snapshot
  schema versioning.
- Creature, World, Combat, Quest, Inventory, Equipment, Event Log, AI State,
  and all other cross-domain State.

## 2026-08-22 — Phase 1 Dice Engine slice

### Initial state

- Fetched `origin/main` and created `codex/feat/phase-1-dice-engine` directly
  from commit `771cf1d6e1aa43524f77662eda5e1fa4c02f8358` with a clean working tree.
- All earlier Phase 1 data-contract items were implemented. Architecture
  required gameplay randomness to pass through `DiceEngine`, but the Domain
  port, result Value Object, strict notation, parser ownership, and production
  RNG injection contract were not yet concrete.

### Implemented

- Added immutable `DiceRoll` with exactly `expression`, individual tuple
  `rolls`, and `total`, plus its minimal intrinsic type, positivity, non-empty,
  and sum invariants.
- Added the Domain `DiceEngine` `Protocol` with
  `roll(expression: str) -> DiceRoll`.
- Added Infrastructure `PythonDiceEngine` with private strict lowercase `NdM`
  parsing and an injected `random.Random`; every individual result uses that
  controlled instance.
- Added deterministic Domain and Infrastructure tests for Value Object
  invariants, frozen/tuple semantics, valid notation including non-standard
  sides, invalid/unsupported expressions, exact input types, same-seed
  sequences, injected RNG state, and isolation from module-global RNG state.
- Added canonical Architecture §1.7.1, clarified the future
  `ResolutionResult` example, appended DEC-0011, and marked only Dice Engine
  complete in the Phase 1 Roadmap.

### Changed files

- `src/dnd_engine/domain/value_objects/dice_roll.py` — immutable `DiceRoll`.
- `src/dnd_engine/domain/services/dice.py` — Domain `DiceEngine` port.
- `src/dnd_engine/infrastructure/random/dice.py` — injected Python RNG adapter.
- `tests/domain/test_dice_roll.py` — Domain Value Object tests.
- `tests/infrastructure/test_dice_engine.py` — adapter, notation, and
  determinism tests.
- `docs/ARCHITECTURE.md` — canonical minimal Dice Engine contract.
- `docs/DECISIONS.md` — append-only DEC-0011.
- `docs/ROADMAP.md` — marked only Dice Engine complete in Phase 1.
- `docs/DEVELOPMENT_LOG.md` — this factual iteration entry.

### Verification

- The repository `.venv` launcher referenced an unavailable Python
  installation. Tests used bundled Python 3.12.13 with the existing temporary
  pytest 9.1.1 dependency directory outside the repository and a test-only
  `PYTHONPATH`; no project dependency was added.
- Narrow Dice Engine suite with the cache provider disabled: 53 tests passed.
- Full pytest suite with the cache provider disabled: 139 tests passed.
- `git diff --check` passed; Git emitted only existing Windows checkout
  warnings that LF will be converted to CRLF if Git rewrites changed Markdown
  files.
- No formatter, linter, or type checker is configured in the repository.

### Intentionally deferred

- Event model, Event emission, State Store, State mutation, persistence,
  serialization, RNG state persistence, and replay subsystem.
- `ResolutionResult`, ability checks, saving throws, attacks, damage, healing,
  modifiers, advantage/disadvantage, critical logic, and all other Phase 2
  gameplay rules.
- Full dice DSL, parser packages, production fake framework, API/security
  resource limits, and package-level re-export APIs.

## 2026-08-23 — Phase 1 Event model slice

### Initial state

- Fetched `origin/main` and created `codex/feat/phase-1-event-model` directly
  from the audited commit `c1b07eedceed3f81334c087299583f1399933e16`
  with a clean worktree; current `origin/main` matched the approved Event-model
  task baseline.
- The Event envelope was canonical documentation, but no Domain `GameEvent`,
  Event codec, or Event tests existed. The Domain timestamp type and recursive
  payload immutability semantics were not yet explicit.

### Implemented

- Added one frozen generic `GameEvent` with exactly the nine canonical Domain
  fields, an explicit timezone-aware UTC `datetime`, and intrinsic field/value
  validation without external ID, entity, registry, or gameplay checks.
- Added defensive recursive payload freezing for JSON-compatible values:
  mappings are copied into immutable mapping proxies and arrays into tuples.
- Added a pure `EventSerializer` for the exact camelCase Event envelope,
  canonical UTC `Z` timestamps, normal JSON objects/arrays, nullable-field
  behavior, strict required/unknown envelope fields, and immutable round trips.
- Added deterministic Domain and Infrastructure tests for exact shape, frozen
  and deep-immutable semantics, timestamp constraints, JSON payload validation,
  exact serialization, nullable fields, malformed input, and round trips.

### Canonical contract updates

- Clarified that Phase 1 has one `GameEvent` rather than separate Domain Event
  and envelope types; timestamp is explicit aware UTC `datetime`, payload is
  defensively immutable, and `EventSerializer` is a pure boundary.
- Appended DEC-0012 and marked only Event model complete in Phase 1.

### Changed files

- `src/dnd_engine/domain/events/game_event.py` — immutable generic Event model.
- `src/dnd_engine/infrastructure/persistence/json/event_serializer.py` — pure
  canonical Event codec.
- `tests/domain/test_game_event.py` — Domain Event contract tests.
- `tests/infrastructure/test_event_serializer.py` — Event codec tests.
- `docs/ARCHITECTURE.md` — approved Event contract clarifications.
- `docs/DECISIONS.md` — append-only DEC-0012.
- `docs/ROADMAP.md` — marked only Event model complete.
- `docs/DEVELOPMENT_LOG.md` — this factual iteration entry.

### Verification

- The repository `.venv` launcher was absent. Tests used bundled Python
  3.12.13 with pytest 9.1.1 installed into a temporary directory outside the
  repository and `src` supplied through a test-only `PYTHONPATH`; no project
  dependency was added.
- Focused Event suites with the cache provider disabled: 41 tests passed.
- Full pytest suite with the cache provider disabled: 180 tests passed.
- `git diff --check` passed; Git emitted only the existing Windows checkout
  warnings that LF will be converted to CRLF if it rewrites changed Markdown.
- No formatter, linter, or type checker is configured in the repository.

### Intentionally deferred

- State Store, Event Store, filesystem/JSONL persistence, Event ID and sequence
  allocation, State mutation/application, replay, and Event Sourcing machinery.
- `ResolutionResult`, concrete gameplay Events and payload types, Command/rule
  resolvers, and all Phase 2 gameplay rules.

## 2026-08-23 — Phase 1 Event timestamp review fix

- Tightened Event timestamp deserialization by requiring the parsed UTC
  `datetime` to serialize back to the input's exact canonical Event format.
- Added deterministic regressions for non-canonical ISO 8601 variants,
  serializer-produced fractional microseconds, and explicit JSON null actor and
  causation fields.
- Event serializer suite: 26 tests passed; Domain Event suite: 22 tests passed;
  full pytest suite: 187 tests passed. Tests used bundled Python 3.12.13 and the
  existing temporary pytest 9.1.1 installation outside the repository.
- No Architecture, Decision Log, or Roadmap contract/status change was needed.

## 2026-08-24 — Phase 1 State Store slice

### Initial state

- Fetched `origin/main` and created `codex/feat/phase-1-state-store` directly
  from commit `985eb691f3dda44de006b85384f86cce3fb88dec` with a clean worktree.
- The Phase 1 Event model was merged and all earlier Phase 1 items were
  complete; only State Store remained unchecked in the Roadmap.

### Implemented

- Added frozen `StateSnapshot` as a persistence grouping of one
  `CampaignState` and a tuple of uniquely identified `CreatureState` objects,
  without changing State Ownership.
- Added the snapshot-only Domain `StateStore` Protocol and stable
  `StateStoreError`, `StateNotFoundError`, and `InvalidStateSnapshotError`
  hierarchy.
- Added pure strict `StateSerializer` for exact camelCase schema version 1,
  without defaults or coercion, with nested Domain validation and deterministic
  Creature ordering.
- Added UTF-8 `FilesystemStateStore` at `<root>/<campaign_id>/state.json`, path
  containment at the Infrastructure boundary, stable error translation, and
  atomic same-directory temporary-file replacement through `os.replace`.
- Added deterministic Domain, serializer, and filesystem tests, including
  Event file isolation and atomic failure behavior. Updated Architecture,
  appended DEC-0013, and completed only the Phase 1 State Store Roadmap item.

### Verification

- Narrow StateSnapshot/StateSerializer/FilesystemStateStore suites with the
  cache provider disabled: 68 tests passed.
- Full pytest suite with the cache provider disabled: 255 tests passed.
- Tests used bundled Python 3.12.13 and the existing temporary pytest 9.1.1
  installation outside the repository; the repository `.venv` launcher still
  referenced an unavailable Python installation.
- `git diff --check` passed; Git emitted only existing Windows checkout
  warnings that LF will be converted to CRLF if Git rewrites changed files.
- No formatter, linter, or type checker is configured in the repository.
- `pyproject.toml` and production dependencies were unchanged.

### Intentionally deferred

- EventStore, Event ID/sequence allocation, Event persistence, replay, and
  Event-to-State application.
- Transaction ordering between EventStore persistence and State projection.
- State revisions, optimistic concurrency, locks, migrations, and database
  persistence.
- Commands, gameplay State transitions, future State domains, and all Phase 2
  rules.

## 2026-08-24 — Phase 1 finalization and Phase 2 contract preparation

### Initial state

- Phase 1 implementation and its Roadmap checklist were complete.
- README and the Roadmap still named Phase 1 as the current development phase.
- No Phase 2 gameplay mechanic was implemented.
- The Architecture still left generic Command payloads,
  `ResolutionResult.success`, `state_changes`, expected error representation,
  and the first Phase 2 resolver/application boundary ambiguous.

### Changed

- Aligned README and Roadmap status, officially closed Phase 1, and declared
  Phase 2 — Basic Rules current without completing any Phase 2 item.
- Fixed the boundary between the canonical JSON Command Envelope and concrete
  typed immutable Python gameplay Commands.
- Fixed the exact planned generic `ResolutionResult` fields and separated
  processing success from gameplay success without materializing
  `state_changes`.
- Prepared the minimal `ErrorCode` / `EngineError`, Ability identifier,
  modifier, DC, resolver, result, Event, and read-only Application boundaries
  for the future Ability Check slice.
- Deferred shared GameEngine/framework abstractions and EventStore, and added
  append-only DEC-0014.

### Changed files

- `README.md` — completed Phase 1/current Phase 2 status and current-stack text.
- `CLAUDE.md` — clarified JSON Envelope versus typed Python Command payload.
- `docs/ARCHITECTURE.md` — canonical Phase 2 preparation contracts and
  orchestration boundaries.
- `docs/ROADMAP.md` — Phase 1 completion and current Phase 2 status.
- `docs/DECISIONS.md` — append-only DEC-0014.
- `docs/DEVELOPMENT_LOG.md` — this factual iteration entry.

### Not implemented

- `AbilityCheckCommand`, `AbilityCheckPayload`, `Ability`,
  `AbilityCheckResult`, `ability_modifier`, or an Ability Check resolver.
- An Application handler or runtime `AbilityCheckResolved` production.
- EventStore, replay, event-to-State application, GameEngine, buses,
  dispatcher, registry, or transaction framework.
- Any Phase 2 gameplay mechanics.

### Verification

- Fetched `origin/main` at `7e87d4a96235ae84aa9e0faba272cf71039bee1a`
  and created `codex/chore/finalize-phase-1-phase-2-prep` directly from it with
  a clean working tree.
- Audited all nine Phase 1 Roadmap implementations and their corresponding
  Domain/Infrastructure tests; no implementation gap was found.
- The repository `.venv` launcher remained broken and PATH had no Python.
  Tests used bundled Python 3.12.13 with pytest 9.1.1 installed into a temporary
  dependency directory outside the repository and `src` supplied through a
  test-only `PYTHONPATH`; no project dependency was added.
- Full pytest suite with the cache provider disabled: 255 tests passed.
- Repository-wide status/contract searches and full diff review completed;
  historical statements in append-only logs were left unchanged.
- `git diff --check` passed; Git emitted only the existing Windows checkout
  warnings that LF will be converted to CRLF if Git rewrites changed files.
- No formatter, linter, type checker, or additional documentation check is
  configured in the repository.

## 2026-08-24 — Command lifecycle documentation deduplication

### Initial state

- Fetched `origin/main` and created `claude/docs-command-lifecycle-dedup-ci9085`
  directly from commit `ac78dca6ae2b40099810f92a800300b807e0f718` with a clean
  worktree.
- `docs/ARCHITECTURE.md` described the Command lifecycle twice with two
  incompatible state vocabularies: §3.3 used `Created → Validating →
  Valid | Invalid → Executing → Completed | Failed`, and §9.7 used
  `Created → Validating → Rejected | Accepted → Resolving → Completed | Failed`.

### Changed

- Removed the duplicate `flowchart LR` mermaid diagram under the unnumbered
  `#### Command lifecycle` subsection in §3.3 Command Contract and replaced it
  with a short reference to §9.7 Command lifecycle as the single canonical
  description.
- Left §9.7 Command lifecycle, the Quick lookup table, and the table of
  contents unchanged.
- Appended append-only DEC-0015 recording the decision.

### Changed files

- `docs/ARCHITECTURE.md` — deduplicated the §3.3 Command lifecycle subsection.
- `docs/DECISIONS.md` — append-only DEC-0015.
- `docs/DEVELOPMENT_LOG.md` — this factual iteration entry.

### Not implemented

- `CLAUDE.md` still states the stale `Received → ...` Command lifecycle
  variant; correcting it is deferred to a separate slice.
- No Python, test, rule, or campaign file was changed. No `AbilityCheckCommand`,
  `Ability`, `ErrorCode`, `EngineError`, `ResolutionResult`, or other Phase 2
  contract was implemented, stubbed, or scaffolded.

### Verification

- Full pytest suite: 255 tests passed.
- `git diff --check` passed.
- `git diff --stat` against `origin/main` touched exactly
  `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, and `docs/DEVELOPMENT_LOG.md`.

## 2026-08-24 — CLAUDE.md rebuild and duplication policy (DEC-0016)

### Initial state

- Fetched `origin/main` and worked from commit
  `03aaf901b407b76c3fc9de8b0e919a20ca2e9111` on branch
  `claude/docs-claude-md-rebuild-6w8etl`, which the session's harness had
  already created at that same commit with a clean worktree.
- `CLAUDE.md` reproduced a third, invented Command lifecycle vocabulary
  (`Received → Rejected | Accepted → Resolving → Completed | Failed`) whose
  initial state `Received` existed nowhere in the canon — the exact stale
  variant DEC-0015 left open for a separate slice. It also duplicated three
  canonical structures verbatim (the full ID reference table, the full State
  Ownership matrix, both Envelope JSON examples) while omitting every
  implemented Phase 1 contract, the phase-scope rule, the §3.6
  deferred-abstractions list, the mandatory `docs/DEVELOPMENT_LOG.md` append
  rule, the document map, and branch/PR policy.

### Changed

- Rebuilt `CLAUDE.md` in full: added a document map, current-phase and
  phase-discipline statement, a table of implemented Phase 1 contracts, a
  list of fixed-but-unimplemented Phase 2 preparation contracts, the §3.6
  deferred-abstractions list, the single canonical Command lifecycle from
  §9.7 (removing the stale `Received` variant), a naming-traps table
  covering points where default intuition diverges from the canon, and
  branch/PR/tooling policy. Removed the verbatim ID table, Owner Matrix, and
  both JSON envelope examples in favor of section references.
- Appended append-only DEC-0016 recording the CLAUDE.md duplication policy:
  the file reproduces verbatim only single facts an agent can violate
  without noticing (names, closed value sets, phase status, prohibitions),
  never structures (tables, field lists, JSON schemas), which live in
  exactly one place in `docs/ARCHITECTURE.md`.
- Verified every `§N.N` reference against its `docs/ARCHITECTURE.md` section
  subject and every `docs/ARCHITECTURE.md#slug` anchor against the GitHub
  slug of its actual heading text; all 23 links and all bare section
  references matched with no corrections required.

### Changed files

- `CLAUDE.md` — full rebuild per the fixed text supplied for this task.
- `docs/DECISIONS.md` — append-only DEC-0016.
- `docs/DEVELOPMENT_LOG.md` — this factual iteration entry.

### Not implemented

- No Python, test, rule, or campaign file was changed.
- `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `README.md`, and `AGENTS.md`
  were read for verification but not modified.
- No Phase 2 contract (`AbilityCheckCommand`, `Ability`, `ErrorCode`,
  `EngineError`, `ResolutionResult`, etc.) was implemented, stubbed, or
  scaffolded.

### Verification

- Anchor corrections: none. All 23 `docs/ARCHITECTURE.md#slug` links and the
  four bare `§9.7` / `§12.9` / `§3.2.3` references matched the canon exactly;
  no `§12.13` bare reference exists anywhere in the fixed `CLAUDE.md` text
  actually supplied for this task, so none was left to verify or correct.
- Section-number and factual-claim spot checks against
  `docs/ARCHITECTURE.md`: the §9.7 Command lifecycle string, the 13-value
  `DamageType` enum, `current_hp`/`max_hp` and `currentHp`/`maxHp` HP naming
  (also DEC-0008), the §3.6 deferred-abstractions list, and the
  `ResolutionResult`/`ErrorCode` statements in §3.5/§3.9 all matched
  verbatim; no mismatch found.
- Phase status cross-checked against `docs/ROADMAP.md`: Phase 0 and Phase 1
  complete, Phase 2 — Basic Rules current; matches.
- Python 3.11.15 was the ambient interpreter in this environment, below the
  `>=3.12` target declared in `pyproject.toml`/`AGENTS.md`; a Python 3.12.3
  virtualenv was created in the session scratchpad and used for the
  installation and test run below instead.
- `pip install -e ".[dev]"` succeeded under Python 3.12.3 (pytest 9.1.1).
- Full pytest suite: 255 passed, matching the expected count on `main`.
- No formatter, linter, or type checker is configured in this repository;
  none was installed or run — reported as `not configured`.
- `git diff --check` passed.
- `git diff --stat` against `origin/main` touched exactly `CLAUDE.md`,
  `docs/DECISIONS.md`, and `docs/DEVELOPMENT_LOG.md`.
- No formatter, linter, or type checker is configured in the repository.

## 2026-08-24 — §3.7 Action Lifecycle edge labels

- Relabelled the two validation edges of the §3.7 Action Lifecycle diagram in
  `docs/ARCHITECTURE.md` from `Invalid` / `Valid` to `Rejected` / `Accepted`,
  matching the canonical §9.7 Command lifecycle vocabulary. No node, no other
  edge, no heading, and no surrounding text changed.
- These were the last occurrence in the canonical contract of the vocabulary
  DEC-0015 rejected, which `CLAUDE.md` already described as rejected.
- No Decision Log entry was added: this changes no Envelope, ID format, State
  Ownership, serialization, or dependency direction.
- A repository-wide sweep for `Received`, `Executing`, and standalone `Valid` /
  `Invalid` found no remaining live use outside append-only history and the
  two `CLAUDE.md` lines that describe the rejected vocabulary.
- Full pytest suite on Python 3.12.9 with pytest 9.1.1: 255 passed. No source,
  test, rule, or campaign file was changed.
- No formatter, linter, or type checker is configured in the repository.

## 2026-08-24 — Change authorisation and diff-review workflow

- Branch `claude/docs-change-authorisation`, based on `origin/main` at
  `7c249b5b8f63eb9d1fa16173acc008c1fa35977f`.
- Added a new top-level "Change authorisation and diff review" section to
  `AGENTS.md`, placed immediately after the existing "Branches and pull
  requests" section at the end of the file. It states that commit, push, PR
  creation, and merge require separate authorisation given after the user
  has seen the diff, that authorisation embedded in the task description
  does not count, and that a `review.patch` diff must be produced instead.
- In `CLAUDE.md`, section "Ветки, PR и инструменты", replaced the two
  bullets on commit/push/PR/merge authorisation and PR draft policy with
  four bullets covering separate authorisation after diff review, the
  mandatory `review.patch` artefact, PR draft policy, and the missing-`gh`
  stop condition, followed by a reference paragraph pointing to the new
  `AGENTS.md` section.
- Added a `.gitignore` block ignoring `*.patch` and `*.diff` review
  artefacts; no prior rule in the file covered either pattern.
- No Decision Log entry was added: this changes no Envelope, ID format,
  State Ownership, serialization, or dependency direction.
- Full pytest suite on Python 3.12.9 with pytest 9.1.1: 255 passed. No
  source, test, rule, or campaign file was changed.
- No formatter, linter, or type checker is configured in the repository.
- Diff written to `review.patch` in the repository root for review; not
  committed.

## 2026-08-24 — Campaign ID format fixed in the canonical contract

- Branch `claude/docs-campaign-id-format`, based on `origin/main` at
  `e73d9632965aea1e7fcdb1bb981862b3cd364aa8`.
- In `docs/ARCHITECTURE.md` §4.12, added a paragraph after the `Campaign
  IDs` code block stating that Campaign ID uses the strict numeric format
  `campaign_NNN` and that semantic IDs, permitted for Quest and Location,
  are forbidden for Campaign.
- In `docs/ARCHITECTURE.md` §4.13, inserted a `Campaign | campaign_NNN |
  campaign_001` row between the `Definition` and `Character` rows.
- Appended DEC-0017 to `docs/DECISIONS.md`, recording the decision and its
  rationale.
- §4.2's example list still omits Campaign, §4.10 states no uniqueness
  scope for Campaign, and §4.11 assigns no ID-generating service for
  Campaign; all three gaps are left untouched, as this is a
  documentation-only slice.
- Implementation check: every campaign ID literal found in `src/`,
  `tests/`, and `campaigns/` is `campaign_001` or `campaign_002`, all
  matching `campaign_NNN`; `rules/` has none. The three `campaign_id`
  values used in `tests/infrastructure/test_state_store.py`'s path-escape
  test (`../outside`, `nested/campaign`, `..`) are inputs the test asserts
  are rejected, not accepted campaign IDs. No component validates campaign
  ID format by pattern — `FilesystemStateStore` only checks the value is a
  `str` and that the resolved path stays a direct child of the store root;
  `CampaignState` and the JSON serializers require a `str` with no shape
  check. No contradiction with `campaign_NNN` was found.
- Full pytest suite on Python 3.12.9 with pytest 9.1.1: 255 passed. No
  source, test, rule, or campaign file was changed.
- No formatter, linter, or type checker is configured in the repository.
- Diff written to `review.patch` in the repository root for review; not
  committed.

## 2026-08-24 — AGENTS.md deduplicated and CLAUDE.md resync obligation added

- Branch `claude/docs-agents-resync-rule-dec18`, based on `origin/main` at
  `0e7d9a7d174d3b1088c050a1e3d7a39de88801ba`.
- In `AGENTS.md` "Branches and pull requests", removed the last bullet
  duplicating commit/push/PR/merge authorisation, closed the bullet list
  on the preceding item, and replaced the two authorisation paragraphs
  plus the trailing "Do not merge without explicit authorization." line
  with a single cross-reference to "Change authorisation and diff review",
  which remains the sole statement of those rules.
- In `AGENTS.md` "Working method", inserted a paragraph after the
  canonical-contracts sentence requiring `CLAUDE.md` to be reread and,
  within the same slice, updated whenever a canonical contract change
  affects one of the specific facts it reproduces per DEC-0016.
- Appended DEC-0018 to `docs/DECISIONS.md`, recording both changes and
  their shared motivation.
- `CLAUDE.md` itself was not modified: it is already consistent with the
  new rule, and this slice adds the obligation to reread it, it does not
  exercise that obligation against a contract change.
- Full pytest suite on Python 3.12.9 with pytest 9.1.1: 255 passed (run
  with `--basetemp` pointed outside the default OS temp directory, whose
  `pytest-of-redbu` folder was not writable in this environment). No
  source, test, rule, or campaign file was changed.
- No formatter, linter, or type checker is configured in the repository.
- Diff written to `review.patch` in the repository root for review; not
  committed.

## 2026-08-24 — Campaign ID gaps and missing-gh PR gate documented

- Branch `claude/docs-campaign-id-gaps`, based on `origin/main` at
  `8fefbbb3dde54f745e9b095f99835e0888470080`.
- In `docs/ARCHITECTURE.md`, added `campaign_001` to the §4.2 runtime ID
  examples and documented Campaign uniqueness within campaigns root in §4.10.
- In `CLAUDE.md`, clarified that missing `gh` blocks an authorised PR creation
  attempt but does not block commit or push.
- No Decision Log entry was added because both edits document behaviour already
  implied by the canon and Phase 1 filesystem layout, while the `gh` change only
  clarifies repository workflow. The §4.11 Campaign ID generation-service gap
  recorded by DEC-0017 remains deliberately open.
- Full unchanged pytest suite on bundled external Python 3.12.13 with pytest
  9.1.1: 255 passed. No source or test file was changed.
- No formatter, linter, or type checker is configured in the repository.
- Diff written to
  `C:\Users\redbu\Documents\GitHub\ai-dnd-master\review.patch` for review;
  not committed.

## 2026-08-24 — Phase 2 Ability Check contract gates

### Initial state

- Fetched `origin/main` and created `feat/phase-2-ability-check-slice`
  directly from `e204ae48766fec10ce7bf1290dc4bbe235a00820` with a clean
  worktree.
- Phase 1 was complete, no Phase 2 mechanic was marked complete, and no
  `ResolutionResult`, `Ability`, Ability Check Command/result/resolver,
  Application handler, `EngineError`, Event metadata provider, or EventStore
  production implementation existed.
- The planned `ResolutionResult` duplicated rolls, while Application Event
  creation and deferred EventStore ID allocation left metadata responsibility
  ambiguous.

### Canonical contract changes

- Added the planned injected `EventMetadata` / `EventMetadataProvider`
  application-facing seam. Application handlers do not allocate Event IDs or
  read the system clock; the provider is not durable EventStore semantics, and
  EventStore remains deferred as the future authoritative durable sequence/ID
  allocator.
- Removed generic top-level `ResolutionResult.rolls` and fixed success,
  failure, and Event-command-correlation invariants without requiring Events
  for every successful future use case.
- Retained the generic `GameEvent` envelope and fixed
  `AbilityCheckResolvedPayloadV1` plus the
  `build_ability_check_resolved_v1(...)` builder boundary.
- Appended DEC-0019, which supersedes only the affected exact field and Event
  metadata responsibility provisions of historical DEC-0014.
- Reordered the unchecked Phase 2 mechanics to Ability checks, Proficiency,
  Saving throws, Skills, AC, Attack rolls, HP, Damage, Healing, Conditions.
- Resynchronised the corresponding planned-contract summary and naming traps
  in `CLAUDE.md`.

### Changed files

- `docs/ARCHITECTURE.md` — Application metadata, ResolutionResult, and Ability
  Check Event payload/builder contracts.
- `docs/ROADMAP.md` — Phase 2 dependency order only; no item completed.
- `docs/DECISIONS.md` — append-only DEC-0019.
- `CLAUDE.md` — canonical-summary synchronisation.
- `docs/DEVELOPMENT_LOG.md` — this factual iteration entry.

### Not implemented

- No production Python code, tests, rules, campaign data, dependency, State
  mutation, persistence, EventStore, bus, dispatcher, or framework abstraction
  was added or changed.

### Verification

- Bundled Python 3.12.13 with pytest 9.1.1 installed into a temporary external
  dependency directory; no project dependency changed.
- Full pytest suite with the cache provider disabled: 255 tests passed.
- Repository searches confirmed the planned contracts still have no
  production implementation and the Phase 2 checklist contains the exact
  requested unchecked order.
- `git diff --check` passed; Git emitted only Windows checkout warnings that LF
  will be converted to CRLF if Git rewrites the changed Markdown files.
- No formatter, linter, or type checker is configured in the repository:
  `not configured`.

## 2026-08-24 — Phase 2 Ability Check Domain foundation

### Initial state

- Continued on `feat/phase-2-ability-check-slice`, based on
  `e204ae48766fec10ce7bf1290dc4bbe235a00820`, with only the expected
  uncommitted Task 1 documentation changes in the worktree.
- Task 1 had fixed the Domain contracts and Application metadata boundary, but
  no Phase 2 production types, rule resolver, concrete Event payload builder,
  or related tests existed.

### Implemented

- Added the six-value `Ability` Domain `StrEnum` and the frozen typed
  `AbilityCheckPayload` / `AbilityCheckCommand` without a generic Command base.
- Added the minimal `ErrorCode` / frozen `EngineError` contracts and generic
  frozen `ResolutionResult[T]` with success/failure and Event correlation
  invariants, without `rolls` or `state_changes` fields.
- Added the pure `ability_modifier` rule, immutable `AbilityCheckResult`, and
  deterministic `resolve_ability_check(...)` using exactly one injected
  `DiceEngine.roll("1d20")` call.
- Added immutable `AbilityCheckResolvedPayloadV1` and
  `build_ability_check_resolved_v1(...)`, preserving generic `GameEvent` and
  deriving its fixed v1 envelope/payload from the Command and resolver outcome.
- Added an AST-based architecture test that checks every Domain Python module
  for forbidden imports from Application, Infrastructure, or API.

### Changed files

- `src/dnd_engine/domain/value_objects/ability.py` — closed ability identifier.
- `src/dnd_engine/domain/commands/ability_check.py` — typed payload and Command.
- `src/dnd_engine/domain/errors.py` — error code and structured error.
- `src/dnd_engine/domain/resolution.py` — generic resolution result.
- `src/dnd_engine/domain/rules/ability_check.py` — modifier, result, and resolver.
- `src/dnd_engine/domain/events/ability_check.py` — typed payload and generic
  Event builder.
- `tests/domain/test_ability_check.py` — Ability, Command, modifier, resolver,
  derived-result, dice-call, and non-mutation tests.
- `tests/domain/test_resolution_result.py` — errors and result invariants.
- `tests/domain/test_ability_check_event.py` — payload/builder and existing
  Event serialization integration.
- `tests/architecture/test_domain_dependencies.py` — Domain dependency guard.
- `docs/ARCHITECTURE.md` and `CLAUDE.md` — minimal implemented-status sync.
- `docs/DEVELOPMENT_LOG.md` — this factual iteration entry.

### Boundaries preserved

- The resolver does not mutate `CreatureState` or `AbilityScores`, load or save
  State, create Events, allocate IDs, read a clock, serialize, or import an
  outer layer.
- The Event builder accepts injected ID/timestamp and performs no persistence.
- No Application handler, `EventMetadataProvider` code, metadata allocator,
  EventStore, State mutation, registry, dispatcher, bus, framework abstraction,
  future mechanic, API, dependency, or AI integration was added.
- The Phase 2 Ability checks Roadmap item remains unchecked until the
  Application vertical slice is complete.

### Verification

- Python 3.12.13 with pytest 9.1.1 from the existing temporary external
  dependency directory; project dependencies were unchanged.
- Narrow `tests/domain tests/architecture` suite: 193 tests passed.
- Full pytest suite: 313 tests passed.
- The AST architecture test passed with no Domain → Application,
  Infrastructure, or API imports.
- `git diff --check` passed; Git emitted only Windows checkout warnings that LF
  will be converted to CRLF if Git rewrites changed files.
- Formatter, linter, and type checker remain `not configured`.

## 2026-08-24 — Domain dependency guard relative-import correction

- Corrected the architecture test's relative-import resolution by deriving the
  package from the source path without its filename and using stdlib
  `importlib.util.resolve_name`.
- Added regression coverage for forbidden relative imports from an ordinary
  Domain module and `domain/__init__.py`, allowed Domain-relative imports
  including `from . import ...`, absolute forbidden imports, and the current
  production Domain tree scan.
- Production code and Ability Check contracts were unchanged; Application Task
  3 was not started and no dependency was added.
- Python 3.12.13 / pytest 9.1.1: `tests/architecture` — 5 passed;
  `tests/domain tests/architecture` — 197 passed; full suite — 317 passed.
- `git diff --check` passed; formatter, linter, and type checker remain
  `not configured`.

## 2026-08-24 — Ability Check documentation status correction

- In `docs/ARCHITECTURE.md` §3.10, changed the stale `Future payload v1`
  label to `Canonical payload v1` for the implemented
  `AbilityCheckResolvedPayloadV1` contract.
- In §12.10, kept EventStore, durable Event ID/sequence allocation, JSONL
  append, replay, and Event application deferred while recording that the
  generic `GameEvent` envelope and first concrete Ability Check payload/builder
  are implemented.
- No production code, tests, Roadmap status, architectural decision, contract
  schema, or dependency changed; Application Task 3 was not started.
- Full pytest suite on Python 3.12.13 / pytest 9.1.1: 317 passed.
- `git diff --check` passed.

## 2026-08-24 — Phase 2 Ability Check read-only vertical slice

### Initial state

- Continued on `feat/phase-2-ability-check-slice`, based on
  `e204ae48766fec10ce7bf1290dc4bbe235a00820`.
- The Task 1 and Task 2 foundation was present in existing commit `d90ccda`
  rather than as the expected uncommitted worktree changes; the worktree was
  clean at precheck and the committed contracts matched the agreed design.
- Task 2 Domain and architecture precheck: 62 tests passed.
- After review, the uncommitted Task 3 change-set was normalized onto
  `feat/phase-2-ability-check-application`, created directly from current
  `origin/main` at `7a3b8108c044cdcf12913a10eb624c289c7e8933`; that history
  already contains `d90ccda` through PR #35.

### Implemented

- Added frozen `EventMetadata` with exact-string Event ID and exact aware UTC
  `datetime` validation, plus the minimal `EventMetadataProvider` Application
  protocol. No concrete production allocator was added.
- Added explicit `AbilityCheckHandler`: it loads one snapshot, finds the actor,
  calls the deterministic resolver, obtains injected Event metadata, builds one
  `AbilityCheckResolved` v1 `GameEvent`, and returns a typed
  `ResolutionResult[AbilityCheckResult]`.
- Missing actors return `ENTITY_NOT_FOUND` as a processing failure without a
  dice roll, metadata request, Event, or save. A failed gameplay check remains
  successful processing and publishes its resolved Event.
- The handler is read-only: it creates no working copy, applies no Event to
  State, mutates no `CreatureState`, and never calls `StateStore.save()`.

### Tests and status documentation

- Added nine Application tests with local fakes/spies for successful and failed
  gameplay checks, missing actor behavior, State non-mutation, exact metadata
  injection and validation, exception propagation, and absence of saves.
- Marked only Phase 2 Ability checks complete in the Roadmap and retained the
  Task 1 dependency order for all remaining mechanics.
- Updated Architecture, README, and CLAUDE status text to describe the completed
  slice while retaining EventStore, Event persistence, State application,
  transaction/UoW, buses, dispatcher, and GameEngine as deferred.

### Verification and boundaries

- Python 3.12.13 / pytest 9.1.1: Application tests — 9 passed; full suite —
  326 passed. Domain dependency test remains green.
- No production or development dependency was added. Formatter, linter, and
  type checker remain `not configured`.
- No EventStore, Event persistence, State mutation/application, transaction or
  UoW, bus, dispatcher, GameEngine, registry, future Phase 2 mechanic, database,
  API, AI integration, or expanded dice DSL was added.

## 2026-08-26 — Phase 2 Group 1 hardening and current maintenance

### Initial state

- Fetched `origin/main` and created `codex/phase2-group1-hardening` directly
  from `8fc3c4642d44cded80aa12f1daf91de484a46327` with a clean worktree.
- The completed read-only Ability Check used production adapters but had no
  integration test joining filesystem State persistence, deserialization,
  Application orchestration, and injected production RNG.
- Current-contract documentation had no automated local-link/section-reference
  check or general runtime-validation ownership policy, and README still
  described replay-oriented storage more strongly than current capabilities.

### Implemented

- Added one deterministic real-adapter Ability Check integration test using
  `FilesystemStateStore`, its actual `StateSerializer`/JSON path,
  `PythonDiceEngine(random.Random(...))`, and a test-only fixed Event metadata
  provider. It verifies typed outcome/Event consistency, unchanged persisted
  `state.json` bytes, and absence of temporary or Event artifacts.
- Added a stdlib-only repository documentation-reference test for local
  Markdown files/anchors and current `§...` Architecture section references;
  historical Decision/Development Log section references remain outside the
  current-contract check.
- Added canonical runtime-validation ownership policy §12.25 and append-only
  DEC-0020. Strict boundary shape/type/version/reference validation is separated
  from intrinsic Domain invariants, with no silent Domain coercion and no
  symmetry-driven mass `__post_init__` retrofit.
- Clarified README storage/replay capability and added narrow
  Implemented/Planned/Deferred markers to affected Event lifecycle,
  persistence, ordering, projection, replay, and atomic-mutation sections.
- Updated CI to one Python 3.12/3.13/3.14 matrix, `contents: read`, and the
  current official `actions/checkout@v7` / `actions/setup-python@v7` majors.

### Verification

- Clean external Python 3.12.13 virtual environment: editable `.[dev]` install
  completed with pytest 9.1.1; no project dependency changed.
- New integration test: 1 passed.
- New documentation-reference tests: 2 passed.
- Existing Application suite: 9 passed.
- Architecture suite: 7 passed.
- Infrastructure suite: 118 passed.
- Full suite after code/documentation/CI changes: 329 passed.
- No formatter, linter, or type checker is configured: `not configured`.

### Intentionally deferred

- `TEST-02` `dataclasses.Field.type` cleanup: no touched test required it and no
  observed compatibility failure reached its conditional trigger.
- Static type checking, concurrency/revisions, database/ORM, full dice DSL,
  generic registries/dispatcher, EventStore, runtime Event append, replay,
  State mutation/application, and transaction/UoW remain unimplemented.
- Existing broad runtime-constructor validation gaps in simple State/Definition
  dataclasses were not retrofitted; DEC-0020 records the policy without claiming
  that a complete Domain-invariant audit has already been performed.

## 2026-08-26 — Group 2 tooling quality track

### Initial state

- Pytest was the only configured development check; mypy was neither a
  development dependency nor configured in `pyproject.toml`.
- CI already tested Python 3.12, 3.13, and 3.14 with
  `actions/checkout@v7` and `actions/setup-python@v7`, so the earlier CI hygiene
  finding required no additional compatibility or Action-version change.
- Four tests inspected annotation objects through `dataclasses.Field.type`:
  the `CreatureState`, `CampaignState`, `MonsterDefinition`, and
  `WeaponDefinition` tests.

### Implemented

- Added mypy as a development-only dependency and configured an incremental
  Python 3.12 baseline for `src/dnd_engine`, with error codes and unused-config
  warnings enabled.
- Added one Python 3.12 CI `typecheck` job, separate from the unchanged pytest
  compatibility matrix.
- Removed the four brittle annotation-object assertions while retaining exact
  canonical field-name tests and the meaningful constructed-value assertions.
- Added the configured type-check command to the README quick start.

### Verification

- A clean editable `.[dev]` install completed in a temporary Python 3.12.13
  environment with mypy 1.20.2 and pytest 9.1.1.
- The four affected Domain test files passed: 42 tests.
- `python -m mypy src/dnd_engine` passed with no issues in 48 source files; no
  source typing changes or new ignores were required.
- The full pytest suite passed: 328 tests.
- `git diff --check` passed.

### Intentionally deferred

- Strict mypy mode and mypy checking of the test suite.
- Formatter, linter, pre-commit, tox/nox, and coverage tooling.
- Production dependency changes and unrelated runtime refactors.

## 2026-08-26 — Phase 2 Proficiency foundation

### Initial state

- Fetched `origin/main` and created
  `codex/phase2-proficiency-foundation` directly from
  `93faa86a395c1545879ea3e5029a3a3c48fd0816` with a clean worktree.
- Phase 2 Ability checks were complete while Proficiency remained unchecked;
  no character-level proficiency rule, authoritative character level, or
  proficiency membership model existed.

### Implemented

- Added the pure Domain rule `character_proficiency_bonus(level)` for exact
  integer character levels `1..20`, with the canonical `+2..+6` progression,
  `TypeError` for invalid runtime types, and `ValueError` outside the intrinsic
  character-level range.
- Added parameterized Domain tests for every tier boundary, non-exact integer
  inputs including `bool`, and out-of-range levels.
- Added canonical Architecture §3.11, append-only DEC-0021, and the minimal
  implemented-contract reference in `CLAUDE.md`.
- Kept the Roadmap Proficiency item unchecked because this foundation does not
  complete the overall mechanic.

### Verification

- Python 3.12.13 in a temporary external virtual environment with the existing
  declared development dependencies: pytest 9.1.1 and mypy 1.20.2.
- New Proficiency tests: 17 passed. The first run reported one cache-write
  warning from the pre-existing inaccessible repository `.pytest_cache`;
  subsequent pytest checks disabled the cache provider.
- Ability Check and CreatureState regression tests: 55 passed.
- Documentation-reference tests: 2 passed.
- Full pytest suite: 345 passed.
- `python -m mypy src/dnd_engine`: no issues in 49 source files.
- `git diff --check` passed; Git emitted only Windows checkout warnings that LF
  will be converted to CRLF if Git rewrites the changed files.

### Intentionally deferred

- Authoritative character-level State, proficiency membership for skills,
  saving throws, attacks, tools, and other mechanics, Expertise, half/double
  proficiency, and stacking rules.
- Monster proficiency by Challenge Rating, `CreatureState` or State snapshot
  schema changes, Ability Check integration, generic modifier/proficiency
  frameworks, and new orchestration or persistence abstractions.

## 2026-08-26 — Phase 2 Group 3A canonical d20 semantics

### Initial state

- Fetched `origin/main` and created `codex/phase2-d20-semantics` directly from
  `e9715f7398844f4f0e237c4892e66405e180e0a4` with a clean worktree.
- The Ability Check vertical slice used `DiceRoll.total`, wrote
  `AbilityCheckResolved` V1, and had no shared effective d20 selection contract.

### Implemented

- Added the closed `RollMode` enum, immutable validated
  `D20Roll(mode, rolls, selected)`, and concrete `resolve_d20_roll()` rule.
- Implemented one independent `"1d20"` call for NORMAL and two independent
  `"1d20"` calls for ADVANTAGE/DISADVANTAGE, with strict validation of each
  primitive `DiceEngine` response and no `"2d20"` shortcut.
- Migrated `AbilityCheckResult` and `resolve_ability_check()` to `D20Roll` and
  `roll.selected`, adding the keyword-only effective `roll_mode` seam with a
  NORMAL default while leaving the Command contract unchanged.
- Added `AbilityCheckResolvedPayloadV2` and its builder as the current writer;
  retained V1 as the exact legacy `DiceRoll` schema for NORMAL outcomes only
  and rejected lossy ADVANTAGE/DISADVANTAGE conversion.
- Updated Domain, Application, integration, and `ResolutionResult` fixtures and
  tests, canonical Architecture §§3.10/3.12/12.10, append-only DEC-0022, and
  the reproduced Phase 2 facts in `CLAUDE.md`. `docs/ROADMAP.md` was unchanged.

### Verification

- Python 3.12.13 in a temporary external virtual environment with the existing
  declared dev dependencies: pytest 9.1.1 and mypy 1.20.2. The repository
  `.venv` launcher was stale and referenced a missing local Python executable.
- New d20 tests: 32 passed.
- Migrated Ability Check Domain/Event/Application/integration tests: 56 passed.
- Documentation-reference tests: 2 passed.
- Full pytest suite: 384 passed.
- `python -m mypy src/dnd_engine`: no issues in 51 source files.
- `git diff --check` passed; Git emitted only Windows LF-to-CRLF checkout
  warnings for changed files.

### Intentionally deferred

- Saving Throws, Skills, Attack Rolls, AC, authoritative character level,
  proficiency membership, Conditions, Effects, and advantage/disadvantage
  source aggregation or cancellation.
- Generic modifier/check frameworks, rerolls, Lucky, critical-hit or automatic
  natural-1/natural-20 semantics, EventStore/runtime Event persistence, replay,
  State mutation, buses, registries, dispatcher, and broader orchestration.

## 2026-08-26 — Phase 2 character proficiency State prerequisites

### Initial state

- Fetched `origin/main` and created
  `codex/phase2-character-proficiency-state` directly from
  `38f90097962f0c13d5f27a84e1c154f6334b846f` with a clean worktree.
- The implemented character proficiency formula had no authoritative total
  character level or Saving Throw proficiency membership State, and strict
  State snapshot schema V1 contained only Campaign and Creature projections.

### Implemented

- Added mutable `CharacterState` with exactly `id`, exact integer
  `total_level` in `1..20`, and actual immutable
  `frozenset[Ability]` Saving Throw proficiency membership.
- Expanded frozen `StateSnapshot` with backward-compatible
  `characters=()`, unique Character IDs, and the invariant that every
  Character projection has a corresponding Creature projection with the same
  runtime ID.
- Advanced the current State storage schema to V2. `StateSerializer` now
  writes only exact V2 with deterministic Creature, Character, and proficiency
  ordering; it reads exact V2 and exact legacy V1, mapping V1 to
  `characters=()` without invented progression defaults.
- Kept `FilesystemStateStore` production code unchanged; its existing
  serializer delegation now saves and loads V2 while retaining V1 read
  compatibility.
- Updated canonical Architecture, added append-only DEC-0023, and synchronized
  the reproduced State/proficiency facts in `CLAUDE.md`. The Roadmap remained
  unchanged.

### Verification

- Python 3.12.13 from the existing temporary external virtual environment with
  pytest 9.1.1 and mypy 1.20.2; no dependency was added.
- CharacterState/StateSnapshot/StateSerializer/StateStore narrow suites: 112
  passed.
- Proficiency, d20, Ability Check Domain/Event/Application/integration
  regressions: 105 passed.
- Documentation-reference tests: 2 passed.
- Full pytest suite: 428 passed.
- `python -m mypy src/dnd_engine`: no issues in 52 source files.
- `git diff --check` passed; Git emitted only Windows LF-to-CRLF checkout
  warnings for changed files. Formatter and linter remain not configured.

### Intentionally deferred

- Saving Throw Command/resolver/Event/handler and any State mutation use case.
- Skills, Expertise, other proficiency categories or provenance, class/XP/
  level-up systems, and monster proficiency/Challenge Rating paths.
- Generic proficiency/modifier frameworks, new State owners, EventStore,
  replay, transactions, buses, registries, frameworks, and dependencies.

## 2026-08-26 — Phase 2 Character Saving Throw vertical slice

### Initial state

- Fetched `origin/main` and created
  `codex/phase2-character-saving-throw` directly from
  `f533813f66c304f3a475eacc172776287d0cf6ed` with a clean worktree.
- The repository already contained `CharacterState`, character proficiency
  progression, shared d20 selection semantics, `ResolutionResult`,
  `EventMetadataProvider`, and State schema V2, but no Saving Throw
  Command/resolver/Event/handler flow.

### Implemented

- Extracted the pure `ability_modifier()` rule to `domain.rules.ability` and
  preserved the existing Ability Check import path through a module-level
  import without changing Ability Check behavior.
- Added immutable `SavingThrowPayload` / `SavingThrowCommand`, the
  character-specific `resolve_character_saving_throw(...)`, and immutable
  `SavingThrowResult` with separate ability-modifier and proficiency-bonus
  contributions.
- Composed authoritative `CreatureState` ability scores with matching
  `CharacterState` total level and Saving Throw proficiency membership. The
  resolver delegates NORMAL/ADVANTAGE/DISADVANTAGE to `resolve_d20_roll()` and
  applies no automatic natural-1/natural-20 result semantics.
- Added typed `SavingThrowResolvedPayloadV1` and a generic `GameEvent` builder
  with the current d20 shape and separate `abilityModifier` /
  `proficiencyBonus` audit fields.
- Added explicit `SavingThrowHandler`. Missing Creature returns
  `ENTITY_NOT_FOUND`; missing matching Character projection returns
  `INVALID_STATE`. Infrastructure/programming failures propagate.
- Preserved read-only behavior: the handler never calls `StateStore.save()`,
  does not apply Events to State, and creates no persisted Event artifact.
- Added Domain, Application, and real-adapter integration coverage; updated
  canonical Architecture §3.13, proficiency/d20/current-status references,
  Event serialization documentation, append-only DEC-0024, and `CLAUDE.md`.
  `docs/ROADMAP.md` and State/persistence contracts were unchanged.

### Verification

- Python 3.12.13 in a temporary external virtual environment with the existing
  declared dependencies: pytest 9.1.1 and mypy 1.20.2; no dependency changed.
- New/shared Domain tests: 64 passed.
- New Application and real-adapter integration tests: 8 passed.
- Ability Check/proficiency/d20 regressions: 105 passed.
- Documentation-reference tests: 2 passed.
- Full pytest suite: 500 passed.
- `python -m mypy src/dnd_engine`: no issues in 57 source files.
- `git diff --check` passed.
- Formatter and linter remain not configured.

### Intentionally deferred

- Monster Saving Throws, Challenge Rating and monster proficiency sources,
  Death Saving Throws, Skills, Expertise, and other proficiency categories.
- Conditions/Effects and advantage-source aggregation/cancellation, rerolls,
  spells/effects that create Saving Throw Commands, and source Event causality.
- Generic modifier/check/resolver frameworks, EventStore/runtime Event
  persistence, replay, State mutation/application, transaction/UoW, buses,
  registries, frameworks, databases, and new dependencies.

## 2026-08-27 — Phase 2 Skill proficiency State foundation

### Initial state

- Fetched `origin/main` and created
  `codex/phase2-skill-proficiency-foundation` directly from
  `3d8a83905a06b573ab41727f57c3673293ba48ac` with a clean worktree.
- The repository had no canonical Skill identity, `CharacterState` contained
  only total level and Saving Throw proficiency membership, and the current
  State writer emitted schema V2.

### Implemented

- Added the closed 18-value `Skill` Domain `StrEnum` as an identity-only Value
  Object without an associated Ability or rules logic.
- Extended mutable `CharacterState` with the explicit required
  `skill_proficiencies: frozenset[Skill]` effective membership field and strict
  Domain validation. Derived proficiency bonus remains unstored.
- Advanced the current State schema to V3 with required exact
  `skillProficiencies` Character JSON arrays, deterministic sorting, duplicate
  rejection, strict Skill decoding, and current V3-only writing.
- Preserved exact V1/V2 reads. V1 still maps to `characters=()`; V2 Character
  entries map to empty Skill membership and reserialize as V3 without changing
  the legacy V2 wire schema.
- Updated all explicit `CharacterState` construction sites and added Domain,
  serializer, StateStore, legacy-migration, and Saving Throw regression
  coverage.
- Updated canonical Architecture §§1.2.2/3.2.4/3.11/12.9/12.12–12.13,
  append-only DEC-0025, and factual current-contract summaries in `CLAUDE.md`.
  `README.md` and `docs/ROADMAP.md` remained unchanged.

### Verification

- Python 3.12.13 from the existing temporary external environment with pytest
  9.1.1 and mypy 1.20.2; no dependency changed. The repository `.venv`
  launcher remains stale and references a missing Python executable.
- Skill/CharacterState/StateSerializer/StateStore narrow suites: 122 passed.
- Broader State/persistence suites: 162 passed.
- Proficiency and Saving Throw Domain/Application/integration regressions:
  49 passed.
- Documentation-reference, Domain dependency, package, and JSON artifact
  checks: 9 passed.
- Full pytest suite: 522 passed. Pytest reported only a sandbox permission
  warning while attempting to write `.pytest_cache`; test execution passed.
- `python -m mypy src/dnd_engine`: no issues in 58 source files.
- `git diff --check` passed; Git emitted only Windows LF-to-CRLF checkout
  warnings for changed files. Formatter and linter remain not configured.

### Intentionally deferred

- `SkillCheckCommand`, payload/result/resolver/Event/Application handler,
  integration Skill Check flow, and monster Skill Checks.
- Fixed Skill-to-Ability mapping, Expertise, half proficiency, modifier
  storage, generic proficiency/check/modifier frameworks, and broader Skills
  or Proficiency Roadmap completion.
- State mutation/application, EventStore/runtime Event persistence, replay,
  transaction/UoW, buses, registries, frameworks, databases, and new
  dependencies.

## 2026-08-27 — Phase 2 Character Skill Check vertical slice

### Initial state

- Fetched `origin/main` and created
  `codex/phase2-character-skill-check` directly from
  `fd06755c27f0ce636ed637487ddbd22c3037a0fe` with a clean worktree.
- Verified the canonical 18-value `Skill`, V3 `CharacterState` Skill
  membership persistence, shared ability/proficiency/d20 rules, passing
  Character Saving Throw slice, and the §3.6 deferred-abstraction boundary.
- The repository `.venv` launcher referenced a missing Python executable, so
  verification used an external temporary Python 3.12.13 environment with the
  existing declared `.[dev]` dependencies; no project dependency changed.

### Implemented

- Added immutable `SkillCheckPayload` / `SkillCheckCommand` with explicit
  `skill`, `ability`, and `dc`; no fixed Skill-to-Ability mapping or generic
  Command hierarchy was introduced.
- Added character-specific `resolve_character_skill_check(...)` and immutable
  `SkillCheckResult`. The resolver composes matching Creature/Character
  projections, shared `ability_modifier`, conditional Skill membership,
  shared character proficiency progression, and shared d20 selection.
- Preserved alternative Ability semantics end-to-end: Strength (Intimidation)
  uses Strength for the modifier and Intimidation for proficiency membership.
- Added `SkillCheckResolvedPayloadV1` and the `SkillCheckResolved` V1 builder
  with explicit Skill/Ability, `D20Roll`, separate ability/proficiency audit
  contributions, and externally supplied Event metadata.
- Added explicit read-only `SkillCheckHandler`. Missing Creature returns
  `ENTITY_NOT_FOUND`; missing matching Character projection returns
  `INVALID_STATE` with `field="characters"`. Load, dice, and metadata failures
  retain the established propagation semantics.
- Added dedicated Command, resolver/result, Event, Application, and real-
  adapter integration tests, including projection immutability, lookup failure
  ordering, no-save behavior, V3 Skill membership loading, byte-for-byte State
  preservation, and seeded RNG reproducibility.
- Added canonical Architecture §3.14, append-only DEC-0026, and synchronized
  lifecycle, proficiency, d20, Event serialization, `CLAUDE.md`, and README
  factual summaries. `docs/ROADMAP.md` remained unchanged.

### Verification

- New Skill Check Domain/Application/integration tests: 67 passed.
- Expanded Skill, CharacterState/V3, Ability Check, Saving Throw, Application,
  integration, and architecture regression selection: 281 passed.
- Full pytest suite: 590 passed.
- `python -m mypy src/dnd_engine`: no issues in 62 source files.
- No formatter or linter is configured; neither was introduced.

### Intentionally deferred

- Expertise, half proficiency, monster Skill Checks, and default
  Skill-to-Ability association in adjudication/presentation.
- Generic check/resolver/result/payload/proficiency frameworks, buses,
  registries, dispatcher, EventStore, replay, and State mutation/application.
- Any post-third-consumer orchestration duplication review; this slice keeps
  the three concrete handlers explicit.
- Broad Skills and Proficiency Roadmap completion pending an explicit broader
  Definition of Done.

## 2026-08-27 — Third read-only d20 consumer duplication review

- Reviewed the concrete Ability Check, Character Saving Throw, and Character
  Skill Check resolver, handler, projection lookup, result, and Event patterns.
- Recorded the verdict `No production abstraction justified yet` in DEC-0027:
  the existing shared ability, proficiency-bonus, d20, dice, Event metadata,
  resolution-result, Event-envelope, and StateStore primitives are sufficient,
  while each mechanic remains concrete.
- Production code and tests were unchanged. Repeated test StateStore doubles,
  Dice doubles, metadata providers, and Campaign/Creature fixtures were noted
  as candidates for a separate low-risk test-only cleanup, not as evidence for
  a production abstraction or generic testing framework.
- The next production re-evaluation checkpoints are a concrete Attack Roll
  slice and the first real state-mutating action; Character projection and
  proficiency abstractions retain their separate evidence thresholds.
- `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `CLAUDE.md`, and `README.md`
  remained unchanged because the review confirms the existing §3.6 policy and
  changes no canonical contract or Roadmap completion status.

## 2026-08-27 — Armor Class design documented (documentation-only)

### Initial state

- Fetched `origin/main` and created `codex/docs-phase2-ac-design` directly
  from `3a40d1a5554d60fbcb70a4683f65b6fff6041e27` with a clean worktree.
- Ability Check, Character Saving Throw, and Character Skill Check were
  already implemented; DEC-0027 had left shared check/orchestration
  abstractions deferred pending a concrete Attack Roll slice.
- AC and Attack Rolls remained unchecked in the Roadmap. No Definition
  access port, typed Definition lookup, or Definition-loading boundary
  existed; the implemented Phase 1 `MonsterDefinition` (§3.1.1) had no
  `armor_class` field.

### Documented

- Added canonical Architecture §3.15 recording the approved but
  not-implemented Armor Class design: effective AC is a derived Domain rule
  result, never persisted on `CreatureState`/`CharacterState`, and no new
  `ArmorClassState`/`ACState` State Owner is introduced.
- Fixed the initial Character AC scope (`10 + Dexterity modifier`, sourced
  from `CreatureState.ability_scores.dexterity` via the existing
  `ability_modifier()` rule, no `CharacterState`/proficiency/`DiceEngine`,
  no State write-back) and the initial Monster AC scope (future
  `MonsterDefinition.armor_class` baseline dereferenced through
  `CreatureState.definition_id`, not derived from Dexterity).
- Recorded G4a as the explicit pipeline gate before the whole AC
  IMPLEMENTATION slice — both unarmored Character AC and baseline Monster
  AC — not only before the Monster AC branch, even though only Monster AC
  technically depends on typed Definition access (Definition access port,
  typed lookup, `MonsterDefinition.armor_class`, minimal real data, lazy
  referential validation, `DEFINITION_NOT_FOUND` for missing Definitions, a
  wrong-type failure policy deferred to G4a, packaged ruleset resources, and
  an installed-wheel test) without designing G4a's Python signature or
  implementation.
- Documented that AC calculation is a read-only Domain query, not a
  Command/Event use case, and that Attack will consume effective target AC
  without owning or persisting it, while explicitly excluding a generic
  Armor Class provider/strategy/formula abstraction per DEC-0027.
- Explicitly left the current implemented §3.1.1 `MonsterDefinition` schema
  unchanged in this slice, adding only a design-note pointer to the future
  G4a extension.
- Recorded that Creature ability ownership (§10.4) and Equipment
  armor/shield ownership (§10.6) are unchanged by this design, while
  explicitly leaving Conditions/Effects ownership and composition for
  future AC inputs undetermined by this slice, since §10.4 and §10.13
  already describe that area differently and this design must not harden
  either reading.
- Appended DEC-0028 recording the decision and its rationale.

### Changed files

- `docs/ARCHITECTURE.md` — new §3.15 Armor Class design, plus Quick lookup
  and table-of-contents entries.
- `docs/DECISIONS.md` — append-only DEC-0028.
- `docs/DEVELOPMENT_LOG.md` — this factual iteration entry.

### Explicitly not implemented

- `MonsterDefinition.armor_class` production field, any Definition access
  port, ruleset loader, ruleset data, or packaging change.
- Any AC Python rule, Attack Roll, `EquipmentState`, `ArmorDefinition`, or
  generic modifier framework.
- No `src/`, `tests/`, `rules/`, `campaigns/`, `pyproject.toml`, `CLAUDE.md`,
  `README.md`, or `docs/ROADMAP.md` change; the Roadmap AC and Attack rolls
  items remain unchecked. `CLAUDE.md` was reread against the new §3.15
  content and found to state nothing that contradicts it, so it was left
  unchanged.

### Verification

- Reviewed `CLAUDE.md` against the new §3.15 content for contradiction per
  the DEC-0018 resync obligation; found none, so `CLAUDE.md` was not edited.
- Repository-wide search for `armor_class` / `armorClass` found the new AC
  design/history (§3.15, DEC-0028, and this `docs/DEVELOPMENT_LOG.md` entry)
  and the pre-existing `tests/domain/test_creature_state.py` future-phase-field
  exclusion entry; no persisted `CreatureState`, `CharacterState`, or
  `StateSnapshot` field was introduced.
- Confirmed `ErrorCode.DEFINITION_NOT_FOUND` already exists in §3.9; no new
  error code was added.
- Confirmed `docs/ROADMAP.md` AC and Attack rolls items remain unchecked.
- The repository `.venv` (Python 3.12.9) was usable in this environment.
  The default OS temp directory (`%TEMP%\pytest-of-redbu`) was inaccessible
  to pytest with a `PermissionError`, so an external `--basetemp` was used
  for full-suite runs; the documentation-only narrow run did not hit this
  path.
- `python -m pytest tests/architecture/test_documentation_references.py`:
  2 passed.
- Full `python -m pytest --basetemp=<external tmp>`: 590 passed, matching
  the pre-existing count on `origin/main`.
- `mypy` was not yet installed in the repository `.venv`; it was installed
  by running `pip install -e ".[dev]"`, which installs exactly the
  dependencies already declared in `pyproject.toml` `[dev]` extras — no new
  dependency declaration was added or changed. `python -m mypy
  src/dnd_engine`: no issues in 62 source files.
- `git diff --check`: passed, no output.
- `git status --short` showed only `docs/ARCHITECTURE.md`,
  `docs/DECISIONS.md`, and `docs/DEVELOPMENT_LOG.md` modified.

## 2026-08-27 — Definition access foundation and packaged SRD 5.1 ruleset boundary (G4a)

### Initial state

- Fetched `origin/main` and created `claude/phase2-g4a-definition-loading`
  directly from `f820e79b0bc33a4139306d6799c1d7b7b524f3ae` with a clean
  worktree.
- DEC-0028/§3.15 had fixed G4a as the mandatory prerequisite gate before AC
  IMPLEMENTATION without designing it: no Definition access port existed,
  `MonsterDefinition` (§3.1.1) had no `armor_class`, `rules/dnd_5e/` was pure
  `.gitkeep` scaffold outside the installable `src/` tree, and
  `ruleset_version="5.2.1"` was used throughout the canon and test fixtures
  as the current `dnd_5e` example value without ever being tied to a
  specific SRD edition.

### Implemented

- Added Domain port `DefinitionSource` and semantic exceptions
  `DefinitionSourceError` / `DefinitionNotFoundError` /
  `DefinitionTypeMismatchError` in `src/dnd_engine/domain/services/definitions.py`,
  mirroring the existing `StateStore` port-in-Domain pattern: generic
  `get_definition(*, ruleset_id, ruleset_version, definition_id,
  expected_type) -> TDefinition`, taking only the two ruleset identity
  strings (never the full `CampaignState`), never returning `None`.
- Added `MonsterDefinition.armor_class: int` (§3.1.1), the only new field,
  with an intrinsic invariant rejecting `bool`/non-`int`; no other monster
  field and no numeric range beyond exact `int` was added.
- Added production Infrastructure adapter `PackagedDefinitionSource`
  (`src/dnd_engine/infrastructure/definitions/packaged.py`) reading packaged
  JSON via `importlib.resources`, with an optional `resources_root`
  constructor override for isolated tests. It strictly validates the
  untrusted JSON boundary (malformed JSON, non-object root, missing/unknown
  fields, wrong primitive types including `bool`-for-`int`, malformed
  `abilityScores`, unknown `type`, invalid Domain values, payload `id`
  mismatch), discriminates the actual concrete Definition kind from an
  explicit `type` field (`monster`/`item`/`weapon`) via a small deterministic
  dispatch (not a registry), and only then checks
  `isinstance(decoded, expected_type)`. All of the above raise a distinct
  Infrastructure `InvalidPackagedDefinitionError`, never silently collapsed
  into `DefinitionNotFoundError`.
- Moved ruleset Definition data into the installable package at
  `src/dnd_engine/resources/rulesets/<ruleset_id>/<ruleset_version>/definitions/<definition_id>.json`
  and added one production Definition, SRD 5.1 `goblin`
  (`id`, `version`, `name`, ability scores, `armorClass: 15`), with a
  `NOTICE.md` recording SRD 5.1 / CC-BY-4.0 attribution. Verified the
  packaged Ability Scores (STR 8, DEX 14, CON 10, INT 10, WIS 8, CHA 8) and
  Armor Class 15 against the official SRD 5.1 Goblin stat block before
  writing the file. Removed the obsolete top-level `rules/dnd_5e/` scaffold
  (`.gitkeep` placeholders only) so exactly one authoritative packaged
  dataset exists; no weapon or second-monster production dataset was added
  (G4b untouched).
- Added `[tool.setuptools.package-data]` to `pyproject.toml` for
  `dnd_engine.resources` so the built wheel actually contains the packaged
  JSON/`NOTICE.md`; no production dependency was added.
- Replaced the ambiguous `ruleset_version="5.2.1"` current-value usage with
  the canonical SRD 5.1 value `"5.1"` in `docs/ARCHITECTURE.md` (§§4.6–4.7,
  12.9) and in `tests/domain/test_campaign_state.py`,
  `tests/domain/test_state_snapshot.py`,
  `tests/infrastructure/test_state_serializer.py`, and
  `tests/infrastructure/test_state_store.py`. No `Ruleset` Value Object was
  introduced.
- Kept referential validation lazy: `StateStore`, `StateSerializer`, and
  `StateSnapshot` were not touched to call `DefinitionSource`, and a new
  regression test (`test_load_does_not_dereference_definition_id`) proves a
  snapshot with a nonexistent `definition_id` still loads and deserializes.
- Added `tests/packaging/test_installed_wheel_definitions.py`: builds a real
  wheel from an isolated copy of the source tree (so setuptools' `build/`
  staging directory never lands inside the repository checkout), installs it
  into a fresh venv (never `pip install -e`), and runs a child process
  outside the checkout with `PYTHONPATH` cleared, proving both the
  successful `goblin` lookup (`MonsterDefinition`, `armor_class == 15`,
  `ability_scores.dexterity == 14`) and `DefinitionNotFoundError` for a
  missing id resolve from the installed wheel alone, independent of the
  `src/`/`rules/` repository path.
- Added `tests/domain/test_definition_source.py` (port/error-hierarchy
  contract with a fake source) and
  `tests/infrastructure/test_packaged_definition_source.py` (production
  default lookup, ruleset/version scoping, missing vs. wrong-type vs.
  content-corruption distinctions, unknown type, missing/unknown fields,
  wrong primitive types including `bool`-for-`int`, malformed
  `abilityScores`, intrinsic Domain invariant violation, id mismatch,
  malformed/non-object JSON). Extended `tests/domain/test_monster_definition.py`
  with the new canonical field list and `armor_class` int/bool checks.
  Repointed `tests/test_json_artifacts.py` from the removed `rules/` tree to
  `src/dnd_engine/resources/rulesets/`.
- Updated `AGENTS.md`, `CLAUDE.md`, and `README.md` to stop naming
  `rules/dnd_5e/` as the canonical Definition location and to point at
  `src/dnd_engine/resources/rulesets/` instead; added a G4a summary bullet
  and two naming-trap rows to `CLAUDE.md` per the DEC-0018 resync
  obligation.
- Added canonical Architecture §3.16 (Definition Access vertical slice, G4a)
  and §12.26 (Packaged Ruleset Resources), updated §3.1.1
  (`MonsterDefinition.armor_class`), §3.15 (G4a prerequisite status,
  resolved wrong-type/missing policy, resolved packaging requirement), and
  §§4.6–4.7/12.9 (canonical `ruleset_version`), plus Quick lookup and
  table-of-contents entries. Appended DEC-0029.

### Changed files

- New: `src/dnd_engine/domain/services/definitions.py`,
  `src/dnd_engine/infrastructure/definitions/__init__.py`,
  `src/dnd_engine/infrastructure/definitions/packaged.py`,
  `src/dnd_engine/resources/__init__.py`,
  `src/dnd_engine/resources/rulesets/dnd_5e/5.1/definitions/goblin.json`,
  `src/dnd_engine/resources/rulesets/dnd_5e/5.1/NOTICE.md`,
  `tests/domain/test_definition_source.py`,
  `tests/infrastructure/test_packaged_definition_source.py`,
  `tests/packaging/test_installed_wheel_definitions.py`.
- Modified: `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `AGENTS.md`,
  `CLAUDE.md`, `README.md`, `pyproject.toml`,
  `src/dnd_engine/domain/definitions/monster.py`,
  `tests/domain/test_monster_definition.py`,
  `tests/domain/test_campaign_state.py`,
  `tests/domain/test_state_snapshot.py`,
  `tests/infrastructure/test_state_serializer.py`,
  `tests/infrastructure/test_state_store.py`, `tests/test_json_artifacts.py`.
- Removed: `rules/dnd_5e/` (twelve `.gitkeep` scaffold files, no real
  content).

### Explicitly not implemented

- `ArmorClassCommand`/`Result`/`Event`/`Handler`, `unarmored_armor_class`,
  `resolve_character_armor_class`, `monster_armor_class`, `AttackCommand`,
  any attack resolver, hit/miss comparison, weapon proficiency, damage, or
  HP mutation.
- A shared strict `NdM` parser, `WeaponDefinition.damage_dice` redesign, or a
  weapon production dataset (G4b).
- A generic exception → `EngineError` mapping function (no concrete
  Application consumer exists yet; the future mapping is fixed in canon
  only).
- `docs/ROADMAP.md` AC and Attack rolls items remain unchecked; no broad
  completion claim was invented since Roadmap has no explicit G4a line.

### Verification

- Python 3.12.9 (repository `.venv`). The default OS temp directory
  (`%TEMP%\pytest-of-redbu`) remained inaccessible with a `PermissionError`
  in this environment, so an external `--basetemp` was used for all pytest
  runs.
- `python -m pytest tests/domain/test_monster_definition.py tests/domain/test_definition_source.py tests/domain/test_campaign_state.py tests/domain/test_state_snapshot.py tests/domain/test_creature_state.py`:
  55 passed.
- `python -m pytest tests/infrastructure/ tests/test_json_artifacts.py`:
  174 passed.
- `python -m pytest tests/architecture/`: 7 passed.
- `python -m pytest tests/packaging/` (installed-wheel proof, run
  separately): 2 passed in ~13-14s; confirmed via manual wheel build that
  the wheel contains `dnd_engine/resources/rulesets/dnd_5e/5.1/NOTICE.md`
  and `.../definitions/goblin.json`.
- Full `python -m pytest --basetemp=<external tmp>`: 622 passed (620
  pre-existing-shape tests plus the 2 installed-wheel tests), no regressions.
- `python -m mypy src/dnd_engine`: no issues in 66 source files.
- `git diff --check`: reports 6 "trailing whitespace" warnings on new
  `pyproject.toml` lines. Confirmed these are not added spaces: the file's
  git blob already stores literal CRLF line endings before this change
  (pre-existing unchanged context lines show the same `^M` in `git diff`),
  and the new lines match that pre-existing per-file convention exactly. Not
  changed, to avoid introducing a mixed-line-ending diff into an unrelated
  pre-existing file convention.
- `git status --short` / `git diff --stat` / `git diff` were reviewed for
  unrelated changes; none found. No `dist/`, `build/`, `*.egg-info/`,
  temporary venvs, wheel files, or cache files were left tracked or in the
  diff (the packaging test builds from an isolated copy of the source tree
  specifically to avoid this).
- No commit, push, or pull request was performed.

## 2026-08-27 — G4a review fixes: licensing, path traversal, broken root, offline build, git diff --check

### Initial state

- Continued on the existing `claude/phase2-g4a-definition-loading` branch
  (no new branch); re-fetched `origin/main` and confirmed it still matched
  the recorded baseline `f820e79b0bc33a4139306d6799c1d7b7b524f3ae`, so no
  rebase was required.
- Review findings on the G4a slice above: the packaged `NOTICE.md` claimed
  OGL 1.0a without including the OGL text; `PackagedDefinitionSource`
  passed `ruleset_id`/`ruleset_version`/`definition_id` into
  `Traversable.joinpath(...)` without validating they were a single
  resource path segment; a missing/broken top-level packaged `rulesets/`
  root was indistinguishable from an ordinary missing Definition; the
  installed-wheel test always built through pip's isolated build
  environment; and `git diff --check` failed on new `pyproject.toml` lines.

### Fixed

- **Licensing:** rewrote `src/dnd_engine/resources/rulesets/dnd_5e/5.1/NOTICE.md`
  to use the official SRD 5.1 Creative Commons release instead of OGL:
  the verbatim required Wizards attribution statement and the CC-BY-4.0
  license/URL from the SRD 5.1 CC legal-information preamble, a short note
  that the packaged JSON is a transformed/abbreviated extract (no prose
  copied), and no attribution beyond what the preamble requires. Updated
  the "OGL 1.0a" mentions in DEC-0029 and the prior G4a
  `docs/DEVELOPMENT_LOG.md` entry to "CC-BY-4.0"; did not touch any other
  historical entry.
- **Path traversal:** added `_require_resource_segment()` in
  `src/dnd_engine/infrastructure/definitions/packaged.py`, run before any
  dynamic value reaches `Traversable.joinpath(...)`. `ruleset_id` and
  `definition_id` must match the existing canonical lowercase snake_case
  ID contract (§4.1/§4.6); `ruleset_version` must be one path segment with
  no `/`, `\`, or `.`/`..` path semantics. A value that fails this check
  raises the existing `DefinitionNotFoundError` — no new exception type —
  since it cannot resolve to any packaged Definition. Synced this extended
  semantics into §3.16 and §12.26, and added one sentence to DEC-0029.
- **Broken resource root:** `_read_payload()` now checks the top-level
  `<resources_root>/rulesets/` directory's existence/type before anything
  else; if missing or not a directory, it raises
  `InvalidPackagedDefinitionError` (packaging/infrastructure failure), kept
  distinct from an ordinary missing/unsupported `ruleset_id`/`ruleset_version`
  scope below that root (e.g. `dnd_5e/9.9/goblin`), which remains
  `DefinitionNotFoundError` as before. No manifest or supported-ruleset
  registry was added. Documented in §12.26.
- **Offline-friendlier wheel build:** `tests/packaging/test_installed_wheel_definitions.py`
  now checks whether the interpreter running the test already satisfies
  the declared `setuptools>=68` build requirement
  (`_build_environment_has_declared_setuptools()`) and, if so, adds
  `--no-build-isolation` to the `pip wheel` invocation, skipping pip's
  network-dependent isolated build environment; otherwise it falls back to
  the previous (isolated) build. `--no-deps`, the fresh venv, `pip install
  --no-index`, the outside-checkout child process, and the cleared
  `PYTHONPATH` are all unchanged; no editable install is used.
- **`git diff --check`:** investigated with `git ls-files --eol`, `git
  check-attr`, `core.autocrlf`, and `core.whitespace` per the review
  instructions. Every other tracked file in the repository has an
  LF-committed blob (`i/lf`) with a CRLF working-tree copy from
  `core.autocrlf=true` (`w/crlf`); `pyproject.toml` alone had a
  CRLF-committed blob (`i/crlf`), which is why `git diff --check` flagged
  only its new lines as "trailing whitespace" (the default
  `core.whitespace` treats a bare `\r` before `\n` as trailing whitespace).
  This is a pre-existing single-file anomaly, not a repository-wide
  convention, so the minimal repository-consistent fix was to normalize
  only `pyproject.toml` (a file already substantively changed in this
  slice) to LF, matching every other tracked file. No `.gitattributes` was
  added and `core.whitespace`/`core.autocrlf` were not changed (git config
  is never modified). This necessarily shows the whole 33-line file as
  changed in `git diff`, since its line endings changed throughout; no
  other file's line endings were touched.

### Changed files (relative to the prior G4a slice)

- Modified: `src/dnd_engine/resources/rulesets/dnd_5e/5.1/NOTICE.md`,
  `src/dnd_engine/infrastructure/definitions/packaged.py`,
  `tests/infrastructure/test_packaged_definition_source.py`,
  `tests/packaging/test_installed_wheel_definitions.py`,
  `docs/ARCHITECTURE.md` (§3.16, §12.26), `docs/DECISIONS.md` (DEC-0029
  amended in place, not superseded), `docs/DEVELOPMENT_LOG.md` (prior G4a
  entry's OGL mention corrected; this entry appended), `pyproject.toml`
  (line-ending normalization only; no content change beyond the prior
  slice's `package-data` addition).
- No files added or removed beyond the prior G4a slice.

### Explicitly not implemented

- No AC, Attack, G4b `NdM` parser, damage, HP, or equipment work.
- No `DefinitionRegistry`, cache, plugin system, DI container, or database.
- No new production dependency; `setuptools`/`wheel` used only as
  already-declared build-system/dev tooling, not added to
  `[project.dependencies]` or `[project.optional-dependencies]`.
- No `Ruleset` Value Object, generic path sanitizer, or ID framework — the
  traversal guard is two small regexes local to
  `infrastructure/definitions/packaged.py`.

### Verification

- Python 3.12.9 (repository `.venv`); external `--basetemp` used again for
  the same pre-existing default-temp-dir `PermissionError` reason.
- `python -m pytest tests/infrastructure/test_packaged_definition_source.py`:
  45 passed (includes new traversal, broken-root, and adversarial-fixture
  tests).
- `python -m pytest tests/architecture/`: 7 passed.
- `python -m pytest tests/packaging/`: 2 passed (~9-10s with
  `--no-build-isolation` active locally after installing `setuptools` into
  the dev `.venv` for verification; falls back to the previous isolated,
  network-dependent build when `setuptools` is absent).
- Full `python -m pytest --basetemp=<external tmp>`: 646 passed (up from
  622; the increase is the new traversal/broken-root/adversarial-fixture
  tests), no regressions.
- `python -m mypy src/dnd_engine`: no issues in 66 source files.
- `git diff --check`: exit code 0, empty stdout; stderr contains only the
  informational `warning: in the working copy of 'pyproject.toml', LF will
  be replaced by CRLF the next time Git touches it` (a normal
  `core.autocrlf` advisory, not a `--check` diagnostic).
- Rebuilt the wheel manually and confirmed it still contains
  `dnd_engine/resources/rulesets/dnd_5e/5.1/definitions/goblin.json` and
  the corrected `NOTICE.md`; re-ran the installed-wheel test to confirm the
  `goblin` lookup and `DefinitionNotFoundError` still resolve from the
  installed copy.
- `git status --short` / `git diff --stat` / `git diff` were reviewed;
  changes are limited to the files listed above (`pyproject.toml`'s diff is
  larger than its content change because of the line-ending normalization,
  as explained above). No `dist/`, `build/`, `*.egg-info/`, temporary
  venvs, wheel files, or cache files were left tracked or in the diff.
- No commit, push, or pull request was performed.

## 2026-08-27 — Minimal Armor Class implementation

### Implemented

- Added the pure Domain rule
  `unarmored_character_armor_class(creature: CreatureState) -> int` in
  `domain/rules/armor_class.py`. It reads
  `creature.ability_scores.dexterity`, delegates modifier calculation to the
  shared `ability_modifier()`, and returns `10 + modifier` without mutation,
  Definition access, RNG, persistence, Commands, Events, or
  `CharacterState`.
- Baseline Monster AC uses the existing G4a production path: Campaign
  ruleset identity plus `CreatureState.definition_id` are passed to typed
  `DefinitionSource.get_definition(..., expected_type=MonsterDefinition)`,
  after which the consumer reads `MonsterDefinition.armor_class` directly.
  A pass-through `baseline_monster_armor_class()` abstraction was
  intentionally not introduced because the immutable Definition field is
  already the authoritative fact and no separate calculation policy exists.
- Added focused Domain tests for neutral, positive, negative, and odd
  Dexterity modifier semantics, the absence of a `CharacterState`
  requirement, the exact `int` result, and source `CreatureState`
  non-mutation.
- Added an integration/regression proof using the packaged SRD 5.1 Goblin
  through production `PackagedDefinitionSource`. Its runtime Creature
  Dexterity intentionally differs from Definition data; the test proves
  baseline Monster AC equals `MonsterDefinition.armor_class` and differs
  from `10 + ability_modifier(creature.ability_scores.dexterity)`.
- Updated `docs/ARCHITECTURE.md` §3.15 from approved/not implemented to the
  implemented minimal Character/Monster boundary, preserved derived/not
  persisted semantics and deferred Equipment/runtime modifiers/Attack, and
  documented the deliberate absence of a Monster pass-through rule.
- Marked the Roadmap AC item complete because canonical §3.15 defines the
  minimal AC slice as exactly unarmored Character AC plus baseline Monster
  AC and both are now implemented and tested. Updated the reproduced AC/G4a
  status in `CLAUDE.md`. No new DEC was needed because DEC-0028/DEC-0029
  already cover the implemented boundary.

### Verification

- Python 3.12.13 in an isolated temporary environment using the existing
  `.[dev]` dependencies. The repository `.venv` was not modified; its
  launcher currently points to a missing Python 3.12.9 installation.
- Focused Character AC Domain tests: 6 passed.
- Focused Monster AC integration/regression test: 1 passed.
- Relevant Domain/G4a regressions: 69 passed.
- Packaged Definition, serialization/store lazy-validation, and Monster AC
  integration regressions: 142 passed.
- Architecture/documentation invariants: 7 passed.
- Installed-wheel packaged Definition tests: 2 passed. The first attempt was
  blocked by sandbox denial on the global pip wheel cache; the unchanged test
  passed after directing `PIP_CACHE_DIR` to a writable temporary directory.
- Full suite: 653 passed.
- `python -m mypy src/dnd_engine`: no issues in 67 source files (cache was
  directed to a writable temporary directory).

### Explicitly not implemented

- No Monster AC function/resolver/provider, generic modifier framework,
  State AC field, eager Definition dereference, Equipment, runtime AC
  modifier, G4b, Attack, HP, damage, or other deferred mechanic.
- No production dependency, packaged resource, Definition schema, State
  schema, persistence, Command, Event, or error-taxonomy change.

## 2026-08-27 — Weapon damage dice foundation (G4b)

### Implemented

- Added a shared pure Domain primitive `parse_ndm(expression: str) ->
  tuple[int, int]` in `src/dnd_engine/domain/dice.py`. It accepts only
  exact `str`, enforces strict lowercase grammar `[1-9][0-9]*d[1-9][0-9]*`,
  and rejects `sides < 2`, preserving the exact prior error types/messages
  (`TypeError("expression must be a str")`,
  `ValueError("invalid dice expression")`,
  `ValueError("dice must have at least two sides")`). It imports nothing
  beyond stdlib `re`.
- Migrated `PythonDiceEngine.roll()` (`infrastructure/random/dice.py`) to
  call `parse_ndm(expression)` instead of its own private regex/parser
  method, which was removed rather than duplicated. RNG call count, call
  order, and `DiceRoll.total` computation are unchanged.
- Added `WeaponDefinition.__post_init__` (`domain/definitions/weapon.py`)
  calling the same `parse_ndm(self.damage_dice)` as an intrinsic Domain
  invariant. `damage_dice` remains a plain `str` field; no `(count, sides)`
  representation is stored and no field was added.
- Added the first production weapon Definition,
  `src/dnd_engine/resources/rulesets/dnd_5e/5.1/definitions/dagger.json`
  (SRD 5.1: `1d4` piercing; properties `finesse`, `light`, `thrown`; no
  range/cost/weight, which the current `WeaponDefinition` contract does not
  model). Decoded by the existing, unmodified `_decode_weapon()` dispatch in
  `PackagedDefinitionSource` (G4a). Updated
  `rulesets/dnd_5e/5.1/NOTICE.md` to record the `dagger` field provenance
  alongside the existing `goblin` entry.
- `pyproject.toml`'s existing `rulesets/dnd_5e/5.1/definitions/*.json`
  package-data wildcard already covers `dagger.json`; no change was made.
- Recorded DEC-0030, narrowing DEC-0011's "parsing remains private to the
  Infrastructure implementation" clause now that `WeaponDefinition` is a
  second, non-RNG consumer of the same grammar; DEC-0011's `DiceEngine`/
  `DiceRoll`/RNG-injection contract is otherwise unaffected. Updated
  `docs/ARCHITECTURE.md` §1.7.1 (parser ownership), §3.1.1
  (`WeaponDefinition.damage_dice` intrinsic invariant), and §12.26 (packaged
  dataset now lists `dagger.json`; installed-wheel proof description
  extended). Updated `CLAUDE.md`'s "Случайность" and "Реализованные
  контракты Phase 2" sections to match.

### Tests added

- `tests/domain/test_dice_parser.py` (new): exhaustive valid/invalid-syntax/
  invalid-type matrix for `parse_ndm`, including leading zeros, uppercase
  `D`, whitespace, modifier/keep-drop/exploding notation, and non-ASCII
  digit variants (Arabic-indic, fullwidth) that the literal `[0-9]` grammar
  does not accept.
- `tests/domain/test_weapon_definition.py`: added valid `1d8` acceptance,
  malformed-syntax/leading-zero/whitespace/modifier/uppercase rejection,
  `1d1` rejection, non-`str`/`str`-subclass rejection, all via direct
  `WeaponDefinition(...)` construction (no packaged loader involved).
- `tests/infrastructure/test_dice_engine.py`: left unmodified as the
  regression proof that the migration did not change accepted/rejected
  expressions, exact-`str` requirement, seeded-sequence equality, or
  injected/global RNG state.
- `tests/infrastructure/test_packaged_definition_source.py`: added a direct
  `WeaponDefinition`-typed decode of a packaged `dagger`-shaped fixture, a
  malformed `"damageDice": "1D4"` string case and a malformed `damageDice:
  4` primitive case (both asserting `InvalidPackagedDefinitionError`), a
  production `dagger` lookup via `PackagedDefinitionSource()` asserting
  exact fields, and `dagger` requested as `MonsterDefinition` asserting
  `DefinitionTypeMismatchError`.
- `tests/packaging/test_installed_wheel_definitions.py`: extended the
  existing success child script to also resolve `dagger` as
  `WeaponDefinition` from the installed wheel and assert its id, name,
  `damage_dice`, `DamageType.PIERCING`, and properties tuple, proving
  `dagger.json` ships inside the wheel rather than only the checkout.

### Explicitly not implemented

- No Attack rolls, damage resolution, HP, hit/miss resolution, attack
  modifiers, weapon attack bonus, range/ammunition mechanics, versatile
  damage switching, two-handed behavior, equipment/wielding, or generic
  modifier pipeline.
- No `DiceExpression` Value Object, dice AST, or full dice DSL; no
  `DefinitionRegistry`, decoder registry/plugin system, service locator, or
  DI container; no generic Definition serialization framework.
- No new `WeaponDefinition` field, no second production weapon, no new
  packaged data location, no new Infrastructure exception type, and no
  change to the existing `DefinitionNotFoundError` /
  `DefinitionTypeMismatchError` / `InvalidPackagedDefinitionError` taxonomy.
- No production dependency added; `pyproject.toml` was not modified.
- `docs/ROADMAP.md`'s Attack rolls checkbox remains unchecked; this slice is
  not a Roadmap mechanic completion.

### Verification

- Python 3.12.9 (repository `.venv`), pytest 9.1.1, mypy (version declared
  in `pyproject.toml`'s `dev` extra).
- `tests/domain/test_dice_parser.py`: 30 passed.
- `tests/domain/test_weapon_definition.py`: 24 passed.
- `tests/infrastructure/test_dice_engine.py`: 30 passed (unmodified,
  regression-only).
- `tests/infrastructure/test_packaged_definition_source.py`: 50 passed
  (`--basetemp` pointed at a writable directory outside the default OS temp
  root, which this sandbox denies).
- `tests/packaging/test_installed_wheel_definitions.py`: 2 passed
  (`PIP_CACHE_DIR` and `--basetemp` pointed at writable directories for the
  same pre-existing sandbox reason as prior iterations).
- Full `python -m pytest` (`--basetemp` as above): 705 passed.
- `python -m mypy src/dnd_engine`: no issues in 68 source files.
- `git diff --check`: reviewed as part of final diff review.
- No commit, push, or pull request was performed.

## 2026-08-27 — Initial React frontend and LoginPage foundation

### Implemented

- Added an isolated `frontend/` application using React 19, TypeScript strict
  mode, Vite, CSS Modules, Vitest, React Testing Library, and ESLint.
- Added the responsive `LoginPage` with semantic username/password controls,
  custom client-side required-field validation, accessible errors/status,
  and a keyboard-operable CSS wax-seal-inspired submit button.
- Kept login presentation-only: valid submission preserves form values in
  component state and reports that backend authentication is not connected.
  No endpoint, credentials, success state, or D&D rule logic was introduced.
- Added global fantasy design tokens and an original generated medieval room
  background with gradient/color fallback and a readability overlay.
- Added frontend setup/check instructions and ignored frontend dependency,
  build, and coverage output at repository level.
- Kept TypeScript on the compatible `>=6.0.0 <6.1.0` range because the
  installed `typescript-eslint` 8.x peer contract does not yet support
  TypeScript 7.

### Tests added

- Added seven behavior-focused LoginPage tests covering the page, both
  inputs, submit button, empty validation, presentation-only submission, and
  the absence of fabricated successful authentication.

### Explicitly not implemented

- No backend or authentication API integration, routing, campaign selection,
  game UI, shared state manager, or frontend D&D mechanics.
- Phase 7 remains open in `docs/ROADMAP.md`; canonical backend contracts and
  Python Domain/Application code were not changed.

### Verification

- Node.js 24.19.0 and npm 11.17.0.
- `npm run lint`: passed.
- `npm run test`: 1 test file and 7 tests passed.
- `npm run build`: Vite 8.2.2 production build passed.
- In-app browser QA at 1920x1080, 1366x768, 768x1024, and 375x812: no
  horizontal overflow, the panel remained inside the viewport, empty
  validation and presentation-only valid submission rendered correctly,
  and no console errors/warnings were reported.
- Python/pytest regression checks were not run because neither `python`,
  `py`, nor a repository `.venv` Python executable is available in this
  environment; no Python source or packaging configuration was changed.

## 2026-08-27 — Initial frontend review fixes

### Changed

- Replaced the LoginPage root `overflow: hidden` with horizontal clipping and
  vertical auto-scrolling so short landscape viewports and browser zoom do
  not make lower form content unreachable.
- Converted `login-background.png` to quality-84 WebP at the original
  1672x941 resolution and updated the CSS asset reference. The asset decreased
  from 2,097,886 bytes to 157,220 bytes (approximately 92.5%) while retaining
  the intended visual quality.
- Added a separate `frontend` job to the existing GitHub Actions workflow.
  It uses `actions/setup-node@v7`, Node.js 24.15.0, npm caching keyed by the
  frontend lockfile, and runs `npm ci`, lint, tests, and the production build
  from `frontend/`. Existing Python pytest and mypy jobs were not changed.
- Declared the supported Node.js line as `^24.15.0` in `package.json`, synced
  it into `package-lock.json`, and documented the same baseline in the
  frontend README. This satisfies the installed Vite 8 engine and the stricter
  current jsdom development-dependency engine.

### Explicitly not implemented

- No routing, Authentication API integration, API service, global state
  management, additional screen, or Python backend change.

### Verification

- `npm ci`: completed successfully; 237 packages audited, zero vulnerabilities.
- `npm run lint`: passed.
- `npm run test`: 1 test file and 7 tests passed.
- `npm run build`: Vite 8.2.2 production build passed.
- In-app browser QA at 812x500 landscape and an effective 683x384 zoomed
  viewport confirmed `overflow-x: hidden`, `overflow-y: auto`, working
  vertical scrolling to the panel bottom, no horizontal overflow, the WebP
  background request, and no console errors/warnings.
- `git diff --check`: passed for the complete frontend diff.
