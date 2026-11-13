"""Write go/internal/hostweb/layout/testdata/ from the real Python layout (briefs 1380, 1381).

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

Fixed here so the two sides match: the CSRF token is "GOLDEN-CSRF", the clock
is 2026-11-13 10:00 in Prague, and the shell reads (current user, workspace,
property list, impersonation minutes, alert rows and their stays, billing row,
Havel state) come from the case. 1381: the alert rows go through the real
alerts.open_alerts, shell_slice and present_many with a stand-in for alerts.db
(stays with no guests), the billing row through billing_trial.banner, and the
security prompt through templating._security_prompt.
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
{% set m = macro_data %}
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
{{ ui_icon_button('Close', 'x', href='/a?x=1') }}
{{ ui_chip('All', href='/r?f=all', selected=true) }}
{{ ui_select('s1', 'Pick', m.options, selected='b', help='Choose one') }}
{{ ui_textarea('t1', 'Note', value='Hi <there>', rows=4, optional=true) }}
{{ ui_check('c1', 'Agree', name='agree', checked=true) }}
{{ ui_toggle('g1', 'On', name='on') }}
{{ ui_menu_begin('More') }}{{ ui_menu_item('Delete', href='/d', danger=true, icon_name='x') }}{{ ui_menu_end() }}
{{ ui_dialog_begin('d1', 'Dialog') }}<p>x</p>{{ ui_dialog_end() }}
{{ ui_empty('Empty', 'Nothing here', 'Add', '/add', tip='A tip') }}
{{ ui_tip('tp1', 'Tip <b>text</b>', 'mailto:help@example.com') }}
{{ ui_pagination(2, 5, '/p?page=1', '/p?page=3', 'Pages', 'More', 'Prev', 'Next', 'Page 2 of 5') }}
{{ ui_pdot(2, 'Second') }}
{{ ui_tabs(m.tabs, 'Sections') }}
{{ ui_toolbar(m.search, m.chips, 'flt', 2, ui_button('Go', 'secondary', href='/go')) }}
{% call ui_section('Sec title', id='sec1', tip='Section tip') %}<p>body</p>{% endcall %}
{{ ui_facts(m.facts) }}
{{ ui_stats(m.stats, 'Stats') }}
{{ ui_banner('warning', 'Careful', 'Fix', '/fix') }}
{{ ui_table_begin(m.columns, 'Table') }}<tr><td>1</td></tr>{{ ui_table_end() }}
{{ ui_card('/c/1', 'L1', 'L2', 'L3', 'Badge', 'Card') }}
{{ ui_skeleton('list') }}
<p>{{ value }}</p>
{% endblock %}
"""

# Lists the ui_* macros above read; the Go page gets the same values as .M.
MACRO_DATA = {
    "options": [["a", "Apple"], ["b", "Banana & <Co>"]],
    "tabs": [["/t/1", "One", True], ["/t/2", "Two", False]],
    "search": ["q", "Search stays", "x\"y"],
    "chips": [["/c?f=1", "First", True], ["/c?f=2", "Second", False]],
    "facts": [["Key", "Value one"], ["Other", "plain"]],  # | safe in Jinja: Go needs template.HTML for markup
    "stats": [["/s/1", "3", "Ready"], ["/s/2", "12", "Waiting"]],
    "columns": [["Name", ""], ["Count", "r"]],
}

# 1381: the clock of the alert, billing and prompt cases (Prague wall time).
NOW_PRAGUE = (2026, 11, 13, 10, 0, 0)


def _stay(rid, date_from, date_to, declared=None, prop="Flat A"):
    return {"id": rid, "date_from": date_from, "date_to": date_to, "declared": declared,
            "override": None, "reduced": None, "property": prop}


def _alert(aid, level, kind, apt=None, res=None, msg="", detail="", params=None, dedupe="", feed="", stay=None):
    return {"id": aid, "level": level, "kind": kind, "apartment_id": apt, "reservation_id": res,
            "dedupe_key": dedupe, "message": msg or f"{kind} (English log copy)", "detail": detail,
            "params": json.dumps(params) if params is not None else "", "feed_property": feed, "stay": stay}


