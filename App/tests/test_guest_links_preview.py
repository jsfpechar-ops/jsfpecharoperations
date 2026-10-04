"""The guest link page can show the host what a guest actually sees [C-36].

The permanent link lives on this page, but the only preview of it was on the
onboarding finish card - two screens away, and gone once onboarding is done.
"""
from __future__ import annotations

from app import db, guest_slug, host_i18n
from tests.test_guest_links_bilingual import TOKEN, _apartment_id, host  # noqa: F401


def _preview_href() -> str:
    """The preview opens the readable link (WP19), which resolves to TOKEN."""
    row = db.query_one("SELECT id FROM apartment WHERE permalink_token = ?", (TOKEN,))
    return f'href="/l/{guest_slug.current(row["id"])}"'


def _preview_anchor(text: str) -> str:
    marker = _preview_href()
    assert marker in text, "no preview link to the guest picker"
    anchor = text.split(marker, 1)[1]
    return marker + anchor.split("</a>", 1)[0]


def test_the_page_offers_a_preview_of_the_guest_picker(host):  # noqa: F811
    _apartment_id()

    page = host.get("/guest-links?lang=en")

    assert page.status_code == 200
    assert _preview_href() in page.text
    assert host_i18n.STRINGS["en"]["guest_links.preview"] in page.text


def test_the_preview_opens_in_a_new_tab_so_the_host_does_not_lose_the_page(host):  # noqa: F811
    _apartment_id()

    anchor = _preview_anchor(host.get("/guest-links?lang=en").text)

    assert 'target="_blank"' in anchor
    assert 'rel="noopener"' in anchor


def test_a_czech_host_reads_the_preview_label_in_czech(host):  # noqa: F811
    _apartment_id()

    page = host.get("/guest-links?lang=cs")

    assert host_i18n.STRINGS["cs"]["guest_links.preview"] in page.text
    assert host_i18n.STRINGS["cs"]["guest_links.preview"] == "Zobrazit jako host"


def test_the_preview_sits_beside_the_property_setup_link(host):  # noqa: F811
    _apartment_id()

    text = host.get("/guest-links?lang=en").text
    setup = text.index(host_i18n.STRINGS["en"]["guest_links.property_setup"])
    preview = text.index(host_i18n.STRINGS["en"]["guest_links.preview"])

    assert setup < preview
    # Same actions row: nothing opens a new block between the two.
    assert "</div>" not in text[setup:preview]


def test_the_preview_targets_the_guest_side_not_the_host_property_page(host):  # noqa: F811
    apartment_id = _apartment_id()

    anchor = _preview_anchor(host.get("/guest-links?lang=en").text)

    assert f"/apartments/{apartment_id}" not in anchor
    assert anchor.endswith(f'{_preview_href()} target="_blank" rel="noopener">'
                           f'{host_i18n.STRINGS["en"]["guest_links.preview"]}')


def test_the_preview_is_a_link_not_a_button_so_it_can_be_opened_in_a_tab(host):  # noqa: F811
    _apartment_id()

    label = host_i18n.STRINGS["en"]["guest_links.preview"]
    text = host.get("/guest-links?lang=en").text
    tag = text[: text.index(f">{label}</a>")].rsplit("<", 1)[-1]

    assert tag.startswith("a class="), tag
