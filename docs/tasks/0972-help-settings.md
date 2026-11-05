# 0972: Align help, headings and account status copy (batch B14: X03, X04, F02, F03)

Status: blocked (executor handed over at the token checkpoint after step 1; steps 2 to 4 not run; see docs/tasks/0972-report.md)
Depends on: B13 (master plan; nothing in the repo to wait for) | Base commit: 7b0355c45ccdd2557a28edfcfe228aa1dc766e36 | Branch: codex/0972-b14-help-settings
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Settings help "?" buttons stay on the last line of their label and get a contextual accessible name ("Help with Passkeys"). The property H1 holds only the title (the "How does this work?" panel becomes its sibling), the Technical mail status reports the real runtime backend instead of staging/production prose, and the activity count, Passkeys and Help labels stop repeating or mis-pluralising.

## 2. Context

Rules that apply (full text in docs/context/rules.md; read-only here):
- Mail and secrets: **no mail configuration change, no authentication or security setting change.** You only change what Settings prints. Never print guest data, passwords or secrets; the repo is public.
- Copy: write "no tracking cookies", never "no cookies"; no em dashes (`test_no_em_dashes.py`).
- Host UI: light mode only; focus ring stays visible; Escape closes help and focus returns to the "?" (already done by `App/app/static/app.js`, around the line `if (e.key !== "Escape" || !helpTipState.current) return;`; **do not edit app.js or any CSS**, the tests prove it already works).

How it works today (read, do not change beyond §4):
- `help_tip(id, text, guide_href)` in `App/app/templates/_components.html` renders the "?" button with the generic name `t('help.tip.label')` ("Help"). `tip_label(text, id, help, tag)` keeps the "?" glued to the last word (`tip-nowrap`). In `settings.html` several rows used a bare `<strong>` plus a separate `help_tip`, so the "?" could wrap alone onto a new line.
- `partials/settings_back_header.html` puts its `help` argument **inside** the `<h1>`. `apartment_form.html` passes `help=page_help('property')`, a `<details>` with three steps, so the H1 text included that prose when open. `help_after` (already supported) renders a sibling after the H1 and `app2.css` already styles `.airbnb-header > .page-help`. This brief reuses that existing path.
- `settings.html` shows mail text from `settings.mail.help` (staging console prose plus production-disabled prose). The runtime value is `mail_backend` (from `mail.backend_name()` in `App/app/mail.py`, values `disabled`, `console`, `ses`, passed by `App/app/routes/admin.py`). Do not hard-code a message: the status line must be chosen from `mail_backend`.
- Plural keys: `tp('key', n)` looks up `key` (many), `key.one`, `key.few` (see `settings.retention.delete`). Languages: `en`, `cs` in `App/app/host_i18n.py`, `vi` in `App/app/host_vi_i18n.py`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/_components.html | edit | macro `help_tip` gets optional 4th arg `label` (contextual aria-label); macros `tip_label` and `settings_heading` pass their text to it |
| App/app/templates/partials/settings_back_header.html | edit | a `help` that is a `page-help` panel renders after the `</h1>`, not inside it |
| App/app/templates/partials/settings_value_card.html | edit | pass `label` to `help_tip` |
| App/app/templates/partials/settings_toggle_row.html | edit | pass `label` to `help_tip` |
| App/app/templates/settings.html | edit | rows use `tip_label`; heading helps get names; mail status line from `mail_backend`; `tp` for activity; Passkeys/Help label fixes |
| App/app/host_i18n.py | edit | en + cs keys |
| App/app/host_vi_i18n.py | edit | vi keys |
| App/tests/test_0786_settings_geometry_browser.py | append | new tests (§4 step 3) |
| App/tests/static_versions.json | do not edit | no static file changes in this brief; edit only if `test_static_versions.py` fails, then STOP (§8) |

No other file may change. The patch in step 2 touches exactly the first seven rows.

## 4. Steps

Work in the worktree `/tmp/ubyhost-b14-worktree` (already created on branch `codex/0972-b14-help-settings`; do not create another). If `git rev-parse HEAD` is not a descendant of `7b0355c4`, STOP. Commands run from `/tmp/ubyhost-b14-worktree/App` unless stated.

### Step 1: anchors and venv

```
cd /tmp/ubyhost-b14-worktree/App
ln -s /tmp/ubyhost-0958-worktree/App/.venv .venv 2>&1 | tail -3
.venv/bin/python --version 2>&1 | tail -3
mkdir -p /tmp/ubyhost-b14
git status --short | tail -5
```
`.venv` is git-ignored; it must not appear in `git status`. Then confirm each anchor with `grep -nF` (any missing: STOP):

| File | Anchor |
|---|---|
| app/templates/_components.html | `{%- macro help_tip(id, text, guide_href='') -%}` |
| app/templates/_components.html | `aria-label="{{ t('help.tip.label') }}" aria-expanded="false"` |
| app/templates/_components.html | `{{ help_tip(id, help) }}</span></{{ tag }}>` |
| app/templates/_components.html | `{{ help_tip('settings-' ~ key ~ '-help', help_text, guide_href) }}` |
| app/templates/partials/settings_back_header.html | `<h1 class="airbnb-title">{% if help %}` |
| app/templates/settings.html | `{{ t('settings.audit.recent', count=audit_count) }}` |
| app/templates/settings.html | `{% with label=t('passkeys.title'), value=(passkeys or []) \| length %}` |
| app/templates/settings.html | `aria-label="{{ t('settings.help.guide_action') }} {{ t('help.tip.label') \| lower }}"` |
| app/host_i18n.py | `"settings.mail.help": "Staging uses the console backend` |
| app/host_i18n.py | `"settings.help.guide_action": "Open",` |
| app/host_vi_i18n.py | `"settings.help.guide_action": "Mở Trợ giúp",` |

(In the grep, the `\|` above is a literal `|`.)

Commit nothing yet.

### Step 2: apply the patch

Write the patch, check it, apply it from the repo root:

```
cd /tmp/ubyhost-b14-worktree
cat > /tmp/ubyhost-b14/b14.patch <<'B14_PATCH_EOF'
diff --git a/App/app/host_i18n.py b/App/app/host_i18n.py
index b265a7d7..64f1bc5d 100644
--- a/App/app/host_i18n.py
+++ b/App/app/host_i18n.py
@@ -30,6 +30,7 @@ STRINGS: Dict[str, Dict[str, str]] = {
         "lang.switch": "Language",
         "nav.guide": "Help",
         "help.tip.label": "Help",
+        "help.tip.label_for": "Help with %(topic)s",
         "help.tip.more": "Read more",
         "nav.operations": "Operations",
         "nav.records": "Records",
@@ -2526,6 +2527,7 @@ STRINGS: Dict[str, Dict[str, str]] = {
         "housebook.legal_footnote": "Správcem údajů hostů jste vy. UbyHost poskytuje jen software: nejde o právní poradenství a neodpovídá za údaje zadané vámi nebo hosty ani za způsob jeho použití.",
         "nav.guide": "Nápověda",
         "help.tip.label": "Nápověda",
+        "help.tip.label_for": "Nápověda: %(topic)s",
         "help.tip.more": "Číst více",
         "send.this_stay": "Odeslat tento pobyt",
         "send.all_ready": "Odeslat všechny připravené",
@@ -4943,7 +4945,11 @@ _INTERFACE_STRINGS = {
         "settings.destination.help": "The target and public URL come from server environment variables, so they cannot be changed by an accidental click.",
         "settings.mail.title": "Guest e-mails",
         "settings.mail.backend": "Mail backend",
-        "settings.mail.help": "Staging uses the console backend: messages are stored here so you can copy claim links. Production stays disabled until SES is signed off.",
+        "settings.mail.help": "Guest e-mails such as claim links. The line below says what this installation does now.",
+        "settings.mail.status.disabled": "Sending is off: no guest e-mail leaves this installation.",
+        "settings.mail.status.console": "Not delivered: messages are kept below for claim links.",
+        "settings.mail.status.ses": "Sending is on through Amazon SES.",
+        "settings.mail.status.unknown": "Mail status is unknown.",
         "settings.mail.preview": "Preview the HTML e-mail",
         "settings.mail.to": "To",
         "settings.mail.subject": "Subject",
@@ -4984,6 +4990,8 @@ _INTERFACE_STRINGS = {
         "settings.privacy_incomplete": "The guest privacy notice is incomplete.",
         "settings.audit.help": "Important changes, archives, PIN rotations and police submissions are recorded here.",
         "settings.audit.recent": "Recent activity (%(count)s events)",
+        "settings.audit.recent.one": "Recent activity (%(count)s event)",
+        "settings.audit.recent.few": "Recent activity (%(count)s events)",
         "settings.audit.when": "When",
         "settings.audit.who": "Who",
         "settings.audit.as_admin": "as admin %(name)s",
@@ -5779,7 +5787,11 @@ _INTERFACE_STRINGS = {
         "settings.destination.help": "Cíl a veřejná URL pocházejí z proměnných serveru, takže je nelze změnit náhodným kliknutím.",
         "settings.mail.title": "E-maily hostům",
         "settings.mail.backend": "E-mailový backend",
-        "settings.mail.help": "Staging používá konzoli: zprávy se ukládají sem, abyste mohli zkopírovat odkazy na převzetí. Produkce zůstává vypnutá, dokud nebude SES schválené.",
+        "settings.mail.help": "E-maily hostům, například odkazy na převzetí. Řádek níže říká, co tato instalace dělá teď.",
+        "settings.mail.status.disabled": "Odesílání je vypnuté: žádný e-mail hostům neodchází.",
+        "settings.mail.status.console": "Nedoručuje se: zprávy jsou uložené níže pro odkazy.",
+        "settings.mail.status.ses": "Odesílání je zapnuté přes Amazon SES.",
+        "settings.mail.status.unknown": "Stav pošty není znám.",
         "settings.mail.preview": "Náhled HTML e-mailu",
         "settings.mail.to": "Komu",
         "settings.mail.subject": "Předmět",
@@ -5820,6 +5832,8 @@ _INTERFACE_STRINGS = {
         "settings.privacy_incomplete": "Informace o zpracování údajů hosta není úplná.",
         "settings.audit.help": "Důležité změny, archivace, změny PIN a policejní hlášení se zapisují zde.",
         "settings.audit.recent": "Nedávná aktivita (%(count)s událostí)",
+        "settings.audit.recent.one": "Nedávná aktivita (%(count)s událost)",
+        "settings.audit.recent.few": "Nedávná aktivita (%(count)s události)",
         "settings.audit.when": "Kdy",
         "settings.audit.who": "Kdo",
         "settings.audit.as_admin": "jako administrátor %(name)s",
@@ -7293,6 +7307,7 @@ _PASSKEY_STRINGS = {
         "login.passkey": "Log in with a passkey",
         "login.passkey_or": "or get a login link by e-mail",
         "passkeys.title": "Passkeys",
+        "passkeys.count_label": "Registered",
         "passkeys.help": "Log in with Face ID, a fingerprint or your device PIN instead of opening your inbox. The e-mail link keeps working, so losing a device never locks you out.",
         "passkeys.add": "Add a passkey",
         "passkeys.unsupported": "This browser cannot create passkeys. Try your phone, or a current Safari, Chrome, Edge or Firefox.",
@@ -7342,6 +7357,7 @@ _PASSKEY_STRINGS = {
         "login.passkey": "Přihlásit se pomocí klíče (passkey)",
         "login.passkey_or": "nebo si nechte poslat odkaz e-mailem",
         "passkeys.title": "Přístupové klíče (passkeys)",
+        "passkeys.count_label": "Zaregistrováno",
         "passkeys.help": "Přihlaste se pomocí Face ID, otisku prstu nebo PINu zařízení, bez otvírání schránky. Odkaz e-mailem dál funguje, takže ztráta zařízení vás nikdy nezamkne.",
         "passkeys.add": "Přidat klíč",
         "passkeys.unsupported": "Tento prohlížeč neumí vytvořit přístupový klíč. Zkuste telefon nebo aktuální Safari, Chrome, Edge či Firefox.",
@@ -7714,7 +7730,8 @@ _SETTINGS_GROUP_STRINGS = {
         "settings.privacy.requests_help": "Requests from guests about their data, and their deadlines.",
         "settings.privacy.requests_action": "Open requests",
         "settings.help.guide_help": "Step-by-step guides, and how to reach support.",
-        "settings.help.guide_action": "Open",
+        "settings.help.guide_action": "Open user guide",
+        "settings.help.guide_label": "User guide",
     },
     "cs": {
         "settings.index_label": "Sekce nastavení",
@@ -7732,7 +7749,8 @@ _SETTINGS_GROUP_STRINGS = {
         "settings.privacy.requests_help": "Žádosti hostů o jejich údaje a jejich lhůty.",
         "settings.privacy.requests_action": "Otevřít žádosti",
         "settings.help.guide_help": "Návody krok za krokem a kontakt na podporu.",
-        "settings.help.guide_action": "Otevřít",
+        "settings.help.guide_action": "Otevřít příručku",
+        "settings.help.guide_label": "Příručka",
     },
 }
 for _lang, _strings in _SETTINGS_GROUP_STRINGS.items():
diff --git a/App/app/host_vi_i18n.py b/App/app/host_vi_i18n.py
index 28f23a46..107eba05 100644
--- a/App/app/host_vi_i18n.py
+++ b/App/app/host_vi_i18n.py
@@ -293,6 +293,7 @@ STRINGS: Dict[str, str] = {
     "lang.switch": "Ngôn ngữ",
     "nav.guide": "Trợ giúp",
     "help.tip.label": "Trợ giúp",
+    "help.tip.label_for": "Trợ giúp: %(topic)s",
     "help.tip.more": "Xem thêm",
     "nav.operations": "Vận hành",
     "nav.records": "Hồ sơ",
@@ -2388,7 +2389,11 @@ STRINGS: Dict[str, str] = {
     "settings.destination.help": "Đích và URL công khai lấy từ biến môi trường của máy chủ, nên không thể bị thay đổi do bấm nhầm.",
     "settings.mail.title": "Email cho khách",
     "settings.mail.backend": "Phương thức gửi thư",
-    "settings.mail.help": "Staging dùng phương thức console: thư được lưu ở đây để bạn sao chép liên kết xác nhận. Bản chính thức tắt cho đến khi SES được duyệt.",
+    "settings.mail.help": "Email cho khách, như liên kết xác nhận. Dòng bên dưới cho biết bản cài đặt này đang làm gì.",
+    "settings.mail.status.disabled": "Đang tắt gửi thư: không có email nào gửi tới khách.",
+    "settings.mail.status.console": "Không gửi đi: thư được giữ bên dưới để lấy liên kết.",
+    "settings.mail.status.ses": "Đang gửi thư qua Amazon SES.",
+    "settings.mail.status.unknown": "Chưa rõ trạng thái thư.",
     "settings.mail.preview": "Xem trước email HTML",
     "settings.mail.to": "Đến",
     "settings.mail.subject": "Tiêu đề",
@@ -2429,6 +2434,8 @@ STRINGS: Dict[str, str] = {
     "settings.privacy_incomplete": "Thông báo quyền riêng tư cho khách chưa đầy đủ.",
     "settings.audit.help": "Các thay đổi quan trọng, lưu trữ, đổi mã PIN và khai báo cảnh sát được ghi lại ở đây.",
     "settings.audit.recent": "Hoạt động gần đây (%(count)s sự kiện)",
+    "settings.audit.recent.one": "Hoạt động gần đây (%(count)s sự kiện)",
+    "settings.audit.recent.few": "Hoạt động gần đây (%(count)s sự kiện)",
     "settings.audit.when": "Thời gian",
     "settings.audit.who": "Người thực hiện",
     "settings.audit.as_admin": "với tư cách quản trị viên %(name)s",
@@ -3104,6 +3111,7 @@ STRINGS: Dict[str, str] = {
     "login.passkey": "Đăng nhập bằng passkey",
     "login.passkey_or": "hoặc nhận liên kết đăng nhập qua e-mail",
     "passkeys.title": "Passkey",
+    "passkeys.count_label": "Đã đăng ký",
     "passkeys.help": "Đăng nhập bằng Face ID, vân tay hoặc mã PIN thiết bị thay vì mở hộp thư. Liên kết e-mail vẫn dùng được, nên mất thiết bị cũng không khóa bạn khỏi tài khoản.",
     "passkeys.add": "Thêm passkey",
     "passkeys.unsupported": "Trình duyệt này không tạo được passkey. Hãy thử trên điện thoại, hoặc Safari, Chrome, Edge hay Firefox bản mới.",
@@ -3183,7 +3191,8 @@ STRINGS: Dict[str, str] = {
     "settings.privacy.requests_help": "Yêu cầu của khách về dữ liệu của họ, và thời hạn xử lý.",
     "settings.privacy.requests_action": "Mở yêu cầu",
     "settings.help.guide_help": "Hướng dẫn từng bước, và cách liên hệ hỗ trợ.",
-    "settings.help.guide_action": "Mở Trợ giúp",
+    "settings.help.guide_action": "Mở hướng dẫn sử dụng",
+    "settings.help.guide_label": "Hướng dẫn sử dụng",
     "property_create.title": "Thêm chỗ ở",
     "property_create.lede": "Bắt đầu với thông tin cơ bản. Kết nối dịch vụ khi bạn cần.",
     "property_create.details": "Thông tin chỗ ở",
diff --git a/App/app/templates/_components.html b/App/app/templates/_components.html
index c4288baf..ad71a798 100644
--- a/App/app/templates/_components.html
+++ b/App/app/templates/_components.html
@@ -7,9 +7,9 @@
 {% set UI_DEADLINE_KINDS = {'overdue': 'action', 'urgent': 'attention', 'soon': 'attention', 'done': 'done', 'late': 'neutral'} %}
 {#- 0093 help: one contextual "?" tip beside a field label. Place it OUTSIDE the <label> tag.
     id must be unique on the page; text is escaped; guide_href optional ("/guide#anchor"). -#}
-{%- macro help_tip(id, text, guide_href='') -%}
+{%- macro help_tip(id, text, guide_href='', label='') -%}
 <span class="help-tip" data-help-tip>
-    <button type="button" class="help-tip-btn" aria-label="{{ t('help.tip.label') }}" aria-expanded="false" aria-controls="{{ id }}">?</button>
+    <button type="button" class="help-tip-btn" aria-label="{{ t('help.tip.label_for', topic=label) if label else t('help.tip.label') }}" aria-expanded="false" aria-controls="{{ id }}">?</button>
     <span class="help-tip-body" id="{{ id }}" role="tooltip">{{ text }}{% if guide_href %} <a href="{{ guide_href }}" aria-label="{{ t('help.tip.more') }}: {{ text | striptags | truncate(50) }}">{{ t('help.tip.more') }}</a>{% endif %}</span>
   </span>
 {% endmacro %}
@@ -22,7 +22,7 @@
 {#- Label text with its "?" tip kept on the last word, so the tip never wraps alone to a new line. -#}
 {% macro tip_label(text, id, help, tag='strong') -%}
 {%- set words = text.rsplit(' ', 1) -%}
-<{{ tag }} class="tip-label">{% if words | length > 1 %}{{ words[0] }} {% endif %}<span class="tip-nowrap">{{ words[-1] }}{{ help_tip(id, help) }}</span></{{ tag }}>
+<{{ tag }} class="tip-label">{% if words | length > 1 %}{{ words[0] }} {% endif %}<span class="tip-nowrap">{{ words[-1] }}{{ help_tip(id, help, '', text) }}</span></{{ tag }}>
 {%- endmacro %}
 {#- 0410: one option card. The label is stretched over the whole bordered card, so a
     tap anywhere selects; the "?" and any extra field (call block) sit above it. No JS. -#}
@@ -542,7 +542,7 @@
 {% macro settings_heading(key, title, help_text='', guide_href='') %}
   <div class="settings-heading">
     <h3>{{ title }}</h3>
-    {% if help_text %}{{ help_tip('settings-' ~ key ~ '-help', help_text, guide_href) }}{% endif %}
+    {% if help_text %}{{ help_tip('settings-' ~ key ~ '-help', help_text, guide_href, title) }}{% endif %}
   </div>
 {% endmacro %}
 
diff --git a/App/app/templates/partials/settings_back_header.html b/App/app/templates/partials/settings_back_header.html
index 2cf85658..b48b7427 100644
--- a/App/app/templates/partials/settings_back_header.html
+++ b/App/app/templates/partials/settings_back_header.html
@@ -1,6 +1,7 @@
 {%- from "_icons.html" import icon with context -%}
 <div class="airbnb-header">
   <a class="airbnb-back" href="{{ href }}" aria-label="{{ t('common.back') }}">{{ icon('arrow-left', 20) }}</a>
-  <h1 class="airbnb-title">{% if help %}{% set words = title.rsplit(' ', 1) %}{% if words | length > 1 %}{{ words[0] }} {% endif %}<span class="tip-nowrap">{{ words[-1] }}{{ help }}</span>{% else %}{{ title }}{% endif %}</h1>{% if help_after %}{{ help_after }}{% endif %}
+  {%- set help_is_page = help and 'page-help' in help -%}
+<h1 class="airbnb-title">{% if help and not help_is_page %}{% set words = title.rsplit(' ', 1) %}{% if words | length > 1 %}{{ words[0] }} {% endif %}<span class="tip-nowrap">{{ words[-1] }}{{ help }}</span>{% else %}{{ title }}{% endif %}</h1>{% if help_is_page %}{{ help }}{% endif %}{% if help_after %}{{ help_after }}{% endif %}
 {% if actions %}<div class="airbnb-actions">{{ actions }}</div>{% endif %}
 </div>
diff --git a/App/app/templates/partials/settings_toggle_row.html b/App/app/templates/partials/settings_toggle_row.html
index 13cd92be..037ae364 100644
--- a/App/app/templates/partials/settings_toggle_row.html
+++ b/App/app/templates/partials/settings_toggle_row.html
@@ -2,6 +2,6 @@
     `control` is the captured form control (the checkbox), `help_text` is optional. -#}
 {%- from "_components.html" import help_tip with context -%}
 <div class="settings-toggle-row">
-  <span class="settings-toggle-label">{{ label }}{% if help_text %}{{ help_tip(help_id, help_text) }}{% endif %}</span>
+  <span class="settings-toggle-label">{{ label }}{% if help_text %}{{ help_tip(help_id, help_text, '', label) }}{% endif %}</span>
   <span class="settings-toggle-control">{{ control }}</span>
 </div>
diff --git a/App/app/templates/partials/settings_value_card.html b/App/app/templates/partials/settings_value_card.html
index b2974166..ced7af16 100644
--- a/App/app/templates/partials/settings_value_card.html
+++ b/App/app/templates/partials/settings_value_card.html
@@ -2,7 +2,7 @@
 {%- from "_icons.html" import icon with context -%}
 {%- from "_components.html" import help_tip with context -%}
 <div class="settings-value-card">
-  <span class="settings-value-label">{{ label }}{% if help_text %} {{ help_tip(help_id, help_text) }}{% endif %}</span>
+  <span class="settings-value-label">{{ label }}{% if help_text %} {{ help_tip(help_id, help_text, '', label) }}{% endif %}</span>
   <strong class="settings-value">{{ value }}</strong>
   {% if href %}<a class="settings-value-link" href="{{ href }}">{{ link_label }} {{ icon('chevron-right', 20) }}</a>{% endif %}
 </div>
diff --git a/App/app/templates/settings.html b/App/app/templates/settings.html
index cb672259..544a189a 100644
--- a/App/app/templates/settings.html
+++ b/App/app/templates/settings.html
@@ -83,17 +83,11 @@
         {% endif %}
         {% if current_user.role == 'admin' %}
           <div class="settings-action-row">
-            <div>
-              <strong>{{ t('settings.account.users') }}</strong>
-              {{ help_tip('settings-users-help', t('settings.account.users_help')) }}
-            </div>
+            <div>{{ tip_label(t('settings.account.users'), 'settings-users-help', t('settings.account.users_help')) }}</div>
             <a data-turbo="false" class="ui-btn ui-btn-secondary ui-btn-compact" href="/admin/customers">{{ t('settings.account.users_action') }}</a>
           </div>
           <div class="settings-action-row">
-            <div>
-              <strong>{{ t('users.incidents_link') }}</strong>
-              {{ help_tip('settings-incidents-help', t('settings.account.incidents_help')) }}
-            </div>
+            <div>{{ tip_label(t('users.incidents_link'), 'settings-incidents-help', t('settings.account.incidents_help')) }}</div>
             <a data-turbo="false" class="ui-btn ui-btn-secondary ui-btn-compact" href="/admin/incidents">{{ t('settings.account.incidents_action') }}</a>
           </div>
         {% endif %}
@@ -105,10 +99,7 @@
     <div class="ui-section" id="settings-security">
       <div class="settings-action-list" id="settings-logout-all">
         <div class="settings-action-row">
-          <div>
-            <strong>{{ t('settings.security.devices') }}</strong>
-            {{ help_tip('settings-logout-all-help', t('settings.security.logout_all_help')) }}
-          </div>
+          <div>{{ tip_label(t('settings.security.devices'), 'settings-logout-all-help', t('settings.security.logout_all_help')) }}</div>
           <form method="post" action="/account/logout-all">
             <button class="ui-btn ui-btn-secondary ui-btn-compact" type="submit">{{ t('settings.security.logout_all') }}</button>
           </form>
@@ -116,10 +107,7 @@
       </div>
       <div class="settings-action-list" id="settings-passkeys">
         <div class="settings-action-row">
-          <div>
-            <strong>{{ t('passkeys.title') }}</strong>
-            {{ help_tip('settings-passkeys-help', t('passkeys.help') ~ (' ' ~ t('passkeys.unavailable') if not passkeys_available else '')) }}
-          </div>
+          <div>{{ tip_label(t('passkeys.title'), 'settings-passkeys-help', t('passkeys.help') ~ (' ' ~ t('passkeys.unavailable') if not passkeys_available else '')) }}</div>
           {% if passkeys_available %}
             <button class="ui-btn ui-btn-primary ui-btn-compact" type="button" data-passkey-add data-passkey-supported hidden>{{ t('passkeys.add') }}</button>
           {% endif %}
@@ -128,7 +116,7 @@
           <p class="ui-sub" data-passkey-unsupported>{{ t('passkeys.unsupported') }}</p>
           <p class="ui-sub err-text" data-passkey-error data-generic="{{ t('passkeys.error.failed') }}" role="alert" hidden></p>
         {% endif %}
-        {% with label=t('passkeys.title'), value=(passkeys or []) | length %}{% include "partials/settings_value_card.html" %}{% endwith %}
+        {% with label=t('passkeys.count_label'), value=(passkeys or []) | length %}{% include "partials/settings_value_card.html" %}{% endwith %}
         {% for key in passkeys %}
           <div class="settings-action-row passkey-row">
             <div>
@@ -160,7 +148,7 @@
         {% endif %}
         {% if not current_user.totp_enabled %}
         <div class="settings-action-row">
-          <div><strong>{{ t('settings.account.2fa') }}</strong>{{ help_tip('settings-2fa-help', t('settings.account.2fa_off')) }}</div>
+          <div>{{ tip_label(t('settings.account.2fa'), 'settings-2fa-help', t('settings.account.2fa_off')) }}</div>
           <a class="ui-btn ui-btn-secondary ui-btn-compact" href="/account/2fa/setup">{{ t('settings.account.setup') }}</a>
         </div>
         {% endif %}
@@ -216,10 +204,7 @@
       {% if push_available %}
       <div class="settings-action-list" id="settings-alerts" data-push-row data-push-key="{{ push_key }}">
         <div class="settings-action-row">
-          <div>
-            <strong>{{ t('push.title') }}</strong>
-            {{ help_tip('settings-push-help', t('push.help')) }}
-          </div>
+          <div>{{ tip_label(t('push.title'), 'settings-push-help', t('push.help')) }}</div>
           <div class="settings-row-actions">
             <button class="ui-btn ui-btn-secondary ui-btn-compact" type="button" data-push-on hidden>{{ t('push.on') }}</button>
             <span class="ui-badge ui-badge-done" data-tone="green" data-push-state-on hidden>{{ t('push.state_on') }}</span>
@@ -367,7 +352,7 @@
       <summary>{{ t('settings.technical.title') }}</summary>
 
       {% if current_user.role == 'admin' %}
-      <h2 id="settings-overview">{{ t('settings.destination.title') }}{{ help_tip('settings-destination-help', t('settings.destination.help')) }}</h2>
+      <h2 id="settings-overview">{{ t('settings.destination.title') }}{{ help_tip('settings-destination-help', t('settings.destination.help'), '', t('settings.destination.title')) }}</h2>
       <dl class="kv">
         <dt>{{ t('settings.destination.deployment') }}</dt><dd>{{ deployment_tier | capitalize }}</dd>
         <dt>{{ t('settings.destination.target') }}</dt><dd>{{ t('settings.destination.production') if ubyport_env == 'prod' else (ubyport_env | upper) }}</dd>
@@ -389,7 +374,8 @@
       
       {% endif %}
       {% if current_user.role == 'admin' or (mail_backend == 'console' and console_mail) %}
-      <h2 id="settings-mail">{{ t('settings.mail.title') }}{{ help_tip('settings-mail-help', t('settings.mail.help')) }}</h2>
+      <h2 id="settings-mail">{{ t('settings.mail.title') }}{{ help_tip('settings-mail-help', t('settings.mail.help'), '', t('settings.mail.title')) }}</h2>
+      <p class="ui-sub" id="settings-mail-status" data-mail-backend="{{ mail_backend }}">{{ t('settings.mail.status.' ~ mail_backend) if mail_backend in ('disabled', 'console', 'ses') else t('settings.mail.status.unknown') }}</p>
       {% if current_user.role == 'admin' %}
       <dl class="kv">
         <dt>{{ t('settings.mail.backend') }}</dt>
@@ -437,7 +423,7 @@
 
       {% endif %}
       {% if current_user.role == 'admin' %}
-      <h2 id="settings-codelists">{{ t('settings.codelists.title') }}{{ help_tip('settings-codelists-help', t('settings.codelists.help')) }}</h2>
+      <h2 id="settings-codelists">{{ t('settings.codelists.title') }}{{ help_tip('settings-codelists-help', t('settings.codelists.help'), '', t('settings.codelists.title')) }}</h2>
       <dl class="kv">
         <dt>{{ t('settings.codelists.countries') }}</dt><dd>{{ (codelists.countries | datetime_local(seconds=true)) if codelists.countries else t('settings.codelists.bundled') }}</dd>
         <dt>{{ t('settings.codelists.purposes') }}</dt><dd>{{ (codelists.purposes | datetime_local(seconds=true)) if codelists.purposes else t('settings.codelists.bundled') }}</dd>
@@ -456,7 +442,7 @@
 
     <details class="ui-section technical" open id="settings-audit">
       <summary>{{ t('settings.nav.audit') }}</summary>
-            <h2>{{ t('settings.audit.recent', count=audit_count) }}</h2>
+            <h2>{{ tp('settings.audit.recent', audit_count) }}</h2>
       {% set audit_pills = [
         {'label': t('settings.audit.filter_all'), 'href': '/settings/technical#settings-audit', 'current': not audit_filter},
         {'label': t('settings.audit.filter_support'), 'href': '/settings/technical?audit=support#settings-audit', 'current': audit_filter == 'support'}
@@ -487,9 +473,9 @@
       <div class="settings-action-list">
         <div class="settings-action-row">
           <div>
-            {{ tip_label(t('nav.guide'), 'settings-guide-help', t('settings.help.guide_help')) }}
+            {{ tip_label(t('settings.help.guide_label'), 'settings-guide-help', t('settings.help.guide_help')) }}
           </div>
-          <a class="ui-btn ui-btn-secondary ui-btn-compact" href="/guide" aria-label="{{ t('settings.help.guide_action') }} {{ t('help.tip.label') | lower }}">{{ t('settings.help.guide_action') }}</a>
+          <a class="ui-btn ui-btn-secondary ui-btn-compact" href="/guide">{{ t('settings.help.guide_action') }}</a>
         </div>
       </div>
     </div>
B14_PATCH_EOF
git apply --check /tmp/ubyhost-b14/b14.patch 2>&1 | tail -30
git apply /tmp/ubyhost-b14/b14.patch 2>&1 | tail -30
git diff --stat | tail -12
```
`--check` fails: STOP, do not hand-edit. The stat must list exactly the seven files in §3 rows 1 to 7. Then `git add` those seven paths by name and commit `0972 step 2`.

