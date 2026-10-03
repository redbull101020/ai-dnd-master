from dataclasses import replace

from dnd_engine.application.services.event_metadata import EventMetadataProvider
from dnd_engine.domain.commands.move_combatant import MoveCombatantCommand
from dnd_engine.domain.definitions.monster import MonsterDefinition
from dnd_engine.domain.errors import EngineError, ErrorCode
from dnd_engine.domain.events.move_combatant import (
    apply_combatant_moved_v1,
    build_combatant_moved_v1,
)
from dnd_engine.domain.resolution import ResolutionResult
from dnd_engine.domain.rules.move_combatant import MoveCombatantResult, resolve_move_combatant
from dnd_engine.domain.services.definitions import (
    DefinitionNotFoundError,
    DefinitionSource,
    DefinitionTypeMismatchError,
)
from dnd_engine.domain.services.state_store import StateStore


class MoveCombatantHandler:
    def __init__(
        self,
        *,
        state_store: StateStore,
        definition_source: DefinitionSource,
        event_metadata_provider: EventMetadataProvider,
    ) -> None:
        self._state_store = state_store
        self._definition_source = definition_source
        self._event_metadata_provider = event_metadata_provider

    def handle(self, command: MoveCombatantCommand) -> ResolutionResult[MoveCombatantResult]:
        def reject(
            code: ErrorCode, message: str, entity_id: str, field: str | None = None,
        ) -> ResolutionResult[MoveCombatantResult]:
            return ResolutionResult(
                success=False, command_id=command.command_id, outcome=None, events=(),
                errors=(EngineError(code=code, message=message, entity_id=entity_id, field=field),),
            )

        snapshot = self._state_store.load(command.campaign_id)
        actor = next((c for c in snapshot.creatures if c.id == command.actor_id), None)
        if actor is None:
            return reject(ErrorCode.ENTITY_NOT_FOUND, "Movement actor was not found.", command.actor_id)
        combat = snapshot.combat
        if combat is None or combat.id != command.payload.combat_id:
            return reject(ErrorCode.ENTITY_NOT_FOUND, "Combat was not found.", command.payload.combat_id, "combat_id")
        if actor.id != combat.active_creature_id:
            return reject(ErrorCode.ACTION_NOT_AVAILABLE, "Movement actor is not active.", actor.id)
        if any(c.id == actor.id for c in snapshot.characters):
            return reject(ErrorCode.ACTION_NOT_AVAILABLE, "Character Movement is unsupported.", actor.id)
        try:
            definition = self._definition_source.get_definition(
                ruleset_id=snapshot.campaign.ruleset_id,
                ruleset_version=snapshot.campaign.ruleset_version,
                definition_id=actor.definition_id,
                expected_type=MonsterDefinition,
            )
        except DefinitionNotFoundError:
            return reject(ErrorCode.DEFINITION_NOT_FOUND, "Movement actor Definition was not found.", actor.definition_id, "definition_id")
        except DefinitionTypeMismatchError:
            return reject(ErrorCode.INVALID_STATE, "Movement actor Definition is not a MonsterDefinition.", actor.id, "definition_id")
        if actor.current_hp == 0:
            return reject(ErrorCode.ACTION_NOT_AVAILABLE, "Movement actor has 0 current HP.", actor.id)
        if definition.walking_speed is None:
            return reject(ErrorCode.ACTION_NOT_AVAILABLE, "Monster has no supported walking speed.", actor.id, "walking_speed")
        position = next((p for p in combat.positions if p.creature_id == actor.id), None)
        if position is None:
            return reject(ErrorCode.ACTION_NOT_AVAILABLE, "Movement actor has no Combat position.", actor.id, "position")
        if (position.x, position.y) == (command.payload.x, command.payload.y):
            return reject(ErrorCode.INVALID_COMMAND, "Movement destination equals current position.", actor.id, "position")
        outcome = resolve_move_combatant(command, combat, position)
        if outcome.movement_spent > definition.walking_speed:
            return reject(ErrorCode.OUT_OF_RANGE, "Movement exceeds walking speed.", actor.id, "position")
        metadata = self._event_metadata_provider.next_metadata(command.campaign_id)
        event = build_combatant_moved_v1(
            event_id=metadata.event_id, timestamp=metadata.timestamp, command=command, outcome=outcome,
        )
        replacement_combat = apply_combatant_moved_v1(combat, event)
        self._state_store.save(replace(snapshot, combat=replacement_combat))
        return ResolutionResult(
            success=True, command_id=command.command_id, outcome=outcome, events=(event,), errors=(),
        )
