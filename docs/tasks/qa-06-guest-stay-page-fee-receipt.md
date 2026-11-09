# QA-06: Guest stay page, stay fee pay box, receipt

Status: todo
Depends on: none | Base commit: current `main` | Branch: none (report only, no PR)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens. Read-only QA: never edit code.

## 1. Objective

Click through the guest stay page after check-in: stay overview, door code area, stay fee pay box (QR, bank details, receipt or confirmation) and the guest guide, and report problems.
Screenshots go to `/mnt/project-files/qa/guest-stay/`, findings to `/mnt/project-files/qa/findings/guest-stay.md`. You REPORT, you do not fix.

## 2. Start the app (call 1 to 3; do not explore)

Run from the repo root. Port 8090 avoids clashes.

```
cd /home/user/jsfpecharoperations/App && [ -d .venv ] || (python3.12 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -3)
.venv/bin/python -m playwright install chromium 2>&1 | tail -3
export DATA_DIR=/tmp/qa-data PORT=8090 PUBLIC_BASE_URL=http://127.0.0.1:8090 UBYHOST_DEPLOYMENT=staging UBYHOST_STAGING_NO_LOGIN=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_MAIL_BACKEND=disabled
rm -rf $DATA_DIR && mkdir -p $DATA_DIR /mnt/project-files/qa/guest-stay /mnt/project-files/qa/findings
(nohup ./run.sh > /tmp/qa-app.log 2>&1 &) ; sleep 8; curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8090/healthz
```

Expect `200`. Seed the demo data (staging mode only) inside your Playwright script: open `/`, read `<meta name="csrf-token">`, then `page.request.post("/demo", headers={"x-csrf-token": token})`. Expect 2 apartments, 18 reservations, 8 guests. Not 200 or no data: STOP (section 8).
Host language: `page.request.post("/language", form={"lang":"cs","next":"/"}, headers={"x-csrf-token": token})` once per context, then load the route. Guest pages take `?lang=cs` or `?lang=en`.
Do not set `PYTHONPATH`. Do not run pytest. Do not print guest names, passports or addresses in the report (public repo): say "demo guest 3".

## 2b. Area context (pasted; open no other file)

The stay page is `/l/TOKEN/RES` (`App/app/routes/guest.py`, template `guest/stay.html`). The pay box shows only when the party is complete. Complete the party first with invented data (see brief qa-05 style: Jana Testova), or use a seeded reservation that already has all guests. The stay fee rate must be set on the host side (`/stay-fees/APT`, set a rate, e.g. 50 CZK per person per night, if empty). Guide: `/g/GUIDETOKEN` from the host `/guest-links`. No real payment: Stripe is not configured, check the fallback (bank details, QR) state.

## 2c. Routes (BASE = http://127.0.0.1:8090; the loop covers every one, 3 viewports x 2 languages)

1. `/l/TOKEN/RES` (incomplete party, then complete party)
2. `/l/TOKEN/RES?saved=1` (just saved banner)
3. `/l/TOKEN/RES?party_error=1`
4. `/g/GUIDETOKEN` and each guide card
5. `/g/GUIDETOKEN/leon` (guest bot; may be disabled: log kindly or not)
6. `/pay/ID/TOKEN` (payment request link from host `/payments/requests/ID/share`)
7. Stay fee receipt or confirmation view, if a link exists on the stay page (find it by link text containing receipt, potvrzeni or doklad; else log "no receipt reachable")

## 2d. Interactions to try (second loop, 390 px, en then cs)

- Fee box: rate 0, rate with decimals, 1 guest vs 6 guests, children exempt wording, a stay of 1 and of 30 nights; is the amount in CZK, with the maths shown, and the same number everywhere?
- Elderly: can the QR be read at 390 px (size, quiet zone)? Is the bank account copyable (large tap target)? Is "what do I pay and to whom" clear in one glance?
- Child: open the page after payment marked paid (host `POST /stay-fees/APT/paid`) and before; is there a dead end or a scary state?
- Door code area: before check-in time, after, after checkout (window closed): message kind and clear?
- Print view: `page.emulate_media(media="print")` screenshot of the receipt if it exists.
- Language switch buttons on the page: land on the same page, state kept?

## 3. The two personas (judge every screenshot as both)

