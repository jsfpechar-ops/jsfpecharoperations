# 0070: Extract the existing property editor without changing behavior

Status: blocked — depends on reviewed 0069 and its green baseline; orchestrator sets todo after verification.
Depends on: 0069 done | Base source: 0e8e468f6f8a7d4e33109493c115f580e0006504 | Branch: task/0070-property-editor-extraction | PR base: task/host-navigation-integration
Patch status: ready — exact extraction command below; verify against reviewed integration HEAD before release.
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

Extract the current full property form and calendar block into canonical Jinja partials without changing their content or save behavior. This gives later navigation one editor implementation instead of copied desktop/tab/standalone forms.

## 2. Context

Read AGENTS.md, the execution protocol and the reviewed 0069 report/inventory. Designs are approved; this phase is structural only. Exact anchors in App/app/templates/apartment_form.html:

```jinja
{% set more_open = more_options_open|default(false) or copied_from_name %}
<form method="post" action="{{ '/apartments/' ~ apartment.id if editing else '/apartments' }}">
```

```jinja
{% if editing %}
<h2 id="calendars">{{ t('apartments.table.calendars') }}</h2>
```

The form must retain its hidden Enter-default submit, field names/defaults, copied-property values, return_to, formaction buttons, nested details, shared fee/account includes and all create/edit conditions. Keep the parent macros/context available to includes.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/apartment_form.html` | edit | Replace only the exact original form/calendar spans with canonical includes |
| `App/app/templates/_property_settings_form.html` | create | Byte-preserved original full property form |
| `App/app/templates/_property_calendars.html` | create | Byte-preserved original conditional calendar block |
| `docs/tasks/0070-property-editor-extraction.md` | edit | Lifecycle status only |
| `docs/tasks/0070-report.md` | create | Required report |
| `docs/tasks/0070-evidence/` | create | Synthetic screenshots and focused equivalence evidence only |

Read-only tests: test_property_form_save.py, test_property_form_nav.py, test_property_hub.py, test_property_readiness.py, test_copy_property_settings.py, test_stay_fee_property_panel.py, test_host_property_controls_browser.py, test_host_wide_geometry_browser.py, test_host_redesign.py, plus their existing fixtures/helpers. No tests change in this extraction.

## 4. Steps

1. Confirm 0069 is done, baseline prerequisites satisfied, branch/base recorded, source anchors unchanged and no pre-existing user changes overwritten. Capture existing property/create page screenshots and relevant form control names/actions using synthetic fixtures. Verify one full form and the separate calendar forms in rendered HTML before the patch.
2. Execute this complete command from repo root once. It refuses if anchors or target partials are unexpected. Do not relax its assertions to fit a different revision; obtain a corrected exact patch instead.

```python
from pathlib import Path

root = Path("App/app/templates")
page = root / "apartment_form.html"
form_target = root / "_property_settings_form.html"
calendar_target = root / "_property_calendars.html"
source = page.read_text(encoding="utf-8")
form_marker = '<form method="post" action="{{ \'/apartments/\' ~ apartment.id if editing else \'/apartments\' }}">'
calendar_marker = '{% if editing %}\n<h2 id="calendars">'
assert source.count(form_marker) == 1, "Property form anchor changed"
assert source.count(calendar_marker) == 1, "Calendar anchor changed"
assert not form_target.exists(), "Form partial already exists; do not overwrite"
assert not calendar_target.exists(), "Calendar partial already exists; do not overwrite"
form_start = source.index(form_marker)
form_end = source.index("</form>", form_start) + len("</form>")
calendar_start = source.index(calendar_marker, form_end)
calendar_end = source.index("\n{% endblock %}", calendar_start)
form = source[form_start:form_end]
calendars = source[calendar_start:calendar_end]
assert form.count('<form ') == 1 and form.count('</form>') == 1
assert 'hidden tabindex="-1" aria-hidden="true"' in form
assert 'id="automation"' in form and 'id="communication"' in form
assert 'id="stay-fee-settings"' in form and 'name="notes"' in form
assert '{% include "_stay_fee_fields.html" %}' in form
assert '/test-connection' in form and '/refresh-codelists' in form
assert 'regenerate-link' in form and 'regenerate-pin' in form
assert 'method="post"' in calendars and '/feeds' in calendars
updated = (source[:form_start] + '{% include "_property_settings_form.html" %}'
           + source[form_end:calendar_start] + '{% include "_property_calendars.html" %}'
           + source[calendar_end:])
