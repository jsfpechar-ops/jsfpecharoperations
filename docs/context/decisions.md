# Decisions

Append-only.

- 2026-10-06 | UbyPort: 0-2 accepted, 4-6 not; 112 = late = accepted | police A1-A5 | OPERATIONS
- 2026-10-06 | Sweep: one send per refused record, then host fix | police B2-B3 | OPERATIONS
- 2026-10-06 | Staging may use the police test env; creds only in staging | police B4 | LIGHTSAIL
- 2026-10-06 | Abbreviation check accepts 5-6 alphanumeric characters | police test abbreviation | validation.py
- 2026-10-08 | Door codes (TTLock pilot): timed codes, test mode until live; full rules in the plan | owner + council-lite | [ttlock-door-codes](../plans/ttlock-door-codes.md)
- 2026-10-08 | Funnel: in-app dashboard, no JS; Umami public-only | own rows | 0018
- 2026-10-08 | Stored files: no expiry; invoices 10 y; first new file kind brings a storage module | tiny saving, legal risk | [plan](../plans/file-retention.md)
- 2026-10-08 | Door codes: one 1-min job; no PIN/list/unlock polling; weekly `queryDate` | API budget; type-3 unknown until use | [plan §7](../plans/ttlock-door-codes.md)
- 2026-10-08 | Invoices per stay only, replaces 09-26 | scope | [plan](../plans/stay-only-invoices.md)
- 2026-10-08 | Staging: `UBYHOST_STAGING_NO_LOGIN=1` skips login; door-code alert after 10 min | test-only | [ENVIRONMENT](../ENVIRONMENT.md)
- 2026-10-09 | [workflow] One brief per copy text; replaced brief marked in the same commit; executors skip non-todo; lint warns on brief overlap | brief collisions | [workflow](workflow.md)
- 2026-10-09 | Waiting guest sees only "You will receive your door code by e-mail." (0024; replaces 0022) | [0022](../tasks/0022-guest-door-code-waiting-messages.md)
- 2026-10-09 | [workflow] Status `replaced`: a newer brief took over | `blocked` reads as waiting
- 2026-10-10 | UI decisions continue | cap | [UI](ui-decisions.md)
- 2026-10-09 | #331: no ID-check step (host checks ID); guest link default 1 day ahead | K-F12
- 2026-10-10 | PostHog replaces Umami; privacy settings in the snippet | owner | [plan](../plans/posthog-analytics.md), [0039](../tasks/0039-posthog-hardening.md)
- 2026-10-10 | Taken type-3 period: worker `add`, host warned; no shift, reuse or `change`; deleted untyped code is dead (lock test) | staging | [0037](../tasks/0037-door-code-taken-period.md)
- 2026-10-11 | ARES lookup on host click; sends only the IČO; requests lib; 24 h cache; 20/h per user | owner | [0055](../tasks/0055-ares-lookup.md)
- 2026-10-11 | Facility abbreviation: suffix after UBY-WS_ | owner | [0043](../tasks/0043-police-setup-fewer-fields.md)
- 2026-10-11 | Web-service credential request: data box ybndqw9, Ředitelství služby cizinecké policie, Praha 3 | owner | [0044](../tasks/0044-ws-request-letter.md)
- 2026-10-12 | TTLock: -1026 = created/deleted; host provider, no SCCs; same-period reuse needs custom PIN/mail; retry deletion to end (0067–69) | [legal](../privacy/DOOR_CODES_LEGAL.md)
- 2026-10-12 | Host UX: [UI](ui-decisions.md), 0087–0094 | owner; staging first
- 2026-10-15 | Watchdog digest every 72 h (server 10-15, repo 10-20) | owner | [OPERATIONS](../OPERATIONS.md)
- 2026-10-16 | #397: white workspace; Property hours; fractional stays; Dashboard stays only; Cleaning day markers; in-page creation | owner | PR #397
- 2026-10-17 | [workflow] Haiku 5.5 only executor; 100k cap per chat; scoped tests, no audits unless asked | owner | [workflow](workflow.md#when-haiku-reaches-the-cap)
- 2026-10-19 | Design reset v2: MASTER.md is the only host design source; Lucide inline SVG icons; CI lint blocks raw colours, inline styles, page CSS | owner | [plan](../plans/design-v2.md)

- 2026-10-19 [workflow] `test_static_versions.py --write` refuses a changed file under an old `?v=` key (0172).
- 2026-10-19 Accessibility: WCAG 2.2 AA, `a11y_guard.js`; no statement page (owner).

- 2026-10-22 [deps] Signature font: self-hosted Dancing Script (OFL) (owner).
- 2026-10-24 | [deps] `anthropic` 2.3.0 pinned+hashed; model `claude-haiku-5-5`; every call through `App/app/ai.py`, per-feature switch and budget | Havel + guest assistant; one module to swap providers | plan havel-support-assistant, task 0310
- 2026-10-25 | Invoice "Fill from register" also asks the MFČR VAT register (CRPDPH SOAP); sends DIČ digits only; 24 h cache; no new dependency | owner | [0394](../tasks/0394-vat-register-bank-account.md)
- 2026-10-26 | Billing phase 1: invoices only, no gateway yet | owner | 0411
- 2026-10-26 | Unpaid = read-only, filing never blocked | owner | 0415
- 2026-10-27 | [Max policy](../reports/max-159-fivefold-ai.md); [original layout, 229 monthly](../reports/original-pricing-229.md) | owner
- 2026-10-27 | Direct payments folded into the FastAPI app; requests first, page booking second; QR rail = tech provider only | owner | plan direct-payments-build-plan, 0425
- Grafana Cloud free tier (EU) is the subprocessor for operational logs and metrics (PII-free per OPS-3); monitoring containers behind compose profile "monitoring" (owner, 2026-10-27).
- 2026-10-28 | [deps] `stripe` 16.0.1 pinned+hashed in requirements.lock (owner); every call through `App/app/stripe_connect.py`, shared monthly cap `UBYHOST_STRIPE_MONTHLY_API_CALLS` | 0428
- 2026-10-28 | Property pages: Apify scrape-first prefill (page + Leon guide, one fetch), page pipeline deterministic, no AI step; host reviews once, then publish | owner | plan property-pages, 0431
- 2026-10-28 | Property page design: Airbnb-style layout patterns (hero grid, 65ch description, icon amenities); no Airbnb brand assets, fonts or copied CSS | owner | plan property-pages, 0431
- 2026-10-28 | Page photos: download + re-host from the host's own import run (max 10, EXIF stripped), never hotlink; host confirms rights at review | owner | plan property-pages, 0432
- 2026-10-28 | Booking widget: Airbnb-style interaction built from our own calendar/fee logic, no-JS form, Stripe checkout on the host account; no dark patterns, no tracking | owner | plan property-pages, 0434
- 2026-10-28 | Listing pages are English-only; no per-listing translation, no per-language variants (OTA copy verbatim) | owner | plan property-pages, 0431/0433
- 2026-10-29 | OCR: local Tesseract in the image (no AI, photo stays on the server), MRZ check digits required, prefill only, Max plan only, guest tickbox | owner | test_doc_ocr
- 2026-10-29 | Trials are extendable by the operator, 1-365 days | owner | 0448
- 2026-10-29 | Stripe Accounts v2; responsibilities immutable; company hosts via business_type | owner | 0437
- 2026-10-29 | Connect accounts: full Stripe Dashboard + Stripe collectors (Express+Stripe is preview-only; Express pairs with application liability, rejected) | owner | 0439

- 2026-10-30 | [workflow/db/deps] PostgreSQL kit, psycopg3 + pgBackRest approved; Haiku-only execution; manual cutover | 0455–0456
- 2026-10-31 | Postgres now (#592), Go port G1–G6 now after cutover + tenancy, per-feature rollback, no load-test gate. `ws_uby_test` and golden files dropped; XML snapshot test before G5. [workflow] Fable briefs critical items, Haiku implements | owner | [plan v4](../plans/postgresql/migration-plan-v4.md)
- 2026-10-31 | Every change lean: no dead code, no extras; dead code found on the way is removed in its own small commit or PR | owner | plan v4
- 2026-10-31 | Approval gates waived for the whole PostgreSQL and Go migration; the bar stays (verified backup, rehearsal on a production copy, per-table counts and hashes, suite green on PG, SQLite as rollback, automatic rollback). Owner acts only where his hands are needed | owner | 0463
- 2026-10-31 | D2 required reviewer on `production`; D3 goose (step 10); D4 Postgres job table with `SKIP LOCKED`. D1: PostgreSQL self-hosted as a Compose service on the current 8 GB Lightsail server (socket, no port, 1 GB cap), not managed; nightly encrypted `pg_dump` in the existing backup, restore proven at every rehearsal; no pgBackRest | owner | 0463, 0464
- 2026-10-31 | PostgreSQL container has no password and no network (`network_mode: none`, Unix socket volume, trust auth). A Haiku commit from a stale worktree reverted main (#601, fixed in #606). [workflow] Before every merge: `git diff --stat origin/main <branch>` against the brief's Files; one fresh worktree per Haiku | owner, orchestrator | 0463, #606
- 2026-10-31 | [workflow] `test-postgres-full` (app suite on PG 17) gates every merge; SQLite-file tests carry `sqlite_only` | orchestrator | 0462
- 2026-11-01 | Host redesign: add vendored Hotwire Turbo (MIT, ~25 KB) for page-body swaps; redesign needs owner OK of mockups before build or merge | owner | #614
- 2026-10-31 | D3 detail: goose v3.29.0, asset goose_linux_x86_64, SHA-256 cc56e2f75532a4dd52f5ef2d31db0121e91079a9c2617bc0ad4e04e2d41c228b | owner | 0465b
- 2026-11-01 | Go: module go/, stdlib, pgx v5, go-ntlmssp v0.1.1; crypto via Python fixtures | owner (waiver) | 0474, 0481
