# 1629: Go guest guide view (GET /l/{token}/{reservation_id}/guide, /g/{token} and their photos)

Status: blocked — the page needs the guest shell, the link, PIN and claim gate, the guest catalog and the Leon routes of the thread "Port guest registration pages" (`guest.py`, `guest_leon.py`), which has not started; nothing in this brief can run before it
Depends on: the "Port guest registration pages" thread (shell, gate, guest i18n, Leon) | Base commit: none | Branch: none
Executor: Haiku 5.5 | Not runnable. Tier B (a host's guide shown to guests). The orchestrator re-splits this into briefs when the dependencies exist.

## 1. Objective

Port the four routes of `App/app/routes/guest_guide_view.py`: `stay_guide` (`GET /l/{token}/{reservation_id}/guide`), `stay_guide_photo` (`.../guide/photos/{item_id}/{photo_id}`), `qr_guide` (`GET /g/{token}`) and `qr_guide_photo` (`/g/{token}/photos/{item_id}/{photo_id}`) to Go, showing exactly the cards, host name and photos the Python page shows for the same token and nothing else from the host's data. This file records why it cannot be written yet, what is already known, and how to cut it once it can.

## 2. Context

What Python does (read once, so the later writer need not):

- Both doors render only `guest_guide.for_guest(apartment_id, level)`: cards with state `done`, visibility allowed for the level (`booked` from the day before check-in to the checkout day, else `everyone`; the QR door is always `everyone`), nothing until `guest_guide.progress(...)["live"]`. A photo is served only when its card is in that list and the file exists; else the guest 404 page. The QR door shows the host's name only (never phone or e-mail, owner decision 2026-10-24) and no privacy link with a stay token. Every response carries `Cache-Control: no-store`, `X-Robots-Tag: noindex, nofollow`, `Referrer-Policy: no-referrer` (photos: `private, max-age=3600`, `noindex`). The QR door counts page views per address (`guide_qr`, 120 per window, photos not counted) and answers 429 through the guest 404 page.
- Card text is in the host's language; the page language comes from `guest._language` (`?lang=`, cookie, then `Accept-Language`). `guide_translate.apply` swaps in cached AI translations and `fill` translates the missing cards after the response with a model call (budget, validation of numbers and links, `guide_translation` rows).

Why it is blocked (each point is a file the reviewer can open):

1. **Gate (tier A).** `stay_guide` runs `guest._open_link`, `_require_pin`, `_reservation_for_guest`, `claim.ensure_row`, `claim.guest_access_open`, `claim.is_claimed` and `_device_holds_claim`, and redirects to the stay page while the claim step is open. That logic lives in `guest.py` (3062 lines) and belongs to the thread "Port guest registration pages" (waits for filing). Copying it here would fork the PIN and claim rules.
2. **Shell.** Both doors render `guest/guide.html` through `render_guest` (`guest/base.html`, `_host.html`, `_shared`: facility, controller, host contact, language switcher with the guest catalog `app/i18n.py`). The 404 and 429 answers use `guest/unavailable.html`. No Go guest shell exists; building one here would duplicate the one the guest thread needs.
3. **Leon.** With AI on and Leon switched on for the property the page carries the chat (`guest/_leon.html`, `guest-leon.js`); its routes `GET/POST /g/{token}/leon` and `.../guide/leon` are `guest_leon.py` (the guest thread). Caddy routes by path prefix only, so `/g/{token}` cannot move to Go while `/g/{token}/leon` stays on Python, and a Go page without the chat would silently drop a feature.
4. **Translation fill.** The Go guide editor (1440 to 1447) has the guide data but not `guide_translate`. Skipping `fill` would stop translations for ever; porting it adds an outbound model call that needs its own PR text and budget tests.
5. **Path collision.** `/l/{token}/...` carries 19 further Python routes (`guest.py`) and 4 Leon routes, `/g/{token}/...` one more. Neither prefix can be switched to Go before all of them are ported.

What is not blocked and could be written now if the owner wants a head start: the pure data layer in a new file of `go/internal/web/ai/` or its own package (cards, groups, `booked_level`, steps split, video-URL rule, photo path lookup), tested against a Python golden. It would have no caller until the shell exists; the orchestrator decides.

## 3. Files

None. The files will be named when the brief is cut.

## 4. Steps

None. Proposed cut, once the guest thread has merged its shell, gate and catalog (tier B each; one Haiku session each):

1. Golden script for both doors: made-up apartment with a live guide, one card per kind, a `booked` and an `everyone` card, a photo, a QR token; cases for each language, each level date window, 404, 429, not-ready, empty guide; rows read, none written.
2. Go data layer: `for_guest`, `_cards`, `_groups`, `booked_level`, photo file lookup (read-only).
3. QR door and its photo route (uses the guest shell); register `GET /g/{token}` and `GET /g/{token}/photos/...`.
4. Stay door and its photo route (uses the guest gate); register the two `/l/...` patterns.
5. Translation: port `guide_translate.apply` (read) and `fill` (model call through `go/internal/anthropic`), or decide with the owner to leave `fill` on Python's worker.
6. The switch: `/g/*` and the guide paths of `/l/*` in `UBYHOST_GO_PATHS` only when the guest thread's routes are also on Go (point 5 above).

## 5. Do not touch

Everything. Do not run this brief.

## 6. Commands

None.

## 7. Acceptance

- [ ] Not applicable until the brief is cut.

## 8. Stop and ask

Stop at once: the brief is blocked.

## 9. Report

None.

## Risk list (for the reviewer)

None yet. When cut: the gate checks (link, PIN, claim), that no host field beyond the QR door's host name reaches the page, and that a photo is served only for a card `for_guest` returns.

## Owner steps

None.
