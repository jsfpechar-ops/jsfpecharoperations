# 0995: Booking site item in the host sidebar

Status: todo
Depends on: none | Base commit: 47640cf3 | Branch: task/0995-booking-site-sidebar
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Every host gets a "Booking site" item in the desktop sidebar. It opens a new page `/booking-sites` that lists the owner's properties with their published status and a button to each property's booking-site setup; an owner with exactly one property is sent straight to that property's setup page.

## 2. Context

Rules that apply: AGENTS.md rule 6 (light mode), 7 (browser + geometry tests, 390 px screenshot per changed page), 9 (copy lives in one place, no sentence the button already says), 10 (UX gate: you run it, you write per page what you saw). Do not add dependencies.

Existing pieces (all verified at base commit):

- `App/app/templates/_shell_sidebar.html` lines 4-5 and 14-20 (the list the new item joins):
```
{% set stays_nav = nav in ('reservations', 'submissions', 'housebook') %}
{% set properties_nav = nav in ('apartments', 'guest_links', 'automation', 'entities', 'smart_locks') %}
...
        ('/payments', 'credit-card', t('nav.payments'), nav == 'payments')] %}
```
- `App/app/routes/payments.py`: `_bsite_apartment(request, apartment_id)`, `@router.get("/apartments/{apartment_id}/booking-site")` def `booking_site_setup`, which sets `"nav": "properties"` in its context dict. Imports at top already include `access, auth, config, db, host_i18n`, `render`, `RedirectResponse`, `Response`.
- `App/app/templates/booking_site_setup.html`: line 5 `{% set nav = 'properties' %}`; lines 15-16 the locked state: `{% if not allowed %}` then `{{ ui_banner('attention', t('bsite.max_only'), t('bsite.max_cta'), '/predplatne') }}`.
- `booking_site.site_allowed(owner_id)` in `App/app/booking_site.py` (Max plan only; billing off = allowed).
- Published status: table `property_page`, column `published` (0/1), keyed by `apartment_id` (see `property_page.publish_page`).
- Owner scoping for property lists (copy from `routes/stay_fees.py`): `access.owner_id(request)`, query `SELECT ... FROM apartment WHERE {db.null_safe_eq('owner_user_id')} AND archived_at IS NULL AND active = 1 ORDER BY internal_name, id`.
- Existing i18n keys to reuse, no new copy for these: `bsite.title` (Booking site / Rezervační web), `bsite.max_only`, `bsite.max_cta`, `bsite.badge.done`. Keys that do NOT exist yet and are added in step 1: `nav.booking_sites`, `bsite.list.live`, `bsite.list.off`, `bsite.list.open`, `bsite.list.empty`.
- Icons: `App/app/templates/_icons.html` is a dict of names; use the existing `'globe'` only if it is there (grep first), else existing `'external-link'`. Do not add a new icon.
- Pages with `{% set v2 = true %}` are covered by `test_0710_v2_mockup_match_browser.py`; the new page is NOT v2 (same as `booking_site_setup.html`).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/host_i18n.py | edit | add 5 keys, cs + en |
| App/app/templates/_shell_sidebar.html | edit | add the nav row |
| App/app/routes/payments.py | edit | new GET `/booking-sites`; setup page nav |
| App/app/templates/booking_sites.html | create | the list page |
| App/app/templates/booking_site_setup.html | edit | line 5 nav value |
| App/tests/test_booking_site_host.py | create | route + sidebar tests |
| App/tests/test_layout_lint_browser.py | edit | add `"booking-sites": "/booking-sites"` to `EXTRA_ROUTES` |

No other file may change. The mobile tab bar (`_shell_tabbar.html`) and `_shell_v2.html` stay as they are (sidebar only, owner request).

## 4. Steps

Commit after each step as `0995 step k`.

### Step 1. i18n keys (`App/app/host_i18n.py`)

1. `grep -nF '"nav.stay_fees"' App/app/host_i18n.py` (expect two hits: en near line 52, cs near line 2132). Directly after each hit add:
   - en: `"nav.booking_sites": "Booking site",`
   - cs: `"nav.booking_sites": "Rezervační web",`
