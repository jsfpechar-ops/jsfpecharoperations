# 0432: Property page OTA photos — download, re-host, review (property pages C)

Status: review
Depends on: 0431 | Base commit: after 0431 | Branch: task/0432-page-photos
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The OTA photo pipeline per the [property-pages plan](../plans/property-pages.md)
"OTA photos" section (owner decision 28 Oct): when an import row lands, the
worker downloads the listing's photos **once**, stores them through the existing
image pipeline (0343), and the review screen lets the host delete/replace them
before publish. Never hotlink: OTA CDN URLs are signed and expire.

## 2. Context

- How the platforms do it (plan section): official partner APIs + re-host.
- We act on the host's instruction on the host's own listing; the review screen
  carries the notice (cs/en): "Use only photos of your property that you have
  the right to publish." Host confirms before anything is public.
- Reuse, do not rebuild: the 0347 import worker (queue, one run per listing,
  caps) — extend the *post-fetch* step only; the image pipeline from 0343
  (per-file size cap, type allowlist); `property_page.photos_json` (0431).
- Download rules: only URLs from the actor's response for the host's own run;
  `https` only; per-file cap as in 0343; max 10 photos per property (extras
  dropped, first 10 kept); EXIF stripped (privacy rule 2 — GPS in listing
  photos); image re-encoded to the existing pipeline's format/size; stored under
  the property, not user-scoped.
- The actor run already counts against `UBYHOST_APIFY_MONTHLY_RUNS`; the
  photo download rides the same run — no new fetches, no new cap.
- Review screen: grid of imported photos (order preserved), each with delete;
  "add your own" reuses the 0343 upload; notice line above the grid.
- No template for the public hero changes here — the 0431 template already
  renders `photos_json`; this brief fills it.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/guest_guide_import.py` | edit | after a successful fetch: download + store photos |
| `App/app/property_page.py` | edit | photo list helpers; delete/replace |
| `App/app/routes/<host UI>.py` | edit | review screen photo grid + delete/upload |
| `App/app/templates/<review screen>` | edit | photo grid, notice, delete buttons |
| `App/tests/test_property_page_photos.py` | create | download, caps, EXIF strip, delete/replace |
| `docs/context/status.md` | edit | Now line |

## 4. Steps

1. Photo download in the import worker: iterate the actor's photo URLs,
   enforce caps (10, size, type), strip EXIF, store via the 0343 pipeline,
   write `photos_json`.
2. Review screen grid + delete/replace + notice.
3. Tests: cap of 10, size refusal, non-image refusal, EXIF stripped,
   delete removes the row's reference, replace uploads a new file,
   unpublished page never serves photos (404 rules from 0430/0431).

## 5. Do not touch

The 0347 URL allowlist/fetch logic, the 0348 merge, `stripe_connect.py`,
`requirements.*` (Pillow already used by 0343/qrcode).

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_property_page_photos.py
tests/test_property_page.py tests/test_guide_import*.py -q --tb=short -x
2>&1 | tail -30` — plus the browser row for the review screen.

## 7. Acceptance

- [ ] Import stores photos locally; the page never references OTA CDN URLs.
- [ ] Caps enforced; EXIF stripped; only images accepted.
- [ ] Host can delete/replace before publish; notice shown.
- [ ] Tests per §4 pass; lint OK.

## 8. Stop and ask

- If the actor's response has no usable photo URLs for a source (record which).
- If photo volume materially changes the backup size (owner note in the report).

## 9. Report

`docs/tasks/0432-report.md` (600 tokens at most): files, commands' last 5
lines, deviations, owner steps. `Status: review`. Do not push.
