# Plan: guest form isolation

Status: owner approved the idea on 2026-11-16. Briefs 1830-1852 are reserved and not written. The owner decided D4-D6 on 2026-11-16 (section 11).
Goal: a change to the app, a bad app deploy, an app crash or a database outage cannot stop a guest from registering.
Lane F of [optimization wins](optimization-wins.md). Needs the guest registration pages on Go ([remaining](go-full-move-remaining.md): `/l/{token}` routes, 19 in `guest.py`, 0 ported on 2026-11-16).

Rule 1 applies to every brief: nothing here changes what is filed with UbyPort, when it is due, or the evidence of what the guest signed.

## 1. What it guarantees

| Failure | Guest can register? | By what |
|---|---|---|
| Bug in the app, bad app deploy, app restart | Yes | Separate program and release (section 2) |
| App container crashes or runs out of memory | Yes | Own container and memory limit |
| App uses up all database connections | Yes | Own database role with reserved connections |
| Database change that breaks the form | Cannot merge | Compatibility gate in CI (section 5) |
| Postgres down or restarting | Yes | Local copy of form data and disk spool (section 4) |
| Bad Caddy config | Old config stays live | Validate before reload (section 6) |
| Guest program itself is down or mid-deploy | Sees a "try again in a minute" page that retries | Caddy fallback page; two-copy deploy (section 6) |
| Server dies, disk full, DNS down | No | Out of scope; disk alert is brief 1823; second server is section 12 |

## 2. Shape

- New command `go/cmd/ubyhost-guest`, same Go module, built into its own image `ubyhost-guest`. Compose service `ubyhost-guest`, memory limit 96 MB, restart always.
- It serves only the registration form: `GET/POST /l/{token}` and the form's own sub-routes (pin, address suggest, privacy notice, confirmation). Guide, Leon, door code and payment pages stay in the app.
- It is rebuilt and deployed only when its own code changes (CI path filter on `go/cmd/ubyhost-guest`, `go/internal/guestform/**`, `go/internal/guestcontract/**`). An app deploy runs `up -d --no-deps` for the app only and never touches this container.
- It talks to the app only through the two contract tables in section 3. It never reads or writes any other table.
- Database role `ubyhost_guest`: `SELECT` on `guest_form_snapshot`, `INSERT` and `SELECT (id, token hash, status)` on `guest_inbox`, nothing else. `CONNECTION LIMIT 3`, `statement_timeout` 2 s. Pools: app 10, guest 3, of `max_connections` 20.

## 3. The contract (version 1)

| Table | Written by | Read by | Holds |
|---|---|---|---|
| `guest_form_snapshot` | app | guest program | One row per active guest link: token hash, contract version, expiry, form config as JSON (property name, languages, required fields, legal text versions, how many guests are still expected), updated-at |
| `guest_inbox` | guest program | app | One row per submission: idempotency key (unique, made by the form page), token hash, contract version, `received_at`, payload (compressed, then encrypted: D4), status `new / done / held`, host note, attempts, processed-at |

Rules:

1. The app rewrites a snapshot row in the same transaction as any change that affects the form (stay created, guest count changed, link revoked, language or legal text changed). A nightly job rebuilds all rows and reports any difference as an alert.
2. `received_at` is the legal time of submission. Signed-at times, the consent record and UbyPort deadlines are computed from it, never from the processing time.
3. The app worker claims inbox rows with `FOR UPDATE SKIP LOCKED` and, in one transaction, writes the guest rows and marks the inbox row `done`. The unique idempotency key makes a repeated submission a no-op. This is the only path from the form into guest data.
4. The guest is never asked to type a registration again (owner, 2026-11-16). Every check that needs no database runs in the guest program before it accepts the submission (rule 6), so the guest fixes typing mistakes on the spot, also during an outage. After that the app has three outcomes only:
   - `done`: guest rows written.
   - `done` with a note for the host: a guest already registered on this stay (kept once), or more guests than the stay expects (registered and filed like any other guest, in line with the 2026-11-09 filing decision; the host sees the count change).
   - `held`: the submission cannot be attached (link revoked, stay cancelled or moved). The data stays in the inbox, the host gets an alert that names the filing deadline, and attaches it to a stay or dismisses it in one step.
   A stored submission that fails a shared check on processing is a bug, not a guest error: it is `held`, raises the disagreement alert, and the host can correct the field or send the guest their own link, which opens the form filled in with what they entered and the one field marked (brief 1852).
