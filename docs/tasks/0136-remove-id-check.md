# 0136: Remove the host ID check (Mark ID checked) and its unused texts

Status: todo
Depends on: 0135 | Base commit: 5b10d6a (refreshed 2026-10-19 against 0133 to 0150; every anchor re-verified) | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
HIGH RISK (filing-adjacent): exact diff only; the reviewer reads the full diff of every file below.

Owner-confirmed set (2026-10-19): legacy actions items 1 and 2. Part of [design-v2](../plans/design-v2.md). Commit each step as `0136 step k`. Never push, never open a PR.

## 1. Objective

Remove the "Mark ID checked" button, the amber "ID not checked" guest badge and the "ID checked on" panel from the stay detail and the guest edit page, and delete the host texts no page uses any more. Passport photos then go only by the existing limits in `purge_stale` (7 days after check-in, 30 days after upload). Nothing about filing changes: the `awaiting_verification` reporting status, `identity_verified_at`, `reporting.record_host_identity_confirmation`, the `/guests/{id}/verify-identity` route and the passport-photo preview stay exactly as they are.

## 2. Context

The ID gate was dropped in PR #331 (known issue K-F12): an unchecked stay sends. `docs/UBYPORT_CORE.md` lists the status machine, auto-submit and the "filed by hand" mark as one system with UbyPort; `app/reporting.py` still computes `awaiting_verification` and the worker treats it as sendable, so this brief does not touch `reporting.py`, `routes/admin.py` or the database. Hosts still check documents themselves (legacy list, Keep); only UbyHost's record of that check loses its button. The stay pill's tip `status.awaiting_verification_tip` ("ID not checked (optional)") is a reporting-status text and stays (orchestrator may reword it later; not here).

Settled rules for every v2 brief: one DOM (MASTER 7.4), card roles via `data-card` (7.3); never `class=` inside a ui macro's `attrs` (use `extra_class`); v2 controls 40 px at 768+ and 44 below; a hook or text the old page rendered and the new page lacks is a regression unless this brief removes it on purpose (listed in section 1); tests that read old markup are updated to v2 markup, keeping what they assert, never skipped or weakened; no raw colours or bare px in CSS (no CSS in this brief); "Clear demo data" stays.

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

Anchor C, `App/app/templates/guest_form_admin.html` lines 230 to 246 (not yet migrated, so still v1 classes; the quoted `style=` is old code being deleted):

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

Line 213 of the same file, `  {% if editing and needs_verification %}` (the passport-preview panel opener), is the only other copy of that condition once Anchor D is gone.

Anchor E, `App/tests/test_status_colours.py` lines 230 to 237:

```
def test_the_guest_card_keeps_its_amber_id_not_checked_pill(host):
    """The guest-card pill is a per-person to-do, so amber stays there."""
    client, _, reservation_id = host
    page = client.get(f"/reservations/{reservation_id}")
    assert page.status_code == 200
    tone, _tip = _pill(page.text, host_i18n.translate("en", "host.verify_pending"))
    assert tone == "amber"
```

Anchor F, `App/tests/test_wp28_geometry.py` (after 0135): the line `              const out = {placeholders: [], verify: null, filing: null};`, the five-line block from `              const verify = document.querySelector('.guest-card .verify-form .ui-btn');` to its closing `              }`, and the two lines `    if measured["verify"] is not None:` / `        assert measured["verify"] >= 8, f"Mark ID checked touches the card edge: {measured}"`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/reservation_detail.html` | edit | Anchors A and B removed |
| `App/app/templates/guest_form_admin.html` | edit | Anchors C and D; the preview panel opens only with a photo |
| `App/app/host_i18n.py` | edit | delete the unused host.verify_*, hint.need_verification, stay.detail.cta.verify, stay.detail.guests.verify texts (en and cs); shorten guest.admin.passport_pdf_hint |
| `App/app/passport_photos.py` | edit | comments only: the button no longer exists |
| `App/tests/test_status_colours.py` | edit | Anchor E |
| `App/tests/test_host_guest_form.py` | edit | lines 234 and 260 to 262: the verify form is gone |
| `App/tests/test_wp28_geometry.py` | edit | Anchor F: the measurement of a button that no longer exists |
| `App/tests/test_remove_id_check.py` | create | the button, badge and texts are gone; the route and status still exist |

No other file may change. `reporting.py`, `routes/admin.py`, `db.py`, migrations: never.

## 4. Steps

1. Templates, run from `App/` (one script; each anchor must occur exactly once):

```
.venv/bin/python - <<'EOF'
import pathlib
def patch(name, pairs):
    p = pathlib.Path("app/templates/" + name); s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, (name, old[:70], s.count(old)); s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")
