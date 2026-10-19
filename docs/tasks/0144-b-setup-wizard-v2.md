# 0144-b: the setup wizard on the v2 template

Status: todo
Depends on: 0144 | Base commit: c340b7f | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit once at the end (step 9). Never push, never open a PR. Page file: `docs/design/pages/settings.md` (onboarding row of `migration-map.md`).

## 1. Objective

Move the setup wizard (`setup_wizard/_layout.html` and its nine step templates) onto `host_page.html` as a form-kind page: the wizard title and "Step n of 8" become the v2 page header, the progress bar and Exit setup stay at the top of the body, every legacy button and pill becomes a v2 class, and the demo note on the "Try it" step becomes a neutral banner. The owner saw the wizard's left edge under the collapsed sidebar; on `host_page` the shell owns the lane, and a new browser test pins that, collapsed and expanded.

## 2. Context

Rules: MASTER 5 (form kind), 7.1 (buttons: one primary per screen), 7.5 (badges), banner `neutral`. Migration map row: `onboarding.html + setup_wizard/*` = nav dashboard, form, primary Continue, steps indicator, demo label as neutral banner. The step templates keep their own primary in the footer (`wizard_actions`): that is the Continue button. Exit setup stays in the body, not in the header, because `host2.css` hides header secondary buttons on phone (`.ui-ph-acts .ui-btn-secondary { display: none }` under 1024 px).

How migrated pages do it: `reservation_detail.html` extends `host_page.html`, sets `body_kind`, fills `title`, `page_title`, `meta`, and puts the page in `{% block body %}`; when one file has several primaries in exclusive branches it sets `{% set cta = 'ui-btn ui-btn-primary' %}` and writes `class="{{ cta }}"`, so the design lint (T4: one `ui-btn-primary` per file) counts the screen, not the branches. Child step templates extend `setup_wizard/_layout.html` and fill `wizard_content`, `wizard_actions`, `wizard_notes`; those nested blocks keep working under `body`.

Root cause of the clipping (for the reviewer): 0153 fixed the stale `tokens.css` cache key; with fresh tokens the current wizard already starts right of the rail (checked at c340b7f, 1280 px collapsed and expanded: 0 elements under the rail). This brief makes it structural (the wizard renders in `.ui-page` inside the lane) and adds a guard test.

Anchors (verbatim at c340b7f; no earlier brief changes `setup_wizard/*`, `test_onboarding_wizard_browser.py` or `test_onboarding_followup_browser.py`):

- `App/app/templates/setup_wizard/_layout.html`: 41 lines, line 1 `{% extends "base.html" %}`, line 8 `<header class="setup-wizard-head">`. Step 1 replaces the whole file.
- Every step template's line 1 is `{% extends "setup_wizard/_layout.html" %}`.
- Counts in the step 2 script were dry-run at c340b7f: all match.

Pre-existing coverage this brief changes: `test_onboarding_wizard_browser.py` checks the warm skeleton on the automation step with the legacy `.c05-skel__bone` markup and its hidden-tab pause. On `host_page` the skeleton is `ui_skeleton('form')` (`.ui-bone`, `ui-pulse` animation); step 5 checks that instead and drops the hidden-tab pause check (`skeleton.js` pauses only `.c05-skel`; 0146 owns the skeleton cleanup).

