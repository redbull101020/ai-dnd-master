# Architecture Decision Log

This append-only log records rationale and history. `ARCHITECTURE.md = current canonical contract`; `DECISIONS.md = append-only rationale/history` and does not override it.

## DEC-0001 — Event → Command correlation

- **Date:** 2026-08-20
- **Status:** Accepted
- **Context:** Event causality alone did not link all results of one logical Command transaction.
- **Decision:** Every domain Event has mandatory `commandId`. All Events from one Command share it, including cascading Events. System actions enter the authoritative pipeline through a system/internal Command. Canonical envelope: `eventId`, `commandId`, `type`, `version`, `campaignId`, `timestamp`, `actorId`, `causedBy`, `payload`.
- **Consequences:** tracing, replay, and audit can reconstruct a Command transaction; `causedBy` remains Event → Event causality.
- **Affected contracts/files:** `docs/ARCHITECTURE.md` §§8–9.

## DEC-0002 — Runtime IDs do not depend on Definition IDs

- **Date:** 2026-08-20
- **Status:** Accepted
- **Context:** Definition-derived runtime IDs blur immutable content and campaign State.
- **Decision:** Use generic runtime prefixes: `character_NNN`, `player_NNN`, `npc_NNN`, `monster_NNN`, `item_NNN`, `combat_NNN`, `quest_NNN`, `objective_NNN`, `location_NNN`, `effect_NNN`, `condition_NNN`, `command_NNNNNN`, `event_NNNNNN`. Store Definition separately, e.g. `monster_001` with `definitionId: goblin`. Player identity and CharacterState remain distinct.
- **Consequences:** Definitions may retain semantic IDs such as `goblin`, `fighter`, and `longsword`; runtime identity stays stable.
- **Affected contracts/files:** `docs/ARCHITECTURE.md` §4.

## DEC-0003 — Game time belongs to World State

- **Date:** 2026-08-20
- **Status:** Accepted
- **Context:** Campaign ownership of global game time created two logical owners.
- **Decision:** `WorldEngine / WorldState` is the sole authoritative owner of world/game time. Campaign ownership covers identity, ruleset reference, metadata, and session/lifecycle metadata. Event system timestamps are separate.
- **Consequences:** one State has one logical owner.
- **Affected contracts/files:** `docs/ARCHITECTURE.md` §10.

## DEC-0004 — Pydantic only at boundaries

- **Date:** 2026-08-20
- **Status:** Accepted
- **Context:** Domain contracts needed a framework-independent model.
- **Decision:** Domain uses dataclasses, frozen dataclasses for Definitions and immutable Value Objects, Enums, Value Objects, and type hints. Pydantic is restricted to API, storage I/O validation, configuration, external JSON, and LLM structured output.
- **Consequences:** rule resolution has no Pydantic dependency.
- **Affected contracts/files:** `docs/ARCHITECTURE.md` §§1.2, 12.7.

## DEC-0005 — Phase 0 includes minimal CI

- **Date:** 2026-08-20
- **Status:** Accepted
- **Context:** Foundation must be technically verifiable.
- **Decision:** GitHub Actions uses Python 3.12, `python -m pip install -e ".[dev]"`, and `python -m pytest` on push and pull requests.
- **Consequences:** no lint, type, format, or coverage tools are introduced.
- **Affected contracts/files:** `.github/workflows/tests.yml`, `docs/ROADMAP.md`.

## DEC-0006 — JSON placeholder policy

- **Date:** 2026-08-20
- **Status:** Accepted
- **Context:** zero-byte JSON files are neither data nor valid JSON artifacts.
- **Decision:** A tracked `.json` must be non-empty valid JSON; otherwise it is not created. Empty directories use `.gitkeep`. An empty `events.jsonl` is allowed as a valid empty append-only stream.
- **Consequences:** repository tests validate all JSON artifacts under `rules/` and `campaigns/`.
- **Affected contracts/files:** `rules/`, `campaigns/`, `tests/test_json_artifacts.py`.

## DEC-0007 — README separates current and planned state

- **Date:** 2026-08-20
- **Status:** Accepted
- **Context:** README implied a runnable API and installed dependencies that do not yet exist.
- **Decision:** README lists Python 3.12+, JSON/JSONL, pytest, and setuptools as current Foundation; FastAPI, WebSocket, Pydantic v2, and LLM adapters are planned boundary stack.
- **Consequences:** planned dependencies wait for their Roadmap phase.
- **Affected contracts/files:** `README.md`, `docs/ROADMAP.md`.

