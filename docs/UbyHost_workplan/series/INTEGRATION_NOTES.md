# Integration notes: one linear series of 34 patches on the real main

## Base and method
- Base: `origin/main` 709076a, PR 230 squash-merged with its six follow-up fixes:
  - one automatic resend from the sweep only (`submission.retried_at`);
  - date trimming instead of re-signing (`icalsync._fit_unsent_guest_windows`);
  - the account ZIP includes stay-fee filings;
  - the cancelled-stay mail kind `cancelled_with_guests`;
  - test cleanup and repo hygiene, including the archived Ticket Wallet guest UI under `static/archive/` and `templates/guest/archive/`.
- Worktree `/tmp/wp/final`, branch `final`. Every patch was applied with `git am -3`. Conflicts were resolved by hand, then `git am --continue`. Every commit whose patch needed a resolution or a cross-WP change has a "Conflict resolution:" paragraph in its message. Stale "Integration (new order)" paragraphs from the previous series were dropped where they described an order that no longer holds.
- Sources:
  - the previous `series/0001..0026`, written on `wpbase` (PR 230 head 4fd05de plus test cleanup);
  - `round3/WP25`, `WP26`, `WP27` and `WP28`, written on `golive` (wpbase plus old 0001..0012);
  - `round3/WP30`, written on origin/main;
  - WP29, new;
  - WP32 (container sizing) and WP31 (one automatic resend), new in the latest rebuild.
- Rule: PR 230's behaviour wins on filing logic; every WP keeps its intent.
- Latest rebuild (33 patches): a new branch from origin/main took steps 1 to 4 of the 31-patch series, then the new WP32 commit, WP30, the new WP31 commit, and the remaining 26 steps, all with `git am -3`. All 26 merged without a conflict. The WP23 commit was then amended with a WP31 test and one docstring line (see 0018), and the 15 later commits were cherry-picked on top cleanly. Branch `final` now points at the new head.
- Verification: a fresh worktree from `origin/main` took all 33 patches with plain `git am` (no `-3`), with no conflicts and no warnings. The resulting tree is identical to branch `final` (`git diff --quiet` exit 0). The worktree was removed.
- Python: `/tmp/pr230/App/.venv/bin/python`. Tests ran from `App/` with `LD_LIBRARY_PATH=/tmp/libs/root/usr/lib/aarch64-linux-gnu ... -m pytest -q -p no:cacheprovider`.

## Order
Infrastructure first, then the go-live set, then the rest.

| # | Commit | Conflicts or integration work |
|---|---|---|
| 0001 | WP05 Litestream | none |
| 0002 | WP06 Worker process | main.py lifespan |
| 0003 | WP07 Heartbeats, cache | guest/base.html, guest/pin.html (archived TW UI); WP07 test |
| 0004 | STEP0 Staging | none |
| 0005 | WP32 Container sizing, 8 GB server | new WP |
| 0006 | WP30 Doručenka PDF | none |
| 0007 | WP31 One automatic resend | new WP |
| 0008 | WP01 Deadline after reporting | none |
| 0009 | WP02 Property names | none |
| 0010 | WP03 Guide second pass | none; guide text corrected to PR 230's merged behaviour |
| 0011 | WP04 Admin guest data | none |
| 0012 | WP25 Reported bugs | guest_form_admin.html; `_field`; hand-filed tests deferred to WP23; moved-after-report copy |
| 0013 | WP28 UI sweep | 4 base templates (cache keys), host.css, reservation_detail.html; one overflow fix with WP25 |
| 0014 | WP08 Upload hardening | main.py lifespan, 3 base templates |
| 0015 | WP09 Umami | none |
| 0016 | WP27 Privacy first | privacy.html |
| 0017 | WP22 Retention | none |
| 0018 | WP23 Filing watchdog | db.py, mail.py, test_claim_mail.py, guest_form_admin.html; PR 230 retry state; no SMS; WP31 test |
| 0019 | WP24 Terms, DPA | privacy.html |
| 0020 | WP26 Guest languages | guest/base.html, form.html, guest.css, e2e and TW tests; archive left alone; WP27 strings |
| 0022 | WP10 Admin Operations | none |
| 0023 | WP13 Perf logging | none; `awaiting_retry` added to the deadline run line |
| 0024 | WP14 Connection reuse | none |
| 0025 | WP15 Skip unchanged iCal | none |
| 0026 | WP17 Copy cleanup | 3 base templates, guest/stay.html; de/es/fr follow WP17; claim hint; WP27 storage row |
| 0027 | WP11 Admin funnel | none |
| 0028 | WP12 Lifecycle mail | none |
| 0029 | WP16 Data key | none |
| 0030 | WP18 Postgres prep | db.py init; workspace_export.py `IS ?` |
| 0031 | WP19 Readable links | routes/guest.py imports, _components.html, e2e |
| 0032 | WP20 Sign-up | none |
| 0033 | WP21 Meta CAPI | none |
| 0034 | WP29 No em dashes | new WP |

