# 0246: "What needs you" review fixes

Status: todo
Depends on: 0245 | Base commit: after 0245 | Branch: claude/project-thread-0io75h
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Two things the reviewer saw in the 0243 screenshots (`/mnt/project-files/foolproof-round2/dashboard/`):

1. The sample property ("Vinohrady Studio (demo)") gets a "Police details are missing" line. The sample property never reports to the police, so the line is noise. Sample properties get no setup line.
2. "How to paste it" sits at the bottom of the card, away from the paste line it explains, and it stays visible even when that line is folded under "Show 1 more". It moves inside the paste line, under its sentence.

## 2. Context

- `needs_you.build` adds one `setup` line per row of `missing_rows`; `demo.is_demo_apartment(apartment)` tells a sample property (import `demo` locally, as `stay_line` does).
- `dashboard.html`: macro `needs_you_line(line)` renders `li.needs-you-item` (grid: copy, actions); the card-level `<details class="needs-you-more" data-paste-check>` follows the lists.
- `workflow.css` has the `needs-you*` rules; a changed CSS file needs a new `?v=` key in `base.html` and the manifest refresh.
- `test_paste_check_0233.py` checks `data-paste-check` on "/", so the attribute stays on the how-to.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/needs_you.py` | edit | no setup line for a sample property (step 1) |
| `App/app/templates/dashboard.html` | edit | how-to inside the paste line (step 2) |
| `App/app/static/workflow.css` | edit | one rule (step 3) |
| `App/app/templates/base.html` | edit | cache key (step 3) |
| `App/tests/static_versions.json` | edit | manifest refresh (step 3) |
| `App/tests/test_needs_you_0240.py` | edit | one test (step 4) |
| `App/tests/test_host_quiet_dashboard_browser.py` | edit | two lines (step 4) |
| `docs/tasks/0246-report.md` | create | report |

No other file may change.

## 4. Steps

### Step 1. `needs_you.py`

Anchor (these exact lines):

```python
    for row in missing_rows or []:
        apartment = row["apartment"]
        if apartment["id"] in setup_alerts or not row.get("missing"):
            continue
```

Replace with:

```python
    from . import demo  # local: demo imports many modules

    for row in missing_rows or []:
        apartment = row["apartment"]
        if apartment["id"] in setup_alerts or not row.get("missing"):
            continue
        if demo.is_demo_apartment(apartment):
            continue  # the sample property never reports to the police
```

Command: `cd App && .venv/bin/python -m pytest tests/test_alert_stack.py tests/test_needs_you_0240.py tests/test_dashboard_missing_banner.py -q --tb=short 2>&1 | tail -10` → pass. Commit `0246 step 1`.

### Step 2. `dashboard.html`

2a. In the macro, anchor (exact line):

```jinja
  <div class="needs-you-copy"><strong>{{ line.subject }}</strong>{% if line.text %}<span>{{ line.text }}</span>{% endif %}</div>
```

Replace with:

```jinja
  <div class="needs-you-copy"><strong>{{ line.subject }}</strong>{% if line.text %}<span>{{ line.text }}</span>{% endif %}</div>
  {% if line.kind == 'paste' %}
  <details class="needs-you-more" data-paste-check><summary>{{ t('workflow.paste.how') }}</summary>
    <ul class="needs-you-how">
      <li>{{ t('workflow.paste.airbnb') }}</li>
      <li>{{ t('workflow.paste.booking') }}</li>
      <li>{{ t('workflow.paste.direct') }}</li>
    </ul>
  </details>
  {% endif %}
```

2b. Delete these exact lines (the card-level how-to):

```jinja
    {% if ny_lines | selectattr('kind', 'equalto', 'paste') | list %}
    <details class="needs-you-more" data-paste-check><summary>{{ t('workflow.paste.how') }}</summary>
      <ul class="needs-you-how">
        <li>{{ t('workflow.paste.airbnb') }}</li>
        <li>{{ t('workflow.paste.booking') }}</li>
        <li>{{ t('workflow.paste.direct') }}</li>
      </ul>
    </details>
    {% endif %}
