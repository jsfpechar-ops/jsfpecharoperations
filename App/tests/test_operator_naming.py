"""The host app calls the business behind a property an "operator".

The screens said "Legal entity" / "Právnická osoba" — a register-office phrase
that hides who the record actually is: the company or self-employed person who
runs the accommodation. The add form also marked only the name as required, so a
host could save a nameless operator with no seat, no IČO and no contact e-mail,
and the guest privacy notice then had nobody to point at.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app import auth, db, host_i18n
from app.dpa_i18n import DPA_STRINGS
from app.main import app
from app.privacy_policy_i18n import PRIVACY_STRINGS
from app.terms_i18n import TERMS_STRINGS

PASSWORD = "Secure-Password-123"
USERNAME = "operator-naming-host"

ENTITY_NAME = "Operator Naming s.r.o."

# The noun the host app must no longer use, in either language.
OLD_NOUNS = ("legal entity", "legal entities", "právnick")

# The stay-fee surfaces report to the municipal office and are filed by the
# legal entity that runs the accommodation. "Legal entity" is the term of art
# the report itself uses, pinned by the stay-fee plan (§12.2), so those keys are
# exempt from the operator rename — same reasoning as _legal_document_keys().
STAY_FEE_KEY_PREFIXES = ("stay_fees.", "apartment.form.stay_fee.")


def _legal_document_keys() -> set[str]:
    """Keys owned by the legal-document modules merged into the host table.

    Terms, the DPA and the privacy policy are contract prose with their own
    legally-defined vocabulary, and they are not part of this rename.
    """
    keys: set[str] = set()
    for module in (TERMS_STRINGS, PRIVACY_STRINGS, DPA_STRINGS):
        for table in module.values():
            keys.update(table)
    return keys

# (key, EN, CS) — copy the audit fixed, pinned so it cannot drift back.
PINNED = [
    ("nav.entities", "Operators", "Provozovatelé"),
    ("onboarding.entity.title", "Operator", "Provozovatel"),
    ("onboarding.entity.detail",
     "Who runs the accommodation — a company or a self-employed person.",
     "Kdo ubytování provozuje — firma nebo podnikající fyzická osoba."),
    ("onboarding.entity.prepare",
     "Have ready: name, IČO, registered address and a contact e-mail.",
     "Připravte si: jméno nebo název, IČO, sídlo a kontaktní e-mail."),
    ("onboarding.entity.action", "Add operator", "Přidat provozovatele"),
    ("apartments.table.entity", "Legal operator", "Právní provozovatel"),
    ("entities.title", "Business & legal details", "Firma a právní údaje"),
    ("entities.lede",
     "Who runs the accommodation — a company or a self-employed person.",
     "Kdo ubytování provozuje — firma nebo podnikající fyzická osoba."),
    ("entities.add_action", "Add operator", "Přidat provozovatele"),
    ("entities.email_hint",
     "Shown to guests as your contact.",
     "Hostům se zobrazí jako váš kontakt."),
    ("archive.chip.entities_count",
     "Operators (%(count)s)", "Provozovatelé (%(count)s)"),
    ("apartment.form.entity.label",
     "Property manager / operator", "Správce objektu / provozovatel"),
    ("apartment.form.controller.choose",
     "Choose an operator", "Vyberte provozovatele"),
    ("apartment.form.controller.manage_entities",
     "Manage operators", "Spravovat provozovatele"),
]


def _cleanup():
    """Delete this module's rows but keep the account other tables point at."""
    owner = "(SELECT id FROM user_account WHERE username = ?)"
    db.execute(f"DELETE FROM apartment WHERE owner_user_id = {owner}", (USERNAME,))
    db.execute(f"DELETE FROM legal_entity WHERE owner_user_id = {owner}", (USERNAME,))


def _add_operator() -> int:
    owner = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    return db.insert(
        "legal_entity",
        {
            "name": ENTITY_NAME,
            "seat": "Testovací 1, Praha",
            "ico": "12345678",
            "contact_email": "operator@naming.test",
            "owner_user_id": owner["id"],
            "created_at": db.utcnow(),
        },
    )


def _add_property(entity_id: int) -> int:
    owner = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    return db.insert(
        "apartment",
        {
            "internal_name": "Operator Naming Flat",
            "legal_entity_id": entity_id,
            "owner_user_id": owner["id"],
            "created_at": db.utcnow(),
        },
    )


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    existing = db.query_one(
        "SELECT id FROM user_account WHERE username = ?", (USERNAME,)
    )
    if not existing:
        auth.create_account(
            USERNAME, PASSWORD, "Operator Naming Host", must_change_password=False
        )
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": USERNAME, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup()


@pytest.fixture
def host_with_property(host):
    """A host that already has one property, so the table header renders."""
    _add_property(_add_operator())
    return host


def _input_tag(html: str, field_id: str) -> str:
    """The whole <input ...> tag for one field, attributes and all."""
    match = re.search(
        rf'<input[^>]*\bid="{re.escape(field_id)}"[^>]*>', html, re.DOTALL
    )
    assert match, f"no input with id {field_id!r} on the page"
    return match.group(0)


def _label_for(html: str, field_id: str) -> str:
    match = re.search(
        rf'<label[^>]*\bfor="{re.escape(field_id)}"[^>]*>(.*?)</label>',
        html,
        re.DOTALL,
    )
    assert match, f"no label for {field_id!r} on the page"
    return match.group(1)


# --- the copy itself -------------------------------------------------------


