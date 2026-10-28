# Property public pages: deterministic URL→page mapper + booking widget

Status: draft for owner approval. Written by the orchestrator 28 Oct 2026; fills the
item the [direct-payments plan](direct-payments-build-plan.md) §1 Phase 2 item 13
deferred ("Page generator + Apify import: separate plan").

## 1. What this workstream is

Every property gets one public page on the public host (UBYHOST_DOMAIN, see
[APP_SUBDOMAIN](../APP_SUBDOMAIN.md)): a short listing-style page the host can link
from anywhere, which shows only data the host confirmed, and — once the payments
rail is on — carries the Phase 2 booking widget (plan §1 item 7) on top of it.

Two products, deliberately separated:

1. **The page itself** (this plan): deterministic URL→page mapper, page content,
   publication toggle, caching, sitemap. No booking code.
2. **Booking on the page**: the direct-payments plan Phase 2 (P2.1–P2.3) lands on
   the published page; nothing here duplicates it. This plan only reserves the
   slot and defines the page's data contract so P2.1 can drop in.

Apify is **not** part of the public page: imports (briefs 0347-0349, 0403) fill the
host's *private* guide editor. The public page shows confirmed cards only, so the
"scraper orchestration" for the public page is limited to what is already built.
Nothing new is fetched for the public page.

## 2. URL scheme (deterministic mapper)

- `/p/<slug>` on the public host. One page per property, forever.
- `slug` = URL-safe normalisation of the property name + a stable 4-character
  suffix from a hash of `apartment.id` (e.g. `vinohradska-11-x7q2`). Deterministic
  (recomputable from the row, no new state), collision-free across owners, and
  non-enumerative enough to not leak the property count.
- Redirects: if the host renames the property, the slug is regenerated and the old
  slug 301s to the new one (a `property_slug` history table, pruned with the
  property). The QR codes (0345) print the resolved absolute URL; they keep
  working through the redirect.
- Rules respected: rule 2 (no third-party scripts on public pages — the page uses
  the existing Turnstile/PostHog allowlist only if it hosts a form; a pure
  listing page has none), rule 6 (works without JavaScript: booking widget JS is
  progressive enhancement over a form POST path), rule 7 (browser + geometry
  tests, 390 px screenshot per new page).

## 3. Page content (host-confirmed data only)

| Section | Source | Notes |
|---|---|---|
| Name, photos | `apartment`, `guide_photo` (0343) | Host's own photos, already size-capped |
| "Everyone" guide cards | guest guide, `visibility = everyone` (0341/0342) | Same rendering as the guest view (0344); drafts and "Check this" never publish |
| Address (district only) | `apartment` city + district | Full address never on the public page (privacy first; exact address goes to booked guests) |
| Check-in/check-out times | guide import cards if confirmed | From the guide, not raw import text |
| Contact / booking CTA | host settings | "Book" button appears only when payments Phase 2 is live and the page is published |

Everything renders server-side; no client fetch. Languages: the property page
follows the guest-view language set (cs/en + configured `UBYHOST_GUEST_LANGS`),
same cookie/no-JS rules as 0344/0353.

## 4. Publication model

- Default **unpublished**. Host toggles "Public page" in the property settings;
  the toggle shows the exact public URL.
- `apartment.public_page` (0/1) + `published_at`. Unpublish = 404 (not 410, no
  tombstone), redirect history is kept so re-publishing under the same name
  restores the URL.
- Robots: `noindex` while unpublished is irrelevant (404); published pages may be
  indexed; a per-host "hide from search" switch adds `noindex` (default on — see
  rule 2; opt-in to search).
- `sitemap.xml` on the public host lists published, search-visible pages only.

## 5. Caching, abuse, rate limits

- Public GET; cache headers short (5 min) so host edits show up fast; no ETag
  machinery needed at this scale.
- Rate limit per the existing public GET pattern (`rate_limit.client_key`), same
  order as the guest guide QR view (0345).
- No secrets, no session, no cookies on the page beyond the language cookie.

## 6. Build order (briefs, numbered after 0429)

| # | Deliverable | Depends on |
|---|---|---|
| A (0430) | Slug mapper + `property_slug` migration (0028) + redirect; no template yet, tests for mapper/redirects | — |
| B (0431) | Public page template (sections §3), publication toggle in host UI, 404 when off; browser + geometry tests, 390 px screenshots | A |
| C (0432) | sitemap + noindex switch + cache/rate-limit pass | B |
| D | Booking widget slot (P2.1 of the payments plan) | B + payments P1.5 |

0430 and 0431 are one session each; 0432 is small. Each brief follows the repo's
TEMPLATE.md and lands per the [test-map](../context/test-map.md) (new row:
"Public property pages").

## 7. Open items for the owner

1. Approve this plan (or amend).
2. Confirm: district-level address only, full address never on the public page.
3. Confirm the default "hide from search" (noindex unless the host opts in).
4. Confirm the slug shape (`name-<4-char suffix>`).