```

Command: `cd App && grep -c 'data-paste-check' app/templates/dashboard.html` → `1`. Commit `0246 step 2`.

### Step 3. CSS and cache key

3a. In `App/app/static/workflow.css`, directly after the line that starts `.needs-you-more > .needs-you-list, .needs-you-how {`, add:

```css
/* 0246: the paste how-to sits in its line, under the sentence, full width. */
.needs-you-item > .needs-you-more { grid-column: 1 / -1; grid-row: 2; margin-top: 0; }
```

3b. In `base.html` replace `/static/workflow.css?v=20261022-0244` with `/static/workflow.css?v=20261022-0246`. If the current key is not `20261022-0244`, replace whatever `workflow.css?v=` key is there and say so in the report.

3c. Command: `cd App && .venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5 && .venv/bin/python -m pytest tests/test_alert_stack.py tests/test_static_versions.py tests/test_paste_check_0233.py -q --tb=short 2>&1 | tail -5` → pass. Commit `0246 step 3`.

### Step 4. Tests

4a. `test_needs_you_0240.py`: append at the end of the file:

```python


def test_the_sample_property_gets_no_setup_line():
    """0246: the sample property never reports to the police, so no setup nag."""
    from app import demo

    sample = {"id": 99, "internal_name": demo.DEMO_APARTMENT, "active": 1}
    missing = [{"apartment": sample, "missing": [{"anchor": "ubyport"}]}]
    built = needs_you.build([], {}, [], missing, [], "en", date(2026, 10, 22))
    assert [line for line in built["lines"] if line["kind"] == "setup"] == []
```

If `needs_you` or `date` is not imported at the top of that file, add the import (`from app import needs_you`, `from datetime import date`) and say so in the report. If `demo.is_demo_apartment` needs more fields than `internal_name` to recognise the sample, read `app/demo.py` `is_demo_apartment` and add only the field it reads.

4b. `test_host_quiet_dashboard_browser.py`, in `test_dashboard_rich_needs_you_order_cap_and_geometry`, replace these exact lines:

```python
                    if "paste" in page.locator(".needs-you-item").evaluate_all("nodes => nodes.map(node => node.dataset.needsYou)"):
                        assert page.locator(".needs-you-more[data-paste-check] > summary").is_visible(), label
```

with:

```python
                    paste_line = page.locator('.needs-you-item[data-needs-you="paste"]')
                    if paste_line.count() and paste_line.first.is_visible():
                        how = paste_line.first.locator("[data-paste-check] > summary")
                        assert how.is_visible(), label
                        how_box, copy_box = how.bounding_box(), paste_line.first.locator(".needs-you-copy").bounding_box()
                        assert how_box["y"] >= copy_box["y"] + copy_box["height"] - 1, (label, how_box, copy_box)
                    assert page.locator('.needs-you-item[data-needs-you="setup"]', has_text="(demo)").count() == 0, label
```

Command: `cd App && PLAYWRIGHT_BROWSERS_PATH=/tmp/claude-0/pw UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_alert_stack.py tests/test_needs_you_0240.py tests/test_host_quiet_dashboard_browser.py -q --tb=short -rs 2>&1 | tail -10` → pass, 0 skipped. Commit `0246 step 4`.

## 5. Do not touch

Everything outside §3.

## 6. Commands

From `App/` with `export PLAYWRIGHT_BROWSERS_PATH=/tmp/claude-0/pw UBYHOST_REQUIRE_BROWSER=1`, `tests/test_alert_stack.py` first:

1. `.venv/bin/python -m pytest tests/test_alert_stack.py tests/test_needs_you_0240.py tests/test_needs_you_dashboard_0241.py tests/test_dashboard_missing_banner.py tests/test_paste_check_0233.py tests/test_static_versions.py tests/test_design_lint.py -q --tb=short 2>&1 | tail -10`
2. `UBYHOST_SHOTS_DIR=/mnt/project-files/foolproof-round2/dashboard .venv/bin/python -m pytest tests/test_alert_stack.py tests/test_host_quiet_dashboard_browser.py tests/test_dashboard_phone_browser.py -q --tb=short -rs 2>&1 | tail -10` (refreshes the screenshots)

## 7. Acceptance

- [ ] §6 commands 1 and 2 pass with 0 skipped.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found; a test fails twice; you reach 25 tool calls; a file outside §3 needs a change; a step is unclear.

## 9. Report

Write `docs/tasks/0246-report.md` (600 tokens at most) with the last lines of each command, and set `Status: review`. Do not push or open a PR.

## Risk list (for the reviewer)

`dashboard.html` (paste how-to position), `workflow.css` plus cache key.

## Owner steps

None.
