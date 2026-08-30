from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.commands.start_combat import (
    StartCombatCommand,
    StartCombatPayload,
)
from dnd_engine.domain.rules.start_combat import (
    InitiativeEntry,
    StartCombatResult,
    resolve_start_combat,
)
from dnd_engine.domain.state.creature import CreatureState
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
    *, creature_id: str, dexterity: int = 10
) -> CreatureState:
    return CreatureState(
        id=creature_id,
        definition_id="fighter",
        ability_scores=AbilityScores(
            strength=10,
            dexterity=dexterity,
            constitution=10,
            intelligence=10,
            wisdom=10,
            charisma=10,
        ),
        current_hp=10,
        max_hp=10,
    )


def make_command(*participant_ids: str, actor_id: str = "character_001") -> StartCombatCommand:
    return StartCombatCommand(
        command_id="command_000001",
        campaign_id="campaign_001",
        actor_id=actor_id,
        payload=StartCombatPayload(
            combat_id="combat_001", participant_ids=participant_ids
        ),
    )


def normal_modes(count: int) -> tuple[RollMode, ...]:
    return tuple(RollMode.NORMAL for _ in range(count))


def test_resolver_orders_participants_by_descending_total() -> None:
    command = make_command("character_001", "monster_001")
    participants = (
        make_creature(creature_id="character_001", dexterity=10),
        make_creature(creature_id="monster_001", dexterity=14),
    )
    dice = ScriptedDiceEngine(8, 15)

    result = resolve_start_combat(
        command, participants, dice, roll_modes=normal_modes(2)
    )

    assert dice.calls == ["1d20", "1d20"]
    assert result.combat_id == "combat_001"
    assert result.round == 1
    assert result.order == ("monster_001", "character_001")
    assert [entry.total for entry in result.entries] == [17, 8]


def test_resolver_breaks_equal_total_ties_by_higher_dexterity() -> None:
    command = make_command("character_001", "monster_001")
    participants = (
        make_creature(creature_id="character_001", dexterity=10),
        make_creature(creature_id="monster_001", dexterity=18),
    )
    # character_001: roll 10 + mod 0 = 10; monster_001: roll 6 + mod 4 = 10
    dice = ScriptedDiceEngine(10, 6)

    result = resolve_start_combat(
        command, participants, dice, roll_modes=normal_modes(2)
    )

    assert [entry.total for entry in result.entries] == [10, 10]
    assert result.order == ("monster_001", "character_001")


def test_resolver_breaks_full_ties_by_creature_id() -> None:
    command = make_command("monster_002", "monster_001")
    participants = (
        make_creature(creature_id="monster_002", dexterity=10),
        make_creature(creature_id="monster_001", dexterity=10),
    )
    dice = ScriptedDiceEngine(10, 10)

    result = resolve_start_combat(
        command, participants, dice, roll_modes=normal_modes(2)
    )

    assert result.order == ("monster_001", "monster_002")


def test_resolver_supports_single_participant() -> None:
    command = make_command("character_001")
    participants = (make_creature(creature_id="character_001"),)
    dice = ScriptedDiceEngine(12)

    result = resolve_start_combat(
        command, participants, dice, roll_modes=normal_modes(1)
    )

    assert result.order == ("character_001",)
    assert len(result.entries) == 1


def test_entries_carry_full_roll_audit() -> None:
    command = make_command("character_001")
    participants = (make_creature(creature_id="character_001", dexterity=14),)
    dice = ScriptedDiceEngine(9)

    result = resolve_start_combat(
        command, participants, dice, roll_modes=normal_modes(1)
    )

    entry = result.entries[0]
    assert entry.creature_id == "character_001"
    assert entry.roll == D20Roll(mode=RollMode.NORMAL, rolls=(9,), selected=9)
    assert entry.modifier == 2
    assert entry.total == 11


# --- effective RollMode per participant (SRD 5.1: Initiative is a Dexterity
# check, so the existing Poisoned Ability Check policy applies) -------------


def test_normal_participant_uses_one_roll_and_records_normal_mode() -> None:
    command = make_command("character_001")
    participants = (make_creature(creature_id="character_001", dexterity=14),)
    dice = ScriptedDiceEngine(9)

    result = resolve_start_combat(
        command, participants, dice, roll_modes=(RollMode.NORMAL,)
    )

    assert dice.calls == ["1d20"]
    entry = result.entries[0]
    assert entry.roll == D20Roll(mode=RollMode.NORMAL, rolls=(9,), selected=9)


def test_poisoned_participant_uses_two_rolls_and_selects_the_lower() -> None:
    command = make_command("character_001")
    participants = (make_creature(creature_id="character_001", dexterity=14),)
    dice = ScriptedDiceEngine(17, 6)

    result = resolve_start_combat(
        command, participants, dice, roll_modes=(RollMode.DISADVANTAGE,)
    )

    assert dice.calls == ["1d20", "1d20"]
    entry = result.entries[0]
    assert entry.roll == D20Roll(
        mode=RollMode.DISADVANTAGE, rolls=(17, 6), selected=6
    )
    assert entry.modifier == 2
    assert entry.total == 8


