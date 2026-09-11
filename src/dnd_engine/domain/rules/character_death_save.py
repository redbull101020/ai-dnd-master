from dataclasses import dataclass

from dnd_engine.domain.rules.d20 import resolve_d20_roll
from dnd_engine.domain.rules.damage import DamageResult
from dnd_engine.domain.services.dice import DiceEngine
from dnd_engine.domain.state.character import CharacterState
from dnd_engine.domain.value_objects.d20 import D20Roll, RollMode


@dataclass(frozen=True)
class CharacterDeathSaveResult:
    character_id: str
    roll: D20Roll
    previous_successes: int
    previous_failures: int
    previous_stable: bool
    previous_dead: bool
    successes: int
    failures: int
    stable: bool
    dead: bool
    hp_regain_amount: int

    def __post_init__(self) -> None:
        if type(self.character_id) is not str:
            raise TypeError("character_id must be a str")
        if not isinstance(self.roll, D20Roll):
            raise TypeError("roll must be a D20Roll")
        if self.roll.mode is not RollMode.NORMAL:
            raise ValueError("roll mode must be normal")
        for name in ("previous_successes", "previous_failures", "successes", "failures", "hp_regain_amount"):
            if type(getattr(self, name)) is not int:
                raise TypeError(f"{name} must be an int")
        for name in ("previous_stable", "previous_dead", "stable", "dead"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be a bool")
        if not 0 <= self.previous_successes <= 2:
            raise ValueError("previous_successes must be between 0 and 2")
        if not 0 <= self.previous_failures <= 2:
            raise ValueError("previous_failures must be between 0 and 2")
        if self.previous_stable or self.previous_dead:
            raise ValueError("previous_stable and previous_dead must be False")
        if not 0 <= self.successes <= 2:
            raise ValueError("successes must be between 0 and 2")
        if not 0 <= self.failures <= 3:
            raise ValueError("failures must be between 0 and 3")
        if self.stable and self.dead:
            raise ValueError("stable and dead cannot both be True")
        if self.stable and (self.successes != 0 or self.failures != 0):
            raise ValueError("stable requires reset counters")
        if self.failures == 3 and not self.dead:
            raise ValueError("three failures require dead to be True")
        if self.hp_regain_amount not in (0, 1):
            raise ValueError("hp_regain_amount must be 0 or 1")

        expected = _death_save_transition(
            selected=self.roll.selected,
            previous_successes=self.previous_successes,
            previous_failures=self.previous_failures,
        )
        actual = (
            self.successes,
            self.failures,
            self.stable,
            self.dead,
            self.hp_regain_amount,
        )
        if actual != expected:
            raise ValueError("result must match the canonical death save transition")


@dataclass(frozen=True)
class CharacterDeathSaveFailureResult:
    character_id: str
    previous_failures: int
    previous_stable: bool
    previous_dead: bool
    critical_hit: bool
    failures: int
    stable: bool
    dead: bool

    def __post_init__(self) -> None:
        if type(self.character_id) is not str:
            raise TypeError("character_id must be a str")
        for name in ("previous_failures", "failures"):
            if type(getattr(self, name)) is not int:
                raise TypeError(f"{name} must be an int")
        for name in ("previous_stable", "previous_dead", "critical_hit", "stable", "dead"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be a bool")
        if not 0 <= self.previous_failures <= 2:
            raise ValueError("previous_failures must be between 0 and 2")
        if self.previous_dead:
            raise ValueError("previous_dead must be False")
        if self.previous_stable and self.previous_failures != 0:
            raise ValueError("previous_stable requires zero previous_failures")
        if not 0 <= self.failures <= 3:
            raise ValueError("failures must be between 0 and 3")
        if self.stable:
            raise ValueError("stable must be False")
        expected_failures = min(
            self.previous_failures + (2 if self.critical_hit else 1),
            3,
        )
        if self.failures != expected_failures:
            raise ValueError("failures must match the canonical damage consequence")
        if self.dead is not (self.failures == 3):
            raise ValueError("dead must equal failures == 3")


def _death_save_transition(
    *,
    selected: int,
    previous_successes: int,
    previous_failures: int,
) -> tuple[int, int, bool, bool, int]:
    if selected == 20:
        return (0, 0, False, False, 1)
    if selected == 1:
        failures = min(previous_failures + 2, 3)
        return (previous_successes, failures, False, failures == 3, 0)
    if selected <= 9:
        failures = previous_failures + 1
        return (previous_successes, failures, False, failures == 3, 0)
    if previous_successes == 2:
        return (0, 0, True, False, 0)
    return (
        previous_successes + 1,
        previous_failures,
        False,
        False,
        0,
    )


def resolve_character_death_save(
    character: CharacterState,
    dice: DiceEngine,
) -> CharacterDeathSaveResult:
    if not isinstance(character, CharacterState):
        raise TypeError("character must be a CharacterState")
    if character.death_save_stable:
        raise ValueError("character must not already be stable")
    if character.dead:
        raise ValueError("character must not already be dead")

    roll = resolve_d20_roll(dice, RollMode.NORMAL)
    successes = character.death_save_successes
    failures = character.death_save_failures
    stable = False
    dead = False
    hp_regain_amount = 0

    if roll.selected == 20:
        successes = 0
        failures = 0
        hp_regain_amount = 1
    elif roll.selected == 1:
        failures = min(failures + 2, 3)
        dead = failures == 3
    elif roll.selected <= 9:
        failures += 1
        dead = failures == 3
    elif successes == 2:
        successes = 0
        failures = 0
        stable = True
    else:
        successes += 1

    return CharacterDeathSaveResult(
        character_id=character.id,
        roll=roll,
        previous_successes=character.death_save_successes,
        previous_failures=character.death_save_failures,
        previous_stable=character.death_save_stable,
        previous_dead=character.dead,
        successes=successes,
        failures=failures,
        stable=stable,
        dead=dead,
        hp_regain_amount=hp_regain_amount,
    )


def resolve_character_death_save_failure(
    damage: DamageResult,
    character: CharacterState,
    *,
    critical_hit: bool,
) -> CharacterDeathSaveFailureResult:
    if not isinstance(damage, DamageResult):
        raise TypeError("damage must be a DamageResult")
    if not isinstance(character, CharacterState):
        raise TypeError("character must be a CharacterState")
    if type(critical_hit) is not bool:
        raise TypeError("critical_hit must be a bool")
    if damage.target_id != character.id:
        raise ValueError("damage target_id must match character id")
    if damage.previous_hp != 0:
        raise ValueError("damage previous_hp must be 0")
    if character.dead:
        raise ValueError("character must not already be dead")

    failures = min(character.death_save_failures + (2 if critical_hit else 1), 3)
    return CharacterDeathSaveFailureResult(
        character_id=character.id,
        previous_failures=character.death_save_failures,
        previous_stable=character.death_save_stable,
        previous_dead=character.dead,
        critical_hit=critical_hit,
        failures=failures,
        stable=False,
        dead=failures == 3,
    )
