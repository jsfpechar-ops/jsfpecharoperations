"""WP09 guard: Umami only on the public marketing and legal pages.

Permanent rule (plan README, rule 6): no analytics or third-party script on app
pages, guest pages (``/l/...``, including ``pick.html``) or auth pages. With
Umami fully configured, this renders the app and fails if the tag, the website
ID or the Umami origin reaches any of those pages or their CSP, or if a
template other than the allowed public shells can pull the tag in.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import analytics, config, db
from app.main import _CSP, app
from app.public_guides import GUIDE_TRANSLATIONS
from tests import test_host_guest_form as hg

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"

# Placeholders only. The script host is a stand-in on purpose, so the test
# proves the CSP is derived from config and not hard-coded.
WEBSITE_ID = "00000000-0000-4000-8000-000000000000"
SCRIPT_URL = "https://analytics.example.invalid/script.js"
SCRIPT_ORIGIN = "https://analytics.example.invalid"
HOST_URL = "https://events.example.invalid"

# The page shells allowed to include _umami.html. Every public page extends or
# is one of these.
ALLOWED_SHELLS = {
    "landing.html",
    "product.html",
    "pricing.html",
    "public_guide.html",
    "public_legal_base.html",
}

PUBLIC_PATHS = [
    "/",
    "/jak-to-funguje",
    "/cenik",
    f"/pruvodce/{sorted(GUIDE_TRANSLATIONS['en'])[0]}",
    "/legal",
    "/terms",
    "/privacy",
    "/dpa",
    "/subprocessors",
]

AUTH_PATHS = ["/login", "/login/2fa", "/account/password", "/healthz"]


def _markers(text: str) -> list[str]:
    return [m for m in (WEBSITE_ID, SCRIPT_ORIGIN, HOST_URL, "data-website-id", "umami.is")
            if m in text]


@pytest.fixture
def umami_on(monkeypatch):
    monkeypatch.setattr(config, "UMAMI_WEBSITE_ID", WEBSITE_ID)
    monkeypatch.setattr(config, "UMAMI_SCRIPT_URL", SCRIPT_URL)
    monkeypatch.setattr(config, "UMAMI_HOST_URL", HOST_URL)
    monkeypatch.setattr(config, "UMAMI_DOMAINS", "ubyhost.com,www.ubyhost.com")
    db.init_db()


# --- static: which templates can ever carry the tag -------------------------

def _template_sources() -> dict[str, str]:
    return {
        str(p.relative_to(TEMPLATES)): p.read_text(encoding="utf-8")
        for p in TEMPLATES.rglob("*.html")
    }


def test_only_the_partial_contains_the_tag():
    for name, source in _template_sources().items():
        if name == "_umami.html":
            continue
        assert "data-website-id" not in source, name
        assert "umami.is" not in source, name
        assert "umami_tag." not in source, name


def test_only_the_public_shells_include_the_partial():
    including = {
        name for name, source in _template_sources().items()
        if re.search(r"""include\s+["']_umami\.html["']""", source)
    }
    assert including == ALLOWED_SHELLS


def test_every_template_that_reaches_the_partial_is_a_public_page():
    """Follow extends/include edges: nothing app, guest or auth reaches it."""
    sources = _template_sources()
    edges = {
        name: set(re.findall(r"""(?:extends|include)\s+["']([^"']+)["']""", src))
        for name, src in sources.items()
    }

    def reaches(name: str, seen=None) -> bool:
        seen = seen or set()
        if name in seen:
            return False
        seen.add(name)
        return any(t == "_umami.html" or reaches(t, seen) for t in edges.get(name, ()))

    reaching = {n for n in sources if n != "_umami.html" and reaches(n)}
    allowed = ALLOWED_SHELLS | (analytics.PUBLIC_ANALYTICS_TEMPLATES)
    assert reaching <= allowed, sorted(reaching - allowed)
    assert not any(n.startswith("guest/") for n in reaching)
    for name in ("base.html", "auth_base.html", "login.html", "error.html"):
        assert name not in reaching, name


def test_the_allowed_page_templates_are_public_only():
    assert analytics.PUBLIC_ANALYTICS_TEMPLATES.isdisjoint(
        {"base.html", "auth_base.html", "login.html", "error.html", "dashboard.html"}
    )
    assert not any(n.startswith("guest/") for n in analytics.PUBLIC_ANALYTICS_TEMPLATES)


# --- rendered: public pages carry it, everything else does not -------------

