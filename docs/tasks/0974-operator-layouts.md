# 0974: Operator Customers and Billing layouts (B16, findings A01, A02)

Status: blocked (tool-call cap; host guard run incomplete; 6 of 19 screenshots inspected)
Depends on: B03, B14, B15 (not needed; run on base) | Base commit: 7b0355c45ccdd2557a28edfcfe228aa1dc766e36 | Branch: codex/0974-b16-operator
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Split decision: NOT split. Customers needs 4 small template edits plus CSS, Billing 5 form edits; both share one stylesheet and one test append. Everything is already written as two patches below, so the executor only applies them. If you reach 25 tool calls, stop at the step you are on (executor.md).

## 1. Objective

Customers: the six metrics become a balanced grid (2 x 3 on a phone, 3 x 2 from 768 px) and the create-host form sits at normal form width (max 560 px) left-aligned in the content lane, with one primary action. Billing: each label sits directly above its own field, fields and buttons share one control height (40 px desktop, 44 px under 1024 px), Show is the primary action and the accountant export is a secondary download link.

## 2. Context

Root causes found on base (verify with the anchors, STOP if absent):

- `App/app/templates/admin_customers.html`: the create-host `<section class="ui-section" id="create-host">` sits INSIDE the pager `<nav class="ui-form-actions" aria-label=...>` (flex, `justify-content:flex-end` from app2.css), which pushes it into a narrow right column. Anchors (grep -nF):
  - `{{ ui_stats(stats, label=t('customers.overview')) }}`
  - `{% if newer_url or older_url %}{{ ui_button(t('customers.reset'), 'quiet', href=href()) }}{% endif %}`
  - `<button class="ui-btn ui-btn-primary" type="submit">{{ t('users.create.submit') }}</button>`
  - `</section>` followed by `</nav>` before `{% endblock %}`
- `App/app/templates/admin_billing.html`: labels `class="admin-label"` and inputs sit directly inside `<form class="ui-form-actions">` (flex, `justify-content:flex-end`), so labels float right of the controls. Anchors:
  - `<label class="admin-label" for="month-pick">`
  - `<label class="admin-label" for="portfolio-q">`
  - `<label class="admin-label" for="statement-file">`
  - `<label class="admin-label" for="paid-{{ inv.id }}">`
  - `<label class="admin-label" for="reason-{{ inv.id }}">`
  - `{{ ui_button(t('billing.admin.month.export'), 'primary', href='/admin/fakturace/export?mesic=' ~ month) }}`
- Reused existing components (no new component): macros `ui_field`, `ui_select`, `ui_button` (icon_name='download', attrs='download') from `_ui.html`; classes `ui-field`, `ui-stats`, `ui-stat`, `ui-form-actions`, `ui-btn-*`; tokens `--control-h` (40px) and `--control-h-phone` (44px) from tokens.css.
- New scoped stylesheet `App/app/static/admin2-operator-0974.css`, referenced only by admin_customers.html and admin_billing.html (a change to shared admin2.css would force a key bump in four other templates, so it is not touched).
- Element ids are kept (`month-pick`, `portfolio-q`, `portfolio-state`, `statement-file`, `paid-<id>`, `reason-<id>`, `display_name`, `email`, `create-host`) and so are `data-billing-admin-*` attributes and form actions and field names.
- Validation behaviour (unchanged, do not "improve"): the create-host e-mail input has `required` and `type=email`, so an empty submit is stopped by the browser before any request. The server error path (`routes/admin_accounts.py` user_create) redirects with a flash banner; moving it next to the field needs a route change, which is out of scope. Report this as an observation, not a defect you fix.
- Hard rules that apply: no host creation, no statement upload, no payment, no export disclosure change, no permissions change (tests never submit a valid create-host form, never upload, never click the export link); light mode only; Chromium only with synthetic operator fixtures from `tests/test_0893_admin_airbnb_browser.py` (`host`, `base`); screenshots only under /tmp/ubyhost-b16; do not open them in the PR or commit them.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/admin_customers.html | edit (patch A) | metrics wrapper, close pager nav before the form, form actions wrapper, stylesheet link |
| App/app/templates/admin_billing.html | edit (patch A) | five forms use `admin-controls` + `ui_field`/`ui_select`, Show primary, exports secondary download, stylesheet link |
| App/app/static/admin2-operator-0974.css | new (patch A) | scoped styles |
| App/tests/static_versions.json | edit (patch A) | entry for the new stylesheet |
| App/tests/test_0894_admin_airbnb_billing_ops_browser.py | append (patch B) | B16 browser tests |
| docs/tasks/0974-report.md | new | report |

