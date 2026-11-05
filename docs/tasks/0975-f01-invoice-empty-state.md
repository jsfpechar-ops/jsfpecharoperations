# 0975-f01: Invoice empty state says where invoices come from

Status: todo
Depends on: B01 to B16 merged (master plan B17) | Base commit: 7b0355c45ccdd2557a28edfcfe228aa1dc766e36 | Branch: task/0975-f01
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The empty Invoices list gains one sentence under its title: an invoice is always issued for a stay. It reuses the existing picker copy, so no new text and no new key.

## 2. Context

Finding F01 is an "Opportunity" in the review (not a confirmed defect). Rules: one explanation lives in one place; no new dependency; no behaviour change; light mode only.
`App/app/templates/invoices.html` already calls the shared `empty_state(title, body, ...)` macro (App/app/templates/_components.html line 287, not edited). Current anchor: `{{ empty_state(t('invoices.empty_title')) }}` (once, in the `{% else %}` of `{% if filter_active %}`). The key `invoice.picker.lede` is "An invoice is always issued for a stay." (EN, host_i18n.py ~1740; CS and VI exist).
Deliberately NOT included: a second "Issue invoice" button inside the empty block. The head already carries it and `tests/test_host_list_page_layout_browser.py::test_empty_states_use_the_shared_component` asserts the empty block has no button (0818); the owner can overrule that later as its own brief.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/invoices.html | edit | pass the body line to `empty_state` |
| App/tests/test_host_invoice_navigation.py | edit | one new test |

No other file may change.

## 4. Steps

1. Save the patch below to `/tmp/0975-f01.patch` (exact text), run `git apply --check /tmp/0975-f01.patch`. If it fails, STOP (anchor moved; brief §8).
2. `git apply /tmp/0975-f01.patch`, then commit `0975 step 1`.
3. Run §6, one test row at a time. Commit `0975 step 2` if you changed anything to fix a first failure (once only).

```diff
diff --git a/App/app/templates/invoices.html b/App/app/templates/invoices.html
index 550bf6a9..c5095416 100644
--- a/App/app/templates/invoices.html
+++ b/App/app/templates/invoices.html
@@ -76,7 +76,7 @@
 {% if filter_active %}
 {{ empty_state(t('filter.no_results'), '', filter_reset_href, t('filter.reset'), primary=false) }}
 {% else %}
-{{ empty_state(t('invoices.empty_title')) }}
+{{ empty_state(t('invoices.empty_title'), t('invoice.picker.lede')) }}
 {% endif %}
 {% endif %}
 </div>
diff --git a/App/tests/test_host_invoice_navigation.py b/App/tests/test_host_invoice_navigation.py
index 3b0b6f17..7119c974 100644
--- a/App/tests/test_host_invoice_navigation.py
+++ b/App/tests/test_host_invoice_navigation.py
@@ -88,6 +88,14 @@ def test_list_and_picker_link_to_settings(world):
     assert details in picker
 
 
+def test_empty_list_says_invoices_come_from_a_stay(world):
+    html = world["client"].get("/invoices?lang=en").text
+    empty = html[html.index("data-empty-state"):]
+    assert "No invoices yet" in empty
+    assert "<p>An invoice is always issued for a stay.</p>" in empty
+    assert "ui-btn" not in empty[: empty.index("</div>")]  # the head still carries the action (0818)
+
+
 def test_builder_shows_stay_and_unfolds_options_without_changing_fields(world):
     client = world["client"]
     html = client.get(f"/invoices/new?reservation_id={world['stay']}&entity={world['entity']}").text
```

## 5. Do not touch

App/app/static/*, `_components.html`, `host_i18n.py` (no new key), filing code. Never push or merge.

## 6. Commands

From `App/`; every command ends `2>&1 | tail -30`. `export UBYHOST_SHOTS_DIR=/tmp/ubyhost-b17` first (create it with `mkdir -p`).

```
.venv/bin/python -m pytest tests/test_host_invoice_navigation.py -k empty_list -q --tb=short -x -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_invoice_*.py tests/test_stay_fee*.py -q --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py -q --tb=short -x -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_layout_lint_browser.py tests/test_0710_v2_mockup_match_browser.py -q --tb=short -x -rs 2>&1 | tail -30
```
0 skipped in every browser file. (Test-map rows: Invoices; host pages; any host template; v2 pages.)

Screenshots: `test_layout_lint_browser.py` writes 390/768/1280 PNGs of host pages to `$UBYHOST_SHOTS_DIR/layout-lint`. The Invoices page is only reached with no invoices when the workspace is new; if the lint run has no empty-invoices PNG, the owner-facing check is the populated-account screenshot plus the new unit test. Open the Invoices (empty) PNGs at 390, 768 and 1280 once each. Repeat the visual check with `?lang=cs` (EN and CS, Chromium). If no PNG for the page exists after the run, STOP and report `blocked`; do not write a new screenshot script.

## 7. Acceptance

- [ ] `git apply --check` passed and the diff touches only the two files.
- [ ] Empty list shows title, one sentence, no second button (EN and CS); populated list and filtered empty state unchanged.
- [ ] No horizontal scroll at 390/768/1280; sentence wraps cleanly (long Czech included).
- [ ] All §6 commands green, 0 skipped.
- [ ] Per page, one line in the PR of what you saw (UX gate).

## 8. Stop and ask

Stop and write the report (`docs/tasks/0975-f01-report.md`, `Status: review` or `blocked`) if: the patch does not apply; a test fails twice; a test is skipped; a file outside §3 needs a change; 25 tool calls or about 50k tokens are reached; push, merge or deploy would be needed (hand to the owner).

## 9. Report

Files changed (`git diff --stat`), each command's last 5 lines, §7 ticked, deviations, questions, owner steps left.
