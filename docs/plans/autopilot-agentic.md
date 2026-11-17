# Autopilot and agent-ready UbyHost

State: draft for owner review, 2026-11-17. Nothing is built. No brief exists yet.

## Principle

The host is involved only when the app cannot legally or safely decide alone.
Most hosts have one flat; a few managers have many. Single-flat owners get an
app that runs itself. Managers get delegation and an API on the same foundation.

## Steering numbers

| Number | Meaning | Direction |
|---|---|---|
| Zero-touch rate | Share of stays that reach an accepted filing with no host action | up |
| Rejected filings | Filings UbyPort refuses, per 100 | down, never traded for the first |
| Late filings | Filings accepted after the legal deadline | zero |
| Host actions per stay | Clicks and messages a host needed | down |

A feature is built only if it moves one of these or protects filing correctness (rule 1).

## What already exists (checked 2026-11-17, module docstrings only)

| Piece | Where | Reuse |
|---|---|---|
| Permanent per-property guest link, readable slug, PIN | `App/app/guest_slug.py`, `apartment.permalink_token` | Phase 3: this is the "paste once" link |
| "What needs you" card | `App/app/needs_you.py` | Phase 4: becomes the exception list |
| Property health check | `App/app/property_health.py` | Phase 4: source of exception types |
| Five-step stay story, per-property filing option | `App/app/workflow.py` | Phase 5: trust ladder extends that option |
| Deadline watchdog with host and operator mail | `App/app/filing_watchdog.py` | Phase 4: its findings are exceptions |
| Audit table with actor, owner, impersonator | `audit` in `App/migrations_pg/00001_baseline.sql` | Phase 2: actor types added here |
| Notification idempotency keys | `App/app/reporting.py`, `go/internal/ubyport/notify.go` | Phase 2: same idea for writes |
| Push, lifecycle mail, job queue | `App/app/push.py`, `go/internal/jobs` | Phases 3-4 |
| Document OCR | `App/app/doc_ocr.py` | Phase 6 |

So the plan is mostly joining and measuring existing parts, not new machinery.

## Phases

Each phase ends with a check the owner can see. A phase does not start before the one above it passes.

### Phase 0: clear the ground

1. Finish the Go cutover ([remaining](go-full-move-remaining.md), [final](go-sqlite-final.md)).
2. Hide Payments and Booking sites (owner decision 2026-11-17): payment requests, Stripe Connect, direct booking, public property pages. Menu items removed, routes answer 404 in Python and Go, data kept. The guest guide stays. Delete code, tests and tables only after Python is retired.
3. Prove filing against the real UbyPort test service (NTLM, TLS, WS-Addressing).

Check: `/payments` and `/booking-sites` give 404 on production; one test filing accepted by the real test service.

Open before step 2:
- `/webhooks/stripe` is defined only in `App/app/routes/stripe_connect.py`. Confirm host subscription billing does not depend on it.
- Count open payment requests and direct bookings on production. Expected zero (Stripe is in test mode).
- Invoices, demo data, mail, retention and scheduler reference payment modules; hiding must not break them.
- Terms, DPA and subprocessors text mention these features; shorten them in the same lawyer pass.

### Phase 1: measure

1. Record per stay: who performed each step (host, guest, app), and when.
2. Admin-only view: zero-touch rate, the stage where stays stop, rejected and late filings.

No personal data is added: counts and stage names only. Not PostHog; it stays in the app's own database.

Check: the owner can read last month's zero-touch rate and the weakest stage. Phases 3 to 5 are reordered by that result.

### Phase 2: action layer (done inside the Go port, not after it)

1. Named actions for every change to a stay: create stay, set head count, add or correct guest, file, re-file, cancel, record stay fee.
2. Every caller (page handler, job, later an API key) goes through them.
3. Actor on each action: host, guest, autopilot, team member, external key. Written to `audit`.
4. Each write takes an idempotency key. Each action has a dry run that returns what would change.
5. Errors come from one fixed list with a code, a plain sentence and the field concerned.

Check: a filing made from the page and one made by the job produce the same audit row shape; repeating a request with the same key changes nothing.

### Phase 3: the guest arrives without the host

