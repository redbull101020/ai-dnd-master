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

## 2026-08-28 — State Mutation Foundation (G5) canonical contract (DEC-0032)

### Initial state

- Fetched `origin/main` and found the local `main` checkout stale by 35
  commits (18 merged PRs, up to PR #53 `codex/docs-attack-roll-unarmed-monster`
  at `1dcf6d7c43654703ef7ba5bf424c3cba9e942d1a`); local `main` was a clean
  ancestor of `origin/main` with no unique commits, so it was fast-forwarded
  before any other precondition check. Created
  `claude/docs-state-mutation-foundation` directly from the fast-forwarded
  `origin/main`.
- After the fast-forward, all task preconditions matched: latest accepted
  decision was DEC-0031, `docs/ARCHITECTURE.md` §3 ended at §3.17, §3.8
  Atomicity was still `Planned / Deferred` pending "a separate State Mutation
  Foundation decision," no production gameplay handler called
  `StateStore.save()`, `StateStore` remained `load()`/`save()`-only,
  `StateSnapshot` stayed a frozen container of mutable `CreatureState`/
  `CharacterState` objects, and `ResolutionResult` had no `state_changes`
  field.

### Canonical contract changes

- Added `docs/ARCHITECTURE.md` §3.18 State Mutation Foundation (G5): the
  mutating-command lifecycle (`load snapshot → validate → resolve rules →
  outcome → Event batch → apply to isolated replacement projection →
  replacement StateSnapshot → StateStore.save → successful ResolutionResult`)
  with read-only Commands' current no-op semantics preserved; loaded State as
  read-only input with replacement/copy-on-write mutation (`deepcopy()`,
  `WorkingState`, and frozen State dataclasses explicitly rejected);
  transition-specific mutation scope, fixing the future Damage → HP scope to
  `CreatureState.current_hp` only, preserving `id`/`definition_id`/
  `ability_scores`/`max_hp` without declaring them globally immutable; the
  Event → State application contract (no dice, Definitions, AI, persistence
  I/O, clock, ID allocation, new Events, or re-decided gameplay per
  application step) with no production `EventApplierRegistry`/generic
  reducer/dispatcher; a three-way resolver/Application/State-application
  separation (the resolver determines the outcome only and never receives
  `EventMetadataProvider`; Application constructs the Event batch from that
  outcome plus `EventMetadataProvider` metadata, matching the existing §2.2
  handler pattern; State application projects an already-resolved Event);
  persistence ordering forbidding "return success, save later" and using
  "successfully persisted through `StateStore.save()`" rather than "durably
  saved" language; save-failure semantics with no rollback/ID reuse; the
  snapshot-authoritative MVP statement bounded by `FilesystemStateStore`'s
  existing non-durability caveat (§12.9); EventStore and serialized Event
  type/version dispatch staying deferred; `state_changes` staying absent; an
  explicit no-generic-transaction-framework list (`UnitOfWork`,
  `TransactionManager`, `WorkingState`, `MutationContext`, `StateChange`,
  `EventApplierRegistry`, generic reducer, generic State Owner repository,
  generic transaction coordinator); and the exact MVP atomicity
  guarantee/non-guarantee boundary.
- Updated §3.8 Atomicity to point at §3.18 instead of an unnamed future
  decision, without changing its `Planned / Deferred` implementation status.
- Added the §3.18 row to the Quick lookup table and the Table of contents.
- Appended `docs/DECISIONS.md` DEC-0032 recording the same decision.
- In `docs/ROADMAP.md`, inserted `[x] State Mutation Foundation (G5)` between
  `[ ] Attack rolls` and `[ ] HP`, added a §3.18 link to the Phase 2 contracts
  line, and added a clarifying note that G5 is documentation-only and sits
  between the existing minimal Attack slice and the first HP/Damage
  state-mutating slice. `Attack rolls`, `HP`, and `Damage` stay unchecked.
- In `CLAUDE.md`, added a current-phase bullet for G5, replaced the blanket
  "Event application to State is deferred" statement with the accurate
  canonical-contract-exists-but-unimplemented statement, added the §3.18
  deferred-abstractions block, and added two naming-trap rows
  (`deepcopy()` and `state_changes`/UoW as a stand-in for concrete State
  Owner-specific Event application).

### Changed files

- `docs/ARCHITECTURE.md` — new §3.18, §3.8 cross-reference update, Quick
  lookup and Table of contents entries.
- `docs/DECISIONS.md` — append-only DEC-0032.
- `docs/ROADMAP.md` — Phase 2 checklist and contracts-line update.
- `CLAUDE.md` — current-phase, deferred-abstractions, and naming-traps sync.
- `docs/DEVELOPMENT_LOG.md` — this factual iteration entry.

### Not implemented

- No production Python, test, rule, or campaign file was changed.
- No `EventApplierRegistry`, `UnitOfWork`, `TransactionManager`,
  `WorkingState`, `MutationContext`, `StateChange`, generic reducer, or
  generic transaction coordinator was added as production code.
- No `Damage`, `HP` mutation, `Healing`, `EventStore`, Event persistence, or
  replay was implemented.
- `StateStore`'s `load()`/`save()` signature, `StateSnapshot`'s schema, and
  `ResolutionResult`'s fields are unchanged.
- `README.md` was read for contradictions against the new §3.18 contract;
  none was found, so it was left unchanged.

### Verification

- The repository's own `.venv` (Python 3.12.9, pytest 9.1.1) was functional
  and used directly; `--basetemp` was pointed outside the default OS temp
  directory, whose `pytest-of-redbu` folder was not writable in this
  environment.
- Narrow `tests/architecture` suite, including the documentation-link and
  `§N.N` cross-reference validator that now covers the new §3.18 anchor: 7
  passed.
- Full pytest suite: 805 passed. No production or test file was changed.
- `git diff --check` passed.
- `git status --short` showed only the tracked documentation files listed
  above as modified.
- No formatter, linter, or type checker is configured in the repository.
- Diff written to `review.patch` in the repository root for review; not
  committed.

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

## 2026-08-28 — Character unarmed Attack Roll → Monster canon and post-Attack review

### Branch, base, and prerequisites

- Documentation work was performed on
  `codex/docs-attack-roll-unarmed-monster`, created from fetched
  `origin/main` at `1f1a532`. The initial checkout was clean. Reviewed Attack
  implementation was already present in repository history: Domain resolution
  in `d8af001`, Application/integration in `7e8b931`, and both merged into
  `origin/main`; no Attack source or test file was edited in this group.
- Confirmed the implemented prerequisites: shared Ability/Proficiency/d20
  rules, G4a typed `DefinitionSource`, Campaign ruleset identity, immutable
  `MonsterDefinition.armor_class`, packaged SRD 5.1 Goblin data, minimal AC,
  and G4b weapon damage-dice invariant.

### Reviewed implementation and canonical documentation

- Confirmed target-only immutable `AttackCommand`/`AttackPayload`, immutable
  `AttackResult`, and concrete `resolve_character_unarmed_attack()`. The
  resolver uses Strength, `ability_modifier()`, derived
  `character_proficiency_bonus(CharacterState.total_level)`, and the shared
  `resolve_d20_roll()` primitive; the production handler defaults to NORMAL.
- Confirmed Attack-owned natural semantics over `D20Roll.selected`: natural 1
  is an automatic miss, natural 20 is an automatic hit with
  `critical_hit=true`, and other rolls compare total to target AC.
- Confirmed `AttackHandler` loads matching actor `CreatureState` and
  `CharacterState`, then target `CreatureState`; it dereferences
  `target.definition_id` under Campaign `ruleset_id`/`ruleset_version` through
  `DefinitionSource(expected_type=MonsterDefinition)` and reads
  `MonsterDefinition.armor_class`. The real-adapter integration test exercises
  `FilesystemStateStore`, `PackagedDefinitionSource`, seeded
  `PythonDiceEngine`, and a test-only fixed `EventMetadataProvider` together.
- Confirmed one `AttackResolved` V1 Event for hit, miss, or critical outcome;
  it records the actual target AC used as an audit fact. No separate
  `AttackHit`, `AttackMissed`, or `CriticalHit` Event exists.
- Confirmed the read-only boundary: no State mutation, no `StateStore.save()`,
  no Event application/persistence, no damage resolution, and no HP mutation.
- Added canonical §3.17, updated Architecture navigation and stale illustrative
  Attack examples, appended DEC-0031, and synchronized the reproduced current
  state in `CLAUDE.md` and `README.md`.
- Completed the DEC-0027 post-Attack abstraction checkpoint with verdict
  **KEEP CONCRETE**. Rejected a generic d20/check resolver, Character
  projection wrapper, actor/target lookup helper, generic Definition-exception
  mapper, handler success-tail helper, proficiency abstraction, and
  `ModifierPipeline`; consumer count remains a review trigger, not an
  abstraction rule.
- `docs/ROADMAP.md` was intentionally not modified. `[ ] Attack rolls`
  remains unchecked because only Character unarmed → Monster is implemented,
  not the broad weapon/Monster/spell/targeting Attack Roll mechanic.

### Verification before documentation

- Python 3.12.13 in an isolated temporary environment using the repository's
  existing `.[dev]` dependencies; the repository `.venv` launcher pointed to
  a missing Python installation and was not modified.
- All Attack narrow tests (Domain Command/resolver/Event, Application handler,
  and real-adapter integration): 100 passed.
- `tests/architecture`: 7 passed.
- First full-suite attempt: 803 passed and 2 packaging setup errors because
  the sandbox denied the global pip wheel cache (`WinError 5`), not because of
  source/test behavior. Re-run with `PIP_CACHE_DIR` and `--basetemp` in a
  writable temporary directory: 805 passed.
- `python -m mypy src/dnd_engine`: no issues in 72 source files.

### Verification after documentation

- Documentation-reference/architecture tests (`tests/architecture`): 7
  passed, including 2 documentation-reference tests and 5 Domain dependency
  tests.
- All Attack narrow tests (Domain Command/resolver/Event, Application handler,
  and real-adapter integration): 100 passed.
- Full `python -m pytest` with writable `PIP_CACHE_DIR`/`--basetemp`: 805
  passed.
- `python -m mypy src/dnd_engine`: no issues in 72 source files.
- Repository searches found no `StateStore.save()` call, HP/current_hp
  mutation, damage implementation, weapon/equipment/inventory/range fields, or
  forbidden Application/API/Infrastructure import in the Attack Domain and
  handler files. `AttackPayload` contains only `target_id`.
- `docs/ROADMAP.md` remains unchanged with `[ ] Attack rolls`.
- `git diff --check`: exit code 0; only normal `core.autocrlf` LF→CRLF
  working-copy advisories were emitted.

### Explicitly deferred

- Damage, critical damage, HP/current_hp mutation, dagger/weapon attacks,
  equipment/inventory, weapon proficiency, Finesse, range/reach/ammunition,
  Character targets, Monster attacks, spell attacks, and broader
  targeting/visibility/cover.
- Event persistence/application, State mutation orchestration, a combat
  system, and all rejected generic production abstractions.

## 2026-08-28 — State Mutation Foundation (G5) acceptance obligations for the first Damage → HP consumer

### Initial state

- Continued on `claude/docs-state-mutation-foundation`, on top of the already
  committed G5 canonical contract (`docs/ARCHITECTURE.md` §3.18, DEC-0032).
  `§3.18` fixed the mutating-command lifecycle, read-only loaded-snapshot
  input, transition-specific mutation scope, Event → State contract,
  persistence ordering, save-failure semantics, and the exact MVP atomicity
  boundary, but did not yet state what a first concrete Damage → HP slice
  must actually prove to be accepted as evidence for that contract.

### Documentation changes

- Added a new `docs/ARCHITECTURE.md` §3.18 subsection, "Acceptance
  obligations for the first Damage → HP consumer," fixing three groups of
  executable obligations for that future slice: (A) Domain/concrete State
  transition — determinism, no `DiceEngine`/`DefinitionSource`/persistence
  I/O/new-Event/re-decided-rule during State application, only `current_hp`
  changes while `id`/`definition_id`/`ability_scores`/`max_hp` are preserved,
  and the resulting `CreatureState` still satisfies its existing invariants
  (§3.2.1); (B) Application orchestration — no mutation of the loaded object
  graph, a complete Event before State application, replacement (not
  in-place) `CreatureState`/`StateSnapshot`, unrelated projections left
  semantically unchanged, exactly one `StateStore.save()` call on the
  successful path with the replacement snapshot, no `save()` on a
  pre-Event/Event-application failure, save failures propagating per existing
  `StateStoreError` boundary semantics (§12.9) without a successful
  `ResolutionResult`, and a successful `ResolutionResult` only observable
  after a successful save; (C) regression/architecture boundary — existing
  read-only handlers still never call `save()`, no `state_changes` field, no
  `EventStore`/runtime Event persistence/generic Event applier
  registry/reducer/`UnitOfWork`/`TransactionManager`/`MutationContext`, no
  new production dependency, and `StateStore`/`StateSnapshot` unchanged. A
  closing "G6a boundary" paragraph records that this fixes obligations only,
  not the `DamageCommand`/`DamageApplied` payload schema, resistances,
  vulnerabilities, immunities, temporary HP, unconscious/death, healing,
  critical damage, equipment, Attack → Damage orchestration, generic Effects,
  or a generic modifier pipeline.
