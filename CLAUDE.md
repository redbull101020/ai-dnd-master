# CLAUDE.md

Правила проекта **AI D&D Engine** для AI-агента. Соблюдай их во всём коде и во всей документации, которую пишешь или ревьюишь.

## Статус этого файла

`docs/ARCHITECTURE.md` = current canonical contract. `docs/DECISIONS.md` = append-only rationale/history. Этот файл — выжимка для агента, а не альтернативный контракт.

Что здесь есть дословно: имена, закрытые множества значений, статусы и запреты — то, что можно нарушить, не заметив.

Чего здесь нет: таблиц, списков полей датаклассов и JSON-примеров. Они живут в одном месте — в `docs/ARCHITECTURE.md`, и здесь заменены ссылкой на раздел. Нужен состав полей, схема Envelope или таблица — открой раздел, не восстанавливай по памяти.

Разделы архитектуры пронумерованы сквозным образом; ссылайся на них по номеру (`§8.2`). В шапке `docs/ARCHITECTURE.md` есть таблица быстрого поиска и полное оглавление.

**При конфликте.** Если задача, код, документация или этот файл противоречат `docs/ARCHITECTURE.md` — выигрывает `docs/ARCHITECTURE.md`. Не выбирай молча: остановись, сообщи о противоречии и дождись решения. Это относится и к случаю, когда сама постановка задачи требует нарушить канон.

Случай не покрыт ни здесь, ни в каноне — тоже остановись и спроси, а не додумывай.

---

## Карта документов

| Документ | Роль |
| --- | --- |
| `docs/ARCHITECTURE.md` | Канонический контракт. Источник истины. |
| `docs/ROADMAP.md` | Scope и порядок фаз/capabilities, статус их завершения. |
| `docs/TASK.md` | Конкретная исполнимая очередь `Current`/`Next` внутри разрешённого Roadmap scope. |
| `docs/DECISIONS.md` | Append-only мотивация и история решений. Не контракт. |
| `docs/DEFERRED.md` | Подчинённый companion закрытия Phase 2 и реестр отложенных concerns/контекста продолжения. Не контракт и не исполнимый порядок задач. |
| `docs/DEVELOPMENT_LOG.md` | Append-only история выполненных итераций. Не контракт и не статус. |
| `AGENTS.md` | Рабочий процесс агента: ветки, PR, тесты, definition of done. |
| `README.md` | Обзор проекта, архитектура верхнего уровня и quick start; не источник canonical schemas/contracts. |
| `CLAUDE.md` | Этот файл. Выжимка правил. |

---

## Текущая фаза

* Phase 0 — Foundation: завершена.
* Phase 1 — Core: завершена.
* Phase 2 — Basic Rules: завершена в foundation scope (§3.24); более широкий D&D scope `PARTIAL` и продолжается через `docs/DEFERRED.md`, не переоткрывая Phase 2.
* **Phase 3 — Combat: текущая.**

Реализованные и pending Phase 2/3 contracts — см. «Индекс реализованных
контрактов» ниже; точная история и rationale каждого среза — в
`docs/ARCHITECTURE.md` и `docs/DECISIONS.md`, не здесь.

Актуальный scope, порядок и статус фаз/capabilities — в `docs/ROADMAP.md`;
конкретные `Current`/`Next` задачи — в `docs/TASK.md`. При расхождении с этим
списком выигрывает Roadmap.

**Правило фазовой дисциплины.** Поля, типы и абстракции будущих фаз не добавляются заранее. Контракты Phase 1 минимальны намеренно: отсутствие поля — это решение, а не недоделка. Расширять канонический контракт можно только вместе с реализацией соответствующего поведения и только через процедуру изменения контракта.

---

## Главный принцип

> AI интерпретирует намерения и ведёт повествование. Engine определяет истину игрового мира.

LLM никогда не решает исход броска, не меняет State напрямую и не определяет, разрешено ли действие. Всё это — детерминированный Rule Engine.

