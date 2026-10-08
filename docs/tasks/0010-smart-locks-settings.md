# 0010: Smart locks card in Settings

Status: todo
Depends on: 0009 | Base commit: after 0009 merges | Branch: task/0010-smart-locks-settings
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

Every host sees a "Smart locks" card in Settings once the owner has switched the feature on. There a host who has TTLock connects the TTLock account UbyHost may use (their own, or a separate one their locks are shared with), accepts the door-code terms, sees their locks with name, ID and battery, refreshes the list, or removes the connection. A host without TTLock simply never uses the card.

## 2. Context

- Plan: `docs/plans/ttlock-door-codes.md` §8.2 (account model) and §10 (the Settings sketch). Facts: `docs/TTLOCK.md` "Finding locks and codes".
- Client from task 0009 (`App/app/ttlock.py`): `connect(owner_user_id, username, password) -> int`, `list_admin_locks(account_id) -> List[dict]` (items `lock_id`, `alias`, `battery`, `tz_offset_ms`, `key_end`), `TTLockError` with `.kind`.
- Settings page: `settings_view` in `App/app/routes/admin.py` (about line 2710) renders `settings.html` with a context dict. Cards there look like:
  ```
  <div class="panel" id="settings-retention"><h2 style="margin-top:0">{{ t('settings.nav.retention') }}</h2><p class="small muted">...</p> ... </div>
  ```
  A destructive form uses `data-confirm data-confirm-message="{{ t('...') }}"` (see `settings.html` near line 121).