- This is a concretization of the already-accepted DEC-0032, not a new
  architectural decision: no new Decision Log entry was added, and DEC-0032's
  existing text was left unmodified.
- Added one short cross-reference sentence to the existing G5 paragraph in
  `docs/ROADMAP.md`, noting that §3.18 also fixes the acceptance obligations
  for the first Damage → HP slice. No new Roadmap checkbox was added, and the
  paragraph's existing `Damage`/`HP` framing was left otherwise unchanged.
- `CLAUDE.md` was re-read for drift against the new subsection; its existing
  G5 bullet, deferred-abstractions block, and naming-trap rows already match
  the concretized contract, so it was left unchanged.

### Changed files

- `docs/ARCHITECTURE.md` — new §3.18 "Acceptance obligations for the first
  Damage → HP consumer" subsection (unnumbered `####` heading, no Table of
  contents or Quick lookup table change needed).
- `docs/ROADMAP.md` — one added cross-reference sentence in the existing G5
  paragraph.
- `docs/DEVELOPMENT_LOG.md` — this factual iteration entry.

### Not implemented

- No production Python, test, rule, or campaign file was changed.
- No `DamageCommand`, `DamageApplied` Event, Damage resolver, or Event
  applier was implemented or schema-designed.
- No `EventApplierRegistry`, `UnitOfWork`, `TransactionManager`,
  `WorkingState`, `MutationContext`, `StateChange`, generic reducer, or
  generic transaction coordinator was added.
- `docs/DECISIONS.md` DEC-0032 was left unmodified; no new Decision Log entry
  was added.
- `StateStore`'s `load()`/`save()` signature, `StateSnapshot`'s schema, and
  `ResolutionResult`'s fields are unchanged.
- No new test was added for this documentation-only iteration.

### Verification

- The repository's own `.venv` (Python 3.12.9, pytest 9.1.1) was used
  directly; `--basetemp` was pointed outside the default OS temp directory,
  whose `pytest-of-redbu` folder was not writable in this environment.
- Narrow `tests/architecture` suite, including the documentation-link and
  `§N.N` cross-reference validator covering the new subsection's §3.2.1,
  §12.9, and §3.6 references: 7 passed.
- Full pytest suite: 805 passed. No production or test file was changed.
- `git diff --check` passed.
- `git status --short` showed only the tracked documentation files listed
  above as modified.
- No formatter, linter, or type checker is configured in the repository.
- Diff written to `review.patch` in the repository root for review; not
  committed. The prior G5 canonical-contract commit
  (`e4acf06f5b0dae8d1d2d70bcebc624785bb26546`) was already committed and
  pushed before this iteration started, so `review.patch` contains only this
  iteration's changes.

## 2026-08-28 — G6a Group 1: ApplyDamage Command + DamageResult + pure resolver

### Initial state

- Branched `claude/g6a-minimal-damage-hp` from `origin/main` at
  `c040c2992a2e1e1a87021c42439e8b81560d6181`, which already carried the G5
  State Mutation Foundation canonical contract (§3.18, DEC-0032) and its
  acceptance obligations for the future first Damage → HP consumer, but no
  `ApplyDamageCommand`/`DamageResult` Python code, schema, or resolver.
- This iteration implements only Group 1 of the G6a evidence slice: the pure
  Domain contract `already-resolved positive damage amount → one target
  CreatureState → DamageResult`. It does not implement `DamageApplied` Event,
  Event application, an Application handler, or any `StateStore.save()`
  mutation — those remain for later G6a groups.

### Implementation

- Added `src/dnd_engine/domain/commands/damage.py`: immutable
  `ApplyDamagePayload` (`target_id: str`, `amount: int`, `amount >= 1`) and
  immutable `ApplyDamageCommand` (`command_id`, `campaign_id`, `actor_id`,
  `payload: ApplyDamagePayload`, fixed `type = "ApplyDamageCommand"`),
  following the same intrinsic-invariant style as the existing
  `AttackCommand`/`AttackPayload`. No `new_hp`, `damage_type`, `weapon_id`,
  `attack_id`, `critical`, `source`, or `rolls` field was added.
- Added `src/dnd_engine/domain/rules/damage.py`: immutable `DamageResult`
  (`target_id`, `amount`, `previous_hp`, `new_hp`) that independently
  enforces its own field types, `amount >= 1`, `previous_hp >= 0`, and the
  canonical formula invariant `new_hp == max(0, previous_hp - amount)`; and
  the pure `resolve_damage(command, target) -> DamageResult` resolver, which
  validates concrete `ApplyDamageCommand`/`CreatureState` argument types,
  validates `command.payload.target_id == target.id`, reads
  `target.current_hp`, computes the clamped `new_hp`, and returns a
  `DamageResult` without mutating `target`, calling `DiceEngine`, loading a
  Definition, or performing I/O. Target lookup remains an Application-handler
  concern, per §3.18's "Resolver ≠ State application" split.
- Zero-HP input is accepted as ordinary input: a target already at
  `current_hp = 0` with `amount > 0` resolves to a successful `DamageResult`
  with `previous_hp = 0` and `new_hp = 0`; no death/unconscious semantics
  were introduced. `DamageType` was intentionally left unused by this slice.

### Changed files

- `src/dnd_engine/domain/commands/damage.py` — new file.
- `src/dnd_engine/domain/rules/damage.py` — new file.
- `tests/domain/test_damage_command.py` — new file, narrow
  `ApplyDamageCommand`/`ApplyDamagePayload` tests.
- `tests/domain/test_damage.py` — new file, narrow `DamageResult`/
  `resolve_damage` tests.
- `docs/DEVELOPMENT_LOG.md` — this factual iteration entry.

### Not implemented

- No `DamageApplied` Event, Event applier, or `StateSnapshot` replacement
  logic.
- No Application-level `DamageHandler`, `EventMetadataProvider` usage, or
  `StateStore.save()` call.
- No Attack → Damage orchestration, weapon damage dice, critical damage,
  `DamageType` mechanics (resistance/immunity/vulnerability), temporary HP,
  healing, death saves, or conditions.
- No canonical `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`,
  `docs/ROADMAP.md`, `README.md`, or `CLAUDE.md` change: per this task's own
  scope, the contract will be documented once full G6a production evidence
  exists.
- No production dependency was added or changed; `pyproject.toml` is
  unmodified.

### Verification

- The repository's own `.venv` (Python 3.12.9, pytest 9.1.1) was used
  directly; `--basetemp` was pointed outside the default OS temp directory,
  whose `pytest-of-redbu` folder was not writable in this environment (same
  pre-existing environment condition already recorded in the prior G5
  iteration entry above).
- Narrow new tests: `tests/domain/test_damage.py` (24 tests) and
  `tests/domain/test_damage_command.py` (17 tests) — 41 passed.
