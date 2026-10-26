# 0412: Public /cenik price list with the calculator (B8)

Status: todo
Depends on: none (runs in parallel with 0411) | Base commit: 1255954 | Branch: task/0412-cenik-calculator
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Order: after any open brief that also names `tests/static_versions.json` (0219, 0244, 0246, 0344, 0352-0355); rerun step 7 last so the json matches.

## 1. Objective

Replace today's "Dle domluvy" pricing page with the agreed price list: plan cards for UbyHost and UbyHost Max, a calculator (yearly/monthly, number of apartments, TTLock), price bands, founder strip, add-ons, FAQ and a final call to action. The page must work without JavaScript (server shows 1 apartment, yearly); `pricing.js` only updates the numbers.

Payment is by invoice only. Nothing on this page mentions or loads a card gateway.

## 2. Context

Rules that apply (from [rules](../context/rules.md)):

- Copy: strings live in `landing_i18n.py`; EN/CS keys stay in parity; one explanation lives in one place; no sentence the button already says; no em dashes; "no tracking cookies", never "no cookies".
- Light mode only. No third-party script: `pricing.js` is our own file, served from `/static`, no network calls, no storage.
- Template or CSS change: one 390 px screenshot of the changed page in the report. A changed static file gets a new `?v=` key in every template that references it, then `tests/static_versions.json` is rewritten (`.venv/bin/python tests/test_static_versions.py --write`).
- Placeholders in copy are `%(name)s` (not `{name}`); a counted word uses `key`, `key.one`, `key.few` (Czech: 1 / 2–4 / 5+).
- The public term is "ubytovací kniha" / "guest book" (owner decision D-18), never "domovní kniha" on public pages.

Prices (final, per apartment, graduated: each band prices only the apartments in it; bands 1–4, 5–9, 10+):

| | Month | Year |
|---|---|---|
| UbyHost | 149 / 119 / 99 | 1 190 / 950 / 790 |
| Max, on top | 79 / 59 / 39 | 760 / 570 / 370 |
| TTLock (Standard only; included in Max) | 49 per apartment | 470 per apartment |

Display rule: the big number is always per month. Yearly selected: big = year total / 12 rounded half up, small line "Platíte {year total} Kč jednou ročně". Monthly selected: big = month total, small line "S roční platbou jen {year total / 12} Kč / měsíc". Checks: 1 apt → 99 (1 190/yr), 149/mo; Max 1 apt → 163 (1 950/yr), 228/mo; 5 apt → 476 (5 710/yr), 715/mo; 5 apt Max monthly → 1 090.

Layout comes from the owner's design canvas "UbyHost pricing & checkout", artboard "Public pricing page /cenik" (already translated into the template and CSS below; you do not need to open it). Differences from the canvas on purpose: no drop shadow on the Max card (`tests/test_landing_decoration.py` forbids shadows on `.pricing-card`), the founder strip uses the light brand tint, not a dark band.

**Excerpt A**, `App/app/routes/legal.py` lines 60–67:

```python
@router.get("/cenik")
def pricing(request: Request):
    """Public contact-led pricing page."""
    return render(
        request,
        "pricing.html",
        {"show_nav": False, "open_alerts": [], **signup.public_context(request)},
    )
```

**Excerpt B**, `App/app/landing_i18n.py`, the English block (lines 106–139) starts and ends:

```python
        "pricing.page_title": "UbyHost pricing: tailored for your accommodation",
```
```python
        "pricing.final.body": "A short email is enough to start the conversation.",
```

**Excerpt C**, `App/app/landing_i18n.py`, the Czech block (lines 314–347) starts and ends:

```python
        "pricing.page_title": "Ceník UbyHostu: cena dle domluvy",
```
```python
        "pricing.final.body": "Pro začátek stačí krátký e-mail.",
```

**Excerpt D**, `App/app/static/landing.css` line 943 and lines 1046–1048:

```css
/* Contact-led pricing: one honest offer instead of invented SaaS tiers. */
```
```css
  .pricing-price { font-size: clamp(2.6rem, 12vw, 3.6rem); }
  .pricing-includes { padding: 18px; }
}
```

**Excerpt E**, `App/tests/test_public_seo.py` line 132: `def test_pricing_is_contact_led_and_honest_in_both_languages():` through line 157 (the last line of `test_the_pricing_page_answers_the_price_question_in_the_first_sentence`, which is `        assert page.text.index(summary) > price, f"{lang}: the answer is not under the price"`).

**Excerpt F**, `App/tests/test_owner_decisions.py` lines 68–69:

```python
    assert LANDING_STRINGS["en"]["pricing.includes.3"] == "Online guest book"
    assert LANDING_STRINGS["cs"]["pricing.includes.3"] == "Online ubytovací kniha"
```

**Excerpt G**, `App/tests/test_landing_decoration.py` line 44 and lines 209–214:

```python
LANES = (".benefit-list", ".pricing-factor-list", ".product-feature-row")
```
```python
def test_the_pricing_factors_render_as_three_numbered_lanes():
    section = _section(_render("/cenik"), "pricing-factors")
    assert 'class="pricing-factor-list"' in section
    assert section.count("<li>") == 3
    for name in ("properties", "volume", "workflow"):
        assert LANDING_STRINGS["en"][f"pricing.factor.{name}.title"] in section
```

