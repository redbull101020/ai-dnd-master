from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from dnd_engine.domain.commands.start_combat import StartCombatCommand
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.rules.start_combat import InitiativeEntry, StartCombatResult
from dnd_engine.domain.state.combat import CombatState
from dnd_engine.domain.value_objects.d20 import D20Roll, RollMode


_COMBAT_STARTED_V1_PAYLOAD_FIELDS = frozenset(
    {"combatId", "round", "order", "entries"}
)
_INITIATIVE_ENTRY_FIELDS = frozenset({"creatureId", "roll", "modifier", "total"})
_D20_ROLL_FIELDS = frozenset({"mode", "rolls", "selected"})


@dataclass(frozen=True)
class CombatStartedPayloadV1:
    combat_id: str
    round: int
    order: tuple[str, ...]
    entries: tuple[InitiativeEntry, ...]

    def __post_init__(self) -> None:
        if type(self.combat_id) is not str:
            raise TypeError("combat_id must be a str")
        if type(self.round) is not int:
            raise TypeError("round must be an int")
        if self.round != 1:
            raise ValueError("round must be 1 for CombatStarted")
        if type(self.order) is not tuple:
            raise TypeError("order must be a tuple")
        if type(self.entries) is not tuple:
            raise TypeError("entries must be a tuple")
        if not all(isinstance(entry, InitiativeEntry) for entry in self.entries):
            raise TypeError("entries must contain only InitiativeEntry values")
        if self.order != tuple(entry.creature_id for entry in self.entries):
            raise ValueError("order must match entries in the same sequence")


def build_combat_started_v1(
    *,
    event_id: str,
    timestamp: datetime,
    command: StartCombatCommand,
    outcome: StartCombatResult,
) -> GameEvent:
    if not isinstance(command, StartCombatCommand):
        raise TypeError("command must be a StartCombatCommand")
    if not isinstance(outcome, StartCombatResult):
        raise TypeError("outcome must be a StartCombatResult")
    if outcome.combat_id != command.payload.combat_id:
        raise ValueError("outcome combat_id must match command payload combat_id")
    if set(outcome.order) != set(command.payload.participant_ids):
        raise ValueError(
            "outcome order must contain exactly the command participant_ids"
        )

    payload = CombatStartedPayloadV1(
        combat_id=outcome.combat_id,
        round=outcome.round,
        order=outcome.order,
        entries=outcome.entries,
    )

    return GameEvent(
        event_id=event_id,
        command_id=command.command_id,
        type="CombatStarted",
        version=1,
        campaign_id=command.campaign_id,
        timestamp=timestamp,
        actor_id=command.actor_id,
        caused_by=None,
        payload={
            "combatId": payload.combat_id,
            "round": payload.round,
            "order": payload.order,
            "entries": tuple(
                {
                    "creatureId": entry.creature_id,
                    "roll": {
                        "mode": entry.roll.mode.value,
                        "rolls": entry.roll.rolls,
                        "selected": entry.roll.selected,
                    },
                    "modifier": entry.modifier,
                    "total": entry.total,
                }
                for entry in payload.entries
            ),
        },
    )


def _require_mapping(value: object, location: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"payload {location} must be a mapping")
    return value  # type: ignore[return-value]


def _payload_str(value: object, field_name: str) -> str:
    if type(value) is not str:
        raise TypeError(f"payload {field_name} must be a str")
    return value


def _payload_int(value: object, field_name: str) -> int:
    if type(value) is not int:
        raise TypeError(f"payload {field_name} must be an int")
    return value


def _decode_roll_mode(value: object, field_name: str) -> RollMode:
    if type(value) is not str:
        raise TypeError(f"payload {field_name} must be a str")
    try:
        return RollMode(value)
    except ValueError as error:
        raise ValueError(
            f"payload {field_name} has unknown RollMode value: {value!r}"
        ) from error


def _decode_d20_roll(value: object, location: str) -> D20Roll:
    mapping = _require_mapping(value, location)
    if mapping.keys() != _D20_ROLL_FIELDS:
        raise ValueError(f"payload {location} has unexpected fields")
    rolls_data = mapping["rolls"]
    if type(rolls_data) is not tuple:
        raise TypeError(f"payload {location}.rolls must be a tuple")
    rolls = tuple(
        _payload_int(value, f"{location}.rolls") for value in rolls_data
    )
    return D20Roll(
        mode=_decode_roll_mode(mapping["mode"], f"{location}.mode"),
        rolls=rolls,
        selected=_payload_int(mapping["selected"], f"{location}.selected"),
    )


def _decode_initiative_entry(value: object, index: int) -> InitiativeEntry:
    location = f"entries[{index}]"
    mapping = _require_mapping(value, location)
    if mapping.keys() != _INITIATIVE_ENTRY_FIELDS:
        raise ValueError(f"payload {location} has unexpected fields")
    return InitiativeEntry(
        creature_id=_payload_str(mapping["creatureId"], f"{location}.creatureId"),
        roll=_decode_d20_roll(mapping["roll"], f"{location}.roll"),
        modifier=_payload_int(mapping["modifier"], f"{location}.modifier"),
        total=_payload_int(mapping["total"], f"{location}.total"),
    )


def apply_combat_started_v1(event: GameEvent) -> CombatState:
    if not isinstance(event, GameEvent):
        raise TypeError("event must be a GameEvent")
    if event.type != "CombatStarted":
        raise ValueError("event type must be CombatStarted")
    if event.version != 1:
        raise ValueError("event version must be 1")
    if event.payload.keys() != _COMBAT_STARTED_V1_PAYLOAD_FIELDS:
        raise ValueError("CombatStarted V1 payload has unexpected fields")

    round_ = _payload_int(event.payload["round"], "round")
    if round_ != 1:
        raise ValueError("payload round must be 1 for CombatStarted")

    order_data = event.payload["order"]
    if type(order_data) is not tuple:
        raise TypeError("payload order must be a tuple")
    order = tuple(_payload_str(value, "order item") for value in order_data)

    entries_data = event.payload["entries"]
    if type(entries_data) is not tuple:
        raise TypeError("payload entries must be a tuple")
    entries = tuple(
        _decode_initiative_entry(value, index)
        for index, value in enumerate(entries_data)
    )

    decoded = CombatStartedPayloadV1(
        combat_id=_payload_str(event.payload["combatId"], "combatId"),
        round=round_,
        order=order,
        entries=entries,
    )

    return CombatState(
        id=decoded.combat_id,
        round=decoded.round,
        order=decoded.order,
        active_index=0,
    )
