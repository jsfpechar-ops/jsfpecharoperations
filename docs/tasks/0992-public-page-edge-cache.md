# 0992: Let Cloudflare cache the public marketing pages for 5 minutes

Status: review
Depends on: none | Base commit: f0a7fa3f | Branch: claude/zealous-planck-raxu4v
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Overlap: 0990 (settings write loop) and 0991 (indexes) must not touch main.py or templating.py; if either has, stop at the first missing anchor (§8).

## 1. Objective

The public pages (`/`, `/legal`, `/terms`, `/privacy`, `/dpa`, `/subprocessors`, `/cenik`, `/jak-to-funguje`, `/pruvodce/{slug}`, `/robots.txt`, `/sitemap.xml`) get `Cache-Control: public, max-age=0, s-maxage=300` when, and only when, the response provably does not depend on the visitor. Every other response keeps `no-store, private`. The owner then adds one Cloudflare Cache Rule so bots stop hitting the app.

## 2. Context

### Safety analysis (done by the brief writer; verdict: GO, narrowly)

| Risk | Finding | Consequence |
|---|---|---|
| CSP nonce | None. `_CSP` / `_public_csp()` in `main.py` are static strings built from config, no per-request value. | Safe. CSP is not touched. |
| CSRF token in HTML | `templating.render()` always calls `security.csrf_token(request)`, but none of the public templates (`landing`, `product`, `pricing`, `public_guide`, `legal`, `terms`, `privacy`, `dpa`, `subprocessors`, `public_legal_base`, `_public_header`, `_public_footer`, `_posthog`) contain `csrf` or a `<form>`. The token is in `base.html` only, which these pages do not extend. | HTML is token-free. |
| Set-Cookie | The same `csrf_token()` call creates a nonce for a visitor without a cookie, and `security.attach_csrf_cookie` (middleware) then sends `Set-Cookie: ubyhost_csrf=...`. Cloudflare never caches a response with Set-Cookie, and a cached one would be dangerous. | Strip that one cookie on cacheable responses (no form on these pages needs it). If any other Set-Cookie remains, do not mark the response public. |
| Language | `host_i18n.resolve_language` reads `?lang=` THEN the `ubyhost_lang` cookie. Cloudflare's cache key ignores cookies. A `?lang=` request also sets `ubyhost_lang` (`templating.render`, end of function). | Cache only requests with no `ubyhost_lang` cookie and no query string at all. `?lang=en` URLs stay uncached (same as today). |
| Logged-in `/` | `routes/admin.py` `dashboard()` returns the dashboard for a signed-in user at `/`. | Cache only requests without the `ubyhost_session` cookie. The Cloudflare rule also bypasses when that cookie is present. A dashboard is rendered from `dashboard.html`, never in the public set, so it can never get the public header. |
| Attribution | `signup.signup_href(..., mint=True)` signs a click value from `gclid`-style query ids, with a timestamp. | Any query string is uncached, so no minted value is ever shared. |
| PostHog | `analytics.tag()` is config-only, same for every visitor. | Safe. |
| Existing default | `main.py` middleware: `response.headers.setdefault("Cache-Control", "no-store, private")` for everything except `/static/`. | Already the explicit default. Do not add another. |

### The public set is reused, not duplicated

`App/app/analytics.py`:

```python
PUBLIC_ANALYTICS_TEMPLATES = frozenset(
    {
        "landing.html",
        "product.html",
        "pricing.html",
        "public_guide.html",
```

`App/app/templating.py` (end of `render`), anchor:

```python
    data["analytics_tag"] = analytics.tag() if analytics.mark_public_page(request, name) else None
```

`App/app/main.py` middleware, anchor (exact text):

```python
    _harden(response, public_analytics=analytics.is_public_page(request))
    # Everything outside /static carries passport numbers, addresses and
    # signatures. Guests hand the phone back and hosts share laptops, so these
    # pages must not sit in history, the back/forward cache, or a proxy.
    if not request.url.path.startswith("/static/"):
        response.headers.setdefault("Cache-Control", "no-store, private")
```

`main.py` routes, anchors:

```python
@app.get("/robots.txt", include_in_schema=False)
def robots():
    return Response(seo.robots_txt(), media_type="text/plain; charset=utf-8")
```

```python
@app.get("/sitemap.xml", include_in_schema=False)
```