- POST handlers: start with `guard = auth.require_login(request)` and `if guard: return guard`, then end with `return _back("/settings#settings-...", msg=_flash(request, key))` or `err=...`. CSRF is checked by the router dependency (`security.protect_host_post`), and `static/csrf.js` adds the token to every form, so there is nothing to add for it.
- Owner id: `access.owner_id(request)`. Audit: `db.audit(action, detail)`; never put a username, password or token in `detail`.
- Rate limit (`App/app/rate_limit.py`): `rate_limit.blocked(scope, key, max_events)` and `rate_limit.record(scope, key)`.
- Host strings: `App/app/host_i18n.py`, `STRINGS["en"]` and `STRINGS["cs"]`, placeholders `%(name)s`. `tests/test_host_i18n.py::test_english_and_czech_carry_the_same_keys` must stay green. `tests/test_no_em_dashes.py` must stay green.
- Read `config.X` at call time inside functions (tests change config with `monkeypatch.setattr`), never copy it into a module-level constant.
- Rule 3: the password is used once, never stored, never logged, never echoed back into the form.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/ttlock.py` | edit | Steps 1 and 2 |
| `App/app/routes/admin.py` | edit | Steps 3 and 4 |
| `App/app/templates/settings.html` | edit | Step 5 |
| `App/app/host_i18n.py` | edit | Step 6 |
| `App/tests/test_smart_locks_settings.py` | create | Step 7 |
| `App/tests/test_host_geometry.py` | edit | Step 8, one test |

No other file may change.

## 4. Steps

1. **Terms version.** In `ttlock.py` add `DOOR_CODE_TERMS_VERSION = "2026-10-08"` (the date of the door-code terms in the Guide, task 0016).
2. **Gate.** In `ttlock.py` add:
   ```python
   def allowed_for(owner_user_id: Optional[int]) -> bool:
       """Door codes can be used: feature on and the app's TTLock credentials set."""
       return bool(
           config.DOOR_CODES_ENABLED and config.TTLOCK_CLIENT_ID and config.TTLOCK_CLIENT_SECRET
           and owner_user_id is not None
       )
   ```
   Also add `account_for(owner_user_id) -> Optional[Row]` returning the `lock_account` row for that owner and provider `ttlock`, and `locks_of(account) -> List[dict]` returning `json.loads(account["locks_json"] or "[]")`.
3. **Settings context.** In `settings_view`, add the key `smart_locks` to the context:
   - `None` when `not ttlock.allowed_for(owner_id)`.
   - Otherwise a dict: `{"account": row or None, "label": masked username, "locks": ttlock.locks_of(row) if row else [], "fetched_at": row["locks_fetched_at"] if row else None, "reauth": row is not None and row["status"] != "ok"}`.
   - Masked username: `mail.mask_email(username)` if it contains `@`, else the first 2 characters plus `•••`.
4. **Three POST handlers** in `admin.py`, near the other `/settings/*` handlers. Each: require login, return `_back("/settings", err=_flash(request, "flash.error.smart_locks_unavailable"))` if `not ttlock.allowed_for(owner_id)`.
   - `POST /settings/smart-locks/connect` (`smart_locks_connect`): read `username` and `password` (strip `username` only). Both required, else `err` `flash.error.smart_locks_missing`. The tick box `terms` must be `"1"`, else `err` `flash.error.smart_locks_terms`, before any TTLock call. Rate limit with scope `ttlock_connect`, key `f"user:{owner_id}"`, at most 5 per window: refuse with `flash.error.smart_locks_rate_limited` before calling TTLock, and `record` every attempt. Then `account_id = ttlock.connect(owner_id, username, password)` and `ttlock.list_admin_locks(account_id)`. On `TTLockError` with kind `login`: `flash.error.smart_locks_login`. Any other `TTLockError`: `flash.error.smart_locks_failed`. Success: `db.audit("smart_locks_connected", f"account={account_id}")`, `db.audit("door_code_terms_accepted", f"version={ttlock.DOOR_CODE_TERMS_VERSION}")`, and `msg` `flash.ok.smart_locks_connected`. Redirect to `/settings#settings-smart-locks` in every case.
   - `POST /settings/smart-locks/refresh` (`smart_locks_refresh`): needs an account (else `flash.error.smart_locks_missing_account`). Call `ttlock.list_admin_locks(account["id"])`. Kind `budget`: `flash.error.smart_locks_budget`. Kind `reauth`: `flash.error.smart_locks_reauth`. Other errors: `flash.error.smart_locks_failed`. Success: `flash.ok.smart_locks_refreshed`.
   - `POST /settings/smart-locks/remove` (`smart_locks_remove`): in one `with db.cursor() as cur:` block, set `lock_provider = NULL` on this owner's apartments (`WHERE owner_user_id = ?`) and delete the `lock_account` row. No TTLock call. `db.audit("smart_locks_removed", "")`, `msg` `flash.ok.smart_locks_removed`.
5. **The card** in `settings.html`, placed right after the `settings-ubyport` card, rendered only `{% if smart_locks %}`:
   ```
   <div class="panel" id="settings-smart-locks">
     <h2 style="margin-top:0">{{ t('settings.smart_locks.title') }}</h2>
     <p class="small muted">{{ t('settings.smart_locks.lede') }}</p>
     {% if not smart_locks.account %}
       <form method="post" action="/settings/smart-locks/connect" class="grid two">
         <div class="field"><label for="ttlock_username">{{ t('settings.smart_locks.username') }}</label>
           <input id="ttlock_username" name="username" autocomplete="off" required></div>
         <div class="field"><label for="ttlock_password">{{ t('settings.smart_locks.password') }}</label>
           <input id="ttlock_password" name="password" type="password" autocomplete="new-password" required></div>
         <div class="checkline" style="grid-column: 1 / -1"><input type="checkbox" id="ttlock_terms" name="terms" value="1" required><label for="ttlock_terms">{{ t('settings.smart_locks.terms') }} <a href="/guide#door-codes-terms">{{ t('settings.smart_locks.terms_link') }}</a></label></div>
         <div class="action-group"><button class="btn primary" type="submit">{{ t('settings.smart_locks.connect') }}</button></div>
       </form>
       <p class="small muted">{{ t('settings.smart_locks.password_note') }} <a href="/guide#door-codes">{{ t('settings.smart_locks.guide_link') }}</a></p>
     {% else %}
       {% if smart_locks.reauth %}<p class="small">{{ t('settings.smart_locks.reauth') }}</p>{% endif %}
       <p>{{ tp('settings.smart_locks.connected', smart_locks.locks | length, account=smart_locks.label) }}</p>
       {% if smart_locks.locks %}<ul class="small">{% for lock in smart_locks.locks %}
         <li>{{ lock.alias }} · {{ t('settings.smart_locks.lock_id', id=lock.lock_id) }}{% if lock.battery is not none %} · {{ t('settings.smart_locks.battery', percent=lock.battery) }}{% endif %}
           {% if lock.tz_offset_ms is not none and lock.tz_offset_ms != 3600000 %} · <strong>{{ t('settings.smart_locks.timezone_warning') }}</strong>{% endif %}</li>
       {% endfor %}</ul>{% else %}<p class="small muted">{{ t('settings.smart_locks.no_locks') }}</p>{% endif %}
       <div class="action-group">
         <form method="post" action="/settings/smart-locks/refresh"><button class="btn" type="submit">{{ t('settings.smart_locks.refresh') }}</button></form>
         <form method="post" action="/settings/smart-locks/remove" data-confirm data-confirm-message="{{ t('settings.smart_locks.remove_confirm') }}"><button class="btn danger" type="submit">{{ t('settings.smart_locks.remove') }}</button></form>
       </div>
     {% endif %}
   </div>
   ```
   If the settings page has an index or nav list of cards, add `settings-smart-locks` there in the same way, inside the same `{% if smart_locks %}`.
6. **Strings.** Add these keys to `STRINGS["en"]` and `STRINGS["cs"]` (next to the other `settings.*` and `flash.*` keys). `settings.smart_locks.connected` is plural: add `.one`, `.few` and the bare key, as other `tp` keys do.

   | Key | EN | CS |
   |---|---|---|
   | `settings.smart_locks.title` | Smart locks | Chytré zámky |
   | `settings.smart_locks.lede` | Optional. If your property has a TTLock lock with a gateway, UbyHost can send each guest a timed door code once everyone is registered. | Volitelné. Pokud má vaše ubytování zámek TTLock s bránou, UbyHost může každému hostovi poslat časově omezený kód ke dveřím, jakmile jsou všichni zaregistrováni. |
   | `settings.smart_locks.guide_link` | How to set it up | Jak to nastavit |
   | `settings.smart_locks.terms` | I have read and accept the door code terms. | Přečetl(a) jsem si podmínky pro kódy ke dveřím a souhlasím s nimi. |
   | `settings.smart_locks.terms_link` | Read the terms | Přečíst podmínky |
   | `settings.smart_locks.lock_id` | ID %(id)s | ID %(id)s |
   | `flash.error.smart_locks_terms` | Accept the door code terms to connect. | Pro připojení přijměte podmínky pro kódy ke dveřím. |
   | `settings.smart_locks.username` | TTLock e-mail or phone | E-mail nebo telefon TTLock |
   | `settings.smart_locks.password` | TTLock password | Heslo TTLock |
   | `settings.smart_locks.connect` | Connect | Připojit |
   | `settings.smart_locks.password_note` | The password is used once to connect and is not stored. | Heslo se použije jednou k připojení a neukládá se. |
   | `settings.smart_locks.connected.one` | Connected as %(account)s · %(count)s lock | Připojeno jako %(account)s · %(count)s zámek |
   | `settings.smart_locks.connected.few` | Connected as %(account)s · %(count)s locks | Připojeno jako %(account)s · %(count)s zámky |
   | `settings.smart_locks.connected` | Connected as %(account)s · %(count)s locks | Připojeno jako %(account)s · %(count)s zámků |
   | `settings.smart_locks.battery` | battery %(percent)s %% | baterie %(percent)s %% |
   | `settings.smart_locks.timezone_warning` | Time zone is not Prague. Fix it in the TTLock app. | Časové pásmo není Praha. Opravte ho v aplikaci TTLock. |
   | `settings.smart_locks.no_locks` | This account has no lock it may manage. Add the lock in the TTLock app, or share it with this account as Authorized admin. | Tento účet nemá žádný zámek, který smí spravovat. Přidejte zámek v aplikaci TTLock, nebo ho s tímto účtem sdílejte jako Autorizovaný správce. |
   | `settings.smart_locks.reauth` | TTLock no longer accepts this connection. Remove it and connect again. | TTLock už toto připojení nepřijímá. Odeberte ho a připojte znovu. |
   | `settings.smart_locks.refresh` | Refresh lock list | Obnovit seznam zámků |
   | `settings.smart_locks.remove` | Remove | Odebrat |
   | `settings.smart_locks.remove_confirm` | Remove the TTLock connection? Door codes stop for all your properties. | Odebrat připojení TTLock? Kódy ke dveřím se vypnou u všech vašich ubytování. |
   | `flash.ok.smart_locks_connected` | TTLock connected. | TTLock připojen. |
   | `flash.ok.smart_locks_refreshed` | Lock list refreshed. | Seznam zámků obnoven. |
   | `flash.ok.smart_locks_removed` | TTLock connection removed. | Připojení TTLock odebráno. |
   | `flash.error.smart_locks_unavailable` | Smart locks are not available for this account. | Chytré zámky nejsou pro tento účet k dispozici. |
   | `flash.error.smart_locks_missing` | Enter the TTLock e-mail or phone and the password. | Zadejte e-mail nebo telefon TTLock a heslo. |
   | `flash.error.smart_locks_missing_account` | Connect a TTLock account first. | Nejdřív připojte účet TTLock. |
   | `flash.error.smart_locks_login` | TTLock did not accept this login. | TTLock toto přihlášení nepřijal. |
   | `flash.error.smart_locks_failed` | TTLock did not answer. Try again in a few minutes. | TTLock neodpověděl. Zkuste to za pár minut. |
   | `flash.error.smart_locks_rate_limited` | Too many attempts. Try again in an hour. | Příliš mnoho pokusů. Zkuste to za hodinu. |
   | `flash.error.smart_locks_budget` | The monthly TTLock limit is nearly used. The lock list refreshes again next month. | Měsíční limit TTLock je téměř vyčerpán. Seznam zámků půjde obnovit příští měsíc. |
   | `flash.error.smart_locks_reauth` | TTLock no longer accepts this connection. Remove it and connect again. | TTLock už toto připojení nepřijímá. Odeberte ho a připojte znovu. |

   If `%%` is not how host strings write a literal percent sign, follow the existing convention (grep `host_i18n.py` for `%%`).
7. **Tests** (`App/tests/test_smart_locks_settings.py`). Use `login_as` from `tests/conftest.py` and a host user like other settings tests (`tests/test_settings_data_panel.py`). Monkeypatch `config.DOOR_CODES_ENABLED`, `config.TTLOCK_CLIENT_ID`, `config.TTLOCK_CLIENT_SECRET`, and monkeypatch `ttlock.connect` and `ttlock.list_admin_locks` (no network). Every connect post sends `terms=1` unless the test says otherwise. Tests:
   - `test_card_hidden_when_feature_off`: `id="settings-smart-locks"` absent.
   - `test_card_shows_the_connect_form_when_allowed`.
   - `test_connect_redirects_with_success_and_never_echoes_the_password`: the response and the following settings page do not contain the password; `caplog.text` does not contain it; an `audit` row `smart_locks_connected` exists and its `detail` holds no username.
   - `test_wrong_login_shows_the_login_error` (fake raises `TTLockError(kind="login")`).
   - `test_sixth_attempt_is_refused_without_calling_ttlock`.
   - `test_connected_card_lists_locks_and_warns_on_wrong_time_zone` (seed `lock_account` with `locks_json` of two locks, one with `tz_offset_ms` 28800000).
   - `test_remove_deletes_the_account_and_turns_door_codes_off` (seed an apartment with `lock_provider='ttlock'`; after remove it is NULL and the account row is gone).
   - `test_connect_requires_the_terms` (no `terms`: the terms error, `ttlock.connect` not called); with `terms=1`, an audit row `door_code_terms_accepted` with the version.
   - `test_each_host_sees_only_their_own_account` (two hosts, each with a seeded account: each settings page lists only its own locks).
8. **Geometry.** In `App/tests/test_host_geometry.py` add `test_smart_locks_card_fits(base, width)` parametrized with `width` 360, 390 and 1280, in the style of `test_dashboard_actions_share_height_and_gap`: enable the feature with `monkeypatch` (the server runs in the same process), seed a connected account with two locks, open `/settings?lang=en`, and assert that `document.documentElement.scrollWidth <= window.innerWidth` and that the Refresh and Remove buttons have equal height. Save a screenshot of the card at each width to `docs/tasks/0010-shots/` (create the folder) and list them in the report.

## 5. Do not touch

Everything outside §3. `App/app/ttlock.py` beyond the three small functions in step 2. No apartment form change (task 0011). No scheduler, guest page or mail change.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests -q` (all pass), and `.venv/bin/python -m pytest tests/test_host_geometry.py -q -rs` (0 skipped; set `UBYHOST_REQUIRE_BROWSER=1` so a missing browser fails instead of skipping). From the repo root: `python3 scripts/context_lint.py` (last line `context lint: OK`).

## 7. Acceptance

- [ ] The 9 tests in step 7 and the geometry test pass. The full suite passes. Host geometry: 0 skipped.
- [ ] Screenshots at 360, 390 and 1280 px in `docs/tasks/0010-shots/`.
- [ ] `grep -rn "password" App/app/routes/admin.py` shows no log call that includes the password.
- [ ] `git diff --stat` shows only the files in §3 plus the screenshots.

## 8. Stop and ask

Stop, and write the report, if:

- a name in §2 is not found;
- a test fails twice;
- the settings page has no obvious place for the card after `settings-ubyport`;
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

- `App/app/routes/admin.py` (the three handlers and the `settings_view` addition)
- `App/app/templates/settings.html` (the card)

## Owner steps

Do these after this PR is merged and deployed.

1. In the TTLock developer console, copy the `client_id`. Tap **View** next to `client_secret` and copy it.
2. On the Lightsail server, open `/opt/ubyhost/.env` and add:
   ```
   UBYHOST_TTLOCK_CLIENT_ID=<client_id>
   UBYHOST_TTLOCK_CLIENT_SECRET=<client_secret>
   UBYHOST_DOOR_CODES=1
   ```
3. Restart the app the way `docs/LIGHTSAIL.md` describes.
4. Follow the Guide section "Door codes with TTLock" (task 0016) to connect.
