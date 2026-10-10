"""MK-1: the public site must never ship a tracker, pixel or third-party asset.

Review M-1/M-5: UbyHost loads no analytics, ad pixels, tag managers, heatmaps or
CDN fonts, and the CSP blocks third-party scripts except Turnstile. This test is
the guardrail: adding Google Analytics, a Meta pixel, a CDN font or a chat widget
fails CI here, and widening the CSP fails the exact-string assertion (which MK-5
requires be changed in the same PR as any CMP).

WP09: PostHog may appear on the public marketing and legal pages, but only when
POSTHOG_PROJECT_API_KEY is set and the EU hosts are valid. They are unset here,
so this contract still holds; tests/test_umami_guard.py covers the configured case.
"""
from __future__ import annotations

import re

import pytest
from starlette.testclient import TestClient

from app import db
from app.main import app
from app.public_guides import GUIDE_TRANSLATIONS

EXPECTED_CSP = (
    "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
    "form-action 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
    "script-src 'self' 'unsafe-inline' https://challenges.cloudflare.com; "
    "frame-src https://challenges.cloudflare.com; "
    "connect-src 'self' https://challenges.cloudflare.com"
)

# The only non-essential-storage-free external origin the public site may use.
TURNSTILE_ORIGIN = "https://challenges.cloudflare.com"

# The only cookies the public pages may set (FE-4 will move this to
# cookie_inventory; until then it is the contract).
PUBLIC_COOKIES = {"ubyhost_lang", "ubyhost_csrf"}

GUIDE_SLUGS = sorted(GUIDE_TRANSLATIONS["en"].keys())

PUBLIC_PATHS = [
    "/",
    "/jak-to-funguje",
    "/cenik",
    *[f"/pruvodce/{slug}" for slug in GUIDE_SLUGS],
    "/legal",
    "/terms",
    "/privacy",
    "/dpa",
    "/subprocessors",
    "/login",
]

RESOURCE_RE = re.compile(
    r"<(?:script|link|img|iframe)\b[^>]*?\b(?:src|href)=\"([^\"]+)\"", re.IGNORECASE
)


def _client() -> TestClient:
    db.init_db()
    return TestClient(app)


def _cookie_names(response) -> set[str]:
    names = set()
    for header in response.headers.get_list("set-cookie"):
        match = re.match(r"\s*([^=;]+)=", header)
        if match:
            names.add(match.group(1).strip())
    return names


def _allowed(url: str) -> bool:
    if url.startswith(("/", "#", "")) or url.startswith("data:"):
        return True
    return url.startswith(TURNSTILE_ORIGIN)


@pytest.mark.parametrize("lang", ("cs", "en"))
@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_public_pages_set_only_necessary_cookies_and_load_no_third_party_assets(
    path, lang
):
    response = _client().get(f"{path}?lang={lang}")
    assert response.status_code == 200, (path, lang, response.status_code)

    assert _cookie_names(response) <= PUBLIC_COOKIES, (path, lang, _cookie_names(response))

    for url in RESOURCE_RE.findall(response.text):
        assert _allowed(url), f"{path} ({lang}) loads a third-party asset: {url}"


@pytest.mark.parametrize("lang", ("cs", "en"))
def test_the_csp_is_exactly_the_reviewed_policy(lang):
    response = _client().get(f"/?lang={lang}")
    assert response.headers.get("content-security-policy") == EXPECTED_CSP
