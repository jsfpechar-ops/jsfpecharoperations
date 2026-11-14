# 1646: Go stay page — entry code above the door code, guide block after it

Status: blocked — the stay page `GET /l/{token}/{reservation_id}` (`App/app/routes/guest.py:1481` `stay_overview`) is part of the thread "Port guest registration pages" (`guest.py`, 19 routes, 0 in Go; `docs/plans/go-full-move-remaining.md` §2), which has not started; same reason as 1629
Depends on: 1641, 1644; the "Port guest registration pages" thread (guest shell, link + PIN + device-claim gate, guest catalog); 1645 for hosts to enter a code | Base commit: none | Branch: none
Executor: Haiku 5.5 | Not runnable. Tier B (a secret on a guest page). The orchestrator cuts this when the Go stay page exists.

## 1. Objective

On the completed stay page show, in this order: building entry code (label + code), the apartment door code, the fee, then a guide block (prominent button to the internal guide when it is live, plus the external link with its domain when `guide_external_url` is set).

## 2. Context

Known design, verified on bdfaa4d4, kept for the later cut:

- **Window (owner 2026-11-14):** entry code shown only when `booked_level(reservation) == "booked"` (day before check-in through checkout day, `App/app/routes/guest_guide_view.py:57`) AND (`entry_code_until` is NULL or today ≤ `entry_code_until`). Decrypted at render only; the page is behind permalink + PIN + device claim. The page is the source of truth if the host changes the code mid-stay.
- Never on the public QR guide `/g/{token}`, in Leon (`leon.guide_block` reads guide cards only), logs, analytics.
- Python anchors the Go twin replaces: door-code block `App/app/templates/guest/stay.html:66` `{% if door_code %}`; small guide card `:158` `{% if guide_live %}`; `guide_live` in the handler context `guest.py:1577` `"guide_live": _guide_is_live(apartment["id"]),`.
- External link: `target="_blank" rel="noopener noreferrer"`, text shows the domain. All strings through the guest catalog, every guest language.
- Guest-page rules (`docs/context/rules.md` §Guest pages): browser + geometry tests 0 skipped, one 390 px screenshot.

## 3. Files

None. The files are named when the brief is cut.

## 4. Steps

None. Do not run this brief.

## 5. Do not touch

Everything.

## 6. Commands

None.

## 7. Acceptance

- [ ] Not applicable until the brief is cut.

## 8. Stop and ask

Stop at once: the brief is blocked.

## 9. Report

None.

## Risk list (for the reviewer)

When cut: the window check, no code outside the gate, QR guide and Leon untouched.

## Owner steps

When cut: `/l/*` moves to `UBYHOST_GO_PATHS` only with all guest-thread routes (path-prefix routing, as 1629 explains).
