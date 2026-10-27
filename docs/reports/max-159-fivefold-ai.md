# Max pricing and AI allowance

Status: draft; CI and visual review pending.

Owner authorized implementation with Sol on 2026-10-27. Based on main 1a82d40.

## Changes

- Max annual first-band extra: 718 Kč instead of 760 Kč per apartment. Combined with the 1,190 Kč base, apartments 1–4 cost 1,908 Kč/year each: exactly 159 Kč/month equivalent. This is annual billing, not a 159 Kč monthly invoice.
- Preserve monthly Max totals of 228/178/138 Kč per apartment by band. Annual combined marginal rates are 1,908/1,520/1,160 Kč; later bands and Standard rates stay unchanged. Existing founder base agreements still use their confirmed base price plus the revised Max extra.
- Effective Max message allowance multiplier is 5 for Leon and Havel. Standard and trial remain 1; paused remains 0. Existing budgets, feature flags, AI availability and conversation protections remain in force.
- Czech/English public and subscription copy says 5×. The Max OCR mention is clearly coming soon and unavailable today, including in the trial. No OCR implementation, entitlement or launch date is introduced.
- Update price, activation, enforcement, public no-JS/browser expectations and add annual Max upgrade proration coverage. No assertions are relaxed.

## Verification

Managed workspace cannot start: managed network requirements require sandbox enforcement. No local pytest, context lint, browser or screenshots were run. Changes assembled through connected GitHub tools; CI must verify this draft. Required test-map rows: billing, Havel/AI, public pages, copy and host browser/geometry for subscription text. Existing pricing browser tests capture 390 px Czech/English screenshots in CI artifacts; inspect those and the subscription page before release.

No deployment, merge, feature enablement, dependencies, schema or guest-filing changes.

## Private AI allowances follow-up

- Public pricing and subscription copy explicitly says “5× AI usage for both Leon and Havel” (Czech equivalent). No absolute message allowance or unlimited claim is advertised.
- Havel customer routes, panel, page and JavaScript already omit allowance counts. Remove unused remaining-quota translation keys and the stale design instruction. Internal Havel remaining(), enforcement and admin observability stay intact.
- Leon setup trial chat no longer publishes its daily test-message count or returns numeric left in its customer JSON. The response explicitly allows only kind, text, would_ask, boolean blocked, note and cap. Templates and JavaScript use the boolean; internal accounting and rate limits stay intact. Exhaustion copy honestly states a usage limit and asks the host to try again later.
- Add rendering regression coverage for Havel with varied internal caps and a failing remaining() stub. Update Leon API/render tests to reject numeric allowance exposure while verifying the cap still stops model calls.
- Local tests, browser/geometry checks, screenshots and context lint remain unrun because the managed workspace is unavailable. CI must verify the changed Leon setup, Havel, host, copy, public and billing test-map rows; inspect 390 px Leon setup and pricing/subscription screenshots before release.

## Latest owner decision: Leon Lite and withdrawn white label

Standard includes Leon Lite permanently at the base allowance. Max keeps the same model and capabilities with 5× Leon and Havel capacity. This supersedes the intervening Max-only entitlement change. Exact quotas remain internal; OCR stays unavailable. The two pricing cards retain 99/159 Kč annual equivalents and Max TTLock inclusion appears once.

White label is unavailable for new orders/upgrades, including forged API/forms. Public pricing data and purchase controls/copy are removed. Existing saved entitlements, invoices, migration/configuration and removal controls are preserved. Reordering cannot silently strip an existing entitlement.

Added regression assertions cover shared-stay Lite/Max limits and handoff, Standard activation, paused access, new-purchase rejection, existing-contract preservation and public/browser copy. No local execution or screenshot inspection was possible; green CI plus the existing required visual review are still outstanding.
