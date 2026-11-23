# 2036: Go host page "Access & guide" — entry codes (up to 3), guest preview, door-code status

Report: docs/tasks/2036-go-apartment-access-page-report.md

Status: review
Depends on: 2032, 1668 (1664 for the external-link line, see §2) | Base commit: fill from `git rev-parse --short HEAD` | Branch: task/2036-go-apartment-access-page
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two PRs if you reach 25 calls before §4 step 8: PR 1 = steps 1-5, PR 2 = the rest) | Tier B (a secret on a host page)

## 1. Objective

Hosts have no place to enter entry codes: the Python settings page is not in Go, so 1665 could never run. This brief adds a new Go-only page `GET/POST /apartments/{id}/access`, title "Access & guide" (cs "Přístup a průvodce"), with: (a) the entry-codes section, up to 3 rows (owner D1, D2; rules from 1665), (b) a "What your guest sees" preview in the guest's display order (door code first, then the codes, then the host's external guide link), (c) one read-only line about the TTLock apartment door code when the apartment has a lock. The page itself is not behind the TTLock gate.

## 2. Context (verified on main)

- **Where Go host routes live.** The guide editor pages are Go in `go/internal/web/ai/`: each `guide*.go` has an `init()` calling `guideAdd(method, path, handler)` (`guide_common.go:101`), collected by `ai.GuideRoutes(pool, os.Getenv, os.LookupEnv, time.Now)` and mounted by `go/cmd/ubyhost-web/register_web_ai_guide.go` (`registerWebAIGuide`, no change needed). Handlers start with `q, ok := s.enter(w, r)` (CSRF on POST, `guide_common.go:177`) and `a, ok := s.home(w, q)` (apartment of the signed-in workspace, 404 otherwise, `:245`); redirect with `q.back(w, page, okFlash, errFlash)`; audit with `s.audit(ctx, q, action, detail)` (`:308`); title built as in `guide_index.go:306`. This page is added there as `guide_access.go`, route `guideAdd("GET", "/apartments/{id}/access", ...)` and `guideAdd("POST", "/apartments/{id}/access", ...)`: one path, so the owner lists one entry. Forms post to the same path with a hidden `action` (`save`, `clear`).
- **How a brand-new path reaches Go.** `docs/ENVIRONMENT.md` row `UBYHOST_GO_PATHS` (line 190): Caddy sends only listed paths to Go; unset or unlisted means Python, which has no `/apartments/{id}/access` and answers 404. The "501 then Python" fallback applies only to paths Go answers with 501 for a page Python has; a path Python never had has no fallback. `/apartments/*/access` matches exactly `/apartments/<id>/access` (GET and POST); `*` inside a path stays in one segment (same row).
- **Where the entry link goes (and never earlier).** Python never renders a link to this page. The Go guide index (`go/internal/web/ai/guide/templates/guide_index.tmpl`, served by Go only when `/apartments/*/guide*` is listed) gets a small link row. It is rendered only when the env `UBYHOST_GO_ACCESS_PAGE=1` is set in the Go container (one row in `docs/ENVIRONMENT.md`), which the owner sets after listing the path, so a link can never point at a Python 404. Later the ported settings page gets the same link (named in that port brief, not here).
- **Decision (G1): 1664 stays as it is** (runnable now: validator, route `POST /apartments/{id}/guide/external`, field on the guide index) and this page does NOT edit the link. It shows the saved link read-only in the preview with a "Change" link to `/apartments/{id}/guide#external`. Why: one explanation and one editor in one place (rule 9), 1664 needs no new path and ships first, 2036 needs 2032. 1665 is `replaced` by this brief.
- **TTLock status:** `apartment.lock_provider` and `lock_id` columns exist (`App/migrations_pg/00001_baseline.sql:288-289`); "has a lock" = `COALESCE(lock_id,'') <> ''`. The door code itself (`door_code.pin_enc`, per reservation) is never read by this page. Python's gate `ttlock.allowed_for` (`App/app/routes/admin.py:2503`) does not apply here.
- **Codes:** table `apartment_entry_code` (2032): `position` 1-3 unique per apartment, `code_type` in `building_entrance, gate, garage, bike_room, other`, `custom_label` (required for `other`, at most 60 characters), `code_enc` (Fernet via `go/internal/secure`), `valid_until` ISO date or NULL. Code rule `^[A-Za-z0-9*#-]{1,32}$` (`App/app/cleaning_codes.py:123`). Guest order (owner D2): door code first, then rows by `position`, each `<Type label>: <code>`; whether that is the best physical order is an open question (§8).
- **Secrecy:** never in clear after save (masked `••••` plus the last character), never in logs, flashes, audit values (audit `entry_code_set` / `entry_code_cleared` detail `apartment=<id> position=<n> type=<code_type>`; never the code or the custom label, which is free text), analytics, exports, Leon (2037). No tracking cookies, no third-party script (rule 2). Privacy line: the codes are personal-data-adjacent secrets; retention is 2032's `stepEntryCodes` (rows deleted 1 day after `valid_until` or archive), `docs/privacy/RETENTION.md` line added there. This brief adds no new data field.
- **Help & guide (PR template `.github/PULL_REQUEST_TEMPLATE.md:7`):** the Help & guide pages are Python (`App/app/guide_i18n.py`, `App/app/host_vi_i18n.py`, `App/app/templates/guide.html`, test `App/tests/test_guide_coverage.py`); no Go help exists (`ls go/internal/web` shows none). The edit is go-first exception 1 (port plumbing: the help stays in Python until it is ported; the brief names it). Find the neighbour: `grep -n "guide.door_codes" App/app/guide_i18n.py App/app/templates/guide.html | head -6`.
- Strings: Go host catalogs come from Python (`guide/i18n_keys.txt` + `App/scripts/go_host_i18n.py`, `go/internal/web/ai/guide_common.go:37`); new keys go in `App/app/host_i18n.py` (en, cs) and `App/app/host_vi_i18n.py`, go-first exception 1, as 1664 did.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/ai/guide_access.go` | new | routes, validation, encryption, audit, data |
| `go/internal/web/ai/guide/templates/access.tmpl` | new | page (copy the section-card helpers used by `guide_index.tmpl`: `guide_section_open` / `guide_section_close`) |
| `go/internal/web/ai/guide/templates/guide_index.tmpl` | edit | link row behind `.AccessLink` |
| `go/internal/web/ai/guide_index.go` | edit | `AccessLink bool` from env `UBYHOST_GO_ACCESS_PAGE` |
| `go/internal/web/ai/guide/i18n_keys.txt`, `i18n.json` | edit, regenerated | keys of §Design |
| `App/app/host_i18n.py`, `App/app/host_vi_i18n.py` | edit (exception 1) | keys of §Design (en, cs, vi) |
| `App/app/guide_i18n.py`, `App/app/templates/guide.html` | edit (exception 1) | one Help & guide section "Entry codes" (en, cs; vi in `host_vi_i18n.py`) |
| `go/internal/web/ai/guide_access_test.go` | new | step 6 |
| `App/tests/test_go_pages_layout_lint_browser.py` | edit | §Design states (1668 harness) |
| `docs/ENVIRONMENT.md` | edit | one row `UBYHOST_GO_ACCESS_PAGE` |
| `docs/tasks/1665-host-ui-entry-code-field.md` | already marked replaced | no change |

No other file may change.

## 4. Steps

1. `guide_access.go`: types `accessCode{Position int; Type, Label, Masked, Until string; Expired bool}`; data builder reading `apartment_entry_code` ordered by `position`, decrypting only to mask (last character), plus `has_lock`, the saved `guide_external_url` host (read-only, may be empty if 1664 is not on main: select the column, it exists since 00022).
2. GET: render `access.tmpl`; query `?edit=<1-3>` shows that row as a form (Replace), `?add=1` shows an empty new-row form when fewer than 3 rows exist (Add code is a plain link, no JavaScript); exactly one form is open at a time, so there is one Save (design-system rule 5).
3. POST `action=save`: fields `position` (1-3, or empty for a new row = lowest free position), `code_type`, `custom_label`, `code`, `valid_until`. Server validation (the label input is always rendered; JavaScript only hides it for non-`other` types): type in the list; `other` needs a non-blank label of at most 60 characters; a label with another type is stored NULL; code by the regexp; `valid_until` empty or ISO date today or later; a new row with 3 existing rows is refused. Encrypt with `go/internal/secure`; `INSERT ... ON CONFLICT (apartment_id, position) DO UPDATE`; audit `entry_code_set`; flash saved (new) or replaced (existing position). Errors: `q.back(w, page+"?edit=<n>#entry-codes", hostweb.Flash{}, q.flash(key, nil))` and never echo the code back into the URL or form.
4. POST `action=clear` with `position`: delete the row, renumber the rest to 1..n in one transaction, audit `entry_code_cleared`, flash cleared.
5. Preview block: every code as `<Type label>: ••••<last char>` (the door-code line only when `has_lock`) in the D5 guest arrival order from `entryCodeGuestOrder` (gate, building entrance, apartment door, garage, bike room, other), then the external-guide line (domain only) with a Change link. Server-rendered, no JavaScript.
6. Tests (`guide_access_test.go`; world helpers `newGuideCardWorld`, `guideSeedApartment`, `guideTestDo` from `guide_index_test.go:49-54`; DB tests need `UBYHOST_TEST_DATABASE_URL`): save each of the five types; `other` without label refused (no write); 61-character label refused; code with a space refused; past `valid_until` refused; a fourth row refused; replace keeps the position; clear renumbers; the stored `code_enc` never equals the plaintext and the response bodies, flashes, redirect URLs and `audit` rows never contain a seeded code or label (assert for all three); foreign apartment 404; unsigned POST without CSRF refused; the page for a lock-less apartment has no door-code line, with a lock it has one; the preview order is door, then positions 1..3.
7. Link row on the guide index behind `UBYHOST_GO_ACCESS_PAGE` (test both settings), env row in ENVIRONMENT.md.
8. Strings, Help & guide section, regenerate the catalog (`cd App && .venv/bin/python scripts/go_host_i18n.py 2>&1 | tail -5`; only `guide/i18n.json` may change), browser states of §Design.
9. Run §6; commit per step.

## Design

Components (design-system §2 and §5b): page `ui-page-narrow` (720 px) extending the Go host shell; each block ONE `ui-section-card` (no card in a card); title with the help "?" right after it (rule 7); fields in `ui-kv` rows; buttons: `secondary` for Save and Replace, `quiet` for Clear and Cancel, Add code `secondary`; no page header action row (the page has no primary action); empty state = title, next step, one button; banners: one at a time, plain surface with a status dot, never coral fill; one Save per open form; no floating bar; light mode only; 44 px targets on phone (40 desktop); labels 6 px above inputs, 12 px between neighbours; never truncate a label.

Code display: monospace (`ui-monospace`), letter-spaced, `overflow-wrap: anywhere` is NOT used on host rows (host sees only the masked value: `••••` plus last character, no wrap inside it: `white-space: nowrap`); a copy button is not offered on the host page (the code is never shown in clear).

Screen order: card 1 "Entry codes" (rows or empty state, Add code), card 2 "What your guest sees" (preview), card 3 "Apartment door code" only when the apartment has a lock.

Copy (en / cs; no em dashes; no sentence a button already says):
- Page title: "Access & guide" / "Přístup a průvodce"
- Card 1 title: "Entry codes" / "Vstupní kódy"; help "?": "Codes for the building, gate or garage. Guests see them on their stay page and in the confirmation email, never in the guide or in Leon." / "Kódy k domu, bráně nebo garáži. Hosté je uvidí na stránce pobytu a v potvrzovacím e-mailu, nikdy v průvodci ani v Leonovi."
- Types: "Building entrance" / "Vchod do domu"; "Gate" / "Brána"; "Garage" / "Garáž"; "Bike room" / "Kolárna"; "Other" / "Jiné"
- Fields: "Type" / "Typ"; "Name" / "Název" (shown for every type, required for Other; help "?": "Only for Other, up to 60 characters." / "Jen u typu Jiné, nejvýše 60 znaků."); "Code" / "Kód"; "Valid until (optional)" / "Platí do (nepovinné)"
- Buttons: "Add code" / "Přidat kód"; "Save" / "Uložit"; "Cancel" / "Zrušit"; "Replace" / "Nahradit"; "Clear" / "Smazat"
- Row facts: "Valid until {date}" / "Platí do {date}" (dd.mm.yyyy); no date: nothing
- Empty state: title "No entry codes" / "Žádné vstupní kódy", button "Add code"
- Expired notice (row, amber): "Expired on {date}. Guests no longer see it." / "Vypršel {date}. Hosté ho už nevidí."
- Errors under the field: "Choose a type." / "Vyberte typ."; "Add a name for Other." / "U typu Jiné doplňte název."; "Use 1 to 32 letters, digits or * # -." / "Použijte 1 až 32 písmen, číslic nebo * # -."; "Use today or a later date." / "Zadejte dnešní nebo pozdější datum."; "You can save up to 3 codes." / "Uložit lze nejvýše 3 kódy."
- Flashes: saved "Code saved." / "Kód je uložený."; replaced (G4) "Guests with upcoming stays see the new code on their stay page. Codes already emailed are not updated." / "Hosté s nadcházejícím pobytem uvidí nový kód na stránce pobytu. Kódy, které už byly v e-mailu, se neaktualizují."; cleared "Code removed." / "Kód je odebraný." No automatic re-send of emails exists or is built here; the owner may decide later.
- Card 2: title "What your guest sees" / "Co uvidí host"; lines: "Apartment door: from the lock at check-in" / "Byt: kód ze zámku při příjezdu" (only with a lock); each code "Garage: ••••1" / "Garáž: ••••1"; external "Host's guide: notion.so" with link "Change" / "Změnit" to `/apartments/{id}/guide#external`; empty: "Guests see nothing here yet." / "Hosté tu zatím nic neuvidí."
- Card 3: title "Apartment door code" / "Kód od bytu"; line "Sent by the smart lock, not set here." / "Posílá ho chytrý zámek, nenastavuje se tady."
- Guide index link row: "Entry codes and guest view" / "Vstupní kódy a pohled hosta"

