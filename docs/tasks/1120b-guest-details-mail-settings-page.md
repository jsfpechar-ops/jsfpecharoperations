# 1120b: Guest details mail, part b: the switch on the settings page

Status: todo
Depends on: 1120 (the column and `App/app/guest_mail_pref.py` must be in your checkout; if `App/app/guest_mail_pref.py` is missing, STOP) | Base commit: 169ee203 | Branch: task/1120b-guest-details-mail-settings-page
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Split note: second half of the plan's brief 1120, see [1120](1120-guest-details-mail-setting.md).

## 1. Objective

Add one switch, "Guest details in the confirmation e-mail", to Settings > Account, next to the two existing e-mail switches, with a plain form POST that works without JavaScript. This is host UI, so the UX gate (AGENTS rule 10) is part of this brief.

## 2. Context

Design rules that apply (docs/design/design-system.md section 1, rules 5 and 7; grep `^5\.\|^7\.` there if you want the text): one Save per form (the existing switches use a `<noscript>` Save), and help text goes under the "?" not as fine print. The existing toggle row partial is reused verbatim (`App/app/templates/partials/settings_toggle_row.html`, takes `label`, `help_id`, `help_text`, `control`). Light mode only, no new CSS, no `style=""`. CSRF is added by the app's middleware for every form POST, as for the neighbouring forms (they carry no hidden field).

Copy rule (AGENTS rule 9): the label is the switch, the help "?" holds the one explanation; no extra sentence on the page.

Anchor 1, `App/app/templates/settings.html` (lines 77-83):
```
        {% if stay_fee_emails is not none %}
          <form method="post" action="/account/stay-fee-emails" class="settings-toggle-form" id="settings-stay-fee-emails">
            {% set control %}<input type="checkbox" name="enabled" value="1" data-toggle-submit aria-label="{{ t('settings.account.stay_fee_emails') }}"{% if stay_fee_emails %} checked{% endif %}>{% endset %}
            {% with label=t('settings.account.stay_fee_emails'), help_id='settings-stay-fee-emails-help', help_text=t('settings.account.stay_fee_emails_help'), control=control %}{% include "partials/settings_toggle_row.html" %}{% endwith %}
            <noscript><button class="ui-btn ui-btn-secondary ui-btn-compact" type="submit">{{ t('settings.account.stay_fee_emails_save') }}</button></noscript>
          </form>
        {% endif %}
```
Anchor 2, `App/app/routes/admin.py` (the context dict, one line) and the helper it calls:
```
            "stay_fee_emails": _stay_fee_emails(request),
```
```
def _stay_fee_emails(request: Request):
    """The "Stay fee report by e-mail" toggle: True or False, None when hidden.

    Same guards as the onboarding switch, and hidden without a fee property.
    """
    account = auth.current_user(request)
    workspace = auth.workspace_user(request)
    if not account or account["role"] != "host":
        return None
    if workspace and workspace["id"] != account["id"]:
        return None
    if not stay_fee_auto.workspace_has_fee_property(account["id"]):
        return None
    return stay_fee_auto.emails_enabled(account["id"])


def _backup_status(request: Request):
```
Anchor 3, `App/app/routes/admin_accounts.py` (the neighbouring POST route, its last lines):
```
    form = await request.form()
    wanted = str(form.get("enabled", "")) == "1"
    stay_fee_auto.set_emails_enabled(int(account["id"]), wanted, actor=account["username"])
    key = "flash.accounts.stay_fee_emails_on" if wanted else "flash.accounts.stay_fee_emails_off"
    return _back("/settings/account#settings-stay-fee-emails", msg=_flash(request, key))
```
The import blocks: `App/app/routes/admin_accounts.py` has `    havel,\n    host_i18n,\n    incidents,` and `App/app/routes/admin.py` has `    stay_fee_auto,\n    ttlock,`.
Anchor 4, `App/app/host_i18n.py`: the English block ends the stay-fee strings with `        "flash.accounts.stay_fee_emails_off": "Stay fee emails are off. Confirm each period on the Stay fee page.",` and the Czech block with `        "flash.accounts.stay_fee_emails_off": "E-maily s hlášením jsou vypnuté. Každé období potvrďte na stránce Poplatek z pobytu.",`.

