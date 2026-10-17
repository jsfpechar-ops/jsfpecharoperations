"""WP09 guard: PostHog only on the public marketing and legal pages.

Permanent rule (plan README, rule 6): no analytics or third-party script on app
pages, guest pages (``/l/...``, including ``pick.html``) or auth pages. With
PostHog fully configured, this renders the app and fails if the tag, the API key
or the PostHog origins reach any of those pages or their CSP, or if a template
other than the allowed public shells can pull the tag in.
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
STATIC = Path(__file__).resolve().parents[1] / "app" / "static"

# Placeholders only. The hosts are stand-ins so the test proves the CSP is
# derived from config and not hard-coded.
API_KEY = "phc_test"
API_HOST = "https://analytics.example.invalid"
ASSETS_HOST = "https://assets.example.invalid"

# The page shells allowed to include _posthog.html. Every public page extends or
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

STRIP_KEYS = ("gclid", "fbclid", "ttclid", "click", "token", "email")


def _markers(text: str) -> list[str]:
    return [
        m
        for m in (API_KEY, API_HOST, ASSETS_HOST, "posthog.init", "posthog")
        if m in text
    ]


@pytest.fixture
def posthog_on(monkeypatch):
    monkeypatch.setattr(config, "POSTHOG_PROJECT_API_KEY", API_KEY)
    monkeypatch.setattr(config, "POSTHOG_HOST", API_HOST)
    monkeypatch.setattr(config, "POSTHOG_ASSETS_HOST", ASSETS_HOST)
    db.init_db()


# --- static: which templates can ever carry the tag -------------------------

def _template_sources() -> dict[str, str]:
    return {
        str(p.relative_to(TEMPLATES)): p.read_text(encoding="utf-8")
        for p in TEMPLATES.rglob("*.html")
    }


def test_only_the_partial_contains_the_tag():
    for name, source in _template_sources().items():
        if name == "_posthog.html":
            continue
        assert "posthog.init" not in source, name
        assert "array.js" not in source, name
        assert "analytics_tag." not in source, name


def test_only_the_public_shells_include_the_partial():
    including = {
        name
        for name, source in _template_sources().items()
        if re.search(r"""include\s+["']_posthog\.html["']""", source)
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
        return any(t == "_posthog.html" or reaches(t, seen) for t in edges.get(name, ()))

    reaching = {n for n in sources if n != "_posthog.html" and reaches(n)}
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


def test_the_snippet_strips_sensitive_query_keys():
    source = (TEMPLATES / "_posthog.html").read_text(encoding="utf-8")
    for key in STRIP_KEYS:
        assert key in source


def test_the_snippet_locks_the_privacy_settings():
    source = (TEMPLATES / "_posthog.html").read_text(encoding="utf-8")
    for needle in (
        "advanced_disable_flags: true",
        "disable_surveys: true",
        "enable_heatmaps: false",
        "capture_dead_clicks: false",
        "capture_exceptions: false",
        "capture_performance: false",
        "disable_external_dependency_loading: true",
        "mask_personal_data_properties: true",
        "disable_session_recording: true",
        "autocapture: false",
    ):
        assert needle in source


def test_templates_and_static_contain_no_identify_call():
    for path in TEMPLATES.rglob("*.html"):
        assert "identify(" not in path.read_text(encoding="utf-8"), path.name
    for path in STATIC.rglob("*.js"):
        assert "identify(" not in path.read_text(encoding="utf-8"), path.name


# --- rendered: public pages carry it, everything else does not -------------

def test_nothing_is_rendered_and_the_csp_is_strict_while_unconfigured(monkeypatch):
    monkeypatch.setattr(config, "POSTHOG_PROJECT_API_KEY", "")
    monkeypatch.setattr(config, "POSTHOG_HOST", API_HOST)
    db.init_db()
    client = TestClient(app)
    for path in PUBLIC_PATHS:
        response = client.get(path)
        assert response.status_code == 200, path
        assert "posthog.init" not in response.text, path
        assert response.headers["content-security-policy"] == _CSP, path


def test_a_non_https_host_is_refused(monkeypatch):
    monkeypatch.setattr(config, "POSTHOG_PROJECT_API_KEY", API_KEY)
    monkeypatch.setattr(config, "POSTHOG_HOST", "http://analytics.example.invalid")
    assert not analytics.enabled()
    assert analytics.tag() is None


def test_us_posthog_hosts_leave_the_tag_off_and_csp_strict(monkeypatch):
    monkeypatch.setattr(config, "POSTHOG_PROJECT_API_KEY", API_KEY)
    monkeypatch.setattr(config, "POSTHOG_HOST", "https://us.i.posthog.com")
    monkeypatch.setattr(config, "POSTHOG_ASSETS_HOST", ASSETS_HOST)
    assert not analytics.enabled()
    db.init_db()
    response = TestClient(app).get("/?lang=en")
    assert "posthog.init" not in response.text
    assert response.headers["content-security-policy"] == _CSP


@pytest.mark.parametrize("lang", ("cs", "en"))
@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_public_pages_carry_the_tag_and_a_matching_csp(posthog_on, path, lang):
    response = TestClient(app).get(f"{path}?lang={lang}")
    assert response.status_code == 200, path
    html = response.text
    assert "posthog.init" in html
    assert API_KEY in html
    assert ASSETS_HOST in html
    assert API_HOST in html
    csp = response.headers["content-security-policy"]
    script_src = re.search(r"script-src ([^;]+)", csp).group(1).split()
    connect_src = re.search(r"connect-src ([^;]+)", csp).group(1).split()
    assert ASSETS_HOST in script_src
    assert API_HOST in connect_src
    assert ASSETS_HOST in connect_src
    assert API_HOST not in script_src


def test_the_events_carry_no_extra_properties(posthog_on):
    client = TestClient(app)
    landing = client.get("/?lang=en").text
    assert landing.count('data-analytics-event="login_click"') >= 2
    assert 'data-analytics-event="contact_click"' in landing  # footer mailto
    pricing = client.get("/cenik?lang=en").text
    assert 'data-analytics-event="contact_click"' in pricing
    for html in (landing, pricing):
        assert not re.search(r"data-analytics-event-[\w-]+=", html)


def test_privacy_and_subprocessors_describe_posthog(posthog_on):
    client = TestClient(app)
    for lang in ("en", "cs"):
        privacy = client.get(f"/privacy?lang={lang}").text
        assert "PostHog" in privacy and "Umami" not in privacy, lang
        register = client.get(f"/subprocessors?lang={lang}").text
        assert "PostHog, Inc. (PostHog Cloud EU)" in register, lang
        assert "Umami" not in register, lang


# --- opt-out on /privacy -----------------------------------------------------

OPTOUT_SCRIPT = "/static/analytics-optout.js"
OPTOUT_TEXT = {
    "en": ("Turn off measurement in this browser", "Turn measurement back on"),
    "cs": ("Vypnout měření v tomto prohlížeči", "Znovu zapnout měření"),
}


@pytest.mark.parametrize("lang", ("cs", "en"))
def test_privacy_offers_the_opt_out_and_opt_back_in(posthog_on, lang):
    response = TestClient(app).get(f"/privacy?lang={lang}")
    html = response.text
    off, on = OPTOUT_TEXT[lang]
    assert 'id="analytics-optout"' in html
    assert 'data-optout-action="disable"' in html and off in html
    assert 'data-optout-action="enable"' in html and on in html
    assert f'src="{OPTOUT_SCRIPT}' in html
    assert "'self'" in re.search(
        r"script-src ([^;]+)", response.headers["content-security-policy"]
    ).group(1)


def test_the_opt_out_script_toggles_the_analytics_key():
    source = (STATIC / "analytics-optout.js").read_text(encoding="utf-8")
    assert 'var KEY = "ubyhost.analytics.disabled"' in source
    assert "localStorage.setItem(KEY" in source and "localStorage.removeItem(KEY" in source


def test_only_the_privacy_page_loads_the_opt_out_script():
    loading = {
        name for name, source in _template_sources().items() if "analytics-optout.js" in source
    }
    assert loading == {"privacy.html"}


def test_no_opt_out_while_posthog_is_unconfigured(monkeypatch):
    monkeypatch.setattr(config, "POSTHOG_PROJECT_API_KEY", "")
    db.init_db()
    html = TestClient(app).get("/privacy?lang=en").text
    assert 'id="analytics-optout"' not in html
    assert OPTOUT_SCRIPT not in html


def test_other_public_pages_carry_no_opt_out(posthog_on):
    client = TestClient(app)
    for path in PUBLIC_PATHS:
        if path == "/privacy":
            continue
        html = client.get(f"{path}?lang=en").text
        assert OPTOUT_SCRIPT not in html, path
        assert 'id="analytics-optout"' not in html, path


@pytest.mark.parametrize("path", AUTH_PATHS)
def test_auth_pages_never_carry_posthog(posthog_on, path):
    response = TestClient(app).get(path, follow_redirects=True)
    assert not _markers(response.text), (path, _markers(response.text))
    assert response.headers.get("content-security-policy") == _CSP, path


def test_the_sign_up_pages_never_carry_umami(posthog_on, monkeypatch):
    # WP20/WP21: /signup reads gclid and fbclid; it is an auth page, no tag.
    monkeypatch.setattr(config, "SIGNUP_ENABLED", True)
    for path in ("/signup?lang=en&gclid=TEST123&fbclid=TEST456", "/signup/verify?t=x"):
        response = TestClient(app).get(path, follow_redirects=True)
        assert not _markers(response.text), (path, _markers(response.text))
        assert response.headers.get("content-security-policy") == _CSP, path


def test_app_and_guest_pages_never_carry_posthog(posthog_on):
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
            f"/l/{hg.TOKEN}/{stay_id}",
        ]
        for path in app_paths:
            response = host.get(path, follow_redirects=True)
            assert response.status_code < 500, path
            assert not _markers(response.text), (path, _markers(response.text))
            assert response.headers.get("content-security-policy") == _CSP, path
        assert "posthog.init" not in host.get("/").text

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
