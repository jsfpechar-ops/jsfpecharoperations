# 0010: Smart locks page under Property tools

Status: todo
Depends on: 0009 | Base commit: after 0009 merges | Branch: task/0010-smart-locks-page
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

Under Properties → Property tools, a host finds "Smart locks". One tap sets up a UbyHost TTLock user for them. The page then shows that user's name and one instruction: send each rental lock's eKey to it from the TTLock app. "Check for locks" lists the locks shared with it, with name, ID and battery. "Remove" disconnects everything. The host never types a TTLock password into UbyHost. A host without TTLock never needs the page.

## 2. Context

- Plan: `docs/plans/ttlock-door-codes.md` §8.2 (account model) and §10. Rule `docs/HOST_APP_DESIGN.md` §6: property-wide tools live in Property tools next to Guest links and Automation, and edits happen in context.
- Client (task 0009, `App/app/ttlock.py`): `create_account(owner_user_id) -> int`, `list_admin_locks(account_id) -> List[dict]` (items `lock_id`, `alias`, `battery`, `tz_offset_ms`, `key_end`), `delete_account(account_id)`, `receiver_name(account)`, `TTLockError` (`.kind`).
- Page pattern: `guest_links` in `App/app/routes/admin.py` (line 283) and `App/app/templates/guest_links.html` (`{% extends "base.html" %}`, `{% set nav = 'guest_links' %}`, `page_header(...)`, `copy_button(target_id)` from `_components.html`, which copies the text of the element with that id).
- Navigation `App/app/templates/_host_navigation.html`: line 5 `{% elif nav in ('apartments', 'entities', 'guest_links', 'automation') %}` and line 15 `{% if nav in ('apartments', 'entities', 'guest_links', 'automation') %}`, then the `host-tools` `<details>` with links to `/guest-links` and `/automation`.
- Template globals: `templates.env.globals[...]` in `App/app/templating.py` (line 340 onwards).
- POST handlers: `guard = auth.require_login(request)`, `if guard: return guard`; end with `_back(url, msg=_flash(request, key))` or `err=`. CSRF is automatic (router dependency and `static/csrf.js`). Owner id: `access.owner_id(request)`. Audit: `db.audit(action, detail)`, never a username or secret in `detail`. Safe redirect targets: `security.safe_local_path(value, default)`.
- Host strings: `App/app/host_i18n.py` EN and CS (parity test). No em dashes. Read `config.X` inside functions, never at import.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/ttlock.py` | edit | Step 1 |
| `App/app/templating.py` | edit | Step 2, one global |
| `App/app/routes/admin.py` | edit | Step 3 |
| `App/app/templates/smart_locks.html` | create | Step 4 |
| `App/app/templates/_host_navigation.html` | edit | Step 5 |
| `App/app/host_i18n.py` | edit | Step 6 |
| `App/tests/test_smart_locks_page.py` | create | Step 7 |
| `App/tests/test_host_geometry.py` | edit | Step 8, one test |

No other file may change.

## 4. Steps

1. **Client helpers** in `ttlock.py`:
   ```python
   DOOR_CODE_TERMS_VERSION = "2026-10-08"   # the door-code terms in the Guide (task 0016)

   def enabled() -> bool:
       """The owner has switched door codes on and set the app's TTLock credentials."""
       return bool(config.DOOR_CODES_ENABLED and config.TTLOCK_CLIENT_ID and config.TTLOCK_CLIENT_SECRET)

   def allowed_for(owner_user_id: Optional[int]) -> bool:
       return enabled() and owner_user_id is not None
   ```
   Plus `account_for(owner_user_id) -> Optional[Row]` (the `lock_account` row for that owner, provider `ttlock`) and `locks_of(account) -> List[dict]` (`json.loads(account["locks_json"] or "[]")`).
2. **Global** in `templating.py`: `templates.env.globals["door_codes_enabled"] = lambda: ttlock.enabled()` (import inside the lambda's module scope the way the other globals do).
3. **Routes** in `admin.py`, all requiring login; every handler returns `_back("/apartments", err=_flash(request, "flash.error.smart_locks_unavailable"))` when `not ttlock.enabled()`. `return_to` is read from the form or query and passed through `security.safe_local_path(value, "/smart-locks")`; only `/smart-locks` and `/apartments/...` paths are kept.
   - `GET /smart-locks` (`smart_locks_page`): render `smart_locks.html` with `account` (or `None`), `receiver` (`ttlock.receiver_name(account)` if any), `locks` (`ttlock.locks_of(account)`), `fetched_at`, `reauth` (`account["status"] != "ok"`), `return_to`, and `properties_using`: for each lock id, the internal names of this owner's apartments whose `lock_id` equals it and `lock_provider = 'ttlock'`.
   - `POST /smart-locks/setup` (`smart_locks_setup`): the tick box `terms` must be `"1"`, else `err` `flash.error.smart_locks_terms`. Rate limit scope `ttlock_setup`, key `f"user:{owner_id}"`, at most 5 (`rate_limit.blocked` / `rate_limit.record`), error `flash.error.smart_locks_rate_limited`. Then `ttlock.create_account(owner_id)`. `TTLockError`: `flash.error.smart_locks_failed`. Success: `db.audit("door_code_terms_accepted", f"version={ttlock.DOOR_CODE_TERMS_VERSION}")`, `msg` `flash.ok.smart_locks_ready`, redirect to `/smart-locks` keeping `return_to`.
   - `POST /smart-locks/refresh` (`smart_locks_refresh`): needs an account (else `flash.error.smart_locks_missing_account`). `ttlock.list_admin_locks(account["id"])`. Kind `budget`: `flash.error.smart_locks_budget`; kind `reauth`: `flash.error.smart_locks_reauth`; other errors: `flash.error.smart_locks_failed`. Success with no locks: `msg` `flash.ok.smart_locks_none_yet` and stay on `/smart-locks`. Success with locks: `msg` `flash.ok.smart_locks_found` (plural via `tp`, count = number of locks) and redirect to `return_to` if it is an `/apartments/...` path, else `/smart-locks`.
   - `POST /smart-locks/remove` (`smart_locks_remove`): in one `with db.cursor() as cur:` block set `lock_provider = NULL` on this owner's apartments; then `ttlock.delete_account(account["id"])` (it deletes the TTLock user, which also removes every shared eKey, and the row). On `TTLockError` still finish and use `flash.ok.smart_locks_removed_local`; otherwise `flash.ok.smart_locks_removed`. `db.audit("smart_locks_removed", "")`. Redirect to `/smart-locks`.
4. **Page** `smart_locks.html` (`{% set nav = 'smart_locks' %}`, `page_header(t('smart_locks.title'), t('smart_locks.lede'))`). Three states, each one panel:
   - **No account:**
     ```
     <section class="panel" id="smart-locks-setup">
       <form method="post" action="/smart-locks/setup">
         <input type="hidden" name="return_to" value="{{ return_to }}">
         <div class="checkline"><input type="checkbox" id="terms" name="terms" value="1" required>
           <label for="terms">{{ t('smart_locks.terms') }} <a href="/guide#door-codes-terms">{{ t('smart_locks.terms_link') }}</a></label></div>
         <div class="action-group"><button class="btn primary" type="submit">{{ t('smart_locks.setup') }}</button></div>
       </form>
       <p class="small muted"><a href="/guide#door-codes">{{ t('smart_locks.guide_link') }}</a></p>
     </section>
     ```
   - **Account, no locks yet** (and the same block above the list once locks exist, folded in a `<details>` titled `smart_locks.add_more`):
     ```
     <section class="panel" id="smart-locks-share">
       <h2 style="margin-top:0">{{ t('smart_locks.share_title') }}</h2>
       <p>{{ t('smart_locks.share_step') }}</p>
       <p><code id="ttlock-receiver">{{ receiver }}</code> {{ copy_button('ttlock-receiver') }}</p>
       <p class="small muted">{{ t('smart_locks.share_settings') }} <a href="/guide#door-codes">{{ t('smart_locks.guide_link') }}</a></p>
       <form method="post" action="/smart-locks/refresh"><input type="hidden" name="return_to" value="{{ return_to }}">
         <div class="action-group"><button class="btn primary" type="submit">{{ t('smart_locks.check') }}</button></div></form>
     </section>
     ```
   - **Locks found:** a panel `id="smart-locks-list"` with one row per lock: alias, `t('smart_locks.lock_id', id=...)`, battery (`t('smart_locks.battery', percent=...)`), the properties using it (or `t('smart_locks.unused')`), and `<strong>{{ t('smart_locks.timezone_warning') }}</strong>` when `tz_offset_ms` is not `None` and not `3600000`. Under the list, one `action-group` with the Refresh form (`smart_locks.check`) and the Remove form (`btn danger`, `data-confirm data-confirm-message="{{ t('smart_locks.remove_confirm') }}"`, label `smart_locks.remove`).
   - `reauth` shows `<p class="small"><strong>{{ t('smart_locks.reauth') }}</strong></p>` at the top.
5. **Navigation**: add `'smart_locks'` to both `nav in (...)` tuples in `_host_navigation.html`, and inside the `host-tools` `<div>`, after the Automation link: `{% if door_codes_enabled() %}<a href="/smart-locks" {% if nav == 'smart_locks' %}aria-current="page"{% endif %}>{{ t('smart_locks.title') }}</a>{% endif %}`. Nothing is added to the main sidebar or to Settings.
6. **Strings** (EN, CS). `flash.ok.smart_locks_found` is plural (`.one`, `.few`, bare key).

   | Key | EN | CS |
   |---|---|---|
   | `smart_locks.title` | Smart locks | Chytré zámky |
   | `smart_locks.lede` | Optional. With a TTLock lock and gateway, guests get a timed door code once everyone is registered. | Volitelné. Se zámkem a bránou TTLock dostanou hosté časově omezený kód ke dveřím, jakmile jsou všichni zaregistrováni. |
   | `smart_locks.terms` | I accept the door code terms. | Souhlasím s podmínkami pro kódy ke dveřím. |
   | `smart_locks.terms_link` | Read them | Přečíst |
   | `smart_locks.setup` | Set up | Nastavit |
   | `smart_locks.guide_link` | Step-by-step guide | Návod krok za krokem |
   | `smart_locks.share_title` | Share your locks with UbyHost | Sdílejte zámky s UbyHost |
   | `smart_locks.share_step` | In the TTLock app, open each rental lock, tap Send eKey and enter this account: | V aplikaci TTLock otevřete každý zámek pronájmu, klepněte na Odeslat eKey a zadejte tento účet: |
   | `smart_locks.share_settings` | Turn on Authorized admin, turn off Remote unlock, leave the end date empty. | Zapněte Autorizovaný správce, vypněte Vzdálené odemykání, datum konce nechte prázdné. |
   | `smart_locks.check` | Check for locks | Zkontrolovat zámky |
   | `smart_locks.add_more` | Add another lock | Přidat další zámek |
   | `smart_locks.lock_id` | ID %(id)s | ID %(id)s |
   | `smart_locks.battery` | battery %(percent)s %% | baterie %(percent)s %% |
   | `smart_locks.unused` | Not used by a property yet | Zatím nepoužívá žádné ubytování |
   | `smart_locks.timezone_warning` | Time zone is not Prague. Fix it in the TTLock app. | Časové pásmo není Praha. Opravte ho v aplikaci TTLock. |
   | `smart_locks.reauth` | TTLock no longer accepts this connection. Remove it and set it up again. | TTLock už toto připojení nepřijímá. Odeberte ho a nastavte znovu. |
   | `smart_locks.remove` | Remove | Odebrat |
   | `smart_locks.remove_confirm` | Remove the TTLock connection? Door codes stop for all your properties, and the shared eKeys are deleted. | Odebrat připojení TTLock? Kódy ke dveřím se vypnou u všech vašich ubytování a sdílené eKey se smažou. |
   | `flash.ok.smart_locks_ready` | Set up. Now share your locks. | Nastaveno. Teď sdílejte své zámky. |
   | `flash.ok.smart_locks_found.one` | %(count)s lock found. | Nalezen %(count)s zámek. |
   | `flash.ok.smart_locks_found.few` | %(count)s locks found. | Nalezeny %(count)s zámky. |
   | `flash.ok.smart_locks_found` | %(count)s locks found. | Nalezeno %(count)s zámků. |
   | `flash.ok.smart_locks_none_yet` | No shared lock yet. Send the eKey in the TTLock app, then check again. | Zatím žádný sdílený zámek. Odešlete eKey v aplikaci TTLock a zkontrolujte znovu. |
   | `flash.ok.smart_locks_removed` | TTLock connection removed. | Připojení TTLock odebráno. |
   | `flash.ok.smart_locks_removed_local` | Removed in UbyHost. TTLock did not answer, so also delete the eKeys in the TTLock app. | Odebráno v UbyHost. TTLock neodpověděl, smažte proto eKey i v aplikaci TTLock. |
   | `flash.error.smart_locks_unavailable` | Smart locks are not switched on. | Chytré zámky nejsou zapnuté. |
   | `flash.error.smart_locks_terms` | Accept the door code terms to continue. | Pro pokračování přijměte podmínky pro kódy ke dveřím. |
   | `flash.error.smart_locks_missing_account` | Set up smart locks first. | Nejdřív nastavte chytré zámky. |
   | `flash.error.smart_locks_failed` | TTLock did not answer. Try again in a few minutes. | TTLock neodpověděl. Zkuste to za pár minut. |
   | `flash.error.smart_locks_rate_limited` | Too many attempts. Try again in an hour. | Příliš mnoho pokusů. Zkuste to za hodinu. |
   | `flash.error.smart_locks_budget` | The monthly TTLock limit is nearly used. Try again next month. | Měsíční limit TTLock je téměř vyčerpán. Zkuste to příští měsíc. |
   | `flash.error.smart_locks_reauth` | TTLock no longer accepts this connection. Remove it and set it up again. | TTLock už toto připojení nepřijímá. Odeberte ho a nastavte znovu. |

   Use the existing convention for a literal percent sign (grep `%%` in `host_i18n.py`).
7. **Tests** (`App/tests/test_smart_locks_page.py`). Use `login_as` and a host user like `tests/test_settings_data_panel.py`. Monkeypatch the feature on (`config.DOOR_CODES_ENABLED`, `TTLOCK_CLIENT_ID`, `TTLOCK_CLIENT_SECRET`) and fake `ttlock.create_account`, `list_admin_locks`, `delete_account` (no network). Tests:
   - `test_page_and_tools_link_hidden_when_off` (404 or redirect with the unavailable error; no `/smart-locks` link on `/apartments`).
   - `test_tools_link_shows_under_property_tools_only` (present inside `host-tools` on `/apartments`; absent from `/settings` and the main sidebar).
   - `test_setup_requires_the_terms` (no `terms`: error, `create_account` not called).
   - `test_setup_creates_the_account_and_records_the_terms` (one `door_code_terms_accepted` audit row with the version; the page then shows the receiver name and the copy button).
   - `test_no_password_field_anywhere` (no `type="password"` on the page in any state).
   - `test_check_with_no_shared_lock_says_so`.
   - `test_check_with_locks_returns_to_the_property` (`return_to=/apartments/<id>#door-code` is honoured; an external `return_to` is ignored).
   - `test_list_shows_id_battery_property_and_timezone_warning`.
   - `test_remove_turns_codes_off_and_deletes_the_account` (and the TTLock-failure variant shows `smart_locks_removed_local`).
   - `test_each_host_sees_only_their_own_account`.
