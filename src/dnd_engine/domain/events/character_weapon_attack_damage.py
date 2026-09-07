from dataclasses import dataclass
from datetime import datetime

from dnd_engine.domain.commands.attack import AttackCommand
from dnd_engine.domain.events.game_event import GameEvent
from dnd_engine.domain.rules.character_weapon_attack_damage import (
    CharacterWeaponAttackDamageResult,
)
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.damage_type import DamageType
from dnd_engine.domain.value_objects.dice_roll import DiceRoll


@dataclass(frozen=True)
class CharacterWeaponAttackDamageResolvedPayloadV1:
    target_id: str
    weapon_item_id: str
    weapon_definition_id: str
    roll: DiceRoll
    ability: Ability
    ability_modifier: int
    damage_type: DamageType
    critical_hit: bool
    amount: int

    def __post_init__(self) -> None:
        if type(self.target_id) is not str:
            raise TypeError("target_id must be a str")
        if type(self.weapon_item_id) is not str:
            raise TypeError("weapon_item_id must be a str")
        if type(self.weapon_definition_id) is not str:
            raise TypeError("weapon_definition_id must be a str")
        if not isinstance(self.roll, DiceRoll):
            raise TypeError("roll must be a DiceRoll")
        if not isinstance(self.ability, Ability):
            raise TypeError("ability must be an Ability")
        if type(self.ability_modifier) is not int:
            raise TypeError("ability_modifier must be an int")
        if not isinstance(self.damage_type, DamageType):
            raise TypeError("damage_type must be a DamageType")
        if type(self.critical_hit) is not bool:
            raise TypeError("critical_hit must be a bool")
        if type(self.amount) is not int:
            raise TypeError("amount must be an int")
        if self.amount != max(0, self.roll.total + self.ability_modifier):
            raise ValueError(
                "amount must equal max(0, roll.total plus ability_modifier)"
            )


def build_character_weapon_attack_damage_resolved_v1(
    *,
    event_id: str,
    timestamp: datetime,
    command: AttackCommand,
    outcome: CharacterWeaponAttackDamageResult,
    caused_by: str,
) -> GameEvent:
    if not isinstance(command, AttackCommand):
        raise TypeError("command must be an AttackCommand")
    if not isinstance(outcome, CharacterWeaponAttackDamageResult):
        raise TypeError("outcome must be a CharacterWeaponAttackDamageResult")
    if type(caused_by) is not str:
        raise TypeError("caused_by must be a str")
    if outcome.target_id != command.payload.target_id:
        raise ValueError("outcome target_id must match command payload target_id")
    if command.payload.weapon_item_id is None:
        raise ValueError(
            "command payload weapon_item_id must not be None for a "
            "Character weapon Damage Event"
        )
    if command.payload.weapon_item_id != outcome.weapon_item_id:
        raise ValueError(
            "outcome weapon_item_id must match command payload weapon_item_id"
        )

    payload = CharacterWeaponAttackDamageResolvedPayloadV1(
        target_id=outcome.target_id,
        weapon_item_id=outcome.weapon_item_id,
        weapon_definition_id=outcome.weapon_definition_id,
        roll=outcome.roll,
        ability=outcome.ability,
        ability_modifier=outcome.ability_modifier,
        damage_type=outcome.damage_type,
        critical_hit=outcome.critical_hit,
        amount=outcome.amount,
    )

    return GameEvent(
        event_id=event_id,
        command_id=command.command_id,
        type="CharacterWeaponAttackDamageResolved",
        version=1,
        campaign_id=command.campaign_id,
        timestamp=timestamp,
        actor_id=command.actor_id,
        caused_by=caused_by,
        payload={
            "targetId": payload.target_id,
            "weaponItemId": payload.weapon_item_id,
            "weaponDefinitionId": payload.weapon_definition_id,
            "roll": {
                "expression": payload.roll.expression,
                "rolls": payload.roll.rolls,
                "total": payload.roll.total,
            },
            "ability": payload.ability.value,
            "abilityModifier": payload.ability_modifier,
            "damageType": payload.damage_type.value,
            "criticalHit": payload.critical_hit,
            "amount": payload.amount,
        },
    )
