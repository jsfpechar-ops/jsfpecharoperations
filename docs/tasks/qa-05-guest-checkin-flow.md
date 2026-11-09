# QA-05: Guest check-in flow

Status: todo
Depends on: none | Base commit: current `main` | Branch: none (report only, no PR)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens. Read-only QA: never edit code.

## 1. Objective

Click through the whole guest check-in (registration form, minors, groups, long names and unusual cities, back/refresh/double-submit, expired link, JS off) and report problems. Guest filing correctness is the product's top rule: report any case where entered data could be lost or filed wrong as P0 or P1.
Screenshots go to `/mnt/project-files/qa/guest-checkin/`, findings to `/mnt/project-files/qa/findings/guest-checkin.md`. You REPORT, you do not fix.

## 2. Start the app (call 1 to 3; do not explore)

Run from the repo root. Port 8090 avoids clashes.

```
cd /home/user/jsfpecharoperations/App && [ -d .venv ] || (python3.12 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -3)
.venv/bin/python -m playwright install chromium 2>&1 | tail -3
export DATA_DIR=/tmp/qa-data PORT=8090 PUBLIC_BASE_URL=http://127.0.0.1:8090 UBYHOST_DEPLOYMENT=staging UBYHOST_STAGING_NO_LOGIN=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_MAIL_BACKEND=disabled
rm -rf $DATA_DIR && mkdir -p $DATA_DIR /mnt/project-files/qa/guest-checkin /mnt/project-files/qa/findings
(nohup ./run.sh > /tmp/qa-app.log 2>&1 &) ; sleep 8; curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8090/healthz
```

Expect `200`. Seed the demo data (staging mode only) inside your Playwright script: open `/`, read `<meta name="csrf-token">`, then `page.request.post("/demo", headers={"x-csrf-token": token})`. Expect 2 apartments, 18 reservations, 8 guests. Not 200 or no data: STOP (section 8).
Host language: `page.request.post("/language", form={"lang":"cs","next":"/"}, headers={"x-csrf-token": token})` once per context, then load the route. Guest pages take `?lang=cs` or `?lang=en`.
Do not set `PYTHONPATH`. Do not run pytest. Do not print guest names, passports or addresses in the report (public repo): say "demo guest 3".

## 2b. Area context (pasted; open no other file)

Guest link: the seeded demo gives a per-apartment link. In the script, read `/guest-links` on the host side to get `/l/TOKEN`; the demo route `/l/TOKEN/demo/RES` opens a seeded stay. Guest pages take `?lang=en|cs` (also de, others may exist: try `de` once). Use a NEW browser context per run with NO host cookie. Guests are real people: use only invented data (Jana Testova, 2000-01-01, passport `QA000001`).

## 2c. Routes (BASE = http://127.0.0.1:8090; the loop covers every one, 3 viewports x 2 languages)

1. `/l/TOKEN` (landing and PIN if asked: `POST /l/TOKEN/pin`)
2. `/l/TOKEN/privacy`
3. `/l/TOKEN/RES` (stay overview)
4. `/l/TOKEN/RES/new` (registration form, first person)
5. `/l/TOKEN/RES/edit/GUEST`
6. `/l/TOKEN/RES/claim`
7. `/l/TOKEN/demo/RES`
8. `/l/BADTOKEN` and `/l/TOKEN/999999` (expired or wrong link)

## 2d. Interactions to try (second loop, 390 px, en then cs)

- Fill the form fully and save: success page? Is it clear what happens next and that the data is filed?
- Minors: a child born 3 years ago and one born 17 years ago: any question that makes no sense (passport for a baby)? Party size via `/party`, `/another`.
- Groups: 6 guests in a row; progress indicator right? Can a guest go back and edit person 2?
- Names: 120-character name; `Zizkov`, `Hradec Kralove`, `Zwierzyniec`; city `Ceske Budejovice`; non-Latin `Mueller`, Cyrillic, Arabic, emoji; apostrophes `O'Brien`; leading spaces. Check no clipping and no wrong rejection.
- Back, Refresh and F5 after submit; double-click Save (no duplicate person); submit with network aborted (`page.route("**/save", lambda r: r.abort())`): is typed data kept?
- Expired link (`/l/BADTOKEN`): is the message kind, in the right language, with a next step?
- JS off (new context `java_script_enabled=False`): can the form be completed?
- Scan/upload passport step: upload a non-image; error friendly? (do not use a real document)

## 3. The two personas (judge every screenshot as both)

