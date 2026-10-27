# Original pricing layout and Max monthly price

Owner request: restore the original two-card presentation, retain the current plan features and annual prices, and set monthly Max to 229 CZK.

- Restore the original hero spacing, 40 px card padding, 20 px gaps, reassuring taglines, and a compact Max badge.
- Keep trial buttons aligned with shared grid rows. Keep apartment bands immediately below the cards.
- Standard has one TTLock checkbox inside its card. Max includes TTLock once.
- Shorten the comparison to six Standard features and five Max features. Explain Leon Lite and Havel by their roles; Max explicitly offers 5× usage for both.
- Keep OCR clearly unavailable until released. Keep founding-host and white-label offers hidden.
- Change the first four monthly Max supplements from 79 to 80 CZK. Base 149 + supplement 80 = 229. Other bands and annual prices are unchanged: one apartment remains 1,908 CZK/year (159/month equivalent). Annual pricing is still under owner review.
- No changes to authentication, trial timing, AI enforcement, legacy access, or issued invoices. Public rates and new billing quotes use the same constants.

Validation: update the existing billing strategy assertions and pricing browser checks for the revised totals and feature counts. Browser checks exercise Czech/English at 360, 390, 1024 and 1280 px, both billing intervals, 1–50 apartments, TTLock, signup URLs, CTA geometry and no-JavaScript fallback. CI captures `cenik-cs-390.png` and `cenik-en-390.png` in its browser-shots artifact. Execution is pending GitHub CI; the managed workspace could not start. No local test or visual-review result is claimed.

CI follow-up: invoice expectations now include the new monthly Max supplement. Keep the documented 44 px logo width explicit. The Havel phone geometry test now waits for first-open fragment replacement before measuring topic nodes; all existing count, visibility and size assertions remain.
