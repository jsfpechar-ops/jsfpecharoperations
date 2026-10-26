# 0404: Leon setup wizard (switch on, import, check cards, try, done)

Status: review
Depends on: 0403 (same branch) | Branch: claude/0403-leon-setup-wizard (checked out; commit here)
Executor: Haiku 5.5 | Reviewer: Opus | Fits one session: 40 tool calls, 100k tokens
Followed by: 0405 fills the "try" step with the test chat. This brief renders that step as a placeholder.

## 1. Objective

Owner (Josef, 2026-10-25): "make it like a wizard like the onboarding one, walk them through it, support them". When a host activates Leon, the very first thing after the terms is the Booking/Airbnb import.

A wizard at `/apartments/{id}/leon/setup/{step}` that looks and behaves like the property setup wizard (`setup_wizard/_layout.html`): progress dots, one question per page, Back on the left, the one primary action on the right, Exit at the top.

Steps, in order (`leon.SETUP_STEPS`):

| step | page shows | done when |
|---|---|---|
| `switch_on` | what Leon does, the six warnings, the terms checkbox; primary "Switch Leon on" | `leon.host_state` is `on` or `waiting` |
| `import` | the two-link import form (0403), then "Importing…" while running, then the result | at least one import row not `failed`, or imports off, or host pressed "Fill by hand" |
| `cards` | must-haves done x of 5, the cards still needing the host (Check this / Missing), primary "Check the next card"; Quick answers link | `guest_guide.progress(id)["live"]` and no card in `check` |
| `try` | (0405) test chat; here a placeholder paragraph and primary "Finish" | host pressed Finish |
| `done` | celebration, links: QR guide page, guest guide, Leon settings | — |

Entry points: the Overview "Leon (AI)" card opens `/apartments/{id}/leon/setup` until Leon is fully on (state `off`, `terms` or `waiting`), and `/apartments/{id}/leon` once `on`. `GET /apartments/{id}/leon` in state `off` or `terms` redirects (303) to the wizard, so the terms form lives in one place.

## 2. Context (read only these)

- Look and markup to mirror: `App/app/templates/setup_wizard/_layout.html` (classes `setup-wizard`, `setup-wizard-head`, `setup-wizard-meter`, `setup-wizard-progress` with `li.is-done` / `is-current`, `setup-wizard-done-count`, `setup-wizard-exit`, `setup-wizard-body`, `setup-wizard-ask`, `setup-wizard-ask-icon`, `setup-wizard-question`, `setup-wizard-lede`, `setup-wizard-instruction`, `setup-wizard-foot`, `setup-wizard-back`, `setup-wizard-skip`), `setup_wizard/done.html` (`setup-wizard-celebrate`, `-mark`, `-copy`, `-title`, `setup-wizard-confetti`). All are in `App/app/static/wizard.css`, loaded on every host page. **Use only existing classes** (design lint); for JS hooks use `data-*`.
- Current Leon page and POST: `App/app/routes/guest_guide.py` `leon_page`, `leon_save` (~95-140), `leon_card_state`; template `App/app/templates/leon_settings.html` (warnings loop `leon_page.warn1..6`, checkbox `#leon-terms`).
- `App/app/leon.py` `host_state`, `terms_current`, `FEATURE`.
- Import module (after 0403): `guest_guide_import.enabled`, `sources_left`, `imports_left`, `in_progress`, `imports`; `guest_guide_merge.drafted_count`.
- Guide: `guest_guide.progress`, `guest_guide.items`, `guest_guide.MUST_HAVE`; `routes/guest_guide.py` `_next_open`, `guide_card_save` (~330-350, the `then == "next"` redirect), template `App/app/templates/guest_guide_card.html` (save form ~44-56).
- Overview card: `App/app/templates/_property_overview.html` ~58 (`href="{{ base_url }}/leon"`).
- Icons: `{% from "_icons.html" import icon with context %}`, names `message-circle-question`, `download`, `book-open`, `send`.
- Routers: `App/app/main.py` ~359 `app.include_router(guest_guide_routes.router)`. Route helpers `_home`, `_render` in `routes/guest_guide.py`.
- Copy: `App/app/host_i18n.py` en `leon_page.*` (~8531), cs (~8594); Vietnamese `App/app/host_vi_i18n.py` (~190, `leon_page.*` exist there).
- Browser test pattern: `App/tests/test_0396_leon_opt_in_browser.py` (fixtures `leon_offered`, `live_server`, `browser`, `host`, `base`, `_no_overflow`); unit pattern: `App/tests/test_0396_leon_opt_in.py`.

