"""A 27-clause contract needs a contents list, anchors, and a way back.

The audit asked for one `<details>` that is `open` on a wide screen and closed
on a phone. No stylesheet can do that: a media query cannot set the `open`
attribute, and a closed `<details>` hides its content in a way CSS cannot
override (the child is not rendered at all, so `display` on it changes
nothing). So the wide layout is a plain `<nav>` and the phone layout is a
`<details>` — the same split `_public_header.html` already uses for its nav and
its menu. Both carry the same list, and the hidden one is `display: none`, so
only the visible one is ever in the accessibility tree.

The anchor offset is deliberately not a `scroll-margin-top`: `landing.css`
already sets `html { scroll-padding-top: 88px }`, which clears the 76px sticky
public header by 12px. Adding a margin would stack on top of it and leave ~192px
of dead space above every heading.
"""
from __future__ import annotations

import re
from pathlib import Path

from starlette.testclient import TestClient

from app import db, host_i18n
from app.main import app
from app.routes.legal import DPA_SECTION_IDS, PRIVACY_SECTION_IDS, TERMS_SECTION_IDS
from app.subprocessors_i18n import SUBPROCESSOR_STRINGS

APP_DIR = Path(__file__).resolve().parents[1]

# path, i18n key prefix, the ids the route hands the template
DOCUMENTS = (
    ("/terms", "terms", TERMS_SECTION_IDS),
    ("/privacy", "privacy", PRIVACY_SECTION_IDS),
    ("/dpa", "dpa", DPA_SECTION_IDS),
)

TEMPLATES = {
    "terms": "terms.html",
    "privacy": "privacy.html",
    "dpa": "dpa.html",
}


def _client() -> TestClient:
    db.init_db()
    return TestClient(app)


def _read(relative: str) -> str:
    return (APP_DIR / relative).read_text(encoding="utf-8")


def _toc_block(html: str) -> str:
    start = html.index('<div class="legal-toc"')
    return html[start : html.index("</div>", html.index("</details>", start))]


def _toc_halves(html: str) -> tuple[list[str], list[str]]:
    block = _toc_block(html)
    wide, narrow = block.split("<details", 1)
    href = re.compile(r'<a href="#s(\d+)">')
    return href.findall(wide), href.findall(narrow)


def test_every_clause_has_a_stable_anchor_matching_the_route():
    client = _client()
    for path, _prefix, ids in DOCUMENTS:
        for lang in ("en", "cs"):
            html = client.get(f"{path}?lang={lang}").text
            found = re.findall(
                r'<section class="legal-section" id="s(\d+)">', html
            )
            assert found == list(ids), (path, lang, len(found), len(ids))
            assert len(set(found)) == len(found), path


def test_the_contents_list_the_clauses_in_order():
    client = _client()
    for path, _prefix, ids in DOCUMENTS:
        html = client.get(f"{path}?lang=cs").text
        wide, narrow = _toc_halves(html)
        assert wide == list(ids), path
        assert narrow == list(ids), path


def test_the_contents_are_labelled_for_screen_readers():
    client = _client()
    for path, _prefix, _ids in DOCUMENTS:
        for lang, expected in (("en", "Contents"), ("cs", "Obsah")):
            block = _toc_block(client.get(f"{path}?lang={lang}").text)
            labels = re.findall(r'<nav[^>]*aria-label="([^"]+)"', block)
            # one for the wide list, one for the phone disclosure's list
            assert labels == [expected, expected], (path, lang, labels)


def test_a_wide_screen_gets_the_list_and_a_phone_gets_the_disclosure():
    css = _read("app/static/app.css")
    assert re.search(
        r"\.legal-toc-narrow\s*\{[^}]*display:\s*none", css
    ), "the phone disclosure must be hidden by default"
    # the flip must happen inside a max-width media block
    for block in re.findall(r"@media \(max-width: \d+px\) \{(.*?)\n\}", css, re.S):
        if ".legal-toc-wide { display: none; }" in block:
            assert ".legal-toc-narrow { display: block; }" in block
            break
    else:
        raise AssertionError("no media block hides the wide list")


def test_the_phone_disclosure_starts_closed():
    client = _client()
    for path, _prefix, _ids in DOCUMENTS:
        html = client.get(f"{path}?lang=cs").text
        assert "<details class=\"legal-toc-narrow\" open" not in html, path
        assert '<details class="legal-toc-narrow">' in html, path


def test_every_clause_offers_a_way_back_to_the_contents():
    client = _client()
    for path, _prefix, ids in DOCUMENTS:
        for lang in ("en", "cs"):
            html = client.get(f"{path}?lang={lang}").text
            assert 'id="legal-contents"' in html, path
            back = re.findall(
                r'<p class="legal-back"><a href="#legal-contents">(.*?)</a></p>',
                html,
            )
            assert len(back) == len(ids), (path, lang, len(back))
            label = host_i18n.translate(lang, "legal.back_to_toc")
            assert all(item.startswith(label) for item in back), (path, lang)
            # the arrow is decoration; a screen reader must not read it out
            assert all('aria-hidden="true"' in item for item in back), path


