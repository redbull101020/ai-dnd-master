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

Следующий этап после Foundation — **Phase 1 — Core**.

---

## Phase 1 — Core

> Контракты: [§3.1 Definition](ARCHITECTURE.md#31-definition-contract) · [§3.2 State](ARCHITECTURE.md#32-state-contract) · [§4 ID System](ARCHITECTURE.md#4-id-system) · [§8 Event Envelope](ARCHITECTURE.md#8-event-envelope) · [§12.10 Event Serialization](ARCHITECTURE.md#1210-event-serialization)

* [ ] `CampaignState`
* [ ] `CreatureState`
* [x] `AbilityScores`
* [x] `ItemDefinition`
* [x] `WeaponDefinition`
* [x] `MonsterDefinition`
* [ ] Dice Engine
* [ ] Event model
* [ ] State Store

## Phase 2 — Basic Rules

> Контракты: [§3.5 ResolutionResult](ARCHITECTURE.md#35-resolutionresult-contract) · [§1.7 Random Number Generation](ARCHITECTURE.md#17-random-number-generation) · [§9 Command Envelope](ARCHITECTURE.md#9-command-envelope)

* [ ] Ability checks
* [ ] Saving throws
* [ ] Skills
* [ ] Proficiency
* [ ] Attack rolls
* [ ] Damage
* [ ] Healing
* [ ] AC
* [ ] HP
* [ ] Conditions

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

✅ **Phase 0 — Foundation** завершена. Текущий этап — **Phase 1 — Core**.

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
