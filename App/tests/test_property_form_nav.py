"""The property form's section nav sends you to the page you are already on.

Editing a property used to offer "3. Automation & UbyPort" — a link that jumped
clean off the form to /automation, where credentials are not edited either. The
third section of the form is the UbyPort police credentials, so the third link
now says "Police reporting" and stays on the page. The automation summary keeps
one honest sentence and one link out, instead of claiming credentials live
there.
"""
from __future__ import annotations

import html
import re

from app import host_i18n

# test_property_readiness already seeds a property and logs in as its owner;
# `as host` marks the import as an intentional re-export so ruff keeps it.
from tests.test_property_readiness import host as host  # noqa: F401


def _nav(text: str) -> str:
    """Just the section nav, so the page body cannot be mistaken for it."""
    if 'class="host-property-grid"' in text:
        start = text.index('<div class="host-property-grid"')
        end = text.find('<section class="panel host-checklist"', start)
        return text[start:end if end > 0 else text.index('data-property-view="bookings"', start)]
    start = text.index('<nav class="section-nav"')
    return text[start:text.index('</nav>', start)]


def _rendered_text(text: str) -> str:
    """Page copy with the tags taken out, so a link inside a sentence reads as one."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", text))).strip()


def _automation_panel(text: str) -> str:
    start = text.index('<section class="panel property-section" id="automation"')
    return text[start:text.index('</section>', start)]


def test_the_third_nav_link_is_the_police_panel(host):
    client, apartment_id = host

    nav = _nav(client.get(f"/apartments/{apartment_id}?lang=en").text)

    assert '#ubyport"' in nav  # 0094: ?view=settings&section=reporting#ubyport
    assert '<strong>Police reporting</strong>' in nav


def test_the_nav_no_longer_sends_you_off_the_form(host):
    client, apartment_id = host

    nav = _nav(client.get(f"/apartments/{apartment_id}?lang=en").text)

    assert "/automation#apartment-" not in nav


def test_the_czech_nav_says_hlasi_se_policii(host):
    client, apartment_id = host

    nav = _nav(client.get(f"/apartments/{apartment_id}?lang=cs").text)

    assert '#ubyport"' in nav
    assert '<strong>Hlášení policii</strong>' in nav


def test_the_nav_numbers_run_one_to_five_without_a_gap(host):
    client, apartment_id = host

    nav = _nav(client.get(f"/apartments/{apartment_id}?lang=en").text)
    targets = re.findall(r'href="[^"#]*#([^"]+)"', nav)
    # 0094: the business card opens the shared entity editor, not a property anchor.
    assert targets == ['calendars', 'ubyport', 'stay-fee-settings', 'address']
    assert 'href="/entities' in nav


def test_the_automation_panel_is_editable_on_the_property_page(host):
    client, apartment_id = host

    panel = _automation_panel(client.get(f"/apartments/{apartment_id}?lang=en").text)

    assert 'name="automation_mode"' in panel
    assert 'name="default_purpose"' in panel
    assert "Automatic modes do not wait for ID verification" in panel


def test_the_automation_summary_no_longer_promises_credentials(host):
    client, apartment_id = host

    panel = _automation_panel(client.get(f"/apartments/{apartment_id}?lang=en").text)

    assert "UbyPort credentials" not in panel
    assert "one place to manage reporting" not in panel


def test_the_czech_automation_summary_no_longer_promises_credentials(host):
    client, apartment_id = host

    page = client.get(f"/apartments/{apartment_id}?lang=cs").text

    assert "údaje UbyPortu" not in _automation_panel(page)


def test_the_automation_panel_does_not_link_away(host):
    client, apartment_id = host

    page = client.get(f"/apartments/{apartment_id}?lang=en").text

    assert "/automation" not in _automation_panel(page)


def test_the_new_property_form_has_no_numbered_nav(host):
    """0092: creating a property is one short page, not a numbered tour."""
    client, _apartment_id = host

    page = client.get("/apartments/new?lang=en").text

    assert '<nav class="section-nav"' not in page
    assert "3. UbyPort" not in page and "5. Guest link" not in page
    assert 'name="uby_idub"' not in page


def test_the_audited_copy_is_in_both_dictionaries():
    pinned = {
        "apartment.form.nav.police_reporting": ("3. Police reporting", "3. Hlášení policii"),
        "apartment.form.automation.page_name": ("Automation", "Automatizace"),
    }
    for key, (en, cs) in pinned.items():
        assert host_i18n.STRINGS["en"][key] == en, key
        assert host_i18n.STRINGS["cs"][key] == cs, key


def test_the_automation_lede_has_no_leftover_credentials_clause():
    for lang in ("en", "cs"):
        before = host_i18n.STRINGS[lang]["apartment.form.automation.editing_lede_before"]
        after = host_i18n.STRINGS[lang]["apartment.form.automation.editing_lede_after"]
        sentence = f"{before}Automation{after}"
        assert "UbyPort" not in before, lang
        assert sentence.endswith("."), lang
        assert len(sentence) < 120, lang