def test_mixed_normal_and_poisoned_participants_preserve_dice_call_order() -> None:
    command = make_command("character_001", "monster_001", "monster_002")
    participants = (
        make_creature(creature_id="character_001", dexterity=10),
        make_creature(creature_id="monster_001", dexterity=10),
        make_creature(creature_id="monster_002", dexterity=10),
    )
    # character_001 (poisoned): rolls 17, 6 -> selected 6
    # monster_001 (normal): rolls 12
    # monster_002 (poisoned): rolls 4, 19 -> selected 4
    dice = ScriptedDiceEngine(17, 6, 12, 4, 19)

    result = resolve_start_combat(
        command,
        participants,
        dice,
        roll_modes=(RollMode.DISADVANTAGE, RollMode.NORMAL, RollMode.DISADVANTAGE),
    )

    assert dice.calls == ["1d20", "1d20", "1d20", "1d20", "1d20"]
    entries_by_id = {entry.creature_id: entry for entry in result.entries}
    assert entries_by_id["character_001"].roll == D20Roll(
        mode=RollMode.DISADVANTAGE, rolls=(17, 6), selected=6
    )
    assert entries_by_id["monster_001"].roll == D20Roll(
        mode=RollMode.NORMAL, rolls=(12,), selected=12
    )
    assert entries_by_id["monster_002"].roll == D20Roll(
        mode=RollMode.DISADVANTAGE, rolls=(4, 19), selected=4
    )


def test_resolver_rejects_roll_modes_length_mismatch() -> None:
    command = make_command("character_001", "monster_001")
    participants = (
        make_creature(creature_id="character_001"),
        make_creature(creature_id="monster_001"),
    )
    dice = ScriptedDiceEngine(10, 10)

    with pytest.raises(ValueError, match="roll_modes"):
        resolve_start_combat(
            command, participants, dice, roll_modes=(RollMode.NORMAL,)
        )

    assert dice.calls == []


def test_resolver_rejects_non_tuple_roll_modes() -> None:
    command = make_command("character_001")
    participants = (make_creature(creature_id="character_001"),)
    dice = ScriptedDiceEngine(10)

    with pytest.raises(TypeError, match="roll_modes"):
        resolve_start_combat(
            command,
            participants,
            dice,
            roll_modes=[RollMode.NORMAL],  # type: ignore[arg-type]
        )

    assert dice.calls == []


def test_resolver_rejects_non_rollmode_entries() -> None:
    command = make_command("character_001")
    participants = (make_creature(creature_id="character_001"),)
    dice = ScriptedDiceEngine(10)

    with pytest.raises(TypeError, match="roll_modes"):
        resolve_start_combat(
            command,
            participants,
            dice,
            roll_modes=("normal",),  # type: ignore[arg-type]
        )

    assert dice.calls == []


def test_resolver_rejects_wrong_types() -> None:
    dice = ScriptedDiceEngine(10)

    with pytest.raises(TypeError, match="StartCombatCommand"):
        resolve_start_combat(
            object(),  # type: ignore[arg-type]
            (make_creature(creature_id="character_001"),),
            dice,
            roll_modes=normal_modes(1),
        )
    with pytest.raises(TypeError, match="tuple"):
        resolve_start_combat(
            make_command("character_001"),
            [make_creature(creature_id="character_001")],  # type: ignore[arg-type]
            dice,
            roll_modes=normal_modes(1),
        )


def test_resolver_rejects_participant_order_mismatch() -> None:
    command = make_command("character_001", "monster_001")
    participants = (
        make_creature(creature_id="monster_001"),
        make_creature(creature_id="character_001"),
    )
    dice = ScriptedDiceEngine(10, 10)

    with pytest.raises(ValueError, match="participant_ids"):
        resolve_start_combat(
            command, participants, dice, roll_modes=normal_modes(2)
        )

    assert dice.calls == []


# --- InitiativeEntry / StartCombatResult invariants -----------------------


def canonical_entry(**overrides: object) -> InitiativeEntry:
    values: dict[str, object] = {
        "creature_id": "character_001",
        "roll": D20Roll(mode=RollMode.NORMAL, rolls=(10,), selected=10),
        "modifier": 2,
        "total": 12,
    }
    values.update(overrides)
    return InitiativeEntry(**values)  # type: ignore[arg-type]


def test_initiative_entry_has_exact_fields_and_is_immutable() -> None:
    entry = canonical_entry()

    assert tuple(field.name for field in fields(InitiativeEntry)) == (
        "creature_id",
        "roll",
        "modifier",
        "total",
    )
    with pytest.raises(FrozenInstanceError):
        entry.total = 1  # type: ignore[misc]


def test_initiative_entry_rejects_inconsistent_total() -> None:
    with pytest.raises(ValueError, match="total"):
        canonical_entry(total=99)


def canonical_result(**overrides: object) -> StartCombatResult:
    values: dict[str, object] = {
        "combat_id": "combat_001",
        "round": 1,
        "order": ("character_001",),
        "entries": (canonical_entry(),),
    }
    values.update(overrides)
    return StartCombatResult(**values)  # type: ignore[arg-type]


def test_start_combat_result_rejects_round_other_than_one() -> None:
    with pytest.raises(ValueError, match="round"):
        canonical_result(round=2)


def test_start_combat_result_rejects_order_entry_mismatch() -> None:
    with pytest.raises(ValueError, match="order"):
        canonical_result(order=("monster_001",))


def test_start_combat_result_rejects_ascending_totals() -> None:
    low = canonical_entry(creature_id="character_001", modifier=-5, total=5)
    high = canonical_entry(
        creature_id="monster_001",
        roll=D20Roll(mode=RollMode.NORMAL, rolls=(15,), selected=15),
        total=17,
    )

    with pytest.raises(ValueError, match="descending"):
        canonical_result(
            order=("character_001", "monster_001"), entries=(low, high)
        )


def test_start_combat_result_rejects_duplicate_order_entries() -> None:
    duplicate = canonical_entry(creature_id="character_001")

    with pytest.raises(ValueError, match="duplicate"):
        canonical_result(
            order=("character_001", "character_001"),
            entries=(duplicate, duplicate),
        )