If any excerpt is not found verbatim, STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/legal.py` | edit | price table and the 1-apartment defaults for the template |
| `App/app/templates/pricing.html` | replace | new page |
| `App/app/landing_i18n.py` | edit | replace the `pricing.*` keys, EN and CS |
| `App/app/static/pricing.js` | create | the calculator |
| `App/app/static/landing.css` | edit | replace the pricing block |
| `App/app/templates/landing.html`, `product.html`, `public_guide.html`, `public_legal_base.html` | edit | `landing.css` key only |
| `App/tests/static_versions.json` | rewrite | by the `--write` command |
| `App/tests/test_public_seo.py` | edit | two old pricing tests → two new ones |
| `App/tests/test_owner_decisions.py` | edit | two lines |
| `App/tests/test_landing_decoration.py` | edit | drop the factor lane |
| `App/tests/test_0412_pricing_browser.py` | create | calculator in a real browser |
| `docs/tasks/screenshots-0412/cenik-390.png` | create | screenshot |
| `docs/tasks/0412-report.md` | create | the report |

No other file may change.

## 4. Steps

All commands run from `App/`.

### Step 1. `App/app/routes/legal.py`

Replace Excerpt A with:

```python
# Brief 0412: the public price list in whole Kč. Same numbers as app/billing.py
# (brief 0411); the plan-picker brief replaces this copy with an import and a test.
PUBLIC_RATES = {
    "base": {"month": [149, 119, 99], "year": [1190, 950, 790]},
    "max": {"month": [79, 59, 39], "year": [760, 570, 370]},
    "ttlock": {"month": 49, "year": 470},
}


def _graduated(count: int, rates) -> int:
    """Each band prices only the apartments in it: 1-4, 5-9, 10 and up."""
    return sum(rates[0 if i <= 4 else 1 if i <= 9 else 2] for i in range(1, count + 1))


def _per_month(year_total: int) -> int:
    """A yearly total shown per month, rounded half up like Math.round in pricing.js."""
    return (year_total * 2 + 12) // 24


def _kc(amount: int, lang: str) -> str:
    """1 190 (no-break space) in Czech, 1,190 in English, as pricing.js prints it."""
    text = f"{amount:,}"
    return text.replace(",", " ") if lang == "cs" else text


@router.get("/cenik")
def pricing(request: Request):
    """Public price list with the calculator (brief 0412). Without JS: 1 apartment, yearly."""
    lang = host_i18n.resolve_language(request, default=host_i18n.PUBLIC_DEFAULT_LANGUAGE)
    std_year = _graduated(1, PUBLIC_RATES["base"]["year"])
    max_year = std_year + _graduated(1, PUBLIC_RATES["max"]["year"])
    start = {
        "std_month": _kc(_per_month(std_year), lang),
        "max_month": _kc(_per_month(max_year), lang),
        "std_year": _kc(std_year, lang),
        "max_year": _kc(max_year, lang),
        "bands": [_kc(_per_month(rate), lang) for rate in PUBLIC_RATES["base"]["year"]],
    }
    return render(
        request,
        "pricing.html",
        {
            "show_nav": False,
            "open_alerts": [],
            **signup.public_context(request),
            "rates": PUBLIC_RATES,
            "start": start,
            # The founder counter comes with the plan-picker brief; until then no strip.
            "founder_left": None,
        },
    )
```

Run: `.venv/bin/python -c "from app.routes import legal; print(legal._per_month(1190), legal._per_month(1950), legal._kc(1190, 'cs') == '1 190')" 2>&1 | tail -3`
Expected: `99 163 True`

### Step 2. Replace `App/app/templates/pricing.html` with this whole file

```html
<!doctype html>
<html lang="{{ lang }}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#f7f7f5">
  <title>{{ t('pricing.page_title') }}</title>
  <meta name="description" content="{{ t('pricing.meta_description') }}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{{ canonical_url }}">
  {% for code, href in alternate_urls %}
  <link rel="alternate" hreflang="{{ code }}" href="{{ href }}">
  {% endfor %}
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="UbyHost">
  <meta property="og:title" content="{{ t('pricing.page_title') }}">
  <meta property="og:description" content="{{ t('pricing.meta_description') }}">
  <meta property="og:url" content="{{ canonical_url }}">
  <meta property="og:locale" content="{{ 'cs_CZ' if lang == 'cs' else 'en_US' }}">
  <meta property="og:image" content="{{ public_base_url }}/static/apple-touch-icon.png">
  <meta name="twitter:card" content="summary">
  <link rel="icon" type="image/png" sizes="64x64" href="/static/favicon.png?v=20261004a">
  <link rel="apple-touch-icon" sizes="180x180" href="/static/apple-touch-icon.png?v=20261004a">
  <link rel="stylesheet" href="/static/tokens.css?v=20261022-0284">
  <link rel="stylesheet" href="/static/landing.css?v=20261026-0412">
  <script type="application/ld+json">
  {{ {
    "@context": "https://schema.org",
    "@type": "WebPage",
    "name": t("pricing.page_title"),
    "description": t("pricing.meta_description"),
    "url": canonical_url,
    "inLanguage": lang,
    "isPartOf": {"@type": "WebSite", "name": "UbyHost", "url": public_base_url ~ "/"}
  } | tojson }}
  </script>
  <script type="application/ld+json">
  {{ {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": [
      {"@type": "Question", "name": t("pricing.faq.1.q"), "acceptedAnswer": {"@type": "Answer", "text": t("pricing.faq.1.a")}},
      {"@type": "Question", "name": t("pricing.faq.2.q"), "acceptedAnswer": {"@type": "Answer", "text": t("pricing.faq.2.a")}},
      {"@type": "Question", "name": t("pricing.faq.3.q"), "acceptedAnswer": {"@type": "Answer", "text": t("pricing.faq.3.a")}},
      {"@type": "Question", "name": t("pricing.faq.4.q"), "acceptedAnswer": {"@type": "Answer", "text": t("pricing.faq.4.a")}},
      {"@type": "Question", "name": t("pricing.faq.5.q"), "acceptedAnswer": {"@type": "Answer", "text": t("pricing.faq.5.a")}},
      {"@type": "Question", "name": t("pricing.faq.6.q"), "acceptedAnswer": {"@type": "Answer", "text": t("pricing.faq.6.a")}},
      {"@type": "Question", "name": t("pricing.faq.7.q"), "acceptedAnswer": {"@type": "Answer", "text": t("pricing.faq.7.a")}},
      {"@type": "Question", "name": t("pricing.faq.8.q"), "acceptedAnswer": {"@type": "Answer", "text": t("pricing.faq.8.a")}},
      {"@type": "Question", "name": t("pricing.faq.9.q"), "acceptedAnswer": {"@type": "Answer", "text": t("pricing.faq.9.a")}}
    ]
  } | tojson }}
  </script>
  {% include "_posthog.html" %}