## 3. Files

| Path | Action |
|---|---|
| App/app/leon.py | `SETUP_STEPS`, `setup_step(apartment, ...)` helper |
| App/app/routes/leon_setup.py | new router: GET `/leon/setup`, GET `/leon/setup/{step}`, POST `/leon/setup` |
| App/app/main.py | include the router (before `guest_guide_routes.router`) |
| App/app/routes/guest_guide.py | `leon_page` redirect for off/terms; `leon_save` `next=setup`; `guide_card` / `guide_card_save` keep `from=leon` |
| App/app/templates/leon_setup/_layout.html | new |
| App/app/templates/leon_setup/switch_on.html, import.html, cards.html, try.html, done.html | new |
| App/app/templates/guest_guide_card.html | hidden `from` field |
| App/app/templates/_property_overview.html | card href |
| App/app/static/leon-setup.js | new: reload the import step every 10 s while it waits |
| App/app/host_i18n.py, App/app/host_vi_i18n.py | copy |
| App/tests/test_0404_leon_setup.py, App/tests/test_0404_leon_setup_browser.py | new |
| App/tests/test_0396_leon_opt_in.py, App/tests/test_0396_leon_opt_in_browser.py | adjust to the redirect |

## 4. Steps

1. `leon.py`, below `host_state`:
   ```python
   # 0404: the Leon setup wizard, in order. "done" is the finish page, not a step.
   SETUP_STEPS = ("switch_on", "import", "cards", "try")


   def setup_step(apartment, *, live: bool, checking: int, import_started: bool, import_on: bool) -> str:
       """The first step the host still has to do; "try" once everything else is ready."""
       if host_state(apartment, live) in ("off", "terms"):
           return "switch_on"
       if import_on and not import_started and not live:
           return "import"
       if not live or checking:
           return "cards"
       return "try"
   ```
2. `routes/leon_setup.py` (copy the header style of `routes/guest_guide.py`; `router = APIRouter(dependencies=[Depends(security.protect_host_post)])`). Helpers:
   - `_facts(apartment_id)` -> dict: `progress` (`guest_guide.progress`), `live`, `checking` (= progress["check"]), `import_on` (`guest_guide_import.enabled()`), `imports` (`guest_guide_import.imports(id)`), `import_started` (any import row whose status is not `failed`), `import_busy` (`in_progress`), `sources` (`sources_left`), `drafts` (`guest_guide_merge.drafted_count`), `open_cards` (rows of `guest_guide.items(id)` with state `check`, or state `missing` and kind in `MUST_HAVE`; in guest order).
   - "Fill by hand" on the import step is stateless: POST `/apartments/{id}/leon/setup` with `action=skip_import` redirects straight to `/leon/setup/cards`; the GET of `import` stays reachable by Back. `setup_step` therefore only sends a host to `import` from the `/leon/setup` entry, never forces it.
   - `GET /apartments/{apartment_id}/leon/setup`: login guard, `_home` (import from `.guest_guide`), 404 unless `ai.enabled_for_property(leon.FEATURE, id)`; redirect 303 to `/apartments/{id}/leon/setup/{leon.setup_step(...)}`.
   - `GET /apartments/{apartment_id}/leon/setup/{step}`: same guards; `step` must be in `SETUP_STEPS + ("done",)` else 404. A host who is not switched on (`host_state` off/terms) and asks for any step other than `switch_on` is redirected to `switch_on`. Render `leon_setup/<step>.html` with: `apartment`, `step`, `steps=SETUP_STEPS`, `number` (1-based index; `done` has none), `total=4`, `prev_step` (previous step name or None), `done_steps` (set of steps already done, by the table in §1: `switch_on` when state on/waiting; `import` when `import_started` or not `import_on`; `cards` when live and not checking; `try` never), `state=leon.host_state(...)`, and all of `_facts`. Also `next_id` for `cards`: the id of `open_cards[0]` or None. Use `_render` from `.guest_guide` (it sets no-store).
   - `POST /apartments/{apartment_id}/leon/setup`: guards; `action` in (`skip_import`, `finish`): `skip_import` -> `back(".../leon/setup/cards")`; `finish` -> `back(".../leon/setup/done")`. Anything else -> `back(".../leon/setup")`.
   Register in `main.py` right before `app.include_router(guest_guide_routes.router)` (import as `leon_setup as leon_setup_routes`, following the import style there).
