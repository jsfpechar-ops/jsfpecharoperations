# 0396: Leon (AI) card on the property overview, with warnings and terms the host accepts first

Status: review
Depends on: main (0376, 0393 merged) | Branch: claude/0396-leon-card-legal-opt-in (checked out; commit here)
Executor: Haiku 5.5 | Reviewer: Opus | Fits one session: 40 tool calls, 90k tokens

## 1. Objective

Owner (Josef, 2026-10-25): Leon's switch is "really difficult to find" (it sits at the bottom of the Guest guide tab). He wants it on the property **Overview** grid of cards (Connected calendars, Guest links, Police reporting, Digital door lock ...), "optional of course, with all warning and legal they have to accept before using, like TTLock". Legal copy was written by an Opus legal-counsel pass (§4 Copy).

1. New optional **"Leon (AI)" card** on the property Overview grid, shown only where Leon is offered (`ai.enabled_for_property(leon.FEATURE, id)`, i.e. `leon` in `UBYHOST_AI_FEATURES`, a key, and the owner on `UBYHOST_AI_TEST_EMAILS` when set). Status line: Off / On / On, starts when the guide is live / Terms updated, accept again. Opens the new Leon page.
2. New page **`/apartments/{id}/leon`** ("Leon (AI)"): what Leon does, the warnings, one required checkbox accepting the versioned Leon terms (link to `/guide#leon-terms`), primary button "Switch Leon on". When on: who accepted which version when, and "Switch Leon off".
3. **Acceptance stored** on the property (version, UTC time, user id) plus an audit row, like TTLock's `door_code_terms_accepted`.
4. **Leon only answers when the accepted version is the current one.** `leon.switched_on` checks it, so bumping `LEON_TERMS_VERSION` later turns Leon off everywhere until each host accepts again.
5. The Guest guide tab's Leon section loses its toggle: it keeps one status line and a link to the Leon page (one place for the switch, rules.md copy rule 9).
6. The help guide gets the Leon terms section `#leon-terms` (en, cs), like `#door-codes-terms`.

Off is always allowed. With no env change nothing shows on production for hosts not on the test list.

## 2. Context (read only these)

- TTLock pattern to mirror: `App/app/templates/_smart_locks_panel.html` (checkbox `terms` required + link to `/guide#door-codes-terms`), `App/app/routes/admin.py` `smart_locks_setup` (~594-621: rejects without `terms == "1"`, then `db.audit("door_code_terms_accepted", f"version={ttlock.DOOR_CODE_TERMS_VERSION}")`), `App/app/ttlock.py:18` `DOOR_CODE_TERMS_VERSION = "2026-10-12"`, `App/app/templates/guide.html:276-278` (terms section), `App/app/guide_i18n.py` keys `guide.door_codes.terms_title`, `terms_version`, `terms1..9` (en ~57, cs ~421).
- Leon gate: `App/app/leon.py` ~428 `switched_on(apartment)`; `FEATURE`.
- Current switch: `App/app/routes/guest_guide.py` `guide_index` (context `leon_offer`, `leon_on`) and POST `guide_leon` (`/apartments/{id}/guide/leon`); template `App/app/templates/guest_guide.html` lines 39-49.
- Page pattern: `guest_guide.html` extends `host_page.html` (blocks `title`, `page_title`, `back_url`, `back_label`, `meta`, `primary_action`, `body`); route helpers `_home`, `_render` in `routes/guest_guide.py`. Macros in `App/app/templates/_ui.html`: `ui_section`, `ui_button`, `ui_banner`, `ui_check(id, label, name, ...)`. **Exactly one primary button per page** (design tests).
- Overview grid: `App/app/templates/_property_overview.html` (`host-property-grid`, cards `host-property-card`, `open_pill`, icons from `_icons.html`; use `message-circle-question`). Context built in `App/app/routes/admin.py` ~1841-1860 (`render(request, "apartment_form.html", {...})`).
- Copy: host strings `App/app/host_i18n.py` (en block ~8511, cs ~8546, `guest_guide.leon.*`), Vietnamese `App/app/host_vi_i18n.py` (~188). Help-guide strings `App/app/guide_i18n.py` (en, cs only).
- Migrations: last is `0021_leon_opt_in.sql`. New: `0022_leon_terms.sql`.
- Retention: `App/app/retention.py`. New fields hold a user id, so add a line where apartment fields are listed (grep `leon_enabled` / `apartment` there; if apartment columns are not listed one by one, add a comment line under the existing apartment entry).
- Tests that set `leon_enabled = 1` and expect Leon on: `test_guest_leon_chat.py:39`, `test_guest_leon_browser.py:33`, `test_privacy_first.py:212`, `test_leon.py:35`, `test_0376_ai_gates.py` (76, 106, 117). They must also set `leon_terms_version` to `leon.LEON_TERMS_VERSION`.
- Rules: `docs/context/rules.md` (copy, guest pages), `scripts/design_lint.py` (a new CSS class must be in `docs/design/catalog.json`: prefer existing classes, no new CSS).

