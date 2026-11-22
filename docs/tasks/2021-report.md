# 2021 report — the 1820 screenshot tool works again

Status: review (both defects fixed; a third, worse defect found: one-shot state poisoned every logged-in comparison)

## Files changed

- `App/scripts/go_page_parity_screenshots.py`
  - `App/` is put on `sys.path` at import time, so the **documented** invocation
    (`python scripts/go_page_parity_screenshots.py …`) works without `PYTHONPATH`.
  - `ensure_go_running("http://127.0.0.1:1")` — positional, matching the real
    signature `ensure_go_running(public_base_url: str) -> str`. The kwarg
    `public_base=` did not exist and the call was the `TypeError` at every run.
  - New `--pre-sql` (repeatable): statements run **before each stack renders**,
    through `app.db.execute` (rule 5). See the third defect below.

## Commands (last lines)

```
cd App && .venv/bin/python -m pytest tests/test_go_page_parity_screenshots.py -q -x
2 passed, 1 skipped in 0.12s

# anon page, the brief's own smoke case
scripts/go_page_parity_screenshots.py --name smoke-login --path '/login?lang=en' \
  --out /tmp/parity-2021 --widths 390 --fail-on-visible
390px: identical (max_delta=0, diff_pixels=0)
```

Host page (minted session for the seed host, `POST /account/security-prompt/seen` visible in the log):

```
scripts/go_page_parity_screenshots.py --name pre-sql-reservations --path '/reservations' \
  --cookie-name ubyhost_session --cookie-value "$TOK" --widths 390,1280 \
  --pre-sql "UPDATE user_account SET two_factor_prompted_at = NULL"
390px: identical (max_delta=0, diff_pixels=0)
1280px: identical (max_delta=0, diff_pixels=0)
```

## The third defect, and why `--pre-sql` exists

The first honest run of the fixed tool reported:

```
390px:  visible  (max_delta=229, diff_pixels=350700)
1280px: identical (max_delta=0, diff_pixels=0)
```

for `/reservations`, a page the DOM audit calls character-identical (2599/2599). The
side-by-side showed Python rendering the **"Add a second way in?"** dialog over a dimmed
page while Go rendered the page itself.

It was not the page. `templating._security_prompt` (`App/app/templating.py:675`) shows that
dialog once, on the first app page after login, to an account with no passkey and no TOTP,
and `app.js` marks it seen by `POST /account/security-prompt/seen`, which sets
`user_account.two_factor_prompted_at`. **Python and Go share one database here**, so the
stack that rendered second never saw the prompt. Every logged-in comparison would have
been poisoned this way, in whichever direction ran second — and `1280` looked clean only
because the flag was already set by then.

With `--pre-sql` resetting the flag before each capture, both stacks render the prompt and
the page compares `identical`. Use it for any one-shot state; it is deliberately generic,
so the tool learns nothing about app internals.

## Acceptance

- Both invocations from the brief's §1 run; plain and `-m`.
- PNGs plus `parity-report.json`/`.md` with a verdict per width.
- `--fail-on-visible` returns 1 only on `visible` (checked by the passing tests).
- Real verdicts on one anon page and one host page — pasted above.

## Deviation

`--pre-sql` is beyond the brief's §4. Without it the tool produces confident false
positives on the majority of pages (any page that shows a one-shot prompt), which would
have been worse than the tool not running at all. Nothing under `App/app/` was touched.
