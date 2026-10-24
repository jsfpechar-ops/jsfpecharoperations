# Guest guide and guest bot

Approved by the owner 2026-10-24. Full plan with the host form mock-up, the handoff flow, costs and risks: [Guest Guide and Guest Bot Plan](https://claude.ai/artifact/FEpcHNdBDMGTMApphjiL1y).

## What it is

One guest guide per property, made of small cards ("Turn on the heating", "Open the garage"). The host fills them; guests read the confirmed ones; the guest bot (Haiku 5.5) answers only from them and asks the host when the guide has no answer. Replaces the earlier "Task 0250 knowledge ingestion" draft, which was never committed (0250 is a different task).

## Owner decisions (2026-10-24)

- Order: guide editor first (no AI), then imports, then the bot.
- Imports: the host pastes both the Booking and the Airbnb link; Apify actors fetch them on the free monthly credit; Haiku 5.5 merges them into draft cards. Conflicts between platforms are shown to the host as "Check this"; the AI never picks. No in-house scraper.
- Import once: each listing (Booking, Airbnb) can be imported once per property, for good; a failed run does not count. After that the host fills the form.
- Never invent: anything the AI is not sure of stays "Missing" or "Check this"; drafts never reach guests.
- Guide and bot free for every host, with a daily cap per property.
- Two doors to one bot: a QR code at the property (public, "everyone" items) and the guest's stay link ("booked" items from 1 day before check-in until checkout). Door codes stay with TTLock only.
- Host replies reach the guest on the page only; no guest email is collected.
- Chat logs: 30 days after checkout (QR chats with no stay: 30 days after the last message).
- In-app support bot for hosts: separate plan.
- The guest bot is called "Leon (AI)" everywhere guests see it; it always says it is an AI.

## Leon (AI): character (owner, 2026-10-24)

Leon is the guest bot. He should sound like the best hotel concierge in the world: kind, quick, understanding and helpful. Brief 0350 turns this section into the system prompt and the eval set.

- **Warm and unhurried.** He never makes anyone feel silly for asking, and a guest arriving tired at night gets calm, short answers.
- **Answers first.** The first sentence is the answer. Steps follow, one per line, written exactly as the host wrote them. He offers the card's photo or video when it has one.
- **Understanding.** When something is wrong (cold flat, locked out, no hot water), he says he's sorry it happened, gives the host's fix straight away, and asks the host if the fix is not in the guide. He reads worry or frustration and answers it before anything else.
- **Anticipates, from the guide only.** He may add one useful next thing that the guide says, for example "Checkout is at 10:00, and the keys go in the box by the door." He never adds tips the host did not write.
- **Honest above charm.** Personality never beats "never invent". If the guide has no answer, he says so warmly and asks the host: "I don't want to guess about this, so I've asked Jana, your host. I'll show her answer here as soon as she replies." He never promises a time the host has not given.
- **Discreet.** He never repeats codes or private details to someone outside the booked window. He never discusses other guests, the host's private life or prices the host did not write.
- **Speaks the guest's language.** He replies in the language the guest writes in, with the same warmth.
- **Brief.** Only what the guest asked for, usually one or two sentences plus steps when needed; short answers also keep the cost down. He never gets the guest's name. No emojis in problems; at most one friendly emoji in a welcome. No exclamation marks when something is wrong.
- **Always an AI.** He is "Leon (AI)". If asked, he says he is the host's AI assistant and that the host can always be reached through him.

Sample tone: "Good evening, Anna, welcome to Vinohrady. To turn on the heating, press the round button on the boiler in the hallway cupboard until the display shows 22. If it shows E1 instead, hold the reset button for five seconds. Anything else I can help with tonight?"

Czech: "Dobrý večer, Anno, vítejte na Vinohradech. Topení zapnete kulatým tlačítkem na kotli ve skříni v předsíni, dokud displej neukáže 22. Pokud ukáže E1, podržte pět sekund tlačítko reset. Můžu vám ještě s něčím pomoct?"

## Spike (2026-10-24, 3 Booking and 4 Airbnb listings)

Booking (Apify voyager/booking-scraper): address, check-in and check-out times, a generated description, photos, rating. No house rules, facilities list or FAQ. Airbnb: the host's own description with house rules, fees, quiet hours and equipment, but no check-in time. Descriptions contain filler ("boating and scuba diving" in Prague 3) and host editing notes, so imports use them only as hints for cards.

## Briefs

Numbers: this plan owns tasks 0341 to 0359 (renumbered from 0291 to 0305 on 2026-10-24: another thread used 0291 to 0302 on main) and migrations 0013, 0014 and 0016. Havel (host help bot) owns 0310 to 0329 and migrations from 0015; its 0310 is the shared AI core (`ai.py`, `anthropic` decision, `ai_usage` by feature, kill switch, caps) that 0346 and later build on.

Owner rule (2026-10-24): critical briefs are written by Fable 5.1, or reviewed by Fable when Opus already wrote them; the rest are written by Opus 5.5. Executor is Haiku 5.5 for every brief (owner, 2026-10-24); Fable reviews the diffs of critical briefs before merge.

Critical means one of: a public or guest-facing surface, file uploads, secrets or paid APIs, AI output that could reach a guest, personal data or deletion, a migration.

| Phase | Brief | What | Critical | Written by | Fable review | Executor | State |
|---|---|---|---|---|---|---|---|
| 1 | [0341](../tasks/0341-guest-guide-data.md) | Tables, `guest_guide.py`, the guest gate `for_guest` | yes: migration, guest gate | Opus | yes | Haiku | todo |
| 1 | [0342](../tasks/0342-guest-guide-pages.md) | Host "Guest guide" tab, card list, card editor, "Save and next card" | no | Opus | no | Haiku | todo |
| 1 | [0343](../tasks/0343-guide-photos.md) | Card photos: upload, clean, shrink, serve to owner, delete, orphan sweep | yes: uploads | Opus | yes | Haiku | todo |
| 1 | [0344](../tasks/0344-guest-guide-view.md) | Guest side: "Your guide" on the stay page; public QR page; QR token; guest photo serving; no-index, caching, rate limits | yes: public surface | Fable | n/a | Haiku | todo |
| 1 | [0345](../tasks/0345-guide-qr.md) | Printable QR sheet for the host (PNG/PDF), rotate the QR link | no | Opus | no | Haiku | todo |
| 2 | 0346 | Dropped: the shared core 0310 already has per-feature switches and caps; the "leon" and "guide_import" settings ride in 0348 and 0350 | | | | | dropped |
| 2 | [0347](../tasks/0347-guide-import-fetch.md) | Booking and Airbnb import: Apify key and config, URL allowlist, Apify run, raw data kept only for the run | yes: outbound calls, untrusted data | Fable | n/a | Haiku | todo |
| 2 | [0348](../tasks/0348-guide-import-merge.md) | Haiku merge into draft cards: "Check this" only, conflicts shown, scraped text treated as data, eval set from the spike listings | yes: AI to guests | Fable | n/a | Haiku | todo |
| 2 | [0349](../tasks/0349-guide-drafts.md) | Draft review: source line and "Discard this draft" on the card editor (paste box dropped to keep AI cost down) | no | Opus | no | Haiku | todo |
| 3 | [0350](../tasks/0350-leon-core.md) | Guest bot core: cached guide prompt, `ask_host` tool, refusals, injection rules, rate limits, 30-day chat deletion | yes: AI to guests, personal data | Fable | n/a | Haiku | review |
| 3 | [0351](../tasks/0351-guest-handoff.md) | Host handoff: "needs you" alert and one mail per batch, reply in app, answer shown to guest, "Add to guide" | yes: messaging, personal data | Fable | n/a | Haiku | review |
| 3 | [0352](../tasks/0352-guest-chat-ui.md) | Guest chat UI on the stay link and QR guide pages (all kinds, host answers, waiting state, emergency block), QR contact line; the guide link on the form and claim pages is split out to a later brief (claim gate) | no | Opus | no | Haiku | review |
| 3 | [0353](../tasks/0353-guide-translation.md) | Guide translation for guests (cached per card and language, filled after the response, facts checked) and one host usage line instead of a page; migration from the lint | no | Opus | no | Haiku | review |
| 1 | [0354](../tasks/0354-guide-full-catalog.md) | Full card catalog: 17 default cards (24 kinds) with checklist prompts and detailed ghost text per field; progress counts skipped as answered | no | Opus | no | Haiku | todo |
| 1 | [0355](../tasks/0355-guide-quick-answers.md) | Quick answers: 5-step yes/no wizard, `guide_fact` table, fact lines inside cards for guests (6 languages) and Leon, "Your guide" summary | yes: migration, guest surface, AI to guests | Opus | yes | Haiku | todo |
| end | phase review | Fable reads the diffs of the critical files only, before each phase merges | | | yes | | |

Every brief states, in §2 or the risk list: security (ownership on every query, CSRF, input limits), privacy (no guest data in logs, retention), UX (phone first, one primary action, Czech and English copy), design (catalog classes, tokens, layout guard, 390 px screenshot), function (tests for the happy path and each refusal) and cost (tokens per call, caps). Opus checks the embedded code in a scratch copy before the brief is committed, so the executor copies working code.

Token rules: a Fable review reads only the brief and the files in its risk list, stays under 15k tokens and returns findings, never a rewrite. One review pass, no swarm. Bug fixes found in review go back into the brief by Opus.
