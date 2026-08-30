# Roadmap

Фазы разработки AI D&D Engine.

Другие документы: [`../README.md`](../README.md) — обзор проекта · [`ARCHITECTURE.md`](ARCHITECTURE.md) — текущий канонический контракт · [`DECISIONS.md`](DECISIONS.md) — append-only мотивация и история решений · [`DEFERRED.md`](DEFERRED.md) — подчинённый companion закрытия Phase 2 и реестр продолжений · [`../CLAUDE.md`](../CLAUDE.md) — выжимка правил для AI-агента.

Каждая фаза реализуется в рамках контрактов из `ARCHITECTURE.md`. Опорные разделы указаны под заголовком фазы.

`ARCHITECTURE.md = current canonical contract`; `DECISIONS.md = append-only rationale/history`.

---

## Phase 0 — Foundation

> Контракты: Architecture Foundation, Application Layers, Contracts, ID System,
> State Ownership, Serialization Rules.

- [x] Canonical architecture documented
- [x] Application/Domain/Infrastructure package skeleton
- [x] Python package bootstrap through `pyproject.toml`
- [x] Package import smoke test
- [x] Architecture contract consistency pass
- [x] Architectural decision log
- [x] Repository placeholder/data hygiene
- [x] Current-vs-planned documentation alignment
- [x] Minimal GitHub Actions pytest workflow

### Definition of Done

- `pip install -e ".[dev]"` работает в чистом Python 3.12 environment;
- `import dnd_engine` работает;
- весь `pytest` проходит;
- package skeleton соответствует §2;
- в tracked repository нет 0-byte `.json` placeholders;
- Architecture/README/CLAUDE не конфликтуют по Event Envelope, runtime IDs, State Ownership и Pydantic boundary;
- GitHub Actions workflow выполняет тот же pytest suite;
- Phase 1 может начинаться без изменения Foundation contracts.

Phase 0 подготовила фундамент для завершённой **Phase 1 — Core**.

---

## Phase 1 — Core

