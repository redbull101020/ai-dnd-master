def character_proficiency_bonus(level: int) -> int:
    if type(level) is not int:
        raise TypeError("level must be an int")
    if not 1 <= level <= 20:
        raise ValueError("level must be between 1 and 20")
    return 2 + (level - 1) // 4