A = """          {% elif row.needs_verification %}
            <span class="ui-badge ui-badge-action" data-tone="amber">{{ t('host.verify_pending') }}</span>
"""
B = """      {% if row.needs_verification %}
        <form method="post" action="/guests/{{ guest.id }}/verify-identity" class="verify-form guest-card-action">
          <input type="hidden" name="return_to" value="/reservations/{{ reservation.id }}">
          <button class="ui-btn ui-btn-secondary ui-btn-compact" type="submit">{{ t('host.verify_button') }}</button>
          {% if row.has_passport_photo %}
            <a class="ui-sub" href="/guests/{{ guest.id }}?return_to=/reservations/{{ reservation.id }}">{{ t('host.verify_view_photo') }}</a>
          {% endif %}
        </form>
      {% endif %}
"""
patch("reservation_detail.html", [(A, ""), (B, "")])
C = """    <p class="small muted" style="margin:0 0 10px">{{ t('host.verify_in_person') }}</p>
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
"""
D = """{% if editing and needs_verification %}
<form id="verify-{{ guest.id }}" method="post" action="/guests/{{ guest.id }}/verify-identity">
  <input type="hidden" name="_csrf" value="{{ csrf_token }}">
  <input type="hidden" name="return_to" value="/guests/{{ guest.id }}?return_to=/reservations/{{ reservation.id }}">
</form>
{% endif %}
"""
patch("guest_form_admin.html", [
    (C, "  </div>\n  {% endif %}\n"),
    (D, ""),
    # 0136: without the button the panel only has the preview, so it opens only when there is a photo.
    ("  {% if editing and needs_verification %}\n", "  {% if editing and needs_verification and has_passport_photo %}\n"),
])
print("ok")
EOF
```

   Expected: `ok`. Command: `grep -c 'verify-identity\|host.verify_' App/app/templates/reservation_detail.html App/app/templates/guest_form_admin.html`. Expected: `0` for both. Then `cd App && .venv/bin/python -c "from app.templating import templates; templates.env.get_template('guest_form_admin.html'); templates.env.get_template('reservation_detail.html'); print('compiled')"`. Expected: `compiled`.

2. In `App/app/host_i18n.py`, run from `App/`:

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
assert "host.verify_" not in s
p.write_text(s, encoding="utf-8"); print("ok")
EOF
```

   Expected: `ok`. Command: `cd App && .venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -5`. Expected: passed (`test_host_i18n` language-endpoint test is a known local failure only when run alone; here it runs with its file).

