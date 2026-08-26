from dnd_engine.application.services.event_metadata import EventMetadataProvider
from dnd_engine.domain.commands.saving_throw import SavingThrowCommand
from dnd_engine.domain.errors import EngineError, ErrorCode
from dnd_engine.domain.events.saving_throw import build_saving_throw_resolved_v1
from dnd_engine.domain.resolution import ResolutionResult
from dnd_engine.domain.rules.saving_throw import (
    SavingThrowResult,
    resolve_character_saving_throw,
)
from dnd_engine.domain.services.dice import DiceEngine
from dnd_engine.domain.services.state_store import StateStore


class SavingThrowHandler:
    def __init__(
        self,
        *,
        state_store: StateStore,
        dice: DiceEngine,
        event_metadata_provider: EventMetadataProvider,
    ) -> None:
        self._state_store = state_store
        self._dice = dice
        self._event_metadata_provider = event_metadata_provider

    def handle(
        self,
        command: SavingThrowCommand,
    ) -> ResolutionResult[SavingThrowResult]:
        snapshot = self._state_store.load(command.campaign_id)
        creature = next(
            (
                candidate
                for candidate in snapshot.creatures
                if candidate.id == command.actor_id
            ),
            None,
        )

        if creature is None:
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.ENTITY_NOT_FOUND,
                        message="Saving Throw actor was not found.",
                        entity_id=command.actor_id,
                    ),
                ),
            )

        character = next(
            (
                candidate
                for candidate in snapshot.characters
                if candidate.id == command.actor_id
            ),
            None,
        )

        if character is None:
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.INVALID_STATE,
                        message="Saving Throw actor has no CharacterState.",
                        entity_id=command.actor_id,
                        field="characters",
                    ),
                ),
            )

        outcome = resolve_character_saving_throw(
            command,
            creature,
            character,
            self._dice,
        )
        metadata = self._event_metadata_provider.next_metadata(command.campaign_id)
        event = build_saving_throw_resolved_v1(
            event_id=metadata.event_id,
            timestamp=metadata.timestamp,
            command=command,
            outcome=outcome,
        )

        return ResolutionResult(
            success=True,
            command_id=command.command_id,
            outcome=outcome,
            events=(event,),
            errors=(),
        )
