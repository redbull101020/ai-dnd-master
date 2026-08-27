from dnd_engine.domain.value_objects.skill import Skill


CANONICAL_SKILL_VALUES = (
    "acrobatics",
    "animal_handling",
    "arcana",
    "athletics",
    "deception",
    "history",
    "insight",
    "intimidation",
    "investigation",
    "medicine",
    "nature",
    "perception",
    "performance",
    "persuasion",
    "religion",
    "sleight_of_hand",
    "stealth",
    "survival",
)


def test_skill_is_exact_closed_canonical_set() -> None:
    assert tuple(skill.value for skill in Skill) == CANONICAL_SKILL_VALUES
    assert len(Skill) == 18


def test_skill_serialized_values_are_canonical_strings() -> None:
    assert all(type(skill.value) is str for skill in Skill)
    assert tuple(map(str, Skill)) == CANONICAL_SKILL_VALUES