## DEC-0008 — Phase 1 starts with minimal Core data contracts

- **Date:** 2026-08-22
- **Status:** Accepted
- **Context:** Phase 1 needed canonical first-pass Value Object, Definition, and Creature State shapes before Python implementation, including one unambiguous HP field name.
- **Decision:** `AbilityScores` is an immutable six-score Value Object whose required values are each in `1..30`. `CreatureState` uses `current_hp` / `max_hp` in Python (`currentHp` / `maxHp` in JSON). `ItemDefinition`, `WeaponDefinition`, and `MonsterDefinition` contain only their documented minimal Phase 1 fields, and `WeaponDefinition` is a specialization of `ItemDefinition`. Runtime State remains separate from immutable Definitions.
- **Consequences:** fields belonging to later Roadmap phases are intentionally absent; future slices can extend the canonical contracts only when the corresponding behavior is implemented.
- **Affected contracts/files:** `docs/ARCHITECTURE.md` §§1.2.1, 3.1.1, 3.2.1.

## DEC-0009 — DamageType is a closed Domain StrEnum

- **Date:** 2026-08-22
- **Status:** Accepted
- **Context:** DEC-0008 and the initial Phase 1 `WeaponDefinition` contract deferred the exact `damage_type` Domain type and closed set until code implementation.
- **Decision:** `DamageType` is a Domain `StrEnum` with exactly 13 lowercase string values: `acid`, `bludgeoning`, `cold`, `fire`, `force`, `lightning`, `necrotic`, `piercing`, `poison`, `psychic`, `radiant`, `slashing`, and `thunder`. `WeaponDefinition.damage_type` uses `DamageType`, and future serialization emits the enum string value.
- **Consequences:** weapon definitions cannot extend the canonical damage-type vocabulary with arbitrary enum members. This decision introduces no resistance, immunity, vulnerability, or damage-calculation mechanics; those remain deferred to their corresponding future Roadmap phases.
- **Affected contracts/files:** `docs/ARCHITECTURE.md` §§3.1.1, 12.16; `src/dnd_engine/domain/value_objects/damage_type.py`; `src/dnd_engine/domain/definitions/weapon.py`.

## DEC-0010 — Minimal Phase 1 CampaignState contract

- **Date:** 2026-08-22
- **Status:** Accepted
- **Context:** Phase 1 reached `CampaignState`. Architecture already assigned Campaign ownership but did not define a concrete minimal Python schema, leaving room for the implementation to become an implicit aggregate or God Object for other State domains.
- **Decision:** Phase 1 `CampaignState` is mutable and contains exactly `id: str`, `ruleset_id: str`, and `ruleset_version: str`. Other State domains are not embedded in it. World/game time remains exclusively in World State. Concrete fields for campaign metadata, session state, and lifecycle are deferred until corresponding use cases and contracts exist.
- **Consequences:** Campaign State remains small while exposing campaign identity and an explicit ruleset identity/version reference. State Ownership boundaries remain intact. A persistence snapshot may aggregate State domains separately without transferring their ownership to `CampaignState`. Future extensions require a concrete use case and canonical contract update.
- **Affected contracts/files:** `docs/ARCHITECTURE.md` §3.2.2; `src/dnd_engine/domain/state/campaign.py`.

## DEC-0011 — Minimal Phase 1 Dice Engine contract

- **Date:** 2026-08-22
- **Status:** Accepted
- **Context:** Phase 1 reached Dice Engine. Architecture already required all gameplay randomness to pass through `DiceEngine` and showed `roll("1d20")`, but the exact Domain API, result type, minimal parsing ownership, and RNG injection contract were not canonical.
- **Decision:** `DiceEngine` is a Domain `Protocol` with `roll(expression: str) -> DiceRoll`. Immutable `DiceRoll` contains the accepted `expression`, individual `rolls`, and their `total`. Phase 1 accepts strict simple lowercase `NdM` only; modifiers and a full DSL are deferred. Parsing remains private to the Infrastructure implementation. Production `PythonDiceEngine` receives an injected `random.Random`; Domain does not depend on Python RNG implementation or Infrastructure. RNG internal state is not authoritative campaign State.
- **Consequences:** Rules can receive deterministic scripted `DiceEngine` implementations, production randomness remains replaceable, and equivalent controlled RNG sources can reproduce sequences. Individual rolls remain available for debugging and future resolution/replay work. No Phase 2 rules or replay subsystem are introduced.
- **Affected contracts/files:** `docs/ARCHITECTURE.md` §1.7.1; `src/dnd_engine/domain/services/dice.py`; `src/dnd_engine/domain/value_objects/dice_roll.py`; `src/dnd_engine/infrastructure/random/dice.py`.

