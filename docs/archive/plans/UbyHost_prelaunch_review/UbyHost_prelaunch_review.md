# UbyHost pre-launch review and Cursor plan

Repo: github.com/jsfpechar-ops/jsfpecharoperations, `main` at 7372d34 (fetched 2 October 2026). Your local copy was not changed.

Everything below was read in the code or reproduced in a sandbox, except items marked [ASSUMPTION].

The plan in Part 3 was checked end to end in the sandbox:

- applied mechanically, task by task, to a fresh checkout of `main`;
- every Find block matched exactly once at the point it is applied;
- the result is byte-identical to the reference branch;
- the full suite passes on the final result (about 2,170 tests, browser tests included, 0 failures). It also passed at the end of each phase before the review round; after that round only the final state was re-run;
- the guest browser e2e passes with 0 skipped;
- three files fail when run alone on `main` too (test_host_i18n, test_mail_failed_alert, test_notification_copy need an earlier test to create the tables). This is not caused by the plan; run the suite in one process.
- the CI lint passes.

Severity:

- BLOCKER: do not launch.
- HIGH: wrong legal or financial output, or data loss.
- MEDIUM: a real defect with a workaround.
- LOW: polish or hardening.

No BLOCKER was found. "Open" means the item is not in this plan, because it is safe to do after launch. Your answers to the owner questions are recorded at the end and are in the plan.

## Part 1. Audit

### Correctness: stay fee and invoices

| ID | File, location | Problem | Sev | Fix | Plan |
|---|---|---|---|---|---|
| A01 | App/app/stay_fee.py `hlaseni()`, exempt bucket loop | A guest who turns 18 during the period is "liable" overall but still has exempt minor nights. Those nights went to no bucket, so `validate()` raised and the period could never be finalized (reproduced). | HIGH | Bucket on `exempt_nights`. Treat liable lines with exempt nights as minors. | T01, T02 |
| A02 | App/app/routes/stay_fees.py finalize; stay_fee_detail.html hidden `rate_czk` | The stored rate came from a form field and could differ from the rate used for the total. | MEDIUM | Use `period["rate_czk"]` and remove the hidden field. | T03, T04 |
| A03 | App/app/stay_fee.py `property_period` (`rate = int(apartment["stay_fee_rate_czk"])`); routes/stay_fees.py correction path | Correcting a sealed period recalculates it at today's rate. After a 1 January rate change, a correction gives the wrong amount owed. | HIGH | Decision Q1: a correction uses the rate stored with the sealed period. | T31, T32, T33, T34 |
| A04 | App/app/invoice_pdf.py (one page, no page break); invoices.py no item cap | Long invoices overflow into the footer and the QR code goes off the page. Issued PDFs are immutable. The limit was measured: payer + unpaid + QR overflows at 5 two-line items. | HIGH | Cap at 4 items with a clear validation message. Pagination is the alternative (Q2). | T07, T08, T09 (decision Q2: keep the cap) |
| A05 | App/app/invoices.py `_to_decimal`, `_items_from_form` | "1.000,50" silently became 0. "NaN", "Infinity" and "1e30" gave a 500. | MEDIUM | Parse Czech thousands. A typed price that is not a finite number, or is over 10,000,000, blocks issuing with the amount error instead of becoming 0 Kč. | T07, T09 |
| A06 | App/app/invoices.py `build_draft` captures `note`; no column, not printed | The invoice note field is accepted and then thrown away. | MEDIUM | Decision Q3: store the note, print it, keep it immutable once issued. An invoice that would no longer fit one page is refused at issue with a clear message. | T35 to T41 |
| A07 | App/app/routes/invoices.py issue route | No idempotency. A double submit issues two consecutive numbers, which can only be cancelled by storno. | MEDIUM | One-time form nonce, or put the existing submit guard on this form. | Open |
| A08 | App/app/stay_fee.py `_day_liability` with decision "charge" | For a real minor, "charge" changes nothing but files the minor under host exemptions with a blank reason. | LOW | Keep `auto_minor` for minors whatever the decision, or fix the docstring. | Open |
| A09 | App/app/templates/stay_fees.html | Saved and unsaved periods both showed "Ready". | LOW | Status per row: attention / ready / saved. | T81, T90 |
| A10 | App/app/invoices.py `cancel`; invoice_detail.html | A concurrent cancel hits IntegrityError and returns a 500. The cancel form is still shown after a cancellation. | LOW | Catch IntegrityError; hide the form when a correction exists. | Open |
| A11 | App/app/invoices.py `duzp`, `due_date`, `correction_date` | Dates are not validated. Text that is not a date gives a 500 in `cz_date`. | LOW | Validate with `parse_iso_date`. | Open |
| A12 | App/app/routes/invoices.py next-number year; templating `today()` | Uses the server date rather than the Prague date. This is wrong around midnight on 1 January. | LOW | Use `claim.prague_today()`. | Open |
| A13 | App/app/invoice_pdf.py unit price `base_haler // qty` | The PDF floors the unit price while the web page rounds half-up, so they can differ by 1 haléř. | LOW | Use the same rounding. | Open |
| A14 | App/app/stay_fee.py `parse_month` | `?month=0001-01` returned a 500 on /invoices and /stay-fees. | LOW | Reject years before 2000. | T92, T82 |
| A15 | App/app/routes/stay_fees.py adjustments | Adjustments are keyed by the current cadence, so a cadence switch orphans them. | LOW | Use the sealed cadence when correcting. | Open |
| A76 | App/app/invoice_pdf.py VAT recap | For a VAT payer the recap amounts ran into their labels ("12 %Základ"). Found while testing the note. | LOW | Right-align the amounts at fixed columns. | T37 |

### Correctness and reliability: calendars and police filing

| ID | File, location | Problem | Sev | Fix | Plan |
|---|---|---|---|---|---|
| A16 | App/app/reporting.py `submit_batch` | A batch that dies mid-send (restart, OOM, crash after the insert) stays `running` forever. Its guests stay pending and are sent again, and the first receipt is lost. HIGH RISK (filing). | HIGH | Before each send, a `running` batch with no live send claim becomes `outcome_unknown`, its guests are linked to it, and the critical alert is raised. This runs under BEGIN IMMEDIATE and is judged by the claim, not the row age, so a lapsed claim cannot let the batch be sent twice. Nothing is resent automatically. | T13, T14 |
| A17 | App/app/icalsync.py both cancellation paths | A stay whose guests already filled in forms but are not yet sent is cancelled silently, so nothing is ever filed for them. HIGH RISK (filing). | HIGH | Raise a `cancelled_with_guests` warning when guests still need filing (Czech nationals and guests already sent do not count). Setting the stay back to Active clears it. Cancellation behaviour is unchanged (alert only). | T16, T17, T26, T27 |
| A18 | App/app/retention.py `_delete_workspace` | The apartment delete failed on foreign keys after the guests were already gone. The account, entities, audit rows and stay-fee filings survived, and the job failed every night. So on `main` no terminated workspace was ever fully deleted. Queued mail with guest addresses was never deleted. HIGH RISK (retention). | HIGH | One transaction in foreign-key order, covering stay-fee filings, adjustments, invoices, sequences and queued mail. Guest IDs are read inside the lock. Photos are deleted after commit; a failing photo is logged, not fatal. Needs Q9 before merging. | T11, T12; decision Q9 notices: T59 to T66 |
| A19 | App/app/icalsync.py suspect threshold | With one future booking that disappears, the feed is "suspect" forever and the stay is never cancelled. | MEDIUM | Apply the threshold only to 3 or more candidates. HIGH RISK (filing), so it is not in this plan. | Open |
| A20 | App/app/feed_fetch.py decode | A `text/*` response without a charset was decoded as Latin-1, garbling UTF-8 names. A BOM was never stripped, so the parser failed. | MEDIUM | Use the explicit charset, else UTF-8. Always strip a leading BOM. | T18, T29 |
| A21 | App/app/feed_fetch.py | No total time limit, so a trickling server can hold the sync. | MEDIUM | 60 s deadline in the read loop. | T18 |
| A22 | App/app/icalsync.py insert | The same booking in two feeds becomes two stays, one of them overdue forever. | MEDIUM | `possible_duplicate_stay` alert on identical dates from another feed. | Open |
| A23 | App/app/icalsync.py; routes/admin.py sync | A manual sync and the scheduled sync can clash on the UNIQUE constraint, and the losing feed is marked `error`. | MEDIUM | Per-feed lock, or catch IntegrityError. | Open |
| A24 | App/app/icalsync.py date move UPDATE | Ignores `submission_claim`, so it can move a guest who is on the wire. HIGH RISK (filing). | LOW | Add `NOT EXISTS (… submission_claim …)`. | Open |
| A25 | App/app/routes/guest.py, `dates_changed_resign` resolve | After a date move that keeps the old signed window inside the new booking (for example an extension), one guest's save lifts the "re-sign" hold for the whole party. Stale signatures still block filing on their own, so the gap is narrow. HIGH RISK (filing). | LOW | Decision Q6: the alert records each earlier signer; the hold lifts only when every one of them has signed again. | T48, T49, T50 |
| A26 | App/app/reporting.py `submit_stay_if_complete` | Immediate mode ignored the refused-login pause, so it kept retrying a login UbyPort had refused (account lockout risk). HIGH RISK (filing). | MEDIUM | Return early while `ubyport_auth_failed` is open. | T15 |
| A27 | App/app/validation.py `country_codes()` | The bundled list has no Kosovo. Police codes that are not bundled are offered and then rejected. [ASSUMPTION on the police code] | MEDIUM | Decision Q7: add Kosovo as XKX. Merging the cached police list into the valid codes stays open. [ASSUMPTION: UbyPort accepts XKX; check its country list once the connection works] | T57, T58 (Kosovo only) |
| A28 | App/app/ubyport/client.py, non-401 4xx | Retried every 10 minutes with no limit. | LOW | Count these against `submit_attempts`. | Open |
| A29 | App/app/ubyport/client.py header rejection | A rejected header with no per-record list is reported as "outcome unknown". [ASSUMPTION on service behaviour] | LOW | Map it to per-record rejection. | Open |
| A30 | App/app/reporting.py claim TTL | The lease can expire across several slow batches. | LOW | Refresh `claimed_at` per batch. | Open |
| A31 | App/app/icalsync.py event dates | DTEND on or before DTSTART is stored, and those guests can never validate. | LOW | Force at least one night. | Open |
| A32 | App/app/deadlines.py | The countdown is 1 h off across a DST switch. The send cutoff itself is correct. | LOW | Use aware datetimes. | Open |
| A33 | App/app/validation.py birth date | An ISO autofill value (1990-05-12) is rejected. | LOW | Accept YYYY-MM-DD. | Open |
| A34 | App/app/routes/admin.py calendar delete | The deleted calendar's future stays stay active and keep alerting. | LOW | Cancel future stays without guests. | Open |
| A35 | App/app/housebook.py purge `IN (…)` | Can exceed the SQLite variable limit on a large first purge. [ASSUMPTION: older SQLite] | LOW | Chunk the deletes. | Open |
| A36 | App/app/routes/admin.py manual send | Only `results[0]` is inspected, so a failure in a later batch is hidden. | LOW | Report the worst result. | Open |

### Security and privacy

| ID | File, location | Problem | Sev | Fix | Plan |
|---|---|---|---|---|---|
| A37 | App/app/dsr.py `guest_export` | The guest's data export matched audit rows by `LIKE %guest_id=N%` across all workspaces, so `guest_id=1` also matched 12, 100 and so on, and other tenants' rows leaked. It also missed the guest's own rows logged as `id=N` and `guest=N`. | MEDIUM | Scope to the owner and match all three formats exactly. | T06, T28 |
| A38 | App/app/routes/admin_accounts.py `logout` | Logout clears only the cookie. A copied cookie stays valid for 12 h, or 30 days with "remember me". | MEDIUM | Decision Q4: Log out bumps `session_version`, so every device is signed out. | T42, T43, T44 |
| A39 | App/app/stay_fee.py `register_csv` | The register CSV wrote guest-typed text raw, so formula injection was possible. The other exports already escape. | MEDIUM | `csv_safe` on every cell. | T05 |
| A40 | App/app/rate_limit.py, routes/guest.py PIN | Anyone with a guest link can lock that link for 24 h for every guest by sending wrong PINs. | MEDIUM | Decision Q5: with Turnstile configured, a locked link asks for the challenge instead of refusing. Without Turnstile the 24 h lock stays. | T45, T46, T47 |
| A41 | App/app/reporting.py `request_xml` | The police envelope, with passport numbers, is stored unencrypted for 90 days. | LOW | Encrypt the field. | Open |
| A42 | App/app/main.py CSP | `script-src 'unsafe-inline'` weakens the XSS backstop. | LOW | Move the inline scripts to files, or use nonces. | Open |
| A43 | App/app/main.py header vs guest/base.html meta | Guest pages set `no-referrer` only through a meta tag. The HTTP header is `strict-origin-when-cross-origin`. No leak today. | LOW | Also send the header for `/l/` paths. | Open |
| A44 | App/app/rate_limit.py login | No per-account lockout across many addresses. 2FA and Turnstile soften this. | LOW | Add an account-level limit. | Open |
| A45 | App/app/routes/privacy_requests.py | `guest_id` is stored without an ownership check. Data integrity only, nothing is disclosed. | LOW | Check with `access.guest`. | Open |
| A46 | App/app/routes/stay_fees.py `fee_host_reason_reference` | The disability-exemption reference is stored unencrypted, while the reason next to it is encrypted. | LOW | Encrypt the column. | Open |
| A47 | App/app/auth.py `require_login` | Outside production, with `BOOTSTRAP_ADMIN=0` and no accounts, the host UI is open. | LOW | env_guard should refuse this on a public URL. | Open |
| A48 | App/app/routes/onboarding.py `int(milestone)` | A crafted value gives a 500. | LOW | Parse defensively. | Open |

### Performance

| ID | File, location | Problem | Sev | Fix | Plan |
|---|---|---|---|---|---|
| A49 | App/app/routes/invoices.py list and `_load_invoice` | `SELECT *` loaded the ~200 KB PDF blob per row, about 10 MB for a 50-row page. | HIGH | Explicit columns, without `pdf_blob`. | T10, T87 |
| A50 | App/app/routes/stay_fees.py list; stay_fee.py `register_rows` | About 7 queries per property, and every guest is decrypted twice. | MEDIUM | Count unsigned guests in one pass and drop the second decrypt. | Open |
| A51 | App/app/reporting.py `dashboard_rows` | N+1: one full guest decrypt and one apartment query per stay. | MEDIUM | Preload guests with `IN (…)`. | Open |
| A77 | App/app/invoice_pdf.py, stay_fee_remittance_pdf.py | Every stored PDF embedded the 512 px web logo, about 140 KB of a 197 KB invoice. | MEDIUM | Embed a 192 px copy, made at runtime with Pillow (already a dependency). Printed size is unchanged (4.5 mm), so it looks the same. Invoice PDF: 197 KB to 74 KB. Regenerating PDFs instead of storing them was rejected: issued documents must stay byte-identical. | T131 to T134 |

### Launch readiness and operations

| ID | File, location | Problem | Sev | Fix | Plan |
|---|---|---|---|---|---|
| A52 | deploy/lightsail/scripts/preflight.sh, deploy/lightsail/.env.example | Production could start without a backup recipient, so the nightly backup fails with only a log line to show it. | HIGH | Preflight refuses production without `UBYHOST_BACKUP_AGE_RECIPIENT` and, by decision Q11, without the ping URL. The env template lists the key as required. The off-site copy and a restore drill stay manual (see the checklist). | T24, T30, T54, T55, T56 |
| A53 | App/app/main.py | No HTML error pages. People saw raw JSON for a 404 and plain text for a 500. | MEDIUM | Branded 404/405/500 page for HTML requests; JSON is unchanged for `/api/` and scripts. The crash page keeps no-store, CSP and frame headers and logs the route template, never a guest token. A 405 keeps Allow but shows the not-found wording. | T19-T22 |
| A54 | .github/workflows/deploy-production.yml | The deploy waited only for `test` and `smoke`. | MEDIUM | Also wait for guest-browser, shellcheck, docker and secrets. | T25 |
| A55 | .dockerignore | docs, artifacts, tests, tools, mock_ubyport and a developer `.env` went into the image or build context. | MEDIUM | Exclude them. Keep `App/scripts`. | T23 |
| A56 | App/app/env_guard.py | Only warns on production misconfigurations that should be fatal (non-https base URL, host mismatch, guest PIN off). | MEDIUM | Decision Q8: production refuses to start. It also refuses an empty operator name, IČO or address, because the legal notice must name the operator. | T51, T52, T53 |
| A57 | App/app/main.py logging | No error tracking. | LOW | Alert on ERROR lines, or add a tracker (a new dependency, so not here). | Open |
| A58 | .github/workflows/deploy-production.yml | `GITHUB_TOKEN` is persisted in the server's git remote. It expires. | LOW | Reset the remote URL after fetch. | Open |
| A59 | App/requirements.txt, requirements-dev.txt | Pillow is imported directly but declared only in the lock file (pinned there). Two dev dependencies (pdfplumber, pypdf) use `>=`. | LOW | Declare Pillow in requirements.txt; pin the two dev deps. Nothing new is added. | Open |
| A60 | App/mock_ubyport/mock_state.json | Tracked, but rewritten at runtime. | LOW | Gitignore it and seed it at start. | Open |
| A61 | Caddyfiles | HSTS has no includeSubDomains, and the Server header is not stripped. | LOW | Add both. | Open |

### Lean code

| ID | File, location | Problem | Sev | Fix | Plan |
|---|---|---|---|---|---|
| A62 | cookie_inventory, invoices, mail_notify, stay_fee_adjustment, validation_i18n, stay_fee, routes/guest, routes/admin | Unused functions and constants: `for_surface`, `view_row`, `_fmt_dates`, `_panel_text_lines`, `attach_open`, `localize_issues`, `_localize_message`, `MAX_CALENDAR_DAYS`, `CORE_ENTITY_FIELDS`. | LOW | Delete. | T115-T122 |
| A63 | app.css, host.css, components.css, guest.css | Rules for classes no template, script or Python uses: the old sidebar, focus-*, nav-sub, property-switcher, view-switch, shortcut-trigger, unused pill tones and guide screenshots. | LOW | Delete. Dynamic `property-tone-*` classes are kept. | T68, T104, T123-T126 |
| A64 | repo root, docs/plans | `CURSOR_REMEDIATION_PLAN.md`, `artifacts/` (12 MB), the dead Caddyfile, `favicon.svg` and stale plan payloads (a full stale copy of app code, patches, bundles). Nothing reads them. | LOW | Delete. Referenced docs are kept. | T135-T147 |
| A65 | stay_fee, stay_fee_remittance_pdf, invoice_pdf, templating | Three Czech money formats and two date formats, with inconsistent thousands separators. | MEDIUM | One formatting module. Not done: it touches every PDF and is mostly taste. | Open |
| A66 | App/app/ubyport_sample_pdf.py | A build-time generator that ships in the app package. | LOW | Move it to tools/. | Open |
| A67 | App/app/host_i18n.py | Four duplicate keys. The later value already won. | LOW | Delete the earlier copies. | T114 |
| A68 | App/app/config.py ACCESS_LOG comment | The comment is ambiguous: uvicorn's raw log is off, but the app's own PII-free access line is on by default. | LOW | Reword the comment. | Open |

### UX

| ID | File, location | Problem | Sev | Fix | Plan |
|---|---|---|---|---|---|
| A69 | dashboard.html, reservations.html, reservation_detail.html | The Dashboard repeated "Number of guests not known yet" on every row and pushed the next action down. The stays table and the stay page showed a bare dash with no screen-reader text. | MEDIUM | Compact guest count (Part 2 C). | T71-T76 |
| A70 | stay_fees.html, stay_fee_detail.html, invoices.html; list_month_filter.py, _host_month_filter.html | Month-only filters built twice. No property, status or search filter on Invoices. Invoices had no status column. | MEDIUM | One shared filter (Part 2 A). | T82-T96, T111, T112 |
| A71 | app.css, host.css, _components.html, several templates | Pill colours did not follow criticality ("in house" blue, unpaid grey, storno amber). Duplicate host overrides. Hard-coded stat tile colours. Contrast 5.05-5.83 on the old red, amber and teal. Red was distinguishable by colour only. | MEDIUM | Criticality tokens (Part 2 B). | T67-T70, T72, T77-T81, T97, T98 |
| A72 | guide.html, host_i18n guide keys, static/guide/*.png | Help & Guide was out of date: screenshots of the old UI, missing features (filters, stay fee, invoices, statuses). | MEDIUM | Rewritten from the code (Part 2 D). | T99-T108, T113 |
| A73 | host_i18n `hint.ready_id_optional`, `automation.timing_help` | The copy said the ID check was needed and stated the wrong retry rule. | LOW | Match the code. | T108 |
| A74 | routes/admin.py `/sync` | A manual sync blocks the request with no progress shown. | LOW | Run it in the background and show a notice. | Open |
| A75 | routes/guest.py, immediate mode | The guest's save waits for the UbyPort call, which can take 60 s or more. | LOW | Send after the response. HIGH RISK (filing), so it is not in this plan. | Open |

Checked and fine:

- ownership scoping on every host route;
- CSRF (12 routes probed at runtime);
- open-redirect handling;
- session cookie flags;
- 2FA replay protection;
- guest PIN comparison;
- SQL parameterisation;
- autoescape;
- SSRF pinning;
- passport photo encryption and deletion;
- invoice numbering under BEGIN IMMEDIATE;
- immutability triggers;
- the 10-year invoice purge;
- the stay-fee base and the 60-night rule;
- Prague time conversion;
- outcome-unknown and duplicate-150 handling;
- the healthcheck;
- the compose file.

## Part 2. Decisions

### A. One filter for Stay fees and Invoices

Model: `App/app/list_filter.py`.

- One frozen `ListFilter(month, apartment_id, status, q, default_month)`.
- `parse()` bounds every input:
  - month from 2000-01 to the current month, otherwise the view's default;
  - property must be owned by the workspace;
  - status must be one the view declares;
  - search has whitespace collapsed and is capped at 60 characters.
- `context()` gives the template everything it needs: previous/next links, max month, options, active count and reset link.
- State lives only in the URL query, so links, the back button and bookmarks work. No session state.

Component: `templates/_list_filter.html`.

- One GET form with `role=search` that applies on change.
- It degrades to an Apply button without JS.
- The same markup, CSS and keyboard order serve both pages, and the stay-fee detail page reuses the month control.

| Filter | Stay fees | Invoices | Why |
|---|---|---|---|
| Month with ‹ › steppers | Required. Defaults to the last finished month. | Optional. Default "All dates". | Stay fees are filed per period, so a period is always selected. Invoices are looked up across time. |
| Property | When there is more than one | When there is more than one | Both lists span properties. With one property the control is noise, so it is hidden. |
| Status | Needs attention / Ready / Saved | Unpaid / Paid / Corrections | The question each list answers is "what still needs me". The options are the row states the list already shows. |
| Search | No | Number or customer | Hosts look up an invoice by number or buyer. Stay-fee rows are properties, already covered by Property. |
| Reset with active-count badge | Yes | Yes | One tap back to the default. The badge shows that filters are hiding rows. |

Deleted: `App/app/list_month_filter.py`, `templates/_host_month_filter.html`, the `.host-month-filter` CSS, and the hint keys `stay_fees.filter.hint` and `invoices.filter.hint`.

Behaviour change: a future or crafted month now falls back to the view's default (last finished month on Stay fees, all dates on Invoices) instead of redirecting. Tests are updated.

### B. Status colours by criticality

Tokens are in `static/tokens.css`. Ratio is ink on bg (WCAG 2.x, computed). All pairs pass AA for small text. They are new shades derived from the existing hues of the warm palette; only the ready background (`--blue-bg`) and the neutral border (`--border`) are existing values.

| Level | Meaning | bg | ink | border | Ratio | Non-colour cue |
|---|---|---|---|---|---|---|
| critical | Blocked or failed; the host must act now | #b42318 | #ffffff | #b42318 | 6.57 | Solid fill plus a "!" glyph, unlike every other level |
| action | The host must do something | #fde9c2 | #6b3a00 | #eec27a | 7.90 | Text label |
| ready | Can be sent or used now | #e9f0fc | #1d4f9e | #c8d8f3 | 6.88 | Text label |
| waiting | Waiting on the guest or the system | #eef6f5 | #285e59 | #d3e7e4 | 6.75 | Text label |
| done | Finished | #eef6f1 | #24613f | #d3e8db | 6.68 | Text label |
| neutral | Information only | #ffffff | #5f625f | #deded9 | 6.18 | Text label, outline only |

Previous contrast: red 5.70, amber 5.83, teal 5.05.

Every pill always carries its text label, so colour is never the only signal. The existing class names map onto the tokens: `.pill.red` critical, `.amber` action, `.blue` ready, `.teal` waiting, `.green` done, `.grey` neutral.

Every status, and where it shows:

| Status (where) | Level |
|---|---|
| Stay: failed / rejected | critical |
| Stay: incomplete forms | action |
| Stay: waiting for guest (any mode); incomplete while sending is immediate | waiting |
| Stay: ready, ready (scheduled), ready (immediate), ID not checked (the ID check is optional, so it is still ready) | ready |
| Stay: reported | done |
| Stay: not required; demo preview | neutral |
| Submission: error, failed, transport error, outcome unknown | critical |
| Submission: partial, not configured | action |
| Submission: running | waiting |
| Submission: ok, accepted as duplicate (decision Q10, T109) | done |
| Submission: nothing to send | neutral |
| Guest card: rejected, rejected final | critical |
| Guest card: incomplete, ID not checked, restricted | action (kept on purpose: a per-person to-do; an existing test enforces this) |
| Guest card: ready | ready |
| Guest card: reported | done |
| Guest card: exempt, lead guest | neutral |
| Stays list: in house, cancelled or inactive stay | neutral |
| Guest register: rejected | critical |
| Guest register: not signed | action |
| Guest register: not sent | waiting |
| Guest register: reported, signed | done |
| Guest register: not required | neutral |
| Stay fees list: needs attention | action |
| Stay fees list: ready | ready |
| Stay fees list: saved vN | done |
| Stay fee detail: payment incomplete | action |
| Stay fee detail: payment ready, saved vN | done |
| Stay fee detail: line status | neutral |
| Invoice: unpaid | waiting |
| Invoice: paid | done |
| Invoice: storno / corrective, cancelled, kind | neutral |
| Calendar feed: error | critical |
| Calendar feed: suspect | action |
| Calendar feed: ok | done |
| Calendar feed: never synced | neutral |
| Properties, links, entities, users: setup needed, missing, temporary password | action |
| Properties, links, entities, users: ready, active, enabled | done |
| Properties, links, entities, users: inactive, disabled | neutral |
| Dashboard tiles: overdue | critical |
| Dashboard tiles: needs action | action |
| Dashboard tiles: ready | ready |
| Dashboard tiles: waiting | waiting |
| Deadlines: overdue, urgent | critical |
| Deadlines: soon | action |
| Deadlines: ok | done |

Removed: the unused pill tones (orange, purple, pink, brown, indigo, `.tone-*`) and the duplicate host-shell pill overrides. `docs/DESIGN.md` is updated.

### C. Guest count

The macro `guest_count(progress, placeholder=false)` lives in `_components.html`.

What it shows:

- Expected count known: a person icon plus "filled / expected", e.g. "2 / 3".
- Expected count unknown but guests exist: the icon plus the number of guests.
- Nothing known: nothing at all on the Dashboard. In tables and on the stay page (`placeholder=true`), a quiet "–" with screen-reader text "Number of guests not known yet".

Where it shows:

- Dashboard: in the context line after the deadline, not inside the next action, so the action stays first.
- Stays table: in the guests column.
- Stay page: in the Guests heading.

Status logic is unchanged. The count is display only and reads the same `progress` the status pill uses. A stay with an unknown count and no guests yet is still "waiting for guest"; one with an unfinished guest is "incomplete", as before.

### D. Help & Guide

New copy is in `App/app/guide_i18n.py`, EN and CS with identical keys (89 each). It was written by reading the routes and templates, and every button and label it names was checked against the real UI string.

Sections:

1. Overview
2. Status colours: the real pills, rendered from the same macro
3. Setup: property, calendar, police login with "Save and test connection", legal entity
4. Stays
5. Guests: link, PIN, forms, document photo only when the property requires it, cookies
6. Police reporting: manual / scheduled / immediate, retries, outcome unknown
7. Filters
8. Guest register
9. Stay fee: period, "Save period", "Start correction", adjustments
10. Invoices: issue, paid, storno, 4-item limit
11. Settings
12. Faster with shortcuts ("zkratka" in CS)
13. FAQ, including "Release assignment" when the wrong person claimed a stay
14. Demo data: shown only where demo data works (mock UbyPort)

The legal section is kept with its existing keys. Old screenshots that no longer matched the UI were deleted, along with 102 old guide keys.

## Part 3. Cursor tasks

How to run this plan:

- Apply the tasks in order, one task per commit. Use the commit message `Txx: <title>`.
- Each task touches one file.
- EDIT blocks are applied in the order listed, each against the file as the previous block left it.
- Every Find block matches the file exactly once at that point. If it does not, stop and report; do not improvise.
- REPLACE ENTIRE FILE and CREATE give the complete file, so write it byte for byte.
- DELETE paths that are directories use `git rm -r`.
- `pt` below means: `cd App && UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 python -m pytest -q -p no:cacheprovider` followed by the test files. Run the suite serially; some tests depend on order.
- Browser tests need Playwright Chromium and `UBYHOST_REQUIRE_BROWSER=1`.
- Tasks marked HIGH RISK change police filing or data retention. Review them by hand before merging.
- "Depends on: Phase N complete" means every task of that phase is done and the suite passes. Phase 5 tasks (T148 to T151) are run-only checks: they have no file and change nothing.

### Phase 1. Blockers, security, filing and retention

#### T01 Stay fee report accepts a guest who turns 18 in the period. HIGH RISK (stay-fee filing)

File: `App/app/stay_fee.py`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python
            })
        for line in period["lines"]:
            if line["status"] == "exempt":
                bucket = minors if line["auto_minor"] else hosts
                bucket["count"] += 1
                bucket["nights"] += line["exempt_nights"]
```

Replace with:

```python
            })
        for line in period["lines"]:
            if line["exempt_nights"]:
                # A guest who turns 18 inside the period is "liable" overall
                # but still carries exempt minor nights; they count as minors.
                bucket = minors if (line["auto_minor"] or line["status"] == "liable") else hosts
                bucket["count"] += 1
                bucket["nights"] += line["exempt_nights"]
```

Why: A01. The exempt minor nights of a guest who is liable overall had no bucket, so the hlášení could never be generated. Risk: this changes which bucket those nights are reported under in the municipal stay-fee report.

Verify: After T02: `pt tests/test_stay_fee.py` passes.

#### T02 Test for the 18th-birthday period

File: `App/tests/test_stay_fee.py`

Action: EDIT

Depends on: T01

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python


def test_quarterly_pdf_title(owner):
    ent = _entity(owner)
```

Replace with:

```python


def test_hlaseni_accepts_a_guest_who_turns_18_in_the_period(owner):
    ent = _entity(owner, signature_name="Josef Novák")
    aid = _apartment(owner, ent, "Apartmán Žižkov", stay_fee_payee="MČ Praha 3",
                     addr_street="Dlouhá", addr_house_no="12", addr_zip="13000", addr_obec="Praha 3")
    _stay(aid, "2026-08-10", "2026-08-14", [{"birth_date": "12082008"}])
    data = stay_fee.hlaseni(stay_fee.report_group(_apt(aid), AUG), date(2026, 9, 1))
    stay_fee_remittance_pdf.render(data)
    assert [(row["count"], row["nights"]) for row in data["not_charged"]] == [(1, 1)]


def test_quarterly_pdf_title(owner):
    ent = _entity(owner)
```

Why: A01 regression test; expects [(1, 1)] because nights count (arrival, departure].

Verify: `pt tests/test_stay_fee.py -k turns_18` passes; it fails if T01 is reverted.

#### T03 Finalize uses the computed stay-fee rate. HIGH RISK (stay-fee filing)

File: `App/app/routes/stay_fees.py`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python
    if stay_fee_filing.latest(apartment["id"], key) and not correcting:
        return _back(back_path, err=_flash(request, "flash.stay_fees.already_saved"))
    rate = stay_fee.clamp_rate(_form_str(form, "rate_czk") or apartment["stay_fee_rate_czk"])
    collected: dict[int, int] = {}
    if period:
```

Replace with:

```python
    if stay_fee_filing.latest(apartment["id"], key) and not correcting:
        return _back(back_path, err=_flash(request, "flash.stay_fees.already_saved"))
    # The stored rate must be the one the total was calculated with.
    rate = period["rate_czk"] if period else stay_fee.clamp_rate(apartment["stay_fee_rate_czk"])
    collected: dict[int, int] = {}
    if period:
```

Why: A02. The stored rate must be the rate the total was computed with, not a posted form field. Risk: it changes the rate stored with each new filing.

Verify: `pt tests/test_stay_fee_finalize.py tests/test_stay_fee_detail.py` passes.

#### T04 Remove the hidden rate field

File: `App/app/templates/stay_fee_detail.html`

Action: EDIT

Depends on: T03

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```html
      <input type="hidden" name="_csrf" value="{{ csrf_token }}">
      <input type="hidden" name="month" value="{{ month_key }}">
      <input type="hidden" name="rate_czk" value="{{ period.rate_czk }}">
      {% if lines %}<input type="hidden" name="confirm_collected" value="1">{% endif %}
      {% for line in lines %}
```

Replace with:

```html
      <input type="hidden" name="_csrf" value="{{ csrf_token }}">
      <input type="hidden" name="month" value="{{ month_key }}">
      {% if lines %}<input type="hidden" name="confirm_collected" value="1">{% endif %}
      {% for line in lines %}
```

Why: A02. The route no longer reads it.

Verify: `grep -n rate_czk App/app/templates/stay_fee_detail.html` shows no hidden input; `pt tests/test_stay_fee_detail.py` passes.

#### T05 Escape formulas in the register CSV

File: `App/app/stay_fee.py`

Action: EDIT

Depends on: T01

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```python

from . import db, payments, reporting, validation

MAX_RATE_CZK = 50        # §3d
```

Replace with:

```python

from . import db, payments, reporting, validation
from .csv_safety import csv_safe

MAX_RATE_CZK = 50        # §3d
```

Edit 2 of 2. Find (exactly once):

```python
    writer.writerow([label for _, label in REGISTER_COLUMNS])
    for row in rows:
        writer.writerow([row[key] for key, _ in REGISTER_COLUMNS])
    return ("﻿" + buffer.getvalue()).encode("utf-8")
```

Replace with:

```python
    writer.writerow([label for _, label in REGISTER_COLUMNS])
    for row in rows:
        writer.writerow([csv_safe(row[key]) for key, _ in REGISTER_COLUMNS])
    return ("﻿" + buffer.getvalue()).encode("utf-8")
```

Why: A39. Guest-typed names and addresses reach a spreadsheet.

Verify: `pt tests/test_stay_fee_downloads.py tests/test_stay_fee.py` passes.

#### T06 Guest export includes only that guest's audit rows (review by hand: privacy)

File: `App/app/dsr.py`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python
        (guest_id, guest_id),
    )
    audit_rows = db.query(
        "SELECT at, actor, action, detail FROM audit WHERE detail LIKE ? ORDER BY id",
        (f"%guest_id={guest_id}%",),
    )

```

Replace with:

```python
        (guest_id, guest_id),
    )
    owner = db.query_one(
        "SELECT a.owner_user_id AS id FROM reservation r "
        "JOIN apartment a ON a.id = r.apartment_id WHERE r.id = ?",
        (guest["reservation_id"],),
    )
    # Exact token match inside this workspace only: "guest_id=1" must not
    # pull in guest 12 or another host's audit trail. Guest actions write
    # "id=N" and the guest form writes "guest=N", so all three are matched.
    by_id, by_guest, by_form = f"guest_id={guest_id}", f"id={guest_id}", f"guest={guest_id}"
    audit_rows = db.query(
        "SELECT at, actor, action, detail FROM audit WHERE owner_user_id IS ? AND ("
        "detail = ? OR detail LIKE ? "
        "OR (action LIKE 'guest\\_%' ESCAPE '\\' AND (detail = ? OR detail LIKE ?)) "
        "OR (action = 'guest_form_saved' AND (detail = ? OR detail LIKE ?))"
        ") ORDER BY id",
        (
            owner["id"] if owner else None,
            by_id, f"{by_id} %",
            by_guest, f"{by_guest} %",
            by_form, f"{by_form} %",
        ),
    )

```

Why: A37. Cross-tenant audit rows leaked into a data-subject export. The export now also includes the guest's own rows logged as `id=N` and `guest=N`, which it used to miss.

Verify: After T28: `pt tests/test_dsr_audit.py tests/test_privacy_requests.py` passes.

#### T07 Invoice amounts: Czech thousands, finite and bounded; cap items at 4

File: `App/app/invoices.py`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 5. Find (exactly once):

```python

VAT_RATES = (0, 12, 21)
PAID_VIA_LABELS = {
    "airbnb": "Airbnb",
```

Replace with:

```python

VAT_RATES = (0, 12, 21)
# The one-page PDF fits four two-line items with VAT detail and the QR block.
MAX_ITEMS = 4
# Ten million CZK per figure: anything larger is a typo, not an invoice.
MAX_AMOUNT = Decimal("10000000")
PAID_VIA_LABELS = {
    "airbnb": "Airbnb",
```

Edit 2 of 5. Find (exactly once):

```python


def _to_decimal(text: str) -> Decimal:
    cleaned = (text or "").replace(" ", "").replace("\u00a0", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return Decimal(0)


```

Replace with:

```python


def _parse_decimal(text: str) -> Optional[Decimal]:
    """The amount, or None when it is not a finite number within MAX_AMOUNT."""
    cleaned = (text or "").replace(" ", "").replace("\u00a0", "")
    if "," in cleaned:
        # Czech style "1.000,50": the dot groups thousands, the comma is decimal.
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        value = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None
    if not value.is_finite() or abs(value) > MAX_AMOUNT:
        return None
    return value


def _to_decimal(text: str) -> Decimal:
    value = _parse_decimal(text)
    return Decimal(0) if value is None else value


```

Edit 3 of 5. Find (exactly once):

```python
        quantity = max(_to_int(_at(qtys, i, "1"), default=1), 1)
        unit = _at(units, i).strip()[:20]
        price = _to_decimal(_at(prices, i, "0"))
        if vat_status == "payer":
            rate = _to_rate(_at(rates, i))
```

Replace with:

```python
        quantity = max(_to_int(_at(qtys, i, "1"), default=1), 1)
        unit = _at(units, i).strip()[:20]
        raw_price = _at(prices, i, "0")
        price = _to_decimal(raw_price)
        if vat_status == "payer":
            rate = _to_rate(_at(rates, i))
```

Edit 4 of 5. Find (exactly once):

```python
                "vat_haler": vat,
                "gross_haler": gross,
            }
        )
```

Replace with:

```python
                "vat_haler": vat,
                "gross_haler": gross,
                # A typed price that is not a number must not become 0 Kč.
                "price_invalid": bool(raw_price.strip()) and _parse_decimal(raw_price) is None,
            }
        )
```

Edit 5 of 5. Find (exactly once):

```python
    if not draft["items"]:
        issues.append(validation.Issue("items", "invoice.err.no_items"))
    if draft["total_haler"] <= 0:
        issues.append(validation.Issue("price_czk", "invoice.err.amount"))
    return issues
```

Replace with:

```python
    if not draft["items"]:
        issues.append(validation.Issue("items", "invoice.err.no_items"))
    elif len(draft["items"]) > MAX_ITEMS:
        issues.append(validation.Issue("items", "invoice.err.too_many_items"))
    if draft["total_haler"] <= 0 or any(i.get("price_invalid") for i in draft["items"]):
        issues.append(validation.Issue("price_czk", "invoice.err.amount"))
    return issues
```

Why: A04, A05. Overflowing immutable PDFs, and prices silently turning into 0. A typed price that is not a number, or is over 10,000,000, now blocks issuing with `invoice.err.amount`.

Verify: After T09: `pt tests/test_invoice_pdf.py tests/test_invoice_corrections.py tests/test_invoice_vat.py` passes.

#### T08 Message for the item cap (EN/CS)

File: `App/app/host_i18n.py`

Action: EDIT

Depends on: T07

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```python
        "invoice.note": "Note on the invoice",
        "invoice.err.no_items": "Add at least one line item.",
        "invoice.err.seller_name": "The operator needs a name.",
        "flash.error.no_such_invoice": "No such invoice.",
```

Replace with:

```python
        "invoice.note": "Note on the invoice",
        "invoice.err.no_items": "Add at least one line item.",
        "invoice.err.too_many_items": "An invoice can have at most 4 line items. Combine items or issue a second invoice.",
        "invoice.err.seller_name": "The operator needs a name.",
        "flash.error.no_such_invoice": "No such invoice.",
```

Edit 2 of 2. Find (exactly once):

```python
        "invoice.note": "Poznámka na faktuře",
        "invoice.err.no_items": "Přidejte alespoň jednu položku.",
        "invoice.err.seller_name": "Provozovatel musí mít název.",
        "flash.error.no_such_invoice": "Faktura nenalezena.",
```

Replace with:

```python
        "invoice.note": "Poznámka na faktuře",
        "invoice.err.no_items": "Přidejte alespoň jednu položku.",
        "invoice.err.too_many_items": "Faktura může mít nejvýše 4 položky. Položky sloučte, nebo vystavte druhou fakturu.",
        "invoice.err.seller_name": "Provozovatel musí mít název.",
        "flash.error.no_such_invoice": "Faktura nenalezena.",
```

Why: A04. `invoice.err.too_many_items` must exist in both languages.

Verify: `pt tests/test_host_i18n.py` passes.

#### T09 Tests for amount parsing, invalid prices and the item cap

File: `App/tests/test_invoice_pdf.py`

Action: EDIT

Depends on: T07, T08

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python
        )
        assert data.startswith(b"%PDF")
```

Replace with:

```python
        )
        assert data.startswith(b"%PDF")


def test_invoice_amount_parsing_and_item_cap():
    from decimal import Decimal

    from app import invoices

    assert invoices._to_decimal("1.000,50") == Decimal("1000.50")
    assert invoices._to_decimal("1 234,5") == Decimal("1234.5")
    assert invoices._to_decimal("12.5") == Decimal("12.5")
    assert invoices._to_decimal("NaN") == 0
    assert invoices._to_decimal("1e30") == 0
    assert invoices.MAX_ITEMS == 4


def test_a_price_that_is_not_a_number_blocks_the_invoice():
    from app import invoices

    form = {
        "item_description": ["Stay", "Cleaning"],
        "item_quantity": ["1", "1"],
        "item_unit": ["", ""],
        "item_unit_price": ["1000", "1e30"],
        "item_vat_rate": ["12", "12"],
    }
    items = invoices._items_from_form(form, "non_payer")
    assert [item["price_invalid"] for item in items] == [False, True]
    draft = {
        "seller": {"name": "S", "seat": "P", "registry": "R", "dic": ""},
        "buyer": {"name": "B"}, "vat_status": "non_payer", "items": items,
        "total_haler": sum(item["gross_haler"] for item in items),
    }
    keys = [issue.message for issue in invoices.validate_for_issue(draft)]
    assert "invoice.err.amount" in keys
```

Why: A04, A05 regression tests.

Verify: `pt tests/test_invoice_pdf.py` passes.

#### T10 Invoice pages stop loading the PDF blob

File: `App/app/routes/invoices.py`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```python

from datetime import date
from typing import Any, Dict

```

Replace with:

```python

from datetime import date
from functools import lru_cache
from typing import Any, Dict

```

Edit 2 of 2. Find (exactly once):

```python


def _load_invoice(request: Request, invoice_id: int):
    return db.query_one(
        "SELECT * FROM invoice WHERE id = ? AND owner_user_id IS ?",
        (invoice_id, access.owner_id(request)),
    )
```

Replace with:

```python


@lru_cache(maxsize=1)
def _invoice_columns() -> str:
    """Every invoice column except the stored PDF, which only downloads read."""
    names = [row["name"] for row in db.query("PRAGMA table_info(invoice)")]
    return ", ".join(name for name in names if name != "pdf_blob")


def _load_invoice(request: Request, invoice_id: int):
    return db.query_one(
        f"SELECT {_invoice_columns()} FROM invoice WHERE id = ? AND owner_user_id IS ?",
        (invoice_id, access.owner_id(request)),
    )
```

Why: A49. Detail and action routes read the ~200 KB blob for nothing.

Verify: `pt tests/test_invoice_ux.py tests/test_invoice_corrections.py tests/test_invoice_workspace.py` passes.

#### T11 Workspace deletion in one transaction, full coverage. HIGH RISK (retention)

File: `App/app/retention.py`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 3. Find (exactly once):

```python

import json
import time
from datetime import date, datetime, timedelta, timezone
```

Replace with:

```python

import json
import logging
import time
from datetime import date, datetime, timedelta, timezone
```

Edit 2 of 3. Find (exactly once):

```python

from . import alerts, config, db, housebook, invoices, passport_photos

# G-D5: null the claim e-mail / reservation e-mail / phone fragment this long
```

Replace with:

```python

from . import alerts, config, db, housebook, invoices, passport_photos

log = logging.getLogger(__name__)

# G-D5: null the claim e-mail / reservation e-mail / phone fragment this long
```

Edit 3 of 3. Find (exactly once):

```python

def _delete_workspace(owner_id: int) -> None:
    """Remove every row that belongs to one workspace, in dependency order."""
    for guest in db.query(
        "SELECT g.id AS id FROM guest g JOIN reservation r ON r.id = g.reservation_id "
        "JOIN apartment a ON a.id = r.apartment_id WHERE a.owner_user_id IS ?",
        (owner_id,),
    ):
        passport_photos.delete_photo(guest["id"])
    db.execute(
        "DELETE FROM guest WHERE reservation_id IN "
        "(SELECT r.id FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        "WHERE a.owner_user_id IS ?)",
        (owner_id,),
    )
    db.execute(
        "DELETE FROM submission WHERE apartment_id IN "
        "(SELECT id FROM apartment WHERE owner_user_id IS ?)",
        (owner_id,),
    )
    db.execute(
        "DELETE FROM reservation WHERE apartment_id IN "
        "(SELECT id FROM apartment WHERE owner_user_id IS ?)",
        (owner_id,),
    )
    db.execute("DELETE FROM apartment WHERE owner_user_id IS ?", (owner_id,))

    invoice_ids = [
        row["id"]
        for row in db.query("SELECT id FROM invoice WHERE owner_user_id IS ?", (owner_id,))
    ]
    if invoice_ids:
        db.execute(
            "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '1') "
            "ON CONFLICT(key) DO UPDATE SET value = '1'"
        )
        try:
            for invoice_id in invoice_ids:
                db.execute("DELETE FROM invoice_item WHERE invoice_id = ?", (invoice_id,))
                db.execute("DELETE FROM invoice WHERE id = ?", (invoice_id,))
        finally:
            db.execute(
                "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '') "
                "ON CONFLICT(key) DO UPDATE SET value = ''"
            )

    db.execute("DELETE FROM legal_entity WHERE owner_user_id IS ?", (owner_id,))

    db.execute("DELETE FROM data_subject_request WHERE owner_user_id IS ?", (owner_id,))
    db.execute("DELETE FROM alert WHERE owner_user_id IS ?", (owner_id,))
    # legal_acceptance has a NOT NULL account reference, so it cannot outlive the
    # account; see FOLLOWUPS.md for the tension with G-D7.
    db.execute("DELETE FROM legal_acceptance WHERE user_account_id = ?", (owner_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id IS ?", (owner_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


```

Replace with:

```python

def _delete_workspace(owner_id: int) -> None:
    """Remove every row that belongs to one workspace, in dependency order.

    One transaction: a failure part-way used to leave the account and its
    entities behind with the guests already gone, and fail again every night.
    """
    apartments = "(SELECT id FROM apartment WHERE owner_user_id IS ?)"
    entities = "(SELECT id FROM legal_entity WHERE owner_user_id IS ?)"
    with db.immediate() as cur:
        # Read inside the lock so a guest saved a moment earlier keeps no photo.
        cur.execute(
            "SELECT g.id AS id FROM guest g JOIN reservation r ON r.id = g.reservation_id "
            "JOIN apartment a ON a.id = r.apartment_id WHERE a.owner_user_id IS ?",
            (owner_id,),
        )
        guest_ids = [row["id"] for row in cur.fetchall()]
        cur.execute(
            "DELETE FROM guest WHERE reservation_id IN "
            f"(SELECT id FROM reservation WHERE apartment_id IN {apartments})",
            (owner_id,),
        )
        cur.execute(f"DELETE FROM submission WHERE apartment_id IN {apartments}", (owner_id,))
        cur.execute(f"DELETE FROM reservation WHERE apartment_id IN {apartments}", (owner_id,))
        cur.execute(
            f"DELETE FROM stay_fee_adjustment WHERE apartment_id IN {apartments}", (owner_id,)
        )
        cur.execute(f"DELETE FROM stay_fee_filing WHERE apartment_id IN {apartments}", (owner_id,))
        cur.execute(
            "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '1') "
            "ON CONFLICT(key) DO UPDATE SET value = '1'"
        )
        # Corrections first: they reference the invoice they correct.
        cur.execute(
            "DELETE FROM invoice_item WHERE invoice_id IN "
            "(SELECT id FROM invoice WHERE owner_user_id IS ?)",
            (owner_id,),
        )
        cur.execute(
            "DELETE FROM invoice WHERE owner_user_id IS ? AND corrects_invoice_id IS NOT NULL",
            (owner_id,),
        )
        cur.execute("DELETE FROM invoice WHERE owner_user_id IS ?", (owner_id,))
        cur.execute(
            "UPDATE settings SET value = '' WHERE key = 'invoice_purge_unlock'"
        )
        # Queued mail carries guest addresses and must not outlive the workspace.
        cur.execute(
            f"DELETE FROM email_outbox WHERE owner_user_id IS ? OR apartment_id IN {apartments}",
            (owner_id, owner_id),
        )
        cur.execute("DELETE FROM apartment WHERE owner_user_id IS ?", (owner_id,))
        cur.execute(f"DELETE FROM invoice_sequence WHERE legal_entity_id IN {entities}", (owner_id,))
        cur.execute("DELETE FROM legal_entity WHERE owner_user_id IS ?", (owner_id,))
        cur.execute("DELETE FROM data_subject_request WHERE owner_user_id IS ?", (owner_id,))
        cur.execute("DELETE FROM alert WHERE owner_user_id IS ?", (owner_id,))
        # legal_acceptance has a NOT NULL account reference, so it cannot
        # outlive the account.
        cur.execute("DELETE FROM legal_acceptance WHERE user_account_id = ?", (owner_id,))
        cur.execute("DELETE FROM audit WHERE owner_user_id IS ?", (owner_id,))
        cur.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))
    # Files last: a rolled-back delete must not have lost the photos. One
    # failing file must not stop the rest; the orphan sweep retries it.
    for guest_id in guest_ids:
        try:
            passport_photos.delete_photo(guest_id)
        except OSError:
            log.exception("workspace deletion: photo for guest %s not removed", guest_id)


```

Why: A18. Partial deletes left accounts, filings and audit rows behind, and the job failed every night. Risk: on main this function always failed, so in practice nothing was ever deleted. From now on, a workspace past `deletion_due_at` really loses its guests, invoices, stay-fee filings and adjustments, corrections, sequences and queued mail. Guest IDs are read inside the lock. A photo that fails to delete is logged and left for the orphan sweep. Confirm Q9 with counsel before merging.

Verify: After T12: `pt tests/test_workspace_termination.py tests/test_retention.py` passes.

#### T12 Test full workspace deletion

File: `App/tests/test_workspace_termination.py`

Action: EDIT

Depends on: T11

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python
    retention._workspace_deletion_step(date.today(), False, None)
    assert db.query_one("SELECT id FROM invoice WHERE id = ?", (invoice,)) is None
```

Replace with:

```python
    retention._workspace_deletion_step(date.today(), False, None)
    assert db.query_one("SELECT id FROM invoice WHERE id = ?", (invoice,)) is None


def test_a_workspace_with_filed_stay_fees_and_property_invoices_is_deleted_completely():
    owner, entity, apartment, _reservation, _guest = _seed("ws-full")
    now = db.utcnow()
    db.insert("invoice_sequence", {"legal_entity_id": entity, "year": 2026, "last_no": 1})
    db.insert(
        "invoice",
        {
            "legal_entity_id": entity, "apartment_id": apartment, "kind": "invoice",
            "seq_year": 2026, "seq_no": 1, "number": "INV-2", "vs": "2", "lang": "en",
            "vat_status": "non_payer", "issue_date": "2026-01-01", "seller_name": "S",
            "seller_seat": "P", "buyer_name": "B", "total_haler": 100, "issued_at": now,
            "owner_user_id": owner, "created_at": now,
        },
    )
    filing = db.insert(
        "stay_fee_filing",
        {
            "apartment_id": apartment, "period_key": "2026-01", "cadence": "monthly",
            "rate_czk": 50, "liable_days": 1, "exempt_days": 0, "total_due_czk": 50,
            "total_collected_czk": 50, "created_at": now,
        },
    )
    db.insert(
        "stay_fee_adjustment",
        {
            "apartment_id": apartment, "period_key": "2026-01", "direction": "add",
            "mode": "bed_days", "bed_days": 1, "reason_enc": "x", "created_at": now,
            "filing_id": filing,
        },
    )
    mail = db.insert(
        "email_outbox",
        {
            "idempotency_key": "ws-full-mail", "kind": "guest_link", "apartment_id": apartment,
            "owner_user_id": owner, "to_email": "guest@example.invalid", "created_at": now,
            "updated_at": now,
        },
    )
    db.execute(
        "UPDATE user_account SET deletion_due_at = ? WHERE id = ?",
        ((date.today() - timedelta(days=1)).isoformat(), owner),
    )
    retention._workspace_deletion_step(date.today(), False, None)
    assert db.query_one("SELECT id FROM user_account WHERE id = ?", (owner,)) is None
    assert db.query_one("SELECT id FROM apartment WHERE id = ?", (apartment,)) is None
    assert db.query_one("SELECT id FROM legal_entity WHERE id = ?", (entity,)) is None
    assert db.query_one("SELECT id FROM email_outbox WHERE id = ?", (mail,)) is None
```

Why: A18 regression test, including queued mail. It fails on the old code with a FOREIGN KEY error.

Verify: `pt tests/test_workspace_termination.py` passes.

#### T13 A running batch with no live send claim becomes outcome unknown. HIGH RISK (filing)

File: `App/app/reporting.py`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```python


def submit_for_apartment(
    apartment_id: int,
```

Replace with:

```python


def recover_stale_submissions(apartment_id: int) -> int:
    """Treat a batch stuck in ``running`` as one whose outcome is unknown.

    A process that dies mid-call (deploy, OOM) leaves the row ``running`` with
    no guest pointing at it, so the next pass would refile a batch the register
    may already hold. A batch is stale as soon as none of its guests holds a
    live send claim: nobody is sending it any more, and the lapsed claim would
    otherwise let the next pass claim and refile them. Hold its guests for a
    person, exactly like an unanswered call.
    """
    live_after = time.time() - SUBMISSION_CLAIM_TTL_SECONDS
    reason = "The send stopped before UbyPort answered."
    stale = []
    with db.immediate() as cur:
        cur.execute(
            "SELECT id, guest_ids FROM submission WHERE apartment_id = ? AND state = 'running'",
            (apartment_id,),
        )
        for row in cur.fetchall():
            guest_ids = json.loads(row["guest_ids"] or "[]")
            if guest_ids:
                marks = ",".join("?" * len(guest_ids))
                cur.execute(
                    f"SELECT 1 FROM submission_claim WHERE guest_id IN ({marks}) "
                    "AND claimed_at >= ? LIMIT 1",
                    (*guest_ids, live_after),
                )
                if cur.fetchone():
                    continue
            stale.append(row["id"])
            db.update_in(
                cur, "submission", row["id"],
                {"state": "outcome_unknown", "finished_at": db.utcnow(), "error_text": reason},
            )
            for guest_id in guest_ids:
                cur.execute(
                    "UPDATE guest SET submission_id = ? WHERE id = ? AND submit_state != ? "
                    "AND (submission_id IS NULL OR submission_id < ?)",
                    (row["id"], guest_id, SENT, row["id"]),
                )
    if not stale:
        return 0
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    alerts.raise_alert(
        "critical",
        "submission_outcome_unknown",
        f"{apartment['internal_name']}: UbyPort may or may not have received the report.",
        reason,
        dedupe_key=f"submission_outcome_unknown:{apartment_id}",
        apartment_id=apartment_id,
        params={"property": apartment["internal_name"], "error": reason},
    )
    log.error("ubyport_submission_stale apartment_id=%s submissions=%s",
              apartment_id, stale)
    return len(stale)


def submit_for_apartment(
    apartment_id: int,
```

Edit 2 of 2. Find (exactly once):

```python
            }
        ]

    ap_dict = dict(apartment)
```

Replace with:

```python
            }
        ]
    recover_stale_submissions(apartment_id)

    ap_dict = dict(apartment)
```

Why: A16. A batch that died mid-send stayed `running` and its guests were sent again. Staleness is judged by the send claim, not by the row's age: once no guest of the batch holds a live claim, nobody is sending it, and a lapsed claim would otherwise let the next pass claim and send again. The check runs under BEGIN IMMEDIATE. A guest already linked to a newer batch keeps that link. Risk: the next sweep now holds those guests for the host instead of sending them again.

Verify: After T14: `pt tests/test_stale_submission.py tests/test_ubyport_outcome_unknown.py tests/test_submission_retry_cap.py` passes.

#### T14 Test stale batch recovery

File: `App/tests/test_stale_submission.py`

Action: CREATE

Depends on: T13

Code:

Full content:

```python
"""A batch left 'running' by a dead process is held for a person, not resent."""
from __future__ import annotations

import json
import time

from app import db, reporting


def _guest(reservation: int, name: str, now: str) -> int:
    return db.insert(
        "guest",
        {"reservation_id": reservation, "surname": name, "first_name": "Test",
         "nationality": "GBR", "created_at": now, "updated_at": now},
    )


def _batch(apartment: int, guests: list, now: str) -> int:
    return db.insert(
        "submission",
        {"apartment_id": apartment, "created_at": now, "mode": "auto",
         "state": "running", "guest_ids": json.dumps(guests)},
    )


def test_a_running_batch_without_a_live_claim_becomes_outcome_unknown():
    db.init_db()
    now = db.utcnow()
    apartment = db.insert("apartment", {"internal_name": "Stale flat", "created_at": now})
    reservation = db.insert(
        "reservation",
        {"apartment_id": apartment, "uid": "stale-1", "date_from": "2026-01-01",
         "date_to": "2026-01-03", "status": "active", "created_at": now, "updated_at": now},
    )
    dead, sending, moved_on = (_guest(reservation, n, now) for n in ("Dead", "Sending", "Moved"))
    # A fresh row counts as stale once its claim has lapsed: the age of the
    # row is not what matters, the lease is.
    dead_batch = _batch(apartment, [dead], now)
    live_batch = _batch(apartment, [sending], now)
    db.insert("submission_claim", {"guest_id": sending, "claim_token": "t", "claimed_at": time.time()})
    old_batch = _batch(apartment, [moved_on], now)
    newer = db.insert(
        "submission",
        {"apartment_id": apartment, "created_at": now, "mode": "auto",
         "state": "error", "guest_ids": json.dumps([moved_on])},
    )
    db.execute("UPDATE guest SET submission_id = ? WHERE id = ?", (newer, moved_on))

    assert reporting.recover_stale_submissions(apartment) == 2

    def state(sid):
        return db.query_one("SELECT state FROM submission WHERE id = ?", (sid,))["state"]

    def pointer(gid):
        return db.query_one("SELECT submission_id FROM guest WHERE id = ?", (gid,))["submission_id"]

    assert state(dead_batch) == "outcome_unknown"
    assert state(old_batch) == "outcome_unknown"
    assert state(live_batch) == "running"
    assert pointer(dead) == dead_batch
    assert pointer(sending) is None
    assert pointer(moved_on) == newer, "a newer batch keeps the guest's pointer"
    assert reporting.apartment_in_doubt(apartment)
```

Why: A16 regression test. It covers a dead batch, a batch still being sent (live claim) and a newer pointer that must be kept.

Verify: `pt tests/test_stale_submission.py` passes.

#### T15 Immediate send respects the refused-login pause. HIGH RISK (filing)

File: `App/app/reporting.py`

Action: EDIT

Depends on: T13

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python
    completed_at = refresh_registration_completed_at(reservation_id)
    if not completed_at or apartment["automation_mode"] != "immediate":
        return
    reservation = db.query_one(
```

Replace with:

```python
    completed_at = refresh_registration_completed_at(reservation_id)
    if not completed_at or apartment["automation_mode"] != "immediate":
        return
    if alerts.open_alert(f"ubyport_auth_failed:{apartment_id}"):
        # Same pause as the sweep: retrying a refused login on every guest
        # save risks locking the police account.
        return
    reservation = db.query_one(
```

Why: A26. Repeated logins after a refusal can lock the police account. Risk: immediate mode now stops sending while the pause alert is open, exactly like the sweep.

Verify: `pt tests/test_send_controls.py tests/test_submission_retry_cap.py` passes.

#### T16 Warn when a cancelled stay still has guests to file. HIGH RISK (filing)

File: `App/app/icalsync.py`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 3. Find (exactly once):

```python


def _cancel_existing_stay(apartment_id: int, uid: str, date_from: str, now: str, stats: Dict[str, Any]) -> None:
    """Mark an active future stay as cancelled when the feed signals cancellation."""
```

Replace with:

```python


def _warn_if_guests_registered(reservation, apartment_id: int, variant: str) -> None:
    """A cancelled stay that already has guest forms is never filed: say so.

    Some portals re-issue a booking under a new UID when it is modified, so a
    stay with completed forms may simply have moved. The host decides.
    """
    # Only guests the police still expect: Czech nationals are never filed.
    registered = db.query_one(
        "SELECT COUNT(*) AS n FROM guest WHERE reservation_id = ? AND archived_at IS NULL "
        "AND submit_state NOT IN ('sent', 'not_required')",
        (reservation["id"],),
    )
    if not registered or not registered["n"]:
        return
    alerts.raise_alert(
        "warning",
        "cancelled_with_guests",
        f"A stay from {reservation['date_from']} with guest forms was cancelled in the calendar.",
        "Nothing will be reported for it. If the booking only moved, set the stay back to Active.",
        dedupe_key=f"cancelled_with_guests:{reservation['id']}",
        apartment_id=apartment_id,
        reservation_id=reservation["id"],
        params={"date": reservation["date_from"], "variant": variant},
    )


def _cancel_existing_stay(apartment_id: int, uid: str, date_from: str, now: str, stats: Dict[str, Any]) -> None:
    """Mark an active future stay as cancelled when the feed signals cancellation."""
```

Edit 2 of 3. Find (exactly once):

```python

    stay_claim.expire_on_cancel(existing)
    stats["cancelled"] += 1

```

Replace with:

```python

    stay_claim.expire_on_cancel(existing)
    _warn_if_guests_registered(existing, apartment_id, "cancelled")
    stats["cancelled"] += 1

```

Edit 3 of 3. Find (exactly once):

```python

        stay_claim.expire_on_cancel(row)
        stats["cancelled"] += 1

```

Replace with:

```python

        stay_claim.expire_on_cancel(row)
        _warn_if_guests_registered(row, feed["apartment_id"], "disappeared")
        stats["cancelled"] += 1

```

Why: A17. Guests on a cancelled stay are never filed, and nobody was told. Only guests that still need filing count; Czech nationals (`not_required`) and guests already sent do not. Risk: alert only. The cancellation itself is unchanged.

Verify: After T27: `pt tests/test_cancelled_with_guests.py tests/test_icalsync.py` passes.

#### T17 Copy for the cancelled-with-guests alert

File: `App/app/host_i18n.py`

Action: EDIT

Depends on: T08, T16

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```python
        "notification.cancelled_after_report.title.disappeared": "A stay from %(date)s disappeared from the calendar after it had already been reported to the police.",
        "notification.cancelled_after_report.detail": "Check whether the booking was cancelled or merely moved.",
        "notification.feed_error.title": "Calendar '%(feed)s' could not be synchronised.",
        "notification.feed_error.detail": "The calendar server answered: %(error)s",
```

Replace with:

```python
        "notification.cancelled_after_report.title.disappeared": "A stay from %(date)s disappeared from the calendar after it had already been reported to the police.",
        "notification.cancelled_after_report.detail": "Check whether the booking was cancelled or merely moved.",
        "notification.cancelled_with_guests.title.cancelled": "A stay from %(date)s with guest forms was cancelled in the calendar.",
        "notification.cancelled_with_guests.title.disappeared": "A stay from %(date)s with guest forms disappeared from the calendar.",
        "notification.cancelled_with_guests.detail": "Nothing will be reported for it. If the booking only moved, set the stay back to Active.",
        "notification.feed_error.title": "Calendar '%(feed)s' could not be synchronised.",
        "notification.feed_error.detail": "The calendar server answered: %(error)s",
```

Edit 2 of 2. Find (exactly once):

```python
        "notification.cancelled_after_report.title.disappeared": "Pobyt od %(date)s zmizel z kalendáře poté, co již byl nahlášen na policii.",
        "notification.cancelled_after_report.detail": "Zkontrolujte, zda byla rezervace zrušena, nebo se jen přesunula.",
        "notification.feed_error.title": "Kalendář '%(feed)s' se nepodařilo synchronizovat.",
        "notification.feed_error.detail": "Server kalendáře odpověděl: %(error)s",
```

Replace with:

```python
        "notification.cancelled_after_report.title.disappeared": "Pobyt od %(date)s zmizel z kalendáře poté, co již byl nahlášen na policii.",
        "notification.cancelled_after_report.detail": "Zkontrolujte, zda byla rezervace zrušena, nebo se jen přesunula.",
        "notification.cancelled_with_guests.title.cancelled": "Pobyt od %(date)s s vyplněnými formuláři byl v kalendáři zrušen.",
        "notification.cancelled_with_guests.title.disappeared": "Pobyt od %(date)s s vyplněnými formuláři zmizel z kalendáře.",
        "notification.cancelled_with_guests.detail": "Nic se za něj nenahlásí. Pokud se rezervace jen přesunula, nastavte pobyt zpět na Aktivní.",
        "notification.feed_error.title": "Kalendář '%(feed)s' se nepodařilo synchronizovat.",
        "notification.feed_error.detail": "Server kalendáře odpověděl: %(error)s",
```

Why: A17. Alert title and text, EN and CS, for both variants (cancelled and disappeared).

Verify: `pt tests/test_host_i18n.py` passes.

#### T18 Calendar fetch: UTF-8 default, no BOM, 60 s total limit

File: `App/app/feed_fetch.py`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 3. Find (exactly once):

```python
import socket
import sys
from typing import Optional

```

Replace with:

```python
import socket
import sys
import time
from typing import Optional

```

Edit 2 of 3. Find (exactly once):

```python
FETCH_TIMEOUT = 45
MAX_FEED_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 3

```

Replace with:

```python
FETCH_TIMEOUT = 45
MAX_FEED_BYTES = 5 * 1024 * 1024
# A server that trickles bytes would otherwise hold the sync for ever.
TOTAL_TIMEOUT_SECONDS = 60
MAX_REDIRECTS = 3

```

Edit 3 of 3. Find (exactly once):

```python
            raise CalendarFetchError("Calendar is too large.")
        body = bytearray()
        for chunk in response.iter_content(chunk_size=64 * 1024):
            body.extend(chunk)
            if len(body) > MAX_FEED_BYTES:
                raise CalendarFetchError("Calendar is too large.")
        text = bytes(body).decode(response.encoding or "utf-8", errors="replace")
    except requests.RequestException as exc:
        raise CalendarFetchError(f"Could not download the calendar: {exc}") from exc
```

Replace with:

```python
            raise CalendarFetchError("Calendar is too large.")
        body = bytearray()
        deadline = time.monotonic() + TOTAL_TIMEOUT_SECONDS
        for chunk in response.iter_content(chunk_size=64 * 1024):
            body.extend(chunk)
            if len(body) > MAX_FEED_BYTES:
                raise CalendarFetchError("Calendar is too large.")
            if time.monotonic() > deadline:
                raise CalendarFetchError("Calendar download took too long.")
        # iCal is UTF-8 by spec. requests guesses ISO-8859-1 for any text/*
        # without a charset, which garbled Czech names; trust only an explicit one.
        declared = "charset" in response.headers.get("Content-Type", "").lower()
        encoding = response.encoding if declared and response.encoding else "utf-8-sig"
        # A BOM survives a declared "charset=utf-8" and breaks the parser.
        text = bytes(body).decode(encoding, errors="replace").lstrip("\ufeff")
    except requests.RequestException as exc:
        raise CalendarFetchError(f"Could not download the calendar: {exc}") from exc
```

Why: A20, A21. `requests` guessed Latin-1 for `text/*` without a charset. A BOM survived a declared charset and broke the parser. A trickling server could hold the sync forever.

Verify: After T29: `pt tests/test_feed_dns_pinning.py tests/test_icalsync.py` passes.

#### T19 Branded error page

File: `App/app/templates/error.html`

Action: CREATE

Depends on: none

Code:

Full content:

```html
{% extends "auth_base.html" %}
{% block title %}{{ t('error.' ~ error_kind ~ '.title') }} · UbyHost{% endblock %}
{% block auth_body %}
<h1>{{ t('error.' ~ error_kind ~ '.title') }}</h1>
<p class="lede">{{ t('error.' ~ error_kind ~ '.body') }}</p>
<p><a class="btn primary" href="/">{{ t('error.home') }}</a></p>
{% endblock %}
```

Why: A53. A branded page that people see instead of raw JSON. It extends auth_base, so it works signed in or out.

Verify: After T22.

#### T20 HTML error handlers for people, JSON for scripts (review by hand: security headers)

File: `App/app/main.py`

Action: EDIT

Depends on: T19

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 4. Find (exactly once):

```python

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import (
```

Replace with:

```python

from fastapi import Depends, FastAPI, Request, Response
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import (
```

Edit 2 of 4. Find (exactly once):

```python
    security,
    seo,
)
from .routes import admin, guest, invoices, legal, stay_fees
```

Replace with:

```python
    security,
    seo,
    templating,
)
from .routes import admin, guest, invoices, legal, stay_fees
```

Edit 3 of 4. Find (exactly once):

```python


@app.exception_handler(security.GuestFormExpiredError)
async def guest_form_expired_handler(request: Request, exc: security.GuestFormExpiredError):
```

Replace with:

```python


def _wants_html(request: Request) -> bool:
    return not request.url.path.startswith("/api/") and "text/html" in request.headers.get("accept", "")


_CSP = (
    "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
    "form-action 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
    "script-src 'self' 'unsafe-inline' https://challenges.cloudflare.com; "
    "frame-src https://challenges.cloudflare.com; "
    "connect-src 'self' https://challenges.cloudflare.com"
)


def _harden(response):
    """Headers every page needs. The 500 handler runs outside the middleware."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=()")
    response.headers.setdefault("Content-Security-Policy", _CSP)
    return response


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    """A branded page for people; the JSON body stays for scripts and the API."""
    if exc.status_code not in (404, 405) or not _wants_html(request):
        return await http_exception_handler(request, exc)
    response = templating.render(
        request, "error.html", {"error_kind": "not_found"}, status_code=exc.status_code
    )
    if exc.headers:
        response.headers.update(exc.headers)  # keeps Allow on a 405
    return response


@app.exception_handler(Exception)
async def server_error_handler(request: Request, exc: Exception):
    """Log the failure and show a calm page instead of a bare 500 text."""
    # The route template, never the path: guest links carry a token (OPS-3).
    log.exception("unhandled error on %s", _access_route(request))
    response = None
    if _wants_html(request):
        try:
            response = templating.render(request, "error.html", {"error_kind": "server"}, status_code=500)
        except Exception:
            log.exception("error page failed to render")
    if response is None:
        response = PlainTextResponse("Internal Server Error", status_code=500)
    response.headers["Cache-Control"] = "no-store, private"
    return _harden(response)


@app.exception_handler(security.GuestFormExpiredError)
async def guest_form_expired_handler(request: Request, exc: security.GuestFormExpiredError):
```

Edit 4 of 4. Find (exactly once):

```python
    response = await call_next(request)
    security.attach_csrf_cookie(request, response)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
        "form-action 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline' https://challenges.cloudflare.com; "
        "frame-src https://challenges.cloudflare.com; "
        "connect-src 'self' https://challenges.cloudflare.com",
    )
    # Everything outside /static carries passport numbers, addresses and
    # signatures. Guests hand the phone back and hosts share laptops, so these
```

Replace with:

```python
    response = await call_next(request)
    security.attach_csrf_cookie(request, response)
    _harden(response)
    # Everything outside /static carries passport numbers, addresses and
    # signatures. Guests hand the phone back and hosts share laptops, so these
```

Why: A53. Guests saw raw JSON and plain-text errors. The 500 handler runs outside the HTTP middleware, so it sets no-store, CSP and frame headers itself. It logs the route template, never the path, because guest links carry a token (OPS-3). A 405 keeps its Allow header.

Verify: After T22.

#### T21 Error page copy (EN/CS)

File: `App/app/host_i18n.py`

Action: EDIT

Depends on: T17, T19

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```python
        "invoice.note": "Note on the invoice",
        "invoice.err.no_items": "Add at least one line item.",
        "invoice.err.too_many_items": "An invoice can have at most 4 line items. Combine items or issue a second invoice.",
        "invoice.err.seller_name": "The operator needs a name.",
```

Replace with:

```python
        "invoice.note": "Note on the invoice",
        "invoice.err.no_items": "Add at least one line item.",
        "error.not_found.title": "Page not found",
        "error.not_found.body": "The link is wrong or the page no longer exists.",
        "error.server.title": "Something went wrong",
        "error.server.body": "We could not finish that. Check the page before trying again, then try again in a moment.",
        "error.home": "Back to UbyHost",
        "invoice.err.too_many_items": "An invoice can have at most 4 line items. Combine items or issue a second invoice.",
        "invoice.err.seller_name": "The operator needs a name.",
```

Edit 2 of 2. Find (exactly once):

```python
        "invoice.note": "Poznámka na faktuře",
        "invoice.err.no_items": "Přidejte alespoň jednu položku.",
        "invoice.err.too_many_items": "Faktura může mít nejvýše 4 položky. Položky sloučte, nebo vystavte druhou fakturu.",
        "invoice.err.seller_name": "Provozovatel musí mít název.",
```

Replace with:

```python
        "invoice.note": "Poznámka na faktuře",
        "invoice.err.no_items": "Přidejte alespoň jednu položku.",
        "error.not_found.title": "Stránka nenalezena",
        "error.not_found.body": "Odkaz je chybný, nebo stránka už neexistuje.",
        "error.server.title": "Něco se pokazilo",
        "error.server.body": "Akci se nepodařilo dokončit. Než to zkusíte znovu, zkontrolujte stránku, a pak to zkuste za chvíli.",
        "error.home": "Zpět do UbyHost",
        "invoice.err.too_many_items": "Faktura může mít nejvýše 4 položky. Položky sloučte, nebo vystavte druhou fakturu.",
        "invoice.err.seller_name": "Provozovatel musí mít název.",
```

Why: A53. The crash copy does not promise that nothing was sent, because after an unhandled error that is not guaranteed.

Verify: `pt tests/test_host_i18n.py` passes.

#### T22 Test error pages

File: `App/tests/test_error_pages.py`

Action: CREATE

Depends on: T20, T21

Code:

Full content:

```python
"""People get a branded error page; scripts keep the JSON body."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import db
from app.main import app


def test_unknown_page_is_html_for_browsers_and_json_otherwise():
    db.init_db()
    client = TestClient(app)
    page = client.get("/no-such-page?lang=en", headers={"accept": "text/html"})
    assert page.status_code == 404
    assert "text/html" in page.headers["content-type"]
    assert "Page not found" in page.text or "Stránka nenalezena" in page.text
    api = client.get("/no-such-page")
    assert api.status_code == 404
    assert api.headers["content-type"].startswith("application/json")


def test_a_crash_page_keeps_the_security_headers_and_logs_no_token(caplog):
    db.init_db()

    async def boom(token: str):
        raise RuntimeError("boom")

    app.add_api_route("/__test_boom/{token}", boom)
    client = TestClient(app, raise_server_exceptions=False)
    page = client.get("/__test_boom/secret-token-123", headers={"accept": "text/html"})
    assert page.status_code == 500
    assert page.headers["cache-control"] == "no-store, private"
    assert page.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
    assert "secret-token-123" not in caplog.text
    assert "/__test_boom/{token}" in caplog.text


def test_a_405_page_keeps_the_allow_header():
    db.init_db()
    client = TestClient(app)
    page = client.put("/login", headers={"accept": "text/html"})
    assert page.status_code == 405
    assert "allow" in {key.lower() for key in page.headers}
```

Why: A53 regression tests: HTML vs JSON, crash headers, no token in the log, Allow on 405.

Verify: `pt tests/test_error_pages.py` passes.

#### T23 Keep docs, tests, tools and .env out of the image

File: `.dockerignore`

Action: REPLACE ENTIRE FILE

Depends on: none

Code:

Full content:

```
.git
.github
**/.venv
**/__pycache__
**/.pytest_cache
App/data/*
!App/data/.gitkeep
.screenshots
*.md
!App/README.md
docs/
artifacts/
.cursor/
App/tests
App/tools
App/mock_ubyport
**/.env
**/.env.*
!**/.env.example
**/.coverage
**/htmlcov
```

Why: A55. The image must not contain docs, tests, tools, the mock server or a developer .env. App/scripts stays, because backups run it inside the container.

Verify: `docker build .` succeeds (the CI docker job) and `docker run --rm <image> ls /app` shows no tests, tools or mock_ubyport.

#### T24 Preflight refuses production without a backup recipient

File: `deploy/lightsail/scripts/preflight.sh`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```bash
fi

if [ -n "${UBYHOST_SECRET_KEY:-}" ] && [ "${#UBYHOST_SECRET_KEY}" -lt 32 ]; then
  die "UBYHOST_SECRET_KEY must be at least 32 characters (or leave empty for auto-generate)"
```

Replace with:

```bash
fi

if [ "${DEPLOYMENT}" = "production" ] && [ -z "${UBYHOST_BACKUP_AGE_RECIPIENT:-}" ]; then
  die "UBYHOST_BACKUP_AGE_RECIPIENT is empty — the nightly backup refuses to run on production without it"
fi

if [ "${DEPLOYMENT}" = "production" ] && [ -z "${UBYHOST_BACKUP_PING_URL:-}" ]; then
  warn "UBYHOST_BACKUP_PING_URL is empty — a failing nightly backup will go unnoticed"
fi

if [ -n "${UBYHOST_SECRET_KEY:-}" ] && [ "${#UBYHOST_SECRET_KEY}" -lt 32 ]; then
  die "UBYHOST_SECRET_KEY must be at least 32 characters (or leave empty for auto-generate)"
```

Why: A52. Without the recipient the nightly backup fails, with only a log line to show it.

Verify: `bash -n deploy/lightsail/scripts/preflight.sh` succeeds. CI shellcheck passes. With `UBYHOST_DEPLOYMENT=production` and no recipient, the script exits non-zero.

#### T25 Deploy waits for every CI check

File: `.github/workflows/deploy-production.yml`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```yaml
            -H "Accept: application/vnd.github+json" \
            "https://api.github.com/repos/jsfpechar-ops/jsfpecharoperations/commits/${DEPLOY_SHA}/check-runs?per_page=100" \
            | python3 -c 'import json,sys; runs={r["name"]:r for r in json.load(sys.stdin)["check_runs"]}; need=["test","smoke"]; bad=[n for n in need if n not in runs or runs[n]["conclusion"]!="success"]; print(" ".join(bad))')"
          if [ -n "${FAILED_OR_MISSING}" ]; then
            echo "CI has not passed for ${DEPLOY_SHA} (not green: ${FAILED_OR_MISSING}). Refusing to deploy." >&2
```

Replace with:

```yaml
            -H "Accept: application/vnd.github+json" \
            "https://api.github.com/repos/jsfpechar-ops/jsfpecharoperations/commits/${DEPLOY_SHA}/check-runs?per_page=100" \
            | python3 -c 'import json,sys; runs={r["name"]:r for r in json.load(sys.stdin)["check_runs"]}; need=["test","smoke","guest-browser","shellcheck","docker","secrets"]; bad=[n for n in need if n not in runs or runs[n]["conclusion"]!="success"]; print(" ".join(bad))')"
          if [ -n "${FAILED_OR_MISSING}" ]; then
            echo "CI has not passed for ${DEPLOY_SHA} (not green: ${FAILED_OR_MISSING}). Refusing to deploy." >&2
```

Why: A54. A failing browser, shellcheck, docker or secrets job used to let the deploy go ahead.

Verify: The six names in `need=[...]` match the job keys in `.github/workflows/ci.yml` (`grep -n '^  [a-z-]*:$' .github/workflows/ci.yml`).

#### T26 Setting a stay back to Active clears its cancelled-with-guests warning

File: `App/app/routes/admin.py`

Action: EDIT

Depends on: T16

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python
            claim.expire_on_cancel(row)
    else:
        current = db.query_one(
            "SELECT apartment_id FROM reservation WHERE id = ?", (reservation_id,)
```

Replace with:

```python
            claim.expire_on_cancel(row)
    else:
        if payload.get("status") == "active":
            alerts.resolve(f"cancelled_with_guests:{reservation_id}")
        current = db.query_one(
            "SELECT apartment_id FROM reservation WHERE id = ?", (reservation_id,)
```

Why: A17. The alert tells the host to do exactly this, so doing it must clear the alert.

Verify: `pt tests/test_admin_route_split.py tests/test_cancelled_with_guests.py` passes.

#### T27 Test the cancelled-with-guests warning

File: `App/tests/test_cancelled_with_guests.py`

Action: CREATE

Depends on: T16

Code:

Full content:

```python
"""A stay cancelled in the calendar after guests filled in forms raises a warning."""
from __future__ import annotations

from app import alerts, db, icalsync


def _stay(now: str, uid: str) -> dict:
    apartment = db.insert("apartment", {"internal_name": f"Flat {uid}", "created_at": now})
    reservation = db.insert(
        "reservation",
        {"apartment_id": apartment, "uid": uid, "date_from": "2030-05-01",
         "date_to": "2030-05-03", "status": "cancelled", "created_at": now, "updated_at": now},
    )
    return db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation,))


def _guest(reservation_id: int, state: str, now: str) -> None:
    db.insert(
        "guest",
        {"reservation_id": reservation_id, "surname": "Form", "first_name": "Filled",
         "nationality": "GBR", "submit_state": state, "created_at": now, "updated_at": now},
    )


def test_pending_guests_raise_the_warning_and_reactivation_clears_it():
    db.init_db()
    now = db.utcnow()
    stay = _stay(now, "cwg-1")
    _guest(stay["id"], "pending", now)
    icalsync._warn_if_guests_registered(stay, stay["apartment_id"], "cancelled")
    key = f"cancelled_with_guests:{stay['id']}"
    assert alerts.open_alert(key)
    alerts.resolve(key)
    assert not alerts.open_alert(key)


def test_guests_the_police_never_expect_raise_nothing():
    db.init_db()
    now = db.utcnow()
    stay = _stay(now, "cwg-2")
    _guest(stay["id"], "not_required", now)
    icalsync._warn_if_guests_registered(stay, stay["apartment_id"], "cancelled")
    assert not alerts.open_alert(f"cancelled_with_guests:{stay['id']}")
```

Why: A17 regression test.

Verify: `pt tests/test_cancelled_with_guests.py` passes.

#### T28 Test the guest export audit trail

File: `App/tests/test_dsr_audit.py`

Action: CREATE

Depends on: T06

Code:

Full content:

```python
"""A guest's data export carries that guest's audit trail and nobody else's."""
from __future__ import annotations

from app import db, dsr


def test_the_export_matches_every_audit_format_for_this_guest_only():
    db.init_db()
    now = db.utcnow()
    owner = db.insert(
        "user_account",
        {"username": "dsr-owner", "password_hash": "x", "role": "host", "created_at": now},
    )
    apartment = db.insert(
        "apartment", {"internal_name": "DSR flat", "owner_user_id": owner, "created_at": now}
    )
    reservation = db.insert(
        "reservation",
        {"apartment_id": apartment, "uid": "dsr-1", "date_from": "2026-01-01",
         "date_to": "2026-01-03", "status": "active", "created_at": now, "updated_at": now},
    )
    guest = db.insert(
        "guest",
        {"reservation_id": reservation, "surname": "Export", "first_name": "Me",
         "nationality": "GBR", "created_at": now, "updated_at": now},
    )
    other = guest * 10 + 7  # shares a prefix with this guest's id
    for action, detail, who in (
        ("passport_photo_viewed", f"guest_id={guest}", owner),
        ("guest_updated", f"id={guest} by=host", owner),
        ("guest_form_saved", f"guest={guest} reservation={reservation}", owner),
        ("guest_updated", f"id={other} by=host", owner),
        ("apartment_updated", f"id={guest}", owner),
        ("passport_photo_viewed", f"guest_id={guest}", None),
    ):
        db.audit(action, detail, owner_user_id=who)
    actions = [row["action"] for row in dsr.guest_export(guest)["audit"]]
    assert actions == ["passport_photo_viewed", "guest_updated", "guest_form_saved"]
```

Why: A37 regression test: all three detail formats match, other guests and other tenants never do.

Verify: `pt tests/test_dsr_audit.py` passes.

#### T29 Test calendar UTF-8 and BOM handling

File: `App/tests/test_feed_dns_pinning.py`

Action: EDIT

Depends on: T18

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python
    with pytest.raises(CalendarFetchError, match="Could not download the calendar"):
        fetch_calendar_text("http://dead.example:1/calendar.ics")
```

Replace with:

```python
    with pytest.raises(CalendarFetchError, match="Could not download the calendar"):
        fetch_calendar_text("http://dead.example:1/calendar.ics")


def test_a_calendar_is_read_as_utf8_and_loses_its_bom(monkeypatch):
    """No charset means UTF-8, not Latin-1; a BOM never reaches the parser."""
    _allow_local_servers(monkeypatch, "feed.example")
    payload = "﻿BEGIN:VCALENDAR\r\nSUMMARY:Novák Šťastný\r\nEND:VCALENDAR\r\n".encode()

    class Plain(_Routes):
        body = payload

    class Declared(_Routes):
        body = payload

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/calendar; charset=utf-8")
            self.send_header("Content-Length", str(len(self.body)))
            self.end_headers()
            self.wfile.write(self.body)

    plain = _serve(Plain, "127.0.0.1", 0)
    declared = _serve(Declared, "127.0.0.1", 0)
    try:
        for server in (plain, declared):
            text = fetch_calendar_text(f"http://feed.example:{server.server_port}/calendar.ics")
            assert text.startswith("BEGIN:VCALENDAR")
            assert "Novák Šťastný" in text
    finally:
        _stop(plain, declared)
```

Why: A20 regression test.

Verify: `pt tests/test_feed_dns_pinning.py` passes.

#### T30 Production env template lists the backup recipient as required

File: `deploy/lightsail/.env.example`

Action: EDIT

Depends on: T24

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```
# offline (owner's password manager + one offline copy) and never on the server.
# Generate it with:  age-keygen -o ubyhost-backup.agekey
# UBYHOST_BACKUP_AGE_RECIPIENT=age1...
# Time-based retention for local snapshots (days); the newest is always kept.
UBYHOST_BACKUP_RETENTION_DAYS=30
```

Replace with:

```
# offline (owner's password manager + one offline copy) and never on the server.
# Generate it with:  age-keygen -o ubyhost-backup.agekey
# Required in production: preflight.sh refuses to deploy while it is empty.
UBYHOST_BACKUP_AGE_RECIPIENT=
# Time-based retention for local snapshots (days); the newest is always kept.
UBYHOST_BACKUP_RETENTION_DAYS=30
```

Why: A52. A fresh production setup must not stop at preflight without saying why.

Verify: `grep -n UBYHOST_BACKUP_AGE_RECIPIENT deploy/lightsail/.env.example` shows the uncommented key and the comment.

#### T31 Stay fee period can be computed at a given rate. HIGH RISK (filing)

File: `App/app/stay_fee.py`

Action: EDIT

Depends on: T05

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```python
    live_only: bool = False,
    cadence: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Figures for one property and the period (of its cadence) containing month."""
    chosen = cadence if cadence in CADENCES else cadence_of(apartment)
    if not live_only:
```

Replace with:

```python
    live_only: bool = False,
    cadence: Optional[str] = None,
    rate: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Figures for one property and the period (of its cadence) containing month.

    ``rate`` overrides the property's current rate: a correction recalculates a
    sealed period at the rate it was sealed with, not at today's rate.
    """
    chosen = cadence if cadence in CADENCES else cadence_of(apartment)
    if not live_only:
```

Edit 2 of 2. Find (exactly once):

```python
        return None
    first, last = period_bounds(chosen, month)
    rate = int(apartment["stay_fee_rate_czk"])
    lines: List[Dict[str, Any]] = []
    for row in db.query(_GUESTS_SQL, (apartment["id"], last.isoformat(), first.isoformat())):
```

Replace with:

```python
        return None
    first, last = period_bounds(chosen, month)
    rate = int(apartment["stay_fee_rate_czk"]) if rate is None else int(rate)
    lines: List[Dict[str, Any]] = []
    for row in db.query(_GUESTS_SQL, (apartment["id"], last.isoformat(), first.isoformat())):
```

Why: Owner decision Q1. A correction must use the rate the period was sealed with, not today's property rate. Risk: changes the amount in a filed hlášení.

Verify: After T34.

#### T32 A correction uses the sealed rate. HIGH RISK (filing)

File: `App/app/routes/stay_fees.py`

Action: EDIT

Depends on: T03, T31

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```python
            live_only=True,
            cadence=sealed["cadence"],
        )
    else:
```

Replace with:

```python
            live_only=True,
            cadence=sealed["cadence"],
            rate=sealed["rate_czk"],
        )
    else:
```

Edit 2 of 2. Find (exactly once):

```python
        calc_month = month
    period = stay_fee.property_period(
        apartment, calc_month, live_only=True, cadence=cadence
    )
    group = stay_fee.report_group(
```

Replace with:

```python
        calc_month = month
    period = stay_fee.property_period(
        apartment, calc_month, live_only=True, cadence=cadence,
        rate=sealed["rate_czk"] if correcting else None,
    )
    group = stay_fee.report_group(
```

Why: Owner decision Q1. The detail view and finalize both pass the sealed period's rate when correcting.

Verify: After T34.

#### T33 Saving a period computes it at the stored rate. HIGH RISK (filing)

File: `App/app/stay_fee_filing.py`

Action: EDIT

Depends on: T31

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python
    """
    chosen = cadence if cadence in stay_fee.CADENCES else stay_fee.cadence_of(apartment)
    period = stay_fee.property_period(apartment, month, live_only=True, cadence=chosen)
    if period is None:
        raise ValueError("inactive property")
```

Replace with:

```python
    """
    chosen = cadence if cadence in stay_fee.CADENCES else stay_fee.cadence_of(apartment)
    period = stay_fee.property_period(
        apartment, month, live_only=True, cadence=chosen, rate=rate_czk
    )
    if period is None:
        raise ValueError("inactive property")
```

Why: Owner decision Q1. The saved snapshot and its stored rate_czk can no longer disagree.

Verify: After T34.

#### T34 Test a correction keeps the sealed rate

File: `App/tests/test_stay_fee_finalize.py`

Action: EDIT

Depends on: T31, T32, T33

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
```

Replace with:

```python
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")


def test_a_correction_keeps_the_rate_the_period_was_sealed_with(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    _stay(apartment_id)
    guest_id = db.query_one("SELECT id FROM guest ORDER BY id DESC")["id"]
    saved = client.post(
        f"/stay-fees/{apartment_id}/finalize",
        data={
            "_csrf": _csrf(client, f"/stay-fees/{apartment_id}?month=2026-08"),
            "month": "2026-08",
            "confirm_collected": "1",
            f"collected_{guest_id}": "200",
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303
    first = stay_fee_filing.latest(apartment_id, "2026-08")
    db.update("apartment", apartment_id, {"stay_fee_rate_czk": 90})
    corrected = client.post(
        f"/stay-fees/{apartment_id}/finalize",
        data={
            "_csrf": _csrf(client, f"/stay-fees/{apartment_id}?month=2026-08&correct=1"),
            "month": "2026-08",
            "correct": "1",
            "confirm_collected": "1",
            f"collected_{guest_id}": "200",
        },
        follow_redirects=False,
    )
    assert corrected.status_code == 303
    second = stay_fee_filing.latest(apartment_id, "2026-08")
    assert second["id"] != first["id"]
    assert second["rate_czk"] == first["rate_czk"] == 50
    assert second["total_due_czk"] == first["total_due_czk"]
```

Why: Q1 regression test: the property rate changes after sealing, the correction still uses the old rate.

Verify: `pt tests/test_stay_fee_finalize.py tests/test_stay_fee.py` passes.

#### T35 Invoices store a note, immutable once issued

File: `App/app/db.py`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 3. Find (exactly once):

```python
    paid_on              TEXT,
    paid_via             TEXT,
    seller_name TEXT NOT NULL, seller_seat TEXT NOT NULL, seller_ico TEXT, seller_dic TEXT,
    seller_registry TEXT, seller_bank_account TEXT, seller_iban TEXT, seller_bic TEXT,
```

Replace with:

```python
    paid_on              TEXT,
    paid_via             TEXT,
    note                 TEXT,
    seller_name TEXT NOT NULL, seller_seat TEXT NOT NULL, seller_ico TEXT, seller_dic TEXT,
    seller_registry TEXT, seller_bank_account TEXT, seller_iban TEXT, seller_bic TEXT,
```

Edit 2 of 3. Find (exactly once):

```python
    pdf_blob, pdf_sha256, issued_at, issued_by
ON invoice
WHEN OLD.issued_at IS NOT NULL
BEGIN
```

Replace with:

```python
    pdf_blob, pdf_sha256, issued_at, issued_by
ON invoice
WHEN OLD.issued_at IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'invoice is issued and immutable');
END;

-- The note came later; a separate trigger, because CREATE TRIGGER IF NOT
-- EXISTS never updates the column list of invoice_issued_guard.
CREATE TRIGGER IF NOT EXISTS invoice_note_guard
BEFORE UPDATE OF note ON invoice
WHEN OLD.issued_at IS NOT NULL
BEGIN
```

Edit 3 of 3. Find (exactly once):

```python
    # BE-10: workspace termination.
    ("user_account", "deletion_due_at", "TEXT"),
    # Stay-fee remittance, host only
    # (docs/plans/stay-fee-remittance/PLAN_STAY_FEE_REMITTANCE.md).
```

Replace with:

```python
    # BE-10: workspace termination.
    ("user_account", "deletion_due_at", "TEXT"),
    # The free-text note printed on an invoice.
    ("invoice", "note", "TEXT"),
    # Stay-fee remittance, host only
    # (docs/plans/stay-fee-remittance/PLAN_STAY_FEE_REMITTANCE.md).
```

Why: Owner decision Q3. New column plus a trigger, so an issued note cannot change like the other issued fields.

Verify: After T41.

#### T36 Issuing copies the draft's note

File: `App/app/invoices.py`

Action: EDIT

Depends on: T07, T35

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python
        "paid_on": draft.get("paid_on"),
        "paid_via": draft.get("paid_via"),
        "seller_name": seller["name"],
        "seller_seat": seller["seat"],
```

Replace with:

```python
        "paid_on": draft.get("paid_on"),
        "paid_via": draft.get("paid_via"),
        "note": draft.get("note") or None,
        "seller_name": seller["name"],
        "seller_seat": seller["seat"],
```

Why: Owner decision Q3.

Verify: After T41.

#### T37 Invoice PDF prints the note and can refuse an overfull page

File: `App/app/invoice_pdf.py`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 3. Find (exactly once):

```python


def render(inv: dict, items: list, lang: str = "cs", preview: bool = False) -> bytes:
    L = LABELS[lang]
    payer = inv["vat_status"] == "payer"
```

Replace with:

```python


class TooLong(ValueError):
    """The content would run into the footer: an issued PDF must be one clean page."""


def too_long(inv: dict, items: list, lang: str = "cs") -> bool:
    try:
        render(inv, items, lang, strict=True)
    except TooLong:
        return True
    return False


def render(
    inv: dict, items: list, lang: str = "cs", preview: bool = False, strict: bool = False
) -> bytes:
    L = LABELS[lang]
    payer = inv["vat_status"] == "payer"
```

Edit 2 of 3. Find (exactly once):

```python
        for rate, (b, v, g) in sorted(rates.items()):
            _text(c, M, yy, f"{rate} %", size=8.5, color=INK_2)
            _text(c, M + 38 * mm, yy, f"{L['base']} {money(b)}", size=8.5, color=INK_2, right=True)
            _text(c, M + 70 * mm, yy, f"{L['vat']} {money(v)}", size=8.5, color=INK_2, right=True)
            yy -= 4.5 * mm
    paid = bool(inv.get("paid_on"))
```

Replace with:

```python
        for rate, (b, v, g) in sorted(rates.items()):
            _text(c, M, yy, f"{rate} %", size=8.5, color=INK_2)
            # Right edges leave room for "Základ 99 999,99 Kč" after the rate.
            _text(c, M + 50 * mm, yy, f"{L['base']} {money(b)}", size=8.5, color=INK_2, right=True)
            _text(c, M + 84 * mm, yy, f"{L['vat']} {money(v)}", size=8.5, color=INK_2, right=True)
            yy -= 4.5 * mm
    paid = bool(inv.get("paid_on"))
```

Edit 3 of 3. Find (exactly once):

```python
    if kind == "corrective" and inv.get("correction_date"):
        ny = _wrap(c, M, ny, f"{L['correction_date']}: {cz_date(inv['correction_date'])}", CW, size=8.5, color=INK_2)
    if not payer:
        ny = _wrap(c, M, ny, L["non_payer"], CW, size=8.5, color=INK_2)

    fy2 = M + 10 * mm
    reg = inv.get("seller_registry") or ""
    contact = "   ·   ".join(p for p in [inv.get("seller_email"), inv.get("seller_phone")] if p)
```

Replace with:

```python
    if kind == "corrective" and inv.get("correction_date"):
        ny = _wrap(c, M, ny, f"{L['correction_date']}: {cz_date(inv['correction_date'])}", CW, size=8.5, color=INK_2)
    if inv.get("note"):
        ny = _wrap(c, M, ny, inv["note"], CW, size=8.5, color=INK_2)
    if not payer:
        ny = _wrap(c, M, ny, L["non_payer"], CW, size=8.5, color=INK_2)

    fy2 = M + 10 * mm
    # ny is the next baseline; the last line's descenders sit about 2 mm above
    # it, and the registry line's cap height reaches about 7 mm above fy2.
    if strict and ny + 2 * mm < fy2 + 7 * mm:
        raise TooLong()
    reg = inv.get("seller_registry") or ""
    contact = "   ·   ".join(p for p in [inv.get("seller_email"), inv.get("seller_phone")] if p)
```

Why: Owner decision Q3. The invoice must stay one page. Strict mode raises TooLong instead of drawing over the footer. Also fixes the VAT recap overlapping its label ('12 %Základ').

Verify: After T41.

#### T38 Issuing refuses an invoice that does not fit one page

File: `App/app/routes/invoices.py`

Action: EDIT

Depends on: T10, T36, T37

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```python
        "paid_on": draft.get("paid_on"),
        "paid_via_label": invoices.custom_paid_via_label(draft.get("paid_via")),
        "seller_name": seller["name"],
        "seller_seat": seller["seat"],
```

Replace with:

```python
        "paid_on": draft.get("paid_on"),
        "paid_via_label": invoices.custom_paid_via_label(draft.get("paid_via")),
        "note": draft.get("note"),
        "seller_name": seller["name"],
        "seller_seat": seller["seat"],
```

Edit 2 of 2. Find (exactly once):

```python
    draft = _draft(request, entity, form)
    issues = invoices.validate_for_issue(draft)
    if issues:
        lang = _lang(request)
```

Replace with:

```python
    draft = _draft(request, entity, form)
    issues = invoices.validate_for_issue(draft)
    if not issues and invoices.invoice_pdf.too_long(_preview_view(draft), draft["items"], draft["lang"]):
        issues = [invoices.validation.Issue("note", "invoice.err.too_long")]
    if issues:
        lang = _lang(request)
```

Why: Owner decision Q3. The host gets a clear message instead of a broken immutable PDF.

Verify: After T41.

#### T39 Invoice page shows the note

File: `App/app/templates/invoice_detail.html`

Action: EDIT

Depends on: T35

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```html
    </table>
  </div>
  </div>{# /invoice-document #}

```

Replace with:

```html
    </table>
  </div>
  {% if invoice.note %}
  <p class="small muted"><strong>{{ t('invoice.note') }}:</strong> {{ invoice.note }}</p>
  {% endif %}
  </div>{# /invoice-document #}

```

Why: Owner decision Q3.

Verify: After T41.

#### T40 Message for an invoice that does not fit (EN/CS)

File: `App/app/host_i18n.py`

Action: EDIT

Depends on: T21, T38

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```python
        "error.home": "Back to UbyHost",
        "invoice.err.too_many_items": "An invoice can have at most 4 line items. Combine items or issue a second invoice.",
        "invoice.err.seller_name": "The operator needs a name.",
        "flash.error.no_such_invoice": "No such invoice.",
```

Replace with:

```python
        "error.home": "Back to UbyHost",
        "invoice.err.too_many_items": "An invoice can have at most 4 line items. Combine items or issue a second invoice.",
        "invoice.err.too_long": "This invoice does not fit on one page. Shorten the note or the item descriptions, or use fewer items.",
        "invoice.err.seller_name": "The operator needs a name.",
        "flash.error.no_such_invoice": "No such invoice.",
```

Edit 2 of 2. Find (exactly once):

```python
        "error.home": "Zpět do UbyHost",
        "invoice.err.too_many_items": "Faktura může mít nejvýše 4 položky. Položky sloučte, nebo vystavte druhou fakturu.",
        "invoice.err.seller_name": "Provozovatel musí mít název.",
        "flash.error.no_such_invoice": "Faktura nenalezena.",
```

Replace with:

```python
        "error.home": "Zpět do UbyHost",
        "invoice.err.too_many_items": "Faktura může mít nejvýše 4 položky. Položky sloučte, nebo vystavte druhou fakturu.",
        "invoice.err.too_long": "Faktura se nevejde na jednu stránku. Zkraťte poznámku nebo popisy položek, nebo použijte méně položek.",
        "invoice.err.seller_name": "Provozovatel musí mít název.",
        "flash.error.no_such_invoice": "Faktura nenalezena.",
```

Why: Owner decision Q3. `invoice.err.too_long` in both languages.

Verify: `pt tests/test_host_i18n.py` passes.

#### T41 Test the invoice note

File: `App/tests/test_invoice_pdf.py`

Action: EDIT

Depends on: T09, T35, T36, T37, T38, T40

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python
    keys = [issue.message for issue in invoices.validate_for_issue(draft)]
    assert "invoice.err.amount" in keys
```

Replace with:

```python
    keys = [issue.message for issue in invoices.validate_for_issue(draft)]
    assert "invoice.err.amount" in keys


def test_the_note_is_printed_and_an_overfull_page_is_refused():
    import io as _io

    import pdfplumber

    inv = _inv(note="Děkujeme za pobyt.")
    data = invoice_pdf.render(inv, [dict(ACCOM, vat_rate=None, base_haler=None, vat_haler=None)], "cs")
    with pdfplumber.open(_io.BytesIO(data)) as pdf:
        assert "Děkujeme za pobyt." in pdf.pages[0].extract_text()
    long_desc = "Ubytování v apartmánu s dlouhým popisem, který se zalomí na dva řádky v tabulce položek faktury"
    payer = _inv(vat_status="payer", seller_dic="CZ04656679", note="Děkujeme za pobyt. " * 5)
    items = [dict(ACCOM, description=long_desc)] * 4
    assert invoice_pdf.too_long(payer, items, "cs")
    assert not invoice_pdf.too_long(dict(payer, note=""), items, "cs")


def test_an_issued_note_cannot_be_changed():
    import sqlite3

    import pytest

    from app import db

    db.init_db()
    now = db.utcnow()
    entity = db.insert("legal_entity", {"name": "Note s.r.o.", "created_at": now})
    invoice = db.insert(
        "invoice",
        {
            "legal_entity_id": entity, "kind": "invoice", "seq_year": 2026, "seq_no": 7001,
            "number": "NOTE-1", "vs": "1", "lang": "cs", "vat_status": "non_payer",
            "issue_date": "2026-01-01", "seller_name": "S", "seller_seat": "P",
            "buyer_name": "B", "total_haler": 100, "note": "Původní", "issued_at": now,
            "created_at": now,
        },
    )
    with pytest.raises(sqlite3.DatabaseError, match="immutable"):
        db.execute("UPDATE invoice SET note = 'Jiná' WHERE id = ?", (invoice,))
```

Why: Q3 regression tests: the note is printed, an overfull page is refused, an issued note cannot change.

Verify: `pt tests/test_invoice_pdf.py tests/test_invoice_ux.py` passes.

#### T42 auth.end_all_sessions

File: `App/app/auth.py`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python


def set_account_password(user_id: int, password: str, must_change: bool = False) -> None:
    error = password_error(password)
```

Replace with:

```python


def end_all_sessions(user_id: int) -> None:
    """Retire every session cookie issued for this account, on every device."""
    db.execute(
        "UPDATE user_account SET session_version = session_version + 1 WHERE id = ?",
        (user_id,),
    )


def set_account_password(user_id: int, password: str, must_change: bool = False) -> None:
    error = password_error(password)
```

Why: Owner decision Q4. Bumping session_version invalidates every cookie of the account.

Verify: After T44.

#### T43 Log out signs out every device

File: `App/app/routes/admin_accounts.py`

Action: EDIT

Depends on: T42

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python

@router.post("/logout")
def logout():
    response = RedirectResponse("/login?notice=logged_out", status_code=303)
    auth.clear_session(response)
```

Replace with:

```python

@router.post("/logout")
def logout(request: Request):
    # Cookies are signed, not stored, so clearing this browser's copy alone
    # would leave a copied cookie valid. Log out ends the account's sessions
    # everywhere (the real account, also when an admin is impersonating).
    account = auth.current_user(request)
    if account:
        auth.end_all_sessions(account["id"])
        db.audit("logout", actor=account["username"], owner_user_id=account["id"])
    response = RedirectResponse("/login?notice=logged_out", status_code=303)
    auth.clear_session(response)
```

Why: Owner decision Q4. A stolen or forgotten session ends when the host logs out anywhere. The logout is audited.

Verify: After T44.

#### T44 Test log out everywhere

File: `App/tests/test_logout_everywhere.py`

Action: CREATE

Depends on: T43

Code:

Full content:

```python
"""Log out ends the account's sessions on every device, not only this browser."""
from __future__ import annotations

import secrets

from fastapi.testclient import TestClient

from app import auth, db
from app.main import app

PASSWORD = f"Logout-everywhere-{secrets.token_urlsafe(12)}-7"


def _signed_in(username: str) -> TestClient:
    client = TestClient(app)
    response = client.post(
        "/login?lang=en", data={"username": username, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client


def test_logging_out_on_one_device_signs_out_the_other():
    db.init_db()
    username = f"logout-{secrets.token_hex(4)}"
    auth.create_account(username, PASSWORD, "Logout Host", role="host", must_change_password=False)
    laptop, phone = _signed_in(username), _signed_in(username)
    copied = dict(phone.cookies)
    assert phone.get("/reservations", follow_redirects=False).status_code == 200

    assert laptop.post("/logout", follow_redirects=False).status_code == 303

    assert phone.get("/reservations", follow_redirects=False).status_code in (302, 303)
    replay = TestClient(app, cookies=copied)
    assert replay.get("/reservations", follow_redirects=False).status_code in (302, 303)
```

Why: Q4 regression test: a second client is signed out by the first one's logout. It fails on the old code.

Verify: `pt tests/test_logout_everywhere.py tests/test_accounts.py` passes.

#### T45 A locked guest link asks for the Turnstile check instead of refusing everyone

File: `App/app/routes/guest.py`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 5. Find (exactly once):

```python
        {
            "error": error,
            "require_turnstile": failures >= 3,
            "return_to": request.url.path
            + (("?" + str(request.url.query)) if request.url.query else ""),
```

Replace with:

```python
        {
            "error": error,
            "require_turnstile": failures >= 3 or _link_challenged(token, apartment),
            "return_to": request.url.path
            + (("?" + str(request.url.query)) if request.url.query else ""),
```

Edit 2 of 5. Find (exactly once):

```python
    )
    return _with_lang(render_guest(request, "guest/pin.html", context), lang)


```

Replace with:

```python
    )
    return _with_lang(render_guest(request, "guest/pin.html", context), lang)


def _link_challenged(token: str, apartment) -> bool:
    """A link guessed at from many addresses asks every visitor for the check.

    With Turnstile on, a locked link is challenged rather than refused, so one
    person with an old link cannot shut every guest out for a day.
    """
    if not apartment or not turnstile.required():
        return False
    expected = apartment["permalink_pin"] or ""
    return rate_limit.pin_token_blocked(f"{token}:{auth.pin_fingerprint(token, expected)}")


```

Edit 3 of 5. Find (exactly once):

```python
    pin_key = rate_limit.client_key(request, token)
    pin_lock_key = f"{token}:{auth.pin_fingerprint(token, expected)}"
    if rate_limit.pin_token_blocked(pin_lock_key):
        return _pin_page(
            request,
```

Replace with:

```python
    pin_key = rate_limit.client_key(request, token)
    pin_lock_key = f"{token}:{auth.pin_fingerprint(token, expected)}"
    link_locked = rate_limit.pin_token_blocked(pin_lock_key)
    if link_locked and not turnstile.required():
        return _pin_page(
            request,
```

Edit 4 of 5. Find (exactly once):

```python
            error=i18n.translator(lang)("pin_locked_out"),
        )
    if rate_limit.pin_failure_count(pin_key) >= 3 and not turnstile.verify(
        request, form.get("cf-turnstile-response"), "guest_pin"
    ):
```

Replace with:

```python
            error=i18n.translator(lang)("pin_locked_out"),
        )
    if (link_locked or rate_limit.pin_failure_count(pin_key) >= 3) and not turnstile.verify(
        request, form.get("cf-turnstile-response"), "guest_pin"
    ):
```

Edit 5 of 5. Find (exactly once):

```python
        # so the host is told the moment the link itself burns its budget: every
        # guest using it is refused for a day until the PIN is rotated.
        if rate_limit.pin_token_blocked(pin_lock_key):
            alerts.raise_alert(
                "critical",
```

Replace with:

```python
        # so the host is told the moment the link itself burns its budget: every
        # guest using it is refused for a day until the PIN is rotated.
        if rate_limit.pin_token_blocked(pin_lock_key) and turnstile.required():
            alerts.raise_alert(
                "warning",
                "guest_pin_challenged",
                "Guest link now asks for a security check after repeated wrong PINs.",
                detail="Guests can still open it after the check. Generate a new PIN if the link may have leaked.",
                dedupe_key=f"guest_pin_challenged:{apartment['id']}",
                apartment_id=apartment["id"],
            )
            db.audit(
                "guest_pin_token_challenged",
                detail=f"apartment={apartment['id']}",
                actor="anonymous",
                owner_user_id=apartment["owner_user_id"],
            )
        elif rate_limit.pin_token_blocked(pin_lock_key):
            alerts.raise_alert(
                "critical",
```

Why: Owner decision Q5. The 24 h link lock let anyone lock a real guest out by guessing from many addresses. With Turnstile configured the link stays usable after the check; without Turnstile the old lock stays.

Verify: After T47.

#### T46 Copy for the challenged-link alert (EN/CS)

File: `App/app/host_i18n.py`

Action: EDIT

Depends on: T40, T45

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```python
        "notification.guest_pin_locked_out.title": "Guest link locked out for 24 hours after repeated wrong PINs.",
        "notification.guest_pin_locked_out.detail": "Every guest using this link is refused until you generate a new PIN. The lockout followed attempts spread over many addresses, so the link itself is being guessed at.",
        # Host flash messages. `back()` carries them through the query string,
        # so they are translated where they are raised, not where they render.
```

Replace with:

```python
        "notification.guest_pin_locked_out.title": "Guest link locked out for 24 hours after repeated wrong PINs.",
        "notification.guest_pin_locked_out.detail": "Every guest using this link is refused until you generate a new PIN. The lockout followed attempts spread over many addresses, so the link itself is being guessed at.",
        "notification.guest_pin_challenged.title": "Guest link now asks for a security check after repeated wrong PINs.",
        "notification.guest_pin_challenged.detail": "Guests can still open it after the check. The wrong PINs came from many addresses; generate a new PIN if the link may have leaked.",
        # Host flash messages. `back()` carries them through the query string,
        # so they are translated where they are raised, not where they render.
```

Edit 2 of 2. Find (exactly once):

```python
        "notification.guest_pin_locked_out.title": "Hostovský odkaz je po opakovaných chybných PINech zablokován na 24 hodin.",
        "notification.guest_pin_locked_out.detail": "Dokud nevygenerujete nový PIN, žádný host se přes tento odkaz nedostane. Pokusy přicházely z mnoha adres, takže se někdo snaží hádat PIN k odkazu.",
        "flash.demo.loaded": "Demo ubytování bylo načteno. Až budete hotovi, použijte v Přehledu „Vymazat demo data“.",
        "flash.demo.cleared": "Demo data byla vymazána.",
```

Replace with:

```python
        "notification.guest_pin_locked_out.title": "Hostovský odkaz je po opakovaných chybných PINech zablokován na 24 hodin.",
        "notification.guest_pin_locked_out.detail": "Dokud nevygenerujete nový PIN, žádný host se přes tento odkaz nedostane. Pokusy přicházely z mnoha adres, takže se někdo snaží hádat PIN k odkazu.",
        "notification.guest_pin_challenged.title": "Hostovský odkaz po opakovaných chybných PINech vyžaduje bezpečnostní kontrolu.",
        "notification.guest_pin_challenged.detail": "Hosté se přes odkaz po kontrole stále dostanou. Chybné PINy přicházely z mnoha adres; pokud mohl odkaz uniknout, vygenerujte nový PIN.",
        "flash.demo.loaded": "Demo ubytování bylo načteno. Až budete hotovi, použijte v Přehledu „Vymazat demo data“.",
        "flash.demo.cleared": "Demo data byla vymazána.",
```

Why: Owner decision Q5.

Verify: `pt tests/test_host_i18n.py` passes.

#### T47 Test a locked link is challenged

File: `App/tests/test_guest_pin.py`

Action: EDIT

Depends on: T45, T46

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python
        db.execute("DELETE FROM rate_limit_event WHERE key LIKE ?", (f"%:{TOKEN}",))
        _cleanup()
```

Replace with:

```python
        db.execute("DELETE FROM rate_limit_event WHERE key LIKE ?", (f"%:{TOKEN}",))
        _cleanup()


def test_with_turnstile_a_locked_link_is_challenged_not_refused(pin_required, monkeypatch):
    """One person with an old link must not shut every guest out for a day."""
    from app import turnstile

    _stay_id()
    monkeypatch.setattr("app.routes.guest.asyncio.sleep", AsyncMock())
    monkeypatch.setattr(turnstile, "required", lambda: True)
    monkeypatch.setattr(turnstile, "verify", lambda _request, token, _action: token == "human")
    try:
        db.execute("DELETE FROM rate_limit_event WHERE key LIKE ?", (f"%:{TOKEN}",))
        for attempt in range(rate_limit._PIN_TOKEN_MAX_FAILURES):
            TestClient(app, client=(f"10.0.0.{attempt}", 50000)).post(
                f"/l/{TOKEN}/pin",
                data={"pin": "000000", "cf-turnstile-response": "human", "return_to": f"/l/{TOKEN}"},
                follow_redirects=False,
            )
        assert rate_limit.pin_token_blocked(f"{TOKEN}:{auth.pin_fingerprint(TOKEN, PIN)}")

        guest = TestClient(app, client=("10.0.1.1", 50000))
        unchecked = guest.post(
            f"/l/{TOKEN}/pin", data={"pin": PIN, "return_to": f"/l/{TOKEN}"},
            follow_redirects=False,
        )
        assert unchecked.status_code == 200, "a locked link still needs the check"
        assert 'name="pin"' in unchecked.text
        checked = guest.post(
            f"/l/{TOKEN}/pin",
            data={"pin": PIN, "cf-turnstile-response": "human", "return_to": f"/l/{TOKEN}"},
            follow_redirects=False,
        )
        assert checked.status_code == 303
    finally:
        db.execute("DELETE FROM rate_limit_event WHERE key LIKE ?", (f"%:{TOKEN}",))
        db.execute("DELETE FROM rate_limit_event WHERE scope = ?", ("pin_fail_token",))
        _cleanup()
```

Why: Q5 regression test.

Verify: `pt tests/test_guest_pin.py` passes. Then run the guest browser e2e (AGENTS.md).

#### T48 The date-change hold records who had signed. HIGH RISK (filing)

File: `App/app/icalsync.py`

Action: EDIT

Depends on: T16

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```python
                )
                if on_stay and on_stay["n"]:
                    alerts.raise_alert(
                        "critical",
```

Replace with:

```python
                )
                if on_stay and on_stay["n"]:
                    # Who had signed, and when: each of them must sign again
                    # before the hold lifts (routes.guest).
                    signed = {
                        str(row["id"]): row["signed_at"]
                        for row in db.query(
                            "SELECT id, signed_at FROM guest WHERE reservation_id = ? "
                            "AND archived_at IS NULL AND signed_at IS NOT NULL "
                            "AND submit_state != ?",
                            (existing["id"], reporting.SENT),
                        )
                    }
                    alerts.raise_alert(
                        "critical",
```

Edit 2 of 2. Find (exactly once):

```python
                        dedupe_key=f"dates_changed_resign:{existing['id']}",
                        apartment_id=feed["apartment_id"],
                        reservation_id=existing["id"],
                    )
                    log.warning(
                        "ical_dates_changed_resign_required apartment_id=%s reservation_id=%s",
```

Replace with:

```python
                        dedupe_key=f"dates_changed_resign:{existing['id']}",
                        apartment_id=feed["apartment_id"],
                        reservation_id=existing["id"],
                        params={"signed": signed},
                    )
                    log.warning(
                        "ical_dates_changed_resign_required apartment_id=%s reservation_id=%s",
```

Why: Owner decision Q6. The alert stores each earlier signer's signed_at so the hold can tell a fresh signature from an old one. Risk: holds police filing for the stay.

Verify: After T50.

#### T49 The hold lifts only when every earlier signer has signed again. HIGH RISK (filing)

File: `App/app/routes/guest.py`

Action: EDIT

Depends on: T45, T48

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```python
    expected = apartment["permalink_pin"] or ""
    return rate_limit.pin_token_blocked(f"{token}:{auth.pin_fingerprint(token, expected)}")


```

Replace with:

```python
    expected = apartment["permalink_pin"] or ""
    return rate_limit.pin_token_blocked(f"{token}:{auth.pin_fingerprint(token, expected)}")


def clear_resign_when_everyone_signed(reservation_id: int) -> None:
    """Lift the "sign again" hold once every guest who signed has signed again.

    The sync records, in the alert, the signature time of every guest who had
    signed when the dates moved. A guest whose signature time is unchanged
    still holds a form with the old dates, even when the sync moved the row
    onto the new dates (owner decision Q6). The host can still send by hand.
    Alerts raised before that record existed fall back to the date check.
    """
    key = f"dates_changed_resign:{reservation_id}"
    resign = alerts.open_alert(key)
    stay = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))
    if not resign or not stay:
        return
    party = db.query(
        "SELECT * FROM guest WHERE reservation_id = ? AND archived_at IS NULL",
        (reservation_id,),
    )
    if any(reporting.signature_dates_stale(g, stay) for g in party):
        return
    signed_then = alerts.stored_params(dict(resign)).get("signed") or {}
    if any(str(g["id"]) in signed_then and g["signed_at"] == signed_then[str(g["id"])] for g in party):
        return
    alerts.resolve(key)


```

Edit 2 of 2. Find (exactly once):

```python
    # older signature. Resolving on any one guest's save hid the warning while
    # the rest of the party still had the old dates on file.
    filing = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))
    if filing:
        still_stale = db.query(
            "SELECT * FROM guest WHERE reservation_id = ? AND archived_at IS NULL",
            (reservation_id,),
        )
        if not any(reporting.signature_dates_stale(g, filing) for g in still_stale):
            alerts.resolve(f"dates_changed_resign:{reservation_id}")
    await run_in_threadpool(reporting.submit_stay_if_complete, apartment["id"], reservation_id)

```

Replace with:

```python
    # older signature. Resolving on any one guest's save hid the warning while
    # the rest of the party still had the old dates on file.
    clear_resign_when_everyone_signed(reservation_id)
    await run_in_threadpool(reporting.submit_stay_if_complete, apartment["id"], reservation_id)

```

Why: Owner decision Q6. One guest re-signing used to release the whole stay for filing with other signatures still on the old dates.

Verify: After T50.

#### T50 Test the hold waits for every signer

File: `App/tests/test_guest_navigation.py`

Action: EDIT

Depends on: T48, T49

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 3. Find (exactly once):

```python


def test_re_signing_a_moved_stay_clears_the_date_change_alert(monkeypatch):
    """W1.1: the host's warning is stale once the guest signs the new dates."""
    db.init_db()
```

Replace with:

```python


def test_the_date_change_hold_lifts_only_after_every_signer_signs_again(monkeypatch):
    """W1.1: the host's warning is stale once the guest signs the new dates."""
    db.init_db()
```

Edit 2 of 3. Find (exactly once):

```python
        )

        # The next guest to sign the stay signs the moved dates, so the warning
        # that the filed dates moved is stale.
        again = browser.post(
            f"/l/{TOKEN}/{stay}/save",
```

Replace with:

```python
        )

        # The next guest signs the moved dates, but the first guest's form still
        # carries the signature given for the old dates (owner decision Q6).
        again = browser.post(
            f"/l/{TOKEN}/{stay}/save",
```

Edit 3 of 3. Find (exactly once):

```python
            "SELECT COUNT(*) AS n FROM guest WHERE reservation_id = ?", (stay,)
        )["n"] == 2
        assert db.query_one(
            "SELECT resolved_at FROM alert WHERE dedupe_key = ?", (key,)
```

Replace with:

```python
            "SELECT COUNT(*) AS n FROM guest WHERE reservation_id = ?", (stay,)
        )["n"] == 2
        assert not db.query_one(
            "SELECT resolved_at FROM alert WHERE dedupe_key = ?", (key,)
        )["resolved_at"], "one new signature does not stand for the whole party"

        first = db.query_one(
            "SELECT id FROM guest WHERE reservation_id = ? ORDER BY id LIMIT 1", (stay,)
        )["id"]
        db.update("guest", first, {"signed_at": "2999-01-01T00:00:00+00:00"})
        guest.clear_resign_when_everyone_signed(stay)
        assert db.query_one(
            "SELECT resolved_at FROM alert WHERE dedupe_key = ?", (key,)
```

Why: Q6 regression test.

Verify: `pt tests/test_guest_navigation.py tests/test_icalsync.py` passes.

#### T51 Production refuses to start when unsafe or without the operator identity

File: `App/app/env_guard.py`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 3. Find (exactly once):

```python
    domain: Optional[str] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> List[str]:
    """Return warnings. Raise EnvGuardError when starting would be unsafe."""
```

Replace with:

```python
    domain: Optional[str] = None,
    environ: Optional[Mapping[str, str]] = None,
    operator_identity: Optional[Mapping[str, str]] = None,
) -> List[str]:
    """Return warnings. Raise EnvGuardError when starting would be unsafe."""
```

Edit 2 of 3. Find (exactly once):

```python

    if deploy == "production" and not pin:
        warnings.append(
            "UBYHOST_GUEST_PIN is off on production — guest permalinks are unprotected"
        )

```

Replace with:

```python

    if deploy == "production" and not pin:
        raise EnvGuardError(
            "UBYHOST_GUEST_PIN is off on production. Guest permalinks would be "
            "unprotected. Set UBYHOST_GUEST_PIN=1."
        )

```

Edit 3 of 3. Find (exactly once):

```python
    actual_host = public_url_host(base_url)
    if expected_host and actual_host and expected_host != actual_host:
        warnings.append(
            f"UBYHOST_PUBLIC_BASE_URL host {actual_host!r} does not match "
            f"UBYHOST_DOMAIN {expected_host!r} — guest permalinks will be wrong"
        )

    if deploy == "production" and not str(base_url).lower().startswith("https://"):
        warnings.append("UBYHOST_PUBLIC_BASE_URL should use https:// in production")

    try:
```

Replace with:

```python
    actual_host = public_url_host(base_url)
    if expected_host and actual_host and expected_host != actual_host:
        message = (
            f"UBYHOST_PUBLIC_BASE_URL host {actual_host!r} does not match "
            f"UBYHOST_DOMAIN {expected_host!r} — guest permalinks will be wrong"
        )
        if deploy == "production":
            raise EnvGuardError(message)
        warnings.append(message)

    if deploy == "production" and not str(base_url).lower().startswith("https://"):
        raise EnvGuardError("UBYHOST_PUBLIC_BASE_URL must use https:// in production")

    if deploy == "production":
        identity = (
            operator_identity
            if operator_identity is not None
            else {
                "UBYHOST_OPERATOR_NAME": config.OPERATOR_NAME,
                "UBYHOST_OPERATOR_ICO": config.OPERATOR_ICO,
                "UBYHOST_OPERATOR_ADDRESS": config.OPERATOR_ADDRESS,
            }
        )
        missing = [key for key, value in identity.items() if not str(value or "").strip()]
        if missing:
            raise EnvGuardError(
                "The legal notice needs the software operator. Set "
                + ", ".join(missing)
                + " in the production .env."
            )

    try:
```

Why: Owner decision Q8. Guest PIN off, a non-https base URL and a domain mismatch were warnings nobody reads. The legal notice also must name the operator, so an empty name, IČO or address now stops the start. Values live only in the server .env (AGENTS.md: the repo is public).

Verify: After T52.

#### T52 Tests for the production start guard

File: `App/tests/test_env_guard.py`

Action: REPLACE ENTIRE FILE

Depends on: T51

Code:

Full content:

```python
"""Process-start guards: prod never on Render, never without production deployment."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import __version__, config, env_guard
from app.main import app

OPERATOR = {
    "UBYHOST_OPERATOR_NAME": "Example Operator",
    "UBYHOST_OPERATOR_ICO": "12345678",
    "UBYHOST_OPERATOR_ADDRESS": "Example Street 1, Praha",
}


def test_healthz_includes_env_outside_production():
    response = TestClient(app).get("/healthz")
    body = response.json()
    assert response.status_code == 200
    assert body["status"] in {"ok", "degraded"}
    assert body["version"] == __version__ == "1.1.0"
    assert "data_dir_writable" in body
    assert body.get("deployment") == config.DEPLOYMENT
    assert body.get("ubyport_env") == config.UBYPORT_ENV


def test_refuse_prod_without_production_deployment():
    with pytest.raises(env_guard.EnvGuardError, match="requires UBYHOST_DEPLOYMENT=production"):
        env_guard.validate_runtime_env(ubyport_env="prod", deployment="staging")


def test_refuse_prod_on_render_flag():
    with pytest.raises(env_guard.EnvGuardError, match="not allowed on Render"):
        env_guard.validate_runtime_env(
            ubyport_env="prod",
            deployment="production",
            environ={"RENDER": "true"},
        )


def test_refuse_prod_when_public_url_is_onrender():
    with pytest.raises(env_guard.EnvGuardError, match="not allowed on Render"):
        env_guard.validate_runtime_env(
            ubyport_env="prod",
            deployment="production",
            environ={"UBYHOST_PUBLIC_BASE_URL": "https://ubyhost-staging.onrender.com"},
        )


def test_test_endpoint_allowed_on_lightsail_production():
    warnings = env_guard.validate_runtime_env(
        ubyport_env="test",
        deployment="production",
        guest_pin_required=True,
        scheduler_enabled=True,
        public_base_url="https://ubyhost.com",
        domain="ubyhost.com",
        environ={"UBYHOST_MAIL_BACKEND": "disabled"},
        operator_identity=OPERATOR,
    )
    assert warnings == ["guest e-mail is disabled on production"]


def test_prod_allowed_on_lightsail_production():
    warnings = env_guard.validate_runtime_env(
        ubyport_env="prod",
        deployment="production",
        guest_pin_required=True,
        scheduler_enabled=True,
        public_base_url="https://ubyhost.com",
        domain="ubyhost.com",
        environ={"UBYHOST_MAIL_BACKEND": "disabled"},
        operator_identity=OPERATOR,
    )
    assert warnings == ["guest e-mail is disabled on production"]


def _production(**overrides):
    args = dict(
        ubyport_env="test",
        deployment="production",
        guest_pin_required=True,
        scheduler_enabled=True,
        public_base_url="https://ubyhost.com",
        domain="ubyhost.com",
        environ={"UBYHOST_MAIL_BACKEND": "disabled"},
        operator_identity=OPERATOR,
    )
    args.update(overrides)
    return env_guard.validate_runtime_env(**args)


def test_warns_when_scheduler_off():
    assert any("ENABLE_SCHEDULER" in item for item in _production(scheduler_enabled=False))


def test_refuse_production_without_guest_pin():
    with pytest.raises(env_guard.EnvGuardError, match="GUEST_PIN"):
        _production(guest_pin_required=False)


def test_refuse_production_without_https():
    with pytest.raises(env_guard.EnvGuardError, match="https://"):
        _production(public_base_url="http://ubyhost.com")


def test_refuse_production_when_public_url_host_mismatches_domain():
    with pytest.raises(env_guard.EnvGuardError, match="does not match"):
        _production(public_base_url="https://wrong.example")


def test_staging_only_warns_when_public_url_host_mismatches_domain():
    warnings = env_guard.validate_runtime_env(
        ubyport_env="mock",
        deployment="staging",
        public_base_url="https://wrong.example",
        domain="ubyhost.com",
        environ={},
    )
    assert any("does not match" in item for item in warnings)


def test_refuse_production_without_operator_identity():
    with pytest.raises(env_guard.EnvGuardError, match="UBYHOST_OPERATOR_ICO"):
        _production(operator_identity={**OPERATOR, "UBYHOST_OPERATOR_ICO": " "})


def test_invalid_ubyport_env():
    with pytest.raises(env_guard.EnvGuardError, match="invalid"):
        env_guard.validate_runtime_env(ubyport_env="live", deployment="production")


def test_refuse_ses_mail_on_staging():
    with pytest.raises(env_guard.EnvGuardError, match="only allowed on production"):
        env_guard.validate_runtime_env(
            ubyport_env="mock",
            deployment="staging",
            environ={"UBYHOST_MAIL_BACKEND": "ses"},
        )


def test_console_mail_is_allowed_on_staging():
    warnings = env_guard.validate_runtime_env(
        ubyport_env="mock",
        deployment="staging",
        environ={"UBYHOST_MAIL_BACKEND": "console"},
    )
    assert not any("MAIL_BACKEND" in item for item in warnings)


def test_refuse_production_on_mock_by_default():
    with pytest.raises(env_guard.EnvGuardError, match="nothing to the police"):
        env_guard.validate_runtime_env(
            ubyport_env="mock",
            deployment="production",
            environ={},
        )


def test_production_mock_allowed_with_explicit_opt_in():
    warnings = env_guard.validate_runtime_env(
        ubyport_env="mock",
        deployment="production",
        guest_pin_required=True,
        public_base_url="https://ubyhost.com",
        domain="ubyhost.com",
        environ={"UBYHOST_ALLOW_PROD_MOCK": "1"},
        operator_identity=OPERATOR,
    )
    assert any("nothing is reported" in item for item in warnings)
```

Why: Q8. The old warning tests become refusal tests; staging still only warns.

Verify: `pt tests/test_env_guard.py tests/test_security.py` passes.

#### T53 Docs: what production refuses

File: `docs/ENVIRONMENT.md`

Action: EDIT

Depends on: T51

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 3. Find (exactly once):

```markdown
| --- | --- | --- |
| `UBYHOST_PUBLIC_BASE_URL` | `http://127.0.0.1:8080` | Used to build guest permalinks, to match `Origin`/`Referer` on host POSTs, and to decide whether guest cookies get the `Secure` flag. If this is wrong, guest links point at the wrong host and the ownership/claim cookies may be issued without `Secure`. |
| `UBYHOST_DOMAIN` | unset | Expected public hostname. Only used by the startup guard, which warns when it disagrees with `PUBLIC_BASE_URL`. |
| `UBYHOST_GUEST_PIN` | `1` | `0` removes the PIN gate from every guest route, leaving the permalink token as the only barrier. A production deployment with this off gets a startup warning. |
| `UBYHOST_GUEST_NOTICE_VERSION` | `1.0` | Version stamped on a guest's notice acknowledgement (BE-5). Bump whenever a `legal_notice_*` / `privacy_*` string in `i18n.py` changes materially. |
| `TURNSTILE_SITE_KEY` | the production widget key in `config.py` | Cloudflare Turnstile site key. |
```

Replace with:

```markdown
| --- | --- | --- |
| `UBYHOST_PUBLIC_BASE_URL` | `http://127.0.0.1:8080` | Used to build guest permalinks, to match `Origin`/`Referer` on host POSTs, and to decide whether guest cookies get the `Secure` flag. If this is wrong, guest links point at the wrong host and the ownership/claim cookies may be issued without `Secure`. |
| `UBYHOST_DOMAIN` | unset | Expected public hostname. Only used by the startup guard. When it disagrees with `PUBLIC_BASE_URL`, production refuses to start and other deployments get a warning. Production also refuses a `PUBLIC_BASE_URL` that is not `https://`. |
| `UBYHOST_GUEST_PIN` | `1` | `0` removes the PIN gate from every guest route, leaving the permalink token as the only barrier. A production deployment refuses to start with this off. |
| `UBYHOST_GUEST_NOTICE_VERSION` | `1.0` | Version stamped on a guest's notice acknowledgement (BE-5). Bump whenever a `legal_notice_*` / `privacy_*` string in `i18n.py` changes materially. |
| `TURNSTILE_SITE_KEY` | the production widget key in `config.py` | Cloudflare Turnstile site key. |
```

Edit 2 of 3. Find (exactly once):

```markdown
| `UBYHOST_OPERATOR_REGISTRY_URL` | unset |

All six must be set for your own deployment. Without them the legal pages
will show empty operator details; set `UBYHOST_OPERATOR_REGISTRY_URL` to your
own public-register entry, or the legal pages will name the wrong company.
```

Replace with:

```markdown
| `UBYHOST_OPERATOR_REGISTRY_URL` | unset |

All six must be set for your own deployment. Production refuses to start while the name, IČO or address is empty. Set them only in the server `.env`, never in the repository. Without them the legal pages
will show empty operator details; set `UBYHOST_OPERATOR_REGISTRY_URL` to your
own public-register entry, or the legal pages will name the wrong company.
```

Edit 3 of 3. Find (exactly once):

```markdown
| `UBYHOST_BACKUP_AGE_RECIPIENT` | unset | `App/scripts/backup_data.sh` — public `age1...` recipient the snapshot is encrypted to. **Required when `UBYHOST_DEPLOYMENT=production`**; the run fails closed without it |
| `UBYHOST_BACKUP_RETENTION_DAYS` | `30` | `App/scripts/backup_data.sh` — snapshots older than this many days are removed; the newest is always kept |
| `UBYHOST_BACKUP_PING_URL` | unset | `deploy/lightsail/scripts/backup.sh` — pinged after each successful daily backup; if unset, no one is told when backups stop |
| `AGE_IDENTITY_FILE` | unset | `restore.sh` — host path to the age private identity used to decrypt an encrypted snapshot; never inside the volume |
| `RESTORE_CONFIRM` | unset | `restore.sh` — `yes` skips the interactive confirmation prompt |
```

Replace with:

```markdown
| `UBYHOST_BACKUP_AGE_RECIPIENT` | unset | `App/scripts/backup_data.sh` — public `age1...` recipient the snapshot is encrypted to. **Required when `UBYHOST_DEPLOYMENT=production`**; the run fails closed without it |
| `UBYHOST_BACKUP_RETENTION_DAYS` | `30` | `App/scripts/backup_data.sh` — snapshots older than this many days are removed; the newest is always kept |
| `UBYHOST_BACKUP_PING_URL` | unset | `deploy/lightsail/scripts/backup.sh` — pinged after each successful daily backup. Required in production: `preflight.sh` refuses to deploy while it is empty. |
| `AGE_IDENTITY_FILE` | unset | `restore.sh` — host path to the age private identity used to decrypt an encrypted snapshot; never inside the volume |
| `RESTORE_CONFIRM` | unset | `restore.sh` — `yes` skips the interactive confirmation prompt |
```

Why: Q8 and Q11. The table described warnings that are now refusals.

Verify: `grep -n 'refuses' docs/ENVIRONMENT.md` shows the PIN, domain, operator and ping rows.

#### T54 Preflight report lists the ping URL and operator keys

File: `.github/workflows/deploy-preflight.yml`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```yaml
            echo "UBYHOST_ADMIN_PASSWORD=$(present UBYHOST_ADMIN_PASSWORD)"
            echo "UBYHOST_SECRET_KEY=$(present UBYHOST_SECRET_KEY)"
            REC="$(value UBYHOST_BACKUP_AGE_RECIPIENT)"
            if [ -z "$REC" ]; then
```

Replace with:

```yaml
            echo "UBYHOST_ADMIN_PASSWORD=$(present UBYHOST_ADMIN_PASSWORD)"
            echo "UBYHOST_SECRET_KEY=$(present UBYHOST_SECRET_KEY)"
            echo "UBYHOST_BACKUP_PING_URL=$(present UBYHOST_BACKUP_PING_URL)"
            echo "UBYHOST_OPERATOR_NAME=$(present UBYHOST_OPERATOR_NAME)"
            echo "UBYHOST_OPERATOR_ICO=$(present UBYHOST_OPERATOR_ICO)"
            echo "UBYHOST_OPERATOR_ADDRESS=$(present UBYHOST_OPERATOR_ADDRESS)"
            REC="$(value UBYHOST_BACKUP_AGE_RECIPIENT)"
            if [ -z "$REC" ]; then
```

Why: Q8 and Q11. The read-only check shows SET or MISSING for the newly required keys, never the value.

Verify: Workflow YAML is valid (`python -c 'import yaml;yaml.safe_load(open(".github/workflows/deploy-preflight.yml"))'`).

#### T55 Env template: ping URL and operator keys are required

File: `deploy/lightsail/.env.example`

Action: EDIT

Depends on: T30

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```
# Time-based retention for local snapshots (days); the newest is always kept.
UBYHOST_BACKUP_RETENTION_DAYS=30
# UBYHOST_BACKUP_PING_URL=https://hc-ping.com/<uuid>   # optional: pinged after each successful daily backup

# --- Software operator (host-admin support is support@ubyhost.com) ---
# Set your own operator identity; the legal pages render these values.
# UBYHOST_OPERATOR_NAME=
# UBYHOST_OPERATOR_ICO=
# UBYHOST_OPERATOR_DIC=
# UBYHOST_OPERATOR_ADDRESS=
UBYHOST_OPERATOR_EMAIL=support@ubyhost.com

```

Replace with:

```
# Time-based retention for local snapshots (days); the newest is always kept.
UBYHOST_BACKUP_RETENTION_DAYS=30
# Required in production: pinged after each successful daily backup; preflight.sh refuses to deploy while it is empty.
UBYHOST_BACKUP_PING_URL=

# --- Software operator (host-admin support is support@ubyhost.com) ---
# Required in production: the app refuses to start while name, IČO or address is empty.
# Fill these in on the server only. Never commit real values (this repo is public).
UBYHOST_OPERATOR_NAME=
UBYHOST_OPERATOR_ICO=
UBYHOST_OPERATOR_DIC=
UBYHOST_OPERATOR_ADDRESS=
UBYHOST_OPERATOR_EMAIL=support@ubyhost.com

```

Why: Q8 and Q11. The keys stay empty in the repo; they are filled on the server.

Verify: `grep -n 'UBYHOST_BACKUP_PING_URL=\|UBYHOST_OPERATOR_NAME=' deploy/lightsail/.env.example` shows both, empty.

#### T56 Preflight refuses production without the ping URL or with the PIN off

File: `deploy/lightsail/scripts/preflight.sh`

Action: EDIT

Depends on: T24

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```bash

if [ "${DEPLOYMENT}" = "production" ] && [ "${UBYHOST_GUEST_PIN:-1}" = "0" ]; then
  warn "UBYHOST_GUEST_PIN=0 on production — guest permalinks are unprotected"
fi

```

Replace with:

```bash

if [ "${DEPLOYMENT}" = "production" ] && [ "${UBYHOST_GUEST_PIN:-1}" = "0" ]; then
  die "UBYHOST_GUEST_PIN=0 on production — guest permalinks would be unprotected and the app refuses to start"
fi

```

Edit 2 of 2. Find (exactly once):

```bash

if [ "${DEPLOYMENT}" = "production" ] && [ -z "${UBYHOST_BACKUP_PING_URL:-}" ]; then
  warn "UBYHOST_BACKUP_PING_URL is empty — a failing nightly backup will go unnoticed"
fi

```

Replace with:

```bash

if [ "${DEPLOYMENT}" = "production" ] && [ -z "${UBYHOST_BACKUP_PING_URL:-}" ]; then
  die "UBYHOST_BACKUP_PING_URL is empty — a failing nightly backup would go unnoticed"
fi

```

Why: Owner decision Q11. A failing nightly backup must not go unnoticed.

Verify: `bash -n deploy/lightsail/scripts/preflight.sh` and `shellcheck` are clean.

#### T57 Kosovo (XKX) is a nationality. HIGH RISK (filing)

File: `App/app/data/countries.json`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```
},
{
"code": "XXA",
"en": "Stateless person",
```

Replace with:

```
},
{
"code": "XKX",
"en": "Kosovo",
"cs": "Kosovo"
},
{
"code": "XXA",
"en": "Stateless person",
```

Why: Owner decision Q7. Guests from Kosovo could not register. XKX is the user-assigned alpha-3 code in common use; confirm UbyPort accepts it before relying on it.

Verify: After T58.

#### T58 Test Kosovo can be picked and validates

File: `App/tests/test_guest_country_picker.py`

Action: EDIT

Depends on: T57

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```python
-- a guest looking under "C" has to find their own country. And the eight
nationalities a Czech host actually files are lifted into their own group at the
top, so the guest does not scroll a 253-row wheel for the common case. The field
still starts empty: the guest's phone language says nothing about their
nationality.
```

Replace with:

```python
-- a guest looking under "C" has to find their own country. And the eight
nationalities a Czech host actually files are lifted into their own group at the
top, so the guest does not scroll a 254-row wheel for the common case. The field
still starts empty: the guest's phone language says nothing about their
nationality.
```

Edit 2 of 2. Find (exactly once):

```python
        assert '<option value=""' in form.text
    finally:
        _cleanup()
```

Replace with:

```python
        assert '<option value=""' in form.text
    finally:
        _cleanup()


def test_kosovo_can_be_picked_and_passes_validation():
    from app import validation

    assert "Kosovo" in _labels("en")
    assert validation.country_name("XKX", "cs") == "Kosovo"
    assert "XKX" in validation.country_codes()
```

Why: Q7 regression test.

Verify: `pt tests/test_guest_country_picker.py tests/test_validation.py` passes.

#### T59 Deletion notice copy (EN/CS)

File: `App/app/host_i18n.py`

Action: EDIT

Depends on: T46

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 4. Find (exactly once):

```python
        "notification.mail_kind.submission_problem": "police report problem",
        "notification.mail_kind.invoice_issued": "invoice to the customer",
        "notification.turnstile_unavailable.title": "The security check could not be reached, so it was skipped.",
        "notification.turnstile_unavailable.detail": "Cloudflare Turnstile did not answer. Guests were let through without the check for a short while; the alert clears itself once verification works again.",
```

Replace with:

```python
        "notification.mail_kind.submission_problem": "police report problem",
        "notification.mail_kind.invoice_issued": "invoice to the customer",
        "notification.mail_kind.workspace_deletion": "workspace deletion notice",
        "notification.turnstile_unavailable.title": "The security check could not be reached, so it was skipped.",
        "notification.turnstile_unavailable.detail": "Cloudflare Turnstile did not answer. Guests were let through without the check for a short while; the alert clears itself once verification works again.",
```

Edit 2 of 4. Find (exactly once):

```python
        "submission.nothing_to_send": "Nothing to send",
        "mail.submission_problem.subject": "UbyPort did not accept your report - %(property)s",
        "mail.submission_problem.subject_transport": "Report for %(property)s not delivered yet — retrying automatically",
        "mail.submission_problem.heading": "Your report was not accepted",
```

Replace with:

```python
        "submission.nothing_to_send": "Nothing to send",
        "mail.submission_problem.subject": "UbyPort did not accept your report - %(property)s",
        "mail.workspace_deletion.subject_scheduled": "Your UbyHost account will be deleted on %(date)s",
        "mail.workspace_deletion.subject_week_before": "Your UbyHost account will be deleted in 7 days (%(date)s)",
        "mail.workspace_deletion.heading": "Account deletion on %(date)s",
        "mail.workspace_deletion.intro_scheduled": "Your UbyHost account has been closed and sign-in is disabled. On %(date)s every property, stay, guest record, invoice and stay-fee filing in it will be permanently deleted.",
        "mail.workspace_deletion.intro_week_before": "This is a reminder: on %(date)s every property, stay, guest record, invoice and stay-fee filing in your UbyHost account will be permanently deleted.",
        "mail.workspace_deletion.keep_label": "Records you must keep",
        "mail.workspace_deletion.keep": "Czech law may require you to keep invoices, stay-fee filings and police receipts for several years. That duty stays with you after the account is gone. To receive an export of your data, reply to this e-mail or write to %(support)s before %(date)s.",
        "mail.workspace_deletion.footer": "Questions: %(support)s",
        "mail.submission_problem.subject_transport": "Report for %(property)s not delivered yet — retrying automatically",
        "mail.submission_problem.heading": "Your report was not accepted",
```

Edit 3 of 4. Find (exactly once):

```python
        "notification.mail_kind.submission_problem": "problém s hlášením na policii",
        "notification.mail_kind.invoice_issued": "faktura odběrateli",
        "notification.turnstile_unavailable.title": "Bezpečnostní kontrolu se nepodařilo ověřit, proto byla přeskočena.",
        "notification.turnstile_unavailable.detail": "Cloudflare Turnstile neodpověděl. Hosté byli krátce vpuštěni bez kontroly; upozornění zmizí, jakmile ověřování začne znovu fungovat.",
```

Replace with:

```python
        "notification.mail_kind.submission_problem": "problém s hlášením na policii",
        "notification.mail_kind.invoice_issued": "faktura odběrateli",
        "notification.mail_kind.workspace_deletion": "oznámení o smazání účtu",
        "notification.turnstile_unavailable.title": "Bezpečnostní kontrolu se nepodařilo ověřit, proto byla přeskočena.",
        "notification.turnstile_unavailable.detail": "Cloudflare Turnstile neodpověděl. Hosté byli krátce vpuštěni bez kontroly; upozornění zmizí, jakmile ověřování začne znovu fungovat.",
```

Edit 4 of 4. Find (exactly once):

```python
        "submission.nothing_to_send": "Nic k odeslání",
        "mail.submission_problem.subject": "UbyPort nepřijal vaše hlášení - %(property)s",
        "mail.submission_problem.subject_transport": "Hlášení pro %(property)s zatím nebylo doručeno – zkusíme to znovu automaticky",
        "mail.submission_problem.heading": "Vaše hlášení nebylo přijato",
```

Replace with:

```python
        "submission.nothing_to_send": "Nic k odeslání",
        "mail.submission_problem.subject": "UbyPort nepřijal vaše hlášení - %(property)s",
        "mail.workspace_deletion.subject_scheduled": "Váš účet UbyHost bude %(date)s smazán",
        "mail.workspace_deletion.subject_week_before": "Váš účet UbyHost bude za 7 dní smazán (%(date)s)",
        "mail.workspace_deletion.heading": "Smazání účtu %(date)s",
        "mail.workspace_deletion.intro_scheduled": "Váš účet UbyHost byl uzavřen a přihlášení je vypnuté. Dne %(date)s budou trvale smazány všechny nemovitosti, pobyty, údaje hostů, faktury i přiznání k poplatku z pobytu.",
        "mail.workspace_deletion.intro_week_before": "Připomínáme, že dne %(date)s budou z vašeho účtu UbyHost trvale smazány všechny nemovitosti, pobyty, údaje hostů, faktury i přiznání k poplatku z pobytu.",
        "mail.workspace_deletion.keep_label": "Doklady, které musíte uchovat",
        "mail.workspace_deletion.keep": "Faktury, přiznání k poplatku z pobytu a doručenky z policie můžete být podle zákona povinni uchovávat několik let. Tato povinnost zůstává na vás i po smazání účtu. Pokud chcete export svých dat, odpovězte na tento e-mail nebo napište na %(support)s do %(date)s.",
        "mail.workspace_deletion.footer": "Dotazy: %(support)s",
        "mail.submission_problem.subject_transport": "Hlášení pro %(property)s zatím nebylo doručeno – zkusíme to znovu automaticky",
        "mail.submission_problem.heading": "Vaše hlášení nebylo přijato",
```

Why: Owner decision Q9. Says sign-in is off, what will be deleted, that keeping invoices and filings is the host's duty, and how to ask for the export.

Verify: `pt tests/test_host_i18n.py` passes.

#### T60 New host mail kind workspace_deletion

File: `App/app/mail.py`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```python
    "submission_problem",
    "invoice_issued",
)

```

Replace with:

```python
    "submission_problem",
    "invoice_issued",
    "workspace_deletion",
)

```

Edit 2 of 2. Find (exactly once):

```python
    "reminder_host",
    "submission_problem",
)

```

Replace with:

```python
    "reminder_host",
    "submission_problem",
    "workspace_deletion",
)

```

Why: Owner decision Q9.

Verify: After T65.

#### T61 Compose and queue the deletion notice. HIGH RISK (retention)

File: `App/app/mail_notify.py`

Action: EDIT

Depends on: T59, T60

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python


# --- guest mail -------------------------------------------------------------
#
```

Replace with:

```python


# --- workspace deletion ----------------------------------------------------
#
# The host is the controller and keeps the duty to hold invoices, stay-fee
# filings and Doručenky. Sign-in is disabled the moment deletion is scheduled,
# so the notice tells them to ask support for the export an admin can download.

WORKSPACE_DELETION_STAGES = ("scheduled", "week_before")


def workspace_contact_emails(owner_user_id: int) -> List[str]:
    """Every distinct contact address on the workspace's legal entities."""
    rows = db.query(
        "SELECT contact_email FROM legal_entity WHERE owner_user_id = ? ORDER BY id",
        (owner_user_id,),
    )
    found: List[str] = []
    for row in rows:
        address = mail.normalise_email(row["contact_email"] or "")
        if address and address not in found:
            found.append(address)
    return found


def build_workspace_deletion(*, stage: str, date: str, lang: Optional[str] = None) -> Dict[str, str]:
    lang = host_i18n.normalise_language(lang or HOST_MAIL_LANGUAGE)
    support = config.OPERATOR_EMAIL
    subject = _text(lang, f"mail.workspace_deletion.subject_{stage}", date=date)
    heading = _text(lang, "mail.workspace_deletion.heading", date=date)
    intro = _text(lang, f"mail.workspace_deletion.intro_{stage}", date=date)
    keep_label = _text(lang, "mail.workspace_deletion.keep_label")
    keep = _text(lang, "mail.workspace_deletion.keep", date=date, support=support)
    footer = _text(lang, "mail.workspace_deletion.footer", support=support)
    text = "\n".join([intro, "", f"{keep_label}: {keep}", "", "--", "UbyHost", footer])
    blocks = [
        _block_heading(heading),
        _block_paragraph(intro),
        _block_section(keep_label, keep),
    ]
    return {
        "subject": subject,
        "text": text,
        "html": _shell(
            lang=lang,
            title=heading,
            preheader=intro,
            blocks=blocks,
            footer_lines=["UbyHost", footer],
        ),
    }


def workspace_deletion(owner_user_id: int, due_at: str, stage: str) -> int:
    """Queue the deletion notice to every contact address. Returns how many."""
    if stage not in WORKSPACE_DELETION_STAGES:
        raise ValueError(f"unknown stage {stage}")
    date = validation.fmt_date(due_at[:10])
    content = build_workspace_deletion(stage=stage, date=date)
    payload: Dict[str, Any] = {
        "text": content["text"],
        "html": content["html"],
        "lang": HOST_MAIL_LANGUAGE,
        "reply_to": config.OPERATOR_EMAIL,
    }
    queued = 0
    for address in workspace_contact_emails(owner_user_id):
        if mail.enqueue(
            kind="workspace_deletion",
            idempotency_key=f"workspace_deletion:{owner_user_id}:{due_at}:{stage}:{address}",
            to_email=address,
            subject=content["subject"],
            payload=payload,
            owner_user_id=owner_user_id,
        ):
            queued += 1
    return queued


# --- guest mail -------------------------------------------------------------
#
```

Why: Owner decision Q9. One notice per distinct contact address, Reply-To support, idempotent per stage.

Verify: After T65.

#### T62 Reminder 7 days before deletion. HIGH RISK (retention)

File: `App/app/retention.py`

Action: EDIT

Depends on: T11, T61

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 3. Find (exactly once):

```python
from typing import Any, Dict, List, Optional

from . import alerts, config, db, housebook, invoices, passport_photos

log = logging.getLogger(__name__)
```

Replace with:

```python
from typing import Any, Dict, List, Optional

from . import alerts, config, db, housebook, invoices, mail_notify, passport_photos

log = logging.getLogger(__name__)
```

Edit 2 of 3. Find (exactly once):

```python
    if owner_user_id is not None:
        return 0
    rows = db.query(
        "SELECT id FROM user_account WHERE deletion_due_at IS NOT NULL AND deletion_due_at <= ?",
```

Replace with:

```python
    if owner_user_id is not None:
        return 0
    if not dry_run:
        _workspace_deletion_reminders()
    rows = db.query(
        "SELECT id FROM user_account WHERE deletion_due_at IS NOT NULL AND deletion_due_at <= ?",
```

Edit 3 of 3. Find (exactly once):

```python
        _delete_workspace(row["id"])
    return len(rows)


```

Replace with:

```python
        _delete_workspace(row["id"])
    return len(rows)


WORKSPACE_REMINDER_DAYS = 7


def _workspace_deletion_reminders() -> None:
    """Remind each workspace due within a week. The outbox key sends it once."""
    soon = (
        datetime.now(timezone.utc) + timedelta(days=WORKSPACE_REMINDER_DAYS)
    ).replace(microsecond=0).isoformat()
    rows = db.query(
        "SELECT id, deletion_due_at FROM user_account "
        "WHERE deletion_due_at IS NOT NULL AND deletion_due_at > ? AND deletion_due_at <= ?",
        (db.utcnow(), soon),
    )
    for row in rows:
        mail_notify.workspace_deletion(row["id"], row["deletion_due_at"], "week_before")


```

Why: Owner decision Q9. Sent only when the retention run really deletes (not a dry run), so nobody is warned of a deletion that will not happen.

Verify: After T65.

#### T63 Scheduling deletion sends the first notice

File: `App/app/routes/admin_accounts.py`

Action: EDIT

Depends on: T43, T61

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```python
    host_i18n,
    incidents,
    rate_limit,
    security,
```

Replace with:

```python
    host_i18n,
    incidents,
    mail_notify,
    rate_limit,
    security,
```

Edit 2 of 2. Find (exactly once):

```python
    ).replace(microsecond=0).isoformat()
    db.update("user_account", user_id, {"deletion_due_at": due, "active": 0})
    db.audit(
        "workspace_deletion_scheduled",
```

Replace with:

```python
    ).replace(microsecond=0).isoformat()
    db.update("user_account", user_id, {"deletion_due_at": due, "active": 0})
    mail_notify.workspace_deletion(user_id, due, "scheduled")
    db.audit(
        "workspace_deletion_scheduled",
```

Why: Owner decision Q9.

Verify: After T65.

#### T64 Mail kinds test lists workspace_deletion

File: `App/tests/test_claim_mail.py`

Action: EDIT

Depends on: T60

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python
        "submission_problem",
        "invoice_issued",
    }

```

Replace with:

```python
        "submission_problem",
        "invoice_issued",
        "workspace_deletion",
    }

```

Why: The test pins KINDS so a new kind is deliberate.

Verify: `pt tests/test_claim_mail.py` passes.

#### T65 Tests for the deletion notices

File: `App/tests/test_workspace_termination.py`

Action: EDIT

Depends on: T12, T61, T62, T63

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```python
        db.execute("DELETE FROM legal_acceptance WHERE user_account_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))

```

Replace with:

```python
        db.execute("DELETE FROM legal_acceptance WHERE user_account_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))

```

Edit 2 of 2. Find (exactly once):

```python
    assert db.query_one("SELECT id FROM legal_entity WHERE id = ?", (entity,)) is None
    assert db.query_one("SELECT id FROM email_outbox WHERE id = ?", (mail,)) is None
```

Replace with:

```python
    assert db.query_one("SELECT id FROM legal_entity WHERE id = ?", (entity,)) is None
    assert db.query_one("SELECT id FROM email_outbox WHERE id = ?", (mail,)) is None


def _notices(owner):
    return db.query(
        "SELECT to_email, subject, payload FROM email_outbox "
        "WHERE kind = 'workspace_deletion' AND owner_user_id = ? ORDER BY id",
        (owner,),
    )


def test_scheduling_deletion_mails_every_contact_address_once():
    owner, entity, *_rest = _seed("ws-mail")
    db.execute("UPDATE legal_entity SET contact_email = ? WHERE id = ?", ("host@example.com", entity))
    db.insert(
        "legal_entity",
        {"name": "second", "owner_user_id": owner, "contact_email": "HOST@example.com",
         "created_at": db.utcnow()},
    )
    _admin("ws-admin")
    client = _login("ws-admin")
    response = client.post(
        f"/admin/users/{owner}/schedule-deletion",
        data={"confirm": "ws-mail"}, follow_redirects=False,
    )
    assert response.status_code == 303
    rows = _notices(owner)
    assert [row["to_email"] for row in rows] == ["host@example.com"]
    assert "will be deleted on" in rows[0]["subject"]
    payload = json.loads(rows[0]["payload"])
    assert "support@ubyhost.com" in payload["text"]
    assert payload["reply_to"] == "support@ubyhost.com"


def test_a_workspace_due_within_a_week_gets_one_reminder():
    owner, entity, *_rest = _seed("ws-soon")
    db.execute("UPDATE legal_entity SET contact_email = ? WHERE id = ?", ("soon@example.com", entity))
    later, later_entity, *_rest = _seed("ws-later")
    db.execute("UPDATE legal_entity SET contact_email = ? WHERE id = ?", ("later@example.com", later_entity))
    db.execute(
        "UPDATE user_account SET deletion_due_at = ? WHERE id = ?",
        ((date.today() + timedelta(days=5)).isoformat() + "T12:00:00+00:00", owner),
    )
    db.execute(
        "UPDATE user_account SET deletion_due_at = ? WHERE id = ?",
        ((date.today() + timedelta(days=20)).isoformat() + "T12:00:00+00:00", later),
    )
    retention._workspace_deletion_step(date.today(), True, None)
    assert _notices(owner) == []  # a dry run deletes nothing, so it warns of nothing

    retention._workspace_deletion_step(date.today(), False, None)
    retention._workspace_deletion_step(date.today(), False, None)
    rows = _notices(owner)
    assert len(rows) == 1
    assert "in 7 days" in rows[0]["subject"]
    assert _notices(later) == []
```

Why: Q9 regression tests: one mail per address at scheduling, one reminder inside 7 days, none on a dry run.

Verify: `pt tests/test_workspace_termination.py tests/test_retention.py` passes.

#### T66 Docs: the HTML mail kinds list

File: `docs/SES.md`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```markdown

Kinds that carry HTML today: `claim`, `claim_resend`, `completion`,
`reminder_guest`, `reminder_host` and `submission_problem`. Every kind the app
can send is in that list: there is no plain-text-only message. The
**host submission-problem** notice additionally names the
```

Replace with:

```markdown

Kinds that carry HTML today: `claim`, `claim_resend`, `completion`,
`reminder_guest`, `reminder_host`, `submission_problem`, `invoice_issued` and
`workspace_deletion`. Every kind the app
can send is in that list: there is no plain-text-only message. The
**host submission-problem** notice additionally names the
```

Why: The list claimed to be complete but missed invoice_issued; it now also has workspace_deletion.

Verify: `grep -n workspace_deletion docs/SES.md` finds it.

### Phase 2. Shared tokens

#### T67 Status colour tokens by criticality

File: `App/app/static/tokens.css`

Action: EDIT

Depends on: Phase 1 complete

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```css
  --brown: #79533d;  --brown-bg: #f3ece7;
  --gray: #5f625f;   --gray-bg: #eceeec;

  /* Type scale */
```

Replace with:

```css
  --brown: #79533d;  --brown-bg: #f3ece7;
  --gray: #5f625f;   --gray-bg: #eceeec;

  /* Status by criticality. The more a status needs the host, the stronger
     its contrast; calm and finished states stay quiet. Text contrast on its
     own background (WCAG AA needs 4.5:1): critical 6.6, action 7.9,
     ready 6.9, waiting 6.8, done 6.7, neutral 6.2. Every badge also carries
     a text label, and critical adds a "!" mark, so colour is never alone. */
  --status-critical-bg: #b42318; --status-critical-ink: #ffffff; --status-critical-border: #b42318;
  --status-action-bg: #fde9c2;   --status-action-ink: #6b3a00;   --status-action-border: #eec27a;
  --status-ready-bg: #e9f0fc;    --status-ready-ink: #1d4f9e;    --status-ready-border: #c8d8f3;
  --status-waiting-bg: #eef6f5;  --status-waiting-ink: #285e59;  --status-waiting-border: #d3e7e4;
  --status-done-bg: #eef6f1;     --status-done-ink: #24613f;     --status-done-border: #d3e8db;
  --status-neutral-bg: #ffffff;  --status-neutral-ink: #5f625f;  --status-neutral-border: #deded9;

  /* Type scale */
```

Why: Part 2 B. Six criticality levels as tokens. Each ink-on-bg pair passes WCAG AA (6.2 to 7.9). Pills, tiles and deadlines all read from here.

Verify: `pt tests/test_signed_in_chrome.py tests/test_status_colours.py` passes after T70.

#### T68 Pills and deadlines use the tokens; drop unused tones

File: `App/app/static/app.css`

Action: EDIT

Depends on: T67

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 4. Find (exactly once):

```css
/* --- status pills ------------------------------------------------------ */

.pill {
  display: inline-flex;
```

Replace with:

```css
/* --- status pills ------------------------------------------------------ */

/* Colour classes map onto the criticality tokens in tokens.css:
   red = critical, amber = action, blue = ready, teal = waiting,
   green = done, grey = neutral. */
.pill {
  display: inline-flex;
```

Edit 2 of 4. Find (exactly once):

```css
  font-weight: 600;
  padding: 4px 10px;
  border-radius: var(--pill);
  white-space: nowrap;
  line-height: 1.35;
```

Replace with:

```css
  font-weight: 600;
  padding: 4px 10px;
  border: 1px solid var(--status-neutral-border);
  border-radius: var(--pill);
  background: var(--status-neutral-bg);
  color: var(--status-neutral-ink);
  white-space: nowrap;
  line-height: 1.35;
```

Edit 3 of 4. Find (exactly once):

```css
}
.pill.no-dot::before { display: none; }
.pill.grey { background: var(--gray-bg); color: var(--gray); }
.pill.blue { background: var(--brand-soft); color: var(--brand-ink); }
.pill.green { background: var(--ok-soft); color: var(--ok); }
.pill.amber { background: var(--warn-soft); color: var(--warn); }
.pill.red { background: var(--bad-soft); color: var(--bad); }
.pill.orange, .tone-orange { background: var(--orange-bg); color: var(--orange); }
.pill.teal, .tone-teal { background: var(--teal-bg); color: var(--teal); }
.pill.indigo, .tone-indigo { background: var(--indigo-bg); color: var(--indigo); }
.pill.purple, .tone-purple { background: var(--purple-bg); color: var(--purple); }
.pill.pink, .tone-pink { background: var(--pink-bg); color: var(--pink); }
.pill.brown, .tone-brown { background: var(--brown-bg); color: var(--brown); }

.deadline { font-weight: 600; font-size: 13.5px; }
.deadline.urgent { color: var(--bad); }
/* "Act today" and "already late" are different jobs: one is still compliant,
   the other is a breach where re-sending is penalised. Same red read as the
   same row, so past-deadline gets the filled treatment. */
.deadline.overdue {
  color: var(--bad);
  background: var(--bad-soft);
  padding: 2px 8px;
  border-radius: var(--pill);
  white-space: nowrap;
}
.deadline.soon { color: var(--warn); }
.deadline.ok { color: var(--ok); }
.deadline.future { color: var(--muted); font-weight: 500; }

```

Replace with:

```css
}
.pill.no-dot::before { display: none; }
.pill.red { background: var(--status-critical-bg); color: var(--status-critical-ink); border-color: var(--status-critical-border); }
.pill.red::before { content: "!"; width: auto; height: auto; background: none; opacity: 1; font-weight: 800; line-height: 1; }
.pill.amber { background: var(--status-action-bg); color: var(--status-action-ink); border-color: var(--status-action-border); }
.pill.blue { background: var(--status-ready-bg); color: var(--status-ready-ink); border-color: var(--status-ready-border); }
.pill.teal { background: var(--status-waiting-bg); color: var(--status-waiting-ink); border-color: var(--status-waiting-border); }
.pill.green { background: var(--status-done-bg); color: var(--status-done-ink); border-color: var(--status-done-border); }

.deadline { font-weight: 600; font-size: 13.5px; }
.deadline.urgent { color: var(--status-critical-bg); }
/* "Act today" and "already late" are different jobs: one is still compliant,
   the other is a breach where re-sending is penalised. Same red read as the
   same row, so past-deadline gets the filled treatment. */
.deadline.overdue {
  color: var(--status-critical-ink);
  background: var(--status-critical-bg);
  padding: 2px 8px;
  border-radius: var(--pill);
  white-space: nowrap;
}
.deadline.soon { color: var(--status-action-ink); }
.deadline.ok { color: var(--status-done-ink); }
.deadline.future { color: var(--muted); font-weight: 500; }

```

Edit 4 of 4. Find (exactly once):

```css

.pill {
  padding: 4px 10px;
  border: 1px solid color-mix(in srgb, currentColor 22%, transparent);
  font-size: 11.5px;
  font-weight: 650;
```

Replace with:

```css

.pill {
  font-size: 11.5px;
  font-weight: 650;
```

Why: Part 2 B, A63, A71. Pills and deadlines read the tokens. Red gets a '!' glyph, so it is not told apart by colour alone. Pill tones no template uses are removed.

Verify: After T70.

#### T69 Host shell drops duplicate pill colours and hard-coded stat colours

File: `App/app/static/host.css`

Action: EDIT

Depends on: T67

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 3. Find (exactly once):

```css
.host-task-list { display: grid; gap: 10px; }
.host-task { padding: 18px 20px; border: 1px solid var(--line); border-radius: 14px; background: white; display: flex; align-items: center; gap: 18px; }
.host-task.is-urgent { border-left: 4px solid var(--brand); }
.host-task-main { flex: 1; min-width: 0; }
.host-task-main > a { font-size: 16px; font-weight: 750; color: var(--ink); text-decoration: none; }
```

Replace with:

```css
.host-task-list { display: grid; gap: 10px; }
.host-task { padding: 18px 20px; border: 1px solid var(--line); border-radius: 14px; background: white; display: flex; align-items: center; gap: 18px; }
.host-task.is-urgent { border-left: 4px solid var(--status-critical-border); }
.host-task-main { flex: 1; min-width: 0; }
.host-task-main > a { font-size: 16px; font-weight: 750; color: var(--ink); text-decoration: none; }
```

Edit 2 of 3. Find (exactly once):

```css
}
.host-property-save { position: sticky; bottom: 12px; z-index: 19; width: fit-content; background: white; border: 1px solid var(--line); border-radius: 12px; padding: 12px; box-shadow: var(--shadow-popover); }
body.host-workspace .pill.blue { color: var(--blue); background: var(--blue-bg); border-color: transparent; }
body.host-workspace .pill.teal { color: var(--teal); background: var(--teal-bg); border-color: transparent; }
body.host-workspace .pill.green { color: var(--green); background: var(--green-bg); border-color: transparent; }
body.host-workspace .pill.amber { color: var(--amber); background: var(--amber-bg); border-color: transparent; }
body.host-workspace .pill.grey { color: var(--gray); background: var(--gray-bg); border-color: transparent; }
body.host-workspace .pill.red { color: var(--red); background: var(--red-bg); border-color: transparent; }
.host-today-actions { display: flex; flex-direction: column; align-items: flex-end; gap: 8px; }
.host-today-actions .page-toolbar, .host-today-actions .page-toolbar-row { margin: 0; padding: 0; }
```

Replace with:

```css
}
.host-property-save { position: sticky; bottom: 12px; z-index: 19; width: fit-content; background: white; border: 1px solid var(--line); border-radius: 12px; padding: 12px; box-shadow: var(--shadow-popover); }
.host-today-actions { display: flex; flex-direction: column; align-items: flex-end; gap: 8px; }
.host-today-actions .page-toolbar, .host-today-actions .page-toolbar-row { margin: 0; padding: 0; }
```

Edit 3 of 3. Find (exactly once):

```css
.host-workspace .dashboard-stats strong { font-size: 24px; letter-spacing: -.04em; }
.host-workspace .dashboard-stats span { font-size: 13px; font-weight: 650; }
/* Strong enough to read against the warm canvas, unlike the pale token tints. */
.host-workspace .dashboard-stats .stat-action { background: #ffe1cd; border-color: #f6cbb2; }
.host-workspace .dashboard-stats .stat-action strong,
.host-workspace .dashboard-stats .stat-action span { color: #9a3f06; }
.host-workspace .dashboard-stats .stat-waiting { background: #d5ecea; border-color: #b3dcd8; }
.host-workspace .dashboard-stats .stat-waiting strong,
.host-workspace .dashboard-stats .stat-waiting span { color: #086b63; }
.host-workspace .dashboard-stats .stat-ready { background: #d9efe1; border-color: #b5dcc4; }
.host-workspace .dashboard-stats .stat-ready strong,
.host-workspace .dashboard-stats .stat-ready span { color: #146a41; }
.host-workspace .dashboard-stats .stat-overdue { background: #f9d7d3; border-color: #efb9b2; }
.host-workspace .dashboard-stats .stat-overdue strong,
.host-workspace .dashboard-stats .stat-overdue span { color: #ab2015; }
.host-workspace .host-month-filter { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin: 0 auto 18px; padding: 0; border: 0; background: none; }
.host-workspace .host-month-filter label { font-size: 13px; font-weight: 700; color: var(--ink-secondary); }
```

Replace with:

```css
.host-workspace .dashboard-stats strong { font-size: 24px; letter-spacing: -.04em; }
.host-workspace .dashboard-stats span { font-size: 13px; font-weight: 650; }
.host-workspace .dashboard-stats .stat-overdue { background: var(--status-critical-bg); border-color: var(--status-critical-border); color: var(--status-critical-ink); }
.host-workspace .dashboard-stats .stat-action { background: var(--status-action-bg); border-color: var(--status-action-border); color: var(--status-action-ink); }
.host-workspace .dashboard-stats .stat-ready { background: var(--status-ready-bg); border-color: var(--status-ready-border); color: var(--status-ready-ink); }
.host-workspace .dashboard-stats .stat-waiting { background: var(--status-waiting-bg); border-color: var(--status-waiting-border); color: var(--status-waiting-ink); }
.host-workspace .host-month-filter { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin: 0 auto 18px; padding: 0; border: 0; background: none; }
.host-workspace .host-month-filter label { font-size: 13px; font-weight: 700; color: var(--ink-secondary); }
```

Why: Part 2 B, A71. The host shell repeated pill colours and hard-coded the stat tile colours, so the same status could look different in two places.

Verify: After T70.

#### T70 Test: stat tiles use the status tokens

File: `App/tests/test_signed_in_chrome.py`

Action: EDIT

Depends on: T69

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python


def test_stat_tiles_read_against_the_warm_canvas():
    """The pale token tints vanished on the warm canvas; tiles carry their own."""
    css = (Path(__file__).resolve().parents[1] / "app" / "static" / "host.css").read_text()
    block = css.split(".dashboard-stats .stat-action", 1)[1].split(".host-month-filter", 1)[0]
    assert "#ffe1cd" in block, "needs action tile must not reuse the washed-out amber tint"
    assert "var(--amber-bg)" not in block
    for name in ("stat-waiting", "stat-ready", "stat-overdue"):
        assert css.count(f".dashboard-stats .{name} {{ background: #") == 1
        assert f".dashboard-stats .{name} {{ background: var(--" not in css


```

Replace with:

```python


def test_stat_tiles_use_the_status_tokens():
    """Tiles take their colours from the criticality tokens, never hard-coded hex."""
    css = (Path(__file__).resolve().parents[1] / "app" / "static" / "host.css").read_text()
    for name, level in (("stat-overdue", "critical"), ("stat-action", "action"),
                        ("stat-ready", "ready"), ("stat-waiting", "waiting")):
        assert f".dashboard-stats .{name} {{ background: var(--status-{level}-bg);" in css


```

Why: Part 2 B. The old test asserted the hard-coded colours.

Verify: End of Phase 2: full suite passes.

### Phase 3. Part 2 A to D (filters, status colours, guest count, guide)

#### T71 Compact guest count style

File: `App/app/static/app.css`

Action: EDIT

Depends on: Phase 2 complete, T68

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```css
.pill.teal { background: var(--status-waiting-bg); color: var(--status-waiting-ink); border-color: var(--status-waiting-border); }
.pill.green { background: var(--status-done-bg); color: var(--status-done-ink); border-color: var(--status-done-border); }

.deadline { font-weight: 600; font-size: 13.5px; }
```

Replace with:

```css
.pill.teal { background: var(--status-waiting-bg); color: var(--status-waiting-ink); border-color: var(--status-waiting-border); }
.pill.green { background: var(--status-done-bg); color: var(--status-done-ink); border-color: var(--status-done-border); }
.guest-count { display: inline-flex; align-items: center; gap: 4px; color: var(--ink-secondary); font-size: 13px; font-weight: 600; white-space: nowrap; }
.guest-count svg { width: 14px; height: 14px; flex: 0 0 auto; }

.deadline { font-weight: 600; font-size: 13.5px; }
```

Why: Part 2 C. Styles for the icon + n/m count that replaces the long sentence.

Verify: After T76: `pt tests/test_overview_headcount.py` passes.

#### T72 Pill tone follows criticality; guest_count macro

File: `App/app/templates/_components.html`

Action: EDIT

Depends on: T67

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 3. Find (exactly once):

```html
    'awaiting_verification': t('status.awaiting_verification')
  } %}
  {% if is_demo and status in ('ready', 'awaiting_verification') %}
    {% set label = t('status.demo_preview') %}
    {% set tip = t('status.demo_preview_tip') %}
  {% elif automation_mode == 'immediate' and status in ('awaiting_guest', 'incomplete') %}
    {% set label = t('status.waiting_guest') %}
    {% set tip = t('status.waiting_guest_tip') %}
  {% elif status in ('ready', 'awaiting_verification') and automation_mode == 'immediate' %}
    {% set label = t('status.ready_immediate') %}
    {% set tip = t('status.ready_immediate_tip') %}
  {% elif status in ('ready', 'awaiting_verification') and automation_mode == 'scheduled' %}
    {% set label = t('status.ready_scheduled') %}
    {% set tip = t('status.ready_scheduled_tip') %}
  {% elif status == 'awaiting_verification' %}
    {% set label = t('status.awaiting_verification') %}
```

Replace with:

```html
    'awaiting_verification': t('status.awaiting_verification')
  } %}
  {# Tone follows criticality (tokens.css): red critical, amber host action,
     blue ready, teal waiting on the guest, green done, grey neutral. #}
  {% set tones = {
    'failed': 'red',
    'reported': 'green',
    'ready': 'blue',
    'incomplete': 'amber',
    'not_required': 'grey',
    'awaiting_guest': 'teal',
    'awaiting_verification': 'amber'
  } %}
  {% set tone = tones.get(status, 'grey') %}
  {% if is_demo and status in ('ready', 'awaiting_verification') %}
    {% set label = t('status.demo_preview') %}
    {% set tip = t('status.demo_preview_tip') %}
    {% set tone = 'grey' %}
  {% elif automation_mode == 'immediate' and status in ('awaiting_guest', 'incomplete') %}
    {% set label = t('status.waiting_guest') %}
    {% set tip = t('status.waiting_guest_tip') %}
    {% set tone = 'teal' %}
  {% elif status in ('ready', 'awaiting_verification') and automation_mode == 'immediate' %}
    {% set label = t('status.ready_immediate') %}
    {% set tip = t('status.ready_immediate_tip') %}
    {% set tone = 'blue' %}
  {% elif status in ('ready', 'awaiting_verification') and automation_mode == 'scheduled' %}
    {% set label = t('status.ready_scheduled') %}
    {% set tip = t('status.ready_scheduled_tip') %}
    {% set tone = 'blue' %}
  {% elif status == 'awaiting_verification' %}
    {% set label = t('status.awaiting_verification') %}
```

Edit 2 of 3. Find (exactly once):

```html
    {% set tip = '' %}
  {% endif %}
  {% set tones = {
    'failed': 'red',
    'reported': 'green',
    'ready': 'blue',
    'incomplete': 'amber',
    'not_required': 'grey',
    'awaiting_guest': 'teal',
    'awaiting_verification': 'blue'
  } %}
  <span class="pill {{ tones.get(status, 'grey') }}" {% if tip %}title="{{ tip }}"{% endif %}>{{ label }}</span>
{% endmacro %}

```

Replace with:

```html
    {% set tip = '' %}
  {% endif %}
  <span class="pill {{ tone }}" {% if tip %}title="{{ tip }}"{% endif %}>{{ label }}</span>
{% endmacro %}

{# Guest count for a stay. Calendars never carry it, so until the guest or the
   host declares it the count shows nothing (or a quiet dash in tables). #}
{% macro guest_count(progress, placeholder=false) %}
  {% if progress.expected is not none or progress.guests %}
    <span class="guest-count" title="{{ t('stays.table.guests') }}">
      <svg viewBox="0 0 16 16" fill="none" aria-hidden="true"><circle cx="8" cy="5.5" r="2.5" stroke="currentColor" stroke-width="1.4"/><path d="M3.5 13.5c0-2.4 2-3.8 4.5-3.8s4.5 1.4 4.5 3.8" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>
      <span class="sr-only">{{ t('stays.table.guests') }}:</span>
      {% if progress.expected is not none %}{{ progress.filled }} / {{ progress.expected }}{% else %}{{ progress.guests | length }}{% endif %}
    </span>
  {% elif placeholder %}
    <span class="muted" aria-hidden="true">–</span><span class="sr-only">{{ t('common.guests_unknown') }}</span>
  {% endif %}
{% endmacro %}

```

Edit 3 of 3. Find (exactly once):

```html
    'outcome_unknown': 'red',
    'not_configured': 'amber',
    'running': 'grey',
    'noop': 'grey'
  } %}
```

Replace with:

```html
    'outcome_unknown': 'red',
    'not_configured': 'amber',
    'running': 'teal',
    'noop': 'grey'
  } %}
```

Why: Part 2 B and C. The tone of each stay status follows the criticality scale, and the new guest_count macro gives one rendering for every page.

Verify: After T76.

#### T73 Dashboard shows the compact guest count

File: `App/app/templates/dashboard.html`

Action: EDIT

Depends on: T72

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```html
{% block title %}{{ t('dashboard.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header, progress_pill, row_menu_begin, row_menu_end, row_reporting_actions, copy_inline, onboarding_banner, onboarding_finish, onboarding_finish_strip, onboarding_welcome, next_action, property_identity, sync_calendars_button with context %}

{% macro queue_table(items, empty_key='dashboard.queue.empty.default') %}
```

Replace with:

```html
{% block title %}{{ t('dashboard.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header, progress_pill, row_menu_begin, row_menu_end, row_reporting_actions, copy_inline, onboarding_banner, onboarding_finish, onboarding_finish_strip, onboarding_welcome, next_action, property_identity, sync_calendars_button, guest_count with context %}

{% macro queue_table(items, empty_key='dashboard.queue.empty.default') %}
```

Edit 2 of 2. Find (exactly once):

```html
        <span class="deadline {{ row.urgency }}">{{ describe_time_left(row.check_in) }}</span>
        {% if row.deadline and row.urgency != 'future' %}<span>{{ t('dashboard.table.deadline_by', when=row.deadline.strftime('%d.%m. %H:%M')) }}</span>{% endif %}
      </div>
      <a href="/reservations/{{ reservation.id }}?return_to=/">{{ property_identity(reservation.apartment_id, reservation.internal_name, true) }}</a>
      <div class="host-task-state next-action">
        {% if progress.expected is none %}<span title="{{ t('common.guests_unknown') }}">—</span> {{ t('common.guests_unknown') }} · {% endif %}
        {% if progress.status == 'failed' %}{{ progress_pill(progress.status, reservation.automation_mode) }}
        {% elif progress.not_registered %}{{ tp('host.missing', progress.not_registered) }}
```

Replace with:

```html
        <span class="deadline {{ row.urgency }}">{{ describe_time_left(row.check_in) }}</span>
        {% if row.deadline and row.urgency != 'future' %}<span>{{ t('dashboard.table.deadline_by', when=row.deadline.strftime('%d.%m. %H:%M')) }}</span>{% endif %}
        {{ guest_count(progress) }}
      </div>
      <a href="/reservations/{{ reservation.id }}?return_to=/">{{ property_identity(reservation.apartment_id, reservation.internal_name, true) }}</a>
      <div class="host-task-state next-action">
        {% if progress.status == 'failed' %}{{ progress_pill(progress.status, reservation.automation_mode) }}
        {% elif progress.not_registered %}{{ tp('host.missing', progress.not_registered) }}
```

Why: Part 2 C, A69. The long 'not known yet' sentence is replaced by nothing (when unknown) or an icon with n / m, in the context line, so the next action stays first.

Verify: After T76.

#### T74 Stays list shows the compact guest count

File: `App/app/templates/reservations.html`

Action: EDIT

Depends on: T72

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```html
{% block content %}
<div class="saved-views" data-saved-views data-label="{{ t('stays.filter.saved_views') }}"></div>
{% from "_components.html" import page_header, progress_pill, row_menu_begin, row_menu_end, row_reporting_actions, bulk_send_ready, csv_actions_menu, copy_inline, property_identity with context %}
{% set csv_export_params = 'apartment=' ~ (apartment_id or '') %}
{% set view_query = 'range=' ~ date_range ~ '&status=' ~ status ~ '&apartment=' ~ (apartment_id or '') ~ '&from=' ~ (date_from or '') ~ '&to=' ~ (date_to or '') %}
```

Replace with:

```html
{% block content %}
<div class="saved-views" data-saved-views data-label="{{ t('stays.filter.saved_views') }}"></div>
{% from "_components.html" import page_header, progress_pill, row_menu_begin, row_menu_end, row_reporting_actions, bulk_send_ready, csv_actions_menu, copy_inline, property_identity, guest_count with context %}
{% set csv_export_params = 'apartment=' ~ (apartment_id or '') %}
{% set view_query = 'range=' ~ date_range ~ '&status=' ~ status ~ '&apartment=' ~ (apartment_id or '') ~ '&from=' ~ (date_from or '') ~ '&to=' ~ (date_to or '') %}
```

Edit 2 of 2. Find (exactly once):

```html
          {% endif %}
        </td>
        <td class="num" data-label="{{ t('stays.table.guests') }}">{% if progress.expected is not none %}{{ progress.filled }} / {{ progress.expected }}{% else %}<span title="{{ t('common.guests_unknown') }}">—</span>{% endif %}</td>
        <td data-label="{{ t('stays.table.reporting') }}">
          {% if reservation.status != 'active' %}<span class="pill grey">{{ t('stays.filter.state.' ~ reservation.status) }}</span>
```

Replace with:

```html
          {% endif %}
        </td>
        <td class="num" data-label="{{ t('stays.table.guests') }}">{{ guest_count(progress, placeholder=true) }}</td>
        <td data-label="{{ t('stays.table.reporting') }}">
          {% if reservation.status != 'active' %}<span class="pill grey">{{ t('stays.filter.state.' ~ reservation.status) }}</span>
```

Why: Part 2 C. The stays table shows the same count, with a quiet dash and screen-reader text when unknown.

Verify: After T76.

#### T75 Stay page shows the compact guest count

File: `App/app/templates/reservation_detail.html`

Action: EDIT

Depends on: T72

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```html
{% block title %}{{ reservation.internal_name }} · {{ reservation.date_from | date_cz }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header, progress_pill, submission_pill, row_menu_begin, row_menu_end with context %}
<input class="sr-only" type="text" id="stay-link" readonly value="{{ guest_link }}">
{{ page_header(
```

Replace with:

```html
{% block title %}{{ reservation.internal_name }} · {{ reservation.date_from | date_cz }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header, progress_pill, submission_pill, row_menu_begin, row_menu_end, guest_count with context %}
<input class="sr-only" type="text" id="stay-link" readonly value="{{ guest_link }}">
{{ page_header(
```

Edit 2 of 2. Find (exactly once):

```html
{# --- 2. Guests --------------------------------------------------------- #}
<section id="guests">
<div class="section-heading"><h2>{{ t('stay.detail.guests.title') }} <span class="muted">{{ progress.filled }} / {{ progress.expected if progress.expected is not none else '—' }}</span></h2>
  <div class="actions"><a href="#stay-quick-edit" data-open-details>{{ t('host.edit_count') }}</a><a class="btn small" href="/reservations/{{ reservation.id }}/guests/new">+ {{ t('stay.detail.cta.add_guest') }}</a></div>
</div>
```

Replace with:

```html
{# --- 2. Guests --------------------------------------------------------- #}
<section id="guests">
<div class="section-heading"><h2>{{ t('stay.detail.guests.title') }} {{ guest_count(progress, placeholder=true) }}</h2>
  <div class="actions"><a href="#stay-quick-edit" data-open-details>{{ t('host.edit_count') }}</a><a class="btn small" href="/reservations/{{ reservation.id }}/guests/new">+ {{ t('stay.detail.cta.add_guest') }}</a></div>
</div>
```

Why: Part 2 C. The stay page heading shows the same count.

Verify: After T76.

#### T76 Tests for the compact guest count

File: `App/tests/test_overview_headcount.py`

Action: REPLACE ENTIRE FILE

Depends on: T73, T74, T75

Code:

Full content:

```python
"""An unknown guest headcount should read as unknown, not as "0 / ?".

The Overview and Stays lists printed "0 / ?" and left the host to guess what the
question mark meant. The focus card's Czech note counted "%(filled)s /
%(expected)s formulářů hostů", so one registered guest read "1 formulářů hostů".
The Overview now shows nothing until the count is declared; tables show a
quiet dash with the meaning for screen readers.
"""
from __future__ import annotations

from app import db, host_i18n
from tests.test_submission_retry_cap import (  # noqa: F401
    _cleanup,
    _seed,
    host as host,
)

UNKNOWN_EN = "Number of guests not known yet"
UNKNOWN_CS = "Počet hostů zatím neznáme"
LIST_DASH = '<span class="muted" aria-hidden="true">–</span><span class="sr-only">{text}</span>'


def _seed_unknown_headcount(token: str):
    """A stay whose headcount nobody knows, with nobody registered yet."""
    apartment, reservation, _guest = _seed(token)
    db.execute("DELETE FROM guest WHERE reservation_id = ?", (reservation["id"],))
    db.update("reservation", reservation["id"], {"expected_guests_override": None})
    return apartment, reservation


def test_the_overview_says_nothing_about_an_unknown_headcount(host):
    apartment, _reservation = _seed_unknown_headcount("ux147-dash")
    try:
        english = host.get("/?lang=en").text
        czech = host.get("/?lang=cs").text

        assert "0 / ?" not in english
        assert UNKNOWN_EN not in english
        assert UNKNOWN_CS not in czech
    finally:
        _cleanup(apartment["id"])


def test_the_reservations_list_shows_a_quiet_dash(host):
    apartment, _reservation = _seed_unknown_headcount("ux147-list")
    try:
        page = host.get("/reservations?lang=en").text

        assert LIST_DASH.format(text=UNKNOWN_EN) in page
        assert "0 / ?" not in page
    finally:
        _cleanup(apartment["id"])


def test_a_known_headcount_shows_the_count(host):
    apartment, reservation = _seed_unknown_headcount("ux147-known")
    db.update("reservation", reservation["id"], {"expected_guests_override": 3})
    try:
        page = host.get("/?lang=en").text

        assert "0 / 3" in page
    finally:
        _cleanup(apartment["id"])


def test_the_copy_is_in_both_dictionaries():
    assert host_i18n.STRINGS["en"]["common.guests_unknown"] == UNKNOWN_EN
    assert host_i18n.STRINGS["cs"]["common.guests_unknown"] == UNKNOWN_CS
```

Why: Part 2 C. The tests asserted the old sentence; they now assert the compact count and the unknown case.

Verify: `pt tests/test_overview_headcount.py tests/test_dashboard_queue.py tests/test_dashboard_queue_copy.py` passes.

#### T77 Stays list pills ranked by criticality

File: `App/app/templates/reservations.html`

Action: EDIT

Depends on: T74

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```html
            {{ tp('stays.table.nights', nights(reservation.date_from, reservation.date_to)) }}
            {%- if check_in and check_out and check_in <= today() <= check_out %}
              &middot; <span class="pill blue">{{ t('stays.table.in_house') }}</span>
            {%- endif %}
          </div>
```

Replace with:

```html
            {{ tp('stays.table.nights', nights(reservation.date_from, reservation.date_to)) }}
            {%- if check_in and check_out and check_in <= today() <= check_out %}
              &middot; <span class="pill grey">{{ t('stays.table.in_house') }}</span>
            {%- endif %}
          </div>
```

Why: Part 2 B. 'In house' and cancelled are information (neutral), not 'ready'.

Verify: `pt tests/test_status_colours.py` passes.

#### T78 Stay fee detail line pills are neutral

File: `App/app/templates/stay_fee_detail.html`

Action: EDIT

Depends on: T04

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```html
            <div class="small muted">{{ line.stay_from }} – {{ line.stay_to }} · {{ tp('stay_fees.nights', line.nights) }}</div>
          </div>
          <span class="pill {{ 'amber' if line.status == 'liable' else ('grey' if line.status == 'not_subject' else 'green') }}">{{ t(line.status_key) }}</span>
          <span class="fee-amount">{{ line.amount_display }}</span>
          {% if line.local_hint %}
```

Replace with:

```html
            <div class="small muted">{{ line.stay_from }} – {{ line.stay_to }} · {{ tp('stay_fees.nights', line.nights) }}</div>
          </div>
          <span class="pill grey no-dot">{{ t(line.status_key) }}</span>
          <span class="fee-amount">{{ line.amount_display }}</span>
          {% if line.local_hint %}
```

Why: Part 2 B. Line statuses on the stay fee detail page are information, not status calls.

Verify: `pt tests/test_stay_fee_detail.py` passes.

#### T79 Invoice detail pills ranked by criticality

File: `App/app/templates/invoice_detail.html`

Action: EDIT

Depends on: T39

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```html
   the line items, and the destructive fold last. #}
{% if invoice.kind in ('storno', 'corrective') %}
  {% set state_pill = '<span class="pill amber">' ~ t('invoice.kind.' ~ invoice.kind) ~ '</span>' %}
  {% set state_note = t('invoice.detail.note_' ~ invoice.kind) %}
{% elif invoice.marked_paid_at or invoice.paid_on %}
```

Replace with:

```html
   the line items, and the destructive fold last. #}
{% if invoice.kind in ('storno', 'corrective') %}
  {% set state_pill = '<span class="pill grey">' ~ t('invoice.kind.' ~ invoice.kind) ~ '</span>' %}
  {% set state_note = t('invoice.detail.note_' ~ invoice.kind) %}
{% elif invoice.marked_paid_at or invoice.paid_on %}
```

Edit 2 of 2. Find (exactly once):

```html
  {% set state_note = t('invoice.detail.note_paid') %}
{% else %}
  {% set state_pill = '<span class="pill grey">' ~ t('invoice.state.unpaid') ~ '</span>' %}
  {% set state_note = t('invoice.detail.note_unpaid') %}
{% endif %}
```

Replace with:

```html
  {% set state_note = t('invoice.detail.note_paid') %}
{% else %}
  {% set state_pill = '<span class="pill teal">' ~ t('invoice.state.unpaid') ~ '</span>' %}
  {% set state_note = t('invoice.detail.note_unpaid') %}
{% endif %}
```

Why: Part 2 B. Unpaid is waiting on the customer (teal). Storno and corrective documents are information (grey), not a to-do.

Verify: `pt tests/test_invoice_ux.py` passes.

#### T80 Guest register: not sent is waiting

File: `App/app/templates/housebook.html`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```html
          {% elif row.reported == 'NO - rejected, cannot be corrected' %}<span class="pill red">{{ t('stay.detail.guests.rejected_final') }}</span>
          {% elif row.reported.startswith('NO') %}<span class="pill red">{{ t('submission.rejected') }}</span>
          {% else %}<span class="pill amber">{{ t('housebook.not_sent') }}</span>{% endif %}
        </td>
        <td class="nowrap row-actions" data-label="">
```

Replace with:

```html
          {% elif row.reported == 'NO - rejected, cannot be corrected' %}<span class="pill red">{{ t('stay.detail.guests.rejected_final') }}</span>
          {% elif row.reported.startswith('NO') %}<span class="pill red">{{ t('submission.rejected') }}</span>
          {% else %}<span class="pill teal">{{ t('housebook.not_sent') }}</span>{% endif %}
        </td>
        <td class="nowrap row-actions" data-label="">
```

Why: Part 2 B. 'Not sent' in the guest register waits on the system, so it is waiting (teal), not action.

Verify: `pt tests/test_endtoend.py tests/test_csv_safety.py tests/test_status_colours.py` passes.

#### T81 Stay fees list pills ranked by criticality

File: `App/app/templates/stay_fees.html`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```html
        <td class="num" data-label="{{ t('stay_fees.col.total') }}">{{ period.total_display }}</td>
        <td class="nowrap">
          {% if period.issues and period.issues != ['stay_fees.issue.period_running'] %}
            <span class="pill amber">{{ t('stay_fees.needs_setup') }}</span>
          {% else %}
```

Replace with:

```html
        <td class="num" data-label="{{ t('stay_fees.col.total') }}">{{ period.total_display }}</td>
        <td class="nowrap">
          {% if period.frozen %}
            <span class="pill green">{{ t('stay_fees.saved_version', version=period.version) }}</span>
          {% elif period.issues and period.issues != ['stay_fees.issue.period_running'] %}
            <span class="pill amber">{{ t('stay_fees.needs_setup') }}</span>
          {% else %}
```

Why: Part 2 B, A09. The stay fees list shows attention, ready or saved per row.

Verify: `pt tests/test_stay_fee_list.py` passes.

#### T82 Shared filter model

File: `App/app/list_filter.py`

Action: CREATE

Depends on: none

Code:

Full content:

```python
"""One filter model for the host list pages (Stay fee, Invoices).

Both pages share the same controls and behaviour: a month with previous/next
steps, a property, a status, and, on Invoices only, a text search. A page
passes only what genuinely differs: whether a month is required, its default,
the status options and whether search is offered.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Iterable, Optional, Sequence, Tuple
from urllib.parse import urlencode

from . import stay_fee

SEARCH_MAX = 60


@dataclass(frozen=True)
class ListFilter:
    month: Optional[date]
    apartment_id: Optional[int]
    status: str
    q: str
    default_month: Optional[date]

    @property
    def month_key(self) -> str:
        return stay_fee.month_key(self.month) if self.month else ""

    def active_count(self) -> int:
        """Filters that differ from the page's default view."""
        return sum((
            self.month != self.default_month,
            self.apartment_id is not None,
            bool(self.status),
            bool(self.q),
        ))

    def query(self, **changes) -> str:
        """Query string for this view with some fields changed ('' when empty)."""
        view = replace(self, **changes) if changes else self
        params = []
        if view.month:
            params.append(("month", stay_fee.month_key(view.month)))
        if view.apartment_id is not None:
            params.append(("apartment", str(view.apartment_id)))
        if view.status:
            params.append(("status", view.status))
        if view.q:
            params.append(("q", view.q))
        return urlencode(params)


def parse(
    params,
    *,
    today: date,
    statuses: Iterable[str],
    default_month: Optional[date],
    apartment_ids: Iterable[int],
) -> ListFilter:
    """Read the query string; anything unknown or out of range falls back."""
    month = stay_fee.parse_month(params.get("month"))
    if month is not None and not (date(2000, 1, 1) <= month <= today.replace(day=1)):
        month = None
    if month is None:
        month = default_month
    raw_apartment = (params.get("apartment") or "").strip()
    apartment_id = int(raw_apartment) if raw_apartment.isdigit() else None
    if apartment_id not in set(apartment_ids):
        apartment_id = None
    status = (params.get("status") or "").strip()
    if status not in set(statuses):
        status = ""
    q = " ".join((params.get("q") or "").split())[:SEARCH_MAX]
    return ListFilter(month, apartment_id, status, q, default_month)


def context(
    view: ListFilter,
    *,
    action: str,
    today: date,
    period_label_key: str,
    properties: Sequence,
    statuses: Sequence[Tuple[str, str]],
    search: bool = False,
) -> dict:
    """Template context for ``_list_filter.html``."""
    max_month = today.replace(day=1)
    anchor = view.month or max_month
    prev_month = stay_fee.shift_month(anchor, -1)
    next_month = stay_fee.shift_month(anchor, 1)
    has_next = view.month is not None and next_month <= max_month

    def href(**changes) -> str:
        query = view.query(**changes)
        return f"{action}?{query}" if query else action

    return {
        "filter": view,
        "filter_action": action,
        "filter_period_label_key": period_label_key,
        "filter_max_month": stay_fee.month_key(max_month),
        "filter_prev_href": href(month=prev_month),
        "filter_next_href": href(month=next_month) if has_next else None,
        "filter_month_optional": view.default_month is None,
        "filter_properties": properties,
        "filter_statuses": statuses,
        "filter_search": search,
        "filter_active": view.active_count(),
        "filter_reset_href": action,
    }
```

Why: Part 2 A. One bounded state model (month, property, status, search) replaces two month-only implementations. Crafted input falls back to the default.

Verify: After T96: `pt tests/test_list_filter.py` passes.

#### T83 Shared filter component

File: `App/app/templates/_list_filter.html`

Action: CREATE

Depends on: T82

Code:

Full content:

```html
{# The one list filter for Stay fee and Invoices (app/list_filter.py).
   A plain GET form: changes apply on their own, Reset returns to the page's
   default view, and the badge counts what differs from that default. #}
{% set view = filter %}
<form method="get" action="{{ filter_action }}" class="filters panel list-filter" data-auto-submit role="search">
  <div class="field list-filter-period">
    <label for="filter-month">{{ t(filter_period_label_key) }}</label>
    <div class="month-row">
      <a class="btn month-step" href="{{ filter_prev_href }}" aria-label="{{ t('host.filter.prev_month') }}" title="{{ t('host.filter.prev_month') }}">‹</a>
      <div class="month-control{% if not view.month %} is-empty{% endif %}">
        {% if not view.month %}<span class="month-control-face" aria-hidden="true">{{ t('host.filter.all_dates') }}</span>{% endif %}
        <input type="month" id="filter-month" name="month" value="{{ view.month_key }}" max="{{ filter_max_month }}"
               {% if not filter_month_optional %}required{% endif %}>
      </div>
      {% if filter_next_href %}
      <a class="btn month-step" href="{{ filter_next_href }}" aria-label="{{ t('host.filter.next_month') }}" title="{{ t('host.filter.next_month') }}">›</a>
      {% else %}
      <button class="btn month-step" type="button" disabled aria-label="{{ t('host.filter.next_month') }}">›</button>
      {% endif %}
    </div>
  </div>
  {% if filter_properties | length > 1 %}
  <div class="field">
    <label for="filter-apartment">{{ t('stays.filter.apartment') }}</label>
    <select id="filter-apartment" name="apartment">
      <option value="">{{ t('stays.filter.all_apartments') }}</option>
      {% for apartment in filter_properties %}
      <option value="{{ apartment.id }}" {% if view.apartment_id == apartment.id %}selected{% endif %}>{{ apartment.internal_name }}</option>
      {% endfor %}
    </select>
  </div>
  {% endif %}
  {% if filter_statuses %}
  <div class="field">
    <label for="filter-status">{{ t('filter.status') }}</label>
    <select id="filter-status" name="status">
      <option value="">{{ t('stays.filter.all_apartments') }}</option>
      {% for value, label_key in filter_statuses %}
      <option value="{{ value }}" {% if view.status == value %}selected{% endif %}>{{ t(label_key) }}</option>
      {% endfor %}
    </select>
  </div>
  {% endif %}
  {% if filter_search %}
  <div class="field list-filter-search">
    <label for="filter-q">{{ t('filter.search') }}</label>
    <input type="search" id="filter-q" name="q" value="{{ view.q }}" maxlength="60" placeholder="{{ t('invoices.filter.search_placeholder') }}">
  </div>
  {% endif %}
  <div class="field filter-actions filter-actions-end">
    <button class="btn filter-apply" type="submit">{{ t('common.apply') }}</button>
    {% if filter_active %}
    <a class="btn ghost list-filter-reset" href="{{ filter_reset_href }}">{{ t('filter.reset') }} <span class="list-filter-count" aria-label="{{ t('filter.active', count=filter_active) }}">{{ filter_active }}</span></a>
    {% endif %}
  </div>
</form>
```

Why: Part 2 A. One GET form, used by both lists and the stay-fee detail month control. It applies on change and works without JS.

Verify: After T96.

#### T84 Filter copy; drop unused hint keys

File: `App/app/host_i18n.py`

Action: EDIT

Depends on: T59, T83

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 4. Find (exactly once):

```python
        "host.filter.next_month": "Next month",
        "host.filter.all_dates": "All dates",
        "stay_fees.filter.period": "Reporting period",
        "stay_fees.filter.hint": "",
        "stay_fees.setup.title": "Set up stay fee",
        "stay_fees.setup.action": "Set up stay fee",
```

Replace with:

```python
        "host.filter.next_month": "Next month",
        "host.filter.all_dates": "All dates",
        "filter.status": "Status",
        "filter.search": "Search",
        "filter.reset": "Reset",
        "filter.active": "%(count)s active filters",
        "filter.no_results": "Nothing matches these filters.",
        "invoices.filter.search_placeholder": "Number or customer",
        "invoices.filter.corrections": "Corrections",
        "invoice.state.cancelled": "Cancelled",
        "stay_fees.status.saved": "Saved",
        "stay_fees.filter.period": "Reporting period",
        "stay_fees.setup.title": "Set up stay fee",
        "stay_fees.setup.action": "Set up stay fee",
```

Edit 2 of 4. Find (exactly once):

```python
        "entity.signature.scope": "Printed on stay-fee reports.",
        "invoices.filter.period": "Issue month",
        "invoices.filter.hint": "Leave empty and apply to list every invoice, or pick a month to filter by issue date.",
        "stay_fees.col.property": "Property",
        "stay_fees.col.period": "Period",
```

Replace with:

```python
        "entity.signature.scope": "Printed on stay-fee reports.",
        "invoices.filter.period": "Issue month",
        "stay_fees.col.property": "Property",
        "stay_fees.col.period": "Period",
```

Edit 3 of 4. Find (exactly once):

```python
        "host.filter.next_month": "Následující měsíc",
        "host.filter.all_dates": "Všechna data",
        "stay_fees.filter.period": "Vykazované období",
        "stay_fees.filter.hint": "",
        "stay_fees.setup.title": "Nastavit poplatek",
        "stay_fees.setup.action": "Nastavit poplatek",
```

Replace with:

```python
        "host.filter.next_month": "Následující měsíc",
        "host.filter.all_dates": "Všechna data",
        "filter.status": "Stav",
        "filter.search": "Hledat",
        "filter.reset": "Zrušit filtry",
        "filter.active": "Aktivní filtry: %(count)s",
        "filter.no_results": "Těmto filtrům nic neodpovídá.",
        "invoices.filter.search_placeholder": "Číslo nebo odběratel",
        "invoices.filter.corrections": "Opravy a storna",
        "invoice.state.cancelled": "Stornováno",
        "stay_fees.status.saved": "Uloženo",
        "stay_fees.filter.period": "Vykazované období",
        "stay_fees.setup.title": "Nastavit poplatek",
        "stay_fees.setup.action": "Nastavit poplatek",
```

Edit 4 of 4. Find (exactly once):

```python
        "entity.signature.scope": "Tiskne se na hlášení poplatku z pobytu.",
        "invoices.filter.period": "Měsíc vystavení",
        "invoices.filter.hint": "Nechte prázdné a použijte Použít pro všechny faktury, nebo zvolte měsíc podle data vystavení.",
        "stay_fees.col.property": "Nemovitost",
        "stay_fees.col.period": "Období",
```

Replace with:

```python
        "entity.signature.scope": "Tiskne se na hlášení poplatku z pobytu.",
        "invoices.filter.period": "Měsíc vystavení",
        "stay_fees.col.property": "Nemovitost",
        "stay_fees.col.period": "Období",
```

Why: Part 2 A. Labels for status, search, reset and the active count. The two old hint keys are no longer used.

Verify: `pt tests/test_host_i18n.py` passes.

#### T85 Filter styles replace the month-only filter

File: `App/app/static/host.css`

Action: EDIT

Depends on: T69, T83

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```css
.host-workspace .dashboard-stats .stat-ready { background: var(--status-ready-bg); border-color: var(--status-ready-border); color: var(--status-ready-ink); }
.host-workspace .dashboard-stats .stat-waiting { background: var(--status-waiting-bg); border-color: var(--status-waiting-border); color: var(--status-waiting-ink); }
.host-workspace .host-month-filter { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin: 0 auto 18px; padding: 0; border: 0; background: none; }
.host-workspace .host-month-filter label { font-size: 13px; font-weight: 700; color: var(--ink-secondary); }
.host-workspace .host-month-filter input[type=month] { width: 12rem; height: var(--action-height); margin: 0; background: white; border: 1px solid var(--border-strong); border-radius: 9px; padding: 8px 12px; font-weight: 650; }
.host-workspace .month-control { position: relative; display: flex; align-items: center; flex: 0 1 auto; }
.host-workspace .month-control.is-empty { height: var(--action-height); padding: 0 14px; border: 1px dashed var(--border-strong); border-radius: 9px; background: white; }
.host-workspace .month-control.is-empty input[type=month] { position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer; border: 0; }
.host-workspace .month-control-face { font-size: 13.5px; font-weight: 650; color: var(--ink-muted); }
.host-workspace .month-stepper { margin-left: 0; }
.host-workspace .month-stepper .btn { background: transparent; border-color: transparent; color: var(--brand-ink); font-weight: 700; padding-inline: 10px; }
.host-workspace .month-stepper .btn:hover { background: var(--surface-hover); }
.host-workspace .month-stepper .btn[disabled] { color: var(--ink-faint); }
.host-workspace .account-parts, .host-workspace .fee-adjust-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.host-workspace .fee-adjust-reason { grid-column: 1 / -1; }
```

Replace with:

```css
.host-workspace .dashboard-stats .stat-ready { background: var(--status-ready-bg); border-color: var(--status-ready-border); color: var(--status-ready-ink); }
.host-workspace .dashboard-stats .stat-waiting { background: var(--status-waiting-bg); border-color: var(--status-waiting-border); color: var(--status-waiting-ink); }
/* Shared list filter (Stay fee, Invoices): the .filters panel used across the app. */
.host-workspace .list-filter { padding: 14px 16px; }
.host-workspace .list-filter .month-row { display: flex; align-items: center; gap: 4px; }
.host-workspace .list-filter .month-step { width: var(--action-height); min-width: var(--action-height); height: var(--action-height); padding: 0; justify-content: center; font-size: 18px; font-weight: 700; color: var(--brand-ink); }
.host-workspace .list-filter .month-step[disabled] { color: var(--ink-faint); }
.host-workspace .month-control { position: relative; display: flex; align-items: center; flex: 1 1 auto; }
.host-workspace .month-control input[type=month] { width: 100%; min-width: 9.5rem; font-weight: 650; }
.host-workspace .month-control.is-empty { height: var(--action-height); padding: 0 14px; border: 1px dashed var(--border-strong); border-radius: 9px; background: white; }
.host-workspace .month-control.is-empty input[type=month] { position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer; border: 0; }
.host-workspace .month-control-face { font-size: 13.5px; font-weight: 650; color: var(--ink-muted); white-space: nowrap; }
.host-workspace .list-filter .list-filter-period { max-width: 260px; flex-basis: 220px; }
.host-workspace .list-filter .list-filter-search { max-width: 240px; }
.host-workspace .list-filter-count { display: inline-grid; place-items: center; min-width: 20px; height: 20px; margin-left: 6px; padding: 0 6px; border-radius: var(--radius-pill); background: var(--ink); color: var(--canvas); font-size: 12px; font-weight: 700; }
.host-workspace .account-parts, .host-workspace .fee-adjust-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.host-workspace .fee-adjust-reason { grid-column: 1 / -1; }
```

Edit 2 of 2. Find (exactly once):

```css
  .host-workspace .dashboard-stats { grid-template-columns: 1fr 1fr; }
  .host-workspace .account-parts, .host-workspace .fee-adjust-grid { display: grid; grid-template-columns: 1fr; }
  .host-workspace .host-month-filter { row-gap: 8px; }
  .host-workspace .host-month-filter .month-control { flex: 1 1 100%; }
  .host-workspace .host-month-filter .month-control input[type=month] { width: 100%; }
  .host-workspace .month-control.is-empty { width: 100%; }
  .host-workspace .month-stepper { margin-left: 0; }
  .host-workspace .month-stepper .btn { padding-inline: 12px; }
}
```

Replace with:

```css
  .host-workspace .dashboard-stats { grid-template-columns: 1fr 1fr; }
  .host-workspace .account-parts, .host-workspace .fee-adjust-grid { display: grid; grid-template-columns: 1fr; }
  .host-workspace .list-filter .field { flex: 1 1 100%; max-width: none; }
  .host-workspace .list-filter .filter-actions-end { margin-left: 0; }
}
```

Why: Part 2 A. One style block for the shared filter, including the mobile stacking. It replaces .host-month-filter.

Verify: After T95.

#### T86 Filter spacing and search width

File: `App/app/static/host.css`

Action: EDIT

Depends on: T85

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```css
/* Shared list filter (Stay fee, Invoices): the .filters panel used across the app. */
.host-workspace .list-filter { padding: 14px 16px; }
.host-workspace .list-filter .month-row { display: flex; align-items: center; gap: 4px; }
.host-workspace .list-filter .month-step { width: var(--action-height); min-width: var(--action-height); height: var(--action-height); padding: 0; justify-content: center; font-size: 18px; font-weight: 700; color: var(--brand-ink); }
.host-workspace .list-filter .month-step[disabled] { color: var(--ink-faint); }
```

Replace with:

```css
/* Shared list filter (Stay fee, Invoices): the .filters panel used across the app. */
.host-workspace .list-filter { padding: 14px 16px; }
.host-workspace .list-filter .month-row { display: flex; align-items: center; gap: 8px; }
.host-workspace .list-filter .month-step { width: var(--action-height); min-width: var(--action-height); height: var(--action-height); padding: 0; justify-content: center; font-size: 18px; font-weight: 700; color: var(--brand-ink); }
.host-workspace .list-filter .month-step[disabled] { color: var(--ink-faint); }
```

Edit 2 of 2. Find (exactly once):

```css
.host-workspace .month-control-face { font-size: 13.5px; font-weight: 650; color: var(--ink-muted); white-space: nowrap; }
.host-workspace .list-filter .list-filter-period { max-width: 260px; flex-basis: 220px; }
.host-workspace .list-filter .list-filter-search { max-width: 240px; }
.host-workspace .list-filter-count { display: inline-grid; place-items: center; min-width: 20px; height: 20px; margin-left: 6px; padding: 0 6px; border-radius: var(--radius-pill); background: var(--ink); color: var(--canvas); font-size: 12px; font-weight: 700; }
.host-workspace .account-parts, .host-workspace .fee-adjust-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
```

Replace with:

```css
.host-workspace .month-control-face { font-size: 13.5px; font-weight: 650; color: var(--ink-muted); white-space: nowrap; }
.host-workspace .list-filter .list-filter-period { max-width: 260px; flex-basis: 220px; }
.host-workspace .list-filter .list-filter-search { max-width: 240px; min-width: 200px; flex-basis: 200px; }
.host-workspace .list-filter-count { display: inline-grid; place-items: center; min-width: 20px; height: 20px; margin-left: 6px; padding: 0 6px; border-radius: var(--radius-pill); background: var(--ink); color: var(--canvas); font-size: 12px; font-weight: 700; }
.host-workspace .account-parts, .host-workspace .fee-adjust-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
```

Why: Part 2 A. Keeps controls from clipping at 1024 px.

Verify: After T95: `pt tests/test_host_geometry.py` passes with a browser installed.

#### T87 Invoices use the shared filter

File: `App/app/routes/invoices.py`

Action: EDIT

Depends on: T38, T82, T84

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 6. Find (exactly once):

```python
    invoice_links,
    invoices,
    list_month_filter,
    mail,
    mail_notify,
```

Replace with:

```python
    invoice_links,
    invoices,
    list_filter,
    mail,
    mail_notify,
```

Edit 2 of 6. Find (exactly once):

```python
    rate_limit,
    security,
)

```

Replace with:

```python
    rate_limit,
    security,
    stay_fee,
)

```

Edit 3 of 6. Find (exactly once):

```python


@router.get("/invoices")
def invoices_list(request: Request):
```

Replace with:

```python


INVOICE_STATUSES = (
    ("unpaid", "invoice.state.unpaid"),
    ("paid", "invoice.state.paid"),
    ("correction", "invoices.filter.corrections"),
)
_CANCELLED = (
    "EXISTS (SELECT 1 FROM invoice c WHERE c.corrects_invoice_id = invoice.id "
    "AND c.kind = 'storno')"
)
_PAID = "(paid_on IS NOT NULL OR marked_paid_at IS NOT NULL)"
_STATUS_SQL = {
    "unpaid": f"kind = 'invoice' AND NOT {_PAID} AND NOT {_CANCELLED}",
    "paid": f"kind = 'invoice' AND {_PAID}",
    "correction": "kind IN ('storno', 'corrective')",
}


@router.get("/invoices")
def invoices_list(request: Request):
```

Edit 4 of 6. Find (exactly once):

```python
        return guard
    today = claim.prague_today()
    selected_month = list_month_filter.parse_month_param(request.query_params.get("month"))
    if selected_month and selected_month > today.replace(day=1):
        return RedirectResponse("/invoices", status_code=303)
    owner_id = access.owner_id(request)
    page_size = 50
    try:
```

Replace with:

```python
        return guard
    today = claim.prague_today()
    owner_id = access.owner_id(request)
    properties = db.query(
        "SELECT id, internal_name FROM apartment WHERE owner_user_id IS ? AND archived_at IS NULL "
        "ORDER BY internal_name, id",
        (owner_id,),
    )
    view = list_filter.parse(
        request.query_params,
        today=today,
        statuses=_STATUS_SQL,
        default_month=None,
        apartment_ids=[row["id"] for row in properties],
    )
    page_size = 50
    try:
```

Edit 5 of 6. Find (exactly once):

```python
    except ValueError:
        page_no = 1
    offset = (page_no - 1) * page_size
    if selected_month:
        first, last = list_month_filter.month_bounds(selected_month)
        where, params = (
            "owner_user_id IS ? AND issue_date >= ? AND issue_date <= ?",
            (owner_id, first.isoformat(), last.isoformat()),
        )
    else:
        where, params = "owner_user_id IS ?", (owner_id,)
    total = int(db.query_one(f"SELECT COUNT(*) AS n FROM invoice WHERE {where}", params)["n"])
    rows = db.query(
        f"SELECT * FROM invoice WHERE {where} ORDER BY issue_date DESC, id DESC LIMIT ? OFFSET ?",
        (*params, page_size, offset),
    )
    pages = max((total + page_size - 1) // page_size, 1)
    return render(
        request,
```

Replace with:

```python
    except ValueError:
        page_no = 1
    where, params = ["owner_user_id IS ?"], [owner_id]
    if view.month:
        first, last = stay_fee.period_bounds("monthly", view.month)
        where.append("issue_date >= ? AND issue_date <= ?")
        params += [first.isoformat(), last.isoformat()]
    if view.apartment_id is not None:
        where.append("apartment_id = ?")
        params.append(view.apartment_id)
    if view.status:
        where.append(_STATUS_SQL[view.status])
    if view.q:
        where.append("(instr(lower(number), ?) > 0 OR instr(lower(buyer_name), ?) > 0)")
        params += [view.q.lower(), view.q.lower()]
    clause = " AND ".join(where)
    total = int(db.query_one(f"SELECT COUNT(*) AS n FROM invoice WHERE {clause}", params)["n"])
    rows = db.query(
        "SELECT id, number, issue_date, buyer_name, kind, total_haler, "
        f"CASE WHEN kind != 'invoice' THEN 'correction' WHEN {_PAID} THEN 'paid' "
        f"WHEN {_CANCELLED} THEN 'cancelled' ELSE 'unpaid' END AS state "
        f"FROM invoice WHERE {clause} ORDER BY issue_date DESC, id DESC LIMIT ? OFFSET ?",
        (*params, page_size, (page_no - 1) * page_size),
    )
    pages = max((total + page_size - 1) // page_size, 1)
    query = view.query()
    page_href = "/invoices?" + (query + "&" if query else "") + "page="
    return render(
        request,
```

Edit 6 of 6. Find (exactly once):

```python
            "invoice_page": page_no,
            "invoice_pages": pages,
            "filter_id": "invoice-list",
            "form_action": "/invoices",
            "period_label_key": "invoices.filter.period",
            "hint_label_key": "invoices.filter.hint",
            **list_month_filter.month_filter_nav(
                selected_month, today, month_required=False
            ),
        },
```

Replace with:

```python
            "invoice_page": page_no,
            "invoice_pages": pages,
            "page_href": page_href,
            **list_filter.context(
                view,
                action="/invoices",
                today=today,
                period_label_key="invoices.filter.period",
                properties=properties,
                statuses=INVOICE_STATUSES,
                search=True,
            ),
        },
```

Why: Part 2 A, A49. Status and search filters for invoices. The list selects explicit columns, so the PDF blob is never read.

Verify: After T93.

#### T88 Invoices list: shared filter and status column

File: `App/app/templates/invoices.html`

Action: REPLACE ENTIRE FILE

Depends on: T83, T87

Code:

Full content:

```html
{% extends "base.html" %}
{% set nav = 'invoices' %}
{% block title %}{{ t('invoices.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header with context %}
{{ page_header(t('invoices.title'), t('invoices.lede'), '', '', '',
    '<a class="btn accent primary" href="/invoices/new">' ~ t('invoice.new') ~ '</a>') }}
{% include "_list_filter.html" %}
{% if invoices %}
<div class="panel tight scroll-x">
  <table class="table-cards">
    <thead>
      <tr>
        <th>{{ t('invoices.col.number') }}</th>
        <th>{{ t('invoices.col.date') }}</th>
        <th class="col-name">{{ t('invoices.col.customer') }}</th>
        <th>{{ t('invoices.col.kind') }}</th>
        <th>{{ t('invoices.col.total') }}</th>
        <th>{{ t('filter.status') }}</th>
        <th><span class="sr-only">{{ t('common.actions') }}</span></th>
      </tr>
    </thead>
    <tbody>
    {% for inv in invoices %}
      <tr class="clickable-row" data-href="/invoices/{{ inv.id }}" tabindex="0" role="link">
        <td class="mono small" data-label="{{ t('invoices.col.number') }}"><a href="/invoices/{{ inv.id }}">{{ inv.number }}</a></td>
        <td class="nowrap small" data-label="{{ t('invoices.col.date') }}">{{ inv.issue_date | date_cz }}</td>
        <td class="col-name" data-label="{{ t('invoices.col.customer') }}">{{ inv.buyer_name }}</td>
        <td class="small" data-label="{{ t('invoices.col.kind') }}">{{ t('invoice.kind.' ~ inv.kind) }}</td>
        <td class="num" data-label="{{ t('invoices.col.total') }}">{{ inv.total_haler | money_czk }}</td>
        <td data-label="{{ t('filter.status') }}">{% if inv.state == 'paid' %}<span class="pill green">{{ t('invoice.state.paid') }}</span>{% elif inv.state == 'unpaid' %}<span class="pill teal">{{ t('invoice.state.unpaid') }}</span>{% elif inv.state == 'cancelled' %}<span class="pill grey">{{ t('invoice.state.cancelled') }}</span>{% else %}<span class="pill grey">{{ t('invoice.kind.' ~ inv.kind) }}</span>{% endif %}</td>
        <td class="row-actions" data-label=""><a class="btn small" href="/invoices/{{ inv.id }}.pdf">{{ t('host.invoice_pdf') }}</a></td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</div>
{% if invoice_pages > 1 %}
<nav class="action-group" aria-label="{{ t('invoices.title') }}">
  {% if invoice_page > 1 %}
  <a class="btn" href="{{ page_href }}{{ invoice_page - 1 }}" aria-label="{{ invoice_page - 1 }}">‹</a>
  {% endif %}
  {% if invoice_page < invoice_pages %}
  <a class="btn" href="{{ page_href }}{{ invoice_page + 1 }}" aria-label="{{ invoice_page + 1 }}">›</a>
  {% endif %}
</nav>
{% endif %}
{% else %}
<div class="panel empty">
  {% if filter_active %}
  <h2>{{ t('filter.no_results') }}</h2>
  <a class="btn" href="{{ filter_reset_href }}">{{ t('filter.reset') }}</a>
  {% else %}
  <h2>{{ t('invoices.empty_title') }}</h2>
  <p class="lede">{{ t('invoices.empty') }}</p>
  {% endif %}
</div>
{% endif %}
{% endblock %}
```

Why: Part 2 A, A70. Invoices get the shared filter, a status column, pagination that keeps the filter, and a filtered empty state.

Verify: After T93.

#### T89 Stay fees use the shared filter

File: `App/app/routes/stay_fees.py`

Action: EDIT

Depends on: T32, T82, T84

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 6. Find (exactly once):

```python
    db,
    host_i18n,
    list_month_filter,
    payments,
    security,
```

Replace with:

```python
    db,
    host_i18n,
    list_filter,
    payments,
    security,
```

Edit 2 of 6. Find (exactly once):

```python


def _month_filter_template(
    selected_month: date,
    today: date,
    *,
    form_action: str = "/stay-fees",
    filter_id: str = "stay-fee-period",
) -> dict:
    return {
        "filter_id": filter_id,
        "form_action": form_action,
        "period_label_key": "stay_fees.filter.period",
        "hint_label_key": "stay_fees.filter.hint",
        **list_month_filter.month_filter_nav(
            selected_month, today, month_required=True
        ),
    }
```

Replace with:

```python


STAY_FEE_STATUSES = (
    ("attention", "stay_fees.needs_setup"),
    ("ready", "stay_fees.status.ready"),
    ("saved", "stay_fees.status.saved"),
)


def _row_status(row: dict) -> str:
    if row["unset"]:
        return "attention"
    if row.get("frozen"):
        return "saved"
    if row["issues"] and row["issues"] != ["stay_fees.issue.period_running"]:
        return "attention"
    return "ready"


def _detail_filter(selected_month: date, today: date, apartment_id: int) -> dict:
    """The detail page uses the same control, month only."""
    view = list_filter.ListFilter(selected_month, None, "", "", selected_month)
    return {
        "month_key": stay_fee.month_key(selected_month),
        **list_filter.context(
            view,
            action=f"/stay-fees/{apartment_id}",
            today=today,
            period_label_key="stay_fees.filter.period",
            properties=(),
            statuses=(),
        ),
    }
```

Edit 3 of 6. Find (exactly once):

```python

    today = claim.prague_today()
    default_month = _default_month(today)
    selected_month = stay_fee.parse_month(request.query_params.get("month"))
    if selected_month is None:
        selected_month = default_month
    elif selected_month > today.replace(day=1):
        return RedirectResponse(
            f"/stay-fees?month={stay_fee.month_key(default_month)}",
            status_code=303,
        )

    owner_id = access.owner_id(request)
    periods = stay_fee.owner_periods(owner_id, selected_month)
    rows = []
    for period in periods:
        apartment = period["apartment"]
        group = stay_fee.report_group(apartment, selected_month, period=period)
```

Replace with:

```python

    today = claim.prague_today()
    owner_id = access.owner_id(request)
    apartments = db.query(
        "SELECT * FROM apartment WHERE owner_user_id IS ? AND archived_at IS NULL "
        "AND active = 1 ORDER BY internal_name, id",
        (owner_id,),
    )
    view = list_filter.parse(
        request.query_params,
        today=today,
        statuses=[value for value, _ in STAY_FEE_STATUSES],
        default_month=_default_month(today),
        apartment_ids=[row["id"] for row in apartments],
    )
    selected_month = view.month
    rows = []
    for period in stay_fee.owner_periods(owner_id, selected_month):
        apartment = period["apartment"]
        group = stay_fee.report_group(apartment, selected_month, period=period)
```

Edit 4 of 6. Find (exactly once):

```python
        })
    configured = {row["apartment"]["id"] for row in rows}
    apartments = db.query(
        "SELECT * FROM apartment WHERE owner_user_id IS ? AND archived_at IS NULL "
        "AND active = 1 ORDER BY internal_name, id",
        (owner_id,),
    )
    for apartment in apartments:
        if apartment["id"] not in configured:
            rows.append({"apartment": apartment, "unset": True})
    rows.sort(key=lambda row: (row["apartment"]["internal_name"] or "", row["apartment"]["id"]))

```

Replace with:

```python
        })
    configured = {row["apartment"]["id"] for row in rows}
    for apartment in apartments:
        if apartment["id"] not in configured:
            rows.append({"apartment": apartment, "unset": True, "issues": []})
    for row in rows:
        row["status"] = _row_status(row)
    rows = [
        row for row in rows
        if (view.apartment_id is None or row["apartment"]["id"] == view.apartment_id)
        and (not view.status or row["status"] == view.status)
    ]
    rows.sort(key=lambda row: (row["apartment"]["internal_name"] or "", row["apartment"]["id"]))

```

Edit 5 of 6. Find (exactly once):

```python
        "selected_month": selected_month,
        "has_properties": bool(apartments),
        **_month_filter_template(selected_month, today),
    })

```

Replace with:

```python
        "selected_month": selected_month,
        "has_properties": bool(apartments),
        **list_filter.context(
            view,
            action="/stay-fees",
            today=today,
            period_label_key="stay_fees.filter.period",
            properties=apartments,
            statuses=STAY_FEE_STATUSES,
        ),
    })

```

Edit 6 of 6. Find (exactly once):

```python
        "nav": "stay_fees",
        "apartment": apartment,
        **_month_filter_template(
            selected_month,
            today,
            form_action=f"/stay-fees/{apartment_id}",
            filter_id="stay-fee-detail-period",
        ),
        "period": period,
        "group": group,
```

Replace with:

```python
        "nav": "stay_fees",
        "apartment": apartment,
        **_detail_filter(selected_month, today, apartment_id),
        "period": period,
        "group": group,
```

Why: Part 2 A. Stay fees get property and status filters. A future month falls back to the default instead of redirecting.

Verify: After T94.

#### T90 Stay fees list: shared filter and row status

File: `App/app/templates/stay_fees.html`

Action: EDIT

Depends on: T81, T89

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 3. Find (exactly once):

```html
{% from "_components.html" import page_header with context %}
{{ page_header(t('stay_fees.title'), '', '', '', '', '') }}
{% include "_host_month_filter.html" %}
{% if periods %}
<div class="panel tight scroll-x">
```

Replace with:

```html
{% from "_components.html" import page_header with context %}
{{ page_header(t('stay_fees.title'), '', '', '', '', '') }}
{% include "_list_filter.html" %}
{% if periods %}
<div class="panel tight scroll-x">
```

Edit 2 of 3. Find (exactly once):

```html
        <td class="num" data-label="{{ t('stay_fees.col.total') }}">{{ period.total_display }}</td>
        <td class="nowrap">
          {% if period.frozen %}
            <span class="pill green">{{ t('stay_fees.saved_version', version=period.version) }}</span>
          {% elif period.issues and period.issues != ['stay_fees.issue.period_running'] %}
            <span class="pill amber">{{ t('stay_fees.needs_setup') }}</span>
          {% else %}
```

Replace with:

```html
        <td class="num" data-label="{{ t('stay_fees.col.total') }}">{{ period.total_display }}</td>
        <td class="nowrap">
          {% if period.status == 'saved' %}
            <span class="pill green">{{ t('stay_fees.saved_version', version=period.version) }}</span>
          {% elif period.status == 'attention' %}
            <span class="pill amber">{{ t('stay_fees.needs_setup') }}</span>
          {% else %}
```

Edit 3 of 3. Find (exactly once):

```html
{% else %}
<div class="panel empty">
  <h2>{{ t('stay_fees.empty_title') }}</h2>
  <a class="btn primary" href="/apartments/new">{{ t('apartments.add') }}</a>
</div>
{% endif %}
```

Replace with:

```html
{% else %}
<div class="panel empty">
  {% if filter_active and has_properties %}
  <h2>{{ t('filter.no_results') }}</h2>
  <a class="btn" href="{{ filter_reset_href }}">{{ t('filter.reset') }}</a>
  {% else %}
  <h2>{{ t('stay_fees.empty_title') }}</h2>
  <a class="btn primary" href="/apartments/new">{{ t('apartments.add') }}</a>
  {% endif %}
</div>
{% endif %}
```

Why: Part 2 A, A09. Stay fees list: the shared filter plus a status per row.

Verify: After T94.

#### T91 Stay fee detail uses the shared month control

File: `App/app/templates/stay_fee_detail.html`

Action: EDIT

Depends on: T78, T89

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```html
{% from "_components.html" import page_header, copy_button with context %}
<a class="back-link" href="/stay-fees?month={{ month_key }}"><span aria-hidden="true">&larr;</span> {{ t('stay_fees.back') }}</a>
{% include "_host_month_filter.html" %}
{% set actions %}
  {% if frozen %}
```

Replace with:

```html
{% from "_components.html" import page_header, copy_button with context %}
<a class="back-link" href="/stay-fees?month={{ month_key }}"><span aria-hidden="true">&larr;</span> {{ t('stay_fees.back') }}</a>
{% include "_list_filter.html" %}
{% set actions %}
  {% if frozen %}
```

Why: Part 2 A. The detail page uses the same month control, so moving between months looks the same everywhere.

Verify: `pt tests/test_stay_fee_detail.py` passes.

#### T92 Crafted months before 2000 are ignored

File: `App/app/stay_fee.py`

Action: EDIT

Depends on: T05, T31

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python
        return None
    try:
        return date(int(text[:4]), int(text[5:]), 1)
    except ValueError:
        return None


```

Replace with:

```python
        return None
    try:
        month = date(int(text[:4]), int(text[5:]), 1)
    except ValueError:
        return None
    # Earlier years only come from a crafted link and break month arithmetic.
    return month if month.year >= 2000 else None


```

Why: A14. `?month=0001-01` crashed both list pages.

Verify: `pt tests/test_stay_fee.py` passes.

#### T93 Tests: invoices filter

File: `App/tests/test_invoice_ux.py`

Action: EDIT

Depends on: T88

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```python
    assert "2026-0009" in all_page.text
    assert 'type="month"' in all_page.text
    assert "host-month-filter" in all_page.text
    assert "month-control is-empty" in all_page.text
    assert "All dates" in all_page.text

    august = host.get("/invoices?month=2026-08")
```

Replace with:

```python
    assert "2026-0009" in all_page.text
    assert 'type="month"' in all_page.text
    assert "list-filter" in all_page.text
    assert "month-control is-empty" in all_page.text
    assert "All dates" in all_page.text
    assert "list-filter-reset" not in all_page.text

    august = host.get("/invoices?month=2026-08")
```

Edit 2 of 2. Find (exactly once):

```python
    assert 'value="2026-08"' in august.text
    assert "month-control is-empty" not in august.text
    assert 'href="/invoices"' in august.text  # All dates when filtered


```

Replace with:

```python
    assert 'value="2026-08"' in august.text
    assert "month-control is-empty" not in august.text
    assert 'class="btn ghost list-filter-reset" href="/invoices"' in august.text

    unpaid = host.get("/invoices?status=unpaid&q=0009")
    assert "2026-0009" in unpaid.text
    assert "2026-0008" not in unpaid.text
    assert host.get("/invoices?status=paid").text.count("/invoices/") < all_page.text.count("/invoices/")


```

Why: Part 2 A. The invoice UX tests used the old filter markup.

Verify: `pt tests/test_invoice_ux.py` passes.

#### T94 Tests: stay fees filter

File: `App/tests/test_stay_fee_list.py`

Action: EDIT

Depends on: T90

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```python
    assert 'href="/stay-fees?month=2026-09"' in response.text
    assert 'class="chip' not in response.text
    assert "host-month-filter" in response.text


```

Replace with:

```python
    assert 'href="/stay-fees?month=2026-09"' in response.text
    assert 'class="chip' not in response.text
    assert "list-filter" in response.text


```

Edit 2 of 2. Find (exactly once):

```python


def test_future_month_redirects_to_default(host):
    client, _owner_id, _entity_id = host

    response = client.get("/stay-fees?month=2026-10", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/stay-fees?month=2026-08"


```

Replace with:

```python


def test_future_or_crafted_month_falls_back_to_default(host):
    client, _owner_id, _entity_id = host

    for month in ("2026-10", "0001-01"):
        response = client.get(f"/stay-fees?month={month}", follow_redirects=False)

        assert response.status_code == 200
        assert 'value="2026-08"' in response.text


```

Why: Part 2 A. A future or crafted month now falls back to the default.

Verify: `pt tests/test_stay_fee_list.py` passes.

#### T95 Tests: filter geometry

File: `App/tests/test_host_geometry.py`

Action: EDIT

Depends on: T86, T88, T90

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 3. Find (exactly once):

```python
        for route in ("/stay-fees?lang=en", "/invoices?lang=en"):
            page.goto(base + route)
            page.wait_for_selector(".host-month-filter", timeout=30000)
            measured[route] = page.evaluate(
                """() => {
```

Replace with:

```python
        for route in ("/stay-fees?lang=en", "/invoices?lang=en"):
            page.goto(base + route)
            page.wait_for_selector(".list-filter", timeout=30000)
            measured[route] = page.evaluate(
                """() => {
```

Edit 2 of 3. Find (exactly once):

```python
                    return [Math.round(rect.left), Math.round(rect.right)];
                  };
                  const filter = box('.host-month-filter');
                  const control = box('.month-control');
                  const stepper = box('.month-stepper');
                  return {
                    filter: edges('.host-month-filter'),
                    table: edges('.panel, table'),
                    title: edges('.page-header, h1'),
```

Replace with:

```python
                    return [Math.round(rect.left), Math.round(rect.right)];
                  };
                  const filter = box('.list-filter');
                  const control = box('.month-control');
                  const stepper = box('.month-row .month-step:last-child');
                  return {
                    filter: edges('.list-filter'),
                    table: edges('.panel, table'),
                    title: edges('.page-header, h1'),
```

Edit 3 of 3. Find (exactly once):

```python
                    route = f"{path}?lang={lang}"
                    page.goto(base + route)
                    page.wait_for_selector(".host-month-filter", timeout=30000)
                    responsive[(width, route)] = page.evaluate(
                        """() => {
                          const root = document.documentElement;
                          const filter = document.querySelector('.host-month-filter');
                          const bounds = filter.getBoundingClientRect();
                          const children = [...filter.children].filter(
                            (element) => getComputedStyle(element).display !== 'none'
                          );
                          const buttons = [...filter.querySelectorAll('.month-stepper .btn')];
                          return {
                            overflow: root.scrollWidth > root.clientWidth + 1,
```

Replace with:

```python
                    route = f"{path}?lang={lang}"
                    page.goto(base + route)
                    page.wait_for_selector(".list-filter", timeout=30000)
                    responsive[(width, route)] = page.evaluate(
                        """() => {
                          const root = document.documentElement;
                          const filter = document.querySelector('.list-filter');
                          const bounds = filter.getBoundingClientRect();
                          const children = [...filter.children].filter(
                            (element) => getComputedStyle(element).display !== 'none'
                          );
                          const buttons = [...filter.querySelectorAll('.month-step')];
                          return {
                            overflow: root.scrollWidth > root.clientWidth + 1,
```

Why: Part 2 A. The geometry test checks the new selectors at 1280, 1024, 390 and 360 px in EN and CS.

Verify: `pt tests/test_host_geometry.py` passes (UBYHOST_REQUIRE_BROWSER=1).

#### T96 Tests: filter model

File: `App/tests/test_list_filter.py`

Action: CREATE

Depends on: T82

Code:

Full content:

```python
"""The shared Stay fee / Invoices filter model."""
from __future__ import annotations

from datetime import date

from app import list_filter

TODAY = date(2026, 9, 15)


def _parse(params, default=None):
    return list_filter.parse(
        params, today=TODAY, statuses=("paid", "unpaid"), default_month=default, apartment_ids=(4, 7)
    )


def test_unknown_values_fall_back_to_the_default_view():
    view = _parse({"month": "2027-01", "apartment": "99", "status": "bogus", "q": "  "}, date(2026, 8, 1))
    assert (view.month, view.apartment_id, view.status, view.q) == (date(2026, 8, 1), None, "", "")
    assert view.active_count() == 0


def test_active_filters_are_counted_and_kept_in_links():
    view = _parse({"month": "2026-07", "apartment": "7", "status": "paid", "q": "Novák  s.r.o."})
    assert view.q == "Novák s.r.o."
    assert view.active_count() == 4
    ctx = list_filter.context(view, action="/invoices", today=TODAY, period_label_key="x",
                              properties=(), statuses=(), search=True)
    assert ctx["filter_prev_href"].startswith("/invoices?month=2026-06&apartment=7&status=paid&q=")
    assert ctx["filter_next_href"].startswith("/invoices?month=2026-08&")
    assert ctx["filter_reset_href"] == "/invoices"


def test_no_next_month_past_the_current_one():
    view = _parse({"month": "2026-09"})
    ctx = list_filter.context(view, action="/stay-fees", today=TODAY, period_label_key="x",
                              properties=(), statuses=())
    assert ctx["filter_next_href"] is None
```

Why: Part 2 A. Unit tests for parsing bounds, ownership of the property filter, and the query builder.

Verify: `pt tests/test_list_filter.py` passes.

#### T97 An unchecked ID stays ready (blue)

File: `App/app/templates/_components.html`

Action: EDIT

Depends on: T72

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```html
  } %}
  {# Tone follows criticality (tokens.css): red critical, amber host action,
     blue ready, teal waiting on the guest, green done, grey neutral. #}
  {% set tones = {
    'failed': 'red',
```

Replace with:

```html
  } %}
  {# Tone follows criticality (tokens.css): red critical, amber host action,
     blue ready (the ID check is optional, so an unchecked ID is still ready),
     teal waiting on the guest, green done, grey neutral. #}
  {% set tones = {
    'failed': 'red',
```

Edit 2 of 2. Find (exactly once):

```html
    'not_required': 'grey',
    'awaiting_guest': 'teal',
    'awaiting_verification': 'amber'
  } %}
  {% set tone = tones.get(status, 'grey') %}
```

Replace with:

```html
    'not_required': 'grey',
    'awaiting_guest': 'teal',
    'awaiting_verification': 'blue'
  } %}
  {% set tone = tones.get(status, 'grey') %}
```

Why: Part 2 B. The ID check is optional, so a stay with an unchecked ID is still ready. An existing test enforces blue.

Verify: `pt tests/test_status_colours.py` passes.

#### T98 Docs: criticality colours in DESIGN.md

File: `docs/DESIGN.md`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```markdown
|---|---|
| Next-action card | One sentence, one coral button, and an optional "Why?" link. There is at most one on a page. |
| Status pill | A dot plus the fixed status word, in semantic colours (green ready/done, amber waiting, coral needs you, red rejected). One per row. |
| Side panel | Opens from the right on desktop and as a full sheet on a phone. It has a title, the form, and a sticky footer with the primary button and Cancel. `Esc` closes it. Unsaved changes ask before closing. |
| Toast | Bottom-left, 6 seconds, "Saved — Undo". It never carries an error that needs action; those stay on the page. |
```

Replace with:

```markdown
|---|---|
| Next-action card | One sentence, one coral button, and an optional "Why?" link. There is at most one on a page. |
| Status pill | A dot plus the fixed status word, coloured by criticality from the `--status-*` tokens in `tokens.css`: solid red with "!" = critical (failed, rejected, overdue), amber = host action, blue = ready, teal = waiting on the guest or payer, green = done, white outline = neutral. One per row. |
| Side panel | Opens from the right on desktop and as a full sheet on a phone. It has a title, the form, and a sticky footer with the primary button and Cancel. `Esc` closes it. Unsaved changes ask before closing. |
| Toast | Bottom-left, 6 seconds, "Saved — Undo". It never carries an error that needs action; those stay on the page. |
```

Why: Part 2 B. The design doc must name the same six levels as tokens.css.

Verify: `grep -n 'status-critical' docs/DESIGN.md` finds the row.

#### T99 Help & Guide text in EN and CS

File: `App/app/guide_i18n.py`

Action: CREATE

Depends on: none

Code:

Full content:

```python
"""Help & guide copy (templates/guide.html), English and Czech.

Every sentence describes behaviour in the code. When a feature changes,
change its paragraph here in the same commit.
"""

GUIDE_STRINGS = {
    "en": {
        "guide.title": "Help & guide",
        "guide.lede": "How UbyHost works, page by page. Short answers first.",
        "guide.nav.overview": "Dashboard",
        "guide.nav.statuses": "What the colours mean",
        "guide.nav.setup": "First-time setup",
        "guide.nav.stays": "Stays & calendars",
        "guide.nav.guests": "Guest check-in",
        "guide.nav.reporting": "Police reporting",
        "guide.nav.filters": "Filters on Stay fees and Invoices",
        "guide.nav.housebook": "Guest register",
        "guide.nav.stay_fee": "Stay fees",
        "guide.nav.invoices": "Invoices",
        "guide.nav.settings": "Settings & security",
        "guide.nav.faster": "Faster work",
        "guide.nav.faq": "Common questions",
        "guide.nav.legal": "Your legal duties",
        "guide.nav.demo": "Demo data",

        "guide.overview.body": "The Dashboard lists the stays that need you first, then stays waiting for guests, upcoming arrivals and finished stays. The four tiles count what needs action, what waits for guests, what is ready to send and what is overdue.",
        "guide.overview.count": "The person icon shows registered guests against the expected number, for example 2 / 3. Calendars never include a guest count, so nothing is shown until the guest states the group size or you set it on the stay.",
        "guide.overview.deadline": "Each row shows the time left until the police deadline. Red means less than a day or already late.",

        "guide.statuses.lede": "The stronger the colour, the more it needs you. Every badge also has a word, so colour is never the only signal.",
        "guide.statuses.failed": "UbyPort rejected the record, the delivery failed or the outcome is unknown. Open the stay and act.",
        "guide.statuses.incomplete": "A guest started the form but something is missing, such as the signature or the document number.",
        "guide.statuses.ready": "Everything is complete. In Manual mode you press Send this stay; in the automatic modes UbyHost sends it. Checking the ID is optional.",
        "guide.statuses.waiting": "Nobody has registered yet, or the remaining guests have not filled in their forms.",
        "guide.statuses.reported": "UbyPort accepted every foreign guest of the stay.",
        "guide.statuses.not_required": "Only Czech guests. They go into the guest register but are not reported to the police.",
        "guide.statuses.other": "The same scale is used everywhere: house book rows, reports, properties, stay fees and invoices. Amber always means you can fix something; grey is information only.",

        "guide.setup.step1_title": "Operator",
        "guide.setup.step1": "Under Properties, Business & legal details: the person or company registered with the police, with seat, IČO and contact.",
        "guide.setup.step2_title": "Property",
        "guide.setup.step2": "Name and address. The address and the UbyPort details must match the police letter exactly.",
        "guide.setup.step3_title": "Calendars",
        "guide.setup.step3": "Paste the iCal export link from Airbnb, Booking.com or another portal. Stays are imported and synced automatically.",
        "guide.setup.step4_title": "UbyPort and automation",
        "guide.setup.step4": "Under Property tools, Automation & UbyPort: the IDUB, mark, web-service login and password from the police letter, and when to send. Use Save and test connection to check the login.",
        "guide.setup.step5_title": "Guest link",
        "guide.setup.step5": "Under Property tools, Guest links: one permanent link and a 6-digit PIN per property. Copy the ready-made message into your check-in message on every portal.",

        "guide.stays.body": "Stays come from your calendars, or you add them with Add stay. Update calendars fetches all feeds now. Filter by property, state and dates, save a view in this browser, and export the filtered stays as CSV.",
        "guide.stays.detail": "Open a stay to add or remove guests, copy the guest link, send the report, change the expected number of guests, set the state (active, cancelled, ignored), reopen guest access or release the assignment, and create an invoice.",
        "guide.stays.cancelled": "If a booking disappears from the calendar or is cancelled, the stay is cancelled and never reported. If guests had already filled in forms, you get a warning: when the booking only moved, set the stay back to Active.",

        "guide.guests.body": "Guests open your property link on their phone and follow these steps:",
        "guide.guests.step_pin": "Enter the PIN you sent them.",
        "guide.guests.step_pick": "Pick their stay by dates. Stays arriving today and in the next two days are offered.",
        "guide.guests.step_claim": "The lead guest states the group size and an e-mail address, then confirms from the e-mail. The stay then opens on that device only.",
        "guide.guests.step_form": "Each person, children included, fills in their own form: personal details, travel document, home address, a photo of the document when the property asks for it, and a signature.",
        "guide.guests.step_mail": "Guests get the private link, one reminder the day before arrival if forms are still incomplete, and a copy when all forms are done. You get an e-mail and an alert on arrival day if forms are still missing.",
        "guide.guests.czech": "Czech guests fill in the same form. They go into the guest register and are not reported.",
        "guide.guests.cookies": "The guest's phone remembers the PIN for 7 days, and the language, the claimed stay and submitted forms for 60 days.",
        "guide.guests.photo": "Document photos are off by default. When a property requires them for foreign guests, the photo is deleted when you verify the guest, or 30 days after the stay. It is never sent to UbyPort.",

        "guide.reporting.body": "Each property chooses when completed foreign guests are sent to UbyPort:",
        "guide.reporting.immediate": "Immediately",
        "guide.reporting.immediate_detail": "Sent as soon as every declared guest form is complete.",
        "guide.reporting.scheduled": "Scheduled",
        "guide.reporting.scheduled_detail": "Sent a chosen number of hours (0 to 48) after the forms are complete, and never later than six hours before the deadline.",
        "guide.reporting.manual": "Manual",
        "guide.reporting.manual_detail": "Nothing is sent until you press Send this stay or Send all ready stays.",
        "guide.reporting.deadline": "The deadline is the end of the third working day, counting the arrival day when it is a working day. Weekends and Czech public holidays do not count.",
        "guide.reporting.failure": "If UbyPort is down, UbyHost retries on its own and alerts you. If UbyPort refuses the login, automatic sending for that property pauses until you save or test new credentials. If the answer never arrives, the guests are held and you decide whether to send again, so nothing is reported twice.",
        "guide.reporting.receipts": "Police reports lists every report with its Doručenka receipt. You can download receipts one by one or as a ZIP for a date range.",

        "guide.filters.body": "Stay fees and Invoices share the same filter. Changes apply as soon as you pick them.",
        "guide.filters.month": "Month: use the arrows for the previous or next month. Stay fees always show one period (the last finished month by default). Invoices show all dates until you pick a month.",
        "guide.filters.property": "Property: shown when you have more than one.",
        "guide.filters.status": "Status: on Stay fees needs setup, ready or saved; on Invoices awaiting payment, paid or corrections.",
        "guide.filters.search": "Search (Invoices only): part of the invoice number or the customer name, then Enter.",
        "guide.filters.reset": "The number on Reset shows how many filters are active. Reset returns to the default view.",

        "guide.housebook.body": "The guest register lists every guest, Czech and foreign, with their reporting state. Filter by property and dates, export CSV, or download signed PDFs as a ZIP (up to 100 at a time) for an inspection.",

        "guide.stay_fee.body": "A property takes part once you set its rate per night (up to 50 CZK). Set monthly or quarterly reporting, the variable symbol, the council account and the authority's details.",
        "guide.stay_fee.rules": "Guests under 18 on a night are exempt. You can exempt a guest for a legal reason, or charge one. Stays over 60 nights are not subject to the fee; an exactly 60-night stay needs your council's ruling first.",
        "guide.stay_fee.save": "When the period has ended and nothing is missing, press Save period. That fixes the report PDF, the guest register CSV and the payment QR. Start correction creates a new version; adjustments add or remove bed-nights without naming guests.",

        "guide.invoices.body": "Create an invoice for any stay or customer. The seller is one of your operators; VAT rates appear only for VAT payers. An invoice has up to four items so it fits one page.",
        "guide.invoices.flow": "Preview, then issue: the number is assigned per operator and year and cannot be changed. Afterwards you can record payment, e-mail it with a download link valid for 30 days, download the PDF, or cancel it with a cancellation or corrective document.",

        "guide.settings.body": "Settings hold your password and two-factor sign-in, the guest PIN setting, archived records, data protection (retention and deleting expired records), the activity log and technical details.",
        "guide.settings.two_factor": "Two-factor sign-in uses an authenticator app. Store the recovery codes somewhere safe; each works once.",
        "guide.settings.retention": "Guest records are kept 6 years after the stay, invoices 10 years. Document photos go after 30 days, raw police request data after 90 days.",
        "guide.settings.requests": "Data requests records a guest's GDPR request and its one-month deadline.",

        "guide.faster.search": "Press Ctrl+K (Cmd+K on a Mac) or / to search pages, properties, stays and reports.",
        "guide.faster.shortcuts": "Press ? for keyboard shortcuts: g d Dashboard, g s Stays, g r Police reports, g h Guest register, j and k to move between rows, Enter to open one.",

        "guide.faq.link_q": "A guest says the link does not work.",
        "guide.faq.link_a": "Check they have the current PIN under Guest links. Their stay is offered from the arrival day minus two days. If someone else claimed it, use Release assignment on the stay.",
        "guide.faq.count_q": "Why is there no guest count?",
        "guide.faq.count_a": "Calendars do not include it. It appears once the lead guest states the group size, or when you set it on the stay.",
        "guide.faq.czech_q": "Why was a stay not reported?",
        "guide.faq.czech_a": "Czech guests are not reported. Otherwise check the status: incomplete forms, Manual mode, or a paused login stop sending.",
        "guide.faq.twice_q": "Can a guest be reported twice?",
        "guide.faq.twice_a": "Not by UbyHost on its own. When the police answer is unclear, the guests wait for you instead of being resent.",
        "guide.faq.edit_q": "A guest made a mistake after the report was sent.",
        "guide.faq.edit_a": "Correct it on the stay and send again. Records the police rejected can be corrected and are retried up to three times.",

        "guide.demo.body": "Press Explore with demo data to try every screen with sample properties and stays. Demo records are never sent to the police. Use Clear demo data on the Dashboard when you are done.",
    },
    "cs": {
        "guide.title": "Nápověda a průvodce",
        "guide.lede": "Jak UbyHost funguje, stránku po stránce. Nejdřív krátké odpovědi.",
        "guide.nav.overview": "Přehled",
        "guide.nav.statuses": "Co znamenají barvy",
        "guide.nav.setup": "První nastavení",
        "guide.nav.stays": "Pobyty a kalendáře",
        "guide.nav.guests": "Registrace hostů",
        "guide.nav.reporting": "Hlášení policii",
        "guide.nav.filters": "Filtry v poplatcích a fakturách",
        "guide.nav.housebook": "Kniha hostů",
        "guide.nav.stay_fee": "Poplatky z pobytu",
        "guide.nav.invoices": "Faktury",
        "guide.nav.settings": "Nastavení a zabezpečení",
        "guide.nav.faster": "Rychlejší práce",
        "guide.nav.faq": "Časté otázky",
        "guide.nav.legal": "Vaše zákonné povinnosti",
        "guide.nav.demo": "Ukázková data",

        "guide.overview.body": "Přehled ukazuje nejdřív pobyty, které potřebují vás, pak pobyty čekající na hosty, nadcházející příjezdy a hotové pobyty. Čtyři dlaždice počítají, co vyžaduje akci, co čeká na hosty, co je připraveno k odeslání a co je po termínu.",
        "guide.overview.count": "Ikona osoby ukazuje registrované hosty proti očekávanému počtu, například 2 / 3. Kalendáře počet hostů neuvádějí, takže se nic nezobrazí, dokud host neuvede velikost skupiny nebo ji nenastavíte u pobytu.",
        "guide.overview.deadline": "Každý řádek ukazuje čas do termínu hlášení. Červená znamená méně než den nebo už po termínu.",

        "guide.statuses.lede": "Čím výraznější barva, tím víc to potřebuje vás. Každý štítek má i slovo, barva tedy nikdy není jediný signál.",
        "guide.statuses.failed": "UbyPort záznam odmítl, doručení selhalo nebo výsledek není známý. Otevřete pobyt a jednejte.",
        "guide.statuses.incomplete": "Host začal vyplňovat, ale něco chybí, třeba podpis nebo číslo dokladu.",
        "guide.statuses.ready": "Vše je vyplněné. V ručním režimu stisknete Odeslat tento pobyt, v automatických režimech odešle UbyHost. Kontrola dokladu je volitelná.",
        "guide.statuses.waiting": "Zatím se nikdo nezaregistroval nebo zbývající hosté nevyplnili formulář.",
        "guide.statuses.reported": "UbyPort přijal všechny cizince z pobytu.",
        "guide.statuses.not_required": "Jen čeští hosté. Jsou v knize hostů, ale policii se nehlásí.",
        "guide.statuses.other": "Stejná škála platí všude: kniha hostů, hlášení, ubytování, poplatky i faktury. Jantarová vždy znamená, že můžete něco opravit; šedá je jen informace.",

        "guide.setup.step1_title": "Ubytovatel",
        "guide.setup.step1": "V Ubytování, Firma a právní údaje: osoba nebo firma registrovaná u policie, se sídlem, IČO a kontaktem.",
        "guide.setup.step2_title": "Ubytování",
        "guide.setup.step2": "Název a adresa. Adresa a údaje UbyPortu musí přesně odpovídat dopisu od policie.",
        "guide.setup.step3_title": "Kalendáře",
        "guide.setup.step3": "Vložte odkaz na export iCal z Airbnb, Booking.com nebo jiného portálu. Pobyty se načtou a synchronizují samy.",
        "guide.setup.step4_title": "UbyPort a automatizace",
        "guide.setup.step4": "V Nástrojích ubytování, Automatizace a UbyPort: IDUB, zkratka, přihlášení a heslo k webové službě z dopisu od policie a kdy odesílat. Přihlášení ověříte tlačítkem Uložit a otestovat spojení.",
        "guide.setup.step5_title": "Odkaz pro hosty",
        "guide.setup.step5": "V Nástrojích ubytování, Odkazy pro hosty: jeden trvalý odkaz a šestimístný PIN pro každé ubytování. Připravenou zprávu vložte do zprávy k příjezdu na každém portálu.",

        "guide.stays.body": "Pobyty přicházejí z kalendářů, nebo je přidáte tlačítkem Přidat pobyt. Aktualizovat kalendáře je načte hned. Filtrujte podle ubytování, stavu a dat, uložte si pohled v tomto prohlížeči a vyfiltrované pobyty exportujte do CSV.",
        "guide.stays.detail": "Na pobytu přidáte nebo odeberete hosty, zkopírujete odkaz pro hosty, odešlete hlášení, změníte očekávaný počet hostů, nastavíte stav (aktivní, zrušený, ignorovaný), znovu otevřete přístup hostům nebo uvolníte přiřazení a vystavíte fakturu.",
        "guide.stays.cancelled": "Když rezervace z kalendáře zmizí nebo je zrušená, pobyt se zruší a nikdy se nenahlásí. Pokud už hosté vyplnili formuláře, dostanete upozornění: když se rezervace jen přesunula, nastavte pobyt zpět na Aktivní.",

        "guide.guests.body": "Hosté otevřou odkaz vašeho ubytování v telefonu a projdou tyto kroky:",
        "guide.guests.step_pin": "Zadají PIN, který jste jim poslali.",
        "guide.guests.step_pick": "Vyberou svůj pobyt podle dat. Nabízejí se pobyty s příjezdem dnes a v příštích dvou dnech.",
        "guide.guests.step_claim": "Hlavní host uvede velikost skupiny a e-mail a potvrdí ho z e-mailu. Pobyt se pak otevře jen na tomto zařízení.",
        "guide.guests.step_form": "Každý, i děti, vyplní vlastní formulář: osobní údaje, cestovní doklad, adresu bydliště, fotku dokladu, pokud ji ubytování vyžaduje, a podpis.",
        "guide.guests.step_mail": "Hosté dostanou soukromý odkaz, jednu připomínku den před příjezdem, pokud formuláře nejsou hotové, a kopii, když je vše vyplněno. Vy dostanete e-mail a upozornění v den příjezdu, pokud formuláře chybí.",
        "guide.guests.czech": "Čeští hosté vyplní stejný formulář. Jsou v knize hostů a nehlásí se.",
        "guide.guests.cookies": "Telefon hosta si pamatuje PIN 7 dní a jazyk, převzatý pobyt a odeslané formuláře 60 dní.",
        "guide.guests.photo": "Fotky dokladů jsou ve výchozím stavu vypnuté. Když je ubytování u cizinců vyžaduje, fotka se smaže po ověření hosta nebo 30 dní po pobytu. Nikdy se neposílá do UbyPortu.",

        "guide.reporting.body": "Každé ubytování si volí, kdy se vyplnění cizinci odešlou do UbyPortu:",
        "guide.reporting.immediate": "Ihned",
        "guide.reporting.immediate_detail": "Odešle se, jakmile jsou hotové formuláře všech uvedených hostů.",
        "guide.reporting.scheduled": "Naplánovaně",
        "guide.reporting.scheduled_detail": "Odešle se zvolený počet hodin (0 až 48) po vyplnění, nejpozději šest hodin před termínem.",
        "guide.reporting.manual": "Ručně",
        "guide.reporting.manual_detail": "Nic se neodešle, dokud nestisknete Odeslat tento pobyt nebo Odeslat všechny připravené.",
        "guide.reporting.deadline": "Termín je konec třetího pracovního dne, počítá se i den příjezdu, pokud je pracovní. Víkendy a české svátky se nepočítají.",
        "guide.reporting.failure": "Když UbyPort nefunguje, UbyHost to zkouší znovu sám a upozorní vás. Když UbyPort odmítne přihlášení, automatické odesílání pro toto ubytování se zastaví, dokud neuložíte nebo neotestujete nové údaje. Když odpověď nepřijde, hosté se podrží a o novém odeslání rozhodnete vy, aby se nic nenahlásilo dvakrát.",
        "guide.reporting.receipts": "Hlášení policii obsahují každé hlášení s doručenkou. Doručenky stáhnete jednotlivě nebo jako ZIP za zvolené období.",

        "guide.filters.body": "Poplatky z pobytu a Faktury mají stejný filtr. Změny se použijí hned po výběru.",
        "guide.filters.month": "Měsíc: šipkami přejdete na předchozí nebo další měsíc. Poplatky vždy ukazují jedno období (výchozí je poslední skončený měsíc). Faktury ukazují všechna data, dokud měsíc nevyberete.",
        "guide.filters.property": "Ubytování: zobrazí se, když jich máte víc.",
        "guide.filters.status": "Stav: u poplatků doplnit údaje, připraveno nebo uloženo; u faktur čeká na platbu, zaplaceno nebo opravy a storna.",
        "guide.filters.search": "Hledat (jen u faktur): část čísla faktury nebo jména odběratele, pak Enter.",
        "guide.filters.reset": "Číslo u Zrušit filtry ukazuje počet aktivních filtrů. Tlačítko vrátí výchozí pohled.",

        "guide.housebook.body": "Kniha hostů obsahuje všechny hosty, české i zahraniční, se stavem hlášení. Filtrujte podle ubytování a dat, exportujte CSV nebo stáhněte podepsaná PDF jako ZIP (až 100 najednou) pro kontrolu.",

        "guide.stay_fee.body": "Ubytování se zapojí, jakmile nastavíte sazbu za noc (až 50 Kč). Nastavte měsíční nebo čtvrtletní vykazování, variabilní symbol, účet obce a údaje úřadu.",
        "guide.stay_fee.rules": "Hosté mladší 18 let jsou za danou noc osvobozeni. Hosta můžete osvobodit ze zákonného důvodu, nebo naopak zpoplatnit. Pobyty delší než 60 nocí poplatku nepodléhají; pobyt na přesně 60 nocí potřebuje nejdřív výklad vaší obce.",
        "guide.stay_fee.save": "Když období skončí a nic nechybí, stiskněte Uložit období. Tím se zafixuje PDF hlášení, CSV evidence a QR platba. Opravit vytvoří novou verzi; úpravy přidají nebo uberou lůžkodny bez jmen hostů.",

        "guide.invoices.body": "Fakturu vystavíte k jakémukoli pobytu nebo odběrateli. Dodavatelem je jeden z vašich ubytovatelů; sazby DPH se zobrazí jen plátcům. Faktura má nejvýše čtyři položky, aby se vešla na jednu stránku.",
        "guide.invoices.flow": "Náhled, pak vystavení: číslo se přidělí podle ubytovatele a roku a nejde změnit. Potom můžete zaznamenat platbu, poslat ji e-mailem s odkazem ke stažení platným 30 dní, stáhnout PDF nebo ji zrušit stornem či opravným dokladem.",

        "guide.settings.body": "Nastavení obsahuje heslo a dvoufázové přihlášení, nastavení PINu pro hosty, archiv, ochranu dat (doba uchování a mazání prošlých záznamů), protokol činnosti a technické údaje.",
        "guide.settings.two_factor": "Dvoufázové přihlášení používá ověřovací aplikaci. Záložní kódy si uložte na bezpečné místo; každý platí jednou.",
        "guide.settings.retention": "Záznamy hostů se uchovávají 6 let po pobytu, faktury 10 let. Fotky dokladů se mažou po 30 dnech, surová data hlášení po 90 dnech.",
        "guide.settings.requests": "Žádosti o data zaznamenávají žádost hosta podle GDPR a její měsíční lhůtu.",

        "guide.faster.search": "Stiskněte Ctrl+K (na Macu Cmd+K) nebo / a hledejte stránky, ubytování, pobyty a hlášení.",
        "guide.faster.shortcuts": "Stiskněte ? pro klávesové zkratky: g d Přehled, g s Pobyty, g r Hlášení policii, g h Kniha hostů, j a k pro pohyb mezi řádky, Enter pro otevření.",

        "guide.faq.link_q": "Host říká, že odkaz nefunguje.",
        "guide.faq.link_a": "Ověřte, že má aktuální PIN z Odkazů pro hosty. Pobyt se nabízí od dvou dnů před příjezdem. Pokud ho převzal někdo jiný, použijte na pobytu Uvolnit přiřazení.",
        "guide.faq.count_q": "Proč se nezobrazuje počet hostů?",
        "guide.faq.count_a": "Kalendáře ho neuvádějí. Zobrazí se, jakmile hlavní host uvede velikost skupiny, nebo když ho nastavíte u pobytu.",
        "guide.faq.czech_q": "Proč se pobyt nenahlásil?",
        "guide.faq.czech_a": "Čeští hosté se nehlásí. Jinak zkontrolujte stav: odesílání zastaví nehotové formuláře, ruční režim nebo pozastavené přihlášení.",
        "guide.faq.twice_q": "Může se host nahlásit dvakrát?",
        "guide.faq.twice_a": "Sám od sebe ne. Když odpověď policie není jasná, hosté čekají na vás a znovu se neposílají.",
        "guide.faq.edit_q": "Host se spletl a hlášení už odešlo.",
        "guide.faq.edit_a": "Opravte údaje na pobytu a odešlete znovu. Záznamy, které policie odmítla, lze opravit a zkouší se až třikrát.",

        "guide.demo.body": "Tlačítkem Prohlédnout s ukázkovými daty vyzkoušíte všechny obrazovky s ukázkovými ubytováními a pobyty. Ukázkové záznamy se policii nikdy neposílají. Až skončíte, použijte na Přehledu Smazat ukázková data.",
    },
}
```

Why: Part 2 D. Guide copy written from the routes and templates, with identical keys in both languages.

Verify: After T107: `pt tests/test_guide.py tests/test_host_i18n.py` passes.

#### T100 Guide template

File: `App/app/templates/guide.html`

Action: REPLACE ENTIRE FILE

Depends on: T99

Code:

Full content:

```html
{% extends "base.html" %}
{% set nav = 'guide' %}
{% block title %}{{ t('guide.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header with context %}
{{ page_header(t('guide.title'), t('guide.lede')) }}

{% set sections = ['overview', 'statuses', 'setup', 'stays', 'guests', 'reporting', 'filters', 'housebook', 'stay_fee', 'invoices', 'settings', 'faster', 'faq', 'legal'] + (['demo'] if demo_available else []) %}
<div class="guide-layout">
  <nav class="guide-nav panel" aria-label="{{ t('guide.title') }}">
    {% for key in sections %}<a href="#{{ key }}" class="guide-nav-link">{{ t('guide.nav.' ~ key) }}</a>{% endfor %}
  </nav>

  <div class="guide-content">
    <section class="guide-section panel" id="overview">
      <h2>{{ t('guide.nav.overview') }}</h2>
      <p>{{ t('guide.overview.body') }}</p>
      <p>{{ t('guide.overview.count') }}</p>
      <p>{{ t('guide.overview.deadline') }}</p>
    </section>

    <section class="guide-section panel" id="statuses">
      <h2>{{ t('guide.nav.statuses') }}</h2>
      <p>{{ t('guide.statuses.lede') }}</p>
      <dl class="kv guide-statuses">
        {% for tone, label_key, body_key in [
          ('red', 'status.failed', 'guide.statuses.failed'),
          ('amber', 'status.incomplete', 'guide.statuses.incomplete'),
          ('blue', 'status.ready', 'guide.statuses.ready'),
          ('teal', 'status.awaiting_guest_short', 'guide.statuses.waiting'),
          ('green', 'status.reported', 'guide.statuses.reported'),
          ('grey', 'status.not_required', 'guide.statuses.not_required')] %}
        <dt><span class="pill {{ tone }}">{{ t(label_key) }}</span></dt>
        <dd>{{ t(body_key) }}</dd>
        {% endfor %}
      </dl>
      <p class="small muted">{{ t('guide.statuses.other') }}</p>
    </section>

    <section class="guide-section panel" id="setup">
      <h2>{{ t('guide.nav.setup') }}</h2>
      <ol class="guide-steps">
        {% for n in range(1, 6) %}
        <li><strong>{{ t('guide.setup.step' ~ n ~ '_title') }}</strong> — {{ t('guide.setup.step' ~ n) }}</li>
        {% endfor %}
      </ol>
    </section>

    <section class="guide-section panel" id="stays">
      <h2>{{ t('guide.nav.stays') }}</h2>
      <p>{{ t('guide.stays.body') }}</p>
      <p>{{ t('guide.stays.detail') }}</p>
      <p class="small muted">{{ t('guide.stays.cancelled') }}</p>
    </section>

    <section class="guide-section panel" id="guests">
      <h2>{{ t('guide.nav.guests') }}</h2>
      <p>{{ t('guide.guests.body') }}</p>
      <ol class="guide-steps">
        {% for step in ['pin', 'pick', 'claim', 'form'] %}<li>{{ t('guide.guests.step_' ~ step) }}</li>{% endfor %}
      </ol>
      <p>{{ t('guide.guests.step_mail') }}</p>
      <p>{{ t('guide.guests.czech') }}</p>
      <p class="small muted">{{ t('guide.guests.photo') }}</p>
      <p class="small muted">{{ t('guide.guests.cookies') }}</p>
    </section>

    <section class="guide-section panel" id="reporting">
      <h2>{{ t('guide.nav.reporting') }}</h2>
      <p>{{ t('guide.reporting.body') }}</p>
      <dl class="kv">
        {% for mode in ['immediate', 'scheduled', 'manual'] %}
        <dt>{{ t('guide.reporting.' ~ mode) }}</dt>
        <dd>{{ t('guide.reporting.' ~ mode ~ '_detail') }}</dd>
        {% endfor %}
      </dl>
      <p>{{ t('guide.reporting.deadline') }}</p>
      <p>{{ t('guide.reporting.failure') }}</p>
      <p class="small muted">{{ t('guide.reporting.receipts') }}</p>
    </section>

    <section class="guide-section panel" id="filters">
      <h2>{{ t('guide.nav.filters') }}</h2>
      <p>{{ t('guide.filters.body') }}</p>
      <ul class="guide-steps">
        {% for item in ['month', 'property', 'status', 'search', 'reset'] %}<li>{{ t('guide.filters.' ~ item) }}</li>{% endfor %}
      </ul>
    </section>

    <section class="guide-section panel" id="housebook">
      <h2>{{ t('guide.nav.housebook') }}</h2>
      <p>{{ t('guide.housebook.body') }}</p>
      <p class="small muted">{{ t('housebook.legal_footnote') }}</p>
    </section>

    <section class="guide-section panel" id="stay_fee">
      <h2>{{ t('guide.nav.stay_fee') }}</h2>
      <p>{{ t('guide.stay_fee.body') }}</p>
      <p>{{ t('guide.stay_fee.rules') }}</p>
      <p>{{ t('guide.stay_fee.save') }}</p>
    </section>

    <section class="guide-section panel" id="invoices">
      <h2>{{ t('guide.nav.invoices') }}</h2>
      <p>{{ t('guide.invoices.body') }}</p>
      <p>{{ t('guide.invoices.flow') }}</p>
    </section>

    <section class="guide-section panel" id="settings">
      <h2>{{ t('guide.nav.settings') }}</h2>
      <p>{{ t('guide.settings.body') }}</p>
      <ul class="guide-steps">
        {% for item in ['two_factor', 'retention', 'requests'] %}<li>{{ t('guide.settings.' ~ item) }}</li>{% endfor %}
      </ul>
    </section>

    <section class="guide-section panel" id="faster">
      <h2>{{ t('guide.nav.faster') }}</h2>
      <ul class="guide-steps">
        <li>{{ t('guide.faster.search') }}</li>
        <li>{{ t('guide.faster.shortcuts') }}</li>
      </ul>
    </section>

    <section class="guide-section panel" id="faq">
      <h2>{{ t('guide.nav.faq') }}</h2>
      <dl class="kv">
        {% for item in ['link', 'count', 'czech', 'twice', 'edit'] %}
        <dt>{{ t('guide.faq.' ~ item ~ '_q') }}</dt>
        <dd>{{ t('guide.faq.' ~ item ~ '_a') }}</dd>
        {% endfor %}
      </dl>
    </section>

    <section class="guide-section panel guide-legal" id="legal">
      <h2>{{ t('guide.nav.legal') }}</h2>
      <p class="lede">{{ t('guide.legal.lede') }}</p>
      {% for item in ['housebook', 'paper', 'signature', 'verification', 'reporting', 'retention'] %}
      <h3>{{ t('guide.legal.' ~ item ~ '_title') }}</h3>
      <p>{{ t('guide.legal.' ~ item ~ '_body') }}</p>
      {% endfor %}
      <div class="legal-disclaimer panel quiet">
        <h3>{{ t('guide.legal.disclaimer_title') }}</h3>
        <p class="small muted">{{ t('guide.legal.disclaimer_body') }}</p>
      </div>
    </section>

    {% if demo_available %}
    <section class="guide-section panel" id="demo">
      <h2>{{ t('guide.nav.demo') }}</h2>
      <p>{{ t('guide.demo.body') }}</p>
      <form method="post" action="/demo" class="inline">
        <button class="btn primary" type="submit">{{ t('demo.load') }}</button>
      </form>
    </section>
    {% endif %}
  </div>
</div>
{% endblock %}
```

Why: Part 2 D. One loop over the sections. The status section renders the real pills, the legal section is kept, and demo data appears only where it works.

Verify: After T107.

#### T101 Guide shows demo data only where it works

File: `App/app/routes/admin.py`

Action: EDIT

Depends on: T26, T100

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python
    if guard:
        return guard
    return render(request, "guide.html")


```

Replace with:

```python
    if guard:
        return guard
    return render(request, "guide.html", {"demo_available": config.UBYPORT_ENV == "mock"})


```

Why: Part 2 D. Demo loading needs the mock UbyPort, so the guide hides it elsewhere.

Verify: After T107.

#### T102 Load the new guide copy; drop the old

File: `App/app/host_i18n.py`

Action: EDIT

Depends on: T84, T99

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 7. Find (exactly once):

```python
        ),
        "celebration.dismiss": "Thanks!",
        "guide.title": "Help & guide",
        "guide.lede": "Everything you need to run guest reporting calmly, from setup to the house book.",
        "guide.nav.overview": "Overview",
        "guide.nav.productivity": "Faster everyday work",
        "guide.nav.setup": "First-time setup",
        "guide.nav.stays": "Stays & calendars",
        "guide.nav.guests": "Guest forms",
        "guide.nav.reporting": "Police reporting",
        "guide.nav.housebook": "House book",
        "guide.nav.security": "Security & backups",
        "guide.nav.demo": "Demo data",
        "guide.overview.body": (
            "Overview shows what needs attention now: missing guest forms, stays ready to report, "
            "and deadlines. Stays lists every booking; Reports keeps Doručenka receipts."
        ),
        "guide.overview.caption": "The next-up card shows the most urgent stay and its send button.",
        "guide.productivity.search": (
            "Press Ctrl+K (or Cmd+K on a Mac) to search and jump to a property, stay, guest, or page."
        ),
        "guide.productivity.shortcuts": (
            "Open the ? menu at the bottom of the sidebar for navigation and table keyboard shortcuts."
        ),
        "guide.productivity.views": (
            "On Stays, switch between List and Timeline, set filters, and choose Save view to "
            "keep a useful view for next time."
        ),
        "guide.productivity.quick_edit": (
            "Open a stay for its guest link, Add a guest, reporting controls, and the compact Quick edit panel."
        ),
        "guide.setup.step1_title": "Operator",
        "guide.setup.step1": "The company or person registered with the police.",
        "guide.setup.step2_title": "Property",
        "guide.setup.step2": "IDUB, mark, and address must match UbyPort exactly.",
        "guide.setup.step3_title": "Calendars",
        "guide.setup.step3": "Paste Airbnb or Booking.com iCal export links.",
        "guide.setup.step4_title": "UbyPort credentials",
        "guide.setup.step4": (
            "Enter the UBY-WS web-service login from the police letter on the property page. "
            "The annotated sample shows the exact fields; leaving an already-saved password blank keeps it."
        ),
        "guide.setup.step5_title": "Guest link",
        "guide.setup.step5": "Put the permalink in your check-in message on every portal.",
        "guide.stays.body": (
            "Stays arrive from calendars or manual entry. Open a row to add guests, copy the guest link, "
            "or send completed records."
        ),
        "guide.stays.csv": (
            "Use Export stays (CSV) in the filter bar for a spreadsheet copy. House book offers CSV "
            "and an inspection PDF bundle from its Export menu. Exports respect the current filters."
        ),
        "guide.guests.body": (
            "Each stay has a guest link meant for a phone. Guests pick their arrival dates, the lead "
            "guest states how many people are staying, claims the reservation by e-mail, then each "
            "person fills in a short step-by-step form. An incomplete claimed form remains reachable "
            "after check-in until it is completed or you explicitly lock guest access."
        ),
        "guide.guests.step_email": (
            "The e-mail receives the private form link, one reminder if incomplete the day before "
            "check-in, and a completion receipt. The host gets a completion copy; public screens "
            "mask the address. Necessary guest cookies preserve PIN access for up to 7 days and "
            "language, confirmed-stay access, and forms submitted on the device for up to 60 days."
        ),
        "guide.guests.step_party": (
            "Headcount first — everyone in the group, including children, gets a separate form so "
            "nobody sees anyone else's passport details. The count is stored with the stay to measure "
            "whether all expected forms are complete and follows the stay's retention."
        ),
        "guide.guests.step_details": (
            "Each guest types name, birth date, nationality, and document number as printed on the "
            "travel document (no scanning or machine-readable line copying)."
        ),
        "guide.guests.step_photo": (
            "Passport/ID upload is off by default. A property can require a temporary image or PDF "
            "from foreign guests; it is never sent to UbyPort."
        ),
        "guide.guests.step_czech": (
            "Czech guests are still written to the house book but are not reported to the police."
        ),
        "guide.reporting.body": "Each property chooses how completed guest records reach UbyPort:",
        "guide.reporting.caption": (
            "Passport checking is an optional explicit host action. Automatic reporting follows "
            "the completion timing you choose and does not wait for that check."
        ),
        "guide.reporting.immediate": "Immediately after completion",
        "guide.reporting.immediate_detail": (
            "Sent automatically as soon as every declared guest form is complete, "
            "without waiting for host verification."
        ),
        "guide.legal.verification_title": "Verify every foreign guest",
        "guide.legal.verification_body": (
```

Replace with:

```python
        ),
        "celebration.dismiss": "Thanks!",
        "guide.legal.verification_title": "Verify every foreign guest",
        "guide.legal.verification_body": (
```

Edit 2 of 7. Find (exactly once):

```python
            "refuse accommodation."
        ),
        "guide.reporting.scheduled": "Scheduled",
        "guide.reporting.scheduled_detail": "Sent automatically after your chosen delay from completion.",
        "guide.reporting.manual": "Manual",
        "guide.reporting.manual_detail": "You click Send on the stay or use Send all ready stays.",
        "guide.reporting.bulk": (
            "Send all ready stays only sends stays that are complete and allowed by the automation mode — "
            "it never forces a partial stay."
        ),
        "guide.housebook.body": (
            "The house book lists every guest — Czech and foreign. Export CSV or download PDFs for "
            "inspections from the Export menu. Import is currently unavailable."
        ),
        "guide.security.two_factor": (
            "Enable two-factor authentication in Settings with an authenticator app, and store the "
            "one-time recovery codes somewhere safe."
        ),
        "guide.security.turnstile": (
            "Production sits behind Cloudflare: Turnstile on sign-in and after repeated guest PIN "
            "failures, Bot Fight Mode, leaked-credential checks on login, HSTS, and client-side "
            "script monitoring. Legitimate visitors may occasionally see a short challenge."
        ),
        "guide.security.passports": (
            "Passport/ID upload is off by default. When enabled, access is restricted to authorised "
            "host users in the app; the file is deleted after verification, with a stale-file sweep "
            "as a backstop. It is never sent to UbyPort."
        ),
        "guide.security.backups": (
            "The Settings \u201cData protection\u201d panel (platform administrators only) shows when "
            "the last backup ran, whether it was encrypted, and the retention window. Keep an "
            "independent export before closing the service or making major changes."
        ),
        "guide.nav.legal": "Your legal duties",
        "guide.legal.lede": (
            "UbyHost helps you comply, but the accommodation provider remains legally responsible. "
```

Replace with:

```python
            "refuse accommodation."
        ),
        "guide.legal.lede": (
            "UbyHost helps you comply, but the accommodation provider remains legally responsible. "
```

Edit 3 of 7. Find (exactly once):

```python
            "Software questions: support@ubyhost.com. Guests with a stay question should use "
            "the host name, e-mail, and phone shown on the guest form."
        ),
        "guide.demo.body": (
            "Load demo data to explore both sample properties: mail claim, assigned stays, late "
            "incomplete forms, the optional passport toggle, a separate controller, and reporting. "
            "On staging, open Settings → Guest e-mails for the confirmation links. Demo guests are "
            "never sent to the real police register."
        ),
        "a11y.skip_to_content": "Skip to main content",
```

Replace with:

```python
            "Software questions: support@ubyhost.com. Guests with a stay question should use "
            "the host name, e-mail, and phone shown on the guest form."
        ),
        "a11y.skip_to_content": "Skip to main content",
```

Edit 4 of 7. Find (exactly once):

```python
        ),
        "celebration.dismiss": "Díky!",
        "guide.title": "Nápověda a průvodce",
        "guide.lede": "Vše pro klidné hlášení hostů — od nastavení po domovní knihu.",
        "guide.nav.overview": "Přehled",
        "guide.nav.productivity": "Rychlejší každodenní práce",
        "guide.nav.setup": "První nastavení",
        "guide.nav.stays": "Pobyty a kalendáře",
        "guide.nav.guests": "Formuláře hostů",
        "guide.nav.reporting": "Hlášení na policii",
        "guide.nav.housebook": "Domovní kniha",
        "guide.nav.security": "Zabezpečení a zálohy",
        "guide.nav.demo": "Ukázková data",
        "guide.overview.body": (
            "Přehled ukazuje, co vyžaduje pozornost: chybějící formuláře, připravená hlášení a termíny. "
            "Pobyty obsahují rezervace; Hlášení uchovává doručenky."
        ),
        "guide.overview.caption": "Karta Další na řadě ukazuje nejnaléhavější pobyt a tlačítko Odeslat.",
        "guide.productivity.search": (
            "Klávesami Ctrl+K (na Macu Cmd+K) otevřete hledání ubytování, pobytu, hosta nebo stránky."
        ),
        "guide.productivity.shortcuts": (
            "V nabídce ? dole v postranním panelu najdete klávesové zkratky pro navigaci a tabulky."
        ),
        "guide.productivity.views": (
            "Na stránce Pobyty přepínejte Seznam a Časovou osu, nastavte filtry a volbou Uložit "
            "pohled si je uchovejte pro příště."
        ),
        "guide.productivity.quick_edit": (
            "V detailu pobytu najdete odkaz pro hosty, Přidat hosta, ovládání hlášení a stručnou Rychlou úpravu."
        ),
        "guide.setup.step1_title": "Provozovatel",
        "guide.setup.step1": "Firma nebo osoba registrovaná u policie.",
        "guide.setup.step2_title": "Ubytování",
        "guide.setup.step2": "IDUB, zkratka a adresa musí přesně sedět s UbyPortem.",
        "guide.setup.step3_title": "Kalendáře",
        "guide.setup.step3": "Vložte exportní iCal odkazy z Airbnb nebo Booking.com.",
        "guide.setup.step4_title": "Přihlašovací údaje UbyPort",
        "guide.setup.step4": (
            "Na stránce ubytování zadejte přihlašovací jméno UBY-WS z policejního dopisu. "
            "Anotovaná ukázka přesně ukazuje pole; prázdné již uložené heslo se při uložení zachová."
        ),
        "guide.setup.step5_title": "Odkaz pro hosty",
        "guide.setup.step5": "Odkaz pro hosty vložte do zprávy při příjezdu na všech portálech.",
        "guide.stays.body": (
            "Pobyty přicházejí z kalendářů nebo ručního zadání. Otevřete řádek pro hosty, odkaz nebo odeslání."
        ),
        "guide.stays.csv": (
            "Tlačítkem Export pobytů (CSV) v panelu filtrů získáte tabulku. Domovní kniha nabízí "
            "v nabídce Export CSV a balíček PDF pro kontrolu. Export respektuje aktuální filtry."
        ),
        "guide.guests.body": (
            "Každý pobyt má odkaz pro hosty na telefonu. Vyberou termín pobytu, hlavní host uvede "
            "počet osob, převezme rezervaci e-mailem a každý pak vyplní vlastní krátký formulář. "
            "Nedokončený převzatý formulář zůstává po příjezdu dostupný, dokud není dokončen nebo "
            "přístup výslovně nezamknete."
        ),
        "guide.guests.step_email": (
            "Na e-mail přijde soukromý odkaz, jedno upozornění při nedokončení den před příjezdem "
            "a potvrzení o dokončení. Ubytovatel dostane kopii potvrzení; veřejné obrazovky adresu "
            "zastřou. Nezbytné cookies pro hosty uchovají přístup přes PIN nejvýše 7 dní a jazyk, "
            "přístup k potvrzenému pobytu a odeslané formuláře v zařízení nejvýše 60 dní."
        ),
        "guide.guests.step_party": (
            "Nejdřív počet osob — včetně dětí; každý má vlastní formulář, aby nikdo neviděl "
            "údaje z pasu ostatních. Počet se ukládá k pobytu pro kontrolu, zda jsou hotové všechny "
            "očekávané formuláře, a uchovává se stejně dlouho jako pobyt."
        ),
        "guide.guests.step_details": (
            "Každý host ručně zadá jméno, datum narození, státní občanství a číslo dokladu tak, "
            "jak jsou v cestovním dokladu (bez skenování ani přepisování strojově čitelných řádků)."
        ),
        "guide.guests.step_photo": (
            "Nahrávání pasu či dokladu je ve výchozím stavu vypnuté. Ubytování může od cizinců "
            "vyžadovat dočasnou fotografii nebo PDF; do UbyPortu se nikdy neposílá."
        ),
        "guide.guests.step_czech": (
            "Občané ČR se zapisují do domovní knihy, policii se neoznamují."
        ),
        "guide.reporting.body": "Každé ubytování volí, jak se hotová hlášení dostanou do UbyPortu:",
        "guide.reporting.caption": (
            "Kontrola pasu je volitelný výslovný úkon ubytovatele. Automatické hlášení se řídí "
            "zvoleným časem od dokončení a na kontrolu nečeká."
        ),
        "guide.reporting.immediate": "Okamžitě po dokončení",
        "guide.reporting.immediate_detail": (
            "Odešle se automaticky, jakmile jsou hotové všechny nahlášené formuláře hostů, "
            "bez čekání na ověření ubytovatelem."
        ),
        "guide.legal.verification_title": "Ověřte každého cizince",
        "guide.legal.verification_body": (
```

Replace with:

```python
        ),
        "celebration.dismiss": "Díky!",
        "guide.legal.verification_title": "Ověřte každého cizince",
        "guide.legal.verification_body": (
```

Edit 5 of 7. Find (exactly once):

```python
            "Odmítne-li host doklad ukázat, můžete odmítnout ubytování."
        ),
        "guide.reporting.scheduled": "Naplánované",
        "guide.reporting.scheduled_detail": "Odešle se automaticky po zvolené prodlevě od dokončení.",
        "guide.reporting.manual": "Ruční",
        "guide.reporting.manual_detail": "Kliknete Odeslat u pobytu nebo Odeslat všechny připravené.",
        "guide.reporting.bulk": (
            "Hromadné odeslání jen u kompletních pobytů povolených režimem — nikdy ne částečných."
        ),
        "guide.housebook.body": (
            "Domovní kniha obsahuje všechny hosty — Čechy i cizince. CSV nebo PDF pro kontroly "
            "stáhnete z nabídky Export. Import nyní není k dispozici."
        ),
        "guide.security.two_factor": (
            "V Nastavení zapněte dvoufázové ověření pomocí autentizační aplikace a jednorázové "
            "obnovovací kódy uložte na bezpečné místo."
        ),
        "guide.security.turnstile": (
            "Produkce je za Cloudflare: Turnstile při přihlášení a po opakovaných chybách PIN, "
            "Bot Fight Mode, kontrola uniklých přihlašovacích údajů, HSTS a monitoring skriptů "
            "v prohlížeči. Návštěvník může občas vidět krátkou výzvu."
        ),
        "guide.security.passports": (
            "Nahrávání pasu či dokladu je ve výchozím stavu vypnuté. Po zapnutí k souboru v aplikaci "
            "přistupují jen oprávnění uživatelé ubytovatele; po ověření se smaže a pojistkou je "
            "automatické mazání starých souborů. Do UbyPortu se nikdy neposílá."
        ),
        "guide.security.backups": (
            "Panel Nastavení \u201eOchrana údajů\u201c (pouze pro administrátory platformy) ukazuje, kdy "
            "proběhla poslední záloha, zda byla šifrovaná, a dobu uchování. Před ukončením služby "
            "nebo zásadní změnou si ponechte také vlastní export."
        ),
        "guide.nav.legal": "Vaše právní povinnosti",
        "guide.legal.lede": (
            "UbyHost pomáhá s plněním povinností, ale ubytovatel zůstává právně odpovědný. "
```

Replace with:

```python
            "Odmítne-li host doklad ukázat, můžete odmítnout ubytování."
        ),
        "guide.legal.lede": (
            "UbyHost pomáhá s plněním povinností, ale ubytovatel zůstává právně odpovědný. "
```

Edit 6 of 7. Find (exactly once):

```python
            "Dotazy k software: support@ubyhost.com. Hosté s otázkou k pobytu mají použít "
            "jméno, e-mail a telefon ubytovatele na formuláři pro hosty."
        ),
        "guide.demo.body": (
            "Načtěte ukázková data a projděte obě ubytování: převzetí e-mailem, přiřazené pobyty, "
            "nedokončené formuláře po příjezdu, volitelný pas, odděleného správce a hlášení. "
            "Na stagingu jsou potvrzovací odkazy v Nastavení → E-maily hostům. Na skutečnou "
            "policii se ukázková data nikdy neodešlou."
        ),
        "a11y.skip_to_content": "Přeskočit na hlavní obsah",
```

Replace with:

```python
            "Dotazy k software: support@ubyhost.com. Hosté s otázkou k pobytu mají použít "
            "jméno, e-mail a telefon ubytovatele na formuláři pro hosty."
        ),
        "a11y.skip_to_content": "Přeskočit na hlavní obsah",
```

Edit 7 of 7. Find (exactly once):

```python
    STRINGS[_lang].update(_strings)


def normalise_language(value: str | None) -> str:
```

Replace with:

```python
    STRINGS[_lang].update(_strings)

from .guide_i18n import GUIDE_STRINGS
for _lang, _strings in GUIDE_STRINGS.items():
    STRINGS[_lang].update(_strings)


def normalise_language(value: str | None) -> str:
```

Why: Part 2 D. The guide copy is merged last, and the 102 old guide.* keys go. guide.legal.* and the shared guide keys stay.

Verify: `pt tests/test_host_i18n.py` passes after T105.

#### T103 Drop guide and overview copy no longer used

File: `App/app/host_design_i18n.py`

Action: EDIT

Depends on: T102

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```python
STRINGS['en'].update({
    'host.count_changed': 'The guest count changed. Review the guests and try again.',
    'host.help_stays': 'Guests, police reports and the guest register.',
    'host.help_properties': 'Calendars, guest links, reporting and business details.',
    'host.help_invoices': 'Generate invoices and download PDFs.',
    'host.help_settings': 'Account, archived records, privacy and data.',
    'settings.lede': 'Your account, data and workspace.',
    'guide.overview.body': 'Dashboard shows stays that need your attention, followed by upcoming stays. Open a stay to review guest details or its police report.',
    'invoice.detail.note_paid': 'Payment was recorded by the host.',
    'invoice.detail.note_unpaid': 'Record payment here when you receive it.',
```

Replace with:

```python
STRINGS['en'].update({
    'host.count_changed': 'The guest count changed. Review the guests and try again.',
    'settings.lede': 'Your account, data and workspace.',
    'invoice.detail.note_paid': 'Payment was recorded by the host.',
    'invoice.detail.note_unpaid': 'Record payment here when you receive it.',
```

Edit 2 of 2. Find (exactly once):

```python
STRINGS['cs'].update({
    'host.count_changed': 'Počet hostů se změnil. Zkontrolujte hosty a zkuste to znovu.',
    'host.help_stays': 'Hosté, hlášení policii a kniha hostů.',
    'host.help_properties': 'Kalendáře, odkazy pro hosty, hlášení a firemní údaje.',
    'host.help_invoices': 'Vystavení faktur a stažení PDF.',
    'host.help_settings': 'Účet, archivované záznamy, soukromí a data.',
    'settings.lede': 'Váš účet, data a pracovní prostor.',
    'guide.overview.body': 'Přehled ukazuje pobyty, které vyžadují vaši pozornost, a nadcházející pobyty. Otevřete pobyt a zkontrolujte údaje hostů nebo hlášení policii.',
    'invoice.detail.note_paid': 'Platbu zaznamenal ubytovatel.',
    'invoice.detail.note_unpaid': 'Po přijetí platby ji zde zaznamenejte.',
```

Replace with:

```python
STRINGS['cs'].update({
    'host.count_changed': 'Počet hostů se změnil. Zkontrolujte hosty a zkuste to znovu.',
    'settings.lede': 'Váš účet, data a pracovní prostor.',
    'invoice.detail.note_paid': 'Platbu zaznamenal ubytovatel.',
    'invoice.detail.note_unpaid': 'Po přijetí platby ji zde zaznamenejte.',
```

Why: Part 2 D. Help card and overview keys that nothing renders after T100.

Verify: After T105.

#### T104 Drop the guide screenshot styles

File: `App/app/static/app.css`

Action: EDIT

Depends on: T71, T100

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```css
.guide-section h2 { margin-top: 0; }
.guide-steps { margin: 0; padding-left: 1.2rem; display: grid; gap: 10px; }
.guide-figure {
  margin: 16px 0 0;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;
  background: var(--bg);
  box-shadow: var(--shadow-sm);
}
.guide-figure img {
  display: block;
  width: 100%;
  height: auto;
}
.guide-figure figcaption {
  padding: 8px 12px;
  font-size: 12.5px;
  color: var(--muted);
  border-top: 1px solid var(--line);
  background: var(--surface-2);
}
.guide-shot {
  margin-top: 16px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;
  background: var(--bg);
}
.guide-shot-bar { height: 10px; background: var(--surface-3); }
.guide-shot-body { display: flex; min-height: 120px; }
.guide-shot-sidebar {
  width: 22%;
  background: var(--surface);
  border-right: 1px solid var(--line);
}
.guide-shot-main { flex: 1; padding: 14px; display: grid; gap: 10px; align-content: start; }
.guide-shot-card {
  height: 36px;
  border-radius: var(--radius-sm);
  background: var(--surface);
  border: 1px solid var(--line);
}
.guide-shot-card.short { width: 55%; }
.guide-shot.guest { display: grid; place-items: center; padding: 20px; }
.guide-shot-phone {
  width: 140px;
  padding: 16px 14px;
  border-radius: 18px;
  background: var(--surface);
  border: 1px solid var(--line);
  display: grid;
  gap: 8px;
}
.guide-shot-line { height: 8px; border-radius: 4px; background: var(--surface-3); }
.guide-shot-line.wide { width: 80%; }
.guide-shot-btn {
  height: 28px;
  margin-top: 6px;
  border-radius: var(--radius-sm);
  background: var(--brand-soft);
  border: 1px solid rgba(200, 90, 82, 0.25);
}

/* --- milestone celebration --------------------------------------------- */
```

Replace with:

```css
.guide-section h2 { margin-top: 0; }
.guide-steps { margin: 0; padding-left: 1.2rem; display: grid; gap: 10px; }
.legal-disclaimer h3 { margin-top: 0; }
.legal-disclaimer p { margin-bottom: 0; }

/* --- milestone celebration --------------------------------------------- */
```

Why: Part 2 D, A63. Styles for the deleted screenshots.

Verify: After T107.

#### T105 Tests: guide strings

File: `App/tests/test_host_i18n.py`

Action: EDIT

Depends on: T102

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python
def test_release_help_describes_optional_passports_and_cookie_lifetimes():
    for lang in ("en", "cs"):
        passport = host_i18n.translate(lang, "guide.security.passports")
        cookies = host_i18n.translate(lang, "guide.guests.step_email")
        assert "UbyPort" in passport
        assert ("off by default" in passport) or ("výchozím stavu vypnuté" in passport)
```

Replace with:

```python
def test_release_help_describes_optional_passports_and_cookie_lifetimes():
    for lang in ("en", "cs"):
        passport = host_i18n.translate(lang, "guide.guests.photo")
        cookies = host_i18n.translate(lang, "guide.guests.cookies")
        assert "UbyPort" in passport
        assert ("off by default" in passport) or ("výchozím stavu vypnuté" in passport)
```

Why: Part 2 D. The i18n test looked for old guide keys; it now checks the photo and cookie copy.

Verify: `pt tests/test_host_i18n.py` passes.

#### T106 Tests: Czech stay labels

File: `App/tests/test_stay_labels_cs.py`

Action: EDIT

Depends on: T102

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python
def test_the_guide_uses_the_same_czech_nouns_as_the_ui():
    cs = host_i18n.STRINGS["cs"]
    assert cs["guide.setup.step2"] == "IDUB, zkratka a adresa musí přesně sedět s UbyPortem."
    assert "značka" not in cs["guide.setup.step2"]
    assert (
        cs["guide.setup.step5"]
        == "Odkaz pro hosty vložte do zprávy při příjezdu na všech portálech."
    )
    assert "Permalink" not in cs["guide.setup.step5"]
    assert "hlavní host uvede" in cs["guide.guests.body"]
    assert "vedoucí" not in cs["guide.guests.body"]
```

Replace with:

```python
def test_the_guide_uses_the_same_czech_nouns_as_the_ui():
    cs = host_i18n.STRINGS["cs"]
    assert "zkratka" in cs["guide.setup.step4"]
    assert "značka" not in cs["guide.setup.step4"]
    assert "Odkazy pro hosty" in cs["guide.setup.step5"]
    assert "Permalink" not in cs["guide.setup.step5"]
    assert "Hlavní host uvede" in cs["guide.guests.step_claim"]
    assert "vedoucí" not in cs["guide.guests.step_claim"]
```

Why: Part 2 D. Czech labels must keep 'zkratka' and the new keys.

Verify: `pt tests/test_stay_labels_cs.py` passes.

#### T107 Tests: guide page

File: `App/tests/test_guide.py`

Action: CREATE

Depends on: T101

Code:

Full content:

```python
"""The Help & guide renders every section in both languages, with no raw keys."""
from __future__ import annotations

from tests.test_submission_retry_cap import host as host  # noqa: F401


def test_the_guide_renders_every_section_without_raw_keys(host):
    for lang in ("en", "cs"):
        page = host.get(f"/guide?lang={lang}").text
        for section in ("overview", "statuses", "setup", "stays", "guests", "reporting",
                        "filters", "housebook", "stay_fee", "invoices", "settings",
                        "faster", "faq", "legal"):
            assert f'id="{section}"' in page, (lang, section)
        assert "guide." not in page.replace("/guide", "")
        assert '<span class="pill red">' in page
```

Why: Part 2 D. The guide renders every section in both languages, and demo is gated.

Verify: `pt tests/test_guide.py` passes.

#### T108 Copy matches behaviour (optional ID check, retry rule)

File: `App/app/host_i18n.py`

Action: EDIT

Depends on: T102

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 4. Find (exactly once):

```python
        "hint.missing_guests": "Guest forms: %(filled)s/%(expected)s. Send the link to the others, add them yourself, or lower the guest count if fewer came.",
        "hint.ready_to_send": "Send completed guest records to UbyPort now",
        "hint.ready_id_optional": "Forms complete — send now or mark ID checked first (recorded on send)",
        "hint.failed": "UbyPort rejected a guest record. Fix the details marked in red below, then send again.",
        "hint.demo_preview": "Demo stays are never sent — use a real property to report to UbyPort",
```

Replace with:

```python
        "hint.missing_guests": "Guest forms: %(filled)s/%(expected)s. Send the link to the others, add them yourself, or lower the guest count if fewer came.",
        "hint.ready_to_send": "Send completed guest records to UbyPort now",
        "hint.ready_id_optional": "Forms complete — send now. Checking the ID first is optional.",
        "hint.failed": "UbyPort rejected a guest record. Fix the details marked in red below, then send again.",
        "hint.demo_preview": "Demo stays are never sent — use a real property to report to UbyPort",
```

Edit 2 of 4. Find (exactly once):

```python
        "hint.missing_guests": "Formuláře hostů: %(filled)s/%(expected)s. Pošlete ostatním odkaz, zadejte je sami, nebo snižte počet hostů, pokud jich přijelo méně.",
        "hint.ready_to_send": "Odeslat hotové záznamy hostů do UbyPortu",
        "hint.ready_id_optional": "Formuláře hotové — odešlete, nebo nejdřív označte kontrolu dokladu (zapíše se při odeslání)",
        "hint.failed": "UbyPort odmítl záznam hosta. Opravte údaje označené červeně níže a odešlete znovu.",
        "hint.demo_preview": "Ukázkové pobyty se neodesílají — pro hlášení použijte skutečnou nemovitost",
```

Replace with:

```python
        "hint.missing_guests": "Formuláře hostů: %(filled)s/%(expected)s. Pošlete ostatním odkaz, zadejte je sami, nebo snižte počet hostů, pokud jich přijelo méně.",
        "hint.ready_to_send": "Odeslat hotové záznamy hostů do UbyPortu",
        "hint.ready_id_optional": "Formuláře hotové — odešlete. Kontrola dokladu předem je volitelná.",
        "hint.failed": "UbyPort odmítl záznam hosta. Opravte údaje označené červeně níže a odešlete znovu.",
        "hint.demo_preview": "Ukázkové pobyty se neodesílají — pro hlášení použijte skutečnou nemovitost",
```

Edit 3 of 4. Find (exactly once):

```python
        "automation.missing": "Still missing:",
        "automation.timing_title": "When to send to UbyPort",
        "automation.timing_help": "Immediate sends when all declared forms are complete. Delayed sends after the chosen number of hours from completion, giving you time to review. Both are automatic and do not wait for verification. Rejected records are never silently retried.",
        "automation.timing_label": "Send timing",
        "automation.mode.manual": "Only when I press send",
```

Replace with:

```python
        "automation.missing": "Still missing:",
        "automation.timing_title": "When to send to UbyPort",
        "automation.timing_help": "Immediate sends when all declared forms are complete. Delayed sends after the chosen number of hours from completion, giving you time to review. Both are automatic and do not wait for verification. A rejected record is retried automatically at most three times, and again after you correct it; you get an alert either way.",
        "automation.timing_label": "Send timing",
        "automation.mode.manual": "Only when I press send",
```

Edit 4 of 4. Find (exactly once):

```python
        "automation.missing": "Ještě chybí:",
        "automation.timing_title": "Kdy odesílat do UbyPortu",
        "automation.timing_help": "Okamžitý režim odešle po dokončení všech nahlášených formulářů. Odložený odešle po zvoleném počtu hodin od dokončení a dává vám čas na kontrolu. Oba jsou automatické a nečekají na ověření. Odmítnuté záznamy se nikdy tiše neopakují.",
        "automation.timing_label": "Čas odeslání",
        "automation.mode.manual": "Jen po stisknutí Odeslat",
```

Replace with:

```python
        "automation.missing": "Ještě chybí:",
        "automation.timing_title": "Kdy odesílat do UbyPortu",
        "automation.timing_help": "Okamžitý režim odešle po dokončení všech nahlášených formulářů. Odložený odešle po zvoleném počtu hodin od dokončení a dává vám čas na kontrolu. Oba jsou automatické a nečekají na ověření. Odmítnutý záznam se automaticky zkusí nejvýše třikrát a znovu po opravě; upozornění dostanete vždy.",
        "automation.timing_label": "Čas odeslání",
        "automation.mode.manual": "Jen po stisknutí Odeslat",
```

Why: A73. The old copy said the ID check was required and gave the wrong retry rule.

Verify: `pt tests/test_host_i18n.py tests/test_status_colours.py` passes.

#### T109 A duplicate filing pill is green

File: `App/app/templates/_components.html`

Action: EDIT

Depends on: T97

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```html
  {% set tones = {
    'ok': 'green',
    'ok_duplicate': 'amber',
    'partial': 'amber',
    'error': 'red',
```

Replace with:

```html
  {% set tones = {
    'ok': 'green',
    'ok_duplicate': 'green',
    'partial': 'amber',
    'error': 'red',
```

Why: Owner decision Q10. Code 150 means the register already holds every record: nothing is left to do.

Verify: After T110.

#### T110 Test the duplicate pill is green

File: `App/tests/test_status_colours.py`

Action: EDIT

Depends on: T109

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python
        assert tone == "red"
    finally:
        _cleanup()
```

Replace with:

```python
        assert tone == "red"
    finally:
        _cleanup()


def test_a_duplicate_filing_is_green_because_nothing_is_left_to_do():
    """Code 150 means the register already holds every record: a success."""
    from app import templating

    html = templating.templates.env.from_string(
        "{% from '_components.html' import submission_pill %}"
        "{{ submission_pill('ok_duplicate') }}"
    ).render(t=lambda key, **kw: host_i18n.translate("en", key))
    tone, _tip, _label = PILL.search(html).groups()
    assert tone == "green"
```

Why: Q10 regression test.

Verify: `pt tests/test_status_colours.py` passes.

#### T111 Delete the old month filter model

File: `App/app/list_month_filter.py`

Action: DELETE

Depends on: T87, T89

Code:

Run: `git rm App/app/list_month_filter.py`

Why: Part 2 A. Replaced by list_filter.py; nothing imports it after T87 and T89.

Verify: `grep -rn list_month_filter App` returns nothing.

#### T112 Delete the old month filter template

File: `App/app/templates/_host_month_filter.html`

Action: DELETE

Depends on: T88, T90, T91

Code:

Run: `git rm App/app/templates/_host_month_filter.html`

Why: Part 2 A. Replaced by _list_filter.html.

Verify: `grep -rn _host_month_filter App/app` returns nothing.

#### T113 Delete outdated guide screenshots

File: `App/app/static/guide`

Action: DELETE

Depends on: T100, T104

Code:

Run: `git rm -r App/app/static/guide`

Why: Part 2 D. Screenshots of the old UI that the new guide no longer shows.

Verify: `grep -rn static/guide App/app` returns nothing. End of Phase 3: the full suite passes.

### Phase 4. Dead code and files

#### T114 Drop four duplicate translation keys

File: `App/app/host_i18n.py`

Action: EDIT

Depends on: Phase 3 complete, T108

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 4. Find (exactly once):

```python
        "status.awaiting_verification": "Ready to report",
        "status.awaiting_verification_tip": "ID not checked (optional)",
        "stay.detail.note.immediate": "after guest forms are complete",
        "terms.footer_short": "Terms",
        "privacy.footer_short": "Privacy",
```

Replace with:

```python
        "status.awaiting_verification": "Ready to report",
        "status.awaiting_verification_tip": "ID not checked (optional)",
        "terms.footer_short": "Terms",
        "privacy.footer_short": "Privacy",
```

Edit 2 of 4. Find (exactly once):

```python
        "flash.stay_fees.confirm_collected": "Confirm you checked the amounts actually collected.",
        "flash.stay_fees.scope_invalid": "Enter the council ruling and reference.",
        "flash.stay_fees.account_invalid": "That council account number is not valid. Nothing was saved.",
        "flash.entities.archived": "“%(name)s” archived.",
        "flash.entities.restored": "“%(name)s” restored.",
```

Replace with:

```python
        "flash.stay_fees.confirm_collected": "Confirm you checked the amounts actually collected.",
        "flash.stay_fees.scope_invalid": "Enter the council ruling and reference.",
        "flash.entities.archived": "“%(name)s” archived.",
        "flash.entities.restored": "“%(name)s” restored.",
```

Edit 3 of 4. Find (exactly once):

```python
        "status.awaiting_verification": "Připraveno k hlášení",
        "status.awaiting_verification_tip": "Doklad nezkontrolován (volitelné)",
        "stay.detail.note.immediate": "po dokončení formulářů hostů",
        "terms.footer_short": "Podmínky",
        "privacy.footer_short": "Soukromí",
```

Replace with:

```python
        "status.awaiting_verification": "Připraveno k hlášení",
        "status.awaiting_verification_tip": "Doklad nezkontrolován (volitelné)",
        "terms.footer_short": "Podmínky",
        "privacy.footer_short": "Soukromí",
```

Edit 4 of 4. Find (exactly once):

```python
        "flash.stay_fees.confirm_collected": "Potvrďte, že jste zkontrolovali skutečně vybrané částky.",
        "flash.stay_fees.scope_invalid": "Doplňte rozhodnutí úřadu a jeho odkaz.",
        "flash.stay_fees.account_invalid": "Číslo účtu obce není platné. Nic nebylo uloženo.",
        "flash.entities.archived": "„%(name)s“ bylo archivováno.",
        "flash.entities.restored": "„%(name)s“ bylo obnoveno.",
```

Replace with:

```python
        "flash.stay_fees.confirm_collected": "Potvrďte, že jste zkontrolovali skutečně vybrané částky.",
        "flash.stay_fees.scope_invalid": "Doplňte rozhodnutí úřadu a jeho odkaz.",
        "flash.entities.archived": "„%(name)s“ bylo archivováno.",
        "flash.entities.restored": "„%(name)s“ bylo obnoveno.",
```

Why: A67. Python keeps the later value of a duplicate dict key, so the earlier copies were dead and misleading.

Verify: `pt tests/test_host_i18n.py` passes.

#### T115 Remove unused code in cookie_inventory

File: `App/app/cookie_inventory.py`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python


def for_surface(surface: str) -> Tuple[Dict[str, object], ...]:
    return tuple(row for row in COOKIE_INVENTORY if row["surface"] in (surface, "any"))


def names() -> Tuple[str, ...]:
    return tuple(str(row["name"]) for row in COOKIE_INVENTORY)
```

Replace with:

```python


def names() -> Tuple[str, ...]:
    return tuple(str(row["name"]) for row in COOKIE_INVENTORY)
```

Why: A62. No caller in app, tests, tools or scripts.

Verify: `ruff check app tests tools --select E9,F63,F7,F82,F401,F841` and the full suite pass.

#### T116 Remove unused code in invoices

File: `App/app/invoices.py`

Action: EDIT

Depends on: T36

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python


def view_row(invoice_id: int) -> Dict[str, Any]:
    """The stored invoice row plus the view fields, for detail/PDF/preview."""
    with db.cursor() as cur:
        return pdf_view_row(cur, invoice_id)


def _write_issued(draft: Dict[str, Any], actor_user_id: Optional[int]) -> tuple:
    """Write an issued document inside one write lock. Returns (id, number)."""
```

Replace with:

```python


def _write_issued(draft: Dict[str, Any], actor_user_id: Optional[int]) -> tuple:
    """Write an issued document inside one write lock. Returns (id, number)."""
```

Why: A62. No caller in app, tests, tools or scripts.

Verify: `ruff check app tests tools --select E9,F63,F7,F82,F401,F841` and the full suite pass.

#### T117 Remove unused code in mail_notify

File: `App/app/mail_notify.py`

Action: EDIT

Depends on: T61

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```python


def _fmt_dates(date_from: Optional[str], date_to: Optional[str]) -> str:
    return validation.fmt_date_range(date_from, date_to)


def _block_heading(text: str) -> str:
    return (
```

Replace with:

```python


def _block_heading(text: str) -> str:
    return (
```

Edit 2 of 2. Find (exactly once):

```python
        f'border-radius:12px;padding:18px 20px;">' + "".join(parts) + "</div></td></tr>"
    )


def _panel_text_lines(panel: Dict[str, Any]) -> List[str]:
    """The plain-text mirror of a money panel, in the same order."""
    lines = []
    if panel.get("title"):
        lines.append(str(panel["title"]))
    for row in panel.get("rows") or []:
        lines.append(f"{row[0]}: {row[1]}")
    if panel.get("note"):
        lines.append(str(panel["note"]))
    action = panel.get("action")
    if action:
        lines.append(f"{action[1]}: {action[0]}")
    return lines


```

Replace with:

```python
        f'border-radius:12px;padding:18px 20px;">' + "".join(parts) + "</div></td></tr>"
    )


```

Why: A62. No caller in app, tests, tools or scripts.

Verify: `ruff check app tests tools --select E9,F63,F7,F82,F401,F841` and the full suite pass.

#### T118 Remove unused code in stay_fee_adjustment

File: `App/app/stay_fee_adjustment.py`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python
    )


def attach_open(apartment_id: int, period_key: str, filing_id: int) -> None:
    db.execute(
        "UPDATE stay_fee_adjustment SET filing_id = ? "
        "WHERE apartment_id = ? AND period_key = ? AND reversed_at IS NULL AND filing_id IS NULL",
        (filing_id, apartment_id, period_key),
    )
```

Replace with:

```python
    )

```

Why: A62. No caller in app, tests, tools or scripts.

Verify: `ruff check app tests tools --select E9,F63,F7,F82,F401,F841` and the full suite pass.

#### T119 Remove unused code in validation_i18n

File: `App/app/validation_i18n.py`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python


def localize_issues(issues: List[validation.Issue], lang: str = "cs") -> List[validation.Issue]:
    """The same issues, with their sentences in the reader's language."""
    if lang != "cs":
        return issues
    return [
        validation.Issue(issue.field, localize(issue.message, lang), issue.severity)
        for issue in issues
    ]


def guest_localize(message: str, lang: str = "cs") -> str:
    """The sentence as the guest form should read it, in the guest's language.
```

Replace with:

```python


def guest_localize(message: str, lang: str = "cs") -> str:
    """The sentence as the guest form should read it, in the guest's language.
```

Why: A62. No caller in app, tests, tools or scripts.

Verify: `ruff check app tests tools --select E9,F63,F7,F82,F401,F841` and the full suite pass.

#### T120 Remove unused code in stay_fee

File: `App/app/stay_fee.py`

Action: EDIT

Depends on: T92

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python

MAX_RATE_CZK = 50        # §3d
MAX_CALENDAR_DAYS = 60   # §3a
ADULT_AGE = 18           # §3b(1)(b)
CADENCES = ("monthly", "quarterly")
```

Replace with:

```python

MAX_RATE_CZK = 50        # §3d
ADULT_AGE = 18           # §3b(1)(b)
CADENCES = ("monthly", "quarterly")
```

Why: A62. No caller in app, tests, tools or scripts.

Verify: `ruff check app tests tools --select E9,F63,F7,F82,F401,F841` and the full suite pass.

#### T121 Remove unused code in routes/guest

File: `App/app/routes/guest.py`

Action: EDIT

Depends on: T49

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python
        return fallback
    return urlunsplit(("", "", path, split.query, "")) + fragment


def _localize_message(message: str) -> str:
    return validation_i18n.localize(message)


```

Replace with:

```python
        return fallback
    return urlunsplit(("", "", path, split.query, "")) + fragment


```

Why: A62. No caller in app, tests, tools or scripts.

Verify: `ruff check app tests tools --select E9,F63,F7,F82,F401,F841` and the full suite pass.

#### T122 Remove unused code in routes/admin

File: `App/app/routes/admin.py`

Action: EDIT

Depends on: T101

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python
    "registry_entry",
    "invoice_prefix",
)

# The identity block shown on the (short) operator form. Bank, VAT, registry
# and numbering fields keep their saved values when a form posts only these.
CORE_ENTITY_FIELDS = (
    "name",
    "seat",
    "ico",
    "contact_email",
    "contact_phone",
    "dic",
)

```

Replace with:

```python
    "registry_entry",
    "invoice_prefix",
)

```

Why: A62. No caller in app, tests, tools or scripts.

Verify: `ruff check app tests tools --select E9,F63,F7,F82,F401,F841` and the full suite pass.

#### T123 Remove CSS rules nothing uses (app.css)

File: `App/app/static/app.css`

Action: EDIT

Depends on: T104

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 27. Find (exactly once):

```css
  min-width: 0;
}
.sidebar-brand-actions { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.sidebar .brand {
  display: flex;
```

Replace with:

```css
  min-width: 0;
}
.sidebar .brand {
  display: flex;
```

Edit 2 of 27. Find (exactly once):

```css
  color: var(--ink);
}
.brand-mark {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border-radius: 9px;
  background: var(--ink);
  color: var(--canvas);
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0;
}

.sidebar-nav { display: flex; flex-direction: column; gap: 20px; overflow-y: auto; }
.nav-group { display: grid; gap: 2px; }
.nav-label {
  color: var(--faint);
```

Replace with:

```css
  color: var(--ink);
}

.sidebar-nav { display: flex; flex-direction: column; gap: 20px; overflow-y: auto; }
.nav-label {
  color: var(--faint);
```

Edit 3 of 27. Find (exactly once):

```css
}

.sidebar-user {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0 12px 16px;
  padding: 12px 14px;
  border: 1px solid color-mix(in srgb, var(--brand) 14%, var(--line));
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, var(--brand-soft), color-mix(in srgb, var(--orange-bg) 55%, var(--surface)));
  box-shadow: 0 4px 14px rgba(35, 30, 28, .05);
}

.sidebar-user-avatar {
  display: grid;
```

Replace with:

```css
}

.sidebar-user-avatar {
  display: grid;
```

Edit 4 of 27. Find (exactly once):

```css
  font-weight: 700;
  flex: 0 0 auto;
}

.sidebar-user-meta {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.sidebar-user-meta strong {
  font-size: 14px;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar-user-meta span {
  font-size: 12.5px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

```

Replace with:

```css
  font-weight: 700;
  flex: 0 0 auto;
}

```

Edit 5 of 27. Find (exactly once):

```css
.sidebar-nav a.active { background: var(--brand-soft); color: var(--brand-ink); font-weight: 650; }
.sidebar-nav a.active .nav-icon { color: var(--brand); }
.nav-group:nth-child(1) .nav-icon { color: var(--blue); }
.nav-group:nth-child(2) .nav-icon { color: var(--purple); }
.nav-group:nth-child(3) .nav-icon { color: var(--teal); }
.nav-group:nth-child(1) a.active { background: var(--blue-bg); color: var(--blue); }
.nav-group:nth-child(2) a.active { background: var(--purple-bg); color: var(--purple); }
.nav-group:nth-child(3) a.active { background: var(--teal-bg); color: var(--teal); }
.sidebar-footer {
  margin-top: auto;
  padding-top: 8px;
  border-top: 1px solid var(--line);
  display: grid;
  gap: 5px;
}
.sidebar-footer-links {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px 6px;
  padding: 0 2px;
  font-size: 11.5px;
  font-weight: 600;
  line-height: 1.3;
}
.sidebar-footer-links a {
  color: var(--muted);
  text-decoration: none;
}
.sidebar-footer-links a:hover { color: var(--brand); }
.sidebar-footer-sep {
  color: var(--faint);
  font-weight: 400;
  user-select: none;
}
.sidebar-footer-support {
  padding: 0 2px;
  font-size: 12px;
  line-height: 1.35;
}
.sidebar-footer-support a {
  color: var(--ink-2);
  text-decoration: none;
}
.sidebar-footer-support a:hover {
  color: var(--brand);
  text-decoration: underline;
}
.guest-card-action {
  display: flex;
```

Replace with:

```css
.sidebar-nav a.active { background: var(--brand-soft); color: var(--brand-ink); font-weight: 650; }
.sidebar-nav a.active .nav-icon { color: var(--brand); }
.guest-card-action {
  display: flex;
```

Edit 6 of 27. Find (exactly once):

```css
  gap: 10px;
  margin-top: 10px;
}
.sidebar-footer-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.sidebar-footer-row .lang-switch.compact {
  flex: 0 0 auto;
  width: fit-content;
}
.sidebar-logout { margin: 0; padding: 0; flex-shrink: 0; }
.sidebar-logout .nav-button {
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-2);
  padding: 6px 10px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--surface);
  transition: background 0.14s ease, border-color 0.14s ease, color 0.14s ease;
}
.sidebar-logout .nav-button:hover {
  background: var(--surface-3);
  border-color: var(--line-2);
  color: var(--ink);
}

```

Replace with:

```css
  gap: 10px;
  margin-top: 10px;
}

```

Edit 7 of 27. Find (exactly once):

```css
  pointer-events: none;
}
.notification-more {
  pointer-events: auto;
  padding: 8px 12px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--surface);
  box-shadow: var(--shadow-popover);
  font-size: 13px;
  font-weight: 650;
  text-align: center;
  text-decoration: none;
}
.notification-bubble {
  position: relative;
```

Replace with:

```css
  pointer-events: none;
}
.notification-bubble {
  position: relative;
```

Edit 8 of 27. Find (exactly once):

```css
/* --- focus card: the one thing to do next ------------------------------ */

.focus-card {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 18px;
  padding: 20px 22px;
  margin-bottom: 20px;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, var(--surface) 0%, var(--surface-2) 100%);
  box-shadow: var(--shadow);
}
.focus-card .focus-main { flex: 1 1 280px; min-width: 0; }
.focus-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 11.5px;
  font-weight: 700;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 8px;
}
.focus-eyebrow .dot { width: 7px; height: 7px; border-radius: var(--pill); background: var(--brand); }
.focus-card.is-overdue .focus-eyebrow .dot { background: var(--bad); }
.focus-card.is-overdue { border-color: rgba(195, 47, 36, 0.24); }
.focus-title { font-size: 21px; font-weight: 700; letter-spacing: -0.025em; color: var(--ink); margin: 0 0 4px; }
.focus-title a { color: inherit; text-decoration: none; }
.focus-title a:hover { color: var(--brand); }
.focus-meta { color: var(--muted); font-size: 14px; display: flex; flex-wrap: wrap; gap: 6px 12px; align-items: center; }
.focus-actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.focus-actions .btn.accent { white-space: nowrap; }
.page-toolbar {
  display: flex;
```

Replace with:

```css
/* --- focus card: the one thing to do next ------------------------------ */

.page-toolbar {
  display: flex;
```

Edit 9 of 27. Find (exactly once):

```css
}
.page-toolbar-row form { margin: 0; }
.page-toolbar-meta { margin: 0; font-size: 12px; line-height: 1.35; }
.sync-cta {
  display: flex;
```

Replace with:

```css
}
.page-toolbar-row form { margin: 0; }
.sync-cta {
  display: flex;
```

Edit 10 of 27. Find (exactly once):

```css
  box-shadow: 0 1px 2px rgba(173, 73, 66, 0.24), 0 10px 22px rgba(173, 73, 66, 0.2);
}
.entity-edit-panel { margin-bottom: 16px; }

/* The operator form is short on purpose (~700px): only the identity block,
```

Replace with:

```css
  box-shadow: 0 1px 2px rgba(173, 73, 66, 0.24), 0 10px 22px rgba(173, 73, 66, 0.2);
}

/* The operator form is short on purpose (~700px): only the identity block,
```

Edit 11 of 27. Find (exactly once):

```css
/* --- sticky action bar ------------------------------------------------- */

.action-bar {
  position: sticky;
  top: 12px;
  z-index: 12;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  padding: 14px 16px;
  margin-bottom: 18px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  box-shadow: var(--shadow);
}
.action-bar .bar-note { flex: 1 1 220px; color: var(--muted); font-size: 13.5px; min-width: 0; }
.inline-edit-bar {
  display: flex;
```

Replace with:

```css
/* --- sticky action bar ------------------------------------------------- */

.inline-edit-bar {
  display: flex;
```

Edit 12 of 27. Find (exactly once):

```css
.filters input[type=date], .filters input[type=month], .filters input[type=text], .filters select { height: 44px; }

.reporting-modes-panel {
  padding: 14px 16px;
  margin-bottom: 14px;
}

.signature-pad {
  border: 1px solid var(--line);
```

Replace with:

```css
.filters input[type=date], .filters input[type=month], .filters input[type=text], .filters select { height: 44px; }

.signature-pad {
  border: 1px solid var(--line);
```

Edit 13 of 27. Find (exactly once):

```css
  border-color: var(--line);
}
.compact-filters summary { color: var(--brand); font-size: 13.5px; font-weight: 600; }
/* With scripting the filters apply themselves, so Apply is only a fallback. */
.has-js form[data-auto-submit] .filter-apply { display: none; }
```

Replace with:

```css
  border-color: var(--line);
}
/* With scripting the filters apply themselves, so Apply is only a fallback. */
.has-js form[data-auto-submit] .filter-apply { display: none; }
```

Edit 14 of 27. Find (exactly once):

```css
.section-heading a { font-size: 13.5px; font-weight: 600; text-decoration: none; }
.section-heading a:hover { text-decoration: underline; }

.task-row-main { min-width: 230px; }
.task-title { color: var(--ink); font-weight: 650; text-decoration: none; }
.next-action { color: var(--muted); font-size: 13px; margin-top: 4px; }
.status-summary { display: flex; gap: 9px; flex-wrap: wrap; align-items: center; }
```

Replace with:

```css
.section-heading a { font-size: 13.5px; font-weight: 600; text-decoration: none; }
.section-heading a:hover { text-decoration: underline; }
.next-action { color: var(--muted); font-size: 13px; margin-top: 4px; }
.status-summary { display: flex; gap: 9px; flex-wrap: wrap; align-items: center; }
```

Edit 15 of 27. Find (exactly once):

```css
}
.section-nav a:hover { color: var(--brand-ink); background: var(--brand-soft); }
.settings-nav { position: static; }

.message-template {
```

Replace with:

```css
}
.section-nav a:hover { color: var(--brand-ink); background: var(--brand-soft); }

.message-template {
```

Edit 16 of 27. Find (exactly once):

```css
  font: 13px/1.6 ui-monospace, SFMono-Regular, Menlo, monospace;
}
.import-guide { font-size: 14px; color: var(--muted); }

.code-block {
```

Replace with:

```css
  font: 13px/1.6 ui-monospace, SFMono-Regular, Menlo, monospace;
}

.code-block {
```

Edit 17 of 27. Find (exactly once):

```css
.truncate { max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
@media (max-width: 720px) { .truncate { max-width: none; white-space: normal; overflow-wrap: anywhere; } }
.import-guide ol { margin: 8px 0 0; padding-left: 18px; }
.import-guide li { margin-bottom: 6px; }

.action-panel { margin-bottom: 18px; }
```

Replace with:

```css
.truncate { max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
@media (max-width: 720px) { .truncate { max-width: none; white-space: normal; overflow-wrap: anywhere; } }

.action-panel { margin-bottom: 18px; }
```

Edit 18 of 27. Find (exactly once):

```css
  .appbar-help { display: none; }
  .appbar .env-badge { max-width: 118px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .sidebar-user { margin-inline: 4px; }
  .sidebar-nav { gap: 15px; }
}
```

Replace with:

```css
  .appbar-help { display: none; }
  .appbar .env-badge { max-width: 118px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .sidebar-nav { gap: 15px; }
}
```

Edit 19 of 27. Find (exactly once):

```css
    gap: 0;
  }
  .notification-bubble,
  .notification-more { border-radius: 0; border-left: 0; border-right: 0; box-shadow: none; }
  .notification-bubble + .notification-bubble,
  .notification-more { border-top: 0; }
  .pagination { justify-content: space-between; }
  .table-cards thead { display: none; }
```

Replace with:

```css
    gap: 0;
  }
  .notification-bubble { border-radius: 0; border-left: 0; border-right: 0; box-shadow: none; }
  .notification-bubble + .notification-bubble { border-top: 0; }
  .pagination { justify-content: space-between; }
  .table-cards thead { display: none; }
```

Edit 20 of 27. Find (exactly once):

```css
  .filters .field { max-width: none; }
  .settings-action-row { align-items: flex-start; flex-direction: column; }
  .action-bar { position: static; }
}

```

Replace with:

```css
  .filters .field { max-width: none; }
  .settings-action-row { align-items: flex-start; flex-direction: column; }
}

```

Edit 21 of 27. Find (exactly once):

```css
.auth-foot strong { color: var(--ink-2); font-weight: 650; }

.auth-setup-hint {
  padding: 12px 14px;
  border-radius: 12px;
  background: var(--canvas-subtle);
  border: 1px solid var(--border);
}

@media (max-width: 900px) {
  .auth-layout { grid-template-columns: 1fr; }
```

Replace with:

```css
.auth-foot strong { color: var(--ink-2); font-weight: 650; }

@media (max-width: 900px) {
  .auth-layout { grid-template-columns: 1fr; }
```

Edit 22 of 27. Find (exactly once):

```css
.sidebar-brand .brand-logo { width: 28px; height: 28px; }

.sidebar-user {
  gap: 9px;
  margin: 9px 2px 11px;
  padding: 0 4px;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.sidebar-user-avatar {
  width: 28px;
```

Replace with:

```css
.sidebar-brand .brand-logo { width: 28px; height: 28px; }

.sidebar-user-avatar {
  width: 28px;
```

Edit 23 of 27. Find (exactly once):

```css
  font-size: 13px;
}
.sidebar-user-meta strong { font-size: 13px; }
.sidebar-user-meta span { font-size: 11.5px; }

.sidebar-nav { gap: 10px; padding: 2px 0; }
```

Replace with:

```css
  font-size: 13px;
}

.sidebar-nav { gap: 10px; padding: 2px 0; }
```

Edit 24 of 27. Find (exactly once):

```css
.sidebar-nav a:hover,
.nav-button:hover { color: var(--ink); background: var(--canvas-subtle); }
.sidebar-nav a.active,
.nav-group:nth-child(1) a.active,
.nav-group:nth-child(2) a.active,
.nav-group:nth-child(3) a.active {
  color: var(--brand-ink);
  background: var(--brand-soft);
  box-shadow: none;
}
.sidebar-nav a.active .nav-icon,
.nav-group:nth-child(1) a.active .nav-icon,
.nav-group:nth-child(2) a.active .nav-icon,
.nav-group:nth-child(3) a.active .nav-icon { color: var(--brand); }
/* One calm icon colour; the active item is the only thing that stands out. */
.nav-group .nav-icon,
.nav-group:nth-child(1) .nav-icon,
.nav-group:nth-child(2) .nav-icon,
.nav-group:nth-child(3) .nav-icon { color: var(--ink-faint); }
.sidebar-nav a:hover .nav-icon { color: var(--ink-secondary); }

/* Guest links and automation belong to a property, so they sit inside the
   Properties group rather than competing with it as separate destinations. */
.nav-sub {
  display: grid;
  gap: 1px;
  margin: 2px 0 2px 19px;
  padding-left: 10px;
  border-left: 1px solid var(--border);
}
.nav-sub-label {
  margin: 1px 0 2px;
  color: var(--ink-faint);
  font-size: 10.5px;
  font-weight: 600;
}
.nav-sub a { min-height: 29px; font-size: 13.5px; font-weight: 580; }
.nav-sub .nav-icon { width: 16px; height: 16px; }
.sidebar-footer { padding-top: 7px; border-top: 1px solid var(--border); }
.sidebar-footer-links { gap: 1px 6px; font-size: 11px; line-height: 1.25; }
.sidebar-footer-links a.is-current { color: var(--brand-ink); font-weight: 650; }

.property-switcher { padding: 0 2px 14px; }
.property-mark,
.avatar { width: 30px; height: 30px; border-radius: 9px; }
```

Replace with:

```css
.sidebar-nav a:hover,
.nav-button:hover { color: var(--ink); background: var(--canvas-subtle); }
.sidebar-nav a.active {
  color: var(--brand-ink);
  background: var(--brand-soft);
  box-shadow: none;
}
.sidebar-nav a.active .nav-icon { color: var(--brand); }
/* One calm icon colour; the active item is the only thing that stands out. */

.sidebar-nav a:hover .nav-icon { color: var(--ink-secondary); }

/* Guest links and automation belong to a property, so they sit inside the
   Properties group rather than competing with it as separate destinations. */

.property-mark,
.avatar { width: 30px; height: 30px; border-radius: 9px; }
```

Edit 25 of 27. Find (exactly once):

```css
  box-shadow: none;
}

.focus-card {
  gap: 22px;
  padding: clamp(20px, 2.5vw, 28px);
  border: 1px solid var(--border-strong);
  border-radius: 14px;
  background: linear-gradient(135deg, var(--brand-soft), var(--surface) 62%);
  box-shadow: 0 1px 3px rgba(32, 32, 30, .05);
}
.focus-card.is-overdue {
  border-color: color-mix(in srgb, var(--bad) 32%, var(--border-strong));
  background: linear-gradient(135deg, var(--red-bg), var(--surface) 62%);
}
.focus-eyebrow {
  padding: 4px 10px;
  border-radius: var(--radius-pill);
  color: var(--brand-ink);
  background: var(--surface);
}
.focus-title { margin-bottom: 7px; font-size: clamp(1.4rem, 2.4vw, 1.85rem); font-weight: 760; line-height: 1.08; letter-spacing: -.04em; }

.btn {
```

Replace with:

```css
  box-shadow: none;
}

.btn {
```

Edit 26 of 27. Find (exactly once):

```css
  .page-toolbar-row .btn,
  .sync-cta .btn { width: 100%; }
  .focus-card { margin-inline: 0; }
  .filters { padding: 13px; }
  .table-cards tr { padding: 16px; }
```

Replace with:

```css
  .page-toolbar-row .btn,
  .sync-cta .btn { width: 100%; }
  .filters { padding: 13px; }
  .table-cards tr { padding: 16px; }
```

Edit 27 of 27. Find (exactly once):

```css
  :root { color-scheme: light; }
  body { background: #fff; color: #111; font-size: 10pt; }
  .sidebar, .appbar, .sidebar-expand, .page-actions, .filters, .chips,
  .row-actions, .action-bar, .toast-stack, .notification-stack,
  .onboarding-banner, dialog { display: none !important; }
  .wrap.with-sidebar, .wrap { max-width: none; margin: 0; padding: 0; }
  .page-header { position: static; margin: 0 0 16pt; padding: 0 0 8pt; background: none; }
```

Replace with:

```css
  :root { color-scheme: light; }
  body { background: #fff; color: #111; font-size: 10pt; }
  .sidebar, .appbar, .sidebar-expand, .page-actions, .filters, .chips, .row-actions, .toast-stack, .notification-stack, .onboarding-banner, dialog { display: none !important; }
  .wrap.with-sidebar, .wrap { max-width: none; margin: 0; padding: 0; }
  .page-header { position: static; margin: 0 0 16pt; padding: 0 0 8pt; background: none; }
```

Why: A63. Selectors no template, script or Python references.

Verify: `pt tests/test_host_geometry.py tests/test_signed_in_chrome.py tests/test_guest_browser_e2e.py` passes.

#### T124 Remove CSS rules nothing uses (host.css)

File: `App/app/static/host.css`

Action: EDIT

Depends on: T86

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 5. Find (exactly once):

```css
.host-property-card .nav-icon { color: var(--muted); width: 23px; height: 23px; }
.host-property-card > span:last-child { margin-left: auto; color: var(--muted); }
.host-property-heading { margin-top: 8px; }
.host-workspace .property-section > summary { cursor: pointer; font-size: 17px; font-weight: 700; padding: 0; }
.host-workspace .property-section[open] > summary { margin-bottom: 20px; }
```

Replace with:

```css
.host-property-card .nav-icon { color: var(--muted); width: 23px; height: 23px; }
.host-property-card > span:last-child { margin-left: auto; color: var(--muted); }
.host-workspace .property-section > summary { cursor: pointer; font-size: 17px; font-weight: 700; padding: 0; }
.host-workspace .property-section[open] > summary { margin-bottom: 20px; }
```

Edit 2 of 5. Find (exactly once):

```css
.host-workspace .saved-views:empty { display: none; }
.host-workspace .saved-views { margin: 0 auto 15px; }
.host-workspace .focus-card { background: white; border: 1px solid var(--line); box-shadow: none; border-left: 4px solid var(--brand); }
.host-workspace .focus-title { font-size: 19px; }
.host-workspace .focus-meta { font-size: 12px; }
.host-workspace .onboarding-banner, .host-workspace .onboarding-finish { box-shadow: none; background: #fbeae2; }
.host-workspace .page-toolbar { gap: 8px; }
```

Replace with:

```css
.host-workspace .saved-views:empty { display: none; }
.host-workspace .saved-views { margin: 0 auto 15px; }
.host-workspace .onboarding-banner, .host-workspace .onboarding-finish { box-shadow: none; background: #fbeae2; }
.host-workspace .page-toolbar { gap: 8px; }
```

Edit 3 of 5. Find (exactly once):

```css
    gap: 8px;
  }
  .host-workspace .notification-bubble,
  .host-workspace .notification-more {
    border-radius: 22px;
    border: 0;
```

Replace with:

```css
    gap: 8px;
  }
  .host-workspace .notification-bubble {
    border-radius: 22px;
    border: 0;
```

Edit 4 of 5. Find (exactly once):

```css
}
.host-property-save { position: sticky; bottom: 12px; z-index: 19; width: fit-content; background: white; border: 1px solid var(--line); border-radius: 12px; padding: 12px; box-shadow: var(--shadow-popover); }
.host-today-actions { display: flex; flex-direction: column; align-items: flex-end; gap: 8px; }
.host-today-actions .page-toolbar, .host-today-actions .page-toolbar-row { margin: 0; padding: 0; }
.host-workspace { --action-gap: 8px; --action-height: 42px; }
.host-workspace .action-group { display: flex; align-items: center; gap: var(--action-gap); }
```

Replace with:

```css
}
.host-property-save { position: sticky; bottom: 12px; z-index: 19; width: fit-content; background: white; border: 1px solid var(--line); border-radius: 12px; padding: 12px; box-shadow: var(--shadow-popover); }
.host-workspace { --action-gap: 8px; --action-height: 42px; }
.host-workspace .action-group { display: flex; align-items: center; gap: var(--action-gap); }
```

Edit 5 of 5. Find (exactly once):

```css
.host-workspace .action-group > form > .btn,
.host-workspace .action-group .sync-cta .btn { height: var(--action-height); min-height: var(--action-height); }
.host-workspace .action-group-equal > .btn,
.host-workspace .action-group-equal > form,
.host-workspace .action-group-equal > .sync-cta { flex: 1 1 0; min-width: 0; }
.host-workspace .action-group-equal > form > .btn,
.host-workspace .action-group-equal .sync-cta .btn { width: 100%; }
.host-workspace .action-group .sync-cta { display: flex; }
.host-workspace .action-group .sync-cta-form { flex: 1; }
```

Replace with:

```css
.host-workspace .action-group > form > .btn,
.host-workspace .action-group .sync-cta .btn { height: var(--action-height); min-height: var(--action-height); }
.host-workspace .action-group .sync-cta { display: flex; }
.host-workspace .action-group .sync-cta-form { flex: 1; }
```

Why: A63. Selectors no template, script or Python references.

Verify: `pt tests/test_host_geometry.py tests/test_signed_in_chrome.py tests/test_guest_browser_e2e.py` passes.

#### T125 Remove CSS rules nothing uses (components.css)

File: `App/app/static/components.css`

Action: REPLACE ENTIRE FILE

Depends on: none

Code:

Full content:

```css
/* Shared host primitives. Structural chrome stays neutral; color is reserved
   for status, urgency, focus, and stable property identity. */
.command-trigger { display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:9px;width:100%;margin:0 0 14px;padding:9px 10px;border:1px solid color-mix(in srgb,var(--blue) 18%,var(--border));border-radius:var(--radius-md);background:linear-gradient(135deg,var(--blue-bg),var(--purple-bg));color:var(--ink-secondary);font:inherit;font-size:var(--text-sm);text-align:left;cursor:pointer;box-shadow:0 1px 2px rgba(20,20,18,.05) }
.command-trigger:hover { border-color:color-mix(in srgb,var(--blue) 36%,var(--border));color:var(--ink);transform:translateY(-1px) }
.command-trigger-icon { display:grid;place-items:center;width:24px;height:24px;border-radius:7px;background:var(--surface-raised);color:var(--blue);font-size:18px;box-shadow:0 1px 3px rgba(20,20,18,.1) }
kbd { padding:1px 5px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--surface);color:var(--ink-muted);font:11px/1.5 var(--font-sans) }
.saved-views { display:grid;gap:2px;margin:0 0 12px }
.saved-views:empty { display:none }
.saved-views .nav-label { padding-left:4px }
.saved-views a { display:block;padding:6px 8px;overflow:hidden;border-radius:var(--radius-sm);color:var(--ink-muted);font-size:var(--text-sm);text-decoration:none;text-overflow:ellipsis;white-space:nowrap }
.saved-views a:hover { color:var(--ink);background:var(--surface-hover) }
.stays-toolbar { display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px;margin:0 0 16px }
.stays-toolbar .chips { margin-bottom:0 }
.property-identity { display:inline-flex;align-items:center;gap:var(--space-2);min-width:0 }
.property-mark,.avatar { display:inline-grid;place-items:center;width:28px;height:28px;flex:0 0 auto;border-radius:var(--radius-sm);background:var(--gray-bg);color:var(--gray);font-size:var(--text-sm);font-weight:750;text-transform:uppercase }
.property-tone-0 { background:var(--blue-bg);color:var(--blue) }
.property-tone-1 { background:var(--purple-bg);color:var(--purple) }
.property-tone-2 { background:var(--teal-bg);color:var(--teal) }
.property-tone-3 { background:var(--orange-bg);color:var(--orange) }
.property-tone-4 { background:var(--pink-bg);color:var(--pink) }
.property-tone-5 { background:var(--green-bg);color:var(--green) }
.property-tone-6 { background:var(--indigo-bg);color:var(--indigo) }
.property-tone-7 { background:var(--brown-bg);color:var(--brown) }
.property-tone-8 { background:var(--amber-bg);color:var(--amber) }
.property-tone-9 { background:var(--red-bg);color:var(--red) }

.switch { display:inline-flex;align-items:center;gap:var(--space-2);min-height:32px }
.switch input { appearance:none;width:34px;height:20px;margin:0;border:1px solid var(--border-strong);border-radius:var(--radius-pill);background:var(--surface-active);cursor:pointer;transition:background var(--motion-fast) var(--ease-standard) }
.switch input::after { content:"";display:block;width:14px;height:14px;margin:2px;border-radius:50%;background:var(--surface-raised);box-shadow:0 1px 2px rgba(0,0,0,.22);transition:transform var(--motion-fast) var(--ease-standard) }
.switch input:checked { background:var(--brand);border-color:var(--brand) }
.switch input:checked::after { transform:translateX(14px) }

[data-tooltip] { position:relative }
[data-tooltip]::after { content:attr(data-tooltip);position:absolute;left:50%;bottom:calc(100% + 7px);z-index:var(--z-popover);max-width:240px;padding:5px 8px;border-radius:var(--radius-xs);background:var(--ink);color:var(--canvas);font-size:var(--text-xs);line-height:1.35;white-space:nowrap;opacity:0;pointer-events:none;transform:translate(-50%,3px);transition:opacity var(--motion-fast),transform var(--motion-fast) }
[data-tooltip]:hover::after,[data-tooltip]:focus-visible::after { opacity:1;transform:translate(-50%,0) }
html:not(.has-js) .row-menu-trigger { display:none }
html:not(.has-js) .row-menu-panel[hidden] {
  position:static!important;
  display:flex!important;
  flex-wrap:wrap;
  gap:4px;
  width:auto;
  padding:0;
  border:0;
  background:transparent;
  box-shadow:none;
}
html:not(.has-js) .row-menu-item { width:auto;padding:5px 7px;text-decoration:underline }
/* Placeholders for content on its way. Static on purpose: DESIGN.md
   allows no looping animation, so there is no shimmer. */
.skeleton { display:block;min-height:12px;border-radius:var(--radius-xs);background:var(--surface-active) }
.skeleton-line { height:12px;margin:10px 0 }
.skeleton-line.short { width:40% }
.skeleton-line.medium { width:70% }
.skeleton-block { height:96px;margin:16px 0;border-radius:var(--radius-sm) }
.page-skeleton { padding-top:8px;animation:skeleton-in var(--motion-base) var(--ease-standard) both }
.page-skeleton[hidden] { display:none }
main[aria-busy="true"] > :not([data-page-skeleton]) { display:none }
.command-skeleton { margin:12px 14px }
@keyframes skeleton-in { from { opacity:0 } }
@media (hover:hover) {
  tbody tr .row-actions>* { opacity:0;transition:opacity var(--motion-fast) }
  tbody tr:hover .row-actions>*,tbody tr:focus-within .row-actions>*,tbody tr.row-selected .row-actions>* { opacity:1 }
}

dialog { color:var(--ink-secondary);background:var(--surface-raised) }
dialog::backdrop { background:rgba(10,10,9,.58) }
.command-dialog,.shortcuts-dialog { width:min(640px,calc(100vw - 24px));max-height:min(680px,calc(100vh - 40px));padding:0;border:1px solid var(--border-strong);border-radius:var(--radius-lg);background:var(--surface-raised);box-shadow:var(--shadow-dialog) }
.command-dialog { margin-top:max(8vh,32px) }
.command-shell { overflow:hidden }
.command-search { display:flex;align-items:center;gap:10px;padding:14px 16px;border-bottom:1px solid var(--border) }
.command-search>span { color:var(--ink-muted);font-size:22px }
.command-search input { flex:1;min-width:0;padding:4px 0;border:0;border-radius:0;background:transparent;font-size:var(--text-md);box-shadow:none }
.command-search input:focus { box-shadow:none }
.command-close { display:grid;place-items:center;width:30px;height:30px;padding:0;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--surface-hover);color:var(--ink-muted);font-size:20px;line-height:1;cursor:pointer }
.command-close:hover { color:var(--ink);background:var(--surface-active) }
.command-results { max-height:min(520px,65vh);padding:6px;overflow-y:auto }
.command-option { display:flex;align-items:center;gap:10px;width:100%;padding:9px 10px;border:0;border-radius:var(--radius-sm);background:transparent;color:var(--ink-secondary);font:inherit;text-align:left;cursor:pointer }
.command-option.is-selected { background:var(--surface-hover);color:var(--ink) }
.command-option-copy { display:grid;flex:1;min-width:0 }
.command-option-copy strong,.command-option-copy small { overflow:hidden;text-overflow:ellipsis;white-space:nowrap }
.command-option-copy strong { font-size:var(--text-base) }
.command-option-copy small,.command-group { color:var(--ink-muted);font-size:var(--text-xs) }
.command-empty { padding:32px;color:var(--ink-muted);text-align:center }
.shortcuts-shell { padding:20px }
.shortcuts-shell .section-heading { margin:0 0 12px }
.shortcut-list { display:grid;margin:0 }
.shortcut-list>div { display:grid;grid-template-columns:150px 1fr;gap:16px;padding:10px 0;border-top:1px solid var(--border) }
.shortcut-list dt,.shortcut-list dd { margin:0 }
.shortcut-list dd { color:var(--ink-muted) }
@media (max-width:560px) {
  .command-dialog { width:calc(100vw - 16px);max-height:calc(100dvh - 16px);margin:8px auto;border-radius:18px }
  .command-search { padding:12px }
  .command-results { max-height:calc(100dvh - 82px) }
  .command-group { display:none }
  .shortcut-list>div { grid-template-columns:120px 1fr }
  .command-trigger kbd { display:none }
}

/* Match shared controls to the colorful, crisp workspace shell. */
.command-trigger {
  min-height:38px;
  margin-bottom:12px;
  border:1px solid var(--border-strong);
  border-radius:10px;
  background:var(--surface);
  color:var(--ink-secondary);
  font-weight:640;
  box-shadow:0 1px 2px rgba(32,32,30,.06);
}
.command-trigger:hover {
  border-color:color-mix(in srgb,var(--brand) 38%,var(--border-strong));
  color:var(--ink);
  transform:none;
  box-shadow:0 2px 8px rgba(32,32,30,.09);
}
.command-trigger-icon {
  border:1px solid var(--border);
  color:var(--brand-ink);
  background:var(--brand-soft);
  box-shadow:none;
}
.property-mark,.avatar { border:1px solid color-mix(in srgb,currentColor 28%,transparent) }
.command-dialog,.shortcuts-dialog {
  border:2px solid var(--ink);
  box-shadow:8px 9px 0 rgba(32,32,30,.32);
}
.command-search { background:linear-gradient(135deg,var(--amber-bg),var(--surface) 52%) }
.command-option { border-radius:9px }
.command-option.is-selected { color:var(--ink);background:var(--blue-bg) }
```

Why: A63. Selectors no template, script or Python references.

Verify: `pt tests/test_host_geometry.py tests/test_signed_in_chrome.py tests/test_guest_browser_e2e.py` passes.

#### T126 Remove CSS rules nothing uses (guest.css)

File: `App/app/static/guest.css`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```css
  transform: none;
}
.g-range-cue {
  position: relative;
  align-self: stretch;
  width: 18px;
  flex: 0 0 18px;
}
.g-range-cue::before,
.g-range-cue::after {
  content: "";
  position: absolute;
  left: 5px;
  z-index: 1;
  width: 8px;
  height: 8px;
  border: 2px solid var(--g-line-2);
  border-radius: 50%;
  background: var(--g-surface);
  transition: border-color 160ms var(--g-ease), background 160ms var(--g-ease);
}
.g-range-cue::before { top: 4px; }
.g-range-cue::after { bottom: 4px; }
.g-range-cue i {
  position: absolute;
  left: 8px;
  top: 13px;
  bottom: 13px;
  width: 2px;
  background: var(--g-line-2);
  transition: background 160ms var(--g-ease);
}
.g-arrival-lane:hover .g-range-cue::before,
.g-arrival-lane:hover .g-range-cue::after,
.g-arrival-lane:focus-visible .g-range-cue::before,
.g-arrival-lane:focus-visible .g-range-cue::after {
  border-color: var(--g-accent);
  background: var(--g-accent);
}
.g-arrival-lane:hover .g-range-cue i,
.g-arrival-lane:focus-visible .g-range-cue i { background: var(--g-accent); }
.g-arrival-lane:active { transform: translateY(1px); opacity: .88; }
.g-lane-status { display: inline; margin-left: 8px; color: var(--g-ok) !important; font-weight: 650; }
```

Replace with:

```css
  transform: none;
}
.g-arrival-lane:active { transform: translateY(1px); opacity: .88; }
.g-lane-status { display: inline; margin-left: 8px; color: var(--g-ok) !important; font-weight: 650; }
```

Why: A63. Selectors no template, script or Python references.

Verify: `pt tests/test_host_geometry.py tests/test_signed_in_chrome.py tests/test_guest_browser_e2e.py` passes.

#### T127 Bump stylesheet version (base)

File: `App/app/templates/base.html`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```html
  <link rel="icon" type="image/png" sizes="64x64" href="/static/favicon.png">
  <link rel="apple-touch-icon" sizes="180x180" href="/static/apple-touch-icon.png">
  <link rel="stylesheet" href="/static/tokens.css?v=20260914d">
  <link rel="stylesheet" href="/static/app.css?v=20261001d">
  <link rel="stylesheet" href="/static/components.css?v=20261001c">
  {% if show_nav | default(true) %}<link rel="stylesheet" href="/static/host.css?v=20261001j">{% endif %}
</head>
<body class="layout-host {{ 'host-workspace' if show_nav | default(true) }} {{ 'no-nav' if not (show_nav | default(true)) }}">
```

Replace with:

```html
  <link rel="icon" type="image/png" sizes="64x64" href="/static/favicon.png">
  <link rel="apple-touch-icon" sizes="180x180" href="/static/apple-touch-icon.png">
  <link rel="stylesheet" href="/static/tokens.css?v=20261002a">
  <link rel="stylesheet" href="/static/app.css?v=20261002a">
  <link rel="stylesheet" href="/static/components.css?v=20261002a">
  {% if show_nav | default(true) %}<link rel="stylesheet" href="/static/host.css?v=20261002a">{% endif %}
</head>
<body class="layout-host {{ 'host-workspace' if show_nav | default(true) }} {{ 'no-nav' if not (show_nav | default(true)) }}">
```

Why: Browsers must fetch the new CSS instead of a cached copy.

Verify: `grep -c '?v=20261002a' App/app/templates/base.html` is at least 1. In a browser, the page source of / (signed in) shows it.

#### T128 Bump stylesheet version (auth_base)

File: `App/app/templates/auth_base.html`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```html
  <link rel="icon" type="image/png" sizes="64x64" href="/static/favicon.png">
  <link rel="apple-touch-icon" sizes="180x180" href="/static/apple-touch-icon.png">
  <link rel="stylesheet" href="/static/tokens.css?v=20260914d">
  <link rel="stylesheet" href="/static/app.css?v=20260929a">
  <link rel="stylesheet" href="/static/components.css?v=20260919v">
</head>
<body class="auth-page">
```

Replace with:

```html
  <link rel="icon" type="image/png" sizes="64x64" href="/static/favicon.png">
  <link rel="apple-touch-icon" sizes="180x180" href="/static/apple-touch-icon.png">
  <link rel="stylesheet" href="/static/tokens.css?v=20261002a">
  <link rel="stylesheet" href="/static/app.css?v=20261002a">
  <link rel="stylesheet" href="/static/components.css?v=20261002a">
</head>
<body class="auth-page">
```

Why: Browsers must fetch the new CSS instead of a cached copy.

Verify: `grep -c '?v=20261002a' App/app/templates/auth_base.html` is at least 1. In a browser, the page source of /login shows it.

#### T129 Bump stylesheet version (guest/base)

File: `App/app/templates/guest/base.html`

Action: EDIT

Depends on: none

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```html
  <link rel="icon" type="image/png" sizes="64x64" href="/static/favicon.png">
  <link rel="apple-touch-icon" sizes="180x180" href="/static/apple-touch-icon.png">
  <link rel="stylesheet" href="/static/tokens.css?v=20260914d">
  <link rel="stylesheet" href="/static/guest.css?v=20260929a">
  <link rel="stylesheet" href="/static/guest-ticket.css?v=20260930a">
</head>
```

Replace with:

```html
  <link rel="icon" type="image/png" sizes="64x64" href="/static/favicon.png">
  <link rel="apple-touch-icon" sizes="180x180" href="/static/apple-touch-icon.png">
  <link rel="stylesheet" href="/static/tokens.css?v=20261002a">
  <link rel="stylesheet" href="/static/guest.css?v=20261002a">
  <link rel="stylesheet" href="/static/guest-ticket.css?v=20260930a">
</head>
```

Why: Browsers must fetch the new CSS instead of a cached copy.

Verify: `grep -c '?v=20261002a' App/app/templates/guest/base.html` is at least 1. In a browser, the page source of a guest link /l/<token> shows it.

#### T130 Bump stylesheet version (public_legal_base)

File: `App/app/templates/public_legal_base.html`

Action: REPLACE ENTIRE FILE

Depends on: none

Code:

Full content:

```html
{#- The shell every public legal page shares.

    These five pages used to extend `base.html`, the signed-in host shell, with
    `show_nav = false`. That meant an anonymous visitor — a prospect, or a
    lawyer following a link out of the login page — was served the command
    palette, the CSV-export dialog, the keyboard-shortcut sheet and `app.js` for
    a page of prose, and the only way out was "Back to login".

    Now they get the marketing header and footer, the CZ/EN switch, and a
    reading column, and no host furniture at all.

    `no-nav` stays only as the CSS hook that gives the reading column its width
    and the page header its static position (`app.css`); it pulls in nothing. -#}
<!doctype html>
<html lang="{{ lang }}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#f7f7f5">
  <title>{% block title %}UbyHost{% endblock %}</title>
  {% include "_seo_head.html" %}
  <link rel="icon" type="image/png" sizes="64x64" href="/static/favicon.png">
  <link rel="apple-touch-icon" sizes="180x180" href="/static/apple-touch-icon.png">
  <link rel="stylesheet" href="/static/tokens.css?v=20261002a">
  {#- landing.css first so app.css keeps the reading typography and the link
      colour; it is here only for the shared header and footer. -#}
  <link rel="stylesheet" href="/static/landing.css?v=20260919y">
  <link rel="stylesheet" href="/static/app.css?v=20261002a">
  <link rel="stylesheet" href="/static/components.css?v=20261002a">
</head>
<body class="layout-host no-nav">
{#- No nav item names a legal page, and the language switch comes back here. -#}
{% set active = '' %}{% set switch_path = request.url.path %}
{% include "_public_header.html" %}
<main id="content" class="wrap {{ wrap_class | default('') }}">
  {% block content %}{% endblock %}
</main>
{% include "_public_footer.html" %}
</body>
</html>
```

Why: Browsers must fetch the new CSS instead of a cached copy.

Verify: `grep -c '?v=20261002a' App/app/templates/public_legal_base.html` is at least 1. In a browser, the page source of /privacy shows it.

#### T131 A print-sized logo for PDFs

File: `App/app/pdf_mark.py`

Action: CREATE

Depends on: none

Code:

Full content:

```python
"""The UbyHost mark, sized for print.

The web mark is a 512 px RGBA PNG. Embedded as is, it made up about 140 KB of
every invoice and stay-fee PDF, while printing at 3.6-4.5 mm. 192 px is still
over 1,000 dpi at that size, so the printed mark looks identical.
"""
from __future__ import annotations

import io
import os
from functools import lru_cache

from PIL import Image
from reportlab.lib.utils import ImageReader

SOURCE = os.path.join(os.path.dirname(__file__), "static", "ubyhost-mark.png")
PRINT_PX = 192


@lru_cache(maxsize=1)
def _png() -> bytes:
    with Image.open(SOURCE) as image:
        mark = image.convert("RGBA")
        mark.thumbnail((PRINT_PX, PRINT_PX), Image.LANCZOS)
        out = io.BytesIO()
        mark.save(out, "PNG", optimize=True)
    return out.getvalue()


def reader() -> ImageReader:
    """A fresh reader per document; the resized bytes are computed once."""
    return ImageReader(io.BytesIO(_png()))
```

Why: Each stored PDF embedded the 512 px web logo (about 140 KB). 192 px is still over 1,000 dpi at the printed 4.5 mm, so it looks the same. Pillow is already a dependency.

Verify: After T134.

#### T132 Invoice PDFs use the print-sized logo

File: `App/app/invoice_pdf.py`

Action: EDIT

Depends on: T37, T131

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 3. Find (exactly once):

```python
from reportlab.pdfgen import canvas as pdfcanvas

from . import payments

# ---- fonts: DejaVu Sans covers all of Czech; vendored under static/fonts ----
```

Replace with:

```python
from reportlab.pdfgen import canvas as pdfcanvas

from . import payments, pdf_mark

# ---- fonts: DejaVu Sans covers all of Czech; vendored under static/fonts ----
```

Edit 2 of 3. Find (exactly once):

```python
GREEN_BG = (0xE6 / 255, 0xF5 / 255, 0xEC / 255)

MARK_PATH = os.path.join(os.path.dirname(__file__), "static", "ubyhost-mark.png")
FOOTER_URL = "https://ubyhost.com/?utm_source=invoice&utm_medium=pdf"

```

Replace with:

```python
GREEN_BG = (0xE6 / 255, 0xF5 / 255, 0xEC / 255)

FOOTER_URL = "https://ubyhost.com/?utm_source=invoice&utm_medium=pdf"

```

Edit 3 of 3. Find (exactly once):

```python
    c.line(M, M + 5 * mm, W - M, M + 5 * mm)
    mark = 3.6 * mm
    c.drawImage(MARK_PATH, M, M - 0.4 * mm, mark, mark, mask="auto")
    credit = f"{L['footer']}  ·  ubyhost.com"
    _text(c, M + mark + 1.8 * mm, M + 0.4 * mm, credit, size=7, color=FAINT)
```

Replace with:

```python
    c.line(M, M + 5 * mm, W - M, M + 5 * mm)
    mark = 3.6 * mm
    c.drawImage(pdf_mark.reader(), M, M - 0.4 * mm, mark, mark, mask="auto")
    credit = f"{L['footer']}  ·  ubyhost.com"
    _text(c, M + mark + 1.8 * mm, M + 0.4 * mm, credit, size=7, color=FAINT)
```

Why: Invoice PDF 197 KB to 74 KB.

Verify: After T134.

#### T133 Stay-fee PDFs use the print-sized logo

File: `App/app/stay_fee_remittance_pdf.py`

Action: EDIT

Depends on: T131

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 2. Find (exactly once):

```python
from reportlab.pdfgen import canvas as pdfcanvas

_FONT_DIR = os.path.join(os.path.dirname(__file__), "static", "fonts")
pdfmetrics.registerFont(TTFont("UHRemit", os.path.join(_FONT_DIR, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("UHRemit-Bold", os.path.join(_FONT_DIR, "DejaVuSans-Bold.ttf")))
REG, BOLD = "UHRemit", "UHRemit-Bold"
MARK = os.path.join(os.path.dirname(__file__), "static", "ubyhost-mark.png")

W, H = A4
```

Replace with:

```python
from reportlab.pdfgen import canvas as pdfcanvas

from . import pdf_mark

_FONT_DIR = os.path.join(os.path.dirname(__file__), "static", "fonts")
pdfmetrics.registerFont(TTFont("UHRemit", os.path.join(_FONT_DIR, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("UHRemit-Bold", os.path.join(_FONT_DIR, "DejaVuSans-Bold.ttf")))
REG, BOLD = "UHRemit", "UHRemit-Bold"

W, H = A4
```

Edit 2 of 2. Find (exactly once):

```python
def _footer(c, page: int):
    _rule(c, 20 * mm)
    c.drawImage(ImageReader(MARK), M, 12.7 * mm, 4.5 * mm, 4.5 * mm, mask="auto")
    _text(c, M + 6.5 * mm, 14 * mm, "UbyHost", size=8.5, bold=True)
    _text(c, M + 32 * mm, 14 * mm, "Vytvořeno v UbyHost", size=7, color=MUTED)
```

Replace with:

```python
def _footer(c, page: int):
    _rule(c, 20 * mm)
    c.drawImage(pdf_mark.reader(), M, 12.7 * mm, 4.5 * mm, 4.5 * mm, mask="auto")
    _text(c, M + 6.5 * mm, 14 * mm, "UbyHost", size=8.5, bold=True)
    _text(c, M + 32 * mm, 14 * mm, "Vytvořeno v UbyHost", size=7, color=MUTED)
```

Why: Same saving for stored stay-fee PDFs.

Verify: `pt tests/test_stay_fee.py tests/test_stay_fee_signature.py` passes.

#### T134 Test stored PDFs stay small

File: `App/tests/test_invoice_pdf.py`

Action: EDIT

Depends on: T41, T131

Code:

Apply in order, each against the file as left by the previous edit.

Edit 1 of 1. Find (exactly once):

```python
    with pytest.raises(sqlite3.DatabaseError, match="immutable"):
        db.execute("UPDATE invoice SET note = 'Jiná' WHERE id = ?", (invoice,))
```

Replace with:

```python
    with pytest.raises(sqlite3.DatabaseError, match="immutable"):
        db.execute("UPDATE invoice SET note = 'Jiná' WHERE id = ?", (invoice,))


def test_the_printed_mark_is_small_so_stored_pdfs_stay_small():
    from app import pdf_mark

    assert len(pdf_mark._png()) < 40_000
    data = invoice_pdf.render(_inv(), [dict(ACCOM, vat_rate=None, base_haler=None, vat_haler=None)], "cs")
    assert len(data) < 100_000, "the full-size web mark was embedded again"
```

Why: Fails if the full-size logo is embedded again.

Verify: `pt tests/test_invoice_pdf.py` passes.

#### T135 Delete App/app/static/favicon.svg

File: `App/app/static/favicon.svg`

Action: DELETE

Depends on: none

Code:

Run: `git rm App/app/static/favicon.svg`

Why: A64. Not read by code, CI, the Dockerfile or tests.

Verify: `git grep -n <path>` finds no live reference; full suite passes.

#### T136 Delete CURSOR_REMEDIATION_PLAN.md

File: `CURSOR_REMEDIATION_PLAN.md`

Action: DELETE

Depends on: none

Code:

Run: `git rm CURSOR_REMEDIATION_PLAN.md`

Why: A64. Not read by code, CI, the Dockerfile or tests.

Verify: `git grep -n <path>` finds no live reference; full suite passes.

#### T137 Delete artifacts

File: `artifacts`

Action: DELETE

Depends on: none

Code:

Run: `git rm -r artifacts`

Why: A64. Not read by code, CI, the Dockerfile or tests.

Verify: `git grep -n <path>` finds no live reference; full suite passes.

#### T138 Delete deploy/lightsail/caddy/Caddyfile

File: `deploy/lightsail/caddy/Caddyfile`

Action: DELETE

Depends on: none

Code:

Run: `git rm deploy/lightsail/caddy/Caddyfile`

Why: A64. Not read by code, CI, the Dockerfile or tests.

Verify: `git grep -n <path>` finds no live reference; full suite passes.

#### T139 Delete docs/plans/ticket-wallet

File: `docs/plans/ticket-wallet`

Action: DELETE

Depends on: none

Code:

Run: `git rm -r docs/plans/ticket-wallet`

Why: A64. Not read by code, CI, the Dockerfile or tests.

Verify: `git grep -n <path>` finds no live reference; full suite passes.

#### T140 Delete docs/plans/ticket-wallet-v3-stay-fee-audit

File: `docs/plans/ticket-wallet-v3-stay-fee-audit`

Action: DELETE

Depends on: none

Code:

Run: `git rm -r docs/plans/ticket-wallet-v3-stay-fee-audit`

Why: A64. Not read by code, CI, the Dockerfile or tests.

Verify: `git grep -n <path>` finds no live reference; full suite passes.

#### T141 Delete docs/plans/stay-fee-audit-new

File: `docs/plans/stay-fee-audit-new`

Action: DELETE

Depends on: none

Code:

Run: `git rm docs/plans/stay-fee-audit-new`

Why: A64. Not read by code, CI, the Dockerfile or tests.

Verify: `git grep -n <path>` finds no live reference; full suite passes.

#### T142 Delete docs/plans/host-app-redesign/host-app-redesign/payload

File: `docs/plans/host-app-redesign/host-app-redesign/payload`

Action: DELETE

Depends on: none

Code:

Run: `git rm -r docs/plans/host-app-redesign/host-app-redesign/payload`

Why: A64. Not read by code, CI, the Dockerfile or tests.

Verify: `git grep -n <path>` finds no live reference; full suite passes.

#### T143 Delete docs/plans/host-app-redesign/host-app-redesign/implementation.patch

File: `docs/plans/host-app-redesign/host-app-redesign/implementation.patch`

Action: DELETE

Depends on: none

Code:

Run: `git rm docs/plans/host-app-redesign/host-app-redesign/implementation.patch`

Why: A64. Not read by code, CI, the Dockerfile or tests.

Verify: `git grep -n <path>` finds no live reference; full suite passes.

#### T144 Delete docs/plans/host-app-redesign/host-app-redesign/apply_handoff.py

File: `docs/plans/host-app-redesign/host-app-redesign/apply_handoff.py`

Action: DELETE

Depends on: none

Code:

Run: `git rm docs/plans/host-app-redesign/host-app-redesign/apply_handoff.py`

Why: A64. Not read by code, CI, the Dockerfile or tests.

Verify: `git grep -n <path>` finds no live reference; full suite passes.

#### T145 Delete docs/plans/host-app-redesign/host-app-redesign/manifest.json

File: `docs/plans/host-app-redesign/host-app-redesign/manifest.json`

Action: DELETE

Depends on: none

Code:

Run: `git rm docs/plans/host-app-redesign/host-app-redesign/manifest.json`

Why: A64. Not read by code, CI, the Dockerfile or tests.

Verify: `git grep -n <path>` finds no live reference; full suite passes.

#### T146 Delete docs/plans/host-app-redesign/host-app-redesign/package-verification.json

File: `docs/plans/host-app-redesign/host-app-redesign/package-verification.json`

Action: DELETE

Depends on: none

Code:

Run: `git rm docs/plans/host-app-redesign/host-app-redesign/package-verification.json`

Why: A64. Not read by code, CI, the Dockerfile or tests.

Verify: `git grep -n <path>` finds no live reference; full suite passes.

#### T147 Delete docs/plans/host-app-redesign/host-app-redesign/CURSOR_PROMPT.md

File: `docs/plans/host-app-redesign/host-app-redesign/CURSOR_PROMPT.md`

Action: DELETE

Depends on: none

Code:

Run: `git rm docs/plans/host-app-redesign/host-app-redesign/CURSOR_PROMPT.md`

Why: A64. Not read by code, CI, the Dockerfile or tests.

Verify: `git grep -n <path>` finds no live reference; full suite passes.

### Phase 5. Verification

#### T148 Lint

File: none (command)

Action: none, run only

Depends on: T147

Code: `cd App && ruff check app tests tools --select E9,F63,F7,F82,F401,F841`

Why: the same lint CI runs.

Verify: "All checks passed!"

#### T149 Full test suite

File: none (command)

Action: none, run only

Depends on: T148

Code: `pt tests` with `UBYHOST_REQUIRE_BROWSER=1`

Why: whole-system regression check. In the reference run all tests passed and the only skips were 2 opt-in tests.

Verify: 0 failed.

#### T150 Guest browser e2e

File: none (command)

Action: none, run only

Depends on: T149

Code: `UBYHOST_REQUIRE_BROWSER=1 pt tests/test_guest_browser_e2e.py -rs`

Why: AGENTS.md requires this before any guest-page change. T126 and T129 touch guest CSS and markup.

Verify: 4 passed, 0 skipped.

#### T151 Diff review

File: none (command)

Action: none, run only

Depends on: T150

Code: `git diff --stat main...HEAD` and `git diff main...HEAD -- App/app/data/countries.json App/app/host_i18n.py App/app/icalsync.py App/app/mail.py App/app/mail_notify.py App/app/reporting.py App/app/retention.py App/app/routes/admin_accounts.py App/app/routes/guest.py App/app/routes/stay_fees.py App/app/stay_fee.py App/app/stay_fee_filing.py`

Why: a human reads every HIGH RISK diff (T11, T13, T15, T16, T31, T32, T33, T48, T49, T57, T59, T60, T61, T62, T63) before merging.

Verify: those files contain only the changes in the HIGH RISK tasks and in the other tasks that name them.

## Manual go-live checklist

Run this on staging with the mock UbyPort first. Then repeat the filing steps on production with one real test stay.

Guest flow (phone, then desktop):

1. Add a property with a real Airbnb or Booking iCal URL. Run "Update calendars". Stays appear with Czech names spelled correctly (A20).
2. Open a stay's guest link on a phone. A wrong PIN shows the error, and the right PIN opens the form. With Turnstile on, after many wrong PINs the link asks for the security check instead of locking (T45).
3. Pick Kosovo as a nationality. The form accepts it. On production, file one such test guest and confirm UbyPort accepts XKX (T57).
4. Fill in two guests, one of them a child. Sign, submit, and reopen the link: the forms are locked as signed.
5. On the stay page, the guest count reads 2 / 2 and the status is Ready (blue).
6. If the property asks for a document photo, upload one. Verify the guest and check that the photo is gone.
7. Open `/doesnotexist` and see the branded 404 page, in CS and EN.
8. Extend a signed stay by one night in the calendar. Both guests must sign again; after only one has signed, the stay is still held (T49).
9. Sign in on two browsers, log out on one. The other is signed out too (T43).

Police filing:

1. Settings, Automation & UbyPort: "Save and test connection" succeeds.
2. Manual mode: send the stay. It shows Reported (green), and the receipt (Doručenka) downloads. Send it again: it is accepted as a duplicate and also shows green (T109).
3. Scheduled mode: a complete stay is sent by the next sweep.
4. Enter a wrong UbyPort password. Within one save in immediate mode, sending pauses and the "login refused" alert shows. No further login attempts appear in the log (T15). Restore the password.
5. Remove a stay with filled-in forms from the feed. After sync, the "cancelled with guests" warning appears and nothing is sent (T16).
6. Stop the app during a send, for example by restarting the container on staging. On the next sweep the batch shows Outcome unknown (red) and is not resent (T13).

Stay fee:

1. With last month selected by default, the filters show Property (only if there is more than one property) and Status.
2. Add a guest who turns 18 in the middle of the period. "Save period" succeeds, and the hlášení PDF lists the minor nights (T01).
3. Open the register CSV in Excel or Numbers. A guest address starting with `=` or `@` shows as text (T05).
4. "Start correction" on a saved period creates v2. Change the property's rate first: the correction still uses the sealed rate (T32).

Invoices:

1. Filter by month, property, status (Unpaid, Paid, Corrections) and search (number or customer). Reset clears everything and the badge count goes to 0.
2. Enter "1.000,50". The total is 1 000,50 Kč.
3. A 5th item is refused with the item-limit message. Four two-line items fit on one page with the QR code.
4. Add a note. It shows on the invoice page and the PDF. A note too long for one page is refused at issue with the "does not fit" message (T38). The PDF is about 75 KB, not 200 KB.
5. Mark one invoice paid and storno another. In the list, the paid invoice shows Paid (green) and an open one shows Awaiting payment (teal). The cancelled original and its cancellation document show grey. The cancel form is still shown on the cancelled original; that is known issue A10.

Mobile (390 px and 360 px, CS and EN):

1. Dashboard, Stays, Stay fees and Invoices all load without sideways scrolling.
2. The filter fields stack one per row and the month steppers are 44 px tall.
3. The guest form is usable one-handed, and the signature pad works.

Second-host isolation:

1. Create host B with its own property and stay.
2. As host B, open host A's `/reservations/<id>`, `/invoices/<id>` and `/guests/<id>/export.json`. Each returns 404.
3. Host A's guest export contains only host A's audit rows (T06).
4. The filters on B never list A's properties.

Operations:

1. Production `.env` has `UBYHOST_BACKUP_AGE_RECIPIENT` and `UBYHOST_BACKUP_PING_URL` (both now required). Preflight passes.
2. Production `.env` has the operator identity. Put it only in the server `.env`, never in the repo (AGENTS.md, the repo is public). The app refuses to start without name, IČO and address. Your values, from ARES:

   ```
   UBYHOST_OPERATOR_NAME=Josef Pechar
   UBYHOST_OPERATOR_ICO=24005169
   UBYHOST_OPERATOR_DIC=CZ0101190518
   UBYHOST_OPERATOR_ADDRESS=Kubelíkova 697/13, 130 00 Praha 3 - Žižkov
   UBYHOST_OPERATOR_EMAIL=support@ubyhost.com
   UBYHOST_OPERATOR_REGISTRY_URL=https://ares.gov.cz/ekonomicke-subjekty?ico=24005169
   ```

   Then open the Legal notice page and check that the name, IČO and registered address show.
3. With `UBYHOST_GUEST_PIN=0`, an `http://` base URL, or a base URL that does not match `UBYHOST_DOMAIN`, production refuses to start. Try one on staging with `UBYHOST_DEPLOYMENT=production` to see the message.
4. Run one backup by hand and restore it on a scratch machine with `restore.sh`.
5. Set up the off-site copy (backup-s3.sh or backup-gdrive.sh) and confirm one copy arrived.
6. On the deploy workflow, a failing guest-browser or secrets check blocks the deploy (T25).
7. Check the image contents: no `tests/`, `tools/`, `mock_ubyport/` or `.env` (T23).

## Owner decisions (recorded)

Your answers, and where they are in the plan.

- Q1. A correction uses the rate stored with the sealed period. T31 to T34, HIGH RISK (filing).
- Q2. Keep the 4-item cap. No change beyond T07 to T09.
- Q3. Store and print the note. T35 to T41. An invoice that would no longer fit one page is refused at issue.
- Q4. Log out signs out every device. T42 to T44.
- Q5. With Turnstile, a locked guest link asks for the check instead of refusing. T45 to T47. Without Turnstile the 24 h lock stays, so keep Turnstile configured in production.
- Q6. Every guest who had signed must sign again. T48 to T50, HIGH RISK (filing).
- Q7. Kosovo is added as XKX. T57, T58. [ASSUMPTION] XKX is the widely used user-assigned code, not an ISO standard code. Check it against UbyPort's own country list (the cached `staty` list) once the connection works. Accepting every cached police code stays open (A27).
- Q8. Production refuses to start on guest PIN off, a non-https base URL or a domain mismatch, and also without the operator identity. T51 to T53.
- Q9. Deletion stays as designed: a terminated workspace loses everything, including invoices and stay-fee filings. Keeping those is the host's duty as controller. The host is mailed when deletion is scheduled and again 7 days before. T59 to T66, HIGH RISK (retention). Two things to know:
  - Scheduling deletion disables sign-in at once, so the host cannot export alone. The mail asks them to reply to support@ubyhost.com; you then use "Export workspace" on the Users page, or re-enable the account for a while.
  - The 7-day reminder is only sent when `UBYHOST_RETENTION_AUTOPURGE=1`, because only then does deletion really happen.
  - Not legal advice: have a lawyer check that Terms s19 says this plainly (the host must export before the date; nothing is kept after it).
- Q10. A duplicate (code 150) shows green. T109, T110.
- Q11. The backup ping URL is mandatory in production. T54 to T56.
- Q12. The old docs stay in the repo. No change.
- PDF storage. Stored PDFs stay (an issued document must stay byte-identical), but each one now embeds a print-sized logo: 197 KB to 74 KB per invoice. The logo prints at the same 4.5 mm and looks the same (A77).

## Note on the review step

You asked for a check with the "pstack" and "claude council" skills. Neither is installed in this workspace, so I ran three independent reviewer agents instead. One checked the correctness of every claim, one checked security and filing or retention risk, and one replayed the plan from scratch with its own parser.

They found these problems, and all of them are now fixed in the code and the plan:

- A double-filing window in stale-batch recovery. Staleness is now judged by the claim, not by the row's age.
- The guest export missed the guest's own audit rows.
- Workspace deletion left queued mail behind, and it read guest IDs outside the lock.
- The crash page had no security headers, and the crash log line could carry a guest token.
- A 405 lost its Allow header.
- A BOM survived a declared charset.
- An invalid invoice price became 0 Kč instead of blocking the invoice.
- The cancelled-with-guests warning counted Czech nationals, and setting the stay back to Active did not clear it.
- The env template did not list the backup recipient.
- Several overstated audit rows were corrected (A05, A17, A20, A25, A43, A53, A59, A68, A69).
- T01 and T03 are now flagged as stay-fee filing changes, and T06 and T20 are marked for review by hand.

After the fixes, the plan was replayed again on a fresh `main` and the suite was re-run.
