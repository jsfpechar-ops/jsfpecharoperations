"""Skeleton loaders (FR-1): the placeholder markup, script and copy exist."""
from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from app import host_i18n
from app.main import app

APP_DIR = Path(__file__).resolve().parents[1] / "app"


def test_host_base_has_hidden_page_skeleton_before_app_js():
    html = (APP_DIR / "templates" / "base.html").read_text(encoding="utf-8")
    assert "data-page-skeleton" in html
    assert 'role="status" hidden' in html
    assert html.index("/static/skeleton.js") < html.index("/static/app.js")


def test_host_loading_copy_in_both_languages():
    assert host_i18n.translate("en", "a11y.loading") == "Loading…"
    assert host_i18n.translate("cs", "a11y.loading") == "Načítá se…"


def test_skeleton_styles_do_not_loop():
    css = (APP_DIR / "static" / "components.css").read_text(encoding="utf-8")
    assert ".page-skeleton" in css
    assert "infinite" not in css


def test_skeleton_script_is_served():
    with TestClient(app) as client:
        response = client.get("/static/skeleton.js")
    assert response.status_code == 200
    assert "window.ubyhostSkeleton" in response.text


def test_the_dsr_json_export_is_treated_as_a_download():
    """The Art 15/20 bundle is an attachment, so it must not blank the page.

    ``/guests/{id}/export.json`` answers with ``Content-Disposition:
    attachment``; the browser cancels the navigation, so a suffix missing from
    ``DOWNLOAD_RE`` would leave the skeleton up until the 15-second timer.
    ``isDownload`` is a bare regex test on the pathname, so the regex itself is
    the unit under test.
    """
    script = (APP_DIR / "static" / "skeleton.js").read_text(encoding="utf-8")
    match = re.search(r"DOWNLOAD_RE\s*=\s*/(.+?)/([a-z]*);", script)
    assert match, "skeleton.js no longer defines DOWNLOAD_RE"
    flags = re.IGNORECASE if "i" in match.group(2) else 0
    pattern = re.compile(match.group(1), flags)

    assert pattern.search("/guests/7/export.json"), "the DSR export still blanks the page"
    assert not pattern.search("/guests/7"), "a normal page must keep the skeleton"


def test_guest_base_has_hidden_page_skeleton():
    html = (APP_DIR / "templates" / "guest" / "base.html").read_text(encoding="utf-8")
    assert "data-page-skeleton" in html
    assert html.index("/static/skeleton.js") < html.index("/static/signature.js")


def test_guest_loading_copy_in_both_languages():
    from app import i18n

    assert i18n.translator("en")("loading") == "Loading…"
    assert i18n.translator("cs")("loading") == "Načítá se…"


def _download_pattern():
    script = (APP_DIR / "static" / "skeleton.js").read_text(encoding="utf-8")
    match = re.search(r"DOWNLOAD_RE\s*=\s*/(.+?)/([a-z]*);", script)
    assert match, "skeleton.js no longer defines DOWNLOAD_RE"
    flags = re.IGNORECASE if "i" in match.group(2) else 0
    return re.compile(match.group(1), flags)


# Every route that answers with an attachment, as a concrete path. A new
# download route belongs here; if its path does not match, the page goes
# blank behind the skeleton for 15 seconds after the click.
DOWNLOAD_PATHS = (
    "/stay-fees/42/pdf",
    "/stay-fees/42/csv",
    "/invoices/5.pdf",
    "/guests/7/form.pdf",
    "/guests/7/export.json",
    "/guests/7/passport-photo",  # linked with the download attribute
    "/submissions/3/receipt.pdf",
    "/submissions/3/errors.pdf",
    "/submissions/receipts.zip",
    "/housebook.csv",
    "/housebook/pdfs.zip",
    "/reservations.csv",
    "/settings/workspace-export",
    "/admin/users/9/export",
    "/admin/funnel.csv",
    "/admin/ads-conversions.csv",
)

# Pages that render HTML and must keep the skeleton.
PAGE_PATHS = (
    "/stay-fees",
    "/stay-fees/42",
    "/invoices/5",
    "/guests/7",
    "/submissions/3",
    "/housebook",
    "/settings",
    "/admin/users",
    "/reservations/12",
)


def test_every_download_route_skips_the_skeleton():
    """Download PDF on a stay-fee report blanked the page (2026-10-06).

    ``/stay-fees/{id}/pdf`` has no file extension, so the old suffix regex
    treated it as a page and showed the placeholder until the safety timer.
    """
    pattern = _download_pattern()
    for path in DOWNLOAD_PATHS:
        if path.endswith("/passport-photo"):
            continue  # the template link carries ``download``
        assert pattern.search(path), f"{path} would blank the page behind the skeleton"
    for path in PAGE_PATHS:
        assert not pattern.search(path), f"{path} is a page and must keep the skeleton"


def test_download_links_in_templates_are_covered():
    """Every download href/action in a template matches DOWNLOAD_RE or opts out."""
    pattern = _download_pattern()
    templates = APP_DIR / "templates"
    found = []
    for html in templates.rglob("*.html"):
        text = html.read_text(encoding="utf-8")
        for match in re.finditer(r'(?:href|action)="(/[^"?{]*(?:\{\{[^}]*\}\}[^"?{]*)*)', text):
            path = re.sub(r"\{\{[^}]*\}\}", "1", match.group(1))
            if path.startswith("/static/"):
                continue
            tail = text[match.end(): match.end() + 200]
            if re.search(r"(?:^|\W)(?:pdf|zip|csv|json|export)$", path, re.IGNORECASE):
                found.append(path)
                assert pattern.search(path) or "download" in tail.split(">")[0], (html.name, path)
    assert "/stay-fees/1/pdf" in found and "/stay-fees/1/csv" in found