def test_the_back_arrow_is_the_only_thing_inside_aria_hidden():
    client = _client()
    html = client.get("/terms?lang=en").text
    item = re.search(
        r'<p class="legal-back"><a href="#legal-contents">(.*?)</a></p>', html
    )
    assert item is not None
    visible = re.sub(r'<span aria-hidden="true">.*?</span>', "", item.group(1))
    assert visible.strip() == "Back to contents"


def test_contents_and_back_to_contents_are_translated_and_at_parity():
    for key in ("legal.toc", "legal.back_to_toc"):
        english = host_i18n.translate("en", key)
        czech = host_i18n.translate("cs", key)
        assert english and czech, key
        assert english != key and czech != key, key
        assert english != czech, key
    assert host_i18n.translate("en", "legal.toc") == "Contents"
    assert host_i18n.translate("cs", "legal.toc") == "Obsah"
    assert host_i18n.translate("en", "legal.back_to_toc") == "Back to contents"
    assert host_i18n.translate("cs", "legal.back_to_toc") == "Zpět na obsah"


def test_the_clause_text_is_reading_sized_not_fine_print():
    css = _read("app/static/app.css")
    rule = re.search(r"\n\.terms-section \{(.*?)\n\}", css, re.S)
    assert rule is not None, "no .terms-section rule"
    body = rule.group(1)
    assert "font-size: var(--text-md)" in body
    assert "color: var(--ink-secondary)" in body
    assert "line-height: 1.7" in body
    assert "max-width: 70ch" in body
    # and no template still demotes the clause text to small print
    for name in TEMPLATES.values():
        template = _read(f"app/templates/{name}")
        assert 'class="small muted terms-section"' not in template, name


def test_the_clauses_are_separated_by_a_hairline_not_a_card():
    css = _read("app/static/app.css")
    rule = re.search(r"\n\.legal-section \{(.*?)\n\}", css, re.S)
    assert rule is not None, "no .legal-section rule"
    assert "border-top: 1px solid var(--border)" in rule.group(1)
    for prefix, name in TEMPLATES.items():
        template = _read(f"app/templates/{name}")
        assert '<section class="legal-section" id="s{{ sid }}">' in template, name
        assert '<div class="panel">' not in template, name


def test_the_anchor_clears_the_sticky_public_header_without_doubling_up():
    landing = _read("app/static/landing.css")
    padding = re.search(r"scroll-padding-top:\s*(\d+)px", landing)
    assert padding is not None, "landing.css no longer insets the anchor scroll"
    header = re.search(r"\.landing-header\b.*?min-height:\s*(\d+)px", landing, re.S)
    assert header is not None, "landing.css no longer sets a header height"
    assert int(padding.group(1)) > int(header.group(1))
    # a scroll-margin would stack on top of scroll-padding-top
    assert "scroll-margin" not in _read("app/static/app.css")
    assert "scroll-margin" not in landing


# ---- LD-4: the register must not claim backups are encrypted ----------------
#
# Until OPS-1 lands, `backup_data.sh` writes the database and the Fernet key
# into the same snapshot, and `backup-gdrive.sh` / `backup-s3.sh` upload that
# snapshot unchanged (`docs/OPERATIONS.md` "Backup and restore"). The register
# used to call those copies "encrypted", which was false.
#
# When OPS-1 and OPS-2 ship, update the copy *and* this test together, citing
# the vendor evidence file (`docs/vendors/README.md`, LD-9). The four keys
# below are the backup rows: AWS' S3 purpose and Google's purpose and data.

REGISTER_BACKUP_KEYS = (
    "subprocessors.aws_purpose",
    "subprocessors.google_purpose",
    "subprocessors.google_data",
)

# The word that must not describe a backup that still carries its own key.
ENCRYPTION_CLAIMS = ("encrypt", "šifrovan")


def test_the_register_does_not_claim_unencrypted_backups_are_encrypted():
    client = _client()
    for lang in ("en", "cs"):
        html = client.get(f"/subprocessors?lang={lang}").text
        for key in REGISTER_BACKUP_KEYS:
            value = SUBPROCESSOR_STRINGS[lang][key]
            assert value in html, (lang, key, "row missing from the rendered page")
            lowered = value.lower()
            for claim in ENCRYPTION_CLAIMS:
                assert claim not in lowered, (lang, key, value)


def test_the_register_records_the_corrective_version():
    client = _client()
    for lang, effective in (("en", "Version 1.1"), ("cs", "Verze 1.1")):
        assert effective in client.get(f"/subprocessors?lang={lang}").text, lang