def _many_alerts():
    """Newest first (the SQL order): filing, computed, folded, stored and legacy kinds, past the slice limit."""
    rows = [
        _alert(1, "warning", "guest_pin_rotated", apt=5),
        _alert(2, "critical", "submission_rejected", apt=5, params={"property": "Flat A", "count": 2}),
        _alert(3, "critical", "deadline", apt=5, res=11, detail="stored deadline detail",
               stay=_stay(11, "2026-11-05", "2026-11-09", declared=2)),
        _alert(4, "warning", "headcount_mismatch", apt=5, res=12, stay=_stay(12, "2026-11-12", "2026-11-15", declared=3)),
        _alert(5, "warning", "guest_incomplete_checkin", apt=6, res=13,
               stay=_stay(13, "2026-11-10", "2026-11-14", declared=1, prop="Loft <B>")),
        _alert(6, "warning", "deadline", apt=6, res=13, stay=_stay(13, "2026-11-10", "2026-11-14", declared=1, prop="Loft <B>")),
        _alert(7, "critical", "job_failed", dedupe="job_failed:submit"),
        _alert(8, "warning", "feed_incomplete", apt=6, feed="Loft <B>"),
        _alert(9, "info", "guest_pin_rotated", apt=6),
        _alert(10, "warning", "mail_failed", params={"kind": "reminder_host"}),
        _alert(11, "warning", "guest_question", apt=6, params={"count": 2, "property": "Loft", "variant": "urgent"}),
        _alert(12, "warning", "cancelled_after_report", apt=5, res=14, params={"date": "01.11.2026", "variant": "disappeared"}),
        _alert(13, "warning", "dates_changed_resign", apt=5, res=15, stay=_stay(15, "2026-11-20", "2026-11-22")),
        _alert(14, "warning", "ttlock_budget", params={"percent": 85}),
        _alert(15, "info", "legacy_kind", msg="Legacy English text only"),
        _alert(16, "warning", "apartment_setup", apt=5, params={}),
    ]
    for i in range(8):
        rows.append(_alert(20 + i, "info", "controller_missing", apt=30 + i, params={"property": f"P{i}"}))
    return rows


_ACCOUNT_DONE = {"two_factor_prompted_at": "2026-01-01T00:00:00", "totp_enabled": 0, "signup_at": None}
_ACCOUNT_NEW = {"two_factor_prompted_at": None, "totp_enabled": 0, "signup_at": "2026-01-01T00:00:00"}

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

CASE_DEFAULTS = {
    "signed_in": True, "alerts": [], "billing_on": False, "billing": None,
    "havel_on": False, "havel_state": "", "account": _ACCOUNT_DONE,
    "celebration": "", "sent_guest_count": 0,
    "hide_alert_stack": False, "alerts_expanded": False, "ph_hide_pin": False,
}

_HOST = {
    "cookie": "", "v2": False, "body_kind": "list", "how_key": "", "show_nav": True,
    "admin_workspace": False, "back_url": "", "is_admin": False, "impersonating": False,
    "display_name": "Jana", "username": "jana-1a2b", "deletion_due_at": "", "property_count": 2,
    "minutes_left": None,
}

