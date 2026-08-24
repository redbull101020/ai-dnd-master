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
