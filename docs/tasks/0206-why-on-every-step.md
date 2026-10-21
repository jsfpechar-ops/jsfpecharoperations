# 0206: Say why on every setup step and settings section

Status: review
Depends on: 0207 | Base commit: 2a32c64 | Branch: claude/project-thread-cf47ju
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

A new host in the first user test did not understand what several wizard steps were for. Every wizard step and the matching property-settings section now opens with one plain sentence or two saying what it is for and why UbyHost asks (Josef: write for a complete beginner, always say WHY).

## 2. Context

Text only: one new i18n block (en, cs) plus Vietnamese, and templates switch to the new keys. Old keys stay defined (other pages use some of them); do not delete any key.

The host i18n pattern (`App/app/host_i18n.py`, end of the 0205 block, verbatim):

```
for _lang, _strings in _ONBOARDING_TEST_0205_STRINGS.items():
    STRINGS[_lang].update(_strings)

STRINGS["vi"] = dict(_VI_STRINGS)
```

`App/app/host_vi_i18n.py` ends with a `STRINGS.update({ ... })` block whose last line is `})`.

`ui-sub` is an existing catalog class; no new CSS class may be added.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/host_i18n.py | edit | new `_ONBOARDING_TEST_0206_STRINGS` block |
| App/app/host_vi_i18n.py | edit | Vietnamese for the same keys |
| App/app/templates/setup_wizard/property.html | edit | lede, times, address why |
| App/app/templates/setup_wizard/calendar.html | edit | lede |
| App/app/templates/setup_wizard/guest_link.html | edit | lede |
| App/app/templates/setup_wizard/try_it.html | edit | lede (first one only) |
| App/app/templates/setup_wizard/police.html | edit | lede |
| App/app/templates/setup_wizard/stay_fee.html | edit | lede |
| App/app/templates/setup_wizard/door_lock.html | edit | lede, times |
| App/app/templates/setup_wizard/automation.html | edit | lede |
| App/app/templates/_property_editor.html | edit | why lines in settings sections |
| App/app/templates/_entity_business_fields.html | edit | why line on Business details |
| App/tests/test_calendar_platform_required.py | edit | only if its pin fails (Step 6) |
| App/tests/test_onboarding_why_0206.py | create | pins |

No other file may change.

## 4. Steps

### Step 1. `App/app/host_i18n.py`

Insert this block directly above the line `STRINGS["vi"] = dict(_VI_STRINGS)` (keep one blank line before it):

