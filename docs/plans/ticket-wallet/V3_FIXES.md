# Ticket Wallet v3: what broke in v2 and how it is fixed

v2 was merged in #199 and reverted from `main` on 30 Sep 2026 after a real
walkthrough. This branch puts it back with the fixes below. Every item was
found by driving the guest flow in Chromium, and every one is now checked by
`App/tests/test_guest_browser_e2e.py` (browser) and
`App/tests/test_ticket_wallet_v3.py` (markup). The browser test fails on the
v2 code for each of the first three.

| # | What the guest saw | Root cause | Fix |
|---|---|---|---|
| 1 | "How many people are staying?" opened **empty**; tapping + once gave 1, so a family registered one person and was told they were done. | `value="{{ claim.declared_guests or '' }}"`, and the stepper treats an empty box as "below the minimum". | The box always starts with a number: declared, else the host's override, else 1 (claim page, stay page and first form). |
| 2 | The pad said "✓ Signed" but **Submit failed**: "That signature could not be saved". | `signature.js` sized the canvas on every window `resize`. Phones fire one when the keyboard opens, while the signature step is still hidden, so the canvas became 0 × 0. Drawing on it produced `data:,`. | The pad ignores a resize while it is hidden, sizes itself when its step is shown (and via `ResizeObserver`), never saves an empty canvas, and "Signed" only shows for a real image. |
| 3 | After the first person, only a small "Add a person" in a second card. It was easy to miss, so it looked finished. | Two tickets; the button did not say who was next. | The saved ticket carries one button that names the person: **"Register guest 2 of 3"**. The form strip says "Guest 2 of 3" on every step. |
| 4 | Date of birth sat a line **lower** than Nationality beside it, and flush against Surname on a phone. | A second row of "Day / Month / Year" labels above the boxes; `.g-field:last-child` dropped the margin inside a row. | Boxes on one line with DD/MM/YYYY placeholders and `aria-label`s; one 20px rhythm between all fields. |
| 5 | Tracker read "DetailsDone", "Document…". | `signature.js` marks finished steps with `class="sr-only"`, which the guest CSS never defined. | `.tw .sr-only` is visually hidden. |
| 6 | Back and Continue stacked as two full-width buttons in the sticky bar, covering the field being typed in. | `flex: 1 1 160px` wrapped at phone width. | One line: compact Back, wide Continue. |
| 7 | A new step opened with its strip and heading under the app bar. | `scrollIntoView` ignores sticky bars. | `scroll-margin-top` / `scroll-padding` on the page. |
| 8 | Dates shown twice (app bar and a card), "3 nights · Person 1 of 3" floating above the tracker. | Leftovers from the pre-ticket layout. | Hidden under `.tw`; the app bar is the one place for dates. |
| 9 | Photo step: "Take photo" and "Retake or choose another" squashed into circles. | Two pill buttons side by side, text wrapping to three lines. | Stacked, full width. |
| 10 | At 320px the language switch wrapped and the app bar grew to 128px; the stamp animation pushed the page sideways. | Title took its full text width; stamp started at 1.8×. | Title shrinks with an ellipsis; stamp starts at 1.3×; `body.tw { overflow-x: clip }`. |
| 11 | Czech passes said "CHECK-IN / CHECK-OUT". | CS dictionary kept the English words. | "Příjezd / Odjezd". |
| 12 | Desktop: two dashed lines down the page edges. | Decorative background. | Removed. |

Cache keys for `guest-ticket.css`, `ticket.js` and `signature.js` are bumped to
`20260930a`, so phones that cached v2 fetch the fixed files.

QA screenshots of the fixed flow (group of three, EN and CS, 375px, plus
desktop) are in `qa/`.
