from dnd_engine.application.services.event_metadata import EventMetadataProvider
from dnd_engine.domain.commands.apply_condition import ApplyConditionCommand
from dnd_engine.domain.errors import EngineError, ErrorCode
from dnd_engine.domain.events.apply_condition import (
    apply_condition_applied_v1,
    build_condition_applied_v1,
)
from dnd_engine.domain.resolution import ResolutionResult
from dnd_engine.domain.rules.apply_condition import (
    ConditionApplicationResult,
    resolve_condition_application,
)
from dnd_engine.domain.services.state_store import StateStore
from dnd_engine.domain.state.snapshot import StateSnapshot


class ApplyConditionHandler:
    def __init__(
        self,
        *,
        state_store: StateStore,
        event_metadata_provider: EventMetadataProvider,
    ) -> None:
        self._state_store = state_store
        self._event_metadata_provider = event_metadata_provider

    def handle(
        self, command: ApplyConditionCommand
    ) -> ResolutionResult[ConditionApplicationResult]:
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
                        message="Condition application actor was not found.",
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
                        message="Condition application target was not found.",
                        entity_id=command.payload.target_id,
                        field="target_id",
                    ),
                ),
            )

        outcome = resolve_condition_application(command, target)
        metadata = self._event_metadata_provider.next_metadata(command.campaign_id)
        event = build_condition_applied_v1(
            event_id=metadata.event_id,
            timestamp=metadata.timestamp,
            command=command,
            outcome=outcome,
        )

        replacement_target = apply_condition_applied_v1(target, event)
        replacement_creatures = tuple(
            replacement_target if creature.id == target.id else creature
            for creature in snapshot.creatures
        )
        replacement_snapshot = StateSnapshot(
            campaign=snapshot.campaign,
            creatures=replacement_creatures,
            characters=snapshot.characters,
        )

        self._state_store.save(replacement_snapshot)

        return ResolutionResult(
            success=True,
            command_id=command.command_id,
            outcome=outcome,
            events=(event,),
            errors=(),
        )
