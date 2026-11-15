# Plan: Havel, Leon, guest payments, mail and double-booking alarm: hardening and next capabilities

Status 2026-11-15. Scope and plan only: **no briefs written** (owner 2026-11-15). Go only ([go-first](../context/go-first.md)).

Source: five read-only reviews on 2026-11-15 (Havel, Leon, guest payments, outgoing mail, double-booking alarm). No Critical or High finding in any of them. Payments coverage was partial; see [second pass](#p2-second-pass-not-yet-reviewed). File:line references are from those reviews and must be re-checked when a brief is written.

Goal: Havel is the host support agent who can act with the host's tap; Leon is the guests' 24/7 concierge with enough context and an easy way in; both stay cheap and hard to abuse; guest payments are safe to switch from Stripe test to live.

## Decisions (owner, 2026-11-15)

- **One shared AI budget** for Havel and Leon stays. Abuse protection is built inside it ([budget](#shared-budget-and-abuse-protection)).
- **Havel never changes:** IBAN or payout details, login or e-mail, team members, billing, UbyPort credentials, or anything that deletes. For these he only opens the right page.
- **Lookups:** the model sees ids, dates and statuses only. Guest names appear only in the server-rendered card. No guest name goes to the AI provider through a lookup.
- **Host mail goes out in the host's language** (reverses the English default at `App/app/mail_notify.py:44`).
- **Proposed, owner to confirm:** Havel limits in [H0](#h0-limits-and-tokens).

## Order

1. P1 items 1-3 and L1 (money and safety).
2. Shared budget and abuse caps (B1-B6, P1 item 4).
3. P2 second pass.
4. H0-H3 (Havel).
5. L2-L4 (Leon port, context, access).
6. H4 and L5 (personalities).
7. M1-M5 (mail). M2 ships with L4.
8. D1-D6 (double-booking alarm). D1-D3 first.

## Payments (guests paying hosts, Stripe Connect direct charges, test mode)

Hosts pay UbyHost by invoice and QR Platba, not Stripe ([ENVIRONMENT](../ENVIRONMENT.md)).

Sound (verified by reading): webhook signature over the raw body with 300 s tolerance and 1 MiB cap; amount, currency, quantity and connected account all server-side; state changes from the webhook, not the redirect; server-built return URLs; hosted Checkout only, no card data on the server.

### P1 Fix before Stripe goes live

1. **Key/mode guard.** `go/internal/payments/onboarder.go:95-100` accepts any non-empty key for mode `test` or `live`. Check the `sk_test_`/`sk_live_` prefix at startup and the event's `livemode` in the webhook; refuse on mismatch.
2. **Lost confirmation mail.** `booking_webhook.go:322-340`: "paid" commits, then audit and mail run outside the transaction; a retry sees `paid` and skips. Make the mail a queued job written in the same transaction.
3. **Failed clash refund.** `booking_webhook.go:345-366`: refund relies on Stripe retries only; on failure the guest is paid with no booking and no refund. Record a `refund_due` state, retry from a sweeper job, alert the operator.
4. **Checkout abuse.** `go/internal/web/booking/checkout.go:333`: 20 POSTs per hour per IP, no bot check, each one a hold plus a Stripe call against the cap shared by all hosts (`onboarder.go:113-114`). Add Turnstile, a per-property cap on open holds, and a per-host share of the Stripe call cap.
5. **Refunds and disputes.** `webhook.go:289-294` handles neither. Handle `charge.refunded` and `charge.dispute.created`: update the local row, tell the host.

### P1 Lower priority

- Session lives 31 min, hold 15 min (`checkout_session.go:28`, `checkout.go:40`): align them.
- `account.updated` out of order (`webhook.go:304-319`): compare `created`.
- Webhook rate limit runs before signature check (`webhook.go:108-123`): verify first, then count.
- Webhook does not compare paid amount, currency or `account` with the DB row (`webhook.go:393-425`): add as defence in depth.

### P2 Second pass (not yet reviewed)

Host billing, entitlement and cut-off (must confirm a paused host can still file to UbyPort, hard rule 1); `billing_snapshot` and the statement parser; live Python paths (`routes/payments.py`, `booking_webhook.py`, `stripe_connect.py`, `booking_cancel.py`); Connect start/return handlers; IBAN edit protection (re-auth, notification mail; K-S12); direct rails; CSP and CSRF exemption wiring.

## Shared budget and abuse protection

One monthly USD budget (owner). Inside it:

- **B1 Slices.** The anonymous QR door may use at most 20% of the month's budget. Signed-in hosts (Havel) and verified stay guests (Leon stay door) share the rest. A full slice stops only itself.
- **B2 Per-property daily cap for Leon,** counted per property, not per browser cookie, so clearing the cookie gains nothing (today: `guest_leon.py:103-108`). Start: 15 model messages a day on the QR door, 40 on the stay door.
- **B3 Bot check on the QR door:** Turnstile before the first message. Check client-IP handling behind the proxy first (`rate_limit.py:121`).
- **B4 Reserve before calling.** Count the message atomically before the model call, release on failure. Closes the Havel parallel-request race (`havel_handlers.go:450,489`).
- **B5 One host alert per property per day** when Leon is over a cap, not one `guest_question` per conversation (`leon.py:621-634`).
- **B6 Emergency replies cost nothing** and are never blocked by a cap, pause or budget (L1).

## Havel (host support)

Sound: CSRF and login on every POST; properties scoped to the workspace; model-supplied ids validated against that list; replies cannot carry markup or free URLs; links only from fixed page ids. Five confirm-card actions exist: show_guest_link, create_stay, create_cleaning, sync_calendars, new_pin (`havel_data.go:157`). Nothing is written until the host taps.

### H0 Limits and tokens

- Today: 600 chars, 5 per 10 min, 8 a week, 15 a month, x5 on Max (`havel_data.go:60-69`).
- **Proposed:** 10 per 10 min, 30 a week, 100 a month, x5 on Max kept. A tap on a confirm card does not count. Ship only together with the token cut below and B4.
- **Token cut:** the whole guide (about 41k chars) goes into every call and the 5-minute cache is mostly cold (`havel_engine.go:70-72`). Send the prompt, the page table and only the guide sections for the detected topic.

### H1 Scoped lookups

Server-side lookup step: find a stay or a filing in the host's workspace by date, property or status. The model receives ids, dates and statuses; the card shows names. The reply validators (`havel_engine.go:503-560`) must accept numbers that come from a lookup result.

### H2 Cards

- Open doručenka or receipt: links to `GET /reservations/{id}/dorucenka.zip`, `/submissions/{id}/receipt.pdf`, `/submissions/{id}/errors.pdf` (`go/internal/web/exports/routes.go:27`).
- Find a page: exists; extend the page table where gaps show in `havel_gap`.
- Settings changes: one validator, card and route per setting, starting with property setup (`POST /apartments/{id}/setup`) and workspace export. The excluded list in Decisions gets a link card only.
- `create_stay` posts to `POST /reservations`, found only in Python (`App/app/routes/admin.py:3865`): the Go port comes first.

### H3 Memory

Keep the proposed action JSON in the signed history (today prose only, `havel_engine.go:361-362`) and add whether the card was confirmed, so "change the date" and "do it again" work.

### H4 Prompt and smaller fixes

- Rewrite `havel_prompt.txt` as the support persona: calm, exact, short; says what he will do and asks before doing it.
- Align prompt and validator limits (1200 vs 1500 chars, 600 vs 800).
- Hitting a limit must offer the support form, not forward the message unasked (`havel_handlers.go:436-463`).
- Names the host types reach the provider and `havel_gap` (`havel_engine.go:96-100`, `havel_store.go:234-251`): check the retention entry for `havel_gap`; widen redaction where practical.
- Limit keys use Account.ID while properties use Workspace.ID (`havel_handlers.go:199,255`): check team members get the right multiplier.

## Leon (guest concierge)

The live guest chat is Python (`App/app/leon.py`, `routes/guest_leon.py`); Go has only the host wizard. Sound: 192-bit rotatable QR token; cards loaded by the chat's own property; stay door behind permalink, PIN and device claim; answers must cite a card and every number must come from it; UI uses `textContent`; chats purged after 30 days.

### L1 Emergency first (do before the port, go-first exception to be named in the brief)

- The paused, slow-down and busy checks return before the danger check (`leon.py:526-537`): a guest writing "fire" while paused gets no 112 reply. Run the danger check first, answer with fixed copy, always notify the host.
- Fallback keyword list misses "heart attack", "can't breathe", "choking", "overdose" (`leon.py:113-117`).

### L2 Port the guest chat to Go, with these fixes

- Refusal pause per device, not per stay; asking for the door code is not a strike (`leon.py:644-650`).
- An answer containing `@` (wifi password, e-mail contact) is downgraded to ask_host (`leon_core.go:321`): allow `@` when it comes from the cited card.
- `internal_name` goes to the provider (`guest_leon.py:53`): send the public name.
- Prompt says "never repeat door codes" while a keys card may hold one: decide one rule, keep it consistent with the [entry-code plan](entry-code-external-guide.md).

### L3 Context

- Add to the prompt: stay dates, nights, guest count, current date and time, city (stay door only; no names).
- New cards: public transport and airport, nearby shop and pharmacy, luggage, tourist tax and fees, host availability hours.
- Raise the 40-word, four-step reply cap for troubleshooting answers.

### L4 Guest access

Today: QR sticker (`/g/{token}`, print page at `/apartments/{id}/guide/qr`) and a link on the stay page. No mail links to the guide.

- Stay-guide link in the pre-arrival and completion mails.
- The sticker QR hands a guest with a claimed device over to their stay door.
- "Guest QR 404 without IBAN" in status is the payment QR, not this one.

### L5 Personality

Rewrite `leon_prompt.txt` as the 24/7 concierge: warm, brief, local; never guesses; passes the question to the host when the guide is silent.

## Mail

Sound (judged from HTML source, not rendered): one shared 600 px layout with logo, one button, footer and preheader (`App/app/mail_notify.py:484-542`); text part always sent; values escaped; guest mail in six languages with Reply-To set to the host; no open or click tracking; List-Unsubscribe on lifecycle mails. Mail is built in both Python and Go and kept equal by golden files (`App/tests/golden/mail/`), so every copy change lands in both until the Python builders retire.

- **M1 Host language (owner decided).** `HOST_MAIL_LANGUAGE = "en"` (`mail_notify.py:44`), also hard-coded for door-code notices (`:1589`, `:1694`) and guest details (`:2035`); the double-booking mail is English only (`go/internal/mail/double_booking.go`). Send every host mail in the host's language; Czech copy mostly exists.
- **M2 Guide and Leon links in guest mail** (same work as [L4](#l4-guest-access)): completion, pre-arrival reminder and door-code mails. Completion today says "nothing else to do" and nothing about arrival.
- **M3 Bounces and complaints.** No code handles SES feedback ([SES](../SES.md)); stop mailing an address after a hard bounce or complaint and show the host that the guest's address failed. Later: move DMARC off `p=none`.
- **M4 Subjects.** Stay dates in guest subjects (claim, completion, door code); a specific login-link subject; strip control characters from subjects at enqueue (`App/app/mail.py:325`).
- **M5 Door-code notice batching.** 12 variants per stay event, no batching seen (`host_i18n.py:4985-5020`): one mail per stay per day.
- **M6 Look check.** `App/scripts/mail_golden.py --out DIR` renders the goldens; take 390 px screenshots, check dark mode and blocked images (logo is remote, `mail_notify.py:36`).

Not reviewed: bodies of claim, reminder, payment, invoice, site-booking, billing and lifecycle mails; de/es/fr/uk copy; reminder and deadline send frequency.

## Double-booking alarm

Go only: `go/internal/ical/doublebooking.go`. Runs at the end of each iCal feed sync (hourly job or "Sync now"). Per property, half-open interval (same-day turnover is fine), active stays only. One alert per stay pair plus one mail to the entity contact address; clears itself. Prevention exists only on the booking site (advisory lock and re-check at checkout, re-check and refund in the webhook).

- **D1 Check on every stay write,** not only at sync: manual create and edit, site booking paid. Today a property with no working feed or a paused plan is never checked (`syncall.go:55-60`, `syncfeed.go:269-271`).
- **D2 Booking.com closures.** `CLOSED - Not available` is imported as a stay (`parse.go:199-204`), so a booking mirrored from another portal looks like a clash (inferred, confirm with a real feed). Treat a closure with the same dates as another feed's stay as a mirror.
- **D3 Blocks.** Host-blocked dates are skipped on import (`syncfeed.go:327-340`), so the booking site can sell them. Import them as blocked ranges that `DatesAvailable` honours.
- **D4 Dismiss sticks.** The next sync re-raises a dismissed pair (`doublebooking.go:129-135`); respect `user_dismissed` per pair key.
- **D5 Actionable alert.** Add `double_booking` to the alert actions (`alerts.go:54-70`), link both stays, show both date ranges and sources; mail in the host's language (M1); do not skip silently when the contact address is missing. One mail for a three-way overlap.
- **D6 Shorter selling window.** Fetch the feeds fresh at checkout or webhook time; alarm when a feed has had no successful read for N hours. The exemption for a manual stay with identical dates (`doublebooking.go:37-38`) hides a real clash: narrow it.

Not reviewed: production job and path flags, what the portals export and how often they poll, overlap checks on manual date edits (the manual-create warning is Python, `App/app/routes/admin.py:3889`), the cleaning calendar.
