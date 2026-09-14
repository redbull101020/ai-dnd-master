import dataclasses

from dnd_engine.application.services.event_metadata import EventMetadataProvider
from dnd_engine.domain.commands.place_combatant import PlaceCombatantCommand
from dnd_engine.domain.errors import EngineError, ErrorCode
from dnd_engine.domain.events.place_combatant import (
    apply_combatant_placed_v1,
    build_combatant_placed_v1,
)
from dnd_engine.domain.resolution import ResolutionResult
from dnd_engine.domain.rules.place_combatant import (
    PlaceCombatantResult,
    resolve_place_combatant,
)
from dnd_engine.domain.services.state_store import StateStore


class PlaceCombatantHandler:
    def __init__(
        self,
        *,
        state_store: StateStore,
        event_metadata_provider: EventMetadataProvider,
    ) -> None:
        self._state_store = state_store
        self._event_metadata_provider = event_metadata_provider

    def handle(
        self, command: PlaceCombatantCommand
    ) -> ResolutionResult[PlaceCombatantResult]:
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
                        message="Place Combatant actor was not found.",
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

        subject = next(
            (
                candidate
                for candidate in snapshot.creatures
                if candidate.id == command.payload.creature_id
            ),
            None,
        )

        if subject is None:
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.ENTITY_NOT_FOUND,
                        message="Placement subject was not found.",
                        entity_id=command.payload.creature_id,
                        field="creature_id",
                    ),
                ),
            )

        if subject.id not in combat.order:
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.ACTION_NOT_AVAILABLE,
                        message="Placement subject is not a Combat participant.",
                        entity_id=command.payload.creature_id,
                        field="creature_id",
                    ),
                ),
            )

        if any(
            position.creature_id == subject.id for position in combat.positions
        ):
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.ACTION_NOT_AVAILABLE,
                        message="Placement subject already has a Combat position.",
                        entity_id=command.payload.creature_id,
                        field="creature_id",
                    ),
                ),
            )

        outcome = resolve_place_combatant(command, combat)
        metadata = self._event_metadata_provider.next_metadata(command.campaign_id)
        event = build_combatant_placed_v1(
            event_id=metadata.event_id,
            timestamp=metadata.timestamp,
            command=command,
            outcome=outcome,
        )

        replacement_combat = apply_combatant_placed_v1(combat, event)
        replacement_snapshot = dataclasses.replace(snapshot, combat=replacement_combat)

        self._state_store.save(replacement_snapshot)

        return ResolutionResult(
            success=True,
            command_id=command.command_id,
            outcome=outcome,
            events=(event,),
            errors=(),
        )