## DEC-0012 — Minimal Phase 1 Event model contract

- **Date:** 2026-08-23
- **Status:** Accepted
- **Context:** Phase 1 reached the Event model. The canonical Event Envelope already defined identity, Command correlation, campaign scope, causation, naming, and schema-version semantics, but its Domain timestamp representation, payload immutability, nullable-field codec behavior, and the boundary included in this slice required clarification.
- **Decision:** Phase 1 uses one generic immutable `GameEvent`; no separate Python `EventEnvelope` type is introduced. Its timestamp is an explicitly supplied timezone-aware UTC `datetime`, serialized as ISO 8601 UTC with canonical `Z`. Its generic JSON-compatible payload is defensively and recursively immutable. `actorId` and `causedBy` are always emitted and serialize Domain `None` as JSON `null`; missing or null input deserializes to `None`. A pure `EventSerializer` is included in this slice.
- **Consequences:** Event values cannot read the clock, allocate their identity, mutate State, or be changed through nested payload references. EventStore, Event ID/sequence allocation, filesystem persistence, State application, replay, and concrete gameplay Event types remain deferred.
- **Affected contracts/files:** `docs/ARCHITECTURE.md` §§3.4, 8.7–8.10, 12.10, 12.17; `src/dnd_engine/domain/events/game_event.py`; `src/dnd_engine/infrastructure/persistence/json/event_serializer.py`.

## DEC-0013 — Minimal Phase 1 State Store contract

- **Date:** 2026-08-24
- **Status:** Accepted
- **Context:** Phase 1 reached State Store. The canonical architecture required versioned State snapshots but did not yet define the minimal persistence aggregate, strict v1 codec, filesystem error boundary, or atomic replacement behavior without prematurely coupling snapshot persistence to the future EventStore.
- **Decision:** `StateStore` is a snapshot-only Domain port with `load(campaign_id)` and `save(snapshot)`. Frozen `StateSnapshot` groups one `CampaignState` and `tuple[CreatureState, ...]` for persistence without becoming a State Owner or transferring Creature ownership to Campaign. Pure `StateSerializer` maps that aggregate to the exact camelCase Phase 1 `state.json` structure with integer `schemaVersion = 1`, outer `campaignId`, nested Campaign fields, and a deterministically ID-sorted Creature array. Deserialization is strict: all fields are required, unknown fields/defaults/coercion are forbidden, the campaign IDs must match, and nested Domain invariants and unique Creature IDs are enforced. `FilesystemStateStore` uses UTF-8 deterministic JSON at `<root>/<campaign_id>/state.json` and atomically replaces the single file using a same-directory temporary file plus `os.replace` under a Phase 1 single-writer assumption. `schemaVersion` is not a State revision.
- **Consequences:** State snapshot persistence remains separate from gameplay rules and Event persistence. EventStore, replay, Event-to-State application, transaction ordering between EventStore and State projection, revisions/locking, migrations, and database implementations remain deferred. No production dependency is added.
- **Affected contracts/files:** `docs/ARCHITECTURE.md` §§3.2.3, 12.9, 12.12; `src/dnd_engine/domain/state/snapshot.py`; `src/dnd_engine/domain/services/state_store.py`; `src/dnd_engine/infrastructure/persistence/json/state_serializer.py`; `src/dnd_engine/infrastructure/filesystem/state_store.py`.

## DEC-0014 — Phase 1 closure and minimal Phase 2 resolution foundation