Browser: set `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium` (`tests/browser_support.py` does not find it by itself).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/setup_wizard/_layout.html` | replace | extends `host_page.html` |
| `App/app/templates/setup_wizard/automation.html`, `calendar.html`, `done.html`, `door_lock.html`, `guest_link.html`, `police.html`, `property.html`, `stay_fee.html`, `try_it.html` | edit | v2 buttons, badges, banner |
| `App/app/static/host2.css` | edit | append six wizard rules |
| `App/app/templates/base.html` | edit | `host2.css?v=` key only (step 8) |
| `App/tests/static_versions.json` | edit | regenerated (step 8) |
| `docs/design/catalog.json` | edit | enforce the ten wizard templates; legacy lists |
| `App/tests/test_onboarding_wizard_browser.py` | edit | selectors, skeleton check |
| `App/tests/test_onboarding_followup_browser.py` | edit | one selector |
| `App/tests/test_design_setup_wizard_browser.py` | create | lane guard, no legacy controls |

No other file may change.

## 4. Steps

Run every command from `App/` unless it says otherwise.

1. Replace the whole of `App/app/templates/setup_wizard/_layout.html` (Write tool) with:

```
{% extends "host_page.html" %}
{% set body_kind = 'form' %}
{% block title %}{{ t('wizard.title', name=apartment.internal_name) }}{% endblock %}
{% block page_title %}{{ t('wizard.title', name=apartment.internal_name) }}{% endblock %}
{% block meta %}{% if wizard_number %}{{ t('wizard.count', n=wizard_number, total=wizard_total, step=t('wizard.step.' ~ wizard_step)) }}{% elif guide %}{{ t('wizard.count', n=guide.number, total=guide.total, step=t('wizard.step.' ~ guide.key)) }}{% endif %}{% endblock %}
{% block body %}
{% from "_components.html" import help_tip, copy_button, progress_pill, guest_count with context %}
{% set base_setup = '/apartments/' ~ apartment.id ~ '/' ~ 'setup' %}
{% set values = draft if draft is defined else apartment %}
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
      <input type="hidden" name="_csrf" value="{{ csrf_token }}">
      <button class="ui-btn ui-btn-secondary" type="submit" name="action" value="hide" formnovalidate>{{ t('wizard.exit') }}</button>
    </form>
  </div>
  <div class="setup-wizard-body">
    {% if setup_notice %}<p class="err-text" role="alert">{{ setup_notice }}</p>{% endif %}
    {% block wizard_content %}{% endblock %}
  </div>
  <footer class="setup-wizard-foot">
    {% if prev_step %}
    <a class="ui-btn ui-btn-quiet setup-wizard-back" href="{{ base_setup }}/{{ prev_step }}">{{ t('wizard.back') }}</a>
    {% else %}
    <span></span>
    {% endif %}
    {% block wizard_actions %}{% endblock %}
  </footer>
  {% block wizard_notes %}{% endblock %}
</div>
{% endblock %}
```

   Command: `.venv/bin/python -c "from app.templating import templates; templates.env.get_template('setup_wizard/_layout.html'); print('compiled')"`. Expected: `compiled`.

2. Step templates. Save this as `/tmp/0144b_steps.py` and run `.venv/bin/python /tmp/0144b_steps.py`:

```
import pathlib
T = pathlib.Path("app/templates/setup_wizard")
P = 'class="ui-btn ui-btn-primary"'
CTA = 'class="{{ cta }}"'
SEC = 'class="ui-btn ui-btn-secondary"'
def run(name, pairs, top=None):
    p = T / name; s = p.read_text(encoding="utf-8")
    for old, new, n in pairs:
        assert s.count(old) == n, (name, old, s.count(old)); s = s.replace(old, new)
    if top:
        old, new = top
        assert s.count(old) == 1, (name, old); s = s.replace(old, old + new, 1)
    assert 'class="btn' not in s and 'class="pill' not in s and 'style="' not in s, name
    assert s.count("ui-btn-primary") <= 1, (name, s.count("ui-btn-primary"))
    p.write_text(s, encoding="utf-8")
run("automation.html", [('class="btn primary"', P, 1)])
run("calendar.html", [('class="btn primary"', P, 1), ('class="btn"', SEC, 1)])
run("done.html", [('class="btn primary"', P, 1),
  ("""<span class="pill {{ 'green' if status == 'done' else 'amber' if status == 'waiting' else 'grey' }}">""",
   """<span class="ui-badge ui-badge-{{ 'done' if status == 'done' else 'attention' if status == 'waiting' else 'neutral' }}" data-tone="{{ 'green' if status == 'done' else 'amber' if status == 'waiting' else 'grey' }}">""", 1)])
run("door_lock.html", [('class="btn primary"', CTA, 2), ('class="btn"', SEC, 3)],
    top=('{% extends "setup_wizard/_layout.html" %}\n', "{% set cta = 'ui-btn ui-btn-primary' %}\n"))
run("guest_link.html", [('class="btn primary"', P, 1), ('class="btn setup-wizard-copy"', 'class="ui-btn ui-btn-secondary setup-wizard-copy"', 3)])
run("police.html", [('class="btn primary"', P, 1), ('class="btn setup-wizard-wait"', 'class="ui-btn ui-btn-secondary setup-wizard-wait"', 1),
  ('class="btn small police-sample-link"', 'class="ui-btn ui-btn-secondary ui-btn-compact police-sample-link"', 1)])