No other file may change.

## 4. Steps

Run everything from the worktree root `/tmp/ubyhost-b16-worktree` unless stated. Commit message per step: `0974 step k` with trailer `Co-authored-by: Codex <noreply@openai.com>`.

### Step 1. Prepare

```
cd /tmp/ubyhost-b16-worktree && git status --short | tail -5 && git rev-parse HEAD | tail -1
ln -s /tmp/ubyhost-0958-worktree/App/.venv App/.venv && ls App/.venv/bin/python | tail -1
for a in "id=\"create-host\"" "<label class=\"admin-label\" for=\"month-pick\">" "<label class=\"admin-label\" for=\"statement-file\">"; do grep -c -F -- "$a" App/app/templates/admin_customers.html App/app/templates/admin_billing.html; done 2>&1 | tail -10
```
Expected: clean status, HEAD 7b0355c4..., python path printed, counts show one match for each anchor in the right file. `.venv` is ignored by git; never commit it. Any anchor missing: STOP.

### Step 2. Apply patch A (templates, stylesheet, static manifest)

Write the patch with the quoted heredoc exactly as below, then check and apply:
```
cat > /tmp/b16_code.diff <<'B16EOF'
diff --git a/App/app/static/admin2-operator-0974.css b/App/app/static/admin2-operator-0974.css
new file mode 100644
index 00000000..46ec6113
--- /dev/null
+++ b/App/app/static/admin2-operator-0974.css
@@ -0,0 +1,18 @@
+/* 0974: operator Customers and Billing layouts. Loaded only by admin_customers.html and admin_billing.html. Light mode only. */
+/* Customers: six metrics as 2 x 3 on a phone and 3 x 2 from 768 px; long labels wrap inside their card */
+body.v2 .customers-metrics .ui-stats{grid-template-columns:repeat(2,minmax(0,1fr))}
+@media (min-width:768px){body.v2 .customers-metrics .ui-stats{grid-template-columns:repeat(3,minmax(0,1fr))}}
+body.v2 .customers-metrics .ui-stat{min-width:0}
+body.v2 .customers-metrics .ui-stat span{overflow-wrap:anywhere}
+/* Customers: the create-host form at a normal form width, left aligned in the content lane */
+body.v2 #create-host{max-width:560px;margin-top:32px}
+body.v2 #create-host .ui-field{width:100%;min-width:0}
+body.v2 #create-host .ui-input{width:100%;box-sizing:border-box}
+body.v2 #create-host .ui-form-actions{justify-content:flex-start}
+/* Billing: each label sits above its own field; fields and buttons share the control height token (40 px, 44 px under 1024 px) and one bottom line */
+body.v2 .admin-controls{display:flex;flex-wrap:wrap;align-items:flex-end;gap:12px 16px}
+body.v2 .admin-controls>.ui-field{flex:1 1 200px;max-width:320px;min-width:0;margin:0}
+body.v2 .admin-controls .ui-input,body.v2 .admin-controls .ui-select{box-sizing:border-box;width:100%}
+body.v2 .ui-body .admin-controls input[type="file"]{min-height:var(--control-h,40px)}
+body.v2 .admin-controls .ui-btn{box-sizing:border-box;height:var(--control-h,40px);min-height:var(--control-h,40px);display:inline-flex;align-items:center;justify-content:center;gap:8px}
+@media (max-width:1023.98px){body.v2 .admin-controls .ui-btn{height:var(--control-h-phone,44px)}}
diff --git a/App/app/templates/admin_billing.html b/App/app/templates/admin_billing.html
index 4967e6ad..a6237749 100644
--- a/App/app/templates/admin_billing.html
+++ b/App/app/templates/admin_billing.html
@@ -2,7 +2,7 @@
     Data: routes/admin_billing.py, app/billing_admin.py, app/bank_import.py. -#}
 {% extends "host_page.html" %}
 {% set v2 = true %}
-{% block head_extra %}<link rel="stylesheet" href="/static/admin2.css?v=20261102-0893o"><link rel="stylesheet" href="/static/admin2-system.css?v=20261102-0894e">{% endblock %}
+{% block head_extra %}<link rel="stylesheet" href="/static/admin2.css?v=20261102-0893o"><link rel="stylesheet" href="/static/admin2-system.css?v=20261102-0894e"><link rel="stylesheet" href="/static/admin2-operator-0974.css?v=20261105-0974a">{% endblock %}
 {% from "_components.html" import tip_label with context %}
 {% set nav = 'billing_admin' %}
 {% set body_kind = 'detail' %}
@@ -47,18 +47,16 @@
 </tr>
 <tr class="ui-row ui-row-actions">
   <td colspan="4">
-    <form method="post" action="/admin/fakturace/{{ inv.id }}/zaplaceno" class="ui-form-actions">
+    <form method="post" action="/admin/fakturace/{{ inv.id }}/zaplaceno" class="admin-controls">
       <input type="hidden" name="_csrf" value="{{ csrf_token }}">
-      <label class="admin-label" for="paid-{{ inv.id }}">{{ t('billing.admin.paid.date') }}</label>
-      <input class="ui-input" type="date" id="paid-{{ inv.id }}" name="paid_on" value="{{ today }}" required>
+      {{ ui_field('paid-' ~ inv.id, t('billing.admin.paid.date'), name='paid_on', value=today, type='date', attrs='required') }}
       {{ ui_button(t('billing.admin.paid.submit'), 'secondary', type='submit') }}
     </form>
     <details>
       <summary>{{ t('billing.admin.storno.open') }}</summary>
-      <form method="post" action="/admin/fakturace/{{ inv.id }}/storno" class="ui-form-actions">
+      <form method="post" action="/admin/fakturace/{{ inv.id }}/storno" class="admin-controls">
         <input type="hidden" name="_csrf" value="{{ csrf_token }}">
-        <label class="admin-label" for="reason-{{ inv.id }}">{{ t('billing.admin.storno.reason') }}</label>
-        <input class="ui-input" type="text" id="reason-{{ inv.id }}" name="reason" maxlength="200" required>
+        {{ ui_field('reason-' ~ inv.id, t('billing.admin.storno.reason'), name='reason', attrs='maxlength="200" required') }}
         {{ ui_button(t('billing.admin.storno.submit'), 'danger', type='submit') }}
       </form>
     </details>
@@ -70,11 +68,10 @@
 {% endcall %}
 
 {% call ui_section(tip_label(t('billing.admin.month.title'), 'month-help', t('billing.admin.month.export_help'), tag='span'), id='month') %}
-<form method="get" action="/admin/fakturace" class="ui-form-actions">
-  <label class="admin-label" for="month-pick">{{ t('billing.admin.month.pick') }}</label>
-  <input class="ui-input" type="month" id="month-pick" name="mesic" value="{{ month }}">
-  {{ ui_button(t('billing.admin.month.show'), 'secondary', type='submit') }}
-  {{ ui_button(t('billing.admin.month.export'), 'primary', href='/admin/fakturace/export?mesic=' ~ month) }}
+<form method="get" action="/admin/fakturace" class="admin-controls">
+  {{ ui_field('month-pick', t('billing.admin.month.pick'), name='mesic', value=month, type='month') }}
+  {{ ui_button(t('billing.admin.month.show'), 'primary', type='submit') }}
+  {{ ui_button(t('billing.admin.month.export'), 'secondary', href='/admin/fakturace/export?mesic=' ~ month, icon_name='download', attrs='download') }}
 </form>
 {% if invoices %}
 {{ ui_table_begin([(t('billing.admin.col.number'), ''), (t('billing.admin.col.buyer'), ''), (t('billing.admin.col.amount'), 'r'), (t('billing.admin.col.state'), 'r')], label=t('billing.admin.month.title')) }}
@@ -95,16 +92,13 @@
 <details class="ui-section" id="reports"><summary>{{ t('billing.admin.reports') }}</summary>
 
 {% call ui_section(t('billing.admin.portfolio.title'), id='portfolio') %}
-<form method="get" action="/admin/fakturace" class="ui-form-actions" data-billing-admin-portfolio-filter>
-  <label class="admin-label" for="portfolio-q">{{ t('billing.admin.portfolio.search') }}</label>
-  <input class="ui-input" type="search" id="portfolio-q" name="q" value="{{ q }}" placeholder="{{ t('billing.admin.portfolio.search_placeholder') }}">
-  <label class="admin-label" for="portfolio-state">{{ t('billing.admin.portfolio.state') }}</label>
-  <select class="ui-input" id="portfolio-state" name="state">
-    <option value="">{{ t('billing.admin.portfolio.all') }}</option>
-    {% for s in states %}<option value="{{ s }}"{% if state == s %} selected{% endif %}>{{ t('billing.plan.state.' ~ s) }}</option>{% endfor %}
-  </select>
-  {{ ui_button(t('billing.admin.portfolio.show'), 'secondary', type='submit') }}
-  {{ ui_button(t('billing.admin.portfolio.export_all'), 'primary', href='/admin/fakturace/export-vse') }}
+{% set state_options = [('', t('billing.admin.portfolio.all'))] %}
+{% for s in states %}{% set _ = state_options.append((s, t('billing.plan.state.' ~ s))) %}{% endfor %}
+<form method="get" action="/admin/fakturace" class="admin-controls" data-billing-admin-portfolio-filter>
+  {{ ui_field('portfolio-q', t('billing.admin.portfolio.search'), name='q', value=q, type='search', placeholder=t('billing.admin.portfolio.search_placeholder')) }}
+  {{ ui_select('portfolio-state', t('billing.admin.portfolio.state'), state_options, selected=state or '', name='state') }}
+  {{ ui_button(t('billing.admin.portfolio.show'), 'primary', type='submit') }}
+  {{ ui_button(t('billing.admin.portfolio.export_all'), 'secondary', href='/admin/fakturace/export-vse', icon_name='download', attrs='download') }}
 </form>
 {% set shown = [] %}
 {% for c in cockpit.customers %}
@@ -151,11 +145,10 @@
 {% endcall %}
 
 {% call ui_section(tip_label(t('billing.admin.statement.title'), 'statement-help', t('billing.admin.statement.help'), tag='span'), id='statement') %}
-<form method="post" action="/admin/fakturace/vypis" enctype="multipart/form-data" data-billing-admin-statement>
+<form method="post" action="/admin/fakturace/vypis" enctype="multipart/form-data" class="admin-controls" data-billing-admin-statement>
   <input type="hidden" name="_csrf" value="{{ csrf_token }}">
-  <label class="admin-label" for="statement-file">{{ t('billing.admin.statement.file') }}</label>
-  <input class="ui-input" type="file" id="statement-file" name="statement" accept=".gpc,.csv,.txt" required>
-  <div class="ui-form-actions">{{ ui_button(t('billing.admin.statement.submit'), 'primary', type='submit') }}</div>
+  {{ ui_field('statement-file', t('billing.admin.statement.file'), name='statement', type='file', attrs='accept=".gpc,.csv,.txt" required') }}
+  {{ ui_button(t('billing.admin.statement.submit'), 'primary', type='submit') }}
 </form>
 {% endcall %}
 
diff --git a/App/app/templates/admin_customers.html b/App/app/templates/admin_customers.html
index d7df9cdf..39bf9385 100644
--- a/App/app/templates/admin_customers.html
+++ b/App/app/templates/admin_customers.html
@@ -1,6 +1,6 @@
 {% extends "host_page.html" %}
 {% set v2 = true %}
-{% block head_extra %}<link rel="stylesheet" href="/static/admin2.css?v=20261102-0893o">{% endblock %}
+{% block head_extra %}<link rel="stylesheet" href="/static/admin2.css?v=20261102-0893o"><link rel="stylesheet" href="/static/admin2-operator-0974.css?v=20261105-0974a">{% endblock %}
 {% set nav = 'users' %}
 {% set body_kind = 'list' %}
 {% from "_ui_layout.html" import ui_section_tabs with context %}
@@ -34,7 +34,7 @@
 {% for value in ['legacy', 'unverified', 'trialing', 'ending', 'active', 'overdue'] %}
 {% set _ = stats.append((href(state=value, q='', plan=''), summary.get(value, 0), t('customers.ending') if value == 'ending' else t('customers.state.' ~ value))) %}
 {% endfor %}
-{{ ui_stats(stats, label=t('customers.overview')) }}
+<div class="customers-metrics">{{ ui_stats(stats, label=t('customers.overview')) }}</div>
 <p class="ui-sub">{{ t('customers.as_of', date=today) }}</p>
 {% if customers %}
 {{ ui_table_begin([(t('customers.customer'), ''), (t('customers.properties'), 'r'), (t('customers.plan'), ''), (t('customers.state'), ''), (t('customers.period'), ''), (t('common.actions'), '')], label=t('customers.title')) }}
@@ -54,6 +54,7 @@
 {% if newer_url %}{{ ui_button(t('customers.newer'), 'secondary', href=newer_url) }}{% endif %}
 {% if older_url %}{{ ui_button(t('customers.older'), 'secondary', href=older_url) }}{% endif %}
 {% if newer_url or older_url %}{{ ui_button(t('customers.reset'), 'quiet', href=href()) }}{% endif %}
+</nav>
 
 <section class="ui-section" id="create-host">
   <h2>{{ tip_label(t('users.create.title'), 'create-host-help', t('users.create.lede'), tag='span') }}</h2>
@@ -68,8 +69,7 @@
              autocapitalize="none" spellcheck="false">
       <div class="ui-help">{{ t('users.email.create_hint') }}</div>
     </div>
-    <button class="ui-btn ui-btn-primary" type="submit">{{ t('users.create.submit') }}</button>
+    <div class="ui-form-actions"><button class="ui-btn ui-btn-primary" type="submit">{{ t('users.create.submit') }}</button></div>
   </form>
 </section>
-</nav>
 {% endblock %}
diff --git a/App/tests/static_versions.json b/App/tests/static_versions.json
index b0642a2f..4a3f297e 100644
--- a/App/tests/static_versions.json
+++ b/App/tests/static_versions.json
@@ -1,4 +1,8 @@
 {
+  "admin2-operator-0974.css": {
+    "sha256": "64318b649212ad2dfabeb93a13043b4c7bdf4181bbe015ece27f302ebf6cccff",
+    "v": "20261105-0974a"
+  },
   "admin2-system.css": {
     "sha256": "71375d0cbcd5e0cef2b3e8a07c08a3b87520ef186ee4d324e1b5213ec9b228d6",
     "v": "20261102-0894e"
B16EOF
git apply --check /tmp/b16_code.diff && git apply /tmp/b16_code.diff && git status --short | tail -6
```
Expected: four modified/new paths (the two templates, the css, static_versions.json). If `--check` fails: STOP.
Then:
```
cd App && .venv/bin/python -m pytest tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30
```
Expected: passes. If it reports a sha mismatch for `admin2-operator-0974.css`, do NOT hand-edit; STOP. Commit `0974 step 2`.

