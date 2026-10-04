# UbyHost: product, admin, analytics, infrastructure and scaling review

Basis: the repo at branch `cursor/prelaunch-review-b3bc` (PR 230, head `4fd05de`), which is `main` (`98219d1`) plus the pre-launch plan T01 to T151 and the owner-decision commit. Paths are relative to `App/app/` unless stated. Measurements were taken in a sandbox with the app's own demo data (18 stays, 8 guests). Production data, host count and traffic were not available: anything about them is [ASSUMPTION] or [ESTIMATE]. Vendor prices and limits were checked on official pages on 3 October 2026; sources are listed at the end.

Two corrections to the brief, because several answers depend on them:

- There is no `pick.html?id=12345` URL. `templates/guest/pick.html` exists, but guests reach it through `GET /l/{token}` (`routes/guest.py:917`). The token is 20 characters from a 33-character alphabet, about 101 bits (`auth.py:506`). It is one permanent link per property (`apartment.permalink_token`, UNIQUE, `db.py:88`), and every guest page sits behind a 6-digit PIN (`routes/guest.py:405`). This changes Workstream 5 a lot.
- iCal sync does not run every 5 minutes. It runs hourly by default (`UBYHOST_ICAL_POLL_MINUTES=60`, `config.py:121`) and is already sequential: one `for` loop over feeds (`icalsync.py:797`), in one APScheduler job with `max_instances=1` (`scheduler.py:194`).

## 1. Summary

| Topic | Recommendation | Cost |
|---|---|---|
| Admin scope | The admin area you need already exists (users, impersonation, export, deletion, incident register). Add three small things: a reason and time limit on impersonation, masking of guest identity data while impersonating, and one cross-workspace "Operations" page. Build nothing else. | About 3 to 4 days in total |
| Analytics | No analytics script inside the app. Build the product funnel from data the database already holds (every stage is already a timestamped row), shown on an admin page. Use Plausible (EU, cookieless, about 1.3 KB) on the public marketing pages only. Fallback: Umami Cloud (EU). | Plausible $9 to $19 per month; funnel page about 2 days |
| Infrastructure | Do not move to Lambda + Turso. Stay on one always-on container with local SQLite, and add continuous replication (Litestream to S3), a separate scheduler process, and more web workers. Move stored PDFs and photos to a private S3 bucket later, behind a small storage interface. | Under $25 per month at 100 hosts; about 3 to 5 days of work, spread out |
| SQLite limits | SQLite is not the bottleneck at 100 hosts, or at 1,000. Estimated peak write load at 100 hosts is around 1 to 8 commits per second, against a measured capacity of hundreds per second. The real limits today are one Python process (one uvicorn worker) and one VM. Turso would make this worse, not better: same single writer, plus network latency on every one of the 73 queries the dashboard runs. | See Workstream 4 |
| Database future | The eventual move, if it comes, is to Postgres in Frankfurt, not Turso. Trigger: needing a second app server, or sustained write lock waits. Make the SQL portable now so that move is mechanical. | About 2 days of portability work now |
| Guest URL slugs | Do not replace the random token. If you want branding, add an optional readable prefix (`/l/vinohrady-studio-k7m2qx`) after go-live. Old links keep working forever. Low value, low priority. | About 2 to 3 days, after go-live |

## 2. Part 1. "Reported" and "overdue by 42 h" on the same stay

### 2.1 What "reported" means in this code

A stay is "reported" when every reportable guest has `submit_state = 'sent'` (`reporting.py:334`). A guest becomes `sent` only when UbyPort's synchronous answer classifies that record as accepted (`reporting.py:1224-1260`), including the "already held" duplicate answer (code 150). The Doručenka receipt comes back in the same answer when one is issued.

So "reported" means: the police register accepted the record. It is not just "we sent it". There is no later confirmation step from the police in the code, and UbyPort's accepted answer is the filing.

### 2.2 Display bug or logic bug

It is a display bug. The status and the counts are correct. The deadline badge is computed from the arrival date only and ignores the status.

- The countdown is `deadlines.urgency(check_in)` and `describe_time_left(check_in)` (`deadlines.py:111-131`, `146-165`). Both take only the date.
- The work-queue logic does exclude finished stays from "overdue": `queue_groups` (`reporting.py:372`) and the overdue tile count (`reporting.py:408-412`) both skip `FINISHED_STATUSES`.
- The templates print the badge for every active stay, whatever its status:
  - Dashboard: `templates/dashboard.html:15`
  - Stays list: `templates/reservations.html:164-167`
  - Stay page: `templates/reservation_detail.html:307-311`
- The deadline is the end of the third working day, counting the arrival day (`deadlines.py:75-94`; a Monday arrival is due Wednesday 23:59).
- The dashboard drops a reported stay 3 days after arrival (`reporting.py:546-548`), so there it shows red only briefly, and by less than 24 h.
- The stays list and the stay page have no cutoff. A reported stay there shows "overdue" forever, and "overdue by 42 h" comes from one of these two pages.

One more gap: the badge says nothing about whether the filing was late. That fact exists (`guest.submitted_at` against `deadlines.reporting_deadline(check_in)`), but the app never compares them.

### 2.3 Correct behaviour

Once a stay is finished, the deadline stops being a countdown and becomes a record:

| Stay status | Deadline cell shows | Level |
|---|---|---|
| Not finished (waiting, incomplete, ready, failed) | Countdown as today ("2 days left", "overdue by 5 h") | As today: critical, action or done |
| Reported, on time | "Reported 12.05. 14:32" | done, or plain muted text in tables |
| Reported, after the deadline | "Reported 6 h late" | neutral. It is history; nothing can be fixed now. |
| Not required (Czech guests only) | nothing | not applicable |
| Cancelled or inactive | dash, as today | neutral |

Why not just hide it: hosts and inspectors ask "did I file on time". Showing the filing time answers that without a red badge.

### 2.4 Implementation (for the Cursor pass)

- `reporting.py`: add a helper `filed_at(progress)` that returns the latest `submitted_at` of the reportable guests. Add a field to each dashboard row: `deadline_state` = `countdown`, `filed_on_time` or `filed_late`, plus `filed_at` and `late_hours`. Compute it once per row in `dashboard_rows`.
- `templating.py`: one global `deadline_cell(progress, check_in)` so the three templates share the logic, rather than calling `urgency()` directly.
- `_components.html`: one macro `deadline_badge(...)`. Use it in the three templates above, replacing the raw `<span class="deadline ...">`.
- `host_i18n.py`: three keys in EN and CS (`deadline.filed_at`, `deadline.filed_late_hours`, `deadline.filed_late_days`).
- Tests:
  - A reported stay past its deadline shows no "overdue" in the dashboard, stays list or stay page.
  - A stay filed after its deadline shows "late".
  - An unreported stay past its deadline is still red.
- Effort: S (about half a day). Risk: low. It is display only and does not touch filing.

## 3. Part 2. Owner requests A to F

A to D are already designed, coded and tested in PR 230: tasks T46 to T75, the decisions in `docs/plans/UbyHost_prelaunch_review/UbyHost_prelaunch_review.md` Part 2, and test results in the review. They are summarised here, with what still has to change.

### A. One filter for Stay fees and Invoices (done in PR 230)

- **Shared model:** `list_filter.py`, an immutable `ListFilter(month, apartment_id, status, q)`. Every input is bounded and checked for ownership. State lives only in the URL query.
- **Shared component:** `templates/_list_filter.html`, one GET form. It applies on change, falls back to an Apply button without JS, and shows a reset link with an active-filter count badge.
- **Old code removed:** `list_month_filter.py`, `_host_month_filter.html` and the old CSS.

| Filter | Stay fees | Invoices | Why |
|---|---|---|---|
| Month with back and forward steppers | Required; default is the last finished month | Optional; default is all dates | Stay fees are filed per period; invoices are looked up across time. |
| Property | Only when there is more than one | Same | With one property the control is noise. |
| Status | Needs attention / Ready / Saved, plus In progress (owner decision Q22, PR 230) | Unpaid / Paid / Corrections | Answers "what still needs me". |
| Search | No | Invoice number or customer | Invoices are looked up by number or buyer; stay-fee rows are properties. |
| Reset with count | Yes | Yes | One tap back to the default. |

Remaining: none, apart from the PR 230 fixes already handed to Cursor.

### B. Status colours by criticality (done in PR 230)

There are six levels as CSS tokens in `static/tokens.css`. Every pill, tile and deadline reads from them, and the old one-off tones were removed.

| Level | bg | ink (text) | border | Contrast | Non-colour cue |
|---|---|---|---|---|---|
| critical | #b42318 | #ffffff | #b42318 | 6.57:1 | Solid fill plus a "!" glyph |
| action | #fde9c2 | #6b3a00 | #eec27a | 7.90:1 | Label |
| ready | #e9f0fc | #1d4f9e | #c8d8f3 | 6.88:1 | Label |
| waiting | #eef6f5 | #285e59 | #d3e7e4 | 6.75:1 | Label |
| done | #eef6f1 | #24613f | #d3e8db | 6.68:1 | Label |
| neutral | #ffffff | #5f625f | #deded9 | 6.18:1 | Label, outline only |

All pairs pass WCAG AA for normal text (4.5:1). The full mapping of 45 statuses to levels is in the review document, Part 2 B.

Changes since then:

- A duplicate filing (code 150) is now "done", green.
- "In progress" for a running stay-fee period is "waiting".
- The new reported-on-time and reported-late deadline states from Part 1 map to done and neutral.

### C. "Number of guests not known yet" (done in PR 230)

The macro `guest_count(progress, placeholder)` in `_components.html` shows:

- nothing on the dashboard while the count is unknown;
- in tables, a quiet dash, with "Number of guests not known yet" kept only as screen-reader text (`host_i18n.py:922`);
- once guests are declared, a person icon with "2 / 3".

Status logic does not change, because the count is read from the same `progress` the status pill uses. Remaining: none.

### D. Help & Guide (done in PR 230, needs a second pass)

The guide (`guide_i18n.py`, 89 keys in EN and CS) was written from the code before the owner decisions. Three statements are now wrong and must change in the same PR as the PR 230 fixes:

- `guide.reporting.failure` (`guide_i18n.py:73`) says a send with no answer "is held and you decide". After the PR 230 fix the app retries once on its own, then holds.
- There is no text for scheduled account deletion: banner, sign-in kept until the date, ZIP download.
- There is no text for calendar date changes. Guests do not sign again; the app moves their dates.

