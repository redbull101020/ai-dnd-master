import dataclasses

from dnd_engine.application.services.event_metadata import EventMetadataProvider
from dnd_engine.domain.commands.advance_turn import AdvanceTurnCommand
from dnd_engine.domain.errors import EngineError, ErrorCode
from dnd_engine.domain.events.advance_turn import (
    apply_turn_advanced_v1,
    build_turn_advanced_v1,
)
from dnd_engine.domain.resolution import ResolutionResult
from dnd_engine.domain.rules.advance_turn import (
    AdvanceTurnResult,
    resolve_advance_turn,
)
from dnd_engine.domain.services.state_store import StateStore


class AdvanceTurnHandler:
    def __init__(
        self,
        *,
        state_store: StateStore,
        event_metadata_provider: EventMetadataProvider,
    ) -> None:
        self._state_store = state_store
        self._event_metadata_provider = event_metadata_provider

    def handle(
        self, command: AdvanceTurnCommand
    ) -> ResolutionResult[AdvanceTurnResult]:
        snapshot = self._state_store.load(command.campaign_id)
        combat = snapshot.combat

        if combat is None or combat.id != command.payload.combat_id:
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.ENTITY_NOT_FOUND,
                        message="Combat was not found.",
                        entity_id=command.payload.combat_id,
                        field="combat_id",
                    ),
                ),
            )

        if command.actor_id != combat.active_creature_id:
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.ACTION_NOT_AVAILABLE,
                        message="Only the active combatant may advance the turn.",
                        entity_id=command.actor_id,
                    ),
                ),
            )

        outcome = resolve_advance_turn(command, combat)
        metadata = self._event_metadata_provider.next_metadata(command.campaign_id)
        event = build_turn_advanced_v1(
            event_id=metadata.event_id,
            timestamp=metadata.timestamp,
            command=command,
            outcome=outcome,
        )

        replacement_combat = apply_turn_advanced_v1(combat, event)
        replacement_snapshot = dataclasses.replace(snapshot, combat=replacement_combat)

        self._state_store.save(replacement_snapshot)

        return ResolutionResult(
            success=True,
            command_id=command.command_id,
            outcome=outcome,
            events=(event,),
            errors=(),
        )
