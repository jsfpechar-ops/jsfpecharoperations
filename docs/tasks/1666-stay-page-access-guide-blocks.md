# 1666: Go stay page — door code and up to 3 entry codes in arrival order, guide block after

Status: blocked — the stay page `GET /l/{token}/{reservation_id}` (`App/app/routes/guest.py:1481` `stay_overview`) is part of the thread "Port guest registration pages" (`guest.py`, 19 routes, 0 in Go; `docs/plans/go-full-move-remaining.md` §2), which has not started; same reason as 1629
Depends on: 1661, 2032, 1664, 1668 (extended to guest paths once the guest port exists); the "Port guest registration pages" thread (guest shell, link + PIN + device-claim gate, guest catalog); 2036 for hosts to enter codes (1665 is replaced by it) | Base commit: none | Branch: none
Executor: Haiku 5.5 | Not runnable. Tier B (a secret on a guest page). The orchestrator cuts this when the Go stay page exists.

## 1. Objective

On the completed stay page show, the TTLock apartment door code and the extra entry codes from `apartment_entry_code` (brief 2032) in arrival order (owner 2026-11-22, D5, replaces the D2 order): `gate`, then `building_entrance`, then the TTLock apartment door code, then `garage`, `bike_room`, `other`; two codes of the same type keep the host's `position` order. Sort in one Go helper `entryCodeGuestOrder` (in the 2032 package, table test) used by every guest surface and the host preview, each as `<Type label>: <code>` (for type `other` the host's custom label), then the fee, then a guide block (prominent button to the internal guide when it is live, plus the external link with its domain when `guide_external_url` is set).

## 2. Context

Known design, verified on bdfaa4d4, kept for the later cut:

- **Window (owner 2026-11-14), per row:** each entry code shown only when `booked_level(reservation) == "booked"` (day before check-in through checkout day, `App/app/routes/guest_guide_view.py:57`) AND (`valid_until` is NULL or today ≤ `valid_until`), read from `apartment_entry_code` (the old `apartment.entry_code_*` columns are no longer read). Decrypted at render only; type labels come from the guest catalog (`entry_code.type.*`, every guest language); the page is behind permalink + PIN + device claim. The page is the source of truth if the host changes the code mid-stay.
- Never on the public QR guide `/g/{token}`, in Leon (`leon.guide_block` reads guide cards only), logs, analytics.
- Python anchors the Go twin replaces: door-code block `App/app/templates/guest/stay.html:66` `{% if door_code %}`; small guide card `:158` `{% if guide_live %}`; `guide_live` in the handler context `guest.py:1577` `"guide_live": _guide_is_live(apartment["id"]),`.
- External link: `target="_blank" rel="noopener noreferrer"`, text shows the domain. All strings through the guest catalog, every guest language.
- Guest-page rules (`docs/context/rules.md` §Guest pages; look and layout `docs/DESIGN.md#guest-registration-arrival-lane-active`): browser and geometry tests with 0 skipped, plus the screenshots below. Existing guest browser tests that open the stay page (`grep -ln '/l/' App/tests/test_guest*_browser.py`): `test_guest_browser_e2e.py`, `test_guest_form_input_browser.py`, `test_guest_polish_1098_browser.py`, `test_guest_title_1091_browser.py`; geometry: `test_host_geometry.py`, `test_guest_ocr_geometry_browser.py`.
- Evidence (owner 2026-11-14, nothing may say "pending"): the 1668 harness is extended to guest paths when the Go guest-pages port exists (signed-out context, stay link + PIN + device claim from the seed; report-only lint for guest pages as in `test_layout_lint_browser.py`, but here every finding is listed and fixed or explained). Completed-state screenshots at 390, 768 and 1280 for: (a) door code + 3 entry codes (one of type `other` with a 60-character label) + internal guide + external link + fee; (b) one entry code only; (c) nothing optional (no code, no guide). Checks per screenshot: order door code, then entry codes in `position` order, then fee, then guide; no horizontal scroll (`scrollWidth <= innerWidth`); three 32-character entry codes and a long external domain wrap without overflow; every link and button at least 44 px tall; the external link shows its domain.

## 3. Files

None. The files are named when the brief is cut.

## 4. Steps

None. Do not run this brief.

## Design

Components: the stay page's `g-card` blocks. Block "How to get in" (cs "Jak se dostat dovnitř") holds one `g-card` per code, in the D5 arrival order (gate, building entrance, apartment door code from the existing block `stay.html:66`, garage, bike room, other); then the fee card, then the guide block ("Your guide" / "Váš průvodce", same block as 2033 shows after submit: one component, one place).

Copy (guest catalog, keys `entry_code.type.*`; every guest language: add the keys to each language block of the guest catalog, found with `grep -n "guide_title" App/app/i18n.py | head -5`, or, if missing keys fall back to English there, add en and cs and say so in the report): card label is the type, "Building entrance" / "Vchod do domu", "Gate" / "Brána", "Garage" / "Garáž", "Bike room" / "Kolárna", "Other" shows the host's custom label as written. The code sits under the label. No sentence repeats the label. Block title: "How to get in" / "Jak se dostat dovnitř" (shown only when at least one code or the door code is shown). Guide block copy: see 2033 §Design.

Code display (guest, `App/app/static/guest.css:1357` `.g-door-code`, today 700 34px monospace, `letter-spacing: .14em`, `font-variant-numeric: tabular-nums`, `overflow-wrap: anywhere`): every entry code uses the same style; codes up to 12 characters stay at 34 px on one line (no wrap inside a code); a longer code steps down to 22 px (class `g-code-long`); `overflow-wrap: anywhere` stays only as the last resort so a 32-character code never scrolls the page sideways. The text is selectable (`user-select: all`, so one tap selects the code). No copy button in this brief (a clipboard script would be a new script on a guest page; the page works without JavaScript either way). Light mode only. Links and buttons at least 44 px tall. Bump the `?v=` cache key of every CSS file changed in `App/app/templates/guest/base.html` (rules.md §Guest pages).

Behaviour by size (guest arrival lane, `docs/DESIGN.md` "Guest registration: arrival lane"; read only that section): 390 px single column with a 16 px gutter, each code in its own `g-card`; 768 px the same column centred; 1280 px the same centred column (no side-by-side codes). Order is owner D2: apartment door code first, then entry codes by `position`. Open question for the owner, not decided and not built: show codes in physical arrival order (gate, building, apartment) instead.

Design-system checklist: tick the items of `docs/design/design-system.md` §5 that apply and write "n/a guest page" for the host-shell items in the PR; the guest rules are rules.md §Guest pages and `docs/DESIGN.md#guest-registration-arrival-lane-active`.

States to build and screenshot (each at 390, 768, 1280; file `stay-<state>-<width>.png`; state list): `door-only`, `door-3codes` (one `other` with a 60-character label, one 32-character code), `nolock-codes` (entry codes, no door code), `guide-ours`, `guide-external`, `guide-both`, `guide-none-no-codes` (the whole block hidden, no empty frame). Checks per image: order, `scrollWidth <= innerWidth`, no wrap inside a code of 12 characters or fewer, targets at least 44 px, long label wraps.

UX gate (rule 10): guest browser and geometry tests with 0 skipped (§7), the 1668 harness extended to guest paths for the Go page; open all 21 images; the PR writes per state "390: ...; 768: ...; 1280: ..."; never silence a finding.

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