Also add one sentence for Part 1: "After a stay is reported, its deadline shows when it was filed." Effort: S.

### E. Remove unnecessary descriptions and marketing

There is no marketing on the guest pages: no "powered by" and no upsell. The guest flow does have about 10 items to cut and 10 to shorten, out of about 40 text items. The signed-in host app has about 25 instances of tagline, AI-sounding or duplicated help text. Landing and legal pages are out of scope: the landing page is meant to sell, and legal text is required.

Guest pages (strings in `i18n.py`, EN line numbers):

| # | Where | Text (short) | Action | Reason |
|---|---|---|---|---|
| 1 | pick.html:9, i18n 65 | "Welcome, guest registration for %s." | Cut | Repeats the heading and property name |
| 2 | pick.html:21, i18n 67 | "Choose your arrival and departure dates to continue." | Cut | The question above already says it |
| 3 | `_why.html:3`, i18n 22 | Four-sentence legal intro | Shorten to one line | Duplicates the legal notice |
| 4 | `_why.html:7-15`, i18n 33-59 | Seven "why" bullets | Cut six, keep the accuracy point | Duplicates the legal notice the guest acknowledges anyway |
| 5 | base.html:57, i18n 393 | Footer data-use paragraph | Shorten | The full text is one link away |
| 6 | `_host.html:3`, i18n 109 | "If there is any problem, feel free to contact your host. UbyHost does not run the property..." | Shorten to "Questions? Contact your host." | Wordy |
| 7 | pin.html:6, i18n 209 | PIN explanation | Shorten | One line is enough |
| 8 | claim.html:32, i18n 118 | "We'll e-mail you a private link..." | Shorten | |
| 9 | claim.html:50, i18n 122 | Three-sentence e-mail help | Cut | Repeats the line above it (i18n 85) |
| 10 | confirm.html:15, i18n 160 | "One tap to confirm it's really you." | Cut | The button says it |
| 11 | assigned.html:26-43 | Four help lines | Shorten to two | Repeats items 8 and 9 |
| 12 | form.html:216, i18n 278 | "...Required by law." | Cut the second sentence | Every field is required by law |
| 13 | form.html:256, i18n 312 | Photo step, three sentences | Shorten; keep the privacy sentence | |
| 14 | stay.html:53, i18n 102 | "Keep this page, it is your confirmation." | Cut | Contradicts "You can close this page" on line 44 |
| 15 | stay.html:59, i18n 270 | "Forgot someone?..." | Shorten | |
| 16 | `_legal_notice.html`, i18n 343, 348, 366 | Intro, duty and reporting sections | Cut the intro, shorten two sections | Retention and legal-basis text stays (GDPR Art. 13) |
| 17 | i18n 344 `legal_notice_disclaimer` | Unused string | Delete | Dead |

Keep: the PIN help, party-size instruction, document, child and visa help, signature line, review lock line, cookie notice, legal notice acknowledgement and privacy page. These are needed to act, or legally required.

Host app (strings in `host_i18n.py`):

| # | Key or place | Action | Reason |
|---|---|---|---|
| 1 | housebook.html:123-141, the legal block shown twice | Keep one copy | Duplicate |
| 2 | `housebook.legal_paper` (373), `legal_footnote` (421) | Shorten | Disclaimer prose |
| 3 | `apartment.form.guest_link.lede` (2999), `guest_links.lede` (3327) | One line, and only once | AI-sounding, duplicated |
| 4 | `apartment.form.calendars.lede` (2970), rendered twice (apartment_form.html:28, :464) | Shorten, render once | |
| 5 | `automation.timing_help` (2907) | Shorten | Long explanation of 3 options already labelled |
| 6 | `dashboard.reporting_modes_body` (452), `dashboard.minutes_saved` (457) | Delete | Unused |
| 7 | UbyPort field hints (3085 to 3099, 7 strings for 5 fields) | Merge to one hint per field | Overlap |
| 8 | `guest.admin.resend.help` (3153) | Shorten | |
| 9 | Retention notes (1408, 1431, 3532) | Keep one | Same message three times |
| 10 | `onboarding.welcome_lede` (221), `safe_title`/`safe_body` (237-238), `finish_lede` (248) | Cut or shorten | Reassurance copy inside the app |
| 11 | `celebration.title/body` (458-459), a modal in base.html:209 | Replace with a small non-blocking notice, or delete | A modal interrupts work |
| 12 | Page ledes: `apartments.lede` (1366), `apartment.form.lede` (3024), `stays.lede` (1087), `automation.lede` (2903) | Cut | Taglines; the page title is enough |
| 13 | `guest_links.message_lede` (3335), shown on two pages | Keep one | Duplicate |
| 14 | `apartment.form.internal_name.hint` (3022), `passport_policy.hint` (3016), `guest_message.hint` (3012) | Shorten | |
| 15 | `demo.load_detail` (310) | Shorten | Lists every feature |
| 16 | `host.signature_help` (397), `host.verify_in_person` (405) | Drop statute numbers from the hints | They belong in the guide |

Effort: M overall, about 1.5 days including Czech copy and test updates. Many tests assert exact strings, so expect to update about 10 to 20 tests [ESTIMATE].

Two rules for later:

- One explanation lives in one place. Pages link to the guide instead of repeating it.
- No sentence that the button label already says.

Risk: removing guest legal text. Every item marked Keep stays, and the GDPR Art. 13 notice and the acknowledgement are untouched.

### F. Human-readable property names in all communication

What is a "name" in the data (`db.py:66-109`):

- `internal_name` is the host's own name. The form hint says it is shown to guests: "use the name you list on Airbnb".
- `uby_name` is the facility name registered with the police (max 35 characters).
- `uby_mark` is the 5-letter police abbreviation.
- `uby_idub` is the 12 to 14 digit police facility ID.

No field holds "č1". That is most likely what a host typed as `uby_name`, the police-register name [ASSUMPTION].

The bug: every guest e-mail uses `mail_notify.property_label()` (`mail_notify.py:1006-1014`). It returns `uby_name` first and falls back to `internal_name`. The guest pages do the opposite (`routes/guest.py:618-628`, `internal_name` first). So a guest sees "Downtown Comfort..." on the page and "č1" in the e-mail.

| Message | To | Name used today | Change |
|---|---|---|---|
| claim (link to confirm the stay), `claim.py:368` | Guest | uby_name, else internal_name | Use internal_name |
| claim_resend | Guest | Same | Same |
| reminder_guest (`claim.py:696`) | Guest | Same | Same |
| completion ("you're registered") | Guest | Same | Same |
| invoice_issued (`routes/invoices.py:495`) | Invoice buyer | Legal entity name; subject "Invoice %s" only | Add the property name to the subject and body when the invoice has a stay |
| reminder_host (`claim.py:767`) | Host | internal_name | None |
| submission_problem (`mail_notify.py:819`) | Host | internal_name | None |
| cancelled_with_guests (`mail_notify.py:902-930`, new in PR 230) | Host | Not in subject or body | Add the property name to subject and body (already in the PR 230 fix brief, item 5) |
| workspace_deletion | Account owner | Account level | None |
| Sign-up or registration confirmation | Not applicable | Does not exist: accounts are created by an admin (`routes/admin_accounts.py:468`) | None |
| SMS | Not applicable | Not implemented anywhere | None |

Fix:

- Change `property_label()` to prefer `internal_name`, so guest pages and mail agree.
- Add one test per mail kind asserting that the subject contains `internal_name` and never `uby_name` when the two differ.
- Effort: S (half a day).
- Risk: none for filing. `uby_name` is still what goes to UbyPort.

## 4. Workstream 1. Admin privileges

### 4.1 What exists today

- **Accounts:**
  - One `user_account` table with `role IN ('admin','host')` (`db.py:31`).
  - Accounts are created only by an admin (`POST /admin/users`, `routes/admin_accounts.py:468`). There is no self sign-up.
  - A first admin is bootstrapped on start (`auth.py:454`).
- **Sessions:**
  - Signed cookie carrying `session_version`, which is bumped to sign out everywhere (T42 in PR 230).
  - Two-factor login (TOTP) is mandatory for every account in production (`auth.py:350`).
- **Tenancy:**
  - Every host object is reached through `apartment.owner_user_id` (`access.py`).
  - An admin is a normal workspace owner plus admin routes. An admin does not see other workspaces unless impersonating.
- **Admin capabilities that exist:**

  | Capability | Route | File |
  |---|---|---|
  | List and create users | `/admin/users` | `routes/admin_accounts.py:450, 468` |
  | Reset password | `/admin/users/{id}/password` | `routes/admin_accounts.py:501` |
  | Impersonate a workspace, and stop | `/admin/users/{id}/impersonate` | `routes/admin_accounts.py:523, 573` |
  | Enable or disable an account | `/admin/users/{id}/toggle` | `routes/admin_accounts.py:545` |
  | Export a workspace as ZIP | `/admin/users/{id}/export` | `routes/admin_accounts.py:660` |
  | Schedule deletion | `/admin/users/{id}/schedule-deletion` | `routes/admin_accounts.py:684` |
  | Security incident register | `/admin/incidents` | `routes/admin_accounts.py:584-631`, `incidents.py` |

- **Audit:**
  - `db.audit` records `actor`, `actor_user_id` and `impersonator_user_id` on every row (`db.py:956-980`).
  - Impersonation start and stop are logged.
  - Reads of guest data are not logged, except passport photo views (`passport_photo_viewed`).
- **The gap:** impersonation gives the admin the host's full view, including document numbers, signatures and passport photos. It asks for no reason and has no time limit.

### 4.2 Capability decisions

