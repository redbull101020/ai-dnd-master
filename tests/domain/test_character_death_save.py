from dataclasses import FrozenInstanceError

import pytest

from dnd_engine.domain.rules.character_death_save import (
    CharacterDeathSaveFailureResult,
    CharacterDeathSaveResult,
    resolve_character_death_save,
    resolve_character_death_save_failure,
)
from dnd_engine.domain.rules.damage import DamageResult
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.value_objects.dice_roll import DiceRoll
from dnd_engine.domain.value_objects.d20 import D20Roll, RollMode


class ScriptedDiceEngine:
    def __init__(self, selected: int) -> None:
        self.selected = selected
        self.calls: list[str] = []

    def roll(self, expression: str) -> DiceRoll:
        self.calls.append(expression)
        return DiceRoll(expression=expression, rolls=(self.selected,), total=self.selected)


def character(**overrides: object) -> CharacterState:
    values: dict[str, object] = {
        "id": "character_001", "total_level": 1,
        "saving_throw_proficiencies": frozenset(), "skill_proficiencies": frozenset(),
        "weapon_proficiencies": frozenset(),
    }
    values.update(overrides)
    return CharacterState(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("selected", "successes", "failures", "stable", "dead", "hp"),
    [(1, 1, 3, False, True, 0), (2, 1, 2, False, False, 0), (9, 1, 2, False, False, 0),
     (10, 2, 1, False, False, 0), (19, 2, 1, False, False, 0), (20, 0, 0, False, False, 1)],
)
def test_resolve_death_save_outcomes(selected: int, successes: int, failures: int, stable: bool, dead: bool, hp: int) -> None:
    dice = ScriptedDiceEngine(selected)
    result = resolve_character_death_save(character(death_save_successes=1, death_save_failures=1), dice)
    assert (result.successes, result.failures, result.stable, result.dead, result.hp_regain_amount) == (successes, failures, stable, dead, hp)
    assert dice.calls == ["1d20"]


def test_third_success_stabilizes_and_resets_both_counters() -> None:
    result = resolve_character_death_save(character(death_save_successes=2, death_save_failures=2), ScriptedDiceEngine(10))
    assert (result.successes, result.failures, result.stable, result.dead) == (0, 0, True, False)


def test_natural_one_caps_failures_at_three() -> None:
    result = resolve_character_death_save(character(death_save_failures=2), ScriptedDiceEngine(1))
    assert result.failures == 3
    assert result.dead is True


def test_ordinary_third_failure_kills_character() -> None:
    result = resolve_character_death_save(
        character(death_save_failures=2),
        ScriptedDiceEngine(2),
    )
    assert result.failures == 3
    assert result.dead is True


def valid_death_save_result(**overrides: object) -> CharacterDeathSaveResult:
    values: dict[str, object] = {
        "character_id": "character_001",
        "roll": D20Roll(RollMode.NORMAL, (10,), 10),
        "previous_successes": 1,
        "previous_failures": 1,
        "previous_stable": False,
        "previous_dead": False,
        "successes": 2,
        "failures": 1,
        "stable": False,
        "dead": False,
        "hp_regain_amount": 0,
    }
    values.update(overrides)
    return CharacterDeathSaveResult(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "overrides",
    [
        {"successes": 1},
        {"roll": D20Roll(RollMode.NORMAL, (2,), 2), "successes": 1, "failures": 1},
        {"roll": D20Roll(RollMode.NORMAL, (20,), 20), "successes": 0, "failures": 0, "hp_regain_amount": 0},
        {"roll": D20Roll(RollMode.NORMAL, (20,), 20), "successes": 1, "failures": 0, "hp_regain_amount": 1},
        {"previous_successes": 2, "successes": 0, "failures": 1},
        {"previous_stable": True},
        {"previous_dead": True},
        {
            "roll": D20Roll(RollMode.ADVANTAGE, (10, 4), 10),
        },
        {
            "roll": D20Roll(RollMode.DISADVANTAGE, (10, 14), 10),
        },
    ],
)
def test_death_save_result_rejects_impossible_transition(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        valid_death_save_result(**overrides)


def valid_failure_result(**overrides: object) -> CharacterDeathSaveFailureResult:
    values: dict[str, object] = {
        "character_id": "character_001", "previous_failures": 1,
        "previous_stable": False, "previous_dead": False,
        "critical_hit": False, "failures": 2, "stable": False, "dead": False,
    }
    values.update(overrides)
    return CharacterDeathSaveFailureResult(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "overrides",
    [
        {"failures": 3, "dead": True},
        {"critical_hit": True, "failures": 2},
        {"previous_failures": 2, "failures": 3, "dead": False},
        {"stable": True},
        {"previous_dead": True},
        {"previous_stable": True},
    ],
)
def test_failure_result_rejects_impossible_transition(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        valid_failure_result(**overrides)


@pytest.mark.parametrize(("critical", "expected"), [(False, 2), (True, 3)])
def test_damage_at_zero_records_failure_and_clears_stable(critical: bool, expected: int) -> None:
    result = resolve_character_death_save_failure(
        DamageResult(target_id="character_001", amount=4, previous_hp=0, new_hp=0),
        character(death_save_failures=1), critical_hit=critical,
    )
    assert result.failures == expected
    assert result.stable is False
    assert result.dead is (expected == 3)


def test_damage_at_zero_accepts_stable_character_and_preserves_result_immutability() -> None:
    result = resolve_character_death_save_failure(
        DamageResult(target_id="character_001", amount=1, previous_hp=0, new_hp=0),
        character(death_save_stable=True), critical_hit=False,
    )
    assert (result.previous_stable, result.failures, result.stable) == (True, 1, False)
    with pytest.raises(FrozenInstanceError):
        result.failures = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    ("damage", "state", "match"),
    [
        (DamageResult("character_001", 1, 1, 0), character(), "previous_hp"),
        (DamageResult("character_001", 1, 0, 0), character(dead=True), "dead"),
        (DamageResult("character_002", 1, 0, 0), character(), "target_id"),
    ],
)
def test_damage_failure_rejects_invalid_preconditions(damage: DamageResult, state: CharacterState, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        resolve_character_death_save_failure(damage, state, critical_hit=False)
