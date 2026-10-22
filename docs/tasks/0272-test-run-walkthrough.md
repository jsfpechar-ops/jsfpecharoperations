# 0272: The test run shows the whole story (C, part 2)

Status: todo
Depends on: 0271 | Base commit: 48c21b3 + 0270, 0271 | Branch: claude/project-thread-4b2e7k (commit here, do not push)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The wizard's last step is now the test run. After the host fills in the guest form as their own guest, the step shows the five workflow steps for this property, each with what just happened or what a real stay would do next (email, police report in the host's chosen mode, door code or confirmation). Hosts finally see the end of the story before their first real guest.

## 2. Context

- Demo stays never go to the police and send no email (owner: no new emails). The walkthrough only says what a real stay would do; it sends nothing.
- `workflow_steps(apartment)` is a Jinja global (from `workflow.steps`) returning five dicts `{"n", "key", "who"}`; keys are `paste`, `form`, `email`, one of `police_manual|police_scheduled|police_immediate|police`, and `finish|finish_lock`. Their titles are `t('workflow.step.' ~ key)`.
- The try_it context already has `setup_demo` (state `none|open|registered`), `apartment` (with `automation_mode`, `submit_after_hours`) and `setup_sweep_minutes`.
- Styles go in a NEW file `App/app/static/wizard.css` that this brief creates and links (other threads edit host2.css; keep out of it). Later briefs append to it. Lint rules: no bare px in margin/padding/gap/radius/font-size, no raw colours; borders visible.

Excerpt `App/app/templates/setup_wizard/try_it.html` lines 36-41:

```
{% if demo_state == 'registered' %}
<p class="setup-wizard-lede">{{ t('setup_guide.try.registered_text') }}</p>
{% elif demo_state == 'open' %}
<p class="setup-wizard-instruction" data-wizard-demo-wait>{{ t('wizard.try_it.waiting') }}</p>
{% endif %}
{% endblock %}
```

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/setup_wizard/try_it.html | edit | walkthrough list |
| App/app/static/wizard.css | create | list styles |
| App/app/templates/base.html | edit | link wizard.css |
| App/app/host_i18n.py | edit | EN + CS block |
| App/app/host_vi_i18n.py | edit | VI block |
| docs/design/catalog.json | edit | legacy classes for try_it.html; wizard.css in enforced_stylesheets |
| App/tests/static_versions.json | regenerate | |
| App/tests/test_test_run_0272.py | create | tests |

No other file may change.

## 4. Steps

**Step 1.** In `try_it.html` replace the line `<p class="setup-wizard-lede">{{ t('setup_guide.try.registered_text') }}</p>` with:

```
<section class="setup-rehearsal" aria-labelledby="rehearsal-title" data-rehearsal>
  <h2 id="rehearsal-title">{{ t('wizard.rehearsal.title') }}</h2>
  <ol class="setup-rehearsal-steps">
    {% for step in workflow_steps(apartment) %}
    {% set real = step.n <= 2 %}
    <li class="{{ 'is-done' if real else 'is-test' }}" data-rehearsal-step="{{ step.key }}">
      <span class="workflow-num" aria-hidden="true">{% if real %}✓{% else %}{{ step.n }}{% endif %}</span>
      <span class="setup-rehearsal-copy">
        <strong>{{ t('workflow.step.' ~ step.key) }}</strong>
        <span>{% if step.key == 'police_scheduled' %}{{ t('wizard.rehearsal.police_scheduled', hours=apartment.submit_after_hours or 24) }}{% elif step.key == 'police_immediate' %}{{ t('wizard.rehearsal.police_immediate', minutes=setup_sweep_minutes) }}{% else %}{{ t('wizard.rehearsal.' ~ step.key) }}{% endif %}</span>
      </span>
      <span class="ui-badge ui-badge-{{ 'done' if real else 'neutral' }}" data-tone="{{ 'green' if real else 'grey' }}">{{ t('wizard.rehearsal.badge_done') if real else t('wizard.rehearsal.badge_test') }}</span>
    </li>
    {% endfor %}
  </ol>
  <p class="setup-wizard-instruction">{{ t('wizard.rehearsal.never_police') }}</p>
</section>
```

**Step 2.** Create `App/app/static/wizard.css`:

