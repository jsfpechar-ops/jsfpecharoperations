# Billing phase 1: spec 03 checked against the repo

Checked 2026-10-26 against `main` at `1255954`. Source: "Self-service plans and billing (spec v2: invoices first)" and "Pricing page update (/cenik)", both agreed 26 Oct 2026. Phase 1 is invoices only: nothing here is for a card gateway.

Each row says what the spec says, what the code actually has, and how the briefs handle it. Briefs: B1 = [0411](../tasks/0411-billing-core.md), B8 = [0412](../tasks/0412-cenik-calculator.md). B2–B7, B9, B10 are not written yet; rows that land in them are listed so those briefs pick them up.

## Mismatches that would break something

| # | Spec says | Repo has | Fix | Brief |
|---|---|---|---|---|
| 1 | `platform_invoice.owner_user_id INTEGER NOT NULL REFERENCES user_account(id)` | `db.py:685` turns `PRAGMA foreign_keys = ON`, and `retention._delete_workspace` deletes the `user_account` row | The nightly workspace deletion would fail for every host who ever got an invoice, and our invoices must stay 10 years anyway. `owner_user_id` becomes nullable; workspace deletion sets it to NULL (the `snapshot_json` keeps the buyer exactly as printed). Same for `founder_slot` (the slot stays used). `billing_account` is deleted with the workspace. | B1 |
| 2 | VS = the numeric part of `UBY-{year}-{0001}`, `vs UNIQUE` | n/a | `0042` comes back every year, so the second January would hit the UNIQUE constraint. VS = year + 4-digit number (`UBY-2026-0042` → VS `20260042`, 8 digits, fits the 10-digit limit). | B2 (B1 documents it in the migration) |
| 3 | §7: "an invoice for a period is never issued twice (UNIQUE on owner + period + kind)" | §5 schema has no such constraint | Partial unique index on `(owner_user_id, period_from, period_to)` for `kind = 'invoice' AND voided = 0`. A `voided` flag lets a storno'd period be invoiced again. | B1 |
| 4 | Supplementary invoices are `kind = 'supplementary'`, rendered with `invoice_pdf.render` | `invoice_pdf.py:153` only knows `invoice`, `storno`, `corrective`: anything else is a `KeyError` | B2 passes `kind = 'invoice'` to the renderer for a supplementary invoice. | B2 |
| 5 | Seller = `operator.py` identity (name, IČO, address) | `invoice_pdf.render` reads `seller_name`, `seller_seat`, `seller_ico`, `seller_dic`, `seller_iban`, `seller_bank_account`, `seller_bic`, `seller_email`, `vat_status`, `duzp`, `buyer_*` …; `operator.details()` returns `name`, `ico`, `dic`, `address`, `email` | B2 maps `address` → `seller_seat` and fills the bank fields from the new `UBYHOST_BILLING_*` config. | B2 |
| 6 | §3a "Trial (unchanged)": `trial_pending` → `trialing` on "first verified UbyPort connection" | There is no trial in the code at all, and nothing stores "UbyPort verified": only an `ubyport_connection_ok` audit line when someone clicks Test connection (`routes/admin.py:2901`) | B1's migration adds `apartment.ubyport_verified_at`; B3 sets it (successful test connection or first accepted filing) and starts the clock. | B1 (column), B3 |
| 7 | Column `interval` | Rules: SQL must stay Postgres-portable | `interval` is an SQL type keyword. Renamed `billing_interval`. | B1 |
| 8 | `founder_slot.slot CHECK (slot BETWEEN 1 AND 100)` and `UBYHOST_FOUNDER_SLOTS` configurable | n/a | The two disagree as soon as the env var changes. CHECK is `slot >= 1`; the code enforces the cap. | B1 |
| 9 | Downgrades, interval switches and add-on removals apply "from the next period" | §5 has nowhere to keep them | `billing_account.pending_change_json`. Amounts under 50 Kč "added to the next invoice" need `carry_czk`. | B1 |
| 10 | Copy keys use `{amount}`, `{price}`, `{n}` | `host_i18n.lookup` formats with `%`: placeholders are `%(amount)s`; counted words use the `key` / `key.one` / `key.few` plural pattern | B8 writes `%(name)s`. | B8 |
| 11 | /cenik feature line "Online check-in, domovní kniha na 6 let", FAQ 5 "domovní knihu" | Owner decision D-18, guarded by `tests/test_owner_decisions.py:66`: the public term is "ubytovací kniha" / "guest book" | B8 says "ubytovací kniha". | B8 |
| 12 | (not mentioned) | `tests/test_public_seo.py:132-160`, `test_landing_decoration.py:209`, `test_owner_decisions.py:68-69` assert the old "Dle domluvy" page and forbid prices in the JSON-LD | B8 rewrites those tests for the new page. | B8 |

