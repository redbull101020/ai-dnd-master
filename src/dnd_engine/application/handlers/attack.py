from dnd_engine.application.services.event_metadata import EventMetadataProvider
from dnd_engine.domain.commands.attack import AttackCommand
from dnd_engine.domain.definitions.monster import MonsterDefinition
from dnd_engine.domain.errors import EngineError, ErrorCode
from dnd_engine.domain.events.attack import build_attack_resolved_v1
from dnd_engine.domain.resolution import ResolutionResult
from dnd_engine.domain.rules.attack import (
    AttackResult,
    resolve_character_unarmed_attack,
)
from dnd_engine.domain.services.definitions import (
    DefinitionNotFoundError,
    DefinitionSource,
    DefinitionTypeMismatchError,
)
from dnd_engine.domain.services.dice import DiceEngine
from dnd_engine.domain.services.state_store import StateStore


class AttackHandler:
    def __init__(
        self,
        *,
        state_store: StateStore,
        definition_source: DefinitionSource,
        dice: DiceEngine,
        event_metadata_provider: EventMetadataProvider,
    ) -> None:
        self._state_store = state_store
        self._definition_source = definition_source
        self._dice = dice
        self._event_metadata_provider = event_metadata_provider

    def handle(self, command: AttackCommand) -> ResolutionResult[AttackResult]:
        snapshot = self._state_store.load(command.campaign_id)
        actor_creature = next(
            (
                candidate
                for candidate in snapshot.creatures
                if candidate.id == command.actor_id
            ),
            None,
        )

        if actor_creature is None:
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.ENTITY_NOT_FOUND,
                        message="Attack actor was not found.",
                        entity_id=command.actor_id,
                    ),
                ),
            )

        actor_character = next(
            (
                candidate
                for candidate in snapshot.characters
                if candidate.id == command.actor_id
            ),
            None,
        )

        if actor_character is None:
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.INVALID_STATE,
                        message="Attack actor has no CharacterState.",
                        entity_id=command.actor_id,
                        field="characters",
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
                        message="Attack target was not found.",
                        entity_id=command.payload.target_id,
                        field="target_id",
                    ),
                ),
            )

        try:
            monster_definition = self._definition_source.get_definition(
                ruleset_id=snapshot.campaign.ruleset_id,
                ruleset_version=snapshot.campaign.ruleset_version,
                definition_id=target.definition_id,
                expected_type=MonsterDefinition,
            )
        except DefinitionNotFoundError:
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.DEFINITION_NOT_FOUND,
                        message="Attack target Definition was not found.",
                        entity_id=target.definition_id,
                        field="definition_id",
                    ),
                ),
            )
        except DefinitionTypeMismatchError:
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.INVALID_STATE,
                        message="Attack target Definition is not a MonsterDefinition.",
                        entity_id=target.id,
                        field="definition_id",
                    ),
                ),
            )

        target_armor_class = monster_definition.armor_class
        outcome = resolve_character_unarmed_attack(
            command,
            actor_creature,
            actor_character,
            self._dice,
            target_armor_class=target_armor_class,
        )
        metadata = self._event_metadata_provider.next_metadata(command.campaign_id)
        event = build_attack_resolved_v1(
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
