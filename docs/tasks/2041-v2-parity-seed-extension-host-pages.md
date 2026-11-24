# 2041: V2 visual parity, part 2: seed the missing host-side data, compare the pages that need it

Status: todo
Depends on: 2040 (its `parity_env.sh`, `parity_cases.py`, the harness changes) | Base commit: HEAD | Branch: current
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 100k tokens (stop at 25 calls; see section 8)

## 1. Objective

2040 compared every host/admin page the seed already feeds, mostly in empty states. This brief
adds the data those pages need (guide items, questions, Leon, payment requests, booking site,
cleaning, Havel, privacy requests, submission, account invite, a property-detail variant) and
compares them populated and in the important tab states, cs and en, at 390/768/1280 px.
**Do not fix any visible difference.** Only tooling, seed, run, report. Guest and token-link
pages for non-hosts are brief 2042.

## 2. Context

- Do not change `scripts/e2e/seed.py`: `page_parity_audit.py` and CI depend on it. The new data
  goes in a NEW file `scripts/e2e/seed_parity_extra.py`, run AFTER the audit seed on `parity_run`.
- `page_parity_visual.main()` (2040) calls `audit.seed_db()` which builds `parity_tpl`, clones it
  to `parity_run`; the extra seed runs against `parity_run` before servers start (hook point:
  right after `seed, refs = audit.seed_db()`).
- The extra seed runs with the Python app code the way `seed.py` does: `cd App`, env from
  `audit.ENV` plus `UBYHOST_DATABASE_URL=<PG>/parity_run`, `from app import db, ...`.
  Use `db.insert` / `db.execute` / `db.query_one` only (rule 5), and an app helper where one exists.
  No real data: names `Parity Guest`, mail `*@e2e.test`, every text is lorem-style or `E2E ...`.
- Helpers (verified by grep): `guest_guide.add_kind(apartment_id, kind, source=)`,
  `guest_guide.save(apartment_id, item_id, fields)`, `guest_guide.add_custom(apartment_id, topic, title)`,
  `guide_facts.STEPS` (quick-answer step names), `payment_request.create(...)` (line 42),
  `payment_request.guest_token(row)`, `cleaning.save_event(apartment_id, values)`,
  `cleaning.new_share(owner_id, property_ids)`, `havel.record_gap(lang, page, kind, question)`,
  `havel.record_stat(kind)`, `property_page.save_page(apartment_id, description=, amenities=, ...)`,
  `lifecycle_mail.unsubscribe_token(user_id, address)`.
  Tables without a helper (`guest_question`, `submission`, privacy request, account invite, booking
  site config, Leon config): copy the column list from `App/migrations_pg/00001_baseline.sql`
  (`grep -n 'CREATE TABLE public.guest_question' ...`, read 25 lines) and use `db.insert`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `scripts/e2e/seed_parity_extra.py` | new | the extra synthetic data, prints a JSON of ids |
| `scripts/e2e/parity_cases.py` | edit | append `EXTRA_CASES` (groups E, F, G) |
| `scripts/e2e/page_parity_visual.py` | edit | run the extra seed after `seed_db()`, merge its ids into the placeholders, include `EXTRA_CASES` |
| `docs/tasks/2041-report.md` | write | verdict table + visible-row descriptions |

Never touch `App/app/**`, `go/**`, `scripts/e2e/seed.py`.

## 4. Steps

1. Environment: `cd /home/user/jsfpecharoperations && source scripts/e2e/parity_env.sh 2>&1 | tail -3; git log --oneline -3 | tail -3; ls scripts/e2e/parity_cases.py`.
   If `parity_cases.py` is missing, stop (2040 not merged into this branch).
2. Find each helper's signature, one grep per group, 40 lines max each (examples):
   `grep -n -A22 '^def create' App/app/payment_request.py | head -45`;
   `grep -n -A12 '^def save_event' App/app/cleaning.py | head -25`;
   `grep -n -B1 -A6 'booking_site' App/app/routes/payments.py | sed -n 1,40p` (which table/columns the `/booking-sites` and `/apartments/{id}/booking-site` pages read: grep `FROM booking_site\|FROM \w*site`);
   `grep -n -A12 'privacy_request' App/app/routes/privacy_requests.py | head -40`;
   `grep -rn 'account_invite\|pending_invite' App/app/routes/admin_accounts.py | head -8`.
   Rule: a helper that needs more than 2 greps to understand is replaced by `db.insert` with the
   baseline column list. Write down (in your head, not a file) the 12 ids below.