- **Date:** 2026-08-24
- **Status:** Accepted
- **Context:** All Phase 1 Roadmap items were implemented and tested, while README/Roadmap status still named Phase 1 as current. Before the first Phase 2 vertical slice, the canonical JSON Command Envelope, future Python Command representation, `ResolutionResult.success`, `state_changes`, expected errors, Ability identifiers, resolver/application responsibilities, and orchestration scope required an unambiguous boundary.
- **Decision:** Phase 1 implementation is complete and the repository moves to Phase 2 — Basic Rules without marking any Phase 2 mechanic complete. The canonical five-field Command Envelope is retained. Validated gameplay Python Commands will be concrete typed immutable dataclasses with concrete typed payloads and fixed command types, not a generic dict-based Domain Command hierarchy; the first planned forms are `AbilityCheckCommand` and `AbilityCheckPayload`. The future immutable generic `ResolutionResult[T]` contains exactly `success`, `command_id`, `outcome`, tuple `rolls`, tuple `events`, and tuple `errors`; `success` means processing/rule-resolution success, not gameplay success. No `state_changes` field or placeholder `StateChange` abstraction is materialized before a concrete state-mutating use case; authoritative mutation remains Event-driven. Expected processing failures use the planned minimal `ErrorCode` / immutable `EngineError` representation, while intrinsic invalid construction may use `TypeError`/`ValueError` and infrastructure/programming failures are not automatically gameplay errors. `Ability` is a planned closed lowercase `StrEnum`; ability modifier is the pure derived rule `(score - 10) // 2`, not stored in `AbilityScores` or State. The Ability Check resolver is stateless, receives a typed Command, `CreatureState`, and `DiceEngine`, performs one `1d20` roll, and does not load/save State or create Event metadata. State lookup and actor validation belong to Application. Ability Check is read-only, so its handler loads State but does not save it. After successful resolution Application creates the planned `AbilityCheckResolved` generic `GameEvent`, with gameplay success/failure in payload. `GameEngine`, `GameContext`, EventStore, buses, registries, dispatcher, transaction coordinator, replay, and broader orchestration framework remain deferred until multiple concrete use cases demonstrate shared behavior.
- **Consequences:** The first Phase 2 implementation can be a narrow explicit Application handler plus pure Domain resolver without accepting untyped gameplay payloads or prematurely designing a framework. A failed check can have `ResolutionResult.success is True` and `outcome.succeeded is False`; a processing failure has no outcome or Events and contains structured errors. Phase 1 contracts and runtime behavior remain unchanged.
- **Affected contracts/files:** `README.md`; `CLAUDE.md`; `docs/ARCHITECTURE.md` §§2.2–2.3, 2.6, 3.3, 3.5–3.10, 9.6; `docs/ROADMAP.md`; `docs/DECISIONS.md`; `docs/DEVELOPMENT_LOG.md`.

## DEC-0015 — Single canonical Command lifecycle

- **Date:** 2026-08-24
- **Status:** Accepted
- **Context:** The canonical architecture described the Command lifecycle twice with two incompatible state vocabularies. §3.3 used `Created → Validating → Valid | Invalid → Executing → Completed | Failed`, while §9.7 used `Created → Validating → Rejected | Accepted → Resolving → Completed | Failed`. `CLAUDE.md` reproduced a third variant whose initial state `Received` appeared in neither. No Command is implemented, so no code, test, or persisted data depended on either vocabulary.
- **Decision:** §9.7 is the single canonical description of the Command lifecycle, with the states `Created`, `Validating`, `Rejected`, `Accepted`, `Resolving`, `Completed`, and `Failed`. The `Valid` / `Invalid` / `Executing` vocabulary is rejected. The lifecycle is documented in exactly one section: §3.3 no longer restates it and links to §9.7 instead.
- **Consequences:** The two descriptions can no longer drift apart, because only one of them exists. `Rejected` stays aligned with the rejection reasons listed in §9.7 and with `ErrorCode` in §3.9. No Python contract, implementation, test, or runtime behavior changes. `CLAUDE.md` still carries the stale third variant and is corrected in a separate slice.
- **Affected contracts/files:** `docs/ARCHITECTURE.md` §§3.3, 9.7; `docs/DECISIONS.md`.

## DEC-0016 — CLAUDE.md duplication policy

