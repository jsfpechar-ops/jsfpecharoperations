"""Brief 0705: the v2 shell is opt-in per page; pages without v2 keep the old stylesheets and sidebar.

TODO (brief 0706): once the Overview renders on the v2 shell, add a route-level test that a v2 page
loads app2.css, not host2.css, and has one aside.side with aria-current on the active nav link.
"""

import re
from pathlib import Path

from tests.test_signed_in_chrome import host_with_property  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]


def test_non_v2_dashboard_still_loads_the_old_stylesheets_and_sidebar(host_with_property):
    # Old shell: / is v2 since 0720, so the non-v2 check uses /settings (no set v2).
    page = host_with_property.get("/settings?lang=en").text
    assert "/static/host2.css" in page
    assert "/static/skeleton.css" in page
    assert "app2.css" not in page
    assert 'class="ui-sidebar" id="app-sidebar"' in page
    assert 'class="side" id="app-sidebar"' not in page


def test_v2_branch_is_wired_in_base_html_and_the_v2_shell_exists():
    base = (ROOT / "app/templates/base.html").read_text(encoding="utf-8")
    assert re.search(r"/static/app2\.css\?v=[\w-]+", base)
    assert '{% include "_shell_v2.html" %}' in base
    assert '{% include "_shell_sidebar.html" %}' in base
    shell = (ROOT / "app/templates/_shell_v2.html").read_text(encoding="utf-8")
    assert 'class="side" id="app-sidebar"' in shell
    assert "data-command-open" in shell and 'action="/logout"' in shell


def test_app2_css_has_the_phone_top_bar_rule_and_no_font_picker():
    css = (ROOT / "app/static/app2.css").read_text(encoding="utf-8")
    assert "@media (max-width: 767px)" in css
    assert "fontpick" not in css and "body.f-" not in css
    assert "--acc:#d0452d" in css  # v2 accent token as copied into app2.css (no --coral-600 there)
