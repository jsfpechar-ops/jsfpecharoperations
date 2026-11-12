# 1166: Cloudflare "we're down" page

Status: todo
Depends on: none | Base commit: 8000926 | Branch: claude/dr-down-page
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add a Cloudflare Worker that answers every request with a short Czech and English "UbyHost is temporarily unavailable" page, and a runbook section that tells the owner how to turn it on and off. This is step 5 of [portable-disaster-recovery](../plans/portable-disaster-recovery.md) (gap 6): during an outage (AWS gone, rebuild in progress) hosts and guests see a clear message instead of a Cloudflare 52x error.

## 2. Context

Rules that apply: AGENTS.md rule 2 (no third-party scripts, no tracking cookies; the Worker makes no outbound request), rule 3 (public repo: no operator identity, so no mailto or contact address on the page), rule 6 (light mode only), rule 9 (copy: no sentence the reader does not need).

Design (decided, do not change):

- One new file, `deploy/cloudflare/down-page-worker.js`: a Cloudflare Worker in ES module syntax. It never calls `fetch()` and never contacts the origin or any other host. It returns the page with status 503 and the headers `content-type: text/html; charset=utf-8`, `cache-control: no-store`, `retry-after: 3600`, `x-robots-tag: noindex`. A HEAD request gets the same status and headers with no body.
- The HTML is a const template string in the same file: inline `<style>` only, no script, no image, no font, no external URL except one link to the police portal `https://ubyport.policie.cz/`.
- The owner turns the page on by adding a Worker route for the domain and turns it off by deleting the route after the new box answers. The Free plan is enough. The runbook's `curl --resolve <DOMAIN>:443:<NEW_IP>` checks bypass Cloudflare, so they still reach the new box while the route is on.
- Heading `## Show the "we're down" page` gives the GitHub anchor `#show-the-were-down-page` (quotes and apostrophe are dropped).

## 3. Files

| Path | Action | What |
|---|---|---|
| docs/tasks/1166-cloudflare-down-page.md | done | this brief (committed by the orchestrator) |
| deploy/cloudflare/down-page-worker.js | create | the Worker and the page |
| docs/DISASTER_RECOVERY.md | edit | new section, plus step 4 in "Point Cloudflare at the new box" |
| docs/CLOUDFLARE.md | edit | one pointer line after the troubleshooting table |
| docs/plans/portable-disaster-recovery.md | edit | step 5 row and gap 6 line |
| docs/tasks/1166-report.md | create | the report (§9) |

No other file may change. Nothing in App/, go/ or docs/context/.

## 4. Steps

### Step 1: the Worker

First check the folder does not exist yet: `ls deploy/cloudflare 2>&1 | tail -5` says "No such file". Then `mkdir -p deploy/cloudflare` and write exactly this content:

