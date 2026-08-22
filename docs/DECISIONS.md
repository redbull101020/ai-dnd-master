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