If an excerpt is not found verbatim, STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/routes/admin_accounts.py | edit | import + POST `/account/guest-details-mail` |
| App/app/routes/admin.py | edit | import + `_guest_details_mail` + context entry |
| App/app/templates/settings.html | edit | the switch row |
| App/app/host_i18n.py | edit | English and Czech strings |
| App/tests/test_guest_mail_pref_settings.py | create | page and POST tests |

No other file may change. (Vietnamese: `host_vi_i18n.py` is not edited; a missing Vietnamese key is assumed to fall back to English like other recent strings. Say in the report if a test says otherwise.)

## 4. Steps

1. `App/app/routes/admin_accounts.py`, imports: replace
```
    havel,
    host_i18n,
    incidents,
```
with
```
    guest_mail_pref,
    havel,
    host_i18n,
    incidents,
```
Command: `cd App && .venv/bin/python -c "import app.routes.admin_accounts" 2>&1 | tail -30`. Expected: no output.

2. `App/app/routes/admin_accounts.py`, after the last line of the anchor 3 block (`    return _back("/settings/account#settings-stay-fee-emails", msg=_flash(request, key))`), add two blank lines and:
```python
@router.post("/account/guest-details-mail")
async def guest_details_mail_submit(request: Request):
    """The Settings switch "Guest details in the confirmation e-mail" (brief 1120b).

    Only the workspace owner changes it, as for the stay fee switch.
    """
    account = auth.current_user(request)
    if not account:
        return RedirectResponse("/login", status_code=303)
    workspace = auth.workspace_user(request)
    if account["role"] != "host" or (workspace and workspace["id"] != account["id"]):
        return _back("/settings/account#settings-guest-details-mail")
    form = await request.form()
    wanted = str(form.get("enabled", "")) == "1"
    guest_mail_pref.set_full_details(int(account["id"]), wanted, actor=account["username"])
    key = "flash.accounts.guest_details_mail_on" if wanted else "flash.accounts.guest_details_mail_off"
    return _back("/settings/account#settings-guest-details-mail", msg=_flash(request, key))
```
Command: `cd App && .venv/bin/python -c "import app.routes.admin_accounts" 2>&1 | tail -30`. Expected: no output.

3. `App/app/routes/admin.py`, imports: replace `    stay_fee_auto,\n    ttlock,` (two lines) with `    stay_fee_auto,\n    guest_mail_pref,\n    ttlock,`.
Command: `cd App && .venv/bin/python -c "import app.routes.admin" 2>&1 | tail -30`. Expected: no output.

4. `App/app/routes/admin.py`, helper: replace the line `def _backup_status(request: Request):` (it appears once) with
```python
def _guest_details_mail(request: Request):
    """The "Guest details in the confirmation e-mail" switch: True or False, None when hidden.

    Same guards as the onboarding switch: a host, on their own account, no preview.
    """
    account = auth.current_user(request)
    workspace = auth.workspace_user(request)
    if not account or account["role"] != "host":
        return None
    if workspace and workspace["id"] != account["id"]:
        return None
    return guest_mail_pref.switch_on(account["id"])


def _backup_status(request: Request):
```
Command: `cd App && grep -n "def _guest_details_mail" app/routes/admin.py | tail -30`. Expected: one line.

5. `App/app/routes/admin.py`, context: replace `            "stay_fee_emails": _stay_fee_emails(request),` with
```
            "stay_fee_emails": _stay_fee_emails(request),
            "guest_details_mail": _guest_details_mail(request),
```
Command: `cd App && .venv/bin/python -c "import app.routes.admin" 2>&1 | tail -30`. Expected: no output.

6. `App/app/templates/settings.html`: replace the line
```
            <noscript><button class="ui-btn ui-btn-secondary ui-btn-compact" type="submit">{{ t('settings.account.stay_fee_emails_save') }}</button></noscript>
          </form>
        {% endif %}
```
with the same three lines followed by
```
        {% if guest_details_mail is not none %}
          <form method="post" action="/account/guest-details-mail" class="settings-toggle-form" id="settings-guest-details-mail">
            {% set control %}<input type="checkbox" name="enabled" value="1" data-toggle-submit aria-label="{{ t('settings.account.guest_details_mail') }}"{% if guest_details_mail %} checked{% endif %}>{% endset %}
            {% with label=t('settings.account.guest_details_mail'), help_id='settings-guest-details-mail-help', help_text=t('settings.account.guest_details_mail_help'), control=control %}{% include "partials/settings_toggle_row.html" %}{% endwith %}
            <noscript><button class="ui-btn ui-btn-secondary ui-btn-compact" type="submit">{{ t('settings.account.guest_details_mail_save') }}</button></noscript>
          </form>
        {% endif %}
```
Command: `grep -n "guest_details_mail" App/app/templates/settings.html | tail -30`. Expected: five matching lines.

