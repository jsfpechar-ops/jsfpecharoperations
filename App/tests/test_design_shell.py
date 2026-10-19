"""Design v2 shell (MASTER 6): sidebar, top bar, tab bar, More sheet."""
import re

from app import host_i18n
from tests.test_signed_in_chrome import host_with_property  # noqa: F401  (fixture reuse)


def test_signed_in_pages_carry_the_v2_shell_and_not_the_drawer(host_with_property):
    page = host_with_property.get("/?lang=en").text
    assert 'class="ui-sidebar" id="app-sidebar"' in page
    assert 'class="ui-topbar"' in page
    assert "data-nav-toggle" not in page and 'class="appbar"' not in page and "nav-backdrop" not in page
    tabbar = re.search(r'<nav class="ui-tabbar".*?</nav>', page, re.S).group(0)
    assert tabbar.count("<a ") == 5
    assert 'data-sheet-open="more-sheet"' in tabbar
    assert '<dialog id="more-sheet" class="ui-dialog"' in page
    for href in ("/invoices", "/settings", "/guide", "/settings/archived", "/privacy-requests"):
        assert f'class="ui-menu-item" href="{href}"' in page, href


def test_the_sidebar_lists_every_destination_with_a_lucide_icon(host_with_property):
    page = host_with_property.get("/?lang=en").text
    sidebar = re.search(r'<aside class="ui-sidebar".*?</aside>', page, re.S).group(0)
    for href, icon in (("/", "layout-dashboard"), ("/reservations", "calendar-days"), ("/apartments", "house"), ("/invoices", "receipt"),
                       ("/cleaning", "brush-cleaning"), ("/settings", "settings"), ("/guide", "book-open")):
        assert re.search(rf'href="{re.escape(href)}"[^>]*>\s*<svg class="ui-icon"[^>]*data-icon="{icon}"', sidebar), href
    assert sidebar.count('aria-current="page"') == 1
    assert "<path" in sidebar and "hand-drawn" not in sidebar
    assert 'data-sidebar-collapse' in sidebar and 'class="ui-nav sidebar-nav"' in sidebar


def test_navigation_labels_exist_in_both_languages():
    for key in ("nav.cleaning", "nav.more", "nav.admin", "nav.smart_locks"):
        assert host_i18n.STRINGS["en"][key] and host_i18n.STRINGS["cs"][key]
    assert host_i18n.STRINGS["cs"]["nav.more"] == "Další"
