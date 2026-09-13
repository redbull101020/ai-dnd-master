import dataclasses

from dnd_engine.application.services.event_metadata import EventMetadataProvider
from dnd_engine.domain.commands.end_combat import EndCombatCommand
from dnd_engine.domain.errors import EngineError, ErrorCode
from dnd_engine.domain.events.end_combat import (
    apply_combat_ended_v1,
    build_combat_ended_v1,
)
from dnd_engine.domain.resolution import ResolutionResult
from dnd_engine.domain.rules.end_combat import EndCombatResult, resolve_end_combat
from dnd_engine.domain.services.state_store import StateStore


class EndCombatHandler:
    def __init__(
        self,
        *,
        state_store: StateStore,
        event_metadata_provider: EventMetadataProvider,
    ) -> None:
        self._state_store = state_store
        self._event_metadata_provider = event_metadata_provider

    def handle(self, command: EndCombatCommand) -> ResolutionResult[EndCombatResult]:
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
                        message="End Combat actor was not found.",
                        entity_id=command.actor_id,
                    ),
                ),
            )

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

        outcome = resolve_end_combat(command, combat)
        metadata = self._event_metadata_provider.next_metadata(command.campaign_id)
        event = build_combat_ended_v1(
            event_id=metadata.event_id,
            timestamp=metadata.timestamp,
            command=command,
            outcome=outcome,
        )

        replacement_combat = apply_combat_ended_v1(  # type: ignore[func-returns-value]
            combat, event
        )
        replacement_snapshot = dataclasses.replace(snapshot, combat=replacement_combat)

        self._state_store.save(replacement_snapshot)

        return ResolutionResult(
            success=True,
            command_id=command.command_id,
            outcome=outcome,
            events=(event,),
            errors=(),
        )