"none" means `git am -3` merged cleanly, including the resolutions the previous series had already folded into the commit (for example WP10, WP11, WP12, WP14, WP15, WP16, WP20 and WP21 against their predecessors).

## Per step

### 0002 WP06
- Resolution: main.py lifespan. WP08 comes later now, so the old 12 MP `Image.MAX_IMAGE_PIXELS` line stays before WP06's role check and `db.startup_lock()` block.

### 0003 WP07
- PR 230 archived the Ticket Wallet guest UI. guest/base.html keeps main's stylesheets and `guest-enhancements.js`, drops `guest-ticket.css` and `ticket.js`, and keeps WP07's `?v=` on the favicons and the `load_signature_js` switch (form and PIN page).
- `tests/test_wp07_cache_heartbeats.py`:
  - the guest script-order check uses `guest-enhancements.js`;
  - the versioned-URL scan skips `templates/guest/archive/`, which no route renders.

### 0005 WP32 (new): container sizing for the 8 GB server
- See `notes/WP32-container-sizing.md`. Dockerfile CMD reads `UBYHOST_WEB_WORKERS` (default 2, 4 documented for production); `mem_limit` web 2g, worker 1g, litestream 256m, caddy 256m, each overridable from `.env`; local snapshot retention 7 days documented, code default 30 unchanged. New `tests/test_wp32_container_sizing.py`.
- Later steps merged over it without conflicts (WP07 and WP23 touch the same `.env.example` and compose file in other places).

### 0007 WP31 (new): exactly one automatic resend
- See `notes/WP31-one-auto-resend.md`. Closes the open item from the previous series: the sweep's resend is written with `submission.mode = 'auto_resend'` and is never resent itself. An unclear resend stays `outcome_unknown`, its guests stay held, and the existing alert and mail fire. A host's manual send is allowed and gets its own one automatic resend if its answer is unclear. No schema change.
- The guide text in 0010 ("sends that batch once more at the next automatic check", "you get an alert whenever an answer is unclear") is now exactly true; unchanged.

### 0010 WP03: guide checked against the merged code
- Checked and corrected:
  - `guide.reporting.failure` and `guide.faq.twice_a`: an unclear answer raises an alert at once, and the sweep resends that batch once at the next automatic check. An immediate send never retries. A duplicate answer counts as reported.
  - `guide.stays.cancelled`: the warning also goes out by e-mail (`cancelled_with_guests`).
- Already matched main: `guide.stays.dates_changed` (date trimming, no re-signing) and `guide.settings.deletion` (ZIP with stay-fee filings).
- WP25 then changed the last sentence of `dates_changed` (see 0012).

### 0012 WP25
- `guest_form_admin.html`: WP23 is later now, so the banner keeps main's sent/submitted title with WP25's `id="filed-lock-note"`. WP23 adds its filed-by-hand title in its own step.
- `reporting._field()` came from WP23 on golive. It is defined here. WP23's second copy is dropped in 0018.
- `tests/test_wp25_reported_bugs.py`: the hand-filed (`manual_filed_at`) variants move to 0018, and the stay-page test declares one guest.
- Cross-WP copy: with filed guests locked, the moved-after-report notice (`notification.reason.moved_after_report`) and the guide's date-change paragraph send the host to the UbyPort web application for a correction instead of "resend" (EN, CS). `tests/test_notification_copy.py` was updated.
- WP25's open question on the `VracetPDF` order is settled by WP30 (0006).

