# Final briefs: finish the move to Go and retire SQLite

Written 2026-11-15 for the owner (Josef). Docs only: nothing here touches a server or `UBYHOST_GO_PATHS`. Companion to [go-full-move-remaining](go-full-move-remaining.md), [sqlite-retirement](sqlite-retirement.md) and the [cutover runbook](go-cutover-runbook.md).

## 1. What "SQLite migration" means here

The data already lives in PostgreSQL (live, WAL-G backups, schema v45, `UBYHOST_SCHEMA_APPLY=go`). What is left of SQLite is: the Python suite's test database, the Python SQLite dialect layer, 44 frozen SQLite migrations, and the rollback path (`pg-cutover.sh`, `restore.sh`, the `sqlite3` binary and one archived file on the server). The briefs 1474-1480 finish steps S6-S14 of [sqlite-retirement](sqlite-retirement.md). S1-S5 are done (briefs 1470-1473, 1263 have reports); S8 is done by the executor AI (11-14); S10 is the proof checklist of 1473 and is the owner's.

## 2. What these briefs are, and what they are not

Each brief has the same sections as 1595: objective, context, files, steps, do-not-touch, commands, acceptance, stop-and-ask, report, plus a rollout wave and a rollback line. They are **scope briefs**: routes, source lines, files, acceptance checks, rollout and rollback are final, but they carry `Status: scoped`. Before Haiku can run one, its exact-diff pass must add the sha256 table, the sidecar code and the `grep -cF` anchors (the way 1595 has them). Writer per tier: **Opus for tier A, Sonnet for tier B and C, Haiku executes and checks, never Fable** (owner rules 11-14). Source line ranges are taken from `main` on 2026-11-15 and must be re-checked by the exact-diff pass.

Numbers: 1474-1480 are the SQLite briefs reserved in the plan; 1700-1790 are new Go briefs. Replaced: 1526 by 1707, 1545 by 1713, 1546 by 1710, 1553 by 1712. 1525, 1527, 1550, 1554, 1429, 1597, 1629, 1665-1667 stay as they are and are named in the dependencies.

## 3. Ordering and dependencies

Phase 0 (start now, no dependencies): 1790 (completeness gate, so every later brief shrinks a visible list), 1474 and 1475 (SQLite schema authority), 1750, 1775, 1780, 1781, 1773, 1706, 1700.
Phase 1 (chains, each starts after the previous merges and main is green): 1700 -> 1701 -> 1702 -> 1703 -> 1704 -> 1705 (property settings); 1706 -> 1707; 1770; 1775 -> 1776 (needs 1429); 1760 -> 1761 (login; 1761 also needs 1501-1510 waves).
Phase 2: 1730 -> 1731 -> 1732; 1733 -> 1734 -> 1735 -> 1737 (stays and host guest editing); 1751 dashboard after 1730; 1710, 1711 -> 1712 booking, then 1714 after 1713.
Phase 3 (HIGH RISK, owner sign-off per switch): 1740 -> 1742 (one week soak) -> 1741. Only after F2 has soaked: guest registration 1720 -> 1721 -> 1722 -> 1723 -> 1724 -> 1725 -> 1726 -> 1728 (1720 can be built earlier because 1713 needs its language port, but its path stays off).
Phase 4: 1771 (after 1707 and the TTLock acceptance test), 1772 (Block S, after 1770, 1771, 1773), 1782 (everything to Go), then 1479 (delete `App/` and the SQLite runtime).
SQLite side: 1474 and 1475 now; 1478 after 1474 and two Go-applied migrations; 1476 and 1477 after the section 6 proofs and the owner's cutover date; 1480 thirty days after 1476; 1479 last with 1782.
Parallel limit: the owner lifted the 3-thread cap (11-13). Rule that stays: two open briefs never name the same file in section 3; chains above are the file-conflict groups.

## 4. Waves still to run on the server (owner; briefs exist, no new text needed)