```js
// "We're down" page for UbyHost (brief 1166, disaster-recovery plan step 5).
// The owner routes this Worker for the domain during an outage; see
// docs/DISASTER_RECOVERY.md. It makes no outbound request and reads no data.

const PAGE = `<!doctype html>
<html lang="cs">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>UbyHost je dočasně nedostupný</title>
<style>
html { background: #fff; color: #1a1a1a; }
body { font-family: system-ui, sans-serif; line-height: 1.5; max-width: 36rem; margin: 0 auto; padding: 1.5rem 1rem; }
h1 { font-size: 1.5rem; margin: 0 0 1rem; }
h2 { font-size: 1.1rem; margin: 1.5rem 0 0.5rem; }
p { margin: 0 0 0.75rem; }
a { color: #0b4fa8; }
hr { border: 0; border-top: 1px solid #ccc; margin: 2rem 0; }
</style>
</head>
<body>
<main>
<h1>UbyHost je dočasně nedostupný</h1>
<p>Stěhujeme UbyHost na nový server. Služba se vrátí během několika hodin. Vaše data jsou v bezpečí.</p>
<h2>Pro ubytovatele</h2>
<p>Blíží-li se lhůta pro ohlášení hosta, ohlaste ho ručně v portálu policie (<a href="https://ubyport.policie.cz/">Ubyport</a>) jako obvykle.</p>
<h2>Pro hosty</h2>
<p>Nemusíte nic dělat. Pokud bude něco potřeba, ubytovatel se vám ozve.</p>
<hr>
<section lang="en">
<h1>UbyHost is temporarily unavailable</h1>
<p>We are moving UbyHost to a new server. It will be back within hours. Your data is safe.</p>
<h2>For hosts</h2>
<p>If a guest's registration deadline is near, register the guest by hand in the police portal (<a href="https://ubyport.policie.cz/">Ubyport</a>) as usual.</p>
<h2>For guests</h2>
<p>There is nothing for you to do. Your host will contact you if needed.</p>
</section>
</main>
</body>
</html>
`;

const HEADERS = {
  "content-type": "text/html; charset=utf-8",
  "cache-control": "no-store",
  "retry-after": "3600",
  "x-robots-tag": "noindex",
};

export default {
  async fetch(request) {
    const body = request.method === "HEAD" ? null : PAGE;
    return new Response(body, { status: 503, headers: HEADERS });
  },
};
```

Check: `node --check` and the smoke test in §6 (commands 1 and 2). Commit: `1166 step 1`.

### Step 2: docs/DISASTER_RECOVERY.md

Edit A. Anchor: `grep -nF '## Rebuild on a new box' docs/DISASTER_RECOVERY.md` must print exactly one line (37). Replace that line with the block below (the new section, a blank line, then the old heading line unchanged):

````
## Show the "we're down" page

Use this while the server is gone and the rebuild runs, so hosts and guests see a clear message instead of a Cloudflare error. The page is the Worker in `deploy/cloudflare/down-page-worker.js`. It never contacts any server. Steps 1 and 2 can be done ahead of time and kept.

1. In Cloudflare, open Workers & Pages, Create, Worker. Name it `ubyhost-down` and click Deploy.
2. Click Edit code, delete the sample code, paste the whole content of `deploy/cloudflare/down-page-worker.js`, and click Deploy. The Free plan is enough.
3. Open the Worker, Settings, Domains & Routes, Add, Route. Zone `ubyhost.com`, route `ubyhost.com/*`. Repeat with `www.ubyhost.com/*` if that host exists.
4. Open the site in a private window and check that the "we're down" page shows.
5. Keep working on the rebuild. The `curl --resolve` checks below bypass Cloudflare, so they still reach the new box.

The page is turned off in "Point Cloudflare at the new box", step 4.

## Rebuild on a new box
````

Edit B. Anchor: `grep -nF '3. Check that `.env` has `CLOUDFLARE_PROXY=1`.' docs/DISASTER_RECOVERY.md` must print one line. Directly after that line add:

```
4. Turn off the "we're down" page: in Cloudflare, Workers & Pages, `ubyhost-down`, Settings, Domains & Routes, delete the route(s). Then open the site in a private window and check the normal start page loads.
```

Do not edit "## Drill". Check: `grep -n 'down' docs/DISASTER_RECOVERY.md | tail -10` shows the new section heading and step 4. Commit: `1166 step 2`.

### Step 3: docs/CLOUDFLARE.md

Anchor: `grep -nF '| **Deploy says missing origin.pem** |' docs/CLOUDFLARE.md` must print line 498. After that line insert a blank line and then this line (the blank line after it, before `### DNS-only mode (grey cloud)`, already exists):

```
Outage page while the server is being rebuilt: [DISASTER_RECOVERY](DISASTER_RECOVERY.md#show-the-were-down-page).
```

Check: `sed -n 496,503p docs/CLOUDFLARE.md` shows the table, a blank line, the new line, a blank line, then the `###` heading. Commit: `1166 step 3`.

### Step 4: docs/plans/portable-disaster-recovery.md

Edit A. Find with `grep -nF '| 5 | Cloudflare' docs/plans/portable-disaster-recovery.md` (line 46). Old line:

```
| 5 | Cloudflare "we're down" page (static, Worker or custom error page) | S | Haiku brief + owner | 1 |
```

New line:

```
| 5 | Cloudflare "we're down" page: Worker the owner routes during an outage (brief 1166) | S | Haiku brief + owner | 1 |
```

Edit B. Find with `grep -nF 'No "we'"'"'re down" page' docs/plans/portable-disaster-recovery.md` (line 25). Old text: `No "we're down" page (CLOUDFLARE.md has none).` New text: `No "we're down" page (CLOUDFLARE.md has none). The page: brief 1166.` The rest of the line stays as it is.

Commit: `1166 step 4`.

### Step 5: report

Run §6, then write `docs/tasks/1166-report.md` (§9), set `Status: review`, commit `1166 step 5`.

## 5. Do not touch

App/, go/, docs/context/, any other file in deploy/, any file not in §3. Hard rules: 2 (no script, no third-party URL except the police portal), 3 (no operator identity, no mailto), 6 (light mode only), 9 (copy). Do not change the copy or the headers in step 1; the owner reviews the Czech text.

## 6. Commands

1. `node --check deploy/cloudflare/down-page-worker.js 2>&1 | tail -5` expect no output.
2. Smoke test (a copy is used because node treats `.js` as CommonJS here):

```bash
cp deploy/cloudflare/down-page-worker.js /tmp/dpw.mjs && node --input-type=module -e "import w from '/tmp/dpw.mjs'; const r = await w.fetch(new Request('https://ubyhost.com/x')); console.log(r.status, r.headers.get('retry-after'), r.headers.get('cache-control'), (await r.text()).length); const h = await w.fetch(new Request('https://ubyhost.com/x',{method:'HEAD'})); console.log(h.status, (await h.text()).length)" 2>&1 | tail -5
```

Expect `503 3600 no-store <n>` (n above 1000) and `503 0`.
3. `grep -c '<script' deploy/cloudflare/down-page-worker.js` expect `0`.
4. `grep -c 'fetch(' deploy/cloudflare/down-page-worker.js` expect `1` (only `async fetch(request)`).
5. `grep -oE 'https?://[^"'"'"' )<]+' deploy/cloudflare/down-page-worker.js | sort -u` expect exactly one line: `https://ubyport.policie.cz/`.
6. `grep -c 'show-the-were-down-page' docs/CLOUDFLARE.md` expect `1`.
7. `python3 scripts/context_lint.py 2>&1 | tail -5` expect `context lint: OK`.
8. `git diff --stat 8000926 2>&1 | tail -10` lists only the §3 files.

The [test-map](../context/test-map.md) has no row for this change (one static Worker file and docs); no pytest runs.

## 7. Acceptance

- [ ] `deploy/cloudflare/down-page-worker.js` matches step 1; commands 1 to 5 give the expected output.
- [ ] GET returns 503 with the four headers; HEAD returns 503 and an empty body.
- [ ] `docs/DISASTER_RECOVERY.md` has the new section between "Two servers never file at once" and "Rebuild on a new box", and step 4 in "Point Cloudflare at the new box".
- [ ] `docs/CLOUDFLARE.md` has the pointer line; the anchor matches the heading.
- [ ] The plan's step 5 row and gap 6 line are updated.
- [ ] `context lint: OK`; only the §3 files changed.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt or anchor is not found, or `deploy/cloudflare/` already exists;
- a check fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1166-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- deploy/cloudflare/down-page-worker.js (no `fetch(` call, no script, one external URL, headers, HEAD handling, Czech copy)
- docs/DISASTER_RECOVERY.md (steps correct and in order; turn-off step present)

## Owner steps

1. Review the Czech copy in `deploy/cloudflare/down-page-worker.js` (the text between `<main>` and `<hr>`).
2. After the merge there is nothing to deploy: no server change.
3. At the next drill or outage, follow the new section "Show the "we're down" page" in `docs/DISASTER_RECOVERY.md`. Optional: create the `ubyhost-down` Worker ahead of time (its steps 1 and 2), without adding a route.
