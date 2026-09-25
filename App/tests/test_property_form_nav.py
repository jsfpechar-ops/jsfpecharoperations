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
    start = text.index('<nav class="section-nav"')
    return text[start : text.index("</nav>", start)]


def _rendered_text(text: str) -> str:
    """Page copy with the tags taken out, so a link inside a sentence reads as one."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", text))).strip()


def _automation_panel(text: str) -> str:
    start = text.index('<div class="panel" id="automation">')
    return text[start : text.index("</div>", start)]


def test_the_third_nav_link_is_the_police_panel(host):
    client, apartment_id = host

    nav = _nav(client.get(f"/apartments/{apartment_id}?lang=en").text)

    assert '<a href="#ubyport">3. Police reporting</a>' in nav


def test_the_nav_no_longer_sends_you_off_the_form(host):
    client, apartment_id = host

    nav = _nav(client.get(f"/apartments/{apartment_id}?lang=en").text)

    assert "/automation#apartment-" not in nav


def test_the_czech_nav_says_hlasi_se_policii(host):
    client, apartment_id = host

    nav = _nav(client.get(f"/apartments/{apartment_id}?lang=cs").text)

    assert '<a href="#ubyport">3. Hlášení policii</a>' in nav


def test_the_nav_numbers_run_one_to_five_without_a_gap(host):
    client, apartment_id = host

    nav = _nav(client.get(f"/apartments/{apartment_id}?lang=en").text)
    numbers = [int(n) for n in re.findall(r">(\d)\. ", nav)]

    assert numbers == [1, 2, 3, 4, 5]


def test_the_automation_summary_names_the_page_it_sends_you_to(host):
    client, apartment_id = host

    page = client.get(f"/apartments/{apartment_id}?lang=en")

    assert (
        "Send timing and default purpose are set on the Automation page."
        in _rendered_text(page.text)
    )


def test_the_czech_automation_summary_says_the_same(host):
    client, apartment_id = host

    page = client.get(f"/apartments/{apartment_id}?lang=cs")

    assert (
        "Časování odesílání a výchozí účel pobytu nastavíte na stránce Automatizace."
        in _rendered_text(page.text)
    )


def test_the_automation_summary_no_longer_promises_credentials(host):
    client, apartment_id = host

    panel = _automation_panel(client.get(f"/apartments/{apartment_id}?lang=en").text)

    assert "UbyPort credentials" not in panel
    assert "one place to manage reporting" not in panel


def test_the_czech_automation_summary_no_longer_promises_credentials(host):
    client, apartment_id = host

    page = client.get(f"/apartments/{apartment_id}?lang=cs").text

    assert "údaje UbyPortu" not in _automation_panel(page)


def test_the_automation_panel_still_links_to_the_automation_page(host):
    client, apartment_id = host

    page = client.get(f"/apartments/{apartment_id}?lang=en").text

    assert f'href="/automation#apartment-{apartment_id}"' in _automation_panel(page)


def test_the_new_property_form_keeps_its_own_nav_labels(host):
    """Creating a property is a different journey; its nav was already correct."""
    client, _apartment_id = host

    nav = _nav(client.get("/apartments/new?lang=en").text)

    assert '<a href="#ubyport">3. UbyPort</a>' in nav
    assert '<a href="#automation">4. Automation</a>' in nav


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
