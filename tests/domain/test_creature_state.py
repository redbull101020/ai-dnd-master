from dataclasses import FrozenInstanceError, fields

import pytest

from dnd_engine.domain.state.creature import CreatureState
from dnd_engine.domain.value_objects.ability_scores import AbilityScores


CANONICAL_FIELDS = (
    "id",
    "definition_id",
    "ability_scores",
    "current_hp",
    "max_hp",
)

FUTURE_PHASE_FIELDS = (
    "skills",
    "saving_throws",
    "proficiency",
    "conditions",
    "effects",
    "movement",
    "speed",
    "senses",
    "position",
    "initiative",
    "turn_resources",
    "equipment",
    "inventory",
    "armor_class",
    "challenge_rating",
    "actions",
    "spellcasting",
    "campaign_id",
    "ruleset_id",
    "owner_id",
    "player_id",
)


def goblin_scores() -> AbilityScores:
    return AbilityScores(
        strength=8,
        dexterity=14,
        constitution=10,
        intelligence=10,
        wisdom=8,
        charisma=8,
    )


def creature_state(
    *,
    current_hp: int = 7,
    max_hp: int = 7,
) -> CreatureState:
    return CreatureState(
        id="monster_001",
        definition_id="goblin",
        ability_scores=goblin_scores(),
        current_hp=current_hp,
        max_hp=max_hp,
    )


def test_creature_state_accepts_canonical_fields() -> None:
    creature = creature_state()

    assert creature.id == "monster_001"
    assert creature.definition_id == "goblin"
    assert creature.ability_scores == goblin_scores()
    assert creature.current_hp == 7
    assert creature.max_hp == 7


def test_creature_state_has_only_canonical_fields() -> None:
    assert tuple(field.name for field in fields(CreatureState)) == CANONICAL_FIELDS


def test_creature_state_is_mutable() -> None:
    creature = creature_state()

    creature.current_hp = 3

    assert creature.current_hp == 3


def test_creature_state_keeps_runtime_and_definition_ids_separate() -> None:
    creature = creature_state()

    assert creature.id == "monster_001"
    assert creature.definition_id == "goblin"
    assert creature.id != creature.definition_id


def test_creature_state_uses_ability_scores() -> None:
    creature = creature_state()

    assert isinstance(creature.ability_scores, AbilityScores)


def test_creature_state_embeds_immutable_ability_scores() -> None:
    creature = creature_state()

    with pytest.raises(FrozenInstanceError):
        creature.ability_scores.dexterity = 12  # type: ignore[misc]


@pytest.mark.parametrize(
    ("current_hp", "max_hp"),
    [
        (0, 7),
        (7, 7),
        (1, 1),
    ],
)
def test_creature_state_accepts_hp_boundaries(current_hp: int, max_hp: int) -> None:
    creature = creature_state(current_hp=current_hp, max_hp=max_hp)

    assert creature.current_hp == current_hp
    assert creature.max_hp == max_hp


@pytest.mark.parametrize("max_hp", [0, -1])
def test_creature_state_rejects_non_positive_max_hp(max_hp: int) -> None:
    with pytest.raises(ValueError):
        creature_state(current_hp=0, max_hp=max_hp)


def test_creature_state_rejects_negative_current_hp() -> None:
    with pytest.raises(ValueError):
        creature_state(current_hp=-1)


def test_creature_state_rejects_current_hp_above_max_hp() -> None:
    with pytest.raises(ValueError):
        creature_state(current_hp=8, max_hp=7)


@pytest.mark.parametrize("current_hp", [7.0, "7", None])
def test_creature_state_rejects_non_int_current_hp(current_hp: object) -> None:
    with pytest.raises(TypeError):
        creature_state(current_hp=current_hp)  # type: ignore[arg-type]


@pytest.mark.parametrize("max_hp", [7.0, "7", None])
def test_creature_state_rejects_non_int_max_hp(max_hp: object) -> None:
    with pytest.raises(TypeError):
        creature_state(max_hp=max_hp)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("current_hp", "max_hp"),
    [
        (True, 7),
        (1, True),
    ],
)
def test_creature_state_rejects_bool_hp_values(
    current_hp: object,
    max_hp: object,
) -> None:
    with pytest.raises(TypeError):
        creature_state(  # type: ignore[arg-type]
            current_hp=current_hp,
            max_hp=max_hp,
        )


def test_creature_state_does_not_include_future_phase_fields() -> None:
    canonical_fields = {field.name for field in fields(CreatureState)}

    assert canonical_fields.isdisjoint(FUTURE_PHASE_FIELDS)