Cookie constants (verified): `auth.SESSION_COOKIE = "ubyhost_session"`, `host_i18n.LANG_COOKIE = "ubyhost_lang"`, `security.CSRF_COOKIE = "ubyhost_csrf"`. Check that `main.py` already imports `auth`, `security`, `host_i18n` (`grep -n "^from\|^import" App/app/main.py | head -40`); if one is missing, STOP.

Rules that apply: no new dependency, no new outbound request, no CSP change, no new personal-data field (AGENTS hard rules 2, 4).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templating.py | edit | In `render`, mark the request `edge_cacheable` when the template is in `PUBLIC_ANALYTICS_TEMPLATES`. |
| App/app/main.py | edit | New `_apply_edge_cache`, one call in the middleware, flag set in `robots()` and `sitemap_xml()`. |
| App/tests/test_public_edge_cache.py | create | The tests in step 4. |
| docs/CLOUDFLARE.md | edit | Replace the "Optional Cache Rules" bullet (step 5). |
| docs/tasks/0992-report.md | create | Report. |

No other file may change (not `analytics.py`, not `security.py`, not any template).

## 4. Steps

1. Set `Status: in-progress` on line 3 of this brief.

2. `App/app/templating.py`: directly AFTER the line `data["analytics_tag"] = analytics.tag() if analytics.mark_public_page(request, name) else None` add:

```python
    # 0992: the public marketing pages carry nothing about the visitor, so the
    # middleware may let Cloudflare keep them for a few minutes (main._apply_edge_cache).
    # The test is the same template set the PostHog tag uses; one list, one place.
    if name in analytics.PUBLIC_ANALYTICS_TEMPLATES:
        request.state.edge_cacheable = True
```

3. `App/app/main.py`, three edits.

   a. Insert this function directly ABOVE `def _is_guest_path(request: Request) -> bool:`:

```python
_EDGE_CACHE_CONTROL = "public, max-age=0, s-maxage=300"


def _apply_edge_cache(request: Request, response) -> None:
    """0992: let Cloudflare keep a public marketing page for 5 minutes.

    Only a plain GET/HEAD with no query string, no session cookie and no
    language cookie, answered 200 by a page that opted in
    (``request.state.edge_cacheable``). The edge cache key ignores cookies, so
    anything that varies by cookie or query must stay private. The anonymous
    CSRF cookie is dropped (no public page has a form); any other Set-Cookie
    keeps the page private.
    """
    if not getattr(request.state, "edge_cacheable", False):
        return
    if request.method not in {"GET", "HEAD"} or response.status_code != 200:
        return
    if request.url.query:
        return
    if auth.SESSION_COOKIE in request.cookies or host_i18n.LANG_COOKIE in request.cookies:
        return
    csrf_prefix = f"{security.CSRF_COOKIE}=".encode("latin-1")
    kept = [
        (key, value) for key, value in response.raw_headers
        if not (key.lower() == b"set-cookie" and value.startswith(csrf_prefix))
    ]
    if any(key.lower() == b"set-cookie" for key, _ in kept):
        return
    response.raw_headers = kept
    response.headers["Cache-Control"] = _EDGE_CACHE_CONTROL


```

   b. In the middleware, change the anchor block so the call comes first. Replace

```python
    _harden(response, public_analytics=analytics.is_public_page(request))
    # Everything outside /static carries passport numbers, addresses and
```

   with

```python
    _harden(response, public_analytics=analytics.is_public_page(request))
    _apply_edge_cache(request, response)
    # Everything outside /static carries passport numbers, addresses and
```

   (the following `setdefault("Cache-Control", "no-store, private")` then leaves the public header alone.)

   c. In `robots()` replace the body with:

```python
def robots():
    request.state.edge_cacheable = True
    return Response(seo.robots_txt(), media_type="text/plain; charset=utf-8")
```

   and change its signature line `def robots():` to `def robots(request: Request):`. For `/sitemap.xml`: read the function (`grep -n 'def sitemap' -A4 App/app/main.py`), add `request: Request` to its signature if missing, and add `request.state.edge_cacheable = True` as its first line. Check: `cd App && .venv/bin/python -c "import app.main" 2>&1 | tail -30` prints nothing.

4. Create `App/tests/test_public_edge_cache.py`. First read lines 1-48 of `App/tests/test_public_seo.py` and copy its import and client setup (`TestClient(app)`, `_clean_accounts`, `_account`, `_login`). Then write these tests (adjust only client setup to match; keep the assertions):