```python
_ONBOARDING_TEST_0206_STRINGS = {
    "en": {
        "why.business": "The operator is whoever runs the accommodation: you as a person (sole trader) or your company. These details are printed on the reports for the police and the town, and on invoices. Type your IČO and tap Fill from register, and we fill in the rest.",
        "why.property": "Here you tell UbyHost which accommodation this is: what you call it, when guests arrive and leave, who runs it and where it is. You only fill this in once.",
        "why.address": "The police and the town need the exact address where your guests stay. Copy it from the police letter or from the land register extract.",
        "why.times": "UbyHost uses these times to decide when a guest's door code starts and stops working, and when cleaning can come. Door codes do not work without them.",
        "why.calendar": "When you connect your Airbnb or Booking.com calendar, every new booking appears here by itself and you do not retype anything. You find the link in your listing settings, under Export calendar (iCal).",
        "why.guest_link": "Every guest has to give their details for the police. Send them this link and PIN, and they fill them in on their own phone before they arrive. You retype nothing.",
        "why.try": "See what your guests will see. Fill in the form yourself with made-up details. Nothing is sent to the police, and you can delete the demo afterwards.",
        "why.police": "Every foreign guest has to be reported to the police within three working days of arrival. UbyHost does it for you through Ubyport. It needs the login the police sent you by letter.",
        "why.police_wait": "Don't have it yet? Tap “I'm still waiting for my police login” and carry on.",
        "why.stay_fee": "Most towns charge guests a stay fee (at most 50 CZK per person per night) and want a regular report about it. UbyHost works out the fee for every stay and prepares the report and a QR code for the payment. You find the rate, the variable symbol and the account on your town's website or in your registration letter.",
        "why.stay_fee_skip": "Your town does not charge it? Skip this step.",
        "why.door_lock": "Optional. Do you have a TTLock smart lock with a gateway? Then UbyHost makes a door code for each stay that works only during that stay. The guest gets it once everyone has registered, so you never hand over keys.",
        "why.automation": "Choose when UbyHost reports your guests to the police. We recommend the delay: you have time to check the details and you never miss the three-day deadline. You can change this at any time.",
        "wizard.automation.manual_detail": "You press Send when a stay is ready to report.",
    },
    "cs": {
        "why.business": "Provozovatel je ten, kdo ubytování provozuje: vy jako osoba (OSVČ), nebo vaše firma. Jeho údaje se tisknou na hlášení pro policii a obec a na faktury. Zadejte IČO a klepněte na Vyplnit z registru, zbytek doplníme za vás.",
        "why.property": "Tady UbyHostu řeknete, o jaké ubytování jde: jak mu říkáte, kdy hosté přijíždějí a odjíždějí, kdo ho provozuje a kde je. Vyplníte to jen jednou.",
        "why.address": "Policie i obec potřebují přesnou adresu, kde vaši hosté bydlí. Opište ji z dopisu od policie nebo z listu vlastnictví.",
        "why.times": "Podle těchto časů UbyHost nastaví, od kdy do kdy platí vstupní kód hosta a kdy může přijít úklid. Bez nich kódy ke dveřím nefungují.",
        "why.calendar": "Když připojíte kalendář z Airbnb nebo Booking.com, každá nová rezervace se tu objeví sama a nemusíte nic opisovat. Odkaz najdete v nastavení inzerátu pod názvem Export kalendáře (iCal).",
        "why.guest_link": "Každý host musí vyplnit své údaje pro policii. Pošlete mu tento odkaz a PIN a host je vyplní sám na svém telefonu, ještě před příjezdem. Vy nic nepřepisujete.",
        "why.try": "Podívejte se, co uvidí váš host. Vyplňte formulář sami s vymyšlenými údaji. Nic se neodešle policii a ukázku pak můžete smazat.",
        "why.police": "Každého cizince musíte nahlásit policii do tří pracovních dnů od příjezdu. UbyHost to udělá za vás přes Ubyport. Potřebuje k tomu přihlašovací údaje, které vám policie poslala dopisem.",
        "why.police_wait": "Ještě je nemáte? Klepněte na „Na přihlašovací údaje od policie ještě čekám“ a pokračujte.",
        "why.stay_fee": "Většina obcí vybírá od hostů poplatek z pobytu (nejvýš 50 Kč za osobu a noc) a chce za něj pravidelné hlášení. UbyHost poplatek spočítá u každého pobytu a připraví hlášení i QR kód pro platbu. Sazbu, variabilní symbol a účet najdete na webu obce nebo v dopise o registraci.",
        "why.stay_fee_skip": "Obec poplatek nevybírá? Tento krok přeskočte.",
        "why.door_lock": "Nepovinné. Máte chytrý zámek TTLock s bránou? UbyHost pak každému pobytu vytvoří vlastní vstupní kód, platný jen po dobu pobytu. Host ho dostane, jakmile se všichni zaregistrují, a vy nemusíte předávat klíče.",
        "why.automation": "Vyberte, kdy má UbyHost hosty nahlásit policii. Doporučujeme odeslání s prodlevou: máte čas údaje zkontrolovat a lhůtu tří pracovních dnů nezmeškáte. Volbu můžete kdykoli změnit.",
        "wizard.automation.manual_detail": "Odeslání spustíte tlačítkem Odeslat, až je pobyt připraven.",
    },
}
for _lang, _strings in _ONBOARDING_TEST_0206_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

### Step 2. `App/app/host_vi_i18n.py`

Append at the very end of the file:

```python