run("property.html", [('class="btn primary"', P, 1)])
run("stay_fee.html", [('class="btn primary"', P, 1), ('class="btn"', SEC, 1)])
run("try_it.html", [('class="btn primary"', CTA, 3), ('class="btn"', SEC, 6),
  ('class="pill grey"', 'class="ui-badge ui-badge-neutral" data-tone="grey"', 3),
  ("""<p class="setup-wizard-instruction setup-demo-disclaimer">{{ t('wizard.try_it.model_note') }}</p>""",
   """<div class="ui-banner ui-banner-neutral setup-demo-disclaimer" role="status">{{ icon('info', 20) }}<div class="grow">{{ t('wizard.try_it.model_note') }}</div></div>""", 1)],
    top=('{% extends "setup_wizard/_layout.html" %}\n', "{% from \"_icons.html\" import icon with context %}\n{% set cta = 'ui-btn ui-btn-primary' %}\n"))
print("ok")
```

   Expected: `ok`. Then: `.venv/bin/python -c "from app.templating import templates; [templates.env.get_template('setup_wizard/' + n + '.html') for n in ('automation','calendar','done','door_lock','guest_link','police','property','stay_fee','try_it')]; print('compiled')"`. Expected: `compiled`.

3. Append to the END of `App/app/static/host2.css`:

```
cat >> app/static/host2.css <<'EOF'

/* 0144-b setup wizard on host_page: the lane owns the gutter */
.host-workspace .setup-wizard { padding: 0; }
.host-workspace .setup-wizard-head { row-gap: var(--space-3); }
.host-workspace .setup-wizard-foot .ui-btn-primary { margin-left: auto; }
.host-workspace .setup-wizard-foot .ui-btn { max-width: 100%; }
.host-workspace .setup-wizard-lede.setup-wizard-fee-intro { font-size: var(--size-26); font-weight: 600; letter-spacing: -0.01em; line-height: 1.2; }
@media (max-width: 1023px) { .host-workspace .setup-wizard-lede.setup-wizard-fee-intro { font-size: var(--size-22); } }
EOF
tail -3 app/static/host2.css
```

   Expected: the last three lines just added. (The fee intro keeps matching the page title, as `test_wizard_polish_and_overview_cards` requires.)

4. Catalog: from the repo root, save as `/tmp/0144b_catalog.py` and run `python3 /tmp/0144b_catalog.py && python3 scripts/design_lint.py 2>&1 | tail -3`:

```
import json, sys, pathlib
sys.path.insert(0, "scripts")
import design_lint as L
names = ["setup_wizard/_layout.html", "setup_wizard/automation.html", "setup_wizard/calendar.html", "setup_wizard/done.html", "setup_wizard/door_lock.html", "setup_wizard/guest_link.html", "setup_wizard/police.html", "setup_wizard/property.html", "setup_wizard/stay_fee.html", "setup_wizard/try_it.html"]
cat = json.loads(L.CATALOG.read_text(encoding="utf-8"))
for n in names:
    rel = f"App/app/templates/{n}"
    if rel not in cat["enforced_templates"]:
        cat["enforced_templates"].append(rel)
    cat.setdefault("legacy", {}).pop(rel, None)
    found = L._findings_template(L.ROOT / rel, (L.ROOT / rel).read_text(encoding="utf-8"), cat)
    other = [f for f in found if " T3 " not in f]
    assert not other, other
    tokens = sorted({f.rsplit(": ", 1)[1] for f in found})
    if tokens:
        cat["legacy"][rel] = tokens
    print(n, len(tokens))