```python
PUBLIC = "public, max-age=0, s-maxage=300"
CACHEABLE = ("/", "/legal", "/terms", "/privacy", "/dpa", "/subprocessors",
             "/cenik", "/jak-to-funguje", "/robots.txt", "/sitemap.xml")


def test_public_pages_get_the_edge_header_and_no_cookie():
    for path in CACHEABLE:
        r = TestClient(app).get(path)          # fresh client: no cookies
        assert r.status_code == 200, path
        assert r.headers["cache-control"] == PUBLIC, path
        assert "set-cookie" not in r.headers, path


def test_a_public_guide_is_cacheable():
    # take the first slug from app.public_guides.GUIDE_TRANSLATIONS["cs"]
    r = TestClient(app).get(f"/pruvodce/{slug}")
    assert r.headers["cache-control"] == PUBLIC and "set-cookie" not in r.headers


def test_query_string_language_cookie_and_session_stay_private():
    assert TestClient(app).get("/?lang=en").headers["cache-control"] == "no-store, private"
    assert TestClient(app).get("/?utm_source=x&gclid=abc").headers["cache-control"] == "no-store, private"
    c = TestClient(app); c.cookies.set("ubyhost_lang", "en")
    assert c.get("/").headers["cache-control"] == "no-store, private"
    c = TestClient(app); c.cookies.set("ubyhost_session", "anything")
    assert c.get("/").headers["cache-control"] == "no-store, private"


def test_signed_in_root_is_the_private_dashboard():
    # use _account/_login exactly as test_public_seo.py does
    r = client.get("/")
    assert r.headers["cache-control"] == "no-store, private"


def test_private_areas_never_get_the_public_header():
    for path in ("/login", "/signup", "/l/not-a-real-token", "/settings",
                 "/reservations", "/healthz", "/api/not-a-route"):
        r = TestClient(app).get(path, follow_redirects=False)
        assert r.headers.get("cache-control") != PUBLIC, path
        assert "s-maxage" not in r.headers.get("cache-control", ""), path


def test_unknown_guide_404_is_private():
    r = TestClient(app).get("/pruvodce/no-such-guide")
    assert r.status_code == 404 and r.headers["cache-control"] == "no-store, private"
```

   If `/` returns a redirect in the test environment (public and app hosts differ), request it the way `test_public_seo.py` does (same headers/base URL) and note it in the report. If a path in `CACHEABLE` is not 200 for another reason, STOP (§8).

5. `docs/CLOUDFLARE.md`: replace the bullet beginning `2. Optional **Cache Rules**: bypass cache for` (2 lines, under "#### 3. Cache purge") with this one paragraph (the one explanation of edge caching; do not repeat it elsewhere):

```markdown
2. **Cache Rules** (brief 0992, public pages cached for 5 minutes). The app marks only the
   public marketing pages with `Cache-Control: public, max-age=0, s-maxage=300` (plain GET, no
   query string, no `ubyhost_session` or `ubyhost_lang` cookie); every other response is
   `no-store, private`. Rule "Public pages": hostname equals the public host AND path in
   `/`, `/legal`, `/terms`, `/privacy`, `/dpa`, `/subprocessors`, `/cenik`, `/jak-to-funguje`,
   `/robots.txt`, `/sitemap.xml` or starts with `/pruvodce/` AND query is empty AND cookie does
   not contain `ubyhost_session` or `ubyhost_lang`; action Eligible for cache, Edge TTL "Use
   cache-control header if present", Browser TTL "Respect origin". Undo: disable the rule.
   Check: `curl -sI https://<public host>/ | grep -i -E 'cf-cache-status|cache-control'` twice,
   the second shows `HIT`.
```

6. Run the tests (from `App/`):
   - `.venv/bin/python -m pytest tests/test_public_edge_cache.py -q --tb=short -x 2>&1 | tail -30` expect all passed.
   - `.venv/bin/python -m pytest tests/test_privacy_first.py tests/test_public_seo.py tests/test_public_chrome.py tests/test_public_legal.py tests/test_security.py tests/test_security_hardening.py -q --tb=short -x 2>&1 | tail -30` expect all passed, 0 skipped added by you.
   - From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` expect no new error.

