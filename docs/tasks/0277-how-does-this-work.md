# 0277: "How does this work?" on each main host page (idea P)

Status: todo
Depends on: 0270-0276, main with #427 | Branch: claude/project-thread-4b2e7k (commit here, do not push)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Hosts forget how the app works after setup. Give each main host page one small, closed-by-default "How does this work?" disclosure under the page title: three short numbered lines and a link to the guide. No paragraphs on the page itself (it stays closed until tapped), no JavaScript (native `<details>`), visible borders.

## 2. Context

- `App/app/templates/host_page.html` renders every host page header (`<header class="ui-ph">`). Pages set variables at the top (`{% set nav = … %}`).
- Strings live in `App/app/host_i18n.py` (EN and CS blocks, merged with a `for _lang, _strings in ….items(): STRINGS[_lang].update(_strings)` loop, see `_WELCOME_0275_STRINGS` near the end, just before `STRINGS["vi"] = dict(_VI_STRINGS)`) and `App/app/host_vi_i18n.py` (a `STRINGS.update({…})` block at the end, see `# 0275`).
- `host2.css` is an enforced stylesheet: only tokens (`var(--…)`) for margin, padding, gap, radius and font-size; no bare px there.
- New classes must be listed in `docs/design/catalog.json` under `"classes"` or the design lint fails.

## 3. Files

| Path | Action |
|---|---|
| App/app/templates/host_page.html | edit (one block) |
| App/app/templates/{dashboard,reservations,reservation_detail,apartments,apartment_form,submissions,invoices,stay_fees,housebook}.html | edit (one line each) |
| App/app/static/host2.css | append |
| App/app/templates/base.html | edit (host2.css `?v=` key) |
| App/tests/static_versions.json | regenerate |
| App/app/host_i18n.py, App/app/host_vi_i18n.py | append blocks |
| docs/design/catalog.json | add 6 classes |
| App/tests/test_page_help_0277.py | create |

No other file may change.

## 4. Steps

**Step 1. host_page.html.** Right after the line `  </header>` and before `  {% endif %}` (the `{% if page_title_html %}` block), insert:

```
  {% set how = how_key | default('') %}
  {% if how %}
  <details class="ui-how" data-how="{{ how }}">
    <summary class="ui-how-toggle">{{ icon('circle-help', 16) }}<span>{{ t('how.toggle') }}</span>{{ icon('chevron-down', 16, 'ui-how-chevron') }}</summary>
    <div class="ui-how-body">
      <ol class="ui-how-steps">
        {% for n in (1, 2, 3) %}<li>{{ t('how.' ~ how ~ '.' ~ n) }}</li>{% endfor %}
      </ol>
      {% set how_anchor = {'dashboard': 'overview', 'stays': 'stays', 'stay': 'guests', 'properties': 'setup', 'property': 'setup', 'reports': 'reporting', 'invoices': 'invoices', 'stay_fees': 'stay_fee', 'housebook': 'housebook'}[how] %}
      <a class="ui-how-more" href="/guide#{{ how_anchor }}">{{ t('how.more') }}</a>
    </div>
  </details>
  {% endif %}
```

Check `icon()` accepts a third class argument (`_icons.html` line 46: `icon(name, size=20, cls='')`). Commit.

**Step 2. Pages.** Add one line right after the `{% set nav = … %}` line of each page:

| Template | Line |
|---|---|
| dashboard.html | `{% set how_key = 'dashboard' %}` |
| reservations.html | `{% set how_key = 'stays' %}` |
| reservation_detail.html | `{% set how_key = 'stay' %}` |
| apartments.html | `{% set how_key = 'properties' %}` |
| apartment_form.html | `{% set how_key = 'property' %}` |
| submissions.html | `{% set how_key = 'reports' %}` |
| invoices.html | `{% set how_key = 'invoices' %}` |
| stay_fees.html | `{% set how_key = 'stay_fees' %}` |
| housebook.html | `{% set how_key = 'housebook' %}` |

If a page's `{% set nav %}` sits inside a block instead of at the top level, put the line next to it anyway and say so. Commit.

**Step 3. Strings.** In `host_i18n.py`, after the `_WELCOME_0275_STRINGS` loop and before `STRINGS["vi"] = …`, add a block `_HOW_0277_STRINGS = {"en": {…}, "cs": {…}}` with the same `for` loop. Keys and text (copy exactly):

