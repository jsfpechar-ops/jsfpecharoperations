# 1666: Go stay page — entry code above the door code, guide block after it

Status: blocked — the stay page `GET /l/{token}/{reservation_id}` (`App/app/routes/guest.py:1481` `stay_overview`) is part of the thread "Port guest registration pages" (`guest.py`, 19 routes, 0 in Go; `docs/plans/go-full-move-remaining.md` §2), which has not started; same reason as 1629
Depends on: 1661, 1664, 1668 (extended to guest paths once the guest port exists); the "Port guest registration pages" thread (guest shell, link + PIN + device-claim gate, guest catalog); 1665 for hosts to enter a code | Base commit: none | Branch: none
Executor: Haiku 5.5 | Not runnable. Tier B (a secret on a guest page). The orchestrator cuts this when the Go stay page exists.

## 1. Objective

On the completed stay page show, in this order: building entry code (label + code), the apartment door code, the fee, then a guide block (prominent button to the internal guide when it is live, plus the external link with its domain when `guide_external_url` is set).

## 2. Context

Known design, verified on bdfaa4d4, kept for the later cut:

- **Window (owner 2026-11-14):** entry code shown only when `booked_level(reservation) == "booked"` (day before check-in through checkout day, `App/app/routes/guest_guide_view.py:57`) AND (`entry_code_until` is NULL or today ≤ `entry_code_until`). Decrypted at render only; the page is behind permalink + PIN + device claim. The page is the source of truth if the host changes the code mid-stay.
- Never on the public QR guide `/g/{token}`, in Leon (`leon.guide_block` reads guide cards only), logs, analytics.
- Python anchors the Go twin replaces: door-code block `App/app/templates/guest/stay.html:66` `{% if door_code %}`; small guide card `:158` `{% if guide_live %}`; `guide_live` in the handler context `guest.py:1577` `"guide_live": _guide_is_live(apartment["id"]),`.
- External link: `target="_blank" rel="noopener noreferrer"`, text shows the domain. All strings through the guest catalog, every guest language.
- Guest-page rules (`docs/context/rules.md` §Guest pages; look and layout `docs/DESIGN.md#guest-registration-arrival-lane-active`): browser and geometry tests with 0 skipped, plus the screenshots below. Existing guest browser tests that open the stay page (`grep -ln '/l/' App/tests/test_guest*_browser.py`): `test_guest_browser_e2e.py`, `test_guest_form_input_browser.py`, `test_guest_polish_1098_browser.py`, `test_guest_title_1091_browser.py`; geometry: `test_host_geometry.py`, `test_guest_ocr_geometry_browser.py`.
- Evidence (owner 2026-11-14, nothing may say "pending"): the 1668 harness is extended to guest paths when the Go guest-pages port exists (signed-out context, stay link + PIN + device claim from the seed; report-only lint for guest pages as in `test_layout_lint_browser.py`, but here every finding is listed and fixed or explained). Completed-state screenshots at 390, 768 and 1280 for: (a) door code + entry code + internal guide + external link + fee; (b) entry code only; (c) nothing optional (no code, no guide). Checks per screenshot: order entry code, then door code, then fee, then guide; no horizontal scroll (`scrollWidth <= innerWidth`); a 32-character entry code and a long external domain wrap without overflow; every link and button at least 44 px tall; the external link shows its domain.

## 3. Files

None. The files are named when the brief is cut.

## 4. Steps

None. Do not run this brief.

## 5. Do not touch

Everything.

## 6. Commands

Filled when the brief is cut. It must include, from `App/`: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_guest_browser_e2e.py tests/test_host_geometry.py <the stay-page test the brief adds> -q -rs --tb=short -x 2>&1 | tail -30` (0 skipped) and the extended 1668 test.

## 7. Acceptance

Filled when the brief is cut. It must contain: guest browser and geometry tests green, 0 skipped; the nine screenshots (three combinations at 390, 768, 1280) opened and described in the PR as "390: ...; 768: ...; 1280: ..." per combination; the checks of §2 (order, no horizontal scroll, wrapping, 44 px targets, domain shown) each ticked; no "pending" wording.

## 8. Stop and ask

Stop at once: the brief is blocked.

## 9. Report

None.

## Risk list (for the reviewer)

When cut: the window check, no code outside the gate, QR guide and Leon untouched.

## Owner steps

When cut: `/l/*` moves to `UBYHOST_GO_PATHS` only with all guest-thread routes (path-prefix routing, as 1629 explains).
