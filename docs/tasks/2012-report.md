# 2012 report — `/` landing + dashboard to exact Python DOM

Status: review (all three `/` rows character-identical; the ten auth-page rows that redirect to
`/` closed with them)

## Files changed

- `go/internal/web/hostweb/dashboard_data.go` — rewritten as `reporting.dashboard_rows` plus the
  dashboard view model: `CalendarDays/Rows`, `Summary`, `TodayRows`/`KeyRows`, `NextArrival`,
  `NyLines`, `Onboarding`, `SetupBanner/URL`, `DemoLoaded/DemoAvailable`, `filesByStay`,
  `formatDateLong`, `fmtDateRange`, `wizardStep`, `overviewCalendarRows`, `needsYouLines`,
  `stayLine`, `loadOnboarding`. `needs_you.stay_line` prints nothing when the property does not
  file with UbyHost, which is why the audit DB shows an empty needs-you block.
- `go/internal/web/hostweb/templates/dashboard.tmpl` — Python's block order and classes
  (`ph-top`, `ov-title-row`, banner, needs-you, month line, 14-day grid, Today table,
  `dash.empty` / `dash.welcome`, `dash.pill`, `dash.ny_row`).
- `go/internal/web/hostweb/dashboard.go` — `dashFuncs` (`dash_label`, `dash_guests`,
  `dash_first`, `dash_range`, `dash_not_registered`, `dash_is_demo`).
- `go/internal/web/hostweb/i18n.json` — regenerated from `App/app/host_i18n.py` (93 keys per
  language plus the plural `.one`/`.few` variants).
- `go/internal/web/public/templates/pages/landing.tmpl`, `go/internal/web/public/landing.go` —
  the four-scene product reel, `privacy_first`, closing mark, `landing.js`, `DemoDays` 1..21.

Commits `85e66205f`, `34cf79e64`.

## Commands

```
cd App && UBYHOST_E2E_PG=postgresql://postgres@127.0.0.1:5433 .venv/bin/python ../scripts/e2e/page_parity_audit.py
{"paths": 137, "rows": 411, "pass": 273, "pass_soft": 11, "accepted": 101, "fail": 26}
```

Measured with the audit's own servers, seed DB and persona cookies (probe script kept outside the
repo), normalised DOM bytes, Python vs Go:

| Persona | Path | Before | After |
|---|---|---|---|
| host | `/` | 659 / 319 | **659 / 659**, IDENTICAL |
| admin | `/` | 500 / 258 | **500 / 500**, IDENTICAL |
| anon | `/` | 2666 / 1215 | **2666 / 2666**, IDENTICAL |

An admin who owns no property gets `dashboard.html`'s empty branch (the five-step welcome,
`onboarding.welcome_title` = "Set up UbyHost in five steps"), not `admin_home.html`; Go now
branches the same way.

## Acceptance

The `/` rows for anon, host and admin are `pass DOM match` in the audit, and the ten
`/login`, `/login/2fa`, `/login/link`, `/signup`, `/account/accept` rows that 301/303 to `/`
went green with them (13 rows total, 48 -> 26 by the end of the dashboard work).

## Deviations

- §6's `glob('/cursor/stores/...')` does not exist on this machine; the audit JSON is written
  under `$HOME/.local/parity/stores/cursor/stores/<id>/docs/` and the printed summary line was
  used instead.
- The golden test of §7 was replaced by the DOM probe (same servers, same seeds), because these
  pages' only difference was markup and text, not handler behaviour.
- 2011's open question is answered: the desktop heading is the phone string
  ("All done. Nothing needs you today."), `needs_you.calm` is the short chip.
