# Autopilot and agent-ready UbyHost

State: detailed plan, 2026-11-17, owner decisions recorded below. Nothing is built. No brief exists yet.
Legal positions: [autopilot-legal-positions](autopilot-legal-positions.md).

## 1. Principle

The host is involved only when the app cannot legally or safely decide alone.
Most hosts have one flat; some managers have many. Single-flat owners get an app
that runs itself. Managers, channel managers and AI assistants connect through
one API built on the same foundation.

## 2. Owner decisions (2026-11-17)

| # | Decision |
|---|---|
| D1 | Hide Payments and Booking sites; the guest guide stays. Delete code after Python is retired. |
| D2 | The app may file without a per-stay confirmation. The host stays responsible and must understand it ([A1](autopilot-legal-positions.md#a1-filing-without-a-per-stay-confirmation)). |
| D3 | Build to be ready for managers and channel managers before their numbers are known. |
| D4 | A UbyHost MCP server so a host's AI assistant (ChatGPT, Claude, others) can find and use UbyHost. |
| D5 | Autopilot and API: build and test first, decide pricing after. Ship behind flags. |
| D6 | Technical gaps: take the recommended option in each (section 6). |

## 3. Steering numbers

| Number | Meaning | Target |
|---|---|---|
| Zero-touch rate | Stays that reach an accepted filing with no host action | up; first target set after Workstream B |
| Rejected filings | Refused by UbyPort, per 100 | never worse than today |
| Late filings | Accepted after the legal deadline | zero |
| Host actions per stay | Clicks and messages the host needed | down |
| Exception resolve time | From raised to resolved | under 1 hour median |

## 4. What exists already (checked 2026-11-17)

| Piece | Where | Used by |
|---|---|---|
| Permanent per-property guest link, slug, PIN | `App/app/guest_slug.py`, `apartment.permalink_token` | D |
| "What needs you" card, property health | `App/app/needs_you.py`, `App/app/property_health.py` | E |
| Deadline watchdog, host and operator mail | `App/app/filing_watchdog.py` | E, T4 |
| Five-step stay story, per-property filing option | `App/app/workflow.py` | F |
| Audit table: actor, owner, impersonator | `audit` in `App/migrations_pg/00001_baseline.sql` | C |
| Acceptance records per document version | `App/app/acceptance.py` | F |
| UbyPort code 150 known as "register already holds it" | `App/app/ubyport/errors.py:22-56,138-150` | T1 |
| Notification idempotency keys | `App/app/reporting.py`, `go/internal/ubyport/notify.go` | C |
| Explicit state tables in Go | `go/internal/statemachine/tables.go` | C |
| Push, lifecycle mail, job queue | `App/app/push.py`, `go/internal/jobs` | D, E |
| Document OCR, one AI door | `App/app/doc_ocr.py`, `App/app/ai.py` | G |
| Hostex partnership notes | `docs/HOSTEX.md` | H |
| Env flag style | `UBYHOST_*_LIVE` in `App/app/config.py` | all |

Checked and closed: host subscription billing does not use Stripe. No `stripe` reference in `App/app/billing*.py`, `App/app/routes/billing.py`, `go/internal/billing`, `go/internal/billingjob`. The `/webhooks/stripe` handler acts only on Connect events (`account.updated`, `App/app/stripe_connect.py:415`). Hiding Payments cannot break billing.

## 5. Workstreams

Order: A, B, C run first (B can run beside A). D, E, F follow C. G is small and late. H and I need C and F.
Every workstream ships behind its own flag, off by default, switched on per account for testing (D5).
Tier is the brief risk tier from [workflow](../context/workflow.md#roles-and-models).

### A. Clear the ground (tier B, A3 is tier A)

| Step | Deliverable | Done when |
|---|---|---|
| A1 | Go cutover finished ([remaining](go-full-move-remaining.md), [final](go-sqlite-final.md)) | Python serves no production route |
| A2 (done 2026-11-22, brief 2029) | `UBYHOST_PAYMENTS_RETIRED`: payments/booking off; property page + iCal stay; webhook 2xx; jobs stop; billing stays; data kept | Owner flag after merge; guide + UbyPort unchanged |
| A3 | Real UbyPort test-service proof: NTLM, TLS, WS-Addressing, one accepted record, one duplicate, one rejected record | Receipts stored in the report; mock updated to match any difference found |
| A4 | Legal copy shortened: Terms, DPA, subprocessors, guest notice lose Payments and booking text; Stripe leaves the subprocessor list if nothing else uses it | Lawyer pass; version bump triggers re-acceptance |
| A5 | `docs/limitations.md` refreshed (it still says SQLite only, no Go) | Lint green |
| A6 | After Python is retired: delete payment and booking code, tests, templates, i18n keys, tables (new goose migration), env vars | No reference left; retention lines removed |

Before A2: count open payment requests and direct bookings on production (owner runs one query from the brief). Expected zero because Stripe is in test mode. If not zero, those hosts are told first.
Answer (owner, 2026-11-18, project Q4): none on production; Payments was never used; safe to hide via `UBYHOST_PAYMENTS_HIDDEN`.
Rollback of A2: one flag, `UBYHOST_PAYMENTS_HIDDEN=0`.

### B. Measure (tier B)

| Step | Deliverable | Done when |
|---|---|---|
| B1 | `stay_event` rows: stay id, stage, actor type, time. Stages: created, invited, form started, form complete, filed, accepted, rejected, fee recorded. No personal data | Rows written by Go for new stays |
| B2 | Backfill from `audit` and submission history where possible | Last 90 days present |
| B3 | Admin-only page: zero-touch rate, drop-off per stage, rejected and late filings, by week | Owner reads last month's numbers |
| B4 | Retention line for `stay_event` (same life as the stay) | `retention.py` and RETENTION doc updated |

Output decides the order of D, E and F and sets the first zero-touch target.

### C. Action layer (tier A; built inside the Go port)

A design note comes first and is reviewed by the owner before any brief.

| Step | Deliverable |
|---|---|
| C1 | Design note: the action list with inputs, outputs, errors and allowed actors. Actions: create stay, change dates, cancel stay, set head count, add guest, correct guest, remove guest, file, re-file after correction, record stay fee, send guest invite, send guest reminder, resolve exception, set property autopilot level |
| C2 | Go package `go/internal/actions`: one function per action. Scope check (account, property, grant) happens here and nowhere else |
| C3 | Actor model: host, team member, key, connected app, autopilot, guest, operator. Written to `audit` with grant id. Migration adds `actor_type`, `grant_id` |
| C4 | Idempotency: every write takes a key; table `action_key` (key, actor, action, result, expires). Same key returns the first result |
| C5 | Dry run on every action: returns the changes and the checks, writes nothing |
| C6 | Error catalogue: fixed codes, plain sentence in CS and EN, field name, whether the guest or the host can fix it. UbyPort codes map into it |
| C7 | Filing target interface: `ubyport` now, stay-fee remittance second, room for a third ([A4](autopilot-legal-positions.md#a4-eturista)). Deadline rules per target in a table |
| C8 | Events: each action emits a typed event (stay created, form complete, filing accepted, filing rejected, deadline near, exception raised, exception resolved) into an outbox table. Webhooks and push read from it |
| C9 | Page handlers and jobs moved onto the actions, one area at a time, with a parity test per action |

Done when: a filing from the page and one from the job give the same audit row shape; a repeated key changes nothing; no handler writes stay or guest tables directly (a lint test enforces it).

### D. The guest arrives without the host (tier A for guest pages)

| Step | Deliverable |
|---|---|
| D1 | Setup shows the permanent link and QR once, with ready text for the Airbnb, Booking.com and channel-manager welcome message, and a printable door card |
| D2 | Guest opens the link; the app matches the stay by date; PIN protection unchanged |
| D3 | Reminders by the app when a contact exists: at most 3, in the guest's language, none at night, stop on completion ([A3](autopilot-legal-positions.md#a3-reminders-to-guests)) |
| D4 | "I cannot complete this" link raises an exception for the host |
| D5 | Health row: "a real guest has used your link" (exists in `workflow.py`), with a nudge to hosts whose link was never used |

Done when: a feed stay with no guest e-mail reaches a complete form with zero host actions. Guest-page rules apply (rule 7: browser and geometry tests, 390 px screenshots).

### E. Exceptions are the product (tier B; tier A where it touches filing)

Fixed list. Each type: code, one sentence, deadline it threatens, actions, what the app does if ignored.

| Code | Raised when | One-tap actions |
|---|---|---|
| feed_broken | Calendar feed fails repeatedly | Open feed setting |
| dates_overlap | Two stays collide | Keep A, keep B |
| guest_data_missing | Form incomplete near deadline | Remind guest now, enter data myself |
| guest_cannot_complete | Guest used the D4 link | Call guest, enter data myself |
| document_unclear | OCR and typed fields disagree | Accept typed, ask guest again |
| filing_rejected | UbyPort refused a record | Shows field and fix; re-file |
| filing_unanswered | No receipt in time | Retry, file by hand |
| fee_rate_missing | Stay fee cannot be computed | Set rate |
| police_setup_incomplete | Credentials missing or refused | Open setup |
| lock_code_failed | Door code not created | Retry, send code by hand |
| autopilot_paused | Instruction pending re-acceptance or checks failing | Review and accept |

| Step | Deliverable |
|---|---|
| E1 | `exception` table and state machine (open, snoozed, resolved, expired); raised and resolved through actions (C) |
| E2 | `needs_you`, property health and the watchdog read from it; no second source |
| E3 | One-tap links in mail and push (rules in T2) |
| E4 | Weekly digest: filed, fees due, open exceptions, or "nothing needs you" |
| E5 | Managers: one list across properties with filters |

Done when: every `needs_you` line and watchdog mail maps to one code; a rejected filing is fixed from a phone in under a minute; host-page UX gate passed (rule 10).

### F. Trust ladder (tier A)

| Level | App does | Host does |
|---|---|---|
| 1 Prepare | Assembles and checks | Taps to file |
| 2 File when clean | Files alone when all checks pass | Handles exceptions |
| 3 Full autopilot | Also reminds guests and resolves known cases (duplicate 150, retry on outage) | Handles the rest |

| Step | Deliverable |
|---|---|
| F1 | Property setting with the three levels, extending today's filing option |
| F2 | Standing-instruction text and recorded acceptance per property and version ([A1](autopilot-legal-positions.md#a1-filing-without-a-per-stay-confirmation)) |
| F3 | The "clean" checklist as code: all guests complete, fields valid, no open exception on the stay, credentials valid, inside deadline window |
| F4 | Offer to move up after 5 clean filings in a row; drop to level 1 and raise `autopilot_paused` after a rejected filing caused by app-side data |
| F5 | Audit row per automatic filing: actor autopilot, checks passed |
| F6 | Terms clause and help text |

Done when: a level 3 property files a clean stay with zero host actions and the audit log says why; switching off stops the next filing.

### G. Narrow AI (tier B)

Allowed: compare a document photo with typed fields; explain a rejection in plain words; draft reminder wording; answer host questions.
Never: decide the content of a filing.
One assistant on the host side, measured by exceptions resolved. All calls through the one AI door and its budget. Leon on the guest guide stays as it is (the guide stays, D1).

### H. Connections: API, webhooks, channel managers (tier A)

| Step | Deliverable |
|---|---|
| H1 | Team accounts: invite a named person, role (manager, staff, read-only), properties in scope. Grants per [A2](autopilot-legal-positions.md#a2-team-members-and-outside-keys) |
| H2 | API keys: created by the host, scoped (properties, read or write, document data off by default), shown once, stored hashed, revocable, last-used shown |
| H3 | Public REST API `v1` over the actions: stays, guests, filing status, exceptions, stay fees, properties (read). Idempotency key header, dry-run flag, error catalogue codes |
| H4 | OpenAPI file generated from the Go types; docs page; `llms.txt` |
| H5 | Webhooks: host registers a URL per event type; signed payloads; retries with backoff; delivery log; no document numbers in payloads |
| H6 | Sandbox: any account can create a test property that files to the mock |
| H7 | Channel-manager intake: "push a reservation with guest contact" is the one call a channel manager or PMS needs. First connector: Hostex ([notes](../HOSTEX.md)). Others when a real manager asks; the API is the fallback for all |
| H8 | Rate limits per key; abuse alerts to the operator |

Why this serves D3: iCal feeds carry no guest contact. A channel manager that pushes the reservation with the guest's e-mail removes the manual link step, so these hosts reach zero-touch without pasting anything.

Done when: an outside system creates a stay, receives "filing accepted" by webhook, and a key scoped to one property gets 404 on another.

### I. MCP server and being found by AI assistants (tier A)

| Step | Deliverable |
|---|---|
| I1 | Remote MCP server at one public URL, thin layer over H3. Sign-in by OAuth with the host's UbyHost account; the consent screen is the grant (A2) |
| I2 | Signed-in tools: list stays, what needs me, stay status, remind guest, resolve exception, file stay (dry run first, then confirm), stay-fee summary. Document numbers masked |
| I3 | Public tools, no account: Czech host duties explained, filing deadline calculator for an arrival date, stay-fee rules lookup, "who must register a guest". These answer the questions hosts ask an assistant before they know UbyHost |
| I4 | Tool descriptions written for selection: plain task words in CS and EN ("register foreign guests with the Czech police", "UbyPort", "poplatek z pobytu") |
| I5 | Listings: submit to the connector directories of the major assistants; public docs page "Use UbyHost from your AI assistant" |
| I6 | Every write tool returns a preview first and needs a second call to confirm, unless the property is on level 2 or 3 |
| I7 | Help pages and guide content readable by crawlers the owner allows (ties to the open crawler Terms item) |

Limits to state plainly: no vendor lets a server force itself first. An assistant picks a tool by its description, the user's connected apps and the vendor's directory. I3 to I5 are what raise the odds. Directory acceptance is each vendor's decision.

Done when: from a connected assistant, "which guests still need to register this week" returns the right stays, and "file it" on a level 1 property asks for confirmation.

## 6. Technical decisions (D6)

| # | Gap | Decision |
|---|---|---|
| T1 | UbyPort has no retry protection; duplicate returns 150 | Already classified in `ubyport/errors.py`. The `file` action treats 150 for a record we sent as success "already filed", stores it as accepted with a note, raises nothing. A 150 for a record we never sent raises `filing_rejected` for review. The police check duplicates across their whole database, so a retry after a timeout is safe. Parity test in Go. Proven in A3 |
| T2 | One-tap links act without login | Signed token bound to one exception, one action, one account; single use; 48 h life or until the exception closes; GET shows a confirm page and only POST acts (mail scanners follow links); no personal data on the confirm page beyond stay dates and property name; actions that change filed data or reveal guest data need login; rate limited; audit actor "host via link" |
| T3 | Tenancy checked per query | Three layers. (1) Scope check only in `go/internal/actions` (C2). (2) Postgres row-level security on tenant tables for the database role the API uses, keyed on a per-request setting; a goose migration per table group. (3) A cross-tenant test suite: two accounts, every API route and MCP tool, expects 404. The API launches only after all three |
| T4 | Queue stall hides deadline warnings | A watchdog inside the Go web process on its own timer, not in the queue: reads at-risk stays and the age of the oldest due job straight from the database, mails the host by a direct SES call (not the outbox), and exposes a metric. Grafana Cloud (already used) alerts the operator when the metric is stale. No new dependency |
| T5 | Billing and the Stripe webhook | Checked: no dependency (section 4). Keep the endpoint answering 2xx while hidden |
| T6 | Corrections after filing | The app may re-file alone only when UbyPort rejected the record and the fix is mechanical (format, transliteration). A change to identity fields after an accepted filing always asks the host |
| T7 | Secrets | API keys and webhook secrets: hashed or Fernet-encrypted as today's pattern, never logged, rotation on demand ([rules: secrets](../context/rules.md#secrets)) |

## 7. Privacy and data (rule 2)

| New data | Purpose | Retention |
|---|---|---|
| `stay_event` | Measure zero-touch | Life of the stay |
| `exception` | Tell the host what is wrong | Life of the stay |
| Standing-instruction acceptance | Proof of the host's instruction | Life of the account plus limitation period |
| Grants, API keys (hashed), connected apps | Delegation record | Life of the account plus audit period |
| `action_key` | Safe retries | 7 days |
| Webhook delivery log | Debugging for the host | 30 days, no guest data |
| Reminder count and times | Cap reminders | Life of the stay |

New outbound requests: webhooks to URLs the host sets; responses to connected assistants. Both are host-chosen recipients (A2). ROPA and the privacy policy get one entry each. No new tracking, no new third-party script.

## 8. Rollout

1. Each workstream behind a flag, default off.
2. Owner's own property first, then staging with the mock, then 3 to 5 invited hosts.
3. Autopilot levels 2 and 3 go wide only after A3 passed and the Terms clause is live.
4. API and MCP: private keys for invited managers first; public docs and directory listings after the cross-tenant suite (T3) is green in CI.
5. Each step has a named rollback: the flag.

## 9. Risks

| Risk | Guard |
|---|---|
| Autopilot files wrong data | F3 checklist, level drop in F4, rejected-filings number, A3 proof |
| A missed scope check leaks guest data | T3, masked documents by default |
| Too many notifications | Digest, fixed exception list, caps in D3 |
| Two codebases during the change | Action layer only in Go; Python gets hide-only changes |
| Law changes (eTurista, shorter deadline) | Target interface and deadline table (C7), quarterly watch |
| Scope too wide again | Section 3 numbers decide; nothing outside this plan without a decision line |

## 10. Still open

- Lawyer: wording of the A1 Terms clause and the A2 DPA clause, in the pass already pending. The positions do not wait for it; go-live of levels 2 and 3 does.
- Owner: which managers to invite first, and whether Hostex is still the first connector.
- Owner: pricing of autopilot and API, after testing (D5).
- Owner: SMS or WhatsApp vendor, if reminders by e-mail prove too weak in B3.

## 11. Ordered brief list

None written yet. First briefs, in order, after owner review of this plan:

1. A2 hide Payments and Booking sites, Python (tier B).
2. A2 the same in Go, with the Caddy path list (tier B).
3. B1 `stay_event` migration and writers (tier A: migration).
4. B3 admin page (tier B, host UX gate).
5. A3 UbyPort test-service proof (tier A).
6. C1 action-layer design note (orchestrator, no executor).
7. T4 in-process watchdog (tier A).

C2 onward, D, E, F, H and I are briefed after C1 is approved; their step tables above are the brief outlines.
