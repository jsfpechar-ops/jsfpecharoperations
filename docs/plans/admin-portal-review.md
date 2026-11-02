# Admin portal review (2026-11-01)

Status: plan only. Held until the Go port is done (owner, 2026-11-01). The access fix 0472 ships now.

## Verdict
The admin area grew one page per feature: seven pages (Console, Customers, Billing, Users, Incidents, Operations, Funnel), each with its own layout, and until 0472 no way between them except a desktop account menu. The data is good; the shape is not. A Wolt-like admin has a few clear places, one list per kind of thing, and shows only what needs a decision.

## Problems, worst first
1. **No way around (fixed by 0472).** The Admin icon opened a console linking only Customers and Payments. Users, Operations, Incidents, Funnel were desktop-menu only, absent on phone. Admin pages showed the Settings tabs.
2. **The same people in two lists.** `/admin/customers` (billing view) and `/admin/users` (account view) list the same hosts. The customer page has two buttons, Manage and Preview, that open the same `/admin/users?manage=` link. One person, two places, two buttons for one action.
3. **Billing is a report, not a tool.** `admin_billing.html` has 12 sections and 7 tables on one page (portfolio, month, unpaid, payments, statement, revenue, trend, movement, discounts, accounts, watch list, trial funnel). The two jobs the owner actually does, mark an invoice paid and export the month, are buried in it.
4. **Trial funnel lives twice.** A "Trial funnel" section in Billing and a separate Funnel page. Its Czech title is a mistranslation ("Tryskový trychtýř", i.e. jet funnel).
5. **Operations shows everything, always.** Seven health blocks (alerts, filings, jobs, feeds, mail, TTLock, Havel) render in full when all is fine. The owner has to read it all to learn "nothing is wrong".
6. **Incidents is a page of its own** for a rare event; it belongs with system health.

## Target shape (four tabs)
| Tab | Holds | Replaces |
|---|---|---|
| Today | Only what needs a decision: overdue, trials ending, unverified, open incidents, failing jobs or filings. Empty state "All clear". | Console queues, Operations alerts |
| Customers | One list of hosts; one detail page with Account (email, invite, disable, delete, open workspace), Plan and invoices, Activity. | Customers + Users |
| Money | Unpaid invoices with Mark paid; month export; MRR/ARR line; trial funnel once. The rest behind "Reports". | Billing + Funnel |
| System | One green line per subsystem; a failing one opens its detail. Incidents as a section. | Operations + Incidents |

Rules as Wolt does them: one primary action per screen, counts on tabs instead of banners, nothing shown when it is fine, same list/detail pattern everywhere, plain words ("Mark paid", not "Statement").

## Order of briefs (after the Go port, one PR each)
1. Merge Users into the customer detail page; drop the duplicate button. Keep every action and its test.
2. Today tab: fold Operations alerts and open incidents into the console queues.
3. Money: unpaid + month export first, other sections under one Reports disclosure; remove the duplicate funnel and fix the Czech title.
4. System: collapsed health lines, Incidents moved in; tabs drop to four.
Each brief removes the old page or section in the same PR (no dead code).
