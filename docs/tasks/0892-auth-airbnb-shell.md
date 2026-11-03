# 0892: Airbnb pattern on the login, magic-link and 2FA pages

Status: todo
Depends on: none (run after PR #729 merges, see §2) | Base commit: 41e86bd3 | Branch: task/0892-auth-airbnb-shell
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Josef wants the auth pages (login, magic link sent / open, 2FA code, 2FA setup, recovery codes) to look like the rest of the app on phone, tablet and desktop: big bold title, no fine print (help goes under a small inline "?" of about 18 px), 12 px between any two neighbouring elements, and fewer taps. Every form keeps working without JavaScript.

## 2. Context

- References: `/mnt/project-files/settings-area/airbnb-ref/` (IMG_2197 pills, IMG_2198 value cards, IMG_2199 index rows). Open at most one.
- `auth_base.html` loads `tokens.css`, `app.css` (shared with the public legal pages, which nobody may touch) and `components.css`; it does NOT load `app2.css`, so the `airbnb-*` and `settings-*` classes do not reach these pages. All new CSS goes in a NEW file `App/app/static/auth2.css`, linked only from `auth_base.html`. Never edit `app.css`.
- `signup.html`, `signup_sent.html`, `signup_verify.html` extend `auth_base.html` too. `signup.html` belongs to PR #729: read-only here. Run this brief after #729 merges; if #729 is still open, base on main anyway and expect only `auth_base.html` to conflict (it does not touch the files in §3 otherwise).
- Owner decisions (2026-11-02): guest pages and public pages (landing, pricing, product, legal) are out of scope and must not change.
- The "?" on auth pages is a `<details>` element, so it opens without JavaScript (AGENTS.md rule 6). Do not use `help_tip` from `_components.html` here: it needs `app.js`, which auth pages do not load.
- What counts as fine print: a description or sub-line under a title (`auth-lede`), a `small` class, muted text. It moves under the "?" next to the h1. Exceptions that stay visible: the legal acceptance line (`p.auth-acceptance`, tested by `test_login_acceptance.py`), the footer legal links (`.auth-foot-legal`), alerts and notices (`role="alert"`/`role="status"`), the sent-page message (it is the page's content), and the recovery "shown once" warning. These become at least 14 px (legal) or 16 px (everything else).

Anchors (exact, verified on 41e86bd3):

`App/app/templates/auth_base.html`
```
  <link rel="stylesheet" href="/static/components.css?v=20261002a">
```
`App/app/templates/login.html`
```
  <h1 class="auth-title">{{ t('login.title') }}</h1>
  <p class="auth-lede">{{ t('login.lede') }}</p>
```
```
  <div class="auth-foot">
    <p>{{ t('login.footnote', email=operator().email) }}</p>
  </div>
```
`App/app/templates/login_link.html`
```
  <h1 class="auth-title">{{ t('login.link.invite_title') if invite else t('login.link.title') }}</h1>
  <p class="auth-lede">{{ t('login.link.lede') }}</p>
```
`App/app/templates/two_factor_login.html`
```
  <h1 class="auth-title">{{ t('account.2fa.code_title') }}</h1>
  <p class="auth-lede">{{ t('account.2fa.code_lede') }}</p>
```
`App/app/templates/two_factor_setup.html`
```
  <h1 class="auth-title">{{ t('account.2fa.setup_title') }}</h1>
  <p class="auth-lede">{{ t('account.2fa.setup_lede') }}</p>
```
```
  <ol class="small">
```
`App/app/templates/two_factor_recovery.html`
```
  <h1 class="auth-title">{{ t('account.2fa.recovery_title') }}</h1>
  <p class="auth-lede">{{ t('account.2fa.recovery_lede') }}</p>
  <p class="small"><strong>{{ t('account.2fa.recovery_once') }}</strong></p>
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/static/auth2.css` | create | the 0892 auth look |
| `App/app/templates/auth_base.html` | edit | link `auth2.css` |
| `App/app/templates/login.html` | edit | title row with "?", footnote into help, `enterkeyhint` |
| `App/app/templates/login_link.html` | edit | title row with "?" |
| `App/app/templates/login_sent.html` | edit | none expected; only if a §6 check fails on it |
| `App/app/templates/two_factor_login.html` | edit | title row with "?", `enterkeyhint` |
| `App/app/templates/two_factor_setup.html` | edit | title row with "?", steps 16 px, `enterkeyhint` |
| `App/app/templates/two_factor_recovery.html` | edit | title row with "?", warning 16 px |
| `App/tests/test_0892_auth_airbnb_browser.py` | create | geometry test, 6 widths |
| `App/tests/static_versions.json` | regenerate | `--write`, never by hand |

Existing tests in §6 may get an assertion updated to the new markup; never delete a behaviour test. No other file may change.

## 4. Steps

1. Create `App/app/static/auth2.css` with exactly this:
```css
/* 0892: Airbnb pattern for the auth shell (login, magic link, 2FA). Loaded only by auth_base.html. Light mode only. */
body.auth-page .auth-title-row{position:relative;display:flex;align-items:flex-end;gap:8px;margin:0 0 24px}
body.auth-page .auth-title-row .auth-title{margin:0;font-size:32px;line-height:1.2;font-weight:700;color:#222;letter-spacing:0}
body.auth-page .auth-q{flex:0 0 auto;margin:0 0 8px}
body.auth-page .auth-q>summary{list-style:none;position:relative;display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;box-sizing:border-box;border-radius:50%;border:1px solid #717171;color:#222;font-size:12px;font-weight:700;line-height:1;cursor:pointer}
body.auth-page .auth-q>summary::-webkit-details-marker{display:none}
body.auth-page .auth-q>summary::after{content:"";position:absolute;inset:-13px}
body.auth-page .auth-q[open]>summary{background:#222;border-color:#222;color:#fff}
body.auth-page .auth-q>.auth-lede{position:absolute;left:0;right:0;top:calc(100% + 12px);z-index:5;margin:0;padding:16px;background:#fff;border:1px solid #e5e5e5;border-radius:12px;font-size:16px;line-height:1.5;color:#222}
body.auth-page .auth-lede,body.auth-page .auth-help-note,body.auth-page .auth-steps,body.auth-page .auth-warn{font-size:16px;line-height:1.5;color:#222}
body.auth-page .auth-steps{margin:0 0 24px;padding-left:20px}
body.auth-page .auth-steps li+li{margin-top:12px}
body.auth-page .auth-form>*+*,body.auth-page .auth-card>*+*{margin-top:12px}
body.auth-page .auth-submit{min-height:48px;border-radius:8px;font-size:16px;font-weight:600}
body.auth-page .auth-submit+*{margin-top:24px}
body.auth-page .auth-field input{min-height:48px;font-size:16px;border-radius:8px}
body.auth-page .auth-help>summary{min-height:44px;display:flex;align-items:center;font-size:16px}
body.auth-page .auth-acceptance,body.auth-page .auth-foot-legal{font-size:14px;line-height:1.5;color:#6a6a6a}
body.auth-page .auth-foot-links a{display:inline-flex;align-items:center;min-height:44px}
body.auth-page .auth-lang-switch{display:flex;gap:12px;flex-wrap:wrap}
body.auth-page .auth-lang-switch button{min-height:44px;padding:0 16px;border-radius:999px;border:0;background:#f2f2f2;color:#222;font-weight:600}
body.auth-page .auth-lang-switch button.is-active{background:#222;color:#fff}
body.auth-page .auth-codes-actions{display:flex;gap:12px;flex-wrap:wrap}
body.auth-page .auth-codes-actions .btn{min-height:44px}
@media (min-width:1024px){body.auth-page .auth-card{border:1px solid #e5e5e5;border-radius:12px;padding:32px}}
```
   Command: `ls -l App/app/static/auth2.css 2>&1 | tail -3`. Expected: the file exists.
2. `auth_base.html`: after the anchor line `  <link rel="stylesheet" href="/static/components.css?v=20261002a">` add the line `  <link rel="stylesheet" href="/static/auth2.css?v=20261102-0892">`. Command: `grep -n "auth2.css" App/app/templates/auth_base.html | tail -3`. Expected: one line.
3. `login.html`: replace the two-line h1/lede anchor with:
```
  <div class="auth-title-row">
    <h1 class="auth-title">{{ t('login.title') }}</h1>
    <details class="auth-q">
      <summary aria-label="{{ t('help.tip.label') }}">?</summary>
      <p class="auth-lede">{{ t('login.lede') }}</p>
    </details>
  </div>
```
   Same command pattern: `grep -c "auth-title-row" App/app/templates/login.html | tail -3`, expected `1`.
4. `login.html`: delete the three-line `<div class="auth-foot">` anchor block, and inside `<details class="auth-help">`, after the line `    <p class="auth-help-note">{{ t('login.help_body', email=operator().email) }}</p>`, add `    <p class="auth-help-note">{{ t('login.footnote', email=operator().email) }}</p>`. Then on the email `<input type="email" id="email"` add the attribute `enterkeyhint="go"` (after `maxlength="254"`). Command: `grep -c "auth-foot\"" App/app/templates/login.html | tail -3`, expected `0`.
5. `login_link.html`: same title-row change as step 3, using its own h1 and lede lines from §2 (keep the `invite` condition in the h1). Do not touch the expired branch's h1/lede (it is the page's message). Command: `grep -c "auth-q" App/app/templates/login_link.html | tail -3`, expected `1`.
6. `two_factor_login.html`: same title-row change for its h1/lede. On `<input type="text" id="code"` add `enterkeyhint="done"`. Command: `grep -c "auth-q\|enterkeyhint" App/app/templates/two_factor_login.html | tail -3`, expected `2`.
7. `two_factor_setup.html`: same title-row change; replace `  <ol class="small">` with `  <ol class="auth-steps">`; on `<input type="text" id="code"` add `enterkeyhint="done"`. Command: `grep -c "class=\"small\"" App/app/templates/two_factor_setup.html | tail -3`, expected `0`.
8. `two_factor_recovery.html`: same title-row change for its h1/lede; replace `  <p class="small"><strong>` with `  <p class="auth-warn"><strong>`. Command: `grep -c "class=\"small\"" App/app/templates/two_factor_recovery.html | tail -3`, expected `0`.
9. Write `App/tests/test_0892_auth_airbnb_browser.py`. Copy the `base` fixture (live uvicorn server) from `App/tests/test_0786_settings_geometry_browser.py` lines 159 to 176 and its imports. Pages, each rendered as HTML by a `TestClient` and shown with `page.goto(base + "/login")` then `page.set_content(html)` (so `/static` resolves):
   - `login`: GET `/login?lang=en`;
   - `login_sent`: POST `/login` with the CSRF token from the login page and an `@example.test` e-mail (copy the CSRF pattern from `App/tests/test_login_help.py`);
   - `login_link_expired`: GET `/login/link?t=nope&lang=en`;
   - `two_factor_login`: copy `_on_the_second_factor` (lines 69 to 92) from `App/tests/test_two_factor_lockout.py`;
   - `two_factor_setup`: a logged-in host (`login_as` from `tests.conftest`) GET `/account/2fa/setup`;
   - `two_factor_recovery`: run `grep -n "recovery" App/tests/test_two_factor_setup_page.py | head -20` and copy how it reaches the recovery page. If nothing reaches it, leave it out (no skip marker) and say so under Questions.
   Parametrise pages x widths (320, 390, 768, 1024, 1280, 1440). Checks per page and width:
   - exactly one visible `h1`, computed font-size >= 28 px, weight >= 700; no horizontal overflow (`scrollWidth <= innerWidth`);
   - where `.auth-q` exists: its summary box is 18 +/- 1 px square, its left edge is 6 to 10 px right of the h1 text's last line right edge or (when the row wraps) on the h1's last line; clicking the summary opens it with JavaScript disabled too (one extra context `java_script_enabled=False` at 390 for `login`, which also asserts the e-mail field and submit button are visible and the form `action` is `/login`);
   - no visible text under 14 px; no visible `p`, `li` or `.small` outside `.auth-q`, `.auth-acceptance`, `.auth-foot-legal`, `[role=alert]`, `[role=status]` under 16 px;
   - 12 px neighbour rule: for every pair of visible boxes among `.auth-card` descendants matching `h1, .auth-q > summary, .auth-field, .auth-submit, .auth-help > summary, .auth-acceptance, .auth-foot a, .auth-codes, .auth-codes-actions .btn` plus `.auth-lang-switch button`, that do not contain each other and do not overlap, the vertical or horizontal gap is >= 12 px (the "?" to h1 gap is the 8 px exception above);
   - buttons, inputs and lang buttons are >= 44 px tall;
   - at >= 1024 `.auth-card` has a 1 px border and radius >= 12; below 1024 it has no border.
   With `UBYHOST_SHOTS_0892=1`, save `docs/tasks/screenshots-0892/<page>-<width>.png` at 390 and 1280 only.
   Run §6 command 1. Fix only `auth2.css` (and, if a template step was misapplied, that template) until green, 0 skipped.
10. Regenerate the manifest: from `App/`, `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`.
11. Run §6 command 2. If an old test asserts the old markup (for example the footnote under `.auth-foot` in `test_login_help.py`), update that assertion to the new place; never delete a test.
12. Screenshots: §6 command 3. Look at each 390 px image once.

## 5. Do not touch

`App/app/static/app.css`, `app2.css`, `components.css`, `auth.js`, `signup*.html` (PR #729), `public_legal_base.html`, every guest and public template, any route or Python file, any `i18n` file (no new copy: every string already exists). AGENTS.md rules 2 (no new third-party script: Turnstile stays as is), 6 (light mode, no-JS auth), 7, 9.

## 6. Commands

From `App/`:
1. `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0892_auth_airbnb_browser.py -q -rs --tb=line -p no:cacheprovider 2>&1 | grep -E "^(FAILED|ERROR)|^E  |passed|failed|skipped" | cut -c1-240 | tail -20`. Expected: all passed, 0 skipped.
2. `.venv/bin/python -m pytest tests/test_login_*.py tests/test_auth_*.py tests/test_two_factor_*.py tests/test_signup.py tests/test_copy_cleanup.py tests/test_logo_placements.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed.
3. `UBYHOST_SHOTS_0892=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0892_auth_airbnb_browser.py -q -k "390 or 1280" -p no:cacheprovider 2>&1 | tail -5`.
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] Command 1: all passed, 0 skipped, widths 320 to 1440.
- [ ] Command 2 passed.
- [ ] `git diff --stat` lists only §3 files.
- [ ] One 390 px screenshot per changed page in `docs/tasks/screenshots-0892/` (1280 too, the desktop card is new).
- [ ] Report lists, per page, taps to finish before and after (expected: same taps; the keyboard's Go/Done key now submits).

## 8. Stop and ask

Stop, and write the report, if:

- an anchor in §2 is not found verbatim;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a form would need JavaScript, or a route or Python change seems needed;
- `signup.html` or any file outside §3 needs a change;
- a step is unclear.

## 9. Report

Write `docs/tasks/0892-report.md` (600 tokens at most) and set `Status: review`. The report has: files changed (`git diff --stat`); each §6 command with its last 5 lines; §7 ticked; the tap counts; Deviations; Questions; owner steps left.

## Risk list (for the reviewer)

`auth_base.html` (also styles signup pages), `login.html` (acceptance line order, Turnstile untouched), `auth2.css`.

## Owner steps

1. Open the PR, check the 390 px screenshots of login and 2FA.
2. On staging, log in once on your phone with the magic link and once with 2FA.
