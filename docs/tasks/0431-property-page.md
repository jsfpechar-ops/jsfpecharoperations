# 0431: Property page — scrape prefill, review screen, public template (property pages B)

Status: todo
Depends on: 0430 | Base commit: after 0430 | Branch: task/0431-property-page
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens — if the session
runs out, the prefill half (§4 steps 1–3) ships alone in this branch

## 1. Objective

The listing page itself, per the amended [property-pages plan](../plans/property-pages.md)
(owner decision 28 Oct): the existing Apify import (0347) also stores **page fields**
verbatim (description, photo URLs, amenities, times — no AI transforms anything),
a one-screen host review (pre-filled, editable, publish toggle), and the public
`/p/<slug>` template (photos, description, amenities, "everyone" guide cards,
district, times, and — when payments Phase 2 is live — the Book CTA slot).
The same import already feeds the Leon guide cards (0347–0349); one fetch, two
consumers. **No Haiku/AI step anywhere in this pipeline.**

## 2. Context

- Owner decision (28 Oct 2026, decisions line): scrape first; the page prefill is
  field mapping, not generation. The 0348 Haiku merge is used only by the guide
  workstream, not by this brief.
- Reuse, do not rebuild: `guest_guide_import` fetch/queue/allowlist/caps (0347,
  `App/app/guest_guide_import.py` — read it first), the slug layer (0430), the
  guest guide view rendering patterns (0344), photo size caps (0343).
- New table (migration 0029, `App/app/migrations/0029_property_page.sql`):
  `property_page (apartment_id UNIQUE REFERENCES apartment(id) ON DELETE CASCADE,
  description TEXT, photos_json TEXT, amenities_json TEXT, checkin_text TEXT,
  checkout_text TEXT, published INTEGER NOT NULL DEFAULT 0, published_at TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL)`. Rows are created empty
  at first import or first edit; the publish toggle is here, the slug stays in
  `property_slug` (0430).
- Prefill mapping (deterministic, in `App/app/property_page.py`):
  Booking `name`/`description`/`checkIn`/`checkOut`/photo array; Airbnb
  `title`/`description`/`subDescription`/`amenities[].values[].title` (available
  only)/`houseRules` → named columns of `property_page`; text verbatim after the
  0347 trim/cap (`MAX_TEXT`), photos as a capped URL list (host's own listing
  photos; serve them through the existing image proxy pattern, never hotlink).
  A re-import overwrites only empty fields, never host edits.
- Review screen: one page in the host UI, fields pre-filled after an import,
  all editable, "Publish public page" toggle + the resolved URL shown. CSRF via
  `security.protect_host_post`; copy per rule 9 (cs/en).
- Public template: server-side only, no third-party scripts (rule 2), no-JS
  (rule 6), languages per 0344. Rule 7: browser + geometry tests 0 skipped, one
  390 px screenshot per page state in the report.
- Retention: the page fields are the host's own content, not personal data; add
  the one-line note in `App/app/retention.py` next to the existing
  `property_page`/import comment when the migration lands.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/migrations/0029_property_page.sql` | create | table above |
| `App/app/property_page.py` | edit | prefill mapping + review save + publish |
| `App/app/routes/property_page.py` | edit | public template render (replaces 0430 stub) |
| `App/app/routes/<host UI>.py` | edit | review screen + publish toggle |
| `App/app/templates/property_page/*` | create | public page; host review screen |
| `App/tests/test_property_page.py` | create | prefill mapping, review save, publish, template |
| `docs/context/status.md`, `test-map.md` | edit | Now line; row already exists |

## 4. Steps

1. Migration 0029; migration guard.
2. Prefill: after an import row lands (0347 worker), map fields into
   `property_page` (empty-fields-only overwrite rule).
3. Review screen + publish toggle + flash copy.
4. Public template per plan §3 table; 404 when unpublished; photo rendering via
   the existing proxy; "Book" CTA slot present but hidden until Phase 2.
5. Tests: mapping per source (Booking/Airbnb field names), no-overwrite rule,
   publish/unpublish, template render + no-JS, browser + geometry, screenshots.

## 5. Do not touch

`guest_guide_import.py` fetch logic, the 0348 merge, `stripe_connect.py`,
`requirements.*` (no new dependency — `requests` already used by 0347).

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_property_page.py
tests/test_property_slug.py tests/test_guide_import*.py -q --tb=short -x
2>&1 | tail -30` — plus the design row when templates change.

## 7. Acceptance

- [ ] An import prefills the page fields verbatim; nothing AI-generated.
- [ ] Host edits are never overwritten by a later import.
- [ ] Unpublished 404; published renders all §3 sections; no-JS works.
- [ ] Browser + geometry 0 skipped; 390 px screenshots in the report.
- [ ] Migration guard passes; retention note added; lint OK.

## 8. Stop and ask

- If the OTA field names on a real run differ from 0347's recorded shapes.
- If photo proxying through the app is rejected by the design lint.

## 9. Report

`docs/tasks/0431-report.md` (600 tokens at most): files, commands' last 5
lines, screenshots, deviations, owner steps. `Status: review`. Do not push.