</head>
<body>
{% set active = 'pricing' %}{% set switch_path = '/cenik' %}
{% set cta_event = 'signup_start' if signup_href else 'login_click' %}
{% macro cta_href(plan, interval='year') -%}
{%- if signup_href -%}{{ signup_href }}&plan={{ plan }}&interval={{ interval }}&apts=1{%- else -%}/login?lang={{ lang }}{%- endif -%}
{%- endmacro %}
{% macro tick() -%}
<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><path d="M4 9.5l3 3 7-7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
{%- endmacro %}
{% include "_public_header.html" %}

  <main id="content" class="pricing-page">
    <section class="pricing-hero" aria-labelledby="pricing-title">
      <p class="landing-eyebrow">{{ t('pricing.eyebrow') }}</p>
      <h1 id="pricing-title">{{ t('pricing.title') }}</h1>
      <p class="pricing-lede">{{ t('pricing.lede') }}</p>
      <ul class="pricing-chips">
        {% for chip in t('pricing.chips').split(' · ') %}<li>{{ chip }}</li>{% endfor %}
      </ul>
    </section>

    <section class="pricing-calc" aria-label="{{ t('pricing.calc.label') }}" data-pricing-calc hidden
      data-rates='{{ rates | tojson }}' data-lang="{{ lang }}" data-signup-base="{{ signup_href or '' }}"
      data-billed-year="{{ t('pricing.billed_year') }}" data-month-hint="{{ t('pricing.month_hint') }}"
      data-apts-one="{{ t('pricing.apts.one') }}" data-apts-few="{{ t('pricing.apts.few') }}" data-apts-many="{{ t('pricing.apts') }}"
      data-std-note="{{ t('pricing.std.note') }}" data-std-note-ttlock="{{ t('pricing.std.note_ttlock') }}"
      data-unit-year="{{ t('pricing.bands.unit_year') }}" data-unit-month="{{ t('pricing.bands.unit_month') }}">
      <div class="pricing-toggle" role="group" aria-label="{{ t('pricing.toggle.label') }}">
        <button type="button" data-interval="year" aria-pressed="true">{{ t('pricing.toggle.year') }}<span>{{ t('pricing.toggle.year_badge') }}</span></button>
        <button type="button" data-interval="month" aria-pressed="false">{{ t('pricing.toggle.month') }}</button>
      </div>
      <div class="pricing-stepper">
        <span id="pricing-count-label">{{ t('pricing.count.label') }}</span>
        <button type="button" data-step="-1" aria-label="{{ t('pricing.count.dec') }}">−</button>
        <output aria-labelledby="pricing-count-label" aria-live="polite" data-count>1</output>
        <button type="button" data-step="1" aria-label="{{ t('pricing.count.inc') }}">+</button>
      </div>
      <label class="pricing-ttlock"><input type="checkbox" data-ttlock>{{ t('pricing.ttlock.label') }}</label>
    </section>

    <section class="pricing-plans" aria-label="{{ t('pricing.std.name') }}, {{ t('pricing.max.name') }}">
      <article class="pricing-card" data-plan="standard">
        <div class="pricing-card-head">
          <div><h2>{{ t('pricing.std.name') }}</h2><p>{{ t('pricing.std.tagline') }}</p></div>
          <img src="/static/ubyhost-mark.png?v=20261004a" alt="">
        </div>
        <p class="pricing-price"><strong data-total>{{ start.std_month }}</strong> {{ t('pricing.currency') }} {{ t('pricing.per_month') }}</p>
        <p class="pricing-sub" data-sub>{{ t('pricing.billed_year', amount=start.std_year) }}</p>
        <p class="pricing-meta"><span data-apts>{{ tp('pricing.apts', 1) }}</span> · <span data-note>{{ t('pricing.std.note') }}</span></p>
        <a class="landing-button primary pricing-button" data-cta-plan="standard" href="{{ cta_href('standard') }}" data-analytics-event="{{ cta_event }}">{{ t('pricing.cta') }}</a>
        <ul class="pricing-features">
          {% for n in range(1, 7) %}<li>{{ tick() }}{{ t('pricing.std.f' ~ n) }}</li>{% endfor %}
        </ul>
      </article>
      <article class="pricing-card pricing-card-max" data-plan="max">
        <div class="pricing-card-head">
          <div><h2>{{ t('pricing.max.name') }}</h2><p>{{ t('pricing.max.tagline') }}</p></div>
          <span class="pricing-badge">{{ t('pricing.max.badge') }}</span>
        </div>
        <p class="pricing-price"><strong data-total>{{ start.max_month }}</strong> {{ t('pricing.currency') }} {{ t('pricing.per_month') }}</p>
        <p class="pricing-sub" data-sub>{{ t('pricing.billed_year', amount=start.max_year) }}</p>
        <p class="pricing-meta"><span data-apts>{{ tp('pricing.apts', 1) }}</span> · <span>{{ t('pricing.max.note') }}</span></p>
        <a class="landing-button primary pricing-button" data-cta-plan="max" href="{{ cta_href('max') }}" data-analytics-event="{{ cta_event }}">{{ t('pricing.cta') }}</a>
        <ul class="pricing-features">
          {% for n in range(1, 6) %}<li>{{ tick() }}{{ t('pricing.max.f' ~ n) }}</li>{% endfor %}
        </ul>
      </article>
    </section>
    <p class="pricing-fineprint">{{ t('pricing.cta_note') }} {{ t('pricing.prices_final') }}</p>

    <section class="pricing-bands" aria-labelledby="bands-title">
      <div>
        <h2 id="bands-title">{{ t('pricing.bands.title') }}</h2>
        <p>{{ t('pricing.bands.body') }}</p>
      </div>
      <ol class="pricing-band-list">
        {% for i in range(3) %}
        <li><span>{{ t('pricing.bands.b' ~ (i + 1)) }}</span><strong><span data-band="{{ i }}">{{ start.bands[i] }}</span> {{ t('pricing.currency') }}</strong><span data-unit>{{ t('pricing.bands.unit_year') }}</span></li>
        {% endfor %}
      </ol>
    </section>

    {% if founder_left %}
    <section class="pricing-founder" aria-labelledby="founder-title">
      <div>
        <h2 id="founder-title">{{ t('pricing.founder.heading') }}</h2>
        <p>{{ t('pricing.founder.body', n=founder_left) }}</p>
      </div>
      <a class="landing-button secondary" data-cta-plan="standard" data-cta-interval="year" href="{{ cta_href('standard') }}" data-analytics-event="{{ cta_event }}">{{ t('pricing.founder.cta') }}</a>
    </section>
    {% endif %}

    <section class="pricing-addons" aria-labelledby="addons-title">
      <h2 id="addons-title">{{ t('pricing.addons.title') }}</h2>
      <ul>
        <li>{{ t('pricing.addon.ttlock') }}</li>
        <li>{{ t('pricing.addon.wl') }}</li>
      </ul>
    </section>

    <section class="pricing-anchor" aria-labelledby="anchor-title">
      <h2 id="anchor-title">{{ t('pricing.anchor.title') }}</h2>
      <p>{{ t('pricing.anchor.body') }}</p>
    </section>

    {% include "_privacy_first.html" %}

    <section class="pricing-faq" aria-labelledby="faq-title">
      <h2 id="faq-title">{{ t('pricing.faq.title') }}</h2>
      <div class="pricing-faq-list">
        {% for n in range(1, 10) %}
        <details><summary>{{ t('pricing.faq.' ~ n ~ '.q') }}</summary><p>{{ t('pricing.faq.' ~ n ~ '.a') }}</p></details>
        {% endfor %}
      </div>
    </section>

    <section class="landing-final pricing-final">
      <img src="/static/ubyhost-mark.png?v=20261004a" alt="">
      <h2>{{ t('pricing.final.title') }}</h2>
      <a class="landing-button primary pricing-button" data-cta-plan="standard" href="{{ cta_href('standard') }}" data-analytics-event="{{ cta_event }}">{{ t('pricing.cta') }}</a>
      <p>{{ t('pricing.final.large') }} <a href="mailto:support@ubyhost.com?subject={{ t('pricing.final.subject') | urlencode }}" data-analytics-event="contact_click">{{ t('pricing.final.write') }}</a></p>
    </section>
  </main>

