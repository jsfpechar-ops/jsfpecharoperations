# 0376: Host opt-in for Leon (AI) per property, and a test list for AI in production

Status: todo
Depends on: none | Base commit: 4ec9930 | Branch: claude/0376-ai-production-gates (already checked out; commit here)
Executor: Haiku 5.5 | Reviewer: Opus | Fits one session: 40 tool calls, 80k tokens

## 1. Objective

Owner, 2026-10-25: he wants to test Leon (AI) and Havel (AI) on production, and "for Leon only if the user ticks yes that they want to use him".

Today Leon answers a property's guests as soon as `leon` is in `UBYHOST_AI_FEATURES` and the guide is live (all must-have cards done). There is no host choice. This brief adds:

1. **Host opt-in per property.** New column `apartment.leon_enabled` (default 0). The host guide page gets a "Leon (AI)" section with one toggle and a Save button. Leon's chat card and its four JSON endpoints stay off (404 / no card) for a property until its host switches it on.
2. **A test list.** New env var `UBYHOST_AI_TEST_EMAILS` (comma-separated e-mails, case-insensitive). When it is set, only those accounts get Havel, and only properties whose owner is on the list get Leon and guide translation. When it is empty, nothing changes (everyone, as today).

With no env change nothing visible changes on production: AI is off there today.

## 2. Context

- `App/app/config.py` ~line 322: `AI_FEATURES = frozenset(...)` from `UBYHOST_AI_FEATURES`.
- `App/app/ai.py`: `def enabled(feature: str) -> bool:` (feature listed and a provider key). `ai` already imports `db`.
- Owner of a property: `apartment.owner_user_id` -> `user_account.email`.
- Leon gates today:
  - `App/app/routes/guest_guide_view.py` `_page`: `"leon_url": leon_url if live and ai.enabled("leon") else "",`
  - `App/app/routes/guest_leon.py`: four endpoints each start with `if early or not guest_guide.progress(apartment["id"])["live"]: return _gone()`.
- Guide translation gate: `App/app/guide_translate.py` `def can_fill(apartment_id: int)` returns `ai.enabled(FEATURE) and ai.budget_state(...) == "ok"`.
- Havel gates (all `ai.enabled(havel.FEATURE)`): `App/app/routes/havel.py` in `_state(uid)` (~line 98) and in the POST branch `elif not ai.enabled(havel.FEATURE):` (~line 207); `App/app/routes/api.py` ~line 116 (palette row); `App/app/routes/admin.py` ~line 515 (`"havel_on": ...`). Get the e-mail with `auth.current_user(request)` (a row with `email`, or None).
- Host guide page: route `guide_index` in `App/app/routes/guest_guide.py`, template `App/app/templates/guest_guide.html`. POST routes `/apartments/{apartment_id}/guide/{item_id}` exist, so the new POST route must be registered **above** them (next to `guide_import`). Pattern to copy: `guide_import` (login guard, `_home`, form, `back(..., msg=flash(request, key))`).
- UI macros: `ui_toggle(id, label, name='', checked=false, attrs='')` and `ui_section`, `ui_button` from `_ui.html`. **Only one primary button per page** (design tests): the Save button is `'secondary'`.
- Copy: `App/app/host_i18n.py` has `en` and `cs` blocks with `guest_guide.*` and `flash.guest_guide.*` keys (e.g. `"guest_guide.import.off"`); Vietnamese lives in `App/app/host_vi_i18n.py` (`_VI_STRINGS`).
- Migrations: last is `App/app/migrations/0020_havel_gap.sql`. Base schema in `db.py` is not edited; migrations only.

## 3. Files

| Path | Action |
|---|---|
| App/app/migrations/0021_leon_opt_in.sql | new |
| App/app/config.py | add `AI_TEST_EMAILS` |
| App/app/ai.py | add `enabled_for`, `enabled_for_property` |
| App/app/leon.py | add `switched_on(apartment)` |
| App/app/routes/guest_guide_view.py | use `leon.switched_on` |
| App/app/routes/guest_leon.py | use `leon.switched_on` in the 4 endpoints |
| App/app/guide_translate.py | `can_fill` checks the owner |
| App/app/routes/havel.py, api.py, admin.py | `ai.enabled_for(havel.FEATURE, email)` |
| App/app/routes/guest_guide.py | context `leon_offer`, `leon_on`; new POST `/apartments/{id}/guide/leon` |
| App/app/templates/guest_guide.html | Leon section |
| App/app/host_i18n.py, App/app/host_vi_i18n.py | new keys en/cs/vi |
| App/tests/test_0376_ai_gates.py | new |
| existing Leon/translate tests | set `leon_enabled = 1` where they expect Leon on |
| docs/DEPLOYMENT.md (or the env table it uses) | document `UBYHOST_AI_TEST_EMAILS` |

