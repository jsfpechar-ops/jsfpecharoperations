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

## Decisions (owner, 2026-11-22)

- D1: up to 3 extra entry codes per apartment, besides the TTLock door code (table `apartment_entry_code`, 2032).
- D2: each code has a type (building_entrance, gate, garage, bike_room, other; `other` needs a label of 60 characters at most); guests see `<Type label>: <code>`; secrecy rules unchanged.
- D3: the post-submit guest screen gets one "Your guide" block (our guide first, else the host's link, no codes); blocked on the guest port (2033). Submit redirects to the stay page with `saved=1` (`guest.py:2770`), so the block lives there; 2033 and 1666 must share one guide block, not two.
- D5 (later 22nd): guest order = arrival order: gate, building entrance, apartment door, garage, bike room, other. Leon: code questions go to the host (`ask_host`), guest sees a fixed text pointing to the confirmation email and stay page (2037). No automatic re-send on code change.
- D4: guide import gains a public-URL source (Notion first) with a code filter before and after the model; drafts only; host sees a count (2034, 2035).

## Briefs

| # | Title | Status | Depends on | Tier |
|---|---|---|---|---|
| [1660](../tasks/1660-schema-check-goose-only-columns.md) | Schema checks accept goose-only columns | done (#1094) | none | A |
| [1661](../tasks/1661-entry-code-schema.md) | Goose 00022 columns + export guard | done (#1095) | 1660 | A |
| [1662](../tasks/1662-entry-code-retention.md) | Retention step `entry_codes` (Go + Python twin for the golden) | done (#1095) | 1661 | A |
| [1663](../tasks/1663-go-mail-entry-code-marker.md) | Go mail indexed markers `{{entry_code_1..3}}` | blocked (rewrite for 3 codes first) | none | B |
| [1668](../tasks/1668-go-pages-layout-lint-harness.md) | Browser harness: layout lint + 390/768/1280 screenshots on Go pages (local Go binary, no staging) | **todo, runnable now** | none | B |
| [1664](../tasks/1664-go-guide-external-url.md) | Go guide editor: external link field | todo after 1661 and 1668 | 1661, 1668 | B |
| [1665](../tasks/1665-host-ui-entry-code-field.md) | Settings-page entry codes | replaced by 2036 | none | none |
| [1666](../tasks/1666-stay-page-access-guide-blocks.md) | Go stay page blocks | blocked | 1661, 2032, 2036, 1664, 1668 (guest paths), guest registration port | B |
| [1667](../tasks/1667-completion-receipt-entry-code-guide.md) | Go completion receipt | blocked | 1661, 2032, 2036, 1663, 1664, guest registration port, Go `mail` job live | B |
| [2032](../tasks/2032-entry-codes-multi-schema.md) | Goose 00023 `apartment_entry_code` (3 codes), retention, guard | **todo, runnable now** | 1661, 1662 | A |
| [2033](../tasks/2033-guest-finish-guide-block.md) | Guest post-submit "Your guide" block | blocked | 1664, 1668, guest registration port | B |
| [2035](../tasks/2035-guide-import-code-filter.md) | Code filter for imported guide text | **todo, runnable now** | none | B |
| [2034](../tasks/2034-guide-import-public-url.md) | Guide import from a public URL (Notion), drafts, codes left out | todo after 2035 | 2035, 1668 | B |
| [2036](../tasks/2036-go-apartment-access-page.md) | Go page `/apartments/{id}/access`: entry codes, guest preview, door-code status | todo after 2032, 1668 | 2032, 1668 | B |
| [2037](../tasks/2037-leon-entry-code-pointer.md) | Leon: code questions go to host, fixed email/stay-page text, no code in prompt | todo after 2035 | 2035 | B |

## Proof it looks good (owner 2026-11-14)

No PR merges with "screenshots pending". 1668 starts the Go web binary locally and runs `layout_lint.js` with 390/768/1280 screenshots, so 1664 and 1665 (host pages) use it directly. 1666 (stay page) adds guest browser and geometry tests plus nine screenshots (three combinations, three widths) and checks order, overflow, wrapping and 44 px targets. 1667 (receipt) renders the golden mail HTML in Chromium at 390 and 1280 and checks the text part and fallback.

## Why 1660 exists

`db.postgres_schema_status()` builds the expected columns from SQLite only (`App/app/db.py:1288`) and counts any column-count difference as a mismatch (`:1311`); a mismatch makes the Python app refuse to start. 00018 would be the first goose-only `ADD COLUMN`, so it cannot merge before that check knows goose-only columns (rules.md §Database, "untried ... until plan step S6").

## Reach production

1663 (blocked) and 1664 are dormant until the Go `mail` job and the Go guide-editor paths are switched on. Hosts enter codes only on the new page of 2036: after it deploys the owner adds `/apartments/*/access` to `UBYHOST_GO_PATHS`, then sets `UBYHOST_GO_ACCESS_PAGE=1` so the guide index links to it (a link before the path is listed would 404). Guests see codes only after 1666 and 1667, which wait for the guest registration port; 2033 (post-submit guide block) waits for it too. 2037 (Leon pointer) and 2035 can run now. 2034 needs a real Apify check of a Notion page before it is enabled.