- **Elderly person (Mrs Novakova, 78, phone with large system font):** text under 16 px or low contrast (grey on white under 4.5:1), unclear labels, jargon (police, IDUB, iCal, API, token, webhook, passkey with no explanation), tap targets under 44 px (measure with `boundingBox()` of every `a, button, input, select, summary`, report those under 44 px high), icon-only buttons with no text, placeholder used as label, unclear which button is the main one, dates in an unfamiliar format.
- **Child (Tom, 10, clicks everything):** dead ends (no way back or forward), scary or technical errors (stack traces, raw keys like `flash.error.x`, English text in Czech mode, `None`, `undefined`, `{{`), lost work (back, refresh or double click erases or duplicates a form), buttons that do nothing, text cut off or overlapping, horizontal scroll at 390 px.

Automatic checks to run on every page in the loop (log, do not fix): `document.documentElement.scrollWidth > innerWidth` (horizontal scroll), console errors, failed requests (status 400 and above), text matching `/flash\.|\bNone\b|undefined|\{\{|Traceback/`, Czech mode showing a sentence in English (eyeball the screenshot), images with no `naturalWidth`.

## 4. Report format

Append to `/mnt/project-files/qa/findings/guest-stay.md` (create it; one block per finding; no prose elsewhere):

```
### guest-stay-NN
- severity: P0 broken | P1 confusing or lost work | P2 ugly or inconsistent | P3 polish
- page: /route    viewport: 390|768|1280    language: en|cs    persona: elderly|child|both
- wrong: one sentence, what you saw
- screenshot: /mnt/project-files/qa/guest-stay/<file>.png
- fix: one sentence, a suggestion only
```

Number NN from 01. Merge identical findings across viewports or languages into one (list all). Max 40 findings: keep the worst. Finish with a line `SUMMARY: n P0, n P1, n P2, n P3, routes covered k of N`.

## 5. Rules for this brief

- **Report only. Never edit any file under App/, docs/ or tests/.** No commits, no PR, no push. Your only writes are screenshots, the findings file, your Playwright script in `/tmp/qa-guest-stay.py`, and the section 7 report.
- Budget: 30 tool calls. Plan: call 1 setup, call 2 write the script, call 3 to 6 run it (split by route group if it times out; use `timeout=600000`), 7 to 10 look at screenshots (open at most 12 images, pick the worst per route group using the automatic checks and the thumbnails you judge), the rest for findings. Stop at 25 calls and report what is done.
- Script shape: one Python file, `sync_playwright`, loop `for lang in ("en","cs")`, `for (w,h) in ((390,844),(768,1024),(1280,800))`, `for route in ROUTES`, new context per language and viewport, `page.goto(BASE+route)`, `wait_for_load_state("networkidle")`, `page.screenshot(path=f"/mnt/project-files/qa/guest-stay/{slug}_{w}_{lang}.png", full_page=True)`, run the automatic checks, append one JSON line per page to `/tmp/qa-guest-stay.jsonl`. Wrap each page in try/except so one failure does not stop the loop.
- Slug = route with `/` replaced by `_`. Interactions (clicks, form submits) go in a second small loop, same script, with a screenshot after each.
- Light mode only; do not report missing dark mode.

## 6. Commands

Only the section 2 start commands and `.venv/bin/python /tmp/qa-guest-stay.py 2>&1 | tail -30` from `App/`. Stop the app at the end: `pkill -f "uvicorn" ; pkill -f run.sh` (expect no output).

## 7. Acceptance

- [ ] Every route in 2c has screenshots for 3 viewports x 2 languages (`ls /mnt/project-files/qa/guest-stay | wc -l` equals routes x 6, or the report lists the gaps).
- [ ] `/mnt/project-files/qa/findings/guest-stay.md` exists, follows section 4, ends with the SUMMARY line.
- [ ] `git status --short | tail -5` shows no change under App/, docs/ or tests/ (screenshots and findings live outside the repo).
- [ ] Report written to `/mnt/project-files/qa/findings/guest-stay-report.md`, 300 tokens at most: routes covered, counts per severity, the 3 worst finding ids, gaps, `Status: review`.

## 8. Stop and ask

Stop and write the report as `blocked` if: the app does not return 200 on `/healthz` after two tries; the demo seed does not create data; a route in 2c returns 404 on first load (log it as a finding P0 once and continue instead, unless every route fails); Chromium cannot be installed; you reach 25 tool calls. Never fix code, never install a new dependency, never touch secrets or main.
