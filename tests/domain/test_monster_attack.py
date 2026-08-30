from copy import deepcopy
from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.commands.attack import AttackCommand, AttackPayload
from dnd_engine.domain.definitions.monster_attack import MonsterAttackDefinition
from dnd_engine.domain.rules.monster_attack import (
    MonsterAttackResult,
    resolve_monster_attack,
)
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.domain.value_objects.d20 import D20Roll, RollMode
from dnd_engine.domain.value_objects.damage_type import DamageType
from dnd_engine.domain.value_objects.dice_roll import DiceRoll


class ScriptedDiceEngine:
    def __init__(self, *raw_rolls: int) -> None:
        self._rolls = iter(raw_rolls)
        self.calls: list[str] = []

    def roll(self, expression: str) -> DiceRoll:
        self.calls.append(expression)
        raw = next(self._rolls)
        return DiceRoll(expression="1d20", rolls=(raw,), total=raw)


def make_creature(*, creature_id: str = "monster_001") -> CreatureState:
    return CreatureState(
        id=creature_id,
        definition_id="goblin",
        ability_scores=AbilityScores(
            strength=8,
            dexterity=14,
            constitution=10,
            intelligence=10,
            wisdom=8,
            charisma=8,
        ),
        current_hp=7,
        max_hp=7,
    )


def make_action(*, action_id: str = "scimitar", attack_bonus: int = 4) -> MonsterAttackDefinition:
    return MonsterAttackDefinition(
        action_id=action_id,
        name="Scimitar",
        attack_bonus=attack_bonus,
        damage_dice="1d6",
        damage_modifier=2,
        damage_type=DamageType.SLASHING,
    )


def make_command(
    *, actor_id: str = "monster_001", target_id: str = "character_001"
) -> AttackCommand:
    return AttackCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id=actor_id,
        payload=AttackPayload(target_id=target_id),
    )


def resolve(
    raw_roll: int,
    *,
    attack_bonus: int = 4,
    target_armor_class: int = 12,
) -> MonsterAttackResult:
    return resolve_monster_attack(
        make_command(),
        make_creature(),
        make_action(attack_bonus=attack_bonus),
        ScriptedDiceEngine(raw_roll),
        target_armor_class=target_armor_class,
    )


def test_ordinary_hit_composes_exact_monster_attack_result() -> None:
    dice = ScriptedDiceEngine(10)

    result = resolve_monster_attack(
        make_command(),
        make_creature(),
        make_action(),
        dice,
        target_armor_class=12,
    )

    assert tuple(field.name for field in fields(result)) == (
        "target_id",
        "action_id",
        "roll",
        "attack_bonus",
        "total",
        "target_armor_class",
        "hit",
        "critical_hit",
    )
    assert result == MonsterAttackResult(
        target_id="character_001",
        action_id="scimitar",
        roll=D20Roll(mode=RollMode.NORMAL, rolls=(10,), selected=10),
        attack_bonus=4,
        total=14,
        target_armor_class=12,
        hit=True,
        critical_hit=False,
    )
    assert dice.calls == ["1d20"]


def test_ordinary_miss() -> None:
    result = resolve(8, target_armor_class=15)

    assert result.total == 12
    assert result.hit is False
    assert result.critical_hit is False


def test_total_equal_to_armor_class_hits() -> None:
    result = resolve(11, target_armor_class=15)

    assert result.total == result.target_armor_class == 15
    assert result.hit is True


def test_result_never_decomposes_flat_bonus_into_ability_or_proficiency() -> None:
    result = resolve(10)

    field_names = {field.name for field in fields(result)}
    assert "ability" not in field_names
    assert "ability_modifier" not in field_names
    assert "proficiency_bonus" not in field_names


def test_natural_one_is_automatic_miss_despite_numeric_total() -> None:
    result = resolve(1, attack_bonus=20, target_armor_class=10)

    assert result.total == 21
    assert result.total >= result.target_armor_class
    assert result.hit is False
    assert result.critical_hit is False


def test_natural_twenty_is_automatic_critical_hit_despite_numeric_total() -> None:
    result = resolve(20, attack_bonus=-5, target_armor_class=100)

    assert result.total == 15
    assert result.total < result.target_armor_class
    assert result.hit is True
    assert result.critical_hit is True


@pytest.mark.parametrize(
    ("mode", "raw_rolls", "selected", "critical_hit"),
    [
        (RollMode.NORMAL, (12,), 12, False),
        (RollMode.ADVANTAGE, (7, 16), 16, False),
        (RollMode.DISADVANTAGE, (7, 16), 7, False),
        (RollMode.ADVANTAGE, (20, 5), 20, True),
    ],
)
def test_attack_semantics_use_only_selected_d20(
    mode: RollMode,
    raw_rolls: tuple[int, ...],
    selected: int,
    critical_hit: bool,
) -> None:
    dice = ScriptedDiceEngine(*raw_rolls)

    result = resolve_monster_attack(
        make_command(),
        make_creature(),
        make_action(),
        dice,
        target_armor_class=10,
        roll_mode=mode,
    )

    assert result.roll == D20Roll(mode=mode, rolls=raw_rolls, selected=selected)
    assert result.total == selected + 4
    assert result.hit is True
    assert result.critical_hit is critical_hit
    assert dice.calls == ["1d20"] * len(raw_rolls)


