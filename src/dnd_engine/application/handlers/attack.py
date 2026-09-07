from dnd_engine.application.services.event_metadata import EventMetadataProvider
from dnd_engine.application.services.state_snapshot import (
    replace_creature_in_snapshot,
)
from dnd_engine.domain.commands.attack import AttackCommand
from dnd_engine.domain.definitions.item import ItemDefinition
from dnd_engine.domain.definitions.monster import MonsterDefinition
from dnd_engine.domain.definitions.weapon import WeaponDefinition
from dnd_engine.domain.errors import EngineError, ErrorCode
from dnd_engine.domain.events.attack import build_attack_resolved_v1
from dnd_engine.domain.events.character_weapon_attack import (
    build_character_weapon_attack_resolved_v1,
)
from dnd_engine.domain.events.character_weapon_attack_damage import (
    build_character_weapon_attack_damage_resolved_v1,
)
from dnd_engine.domain.events.damage import (
    apply_damage_applied_v1,
    build_damage_applied_from_attack_v1,
)
from dnd_engine.domain.events.monster_attack import (
    build_monster_attack_resolved_v1,
)
from dnd_engine.domain.events.monster_attack_damage import (
    build_monster_attack_damage_resolved_v1,
)
from dnd_engine.domain.resolution import ResolutionResult
from dnd_engine.domain.rules.armor_class import unarmored_character_armor_class
from dnd_engine.domain.rules.attack import (
    AttackResult,
    resolve_character_unarmed_attack,
    resolve_character_weapon_attack,
)
from dnd_engine.domain.rules.character_weapon_attack_damage import (
    resolve_character_weapon_attack_damage,
)
from dnd_engine.domain.rules.condition_roll_mode import (
    attack_roll_mode_from_conditions,
)
from dnd_engine.domain.rules.damage import resolve_damage_amount
from dnd_engine.domain.rules.monster_attack import (
    MonsterAttackResult,
    resolve_monster_attack,
)
from dnd_engine.domain.rules.monster_attack_damage import (
    resolve_monster_attack_damage,
)
from dnd_engine.domain.rules.proficiency import character_proficiency_bonus
from dnd_engine.domain.rules.reach import (
    DND_5E_FIRST_CONSUMER_MELEE_REACH_FEET,
    is_within_melee_reach,
)
from dnd_engine.domain.services.definitions import (
    DefinitionNotFoundError,
    DefinitionSource,
    DefinitionTypeMismatchError,
)
from dnd_engine.domain.services.dice import DiceEngine
from dnd_engine.domain.services.state_store import StateStore
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.state.snapshot import StateSnapshot
from dnd_engine.domain.value_objects.ability import Ability


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

    def handle(
        self, command: AttackCommand
    ) -> ResolutionResult[AttackResult | MonsterAttackResult]:
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

        if (
            snapshot.combat is not None
            and command.actor_id != snapshot.combat.active_creature_id
        ):
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.ACTION_NOT_AVAILABLE,
                        message="Attack actor is not the active combatant.",
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

        if actor_character is not None:
            return self._handle_character_attack(
                command, snapshot, actor_creature, actor_character
            )

        return self._handle_monster_attack(command, snapshot, actor_creature)

    def _handle_character_attack(
        self,
        command: AttackCommand,
        snapshot: StateSnapshot,
        actor_creature: CreatureState,
        actor_character: CharacterState,
    ) -> ResolutionResult[AttackResult | MonsterAttackResult]:
        if actor_creature.current_hp == 0:
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.ACTION_NOT_AVAILABLE,
                        message="Attack actor has 0 current HP.",
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

        if command.payload.weapon_item_id is None:
            if command.payload.weapon_ability is not None:
                return ResolutionResult(
                    success=False,
                    command_id=command.command_id,
                    outcome=None,
                    events=(),
                    errors=(
                        EngineError(
                            code=ErrorCode.INVALID_COMMAND,
                            message=(
                                "weapon_ability requires a selected "
                                "weapon_item_id."
                            ),
                            entity_id=command.actor_id,
                            field="weapon_ability",
                        ),
                    ),
                )

            roll_mode = attack_roll_mode_from_conditions(actor_creature.conditions)
            outcome = resolve_character_unarmed_attack(
                command,
                actor_creature,
                actor_character,
                self._dice,
                target_armor_class=target_armor_class,
                roll_mode=roll_mode,
            )
            metadata = self._event_metadata_provider.next_metadata(
                command.campaign_id
            )
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

        return self._handle_character_weapon_attack(
            command, snapshot, actor_creature, actor_character, target, target_armor_class
        )

    def _handle_character_weapon_attack(
        self,
        command: AttackCommand,
        snapshot: StateSnapshot,
        actor_creature: CreatureState,
        actor_character: CharacterState,
        target: CreatureState,
        target_armor_class: int,
    ) -> ResolutionResult[AttackResult | MonsterAttackResult]:
        weapon_item_id = command.payload.weapon_item_id
        assert weapon_item_id is not None

        inventory = next(
            (
                candidate
                for candidate in snapshot.inventories
                if candidate.owner_id == command.actor_id
            ),
            None,
        )
        if inventory is None:
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.ACTION_NOT_AVAILABLE,
                        message="Attack actor has no Inventory.",
                        entity_id=command.actor_id,
                        field="weapon_item_id",
                    ),
                ),
            )

        selected_item = next(
            (item for item in inventory.items if item.id == weapon_item_id),
            None,
        )
        if selected_item is None:
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.ACTION_NOT_AVAILABLE,
                        message=(
                            "Selected weapon Item was not found in actor "
                            "Inventory."
                        ),
                        entity_id=weapon_item_id,
                        field="weapon_item_id",
                    ),
                ),
            )

        equipment = next(
            (
                candidate
                for candidate in snapshot.equipment
                if candidate.owner_id == command.actor_id
            ),
            None,
        )
        if equipment is None:
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.ACTION_NOT_AVAILABLE,
                        message="Attack actor has no Equipment.",
                        entity_id=command.actor_id,
                        field="weapon_item_id",
                    ),
                ),
            )

        if equipment.equipped_weapon_id != weapon_item_id:
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.ACTION_NOT_AVAILABLE,
                        message="Selected weapon Item is not the equipped weapon.",
                        entity_id=weapon_item_id,
                        field="weapon_item_id",
                    ),
                ),
            )

        try:
            item_definition = self._definition_source.get_definition(
                ruleset_id=snapshot.campaign.ruleset_id,
                ruleset_version=snapshot.campaign.ruleset_version,
                definition_id=selected_item.definition_id,
                expected_type=ItemDefinition,
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
                        message="Selected weapon Item Definition was not found.",
                        entity_id=selected_item.definition_id,
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
                        message=(
                            "Selected weapon Item Definition is not an "
                            "ItemDefinition."
                        ),
                        entity_id=selected_item.id,
                        field="definition_id",
                    ),
                ),
            )

        if not isinstance(item_definition, WeaponDefinition):
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.ACTION_NOT_AVAILABLE,
                        message="Selected Item Definition is not a WeaponDefinition.",
                        entity_id=selected_item.id,
                        field="weapon_item_id",
                    ),
                ),
            )

        weapon_definition = item_definition

        if weapon_definition.id != "dagger":
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.ACTION_NOT_AVAILABLE,
                        message=(
                            "Character weapon Attack currently supports only "
                            "the Dagger."
                        ),
                        entity_id=selected_item.id,
                        field="weapon_item_id",
                    ),
                ),
            )

        proficiency_bonus = (
            character_proficiency_bonus(actor_character.total_level)
            if weapon_definition.id in actor_character.weapon_proficiencies
            else 0
        )

        weapon_ability = command.payload.weapon_ability
        if weapon_ability not in (Ability.STRENGTH, Ability.DEXTERITY):
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.INVALID_COMMAND,
                        message=(
                            "Character weapon Attack requires an explicit "
                            "Strength or Dexterity Ability choice."
                        ),
                        entity_id=command.actor_id,
                        field="weapon_ability",
                    ),
                ),
            )

        combat = snapshot.combat
        if combat is None:
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.ACTION_NOT_AVAILABLE,
                        message=(
                            "Character weapon melee Attack requires an "
                            "active CombatState."
                        ),
                        entity_id=command.actor_id,
                    ),
                ),
            )

        actor_position = next(
            (
                position
                for position in combat.positions
                if position.creature_id == command.actor_id
            ),
            None,
        )
        if actor_position is None:
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.ACTION_NOT_AVAILABLE,
                        message="Attack actor has no CombatPosition.",
                        entity_id=command.actor_id,
                        field="position",
                    ),
                ),
            )

        target_id = command.payload.target_id
        if target_id not in combat.order:
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.INVALID_TARGET,
                        message="Attack target is not part of the current Combat.",
                        entity_id=target_id,
                        field="target_id",
                    ),
                ),
            )

        target_position = next(
            (
                position
                for position in combat.positions
                if position.creature_id == target_id
            ),
            None,
        )
        if target_position is None:
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.INVALID_TARGET,
                        message="Attack target has no CombatPosition.",
                        entity_id=target_id,
                        field="position",
                    ),
                ),
            )

        if not is_within_melee_reach(
            actor_position,
            target_position,
            effective_reach=DND_5E_FIRST_CONSUMER_MELEE_REACH_FEET,
        ):
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.OUT_OF_RANGE,
                        message="Attack target is out of melee reach.",
                        entity_id=target_id,
                    ),
                ),
            )

        roll_mode = attack_roll_mode_from_conditions(actor_creature.conditions)
        outcome = resolve_character_weapon_attack(
            command,
            actor_creature,
            actor_character,
            self._dice,
            ability=weapon_ability,
            proficiency_bonus=proficiency_bonus,
            target_armor_class=target_armor_class,
            roll_mode=roll_mode,
        )

        damage_outcome = None
        damage_result = None
        if outcome.hit:
            damage_outcome = resolve_character_weapon_attack_damage(
                outcome,
                weapon_item_id,
                weapon_definition,
                self._dice,
            )
            if damage_outcome.amount > 0:
                damage_result = resolve_damage_amount(
                    target,
                    amount=damage_outcome.amount,
                )

        attack_metadata = self._event_metadata_provider.next_metadata(
            command.campaign_id
        )
        attack_event = build_character_weapon_attack_resolved_v1(
            event_id=attack_metadata.event_id,
            timestamp=attack_metadata.timestamp,
            command=command,
            outcome=outcome,
            weapon_item_id=weapon_item_id,
            weapon_definition_id=weapon_definition.id,
        )

        if damage_outcome is None:
            return ResolutionResult(
                success=True,
                command_id=command.command_id,
                outcome=outcome,
                events=(attack_event,),
                errors=(),
            )

        damage_metadata = self._event_metadata_provider.next_metadata(
            command.campaign_id
        )
        damage_event = build_character_weapon_attack_damage_resolved_v1(
            event_id=damage_metadata.event_id,
            timestamp=damage_metadata.timestamp,
            command=command,
            outcome=damage_outcome,
            caused_by=attack_event.event_id,
        )

        if damage_result is None:
            return ResolutionResult(
                success=True,
                command_id=command.command_id,
                outcome=outcome,
                events=(attack_event, damage_event),
                errors=(),
            )

        application_metadata = self._event_metadata_provider.next_metadata(
            command.campaign_id
        )
        application_event = build_damage_applied_from_attack_v1(
            event_id=application_metadata.event_id,
            timestamp=application_metadata.timestamp,
            command=command,
            outcome=damage_result,
            caused_by=damage_event.event_id,
        )

        replacement_target = apply_damage_applied_v1(target, application_event)
        replacement_snapshot = replace_creature_in_snapshot(
            snapshot,
            replacement_target,
        )
        self._state_store.save(replacement_snapshot)

        return ResolutionResult(
            success=True,
            command_id=command.command_id,
            outcome=outcome,
            events=(attack_event, damage_event, application_event),
            errors=(),
        )

    def _handle_monster_attack(
        self,
        command: AttackCommand,
        snapshot: StateSnapshot,
        actor_creature: CreatureState,
    ) -> ResolutionResult[AttackResult | MonsterAttackResult]:
        try:
            monster_definition = self._definition_source.get_definition(
                ruleset_id=snapshot.campaign.ruleset_id,
                ruleset_version=snapshot.campaign.ruleset_version,
                definition_id=actor_creature.definition_id,
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
                        message="Attack actor Definition was not found.",
                        entity_id=actor_creature.definition_id,
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
                        message="Attack actor Definition is not a MonsterDefinition.",
                        entity_id=actor_creature.id,
                        field="definition_id",
                    ),
                ),
            )

        if actor_creature.current_hp == 0:
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.ACTION_NOT_AVAILABLE,
                        message="Attack actor has 0 current HP.",
                        entity_id=command.actor_id,
                    ),
                ),
            )

        if (
            command.payload.weapon_item_id is not None
            or command.payload.weapon_ability is not None
        ):
            invalid_field = (
                "weapon_item_id"
                if command.payload.weapon_item_id is not None
                else "weapon_ability"
            )
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.INVALID_COMMAND,
                        message=(
                            "Character weapon fields are not valid for a "
                            "Monster Attack actor."
                        ),
                        entity_id=command.actor_id,
                        field=invalid_field,
                    ),
                ),
            )

        if len(monster_definition.attacks) != 1:
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.ACTION_NOT_AVAILABLE,
                        message=(
                            "Attack actor Definition does not have exactly one "
                            "supported Monster attack."
                        ),
                        entity_id=actor_creature.id,
                        field="attacks",
                    ),
                ),
            )

        action = monster_definition.attacks[0]

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

        target_character = next(
            (
                candidate
                for candidate in snapshot.characters
                if candidate.id == target.id
            ),
            None,
        )

        if target_character is None:
            return ResolutionResult(
                success=False,
                command_id=command.command_id,
                outcome=None,
                events=(),
                errors=(
                    EngineError(
                        code=ErrorCode.INVALID_TARGET,
                        message="Attack target has no CharacterState.",
                        entity_id=target.id,
                        field="target_id",
                    ),
                ),
            )

        target_armor_class = unarmored_character_armor_class(target)
        roll_mode = attack_roll_mode_from_conditions(actor_creature.conditions)
        outcome = resolve_monster_attack(
            command,
            actor_creature,
            action,
            self._dice,
            target_armor_class=target_armor_class,
            roll_mode=roll_mode,
        )

        damage_outcome = None
        damage_result = None
        if outcome.hit:
            damage_outcome = resolve_monster_attack_damage(
                outcome,
                action,
                self._dice,
            )
            if damage_outcome.amount > 0:
                damage_result = resolve_damage_amount(
                    target,
                    amount=damage_outcome.amount,
                )

        attack_metadata = self._event_metadata_provider.next_metadata(
            command.campaign_id
        )
        attack_event = build_monster_attack_resolved_v1(
            event_id=attack_metadata.event_id,
            timestamp=attack_metadata.timestamp,
            command=command,
            outcome=outcome,
        )

        if damage_outcome is None:
            return ResolutionResult(
                success=True,
                command_id=command.command_id,
                outcome=outcome,
                events=(attack_event,),
                errors=(),
            )

        damage_metadata = self._event_metadata_provider.next_metadata(
            command.campaign_id
        )
        damage_event = build_monster_attack_damage_resolved_v1(
            event_id=damage_metadata.event_id,
            timestamp=damage_metadata.timestamp,
            command=command,
            outcome=damage_outcome,
            caused_by=attack_event.event_id,
        )

        if damage_result is None:
            return ResolutionResult(
                success=True,
                command_id=command.command_id,
                outcome=outcome,
                events=(attack_event, damage_event),
                errors=(),
            )

        application_metadata = self._event_metadata_provider.next_metadata(
            command.campaign_id
        )
        application_event = build_damage_applied_from_attack_v1(
            event_id=application_metadata.event_id,
            timestamp=application_metadata.timestamp,
            command=command,
            outcome=damage_result,
            caused_by=damage_event.event_id,
        )

        replacement_target = apply_damage_applied_v1(target, application_event)
        replacement_snapshot = replace_creature_in_snapshot(
            snapshot,
            replacement_target,
        )
        self._state_store.save(replacement_snapshot)

        return ResolutionResult(
            success=True,
            command_id=command.command_id,
            outcome=outcome,
            events=(attack_event, damage_event, application_event),
            errors=(),
        )
