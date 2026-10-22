# 0239: Plain fixes for every error, one exact button per alert (idea T)

Status: todo
Depends on: none | Base commit: c1ebb74 | Branch: claude/project-thread-0io75h
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Every host alert says what happened, why it matters and the next step, in plain words, and its button lands on the exact place to fix it (the police login field, the calendar list, the guest details), not on a general page. A guest record the police refused shows the same "what, then what to do" sentence on the stay page.

## 2. Context

- Foolproof workflow round 2 (ideas doc "Foolproof host workflow: ideas", owner decisions 2026-10-22): idea T, "Every error and warning says what happened, why it matters, and the next step, in that order, with the button." Copy is for novices; say "the police" rather than "UbyPort" where the host does not need the system name. No em dashes.
- `App/app/alerts.py`: `present()` builds each alert card (`display_title`, `display_detail`) for the stack in `templates/_host_alerts.html`, which is on every host page (law: a refused record must be shown on every screen; do not remove the stack). Today the card link goes to `/reservations/<id>` or `/apartments/<id>` only.
- Strings: `app/host_i18n.py` has every key twice (EN block, CS block) at 8-space indent; `app/host_vi_i18n.py` once at 4-space indent. Tests demand EN and CS have the same keys, and every VI key exists in EN with the same `%(name)s` placeholders. Stored alerts interpolate only the placeholders the old copy used, so a new value may drop a placeholder but never add one.
- Anchors that exist today: `#ubyport` (settings, section reporting), `#operator-picker` (settings, section property), `#calendars` (view bookings), `#communication` (settings, section guests), `#guests` (stay page).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/host_i18n.py` | edit | drop old lines, add the 0239 block (steps 1, 2) |
| `App/app/host_vi_i18n.py` | edit | drop old lines, add VI (steps 1, 3) |
| `App/app/alerts.py` | edit | `action_for()` + attach in `present()` (step 4) |
| `App/app/templates/_host_alerts.html` | edit | use the action (step 5) |
| `App/app/templates/reservation_detail.html` | edit | refused-record sentence (step 6) |
| `App/tests/test_plain_fixes_0239.py` | create | tests (step 7) |
| `App/tests/test_notification_copy.py`, `App/tests/test_alert_language.py`, `App/tests/test_send_controls.py`, `App/tests/test_host_guest_form.py` | edit | only assertions that pin the old wording (step 8) |
| `docs/tasks/0239-report.md` | create | report |

No other file may change.

## 4. Steps

### Step 1. Remove the old lines (one script)

From `App/`, run exactly:

```bash
.venv/bin/python - <<'EOF'
import pathlib
KEYS = """notification.reason.dates_changed_resign notification.feed_incomplete.title
notification.reason.feed_incomplete notification.reason.moved_after_report
notification.reason.submission_stuck notification.feed_error.title notification.feed_error.detail
notification.submission_immediate.title notification.submission_immediate.detail
notification.submission_transport.title notification.submission_transport.detail
notification.ubyport_auth_failed.title notification.ubyport_auth_failed.detail
notification.submission_outcome_unknown.title notification.submission_outcome_unknown.detail
notification.submission_rejected.title notification.submission_rejected.detail
notification.controller_missing.title notification.controller_missing.detail
notification.apartment_setup.title notification.sweep_failed.title notification.sweep_failed.detail
notification.guest_pin_locked_out.title notification.guest_pin_locked_out.detail hint.failed""".split()
for path, indent in (("app/host_i18n.py", 8), ("app/host_vi_i18n.py", 4)):
    p = pathlib.Path(path)
    lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
    keep = [l for l in lines if not any(l.startswith(" " * indent + '"' + k + '":') for k in KEYS)]
    print(path, len(lines) - len(keep))
    p.write_text("".join(keep), encoding="utf-8")
EOF
```

Expected output: `app/host_i18n.py 50` and `app/host_vi_i18n.py 25`. Any other number: `git checkout app/host_i18n.py app/host_vi_i18n.py` and STOP. Do not commit yet (the strings are missing until steps 2 and 3).

### Step 2. `host_i18n.py`: the 0239 block

Anchor (exact two lines):

```python
for _lang, _strings in _WORKFLOW_0230_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