3. In `App/app/passport_photos.py` make these three comment edits (no code line changes):
   - lines 4 to 11: replace `Files stay on disk only until the host confirms the data matches the\ndocument, then are deleted immediately. Only authenticated hosts can read them\nvia the admin route. Unverified files go 7 days after check-in, and no file\nlives longer than 30 days after upload (see ``purge_stale``).\n\nVerification is the happy path, not a guarantee: a host can simply never press\nthe button. ``purge_stale`` is the backstop that makes the promise true, and it\nalso clears files no guest row points at any more, which nothing else can reach.` with `Files stay on disk only until they have no purpose left. Only authenticated\nhosts can read them via the admin route. A file goes 7 days after check-in and\nnever lives longer than 30 days after upload (see ``purge_stale``). 0136 removed\nthe host's "Mark ID checked" button, so these two limits are the whole rule;\n``purge_stale`` also clears files no guest row points at any more.`
   - lines 221 to 223: replace `# retention decision (legal positions, section 4) is: delete it when the host\n# marks the guest verified, otherwise 7 days after check-in, and never later\n# than 30 days after upload, whatever the stay dates say.` with `# retention decision (legal positions, section 4) is: 7 days after check-in, and\n# never later than 30 days after upload, whatever the stay dates say. A row that\n# still carries identity_verified_at (hand-entered guests) also qualifies.`
   - lines 273 to 274: replace `verified (the Verify route deletes at once; this catches every other path\n    that sets ``identity_verified_at``), check-in was more than 7 days ago, or` with `verified (hand-entered guests set ``identity_verified_at`` on save; no button\n    does any more), check-in was more than 7 days ago, or`

   Command: `cd App && git diff --stat app/passport_photos.py | tail -1 && .venv/bin/python -m pytest tests/test_retention.py tests/test_passport_photo*.py -q --tb=short -x 2>&1 | tail -5`. Expected: passed (behaviour unchanged).

4. Tests, from `App/` (one script, then one new file):

```
.venv/bin/python - <<'EOF'
import pathlib
def patch(path, pairs):
    p = pathlib.Path(path); s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, (path, old[:70], s.count(old)); s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")
E_OLD = '''def test_the_guest_card_keeps_its_amber_id_not_checked_pill(host):
    """The guest-card pill is a per-person to-do, so amber stays there."""
    client, _, reservation_id = host
    page = client.get(f"/reservations/{reservation_id}")
    assert page.status_code == 200
    tone, _tip = _pill(page.text, host_i18n.translate("en", "host.verify_pending"))
    assert tone == "amber"
'''
E_NEW = '''def test_the_guest_card_reads_ready_now_that_the_id_check_is_gone(host):
    """0136: no "Mark ID checked" button, no amber "ID not checked" badge; a complete guest reads Ready.

    The stay pill's tip still says "ID not checked (optional)": that is the
    reporting status text, not the removed badge.
    """
    client, _, reservation_id = host
    page = client.get(f"/reservations/{reservation_id}")
    assert page.status_code == 200
    assert "verify-identity" not in page.text
    assert not [pill for pill in _pills(page.text) if pill[2].strip() == "ID not checked"]
    tone, _tip = _pill(page.text, "Ready")
    assert tone == "blue"
'''
patch("tests/test_status_colours.py", [(E_OLD, E_NEW)])
patch("tests/test_host_guest_form.py", [
    ("def test_the_verify_identity_form_is_not_nested_in_the_guest_form():", "def test_the_guest_form_has_no_nested_form_and_no_verify_form():"),
    ('''        # The verify button still submits, through the form attribute.
        assert f'<form id="verify-{guest_id}"' in html
        assert f'form="verify-{guest_id}"' in nested
''', '''        # 0136: the ID check button and its form are gone.
        assert "verify-identity" not in html
'''),
])
patch("tests/test_wp28_geometry.py", [
    ("              const out = {placeholders: [], verify: null, filing: null};", "              const out = {placeholders: [], filing: null};"),
    ('''              const verify = document.querySelector('.guest-card .verify-form .ui-btn');
              if (verify) {
                const card = verify.closest('.guest-card');
                out.verify = Math.round(R(card).bottom - R(verify).bottom);
              }
''', ""),
    ('''    if measured["verify"] is not None:
        assert measured["verify"] >= 8, f"Mark ID checked touches the card edge: {measured}"
''', ""),
])
print("ok")
EOF
```

   Expected: `ok`. Create `App/tests/test_remove_id_check.py`:

```python
"""0136: the host ID check lost its button and texts; filing code did not move."""
from __future__ import annotations

import inspect
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

   Command: `cd App && .venv/bin/python -m pytest tests/test_remove_id_check.py tests/test_status_colours.py tests/test_host_guest_form.py tests/test_send_controls.py tests/test_endtoend.py tests/test_wp28_ui_sweep.py tests/test_design_stay_detail.py tests/test_design_lint.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed. Then the filing row: `cd App && .venv/bin/python -m pytest tests/test_ubyport_*.py tests/test_worker.py tests/test_submission_*.py tests/test_filed_by_hand.py tests/test_duplicate_guard.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed.

5. Browser and screenshots, from `App/` with `UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_SHOTS_DIR=/tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0136`: `.venv/bin/python -m pytest tests/test_host_stay_detail_layout_browser.py tests/test_wp28_geometry.py tests/test_host_geometry.py -q --tb=short -rs 2>&1 | tail -30`. Expected: passed, 0 skipped. Screenshots (guest edit page and stay detail, 390 and 1280): `UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers SHOT_TASK=0136 SHOT_PAGES="guest-edit stay" .venv/bin/python -m pytest /tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shoot_pages.py -q -s 2>&1 | tail -8` (a scratch helper outside the repo; it reuses the `stay_actions_host` cookie the way `test_host_stay_detail_layout_browser.py` does). Expected: four `SHOT` lines and `1 passed`; files `guest-edit-390.png`, `guest-edit-1280.png`, `stay-390.png`, `stay-1280.png` in that folder. Open them and write what you see (no "Mark ID checked", no "ID not checked" badge, the guest card ends with its facts).

6. Lint and commit: `python3 scripts/design_lint.py | tail -3 && App/.venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 App/ | tail -3`, then `git add App/app/templates/reservation_detail.html App/app/templates/guest_form_admin.html App/app/host_i18n.py App/app/passport_photos.py App/tests && git commit -m "0136 step 6: remove the host ID check button, badge and unused texts"`.

## 5. Do not touch

`app/reporting.py`, `app/routes/admin.py` (the route stays), `app/db.py`, `app/migrations/`, `app/ubyport/`, `passport_photos.py` code lines, the guest pages, `_components.html`, any CSS; hard rules 1, 2, 3, 8.

## 6. Commands

- Step 4 commands (both rows) and step 5, 0 skipped.
- `python3 scripts/design_lint.py` expected: OK.
- Known local failures elsewhere (not in this brief's runs; if you see one, note it and move on, never fix it here): `test_host_i18n` language endpoint run alone, `test_property_navigation_browser.py`, `test_host_properties_navigation` fit test, `test_host_fit_browser`, `test_host_invoice_items_browser`, `test_host_property_controls_browser`, `test_host_ux_acceptance` rail-cards test, `test_host_list_page_layout_browser` properties `[40, 42]`, `test_onboarding_wizard_browser.py:1518` skeleton flake (passes on rerun).

## 7. Acceptance

- [ ] No "Mark ID checked" button or "ID not checked" badge on the stay detail; no check panel on the guest edit page; the passport preview still shows when a photo exists, and no empty panel renders when it does not.
- [ ] `grep -rn 'host.verify_' App/app` prints nothing; en and cs have the same keys.
- [ ] Filing tests pass unchanged; `reporting.py` and `routes/admin.py` have no diff.
- [ ] 390 px and 1280 px screenshots of the guest edit page and the stay detail in the shots folder and described in the report.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found verbatim; a count in step 1, 2 or 4 differs; a filing test fails once; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0136-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left, screenshot paths and what they show. State explicitly: "filing behaviour unchanged; reporting.py and routes/admin.py untouched".

## Risk list (for the reviewer)

`App/app/templates/reservation_detail.html`, `App/app/templates/guest_form_admin.html` (guest card and edit page, hard rule 1 adjacency; the hand-entry hint `host.verify_host_entry` is removed with the panel), `App/app/host_i18n.py` (deleted keys).

## Owner steps

None (set confirmed 2026-10-19).
