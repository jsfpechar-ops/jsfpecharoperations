# 0136: Remove the host ID check (Mark ID checked) and its unused texts

Status: todo
Depends on: 0135 | Base commit: df8b842 | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
HIGH RISK (filing-adjacent): exact diff only; the reviewer reads the full diff of every file below.

Owner-confirmed set (2026-10-19): legacy actions items 1 and 2. Part of [design-v2](../plans/design-v2.md). Commit each step as `0136 step k`. Never push, never open a PR.

## 1. Objective

Remove the "Mark ID checked" button, the amber "ID not checked" guest badge and the "ID checked on" panel from the stay detail and the guest edit page, and delete the host texts no page uses any more. Passport photos then go only by the existing limits in `purge_stale` (7 days after check-in, 30 days after upload). Nothing about filing changes: the `awaiting_verification` reporting status, `identity_verified_at`, `reporting.record_host_identity_confirmation`, the `/guests/{id}/verify-identity` route and the passport-photo preview stay exactly as they are.

## 2. Context

The ID gate was dropped in PR #331 (known issue K-F12): an unchecked stay sends. `docs/UBYPORT_CORE.md` lists the status machine, auto-submit and the "filed by hand" mark as one system with UbyPort; `app/reporting.py` still computes `awaiting_verification` (lines 443, 646, 698) and the worker treats it as sendable, so this brief does not touch `reporting.py`, `routes/admin.py` or the database. Hosts still check documents themselves (legacy list, Keep); only UbyHost's record of that check loses its button.

Anchors are the text after 0135 (verify each with `grep -n`; if one is not found verbatim, stop).

Anchor A, `App/app/templates/reservation_detail.html` (guest badge branch, two lines):

```
          {% elif row.needs_verification %}
            <span class="ui-badge ui-badge-action" data-tone="amber">{{ t('host.verify_pending') }}</span>
```

Anchor B, same file (nine lines):

```
      {% if row.needs_verification %}
        <form method="post" action="/guests/{{ guest.id }}/verify-identity" class="verify-form guest-card-action">
          <input type="hidden" name="return_to" value="/reservations/{{ reservation.id }}">
          <button class="ui-btn ui-btn-secondary ui-btn-compact" type="submit">{{ t('host.verify_button') }}</button>
          {% if row.has_passport_photo %}
            <a class="ui-sub" href="/guests/{{ guest.id }}?return_to=/reservations/{{ reservation.id }}">{{ t('host.verify_view_photo') }}</a>
          {% endif %}
        </form>
      {% endif %}
```

Anchor C, `App/app/templates/guest_form_admin.html` lines 230 to 246 (not yet migrated, so still v1 classes):

```
    <p class="small muted" style="margin:0 0 10px">{{ t('host.verify_in_person') }}</p>
    {# The form element itself renders after the main form, further down: a <form>
       nested inside another one closes the outer form early, which killed Save. #}
    <div class="verify-form">
      <button class="btn small" type="submit" form="verify-{{ guest.id }}">{{ t('host.verify_button') }}</button>
    </div>
  </div>
  {% elif editing and guest.identity_verified_at and guest.nationality != 'CZE' %}
  <div class="panel quiet">
    <p class="small muted" style="margin:0">{{ t('host.verify_done') }}
      {{ guest.identity_verified_at | datetime_local }}.</p>
  </div>
  {% elif not editing %}
  <div class="panel quiet">
    <p class="small muted" style="margin:0">{{ t('host.verify_host_entry') }}</p>
  </div>
  {% endif %}
```

Anchor D, same file, lines 306 to 310:

```
{% if editing and needs_verification %}
<form id="verify-{{ guest.id }}" method="post" action="/guests/{{ guest.id }}/verify-identity">
  <input type="hidden" name="_csrf" value="{{ csrf_token }}">
  <input type="hidden" name="return_to" value="/guests/{{ guest.id }}?return_to=/reservations/{{ reservation.id }}">
</form>
{% endif %}
```

Anchor E, `App/tests/test_status_colours.py` lines 226 to 233:

```
def test_the_guest_card_keeps_its_amber_id_not_checked_pill(host):
    """The guest-card pill is a per-person to-do, so amber stays there."""
    client, _, reservation_id = host
    page = client.get(f"/reservations/{reservation_id}")
    assert page.status_code == 200
    tone, _tip = _pill(page.text, host_i18n.translate("en", "host.verify_pending"))
    assert tone == "amber"
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/reservation_detail.html` | edit | Anchors A and B removed |
| `App/app/templates/guest_form_admin.html` | edit | Anchors C and D; keeps the passport preview |
| `App/app/host_i18n.py` | edit | delete the unused host.verify_*, hint.need_verification, stay.detail.cta.verify, stay.detail.guests.verify texts (en and cs); shorten guest.admin.passport_pdf_hint |
| `App/app/passport_photos.py` | edit | comments only: the button no longer exists |
| `App/tests/test_status_colours.py` | edit | Anchor E |
| `App/tests/test_host_guest_form.py` | edit | lines 234 and 260 to 262: the verify form is gone |
| `App/tests/test_remove_id_check.py` | create | the button, badge and texts are gone; the route and status still exist |

