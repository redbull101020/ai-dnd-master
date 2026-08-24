from copy import deepcopy
from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.commands.ability_check import (
    AbilityCheckCommand,
    AbilityCheckPayload,
)
from dnd_engine.domain.rules.ability_check import (
    AbilityCheckResult,
    ability_modifier,
    resolve_ability_check,
)
from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.value_objects.ability import Ability
from dnd_engine.domain.value_objects.ability_scores import AbilityScores
from dnd_engine.domain.value_objects.dice_roll import DiceRoll


class ScriptedDiceEngine:
    def __init__(self, roll: DiceRoll) -> None:
        self._roll = roll
        self.calls: list[str] = []

    def roll(self, expression: str) -> DiceRoll:
        self.calls.append(expression)
        return self._roll


def make_creature() -> CreatureState:
    return CreatureState(
        id="character_001",
        definition_id="fighter",
        ability_scores=AbilityScores(
            strength=8,
            dexterity=14,
            constitution=12,
            intelligence=16,
            wisdom=10,
            charisma=18,
        ),
        current_hp=20,
        max_hp=20,
    )


def make_command(
    *,
    ability: Ability = Ability.STRENGTH,
    dc: int = 15,
) -> AbilityCheckCommand:
    return AbilityCheckCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id="character_001",
        payload=AbilityCheckPayload(ability=ability, dc=dc),
    )


def test_ability_has_exact_closed_values() -> None:
    assert tuple(Ability) == (
        Ability.STRENGTH,
        Ability.DEXTERITY,
        Ability.CONSTITUTION,
        Ability.INTELLIGENCE,
        Ability.WISDOM,
        Ability.CHARISMA,
    )
    assert tuple(ability.value for ability in Ability) == (
        "strength",
        "dexterity",
        "constitution",
        "intelligence",
        "wisdom",
        "charisma",
    )


def test_ability_members_are_immutable() -> None:
    with pytest.raises(AttributeError):
        Ability.STRENGTH.value = "power"  # type: ignore[misc]


def test_ability_check_payload_and_command_have_exact_fields() -> None:
    assert tuple(field.name for field in fields(AbilityCheckPayload)) == (
        "ability",
        "dc",
    )
    assert tuple(field.name for field in fields(AbilityCheckCommand)) == (
        "command_id",
        "campaign_id",
        "actor_id",
        "payload",
        "type",
    )


def test_ability_check_command_is_typed_and_immutable() -> None:
    command = make_command()

    assert command.type == "AbilityCheckCommand"
    assert isinstance(command.payload, AbilityCheckPayload)
    assert command.payload.ability is Ability.STRENGTH

    with pytest.raises(FrozenInstanceError):
        command.actor_id = "character_002"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        command.payload.dc = 10  # type: ignore[misc]


def test_command_type_is_fixed_and_not_an_init_parameter() -> None:
    with pytest.raises(TypeError):
        AbilityCheckCommand(
            command_id="command_000001",
            campaign_id="campaign_001",
            actor_id="character_001",
            payload=AbilityCheckPayload(ability=Ability.STRENGTH, dc=15),
            type="OtherCommand",  # type: ignore[call-arg]
        )


def test_payload_rejects_arbitrary_ability() -> None:
    with pytest.raises(TypeError):
        AbilityCheckPayload(ability="strength", dc=15)  # type: ignore[arg-type]


@pytest.mark.parametrize("dc", [True, 15.0, "15", None])
def test_payload_rejects_non_exact_integer_dc(dc: object) -> None:
    with pytest.raises(TypeError):
        AbilityCheckPayload(ability=Ability.STRENGTH, dc=dc)  # type: ignore[arg-type]


def test_payload_does_not_add_an_arbitrary_dc_range() -> None:
    assert AbilityCheckPayload(ability=Ability.WISDOM, dc=-5).dc == -5
    assert AbilityCheckPayload(ability=Ability.WISDOM, dc=100).dc == 100


@pytest.mark.parametrize("field_name", ["command_id", "campaign_id", "actor_id"])
def test_command_rejects_non_exact_string_ids(field_name: str) -> None:
    values: dict[str, object] = {
        "command_id": "command_000001",
        "campaign_id": "campaign_001",
        "actor_id": "character_001",
        "payload": AbilityCheckPayload(ability=Ability.STRENGTH, dc=15),
    }
    values[field_name] = 1

    with pytest.raises(TypeError):
        AbilityCheckCommand(**values)  # type: ignore[arg-type]


def test_command_rejects_untyped_payload() -> None:
    with pytest.raises(TypeError):
        AbilityCheckCommand(
            command_id="command_000001",
            campaign_id="campaign_001",
            actor_id="character_001",
            payload={"ability": "strength", "dc": 15},  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("score", "expected"),
    [(1, -5), (8, -1), (9, -1), (10, 0), (11, 0), (12, 1), (20, 5), (30, 10)],
)
def test_ability_modifier(score: int, expected: int) -> None:
    assert ability_modifier(score) == expected


@pytest.mark.parametrize("score", [True, 10.0, "10", None])
def test_ability_modifier_rejects_non_exact_integer(score: object) -> None:
    with pytest.raises(TypeError):
        ability_modifier(score)  # type: ignore[arg-type]


def test_ability_modifier_adds_no_second_score_range() -> None:
    assert ability_modifier(0) == -5
    assert ability_modifier(31) == 10


def test_resolver_selects_requested_score_and_rolls_exactly_once() -> None:
    dice = ScriptedDiceEngine(DiceRoll(expression="1d20", rolls=(7,), total=7))

    result = resolve_ability_check(
        make_command(ability=Ability.DEXTERITY, dc=20),
        make_creature(),
        dice,
    )

    assert dice.calls == ["1d20"]
    assert result == AbilityCheckResult(
        ability=Ability.DEXTERITY,
        dc=20,
        roll=DiceRoll(expression="1d20", rolls=(7,), total=7),
        modifier=2,
        total=9,
        succeeded=False,
    )


@pytest.mark.parametrize(
    ("raw_roll", "dc", "expected_total", "expected_succeeded"),
    [(16, 15, 15, True), (15, 15, 14, False)],
)
def test_resolver_distinguishes_gameplay_success_and_failure(
    raw_roll: int,
    dc: int,
    expected_total: int,
    expected_succeeded: bool,
) -> None:
    dice = ScriptedDiceEngine(
        DiceRoll(expression="1d20", rolls=(raw_roll,), total=raw_roll)
    )

    result = resolve_ability_check(make_command(dc=dc), make_creature(), dice)

    assert result.total == expected_total
    assert result.succeeded is expected_succeeded


def test_resolver_does_not_mutate_creature_or_ability_scores() -> None:
    creature = make_creature()
    original = deepcopy(creature)
    original_scores = creature.ability_scores
    dice = ScriptedDiceEngine(DiceRoll(expression="1d20", rolls=(20,), total=20))

    resolve_ability_check(make_command(), creature, dice)

    assert creature == original
    assert creature.ability_scores is original_scores


def test_ability_check_result_is_immutable_and_consistent() -> None:
    result = resolve_ability_check(
        make_command(),
        make_creature(),
        ScriptedDiceEngine(DiceRoll(expression="1d20", rolls=(7,), total=7)),
    )

    with pytest.raises(FrozenInstanceError):
        result.total = 10  # type: ignore[misc]
    with pytest.raises(ValueError):
        AbilityCheckResult(
            ability=Ability.STRENGTH,
            dc=15,
            roll=DiceRoll(expression="1d20", rolls=(7,), total=7),
            modifier=-1,
            total=7,
            succeeded=False,
        )
