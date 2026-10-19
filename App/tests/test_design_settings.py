"""0144: settings group pages render on host_page without inline styles."""
from __future__ import annotations

from tests.test_signed_in_chrome import host_with_property  # noqa: F401

PAGES = {"/settings": "settings", "/settings/archived": "list", "/privacy-requests": "list", "/guide": "detail"}
TEMPLATES = ("settings.html", "settings_archived.html", "privacy_requests.html", "guide.html", "onboarding.html")


def test_settings_pages_have_the_v2_shell(host_with_property):
    for path, kind in PAGES.items():
        response = host_with_property.get(f"{path}?lang=en")
        assert response.status_code == 200, path
        page = response.text
        assert page.count("<h1") == 1 and f'data-body-kind="{kind}"' in page, path
        # Scoped to <main>: base.html's shared confirm dialogs sit after </main>.
        main = page[page.index('id="main-content"'):page.index('</main>')]
        assert 'style="' not in main, path
        assert page.count('class="ui-btn ui-btn-primary') <= 1, path


def test_archive_chips_mark_the_current_type(host_with_property):
    page = host_with_property.get("/settings/archived?type=stays&lang=en").text
    assert page.count('class="ui-chip"') == 5 and page.count('aria-current="true"') >= 1


def test_templates_have_no_raw_style_or_legacy_control():
    for name in TEMPLATES:
        text = open(f"app/templates/{name}", encoding="utf-8").read()
        assert 'style="' not in text and 'class="btn' not in text and 'class="pill' not in text, name
