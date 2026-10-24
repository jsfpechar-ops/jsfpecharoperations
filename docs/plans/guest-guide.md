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

| Phase | Brief | What | State |
|---|---|---|---|
| 1 | [0291](../tasks/0291-guest-guide-data.md) | Tables `guide_item`, `guide_photo`; `guest_guide.py` | todo |
| 1 | 0292 | Host guide page: a "Guest guide" section in property settings, topic cards, progress, must-have five | to write |
| 1 | 0293 | Card editor: fixed prompts per card, visibility, photo upload, video link | to write |
| 1 | 0294 | Guest side: "Your guide" tab on the stay page, QR page (read-only) | to write |
| 2 | 0295+ | `anthropic` and Apify decisions; paste box; Booking + Airbnb import; "talk to steps" | to write |
| 3 | 0298+ | Guest bot, host handoff, abuse caps, "Add to guide", translation | to write |
