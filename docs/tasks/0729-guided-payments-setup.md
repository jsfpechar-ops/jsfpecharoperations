# 0729: Guided 4-step payments setup around Stripe's hosted onboarding

Status: review
Depends on: 0624 (merged, #668) | Base commit: 7b4109f2 | Branch: task/0729-guided-payments-setup (already exists, check it out)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

On `/payments`, until card payments are on, replace the single "Open Stripe" button with 4 numbered step cards (how payments work, your details, verify with Stripe, take card payments) and exactly one primary button that always points at the next unfinished step. After Stripe, the host lands back on `/payments` with a plain-language message instead of the dashboard root, and a missing business profile gives a clear message instead of a silent redirect.

## 2. Context

- Owner decision 1 Nov 2026: hosted Stripe onboarding (Account Links) stays; no Stripe script on our pages. Setup must be "dumbproof". Host copy never says Connect, KYC, payout or webhook.
- Page add-on: `docs/design/pages/payments.md` (already written). Reuse the setup wizard summary markup (`setup-wizard-checklist host-property-grid`, `host-property-card host-property-card-static setup-summary-card`, `ui-badge`). **No CSS change.**
- `App/app/stripe_connect.py`, inside `create_or_get_account`:
  ```python
      entity = db.query_one(
          "SELECT * FROM legal_entity WHERE owner_user_id = ?", (owner_user_id,)
      )
      if entity is None:
  ```
- `App/app/routes/stripe_connect.py` import line: `from .. import auth, config, payments_consent, rate_limit, security, stripe_connect`
- Same file, end of `connect_start`:
  ```python
      try:
  ```
  (the try that calls `stripe_connect.onboarding_link`) and
  ```python
      except (stripe_connect.StripeOff, ValueError) as exc:
          log.warning("connect start failed: %s", exc)
          return RedirectResponse("/", status_code=303)
  ```
- Same file, end of `connect_return`:
  ```python
      try:
          stripe_connect.handle_return(owner_id)
      except (stripe_connect.StripeOff, ValueError, KeyError) as exc:
          log.warning("connect return failed: %s", exc)
      # The dashboard reads the state from the mirror; the visible copy and the
      # ? popover explaining "return is not verified" arrive with the payments
      # dashboard (plan P1.5).
      return RedirectResponse("/", status_code=303)
  ```
- `App/app/routes/payments.py`, `payments_page` render dict contains `"connect_state": state,`.
- `App/app/templates/payments.html` lines 22 to 30:
  ```
    {% else %}
    <p>{{ t('payments.connect.' ~ connect_state.onboarding_state) }}</p>
    {#- A plain link, not a form POST: the same-origin POST/303 navigation is
        eaten by the PWA submit handling (live-observed hang on the skeleton);
        link navigation works everywhere, and target=_blank keeps the dashboard
        open behind the single-use Stripe onboarding. -#}
    {{ ui_button(t('payments.connect.open_stripe'), 'primary',
                 href='/payments/connect/start', attrs='target="_blank" rel="noopener"') }}
    {% endif %}
  ```
- `App/app/host_i18n.py`: English anchor line `        "payments.connect.open_stripe": "Open Stripe",` (around line 1350) and Czech anchor line `        "payments.connect.open_stripe": "Otevřít Stripe",` (around line 3126). Czech is stored as raw UTF-8 there; write it the same way.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/stripe_connect.py | edit | `legal_entity_for_owner()` helper, used by `create_or_get_account` |
| App/app/routes/stripe_connect.py | edit | start: clear errors back to /payments; return: back to /payments with a message |
| App/app/routes/payments.py | edit | `_setup()` builds the 4 steps, passed as `setup` |
| App/app/templates/payments.html | edit | step cards + one primary button |
| App/app/host_i18n.py | edit | new en + cs keys |
| App/tests/test_payments_dashboard.py | edit | helper + updated button test + 2 new tests |
| App/tests/test_stripe_connect.py | edit | one assert in `test_return_mirrors_state` |
| App/tests/test_payments_setup_browser.py | new | 390 px geometry + screenshot |
| docs/tasks/screenshots-0729/payments-setup-390.png | new | made by the browser test |
| docs/tasks/0729-report.md | new | report |
| docs/tasks/0729-guided-payments-setup.md | edit | Status line only |

No other file may change.

## 4. Steps

1. `git checkout task/0729-guided-payments-setup`. Set this brief's line 3 to `Status: in-progress`. Commit `0729 start`.

2. `App/app/stripe_connect.py`: directly above `def create_or_get_account`, add:
   ```python
   def legal_entity_for_owner(owner_user_id: int) -> Optional[Dict[str, Any]]:
       """The business entity whose details go to Stripe (0729: the host sees
       them on /payments before opening Stripe)."""
       row = db.query_one(
           "SELECT * FROM legal_entity WHERE owner_user_id = ? AND archived_at IS NULL"
           " ORDER BY id",
           (owner_user_id,),
       )
       return dict(row) if row else None


   ```
   In `create_or_get_account`, replace the three lines `entity = db.query_one(` … `)` (§2) with `    entity = legal_entity_for_owner(owner_user_id)`. Leave the rest as it is.
   Run: `cd App && .venv/bin/python -m pytest tests/test_stripe_connect.py -q --tb=short -x 2>&1 | tail -5`. Expected: all pass.

3. `App/app/routes/stripe_connect.py`:
   a. Under the `from .. import …` line add `from .admin_helpers import back as _back`, and `from .admin_helpers import flash as _flash`.
   b. In `connect_start`, directly before its `    try:` line, add:
   ```python
       if stripe_connect.legal_entity_for_owner(owner_id) is None:
           # 0729: say what is missing instead of a silent bounce to "/".
           return _back("/payments", err=_flash(request, "payments.err.no_entity"))
   ```
   c. In the same function, replace `        return RedirectResponse("/", status_code=303)` inside the `except (stripe_connect.StripeOff, ValueError)` block with `        return _back("/payments", err=_flash(request, "payments.err.stripe_start"))`.
   d. Replace the `connect_return` ending (§2, from `    try:` to the final return) with:
   ```python
       state = ""
       try:
           state = stripe_connect.handle_return(owner_id)
       except (stripe_connect.StripeOff, ValueError, KeyError) as exc:
           log.warning("connect return failed: %s", exc)
       # Return is not verified: the message follows the mirrored state (0729).
       key = {
           "complete": "payments.connect.flash_complete",
           "action_required": "payments.connect.flash_action",
       }.get(state, "payments.connect.flash_pending")
       return _back("/payments", msg=_flash(request, key))
   ```

4. `App/app/routes/payments.py`: directly above `@router.get("/payments")` add:
   ```python
   def _setup(owner_id: int, state: Dict[str, Any]) -> Dict[str, Any]:
       """The 4 guided setup steps (0729) and which one the primary button opens."""
       consent = payments_consent.accepted(owner_id)
       entity = stripe_connect.legal_entity_for_owner(owner_id)
       has_details = bool(entity and (entity.get("name") or "").strip())
       onboarding = state.get("onboarding_state") or "none"
       stripe_status = {"pending": "waiting", "action_required": "attention"}.get(onboarding, "todo")
       steps = [
           {"key": "consent", "status": "done" if consent else "todo"},
           {"key": "details", "status": "done" if has_details else "todo",
            "href": f"/entities?edit={entity['id']}" if entity else "/entities"},
           {"key": "stripe", "status": stripe_status},
           {"key": "live", "status": "todo"},
       ]
       if not consent:
           next_step = "consent"
       elif not has_details:
           next_step = "details"
       else:
           next_step = "stripe"
       return {"steps": steps, "next": next_step, "entity": entity if has_details else None}


   ```
   In `payments_page`, under `"connect_state": state,` add `            "setup": _setup(owner_id, state),`.

5. `App/app/templates/payments.html`: replace the §2 block (from `  {% else %}` to its `  {% endif %}`) with:
   ```
     {% else %}
     <p>{{ t('payments.connect.' ~ connect_state.onboarding_state) }}</p>
     <p>{{ t('payments.setup.lead') }}</p>
     <ul class="setup-wizard-checklist host-property-grid" data-payments-setup>
       {% for step in setup.steps %}
       <li class="is-{{ step.status }}" data-payments-step="{{ step.key }}">
         <div class="host-property-card host-property-card-static setup-summary-card">
           <span class="setup-summary-icon" aria-hidden="true">{{ loop.index }}</span>
           <div class="setup-summary-copy">
             <strong>{{ t('payments.setup.step.' ~ step.key) }}</strong>
             <span class="ui-badge ui-badge-{{ 'done' if step.status == 'done' else 'attention' if step.status == 'attention' else 'neutral' }}" data-tone="{{ 'green' if step.status == 'done' else 'amber' if step.status == 'attention' else 'grey' }}">
               {% if step.status == 'done' %}<span aria-hidden="true">✓</span>{% endif %}
               {{ t('payments.setup.badge.' ~ step.status) }}
             </span>
             {% if step.key == 'details' %}
               {% if setup.entity %}
               <span class="ui-sub">{{ setup.entity.name }}{% if setup.entity.contact_email %} · {{ setup.entity.contact_email }}{% endif %}</span>
               <a class="setup-summary-action" href="{{ step.href }}">{{ t('payments.setup.details_edit') }}</a>
               {% else %}
               <span class="ui-sub">{{ t('payments.setup.details_missing') }}</span>
               {% endif %}
             {% elif step.key == 'stripe' %}
               <span class="ui-sub">{{ t('payments.setup.stripe_help') }}</span>
             {% elif step.key == 'live' %}
               <span class="ui-sub">{{ t('payments.setup.live_help') }}</span>
             {% endif %}
           </div>
         </div>
       </li>
       {% endfor %}
     </ul>
     {% if setup.next == 'consent' %}
     {{ ui_button(t('payments.setup.continue'), 'primary', href='/payments/consent') }}
     {% elif setup.next == 'details' %}
     {{ ui_button(t('payments.setup.details_add'), 'primary', href='/entities') }}
     {% else %}
     {#- A plain link, not a form POST: the same-origin POST/303 navigation is
         eaten by the PWA submit handling (live-observed hang on the skeleton);
         link navigation works everywhere, and target=_blank keeps the dashboard
         open behind the single-use Stripe onboarding (and out of prefetch). -#}
     {{ ui_button(t('payments.connect.open_stripe') if connect_state.onboarding_state == 'none' else t('payments.connect.continue_stripe'), 'primary',
                  href='/payments/connect/start', attrs='target="_blank" rel="noopener"') }}
     {% endif %}
     {% endif %}
   ```

6. `App/app/host_i18n.py`, English: directly under the English anchor line (§2) insert:
   ```python
           "payments.connect.continue_stripe": "Continue in Stripe",
           "payments.connect.flash_complete": "Done. Card payments are on.",
           "payments.connect.flash_action": "Stripe still needs something from you. Tap Continue in Stripe.",
           "payments.connect.flash_pending": "Thank you. Stripe is checking your details, usually within a few minutes. You can close this page.",
           "payments.setup.lead": "Four short steps. You can stop at any time and carry on later where you left off.",
           "payments.setup.step.consent": "Read how payments work",
           "payments.setup.step.details": "Check the details we send to Stripe",
           "payments.setup.step.stripe": "Verify yourself with Stripe",
           "payments.setup.step.live": "Take card payments",
           "payments.setup.badge.done": "Done",
           "payments.setup.badge.todo": "To do",
           "payments.setup.badge.waiting": "Stripe is checking",
           "payments.setup.badge.attention": "Stripe needs you",
           "payments.setup.details_missing": "Add your business details first. Stripe needs your name.",
           "payments.setup.details_edit": "Edit",
           "payments.setup.details_add": "Add your details",
           "payments.setup.stripe_help": "About 5 minutes. Have your ID card or passport, your bank account number and your phone ready.",
           "payments.setup.live_help": "Once Stripe approves you, the payment requests below can be paid by card.",
           "payments.setup.continue": "Continue",
           "payments.err.no_entity": "Add your business details first.",
           "payments.err.stripe_start": "Stripe did not open. Try again in a minute.",
   ```
   Czech: directly under the Czech anchor line insert the same keys, in the same order:
   ```python
           "payments.connect.continue_stripe": "Pokračovat ve Stripe",
           "payments.connect.flash_complete": "Hotovo. Platby kartou běží.",
           "payments.connect.flash_action": "Stripe od vás ještě něco potřebuje. Klepněte na Pokračovat ve Stripe.",
           "payments.connect.flash_pending": "Děkujeme. Stripe teď vaše údaje kontroluje, obvykle do pár minut. Stránku můžete zavřít.",
           "payments.setup.lead": "Čtyři krátké kroky. Kdykoli můžete přestat a později pokračovat tam, kde jste skončili.",
           "payments.setup.step.consent": "Přečtěte si, jak platby fungují",
           "payments.setup.step.details": "Zkontrolujte údaje, které pošleme do Stripe",
           "payments.setup.step.stripe": "Ověřte se u Stripe",
           "payments.setup.step.live": "Přijímejte platby kartou",
           "payments.setup.badge.done": "Hotovo",
           "payments.setup.badge.todo": "Zbývá",
           "payments.setup.badge.waiting": "Stripe kontroluje",
           "payments.setup.badge.attention": "Stripe vás potřebuje",
           "payments.setup.details_missing": "Nejdřív vyplňte údaje provozovatele. Stripe potřebuje vaše jméno.",
           "payments.setup.details_edit": "Upravit",
           "payments.setup.details_add": "Vyplnit údaje",
           "payments.setup.stripe_help": "Zabere asi 5 minut. Připravte si občanku nebo pas, číslo účtu a telefon.",
           "payments.setup.live_help": "Jakmile vás Stripe schválí, půjdou žádosti o platbu níže zaplatit kartou.",
           "payments.setup.continue": "Pokračovat",
           "payments.err.no_entity": "Nejdřív vyplňte údaje provozovatele.",
           "payments.err.stripe_start": "Stripe se nepodařilo otevřít. Zkuste to za chvíli znovu.",
   ```
   Run: `cd App && .venv/bin/python -m pytest tests/test_host_i18n.py -q --tb=short -x -k same_keys 2>&1 | tail -5`. Expected: pass.

7. `App/tests/test_payments_dashboard.py`:
   a. Change the import line `from app import auth, config, db, payment_request` to `from app import auth, config, db, payment_request, payments_consent`.
   b. Directly under the `_set_state` function add:
   ```python
   def _ready(oid: int):
       """Consent given and a business entity on file: the Stripe step is next."""
       payments_consent.record(oid)
       db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
       db.insert("legal_entity", {"owner_user_id": oid, "name": "Pay Host s.r.o.",
                                  "contact_email": f"{OWNER}@example.test",
                                  "created_at": db.utcnow()})
   ```
   c. In `test_button_only_in_pending_or_action_required`, add `    _ready(owner)` as the function's first line after the `monkeypatch.setattr` line, and replace `        assert ("Open Stripe" in response.text) == has_button, state` with `        assert ('href="/payments/connect/start"' in response.text) == has_button, state`.
   d. In `test_connect_button_is_a_plain_link`, add `owner` to its arguments (`def test_connect_button_is_a_plain_link(client, owner, monkeypatch):`) and add `    _ready(owner)` before `    response = client.get("/payments")`.
   e. At the end of the file add:
   ```python
   # --- guided setup (0729) -------------------------------------------------------


   def test_setup_button_always_points_at_the_next_step(client, owner, monkeypatch):
       monkeypatch.setattr(config, "STRIPE_MODE", "test")
       _set_state(owner, "none")
       html = client.get("/payments").text
       assert "Read how payments work" in html
       assert 'href="/payments/consent"' in html
       assert 'href="/payments/connect/start"' not in html
       payments_consent.record(owner)
       html = client.get("/payments").text
       assert "Add your business details first" in html
       assert 'href="/entities"' in html
       assert 'href="/payments/connect/start"' not in html
       _ready(owner)
       html = client.get("/payments").text
       assert "Pay Host s.r.o." in html
       assert "Open Stripe" in html
       _set_state(owner, "action_required")
       html = client.get("/payments").text
       assert "Continue in Stripe" in html
       assert "Stripe needs you" in html


   def test_start_without_details_explains_instead_of_bouncing(client, owner, monkeypatch):
       monkeypatch.setattr(config, "STRIPE_MODE", "test")
       monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test_x")
       payments_consent.record(owner)
       db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner,))
       response = client.get("/payments/connect/start", follow_redirects=False)
       assert response.status_code == 303
       assert response.headers["location"].startswith("/payments?")
       assert "err=" in response.headers["location"]
   ```
   Run: `cd App && .venv/bin/python -m pytest tests/test_payments_dashboard.py -q --tb=short -x 2>&1 | tail -15`. Expected: all pass.

8. `App/tests/test_stripe_connect.py`, in `test_return_mirrors_state`, under `    assert response.status_code == 303` add `    assert response.headers["location"].startswith("/payments?msg=")`. Run step 2's command again. Expected: all pass.

9. Create `App/tests/test_payments_setup_browser.py`. Copy the browser part of `App/tests/test_payments_consent.py` (from `REQUIRE_BROWSER = …` to the end) together with that file's imports, `_cleanup`, `owner` and `stripe_env` fixtures, with these changes only:
   - module docstring `"""0729: guided payments setup fits a phone."""`; `OWNER = "paysetup"`; `SHOTS = … / "screenshots-0729"`.
   - `_cleanup` also runs `db.execute("DELETE FROM stripe_account WHERE owner_user_id = ?", (oid,))` before deleting the user.
   - the `owner` fixture also calls `payments_consent.record(oid)` after inserting the legal entity.
   - rename the test to `test_payments_setup_fits_a_phone`; it opens `/payments?lang=cs`, asserts `page.locator("[data-payments-setup] li").count() == 4` and no horizontal overflow, and saves `payments-setup-390.png`.
   Run: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_payments_setup_browser.py -q --tb=short -x -rs 2>&1 | tail -10`. Expected: 1 passed, 0 skipped, and the PNG exists. Open the PNG and check that the 4 cards and the button show in Czech.

10. Commit after each of steps 2 to 9 (`0729 step N`).

## 5. Do not touch

`App/app/static/` (no CSS or JS change), `App/app/migrations*`, `payments_consent.py`, `payment_links.py`, `stripe_connect.process_event` and the webhook route, `docs/context/*`. Hard rules 2 (no new third-party script), 6 (light mode, no JS needed), 7 (browser test, 0 skipped, 390 px screenshot), 8 (never push to main).

## 6. Commands

From `App/`:
1. `.venv/bin/python -m pytest tests/test_payments_dashboard.py tests/test_payment_request_model.py tests/test_stripe_connect.py tests/test_payment_links.py tests/test_payment_qr.py tests/test_payments_consent.py -q --tb=short 2>&1 | tail -15` → all pass.
2. `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_payments_setup_browser.py tests/test_design_guardrails_browser.py -q --tb=short -rs 2>&1 | tail -15` → all pass, 0 skipped.
3. `.venv/bin/python ../scripts/design_lint.py 2>&1 | tail -5` → `design lint: OK`.
From the repo root: 4. `python3 scripts/context_lint.py 2>&1 | tail -5` → `context lint: OK`.

## 7. Acceptance

- [ ] With no consent, the one primary button opens `/payments/consent`; with consent but no business entity, it opens `/entities`; with both, it opens Stripe (`target=_blank`).
- [ ] The details card shows the entity name and e-mail with an Edit link.
- [ ] `/payments/connect/start` without an entity returns to `/payments` with an error message.
- [ ] `/payments/connect/return` lands on `/payments` with a message that matches the state.
- [ ] §6 commands pass; screenshot `docs/tasks/screenshots-0729/payments-setup-390.png` shows the 4 Czech cards.

## 8. Stop and ask

As in the TEMPLATE: an excerpt not found, a test failing twice, 25 tool calls or about 50k tokens (report `blocked`), a file outside §3, a step unclear, or anything needing push, merge, secrets or deploy.

## 9. Report

Write `docs/tasks/0729-report.md` (600 tokens at most) per the TEMPLATE and set this brief's `Status: review`. Do not push.

## Risk list (for the reviewer)

`App/app/routes/stripe_connect.py` (redirect targets), `App/app/templates/payments.html`, `App/app/routes/payments.py`.

## Owner steps

After merge and deploy: open Platby on your phone. You should see 4 numbered steps and one coral button. Tap it and follow it to Stripe. When Stripe sends you back, you land on Platby with a short message.
