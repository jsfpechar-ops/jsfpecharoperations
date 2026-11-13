"""Write go/internal/hostweb/layout/testdata/ from the real Python layout (brief 1380).

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/go_layout_golden.py          write the files
    .venv/bin/python scripts/go_layout_golden.py --check  exit 1 and name each stale file

For each case in CASES it renders GOLDEN_PAGE (a small host_page.html page)
through templating.render with a fixed context and no database, and writes
testdata/<case>.html. It also writes testdata/golden_cases.json with the inputs,
which go/internal/hostweb/layout/layout_test.go reads to render the same page
(testdata/golden_page.html) through layout.render and compare. The comparison
normalises whitespace (see normalise in layout_test.go).

Fixed here so the two sides match: the CSRF token is "GOLDEN-CSRF", the shell
reads (current user, workspace, property list, impersonation minutes) come from
the case, and the parts brief 1381 still has to port (_host_alerts.html,
_billing_banner.html, _havel_panel.html, the security prompt) render empty.
App/tests/test_go_layout_golden.py runs --check in a subprocess (the script
patches module globals, so it never runs inside the pytest process).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "hostweb" / "layout" / "testdata"

# The shell reads these at import; pin them so the files do not depend on the caller.
PINNED_ENV = {
    "UBYHOST_UBYPORT_ENV": "mock",
    "UBYHOST_DEPLOYMENT": "local",
    "UBYHOST_OPERATOR_EMAIL": "",
    "UBYHOST_PUBLIC_BASE_URL": "http://127.0.0.1:8080",
}

GOLDEN_PAGE = """{% extends "host_page.html" %}
{% from "_components.html" import empty_state, progress_pill, row_menu_begin, row_menu_end, copy_button, property_identity, help_tip with context %}
{% block title %}{{ page_title_text }}{% endblock %}
{% block back_url %}{{ back_href }}{% endblock %}
{% block meta %}{{ tp('nav.property_count', 3) }}{% endblock %}
{% block primary_action %}{{ ui_button(t('nav.stays'), 'primary', href='/reservations/new', icon_name='plus') }}{% endblock %}
{% block body %}
{{ ui_badge('done', t('status.reported')) }}
{{ progress_pill('ready', 'immediate') }}
{{ property_identity(5, 'Flat <A> & "B"') }}
{{ empty_state(t('nav.stays'), 'No stays yet.', '/reservations/new', t('common.open')) }}
{{ row_menu_begin() }}{{ ui_menu_item(t('common.open'), href='/x?a=1&b=2') }}{{ row_menu_end() }}
{{ copy_button('link-1') }}
{{ ui_field('name', 'Name', value="O'Brien", help='Your name') }}
{{ help_tip('h1', 'Some <b>help</b> text that is rather long so the truncate filter has to cut it off', '/guide#x') }}
<p>{{ value }}</p>
{% endblock %}
"""

CASES = [
    {
        "name": "legacy_en",
        "url": "/reservations?msg=Saved%20it&toast_kind=success&err=Bank%20missing&fix=bank",
        "cookie": "",
        "v2": False, "nav": "reservations", "body_kind": "list", "how_key": "stays",
        "show_nav": True, "admin_workspace": False, "back_url": "",
        "is_admin": False, "impersonating": False,
        "display_name": "Jana Nováková", "username": "jana-1a2b",
        "deletion_due_at": "2026-12-01T10:00:00", "property_count": 3, "minutes_left": None,
    },
    {
        "name": "v2_cs_impersonating",
        "url": "/apartments/7?lang=cs&undo_stay=12&undo_return=/reservations&saved=1&msg=Hidden",
        "cookie": "",
        "v2": True, "nav": "apartments", "body_kind": "form", "how_key": "",
        "show_nav": True, "admin_workspace": False, "back_url": "/apartments",
        "is_admin": True, "impersonating": True,
        "display_name": "", "username": "host-ab12",
        "deletion_due_at": "", "property_count": 1, "minutes_left": 45,
    },
    {
        "name": "nonav_vi",
        "url": "/settings?toast_kind=warning&toast_sticky=1&msg=Check%20this",
        "cookie": "ubyhost_lang=vi",
        "v2": False, "nav": "settings", "body_kind": "settings", "how_key": "",
        "show_nav": False, "admin_workspace": True, "back_url": "",
        "is_admin": True, "impersonating": True,
        "display_name": "Petr", "username": "petr-9z",
        "deletion_due_at": "", "property_count": 0, "minutes_left": 150,
    },
]

VALUE = "<script>x</script> & 'q'"


def _request(case):
    from starlette.requests import Request

    path, _, query = case["url"].partition("?")
    headers = [(b"host", b"127.0.0.1:8080")]
    if case["cookie"]:
        headers.append((b"cookie", case["cookie"].encode()))
    return Request({
        "type": "http", "method": "GET", "path": path, "raw_path": path.encode(),
        "query_string": query.encode(), "headers": headers, "scheme": "http",
        "server": ("127.0.0.1", 8080), "root_path": "",
    })


def render_case(case) -> str:
    from jinja2 import ChoiceLoader, DictLoader

    from app import access, host_i18n, security, templating

    env = templating.templates.env
    if not isinstance(env.loader, ChoiceLoader):
        env.loader = ChoiceLoader([DictLoader({
            "golden_page.html": GOLDEN_PAGE,
            "_host_alerts.html": "",
            "_billing_banner.html": "",
            "_havel_panel.html": "",
        }), env.loader])
    rows = [{"id": i + 1, "internal_name": f"P{i}", "active": 1, "stay_fee_rate_czk": 0}
            for i in range(case["property_count"])]
    access.apartments = lambda request, columns="*", include_archived=False: list(rows)
    templating.onboarding.progress = lambda owner_user_id: {}
    security.csrf_token = lambda request: "GOLDEN-CSRF"
    templating.security.csrf_token = security.csrf_token
    env.globals["impersonation_minutes_left"] = lambda: case["minutes_left"]
    workspace = {
        "id": 2, "username": case["username"], "display_name": case["display_name"] or None,
        "role": "host", "deletion_due_at": case["deletion_due_at"] or None,
    }
    current = dict(workspace)
    current["role"] = "admin" if case["is_admin"] else "host"
    if case["impersonating"]:
        current.update(id=1, username="admin-1", display_name="Admin")
    request = _request(case)
    lang = host_i18n.resolve_language(request)
    context = {
        "current_user": current, "workspace_user": workspace, "havel_on": False,
        "open_alerts": [], "open_alerts_more": 0, "onboarding": {}, "security_prompt": None,
        "v2": case["v2"], "nav": case["nav"], "body_kind": case["body_kind"],
        "how_key": case["how_key"], "show_nav": case["show_nav"],
        "admin_workspace": case["admin_workspace"], "back_href": case["back_url"],
        "page_title_text": host_i18n.translate(lang, "nav.stays") + " · UbyHost",
        "value": VALUE,
    }
    response = templating.render(request, "golden_page.html", context)
    case["title"] = context["page_title_text"]
    case["set_cookie"] = response.headers.get("set-cookie", "")
    return response.body.decode("utf-8")


def render_all() -> dict[str, str]:
    files = {}
    cases = [dict(c) for c in CASES]
    for case in cases:
        files[f"{case['name']}.html"] = render_case(case)
    files["golden_cases.json"] = json.dumps(
        {"value": VALUE, "cases": cases}, ensure_ascii=False, indent=1, sort_keys=True
    ) + "\n"
    return files


def main(argv: list[str]) -> int:
    check = "--check" in argv
    stale = []
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in render_all().items():
        path = OUT / name
        if path.exists() and path.read_text(encoding="utf-8") == text:
            continue
        if check:
            stale.append(path)
            continue
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path}")
    for path in stale:
        print(f"stale: {path}")
    return 1 if stale else 0


def setup() -> None:
    os.environ.update(PINNED_ENV)
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    if str(APP) not in sys.path:
        sys.path.insert(0, str(APP))


if __name__ == "__main__":
    setup()
    sys.exit(main(sys.argv[1:]))
