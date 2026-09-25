"""UX-121 (audit A-34): the document fields must not be spell-checked."""
import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
FORM = APP_DIR / "templates" / "guest" / "form.html"

# "doc/visa" per the backlog row. parent_doc_number is the same kind of field
# but was not in the row's scope.
DOC_FIELDS = ("doc_number", "visa_number")


def _form() -> str:
    return FORM.read_text(encoding="utf-8")


def _input(field: str) -> str:
    match = re.search(r"<input[^>]*id=\"" + re.escape(field) + r"\"[^>]*>", _form())
    assert match, f"the {field} input disappeared"
    return " ".join(match.group(0).split())


def test_the_document_number_is_not_spell_checked_or_autocorrected():
    for field in DOC_FIELDS:
        tag = _input(field)
        assert 'spellcheck="false"' in tag, field
        assert 'autocorrect="off"' in tag, field
        # the field is still a document field: caps, bounded length
        assert 'autocapitalize="characters"' in tag, field


def test_the_fix_did_not_disturb_the_document_fields():
    assert 'name="doc_number" maxlength="30"' in _input("doc_number")
    assert 'name="visa_number" maxlength="15"' in _input("visa_number")
    assert 'value="{{ val(\'visa_number\') }}"' in _input("visa_number")


def test_the_other_id_like_fields_keep_their_own_attributes():
    # a guard against a blanket edit that would hit the name fields too
    given = _input("first_name")
    assert 'autocomplete="given-name"' in given
    assert "spellcheck" not in given
