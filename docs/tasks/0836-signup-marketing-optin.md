# 0836 Signup: setup-tips opt-out becomes an unticked marketing opt-in

Executor: Haiku 5.5. Alone, no subagents. Branch `claude/project-thread-mb7ww2` (PR #729). Do not push, do not merge.

Status: todo

## 1. Objective

Owner decision (Josef, 2026-11-02): the sign-up box that today reads "No setup tips by e-mail" (an unticked opt-OUT) becomes an unticked marketing opt-IN:

| Language | New label |
|---|---|
| EN | Send me tips and news by e-mail |
| CS | Posílejte mi tipy a novinky e-mailem |
| VI | Gửi cho tôi mẹo và tin tức qua e-mail |

- Box unticked (the default) = the new account stores `onboarding_emails_opt_out = 1` plus the time in `onboarding_emails_opt_out_at`: no setup tips or marketing e-mails.
- Box ticked = `onboarding_emails_opt_out = 0` and `onboarding_emails_opt_out_at = NULL`.
- Existing accounts are untouched: no migration, no data update.
- The Settings toggle "Setup tips by e-mail" keeps working, so a host who left the box unticked can turn tips on later.

## 2. Context

Every reader and writer of the flag, traced by the orchestrator. Only the rows marked "change" are edited.

| Where | What it does | This brief |
|---|---|---|
| `App/app/templates/signup.html` line 50-54 | the box, field `onboarding_opt_out` | change (Step 1) |
| `App/app/host_i18n.py` line 5525-5528 (EN), 5921-5923 (CS) | key `signup.onboarding_opt_out` | change (Step 2) |
| `App/app/host_vi_i18n.py` line 2792 | key `signup.onboarding_opt_out` (VI) | change (Step 3) |
| `App/app/routes/signup.py` line 89, 105, 130 | reads the form field, re-renders it, passes it to `signup.register` | change (Step 4) |
| `App/app/signup.py` line 496, 534-536 | `register(onboarding_opt_out=...)` writes the column | keep the code; comment only (Step 5) |
| `App/app/lifecycle_mail.py` line 15-16 | module docstring "the host can refuse at sign-up" | docstring only (Step 5) |
| `App/app/lifecycle_mail.py` `set_opt_out`, `is_opted_out`, `resubscribe`, `unsubscribe`, `candidates` (line 224 `COALESCE(u.onboarding_emails_opt_out, 0) = 0`) | sending skips every opted-out account | no change: it already respects the stored flag |
| `App/app/routes/admin.py` line 4846 `_onboarding_emails` | Settings checkbox shows `not onboarding_emails_opt_out` | no change: new accounts start with it off, the host can tick it |
| `App/app/routes/admin_accounts.py` line 325-348 `POST /account/onboarding-emails` | ticked calls `lifecycle_mail.resubscribe`, unticked calls `set_opt_out(..., True)` | no change |
| `App/app/db.py` line 1095-1096 | the two columns, default 0 | no change (existing accounts stay as they are) |
| `App/tests/test_signup.py` | old field name, old strings, old default | change (Step 6) |
| `App/tests/test_lifecycle_mail.py` line 322-345 | Settings toggle off then on | no change; must still pass |
| `App/tests/test_signup_selection.py`, `App/tests/test_meta_capi.py` | post `/signup` without the box; assert nothing about the flag | no change; must still pass |

- `signup.register` keeps its parameter `onboarding_opt_out` (the stored meaning). The route passes `onboarding_opt_out=not marketing_opt_in`. `register` has no other caller.
- On GET the template gets no `marketing_opt_in` value, so the box renders unticked (same pattern as today).
- Tip e-mail content is not changed by this brief.

## 3. Files

| File | Change |
|---|---|
| `App/app/templates/signup.html` | Step 1: field name, key, comment |
| `App/app/host_i18n.py` | Step 2: EN and CS key renamed, new text |
| `App/app/host_vi_i18n.py` | Step 3: VI key renamed, new text |
| `App/app/routes/signup.py` | Step 4: read `marketing_opt_in`, invert for `register` |
| `App/app/signup.py` | Step 5: one comment line |
| `App/app/lifecycle_mail.py` | Step 5: two docstring lines |
| `App/tests/test_signup.py` | Step 6: helper, assertions, three tests |
| `docs/UbyHost_workplan/04_legal_positions.md` | Step 7: one dated line |
| `docs/context/decisions.md` | Step 7: compact two lines, append one |
| `docs/tasks/screenshots-0836/` | Step 8: two 390 px screenshots |
| `docs/tasks/0836-report.md` | Report |

## 4. Steps

For each step: find the anchor with `grep -nF`, replace the old block with the new block exactly (whitespace included), change nothing else, commit with the message given.

### Step 1: template

Anchor: `grep -nF "{# Legal position 2: refusing setup tips is one optional, unticked box. #}" App/app/templates/signup.html` (line 50).

Old block (lines 50-54):

```
    {# Legal position 2: refusing setup tips is one optional, unticked box. #}
    <label class="auth-remember">
      <input type="checkbox" name="onboarding_opt_out" value="1"{% if onboarding_opt_out %} checked{% endif %}>
      <span>{{ t('signup.onboarding_opt_out') }}</span>
    </label>
```

New block:

```
    {# Legal position 2 (owner, 2026-11-02): tips and news only with this optional, unticked box. #}
    <label class="auth-remember">
      <input type="checkbox" name="marketing_opt_in" value="1"{% if marketing_opt_in %} checked{% endif %}>
      <span>{{ t('signup.marketing_opt_in') }}</span>
    </label>
```

Check: `grep -c "onboarding_opt_out" App/app/templates/signup.html 2>&1 | tail -30` prints `0`. Commit `0836 step 1`.

### Step 2: EN and CS strings

EN anchor: `grep -nF '"No setup tips by e-mail"' App/app/host_i18n.py` (line 5527). Old block (lines 5525-5528):

```
        # Legal position 2, verbatim.
        "signup.onboarding_opt_out": (
            "No setup tips by e-mail"
        ),
```

New block:

```
        # Legal position 2: unticked marketing opt-in (owner, 2026-11-02).
        "signup.marketing_opt_in": "Send me tips and news by e-mail",
```

CS anchor: `grep -nF '"Bez tipů k nastavení e-mailem"' App/app/host_i18n.py` (line 5922 before the EN edit, 5920 after). Old block (3 lines):

```
        "signup.onboarding_opt_out": (
            "Bez tipů k nastavení e-mailem"
        ),
```

New block:

```
        "signup.marketing_opt_in": "Posílejte mi tipy a novinky e-mailem",
```

Check: `grep -c "signup.onboarding_opt_out" App/app/host_i18n.py 2>&1 | tail -30` prints `0` and `grep -c "signup.marketing_opt_in" App/app/host_i18n.py 2>&1 | tail -30` prints `2`. Commit `0836 step 2`.

### Step 3: VI string

Anchor: `grep -nF '"signup.onboarding_opt_out": "Không gửi mẹo thiết lập qua e-mail",' App/app/host_vi_i18n.py` (line 2792). Replace that one line:

```
    "signup.onboarding_opt_out": "Không gửi mẹo thiết lập qua e-mail",
```

with:

```
    "signup.marketing_opt_in": "Gửi cho tôi mẹo và tin tức qua e-mail",
```

Commit `0836 step 3`.

### Step 4: route

File `App/app/routes/signup.py`.

4a. Anchor: `grep -nF 'onboarding_opt_out = _form_str(form, "onboarding_opt_out") == "1"' App/app/routes/signup.py` (line 89). Replace that line:

```
    onboarding_opt_out = _form_str(form, "onboarding_opt_out") == "1"
```

with:

```
    # Unticked (the default) means no tips or news: stored as the opt-out flag.
    marketing_opt_in = _form_str(form, "marketing_opt_in") == "1"
```

4b. In `again()` (line 103-105 before 4a). Old block:

```
                email=raw_email,
                workspace=workspace,
                onboarding_opt_out=onboarding_opt_out,
```

New block:

```
                email=raw_email,
                workspace=workspace,
                marketing_opt_in=marketing_opt_in,
```

4c. In the `signup.register(` call (line 129-130 before 4a). Old block:

```
        consents=consents,
        onboarding_opt_out=onboarding_opt_out,
        lang=lang,
```

New block:

```
        consents=consents,
        onboarding_opt_out=not marketing_opt_in,
        lang=lang,
```

Check: `grep -n "opt_out\|opt_in" App/app/routes/signup.py 2>&1 | tail -30` shows exactly 4 lines: the comment, the `marketing_opt_in =` line, `marketing_opt_in=marketing_opt_in,` and `onboarding_opt_out=not marketing_opt_in,`. Commit `0836 step 4`.

### Step 5: comments

5a. Anchor: `grep -nF "# Legal position 2: the sign-up refusal of setup-tip e-mails." App/app/signup.py` (line 534). Replace that line with:

```
        # Legal position 2: tips and news only if the unticked sign-up box was ticked.
```

5b. Anchor: `grep -nF "of Czech Act 480/2004 (legal position 2): the host can refuse at sign-up, in" App/app/lifecycle_mail.py` (line 15). Old block (lines 15-16):

```
of Czech Act 480/2004 (legal position 2): the host can refuse at sign-up, in
Settings and with the link in every tip; every tip names the sender.
```

New block:

```
of Czech Act 480/2004 (legal position 2): tips need the unticked opt-in box at
sign-up or the Settings toggle; the host can refuse in Settings and with the
link in every tip; every tip names the sender.
```

Commit `0836 step 5`.

### Step 6: tests in `App/tests/test_signup.py`

6a. Helper `_submit`, anchor `grep -nF 'accept="1", consent=False, gclid="", click=None, opt_out=False, extra=None):' App/tests/test_signup.py` (line 64). In that line change `opt_out=False` to `opt_in=False`. Then the old block (lines 70-71):

```
    if opt_out:
        data["onboarding_opt_out"] = "1"
```

New block:

```
    if opt_in:
        data["marketing_opt_in"] = "1"
```

6b. In `test_the_ads_box_is_shown_only_with_a_click_id`, anchor `grep -nF "# The setup-tips box is always there, optional and unticked." App/tests/test_signup.py` (line 241). Old block (lines 241-244):

```
    # The setup-tips box is always there, optional and unticked.
    box = re.search(r'<input type="checkbox" name="onboarding_opt_out"[^>]*>', html).group(0)
    assert "checked" not in box and "required" not in box
    assert "No setup tips by e-mail" in html
```

New block:

```
    # The tips-and-news opt-in box is always there, optional and unticked.
    box = re.search(r'<input type="checkbox" name="marketing_opt_in"[^>]*>', html).group(0)
    assert "checked" not in box and "required" not in box
    assert "Send me tips and news by e-mail" in html
    assert "No setup tips by e-mail" not in html
```

6c. In `test_the_czech_form_reads_czech`, anchor `grep -nF 'assert "Bez tipů k nastavení e-mailem" in html' App/tests/test_signup.py`. Replace the line with:

```
    assert "Posílejte mi tipy a novinky e-mailem" in html
```

6d. In `test_signup_creates_an_inactive_account_that_cannot_sign_in`, anchor `grep -nF 'assert account["onboarding_emails_opt_out"] == 0' App/tests/test_signup.py` (line 290, the only match). Old block:

```
    assert account["onboarding_emails_opt_out"] == 0
    assert account["onboarding_emails_opt_out_at"] is None
    assert account["signup_utm_source"] == "google"
```

New block:

```
    # No opt-in box ticked: no tips or news (owner decision 2026-11-02).
    assert account["onboarding_emails_opt_out"] == 1
    assert account["onboarding_emails_opt_out_at"]
    assert account["signup_utm_source"] == "google"
```

6e. In `test_form_errors_keep_the_values_and_the_click_id`, anchor `grep -nF "                        opt_out=True)" App/tests/test_signup.py` (line 440). Change `opt_out=True)` to `opt_in=True)` on that line, keep the indentation. Then anchor `grep -nF "name=\"onboarding_opt_out\" value=\"1\" checked" App/tests/test_signup.py` (line 444). Replace the line with:

```
    assert re.search(r'name="marketing_opt_in" value="1" checked', no_accept.text)
```

6f. Anchor `grep -nF "def test_the_setup_tips_opt_out_is_stored_with_its_time():" App/tests/test_signup.py` (line 488). Old block (lines 488-502, both tests, ending at the line before the blank lines and `@pytest.mark.sqlite_only`):

```
def test_the_setup_tips_opt_out_is_stored_with_its_time():
    email = f"optout@{DOMAIN}"
    _submit(_client(), email, opt_out=True)
    account = _account(email)
    assert account["onboarding_emails_opt_out"] == 1
    assert account["onboarding_emails_opt_out_at"]
    # WP12 reads the same column: the lifecycle tips see the refusal, and the
    # Settings toggle starts switched off.
    assert lifecycle_mail.is_opted_out(account["id"])


def test_without_the_opt_out_box_the_setup_tips_are_allowed():
    email = f"optin@{DOMAIN}"
    _submit(_client(), email)
    assert not lifecycle_mail.is_opted_out(_account(email)["id"])
```

New block:

```
def test_without_the_opt_in_box_no_tips_or_news_are_sent():
    email = f"optout@{DOMAIN}"
    _submit(_client(), email)
    account = _account(email)
    assert account["onboarding_emails_opt_out"] == 1
    assert account["onboarding_emails_opt_out_at"]
    # WP12 reads the same column: the lifecycle tips see the refusal, and the
    # Settings toggle starts switched off.
    assert lifecycle_mail.is_opted_out(account["id"])


def test_the_ticked_opt_in_box_allows_tips_and_news():
    email = f"optin@{DOMAIN}"
    _submit(_client(), email, opt_in=True)
    account = _account(email)
    assert account["onboarding_emails_opt_out"] == 0
    assert account["onboarding_emails_opt_out_at"] is None
    assert not lifecycle_mail.is_opted_out(account["id"])


def test_a_host_who_skipped_the_box_can_turn_tips_on_later():
    email = f"tipslater@{DOMAIN}"
    _submit(_client(), email)
    account_id = _account(email)["id"]
    assert lifecycle_mail.is_opted_out(account_id)
    # The Settings toggle calls resubscribe (routes/admin_accounts.py).
    assert lifecycle_mail.resubscribe(account_id, actor="test")
    assert not lifecycle_mail.is_opted_out(account_id)
```

Check: `grep -n "onboarding_opt_out\|opt_out=" App/tests/test_signup.py 2>&1 | tail -30` prints nothing. Run Command 1 (section 6). Commit `0836 step 6`.

### Step 7: docs

7a. Anchor: `grep -nF -- '- Sign-up form: add an **unchecked** checkbox: "Do not send me setup tips by e-mail".' docs/UbyHost_workplan/04_legal_positions.md` (line 99). Insert one new line directly after line 99, no blank line between:

```
  - 2026-11-02 owner decision: signup box changed to unticked marketing opt-in; lawyer to confirm wording
```

Change nothing else in that file.

7b. `docs/context/decisions.md` is 3 tokens under its lint cap (2200), so two long lines are compacted first (same meaning, fewer words; precedent 0684), then one line is appended.

Line anchor 1: `grep -nF "Approval gates waived for the whole PostgreSQL and Go migration" docs/context/decisions.md` (line 57). Replace that whole line:

```
- 2026-10-31 | Approval gates waived for the whole PostgreSQL and Go migration; the bar stays (verified backup, rehearsal on a production copy, per-table counts and hashes, suite green on PG, SQLite as rollback, automatic rollback). Owner acts only where his hands are needed | owner | 0463
```

with:

```
- 2026-10-31 | Approval gates waived for the PostgreSQL and Go migration; the bar stays (verified backup, rehearsal on a prod copy, per-table counts and hashes, suite green on PG, SQLite and automatic rollback). Owner acts only where needed | owner | 0463
```

Line anchor 2: `grep -nF "D2 required reviewer on \`production\`; D3 goose (step 10)" docs/context/decisions.md` (line 58). Replace that whole line:

```
- 2026-10-31 | D2 required reviewer on `production`; D3 goose (step 10); D4 Postgres job table with `SKIP LOCKED`. D1: PostgreSQL self-hosted as a Compose service on the current 8 GB Lightsail server (socket, no port, 1 GB cap), not managed; nightly encrypted `pg_dump` in the existing backup, restore proven at every rehearsal; no pgBackRest | owner | 0463, 0464
```

with:

```
- 2026-10-31 | D1 PostgreSQL self-hosted in Compose on the 8 GB Lightsail (socket, no port, 1 GB cap), not managed; nightly encrypted `pg_dump` in the backup, restore proven each rehearsal; no pgBackRest. D2 required reviewer on `production`; D3 goose (step 10); D4 Postgres job table with `SKIP LOCKED` | owner | 0463, 0464
```

Then append this line as the new last line of the file (after `- 2026-11-02 | [workflow] Read hook: ...`), file ending with one newline:

```
- 2026-11-02 | Signup box: unticked marketing opt-in; lawyer to confirm | owner | 0836
```

Run Command 4 (section 6); it must print `context lint: OK`. Commit `0836 step 7`.

### Step 8: browser test and screenshots

Run Command 3 (section 6). Then from `App/`:

```
mkdir -p ../docs/tasks/screenshots-0836 && cp .pytest_cache/signup-pricing-shots/signup-pricing-en-390-js0.png .pytest_cache/signup-pricing-shots/signup-pricing-cs-390-js0.png ../docs/tasks/screenshots-0836/ 2>&1 | tail -30
```

Look at each screenshot once: the new label is visible and the box is unticked. Commit only those two files with `0836 step 8`.

## 5. Do not touch

- `App/app/signup.py` code (only the one comment line in Step 5), `App/app/lifecycle_mail.py` code (only the docstring in Step 5), `App/app/routes/admin.py`, `App/app/routes/admin_accounts.py`, `App/app/db.py`, migrations, `App/app/retention.py`.
- The Settings strings (`settings.account.onboarding_emails`, `flash.accounts.onboarding_emails_*`, `unsubscribe.*`) and the tip e-mail templates.
- `App/tests/test_lifecycle_mail.py`, `App/tests/test_signup_selection.py`, `App/tests/test_meta_capi.py`, `App/tests/test_signup_selection_browser.py`.
- `docs/UbyHost_workplan/04_legal_positions.md` beyond the one line of Step 7a; `docs/context/decisions.md` beyond Step 7b; `docs/context/status.md`.

## 6. Commands

From `App/`:

1. `.venv/bin/python -m pytest tests/test_signup.py tests/test_signup_selection.py tests/test_meta_capi.py tests/test_lifecycle_mail.py -q --tb=short -x 2>&1 | tail -30`
2. `.venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py -q --tb=short -x 2>&1 | tail -30`
3. `.venv/bin/python -m pytest tests/test_signup_selection_browser.py -q --tb=short -x -rs 2>&1 | tail -30` (must pass with 0 skipped)

From the repo root:

4. `python3 scripts/context_lint.py 2>&1 | tail -30`

## 7. Acceptance

- [ ] The sign-up page shows the new label in EN, CS and VI, unticked, not required; field name `marketing_opt_in`.
- [ ] Unticked sign-up stores `onboarding_emails_opt_out = 1` with a time; ticked stores `0` and `NULL`.
- [ ] A form error re-renders the box ticked if it was ticked.
- [ ] `grep -rn "onboarding_opt_out" App/app App/tests --include=*.py --include=*.html` lists only `App/app/signup.py` (the `register` parameter and its use) and the `onboarding_opt_out=not marketing_opt_in,` line in `App/app/routes/signup.py`.
- [ ] Commands 1 and 2 pass; Command 3 passes with 0 skipped; Command 4 prints `context lint: OK`.
- [ ] Two 390 px screenshots in `docs/tasks/screenshots-0836/` (EN and CS sign-up).

## 8. Stop and ask

- Any `grep -nF` anchor in section 4 finds nothing or more than one match where one is expected.
- A test outside `App/tests/test_signup.py` fails because of the new default (for example it expects tips allowed after a form sign-up): stop, name the test, do not edit it.
- Command 3 reports any skipped test, or Playwright or a browser is missing.
- Command 4 reports `docs/context/decisions.md` over its cap or any other error.
- `lifecycle_mail.resubscribe` returns False in the new test.
- A test fails twice after one fix.

## 9. Report

Write `docs/tasks/0836-report.md` (600 tokens at most): files changed, each section 6 command with its last 5 lines, section 7 ticked, Deviations, Questions, links to the two screenshots. Then set this brief to `Status: review`. Do not push; the orchestrator updates PR #729.
