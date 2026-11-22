# 1665: Go apartment settings — "Entry codes" section (up to 3 codes) for every host

Status: replaced — by 2036 (a new Go-only page `/apartments/{id}/access`; no property-settings port needed). Kept for history; do not run. The old settings-page text below no longer applies.
Depends on: 1661, 2032, 1668; the "Port property settings pages" thread (`go/internal/web/properties/`), whose `/apartments/{id}` settings-page brief must be written first | Base commit: none | Branch: none
Executor: Haiku 5.5 | Not runnable. Tier B (a secret on a host page). The orchestrator cuts this once the Go settings page exists.

## 1. Objective

Hosts list up to 3 extra entry codes besides the TTLock apartment door code (owner 2026-11-22, D1, D2). Each row: type (building entrance, gate, garage, bike room, other), a custom label (required for "other", free text up to 60 characters), the code, an optional "valid until" date. Rows live in `apartment_entry_code` (brief 2032; ciphertext in `code_enc`), never shown in clear again (masked, with Replace and Clear per row), audited without the value. **Not behind the TTLock gate:** Python's door-codes POST refuses unless `ttlock.allowed_for(...)` (`App/app/routes/admin.py:2503`), but entry codes have nothing to do with smart locks, so the section is shown to every host. The Add code button disappears at 3 rows.

## 2. Context

Known design, kept for the later cut (anchors verified on main):

- Python settings sections (`App/app/templates/_property_editor.html`): `sec-basics` (:173), `sec-messages` (:246), `sec-police` (:324), `sec-fee` (:371), `sec-calendars` (:427), `sec-lock` (:435, TTLock). Proposal: a new `<details class="prop-sec" id="sec-access">` "Entry codes" in the Go twin right after `sec-messages`, with its own routes `POST /apartments/{id}/entry-codes` (save one row) and `POST /apartments/{id}/entry-codes/{position}/clear`; not part of the door-codes form. Optional section, neutral dot.
- **No JavaScript needed (rule 6):** every row always renders the type `<select>` and the custom-label `<input maxlength="60">`. With JavaScript the label is hidden unless type is `other`; without it the label is visible and the server validates: `other` with an empty label is refused with a flash, a label sent with another type is ignored (stored NULL). The Add code button is a plain submit that appends an empty row server-side (or a link to `?add=1#sec-access`); it is not rendered when 3 rows exist.
- Field rules: type from the fixed list `building_entrance, gate, garage, bike_room, other`; label up to 60 characters; code `^[A-Za-z0-9*#-]{1,32}$` (same rule as `App/app/cleaning_codes.py:123`); valid-until an ISO date, today or later, or empty. Position is the row order 1..3 (unique per apartment); Clear removes the row and closes the gap by renumbering in one transaction.
- Encrypt with `go/internal/secure` (the Fernet the mail markers decrypt). Audit `entry_code_set` / `entry_code_cleared` with `apartment=<id> position=<n> type=<code_type>` only: never the code, never the custom label (free text may hold a code).
- Display after saving: type label (or the custom label), `••••` plus the last character at most, valid-until date; Replace and Clear per row. No log line carries a value.
- Retention: 2032 deletes rows 1 day after `valid_until` or archive; this brief adds no new personal-data field beyond `apartment_entry_code`, whose line (`go/internal/retention/steps.go` `stepEntryCodes`, `App/app/retention.py` `_entry_code_step`, `docs/privacy/RETENTION.md`) is added by 2032.
- Strings in `App/app/host_i18n.py` / `host_vi_i18n.py` (go-first exception 1, the Go catalog is generated from them) unless the property port has moved its catalog by then. Type labels are catalog keys (`entry_code.type.building_entrance` ...), shared with 1666 and 1667 (guest catalog, every guest language).
- UX gate (rule 10): through the 1668 harness (`App/tests/test_go_pages_layout_lint_browser.py`), no staging server. Section shot in four states: no code; one code set (masked, Replace and Clear); three codes (Add hidden; one `other` row with a 60-character label wrapping at 390); validation error (`other` without a label). 390/768/1280 each, 0 findings, 0 skipped; the PR writes "390: ...; 768: ...; 1280: ..." per state and ticks the design-system checklist. Plus one no-JavaScript check: the page opened with JavaScript disabled still shows the label input and the server refuses `other` without a label.

## 3. Files

None. The files are named when the brief is cut.

## 4. Steps

None. Do not run this brief.

## 5. Do not touch

Everything.

## 6. Commands

Filled when the brief is cut. It must include, from `App/`: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_go_pages_layout_lint_browser.py -q -rs --tb=short -x 2>&1 | tail -30`.

## 7. Acceptance

Filled when the brief is cut. It must contain: the 1668 harness green with 0 findings and 0 skipped for the four states above at 390, 768 and 1280; the per-state "390: ...; 768: ...; 1280: ..." text in the PR; the design-system checklist ticked; no "pending" wording.

## 8. Stop and ask

Stop at once: the brief is blocked.

## 9. Report

None.

## Risk list (for the reviewer)

When cut: no clear-text value (and no custom label) in HTML after save, audit, logs or flashes; the section shows without TTLock; the label rule works without JavaScript; a fourth row is refused server-side.

## Owner steps

When cut: the Go `/apartments/{id}` paths go into `UBYHOST_GO_PATHS` with the property settings port, never this field alone (Caddy routes by path; POST forms of the same page must move together).
