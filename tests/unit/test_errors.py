import pytest

from app.core.errors import translate_error


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        ({"type": "missing", "msg": "Field required"}, "обязательное поле"),
        ({"type": "greater_than_equal", "msg": "", "ctx": {"ge": 0}}, "должно быть не меньше 0"),
        ({"type": "string_too_short", "msg": "", "ctx": {"min_length": 1}}, "минимум 1 симв."),
        (
            {"type": "literal_error", "msg": "", "ctx": {"expected": "'a', 'b' or 'c'"}},
            "допустимые значения: 'a', 'b', 'c'",
        ),
        ({"type": "value_error", "msg": "Value error, x", "ctx": {"error": "нужно поле"}}, "нужно поле"),
        ({"type": "unknown_type", "msg": "Original message"}, "Original message"),
        ({"type": "greater_than", "msg": "Original", "ctx": {}}, "Original"),
    ],
)
def test_translate_error(error, expected):
    assert translate_error(error) == expected
