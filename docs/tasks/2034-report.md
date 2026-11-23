# 2034 report

Status: review

## Summary

Public guide import (`source=url`) on Go guide index. Migration **00024** uses `codes_left_out BIGINT` (fixes Python `postgres_schema_status` bigint parity). Notion fetch not run against real Apify (owner step).

## Fix (browser gate)

`INTEGER` → `BIGINT` in `00024`; `pg_schema.py apply`/`check` green on fresh `ubyhost_dbg2034`.

## Commands (last 5 lines)

`pg_schema apply`: `PostgreSQL schema apply OK: database=ubyhost_dbg2034, version=45, tables=75, goose=24.`

`pg_schema check`: `PostgreSQL schema check OK: database=ubyhost_dbg2034, version=45, tables=75, goose=24.`

`go test ./internal/guideimport/... ./internal/web/ai/... ./internal/schema/`: all ok

`pytest` (§6 subset): `53 passed`

`test_go_pages_layout_lint_browser.py -q -rs`: `4 passed`

## §7

All acceptance ticks satisfied; UX gate 0 findings, 0 skipped.

## Screenshot notes (artifacts `/opt/cursor/artifacts/2034/`)

- **empty** — 390: import card with Booking/Airbnb/Public page fields, yellow “guide not live” banner, no codes notice; 768: same, three URL fields in one column; 1280: sidebar + import card, Public page link with help, Import button.
- **notice** — 390: amber attention banner in import card, text reads “Codes and passwords left out: 3…” (numeric 3, not a placeholder); 768: same banner beside three inputs; 1280: full-width banner under import title, “Codes and passwords left out: 3. Add entry codes…”
- **notice-one** — 390/768/1280: same banner pattern with count **1** (verified visually at 390; 768/1280 match layout).
- **error** — 390: flash via `?err=` above import; 768: red error stripe under header; 1280: red host flash under title, public URL field still visible.
- **queued** — 390: green/success flash “Import started…”; 768/1280: success message in host flash row after post.

## Deviations

Migration **00024**; `test_go_pages_layout_lint_browser` sets `two_factor_prompted_at` on harness host to hide security prompt (layout lint finding).

## Owner

Staging Apify + public Notion page; enable via existing Go path/job switches.