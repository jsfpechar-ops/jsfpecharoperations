# Performance and scale

**No load measurements exist in the repository.** `⚠️ UNKNOWN — needs human input`:
the brief's target of ~1000 clients is not evidenced in code or docs. Current
active-client count, registrations per month and peak RPS must come from the
owner or from production logs. Do not treat the estimates below as measured.

## Architecture limits from code
- **Single writer database.** SQLite WAL with a 30 s busy timeout (`App/app/db.py:667-686`). All writers serialize on the file lock. This is the primary scaling ceiling.
- **One worker.** A single scheduler process (`App/app/worker.py`; `scheduler.lock` refuses a second). Jobs run in one process, `max_instances=1` each (`App/app/scheduler.py`).
- **Web concurrency.** `UBYHOST_WEB_WORKERS` default 2; the Dockerfile comment says 4 on the 8 GB / 2 vCPU Lightsail server (`Dockerfile`). Range 1–16 (`docker-entrypoint.sh`).
- **Sizing documentation.** `docs/LIGHTSAIL.md § Sizing (WP32)` and `§ Scaling the instance` (not read in full here).

## Known bottlenecks (with evidence)

| Area | Evidence | Note |
|---|---|---|
| SQLite writes | `db.py:667-686` | Single writer; any long write blocks all |
| UbyPort submission | `reporting.py` sweep every 10 min; client timeout 60 s (`config.py:146`); batch of 32 (`config.py:144`) | Sequential per-call; no retry at transport level |
| iCal polling | hourly per active feed (`config.py:148`); 5 MiB per feed (`feed_fetch.py:27`) | Work grows linearly with feed count |
| Mail drain | every 5 min (`scheduler.py`); backoff up to 6 h | Bulk sends are slow by design |
| PDF generation | reportlab in request thread (`invoice_pdf.py`, `stay_fee_remittance_pdf.py`) | Synchronous in the web worker |
| OCR | `tesseract` via subprocess (`doc_ocr.py:218-236`) | CPU-bound, in-request or job `⚠️ UNKNOWN` which |
| Photo storage | files under `DATA_DIR`; swept every 12 h | Local disk; no CDN |

## Scaling levers, in the order to pull them
1. **Measure first.** Use `App/tools/perf_report.py` (reads `job run` log lines, `App/tools/perf_report.py:4-5`) and production logs; record clients, registrations/month and p95 request times.
2. **Vertical scale the Lightsail instance** (documented path, `docs/LIGHTSAIL.md § Scaling the instance`).
3. **Tune `UBYHOST_WEB_WORKERS`** within the instance's memory (`docker-entrypoint.sh` range).
4. **Move heavy PDF/OCR work off the request path** into the worker (no queue exists yet; this is a design change).
5. **Replace SQLite with PostgreSQL** — the step that removes the single-writer limit. Not started; see [migration-to-go](migration-to-go.md).
6. Only then consider horizontal web scale-out. Multiple web containers on one SQLite volume are not supported by the design.

## Capacity headroom on current infrastructure
`⚠️ UNKNOWN` — no capacity test or measured headroom in the repo. The `Dockerfile`
and `docs/LIGHTSAIL.md` describe an 8 GB / 2 vCPU instance; confirm the live plan.
