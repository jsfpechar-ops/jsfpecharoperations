# 0416: Plan picker (B4): /predplatne order, change, cancel, invoices; /cenik from billing

Status: review
Depends on: 0411, 0413, 0414, 0415 | Base commit: the head of `claude/billing-phase1-impl` | Branch: task/0416-plan-picker
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The host's plan page `/predplatne` (Czech URL, like `/cenik`):

- **Order.** Plan, yearly or monthly, add-ons, invoice details with "Fill in from ARES", and the price.
  - In a trial, the order starts when the trial ends.
  - When paused, the account opens again today and the first invoice is issued and mailed.
  - The founder price applies automatically on a yearly order while slots last.
- **Change.** One thing at a time, with a preview, then a confirm. This uses `billing.apply_change`; a rise on a yearly plan issues a supplementary invoice.
- **Cancel and take back.** Cancel ends the plan at the end of the period. Take back undoes that before the period ends.
- **Invoices.** A list with PDF download, own invoices only.
- **/cenik.** It takes its prices from `billing.py` and shows the founder counter while billing is on.
- **Settings.** It gets a link to the page while billing is on.

Invoices only: no card or gateway.

## 2. Context

You copy finished files from `docs/plans/billing-0416/` and make small anchored edits. The page uses only the host design macros (`host_page.html`, `choice_card`, `ui_*`) and adds no CSS. It works without JavaScript: the ARES button posts the form back.

**Excerpt A**, `App/app/main.py` (line 32, one line):

```python
from .routes import admin, cleaning as cleaning_routes, dev_ui, guest, guest_guide as guest_guide_routes, guest_guide_view, leon_setup as leon_setup_routes, guest_leon, guest_questions, havel as havel_routes, invoices, legal, mail_unsubscribe, onboarding_wizard, stay_fees
```

and `app.include_router(leon_setup_routes.router)` (line 359).

**Excerpt B**, `App/app/billing.py` (line 23): `    "canceling": {"paused"},`

**Excerpt C**, `App/app/routes/legal.py`:

```python
# Brief 0412: the public price list in whole Kč. Same numbers as app/billing.py
# (brief 0411); the plan-picker brief replaces this copy with an import and a test.
PUBLIC_RATES = {
    "base": {"month": [149, 119, 99], "year": [1190, 950, 790]},
    "max": {"month": [79, 59, 39], "year": [760, 570, 370]},
    "ttlock": {"month": 49, "year": 470},
}
```
```python
            # The founder counter comes with the plan-picker brief; until then no strip.
            "founder_left": None,
```
and the import line `from .. import config, cookie_inventory, host_i18n, operator, signup`.

**Excerpt D**, `App/app/templating.py`: `templates.env.globals["billing_banner"] = _template_billing_banner` (from 0414).

**Excerpt E**, `App/app/templates/settings.html` (lines 14–15):

```
  {% endfor %}
</nav>
```

**Excerpt F**, `App/app/host_i18n.py`: `"billing.banner.action_canceling": "Keep my plan",` and `"billing.banner.action_canceling": "Ponechat předplatné",` (from 0414).

If any excerpt is not found verbatim (and once), STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/billing_order.py` | create | copy of `docs/plans/billing-0416/billing_order.py` |
| `App/app/routes/billing.py` | create | copy of `docs/plans/billing-0416/billing_routes.py` |
| `App/app/templates/billing_plan.html` | create | copy of `docs/plans/billing-0416/billing_plan.html` |
| `App/app/main.py` | edit | register the router |
| `App/app/billing.py` | edit | canceling → active allowed |
| `App/app/routes/legal.py` | edit | prices from billing, founder counter |
| `App/app/templating.py` | edit | `billing_on` global |
| `App/app/templates/settings.html` | edit | link card to /predplatne |
| `App/app/host_i18n.py` | edit | 91 keys EN, 91 keys CS (script) |
| `App/tests/test_billing_order.py` | create | copy |
| `App/tests/test_0416_plan_page_browser.py` | create | copy |
| `docs/tasks/screenshots-0416/` | create | two screenshots |
| `docs/tasks/0416-report.md` | create | the report |

## 4. Steps

### Step 1. Copy (from the repo root)

```bash
cp docs/plans/billing-0416/billing_order.py App/app/billing_order.py
cp docs/plans/billing-0416/billing_routes.py App/app/routes/billing.py
cp docs/plans/billing-0416/billing_plan.html App/app/templates/billing_plan.html
cp docs/plans/billing-0416/test_billing_order.py App/tests/test_billing_order.py
cp docs/plans/billing-0416/test_0416_plan_page_browser.py App/tests/test_0416_plan_page_browser.py
```

### Step 2. `main.py`

In Excerpt A's import line, replace `, legal, mail_unsubscribe,` with `, legal, mail_unsubscribe, billing as billing_routes,`. After `app.include_router(leon_setup_routes.router)` add `app.include_router(billing_routes.router)`.

### Step 3. `billing.py`

Replace Excerpt B with `    "canceling": {"paused", "active"},  # 0416: a host can take a cancellation back`.

