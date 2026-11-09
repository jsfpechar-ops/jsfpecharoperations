# QA-04: Host account settings, security, help and empty states

Status: todo
Depends on: none | Base commit: current `main` | Branch: none (report only, no PR)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens. Read-only QA: never edit code.

## 1. Objective

Click through account settings, subscription, privacy requests, 2FA and passkey prompts, login, the Help & guide pages and every empty state, and report problems.
Screenshots go to `/mnt/project-files/qa/host-account/`, findings to `/mnt/project-files/qa/findings/host-account.md`. You REPORT, you do not fix.

## 2. Start the app (call 1 to 3; do not explore)

Run from the repo root. Port 8090 avoids clashes.

```
cd /home/user/jsfpecharoperations/App && [ -d .venv ] || (python3.12 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -3)
.venv/bin/python -m playwright install chromium 2>&1 | tail -3
export DATA_DIR=/tmp/qa-data PORT=8090 PUBLIC_BASE_URL=http://127.0.0.1:8090 UBYHOST_DEPLOYMENT=staging UBYHOST_STAGING_NO_LOGIN=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_MAIL_BACKEND=disabled
rm -rf $DATA_DIR && mkdir -p $DATA_DIR /mnt/project-files/qa/host-account /mnt/project-files/qa/findings
(nohup ./run.sh > /tmp/qa-app.log 2>&1 &) ; sleep 8; curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8090/healthz
```

Expect `200`. Seed the demo data (staging mode only) inside your Playwright script: open `/`, read `<meta name="csrf-token">`, then `page.request.post("/demo", headers={"x-csrf-token": token})`. Expect 2 apartments, 18 reservations, 8 guests. Not 200 or no data: STOP (section 8).
Host language: `page.request.post("/language", form={"lang":"cs","next":"/"}, headers={"x-csrf-token": token})` once per context, then load the route. Guest pages take `?lang=cs` or `?lang=en`.
Do not set `PYTHONPATH`. Do not run pytest. Do not print guest names, passports or addresses in the report (public repo): say "demo guest 3".

## 2b. Area context (pasted; open no other file)

Host pages need no login in this mode (`UBYHOST_STAGING_NO_LOGIN=1`). Apartment id and reservation id: read them from the seeded `/apartments` and `/reservations` pages (first link per row) inside the script and substitute APT, RES, GUEST in the routes below.
Empty states: run the loop on a fresh DB (before `/demo`) for the list pages, then again after seeding. Passkeys cannot be completed in headless Chromium: only check the prompt, the explanation and the error when you cancel (use a CDP virtual authenticator only if it takes under 2 calls).

## 2c. Routes (BASE = http://127.0.0.1:8090; the loop covers every one, 3 viewports x 2 languages)

1. `/settings`
2. `/guide`
3. `/predplatne` (subscription)
4. `/privacy-requests`
5. `/account/2fa/setup`
6. `/account/email/confirm`
7. `/account/accept`
8. `/login`, `/login/link`, `/login/2fa`
9. Empty states on a fresh DB: `/apartments`, `/reservations`, `/submissions`, `/housebook`, `/stay-fees`, `/payments`, `/booking-sites`, `/guest-links`, `/smart-locks`, `/entities`, `/cleaning` (skip 404)
10. `/legal`, `/terms`, `/privacy`, `/dpa`, `/subprocessors`

## 2d. Interactions to try (second loop, 390 px, en then cs)

- Settings: toggle each switch twice, save with no change, change email to an invalid address and to a 300-character one.
- Login: wrong email format, empty submit, JS off (`java_script_enabled=False`): the form must still work.
- 2FA/passkey: is the wording plain ("fingerprint or phone unlock") or jargon? Is there a way out (Cancel) and a recovery hint? Cancel the browser prompt: friendly message or raw error?
- Guide: click every guide card and tab, search box if any, the Havel/AI help if shown (it may say unavailable: that is fine if worded kindly).
- Empty states: does each say what to do next with ONE obvious button, and not repeat the heading?
- Language switch: change language on each page via `POST /language`; does the user land back on the same page?

## 3. The two personas (judge every screenshot as both)

