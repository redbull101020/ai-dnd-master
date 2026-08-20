# CLAUDE.md

Правила проекта **AI D&D Engine**. Соблюдай их во всём коде, который пишешь или ревьюишь.

`ARCHITECTURE.md = current canonical contract`; [`docs/DECISIONS.md`](docs/DECISIONS.md) = append-only rationale/history. Этот файл — выжимка. При конфликте выигрывает `docs/ARCHITECTURE.md`; если в задаче встретился случай, не покрытый здесь, сверься с ним, а не додумывай.

В архитектуре сквозная нумерация разделов — ссылайся на них по номеру (`§8.2`). В шапке документа есть таблица быстрого поиска и полное оглавление.

---

## Главный принцип

> AI интерпретирует намерения и ведёт повествование. Engine определяет истину игрового мира.

LLM никогда не решает исход броска, не меняет State напрямую и не определяет, разрешено ли действие. Всё это — детерминированный Rule Engine.

---

## Слои и зависимости

> [§2 Application Layers](docs/ARCHITECTURE.md#2-слои-приложения--application-layers) · [§2.5 Forbidden Dependencies](docs/ARCHITECTURE.md#25-запрещённые-зависимости--forbidden-dependencies)

```text
Presentation   src/dnd_engine/api/
      ↓
Application    src/dnd_engine/application/
      ↓
Domain         src/dnd_engine/domain/          ← ядро, ни от чего не зависит
      ↑
Infrastructure src/dnd_engine/infrastructure/
```

**Domain не импортирует:** FastAPI, SQLAlchemy, SDK LLM-провайдеров, реализацию файловой системы, HTTP-типы, ORM-модели.

Infrastructure реализует интерфейсы, объявленные в Domain. Зависимость всегда направлена внутрь.

Проверка: если Rule Engine нельзя выполнить обычным `python` без сети и HTTP — архитектура нарушена.

---

## Definitions ≠ State

> [§3.1 Definition Contract](docs/ARCHITECTURE.md#31-definition-contract) · [§3.2 State Contract](docs/ARCHITECTURE.md#32-state-contract)

**Definition** — неизменяемое описание из правил, лежит в `rules/dnd_5e/`.
**State** — изменяемый экземпляр в кампании, лежит в `campaigns/campaign_NNN/`.

Обязательные поля любого Definition:

```python
@dataclass(frozen=True)
class Definition:
    id: str
    version: int
```

Definition:
* immutable — во время игровой сессии не мутируется;
* при изменении правила создаётся **новая версия**, старая не правится;
* жизненный цикл: `CREATE → LOAD → READ`. Никаких `UPDATE`.

---

## ID System

> [§4 ID System](docs/ARCHITECTURE.md#4-id-system) · [§4.13 Сводная таблица](docs/ARCHITECTURE.md#413-сводная-таблица-id--id-reference-table)

| Сущность | Формат | Пример |
| --- | --- | --- |
| Ruleset | `snake_case` | `dnd_5e` |
| Definition | `snake_case` | `longsword` |
| Character | `character_NNN` | `character_001` |
| Player Identity | `player_NNN` | `player_001` |
| NPC | `npc_NNN` | `npc_001` |
| Monster Instance | `monster_NNN` | `monster_001` |
| Item Instance | `item_NNN` | `item_001` |
| Combat | `combat_NNN` | `combat_001` |
| Quest State | `quest_NNN` | `quest_001` |
| Objective | `objective_NNN` | `objective_001` |
| Location Instance | `location_NNN` | `location_001` |
| Effect State | `effect_NNN` | `effect_001` |
| Condition State | `condition_NNN` | `condition_001` |
| Command | `command_NNNNNN` | `command_000001` |
| Event | `event_NNNNNN` | `event_000001` |

Жёсткие правила:
* **Instance ID никогда не повторяет Definition ID.** Экземпляр меча — `item_001` с полем `definitionId: "longsword"`, а не `longsword_001`.
* ID не переиспользуется после удаления сущности.
* ID не изменяется в течение жизни сущности.

---

## Command Envelope

> [§9.1 Схема](docs/ARCHITECTURE.md#91-каноническая-схема-command--canonical-command-schema) · [§9.2 Поля](docs/ARCHITECTURE.md#92-поля-command-envelope--command-envelope-fields) · [§9.8 Command ≠ Event](docs/ARCHITECTURE.md#98-command--event)

```json
{
  "commandId": "command_000001",
  "type": "AttackCommand",
  "campaignId": "campaign_001",
  "actorId": "character_001",
  "payload": {
    "targetId": "monster_001",
    "weaponId": "item_001"
  }
}
```

Обязательны все пять полей. Специфика команды живёт **только** внутри `payload` — не выноси `targetId`/`weaponId` на верхний уровень.

Жизненный цикл: `Received → Rejected | Accepted → Resolving → Completed | Failed`.

Command — намерение, а не результат. Команда не изменяет State напрямую: она порождает Events, и уже они меняют состояние.

---

## Event Envelope

> [§8.1 Схема](docs/ARCHITECTURE.md#81-каноническая-схема-event--canonical-event-schema) · [§8.2 Поля](docs/ARCHITECTURE.md#82-поля-event-envelope--event-envelope-fields) · [§8.13 Naming](docs/ARCHITECTURE.md#813-event-naming-convention)

```json
{
  "eventId": "event_000124",
  "commandId": "command_000001",
  "type": "DamageApplied",
  "version": 1,
  "campaignId": "campaign_001",
  "timestamp": "2026-08-20T18:42:10Z",
  "actorId": "character_001",
  "causedBy": "event_000123",
  "payload": {
    "targetId": "monster_001",
    "amount": 10,
    "damageType": "slashing"
  }
}
```

| Поле | Обязательное |
| --- | --- |
| `eventId`, `commandId`, `type`, `version`, `campaignId`, `timestamp`, `payload` | да |
| `actorId`, `causedBy` | нет (nullable) |

Правила:
* Event — **факт в прошедшем времени**: `DamageApplied`, `AttackResolved`, `CreatureMoved`. Не `ApplyDamage`, не `DoAttack`.
* Event immutable: не редактируется и не удаляется после записи. Ошибку исправляет новое компенсирующее событие.
* `causedBy` связывает событие с породившим его событием — цепочку не терять.
* Event описывает доменный факт, а не техническую деталь реализации.

---

## State Ownership

> [§10 State Ownership](docs/ARCHITECTURE.md#10-state-ownership) · [§10.13 Owner Matrix](docs/ARCHITECTURE.md#1013-owner-matrix)

У каждого State-объекта ровно один владелец, и только он его изменяет:

| State | Owner |
| --- | --- |
| `CampaignState` | Campaign Engine |
| `WorldState` | World Engine |
| `CreatureState` | Creature Domain |
| `InventoryState` | Inventory Engine |
| `EquipmentState` | Equipment Engine |
| `CombatState` | Combat Engine |
| `QuestState` | Quest Engine |
| `FactionState` | Faction Engine |
| `RelationshipState` | Relationship Engine |
| `EffectState` | Effect Engine |
| `AIState` | AI subsystem |

Остальные системы имеют только read-доступ. Прямая мутация чужого State — архитектурная ошибка, даже если это «быстрее».

Прежде чем добавить новую сущность, ответь на три вопроса:
1. Это Definition или State?
2. Какой у неё ID и формат?
3. Кто владеет её жизненным циклом, какие Commands её меняют и какие Events это фиксируют?

---

## Случайность

> [§1.7 Random Number Generation](docs/ARCHITECTURE.md#17-random-number-generation)

Вся случайность — только через `DiceEngine`:

```python
dice.roll("1d20")        # правильно
random.randint(1, 20)    # запрещено внутри Rule Engine
```

Это нужно для тестов, replay, отладки и детерминированных симуляций. Seed задаётся снаружи.

---

## Сериализация

> [§12.1 Где разрешена](docs/ARCHITECTURE.md#121-где-разрешена-сериализация--where-serialization-is-allowed) · [§12.2 Форматы](docs/ARCHITECTURE.md#122-канонические-форматы--canonical-formats) · [§12.21 Запрещённые практики](docs/ARCHITECTURE.md#1221-запрещённые-практики--forbidden-practices)

* Сериализации **нет внутри Rule Engine.** Resolver не открывает файлы и не знает про JSON.
* Чтение и запись — только в Infrastructure, через Serializer / Repository.
* **JSON** — Definitions, state snapshots, config, AI context, API DTO.
* **JSONL** — append-only потоки: `events/events.jsonl`, command log. Одна строка = один JSON-объект.

---

## Тесты

> [§1.5 Tests](docs/ARCHITECTURE.md#15-tests)

`pytest`. Покрываем в первую очередь: Rule Engine, Resolvers, Dice Engine, переходы State, обработчики Events, сериализацию.

**LLM не используется в тестах игрового ядра.** Тест правил должен быть детерминированным и проходить офлайн.

---

## Стиль кода

* Python 3.12+, type hints везде.
* Domain — `@dataclass` (`frozen=True` для Definitions и Value Objects).
* Pydantic v2 — только на границах: API DTO и валидация входных данных. Не тащи Pydantic в Domain-логику.
* Enums вместо строковых констант для типов урона, состояний, условий.
* Имена сущностей — как в `docs/ARCHITECTURE.md`; не изобретай синонимы (`CreatureState`, а не `MonsterState`/`EntityState`).

---

## Работа с документацией

* Меняешь контракт (поле Envelope, формат ID, владельца State) → сначала обнови `docs/ARCHITECTURE.md`, затем добавь новую запись в `docs/DECISIONS.md`; старые accepted записи не переписывай.
* `README.md` — обзорный документ. Не добавляй в него JSON-схемы, датаклассы и списки полей: они дублируются и разъезжаются. Вместо этого — ссылка на нужный раздел архитектуры.
* Новую сущность документируй в `docs/ARCHITECTURE.md` в момент добавления, а не «потом».

---

## Чего не делать

* Не помещать игровые правила в промпт LLM — они принадлежат Engine и Definitions.
* Не давать AI-слою прямой доступ ко всему State: он получает ограниченную проекцию контекста.
* Не мутировать Definitions во время сессии.
* Не менять State в обход владельца.
* Не редактировать и не удалять уже записанные Events.
* Не вызывать `random` напрямую в доменной логике.
* Не импортировать инфраструктурные библиотеки в Domain.