5. Both sides support contract versions N and N-1. A contract change is always two releases: add the new shape, then remove the old one after no N-1 rows remain.
6. Field checks that need no database (formats, required fields, dates) live in one Go package compiled into both programs. The app runs them again on processing; a disagreement is an alert.
7. Inbox payloads are deleted 7 days after `done`. New lines in `App/app/retention.py`, [RETENTION](../privacy/RETENTION.md); no new processor in [ROPA](../privacy/ROPA.md).

## 4. Guest experience and the two fallbacks

- The form shows field errors itself, from the shared checks, before anything is stored. It counts its own inbox and spool rows for the link, so "2 of 3 guests registered" and "add another guest" are right during an outage too.
- One confirmation page for both cases, so the guest never sees a degraded state. After storing, the guest program waits up to 3 seconds for the app.
  - Heading: "Thank you, we have your details"
  - Line: "Your registration is saved. You do not need to do anything else."
  - Small print: "Received 16 Nov 2026, 14:32" (`received_at`, the guest's proof).
  - App answered: the stay information the page shows today follows below.
  - App did not answer: "Your stay information will appear here shortly." The page refreshes on its own and fills in when the app is back. It promises no e-mail.
- The page works without JavaScript (plain refresh).
- Local copy of form data: the guest program keeps all active snapshot rows on disk and refreshes them every minute. With Postgres down, known links still open.
- Disk spool: if the insert fails, the submission is written encrypted to the `ubyhost-guestspool` volume and synced to disk before the guest sees "Received". A loop delivers spooled files to the inbox when Postgres returns; the idempotency key prevents doubles. Uploaded photos use the same volume and the same rule.
- The guest never sees "Received" before the submission is durable in the inbox or the spool.
- The signature is converted to the 480 px black-and-white format here (brief 1818).

## 5. Gates that keep it safe from app changes

| Gate | Blocks |
|---|---|
| `guest-compat` CI job: apply all migrations of the PR to an empty Postgres, then run `ubyhost-guest selftest` from the released image (reads a snapshot, inserts and reads back an inbox row with the guest role) | A migration that breaks the live guest program |
| Migration lint: a file touching either contract table must carry `-- contract: vN`, may only add nullable columns or new tables, and sets `lock_timeout` | Renames, drops and long locks on the contract tables |
| Same selftest against a copy of the production schema before a guest release | A guest release that needs a schema not live yet |
| `guest-outage` CI test in compose: stop the app, submit, start the app, assert processed; stop Postgres, submit, start Postgres, assert processed exactly once | The fallbacks rotting unnoticed |
| Guest release needs the PR label `guest-release` and never runs in the same deploy as an app release | Both programs changing at once |
| Browser and geometry tests for the form run against the guest program, 0 skipped (rule 7) | Layout regressions |

## 6. Deploy safety (covers the whole app)

- Two-copy deploy: start the new container beside the old one, Caddy health check (`/healthz`) must pass, switch, then stop the old one. For both programs.
- Smoke test after every deploy of either program and after every Caddy reload: a full registration on the demo property through the public address, wait for `done`, delete it. The demo property is excluded from UbyPort filing and the test asserts that no submission row was created.
- Automatic rollback to the previous image when the health check or smoke test fails; the owner gets an alert with the failing step. Migrations are add-only within a release, so the previous image runs on the new schema.
- Caddy: `caddy validate` in CI and again on the server before `caddy reload`; never restart for a config change. App deploys do not recreate the Caddy container. When the guest upstream is down, Caddy serves a static page that retries; when the app is down, host pages get a static maintenance page and guest links are unaffected.
- Lower out-of-memory kill priority for `postgres` and `ubyhost-guest` than for the app.

## 7. Watching it

Grafana (already a processor), no new vendor:

- Outside probe of a demo guest link every minute (Grafana synthetic monitoring).
- The smoke-test registration every 15 minutes.
- Alerts: guest program 5xx or down; oldest `new` inbox row over 2 minutes; any spool file over 10 minutes; any `held` row; snapshot rebuild difference; shared-check disagreement; contract version seen that the other side does not support.

## 8. Rollout

1. Deploy safety (section 6) for the app as it is today.
2. Contract tables and app side: snapshot writer, inbox worker, "needs attention". The old form path keeps working and starts writing through the inbox.
3. Guest program built, deployed, serving only the demo property (Caddy matcher).
4. Owner's own properties for 7 days, then all properties.
5. Old form path removed after 14 days with no alert from section 7. Until then `UBYHOST_GUEST_UPSTREAM` switches back in one reload.

## 9. Briefs

| Brief | Work |
|---|---|
| 1830 | Two-copy deploy with health check for the app |
| 1831 | Smoke-test registration on the demo property, with the no-filing assertion |
| 1832 | Automatic rollback and owner alert |
| 1833 | Caddy validate before reload, fallback and maintenance pages, no recreate on app deploy |
| 1834 | Migration: `guest_form_snapshot`, `guest_inbox`, role `ubyhost_guest`, connection limits |
| 1835 | `guestcontract` package: types, version, shared field checks, payload encoding |
| 1836 | App: snapshot writer in the same transaction, nightly rebuild and difference alert |
| 1837 | App: inbox worker, idempotency, `received_at` as the legal time, tests for deadlines and signed-at |
| 1838 | App: host notes and `held` submissions under "needs attention": attach to a stay or dismiss, deadline shown (host UI, UX gate) |
| 1839 | Retention lines and privacy docs for inbox and spool |
| 1840 | `ubyhost-guest` command: form routes, shared checks, own guest count, 3-second wait, one confirmation page without JavaScript |
| 1841 | Local snapshot copy and refresh |
| 1842 | Disk spool, sync before "Received", delivery loop, uploads |
| 1843 | Image, compose service, memory limit, kill priority, CI path filter, `guest-release` label |
| 1844 | `selftest` subcommand and the `guest-compat` CI job |
| 1845 | Migration lint for the contract tables |
| 1846 | `guest-outage` compose test |
| 1847 | Browser and geometry tests against the guest program; 390 px screenshots |
| 1848 | Grafana probe, 15-minute registration, alerts |
| 1849 | Rollout switch `UBYHOST_GUEST_UPSTREAM` and per-property matcher |
| 1850 | Remove the old form path |
| 1851 | Owner drill, twice a year: stop the app, stop Postgres, confirm a registration arrives each time |
| 1852 | Correction link: the guest's own link, after the PIN, opens the form filled in from the held submission with one field marked |

Order: 1830-1833, then 1834-1839, then 1840-1849 and 1852 after the guest pages are on Go, then 1850, 1851.

## 10. Caddy stays

Go could serve HTTPS itself, but Caddy is what lets two programs share one address and lets one be replaced while the other keeps answering. It also holds the certificates, the static files and the scanner blocking of lane B, in 14 MB. It is the one shared piece, so section 6 makes its config changes safe and rare.

## 11. Owner decisions

| ID | Decision |
|---|---|
| D4 | Decided: inbox and spool payloads use the encryption of the existing `_enc` columns. Public-key sealing waits for a second server |
| D5 | Proposed wording in section 4; the owner confirms the three sentences before brief 1840, translations follow the existing guest language set |
| D6 | Decided: a stored submission is never thrown back to the guest to retype. Outcomes and the filled-in correction link are in section 3 rule 4 |

## 12. Later: second server

The guest program and its spool are built so they can move to a second small server in another EU region with no redesign: the inbox insert becomes a pull by the main server, and D4 becomes public-key sealing. Not in this plan.