- **Date:** 2026-08-24
- **Status:** Accepted
- **Context:** `CLAUDE.md` is loaded automatically by the coding agent while `docs/ARCHITECTURE.md` is not, so the summary had grown verbatim copies of canonical structures: the full ID reference table, the full State Ownership matrix, both Envelope JSON examples, and Definition field lists. DEC-0015 had just removed a duplicated Command lifecycle for exactly this reason, and `CLAUDE.md` still carried a third, invented lifecycle vocabulary whose initial state `Received` existed nowhere in the canon. At the same time the summary omitted every implemented Phase 1 contract, the phase-scope rule, the deferred-abstraction list of §3.6, the mandatory `docs/DEVELOPMENT_LOG.md` append rule, the document map, and branch/PR policy. Without a stated rule for what the summary may repeat, every future edit re-opens the question and the file drifts again.
- **Decision:** `CLAUDE.md` reproduces verbatim only single facts that an agent can violate without noticing: names, closed value sets, phase status, and prohibitions. Structures — reference tables, dataclass field lists, and JSON envelope examples — are not reproduced; `CLAUDE.md` names the entity and points to its canonical section instead. A dedicated naming-trap section enumerates the specific points where an agent's default intuition diverges from the canon. `CLAUDE.md` is a summary for the agent and never an alternative contract: on any conflict with `docs/ARCHITECTURE.md`, including one introduced by a task instruction, the agent stops and reports instead of choosing.
- **Consequences:** Canonical structures have exactly one location, so a later change to §4.13, §10.13, §8.1, §9.1, or a Phase 1 field list no longer requires a matching edit in `CLAUDE.md`. The agent must open `docs/ARCHITECTURE.md` to obtain field lists and envelope schemas; the summary alone is not sufficient for contract-level work. The stale `Received` lifecycle variant left open by DEC-0015 is removed. This decision changes no Python contract, no test, and no runtime behavior.
- **Affected contracts/files:** `CLAUDE.md`; `docs/DECISIONS.md`.

## DEC-0017 — Campaign ID uses the strict numeric format

- **Date:** 2026-08-24
- **Status:** Accepted
- **Context:** `campaignId` is a required field of both the Command and Event Envelope and, per §12.9, is also the campaign directory name, yet the §4.13 ID Reference Table listed every entity except Campaign. §4.12 registered the instance `campaign_001` but no section stated the format, and §4.2 does not list Campaign among its examples of the generic instance pattern. Because §4.12 explicitly permits semantic IDs for Quest and Location, the absence of any statement for Campaign left semantic campaign IDs such as `curse_of_strahd` neither allowed nor forbidden, and `CLAUDE.md` directed the agent to §4.13 for all ID formats.
- **Decision:** Campaign ID uses the strict numeric instance format `campaign_NNN`, consistent with the generic pattern in §4.2. Semantic Campaign IDs are forbidden. The prohibition is stated in §4.12 alongside the registered instance, and the format is listed in §4.13 as a row placed after Definition and before Character, first among the runtime IDs. A human-readable campaign title is not encoded in the identifier.
- **Consequences:** `campaignId` is now validatable by a single pattern everywhere it appears — both Envelopes, the state snapshot, and the campaign directory name — and remains stable when a campaign is renamed, as §4.9 requires of every ID. The cost is that campaign directories are not self-describing on disk; a human-readable title belongs in state rather than in the identifier. §4.2 still omits Campaign from its example list, §4.10 states no uniqueness scope for Campaign, and §4.11 assigns no service that generates Campaign IDs; these gaps are recorded here and left open. This decision changes no Python contract, no test, and no runtime behavior.
- **Affected contracts/files:** `docs/ARCHITECTURE.md` §4.12, §4.13; `docs/DECISIONS.md`.

## DEC-0018 — CLAUDE.md is resynchronised whenever the canon changes

- **Date:** 2026-08-24
- **Status:** Accepted
- **Context:** DEC-0016 fixed which canonical facts `CLAUDE.md` reproduces and which it replaces with a section reference, but it assigned no obligation to reread the summary when the canon changes. `CLAUDE.md` originally drifted for exactly that reason: nobody owned it, and the agent read `AGENTS.md` instead. Two parts of the rebuilt summary remain exposed, the table of implemented Phase 1 contracts and the naming-traps table, because both restate facts that a future contract change could invalidate silently. Separately, `AGENTS.md` stated the commit, push, pull request, and merge authorisation rules twice, in "Branches and pull requests" and again in "Change authorisation and diff review", which is the same duplication hazard inside the process document.
- **Decision:** `AGENTS.md` now requires rereading `CLAUDE.md` after any canonical contract change and updating it within the same slice if a reproduced fact changed, and names the classes of fact the summary reproduces so the check is actionable. Authorisation for commit, push, pull request creation, and merge is stated only in "Change authorisation and diff review"; "Branches and pull requests" keeps branch hygiene and pull request description requirements and carries a cross-reference instead of a restatement.
- **Consequences:** DEC-0016 is complete: the summary now has both a defined content policy and a defined maintenance trigger. Contract slices cost slightly more, since each one must check the summary even when it turns out to be unaffected. The check is manual and nothing enforces it; if it is skipped, drift returns silently, which is the failure this decision is meant to make visible rather than impossible. This decision changes no Python contract, no test, and no runtime behavior.
- **Affected contracts/files:** `AGENTS.md`; `docs/DECISIONS.md`.

