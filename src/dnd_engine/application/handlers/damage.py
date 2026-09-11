from dnd_engine.application.services.event_metadata import EventMetadataProvider
from dnd_engine.application.services.state_snapshot import (
    replace_character_in_snapshot,
    replace_creature_in_snapshot,
)
from dnd_engine.domain.commands.damage import ApplyDamageCommand
from dnd_engine.domain.errors import EngineError, ErrorCode
from dnd_engine.domain.events.character_death_save import (
    apply_character_death_save_failure_recorded_v1,
    build_character_death_save_failure_recorded_v1,
)
from dnd_engine.domain.events.damage import (
    apply_damage_applied_v1,
    build_damage_applied_v1,
)
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.resolution import ResolutionResult
from dnd_engine.domain.rules.character_death_save import (
    resolve_character_death_save_failure,
)
from dnd_engine.domain.rules.damage import DamageResult, resolve_damage
from dnd_engine.domain.services.state_store import StateStore


class DamageHandler:
    def __init__(
        self,
        *,
        state_store: StateStore,
        event_metadata_provider: EventMetadataProvider,
    ) -> None:
        self._state_store = state_store
        self._event_metadata_provider = event_metadata_provider

    def handle(self, command: ApplyDamageCommand) -> ResolutionResult[DamageResult]:
        snapshot = self._state_store.load(command.campaign_id)

        actor = next(
            (
                candidate
                for candidate in snapshot.creatures
                if candidate.id == command.actor_id
            ),
            None,
        )

        if actor is None:
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.ENTITY_NOT_FOUND,
                        message="Damage actor was not found.",
                        entity_id=command.actor_id,
                    ),
                ),
            )

        target = next(
            (
                candidate
                for candidate in snapshot.creatures
                if candidate.id == command.payload.target_id
            ),
            None,
        )

        if target is None:
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.ENTITY_NOT_FOUND,
                        message="Damage target was not found.",
                        entity_id=command.payload.target_id,
                        field="target_id",
                    ),
                ),
            )

        outcome = resolve_damage(command, target)
        metadata = self._event_metadata_provider.next_metadata(command.campaign_id)
        damage_event = build_damage_applied_v1(
            event_id=metadata.event_id,
            timestamp=metadata.timestamp,
            command=command,
            outcome=outcome,
        )

        replacement_target = apply_damage_applied_v1(target, damage_event)
        replacement_snapshot = replace_creature_in_snapshot(
            snapshot, replacement_target
        )
        events: tuple[GameEvent, ...] = (damage_event,)

        character = next(
            (
                candidate
                for candidate in snapshot.characters
                if candidate.id == target.id
            ),
            None,
        )
        if character is not None and outcome.previous_hp == 0 and not character.dead:
            failure_outcome = resolve_character_death_save_failure(
                outcome,
                character,
                critical_hit=False,
            )
            failure_metadata = self._event_metadata_provider.next_metadata(
                command.campaign_id
            )
            failure_event = build_character_death_save_failure_recorded_v1(
                event_id=failure_metadata.event_id,
                timestamp=failure_metadata.timestamp,
                command_id=command.command_id,
                campaign_id=command.campaign_id,
                actor_id=command.actor_id,
                caused_by=damage_event.event_id,
                outcome=failure_outcome,
            )
            replacement_character = (
                apply_character_death_save_failure_recorded_v1(
                    character,
                    failure_event,
                )
            )
            replacement_snapshot = replace_character_in_snapshot(
                replacement_snapshot,
                replacement_character,
            )
            events += (failure_event,)

        self._state_store.save(replacement_snapshot)

        return ResolutionResult(
            success=True,
            command_id=command.command_id,
            outcome=outcome,
            events=events,
            errors=(),
        )
