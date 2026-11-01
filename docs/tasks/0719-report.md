# 0719 report (executor)

Status: blocked (partial). Second executor session: page-scroll fixed, Menu tab fixed; steps 2b to 7 not done. Not pushed.

## Commits (branch task/0719-v2-overview-phone)
- fac1d49 step 1: top row, badge, need cards (class `need`, `b.t`, `small`), phone margins removed, main padding 20 px below 1024 px.
- dda742c step 1b and e0e510e: dashboard tests follow the new markup; ruff F401 removed from test_0718_menu_page.py.
- bfe7824 step 2: calendar hidden below 1024 px, "Kalendář" link, `.hs` today cards, table hidden on phone.
- 3a and 3b commits: `.hs` width guard, chip and round reset, key 20261101-0719b, manifest written.

## Test tails
- `ruff check ... --select E9,F63,F7,F82,F401,F841`: All checks passed.
- test_0520 and test_0718_menu_page: 8 passed.
- Brief set (before the chip/round commit): `15 failed, 26 passed in 208.87s`, 0 skipped.
  Failures: page-scroll at 390 px (dashboard, scrollWidth 432), at 320 and 640 px, menu at 320 px (scrollWidth 364), and a "Check-in KKarlin Loft" card reported outside the 390 px box.
- A DOM probe at 390 px found no element whose box extends past 390 px, so the cause of the 432 px scrollWidth is not yet known.

## Departures from the mockup
- Card name is the stay label (internal name or manual summary), not a guest name: today_rows carries no guest name.
- Today card meta shows nights and guests, without the property name (not in today_rows).
- Needs-you neutral tone maps to `.ic.acc`. Non-first button is `btn sm ghost line`.
- The "nothing needs you" calm card shows whenever needs-you is empty, styled as `.allgood`, even when stays are listed today.
- Greeting stays the page title (no first name stored). ov-how and ov-links stay visible below 1024 px (not in mockup).
- Desktop `b.t` and `small` are neutralised to the old div/p look. Desktop was not checked visually.
- Phone side padding is 20 px on all v2 pages; phone 20 px margins on card, sec, sub, list, grp, facts, allgood removed.
- Menu name: ellipsis via CSS only, no markup change.

## Not done
- v2_mockup.py phone_selectors additions and missing_ok reasons.
- The 768 style test change in test_0710.
- Screenshots in docs/tasks/screenshots-0719/.
- Resolve the page-scroll failures above.

## Owner steps left
None.


## Second session (continued at the call limit)
- Commit c6c1410 (step 1): page width. Cause at 390 px: `.card.needs-you-card-item` stayed `display:grid` (desktop rule has higher specificity), so `.needs-you-actions` got a 0 px column and its nowrap button overflowed. Fixed with phone rules `body.v2 .card.needs-you-card-item{display:block}` and `.needs-you-actions{width:100%}`. Menu at 320: `.me-link` and `.who` had no min-width:0; name ellipsis added (`.who b` block). Probe (temporary, removed): document scrollWidth now equals the viewport at 320, 390 and 640 on `/` and `/menu`. `.hs` scrolls inside itself (312/280 at 320).
- Commit 090ba69 (step 2a): `_shell_v2.html` Menu tab is on for nav in menu, cleaning, stay_fees, payments, settings.
- Not run in this session: the brief §6 test set, test_0718_menu_page, ruff. The first session's last full run was 15 failed (all page-scroll and card-box cases); the scroll cases should now pass, the card-box case is not re-checked.
- Left: step 2b (v2_mockup.py: `.actbar .btn` alias to `.bar .btn`, `.actbar` padding-bottom and height override with the reason); step 3 (overview phone_selectors and missing_ok, the 768 style-only rule in test_0710); step 4 (tests and ruff); step 5 (app2.css key 20261101-0719c in base.html, `tests/test_static_versions.py --write`); step 6 (screenshots in docs/tasks/screenshots-0719/ and the lints); step 7 (this report's test tails).
- Owner steps left: none.
