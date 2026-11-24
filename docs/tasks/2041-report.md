# 2041 report: parity seed extension and populated host pages

Status: blocked

Blocked at the executor tool-call cap (30). Ran groups E, F, G and committed the seed and harness. Not done: image review of the visible rows (no causes written), `context_lint`, and the pytest file. Owner or orchestrator: review the visible PNGs listed below and run lint/pytest.

## Files changed

- `scripts/e2e/seed_parity_extra.py` (new): extra synthetic data, run on `parity_run` after `seed.py`. Each block in its own try/except, skipped blocks printed to stderr.
- `scripts/e2e/parity_cases.py`: `GUIDE_QUICK_STEPS`, `EXTRA_CASES` (groups E, F, G, 25 cases). Removed `invoices-new-picker` and `settings-tab-account`: no such variant (the route has no `step` or `tab` parameter). Used `range=past` for reservations.
- `scripts/e2e/page_parity_visual.py`: `run_extra_seed()` after `audit.seed_db()`, `fill()` takes `extra`, `table_cases()` iterates `CASES + EXTRA_CASES`, `anon_invite` persona (no cookie), missing placeholder prints `SKIPPED (seed block missing)`.

## Seed blocks

- Worked: guide (4 cards, 2 done, 2 missing, 1 custom card), cleaning (3 events, 1 share), havel (gaps; no stats, `STAT_KINDS` not defined), submissions (draft and sent), second apartment (`property_id`), unsubscribe token.
- Skipped (named on stderr):
  - `questions`: no `guest_chat` row in the seed (`NoneType` error). Rows `guide-question` and the question placeholder are SKIPPED.
  - `leon`: no Leon settings table or insert helper found in the baseline. Leon pages render unconfigured.
  - `privacy`: no privacy request table or helper found. `privacy-requests-full` shows the seed's empty state.
  - `invite`: no account invite table or helper found. `account-accept` is SKIPPED.
- Not seeded from the brief: guide "check" and "skipped" states, quick-answer rows.

## Verdicts (harness counts)

| group | rows | identical | invisible | visible | error | skipped |
|---|---|---|---|---|---|---|
| E | 60 | 41 | 1 | 18 | 0 | 6 (account-accept) |
| F | 66 | 51 | 0 | 15 | 0 | 6 (guide-question) |
| G | 12 | 12 | 0 | 0 | 0 | 0 |
| **total** | **138** | **104** | **1** | **33** | **0** | **12** |

Accepted: 0 (no `ACCEPTED` key matched these cases).

Visible rows, not described (no image review):
- Group E, all at 390/768/1280: `submissions-full` cs/en, `submission-draft` cs/en, `submission-sent` cs/en.
- Group E, invisible at 390: `cleaning-edit-en`.
- Group F: 15 visible rows. Their names and side PNGs are in `/var/tmp/parity-visual/report-F.md`, not read here.

## Folders

- Side-by-side PNGs: `/var/tmp/parity-visual/<case>/<case>-<width>-side.png`
- Harness reports: `/var/tmp/parity-visual/report-E.md`, `report-F.md`, `report-G.md`
- Logs: `/var/tmp/parity_E.log`, `/var/tmp/parity_F.log`, `/var/tmp/parity_G.log`

## Commands and last lines

- Group E (2 min 23 s): `{"rows": 60, "verdicts": {"identical": 41, "invisible": 1, "visible": 18, "accepted": 0, "error": 0}}`
- Group F: `{"rows": 66, "verdicts": {"identical": 51, "invisible": 0, "visible": 15, "accepted": 0, "error": 0}}`
- Group G: `{"rows": 12, "verdicts": {"identical": 12, "invisible": 0, "visible": 0, "accepted": 0, "error": 0}}`
- Not run: `python3 scripts/context_lint.py`, `tests/test_go_page_parity_screenshots.py`.

## Owner steps left

- Review the visible PNGs and write the causes (or give the orchestrator a brief for it).
- Run lint and the pytest file. Group E/F/G were not re-run after the cap.
- Seed gaps (Leon, privacy requests, account invites, guest chat) need a table or helper decision before those rows can compare populated.