{% include "_public_footer.html" %}
<script src="/static/pricing.js?v=20261026-0412" defer></script>
</body>
</html>
```

Run: `.venv/bin/python -c "from fastapi.testclient import TestClient; from app.main import app; r = TestClient(app).get('/cenik?lang=cs'); print(r.status_code, 'data-pricing-calc' in r.text)" 2>&1 | tail -3`
(Run it after step 3; the page needs the new keys.) Expected: `200 True`

### Step 3. `App/app/landing_i18n.py`: the English keys

Replace every line from Excerpt B's first line through its last line (the whole English `pricing.*` block, lines 106–139) with:

```python
        "pricing.page_title": "UbyHost pricing: guest reporting from 99 CZK a month",
        "pricing.meta_description": (
            "Automatic UbyPort reporting with receipts, guest book and stay fee. "
            "No guest limits. 30 days free."
        ),
        "pricing.eyebrow": "No guest limits · No paperwork · No fines",
        "pricing.title": "Guest reporting for 99 CZK a month.",
        "pricing.lede": (
            "Guests register themselves, UbyPort gets the report, you get the receipt. "
            "You pay per apartment, not per guest."
        ),
        "pricing.chips": "30 days free · No card · Cancel anytime",
        "pricing.calc.label": "Price calculator",
        "pricing.toggle.label": "Billing",
        "pricing.toggle.year": "Yearly",
        "pricing.toggle.year_badge": "save 33%",
        "pricing.toggle.month": "Monthly",
        "pricing.count.label": "Apartments",
        "pricing.count.dec": "Remove an apartment",
        "pricing.count.inc": "Add an apartment",
        "pricing.ttlock.label": "I have TTLock smart locks",
        "pricing.currency": "CZK",
        "pricing.per_month": "/ month",
        "pricing.billed_year": "Billed %(amount)s CZK once a year",
        "pricing.month_hint": "Only %(price)s CZK / month billed yearly",
        "pricing.apts.one": "%(count)s apartment",
        "pricing.apts.few": "%(count)s apartments",
        "pricing.apts": "%(count)s apartments",
        "pricing.std.name": "UbyHost",
        "pricing.std.tagline": "Everything for worry-free reporting",
        "pricing.std.f1": "Automatic UbyPort reports with receipts",
        "pricing.std.f2": "Online check-in, 6-year guest book",
        "pricing.std.f3": "Duplicate protection",
        "pricing.std.f4": "Stay fee report and QR payment",
        "pricing.std.f5": "Leon answers guests 24/7",
        "pricing.std.f6": "Unlimited guests, stays and teammates",
        "pricing.std.note": "no guest limits",
        "pricing.std.note_ttlock": "incl. TTLock",
        "pricing.max.name": "UbyHost Max",
        "pricing.max.badge": "Only here: AI concierge",
        "pricing.max.tagline": "For hosts who want calm even in high season",
        "pricing.max.f1": "Everything in UbyHost",
        "pricing.max.f2": "3× more answers from Leon and Havel",
        "pricing.max.f3": "TTLock smart locks included",
        "pricing.max.f4": "Priority support",
        "pricing.max.f5": "New features first",
        "pricing.max.note": "TTLock included",
        "pricing.cta": "Try free for 30 days",
        "pricing.cta_note": "The trial starts when UbyPort is connected.",
        "pricing.prices_final": "Prices are final.",
        "pricing.bands.title": "More apartments, lower price",
        "pricing.bands.body": (
            "Discounts stack: the first 4 at full price, the 5th to 9th cheaper, "
            "from the 10th cheapest."
        ),
        "pricing.bands.b1": "1st–4th apartment",
        "pricing.bands.b2": "5th–9th apartment",
        "pricing.bands.b3": "10th apartment and up",
        "pricing.bands.unit_year": "per apartment a month, billed yearly",
        "pricing.bands.unit_month": "per apartment a month",
        "pricing.founder.heading": "Founding hosts: 74 CZK a month",
        "pricing.founder.body": "890 CZK a year per apartment, price locked for 2 years. %(n)s of 100 places left.",
        "pricing.founder.cta": "Claim a place",
        "pricing.addons.title": "Add-ons",
        "pricing.addon.ttlock": "TTLock smart locks: a code per stay, +49 CZK per apartment a month (free in Max)",
        "pricing.addon.wl": "White-label for agencies: +590 CZK a month",
        "pricing.anchor.title": "Cheaper than one mistake",
        "pricing.anchor.body": "A year of UbyHost costs 1,190 CZK. An unreported guest can cost up to 50,000 CZK.",
        "pricing.faq.title": "Questions and answers",
        "pricing.faq.1.q": "When does the trial start?",
        "pricing.faq.1.a": (
            "Once we have verified your UbyPort access, 7 days after sign-up at the latest. "
            "So you get 30 days of real reporting."
        ),
        "pricing.faq.2.q": "What counts as an apartment?",
        "pricing.faq.2.a": "Every listing with its own calendar. Guests, stays and teammates are unlimited.",
        "pricing.faq.3.q": "Do I need a card?",
        "pricing.faq.3.a": "No. You pay by bank transfer on an invoice we send after the trial.",
        "pricing.faq.4.q": "What if I add an apartment?",
        "pricing.faq.4.a": (
            "The price adjusts automatically and you pay only the remaining part. "
            "When you remove an apartment, the lower price applies from the next period."
        ),
        "pricing.faq.5.q": "Can I cancel anytime?",
        "pricing.faq.5.a": (
            "Yes. The service runs until the end of the paid period and you can download "
            "the guest book at any time."
        ),
        "pricing.faq.6.q": "Can I get an invoice for my company?",
        "pricing.faq.6.a": "Yes, with your company ID and VAT ID. We fill in the details from the ARES register.",
        "pricing.faq.7.q": "What if I pay late?",
        "pricing.faq.7.a": (
            "We send a reminder. Everything keeps running for 30 days after the due date, "
            "and we never stop reporting guests who are already registered."
        ),
        "pricing.faq.8.q": "How do I pay?",
        "pricing.faq.8.a": (
            "By bank transfer on the invoice: scan the QR code in your banking app. "
            "We match the payment ourselves. Card payments are coming soon."
        ),
        "pricing.faq.9.q": "What about eTurista?",
        "pricing.faq.9.a": (
            "It is not law yet and the state has not published its interface. Once it does, "
            "we connect to it and move your data over with no retyping."
        ),
        "pricing.final.title": "Start today, pay in 30 days",
        "pricing.final.large": "10 or more apartments?",
        "pricing.final.write": "Write to us.",
        "pricing.final.subject": "UbyHost for 10 or more apartments",