CASES += [
    dict(_HOST, name="alerts_dashboard_cs", url="/?lang=cs", nav="dashboard", alerts=_many_alerts(),
         billing_on=True, billing={"status": "trialing", "plan": None, "trial_ends_at": "2026-11-15T00:00:00", "period_end": None},
         havel_on=True, account=_ACCOUNT_NEW, celebration="first_guest", sent_guest_count=1),
    dict(_HOST, name="alerts_invoices_en", url="/invoices", nav="invoices", alerts=_many_alerts(),
         billing_on=True, billing={"status": "overdue", "plan": "standard", "trial_ends_at": None, "period_end": None},
         havel_on=True, havel_state="limit_week"),
    dict(_HOST, name="alerts_reservations_scope", url="/reservations?apartment=1&apartment=5", nav="reservations",
         alerts=_many_alerts(), ph_hide_pin=True,
         billing_on=True, billing={"status": "canceling", "plan": "max", "trial_ends_at": None, "period_end": "2026-12-31T00:00:00"}),
    dict(_HOST, name="property_err_minutes0", url="/apartments/7?sec=bank&err=E", nav="apartments",
         impersonating=True, is_admin=True, minutes_left=0, havel_on=True,
         alerts=[_alert(40, "warning", "feed_error", apt=7, params={"feed": "Airbnb"})]),
    dict(_HOST, name="v2_alerts_hidden", url="/reservations/11", nav="reservations", v2=True, alerts=_many_alerts()),
    dict(_HOST, name="visitor_cenik", url="/cenik?lang=vi&msg=x&toast_kind=error&fix=nope", nav="",
         signed_in=False, show_nav=True, property_count=0),
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


class _AlertDB:
    """alerts.db for one case: the alert rows, their stays and feed property names."""

    def __init__(self, rows, real):
        self.rows, self.DecryptionError = rows, real.DecryptionError

    def query(self, sql, params=()):
        if "FROM alert" in sql:
            return [{k: v for k, v in r.items() if k not in ("stay", "feed_property")} for r in self.rows]
        wanted = set(params)
        stays = {}
        for r in self.rows:
            s = r["stay"]
            if s and s["id"] in wanted:
                stays[s["id"]] = {"id": s["id"], "apartment_id": r["apartment_id"], "date_from": s["date_from"],
                                  "date_to": s["date_to"], "declared_guests": s["declared"],
                                  "expected_guests_override": s["override"], "lead_reduced_guests": s["reduced"],
                                  "internal_name": s["property"]}
        return list(stays.values())

    def query_one(self, sql, params=()):
        if "FROM apartment WHERE id" in sql:
            for r in self.rows:
                if r["apartment_id"] == params[0] and r["feed_property"]:
                    return {"internal_name": r["feed_property"]}
            return None
        rows = self.query(sql, params)
        return rows[0] if rows else None


def _pin_clock():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app import billing_trial, deadlines

    fixed = datetime(*NOW_PRAGUE)
    real_local_now = getattr(deadlines, "_golden_real_local_now", deadlines.local_now)
    deadlines._golden_real_local_now = real_local_now
    deadlines.local_now = lambda now=None: fixed if now is None else real_local_now(now)

    class _Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            aware = fixed.replace(tzinfo=ZoneInfo("Europe/Prague"))
            return aware.astimezone(tz) if tz else fixed

    billing_trial.datetime = _Clock
    from app import templating
    templating.datetime = _Clock


def render_case(case) -> str:
    from jinja2 import ChoiceLoader, DictLoader

    from app import access, alerts, auth, billing, db, host_i18n, reporting, security, templating

    for key, value in CASE_DEFAULTS.items():
        case.setdefault(key, value)
    _pin_clock()

    env = templating.templates.env
    if not isinstance(env.loader, ChoiceLoader):
        env.loader = ChoiceLoader([DictLoader({
            "golden_page.html": GOLDEN_PAGE,
        }), env.loader])
    alerts.db = _AlertDB(case["alerts"], db)
    reporting.preload_guests = lambda reservations: {r["id"]: [] for r in reservations}
    auth.accounts_exist = lambda: True
    billing.enabled = lambda: case["billing_on"]
    billing.account = lambda owner_user_id: dict(case["billing"]) if case["billing"] else None
    state = (case["havel_state"] or None) if case["havel_on"] else "off"
    env.globals["havel_panel_state"] = lambda request: {"state": state, "history": "", "sig": ""}
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
    current.update(case["account"])
    if case["impersonating"]:
        current.update(id=1, username="admin-1", display_name="Admin")
    if not case["signed_in"]:
        current = workspace = None
    request = _request(case)
    lang = host_i18n.resolve_language(request)
    context = {
        "current_user": current, "workspace_user": workspace, "havel_on": case["havel_on"],
        "onboarding": {}, "macro_data": MACRO_DATA,
        "celebration_milestone": case["celebration"] or None, "sent_guest_count": case["sent_guest_count"],
        "hide_alert_stack": case["hide_alert_stack"], "alerts_expanded": case["alerts_expanded"],
        "ph_hide_pin": case["ph_hide_pin"],
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
        {"value": VALUE, "macro_data": MACRO_DATA, "cases": cases}, ensure_ascii=False, indent=1, sort_keys=True
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
