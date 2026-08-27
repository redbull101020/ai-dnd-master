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
| `docs/ROADMAP.md` | Фазы, порядок работ, текущий статус. |
| `docs/DECISIONS.md` | Append-only мотивация и история решений. Не контракт. |
| `docs/DEVELOPMENT_LOG.md` | Append-only история выполненных итераций. Не контракт и не статус. |
| `AGENTS.md` | Рабочий процесс агента: ветки, PR, тесты, definition of done. |
| `README.md` | Обзор проекта. Без схем и контрактов. |
| `CLAUDE.md` | Этот файл. Выжимка правил. |

---

## Текущая фаза

* Phase 0 — Foundation: завершена.
* Phase 1 — Core: завершена.
* **Phase 2 — Basic Rules: текущая.**
* Первый read-only Ability Check vertical slice Phase 2 реализован.

Актуальный статус — в `docs/ROADMAP.md`; при расхождении с этим списком выигрывает Roadmap.

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

**Definition** — неизменяемое описание из правил, лежит в `rules/dnd_5e/`.
**State** — изменяемый экземпляр в кампании, лежит в `campaigns/campaign_NNN/`.

Обязательные поля любого Definition — `id` и `version` (§3.1). `name` обязательным для всех Definitions не является.

Definition immutable: во время сессии не мутируется, при изменении правила создаётся новая версия, старая не правится. Жизненный цикл — `CREATE → LOAD → READ`, без `UPDATE`.

---

## Реализованные контракты Phase 1

Всё перечисленное реализовано, покрыто тестами и имеет канонический раздел. Наборы полей **полные, минимальные и закрытые**: не добавляй поля, не переименовывай, не заводи синонимы.

| Контракт | Слой | Раздел |
| --- | --- | --- |
| `AbilityScores` | Domain / value object | §1.2.1 |
| `Definition` (база) | Domain / definitions | §3.1 |
| `ItemDefinition`, `WeaponDefinition`, `MonsterDefinition` | Domain / definitions | §3.1.1 |
| `DamageType` | Domain / value object | §3.1.1 |
| `CreatureState` | Domain / state | §3.2.1 |
| `CampaignState` | Domain / state | §3.2.2 |
| `StateSnapshot` | Domain / state | §3.2.3 |
| `DiceEngine`, `DiceRoll` | Domain / service, value object | §1.7.1 |
| `GameEvent` | Domain / events | §3.4, §8.1, §8.2 |
| `StateStore` | Domain port | §3.2.3, §12.9 |
| `EventSerializer` | Infrastructure | §12.10 |
| `StateSerializer`, `FilesystemStateStore` | Infrastructure | §12.9 |

---

## Реализованные контракты Phase 2