- Full pytest suite: 846 passed, with `--basetemp` redirected outside the
  unwritable default temp directory (805 pre-existing, matching the prior G5
  iteration's recorded full-suite baseline, plus the 41 new Group 1 tests);
  no existing test was modified or removed.
- `python -m mypy src/dnd_engine`: `Success: no issues found in 74 source
  files`.
- `git diff --check`: no whitespace errors.
- `git status --short` showed `docs/DEVELOPMENT_LOG.md` modified plus the
  four new Domain/test files marked intent-to-add solely so they are
  included in `review.patch`; no other tracked file was modified, and no
  production dependency changed.
- Diff written to `review.patch` in the repository root for review; not
  committed, not pushed, no pull request opened.

## 2026-08-28 — G6a Group 2: DamageApplied V1 Event contract

### Initial state

- Continued on `claude/g6a-minimal-damage-hp`, on top of the committed G6a
  Group 1 iteration (`ApplyDamageCommand`, `ApplyDamagePayload`,
  `DamageResult`, `resolve_damage`, commit
  `928df81f9d7fe0426d4fe6428032918d4ec5090e`). No `DamageApplied` Event, Event
  builder, Event application, Application handler, or `StateStore.save()`
  mutation existed yet.
- This iteration implements only Group 2 of the G6a evidence slice: the
  concrete immutable `DamageApplied` V1 `GameEvent` contract, built from an
  already-resolved `ApplyDamageCommand` + `DamageResult` pair plus supplied
  Event metadata. It does not implement Event → State application, a
  `DamageHandler`, `StateStore.save()`, or an `EventStore` — those remain for
  later G6a groups.

### Implementation

- Added `src/dnd_engine/domain/events/damage.py`, following the same
  concrete-Event style as `events/attack.py` and `events/saving_throw.py`:
  - `DamageAppliedPayloadV1` (`target_id: str`, `amount: int`,
    `previous_hp: int`, `new_hp: int`) — a frozen internal payload VO whose
    `__post_init__` enforces only field runtime types (no `bool`-as-`int`
    coercion). Unlike `AttackResolvedPayloadV1`/`SavingThrowResolvedPayloadV1`,
    it does **not** re-derive or re-check the `new_hp == max(0, previous_hp -
    amount)` formula: that rule invariant is already owned exclusively by
    `DamageResult` (§3.18 "Resolver ≠ State application" / "Rule consistency
    already belongs to the resolver's own Result type"), and this task's own
    instructions called out not duplicating it here.
  - `build_damage_applied_v1(*, event_id, timestamp, command, outcome) ->
    GameEvent` — validates `command` is an `ApplyDamageCommand`, `outcome` is
    a `DamageResult`, and that `outcome.target_id`/`outcome.amount` match
    `command.payload.target_id`/`command.payload.amount`; then builds the
    typed payload from `outcome` fields verbatim (no recomputation) and
    returns a `GameEvent` with `type="DamageApplied"`, `version=1`,
    `event_id`/`timestamp` taken from the supplied arguments (no clock read,
    no ID generation), `command_id`/`campaign_id`/`actor_id` copied from
    `command`, and `caused_by=None`.
  - Canonical payload written to the Event is exactly `{"targetId",
    "amount", "previousHp", "newHp"}` — no `damageType`, `weaponId`,
    `attackId`, `critical`, `overkill`, `effectiveHpLoss`, `condition`, or
    `stateChanges` field.
- No changes to `GameEvent`, `EventSerializer`, or the Event Envelope: the
  new Event round-trips through the existing generic `EventSerializer`
  unchanged, with no Damage-specific serializer, deserializer registry, Event
  type/version dispatcher, schema registry, or `EventStore` added.

### Changed files

- `src/dnd_engine/domain/events/damage.py` — new file.
- `tests/domain/test_damage_event.py` — new file: canonical Event shape
  (`type`, `version`, exact payload key set, `commandId`/`campaignId`/
  `actorId` correlation, `causedBy is None`, timestamp passthrough), target
  and amount correlation-mismatch rejection, wrong command/outcome type
  rejection, generic-`EventSerializer` round-trip, Event/payload
  immutability, and payload field-type rejection. No test asserts the
  `new_hp` formula clamp as a builder-level rule, per this task's scope.
- `docs/DEVELOPMENT_LOG.md` — this factual iteration entry.

### Not implemented

- No Event → State application, replacement `CreatureState`/`StateSnapshot`
  construction, or production `StateStore.save()` call.
- No Application-level `DamageHandler` or `EventMetadataProvider` usage for
  Damage.
- No `EventStore`, filesystem Event persistence/append, or serialized Event
  type/version dispatch — Event serialization is exercised only through the
  existing generic `EventSerializer`, unchanged.
- No Attack → Damage orchestration, `DamageType` mechanics
  (resistance/immunity/vulnerability), healing, or generic Event applier/
  registry/`UnitOfWork`.
- No canonical `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`,
  `docs/ROADMAP.md`, `README.md`, or `CLAUDE.md` change: `DamageApplied` V1
  exists as a runtime immutable Domain fact only — it is not yet applied to
  State and not yet persisted as durable Event history, so the canonical
  contract documentation is deferred to a later G6a group once fuller
  production evidence exists.
- No production dependency was added or changed; `pyproject.toml` is
  unmodified.

### Verification

- The repository's own `.venv` (Python 3.12.9, pytest 9.1.1) was used
  directly, with `--basetemp` redirected outside the default OS temp
  directory (same pre-existing unwritable `pytest-of-redbu` condition
  recorded in prior iteration entries).
- Narrow new tests: `tests/domain/test_damage_event.py` (20 tests), run
  together with `tests/domain/test_damage.py`, `tests/domain/
  test_damage_command.py`, and `tests/domain/test_attack_event.py` for
  pattern-consistency cross-checking — 91 passed.
- Full pytest suite: 866 passed (846 pre-existing Group-1 baseline plus the
  20 new Group 2 tests); no existing test was modified or removed.
- `python -m mypy src/dnd_engine`: `Success: no issues found in 75 source
  files`.
- `git diff --check`: no whitespace errors (only expected LF/CRLF
  line-ending notices from Git on the two new files).
- `git status --short` showed `docs/DEVELOPMENT_LOG.md` modified plus the
  two new Group 2 files (`src/dnd_engine/domain/events/damage.py`,
  `tests/domain/test_damage_event.py`) marked intent-to-add solely so they
  are included in `review.patch`; no other tracked file was modified, and no
  production dependency changed. Group 1 is already in `HEAD`
  (`928df81f9d7fe0426d4fe6428032918d4ec5090e`) and is not part of this diff.
- `review.patch` in the repository root was regenerated (`git diff >
  review.patch`) so it contains only the fresh, uncommitted Group 2 changes,
  not the already-committed Group 1 content it previously held. Not
  committed, not pushed, no pull request opened.

## 2026-08-28 — G6a Group 3: Creature Event applier + DamageHandler + authoritative persistence

### Initial state

- Group 1 (`928df81`) and Group 2 (`5fad27c`) were already committed to
  `claude/g6a-minimal-damage-hp`: the immutable `ApplyDamageCommand` /
  `ApplyDamagePayload`, the pure `resolve_damage` resolver and its
  `DamageResult`, and the concrete `DamageApplied` V1 `GameEvent` contract
  (`build_damage_applied_v1`). No Event → State application, Application
  handler, or `StateStore.save()` mutation existed yet — no production
  gameplay code path had ever called `StateStore.save()`.
- This iteration implements Group 3 of the G6a evidence slice: the first
  concrete Event → `CreatureState` applier, the `DamageHandler` Application
  orchestrator, and the first production authoritative mutation lifecycle
  `ApplyDamageCommand → DamageResult → DamageApplied → CreatureState
  replacement → StateSnapshot replacement → StateStore.save() → successful
  ResolutionResult`, per §3.18 "Acceptance obligations for the first Damage →
  HP consumer".

### Implementation

- Added `apply_damage_applied_v1(creature: CreatureState, event: GameEvent)
  -> CreatureState` to the existing `src/dnd_engine/domain/events/damage.py`,
  alongside `build_damage_applied_v1` rather than in a new generic mutation
  module or inside `domain/state/creature.py` — placing it in
  `domain/state/creature.py` would create a circular import
  (`state/creature.py -> events/damage.py -> rules/damage.py ->
  state/creature.py`), and co-locating the Event's builder and its applier in
  one file keeps both directions of the same versioned `DamageApplied` V1
  contract together without a new package. It: validates `creature` is a
  `CreatureState` and `event` is a `GameEvent`; requires
  `event.type == "DamageApplied"` and `event.version == 1`; requires the
  payload to have exactly the four canonical keys (`targetId`, `amount`,
  `previousHp`, `newHp`) and decodes them into the existing
  `DamageAppliedPayloadV1` (reusing its field-type `__post_init__` checks, via
  two small local `_payload_str`/`_payload_int` narrowing helpers so mypy
  accepts the `JSONValue` → `str`/`int` narrowing); requires
  `payload.targetId == creature.id` and `payload.previousHp ==
  creature.current_hp`; and returns `dataclasses.replace(creature,
  current_hp=payload.newHp)` — taking the already-resolved `newHp` verbatim,
  never recomputing `max(0, previous_hp - amount)`. All rejections raise the
  existing intrinsic `TypeError`/`ValueError` style and propagate directly;
  no new `ErrorCode` and no gameplay `ResolutionResult(success=False)` is
  involved, since a mismatch here is a State-application integrity failure,
  not a gameplay outcome. The function calls no `DiceEngine`, no
  `DefinitionSource`, no persistence I/O, reads no clock, allocates no Event
  ID, and constructs no new authoritative Event — it only decides whether the
  supplied Event may be projected onto the supplied Creature and, if so,
  returns the replacement.
- Added `src/dnd_engine/application/handlers/damage.py` with a concrete
  `DamageHandler`, in the same explicit-handler style as `AttackHandler`
  (`application/handlers/attack.py`). Constructor dependencies are exactly
  `StateStore` and `EventMetadataProvider` — no `DiceEngine`,
  `DefinitionSource`, `EventStore`, or dispatcher. `handle(command)`:
  loads the snapshot; looks up the actor `CreatureState` by
  `command.actor_id` (`ENTITY_NOT_FOUND`, `entity_id=command.actor_id`, no
  `field`, if absent — actor is a required Command initiator even though
  Damage does not use it for calculation); looks up the target
  `CreatureState` by `command.payload.target_id` (`ENTITY_NOT_FOUND`,
  `entity_id=command.payload.target_id`, `field="target_id"`, if absent);
  calls the pure `resolve_damage(command, target)`; requests
  `EventMetadataProvider.next_metadata`; builds the `DamageApplied` V1 Event
  via `build_damage_applied_v1`; calls `apply_damage_applied_v1(target,
  event)` to get the replacement target; builds a replacement `creatures`
  tuple by substituting the replacement target in place (original ordering
  and every other `CreatureState` object preserved by identity, no
  `deepcopy()`); builds a replacement `StateSnapshot` reusing the loaded
  `CampaignState` and `characters` tuple unchanged; calls
  `StateStore.save(replacement_snapshot)` exactly once; and only then
  returns `ResolutionResult(success=True, outcome=DamageResult, events=(event,),
  errors=())`. Both failure branches (missing actor, missing target) return
  before `EventMetadataProvider` or `StateStore.save()` are ever called. If
  `StateStore.save()` raises `StateStoreError`, the exception propagates
  unmodified — it is not mapped to an `EngineError`, no
  `ResolutionResult(success=True, ...)` is constructed or returned, and there
  is no retry or compensation.

### Changed files

- `src/dnd_engine/domain/events/damage.py` — added `apply_damage_applied_v1`
  and its two private narrowing helpers, alongside the existing
  `DamageAppliedPayloadV1`/`build_damage_applied_v1` from Group 2.
- `src/dnd_engine/application/handlers/damage.py` — new file: `DamageHandler`.
- `tests/domain/test_damage_applier.py` — new file (23 tests): deterministic
  same-Event/same-Creature replacement, returned object identity vs. source
  object non-mutation, exact preserved-field set
  (`id`/`definition_id`/`ability_scores`/`max_hp`), resulting `CreatureState`
  invariant satisfaction, rejection of wrong target/`previousHp`
  mismatch/wrong Event type/wrong version/malformed payload (missing field,
  unknown field, wrong runtime type per field), rejection of non-`CreatureState`/
  non-`GameEvent` inputs, the documented `7 -> 4` replay-rejection case, the
  `0 -> 0` no-op acceptance case with an explicit test (and comment) recording
  that duplicate `0 -> 0` application is *not* detected — a narrow,
  intentional limitation per docs/ARCHITECTURE.md §3.18 "Exact MVP atomicity
  boundary", where replay is explicitly not guaranteed, not a bug — and a
  static source-text check that the applier module names no `DiceEngine`,
  `DefinitionSource`, `StateStore`, `open(`, or `Path(`.
- `tests/application/test_damage_handler.py` — new file (7 tests), in the
  existing Spy-`StateStore`/call-order-list style already used by
  `tests/application/test_attack_handler.py`: full successful lifecycle
  (`["load", "metadata", "save"]` call order; loaded snapshot/target
  observationally unchanged after the call; saved snapshot is a new object
  distinct from the loaded one; saved target is a new object with
  `current_hp == 4`; unrelated creatures/actor/characters/campaign preserved
  by identity; creature ordering preserved); missing-actor and missing-target
  structured failures with no metadata request and no save; an
  applier/invariant-failure case using a single targeted `monkeypatch.setattr`
  on the already-imported `apply_damage_applied_v1` name inside the handler
  module (no new injectable Protocol introduced for this) proving no save
  happens when Event application fails; metadata-provider failure
  propagating with no save; and `StateStore.save()` failure propagating as
  `StateStoreError` with the loaded graph unchanged and `save()` attempted
  exactly once.
- `tests/integration/test_damage_real_adapters.py` — new file (1 test): a
  real `FilesystemStateStore` seeded with `monster_001` at `current_hp=7,
  max_hp=7` alongside an unrelated actor and an unrelated second monster; a
  `DamageHandler` (no fakes except a fixed `EventMetadataProvider`) applies
  `amount=3`; asserts the persisted `state.json` bytes actually changed,
  `store.load("campaign_001")` reflects `current_hp == 4` for the target
  while the actor/other-monster/`CharacterState`/`CampaignState` reload
  unchanged, no `events.jsonl` or other file besides `state.json` exists in
  the campaign directory afterward, and no leftover `.state-*.tmp` file
  remains. A local `CountingStateStore` test-only wrapper delegates every
  call to the real `FilesystemStateStore` and counts `save()` invocations, to
  prove the handler calls `save()` exactly once through the observable store
  seam without adding call-counting to the production adapter itself.
- `docs/DEVELOPMENT_LOG.md` — this factual iteration entry.

### Not implemented

- No `EventStore`, `events.jsonl` runtime append, or serialized Event
  type/version dispatch — `DamageApplied` Events remain in-memory
  `ResolutionResult` facts, not durable runtime history; the integration test
  explicitly asserts no `events.jsonl` or other history artifact is created.
- No generic `EventApplier` Protocol/registry, reducer, `UnitOfWork`,
  `TransactionManager`, `WorkingState`, `MutationContext`, `StateChange`,
  generic Creature repository, `replace_entity` helper, State revision,
  optimistic locking, or retry — the applier is one concrete function and the
  handler is one concrete class, per §3.18's explicit deferred-abstraction
  list.
- `StateStore` remains exactly `load()`/`save()`; `StateSnapshot`'s schema is
  unchanged; `ResolutionResult` gained no new field.
- Attack → Damage orchestration, `DamageType` mechanics
  (resistance/immunity/vulnerability), healing, unconscious/death, critical
  damage, and equipment remain entirely out of scope, per the G6a boundary in
  §3.18.
- No canonical `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`,
  `docs/ROADMAP.md`, `README.md`, or `CLAUDE.md` change: this Group 3 work is
  reported as evidence for review, and canonical documentation is finalized
  only in a later G6a group once the full slice is accepted.
- No production dependency was added or changed; `pyproject.toml` is
  unmodified.

### Verification

- The repository's own `.venv` (Python 3.12.9, pytest 9.1.1) was used
  directly, with `--basetemp` redirected outside the default OS temp
  directory (same pre-existing unwritable `pytest-of-redbu` condition
  recorded in prior iteration entries).
- Narrow new tests: `tests/domain/test_damage_applier.py` (23),
  `tests/application/test_damage_handler.py` (7), and
  `tests/integration/test_damage_real_adapters.py` (1), run together with
  `tests/domain/test_damage.py`, `tests/domain/test_damage_command.py`,
  `tests/domain/test_damage_event.py`, `tests/infrastructure/
  test_state_store.py`, and all four existing read-only handler test modules
  (`test_ability_check_handler.py`, `test_saving_throw_handler.py`,
  `test_skill_check_handler.py`, `test_attack_handler.py`) for
  regression/pattern-consistency cross-checking — 161 passed. The existing
  read-only handler test suites already assert `store.save_calls == []` in
  every one of their success-path tests (21 such assertions across the three
  non-Attack handler test modules alone), which already discharges §3.18's
  "existing read-only handlers still never call `StateStore.save()`"
  obligation without duplicating new regression tests for it here.
- Full pytest suite: 897 passed (866 pre-existing Group-1/Group-2 baseline
  plus the 31 new Group 3 tests); no existing test was modified or removed.
- `python -m mypy src/dnd_engine`: `Success: no issues found in 76 source
  files`. (`mypy` is configured via `pyproject.toml` `[tool.mypy] files =
  ["src/dnd_engine"]` and is not run over `tests/`, consistent with prior
  iterations.)
- `git diff --check`: no whitespace errors (only expected LF/CRLF
  line-ending notices from Git on the new/modified files).
- `git status --short` showed `docs/DEVELOPMENT_LOG.md` and
  `src/dnd_engine/domain/events/damage.py` modified, plus the four new
  Group 3 files (`src/dnd_engine/application/handlers/damage.py`,
  `tests/application/test_damage_handler.py`,
  `tests/domain/test_damage_applier.py`,
  `tests/integration/test_damage_real_adapters.py`) marked intent-to-add
  solely so they are included in `review.patch`; no other tracked file was
  modified, and no production dependency changed. Group 1 and Group 2 are
  already in `HEAD` (`928df81f9d7fe0426d4fe6428032918d4ec5090e`,
  `5fad27c24668be538e52726ce556ef240a077bec`) and are not part of this diff.
- `review.patch` in the repository root was regenerated (`git diff >
  review.patch`) so it contains only the fresh, uncommitted Group 3 changes.
  Not committed, not pushed, no pull request opened.

## 2026-08-28 — G6a Group 4: full verification + abstraction review + canonical documentation

### Initial state

- Group 1 (`928df81`), Group 2 (`5fad27c`), and Group 3 (`176d6a6`) were
  already committed to `claude/g6a-minimal-damage-hp`: `ApplyDamageCommand`/
  `ApplyDamagePayload`, the pure `resolve_damage`/`DamageResult` resolver, the
  `DamageApplied` V1 `GameEvent` contract, the concrete
  `apply_damage_applied_v1` Creature applier, and the `DamageHandler`
  Application orchestrator — the first production gameplay handler path that
  calls `StateStore.save()`. No canonical
  documentation (`docs/ARCHITECTURE.md`, `docs/DECISIONS.md`,
  `docs/ROADMAP.md`, `README.md`, `CLAUDE.md`) had been updated for this
  slice yet; the working tree was clean at the start of this iteration.
- This iteration performs no production code change. It (1) reviews the
  committed Group 1–3 production code for evidence that would justify any
  deferred abstraction from §3.6/§3.18, (2) synchronizes canonical
  documentation with the actually-implemented G6a behaviour, and (3) re-runs
  the full verification suite against the already-committed code.

### Abstraction review

- Re-read `src/dnd_engine/domain/commands/damage.py`,
  `src/dnd_engine/domain/rules/damage.py`,
  `src/dnd_engine/domain/events/damage.py`, and
  `src/dnd_engine/application/handlers/damage.py` end to end. Grepped
  `src/` for `WorkingState`, `UnitOfWork`, `EventApplierRegistry`,
  `TransactionManager`, `MutationContext`, `StateChange`, `EventStore`,
  `state_changes`, `CommandBus`, `EventBus`, `dispatcher`, and generic
  `*Registry` names — no match anywhere in `src/`.
- Verdict: **KEEP CONCRETE.** `DamageHandler` is the only production
  State-mutating consumer; `apply_damage_applied_v1` is the only production
  Event applier. Structural similarity between `DamageHandler` and the four
  existing read-only handlers (load snapshot, look up actor/target, resolve,
  build Event, return `ResolutionResult`) is surface-level only — the
  mutating handler's Event-application, replacement-`StateSnapshot`
  construction, and `StateStore.save()` steps have no counterpart in any
  read-only handler — and one production mutation consumer is not evidence
  for a generic Event applier, `WorkingState`, a Creature replacement helper,
  `UnitOfWork`, a transaction coordinator, `state_changes`, or generic
  handler orchestration. No new production abstraction was introduced.
  **Healing is recorded as the next evidence checkpoint** for re-evaluating a
  shared HP mutation primitive, once it exists as a second concrete
  HP-mutating consumer — not before.

### Documentation changes

- `docs/ARCHITECTURE.md`: added `### 3.19. Minimal Damage → HP mutation
  vertical slice (G6A)` after §3.18, before `## 4. ID System` (the actual
  tail of §3 on this branch — confirmed by reading the section list before
  editing, not assumed). Documents implemented Scope, Explicit exclusions,
  `ApplyDamageCommand`/`ApplyDamagePayload` (internal/Application-level
  intent, not an external API promise), `DamageResult`'s formula invariant,
  the exact `DamageApplied` V1 payload and its "Event carries the complete
  resolved transition" property, the concrete
  `CreatureState + DamageApplied V1 → replacement CreatureState` boundary,
  the Errors taxonomy (existing `ErrorCode`s only, no new code; intrinsic/
  integrity mismatches as `TypeError`/`ValueError`; `StateStoreError`
  propagation), the `0 → 0` no-op case and its documented replay-detection
  limitation (explicitly not described as exactly-once), the persistence
  boundary (snapshot-authoritative, non-durable Event, no `EventStore`), and
  the post-implementation Abstraction verdict (`KEEP CONCRETE`, Healing as
  next checkpoint). Added the matching Quick-lookup row and Table-of-contents
  entry.
- `docs/DECISIONS.md`: appended `DEC-0033 — First concrete Damage → HP
  mutation slice (G6A) stays concrete` (tail was DEC-0032 — confirmed by
  reading the file before appending). Explains why direct already-resolved
  Damage was chosen over Attack → Damage as the first mutation consumer, why
  the Event stores both `previousHp` and `newHp`, why Event application
  executes on the `CreatureState` Owner boundary while `DamageHandler` builds
  the replacement `StateSnapshot`, why `0 → 0` is allowed without a replay
  guarantee, and why `EventStore`/`state_changes`/`UnitOfWork`/generic
  applier stay deferred. Did not edit DEC-0032.
- `docs/ROADMAP.md`: added a factual note under Phase 2 recording that the
  first minimal `direct Damage → current_hp` production mutation slice (G6A,
  §3.19) is implemented and is concrete evidence for G5, without checking
  `HP` or `Damage`. `Healing` stays unchecked. No Roadmap checkbox was
  flipped.
- `README.md`: reworded §4 "Events являются историей изменений" and
  "Хранение данных" so they no longer imply Event → State application is
  fully planned/deferred — they now name the one concrete `DamageApplied` →
  `CreatureState.current_hp` projection plus snapshot persistence as
  implemented, while durable Event history, `EventStore`, generic/serialized
  Event dispatch, and recovery/replay stay listed as deferred. Updated the
  Phase 2 summary near "Быстрый старт" to record that the minimal
  `Damage → current_hp` slice exists while broad `Damage`/`HP` and combat
  remain unimplemented.
- `CLAUDE.md`: updated only the summary facts G6a actually changed — the
  `Текущая фаза` G5 bullet now names §3.19 as its first concrete consumer;
  added one new bullet to `Реализованные контракты Phase 2` describing the
  implemented G6a slice (Command, resolver, Event, applier, handler, write
  scope, `0 → 0` limitation, exclusions, Healing checkpoint); and updated
  `Отложенные абстракции — не вводить` to record that one concrete Event
  applier and one concrete mutating handler now exist for Damage → HP without
  removing any item from the deferred list. No duplicate full Architecture
  contract was added; every fact links back to §3.19/DEC-0033.

### Verification

- Environment: repository's own `.venv` (`Python 3.12.9`, `pytest 9.1.1`),
  same as prior G6a iterations; `--basetemp` redirected into this session's
  scratchpad directory (the default OS temp `pytest-of-redbu` folder remains
  unwritable in this environment, as recorded in every prior iteration).
- `tests/domain/test_damage.py` + `test_damage_command.py` +
  `test_damage_event.py` + `test_damage_applier.py` +
  `tests/application/test_damage_handler.py` +
  `tests/integration/test_damage_real_adapters.py` together: **92 passed**
  (24 + 17 + 20 + 23 + 7 + 1).
- `tests/infrastructure/test_state_store.py` +
  `tests/application/test_ability_check_handler.py` +
  `tests/application/test_saving_throw_handler.py` +
  `tests/application/test_skill_check_handler.py` +
  `tests/application/test_attack_handler.py` (StateStore + read-only handler
  regression): **69 passed**; every read-only handler success-path test still
  asserts `store.save_calls == []`.
- Full `python -m pytest`: **897 passed** — unchanged from the Group 3
  baseline, confirming this iteration made no production or test code change.
- `python -m mypy src/dnd_engine`: `Success: no issues found in 76 source
  files` — unchanged file count from Group 3.
- `git diff --check`: no whitespace errors.
- `pyproject.toml`: no diff; `dependencies = []` unchanged; no new dev
  dependency.
- Forbidden-abstraction grep over `src/` for `WorkingState`, `UnitOfWork`,
  `EventApplierRegistry`, `TransactionManager`, `MutationContext`,
  `StateChange`, `EventStore`, `state_changes`, `CommandBus`, `EventBus`,
  `dispatcher`, generic `*Registry`, `events.jsonl`: no match.
  `StateStore` Protocol confirmed exactly `load()`/`save()`;
  `ResolutionResult` confirmed to still have exactly `success`, `command_id`,
  `outcome`, `events`, `errors`; `StateSnapshot` confirmed to still have
  exactly `campaign`, `creatures`, `characters`.
- `git status --short` showed exactly five modified, already-tracked files —
  `CLAUDE.md`, `README.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`,
  `docs/ROADMAP.md` — plus this `docs/DEVELOPMENT_LOG.md` entry; no `src/` or
  `tests/` file changed, no untracked file, no production dependency
  changed. Groups 1–3 are already in `HEAD` (`928df81`, `5fad27c`,
  `176d6a6`) and are not part of this diff.
- `review.patch` in the repository root was regenerated (`git diff >
  review.patch`) so it contains only the fresh, uncommitted Group 4
  documentation changes relative to the committed Group 3 `HEAD`. Not
  committed, not pushed, no pull request opened, no merge.

### Correction pass — stale current-status wording

- A review of the first Group 4 documentation pass found that
  `docs/ARCHITECTURE.md` §3.18 still read as if no mutation consumer existed,
  contradicting the newly-added §3.19. This pass makes documentation-only
  corrections; production Groups 1–3 remain unchanged and unreviewed by this
  pass (approved as-is), and DEC-0032 was not edited (append-only log).
- `docs/ARCHITECTURE.md` §3.18 fixes, without rewriting the G5 foundation
  contract itself: the `Implementation status` line now reads "Canonical
  foundation contract; first concrete consumer implemented in §3.19" instead
  of claiming no mutating Command/applier/`save()` call exists; the write-scope,
  "Rule resolution", "Event → State contract", and "Resolver ≠ State
  application" passages that illustrated the future shape of Damage/
  `DamageResult`/the first applier now point at the implemented §3.19
  artifacts instead of describing them as hypothetical; "No production
  state-mutating gameplay consumer exists yet" now names `DamageHandler`/
  `apply_damage_applied_v1` as that consumer and points at §3.19's
  post-implementation `KEEP CONCRETE` verdict as the reason the deferred list
  still stands; and the "Acceptance obligations"/"G6a boundary" subsections
  no longer say the exact `ApplyDamageCommand`/`DamageApplied` schema remains
  open — they now point at §3.19/DEC-0033 as having fixed it, while
  Attack → Damage, `DamageType` mechanics, healing, and the rest of the G6a
  exclusion list stay open. The general, still-forward-looking language
  describing the lifecycle for *any* future mutating Command (not
  specifically Damage) was left as-is, since §3.18 remains the general
  foundation for future consumers too, not a duplicate of §3.19.
- `docs/ARCHITECTURE.md` §3.19: corrected "substituting the replacement
  `CreatureState` for the original by identity" to "by stable Creature ID
  (matching `creature.id == target.id`)" — matching the actual
  `replacement_target if creature.id == target.id else creature` production
  code in `DamageHandler`, not Python object identity. Corrected the Errors
  section's closing sentence: an Event/State integrity mismatch propagating
  as `TypeError`/`ValueError` is now described as an
  application-integrity/programming-state failure in its own right, not as
  an instance of §3.18's Infrastructure-level "Save failure semantics" (which
  governs `StateStore.save()` failures specifically, a separate boundary).
- `CLAUDE.md`: the G4b Weapon damage dice bullet's closing sentence — "Dagger/
  weapon attacks, Damage, HP и generic dice DSL остаются deferred" —
  contradicted the new G6A bullet immediately below it (which documents an
  implemented direct-Damage → HP slice). Narrowed it to "Dagger/weapon
  attacks, weapon-derived Damage / Attack → Damage orchestration, broad
  HP/combat mechanics и generic dice DSL остаются deferred", which still
  accurately excludes weapon-driven damage and combat while no longer
  contradicting the implemented minimal slice.
- No change to `docs/DECISIONS.md` (DEC-0032 untouched, DEC-0033 unedited),
  `docs/ROADMAP.md` (`HP`/`Damage`/`Healing` still unchecked), the
  `KEEP CONCRETE` verdict, EventStore/replay deferrals, or any G6a gameplay
  semantics. No production Python or test file was read for edits in this
  pass beyond the read-only re-scan needed to confirm the `by stable Creature
  ID` wording matches `src/dnd_engine/application/handlers/damage.py`.

### Re-verification after the correction pass

- Environment unchanged: repository's own `.venv` (`Python 3.12.9`,
  `pytest 9.1.1`), `--basetemp` redirected into this session's scratchpad
  directory.
