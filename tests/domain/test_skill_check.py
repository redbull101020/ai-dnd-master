from copy import deepcopy
from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.commands.skill_check import (
    SkillCheckCommand,
    SkillCheckPayload,
)
from dnd_engine.domain.rules.skill_check import (
    SkillCheckResult,
    resolve_character_skill_check,
)
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.domain.value_objects.d20 import D20Roll, RollMode
from dnd_engine.domain.value_objects.dice_roll import DiceRoll
from dnd_engine.domain.value_objects.skill import Skill


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
    dexterity: int = 12,
    charisma: int = 8,
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
            charisma=charisma,
        ),
        current_hp=20,
        max_hp=20,
    )


def make_character(
    *,
    character_id: str = "character_001",
    level: int = 5,
    proficiencies: frozenset[Skill] = frozenset({Skill.INTIMIDATION}),
) -> CharacterState:
    return CharacterState(
        id=character_id,
        total_level=level,
        saving_throw_proficiencies=frozenset(),
        skill_proficiencies=proficiencies,
    )


def make_command(
    *,
    actor_id: str = "character_001",
    skill: Skill = Skill.INTIMIDATION,
    ability: Ability = Ability.STRENGTH,
    dc: int = 15,
) -> SkillCheckCommand:
    return SkillCheckCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id=actor_id,
        payload=SkillCheckPayload(skill=skill, ability=ability, dc=dc),
    )


def test_proficient_skill_check_composes_all_authoritative_inputs() -> None:
    dice = ScriptedDiceEngine(9)

    result = resolve_character_skill_check(
        make_command(),
        make_creature(),
        make_character(),
        dice,
    )

    assert tuple(field.name for field in fields(result)) == (
        "skill",
        "ability",
        "dc",
        "roll",
        "ability_modifier",
        "proficiency_bonus",
        "total",
        "succeeded",
    )
    assert result == SkillCheckResult(
        skill=Skill.INTIMIDATION,
        ability=Ability.STRENGTH,
        dc=15,
        roll=D20Roll(mode=RollMode.NORMAL, rolls=(9,), selected=9),
        ability_modifier=3,
        proficiency_bonus=3,
        total=15,
        succeeded=True,
    )
    assert dice.calls == ["1d20"]


def test_non_proficient_skill_uses_zero_proficiency_bonus() -> None:
    result = resolve_character_skill_check(
        make_command(skill=Skill.ATHLETICS, dc=13),
        make_creature(),
        make_character(proficiencies=frozenset({Skill.INTIMIDATION})),
        ScriptedDiceEngine(10),
    )

    assert result.proficiency_bonus == 0
    assert result.total == 13
    assert result.succeeded is True


def test_alternative_ability_uses_explicit_ability_and_skill_membership() -> None:
    result = resolve_character_skill_check(
        make_command(skill=Skill.INTIMIDATION, ability=Ability.STRENGTH, dc=15),
        make_creature(strength=16, charisma=8),
        make_character(proficiencies=frozenset({Skill.INTIMIDATION})),
        ScriptedDiceEngine(9),
    )

    assert result.skill is Skill.INTIMIDATION
    assert result.ability is Ability.STRENGTH
    assert result.ability_modifier == 3
    assert result.proficiency_bonus == 3
    assert result.total == 15


@pytest.mark.parametrize(
    ("mode", "raw_rolls", "selected"),
    [
        (RollMode.NORMAL, (7,), 7),
        (RollMode.ADVANTAGE, (7, 16), 16),
        (RollMode.DISADVANTAGE, (7, 16), 7),
    ],
)
def test_resolver_uses_shared_d20_selection(
    mode: RollMode,
    raw_rolls: tuple[int, ...],
    selected: int,
) -> None:
    dice = ScriptedDiceEngine(*raw_rolls)

    result = resolve_character_skill_check(
        make_command(),
        make_creature(),
        make_character(),
        dice,
        roll_mode=mode,
    )

    assert result.roll == D20Roll(mode=mode, rolls=raw_rolls, selected=selected)
    assert result.total == selected + 3 + 3
    assert dice.calls == ["1d20"] * len(raw_rolls)