3. `routes/guest_guide.py`:
   - `leon_page`: after the 404 check, `if leon.host_state(apartment, live) in ("off", "terms"): return back(f"/apartments/{apartment_id}/leon/setup")` (`back` is already imported; it gives a 303).
   - `leon_save`, action `on`: when `form.get("next") == "setup"`, both the "tick the box" error and the success redirect go to `/apartments/{id}/leon/setup/switch_on` and `/apartments/{id}/leon/setup` respectively (same flashes). Without `next` keep today's redirects.
   - `guide_card` (GET): pass `from_leon=request.query_params.get("from") == "leon"` into `_card(...)` -> template value `from_leon` (add a keyword to `_card` with default False).
   - `guide_card_save`: `leon = form.get("from") == "leon"`. When `leon`: if `then == "next"` and `_next_open(...)` gives an id -> `back(f"{_base}/{next_id}?from=leon", msg=...)`; otherwise -> `back(f"/apartments/{apartment_id}/leon/setup/cards", msg=flash(request, "flash.guest_guide.saved"))`. Same rule after `guide_card_skip` when its form carries `from=leon` (add the hidden field to that form too). Without `from` keep today's behaviour exactly.
4. `guest_guide_card.html`: inside the save form and the skip form add `{% if from_leon %}<input type="hidden" name="from" value="leon">{% endif %}`. Change nothing else.
5. `_property_overview.html` Leon card: `href="{{ base_url }}/leon{{ '' if leon_card == 'on' else '/setup' }}"`.
6. `leon_setup/_layout.html`: copy `setup_wizard/_layout.html` and adapt:
   - title / page_title `t('leon_setup.title', name=apartment.internal_name)`; `back_url` `/apartments/{{ apartment.id }}`; meta `t('leon_setup.count', n=number, total=total, step=t('leon_setup.step.' ~ step))` when `number`.
   - progress: `{% for s in steps %}<li class="is-{{ 'done' if s in done_steps else 'current' if s == step else 'todo' }}"></li>{% endfor %}` and `setup-wizard-done-count` with `t('wizard.done_count', n=done_steps|length, total=total)`.
   - Exit: a plain link `<a class="ui-btn ui-btn-secondary setup-wizard-exit" href="/apartments/{{ apartment.id }}">{{ t('wizard.exit') }}</a>` (no form; no hide action here). If `setup-wizard-exit` styles a `form`, wrap the link in `<div class="setup-wizard-exit">` instead.
   - ask block: icons `{'switch_on': 'message-circle-question', 'import': 'download', 'cards': 'book-open', 'try': 'send'}` via `icon(name, 22)`, tones `{'switch_on': 'blue', 'import': 'teal', 'cards': 'purple', 'try': 'blue'}`, question `t('leon_setup.question.' ~ step)`; skipped on `done`.
   - foot: Back to `/apartments/{{ apartment.id }}/leon/setup/{{ prev_step }}` with `wizard.back`, then `{% block wizard_actions %}`.
   - `data-leon-setup data-leon-setup-step="{{ step }}"` on the outer div (instead of `data-setup-wizard`, so the onboarding JS does not pick it up).
   - At the end: `<script src="/static/leon-setup.js?v=20261026-0404" defer></script>`.