* `ResolutionResult[T]` (§3.5). `success` означает успех обработки команды и разрешения правил, **не** игровой исход: проваленная проверка — это `success is True` и `outcome.succeeded is False`. Полей `state_changes` и generic top-level `rolls` нет; placeholder-абстракция `StateChange` не вводится.
* `ErrorCode` и `EngineError` (§3.9). Минимальное structured representation ожидаемых ошибок без exception hierarchy.
* Ability Check vertical slice (§3.3, §3.10): `Ability`, `AbilityCheckCommand`, `AbilityCheckPayload`, `AbilityCheckResult` и `resolve_ability_check`. Result использует `D20Roll`; total вычисляется из `roll.selected`. `AbilityCheckResolvedPayloadV1`/V1 builder сохранены как legacy NORMAL-only schema, а `AbilityCheckResolvedPayloadV2`/V2 builder являются current writer. Shared `ability_modifier` живёт в `domain.rules.ability`, а прежний import path через `domain.rules.ability_check` сохранён; правило `(score - 10) // 2` не хранится ни в `AbilityScores`, ни в State.
* Character Saving Throw vertical slice (§3.13): generic `SavingThrowCommand` / `SavingThrowResolved` V1 и character-specific `resolve_character_saving_throw`. Resolver получает matching `CreatureState` + `CharacterState`, использует shared `ability_modifier`, условную save proficiency membership и derived character bonus; `SavingThrowResult`/Event хранят contributions раздельно. Missing Creature = `ENTITY_NOT_FOUND`, missing Character projection = `INVALID_STATE`; monster и Death Saving Throws остаются deferred.
* Application orchestration (§2.2, §§3.10, 3.13): `EventMetadata`, `EventMetadataProvider`, explicit `AbilityCheckHandler` и `SavingThrowHandler`. Read-only handlers загружают State, находят нужные projections, вызывают concrete resolver, получают metadata через injected provider и собирают Event/`ResolutionResult`; они не читают clock, не генерируют ID, не мутируют State и не вызывают `StateStore.save()`.
* Proficiency foundation (§3.11): `character_proficiency_bonus(level)` — pure derived character-level rule. Authoritative input хранится в `CharacterState.total_level`, effective Saving Throw и Skill membership — в explicit `saving_throw_proficiencies: frozenset[Ability]` и `skill_proficiencies: frozenset[Skill]`. Bonus не хранится; raw Ability Check не изменён, а Skill Check, Expertise, monster/other proficiency и class progression остаются deferred.
* Skill/Character State foundation (§1.2.2, §3.2.3, §3.2.4, §12.9): `Skill` — closed 18-value identity-only `StrEnum` без fixed Ability mapping. Отдельный `CharacterState` является второй проекцией той же runtime character entity и использует ID существующего `CreatureState`; current State schema V3 хранит mandatory `skillProficiencies`, writer выпускает только V3, strict legacy V1 reader создаёт `characters=()`, а V2 reader создаёт empty Skill membership.
* Minimal d20 semantics (§3.12): closed `RollMode`, immutable `D20Roll` и concrete `resolve_d20_roll`, используемые Ability Check и Character Saving Throw. NORMAL использует один independent `"1d20"` call, ADVANTAGE/DISADVANTAGE — два; `"2d20"` и primitive-level natural-1/natural-20 interpretation не вводятся. Effective mode не является Command/API/AI input.

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

Отложены также EventStore, Event persistence/runtime-append в JSONL, применение
Events к State, replay и transaction/UoW.

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

Специфика команды живёт **только** внутри `payload`. Не выноси `targetId` и `weaponId` на верхний уровень Envelope.

Command Envelope — это JSON/boundary-контракт, а не обязательный generic Python Domain-класс. После boundary validation gameplay-команда представляется отдельным immutable typed dataclass с concrete typed payload; произвольный `dict[str, Any]` не проходит внутрь rule-resolution boundary. Generic Command inheritance hierarchy на текущем этапе не вводится.

**Жизненный цикл Command описан ровно в одном месте — §9.7:**

```text
Created → Validating → Rejected | Accepted → Resolving → Completed | Failed
```

Других словарей состояний нет. `Received`, `Valid`, `Invalid`, `Executing` отвергнуты (DEC-0015).

Event immutable: после записи не редактируется и не удаляется. Ошибку исправляет новое компенсирующее событие. Имя события — факт в прошедшем времени: `DamageApplied`, `AttackResolved`, `CreatureMoved`; не `ApplyDamage`, не `DoAttack`. `causedBy` связывает событие с породившим его событием — цепочку не терять.

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
* Парсер выражения приватен для реализации в Infrastructure; Domain о нём не знает.
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
* Current `state.json` содержит целочисленный `schemaVersion = 3`; writer выпускает только V3, reader принимает exact V3 и legacy V1/V2. V1 мигрирует в `characters=()`, V2 — в empty `skill_proficiencies`. Это версия схемы, а не ревизия State.
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
| Отдельные `Event` и `EventEnvelope` | один `GameEvent` |
| `datetime.now()`, naive datetime, смещение `+00:00` | aware UTC, передан снаружи, в JSON — `Z` |
| `state_changes` в `ResolutionResult` | такого поля нет |
| generic top-level `rolls` в `ResolutionResult` | roll находится в typed outcome и durable Event payload |
| `roll.total` в Ability Check | `D20Roll.selected`; `DiceRoll.total` остаётся суммой dice expression |
| Хранимый `modifier` в `AbilityScores` | чистое правило `(score - 10) // 2` |
| `AbilityCheckSucceeded` / `AbilityCheckFailed` | один `AbilityCheckResolved`, исход в `payload.succeeded` |

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
* Форматтер, линтер и type checker в репозитории **не настроены**. Не приноси Ruff, Black, mypy или их аналоги. Если проверка требуется — сообщи `not configured`.
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
