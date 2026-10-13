# 0098: Properties — inline guest link, PIN and reporting timing

Status: review | Executor: Claude (owner-authorized) | Branch base: claude/quirky-lamport-9svmd1 | Report: [0098-report](0098-report.md)

## 1. Objective

Owner tested staging (2026-10-13). On /apartments "Guest links and reporting timing": show the full guest URL (not a relative `/l/…` path), and let the host change the reporting timing in place. Follow-ups: the section uses the same row design as the Properties table (avatar + bold name, header band, panel, list cards) and a plain heading with `?`; no police/UbyPort value (facility name, address, IDUB, mark, login) appears on the Properties list.

## 2. Context

Built on 0078 (summary section) and 0093a (`help_tip`). Timing is filing-relevant ([UBYPORT_CORE](../UBYPORT_CORE.md)): stored values must equal a Settings → Automation save.

## 3. Files

`App/app/routes/admin.py`, `App/app/templates/apartments.html`, `App/app/static/app.js` (`initInlineTiming`), `App/app/static/host.css` (`/* 0098 */`; the 0078 title band and location rules removed), `App/app/host_i18n.py` (`_PROPERTIES_0098_STRINGS`; 0078 help text updated), `App/tests/test_properties_inline_controls_browser.py` (new), `App/tests/test_host_properties_navigation.py`, `docs/context/ui-decisions.md`.

## 4. Steps

- Per row: Property | Guest link (full URL, icon Copy + Preview as guest) | PIN (icon Copy + New PIN) | When to send to UbyPort (select with the Automation labels; hours box only for the delay mode, CSS `:has()` so it works without JS).
- New PIN: existing `POST /apartments/{id}/regenerate-pin` behind `data-confirm` (message: old PIN stops working for guests); returns to `/apartments#property-summaries`.
- Timing: scoped `POST /apartments/{id}/automation-timing` calling `_automation_timing_values` (extracted from `_apartment_payload`, so both entry points share one normaliser). Writes only `automation_mode` and `submit_after_hours`. Refuses unknown modes and delay hours outside 1–48 (stores nothing). JSON with JS (save on change, debounced hours, aria-live status); redirect plus visible Save without JS.
- Properties table: drop the `addr_obec` and `uby_name` sublines.

## 5. Do not touch

Property page sections (Guest links, Door lock, Bookings, Police reporting, Stay fee), regenerate-link (stays in Settings), default purpose, `base.html` asset versions.

## 6. Commands

From `App/` with the staging/mock/REQUIRE_BROWSER env: `pytest tests/test_properties_inline_controls_browser.py tests/test_host_properties_navigation.py tests/test_host_list_cards_browser.py tests/test_host_ux_acceptance.py tests/test_guest_slugs.py <every automation_mode test> -q -rs`. `UBYHOST_CAPTURE_0098=1` writes the screenshots.

## 7. Acceptance

Full URL shown and copied; PIN copied; New PIN confirm, PIN changes, old PIN refused on the guest page; inline save row equals the Automation-page save; hours box only for the delay mode; invalid hours shows the error and stores nothing; no-JS save; foreign id refused; fits 360/390/760/1024/1280/1440 rail expanded/collapsed, EN/CS.

## 8. Stop and ask

If the inline save would need to store anything the Automation form does not, stop.

## 9. Report

[0098-report](0098-report.md), evidence in `0098-evidence/`.
