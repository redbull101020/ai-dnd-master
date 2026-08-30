import dataclasses

from dnd_engine.application.services.event_metadata import EventMetadataProvider
from dnd_engine.domain.commands.start_combat import StartCombatCommand
from dnd_engine.domain.errors import EngineError, ErrorCode
from dnd_engine.domain.events.start_combat import (
    apply_combat_started_v1,
    build_combat_started_v1,
)
from dnd_engine.domain.resolution import ResolutionResult
from dnd_engine.domain.rules.condition_roll_mode import (
    ability_check_roll_mode_from_conditions,
)
from dnd_engine.domain.rules.start_combat import StartCombatResult, resolve_start_combat
from dnd_engine.domain.services.dice import DiceEngine
from dnd_engine.domain.services.state_store import StateStore
from dnd_engine.domain.state.creature import CreatureState


class StartCombatHandler:
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
        self, command: StartCombatCommand
    ) -> ResolutionResult[StartCombatResult]:
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
                        message="Start Combat actor was not found.",
                        entity_id=command.actor_id,
                    ),
                ),
            )

        if snapshot.combat is not None:
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.RULE_VIOLATION,
                        message="Combat is already in progress.",
                        entity_id=snapshot.combat.id,
                    ),
                ),
            )

        creatures_by_id = {creature.id: creature for creature in snapshot.creatures}
        participants: list[CreatureState] = []
        for participant_id in command.payload.participant_ids:
            creature = creatures_by_id.get(participant_id)
            if creature is None:
                return ResolutionResult(
                    success=False,
                    command_id=command.command_id,
                    outcome=None,
                    events=(),
                    errors=(
                        EngineError(
                            code=ErrorCode.ENTITY_NOT_FOUND,
                            message="Combat participant was not found.",
                            entity_id=participant_id,
                            field="participant_ids",
                        ),
                    ),
                )
            participants.append(creature)

        roll_modes = tuple(
            ability_check_roll_mode_from_conditions(participant.conditions)
            for participant in participants
        )
        outcome = resolve_start_combat(
            command, tuple(participants), self._dice, roll_modes=roll_modes
        )
        metadata = self._event_metadata_provider.next_metadata(command.campaign_id)
        event = build_combat_started_v1(
            event_id=metadata.event_id,
            timestamp=metadata.timestamp,
            command=command,
            outcome=outcome,
        )

        combat = apply_combat_started_v1(event)
        replacement_snapshot = dataclasses.replace(snapshot, combat=combat)

        self._state_store.save(replacement_snapshot)

        return ResolutionResult(
            success=True,
            command_id=command.command_id,
            outcome=outcome,
            events=(event,),
            errors=(),
        )