## 3. Files

| Path | Action |
|---|---|
| App/app/migrations/0022_leon_terms.sql | new |
| App/app/leon.py | `LEON_TERMS_VERSION`, `terms_current(apartment)`, `switched_on` checks it |
| App/app/routes/guest_guide.py | GET+POST `/apartments/{id}/leon`; drop POST `/guide/leon`; guide context `leon_state` |
| App/app/templates/leon_settings.html | new page |
| App/app/templates/_property_overview.html | Leon card |
| App/app/routes/admin.py | overview context `leon_card` |
| App/app/templates/guest_guide.html | Leon section: status line + link |
| App/app/templates/guide.html | `#leon-terms` section |
| App/app/host_i18n.py, App/app/host_vi_i18n.py, App/app/guide_i18n.py | copy (§4 Copy) |
| App/app/retention.py | one line for the acceptance fields |
| App/tests/test_0396_leon_opt_in.py | new |
| App/tests/test_0396_leon_opt_in_browser.py | new (390 px screenshots) |
| tests listed in §2 | set `leon_terms_version` |
| App/tests/test_0376_ai_gates.py | tests of `/guide/leon` move to the new route |

## 4. Steps

1. `0022_leon_terms.sql`:
   ```sql
   -- Brief 0396: which Leon (AI) terms the host accepted for this property, when and who.
   ALTER TABLE apartment ADD COLUMN leon_terms_version TEXT;
   ALTER TABLE apartment ADD COLUMN leon_terms_accepted_at TEXT;
   ALTER TABLE apartment ADD COLUMN leon_terms_accepted_by INTEGER;
   ```
2. `leon.py`, above `switched_on`:
   ```python
   # 0396: the host accepts these terms before Leon answers (text: guide_i18n guide.leon_terms.*).
   # Changing the date turns Leon off on every property until its host accepts again.
   LEON_TERMS_VERSION = "2026-10-25"


   def terms_current(apartment) -> bool:
       return (apartment["leon_terms_version"] or "") == LEON_TERMS_VERSION
   ```
   and `switched_on` returns `bool(apartment["leon_enabled"]) and terms_current(apartment) and ai.owner_on_test_list(...)` (update its docstring: "0376/0396").