```

### Step 4. `App/app/landing_i18n.py`: the Czech keys

Replace every line from Excerpt C's first line through its last line (the whole Czech `pricing.*` block, lines 314–347 before step 3; find it by its first line) with:

```python
        "pricing.page_title": "Ceník UbyHostu: hlášení cizinců od 99 Kč měsíčně",
        "pricing.meta_description": (
            "Automatické hlášení do UbyPortu s doručenkou, ubytovací kniha a poplatek "
            "z pobytu. Bez limitu hostů. 30 dní zdarma."
        ),
        "pricing.eyebrow": "Bez limitu hostů · Bez papírování · Bez pokut",
        "pricing.title": "Hlášení cizinců za 99 Kč měsíčně.",
        "pricing.lede": (
            "Host se zapíše sám, UbyPort dostane hlášení, vy doručenku. "
            "Platíte za apartmán, ne za hosty."
        ),
        "pricing.chips": "30 dní zdarma · Bez platební karty · Zrušíte kdykoli",
        "pricing.calc.label": "Kalkulačka ceny",
        "pricing.toggle.label": "Fakturace",
        "pricing.toggle.year": "Ročně",
        "pricing.toggle.year_badge": "ušetříte 33 %",
        "pricing.toggle.month": "Měsíčně",
        "pricing.count.label": "Počet apartmánů",
        "pricing.count.dec": "Ubrat apartmán",
        "pricing.count.inc": "Přidat apartmán",
        "pricing.ttlock.label": "Mám chytré zámky TTLock",
        "pricing.currency": "Kč",
        "pricing.per_month": "/ měsíc",
        "pricing.billed_year": "Platíte %(amount)s Kč jednou ročně",
        "pricing.month_hint": "S roční platbou jen %(price)s Kč / měsíc",
        "pricing.apts.one": "%(count)s apartmán",
        "pricing.apts.few": "%(count)s apartmány",
        "pricing.apts": "%(count)s apartmánů",
        "pricing.std.name": "UbyHost",
        "pricing.std.tagline": "Vše pro bezstarostné hlášení",
        "pricing.std.f1": "Automatické hlášení do UbyPortu s doručenkou",
        "pricing.std.f2": "Online check-in, ubytovací kniha na 6 let",
        "pricing.std.f3": "Ochrana proti duplicitám",
        "pricing.std.f4": "Poplatek z pobytu a QR platba",
        "pricing.std.f5": "Leon odpovídá hostům 24/7",
        "pricing.std.f6": "Neomezeně hostů, pobytů i kolegů",
        "pricing.std.note": "bez limitu hostů",
        "pricing.std.note_ttlock": "vč. TTLock",
        "pricing.max.name": "UbyHost Max",
        "pricing.max.badge": "Jen u nás: AI concierge",
        "pricing.max.tagline": "Pro hostitele, kteří chtějí klid i v sezóně",
        "pricing.max.f1": "Vše z UbyHostu",
        "pricing.max.f2": "3× víc odpovědí od Leona a Havla",
        "pricing.max.f3": "Chytré zámky TTLock v ceně",
        "pricing.max.f4": "Přednostní podpora",
        "pricing.max.f5": "Nové funkce jako první",
        "pricing.max.note": "TTLock v ceně",
        "pricing.cta": "Vyzkoušet 30 dní zdarma",
        "pricing.cta_note": "Zkušební doba začne, až propojíte UbyPort.",
        "pricing.prices_final": "Ceny jsou konečné.",
        "pricing.bands.title": "Čím víc apartmánů, tím nižší cena",
        "pricing.bands.body": (
            "Sleva se počítá postupně: první 4 za plnou cenu, 5. až 9. levněji, "
            "od 10. nejlevněji."
        ),
        "pricing.bands.b1": "1.–4. apartmán",
        "pricing.bands.b2": "5.–9. apartmán",
        "pricing.bands.b3": "od 10. apartmánu",
        "pricing.bands.unit_year": "za apartmán měsíčně, placeno ročně",
        "pricing.bands.unit_month": "za apartmán měsíčně",
        "pricing.founder.heading": "Zakládající hostitelé: 74 Kč měsíčně",
        "pricing.founder.body": "890 Kč ročně za apartmán, cena zamčená na 2 roky. Zbývá %(n)s ze 100 míst.",
        "pricing.founder.cta": "Získat místo",
        "pricing.addons.title": "Doplňky",
        "pricing.addon.ttlock": "Chytré zámky TTLock: kód pro každý pobyt, +49 Kč za apartmán měsíčně (v Max zdarma)",
        "pricing.addon.wl": "Vlastní značka pro agentury: +590 Kč měsíčně",
        "pricing.anchor.title": "Levnější než jedna chyba",
        "pricing.anchor.body": "Rok UbyHostu stojí 1 190 Kč. Za nenahlášeného hosta hrozí pokuta až 50 000 Kč.",
        "pricing.faq.title": "Časté dotazy",
        "pricing.faq.1.q": "Kdy začne zkušební doba?",
        "pricing.faq.1.a": (
            "Až ověříme vaše přístupy do UbyPortu, nejpozději 7 dní po registraci. "
            "Máte tak 30 dní skutečného hlášení."
        ),
        "pricing.faq.2.q": "Co se počítá jako apartmán?",
        "pricing.faq.2.a": "Každá nabídka s vlastním kalendářem. Hostů, pobytů a kolegů je neomezeně.",
        "pricing.faq.3.q": "Musím zadávat kartu?",
        "pricing.faq.3.a": "Ne. Platíte převodem na fakturu, kterou pošleme až po zkušební době.",
        "pricing.faq.4.q": "Co když přidám apartmán?",
        "pricing.faq.4.a": (
            "Cena se upraví automaticky, doplatíte jen poměrnou část. Když apartmán "
            "odeberete, nižší cena platí od dalšího období."
        ),
        "pricing.faq.5.q": "Můžu zrušit kdykoli?",
        "pricing.faq.5.a": (
            "Ano. Služba běží do konce zaplaceného období a ubytovací knihu si můžete "
            "kdykoli stáhnout."
        ),
        "pricing.faq.6.q": "Dostanu fakturu na firmu?",
        "pricing.faq.6.a": "Ano, s IČO a DIČ. Údaje doplníme z ARES.",
        "pricing.faq.7.q": "Co když fakturu nestihnu zaplatit?",
        "pricing.faq.7.a": (
            "Připomeneme se. Ještě 30 dní po splatnosti běží vše dál a hlášení už "
            "registrovaných hostů nikdy nezastavíme."
        ),
        "pricing.faq.8.q": "Jak platit?",
        "pricing.faq.8.a": (
            "Převodem na fakturu, stačí naskenovat QR kód v bankovní aplikaci. "
            "Platbu spárujeme sami. Platba kartou přibude brzy."
        ),
        "pricing.faq.9.q": "Co eTurista?",
        "pricing.faq.9.a": (
            "Zákon zatím neplatí a stát nezveřejnil rozhraní. Jakmile ho zveřejní, "
            "napojíme se a vaše data převedeme bez přepisování."
        ),
        "pricing.final.title": "Začněte dnes, platit budete až za 30 dní",
        "pricing.final.large": "10 a více apartmánů?",
        "pricing.final.write": "Napište nám.",
        "pricing.final.subject": "UbyHost pro 10 a více apartmánů",
