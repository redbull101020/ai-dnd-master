from dnd_engine.application.services.event_metadata import EventMetadataProvider
from dnd_engine.application.services.state_snapshot import (
    replace_character_in_snapshot,
    replace_creature_in_snapshot,
)
from dnd_engine.domain.events.character_death_save import (
    apply_character_death_save_resolved_v1,
    build_character_death_save_resolved_v1,
)
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.events.healing import (
    apply_healing_applied_v1,
    build_healing_applied_from_death_save_v1,
)
from dnd_engine.domain.rules.character_death_save import (
    resolve_character_death_save,
)
from dnd_engine.domain.rules.healing import resolve_healing_amount
from dnd_engine.domain.services.dice import DiceEngine
from dnd_engine.domain.state.snapshot import StateSnapshot


def apply_active_character_death_save(
    snapshot: StateSnapshot,
    *,
    active_creature_id: str,
    dice: DiceEngine,
    event_metadata_provider: EventMetadataProvider,
    command_id: str,
    campaign_id: str,
    actor_id: str,
    caused_by: str,
) -> tuple[StateSnapshot, tuple[GameEvent, ...]]:
    creature = next(
        candidate
        for candidate in snapshot.creatures
        if candidate.id == active_creature_id
    )
    character = next(
        (
            candidate
            for candidate in snapshot.characters
            if candidate.id == active_creature_id
        ),
        None,
    )
    if (
        character is None
        or creature.current_hp != 0
        or character.dead
        or character.death_save_stable
    ):
        return snapshot, ()

    outcome = resolve_character_death_save(character, dice)
    metadata = event_metadata_provider.next_metadata(campaign_id)
    event = build_character_death_save_resolved_v1(
        event_id=metadata.event_id,
        timestamp=metadata.timestamp,
        command_id=command_id,
        campaign_id=campaign_id,
        actor_id=actor_id,
        caused_by=caused_by,
        outcome=outcome,
    )
    replacement_character = apply_character_death_save_resolved_v1(character, event)
    replacement_snapshot = replace_character_in_snapshot(
        snapshot,
        replacement_character,
    )
    events: tuple[GameEvent, ...] = (event,)

    if outcome.hp_regain_amount == 1:
        healing_outcome = resolve_healing_amount(
            creature,
            amount=outcome.hp_regain_amount,
        )
        healing_metadata = event_metadata_provider.next_metadata(campaign_id)
        healing_event = build_healing_applied_from_death_save_v1(
            event_id=healing_metadata.event_id,
            timestamp=healing_metadata.timestamp,
            command_id=command_id,
            campaign_id=campaign_id,
            actor_id=actor_id,
            caused_by=event.event_id,
            outcome=healing_outcome,
        )
        replacement_creature = apply_healing_applied_v1(creature, healing_event)
        replacement_snapshot = replace_creature_in_snapshot(
            replacement_snapshot,
            replacement_creature,
        )
        events += (healing_event,)

    return replacement_snapshot, events