Insert directly AFTER them (keep one blank line before `STRINGS["vi"] = dict(_VI_STRINGS)`):

```python

# 0239 (idea T): every alert says what happened, why it matters and what to do.
_PLAIN_FIXES_0239_STRINGS = {
    "en": {
        "notification.reason.dates_changed_resign": "The signed form names the old dates. Open the stay and check the new dates with the guest, because the police report must match the real stay.",
        "notification.feed_incomplete.title": "%(property)s: your calendar link sent almost no bookings.",
        "notification.reason.feed_incomplete": "We kept all your stays, so nothing was cancelled. Check that the calendar link is still right before the next sync.",
        "notification.reason.moved_after_report": "This stay moved after its police report went out, so the report still shows the old dates. Check the new dates with the guests, then correct the report in the UbyPort web application.",
        "notification.reason.submission_stuck": "The police refused these guests several times, so automatic sending has stopped to keep errors off your record. Fix the details marked in red, then send it again.",
        "notification.feed_error.title": "Calendar '%(feed)s' could not be read.",
        "notification.feed_error.detail": "New bookings from it will not appear until this is fixed. Check the calendar link. The calendar server said: %(error)s",
        "notification.submission_immediate.title": "%(property)s: the police report could not be sent.",
        "notification.submission_immediate.detail": "The guests are registered, but the police do not have them yet. Open the stay and send it again. Error: %(error)s",
        "notification.submission_transport.title": "%(property)s: the police system could not be reached.",
        "notification.submission_transport.detail": "Nothing was sent, so the police do not have these guests yet. Send it again from the stay a little later. Error: %(error)s",
        "notification.ubyport_auth_failed.title": "%(property)s: the police login (UBY-WS) was refused.",
        "notification.ubyport_auth_failed.detail": "Automatic reporting is paused so your police account does not get locked. Enter the UBY-WS password again, then press Save and test connection.",
        "notification.submission_outcome_unknown.title": "%(property)s: we don't know if the police got the report.",
        "notification.submission_outcome_unknown.detail": "Their answer never arrived (%(error)s), so we will not send it again by ourselves. Check in UbyPort. If the guests are missing there, send it again from the stay.",
        "notification.submission_rejected.title": "%(property)s: the police did not accept %(count)s guest record(s).",
        "notification.submission_rejected.detail": "These guests are not reported yet. Fix the details marked in red on the stay, then send it again. To fix: %(failed)s. Sending again will not fix: %(blocked)s.",
        "notification.controller_missing.title": "%(property)s: the guest form is missing your business details.",
        "notification.controller_missing.detail": "Guests must see who looks after their data before they register. Add your business name, address or IČO and email.",
        "notification.apartment_setup.title": "%(property)s: police setup is not finished, so no police report can go out.",
        "notification.sweep_failed.title": "%(property)s: automatic reporting stopped because of an error on our side.",
        "notification.sweep_failed.detail": "Nothing was sent on the last run. We try again every few minutes. If this does not go away, send it from the stay and write to support@ubyhost.com.",
        "notification.guest_pin_locked_out.title": "Your guest link is locked for 24 hours after many wrong PINs.",
        "notification.guest_pin_locked_out.detail": "No guest can register with it until you make a new PIN. Make a new PIN, then put it in your guest message.",
        "hint.failed": "The police did not accept a guest record. Fix the details marked in red below, then send it again.",
        "notification.action.guests": "Fix the guest details",
        "notification.action.police_login": "Check the police login",
        "notification.action.police_setup": "Finish police setup",
        "notification.action.calendar": "Check the calendar",
        "notification.action.business": "Add business details",
        "notification.action.guest_link": "Open guest link settings",
        "stay.detail.guest_refused": "The police did not accept this record. Fix the details, then send it again. Police reason: %(reason)s",
        "stay.detail.guest_blocked": "The police refused this record, and sending it again will not change that. Police reason: %(reason)s",
    },
    "cs": {
        "notification.reason.dates_changed_resign": "Podepsaný formulář uvádí původní termín. Otevřete pobyt a ověřte s hostem nový termín, protože hlášení policii musí odpovídat skutečnému pobytu.",
        "notification.feed_incomplete.title": "%(property)s: z odkazu na kalendář nepřišly skoro žádné rezervace.",
        "notification.reason.feed_incomplete": "Všechny pobyty jsme ponechali, nic se nezrušilo. Před další synchronizací zkontrolujte, že odkaz na kalendář platí.",
        "notification.reason.moved_after_report": "Pobyt se posunul až po odeslání hlášení policii, takže hlášení uvádí původní termín. Ověřte s hosty nový termín a hlášení opravte ve webové aplikaci UbyPort.",
        "notification.reason.submission_stuck": "Policie tyto hosty několikrát odmítla, proto se automatické odesílání zastavilo, aby vám nepřibývaly chyby. Opravte údaje označené červeně a odešlete znovu.",
        "notification.feed_error.title": "Kalendář '%(feed)s' se nepodařilo načíst.",
        "notification.feed_error.detail": "Dokud to neopravíte, nové rezervace z něj se neobjeví. Zkontrolujte odkaz na kalendář. Server kalendáře odpověděl: %(error)s",
        "notification.submission_immediate.title": "%(property)s: hlášení policii se nepodařilo odeslat.",
        "notification.submission_immediate.detail": "Hosté jsou zaregistrovaní, ale policie je zatím nemá. Otevřete pobyt a odešlete znovu. Chyba: %(error)s",
        "notification.submission_transport.title": "%(property)s: policejní systém nebyl dostupný.",
        "notification.submission_transport.detail": "Nic se neodeslalo, policie tyto hosty zatím nemá. Za chvíli odešlete znovu z pobytu. Chyba: %(error)s",
        "notification.ubyport_auth_failed.title": "%(property)s: policie odmítla přihlášení (UBY-WS).",
        "notification.ubyport_auth_failed.detail": "Automatické hlášení je pozastavené, aby se váš policejní účet nezablokoval. Zadejte znovu heslo UBY-WS a stiskněte Uložit a otestovat spojení.",
        "notification.submission_outcome_unknown.title": "%(property)s: nevíme, jestli policie hlášení dostala.",
        "notification.submission_outcome_unknown.detail": "Odpověď nepřišla (%(error)s), proto hlášení sami znovu neodešleme. Zkontrolujte UbyPort. Pokud tam hosté chybí, odešlete znovu z pobytu.",
        "notification.submission_rejected.title": "%(property)s: policie nepřijala %(count)s záznamů hostů.",
        "notification.submission_rejected.detail": "Tito hosté zatím nahlášení nejsou. Opravte na pobytu údaje označené červeně a odešlete znovu. K opravě: %(failed)s. Opětovné odeslání nevyřeší: %(blocked)s.",
        "notification.controller_missing.title": "%(property)s: ve formuláři pro hosty chybí údaje o vaší firmě.",
        "notification.controller_missing.detail": "Hosté musí před registrací vidět, kdo spravuje jejich údaje. Doplňte název firmy, adresu nebo IČO a e-mail.",
        "notification.apartment_setup.title": "%(property)s: nastavení pro policii není hotové, takže se žádné hlášení neodešle.",
        "notification.sweep_failed.title": "%(property)s: automatické hlášení se zastavilo kvůli chybě na naší straně.",
        "notification.sweep_failed.detail": "Při posledním běhu se nic neodeslalo. Zkoušíme to znovu každých pár minut. Pokud to nezmizí, odešlete z pobytu a napište na support@ubyhost.com.",
        "notification.guest_pin_locked_out.title": "Odkaz pro hosty je po mnoha špatných PINech na 24 hodin zamčený.",
        "notification.guest_pin_locked_out.detail": "Dokud nevytvoříte nový PIN, nikdo se přes něj nezaregistruje. Vytvořte nový PIN a vložte ho do zprávy pro hosty.",
        "hint.failed": "Policie nepřijala záznam hosta. Opravte údaje označené červeně níže a odešlete znovu.",
        "notification.action.guests": "Opravit údaje hostů",
        "notification.action.police_login": "Zkontrolovat přihlášení",
        "notification.action.police_setup": "Dokončit nastavení pro policii",
        "notification.action.calendar": "Zkontrolovat kalendář",
        "notification.action.business": "Doplnit údaje o firmě",
        "notification.action.guest_link": "Otevřít nastavení odkazu",
        "stay.detail.guest_refused": "Policie tento záznam nepřijala. Opravte údaje a odešlete znovu. Důvod policie: %(reason)s",
        "stay.detail.guest_blocked": "Policie tento záznam odmítla a opětovné odeslání to nezmění. Důvod policie: %(reason)s",
    },
}
for _lang, _strings in _PLAIN_FIXES_0239_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

Command: `.venv/bin/python -c "from app import host_i18n as h; print(h.STRINGS['cs']['hint.failed'][:20])" 2>&1 | tail -3` → `Policie nepřijala zá`.

### Step 3. `host_vi_i18n.py`: Vietnamese

Append at the very end of the file (after the last `})`):

```python

