# 0033 — Public tracker swap

Status: review
Depends on: none | Base commit: the plan merge | Branch: task/0033-posthog-public
Executor: Composer 2.5 | Fits one session

**Objective.** Replace the Umami tag with a PostHog cookieless snippet on the same public pages, and rename the click attribute. The sign-up and verify pages stay dark.

**Context.** Anchors the executor must find verbatim. If one is missing, stop.

[App/app/config.py](App/app/config.py), the Umami block starts:

```
# Umami Cloud page analytics, public marketing and legal pages only (WP09).
```

[App/app/templating.py](App/app/templating.py):

```
    data["umami_tag"] = analytics.tag() if analytics.mark_public_page(request, name) else None
```

and:

```
    data["umami_tag"] = None  # permanent rule: guest pages are never measured
```

[App/tests/test_umami_guard.py](App/tests/test_umami_guard.py):

```
def test_the_sign_up_pages_never_carry_umami(umami_on, monkeypatch):
    # WP20/WP21: /signup reads gclid and fbclid; it is an auth page, no tag.
```

**Files.**

- [App/app/analytics.py](App/app/analytics.py) — rewrite. Same `PUBLIC_ANALYTICS_TEMPLATES`. `enabled()` is true only when `POSTHOG_PROJECT_API_KEY` is non-empty, both hosts are `https` origins, and neither host contains `us.i.posthog.com` or `us-assets.i.posthog.com`. `script_origin()` returns the assets host. `connect_origins()` returns the API host. `tag()` returns `api_key`, `api_host`, `assets_host`, or None. Keep `mark_public_page` and `is_public_page`.
- [App/app/config.py](App/app/config.py) — delete the four `UMAMI_*` assignments. Add `POSTHOG_PROJECT_API_KEY` (default empty), `POSTHOG_HOST` (default `https://eu.i.posthog.com`, strip trailing slash), `POSTHOG_ASSETS_HOST` (default `https://eu-assets.i.posthog.com`, strip trailing slash).
- [App/app/main.py](App/app/main.py) — comments only, so they say PostHog. Keep calling `analytics.script_origin()` and `analytics.connect_origins()`.
- [App/app/templating.py](App/app/templating.py) — `umami_tag` becomes `analytics_tag` in both assignments.
- [App/app/templates/_umami.html](App/app/templates/_umami.html) — delete. Add [App/app/templates/_posthog.html](App/app/templates/_posthog.html).
- Includes of `_umami.html` become `_posthog.html` in [landing.html](App/app/templates/landing.html), [product.html](App/app/templates/product.html), [pricing.html](App/app/templates/pricing.html), [public_guide.html](App/app/templates/public_guide.html), [public_legal_base.html](App/app/templates/public_legal_base.html).
- `data-umami-event` becomes `data-analytics-event` in those templates plus [\_public_header.html](App/app/templates/_public_header.html), [\_public_footer.html](App/app/templates/_public_footer.html), [legal.html](App/app/templates/legal.html), [privacy.html](App/app/templates/privacy.html), [dpa.html](App/app/templates/dpa.html). Allowed values stay `login_click`, `contact_click`, `signup_start`. No new events.
- [App/app/templates/privacy.html](App/app/templates/privacy.html) — `{% if umami_tag %}` becomes `{% if analytics_tag %}`. The opt-out script src becomes `/static/analytics-optout.js?v=20261010a`.
- [App/app/static/umami-optout.js](App/app/static/umami-optout.js) — delete. Add [App/app/static/analytics-optout.js](App/app/static/analytics-optout.js) with the same behaviour and `var KEY = "ubyhost.analytics.disabled"`.
- [App/tests/test_umami_guard.py](App/tests/test_umami_guard.py) — retarget to PostHog. Rename the file in a later pass only if every importer is updated in this same brief; otherwise keep the filename and change the assertions. Fixture sets `POSTHOG_PROJECT_API_KEY` to `phc_test`, `POSTHOG_HOST` to `https://analytics.example.invalid`, `POSTHOG_ASSETS_HOST` to `https://assets.example.invalid`. Markers are the key, both origins, and `posthog.init`. Assert `us.i.posthog.com` leaves the tag absent and the CSP strict. Assert `/signup` and `/signup/verify` still have no tag and the strict CSP, including when the URL contains `gclid` and `fbclid`. Assert the snippet source contains the strip list `gclid`, `fbclid`, `click`, `token`.
- [App/tests/test_signup.py](App/tests/test_signup.py) — `data-umami-event` becomes `data-analytics-event`. The assertion that the sign-up page has no such attribute stays.
- [App/tests/test_no_tracking.py](App/tests/test_no_tracking.py) — comment only, so it points at the guard test.

No other file may change. Copy sentences stay in 0034, even if they still say Umami for one commit.

**Steps.**

1. Replace the config block. Delete every `UMAMI_` name. A repo search for `UMAMI_` in `App/` may remain only inside 0034's files (`privacy_policy_i18n.py`, `subprocessors_i18n.py`, `cookie_inventory.py`, `landing_i18n.py`). Those are 0034. Do not edit them here.
2. Rewrite `analytics.py` as described. Refuse a non-https host the same way `_https_origin` does today.
3. Add `_posthog.html`. It prints nothing unless `analytics_tag` is set. The inline script returns immediately when `navigator.doNotTrack` or `window.doNotTrack` is `"1"`, or when `localStorage["ubyhost.analytics.disabled"]` is set. Then it loads `{{ analytics_tag.assets_host }}/static/array.js` and calls `posthog.init` with `api_host`, `cookieless_mode: "always"`, `person_profiles: "identified_only"`, `persistence: "memory"`, `autocapture: false`, `capture_pageleave: false`, `disable_session_recording: true`. `before_send` removes the query keys `gclid`, `gbraid`, `wbraid`, `fbclid`, `click`, `token`, `email` and the hash from `$current_url`, `$referrer` and `$pathname`. `loaded` listens for clicks on `[data-analytics-event]` and calls `capture` only for `login_click`, `contact_click` and `signup_start`. The inline script must not contain the word `identify`.
4. Point the five includes at `_posthog.html` and rename the data attributes.
5. Update the guard test and `test_signup.py` as in the file list.
6. From `App/`: `.venv/bin/python -m pytest tests/test_umami_guard.py tests/test_signup.py tests/test_no_tracking.py -q`. Expected: pass, 0 failed. Then `.venv/bin/python -m pytest tests -q`. Expected: the same pass count as before this brief, 0 failed. UI: screenshots of `/` and `/privacy` at 360, 390 and 1280 px in the report, with the key set in the test client or a local env. Do not commit a real `phc_` key.

**Do not touch.** `admin_funnel.py`, `scheduler.py`, migrations, guest templates, signup templates, filing, `requirements*.txt`, privacy copy strings.

**Stop and ask** on the template conditions in [docs/tasks/TEMPLATE.md](docs/tasks/TEMPLATE.md) section 8, and if making the US host refused forces a CSP that the stand-in test cannot derive from config.

**Acceptance.**

- Unset key: public HTML has no `posthog`, CSP equals `_CSP`.
- Set key: public pages contain `posthog.init` and the CSP allows the configured assets host on `script-src` and the API host on `connect-src`.
- `/signup?gclid=TEST&fbclid=TEST`, `/login`, `/l/...`, and a signed-in `/reservations` stay on `_CSP` with no `posthog`.
- Opt-out script writes `ubyhost.analytics.disabled` and only `/privacy` loads it.
- No `identify(` in `App/app/templates` or `App/app/static`.

**Owner steps.** None in this brief. The key stays unset until 0034's copy is deployed and you have done the steps in section 6.