No other file may change. `reporting.py`, `routes/admin.py`, `db.py`, migrations: never.

## 4. Steps

1. In `reservation_detail.html` delete Anchor A (two lines) and Anchor B (nine lines). Command: `grep -c 'verify-identity\|host.verify_' App/app/templates/reservation_detail.html`. Expected: `0`.

2. In `guest_form_admin.html` replace Anchor C with:

```
  </div>
  {% endif %}
```

   and delete Anchor D (six lines). The surrounding `{% if editing and needs_verification %}<div class="panel verify-panel tight">` with the passport preview stays. Command: `grep -c 'verify-identity\|host.verify_' App/app/templates/guest_form_admin.html`. Expected: `0`. Then `cd App && .venv/bin/python -c "from app.templating import templates; templates.env.get_template('guest_form_admin.html'); templates.env.get_template('reservation_detail.html'); print('compiled')"`. Expected: `compiled`.

3. In `App/app/host_i18n.py`, run from `App/`:

```
.venv/bin/python - <<'EOF'
import pathlib, re
p = pathlib.Path("app/host_i18n.py"); s = p.read_text(encoding="utf-8")
# whole-line keys, en and cs: each must appear exactly twice
for key in ("host.verify_title", "host.verify_help", "host.verify_confirm", "host.verify_button",
            "host.verify_pending", "host.verify_view_photo", "host.verify_footnote",
            "host.verify_waiting_photo", "host.verify_done", "hint.need_verification",
            "stay.detail.cta.verify", "stay.detail.guests.verify"):
    pat = re.compile(r'^        "' + re.escape(key) + r'": .*\n', re.M)
    assert len(pat.findall(s)) == 2, (key, len(pat.findall(s))); s = pat.sub("", s)
# the two multi-line tuples, en and cs
for key in ("host.verify_in_person", "host.verify_host_entry"):
    pat = re.compile(r'^        "' + re.escape(key) + r'": \(\n(?:            .*\n)+?        \),\n', re.M)
    assert len(pat.findall(s)) == 2, (key, len(pat.findall(s))); s = pat.sub("", s)
old_en = "Compare it with the form, then confirm below."; old_cs = "Porovnejte ho s formulářem a pak níže potvrďte."
assert s.count(old_en) == 1 and s.count(old_cs) == 1
s = s.replace(old_en, "Compare it with the form.").replace(old_cs, "Porovnejte ho s formulářem.")
p.write_text(s, encoding="utf-8"); print("ok")
EOF
```

   Expected: `ok`. Command: `cd App && .venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -5`. Expected: passed.

4. In `App/app/passport_photos.py` make these three comment edits (no code line changes):
   - lines 4 to 11: replace `Files stay on disk only until the host confirms the data matches the\ndocument, then are deleted immediately. Only authenticated hosts can read them\nvia the admin route. Unverified files go 7 days after check-in, and no file\nlives longer than 30 days after upload (see ``purge_stale``).\n\nVerification is the happy path, not a guarantee: a host can simply never press\nthe button. ``purge_stale`` is the backstop that makes the promise true, and it\nalso clears files no guest row points at any more, which nothing else can reach.` with `Files stay on disk only until they have no purpose left. Only authenticated\nhosts can read them via the admin route. A file goes 7 days after check-in and\nnever lives longer than 30 days after upload (see ``purge_stale``). 0136 removed\nthe host's "Mark ID checked" button, so these two limits are the whole rule;\n``purge_stale`` also clears files no guest row points at any more.`
   - lines 221 to 223: replace `# retention decision (legal positions, section 4) is: delete it when the host\n# marks the guest verified, otherwise 7 days after check-in, and never later\n# than 30 days after upload, whatever the stay dates say.` with `# retention decision (legal positions, section 4) is: 7 days after check-in, and\n# never later than 30 days after upload, whatever the stay dates say. A row that\n# still carries identity_verified_at (hand-entered guests) also qualifies.`
   - lines 273 to 274: replace `verified (the Verify route deletes at once; this catches every other path\n    that sets ``identity_verified_at``), check-in was more than 7 days ago, or` with `verified (hand-entered guests set ``identity_verified_at`` on save; no button\n    does any more), check-in was more than 7 days ago, or`

   Command: `cd App && .venv/bin/python -m pytest tests/test_retention.py tests/test_passport_photo*.py -q --tb=short -x 2>&1 | tail -5`. Expected: passed (behaviour unchanged).

