# 1089 report: under-15 guests do not sign (server half)

Status: review

## Files changed

Section 3 files only, plus `App/app/host_vi_i18n.py` (see Deviations). New: migrations `0043` / `00014`, `App/tests/test_under15_signature_1089.py` (23 tests), `docs/tasks/screenshots-1089/housebook-{390,768,1280}.png`.

## Commands (last line each)

- A1: `16 passed, 59 skipped` (the skips are the Postgres-only tests: no Postgres in this sandbox; CI runs them).
- A2: `83 passed`.
- A3: `79 passed`.
- F: as written, `13 failed, 139 passed`, all 13 in `test_endtoend.py`; clean `origin/main` (39962ad7) gives the identical `13 failed, 139 passed` with the same command (test-order pollution, not this change). Split: the F files without `test_endtoend.py` `124 passed`; `test_endtoend.py` alone `28 passed`.
- S: `104 passed`. Also `test_host_i18n.py test_go_host_i18n.py`: `16 passed`.
- U: `6 passed in 267.98s`, 0 skipped (`UBYHOST_REQUIRE_BROWSER=1`).
- G: `ok` for `internal/validation`, `internal/ubyport`, `internal/calendar`. `golden.json`: 228 insertions, 0 deletions (eleven new cases after review attempt 2).
- `scripts/context_lint.py`: `context lint: OK`.

## Screenshots (house book, signed-for child)

- 1280: popover open, "Signed: By an adult" as a green pill on one line, inside the card, nothing clipped.
- 768 and 390: the register is a card list at these widths and the Details column is hidden by the existing CSS, so the popover (and the pill, old or new) cannot be opened there; the screenshots show the unchanged card list, no overflow. Finding for the orchestrator, not fixed here (no CSS change allowed).

## Acceptance (section 7)

- [x] Migration pair additive, pins at 43, table counts unchanged, A1 green (SQLite half).
- [x] Under 15: no signature issue in Python and Go; 15 to 17 and adults unchanged; golden gains eleven cases (eight briefed, three from review); G green.
- [x] A child's form saves without a signature and stores none; `submit_state` as today.
- [x] Adult links: both orders, this device only, 18+ with own drawn signature, valid role, first wins; filing columns untouched; remove clears.
- [x] Host send and stay fee counts; S green.
- [x] "Signed by" only while the adult row is valid; corrected to 15+ loses the link.
- [x] Pill for the two values; U green, 0 skipped; three screenshots (see the 390/768 finding).
- [x] Filing unchanged (9c); `git diff origin/main -- App/app/ubyport go/internal/ubyport App/tests/golden` empty. F: see above.
- [x] CSV and PDF show the two sentences.
- [x] Retention line in three places; A3 green.
- [ ] Diff touches only section 3 files: one extra, `host_vi_i18n.py`.

## Deviations

1. `host_vi_i18n.py` also holds `housebook.signed`; the brief gave no Vietnamese. Added `Do người lớn ký` / `Không bắt buộc (dưới 15 tuổi)` so no catalog lacks the keys. Please check the wording.
2. PDF: the "Signed by ..." sentence is 775 pt wide at 9 pt (page 595 pt), so it is wrapped above the rule, and it is not repeated on the grey line, where it would run into the right-aligned reporting status. The short exempt sentence is drawn in both places as briefed.
3. An empty signature reads back as NULL through the encrypted column, so the tests assert "no signature stored", not `== ""`.
4. Route tests use the stay's real arrival (today) with birth years well away from the boundary; the boundary itself is tested with fixed dates.
5. `validation._birth_bounds` is a small shared helper for the two age functions.
6. Go `certainlyUnderAge` reads the stored value without `normalise_birth_date`; a non-8-digit stored date is incomplete in both ports anyway.

## Questions

- Should the house book facts be reachable at 390/768 (a follow-up brief)?

## Owner steps left

- None (deploy.sh applies goose 00014 automatically). No PR opened yet (fresh review first).
