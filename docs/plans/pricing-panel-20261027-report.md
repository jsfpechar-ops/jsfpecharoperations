# Pricing simplification, 2026-10-27

Status: draft; fresh CI and visual review pending.

Restored two calm plan cards immediately after billing and apartment controls. Removed the empty badge row, duplicate total descriptions, duplicate Max TTLock block and large discount/branding panels. Six intrinsic shared rows align desktop trial buttons. Standard TTLock remains an inline optional checkbox with the selected interval fee; Max includes it once.

Apartment bands sit immediately below the cards in a compact disclosure whose summary always shows all three rates. Expanded text explains marginal bands. Branding is a short account-wide optional fee line, excluded from plan totals.

Owner's latest direction: Standard includes Havel; Max adds Leon and five times Havel usage. Both languages and subscription descriptions reflect this. OCR is explicitly coming soon, not available, with no live-feature checkmark. Existing 159 / 1908 pricing, tier math and JS/no-JS signup handoffs are preserved. No founder offer added.

Updated browser coverage checks card/control spacing, close discount placement, aligned CTAs, premium Leon copy, one TTLock inclusion, disclosure access and accurate annual add-on fees. Existing widths are 360/390/1024/1280 in both languages; CI captures 390px screenshots and an English desktop screenshot. CSS cache key and SHA-256 manifest updated.

Managed workspace startup failed: managed network requirements require sandbox enforcement. No local tests or browser screenshot inspection were possible. CI must pass and screenshots must be inspected before owner merge. No merge or deployment performed.