## Gaps and smaller differences

| # | Topic | What we do |
|---|---|---|
| 13 | Hosts who exist today have no `billing_account` row, and the spec doesn't say what happens to them | B1: no row = active Standard, exactly as today, even with billing switched on. New sign-ups get a row from B3. **Josef decides** how current customers move onto a plan (owner step 5). |
| 14 | "Remove/archive an apartment" | There is no archive column: a removed apartment is `apartment.active = 0`. Billing counts `active = 1` rows. |
| 15 | Trial and invoice e-mails via `lifecycle_mail.py` | Mail rule: lifecycle tips cover setup only, "no discounts, pricing". Trial-ending and invoice mails are service mail; B3 sends them outside the lifecycle-tip path. |
| 16 | `/signup?plan=max&interval=year&apts=3` | Sign-up is behind `UBYHOST_SIGNUP_ENABLED` and its link carries attribution (`signup.signup_href`). B8 appends the plan to that link; while sign-up is off the buttons go to `/login`, as today. The sign-up route ignores the plan for now; B4 picks it up. |
| 17 | Founder strip "Zbývá {n} ze 100 míst" on /cenik | The count needs B1's `founder_slot`. B8 runs in parallel, so it shows the strip only when the route passes `founder_left`; wiring that in is two lines in B4. |
| 18 | Price list in one place | B1 puts it in `billing.py`; B8 puts the same numbers in `routes/legal.py` so the two briefs don't touch the same file. B4 replaces B8's copy with an import from `billing.py` and adds a test that they match. |
| 19 | Admin URL | Spec says `/admin/platby` (§6) and `/admin/fakturace` (§8), `routes/admin_billing.py` (B6) and `routes/admin.py` (B5). One page: `/admin/fakturace` in `routes/admin_billing.py`. |
| 20 | 10-year purge of `platform_invoice` and `bank_payment` (spec puts it in B1) | Moved to B2, which owns storno ordering. Nothing reaches 10 years before 2037. B1 adds the RETENTION.md rows. |
| 21 | Design canvas vs 02 copy | The canvas has a few strings 02 doesn't ("−33 %", "Apartmánů", "Mám chytré zámky TTLock"). 02 owns the copy, the canvas owns the layout; the canvas-only strings get their own keys in B8. The Max card's drop shadow is dropped (`test_landing_decoration.py:188` forbids shadows on `.pricing-card`). |
| 22 | "Platba kartou přibude brzy" in both `pricing.pay_note` and FAQ 8; "Bez platební karty" in both the hero chips and `pricing.cta_note` | One explanation in one place: /cenik says the card line in FAQ 8 only (`pricing.pay_note` belongs to the plan picker, B4), and `pricing.cta_note` is just "Zkušební doba začne, až propojíte UbyPort." since the chip already says "Bez platební karty". |

Checked and fine: `invoice_pdf.render`, `payments.spayd`/`qr_png_bytes`, `ares.lookup`, `operator.details`, `lifecycle_mail.py`, `mail.attachments`, `scheduler.py` (APScheduler), `door_codes.py`, `icalsync.py`, `_shell_topbar.html`, `_privacy_first.html`, `routes/legal.py:pricing`, `templates/pricing.html`, `landing_i18n.py`, `landing.css`; next free migration `0023`, next free task `0411`. `static/pricing.js`, `billing.py`, `billing_invoices.py`, `bank_import.py`, `routes/billing.py` and `routes/admin_billing.py` are new files.
