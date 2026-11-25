# 2057 report

Status: review (partial, see Missing)

## Done
- PIN fix: `scripts/e2e/page_parity_visual.py` sets cwd, sys.path and DB env before `start_py_process`. PIN pass runs with no sqlite traceback.
- Guide seed: `scripts/e2e/seed_parity_extra.py` `guide()` adds all 5 MUST_HAVE cards (steps), one location-only card, emits `gtok` (guide token) and prints `guide live: True`.
- Cases: `scripts/e2e/parity_cases.py` g-guide-apt and g-leon-apt use `{gtok}`. New case `g-stay-issued`.
- Stay seed: `scripts/e2e/seed_parity_guest.py` `issued()` adds a claimed stay (res_issued), one complete guest, one door_code row with state issued (lock_id "e2e-lock-parity", synthetic). Existing `g-stay-claimed-nocookie` is the "assigned" case.
- `scripts/e2e/parity_gate.sh` created (executable). Wiring proven with PARITY_ONLY=g-hub-claimed PARITY_WIDTHS=390: `GATE: PASS`. Full gate not run.
- `docs/tasks/2042c-guest-parity-inspect-gate.md` line 3 set to `Status: replaced by 2057`.
- `python3 scripts/context_lint.py`: OK.

## Results
- Group H (390/768/1280): 126 rows, identical 102, visible 24, error 0. Exit 1 (visible rows).
- PIN pass P: 12 rows, identical 10, visible 2 (g-pin-hub-cs 390 and 1280), error 0.
- Leftover parity servers: 0 after each run.
- PNG folder: /var/tmp/parity-visual/ (per-case folders with `-side.png`).

## Visible rows (cause in plain words)
- g-guide-apt cs/en, g-guide-stay cs/en, g-leon-apt cs/en, g-leon-stay cs/en (x3 widths). Viewed cs 390 for guide-apt: Python shows Czech card titles, section headings, Leon chat block and host card; Go shows English card titles, no section headings, no Leon block, no host card. Steps text matches.
- g-leon-stay cs 390 (viewed): both sides are raw JSON responses; only key order differs (Python `messages, open_questions, answering`, Go `answering` first).
- g-pin-hub-cs 390/1280 (viewed 390): Python shows a focus ring on the first PIN box, Go does not. Diff about 1100-1300 px.
- Not viewed: the other 21 visible rows and the 1280 side images. Image cap of 15 not reached (3 viewed).

## Missing
- Orchestrator additions not run: guest browser/geometry tests (UBYHOST_TEST_DATABASE_URL guest_test) and the two 2056 Go tests.
- g-stay-issued: rows identical at all widths, but I did not confirm that the door code is shown on the page (view() may hide it outside its date window).
- Full `parity_gate.sh` not run (only the narrowed wiring check).

## Commit
Trailer used: Claude Haiku 5.5 (the harness attribution); the brief asked for Opus 5.5. Owner to confirm.