EN:
```
"how.toggle": "How does this work?",
"how.more": "More in the guide",
"how.dashboard.1": "Stays arrive here from your calendar by themselves.",
"how.dashboard.2": "Each guest fills in the form from the link in your message.",
"how.dashboard.3": "Anything that needs you shows at the top. An empty list means all is well.",
"how.stays.1": "Every booking in your calendar becomes a stay here.",
"how.stays.2": "Your Airbnb or Booking.com message carries the guest link, so guests fill in the form before arrival.",
"how.stays.3": "When a guest is done, the police report goes out the way you chose for the property.",
"how.stay.1": "This is one stay with its guests.",
"how.stay.2": "Each guest shows where they are: waiting for the form, filled in, or reported.",
"how.stay.3": "Missing a guest? Send the guest link again, or add them yourself.",
"how.properties.1": "Each property has its own calendar, police login and guest link.",
"how.properties.2": "Amber marks a setup step that is still missing. Open the property to finish it.",
"how.properties.3": "Add one property for each place you rent out.",
"how.property.1": "Everything for this one property lives here.",
"how.property.2": "Amber marks what is still missing. The rest runs without you.",
"how.property.3": "Police reports for this property use its own police login.",
"how.reports.1": "Every guest from abroad is reported to the foreign police (Ubyport).",
"how.reports.2": "Reports go out by themselves or when you press Send, as set for each property.",
"how.reports.3": "Each row shows if the police accepted the report. A problem also shows on the dashboard.",
"how.invoices.1": "Issue an invoice when a guest needs one for their stay.",
"how.invoices.2": "Your operator details fill in by themselves.",
"how.invoices.3": "Download the PDF and send it to the guest.",
"how.stay_fees.1": "UbyHost adds up each property's stay fee from its guests and nights.",
"how.stay_fees.2": "Open a property for the report, the PDF and the QR code to pay.",
"how.stay_fees.3": "Mark the period as sent and paid. UbyHost does not pay for you.",
"how.housebook.1": "The house book lists every guest, as Czech law asks.",
"how.housebook.2": "It fills in by itself from the guest forms.",
"how.housebook.3": "Export it as a PDF or a file when an office asks for it.",
```

CS:
```
"how.toggle": "Jak to funguje?",
"how.more": "Více v návodu",
"how.dashboard.1": "Pobyty sem přicházejí samy z vašeho kalendáře.",
"how.dashboard.2": "Každý host vyplní formulář přes odkaz ve vaší zprávě.",
"how.dashboard.3": "Co potřebuje vás, je nahoře. Prázdný seznam znamená, že je vše v pořádku.",
"how.stays.1": "Každá rezervace z kalendáře se tu objeví jako pobyt.",
"how.stays.2": "Vaše zpráva v Airbnb nebo Booking.com obsahuje odkaz pro hosty, takže formulář vyplní před příjezdem.",
"how.stays.3": "Když host formulář dokončí, hlášení na policii odejde tak, jak jste u nemovitosti zvolili.",
"how.stay.1": "Tady je jeden pobyt a jeho hosté.",
"how.stay.2": "U každého hosta vidíte, kde je: čeká na formulář, vyplněno, nebo nahlášeno.",
"how.stay.3": "Chybí host? Pošlete odkaz znovu, nebo ho doplňte sami.",
"how.properties.1": "Každá nemovitost má vlastní kalendář, přihlášení k policii a odkaz pro hosty.",
"how.properties.2": "Oranžově je označeno, co v nastavení ještě chybí. Otevřete nemovitost a dokončete to.",
"how.properties.3": "Přidejte jednu nemovitost za každé ubytování, které pronajímáte.",
"how.property.1": "Vše k této nemovitosti najdete tady.",
"how.property.2": "Oranžově je označeno, co ještě chybí. Zbytek běží bez vás.",
"how.property.3": "Hlášení pro tuto nemovitost používají její vlastní přihlášení k policii.",
"how.reports.1": "Každého hosta ze zahraničí hlásíme cizinecké policii (Ubyport).",
"how.reports.2": "Hlášení odcházejí sama, nebo když stisknete Odeslat, podle nastavení nemovitosti.",
"how.reports.3": "U každého řádku vidíte, zda policie hlášení přijala. Problém se ukáže i na přehledu.",
"how.invoices.1": "Fakturu vystavte, když ji host k pobytu potřebuje.",
"how.invoices.2": "Údaje provozovatele se vyplní samy.",
"how.invoices.3": "Stáhněte PDF a pošlete ho hostovi.",
"how.stay_fees.1": "UbyHost sečte poplatek z pobytu každé nemovitosti podle hostů a nocí.",
"how.stay_fees.2": "Otevřete nemovitost pro hlášení, PDF a QR kód k platbě.",
"how.stay_fees.3": "Období označte jako odeslané a zaplacené. UbyHost za vás neplatí.",
"how.housebook.1": "Domovní kniha uvádí každého hosta, jak to vyžaduje zákon.",
"how.housebook.2": "Vyplňuje se sama z formulářů hostů.",
"how.housebook.3": "Když ji úřad chce, exportujte ji jako PDF nebo soubor.",
```

