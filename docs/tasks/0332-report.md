# 0332 report: "You can ask next" buttons

Status: review

**Files:** routes/havel.py (`"next": []` default in `_item`, `next=reply.next` on the reply item), templates/_havel_thread.html (next form after the links block), static/havel.js (remove old blocks in `swap`; tap handler before the composer handler), static/host2.css (`.havel-next`, appended), templates/base.html (havel.js 0332b, host2.css 0332), host_i18n.py and host_vi_i18n.py (`havel.next_title`), docs/design/catalog.json (`havel-next`), tests/static_versions.json (--write), tests/test_havel_page.py (one unit test), tests/test_havel_browser.py (one test at 390), docs/tasks/screenshots-0332/next-390.png.

**Commands (last lines):**
- required set (test_havel*, design_dashboard, stay_fee_detail, static_versions, design_guardrails_browser, a11y_guard_browser): `103 passed`, 0 skipped
- targeted (test_havel_page, test_havel_browser, test_host_i18n, test_static_versions): `28 passed`
- `design_lint.py`: OK; `context_lint.py`: OK
- i18n: `You can ask next: | Můžete se dál zeptat: | Bạn có thể hỏi tiếp:`

**Section 7:** all four ticked (no-JS path covered by the unit test posting the mini-form fields).

**Screenshot (390 px):** the newest Havel bubble holds the answer, then "You can ask next:" and two secondary buttons ("Sync my calendars", "What does the red badge mean?") stacked left-aligned within the width; no horizontal scroll. The red outline around the bubble is the focus ring on the newly added reply, not part of the new block.
