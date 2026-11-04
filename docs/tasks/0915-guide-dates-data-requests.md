# 0915: Help guide matches the app, dates in dd.mm.yyyy, Data requests "Received" as a date

Status: todo. Source: UX review 2026-11-04 (the Content table: help guide, dates, data requests). Owner decision: no language switcher in the app; the guide stops mentioning one. Czech-term glossing and Havel answer length are out of scope. Executor: Haiku 5.5, one run. Run after 0914 (and 0911, whose "Contact support" label the guide quotes).
Read first: AGENTS.md, docs/context/executor.md, this brief. The privacy row of the routing table applies to step 4: docs/privacy/RETENTION.md, data-requests section only.

## 0. Before you start
Branch from a fresh `origin/main`. No guest, public or Payments template. Copy rule 9: one explanation in one place, no sentence the button already says.

## 1. Objective
- The guide describes the real "?" help button and the real menus, with Payments and Havel, and no language buttons.
- Guide search opens only the sections whose heading matches.
- Host pages show dates as dd.mm.yyyy.
- The data-request "Received" field is a date picker and is shown as a date.

## 2. Context (verified 2026-11-04)
- The guide strings are `GUIDE_STRINGS` in `App/app/guide_i18n.py`: en from line 8, cs from 388. vi at line 774 is `{key: _VI.get(key, en)}`, with `_VI` from `host_vi_i18n.py`, so vi guide text lives in `host_vi_i18n.py` (for example `guide.nav.finding` at ~2765).
- Keys to fix (en line, cs line). Find the vi lines with `grep -n "<key>" App/app/host_vi_i18n.py`.
  - `guide.finding.how` (365, ~743): says "How does this work? under the title". Pages show a "?" button.
  - `guide.finding.phone2` (356, 734): mentions "language buttons (EN, CS, VI)".
  - `guide.finding.computer1` (359, ~737): the menu list lacks Payments. The real order is in `_shell_sidebar.html` 13-19: Dashboard, Stays, Properties, Stay fees, Cleaning, Payments.
  - `guide.finding.computer2` (360, ~738): mentions "Help & support" and "the language buttons".
- Guide sections: `templates/guide.html:11` `{% set sections = [...] %}`. Each section is a `<details class="guide-section ... guide-topic" id="...">`. The template has `havel_on` (line 12).
- Guide search: `static/guide.js` `applySearch` at ~43-60 opens every topic whose text contains the query.
- Data requests: `templates/privacy_requests.html:16-17` `<input id="received_at" name="received_at" placeholder="2026-01-01T00:00:00+00:00">`. Display at line 46: `{{ row.received_at }}`. Route: `routes/privacy_requests.py:55` `received_at=_form_str(form, "received_at") or db.utcnow()`.
- Date filters: `date_cz` (`templating.py:438`, dd.mm.yyyy), `date_short` (`:439`, gives "03.11"), `datetime_local` (`:444`).

## 3. Files
`guide_i18n.py`, `host_vi_i18n.py`, `templates/guide.html`, `static/guide.js` (+ cache key), `templates/privacy_requests.html`, `routes/privacy_requests.py`, the host templates found in step 5 (excluding guest, public, `payments*`, and files 0910 to 0914 already changed for other reasons, which are fine to touch only for a date filter), tests.

## 4. Steps
1. **Guide copy.**
   - `guide.finding.how`: en "Many pages have a ? button next to the title. Tap or click it for a short explanation and a link back here." cs "Mnoho stránek má vedle názvu tlačítko ?. Klepnutím nebo kliknutím zobrazíte krátké vysvětlení a odkaz zpět sem." vi "Nhiều trang có nút ? bên cạnh tiêu đề. Chạm hoặc nhấp vào đó để xem giải thích ngắn và liên kết quay lại đây."
   - `guide.finding.phone2`: delete only the language-button sentence part. en: "... Archive and Data requests. Log out is in the same list. Tap Close to go back." Make the same cut in cs ("Ve stejném seznamu je Odhlásit se.") and vi.
   - `guide.finding.computer1`: en "The menu on the left has Search, Dashboard, Stays, Properties, Stay fees, Cleaning, Payments and Settings. Help is at the bottom of the menu." Do the same in cs ("Platby") and vi, using `nav.payments` from each locale.
   - `guide.finding.computer2`: en "Click your name at the bottom of the menu to open the account menu. It has Settings, Contact support (the e-mail address of UbyHost support), Archive, Data requests, Keyboard shortcuts and Log out." cs/vi: the same cut, with the 0911 label ("Kontaktovat podporu", "Liên hệ hỗ trợ").
   - Run `grep -n "EN, CS\|EN / CS\|language button\|tlačítka jazyka" App/app/guide_i18n.py App/app/host_vi_i18n.py`. Any other hit inside a host guide key gets the same cut. Report hits in guest keys and leave them.