> Контракты: [§3.1 Definition](ARCHITECTURE.md#31-definition-contract) · [§3.2 State](ARCHITECTURE.md#32-state-contract) · [§4 ID System](ARCHITECTURE.md#4-id-system) · [§8 Event Envelope](ARCHITECTURE.md#8-event-envelope) · [§12.10 Event Serialization](ARCHITECTURE.md#1210-event-serialization)

* [x] `CampaignState`
* [x] `CreatureState`
* [x] `AbilityScores`
* [x] `ItemDefinition`
* [x] `WeaponDefinition`
* [x] `MonsterDefinition`
* [x] Dice Engine
* [x] Event model
* [x] State Store

**Phase 1 — Core: COMPLETE.** Все перечисленные Core contracts реализованы и
покрыты соответствующими automated tests. Новые требования задним числом в
Definition of Done Phase 1 не добавляются.

## Phase 2 — Basic Rules

> Контракты: [§3.5 ResolutionResult](ARCHITECTURE.md#35-resolutionresult-contract) · [§3.10 Ability Check vertical slice](ARCHITECTURE.md#310-minimal-phase-2-ability-check-vertical-slice) · [§1.7 Random Number Generation](ARCHITECTURE.md#17-random-number-generation) · [§9 Command Envelope](ARCHITECTURE.md#9-command-envelope) · [§3.18 State Mutation Foundation](ARCHITECTURE.md#318-state-mutation-foundation-g5) · [§3.19 Minimal Damage → HP mutation vertical slice (G6A)](ARCHITECTURE.md#319-minimal-damage--hp-mutation-vertical-slice-g6a) · [§3.20 Minimal Healing → HP mutation vertical slice (G6B)](ARCHITECTURE.md#320-minimal-healing--hp-mutation-vertical-slice-g6b) · [§3.21 Condition State foundation (G6C1)](ARCHITECTURE.md#321-condition-state-foundation-g6c1) · [§3.22 Minimal Poisoned behavior (G6C2)](ARCHITECTURE.md#322-minimal-poisoned-behavior-g6c2) · [§3.24 Phase 2 Closure Contract](ARCHITECTURE.md#324-phase-2-closure-contract)

* [x] Ability checks — COMPLETE ([P2-ABILITY-CHECKS](DEFERRED.md#p2-ability-checks)).
* [x] Proficiency foundation — broader scope PARTIAL ([P2-PROFICIENCY](DEFERRED.md#p2-proficiency); [DEF-0001](DEFERRED.md#def-0001), [DEF-0002](DEFERRED.md#def-0002), [DEF-0003](DEFERRED.md#def-0003)).
* [x] Character saving throw foundation — broader scope PARTIAL ([P2-SAVING-THROWS](DEFERRED.md#p2-saving-throws); [DEF-0004](DEFERRED.md#def-0004), [DEF-0005](DEFERRED.md#def-0005)).
* [x] Character skill-check foundation — broader scope PARTIAL ([P2-SKILLS](DEFERRED.md#p2-skills); [DEF-0001](DEFERRED.md#def-0001), [DEF-0006](DEFERRED.md#def-0006), [DEF-0007](DEFERRED.md#def-0007), [DEF-0008](DEFERRED.md#def-0008)).
* [x] Armor Class foundation — broader scope PARTIAL ([P2-ARMOR-CLASS](DEFERRED.md#p2-armor-class); [DEF-0009](DEFERRED.md#def-0009), [DEF-0010](DEFERRED.md#def-0010)).
* [x] Attack-roll foundation — broader scope PARTIAL ([P2-ATTACK-ROLLS](DEFERRED.md#p2-attack-rolls); [DEF-0011](DEFERRED.md#def-0011), [DEF-0012](DEFERRED.md#def-0012), [DEF-0013](DEFERRED.md#def-0013), [DEF-0014](DEFERRED.md#def-0014)).
* [x] State Mutation Foundation (G5) — COMPLETE ([P2-STATE-MUTATION](DEFERRED.md#p2-state-mutation)).
* [x] Creature HP foundation — broader scope PARTIAL ([P2-HP](DEFERRED.md#p2-hp); [DEF-0015](DEFERRED.md#def-0015), [DEF-0016](DEFERRED.md#def-0016)).
* [x] Direct Damage → HP foundation — broader scope PARTIAL ([P2-DAMAGE](DEFERRED.md#p2-damage); [DEF-0013](DEFERRED.md#def-0013), [DEF-0017](DEFERRED.md#def-0017)).
* [x] Direct Healing → HP foundation — broader scope PARTIAL ([P2-HEALING](DEFERRED.md#p2-healing); [DEF-0018](DEFERRED.md#def-0018), [DEF-0019](DEFERRED.md#def-0019)).
* [x] Condition State foundation + Poisoned behavior — broader scope PARTIAL ([P2-CONDITIONS](DEFERRED.md#p2-conditions); [DEF-0020](DEFERRED.md#def-0020), [DEF-0021](DEFERRED.md#def-0021)).

`State Mutation Foundation (G5)` (§3.18) fixes the canonical contract for
authoritative state-mutating Commands: read-only loaded-snapshot input,
transition-specific mutation scope, Event → State application, replacement
State construction, persistence ordering, save-failure semantics, and the
exact MVP atomicity boundary. Four concrete production consumers now implement
that contract end-to-end: Damage, Healing, Apply Condition, and Remove
Condition.

G6A (§3.19) implements direct `Damage → current_hp`:

```text
ApplyDamageCommand → resolve_damage → DamageApplied V1
→ concrete CreatureState applier → replacement StateSnapshot
→ StateStore.save()
```

G6B (§3.20) implements the parallel minimal direct Healing slice:

```text
ApplyHealingCommand → resolve_healing → HealingApplied V1
→ concrete CreatureState applier → replacement StateSnapshot
→ StateStore.save()
```

The post-G6B comparison of both implementations retained the verdict
`KEEP CONCRETE`: their gameplay math and integrity inputs remain distinct, and
the shared syntax/sequencing does not justify a generic HP mutation primitive,
Event applier, mutation handler, registry, or transaction abstraction.

The completed HP, Damage, and Healing foundation items do not implement healing
sources/resources, spells/items/potions, temporary HP,
death/unconscious/death saves, the broader HP lifecycle, Attack → Damage
orchestration, resistance/immunity/vulnerability, or Conditions. That broader
scope is explicitly PARTIAL and continues through the linked `P2-*`/`DEF-*`
records above; it does not reopen Phase 2.

G6C1 (§3.21) implements the parallel Condition State foundation and its full
direct mutation path — State representation through persistence:

```text
ApplyConditionCommand → resolve_condition_application → ConditionApplied V1
RemoveConditionCommand → resolve_condition_removal → ConditionRemoved V1
→ concrete CreatureState applier → replacement StateSnapshot
→ StateStore.save()
```

`CreatureState.conditions: frozenset[Condition]` (currently only `POISONED`)
and State schema V4 landed in Group 1; the pure Domain mutation contract
landed in Group 2; `ApplyConditionHandler`/`RemoveConditionHandler` and their
`StateStore.save()` orchestration — proven end-to-end against the real
`FilesystemStateStore` — landed in Group 3.

G6C2 (§3.22) makes that membership behavior-driving State for exactly one
Condition interpretation: `POISONED` produces disadvantage for Ability Checks,
Character Skill Checks (through the shared ability-check Condition policy),
and Attack Rolls; Saving Throws remain NORMAL. Application reads authoritative
actor Condition membership and passes a mechanic-specific Domain policy's
effective mode into the unchanged resolver boundary. No generic effect or
advantage/disadvantage aggregation framework was introduced. The Condition
State foundation is complete while broader Conditions scope remains PARTIAL:
all other Conditions and all other Poisoned mechanics remain unimplemented and
continue through the linked DEF records.

**Phase 2 — Basic Rules: COMPLETE (foundation scope).** Per
[Architecture §3.24](ARCHITECTURE.md#324-phase-2-closure-contract), reusable
deterministic foundation readiness closes the phase. Linked broader mechanics
remain PARTIAL and move forward to concrete consumers or cross-cutting tracks;
they do not keep Phase 2 open. Rationale: [DEC-0039](DECISIONS.md#dec-0039--phase-2-closes-on-foundation-readiness-with-linked-forward-scope).

## Phase 3 — Combat

> Контракты: [§10.7 Combat State Owner](ARCHITECTURE.md#107-combat-state-owner) · [§3.8 Atomicity](ARCHITECTURE.md#38-atomicity) · [§12.11 Event Ordering](ARCHITECTURE.md#1211-event-ordering)

* [ ] Initiative
* [ ] Turns
* [ ] Zero-HP and combatant eligibility ([DEF-0005](DEFERRED.md#def-0005), [DEF-0015](DEFERRED.md#def-0015))
* [ ] Movement
* [ ] Reactions
* [ ] Opportunity attacks
* [ ] Weapon attacks ([DEF-0011](DEFERRED.md#def-0011))
* [ ] Monster actions ([DEF-0002](DEFERRED.md#def-0002), [DEF-0004](DEFERRED.md#def-0004), [DEF-0012](DEFERRED.md#def-0012))
* [ ] Attack consequences ([DEF-0013](DEFERRED.md#def-0013))
* [ ] Conditions expansion ([DEF-0020](DEFERRED.md#def-0020), [DEF-0021](DEFERRED.md#def-0021))
* [ ] Targeting ([P2-ATTACK-ROLLS](DEFERRED.md#p2-attack-rolls))
* [ ] Cover ([P2-ATTACK-ROLLS](DEFERRED.md#p2-attack-rolls))
* [ ] Visibility ([P2-ATTACK-ROLLS](DEFERRED.md#p2-attack-rolls))

## Phase 4 — Magic

> Контракты: [§10.5 Inventory](ARCHITECTURE.md#105-inventory-state-owner) · [§3.1 Definition](ARCHITECTURE.md#31-definition-contract) · [§8.13 Event naming convention](ARCHITECTURE.md#813-event-naming-convention)

* [ ] Spell definitions
* [ ] Spell slots
* [ ] Spell targeting
* [ ] AoE
* [ ] Saving throw spells ([P2-SAVING-THROWS](DEFERRED.md#p2-saving-throws))
* [ ] Spell attacks ([DEF-0014](DEFERRED.md#def-0014))
* [ ] Source-aware healing ([DEF-0018](DEFERRED.md#def-0018))
* [ ] Effects — consumer-driven AC, temporary-HP, typed-damage, and Condition continuations ([DEF-0010](DEFERRED.md#def-0010), [DEF-0016](DEFERRED.md#def-0016), [DEF-0017](DEFERRED.md#def-0017), [DEF-0020](DEFERRED.md#def-0020), [DEF-0021](DEFERRED.md#def-0021))
* [ ] Equipment & Inventory supporting continuation ([DEF-0009](DEFERRED.md#def-0009), [DEF-0011](DEFERRED.md#def-0011))
* [ ] Concentration

## Phase 5 — World

> Контракты: [§10.9 World State Owner](ARCHITECTURE.md#109-world-state-owner) · [§10.8 Quest](ARCHITECTURE.md#108-quest-state-owner) · [§10.11 Relationship](ARCHITECTURE.md#1011-relationship-state-owner)

* [ ] Locations
* [ ] Maps
* [ ] NPCs ([DEF-0006](DEFERRED.md#def-0006))
* [ ] Factions
* [ ] Relationships
* [ ] Quests
* [ ] World time
* [ ] Knowledge system ([DEF-0007](DEFERRED.md#def-0007))

## Phase 6 — AI DM

> Контракты: [§1.6 AI Layer](ARCHITECTURE.md#16-ai-layer) · [§10.12 AI State Owner](ARCHITECTURE.md#1012-ai-state-owner) · [§9.3 commandId](ARCHITECTURE.md#93-commandid)

* [ ] Natural language → Commands ([DEF-0008](DEFERRED.md#def-0008))
* [ ] AI Context Projection
* [ ] NPC AI
* [ ] Memory
* [ ] Scene narration
* [ ] World generation
* [ ] Encounter generation
* [ ] AI tool calling

## Phase 7 — Web Application

> Контракты: [§2.1 Presentation Layer](ARCHITECTURE.md#21-presentation-layer) · [§1.3 API](ARCHITECTURE.md#13-api) · [§12.7 Pydantic boundary validation](ARCHITECTURE.md#127-pydantic-как-boundary-validation)

* [ ] Backend API
* [ ] Authentication
* [ ] Campaign management
* [ ] Character sheet
* [ ] Combat UI
* [ ] Tactical map
* [ ] Inventory UI
* [ ] Quest UI
* [ ] AI chat
* [ ] Multiplayer

---

## Cross-cutting continuation tracks

* Character Progression → [DEF-0001](DEFERRED.md#def-0001) / [DEF-0003](DEFERRED.md#def-0003)
* Equipment & Inventory → [DEF-0009](DEFERRED.md#def-0009) / [DEF-0011](DEFERRED.md#def-0011)
* Rest & Recovery → [DEF-0019](DEFERRED.md#def-0019)
* Event History & Replay → [DEF-0022](DEFERRED.md#def-0022). This track is trigger-driven and is not a Phase 3 entry gate.

---


# Текущий статус

- ✅ **Phase 0 — Foundation** завершена.
- ✅ **Phase 1 — Core** завершена.
- ✅ **Phase 2 — Basic Rules** завершена в foundation scope.
- ➡️ Текущий этап — **Phase 3 — Combat**.

Порядок работ:

```text
Data Model
    ↓
State Model
    ↓
Command Model
    ↓
Event Model
    ↓
Core Engine
    ↓
Combat
    ↓
Magic
    ↓
World
    ↓
AI DM
    ↓
Web UI
```

---

Архитектурные контракты, которым должна соответствовать каждая реализуемая фаза, описаны в [`ARCHITECTURE.md`](ARCHITECTURE.md).