```

Run: `.venv/bin/python -c "from app.landing_i18n import LANDING_STRINGS as L; en={k for k in L['en'] if k.startswith('pricing.')}; cs={k for k in L['cs'] if k.startswith('pricing.')}; print(len(en), en == cs)" 2>&1 | tail -3`
Expected: `82 True`

Then run the step 2 check. Expected: `200 True`.

### Step 5. Create `App/app/static/pricing.js`

Copy the reviewed file (do not retype it):

```
cp ../docs/plans/cenik-0412/pricing.js app/static/pricing.js
grep -c 'localStorage\|fetch(\|XMLHttpRequest\|document.cookie' app/static/pricing.js
```

Expected: `0`.

### Step 6. `App/app/static/landing.css`: replace the pricing block

1. The new block is in `docs/plans/cenik-0412/pricing-block.css` (reviewed; do not retype it).

2. Replace lines 943–1048 of `landing.css` with it:

```
.venv/bin/python - <<'EOF'
from pathlib import Path
p = Path("app/static/landing.css")
lines = p.read_text(encoding="utf-8").split("\n")
assert lines[942] == "/* Contact-led pricing: one honest offer instead of invented SaaS tiers. */", lines[942]
assert lines[1045] == "  .pricing-price { font-size: clamp(2.6rem, 12vw, 3.6rem); }", lines[1045]
assert lines[1046] == "  .pricing-includes { padding: 18px; }", lines[1046]
assert lines[1047] == "}", lines[1047]
new = Path("../docs/plans/cenik-0412/pricing-block.css").read_text(encoding="utf-8").rstrip("\n").split("\n")
p.write_text("\n".join(lines[:942] + new + lines[1048:]), encoding="utf-8")
print("replaced 106 lines with", len(new))
EOF
```

Expected: `replaced 106 lines with` and a number. If an `assert` fails, STOP (§8).

Run: `grep -c 'pricing-factor\|pricing-includes\|pricing-hero-copy' app/static/landing.css`
Expected: `0`

### Step 7. New `?v=` key for `landing.css`, register `pricing.js`

```
sed -i 's/landing\.css?v=20260919y/landing.css?v=20261026-0412/' app/templates/landing.html app/templates/product.html app/templates/public_guide.html app/templates/public_legal_base.html
grep -rho 'landing.css?v=[^"]*' app/templates | sort | uniq -c
.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5
```

Expected: `5 landing.css?v=20261026-0412` (pricing.html already has it from step 2), and the json rewritten with `landing.css` and a new `pricing.js` entry.

### Step 8. `App/tests/test_public_seo.py`

Replace the two functions of Excerpt E (from `def test_pricing_is_contact_led_and_honest_in_both_languages():` through `        assert page.text.index(summary) > price, f"{lang}: the answer is not under the price"`) with:

```python
def test_pricing_shows_the_price_list_in_both_languages():
    for lang in ("cs", "en"):
        strings = LANDING_STRINGS[lang]
        page = _client().get(f"/cenik?lang={lang}")
        assert page.status_code == 200
        assert strings["pricing.title"] in page.text
        assert strings["pricing.cta"] in page.text
        assert strings["pricing.std.f1"] in page.text
        assert strings["pricing.max.f2"] in page.text
        assert strings["pricing.faq.9.q"] in page.text
        assert '"@type": "WebPage"' in page.text
        assert '"@type": "FAQPage"' in page.text
        assert f'hreflang="{lang}"' in page.text
        assert "Dle domluvy" not in page.text and "By agreement" not in page.text
        assert "stripe" not in page.text.lower()