# 0206: why on every step.
STRINGS.update({
    "why.business": "Người vận hành là người điều hành chỗ ở: chính bạn (hộ kinh doanh cá thể) hoặc công ty của bạn. Các thông tin này được in trên báo cáo gửi cảnh sát, chính quyền địa phương và trên hóa đơn. Nhập IČO và bấm Điền từ sổ đăng ký, chúng tôi sẽ điền phần còn lại.",
    "why.property": "Tại đây bạn cho UbyHost biết đây là chỗ ở nào: bạn gọi nó là gì, khách đến và đi lúc mấy giờ, ai vận hành và nó ở đâu. Bạn chỉ cần điền một lần.",
    "why.address": "Cảnh sát và chính quyền địa phương cần địa chỉ chính xác nơi khách của bạn lưu trú. Hãy chép lại từ thư của cảnh sát hoặc từ trích lục sổ địa chính.",
    "why.times": "UbyHost dùng các giờ này để quyết định mã cửa của khách bắt đầu và hết hiệu lực khi nào, và khi nào có thể dọn dẹp. Không có chúng, mã cửa sẽ không hoạt động.",
    "why.calendar": "Khi bạn kết nối lịch Airbnb hoặc Booking.com, mỗi đặt phòng mới sẽ tự hiện ở đây và bạn không phải gõ lại gì. Liên kết nằm trong phần cài đặt tin đăng, mục Xuất lịch (iCal).",
    "why.guest_link": "Mỗi khách phải cung cấp thông tin cho cảnh sát. Gửi cho họ liên kết và mã PIN này, họ sẽ tự điền trên điện thoại trước khi đến. Bạn không phải gõ lại gì.",
    "why.try": "Xem khách của bạn sẽ thấy gì. Tự điền biểu mẫu bằng thông tin giả. Không có gì được gửi cho cảnh sát, và bạn có thể xóa bản thử sau đó.",
    "why.police": "Mỗi khách nước ngoài phải được khai báo với cảnh sát trong vòng ba ngày làm việc kể từ khi đến. UbyHost làm việc này cho bạn qua Ubyport. Nó cần thông tin đăng nhập mà cảnh sát đã gửi cho bạn qua thư.",
    "why.police_wait": "Chưa có? Bấm “Tôi vẫn đang chờ thông tin đăng nhập từ cảnh sát” và tiếp tục.",
    "why.stay_fee": "Hầu hết các địa phương thu phí lưu trú của khách (tối đa 50 CZK mỗi người mỗi đêm) và yêu cầu báo cáo định kỳ. UbyHost tính phí cho từng lượt lưu trú và chuẩn bị báo cáo cùng mã QR để thanh toán. Mức phí, mã biến số và số tài khoản có trên trang web của địa phương hoặc trong thư đăng ký.",
    "why.stay_fee_skip": "Địa phương của bạn không thu phí này? Hãy bỏ qua bước này.",
    "why.door_lock": "Không bắt buộc. Bạn có khóa thông minh TTLock kèm gateway? Khi đó UbyHost tạo cho mỗi lượt lưu trú một mã cửa chỉ dùng được trong thời gian lưu trú. Khách nhận mã khi mọi người đã đăng ký xong, nên bạn không cần giao chìa khóa.",
    "why.automation": "Chọn khi nào UbyHost khai báo khách với cảnh sát. Chúng tôi khuyên dùng gửi sau một khoảng chờ: bạn có thời gian kiểm tra thông tin và không bao giờ trễ hạn ba ngày. Bạn có thể đổi lựa chọn này bất cứ lúc nào.",
})
```

### Step 3. Wizard templates (`App/app/templates/setup_wizard/`)

Each replacement is exact; each anchor occurs once.

a) `property.html`:
- `<p class="setup-wizard-lede">{{ t('apartment.form.basics.title') }}</p>` → `<p class="setup-wizard-lede">{{ t('why.property') }}</p>`
- `<p class="setup-wizard-instruction">{{ t('host.property_times_hint') }}</p>` → `<p class="setup-wizard-instruction">{{ t('why.times') }}</p>`
- `  <h3 class="property-section-title">{{ t('apartment.form.address.title') }}</h3>` → the same line followed by a new line `  <p class="setup-wizard-instruction">{{ t('why.address') }}</p>`

b) `calendar.html`: `{{ t('setup_guide.calendar.text') }}` → `{{ t('why.calendar') }}`

c) `guest_link.html`: `{{ t('wizard.guest_link.share_lede') }}` → `{{ t('why.guest_link') }}`

d) `try_it.html`: `{{ t('setup_guide.try.text') }}` → `{{ t('why.try') }}` (the line with `setup-try-help`; leave `registered_text` alone)

e) `police.html`: `<p class="setup-wizard-lede">{{ t('setup_guide.reporting.text') }}</p>` → `<p class="setup-wizard-lede">{{ t('why.police') }} {{ t('why.police_wait') }}</p>`

f) `stay_fee.html`: `{{ t('setup_guide.fee.text') }}` → `{{ t('why.stay_fee') }} {{ t('why.stay_fee_skip') }}`

g) `door_lock.html`:
- `{{ t('wizard.door_lock.intro') }}` → `{{ t('why.door_lock') }}`
- `<p class="setup-wizard-instruction">{{ t('host.property_times_hint') }}` → `<p class="setup-wizard-instruction">{{ t('why.times') }}`

h) `automation.html`: `{{ t('setup_guide.automation.text') }}` → `{{ t('why.automation') }}`

### Step 4. `App/app/templates/_property_editor.html` (settings sections)

a) Address. After the line `      <h3 class="property-section-title">{{ t('apartment.form.address.title') }}</h3>` add `      <p class="ui-sub">{{ t('why.address') }}</p>`.

b) Times. `      <p class="ui-sub">{{ t('host.property_times_hint') }}</p>` → `      <p class="ui-sub">{{ t('why.times') }}</p>`
   and `      <p class="ui-sub">{{ t('host.property_times_hint') }}` (the lock section line, no `</p>` on it) → `      <p class="ui-sub">{{ t('why.times') }}`

c) Guest link. After the line starting `      <div class="field-label-row"><h3 class="property-section-title">{{ t('nav.guest_links') }}</h3>` add `      <p class="ui-sub">{{ t('why.guest_link') }}</p>`.

d) Lock. `    <p class="property-group-intro">{{ t('property_nav.lock_intro') }}</p>` → `    <p class="property-group-intro">{{ t('why.door_lock') }}</p>`

e) Police. Replace `      <p class="ui-sub"><a href="{{ base_url }}?view=settings&amp;section=automation#automation">{{ t('automation.timing_title') }} </a></p>` with
```
      <p class="ui-sub">{{ t('why.police') }}</p>
      <p class="ui-sub"><a href="{{ base_url }}?view=settings&amp;section=automation#automation">{{ t('automation.timing_title') }} </a></p>
