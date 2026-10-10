# 0039: PostHog hardening before the key is set

Status: done
Depends on: 0033 to 0036 | Base commit: 93995e7 | Branch: claude/dazzling-hamilton-8nzb2p (PR 337's work plus this brief)
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

PR 337's public snippet sends Google and Meta click ids to PostHog, which the plan and the new privacy copy both forbid. The server job also invents funnel stages and can send duplicates. This brief fixes both and locks the privacy settings in code, so a switch in the PostHog dashboard cannot change what the public site sends.

## 2. Context

Reviewed 2026-10-10 against posthog-js 1.438.7 in headless Chromium, using the snippet from PR 337 and a landing URL `/?utm_source=google&gclid=…&fbclid=…&click=…&email=…#frag`:

- PR 337's snippet: every `$pageview` and `signup_start` carried `gclid` and `fbclid` as top-level properties, plus `$initial_gclid` and `$initial_current_url` holding the raw URL with the signed `click` value, the e-mail and the hash. The library also POSTed `/flags` and fetched remote config.
- The snippet in §4 step 1: 0 occurrences of any of those values, `utm_source` kept, no `/flags` call, no remote config, no extra scripts.
- posthog-js drops an event whose `token` property was deleted in `before_send`. So click ids are dropped as **property keys**, while `click`, `token` and `email` are only stripped from **URLs**. Do not merge the two lists.

Plan rules that apply ([posthog-analytics](../plans/posthog-analytics.md) §1): ad click ids never go to PostHog. No feature flags, surveys or heatmaps. No `identify` from the browser. No new package.

`App/app/posthog_sync.py` today (excerpt, find it verbatim):

```
def _stages_to_send(previous: Optional[str], current: str) -> List[str]:
    keys = _stage_keys()
```

and:

```
                properties: Dict[str, Any] = {
                    "$ip": None,
                    "$set": _person_set(person_base, stage_key),
                }
```

`admin_funnel.rows()` sets `stage` to the furthest stage reached, but a host can skip stages (guests added by hand, so no `first_calendar_at`; an admin-made account has no `signup_at`). `_stages_to_send` sends every key between the last one sent and the current one, so skipped stages go out as events stamped "now".

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/_posthog.html` | edit | Replace the `<script>` body with §4 step 1 |
| `App/app/posthog_sync.py` | edit | §4 step 2 |
| `App/tests/test_posthog_sync.py` | edit | §4 step 3 |
| `App/tests/test_umami_guard.py` | edit | §4 step 4 |
| `App/tests/test_posthog_snippet_browser.py` | new | §4 step 5 |
| `docs/ENVIRONMENT.md` | edit | §4 step 6 |
| `docs/privacy/ROPA.md`, `docs/privacy/RETENTION.md` | edit | §4 step 7 |

No other file may change.

## 4. Steps

1. In `_posthog.html`, keep the Jinja comment and the `{%- if analytics_tag -%}` / `{%- endif -%}` lines. Replace everything between `<script>` and `</script>` with exactly this:

```js
(function () {
  "use strict";
  if (navigator.doNotTrack === "1" || window.doNotTrack === "1") return;
  try {
    if (window.localStorage.getItem("ubyhost.analytics.disabled")) return;
  } catch (err) {
    /* Storage blocked: continue without opt-out. */
  }
  var apiKey = {{ analytics_tag.api_key | tojson }};
  var apiHost = {{ analytics_tag.api_host | tojson }};
  var assetsHost = {{ analytics_tag.assets_host | tojson }};
  var clickIds = ["gclid", "gclsrc", "dclid", "gbraid", "wbraid", "fbclid", "msclkid", "twclid", "li_fat_id", "igshid", "ttclid", "rdt_cid", "epik", "qclid", "sccid", "oppref", "irclid", "_kx"];
  var stripKeys = clickIds.concat(["click", "token", "email"]);
  var prefixes = ["$initial_", "$session_entry_"];
  function isClickIdKey(key) {
    for (var i = 0; i < prefixes.length; i++) {
      if (key.indexOf(prefixes[i]) === 0) key = key.slice(prefixes[i].length);
    }
    return clickIds.indexOf(key) !== -1;
  }
  function scrubUrl(raw) {
    if (raw.indexOf("?") === -1 && raw.indexOf("#") === -1) return raw;
    try {
      var u = new URL(raw, window.location.origin);
      for (var i = 0; i < stripKeys.length; i++) u.searchParams.delete(stripKeys[i]);
      u.hash = "";
      return raw.indexOf("://") === -1 ? u.pathname + u.search : u.toString();
    } catch (e) {
      return raw.split("?")[0].split("#")[0];
    }
  }
  function scrub(value) {
    if (typeof value === "string") return scrubUrl(value);
    if (!value || typeof value !== "object") return value;
    for (var key in value) {
      if (!Object.prototype.hasOwnProperty.call(value, key)) continue;
      if (isClickIdKey(key)) delete value[key];
      else value[key] = scrub(value[key]);
    }
    return value;
  }
  function beforeSend(event) {
    if (event) scrub(event);
    return event;
  }
  var allowed = { login_click: 1, contact_click: 1, signup_start: 1 };
  function onLoaded(ph) {
    document.addEventListener("click", function (ev) {
      var el = ev.target.closest("[data-analytics-event]");
      if (!el) return;
      var name = el.getAttribute("data-analytics-event");
      if (allowed[name]) ph.capture(name);
    });
  }
  var s = document.createElement("script");
  s.src = assetsHost + "/static/array.js";
  s.onload = function () {
    window.posthog.init(apiKey, {
      api_host: apiHost,
      cookieless_mode: "always",
      person_profiles: "identified_only",
      persistence: "memory",
      mask_personal_data_properties: true,
      custom_personal_data_properties: ["click", "token", "email"],
      disable_capture_url_hashes: true,
      autocapture: false,
      capture_pageleave: false,
      disable_session_recording: true,
      enable_heatmaps: false,
      capture_dead_clicks: false,
      capture_exceptions: false,
      capture_performance: false,
      disable_surveys: true,
      disable_web_experiments: true,
      disable_product_tours: true,
      disable_conversations: true,
      advanced_disable_flags: true,
      advanced_disable_toolbar_metrics: true,
      disable_external_dependency_loading: true,
      before_send: beforeSend,
      loaded: onLoaded
    });
  };
  document.head.appendChild(s);
})();
```

2. In `posthog_sync.py`:
   - `import uuid` (standard library).
   - Add `_EVENT_NAMESPACE = uuid.UUID("6f1c5c6e-0b8e-4d55-9d43-4b1f0b7a3e37")`.
   - Replace `_stages_to_send(previous, current)` with `_stages_to_send(previous, row)`: walk `admin_funnel.stages()` in order, skip keys up to and including `previous` (if `previous` is not a known key, skip nothing), and return the keys whose column in `row` is truthy, stopping after `row["stage"]`. A stage the host never reached is never sent.
   - `_capture` gets a `event_uuid: str` argument and puts it in the payload as `"uuid"`. The caller passes `str(uuid.uuid5(_EVENT_NAMESPACE, f"{account_id}:{stage_key}"))`, so a resend is the same event.
   - Add `"$geoip_disable": True` next to `"$ip": None`.
   - Advance `posthog_stage` to `stage_key` with the existing UPDATE **after each successful capture**, inside the loop, not once at the end.
   - Read `analytics.tag()` once into a local.
3. In `test_posthog_sync.py`, add:
   - `test_skipped_stage_is_not_sent`: a host with `first_guest_at` set and `first_calendar_at` NULL. Assert no captured body has `event == "first_calendar"`.
   - `test_partial_failure_resumes_without_duplicates`: fake `urlopen` succeeds twice then raises `HTTPError` 503. Assert `posthog_stage` equals the second event's name. Run `sync()` again with a succeeding fake. Assert the second run's first event is the third stage, not the first.
   - `test_event_uuid_is_stable`: two runs with `posthog_stage` reset to NULL in between. Assert the `uuid` list is identical.
   - In `test_capture_body_shape`, assert `body["properties"]["$geoip_disable"] is True` and `"uuid" in body`.
4. In `test_umami_guard.py`, add `test_the_snippet_locks_the_privacy_settings`. Read `_posthog.html` and assert each of these strings is present: `advanced_disable_flags: true`, `disable_surveys: true`, `enable_heatmaps: false`, `capture_dead_clicks: false`, `capture_exceptions: false`, `capture_performance: false`, `disable_external_dependency_loading: true`, `mask_personal_data_properties: true`, `disable_session_recording: true`, `autocapture: false`. Change `STRIP_KEYS` to `("gclid", "fbclid", "ttclid", "click", "token", "email")`.
5. New `test_posthog_snippet_browser.py`. Copy the header, the `REQUIRE_BROWSER` import block, `_free_port` and the `base` fixture from `test_host_geometry.py`. Add a `posthog_on` fixture identical to the one in `test_umami_guard.py`. The test:
   - Registers `page.route("https://assets.example.invalid/static/array.js", …)` and fulfils it with this stand-in library, so no network is used:
     `window.posthog = { init: function (key, cfg) { window.__phCfg = cfg; }, capture: function () {} };`
   - Opens `base + "/?lang=en&utm_source=google&gclid=G1&fbclid=F1&click=C1&email=a%40b.cz#frag"` and waits for `window.__phCfg`.
   - Calls `window.__phCfg.before_send(ev)` with this event and asserts on the returned value:

```json
{"event": "$pageview", "properties": {
  "token": "phc_test", "utm_source": "google", "gclid": "G1", "fbclid": "F1", "ttclid": "T1",
  "$initial_gclid": "G1", "$session_entry_fbclid": "F1",
  "$current_url": "https://ubyhost.example/?utm_source=google&gclid=G1&click=C1&email=a%40b.cz#frag",
  "$pathname": "/?gclid=G1", "$referrer": "https://www.google.com/?gclid=G1",
  "$set_once": {"$initial_current_url": "https://ubyhost.example/?gclid=G1&token=K1"}}}
```

   - Asserts: `JSON.stringify(result)` contains none of `G1`, `F1`, `T1`, `C1`, `K1`, `a%40b.cz`, `#frag`. `result.properties.token == "phc_test"`. `result.properties.utm_source == "google"`. `result.properties.$current_url == "https://ubyhost.example/?utm_source=google"`.
   - Asserts `window.__phCfg.advanced_disable_flags === true` and `window.__phCfg.cookieless_mode === "always"`.
   - Asserts the page made no request to any host other than `base` and `assets.example.invalid` (collect with `page.on("request")`).
6. `docs/ENVIRONMENT.md`, PostHog section: add a numbered "Before you set the key" list with the two owner steps from §Owner steps below, word for word.
7. `ROPA.md`: add one processing row "Host product analytics (PostHog Cloud EU)": host e-mail, workspace name, sign-up UTM labels, sign-up source, funnel stage; legitimate interest; processor PostHog, Inc., EU region; deletion by hand on account deletion until automated (see known-issues). `RETENTION.md`: one row "PostHog person profile: until the host account is deleted; the operator deletes the person in PostHog by hand within 30 days". Mark both rows `LAWYER REVIEW`.

## 5. Do not touch

`analytics.py`, `main.py` CSP code, `admin_funnel.py`, privacy and subprocessor copy, migrations, guest, sign-up and auth templates, `requirements*.txt`. Hard rules 2, 3 and 4 in AGENTS.md. No real `phc_` key in any file.

## 6. Commands

From `App/`:

- `.venv/bin/python -m pytest tests/test_posthog_sync.py tests/test_umami_guard.py tests/test_posthog_snippet_browser.py -q` → all pass, 0 skipped (set `UBYHOST_REQUIRE_BROWSER=1`).
- `.venv/bin/python -m pytest tests -q` → 0 failed.

From the repo root: `python3 scripts/context_lint.py`.

## 7. Acceptance

- [ ] The browser test passes with `UBYHOST_REQUIRE_BROWSER=1`, 0 skipped.
- [ ] `grep -n '"identified" + "_only"' App/app/templates/_posthog.html` prints nothing.
- [ ] `grep -c 'posthog_stage = ?' App/app/posthog_sync.py` is 1 and that line is inside the per-stage loop.
- [ ] The four new sync tests pass.
- [ ] ROPA and RETENTION rows exist, marked `LAWYER REVIEW`.

## 8. Stop and ask

As in [TEMPLATE](TEMPLATE.md) §8. Also stop if the browser test can only pass by editing `main.py`'s CSP.

## 9. Report

`docs/tasks/0039-report.md`, as in [TEMPLATE](TEMPLATE.md) §9.

## Risk list (for the reviewer)

`_posthog.html` (diff against §4 step 1, character for character), `posthog_sync.py`, `test_posthog_snippet_browser.py`.

## Owner steps

Do these in PostHog **before** you put `POSTHOG_PROJECT_API_KEY` in the production `.env`. The privacy page promises both.

1. In PostHog, open **Settings**, then **Project**, then **IP data capture**. Turn on **Discard client IP data**.
2. In the same project settings, find **Cookieless server hash mode** and turn it on. Without it, the cookieless page views are dropped.
3. Later, and only if you want automatic deletion: decide whether UbyHost may hold a PostHog personal API key. Until then, when you delete a host account, also delete that person in PostHog (**People**, search the e-mail, **Delete person**).
