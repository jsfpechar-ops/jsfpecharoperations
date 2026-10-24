# Guest guide and guest bot

Approved by the owner 2026-10-24. Full plan with the host form mock-up, the handoff flow, costs and risks: [Guest Guide and Guest Bot Plan](https://claude.ai/artifact/FEpcHNdBDMGTMApphjiL1y).

## What it is

One guest guide per property, made of small cards ("Turn on the heating", "Open the garage"). The host fills them; guests read the confirmed ones; the guest bot (Haiku 5.5) answers only from them and asks the host when the guide has no answer. Replaces the earlier "Task 0250 knowledge ingestion" draft, which was never committed (0250 is a different task).

## Owner decisions (2026-10-24)

- Order: guide editor first (no AI), then imports, then the bot.
- Imports: the host pastes both the Booking and the Airbnb link; Apify actors fetch them on the free monthly credit; Haiku 5.5 merges them into draft cards. Conflicts between platforms are shown to the host as "Check this"; the AI never picks. No in-house scraper.
- Never invent: anything the AI is not sure of stays "Missing" or "Check this"; drafts never reach guests.
- Guide and bot free for every host, with a daily cap per property.
- Two doors to one bot: a QR code at the property (public, "everyone" items) and the guest's stay link ("booked" items from 1 day before check-in until checkout). Door codes stay with TTLock only.
- Host replies reach the guest on the page only; no guest email is collected.
- Chat logs: 30 days after checkout (QR chats with no stay: 30 days after the last message).
- In-app support bot for hosts: separate plan.

## Spike (2026-10-24, 3 Booking and 4 Airbnb listings)

Booking (Apify voyager/booking-scraper): address, check-in and check-out times, a generated description, photos, rating. No house rules, facilities list or FAQ. Airbnb: the host's own description with house rules, fees, quiet hours and equipment, but no check-in time. Descriptions contain filler ("boating and scuba diving" in Prague 3) and host editing notes, so imports use them only as hints for cards.

## Briefs

Owner rule (2026-10-24): critical briefs are written by Fable 5.1, or reviewed by Fable when Opus already wrote them; the rest are written by Opus 5.5. Executor is Haiku 5.5 unless the header says Sonnet 5.5.

Critical means one of: a public or guest-facing surface, file uploads, secrets or paid APIs, AI output that could reach a guest, personal data or deletion, a migration.

| Phase | Brief | What | Critical | Written by | Fable review | Executor | State |
|---|---|---|---|---|---|---|---|
| 1 | [0291](../tasks/0291-guest-guide-data.md) | Tables, `guest_guide.py`, the guest gate `for_guest` | yes: migration, guest gate | Opus | yes | Haiku | todo |
| 1 | [0292](../tasks/0292-guest-guide-pages.md) | Host "Guest guide" tab, card list, card editor, "Save and next card" | no | Opus | no | Haiku | todo |
| 1 | [0293](../tasks/0293-guide-photos.md) | Card photos: upload, clean, shrink, serve to owner, delete, orphan sweep | yes: uploads | Opus | yes | Sonnet | todo |
| 1 | 0294 | Guest side: "Your guide" on the stay page; public QR page; QR token; guest photo serving; no-index, caching, rate limits | yes: public surface | Fable | n/a | Sonnet | to write |
| 1 | 0295 | Printable QR sheet for the host (PNG/PDF), rotate the QR link | no | Opus | no | Haiku | to write |
| 2 | 0296 | AI and Apify plumbing: `anthropic` dependency, keys, `ai_usage` ledger, per-property daily caps, kill switch | yes: secrets, money | Fable | n/a | Sonnet | to write |
| 2 | 0297 | Booking and Airbnb import: URL allowlist, Apify run, raw data kept only for the run | yes: outbound calls, untrusted data | Fable | n/a | Sonnet | to write |
| 2 | 0298 | Haiku merge into draft cards: "Check this" only, conflicts shown, scraped text treated as data, eval set from the spike listings | yes: AI to guests | Fable | n/a | Sonnet | to write |
| 2 | 0299 | Paste box and import review UX (accept, edit, dismiss a draft) | no | Opus | no | Haiku | to write |
| 3 | 0300 | Guest bot core: cached guide prompt, `ask_host` tool, refusals, injection rules, rate limits, 30-day chat deletion | yes: AI to guests, personal data | Fable | n/a | Sonnet | to write |
| 3 | 0301 | Host handoff: alert, reply in app, answer shown to guest, "Add to guide" | yes: messaging, personal data | Fable | n/a | Sonnet | to write |
| 3 | 0302 | Guest chat UI on the stay page and QR page, languages | no | Opus | no | Haiku | to write |
| 3 | 0303 | Guide translation for guests (cached per language) and host usage page | no | Opus | no | Haiku | to write |
| end | phase review | Fable reads the diffs of the critical files only, before each phase merges | | | yes | | |

Every brief states, in §2 or the risk list: security (ownership on every query, CSRF, input limits), privacy (no guest data in logs, retention), UX (phone first, one primary action, Czech and English copy), design (catalog classes, tokens, layout guard, 390 px screenshot), function (tests for the happy path and each refusal) and cost (tokens per call, caps). Opus checks the embedded code in a scratch copy before the brief is committed, so the executor copies working code.

Token rules: a Fable review reads only the brief and the files in its risk list, stays under 15k tokens and returns findings, never a rewrite. One review pass, no swarm. Bug fixes found in review go back into the brief by Opus.
