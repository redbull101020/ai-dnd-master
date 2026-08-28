# Roadmap

Фазы разработки AI D&D Engine.

Другие документы: [`../README.md`](../README.md) — обзор проекта · [`ARCHITECTURE.md`](ARCHITECTURE.md) — текущий канонический контракт · [`DECISIONS.md`](DECISIONS.md) — append-only мотивация и история решений · [`../CLAUDE.md`](../CLAUDE.md) — выжимка правил для AI-агента.

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

> Контракты: [§3.5 ResolutionResult](ARCHITECTURE.md#35-resolutionresult-contract) · [§3.10 Ability Check vertical slice](ARCHITECTURE.md#310-minimal-phase-2-ability-check-vertical-slice) · [§1.7 Random Number Generation](ARCHITECTURE.md#17-random-number-generation) · [§9 Command Envelope](ARCHITECTURE.md#9-command-envelope) · [§3.18 State Mutation Foundation](ARCHITECTURE.md#318-state-mutation-foundation-g5) · [§3.19 Minimal Damage → HP mutation vertical slice (G6A)](ARCHITECTURE.md#319-minimal-damage--hp-mutation-vertical-slice-g6a) · [§3.20 Minimal Healing → HP mutation vertical slice (G6B)](ARCHITECTURE.md#320-minimal-healing--hp-mutation-vertical-slice-g6b) · [§3.21 Condition State foundation (G6C1)](ARCHITECTURE.md#321-condition-state-foundation-g6c1)

* [x] Ability checks
* [ ] Proficiency
* [ ] Saving throws
* [ ] Skills
* [x] AC
* [ ] Attack rolls
* [x] State Mutation Foundation (G5)
* [ ] HP
* [ ] Damage
* [ ] Healing
* [ ] Conditions

`State Mutation Foundation (G5)` (§3.18) fixes the canonical contract for
authoritative state-mutating Commands: read-only loaded-snapshot input,
transition-specific mutation scope, Event → State application, replacement
State construction, persistence ordering, save-failure semantics, and the
exact MVP atomicity boundary. Two concrete production consumers now implement
that contract end-to-end.

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

The broad `HP`, `Damage`, and `Healing` checkboxes intentionally remain open.
These minimal direct slices do not implement healing sources/resources,
spells/items/potions, temporary HP, death/unconscious/death saves, the broader
HP lifecycle, Attack → Damage orchestration, resistance/immunity/vulnerability,
or Conditions.

G6C1 (§3.21) implements the parallel Condition State foundation and its full
direct mutation path — State representation through persistence, but not any
gameplay effect:

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
`FilesystemStateStore` — landed in Group 3. The `[ ] Conditions` checkbox
intentionally remains open: no `Poisoned` (or any other) gameplay effect,
`RollMode`/d20 interaction, Effect framework, or stateful Condition-instance
model is implemented.

## Phase 3 — Combat

> Контракты: [§10.7 Combat State Owner](ARCHITECTURE.md#107-combat-state-owner) · [§3.8 Atomicity](ARCHITECTURE.md#38-atomicity) · [§12.11 Event Ordering](ARCHITECTURE.md#1211-event-ordering)

* [ ] Initiative
* [ ] Turns
* [ ] Movement
* [ ] Reactions
* [ ] Opportunity attacks
* [ ] Targeting
* [ ] Cover
* [ ] Visibility

## Phase 4 — Magic

> Контракты: [§10.5 Inventory](ARCHITECTURE.md#105-inventory-state-owner) · [§3.1 Definition](ARCHITECTURE.md#31-definition-contract) · [§8.13 Event naming convention](ARCHITECTURE.md#813-event-naming-convention)

* [ ] Spell definitions
* [ ] Spell slots
* [ ] Spell targeting
* [ ] AoE
* [ ] Saving throw spells
* [ ] Spell attacks
* [ ] Effects
* [ ] Concentration

## Phase 5 — World

> Контракты: [§10.9 World State Owner](ARCHITECTURE.md#109-world-state-owner) · [§10.8 Quest](ARCHITECTURE.md#108-quest-state-owner) · [§10.11 Relationship](ARCHITECTURE.md#1011-relationship-state-owner)

* [ ] Locations
* [ ] Maps
* [ ] NPCs
* [ ] Factions
* [ ] Relationships
* [ ] Quests
* [ ] World time
* [ ] Knowledge system

## Phase 6 — AI DM

> Контракты: [§1.6 AI Layer](ARCHITECTURE.md#16-ai-layer) · [§10.12 AI State Owner](ARCHITECTURE.md#1012-ai-state-owner) · [§9.3 commandId](ARCHITECTURE.md#93-commandid)

* [ ] Natural language → Commands
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


# Текущий статус

- ✅ **Phase 0 — Foundation** завершена.
- ✅ **Phase 1 — Core** завершена.
- ➡️ Текущий этап — **Phase 2 — Basic Rules**.

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
