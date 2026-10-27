# Pricing panel implementation, 2026-10-27

Status: draft; CI and visual review pending.

## Release dependency

**Do not merge or publish PR #536 without PR #537.** Pricing copy and FAQ structured data now promise that the 30-day trial starts after successful email verification and account activation. PR #537 supplies that trial behavior and removes automatic founder offers. Both PRs remain drafts and need coordinated review before release.

## Changes

Consolidated billing controls, marginal apartment bands, plans and add-ons into one pricing decision. Intrinsic shared grid rows align trial buttons. Standard alone selects TTLock; Max includes it. Add-on prices follow the billing interval and canonical rates; white-label is account-wide and excluded from plan totals. Existing calculator and signup parameters remain intact. Czech and English copy explain AI roles. Asset versions and hashes updated.

## Verification

GitHub CI for bfac481: context, Docker, smoke, shellcheck and secrets passed. Full tests found the last pricing-card logo CSS rule omitted its documented 44px width; corrected without weakening the test. Browser shards were still running at this report update. Follow-up commit requires fresh CI.

The actual pricing.js passed 600 supplementary calculator/handoff assertions across counts 1–50, both billing periods and TTLock states. This does not replace browser verification.

Expanded browser tests cover both languages at 360/390/1024/1280px, marginal totals, button geometry, add-ons, CTA parameters and no-JS fallback. Screenshot capture uses CI browser artifact storage.

## Limitations and owner review

Managed workspace unavailable; no local pytest or browser run. No screenshots have been viewed. Before merge, require green CI, inspect cenik-cs-390.png, cenik-en-390.png and cenik-en-1280.png in browser artifacts, and coordinate #537. No merge or deployment performed.