### 0013 WP28
- Cache keys: app.css `20261004w`, host.css `20261004x`, guest.css `20261004w`. guest/base.html keeps main's stylesheet list.
- One overflow fix with WP25: WP28's shared `.panel.tight.scroll-x { overflow-x: auto }` in app.css is the scroll rule for every wide table. WP25's duplicate host.css rule became `.host-workspace .panel.housebook-scroll { position: relative }`. WP25's house book word-wrap floors and WP28's `break-word` cells both stay.
- host.css keeps WP25's house book, signature and report blocks and WP28's signature-block rules.
- The hand-filing panels (WP23) are applied in 0018 with WP28's `class="panel"`.

### 0014 WP08
- main.py: WP08's `passport_photos.MAX_IMAGE_PIXELS` replaces the 12 MP line, before WP06's lock.
- app.css `20261004y`.
- Kept from before: the WP04 test compares with `passport_photos.read_photo()`.

### 0016 WP27
- privacy.html: the privacy-first line goes above main's effective-date line. 0019 switches that line to `legal_effective('privacy')`.

### 0018 WP23
- Merges: PR 230's `submission.retried_at` and `cancelled_with_guests` kept next to WP23's columns and mail kinds. The banner gets WP23's filed-by-hand title. The duplicate `_field()` is dropped. WP25's hand-filed tests come back. The hand-filing panels use `class="panel"`.
- PR 230 retry state. A guest on an `outcome_unknown` batch with `retried_at` empty is waiting for the sweep's one resend. `filing_watchdog.at_risk_stays` joins the guest's submission. A stay is "awaiting the automatic resend" when:
  - every unfiled guest is in that state;
  - its deadline has not passed;
  - the batch finished at most `RETRY_GRACE` ago (two sweep intervals, 20 min by default).

  Such a stay gets no host mail, no digest line and no heartbeat `/fail`. Otherwise it is at risk as before. `run()` returns `awaiting_retry`, and the scheduler logs it. The grace runs from each batch's own finish time; with WP31 there is only one resend, so it applies once. 6 new tests; one existing stub takes the new keyword.
- WP31 (now earlier, 0007): the commit carries one more test, `test_a_stay_held_on_an_unclear_automatic_resend_is_at_risk_after_the_grace`: a stay held on an unclear `auto_resend` batch is awaiting only within that batch's grace, then at risk, and still at risk five grace windows later. The docstring now says the resend is never resent, so the grace applies once. Watchdog code unchanged. Noted in the commit's "Conflict resolution" paragraph.
- Owner change, no SMS: `config.py`, `deploy/lightsail/.env.example` and `docs/plans/UbyHost_Audit_and_Cursor_Plan_2026-09-28.md` now say the healthchecks.io filing check notifies the owner by e-mail. It is sent by healthchecks.io, so it still arrives when UbyHost's own mail is broken. `notes/WP23-filing-watchdog.md` and `05_owner_checklist.md` were updated the same way. Code unchanged.

### 0019 WP24
- privacy.html: privacy-first line, then `legal_effective('privacy')`.

### 0020 WP26
- WP26's `guest-ticket.css` and `ticket.js` changes landed on the archived copies through rename detection. They were dropped, and the archive is untouched.
- The `<details class="g-lang">` language menu is styled for main's arrival-lane header in guest.css, replacing the two-pill rules. It was checked at 320 px in German: `round3/shots/final-wp26-lang-*.png`.
- Not carried over, because main's arrival lane does not need them:
  - the `data-tw-*` date-of-birth attributes: main's form already uses `date_placeholder`;
  - the 320 px step-strip rule: the arrival lane lists its steps vertically.
- guest.css cookie table: WP28's `.scroll-x` containment plus WP26's phone card layout. The first cell may wrap in card mode.
- Keys: guest.css `20261004z`, signature.js `20261004b`.
- e2e: main's flow ("Add a person" link, done text) with labels from the guest's language, plus WP26's privacy-page check. `test_ticket_wallet_v3.py` keeps main's trimmed version.
- WP27's `privacy_first_line` and its storage row get de/es/fr text.