What the patch does, so you can review it: `help_tip` gets `label=''`; the aria-label is `t('help.tip.label_for', topic=label)` when a label is given, else the old generic name. `tip_label`, `settings_heading`, the value card, the toggle row and the heading helps in settings.html pass their label. Account/Security/Push rows move from a bare `<strong>` plus separate `help_tip` to `tip_label`. The header partial computes `help_is_page = help and 'page-help' in help`; a page-help is printed after `</h1>`, any other `help` (a `help_tip`) stays inside as before. `<p id="settings-mail-status" data-mail-backend="...">` prints `settings.mail.status.<backend>` (`disabled`, `console`, `ses`, else `unknown`). `settings.mail.help` loses the staging/production prose. Activity heading uses `tp` (keys `.one`, `.few`). The Passkeys value card is labelled "Registered" (key `passkeys.count_label`). Help row: label "User guide" (key `settings.help.guide_label`), button "Open user guide", and the extra `aria-label` is removed because the visible text already names the button.

### Step 3: append the tests

Append exactly this block to the end of `App/tests/test_0786_settings_geometry_browser.py` (do not change anything above it):

```
cd /tmp/ubyhost-b14-worktree/App
cat >> tests/test_0786_settings_geometry_browser.py <<'B14_TESTS_EOF'


# ---------------------------------------------------------------------------
# 0972 (B14): help beside its label, contextual help names, short H1, honest mail
# status, plural-aware activity copy and no duplicated Passkeys/Help labels.
# ---------------------------------------------------------------------------
import os
import re
from pathlib import Path

from app import config
from app.host_i18n import STRINGS as HOST_STRINGS_0972, translate_plural

SHOTS_0972 = Path(os.environ.get("UBYHOST_SHOTS_DIR") or "/tmp/ubyhost-b14")
GROUPS_0972 = ("account", "security", "technical", "help")
VIEWS_0972 = [(lang, width) for lang in ("en", "cs") for width in (390, 768, 1280)]
NAME_PREFIX_0972 = {"en": "Help with ", "cs": "Nápověda: "}

PLACEMENT_JS_0972 = """
() => {
  const out = [];
  for (const btn of document.querySelectorAll('.help-tip-btn')) {
    if (!btn.getClientRects().length) continue;
    const name = btn.getAttribute('aria-label') || '';
    const anchor = btn.closest('.tip-label, h1, h2, h3, label, strong, .settings-toggle-label, .settings-value-label');
    if (!anchor) { out.push({name, problem: 'no label around the help button'}); continue; }
    const walker = document.createTreeWalker(anchor, NodeFilter.SHOW_TEXT);
    let last = null, node;
    while ((node = walker.nextNode())) {
      if (node.textContent.trim() && !node.parentElement.closest('.help-tip')) last = node;
    }
    if (!last) { out.push({name, problem: 'label has no text'}); continue; }
    const range = document.createRange();
    range.selectNodeContents(last);
    const rects = [...range.getClientRects()].filter(r => r.height > 0);
    const line = rects[rects.length - 1];
    const b = btn.getBoundingClientRect();
    const mid = b.top + b.height / 2;
    out.push({name, label: anchor.textContent.trim().slice(0, 40), problem: (mid >= line.top - 8 && mid <= line.bottom + 8) ? '' : 'help button is not on the last line of its label'});
  }
  return out;
}
"""

TIP_STATE_JS_0972 = """
(id) => {
  const body = document.getElementById(id);
  const btn = document.querySelector('[aria-controls="' + id + '"]');
  const r = body.getBoundingClientRect();
  const shown = getComputedStyle(body).display !== 'none' && r.width > 0;
  const cs = getComputedStyle(btn);
  return {
    shown, expanded: btn.getAttribute('aria-expanded'),
    left: r.left, right: r.right, top: r.top, bottom: r.bottom,
    vw: document.documentElement.clientWidth, vh: window.innerHeight,
    focusOnBtn: document.activeElement === btn,
    outlineStyle: cs.outlineStyle, outlineWidth: parseFloat(cs.outlineWidth) || 0,
    scrollW: document.documentElement.scrollWidth,
  };
}
"""


@pytest.fixture(scope="module")
def admin_0972():
    db.init_db()
    username = f"b14-0972-{secrets.token_hex(4)}"
    owner_id = auth.create_account(f"{username}@example.test", "B14 0972", role="admin", username=username)
    apartment_id = int(db.insert("apartment", {
        "owner_user_id": owner_id, "internal_name": "B14 Flat", "created_at": db.utcnow(),
    }))
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    yield {"client": client, "owner": owner_id, "apartment": apartment_id}  # rows stay: other tests share the test DB


def _open_0972(playwright, base, admin, width, lang, path):
    browser = playwright.chromium.launch(**chromium_launch_kwargs())
    context = browser.new_context(viewport={"width": width, "height": 900})
    cookie = admin["client"].cookies.get(auth.SESSION_COOKIE)
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
    page = context.new_page()
    sep = "&" if "?" in path else "?"
    page.goto(f"{base}{path}{sep}lang={lang}")
    return browser, context, page


def _shot_0972(page, name):
    SHOTS_0972.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS_0972 / f"{name}.png"), full_page=True)


def _h1_0972(html):
    match = re.search(r'<h1 class="airbnb-title">(.*?)</h1>', html, re.S)
    assert match, "no airbnb-title h1 on the page"
    return match.group(1)


# --- copy and markup tests (no browser needed, but run in the same module) ---

@pytest.mark.parametrize("lang", ("en", "cs"))
def test_0972_activity_copy_is_plural_aware(lang):
    one = translate_plural(lang, "settings.audit.recent", 1)
    many = translate_plural(lang, "settings.audit.recent", 5)
    zero = translate_plural(lang, "settings.audit.recent", 0)
    assert "(1 " in one and "(5 " in many and "(0 " in zero
    assert one != many
    if lang == "en":
        assert one.endswith("(1 event)") and many.endswith("(5 events)") and zero.endswith("(0 events)")
    else:
        assert one.endswith("(1 událost)") and translate_plural(lang, "settings.audit.recent", 3).endswith("(3 události)")
        assert many.endswith("(5 událostí)")


def test_0972_technical_page_uses_the_plural_form_for_its_count(admin_0972):
    html = admin_0972["client"].get("/settings/technical?lang=en").text
    match = re.search(r"Recent activity \((\d+) (event|events)\)", html)
    assert match, "recent-activity heading not found"
    assert match.group(2) == ("event" if match.group(1) == "1" else "events")


def test_0972_h1_is_the_short_title_only(admin_0972):
    client = admin_0972["client"]
    for group, title in (("account", "Account"), ("security", "Security"), ("technical", "Technical"), ("help", "Help")):
        h1 = _h1_0972(client.get(f"/settings/{group}?lang=en").text)
        assert h1.strip() == title, (group, h1)
    h1 = _h1_0972(client.get(f"/apartments/{admin_0972['apartment']}?lang=en").text)
    assert "page-help" not in h1 and "<details" not in h1 and "<ol" not in h1, h1
    assert h1.strip() == "B14 Flat", h1


def test_0972_property_help_is_a_sibling_of_the_h1(admin_0972):
    html = admin_0972["client"].get(f"/apartments/{admin_0972['apartment']}?lang=en").text
    after = html.split("</h1>", 1)[1]
    assert after.lstrip().startswith('<details class="page-help"'), after[:200]


def test_0972_every_settings_help_button_has_its_own_name(admin_0972):
    client = admin_0972["client"]
    for lang, prefix in NAME_PREFIX_0972.items():
        for group in GROUPS_0972:
            html = client.get(f"/settings/{group}?lang={lang}").text
            names = re.findall(r'class="help-tip-btn" aria-label="([^"]*)"', html)
            assert names, (group, lang)
            assert all(n.startswith(prefix) and len(n) > len(prefix) for n in names), (group, lang, names)
            assert len(set(names)) == len(names), (group, lang, names)


def test_0972_passkeys_and_help_labels_are_not_repeated(admin_0972):
    client = admin_0972["client"]
    security = client.get("/settings/security?lang=en").text
    assert security.count(">Passkeys<") == 1
    assert ">Registered<" in security
    helppage = client.get("/settings/help?lang=en").text
    assert ">User guide<" in helppage and ">Open user guide<" in helppage
    assert 'href="/guide" aria-label=' not in helppage
    cs = client.get("/settings/help?lang=cs").text
    assert ">Otevřít příručku<" in cs


@pytest.mark.parametrize("backend", ("disabled", "console", "ses"))
@pytest.mark.parametrize("lang", ("en", "cs"))
def test_0972_mail_status_reports_the_runtime_backend(admin_0972, monkeypatch, backend, lang):
    monkeypatch.setattr(config, "MAIL_BACKEND", backend)
    html = admin_0972["client"].get(f"/settings/technical?lang={lang}").text
    assert f'data-mail-backend="{backend}"' in html
    assert HOST_STRINGS_0972[lang][f"settings.mail.status.{backend}"] in html
    for other in {"disabled", "console", "ses"} - {backend}:
        assert HOST_STRINGS_0972[lang][f"settings.mail.status.{other}"] not in html
    assert "Staging uses the console backend" not in html and "Production stays disabled" not in html


# --- Chromium: placement, keyboard, viewport, H1, mail status ---

@pytest.mark.parametrize("lang,width", VIEWS_0972)
def test_0972_help_stays_beside_its_label_with_a_contextual_name(admin_0972, base, lang, width):
    problems = []
    with sync_api.sync_playwright() as playwright:
        for group in GROUPS_0972:
            browser, context, page = _open_0972(playwright, base, admin_0972, width, lang, f"/settings/{group}")
            for item in page.evaluate(PLACEMENT_JS_0972):
                if item["problem"]:
                    problems.append(f"{group} {lang} {width}: {item['problem']}: {item.get('label') or item['name']}")
                if not item["name"].startswith(NAME_PREFIX_0972[lang]):
                    problems.append(f"{group} {lang} {width}: generic help name {item['name']!r}")
            if page.evaluate("() => document.documentElement.scrollWidth > document.documentElement.clientWidth"):
                problems.append(f"{group} {lang} {width}: page scrolls sideways")
            _shot_0972(page, f"settings-{group}-{lang}-{width}")
            context.close()
            browser.close()
    assert not problems, "\n".join(problems[:30])


@pytest.mark.parametrize("lang,width", [("en", 390), ("en", 768), ("en", 1280), ("cs", 390)])
def test_0972_help_opens_by_pointer_and_keyboard_and_stays_in_the_viewport(admin_0972, base, lang, width):
    problems = []
    with sync_api.sync_playwright() as playwright:
        for group in GROUPS_0972:
            browser, context, page = _open_0972(playwright, base, admin_0972, width, lang, f"/settings/{group}")
            buttons = [b for b in page.locator(".help-tip-btn").all() if b.is_visible()]
            assert buttons, f"{group}: no visible help button"
            for pick, btn in (("first", buttons[0]), ("last", buttons[-1])):
                tip_id = btn.get_attribute("aria-controls")
                where = f"{group} {lang} {width} {pick} ({tip_id})"
                btn.evaluate("e => e.scrollIntoView({block: 'center'})")
                # pointer
                btn.click()
                state = page.evaluate(TIP_STATE_JS_0972, tip_id)
                if not (state["shown"] and state["expanded"] == "true"):
                    problems.append(f"{where}: click did not open the help")
                if state["left"] < -0.5 or state["right"] > state["vw"] + 0.5:
                    problems.append(f"{where}: popover leaves the viewport sideways ({state['left']:.0f}..{state['right']:.0f} of {state['vw']})")
                if state["top"] < -0.5 or state["bottom"] > state["vh"] + 0.5:
                    problems.append(f"{where}: popover leaves the viewport vertically ({state['top']:.0f}..{state['bottom']:.0f} of {state['vh']})")
                if group == "security" and pick == "first" and lang == "en" and width == 390:
                    _shot_0972(page, "help-open-pointer-security-390")
                page.keyboard.press("Escape")
                state = page.evaluate(TIP_STATE_JS_0972, tip_id)
                if state["shown"] or state["expanded"] != "false":
                    problems.append(f"{where}: Escape did not close the help")
                if not state["focusOnBtn"]:
                    problems.append(f"{where}: focus did not return to the help button after Escape")
                # keyboard: reach the button with Tab, so :focus-visible applies
                page.evaluate("() => { document.activeElement && document.activeElement.blur(); window.scrollTo(0, 0); }")
                reached = False
                for _ in range(150):
                    page.keyboard.press("Tab")
                    if page.evaluate("(id) => document.activeElement && document.activeElement.getAttribute('aria-controls') === id", tip_id):
                        reached = True
                        break
                if not reached:
                    problems.append(f"{where}: Tab never reached the help button")
                    continue
                state = page.evaluate(TIP_STATE_JS_0972, tip_id)
                if state["outlineStyle"] == "none" or state["outlineWidth"] < 1:
                    problems.append(f"{where}: focus ring not visible on the help button")
                page.keyboard.press("Enter")
                state = page.evaluate(TIP_STATE_JS_0972, tip_id)
                if not (state["shown"] and state["expanded"] == "true"):
                    problems.append(f"{where}: Enter did not open the help")
                if state["left"] < -0.5 or state["right"] > state["vw"] + 0.5:
                    problems.append(f"{where}: keyboard-opened popover leaves the viewport sideways")
                page.keyboard.press("Escape")
                state = page.evaluate(TIP_STATE_JS_0972, tip_id)
                if state["shown"] or not state["focusOnBtn"]:
                    problems.append(f"{where}: keyboard Escape did not close and return focus")
                page.keyboard.press("Enter")
                page.keyboard.press("Tab")
                state = page.evaluate(TIP_STATE_JS_0972, tip_id)
                if state["shown"] or state["focusOnBtn"]:
                    problems.append(f"{where}: Tab did not move on and close the help")
            context.close()
            browser.close()
    assert not problems, "\n".join(problems[:30])


@pytest.mark.parametrize("lang,width", VIEWS_0972)
def test_0972_property_h1_stays_short_while_its_help_is_open(admin_0972, base, lang, width):
    path = f"/apartments/{admin_0972['apartment']}"
    problems = []
    with sync_api.sync_playwright() as playwright:
        browser, context, page = _open_0972(playwright, base, admin_0972, width, lang, path)
        summary = page.locator(".airbnb-header > .page-help > summary").first
        if not summary.count():
            problems.append("no .airbnb-header > .page-help > summary beside the property H1")
        else:
            summary.click()
            h1 = page.evaluate("() => document.querySelector('h1.airbnb-title').textContent.trim()")
            if h1 != "B14 Flat":
                problems.append(f"H1 text is {h1!r}")
            if page.evaluate("() => !!document.querySelector('h1.airbnb-title details, h1.airbnb-title .page-help-body')"):
                problems.append("help content sits inside the H1")
            box = page.evaluate("""() => { const r = document.querySelector('.page-help-body').getBoundingClientRect();
                return {left: r.left, right: r.right, vw: document.documentElement.clientWidth}; }""")
            if box["left"] < -0.5 or box["right"] > box["vw"] + 0.5:
                problems.append(f"page help leaves the viewport sideways: {box}")
            _shot_0972(page, f"property-help-open-{lang}-{width}")
        context.close()
        browser.close()
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("lang,width", VIEWS_0972)
def test_0972_mail_status_with_mail_disabled_in_the_browser(admin_0972, base, monkeypatch, lang, width):
    monkeypatch.setattr(config, "MAIL_BACKEND", "disabled")
    with sync_api.sync_playwright() as playwright:
        browser, context, page = _open_0972(playwright, base, admin_0972, width, lang, "/settings/technical")
        status = page.locator("#settings-mail-status")
        assert status.is_visible()
        assert status.inner_text().strip() == HOST_STRINGS_0972[lang]["settings.mail.status.disabled"]
        assert page.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        status.scroll_into_view_if_needed()
        _shot_0972(page, f"technical-mail-disabled-{lang}-{width}")
        context.close()
        browser.close()
B14_TESTS_EOF
.venv/bin/python -m py_compile tests/test_0786_settings_geometry_browser.py 2>&1 | tail -5
git add tests/test_0786_settings_geometry_browser.py && git commit -q -m "0972 step 3" 2>&1 | tail -3
```

