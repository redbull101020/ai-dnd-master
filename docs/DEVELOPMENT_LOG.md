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