1. One permanent link and QR per property, shown once in setup with ready text for the Airbnb and Booking.com welcome message, and a printable door card.
2. Guest opens the link, the app matches the stay by date. Existing PIN protection stays.
3. The app reminds the guest itself when a contact exists, with rising urgency toward the deadline.

Check: a stay from a calendar feed with no guest e-mail reaches a complete form with no host action.

### Phase 4: exceptions are the product

1. Fixed exception list, about ten types (feed broken, dates overlap, no guest data near deadline, document unclear, filing rejected, filing unanswered, stay-fee rate missing, police setup incomplete, lock code failed, billing problem).
2. Each exception carries: one sentence, the deadline it threatens, one or two actions, and what the app does if ignored.
3. Actions work from the push notification and from the e-mail, with a signed link, without opening a page first.
4. Weekly digest: stays filed, fees due, "nothing needs you" when true.

Check: every `needs_you` line and every watchdog mail maps to one exception type; a rejected filing can be fixed from the phone in under a minute.

### Phase 5: trust ladder per property

1. Prepare: the app assembles, the host taps to file.
2. File when clean: the app files alone when all checks pass.
3. Full autopilot: the app also chases guests and resolves known cases.

The app offers the next level after a run of clean filings. The default level depends on the lawyer answer below.

Check: a property on level 3 files a clean stay with zero host actions, and the audit log explains why.

### Phase 6: narrow AI

Allowed: read a document photo and compare it with typed fields; explain a rejection in plain words; draft guest reminders in the guest's language; answer host questions.
Never: decide the content of a filing. Filed data comes from validated fields and fixed rules.
One assistant, judged by exceptions resolved. All calls stay behind `App/app/ai.py` or its Go successor, inside the existing budget.

### Phase 7: managers and outside agents

1. Team accounts with per-property scope and roles.
2. Cross-property exception list.
3. Published API over the action layer, scoped revocable keys, webhooks for the exception and filing events.
4. MCP server as a thin layer over the API.

Check: a manager's system creates a stay, receives "filing accepted" by webhook, and the key cannot read another property.

## Gaps and open questions

Legal (lawyer):
- L1. May the app file without a host confirmation per stay? The host remains the responsible accommodation provider. Decides the default trust level.
- L2. A team member or an external key acting for the host: what authorisation record is needed, and does the DPA need a clause?
- L3. Reminders sent to guests by the app: legal basis and sender identity (host or UbyHost).
- L4. eTurista: scope and start date unverified. If it replaces parts of the register or the stay fee, Phases 3 to 5 need a second filing target. Check the current law before Phase 2 freezes the action names.

Product (owner):
- P1. How many managers, how many flats each, and which tools they use. Decides how early Phase 7 moves.
- P2. Most calendar feeds carry no guest contact. Phase 3 depends on hosts pasting the link once. If they do not, the zero-touch rate has a ceiling; measure in Phase 1.
- P3. What a host on full autopilot is told and when. Too many "filed" messages recreates the work.
- P4. Pricing: does autopilot or the API belong to a plan?

Technical:
- T1. No protocol-level idempotency with UbyPort (duplicate returns code 150). The action layer must treat 150 as "already filed", not as an error to retry.
- T2. Corrections after filing: what the app may re-file alone and what needs the host.
- T3. Signed one-tap links in mail act without login. Scope each to one action on one stay, short life, single use ([SECURITY](../SECURITY.md)).
- T4. API keys are a new secret type and a new personal-data path: retention line, rate limits, audit, ROPA entry (rule 2).
- T5. Tenancy is enforced per query, not by the database. An external API raises the cost of one missed owner clause; the action layer should be the only place that checks scope.
- T6. Failure of autopilot itself: if the job queue stalls, the watchdog must still warn the host by a path that does not depend on the queue.
- T7. `docs/limitations.md` is stale (says SQLite only, no Go). Refresh before briefs cite it.

Not in this plan: SMS or WhatsApp to guests (new vendor and dependency, needs an owner decision), ČSÚ statistics, guest payments.

## Ordered brief list

None yet. After owner review, the first briefs are: Phase 0 step 2 (hide, Python and Go), Phase 1 step 1 (stage recording), then the Phase 2 action list as a design note before any handler is ported onto it.