### Step 4: run the tests (section 6), fix once, view screenshots, write the report (section 9)

## 5. Do not touch

- `App/app/static/*` (CSS and JS), `App/app/mail.py`, `App/app/config.py`, `App/app/routes/*`, `App/app/auth.py`, any env or secret file, `docs/` other than your report and the status line of this brief.
- Mail backend, SES, login, 2FA, passkey and session behaviour: you change text and markup only.
- No new dependency. No push, no PR, no merge, no deploy (hand back to the orchestrator in the report).
- Never use `git add -A`. Before each commit run `git status` and `git diff --staged | grep -iE 'secret|token|api[_-]?key|password|AKIA|ghp_'`; nothing may match.

## 6. Commands

All from `/tmp/ubyhost-b14-worktree/App`, each ending `2>&1 | tail -30`. Browser rows need `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b14`, `-rs`, and **0 skipped** (a skip is a failure).

```
# A. new tests plus the settings geometry file (browser, 0 skipped)
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b14 .venv/bin/python -m pytest tests/test_0786_settings_geometry_browser.py -q -rs --tb=short -x 2>&1 | tail -30

# B. settings and status-rendering tests
.venv/bin/python -m pytest tests/test_settings_technical.py tests/test_0789_settings_subpages.py tests/test_0789b_settings_toggles.py tests/test_design_settings.py tests/test_settings_data_panel.py tests/test_copy_property_settings.py tests/test_passkeys.py -q --tb=short -x 2>&1 | tail -30

# C. copy tests
.venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py -q --tb=short -x 2>&1 | tail -30

# D. host pages, geometry, guardrails, layout lint (browser, 0 skipped)
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b14 .venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py tests/test_layout_lint_browser.py -q -rs --tb=short -x 2>&1 | tail -30

# E. static cache keys (no static file changed; must pass untouched)
.venv/bin/python -m pytest tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30

# F. context lint, from the repo root
cd /tmp/ubyhost-b14-worktree && python3 scripts/context_lint.py 2>&1 | tail -30
```
Expected: every command ends `N passed` with no failed, no error, no skipped. Run A first; if A fails read the last 30 lines, fix **once** (only within §3 files), rerun; a second failure: STOP.