- Damage-specific suite (`tests/domain/test_damage.py`,
  `test_damage_command.py`, `test_damage_event.py`, `test_damage_applier.py`,
  `tests/application/test_damage_handler.py`,
  `tests/integration/test_damage_real_adapters.py`): **92 passed** —
  unchanged, as expected for a documentation-only pass.
- StateStore + read-only handler regression set: **69 passed** — unchanged.
- Full `python -m pytest`: **897 passed** — unchanged from Group 3/the first
  Group 4 pass.
- `python -m mypy src/dnd_engine`: `Success: no issues found in 76 source
  files` — unchanged.
- `git diff --check`: no whitespace errors.
- Re-scanned the corrected `docs/ARCHITECTURE.md`/`README.md`/`CLAUDE.md` for
  the stale patterns named in the correction request ("no production
  state-mutating consumer exists", "Damage/HP mutation is entirely
  unimplemented", "the first Damage applier shape is still undecided", "exact
  G6A Command/Event schema is still open") — no remaining match.
- `git status --short`: the same five previously-modified tracked files
  (`CLAUDE.md`, `README.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` —
  unchanged content, `docs/ROADMAP.md`) plus this
  `docs/DEVELOPMENT_LOG.md` entry; still no `src/`/`tests/` change, no
  untracked file, no production dependency change.
- `review.patch` was regenerated again (`git diff > review.patch`) so it
  contains the corrected Group 4 documentation changes relative to the
  committed Group 3 `HEAD`. Not committed, not pushed, no pull request
  opened, no merge.

### Precision correction pass — evidence wording and "first save()" phrasing

- Final review of the correction pass flagged two remaining precision issues,
  both text-only; production Groups 1–3, tests, Roadmap status, and the
  `KEEP CONCRETE` verdict itself were unchanged.
- `docs/DECISIONS.md` DEC-0033: the Decision paragraph overstated the
  relationship to DEC-0032 ("which DEC-0032 already established is
  insufficient evidence") and stated a numeric two-consumer abstraction rule
  ("can only be evaluated with real evidence from two concrete consumers").
  Reworded so the insufficiency finding is attributed to the post-G6A review
  recorded by DEC-0033/§3.19 itself — DEC-0032 deferred these abstractions
  pending evidence, it did not pre-decide the outcome — and so Healing is
  named as the next checkpoint because it is the first expected second
  HP-mutating use case with materially related but different semantics, with
  re-evaluation keyed to the actual common responsibilities/invariants/
  differences the two implementations demonstrate, not to reaching a
  consumer count of two.
- `docs/DEVELOPMENT_LOG.md` (this Group 4 entry's own "Initial state"
  paragraph) and `docs/ARCHITECTURE.md` §3.18's `Implementation status`
  paragraph both said "the first production `StateStore.save()` call in the
  repository's history" / "including the first production `StateStore.save()`
  call" — overbroad, since it could be read as claiming the `StateStore`
  adapter or its `save()` method did not previously exist, rather than that
  no production gameplay handler had called it yet. Both reworded to "the
  first production gameplay handler path/mutation path that calls
  `StateStore.save()`". The distinct architectural claim that `DamageHandler`
  is the first production state-mutating gameplay *consumer* (§3.18 "No
  generic transaction framework") was left unchanged, per this review's
  explicit instruction not to alter it.
- Re-ran the Damage-specific suite + regression set (**161 passed**), full
  `python -m pytest` (**897 passed**), `python -m mypy src/dnd_engine`
  (`Success: no issues found in 76 source files`), and `git diff --check`
  (clean) — all unchanged from the prior correction pass, confirming this is
  a text-only change.
- `review.patch` was regenerated a third time (`git diff > review.patch`) so
  it contains the fully-corrected Group 4 documentation changes relative to
  the committed Group 3 `HEAD`. Not committed, not pushed, no pull request
  opened, no merge.

### Final numeric-abstraction-threshold sweep

- Final review flagged two remaining live numeric-abstraction-threshold
  statements: `docs/ARCHITECTURE.md` §3.18 "No generic transaction framework"
  still said "one consumer remains insufficient evidence ... until a second
  concrete HP-mutating consumer ... actually exists", and `CLAUDE.md` still
  said "одного production-consumer недостаточно, чтобы его пересматривать".
  Both reworded to attribute the deferral to the post-G6A review finding no
  stable shared mutation responsibility yet, with Healing named as the next
  checkpoint for re-evaluation based on actual demonstrated
  commonalities/differences — not a consumer-count rule.
- Per the mandated post-fix patch scan, a third, previously-uncaught instance
  of the same pattern was found in `docs/ARCHITECTURE.md` §3.19 "Abstraction
  verdict": "One production mutation consumer is not sufficient evidence
  for..." and "it is the first candidate second consumer of an HP-shaped
  mutation ... and only once it exists as a concrete implementation should a
  shared HP mutation primitive be re-evaluated — not before." This was not
  one of the two locations named in the review request, but matches the same
  forbidden pattern (a numeric consumer-count threshold), so it was reworded
  with the same evidence-based framing used in §3.18/CLAUDE.md, to keep the
  scan's "no live equivalent statements" confirmation actually true rather
  than reporting a false negative.
- Re-ran the Damage-specific suite + regression set (**161 passed**), full
  `python -m pytest` (**897 passed**), `python -m mypy src/dnd_engine`
  (`Success: no issues found in 76 source files`), and `git diff --check`
  (clean).
- Re-scanned the regenerated `review.patch` for `one consumer remains
  insufficient`, `second concrete ... consumer` (as a requirement),
  `одного production-consumer недостаточно`, and `two concrete consumers` (as
  a threshold): the only remaining matches are inside this Development Log's
  own "Precision correction pass" section, quoting the prior, already-fixed
  wording for the record — clearly presented as corrected text, not a live
  canonical claim.
- `review.patch` was regenerated a fourth time (`git diff > review.patch`)
  reflecting this sweep. Not committed, not pushed, no pull request opened,
  no merge.

## 2026-08-28 — G6B Group 1 minimal Healing Domain contract

- Added immutable `ApplyHealingPayload` / `ApplyHealingCommand` Domain values
  for an already-resolved positive direct-healing amount and a fixed
  `ApplyHealingCommand` type.
- Added immutable `HealingResult` with exact runtime type/range validation and
  the intrinsic `new_hp == min(max_hp, previous_hp + amount)` invariant.
- Added pure deterministic `resolve_healing(command, target)`, including
  concrete input checks and target identity validation; it reads but does not
  mutate `CreatureState`.
- Added focused Domain tests for command validation, all required healing
  boundary semantics, result invariants, determinism, and observational
  non-mutation.
- This Group 1 slice adds no Healing Event, Event applier, Application handler,
  persistence, State schema change, shared HP abstraction, or dependency, and
  does not mark G6B complete.

## 2026-08-28 — G6B Group 2 HealingApplied V1 and Creature applier

- Added the immutable concrete `HealingApplied` V1 Event builder with the exact
  `targetId`, `amount`, `previousHp`, `maxHp`, and `newHp` payload copied from
  the validated `HealingResult`.
- Added the concrete Creature-level `apply_healing_applied_v1` transition with
  exact Event type/version/payload decoding, target/current-HP/max-HP integrity
  checks, and replacement construction through `dataclasses.replace`.
- Kept the Healing formula in the Group 1 resolver/`HealingResult`; the Event
  builder and applier neither recalculate nor decide gameplay semantics.
- Added focused Event, generic serializer round-trip, replacement, malformed
  payload, integrity, no-op/replay-limitation, and forbidden-dependency tests.
- This Group 2 slice adds no Application handler, StateSnapshot orchestration,
  persistence, generic Event applier, shared HP helper, or dependency, and does
  not mark G6B complete.

## 2026-08-28 — G6B Group 3 HealingHandler and snapshot persistence

- Added the concrete `HealingHandler` with the existing Damage sibling's
  Creature actor/target lookup semantics and the ordered `load → resolve →
  metadata → HealingApplied → apply → replacement snapshot → save → success`
  lifecycle.
- Kept loaded State read-only and constructed a replacement target, creatures
  tuple, and `StateSnapshot`; campaign, Character projections, unrelated
  Creatures, and tuple ordering remain unchanged.
- Preserved the full-HP positive-healing no-op lifecycle: it still creates a
  `HealingApplied` V1 Event, a replacement target/snapshot, calls
  `StateStore.save()` exactly once, and only then returns success.
- Preserved the existing metadata/applier/save failure boundaries: failures
  propagate, no successful result is returned, and no retry, rollback, Event
  persistence, or metadata-ID reuse is introduced.
- Added focused Application tests and real-`FilesystemStateStore` integration
  tests for normal `7 / 20 + 8 → 15 / 20` and capped
  `18 / 20 + 10 → 20 / 20` persistence, including reload and artifact checks.
- Verified the focused Healing suite (`111 passed`), Damage mutation
  regressions (`92 passed`), the full suite (`1008 passed`), and configured
  mypy (`Success: no issues found in 80 source files`).
- This Group 3 slice adds no generic mutation abstraction, EventStore,
  `state_changes`, transaction/replay/concurrency mechanism, StateStore or
  StateSnapshot schema change, state schema-version change, or dependency; it
  does not update the canonical G6B architecture/decision documentation.

## 2026-08-28 — G6B Group 4 canonical contract and abstraction review

- Reviewed the committed Damage and Healing Commands, resolvers/results,
  Events, Creature appliers, handlers, and tests as two concrete authoritative
  HP mutation consumers; no production Python changed in this group.
- Compared ten candidates explicitly: shared current-HP transition,
  replacement-Creature and snapshot helpers, stale-state/integrity helper,
  generic Event applier and mutation handler, `WorkingState`,
  `UnitOfWork`/`TransactionManager`, `ResolutionResult.state_changes`, and
  `EventApplierRegistry`/generic reducer.
- Recorded the overall verdict `KEEP CONCRETE`: Damage and Healing retain
  different gameplay formulas, Healing additionally depends on authoritative
  `max_hp`/`maxHp`, the remaining overlap is mostly syntax/sequencing, no third
  mutation consumer exists, and the proposed indirection removes little or no
  current complexity.
- Added canonical §3.20, "Minimal Healing → HP mutation vertical slice
  (G6B)", including exact Command/Result/Event/applier/handler contracts,
  source-agnostic amount semantics, zero-HP/full-HP behavior, persistence and
  failure ordering, no-op replay limitation, and the detailed abstraction
  matrix; synchronized §3.18, §3.19, quick lookup, and table of contents.
- Appended DEC-0034 with the G6B rationale and post-G6B abstraction decision,
  and synchronized the deliberately duplicated implemented/deferred summary
  in `CLAUDE.md`.
- Left broad Roadmap `HP`, `Damage`, and `Healing` checkboxes unchanged and
  introduced no EventStore, `state_changes`, transaction/replay framework,
  schema/version change, production dependency, or generic mutation helper.
- Verified all architecture tests (`7 passed`), including documentation
  references, and checked the new §3.20 heading against its quick-lookup/TOC
  anchor.

## 2026-08-28 — G6B Group 5 documentation/status synchronization

- Committed and pushed the separately reviewed Group 4 canonical-contract
  changes as `ff68523c042912cbc4f469d4fd3eeb68d79a19b4` before starting this
  documentation-only group.
- Synchronized Phase 2 status in `docs/ROADMAP.md`, the project overview in
  `README.md`, and `AI_DND_DATA_FLOW_CURRENT.md` with the implemented minimal
  `ApplyDamageCommand` and `ApplyHealingCommand` mutation paths. The current
  persisted authority remains the replacement `StateSnapshot` saved through
  `StateStore`; runtime EventStore, durable Event history, and replay remain
  deferred.
- Confirmed that the Group 4 `CLAUDE.md` summary already names G6B §3.20,
  `HealingApplied` V1, the Healing mutation path, full-HP no-op semantics, the
  post-G6B `KEEP CONCRETE` verdict, and the remaining deferred abstractions;
  no additional Group 5 edit was needed there.
- Intentionally left the broad Roadmap `HP`, `Damage`, and `Healing`
  checkboxes open: the direct slices do not implement healing
  sources/resources, spells/items/potions, temporary HP,
  death/unconscious/death saves, broader HP lifecycle, Attack → Damage,
  resistance/immunity/vulnerability, or Conditions.
- Verified on Python 3.12.13 / pytest 9.1.1: the six-file narrow Healing suite
  passed (`111 passed`), the six-file Damage mutation regression suite passed
  (`92 passed`), and the full suite passed (`1008 passed`) with pip cache
  disabled for the isolated wheel-build tests. The configured mypy check
  passed (`Success: no issues found in 80 source files`).
- Introduced no production Python change, dependency, State schema/version
  change, EventStore, runtime `events.jsonl` artifact, `state_changes` field,
  generic mutation framework, or direct AI/API State mutation.

## 2026-08-28 — G6C Group 1: Condition State foundation

- Branched `feat/g6c-conditions-foundation` from `origin/main` at
  `0dbe090745e8f58d41ea075e14d0871eab9a8723` (the merged G6B tip, DEC-0034).
- Added a closed, identity-only Domain `StrEnum` `Condition` with exactly one
  member, `POISONED = "poisoned"`
  (`src/dnd_engine/domain/value_objects/condition.py`), following the
  existing `DamageType`/`Skill` pattern; no other 5e Condition was added.
- Added `CreatureState.conditions: frozenset[Condition] = frozenset()` with
  strict `__post_init__` validation (`type(...) is frozenset`, every member
  an actual `Condition`, no coercion from `list`/`set`/`tuple`/
  `frozenset[str]`/raw strings), mirroring
  `CharacterState.saving_throw_proficiencies`/`skill_proficiencies`. The
  empty default preserves every existing `CreatureState(...)` call site;
  `current_hp`/`max_hp` invariants are unchanged.
- Bumped `StateSerializer` to schema V4 as the current writer: added explicit
  `LEGACY_SCHEMA_V3_VERSION = 3`, a V4-only `conditions` Creature field
  (strict JSON list of known, non-duplicate `Condition` values, sorted by
  `Condition.value`, always emitted including `[]`), and kept V1–V3 Creature
  decoding forbidding `conditions` and always producing
  `CreatureState.conditions == frozenset()`.
- Closed a concrete regression found while implementing the bump: Character
  `skillProficiencies` decoding was gated by `schema_version == SCHEMA_VERSION`,
  which would have silently stopped V3 payloads from decoding their Character
  projection once `SCHEMA_VERSION` became `4`. Changed the gate to
  `schema_version != LEGACY_SCHEMA_V2_VERSION` so V3 and V4 both decode the
  unchanged Character schema; added a dedicated regression test asserting a
  realistic V3 payload with non-empty `skillProficiencies` still decodes that
  membership exactly under the V4 implementation, with
  `CreatureState.conditions == frozenset()`.
- Review of Group 1 found the identical trap reintroduced one level down: the
  new V4 Creature field set and `conditions` decoding were both gated by
  `schema_version == SCHEMA_VERSION`, so a future `SCHEMA_VERSION` bump would
  have silently misread already-persisted V4 Creature payloads as pre-V4 and
  rejected their `conditions` field as unknown. Fixed by introducing a
  separate fixed constant `SCHEMA_V4_VERSION = 4` (`SCHEMA_VERSION =
  SCHEMA_V4_VERSION`); the supported-schema-version set, the V4 Creature
  field set, and `conditions` decoding now all compare against
  `SCHEMA_V4_VERSION`, never against the mutable `SCHEMA_VERSION`, which
  remains only the "current writer" pointer used when serializing. Added
  `test_v4_creature_shape_is_fixed_and_survives_future_schema_version_bump`,
  which monkeypatches `SCHEMA_VERSION` to a hypothetical future value and
  asserts a historical V4 payload with `conditions` still decodes exactly —
  this test fails against the pre-fix code. Updated §3.21/§12.9 and DEC-0035
  in place (not yet committed) to describe the fixed-identity design instead
  of the original comparison-against-`SCHEMA_VERSION` description.
- `StateSnapshot`'s top-level shape (`campaign`/`creatures`/`characters`) is
  unchanged; no `StateSnapshot.conditions` field or `ConditionState` aggregate
  was added. No Apply/Remove Command, Event, Application handler, or
  `Poisoned` gameplay effect was implemented — those remain later G6C groups.
- Documented the slice as new canonical §3.21 in `docs/ARCHITECTURE.md`,
  including the explicit clarification that `condition_NNN` (§4.12/§4.13)
  remains reserved for a possible future stateful Condition-instance model
  and is not allocated by this membership set; synchronized §3.2.1, §12.9,
  and §12.12. Appended DEC-0035 with the full rationale. Updated `CLAUDE.md`'s
  Phase 2 summary, current-phase bullet list, serialization schema-version
  fact, and naming-traps table to match.
- Left broad Roadmap `[ ] Conditions` unchecked; `README.md` required no edit
  (it had no stale schema-version or Creature-field text), and
  `AI_DND_DATA_FLOW_CURRENT.md`'s `schemaVersion: 3` example/summary row were
  updated to V4 with `conditions` in the example payload, since that text
  would otherwise become factually stale.
- Verified on Python 3.12.13 / pytest 9.1.1: the narrow five-file Condition
  suite passed (`184 passed`), the full suite passed (`1062 passed`), and the
  configured mypy check passed (`Success: no issues found in 81 source
  files`). `git diff --check` reported no whitespace errors. Manually
  confirmed the new regression test fails against the pre-fix code (reverting
  the two `SCHEMA_V4_VERSION` decode-gate comparisons back to `SCHEMA_VERSION`
  reproduces `ValueError: unknown creature fields: ['conditions']`), then
  restored the fix.
- Introduced no Apply/Remove Command, Event, handler, `Poisoned` behavior,
  Effect framework, `ConditionState`/`ConditionDefinition` hierarchy,
  `condition_instance_id`, runtime `condition_NNN` allocation, new production
  dependency, or `StateSnapshot` shape change.

## 2026-08-28 — G6C Group 2: Apply/Remove Domain mutation

- Committed and pushed the reviewed Group 1 State foundation (including the
  `SCHEMA_V4_VERSION` fixed-identity fix) as
  `00dd4ef19d3af231322a9bba55d69516381f4f7d` on
  `feat/g6c-conditions-foundation`; confirmed `origin/main` had not advanced
  past the branch's base SHA before committing.
- Added `ApplyConditionCommand`/`ApplyConditionPayload`
  (`src/dnd_engine/domain/commands/apply_condition.py`) and
  `RemoveConditionCommand`/`RemoveConditionPayload`
  (`.../remove_condition.py`), each an immutable Command Envelope with
  payload `(target_id: str, condition: Condition)` and no `source`/
  `duration`/`save_dc`/`spell_id`/`item_id`/`feature_id`/`stacks`/
  `condition_instance_id`, matching the existing `ApplyDamageCommand`/
  `ApplyHealingCommand` shape.
- Added two concrete result types, `ConditionApplicationResult`/
  `ConditionRemovalResult` (`domain/rules/apply_condition.py`/
  `remove_condition.py`), each `(target_id, condition, previous_active,
  active)`; `active` is intrinsically fixed by each type's own
  `__post_init__` (`True` for Application, `False` for Removal — a Result
  with the opposite endpoint cannot be constructed). Pure resolvers
  `resolve_condition_application`/`resolve_condition_removal` compute
  `previous_active = condition in target.conditions`, perform no mutation/
  I/O/dice/Definition lookup, and use the same target-identity correlation
  check as `resolve_damage`/`resolve_healing`. Confirmed and tested that
  applying an already-active Condition, or removing an already-absent one,
  is an explicit successful no-op, not `RULE_VIOLATION`.
- Added `ConditionApplied`/`ConditionRemoved` V1 Events
  (`domain/events/apply_condition.py`/`remove_condition.py`) with payload
  exactly `{targetId, condition, previousActive, active}`;
  `build_condition_applied_v1`/`build_condition_removed_v1` check Command/
  outcome correlation and copy the resolved result verbatim, matching
  `build_damage_applied_v1`/`build_healing_applied_v1`. Confirmed the no-op
  case still produces a complete Event (never short-circuited).
- Added concrete Creature appliers `apply_condition_applied_v1`/
  `apply_condition_removed_v1`, following the existing `apply_damage_applied_v1`/
  `apply_healing_applied_v1` integrity-check shape (exact Event type/
  version/payload keys, decoded `targetId`/`condition`/`previousActive`/
  `active`, `targetId == creature.id`, and the Condition-specific
  `previousActive == (condition in creature.conditions)` check — a mismatch
  raises `ValueError`, not a gameplay `EngineError`) before projecting
  `conditions | {condition}` (Apply) or `conditions - {condition}` (Remove)
  through `dataclasses.replace`; only `conditions` changes. Demonstrated and
  documented, mirroring G6A/G6B, that a canonical no-op Event can be
  re-applied to a Creature whose membership already matches without being
  detected as a duplicate — not fixed via revision/CAS/EventStore here.
- No Application handler, `StateStore.save()` call, or gameplay effect was
  implemented — those remain Group 3 (persistence) and Group 4 (`Poisoned`).
- Extended canonical §3.21 in `docs/ARCHITECTURE.md` in place (Commands,
  Results/resolvers, successful no-op semantics, Events, concrete Creature
  appliers, replay/no-op limitation, updated Explicit exclusions/Abstraction
  discipline) rather than adding a new section, since this is still the
  same G6C1 State-and-mutation-foundation slice. Appended DEC-0036 with the
  full rationale. Updated `CLAUDE.md`'s G6C1 bullet and the deferred-
  abstractions paragraph to name the new concrete Condition appliers.
- Left broad Roadmap `[ ] Conditions` unchecked.
- Verified on Python 3.12.13 / pytest 9.1.1: the new eight-file Group 2
  domain suite passed (`148 passed`), the full suite passed
  (`1210 passed`), and the configured mypy check passed (`Success: no
  issues found in 87 source files`). `git diff --check` reported no
  whitespace errors.
- Introduced no `ApplyConditionHandler`/`RemoveConditionHandler`,
  `StateStore.save()` flow, filesystem integration, `Poisoned` d20 effect,
  `RollMode` condition rules, `ModifierPipeline`, Effect framework, generic
  Event applier, generic mutation handler, snapshot replacement helper,
  `EventStore`, `UnitOfWork`, `WorkingState`, `state_changes`, or new
  production dependency.

## 2026-08-28 — G6C Group 3: Application handlers + authoritative persistence

- Committed and pushed the reviewed Group 2 Domain mutation contract as
  `732faecd6e1297d91202e01bc97bfef19ec53571` on `feat/g6c-conditions-foundation`;
  confirmed local and `origin/feat/g6c-conditions-foundation` already matched
  exactly (nothing new to commit) before starting Group 3 edits.
- Added `ApplyConditionHandler`/`RemoveConditionHandler`
  (`src/dnd_engine/application/handlers/apply_condition.py`/
  `remove_condition.py`), each depending only on `StateStore` and
  `EventMetadataProvider` (no `DiceEngine`/`DefinitionSource`), following the
  exact `DamageHandler`/`HealingHandler` lifecycle (§3.19, §3.20):
  `StateStore.load` → actor lookup → target lookup → pure resolver →
  `EventMetadataProvider.next_metadata` → concrete Condition Event → concrete
  Creature applier → replacement `creatures` tuple (order preserved) →
  replacement `StateSnapshot` (`campaign`/`characters` reused unchanged) →
  `StateStore.save()` exactly once on the success path → successful
  `ResolutionResult`.
- Actor/target lookup policy matches the proven Damage/Healing convention
  exactly: missing actor → `ErrorCode.ENTITY_NOT_FOUND`, `entity_id=actor_id`,
  `field=None`; missing target → `ErrorCode.ENTITY_NOT_FOUND`,
  `entity_id=payload.target_id`, `field="target_id"`; both return before
  `next_metadata`/`save()` are reached. Self-targeting is permitted.
  Documented this explicitly in §3.21 as a direct-internal-slice policy, not
  a promise about actor semantics for any future Condition source.
- Confirmed and tested that Apply-already-active and Remove-already-absent
  are never short-circuited: both still run the full lifecycle (resolver →
  Event → applier → replacement snapshot → exactly one `save()`) and return a
  successful `ResolutionResult`.
- Did not extract a shared `replace_creature`/snapshot-replacement helper,
  even though the same inline construction is now duplicated across
  `DamageHandler`, `HealingHandler`, `ApplyConditionHandler`, and
  `RemoveConditionHandler` — a deliberate evidence checkpoint left for a
  later, separately evidenced abstraction-review group, per the task's
  explicit instruction not to extract in this group. No `EventStore` or
  `events.jsonl` write was introduced; persisted `state.json` remains the
  sole authoritative artifact.
- Added `tests/application/test_apply_condition_handler.py` and
  `test_remove_condition_handler.py` (10 tests each), covering: successful
  lifecycle + persistence with ordering/identity assertions; successful
  no-op (already-active / already-absent) still completing the full
  lifecycle and calling `save()` once; missing actor / missing target
  (`ENTITY_NOT_FOUND`, no metadata call, no save); resolver failure (raises,
  call order stays exactly `["load"]`, no metadata call, no save);
  Event-builder failure (raises, call order stays exactly
  `["load", "metadata"]`, no save); applier/invariant failure (raises, no
  save); `EventMetadataProvider` failure (raises, no save); and
  `StateStore.save()` failure (propagates, attempted exactly once, no
  successful result, original loaded Creature/snapshot left unchanged). The
  resolver-failure and Event-builder-failure cases were added after review
  flagged that the initial pass only covered applier/metadata/save failure,
  leaving two links in the six-link failure chain (§3.21's Application
  handlers subsection: resolver / Event-builder / applier / metadata / save,
  each independently, since no shared handler abstraction exists to cover
  them once) unproven; each handler got its own focused pair rather than a
  shared parameterized cross-handler test helper.
- Added `tests/integration/test_apply_condition_real_adapters.py` and
  `test_remove_condition_real_adapters.py`, each driving the corresponding
  handler against a real `FilesystemStateStore`, asserting the persisted
  bytes changed, the raw JSON `conditions` array matches, a *fresh*
  `FilesystemStateStore` instance reloads the expected membership, unrelated
  creatures/characters are untouched, `save()` was called exactly once, and
  no `events.jsonl`/temp artifacts are left behind. Added
  `tests/integration/test_condition_lifecycle_real_adapters.py` as the
  explicit end-to-end proof requested for this group: Apply `POISONED` →
  save → fresh reload → present, then Remove `POISONED` → save → fresh
  reload → absent, each step through its own fresh `FilesystemStateStore`
  instance.
- Added `tests/infrastructure/test_state_store.py::
  test_load_accepts_legacy_v3_with_empty_conditions` as an additional real-
  filesystem-adapter regression proof for the legacy V3→V4 `conditions`
  migration (§12.9), since the existing real-store test file only exercised
  legacy V1/V2 end-to-end; the isolated `StateSerializer` unit tests already
  covered V1/V2/V3 thoroughly, so no further serializer-level tests were
  added.
- No Application handler, `StateStore.save()` call, or gameplay effect
  remained outstanding for G6C1's mutation path after this group — only the
  `Poisoned` gameplay effect (a separate, later G6C group) is still
  unimplemented.
- Extended canonical §3.21 in `docs/ARCHITECTURE.md` in place (updated
  Implementation status, Scope, Explicit exclusions; added a new
  "Application handlers and persistence" subsection covering the lifecycle,
  actor/target policy, replacement-State construction, persistence,
  no-op-not-short-circuited behavior, failure semantics, and the production
  integration proof; extended Replay/no-op limitation and Abstraction
  discipline) rather than adding a new section. Updated `CLAUDE.md`'s G6C1
  bullet and the deferred-abstractions paragraph to describe the new
  handlers and the intentionally-not-yet-extracted shared duplication.
  `README.md` required no edit (no stale implemented-flow summary to fix).
  Left broad Roadmap `[ ] Conditions` unchecked.
- Verified on Python 3.12.13 / pytest 9.1.1: the new 24-test Group 3 suite
  (2 handler files + 3 integration files + 1 legacy-migration regression
  test) passed (`24 passed`), the full suite passed (`1234 passed`), and the
  configured mypy check passed (`Success: no issues found in 89 source
  files`). `git diff --check` reported no whitespace errors. (A pre-existing,
  ACL-locked `%TEMP%\pytest-of-redbu` directory unrelated to this branch's
  changes caused spurious `PermissionError` collection failures under the
  default `tmp_path` base; resolved for verification by passing pytest a
  fresh `--basetemp`, not by modifying any test or fixture.)
- Introduced no generic `MutationHandler`, `EventApplierRegistry`,
  `ConditionMutation` base class, `WorkingState`, `UnitOfWork`,
  `TransactionManager`, `state_changes`, `EventStore`, or new production
  dependency. Did not commit or push Group 3; per-task instruction, it stays
  uncommitted pending review, captured in a fresh `review.patch`.

## 2026-08-29 — G6C Group 4 / G6C2: minimal Poisoned roll behavior

- Verified the reviewed Group 3 diff as the isolated commit after Group 2,
  confirmed `git diff --check` clean, explicitly pushed the branch
  (`Everything up-to-date`), and confirmed the tracked worktree clean before
  starting G6C2. Group 3 SHA:
  `564698db214508c31340b6007d23926072d855de`.
- Added two narrow pure Domain policies in
  `domain.rules.condition_roll_mode`: one derives Ability Check roll mode from
  Condition membership and one derives Attack Roll mode. Both return
  `DISADVANTAGE` for `Condition.POISONED` and `NORMAL` otherwise. No generic
  Condition-to-mode mapping or roll-mode combiner was added.
- Wired `AbilityCheckHandler` and `SkillCheckHandler` to the shared
  ability-check Condition policy, and `AttackHandler` to the attack-roll
  policy after its existing actor/Character/target/Definition lookups. The
  unchanged resolvers still receive effective keyword-only `roll_mode` and
  call `resolve_d20_roll()`. Attack reads attacker Conditions, not target
  Conditions. `SavingThrowHandler` was not changed.
- Added handler proofs using scripted `17, 6` rolls for poisoned Ability,
  Skill, and Attack consumers: each performs exactly two independent
  `dice.roll("1d20")` calls, records ordered `(17, 6)`, selects `6`, and writes
  the same `DISADVANTAGE` D20Roll in its final Event. Added an Attack negative
  proof that a poisoned target does not disadvantage an unpoisoned attacker.
- Added the required production Saving Throw negative proof: a poisoned actor
  follows the real handler path, remains `RollMode.NORMAL`, performs exactly
  one `dice.roll("1d20")`, and records that one-roll D20Roll in
  `SavingThrowResolved`.
- Added a real `FilesystemStateStore` lifecycle proof: persist initially
  unpoisoned actor -> Apply `POISONED` -> fresh later AbilityCheckHandler load
  with two-roll disadvantage -> Remove `POISONED` -> fresh later
  AbilityCheckHandler load with one-roll NORMAL. This proves authoritative
  mutation persistence drives later read-only rule behavior.
- Added canonical §3.22 and DEC-0037, updated the G6C status text in Roadmap
  and the reproduced facts in `CLAUDE.md`. Broad `[ ] Conditions`, Attack,
  Skills, and Proficiency statuses remain unchanged. README required no edit.
- Focused Domain/handler/persistence test checkpoint passed: `54 passed` on
  Python 3.12.13 / pytest 9.1.1. Full-suite and configured-check results are
  recorded after final verification below.
- Final verification passed: full pytest `1248 passed`; configured mypy
  `Success: no issues found in 90 source files`. The full suite used a fresh
  basetemp and pip cache outside the checkout so its installed-wheel fixture
  could build offline without recursively copying the repository-local temp
  directory or writing to the sandbox-blocked default pip cache. No formatter
  or linter is configured in `pyproject.toml`.
- Introduced no other Condition, poison damage, duration/source, immunity,
  save-to-remove behavior, generic Effects, modifier pipeline, advantage/
  disadvantage source framework, pairwise RollMode combiner, EventStore,
  UnitOfWork, or snapshot helper extraction.

## 2026-08-29 — G6C Group 4 review correction: persisted pre-Apply baseline

- Extended the existing real `FilesystemStateStore` lifecycle test before
  any mutation: after persisting an initially unpoisoned Creature, a fresh
  `AbilityCheckHandler` with its own new `FilesystemStateStore` instance now
  loads the empty Condition membership, performs exactly one
  `dice.roll("1d20")`, and records a NORMAL `D20Roll` with the exact scripted
  roll in both the outcome and final Event payload.
- The same test then continues through the already-covered Apply `POISONED`
  -> fresh two-roll DISADVANTAGE check -> Remove `POISONED` -> fresh one-roll
  NORMAL check. No production code, Domain policy contract, handler wiring,
  canonical behavior contract, or Group 5 scope changed in this review
  correction.
- Review verification passed on Python 3.12.13 / pytest 9.1.1: the corrected
  integration test passed (`1 passed`), the focused Group 4 suite remained
  `54 passed`, the full suite remained `1248 passed`, and configured mypy
  remained clean (`Success: no issues found in 90 source files`). Test counts
  are unchanged because the baseline was added inside the existing integration
  test rather than as a new test function.

## 2026-08-29 — G6C Group 5: evidence-based post-G6C abstraction review

- Verified the reviewed and pushed Group 4 as isolated commit
  `a62b9c4649c0f21cce163779df496ef4d034a342`, with branch HEAD matching the
  remote and a clean tracked worktree before Group 5 edits.
- Compared `DamageHandler`, `HealingHandler`, `ApplyConditionHandler`, and
  `RemoveConditionHandler`. All four duplicated the same complete
  owner/Application snapshot policy: replace one Creature by stable ID,
  preserve tuple order, reuse Campaign and Character projections, and leave
  the loaded snapshot untouched. Extracted only
  `replace_creature_in_snapshot()` under Application services. It requires
  exactly one existing matching ID, raises rather than silently appending a
  missing target, and preserves the exact characters tuple identity.
- Migrated the four mutation handlers to the helper without changing their
  resolver, Event, applier, error, metadata, persistence, or result contracts.
  Added focused helper proofs for order/projection identity/copy-on-write,
  missing-ID failure, and boundary types; the existing four handler suites
  provide regression coverage. Focused verification: `38 passed`.
- Compared the four concrete Event appliers and retained `KEEP CONCRETE`:
  Damage, Healing, and Condition payload decoding/correlation policies differ,
  and no serialized replay/dispatch consumer exists. Generic mutation-handler
  orchestration also stays concrete because it would require callbacks,
  generics, error factories, or policy hooks. Ability/Attack Condition policies
  remain narrow; Skill reuse and Saving Throw exclusion are unchanged.
- Canonized the review in §3.23 and DEC-0038, updated current §3.19–§3.22
  references, `CLAUDE.md`, the now-stale README flow text, and
  `AI_DND_DATA_FLOW_CURRENT.md`. Broad Roadmap `Conditions` and all other broad
  mechanic statuses remain unchanged.
- Full verification passed on Python 3.12.13 / pytest 9.1.1: `1251 passed`,
  covering legacy V1–V3 reads, V4 Conditions, mutation/no-op persistence,
  Poisoned positive/negative consumers, later NORMAL restoration, Damage,
  Healing, and all previous read-only mechanics. Configured mypy passed:
  `Success: no issues found in 91 source files`. No formatter or linter is
  configured.
- Introduced no generic Event applier/registry/reducer, mutation handler,
  `ConditionEffectRegistry`, Effect Engine, `ModifierPipeline`, `RollContext`,
  `has_condition`, pairwise RollMode combiner, `WorkingState`, `UnitOfWork`,
  `TransactionManager`, `MutationContext`, `state_changes`, EventStore,
  revision/CAS, runtime Condition entity/source/duration/stacking, production
  dependency, or AI/API/UI State mutation path. Group 5 remains uncommitted
  and unpushed pending review.

## 2026-08-29 — G6C Group 5 review correction: current data-flow sync

- Updated only documentation after review; the approved snapshot helper, four
  handlers, helper tests, Event appliers, and Condition policies were not
  changed.
- Replaced the stale G6B branch/commit header and Damage/Healing-only mutation
  descriptions in `AI_DND_DATA_FLOW_CURRENT.md`. The current flow now records
  all four mutation handlers and concrete Events/appliers, replacement
  Creature → §3.23 Application helper → replacement snapshot → exactly one
  successful-path `StateStore.save()`, plus the helper's explicit non-gameplay,
  non-owner, non-persistence, non-reducer boundary. EventStore/replay remain
  deferred.
- Synchronized §3.19 Damage and §3.20 Healing lifecycle prose with the §3.23
  helper without changing their gameplay, Event, no-op, ordering, or
  persistence guarantees. Corrected DEC-0038's affected Architecture range to
  §§3.19–3.23 and included the Current Data Flow document.
- Documentation reference tests passed (`2 passed`). Full pytest and mypy were
  intentionally not repeated because no Python code or tests changed. Group 5
  remains uncommitted and unpushed pending final re-review.

## 2026-08-29 — G6C Group 5 final re-review: stale wording cleanup

- Updated documentation only. §3.18 now describes Damage/Healing as the first
  two production mutation consumers at the historical post-G6B checkpoint and
  records that G6C later added Apply/Remove Condition while §3.23 supersedes
  only the snapshot-helper verdict.
- Replaced §3.21's stale inline present-tense snapshot construction with the
  current concrete Condition applier → replacement Creature → §3.23 helper →
  replacement snapshot → save flow, retaining the original inline form only
  as historical evidence context. Updated the top `CLAUDE.md` Foundation
  summary to call Damage/Healing the first two HP-mutation consumers rather
  than the current total.
- Production code and tests were unchanged. Documentation reference tests
  passed (`2 passed`); full pytest/mypy were not repeated. Group 5 remains
  uncommitted and unpushed pending review.

## 2026-08-30 — Phase 2 closure and deferred-scope ledger

- Added `docs/DEFERRED.md` as a companion subordinate to Architecture and
  Roadmap, not as an alternative contract or status/order source. It records
  eleven stable `P2-*` closure notes and stable `DEF-0001` through `DEF-0022`
  entries with lifecycle policy, provenance, targets, planned approaches,
  acceptance criteria, references, and dated history.
- Kept Skill and Ability explicit, placed default Skill-to-Ability suggestion
  under future command generation/adjudication, grouped all weapon
  proficiency/Finesse/range/reach/ammunition work under DEF-0011, preserved
  DEC-0037's independent-source-first RollMode rule, and placed legacy Ability
  Check V1 cleanup only under durable Event history/replay DEF-0022.
- Added the ledger to the README, CLAUDE, and AGENTS document maps and to local
  Markdown link/anchor validation. No canonical Architecture, Roadmap, or
  Decision contract and no gameplay production Python was changed.
- Verification on Python 3.12.13 / pytest 9.1.1: focused documentation
  references `2 passed`; full suite `1251 passed` (with one non-failing pytest
  cache warning caused by the managed environment); configured mypy
  `Success: no issues found in 91 source files`.

## 2026-08-30 — Phase 2 canonical foundation closure

- Verified the next canonical identifiers as Architecture §3.24 and DEC-0039.
  Corrected §3.8 from planned-only mutation wording and §3.18 from two to four
  concrete mutation consumers, then added the Phase 2 Closure Contract:
  reusable deterministic foundation readiness closes Phase 2 without claiming
  full D&D mechanic coverage or weakening evidence-driven abstraction.
- Appended Accepted DEC-0039 and rewrote Roadmap Phase 2 as eleven completed,
  scope-accurate foundation items. Every incomplete broader mechanic is marked
  `broader scope PARTIAL` with forward P2/DEF links; Phase 3–6 and the compact
  cross-cutting tracks provide reverse continuation links. Event History &
  Replay remains trigger-driven and is not a Phase 3 entry gate.
- Synchronized README, CLAUDE, the current data-flow document, and the Deferred
  companion: Phase 2 Basic Rules is complete in foundation scope and Phase 3
  Combat is current. No gameplay mechanic, production Python, test contract,
  EventStore/replay, generic Effect/mutation/transaction abstraction, or
  zero-HP/life-state rule was added.
- Verification on Python 3.12.13 / pytest 9.1.1: focused documentation
  references `2 passed`; full suite `1251 passed` (with one non-failing pytest
  cache warning caused by the managed environment); configured mypy
  `Success: no issues found in 91 source files`.

## 2026-08-30 — First Phase 3 Combat consumer: Initiative/Turn Order (G7)

- Confirmed Roadmap already names Phase 3 — Combat current (Phase 2 closed via
  DEC-0039), re-read Architecture §10.7 Combat State Owner, §3.18 State
  Mutation Foundation, §3.8 Atomicity, and the four existing concrete
  mutation consumers (§§3.19–3.21) before designing this slice.
- Added a new minimal State Owner, `CombatState(id, round, order,
  active_index)`, and exactly one new optional `StateSnapshot.combat:
  CombatState | None = None` field (default `None`; every existing snapshot
  construction site is unaffected).
- Implemented `StartCombatCommand(combat_id, participant_ids)`: a pure
  `resolve_start_combat` rolls one `1d20` per participant via the existing
  `resolve_d20_roll`/`RollMode.NORMAL` plus each participant's Dexterity
  modifier, sorts by descending total → descending Dexterity → ascending
  creature id for full determinism, and produces `CombatStarted` V1 plus a
  freshly constructed `CombatState` at `round=1`. `StartCombatHandler` rejects
  starting combat while one is already in progress (`RULE_VIOLATION`) and
  reports a missing participant as `ENTITY_NOT_FOUND`.
- Implemented `AdvanceTurnCommand(combat_id)`: a pure `resolve_advance_turn`
  advances `active_index` modulo `len(order)` and increments `round` only on
  wraparound, producing `TurnAdvanced` V1 and a replacement `CombatState`.
  `AdvanceTurnHandler` requires `command.actor_id ==
  combat.active_creature_id` before resolving (`ACTION_NOT_AVAILABLE`
  otherwise) — this actor-ownership gate is the concrete Combat
  actor/action-eligibility consumer this slice exists to deliver.
  `current_hp` is deliberately not consulted, leaving DEF-0015's zero-HP
  eligibility question exactly as open as before. `AttackHandler`/`AttackCommand`
  (§3.17) were not touched.
- Both handlers attach/replace `StateSnapshot.combat` with the stdlib
  `dataclasses.replace(snapshot, combat=...)` directly; the existing §3.23
  `replace_creature_in_snapshot` helper does not apply to a single optional
  field, and no new helper or transaction abstraction was extracted or
  introduced.
- Bumped State schema to exact integer `schemaVersion = 5`
  (`SCHEMA_V5_VERSION`, following the same fixed-sentinel-vs-mutable-
  `SCHEMA_VERSION` discipline DEC-0035 established for V4): V5 adds exactly
  one required top-level `state.combat` key (`null`, or an object with `id`/
  `round`/`order`/`activeIndex`); V1–V4 payloads keep their existing field
  sets with no `combat` key and always decode to `combat=None`.
- Added new Architecture §3.25, Decision DEC-0040, and Roadmap Phase 3
  `Initiative`/`Turns` foundation-complete status with a forward note on the
  still-open `Zero-HP and combatant eligibility` item; synchronized CLAUDE.md
  and the current data-flow document's schema-version mentions.
- Added deterministic Domain tests (`CombatState`, the two Commands, the two
  resolvers, the two Events/appliers), Application handler tests with spy
  `StateStore`/`DiceEngine`/`EventMetadataProvider` doubles, an integration
  test exercising both handlers through the real `FilesystemStateStore` and
  `PythonDiceEngine` with fresh reloads between steps, and State-serializer/
  State-store V5 persistence and legacy-V1–V4-compatibility coverage.
- Verification on Python 3.12.9 / pytest 9.1.1: full suite `1376 passed`;
  configured mypy `Success: no issues found in 100 source files`. The sandboxed
  test environment's default `%TEMP%\pytest-of-<user>` directory raised a
  pre-existing `PermissionError` unrelated to this change (reproduces on
  unmodified `main`); all pytest runs used an explicit `--basetemp` pointed at
  a writable scratch directory as a workaround, not a code or configuration
  change.

## 2026-08-30 — G7 correction pass: actor validation, Poisoned Initiative, ID-origin wording

- Narrow review-correction pass on the still-uncommitted G7 Initiative/Turn
  Order/`CombatState` slice; the overall design (separate `CombatEngine`-owned
  `CombatState`, optional snapshot-level `combat`, State schema V5 with V1–V4
  legacy reads, `StartCombat`/`CombatStarted` V1, `AdvanceTurn`/`TurnAdvanced`
  V1, concrete Event application, direct `dataclasses.replace(snapshot,
  combat=...)`, no generic pipeline/EventStore/UnitOfWork/TransactionManager/
  WorkingState/LifeState/effects framework) is unchanged.
- `StartCombatHandler` now validates `command.actor_id` against authoritative
  `snapshot.creatures` immediately after loading State, before participant
  resolution, any `DiceEngine` call, any `EventMetadataProvider` call, or
  persistence — matching the actor-first order already used by every other
  handler. A missing actor returns `ENTITY_NOT_FOUND` (`entity_id=actor_id`,
  `field=None`) with `outcome=None`, `events=()`, and no dice/metadata/save
  calls. The actor is not required to also be a participant.
- Corrected Initiative semantics: SRD 5.1 Initiative is a Dexterity check, so
  the already-implemented `ability_check_roll_mode_from_conditions` (§3.22)
  policy now applies. `StartCombatHandler` derives one effective `RollMode`
  per participant from authoritative `CreatureState.conditions` and passes
  the aligned `tuple[RollMode, ...]` into a new required keyword-only
  `resolve_start_combat(..., roll_modes=...)` parameter; the resolver keeps
  owning the Dexterity modifier, `resolve_d20_roll` calls, totals, and
  deterministic ordering. No generic Condition framework, `combine_roll_modes`,
  or DEF-0021 aggregation was introduced — Poisoned is still the only
  production roll-mode source.
- Corrected Architecture wording for `StartCombatPayload.combat_id`: it is
  documented as an already-allocated runtime Combat ID produced through the
  canonical §4.11 `EntityFactory` boundary before Command construction, not
  as a caller-invented value. §4.11 itself is unchanged; this slice still does
  not implement a concrete `EntityFactory`, and fixed literal combat IDs in
  tests are fixtures standing in for an already-allocated ID.
- Made Roadmap Phase 3 scope-accurate: `Initiative` and `Turns` are now
  `Initiative foundation` and `Turn-order advancement foundation`, with new
  explicit open rows for SRD 5.1 grouped initiative for identical
  GM-controlled creatures (not implemented; this is the base grouped-roll
  rule itself, not the paragraph's separate optional tie-break method), turn/
  action economy and turn resources, and Combat lifecycle/`CombatEnded`.
  `Zero-HP and combatant eligibility` remains open and untouched; no
  `LifeState` or Death Saves were introduced.
- Strengthened the duplicate-creature-ID invariant at every layer that could
  let one slip through: `StartCombatPayload.participant_ids` already rejected
  duplicate input IDs; `StartCombatResult` now also rejects a duplicate
  creature ID in its own resolved aggregate `order`; `CombatState` already
  enforced the same invariant at construction; and the State serializer's
  `_validate_combat` now re-validates it again before writing V5, because
  `CombatState` is a mutable dataclass and could have been mutated after
  construction. `InitiativeEntry` itself carries no duplicate-ID
  responsibility.
- Updated Architecture §3.25, DEC-0040 (in place — this slice remains
  entirely uncommitted, so no accepted historical record was rewritten),
  CLAUDE.md, and README.md (distinguishing the four Creature-mutation
  handlers using the §3.23 helper from the two G7 Combat handlers using
  direct `dataclasses.replace`, and noting G7 is already implemented rather
  than purely future Phase 3 work).
- Added Domain resolver coverage for normal/Poisoned/mixed participant sets
  (dice-call counts, recorded `RollMode`, both rolls, selected lower roll,
  preserved call order) and a duplicate-order rejection test; Application
  handler coverage for the missing-actor failure path (call order, error
  shape), actor-not-a-participant, and Poisoned-participant wiring through
  the real Condition policy; a State-serializer regression test for a
  mutated duplicate `CombatState.order`.

## 2026-08-30 — First Monster attacker / Character target: Goblin Scimitar (G8)

- Added the first concrete Phase 3 Monster-as-attacker and Character-as-target
  Attack consumer, gated on two design/gate reports reviewed and corrected in
  conversation before any production code: an initial proposal to unblock
  DEF-0013 via a caller-supplied `weapon_definition_id` on a new
  `WeaponAttackCommand` was rejected (a Definition ID is not an authoritative
  ownership fact, and DEF-0011's own prerequisites name a real
  Equipment/Inventory source, weapon proficiency, and an explicit Finesse
  choice); a full correct Weapon-attack prerequisite was found to need two new
  State Owners and two `CharacterState`/`AttackPayload` extensions and was
  compared against a Monster-attack alternative that needs none, because a
  Monster's attack is fully self-contained in its Definition.
- Added `MonsterAttackDefinition` (`domain/definitions/monster_attack.py`):
  `action_id, name, attack_bonus, damage_dice, damage_modifier, damage_type`,
  intrinsically validated (`action_id` non-empty `str`, `damage_dice` via the
  shared `parse_ndm()`, `damage_type` an actual `DamageType`). It is a narrow
  attack-specific contract, not a generic Monster action/ability model, and
  not a `Definition` subtype — `action_id` is a local identity scoped to the
  owning `MonsterDefinition`, not a runtime `action_NNN` or a global registry
  entry. `MonsterDefinition` gains `attacks: tuple[MonsterAttackDefinition,
  ...] = ()`, validating only tuple/element-type and unique-`action_id`
  invariants that are not already the nested type's own responsibility.
- Packaged the SRD 5.1 Goblin Scimitar (`+4` to hit, `1d6 + 2` slashing) as
  the sole `goblin.attacks` entry; the Goblin's Shortbow is intentionally not
  packaged (no range/reach fields exist on this contract yet), and
  `goblin.version` stays `1` (no Definition-version-aware lookup exists to
  interact with; this is the project's minimal representation of already-
  published SRD content catching up to a new contract field, not a rule
  change). `infrastructure/definitions/packaged.py` gained strict `attacks`
  list decoding with its own exact per-attack field-set check, mirroring the
  existing `_decode_weapon`/`_decode_monster` strictness.
- Added `resolve_monster_attack`/`MonsterAttackResult`
  (`domain/rules/monster_attack.py`) as a separate concrete type from
  `AttackResult`, not a variant of it: a flat stat-block `attack_bonus` is
  never decomposed into a fabricated `ability`/`ability_modifier`/
  `proficiency_bonus` split. Natural-1/20 automatic miss/hit/critical and the
  `total >= target_armor_class` comparison reuse the same Attack-owned
  semantics as the unarmed slice, written again rather than shared — two
  concrete consumers do not by themselves justify extracting a natural-
  outcome helper under the existing evidence-driven abstraction policy.
- Added `MonsterAttackResolved` V1 (`domain/events/monster_attack.py`):
  `targetId, actionId, roll, attackBonus, total, targetArmorClass, hit,
  criticalHit`. This is a new Event type, not an `AttackResolved` V2, because
  the field set is conceptually different rather than a roll-representation
  change (the same reasoning that already keeps `SkillCheckResolved`/
  `SavingThrowResolved`/`AbilityCheckResolved` separate). `AttackResolved` V1
  is completely untouched. The Event carries no damage fields, amount, or
  `previousHp`/`newHp`: it records the attack roll only; Damage resolution is
  explicit future DEF-0013 scope.
- `AttackCommand`/`AttackPayload(target_id)` are completely unchanged — still
  one explicit Attack intent, per DEF-0011's own "Planned approach" wording.
  `AttackHandler` gained one new branch keyed on data it already loads: an
  actor with a matching `CharacterState` projection takes the existing
  unarmed path unchanged; an actor without one — previously an unconditional
  `INVALID_STATE` failure — now takes a new Monster-actor path requiring
  exactly one supported `MonsterAttackDefinition`
  (`ACTION_NOT_AVAILABLE`, not `INVALID_STATE`, for zero or multiple — no
  silent `attacks[0]` fallback, no dice rolled, no Event built), requiring the
  target to have a `CharacterState` projection (`INVALID_TARGET` otherwise),
  computing target AC via the unchanged `unarmored_character_armor_class`,
  and deriving `RollMode` via the unchanged `attack_roll_mode_from_conditions`
  (Poisoned reuse, no duplicated Condition logic). `AttackHandler.handle()`'s
  return type becomes `ResolutionResult[AttackResult | MonsterAttackResult]`.
  No `CombatState`/active-turn check and no `current_hp` eligibility check
  were added — both remain exactly as open as before this slice.
- Updated Architecture (new §3.26), added DEC-0041, updated Roadmap Phase 3
  with a scope-accurate `Monster → Character attack-roll foundation` row
  (broad `Monster actions` and `Weapon attacks` remain open), and updated
  DEF-0011/DEF-0012/DEF-0013 in `docs/DEFERRED.md` with dated History entries
  recording this partial foundation without redefining their titles, status,
  or acceptance criteria — all three stay `Deferred` for their remaining
  scope. `CLAUDE.md` resynced.
- Added focused tests: `MonsterAttackDefinition`/`MonsterDefinition.attacks`
  invariants (empty default, tuple/element-type checks, duplicate `action_id`
  rejection); `resolve_monster_attack`/`MonsterAttackResult` (ordinary hit/
  miss, natural 1/20 automatic outcomes independent of `attack_bonus`,
  advantage/disadvantage roll-mode reuse, actor-id-mismatch and wrong-type
  rejection, no ability/proficiency decomposition); `MonsterAttackResolved`
  V1 payload/builder invariants and JSON serialization; packaged-decoder
  strictness for `attacks` (missing key, non-list, malformed/unknown-field/
  wrong-primitive-type per-attack elements, duplicate `action_id`); real
  packaged-Goblin production decode assertions; `AttackHandler` Monster-actor
  branch coverage (hit/miss/critical, Poisoned disadvantage, actor Definition
  lookup failures, zero/multiple supported attacks with no dice/metadata
  calls, missing target, target without `CharacterState`); a real
  `FilesystemStateStore`/`PackagedDefinitionSource`/`PythonDiceEngine` round
  trip for a Goblin Scimitar attack against a Character target; and an
  updated regression test for the previously-unconditional
  actor-has-no-`CharacterState` failure, now correctly routing to the new
  Monster-actor path. Full `pytest` (1517 tests) and configured `mypy`
  (`src/dnd_engine`) pass; `git diff --check` reports no whitespace errors.

## 2026-08-30 — CombatState-safe Creature snapshot replacement (G9 Group 1)

- Replaced the manual three-field `StateSnapshot` reconstruction in
  `replace_creature_in_snapshot` with `dataclasses.replace`, changing only the
  `creatures` tuple while preserving every unrelated snapshot projection by
  identity, including an existing `CombatState`.
- Kept the existing boundary validation, exactly-one matching-ID requirement,
  tuple ordering, missing-ID rejection, and copy-on-write behavior unchanged.
- Added direct helper and `DamageHandler` regressions proving that Creature HP
  mutation preserves the original Combat projection and leaves the loaded
  snapshot unchanged.
- Updated Architecture §3.23 and related current summaries to describe the
  projection-preservation contract without changing historical DEC-0038 or
  introducing G9 attack-damage orchestration.
- Verification: focused `test_state_snapshot_service.py` (3 tests) and
  `test_damage_handler.py` (8 tests), full pytest (1538 tests), configured
  mypy (103 source files), and `git diff --check` all pass.
