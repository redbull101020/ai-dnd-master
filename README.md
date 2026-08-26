# AI D&D Engine

> Машиночитаемый игровой движок для веб-версии Dungeons & Dragons с AI Dungeon Master.

**AI D&D Engine** отделяет **правила D&D, состояние игры, события и искусственный интеллект** друг от друга.

Главный принцип проекта:

> **AI интерпретирует намерения и ведёт повествование. Engine определяет истину игрового мира.**

ИИ не решает, попал ли персонаж, сколько нанесено урона или можно ли совершить действие. Эти решения принимает детерминированный Rule Engine.

---

## Документация

Этот файл — **обзорный**. Он объясняет идею и общую архитектуру, но не содержит схем и контрактов.

| Документ | Содержание |
| --- | --- |
| `README.md` | Идея, принципы, архитектура верхнего уровня, быстрый старт |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | **Источник истины.** Контракты, Envelope-схемы, ID System, слои, State Ownership, правила сериализации |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Append-only журнал мотивации и истории архитектурных решений |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Фазы разработки и текущий статус |
| [`docs/DEVELOPMENT_LOG.md`](docs/DEVELOPMENT_LOG.md) | Append-only история выполненных development iterations; не источник контрактов или статуса |
| `CLAUDE.md` | Выжимка правил проекта для AI-агента |

`ARCHITECTURE.md = current canonical contract`; `DECISIONS.md = append-only rationale/history`. При любом расхождении приоритет у `docs/ARCHITECTURE.md`.

---

## Основная идея

Проект представляет D&D как систему из трёх слоёв ответственности:

```text
                  ┌─────────────────────┐
                  │      AI DM          │
                  │                     │
                  │ Intent              │
                  │ NPC behavior        │
                  │ Narration           │
                  │ Story generation    │
                  └──────────┬──────────┘
                             │
                     Commands / Context
                             │
                             ▼
                  ┌─────────────────────┐
                  │    D&D ENGINE       │
                  │                     │
                  │ Validation          │
                  │ Rules               │
                  │ Dice                │
                  │ Resolution          │
                  │ State mutation      │
                  └──────────┬──────────┘
                             │
                           Events
                             │
                             ▼
                  ┌─────────────────────┐
                  │     GAME STATE      │
                  │                     │
                  │ Characters          │
                  │ World               │
                  │ Combat              │
                  │ Quests              │
                  │ Inventory           │
                  └─────────────────────┘
```

Игрок взаимодействует с игрой естественным языком:

> «Подкрадываюсь к стражнику и пытаюсь нанести ему удар.»

AI преобразует намерение в **Command** — структурированное намерение с обязательными `commandId`, `type`, `campaignId`, `actorId` и `payload`.

Engine проверяет возможность действия, применяет правила, бросает кубики, изменяет состояние и порождает **Events** — неизменяемые факты произошедшего.

Только после этого AI получает результат и описывает его игроку.

