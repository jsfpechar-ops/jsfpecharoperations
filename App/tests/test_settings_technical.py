"""Settings opens on the host's own work, not on a developer console.

"Where reports go", the guest e-mail outbox and the cached UbyPort code lists
are deployment and developer diagnostics: endpoint, poll intervals, env var
names, "Mail backend: console". They used to be the first thing on Settings,
addressed to every host. They now sit in one collapsed "Technical details"
block, so the page opens on data protection and the account, and the
diagnostics stay one click away.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.host_i18n import STRINGS as HOST_STRINGS
from app.main import app

PASSWORD = "Secure-Password-123"
USERNAME = "settings-technical-host"

OPEN_TAG = '<details class="panel technical" id="settings-technical">'
PIN_PANEL = '<div class="panel" id="settings-ubyport">'


def _cleanup():
    for row in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        for table in ("alert", "audit", "apartment", "legal_entity"):
            db.execute(f"DELETE FROM {table} WHERE owner_user_id = ?", (row["id"],))
        db.execute("DELETE FROM user_account WHERE id = ?", (row["id"],))


def _client(lang: str) -> TestClient:
    db.init_db()
    _cleanup()
    auth.create_account(USERNAME, PASSWORD, "Settings Host", must_change_password=False)
    client = TestClient(app)
    response = client.post(
        f"/login?lang={lang}",
        data={"username": USERNAME, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return client


@pytest.fixture()
def host():
    client = _client("en")
    try:
        yield client
    finally:
        _cleanup()


@pytest.fixture()
def czech_host():
    client = _client("cs")
    try:
        yield client
    finally:
        _cleanup()


def _technical_block(page: str) -> str:
    """The one collapsed block, from its open tag to its own close tag."""
    start = page.index(OPEN_TAG)
    end = page.index(PIN_PANEL, start)
    block = page[start:end].rstrip()
    assert block.endswith("</details>"), "the technical block did not close cleanly"
    return block


def test_the_technical_details_start_collapsed(host):
    page = host.get("/settings").text
    # The exact open tag means no `open` attribute and no extra one.
    assert OPEN_TAG in page
    assert f"{OPEN_TAG}\n      <summary>" in page


def test_the_three_diagnostics_live_in_that_one_block(host):
    page = host.get("/settings").text
    block = _technical_block(page)
    for key in (
        "settings.destination.title",
        "settings.mail.title",
        "settings.codelists.title",
    ):
        assert HOST_STRINGS["en"][key] in block
    # The parts that are addressed to an operator, not to a host.
    assert HOST_STRINGS["en"]["settings.destination.endpoint"] in block
    assert HOST_STRINGS["en"]["settings.mail.backend"] in block


def test_the_guest_form_pin_stays_out_of_the_technical_block(host):
    page = host.get("/settings").text
    block = _technical_block(page)
    assert HOST_STRINGS["en"]["settings.access.title"] not in block
    assert PIN_PANEL in page


def test_the_czech_page_reads_technicke_udaje(czech_host):
    page = czech_host.get("/settings").text
    block = _technical_block(page)
    assert HOST_STRINGS["cs"]["settings.technical.title"] in block
    assert HOST_STRINGS["cs"]["settings.destination.title"] in block
    assert HOST_STRINGS["cs"]["settings.codelists.title"] in block


def test_the_section_nav_points_at_the_collapsed_block(host):
    page = host.get("/settings").text
    start = page.index('class="section-nav settings-nav"')
    nav = page[start : page.index("</nav>", start)]
    assert 'href="#settings-technical"' in nav
    assert 'href="#settings-overview"' not in nav
    assert 'href="#settings-mail"' not in nav


def test_both_languages_name_the_block_the_same_way():
    assert HOST_STRINGS["en"]["settings.technical.title"] == "Technical details"
    assert HOST_STRINGS["cs"]["settings.technical.title"] == "Technické údaje"
    for table in (HOST_STRINGS["en"], HOST_STRINGS["cs"]):
        assert "settings.nav.overview" not in table
        assert "settings.nav.mail" not in table
