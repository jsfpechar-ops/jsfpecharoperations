# 2097 Report: 5-step Stay Journey (SES email, link opened, form + housebook, TTLock, police + manual paths)

Status: done
Branch: `cursor/brief-2097-stay-journey-status-b718`

## Summary

Implemented the Option B 5-step stay journey status funnel in Go (zero DB migrations, zero Python edits):
- **Icons (`go/internal/hostweb/layout/icons.go`):** added Lucide `mail-open` and `mail-x` alongside `mail`, `users`, `key-round`, and `police`.
- **Signals & progress (`go/internal/web/stays/`):** replaced unused `has_entry_code` SQL with a single batched `LEFT JOIN LATERAL` reading latest `email_outbox` state (`kind IN ('claim', 'claim_resend')`) plus `automation_mode` and `checkin_hour`; exposed `ReportedCount`, `ReportableCount`, and `ScheduledSendLabel` (`ubyport.ScheduledSendAt`) on `Progress`.
- **5-step state machine (`journey.go`):**
  1. `email` (`mail` / `mail-x`): tracks SES `queued`/`sending`, `sent`, red `failed`/`bounced`/`complained`, check-in-day nudge, and host manual overrides (`zadáno ručně`).
  2. `opened` (`mail-open`): tracks `reservation_claim.state = 'claimed'`, amber `unopened`, and host manual overrides.
  3. `form` (`users` + `n/m`): turns green `v domovní knize` (`in house book`) with a `/housebook` link on Stay Detail.
  4. `code` (`key-round`): shown for **TTLock only**.
  5. `police` (`police`): calm blue (`scheduled`) with formatted send time for auto-filing; green `netřeba (ČR)` checked before `!FilesUbyPort`; green `nahlášeno ručně` for filed-by-hand; amber `ověřit doklad` / `k odeslání` / partial `2/3`; red `chyba` / `po termínu` / `nepřipojeno` / `zrušeno po hlášení` (`cancelled_after_report`).
- **UI & CSS (`stays_list.tmpl`, `dashboard.tmpl`, `stay_detail_comfy.tmpl`, `comfy-journey.css`, `comfy-polish.css`):** single summary pill next to the 5-step strip (removed duplicate competing pill on desktop `/reservations` and `/`), collapsible no-JS `?` legend with icon and 5-color key, pure `tokens.css` variables (`--status-ready-*`, `--status-action-*`, `--status-done-*`, `--red*`).

## Verification

- `go test ./internal/web/stays/... ./internal/web/staydetail/... ./internal/web/hostweb/... ./internal/hostweb/layout/... -count=1`: **PASS** (all 4 packages `ok`; DB subtests skipped locally without Postgres, run in CI `test-postgres-full`).
- `App/.venv/bin/python -m pytest tests/test_no_em_dashes.py -q`: **4 passed**.
- `python3 scripts/context_lint.py`: **context lint: OK**.
- Chromium visual check at `390`, `768`, and `1280` px: `overflow=False`, `strip_wraps=0`, desktop row height `71.2 px <= 72 px`; inspected all three screenshots (caught and fixed missing `journey-legend` `<details>` override and swatch border contrast). Note: full `test_go_pages_layout_lint_browser.py` requires a running local Postgres 17 instance (executed by CI).

## Acceptance

- [x] 5-step Option B strip renders across `/reservations`, `/reservations/{id}`, and `/`.
- [x] Single batched query reads latest `email_outbox` claim row; `code` is TTLock-only.
- [x] Complete `form` shows Domovní kniha + `/housebook` link on Stay Detail; no 6th icon.
- [x] Calm blue `scheduled` tone, Czech-only `not_required`, partial filing, and `cancelled_after_report` implemented and unit-tested.
- [x] All manual host actions tested and glitch-free.
- [x] Zero PII in strip/tooltips; CS/EN/VI parity with zero em-dashes; zero Python edits.