Канонический поток действия:

```text
Player/AI DM → Command → Validation → Rule Engine → Result → Events → State update → Persistence → Narration
```

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

**Domain не импортирует:** FastAPI, SQLAlchemy и любой ORM, SDK LLM-провайдеров, реализацию файловой системы, HTTP-типы.

Infrastructure реализует интерфейсы, объявленные в Domain. Зависимость всегда направлена внутрь.

Проверка: если Rule Engine нельзя выполнить обычным `python` без сети и HTTP — архитектура нарушена.

---

## Definitions ≠ State

> [§3.1 Definition Contract](docs/ARCHITECTURE.md#31-definition-contract) · [§3.2 State Contract](docs/ARCHITECTURE.md#32-state-contract)

**Definition** — неизменяемое описание из правил. Единственная authoritative
копия — packaged resource `src/dnd_engine/resources/rulesets/` (§12.26);
отдельного top-level `rules/` больше нет.
**State** — изменяемый экземпляр в кампании, лежит в `campaigns/campaign_NNN/`.

Обязательные поля любого Definition — `id` и `version` (§3.1). `name` обязательным для всех Definitions не является.

Definition immutable: во время сессии не мутируется, при изменении правила создаётся новая версия, старая не правится. Жизненный цикл — `CREATE → LOAD → READ`, без `UPDATE`.

---

## Индекс реализованных контрактов

Всё перечисленное реализовано и покрыто тестами. Здесь только имя и раздел;
состав полей, Envelope-схемы и точное поведение — в указанном разделе
`docs/ARCHITECTURE.md`, не здесь. Наборы полей перечисленных Definitions/
State/Value Objects **полные, минимальные и закрытые**: не добавляй поля, не
переименовывай, не заводи синонимы.

| Контракт | Раздел |
| --- | --- |
| `AbilityScores` | §1.2.1 |
| `Definition` (база), `ItemDefinition`, `WeaponDefinition`, `MonsterDefinition` | §3.1, §3.1.1 |
| `DamageType` | §3.1.1 |
| `CreatureState`, `CampaignState`, `StateSnapshot`, `CharacterState` | §3.2.1–§3.2.4 |
| `DiceEngine`, `DiceRoll` | §1.7.1 |
| `GameEvent` | §3.4, §8.1, §8.2 |
| `StateStore`, `EventSerializer`, `StateSerializer`, `FilesystemStateStore` | §3.2.3, §12.9, §12.10 |
| `ResolutionResult[T]`, `ErrorCode`/`EngineError` | §3.5, §3.9 |
| Ability Check vertical slice | §3.3, §3.10 |
| Proficiency foundation | §3.11 |
| Minimal d20 semantics (`RollMode`, `D20Roll`) | §3.12 |
| Character Saving Throw vertical slice | §3.13 |
| Character Skill Check vertical slice | §3.14 |
| Armor Class (minimal) | §3.15 |
| Definition Access foundation (G4a, `DefinitionSource`) | §3.16 |
| Character unarmed Attack Roll → Monster vertical slice | §3.17 |
| State Mutation Foundation (G5) | §3.18 |
| Damage → HP mutation slice (G6A) | §3.19 |
| Healing → HP mutation slice (G6B) | §3.20 |
| Condition State foundation (G6C1) | §3.21 |
| Minimal Poisoned behavior (G6C2) | §3.22 |
| Post-G6C abstraction review / `replace_creature_in_snapshot` | §3.23 |
| Phase 2 Closure Contract | §3.24 |
| Combat Initiative/Turn Order vertical slice (G7) | §3.25 |
| Monster attack → Character vertical slice (G8) | §3.26 |
| Monster Attack consequence → Damage → HP vertical slice (G9) | §3.27 |
| Attack active-turn eligibility | §3.28 |
| Zero-HP Attack eligibility by creature category | §3.31 |

Canonical контракты, чья production implementation ещё не сделана,
отслеживаются в `docs/ROADMAP.md` и `docs/TASK.md`; не выводи implementation
status из одного факта присутствия в Architecture.

---

## Отложенные абстракции — не вводить

§3.6 прямо запрещает вводить заранее:

```text
GameEngine.execute(...)
CommandBus
EventBus
generic resolver registry
generic handler registry
dispatcher
transaction coordinator
GameContext implementation
```

§3.18 State Mutation Foundation (G5) дополнительно запрещает вводить для State
mutation:

```text
UnitOfWork
TransactionManager
WorkingState
MutationContext
StateChange
EventApplierRegistry
generic reducer
generic State Owner repository
generic transaction coordinator
```

Канонический контракт применения Events к State — loaded snapshot как
read-only input, replacement/copy-on-write вместо in-place мутации, save
ordering и exact MVP atomicity boundary — зафиксирован в §3.18. Единственная
извлечённая generic abstraction — narrow Application helper
`replace_creature_in_snapshot` (§3.23): заменяет ровно одного existing
Creature по stable ID и не мутирует loaded snapshot. Остальная orchestration и
все concrete Event appliers остаются narrow, не объединённые в
`EventApplierRegistry`/reducer. EventStore, durable Event persistence/append и
replay остаются отдельно deferred (§12.10, §3.18).

Первый vertical slice Phase 2 использует explicit Application handler и прямой
вызов конкретного Domain resolver. Общая orchestration abstraction появляется
только тогда, когда несколько конкретных Commands покажут реально повторяющееся
поведение. Получив задачу «реализовать механику», не начинай с шины команд.

---

## ID System

> [§4 ID System](docs/ARCHITECTURE.md#4-id-system) · [§4.13 Сводная таблица](docs/ARCHITECTURE.md#413-сводная-таблица-id--id-reference-table)

Форматы всех ID — в §4.13. По памяти не воспроизводи.

Жёсткие правила:
* **Instance ID никогда не повторяет Definition ID.** Экземпляр меча — `item_001` с полем `definitionId: "longsword"`, а не `longsword_001`.
* Definition ID — семантический `lowercase_snake_case`. Runtime ID — `<тип>_<номер>`.
* ID не переиспользуется после удаления сущности и не изменяется в течение её жизни.
* ID не несёт игровой логики: не тип, не класс, не статус, не правило.

---

## Command и Event

> Command: [§9.1](docs/ARCHITECTURE.md#91-каноническая-схема-command--canonical-command-schema) · [§9.2](docs/ARCHITECTURE.md#92-поля-command-envelope--command-envelope-fields) · §9.7 · [§9.8](docs/ARCHITECTURE.md#98-command--event) · [§3.3](docs/ARCHITECTURE.md#33-command-contract)
> Event: [§8.1](docs/ARCHITECTURE.md#81-каноническая-схема-event--canonical-event-schema) · [§8.2](docs/ARCHITECTURE.md#82-поля-event-envelope--event-envelope-fields) · [§8.13](docs/ARCHITECTURE.md#813-event-naming-convention) · [§3.4](docs/ARCHITECTURE.md#34-event-contract)

Схемы обоих Envelope и списки полей — в указанных разделах.

Command — намерение, Event — свершившийся факт в прошедшем времени. Command не меняет State напрямую: она порождает Events, и уже они меняют состояние. Команда может быть отклонена или провалиться; событие описывает только то, что действительно произошло.

Специфика команды живёт **только** внутри `payload`. Не выноси `targetId` или другие mechanic-specific поля на верхний уровень Envelope; current `AttackCommand` содержит только `targetId`, без `weaponId` (§3.17).

Command Envelope — это JSON/boundary-контракт, а не обязательный generic Python Domain-класс. После boundary validation gameplay-команда представляется отдельным immutable typed dataclass с concrete typed payload; произвольный `dict[str, Any]` не проходит внутрь rule-resolution boundary. Generic Command inheritance hierarchy на текущем этапе не вводится.

**Жизненный цикл Command описан ровно в одном месте — §9.7:**

```text
Created → Validating → Rejected | Accepted → Resolving → Completed | Failed
```

Других словарей состояний нет. `Received`, `Valid`, `Invalid`, `Executing` отвергнуты (DEC-0015).

Event immutable: опубликованный Event неизменяем. Имя события — факт в прошедшем времени: `DamageApplied`, `AttackResolved`, `CreatureMoved`; не `ApplyDamage`, не `DoAttack`. `causedBy` связывает событие с породившим его событием — цепочку не терять.

---

## State Ownership

> [§10 State Ownership](docs/ARCHITECTURE.md#10-state-ownership) · [§10.13 Owner Matrix](docs/ARCHITECTURE.md#1013-owner-matrix)

У каждого State-объекта ровно один владелец, и только он его изменяет. Матрица владельцев — §10.13; по памяти не восстанавливай.

Остальные системы имеют только read-доступ. Прямая мутация чужого State — архитектурная ошибка, даже если это «быстрее».

`StateSnapshot` группирует State для персистентности, но владельцем не становится и владение не передаёт.

Прежде чем добавить новую сущность, ответь на три вопроса:
1. Это Definition или State?
2. Какой у неё ID и формат?
3. Кто владеет её жизненным циклом, какие Commands её меняют и какие Events это фиксируют?

---

## Случайность

> [§1.7 Random Number Generation](docs/ARCHITECTURE.md#17-random-number-generation) · [§1.7.1 Minimal Dice Engine](docs/ARCHITECTURE.md#171-minimal-phase-1-dice-engine-contract)

Вся случайность — только через `DiceEngine`. Прямой `random` в доменной логике запрещён.

* `DiceEngine` — Domain `Protocol` с единственным методом `roll(expression: str) -> DiceRoll`.
* Принимается **только строгая нотация `NdM`** в нижнем регистре. Модификаторы, advantage/disadvantage, keep/drop и полный DSL не поддерживаются и не добавляются.
* Advantage/disadvantage реализуются поверх primitive `"1d20"` calls через `resolve_d20_roll`, а не расширением dice-expression DSL или изменением `DiceRoll.total` (§3.12).
* Парсер `NdM` — shared pure Domain primitive `parse_ndm()` (`domain/dice.py`, §1.7.1, DEC-0030), а не private Infrastructure detail. `PythonDiceEngine` и intrinsic invariant `WeaponDefinition.damage_dice` (§3.1.1) — два его consumers; RNG остаётся Infrastructure-only.
* Production-реализация `PythonDiceEngine` получает `random.Random` инъекцией. Domain не зависит от реализации RNG.
* Внутреннее состояние RNG не является авторитетным State кампании.
* Модификаторы правил применяются на уровне rule resolution и не входят в `DiceRoll.total`.

---

## Сериализация

> [§12.1 Где разрешена](docs/ARCHITECTURE.md#121-где-разрешена-сериализация--where-serialization-is-allowed) · [§12.2 Форматы](docs/ARCHITECTURE.md#122-канонические-форматы--canonical-formats) · §12.9 · [§12.10 Event Serialization](docs/ARCHITECTURE.md#1210-event-serialization) · [§12.21 Запрещённые практики](docs/ARCHITECTURE.md#1221-запрещённые-практики--forbidden-practices) · [§12.25 Runtime Validation Policy](docs/ARCHITECTURE.md#1225-runtime-validation-policy)

* Сериализации **нет внутри Rule Engine.** Resolver не открывает файлы и не знает про JSON.
* Чтение и запись — только в Infrastructure, через Serializer или Repository. Serializer — чистая граница без ввода-вывода.
* Python `snake_case` ↔ JSON `camelCase`. Границу пересекает только сериализатор.
* **JSON** — Definitions, state snapshots, config, AI context, API DTO. **JSONL** — append-only потоки; одна строка = один JSON-объект.
* `state.json` несёт целочисленный `schemaVersion`; writer пишет ровно одну current version, reader строго принимает current version и явно перечисленные legacy versions read-only. Точная current version и migration table по каждой legacy version — §12.13 в `docs/ARCHITECTURE.md`, не здесь.
* **Десериализация строгая:** все поля обязательны; неизвестные поля, значения по умолчанию и приведение типов запрещены. Доменные инварианты проверяются при разборе.
* Untrusted boundary проверяет shape, runtime types, schema/version, форматы и ссылки при dereference. Domain Value Objects и State/Definitions сами защищают intrinsic/semantic invariants; transport validation не копируется в каждый dataclass.
* Domain constructors не выполняют coercion (`"1" → 1`, `list → tuple`, `string → enum`); normalization принадлежит boundary mapper/loader.
* Timestamp — timezone-aware UTC `datetime` в Domain, ISO 8601 с канонической `Z` в JSON. Значение передаётся снаружи: доменный объект не читает часы.
* Nullable-поля Envelope всегда присутствуют в JSON: Domain `None` пишется как `null`.

---

## Ловушки именования

Места, где привычка расходится с каноном. Нарушение здесь не даёт ошибки и не ловится тестами — только код-ревью.

| Напрашивается | Канон |
| --- | --- |
| `hp`, `hit_points`, `hitPoints` | `current_hp` / `max_hp` в Python, `currentHp` / `maxHp` в JSON |
| `MonsterState`, `EntityState` | `CreatureState` |
| `Received` в жизненном цикле Command | `Created` (§9.7) |
| `2d6+3`, `1d20kh1`, advantage внутри выражения | только `NdM` |
| `damage_type: str` или собственный Enum | `DamageType`, закрытый Domain `StrEnum` |
| `conditions: list[str]` / `set[str]` на `CreatureState` | `conditions: frozenset[Condition]`, без коэрсии строк (§3.21) |
| Отдельные `Event` и `EventEnvelope` | один `GameEvent` |
| `datetime.now()`, naive datetime, смещение `+00:00` | aware UTC, передан снаружи, в JSON — `Z` |
| `state_changes` в `ResolutionResult` | такого поля нет |
| generic top-level `rolls` в `ResolutionResult` | roll находится в typed outcome и durable Event payload |
| `roll.total` в Ability Check | `D20Roll.selected`; `DiceRoll.total` остаётся суммой dice expression |
| Хранимый `modifier` в `AbilityScores` | чистое правило `(score - 10) // 2` |
| `AbilityCheckSucceeded` / `AbilityCheckFailed` | один `AbilityCheckResolved`, исход в `payload.succeeded` |
| `ruleset_version = "5.2.1"` для `dnd_5e` | `dnd_5e` = SRD 5.1; канонический `ruleset_version = "5.1"` (§4.6) |
| `rules/dnd_5e/...json` как источник Definition data | packaged resource `src/dnd_engine/resources/rulesets/...` (§12.26) |
| `deepcopy()` loaded State перед мутацией | replacement/copy-on-write construction нового State object (§3.18) |
| `state_changes`/UoW как решение задачи «применить Event к State» | конкретное State Owner-specific применение Event + §3.18 mutation scope |

`DamageType` — ровно тринадцать значений, расширять нельзя:

```text
acid  bludgeoning  cold  fire  force  lightning  necrotic
piercing  poison  psychic  radiant  slashing  thunder
```

---

## Тесты

> [§1.5 Tests](docs/ARCHITECTURE.md#15-tests)

`pytest`. Покрываем в первую очередь: Rule Engine, Resolvers, Dice Engine, переходы State, обработчики Events, сериализацию.

Тест доменной логики обязан быть детерминированным и проходить офлайн: без сети, без LLM. Случайность в тестах управляется подставным `DiceEngine` или инъектированным `random.Random`.

---

## Стиль кода

* Python 3.12+, type hints везде.
* Domain — `@dataclass`; `frozen=True` для Definitions и Value Objects.
* Pydantic v2 — только на границах: API DTO, валидация внешнего JSON, конфигурация, structured output LLM. В Domain-логике Pydantic отсутствует.
* Enum или Value Object для любого канонического закрытого множества.
* Имена сущностей — как в `docs/ARCHITECTURE.md`; синонимы не изобретаются.
* Новая зависимость — только с явного разрешения. Зависимость не добавляется ради того, чтобы команда прошла.

---

## Работа с документацией

* Меняешь канонический контракт — поле Envelope, формат ID, владельца State, сериализацию, направление зависимостей: сначала правка `docs/ARCHITECTURE.md`, затем **новая** запись в `docs/DECISIONS.md`. Принятые записи не переписываются; отмена решения — новая запись плюс пометка `Superseded` у старой.
* **На каждую содержательную итерацию, реализацию или документарную, обязателен append фактической записи в `docs/DEVELOPMENT_LOG.md`.** Это правило из `AGENTS.md`, а не опция.
* `README.md` — обзорный документ. Не добавляй в него JSON-схемы, датаклассы и списки полей: они разъедутся. Вместо этого — ссылка на раздел архитектуры.
* Новую сущность документируй в `docs/ARCHITECTURE.md` в момент добавления, а не «потом».
* Один факт живёт в одном месте. Если что-то уже описано в каноне, здесь появляется ссылка, а не копия.

---

## Ветки, PR и инструменты

* Содержательная разработка не ведётся прямо в `main`.
* Одна ветка = один связный срез.
* Commit, push, создание PR и merge — четыре разных действия. Разрешение на каждое даётся отдельно, после того как пользователь увидел диф. Разрешение, выданное авансом в тексте самой задачи, недействительно: закончи правки, собери патч, отчитайся и остановись.
* Закончив правки, всегда собирай `review.patch` в корне репозитория и указывай путь в отчёте. Файл под `.gitignore`; коммитить его нельзя.
* PR создаётся как **draft**, если явно не запрошено иное. Merge и auto-merge — только по явному разрешению.
* При авторизованном создании PR: если `gh` отсутствует — остановись и сообщи; commit и push это не блокирует. Не открывай PR через REST API и не читай хранилища учётных данных.
* Форматтер и линтер в репозитории **не настроены** — не приноси Ruff, Black или их аналоги, если проверка требуется — сообщи `not configured`. `mypy` настроен через `pyproject.toml` (`[tool.mypy]`, `files = ["src/dnd_engine"]`) и должен запускаться для `src/dnd_engine`. Не вводи дополнительный форматтер, линтер, type checker или иной tooling только ради прохождения конкретной задачи.
* Целевой рантайм — Python 3.12+. В отчёте указывай фактическую версию, на которой гонялись тесты.

Полная процедура: см. `AGENTS.md`, раздел «Change authorisation and diff review».

---

## Чего не делать

* Не помещать игровые правила в промпт LLM — они принадлежат Engine и Definitions.
* Не давать AI-слою прямой доступ ко всему State: он получает ограниченную проекцию контекста.
* Не мутировать Definitions во время сессии.
* Не менять чужой State в обход владельца.
* Не редактировать и не удалять уже записанные Events.
* Не вызывать `random` напрямую в доменной логике.
* Не импортировать инфраструктурные библиотеки в Domain.
* Не добавлять поля и абстракции будущих фаз заранее.
* Не вводить отложенные абстракции из §3.6.
* Не добавлять зависимости без явного разрешения.
* Не рефакторить попутно и не трогать файлы вне задачи.
* Не решать молча при конфликте с каноном — останавливаться и сообщать.