### Step 3. Append patch B (browser tests)

```
cd /tmp/ubyhost-b16-worktree
cat > /tmp/b16_test.diff <<'B16EOF'
diff --git a/App/tests/test_0894_admin_airbnb_billing_ops_browser.py b/App/tests/test_0894_admin_airbnb_billing_ops_browser.py
index 8f0fdb00..09ca7dbe 100644
--- a/App/tests/test_0894_admin_airbnb_billing_ops_browser.py
+++ b/App/tests/test_0894_admin_airbnb_billing_ops_browser.py
@@ -49,3 +49,142 @@ def test_admin_billing_ops_geometry(host, base, name, width):
         shoot(page, name, width)
         browser.close()
     assert not problems, "\n".join(problems)
+
+
+# ---- 0974 (B16): operator Customers and Billing layouts ----------------------------
+import tempfile  # noqa: E402
+
+from app import db  # noqa: E402
+
+B16_WIDTHS = [390, 768, 1280]
+B16_LANGS = ["en", "cs"]
+B16_SHOTS = Path(os.environ.get("UBYHOST_SHOTS_DIR") or tempfile.gettempdir())
+B16_LONG = "Synthetic-long-name-" + "x" * 90
+
+
+def _b16_shot(page, name):
+    B16_SHOTS.mkdir(parents=True, exist_ok=True)
+    page.screenshot(path=str(B16_SHOTS / f"{name}.png"), full_page=True)
+
+
+def _b16_open(playwright, host, base, width):
+    browser = playwright.chromium.launch(**chromium_launch_kwargs())
+    context = browser.new_context(viewport={"width": width, "height": 900})
+    cookie = host["client"].cookies.get(auth.SESSION_COOKIE)
+    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
+    return browser, context.new_page()
+
+
+B16_CUSTOMERS_JS = """
+() => {
+  const out = [];
+  const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
+  const cards = [...document.querySelectorAll('.customers-metrics .ui-stat')].filter(vis);
+  if (cards.length !== 6) out.push('metric cards ' + cards.length);
+  const rows = {};
+  for (const c of cards) { const r = c.getBoundingClientRect(); (rows[Math.round(r.top)] = rows[Math.round(r.top)] || []).push(r); }
+  const counts = Object.values(rows).map((r) => r.length);
+  if (new Set(counts).size > 1) out.push('uneven metric rows ' + counts.join(','));
+  const widths = cards.map((c) => c.getBoundingClientRect().width);
+  if (widths.length && Math.max(...widths) - Math.min(...widths) > 1.5) out.push('metric card widths differ');
+  const want = window.innerWidth >= 768 ? 3 : 2;
+  if (counts.length && counts[0] !== want) out.push('metric columns ' + counts[0] + ' want ' + want);
+  const section = document.querySelector('#create-host');
+  if (!section) { out.push('no #create-host'); return out; }
+  if (section.closest('nav')) out.push('create-host sits inside a nav');
+  const lane = document.querySelector('.ui-body').getBoundingClientRect();
+  const s = section.getBoundingClientRect();
+  if (Math.abs(s.left - lane.left) > 2) out.push('create-host not at the lane left edge');
+  if (s.width > 561) out.push('create-host wider than 560: ' + s.width);
+  if (s.width < Math.min(lane.width, 560) - 2) out.push('create-host narrower than its lane: ' + s.width);
+  const primaries = section.querySelectorAll('.ui-btn-primary');
+  if (primaries.length !== 1) out.push('create-host primary buttons ' + primaries.length);
+  for (const i of section.querySelectorAll('input:not([type=hidden])')) if (i.getBoundingClientRect().height < (window.innerWidth >= 1024 ? 39.5 : 43.5)) out.push('create-host input under control height: ' + i.id);
+  if (document.documentElement.scrollWidth > document.documentElement.clientWidth) out.push('horizontal overflow');
+  return out;
+}
+"""
+
+B16_BILLING_JS = """
+() => {
+  const out = [];
+  const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
+  const forms = [...document.querySelectorAll('form.admin-controls')].filter(vis);
+  if (forms.length < 3) out.push('admin-controls forms ' + forms.length);
+  const want = window.innerWidth >= 1024 ? 40 : 44;
+  for (const f of forms) {
+    for (const field of f.querySelectorAll('.ui-field')) {
+      const l = field.querySelector('label').getBoundingClientRect();
+      const i = field.querySelector('input,select').getBoundingClientRect();
+      if (l.bottom > i.top + 1) out.push('label not above its field: ' + field.querySelector('label').textContent.trim());
+      if (Math.abs(l.left - i.left) > 2) out.push('label not aligned with its field');
+      if (Math.abs(i.height - want) > 0.6) out.push('field height ' + i.height + ' want ' + want);
+    }
+    for (const b of f.querySelectorAll('.ui-btn')) if (Math.abs(b.getBoundingClientRect().height - want) > 0.6) out.push('button height ' + b.getBoundingClientRect().height + ' want ' + want);
+    if (f.scrollWidth > f.clientWidth + 1) out.push('form overflows');
+  }
+  if (document.documentElement.scrollWidth > document.documentElement.clientWidth) out.push('horizontal overflow');
+  return out;
+}
+"""
+
+
+@pytest.fixture(scope="module")
+def b16_long_customer(host):
+    """One synthetic customer with a very long name (rows stay: other tests share the test DB)."""
+    username = f"b16-long-{host['owner']}"
+    if not db.query_one("SELECT id FROM user_account WHERE username = ?", (username,)):
+        auth.create_account(f"{username}@example.test", B16_LONG, role="host", username=username)
+    return username
+
+
+@pytest.mark.parametrize("lang", B16_LANGS)
+@pytest.mark.parametrize("width", B16_WIDTHS)
+@pytest.mark.parametrize("state", ["populated", "empty"])
+def test_b16_customers_layout(host, base, b16_long_customer, state, width, lang):
+    query = "Synthetic-long-name" if state == "populated" else "no-such-customer-zzz"
+    with sync_api.sync_playwright() as playwright:
+        browser, page = _b16_open(playwright, host, base, width)
+        page.goto(f"{base}/admin/customers?lang={lang}&q={query}")
+        problems = page.evaluate(B16_CUSTOMERS_JS)
+        if state == "populated":
+            assert page.locator("tr[data-customer-id]").count() >= 1
+        _b16_shot(page, f"customers-{state}-{lang}-{width}")
+        browser.close()
+    assert not problems, "\n".join(f"customers {state} {lang} {width}: {p}" for p in problems)
+
+
+def test_b16_create_host_empty_submit_creates_nothing(host, base):
+    before = db.query_one("SELECT COUNT(*) AS n FROM user_account")["n"]
+    posts = []
+    with sync_api.sync_playwright() as playwright:
+        browser, page = _b16_open(playwright, host, base, 390)
+        page.on("request", lambda r: posts.append(r.url) if r.method == "POST" else None)
+        page.goto(f"{base}/admin/customers?lang=en")
+        page.locator("#create-host button[type=submit]").click()
+        invalid = page.evaluate("document.querySelector('#email').validity.valueMissing")
+        url = page.url
+        _b16_shot(page, "customers-create-empty-submit-en-390")
+        browser.close()
+    assert invalid, "the empty e-mail must be refused in the browser"
+    assert not posts, f"no POST may be sent: {posts}"
+    assert "/admin/customers" in url
+    assert db.query_one("SELECT COUNT(*) AS n FROM user_account")["n"] == before
+
+
+@pytest.mark.parametrize("lang", B16_LANGS)
+@pytest.mark.parametrize("width", B16_WIDTHS)
+def test_b16_billing_controls(host, base, width, lang):
+    with sync_api.sync_playwright() as playwright:
+        browser, page = _b16_open(playwright, host, base, width)
+        page.goto(f"{base}/admin/fakturace?lang={lang}&q={B16_LONG}")
+        page.evaluate("document.querySelector('#reports').open = true")
+        problems = page.evaluate(B16_BILLING_JS)
+        month = page.locator("#month form.admin-controls")
+        assert month.locator(".ui-btn-primary").count() == 1
+        export = month.locator("a.ui-btn-secondary[download]")
+        assert export.count() == 1 and "/admin/fakturace/export?mesic=" in export.get_attribute("href")
+        assert page.locator("#portfolio a.ui-btn-secondary[download]").count() == 1
+        _b16_shot(page, f"billing-{lang}-{width}")
+        browser.close()
+    assert not problems, "\n".join(f"billing {lang} {width}: {p}" for p in problems)
B16EOF
git apply --check /tmp/b16_test.diff && git apply /tmp/b16_test.diff && git status --short | tail -6
```
Commit `0974 step 3`.