3. `routes/guest_guide.py`:
   - Helper `_leon_state(apartment) -> str`: `"off"` if not `leon_enabled`; `"terms"` if on but not `leon.terms_current`; `"waiting"` if on and the guide is not live (`guest_guide.progress(id)["live"]`); else `"on"`.
   - `GET /apartments/{apartment_id}/leon` (`leon_page`): login guard, `_home`; 404 if not `ai.enabled_for_property(leon.FEATURE, apartment_id)`. Render `leon_settings.html` with `apartment`, `state=_leon_state(apartment)`, `terms_version=leon.LEON_TERMS_VERSION`, `accepted_at` (the stored ISO time, shown as `YYYY-MM-DD HH:MM UTC`), `accepted_by` (that user's e-mail via `db.query_one("SELECT email FROM user_account WHERE id = ?", ...)`, or ""), `live`, `usage` (same as `guide_index`).
   - `POST /apartments/{apartment_id}/leon` (`leon_save`), registered **above** the `/apartments/{id}/guide/{item_id}` routes: login guard, `_home`, form. `action == "off"`: `UPDATE apartment SET leon_enabled = 0`, `db.audit("leon_switched_off", f"apartment={id}")`, flash `flash.guest_guide.leon_off`. `action == "on"`: 404 if not offered; if `form.get("terms") != "1"` back to the page with `err=flash(request, "flash.error.leon_terms")`; else one UPDATE setting `leon_enabled = 1, leon_terms_version = ?, leon_terms_accepted_at = db.utcnow(), leon_terms_accepted_by = <current user id>` (use what `smart_locks_setup` / `auth.current_user(request)` gives; the signed-in user, not the owner, since a team member may accept), then `db.audit("leon_terms_accepted", f"apartment={id} version={leon.LEON_TERMS_VERSION}")`, flash `flash.guest_guide.leon_on`. Redirect `back(f"/apartments/{id}/leon", ...)`. Any other action: back to the page.
   - Delete the old `guide_leon` route. In `guide_index` replace `leon_on=` with `leon_state=_leon_state(apartment)` (keep `leon_offer`).
4. `leon_settings.html` (extends `host_page.html`, `body_kind = 'list'`): title "Leon (AI)", back to `/apartments/{id}` with the property name, `meta` = the state text (`leon_page.card.<state>`).
   - State `off` or `terms`: if `terms`, `ui_banner('attention', leon_page.terms_updated)`. Section "What Leon does" (`leon_page.what`, one paragraph). Section "Before you switch on" (`leon_page.warn_title`): `<ul>` of the warnings `leon_page.warn1..N`. A form `method=post` with `_csrf`, hidden `action=on`, `ui_check('leon-terms', ..., name='terms', attrs='required')` whose label is `leon_page.accept` followed by a link `<a href="/guide#leon-terms">{{ t('leon_page.terms_link') }}</a>` (mirror `_smart_locks_panel.html`: plain `<div class="checkline">` markup like there is fine), then the one primary `ui_button(t('leon_page.switch_on'), 'primary', type='submit')`. If the guide is not live, under the form: `leon_page.not_live` with a link to `/apartments/{id}/guide`.
   - State `on` or `waiting`: `ui_banner('neutral', leon_page.on_banner)` (or `leon_page.waiting_banner` + link to the guide). A short `<dl class="kv">`: terms version, accepted at, accepted by. The usage line if any (`guest_guide.usage.leon`). Link "Edit the guest guide Leon answers from" (`leon_page.edit_guide`) to `/apartments/{id}/guide`. A form with hidden `action=off`, `data-confirm data-confirm-message="{{ t('leon_page.off_confirm') }}"`, `ui_button(t('leon_page.switch_off'), 'secondary', type='submit')`. No primary button in this state is fine.
5. Overview card: in `admin.py` context add `"leon_card": _leon_card(apartment)` where it returns `None` unless `ai.enabled_for_property(leon.FEATURE, apartment["id"])`, else the `_leon_state` value (import the helper from `routes/guest_guide.py` or move it to `leon.py` as `host_state(apartment)` and use it in both places; prefer `leon.py`). In `_property_overview.html`, after the door-lock card:
   ```jinja
   {% if leon_card %}
   <a class="host-property-card" href="{{ base_url }}/leon" data-leon-card="{{ leon_card }}">{{ icon('message-circle-question', 20) }}<div><strong>{{ t('leon_page.title') }}</strong>
     <small>{{ t('leon_page.card.' ~ leon_card) }}</small></div>{{ open_pill }}</a>
   {% endif %}
   ```
   Check that `apartment` in this context has the new columns (it is a full row; if it is a dict built by hand, add them).
6. `guest_guide.html` Leon section (keep `id='leon'`, `leon_offer` guard): drop the form and toggle; show `<p class="ui-sub">{{ t('leon_page.card.' ~ leon_state) }}</p>` and `{{ ui_button(t('guest_guide.leon.open'), 'secondary', href='/apartments/' ~ apartment.id ~ '/leon') }}`. Remove keys `guest_guide.leon.toggle`, `guest_guide.leon.save`, `guest_guide.leon.waiting` from en/cs/vi only if nothing else uses them (grep).
7. `guide.html`: right after the door-codes terms section (after line ~279 `</section>`), a new `<section class="guide-section ui-section ui-section-plain" id="leon-terms">` with `<h2>{{ t('guide.leon_terms.title') }}</h2>`, `<p class="ui-sub">{{ t('guide.leon_terms.version', version='2026-10-25') }}</p>`, `<ol>` of `guide.leon_terms.terms1..N`. If the guide has a side nav listing sections (grep `guide.nav.`), add an entry only if every other terms block has one (door-code terms is an `h3` inside a section without its own nav entry; then also make Leon's an `h3` inside the closest AI/guest-guide section if one exists, else its own section without nav).
8. Copy from the Copy section into en and cs (`host_i18n.py`, `guide_i18n.py`); Vietnamese host strings into `host_vi_i18n.py` (translate the host strings yourself, plain and short; the guide terms stay en/cs since `guide_i18n` has no vi).
9. `retention.py`: (a) one line saying `apartment.leon_terms_accepted_by` / `_at` / `_version` are kept while the property exists (proof of the host's acceptance), deleted with the property/account; follow the neighbouring format. (b) Acceptance evidence must not expire after 3 years (legal note part 4): in `_audit_retention_step` change `action NOT IN ('legal_accepted')` to `action NOT IN ('legal_accepted', 'door_code_terms_accepted', 'leon_terms_accepted')` and extend its docstring by one sentence. Add a test in `test_0396_leon_opt_in.py` that an old `leon_terms_accepted` audit row survives the step while an old ordinary row is deleted (copy the pattern from the existing retention tests: grep `_audit_retention_step` in tests).
10. Tests `test_0396_leon_opt_in.py` (copy fixtures from `test_0376_ai_gates.py`):
    - Card absent when Leon not offered (feature off, or owner not on the test list); present with `data-leon-card="off"` when offered.
    - GET `/apartments/{id}/leon` 404 when not offered; 200 and contains `/guide#leon-terms` and one `ui-btn-primary` when offered and off.
    - POST `action=on` without `terms` -> Leon stays off, nothing stored. With `terms=1` -> `leon_enabled=1`, version = `LEON_TERMS_VERSION`, `accepted_at` set, `accepted_by` = the user id, one audit row `leon_terms_accepted`.
    - `leon.switched_on` false when `leon_terms_version` is an older string, true with the current one; card shows `terms` state then.
    - POST `action=off` -> `leon_enabled=0`, acceptance fields kept, audit `leon_switched_off`.
    - Old route `POST /apartments/{id}/guide/leon` no longer switches Leon on (404 or 405).
    - `/guide` contains `id="leon-terms"` in en and cs.
11. `test_0396_leon_opt_in_browser.py` (`sync_api = pytest.importorskip("playwright.sync_api")`, copy the server fixture from `test_guest_leon_browser.py` or the closest host browser test): at 390 px save screenshots to `docs/tasks/screenshots-0396/`: `overview-card-390.png` (overview grid with the Leon card, scrolled to it), `leon-off-390.png`, `leon-on-390.png`; plus `leon-off-1280.png`. Assert no horizontal overflow (`document.documentElement.scrollWidth <= innerWidth`).
12. Update the tests in §2 to set `leon_terms_version` alongside `leon_enabled = 1`.

### Copy (step 8)

The legal note is `docs/privacy/LEON_LEGAL.md` (Opus legal counsel, 2026-10-25). Take text from it **verbatim**:

- `leon_page.warn1`..`warn6` (en, cs): part 1, the six bullets, in order.
- `guide.leon_terms.terms1`..`terms12` (en, cs): part 3. `guide.leon_terms.title`: "Leon (AI) terms" / "Podmínky pro Leona (AI)". `guide.leon_terms.version`: copy the format of `guide.door_codes.terms_version` (same placeholder name).

Host strings (en / cs; translate to vi in `host_vi_i18n.py`):

| key | en | cs |
|---|---|---|
| `leon_page.title` | Leon (AI) | Leon (AI) |
| `leon_page.what` | Leon is an optional AI chat for your guests. He answers their questions on the stay page and the QR guide page from your guide cards marked Done, and passes anything he does not know to you. | Leon je volitelný AI chat pro vaše hosty. Odpovídá na jejich otázky na stránce pobytu a na stránce průvodce z QR kódu podle karet označených Hotovo a vše, co neví, předá vám. |
| `leon_page.what_title` | What Leon does | Co Leon dělá |
| `leon_page.warn_title` | Before you switch Leon on | Než Leona zapnete |
| `leon_page.accept` | I accept the Leon (AI) terms (version 2026-10-25) for this property. I stay responsible for my guide and for what my guests are told. | Souhlasím s podmínkami pro Leona (AI) (verze 2026-10-25) pro toto ubytování. Za svého průvodce a za to, co se hosté dozvědí, odpovídám já. |
| `leon_page.terms_link` | Read the terms | Přečíst podmínky |
| `leon_page.switch_on` | Switch Leon on | Zapnout Leona |
| `leon_page.switch_off` | Switch Leon off | Vypnout Leona |
| `leon_page.off_confirm` | Switch Leon off for this property? Guests will no longer see him. | Vypnout Leona pro toto ubytování? Hosté ho už neuvidí. |
| `leon_page.not_live` | Leon starts answering once your guest guide is live. | Leon začne odpovídat, jakmile bude váš průvodce pro hosty zveřejněný. |
| `leon_page.guide_link` | Open the guest guide | Otevřít průvodce pro hosty |
| `leon_page.on_banner` | Leon is answering your guests on this property. | Leon odpovídá vašim hostům v tomto ubytování. |
| `leon_page.waiting_banner` | Leon is on and starts once your guest guide is live. | Leon je zapnutý a začne, jakmile bude průvodce pro hosty zveřejněný. |
| `leon_page.terms_updated` | The Leon terms have changed. Leon is paused here until you accept the new version. | Podmínky pro Leona se změnily. Leon je tu pozastavený, dokud nepřijmete novou verzi. |
| `leon_page.accepted_title` | Terms accepted | Přijaté podmínky |
| `leon_page.accepted_version` | Version | Verze |
| `leon_page.accepted_at` | Accepted | Přijato |
| `leon_page.accepted_by` | By | Kým |
| `leon_page.edit_guide` | Edit the guide Leon answers from | Upravit průvodce, ze kterého Leon odpovídá |
| `leon_page.card.off` | Off | Vypnuto |
| `leon_page.card.on` | On | Zapnuto |
| `leon_page.card.waiting` | On, starts when the guide is live | Zapnuto, začne po zveřejnění průvodce |
| `leon_page.card.terms` | Terms changed, accept again | Podmínky se změnily, přijměte je znovu |
| `guest_guide.leon.open` | Leon settings | Nastavení Leona |
| `flash.error.leon_terms` | Tick the box to accept the Leon terms first. | Nejdřív zaškrtněte souhlas s podmínkami pro Leona. |

Keep `guest_guide.leon.title`, `guest_guide.leon.help`, `flash.guest_guide.leon_on`, `flash.guest_guide.leon_off`.

## 5. Do not touch

Guest chat pages (`templates/guest/`, `guest-leon.js`), `leon.py` CHARACTER and the AI call path, the legal note text.

## 6. Commands

From `App/`:
```
.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 | tail -5
.venv/bin/python -m pytest tests/test_0396_leon_opt_in.py tests/test_0376_ai_gates.py tests/test_leon.py tests/test_guest_leon_chat.py tests/test_privacy_first.py tests/test_guest_guide*.py tests/test_design_*.py -q --tb=short 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_0396_leon_opt_in_browser.py tests/test_guest_leon_browser.py -q --tb=short 2>&1 | tail -15
```
From repo root: `python3 scripts/design_lint.py | tail -5`, `python3 scripts/context_lint.py | tail -5`. Then `git checkout -- docs/tasks/screenshots-0*` for folders other than `screenshots-0396`.

## 7. Acceptance

- The Leon card shows on the Overview grid only where Leon is offered, and opens `/apartments/{id}/leon`.
- Leon cannot be switched on without ticking the terms; acceptance version, time and user are stored and audited.
- Leon answers only with the current terms version accepted; the old guide toggle is gone.
- All commands in §6 pass with 0 skipped; screenshots in `docs/tasks/screenshots-0396/`.

## 8. Stop and ask

If a design test needs a new CSS class or a second primary button, or the overview `apartment` row lacks the new columns and fixing it means touching unrelated code.

## 9. Report

Write `docs/tasks/0396-report.md`: what changed, test output tails, screenshot paths. Commit (do not push).