| Capability | What it does | Why you need it | How often | Risk if it exists | Risk if missing | Decision |
|---|---|---|---|---|---|---|
| Users and accounts | Create, disable, reset, delete | No self sign-up, so you onboard every host | Weekly | Low, already exists | Cannot onboard | Keep |
| Impersonation | See the host's screens to support them | Support without screen-sharing | Weekly at first | HIGH: full guest data access | Slow support | Keep, and harden (below) |
| Resolve failed filings | See every workspace's failed, rejected and outcome-unknown stays | You will be asked "why didn't it file" | Daily glance | Medium | You learn from angry hosts | Add, as part of the Operations page, read-only, no guest identity |
| iCal sync health | Feeds in error or suspect, last sync per feed | Silent sync failure means missed filings | Daily glance | Low | Same | Add, on the Operations page |
| Job and mail health | Last success per scheduler job, failed mails | Detects a dead scheduler | Daily glance | Low | Same | Add, on the Operations page. Data exists in `settings`, `alert` and `email_outbox`. |
| Funnel and usage per host | Stage, last activity, counts | Sales follow-up and churn (Workstream 2) | Weekly | Low if counts only | Flying blind | Add (Workstream 2) |
| Subscription and billing | Plan, paid state | Only if you charge in-app | Not applicable | | | Do not build. There is no billing code (`payments.py:1-5` says UbyHost never processes a payment). Invoice hosts outside the app. |
| Feature flags | Toggle features per host | Rarely needed by a solo founder | Rare | Config sprawl | None | Do not build. Use environment variables. |
| Audit log viewer | Search audit rows across workspaces | Incident response | Rare | Low | Use SQL over SSH | Do not build now. Add later as a read-only filtered list. |
| GDPR requests | Data-subject request register | Legal duty of the host; you are the processor | Rare | Already exists per workspace (`data_subject_request`, `dsr.py`) | | Keep as is. No admin version. |
| System health, errors | Error rates, logs | Know when it breaks | Daily | | | Do not build. Use an external uptime check plus log alerts (Workstream 3, item 8). |
| Database console | Raw SQL | Emergencies | Rare | HIGH | | Keep outside the app (SSH plus `sqlite3`). Never as a web page. |

### 4.3 Security design for what stays

1. **Identity:**
   - Admin stays a role on `user_account`, with TOTP mandatory (already true in production).
   - Use a dedicated admin account that owns no workspace data. Your own test properties live in a separate host account. This avoids mixing your hosting data with admin power.
2. **Separation:** admin routes already check `role == 'admin'` (`_require_admin`, `routes/admin_accounts.py:440`). Keep all admin routes under `/admin/` so one review covers them.
3. **Impersonation hardening (HIGH risk, touches guest data):**
   - Starting impersonation requires a reason (free text, kept in the audit detail).
   - The session expires after 60 minutes of impersonation.
   - Keep the existing impersonation bar (`templates/base.html:120-128`), which shows the workspace and an Exit button.
   - While impersonating, the following are masked by default:
     - guest document numbers, visa numbers, signatures and passport photos;
     - the guest register PDF and CSV exports;
     - the workspace ZIP.
   - "Reveal" on one guest asks for a reason and writes `guest_identity_revealed` to the audit log with the guest id.
   - Default rule: the admin cannot see passport or ID data without a logged, justified reveal.
   - Implementation: one helper, `access.identity_visible(request)`, which returns False when `session_payload['as']` is set. It is used in the guest detail route, the photo route and the export routes.
4. **Audit:** already records the impersonator on every write. Add: an audit row for every admin page view under `/admin/`, and for every reveal.
5. **Host transparency:**
   - What exists: the host's Settings audit list already shows actions done "as admin X" (`routes/admin.py:2495-2498`, `settings.html:192`), and `impersonation_started` is written to the host's workspace.
   - What to add: write `impersonation_stopped` to the host's workspace too (today it goes to the admin's own, `routes/admin_accounts.py:580`); include the reason; add a filter for support sessions.

### 4.4 Scope and effort

| Item | Scope | Effort |
|---|---|---|
| Impersonation reason, 60-minute expiry, stop row in the host's audit | v1, before go-live | S |
| Masking guest identity while impersonating, plus logged reveal (HIGH risk) | v1, before go-live | M (1 to 1.5 days, with tests on every guest-data route) |
| Operations page: failed and outcome-unknown filings, feeds in error, job last-success, failed mail. Counts and links only, no guest names. | v1 | M (1 day) |
| Funnel page (Workstream 2) | v1.1 | M (1 to 2 days) |
| Audit log viewer | Later | S |
| Billing, feature flags, error console | Do not build | 0 |

## 5. Workstream 2. Analytics, CRM and funnel

### 5.1 Inventory

| Surface | In repo | Route or file |
|---|---|---|
| Landing (signed out) | Yes | `/` renders `landing.html` (`routes/admin.py:204-210`); about 830 EN words |
| How it works | Yes | `/jak-to-funguje` (`routes/legal.py:18`) |
| Pricing | Yes | `/cenik` (`routes/legal.py:28`). There are no prices on the page; the CTA is `mailto:support@ubyhost.com` (`templates/pricing.html:66, 86`). |
| Public guides | Yes | `/pruvodce/{slug}`, 2 guides (`public_guides.py`) |
| Legal pages | Yes | `/legal`, `/terms`, `/privacy`, `/dpa`, `/subprocessors` |
| Login | Yes | `/login`. The landing CTA goes here (`landing.html:71`). |
| Sign-up | No | Does not exist. Accounts are admin-created. |
| Onboarding | Yes | Five steps derived live from counts (`onboarding.py:53-125`); only a dismissed flag is stored |
| Separate marketing site | No | [ASSUMPTION] none outside this repo |
| Guest pages | Yes | `/l/{token}...` (section 1). These must never be tracked. |

Tracking today: none. There is no analytics script in any template, and the CSP allows scripts only from self and Cloudflare Turnstile (`main.py:143-147`). The cookie inventory lists only strictly necessary cookies (`cookie_inventory.py`). That is a strong position: today the site needs no consent banner. Keep it.

### 5.2 Funnel

There is no self sign-up, so the funnel has a manual step in the middle. Every stage after "account created" can already be read from the database. No new tracking is needed for them.

| # | Stage | Marking event | Where it is detected today |
|---|---|---|---|
| 1 | Visit | Page view on the marketing pages | Not detected. Needs web analytics. |
| 2 | Intent | Click on the pricing `mailto`, or a visit to `/login` from the landing page | Not detected. Needs web analytics (outbound and mailto click). |
| 3 | Lead | E-mail received at support@ | Outside the app (inbox). Record it in the CRM (5.5). |
| 4 | Account created | `user_account.created_at`, audit `user_created` | DB |
| 5 | Activated login | First `last_login_at`, and `legal_acceptance.accepted_at` | DB |
| 6 | Set up | First `legal_entity` and `apartment.created_at` for the owner | DB |
| 7 | Calendar connected | First `ical_feed.created_at` with `last_status` ok | DB |
| 8 | First guest done | First `reservation.registration_completed_at` | DB |
| 9 | First filing | First `submission.state IN ('ok','ok_duplicate','partial')` | DB |
| 10 | Paying | Not in the app. There is no billing. | Your invoicing, outside the app |
| 11 | Retained | Filings in each of the last 2 months | DB |

### 5.3 Minimal event set

Marketing pages (Plausible):

| Event | Trigger | Properties | Personal data |
|---|---|---|---|
| pageview | Automatic, on `/`, `/jak-to-funguje`, `/cenik`, `/pruvodce/*`, legal pages | path, referrer, UTM, country, device class (computed by the tool) | No. Plausible keeps no IP and sets no cookie. |
| contact_click | Click on any `mailto:` link | page | No |
| login_click | Click on a landing CTA to `/login` | page | No |
| guide_read | Scroll past 75% on `/pruvodce/*` | slug | No |

In-app product events: none sent to any third party. Stages 4 to 11 are SQL over existing tables, run when the admin funnel page loads. That costs no extra writes and no new script.

Deliberately not tracked:

- anything on `/l/*` (guest pages);
- `/reservations/*`, `/housebook`, guest forms, invoices or stay fees;
- any URL containing a token, id or e-mail;
- form field values;
- session replay anywhere;
- heatmaps.

Hard rule for the code: the analytics script tag lives only in `public_legal_base.html` and `landing.html`. A test fails if `guest/base.html`, `base.html` or `auth_base.html` contain the analytics host.

### 5.4 Tool decision

| | GA4 | PostHog Cloud EU | Umami Cloud | Plausible |
|---|---|---|---|---|
| Consent in CZ | Required. GA4 sets cookies, and Czech law needs opt-in for non-essential cookies (ÚOOÚ, since 1 Jan 2022). A banner is needed. | Default mode sets cookies, so a banner is needed. The cookieless option exists but needs server hash mode enabled. | Cookieless. Most use it without a banner. | Cookieless and no IP stored. Most use it without a banner. |
| Legal residue | US company; no EU-only storage; earlier DPA rulings (Austria, France) against GA before the 2023 EU-US framework | EU cloud (Frankfurt), DPA available | EU servers, DPA [ASSUMPTION] | EU company, data in Germany, DPA |
| Product funnels | Yes | Best in class | Basic funnels | Funnels on the Business plan only |
| Person-level identity for CRM | Weak | Yes, person profiles | No | No |
| Session replay, feature flags | No | Yes | No | No |
| Script weight (measured, gzipped) | About 50 KB or more [ASSUMPTION] | About 97 KB (`array.js`, 311 KB raw) | About 2.3 KB | About 1.3 KB |
| Effort, solo founder | Banner, consent mode, CSP | Banner or cookieless config, plus discipline to avoid autocapture on sensitive pages | Script tag | Script tag |
| Cost small / growth | Free / free | Free up to 1M events per month, then about $0.00005 per event | Free Hobby (100k events) / $20 per month Pro [ASSUMPTION: from third-party listings] | $9 / $19 per month (Business, needed for funnels) |
| Data ownership, export | Google | Good (export, warehouse) | Good | Good (API, CSV) |
| Send to CRM | Weak | Yes (webhooks, destinations) | Limited | Limited |

Recommendation: Plausible, on the marketing pages only. Product funnels come from the app's own database.

- **Smallest page cost:** about 1.3 KB, one request, no cookies.
- **Least legal work:** no stored IP, EU company, data in Germany. [Lawyer to confirm, see 5.6] whether Czech law needs consent for it.
- **The rest is already covered:** a product funnel tool is not needed. Every product stage already exists as a database row, so PostHog would mainly re-collect data you already own, over a 97 KB script, with personal-data risk next to passport pages.

Fallback: Umami Cloud in the EU region. Free at this size, about 2.3 KB, and it has funnels. Choose it if you want funnels on the marketing site without paying for Plausible Business.

Change the answer when:

- You add self sign-up, so the gap between "visit" and "account" becomes a product flow you need to measure step by step. Switch to PostHog Cloud EU, in cookieless mode, on the public pages and sign-up only.
- You run paid ads that need conversion import into Google or Meta. Then you need GA4 or a pixel, and a consent banner. Accept the banner only then.
- You have more than about 50 active hosts and want in-app feature flags or experiments. Then PostHog, server-side only, with no browser SDK on host pages.

### 5.5 CRM and lifecycle e-mail

Do not build a CRM inside the app. Do not adopt PostHog person profiles as a CRM.

- **Lead list, lead source:** a free external CRM, or a simple spreadsheet, until there are about 30 leads. Pre-account leads arrive by e-mail at support@, so a CRM that reads your inbox fits. Any free tier works.
- **Funnel stage and last activity per host:** the admin funnel page (Workstream 1). One row per host: created, stage reached with its date, properties, feeds, stays this month, filings this month, last login, last filing. Add a CSV export so it can be pasted into the CRM. This is the single source of truth for activated hosts.
- **Lifecycle e-mails:** use the app's existing outbox and SES sender (`mail.py`, SES in `eu-central-1`, `config.py:192`). Add three service e-mails triggered by stage, checked once a day by the existing mail job:
  - no property 3 days after the first login;
  - no calendar 3 days after the property was added;
  - no guest completed 14 days after the calendar was connected.
  - These are service messages to existing customers, not marketing. [Lawyer to confirm the legal basis and opt-out wording under Czech Act 480/2004.]
  - Effort: M (1 day).
- **Do not build now:** newsletters, a marketing automation tool, lead scoring, in-app chat, person-level web analytics.

### 5.6 Privacy and legal

- **Consent:**
  - Plausible sets no cookies and stores no IP. Under Czech law the opt-in rule is about storing or reading information on the device (ÚOOÚ).
  - EDPB Guidelines 2/2023 say Art. 5(3) can also cover tracking pixels and JavaScript-built requests, even without cookies. No explicit ÚOOÚ statement exempting cookieless analytics was found.
  - [Lawyer to confirm] that Plausible without a banner is acceptable in Czechia. If the answer is no, use Plausible's server-side Events API from the app's own pages. Nothing then runs in the browser, so no device access happens.
- **Privacy policy:** add Plausible as a processor for the marketing pages (`/subprocessors`, `/privacy`). State that guest and host app pages are not measured.
- **DPA:** sign Plausible's DPA.
- **Data location:** Germany (Plausible).
- **Retention:** set Plausible data retention to the minimum you need, for example 24 months [lawyer to confirm].
- **IP:** none stored by the tool. Cloudflare and Caddy see IPs, as today.
- **CSP:** add the Plausible host to `script-src` and `connect-src` on the public layout only. Pass a per-template CSP flag so host and guest pages keep the current strict policy.

### 5.7 Implementation outline

1. `templates/public_legal_base.html` and `templates/landing.html`: one deferred Plausible script tag, with outbound-link tracking for the `mailto` clicks (use the exact snippet from the Plausible site settings), rendered only when `config.PLAUSIBLE_DOMAIN` is set. Set it only in production.
2. `main.py`: a CSP variant for public pages that adds the Plausible origin.
3. A test asserts that the analytics host appears in no other template.
4. Admin funnel page: `routes/admin_accounts.py`, plus one SQL query per stage that groups by owner. It runs on demand, about 10 indexed queries.
5. Page weight added: about 1.3 KB on marketing pages, 0 on app and guest pages. Effort: S for the script, M for the funnel page.

## 6. Workstream 3. Infrastructure: Lambda + Turso + S3, challenged

### 6.1 Current state (from the code)

| Area | Today | Source |
|---|---|---|
| Hosting | One AWS Lightsail VM, Docker Compose, one app container with `mem_limit: 768m`. Plan size and region [ASSUMPTION]; the memory limit suggests the 1 GB bundle. | repo root `deploy/lightsail/docker-compose.yml` |
| TLS and proxy | Caddy, `encode gzip`. There is an optional Cloudflare front (`Caddyfile.cloudflare`). | `deploy/lightsail/caddy/` |
| Runtime | Python, FastAPI and Starlette, Jinja2. One uvicorn worker. | repo root `Dockerfile:39` |
| Database | SQLite file in the `/data` volume. WAL mode, foreign keys on, `secure_delete`. A new connection is opened for every query (`db.connect()`), and each one runs 3 PRAGMAs. | `db.py:578-591`, `842-861` |
| Files | Passport photos are Fernet-encrypted files in `/data/passport_photos`, deleted after verification or 30 days. These PDFs live inside SQLite: invoice PDFs (`invoice.pdf_blob`), stay-fee PDF and CSV (`stay_fee_filing.pdf_enc`, `csv_enc`), Doručenka (`submission.receipt_pdf`, TEXT). | `passport_photos.py:20,117`, `db.py:218,386,478` |
| Scheduled jobs | APScheduler inside the web process, guarded by a single-instance file lock. Jobs: iCal sync every 60 min, submit sweep every 10 min, deadlines every 30 min, mail every 5 min, photo sweep every 12 h, retention daily at 03:30. | `scheduler.py:185-216` |
| Auth | Signed session cookie with `session_version`. PBKDF2-SHA256 passwords. TOTP mandatory in production. CSRF tokens. Turnstile on login and the guest PIN. | `auth.py`, `security.py` |
| Field encryption | Fernet. The key is SHA-256 of the same secret that signs sessions (`UBYHOST_SECRET_KEY` or a key file). Encrypted: document number, visa number, signatures, host reason, UbyPort password, TOTP secret, stay-fee PDF and CSV. Plain text: guest names, birth date, address, nationality, the UbyPort request XML (90 days). | `db.py:989-1031`, `config.py:70` |
| Secrets | `.env` on the server plus the key file in `/data`. The nightly backup archives the DB and secrets together, encrypted with age. | `deploy/lightsail/scripts/backup.sh:2` |
| Backups | Nightly, age-encrypted, local retention 30 days. Off-site copy scripts (S3 or Google Drive) are manual to set up. RPO is up to 24 h. | `deploy/lightsail/scripts/` |
| Mail | Amazon SES in `eu-central-1`, with an outbox table and retries | `mail.py`, `config.py:192` |
| Deploy | GitHub Actions over SSH, with preflight checks | `.github/workflows/` |

### 6.2 Fit: is Lambda + Turso + S3 right for this app?

No, not now and probably not at 1,000 hosts either.

| Factor | Lambda + Turso + S3 | One container + local SQLite + Litestream + S3 (recommended) |
|---|---|---|
| Latency of a host page | Every query becomes a network round trip. Measured: dashboard 73 queries, stays list 67, stay page 23, guest pick page 10. Turso has no Frankfurt region (EU is Dublin and Stockholm only). With Lambda in Frankfurt at about 20 to 25 ms per round trip [ASSUMPTION], the dashboard spends about 1.5 to 1.8 s waiting on the database. With Lambda in Dublin next to Turso, it is still about 73 to 150 ms [ESTIMATE at 1 to 2 ms]. | Measured: 0.19 ms per query on a new connection, under 0.001 ms on a reused one. Dashboard 60 ms in total in the sandbox. |
| Writes | Still a single writer. Commits are delayed for durability by up to 100 ms (Free), 50 ms (Developer) or 25 ms (Scaler). Interactive transactions must finish within 5 s. Concurrent writes (`BEGIN CONCURRENT`) are an early preview, not GA. | Single writer, about 1 ms per commit measured. Capacity of hundreds of commits per second. |
| Timeouts | API Gateway HTTP API: 30 s, cannot be raised. A UbyPort call can take up to 60 s (`ubyport/client.py:93`), and immediate mode sends during the guest's save (A75). It needs a Function URL or a queue. | No limit beyond the proxy. |
| Cold starts | Python plus reportlab, cryptography, icalendar and Pillow. Expect about 1 to 2 s [ASSUMPTION] on the first guest of a quiet period. Provisioned concurrency removes this, but costs money. | None |
| Statefulness to remove | The in-process scheduler and its file lock; passport photo files; the secret key file; PDF generation into temp files; FileResponse streaming of ZIPs (up to 100 PDFs, memory-heavy). | None |
| Vendor risk | Turso announced on 2 October 2026 that it is joining Supabase. The service continues, but the roadmap is now uncertain. | Litestream and SQLite are open source; S3 is commodity. |
| Cost at 100 hosts [ESTIMATE] | About $8 to $15 per month (section 6.11) | About $13 to $25 per month |
| Solo-founder burden | IAM, API Gateway or Function URLs, EventBridge, SQS, DLQs, CloudWatch, Turso tokens, a deploy tool, local emulation. Many moving parts, each with its own failure mode. | One VM, one compose file, one volume, the deploy you already have |
| Availability | Multi-AZ compute; the DB is a remote dependency | One VM: a VM failure means downtime until it is restored. Mitigate with Litestream (data) and a restore runbook (compute). |

Recommendation: keep the always-on container. Do these four things, in order:

1. Run the scheduler as its own process: a second compose service from the same image, `UBYHOST_ROLE=worker`.
2. Run 2 to 4 uvicorn web workers. The existing scheduler lock already prevents double scheduling, and WAL allows parallel readers.
3. Add Litestream continuous replication of the SQLite file to a private S3 bucket in `eu-central-1`. RPO goes from up to 24 h to seconds. Keep the nightly age backups as a second, independent copy.
4. Later (section 6.6), move file blobs to S3 behind a storage interface.

Conditions that would change this answer:

- You need zero-downtime availability or more than one server. Then move to two containers plus Postgres (RDS or Neon in Frankfurt), not Turso.
- Traffic becomes very spiky with long idle periods and cost matters more than latency. Unlikely for a B2B tool with hourly jobs.
- Turso ships concurrent writes as GA with a Frankfurt region, and you have already removed the N+1 query patterns. Even then, the benefit over local SQLite is mainly managed backups.

### 6.3 If you still go serverless: what must change in the code

This is the full list, so the decision is informed. Effort in total: L, about 3 to 5 weeks [ESTIMATE].

1. **Compute:**
   - Wrap the ASGI app with an adapter (the Mangum package, or the AWS Lambda Web Adapter layer, which needs no code change).
   - Use a Function URL, not API Gateway, for the 30 s limit, or move every UbyPort call out of the request path.
   - Use arm64 and 512 to 1,024 MB of memory.
   - Bundle size: drop dev-only files. reportlab, cryptography and Pillow stay.
