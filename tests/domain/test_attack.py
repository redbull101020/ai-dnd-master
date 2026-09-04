from copy import deepcopy
from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.commands.attack import AttackCommand, AttackPayload
from dnd_engine.domain.rules.attack import (
    AttackResult,
    resolve_character_unarmed_attack,
)
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.domain.value_objects.d20 import D20Roll, RollMode
from dnd_engine.domain.value_objects.dice_roll import DiceRoll


class ScriptedDiceEngine:
    def __init__(self, *raw_rolls: int) -> None:
        self._rolls = iter(raw_rolls)
        self.calls: list[str] = []

    def roll(self, expression: str) -> DiceRoll:
        self.calls.append(expression)
        raw = next(self._rolls)
        return DiceRoll(expression="1d20", rolls=(raw,), total=raw)


def make_creature(
    *,
    creature_id: str = "character_001",
    strength: int = 16,
    dexterity: int = 8,
) -> CreatureState:
    return CreatureState(
        id=creature_id,
        definition_id="fighter",
        ability_scores=AbilityScores(
            strength=strength,
            dexterity=dexterity,
            constitution=14,
            intelligence=10,
            wisdom=10,
            charisma=10,
        ),
        current_hp=20,
        max_hp=20,
    )


def make_character(
    *,
    character_id: str = "character_001",
    level: int = 5,
) -> CharacterState:
    return CharacterState(
        id=character_id,
        total_level=level,
        saving_throw_proficiencies=frozenset(),
        skill_proficiencies=frozenset(),
        weapon_proficiencies=frozenset(),
    )


def make_command(*, actor_id: str = "character_001") -> AttackCommand:
    return AttackCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id=actor_id,
        payload=AttackPayload(target_id="monster_001"),
    )


def resolve_attack(
    raw_roll: int,
    *,
    strength: int = 16,
    level: int = 5,
    target_armor_class: int = 15,
) -> AttackResult:
    return resolve_character_unarmed_attack(
        make_command(),
        make_creature(strength=strength),
        make_character(level=level),
        ScriptedDiceEngine(raw_roll),
        target_armor_class=target_armor_class,
    )


def test_ordinary_hit_composes_exact_attack_result() -> None:
    dice = ScriptedDiceEngine(10)

    result = resolve_character_unarmed_attack(
        make_command(),
        make_creature(),
        make_character(),
        dice,
        target_armor_class=15,
    )

    assert tuple(field.name for field in fields(result)) == (
        "target_id",
        "roll",
        "ability",
        "ability_modifier",
        "proficiency_bonus",
        "total",
        "target_armor_class",
        "hit",
        "critical_hit",
    )
    assert result == AttackResult(
        target_id="monster_001",
        roll=D20Roll(mode=RollMode.NORMAL, rolls=(10,), selected=10),
        ability=Ability.STRENGTH,
        ability_modifier=3,
        proficiency_bonus=3,
        total=16,
        target_armor_class=15,
        hit=True,
        critical_hit=False,
    )
    assert dice.calls == ["1d20"]


def test_ordinary_miss() -> None:
    result = resolve_attack(8, target_armor_class=15)

    assert result.total == 14
    assert result.hit is False
    assert result.critical_hit is False


def test_total_equal_to_armor_class_hits() -> None:
    result = resolve_attack(9, target_armor_class=15)

    assert result.total == result.target_armor_class == 15
    assert result.hit is True


def test_unarmed_attack_uses_strength_not_dexterity() -> None:
    result = resolve_character_unarmed_attack(
        make_command(),
        make_creature(strength=8, dexterity=20),
        make_character(),
        ScriptedDiceEngine(10),
        target_armor_class=100,
    )

    assert result.ability is Ability.STRENGTH
    assert result.ability_modifier == -1
    assert result.total == 10 - 1 + 3


@pytest.mark.parametrize(
    ("strength", "expected_modifier"),
    [(16, 3), (8, -1)],
)
def test_strength_modifier_contributes_to_total(
    strength: int,
    expected_modifier: int,
) -> None:
    result = resolve_attack(10, strength=strength, target_armor_class=100)

    assert result.ability_modifier == expected_modifier
    assert result.total == 10 + expected_modifier + 3


@pytest.mark.parametrize(("level", "expected_bonus"), [(1, 2), (5, 3), (17, 6)])
def test_character_proficiency_always_contributes(
    level: int,
    expected_bonus: int,
) -> None:
    result = resolve_attack(10, level=level, target_armor_class=100)

    assert result.proficiency_bonus == expected_bonus
    assert result.total == 10 + 3 + expected_bonus


def test_natural_one_is_automatic_miss_despite_numeric_total() -> None:
    result = resolve_attack(
        1,
        strength=30,
        level=17,
        target_armor_class=10,
    )

    assert result.total == 17
    assert result.total >= result.target_armor_class
    assert result.hit is False
    assert result.critical_hit is False


def test_natural_twenty_is_automatic_critical_hit_despite_numeric_total() -> None:
    result = resolve_attack(
        20,
        strength=1,
        level=1,
        target_armor_class=100,
    )

    assert result.total == 17
    assert result.total < result.target_armor_class
    assert result.hit is True
    assert result.critical_hit is True


