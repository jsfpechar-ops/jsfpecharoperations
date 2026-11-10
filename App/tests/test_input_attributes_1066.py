"""1066 (plan Q1, S4, S12): input attributes on guest, address and operator fields."""
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
TEMPLATES = APP / "templates"


def _read(rel: str) -> str:
    return (TEMPLATES / rel).read_text(encoding="utf-8")


def _tag(source: str, field_id: str, kind: str = "input") -> str:
    match = re.search(r"<" + kind + r"[^>]*id=\"" + re.escape(field_id) + r"\"[^>]*>", source)
    assert match, f"{field_id} disappeared"
    return " ".join(match.group(0).split())


def test_guest_names_and_address_get_capitals():
    form = _read("guest/form.html")
    for field in ("first_name", "surname", "res_city", "res_street"):
        assert 'autocapitalize="words"' in _tag(form, field), field


def test_guest_document_and_nationality_are_not_autofilled():
    form = _read("guest/form.html")
    for field in ("doc_number", "parent_doc_number", "visa_number"):
        assert 'autocomplete="off"' in _tag(form, field), field
    assert 'autocomplete="off"' in _tag(form, "nationality", "select")
    assert 'autocomplete="off"' in _tag(form, "purpose", "select")


def test_guest_tokens_that_were_right_are_kept():
    form = _read("guest/form.html")
    assert 'autocomplete="given-name"' in _tag(form, "first_name")
    assert 'autocomplete="family-name"' in _tag(form, "surname")
    assert 'autocomplete="address-level2"' in _tag(form, "res_city")
    assert 'autocomplete="address-line1"' in _tag(form, "res_street")
    assert 'autocomplete="country"' in _tag(form, "res_country", "select")
    assert 'autocomplete="bday"' in _tag(form, "birth_date")


def test_guest_email_keyboard():
    tag = _tag(_read("guest/claim.html"), "guest_email")
    assert 'autocomplete="email"' in tag
    assert 'inputmode="email"' in tag
    assert 'autocapitalize="none"' in tag


def test_property_address_is_never_autofilled_and_has_examples():
    source = _read("_property_address_fields.html")
    assert 'name="{{ name }}" autocomplete="off"' in source
    for example in ("Vinohradská", "12000", "Praha", "Vinohrady"):
        assert f"placeholder='{example}'" in source, example


def test_operator_fields_use_standard_tokens():
    source = _read("_entity_business_fields.html")
    assert 'name="name" autocomplete="organization"' in source
    assert 'name="seat" autocomplete="street-address"' in source
    assert 'name="contact_email" autocomplete="email"' in source
    assert 'autocomplete="tel-national"' in source
    assert 'name="ico" inputmode="numeric" autocomplete="off"' in source
    invoice = _read("_entity_invoice_fields.html")
    assert 'autocapitalize="characters"' in _tag(invoice, "bic")


def test_help_dot_tap_targets():
    css = (APP / "static" / "app2.css").read_text(encoding="utf-8")
    # Desktop (>=1024) stays 24 px (WCAG 2.5.8). A 44 px ::before there overflowed #settings-group-phone.
    assert not re.search(
        r"@media \(min-width:1024px\)\{body\.v2 \.help-tip-btn::before\{[^}]*width:44px", css
    )
    assert re.search(r"@media \(max-width:1023px\)\{body\.v2 \.help-tip-btn\{width:44px;height:44px", css)
    guest = (APP / "static" / "guest.css").read_text(encoding="utf-8")
    block = guest.split("details.g-head-help > summary {", 1)[1].split("}", 1)[0]
    assert "width: 44px" in block and "height: 44px" in block