def test_without_javascript_the_page_shows_one_apartment_billed_yearly():
    """The server renders the default (1 apartment, yearly, shown per month); JS only updates it."""
    cs = _client().get("/cenik?lang=cs").text
    assert "<strong data-total>99</strong>" in cs
    assert "<strong data-total>163</strong>" in cs
    assert "Platíte 1 190 Kč jednou ročně" in cs
    assert "Platíte 1 950 Kč jednou ročně" in cs
    assert "1 apartmán" in cs
    assert "data-pricing-calc hidden" in cs
    en = _client().get("/cenik?lang=en").text
    assert "Billed 1,190 CZK once a year" in en
```

### Step 9. `App/tests/test_owner_decisions.py`

Replace Excerpt F with:

```python
    assert LANDING_STRINGS["en"]["pricing.std.f2"] == "Online check-in, 6-year guest book"
    assert LANDING_STRINGS["cs"]["pricing.std.f2"] == "Online check-in, ubytovací kniha na 6 let"
```

### Step 10. `App/tests/test_landing_decoration.py`

1. Replace the `LANES` line of Excerpt G with `LANES = (".benefit-list", ".product-feature-row")`.
2. Delete the whole function `test_the_pricing_factors_render_as_three_numbered_lanes` (the six lines of Excerpt G) and one of the two blank lines that followed it.

### Step 11. Create `App/tests/test_0412_pricing_browser.py`

```python
"""0412: the /cenik calculator in a real browser: numbers update, nothing scrolls sideways."""
from __future__ import annotations