Behaviour by size (design-system §3): phone: single column, rows as stacked cards (type, masked code, valid-until, then Replace and Clear at 44 px, full width side by side); 768: 24 px gutter, same column; 1280: 720 px column, Replace and Clear inline right. The Add code link disappears when 3 rows exist.

States to build and screenshot (each at 390, 768, 1280, file `access-<state>-<width>.png`, states: `empty`, `one`, `three` (Add hidden), `other` (type Other with a 60-character custom label wrapping), `expired`, `error` (Other without name), `replaced` (the replaced flash), `preview-lock` (door line shown), `preview-nolock`). Plus a no-JavaScript run of `error` (JavaScript disabled in the Playwright context): the name input is visible and the server refuses.

UX gate (rule 10): run `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_go_pages_layout_lint_browser.py -q -rs --tb=short -x 2>&1 | tail -30` (0 findings, 0 skipped); open all 27 images once (390 each, 768 and 1280 for `three`, `other`, `error`, `preview-lock`); the PR writes per state "390: ...; 768: ...; 1280: ..." and ticks the design-system §5 and §5b checklists (`docs/design/design-system.md`); never ask the owner, never silence a finding.

## 5. Do not touch

Python routes and templates other than the Help & guide files, TTLock code, `go/internal/hostweb/`, `register_web_ai_guide.go`, `UBYHOST_GO_PATHS`, 1664's route and validator, Leon, the QR guide, guest pages (1666, 2033).

