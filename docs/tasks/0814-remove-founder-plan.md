# 0814: Remove the founder plan

Status: todo
Depends on: none | Base commit: 47a5dbe | Branch: task/0814-remove-founder-plan
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The owner dropped the founder plan (890 Kč a year per apartment, first 100 hosts) on 2026-11-02. Remove every price rule, offer, label and legal sentence for it, so every account is priced at list price.

## 2. Context

- New orders stopped getting the founder price on 2026-10-27 (self-service work); billing went live 2026-10-29. Nothing in the code sets `billing_account.founder = 1` or calls `billing.claim_founder_slot`. What is left is dead code, one price branch and copy.
- Schema stays. Goose migrations must be additive (rules: database) and `App/app/migrations/` is frozen. Do **not** drop the `founder` columns or the `founder_slot` table and do not add a migration. Code simply stops reading and writing `founder`; the columns default to 0.
- Keep `retention.py`'s `UPDATE founder_slot SET owner_user_id = NULL ...` line: old staging rows may still hold an owner id. Only change its comment.
- Never edit `docs/plans/**`, old `docs/tasks/**` briefs or reports, migrations, `App/migrations_pg/**`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/billing.py | edit | Drop `FOUNDER_YEAR`, the `founder` arg of `quote`, every `"founder": ...` key passed to `_period_total`, `founder_slots_left`, `claim_founder_slot` |
| App/app/config.py | edit | Drop the `FOUNDER_SLOTS` line and its comment |
| App/app/billing_order.py | edit | Drop `founder_offer`; `quote` no longer passes founder; `place` no longer writes `founder` |
| App/app/billing_invoices.py | edit | `period_items`: no founder arg, no "zakladatelská cena" label |
| App/app/billing_analytics.py | edit | Stop selecting/passing/storing `founder` |
| App/app/routes/admin_customers.py | edit | `_quote_for` drops `founder=` |
| App/app/routes/billing.py | edit | Drop the `"founder_offer": ...` context line |
| App/app/routes/legal.py | edit | Drop the `founder_left` context entry and its comment |
| App/app/templates/billing_plan.html | edit | Drop line 38 and the founder suffix on line 65 |
| App/app/host_i18n.py | edit | Drop `billing.plan.founder` and `billing.order.founder` (EN and CS, 4 lines) |
| App/app/landing_i18n.py | edit | Drop the 3 `pricing.founder.*` keys in EN and CS (6 lines) |
| App/app/static/landing.css | edit | Drop the `.pricing-founder` rules (3 rule blocks) and "and the founder strip" in the comment above them |
| App/app/terms_i18n.py | edit | Drop the founder sentence from §15 EN and CS |
| App/app/retention.py | edit | Comment only: drop "A founder slot stays used." |
| App/scripts/billing_fixtures.py | edit | Drop founder from the product and output |
| App/scripts/export_billing_analytics.py | edit | Drop `founder` from `ACCOUNT_SQL` and the quote call |
| go/internal/billing/quote.go | edit | Drop `founderYear`, the `founder bool` param and its branch |
| go/internal/billing/snapshot.go | edit | Stop selecting, scanning, passing and writing founder |
| go/internal/billing/quote_test.go | edit | Drop the `Founder` field and argument |
| go/internal/billing/snapshot_test.go | edit | Account 1 becomes plain Standard yearly |
| go/internal/billing/testdata/quote_fixtures.json | regenerate | From the script |
| App/tests/test_billing_core.py | edit | See step 9 |
| App/tests/test_billing_invoices.py | edit | Delete `test_founder_line_on_an_annual_plan` |
| App/tests/test_billing_order.py | edit | See step 9 |
| App/tests/test_billing_self_service.py | edit | See step 9 |
| docs/ENVIRONMENT.md | edit | Drop the `UBYHOST_FOUNDER_SLOTS` row |
| docs/context/status.md | edit | Drop the "founder-price flag" line under Blocked |

No other file may change. `test_signup_selection.py`, `test_0412_pricing_browser.py` and the `pricing-founder` absence check in `test_billing_order.py` stay as they are (they assert the offer is gone).

## 4. Steps

1. **billing.py.** Delete `FOUNDER_YEAR = 890`. In `quote`, delete the `founder: bool = False,` parameter and replace
   ```python
       if founder and interval == "year":
           base = FOUNDER_YEAR * n
       else:
           base = graduated(n, BASE[interval])
   ```
   with `    base = graduated(n, BASE[interval])`. In `_period_total` delete `founder=bool(state["founder"]),`. Delete the three dict entries `"founder": acc["founder"],` / `"founder": refreshed["founder"],` (inside `apply_change` and the discount function; one shares a line with `"addon_whitelabel"`; remove only the founder part). Delete the functions `founder_slots_left` and `claim_founder_slot` completely. `grep -n founder App/app/billing.py` must print nothing. If `Optional` is now unused, leave the import alone.
