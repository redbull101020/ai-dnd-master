import re


_DICE_EXPRESSION = re.compile(r"([1-9][0-9]*)d([1-9][0-9]*)")


def parse_ndm(expression: str) -> tuple[int, int]:
    """Parse strict lowercase `NdM` dice notation into `(count, sides)`.

    Grammar: `[1-9][0-9]*d[1-9][0-9]*`, with `count >= 1` and `sides >= 2`.
    No modifiers, arithmetic, advantage/disadvantage, keep/drop, or other
    dice DSL syntax is accepted.
    """
    if type(expression) is not str:
        raise TypeError("expression must be a str")

    match = _DICE_EXPRESSION.fullmatch(expression)
    if match is None:
        raise ValueError("invalid dice expression")

    count, sides = (int(value) for value in match.groups())
    if sides < 2:
        raise ValueError("dice must have at least two sides")

    return count, sides