7. `App/app/host_i18n.py`, English: after the line `        "flash.accounts.stay_fee_emails_off": "Stay fee emails are off. Confirm each period on the Stay fee page.",` add
```
        "settings.account.guest_details_mail": "Guest details in the confirmation e-mail",
        "settings.account.guest_details_mail_help": "Date of birth, address and the last 4 digits of the document number. Off: names only.",
        "settings.account.guest_details_mail_save": "Save",
        "flash.accounts.guest_details_mail_on": "Guest details are in the confirmation e-mail.",
        "flash.accounts.guest_details_mail_off": "The confirmation e-mail shows names only.",
```

8. `App/app/host_i18n.py`, Czech: after the line `        "flash.accounts.stay_fee_emails_off": "E-maily s hlášením jsou vypnuté. Každé období potvrďte na stránce Poplatek z pobytu.",` add
```
        "settings.account.guest_details_mail": "Údaje o hostech v potvrzovacím e-mailu",
        "settings.account.guest_details_mail_help": "Datum narození, adresa a poslední 4 číslice čísla dokladu. Vypnuto: jen jména.",
        "settings.account.guest_details_mail_save": "Uložit",
        "flash.accounts.guest_details_mail_on": "Potvrzovací e-mail obsahuje údaje o hostech.",
        "flash.accounts.guest_details_mail_off": "Potvrzovací e-mail obsahuje jen jména.",
```
Command (after 7 and 8): `cd App && .venv/bin/python -c "from app import host_i18n as h; print(h.STRINGS['cs']['settings.account.guest_details_mail'])" 2>&1 | tail -30`. Expected: the Czech label. If `STRINGS` has another shape, STOP and report the error (do not guess).

9. Create `App/tests/test_guest_mail_pref_settings.py` with exactly:
```python
"""1120b: the guest-details mail switch on Settings > Account."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, db, guest_mail_pref
from app.main import app
from tests.conftest import login_as

USERNAME = "guest-mail-pref-page"


def _cleanup():
    for user in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user["id"],))
        db.execute("DELETE FROM user_account WHERE id = ?", (user["id"],))


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    owner_id = auth.create_account(
        "guest-mail-pref-page@example.test", "Pref Page", role="host", username=USERNAME
    )
    client = TestClient(app)
    logged_in = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert logged_in.status_code == 303
    try:
        yield client, owner_id
    finally:
        _cleanup()


def test_the_row_is_shown_and_checked_by_default(host):
    client, _owner_id = host
    page = client.get("/settings/account?lang=en")
    assert page.status_code == 200
    assert 'id="settings-guest-details-mail"' in page.text
    form = page.text.split('id="settings-guest-details-mail"', 1)[1].split("</form>", 1)[0]
    assert "Guest details in the confirmation e-mail" in form
    assert " checked" in form
    assert "<noscript><button" in form


def test_the_row_is_in_czech(host):
    client, _owner_id = host
    page = client.get("/settings/account?lang=cs")
    assert "Údaje o hostech v potvrzovacím e-mailu" in page.text


def test_posting_without_enabled_turns_it_off_and_back_on(host):
    client, owner_id = host
    response = client.post("/account/guest-details-mail", data={}, follow_redirects=False)
    assert response.status_code == 303
    assert guest_mail_pref.switch_on(owner_id) is False
    response = client.post(
        "/account/guest-details-mail", data={"enabled": "1"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert guest_mail_pref.switch_on(owner_id) is True
    page = client.get("/settings/account?lang=en")
    form = page.text.split('id="settings-guest-details-mail"', 1)[1].split("</form>", 1)[0]
    assert " checked" in form
```
Command: `cd App && .venv/bin/python -m pytest tests/test_guest_mail_pref_settings.py tests/test_guest_mail_pref.py -q --tb=short -x 2>&1 | tail -30`. Expected: `7 passed`.