## 4. Steps

1. `0021_leon_opt_in.sql`:
   ```sql
   -- Brief 0376: Leon (AI) answers a property's guests only after its host switches it on.
   ALTER TABLE apartment ADD COLUMN leon_enabled INTEGER NOT NULL DEFAULT 0;
   ```
2. `config.py`, right after `AI_FEATURES`:
   ```python
   # 0376: while AI is tested on production, only these accounts get it (comma-separated
   # e-mails, any case). Empty means every account. Leon and guide translation follow the
   # property owner's e-mail, Havel the signed-in host's.
   AI_TEST_EMAILS = frozenset(
       part.strip().lower() for part in os.environ.get("UBYHOST_AI_TEST_EMAILS", "").split(",") if part.strip()
   )
   ```
3. `ai.py`, after `enabled`:
   ```python
   def enabled_for(feature: str, email: Optional[str]) -> bool:
       """``enabled`` and, while UBYHOST_AI_TEST_EMAILS is set, only for an account on it (0376)."""
       if not enabled(feature):
           return False
       return not config.AI_TEST_EMAILS or (email or "").strip().lower() in config.AI_TEST_EMAILS


   def enabled_for_property(feature: str, apartment_id: int) -> bool:
       """``enabled_for`` with the property owner's e-mail."""
       row = db.query_one(
           "SELECT u.email FROM apartment a JOIN user_account u ON u.id = a.owner_user_id WHERE a.id = ?",
           (apartment_id,),
       )
       return enabled_for(feature, row["email"] if row else "")
   ```
4. `leon.py`, near `FEATURE`:
   ```python
   def switched_on(apartment) -> bool:
       """0376: the host ticked yes for this property, Leon is on and the owner may use AI."""
       return bool(apartment["leon_enabled"]) and ai.enabled_for_property(FEATURE, int(apartment["id"]))
   ```
   If `apartment` rows in the guest routes do not carry `leon_enabled` (check what `guide_token.apartment_for` and `_stay_gate` select), read the column with a small query by id instead of changing those selects.
5. `guest_guide_view.py` `_page`: `"leon_url": leon_url if live and leon.switched_on(apartment) else "",`. Drop the `ai` import only if nothing else there uses it.
6. `guest_leon.py`: in all four endpoints change the gate to `if early or not guest_guide.progress(apartment["id"])["live"] or not leon.switched_on(apartment):`. Add a docstring line: "Also 404 until the host switches Leon on (0376)."
7. `guide_translate.can_fill`: `return ai.enabled_for_property(FEATURE, apartment_id) and ai.budget_state(FEATURE, str(apartment_id)) == "ok"`.
8. Havel: add to `routes/havel.py`
   ```python
   def _on(request: Request) -> bool:
       user = auth.current_user(request)
       return ai.enabled_for(havel.FEATURE, user["email"] if user else "")
   ```
   `_state` gets `request` as its first parameter (update its callers) and uses `_on(request)`; the POST branch uses `elif not _on(request):`. In `api.py` and `admin.py` use `ai.enabled_for(havel.FEATURE, <current user email>)` the same way.
9. `routes/guest_guide.py`:
   - `guide_index` context: `leon_offer=ai.enabled_for_property(leon.FEATURE, apartment_id)`, `leon_on=bool(apartment.get("leon_enabled"))`.
   - New route above `guide_import`:
   ```python
   @router.post("/apartments/{apartment_id}/guide/leon")
   async def guide_leon(request: Request, apartment_id: int):
       """0376: the host's yes/no for Leon (AI) on this property. Off is always allowed."""
       guard = auth.require_login(request)
       if guard:
           return guard
       _home(request, apartment_id)
       form = await request.form()
       on = form.get("on") == "1" and ai.enabled_for_property(leon.FEATURE, apartment_id)
       db.execute("UPDATE apartment SET leon_enabled = ? WHERE id = ?", (1 if on else 0, apartment_id))
       key = "flash.guest_guide.leon_on" if on else "flash.guest_guide.leon_off"
       return back(f"{_base(apartment_id)}#leon", msg=flash(request, key))
   ```
   (Use whatever write helper `db.py` offers if `db.execute` is named differently.)
10. `guest_guide.html`, a section right before the import section, only `{% if leon_offer %}`:
   ```jinja
   {% call ui_section(t('guest_guide.leon.title'), id='leon') %}
   <p class="ui-sub">{{ t('guest_guide.leon.help') }}</p>
   <form method="post" action="{{ base_url }}/leon">
   <input type="hidden" name="_csrf" value="{{ csrf_token }}">
   {{ ui_toggle('guide-leon-on', t('guest_guide.leon.toggle'), name='on', checked=leon_on) }}
   <div class="ui-form-actions">{{ ui_button(t('guest_guide.leon.save'), 'secondary', type='submit') }}</div>
   </form>
   {% if leon_on and not progress.live %}<p class="ui-sub">{{ t('guest_guide.leon.waiting') }}</p>{% endif %}
   {% endcall %}
   ```
   Check what value `ui_toggle` submits when checked; make the route accept it (the macro may send `value="1"` or `on`).