### 0023 WP13
- The deadline job's run line also carries `awaiting_retry` (WP23 above).

### 0026 WP17
- app.css `20261004z`. guest/stay.html keeps main's version (no TW keep-this-page line).
- WP26 is earlier now. For each of the 12 guest keys WP17 rewrote, de/es/fr now say the same thing as the new EN text: `legal_intro`, `host_details_help`, `claim_help`, `claim_email_help`, `assigned_body`, `pin_help`, `someone_missing`, `residence_help`, `passport_photo_help`, `legal_notice_duty_body`, `legal_notice_reporting_body`, `privacy`. The 15 keys WP17 deleted are deleted in de/es/fr too.
- Main's claim form shows only `claim_email_help`, so it also gets the `tw_email_short` hint ("We send your private link here. No marketing.") that WP17's shorter text relies on.
- WP17 removes the house book intro dialog, so WP27's `ubyhost_housebook_legal_v1` storage row is removed, and `test_cookie_inventory` asserts only that the scan found keys.
- Test updates: `test_guest_languages` (six years now in `privacy`) and `test_guest_confirm_screen` (main has no `tw_label_confirm`).

### 0030 WP18
- `_init_db_locked`: PR 230's `_resolve_legacy_resign_alerts` runs before WP18 records the baseline and applies migrations. `submission.retried_at` is part of the frozen baseline.
- PR 230's ZIP query in `workspace_export.py` used a bare `owner_user_id IS ?`. WP18's guard rejects that, so it now uses `db.null_safe_eq`.

### 0031 WP19
- `routes/guest.py` imports: WP26's list plus `guest_slug`. `host_i18n` is no longer imported there (found by ruff, fixed in this commit).
- `_components.html`: WP28's `show_toggle` with WP19's `finish.link_key`.
- e2e: WP19's `_register_a_group_of_three` takes the language, so WP26's en/de/es/fr runs and WP19's readable-link runs share it.

### 0034 WP29 (new)
- See `notes/WP29-no-em-dashes.md`: 230 catalogue strings and 3 templates changed, a new `test_no_em_dashes.py`, and 17 test files updated to the new wording.

## Cross-WP decisions carried over from the previous series
These are still in the commits:
- WP08: the WP04 photo test reads the photo through `read_photo()`.
- WP13 and WP14: counters inside WP14's per-thread connection; `lock_ms` around `BEGIN IMMEDIATE`.
- WP15 and WP10: a quiet feed is judged by `COALESCE(last_checked_at, last_sync_at)`.
- WP12 and WP23: `LIFECYCLE_KINDS` holds only the three lifecycle kinds, so the opt-out never blocks a watchdog mail.
- WP16: `check_data_keys()` inside the startup lock and in the worker.
- WP18: `execute()` returns the row count; migrations 0002 to 0004 for WP19, WP20 and WP21.
- WP19: the query-budget fix.
- WP20: the sign-up opt-out writes WP12's column; the Google Ads recipient is listed only while sign-up is on; the funnel stages.
- WP21: `client_user_agent`, consent version `ads-meta-v2`, one recipients panel.
- WP24: Terms, Privacy and DPA at 1.6, accepted once.

## Checkpoints (full suite in four chunks, each one process; browser tests separately)

The first three columns are from the previous 31-patch build (old numbering) and were not rerun. The last column is the 33-patch tree.

| Chunk | After STEP0 (0004) | After WP26 (old 0018, go-live set) | Previous final (old 0032) | Final (0034) |
|---|---|---|---|---|
| `test_[a-c]*` | 285 passed, 2 skipped | 299 passed, 2 skipped | 334 passed, 2 skipped | 334 passed, 2 skipped |
| `test_[d-h]*` (no e2e) | 683 passed | 800 passed | 843 passed | 846 passed |
| `test_[i-r]*` | 693 passed | 756 passed | 858 passed | 858 passed |
| `test_[s-z]*` (no geometry) | 537 passed | 645 passed | 689 passed | 712 passed |
| Guest browser e2e, `UBYHOST_REQUIRE_BROWSER=1` | 4 passed | 13 passed | 16 passed | 16 passed (three runs: en+de, es+fr, readable link + Czech) |
| `test_host_geometry` + `test_wp28_geometry` | 2 passed | 9 passed | 9 passed | 9 passed |
| Total | 2204 passed, 2 skipped | 2522 passed, 2 skipped | 2749 passed, 2 skipped | 2775 passed, 2 skipped |

