# 0843: Faster stay fee, invoices and records: index of briefs 0844-0849 and 0888-0890

Status: todo (index only: run the briefs it lists, never this file)
Owner goal (Josef, 2026-11-02): filing the stay fee much faster; the same for Faktury, Odeslání and Domovní kniha.
Author: Opus brief author, from code on main `89a08e1` and PR #707 head `192a674`.

## 1. Objective

Cut taps and typed fields in the monthly stay fee filing, the first fee setup, stay invoices and the housebook export, without changing what is filed. This file is the index: it holds the counts, the run order and the owner questions; the work is in 0844-0890.

## 2. Context

### What is already fast (no brief)

- Stay fee: the daily job seals clean periods from the 2nd to the 15th day after the period (`stay_fee_auto.run`, hosts with fee e-mails on), so many hosts only download and send. #707 (0630/0794) makes the card two steps with PDF, datová schránka and QR in one box, and removes the sent/paid marks.
- Invoice: due date (issue date + the operator's `invoice_due_days`), DUZP = today, VAT 12 %, "already paid" are defaults already. ARES is click-only and stays so.
- Odeslání: all receipts are one tap (`/submissions/receipts.zip`); a single receipt is 2 (row menu). No change: nothing to cut without touching police data.

### Taps and typed fields (counted from templates and routes, 390 px)

| Flow | Before | After (target) | Briefs |
|---|---|---|---|
| Stay fee, month, 1 property | 4 taps (open, Ano sedí, PDF, datová schránka), 0 typed | 4 taps (unchanged, already minimal after #707) | #707 |
| Stay fee, month, 3 properties | 10 taps (1 + 3 per property) | 5 taps (open, confirm all, confirm, ZIP, datová schránka); stays 5 for any N | 0845, 0846, 0848 |
| Stay fee setup, 2nd property in the same municipality | 2 taps + 4 required typed (rate, VS, account, council) + up to 3 optional | 1 tap ("Use this setup"), 0 typed, values shown first | 0847, 0848 |
| Stay fee setup, first property | 2 taps + 4-7 typed | unchanged (see question 1 on a council list) | none |
| Invoice for a stay (guest complete, repeat property) | 9 taps + 1 typed (New, select, option, Continue, fill from guest, price field, type, Issue, confirm), +2 if paid via Airbnb/cash | 5 taps + 0 typed (New, stay, Use last price, Issue, confirm) | 0836 (#734), 0849, 0888 |
| Invoice, first on a property | 9 taps + 1 typed | 6 taps + 1 typed (price typed once) | 0836, 0849 |
| Domovní kniha, last month's guest PDFs | 5 taps + 2 typed (Filters, from, to, Apply, Export, PDF, Download) | 4 taps + 0 typed (Last month, Export, PDF, Download) | 0889 |
| Odeslání, receipts | 1 tap (ZIP) | 1 tap | none |

The external part (upload to datová schránka, bank payment by QR) is outside the app and is not counted. 0890 measures the "after" column in a browser; 0841 (#734) gives the general flow recorder.

## 3. Files

The briefs below; each lists its own files. No brief in this set shares a file with another except where the run order says so.

## 4. Steps

Run order:

| # | Brief | Files (exclusive within this set) | Runs after |
|---|---|---|---|
| 0844 | [copy keys](0844-speed-copy-keys.md) | `host_i18n.py`, `host_vi_i18n.py` | #707 merged |
| 0845 | [confirm all ready (route)](0845-stay-fee-confirm-all-ready.md) | `routes/stay_fees.py`, `stay_fee_auto.py`, new test | 0844 |
| 0846 | [all PDFs as ZIP (route)](0846-stay-fee-all-pdfs-zip.md) | `routes/stay_fees.py`, test | 0845 |
| 0847 | [copy fee setup (route)](0847-stay-fee-copy-setup.md) | `routes/stay_fees.py`, new test | 0846 |
| 0848 | [stay fee page controls](0848-stay-fees-speed-page.md) | `stay_fees.html`, `app2.css` (own block), `base.html` key | 0847, **#707** |
| 0849 | [invoice picker one tap](0849-invoice-picker-one-tap.md) | `routes/invoices.py` (`_stay_options`, picker branch), `invoice_stay_picker.html`, `host2.css` block, `base.html` key | 0844; after 0836 if open |
| 0888 | [last price + paid-via remembered](0888-invoice-price-and-payment-defaults.md) | `routes/invoices.py` (below price hint), `invoice_form.html`, `host2.css` block, `base.html` key | 0849, 0836 |
| 0889 | [housebook presets](0889-housebook-period-presets.md) | `housebook.py`, one line in `routes/admin.py`, `housebook.html`, `app2.css` block, `base.html` key | 0844, **#707**; merge after 0848 |
| 0890 | [browser, 7 widths, screenshots](0890-speed-pages-browser-shots.md) | new test + screenshots only | all above |

0850 and 0851 are taken by #707. Three lanes can run in parallel after 0844: stay fee (0845 > 0846 > 0847 > 0848), invoices (0849 > 0888), housebook (0889). Briefs that touch `base.html` keys merge one at a time; the later one rebases and reruns `tests/test_static_versions.py --write`.

**Template edits wait for #707.** `stay_fees.html` and `housebook.html` must be read from main after #707 merges (or from its head `claude/project-thread-v4nqi5`), never from older main; their briefs stop if the #707 anchors are missing. Route and logic briefs (0845-0847, 0849) are free of #707 conflicts except that #707 also edits `routes/stay_fees.py` (removes the sent/paid routes), so 0845 starts after #707 too.

## 5. Do not touch

Coordination with other open work:

- **#734 (0836-0841, "Halve the taps"):** 0836 prefills the invoice buyer from the lead guest and owns `_form_context`'s buyer lines; 0849/0888 build on it and never touch them. 0837/0840 own `reservations.html` (stay row actions), so an "invoice" button on the stay row is left out here. 0841 owns the generic tap recorder.
- **#707 (records pages v2, 0790-0799, 0850-0851):** owns the look of `/stay-fees`, `/invoices`, `/housebook`, `/submissions`, the two-step stay fee box and the removal of sent/paid marks. These briefs only add new blocks to those templates and new CSS blocks.
- **Guest/Company switch on the invoice form (no wizard), Josef 2026-11-02:** owned by the "Halve the taps in core flows" thread (invoice buyer prefill, 0836 area). These briefs do not build it; 0849 and 0888 must not touch the buyer block in `invoice_form.html`.
- Hard limits kept: PIN untouched; no autosave (every value is shown and saved only on a tap); filed amounts unchanged (0845 asserts bulk = single = `check()` total; 0846 asserts byte-identical PDFs); no new dependency (`zipfile`, `io` are standard library); no new personal-data field (no `retention.py` line); SQL through `db.py`; no migration; light mode; no fine print; ARES click-only; no Money merge; no accent change.

## 6. Commands

From the repo root after each brief lands: `python3 scripts/context_lint.py 2>&1 | tail -30`. Each brief names its own test-map rows.

## 7. Acceptance

- [ ] 0890's report shows the "after" column of the tap table reached.
- [ ] 0845 and 0846 equality tests are green (filed amounts and PDFs unchanged).

## 8. Stop and ask

Owner decisions needed before the named brief runs:

1. **Copy the variable symbol with the fee setup (0847)?** Some councils give each facility its own VS. Recommended: copy it and show it on the card before "Use this setup"; the host can choose "Set up differently".
2. **One confirm dialog for "Confirm all ready" (0848)?** The single "Ano, sedí" has none. Recommended: keep the one dialog for the bulk action.
3. **DUZP default for stay invoices:** today (now) or the stay's departure date? Not changed in these briefs; it needs your or your accountant's answer first.

## 9. Report

No report for this index; each brief writes its own `NNNN-report.md`.
