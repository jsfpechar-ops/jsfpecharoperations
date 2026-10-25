# 0399: The whole option card selects, radios and checkboxes look calm

Status: review
Depends on: none | Branch: claude/project-thread-cf1iwp (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Owner (Josef, 2026-10-25, setup wizard "When should reports go to the police?"): "I have to click specifically on the words to select it, not the whole row or pill. That's a bug." And: "also weird, it highlights the blue button."

1. A click or tap anywhere on a bordered option card selects its radio. The "?" help button and the hours field inside a card do NOT select it.
2. Radios and checkboxes in the host app use the coral accent, not browser blue.
3. A mouse click on a radio or checkbox draws no square box. Keyboard focus still shows a visible ring (WCAG 2.4.7): on an option card the ring goes round the whole card.
4. One shared macro `choice_card` renders every option card. It works without JavaScript.
5. The two host checkboxes that sit in a `div.checkline` with a separate `<label for>` become one `<label class="checkline">`, so the gap between box and words is clickable too.

## 2. Context (orchestrator checked these; do not re-audit)

- Cause: in `App/app/templates/setup_wizard/automation.html` each card is a `div.setup-wizard-radio-card`; only the inner `label.setup-wizard-radio-choice` is clickable. Card CSS is `App/app/static/host.css` lines ~1366-1372.
- Blue + square box: radios have no `accent-color`, and `App/app/static/host2.css` ~559 `.host-workspace input:focus-visible, .host-workspace input:focus { outline: 2px solid var(--coral-600) !important; ... }` draws an outline on every mouse focus. Line ~556 already gives keyboard focus a ring for every input, so checkbox/radio lose nothing when 559 skips them.
- Other patterns are fine already: settings uses a `<select>` for the same choice; the lock yes/no choice uses buttons; guest quick choice stretches the input; all other checkboxes are inside a `<label>`.
- `help_tip` macro: `App/app/templates/_components.html` line ~10. Its button has a 44 px `::after` hit area.
- 0284 hover block: `host2.css` ~742-757 ("Pages add no hover CSS of their own: extend these lists instead").

## 3. Files

| Path | Action |
|---|---|
| App/app/templates/_components.html | add `choice_card` macro |
| App/app/templates/setup_wizard/automation.html | use it |
| App/app/static/host.css | delete the old setup-wizard-radio rules |
| App/app/static/host2.css | new 0399 block, focus fix, 0284 lists |
| App/app/templates/guest_form_admin.html, App/app/templates/_smart_locks_panel.html | `div.checkline` → `label.checkline` |
| App/app/templates/base.html | bump `host.css` and `host2.css` keys to `20261025-0399` |
| App/tests/static_versions.json | `--write` |
| App/tests/test_onboarding_wizard_browser.py | one selector, one new test |

## 4. Steps

0. **Setup** (from `App/`, only if `.venv` is missing): `python3 -m venv .venv && .venv/bin/pip install -q -r requirements-dev.txt 2>&1 | tail -3`. Do not commit `.venv`.

1. **Macro** (`_components.html`): insert directly after the `help_tip` macro's `{% endmacro %}`:
```jinja
{#- 0399: one option card. The label is stretched over the whole bordered card, so a
    tap anywhere selects; the "?" and any extra field (call block) sit above it. No JS. -#}
{% macro choice_card(name, value, label, checked=false, help_id='', help_text='', type='radio') %}
<div class="ui-choice-card">
  <label class="ui-choice-card-label">
    <input type="{{ type }}" name="{{ name }}" value="{{ value }}"{% if checked %} checked{% endif %}>
    <strong>{{ label }}</strong>
  </label>
  {% if help_text %}{{ help_tip(help_id, help_text) }}{% endif %}
  {% if caller is defined %}<div class="ui-choice-card-extra">{{ caller() }}</div>{% endif %}
</div>
{% endmacro %}
```

2. **Wizard** (`automation.html`): change line 2 to `{% from "_components.html" import choice_card with context %}`. Replace the whole `<div class="setup-wizard-radios"> ... </div>` (the three cards, up to the `</div>` before `</form>`) with:
```jinja
  <div class="ui-choice-cards">
    {{ choice_card('automation_mode', 'manual', t('automation.mode.manual'), values.automation_mode == 'manual', 'wizard-manual-help', t('wizard.automation.manual_detail')) }}
    {% call choice_card('automation_mode', 'scheduled', t('automation.mode.scheduled'), values.automation_mode == 'scheduled', 'wizard-scheduled-help', t('wizard.automation.scheduled_detail')) %}
      <div class="field inline-hours">
        <label for="submit_after_hours">{{ t('automation.hours') }}</label>
        <input type="number" id="submit_after_hours" name="submit_after_hours" min="1" max="48" value="{{ values.submit_after_hours if values.submit_after_hours is not none else 2 }}">
      </div>
    {% endcall %}
    {{ choice_card('automation_mode', 'immediate', t('automation.mode.immediate'), values.automation_mode == 'immediate', 'wizard-immediate-help', t('wizard.automation.immediate_detail')) }}
  </div>
```

3. **host.css**: delete the 7 lines starting `.setup-wizard-radio-choice {`, `.setup-wizard-radio-card .inline-hours`, `.setup-wizard-radios {`, `.setup-wizard-radio-card {`, `.setup-wizard-radio-card:has(`, `.setup-wizard-radio-card strong`, `.setup-wizard-radio-card small`. Then `grep -rn "setup-wizard-radio" app/` must print nothing.

4. **host2.css focus**: replace the 0171 line
`.host-workspace input:focus-visible, .host-workspace input:focus { outline: 2px solid var(--coral-600) !important; outline-offset: 2px; }`
with
```css
.host-workspace input:not([type=checkbox], [type=radio]):focus-visible, .host-workspace input:not([type=checkbox], [type=radio]):focus { outline: 2px solid var(--coral-600) !important; outline-offset: 2px; }
/* 0399: radios and checkboxes are coral, and a mouse click draws no box (keyboard focus keeps the 0169 ring). */
.host-workspace :is(input[type=checkbox], input[type=radio]) { accent-color: var(--accent); }
.host-workspace .checkline > span { font-weight: 500; }
```

5. **host2.css 0284 lists**: in the first line inside `@media (hover: hover)` of the 0284 block, add `, .ui-choice-card` after `.host-task` in the `:is(...)` list (the one ending `):hover { background: var(--state-hover); }`). In the `:active` line right after the media block, add `, .ui-choice-card` after `.host-task` too.

6. **host2.css new block**: append at the end of the file:
```css
/* 0399: option cards (choice_card macro). The label's ::after covers the whole card, so a tap
   anywhere selects; the "?" and the extra field sit above it. The focus ring goes round the card. */
.ui-choice-cards { display: flex; flex-direction: column; gap: var(--space-2); }
.ui-choice-card { position: relative; display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2) var(--space-3); padding: var(--space-3) var(--space-4); border: 1px solid var(--line-strong); border-radius: var(--radius-md); background: var(--surface); cursor: pointer; }
.ui-choice-card-label { display: flex; align-items: center; gap: var(--space-3); flex: 1 1 12rem; min-width: 0; margin: 0; cursor: pointer; }
.ui-choice-card-label::after { content: ""; position: absolute; inset: 0; }
.ui-choice-card-label input { flex: 0 0 auto; width: var(--space-5); height: var(--space-5); margin: 0; accent-color: var(--accent); }
.ui-choice-card-label strong { overflow-wrap: anywhere; }
.ui-choice-card > .help-tip, .ui-choice-card-extra { position: relative; z-index: 1; }
.ui-choice-card > .help-tip:is(.is-open, :focus-within) { z-index: 2; }
.ui-choice-card-extra { flex: 1 1 100%; min-width: 0; cursor: auto; }
.ui-choice-card:has(input:checked) { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); }
.host-workspace .ui-choice-card input:focus-visible { outline: none !important; }
.ui-choice-card:has(input:focus-visible) { outline: 2px solid var(--coral-600); outline-offset: 2px; }
```

7. **checklines**: in `guest_form_admin.html` replace
```html
    <div class="checkline">
      <input type="checkbox" id="confirm_duplicate" name="confirm_duplicate" value="1">
      <label for="confirm_duplicate">{{ t('guest.admin.resend.confirm') }}</label>
    </div>
```
with
```html
    <label class="checkline" for="confirm_duplicate">
      <input type="checkbox" id="confirm_duplicate" name="confirm_duplicate" value="1">
      <span>{{ t('guest.admin.resend.confirm') }}</span>
    </label>
```
In `_smart_locks_panel.html` replace the two lines starting `<div class="checkline"><input type="checkbox" id="terms"` and `<label for="terms">` (ending `</label></div>`) with
```html
    <label class="checkline" for="terms"><input type="checkbox" id="terms" name="terms" value="1" required>
      <span>{{ t('smart_locks.terms') }} <a href="/guide#door-codes-terms">{{ t('smart_locks.terms_link') }}</a></span></label>
```

8. **Cache keys**: in `base.html` set the `host.css?v=` and `host2.css?v=` values to `20261025-0399`. Then `.venv/bin/python tests/test_static_versions.py --write`.

9. **Tests** (`test_onboarding_wizard_browser.py`): change `.setup-wizard-radio-card .help-tip` to `.ui-choice-card .help-tip`. Append at the end of the file:
```python
CHOICE_SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0399"


@pytest.mark.parametrize("lang", ["en", "cs", "vi"])
@pytest.mark.parametrize("width,collapsed", [(390, False), (1280, False), (1280, True), (2000, False), (2000, True)])
def test_choice_card_selects_from_anywhere(host, base_url, lang, width, collapsed):
    """0399: a tap anywhere on an option card selects it; the "?" and the hours field do not."""
    if not REQUIRE_BROWSER:
        pytest.skip("browser not required")
    flat = _create(host)
    session = host["client"].cookies.get(auth.SESSION_COOKIE)
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": width, "height": 900}, locale=lang)
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": session, "url": base_url + "/"}])
        if collapsed:
            context.add_init_script("localStorage.setItem('ubyhost-sidebar-collapsed', '1')")
        page = context.new_page()
        page.goto(f"{base_url}/apartments/{flat['id']}/setup/automation?lang={lang}")
        cards = page.locator(".ui-choice-card")
        assert cards.count() == 3

        def click_empty(card):
            box = card.bounding_box()
            page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] - 4)

        click_empty(cards.nth(2))
        assert page.locator('input[value="immediate"]').is_checked()
        click_empty(cards.nth(1))
        scheduled = page.locator('input[value="scheduled"]')
        assert scheduled.is_checked()
        assert scheduled.evaluate("(el) => getComputedStyle(el).outlineStyle") == "none"
        assert scheduled.evaluate("(el) => getComputedStyle(el).accentColor") != "auto"
        tip = cards.nth(0).locator(".help-tip-btn")
        tip.click()
        assert not page.locator('input[value="manual"]').is_checked()
        tip.click()
        page.locator("#submit_after_hours").click()
        assert scheduled.is_checked()
        scheduled.focus()
        page.keyboard.press("ArrowUp")
        assert page.locator('input[value="manual"]').is_checked()
        assert cards.nth(0).evaluate("(el) => getComputedStyle(el).outlineStyle") == "solid"
        assert page.evaluate(_overflow_js())
        CHOICE_SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(CHOICE_SHOTS / f"automation-{lang}-{width}{'c' if collapsed else ''}.png"), full_page=True)
        browser.close()
```

## 5. Do not touch

Routes, `property_setup.py`, i18n copy, the settings page `<select>`, the lock choice, guest pages, `app.css`.

## 6. Commands

From `App/`:
```
.venv/bin/ruff check app tests --select E9,F63,F7,F82,F401,F841 2>&1 | tail -5
UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests/test_onboarding_wizard_browser.py tests/test_static_versions.py tests/test_design_guardrails_browser.py tests/test_smart_locks_page.py tests/test_host_geometry.py -q --tb=short -rs 2>&1 | tail -30
cd .. && python3 scripts/context_lint.py 2>&1 | tail -5 && git checkout -- docs/tasks/0102-evidence 2>/dev/null; true
```
If a test fails, put its first assertion line in the report. Fix only inside §3.

## 7. Acceptance

- [ ] §6 passes, 0 skipped.
- [ ] `docs/tasks/screenshots-0399/` has 15 PNGs; you looked at `automation-en-390.png` and `automation-vi-2000c.png` once each: three bordered cards, coral radio, no blue, no square box.

## 8. Stop and ask

As in TEMPLATE §8.

## 9. Report

No report file. ONE commit `0399: whole option card selects; coral radios, no box on click`, including this brief and `docs/tasks/screenshots-0399/`, ending with the Haiku Co-Authored-By trailer and `Claude-Session: https://claude.ai/code/session_01NLtgdaBVrKe87AGaYMWFVN`. Do not push.