- **Elderly person (Mrs Novakova, 78, phone with large system font):** text under 16 px or low contrast (grey on white under 4.5:1), unclear labels, jargon (police, IDUB, iCal, API, token, webhook, passkey with no explanation), tap targets under 44 px (measure with `boundingBox()` of every `a, button, input, select, summary`, report those under 44 px high), icon-only buttons with no text, placeholder used as label, unclear which button is the main one, dates in an unfamiliar format.
- **Child (Tom, 10, clicks everything):** dead ends (no way back or forward), scary or technical errors (stack traces, raw keys like `flash.error.x`, English text in Czech mode, `None`, `undefined`, `{{`), lost work (back, refresh or double click erases or duplicates a form), buttons that do nothing, text cut off or overlapping, horizontal scroll at 390 px.

Automatic checks to run on every page in the loop (log, do not fix): `document.documentElement.scrollWidth > innerWidth` (horizontal scroll), console errors, failed requests (status 400 and above), text matching `/flash\.|\bNone\b|undefined|\{\{|Traceback/`, Czech mode showing a sentence in English (eyeball the screenshot), images with no `naturalWidth`.

## 4. Report format

Append to `/mnt/project-files/qa/findings/host-account.md` (create it; one block per finding; no prose elsewhere):

```
### host-account-NN
- severity: P0 broken | P1 confusing or lost work | P2 ugly or inconsistent | P3 polish
- page: /route    viewport: 390|768|1280    language: en|cs    persona: elderly|child|both
- wrong: one sentence, what you saw
- screenshot: /mnt/project-files/qa/host-account/<file>.png
- fix: one sentence, a suggestion only
```

Number NN from 01. Merge identical findings across viewports or languages into one (list all). Max 40 findings: keep the worst. Finish with a line `SUMMARY: n P0, n P1, n P2, n P3, routes covered k of N`.

## 5. Rules for this brief

- **Report only. Never edit any file under App/, docs/ or tests/.** No commits, no PR, no push. Your only writes are screenshots, the findings file, your Playwright script in `/tmp/qa-host-account.py`, and the section 7 report.
- Budget: 30 tool calls. Plan: call 1 setup, call 2 write the script, call 3 to 6 run it (split by route group if it times out; use `timeout=600000`), 7 to 10 look at screenshots (open at most 12 images, pick the worst per route group using the automatic checks and the thumbnails you judge), the rest for findings. Stop at 25 calls and report what is done.
- Script shape: one Python file, `sync_playwright`, loop `for lang in ("en","cs")`, `for (w,h) in ((390,844),(768,1024),(1280,800))`, `for route in ROUTES`, new context per language and viewport, `page.goto(BASE+route)`, `wait_for_load_state("networkidle")`, `page.screenshot(path=f"/mnt/project-files/qa/host-account/{slug}_{w}_{lang}.png", full_page=True)`, run the automatic checks, append one JSON line per page to `/tmp/qa-host-account.jsonl`. Wrap each page in try/except so one failure does not stop the loop.
- Slug = route with `/` replaced by `_`. Interactions (clicks, form submits) go in a second small loop, same script, with a screenshot after each.
- Light mode only; do not report missing dark mode.

## 6. Commands

Only the section 2 start commands and `.venv/bin/python /tmp/qa-host-account.py 2>&1 | tail -30` from `App/`. Stop the app at the end: `pkill -f "uvicorn" ; pkill -f run.sh` (expect no output).

## 7. Acceptance

- [ ] Every route in 2c has screenshots for 3 viewports x 2 languages (`ls /mnt/project-files/qa/host-account | wc -l` equals routes x 6, or the report lists the gaps).
- [ ] `/mnt/project-files/qa/findings/host-account.md` exists, follows section 4, ends with the SUMMARY line.
- [ ] `git status --short | tail -5` shows no change under App/, docs/ or tests/ (screenshots and findings live outside the repo).
- [ ] Report written to `/mnt/project-files/qa/findings/host-account-report.md`, 300 tokens at most: routes covered, counts per severity, the 3 worst finding ids, gaps, `Status: review`.

## 8. Stop and ask

Stop and write the report as `blocked` if: the app does not return 200 on `/healthz` after two tries; the demo seed does not create data; a route in 2c returns 404 on first load (log it as a finding P0 once and continue instead, unless every route fails); Chromium cannot be installed; you reach 25 tool calls. Never fix code, never install a new dependency, never touch secrets or main.
