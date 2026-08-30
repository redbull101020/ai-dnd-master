# Phase 2 Closure and Deferred Scope Register

This document is the detailed closure companion for Phase 2 and the register
for work deliberately left outside its implemented slices. It is subordinate
to [`ARCHITECTURE.md`](ARCHITECTURE.md) and
[`ROADMAP.md`](ROADMAP.md): Architecture remains the current canonical
contract, and Roadmap remains the source for status and implementation order.
[`DECISIONS.md`](DECISIONS.md) remains the append-only rationale/history log.
This file neither changes those roles nor makes a deferred design canonical.

The P2 notes below explain what the implemented foundations prove and why a
completed foundation can coexist with explicitly PARTIAL broader scope. The
DEF records are planning entries, not approved contracts or scheduling
commitments. A DEF `Target` identifies the likely continuation area; Roadmap
still controls when work starts.

## Register policy

- A DEF ID is stable, is never reused, and continues to identify the same
  concern after completion or supersession.
- `Origin` and `Created` are immutable.
- Allowed statuses are `Deferred`, `Ready`, `In progress`, `Blocked`, `Done`,
  and `Superseded`.
- A material change to `Status`, `Target`, `Prerequisites`, `Planned approach`,
  or `Acceptance criteria` requires a dated `History` entry explaining it.
- A DEF becoming `Ready` or `In progress` does not itself alter Roadmap order.
- A DEF becoming `Done` records delivery of that concern; canonical behavior
  still lives in Architecture and rationale still lives in Decisions.
- Links and proposed approaches in this register must be updated when their
  canonical prerequisites change. Historical Decision entries are not edited.

## Phase 2 closure notes

## P2-ABILITY-CHECKS

- **Implemented Phase 2 scope:** A read-only `AbilityCheckCommand` flow loads
  the actor, resolves `d20 + ability modifier` against an explicit DC, emits
  current `AbilityCheckResolved` V2 with a `D20Roll`, and returns a typed
  result. Poisoned supplies the first authoritative disadvantage source.
- **Closure assessment:** This is sufficient for the checked Phase 2 Ability
  Checks foundation: intent, deterministic resolution, audit Event, handler,
  and Condition-driven effective roll mode are proven end to end. It is not a
  complete modifier/effect, durable-history, or multi-source roll system.