@pytest.mark.parametrize("key,en,cs", PINNED)
def test_the_audited_copy_is_in_both_dictionaries(key, en, cs):
    assert host_i18n.STRINGS["en"][key] == en
    assert host_i18n.STRINGS["cs"][key] == cs


def test_no_host_string_still_calls_it_a_legal_entity():
    legal = _legal_document_keys()
    offenders = []
    for lang, table in host_i18n.STRINGS.items():
        for key, value in table.items():
            if key in legal or key.startswith(STAY_FEE_KEY_PREFIXES):
                continue
            lowered = value.lower()
            if any(noun in lowered for noun in OLD_NOUNS):
                offenders.append(f"{lang}:{key}")
    assert offenders == []


def test_the_renamed_keys_exist_in_both_languages():
    en = host_i18n.STRINGS["en"]
    cs = host_i18n.STRINGS["cs"]
    for key, _, _ in PINNED:
        assert key in en, f"{key} is missing from EN"
        assert key in cs, f"{key} is missing from CS"


# --- the screens -----------------------------------------------------------


def test_the_navigation_links_to_operators(host):
    page = host.get("/apartments?lang=en")
    assert page.status_code == 200, page.text
    assert 'href="/entities"' in page.text
    assert "Business &amp; legal details" in page.text
    assert "Legal entities" not in page.text


def test_the_navigation_says_it_in_czech(host):
    page = host.get("/apartments?lang=cs")
    assert ">Firma a právní údaje<" in page.text
    assert "Právnické osoby" not in page.text


def test_the_properties_table_has_an_operator_column(host_with_property):
    page = host_with_property.get("/apartments?lang=en")
    assert page.status_code == 200, page.text
    assert "<th>Legal operator</th>" in page.text
    assert ENTITY_NAME in page.text


def test_the_operators_page_is_named_and_explained(host):
    page = host.get("/entities?lang=en")
    assert page.status_code == 200, page.text
    assert "Business &amp; legal details" in page.text
    assert (
        "Who runs the accommodation — a company or a self-employed person."
        in page.text
    )
    assert "No operators yet. Add the first one here." in page.text
    assert "Add an operator" in page.text
    assert "Legal entities" not in page.text


def test_the_operators_page_is_named_and_explained_in_czech(host):
    page = host.get("/entities?lang=cs")
    assert "Firma a právní údaje" in page.text
    assert "Kdo ubytování provozuje — firma nebo podnikající fyzická osoba." in page.text
    assert "Přidat provozovatele" in page.text
    assert "Právnické osoby" not in page.text


def test_the_saved_operator_is_named_in_the_property_form(host):
    _add_operator()
    page = host.get("/apartments/new?lang=en")
    assert page.status_code == 200, page.text
    assert f">{ENTITY_NAME}</option>" in page.text
    assert "Property manager / operator" in page.text
    assert "Manage operators" in page.text


def test_the_onboarding_banner_asks_for_an_operator(host):
    page = host.get("/?lang=en")
    assert page.status_code == 200, page.text
    assert "Operator" in page.text
    assert (
        "Who runs the accommodation — a company or a self-employed person."
        in page.text
    )
    assert "Add operator" in page.text
    assert "Legal entity" not in page.text


def test_the_onboarding_banner_asks_for_an_operator_in_czech(host):
    page = host.get("/?lang=cs")
    assert "Provozovatel" in page.text
    assert "Kdo ubytování provozuje — firma nebo podnikající fyzická osoba." in page.text
    assert "Přidat provozovatele" in page.text


def test_the_onboarding_checklist_no_longer_demands_a_phone(host):
    page = host.get("/onboarding?lang=en")
    assert page.status_code == 200, page.text
    assert (
        "Have ready: name, IČO, registered address and a contact e-mail."
        in page.text
    )
    assert "phone" not in page.text.split("Have ready")[1].split("</")[0]


# --- the add form ----------------------------------------------------------


def test_the_identity_fields_are_required(host):
    page = host.get("/entities?lang=en")
    for field_id in ("new_seat", "new_ico", "new_contact_email"):
        tag = _input_tag(page.text, field_id)
        assert "required" in tag, f"{field_id} is not required: {tag}"


def test_the_optional_fields_stay_optional(host):
    page = host.get("/entities?lang=en")
    for field_id in ("new_dic", "new_contact_phone"):
        tag = _input_tag(page.text, field_id)
        assert "required" not in tag, f"{field_id} should stay optional: {tag}"
        assert "optional" in _label_for(page.text, field_id).lower()


def test_the_contact_email_explains_where_it_shows(host):
    page = host.get("/entities?lang=en")
    assert '<div class="hint">Shown to guests as your contact.</div>' in page.text


def test_the_contact_email_explains_itself_in_czech(host):
    page = host.get("/entities?lang=cs")
    assert (
        '<div class="hint">Hostům se zobrazí jako váš kontakt.</div>' in page.text
    )


def test_the_edit_form_asks_for_the_same_required_fields(host):
    entity_id = _add_operator()
    page = host.get(f"/entities?edit={entity_id}&lang=en")
    assert page.status_code == 200, page.text
    for field_id in ("edit_seat", "edit_ico", "edit_contact_email"):
        assert "required" in _input_tag(page.text, field_id)


def test_the_required_fields_carry_a_label(host):
    """`required` is only announced if the control still has a real label."""
    page = host.get("/entities?lang=en")
    for field_id in ("new_seat", "new_ico", "new_contact_email"):
        assert _label_for(page.text, field_id).strip()
