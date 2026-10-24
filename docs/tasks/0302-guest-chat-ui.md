# 0302: Leon (AI): the guest chat on the guide pages

Status: todo
Depends on: 0300 and 0301 merged | Base commit: after 0301 | Branch: task/0302-guest-chat-ui
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Guests talk to Leon (AI) in a calm chat panel at the end of "Your guide" on the stay link and on the public QR page, see the host's answers there, and get a clear "waiting for your host" state. The QR page's contact block stops telling a sticker-scanner to use "the message this link came in".

## 2. Context

### Owner decisions that bind this brief ([plan](../plans/guest-guide.md))

Leon is "Leon (AI)" everywhere and says he is an AI (header, intro line, every bubble label). He answers briefly (0300). Guests on the QR page see the host's name only. Light mode only. No tracking cookies, no third-party script, no new dependency. Phone first (390 px).

### Design

**Where.** One `g-card` section `#leon` after the last guide card (`guest/_leon.html`, included by `guest/guide.html`), plus a quiet "Ask Leon (AI)" jump link under the page intro. No sticky button: a fixed element covers card text on a 390 px phone and the layout checker flags it. Shown only when the guide is live and `ai.enabled("leon")` is true (`leon_url` in the context); otherwise nothing renders and no script loads.

**Progressive enhancement.** The guide works without JavaScript. The chat needs it: the form carries `hidden` and the script removes it, so a browser without JavaScript never posts to the JSON endpoint; a `<noscript>` line says "To chat with Leon (AI), turn on JavaScript. The guide above works without it." The jump link is hidden the same way.

**Script.** `App/app/static/guest-leon.js`, vanilla, loaded by `guest/base.html` only when `leon_url` is set. The guest CSP allows `'self'` scripts (`main.py` `_csp`); the file adds no inline script, no storage, no cookie and no request to another origin. Every string it shows comes from `data-*` attributes rendered by Jinja; every text is set with `textContent`. It loads the history (`GET <leon_url>`: `{"messages": [{"role","kind","text","at"}], "open_questions": n}`), posts `FormData` with `message`, `client_id` and `_csrf` plus the `X-CSRF-Token` header (`POST <leon_url>`: `{"kind","text","asked_host"}`). On a failure it shows a short error: 403, 404 or an HTML answer (expired form, guide taken down) say "This page has expired. Please reload it and try again."; anything else (also no answer within 50 s) "That did not go through. Please try again." Counter `n / 500` (warn colour from 450). While `open_questions > 0` or a reply has `asked_host`, the line "Waiting for your host. The answer will appear here, and you can close this page in the meantime." shows and the history is fetched again every 60 seconds while the tab is visible, at most 30 times (one cheap GET; no model call).

**Writing while Leon answers** (owner, 2026-10-24). One request in flight per page. The box and Send stay enabled: Send shows the text at once as the guest's bubble and clears the box; a text sent while a reply is pending is marked "Sending after Leon's reply" (`leon_queued`), the one on its way "Sending". When the reply lands, every queued text goes as ONE message joined with a newline: whole texts only, as many as fit in 500 characters, the rest wait for the next reply (a text is never cut). Each such batch gets a random `client_id` (32 hex) that it keeps on every retry, so a retry after a lost or timed-out response gets 0300's stored reply, never a second turn. `busy` (another device of the stay is waiting for Leon, 0300) puts the batch back and retries every 4 s, at most 20 times. A failed batch stays queued; the next Send (even with an empty box, so the textarea has no `required`) resends it. After each reply the history is fetched again (so the turns of a second device appear), and while `GET` says `"answering": true` (the guest reloaded mid-reply) it is fetched every 3 s, at most 20 times. Old browsers without `fetch` or `FormData.set` keep the hidden form (no broken chat). Every scenario: [leon-scenarios](../plans/leon-scenarios.md).

