# Plan: building entry code + external guide link on the stay page and in the completion receipt

Status 2026-11-14, main at `bdfaa4d4`. Go only (owner 2026-11-14, [go-first](../context/go-first.md)).

Goal: a host-typed building/gate entry code and an optional external (e.g. Notion) guide URL, shown to the guest on the gated stay page and in the completion receipt, right after the apartment door code.

## Decisions (owner, 2026-11-14)

- **Go only.** New code in Go; where the page or job is not in Go, the port comes first and the brief says so in `Depends on`. Python changes only under go-first's three exceptions, named in each brief.
- Entry code lives in exactly two places: the gated stay page (`/l/{token}/{reservation_id}`, behind permalink + PIN + device claim) and the completion receipt. Never in the late-PIN door-code notice, the public QR guide `/g/{token}`, logs, audit values, analytics, exports, or Leon.
- **Windows:** stay page = `booked_level` (day before check-in through checkout day) AND `entry_code_until`. Receipt = whenever it is sent, limited only by `entry_code_until` (it usually goes weeks before check-in).
- **Stored copy (owner 2026-11-14):** UbyHost erases its saved, encrypted copy 1 day after `entry_code_until` or 1 day after the apartment is archived; with no end date it stays until the host clears it. UbyHost never touches the building's own system. Go only; 1660 is go-first exception 1 (owner approved).
- Secret handling copies the door code: encrypted at rest, ciphertext in the outbox payload, `{{entry_code}}` filled at send, missing secret fails the send. Not behind the TTLock gate: every host sees the field.
- External guide URL: https only, no userinfo, no port, domain shown.

## Briefs

| # | Title | Status | Depends on | Tier |
|---|---|---|---|---|
| [1660](../tasks/1660-schema-check-goose-only-columns.md) | Schema checks accept goose-only columns | todo (owner approved exception 1, 2026-11-14) | none | A |
| [1661](../tasks/1661-entry-code-schema.md) | Goose 00018 columns + export guard | blocked on 1660 | 1660 | A |
| [1662](../tasks/1662-entry-code-retention.md) | Retention step `entry_codes` (Go + Python twin for the golden) | todo after 1661 | 1661 | A |
| [1663](../tasks/1663-go-mail-entry-code-marker.md) | Go mail `{{entry_code}}` marker | **todo, runnable now** | none | B |
| [1668](../tasks/1668-go-pages-layout-lint-harness.md) | Browser harness: layout lint + 390/768/1280 screenshots on Go pages (local Go binary, no staging) | **todo, runnable now** | none | B |
| [1664](../tasks/1664-go-guide-external-url.md) | Go guide editor: external link field | todo after 1661 and 1668 | 1661, 1668 | B |
| [1665](../tasks/1665-host-ui-entry-code-field.md) | Go apartment settings: entry code section | blocked | 1661, 1668, property settings port (no brief yet) | B |
| [1666](../tasks/1666-stay-page-access-guide-blocks.md) | Go stay page blocks | blocked | 1661, 1664, 1668 (guest paths), guest registration port | B |
| [1667](../tasks/1667-completion-receipt-entry-code-guide.md) | Go completion receipt | blocked | 1661, 1663, 1664, guest registration port, Go `mail` job live | B |

## Proof it looks good (owner 2026-11-14)

No PR merges with "screenshots pending". 1668 starts the Go web binary locally and runs `layout_lint.js` with 390/768/1280 screenshots, so 1664 and 1665 (host pages) use it directly. 1666 (stay page) adds guest browser and geometry tests plus nine screenshots (three combinations, three widths) and checks order, overflow, wrapping and 44 px targets. 1667 (receipt) renders the golden mail HTML in Chromium at 390 and 1280 and checks the text part and fallback.

## Why 1660 exists

`db.postgres_schema_status()` builds the expected columns from SQLite only (`App/app/db.py:1288`) and counts any column-count difference as a mismatch (`:1311`); a mismatch makes the Python app refuse to start. 00018 would be the first goose-only `ADD COLUMN`, so it cannot merge before that check knows goose-only columns (rules.md §Database, "untried ... until plan step S6").

## Reach production

1663 and 1664 are dormant until the Go `mail` job and the Go guide-editor paths are switched on (owner steps in the briefs; Go host pages get their UX gate from the 1668 harness, so brief 1412 no longer needs a staging server). Guests see nothing until 1666 and 1667, which wait for the guest registration port.