2. **Statelessness:**
   - Remove the file-based single-instance lock (`scheduler.py`).
   - Remove the key file fallback (`config.py`).
   - Move passport photos and all PDFs to S3.
   - Write temporary files only to `/tmp`, and stream ZIPs to S3, then return a presigned URL.
3. **Static assets:** serve `/static` from S3 plus CloudFront, which the always-free tier covers. Guest pages stay dynamic, because they are PIN-gated and per guest.
4. **Domain and TLS:** CloudFront with an ACM certificate in front of the Function URL, or keep Cloudflare in front.
5. **Background work:**
   - EventBridge Scheduler: one schedule per job, invoking a worker function.
   - The UbyPort send goes through SQS FIFO, with `MessageGroupId = apartment_id` (one in-flight batch per property, matching today's claim model) and a DLQ after 3 receives.
   - Idempotency stays in the database (`submission_claim`, the duplicate code 150), not in SQS.
   - HIGH risk: any change to how and when batches are claimed and sent. It must keep "never file twice", which today depends on `BEGIN IMMEDIATE` claims (`reporting.py`).
6. **Database:**
   - Replace `sqlite3` with the `libsql` or `turso_serverless` client.
   - All 7 `with db.immediate()` blocks become interactive transactions over HTTP. Each must finish within 5 s, and each statement is a round trip.
   - Remove the per-query connect pattern; reuse one client per invocation.
   - The 3 PRAGMAs per connection go away, or become server settings.
   - Migrations: the current startup migration (`init_db`, `PRAGMA table_info`) must run as a separate deploy step, not on every cold start.
7. **Secrets:** SSM Parameter Store (standard tier is free). Use a separate KMS key for field encryption (section 6.5).
8. **Observability:** CloudWatch Logs (`$0.63/GB`), alarms on the DLQ depth, Lambda errors and the outcome-unknown count.
9. **Deploy:** SST or AWS SAM. Tests must run against a local libSQL server.

### 6.4 Background work, idempotency and alerting (applies to either platform)

- Keep sequential iCal sync. It is already sequential and hourly. "Sync now" exists (`routes/admin.py:1195`) for the host who needs it.
- The UbyPort send keeps the database claim as the only guard against double filing (`submission_claim`, `claim_sendable`), plus the duplicate code 150 as a backstop. Do not add a second idempotency mechanism in a queue. Two sources of truth is how double filings happen.
- Retry: the one automatic retry after a crash belongs in the scheduled sweep only, as already specified in the PR 230 fix brief (item 2). HIGH risk.
- Alerting today: alerts in the app, host e-mails (`submission_problem`), job-failed alerts (`scheduler.py:39`), a heartbeat ping after each successful submit sweep (`UBYHOST_HEARTBEAT_URL`, `config.py:123`, `scheduler.py:79-90`), and a backup ping. Missing: a heartbeat for iCal sync and the mail job. Add the same ping after those jobs, and set both URLs in production. Effort: S.

### 6.5 Guest and personal data

What should change, on any platform:

| Data | Today | Recommended |
|---|---|---|
| Document and visa number, signatures | Fernet, key derived from the session-signing secret | Separate data-encryption key, not the session secret. Rotating the session secret today would make every encrypted field unreadable (`db.py:989-998`). |
| Name, birth date, address, nationality | Plain text | Encrypt birth date and address. Keep names and nationality plain: they are needed for search and lists, and full-disk plus backup encryption covers them. [Decision for founder: searchable names vs encryption.] |
| UbyPort request XML (contains passport numbers) | Plain text, kept 90 days (A41) | Encrypt the column, or store only a hash plus the response code. |
| Stay-fee PDF and CSV | Encrypted | Keep |
| Invoice PDF | Plain BLOB | Fine (business document, not guest identity) |
| Passport photos | Encrypted files, deleted after verification or 30 days | Keep |

Key management:

- Container: one data key in the server `.env`, separate from `UBYHOST_SECRET_KEY`. Use MultiFernet, so that rotation means adding a new key and re-encrypting in the background. Effort: M.
- AWS later: envelope encryption with KMS. One customer-managed key ($1 per month); data keys are cached in memory. Only the app role can call `kms:Decrypt`; you, as the IAM user, cannot without a logged break-glass role.

Who can decrypt: only the app process. Admin access goes through the masking rule in 4.3.

Retention:

- Existing purges: house book, photos, request XML, the 10-year invoice purge, workspace deletion.
- Every period needs lawyer confirmation. Examples: 6 years for the house book is stated in the guest notice (`i18n.py:393`); invoices 10 years.

Logs never contain guest data:

- The access log is PII-free by design (`main.py` `_log_access`, `config.ACCESS_LOG`).
- Add a test that runs a guest save and greps the captured logs for the guest's surname and document number. Effort: S.

### 6.6 Files in S3

Do it when the database passes about 2 GB, or before any multi-server setup, whichever comes first. Doing it now buys little, because SQLite holds the blobs fine at this size.

- **Bucket:**
  - One private bucket per environment in `eu-central-1`.
  - Block Public Access on; SSE-KMS (or SSE-S3 for less cost and work); versioning on; a lifecycle rule that expires non-current versions after 30 days.
- **Keys, not URLs:** store `owner_user_id/kind/yyyy/uuid.pdf` in the database. Never store a URL.
- **Access:** the app checks ownership through `access.py` first, then returns a presigned GET URL valid for 60 s, or streams the file. Host isolation stays in the application layer, where it is today. The key prefix makes accidental cross-host access visible in review.
- **Upload:** only passport photos are user uploads. JPEG, PNG, WebP or PDF up to 15 MB are accepted, checked by magic bytes, and stored as-is, encrypted (`passport_photos.py:94-117`). The app never executes or renders them server-side; the host downloads them. Recommendation: re-encode images with Pillow (already a dependency) to strip metadata and any payload. Either reject PDFs, or accept them knowing the file goes only to the host's own browser. Antivirus is not worth running for this flow.
- **Interface:** `storage.put(kind, owner, bytes) -> key`, `storage.get(key)`, `storage.delete(key)`, with a local-disk backend for tests. Effort: M (2 days, plus migration of existing blobs).

### 6.7 Security and IAM (for the container plan)

- **Server:**
  - SSH key only.
  - An IAM user for the server with exactly: `s3:PutObject` and `s3:GetObject` on the Litestream prefix, and later the files bucket, and `ses:SendEmail`.
  - No other AWS rights on the box.
- **Secrets:** stay in the server `.env` (never in the repo; AGENTS.md already says so). Moving them to SSM adds work without real gain on one VM.
- **Rate limits:** login, PIN and claim are already rate limited, with Turnstile.
- **WAF:** not needed. Cloudflare in front (already supported) gives DDoS protection for free.
- **Dependencies:** keep the lockfile and the CI secrets scan.

### 6.8 Observability (go-live minimum)

| Need | How | Cost |
|---|---|---|
| Uptime | External check on `/healthz` every minute (any free uptime monitor) | Free |
| Jobs alive | Submit-sweep heartbeat exists (`UBYHOST_HEARTBEAT_URL`); add the same for iCal sync and mail | Free tier of a cron monitor |
| Failed filings, failed syncs | Already raised as alerts and e-mails. Add a daily digest e-mail to you (operator) with counts across workspaces. | S |
| Errors | Ship container logs to one place: Lightsail logs, or the Docker log driver to CloudWatch at `$0.63/GB`. Alert on more than N ERROR lines per 10 minutes. | Under $2 per month [ESTIMATE] |
| Backups | Litestream metrics, plus the existing backup ping | Free |

### 6.9 Deployment

Keep the current GitHub Actions to SSH to `docker compose` flow.

- Add a staging environment on a second small Lightsail instance ($7 per month), with `UBYPORT_ENV=mock`.
- Rollback: redeploy the previous image tag. Add image tags per commit if they are not there [ASSUMPTION].
- Infrastructure as code is not worth it for one VM. If you go to AWS serverless later, use AWS SAM: one YAML file, official, and fewer abstractions than SST or Terraform for a Python app.

### 6.10 Migration plan

No platform migration before go-live. Freezing the platform during launch is the lowest-risk path. A change of database client touches every one of about 450 SQL call sites.

| Step | When | Downtime | Rollback |
|---|---|---|---|
| 1. Litestream sidecar to S3, restore test | Before go-live | None | Remove the sidecar |
| 2. Scheduler as a separate service; 2 web workers | Before go-live | Seconds (container restart) | Revert compose |
| 3. One connection per request; fix N+1 on dashboard and stays list | After go-live, before 100 hosts | None | Revert commit |
| 4. Storage interface plus blobs to S3 (copy, verify checksums, switch reads, then delete blobs) | At about 2 GB database size | None (dual-read during the copy) | Read from the DB again |
| 5. Postgres, only if a trigger in 7.2 fires | At the trigger | About 15 to 30 min maintenance window: dump, load, verify counts per table, switch DSN | Point back at SQLite (kept read-only for a week) |

### 6.11 Cost [ESTIMATE, October 2026 list prices]

Scale assumptions [ASSUMPTION]:

- 10 hosts at launch, 100 at 10x, 1,000 at 100x.
- About 3 properties per host and 10 stays per property per month.
- About 300k requests per month at 100 hosts.

| | 10 hosts | 100 hosts | 1,000 hosts |
|---|---|---|---|
| Container: Lightsail VM | $7 (1 GB) to $12 (2 GB) | $12 to $24 (4 GB) | $24 to $48, or 2 VMs plus Postgres about $60 to $90 |
| Container: S3 (Litestream plus files), logs | Under $2 | About $2 to $4 | About $10 to $20 |
| Container: staging VM | $7 | $7 | $7 |
| Container total | About $14 to $21 | About $21 to $35 | About $41 to $117 |
| Serverless: Lambda (arm64, 512 MB, about 200 ms per request) | $0 (free tier) | About $0 to $1 | About $1 to $5 |
| Serverless: HTTP API (if used) | Under $0.50 | About $0.40 | About $4 |
| Serverless: Turso | $0 (Free, 100 ms commit delay) or $4.99 (Developer) | $4.99 | $24.92 (Scaler) or more |
| Serverless: KMS, S3, CloudFront, CloudWatch | About $2 to $4 | About $3 to $6 | About $15 to $30 |
| Serverless: provisioned concurrency to avoid cold starts on guest pages (optional) | About $5 to $10 [ESTIMATE] | Same | Same |
| Serverless total | About $3 to $20 | About $9 to $22 | About $45 to $75 |

Money does not decide this. Both are under $40 per month at 100 hosts. What decides it is latency (remote DB times 73 queries per page), the 30 s and 5 s limits, and the number of moving parts you have to run.

### 6.12 Interaction with the other workstreams

- **Admin:** the Operations and funnel pages read across workspaces. On SQLite they are cheap read-only queries that never block writers (WAL). On Turso each adds round trips; keep them aggregated in SQL.
- **Analytics:** Plausible is hosted, so nothing is self-hosted on your infrastructure. Do not self-host PostHog or Umami on the VM or on Lambda.
- **Funnel:** derived from the database, so it needs no new writes and no event pipeline.

## 7. Workstream 4. Performance, scaling and efficiency

The short answer to the core fear: SQLite will hold at 100 hosts with a very large margin, and very likely at 1,000. You will not have to rip it out for write throughput. You may want Postgres later for a different reason: running more than one server for availability. Make that move cheap now (7.2.6). Turso does not help with either problem.

### 7.1 iCal sync scheduling

Today:

- Hourly (`config.py:121`) and sequential: one loop over all active feeds (`icalsync.py:781-800`), in one job with `max_instances=1, coalesce=True` (`scheduler.py:194`).
- On-demand "Sync now" exists for a host, for that host's feeds (`routes/admin.py:1195`).
- Every run downloads and parses every feed and writes `last_sync_at` (`icalsync.py:776`), even when nothing changed. No conditional GET (ETag or If-Modified-Since) and no content hash check.
- Host count and feeds per host: [ASSUMPTION] unknown.

Costs at 100 hosts [ESTIMATE: 300 properties with about 2 feeds each, so 600 feeds]:

- 600 fetches per hour, 14,400 per day, about 432,000 per month, plus at least one database commit each.
- That is the largest single source of writes in the system: more than all guest activity, which is about 225,000 commits per month (7.2.2).

Sequential vs parallel:

- On a container, sequential costs nothing extra. The work is network-bound, so total CPU is the same either way.
- On Lambda, sequential inside one invocation avoids per-feed cold starts. But the money is immaterial: about 600 feeds times 0.5 s times 720 runs, at 512 MB, is about 108,000 GB-s per month. That is inside the free tier, or about $1.50 [ESTIMATE].
- Recommendation: keep sequential. Parallel only makes sense per host with many feeds, and only for "Sync now", where a person is waiting.

Latency to the host:

- A new booking appears up to 60 minutes later. The reporting deadline is 3 working days after arrival, so hourly is acceptable.
- Same-day bookings are the exception, and "Sync now" covers them.
- A 5-minute queue is not needed.

The real efficiency win is to skip unchanged feeds:

- Send `If-None-Match` and `If-Modified-Since` when the provider gave an ETag or Last-Modified. Whether Airbnb and Booking send them is [ASSUMPTION]; log it for a week to see.
- Store a SHA-256 of the body. When it is unchanged, skip parsing and write nothing except a cheap `last_checked_at` once per hour at most.
- Expected: most hourly fetches of a quiet calendar are unchanged, so this removes most sync parsing and writes [ESTIMATE: 70 to 90%].
- Effort: S.

### 7.2 SQLite and concurrency (critical)

#### 7.2.1 How concurrency works today

- WAL mode (`db.py:586`): readers never block the writer, and the writer never blocks readers.
- One writer at a time. Others wait up to 30 s (`timeout=30`, `db.py:579`) before "database is locked".
- 7 critical sections use `BEGIN IMMEDIATE` (`with db.immediate()`), for example the UbyPort claim, invoice numbering and workspace deletion. The other writes are autocommit statements.
- One uvicorn worker (`Dockerfile:39`). Blocking work runs in Starlette's thread pool, so writes from threads queue on SQLite's lock.
- The in-process scheduler shares that one process and its GIL. A long deadline scan or sync can slow page responses (a comment at `routes/admin.py:1203-1206` already notes this).
- Measured in the sandbox:

  | Operation | Time |
  |---|---|
  | Autocommit insert | 1.0 ms |
  | Query on a new connection | 0.19 ms |
  | Query on a reused connection | 0.0005 ms |
  | Dashboard, 18 stays | 60 ms total, 73 queries |

  Production disk fsync time is [ASSUMPTION]; 2 ms per commit is used below.

#### 7.2.2 Realistic write load at 100 hosts [ESTIMATE]

Assumptions: 3 properties per host, 10 stays per property per month, 2.5 guests per stay.

| Source | Monthly | How estimated |
|---|---|---|
| Guest flow: 7,500 guests a month, about 10 write requests each (PIN, claim, party, form steps, signature, submit), about 3 commits per request | About 225,000 | Request count from the routes in `routes/guest.py` |
| iCal sync: 600 feeds hourly, at least 1 commit each | About 432,000 | Section 7.1 |
| Filings: one batch per stay, about 5 commits | About 15,000 | `submit_batch` writes a submission row, guest rows and an audit row |
| Host activity: 100 hosts, about 30 write actions a day | About 90,000 | [ASSUMPTION] |
| Mail outbox, alerts, deadlines, rate-limit rows | About 50,000 | [ASSUMPTION] |
| Total | About 800,000 a month | |

This is about 0.3 commits per second on average, and about 1 per second in a busy hour (4x the average).

Worst realistic burst: you mail 100 guest links at once and they all open within a minute. Peak guest page loads are about 2 per second; PIN, claim and form saves follow over 5 to 10 minutes. That is about 5 to 10 commits per second for a few minutes, with "Sync now" from a host with 10 feeds on top.

#### 7.2.3 Simulated latency (single writer as an M/D/1 queue, commit service time s, arrival rate λ)

| Setup | s (per write transaction) | λ = 1 per second (busy hour) | λ = 10 per second (burst) | Comment |
|---|---|---|---|---|
| Local SQLite (today) | about 2 ms | Wait about 0 ms; p99 about 2 ms | Wait about 0.02 ms; p99 about 4 ms | Utilisation 2%. The DB adds nothing noticeable. |
| Turso, Lambda in the same region (Dublin), Developer plan | 4 statements x 2 ms + 50 ms durability delay = about 58 ms | p50 about 60 ms; p99 about 120 ms | Utilisation 58%; mean wait about 40 ms; p99 about 400 to 600 ms | [ASSUMPTION] the durability delay is inside the write lock |
| Turso, Lambda in Frankfurt to Dublin | 4 x 22 ms + 50 ms = about 138 ms | p50 about 140 ms; p99 about 300 ms | Utilisation over 100%: the queue grows without bound during the burst | Not acceptable |

Where the latency actually comes from today is CPU in one Python process, not the database:

- Dashboard about 60 ms; guest pick page about 11 ms (measured).
- If 100 guest requests arrived in the same second, one worker would serve them one after another: p50 about 0.6 s, p99 about 1.2 s [ESTIMATE at about 12 ms each].
- With 4 workers: p99 about 0.3 s.

When it feels broken:

- Navigation feels instant under about 100 ms and acceptable under about 1 s.
- A guest on a phone who waits 3 s or more for a form step is likely to give up.
- Host pages: aim for p99 under 1 s; guest steps: under 500 ms.

#### 7.2.4 Does Turso solve it?

No.

- A Turso database is still single-writer. `BEGIN CONCURRENT` (MVCC) is an early preview on Turso Cloud since 3 August 2026 and needs a special `tursodb` database type. It is not GA (source: Turso blog, concurrent writes).
- Every query becomes a network call. With this code's query patterns, that turns a 60 ms page into a 0.2 s to 1.8 s page, depending on region.
- It adds a commit delay of 25 to 100 ms depending on the plan.
- Turso announced on 2 October 2026 that it is joining Supabase (source: Turso blog).

#### 7.2.5 When to move to a multi-writer database

Move to Postgres (RDS or Neon in Frankfurt) when the first of these happens:

| Signal | Threshold | Why |
|---|---|---|
| You need a second app server (zero-downtime deploys, VM failover) | When downtime starts costing you customers. Likely somewhere between 300 and 1,000 paying hosts [ESTIMATE]. | SQLite cannot be shared safely between servers. This is the most likely trigger. |
| Write lock waits | p99 above 50 ms for a week, or any "database is locked" error | Measure as in 7.3.4 |
| Write utilisation | Sustained above 30% at peak (about 150 commits per second at 2 ms) | About 10,000+ hosts sustained, or about 2,000 hosts for burst patterns [ESTIMATE]. Far away. |
| Database size | Above about 50 GB after blobs move to S3 | Backup and restore time |

Do not set a calendar date. Set the metric alerts in 7.3.4 and decide when one fires. Plan Postgres, not Turso, as the target.

#### 7.2.6 Make the later Postgres move mechanical

The code is in a good position. All SQL goes through helpers in `db.py`; `sqlite3` is imported in only 3 files (`db.py`, `alerts.py`, `routes/stay_fees.py`); and about 450 call sites (`db.query`, `query_one`, `execute`, `insert`, `update*` plus `cur.execute`) are parameterised. The f-strings that exist only build placeholder lists (for example `reporting.py:1910-1915`). The SQLite-specific spots, counted in `App/app`:

| Pattern | Count | Postgres equivalent | When |
|---|---|---|---|
| `x IS ?` null-safe comparisons | 67 | `IS NOT DISTINCT FROM`, or plain `=` where the value is never NULL | Rewrite in a helper now (S) |
| `BEGIN IMMEDIATE` (`with db.immediate()`) | 7 | `BEGIN` + `SELECT ... FOR UPDATE`, or an advisory lock | At migration. Keep these blocks small now. |
| `INSERT OR IGNORE`, `INSERT OR REPLACE`, `ON CONFLICT` | 9 | `ON CONFLICT DO NOTHING` / `DO UPDATE` | Use the `ON CONFLICT` form now; both engines support it |
| Triggers with `RAISE(ABORT, ...)` | 6 | PL/pgSQL triggers | At migration |
| `PRAGMA` (WAL, foreign keys, `table_info` migrations) | 8 | Numbered SQL migration files | Move to numbered migration files now (M). This is also needed for a safe deploy on any platform. |
| `lastrowid` | 3 | `RETURNING id` | Now, in `db.insert` (S); SQLite 3.35+ supports `RETURNING` |
| `COLLATE NOCASE` | 1 | `citext`, or a unique index on `lower(username)` | At migration |
| `AUTOINCREMENT`, ISO TEXT timestamps, INTEGER booleans | Many | Identity columns; keep TEXT ISO or convert to `timestamptz` | At migration (script) |

Rules from now on:

- No new SQLite-only syntax.
- Transactions stay small and never wait on the network.
- No UbyPort call or feed fetch inside an open transaction. The claim model already does this right.
- Every query is parameterised.
- No logic relies on "only one writer exists".

Run the test suite against both engines in CI the month before a migration, not before.

Refactors that buy 2 to 3 times more headroom, in order:

1. One connection per request or thread, instead of per query.
2. Remove the N+1 queries on the dashboard and stays list.
3. A separate scheduler process.
4. 2 to 4 web workers.
5. Skip unchanged iCal feeds.

Items 1 and 2 cut host page time by about 20 to 50% (measured: about 14 of 60 ms is connection setup). Items 3 and 4 multiply CPU capacity. Item 5 removes most writes.

### 7.3 Ecological and efficiency review

Definition for this app:

- No work when nothing changed.
- One request per page where possible, plus cached static assets.
- No third-party scripts on app or guest pages.
- Database work proportional to what is on screen, not to history.
- An idle cost of one small VM.
- No background polling faster than the business needs (hourly feeds; 10-minute submit sweep).

#### 7.3.1 Findings

| # | Finding | Evidence | Fix | Effort | Expected gain |
|---|---|---|---|---|---|
| 1 | New SQLite connection plus 3 PRAGMAs for every query | `db.py:578-591`, `842-861`; measured 0.19 ms vs 0.0005 ms | One connection per request (contextvar), reused by the helpers | S to M | About 20 to 25% of host page time (14 of 60 ms on the dashboard) |
| 2 | N+1 queries | Dashboard 73 queries, stays list 67, for 18 stays (measured); `reporting.dashboard_rows` loads guests per stay (A51) | Load guests for all listed stays with one `IN (...)` query; compute progress from it | M | Query count from about 3 per stay to about 15 total; page time down further |
| 3 | Stay fees list: about 7 queries per property, guests decrypted twice | A50 in the review | One pass over guests per period | M | Proportional to properties |
| 4 | Every feed fully fetched, parsed and written hourly | `icalsync.py:776`, no conditional GET | ETag or Last-Modified plus a body hash; skip unchanged | S | Most sync CPU and writes [ESTIMATE 70 to 90%] |
| 5 | Static assets have no long cache header | Middleware sets `no-store` outside `/static` (`main.py:207-209`); `/static` gets only StaticFiles' ETag | `Cache-Control: public, max-age=31536000, immutable` for `/static`. URLs already carry `?v=` versions. | S | Removes revalidation requests: about 6 to 8 per page (`guest/base.html:13-15, 61-64`) |
| 6 | gzip only | `Caddyfile.*: encode gzip` | `encode zstd gzip` | S | About 10 to 20% smaller text transfer [ESTIMATE] |
| 7 | Background CPU in the web process | `scheduler.py` in-process; the deadline scan decodes signatures | Separate worker service | S | Steadier page latency |
| 8 | Guest pages load `signature.js` (29 KB raw) and `ticket.js` (23 KB) on every step | `guest/base.html:61-64` | Load `signature.js` only on the signature step | S | About 29 KB raw less on most guest pages |
| 9 | PDFs inside SQLite | `invoice.pdf_blob`, `stay_fee_filing.pdf_enc`, `submission.receipt_pdf` | Storage interface, then S3 (section 6.6) | M | Smaller database, faster backups. Invoice PDFs are already down from 197 to 74 KB (T131 to T134). |
| 10 | Indexes | 20 indexes, covering the main owner and parent keys | Run `EXPLAIN QUERY PLAN` on the 20 most frequent queries from the new per-request query log before adding any index. No full scan of a large table was found in this review, but none was measured either. | S | Unknown until measured |

Low-effort wins that cut 20% or more: 1, 4, 5 and 7, about 1.5 days together. Then 2 (1 day).

#### 7.3.2 If you do use Lambda

- arm64, 512 MB.
- One function for the web and one for the workers.
- One scheduled worker invocation every 10 minutes that runs all due jobs sequentially, instead of one schedule per job.
- No provisioned concurrency unless guest p99 shows cold starts over 1 s.
- Keep the log level at INFO and no request-body logging. Logs are the largest variable cost after compute.

#### 7.3.3 If you use Turso

Every finding above becomes more urgent. Items 1 and 2 decide whether pages take 0.1 s or 2 s.

#### 7.3.4 Monitoring without new cost

- Extend the existing access log line (`main.py` `_log_access`, already has `ms=`) with `q=` (queries per request), `db_ms=` (time in the database) and `lock_ms=` (time waiting for `BEGIN IMMEDIATE`). Count these with a contextvar in `db.py`. Effort: S.
- Log each job's run time and items processed: feeds, changed feeds, batches.
- A weekly script, or an admin Operations panel, reads the last 7 days of logs and prints:
  - p50 and p99 per route group (host, guest, public);
  - queries per request;
  - lock wait p99;
  - error rate;
  - sync changed ratio.
- "Environmental cost per transaction": use CPU-ms per request from these logs as the proxy. Do not build carbon accounting.
- Alert thresholds:
  - guest p99 over 500 ms;
  - host p99 over 1 s;
  - `lock_ms` p99 over 50 ms;
  - any "database is locked";
  - any job with no success for twice its interval.

### 7.4 Interaction with the other workstreams

- **Admin:** Operations and funnel pages are read-only aggregate queries. In WAL they never block a guest's write. Rules:
  - no admin query inside a write transaction;
  - `LIMIT` on lists;
  - no full decrypt of guests for counts (count columns, do not load rows).
- **Analytics:**
  - The Plausible script talks to Plausible's servers directly; nothing touches your database.
  - The funnel is computed on demand from existing rows, so it adds no writes, no event table and no queue.
  - If you later add server-side product events (for example to PostHog), send them from the outbox pattern you already use for mail: write a small row in the same transaction, and send asynchronously. Batch them, never inline in a request.
  - Downsampling is not needed at this volume. Funnel stages are low-frequency events (a few per host, ever).
- **Tool choice:** Plausible does not affect the architecture or the scaling timeline.

## 8. Workstream 5. Custom guest form URLs

### 8.1 What exists

- One permanent link per property: `/l/{token}`. The token is 20 random characters, about 101 bits (`auth.py:506-509`).
- The guest picks their stay on that page (stays arriving between today and today plus `permalink_window_days`, default 2, set per property; `routes/guest.py:416-430`), then claims it by e-mail.
- Every page is behind a 6-digit PIN: rate limited, with Turnstile after 3 failures (`routes/guest.py:796-815`).
- The token is a secret. The PIN is the second factor.
- Before the PIN, a visitor sees the PIN page with the property name and the host card (`guest/base.html:22-25, 43`), which shows the host's contact.

### 8.2 Slug design

A readable slug turns the first factor into something guessable. With the PIN still required, guessing a slug reveals only that the property exists, its name and the host card, never guest data. That is a small leak, but it is a leak of host contact details linked to an address-like name.

Proposed scheme:

- **Format:** `/l/{slug}-{code}`. For example `/l/vinohrady-studio-k7m2qx`.
- **Slug:** from `internal_name`, accents folded (č to c), lower case, a to z, 0 to 9 and hyphens only. At most 40 characters, cut at a word boundary.
- **Code:** 6 random characters from the existing 33-character alphabet, about 30 bits. That makes enumeration impractical, and the PIN still guards the data.
- **Case:** lower case in links; matching is case-insensitive.
- **Collisions:** global uniqueness comes from the code. Two hosts can both have "garden-apartment".
- **Who sets it:** generated when the property is created. The host can edit the readable part in property settings; the code is never edited.
- **Renames:** allowed. Every old slug keeps redirecting to the current one, forever. Old links in Airbnb messages, bookmarks and printed cards keep working. Nothing breaks.
- **The old `/l/{token}`:** keeps working forever, as an alias. It costs nothing and removes all migration risk.

Pure memorable slugs without a code (`/l/my-beachhouse`) are possible, but not recommended for a page that leads to passport entry. If you want them anyway, show nothing but the PIN box before the PIN: hide the host card and the property name. That is a small change in `guest/base.html` and the shared guest context.

### 8.3 Schema

```sql
CREATE TABLE IF NOT EXISTS apartment_slug (
    slug          TEXT PRIMARY KEY,          -- full "vinohrady-studio-k7m2qx", lower case
    apartment_id  INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    is_current    INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_slug_current
    ON apartment_slug (apartment_id) WHERE is_current = 1;
```

- Lookup is one primary-key read.
- History is kept by setting `is_current = 0`; old rows redirect to the current row.
- On workspace deletion, the rows are removed through the `apartment` cascade.

### 8.4 Routing

- `GET /l/{key}`: if `key` matches an `apartment.permalink_token`, behave as today. Else look up `apartment_slug`; if it is not current, return 301 to the current slug. Else return 404.
- All existing sub-routes (`/l/{key}/{reservation_id}`, `/claim`, `/party` and so on) resolve `key` the same way. One resolver function in `routes/guest.py`.
- Today `pin_fingerprint` HMACs the token with the PIN (`auth.py:540-551`), the PIN cookie stores the token (`auth.py:575`) and the lockout key uses the token (`routes/guest.py:806`). All three must be keyed by the apartment id (or by its permanent token, resolved from the slug). Otherwise a guest switching between the old and new URL is asked for the PIN again, and the lockout could be dodged by switching URLs.
- The links the host copies from Guest links and the stay page change to the slug form.

### 8.5 Value vs cost

- Guests reach the link from a host's message on Airbnb or Booking, or by e-mail, and they tap it. A readable link improves trust slightly ("this is really my apartment") and helps a host who reads a link out loud or prints it.
- There is no evidence in the code or the funnel that link sharing is a drop-off point, and you cannot measure share rate without tracking guest pages, which you should not do.
- Value: low to modest. Cost: about 2 to 3 days. Risk: medium, because every guest route changes.

| Item | Effort |
|---|---|
| Schema and migration (generate a slug for every existing property) | S |
| Slug generation and validation (accent folding, length, reserved words such as `pin` and `claim`) | S |
| URL resolver and redirects for all guest routes | M |
| Settings UI (edit the readable part, preview, copy) | S |
| Copy-link places use the slug | S |
| Testing and QA, including the guest browser e2e at 360 and 390 px, old-link regression and PIN cookie continuity | M |

Ship nothing of this before go-live. After go-live, ship all of it in one change: the slug without routing is useless, and routing without the UI is invisible.

## 9. Phased plan

### 9.1 Before go-live (about 6 to 8 working days)

| # | Item | Effort | Cost per month |
|---|---|---|---|
| 1 | Finish the PR 230 fixes (retry safety, date trim, ZIP stay fees, e-mail kind, test cleanup) and merge. HIGH risk: filing. | Already specified | 0 |
| 2 | Part 1: deadline shows "Reported 12.05." and late or on time | S | 0 |
| 3 | F: `property_label()` uses `internal_name`, with tests per mail kind | S | 0 |
| 4 | D: guide second pass (retry, deletion, date changes, deadline wording) | S | 0 |
| 5 | Admin v1: impersonation reason, 60-minute expiry and host-visible list; masking of guest identity with logged reveal. HIGH risk: guest data. | M | 0 |
| 6 | Litestream to S3 plus a tested restore | S | About $1 |
| 7 | Scheduler as a separate service; 2 web workers | S | 0 |
| 8 | Set `UBYHOST_HEARTBEAT_URL`; add heartbeats for iCal sync and mail; external uptime check | S | 0 |
| 9 | Static `immutable` cache header; `encode zstd gzip` | S | 0 |
| 10 | Plausible on public pages only, with a test that it appears nowhere else. CSP split. Lawyer check on consent. | S | $9 |

### 9.2 After go-live, before 100 hosts (about 8 to 10 working days)

| # | Item | Effort | Cost per month |
|---|---|---|---|
| 1 | Admin Operations page (failed filings, feeds in error, jobs, mail) | M | 0 |
| 2 | Funnel page plus CSV export; three lifecycle e-mails through the existing outbox | M plus M | 0 (SES pennies) |
| 3 | E: copy cleanup in guest and host pages | M | 0 |
| 4 | Per-request query, DB-time and lock-time logging; weekly report | S | 0 |
| 5 | One connection per request; N+1 removal on the dashboard, stays list and stay fees | M | 0 |
| 6 | iCal skip-unchanged (conditional GET plus hash) | S | 0 |
| 7 | Separate data-encryption key with MultiFernet; encrypt birth date, address and request XML. HIGH risk: data migration with backup first. | M | 0 |
| 8 | Portability: `ON CONFLICT` form, `RETURNING` in `db.insert`, a null-safe helper, numbered migration files | M | 0 |
| 9 | Staging VM | S | $7 |
| 10 | Workstream 5 slugs, if still wanted | M | 0 |

### 9.3 At 100 hosts and beyond (as triggers fire)

| # | Item | Trigger | Effort | Cost per month |
|---|---|---|---|---|
| 1 | Blobs to S3 behind the storage interface | Database over about 2 GB | M | A few dollars |
| 2 | VM to 2 to 4 GB, 4 workers | p99 targets missed | S | +$5 to $17 |
| 3 | Postgres in Frankfurt plus 2 app servers | Need for HA, or the lock-wait signal | L (1 to 2 weeks) | About +$15 to $60 |
| 4 | PostHog (server-side) or self sign-up analytics | Self sign-up added, or paid acquisition | M | Free tier first |
| 5 | Audit log viewer for admin | First real incident, or a customer audit request | S | 0 |

## 10. Risks

| Risk | Where | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| Double filing or a lost filing after changing retry, claims or transactions | PR 230 item 2; any DB or queue migration | Medium | HIGH: a legal record goes wrong | One guard only (the DB claim), retry in the sweep only, tests for crash-retry-once, manual review of every diff to `reporting.py` |
| Filing wrong dates after date changes | PR 230 item 3 | Medium until fixed | HIGH | Trim to the booking plus the safety-net check; tests |
| Admin sees passport data without need | Impersonation today | High (it is the default today) | HIGH (GDPR, trust) | Masking plus logged reveal before go-live |
| Data loss between nightly backups | One VM, RPO up to 24 h | Low per day; over a year, real | HIGH | Litestream before go-live; quarterly restore test |
| VM failure, so downtime | Single VM | Low | Medium: filings delayed; the deadline is 3 working days | Restore runbook; Litestream makes restore minutes, not hours |
| One secret for sessions and data encryption | `db.py:989` | Low | HIGH if the secret leaks or must rotate | Separate data key with MultiFernet |
| Analytics consent ruling | Plausible without a banner | Low to medium | Low (switch to the server-side Events API) | Lawyer check; the code path is ready |
| Turso uncertainty, if adopted anyway | Acquisition, preview features | Medium | Medium | Not adopting it |
| Copy cleanup removes a legally needed sentence | E | Low | Medium | Keep list in 3.E; GDPR Art. 13 text untouched; lawyer read of the guest notice |
| Readable slugs expose host contact details | Workstream 5 | Low | Low | Random code suffix; hide the host card before the PIN |
| Estimates are wrong | Everything marked [ESTIMATE] | Medium | Low | The query and lock logging (7.3.4) replaces the estimates with real numbers within a month of launch |

## 11. Open questions for the founder

1. How many hosts, properties and feeds will be live at launch, and how many do you expect in 12 months? This sets the VM size and confirms the estimates in 7.2.
2. Which Lightsail bundle and region are you on today?
3. Will you add self sign-up, or keep creating accounts by hand? This decides whether a product analytics tool is ever needed.
4. Will you run paid ads that need conversion tracking? If yes, accept a consent banner on the marketing pages.
5. Guest names: keep them searchable in plain text (current), or encrypt them and give up search by name?
6. Impersonation: is a 60-minute session limit and masking of guest identity by default acceptable for your support work?
7. Slugs: do you want readable links badly enough to spend about 3 days after launch, given the random suffix stays?
8. For the lawyer: whether Plausible needs consent in Czechia, the legal basis for the three lifecycle e-mails, and every retention period in 6.5.

## Sources

- Turso pricing: https://turso.tech/pricing
- Turso durability and commit delay: https://docs.turso.tech/cloud/durability
- Turso regions: https://turso.tech/blog/turso-cloud-new-regions
- Turso concurrent writes preview: https://turso.tech/blog/concurrent-writes-on-turso-cloud
- Turso embedded replicas: https://docs.turso.tech/features/embedded-replicas/introduction
- Turso HTTP transaction limits: https://docs.turso.tech/sdk/http/reference
- Turso Python SDKs: https://docs.turso.tech/sdk/python/quickstart
- Turso encryption: https://docs.turso.tech/cloud/encryption
- Turso joining Supabase: https://turso.tech/blog/turso-is-joining-supabase
- AWS Lambda limits: https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html
- API Gateway HTTP API quotas (30 s): https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-quotas.html
- Lambda Function URLs: https://docs.aws.amazon.com/lambda/latest/dg/furls-http-invoke-decision.html
- AWS prices (Lambda, API Gateway, SQS, EventBridge Scheduler, S3, KMS, CloudWatch, RDS) for eu-central-1: the AWS Price List API, https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/index.json
- CloudFront pricing: https://aws.amazon.com/cloudfront/pricing/
- Lightsail pricing: https://aws.amazon.com/lightsail/pricing/
- Neon: https://neon.com/pricing
- Supabase: https://supabase.com/pricing
- Litestream: https://github.com/benbjohnson/litestream and https://fly.io/blog/litestream-revamped/
- ÚOOÚ on cookie consent from 2022: https://uoou.gov.cz/novinky/vse/cookies-od-zacatku-roku-2022-pouze-se-souhlasem
- EDPB Guidelines 2/2023 on Art. 5(3): https://www.edpb.europa.eu/system/files/2024-10/edpb_guidelines_202302_technical_scope_art_53_eprivacydirective_v2_en_0.pdf
- GA4 consent mode and data location: https://support.google.com/analytics/answer/14275483 and https://support.google.com/analytics/answer/12017362
- PostHog pricing and cookieless mode: https://posthog.com/pricing and https://posthog.com/tutorials/cookieless-tracking
- Umami: https://docs.umami.is/docs/cloud/faq
- Plausible pricing and EU hosting: https://plausible.io/#pricing and https://plausible.io/eu-hosted-web-analytics

## 12. Owner decisions (3 October 2026)

1. Database: SQLite plus Litestream to S3, added before go-live. No Turso. Postgres only when a second app server is needed. Until then: all SQL through the `db.py` helpers, no new triggers or SQLite-only features, and keep the `with db.immediate()` blocks small.
2. Hosting: stay on Lightsail, Frankfurt. No Lambda. Move from the 1 GB bundle ($7) to the 2 GB bundle ($12) when Litestream and the separate scheduler process are added. Next step up when needed: 4 GB ($24).
3. Analytics: Umami Cloud, free Hobby plan (100k events/month, EU servers), on the public marketing pages only. No PostHog. No analytics script on the app, the guest pages (`/l/...`) or `pick.html`. The sign-up funnel is counted from the database.
4. Google Ads: server-side sign-up conversion import. No Google tag on the site, no cookie banner. Built together with the future sign-up page: store the click ID (`gclid`) with the sign-up and upload the conversion via the Google Ads API. [Lawyer to confirm] the privacy-notice wording and the legal basis for storing the click ID.
5. Guest links: `/l/{slug}-{6-character code}` after go-live, as in workstream 5. The PIN stays.
6. Admin: only the owner, for now. Build the minimal version: a reason plus a 60-minute expiry when viewing a host's account, and guest identities masked by default with a logged reveal. No separate support role yet.
7. Meta ads (added 4 October 2026): Meta and Facebook groups are the main channel. Sign-up conversions go to Meta through the Conversions API from the server (no Pixel, no cookie), only with a separate unticked consent box, shown only when the visitor arrived with an `fbclid`. See `04_legal_positions.md` section 6 and WP21.
8. Council (4 October 2026): WP23 filing watchdog and WP24 terms texts added before go-live; WP06 moved after go-live. See `06_council_verdict.md`.