Screenshots land in `/tmp/ubyhost-b14/` as `settings-<group>-<lang>-<width>.png` (groups account, security, technical, help; en and cs; 390, 768, 1280), `help-open-pointer-security-390.png`, `property-help-open-<lang>-<width>.png`, `technical-mail-disabled-<lang>-<width>.png`. View exactly these 8 (one Read each) and describe each in one line in the report: `settings-account-en-390`, `settings-security-en-390`, `help-open-pointer-security-390`, `settings-technical-en-390`, `technical-mail-disabled-en-390`, `settings-help-en-390`, `property-help-open-en-390`, `settings-security-cs-768`. The other shots exist for the orchestrator; say "not viewed" for them. Never save screenshots anywhere else, never commit them.

## 7. Acceptance

Each line: PASS or FAIL in the report, with the test or screenshot that proves it.
- [ ] Account, Security, Technical, Help: H1 is exactly the short title (test `test_0972_h1_is_the_short_title_only`).
- [ ] Property heading: H1 is exactly the property name, also with the help open; the help panel is a sibling after `</h1>` (tests `test_0972_property_help_is_a_sibling_of_the_h1`, `test_0972_property_h1_stays_short_while_its_help_is_open`).
- [ ] Help "?" is on the last line of its label on all four pages, EN and CS, 390/768/1280, no sideways scroll (`test_0972_help_stays_beside_its_label_with_a_contextual_name`).
- [ ] Every settings help button has a contextual, unique name ("Help with ...", "Nápověda: ...") (`test_0972_every_settings_help_button_has_its_own_name`).
- [ ] Help opens by pointer and by keyboard (Tab then Enter); Escape closes and returns focus to the "?"; Tab moves on and closes; focus ring visible; the popover stays inside the viewport at 390, 768 and 1280 (`test_0972_help_opens_by_pointer_and_keyboard_and_stays_in_the_viewport`).
- [ ] Activity heading: zero ("0 events"), one ("1 event"), many; Czech one/few/many (`test_0972_activity_copy_is_plural_aware`, `test_0972_technical_page_uses_the_plural_form_for_its_count`).
- [ ] Mail status shows the runtime backend for `disabled`, `console`, `ses` in EN and CS, with no staging/production prose; with mail disabled it says sending is off (`test_0972_mail_status_reports_the_runtime_backend`, `test_0972_mail_status_with_mail_disabled_in_the_browser`).
- [ ] Passkeys appears once as a label; the Help page row says "User guide" / "Open user guide" (`test_0972_passkeys_and_help_labels_are_not_repeated`).
- [ ] Commands A to F green, 0 skipped. `git diff --stat` shows only the files in §3. No file under `App/app/static`, `App/app/mail.py`, `App/app/config.py`, `App/app/routes` changed.
- [ ] The 8 screenshots viewed and described (sections cut, overlapping text, a "?" alone on a line, a popover beyond the screen edge are FAIL).