5. Tests. Replace Anchor E with:

```python
def test_the_guest_card_reads_ready_now_that_the_id_check_is_gone(host):
    """0136: no "Mark ID checked" button, no amber "ID not checked" badge; a complete guest reads Ready."""
    client, _, reservation_id = host
    page = client.get(f"/reservations/{reservation_id}")
    assert page.status_code == 200
    assert "ID not checked" not in page.text and "verify-identity" not in page.text
    tone, _tip = _pill(page.text, "Ready")
    assert tone == "blue"
```

   In `App/tests/test_host_guest_form.py` rename `test_the_verify_identity_form_is_not_nested_in_the_guest_form` (line 234) to `test_the_guest_form_has_no_nested_form_and_no_verify_form`, and replace the last three lines of its `try` block
   `        # The verify button still submits, through the form attribute.\n        assert f'<form id="verify-{guest_id}"' in html\n        assert f'form="verify-{guest_id}"' in nested`
   with `        # 0136: the ID check button and its form are gone.\n        assert "verify-identity" not in html`.

   Create `App/tests/test_remove_id_check.py`:

```python
"""0136: the host ID check lost its button and texts; filing code did not move."""
from __future__ import annotations

import inspect
import re
from pathlib import Path

from app import host_i18n, passport_photos, reporting
from app.routes import admin

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"


def test_no_template_offers_the_id_check():
    for name in ("reservation_detail.html", "guest_form_admin.html"):
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        assert "verify-identity" not in text and "host.verify_" not in text, name


def test_the_unused_verify_texts_are_gone_in_both_languages():
    for lang in ("en", "cs"):
        keys = host_i18n.STRINGS[lang]
        assert not [k for k in keys if k.startswith("host.verify_")]
        for key in ("hint.need_verification", "stay.detail.cta.verify", "stay.detail.guests.verify"):
            assert key not in keys, (lang, key)
        assert "status.awaiting_verification" in keys  # the reporting status stays


def test_filing_code_kept_the_status_and_the_route():
    assert "awaiting_verification" in reporting.HOST_ACTION_STATUSES
    assert callable(reporting.record_host_identity_confirmation)
    assert "verify-identity" in inspect.getsource(admin)
    source = inspect.getsource(passport_photos.purge_stale)
    assert "identity_verified_at IS NOT NULL" in source and passport_photos.PHOTO_AFTER_CHECKIN_DAYS == 7
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_remove_id_check.py tests/test_status_colours.py tests/test_host_guest_form.py tests/test_send_controls.py tests/test_endtoend.py tests/test_wp28_ui_sweep.py tests/test_wp28_geometry.py tests/test_design_stay_detail.py tests/test_design_lint.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed. Then the filing row: `cd App && .venv/bin/python -m pytest tests/test_ubyport_*.py tests/test_worker.py tests/test_submission_*.py tests/test_filed_by_hand.py tests/test_duplicate_guard.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed.

6. Browser: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-shots .venv/bin/python -m pytest tests/test_host_stay_detail_layout_browser.py tests/test_host_geometry.py -q --tb=short 2>&1 | tail -30`. Expected: passed, 0 skipped. Attach a guest edit page at 390 and 1280 (`guest-edit-390.png`, `guest-edit-1280.png`).

7. Commit: `git add App/app/templates/reservation_detail.html App/app/templates/guest_form_admin.html App/app/host_i18n.py App/app/passport_photos.py App/tests && git commit -m "0136 step 7: remove the host ID check button, badge and unused texts"`.

## 5. Do not touch

`app/reporting.py`, `app/routes/admin.py` (the route stays), `app/db.py`, `app/migrations/`, `app/ubyport/`, `passport_photos.py` code lines, the guest pages, `_components.html`; hard rules 1, 2, 3, 8.

## 6. Commands

- Step 5 commands (both rows) and step 6, 0 skipped.
- `python3 scripts/design_lint.py` expected: OK.

## 7. Acceptance

- [ ] No "Mark ID checked" button or "ID not checked" badge on the stay detail; no check panel on the guest edit page; the passport preview still shows.
- [ ] `grep -rn 'host.verify_' App/app` prints nothing; en and cs have the same keys.
- [ ] Filing tests pass unchanged; `reporting.py` and `routes/admin.py` have no diff.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found verbatim; a count in step 3 differs; a filing test fails once; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0136-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left. State explicitly: "filing behaviour unchanged; reporting.py and routes/admin.py untouched".

## Risk list (for the reviewer)

`App/app/templates/reservation_detail.html`, `App/app/templates/guest_form_admin.html` (guest card and edit page, hard rule 1 adjacency), `App/app/host_i18n.py` (deleted keys).

## Owner steps

None (set confirmed 2026-10-19).
