# Guest group registration: "Send to the others"

Planning only, 2026-11-09. Part of the [speed-and-ease plan](speed-and-ease.md) (G7). Owner: yes, "done properly".
Goal: every traveller of one booking registers on their own phone at the same time. A family of four finishes in the time of one.
Risk: **filing HIGH** (wrong head count, duplicates or a double send would reach the police) and **privacy** (one guest must never see another guest's data without consent). Every brief from this plan is HIGH RISK.
Facts below were read from code by grep and ranges; line numbers are approximate and each brief re-checks them.

## 1. How it works today (and why a second phone breaks)

| Fact | Where |
|---|---|
| The guest link is per property (`/l/{token}`); the PIN is per property | `routes/guest.py:1245`, `db.py:1001` |
| With mail on, one e-mail "claims" the whole booking; a mailed one-time link sets a signed cookie for that phone | `claim.py:226,657`, `routes/guest.py:270` |
| A second cookie lists the guest ids this phone entered; it decides what the phone may see, edit and remove | `routes/guest.py:41,128,983-1020` |
| Without that cookie the hub shows "Person N" with no personal data | `stay.html:116` |
| There is no way to pass a booking to another phone. `guest_handoff.py` is about the AI guide, not this | `guest_handoff.py:1-25` |

| What goes wrong if a second phone joins today | Where |
|---|---|
| Phone 2 sees "this stay is taken". If it asks for the link again with the same e-mail, phone 1 is locked out | `claim.py:279`, `routes/guest.py:239,1354` |
| With mail off there is no gate at all: anyone with the link and PIN can add people and change the head count | `routes/guest.py:1068` |
| The "is there room?" check reads the count and then inserts, with no lock. Two phones can both pass and go over the head count | `routes/guest.py:2292-2297` |
| Two guests can both be marked as the lead guest | `routes/guest.py:2299` |
| "Add another person" reads, adds one and writes. Two taps at once add one, not two | `routes/guest.py:1640` |
| Duplicate check only warns, and only about people entered on the same phone | `routes/guest.py:1029` |
| A phone that loses its cookie can never edit or remove its people again; only the host can | `routes/guest.py:1830` |
| Nothing is saved until the form is sent; a locked phone loses the entry | `routes/guest.py:1962-1990` |
| Door code and stay-fee panel show on any phone that reaches the hub once the count is met; the app has no "paid" state for guests | `stay.html:47-69`, `routes/guest.py:1403,2415` |

The three race bugs exist today even without this feature (double tap, or two phones with mail off). They are fixed first.

## 2. What the guests see

| Step | First guest (lead) | The others |
|---|---|---|
| 1 | Registers as today. The hub shows "Registered: 1 of 4" | |
| 2 | Under "Add a person" there is a second button: "Send to the others" | |
| 3 | A screen with a QR code, a "Share link" button and one tick: "Share my home address with my group" (off by default) | Scan the QR code or open the link |
| 4 | Hub shows each place: "Person 2: being filled in on another phone", "Person 3: not started" | "Register for 9 to 13 November at Nav apartment" with one button: "Start" |
| 5 | The count ticks up by itself | The normal form, same look. If the lead shared the address: "Same home address as the first guest?" with the address filled and editable |
| 6 | When all are done: "All done", stay fee if on, door code, guide | "You are registered. 3 of 4 done." Then, when all are done: "All done", door code, guide |

Both ways stay: "Add a person" (on this phone) is the primary button, "Send to the others" the secondary one, shown only while places are left.

## 3. Rules

| Topic | Rule | Why |
|---|---|---|
| Invite | One invite per booking, made by the lead's phone. A long random secret, stored only as a hash. Shown as a QR code and a link. The secret sits after `#` in the link, like the claim link, so it stays out of logs | No guessing; no leak through logs |
| Joining | Joining gives the phone a "member" pass for this booking. It never changes the lead's pass, so the lead is never locked out | Fixes the lockout |
| Member rights | Add people, and edit or remove the people that phone entered, until filing. See the count and "Person N" rows. See the door code when everyone is registered (same as today) | Least access that still works |
| Member limits | Cannot see the e-mail or any other person's data. Cannot change the head count. Cannot ask for the claim link again. Does not see the stay-fee pay panel | Privacy; one payer |
| Places (slots) | Starting a form reserves one place for that phone. The place is the server draft (owner decision 7b), so a closed tab or locked phone loses nothing. An untouched place is freed after 30 minutes | No overbooking; no lost work |
| Head count | Enforced by the database, not by a read-then-write: one place number per booking can exist once. "Add another person" becomes a single add-one update. Only the lead changes it; a host override still wins | Fixes the races |
| Lead guest | Exactly one lead per booking, set with a compare-and-set | Fixes the double lead |
| Duplicates | On save, compare with every person in the booking. Same document number, same name and same birth date: do not save again; say "This person is already registered." A child on a parent's passport is not a duplicate (different name and birth date) | Stops a double filing |
| Address sharing | Only if the lead ticks the box. Copies street, town and country, not the surname. The member can change it. The tick is stored on the invite, not on any guest | Consent; matches today's same-phone copy |
| Signature and legal tick | Each adult signs on their own phone. A parent's phone enters the children | Better than one person signing for all |
| Stay fee | One bill per booking, one payer, one reference. See sections 8 and 9 | The app cannot know who paid; avoids paying twice |
| Door code | Shown on every joined phone once everyone is registered, and mailed to the lead's e-mail as today | Everyone needs to get in |
| Lost phone or cookie | The lead can remove a person entered on another phone (without seeing their data) so the place can be filled again | Today this needs the host |
| Invite end | Stops working when the filing is sent, at check-out, or when the lead taps "Stop sharing". A new invite replaces the old one | Limits a forwarded link |
| Stranger with the link | Can at most fill a place with a made-up person. The lead sees the place as taken and removes it; the host sees everything. Joins are rate-limited | Contained |
| Mail off | No claim exists, so "Send to the others" shares the booking page. Places, head count and duplicate rules still apply | Same safety without mail |
| After filing | A person added later follows today's late-guest path. Must be checked before build: how a second send treats people already sent | Filing |
| Live count | The hub asks every few seconds for counts and place states only, never personal data. Without JavaScript the page reloads itself | Nothing to leak |

## 4. Data, cookies, privacy

| Item | Detail |
|---|---|
| New table: invite | booking id, secret hash, share-address flag, created, expires, revoked. No personal data |
| New table: draft (place) | booking id, place number (unique per booking), phone id, form fields, last change. Personal data: needs a line in `App/app/retention.py` and in RETENTION and ROPA. Deleted on sending, else 7 days after the last change or the day after check-out (owner confirms the numbers) |
| New cookie | One signed "member" cookie, strictly needed for the feature, not a tracking cookie. Add it to `App/app/cookie_inventory.py` and the cookie table |
| Outbound requests | None new |
| Dependencies | None new. The QR image reuses the existing QR code path |
| Schema | New migration files, Postgres-portable, through `db.py` helpers |

## 5. Build order (each is one brief, HIGH RISK)

| # | Brief | Visible change | Must prove |
|---|---|---|---|
| 0 | Read-only check: is the police send safe when two saves finish at the same moment, and when a person is added after sending? | None | Written answer with code references; stop if not safe |
| 1 | Atomic head count, add-one update, single lead | None | Test: two saves at once on the last place, only one wins |
| 2 | Server drafts as places ("Welcome back") | Guest never loses work | Retention job test; draft gone after send |
| 3 | Invite, join screen, member pass | "Send to the others" | Lead never locked out; expired and revoked links refuse |
| 4 | Hub place rows, live count, finish cards with stay fee and door code | Group sees progress | Count endpoint returns no personal data |
| 5 | Address sharing and booking-wide duplicate check | Faster forms, no doubles | Member sees an address only with the tick; duplicate is not saved |
| 6 | Lead removes a person from another phone | Recovery without the host | Cannot remove after filing |

Shipped behind a switch that is off by default: staging first, then one property, then all.

## 6. Tests every brief adds to

Two phones at capacity; lead not locked out by a join; member page and count endpoint contain no other person's data; duplicate not saved; child on a parent's passport is saved; invite expired, revoked and replaced; mail-off path; person added after filing; draft retention; no JavaScript path; guest browser tests at 390 px for the invite screen, join screen and each hub state, 0 skipped.

## 7. Owner decisions (answered 2026-11-09)

| # | Decision | Answer |
|---|---|---|
| 1 | Members see the door code once everyone is registered | Yes |
| 2 | Stay-fee pay details on the lead's phone only | Owner worried about a mess: designed in section 8, awaiting yes |
| 3 | The lead may remove a person entered on another phone | Yes |
| 4 | An exact duplicate is not saved a second time | Yes |
| 5 | A place left untouched for 30 minutes is freed | Yes |

## 8. Stay fee in a group (owner decisions 2026-11-09)

Owner: one payer, the person who booked: **yes**. Host "mark as paid": **no**; the app does not record guest payments, that is the host's business. So nothing on any page or mail ever says "paid".

### How the stay fee works today (read from code)

| Fact | Where |
|---|---|
| One switch per property, `stay_fee_collect` (on or off), plus the deployment switch `UBYHOST_STAY_FEE_GUEST_PAY` (off by default). There is no "manual" mode by that name; "on" means the guest is asked to pay by bank transfer or QR, Revolut link, or cash | `db.py:1054-1070`, `config.py:350`, `routes/stay_fees.py:277-302` |
| The guest pays the host's account, never the town's. Reference (VS) = booking id | `routes/guest.py:2430-2443`, `booking_rails.py:28-38` |
| The amount is worked out live each time: rate per night per liable person. Under 18, same-town residents and stays over 60 nights are exempt; the host can override per guest | `stay_fee.py:294,486-509` |
| The pay box shows only when everyone is registered, with "You only pay once for the whole group" | `routes/guest.py:1403,2415-2468`, `guest/_fee_pay.html` |
| Before that, each person sees "Local stay fee for you ... You do not pay now. When everyone in your group has registered, you choose how to pay." | `guest/_fee_estimate.html`, `i18n.py:365-366` |
| The QR code is offered only if a guest entered on this phone is Czech or Slovak | `routes/guest.py:2403` |
| One completion mail per booking, to the lead's e-mail with the host in copy, sent when the registered count reaches the head count. It includes the door code if ready, and a fee block with total, calculation, the names of the pay ways and the reference | `claim.py:372-402,757-806`, `mail_notify.py:1685-1712` |
| A separate door-code mail goes out only if the completion mail was already sent | `door_codes.py:285-336` |
| Mails can already carry a QR image inside them (used by the host's stay-fee mail) | `mail.py:364-402`, `mail_notify.py:1017` |
| There is no stay-fee pay page reachable from a mail link. The hub needs the phone that registered | `routes/guest.py:1354` |

### What is wrong today, even without groups

| # | Problem | Where |
|---|---|---|
| P1 | The mail says "You're registered: nothing else to do" and "There is nothing else you need to do", then asks for money lower down | `i18n.py:654`, `claim.py:372-402` |
| P2 | The mail has no account number, no QR code, no Revolut link and no cash note. It says "payment details are on your stay page", which only opens on the phone that registered | `mail_notify.py:1685-1712` |
| P3 | The mail is sent once. If a person is added, removed or edited afterwards, the amount changes on screen and the mailed amount is stale | `claim.py:757-806` |
| P4 | If one person never registers, the booking is treated as complete after 12 quiet hours and the door code is made, but no completion mail and no fee request are sent, and the pay box stays hidden. Must be re-checked before build | `reporting.py:110,958-1006` |
| P5 | Screen and mail can disagree about the QR code, because the screen decides by the people on that phone and the mail lists all pay ways | `routes/guest.py:2403` vs `claim.py:372-402` |
| P6 | If the host's bank account is removed after collection was turned on, the guest reads "Your host has not finished setting up payment yet" and the host is not told | `guest/_fee_pay.html`, `routes/stay_fees.py:582-602` |

## 9. The moment everyone is registered

The rule: **the mail is the bill.** It reaches the lead wherever they are, it needs no login, and the host gets the same copy, so both sides see the same amount and reference.

### What each person is told, and when

| Moment | Lead (the person who booked) | Other travellers |
|---|---|---|
| Sharing the link | On the "Send to the others" screen: "When everyone has registered, we e-mail you the door code and the stay fee to pay once for the group (up to 400 CZK)." | |
| Filling in the form | Per-person estimate as today | "Local stay fee for you: 100 CZK. The person who booked pays once for the whole group." |
| While waiting | Hub: "3 of 4 registered. We will e-mail you when everyone is done." | "You are registered. 3 of 4 done." |
| Everyone registered | Hub turns into the finish card by itself: stay fee with all pay details, then door code, then guide. The mail arrives at the same time | Finish card: door code and guide, plus one line: "Stay fee for the group: 400 CZK. The person who booked received the payment details by e-mail." No pay buttons |
| Door code made later | The door-code mail repeats the same fee block | Door code appears on their page |
| Amount changes later | One update mail (below) and the hub shows the new total | The line shows the new total |

### The mail

| Part | Content |
|---|---|
| Subject, fee owed | "Everyone is registered for {property}. Stay fee to pay: 400 CZK" |
| Subject, no fee | "You're registered for {property}: nothing else to do" (today's text, now only when true) |
| Top | Door code, if ready |
| Stay fee block | Amount; "for 4 guests, 4 nights"; calculation per guest; "Pay once for the whole group, in any one way:" then each way the host turned on, complete: bank transfer with recipient, account, amount, reference and the QR code inside the mail; "Pay 400 CZK with Revolut" button; cash note. Last line: "Already paid? Then there is nothing more to do." |
| Why that last line | With no paid state, a second mail (door code, or an update) must never look like a second bill |
| Host copy | The host stays in copy, as today. That copy is the host's record of what the guest was asked to pay and under which reference |

### Edge cases

| Case | What happens |
|---|---|
| A traveller, not the lead, finishes last | The lead's open hub updates by itself; the mail is the notice either way |
| Lead reads the mail on another device | Works: the mail holds every pay detail. No page is needed to pay |
| Someone added after the bill | The new person registers; then one update mail: "The stay fee for your group is now 500 CZK (was 400 CZK). If you already paid 400 CZK, pay the remaining 100 CZK with the same reference." |
| Someone removed, or an edit makes a person exempt | Update mail: "... is now 300 CZK (was 400 CZK). If you already paid 400 CZK, ask your host about the difference." |
| Several changes in a row | Changes are gathered for 10 minutes and sent as one mail |
| One person never registers (P4) | Proposed: when the booking is treated as complete after 12 quiet hours, send the same mail for the people who did register ("3 of 4 registered"), with the fee for those 3 and a link for the missing person. Owner decides |
| Everyone exempt, or fee is 0 | No fee block anywhere; "nothing else to do" is true |
| Collection off for the property | No fee on any page or mail; the host collects outside the app, as today |
| Collection on but no pay way works (P6) | Host gets an alert at once ("Guests cannot pay the stay fee: add a bank account"); the guest sees the ways that still work; the mail never lists a way that does not work |
| QR code (P5) | One rule for screen and mail: offered when any guest in the booking is Czech or Slovak. Bank details are shown to everyone |
| Two people pay anyway | Same reference on both payments; the host sees it in their bank and returns one. The app stays out of it |
| Mail is off for the deployment | No lead e-mail exists. The pay box then shows on the phone that shared the link; other phones say "ask the person who shared the link" |

### Data, privacy, rules

| Item | Detail |
|---|---|
| New stored values | The last mailed total and when it was sent, per booking, to detect a change. An amount, not personal data; listed in retention with the claim row |
| Outbound | No new request. Same mail provider, same recipients as today |
| Mail rule | Door code keeps the existing secret-marker pattern so the outbox never stores it (`docs/context/rules.md`, Mail) |
| Copy | New mail and guest texts in every guest language; legal wording of the fee explanation unchanged |

### Briefs (replace brief 7 in section 5)

| # | Brief | Needs the group feature? | Risk |
|---|---|---|---|
| F0 | Read-only check of P4: what a lead receives today when a booking completes after 12 quiet hours | No | none |
| F1 | The mail is the bill: subject and heading by state, full pay details, QR inside the mail, "Already paid?" line; door-code mail repeats the block (fixes P1, P2) | No | legal: mail copy |
| F2 | One rule for pay ways and QR on screen and in mail (P5) | No | none |
| F3 | Update mail when the total changes; stores the last mailed total (P3) | No | privacy: one retention line |
| F4 | Bill at quiet completion for the people registered (P4) | No | Owner decision first |
| F5 | Host alert when collection is on and no pay way works (P6) | No | host page: UX gate |
| F6 | Group texts: share screen promise, member estimate text, member finish line, pay box on the lead's phone only | Yes | none |

F1, F2, F3 and F5 fix today's single-phone flow as well, so they can ship before the group feature.

Open for the owner: (1) F4, bill the registered people when one person never registers: recommended yes. (2) Update mail on a changed total (F3): recommended yes. (3) Is `UBYHOST_STAY_FEE_GUEST_PAY` on in production? The plan assumes it will be.