def test_nothing_is_rendered_and_the_csp_is_strict_while_unconfigured(monkeypatch):
    monkeypatch.setattr(config, "UMAMI_WEBSITE_ID", "")
    monkeypatch.setattr(config, "UMAMI_SCRIPT_URL", SCRIPT_URL)
    db.init_db()
    client = TestClient(app)
    for path in PUBLIC_PATHS:
        response = client.get(path)
        assert response.status_code == 200, path
        assert not _markers(response.text), path
        assert response.headers["content-security-policy"] == _CSP, path


def test_a_non_https_script_url_is_refused(monkeypatch):
    monkeypatch.setattr(config, "UMAMI_WEBSITE_ID", WEBSITE_ID)
    monkeypatch.setattr(config, "UMAMI_SCRIPT_URL", "http://analytics.example.invalid/s.js")
    assert not analytics.enabled()
    assert analytics.tag() is None


@pytest.mark.parametrize("lang", ("cs", "en"))
@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_public_pages_carry_the_tag_and_a_matching_csp(umami_on, path, lang):
    response = TestClient(app).get(f"{path}?lang={lang}")
    assert response.status_code == 200, path
    html = response.text
    assert f'src="{SCRIPT_URL}"' in html
    assert f'data-website-id="{WEBSITE_ID}"' in html
    assert 'data-domains="ubyhost.com,www.ubyhost.com"' in html
    assert f'data-host-url="{HOST_URL}"' in html
    for attr in ("data-do-not-track", "data-exclude-search", "data-exclude-hash"):
        assert f'{attr}="true"' in html, attr
    assert html.count("data-website-id") == 1
    csp = response.headers["content-security-policy"]
    script_src = re.search(r"script-src ([^;]+)", csp).group(1).split()
    connect_src = re.search(r"connect-src ([^;]+)", csp).group(1).split()
    assert SCRIPT_ORIGIN in script_src
    assert SCRIPT_ORIGIN in connect_src and HOST_URL in connect_src
    assert HOST_URL not in script_src


def test_cloud_script_without_host_url_allows_the_cloud_gateway(monkeypatch):
    monkeypatch.setattr(config, "UMAMI_WEBSITE_ID", WEBSITE_ID)
    monkeypatch.setattr(config, "UMAMI_SCRIPT_URL", "https://cloud.umami.is/script.js")
    monkeypatch.setattr(config, "UMAMI_HOST_URL", "")
    assert analytics.connect_origins() == (
        "https://cloud.umami.is",
        analytics.UMAMI_CLOUD_DEFAULT_ENDPOINT,
    )


def test_the_events_carry_no_properties(umami_on):
    client = TestClient(app)
    landing = client.get("/?lang=en").text
    assert landing.count('data-umami-event="login_click"') >= 2
    assert 'data-umami-event="contact_click"' in landing  # footer mailto
    pricing = client.get("/cenik?lang=en").text
    assert 'data-umami-event="contact_click"' in pricing
    for html in (landing, pricing):
        # data-umami-event-<name> would attach a property; none is allowed.
        assert not re.search(r"data-umami-event-[\w-]+=", html)


def test_privacy_and_subprocessors_describe_umami(umami_on):
    client = TestClient(app)
    for lang, needle in (("en", "Act No. 127/2005 Coll."), ("cs", "zákona č. 127/2005 Sb.")):
        privacy = client.get(f"/privacy?lang={lang}").text
        assert "Umami Cloud" in privacy and needle in privacy, lang
        register = client.get(f"/subprocessors?lang={lang}").text
        assert "Umami Software, Inc. (Umami Cloud)" in register, lang


def test_the_tag_attributes_follow_the_legal_configuration(umami_on):
    """Section 1 of the legal positions: every privacy attribute, nothing more."""
    html = TestClient(app).get("/?lang=en").text
    tag = re.search(r"<script defer src=\"[^\"]+\"[^>]*></script>", html).group(0)
    attrs = dict(re.findall(r'(data-[\w-]+)="([^"]*)"', tag))
    assert attrs == {
        "data-website-id": WEBSITE_ID,
        "data-domains": "ubyhost.com,www.ubyhost.com",
        "data-host-url": HOST_URL,
        "data-do-not-track": "true",
        "data-exclude-search": "true",
        "data-exclude-hash": "true",
    }


def test_the_domains_default_to_the_public_base_url(umami_on, monkeypatch):
    monkeypatch.setattr(config, "UMAMI_DOMAINS", "")
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "https://placeholder.example.invalid")
    assert analytics.tag()["domains"] == "placeholder.example.invalid"
    html = TestClient(app).get("/?lang=en").text
    assert 'data-domains="placeholder.example.invalid"' in html