## DEC-0019 — Ability Check result and Event metadata boundaries

- **Date:** 2026-08-24
- **Status:** Accepted
- **Context:** DEC-0014 prepared the first Phase 2 Ability Check slice, but its planned `ResolutionResult[T]` duplicated each roll at the generic result level, the Application responsibility to create a `GameEvent` conflicted with Event ID allocation being assigned to the deferred EventStore, and the concrete `AbilityCheckResolved` payload/builder contract was not fixed.
- **Decision:** Application handlers obtain `EventMetadata` from one injected application-facing `EventMetadataProvider`; handlers neither allocate Event IDs nor read the system clock directly, and UI/AI/API are not authoritative metadata sources. The provider is not an EventStore and provides no durability guarantee. The future immutable `ResolutionResult[T]` contains exactly `success`, `command_id`, `outcome`, tuple `events`, and tuple `errors`; generic top-level `rolls` is removed. A successful result has a non-null outcome and no errors. A failed result has no outcome or Events and at least one error. Every returned Event has the result's `command_id`; successful results are not generically required to contain an Event. Gameplay failure remains successful processing. The generic immutable `GameEvent` envelope is retained without a concrete Event hierarchy, registry, upcasters, or EventBus. `AbilityCheckResolved` uses `type="AbilityCheckResolved"`, `version=1`, the typed `AbilityCheckResolvedPayloadV1`, and a dedicated `build_ability_check_resolved_v1(...)` builder that receives Event ID/timestamp, derives envelope correlation/scope/actor from the Command, uses `caused_by=None`, derives payload from the single resolver outcome, and performs no clock, ID, or persistence work. EventStore remains deferred and remains the future authoritative durable allocator of Event sequence/ID.
- **Consequences:** The immediate typed outcome and durable Event payload may both represent the same roll without a third generic copy. The first read-only handler has a deterministic metadata seam while making no durability claim and without prematurely implementing EventStore. This decision supersedes only DEC-0014's exact `ResolutionResult[T]` field list containing `rolls` and clarifies DEC-0014's statement that Application creates Event metadata; all other DEC-0014 provisions remain historical and authoritative where not superseded.
- **Affected contracts/files:** `docs/ARCHITECTURE.md` §§2.2, 3.5, 3.10; `CLAUDE.md`; `docs/ROADMAP.md`; `docs/DECISIONS.md`.

## DEC-0020 — Runtime validation is split by invariant ownership

- **Date:** 2026-08-26
- **Status:** Accepted
- **Context:** Strict State/Event deserializers and several Domain Value Objects already validate runtime data, but the canon did not state a general ownership rule. That gap could be read either as requiring transport-shape checks in every dataclass or as allowing Domain constructors to accept semantically impossible objects whenever a serializer was strict.
- **Decision:** Untrusted boundaries strictly validate required/unknown fields, exact runtime types, schema/version, applicable formats, and references when dereferenced, without silent coercion unless a concrete boundary contract permits it. Domain Value Objects own their intrinsic invariants; State and Definitions own semantic in-memory invariants but do not duplicate JSON/document-shape validation. Validation is added for a concrete invariant, not for symmetry with adjacent dataclasses. Typed Domain constructors do not coerce strings, collections, or enums; normalization belongs to boundary mappers/loaders.
- **Consequences:** Boundary and Domain validation remain complementary rather than interchangeable. Existing serializers and intrinsic Value Object checks fit the policy. This decision does not claim that every existing State/Definition invariant is already enforced and does not trigger a mass `__post_init__` retrofit; missing concrete invariants remain work for their owning slices.
- **Affected contracts/files:** `docs/ARCHITECTURE.md` §12.25; `CLAUDE.md`; `docs/DECISIONS.md`.

## DEC-0021 — Proficiency begins as a pure character-level rule

- **Date:** 2026-08-26
- **Status:** Accepted
- **Context:** Phase 2 reached Proficiency, while the intentionally minimal Phase 1 State contracts contain neither character level nor proficiency membership and the implemented Ability Check remains a raw `d20 + ability modifier` vertical slice.
- **Decision:** The first Proficiency slice is the pure Domain rule `character_proficiency_bonus(level)`. It accepts exact integer total character levels `1..20` and returns the canonical bonus progression `+2..+6`. The derived bonus is not stored in `CreatureState`; State snapshot schema and Ability Check remain unchanged. Monster proficiency by Challenge Rating is outside this function. Authoritative character-level representation and proficiency membership for skills, saving throws, attacks, tools, and other mechanics remain deferred, as do Expertise, half/double proficiency and stacking rules.
- **Consequences:** The character proficiency progression can be tested independently without prematurely introducing a Character progression model or coupling Proficiency to Skills, Saving Throws, persistence, or the existing raw Ability Check slice. The overall Roadmap item remains incomplete until the concrete proficiency mechanics are implemented.
- **Affected contracts/files:** `docs/ARCHITECTURE.md` §3.11; `CLAUDE.md`; `src/dnd_engine/domain/rules/proficiency.py`; `tests/domain/test_proficiency.py`.