> Канонические схемы: [§9.1 Command Envelope](docs/ARCHITECTURE.md#91-каноническая-схема-command--canonical-command-schema) · [§8.1 Event Envelope](docs/ARCHITECTURE.md#81-каноническая-схема-event--canonical-event-schema)

---

## Архитектурные принципы

### 1. AI не является источником истины

LLM отвечает за понимание намерения, поведение NPC и повествование. Он не определяет результат броска, не меняет состояние напрямую и не решает, разрешено ли действие.

### 2. Engine является источником игровой истины

Все проверки, броски, расчёты урона, перемещения и изменения состояния проходят через Rule Engine ([§10 State Ownership](docs/ARCHITECTURE.md#10-state-ownership)). Результат воспроизводим и тестируем без участия LLM.

### 3. Definitions ≠ State

**Definition** — неизменяемое описание из правил (`longsword`, `fireball`, `goblin`). Загружается один раз и не меняется во время сессии.

**State** — изменяемый экземпляр в конкретной кампании (`item_001`, `monster_001`), ссылающийся на Definition отдельным полем, например `monster_001` → `definitionId: goblin`.

Экземпляр никогда не называется так же, как Definition — почему, разобрано в [§4.3](docs/ARCHITECTURE.md#43-почему-state-id-не-должен-повторять-definition-id--state-id-vs-definition-id). Форматы всех ID — в [§4.13](docs/ARCHITECTURE.md#413-сводная-таблица-id--id-reference-table).

### 4. Events являются историей изменений

По каноническому контракту состояние меняется только через события. Событие —
факт, который уже произошёл; оно неизменяемо и не удаляется. Сейчас реализованы
модель `GameEvent`, сериализация Event и первый read-only
`AbilityCheckResolved`, но production Event Log и replay subsystem ещё нет.
Durable ordered Events, version-aware decoding и deterministic Event → State
application в будущем позволят реализовать recovery/replay; текущий
`state.json` пока нельзя восстановить из persisted Event history.

### 5. Определённость важнее удобства

Вся случайность проходит через `DiceEngine` ([§1.7](docs/ARCHITECTURE.md#17-random-number-generation)). Прямой вызов `random` внутри правил запрещён — это ломает тестируемость и replay.

---

## Архитектура

Четыре слоя с однонаправленными зависимостями:

```text
Presentation      api/              FastAPI, WebSocket, DTO
      ↓
Application       application/      use cases, оркестрация, handlers
      ↓
Domain            domain/           правила, состояние, события  ← ядро
      ↑
Infrastructure    infrastructure/   persistence, LLM, RNG, filesystem
```

**Domain ни от чего не зависит.** Он не импортирует FastAPI, SQLAlchemy, SDK LLM-провайдеров или реализацию файловой системы. Infrastructure зависит от Domain через интерфейсы, а не наоборот.

Благодаря этому Domain rules и concrete resolvers можно выполнять как обычный
Python-код, без HTTP и без сети. Общий `GameEngine.execute(...)` API пока не
реализован и не требуется для первого Phase 2 vertical slice.

> Подробно: [§2 Слои приложения](docs/ARCHITECTURE.md#2-слои-приложения--application-layers) · [§2.5 Запрещённые зависимости](docs/ARCHITECTURE.md#25-запрещённые-зависимости--forbidden-dependencies)

---

## Цикл игрового действия

```text
Player input (natural language)
        ↓
AI  →  Command
        ↓
Validation           доступно ли действие, есть ли ресурсы, в радиусе ли цель
        ↓
Resolution           броски, модификаторы, правила
        ↓
Events               факты произошедшего
        ↓
State mutation       через владельца состояния
        ↓
AI  →  Narration
```

Ключевое различие: **Command — намерение, Event — факт.** Команда может быть отклонена или провалиться; событие описывает только то, что действительно случилось.

---

## Структура проекта

```text
ai-dnd-master/
│
├── README.md
├── CLAUDE.md
├── pyproject.toml
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DECISIONS.md
│   ├── ROADMAP.md
│   └── DEVELOPMENT_LOG.md
│
├── src/
│   └── dnd_engine/
│       ├── api/                 # Presentation
│       ├── application/         # commands, handlers, services
│       ├── domain/              # definitions, state, events, rules, value_objects
│       └── infrastructure/      # persistence, llm, random
│
├── rules/
│   └── dnd_5e/                  # Definitions: classes, spells, monsters, items, ...
│
├── campaigns/
│   └── campaign_001/            # campaign-specific state and event storage
│
└── tests/
    ├── rules/
    ├── combat/
    ├── spells/
    ├── movement/
    └── scenarios/
```

`rules/` — данные правил, общие для всех кампаний.
`campaigns/` — состояние конкретных партий.

---

## Хранение данных

```text
Event Log  +  Materialized State
```

**Implemented now:**

* filesystem snapshot persistence в `state.json`;
* immutable `GameEvent` model;
* чистый `EventSerializer` без filesystem I/O.

**Planned / deferred:**

* runtime `EventStore` и append в канонический потоковый формат
  `events/events.jsonl` ([§12.10](docs/ARCHITECTURE.md#1210-event-serialization));
* authoritative persistence порядка Events;
* Event → State projection, recovery и replay.

Наличие пути `events/events.jsonl` в архитектуре или scaffold не означает, что
работающий EventStore уже существует. На этапе MVP используется файловая
система; переход на SQLite/PostgreSQL не должен требовать изменения Domain
rules, поскольку persistence доступна через `StateStore` port.

---

## Технологический стек

### Current implemented stack

```text
Python 3.12+
JSON / JSONL
pytest
setuptools / pyproject.toml
```

### Planned application/boundary stack

```text
FastAPI
WebSocket
Pydantic v2
LLM provider adapters
```

Планируемые зависимости добавляются только на соответствующей фазе Roadmap. FastAPI application пока не реализован. В тестах игрового ядра LLM не используется.

---

## Быстрый старт

```bash
git clone <repo-url>
cd ai-dnd-master

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

python -m pip install -e ".[dev]"
python -m pytest
python -m mypy src/dnd_engine
```

Runnable API появится на соответствующей фазе Roadmap; текущий Core repository
проверяется установкой пакета и pytest. Phase 2 начата; первый read-only Ability
Check vertical slice реализован.

---

## Принципы разработки

**Rules are code/data, not prompts** — правила живут в Engine и Definitions, а не в системном промпте LLM.

**State is authoritative** — UI и AI только отображают и запрашивают состояние.

**Commands are intentions** — команда не означает успех.

**Events are facts** — событие описывает то, что уже произошло.

**Definitions are immutable** — изменение правила создаёт новую версию, а не мутирует старую.

**Every state has an owner** — у каждого State-объекта есть система, отвечающая за его изменение.

---

## Философия проекта

> **AI рассказывает историю. Engine решает, что в этой истории действительно произошло.**

Игрок говорит:

> «Прыгаю через пропасть.»

AI понимает намерение. Engine решает:

```text
возможен ли прыжок
↓
какое расстояние
↓
какая проверка и какой DC
↓
результат броска
↓
успех / провал
↓
урон / падение / изменение позиции
```

И только затем AI рассказывает:

> «Ты разбегаешься и прыгаешь в темноту...»

---

## Конечная цель

Веб-платформа, где AI Dungeon Master ведёт полноценную длительную D&D-кампанию, сохраняя при этом:

* детерминированные игровые правила;
* постоянное состояние мира;
* историю всех значимых событий;
* память NPC;
* квесты и последствия действий.

---

## Status

- ✅ **Phase 0 — Foundation** завершена.
- ✅ **Phase 1 — Core** завершена.
- ➡️ Текущий этап: **Phase 2 — Basic Rules**.

Текущие фазы и приоритеты — в [`docs/ROADMAP.md`](docs/ROADMAP.md).

---

## License

Проект находится в разработке. Лицензия, используемые игровые данные и источники контента должны быть определены отдельно перед публикацией полноценного набора правил и контента.
