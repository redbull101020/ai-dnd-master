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
