# 0034 — Copy and subprocessor

Status: review
Depends on: 0033 | Base commit: 0033's commit | Branch: same branch
Executor: Composer 2.5 | Fits one session

(Copied from [posthog-analytics plan](../plans/posthog-analytics.md) §5.)

## 1. Objective

Say PostHog, in English and Czech, in the privacy policy, the subprocessor register, the cookie inventory and the landing line. Remove Umami from those texts.

## 2. Context

See [posthog-analytics plan](../plans/posthog-analytics.md) §5 for the exact English and Czech strings.

## 3. Files

- [App/app/privacy_policy_i18n.py](App/app/privacy_policy_i18n.py) — replace `privacy.analytics_body` and `privacy.optout_lede` in `en` and `cs`. Add `privacy.product_analytics_title` and `privacy.product_analytics_body` in both. Do not claim § 89(3) for the host-profile paragraph. The website paragraph may say legitimate interest and that the measurement is aggregated page statistics. Exact English website body: "On our public pages (not in the app, not on guest pages and not on sign-in) we use PostHog Cloud EU, operated by PostHog, Inc., with data stored in the EU (Frankfurt), to count visits. The measurement is set not to store a cookie and not to store your IP address. PostHog derives a short-lived visit identifier, and we see aggregated statistics (pages viewed, referring site, browser, device type, country). We do not use this for advertising. Legal basis: our legitimate interest in understanding how our website is used (Art. 6(1)(f) GDPR). You can switch measurement off in this browser here:". Exact English product body: "For our marketing and sales picture we also send PostHog, from our own server, the host account e-mail, the workspace name, the campaign labels of the sign-up link (utm_source, utm_medium, utm_campaign), the sign-up source, and how far the account has got. We do not send guest data, passport details, stay contents, door codes or advertising click identifiers. Legal basis: our legitimate interest in operating the service (Art. 6(1)(f) GDPR)." Czech: translate those two paragraphs in the same formal register as the current Umami paragraph. Do not mention Umami.
- [App/app/templates/privacy.html](App/app/templates/privacy.html) — inside the existing `{% if analytics_tag %}` block, after the website paragraph, print the new title and body. Do not change the opt-out markup except the script name 0033 already set.
- [App/app/subprocessors_i18n.py](App/app/subprocessors_i18n.py) — rename keys `umami_*` to `posthog_*` in `en` and `cs`. Provider: "PostHog, Inc. (PostHog Cloud EU)". Purpose: "Website statistics on public pages, and host-account product measurement for the operator." Data: "Public page views and the three click events; for a host account, e-mail, workspace name, UTM labels, sign-up source and funnel stage. No Guest Data. No advertising click identifiers." Location: "EU, Frankfurt. Used only while the operator enables it." Safeguard: "PostHog DPA."
- [App/app/routes/legal.py](App/app/routes/legal.py) — `"umami"` in `SUBPROCESSOR_IDS` becomes `"posthog"`.
- [App/tests/test_privacy_legal_positions.py](App/tests/test_privacy_legal_positions.py) — the five-id assertion ends with `"posthog"`.
- [App/app/cookie_inventory.py](App/app/cookie_inventory.py) — row name `ubyhost.analytics.disabled`, `set_by` `static/analytics-optout.js`. Purpose and the `COOKIELESS_SERVICES` entry say PostHog, no cookies, public pages only, EU. Update the `de` / `es` / `fr` extra strings for that key the same way. Delete `umami.disabled`.
- [App/app/landing_i18n.py](App/app/landing_i18n.py) — `privacy_first.trackers.body` in `en` and `cs`. English: "No ad or analytics scripts in the app or on guest pages. Website statistics run on public pages only, with PostHog Cloud EU."
- [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) — replace the "Page analytics (Umami)" section with PostHog: `POSTHOG_PROJECT_API_KEY`, `POSTHOG_HOST`, `POSTHOG_ASSETS_HOST`. State that both hosts default to EU, a US host is ignored, and the tag is absent until the key is set.
- Guard test assertion that the privacy page and the subprocessor page describe the vendor: they must contain "PostHog" and must not contain "Umami".

## 4. Steps

Implement the file list above; see the plan for wording detail.

## 5. Do not touch

The Google Ads and Meta paragraphs (`privacy.signup_ads_*` and the Meta twins). The click-id consent flow. `analytics.py`.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_umami_guard.py tests/test_privacy_legal_positions.py tests/test_privacy_first.py -q`. Then the full suite. From the repo root: `python3 scripts/context_lint.py`. Screenshots of `/privacy` and `/subprocessors` at 360, 390 and 1280 px, English and Czech.

## 7. Acceptance

A search of `App/` for `umami` finds nothing. `/privacy` shows the website paragraph, the product paragraph and the opt-out. `/subprocessors` lists PostHog, Inc. The Google Ads paragraph still says the click id goes to Google, not to PostHog.

## 8. Stop and ask

As in [TEMPLATE](TEMPLATE.md) §8.

## 9. Report

`docs/tasks/0034-report.md`.