# --- opt-out on /privacy -----------------------------------------------------

OPTOUT_SCRIPT = "/static/umami-optout.js"
OPTOUT_TEXT = {
    "en": ("Turn off measurement in this browser", "Turn measurement back on"),
    "cs": ("Vypnout měření v tomto prohlížeči", "Znovu zapnout měření"),
}


@pytest.mark.parametrize("lang", ("cs", "en"))
def test_privacy_offers_the_opt_out_and_opt_back_in(umami_on, lang):
    response = TestClient(app).get(f"/privacy?lang={lang}")
    html = response.text
    off, on = OPTOUT_TEXT[lang]
    assert 'id="analytics-optout"' in html
    assert 'data-optout-action="disable"' in html and off in html
    assert 'data-optout-action="enable"' in html and on in html
    assert f'src="{OPTOUT_SCRIPT}' in html
    # A same-origin script: the public CSP needs no inline allowance for it.
    assert "'self'" in re.search(r"script-src ([^;]+)", response.headers["content-security-policy"]).group(1)


def test_the_opt_out_script_toggles_the_umami_key():
    source = (Path(__file__).resolve().parents[1] / "app" / "static" / "umami-optout.js").read_text(
        encoding="utf-8"
    )
    assert 'var KEY = "umami.disabled"' in source
    assert "localStorage.setItem(KEY" in source and "localStorage.removeItem(KEY" in source


def test_only_the_privacy_page_loads_the_opt_out_script():
    loading = {
        name for name, source in _template_sources().items() if "umami-optout.js" in source
    }
    assert loading == {"privacy.html"}


def test_no_opt_out_while_umami_is_unconfigured(monkeypatch):
    monkeypatch.setattr(config, "UMAMI_WEBSITE_ID", "")
    db.init_db()
    html = TestClient(app).get("/privacy?lang=en").text
    assert 'id="analytics-optout"' not in html
    assert OPTOUT_SCRIPT not in html


def test_other_public_pages_carry_no_opt_out(umami_on):
    client = TestClient(app)
    for path in PUBLIC_PATHS:
        if path == "/privacy":
            continue
        html = client.get(f"{path}?lang=en").text
        assert OPTOUT_SCRIPT not in html, path
        assert 'id="analytics-optout"' not in html, path


@pytest.mark.parametrize("path", AUTH_PATHS)
def test_auth_pages_never_carry_umami(umami_on, path):
    response = TestClient(app).get(path, follow_redirects=True)
    assert not _markers(response.text), (path, _markers(response.text))
    assert response.headers.get("content-security-policy") == _CSP, path


def test_app_and_guest_pages_never_carry_umami(umami_on):
    owner_id, stay_id = hg._host_stay()
    try:
        host = hg._host_client(owner_id)
        app_paths = [
            "/",  # the dashboard when signed in, not the landing page
            "/reservations",
            f"/reservations/{stay_id}",
            "/apartments",
            "/housebook",
            "/settings",
            "/admin/users",
            "/admin/incidents",
            # A signed-in host on the guest form is still a guest page.
            f"/l/{hg.TOKEN}/{stay_id}",
        ]
        for path in app_paths:
            response = host.get(path, follow_redirects=True)
            assert response.status_code < 500, path
            assert not _markers(response.text), (path, _markers(response.text))
            assert response.headers.get("content-security-policy") == _CSP, path
        assert "data-website-id" not in host.get("/").text

        # An anonymous guest: the PIN page, the claimed form and the privacy note.
        anonymous = TestClient(app)
        for path in (f"/l/{hg.TOKEN}", f"/l/{hg.TOKEN}/{stay_id}", f"/l/{hg.TOKEN}/privacy"):
            response = anonymous.get(path, follow_redirects=True)
            assert response.status_code < 500, path
            assert not _markers(response.text), (path, _markers(response.text))
            assert response.headers.get("content-security-policy") == _CSP, path
        guest = hg._claimed_guest(stay_id)
        for path in (f"/l/{hg.TOKEN}/{stay_id}", f"/l/{hg.TOKEN}/{stay_id}/new"):
            response = guest.get(path, follow_redirects=True)
            assert response.status_code < 500, path
            assert not _markers(response.text), (path, _markers(response.text))
            assert response.headers.get("content-security-policy") == _CSP, path
    finally:
        hg._cleanup()