Already live: W1, W1b, W6, W7, W8 first set. Not yet: W2 exports (due one day after W1), W2b privacy (1615), W3 billing (rolled back on a Cloudflare 403 from the server, an infrastructure issue, not an app fault: the owner must fix the Cloudflare rule for `/admin/fakturace` before retrying), W4 customer admin (Cloudflare blocks admin curl: verify in a browser instead), W8b Havel and Leon (needs the AI budget variables for HAVEL and LEON), W9 invoices (1420-1427), W10 stay fees (1580-1589), wave 5 login (1761), then waves P, B, U, H, G of the new briefs. Also the open items from the memory notes: browser click-through of W1/W1b/W6/W7/W8, SES test M-P8, `/webhooks/stripe` out of the path list (1781), retention variables against P12.

## 5. All new briefs

### SQLite (S6-S14)

| # | Brief | Tier | Depends on |
|---|---|---|---|
| [1474](../tasks/1474-python-apply-goose-only.md) | SQLite retirement S6: Python's PostgreSQL schema apply uses the goose files only | A | 1472 and 1473 merged (done: reports exist), 1471 (00017), owner step S4 done (production schema dump diffed cl |
| [1475](../tasks/1475-go-migrate-init-empty.md) | SQLite retirement S7: `ubyhost-web migrate apply --init` builds an empty database | A | 1260-1263 (done), #982 merged, 1474 not required |
| [1476](../tasks/1476-end-sqlite-rollback-path.md) | SQLite retirement S11: remove the SQLite rollback scripts | A | S8 live (`UBYHOST_SCHEMA_APPLY=go`, done 2026-11-14), the section 6 proofs of the plan all recorded (brief 147 |
| [1477](../tasks/1477-docs-postgresql-only.md) | SQLite retirement S13: docs say PostgreSQL only | C | 1476 merged |
| [1478](../tasks/1478-delete-pg-schema-py.md) | SQLite retirement S9: delete `pg_schema.py` and Python's schema apply | B | 1474, S8 live and two goose migrations applied by Go on production (owner check) |
| [1479](../tasks/1479-delete-sqlite-runtime.md) | SQLite retirement S14 (lane X3): delete the SQLite runtime together with `App/` | B | Go brief 1782 (X2: Caddy sends everything to Go, `ubyhost` and `worker` leave compose) merged and one quiet we |
| [1480](../tasks/1480-sqlite-archive-delete-runbook.md) | SQLite retirement S12: owner runbook to archive and delete the SQLite file | C | 1476 merged plus 30 days (decision 5) |

### Property settings and smart locks (P)

| # | Brief | Tier | Depends on |
|---|---|---|---|
| [1700](../tasks/1700-go-apartment-new-create.md) | Go property settings 1: new property form, RUIAN suggest, create | B | 1525 layout gaps (done), 1527 not required; 1520-1524 on the branch |
| [1701](../tasks/1701-go-apartment-detail-page.md) | Go property settings 2: property detail page (GET /apartments/{id}) | B | 1700 |
| [1702](../tasks/1702-go-apartment-update-door-codes.md) | Go property settings 3: update property and door-code settings (POST) | A | 1701 |
| [1703](../tasks/1703-go-apartment-small-posts.md) | Go property settings 4: PIN, link, timing, archive, feeds, sync, police letter, codelists | B | 1702 |
| [1704](../tasks/1704-go-settings-menu-pages.md) | Go property settings 5: settings, menu, guest links, guide and housebook pages | B | 1380/1381 host layout (done) |
| [1705](../tasks/1705-go-property-settings-switch.md) | Go property settings 6: completeness test, path collisions, rollout wave P | B | 1700-1704 and 1525/1527 decisions |
| [1706](../tasks/1706-go-ttlock-client.md) | Go smart locks 1: TTLock client in Go | A | none (TTLock plan section 11/12 for live use) |
| [1707](../tasks/1707-go-smart-locks-routes.md) | Go smart locks 2: smart-locks page and actions (replaces blocked 1526) | A | 1706, 1704 |

### Booking and payments, guest side (B)

| # | Brief | Tier | Depends on |
|---|---|---|---|
| [1710](../tasks/1710-go-property-page-host.md) | Go booking 1: property page review and booking-site host pages | B | 1540-1544 (done), 1704 |
| [1711](../tasks/1711-go-stay-invoice-engine.md) | Go booking 2: stay-invoice engine (unblocks 1553) | A | 1544, 1220 |
| [1712](../tasks/1712-go-booking-cancel-pdfs.md) | Go booking 3: guest cancel and invoice PDFs (unblocks 1553) | A | 1711, 1544 |
| [1713](../tasks/1713-go-guest-pay-pages.md) | Go booking 4: guest /pay pages and payments consent (unblocks 1545) | B | 1720 (guest shell and language), 1540 |
| [1714](../tasks/1714-go-booking-rollout.md) | Go booking 5: completeness test, `/p/{slug}` collision, wave B (replaces 1550/1554 blocks) | A | 1710, 1712, 1713, 1541-1544 |

### Guest registration (G, moves last)

| # | Brief | Tier | Depends on |
|---|---|---|---|
| [1720](../tasks/1720-go-guest-shell-gate.md) | Go guest 1: guest shell, token gate, PIN, language, privacy notice | A | 1500-1510 session library, 1380 layout, countries/i18n packages |
| [1721](../tasks/1721-go-guest-stay-claim.md) | Go guest 2: stay overview, claim landing and confirm, demo preview | A | 1720 |
| [1722](../tasks/1722-go-guest-party-count.md) | Go guest 3: party size, head count, add another person | A | 1721 |
| [1723](../tasks/1723-go-guest-form-pages.md) | Go guest 4: guest form pages (new, edit, remove, language switch) | A | 1722 |
| [1724](../tasks/1724-go-guest-form-save.md) | Go guest 5: guest form save (POST /save) | A | 1723, validation package, 1171 skip rule, encryption `secure` |
| [1725](../tasks/1725-go-guest-draft-scan.md) | Go guest 6: draft autosave and document scan | A | 1724 |
| [1726](../tasks/1726-go-guest-leon-questions.md) | Go guest 7: guest Leon chat and host question pages | B | 1720, 1436 (Go Leon), 1629 |
| [1728](../tasks/1728-go-guest-completeness-wave.md) | Go guest 8: completeness test and rollout wave G | A | 1720-1726, 1629, F2 (1741) signed off |

### Stays and host guest editing (H)

| # | Brief | Tier | Depends on |
|---|---|---|---|
| [1730](../tasks/1730-go-submissions-reservations-read.md) | Go stays 1: submissions list/detail and stays list/detail | B | 1380/1381, 1720 not needed |
| [1731](../tasks/1731-go-reservation-edit-posts.md) | Go stays 2: create, update, quick-edit, remove slot, archive, demo delete | A | 1730 |
| [1732](../tasks/1732-go-claim-filed-by-hand.md) | Go stays 3: claim operations and 'filed by hand' | A | 1731, 1721 |
| [1733](../tasks/1733-go-host-guest-edit.md) | Go stays 4: host adds and edits guests | A | 1731, 1724 (shared field model) |
| [1734](../tasks/1734-go-guest-privacy-actions.md) | Go stays 5: restrict, verify identity, passport photo, reveal identity | A | 1733 |
| [1735](../tasks/1735-go-guest-archive-delete-resend.md) | Go stays 6: archive, unarchive, delete, resend guest link | A | 1734 |
| [1737](../tasks/1737-go-stays-completeness-wave.md) | Go stays 7: completeness test and rollout wave H (stays and host guest editing) | A | 1730-1735; submit routes belong to 1741 |

### Filing F1/F2 (F, owner sign-off per switch)

| # | Brief | Tier | Depends on |
|---|---|---|---|
| [1740](../tasks/1740-go-filing-f1-send-endpoint.md) | Go filing F1: Go endpoint 'send this stay now' (Python calls it) | A | go/internal/ubyport (client, collect, effects: done), 1171, 1159 watchdog; owner sign-off K-F03/K-F07 |
| [1741](../tasks/1741-go-filing-f2-buttons.md) | Go filing F2: host send and re-file buttons on Go | A | 1740 soaked a week, 1732 |
| [1742](../tasks/1742-go-filing-soak-check.md) | Go filing: soak check script and one-week comparison | B | 1740, 1741 |

### Dashboard and utility routes (D)

| # | Brief | Tier | Depends on |
|---|---|---|---|
| [1750](../tasks/1750-go-main-utility-routes.md) | Go misc 1: robots, sitemap, manifest, service worker, offline, favicon, language, tdmrep | B | none |
| [1751](../tasks/1751-go-dashboard.md) | Go misc 2: dashboard (GET /) | A | 1730 (stays data), 1750, 1380/1381 |

### Login and accounts (L)

| # | Brief | Tier | Depends on |
|---|---|---|---|
| [1760](../tasks/1760-go-passkeys.md) | Go login 1: passkeys (go-webauthn) | A | 1501, owner decision on library (go-webauthn v0.18.0 on Go 1.25, decision line in `docs/context/decisions.md`) |
| [1761](../tasks/1761-go-login-waves.md) | Go login 2: waves 5a-5f owner checklist and completeness test | A | 1501-1510, 1760, 1632 |

### Invoices (I)

| # | Brief | Tier | Depends on |
|---|---|---|---|
| [1775](../tasks/1775-go-invoice-mail-builder.md) | Go invoices 1: invoice mail builder (unblocks 1429) | B | 1420-1427, 1231 |
| [1776](../tasks/1776-go-invoice-detail-send-wave.md) | Go invoices 2: detail page, send, and wave 9 completion | B | 1775, 1429, 1427 |

### Jobs and scheduler (J)

| # | Brief | Tier | Depends on |
|---|---|---|---|
| [1770](../tasks/1770-go-mail-job.md) | Go jobs 1: register the `mail` job kind | B | 1231, 1231b, 1231c (outbox drain, done), 1632 SES keys |
| [1771](../tasks/1771-go-door-codes-job.md) | Go jobs 2: port the `door_codes` job (and cleaning codes) | A | 1706, 1707, 1573, TTLock live acceptance |
| [1772](../tasks/1772-go-scheduler-switch.md) | Go jobs 3: Block S, Go enqueues every job kind (Python worker stops) | A | 1450-1452 (done), 1770, 1771, J-jobs for retention and stay_fee_mail decided |
| [1773](../tasks/1773-go-jobs-retention-staymail-enable.md) | Go jobs 4: enable `retention` and `stay_fee_mail` (owner checklist) | C | three matching retention dry-run mornings, stay-fee wave 10 steps 1-3 |

### Retire Python and gate (X)

| # | Brief | Tier | Depends on |
|---|---|---|---|
| [1780](../tasks/1780-go-ops-scripts-subcommands.md) | Go retire 1 (X1): ops scripts as `ubyhost-web` subcommands | B | none |
| [1781](../tasks/1781-stripe-webhook-path-decision.md) | Go retire 2: `/webhooks/stripe` stays off `UBYHOST_GO_PATHS` (runbook fix) | C | 1350, 1554 |
| [1782](../tasks/1782-go-caddy-everything-to-go.md) | Go retire 3 (X2): Caddy sends everything to Go; `ubyhost` and `worker` leave compose | A | every wave done, 1772, one quiet week |
| [1790](../tasks/1790-route-completeness-gate.md) | Go gate: CI test that every Python route has a Go handler | B | none (do this first) |


## 6. Owner decisions these briefs need

1. SQLite: the cutover date for ending the rollback path (decision 3 of the plan). Without it 1476 cannot merge.
2. Passkey library: go-webauthn (needs a line in `docs/context/decisions.md`) for 1760.
3. Filing: lawyer items K-F03 and K-F07 closed before 1740 goes live; sign-off for each of the F1 and F2 switches.
4. `/dev/ui` is not ported (development page): confirm it may die with Python (1750).
5. Whether the 30-day window before `App/` is deleted (1479) is acceptable; the plan says keep the last Python image and the offline SQLite copy for 30 days.

## 7. Not verified

Line ranges and function names come from reading `main` on 2026-11-15; the Go side of 1700-1704 (what 1300/1520-1524 already registered) was not diffed and is the first job of each exact-diff pass. The live value of `UBYHOST_GO_PATHS` is not in the repo (55 entries per the executor). Nothing was run: no tests, no builds.