2. **config.py.** Delete the two lines `# How many hosts can get the founder price.` and `FOUNDER_SLOTS = ...`.
3. **billing_order.py.** Delete `founder_offer`. `quote` becomes:
   ```python
   def quote(owner_user_id: int, values: Dict[str, Any]) -> Dict[str, int]:
       return billing.quote(
           apartments(owner_user_id), values["plan"], values["billing_interval"],
           ttlock=values["addon_ttlock"],
           whitelabel=bool((billing.account(owner_user_id) or {}).get("addon_whitelabel")),
       )
   ```
   In `place` delete `founder = 1 if acc["founder"] else 0`, remove `founder = ?, ` from the UPDATE string, and remove `founder, ` from the parameter tuple (it sits between `int(acc["addon_whitelabel"]),` and `apartments(owner_user_id),`). Count: placeholders and values must still match.
4. **billing_invoices.py** `period_items`: delete the `founder = ...` line, the `founder=founder,` arg and the two lines `if founder:` / `label += ", zakladatelská cena"`.
5. **billing_analytics.py**: in `portfolio` SQL remove `b.founder, `; in the quote call delete `founder=bool(r["founder"]),`. In the snapshot INSERT remove `founder, ` from the column list, one `?, ` from VALUES (14 → 13), `"founder = excluded.founder, "` → keep `"discount_percent = excluded.discount_percent, "` on that line, and `int(bool(c["founder"])), ` from the tuple. Then `grep -n founder App/app/billing_analytics.py` must print nothing. If `portfolio` builds a customer dict with `founder=bool(r["founder"])` (around line 61), delete that entry too.
6. **Routes, template, i18n, CSS.** admin_customers.py: delete `founder=bool(customer.get("founder")),`. routes/billing.py: delete the `"founder_offer": ...` line. routes/legal.py: delete the `# 0416: places left ...` comment and the `"founder_left": ...` line. billing_plan.html: delete line 38 (`{% if founder_offer %}...{% endif %}`) and change line 65 to `(t('billing.plan.fact.plan'), t('billing.plan.name.' ~ acc.plan)),`. host_i18n.py and landing_i18n.py: delete the keys listed in §3. landing.css: delete `.pricing-founder { ... }`, `.pricing-founder h3 {...}`, `.pricing-founder p {...}` and the blank line after them; in the comment above (around line 945) change "the two plan cards and the founder strip need" to "the two plan cards need".
7. **terms_i18n.py.** EN §15: the string ends `"Operator may change prices for future billing periods with at least 30 days' notice. A "` / `"founder price, where granted, stays for as long as the Host keeps the yearly plan without "` / `"interruption."`. Make it end `"Operator may change prices for future billing periods with at least 30 days' notice."` (delete the next two lines). CS: change `"oznámením nejméně 30 dní předem. Zakladatelská cena, byla-li přiznána, platí, dokud "` / `"Ubytovatel bez přerušení pokračuje v ročním plánu."` to the single line `"oznámením nejméně 30 dní předem."`. Do not change `TERMS_VERSION`.
8. **retention.py, scripts, Go, docs.** retention.py comment: `# link (snapshot_json keeps the buyer as printed).` export_billing_analytics.py: remove `founder, ` from `ACCOUNT_SQL` and the `founder=bool(account["founder"]),` arg. billing_fixtures.py: remove `founder` from the loop names, one `(False, True),` from the product (the third one), the `founder=founder,` arg and the `"founder": founder,` key. quote.go: delete `const founderYear = 890`, the `founder bool` param (signature becomes `Quote(apartments int, plan, interval string, ttlockOn, whitelabelOn bool, discountPercent int)`), and replace the `var b int` / if-else with `b := graduated(n, base[interval])`. snapshot.go: remove `b.founder, ` from `portfolioSQL`; from `insertSnapshotSQL` remove `founder,` from the columns, `$14` (renumber is not needed: drop `founder` and shift to `$1`…`$13`), and the `founder = excluded.founder, ` text; remove the `founder` struct field, the `founder` scan var and its `&founder,` and `a.founder = ...` lines, the `a.founder` arg to `Quote`, and `flag(a.founder), ` from Exec. quote_test.go: drop the `Founder` field and `c.Founder, `. snapshot_test.go: username `'founder'` → `'yearly'`; comment → `// Standard yearly: 3 apartments x 1190 = 3570, monthly 3570/12 = 297.5 -> 298 (half to even).`; in the INSERT row for account 1 change `0, 0, 1, 0, 0,` to `0, 0, 0, 0, 0,`; `want` for 1 becomes `{3570, 3570, 298}`. Regenerate fixtures: `cd App && .venv/bin/python scripts/billing_fixtures.py 2>&1 | tail -5`. ENVIRONMENT.md: delete the `UBYHOST_FOUNDER_SLOTS` row. status.md: delete the line `- Decide with owner: founder-price flag on the customer page or discount-% only.` and add under Now: `- 2026-11-02: founder plan removed (0814). Schema keeps the unused founder column and founder_slot table.`
9. **Tests.**
   - test_billing_core.py: rename `test_addons_and_founder_price` to `test_addons_price` and delete its two `founder=True` asserts. Delete `test_founder_slots_are_claimed_once_and_capped` entirely. In `test_deleting_the_workspace_keeps_our_invoices` delete `slot = billing.claim_founder_slot(owner)` and the last three lines (`used = ...`, `assert used ...`, `db.execute("DELETE FROM founder_slot ...`). Update the module docstring: `"""Brief 0411: billing core. Prices, entitlements, changes, deletion."""`. Keep the fixture's `DELETE FROM founder_slot` line.
   - test_billing_invoices.py: delete `test_founder_line_on_an_annual_plan`.
   - test_billing_order.py: in `test_ordering_in_the_trial_waits_for_its_end` replace the two-line `assert acc["founder"] == (...)` with `assert acc["founder"] == 0`.
   - test_billing_self_service.py: replace both founder tests with:
     ```python
     def test_annual_order_is_at_list_price(owner):
         assert signup.activate(_pending(owner))
         values = _order()
         assert billing_order.quote(owner, values)["base"] == billing.BASE["year"][0]
         assert billing_order.place(owner, values)["invoice_id"] is None
         assert billing.account(owner)["founder"] == 0


     def test_legacy_founder_flag_is_ignored(owner):
         assert signup.activate(_pending(owner))
         db.execute("UPDATE billing_account SET founder = 1 WHERE owner_user_id = ?", (owner,))
         values = _order()
         assert billing_order.quote(owner, values)["base"] == billing.BASE["year"][0]
     ```
     Update the module docstring to `"""Activation trial boundaries and list-price orders."""`. If `config` or `monkeypatch` becomes unused, remove only that import.
