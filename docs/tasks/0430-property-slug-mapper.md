# 0430: Property page slugs — mapper, migration, redirects (property pages A)

Status: todo
Depends on: property-pages plan (owner approval pending) | Base commit: after 0429 | Branch: task/0430-property-slug
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The deterministic URL→page mapper for public property pages, backend only: slug
computation, the `property_slug` table (current + history for 301s), and the
public GET `/p/<slug>` route that 404s while unpublished and serves a placeholder
stub (title only) when published — the full template is 0431, this brief proves
the URL layer.

## 2. Context

- Plan: [property-pages](../plans/property-pages.md) §2 (slug scheme), §4
  (publication model). Owner approval of the plan is the gate for this brief;
  if the owner amends §2, follow the amendment.
- Slug: URL-safe lowercase normalisation of the apartment name (ASCII-fold,
  diacritics stripped, non-alphanumerics to `-`, collapsed, trimmed, max 48
  chars) + `-` + 4 hex chars from `sha256(f"apartment:{id}")[:2]`. Deterministic:
  recomputable from the row, no counter, no stored randomness.
- Migration 0028 (`App/app/migrations/0028_property_slug.sql`):
  `property_slug (apartment_id UNIQUE REFERENCES apartment(id) ON DELETE CASCADE,
  slug TEXT NOT NULL UNIQUE, published INTEGER NOT NULL DEFAULT 0,
  published_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)` —
  the mapper writes this row on first use (property created/published/rename).
  `property_slug_history (old_slug TEXT PRIMARY KEY, apartment_id REFERENCES
  apartment(id) ON DELETE CASCADE, created_at)` — the 301 source, pruned by the
  same cascade.
- Rename: when the computed slug differs from the stored one, move the old slug
  to history and write the new one. Public GET checks history first → 301 to the
  current slug; then current row → published? serve : 404; no row → 404.
- Public host rules: this route runs on the public host exactly like the guest
  guide view (0344, `routes/guest_guide_view.py`) — read its routing and
  language-cookie handling and copy the pattern. Rate limit with
  `rate_limit.client_key` per the QR view (0345).
- No personal data beyond the property reference and a public name already in
  `apartment`; no retention.py line needed (address never touches the slug or
  this table). No template/CSS work: the stub response is a minimal string, not
  a designed page (rule 7 does not apply).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/migrations/0028_property_slug.sql` | create | tables above |
| `App/app/property_page.py` | create | `slug_for(apartment_id)`, `ensure_slug(apartment_id)`, `resolve(slug)`, publish/unpublish |
| `App/app/routes/property_page.py` | create | public GET `/p/<slug>` (404/301/stub) |
| `App/app/main.py` | edit | include the public router (guest/public row, near `guest_guide_view`) |
| `App/tests/test_property_slug.py` | create | mapper + redirect + publication tests |
| `docs/context/test-map.md` | edit | "Public property pages" row |
| `docs/context/status.md` | edit | Now line |

## 4. Steps

1. Migration 0028; run the migration guard (`scripts/migration_guard.py`).
2. `property_page.py`: deterministic slug; ensure/resolve/publish; rename moves
   the old slug to history (one transaction).
3. Route: language handling copied from 0344; 301 from history; 404 when off.
4. Tests: slug determinism (same row → same slug, forever), diacritic folding
   (`Vinohradská 11` → `vinohradska-11-xxxx`), collision (two properties same
   name → different suffixes), rename → 301, unpublished → 404, cascade prune.

## 5. Do not touch

Any template or CSS (0431's job), `stripe_connect.py`, guest routes, the guide
modules. No new dependency.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_property_slug.py
tests/test_migrations.py -q --tb=short -x 2>&1 | tail -30`

## 7. Acceptance

- [ ] Slugs deterministic and stable; renames 301; unpublished 404.
- [ ] Migration guard passes; Postgres-portable SQL only (db.py helpers).
- [ ] Test-map row added; lint OK.

## 8. Stop and ask

- If the owner's plan amendment changes the slug shape (§2).
- If `apartment` lacks a stable public-name column.

## 9. Report

`docs/tasks/0430-report.md` (600 tokens at most): files, commands' last 5 lines,
deviations, owner steps. `Status: review`. Do not push.
