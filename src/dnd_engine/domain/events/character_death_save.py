from dataclasses import dataclass, replace
from datetime import datetime
from typing import cast

from dnd_engine.domain.events.game_event import GameEvent, JSONValue
from dnd_engine.domain.rules.character_death_save import (
    CharacterDeathSaveFailureResult,
    CharacterDeathSaveResult,
)
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.value_objects.d20 import D20Roll, RollMode


_RESOLVED_FIELDS = frozenset({"characterId", "roll", "previousSuccesses", "previousFailures", "previousStable", "previousDead", "successes", "failures", "stable", "dead"})
_FAILURE_FIELDS = frozenset({"characterId", "previousFailures", "failures", "previousStable", "stable", "previousDead", "dead", "criticalHit"})
_ROLL_FIELDS = frozenset({"mode", "rolls", "selected"})


@dataclass(frozen=True)
class CharacterDeathSaveResolvedPayloadV1:
    character_id: str
    roll: D20Roll
    previous_successes: int
    previous_failures: int
    previous_stable: bool
    previous_dead: bool
    successes: int
    failures: int
    stable: bool
    dead: bool


@dataclass(frozen=True)
class CharacterDeathSaveFailureRecordedPayloadV1:
    character_id: str
    previous_failures: int
    failures: int
    previous_stable: bool
    stable: bool
    previous_dead: bool
    dead: bool
    critical_hit: bool


def build_character_death_save_resolved_v1(*, event_id: str, timestamp: datetime, command_id: str, campaign_id: str, actor_id: str, caused_by: str, outcome: CharacterDeathSaveResult) -> GameEvent:
    if not isinstance(outcome, CharacterDeathSaveResult):
        raise TypeError("outcome must be a CharacterDeathSaveResult")
    if type(actor_id) is not str:
        raise TypeError("actor_id must be a str")
    if type(caused_by) is not str:
        raise TypeError("caused_by must be a str")
    return GameEvent(event_id=event_id, command_id=command_id, type="CharacterDeathSaveResolved", version=1, campaign_id=campaign_id, timestamp=timestamp, actor_id=actor_id, caused_by=caused_by, payload={
        "characterId": outcome.character_id,
        "roll": {"mode": outcome.roll.mode.value, "rolls": outcome.roll.rolls, "selected": outcome.roll.selected},
        "previousSuccesses": outcome.previous_successes, "previousFailures": outcome.previous_failures,
        "previousStable": outcome.previous_stable, "previousDead": outcome.previous_dead,
        "successes": outcome.successes, "failures": outcome.failures, "stable": outcome.stable, "dead": outcome.dead,
    })


def build_character_death_save_failure_recorded_v1(*, event_id: str, timestamp: datetime, command_id: str, campaign_id: str, actor_id: str, caused_by: str, outcome: CharacterDeathSaveFailureResult) -> GameEvent:
    if not isinstance(outcome, CharacterDeathSaveFailureResult):
        raise TypeError("outcome must be a CharacterDeathSaveFailureResult")
    if type(actor_id) is not str:
        raise TypeError("actor_id must be a str")
    if type(caused_by) is not str:
        raise TypeError("caused_by must be a str")
    return GameEvent(event_id=event_id, command_id=command_id, type="CharacterDeathSaveFailureRecorded", version=1, campaign_id=campaign_id, timestamp=timestamp, actor_id=actor_id, caused_by=caused_by, payload={
        "characterId": outcome.character_id, "previousFailures": outcome.previous_failures, "failures": outcome.failures,
        "previousStable": outcome.previous_stable, "stable": outcome.stable, "previousDead": outcome.previous_dead,
        "dead": outcome.dead, "criticalHit": outcome.critical_hit,
    })


def _str(value: object, name: str) -> str:
    if type(value) is not str:
        raise TypeError(f"payload {name} must be a str")
    return value


def _int(value: object, name: str) -> int:
    if type(value) is not int:
        raise TypeError(f"payload {name} must be an int")
    return value


def _bool(value: object, name: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"payload {name} must be a bool")
    return value