10. Test-map rows. Mail-adjacent switch tests, copy row, then host pages row (browser, 0 skipped). Commands, one per line:
- `cd App && .venv/bin/python -m pytest tests/test_stay_fee_email_switch.py tests/test_0789b_settings_toggles.py tests/test_0789_settings_subpages.py -q --tb=short -x 2>&1 | tail -30`. Expected: all passed.
- `cd App && .venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py -q --tb=short -x 2>&1 | tail -30`. Expected: all passed. A failure that names `guest_details_mail` (a flash literal or missing Czech key): fix only the strings of step 7 and 8; second failure: STOP.
- `cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q --tb=short -x 2>&1 | tail -30`. Expected: all passed, `0 skipped`. Any skipped: STOP (browser missing, owner step).

11. UX gate (AGENTS rule 10, docs/context/workflow.md "UX gate"). Run from `App/`:
`mkdir -p /tmp/shots && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30`. Expected: passed, 0 skipped, zero host findings. A finding on the settings page: do NOT silence it and do not edit the lint; STOP and report it.
Then `ls /tmp/shots/layout-lint | grep -i settings | head -20` to find the Settings page files (`<page>-390.png`, `-768.png`, `-1280.png`).

12. Open (Read tool, they are images) the 390, 768 and 1280 PNG of the Settings account page. Look for: label wraps instead of truncating, the "?" sits right after the label on the same line, the switch is aligned right like the two switches above, 12 px between rows, no coral except focus. Copy one 390 px PNG to `docs/tasks/1120b-settings-390.png` is NOT required; only describe it.

13. Write `docs/tasks/1120b-report.md` (§9). It must contain the PR-body text, one line per page as the owner will paste it: `Settings > Account: 390: ...; 768: ...; 1280: ...` (what you saw, in plain words), and the design-system checklist ticked, written out:
`[ ] 1 one shell (unchanged)  [ ] 2 tokens only, no style attribute  [ ] 3 12 px between neighbours  [ ] 4 no new header action  [ ] 5 one Save per form (noscript Save only)  [ ] 6 no repeated heading  [ ] 7 no fine print, text under the "?"  [ ] 8 no truncated label  [ ] 9 no coral  [ ] 10 not a table`, each marked `[x]` only if the screenshots show it.

## 5. Do not touch

- `App/app/guest_mail_pref.py`, migrations, `App/app/retention.py` (a boolean preference is not personal data), `App/app/mail_notify.py`, `App/app/claim.py` (briefs 1121 and 1122 own them), `tests/layout_lint.js`, any CSS or static file.
- No new dependency. SQL only through `db.py` helpers (this brief writes none). Public repo: no secrets, no real guest data. No `style=""`, no JavaScript beyond the existing `data-toggle-submit`. Copy rule 9: write "no tracking cookies" never "no cookies" (not used here); one explanation in one place (the "?" only). No em dashes in strings.
- Light mode only. The form must work without JavaScript (the `<noscript>` Save).

## 6. Commands

As in the steps. Every one ends `| tail -30`. No full suite.

## 7. Acceptance

- [ ] `tests/test_guest_mail_pref_settings.py tests/test_guest_mail_pref.py`: `7 passed`.
- [ ] The three step 10 commands pass, browser run shows `0 skipped`.
- [ ] `test_layout_lint_browser.py` green, 0 skipped, no host finding.
- [ ] 390, 768 and 1280 screenshots of the Settings account page opened; per-page notes and the ticked checklist are in the report.
- [ ] `git diff --stat` lists only the §3 files plus the report.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1120b-report.md` (600 tokens at most, the PR-body lines count) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/templates/settings.html`: the new row and its `id`.
- `App/app/routes/admin_accounts.py`: the owner-only guard on the POST.
- `App/app/host_i18n.py`: Czech wording is a draft; the lawyer sees the final text in 1123, not here.

## Owner steps

None for this brief. The switch has no effect on any mail until 1121 ships, and no workspace gets full details before the DPA bump of 1123 is live and accepted. Merge with `scripts/merge-pr-on-green.sh`.
