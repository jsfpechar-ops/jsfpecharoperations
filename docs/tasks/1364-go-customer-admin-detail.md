# 1364: Go customer admin pages part 2 of 2: customer detail page

Status: review
Depends on: 1361 | Base commit: the commit of `1361 step 7` | Branch: go-customer-admin-pages (already checked out; do not create another)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B (admin pages; no filing, no guest data)

## 1. Objective

Port `GET /admin/customers/{user_id}` (`customer_detail` and `_quote_for` in `App/app/routes/admin_customers.py`, template `admin_customer.html`) to Go with the host layout, and extend the page golden of brief 1361 with 14 detail cases so the Go page is proven to show the same text, links and form fields as Python.

## 2. Context

- Needs brief 1361 done: `test -f go/internal/web/customers/pages.go && test -f go/internal/web/customers/testdata/customers_pages_golden.json && echo ok`. Missing: STOP.
- Same rules as 1361 §2: new files byte for byte from §4 with their sha256; existing files change only by the patch in step 3 and the `cat >>` in step 2; generated files only by their script. Read 1361 §2 only if a term here is unclear.
- What the Go page reads: `Detail` (404 as FastAPI's `{"detail":"Not Found"}` when it is nil: not a host, or no row), `ConsentCounts`, and `billing.Quote` (`go/internal/billing`, read-only) for `_quote_for`. `billing.account(user_id)` is not read: the template uses no column of it.
- Python quirk kept on purpose: `admin_customers.FIELDS` has no `discount_percent` or `discount_reason`, so Python always quotes with discount 0, shows "no discount", the discount form value `0` and no reason line. The Go page reads the same map keys, so it behaves the same and follows if FIELDS ever gains the columns.
- `current_user.id` in the template is the real account (`auth.current_user`): Go uses `host.Account.ID`.
- `ui_section` call blocks are written out as their markup (`<section class="ui-section" id=...><div class="ui-section-h"><h2>...</h2></div>...</section>`): Go templates cannot pass a block as `caller`. `partials/settings_value_card.html` is inlined the same way.
- `fmtDate` is `validation.fmt_date`; `moneyCZK` is the `money_czk` filter (no-break space thousands, comma, two decimals, ` Kč`).
- Gap, accepted: the layout's back link shows `arrow-left` + the label "Customers"; Python's `ph_back` override shows a round icon-only control with `aria-label`. The normaliser skips the text inside `.ui-ph-back`, so the golden compares only its href.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/customers/templates/i18n_keys.txt` | edit (append) | detail keys |
| `go/internal/web/customers/templates/i18n.json` | edit (generated) | by `go_host_i18n.py` |
| `go/internal/web/customers/templates/admin_customer.tmpl` | create | Go twin of `admin_customer.html` |
| `go/internal/web/customers/detail.go` | create | `fmtDate`, `moneyCZK`, `quoteFor`, `buildDetail`, `DetailHandler` |
| `go/internal/web/customers/pages_test.go` | edit (patch) | the detail route in `pagesMux` |
| `App/scripts/go_customers_pages_golden.py` | edit (patch) | 14 detail cases |
| `go/internal/web/customers/testdata/customers_pages_golden.json` | edit (generated) | by the script above |
| `go/cmd/ubyhost-web/register_web_customers.go` | edit (patch) | registers `GET /admin/customers/{user_id}` |
| `docs/tasks/1364-go-customer-admin-detail.md` | edit | `Status:` line only |
| `docs/tasks/1364-report.md` | create | your report |

No other file may change.

## 4. Steps

Commit after each step with the message `1364 step k`. Run every command from the repo root unless it says otherwise.

### Step 1: start Postgres (no commit)

```bash
PGBIN=/usr/lib/postgresql/16/bin; mkdir -p /var/tmp/pg1360 && chown postgres /var/tmp/pg1360
[ -f /var/tmp/pg1360/data/PG_VERSION ] || su postgres -c "$PGBIN/initdb -D /var/tmp/pg1360/data -A trust -U postgres" | tail -3
$PGBIN/pg_isready -h 127.0.0.1 -p 55436 || { rm -f /var/tmp/pg1360/data/postmaster.pid /var/tmp/pg1360/.s.PGSQL.55436 /var/tmp/pg1360/.s.PGSQL.55436.lock; su postgres -c "$PGBIN/pg_ctl -D /var/tmp/pg1360/data -l /var/tmp/pg1360/log -o '-p 55436 -k /var/tmp/pg1360 -c listen_addresses=127.0.0.1' -w start" 2>&1 | tail -3; }
$PGBIN/pg_isready -h 127.0.0.1 -p 55436
```

Expected last line: `127.0.0.1:55436 - accepting connections`.

### Step 2: detail strings

Append the block to the keys file: `cat >> go/internal/web/customers/templates/i18n_keys.txt <<'EOF'`, then the lines between the fences, then `EOF`.

~~~~text
# Detail page (brief 1364).
billing.interval.month
billing.interval.year
billing.invoices.state.open
billing.invoices.state.paid
billing.invoices.state.void
billing.plan.name.max
billing.plan.name.standard
billing.plan.state.active
billing.plan.state.canceling
billing.plan.state.overdue
billing.plan.state.paused
billing.plan.state.trialing
confirm.disable_user
customers.account
customers.actions.change
customers.actions.change_help
customers.actions.change_submit
customers.actions.discount
customers.actions.discount_help
customers.actions.discount_submit
customers.actions.field_apartments
customers.actions.field_interval
customers.actions.field_plan
customers.actions.field_ttlock
customers.actions.field_whitelabel
customers.actions.reason
customers.actions.status
customers.actions.status_submit
customers.actions.title
customers.actions.value
customers.activity.billing
customers.activity.kind
customers.activity.login
customers.activity.mail
customers.activity.none
customers.activity.title
customers.activity.what
customers.activity.when
customers.amount
customers.assign.buyer_city
customers.assign.buyer_dic
customers.assign.buyer_email
customers.assign.buyer_ico
customers.assign.buyer_name
customers.assign.buyer_street
customers.assign.buyer_zip
customers.assign.help
customers.assign.help2
customers.assign.plan
customers.assign.submit
customers.assign.title
customers.billing
customers.created
customers.due
customers.extend.days
customers.extend.submit
customers.extend.title
customers.invoice
customers.invoice_none
customers.invoices
customers.last_login
customers.legacy_note
customers.money.discount
customers.money.list
customers.money.monthly
customers.money.net
customers.money.no_discount
customers.money.reason
customers.no
customers.oplog.action
customers.oplog.title
customers.oplog.who
customers.ops.disable
customers.ops.enable
customers.ops.help
customers.ops.title
customers.ops.verify
customers.period_end
customers.period_start
customers.trial_end
customers.trial_start
customers.ttlock
customers.verified
customers.whitelabel
customers.yes
users.email.change
users.email.reason
users.email.set
users.menu.export
users.menu.open_workspace
users.menu.open_workspace_reason
users.menu.open_workspace_reason_optional
users.menu.schedule_deletion
users.menu.schedule_deletion_confirm
users.menu.send_invite
users.menu.withdraw_ads_consent
users.menu.withdraw_meta_consent
~~~~

Check: `sha256sum go/internal/web/customers/templates/i18n_keys.txt 2>&1 | tail -30` must print `0db15e06bf076493216036b0ba7a03a6db3971a49cbcc2d6b6f70ea7a58f76a2`.
Then from `App/`: `.venv/bin/python scripts/go_host_i18n.py 2>&1 | tail -30` (one `wrote` line).
Check: `sha256sum go/internal/web/customers/templates/i18n.json 2>&1 | tail -30` must print `e4b9ef43aadd546823909e7ec8035905b1f63def898ba882e6342d7849a5b137`. Commit `1364 step 2`.

### Step 3: routes, test mux and golden cases (patch)

From the repo root, write the patch below to `/tmp/1364.patch` exactly (keep the tabs and the leading space of each context line), then run `git apply --check /tmp/1364.patch && git apply /tmp/1364.patch && git status --short 2>&1 | tail -30`. If `--check` fails: STOP (§8).

~~~~diff
diff --git a/App/scripts/go_customers_pages_golden.py b/App/scripts/go_customers_pages_golden.py
index 1417a5d..ccd7fb9 100644
--- a/App/scripts/go_customers_pages_golden.py
+++ b/App/scripts/go_customers_pages_golden.py
@@ -44,6 +44,23 @@ CASES = [
     ("list max active in Vietnamese", "vi", True, "/admin/customers?plan=max&state=active&q=Bulk"),
     ("list empty, non-ASCII search", "en", True, "/admin/customers?q=%C5%BDlu%C5%A5+%26+co"),
     ("list bad cursor, repeated q", "en", True, "/admin/customers?after=abc&q=x&q=+Nov+"),
+    # Detail (brief 1364): 2 full history and google consent; 3 legacy without e-mail;
+    # 4 unverified; 6 trialing max with meta consent; 8 overdue yearly with add-ons;
+    # 11 trial pending without plan; 13 blank e-mail; 1 the admin and 99999: 404.
+    ("detail full history", "en", True, "/admin/customers/2"),
+    ("detail full history in Czech", "cs", True, "/admin/customers/2"),
+    ("detail legacy, no e-mail", "en", True, "/admin/customers/3"),
+    ("detail unverified", "en", True, "/admin/customers/4"),
+    ("detail trialing max in Vietnamese", "vi", True, "/admin/customers/6"),
+    ("detail trialing", "en", True, "/admin/customers/7"),
+    ("detail overdue yearly", "en", True, "/admin/customers/8"),
+    ("detail overdue yearly, billing off", "cs", False, "/admin/customers/8"),
+    ("detail canceling", "en", True, "/admin/customers/9"),
+    ("detail trial pending, no plan", "en", True, "/admin/customers/11"),
+    ("detail non-ASCII name", "en", True, "/admin/customers/12"),
+    ("detail blank e-mail, billing off", "en", False, "/admin/customers/13"),
+    ("detail of the admin is 404", "en", True, "/admin/customers/1"),
+    ("detail unknown id is 404", "en", True, "/admin/customers/99999"),
 ]
 
 # visible_lines: keep in step with visibleLines in go/internal/web/customers/pages_test.go.
diff --git a/go/cmd/ubyhost-web/register_web_customers.go b/go/cmd/ubyhost-web/register_web_customers.go
index 4729f7b..11107a8 100644
--- a/go/cmd/ubyhost-web/register_web_customers.go
+++ b/go/cmd/ubyhost-web/register_web_customers.go
@@ -1,7 +1,7 @@
 package main
 
-// Web thread "customer admin" owns this file: the customer list page (brief
-// 1361), the funnel redirect and the account toggle. The port stays off until
+// Web thread "customer admin" owns this file: the customer list and detail pages
+// (briefs 1361, 1364), the funnel redirect and the account toggle. The port stays off until
 // a path is routed to Go.
 
 import (
@@ -17,6 +17,7 @@ import (
 func init() {
 	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
 		mux.Handle("GET /admin/customers", m.wrap("/admin/customers", customers.ListHandler(pool, os.Getenv, time.Now)))
+		mux.Handle("GET /admin/customers/{user_id}", m.wrap("/admin/customers/{user_id}", customers.DetailHandler(pool, os.Getenv, time.Now)))
 		mux.Handle("GET /admin/funnel", m.wrap("/admin/funnel", customers.FunnelHandler(pool, os.Getenv, time.Now)))
 		mux.Handle("POST /admin/customers/{user_id}/aktivovat", m.wrap("/admin/customers/{user_id}/aktivovat", customers.ToggleActiveHandler(pool, os.Getenv, time.Now)))
 	})
diff --git a/go/internal/web/customers/pages_test.go b/go/internal/web/customers/pages_test.go
index c595853..f6e0c26 100644
--- a/go/internal/web/customers/pages_test.go
+++ b/go/internal/web/customers/pages_test.go
@@ -159,6 +159,7 @@ func pagesMux(t *testing.T, g goldenFile, billing bool) *http.ServeMux {
 	now := func() time.Time { return testNow }
 	mux := http.NewServeMux()
 	mux.Handle("GET /admin/customers", ListHandler(pool, getenv, now))
+	mux.Handle("GET /admin/customers/{user_id}", DetailHandler(pool, getenv, now))
 	return mux
 }
 
~~~~

Check: `sha256sum App/scripts/go_customers_pages_golden.py 2>&1 | tail -30` must print `ec0647b918ca7ff2a517e120789b7c2d4d5f56f816ded0277741fec62573ae00`.
Check: `sha256sum go/cmd/ubyhost-web/register_web_customers.go 2>&1 | tail -30` must print `7a7d109926b3f2895c2167b634e19da4a93a6baf7c933d59435936ddc8756da5`.
Check: `sha256sum go/internal/web/customers/pages_test.go 2>&1 | tail -30` must print `9f276a8e3f5fd34b7db3f74fc89dc46466c2421e59b4382435cd49e59272c1a4`.

The patch names `DetailHandler`, so the build fails until step 4. Commit `1364 step 3`.

### Step 4: template and handler

Create `go/internal/web/customers/templates/admin_customer.tmpl`:

~~~~gotemplate
{{- /* Go twin of App/app/templates/admin_customer.html (brief 1364). detail.go builds
     the fact lists and rows; ui_section call blocks are written out as their markup. */ -}}
{{define "admin_customer.head"}}<link rel="stylesheet" href="/static/admin2.css?v=20261106-0893q">{{end}}
{{define "admin_customer.tabs"}}{{ui_tabs .Tabs}}{{end}}
{{define "admin_customer.back_label"}}{{t "customers.title"}}{{end}}
{{define "admin_customer.secondary"}}{{ui_button (t "customers.payments") "secondary" (kv "href" "/admin/fakturace")}}{{end}}
{{define "admin_customer"}}
{{if not .BillingOn}}{{ui_banner "neutral" (t "customers.billing_off")}}{{end}}
{{if eq .State "legacy"}}<p class="ui-sub">{{t "customers.legacy_note"}}</p>{{end}}
<section class="ui-section"><div class="ui-section-h"><h2>{{t "customers.account"}}</h2></div>
<div class="settings-value-card">
  <span class="settings-value-label">{{t "customers.state"}}</span>
  <strong class="settings-value">{{.StateLabel}}</strong>
</div>
{{ui_facts .AccountFacts}}
<form method="post" action="/admin/users/{{.ID}}/email">
  {{ui_field (printf "user-email-%d" .ID) (t "users.email.label") (kv "name" "email" "value" .Email "type" "email" "attrs" (safe `required maxlength="254" autocomplete="off" autocapitalize="none" spellcheck="false"`))}}
  {{if .Email}}
  {{ui_field (printf "user-email-reason-%d" .ID) (t "users.email.reason") (kv "name" "reason" "attrs" (safe `required minlength="5" maxlength="300"`))}}
  {{end}}
  {{ui_button (t (or (and .Email "users.email.change") "users.email.set")) "secondary" (kv "type" "submit")}}
</form>
{{if .NotSelf}}
{{if and .Active .Email}}
<form method="post" action="/admin/users/{{.ID}}/invite">
  {{ui_button (t "users.menu.send_invite") "secondary" (kv "type" "submit")}}
</form>
{{end}}
<form method="post" action="/admin/users/{{.ID}}/impersonate">
  {{ui_field (printf "support-reason-%d" .ID) (t "users.menu.open_workspace_reason") (kv "name" "reason" "placeholder" (t "users.menu.open_workspace_reason_optional") "attrs" (safe `maxlength="300"`))}}
  {{ui_button (t "users.menu.open_workspace") "secondary" (kv "type" "submit")}}
</form>
{{if .Meta}}
<form method="post" action="/admin/users/{{.ID}}/ads-consent/withdraw">
  <input type="hidden" name="platform" value="meta">
  {{ui_button (t "users.menu.withdraw_meta_consent") "secondary" (kv "type" "submit")}}
</form>
{{end}}
{{if .Google}}
<form method="post" action="/admin/users/{{.ID}}/ads-consent/withdraw">
  <input type="hidden" name="platform" value="google">
  {{ui_button (t "users.menu.withdraw_ads_consent") "secondary" (kv "type" "submit")}}
</form>
{{end}}
<form method="post" action="/admin/users/{{.ID}}/export" data-no-skeleton>
  {{ui_button (t "users.menu.export") "secondary" (kv "type" "submit")}}
</form>
<form method="post" action="/admin/users/{{.ID}}/schedule-deletion">
  {{ui_field (printf "user-delete-confirm-%d" .ID) (t "users.menu.schedule_deletion_confirm" "username" .Username) (kv "name" "confirm" "attrs" (safe "required"))}}
  {{ui_button (t "users.menu.schedule_deletion") "secondary" (kv "type" "submit")}}
</form>
{{end}}
</section>
<section class="ui-section"><div class="ui-section-h"><h2>{{t "customers.billing"}}</h2></div>
{{ui_facts .BillingFacts}}
{{if .HasQuote}}
{{ui_facts .MoneyFacts}}
{{if .DiscountReason}}<p class="ui-sub">{{t "customers.money.reason"}}: {{.DiscountReason}}</p>{{end}}
{{end}}
</section>
{{if and .BillingOn (not .HasQuote)}}
<section class="ui-section" id="assign-plan"><div class="ui-section-h"><h2>{{tip_label (t "customers.assign.title") "assign-help" (printf "%s %s" (t "customers.assign.help") (t "customers.assign.help2")) (kv "tag" "span")}}</h2></div>
<form method="post" action="/admin/customers/{{.ID}}/priradit" data-customer-assign>
  <input type="hidden" name="_csrf" value="{{csrf}}">
  <div class="ui-form-actions">
    <label class="admin-label" for="assign-plan">{{t "customers.assign.plan"}}</label>
    <select class="ui-input" id="assign-plan" name="plan">
      <option value="standard">{{t "billing.plan.name.standard"}}</option>
      <option value="max">{{t "billing.plan.name.max"}}</option>
    </select>
    <label class="admin-label" for="assign-interval">{{t "customers.actions.field_interval"}}</label>
    <select class="ui-input" id="assign-interval" name="billing_interval">
      <option value="month">{{t "billing.interval.month"}}</option>
      <option value="year">{{t "billing.interval.year"}}</option>
    </select>
    <label class="admin-label" for="assign-ttlock">{{t "customers.actions.field_ttlock"}}</label>
    <select class="ui-input" id="assign-ttlock" name="addon_ttlock">
      <option value="0">{{t "customers.no"}}</option>
      <option value="1">{{t "customers.yes"}}</option>
    </select>
  </div>
  <div class="ui-form-actions">
    <label class="admin-label" for="assign-name">{{t "customers.assign.buyer_name"}}</label>
    <input class="ui-input" type="text" id="assign-name" name="buyer_name" value="{{.Buyer.Name}}" required>
    <label class="admin-label" for="assign-street">{{t "customers.assign.buyer_street"}}</label>
    <input class="ui-input" type="text" id="assign-street" name="buyer_street" required
           value="{{.Buyer.Street}}">
    <label class="admin-label" for="assign-city">{{t "customers.assign.buyer_city"}}</label>
    <input class="ui-input" type="text" id="assign-city" name="buyer_city" required
           value="{{.Buyer.City}}">
  </div>
  <div class="ui-form-actions">
    <label class="admin-label" for="assign-zip">{{t "customers.assign.buyer_zip"}}</label>
    <input class="ui-input" type="text" id="assign-zip" name="buyer_zip" required
           value="{{.Buyer.Zip}}">
    <label class="admin-label" for="assign-ico">{{t "customers.assign.buyer_ico"}}</label>
    <input class="ui-input" type="text" id="assign-ico" name="buyer_ico"
           value="{{.Buyer.ICO}}">
    <label class="admin-label" for="assign-dic">{{t "customers.assign.buyer_dic"}}</label>
    <input class="ui-input" type="text" id="assign-dic" name="buyer_dic"
           value="{{.Buyer.DIC}}">
    <label class="admin-label" for="assign-email">{{t "customers.assign.buyer_email"}}</label>
    <input class="ui-input" type="email" id="assign-email" name="buyer_email" value="{{.Buyer.Email}}" required>
  </div>
  <div class="ui-form-actions">
    {{ui_button (t "customers.assign.submit") "primary" (kv "type" "submit")}}
  </div>
</form>
</section>
{{end}}
{{if and .BillingOn (eq .State "trialing")}}
<section class="ui-section" id="extend-trial"><div class="ui-section-h"><h2>{{t "customers.extend.title"}}</h2></div>
<form method="post" action="/admin/customers/{{.ID}}/prodlouzit" class="ui-form-actions" data-customer-extend>
  <input type="hidden" name="_csrf" value="{{csrf}}">
  <label class="admin-label" for="extend-days">{{t "customers.extend.days"}}</label>
  <input class="ui-input" type="number" id="extend-days" name="days" min="1" max="365" value="14" inputmode="numeric" required>
  {{ui_button (t "customers.extend.submit") "secondary" (kv "type" "submit")}}
</form>
</section>
{{end}}
{{if and .BillingOn .HasQuote}}
<section class="ui-section" id="operator-actions"><div class="ui-section-h"><h2>{{tip_label (t "customers.actions.title") "actions-help" (printf "%s %s" (t "customers.actions.discount_help") (t "customers.actions.change_help")) (kv "tag" "span")}}</h2></div>
<form method="post" action="/admin/customers/{{.ID}}/sleva" class="ui-form-actions" data-customer-discount>
  <input type="hidden" name="_csrf" value="{{csrf}}">
  <label class="admin-label" for="discount-percent">{{t "customers.actions.discount"}}</label>
  <input class="ui-input" type="number" id="discount-percent" name="percent" min="0" max="100" value="{{.DiscountValue}}" required>
  <label class="admin-label" for="discount-reason">{{t "customers.actions.reason"}}</label>
  <input class="ui-input" type="text" id="discount-reason" name="reason" maxlength="200" value="{{.DiscountReason}}">
  {{ui_button (t "customers.actions.discount_submit") "secondary" (kv "type" "submit")}}
</form>
<form method="post" action="/admin/customers/{{.ID}}/plan" class="ui-form-actions" data-customer-plan>
  <input type="hidden" name="_csrf" value="{{csrf}}">
  <label class="admin-label" for="plan-field">{{t "customers.actions.change"}}</label>
  <select class="ui-input" id="plan-field" name="field">
    <option value="plan">{{t "customers.actions.field_plan"}}</option>
    <option value="billing_interval">{{t "customers.actions.field_interval"}}</option>
    <option value="apartments">{{t "customers.actions.field_apartments"}}</option>
    <option value="addon_ttlock">{{t "customers.actions.field_ttlock"}}</option>
    <option value="addon_whitelabel">{{t "customers.actions.field_whitelabel"}}</option>
  </select>
  <label class="admin-label" for="plan-value">{{t "customers.actions.value"}}</label>
  <input class="ui-input" type="text" id="plan-value" name="value" required>
  {{ui_button (t "customers.actions.change_submit") "secondary" (kv "type" "submit")}}
</form>
<form method="post" action="/admin/customers/{{.ID}}/stav" class="ui-form-actions" data-customer-status>
  <input type="hidden" name="_csrf" value="{{csrf}}">
  <label class="admin-label" for="status-new">{{t "customers.actions.status"}}</label>
  <select class="ui-input" id="status-new" name="status">
    <option value="active">{{t "billing.plan.state.active"}}</option>
    <option value="paused">{{t "billing.plan.state.paused"}}</option>
    <option value="canceling">{{t "billing.plan.state.canceling"}}</option>
    <option value="overdue">{{t "billing.plan.state.overdue"}}</option>
    <option value="trialing">{{t "billing.plan.state.trialing"}}</option>
  </select>
  {{ui_button (t "customers.actions.status_submit") "secondary" (kv "type" "submit")}}
</form>
</section>
{{end}}
<section class="ui-section" id="operator-actions-card"><div class="ui-section-h"><h2>{{tip_label (t "customers.ops.title") "ops-help" (t "customers.ops.help") (kv "tag" "span")}}</h2></div>
<div class="ui-form-actions">
  <form method="post" action="/admin/customers/{{.ID}}/aktivovat" data-customer-toggle{{if .Active}} data-confirm data-confirm-message="{{t "confirm.disable_user" "name" .Name}}"{{end}}>
    <input type="hidden" name="_csrf" value="{{csrf}}">
    {{ui_button (t (or (and .Active "customers.ops.disable") "customers.ops.enable")) "secondary" (kv "type" "submit")}}
  </form>
  {{if eq .State "unverified"}}
  <form method="post" action="/admin/customers/{{.ID}}/overit-znovu" data-customer-verify>
    <input type="hidden" name="_csrf" value="{{csrf}}">
    {{ui_button (t "customers.ops.verify") "secondary" (kv "type" "submit")}}
  </form>
  {{end}}
</div>
</section>
<section class="ui-section" id="activity-card"><div class="ui-section-h"><h2>{{t "customers.activity.title"}}</h2></div>
{{if .Activity}}
{{ui_table_begin .ActivityColumns (t "customers.activity.title")}}
{{range .Activity}}
<tr class="ui-row">
  <td class="ui-cell-first" data-card="meta">{{.When}}</td>
  <td data-card="secondary">{{t (printf "customers.activity.%s" .Kind)}}</td>
  <td data-card="primary">{{.Detail}}{{if .Extra}} <span class="ui-sub">{{.Extra}}</span>{{end}}</td>
</tr>
{{end}}
{{ui_table_end}}
{{else}}<p class="ui-sub">{{t "customers.activity.none"}}</p>{{end}}
</section>
<section class="ui-section" id="operator-log-card"><div class="ui-section-h"><h2>{{t "customers.oplog.title"}}</h2></div>
{{if .OpLog}}
{{ui_table_begin .OpLogColumns (t "customers.oplog.title")}}
{{range .OpLog}}
<tr class="ui-row">
  <td class="ui-cell-first" data-card="meta">{{.When}}</td>
  <td data-card="primary">{{.Action}}{{if .Detail}} <span class="ui-sub">{{.Detail}}</span>{{end}}</td>
  <td data-card="secondary">{{.Actor}}</td>
</tr>
{{end}}
{{ui_table_end}}
{{else}}<p class="ui-sub">{{t "customers.activity.none"}}</p>{{end}}
</section>
<section class="ui-section"><div class="ui-section-h"><h2>{{t "customers.invoices"}}</h2></div>
{{if .Invoices}}
{{ui_table_begin .InvoiceColumns (t "customers.invoices")}}
{{range .Invoices}}
<tr class="ui-row">
  <td class="ui-cell-first" data-card="primary"><a data-turbo="false" href="/admin/fakturace/{{.ID}}.pdf">{{.Number}}</a></td>
  <td class="ui-cell-r" data-card="meta">{{.Amount}}</td>
  <td data-card="secondary">{{.Due}}</td>
  <td data-card="badge">{{t .StateKey}}</td>
</tr>
{{end}}
{{ui_table_end}}
{{else}}<p class="ui-sub">{{t "customers.invoice_none"}}</p>{{end}}
</section>
{{end}}
~~~~

Check: `sha256sum go/internal/web/customers/templates/admin_customer.tmpl 2>&1 | tail -30` must print `e2003e0fab0c9c071f3350a61c1697bed6a77594dc7d49c4f097e4f1f3ba2d33`.

Create `go/internal/web/customers/detail.go`:

~~~~go
package customers

// GET /admin/customers/{user_id}: the port of customer_detail and _quote_for in
// App/app/routes/admin_customers.py with admin_customer.html. Brief 1364.

import (
	"fmt"
	"io"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billing"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

// fmtDate is validation.fmt_date: an ISO date as DD.MM.YYYY; anything that
// does not parse is passed through.
func fmtDate(v any) string {
	s := ""
	if v != nil {
		s = fmt.Sprint(v)
	}
	r := []rune(s)
	if len(r) > 10 {
		r = r[:10]
	}
	if d, err := time.Parse("2006-01-02", string(r)); err == nil {
		return d.Format("02.01.2006")
	}
	return s
}

// moneyCZK is templating._money_czk: haler as "1 234,50 Kč", thousands
// separated by a no-break space.
func moneyCZK(haler int64) string {
	sign := ""
	if haler < 0 {
		sign, haler = "-", -haler
	}
	digits := strconv.FormatInt(haler/100, 10)
	var b strings.Builder
	for i, c := range digits {
		if i > 0 && (len(digits)-i)%3 == 0 {
			b.WriteString(" ")
		}
		b.WriteRune(c)
	}
	return fmt.Sprintf("%s%s,%02d Kč", sign, b.String(), haler%100)
}

// truthy is a column value's Python truth: nil, "", 0 are false.
func truthy(v any) bool {
	switch x := v.(type) {
	case nil:
		return false
	case string:
		return x != ""
	case int64:
		return x != 0
	case int32:
		return x != 0
	case bool:
		return x
	}
	return true
}

// intOr is int(value or 0) for a column value.
func intOr(v any) (int, error) {
	if !truthy(v) {
		return 0, nil
	}
	n, err := asInt64(v, "number")
	return int(n), err
}

// quoteFor is routes/admin_customers._quote_for: nil without a plan.
func quoteFor(c map[string]any) (*billing.Price, error) {
	plan := text(c, "plan")
	if plan == "" {
		return nil, nil
	}
	apartments, err := intOr(c["apartments_billed"])
	if err != nil {
		return nil, err
	}
	discount, err := intOr(c["discount_percent"])
	if err != nil {
		return nil, err
	}
	interval := text(c, "billing_interval")
	if interval == "" {
		interval = "month"
	}
	p, err := billing.Quote(apartments, plan, interval, truthy(c["addon_ttlock"]), truthy(c["addon_whitelabel"]), discount)
	if err != nil {
		return nil, err
	}
	return &p, nil
}

// orNot is fmt_date(v) if v else customers.not_recorded.
func orNot(lang tr, v any) string {
	if truthy(v) {
		return fmtDate(v)
	}
	return lang.t("customers.not_recorded")
}

func yesNo(lang tr, v any) string {
	if truthy(v) {
		return lang.t("customers.yes")
	}
	return lang.t("customers.no")
}

type buyer struct{ Name, Street, City, Zip, ICO, DIC, Email string }

type activityRow struct{ When, Kind, Detail, Extra string }

type opRow struct{ When, Action, Detail, Actor string }

type invoiceRow struct {
	ID                            int64
	Number, Amount, Due, StateKey string
}

type detailView struct {
	ID                                       int64
	Name, Username, Email, State, StateLabel string
	Active, BillingOn, NotSelf, Meta, Google bool
	HasQuote                                 bool
	DiscountValue, DiscountReason            string
	Tabs, AccountFacts, BillingFacts         [][]any
	MoneyFacts                               [][]any
	ActivityColumns, OpLogColumns            [][]any
	InvoiceColumns                           [][]any
	Buyer                                    buyer
	Activity                                 []activityRow
	OpLog                                    []opRow
	Invoices                                 []invoiceRow
}

// rowsOf reads a list Detail stored under key.
func rowsOf(c map[string]any, key string) ([]map[string]any, error) {
	rows, ok := c[key].([]map[string]any)
	if !ok {
		return nil, fmt.Errorf("customers: %s is %T", key, c[key])
	}
	return rows, nil
}

func buildDetail(lang tr, c map[string]any, consent Consent, adminID int64, billingEnabled bool) (detailView, error) {
	id, err := asInt64(c["id"], "id")
	if err != nil {
		return detailView{}, err
	}
	props, err := asInt64(c["active_properties"], "active_properties")
	if err != nil {
		return detailView{}, err
	}
	state := text(c, "customer_state")
	v := detailView{
		ID: id, Name: text(c, "display_name"), Username: text(c, "username"), Email: text(c, "email"),
		State: state, StateLabel: lang.t("customers.state." + state), Active: truthy(c["active"]),
		BillingOn: billingEnabled, NotSelf: id != adminID, Meta: consent.Meta != 0, Google: consent.Google != 0,
		Tabs:           adminTabs(lang, "customers"),
		DiscountReason: text(c, "discount_reason"),
	}
	if v.Name == "" {
		v.Name = v.Username
	}
	email := lang.t("customers.not_recorded")
	if v.Email != "" {
		email = v.Email
	}
	v.AccountFacts = [][]any{
		{lang.t("customers.search"), email},
		{lang.t("customers.created"), fmtDate(c["created_at"])},
		{lang.t("customers.verified"), orNot(lang, c["email_verified_at"])},
		{lang.t("customers.last_login"), orNot(lang, c["last_login_at"])},
		{lang.t("customers.properties"), props},
	}
	interval := text(c, "billing_interval")
	v.BillingFacts = [][]any{
		{lang.t("customers.plan"), planName(lang, text(c, "plan"))},
		{lang.t("customers.period"), period(lang, interval)},
		{lang.t("customers.trial_start"), orNot(lang, c["trial_started_at"])},
		{lang.t("customers.trial_end"), orNot(lang, c["trial_ends_at"])},
		{lang.t("customers.period_start"), orNot(lang, c["period_start"])},
		{lang.t("customers.period_end"), orNot(lang, c["period_end"])},
		{lang.t("customers.ttlock"), yesNo(lang, c["addon_ttlock"])},
		{lang.t("customers.whitelabel"), yesNo(lang, c["addon_whitelabel"])},
	}
	quote, err := quoteFor(c)
	if err != nil {
		return detailView{}, err
	}
	discount, err := intOr(c["discount_percent"])
	if err != nil {
		return detailView{}, err
	}
	v.DiscountValue = strconv.Itoa(discount)
	if quote != nil {
		v.HasQuote = true
		disc := lang.t("customers.money.no_discount")
		if discount != 0 {
			disc = strconv.Itoa(discount) + " %"
		}
		monthly := quote.Total
		if interval != "month" {
			monthly = quote.Total / 12 // floor: totals are never negative
		}
		v.MoneyFacts = [][]any{
			{lang.t("customers.money.list"), strconv.Itoa(quote.List) + " Kč"},
			{lang.t("customers.money.discount"), disc},
			{lang.t("customers.money.net"), strconv.Itoa(quote.Total) + " Kč"},
			{lang.t("customers.money.monthly"), strconv.Itoa(monthly) + " Kč"},
		}
	}
	prefill, ok := c["buyer_prefill"].(map[string]string)
	if !ok {
		return detailView{}, fmt.Errorf("customers: buyer_prefill is %T", c["buyer_prefill"])
	}
	v.Buyer = buyer{Name: prefill["buyer_name"], Street: prefill["buyer_street"], City: prefill["buyer_city"],
		Zip: prefill["buyer_zip"], ICO: prefill["buyer_ico"], DIC: prefill["buyer_dic"], Email: prefill["buyer_email"]}
	if v.Buyer.Name == "" {
		v.Buyer.Name = text(c, "display_name")
	}
	if v.Buyer.Email == "" {
		v.Buyer.Email = v.Email
	}
	when := lang.t("customers.activity.when")
	v.ActivityColumns = [][]any{{when, ""}, {lang.t("customers.activity.kind"), ""}, {lang.t("customers.activity.what"), ""}}
	v.OpLogColumns = [][]any{{when, ""}, {lang.t("customers.oplog.action"), ""}, {lang.t("customers.oplog.who"), ""}}
	v.InvoiceColumns = [][]any{{lang.t("customers.invoice"), ""}, {lang.t("customers.amount"), "r"},
		{lang.t("customers.due"), ""}, {lang.t("customers.state"), ""}}
	activity, err := rowsOf(c, "activity")
	if err != nil {
		return detailView{}, err
	}
	for _, ev := range activity {
		v.Activity = append(v.Activity, activityRow{When: fmtDate(ev["at"]), Kind: text(ev, "kind"),
			Detail: text(ev, "detail"), Extra: text(ev, "extra")})
	}
	oplog, err := rowsOf(c, "operator_log")
	if err != nil {
		return detailView{}, err
	}
	for _, row := range oplog {
		v.OpLog = append(v.OpLog, opRow{When: fmtDate(row["at"]), Action: text(row, "action"),
			Detail: text(row, "detail"), Actor: text(row, "actor")})
	}
	invoices, err := rowsOf(c, "invoices")
	if err != nil {
		return detailView{}, err
	}
	for _, inv := range invoices {
		invID, err := asInt64(inv["id"], "id")
		if err != nil {
			return detailView{}, err
		}
		total, err := asInt64(inv["total_haler"], "total_haler")
		if err != nil {
			return detailView{}, err
		}
		key := "billing.invoices.state.open"
		switch {
		case truthy(inv["voided"]) || text(inv, "kind") == "storno":
			key = "billing.invoices.state.void"
		case truthy(inv["paid_on"]):
			key = "billing.invoices.state.paid"
		}
		v.Invoices = append(v.Invoices, invoiceRow{ID: invID, Number: text(inv, "number"),
			Amount: moneyCZK(total), Due: fmtDate(inv["due_date"]), StateKey: key})
	}
	return v, nil
}

// notFound is HTTPException(404) as FastAPI answers it.
func notFound(w http.ResponseWriter) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusNotFound)
	_, _ = io.WriteString(w, `{"detail":"Not Found"}`)
}

// DetailHandler serves GET /admin/customers/{user_id} (customer_detail).
// billing.account is not read: the template uses no column of it.
func DetailHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		host, ok := requireAdmin(w, r, pool, getenv, at)
		if !ok {
			return
		}
		userID, err := strconv.ParseInt(r.PathValue("user_id"), 10, 64)
		if err != nil {
			http.Error(w, "Unprocessable Entity", http.StatusUnprocessableEntity)
			return
		}
		ctx := r.Context()
		c, err := Detail(ctx, pool, userID)
		if err != nil {
			serverError(w, err)
			return
		}
		if c == nil {
			notFound(w)
			return
		}
		consent, err := ConsentCounts(ctx, pool, userID)
		if err != nil {
			serverError(w, err)
			return
		}
		lang := tr(hostweb.Lang(r))
		view, err := buildDetail(lang, c, consent, host.Account.ID, billingOn(getenv))
		if err != nil {
			serverError(w, err)
			return
		}
		p := layout.Page{Title: view.Name, Nav: "users", BodyKind: "detail", V2: true, AdminWorkspace: true,
			BackURL: page}
		if err := layout.Render(w, r, layout.Env{Pool: pool, Getenv: getenv, Now: at}, host, p, pages, "admin_customer", view); err != nil {
			serverError(w, err)
		}
	}
}
~~~~

Check: `sha256sum go/internal/web/customers/detail.go 2>&1 | tail -30` must print `e6a4c9a4b27ce78b4c99a40cdab6d6db587935799659c91c8020e2fada06f07c`.

Run from `go/`: `/usr/local/go/bin/go vet ./internal/web/... ./cmd/... 2>&1 | tail -30` (no output). Commit `1364 step 4`.

### Step 5: regenerate the golden and test

From `App/`: `env -u UBYHOST_TEST_DATABASE_URL .venv/bin/python scripts/go_customers_pages_golden.py 2>&1 | tail -1` (`wrote ...`), twice; the second run changes nothing (`git status --short`).
Check: `sha256sum go/internal/web/customers/testdata/customers_pages_golden.json 2>&1 | tail -30` must print `d88d9f1338fcd9ad1d0e2ff4ea78a995c4bff102d934417b0efb28fe30ffa6f0`. Run §6. Commit `1364 step 5`.

### Step 6: report

Write the report (§9), set `Status: review`, commit `1364 step 6`.

## 5. Do not touch

Everything in 1361 §5, plus every 1361 file not in §3 above (`pages.go`, `admin_customers.tmpl`, `query.go`, the pytest file). No push, merge or deploy.

## 6. Commands

1. Postgres: step 1 block.
2. Go, from the repo root:

```bash
cd go && export PATH=$PATH:/usr/local/go/bin
test -z "$(gofmt -l ./internal/web ./cmd)" && go vet ./... && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55436/postgres go test ./internal/web/customers/ ./cmd/ubyhost-web/ -count=1 2>&1 | tail -30
UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55436/postgres go test ./internal/web/customers/ -count=1 -v 2>&1 | grep -E -c 'SKIP'
```

Expected: `ok` for both packages; the last command prints `0`.

3. From `App/`: `.venv/bin/python -m pytest tests/test_go_customers_pages_golden.py tests/test_go_host_i18n.py tests/test_admin_customers_golden.py -q --tb=short 2>&1 | tail -30` (`4 passed`).
4. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -5` ends `context lint: OK`.

## 7. Acceptance

- [ ] Every file in §3 has the sha256 given in §4.
- [ ] `TestPagesMatchPython` passes for all 23 cases (9 list, 14 detail incl. two 404s); all `customers` and `cmd/ubyhost-web` tests pass; `grep -c SKIP` prints `0`.
- [ ] `grep -c 'mux.Handle' go/cmd/ubyhost-web/register_web_customers.go` prints `4`.
- [ ] §6 commands 3 and 4 as expected; `git diff --stat <start commit>` lists only the §3 paths.

## 8. Stop and ask

Stop, and write the report, if:

- a sha256 differs twice for the same file, or `git apply --check` fails;
- a generated file (`i18n.json`, the golden JSON) has a different sha256 than §4 says (main moved: the orchestrator regenerates);
- a test fails twice;
- Postgres does not start, or a DB test skips;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1364-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat <start commit>`; `<start commit>` is `git rev-parse HEAD` before step 1, write it down).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `go/internal/web/customers/detail.go`: fact lists and labels against `admin_customer.html`; `quoteFor` (apartments `or 0`, interval `or "month"`, add-ons, discount from the absent column); monthly `floor(total / 12)` unless the stored interval is `month`; invoice state order (void, then paid, then open); `NotSelf` uses the real admin id.
- `go/internal/web/customers/templates/admin_customer.tmpl`: every form action and field name against the Jinja file; hidden `_csrf` inputs use `csrf`; `data-confirm-message` on the toggle.
- Hrefs: no user-controlled URL goes into a layout macro `href` (rule until 1381's `safeHref`): only fixed paths and integer ids.
- UX gate: as 1361 risk list; not runnable on Go pages yet.
- Gaps: the back link (see §2); `billing.account` not read; class names, `data-*`, `aria-*` and icons are not compared by the golden.

## Owner steps

None for this brief. When CI is green on the draft PR, merge it. The pages stay on Python until a later brief routes them to Go (after 1381 and the UX gate).
