# 2033: Guest post-submit screen — one "Your guide" block (our guide, else the host's link)

Status: blocked — the guest registration pages are not in Go (`docs/plans/go-full-move-remaining.md` row "Guest registration pages", `guest.py` 19 routes; `go/internal/web/guest/` has only the save/draft/codelist pieces, no page handler for the post-submit screen). Go-first (rule 11) forbids the Python change.
Depends on: 1661, 1664 (`guide_external_url` is editable), 1668 (extended to guest paths); the "Port guest registration pages" thread; 2032 not needed (no codes on this screen) | Base commit: none | Branch: none
Executor: Haiku 5.5 | Not runnable. Tier B (guest page). The orchestrator cuts this when the Go post-submit page exists.

## 1. Objective

Owner decision 2026-11-22 (D3): the screen the guest sees right after submitting the registration gets one "Your guide" block. Our guide has published cards: primary button to our guide (it includes Leon). Else `guide_external_url` set: button "Open the host's guide" showing the domain. Both: our guide is primary, the external link a secondary text link. Neither: no block. **No entry codes and no door code on this screen** (they stay on the gated stay page and in the completion receipt only).

## 2. Context (verified on main; to re-verify when cut)

- There is no separate "finished" template. `test_finish_moment_0274.py` is the HOST wizard finish, unrelated. After `POST /l/{token}/{reservation_id}/save` (`App/app/routes/guest.py:2363` `guest_form_save`) the guest is redirected (303, `guest.py:2770-2772`) to `destination + "&saved=1"`: the next form (`/new`) while people are missing, otherwise the stay page `GET /l/{token}/{reservation_id}` (`stay_overview`, `guest.py:1481`) with `?saved=1`, which renders `App/app/templates/guest/stay.html`. So "the post-submit screen" is the stay page in its saved state; the cut brief must show the block only when `saved=1` and the party is complete, and must not duplicate the guide card that the stay page already shows at `stay.html:158-159` (`{% if guide_live %}` ... `data-guide-link`): the Go page renders one guide block, not two. The owner decides whether 1666's guide block and this block are the same block (default: yes, one block in one place; this brief then only adds the "external link only" case and the `saved=1` emphasis).
- Go has `go/internal/web/guest/form_save.go` (brief 1724, `guest_form_save`) but no stay-page or redirect-target page.
- "Published cards" (how Python decides): the guide is live when `guest_guide.progress(apartment_id)["live"]` (`App/app/guest_guide.py:278-295`: all `MUST_HAVE` kinds are `done` or `skipped`), wrapped by `_guide_is_live` (`guest.py:1473`); guests read only `state == "done"` cards allowed by their level (`for_guest`, `guest_guide.py:298-306`; drafts (`check`) and skipped never reach guests). Tests: `App/tests/test_guest_guide.py` `test_guests_see_nothing_until_the_five_are_done` (:108), `test_drafts_and_skipped_cards_never_reach_guests` (:132). The Go twin must query the same rule in SQL (`guide_item` rows, `state`, kinds) and be pinned by a Go test with the same fixtures.
- External link rules (1664): https only, no userinfo, no port; shown as the domain; `target="_blank" rel="noopener noreferrer"`. Never a code on this screen; the apartment door code and entry codes are not read by this handler.
- Strings: guest catalog, every guest language: `guide.block.title` "Your guide", `guide.block.open_ours` (button), `guide.block.open_host` "Open the host's guide" with the domain on a second line, `guide.block.host_link` (secondary text link wording "Or the host's own guide: {domain}").

## 3. Files

None. Named when the brief is cut (Go page handler and template in `go/internal/web/guest/`, catalog keys, tests below).

## 4. Steps

None. Do not run this brief. Requirements for the cut: Go test for the three branches (our guide only; external only; both) and the empty case; a test that the response body for each branch contains no `entry_code`, no `{{`, and none of the decrypted code values of a seeded apartment that has door and entry codes; guest browser and geometry tests with 0 skipped (`docs/context/test-map.md` row "Guest pages, guest templates": `test_guest_*.py` and `test_guest_browser_e2e.py`, extended to the Go page via 1668's guest paths); one 390 px screenshot per branch (plus 768 and 1280), each described per width in the PR; buttons at least 44 px, the long domain wraps without horizontal scroll.

## Design

Components: one `g-card` "Your guide" / "Váš průvodce" with a primary button and, in the "both" case, a secondary text link below it. No codes, no door code, no empty frame when there is nothing to show. The block is the same component as the guide block of 1666 (one explanation in one place).

Copy (en / cs; guest catalog, every guest language as in 1666): title "Your guide" / "Váš průvodce"; our guide button "Open the guide" / "Otevřít průvodce"; host link button "Open the host's guide" / "Otevřít průvodce hostitele" with the domain on a second line (for example `notion.so`); both: secondary text link "Also: the host's own guide ({domain})" / "Také: vlastní průvodce hostitele ({domain})". Leon is part of our guide, so no separate sentence about him. The external link is `target="_blank" rel="noopener noreferrer"`.

Code display (guest, `App/app/static/guest.css:1357` `.g-door-code`, today 700 34px monospace, `letter-spacing: .14em`, `font-variant-numeric: tabular-nums`, `overflow-wrap: anywhere`): every entry code uses the same style; codes up to 12 characters stay at 34 px on one line (no wrap inside a code); a longer code steps down to 22 px (class `g-code-long`); `overflow-wrap: anywhere` stays only as the last resort so a 32-character code never scrolls the page sideways. The text is selectable (`user-select: all`, so one tap selects the code). No copy button in this brief (a clipboard script would be a new script on a guest page; the page works without JavaScript either way). Light mode only. Links and buttons at least 44 px tall. Bump the `?v=` cache key of every CSS file changed in `App/app/templates/guest/base.html` (rules.md §Guest pages).

Behaviour by size (guest arrival lane, `docs/DESIGN.md` "Guest registration: arrival lane"; read only that section): 390 px single column with a 16 px gutter, each code in its own `g-card`; 768 px the same column centred; 1280 px the same centred column (no side-by-side codes). Order is owner D2: apartment door code first, then entry codes by `position`. Open question for the owner, not decided and not built: show codes in physical arrival order (gate, building, apartment) instead.

Design-system checklist: tick the items of `docs/design/design-system.md` §5 that apply and write "n/a guest page" for the host-shell items in the PR; the guest rules are rules.md §Guest pages and `docs/DESIGN.md#guest-registration-arrival-lane-active`.

States (each at 390, 768, 1280; file `finish-<state>-<width>.png`): `guide-ours`, `guide-external`, `guide-both`, `guide-none` (block hidden). Open every image; the PR writes per state "390: ...; 768: ...; 1280: ...".

## 5. Do not touch

Python guest routes and templates, Leon, the QR guide `/g/{token}`, the stay page's code blocks (1666).

## 6. Commands

Filled when cut. Must include: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_guest_*.py tests/test_guest_browser_e2e.py -q -rs --tb=short -x 2>&1 | tail -30` (0 skipped).

## 7. Acceptance

Filled when cut. Must contain: three branches plus empty case green; no code on the screen; screenshots at 390/768/1280 described per branch; design-system checklist ticked; no "pending".

## 8. Stop and ask

Stop at once: the brief is blocked.

## 9. Report

None.

## Risk list (for the reviewer)

When cut: no secret read by the handler; the published-cards rule equals Python's; the external link is validated again at render.

## Owner steps

When cut: the Go guest paths go into `UBYHOST_GO_PATHS` together with the guest registration port, never this block alone.
