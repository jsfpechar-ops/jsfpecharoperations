# 0433: Property page — sitemap, noindex, OG tags, guest preview (property pages D)

Status: review
Depends on: 0432 | Base commit: after 0432 | Branch: task/0433-page-meta
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The small-but-visible finish per the owner ("I like the small stuff"):
`sitemap.xml` on the public host, the per-host "hide from search" noindex
switch (default on), Open Graph/Twitter meta tags so a pasted page link
unfurls with a photo in WhatsApp/messenger, and a guest-preview link on the
review screen so the host sees the page exactly as guests will.

## 2. Context

- Plan sections: §4 publication model (noindex default on, sitemap lists
  published + search-visible only), §6 row D.
- sitemap: public GET `/sitemap.xml` (public host), published pages with the
  search switch off excluded; `lastmod` = `published_at`; rate-limited like
  other public GETs; content-type correct. No third-party anything.
- OG tags on the public page: `og:title`, `og:description` (trimmed
  description, ~200 chars), `og:image` (first photo, absolute URL),
  `og:url`, `twitter:card` summary_large_image. Nothing that requires JS.
  Tags reflect the *published* content only; unpublished = 404 = no tags.
- Guest preview: signed link on the review screen (pattern of the guide QR
  tokens, 0345 — same token table approach, read-only, expires with
  unpublish/republish cycle). The preview shows exactly the public page with
  a discreet "Preview" ribbon that never renders for real guests.
- noindex switch: host-side toggle "hide from search engines" default on;
  when on, the page and its sitemap entry get `noindex` + sitemap exclusion.
- Copy cs/en, rule 9 (no sentence the button already says).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/property_page.py` | edit | sitemap route; OG tags in render; noindex handling; preview ribbon |
| `App/app/property_page.py` | edit | search_visible toggle; preview token |
| `App/app/routes/<host UI>.py` | edit | toggle + preview link on the review screen |
| `App/app/templates/property_page/*` | edit | meta block, ribbon |
| `App/tests/test_property_page_meta.py` | create | sitemap contents, noindex, OG tags, preview token |
| `docs/context/status.md` | edit | Now line |

## 4. Steps

1. sitemap route + tests (published-only, switch respected, unpublished 404s
   keep pages out).
2. OG/Twitter meta in the template; og:image absolute URL of the first photo.
3. noindex switch default-on + host UI toggle.
4. Guest preview link (token, read-only, ribbon); expires on unpublish.
5. Tests + browser/geometry row for the changed templates; 390 px screenshot
   of the page with the ribbon in the report.

## 5. Do not touch

`guest_guide_import.py`, the photo pipeline (0432), `stripe_connect.py`,
`requirements.*`.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_property_page_meta.py
tests/test_property_page.py -q --tb=short -x 2>&1 | tail -30` plus the
design row for the template changes.

## 7. Acceptance

- [ ] sitemap lists only published + search-visible pages.
- [ ] noindex default on; toggle works both sides.
- [ ] OG tags render with a real photo URL; no JS involved.
- [ ] Preview link works, is read-only, ribbon never shows to guests.
- [ ] Tests pass; lint OK.

## 8. Stop and ask

- If the sitemap needs domain handling beyond UBYHOST_DOMAIN (multi-domain).

## 9. Report

`docs/tasks/0433-report.md` (600 tokens at most): files, commands' last 5
lines, screenshot, deviations, owner steps. `Status: review`. Do not push.
