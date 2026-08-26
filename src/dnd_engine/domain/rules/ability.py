def ability_modifier(score: int) -> int:
    if type(score) is not int:
        raise TypeError("score must be an int")
    return (score - 10) // 2