In `host_vi_i18n.py`, append `# 0277: "How does this work?" (Vietnamese).` and a `STRINGS.update({…})` block:
```
"how.toggle": "Hoạt động như thế nào?",
"how.more": "Xem thêm trong hướng dẫn",
"how.dashboard.1": "Lượt lưu trú tự đến đây từ lịch của bạn.",
"how.dashboard.2": "Mỗi khách điền biểu mẫu qua liên kết trong tin nhắn của bạn.",
"how.dashboard.3": "Việc cần bạn làm hiện ở trên cùng. Danh sách trống nghĩa là mọi thứ ổn.",
"how.stays.1": "Mỗi đặt phòng trong lịch trở thành một lượt lưu trú ở đây.",
"how.stays.2": "Tin nhắn Airbnb hoặc Booking.com của bạn có liên kết cho khách, nên khách điền biểu mẫu trước khi đến.",
"how.stays.3": "Khi khách điền xong, báo cáo cảnh sát được gửi theo cách bạn chọn cho chỗ ở.",
"how.stay.1": "Đây là một lượt lưu trú và các khách của nó.",
"how.stay.2": "Mỗi khách hiện trạng thái: chờ biểu mẫu, đã điền, hoặc đã khai báo.",
"how.stay.3": "Thiếu khách? Gửi lại liên kết, hoặc tự thêm khách.",
"how.properties.1": "Mỗi chỗ ở có lịch, tài khoản cảnh sát và liên kết cho khách riêng.",
"how.properties.2": "Màu cam đánh dấu bước cài đặt còn thiếu. Mở chỗ ở để hoàn tất.",
"how.properties.3": "Thêm một chỗ ở cho mỗi nơi bạn cho thuê.",
"how.property.1": "Mọi thứ của chỗ ở này đều ở đây.",
"how.property.2": "Màu cam đánh dấu những gì còn thiếu. Phần còn lại tự chạy.",
"how.property.3": "Báo cáo cho chỗ ở này dùng tài khoản cảnh sát riêng của nó.",
"how.reports.1": "Mỗi khách nước ngoài được khai báo với cảnh sát ngoại kiều (Ubyport).",
"how.reports.2": "Báo cáo tự gửi, hoặc gửi khi bạn bấm Gửi, tùy cài đặt của chỗ ở.",
"how.reports.3": "Mỗi dòng cho biết cảnh sát đã nhận báo cáo chưa. Sự cố cũng hiện trên bảng điều khiển.",
"how.invoices.1": "Xuất hóa đơn khi khách cần cho lượt lưu trú.",
"how.invoices.2": "Thông tin đơn vị kinh doanh tự điền.",
"how.invoices.3": "Tải PDF và gửi cho khách.",
"how.stay_fees.1": "UbyHost cộng phí lưu trú của từng chỗ ở theo số khách và số đêm.",
"how.stay_fees.2": "Mở chỗ ở để xem báo cáo, PDF và mã QR để thanh toán.",
"how.stay_fees.3": "Đánh dấu kỳ là đã gửi và đã trả. UbyHost không trả thay bạn.",
"how.housebook.1": "Sổ lưu trú ghi mọi khách, theo yêu cầu của luật.",
"how.housebook.2": "Sổ tự điền từ biểu mẫu của khách.",
"how.housebook.3": "Xuất PDF hoặc tệp khi cơ quan yêu cầu.",
```
Commit.

**Step 4. CSS.** Append to `host2.css`:

```
/* 0277: "How does this work?" under the page title (idea P). Closed by default, no JS. */
.host-workspace .ui-how { margin: var(--space-2) 0 var(--space-3); }
.host-workspace .ui-how-toggle { display: inline-flex; align-items: center; gap: var(--space-2); min-height: 2.75rem; padding: 0 var(--space-3); border: 1px solid var(--line-strong); border-radius: var(--radius-pill); background: var(--surface); color: var(--ink-2); font-size: var(--size-14); font-weight: 600; cursor: pointer; list-style: none; }
.host-workspace .ui-how-toggle::-webkit-details-marker { display: none; }
.host-workspace .ui-how-toggle:hover { background: var(--surface-hover); }
.host-workspace .ui-how-toggle:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }
.host-workspace .ui-how-chevron { transition: transform 0.15s ease; }
.host-workspace .ui-how[open] .ui-how-chevron { transform: rotate(180deg); }
.host-workspace .ui-how-body { max-width: 40rem; margin-top: var(--space-2); padding: var(--space-3) var(--space-4); border: 1px solid var(--line-strong); border-radius: var(--radius-md); background: var(--surface); }
.host-workspace .ui-how-steps { margin: 0; padding-left: var(--space-5); display: grid; gap: var(--space-2); color: var(--ink-2); font-size: var(--size-14); }
.host-workspace .ui-how-more { display: inline-flex; align-items: center; min-height: 2.75rem; color: var(--brand-action); font-size: var(--size-14); font-weight: 600; }
@media (prefers-reduced-motion: reduce) { .host-workspace .ui-how-chevron { transition: none; } }
```