- New in the final column: WP32's 16 sizing tests and WP31's 7 resend tests in `test_stale_submission.py` (`[s-z]`, +23), WP31's new mode in `test_host_labels.py` and the WP23 watchdog test (`[d-h]`, +3). The `[s-z]` run included `test_wp28_geometry` (7 passed); it is counted once, in the geometry row.

- No failures in these chunk runs. The 2 skips are in the `[a-c]` chunk, the same as on main.
- Ruff (`app tests tools scripts mock_ubyport`, E9,F63,F7,F82,F401,F841) on the final tree: all checks passed.

## Remaining open items
- Order-dependent tests that also fail on origin/main (with WP30), not caused by this series:
  - `test_mail_failed_alert.py::test_the_send_loop_stores_the_code_and_renders_a_name` fails when run alone or in an `[m-r]` chunk ("no such table: email_outbox");
  - `test_onboarding` followed by `test_demo_seed` fails;
  - `test_host_i18n::test_language_endpoint_sets_cookie...` fails when it runs first in a process;
  - `test_wp28_ui_sweep` followed by `test_claim_mail` fails 3 tests (WP28's demo seed leaves stays; alphabetical order is unaffected).
- Fixed by WP31 (owner decision Q4): the resend after an unclear answer is no longer repeated every sweep. One automatic resend, then the guests are held and the host is alerted.
- With WP25's lock a filed guest cannot be edited, but PR 230's raw English alert detail for a moved stay (in `icalsync.py`) still says "correct the guest's dates and resend". The host sees the translated `notification.reason.moved_after_report`, which now points to the UbyPort web application.
- German header at 320 px: the guest page title ("Gästeregistrierung") is cut by the narrow header, and the language menu itself is fine. Not a regression (the old two pills took more room). Worth a look in the native-speaker review.
- WP26 translations need a native-speaker review (see `notes/WP26-guest-languages.md`), now including the WP17 and WP29 strings.
- WP32: `docker compose config` and a real `docker compose up` with the new limits were not run here; the YAML is validated with python in `test_wp32_container_sizing.py`. Run `docker compose config | grep mem_limit` on the server once.
- Not run: the full suite in one process, `shellcheck`, `docker compose config`, a real staging deploy with `ubyport_env=test`, the WP30 check against the real UbyPort test endpoint (see `notes/WP30-dorucenka-pdf.md`).
- Go-live without the post-go-live set is no longer the shape of this series: WP06 (worker process) is 0002, so the scheduler, the heartbeats and the watchdog run in `app.worker` from the start. Production needs the worker service from WP06's compose file.
- `05_owner_checklist.md` still numbers steps by the previous series (0006 WP07, 0010 WP23 ...; WP23 is now 0018). Its SMS wording is fixed; renumber it with the new order when it is next edited.
- Migration files 0002 to 0004: a scratch database from an old WP19, WP20 or WP21 branch build must be recreated (unchanged).


## Round 4: WP33 added as 0021 (34 patches)

- Branch from `origin/main`, `git am` of 0001 to 0020, then the new WP33 commit, then the old 0021 to 0033 with `git am -3`. All 13 applied with no conflict. Patch numbers in this file were shifted by one for those 13.
- Series regenerated with `git format-patch origin/main` from that branch.
- Checks on the 34-patch tree: ruff (CI selection) passed. `test_wp33_gates.py` plus the reservation, dashboard, deadline-after-reporting, filing-watchdog, cookie, env, i18n and em-dash tests passed (116 and 116 in two runs). `test_wp33_gates.py::test_an_overdue_unfiled_stay_is_in_the_default_stays_view` fails without the WP33 `admin.py` change (checked).
- The full suite was not rerun on the 34-patch tree. The sandbox stops long processes. Cursor runs it on every PR.
- Tried and dropped: WP16 directly after WP33. It conflicts in `App/app/db.py` (`ADDED_COLUMNS` from WP12 and WP15, `is_decrypted` from WP14).
