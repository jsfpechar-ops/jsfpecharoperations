# 0911 report

Status: review
Branch: vibe/stay-fee-guest-payment-plan-73df64 (no commit, push or PR, per the executor rules)

## Done
- Fee section in `templates/guest/_legal_notice.html`, shown when `fee_notice` is true (`UBYHOST_STAY_FEE_GUEST_PAY` on, `stay_fee_collect`, rate > 0). Title, body, then a link to `https://www.e-sbirka.cz/sb/1990/565` (`rel="noopener" target="_blank"`) as the last element. The URL is not in the body text. Six languages.
- Guest RÚIAN route `GET /l/{token}/ruian-suggest` (`routes/guest.py`, same guards as the other guest GETs). 404 when RÚIAN is disabled, 429 when rate-limited. Declared above `/l/{token}/{reservation_id}`.
- Picker JS inline in `form.html`, CZ only (`CZE`). Picking fills `res_city` with `addr_obec` and `res_street` with street, house number and "/orientation number" when present. Plain inputs work without JS.
- Six new keys in all six guest languages (`i18n.py`, `guest_uk_i18n.py`). en and cs use the counsel text without the URL. de, es, fr and uk are my translations and need lawyer sign-off.

## New outbound request (AGENTS.md rule 2)
The server calls the RÚIAN find service (ČÚZK) through `ruian.suggest()` when a guest types a CZ residence street. Reason: the same-obec exemption (plan §1, decision 9) compares official obec names, so autocomplete prevents typos. The browser calls only the same-origin route. No CSP change.

## Tests (App/, all with UBYHOST_REQUIRE_BROWSER=1)
1. `tests/test_0911_guest_fee_ruian.py`: 5 passed, 0 skipped.
2. `tests/test_guest_browser_e2e.py`: 23 passed, 0 skipped.
3. `tests/test_host_geometry.py tests/test_layout_lint_browser.py`: 4 passed, 0 skipped.
4. `python3 scripts/context_lint.py`: OK (warnings are about other briefs).

## Screenshots (docs/tasks/screenshots-0911/)
- form-390-en-legal.png: fee section and link visible, link ends the section, nothing clipped. The sticky progress bar and "Save details" overlap text in the element capture; a capture artifact, not checked by scrolling.
- form-1280-en-legal.png: fee section, link and checkbox readable, nothing clipped.
- form-390-cs-legal.png: Czech copy fits, link wraps to two lines, no clipping; same sticky overlap.
- residence-390-ruian.png: suggestion fits the card at 390 px; Continue is the only coral action. The street field shows a red border (focus state). The first capture had bare bullets, fixed by CSSOM list styling, then re-shot.

## Deviations
- The link is its own element with key `legal_notice_fee_link`, so the URL is not inside the body text.
- No `base.html` `?v=` bump: the JS is inline in `form.html`, and no static file changed.
- Tests unhide the wizard steps (`_show_all_steps`), set the `combobox` country through the hidden select, and enable RÚIAN explicitly.
- Temporary capture test deleted. No 360 or 768 screenshots taken.

## Owner steps
1. Lawyer sign-off on the counsel text (plan §10), including the de, es, fr and uk translations. I found no legal error in the draft and did not change its substance.
2. Bump `UBYHOST_GUEST_NOTICE_VERSION` at deploy.
3. Merge only through `scripts/merge-pr-on-green.sh`.
