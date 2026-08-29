from dnd_engine.application.services.event_metadata import EventMetadataProvider
from dnd_engine.application.services.state_snapshot import (
    replace_creature_in_snapshot,
)
from dnd_engine.domain.commands.healing import ApplyHealingCommand
from dnd_engine.domain.errors import EngineError, ErrorCode
from dnd_engine.domain.events.healing import (
    apply_healing_applied_v1,
    build_healing_applied_v1,
)
from dnd_engine.domain.resolution import ResolutionResult
from dnd_engine.domain.rules.healing import HealingResult, resolve_healing
from dnd_engine.domain.services.state_store import StateStore


class HealingHandler:
    def __init__(
        self,
        *,
        state_store: StateStore,
        event_metadata_provider: EventMetadataProvider,
    ) -> None:
        self._state_store = state_store
        self._event_metadata_provider = event_metadata_provider

    def handle(self, command: ApplyHealingCommand) -> ResolutionResult[HealingResult]:
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
                        message="Healing actor was not found.",
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
                        message="Healing target was not found.",
                        entity_id=command.payload.target_id,
                        field="target_id",
                    ),
                ),
            )

        outcome = resolve_healing(command, target)
        metadata = self._event_metadata_provider.next_metadata(command.campaign_id)
        event = build_healing_applied_v1(
            event_id=metadata.event_id,
            timestamp=metadata.timestamp,
            command=command,
            outcome=outcome,
        )

        replacement_target = apply_healing_applied_v1(target, event)
        replacement_snapshot = replace_creature_in_snapshot(
            snapshot, replacement_target
        )

        self._state_store.save(replacement_snapshot)

        return ResolutionResult(
            success=True,
            command_id=command.command_id,
            outcome=outcome,
            events=(event,),
            errors=(),
        )