L.CATALOG.write_text(json.dumps(cat, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
```

   Expected: one line per template with a count between 5 and 15, then `design lint: OK`.

5. Test edits. Save as `/tmp/0144b_tests.py` and run `.venv/bin/python /tmp/0144b_tests.py`:

```
import pathlib
def rep(p, old, new, n=1):
    p = pathlib.Path(p); s = p.read_text(encoding="utf-8")
    assert s.count(old) == n, (str(p), old, s.count(old)); p.write_text(s.replace(old, new), encoding="utf-8")
W = "tests/test_onboarding_wizard_browser.py"
rep(W, '''            assert header["x"] + header["width"] <= exit_button["x"] + 1''',
       '''            assert header["y"] + header["height"] <= exit_button["y"] + 1''')
rep(W, '.setup-wizard-head h1', '.ui-ph h1', 3)
rep(W, '.setup-wizard-foot .btn.primary', '.setup-wizard-foot .ui-btn-primary', 2)
rep(W, '".setup-wizard-exit button, .setup-wizard-foot .btn"', '".setup-wizard-exit .ui-btn, .setup-wizard-foot .ui-btn"')
rep(W, "el.classList.contains('btn')", "el.classList.contains('ui-btn')")
rep(W, '.setup-wizard-checklist .pill.green', '.setup-wizard-checklist .ui-badge-done')
rep(W, '.setup-wizard-checklist .pill.grey', '.setup-wizard-checklist .ui-badge-neutral')
rep(W, 'police.locator(".pill.amber").inner_text()', 'police.locator(".ui-badge-attention").inner_text()')
rep(W, '''        assert police.locator(".pill.green").count() == 0
        assert police.locator("a").is_visible()''', '''        assert police.locator(".ui-badge-done").count() == 0
        assert police.locator("a").is_visible()''')
rep("tests/test_onboarding_followup_browser.py", '#demo-message-heading .pill', '#demo-message-heading .ui-badge')
rep(W, '''            bones = skeleton.locator(".c05-skel__bone")
            assert bones.count() == 6
            assert bones.first.evaluate(
                "(el) => getComputedStyle(el, '::after').animationName"
            ) == "c05-skel-sweep"
            assert page.evaluate(_overflow_js())
            _shot(page, f"32-warm-skeleton-{tag}.png")
            page.evaluate("""() => {
                Object.defineProperty(document, 'hidden', {configurable: true, value: true});
                document.dispatchEvent(new Event('visibilitychange'));
            }""")
            assert bones.first.evaluate(
                "(el) => getComputedStyle(el, '::after').animationPlayState"
            ) == "paused"
            page.evaluate("""() => {
                delete document.hidden;
                document.dispatchEvent(new Event('visibilitychange'));
            }""")
            page.emulate_media(reduced_motion="reduce")
            assert bones.first.evaluate(
                "(el) => getComputedStyle(el, '::after').animationName"
            ) == "none"
''', '''            bones = skeleton.locator(".ui-bone")
            assert bones.count() >= 6
            assert bones.first.evaluate("(el) => getComputedStyle(el).animationName") == "ui-pulse"
            assert page.evaluate(_overflow_js())
            _shot(page, f"32-warm-skeleton-{tag}.png")
            page.emulate_media(reduced_motion="reduce")
            assert bones.first.evaluate("(el) => getComputedStyle(el).animationName") == "none"
''')
print("tests ok")
```

   Expected: `tests ok`.

6. Create `App/tests/test_design_setup_wizard_browser.py`:

```python
"""0144-b: the setup wizard renders on host_page, inside the content lane.

The owner saw the wizard's left edge under the collapsed rail (0153). The wizard
now extends host_page.html, so the shell owns its lane; this pins that, collapsed
and expanded at 1280 and 2000 px, and no sideways scroll at 390 px."""
import os
import secrets

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, db
from tests.browser_support import chromium_launch_kwargs
from tests.test_host_geometry import _browser_session_cookie, base  # noqa: F401
from tests.test_shell_lane_browser import GEOMETRY

STEPS = ("property", "done")
TEMPLATES = ("_layout", "automation", "calendar", "done", "door_lock", "guest_link", "police", "property", "stay_fee", "try_it")


def test_wizard_templates_have_no_legacy_control():
    for name in TEMPLATES:
        text = open(f"app/templates/setup_wizard/{name}.html", encoding="utf-8").read()
        assert 'style="' not in text and 'class="btn' not in text and 'class="pill' not in text, name
    assert open("app/templates/setup_wizard/_layout.html", encoding="utf-8").read().startswith('{% extends "host_page.html" %}')


def _property():
    username = f"wiz{secrets.token_hex(3)}"
    owner = auth.create_account(f"{username}@example.test", "Wizard", role="host", username=username)
    entity = db.insert("legal_entity", {"name": "Wizard s.r.o.", "owner_user_id": owner, "created_at": db.utcnow()})
    apartment = db.insert("apartment", {"internal_name": "Wizard flat", "owner_user_id": owner, "legal_entity_id": entity,
                                        "permalink_token": f"wz{secrets.token_hex(4)}", "active": 1, "created_at": db.utcnow()})
    return username, apartment


@pytest.mark.parametrize("width", [390, 1280, 2000])
@pytest.mark.parametrize("collapsed", [False, True])
def test_wizard_sits_in_the_lane(base, width, collapsed):
    username, apartment = _property()
    cookie = _browser_session_cookie(username)
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception as exc:
            if REQUIRE_BROWSER:
                raise
            pytest.skip(f"Chromium is not available: {exc}")
        context = browser.new_context(viewport={"width": width, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
        if collapsed:
            context.add_init_script("try { localStorage.setItem('ubyhost-sidebar-collapsed', '1'); } catch (e) {}")
        page = context.new_page()
        for step in STEPS:
            page.goto(f"{base}/apartments/{apartment}/setup/{step}?lang=en")
            page.wait_for_selector(".ui-page[data-body-kind='form'] .setup-wizard", timeout=30000)
            assert page.locator("main h1").count() == 1, step
            assert page.locator(".ui-ph h1").is_visible(), step
            assert page.locator(".setup-wizard-exit .ui-btn").is_visible(), step
            size = page.evaluate("({sw: document.documentElement.scrollWidth, iw: innerWidth})")
            assert size["sw"] <= size["iw"], (step, width, size)
            if width < 1024:
                continue
            rail_w = 64 if collapsed else 240
            page.wait_for_function(  # app.css animates margin-left for 0.26 s
                "w => getComputedStyle(document.querySelector('.wrap.with-sidebar')).marginLeft === w + 'px'", arg=rail_w, timeout=3000)
            g = page.evaluate(GEOMETRY)
            assert g["mainLeft"] >= g["railRight"] and g["under"] == [], (step, width, collapsed, g)
        browser.close()
```

7. Tests.
   - Unit: `.venv/bin/python -m pytest tests/test_onboarding_wizard_survival.py tests/test_setup_banner.py tests/test_demo_stay_exclusion.py tests/test_no_dead_internal_links.py tests/test_onboarding.py tests/test_design_lint.py tests/test_design_settings.py -q --tb=short -x 2>&1 | tail -3`. Expected: 76 passed.
   - Browser, two separate calls, each with a 600 s timeout:
     `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_onboarding_wizard_browser.py -q --tb=short -rs 2>&1 | tail -8`
     `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_onboarding_followup_browser.py tests/test_design_setup_wizard_browser.py tests/test_shell_lane_browser.py -q --tb=short -rs 2>&1 | tail -8`
   Expected: passed, 0 failed, 0 skipped (93 for the wizard, follow-up and new file together at c340b7f, about 6 minutes, plus 4 for the shell lane). No screenshots: the orchestrator takes them.

8. Static key (last change before the commit; `host2.css` changed in step 3):

```
.venv/bin/python - <<'EOF'
import pathlib, re
for p in pathlib.Path("app/templates").rglob("*.html"):
    if "archive" in p.relative_to("app/templates").parts:
        continue
    s = p.read_text(encoding="utf-8")
    n = re.sub(r'/static/host2\.css\?v=[^"]+', '/static/host2.css?v=20261019-0144b', s)
    if n != s:
        p.write_text(n, encoding="utf-8"); print("bumped", p)
EOF
grep -rn "/static/host2.css?v=" app/templates | grep -v archive
.venv/bin/python tests/test_static_versions.py --write && .venv/bin/python -m pytest tests/test_static_versions.py -q 2>&1 | tail -5
```

   Expected: `bumped app/templates/base.html`, the grep shows only `?v=20261019-0144b`, then `passed`.

9. Commit: from the repo root, `python3 scripts/context_lint.py 2>&1 | tail -3` (expected: OK), then `git add App/app/templates App/app/static/host2.css App/tests docs/design/catalog.json && git commit -m "0144-b: setup wizard on host_page" 2>&1 | tail -3`.

## 5. Do not touch

`routes/onboarding_wizard.py`, `routes/onboarding.py`, `_components.html`, `_property_*.html` includes, `host.css`, `host-design0123.css`, `skeleton.js`; every form `action`, `name`, `value`, `form=` and `data-*` attribute in the wizard; hard rules 1, 2, 3, 6, 8.

## 6. Commands

- `python3 scripts/design_lint.py` expected: OK.
- Step 7 and step 8 commands: passed, 0 failed, 0 skipped.

## 7. Acceptance

- [ ] `setup_wizard/_layout.html` extends `host_page.html`; the wizard page has one `h1` in `.ui-ph` and `data-body-kind="form"`.
- [ ] No `class="btn`, `class="pill` or `style="` in `setup_wizard/*`; one `ui-btn-primary` per screen.
- [ ] Try it: the demo note is a neutral banner (`.ui-banner-neutral.setup-demo-disclaimer`).
- [ ] `test_design_setup_wizard_browser.py`: 0 elements under the rail at 1280 and 2000 px, collapsed and expanded; no sideways scroll at 390 px.
- [ ] Lint OK with the ten templates enforced; `host2.css` key is `20261019-0144b`.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a count differs; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0144-b-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left. No screenshots needed.

## Risk list (for the reviewer)

`App/app/templates/setup_wizard/police.html` (UbyPort credentials step; hard rule 1 adjacency, classes only) and `_layout.html` (Exit setup form).

## Owner steps

None.