7. Step templates (each `{% extends "leon_setup/_layout.html" %}`; exactly one `ui-btn-primary` each):
   - `switch_on.html`: `setup-wizard-lede` = `leon_page.what`; if `state == 'terms'` a `ui_banner('attention', t('leon_page.terms_updated'))`; `<h2 class="setup-wizard-section-title">` `leon_page.warn_title`, the `<ul>` of `leon_page.warn1..6`; the form (POST `/apartments/{id}/leon`, `_csrf`, hidden `action=on`, hidden `next=setup`, the `checkline` checkbox exactly as in `leon_settings.html`) with `id="leon-setup-on"`. Actions block: `<button class="ui-btn ui-btn-primary" type="submit" form="leon-setup-on">{{ t('leon_page.switch_on') }}</button>`. If already on (host came back via Back): instead of the form, `setup-wizard-instruction` `leon_setup.switch_on.already` and a primary link "Next" to `import`.
   - `import.html`:
     - imports off: `setup-wizard-lede` `leon_setup.import.off`; primary link `leon_setup.next` to `cards`.
     - `import_busy`: `setup-wizard-wait`-style instruction `<p class="setup-wizard-instruction" data-leon-import-wait>{{ t('leon_setup.import.waiting') }}</p>`, the import history table (copy the table from `guest_guide.html`), a secondary GET link "Check again" (`wizard.try_it.check_again`) to the same page, and the one primary: a POST `action=skip_import` button labelled `leon_setup.import.meanwhile`.
     - `sources` not empty and not busy: lede `leon_setup.import.lede`, the two fields from 0403 (only the platforms left), form POST `/apartments/{id}/guide/import` with `_csrf` and hidden `next=leon`, `id="leon-setup-import"`; actions: secondary POST `action=skip_import` labelled `leon_setup.import.by_hand` (class `setup-wizard-skip`, own small form like `try_it.html`), primary submit `form="leon-setup-import"` labelled `leon_setup.import.button`. If some imports already exist, show the history table under the form.
     - nothing left to import (both used) and not busy: instruction `leon_setup.import.result` with `n=drafts`, the history table, primary link `leon_setup.import.check_cards` to `cards`.
   - `cards.html`: lede `leon_setup.cards.lede`; a line `t('guest_guide.not_live', done=progress.must_have_done, total=progress.must_have_total)` when not live, else `leon_setup.cards.live`; when `progress.check`, a `ui_banner('attention', t('guest_guide.check_waiting'))`; the open cards as a `ui_table_begin`/`ui_table_end` table exactly like the guide page rows (title, badge), each row linking to `/apartments/{id}/guide/{card.id}?from=leon`; a secondary link to Quick answers (`guest_guide.quick.link`, `/apartments/{id}/guide/quick`) and a secondary link "Open the whole guide" (`leon_page.guide_link`). Actions: if `next_id` a primary link `leon_setup.cards.next` to `/apartments/{id}/guide/{next_id}?from=leon`; else (live, nothing to check) primary link `leon_setup.next` to `try`.
   - `try.html` (placeholder until 0405): lede `leon_setup.try.lede`; if not live, instruction `leon_page.not_live` and primary link back to `cards`; else a `<div data-leon-try></div>` and the actions: primary POST `action=finish` labelled `leon_setup.finish`.
   - `done.html`: the celebrate banner from `setup_wizard/done.html` (always the `done` variant, confetti on) with title `leon_setup.done.title` and text `leon_setup.done.text`; then three `host-property-card` links in a `host-property-grid` list (copy the markup of the overview cards): QR page `/apartments/{id}/guide/qr` (`guest_guide.qr.link`), guest guide `/apartments/{id}/guide` (`leon_page.guide_link`), Leon settings `/apartments/{id}/leon` (`guest_guide.leon.open`). Actions: primary link `leon_setup.done.back` to `/apartments/{id}`.