import os
import socket
import threading
import time
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

import uvicorn

from app import db
from app.main import app
from tests.browser_support import chromium_launch_kwargs

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0412"


@pytest.fixture(scope="module")
def base():
    db.init_db()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("the pricing test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def _browser(playwright):
    try:
        return playwright.chromium.launch(**chromium_launch_kwargs())
    except Exception:
        if REQUIRE_BROWSER:
            raise
        pytest.skip("Chromium is required for the pricing calculator test")


def test_the_calculator_updates_and_fits_a_phone(base):
    capture = os.environ.get("UBYHOST_CAPTURE_0412") == "1"
    if capture:
        EVIDENCE.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        for width in (390, 1280):
            page = browser.new_page(viewport={"width": width, "height": 900})
            page.goto(f"{base}/cenik?lang=cs")
            page.wait_for_load_state("networkidle")
            assert page.locator("[data-pricing-calc]").is_visible(), width
            std = page.locator('[data-plan="standard"] [data-total]')
            top = page.locator('[data-plan="max"] [data-total]')
            assert (std.inner_text(), top.inner_text()) == ("99", "163"), width
            if capture and width == 390:
                page.screenshot(path=str(EVIDENCE / "cenik-390.png"), full_page=True)
            for _ in range(4):
                page.locator('[data-step="1"]').click()
            assert page.locator("[data-count]").inner_text() == "5", width
            assert std.inner_text() == "476", width  # 5 710 / 12
            assert page.locator('[data-plan="standard"] [data-apts]').inner_text() == "5 apartmánů", width
            page.locator('[data-interval="month"]').click()
            assert (std.inner_text(), top.inner_text()) == ("715", "1 090"), width
            page.locator("[data-ttlock]").check()
            assert std.inner_text() == "960", width  # 715 + 5 x 49
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), width
            page.close()
        browser.close()
```

Run: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_CAPTURE_0412=1 .venv/bin/python -m pytest tests/test_0412_pricing_browser.py -q -rs --tb=short -x 2>&1 | tail -30`
Expected: `1 passed`, 0 skipped, and `docs/tasks/screenshots-0412/cenik-390.png` exists. Look at the screenshot once: cards stacked, no text cut off, no sideways scroll. If Chromium is missing, install it as in [rules: guest pages](../context/rules.md#guest-pages) (`pip install playwright==1.63.0 && python -m playwright install chromium`); a skip is a failure.

### Step 12. Run §6, write the report.

## 5. Do not touch

- `App/app/billing.py` and anything brief 0411 creates; `App/app/signup.py`, `App/app/routes/signup.py`; `_public_header.html`, `_public_footer.html`, `_privacy_first.html`, `_posthog.html`.
- No new dependency, no third-party script, no cookie or `localStorage` in `pricing.js`.
- No card-payment wording beyond FAQ 8's "Platba kartou přibude brzy." / "Card payments are coming soon."
- Never push to `main`.

## 6. Commands

From `App/`:

```
.venv/bin/python -m pytest tests/test_public_seo.py tests/test_public_chrome.py tests/test_public_copy_i18n.py tests/test_landing_canonical.py tests/test_landing_dead_css.py tests/test_landing_decoration.py tests/test_owner_decisions.py tests/test_logo_placements.py tests/test_signup.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_privacy_first.py tests/test_no_tracking.py tests/test_umami_guard.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0412_pricing_browser.py -q -rs --tb=short -x 2>&1 | tail -30
```

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` → ends with `context lint: OK`.

## 7. Acceptance

- [ ] `/cenik?lang=cs` without JS shows "99 Kč / měsíc" (UbyHost) and "163 Kč / měsíc" (Max) with "Platíte 1 190 Kč jednou ročně" / "Platíte 1 950 Kč jednou ročně" (test passes).
- [ ] In the browser: 5 apartments yearly → 476; monthly → 715 and 1 090; TTLock on → 960 (test passes, 0 skipped).
- [ ] EN and CS have the same 82 `pricing.*` keys; no `pricing.card.*`, `pricing.includes.*`, `pricing.factor*` key is left.
- [ ] No "domovní kniha" on the page (`curl`-free check: `grep -c 'domovní' app/landing_i18n.py` is unchanged from before, and the new `pricing.*` lines contain none).
- [ ] `screenshots-0412/cenik-390.png` exists and shows no sideways scroll.
- [ ] `git diff --stat` lists only the files in §3.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/0412-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/templates/pricing.html`: the `cta_href` macro keeps the signed sign-up link intact (`test_signup.py`), `data-rates` JSON in a single-quoted attribute.
- `App/app/static/pricing.js`: rounding (`Math.round`) must match `_per_month` in `routes/legal.py`.
- `App/app/landing_i18n.py`: EN/CS parity, `%(name)s` placeholders.

## Owner steps

1. Open the PR's 390 px screenshot and check the page reads well on a phone.
2. After merge, deploy as usual and open https://ubyhost.com/cenik on your phone: change the apartment count and switch Ročně/Měsíčně once.
