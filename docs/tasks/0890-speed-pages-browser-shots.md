# 0890: Speed briefs: browser and geometry at 7 widths, end-to-end taps, 390 px screenshots

Status: todo
Depends on: 0845, 0846, 0847, 0848, 0849, 0888, 0889 merged (and #707, 0836) | Base commit: main after them | Branch: task/0890-speed-pages-browser
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

One browser test file that seeds a host with real stay-fee, invoice and housebook data and checks every new control of 0848, 0849, 0888 and 0889 at 320, 390, 768, 1024, 1280, 1440 and 1920 px (the shared `geometry_findings` plus a 12 px neighbour check), walks the fast paths end to end, and writes one 390 px screenshot per changed page. No app code changes.

## 2. Context

- Rule 7: template/CSS changes need browser and geometry tests with 0 skipped and a 390 px screenshot per changed page. The 0710 suite (`tests/test_0710_v2_mockup_match_browser.py`) stops at 1440 and uses a fixture without fee periods; this file adds 1920 and seeded data.
- Rule 1: never press a police send button or call `/reservations/*/submit`; the test asserts no such request (`page.on("request", ...)`). Stay-fee sealing in the seeded test database is allowed.
- Reusable, verified:
  - `App/tests/test_host_quiet_dashboard_browser.py`: `_launch(playwright)` (line 170), `sync_api`; its `base` fixture (lines 153-168) starts uvicorn in a thread: copy that body into your own `base(speed_host)` fixture.
  - `App/tests/test_0710_v2_mockup_match_browser.py`: `_open_app(browser, base_url, cookie, path, width)` (adds the session cookie, opens `path?lang=en`, closes the security prompt). Import it: `from tests.test_0710_v2_mockup_match_browser import _open_app`.
  - `App/tests/v2_mockup.py`: `geometry_findings(page, width) -> list[str]`.
  - Seeding: stay-fee property and signed guest as `_property`/`_stay` in `tests/test_stay_fee_finalize.py` (lines 59-93); invoice entity as `_add_entity` in `tests/test_invoice_autofill.py`; stays via `tests/invoice_stay_helper.make_stay`.
- Selectors: `.fee-bulk`, `.fee-copy`, `form[action="/stay-fees/confirm-ready"] button`, `a[href^="/stay-fees/pdfs.zip"]`, `.invoice-quick-stays a`, `[data-use-price]`, `input[name="stay_price"]`, `.housebook-presets a`. The confirm dialog of `data-confirm` is accepted with `[data-confirm-proceed]` (`App/app/static/app.js` around line 1428).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_0890_speed_pages_browser.py` | new | Fixture, 3 tests |
| `docs/tasks/screenshots-0890/*.png` | new | 4 screenshots at 390 px |
| `docs/tasks/0890-report.md` | new | Report with the tap table |

No other file may change. If a geometry finding needs a CSS fix, STOP and report it (a fix brief follows), do not edit CSS.

## 4. Steps

1. Fixture `speed_host` (function scope is fine): unique username `speed-0890-<token_hex(4)>`, `auth.create_account(..., role="host", username=...)`, one `legal_entity` (fields of `_add_entity` in `test_invoice_autofill.py`, `owner_user_id` = the new id). `prev = stay_fee.previous_month(claim.prague_today())`. Two fee properties `Fee A`, `Fee B` (`addr_obec="Praha 3"`, `active=1`, fee fields as `_property` in the finalize test), each with one reservation `prev.replace(day=10)` to `prev.replace(day=14)` and one signed guest; one property `Fee C` with `addr_obec="Praha 3"`, `active=1`, rate 0. Invoices: `s1 = make_stay(owner, entity_id=entity)`, issue one invoice for it with price `2500` and `paid_via="cash"` through a logged-in `TestClient` POST to `/invoices` (pattern of `test_issue_for_a_stay_prints_the_stay` in `tests/test_invoice_stay_pages.py`), then a second reservation `s2` in `s1`'s apartment ending 9 days ago (`uid` with `invoice_stay_helper.UID_PREFIX`). Yield `{"client", "cookie", "owner", "entity", "s2", "fee_ids", "month": stay_fee.month_key(prev)}`; cleanup deletes invoice items and invoices (with the `invoice_purge_unlock` setting as `_cleanup` in `test_invoice_autofill.py`), `drop_stays`, filings, guests, reservations, apartments, entity, audit, user. Commit `0890 step 1`.
2. `test_speed_pages_geometry` parametrized over `WIDTHS = (320, 390, 768, 1024, 1280, 1440, 1920)` and four paths: `/stay-fees?month=<month>`, `/invoices/new`, `/invoices/new?reservation_id=<s2>&entity=<entity>`, `/housebook`. For each: `geometry_findings(page, width) == []`; the page's new element (`.fee-bulk` and `.fee-copy`, `.invoice-quick-stays`, `[data-use-price]`, `.housebook-presets`) is visible, `scrollWidth <= innerWidth` for `document.documentElement`, and, with `page.evaluate`, every pair of `a, button` children inside it whose boxes share a row is 12 px or more apart horizontally, and every pair stacked in one column is 12 px or more apart vertically (allow 0.5 px). Commit `0890 step 2`.
3. `test_speed_paths_end_to_end` at 390 px, counting taps in a list:
   - Stay fee: open `/stay-fees?month=<month>` (tap 1), click the confirm-all button (2), click `[data-confirm-proceed]` (3); the page shows `Periods saved: 2`; the `pdfs.zip` link is visible; `page.expect_download()` around its click (4) gives a file ending `.zip`; both `stay_fee_filing.latest(id, <month>)` exist. Then on `.fee-copy`, click `Use this setup` (5): `Fee C`'s `stay_fee_rate_czk` equals `Fee A`'s.
   - Invoice: open `/invoices/new` (1), click the quick link for `s2` (2), click `[data-use-price]` (3): `input[name="stay_price"]` value is `2500`; `#paid_via` value is `cash`. Do not issue.
   - Housebook: open `/housebook` (1), click `Last month` (2): URL has `from=` and `to=`.
   - Throughout, `page.on("request")` collects URLs; assert none contains `/submit`.
   Record the tap counts in the report. Commit `0890 step 3`.
4. `test_speed_screenshots`: returns early unless `UBYHOST_SHOTS_DIR` is set (same rule as the 0710 screenshot test); otherwise writes `stay-fees-390.png`, `invoice-picker-390.png`, `invoice-form-390.png`, `housebook-390.png` (full page, 390x844) into that folder. Run §6 command 2. Commit `0890 step 4`.
5. Run §6 commands 1 and 3. Commit.

## 5. Do not touch

All app code, templates, CSS, other tests. Police send routes and buttons.

## 6. Commands

From `App/`:
1. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0890_speed_pages_browser.py -q --tb=short -rs 2>&1 | tail -30` (0 skipped)
2. `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=../docs/tasks/screenshots-0890 .venv/bin/python -m pytest tests/test_0890_speed_pages_browser.py -k screenshots -q --tb=short -rs 2>&1 | tail -30`
3. v2 row: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "stay_fees or housebook" -q --tb=short -rs 2>&1 | tail -30`

## 7. Acceptance

- [ ] 28 geometry cases pass (4 pages x 7 widths), 0 skipped.
- [ ] End-to-end: stay fee 5 taps for 2 properties incl. ZIP and copy; invoice 3 taps to a filled form; housebook 2 taps; no `/submit` request.
- [ ] Four screenshots in `docs/tasks/screenshots-0890/`.

## 8. Stop and ask

Stop, and write the report, if a selector is missing (a brief did not land); a geometry finding needs CSS; a test fails twice; you reach 25 tool calls or about 50k tokens; you need push, merge, secrets, SSH or deploy.

## 9. Report

`docs/tasks/0890-report.md` (600 tokens at most), `Status: review`: files, command tails, the measured tap table (fill the "after" column of `docs/tasks/0843-speed-overview.md` §2 in the report, not in that file), screenshot paths.

## Risk list (for the reviewer)

`App/tests/test_0890_speed_pages_browser.py` (cleanup complete; no police request).

## Owner steps

1. Look at the four 390 px screenshots, then merge with `scripts/merge-pr-on-green.sh <pr>` when CI is green.
