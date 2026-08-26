from dnd_engine.application.services.event_metadata import EventMetadataProvider
from dnd_engine.domain.commands.ability_check import AbilityCheckCommand
from dnd_engine.domain.errors import EngineError, ErrorCode
from dnd_engine.domain.events.ability_check import build_ability_check_resolved_v2
from dnd_engine.domain.resolution import ResolutionResult
from dnd_engine.domain.rules.ability_check import (
    AbilityCheckResult,
    resolve_ability_check,
)
from dnd_engine.domain.services.dice import DiceEngine
from dnd_engine.domain.services.state_store import StateStore


class AbilityCheckHandler:
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
        command: AbilityCheckCommand,
    ) -> ResolutionResult[AbilityCheckResult]:
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
                        message="Ability Check actor was not found.",
                        entity_id=command.actor_id,
                    ),
                ),
            )

        outcome = resolve_ability_check(command, creature, self._dice)
        metadata = self._event_metadata_provider.next_metadata(command.campaign_id)
        event = build_ability_check_resolved_v2(
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