assert updated.count('{% include "_property_settings_form.html" %}') == 1
assert updated.count('{% include "_property_calendars.html" %}') == 1
form_target.write_text(form + "\n", encoding="utf-8")
calendar_target.write_text(calendars + "\n", encoding="utf-8")
page.write_text(updated, encoding="utf-8")
print("Extracted one canonical property form and one calendar block")
```

Run the Python block as a local Python script/heredoc; the code above is the entire implementation. Do not add any CSS, JS, API handler, field normalization, label change, new tab or draft handling in this phase.

3. Confirm rendered HTML/control actions and successful-control names are equivalent for existing/create/copy/incomplete/fee-enabled/lock-available states. Existing property saving, Enter behavior, credentials actions and calendar actions remain identical. Include contexts must preserve all parent macro/data access. A Jinja error is a failed extraction, not permission to duplicate the form back into the parent.
4. Run §6, capture real after screenshots at required sizes and link evidence. Check no original form copy remains in the parent; unique IDs/names occur as before in the rendered DOM (conditional branches do not create duplicate rendered fields).
5. Write the report, set review and stop. PR targets integration. The next task adds the approved navigation only after this review.

## 5. Do not touch

All backend routes, business logic, CSS/JS, translations, guest pages, PDF/export code, migrations, dependency/CI/deploy files, existing tests or source anchors outside the extracted spans. No behavior change, duplicated rendering or new partial save.

## 6. Commands

From App, run focused tests with REQUIRE_BROWSER=1, staging/mock/scheduler-off as in the protocol:

```bash
.venv/bin/python -m pytest tests/test_property_form_save.py tests/test_property_form_nav.py tests/test_property_hub.py tests/test_property_readiness.py tests/test_copy_property_settings.py tests/test_stay_fee_property_panel.py tests/test_host_property_controls_browser.py tests/test_host_wide_geometry_browser.py -q -rs
```

Then run the protocol's full suite/coverage/ruff and root context lint/diff checks. Required browser/geometry zero skips; synthetic screenshots 360/390/1280 minimum and wide measured evidence through 2048, EN/CS. Expected: current regression baseline remains green; control names/payload/action targets unchanged. If a source-location assertion fails despite equivalent behavior, stop for a scoped correction brief instead of modifying tests here.

## 7. Acceptance

- [ ] Exact spans extracted once; parent includes each partial once.
- [ ] Full form controls/actions/create-edit defaults/conditional guards unchanged.
- [ ] Calendar forms remain outside the property form; no nested forms.
- [ ] Enter saves, test saves-before-test, refresh/regenerate and omitted fields unchanged.
- [ ] Relevant regression/full/coverage checks green; required browser/geometry 0 skips.
- [ ] Real synthetic before/after screenshots and control equivalence evidence linked.
- [ ] Diff exactly matches §3; no test/dependency/schema/logic change.

## 8. Stop and ask

Stop/report on absent anchors, existing partial targets, unreviewed prerequisite, unexpected macro context, any scope expansion, new dependency, failed baseline, required skipped checks or two failures of the same test. No main merge, secrets/provider operation or deployment. The orchestrator must issue the correction; do not improvise.

## 9. Report

Write docs/tasks/0070-report.md (<=1500 tokens), mark review: base/ending SHA, changed paths/stat, focused/full results and skips, §7 ticked with links, control equivalence, screenshot/geometry evidence, deviations and exact next-task risks. Publication, review and merge follow the integration-only protocol.

## Risk list (for the reviewer)

Read apartment_form.html and both new partials. Confirm every extracted byte is preserved and include context renders correctly. Inspect test evidence especially hidden Enter/default and formaction behavior.

## Owner steps

1. Review 0070 report and current-head CI/scope.
2. Confirm the PR base is task/host-navigation-integration before guarded merge.
3. Have the orchestrator release the exact 0071 patch against that reviewed tip.
