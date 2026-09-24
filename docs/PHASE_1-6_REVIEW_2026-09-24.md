# UbyHost Phases 1–6 post-merge regression review — 2026-09-24

> **Scope:** Phases 1–6 as merged to `main`, that is PRs #103, #104, #106, #107,
> #108, #109, #110, #111, #112, #113, plus the direct pushes to `main` that
> followed #113. Findings are reported against `main` @ `7d22b50`, which is also
> the SHA running in production. Source: GitHub issue #114.

## Posture summary

**Bottom line:** nothing is broken in the sense of crashes or failing tests. However, 24 reproduction tests written during the review show real logic bugs. Several of them contradict a phase's own stated goal, and a few of them can leave a guest **never filed with the police, with no warning**.

## Regression run (Python 3.12, same setup as CI)

| Check | Result |
|---|---|
| `ruff` (the CI rule set) | Pass |
| `pytest` (all 729 tests) | **729 passed**, 0 failed |
| Coverage | 86.57% against a required 86%. Passes, but only just. |
| `tools/smoke.py` | Passes. **But this gate is ineffective** (see #6 below). |
| Route table before and after #112 | 109 routes both times. None lost, none renamed, and every route keeps its auth and CSRF dependency. |
| GET sweep before and after #112 (150 URLs, en and cs) | Same status codes and same HTML |

## Findings

### High

| # | Sev | PR | Issue | Where | Evidence |
|---|---|---|---|---|---|
| 1 | **High** | #112 | **The demo guard is switched off outside mock.** `is_demo_apartment` returns False whenever `UBYPORT_ENV != "mock"`. If the demo is seeded under mock and the app is then switched to test or prod, demo guests are sent to UbyPort. The "Clear demo" button also disappears. | `app/demo.py:41` | CONFIRMED: 2 `ZapisUbytovane` posts were made |
| 2 | **High** | #112 | **The signature check can be bypassed.** A guest can POST `signature=imported`, and the record is saved as signed and becomes sendable. Before #112 this was rejected with a 422. | `app/reporting.py:180`, `routes/guest.py:1318` | CONFIRMED |
| 3 | **High** | #111 | **A guest who corrects their own form stays over the retry cap forever.** The guest save does not reset `submit_attempts`, so the sweep never sends the record, and the "stuck" card clears itself. | `routes/guest.py:1399`, `reporting.py:755/820` | CONFIRMED |
| 4 | **High** | #109 | **Stays can swap identities in feeds without UIDs.** The made-up key depends on the order of events in the feed. When an earlier stay with the same summary ("Reserved") drops out, the next stay's row is cancelled, and that guest silently disappears from sending. | `app/icalsync.py:208-215` | CONFIRMED |
| 5 | **High** | #104 | **One row that can't be decrypted stops sending and deadline alerts for *every* host.** `DecryptionError` is raised inside `query()` and nothing in `sweep()` or `check_deadlines()` catches it. | `app/db.py:470,613`, `reporting.py:1251` | CONFIRMED |
| 6 | **High** | #113 | **The CI smoke job never contacts the server it starts.** `smoke.py` ignores its URL argument and runs in-process, so a server that fails to boot would still pass CI and deploy. | `tools/smoke.py`, `ci.yml:88-92` | CONFIRMED: passes against `http://127.0.0.1:1`, where nothing is listening |
| 7 | **High** | #103 | **Job-failure alerts are invisible to logged-in users.** They are stored with `owner_user_id = NULL`, and `open_alerts(uid)` filters those rows out, so W1.3 has no effect. | `scheduler.py:34-46`, `alerts.py:336` | CONFIRMED |
| 8 | **High** | #103 | **Guests who arrive early never trigger a deadline alert.** `check_deadlines` still filters on `r.date_from <= today` and ignores the guest's earlier `stay_from`. | `reporting.py:1301` | CONFIRMED |
| 9 | **High** | #103 | **When a stay moves, guests are left on the old dates** unless their dates match the old booking exactly. The deadline follows the old dates, so there is no alert. | `icalsync.py:498-510` | CONFIRMED |
| 10 | **High** | #103 | **The W1.5 quiet-window completion never fires unattended.** It is only checked on save, and saves reset the clock. | `reporting.py:534-575` | CONFIRMED |
| 11 | **High** | #104 | **The backfill script can create a new key without warning.** Run without `UBYHOST_SECRET_KEY`, it creates a new key, encrypts everything with it, blanks the plaintext, and exits 0. The app then can't read any guest. | `scripts/migrate_encrypt_doc_fields.py:37-68` | CONFIRMED |
| 12 | **High** | old | **Live iCal tokens (Airbnb and Booking) and a guest passport row are in git history** from commit `a3b96a0`. | history | CONFIRMED. **Rotate both iCal links now.** |

### Medium

- **#111** The cap is bypassed on "immediate" properties. `submit_stay_if_complete` resends with `ignore_automation=True` on unrelated edits: attempts went 3 → 8. `reporting.py:604-612`
- **#109** The receipt link is lost, or points at the wrong submission, after a second duplicate (150). Fix: `guest["receipt_submission_id"] or …`. `reporting.py:1018`
- **#109** The submission detail page shows each guest's *current* state, so an old submission refused with 112 now shows "Accepted". `admin.py:1703-1738`
- **#106** A stay date that can't be parsed (`garbage`, `2026-02-30`) skips the W3.2 window check and is stored raw. Such a guest also escapes the passport-photo purge. `routes/guest.py:1273-1296`
- **#106** The claim routes skip the W3.5 reach-back limit, so the "which IDs exist" oracle is still open. `guest.py:831,891`
- **#106** When the host releases a claim, a device that already confirmed isn't revoked. The cookie isn't tied to `token_version`. `guest.py:184`, `claim.py:470`
- **#106** Per-IP limits can be bypassed by spoofing `CF-Connecting-IP` when the origin is reached directly. Caddy must accept only Cloudflare's ranges or overwrite the header. `client_ip.py:24-43`
- **#104** Plaintext doc numbers are still in the SQLite free pages after the backfill. Fix: `PRAGMA secure_delete=ON` plus `VACUUM`.
- **#104** Production backups don't include the key (it lives in `.env`), so an off-site restore can't be decrypted.
- **#104** Rolling back loses data. The plaintext column is no longer written, so the old code files an empty `cDocN`.
- **#112** Opening a guest link sets the shared `ubyhost_lang=cs` cookie, and the host UI switches to Czech.
- **#112** Foreign guests' claim and reminder e-mails now default to Czech.
- **#112** The backfill script fails on a DB the new app hasn't opened (no `init_db()`).
- **#112** A bad secret key no longer stops startup: `/healthz` returns 200 while `/login` returns 500, so the deploy health checks pass.
- **#103** The re-sign alert is resolved by *any* guest's save, and nothing blocks filing the old signature.
- **#103** The partial-feed guard counts all events instead of the stored UIDs it still matches, so a feed of unrelated events cancels every stay.
- **#103** A crash partway through a feed sync leaves `last_status='ok'` and raises no alert.
- **#113** Manual `workflow_dispatch` can deploy any branch. There is also no `concurrency:` group on deploy, so deploys can overlap.
- **#113** The "Czech time" deadline test can't catch the bug it's named for. Swapping in the UTC date still passes the suite.

### Low (abridged)

- A PIN lockout from many IPs raises no alert.
- A concurrent double-confirm can both return True (use `rowcount`).
- There is a race window in which the sweep and a manual send both file the same guest.
- In the mock, 112 still means "reported late".
- The Caddy reload after `up -d` has no retry.
- `tools/design_matrix.py` imports the deleted `walkthrough.py`.
- The DejaVu fonts committed to `App/app/static/fonts/` are unused, while the PDF code looks for system DejaVu, which the slim image likely lacks. Czech letters may be mangled in PDFs.
- There are Czech plural and mixed-language flash strings.
- The stale `docs/ubyhost-docs-update.patch` is still in the repo.
- Docs-only pushes trigger full production deploys (add `paths-ignore`).

## Direct pushes to main after #113

All of them were docs or fonts only. No runtime code, templates, requirements, Dockerfile, deploy scripts or CI changed. Production (`7d22b50`) passed CI, and its code is identical to the #113 merge.

## Suggested order

1. Rotate the iCal tokens (#12).
2. Fix #1 and #2. Both are one-line reverts of #112 regressions.
3. Fix #3, #4, #5, #7 and #8. These are the "silently never filed" class.
4. Make the smoke test hit the real port (#6), so CI protects the rest.
5. Guard the backfill script (#11) **before** anyone runs it in production.

## Reproduction tests

These are in `repro_tests/`. Drop them into `App/tests/` to run them.

- `test_p1_review.py` (8) and `test_p3_review_repro.py` (9) **pass** on main because they assert the buggy behaviour.
- `test_zz_review.py` (7) **fails** on main because it asserts the correct behaviour. It should go green once the fixes land.