10. Run §6. Commit after each step (`0814 step k`).

## 5. Do not touch

`App/app/migrations/`, `App/migrations_pg/`, `App/app/db.py`, `TERMS_VERSION`, `docs/plans/**`, other briefs and reports. AGENTS.md hard rules 3, 5, 8.

## 6. Commands

```
grep -rn -i "founder\|zakladatel" App/app go --include=*.py --include=*.go --include=*.html --include=*.css 2>&1 | tail -30
```
Expected: only `retention.py` (`UPDATE founder_slot ...`) and the two `founder` lines in `migrations/0023_billing.sql` / `0031_...sql` (sql is not in the include list, so none) remain.
```
cd App && .venv/bin/python -m pytest tests/test_billing_core.py tests/test_billing_invoices.py tests/test_billing_order.py tests/test_billing_self_service.py tests/test_billing_admin.py -q --tb=short -x 2>&1 | tail -30
cd go && go vet ./internal/billing/ 2>&1 | tail -10 && go test ./internal/billing/ 2>&1 | tail -10
python3 scripts/context_lint.py 2>&1 | tail -10
```
If `tests/test_billing_admin.py` does not exist, drop it from the command. The Go snapshot test may skip without a Postgres URL; that is fine for it only.

## 7. Acceptance

- [ ] The grep in §6 shows only the retention line.
- [ ] Billing tests pass; `go test ./internal/billing/` passes.
- [ ] Terms §15 EN and CS end at the 30-day notice sentence.
- [ ] No migration file added or changed.

## 8. Stop and ask

As in TEMPLATE: excerpt not found, a test fails twice, 25 tool calls / 50k tokens, a file outside §3, a step unclear, push/merge/deploy needed.

## 9. Report

`docs/tasks/0814-report.md`, 600 tokens at most, then `Status: review`.

## Risk list (for the reviewer)

billing.py, billing_order.py (`place` UPDATE placeholders), billing_analytics.py and snapshot.go (INSERT column/value counts), terms_i18n.py.

## Owner steps

1. Before deploying, check production has no founder account: on the server run
   `psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM billing_account WHERE founder = 1;"` (expect 0).
   If it is not 0, do not deploy; tell the thread.
2. Merge the PR, deploy as usual.
3. Optional: remove `UBYHOST_FOUNDER_SLOTS` from the server `.env` if it is set.