Check the tokens used exist (`grep -n -- '--space-3:\|--space-4:\|--space-5:\|--line-strong:\|--focus-ring:\|--brand-action:' app/static/tokens.css`); if one is missing, use the nearest existing token and say so. Bump the host2.css key in `base.html` to `20261022-0277`, then from `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -3`. Commit.

**Step 5. Catalog.** In `docs/design/catalog.json` `"classes"` add `"ui-how"`, `"ui-how-toggle"`, `"ui-how-chevron"`, `"ui-how-body"`, `"ui-how-steps"`, `"ui-how-more"`. Run `python3 scripts/design_lint.py 2>&1 | tail -5` from the repo root. Commit.

**Step 6. Test.** Create `App/tests/test_page_help_0277.py`:

```python
"""0277: "How does this work?" on each main host page (idea P)."""
from __future__ import annotations

import re

import pytest

from app import demo, host_i18n
from tests.test_onboarding_wizard_survival import _full_apartment, host  # noqa: F401

KEYS = ("dashboard", "stays", "stay", "properties", "property", "reports", "invoices", "stay_fees", "housebook")


def _paths(host):
    flat = _full_apartment(host)
    stay = demo.create_demo_stay(flat["id"])
    return {
        "dashboard": "/", "stays": "/reservations", "stay": f"/reservations/{stay}",
        "properties": "/apartments", "property": f"/apartments/{flat['id']}",
        "reports": "/submissions", "invoices": "/invoices", "stay_fees": "/stay-fees", "housebook": "/housebook",
    }


@pytest.mark.parametrize("lang", ["en", "cs", "vi"])
def test_every_main_page_has_one_closed_help(host, lang):
    for key, path in _paths(host).items():
        page = host["client"].get(f"{path}{'&' if '?' in path else '?'}lang={lang}")
        assert page.status_code == 200, (key, page.status_code)
        text = page.text
        assert text.count("data-how=") == 1, key
        assert f'data-how="{key}"' in text, key
        block = text.split(f'data-how="{key}"', 1)[1].split("</details>", 1)[0]
        assert " open" not in text.split(f'data-how="{key}"', 1)[0].rsplit("<details", 1)[1], key
        assert block.count("<li>") == 3, key
        for n in (1, 2, 3):
            assert host_i18n.translate(lang, f"how.{key}.{n}") != f"how.{key}.{n}", (lang, key, n)
        assert re.search(r'href="/guide#[a-z_-]+"', block), key


def test_strings_are_short():
    for lang in ("en", "cs", "vi"):
        for key in KEYS:
            for n in (1, 2, 3):
                assert len(host_i18n.translate(lang, f"how.{key}.{n}")) <= 120, (lang, key, n)
```

Check how the file's helper translates (`host_i18n.translate(lang, key)` or another name: `grep -n '^def t\b\|^def translate' app/host_i18n.py`) and how `/` behaves for a host that has properties (it must be the dashboard with its title; if the dashboard shows the first-run welcome instead, assert no `data-how` there and say so). Run it. Commit.

## 5. Do not touch

Other templates, routes, tests. No JavaScript. Never push. Never run `playwright install`.

## 6. Commands (from `App/`)

1. `.venv/bin/python -m pytest tests/test_page_help_0277.py tests/test_static_versions.py tests/test_no_em_dashes.py tests/test_host_i18n.py tests/test_dashboard_order.py tests/test_property_hub.py -q --tb=short 2>&1 | tail -15` (test_host_i18n may show 3 failures that also fail on main: name them, do not fix them)
2. `UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/tmp/claude-0/pwb .venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py tests/test_0252_touch_sweep_browser.py tests/test_host_wide_geometry_browser.py -q --tb=line -rs -p no:cacheprovider 2>&1 | tail -15` (timeout 1200000 ms; 0 skipped)
3. From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -3 && python3 scripts/context_lint.py 2>&1 | tail -3`, then `git checkout -- docs/tasks/0102-evidence && git clean -fdq docs/tasks/0102-evidence`.

## 7. Acceptance

- [ ] Nine pages show one closed disclosure with three lines and a guide link, in EN, CS and VI.
- [ ] All three commands pass (apart from the named pre-existing test_host_i18n failures), 0 skipped.

## 8. Stop and ask

Per TEMPLATE. If a browser test fails because of the new block (overflow, tap size, contrast), stop and report the test and the message; do not change other CSS.

## 9. Report

`docs/tasks/0277-report.md` (500 tokens max), `Status: review`. Commits `0277 step k`. Do not push.