3. Create `scripts/e2e/seed_parity_extra.py`. Skeleton (fill each `# TODO(db)` with the helper or
   `db.insert` found in step 2; keep every block in its own `try/except` that prints
   `{"skipped": "<block>"}` to stderr and continues, so one missing helper never kills the run; list the
   skipped blocks in the report):
```
"""Synthetic extra data for the visual parity run (brief 2041). Run from App/: python ../scripts/e2e/seed_parity_extra.py <owner_user_id> <apartment_id> <reservation_id>"""
import json, os, sys
sys.path.insert(0, os.getcwd())
from app import db  # noqa: E402

def main():
    owner, apt, res = (int(x) for x in sys.argv[1:4])
    out = {}
    # 1 guide: 4 items in different states (missing, check, done, skipped), 2 quick answers
    # 2 guest_question: 2 questions (one open, one answered) for apt
    # 3 Leon: settings row for apt (enabled) so /leon and /leon/setup/* render configured
    # 4 payment_request: 3 requests (open, paid, expired) -> out["pay_open"], out["pay_paid"]
    # 5 booking site: config for apt + 1 booking_hold/booking in 'requested' state -> out["booking_id"]
    # 6 cleaning: 3 events over next 7 days for apt, 1 share -> out["cleaning_event"], out["share_token"]
    # 7 havel: 3 gaps, a few stats -> shows /havel populated
    # 8 privacy_request: 2 rows (open, closed)
    # 9 submission: 1 per submit_state 'draft' and 'sent' -> out["submission_id"], out["submission_sent"]
    # 10 account invite for a new e-mail invited@e2e.test -> out["invite_token"]
    # 11 a second property (kind 'property' variant of /apartments/{id}) -> out["property_id"]
    # 12 mail unsubscribe token for the owner -> out["unsub_token"]
    json.dump(out, sys.stdout)

main()
```
   Check: `cd App && .venv/bin/python -m py_compile ../scripts/e2e/seed_parity_extra.py && echo ok | tail -3`.
4. Hook it in `scripts/e2e/page_parity_visual.py` (anchor `seed, refs = audit.seed_db()`): immediately after it,
   run `subprocess.run([sys.executable, str(ROOT/"scripts/e2e/seed_parity_extra.py"), str(seed["h1"]["id"]), refs["apartment_id"], refs["reservation_id"]], cwd=APP, env={**os.environ, **audit.ENV, "UBYHOST_DATABASE_URL": f"{audit.PG}/parity_run"}, capture_output=True, text=True, check=True)`, parse stdout JSON into `extra`, and pass `extra` to `fill()` (2040) so that the placeholders `{pay_open} {pay_paid} {booking_id} {cleaning_event} {share_token} {submission_id} {property_id} {invite_token} {unsub_token}` resolve. Cases whose placeholder is missing from `extra` are skipped and listed as `SKIPPED (seed block missing)` in the report, never silently dropped.