### Step 4. Run the checks (section 6), look at screenshots (section 7), write the report.

## 5. Do not touch

`App/app/routes/*`, `App/app/db.py`, migrations, `_ui.html`/`_ui_layout.html`, `admin2.css`, `admin2-system.css`, `host2.css`, any other template (admin_customer.html, admin_home.html, admin_operations.html share admin2.css: do not bump its key), i18n files, any file under docs/ other than your report. Do not submit the create-host form with valid data, upload a statement, mark a payment, or click an export link. Do not change export content, permissions or the CSRF handling. Never push, merge or open a PR from here beyond what executor.md says; report only.

## 6. Commands

From `/tmp/ubyhost-b16-worktree/App`, each ending `2>&1 | tail -30`. Env for browser runs: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b16`.

1. New B16 tests (19 expected, 0 skipped):
   `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b16 .venv/bin/python -m pytest tests/test_0894_admin_airbnb_billing_ops_browser.py -q --tb=short -rs -x -k b16 2>&1 | tail -30`
2. Operator-customer row plus guards (test-map: "Operator customer dashboard", host pages, design guardrails):
   `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b16 .venv/bin/python -m pytest tests/test_admin_customers.py tests/test_0893_admin_airbnb_browser.py tests/test_design_guardrails_browser.py -q --tb=short -rs -x 2>&1 | tail -30`
3. Host guard row:
   `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b16 .venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py -q --tb=short -rs 2>&1 | tail -30` (drop `-x`; if it is slow, run once only).
4. Billing presentation row:
   `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b16 .venv/bin/python -m pytest tests/test_billing_admin.py tests/test_billing_analytics.py tests/test_design_admin.py tests/test_0419_admin_billing_browser.py tests/test_0894_admin_airbnb_billing_ops_browser.py tests/test_static_versions.py -q --tb=short -rs -x 2>&1 | tail -30`
5. Context lint from the root: `cd /tmp/ubyhost-b16-worktree && python3 scripts/context_lint.py 2>&1 | tail -30`

Expected: all pass, `0 skipped`. Known environment note: on the reference run, `test_admin_airbnb_geometry[admin_customers-*]` failed once with `text 12px SPAN.: First page` when the shared test DB held more than one page of customers (the pager shows the quiet "First page" button); it passed on a fresh DB. It is not caused by this brief (the button is unchanged). If it appears: rerun that file once; if it still fails, STOP and report it, do not edit CSS to hide it.

## 7. Acceptance and Chromium UX checks

Screenshots are written by the tests to `/tmp/ubyhost-b16`. Open each listed file once with the Read tool and write one sentence per page in the report: pass or fail plus what you see. Fail if any item below is not visible.

Customers (`customers-populated-{en,cs}-{390,768,1280}.png`, `customers-empty-{en,cs}-{390,768,1280}.png`):
- [ ] Six metric cards of equal size: two columns at 390, three columns at 768 and 1280, no lone card on a last row.
- [ ] Long customer name (`Synthetic-long-name-xxxx...`) wraps or scrolls inside the table card; the page itself has no sideways scroll.
- [ ] Create host sits below the list at the left edge of the content lane, at most 560 px wide, with heading "Create a host" (CS equivalent), Name and Login e-mail fields and ONE primary button "Create host".
- [ ] Empty state (`customers-empty-*`): metrics still balanced, empty message shown, form unchanged.
- [ ] `customers-create-empty-submit-en-390.png`: after clicking Create host with an empty e-mail the page is unchanged (the browser's own "required" bubble may not be captured) and the test proves no POST was sent and no account was created.

Billing (`billing-{en,cs}-{390,768,1280}.png`):
- [ ] Each label sits directly above its own field and left-aligned with it (Month; Search and State; Statement file).
- [ ] Month input, Show button and "Download for the accountant" link share one height and one bottom line; Show is the filled primary, the download is the grey secondary with a download icon.
- [ ] In Reports: Search, State, Show (primary) and "Download everything (CSV)" (secondary) share one height; the long search value stays inside its field.
- [ ] Statement file field and the "Upload statement" primary button share one height.
- [ ] No sideways page scroll at 390.

Code checks:
- [ ] `git diff --stat 7b0355c4..HEAD` lists only the files in section 3 plus the brief.
- [ ] Commands 1 to 5 pass, 0 skipped.
- [ ] `grep -c "ui-btn-primary\|'primary'" App/app/templates/admin_customers.html` prints 2 (Apply filters in the toolbar and Create host; one primary per form). Report the number; do not change it.

Known gap, not fixable here: the unpaid-invoice forms (paid date, storno reason) are only on a populated billing page; they use the same `admin-controls` pattern and are not visible in the empty fixtures. Say so in the report.

## 8. Stop and ask

Stop, and write the report, if: an anchor or patch does not apply; a test fails twice; you reach 25 tool calls or about 50k tokens (report `blocked`, `Done: steps 1 to k. Left: steps k+1 to n.`); a file outside section 3 needs a change; a screenshot shows a defect that needs a change beyond the patch (describe it, do not improve); Chromium is missing (do not skip; report); anything needs push, merge, secrets or deploy.

## 9. Report

Write `docs/tasks/0974-report.md` (600 tokens at most): files changed (`git diff --stat`), each command with its last 5 lines, section 7 ticked with one sentence per screenshot group, Deviations, Questions, owner steps left. Set `Status: review` in this brief, commit `0974 report`. Do not push.

## Risk list (for the reviewer)

`App/app/templates/admin_billing.html` (five forms rewritten; csrf hidden inputs and field names must be unchanged), `App/app/templates/admin_customers.html` (nav closing tag moved), `App/app/static/admin2-operator-0974.css`.

## Owner steps

1. Review the PR diff of the two templates and the stylesheet.
2. Merge only with `scripts/merge-pr-on-green.sh` after CI is green. Deploy is yours; nothing to run on the server.