- **Broader unimplemented scope:** Independent advantage/disadvantage source
  aggregation and durable decoding/history remain open. Legacy
  `AbilityCheckResolvedPayloadV1` cleanup has no standalone DEF; it belongs to
  [DEF-0022](#def-0022) when durable event reading creates a real migration or
  removal trigger.
- **Motivation:** Preserve a small, tested check mechanic without inventing a
  generic check or Event migration framework before a consumer needs one.
- **Continuation:** [DEF-0021](#def-0021) and [DEF-0022](#def-0022).
- **References:** [Architecture §3.10](ARCHITECTURE.md#310-minimal-phase-2-ability-check-vertical-slice),
  [§3.12](ARCHITECTURE.md#312-minimal-phase-2-d20-semantics),
  [§3.22](ARCHITECTURE.md#322-minimal-poisoned-behavior-g6c2),
  [DEC-0019](DECISIONS.md#dec-0019--ability-check-result-and-event-metadata-boundaries),
  [DEC-0022](DECISIONS.md#dec-0022--canonical-d20-selection-semantics), and
  [DEC-0037](DECISIONS.md#dec-0037--minimal-poisoned-behavior-uses-mechanic-specific-condition-policies-g6c2).

## P2-PROFICIENCY

- **Implemented Phase 2 scope:** Character proficiency bonus is derived from
  authoritative `CharacterState.total_level`; Saving Throw and Skill
  proficiency use separate effective membership sets, and the narrow unarmed
  Character attack always applies the derived Character bonus.
- **Closure assessment:** The foundation is sufficient for the implemented
  Character consumers because bonus derivation and membership sources are
  explicit and persisted. It is not sufficient to close broad Proficiency:
  source provenance, Expertise/half proficiency, monster sources, and broader
  attack proficiency are absent.
- **Broader unimplemented scope:** [DEF-0001](#def-0001),
  [DEF-0002](#def-0002), [DEF-0003](#def-0003), and the weapon-proficiency
  portion of [DEF-0011](#def-0011).
- **Motivation:** Character level, monster challenge/profiles, and weapon
  training are materially different sources and must not be forced through a
  universal Creature formula.
- **Continuation:** The DEF records above; Roadmap determines their order.
- **References:** [Architecture §3.11](ARCHITECTURE.md#311-minimal-phase-2-proficiency-foundation),
  [§3.2.4](ARCHITECTURE.md#324-minimal-phase-2-characterstate-contract),
  [DEC-0021](DECISIONS.md#dec-0021--proficiency-begins-as-a-pure-character-level-rule),
  and [DEC-0023](DECISIONS.md#dec-0023--character-proficiency-prerequisites-live-in-dedicated-characterstate).

## P2-SAVING-THROWS

- **Implemented Phase 2 scope:** A read-only Character Saving Throw resolves
  an explicit Ability and DC from matching Creature/Character projections,
  applies effective save proficiency, emits `SavingThrowResolved` V1, and
  deliberately remains NORMAL under Poisoned.
- **Closure assessment:** This is a complete Character vertical slice and a
  sufficient reusable foundation. Broad Saving Throws remain incomplete
  because monster proficiency, monster resolution, Death Saving Throws, and
  future source aggregation are not implemented.
- **Broader unimplemented scope:** [DEF-0002](#def-0002),
  [DEF-0004](#def-0004), [DEF-0005](#def-0005),
  [DEF-0021](#def-0021), and durable history in [DEF-0022](#def-0022).
- **Motivation:** Character saves must not imply monster or zero-HP policies
  whose authoritative inputs and lifecycle differ.
- **Continuation:** The Saving Throw and HP continuation DEF records above.
- **References:** [Architecture §3.13](ARCHITECTURE.md#313-minimal-phase-2-character-saving-throw-vertical-slice),
  [§3.22](ARCHITECTURE.md#322-minimal-poisoned-behavior-g6c2), and
  [DEC-0024](DECISIONS.md#dec-0024--first-saving-throw-vertical-slice-is-character-specific).

## P2-SKILLS

- **Implemented Phase 2 scope:** `Skill` is an identity-only closed set;
  Character Skill proficiency membership is persisted; and the read-only
  Skill Check takes Skill and Ability as independent explicit inputs, allowing
  combinations such as Strength (Intimidation). Poisoned reuses the
  ability-check Condition policy.
- **Closure assessment:** This is sufficient for Character Skill Check
  resolution without corrupting Skill identity. Broad Skills remain
  incomplete because Expertise/half proficiency, monsters/NPCs, passive
  scores, and command-generation suggestions are absent.
- **Broader unimplemented scope:** [DEF-0001](#def-0001),
  [DEF-0006](#def-0006), [DEF-0007](#def-0007),
  [DEF-0008](#def-0008), [DEF-0021](#def-0021), and
  [DEF-0022](#def-0022).
- **Motivation:** A default Skill-to-Ability suggestion is adjudication input,
  not a Domain invariant; alternative Ability use must remain possible.
- **Continuation:** DEF-0008 belongs to future command generation/adjudication,
  while Domain Skill Check keeps both values explicit.
- **References:** [Architecture §1.2.2](ARCHITECTURE.md#122-skill-value-object),
  [§3.14](ARCHITECTURE.md#314-minimal-phase-2-character-skill-check-vertical-slice),
  [DEC-0025](DECISIONS.md#dec-0025--skill-identity-and-proficiency-membership-foundation),
  and [DEC-0026](DECISIONS.md#dec-0026--character-skill-check-keeps-skill-and-ability-explicit).

## P2-ARMOR-CLASS

- **Implemented Phase 2 scope:** Effective AC is derived rather than persisted:
  unarmored Character AC is `10 + Dexterity modifier`, while Monster baseline
  AC is read from a typed immutable `MonsterDefinition` through packaged
  Definition access. Attack records the actual target AC used.
- **Closure assessment:** This is sufficient for the checked minimal AC item
  and its first consumer. It is not sufficient for equipment-derived or
  runtime-modified effective AC.
- **Broader unimplemented scope:** [DEF-0009](#def-0009) and
  [DEF-0010](#def-0010).
- **Motivation:** Keep authoritative AC inputs with their existing owners and
  avoid a duplicated materialized `armor_class` field or premature modifier
  pipeline.
- **Continuation:** Equipment and runtime composition are separate DEF records
  and require their own concrete consumers.
- **References:** [Architecture §3.15](ARCHITECTURE.md#315-minimal-phase-2-armor-class-design),
  [§3.16](ARCHITECTURE.md#316-minimal-phase-2-definition-access-vertical-slice-g4a),
  [DEC-0028](DECISIONS.md#dec-0028--armor-class-is-derived-from-authoritative-sources),
  and [DEC-0029](DECISIONS.md#dec-0029--definition-access-and-packaged-srd-51-ruleset-boundary-g4a).

## P2-ATTACK-ROLLS

- **Implemented Phase 2 scope:** One read-only Character unarmed attack against
  a Monster target uses Strength, derived Character proficiency, baseline
  Monster AC, shared d20 selection, Attack-owned natural 1/20 semantics, and
  one `AttackResolved` V1 Event. Poisoned affects the attacker.
- **Closure assessment:** The slice is sufficient evidence for the Attack
  boundary and for keeping the mechanic concrete. It is not sufficient for
  the broad Attack Rolls item because weapons, Character targets, monsters,
  spells, and consequences are missing.
- **Broader unimplemented scope:** [DEF-0011](#def-0011),
  [DEF-0012](#def-0012), [DEF-0013](#def-0013),
  [DEF-0014](#def-0014), [DEF-0021](#def-0021), and
  [DEF-0022](#def-0022).
- **Motivation:** Different attack sources have different authoritative
  inputs; the first narrow slice does not justify a generic check, attack, or
  modifier framework.
- **Continuation:** Weapon/Character, monster, consequence, and spell paths
  remain separate DEF records.
- **References:** [Architecture §3.17](ARCHITECTURE.md#317-minimal-phase-2-character-unarmed-attack-roll--monster-vertical-slice),
  [DEC-0031](DECISIONS.md#dec-0031--first-character-unarmed-attack-roll--monster-slice-stays-concrete),
  and [DEC-0037](DECISIONS.md#dec-0037--minimal-poisoned-behavior-uses-mechanic-specific-condition-policies-g6c2).

## P2-STATE-MUTATION

- **Implemented Phase 2 scope:** The G5 contract and four concrete handlers
  prove read-only loaded snapshots, pure resolution, complete Event creation,
  concrete Event application, copy-on-write Creature/snapshot replacement,
  one successful-path `StateStore.save()`, and success only after save. The
  only extracted abstraction is stable-ID Creature replacement in a snapshot.
- **Closure assessment:** This is sufficient as the Phase 2 mutation
  foundation for Damage, Healing, Apply Condition, and Remove Condition. It is
  not a durable Event-history, replay, transaction, concurrency, or
  exactly-once subsystem.
- **Broader unimplemented scope:** Durable history, serialized dispatch,
  replay/recovery, idempotency, and atomic Event/State persistence are tracked
  together in [DEF-0022](#def-0022).
- **Motivation:** Snapshot-authoritative persistence solves the current
  single-store problem without claiming guarantees that require a second
  durable resource and transaction design.
- **Continuation:** DEF-0022; concrete gameplay continuations remain in their
  mechanic-specific DEF records.
- **References:** [Architecture §3.18](ARCHITECTURE.md#318-state-mutation-foundation-g5),
  [§3.23](ARCHITECTURE.md#323-post-g6c-abstraction-review),
  [DEC-0032](DECISIONS.md#dec-0032--first-authoritative-state-mutation-uses-snapshot-authoritative-event-driven-replacement),
  and [DEC-0038](DECISIONS.md#dec-0038--post-g6c-review-extracts-only-stable-creature-snapshot-replacement).

## P2-HP

- **Implemented Phase 2 scope:** `CreatureState.current_hp`/`max_hp` invariants
  are persisted, and concrete Damage and Healing paths replace only
  `current_hp`, with floor/cap behavior and documented successful no-ops.
- **Closure assessment:** This is sufficient for direct bounded HP mutation
  evidence. Broad HP remains incomplete because zero-HP eligibility, death,
  temporary HP, recovery, and related lifecycle policy are absent.
- **Broader unimplemented scope:** [DEF-0005](#def-0005),
  [DEF-0015](#def-0015), [DEF-0016](#def-0016), and
  [DEF-0019](#def-0019).
- **Motivation:** HP arithmetic is not the same policy as life state, temporary
  buffers, or rest-driven resource recovery.
- **Continuation:** The four HP/lifecycle DEF records above.
- **References:** [Architecture §3.2.1](ARCHITECTURE.md#321-minimal-phase-1-creaturestate-contract),
  [§3.19](ARCHITECTURE.md#319-minimal-damage--hp-mutation-vertical-slice-g6a),
  [§3.20](ARCHITECTURE.md#320-minimal-healing--hp-mutation-vertical-slice-g6b),
  [DEC-0033](DECISIONS.md#dec-0033--first-concrete-damage--hp-mutation-slice-g6a-stays-concrete),
  and [DEC-0034](DECISIONS.md#dec-0034--minimal-healing--hp-mutation-slice-g6b-stays-concrete).

## P2-DAMAGE

- **Implemented Phase 2 scope:** A direct already-resolved positive amount is
  floored at zero, recorded as `DamageApplied` V1 with both HP endpoints,
  applied by a concrete Creature applier, and persisted through the G5 flow.
- **Closure assessment:** This is sufficient for the first authoritative
  Damage-to-HP mutation slice. Broad Damage is incomplete because source
  orchestration, weapon/critical damage, and typed defenses are absent.
- **Broader unimplemented scope:** Attack consequence and weapon/critical
  damage in [DEF-0013](#def-0013), typed defenses in
  [DEF-0017](#def-0017), and durable application history in
  [DEF-0022](#def-0022).
- **Motivation:** First prove Event-driven HP mutation with a resolved amount;
  do not mix attack, damage dice, defense composition, and persistence into one
  initial contract.
- **Continuation:** DEF-0013, DEF-0017, and DEF-0022.
- **References:** [Architecture §3.19](ARCHITECTURE.md#319-minimal-damage--hp-mutation-vertical-slice-g6a)
  and [DEC-0033](DECISIONS.md#dec-0033--first-concrete-damage--hp-mutation-slice-g6a-stays-concrete).

## P2-HEALING

- **Implemented Phase 2 scope:** A direct source-agnostic positive amount is
  capped at authoritative `max_hp`, recorded as `HealingApplied` V1, applied
  by a concrete Creature applier, and persisted through the G5 flow. Healing
  from zero and full-HP no-op Healing are accepted.
- **Closure assessment:** This is sufficient for direct bounded Healing
  mutation and the Damage/Healing comparison. Broad Healing is incomplete
  because sources, resources, recovery semantics, and rests are absent.
- **Broader unimplemented scope:** [DEF-0015](#def-0015),
  [DEF-0018](#def-0018), [DEF-0019](#def-0019), and
  [DEF-0022](#def-0022).
- **Motivation:** Source/resource consumption and life-state recovery need
  facts that a source-agnostic HP amount cannot supply.
- **Continuation:** The Healing, recovery, and history DEF records above.
- **References:** [Architecture §3.20](ARCHITECTURE.md#320-minimal-healing--hp-mutation-vertical-slice-g6b)
  and [DEC-0034](DECISIONS.md#dec-0034--minimal-healing--hp-mutation-slice-g6b-stays-concrete).

## P2-CONDITIONS

- **Implemented Phase 2 scope:** Persisted effective membership currently
  supports only `POISONED`; Apply/Remove Commands, resolvers, V1 Events,
  concrete appliers, and saving handlers are implemented. Poisoned causes
  disadvantage for Ability/Skill Checks and attacker Attack Rolls, but not
  Saving Throws.
- **Closure assessment:** This is sufficient to prove that Condition State is
  authoritative and behavior-driving. Broad Conditions remain incomplete:
  other identities, lifecycle/source/duration/stacking, other Poisoned rules,
  and multiple roll-mode sources are absent.
- **Broader unimplemented scope:** [DEF-0020](#def-0020),
  [DEF-0021](#def-0021), and [DEF-0022](#def-0022).
- **Motivation:** One Condition and one effect family do not justify an Effect
  Engine, registry, modifier pipeline, runtime Condition entity, or collapsed
  `RollMode` combiner.
- **Continuation:** Expand concrete lifecycle/behavior through DEF-0020; model
  independent roll sources through DEF-0021 when a second source exists.
- **References:** [Architecture §3.21](ARCHITECTURE.md#321-condition-state-foundation-g6c1),
  [§3.22](ARCHITECTURE.md#322-minimal-poisoned-behavior-g6c2),
  [DEC-0035](DECISIONS.md#dec-0035--condition-state-foundation-g6c1-persisted-membership-only-state-schema-v4),
  [DEC-0036](DECISIONS.md#dec-0036--condition-applyremove-pure-domain-mutation-contract-g6c1-group-2),
  and [DEC-0037](DECISIONS.md#dec-0037--minimal-poisoned-behavior-uses-mechanic-specific-condition-policies-g6c2).

## Deferred-scope register

## DEF-0001

- **Title:** Expertise and half proficiency
- **Origin:** [P2-PROFICIENCY](#p2-proficiency) and
  [P2-SKILLS](#p2-skills).
- **Created:** 2026-08-30
- **Target:** Character Progression cross-cutting track.
- **Status:** Deferred
- **Description:** Model character mechanics that apply double or half the
  normal proficiency bonus without changing the existing base bonus rule.
- **Motivation:** Current membership is binary and cannot express Expertise or
  half proficiency while preserving auditable contribution calculation.
- **Why deferred:** No implemented mechanic or authoritative State source yet
  requires a multiplier or rounding/stacking policy.
- **Prerequisites:** A concrete feature/source that grants Expertise or half
  proficiency and a decision about authoritative effective membership versus
  source provenance.
- **Planned approach:** Design from the first real source; keep base
  `character_proficiency_bonus()` derived, record contributions explicitly,
  and avoid a generic modifier pipeline unless multiple consumers prove it.
- **Acceptance criteria:** Concrete source and lifecycle are represented;
  double/half calculation and rounding are deterministic; stacking and
  conflicting-source behavior are explicit; Skill/Saving Throw regressions
  remain intact; persistence and Events are versioned if State changes.
- **References:** [Architecture §3.11](ARCHITECTURE.md#311-minimal-phase-2-proficiency-foundation),
  [§3.14](ARCHITECTURE.md#314-minimal-phase-2-character-skill-check-vertical-slice),
  and [DEC-0027](DECISIONS.md#dec-0027--third-d20-consumer-does-not-justify-shared-checkorchestration-abstraction).
- **History:** 2026-08-30 — Created from the Phase 2 closure review; no
  implementation or scheduling commitment.

## DEF-0002

- **Title:** Monster proficiency sources
- **Origin:** [P2-PROFICIENCY](#p2-proficiency) and
  [P2-SAVING-THROWS](#p2-saving-throws).
- **Created:** 2026-08-30
- **Target:** Phase 3 — Monster actions.
- **Status:** Deferred
- **Description:** Establish authoritative monster proficiency inputs for
  saves, skills, attacks, and other mechanics without applying the Character
  total-level formula to monsters.
- **Motivation:** Monster proficiency follows monster/stat-block or challenge
  rules, not `CharacterState.total_level`.
- **Why deferred:** Current `MonsterDefinition` intentionally lacks challenge,
  proficiency, save, skill, and action fields.
- **Prerequisites:** A concrete monster save/skill/attack consumer and the
  minimal immutable Definition facts it needs.
- **Planned approach:** Extend the typed packaged Monster Definition only with
  evidence-required source facts; keep derived values out of runtime State
  unless a mutable source is demonstrated.
- **Acceptance criteria:** At least one monster consumer resolves from typed
  authoritative data; missing/wrong-type Definitions follow existing lookup
  errors; Character formulas are not reused incorrectly; wheel packaging and
  deterministic tests cover the new data.
- **References:** [Architecture §3.11](ARCHITECTURE.md#311-minimal-phase-2-proficiency-foundation),
  [§3.16](ARCHITECTURE.md#316-minimal-phase-2-definition-access-vertical-slice-g4a),
  and [DEC-0029](DECISIONS.md#dec-0029--definition-access-and-packaged-srd-51-ruleset-boundary-g4a).
- **History:** 2026-08-30 — Created from the Phase 2 closure review; no
  implementation or scheduling commitment.

## DEF-0003

- **Title:** Character progression / `total_level` provenance
- **Origin:** [P2-PROFICIENCY](#p2-proficiency).
- **Created:** 2026-08-30
- **Target:** Future Character progression slice.
- **Status:** Deferred
- **Description:** Represent how authoritative `CharacterState.total_level`
  is established and changed, including class-level or equivalent provenance.
- **Motivation:** Current consumers can derive proficiency from total level,
  but the engine cannot audit or execute progression that changes it.
- **Why deferred:** Phase 2 needed only the effective current total; no XP,
  class, multiclass, level-up Command, or progression Event exists.
- **Prerequisites:** A concrete progression use case and ruleset Definitions
  for the minimum required progression facts.
- **Planned approach:** Add the smallest owner-authorized progression Command,
  outcome, Event, and replacement `CharacterState` flow; keep total proficiency
  derived and avoid inventing a class framework before required.
- **Acceptance criteria:** Provenance and allowed transition are explicit;
  State Owner and mutation scope are documented; persistence is versioned;
  proficiency consumers observe the new total after reload; invalid
  transitions fail deterministically.
- **References:** [Architecture §3.2.4](ARCHITECTURE.md#324-minimal-phase-2-characterstate-contract),
  [§3.11](ARCHITECTURE.md#311-minimal-phase-2-proficiency-foundation), and
  [DEC-0023](DECISIONS.md#dec-0023--character-proficiency-prerequisites-live-in-dedicated-characterstate).
- **History:** 2026-08-30 — Created from the Phase 2 closure review; no
  implementation or scheduling commitment.

## DEF-0004

- **Title:** Monster saving throws
- **Origin:** [P2-SAVING-THROWS](#p2-saving-throws).
- **Created:** 2026-08-30
- **Target:** Phase 3 / first concrete monster-saving-throw consumer.
- **Status:** Deferred
- **Description:** Add a monster Saving Throw path using monster-authoritative
  ability and proficiency inputs while preserving mechanic-level Command/Event
  naming where appropriate.
- **Motivation:** Broad Saving Throws cannot close with only a Character
  projection-dependent resolver.
- **Why deferred:** [DEF-0002](#def-0002) is unresolved and the current monster
  Definition contains no saving-throw proficiency facts.
- **Prerequisites:** DEF-0002 and a concrete monster-save caller.
- **Planned approach:** Reuse `D20Roll` and shared ability modifier, but create
  a concrete monster resolver/handler policy rather than forcing
  `CharacterState` or a universal Creature proficiency formula.
- **Acceptance criteria:** Proficient and non-proficient monster saves resolve
  deterministically; natural 1/20 retain Saving Throw semantics; Event audit
  contributions are explicit; Character save behavior is unchanged.
- **References:** [Architecture §3.13](ARCHITECTURE.md#313-minimal-phase-2-character-saving-throw-vertical-slice)
  and [DEC-0024](DECISIONS.md#dec-0024--first-saving-throw-vertical-slice-is-character-specific).
- **History:** 2026-08-30 — Created from the Phase 2 closure review; no
  implementation or scheduling commitment.

## DEF-0005

- **Title:** Death saving throws
- **Origin:** [P2-SAVING-THROWS](#p2-saving-throws) and [P2-HP](#p2-hp).
- **Created:** 2026-08-30
- **Target:** Phase 3 — Character zero-HP lifecycle.
- **Status:** Deferred
- **Description:** Implement the Character zero-HP death-save lifecycle, its
  counters, reset rules, outcomes, and authoritative State transitions.
- **Motivation:** Death saves are not ordinary ability-based Saving Throws and
  require Character-specific zero-HP and turn sequencing absent from the
  Character save slice.
- **Why deferred:** Zero-HP semantics and combatant eligibility
  ([DEF-0015](#def-0015)) plus turn/lifecycle inputs are not implemented.
- **Prerequisites:** A concrete Character zero-HP/turn consumer from DEF-0015
  and the minimum combat timing/ownership contract needed to request and apply
  a death save.
- **Planned approach:** Design a Character-specific mechanic rather than reuse
  `SavingThrowCommand(ability, dc)`; persist only the Character death-save
  counters and lifecycle data proven necessary by the concrete zero-HP/turn
  consumer, through concrete Events and owner-specific replacement. Do not
  require a universal Creature `LifeState`.
- **Acceptance criteria:** Success/failure/critical outcomes, three-success and
  three-failure transitions, reset conditions, damage/healing interaction,
  turn eligibility, persistence, and deterministic tests are explicit.
- **References:** [Architecture §3.13](ARCHITECTURE.md#313-minimal-phase-2-character-saving-throw-vertical-slice),
  [§10.4](ARCHITECTURE.md#104-creature-state-owner), and
  [DEC-0033](DECISIONS.md#dec-0033--first-concrete-damage--hp-mutation-slice-g6a-stays-concrete).
- **History:** 2026-08-30 — Created from the Phase 2 closure review; no
  implementation or scheduling commitment.

## DEF-0006

- **Title:** Monster/NPC skill checks
- **Origin:** [P2-SKILLS](#p2-skills).
- **Created:** 2026-08-30
- **Target:** Phase 5 — NPCs / first concrete NPC skill-check consumer.
- **Status:** Deferred
- **Description:** Resolve Skill Checks for monsters and NPCs without requiring
  a matching `CharacterState` projection.
- **Motivation:** Broad Skills apply beyond player Characters, while current
  proficiency and lookup policy is Character-specific.
- **Why deferred:** Monster/NPC proficiency sources and required Definition or
  State inputs are not established.
- **Prerequisites:** DEF-0002 or another explicit NPC/monster proficiency
  source, plus a concrete caller.
- **Planned approach:** Keep Skill and Ability explicit; reuse shared d20 and
  ability rules; add source-specific concrete resolution rather than a generic
  check hierarchy.
- **Acceptance criteria:** Monster/NPC lookup and proficiency inputs are
  authoritative; alternative Ability use remains valid; Event audit records
  actual Skill/Ability/contributions; Character behavior is unchanged.
- **References:** [Architecture §1.2.2](ARCHITECTURE.md#122-skill-value-object),
  [§3.14](ARCHITECTURE.md#314-minimal-phase-2-character-skill-check-vertical-slice),
  and [DEC-0026](DECISIONS.md#dec-0026--character-skill-check-keeps-skill-and-ability-explicit).
- **History:** 2026-08-30 — Created from the Phase 2 closure review; no
  implementation or scheduling commitment.

## DEF-0007

- **Title:** Passive skill scores
- **Origin:** [P2-SKILLS](#p2-skills).
- **Created:** 2026-08-30
- **Target:** Phase 5 — Knowledge/exploration / first concrete passive-score
  consumer.
- **Status:** Deferred
- **Description:** Define passive score calculation and consumption for a
  concrete Skill/Ability combination, including applicable modifiers.
- **Motivation:** Passive scores are queries/derived results, not rolls, and
  should not be invented as persisted fields or routed through DiceEngine.
- **Why deferred:** No visibility, encounter, search, or AI-context consumer
  currently requires them, and multi-source modifier rules are incomplete.
- **Prerequisites:** A concrete passive-score consumer and the exact
  authoritative inputs it requires.
- **Planned approach:** Prefer a pure derived query over persisted State;
  preserve explicit Skill+Ability and add only evidenced source adjustments.
- **Acceptance criteria:** Formula, source inputs, rounding, active-versus-
  passive boundary, alternative Ability behavior, and Condition interaction
  are deterministic and tested without RNG or State mutation.
- **References:** [Architecture §3.14](ARCHITECTURE.md#314-minimal-phase-2-character-skill-check-vertical-slice)
  and [DEC-0026](DECISIONS.md#dec-0026--character-skill-check-keeps-skill-and-ability-explicit).
- **History:** 2026-08-30 — Created from the Phase 2 closure review; no
  implementation or scheduling commitment.

## DEF-0008

- **Title:** Default Skill-to-Ability suggestion for command generation
- **Origin:** [P2-SKILLS](#p2-skills).
- **Created:** 2026-08-30
- **Target:** Future command-generation/adjudication, including Phase 6 AI DM
  where applicable.
- **Status:** Deferred
- **Description:** Provide a ruleset-aware default Ability suggestion when an
  adjudicator or command generator chooses a Skill Check, without making that
  suggestion part of Skill identity or Domain resolution.
- **Motivation:** Defaults improve command generation, but fixed Domain mapping
  would invalidate legitimate alternatives such as Strength (Intimidation).
- **Why deferred:** No command-generation/adjudication layer or AI tool surface
  currently consumes such suggestions.
- **Prerequisites:** A concrete command-generation caller and a defined
  ruleset/configuration source for suggestions.
- **Planned approach:** Keep `SkillCheckCommand(skill, ability, dc)` explicit;
  place defaults before Command construction, allow adjudicator override, and
  never normalize the supplied Ability inside Domain Skill Check resolution.
- **Acceptance criteria:** Suggested defaults are ruleset-aware and testable;
  overrides survive unchanged into Command/Event/result; no fixed mapping is
  added to `Skill`; Domain accepts alternative combinations.
- **References:** [Architecture §1.2.2](ARCHITECTURE.md#122-skill-value-object),
  [§3.14](ARCHITECTURE.md#314-minimal-phase-2-character-skill-check-vertical-slice),
  and [DEC-0026](DECISIONS.md#dec-0026--character-skill-check-keeps-skill-and-ability-explicit).
- **History:** 2026-08-30 — Created from the Phase 2 closure review; no
  implementation or scheduling commitment.

## DEF-0009

- **Title:** Equipment-derived Armor Class
- **Origin:** [P2-ARMOR-CLASS](#p2-armor-class).
- **Created:** 2026-08-30
- **Target:** Equipment/Armor Class continuation.
- **Status:** Deferred
- **Description:** Derive effective Character and applicable monster AC from
  equipped armor, shields, and supported equipment rules while respecting the
  Equipment State Owner.
- **Motivation:** Unarmored Character and baseline Monster AC cannot represent
  equipped defenses.
- **Why deferred:** `EquipmentState`, equipped slots, armor Definitions, and
  equip/unequip lifecycle are not implemented.
- **Prerequisites:** Minimal Equipment State/owner flow, typed armor/shield
  Definitions, and a concrete AC consumer.
- **Planned approach:** Read authoritative equipment through its owner and
  derive AC at query/resolution time; do not persist duplicate effective AC on
  Creature/Character State.
- **Acceptance criteria:** Armor/shield formulas and incompatibilities are
  deterministic; equipment changes affect later AC after persistence; owners
  remain separate; unarmored and Monster baseline regressions pass.
- **References:** [Architecture §3.15](ARCHITECTURE.md#315-minimal-phase-2-armor-class-design),
  [§10.6](ARCHITECTURE.md#106-equipment-state-owner), and
  [DEC-0028](DECISIONS.md#dec-0028--armor-class-is-derived-from-authoritative-sources).
- **History:** 2026-08-30 — Created from the Phase 2 closure review; no
  implementation or scheduling commitment.

## DEF-0010

- **Title:** Runtime Armor Class modifiers
- **Origin:** [P2-ARMOR-CLASS](#p2-armor-class).
- **Created:** 2026-08-30
- **Target:** Armor Class continuation with concrete Condition/effect/spell
  consumers.
- **Status:** Deferred
- **Description:** Compose temporary/runtime AC changes from authoritative
  sources without materializing effective AC or introducing an unproven
  generic modifier framework.
- **Motivation:** Spells, effects, and Conditions can change effective AC after
  baseline/equipment calculation.
- **Why deferred:** No implemented AC modifier source establishes composition,
  precedence, duration, or ownership semantics.
- **Prerequisites:** At least one concrete runtime AC source; ownership and
  lifecycle for that source; DEF-0009 if equipment baseline is required.
- **Planned approach:** Add source-specific policy first, then extract only
  stable composition behavior proven by multiple sources.
- **Acceptance criteria:** Source lifecycle and ownership are explicit;
  stacking/precedence and expiration are deterministic; Attack audits the
  actual effective AC; no duplicate persisted AC source is created.
- **References:** [Architecture §3.15](ARCHITECTURE.md#315-minimal-phase-2-armor-class-design)
  and [DEC-0028](DECISIONS.md#dec-0028--armor-class-is-derived-from-authoritative-sources).
- **History:** 2026-08-30 — Created from the Phase 2 closure review; no
  implementation or scheduling commitment.

## DEF-0011

- **Title:** Weapon attacks and Character-target attacks
- **Origin:** [P2-ATTACK-ROLLS](#p2-attack-rolls) and
  [P2-PROFICIENCY](#p2-proficiency).
- **Created:** 2026-08-30
- **Target:** Phase 3 — Weapon attacks.
- **Status:** Deferred
- **Description:** Extend Character attacks to weapon sources and Character
  targets, including weapon proficiency, ability selection, Finesse, range,
  reach, and ammunition constraints.
- **Motivation:** The unarmed-to-Monster path hard-codes Strength and Character
  proficiency and has no equipment, weapon, or spatial inputs.
- **Why deferred:** Equipment/inventory, weapon-instance selection, target
  categories, distance, and ammunition State are absent.
- **Prerequisites:** Minimal equipment/inventory source, typed weapon lookup,
  necessary targeting/distance facts, and a concrete attack use case.
- **Planned approach:** Keep one explicit Attack intent while deriving weapon
  attack inputs from authoritative State/Definitions; implement concrete
  weapon policies before considering shared abstractions.
- **Acceptance criteria:** Proficiency, Strength/Dexterity/Finesse choice,
  melee reach, ranged limits, ammunition consumption, Character AC lookup,
  failures, Events, and persistence side effects are explicit and tested.
- **References:** [Architecture §3.17](ARCHITECTURE.md#317-minimal-phase-2-character-unarmed-attack-roll--monster-vertical-slice),
  [§3.1.1](ARCHITECTURE.md#311-minimal-phase-1-definition-contracts),
  [DEC-0030](DECISIONS.md#dec-0030--shared-domain-ndm-parser-for-dice-engine-and-weapondefinition-g4b),
  and [DEC-0031](DECISIONS.md#dec-0031--first-character-unarmed-attack-roll--monster-slice-stays-concrete).
- **History:** 2026-08-30 — Created from the Phase 2 closure review; no
  implementation or scheduling commitment.

## DEF-0012

- **Title:** Monster attacks/actions
- **Origin:** [P2-ATTACK-ROLLS](#p2-attack-rolls).
- **Created:** 2026-08-30
- **Target:** Phase 3 — Monster actions.
- **Status:** Deferred
- **Description:** Represent and resolve monster stat-block attacks and
  actions using typed packaged Definitions and appropriate runtime targets.
- **Motivation:** Character unarmed rules and `CharacterState.total_level`
  cannot authoritatively describe monster actions.
- **Why deferred:** Monster action Definitions, monster proficiency sources,
  target/range rules, and consequence orchestration are absent.
- **Prerequisites:** DEF-0002, the minimal Monster action Definition schema,
  and required targeting/combat facts.
- **Planned approach:** Add one real stat-block action and concrete resolver;
  reuse only proven d20/Definition boundaries; do not create a generic action
  registry ahead of multiple consumers.
- **Acceptance criteria:** Packaged action data loads from an installed wheel;
  attack bonus/source and targets are authoritative; natural semantics and
  Event audit are explicit; consequence handoff is tested if included.
- **References:** [Architecture §3.16](ARCHITECTURE.md#316-minimal-phase-2-definition-access-vertical-slice-g4a),
  [§3.17](ARCHITECTURE.md#317-minimal-phase-2-character-unarmed-attack-roll--monster-vertical-slice),
  and [DEC-0031](DECISIONS.md#dec-0031--first-character-unarmed-attack-roll--monster-slice-stays-concrete).
- **History:** 2026-08-30 — Created from the Phase 2 closure review; no
  implementation or scheduling commitment.

## DEF-0013

- **Title:** Attack consequence, weapon damage and critical damage
- **Origin:** [P2-ATTACK-ROLLS](#p2-attack-rolls) and
  [P2-DAMAGE](#p2-damage).
- **Created:** 2026-08-30
- **Target:** Phase 3 — Attack consequences.
- **Status:** Deferred
- **Description:** Connect a successful attack to source-specific damage
  resolution, including weapon dice/modifiers and natural-20 critical damage,
  then apply the result through the authoritative Damage/HP flow.
- **Motivation:** `AttackResolved` currently stops at hit/miss/critical, while
  `ApplyDamageCommand` accepts an unrelated already-resolved amount.
- **Why deferred:** Weapon attack inputs and critical-damage policy are absent;
  premature orchestration would couple unrelated foundations.
- **Prerequisites:** Relevant part of DEF-0011, a concrete damage source, and
  an explicit Event ordering/causation design; DEF-0022 only if durability is
  made part of the slice.
- **Planned approach:** Preserve Attack and Damage as separate decisions;
  construct ordered correlated Events and feed an already-resolved damage
  outcome into concrete State application without re-rolling in the applier.
- **Acceptance criteria:** Miss produces no damage; hit and critical formulas
  are deterministic; dice use `DiceEngine`; Event order/`causedBy` are clear;
  HP changes only after concrete Damage application and successful save.
- **References:** [Architecture §3.17](ARCHITECTURE.md#317-minimal-phase-2-character-unarmed-attack-roll--monster-vertical-slice),
  [§3.19](ARCHITECTURE.md#319-minimal-damage--hp-mutation-vertical-slice-g6a),
  [§12.11](ARCHITECTURE.md#1211-event-ordering),
  [DEC-0031](DECISIONS.md#dec-0031--first-character-unarmed-attack-roll--monster-slice-stays-concrete),
  and [DEC-0033](DECISIONS.md#dec-0033--first-concrete-damage--hp-mutation-slice-g6a-stays-concrete).
- **History:** 2026-08-30 — Created from the Phase 2 closure review; no
  implementation or scheduling commitment.

## DEF-0014

- **Title:** Spell attacks
- **Origin:** [P2-ATTACK-ROLLS](#p2-attack-rolls).
- **Created:** 2026-08-30
- **Target:** Phase 4 Magic.
- **Status:** Deferred
- **Description:** Resolve spell attack rolls from spellcasting sources,
  spellcasting ability/proficiency, targets, and spell Definitions.
- **Motivation:** Spell attacks share d20/AC comparison but have different
  authoritative sources and belong with the Magic contracts.
- **Why deferred:** Spells, slots/resources, casting State, spell targeting,
  and spell Definitions are Phase 4 Roadmap work.
- **Prerequisites:** Minimal Magic Definition/State/Command boundaries and a
  concrete spell-attack consumer.
- **Planned approach:** Reuse d20 and effective AC primitives while keeping
  spell-specific source/resource/target policy concrete; coordinate damage
  through DEF-0013 where appropriate.
- **Acceptance criteria:** Casting source and resources are authoritative;
  attack bonus and target AC are auditable; resource failure happens before
  resolution; hit/miss/critical policy and resulting Events are explicit.
- **References:** [Architecture §3.17](ARCHITECTURE.md#317-minimal-phase-2-character-unarmed-attack-roll--monster-vertical-slice),
  [Roadmap Phase 4](ROADMAP.md#phase-4--magic), and
  [DEC-0031](DECISIONS.md#dec-0031--first-character-unarmed-attack-roll--monster-slice-stays-concrete).
- **History:** 2026-08-30 — Created from the Phase 2 closure review; no
  implementation or scheduling commitment.

## DEF-0015

- **Title:** Zero-HP semantics and combatant eligibility
- **Origin:** [P2-HP](#p2-hp) and [P2-HEALING](#p2-healing).
- **Created:** 2026-08-30
- **Target:** Phase 3 — zero-HP and combatant eligibility.
- **Status:** Deferred
- **Description:** Define Character and Monster zero-HP semantics separately
  and their effects on available actions, combat participation, targeting,
  Damage, stabilization, and Healing.
- **Motivation:** Current `0 -> 0` Damage and Healing from zero are arithmetic
  only; they intentionally make no unconscious/death/eligibility decision.
- **Why deferred:** No concrete Phase 3 Turns/action-eligibility consumer has
  yet established what a combatant may do at `current_hp == 0` or whether
  either creature category needs additional lifecycle State.
- **Prerequisites:** A concrete Phase 3 Turns/action-eligibility consumer that
  must answer what a combatant may do at `current_hp == 0`; evaluate Character
  and Monster requirements separately and coordinate the Character path with
  DEF-0005.
- **Planned approach:** Treat `current_hp == 0` as the already-authoritative
  fact. Add only the category-specific authoritative lifecycle State and Events
  that the concrete consumer proves necessary; do not predefine a universal
  `LifeState` enum/model. UI, AI, and API may consume resolved facts but must
  not invent them.
- **Acceptance criteria:** Character and Monster zero-HP behavior is specified
  separately; further Damage, Healing, stabilization/death, action eligibility,
  persistence, and Event causation are deterministic; any additional lifecycle
  State is consumer-proven, and external layers cannot mutate or invent
  authoritative lifecycle facts.
- **References:** [Architecture §3.19](ARCHITECTURE.md#319-minimal-damage--hp-mutation-vertical-slice-g6a),
  [§3.20](ARCHITECTURE.md#320-minimal-healing--hp-mutation-vertical-slice-g6b),
  and [§10.4](ARCHITECTURE.md#104-creature-state-owner).
- **History:** 2026-08-30 — Created from the Phase 2 closure review; no
  implementation or scheduling commitment.

## DEF-0016

- **Title:** Temporary HP
- **Origin:** [P2-HP](#p2-hp).
- **Created:** 2026-08-30
- **Target:** Phase 4 Effects or an earlier concrete temporary-HP consumer.
- **Status:** Deferred
- **Description:** Add temporary HP as an authoritative, separate buffer with
  replacement and non-stacking semantics, integrated with Damage.
- **Motivation:** Temporary HP is not `current_hp`, Healing, or a raised
  `max_hp`; conflating them would corrupt the existing HP invariants.
- **Why deferred:** No concrete grant source, State field, Damage ordering, or
  expiration/replacement policy is implemented.
- **Prerequisites:** A concrete temporary-HP source and agreed interaction with
  typed Damage and life state.
- **Planned approach:** Model the minimum separate Creature-owned State and
  source-specific Events; apply Damage to the buffer before current HP without
  routing grants through Healing.
- **Acceptance criteria:** Grant/replacement/non-stacking, Damage absorption,
  zero/removal, persistence/migration, and audit Events are deterministic;
  `current_hp`/`max_hp` contracts remain intact.
- **References:** [Architecture §3.2.1](ARCHITECTURE.md#321-minimal-phase-1-creaturestate-contract),
  [§3.19](ARCHITECTURE.md#319-minimal-damage--hp-mutation-vertical-slice-g6a),
  and [DEC-0033](DECISIONS.md#dec-0033--first-concrete-damage--hp-mutation-slice-g6a-stays-concrete).
- **History:** 2026-08-30 — Created from the Phase 2 closure review; no
  implementation or scheduling commitment.

## DEF-0017

- **Title:** Typed damage defenses: resistance/immunity/vulnerability
- **Origin:** [P2-DAMAGE](#p2-damage).
- **Created:** 2026-08-30
- **Target:** first concrete typed-damage consumer.
- **Status:** Deferred
- **Description:** Resolve an incoming typed Damage amount through
  resistance, immunity, and vulnerability before HP application.
- **Motivation:** `DamageType` identity exists, but the current direct Damage
  Command deliberately contains no type or defense sources.
- **Why deferred:** No authoritative Creature/Definition defense data or
  stacking/precedence policy exists.
- **Prerequisites:** At least one real defense source, typed damage source, and
  decision on immutable versus runtime defense inputs.
- **Planned approach:** Keep defense resolution before `DamageApplied`; use the
  closed `DamageType`; record original/effective contributions needed for
  audit; avoid a generic modifier pipeline until multiple sources prove one.
- **Acceptance criteria:** Each defense kind and its interactions are
  deterministic; rounding/order are explicit; missing/duplicate sources are
  handled; only the resolved amount reaches HP mutation; Events are auditable.
- **References:** [Architecture §3.1.1](ARCHITECTURE.md#311-minimal-phase-1-definition-contracts),
  [§3.19](ARCHITECTURE.md#319-minimal-damage--hp-mutation-vertical-slice-g6a),
  and [DEC-0009](DECISIONS.md#dec-0009--damagetype-is-a-closed-domain-strenum).
- **History:** 2026-08-30 — Created from the Phase 2 closure review; no
  implementation or scheduling commitment.

## DEF-0018

- **Title:** Source-aware healing
- **Origin:** [P2-HEALING](#p2-healing).
- **Created:** 2026-08-30
- **Target:** Phase 4 / first concrete spell, item, or feature healing consumer.
- **Status:** Deferred
- **Description:** Resolve Healing from spells, items, features, or other
  identified sources, including dice/modifiers and resource consumption.
- **Motivation:** `ApplyHealingCommand.amount` is intentionally already
  resolved and cannot audit or authorize a source/resource.
- **Why deferred:** Spell/item/feature Definitions, inventory/resources, and
  source-specific rules are not implemented.
- **Prerequisites:** One concrete Healing source and its authoritative
  Definition/State/resource lifecycle.
- **Planned approach:** Resolve and consume the source before applying a
  concrete Healing outcome; keep source mechanics outside the HP applier and
  correlate ordered Events when multiple State owners change.
- **Acceptance criteria:** Source identity, dice/modifiers, availability,
  resource consumption, target legality, Healing amount, Event order, and
  persistence failure behavior are deterministic and auditable.
- **References:** [Architecture §3.20](ARCHITECTURE.md#320-minimal-healing--hp-mutation-vertical-slice-g6b),
  [§10.5](ARCHITECTURE.md#105-inventory-state-owner), and
  [DEC-0034](DECISIONS.md#dec-0034--minimal-healing--hp-mutation-slice-g6b-stays-concrete).
- **History:** 2026-08-30 — Created from the Phase 2 closure review; no
  implementation or scheduling commitment.

## DEF-0019

- **Title:** Rest & Recovery
- **Origin:** [P2-HP](#p2-hp) and [P2-HEALING](#p2-healing).
- **Created:** 2026-08-30
- **Target:** Rest & Recovery cross-cutting track.
- **Status:** Deferred
- **Description:** Implement short/long rest recovery of HP and applicable
  resources under authoritative world time and Creature/resource ownership.
- **Motivation:** Rest is a multi-rule recovery action, not merely a direct
  Healing amount.
- **Why deferred:** World time, rest eligibility, hit dice/resources, class
  features, interruption, and source-aware recovery are absent.
- **Prerequisites:** Minimum World time access, recoverable resource State,
  concrete rest Command semantics, and DEF-0018 where Healing sources overlap.
- **Planned approach:** Coordinate owner-specific outcomes/Events without
  direct cross-domain mutation; preserve World State as the sole game-time
  owner.
- **Acceptance criteria:** Rest eligibility/duration/interruption, HP and
  resource recovery, Event order, owner boundaries, persistence atomicity
  scope, and deterministic offline tests are explicit.
- **References:** [Architecture §10.4](ARCHITECTURE.md#104-creature-state-owner),
  [§10.9](ARCHITECTURE.md#109-world-state-owner),
  [Roadmap Phase 2](ROADMAP.md#phase-2--basic-rules), and
  [DEC-0003](DECISIONS.md#dec-0003--game-time-belongs-to-world-state).
- **History:** 2026-08-30 — Created from the Phase 2 closure review; no
  implementation or scheduling commitment.

## DEF-0020

- **Title:** Condition expansion and lifecycle
- **Origin:** [P2-CONDITIONS](#p2-conditions).
- **Created:** 2026-08-30
- **Target:** Phase 3 Combat + Phase 4 Effects, consumer-driven.
- **Status:** Deferred
- **Description:** Add further Condition identities and the source, duration,
  expiry/removal, stacking, immunity, and behavior required by concrete
  mechanics; introduce runtime Condition instances only if those facts need
  independent identity.
- **Motivation:** Effective `POISONED` membership proves behavior-driving State
  but cannot represent broader Condition lifecycles.
- **Why deferred:** Only one Condition and one effect family exist; no source,
  duration, runtime instance, or expiry consumer justifies a framework.
- **Prerequisites:** A concrete next Condition or Poisoned lifecycle consumer
  and its authoritative timing/source data.
- **Planned approach:** Extend one behavior/lifecycle at a time; retain
  `frozenset[Condition]` while membership is sufficient; use `condition_NNN`
  only if source/duration/provenance requires addressable instances.
- **Acceptance criteria:** New identity has concrete behavior; apply/remove/
  expiry and no-op rules are explicit; owner and persistence schema are
  versioned; immunity/stacking/source behavior is tested; no unused framework
  is introduced.
- **References:** [Architecture §3.21](ARCHITECTURE.md#321-condition-state-foundation-g6c1),
  [§4.12](ARCHITECTURE.md#412-canonical-id-registry),
  [DEC-0035](DECISIONS.md#dec-0035--condition-state-foundation-g6c1-persisted-membership-only-state-schema-v4),
  and [DEC-0036](DECISIONS.md#dec-0036--condition-applyremove-pure-domain-mutation-contract-g6c1-group-2).
- **History:** 2026-08-30 — Created from the Phase 2 closure review; no
  implementation or scheduling commitment.

## DEF-0021

- **Title:** Independent advantage/disadvantage source aggregation
- **Origin:** [P2-ABILITY-CHECKS](#p2-ability-checks),
  [P2-SAVING-THROWS](#p2-saving-throws), [P2-SKILLS](#p2-skills),
  [P2-ATTACK-ROLLS](#p2-attack-rolls), and
  [P2-CONDITIONS](#p2-conditions).
- **Created:** 2026-08-30
- **Target:** First slice that introduces a second real roll-mode source.
- **Status:** Deferred
- **Description:** Represent the presence of independent advantage and
  disadvantage sources and derive one final effective `RollMode` for a
  mechanic context.
- **Motivation:** Poisoned is the only current source; final `RollMode` alone
  loses source presence and does not scale safely to cancellation.
- **Why deferred:** A second production source does not yet exist, so source
  identity, scope, precedence, and audit needs are unknown.
- **Prerequisites:** At least one second real source in a concrete Ability,
  Skill, Saving Throw, or Attack consumer.
- **Planned approach:** Model independent source presence first, then derive
  final NORMAL/ADVANTAGE/DISADVANTAGE once. Preserve DEC-0037: do not add
  `combine_roll_modes` and do not combine already-collapsed `RollMode` values
  pairwise.
- **Acceptance criteria:** Multiple same-side and opposing sources are
  represented without information loss; mechanic context is explicit; final
  mode is deterministic; Commands/UI/AI remain non-authoritative; Poisoned
  positive and Saving Throw negative boundaries remain covered.
- **References:** [Architecture §3.12](ARCHITECTURE.md#312-minimal-phase-2-d20-semantics),
  [§3.22](ARCHITECTURE.md#322-minimal-poisoned-behavior-g6c2), and
  [DEC-0037](DECISIONS.md#dec-0037--minimal-poisoned-behavior-uses-mechanic-specific-condition-policies-g6c2).
- **History:** 2026-08-30 — Created from the Phase 2 closure review; no
  implementation or scheduling commitment.

## DEF-0022

- **Title:** Durable Event history, replay and idempotency
- **Origin:** [P2-ABILITY-CHECKS](#p2-ability-checks),
  [P2-STATE-MUTATION](#p2-state-mutation), and every current Event-producing
  Phase 2 slice.
- **Created:** 2026-08-30
- **Target:** Event History & Replay cross-cutting track; trigger-driven and not
  a Phase 3 entry gate.
- **Status:** Deferred
- **Description:** Add durable ordered Event storage, authoritative sequence/ID
  allocation, version-aware decoding, replay/recovery, Command idempotency,
  and an explicit consistency boundary with snapshot persistence.
- **Motivation:** Current Events are immutable in-memory facts and snapshots
  are authoritative, but no EventStore, JSONL append, replay, recovery,
  deduplication, or exactly-once guarantee exists.
- **Why deferred:** `EventStore.append` plus `StateStore.save` creates a
  multi-resource inconsistency window; no current consumer justifies choosing
  a transaction/recovery design.
- **Prerequisites:** A concrete durable-history/recovery/idempotency consumer;
  explicit ordering and failure requirements; inventory of every persisted
  Event type/version and applicable concrete applier.
- **Planned approach:** Design storage and consistency from required recovery
  guarantees; decode by explicit Event type/version without rewriting history;
  keep concrete appliers unless replay proves a narrow dispatch boundary. Track
  `AbilityCheckResolvedPayloadV1`/V1 builder cleanup here only when durable
  decoding provides a real migration, retention, or removal trigger; do not
  create a separate cleanup DEF.
- **Acceptance criteria:** Ordered append and ID allocation are durable;
  unknown type/version behavior is explicit; replay produces validated State
  or a defined failure; Command retries are deterministic; snapshot/Event
  crash windows and recovery are specified and tested; no-op Damage/Healing/
  Condition duplicates are addressed; legacy Ability Check V1 retention or
  removal has a tested migration policy.
- **References:** [Architecture §3.18](ARCHITECTURE.md#318-state-mutation-foundation-g5),
  [§9.10](ARCHITECTURE.md#910-idempotency),
  [§12.10](ARCHITECTURE.md#1210-event-serialization),
  [§12.11](ARCHITECTURE.md#1211-event-ordering),
  [DEC-0012](DECISIONS.md#dec-0012--minimal-phase-1-event-model-contract),
  [DEC-0019](DECISIONS.md#dec-0019--ability-check-result-and-event-metadata-boundaries),
  and [DEC-0032](DECISIONS.md#dec-0032--first-authoritative-state-mutation-uses-snapshot-authoritative-event-driven-replacement).
- **History:** 2026-08-30 — Created from the Phase 2 closure review; no
  implementation or scheduling commitment.