def test_resolver_rejects_actor_id_mismatch() -> None:
    dice = ScriptedDiceEngine(10)

    with pytest.raises(ValueError, match="actor_id"):
        resolve_monster_attack(
            make_command(actor_id="monster_002"),
            make_creature(creature_id="monster_001"),
            make_action(),
            dice,
            target_armor_class=12,
        )

    assert dice.calls == []


@pytest.mark.parametrize(
    ("command", "creature", "action", "match"),
    [
        (object(), make_creature(), make_action(), "AttackCommand"),
        (make_command(), object(), make_action(), "CreatureState"),
        (make_command(), make_creature(), object(), "MonsterAttackDefinition"),
    ],
)
def test_resolver_rejects_wrong_domain_input_types(
    command: object,
    creature: object,
    action: object,
    match: str,
) -> None:
    dice = ScriptedDiceEngine(10)

    with pytest.raises(TypeError, match=match):
        resolve_monster_attack(
            command,  # type: ignore[arg-type]
            creature,  # type: ignore[arg-type]
            action,  # type: ignore[arg-type]
            dice,
            target_armor_class=12,
        )

    assert dice.calls == []


@pytest.mark.parametrize("target_armor_class", [True, 12.0, "12", None])
def test_resolver_requires_exact_integer_target_armor_class(
    target_armor_class: object,
) -> None:
    dice = ScriptedDiceEngine(10)

    with pytest.raises(TypeError, match="target_armor_class"):
        resolve_monster_attack(
            make_command(),
            make_creature(),
            make_action(),
            dice,
            target_armor_class=target_armor_class,  # type: ignore[arg-type]
        )

    assert dice.calls == []


def test_resolver_does_not_mutate_state_or_definition() -> None:
    creature = make_creature()
    action = make_action()
    creature_before = deepcopy(creature)
    action_before = deepcopy(action)

    resolve_monster_attack(
        make_command(),
        creature,
        action,
        ScriptedDiceEngine(10),
        target_armor_class=12,
    )

    assert creature == creature_before
    assert action == action_before


def canonical_result(**overrides: object) -> MonsterAttackResult:
    values: dict[str, object] = {
        "target_id": "character_001",
        "action_id": "scimitar",
        "roll": D20Roll(mode=RollMode.NORMAL, rolls=(10,), selected=10),
        "attack_bonus": 4,
        "total": 14,
        "target_armor_class": 12,
        "hit": True,
        "critical_hit": False,
    }
    values.update(overrides)
    return MonsterAttackResult(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("target_id", 1),
        ("action_id", 1),
        ("roll", object()),
        ("attack_bonus", True),
        ("total", True),
        ("target_armor_class", True),
        ("hit", 1),
        ("critical_hit", 0),
    ],
)
def test_result_rejects_wrong_runtime_types(
    field_name: str,
    invalid_value: object,
) -> None:
    with pytest.raises(TypeError):
        canonical_result(**{field_name: invalid_value})


def test_result_is_immutable() -> None:
    result = canonical_result()

    with pytest.raises(FrozenInstanceError):
        result.total = 15  # type: ignore[misc]


def test_result_rejects_inconsistent_total() -> None:
    with pytest.raises(ValueError, match="total"):
        canonical_result(total=15)


@pytest.mark.parametrize(
    ("roll", "total", "target_ac", "hit", "critical_hit", "match"),
    [
        (
            D20Roll(mode=RollMode.NORMAL, rolls=(1,), selected=1),
            5,
            5,
            True,
            False,
            "natural 1",
        ),
        (
            D20Roll(mode=RollMode.NORMAL, rolls=(1,), selected=1),
            5,
            5,
            False,
            True,
            "natural 1",
        ),
        (
            D20Roll(mode=RollMode.NORMAL, rolls=(20,), selected=20),
            24,
            100,
            False,
            True,
            "natural 20",
        ),
        (
            D20Roll(mode=RollMode.NORMAL, rolls=(20,), selected=20),
            24,
            100,
            True,
            False,
            "natural 20",
        ),
        (
            D20Roll(mode=RollMode.NORMAL, rolls=(10,), selected=10),
            14,
            12,
            False,
            False,
            "hit",
        ),
        (
            D20Roll(mode=RollMode.NORMAL, rolls=(10,), selected=10),
            14,
            12,
            True,
            True,
            "natural 20",
        ),
    ],
)
def test_result_enforces_hit_and_critical_invariants(
    roll: D20Roll,
    total: int,
    target_ac: int,
    hit: bool,
    critical_hit: bool,
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        canonical_result(
            roll=roll,
            total=total,
            target_armor_class=target_ac,
            hit=hit,
            critical_hit=critical_hit,
        )