```

f) Stay fee. After the line starting `      <div class="field-label-row"><h3 class="property-section-title">{{ t('apartment.form.stay_fee.heading') }}</h3>` add `      <p class="ui-sub">{{ t('why.stay_fee') }}</p>`.

g) Automation. After the line starting `      <div class="field-label-row"><h3 class="property-section-title">{{ t('automation.timing_title') }}</h3>` add `      <p class="ui-sub">{{ t('why.automation') }}</p>`.

### Step 5. `App/app/templates/_entity_business_fields.html`

In `business_form_body`, replace `  <p class="required-legend">{{ t('common.required_legend') }}</p>` with
```
  <p class="ui-sub">{{ t('why.business') }}</p>
  <p class="required-legend">{{ t('common.required_legend') }}</p>
```
If that anchor occurs more than once in the file, change only the one inside `business_form_body` and say so in the report.

### Step 6. Tests

Create `App/tests/test_onboarding_why_0206.py`:

```python
"""0206: every setup step and settings section says why it asks."""

from app import host_i18n

KEYS = (
    "why.business", "why.property", "why.address", "why.times", "why.calendar",
    "why.guest_link", "why.try", "why.police", "why.police_wait", "why.stay_fee",
    "why.stay_fee_skip", "why.door_lock", "why.automation",
)


def test_why_keys_exist_in_every_host_language():
    for lang in ("en", "cs", "vi"):
        for key in KEYS:
            text = host_i18n.STRINGS[lang].get(key, "")
            assert text and text != key, (lang, key)


def test_czech_manual_detail_has_no_english_button():
    assert "Send" not in host_i18n.STRINGS["cs"]["wizard.automation.manual_detail"]
```

Check how other tests import `host_i18n` (`grep -n "import host_i18n" App/tests/test_host_i18n.py | head -3`) and match it if it differs.

Run (from `App/`): `.venv/bin/python -m pytest tests/test_onboarding_why_0206.py tests/test_calendar_platform_required.py tests/test_onboarding_wizard_survival.py tests/test_fee_setup_compatibility.py tests/test_property_readiness.py -q --tb=short 2>&1 | tail -30`.

If `test_calendar_platform_required.py` fails only because it looks for `"Paste the calendar link."` on the wizard calendar step, change that pin to `"every new booking appears here by itself"`. Any other failure that pins an old lede text: update the pin to a phrase of the new `why.*` English text and list each in the report. A failure of any other kind: STOP (§8).

### Step 7. Commit

`git add` only the §3 files. Commit `0206 why on every step` with the two trailer lines from your prompt. Never commit PNGs under docs/tasks/*-evidence.

## 5. Do not touch

Guest templates, filing code (`reporting.py`, `ubyport*`), CSS, JS, every file not in §3. Do not delete any i18n key. AGENTS hard rules 1, 3, 5, 6, 8.

## 6. Commands

1. From `App/`: Step 6 command → all pass.
2. From `App/`: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_onboarding_wizard_browser.py tests/test_design_setup_wizard_browser.py tests/test_host_ux_acceptance.py -q --tb=line -rs 2>&1 | tail -30` (0 skipped; list every failure by name). A failure that pins old text: update the pin as in Step 6.
3. From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -10` → `OK`
4. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -10`
5. From `App/`: `.venv/bin/python -m pytest tests/test_host_i18n.py -q --tb=line 2>&1 | tail -15`. Known failures on main, not ours: three tests about the language endpoint and Vietnamese. Report any other.

## 7. Acceptance

- [ ] Every wizard step shows its `why.*` text; the settings sections in Step 4 show theirs.
- [ ] §6 commands pass apart from the known failures named there.

## 8. Stop and ask

As in TEMPLATE.md §8: an anchor not found verbatim, a test failure that is not an old-text pin, or a change needed outside §3.

## 9. Report

`docs/tasks/0206-report.md`, as in TEMPLATE.md §9.
