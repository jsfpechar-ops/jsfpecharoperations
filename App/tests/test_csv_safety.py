from app.csv_safety import csv_safe
from app.housebook import housebook_csv


def test_formula_prefix_is_neutralised():
    assert csv_safe("=HYPERLINK(1)") == "'=HYPERLINK(1)"


def test_line_breaks_and_nbsp_are_neutralised():
    """A formula behind a line break or a non-breaking space still executes."""
    assert csv_safe("\n=HYPERLINK(1)") == "'\n=HYPERLINK(1)"
    assert csv_safe("\r=HYPERLINK(1)") == "'\r=HYPERLINK(1)"
    assert csv_safe("\xa0=HYPERLINK(1)") == "'\xa0=HYPERLINK(1)"


def test_plain_text_is_untouched():
    assert csv_safe("Novák") == "Novák"


def test_numbers_are_untouched():
    assert csv_safe(3) == 3


def test_housebook_csv_escapes_a_formula_cell():
    out = housebook_csv([{"surname": "=1+1"}])
    assert "'=1+1" in out.decode("utf-8")