8. **Geometry.** In `App/tests/test_host_geometry.py` add `test_smart_locks_page_fits(base, width)` for 360, 390 and 1280: feature on via `monkeypatch` (same process), seed an account with two locks, open `/smart-locks?lang=en`, assert no horizontal overflow and equal heights for the Check and Remove buttons. Save screenshots of all three states at each width to `docs/tasks/0010-shots/`.

## 5. Do not touch

Everything outside §3. `settings.html` and the main navigation stay as they are. No property form change (task 0011).

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests -q` (all pass) and `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_geometry.py -q -rs` (0 skipped). From the repo root: `python3 scripts/context_lint.py` (last line `context lint: OK`).

## 7. Acceptance

- [ ] The 10 tests in step 7 and the geometry test pass. The full suite passes. Host geometry: 0 skipped.
- [ ] Screenshots of the three states at 360, 390 and 1280 px in `docs/tasks/0010-shots/`.
- [ ] The PR description states the outbound requests (TTLock user register, token, eKey list, user delete) and why (rule 2).
- [ ] `git diff --stat` shows only the files in §3 plus the screenshots.

## 8. Stop and ask

Stop, and write the report, if:

- a name or excerpt in §2 is not found;
- `safe_local_path` does not exist or behaves differently;
- a test fails twice;
- a new dependency seems needed;
- a file outside §3 needs a change;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/0010-report.md` (1,500 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/routes/admin.py` (the four handlers, `return_to` handling)
- `App/app/templates/smart_locks.html`

## Owner steps

After this PR is merged and deployed:

1. In the TTLock developer console, copy the `client_id`; tap **View** next to `client_secret` and copy it.
2. On the Lightsail server, add to `/opt/ubyhost/.env`:
   ```
   UBYHOST_TTLOCK_CLIENT_ID=<client_id>
   UBYHOST_TTLOCK_CLIENT_SECRET=<client_secret>
   UBYHOST_DOOR_CODES=1
   ```
3. Restart the app the way `docs/LIGHTSAIL.md` describes.
4. Properties → Property tools → Smart locks: tick the terms, tap **Set up**, send each lock's eKey to the shown account in the TTLock app, then tap **Check for locks**.
