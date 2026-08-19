````markdown
# AI-D&D

Test code changes

> Persistent AI Dungeon Master system for D&D campaigns.

AI-D&D — это система для проведения длительных D&D-кампаний с использованием LLM в роли Dungeon Master.

Главная архитектурная задача проекта — отделить **AI-контекст** от **состояния самой игры**.

LLM не должна хранить всю кампанию в контекстном окне одного чата. Кампания существует независимо от конкретного чата и может быть продолжена в новом контексте.

---

## Содержание

- [Концепция](#концепция)
- [Архитектурный принцип](#архитектурный-принцип)
- [Основные компоненты](#основные-компоненты)
- [Структура проекта](#структура-проекта)
- [Источники истины](#источники-истины)
- [Поток игрового действия](#поток-игрового-действия)
- [Жизненный цикл хода](#жизненный-цикл-хода)
- [Система памяти](#система-памяти)
- [Смена AI-чата](#смена-ai-чата)
- [Data Model](#data-model)
- [Engine](#engine)
- [AI-DM](#ai-dm)
- [Events](#events)
- [Validation](#validation)
- [Git и внешние инструменты](#git-и-внешние-инструменты)
- [MVP](#mvp)
- [Roadmap](#roadmap)
- [Основные архитектурные правила](#основные-архитектурные-правила)

---

# Концепция

Обычная игра с AI-DM сталкивается с фундаментальной проблемой:

```text
Длинная кампания
       │
       ▼
Длинный чат
       │
       ▼
Контекстное окно переполняется
       │
       ▼
Старые сообщения теряются / сжимаются
       │
       ▼
AI начинает забывать состояние игры
````

AI-D&D решает проблему иначе:

```text
                    CAMPAIGN
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       STATE        ENTITIES       EVENTS
          │            │            │
          └────────────┼────────────┘
                       │
                       ▼
                 AI CONTEXT
                       │
                       ▼
                    AI-DM
```

Чат является **интерфейсом**, а не хранилищем игры.

---

# Архитектурный принцип

Система разделена на три основных слоя:

```text
┌──────────────────────────────────────────┐
│                  PLAYER                  │
│                                          │
│  "Я атакую гоблина мечом"                │
└────────────────────┬─────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────┐
│                 AI-DM                    │
│                                          │
│  • понимает намерение игрока             │
│  • ведёт повествование                   │
│  • играет NPC                            │
│  • принимает DM-решения                  │
│  • формирует запросы к Engine            │
└────────────────────┬─────────────────────┘
                     │
                  intent
                     │
                     ▼
┌──────────────────────────────────────────┐
│                  ENGINE                  │
│                                          │
│  • dice                                  │
│  • checks                                │
│  • combat                                │
│  • damage                                │
│  • effects                               │
│  • inventory                             │
│  • state mutations                       │
│  • validation                            │
└────────────────────┬─────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────┐
│                PERSISTENCE               │
│                                          │
│  characters/                             │
│  world/                                  │
│  quests/                                 │
│  items/                                  │
│  campaign/state.json                     │
│  events/                                 │
│  sessions/                               │
└──────────────────────────────────────────┘
```

### Ключевое правило

**AI не является источником истины для игровой механики.**

AI может сказать:

> «Я хочу атаковать гоблина».

Но окончательный результат:

> Hit / Miss / Damage / Conditions / HP

определяет Engine.

---

# Основные компоненты

| Компонент             | Ответственность                        |
| --------------------- | -------------------------------------- |
| `AI-DM`               | Интерпретация, narration, NPC, DM      |
| `Engine`              | Игровая механика и расчёты             |
| `campaign/state.json` | Текущее глобальное состояние           |
| `characters/`         | Состояние персонажей                   |
| `world/`              | Мир, NPC, локации, фракции             |
| `quests/`             | Квесты и их состояние                  |
| `items/`              | Предметы                               |
| `rules/`              | Машиночитаемые правила                 |
| `rules.md`            | House Rules и договорённости           |
| `schemas/`            | Валидация структуры данных             |
| `events/`             | История изменений                      |
| `sessions/`           | История AI-сессий                      |
| `handoff`             | Передача кампании между AI-контекстами |

---

# Структура проекта

Текущая целевая структура:

```text
AI-DND/
│
├── campaign/
│   ├── state.json
│   ├── config.json
│   └── rules.md
│
├── characters/
│   ├── pc_001.json
│   ├── pc_002.json
│   └── ...
│
├── world/
│   ├── locations/
│   │   ├── loc_001.json
│   │   └── ...
│   │
│   ├── npcs/
│   │   ├── npc_001.json
│   │   └── ...
│   │
│   ├── factions/
│   └── knowledge/
│
├── quests/
│   ├── quest_001.json
│   └── ...
│
├── items/
│   ├── definitions/
│   │   ├── longsword.json
│   │   └── ...
│   │
│   └── instances/
│       ├── item_001.json
│       └── ...
│
├── rules/
│   ├── abilities.json
│   ├── skills.json
│   ├── conditions.json
│   ├── weapons.json
│   ├── armor.json
│   ├── spells.json
│   ├── classes.json
│   └── ...
│
├── schemas/
│   ├── state.schema.json
│   ├── character.schema.json
│   ├── npc.schema.json
│   ├── location.schema.json
│   ├── quest.schema.json
│   ├── item.schema.json
│   └── event.schema.json
│
├── events/
│   └── events.jsonl
│
├── sessions/
│   ├── session_001/
│   │   ├── transcript.md
│   │   ├── recap.md
│   │   └── handoff.json
│   │
│   └── ...
│
└── engine/
    ├── dice.py
    ├── checks.py
    ├── combat.py
    ├── damage.py
    ├── movement.py
    ├── inventory.py
    ├── quests.py
    ├── effects.py
    ├── state.py
    ├── events.py
    └── validation.py
```

> Структура является целевой архитектурой. Некоторые директории и модули появляются по мере развития MVP.

---

# Источники истины

Одна из главных архитектурных целей — не допустить дублирования состояния.

Каждая сущность должна иметь один основной источник истины.

```text
Rules
   │
   └── rules/

Campaign configuration
   │
   └── campaign/config.json

Campaign runtime state
   │
   └── campaign/state.json

Player Character
   │
   └── characters/pc_XXX.json

NPC
   │
   └── world/npcs/npc_XXX.json

Location
   │
   └── world/locations/loc_XXX.json

Quest
   │
   └── quests/quest_XXX.json

Item definition
   │
   └── items/definitions/

Item instance
   │
   └── items/instances/

History
   │
   └── events/

AI conversation
   │
   └── sessions/
```

### Пример

HP персонажа хранится:

```text
characters/pc_001.json
```

а не одновременно в:

```text
state.json
combat.json
session.json
character.json
```

`state.json` может содержать ссылку:

```json
{
  "party": {
    "character_ids": [
      "pc_001"
    ]
  }
}
```

Но не копию всего character sheet.

---

# `campaign/`

## `config.json`

Конфигурация кампании.

Отвечает на вопрос:

> **Как мы играем?**

Пример:

```json
{
  "schema_version": "1.0.0",

  "campaign": {
    "name": "Example Campaign",
    "setting": "homebrew",
    "difficulty": "normal"
  },

  "rules": {
    "system": "dnd5e",
    "ruleset": "dnd_2024",
    "leveling": "milestone",
    "use_feats": true,
    "use_multiclassing": true,
    "encumbrance": false,
    "flanking": false
  },

  "house_rules": {},

  "dm": {
    "style": "cinematic",
    "verbosity": "medium",
    "rules_strictness": "strict",
    "hidden_rolls": true,
    "announce_dc": false,
    "allow_retcon": false
  }
}
```

`config.json` изменяется редко.

---

## `state.json`

Текущее runtime-состояние кампании.

Отвечает на вопрос:

> **Что происходит прямо сейчас?**

Основные разделы:

```text
campaign
runtime
time
world
party
combat
quests
story
knowledge
integrity
```

Принцип:

```text
state.json
   │
   ├── current scene
   ├── current location
   ├── current time
   ├── active combat
   ├── party
   ├── active quests
   └── runtime flags
```

`state.json` обновляется во время игры.

---

## `rules.md`

Человеческое описание правил кампании.

Используется для:

* house rules;
* договорённостей;
* трактовки неоднозначных правил;
* поведения DM;
* особых правил конкретной кампании.

Разница:

```text
rules/*.json
    ↓
машиночитаемые правила

config.json
    ↓
какие правила включены

rules.md
    ↓
как мы договорились их трактовать
```

---

# Characters

Каждый PC — отдельная сущность.

```text
characters/
├── pc_001.json
├── pc_002.json
└── ...
```

Пример структуры:

```text
pc_001
│
├── identity
├── abilities
├── proficiencies
├── skills
├── combat
├── resources
├── inventory
├── currency
├── spells
├── features
├── conditions
├── effects
├── death
├── progression
└── relationships
```

Персонаж содержит **текущее состояние** PC.

Биография и большие текстовые описания могут храниться отдельно, чтобы не загружать их Engine без необходимости.

---

# World

## Locations

```text
world/locations/
```

Локация содержит:

* идентификатор;
* название;
* тип;
* описание;
* соединения с другими локациями;
* локальные объекты;
* связанные NPC;
* свойства местности.

Но текущая позиция партии находится в:

```text
campaign/state.json
```

---

## NPCs

```text
world/npcs/
```

NPC может содержать:

```text
identity
stats
combat
personality
knowledge
inventory
relationships
state
```

NPC является самостоятельной сущностью.

---

## Factions

```text
world/factions/
```

Фракции описывают:

* цели;
* ресурсы;
* территории;
* участников;
* отношения;
* отношение к партии.

---

## Knowledge

```text
world/knowledge/
```

Содержит:

* facts;
* secrets;
* rumors;
* discoveries.

Это позволяет разделять:

```text
Что знает DM
```

и

```text
Что знает игрок
```

---

# Quests

Квесты находятся в:

```text
quests/
```

Квест содержит:

```text
identity
description
objectives
state
requirements
rewards
related NPCs
related locations
```

`state.json` хранит ссылки на активные квесты:

```json
{
  "quests": {
    "active_ids": [
      "quest_001"
    ],
    "completed_ids": [],
    "failed_ids": []
  }
}
```

---

# Items

Предметы разделены на два уровня.

```text
items/
├── definitions/
└── instances/
```

## Definition

Определяет, что такое предмет по правилам:

```text
Longsword
1d8
Slashing
Versatile
Martial
```

## Instance

Конкретный предмет:

```text
item_001
```

Например:

```text
"Меч старого барона"
```

Это позволяет иметь несколько экземпляров одного типа с разными свойствами.

---

# Rules

```text
rules/
```

Машиночитаемая база игровых правил.

Например:

```text
abilities.json
skills.json
weapons.json
armor.json
spells.json
conditions.json
classes.json
```

Engine использует эти данные для расчётов.

---

# Schemas

```text
schemas/
```

JSON Schema определяет допустимую структуру игровых данных.

Например:

```text
character.schema.json
```

может гарантировать:

```text
HP.current → integer
HP.maximum → integer
level → integer
abilities.str → integer
```

Это защищает игру от повреждённого состояния.

---

# Engine

Engine — программная часть проекта, которая отвечает за игровую механику.

```text
engine/
├── dice.py
├── checks.py
├── combat.py
├── damage.py
├── movement.py
├── inventory.py
├── quests.py
├── effects.py
├── state.py
├── events.py
└── validation.py
```

---

## `dice.py`

Броски:

```text
1d20
2d6+3
1d8
```

---

## `checks.py`

Разрешение:

* ability checks;
* skill checks;
* saving throws;
* attack rolls;
* contested checks;
* advantage/disadvantage.

---

## `combat.py`

Управление боем:

```text
start combat
initiative
turn order
actions
bonus actions
reactions
movement
end turn
end combat
```

---

## `damage.py`

Обработка:

* damage;
* damage types;
* resistance;
* vulnerability;
* immunity;
* temporary HP;
* critical damage.

---

## `effects.py`

Временные эффекты:

```text
Bless
Poisoned
Stunned
Invisible
Cursed
Burning
```

Управляется жизненный цикл:

```text
apply
update
expire
remove
```

---

## `inventory.py`

Операции:

```text
add
remove
equip
unequip
consume
transfer
attune
```

---

## `state.py`

Слой доступа к persistent state:

```text
load
save
update
```

Он не должен содержать правила боя.

---

## `events.py`

Создание и запись событий.

---

## `validation.py`

Проверка целостности данных.

---

# Игровой цикл

Рассмотрим:

> «Я атакую гоблина мечом».

## 1. Player

```text
Я атакую гоблина мечом.
```

↓

## 2. AI-DM

AI определяет намерение:

```json
{
  "action": "attack",
  "actor_id": "pc_001",
  "target_id": "npc_001",
  "weapon_id": "item_001"
}
```

↓

## 3. Engine

Engine загружает:

```text
PC
NPC
Weapon
Rules
State
```

↓

## 4. Attack resolution

```text
d20
+
attack modifier
+
advantage/disadvantage
```

↓

## 5. Damage resolution

```text
weapon damage
+
modifiers
-
resistance
```

↓

## 6. State mutation

Например:

```text
Goblin HP
12 → 4
```

↓

## 7. Event

Записывается:

```text
attack_resolved
damage_applied
```

↓

## 8. Validation

Проверяется новое состояние.

↓

## 9. AI-DM

Engine возвращает:

```text
HIT
8 damage
target HP = 4
```

AI превращает результат в повествование:

> Клинок пробивает защиту гоблина...

---

# Полный поток данных

```text
                       PLAYER
                          │
                          ▼
                   ┌─────────────┐
                   │    AI-DM    │
                   └──────┬──────┘
                          │
                       Intent
                          │
                          ▼
                   ┌─────────────┐
                   │   ENGINE    │
                   └──────┬──────┘
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
         Characters      World       Rules
              │           │           │
              └───────────┼───────────┘
                          ▼
                    Resolution
                          │
                          ▼
                   State Mutation
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
           Entities                 Events
              │                       │
              └───────────┬───────────┘
                          ▼
                       State
                          │
                          ▼
                        AI-DM
                          │
                          ▼
                      Narration
                          │
                          ▼
                        PLAYER
```

---

# Events

Events являются историческим журналом.

Пример:

```json
{
  "event_id": "evt_145",
  "sequence": 145,
  "type": "damage_applied",

  "actor_id": "pc_001",
  "target_id": "npc_001",

  "amount": 8,

  "timestamp": "2026-08-18T10:00:00Z"
}
```

Главное различие:

```text
STATE
=
что есть сейчас

EVENT
=
как мы к этому пришли
```

Например:

```text
HP = 12
```

находится в character state.

А:

```text
Goblin attacked PC
PC dealt 8 damage
```

находится в event history.

---

# Sessions

Сессия является историей общения AI и игрока.

```text
sessions/
└── session_001/
    ├── transcript.md
    ├── recap.md
    └── handoff.json
```

### transcript.md

Полный диалог.

### recap.md

Сжатое резюме.

### handoff.json

Машиночитаемый пакет для продолжения игры в другом AI-контексте.

---

# Решение проблемы Context Window

Контекст чата не является долговременной памятью.

Поэтому новый AI-контекст получает не весь старый чат, а необходимый набор данных.

```text
OLD CHAT
   │
   ├── transcript
   ├── events
   └── current state
          │
          ▼
      HANDOFF
          │
          ▼
      NEW CHAT
          │
          ├── state.json
          ├── relevant characters
          ├── relevant NPCs
          ├── current location
          ├── active quests
          ├── rules.md
          ├── recent events
          └── handoff.json
```

Таким образом:

> **Чат является disposable context, а campaign является persistent state.**

---

# Модель памяти

Система использует несколько уровней памяти:

```text
┌─────────────────────────────────┐
│        WORLD / ENTITIES         │
│                                 │
│ characters / NPC / locations    │
│ quests / items / factions       │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│          CURRENT STATE          │
│                                 │
│ campaign/state.json             │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│          EVENT HISTORY          │
│                                 │
│ events/events.jsonl             │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│         SESSION MEMORY          │
│                                 │
│ transcript / recap / handoff    │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│        AI CONTEXT WINDOW        │
│                                 │
│ only relevant information       │
└─────────────────────────────────┘
```

---

# AI-DM Responsibilities

AI отвечает за то, что плохо формализуется обычным кодом.

### AI может:

* понимать естественный язык;
* интерпретировать намерения игрока;
* вести диалоги;
* отыгрывать NPC;
* описывать мир;
* создавать повествование;
* предлагать варианты действий;
* управлять pacing;
* принимать DM-решения;
* выбирать подходящие правила;
* определять, какие игровые сущности необходимо загрузить.

### AI не должен самостоятельно:

* считать урон;
* менять HP без Engine;
* менять inventory;
* менять XP;
* определять случайный результат броска;
* самостоятельно изменять state;
* переписывать event history.

---

# Engine Responsibilities

Engine отвечает за то, что должно быть воспроизводимым и проверяемым.

```text
AI:
"Я атакую."

Engine:
d20 = 17
attack bonus = +5
target AC = 15

17 + 5 = 22

HIT

damage = 8
```

Engine является источником истины для механики.

---

# GitHub

GitHub используется как система контроля версий проекта.

Репозиторий может содержать:

```text
source code
JSON data
schemas
rules
tests
documentation
campaign data
```

Git позволяет:

* отслеживать изменения;
* откатывать состояние;
* сравнивать версии;
* создавать branches;
* проводить code review;
* восстанавливать предыдущие состояния кампании.

---

# Внешние AI coding tools

Инструменты вроде Claude Code, Codex и других coding agents могут использоваться для разработки самого проекта.

Например:

```text
Developer
    │
    ▼
Coding Agent
    │
    ├── Engine
    ├── Tests
    ├── Schemas
    ├── Refactoring
    └── Git
```

Однако coding agent не является частью игрового runtime.

Во время игры основной поток:

```text
Player
   ↓
AI-DM
   ↓
Engine
   ↓
Persistent State
```

---

# MVP

Первая рабочая версия не должна пытаться реализовать всю D&D.

Минимальная вертикальная версия должна поддерживать:

```text
Campaign
   │
   ├── 2 Player Characters
   │
   ├── Location
   │
   ├── NPC
   │
   ├── Quest
   │
   ├── Item
   │
   └── Combat
```

Игровой сценарий:

```text
Create campaign
      ↓
Create characters
      ↓
Enter location
      ↓
Talk to NPC
      ↓
Receive quest
      ↓
Move to another location
      ↓
Skill check
      ↓
Start combat
      ↓
Attack
      ↓
Damage
      ↓
End combat
      ↓
Save state
      ↓
Write events
      ↓
Create session handoff
```

Если этот сценарий работает корректно, архитектура доказала свою жизнеспособность.

---

# Roadmap

## Phase 1 — Data Model

* [x] Campaign structure
* [x] `state.json`
* [x] `config.json`
* [x] `rules.md`
* [x] Character structure
* [ ] Location
* [ ] NPC
* [ ] Quest
* [ ] Item
* [ ] Event
* [ ] Session
* [ ] Handoff

---

## Phase 2 — Schemas

* [ ] JSON Schema для Campaign
* [ ] JSON Schema для Character
* [ ] JSON Schema для Location
* [ ] JSON Schema для NPC
* [ ] JSON Schema для Quest
* [ ] JSON Schema для Item
* [ ] JSON Schema для Event

---

## Phase 3 — Engine

* [ ] State manager
* [ ] Dice
* [ ] Checks
* [ ] Modifiers
* [ ] Advantage / Disadvantage
* [ ] Combat
* [ ] Damage
* [ ] Conditions
* [ ] Effects
* [ ] Inventory
* [ ] Quest state
* [ ] Event log
* [ ] Validation

---

## Phase 4 — AI-DM Integration

* [ ] Intent parser
* [ ] Context builder
* [ ] Entity retrieval
* [ ] Engine command interface
* [ ] Result formatter
* [ ] Narration layer
* [ ] NPC roleplay
* [ ] Memory management
* [ ] Handoff generation

---

## Phase 5 — Long Campaign Support

* [ ] Session summaries
* [ ] Automatic checkpoints
* [ ] Event compaction
* [ ] Context retrieval
* [ ] Relevant entity loading
* [ ] Long-term memory
* [ ] Campaign migration
* [ ] State rollback

---

# Основные архитектурные правила

## 1. Один источник истины

Не дублировать mutable state.

Плохо:

```text
state.json → HP = 20
pc_001.json → HP = 17
combat.json → HP = 15
```

Хорошо:

```text
pc_001.json → HP = 17
```

Остальные системы используют ссылку на `pc_001`.

---

## 2. State ≠ History

```text
state.json
```

хранит настоящее.

```text
events.jsonl
```

хранит прошлое.

---

## 3. Definition ≠ Instance

```text
Longsword definition
```

не является конкретным мечом персонажа.

```text
item_001
```

является экземпляром.

---

## 4. Rules ≠ State

Правила:

```text
rules/
```

Состояние:

```text
campaign/state.json
```

---

## 5. AI ≠ Engine

AI может интерпретировать действие.

Engine определяет механический результат.

---

## 6. Chat ≠ Campaign

Чат — временный контекст.

Кампания — persistent data.

```text
CHAT
  ↓
temporary context

CAMPAIGN
  ↓
persistent world
```

---

## 7. Любое значимое изменение должно быть проверяемым

Изменение состояния должно проходить через Engine и, где необходимо, создавать Event.

```text
Action
   ↓
Engine
   ↓
Validation
   ↓
State mutation
   ↓
Event
```

---

# Итоговая архитектура

```text
                              ┌───────────────┐
                              │    PLAYER     │
                              └───────┬───────┘
                                      │
                                      ▼
                              ┌───────────────┐
                              │     AI-DM     │
                              │               │
                              │ Intent        │
                              │ Narration     │
                              │ NPC           │
                              │ DM Logic      │
                              └───────┬───────┘
                                      │
                                      ▼
                              ┌───────────────┐
                              │    ENGINE     │
                              │               │
                              │ Rules         │
                              │ Dice          │
                              │ Checks        │
                              │ Combat        │
                              │ Damage        │
                              │ Effects       │
                              │ State         │
                              │ Validation    │
                              └───────┬───────┘
                                      │
                 ┌────────────────────┼────────────────────┐
                 │                    │                    │
                 ▼                    ▼                    ▼
          ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
          │  CHARACTERS │      │    WORLD    │      │    RULES    │
          │             │      │             │      │             │
          │ PC state    │      │ NPC         │      │ D&D rules  │
          │ Inventory   │      │ Locations   │      │ Spells     │
          │ Effects     │      │ Factions    │      │ Conditions │
          └──────┬──────┘      └──────┬──────┘      └─────────────┘
                 │                    │
                 └──────────┬─────────┘
                            │
                            ▼
                     ┌─────────────┐
                     │    STATE    │
                     │             │
                     │ Current     │
                     │ Runtime     │
                     └──────┬──────┘
                            │
                 ┌──────────┴──────────┐
                 ▼                     ▼
          ┌─────────────┐       ┌─────────────┐
          │   EVENTS    │       │  SESSIONS   │
          │             │       │             │
          │ History     │       │ Transcript  │
          │ Audit       │       │ Recap       │
          │ Recovery    │       │ Handoff     │
          └─────────────┘       └──────┬──────┘
                                       │
                                       ▼
                                  NEW AI CHAT
```

---

# Core Philosophy

AI-D&D is built around one central principle:

> **The AI does not need to remember the entire game. It only needs to reconstruct the current game state from persistent, structured data.**

The campaign survives:

* context-window limits;
* chat changes;
* model changes;
* session interruptions;
* AI memory degradation;
* long campaign histories.

The AI is replaceable.

The chat is replaceable.

The persistent campaign state is not.

---

## Status

**Current stage:** Architecture / MVP data model

**Primary goal:** Build a minimal, reliable vertical slice before expanding into the complete D&D ruleset.

**Next implementation step:** Define `Location` entity and its JSON schema, then `NPC`, `Quest`, `Item`, `Event`, and only after that begin implementation of the Engine.

```
```
# ai-dnd-master
