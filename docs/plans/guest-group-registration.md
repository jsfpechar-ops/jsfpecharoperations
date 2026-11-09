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
| Stay fee | One total for the booking, shown on the lead's phone only, with "Pay once for the whole group". Members see "The stay fee is paid on the first phone." The app never says "paid" | The app cannot know who paid; avoids paying twice |
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

## 7. Owner decisions (recommended answer first)

1. Members see the door code once everyone is registered: yes (same as today for any phone on the hub).
2. Stay-fee pay panel on the lead's phone only: yes.
3. The lead may remove a person entered on another phone: yes.
4. An exact duplicate (document number, name and birth date) is not saved a second time: yes.
5. A place left untouched is freed after 30 minutes: yes.
