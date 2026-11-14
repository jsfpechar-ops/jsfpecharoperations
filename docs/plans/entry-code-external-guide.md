# Plan: building entry code + external guide link on the stay page and in the completion receipt

Status 2026-11-14, main at `bdfaa4d4`. Go only (owner 2026-11-14, [go-first](../context/go-first.md)).

Goal: a host-typed building/gate entry code and an optional external (e.g. Notion) guide URL, shown to the guest on the gated stay page and in the completion receipt, right after the apartment door code.

## Decisions (owner, 2026-11-14)

- **Go only.** New code in Go; where the page or job is not in Go, the port comes first and the brief says so in `Depends on`. Python changes only under go-first's three exceptions, named in each brief.
- Entry code lives in exactly two places: the gated stay page (`/l/{token}/{reservation_id}`, behind permalink + PIN + device claim) and the completion receipt. Never in the late-PIN door-code notice, the public QR guide `/g/{token}`, logs, audit values, analytics, exports, or Leon.
- **Windows:** stay page = `booked_level` (day before check-in through checkout day) AND `entry_code_until`. Receipt = whenever it is sent, limited only by `entry_code_until` (it usually goes weeks before check-in).
- Secret handling copies the door code: encrypted at rest, ciphertext in the outbox payload, `{{entry_code}}` filled at send, missing secret fails the send. Not behind the TTLock gate: every host sees the field.
- External guide URL: https only, no userinfo, no port, domain shown.

## Briefs

| # | Title | Status | Depends on | Tier |
|---|---|---|---|---|
| [1640](../tasks/1640-schema-check-goose-only-columns.md) | Schema checks accept goose-only columns | todo (owner approved exception 1, 2026-11-14) | none | A |
| [1641](../tasks/1641-entry-code-schema.md) | Goose 00018 columns + export guard | blocked on 1640 | 1640 | A |
| [1642](../tasks/1642-entry-code-retention.md) | Retention step `entry_codes` (Go + Python twin for the golden) | todo after 1641 | 1641 | A |
| [1643](../tasks/1643-go-mail-entry-code-marker.md) | Go mail `{{entry_code}}` marker | **todo, runnable now** | none | B |
| [1644](../tasks/1644-go-guide-external-url.md) | Go guide editor: external link field | todo after 1641 | 1641 | B |
| [1645](../tasks/1645-host-ui-entry-code-field.md) | Go apartment settings: entry code section | blocked | 1641, property settings port (no brief yet) | B |
| [1646](../tasks/1646-stay-page-access-guide-blocks.md) | Go stay page blocks | blocked | 1641, 1644, guest registration port | B |
| [1647](../tasks/1647-completion-receipt-entry-code-guide.md) | Go completion receipt | blocked | 1641, 1643, 1644, guest registration port, Go `mail` job live | B |

## Why 1640 exists

`db.postgres_schema_status()` builds the expected columns from SQLite only (`App/app/db.py:1288`) and counts any column-count difference as a mismatch (`:1311`); a mismatch makes the Python app refuse to start. 00018 would be the first goose-only `ADD COLUMN`, so it cannot merge before that check knows goose-only columns (rules.md §Database, "untried ... until plan step S6").

## Reach production

1643 and 1644 are dormant until the Go `mail` job and the Go guide-editor paths are switched on (owner steps in the briefs; Go host pages wait for the 1412 UX gate, paused without staging). Guests see nothing until 1646 and 1647, which wait for the guest registration port.