## 8. Stop and ask

Stop, and write the report (`Status: blocked`), if:
- an anchor or excerpt is not found, or `git apply --check` fails;
- a test fails twice, or any browser test is skipped;
- test A finds a "?" that is not on the last line of its label, or a popover outside the viewport, and one fix inside §3 files does not cure it (a CSS or app.js change would be needed: that is a new brief, do not do it);
- a test in B to E that you did not write fails because of your patch and the fix is outside §3;
- `test_static_versions.py` fails (do not edit `static_versions.json`);
- you reach 25 tool calls or about 50k tokens (see executor.md, write `Done: steps 1 to k. Left: steps k+1 to n.`);
- you would need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0972-report.md` (600 tokens at most): `git diff --stat`; each command with the last 5 lines of output; the §7 list with PASS or FAIL per line; one line per viewed screenshot (file name plus what you saw); Deviations; Questions; owner steps left. Set `Status: review` in this brief, commit `0972 report` (report and brief only). Do **not** push and do **not** open a PR: the orchestrator does that after reading the report.

## Risk list (for the reviewer)

- `App/app/templates/partials/settings_back_header.html` (shared by about 18 pages: the `help_is_page` branch must not change pages that pass a `help_tip` or no help).
- `App/app/templates/_components.html` (`tip_label` and `settings_heading` now name their "?" buttons site-wide; `help_tip` default is unchanged).
- `App/app/templates/settings.html` (rows moved from `<strong>` plus `help_tip` to `tip_label`; mail status line).

## Owner steps

None for this brief. After review the orchestrator pushes `codex/0972-b14-help-settings` and merges with `scripts/merge-pr-on-green.sh`; the production deploy stays manual.
