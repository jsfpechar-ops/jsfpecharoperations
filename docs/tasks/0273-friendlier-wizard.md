# 0273: Friendlier wizard (K): step colour, icon, question title, coral bar, tick

Status: todo
Depends on: 0272 | Base commit: 48c21b3 + 0270-0272 | Branch: claude/project-thread-4b2e7k (commit here, do not push)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Every wizard step opens with a coloured icon tile and a plain question as its title, and the progress dots become a coral bar with "3 of 8 done" in words beside it, where the tick pops in once. Hosts see where they are and that each answer counted, without extra text.

## 2. Context

- Owner decision 2026-10-22 (docs/context/decisions.md): in the setup wizard only, the progress bar fills in coral (`--brand-action`). Everywhere else MASTER 10.5 still holds. Step icons never use coral; they use blue, teal or purple on their own `-bg` tile with a 1px border (no borderless look).
- CSS goes in `App/app/static/wizard.css` (created by 0272; append to it, never host2.css). Lint rule S2: no bare px in margin, padding, gap, border-radius, font-size (use `var(--space-*)`, `var(--radius-*)`, `var(--text-*)`). width/height px are fine. No raw colours.
- Reduced motion: the tick pop is off for `prefers-reduced-motion: reduce`.
- Colour is never the only signal: the words "3 of 8 done" carry the count.
- Templates: classes must be listed in `docs/design/catalog.json` under that template's `legacy` list, or lint T3 fails.

Excerpt, `App/app/templates/setup_wizard/_layout.html` lines 9-21:

```
<div class="setup-wizard" data-setup-wizard data-setup-step="{{ wizard_step }}">
  <div class="setup-wizard-head">
    {% if guide %}
    <ol class="setup-wizard-progress" aria-hidden="true">
      {% for item in guide.progress %}
      <li class="is-{{ item.state }}"></li>
      {% endfor %}
    </ol>
    {% endif %}
    <form method="post" action="{{ base_setup }}" class="setup-wizard-exit">
```

and lines 22-25:

```
  <div class="setup-wizard-body">
    {% if wizard_step in ('property', 'police', 'stay_fee') %}<p class="required-legend">{{ t('common.required_legend') }}</p>{% endif %}
```

`guide` has `done_count`, `total`, `progress` (list of `{"key", "state"}` with state done | skipped | waiting | current | todo).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/setup_wizard/_layout.html | edit | meter + question header |
| App/app/static/wizard.css | edit | append styles |
| App/app/templates/base.html | edit | wizard.css key |
| App/app/host_i18n.py | edit | EN + CS keys block |
| App/app/host_vi_i18n.py | edit | VI keys block |
| docs/design/catalog.json | edit | legacy classes for _layout.html |
| App/tests/static_versions.json | regenerate | via --write |
| App/tests/test_wizard_friendly_0273.py | create | tests |

No other file may change.

## 4. Steps

**Step 1.** In `_layout.html`, replace the excerpt block from `    {% if guide %}` to its `{% endif %}` (the `<ol class="setup-wizard-progress"...` block, 7 lines) with:

```
    {% if guide %}
    <div class="setup-wizard-meter">
      <ol class="setup-wizard-progress" aria-hidden="true">
        {% for item in guide.progress %}
        <li class="is-{{ item.state }}"></li>
        {% endfor %}
      </ol>
      <p class="setup-wizard-done-count">{% if guide.done_count %}<span class="setup-wizard-tick" aria-hidden="true">✓</span> {% endif %}{{ t('wizard.done_count', n=guide.done_count, total=guide.total) }}</p>
    </div>
    {% endif %}
```

**Step 2.** In `_layout.html`, directly after the line `  <div class="setup-wizard-body">`, insert:

```
    {% set step_icons = {'property': 'property', 'calendar': 'calendar', 'police': 'report', 'automation': 'automation', 'stay_fee': 'coins', 'door_lock': 'lock', 'guest_link': 'link', 'try_it': 'users'} %}
    {% set step_tones = {'property': 'blue', 'calendar': 'teal', 'police': 'purple', 'automation': 'blue', 'stay_fee': 'teal', 'door_lock': 'purple', 'guest_link': 'blue', 'try_it': 'teal'} %}
    {% if wizard_step in step_icons %}
    <div class="setup-wizard-ask" data-step-tone="{{ step_tones[wizard_step] }}">
      <span class="setup-wizard-ask-icon">{{ nav_icon(step_icons[wizard_step]) }}</span>
      <h2 class="setup-wizard-question">{{ t('wizard.question.' ~ wizard_step) }}</h2>
    </div>
    {% endif %}
```

