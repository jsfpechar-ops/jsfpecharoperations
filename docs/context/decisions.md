# Decisions

Append-only.

- 2026-10-06 | UbyPort: 0-2 accepted, 4-6 not; 112 = late = accepted | police A1-A5 | OPERATIONS
- 2026-10-06 | Sweep: one send per refused record, then host fix | police B2-B3 | OPERATIONS
- 2026-10-06 | Staging may use the police test env; creds only in staging | police B4 | LIGHTSAIL
- 2026-10-06 | Abbreviation check accepts 5-6 alphanumeric characters | police test abbreviation | validation.py
- 2026-10-08 | Door codes (TTLock pilot): timed codes, test mode until live | owner + council-lite | [ttlock-door-codes](../plans/ttlock-door-codes.md)
- 2026-10-08 | Funnel: in-app dashboard, no JS; Umami public-only | own rows | 0018
- 2026-10-08 | Stored files: no expiry; invoices 10 y; new file kind brings a storage module | legal risk | [plan](../plans/file-retention.md)
- 2026-10-08 | Door codes: one 1-min job; no PIN/list/unlock polling; weekly `queryDate` | API budget; type-3 unknown until use | [plan §7](../plans/ttlock-door-codes.md)
- 2026-10-08 | Invoices per stay only, replaces 09-26 | scope | [plan](../plans/stay-only-invoices.md)
- 2026-10-08 | Staging: `UBYHOST_STAGING_NO_LOGIN=1` skips login; door-code alert after 10 min | test-only | [ENVIRONMENT](../ENVIRONMENT.md)
- 2026-10-09 | [workflow] One brief per copy text; replaced brief marked in commit; executors skip non-todo; lint warns on overlap | brief collisions | [workflow](workflow.md)
- 2026-10-09 | Waiting guest sees only "You will receive your door code by e-mail." (0024; replaces 0022) | [0022](../tasks/0022-guest-door-code-waiting-messages.md)
- 2026-10-09 | [workflow] Status `replaced`: newer brief took over | `blocked` reads as waiting
- 2026-10-10 | UI decisions continue | cap | [UI](ui-decisions.md)
- 2026-10-09 | #331: no ID-check step (host checks ID); guest link default 1 day ahead | K-F12
- 2026-10-10 | PostHog replaces Umami; privacy settings in the snippet | owner | [plan](../plans/posthog-analytics.md), [0039](../tasks/0039-posthog-hardening.md)
- 2026-10-10 | Taken type-3 period: worker `add`, host warned; no shift, reuse or `change`; deleted untyped code is dead | staging | [0037](../tasks/0037-door-code-taken-period.md)
- 2026-10-11 | ARES lookup on host click; sends only the IČO; requests lib; 24 h cache; 20/h per user | owner | [0055](../tasks/0055-ares-lookup.md)
- 2026-10-11 | Facility abbreviation: suffix after UBY-WS_ | owner | [0043](../tasks/0043-police-setup-fewer-fields.md)
- 2026-10-11 | Web-service credential request: data box ybndqw9, Ředitelství služby cizinecké policie | owner | [0044](../tasks/0044-ws-request-letter.md)
- 2026-10-12 | TTLock: -1026 = created/deleted; host provider, no SCCs; same-period reuse needs custom PIN/mail; retry deletion to end (0067–69) | [legal](../privacy/DOOR_CODES_LEGAL.md)
- 2026-10-12 | Host UX: [UI](ui-decisions.md), 0087–0094 | owner; staging first
- 2026-10-15 | Watchdog digest every 72 h (server 10-15, repo 10-20) | owner | [OPERATIONS](../OPERATIONS.md)
- 2026-10-16 | #397: white workspace; Property hours; fractional stays; Dashboard stays only; Cleaning day markers; in-page creation | owner | PR #397
- 2026-10-17 | [workflow] Haiku 5.5 only executor; 100k cap per chat; scoped tests, no audits unless asked | owner | [workflow](workflow.md#when-haiku-reaches-the-cap)
- 2026-10-19 | Design v2: MASTER.md is the only host design source; Lucide inline SVG; CI lint blocks raw colours, inline styles, page CSS | owner | [plan](../plans/design-v2.md)

- 2026-10-19 [workflow] `test_static_versions.py --write` refuses a changed file under an old `?v=` key (0172).
- 2026-10-19 Accessibility: WCAG 2.2 AA, `a11y_guard.js`; no statement page (owner).

- 2026-10-22 [deps] Signature font: self-hosted Dancing Script (OFL) (owner).
- 2026-10-24 | [deps] `anthropic` 2.3.0 pinned+hashed; model `claude-haiku-5-5`; calls via `App/app/ai.py` (per-feature switch) | Havel and guest assistant; one module swaps providers | plan havel-support-assistant, 0310
- 2026-10-25 | Invoice "Fill from register" also asks MFČR VAT register (CRPDPH SOAP); DIČ digits only; 24 h cache; no dependency | owner | [0394](../tasks/0394-vat-register-bank-account.md)
- 2026-10-26 | Billing phase 1: invoices only, no gateway yet | owner | 0411
- 2026-10-26 | Unpaid = read-only, filing never blocked | owner | 0415
- 2026-10-27 | [Max policy](../reports/max-159-fivefold-ai.md); [original layout, 229 monthly](../reports/original-pricing-229.md) | owner
- 2026-10-27 | Direct payments folded into FastAPI; requests first, page booking second; QR rail = tech provider only | owner | plan direct-payments-build-plan, 0425
- Grafana Cloud (EU free tier) is subprocessor for ops logs and metrics (PII-free, OPS-3); monitoring behind compose profile "monitoring" (owner, 2026-10-27).
- 2026-10-28 | [deps] `stripe` 16.0.1 pinned+hashed in requirements.lock (owner); calls via `App/app/stripe_connect.py`; shared monthly cap `UBYHOST_STRIPE_MONTHLY_API_CALLS` | 0428
- 2026-10-28 | Property pages: Apify scrape-first prefill (page + Leon guide, 1 fetch), deterministic, no AI step; host reviews once | owner | plan property-pages, 0431
- 2026-10-28 | Property page: Airbnb-style layout patterns (hero grid, 65ch description, icon amenities); no Airbnb brand assets or CSS | owner | plan property-pages, 0431
- 2026-10-28 | Page photos: download + re-host from the import run (max 10, EXIF stripped), never hotlink; host confirms rights | owner | plan property-pages, 0432
- 2026-10-28 | Booking widget: Airbnb-style on our calendar/fee logic, no-JS, Stripe checkout on host account | owner | plan property-pages, 0434
- 2026-10-28 | Listing pages English-only; no per-listing or per-language translation (OTA copy verbatim) | owner | plan property-pages, 0431/0433
- 2026-11-02 | OCR: Tesseract only, local, MRZ check digits, Max only; band crop; Paddle if ocr_readrate <90% | owner | test_doc_ocr
- 2026-10-29 | Trials are extendable by the operator, 1-365 days | owner | 0448
- 2026-10-29 | Stripe Accounts v2; responsibilities immutable; company hosts via business_type | owner | 0437
- 2026-10-29 | Connect: full Stripe Dashboard + collectors (Express+Stripe preview-only; Express with application liability rejected) | owner | 0439

- 2026-10-30 | [workflow/db/deps] PostgreSQL kit, psycopg3 + pgBackRest approved; Haiku-only execution; manual cutover | 0455–0456
- 2026-10-31 | Postgres (#592), then Go G1-G6, per-feature rollback, no load test. [workflow] Haiku implements | owner | [plan v4](../plans/postgresql/migration-plan-v4.md)
- 2026-10-31 | Every change lean: no dead code or extras; dead code goes in its own small commit | owner | plan v4
- 2026-10-31 | Postgres/Go: approval gates waived, bar stays (backup, rehearsal, hashes, both-DB suite, auto rollback). D1 self-hosted Postgres in Compose (socket, 1 GB cap); nightly `pg_dump`; D2 reviewer on `production`; D3 goose; D4 job table, `SKIP LOCKED`. No password, no network (`network_mode: none`, socket volume). [workflow] Pre-merge: `git diff --stat origin/main <branch>` vs brief Files; one worktree per Haiku | owner, orchestrator | 0463, 0464, #606
- 2026-10-31 | [workflow] `test-postgres-full` (app suite on PG 17) gates every merge; SQLite-file tests carry `sqlite_only` | orchestrator | 0462
- 2026-11-01 | Host redesign: vendored Hotwire Turbo (MIT) for page-body swaps; owner OKs mockups first | owner | #614
- 2026-10-31 | D3 detail: goose v3.29.0, asset goose_linux_x86_64 (SHA-256 pinned) | owner | 0465b
- 2026-11-01 | Go: module go/, stdlib, pgx v5, go-ntlmssp v0.1.1, go-qrcode (11-02) | owner (waiver) | 0474, 0481, 0684
- 2026-11-02 | [workflow] Read hook: 350+ lines needs a limit | owner | 0810
- 2026-11-02 | Signup box: unticked marketing opt-in; lawyer to confirm | owner | 0836
- 2026-11-02 | Address autofill from RÚIAN, server-side | owner | 0884
- 2026-11-03 | Try it rehearsal: optional page, Skip and Leave | owner | 0884
- 2026-11-02 | Booking site: CS/EN, one HMAC link per booking, cancel refunds per policy | owner | 0818-0821

- 2026-11-03 | [workflow] UX gate: threads self-check UX (lint + screenshots) | owner | 0900
- 2026-11-03 | Booking terms: own text modeled on marketplace guest terms (structure only), CS+EN, /terms/booking, versioned | owner | 0900
- 2026-11-03 | Partial site refund issues a credit note / corrective document for the refunded amount; full refund keeps storno | owner | 0901

- [filing] 2026-11-04: unanswered filings retry 30m/2h/6h/12h, duplicate answer stops; supersedes OD-1 and WP31 (0909). After the 5th attempt: host and support mail and push, once per chain.
- 2026-11-04 | Stay fee pay v4 (Stripe v2) | owner | [plan](../plans/stay-fee-guest-payment.md)
- 2026-11-04 | [workflow] Sonnet writes briefs, Haiku executes | owner | [workflow](workflow.md)
