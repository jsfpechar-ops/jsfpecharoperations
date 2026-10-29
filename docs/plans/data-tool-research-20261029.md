# Research: choosing the analysis/data tool for UbyHost

Status: research note for the owner, 2026-10-29. Supports §12 of [billing-admin-revenue-cockpit-20261028.md](billing-admin-revenue-cockpit-20261028.md). No decision made — the funnel stays tool-neutral by the owner's instruction.

## 0. What the tool must fit (facts from the repo)

| Fact | Consequence for tool choice |
|---|---|
| Database is **SQLite** (`App/app/db.py`, Postgres-portable SQL only) | Most BI tools connect live to Postgres/MySQL — **not SQLite**. Live DB connection needs either a Postgres move, a sync replica, or the app's own export endpoint (the plan's tool-neutral surface). |
| One operator (Josef), small SaaS, cz/en market | Per-seat pricing (Power BI $14/user/mo, Tableau $75/user/mo) is waste; one viewer means the tool should be free or a flat low fee. |
| Privacy rules: no third-party scripts, minimal data storage, public repo | Cloud dashboards mean business data (MRR, customer names) leaves the infrastructure. GDPR-wise legal (intra processing on a processor), but self-hosted keeps everything in-house — closest to the repo's privacy-first culture. |
| **Grafana Cloud already in use** (Loki + Prometheus, docs/OBSERVABILITY.md) | Grafana is already paid for and running; adding business panels there costs nothing extra, but Grafana is time-series/ops-oriented, weak for business tables (aging, cohorts, invoices). |
| Data volume: hundreds of customers, thousands of invoice rows | Tiny. Any tool handles it; performance is a non-issue at this scale. |
| No new dependency without an owner decision (rule 4) | Whatever is chosen gets a decision line in decisions.md; the app itself ships only the export surface. |

## 1. Candidates compared (2025/2026 market)

| Tool | Cost for 1 operator | Connects to SQLite? | Data stays on your server? | Effort to first dashboard | Scales to? | Verdict for UbyHost |
|---|---|---|---|---|---|---|
| **Excel / Google Sheets + bulk CSV export (plan §12 2a)** | 0 € | n/a (file import) | with Sheets: data leaves to Google; with Excel: stays | minutes | fine to ~10k rows; manual refresh | **Start here.** Zero new tool, zero new risk; the 0446 ZIP already gives everything. |
| **Metabase (open source, self-hosted)** | 0 € software + ~5–10 €/mo VPS (or Docker on the existing Lightail host) | **No native SQLite driver** (community workarounds only) → needs the export endpoint or a small sync to Postgres | **Yes** | ~1 hour | 500+ dashboards, 30+ users; the standard startup choice | **Best fit if you want a real BI tool**: free, self-hosted, privacy-clean, visual builder + SQL. |
| **Looker Studio (Google, free)** | 0 € | No — needs a connector: file upload, Google Sheets, or the plan's JSON/CSV endpoint pulled via a scheduled import | **No** — Google's cloud | ~1 hour | good dashboards, weaker governance | Good if you like the Google ecosystem; business data lives at Google. |
| **Grafana (already running)** | already paid | via plugin/CSV/JSON endpoint | **Yes** (Cloud: at Grafana Labs) | low | ops dashboards, not business tables | Use for uptime/metrics as today; business revenue tables are awkward in Grafana. |
| **Power BI Pro** | $14/user/mo | via OData/CSV gateway | No (Microsoft cloud) | medium (DAX learning) | enterprise | Overkill; per-seat cost for one viewer is pointless. |
| **Tableau** | $75/user/mo | no | No | medium | enterprise | Overkill. |
| **Looker (enterprise, not Looker Studio)** | from ~$3,500–5,000/mo contracts | via BigQuery warehouse | No | weeks (LookML) | large governed orgs | Ruled out: price and weight are absurd for one operator. (If you heard "Looker", the sensible version is Looker Studio.) |
| **Apache Superset (open source)** | 0 € + heavier hosting | SQLAlchemy drivers | Yes | ~a day of DevOps (Flask+Redis+Celery) | large | More power than needed; the setup/maintenance cost exceeds Metabase's for one person. |
| **Redash / Lightdash / Preset** | free–low | varies | mostly | varies | mid | Metabase dominates them for this use case; no reason to prefer. |

Sources: vendor pricing pages and 2025–2026 comparisons (metabase.com, ikemo.io, fastero.com, definite.app, teknologiasolutions.com, valiotti.com).

## 2. Recommendation (advisory, not a decision)

**Now (already in the plan):** ship the tool-neutral export endpoint + bulk CSV ZIP. Analyse in Excel/Google Sheets. This costs nothing and answers everything you asked for ("analyse it somewhere").

**When you outgrow spreadsheets (multiple dashboards, recurring monthly review, filters/cohorts on tap):** self-hosted **Metabase** is the strongest fit — free, one Docker container, data never leaves your server, both a no-SQL builder and full SQL, and it's the de-facto startup standard. The one prerequisite: it can't read SQLite directly, so it consumes the same export endpoint (Metabase can query an API-backed database via a sync job) or a lightweight monthly sync of the `billing_month_snapshot` into a small Postgres.

**Avoid for this use case:** enterprise Looker, Tableau, Power BI (cost/complexity per seat with a single viewer), and Grafana for business tables.

**Scalability note:** the plan's funnel design is exactly what makes any of these swaps painless later — `billing_month_snapshot` + a stable export contract means the tool choice can be deferred and changed without touching the app.

## 3. What the choice would need (when you decide)

1. An owner decision line in `docs/context/decisions.md` (new external service → rule 4; if any data leaves the infra, name the processor in the ROPA line for it).
2. The export endpoint brief (§12.3) if a live tool is chosen; nothing if spreadsheets suffice.
3. If Metabase: a Docker container on the existing host + a sync job (one brief, ~1 session).
