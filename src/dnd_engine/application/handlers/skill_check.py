from dnd_engine.application.services.event_metadata import EventMetadataProvider
from dnd_engine.domain.commands.skill_check import SkillCheckCommand
from dnd_engine.domain.errors import EngineError, ErrorCode
from dnd_engine.domain.events.skill_check import build_skill_check_resolved_v1
from dnd_engine.domain.resolution import ResolutionResult
from dnd_engine.domain.rules.skill_check import (
    SkillCheckResult,
    resolve_character_skill_check,
)
from dnd_engine.domain.services.dice import DiceEngine
from dnd_engine.domain.services.state_store import StateStore


class SkillCheckHandler:
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
        command: SkillCheckCommand,
    ) -> ResolutionResult[SkillCheckResult]:
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
                        message="Skill Check actor was not found.",
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
                        message="Skill Check actor has no CharacterState.",
                        entity_id=command.actor_id,
                        field="characters",
                    ),
                ),
            )

        outcome = resolve_character_skill_check(
            command,
            creature,
            character,
            self._dice,
        )
        metadata = self._event_metadata_provider.next_metadata(command.campaign_id)
        event = build_skill_check_resolved_v1(
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