8. `static/leon-setup.js` (no inline script; CSP): 
   ```js
   // 0404: the Leon setup import step reloads itself while the listing is being fetched.
   (function () {
     if (!document.querySelector("[data-leon-import-wait]")) return;
     var tries = 0;
     var timer = setInterval(function () {
       tries += 1;
       if (tries > 30 || document.hidden) { if (tries > 30) clearInterval(timer); return; }
       window.location.reload();
     }, 10000);
   })();
   ```
9. Copy (en / cs; vi in `host_vi_i18n.py`, short and plain, translate yourself):

   | key | en | cs |
   |---|---|---|
   | `leon_setup.title` | Set up Leon for %(name)s | Nastavení Leona pro %(name)s |
   | `leon_setup.count` | Step %(n)s of %(total)s: %(step)s | Krok %(n)s z %(total)s: %(step)s |
   | `leon_setup.step.switch_on` | Switch on | Zapnutí |
   | `leon_setup.step.import` | Import your listing | Import nabídky |
   | `leon_setup.step.cards` | Check the cards | Kontrola karet |
   | `leon_setup.step.try` | Try Leon | Vyzkoušejte Leona |
   | `leon_setup.question.switch_on` | Do you want Leon to answer your guests? | Má Leon odpovídat vašim hostům? |
   | `leon_setup.question.import` | Where is your property listed? | Kde máte ubytování vystavené? |
   | `leon_setup.question.cards` | Is everything Leon will say correct? | Je správně všechno, co bude Leon říkat? |
   | `leon_setup.question.try` | Ask Leon what a guest would ask | Zeptejte se Leona jako host |
   | `leon_setup.switch_on.already` | Leon is switched on for this property. | Leon je pro toto ubytování zapnutý. |
   | `leon_setup.next` | Next | Další |
   | `leon_setup.import.lede` | Paste your Booking.com and Airbnb links. We read both listings and write draft guide cards for you, so you do not start from an empty page. One link is enough. | Vložte odkazy na Booking.com a Airbnb. Obě nabídky přečteme a připravíme vám návrhy karet průvodce, ať nezačínáte od nuly. Stačí i jeden odkaz. |
   | `leon_setup.import.button` | Import my listings | Importovat nabídky |
   | `leon_setup.import.by_hand` | Fill in by hand | Vyplním ručně |
   | `leon_setup.import.waiting` | Reading your listings. This usually takes one or two minutes; this page updates by itself. | Čteme vaše nabídky. Obvykle to trvá minutu nebo dvě, stránka se obnoví sama. |
   | `leon_setup.import.meanwhile` | Fill the cards by hand meanwhile | Mezitím vyplnit karty ručně |
   | `leon_setup.import.result` | Done. %(n)s draft cards are waiting for you to check. | Hotovo. Ke kontrole na vás čeká %(n)s návrhů karet. |
   | `leon_setup.import.check_cards` | Check the cards | Zkontrolovat karty |
   | `leon_setup.import.off` | Imports are not available here. Fill in the cards by hand in the next step; it takes about ten minutes. | Import tu není k dispozici. V dalším kroku vyplníte karty ručně, zabere to asi deset minut. |
   | `leon_setup.cards.lede` | Leon only says what your cards say. Read each draft, fix what is wrong and save it. Guests see nothing until you do. | Leon říká jen to, co je na vašich kartách. Každý návrh si přečtěte, opravte, co nesedí, a uložte. Hosté nic neuvidí, dokud to neuděláte. |
   | `leon_setup.cards.live` | Your guide is live and every card is checked. | Průvodce je zveřejněný a všechny karty jsou zkontrolované. |
   | `leon_setup.cards.next` | Check the next card | Zkontrolovat další kartu |
   | `leon_setup.try.lede` | Ask Leon a few questions the way a guest would. Nothing is sent to anyone. | Položte Leonovi pár otázek jako host. Nic se nikomu neodešle. |
   | `leon_setup.finish` | Finish | Dokončit |
   | `leon_setup.done.title` | Leon is ready | Leon je připravený |
   | `leon_setup.done.text` | Guests can now ask Leon on the stay page and the QR guide page. Anything he does not know comes to you. | Hosté se teď mohou Leona ptát na stránce pobytu a na stránce průvodce z QR kódu. Co neví, přijde vám. |
   | `leon_setup.done.back` | Back to the property | Zpět na ubytování |

   `leon_setup.import.meanwhile` is the busy-state primary label in step 7.
