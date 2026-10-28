# Property public pages: deterministic URL→page mapper + booking widget

Status: draft amended per owner decision (28 Oct 2026 chat): **scrape first** — Apify pre-fills the page from the host's own OTA listing, the host reviews once, the page publishes; the same scrape feeds the Leon guide; **no AI in this pipeline** (deterministic only). Fills the item the [direct-payments plan](direct-payments-build-plan.md) §1 Phase 2 item 13 deferred ("Page generator + Apify import: separate plan").

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
   slot and defines the page's data contract so P2.1 can drop in. The "Book"
   path is the host's own Stripe account (0428's Connect rail).

### Scrape-first content (owner decision, 28 Oct)

The page is **pre-filled by Apify from the host's own Booking/Airbnb listing**,
reviewed once by the host, then published — no AI anywhere in the pipeline:

```
Host pastes their OTA link(s)
   → Apify fetches (existing actors, existing SSRF allowlist)
   → structured fields stored in guide_import (one fetch, both consumers)
      ├─ → public page draft: description, photos, amenities, times (0431)
      └─ → Leon guide draft cards (existing 0347–0349 merge, unchanged)
   → host reviews the page once (one screen: fields pre-filled, editable)
   → publish toggle → the live page
```

- One scrape serves **both** the page and the guide — no second fetch, no
  duplicate cost against `UBYHOST_APIFY_MONTHLY_RUNS`.
- The page prefill is **field mapping, not generation**: listing text and photo
  URLs are placed into named page fields verbatim (trimmed/capped as in 0347);
  nothing is written, rewritten or summarised by a model. The guide-merge step
  (0348, Haiku-based) is **not used for the page** — if the owner also wants the
  guide merge without AI, that is a separate decision for the guide workstream.
- Host's own listing only: the host pastes their own link (0347 rule), so the
  content and photos are the host's; reusing them on their own page is fine.
- Host review is one screen, once: pre-filled fields the host can edit, then
  publish. Unreviewed page drafts never publish.
- Import data needs a retention line (raw OTA text retained for the page
  prefill is content, not personal data; guest-facing publication requires host
  confirmation — add the line when the schema lands).

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
| Name, photos | scrape prefill → `apartment`, page photo store | OTA listing photos (host's own) pre-fill; host can replace with `guide_photo` shots |
| Description | scrape prefill (verbatim, trimmed/capped) | Host's OTA listing text, editable at review |
| Amenities, house rules | scrape prefill → structured fields | Same field names as the guide import |
| "Everyone" guide cards | guest guide, `visibility = everyone` (0341/0342) | Same rendering as the guest view (0344); drafts and "Check this" never publish |
| Address (district only) | `apartment` city + district | Full address never on the public page (privacy first; exact address goes to booked guests) |
| Check-in/check-out times | scrape prefill → structured fields | The same values the guide cards get |
| Contact / booking CTA | host settings | "Book" button appears only when payments Phase 2 is live and the page is published; the charge lands on the host's connected account (0428) |

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
| B (0431) | Scrape prefill: page fields on the import row (description/photos/amenities verbatim, no AI), review screen (pre-filled, editable), publish toggle, public page template, 404 when off; browser + geometry tests, 390 px screenshots | A; reuses the existing Apify fetch (0347) |
| C (0432) | sitemap + noindex switch + cache/rate-limit pass | B |
| D | Booking widget slot (payments P2.1, Stripe checkout on the host's connected account) | B + payments P1.5 |

0430 and 0431 are one session each; 0432 is small. Each brief follows the repo's
TEMPLATE.md and lands per the [test-map](../context/test-map.md) (new row:
"Public property pages"). No brief in this workstream may add an AI step: the
pipeline is scrape -> map fields -> host review -> publish.

## 7. Open items for the owner

1. ~~Scrape-first, no AI~~ -- **decided (28 Oct)**: Apify pre-fills the page and
   the guide; the page pipeline is deterministic (no Haiku anywhere in it).
2. Confirm: district-level address only, full address never on the public page.
3. Confirm the default "hide from search" (noindex unless the host opts in).
4. Confirm the slug shape (`name-<4-char suffix>`).
5. Whether the **guide merge** (0348, currently Haiku-based) should also lose
   its AI step -- separate decision, guide workstream; the page does not wait for it.