**Kinds** (0300 §2): `answer`, `ask_host`, `refuse`, `about_me`, `emergency`, `unclear`, `smalltalk`, `passed`, `too_long`, `slow_down`, `paused`, `answered`, and `busy` (never shown: re-queued). All are rendered as Leon bubbles with the text the server sent (fixed copy or a checked answer). `emergency` (112 and the host's emergency card) gets an urgent block: 2 px red border, red-soft background, bold ink text, full width, `role="alert"`. `ask_host` and `passed` get the accent border. Host turns (role `host`, 0301) are green-soft with the label `leon_host_answered` ("Jana, your host, answered:"; first name by `leon.host_first_name`, the plain label when there is no name). Guest bubbles sit on the right with the label "You". Text keeps its line breaks (`white-space: pre-line`).

**QR contact block.** `guest/_host.html` gets a QR branch: the host's name (if any) and `guide_qr_contact`: "To reach your host directly, write to them where you booked, for example in your Booking.com or Airbnb messages." The stay link keeps its phone and e-mail block unchanged.

**Guide link on the claim and form pages: split out.** The stay guide sits behind the claim gate (`_stay_gate` redirects an unclaimed device to the stay page), so a link from the claim or form page would loop; doing it properly means a gate change in `routes/guest.py` (1,900 lines) plus two more guest pages under rule 7. A later brief takes it.

**Security and privacy.** No new route: 0300's endpoints and gates. CSRF: hidden `_csrf` input (registered in `test_guest_csrf.py`) and the header. Input capped at 500 characters in the box and on the server. Nothing is logged by this brief. Host text is shown as typed and escaped (`textContent`).

**Copy.** 13 guest keys in en, cs, de, es, fr, uk by `docs/plans/0302-files/add_chat_i18n.py` (run once; it refuses a second run).

Hard rules 2, 3, 4, 6 (light mode; the guide works without JavaScript), 7, 8, 9 apply. Rule 7: the browser tests below pass with 0 skipped; the orchestrator takes the 390 px screenshots.

### Anchors (verbatim; a missing anchor means STOP)

`App/app/templates/guest/base.html`: a line containing `/static/guest.css?v=` and the line `<script src="/static/csrf.js?v=20260915a"></script>`.
`App/app/templates/guest/guide.html`: the line `    <p class="g-intro" data-guide-window-note>{{ t('guide_more_from_arrival') }}</p>` and the three lines `    {% endfor %}` / `  {% endfor %}` / `{% endif %}` near the end.
`App/app/templates/guest/_host.html`: the line `  <p class="g-intro">{{ t('host_details_help') }}</p>` and the line `    <p class="hint">{{ t('host_details_missing') }}</p>`.
`App/app/routes/guest_guide_view.py`: `from ..templating import render_guest`, `def _page(request: Request, lang: str, apartment, context: Dict[str, Any], level: str, photo_url, back_url: str = ""):`, `            "back_url": back_url,`, `        back_url=f"{base}?lang={lang}",`, `        lambda item_id, photo_id: f"/g/{token}/photos/{item_id}/{photo_id}",`.
`App/app/i18n.py`: five lines starting `        "leon_host_answered_plain":` (0301); `App/app/guest_uk_i18n.py`: one.
`App/tests/test_guest_csrf.py`: `    ("assigned.html", "/l/{{ token }}/{{ reservation.id }}/party?lang={{ lang }}"),`.
`docs/context/test-map.md`: the row starting `| Guest bot (Leon) |`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/guest/_leon.html` | create | Copied from `docs/plans/0302-files/` |
| `App/app/static/guest-leon.js` | create | Copied |
| `App/tests/test_guest_leon_chat.py`, `App/tests/test_guest_leon_browser.py` | create | Copied (6 and 5 tests) |
| `App/app/static/guest.css` | edit | Append `docs/plans/0302-files/guest-leon.css` |
| `App/app/templates/guest/base.html`, `guide.html`, `_host.html` | edit | Steps 4 to 6 |
| `App/app/routes/guest_guide_view.py` | edit | `leon_url`, `leon_host` |
| `App/app/i18n.py`, `App/app/guest_uk_i18n.py` | edit | By the script (run, not copied) |
| `App/tests/test_guest_csrf.py` | edit | Register the form |
| `App/tests/static_versions.json` | edit | `--write` |
| `docs/context/test-map.md`, `docs/plans/guest-guide.md` | edit | One row each |

No other file may change. No migration.

## 4. Steps

Commands run from `App/` unless a step says the repo root. Commit after every step (`0302 step k`).

### Step 1: preflight

From the repo root: `grep -c '"leon_host_answered_plain"' App/app/i18n.py; grep -c 'def _stay_gate' App/app/routes/guest_guide_view.py; grep -n 'guest.css?v=' App/app/templates/guest/base.html`. Expected: `5`, `1`, one line. If the first is `0`, 0301 is not merged: STOP.

### Step 2: copy the files

From the repo root:

```bash
cp docs/plans/0302-files/_leon.html App/app/templates/guest/_leon.html
cp docs/plans/0302-files/guest-leon.js App/app/static/guest-leon.js
cp docs/plans/0302-files/test_guest_leon_chat.py docs/plans/0302-files/test_guest_leon_browser.py App/tests/
cat docs/plans/0302-files/guest-leon.css >> App/app/static/guest.css
```

Command: `grep -c 'g-leon-msg--emergency' App/app/static/guest.css`. Expected: `2`.

### Step 3: copy (guest languages)

From the repo root: `python3 docs/plans/0302-files/add_chat_i18n.py`. Expected: `added 13 guest keys x 6 languages`. Command: `grep -c '"leon_intro"' App/app/i18n.py App/app/guest_uk_i18n.py`. Expected: `5` and `1`.

### Step 4: `App/app/templates/guest/base.html`

In the line containing `/static/guest.css?v=`, replace the key after `?v=` (whatever it is, for example `20261024-0294`) with `20261024-0302`. Directly after the line `<script src="/static/csrf.js?v=20260915a"></script>` insert:

```
{% if leon_url %}<script src="/static/guest-leon.js?v=20261024-0302"></script>{% endif %}
```

Command: `grep -c '20261024-0302' app/templates/guest/base.html`. Expected: `2`.

### Step 5: `App/app/templates/guest/guide.html`

Directly after the line `    <p class="g-intro" data-guide-window-note>{{ t('guide_more_from_arrival') }}</p>` and the `  {% endif %}` that follows it, insert:

```
  {% if leon_url %}<a class="g-leon-jump" href="#leon" data-leon-jump hidden>{{ t('leon_ask') }}</a>{% endif %}
```

Replace the three lines at the end of the content block

```
    {% endfor %}
  {% endfor %}
{% endif %}
```

with

```
    {% endfor %}
  {% endfor %}
  {% if leon_url %}{% include "guest/_leon.html" %}{% endif %}
{% endif %}
```

Command: `grep -c 'leon_url' app/templates/guest/guide.html`. Expected: `2`.

### Step 6: `App/app/templates/guest/_host.html`

Replace the line `  <p class="g-intro">{{ t('host_details_help') }}</p>` with:

```
  {% if door == 'qr' %}
    {# 0302: a QR guest scanned a sticker, so there is no message this link came in. #}
    {% if host and host.name %}<p>{{ host.name }}</p>{% endif %}
    <p class="g-intro" style="margin-bottom:0" data-qr-contact>{{ t('guide_qr_contact') }}</p>
  {% else %}
  <p class="g-intro">{{ t('host_details_help') }}</p>
```

The line `    <p class="hint">{{ t('host_details_missing') }}</p>` is followed by `  {% endif %}`; directly after that `  {% endif %}` insert one more line `  {% endif %}` (it closes the QR branch, before `</div>`). Command: `grep -c 'endif' app/templates/guest/_host.html`. Expected: `6`.

### Step 7: `App/app/routes/guest_guide_view.py`

Directly after `from ..templating import render_guest` insert:

```python
from .. import ai, leon  # 0302: the Leon (AI) chat
```

Replace `def _page(request: Request, lang: str, apartment, context: Dict[str, Any], level: str, photo_url, back_url: str = ""):` with:

```python
def _page(request: Request, lang: str, apartment, context: Dict[str, Any], level: str, photo_url, back_url: str = "",
          leon_url: str = ""):
```

Directly after `            "back_url": back_url,` insert:

```python
            # 0302: the chat only while the guide is live and Leon is switched on.
            "leon_url": leon_url if live and ai.enabled("leon") else "",
            "leon_host": leon.host_first_name((context.get("host") or {}).get("name", "")),
```

Replace `        back_url=f"{base}?lang={lang}",` with `        back_url=f"{base}?lang={lang}", leon_url=f"{base}/guide/leon",`. Replace `        lambda item_id, photo_id: f"/g/{token}/photos/{item_id}/{photo_id}",` with `        lambda item_id, photo_id: f"/g/{token}/photos/{item_id}/{photo_id}", leon_url=f"/g/{token}/leon",`.

Command: `grep -c 'leon_url' app/routes/guest_guide_view.py`. Expected: `4`.

### Step 8: register the form, `App/tests/test_guest_csrf.py`

Directly before `    ("assigned.html", "/l/{{ token }}/{{ reservation.id }}/party?lang={{ lang }}"),` insert:

```python
    ("_leon.html", "{{ leon_url }}"),
```

### Step 9: static versions

`.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -2`. Expected: `wrote .../tests/static_versions.json (N files)`. If it prints `refusing`, a key in step 4 is missing: check it, then run again.

### Step 10: docs

`docs/context/test-map.md`: in the row starting `| Guest bot (Leon) |`, replace `` `test_leon.py `` with `` `test_leon.py test_guest_leon_chat.py test_guest_leon_browser.py ``. `docs/plans/guest-guide.md`: in the row starting `| 3 | [0302](../tasks/0302-guest-chat-ui.md) |`, change the last cell `todo` to `review`.

### Step 11: tests

The commands in §6.

## 5. Do not touch

`App/app/leon.py`, `App/app/routes/guest_leon.py`, `App/app/routes/guest.py`, `App/app/main.py` (CSP), `guest/stay.html`, `guest/claim.html`, `guest/form.html`, every migration, `tokens.css`. No inline `<script>`, no `innerHTML`, no new dependency. Hard rules 2, 3, 4, 8, 9 apply.

## 6. Commands

From `App/`:

- `.venv/bin/python -m pytest tests/test_guest_leon_chat.py tests/test_guest_csrf.py tests/test_guest_guide_view.py tests/test_leon.py tests/test_guest_languages.py tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_privacy_first.py -q --tb=short 2>&1 | tail -30`. Expected: 0 failed.
- `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_leon_browser.py tests/test_guest_guide_browser.py tests/test_guest_browser_e2e.py -q --tb=short -rs 2>&1 | tail -30`. Expected: all passed, 0 skipped. If Chromium is missing (`Executable doesn't exist`), say so in the report; CI runs it.
- From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -2` (`design lint: OK`) and `python3 scripts/context_lint.py 2>&1 | tail -3` (`context lint: OK`).

## 7. Acceptance

- [ ] `test_guest_leon_chat.py` (6): chat and script on both doors with the right URL and host label, hidden form plus `<noscript>`, nothing while Leon is off or the guide is not live, the QR contact line in all six languages with no phone or e-mail, every key filled in every language, no `innerHTML`, storage, cookie or remote URL in the script.
- [ ] `test_guest_leon_browser.py` (5, 0 skipped): a greeting round trip at 390 px (counter, cleared box, no error), a host answer with the host's name, the emergency block (`role="alert"`), the waiting line, no layout problems; two texts typed while Leon answers go as one POST, and a `busy` reply is retried with the same `client_id`; a reload mid-reply shows the reply when it lands; without JavaScript one line and no form.
- [ ] `grep -c 'innerHTML' App/app/static/guest-leon.js` is `0`; `grep -c '—' App/app/static/guest-leon.js App/app/templates/guest/_leon.html` both `0`.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found; 0301 is not merged (step 1); a test fails twice; you reach 30 tool calls or about 50k tokens (report `blocked`); a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push, merge, secrets or deploy.

## 9. Report

Write `docs/tasks/0302-report.md` (600 tokens at most) and set `Status: review`: files changed (`git diff --stat`), each command with its last 5 lines, §7 ticked, whether the browser tests ran, deviations, questions, owner steps left. The orchestrator takes the screenshots (`App/.screenshots/0302-guide-chat-*-390.png`).

## Risk list (for the reviewer)

`guest-leon.js` (textContent only, error paths, polling bounds), `_leon.html` (hidden form, CSRF input), the `_host.html` branch. Known limits: a host answer appears within 60 seconds, not live; polling stops after 30 minutes (a reload shows later answers); the chat is hidden while `leon` is not in `UBYHOST_AI_FEATURES`, so guests then have the guide and the contact block only. Works before or after 0304 and 0305: its anchors avoid the lines they edit.

## Owner steps

1. Merge as usual with `scripts/merge-pr-on-green.sh` once CI is green.
2. Leon appears for guests only when `UBYHOST_AI_FEATURES` lists `leon` (0300, owner step 2).