### Step 4. `routes/legal.py`

4a. Change the import line to `from .. import billing, config, cookie_inventory, host_i18n, operator, signup`.

4b. Replace the whole first block of Excerpt C (comment and `PUBLIC_RATES`) with:

```python
# The public price list in whole Kč, read from app/billing.py (brief 0416) so
# the page and the invoices can never disagree.
PUBLIC_RATES = {
    "base": {interval: list(rates) for interval, rates in billing.BASE.items()},
    "max": {interval: list(rates) for interval, rates in billing.MAX_EXTRA.items()},
    "ttlock": dict(billing.TTLOCK),
}
```

4c. Replace the two lines of the second block with:

```python
            # 0416: places left at the founder price, only while billing is on.
            "founder_left": billing.founder_slots_left() if billing.enabled() else None,
```

### Step 5. `templating.py`, `settings.html`, copy keys

5a. After Excerpt D add:

```python


def _template_billing_on() -> bool:
    """0416: whether UbyHost's own billing is switched on (the /predplatne link)."""
    from . import billing

    return billing.enabled()


templates.env.globals["billing_on"] = _template_billing_on
```

5b. In `settings.html` replace Excerpt E with:

```
  {% endfor %}
  {% if billing_on() %}<a class="host-property-card" href="/predplatne"><strong>{{ t('billing.plan.title') }}</strong><span class="host-property-card-open" aria-hidden="true"><span class="host-property-card-open-text">{{ t('common.open') }}</span></span></a>{% endif %}
</nav>
```

5c. From the repo root: `python3 docs/plans/billing-0416/insert_keys.py 2>&1 | tail -3`. Expected: `inserted 91 EN and 91 CS keys`.

### Step 6. Run §6, look at the two screenshots once, write the report, `Status: review`, commit.

## 5. Do not touch

`billing_invoices.py`, `billing_trial.py`, `auth.py`, `reporting.py`, any CSS or JS, `pricing.html`, `pricing.js`, `landing_i18n.py`.

## 6. Commands

From `App/`:

1. `.venv/bin/python -m pytest tests/test_billing_order.py tests/test_billing_core.py tests/test_billing_invoices.py tests/test_billing_trial.py tests/test_billing_enforcement.py -q --tb=short -x 2>&1 | tail -30`
2. `.venv/bin/python -m pytest tests/test_public_seo.py tests/test_owner_decisions.py tests/test_landing_decoration.py tests/test_dev_ui.py tests/test_host_i18n.py -q --tb=short 2>&1 | tail -30` (test_host_i18n.py has 3 known failures on main, "no such table: apartment" when run alone; anything else is yours)
3. `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_CAPTURE_0416=1 .venv/bin/python -m pytest tests/test_0416_plan_page_browser.py tests/test_0412_pricing_browser.py -q -rs --tb=short -x 2>&1 | tail -30` (0 skipped)
4. `ls tests | grep -iE 'settings.*(browser|geometry)|geometry' | tail -30`, then run the settings ones the same way as command 3.

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`. After the test runs, `git checkout -- docs/tasks/screenshots-0*` for any screenshot folder other than `screenshots-0416` that the runs rewrote.

## 7. Acceptance

- [ ] All commands pass, 0 skipped in the browser runs.
- [ ] `docs/tasks/screenshots-0416/predplatne-order-390.png` and `predplatne-plan-390.png` exist; nothing scrolls sideways.
- [ ] `git diff --stat` shows only the §3 files.

## 8. Stop and ask

- An excerpt is not found once.
- A copied test fails twice: report the assertion and the last 30 lines. One obvious typo fix in a copied file is allowed; name it under Deviations.
- A design or catalog test fails on `billing_plan.html`: report it, do not add CSS.

## 9. Report

`docs/tasks/0416-report.md`: files changed, the last 5 lines of each command, §7 ticked, Deviations, Questions.

## Risk list (for the reviewer)

- A founder slot is claimed at order time and stays used if the host later switches to monthly.
- The list of what each plan includes on this page is short on purpose; /cenik holds the full comparison.