def test_natural_one_can_succeed() -> None:
    result = resolve_character_skill_check(
        make_command(dc=17),
        make_creature(strength=30),
        make_character(level=17),
        ScriptedDiceEngine(1),
    )

    assert result.roll.selected == 1
    assert result.total == 17
    assert result.succeeded is True


def test_natural_twenty_can_fail() -> None:
    result = resolve_character_skill_check(
        make_command(dc=16),
        make_creature(strength=1),
        make_character(proficiencies=frozenset()),
        ScriptedDiceEngine(20),
    )

    assert result.roll.selected == 20
    assert result.total == 15
    assert result.succeeded is False


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
        resolve_character_skill_check(
            make_command(),
            make_creature(creature_id=creature_id),
            make_character(character_id=character_id),
            dice,
        )

    assert dice.calls == []


@pytest.mark.parametrize(
    ("command", "creature", "character", "match"),
    [
        (object(), make_creature(), make_character(), "SkillCheckCommand"),
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
        resolve_character_skill_check(
            command,  # type: ignore[arg-type]
            creature,  # type: ignore[arg-type]
            character,  # type: ignore[arg-type]
            dice,
        )

    assert dice.calls == []


def test_resolver_delegates_roll_mode_validation_to_d20_rule() -> None:
    dice = ScriptedDiceEngine(10)

    with pytest.raises(TypeError, match="RollMode"):
        resolve_character_skill_check(
            make_command(),
            make_creature(),
            make_character(),
            dice,
            roll_mode="normal",  # type: ignore[arg-type]
        )

    assert dice.calls == []


def test_resolver_does_not_mutate_loaded_projections() -> None:
    creature = make_creature()
    character = make_character()
    creature_before = deepcopy(creature)
    character_before = deepcopy(character)

    resolve_character_skill_check(
        make_command(),
        creature,
        character,
        ScriptedDiceEngine(10),
    )

    assert creature == creature_before
    assert character == character_before


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("skill", "intimidation"),
        ("ability", "strength"),
        ("dc", True),
        ("roll", object()),
        ("ability_modifier", True),
        ("proficiency_bonus", True),
        ("total", True),
        ("succeeded", 1),
    ],
)
def test_result_rejects_wrong_runtime_types(
    field_name: str,
    invalid_value: object,
) -> None:
    values: dict[str, object] = {
        "skill": Skill.INTIMIDATION,
        "ability": Ability.STRENGTH,
        "dc": 15,
        "roll": D20Roll(mode=RollMode.NORMAL, rolls=(9,), selected=9),
        "ability_modifier": 3,
        "proficiency_bonus": 3,
        "total": 15,
        "succeeded": True,
    }
    values[field_name] = invalid_value

    with pytest.raises(TypeError):
        SkillCheckResult(**values)  # type: ignore[arg-type]


def test_result_is_immutable_and_enforces_semantic_invariants() -> None:
    result = SkillCheckResult(
        skill=Skill.INTIMIDATION,
        ability=Ability.STRENGTH,
        dc=15,
        roll=D20Roll(mode=RollMode.NORMAL, rolls=(9,), selected=9),
        ability_modifier=3,
        proficiency_bonus=3,
        total=15,
        succeeded=True,
    )

    with pytest.raises(FrozenInstanceError):
        result.total = 14  # type: ignore[misc]
    with pytest.raises(ValueError, match="negative"):
        SkillCheckResult(
            skill=result.skill,
            ability=result.ability,
            dc=15,
            roll=result.roll,
            ability_modifier=3,
            proficiency_bonus=-1,
            total=11,
            succeeded=False,
        )
    with pytest.raises(ValueError, match="total"):
        SkillCheckResult(
            skill=result.skill,
            ability=result.ability,
            dc=15,
            roll=result.roll,
            ability_modifier=3,
            proficiency_bonus=3,
            total=14,
            succeeded=False,
        )
    with pytest.raises(ValueError, match="succeeded"):
        SkillCheckResult(
            skill=result.skill,
            ability=result.ability,
            dc=15,
            roll=result.roll,
            ability_modifier=3,
            proficiency_bonus=3,
            total=15,
            succeeded=False,
        )