## DEC-0022 — Canonical d20 selection semantics

- **Date:** 2026-08-26
- **Status:** Accepted
- **Context:** `DiceRoll.total = sum(rolls)` correctly represents one dice expression but cannot represent effective d20 selection for advantage/disadvantage. The existing Ability Check used `DiceRoll.total`, so a shared d20 primitive was required before Saving Throws and Attack Rolls without changing the Phase 1 dice-expression contract.
- **Decision:** Add the closed `RollMode` enum and immutable `D20Roll(mode, rolls, selected)`, plus the concrete `resolve_d20_roll()` mechanic. NORMAL performs one independent `dice.roll("1d20")`; ADVANTAGE and DISADVANTAGE perform two independent `dice.roll("1d20")` calls and select the maximum or minimum respectively. `dice.roll("2d20")` is not used, and `DiceRoll` remains unchanged. Ability Check accepts a keyword-only effective `roll_mode` defaulting to NORMAL; roll mode is authoritative rule output, not Command, API, or AI input, and Ability Check total uses `D20Roll.selected`. `AbilityCheckResolved` V2 records mode, ordered raw rolls, and selected value and is the current writer. V1 remains an immutable legacy NORMAL-only schema and rejects advantage/disadvantage rather than losing a raw roll.
- **Consequences:** Future Saving Throws and Attack Rolls can reuse the same concrete d20 primitive while advantage sources and Conditions remain deferred. No generic modifier/check framework is introduced, `DiceRoll.total` retains its dice-expression meaning, and existing Event history is not rewritten.
- **Affected contracts/files:** `docs/ARCHITECTURE.md` §§3.10, 3.12, 12.10; `CLAUDE.md`; `src/dnd_engine/domain/value_objects/d20.py`; `src/dnd_engine/domain/rules/d20.py`; `src/dnd_engine/domain/rules/ability_check.py`; `src/dnd_engine/domain/events/ability_check.py`; `src/dnd_engine/application/handlers/ability_check.py`.

## DEC-0023 — Character proficiency prerequisites live in dedicated CharacterState

- **Date:** 2026-08-26
- **Status:** Accepted
- **Context:** `CreatureState` is the universal runtime projection for creature instances, while character proficiency bonus is already derived from total character level. Future Saving Throws require authoritative current character level and effective Saving Throw proficiency membership, but those character-only facts must not pollute universal `CreatureState`. The strict State snapshot V1 schema contains no character-specific collection.
- **Decision:** Add mutable `CharacterState` with exactly `id`, `total_level`, and `saving_throw_proficiencies`. Its ID identifies the same runtime character entity and must match an existing `CreatureState.id` in the same `StateSnapshot`; the two projections use composition, not inheritance. `total_level` is an exact integer in `1..20`, and Saving Throw membership is an actual `frozenset[Ability]` with no fixed count. Proficiency bonus remains derived and is not stored. Skill and other proficiency categories, proficiency provenance, class progression, and monster proficiency remain deferred. The current State schema becomes V2 with exact `campaign`, `creatures`, and `characters` state fields. The writer emits only V2; the reader accepts exact V2 and exact legacy V1, mapping V1 to `characters=()` without invented defaults. This supersedes only DEC-0013's current-schema V1 provisions and DEC-0021's deferral of authoritative character level and Saving Throw membership.
- **Consequences:** A future Saving Throw slice can obtain authoritative character inputs without a class system, Skill system, generic proficiency framework, or changes to `CreatureState`. Legacy V1 snapshots remain readable but acquire no inferred progression data; any subsequent save materializes V2. `CharacterState` remains under the existing Creature Domain owner and introduces no mutation use case, Event, or new State Owner in this slice.
- **Affected contracts/files:** `docs/ARCHITECTURE.md` §§3.2.3, 3.2.4, 3.11, 10.13, 12.9, 12.12, 12.13; `CLAUDE.md`; `src/dnd_engine/domain/state/character.py`; `src/dnd_engine/domain/state/snapshot.py`; `src/dnd_engine/infrastructure/persistence/json/state_serializer.py`.

