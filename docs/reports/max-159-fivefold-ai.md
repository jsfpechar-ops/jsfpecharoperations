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
