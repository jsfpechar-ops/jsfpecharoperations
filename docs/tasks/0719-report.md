# 0719 report (executor)

Status: blocked. Stopped at the call limit with browser failures open. Not pushed.

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