5. Append to `scripts/e2e/parity_cases.py` an `EXTRA_CASES` list (same tuple shape, `fill` handles it; `page_parity_visual.table_cases` iterates `CASES + EXTRA_CASES`):
```
EXTRA_CASES = [
    # E: populated versions of pages that were empty in 2040
    ("cleaning-full", "/cleaning", "host", "E"),
    ("cleaning-edit", "/cleaning/events/{cleaning_event}/edit", "host", "E"),
    ("cleaning-shares-full", "/cleaning/shares", "host", "E"),
    ("havel-full", "/havel", "host", "E"),
    ("privacy-requests-full", "/privacy-requests", "admin", "E"),
    ("payments-full", "/payments", "host", "E"),
    ("payment-share", "/payments/requests/{pay_open}/share", "host", "E"),
    ("payment-qr-open", "/payments/qr/{pay_open}", "host", "E"),
    ("payment-qr-paid", "/payments/qr/{pay_paid}", "host", "E"),
    ("booking-sites-full", "/booking-sites", "host", "E"),
    ("booking-site-setup-full", "/apartments/{apt}/booking-site", "host", "E"),
    ("submissions-full", "/submissions", "host", "E"),
    ("submission-draft", "/submissions/{submission_id}", "host", "E"),
    ("submission-sent", "/submissions/{submission_sent}", "host", "E"),
    ("apartments-full", "/apartments", "host", "E"),
    ("property-detail", "/apartments/{property_id}", "host", "E"),
    ("account-accept", "/account/accept?token={invite_token}", "anon_invite", "E"),
    # F: guide, questions, Leon (populated)
    ("apt-guide-full", "/apartments/{apt}/guide", "host", "F"),
    ("guide-item", "/apartments/{apt}/guide/{guide_item}", "host", "F"),
    ("guide-questions-full", "/apartments/{apt}/guide/questions", "host", "F"),
    ("guide-question", "/apartments/{apt}/guide/questions/{question_id}", "host", "F"),
    ("guide-quick-done", "/apartments/{apt}/guide/quick/done", "host", "F"),
    ("leon-settings-full", "/apartments/{apt}/leon", "host", "F"),
    ("leon-setup-cards-full", "/apartments/{apt}/leon/setup/cards", "host", "F"),
    ("property-page-review-full", "/apartments/{apt}/page", "host", "F"),
] + [
    (f"guide-quick-{s}", f"/apartments/{{apt}}/guide/quick/{s}", "host", "F")
    for s in GUIDE_QUICK_STEPS
]
# G: variants of existing pages (tabs, filters, months)
VARIANT_CASES = [
    ("reservations-past", "/reservations?filter=past", "host", "G"),
    ("stay-fees-oct", "/stay-fees?month=2026-10", "host", "G"),
    ("invoices-new-picker", "/invoices/new?step=stays", "host", "G"),
    ("settings-tab-account", "/settings?tab=account", "host", "G"),
]
```
   Before writing it: (a) put at the top of the file `GUIDE_QUICK_STEPS = (...)` with the tuple printed by
   `cd App && .venv/bin/python -c "from app import guide_facts; print(guide_facts.STEPS)" 2>&1 | tail -3`;
   (b) add `{guide_item}` and `{question_id}` to the seed output (items 1 and 2) and to `fill()`;
   (c) for each `VARIANT_CASES` query parameter, grep it in the route (`grep -n 'query_params.get("filter"\|"month"\|"tab"\|"step"' App/app/routes/reservations... `): the file is `App/app/routes/admin.py` for `/reservations`, `stay_fees.py`, `invoices.py`, `admin.py` for `/settings`. Replace each query by the real one found; delete a row whose parameter does not exist (one line in the report: "no such variant").
   (d) persona `anon_invite` means no cookie for both stacks (the invite link works signed out); add that branch to `table_cases`.
   Check: `python3 -c "import sys; sys.path.insert(0,'scripts/e2e'); import parity_cases as c; print(len(c.EXTRA_CASES)+len(c.VARIANT_CASES))" | tail -3` (about 30+).
6. Run (timeout 600000 each): `source scripts/e2e/parity_env.sh; cd App && PARITY_GROUP=E .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -12`, then `F`, then `G`. Rows: 17x6, 25+x6, 4x6 at most. If a group times out, re-run with `PARITY_WIDTHS=390,1280`, say so.
   First look at the stderr `skipped` lines of the seed; a skipped block makes the dependent cases `SKIPPED`: try one more fix of the block (one tool call), then go on.
7. Inspect visible/error rows exactly as 2040 step 6 (max 12 image reads; one description per cause; Python on the left, Go on the right). Re-run a suspect row once for one-shot state.
8. Write `docs/tasks/2041-report.md`: totals, all-rows table, skipped seed blocks, visible causes in plain words, errors, not inspected, wall time per group. Then `python3 scripts/context_lint.py 2>&1 | tail -3` and `cd App && .venv/bin/python -m pytest tests/test_go_page_parity_screenshots.py -q --tb=short -x 2>&1 | tail -30`. Commit only the files of section 3: `2041: parity seed extension and populated host pages (report)`.

## 5. Do not touch

`App/app/**`, `go/**`, `scripts/e2e/seed.py`, `page_parity_audit.py`, `App/scripts/go_page_parity_screenshots.py`. No new dependency.

## 6. Commands

```
source scripts/e2e/parity_env.sh
cd App && PARITY_GROUP=E .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -12
python3 scripts/context_lint.py 2>&1 | tail -3
```

## 7. Acceptance

- [ ] `seed_parity_extra.py` prints a JSON with the ids; every skipped block is named in the report.
- [ ] Every case in groups E, F, G has verdicts for cs/en x 390/768/1280, or an explicit SKIPPED/error line with the reason.
- [ ] Report lists every row; each visible cause is described after looking at the side-by-side PNG.
- [ ] `git status --short | tail -10` shows only the section 3 files; `context_lint` passes.

## 8. Stop and ask

- 2040 files missing, the venv or Postgres is not up: stop.
- 25 tool calls used: stop, commit, report which groups are missing.
- A seed block that violates a DB constraint after two tries: skip it (rule in step 3), report it.
- Do not fix visible rows. Do not edit seed.py.
