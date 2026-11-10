# 1080: Skip the login Turnstile for a known browser

Status: todo
Depends on: none | Base commit: main | Branch: task/1080-login-turnstile-skip
Executor: Haiku 5.5 | Fits one session

## 1. Objective

Owner goal: a host faces Cloudflare Turnstile about once a month. Today the server already skips verification for a trusted device (cookie `ubyhost_device`, 30 days, `auth.trusted_device(request, email)`), but `login.html` still renders the widget every time, so the owner sees it on every visit. Hide the widget on `/login` when the browser carries a valid device cookie. The server still checks the cookie against the submitted e-mail. If that check fails, or `login_link.request_blocked` is true, re-render the form WITH the widget and the existing error `auth.error.turnstile`. Bot protection stays for unknown devices. The Cloudflare edge challenge is the owner's job (§Owner steps), not code.

## 2. Context (verified)

- `App/app/auth.py` 616-651: `attach_device(response, account)` sets the signed cookie (30 days; payload `uid`, `sv`, `did`); `trusted_device(request, email)` loads it, then compares to `account_by_email(email)`.
- `App/app/routes/admin_accounts.py` 59-63: `GET /login` renders `login.html` with `_login_page_context(request)`. 114-148: `POST /login` computes `trusted`, verifies Turnstile only if not trusted, and `again(error, status)` re-renders the form. `_finish_login` (~219) calls `attach_device` on every successful login, so the cookie already slides: 30 days from the last login. No change needed there.
- `admin_accounts.py` 96 is the staging password path only (`_try_staging_password_login`). Leave it: it is staging only and has no e-mail-bound device check.
- `App/app/templates/login.html`: e-mail form widget at lines 69-72, script tag at 89-91, staging-password widget at 33-36.
- Existing tests `App/tests/test_login_session_persistence.py` lines ~113-140 cover the server skip (device cookie for that e-mail skips; for another e-mail does not).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/auth.py` | edit | add `device_cookie_valid(request)` after `trusted_device` |
| `App/app/routes/admin_accounts.py` | edit | pass `skip_turnstile` in `GET /login` and in `again`; force the widget on a Turnstile error |
| `App/app/templates/login.html` | edit | hide widget and script when `skip_turnstile` |
| `App/tests/test_login_session_persistence.py` | edit | 4 new tests (step 4) |
| `docs/context/decisions.md` | edit | append one line (step 5) |
| `docs/tasks/1080-report.md` | create | §9 |

No other file may change.

## 4. Steps

1. `auth.py`: after `trusted_device` (ends with `and int(payload.get("sv", -1)) == int(account["session_version"])` then `)`), add. Find the anchor with `grep -nF "def create_account(" App/app/auth.py` and insert above it:
```python
def device_cookie_valid(request) -> bool:
    """True when the device cookie is signed, fresh and matches a live account.

    Used only to decide whether /login shows the widget. The submit still
    checks the cookie against the typed e-mail (trusted_device).
    """
    token = request.cookies.get(DEVICE_COOKIE)
    if not token:
        return False
    try:
        payload = _device_serializer().loads(token, max_age=DEVICE_MAX_AGE)
    except Exception:
        return False
    if not isinstance(payload, dict):
        return False
    try:
        account = db.query_one(
            "SELECT * FROM user_account WHERE id = ? AND active = 1",
            (int(payload.get("uid", -1)),),
        )
    except (TypeError, ValueError):
        return False
    return bool(
        account
        and int(account["active"]) == 1
        and int(payload.get("sv", -1)) == int(account["session_version"])
    )
```
   (The query is the same one `auth.py` line 322 uses; `db` is already imported there.)
   Check: `cd App && .venv/bin/python -c "from app import auth" 2>&1 | tail -30` prints nothing.
2. `admin_accounts.py` `_login_page_context` (anchor `def _login_page_context(request: Request) -> dict:` / `ctx: dict = {}`): add after `ctx: dict = {}`:
```python
    ctx["skip_turnstile"] = auth.device_cookie_valid(request)