def _roll(value: JSONValue) -> D20Roll:
    if not hasattr(value, "keys") or value.keys() != _ROLL_FIELDS:  # type: ignore[union-attr]
        raise ValueError("CharacterDeathSaveResolved V1 roll has unexpected fields")
    mapping = cast(dict[str, object], value)
    mode = _str(mapping["mode"], "roll.mode")
    try:
        roll_mode = RollMode(mode)
    except ValueError as error:
        raise ValueError("payload roll.mode must be a valid RollMode") from error
    raw_rolls = mapping["rolls"]
    if not isinstance(raw_rolls, tuple):
        raise TypeError("payload roll.rolls must be a tuple")
    return D20Roll(mode=roll_mode, rolls=raw_rolls, selected=_int(mapping["selected"], "roll.selected"))


def apply_character_death_save_resolved_v1(character: CharacterState, event: GameEvent) -> CharacterState:
    if not isinstance(character, CharacterState):
        raise TypeError("character must be a CharacterState")
    if not isinstance(event, GameEvent):
        raise TypeError("event must be a GameEvent")
    if event.type != "CharacterDeathSaveResolved" or event.version != 1:
        raise ValueError("event must be CharacterDeathSaveResolved V1")
    if event.payload.keys() != _RESOLVED_FIELDS:
        raise ValueError("CharacterDeathSaveResolved V1 payload has unexpected fields")
    payload = CharacterDeathSaveResolvedPayloadV1(
        character_id=_str(event.payload["characterId"], "characterId"), roll=_roll(event.payload["roll"]),
        previous_successes=_int(event.payload["previousSuccesses"], "previousSuccesses"), previous_failures=_int(event.payload["previousFailures"], "previousFailures"),
        previous_stable=_bool(event.payload["previousStable"], "previousStable"), previous_dead=_bool(event.payload["previousDead"], "previousDead"),
        successes=_int(event.payload["successes"], "successes"), failures=_int(event.payload["failures"], "failures"),
        stable=_bool(event.payload["stable"], "stable"), dead=_bool(event.payload["dead"], "dead"),
    )
    if payload.character_id != character.id:
        raise ValueError("event characterId must match character id")
    if (payload.previous_successes, payload.previous_failures, payload.previous_stable, payload.previous_dead) != (character.death_save_successes, character.death_save_failures, character.death_save_stable, character.dead):
        raise ValueError("event previous lifecycle state is stale")
    return replace(character, death_save_successes=payload.successes, death_save_failures=payload.failures, death_save_stable=payload.stable, dead=payload.dead)


def apply_character_death_save_failure_recorded_v1(character: CharacterState, event: GameEvent) -> CharacterState:
    if not isinstance(character, CharacterState):
        raise TypeError("character must be a CharacterState")
    if not isinstance(event, GameEvent):
        raise TypeError("event must be a GameEvent")
    if event.type != "CharacterDeathSaveFailureRecorded" or event.version != 1:
        raise ValueError("event must be CharacterDeathSaveFailureRecorded V1")
    if event.payload.keys() != _FAILURE_FIELDS:
        raise ValueError("CharacterDeathSaveFailureRecorded V1 payload has unexpected fields")
    payload = CharacterDeathSaveFailureRecordedPayloadV1(
        character_id=_str(event.payload["characterId"], "characterId"), previous_failures=_int(event.payload["previousFailures"], "previousFailures"), failures=_int(event.payload["failures"], "failures"),
        previous_stable=_bool(event.payload["previousStable"], "previousStable"), stable=_bool(event.payload["stable"], "stable"), previous_dead=_bool(event.payload["previousDead"], "previousDead"),
        dead=_bool(event.payload["dead"], "dead"), critical_hit=_bool(event.payload["criticalHit"], "criticalHit"),
    )
    if payload.character_id != character.id:
        raise ValueError("event characterId must match character id")
    if (payload.previous_failures, payload.previous_stable, payload.previous_dead) != (character.death_save_failures, character.death_save_stable, character.dead):
        raise ValueError("event previous lifecycle state is stale")
    return replace(character, death_save_failures=payload.failures, death_save_stable=payload.stable, dead=payload.dead)
