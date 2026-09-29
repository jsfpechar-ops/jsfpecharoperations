from app.csv_safety import csv_safe
from app.housebook import housebook_csv


def test_formula_prefix_is_neutralised():
    assert csv_safe("=HYPERLINK(1)") == "'=HYPERLINK(1)"


def test_plain_text_is_untouched():
    assert csv_safe("Novák") == "Novák"


def test_numbers_are_untouched():
    assert csv_safe(3) == 3


def test_housebook_csv_escapes_a_formula_cell():
    out = housebook_csv([{"surname": "=1+1"}])
    assert "'=1+1" in out.decode("utf-8")