11. Copy keys (en / cs / vi):
   - `guest_guide.leon.title`: "Leon (AI) for your guests" / "Leon (AI) pro vaše hosty" / "Leon (AI) cho khách của bạn"
   - `guest_guide.leon.help`: "Leon answers guests' questions from the cards marked Done, and passes anything he does not know to you. He stays off until you switch him on." / "Leon odpovídá hostům na otázky podle karet označených Hotovo a vše, co neví, předá vám. Dokud ho nezapnete, zůstává vypnutý." / "Leon trả lời câu hỏi của khách dựa trên các thẻ đã đánh dấu Xong và chuyển cho bạn những gì anh ấy không biết. Leon sẽ tắt cho đến khi bạn bật."
   - `guest_guide.leon.toggle`: "Let Leon answer my guests" / "Ať Leon odpovídá mým hostům" / "Cho phép Leon trả lời khách của tôi"
   - `guest_guide.leon.save`: "Save" / "Uložit" / "Lưu"
   - `guest_guide.leon.waiting`: "Leon starts once the guide is live." / "Leon začne, jakmile bude průvodce zveřejněný." / "Leon sẽ bắt đầu khi hướng dẫn được công khai."
   - `flash.guest_guide.leon_on`: "Leon (AI) is on for this property." / "Leon (AI) je pro tuto nemovitost zapnutý." / "Leon (AI) đã bật cho chỗ nghỉ này."
   - `flash.guest_guide.leon_off`: "Leon (AI) is off for this property." / "Leon (AI) je pro tuto nemovitost vypnutý." / "Leon (AI) đã tắt cho chỗ nghỉ này."
12. Existing tests that expect Leon on (grep `leon_url`, `/leon"`, `guide/leon` in App/tests): set `UPDATE apartment SET leon_enabled = 1` in their setup. Do not loosen any assertion.
13. `test_0376_ai_gates.py` (use the fake client from `ai_fake.py` and the existing Leon test fixtures as a pattern):
   - Live guide, `leon` on, `leon_enabled = 0`: QR POST `/g/{token}/leon` -> 404 and the guide page has no `data-leon`. Same for the stay door.
   - Same with `leon_enabled = 1` -> 200 / card present.
   - `AI_TEST_EMAILS = {"owner@example.com"}` (monkeypatch `config.AI_TEST_EMAILS`) and an owner with another e-mail: Leon 404 even with `leon_enabled = 1`; `guide_translate.can_fill` False; the host guide page has no `id="leon"` section; POST `/guide/leon` with `on=1` stores 0.
   - Same list containing the owner (any case): all on.
   - Havel: with a test list not containing the host, `_state` is `"off"` (POST `/havel` with a message answers with the `havel.off` text and the fake client is never called); with the host listed, the fake client is called.
   - Host POST `/apartments/{id}/guide/leon` `on=1` -> column 1, then no `on` -> 0; another host's property -> 404.
14. Document `UBYHOST_AI_TEST_EMAILS` next to the other `UBYHOST_AI_*` vars (find them with `grep -rn UBYHOST_AI_FEATURES docs deploy`).

## 5. Do not touch

- `App/app/db.py` base schema (migrations only), `leon.reply` and the Leon prompt, Havel's limits, any CI workflow.

## 6. Commands

- `App/.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841` (from `App/`)
- `python scripts/design_lint.py`, `python scripts/migration_guard.py` if it runs locally
- `pytest App/tests/test_0376_ai_gates.py App/tests/test_leon.py App/tests/test_guest_leon_chat.py App/tests/test_guest_guide_view.py App/tests/test_guest_guide_pages.py App/tests/test_guide_translate.py App/tests/test_havel_page.py App/tests/test_havel_panel.py App/tests/test_havel_palette.py App/tests/test_ai.py App/tests/test_design_*.py -q` plus any i18n parity test (`grep -ln "host_vi_i18n\|STRINGS\[" App/tests`).
- `git checkout -- docs/tasks` if browser tests rewrote screenshots.

## 7. Acceptance

- With no new env vars nothing changes for hosts or guests on production.
- Leon's card and endpoints stay off for a property until its host switches Leon on.
- With `UBYHOST_AI_TEST_EMAILS` set, Havel, Leon and guide translation work only for listed accounts.
- Every command in section 6 passes.

## 8. Stop and ask

- If a step needs a new dependency, a change to Leon's answers, or a second migration.

## 9. Report

Write `docs/tasks/0376-report.md`: what changed, test output summary, anything you could not do.