- **Elderly person (Mrs Novakova, 78, phone with large system font):** text under 16 px or low contrast (grey on white under 4.5:1), unclear labels, jargon (police, IDUB, iCal, API, token, webhook, passkey with no explanation), tap targets under 44 px (measure with `boundingBox()` of every `a, button, input, select, summary`, report those under 44 px high), icon-only buttons with no text, placeholder used as label, unclear which button is the main one, dates in an unfamiliar format.
- **Child (Tom, 10, clicks everything):** dead ends (no way back or forward), scary or technical errors (stack traces, raw keys like `flash.error.x`, English text in Czech mode, `None`, `undefined`, `{{`), lost work (back, refresh or double click erases or duplicates a form), buttons that do nothing, text cut off or overlapping, horizontal scroll at 390 px.

Automatic checks to run on every page in the loop (log, do not fix): `document.documentElement.scrollWidth > innerWidth` (horizontal scroll), console errors, failed requests (status 400 and above), text matching `/flash\.|\bNone\b|undefined|\{\{|Traceback/`, Czech mode showing a sentence in English (eyeball the screenshot), images with no `naturalWidth`.

## 4. Report format

Append to `/mnt/project-files/qa/findings/guest-checkin.md` (create it; one block per finding; no prose elsewhere):

```
### guest-checkin-NN
- severity: P0 broken | P1 confusing or lost work | P2 ugly or inconsistent | P3 polish
- page: /route    viewport: 390|768|1280    language: en|cs    persona: elderly|child|both
- wrong: one sentence, what you saw
- screenshot: /mnt/project-files/qa/guest-checkin/<file>.png
- fix: one sentence, a suggestion only
```

Number NN from 01. Merge identical findings across viewports or languages into one (list all). Max 40 findings: keep the worst. Finish with a line `SUMMARY: n P0, n P1, n P2, n P3, routes covered k of N`.

## 5. Rules for this brief

- **Report only. Never edit any file under App/, docs/ or tests/.** No commits, no PR, no push. Your only writes are screenshots, the findings file, your Playwright script in `/tmp/qa-guest-checkin.py`, and the section 7 report.
- Budget: 30 tool calls. Plan: call 1 setup, call 2 write the script, call 3 to 6 run it (split by route group if it times out; use `timeout=600000`), 7 to 10 look at screenshots (open at most 12 images, pick the worst per route group using the automatic checks and the thumbnails you judge), the rest for findings. Stop at 25 calls and report what is done.
- Script shape: one Python file, `sync_playwright`, loop `for lang in ("en","cs")`, `for (w,h) in ((390,844),(768,1024),(1280,800))`, `for route in ROUTES`, new context per language and viewport, `page.goto(BASE+route)`, `wait_for_load_state("networkidle")`, `page.screenshot(path=f"/mnt/project-files/qa/guest-checkin/{slug}_{w}_{lang}.png", full_page=True)`, run the automatic checks, append one JSON line per page to `/tmp/qa-guest-checkin.jsonl`. Wrap each page in try/except so one failure does not stop the loop.
- Slug = route with `/` replaced by `_`. Interactions (clicks, form submits) go in a second small loop, same script, with a screenshot after each.
- Light mode only; do not report missing dark mode.

## 6. Commands

Only the section 2 start commands and `.venv/bin/python /tmp/qa-guest-checkin.py 2>&1 | tail -30` from `App/`. Stop the app at the end: `pkill -f "uvicorn" ; pkill -f run.sh` (expect no output).

## 7. Acceptance

- [ ] Every route in 2c has screenshots for 3 viewports x 2 languages (`ls /mnt/project-files/qa/guest-checkin | wc -l` equals routes x 6, or the report lists the gaps).
- [ ] `/mnt/project-files/qa/findings/guest-checkin.md` exists, follows section 4, ends with the SUMMARY line.
- [ ] `git status --short | tail -5` shows no change under App/, docs/ or tests/ (screenshots and findings live outside the repo).
- [ ] Report written to `/mnt/project-files/qa/findings/guest-checkin-report.md`, 300 tokens at most: routes covered, counts per severity, the 3 worst finding ids, gaps, `Status: review`.

## 8. Stop and ask

Stop and write the report as `blocked` if: the app does not return 200 on `/healthz` after two tries; the demo seed does not create data; a route in 2c returns 404 on first load (log it as a finding P0 once and continue instead, unless every route fails); Chromium cannot be installed; you reach 25 tool calls. Never fix code, never install a new dependency, never touch secrets or main.