and change the import line `{% from "_components.html" import help_tip, copy_button, progress_pill, guest_count with context %}` to `{% from "_components.html" import help_tip, copy_button, progress_pill, guest_count, nav_icon with context %}`. Check first that `coins` exists: `grep -n "name == 'coins'" App/app/templates/_components.html`. If it is missing, STOP.

**Step 3.** Append to `App/app/static/wizard.css`:

```
/* 0273: friendlier setup wizard (K). Coral bar is wizard-only (decision 2026-10-22). */
.host-workspace .setup-wizard-meter { grid-column: 1 / -1; display: grid; gap: var(--space-2); min-width: 0; }
.host-workspace .setup-wizard-meter .setup-wizard-progress li { height: 8px; border: 1px solid var(--border); background: var(--surface); opacity: 1; }
.host-workspace .setup-wizard-meter .setup-wizard-progress li.is-done { border-color: var(--brand-action); background: var(--brand-action); }
.host-workspace .setup-wizard-meter .setup-wizard-progress li.is-current { border-color: var(--brand-action); background: var(--brand-soft); }
.host-workspace .setup-wizard-meter .setup-wizard-progress li.is-waiting { border-color: var(--amber-300); background: var(--amber-100); }
.host-workspace .setup-wizard-meter .setup-wizard-progress li.is-skipped { border-style: dashed; background: var(--surface); }
.host-workspace .setup-wizard-done-count { display: flex; align-items: center; gap: var(--space-2); margin: 0; color: var(--ink-secondary); font-size: var(--text-sm); font-weight: 600; }
.host-workspace .setup-wizard-tick { display: inline-grid; place-items: center; width: 20px; height: 20px; border: 1px solid var(--green-300); border-radius: var(--radius-pill); background: var(--green-bg); color: var(--green-700); font-size: var(--text-xs); line-height: 1; animation: setup-wizard-tick-pop 300ms ease-out 1 both; }
@keyframes setup-wizard-tick-pop { 0% { transform: scale(0); } 70% { transform: scale(1.2); } 100% { transform: scale(1); } }
@media (prefers-reduced-motion: reduce) { .host-workspace .setup-wizard-tick { animation: none; } }
.host-workspace .setup-wizard-ask { display: flex; align-items: center; gap: var(--space-3); margin: 0 0 var(--space-3); min-width: 0; }
.host-workspace .setup-wizard-ask-icon { flex: 0 0 auto; display: inline-grid; place-items: center; width: 44px; height: 44px; border: 1px solid currentColor; border-radius: var(--radius-md); }
.host-workspace .setup-wizard-ask-icon .nav-icon { width: 24px; height: 24px; color: inherit; }
.host-workspace .setup-wizard-ask[data-step-tone="blue"] .setup-wizard-ask-icon { color: var(--blue); background: var(--blue-bg); }
.host-workspace .setup-wizard-ask[data-step-tone="teal"] .setup-wizard-ask-icon { color: var(--teal); background: var(--teal-bg); }
.host-workspace .setup-wizard-ask[data-step-tone="purple"] .setup-wizard-ask-icon { color: var(--purple); background: var(--purple-bg); }
.host-workspace .setup-wizard-question { margin: 0; min-width: 0; color: var(--ink); font-size: var(--text-lg); line-height: 1.25; overflow-wrap: anywhere; }
```

Check the tokens exist before saving: `grep -c -- "--text-lg\|--text-xs\|--radius-pill\|--radius-md\|--amber-300\|--amber-100\|--green-300\|--green-700\|--brand-soft\|--teal-bg\|--purple-bg\|--blue-bg\|--border:" App/app/static/tokens.css` must print a number of 13 or more lines found; if a token is missing, STOP.

**Step 4.** In `App/app/templates/base.html`, change the wizard.css link key from `20261022-0272` to `20261022-0273`.

**Step 5.** In `App/app/host_i18n.py`, after the block that ends with `for _lang, _strings in _MAIL_0245_STRINGS.items():` and its `    STRINGS[_lang].update(_strings)` line (grep the LAST `_STRINGS.items():` block; if a later block exists, add after the last one), add:

```python


# 0273: friendlier wizard (K): question titles and the done count.
_WIZARD_0273_STRINGS = {
    "en": {
        "wizard.done_count": "%(n)s of %(total)s done",
        "wizard.question.property": "Where is your property?",
        "wizard.question.calendar": "Where do you take bookings?",
        "wizard.question.police": "What is your police login?",
        "wizard.question.automation": "When should reports go to the police?",
        "wizard.question.stay_fee": "Does your town charge a stay fee?",
        "wizard.question.door_lock": "How do guests get in?",
        "wizard.question.guest_link": "How do guests find their form?",
        "wizard.question.try_it": "Shall we do a test run?",
    },
    "cs": {
        "wizard.done_count": "Hotovo %(n)s z %(total)s",
        "wizard.question.property": "Kde je vaše ubytování?",
        "wizard.question.calendar": "Kde přijímáte rezervace?",
        "wizard.question.police": "Jaké máte přihlášení do Ubyportu?",
        "wizard.question.automation": "Kdy se mají hlášení posílat policii?",
        "wizard.question.stay_fee": "Vybírá vaše obec poplatek z pobytu?",
        "wizard.question.door_lock": "Jak se hosté dostanou dovnitř?",
        "wizard.question.guest_link": "Jak hosté najdou svůj formulář?",
        "wizard.question.try_it": "Vyzkoušíme to nanečisto?",
    },
}
for _lang, _strings in _WIZARD_0273_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

**Step 6.** At the end of `App/app/host_vi_i18n.py` append:

```python