2. **Payments and Havel sections.** In `guide.html:11`, add `'payments'` after `'invoices'`, and append `+ (['havel'] if havel_on else [])` before the demo part. Add two `<details class="guide-section card ui-section ui-section-plain guide-topic" id="payments">` / `id="havel"` blocks, copying the markup of the `invoices` section (line ~214). Put them in the same order as the list. The Havel block goes inside `{% if havel_on %}`. New keys:
   - en `guide.nav.payments` "Payments", `guide.payments.body` "Payments lists the payment requests you sent to guests and whether each is paid. To ask for a payment, open a stay and choose Request payment."
   - en `guide.nav.havel` "Havel (AI)", `guide.havel.body` "Havel answers questions about UbyHost. Pick a topic or type your question. Check anything about filing deadlines against this guide."
   - cs: "Platby" / "V Platbách vidíte žádosti o platbu, které jste poslali hostům, a zda jsou zaplacené. Platbu vyžádáte na detailu pobytu volbou Vyžádat platbu." and "Havel (AI)" / "Havel odpovídá na otázky o UbyHost. Vyberte téma nebo napište otázku. Termíny hlášení si ověřte v této nápovědě."
   - vi (`host_vi_i18n.py`): "Thanh toán" / "Mục Thanh toán liệt kê các yêu cầu thanh toán bạn đã gửi cho khách và trạng thái đã trả hay chưa. Để yêu cầu thanh toán, mở một lưu trú và chọn Yêu cầu thanh toán." and "Havel (AI)" / "Havel trả lời các câu hỏi về UbyHost. Chọn một chủ đề hoặc nhập câu hỏi. Hãy kiểm tra thời hạn khai báo trong hướng dẫn này."
   - Check the real button label first: `grep -n "\"stays.row.request_payment\"" App/app/host_i18n.py App/app/host_vi_i18n.py`. Use its exact cs and vi text in place of "Vyžádat platbu" / "Yêu cầu thanh toán" if they differ.
3. **Guide search opens only heading matches.** In `applySearch`, keep `topic.hidden = !match`. Replace `topic.open = match` with `topic.open = match && fold((topic.querySelector("summary") || topic).textContent).indexOf(q) !== -1;`. After the loop, if no shown topic is open, open the first shown one. Bump `guide.js`'s `?v=`.
4. **Received as a date.** In `privacy_requests.html:17`, use `<input type="date" id="received_at" name="received_at" value="">` with no ISO placeholder. On line 46, use `{{ row.received_at | date_cz }}`. First check that `_fmt_date` (`grep -n "def _fmt_date" -A8 App/app/templating.py`) accepts a full ISO timestamp string; if it does not, slice `row.received_at[:10]` before the filter. In `routes/privacy_requests.py:55`, when the value matches `^\d{4}-\d{2}-\d{2}$`, store `value + "T00:00:00+00:00"` so deadline maths still gets an aware timestamp. An empty value keeps `db.utcnow()`.
5. **Dates dd.mm.yyyy.**
   - Run `grep -rnE "\{\{ *[a-z_]+\.(date_from|date_to|check_in|check_out|created_at|received_at|period_start|period_end) *\}\}" App/app/templates/*.html | grep -v "guest_\|property_page\|public\|payments\|landing\|legal\|login\|signup" | head -40`.
   - Each hit that prints a date-only value gets `| date_cz`, and each timestamp gets `| datetime_local`. Exclude `value="..."` attributes of `<input type="date">` and `href`/`data-*` attributes (those must stay ISO).
   - Then `grep -rn "date_short" App/app/templates/*.html`: replace `date_short` with `date_cz` except inside calendar day cells and bars (`_dashboard_calendar.html`, `_cleaning_*.html`), where space is the reason. List the kept ones in the report.
   - Do not edit `dashboard.html` or `_components.html`. Report hits there for a follow-up.

## 5. Do not touch
Guest and public templates and guide pages for guests (`guest_guide*.html`, `public_guide.html`), `payments*.html`, `routes/payments.py`, `dashboard.html`, `_components.html`, `base.html`.

## 6. Commands (from `App/`, `2>&1 | tail -30`)
- `.venv/bin/python -m pytest tests/test_guide*.py tests/test_ai*.py tests/test_havel*.py tests/test_retention*.py tests/test_privacy_*.py tests/test_dsr_audit.py tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py tests/test_static_versions.py -q --tb=short -x -rs`, 0 skipped.
- Copy row: `test_*_i18n.py test_no_em_dashes.py test_copy_cleanup.py test_flash_literals.py`.
- New `tests/test_0915_guide_dates.py`:
  - the guide HTML has no "EN, CS" and has `id="payments"`;
  - posting a data request with `received_at=2026-11-01` stores `2026-11-01T00:00:00+00:00` and lists "01.11.2026".
- UX gate: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x -rs`, 0 skipped. Open the 390/768/1280 shots of Help, Data requests and each page whose date you changed. PR body: per page "390: ...; 768: ...; 1280: ...".
- `python3 scripts/context_lint.py`.

## 7. Acceptance
- [ ] The guide mentions no language buttons, describes the "?" button, and lists Payments in the menu and contents (Havel when enabled).
- [ ] Searching "police" in the guide opens only sections with "police" in the heading (others matching in body stay closed but listed).
- [ ] No host page shows `YYYY-MM-DD` or a timestamp in text, except where the report lists a reason.
- [ ] "Received" is a date picker and lists as dd.mm.yyyy.
- [ ] No new dependency, light mode only.

## 8. Stop and ask
`_fmt_date` cannot take the stored value; a date in a host page comes from JS, not a template (report it and leave it); a privacy test expects the raw ISO text.

## 9. Report
`docs/tasks/0915-report.md` with the list of date hits changed and kept, and the 390 px shots.