```
   In `login_submit`, inside `again(...)`, the render context dict is `{"error": error, "email": raw_email, "next": next_path, **_login_page_context(request)}`. Append `, **({"skip_turnstile": False} if error == "auth.error.turnstile" else {})` after the `_login_page_context` spread, so the re-rendered form shows the widget. Do not touch lines 96-97 or the `trusted` logic at 145-148.
   Check: `cd App && .venv/bin/python -c "from app.routes import admin_accounts" 2>&1 | tail -30`.
3. `login.html`: change ONLY the e-mail form widget condition (line 69, the second `{% if turnstile_site_key %}`, the one followed by `data-action="host_login"` after the `email` input) to `{% if turnstile_site_key and not skip_turnstile %}`. Change the script condition (line 89, `{% if turnstile_site_key %}` before `api.js`) to `{% if turnstile_site_key and (staging_password_enabled or not skip_turnstile) %}`. Leave the staging widget at line 33 alone. Show no new text; no new copy.
4. Tests in `test_login_session_persistence.py` (reuse that file's fixtures and its `turnstile.required` monkeypatch; copy the style of the tests at ~113-140). Add:
   - `test_login_page_hides_the_widget_with_a_valid_device_cookie`: sign in once to get the cookie, log out (plain logout keeps it), GET `/login` with the cookie: body has no `cf-turnstile` and no `challenges.cloudflare.com`.
   - `test_login_page_shows_the_widget_without_a_device_cookie`: fresh client, GET `/login`: body contains `cf-turnstile` (site key set via the same monkeypatch the file uses for `config.TURNSTILE_SITE_KEY`; copy it).
   - `test_login_page_shows_the_widget_with_a_forged_or_stale_device_cookie`: cookie `ubyhost_device=garbage` and a cookie whose account `session_version` was bumped: widget present.
   - `test_turnstile_failure_rerenders_the_form_with_the_widget`: valid device cookie, POST `/login` with another e-mail and no token: status 403, body contains `cf-turnstile`.
   Existing tests at ~120 and ~133 must stay unchanged and green.
5. `docs/context/decisions.md`: append at the end: `- 2026-11-10 [auth] Login hides the Turnstile widget when the browser has a valid signed device cookie (30 days, renewed on each login); the server still checks it against the typed e-mail, and a failed check or a blocked link request re-renders the form with the widget. Edge Managed Challenge and Challenge Passage stay in the Cloudflare dashboard (docs/CLOUDFLARE.md). | owner | 1080`
6. Commit each step as `1080 step k`.

## 5. Do not touch

`turnstile.py`, `_try_staging_password_login`, the `trusted` logic in `login_submit`, `attach_device`, cookie lifetimes, guest or signup pages, i18n files, CSS, any dependency. Hard rules 2, 4, 6, 7, 8, 10 of AGENTS.md apply. The form must keep working without JavaScript: a visitor with a valid device cookie can submit with no widget and no JS.

## 6. Commands

From `App/` (each ends `-q --tb=short -x -rs 2>&1 | tail -30`):
1. `.venv/bin/python -m pytest tests/test_login_session_persistence.py tests/test_login_*.py tests/test_auth_*.py tests/test_two_factor_*.py tests/test_passkeys.py tests/test_remember_me_reissue.py tests/test_security*.py tests/test_logout_devices.py tests/test_cookie_inventory.py tests/test_turnstile_language.py`
2. Template changed: `.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py` (0 skipped).
3. UX gate: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x -rs 2>&1 | tail -30` (0 skipped, zero findings). Open `/tmp/shots/layout-lint/login-{390,768,1280}.png` (use the real file names `ls` shows).
From the repo root: `python3 scripts/context_lint.py | tail -30`.

## 7. Acceptance

- [ ] With a valid device cookie, `/login` has no widget and no `api.js` script; without one, or with a forged or stale one, it has both.
- [ ] POST with a device cookie for another e-mail, or with `request_blocked` true, gives 403 `auth.error.turnstile` and the re-rendered form shows the widget.
- [ ] Existing server-skip tests (~120, ~133) pass unchanged.
- [ ] Staging password form and line 96 unchanged.
- [ ] §6 commands 1-3 green, 0 skipped; context lint passes.
- [ ] One 390 px screenshot of `/login` in the report, plus the PR text per page: "390: ...; 768: ...; 1280: ..." (what you saw). Design-system checklist ([design-system](../design/design-system.md)) ticked in the PR. Never silence a finding.

## 8. Stop and ask

An anchor is not found verbatim; a test fails twice; a file outside §3 needs a change; the layout lint reports a finding on `/login` you did not cause; you need push, merge, secrets, SSH or deploy.

## 9. Report

`docs/tasks/1080-report.md` (600 tokens at most): files changed, each command with its last 5 lines, §7 ticked, deviations, questions. Set `Status: review` and open one PR. Merge only with `scripts/merge-pr-on-green.sh` (owner or orchestrator).

## Risk list (for the reviewer)

`App/app/auth.py` and `admin_accounts.py` (auth code: read every line of the diff). Check that the widget hiding never removes the server check, and that a cookie for account A cannot skip Turnstile for e-mail B.

## Owner steps (Cloudflare dashboard, not code)

1. Open dash.cloudflare.com, pick the `ubyhost.com` zone.
2. Security, Settings, find **Challenge Passage**, set it to **1 month** (longest offered; if the list stops at 1 week or 1 day, pick the longest and tell the orchestrator). Save.
3. Security, Security rules: for each rule with action Managed Challenge, check its expression does not match every request to `app.ubyhost.com` (a rule on the whole host re-challenges after each passage). Narrow it to `/login`, `/signup` and the paths that need it, or leave it if it already does. Say what you changed.
4. Security, Events: filter host `app.ubyhost.com`, last 7 days. Note which rule or "Bot Fight Mode" produced Challenge actions on returning visitors; send the orchestrator the rule names.
5. Turnstile, UbyHost widget, Settings: confirm pre-clearance is still On and Interactive (docs/CLOUDFLARE.md 177-199 records the 23 October values).
6. After the deploy: log in once, then open `app.ubyhost.com/login` in a new tab. Expect no widget. Update the dated table in docs/CLOUDFLARE.md only through a brief.