## 6. Commands

From `go/`: `gofmt -l internal/web/ai/ 2>&1 | tail -5`; `go vet ./internal/web/ai/ 2>&1 | tail -10`
From `go/`, with `UBYHOST_TEST_DATABASE_URL` set: `go test ./internal/web/ai/... ./cmd/ubyhost-web/ -run 'Guide|Access|Route' 2>&1 | tail -30`
From `App/`: `.venv/bin/python scripts/go_host_i18n.py --check 2>&1 | tail -5`
From `App/`: `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_guide_coverage.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py tests/test_privacy_first.py -q --tb=short -x 2>&1 | tail -30`
From `App/`: the browser command of §Design
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -10`

## 7. Acceptance

- [ ] All §4 step 6 tests green; no code, label or ciphertext in any response, flash, URL, log or audit row.
- [ ] Label input always rendered; server validation proven with JavaScript off.
- [ ] Help & guide section added in en, cs, vi; `test_guide_coverage.py` green.
- [ ] 1668 harness: 0 findings, 0 skipped, nine states at the widths above, each described in the PR; checklists ticked; nothing says "pending".
- [ ] The guide index shows the link only with `UBYHOST_GO_ACCESS_PAGE=1`.

## 8. Stop and ask

Stop if: 2032 or 1668 is not on main; the guide editor's section-card helpers do not fit (report, do not invent a layout); `guide.door_codes` neighbours for the Help section are not found; a test fails twice; 25 tool calls or ~50k tokens; a file outside §3 needs a change.

Decided (owner 2026-11-22, D5): guests see codes in arrival order (gate, building entrance, apartment door, garage, bike room, other). The host's row order only breaks ties within one type. No automatic re-send when a code is replaced (owner 2026-11-22).

## 9. Report

`docs/tasks/2036-go-apartment-access-page-report.md` (≤600 tokens), `Status: review`, one PR (or two, see header).

## Risk list (for the reviewer)

`guide_access.go` (a secret handled on a host page: masking, audit values, URL redirects), the renumbering transaction, the Help & guide Python edit.

## Owner steps

1. After the PR deploys, add `/apartments/*/access` to `UBYHOST_GO_PATHS` (keep the existing entries; double quotes, never empty).
2. Then set `UBYHOST_GO_ACCESS_PAGE=1` for the Go service so the guide index shows the link, and redeploy. Do this second: a link before the path is listed would lead to a 404.
3. Until then nothing changes for hosts.