# 0273: friendlier wizard (K).
STRINGS.update({
    "wizard.done_count": "Đã xong %(n)s/%(total)s",
    "wizard.question.property": "Chỗ ở của bạn ở đâu?",
    "wizard.question.calendar": "Bạn nhận đặt phòng ở đâu?",
    "wizard.question.police": "Thông tin đăng nhập cảnh sát của bạn là gì?",
    "wizard.question.automation": "Khi nào gửi khai báo cho cảnh sát?",
    "wizard.question.stay_fee": "Địa phương của bạn có thu phí lưu trú không?",
    "wizard.question.door_lock": "Khách vào nhà bằng cách nào?",
    "wizard.question.guest_link": "Khách tìm biểu mẫu của mình bằng cách nào?",
    "wizard.question.try_it": "Chạy thử một lần nhé?",
})
```

**Step 7.** In `docs/design/catalog.json`: add these tokens to the `legacy` list of `"App/app/templates/setup_wizard/_layout.html"`: `setup-wizard-meter`, `setup-wizard-done-count`, `setup-wizard-tick`, `setup-wizard-ask`, `setup-wizard-ask-icon`, `setup-wizard-question`. Edit with a short python script that loads, appends and dumps with the same indent the file uses (check `head -c 300` first).

**Step 8.** Regenerate the static manifest: from `App/`, `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`.

**Step 9.** Create `App/tests/test_wizard_friendly_0273.py`. Copy the `host` fixture and the `_full_apartment` helper pattern from `tests/test_onboarding_wizard_survival.py` (read only the fixture and helper: `grep -n "def host\|def _full_apartment" tests/test_onboarding_wizard_survival.py`, then import them: `from tests.test_onboarding_wizard_survival import host, _full_apartment  # noqa: F401` if that import works; run it once to check). Tests:

1. `test_question_title_and_icon_on_every_step`: for lang in en, cs, vi, GET `/apartments/{id}/setup/calendar?lang=<lang>`; assert `class="setup-wizard-question"` in text and the translated `wizard.question.calendar` (use `host_i18n.translate(lang, key)`) is in the text, and `data-step-tone="teal"` is in the text.
2. `test_done_count_words_and_tick`: post `{"step": "calendar", "action": "skip"}` to `/apartments/{id}/setup`, GET the next step page (`?lang=en`); assert `1 of 8 done` in text and `setup-wizard-tick` in text. A fresh property GET calendar page asserts `0 of 8 done` and `setup-wizard-tick` not in text.
3. `test_every_question_key_in_three_languages`: for every step in `property_setup.STEPS` and lang in en, cs, vi, `translate(lang, "wizard.question." + step)` does not equal the key.
4. `test_wizard_css_reduced_motion_and_no_coral_icons`: read `app/static/wizard.css`; assert `prefers-reduced-motion` in it, and that no line containing `setup-wizard-ask` also contains `--brand`.

## 5. Do not touch

host2.css, host.css, any other template, routes, property_setup.py. Hard rules: privacy, light mode only, no new dependency, never push.

## 6. Commands

From `App/`:

- `.venv/bin/python -m pytest tests/test_wizard_friendly_0273.py tests/test_static_versions.py tests/test_onboarding_wizard_survival.py -q --tb=short -x 2>&1 | tail -30`
- `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -30` (skip a file that does not exist; list them with `ls tests/test_*i18n*.py`)
- From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -5` must end `design lint: OK`.

## 7. Acceptance

- [ ] Every step page shows an icon tile and a question h2 in EN, CS, VI.
- [ ] The bar reads "n of 8 done"; the tick shows only when n > 0.
- [ ] Design lint OK; static versions test passes.
- [ ] New tests pass.

## 8. Stop and ask

Per TEMPLATE: excerpt not found, a test fails twice, 25 tool calls, a file outside §3, a step unclear.

## 9. Report

Write `docs/tasks/0273-report.md` (600 tokens max), set `Status: review`. Commit each step as `0273 step k`. Do not push; do not open a PR.