@pytest.mark.parametrize(
    ("mode", "raw_rolls", "selected", "critical_hit"),
    [
        (RollMode.NORMAL, (12,), 12, False),
        (RollMode.ADVANTAGE, (7, 16), 16, False),
        (RollMode.DISADVANTAGE, (7, 16), 7, False),
        (RollMode.ADVANTAGE, (1, 15), 15, False),
        (RollMode.DISADVANTAGE, (20, 5), 5, False),
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

    result = resolve_character_unarmed_attack(
        make_command(),
        make_creature(),
        make_character(),
        dice,
        target_armor_class=10,
        roll_mode=mode,
    )

    assert result.roll == D20Roll(mode=mode, rolls=raw_rolls, selected=selected)
    assert result.total == selected + 3 + 3
    assert result.hit is True
    assert result.critical_hit is critical_hit
    assert dice.calls == ["1d20"] * len(raw_rolls)


@pytest.mark.parametrize(
    ("creature_id", "character_id"),
    [("character_002", "character_001"), ("character_001", "character_002")],
)
def test_resolver_rejects_projection_identity_mismatch(
    creature_id: str,
    character_id: str,
) -> None:
    dice = ScriptedDiceEngine(10)

    with pytest.raises(ValueError, match="actor_id"):
        resolve_character_unarmed_attack(
            make_command(),
            make_creature(creature_id=creature_id),
            make_character(character_id=character_id),
            dice,
            target_armor_class=15,
        )

    assert dice.calls == []


@pytest.mark.parametrize(
    ("command", "creature", "character", "match"),
    [
        (object(), make_creature(), make_character(), "AttackCommand"),
        (make_command(), object(), make_character(), "CreatureState"),
        (make_command(), make_creature(), object(), "CharacterState"),
    ],
)
def test_resolver_rejects_wrong_domain_input_types(
    command: object,
    creature: object,
    character: object,
    match: str,
) -> None:
    dice = ScriptedDiceEngine(10)

    with pytest.raises(TypeError, match=match):
        resolve_character_unarmed_attack(
            command,  # type: ignore[arg-type]
            creature,  # type: ignore[arg-type]
            character,  # type: ignore[arg-type]
            dice,
            target_armor_class=15,
        )

    assert dice.calls == []


@pytest.mark.parametrize("target_armor_class", [True, 15.0, "15", None])
def test_resolver_requires_exact_integer_target_armor_class(
    target_armor_class: object,
) -> None:
    dice = ScriptedDiceEngine(10)

    with pytest.raises(TypeError, match="target_armor_class"):
        resolve_character_unarmed_attack(
            make_command(),
            make_creature(),
            make_character(),
            dice,
            target_armor_class=target_armor_class,  # type: ignore[arg-type]
        )

    assert dice.calls == []


def test_resolver_delegates_roll_mode_validation_to_d20_rule() -> None:
    dice = ScriptedDiceEngine(10)

    with pytest.raises(TypeError, match="RollMode"):
        resolve_character_unarmed_attack(
            make_command(),
            make_creature(),
            make_character(),
            dice,
            target_armor_class=15,
            roll_mode="normal",  # type: ignore[arg-type]
        )

    assert dice.calls == []


def test_resolver_does_not_mutate_state_projections() -> None:
    creature = make_creature()
    character = make_character()
    creature_before = deepcopy(creature)
    character_before = deepcopy(character)

    resolve_character_unarmed_attack(
        make_command(),
        creature,
        character,
        ScriptedDiceEngine(10),
        target_armor_class=15,
    )

    assert creature == creature_before
    assert character == character_before


def canonical_result(**overrides: object) -> AttackResult:
    values: dict[str, object] = {
        "target_id": "monster_001",
        "roll": D20Roll(mode=RollMode.NORMAL, rolls=(10,), selected=10),
        "ability": Ability.STRENGTH,
        "ability_modifier": 3,
        "proficiency_bonus": 3,
        "total": 16,
        "target_armor_class": 15,
        "hit": True,
        "critical_hit": False,
    }
    values.update(overrides)
    return AttackResult(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("target_id", 1),
        ("roll", object()),
        ("ability", "strength"),
        ("ability_modifier", True),
        ("proficiency_bonus", True),
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


def test_result_is_immutable_and_rejects_negative_proficiency() -> None:
    result = canonical_result()

    with pytest.raises(FrozenInstanceError):
        result.total = 15  # type: ignore[misc]
    with pytest.raises(ValueError, match="negative"):
        canonical_result(proficiency_bonus=-1, total=12, hit=False)


def test_result_rejects_inconsistent_total() -> None:
    with pytest.raises(ValueError, match="total"):
        canonical_result(total=15)


@pytest.mark.parametrize(
    ("roll", "total", "target_ac", "hit", "critical_hit", "match"),
    [
        (
            D20Roll(mode=RollMode.NORMAL, rolls=(1,), selected=1),
            7,
            5,
            True,
            False,
            "natural 1",
        ),
        (
            D20Roll(mode=RollMode.NORMAL, rolls=(1,), selected=1),
            7,
            5,
            False,
            True,
            "natural 1",
        ),
        (
            D20Roll(mode=RollMode.NORMAL, rolls=(20,), selected=20),
            26,
            100,
            False,
            True,
            "natural 20",
        ),
        (
            D20Roll(mode=RollMode.NORMAL, rolls=(20,), selected=20),
            26,
            100,
            True,
            False,
            "natural 20",
        ),
        (
            D20Roll(mode=RollMode.NORMAL, rolls=(10,), selected=10),
            16,
            15,
            False,
            False,
            "hit",
        ),
        (
            D20Roll(mode=RollMode.NORMAL, rolls=(10,), selected=10),
            16,
            15,
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
