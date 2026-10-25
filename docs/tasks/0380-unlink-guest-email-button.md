# 0380: "Unlink this e-mail" button with a "?" on the stay page

Status: todo
Depends on: none | Base commit: 4ec9930 | Branch: claude/project-thread-uzatqp (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Owner, 2026-10-25: a user could not find "Release assignment" (hidden in the stay's ⋯ menu) and the name did not say what it does. It becomes a visible bordered button "Unlink this e-mail" in the stay's guest-form line (Guests section), with a "?" toggletip that explains it, and the old menu item goes.

What the action really does (`App/app/claim.py` `release()`): only one guest e-mail can fill in a stay's guest form. Release clears that e-mail, cuts off the browser that confirmed it, keeps the guests already entered, and lets the next person who opens the guest form claim the stay with their own e-mail.

## 2. Context

`App/app/templates/reservation_detail.html`, inside `{{ row_menu_begin() }}` … `{{ row_menu_end() }}` (the ⋯ menu of the Now section), this block exists verbatim:

```
        {% if stay_claim.state != 'unclaimed' %}
          <form method="post" action="/reservations/{{ reservation.id }}/release-claim" class="row-menu-form"
                data-confirm data-confirm-message="{{ t('stay.claim.release_confirm') }}">
            <input type="hidden" name="_csrf" value="{{ csrf_token }}">
            <button class="row-menu-item" type="submit" role="menuitem">{{ t('stay.claim.release') }}</button>
          </form>
        {% endif %}
```

Further down, in the Guests section:

```
{% if stay_claim and (stay_claim.state != 'unclaimed' or stay_claim.guest_access_locked_at) %}
<div class="stay-claim-line">
  <div class="stay-claim-label">{{ t('stay.claim.title') }}</div>
  <p>
  ...
  </p>
</div>
{% endif %}
```

`help_tip(id, text)` is already imported and used in this template. `App/app/static/app.css` already has `.stay-claim-line .stay-command-actions { flex: 0 0 auto; }`, so **no CSS change** and no `?v=` bump.

`App/tests/test_remove_legacy_actions.py` line 32: `assert "reopen-guest" in menu and "release-claim" in menu`.

Translations: EN and CS live in `App/app/host_i18n.py` (EN block first, CS block second; same key appears once per block), VI in `App/app/host_vi_i18n.py`, guide copy in `App/app/guide_i18n.py` (EN then CS) and `App/app/host_vi_i18n.py`.

## 3. Files

| Path | Action |
|---|---|
| App/app/templates/reservation_detail.html | delete the menu block; add the button + tip to the claim line |
| App/app/host_i18n.py | change 4 keys in EN and CS, add 1 key in EN and CS |
| App/app/host_vi_i18n.py | same for VI, plus 2 guide keys |
| App/app/guide_i18n.py | 2 keys in EN and CS |
| App/tests/test_remove_legacy_actions.py | line 32 |
| App/tests/test_0380_unlink_email_browser.py | new |
| docs/tasks/screenshots-0380/ | new PNGs from the test |
| docs/tasks/0380-report.md | new |

No other file may change. "Reopen guest access" stays in the menu.

## 4. Steps

1. Template: delete the menu block quoted in §2 (all 7 lines). In the claim line, directly after the closing `</p>` and before `</div>`, insert:
```
  {% if stay_claim.state != 'unclaimed' %}
  <div class="stay-command-actions">
    <form method="post" action="/reservations/{{ reservation.id }}/release-claim" class="inline"
          data-confirm data-confirm-message="{{ t('stay.claim.release_confirm') }}">
      <input type="hidden" name="_csrf" value="{{ csrf_token }}">
      <button class="ui-btn ui-btn-secondary ui-btn-compact" type="submit" data-release-claim>{{ t('stay.claim.release') }}</button>
    </form>
    {{ help_tip('release-claim-help', t('stay.claim.release_help')) }}
  </div>
  {% endif %}
```
Also change `<div class="stay-claim-line">` to `<div class="stay-claim-line" data-stay-claim>`.

2. Copy. Replace the value of each key (keep the key, quotes and trailing comma; a value that spans lines in parentheses becomes one line). Add `stay.claim.release_help` on the line after `stay.claim.release` in each language.

| Key | EN | CS | VI |
|---|---|---|---|
| stay.claim.title | Guest form access | Přístup k formuláři hostů | Quyền điền biểu mẫu khách |
| stay.claim.release | Unlink this e-mail | Odpojit tento e-mail | Gỡ email này |
| stay.claim.release_help (new) | Only one e-mail can fill in this stay's guest form. Unlink it if the wrong person took the stay: their link stops working, guests already entered are kept, and the next person who opens the guest form can use their own e-mail. | Formulář hostů k pobytu může vyplňovat jen jeden e-mail. Odpojte ho, pokud pobyt zabral někdo jiný: jeho odkaz přestane fungovat, už zadaní hosté zůstanou a další, kdo formulář otevře, může použít vlastní e-mail. | Mỗi lượt lưu trú chỉ một email được điền biểu mẫu khách. Gỡ email nếu người khác đã nhận nhầm: liên kết của họ ngừng hoạt động, khách đã nhập vẫn được giữ, và người tiếp theo mở biểu mẫu có thể dùng email của mình. |
| stay.claim.release_confirm | Unlink this e-mail? Its link stops working, and the next person who opens the guest form can take the stay with their own e-mail. | Odpojit tento e-mail? Jeho odkaz přestane fungovat a další, kdo otevře formulář hostů, může pobyt převzít vlastním e-mailem. | Gỡ email này? Liên kết của email đó sẽ ngừng hoạt động và người tiếp theo mở biểu mẫu khách có thể nhận lượt lưu trú bằng email của mình. |
| flash.reservations.claim_released | E-mail unlinked. The next person who opens the guest form can take this stay. | E-mail odpojen. Pobyt může převzít další, kdo otevře formulář hostů. | Đã gỡ email. Người tiếp theo mở biểu mẫu khách có thể nhận lượt lưu trú này. |

Guide keys (in `guide_i18n.py` for EN/CS, `host_vi_i18n.py` for VI). In `guide.faq.link_a` replace only the last sentence; replace `guide.guest_links.wrong3` whole:

| Key | EN | CS | VI |
|---|---|---|---|
| guide.faq.link_a, last sentence | If someone else claimed it, open the stay and press Unlink this e-mail under Guests. | Pokud ho převzal někdo jiný, otevřete pobyt a v části Hosté stiskněte Odpojit tento e-mail. | Nếu người khác đã xác nhận, mở lượt lưu trú và bấm Gỡ email này trong phần Khách. |
| guide.guest_links.wrong3 | A guest says someone else already took the stay: open the stay and press Unlink this e-mail under Guests. | Host říká, že pobyt už zabral někdo jiný: otevřete pobyt a v části Hosté stiskněte Odpojit tento e-mail. | Khách nói người khác đã nhận lượt lưu trú: mở lượt lưu trú và bấm Gỡ email này trong phần Khách. |

Check: `grep -rn "Release assignment\|Uvolnit přiřazení\|Gỡ liên kết" App/app | head` prints nothing.

3. `test_remove_legacy_actions.py` line 32 becomes two lines:
```
    assert "reopen-guest" in menu and "release-claim" not in menu
    assert text.count("data-release-claim") == 1  # 0380: a visible button in the Guests section
```

4. New `App/tests/test_0380_unlink_email_browser.py`. Copy the import block of `tests/test_host_stay_detail_layout_browser.py` (fixtures `stay_actions_host`, `stay_actions_base`, `_browser`, `sync_api`). Before opening pages, mark the "ready" stay as claimed:
```
from app import claim, db
rid = stay_actions_host["ids"]["ready"]
claim.ensure_row(rid)
db.execute("UPDATE reservation_claim SET state = ?, email = ?, email_masked = ?, claimed_at = ? WHERE reservation_id = ?",
           (claim.CLAIMED, "guest@example.test", "g***@example.test", db.utcnow(), rid))
```
   Test A `test_unlink_button_is_visible_and_explained`: for lang in en, cs, vi; for (width, collapsed) in (390, False), (1280, False), (1280, True), (2000, False), (2000, True): new context with viewport (width, 900), the session cookie as in the 0080 test, and `context.add_init_script("try { localStorage.setItem('ubyhost-sidebar-collapsed', '%s'); } catch (e) {}" % ("1" if collapsed else "0"))`. Go to `/reservations/{rid}?lang={lang}`, wait for networkidle. Assert:
   - `[data-stay-claim] [data-release-claim]` is visible and its text equals `host_i18n.translate(lang, "stay.claim.release")` (import `from app import host_i18n`; if VI does not resolve that way, use the same lookup the other VI tests use);
   - no horizontal scroll: `document.documentElement.scrollWidth <= window.innerWidth + 1`;
   - the button's bounding box does not overlap the claim line's `p`;
   - the menu (`[role=menu]`) contains no `release-claim` action;
   - click `[data-stay-claim] .help-tip-btn`: its `aria-expanded` becomes `"true"`, `#release-claim-help` is visible and its box is fully inside the viewport (left ≥ 0, right ≤ innerWidth).
   - Then, when `os.environ.get("UBYHOST_CAPTURE_0380") == "1"`, save `page.screenshot(path=EVIDENCE / f"{lang}-{width}{'c' if collapsed else ''}.png", full_page=True)` with the tip open, where `EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0380"` (mkdir it).

   Test B `test_unlink_asks_then_frees_the_stay`: EN, 1280 wide. Click the button; the confirm dialog opens (wait for a visible `[data-confirm-proceed]`); click it; after navigation the page shows the EN `flash.reservations.claim_released` text and `[data-release-claim]` is gone. Read back `SELECT state FROM reservation_claim WHERE reservation_id = ?` and assert it is `claim.UNCLAIMED` (use `db.query_one` or whatever helper `db.py` offers; grep `def ` in `App/app/db.py`).

## 5. Do not touch

Everything outside §3. No CSS, no JS, no new classes besides the two data attributes. `App/app/claim.py` and the route stay as they are.

## 6. Commands

From `App/`:
```
UBYHOST_CAPTURE_0380=1 UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests/test_0380_unlink_email_browser.py tests/test_remove_legacy_actions.py tests/test_flash_next_step.py tests/test_host_stay_detail_layout_browser.py tests/test_design_stay_detail.py tests/test_design_guardrails_browser.py -q --tb=short 2>&1 | tail -30
cd .. && python3 scripts/design_lint.py 2>&1 | tail -5
```
If a translation-coverage test fails elsewhere, run `grep -rln "stay.claim" App/tests` and include that file in the run.

## 7. Acceptance

- [ ] §6 passes with 0 skipped, or the first failing assertion is in the report.
- [ ] 15 PNGs in `docs/tasks/screenshots-0380/`.

## 8. Stop and ask

As in TEMPLATE §8. A test failing twice: stop and report; do not change CSS to make it pass.

## 9. Report

`docs/tasks/0380-report.md` (200 tokens), `Status: review`, with the test tail. One commit `0380: visible Unlink this e-mail button with help` including the screenshots. Do not push.
