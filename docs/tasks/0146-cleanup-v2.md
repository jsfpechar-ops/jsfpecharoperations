# 0146: Design v2 cleanup: one skeleton, dead macros out, legacy burn-down report

Status: todo
Depends on: 0145 | Base commit: cdcb781 | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit each step as `0146 step k`. Never push, never open a PR.

## 1. Objective

After every host page sits on `host_page.html`: (a) one skeleton markup and one shimmer (the `c05` loader goes; `base.html`'s fallback uses `ui_skeleton`), (b) the `_components.html` macros no template calls any more are deleted, (c) a burn-down report lists which legacy classes and which rules of `host-controls.css` and `host-design0123.css` are still referenced, so the owner can decide the stylesheet deletions in a later brief. Nothing visible changes except the loading placeholder on non-host pages.

## 2. Context

Rules: MASTER 2 (one system), 7.14 (skeleton). `skeleton.js` toggles `paused` on `.c05-skel` cards when the tab is hidden and keys on `[data-page-skeleton]`; `host_page.html` (0129) already renders `ui_skeleton(body_kind)` inside its `page_skeleton` block, so only the `base.html` fallback (public and non-host pages) still prints `c05` markup. `components.css` keeps its own `.skeleton`, `.skeleton-line` rules (used by `invoice_form.html` placeholders); `skeleton.css` keeps the `.skeleton`/`.g-skeleton` shimmer. `host-controls.css` and `host-design0123.css` are NOT deleted here: both still style classes the legacy allowlists carry (`row-menu`, `popover`, `host-filter-panel`, `guest-card`, `onboarding-*`, `csv-export-dialog`, `clickable-row`); `test_host_controls_browser.py` line 169 and `test_signed_in_chrome.py` lines 250 to 262 keep asserting on them unchanged.

Anchor A, `App/app/templates/base.html`, the fallback skeleton inside `{% block page_skeleton %}` (as 0129 left it): the block from the line `    <div class="c05-skel" aria-hidden="true">` to the matching `    </div>` (four-space indent), eleven lines, containing six `c05-skel__bone` spans.

Anchor B, `App/app/static/skeleton.js`:

```
    document.querySelectorAll(".c05-skel").forEach(function (card) {
      card.classList.toggle("paused", document.hidden);
    });
```

Anchor C, `App/tests/test_onboarding_wizard_browser.py` lines 1494 to 1498:

```
            bones = skeleton.locator(".c05-skel__bone")
            assert bones.count() == 6
            assert bones.first.evaluate(
                "(el) => getComputedStyle(el, '::after').animationName"
            ) == "c05-skel-sweep"
```

Anchor D, `App/tests/test_skeleton_loaders.py` lines 27 to 33:

```
def test_requested_skeleton_has_motion_and_accessibility_guards():
    css = (APP_DIR / "static" / "skeleton.css").read_text(encoding="utf-8")
    assert ".page-skeleton" in css
    assert ".c05-skel__bone" in css
    assert "prefers-reduced-motion:reduce" in css
    assert "animation:none!important" in css
    assert "animation-play-state:paused" in css
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/base.html` | edit | fallback skeleton via `ui_skeleton`; import; new `?v=` keys |
| `App/tests/static_versions.json` | edit | regenerated |
| `App/app/static/skeleton.css` | edit | drop the `c05` rules |
| `App/app/static/skeleton.js` | edit | pause hook on `.ui-skel` |
| `App/app/static/host2.css` | edit | paused rule for `.ui-bone` |
| `App/app/templates/_components.html` | edit | delete unused macros |
| `App/tests/test_onboarding_wizard_browser.py` | edit | Anchor C |
| `App/tests/test_skeleton_loaders.py` | edit | Anchor D |
| `App/tests/test_design_cleanup.py` | create | no `c05` anywhere; macros gone |
| `docs/tasks/0146-report.md` | create | includes the burn-down table |

No other file may change.

## 4. Steps

1. `base.html`: add as the very first line `{% from "_ui_layout.html" import ui_skeleton with context %}` and replace Anchor A with `    {{ ui_skeleton('detail') }}`. From `App/`:

```
.venv/bin/python - <<'EOF'
import pathlib, re
p = pathlib.Path("app/templates/base.html"); s = p.read_text(encoding="utf-8")
pat = re.compile(r'    <div class="c05-skel" aria-hidden="true">\n(?:.*\n)*?    </div>\n')
assert len(pat.findall(s)) == 1, len(pat.findall(s))
s = pat.sub("    {{ ui_skeleton('detail') }}\n", s)
if not s.startswith('{% from "_ui_layout.html" import ui_skeleton with context %}'):
    s = '{% from "_ui_layout.html" import ui_skeleton with context %}\n' + s
assert "c05" not in s
p.write_text(s, encoding="utf-8"); print("ok")
EOF
```

   Expected: `ok`. Command: `grep -rn "c05" App/app/templates | head`. Expected: no output (if `host_page.html` still prints `c05`, stop: 0129 was not applied as written).

2. `skeleton.css`: replace the whole file with:

```
/* Shared warm skeleton shimmer for inline placeholders (.skeleton, .g-skeleton). Page skeletons use .ui-skel from host2.css (0129, 0146). */
.skeleton, .g-skeleton { display:block;position:relative;min-height:12px;border-radius:var(--radius-xs);background:var(--surface-active);overflow:hidden }
.skeleton::after, .g-skeleton::after { content:"";position:absolute;inset:0;transform:translateX(-100%);background:linear-gradient(90deg,transparent,var(--surface) 40%,var(--canvas-subtle,var(--surface-hover)) 60%,transparent);animation:ui-sweep 1.8s cubic-bezier(.65,0,.35,1) infinite }
.skeleton-paused .skeleton::after, .skeleton-paused .g-skeleton::after { animation-play-state:paused }
@keyframes ui-sweep { 0% { transform:translateX(-100%) } 60%,100% { transform:translateX(100%) } }
@media (prefers-reduced-motion:reduce) { .skeleton::after, .g-skeleton::after, .page-skeleton, .g-page-skeleton { animation:none!important } }
```

   (`skeleton.css` is not on the lint's enforced stylesheet list; it keeps its legacy tokens.) `skeleton.js`: replace Anchor B with:

```
    document.querySelectorAll(".ui-skel").forEach(function (card) {
      card.classList.toggle("paused", document.hidden);
    });
```

   Append to `host2.css` after the 0129 skeleton rules:

```
/* 0146 skeleton pause while the tab is hidden */
.ui-skel.paused .ui-bone { animation-play-state: paused; }
```

   Bump the two cache keys in `base.html`: `skeleton.css?v=20261014-0102c` → `skeleton.css?v=20261019-v2b` and `skeleton.js?v=20261014-0102c` → `skeleton.js?v=20261019-v2b` (each occurs once; check with `grep -c`). Command: `grep -rn "c05" App/app/static App/app/templates | head`. Expected: no output.

3. Unused macros. From the repo root:

```
for m in list_page_header list_toolbar sub_tabs breadcrumb nav_icon row_reporting_actions sync_calendars_button list_section_heading; do printf "%s: " $m; grep -l "$m(" App/app/templates/*.html | grep -v _components.html | tr '\n' ' '; echo; done
```

   For every macro that prints no template after the colon, delete its whole `{% macro name(...) %}` ... `{% endmacro %}` block (and the comment line directly above it, if that comment names the macro) from `App/app/templates/_components.html`. A macro that still prints a template stays, and is listed in the report. For each deleted macro also run `grep -n "import.*\\b<name>\\b" App/app/templates/*.html` and remove the name from any `{% from "_components.html" import ... %}` list that still names it (an import of a missing macro fails only at render time, not at compile time). `page_header` stays in any case: the public documents (`dpa.html`, `legal.html`, `privacy.html`, `subprocessors.html`, `terms.html`) use it. Command: `cd App && .venv/bin/python -c "from app.templating import templates; import glob, os; [templates.env.get_template(os.path.basename(p)) for p in glob.glob('app/templates/*.html')]; print('all compiled')"`. Expected: `all compiled`.

4. Tests. Anchor C was already replaced by an earlier brief (the file already checks `.ui-bone` and `ui-pulse`); if so, leave it. Otherwise replace Anchor C with:

```
            bones = skeleton.locator(".ui-bone")
            assert bones.count() >= 6
            assert bones.first.evaluate(
                "(el) => getComputedStyle(el).animationName"
            ) == "ui-pulse"
```

   Replace Anchor D with:

```
def test_requested_skeleton_has_motion_and_accessibility_guards():
    css = (APP_DIR / "static" / "skeleton.css").read_text(encoding="utf-8")
    assert ".page-skeleton" in css
    assert "c05" not in css
    assert "prefers-reduced-motion:reduce" in css
    assert "animation:none!important" in css
    assert "animation-play-state:paused" in css
    host2 = (APP_DIR / "static" / "host2.css").read_text(encoding="utf-8")
    assert ".ui-bone" in host2 and "prefers-reduced-motion" in host2
```

   (`APP_DIR` is `App/app`). Create `App/tests/test_design_cleanup.py`:

```python
"""0146: one skeleton system, no c05 loader, dead layout macros removed."""
from __future__ import annotations

import glob
import re

REMOVED = ("list_page_header", "list_toolbar", "sub_tabs", "breadcrumb", "nav_icon", "row_reporting_actions")


def test_no_c05_markup_or_rules_remain():
    for path in glob.glob("app/templates/*.html") + glob.glob("app/static/*.css") + glob.glob("app/static/*.js"):
        assert "c05" not in open(path, encoding="utf-8").read(), path


def test_removed_macros_are_neither_defined_nor_called():
    components = open("app/templates/_components.html", encoding="utf-8").read()
    pages = "".join(open(p, encoding="utf-8").read() for p in glob.glob("app/templates/*.html") if not p.endswith("_components.html"))
    for name in REMOVED:
        assert not re.search(r"\{%\s*macro\s+" + name + r"\(", components), name
        assert name + "(" not in pages, name
```

   If step 3 kept one of the `REMOVED` names because a template still calls it, drop that name from the tuple and say so in the report. Command: `cd App && .venv/bin/python -m pytest tests/test_design_cleanup.py tests/test_skeleton_loaders.py tests/test_design_lint.py tests/test_signed_in_chrome.py tests/test_host_guest_pages.py -q --tb=short -x 2>&1 | tail -30` (drop a test file from the list if it does not exist). Expected: passed.

5. Asset versions first: in `App/app/templates/base.html` give `skeleton.css`, `skeleton.js` and `host2.css` new `?v=` keys ending in `-0146` (grep `?v=` to find them), then from `App/`: `.venv/bin/python tests/test_static_versions.py --write && .venv/bin/python -m pytest tests/test_static_versions.py -q 2>&1 | tail -3` (passed). Browser: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_SHOTS_DIR=/tmp/ubyhost-shots .venv/bin/python -m pytest tests/test_onboarding_wizard_browser.py tests/test_download_skeleton_browser.py tests/test_host_controls_browser.py tests/test_design_guardrails_browser.py -q -rs --tb=short 2>&1 | tail -30` (foreground, timeout 600000), then from the repo root `git checkout -- docs/tasks/0102-evidence; git clean -fdq docs/tasks/0102-evidence`. Expected: passed, 0 skipped. Attach one screenshot of a host page while the skeleton shows (the onboarding wizard test writes one when `UBYHOST_SHOTS_DIR` is set; otherwise `skeleton-1280.png` from `page.evaluate("window.ubyhostSkeleton.start()")` on `/reservations`).

6. Burn-down table, from the repo root (output goes into the report, section "Legacy burn-down"):

```
python3 - <<'EOF' | head -50
import json, re, glob, collections
cat = json.load(open("docs/design/catalog.json"))
legacy = collections.Counter()
for tpl, names in cat.get("legacy", {}).items():
    for n in names: legacy[n] += 1
print("legacy tokens still allowlisted (token: templates):", len(legacy))
print(", ".join(f"{k}:{v}" for k, v in legacy.most_common(40)))
for css in ("App/app/static/host-controls.css", "App/app/static/host-design0123.css"):
    text = open(css, encoding="utf-8").read()
    classes = sorted(set(re.findall(r"\.([a-zA-Z][a-zA-Z0-9_-]*)", re.sub(r"\{[^}]*\}", "", text))))
    pages = "".join(open(p, encoding="utf-8").read() for p in glob.glob("App/app/templates/*.html"))
    js = "".join(open(p, encoding="utf-8").read() for p in glob.glob("App/app/static/*.js"))
    dead = [c for c in classes if c not in pages and c not in js]
    print(css, "selectors:", len(classes), "unreferenced:", len(dead))
    print("  unreferenced:", ", ".join(dead))
EOF
```

   Expected: two stylesheet lines each with an `unreferenced:` list. Copy the output verbatim into the report. Do not delete anything based on it.

7. Commit: `git add App/app/templates App/app/static App/app/static/host2.css App/tests docs/tasks/0146-report.md && git commit -m "0146 step 7: one skeleton, dead macros removed, legacy burn-down"`.

## 5. Do not touch

`host-controls.css`, `host-design0123.css`, `host.css`, `app.css`, `components.css`, `cleaning.css`, `host_page.html`, `_ui.html`, `_ui_layout.html`, `page_header` and `empty_state` macros, public templates; hard rules 2, 3, 8.

## 6. Commands

- `python3 scripts/design_lint.py` expected: OK.
- Step 4, 5 and 6 commands.

## 7. Acceptance

- [ ] No `c05` string anywhere under `App/app`; the fallback skeleton on a non-host page renders `.ui-skel` markup.
- [ ] Every macro in `_components.html` is called by at least one template.
- [ ] Burn-down table in the report.
- [ ] Screenshot attached; lint OK.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a template still prints `c05` after step 1; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0146-report.md` (800 tokens at most, the burn-down table included) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/templates/_components.html` (deleting a macro a template imports but never calls breaks that template at render time; step 3's compile check covers imports since Jinja resolves `from ... import` at load time).

## Owner steps

Decide, from the burn-down table, whether `host-controls.css` and `host-design0123.css` get a deletion brief (0147) or stay until the legacy allowlists are empty.
