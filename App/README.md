# UbyHost

Reports foreign guests to the Czech Foreign Police automatically, so you stop
filling in the UbyPort form by hand.

It watches your Airbnb and Booking.com calendars, gives each guest a link where
they enter their own passport details and sign, and sends the batch to UbyPort
inside the three-working-day legal window. You only get involved when something
is missing or the police refuse a record.

## Run it

```bash
./run.sh
```

Then open <http://127.0.0.1:8080>. On first start, UbyHost creates the `admin`
account and writes its one-time password to
`data/initial_admin_credentials`. Sign in and replace that password immediately.

For a deployed environment, set both values before the first start:

```bash
UBYHOST_ADMIN_USERNAME=admin
UBYHOST_ADMIN_PASSWORD='a-long-unique-password'
```

The initial administrator can create host accounts under **Settings → Users**.
Each host gets a private workspace for their own properties and must replace
the temporary password on first login.

The first run installs its dependencies into `.venv/` and starts a **mock
UbyPort server** alongside the app, so nothing is sent to the police until you
say so. On the empty dashboard there is a button that loads a demo apartment
with a sample calendar, so you can click through the whole thing immediately.

## Deploy

| Environment | Where | Purpose |
|-------------|--------|---------|
| **Staging** | Render **`ubyhost-staging`** | Mock UbyPort, free tier — demos and UX testing |
| **Production** | **AWS Lightsail** (`deploy/lightsail`) | Real police reporting (e.g. ubyhost.com) |

The Render blueprint also defines **`ubyhost`** (Starter + disk) for all-on-Render
deployments; this project uses Lightsail for production instead.

Full runbooks: **[docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md)** and
**[docs/PRODUCTION_CHECKLIST.md](../docs/PRODUCTION_CHECKLIST.md)**.

Quick start (staging demo):

1. Push to GitHub → Render **New → Blueprint** → Apply `render.yaml`.
2. Open `https://ubyhost-staging.onrender.com`, sign in with the generated admin
   password (Render → Environment), click **Load demo data**.

Production (Lightsail) requires `.env` admin credentials, UBY-WS per apartment, and
`UBYHOST_UBYPORT_ENV=test` before `prod`. See `deploy/lightsail/` and
[docs/LIGHTSAIL.md](../docs/LIGHTSAIL.md).

**Cloudflare Pages is not suitable** — it cannot run this FastAPI app or SQLite.

Docker: `docker build -t ubyhost .` from the repo root (see `Dockerfile`).

### Name and branding

**UbyHost** is a host-facing tool for preparing guest data and sending it to the
Czech Foreign Police **UbyPort** web service. It is a separate product name for
your side of the workflow, not a government system. If you plan commercial use,
confirm trademark and naming with your lawyer; the police registration system
remains UbyPort.

## How it works

```
Airbnb / Booking.com iCal  ──►  stays with dates only
                                     │
        guest opens your permalink ──┤
                                     ▼
                   passport details + signature
                                     │
                        validated against the
                        UbyPort field rules
                                     │
                                     ▼
                        UbyPort (SOAP over NTLM)
                                     │
                     ┌───────────────┴───────────────┐
                     ▼                               ▼
              Doručenka PDF                  per-record errors
              (kept as proof)                (shown to you, fixable)
```

The calendars are the trigger. An Airbnb export gives you dates, a
reservation URL and the last four digits of a phone number — no name, no
e-mail, no headcount. Booking.com gives you even less. That is enough to know
somebody is arriving, which is all the app needs: the guest supplies the rest
themselves.

Because there is no e-mail address in the feed, the app cannot write to guests.
Instead each apartment gets one permanent link. Paste it into your automated
arrival message on Airbnb or Booking.com and it works for every future booking.
A guest who opens it sees only the stays starting in the next few days, picks
theirs, says how many people are coming, and fills in one short form per
person. Nobody sees anybody else's details.

## What you have to do once

1. **Get web-service credentials.** These are *not* your normal UbyPort login.
   Ask the police for a `UBY-WS…` account: e-mail `reguby@pcr.cz` or use data
   box `ybndqw9`, and say you want to report through the web service
   (`webová služba UBY-WS`) for your IDUB. State your IČO, the accommodation's
   IDUB and its address. Expect a few days.
2. **Add the apartment.** Its IDUB, five-letter mark and address have to match
   the police registration exactly, or every submission comes back rejected.
3. **Paste your calendar links.** Airbnb: Calendar → Availability → Connect to
   another website → Export calendar. Booking.com: Calendar → Sync calendars →
   Export.
4. **Paste the guest link** into your check-in message on both portals.
5. **Switch to the real service.** Set `UBYHOST_UBYPORT_ENV=test` to try the
   police test environment, then `prod` when you are satisfied.

## Choosing how much it does by itself

Each apartment picks one, as the UbyPort operating rules require:

- **Immediate** — the record goes out after the host verifies the guest against
  their travel document.
- **Scheduled** — it goes out a set number of hours after check-in, so late
  arrivals and corrections are batched together.
- **Manual** — nothing leaves without your click.

Whichever you choose, an accepted record is never sent again on its own. Since
1 September 2025 the police reject duplicates and count them against you, so a
re-send needs a deliberate confirmation.

## What it keeps for you

- The **Doručenka** (receipt PDF with the pseudo-stamp) for every transmission,
  plus the exact XML that was sent.
- A signed **registration form PDF** per guest.
- The **house book** (domovní kniha), including Czech nationals, who have no
  reporting duty but still belong in the book. Exportable as CSV; the six-year
  retention period is noted on every record.
- An audit log of everything the app and you did.

## Configuration

Everything has a working default; set these only if you need to.

| Variable | Default | What it does |
| --- | --- | --- |
| `UBYHOST_UBYPORT_ENV` | `mock` | `mock`, `test` or `prod` — which endpoint reports go to |
| `UBYHOST_PUBLIC_BASE_URL` | `http://127.0.0.1:8080` | The address guests reach, used to build their link |
| `UBYHOST_DATA_DIR` | `./data` | Database and secret key |
| `UBYHOST_SECRET_KEY` | generated once into `data/secret_key` | Signs cookies and encrypts the UbyPort password at rest |
| `UBYHOST_ICAL_POLL_MINUTES` | `60` | How often calendars are re-read |
| `UBYHOST_SUBMIT_SWEEP_MINUTES` | `10` | How often queued records are sent |
| `UBYHOST_ENABLE_SCHEDULER` | `1` | Set to `0` to stop all background work |

Losing `UBYHOST_SECRET_KEY` means re-entering the UbyPort password; nothing
else is lost.

## Tests

```bash
.venv/bin/python -m pytest tests -q
```

The end-to-end test starts the mock police server for real and drives the whole
path: calendar import, guest form, signature, submission, Doručenka, duplicate
refusal, a network outage, and the deadline alarm.

`tools/smoke.py` fetches every page of a running instance and reports anything
that failed to render.

## What it deliberately does not do

Accommodation fees (`poplatek z pobytu`) are a separate obligation to your
municipality and are not calculated or reported here.

## UI and design

Host and guest surfaces use a single **light** design system (see
`app/static/tokens.css`). **Dark mode is not part of the product** and must not
be added unless the owner explicitly asks. Full policy for contributors and
agents: **[docs/DESIGN.md](../docs/DESIGN.md)**.
