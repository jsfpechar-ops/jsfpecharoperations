# 0320 report (executor, Haiku 5.5)

Status: review. All steps 1 to 9 done; no checkpoint stop needed.

**Migration:** `App/app/migrations/0020_havel_gap.sql` (0017 to 0019 taken). `scripts/migration_guard.py origin/main`: OK. `next free: migration 0021` from context_lint.

**Files:** `App/app/migrations/0020_havel_gap.sql` (new), `App/app/havel.py` (`GAP_KINDS`, `record_gap`), `App/app/retention.py` (`HAVEL_LIMIT_DAYS=32`, `HAVEL_GAP_DAYS=90`, rate-limit step keeps `havel_*` rows 32 days, `_havel_gap_step`, STEPS and `_cutoffs` lines), `App/app/routes/havel.py` (gap write on escalate/fail, `POST /havel/not-helped`, 5 a day), `App/app/templates/_havel_thread.html` (button), `App/app/host_i18n.py`, `App/app/host_vi_i18n.py` (`havel.not_helped_ack`), `App/tests/test_havel_gap.py`, `App/tests/test_havel_gap_browser.py` (new), `docs/tasks/screenshots-0320/not-helped-390.png` (new).

**Test results (from App/, browser env: chromium-1243):**
- `tests/test_havel_gap.py tests/test_havel_support.py tests/test_havel_page.py`: 13 passed in 1.94s
- `tests/test_havel_gap_browser.py`: 1 passed in 2.75s, 0 skipped
- `tests/test_havel*.py`: 57 passed in 12.26s
- `tests/test_design_guardrails_browser.py -k havel`: selected 0 tests (deselected 10); ran the whole file instead: 10 passed in 44.23s, 0 skipped
- `tests/test_retention*.py tests/test_privacy_first.py tests/test_migrations.py tests/test_host_i18n.py`: 73 passed, 1 warning (DeprecationWarning, pre-existing)
- `tests/test_migrations.py`: 13 passed
- `tests/test_a11y_guard_browser.py`: 4 passed in 68.57s, 0 skipped
- `scripts/context_lint.py` (repo root): context lint OK (warnings only: catalog and RETENTION.md named by open briefs, 51 commits since status.md)

**Screenshot (390 px, light mode):** the last Havel reply bubble ("Open Stays, then tap Add stay.") with a secondary "This didn't help" button under it. Layout is clean, no overflow. The browser test also asserts `scrollWidth <= 390` and the support card opens after the tap.

**Deviations from the brief:**
1. Migration named 0020, as instructed.
2. Base commit: `origin/main` is 13c3de1 (brief said 92646d3); written into the brief header.
3. `request.state.lang` replaced with `host_i18n.lang_from_request(request)` in both route writes.
4. Browser selector: the send button is `[data-havel-send]`, not `button[type=submit]`. Tests use `?lang=en`. Assertions compare `html.unescape` text; the raw page is used for the history regex.
5. `host` fixture imported from `tests.test_submission_retry_cap`, as `test_havel_support.py` does.
6. i18n: `havel.not_helped` already existed (en "This didn't help", cs "Nepomohlo to", vi "Điều này không giúp được") from 0319. The brief's duplicate entries were removed and the existing vi wording kept. Only `havel.not_helped_ack` is new, in en, cs and vi.
7. `_rate_limit_retention_step` anchor line is 187 (brief 187, same); `STEPS` is at 442 (brief said 440). Retention alignment tests pass.
8. Added `record_stat("not_helped")` on each logged tap (the brief's route code has it; it is stored in `havel_stats`).

**Open questions for the owner / reviewer:**
- `redact` does not remove names (the brief's risk list). Gap questions can still contain a guest's name; they are deleted after 90 days and the list is admin-only (0331).
- The 0329 legal wording still needs to say that Havel limits are kept 32 days and gaps 90 days.
- Havel must stay off (`UBYHOST_AI_FEATURES` unset) until this merges, as the brief says.