# 0239 (idea T): plain fixes.
STRINGS.update({
    "notification.reason.dates_changed_resign": "Biểu mẫu đã ký ghi ngày cũ. Mở lượt lưu trú và xác nhận ngày mới với khách, vì khai báo cảnh sát phải khớp với lượt lưu trú thực tế.",
    "notification.feed_incomplete.title": "%(property)s: liên kết lịch gần như không gửi lượt đặt nào.",
    "notification.reason.feed_incomplete": "Chúng tôi giữ nguyên mọi lượt lưu trú, không có lượt nào bị hủy. Hãy kiểm tra liên kết lịch còn đúng trước lần đồng bộ tiếp theo.",
    "notification.reason.moved_after_report": "Lượt lưu trú đã đổi ngày sau khi khai báo cảnh sát được gửi, nên khai báo vẫn ghi ngày cũ. Xác nhận ngày mới với khách, rồi sửa khai báo trong ứng dụng web UbyPort.",
    "notification.reason.submission_stuck": "Cảnh sát đã từ chối những khách này nhiều lần, nên việc gửi tự động đã dừng để hồ sơ của bạn không bị ghi thêm lỗi. Sửa các thông tin đánh dấu đỏ rồi gửi lại.",
    "notification.feed_error.title": "Không đọc được lịch '%(feed)s'.",
    "notification.feed_error.detail": "Lượt đặt mới từ lịch này sẽ không hiện cho đến khi sửa xong. Kiểm tra liên kết lịch. Máy chủ lịch trả lời: %(error)s",
    "notification.submission_immediate.title": "%(property)s: không gửi được khai báo cho cảnh sát.",
    "notification.submission_immediate.detail": "Khách đã đăng ký nhưng cảnh sát chưa nhận được. Mở lượt lưu trú và gửi lại. Lỗi: %(error)s",
    "notification.submission_transport.title": "%(property)s: không kết nối được hệ thống của cảnh sát.",
    "notification.submission_transport.detail": "Chưa có gì được gửi, nên cảnh sát chưa có thông tin những khách này. Lát nữa hãy gửi lại từ lượt lưu trú. Lỗi: %(error)s",
    "notification.ubyport_auth_failed.title": "%(property)s: đăng nhập cảnh sát (UBY-WS) bị từ chối.",
    "notification.ubyport_auth_failed.detail": "Khai báo tự động đã tạm dừng để tài khoản cảnh sát của bạn không bị khóa. Nhập lại mật khẩu UBY-WS rồi bấm Lưu và kiểm tra kết nối.",
    "notification.submission_outcome_unknown.title": "%(property)s: chưa rõ cảnh sát đã nhận khai báo hay chưa.",
    "notification.submission_outcome_unknown.detail": "Không nhận được phản hồi (%(error)s), nên chúng tôi sẽ không tự gửi lại. Hãy kiểm tra trong UbyPort. Nếu thiếu khách ở đó, hãy gửi lại từ lượt lưu trú.",
    "notification.submission_rejected.title": "%(property)s: cảnh sát không chấp nhận %(count)s hồ sơ khách.",
    "notification.submission_rejected.detail": "Những khách này chưa được khai báo. Sửa các thông tin đánh dấu đỏ trên lượt lưu trú rồi gửi lại. Cần sửa: %(failed)s. Gửi lại cũng không khắc phục được: %(blocked)s.",
    "notification.controller_missing.title": "%(property)s: biểu mẫu cho khách thiếu thông tin doanh nghiệp của bạn.",
    "notification.controller_missing.detail": "Khách cần biết ai quản lý dữ liệu của họ trước khi đăng ký. Thêm tên doanh nghiệp, địa chỉ hoặc IČO và email.",
    "notification.apartment_setup.title": "%(property)s: chưa thiết lập xong phần cảnh sát, nên không gửi được khai báo nào.",
    "notification.sweep_failed.title": "%(property)s: khai báo tự động đã dừng do lỗi từ phía chúng tôi.",
    "notification.sweep_failed.detail": "Lần chạy gần nhất không gửi được gì. Chúng tôi thử lại sau vài phút. Nếu thông báo này vẫn còn, hãy gửi từ lượt lưu trú và viết cho support@ubyhost.com.",
    "notification.guest_pin_locked_out.title": "Liên kết cho khách bị khóa 24 giờ sau nhiều lần nhập sai PIN.",
    "notification.guest_pin_locked_out.detail": "Không khách nào đăng ký được cho đến khi bạn tạo PIN mới. Tạo PIN mới rồi đưa vào tin nhắn cho khách.",
    "hint.failed": "Cảnh sát không chấp nhận một hồ sơ khách. Sửa các thông tin đánh dấu đỏ bên dưới rồi gửi lại.",
    "notification.action.guests": "Sửa thông tin khách",
    "notification.action.police_login": "Kiểm tra đăng nhập cảnh sát",
    "notification.action.police_setup": "Hoàn tất thiết lập cảnh sát",
    "notification.action.calendar": "Kiểm tra lịch",
    "notification.action.business": "Thêm thông tin doanh nghiệp",
    "notification.action.guest_link": "Mở cài đặt liên kết cho khách",
    "stay.detail.guest_refused": "Cảnh sát không chấp nhận hồ sơ này. Sửa thông tin rồi gửi lại. Lý do từ cảnh sát: %(reason)s",
    "stay.detail.guest_blocked": "Cảnh sát đã từ chối hồ sơ này và gửi lại cũng không thay đổi được. Lý do từ cảnh sát: %(reason)s",
})
```

Command: `.venv/bin/python -m pytest tests/test_host_i18n.py -q --tb=short 2>&1 | tail -8` → all pass. Commit `0239 steps 1-3`.

### Step 4. `alerts.py`: one exact action per alert

Anchor (exact line): `def present(`

Insert directly BEFORE it:

```python
# 0239 (idea T): the one place each alert sends the host, and its button text.
_ACTIONS = {
    "ubyport_auth_failed": ("notification.action.police_login", "/apartments/{apartment}?view=settings&section=reporting#ubyport"),
    "apartment_setup": ("notification.action.police_setup", "/apartments/{apartment}?view=settings&section=reporting#ubyport"),
    "controller_missing": ("notification.action.business", "/apartments/{apartment}?view=settings&section=property#operator-picker"),
    "feed_error": ("notification.action.calendar", "/apartments/{apartment}?view=bookings#calendars"),
    "feed_incomplete": ("notification.action.calendar", "/apartments/{apartment}?view=bookings#calendars"),
    "feed_duplicate_uid": ("notification.action.calendar", "/apartments/{apartment}?view=bookings#calendars"),
    "feed_recurring_event": ("notification.action.calendar", "/apartments/{apartment}?view=bookings#calendars"),
    "guest_pin_rotated": ("notification.action.guest_link", "/apartments/{apartment}?view=settings&section=guests#communication"),
    "guest_pin_abuse": ("notification.action.guest_link", "/apartments/{apartment}?view=settings&section=guests#communication"),
    "guest_pin_locked_out": ("notification.action.guest_link", "/apartments/{apartment}?view=settings&section=guests#communication"),
    "guest_pin_challenged": ("notification.action.guest_link", "/apartments/{apartment}?view=settings&section=guests#communication"),
    "submission_stuck": ("notification.action.guests", "/reservations/{reservation}#guests"),
}


def action_for(card: Dict[str, Any]) -> Optional[tuple]:
    """(label key, href) for an alert's one button, or None when it has no page."""
    reservation_id = card.get("reservation_id")
    apartment_id = card.get("apartment_id")
    known = _ACTIONS.get(card.get("kind") or "")
    if known:
        key, pattern = known
        if ("{reservation}" not in pattern or reservation_id) and (
            "{apartment}" not in pattern or apartment_id
        ):
            return key, pattern.format(reservation=reservation_id, apartment=apartment_id)
    if reservation_id:
        return "notification.open_stay", f"/reservations/{reservation_id}"
    if apartment_id:
        return "notification.open_property", f"/apartments/{apartment_id}"
    return None


def _with_action(card: Dict[str, Any]) -> Dict[str, Any]:
    action = action_for(card)
    card["action_label_key"], card["action_href"] = action if action else ("", "")
    return card


```

Then, inside `def present(`, anchor (exact two lines):

```python
    if kind in _COMPUTED_ALERT_KINDS:
        return _present_computed(row, kind, lang, stays)
    return _present_stored(row, kind, lang)
```

Replace with:

```python
    if kind in _COMPUTED_ALERT_KINDS:
        return _with_action(_present_computed(row, kind, lang, stays))
    return _with_action(_present_stored(row, kind, lang))
```

Command: `.venv/bin/python -c "from app import alerts; print(alerts.action_for({'kind':'feed_error','apartment_id':3}))" 2>&1 | tail -3` → `('notification.action.calendar', '/apartments/3?view=bookings#calendars')`. Commit `0239 step 4`.

### Step 5. `_host_alerts.html`: use the action

Replace the whole block from the anchor line `      {% if alert.reservation_id %}` (the FIRST occurrence, right after the `<article ...>` line) down to and including the line `      {% if alert.reservation_id or alert.apartment_id %}</a>{% else %}</div>{% endif %}` with exactly:

```jinja
      {% set action_href = '/apartments' if grouped else alert.action_href %}
      {% set action_label = t('dashboard.setup.view_properties') if grouped else (t(alert.action_label_key) if alert.action_label_key else '') %}
      {% if action_href %}
        <a class="notification-link" href="{{ action_href }}">
      {% else %}
        <div class="notification-link">
      {% endif %}
          <span class="notification-icon" aria-hidden="true">!</span>
          <span class="grow">
            <strong>{{ alert.display_title or alert.message }}</strong>
            {% if grouped %}<small>{{ pin_names | join(', ') }}. {{ alert.display_detail or alert.detail }}</small>
            {% elif alert.display_detail or alert.detail %}<small>{{ alert.display_detail or alert.detail }}</small>{% endif %}
            {% if action_label %}<small class="notification-action">{{ action_label }}</small>{% endif %}
          </span>
      {% if action_href %}</a>{% else %}</div>{% endif %}
```

Check with `grep -c "notification-link" app/templates/_host_alerts.html` → 2. Commit `0239 step 5`.

### Step 6. `reservation_detail.html`: the refused-record sentence

Anchor (exact three lines):

```jinja
      {% if guest.last_errors %}
        <p class="guest-card-note err-text">{{ guest.last_errors }}</p>
      {% endif %}
```

Replace with:

```jinja
      {% if guest.last_errors %}
        <p class="guest-card-note err-text">{% if guest.submit_state == 'blocked' %}{{ t('stay.detail.guest_blocked', reason=guest.last_errors) }}{% elif guest.submit_state == 'error' %}{{ t('stay.detail.guest_refused', reason=guest.last_errors) }}{% else %}{{ guest.last_errors }}{% endif %}</p>
      {% endif %}
```

Commit `0239 step 6`.

### Step 7. Create `App/tests/test_plain_fixes_0239.py` with exactly this content

```python
"""0239 (idea T): plain copy and one exact button per alert."""

from __future__ import annotations

import re

from app import alerts, host_i18n

KEYS = (
    "notification.ubyport_auth_failed.detail",
    "notification.submission_rejected.detail",
    "notification.feed_error.detail",
    "notification.action.police_login",
    "stay.detail.guest_refused",
    "hint.failed",
)


def test_every_language_has_the_new_copy_with_the_same_placeholders():
    for key in KEYS:
        en = host_i18n.STRINGS["en"][key]
        for lang in ("cs", "vi"):
            other = host_i18n.STRINGS[lang][key]
            assert other and other != en, (lang, key)
            assert sorted(re.findall(r"%\((\w+)\)s", other)) == sorted(re.findall(r"%\((\w+)\)s", en)), (lang, key)


def test_no_em_dash_and_no_system_name_in_the_first_sentence():
    for lang in ("en", "cs", "vi"):
        for key in KEYS:
            assert "—" not in host_i18n.STRINGS[lang][key]
    assert "UbyPort" not in host_i18n.STRINGS["en"]["hint.failed"]


def test_actions_land_on_the_exact_place():
    assert alerts.action_for({"kind": "ubyport_auth_failed", "apartment_id": 4}) == (
        "notification.action.police_login", "/apartments/4?view=settings&section=reporting#ubyport")
    assert alerts.action_for({"kind": "submission_stuck", "reservation_id": 9, "apartment_id": 4}) == (
        "notification.action.guests", "/reservations/9#guests")
    assert alerts.action_for({"kind": "deadline", "reservation_id": 9}) == ("notification.open_stay", "/reservations/9")
    assert alerts.action_for({"kind": "feed_error"}) is None
    assert alerts.action_for({"kind": "job_failed"}) is None


def test_present_attaches_the_action():
    card = alerts.present({"kind": "controller_missing", "apartment_id": 2, "message": "m", "detail": "d",
                           "params": '{"property": "Loft"}', "level": "warning"}, "en")
    assert card["action_href"] == "/apartments/2?view=settings&section=property#operator-picker"
    assert card["display_title"] == "Loft: the guest form is missing your business details."
```

Command: `.venv/bin/python -m pytest tests/test_plain_fixes_0239.py -q --tb=short -x 2>&1 | tail -15` → 4 passed. If `present()` needs a column the dict lacks (KeyError), add that key with value `None` to the test dict only. Commit `0239 step 7`.

### Step 8. Update tests that pin the old wording

Run: `.venv/bin/python -m pytest tests/test_notification_copy.py tests/test_alert_language.py tests/test_send_controls.py tests/test_host_guest_form.py tests/test_alert_stack.py tests/test_mail_failed_alert.py -q --tb=line 2>&1 | tail -30`

For each failure: if the assertion compares a rendered or translated string to the OLD text of a key from step 1, replace the old text in the test with the NEW text of the same key and language from steps 2 or 3 (copy it exactly). If an assertion checks that a card links to `/apartments/<id>` or `/reservations/<id>` and the kind is in `_ACTIONS`, change the expected href to the `_ACTIONS` one. Change nothing else in those tests. A failure of any other kind: STOP and report it. Rerun until green. Commit `0239 step 8`.

## 5. Do not touch

Everything outside §3. Never change what `raise_alert()` stores (English log copy), `ubyport/`, `reporting.py` or any classification of errors (hard rule 1).

## 6. Commands

1. `.venv/bin/python -m pytest tests/test_plain_fixes_0239.py tests/test_notification_copy.py tests/test_alert_language.py tests/test_send_controls.py tests/test_host_guest_form.py tests/test_alert_stack.py tests/test_mail_failed_alert.py tests/test_host_i18n.py tests/test_design_lint.py -q --tb=short 2>&1 | tail -15`
2. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -5`

## 7. Acceptance

- [ ] Step 1 printed 50 and 25.
- [ ] All tests in §6 pass.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found; a test fails twice; you reach 25 tool calls; a file outside §3 needs a change; a step is unclear.

## 9. Report

Write `docs/tasks/0239-report.md` (600 tokens at most) and set `Status: review`. Do not push or open a PR.

## Risk list (for the reviewer)

`App/app/alerts.py`, `App/app/templates/_host_alerts.html` (every host page), the test edits in step 8.

## Owner steps

None.