## DEC-0024 — First Saving Throw vertical slice is character-specific

- **Date:** 2026-08-26
- **Status:** Accepted
- **Context:** The shared d20 primitive and character proficiency-bonus rule already existed, and `CharacterState` now held authoritative total level and effective Saving Throw proficiency membership. Saving Throw was the second concrete consumer of `ability_modifier`, but no universal monster/Creature proficiency source existed and the first complete Saving Throw flow still needed an explicit Command, resolver, result, Event, and Application handler boundary.
- **Decision:** Command and Event naming remain mechanic-level `SavingThrowCommand` / `SavingThrowResolved`, while the current concrete resolver is `resolve_character_saving_throw(...)` and receives matching `CreatureState` plus `CharacterState` projections. The pure `ability_modifier()` rule moves to shared `domain.rules.ability`; `domain.rules.ability_check` imports and re-exports that same function for compatibility. Saving Throw proficiency is applied only when the selected Ability belongs to `CharacterState.saving_throw_proficiencies`, and its bonus derives from `CharacterState.total_level`. The keyword-only `roll_mode` defaults to NORMAL and is not Command input. `SavingThrowResult` and `SavingThrowResolved` V1 record ability and proficiency contributions separately. The handler is read-only: it emits one Event after successful resolution and never saves State. Missing Creature is `ENTITY_NOT_FOUND`; an existing Creature without matching `CharacterState` is `INVALID_STATE`. Monster Saving Throws remain deferred.
- **Consequences:** Character Saving Throws can be resolved and audited end-to-end without storing derived proficiency bonus, inventing defaults for legacy snapshots, changing the State schema, or introducing a generic modifier/check framework. Gameplay failure remains successful command processing. Ability Check behavior and its public modifier import path remain compatible. The Roadmap Saving Throws item stays incomplete until at least the monster path and its authoritative proficiency source exist.
- **Affected contracts/files:** `docs/ARCHITECTURE.md` §§3.7, 3.11–3.13, 12.10; `CLAUDE.md`; `src/dnd_engine/domain/rules/ability.py`; `src/dnd_engine/domain/commands/saving_throw.py`; `src/dnd_engine/domain/rules/saving_throw.py`; `src/dnd_engine/domain/events/saving_throw.py`; `src/dnd_engine/application/handlers/saving_throw.py`.

## DEC-0025 — Skill identity and proficiency membership foundation

- **Date:** 2026-08-27
- **Status:** Accepted
- **Context:** `CharacterState` already held authoritative character level and Saving Throw proficiency membership, but the next Skills slice required canonical Skill identity and persisted effective Skill proficiency membership before introducing any Skill Check flow. Current State schema V2 could not represent that membership, while legacy V1/V2 snapshots had to remain readable without retroactively changing their wire contracts.
- **Decision:** `Skill` is a closed Domain `StrEnum` with exactly 18 canonical lowercase snake-case values. It represents identity only and does not encode a fixed associated Ability, so future rules can support alternative ability checks such as Strength (Intimidation). Extend `CharacterState` with an explicit required `skill_proficiencies: frozenset[Skill]` containing effective current membership; derived proficiency bonus remains unstored. Advance the current State schema to exact V3 by adding required `skillProficiencies` to each Character entry. The writer emits only V3 with deterministic Skill ordering. The reader retains exact V1 and V2 support: V1 maps to `characters=()`, while V2 Character entries map to `skill_proficiencies=frozenset()`. Expertise, half proficiency, Skill Check Command/resolver/Event/handler, and a generic proficiency framework remain deferred. This supersedes only DEC-0023's current-schema V2 provisions and its deferral of Skill proficiency membership.
- **Consequences:** Current snapshots persist authoritative Skill membership without storing modifiers or coupling Skill identity to Ability. Legacy snapshots remain readable and materialize as V3 on the next save. This foundation does not complete the broad Skills or Proficiency Roadmap items and introduces no Skill Check behavior, State Owner, Event, handler, framework, or dependency.
- **Affected contracts/files:** `docs/ARCHITECTURE.md` §§1.2.2, 3.2.4, 3.11, 12.9, 12.12–12.13; `CLAUDE.md`; `src/dnd_engine/domain/value_objects/skill.py`; `src/dnd_engine/domain/state/character.py`; `src/dnd_engine/infrastructure/persistence/json/state_serializer.py`.