2. `grep -nF '"bsite.max_cta"' App/app/host_i18n.py` (two hits). Directly after each add (match the file's existing escaping style, `\u` escapes in cs):
   - en:
     `"bsite.list.live": "Live",` `"bsite.list.off": "Not published",` `"bsite.list.open": "Set up",` `"bsite.list.empty": "Add a property first.",`
   - cs:
     `"bsite.list.live": "Zveřejněno",` `"bsite.list.off": "Nezveřejněno",` `"bsite.list.open": "Nastavit",` `"bsite.list.empty": "Nejdřív přidejte ubytování.",`
3. Run: `cd App && .venv/bin/python -c "import app.host_i18n as h; print('ok')" 2>&1 | tail -30` expect `ok`.

### Step 2. Sidebar row (`_shell_sidebar.html`)

Replace
```
        ('/payments', 'credit-card', t('nav.payments'), nav == 'payments')] %}
```
with
```
        ('/payments', 'credit-card', t('nav.payments'), nav == 'payments'),
        ('/booking-sites', 'globe', t('nav.booking_sites'), nav == 'booking_sites')] %}
```
(`globe` only if grep in `_icons.html` finds `'globe'`; otherwise use `'external-link'`.) The item is shown to all hosts; no plan check here. `properties_nav` needs no change: the setup page moves to `nav = 'booking_sites'` in step 4, and `'booking_sites'` is deliberately NOT added to `properties_nav`, so Properties is not highlighted at the same time.

### Step 3. Route (`App/app/routes/payments.py`)

Insert directly before `@router.get("/apartments/{apartment_id}/booking-site")`:
```python
@router.get("/booking-sites")
def booking_sites(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    owner_id = access.owner_id(request)
    from .. import booking_site

    rows = db.query(
        "SELECT a.id, a.internal_name, COALESCE(p.published, 0) AS published "
        "FROM apartment a LEFT JOIN property_page p ON p.apartment_id = a.id "
        f"WHERE {db.null_safe_eq('a.owner_user_id')} AND a.archived_at IS NULL AND a.active = 1 "
        "ORDER BY a.internal_name, a.id",
        (owner_id,),
    )
    if len(rows) == 1:
        return RedirectResponse(f"/apartments/{rows[0]['id']}/booking-site", status_code=303)
    return render(
        request,
        "booking_sites.html",
        {"nav": "booking_sites", "rows": rows, "allowed": booking_site.site_allowed(owner_id)},
    )
```
If `db.null_safe_eq` does not accept a dotted column (`grep -n "def null_safe_eq" -A8 App/app/db.py`), STOP (section 8). A single property redirects for Max and non-Max owners alike; the setup page already shows the locked banner.

In `booking_site_setup` change `"nav": "properties", "apartment": apartment,` to `"nav": "booking_sites", "apartment": apartment,`.

Run: `cd App && .venv/bin/python -c "import app.routes.payments" 2>&1 | tail -30` expect no output.

### Step 4. Templates

`App/app/templates/booking_site_setup.html` line 5: `{% set nav = 'properties' %}` becomes `{% set nav = 'booking_sites' %}`. (Back link to the property page stays.)

Create `App/app/templates/booking_sites.html`:
```
{% extends "host_page.html" %}
{% from "_ui.html" import ui_button, ui_badge with context %}
{% from "_ui_layout.html" import ui_section, ui_banner with context %}
{% set nav = 'booking_sites' %}
{% set body_kind = 'list' %}
{% block title %}{{ t('bsite.title') }}{% endblock %}
{% block primary_action %}{% endblock %}
{% block tabs %}{% endblock %}
{% block toolbar %}{% endblock %}
{% block body %}
{% if not allowed %}
{{ ui_banner('attention', t('bsite.max_only'), t('bsite.max_cta'), '/predplatne') }}
{% endif %}
{% if rows %}
{% call ui_section(t('bsite.title')) %}
<dl class="ui-facts">
  {% for row in rows %}
  <div>
    <dt>{{ row.internal_name }}</dt>
    <dd>
      {% if row.published %}{{ ui_badge('done', t('bsite.list.live')) }}{% else %}{{ ui_badge('neutral', t('bsite.list.off')) }}{% endif %}
      {{ ui_button(t('bsite.list.open'), 'secondary', href='/apartments/' ~ row.id ~ '/booking-site', size='compact') }}
    </dd>
  </div>
  {% endfor %}
</dl>
{% endcall %}
{% else %}
<p>{{ t('bsite.list.empty') }}</p>
{% endif %}
{% endblock %}
```
Copy check (rule 9): the locked sentence and the upgrade link come only from `bsite.max_only` and `bsite.max_cta`; no new sentence repeats a button label. If `host_page.html` does not define one of these blocks, or `body_kind='list'` is unknown, STOP.
Run: `cd App && .venv/bin/python -m pytest tests/test_booking_site.py -q --tb=short -x 2>&1 | tail -30`.

### Step 5. Tests (`App/tests/test_booking_site_host.py`)

Before writing, `grep -n "def \|fixture" App/tests/test_booking_site.py | head -40` and copy its login/client/owner-with-apartment fixtures and the way it turns billing on and puts an owner on a non-Max plan (reuse, do not invent). Write tests:
1. Logged-in host with 2 apartments: GET `/booking-sites` returns 200, contains both names and `/apartments/{id}/booking-site` for each, and contains `href="/booking-sites"` in the sidebar with `aria-current="page"` on that row.
2. Host with exactly 1 apartment: GET `/booking-sites` (no redirect following) returns 303 with Location `/apartments/{id}/booking-site`.
3. Non-Max owner with 2 apartments: 200 and body contains the en text of `bsite.max_only` and `href="/predplatne"`.
4. Published apartment shows the `bsite.list.live` text, an unpublished one `bsite.list.off`.
5. Logged out: GET `/booking-sites` redirects to login (same assertion style as the other tests in the file you copied).
6. GET `/apartments/{id}/booking-site` page: Properties row has no `aria-current`, Booking site row has `aria-current="page"`.

### Step 6. Layout lint route (`App/tests/test_layout_lint_browser.py`)

In `EXTRA_ROUTES` (grep `-nF '"stay-fees": "/stay-fees",'`) add the line after it: `    "booking-sites": "/booking-sites",`. Note: the lint fixture host has several apartments, so the list renders; if it has exactly one, the route redirects and the shot is the setup page; that is acceptable.

## 5. Do not touch

`App/app/booking_site.py`, `booking_setup.py`, payments POST handlers, `_shell_tabbar.html`, `_shell_v2.html`, CSS files (reuse existing classes only), migrations (no schema change), billing/plan logic, any other test. AGENTS.md rules 1-3 (no new data, no new outbound request, no JavaScript needed).

## 6. Commands

From `App/`, each ending `2>&1 | tail -30`:

1. `.venv/bin/python -m pytest tests/test_booking_site_host.py tests/test_booking_site.py tests/test_property_page.py tests/test_stripe_connect.py -q --tb=short -x 2>&1 | tail -30` (test-map row "Booking site"). Expect all pass.
2. `.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py -q --tb=short -x -rs 2>&1 | tail -30` (test-map row "Host pages, host templates"). Expect 0 skipped.
3. UX gate: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x -rs 2>&1 | tail -30`. Expect 0 findings, 0 skipped.
4. Open `/tmp/shots/layout-lint/booking-sites-390.png`, `-768.png`, `-1280.png` and `booking-site-setup`-style shots if present. Copy the 390 shot of `/booking-sites` into the PR/report.
5. Root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] Sidebar shows "Booking site" (cs "Rezervační web") for a host on any plan; row is highlighted on `/booking-sites` and on `/apartments/{id}/booking-site`, Properties is not.
- [ ] `/booking-sites` lists name, live / not published badge, "Set up" button to the property's booking-site page.
- [ ] Exactly one property: 303 to that property's page.
- [ ] Non-Max: page renders with the `bsite.max_only` banner and `/predplatne` link.
- [ ] Commands 1 to 3 green, 0 skipped; command 5 clean.
- [ ] One 390 px screenshot of `/booking-sites` in the report; per page text "390: ...; 768: ...; 1280: ..." written by you (rule 10).
- [ ] No file outside section 3 changed (`git diff --stat`).

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt or anchor is not found verbatim;
- `db.null_safe_eq` cannot take `a.owner_user_id`, or `property_page` has no `apartment_id`/`published` columns;
- `host_page.html` lacks a block this template uses, or `ui_banner`/`ui_section` signatures differ;
- the icon `globe` and `external-link` both look wrong or missing in `_icons.html` (do not add icons);
- a test fails twice, or the layout lint reports a finding on the new page you cannot fix inside `booking_sites.html` (never silence it, never add to `ALLOW`);
- you want to change CSS, the tab bar, or a file outside section 3;
- you reach 25 tool calls or about 50k tokens (report as `blocked`);
- you need push, merge, secrets, SSH or deploy (hand to the owner).

## 9. Report

Write `docs/tasks/0995-report.md` (600 tokens at most) and set `Status: review`: files changed (`git diff --stat`), each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left. Open one PR; include the per-page UX notes and tick the design-system checklist in the PR body.

## Risk list (for the reviewer)

- `App/app/routes/payments.py` (new route, SQL join, redirect rule)
- `App/app/templates/_shell_sidebar.html` (shared by every host page)
- `App/app/templates/booking_sites.html`

## Owner steps

1. Review the PR and the screenshots in the report.
2. Merge with `scripts/merge-pr-on-green.sh <PR number>` once CI is green.
3. Deploy manually as usual; then open the app, check the sidebar shows "Booking site" for a Free and a Max account.
