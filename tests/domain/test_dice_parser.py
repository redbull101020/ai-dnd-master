import pytest

from dnd_engine.domain.dice import parse_ndm


@pytest.mark.parametrize(
    ("expression", "count", "sides"),
    [
        ("1d2", 1, 2),
        ("1d6", 1, 6),
        ("2d8", 2, 8),
        ("10d100", 10, 100),
        ("1d7", 1, 7),
    ],
)
def test_parse_ndm_accepts_valid_expression(
    expression: str,
    count: int,
    sides: int,
) -> None:
    assert parse_ndm(expression) == (count, sides)


@pytest.mark.parametrize(
    "expression",
    [
        "",
        "foo",
        "d20",
        "1d",
        "0d20",
        "-1d20",
        "1d0",
        "01d6",
        "1d06",
        "1D20",
        " 1d20",
        "1d20 ",
        "1d20+5",
        "2d20kh1",
        "2d20kl1",
        "4d6d1",
        "1d6!",
        "۱1d20",
        "1٤d20",
        "1d２０",
    ],
)
def test_parse_ndm_rejects_malformed_syntax(expression: str) -> None:
    with pytest.raises(ValueError, match="invalid dice expression"):
        parse_ndm(expression)


def test_parse_ndm_rejects_one_sided_die() -> None:
    with pytest.raises(ValueError, match="dice must have at least two sides"):
        parse_ndm("1d1")


class Expression(str):
    pass


@pytest.mark.parametrize(
    "expression",
    [None, 20, True, Expression("1d20")],
)
def test_parse_ndm_rejects_non_exact_string(expression: object) -> None:
    with pytest.raises(TypeError, match="expression must be a str"):
        parse_ndm(expression)  # type: ignore[arg-type]