7. Commit and push (the executor may; no PR):
   `git add App/app/templating.py App/app/main.py App/tests/test_public_edge_cache.py docs/CLOUDFLARE.md docs/tasks/0992-public-page-edge-cache.md docs/tasks/0992-report.md`
   `git commit` with the message `Cache public marketing pages at the Cloudflare edge for 5 minutes (0992)` and the trailers
   `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_014N5J8K21RfgG5itpXC8Mic`.
   `git push -u origin claude/zealous-planck-raxu4v 2>&1 | tail -30`. If the push is refused, say so in the report (§8).

## 5. Do not touch

CSP strings and `_harden`; `security.py`; `analytics.py`; templates; guest, host, auth, admin and API code; the `/static` cache logic; `/manifest.webmanifest` and `/sw.js` headers; any file of 0990 or 0991. Hard rules 2, 3, 4 and 8. This is not a template or CSS change, so rule 7 and the UX gate do not apply (no HTML changes).

## 6. Commands

Exactly those in step 4 and 6. Test-map rows used: "Public pages, legal, landing" and "Login, 2FA, passkeys, sessions" (security files). Never the full suite.

## 7. Acceptance

- [ ] The ten fixed public paths and a `/pruvodce/{slug}` answer `Cache-Control: public, max-age=0, s-maxage=300` and no `Set-Cookie` for a cookieless plain GET (test passes).
- [ ] `?lang=`, any query string, an `ubyhost_lang` cookie and an `ubyhost_session` cookie each give `no-store, private`.
- [ ] `/login`, `/signup`, `/l/...`, `/settings`, `/healthz`, an API path and a 404 never carry `public` or `s-maxage`.
- [ ] `git diff --stat` shows only the §3 files; CSP unchanged.
- [ ] Privacy-first and security tests green; context lint has no new error.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found verbatim, or `auth`, `security` or `host_i18n` is not imported in `main.py`;
- a test fails twice, or a public path is not 200 in tests;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`);
- a file outside §3 needs a change, or a new dependency seems needed;
- you would need to change the CSP, a template, or the cookie logic beyond step 3;
- push is refused (hand the exact command to the owner).

## 9. Report

Write `docs/tasks/0992-report.md` (600 tokens at most) and set this brief's `Status: review`. It has: 1. `git diff --stat`. 2. Each command with the last 5 lines of output. 3. §7 ticked. 4. Deviations (for example, `/` handling in the test client). 5. Questions. 6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/main.py` `_apply_edge_cache`: the header must never be set for a cookie-bearing, query-bearing or non-200 response, and the only dropped cookie is `ubyhost_csrf`.
- `App/app/templating.py`: the flag comes only from `PUBLIC_ANALYTICS_TEMPLATES` (no host or guest template is in it).

## Owner steps

Do these after the PR is merged and deployed (you merge and deploy; the brief does neither).

1. Open https://dash.cloudflare.com and click the `ubyhost.com` zone.
2. Left menu: **Caching** then **Cache Rules**, then **Create rule**.
3. Rule name: `Public pages`.
4. Click **Edit expression** and paste the expression below (replace `<public host>` with the public hostname, normally `ubyhost.com`):
   `(http.host eq "<public host>" and http.request.uri.query eq "" and not http.cookie contains "ubyhost_session" and not http.cookie contains "ubyhost_lang" and (http.request.uri.path in {"/" "/legal" "/terms" "/privacy" "/dpa" "/subprocessors" "/cenik" "/jak-to-funguje" "/robots.txt" "/sitemap.xml"} or starts_with(http.request.uri.path, "/pruvodce/")))`
5. Under **Cache eligibility** choose **Eligible for cache**.
6. Under **Edge TTL** choose **Use cache-control header if present, bypass cache if not**.
7. Under **Browser TTL** choose **Respect origin TTL**.
8. Click **Deploy**.
9. Check: run `curl -sI https://<public host>/ | grep -i -E 'cf-cache-status|cache-control'` twice. The first shows `MISS` or `DYNAMIC`, the second shows `cf-cache-status: HIT` and `cache-control: public, max-age=0, s-maxage=300`. Then run the same for `https://<public host>/login`: it must show `no-store, private` and no `HIT`.
10. Undo at any time: **Caching**, **Cache Rules**, switch `Public pages` off. The app header is harmless without the rule.
11. After a copy change on a public page, the page updates within 5 minutes, or use **Caching**, **Configuration**, **Purge Everything**.
