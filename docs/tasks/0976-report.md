# 0976 report: Guide audience verification (B18)

Status: review

## Files changed
- App/tests/test_0976_audience_matrix.py (new, 4 tests)
- App/tests/test_0976_audience_browser.py (new, 1 test, synthetic data only)
- docs/tasks/0976-report.md (this file)
No production file under App/app/ changed.

## Matrix (Keys card, guide live, synthetic text; test-verified)

| Stored audience | Editor shows | QR door `/g/...` | Stay door inside window | Stay door outside window |
|---|---|---|---|---|
| everyone (fresh-card default) | Everyone with the QR code | readable | readable | readable |
| booked | Booked guests during their stay | hidden | readable | hidden |
| host | Only you | hidden | hidden | hidden |

Anchors A1 to A11: all found verbatim except A7 (see deviations).

## Results
- Command 1 (matrix): 4 passed. EDITOR_DEFAULT everyone.
- Browser (command 2): 1 passed, 0 skipped. Editor value `everyone`; QR default shows text; after booked, QR hides it; stay door inside window shows it.
- Command 3 (guest guide + matrix): 127 passed, 0 skipped.
- Command 4 (`tests/test_guest_*.py`, browser required): 568 passed, 0 skipped, exit 0. Last lines: `568 passed, 9 warnings in 805.72s (0:13:25)`.
- Lint (`python3 scripts/context_lint.py`): OK, warnings only.
- Tracked PNG `docs/tasks/screenshots-0402/guide-table-1280.png` changed by a test run: reverted with git checkout. Not staged.

Displayed default matches effective authorization: yes.
Leak reproduced: no.

## Screenshots (390 px, /tmp/ubyhost-b18)
- 0976-editor-keys-default-390.png: select shows "Everyone with the QR code". It sits after Video link (empty) and above the Save and next card / Save buttons, with the helper text "Codes and anything private should be for booked guests only." under it. Synthetic text not present (fresh card, not yet saved). Nothing clipped; a mobile tab bar and a sign-in panel overlay the lower page.
- 0976-qr-default-390.png: QR door shows "Keys and getting in" with the synthetic text. Nothing clipped.
- 0976-qr-booked-390.png: QR door, Keys card absent; other cards visible. Nothing clipped.
- 0976-stay-booked-390.png: stay door, "Back to your stay", Keys card shows the synthetic text. Nothing clipped.

## Deviations
- Branch codex/0976-b18-audience (existing) was used, not task/0976-audience-verification.
- Anchor A7 is verbatim only in App/app/guide_facts.py:141. App/app/guest_guide.py:304 has the same condition without the `guest_guide.` prefix.
- The browser test needed GUEST_PIN_REQUIRED off and mail disabled (monkeypatched).
- A background run of command 4 had not finished; it was rerun with a fresh DB (db-cmd4-rerun.sqlite).

## Owner policy decisions (unchanged from brief; not implemented)
1. Default for new access cards: `booked`. Which kinds count as access cards (keys, garage, checkin, wifi?).
2. Existing cards: leave untouched (brief recommends) or offer a one-time host prompt.
3. "Explicit at Save": required choice with no preselected option, or preselected `booked` with the choice visible beside the content.
4. Whether a code-like pattern in the text should warn when `everyone` is chosen.