10. Tests `test_0404_leon_setup.py` (fixtures from `test_0396_leon_opt_in.py`; set `config.APIFY_TOKEN` via monkeypatch for import cases):
    - 404 for `/leon/setup` and `/leon/setup/cards` when Leon is not offered; unknown step 404.
    - Fresh property: `/leon/setup` -> `switch_on`; any other step redirects to `switch_on`; the page has one `ui-btn-primary`, `/guide#leon-terms`, hidden `next` = `setup`.
    - POST `/leon` `action=on, terms=1, next=setup` -> redirect `/leon/setup`, which then redirects to `import` (imports on); with imports off -> `cards`.
    - Import step shows `name="booking_url"` and `name="airbnb_url"` and hidden `next` = `leon`; posting both links queues two rows and comes back to the import step, which now has `data-leon-import-wait`.
    - `action=skip_import` -> `cards`. `cards` lists a missing must-have card with `?from=leon`.
    - Card save with `from=leon` and `then=next` goes to the next open card with `?from=leon`; with no open card left (or a plain save) it goes to `/leon/setup/cards`. Without `from` the old redirects are unchanged.
    - Guide live, nothing in check -> `/leon/setup` -> `try`; `action=finish` -> `done`, which links to `/guide/qr`.
    - `GET /leon` in state off -> 303 to `/leon/setup`; in state on -> 200 (settings page).
    - Overview card href ends in `/leon/setup` when off and `/leon` when on.
    Update `test_0396_leon_opt_in.py` / `_browser.py` where they expect the off-state settings page with the terms form: point them to `/leon/setup/switch_on`, or assert the redirect.
11. `test_0404_leon_setup_browser.py` (`sync_api = pytest.importorskip("playwright.sync_api")`): at 390 px screenshots to `docs/tasks/screenshots-0404/`: `switch-on-390.png`, `import-390.png`, `import-waiting-390.png`, `cards-390.png`, `try-390.png` (guide made live in the fixture), `done-390.png`; plus `import-1280.png`. Each asserts `_no_overflow` and that the footer's Back and primary sit on one row at 1280 (`boundingBox().y` equal within 2 px).

## 5. Do not touch

`leon.reply` and the guest chat, `guest_guide_import` worker, the onboarding wizard routes and its JS, `wizard.css` (no new CSS), legal copy.

## 6. Commands

From `App/`:
```
.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 | tail -5
.venv/bin/python -m pytest tests/test_0404_leon_setup.py tests/test_0396_leon_opt_in.py tests/test_guest_guide_import.py tests/test_guest_guide.py tests/test_guest_guide_pages.py tests/test_design_*.py tests/test_privacy_first.py -q --tb=short 2>&1 | tail -30
UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_0404_leon_setup_browser.py tests/test_0396_leon_opt_in_browser.py -q -rs --tb=short 2>&1 | tail -15
```
From the repo root: `python3 scripts/design_lint.py | tail -5`. Then `git checkout -- docs/tasks/screenshots-0*` except `screenshots-0404`.

## 7. Acceptance

- [ ] Switching Leon on lands the host on the import step (when imports are on).
- [ ] Each wizard page has one primary, progress dots, Back and Exit, no horizontal scroll at 390 px.
- [ ] Card editing from the wizard returns to the wizard; outside it nothing changed.
- [ ] Overview card opens the wizard until Leon is on.
- [ ] §6 passes with 0 skipped; screenshots in `docs/tasks/screenshots-0404/`.

## 8. Stop and ask

A design test or the design lint needs a new class; the CSP blocks the reload script; a test outside §6 starts failing.

## 9. Report

`docs/tasks/0404-report.md` (600 tokens at most). Commit `0404 step k` after each step. Do not push.