```
/* 0272: the test run walkthrough (C). Wizard-only styles live in this file. */
.host-workspace .setup-rehearsal { margin: var(--space-5) 0 0; }
.host-workspace .setup-rehearsal > h2 { margin: 0 0 var(--space-3); font-size: var(--text-md); line-height: 1.3; }
.host-workspace .setup-rehearsal-steps { display: grid; gap: var(--space-2); margin: 0 0 var(--space-3); padding: 0; list-style: none; }
.host-workspace .setup-rehearsal-steps > li { display: flex; align-items: flex-start; gap: var(--space-3); min-width: 0; padding: var(--space-3) var(--space-4); border: 1px solid var(--border); border-radius: var(--radius-lg); background: var(--surface); }
.host-workspace .setup-rehearsal-steps > li.is-done { border-color: var(--green-300); }
.host-workspace .setup-rehearsal-steps > li.is-done .workflow-num { border-color: var(--green-700); background: var(--green-700); color: var(--surface); }
.host-workspace .setup-rehearsal-copy { display: grid; gap: var(--space-1); flex: 1 1 auto; min-width: 0; font-size: var(--text-sm); line-height: 1.4; overflow-wrap: anywhere; }
.host-workspace .setup-rehearsal-copy > span { color: var(--ink-secondary); }
.host-workspace .setup-rehearsal-steps .ui-badge { flex: 0 0 auto; }
@media (max-width: 599px) { .host-workspace .setup-rehearsal-steps > li { flex-wrap: wrap; } .host-workspace .setup-rehearsal-steps .ui-badge { margin-left: calc(28px + var(--space-3)); } }
```

The `calc(28px + …)` is in `margin-left`; the lint forbids bare px in margin. Write it as `margin-left: calc(var(--space-8) - var(--space-1))` instead (`--space-8` exists).

**Step 3.** In `App/app/templates/base.html`, after the line containing `/static/workflow.css?v=`, add `  <link rel="stylesheet" href="/static/wizard.css?v=20261022-0272">`.

**Step 4.** i18n. After the LAST `for _lang, _strings in _…_STRINGS.items():` block in `host_i18n.py` add a block `_TEST_RUN_0272_STRINGS` (same shape as the earlier blocks):

| key | en | cs |
|---|---|---|
| wizard.step.try_it | Test run | Zkušební běh |
| wizard.summary.try_it | Test run | Zkušební běh |
| why.try | Last step: a test run. Be your own guest: open the link in the message, type the PIN and fill in the form with made-up details. Then see what happens next. Nothing goes to the police, and you can delete the test stay afterwards. | Poslední krok: zkušební běh. Buďte sami sobě hostem: otevřete odkaz ze zprávy, zadejte PIN a vyplňte formulář smyšlenými údaji. Pak uvidíte, co se stane dál. Nic se neodešle policii a zkušební pobyt pak můžete smazat. |
| wizard.rehearsal.title | Your test run, step by step | Váš zkušební běh krok za krokem |
| wizard.rehearsal.paste | Done: you opened the link from your guest message. | Hotovo: otevřeli jste odkaz ze zprávy pro hosty. |
| wizard.rehearsal.form | Done: you filled in the guest form. | Hotovo: vyplnili jste formulář pro hosty. |
| wizard.rehearsal.email | With a real stay you get an email now. A test run sends no email. | U skutečného pobytu vám teď přijde e-mail. Zkušební běh žádný e-mail neposílá. |
| wizard.rehearsal.police | With a real stay the police report goes out next. | U skutečného pobytu teď odejde hlášení policii. |
| wizard.rehearsal.police_manual | With a real stay you open it and press Send. | U skutečného pobytu ho otevřete a stisknete Odeslat. |
| wizard.rehearsal.police_scheduled | With a real stay it goes out by itself %(hours)s hours after the form. | U skutečného pobytu odejde samo %(hours)s hodin po vyplnění formuláře. |
| wizard.rehearsal.police_immediate | With a real stay it goes out by itself within %(minutes)s minutes. | U skutečného pobytu odejde samo do %(minutes)s minut. |
| wizard.rehearsal.finish | With a real stay the guest gets a confirmation email. | U skutečného pobytu dostane host potvrzovací e-mail. |
| wizard.rehearsal.finish_lock | With a real stay the guest sees their door code and gets a confirmation email. | U skutečného pobytu host uvidí vstupní kód a dostane potvrzovací e-mail. |
| wizard.rehearsal.badge_done | Done | Hotovo |
| wizard.rehearsal.badge_test | Test only | Jen nanečisto |
| wizard.rehearsal.never_police | A test stay never goes to the police and is left out of stay fees and invoices. | Zkušební pobyt se nikdy neodešle policii a nepočítá se do poplatků ani faktur. |

Append to `host_vi_i18n.py` a `STRINGS.update({...})` block:

