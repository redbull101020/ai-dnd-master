from dataclasses import dataclass

from dnd_engine.domain.definitions.weapon import WeaponDefinition
from dnd_engine.domain.dice import parse_ndm
from dnd_engine.domain.rules.attack import AttackResult
from dnd_engine.domain.services.dice import DiceEngine
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.damage_type import DamageType
from dnd_engine.domain.value_objects.dice_roll import DiceRoll


@dataclass(frozen=True)
class CharacterWeaponAttackDamageResult:
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


def resolve_character_weapon_attack_damage(
    attack_outcome: AttackResult,
    weapon_item_id: str,
    weapon: WeaponDefinition,
    dice: DiceEngine,
) -> CharacterWeaponAttackDamageResult:
    if not isinstance(attack_outcome, AttackResult):
        raise TypeError("attack_outcome must be an AttackResult")
    if type(weapon_item_id) is not str:
        raise TypeError("weapon_item_id must be a str")
    if not isinstance(weapon, WeaponDefinition):
        raise TypeError("weapon must be a WeaponDefinition")
    if not attack_outcome.hit:
        raise ValueError("attack_outcome must be a hit")

    count, sides = parse_ndm(weapon.damage_dice)
    expression = (
        f"{2 * count}d{sides}" if attack_outcome.critical_hit else weapon.damage_dice
    )
    roll = dice.roll(expression)
    if not isinstance(roll, DiceRoll):
        raise TypeError("dice.roll must return a DiceRoll")
    if roll.expression != expression:
        raise ValueError(
            "dice.roll response expression must match requested expression"
        )

    return CharacterWeaponAttackDamageResult(
        target_id=attack_outcome.target_id,
        weapon_item_id=weapon_item_id,
        weapon_definition_id=weapon.id,
        roll=roll,
        ability=attack_outcome.ability,
        ability_modifier=attack_outcome.ability_modifier,
        damage_type=weapon.damage_type,
        critical_hit=attack_outcome.critical_hit,
        amount=max(0, roll.total + attack_outcome.ability_modifier),
    )
