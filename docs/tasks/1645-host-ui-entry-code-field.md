# 1645: Go apartment settings — "Building entry code" section for every host

Status: blocked — `GET/POST /apartments/{id}` (apartment_detail, apartment_update) and `POST /apartments/{id}/door-codes` are not in Go (`docs/plans/go-full-move-remaining.md` §2 "Property settings pages", §3 "only the list, guide, archive and regenerate routes exist"); no port brief exists yet
Depends on: 1641, 1648; the "Port property settings pages" thread (`go/internal/web/properties/`), whose `/apartments/{id}` settings-page brief must be written first | Base commit: none | Branch: none
Executor: Haiku 5.5 | Not runnable. Tier B (a secret on a host page). The orchestrator cuts this once the Go settings page exists.

## 1. Objective

Hosts type a building or gate entry code (label, code, optional "valid until" date) on the apartment settings page. The code is stored encrypted in `apartment.entry_code_enc`, never shown in clear again (masked, with Replace and Clear), audited without the value. **Not behind the TTLock gate:** Python's door-codes POST refuses unless `ttlock.allowed_for(...)` (`App/app/routes/admin.py:2503`: `if not apartment or not ttlock.allowed_for(apartment["owner_user_id"]):`), but a building gate code has nothing to do with smart locks, so it gets its own section that every host sees.

## 2. Context

Known design, verified on bdfaa4d4, kept for the later cut:

- Python settings sections (`App/app/templates/_property_editor.html`): `sec-basics` (:173), `sec-messages` (:246, guest link, PIN, messages; every host), `sec-police` (:324), `sec-fee` (:371), `sec-calendars` (:427), `sec-lock` (:435, TTLock). Proposal: a new `<details class="prop-sec" id="sec-access">` "Building entry code" in the Go twin, right after the guest-links section (`sec-messages`), with its own `POST /apartments/{id}/entry-code` (not part of the door-codes form). Optional, so its dot is neutral like `sec-messages`.
- Field rules: label free text up to 60 characters (default "Building entrance"); code `^[A-Za-z0-9*#-]{1,32}$` (same rule as `App/app/cleaning_codes.py:123`); valid-until an ISO date, today or later, or empty.
- Encrypt with `go/internal/secure` (the Fernet the mail markers decrypt). Audit `entry_code_set` / `entry_code_cleared` with `apartment=<id>` only.
- Display after saving: label, `••••` plus the last character at most, valid-until date; buttons Replace and Clear. No log line carries the value.
- Strings in `App/app/host_i18n.py` / `host_vi_i18n.py` (go-first exception 1, the Go catalog is generated from them) unless the property port has moved its catalog by then.
- UX gate (rule 10): through the 1648 harness (`App/tests/test_go_pages_layout_lint_browser.py`), no staging server. The settings section is shot in three states: no code; code set (masked as label, bullets plus last character, valid-until date, Replace and Clear); valid-until in the past (the expired notice). 390/768/1280 each, 0 findings, 0 skipped; the PR writes "390: ...; 768: ...; 1280: ..." per state and ticks the design-system checklist.

## 3. Files

None. The files are named when the brief is cut.

## 4. Steps

None. Do not run this brief.

## 5. Do not touch

Everything.

## 6. Commands

Filled when the brief is cut. It must include, from `App/`: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_go_pages_layout_lint_browser.py -q -rs --tb=short -x 2>&1 | tail -30`.

## 7. Acceptance

Filled when the brief is cut. It must contain: the 1648 harness green with 0 findings and 0 skipped for the three states above at 390, 768 and 1280; the per-state "390: ...; 768: ...; 1280: ..." text in the PR; the design-system checklist ticked; no "pending" wording.

## 8. Stop and ask

Stop at once: the brief is blocked.

## 9. Report

None.

## Risk list (for the reviewer)

When cut: no clear-text value in HTML after save, audit, logs or flashes; the section shows without TTLock.

## Owner steps

When cut: the Go `/apartments/{id}` paths go into `UBYHOST_GO_PATHS` with the property settings port, never this field alone (Caddy routes by path; POST forms of the same page must move together).