| key | vi |
|---|---|
| wizard.step.try_it | Chạy thử |
| wizard.summary.try_it | Chạy thử |
| why.try | Bước cuối: chạy thử. Hãy tự làm khách của mình: mở liên kết trong tin nhắn, nhập PIN và điền biểu mẫu bằng thông tin giả. Sau đó xem điều gì xảy ra tiếp theo. Không có gì được gửi cho cảnh sát, và bạn có thể xóa lượt lưu trú thử sau đó. |
| wizard.rehearsal.title | Lần chạy thử của bạn, từng bước |
| wizard.rehearsal.paste | Xong: bạn đã mở liên kết từ tin nhắn cho khách. |
| wizard.rehearsal.form | Xong: bạn đã điền biểu mẫu khách. |
| wizard.rehearsal.email | Với lượt lưu trú thật, bạn sẽ nhận email lúc này. Chạy thử không gửi email. |
| wizard.rehearsal.police | Với lượt lưu trú thật, khai báo cảnh sát sẽ được gửi tiếp theo. |
| wizard.rehearsal.police_manual | Với lượt lưu trú thật, bạn mở lượt đó và bấm Gửi. |
| wizard.rehearsal.police_scheduled | Với lượt lưu trú thật, khai báo tự gửi %(hours)s giờ sau khi điền biểu mẫu. |
| wizard.rehearsal.police_immediate | Với lượt lưu trú thật, khai báo tự gửi trong vòng %(minutes)s phút. |
| wizard.rehearsal.finish | Với lượt lưu trú thật, khách nhận email xác nhận. |
| wizard.rehearsal.finish_lock | Với lượt lưu trú thật, khách thấy mã cửa và nhận email xác nhận. |
| wizard.rehearsal.badge_done | Xong |
| wizard.rehearsal.badge_test | Chỉ thử |
| wizard.rehearsal.never_police | Lượt lưu trú thử không bao giờ được gửi cho cảnh sát và không tính vào phí lưu trú hay hóa đơn. |

Check the Czech button word: `grep -n '"reservation.send\|"common.send"' App/app/host_i18n.py | head -4`; if the Send button in Czech is not "Odeslat", use the word it uses.

**Step 5.** `docs/design/catalog.json`: add `App/app/static/wizard.css` to `enforced_stylesheets`; add `setup-rehearsal`, `setup-rehearsal-steps`, `setup-rehearsal-copy`, `is-done`, `is-test`, `workflow-num`, `ui-badge-` (only the ones lint T3 reports) to the `legacy` list of `App/app/templates/setup_wizard/try_it.html`. Run `python3 scripts/design_lint.py` from the repo root until OK.

**Step 6.** From `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`.

**Step 7.** Create `App/tests/test_test_run_0272.py` importing `host` and `_full_apartment` from `tests.test_onboarding_wizard_survival`. Walk to the test run in the new order (see 0270: calendar skip; police already complete in `_full_apartment`; automation saved via POST `/apartments/{id}/automation-timing` with `setup_step=automation`; stay_fee skip; door_lock `none` if its page returns 200; guest_link done), post `("try_it", "demo")`, then mark the demo stay registered by filling one guest like `test_demo_action_teaches_pin_then_opens_the_guest_form_and_reuses_its_stay` does (grep how it fills the demo form or inserts a guest with `filled_at`). Tests:

1. `test_walkthrough_after_demo_registration`: for en, cs, vi the try_it page has `data-rehearsal`, five `data-rehearsal-step=` items, `data-rehearsal-step="paste"` and the translated `wizard.rehearsal.never_police`.
2. `test_police_line_follows_mode`: with `automation_mode='scheduled'` and `submit_after_hours=12` the page contains the EN text with `12 hours`; with `manual` it contains the EN `wizard.rehearsal.police_manual`.
3. `test_no_walkthrough_before_registration`: right after `("try_it", "demo")` (no guest filled) the page has no `data-rehearsal`.

## 5. Do not touch

property_setup.py, routes, other templates, host2.css. Never push.

## 6. Commands

From `App/`:

- `.venv/bin/python -m pytest tests/test_test_run_0272.py tests/test_onboarding_wizard_survival.py tests/test_static_versions.py tests/test_host_i18n.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -30`
- Repo root: `python3 scripts/design_lint.py 2>&1 | tail -3` ends `design lint: OK`.

## 7. Acceptance

- [ ] After the demo form is sent, the last step lists all five steps with real/test badges, the police line follows the mode, and the lock line follows the lock.
- [ ] No email or police send is triggered (no code path added).
- [ ] Tests and lint pass.

## 8. Stop and ask

Per TEMPLATE.

## 9. Report

`docs/tasks/0272-report.md` (600 tokens max), `Status: review`, commits `0272 step k`. Do not push.
