# 0848: Stay fee list: "confirm all ready", "download all PDFs" and the copy-setup card

Status: todo
Depends on: PR #707 merged (read `stay_fees.html` from main after it, never from older main), 0844, 0845, 0846, 0847 merged | Base commit: main after all | Branch: task/0848-stay-fees-speed-page
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

On `/stay-fees` (v2 page from #707), show: one box with **Confirm all ready (N)** when 2 or more periods are ready and **Download all PDFs (N)** when 2 or more are saved; and, for each property without a fee whose municipality matches a configured one, a card with that setup's values and **Use this setup**. Monthly filing for N properties goes from 1 + 3N taps to 5; a second property's fee setup from 2 taps + 4 typed to 1 tap.

## 2. Context

- Routes exist: `POST /stay-fees/confirm-ready` (0845, fields `_csrf`, `month`, `return_to`, repeated `apartment_id`), `GET /stay-fees/pdfs.zip?month=` (0846), `POST /stay-fees/{id}/copy-setup` (0847, fields `_csrf`, `source_id`, `return_to`). Unset rows carry `period.copy_from` (a source apartment row or `None`).
- The two-step card from #707/0630 stays exactly as it is (one primary button per card; no sent/paid marks). The bulk box is its own card above the property cards. The bulk confirm asks once (`data-confirm`, the same pattern as the invoice issue button in `invoice_form.html`): the figures are on each card below it.
- No fine print: only labels, values and buttons; help stays in the existing "?" (`ui-how`). 12 px neighbour rule: buttons in the new boxes have `gap:12px`; text 16 px from card edges.
- Template anchors, `App/app/templates/stay_fees.html` on main after #707 (each once):
  - A: `{% set pay_rows = periods | rejectattr('unset') | list %}`
  - B: `{% set fee_list = namespace(all_unset=true) %}`
- Variables in the template: `csrf_token`, `fee_return`, `selected_month`, `fee_settings_url(apartment_id, fee_return)`.
- Reused keys (exist): `stay_fees.col.period`, `apartment.form.stay_fee.rate_label`, `stay_fees.rate_line` (`%(rate)s`), `apartment.form.stay_fee.cadence.monthly` / `.quarterly`, `stay_fees.payment.vs`, `stay_fees.payment.account`, `apartment.form.stay_fee.authority_name_label`, `stay_fees.send.databox`. New keys (0844): `stay_fees.bulk.label`, `stay_fees.bulk.confirm`, `stay_fees.bulk.confirm_ask`, `stay_fees.bulk.pdfs`, `stay_fees.copy.label`, `stay_fees.copy.title`, `stay_fees.copy.use`, `stay_fees.copy.other`.
- CSS: `App/app/static/app2.css`, after the line `/* 0794 stay fees v2 (end) */`. A changed static file needs a new `?v=` key in `App/app/templates/base.html` (`app2.css?v=...`, find it with `grep -n 'app2.css?v=' app/templates/base.html`) and `.venv/bin/python tests/test_static_versions.py --write`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/stay_fees.html` | edit | Bulk box (anchor A), copy cards (anchor B) |
| `App/app/static/app2.css` | edit | New `0848` block only |
| `App/app/templates/base.html` | edit | app2.css key only |
| `App/tests/static_versions.json` | regenerate | `--write` |
| `App/tests/test_stay_fees_speed_page_0848.py` | new | HTML tests |
| `docs/tasks/0848-report.md` | new | Report |

No other file may change.

## 4. Steps

1. Directly below anchor A insert:
```jinja
{% set fee_bulk = namespace(ready=[], saved=0) %}
{% for period in pay_rows %}{% if period.status == 'ready' %}{% set fee_bulk.ready = fee_bulk.ready + [period.apartment.id] %}{% elif period.status == 'saved' %}{% set fee_bulk.saved = fee_bulk.saved + 1 %}{% endif %}{% endfor %}
{% if fee_bulk.ready | length > 1 or fee_bulk.saved > 1 %}
<section class="card fee-bulk" aria-label="{{ t('stay_fees.bulk.label') }}">
  {% if fee_bulk.ready | length > 1 %}
  <form method="post" action="/stay-fees/confirm-ready">
    <input type="hidden" name="_csrf" value="{{ csrf_token }}">
    <input type="hidden" name="month" value="{{ selected_month.strftime('%Y-%m') }}">
    <input type="hidden" name="return_to" value="{{ fee_return }}">
    {% for apartment_id in fee_bulk.ready %}<input type="hidden" name="apartment_id" value="{{ apartment_id }}">{% endfor %}
    <button class="btn" type="submit" data-confirm data-confirm-message="{{ t('stay_fees.bulk.confirm_ask') }}">{{ t('stay_fees.bulk.confirm', count=fee_bulk.ready | length) }}</button>
  </form>
  {% endif %}
  {% if fee_bulk.saved > 1 %}
  <a data-turbo="false" class="btn ghost" href="/stay-fees/pdfs.zip?month={{ selected_month.strftime('%Y-%m') }}" download>{{ t('stay_fees.bulk.pdfs', count=fee_bulk.saved) }}</a>
  {% endif %}
</section>
{% endif %}
```
   Commit `0848 step 1`.
2. Directly above anchor B insert:
```jinja
{% for period in periods %}{% if period.unset and period.copy_from %}
{% set target = period.apartment %}{% set source = period.copy_from %}
<section class="card fee-copy" id="fee-copy-{{ target.id }}" aria-label="{{ t('stay_fees.copy.label') }}">
  <div class="fee-pay-h">
    <h2>{{ target.internal_name }}</h2>
    <span class="sub">{{ t('stay_fees.copy.title', name=source.internal_name) }}</span>
  </div>
  <dl class="fee-figures">
    <div><dt>{{ t('apartment.form.stay_fee.rate_label') }}</dt><dd>{{ t('stay_fees.rate_line', rate=source.stay_fee_rate_czk) }}</dd></div>
    <div><dt>{{ t('stay_fees.col.period') }}</dt><dd>{{ t('apartment.form.stay_fee.cadence.quarterly' if source.stay_fee_cadence == 'quarterly' else 'apartment.form.stay_fee.cadence.monthly') }}</dd></div>
    {% if source.stay_fee_vs %}<div><dt>{{ t('stay_fees.payment.vs') }}</dt><dd>{{ source.stay_fee_vs }}</dd></div>{% endif %}
    {% if source.stay_fee_council_account or source.stay_fee_council_iban %}<div><dt>{{ t('stay_fees.payment.account') }}</dt><dd>{{ source.stay_fee_council_account or source.stay_fee_council_iban }}</dd></div>{% endif %}
    {% if source.stay_fee_authority_name %}<div><dt>{{ t('apartment.form.stay_fee.authority_name_label') }}</dt><dd>{{ source.stay_fee_authority_name }}</dd></div>{% endif %}
    {% if source.stay_fee_authority_databox %}<div><dt>{{ t('stay_fees.send.databox') }}</dt><dd>{{ source.stay_fee_authority_databox }}</dd></div>{% endif %}
  </dl>
  <form method="post" action="/stay-fees/{{ target.id }}/copy-setup" class="fee-step-actions">
    <input type="hidden" name="_csrf" value="{{ csrf_token }}">
    <input type="hidden" name="source_id" value="{{ source.id }}">
    <input type="hidden" name="return_to" value="{{ fee_return }}">
    <button class="btn" type="submit">{{ t('stay_fees.copy.use') }}</button>
    <a class="btn ghost" href="{{ fee_settings_url(target.id, fee_return) }}">{{ t('stay_fees.copy.other') }}</a>
  </form>
</section>
{% endif %}{% endfor %}
```
   Commit `0848 step 2`.
3. CSS: first `grep -n 'fee-pay{\|\.fee-pay ' app/static/app2.css | head -5` and note the margin rule of `.fee-pay` in the 0794 block. Directly below `/* 0794 stay fees v2 (end) */` insert (replace `<M>` with that margin value, or `0 0 16px` if none):
```css
/* 0848 stay fee speed (start) */
body.v2 .stay-fees-page .fee-bulk{display:flex;flex-wrap:wrap;align-items:center;gap:12px;padding:16px;margin:<M>}
body.v2 .stay-fees-page .fee-bulk form{margin:0}
body.v2 .stay-fees-page .fee-copy{padding:16px;margin:<M>}
body.v2 .stay-fees-page .fee-copy .fee-step-actions{display:flex;flex-wrap:wrap;gap:12px;margin-top:16px}
/* 0848 stay fee speed (end) */
```
   Bump the `app2.css?v=` key to `20261103-0848`, then `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`. Commit `0848 step 3`.
4. New `App/tests/test_stay_fees_speed_page_0848.py`. Fixture: copy the one from `tests/test_stay_fee_bulk_0845.py` with prefix `stay-fee-speed-` (today 2026-09-30). Tests (TestClient, `?lang=en`):
   - `test_two_ready_show_one_confirm_all`: two ready properties; `GET /stay-fees?month=2026-08`: exactly one `action="/stay-fees/confirm-ready"`, two `name="apartment_id"` inputs with the two ids, `Confirm all ready (2)`, `data-confirm`. No `pdfs.zip` link.
   - `test_one_ready_shows_no_bulk_box`: one ready property: no `fee-bulk`.
   - `test_two_saved_show_download_all`: seal both through `/stay-fees/confirm-ready`; the page has `href="/stay-fees/pdfs.zip?month=2026-08"` and `Download all PDFs (2)`, no confirm-ready form.
   - `test_unset_sibling_shows_the_copy_card`: source with fee in `Praha 3`, target `addr_obec="Praha 3"` rate 0: page has `id="fee-copy-<target>"`, the source VS and `Use this setup`; a target in `Brno` gets no card.
   - `test_bulk_box_posts_end_to_end`: post the form the page rendered (parse the `apartment_id` values from the HTML) and assert both filings exist.
   Run §6 command 1. Commit `0848 step 4`.
5. Run §6 commands 2-4. If a v2 geometry finding names `.fee-bulk` or `.fee-copy`, fix it only inside the 0848 CSS block (bump the key again with suffix `b`). Commit.
6. Screenshot (no test file change): run `UBYHOST_SHOTS_V2=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k screenshots -q 2>&1 | tail -5` and copy `docs/tasks/screenshots-0710/stay_fees-390.png` to `docs/tasks/screenshots-0848/stay-fees-390.png`. If the rich fixture shows no bulk box, say so in the report; 0854 takes the seeded screenshot.

## 5. Do not touch

The two-step card markup, `stay_fee_detail.html`, routes, locale files, other CSS blocks, `App/tests/v2_mockup.py`. No JS. Light mode only.

## 6. Commands

From `App/`:
1. `.venv/bin/python -m pytest tests/test_stay_fees_speed_page_0848.py -q --tb=short -x 2>&1 | tail -30`
2. Row: `.venv/bin/python -m pytest tests/test_invoice_*.py tests/test_stay_fee*.py tests/test_fee_*.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`
3. v2 row: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k stay_fees -q --tb=short -rs 2>&1 | tail -30` (0 skipped)
4. Host row: `.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q --tb=short -x -rs 2>&1 | tail -30` (0 skipped)

## 7. Acceptance

- [ ] Bulk box only with 2+ ready or 2+ saved; one confirm question; lists exactly the ready ids.
- [ ] Copy card only for unset properties with a same-place source; shows the values it will save.
- [ ] Commands 1-4 pass, 0 skipped.
- [ ] `docs/tasks/screenshots-0848/stay-fees-390.png` exists.

## 8. Stop and ask

Stop, and write the report, if an anchor is not found (the page may still be the pre-#707 version: STOP, do not work on it); a test fails twice; you reach 25 tool calls or about 50k tokens; a file outside §3 needs a change; you need push, merge, secrets, SSH or deploy.

## 9. Report

`docs/tasks/0848-report.md` (500 tokens at most), `Status: review`: files, command tails, §7 ticked, the screenshot path.

## Risk list (for the reviewer)

`App/app/templates/stay_fees.html` (hidden `apartment_id`s are only the ready rows), `App/app/static/app2.css` (only the 0848 block).

## Owner steps

1. Look at the 390 px screenshot, then merge with `scripts/merge-pr-on-green.sh <pr>` when CI is green.
