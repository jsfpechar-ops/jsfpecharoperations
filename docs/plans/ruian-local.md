# Local RÚIAN address suggest (1700c, 1700d)

Owner decision 2026-11-17 ([decisions](../context/decisions.md), `[dep]` line): address suggestions for the new-property form come from a local copy of the ČÚZK address-point CSV in Postgres, filled by a monthly Go job and queried with `pg_trgm`. Replaces the live ČÚZK ArcGIS call in `App/app/ruian.py` (route `apartments_ruian_suggest`, `admin.py` ~1334). Briefs: [1700c](../tasks/1700c-go-ruian-import.md) (table + import), [1700d](../tasks/1700d-go-ruian-suggest.md) (route). Facts below were checked 2026-11-17 from the sandbox.

## 1. Goal

`GET /apartments/ruian-suggest?q=` answers from our own database: no per-keystroke request to ČÚZK, no typed text leaves the server, no dependence on ČÚZK uptime. The JSON stays `[{label, fields}]` with `fields` keys `addr_street, addr_house_no, addr_orient_no, addr_zip, addr_obec, addr_obec_cast, addr_okres` (read by `App/app/static/ruian_suggest.js`; the wizard `property.tmpl` loads the same script).

## 2. Verified facts

| # | Fact | Status |
|---|---|---|
| a1 | Host `vdp.cuzk.gov.cz` (the old `vdp.cuzk.cz` 302-redirects there). URL pattern `https://vdp.cuzk.gov.cz/vymenny_format/csv/YYYYMMDD_OB_ADR_csv.zip`, `YYYYMMDD` = last day of the previous month. `20261031_OB_ADR_csv.zip` answers 200, 63,371,330 bytes, `Last-Modified: 2026-11-01 03:39 GMT`, `application/zip`. `20260930_…` also 200 (older months stay); `20261101_…` and `20261030_…` give 404. | VERIFIED (curl HEAD + full download) |
| a2 | One zip with 6,258 per-municipality CSVs (`CSV/20261031_OB_<obec code>_ADR.csv`), 354 MB unzipped, 3,029,843 lines in total (about 3.03 M address points). Not one national file. | VERIFIED |
| a3 | Encoding windows-1250 (no file decodes as UTF-8; cp1250 decode is clean). Separator `;`, no quotes anywhere in a sample of 800 files, LF line ends, one header line per file, no BOM. | VERIFIED |
| a4 | Header (19 columns): `Kód ADM; Kód obce; Název obce; Kód MOMC; Název MOMC; Kód obvodu Prahy; Název obvodu Prahy; Kód části obce; Název části obce; Kód ulice; Název ulice; Typ SO; Číslo domovní; Číslo orientační; Znak čísla orientačního; PSČ; Souřadnice Y; Souřadnice X; Platí Od`. `Typ SO` is `č.p.` (about 88 %) or `č.ev.` (about 12 %). Street is empty for villages without streets. Coordinates are S-JTSK, `Platí Od` an ISO timestamp. | VERIFIED |
| a5 | **There is no okres column.** Python fills `addr_okres` from layer 15. `soucasna/20261031_ST_UKSH.xml.zip` (35 MB zip, 104 MB XML) holds `Okresy` (code, name) but no Obec-to-okres link; per-municipality `OB_<code>_UKSH.xml.zip` files do (1.3 MB each) but are 6,258 downloads. A cheap obec-to-okres source is not found yet. | VERIFIED gap, source UNVERIFIED (question Q1) |
| a6 | The ČÚZK page `cuzk.gov.cz/ruian/Adresni-mista.aspx` was not fetched as text; the licence (open data, CC BY 4.0 with attribution "ČÚZK") is from memory. | UNVERIFIED (Q4) |
| b1 | Production Postgres is `postgres:16-alpine` pinned by digest (`deploy/lightsail/docker-compose.yml:15`). Official Alpine images ship the contrib modules, and `pg_trgm` is a *trusted* extension since PG 13, so a role with CREATE on the database can create it. Not run here: no Postgres server in the sandbox. | UNVERIFIED on the server (Q2); expected to work |
| b2 | No migration or SQL file creates an extension today (`grep` of `App/migrations_pg` and `deploy/lightsail/scripts`: none). Highest migration is `00020_guest_contract.sql`, so the next is `00021`. No open brief claims `00021`. | VERIFIED |
| b3 | `deploy.sh` runs pending goose files before `up`; with `UBYHOST_SCHEMA_APPLY=go` the Go image runs `ubyhost-web migrate apply --expect-database ubyhost`, all pending files in one transaction ([LIGHTSAIL](../LIGHTSAIL.md#deploy-path-and-failure-modes)). Migrations run as `ubyhost_app`, which cannot create roles (comment in `00020`). The check compares columns, indexes and functions, and a Go-applied DB is compared with a Python-built one in CI, so the twin must be plain SQL. | VERIFIED |
| c1 | Go jobs: a kind is a row in the job table (`go/internal/jobs/queue.go`, one open row per kind); handlers are in `jobHandlers` in `go/cmd/ubyhost-web/register_jobs.go` (returns `(count, error)`); a kind must also be in `UBYHOST_JOB_QUEUE_KINDS` and `UBYHOST_GO_JOB_KINDS`; the schedule is `go/internal/scheduler/scheduler.go` `Trigger{Kind, Every | Hour, Minute}`. | VERIFIED |
| c2 | The scheduler has only an interval or a daily Prague-time trigger, **no monthly trigger**. Use a daily trigger (04:45) whose handler returns at once when the newest published month is already imported. | VERIFIED |
| c3 | The Go container mounts `ubyhost-data:/data` read-write and has `mem_limit` 128 MB by default (`UBYHOST_GO_MEM`). The job therefore streams: it must not hold the zip or one CSV in memory beyond a batch. The zip is written to `/data/ruian/` (about 65 MB, removed after the run); entries are read one by one from the zip central directory. Postgres has `network_mode: none`, so the download must happen in the Go container, not in SQL. | VERIFIED (compose); `/data` writability for Go also assumed by brief 1640 |
| d1 | Rule 2: the file is the public register of address points; rows carry no person, no owner, no tenant. Not personal data, so no `retention.py` line and no ROPA/RETENTION line. The import sends no data: a plain GET with no query from the server. A new outbound host `vdp.cuzk.gov.cz` goes into the PR text and [ENVIRONMENT](../ENVIRONMENT.md) (proposal in §7). Removing the live call also stops the typed address text going to `ags.cuzk.cz`, a privacy gain. | VERIFIED by reasoning |

## 3. Table (migration `00021_ruian_address.sql`)

```
ruian_address (
  code        BIGINT PRIMARY KEY,        -- Kód ADM
  street      TEXT NOT NULL DEFAULT '',  -- Název ulice
  house_no    TEXT NOT NULL,             -- Číslo domovní
  orient_no   TEXT NOT NULL DEFAULT '',  -- Číslo orientační + Znak
  is_evid     BOOLEAN NOT NULL DEFAULT FALSE, -- Typ SO = č.ev.
  zip         TEXT NOT NULL DEFAULT '',
  obec        TEXT NOT NULL,             -- Název obce
  obec_code   INTEGER NOT NULL,
  part        TEXT NOT NULL DEFAULT '',  -- Název části obce
  district    TEXT NOT NULL DEFAULT '',  -- Název MOMC / obvodu Prahy, e.g. Praha 1
  search      TEXT NOT NULL              -- folded "street cp/co part obec zip"
)
CREATE INDEX ruian_address_search_trgm ON ruian_address USING gin (search gin_trgm_ops);
CREATE TABLE ruian_import (id SMALLINT PRIMARY KEY CHECK (id = 1), data_date DATE NOT NULL,
  rows BIGINT NOT NULL, imported_at TIMESTAMPTZ NOT NULL);   -- one row: what is loaded
```

`CREATE EXTENSION IF NOT EXISTS pg_trgm;` goes first in the migration. No coordinates and no `Platí Od` (not needed). `search` is lower case with Czech diacritics folded in Go (small rune map, no new dependency); the query is folded the same way, so "vaclavske 1306" finds "Václavské náměstí 1306". Query: every query token must appear as `search LIKE '%tok%'` (trigram-accelerated), ranked by `similarity(search, $q) DESC, code`, `LIMIT 6`. Minimum 3 characters as in Python.

Suggest result mapping: `addr_street`=street, `addr_house_no`=house_no, `addr_orient_no`=orient_no, `addr_zip`=zip, `addr_obec`=obec, `addr_obec_cast`=part only when it differs from obec (Python rule), `addr_okres` see Q1. Label: `street house_no[/orient_no], part, zip district-or-obec` (format of the Python label; byte parity is not required, the JS shows the label as text).

## 4. Import design (Go job kind `ruian_import`)

1. Daily at 04:45 Europe/Prague. Find the newest `YYYYMMDD` (last day of previous month, then the month before) with a `HEAD` that answers 200 and a zip content type; none: log and return.
2. If `ruian_import.data_date` is already that date: return (no download). This is the monthly skip.
3. Download to `/data/ruian/<date>.zip.part` (timeout 20 min, `User-Agent: UbyHost`, no redirects off `vdp.cuzk.gov.cz`), check the size is within 30 to 200 MB, rename.
4. Open the zip; for each CSV entry decode cp1250 to UTF-8 (own 128-entry table, no new dependency), parse `;` lines, skip rows without code or house number, fold the search text, `COPY` into `ruian_address_new` (an `UNLOGGED`-then-regular staging table built `LIKE ruian_address INCLUDING DEFAULTS`, **without** the GIN index while loading).
5. Sanity gate: loaded rows at least 2,500,000 and at least 90 % of the previous count; else drop staging, keep the old table, return an error (job row shows the failure, the `job_failed` alert fires as for other kinds).
6. Build the GIN index on the staging table, `ANALYZE`, then one transaction: `ALTER TABLE ruian_address RENAME TO ruian_address_old; ALTER TABLE ruian_address_new RENAME TO ruian_address;` rename the index, update `ruian_import`, drop the old table. Readers see old or new, never an empty table.
7. A lock (advisory) keeps two runs apart. Remove the zip. On any error the old table stays untouched; staging is dropped at the start of the next run.

## 5. Disk and RAM (estimates, not measured)

- Heap about 3.0 M rows at about 130 bytes is roughly 400 MB; GIN trigram index on about 55 characters of search text roughly 500 to 800 MB. Table total about 1 to 1.2 GB; during the swap old and new coexist, so peak about 2.5 GB, then back to about 1.2 GB. The server has 160 GB disk. WAL-G archives that WAL once a month (about 1.5 GB extra WAL); the daily pg_dump grows by about 150 MB compressed: Q3.
- Go RAM: streaming, below 40 MB. Postgres: index build needs `maintenance_work_mem` (default 64 MB is slow but works; the job may `SET LOCAL maintenance_work_mem = '256MB'`). Query RAM: the index should stay in the OS cache, 8 GB server; a cold query takes tens of ms.
- Time: download about 1 min, load and index build roughly 3 to 8 minutes.

## 6. Env vars

- Reuse `UBYHOST_RUIAN_ENABLED` (default 1): `0` makes suggest return `[]` and the job return at once.
- No new var needed. `UBYHOST_RUIAN_URL` (Python geocoder override) becomes unused once Python's route is off; it is kept for Python until 1700d is on Go. A base-URL override for tests is a Go constant/test parameter, not an env var. If the owner wants a mirror switch, propose `UBYHOST_RUIAN_CSV_URL`; not proposed now.

## 7. Proposed ENVIRONMENT.md changes (not applied)

- `UBYHOST_RUIAN_ENABLED`: replace the text with "Set `0` to turn off the address suggestions and the monthly import; suggestions come from the local `ruian_address` table, nothing typed leaves the server."
- Remove the `UBYHOST_RUIAN_URL` row when Python's route is retired.
- Add a line to the job-kinds rows: `ruian_import` joins `UBYHOST_JOB_QUEUE_KINDS` and `UBYHOST_GO_JOB_KINDS`. Outbound host list: `vdp.cuzk.gov.cz` (monthly GET, public data).
- Attribution line "Address data: ČÚZK, RÚIAN" in the privacy/licence page if the licence requires it (Q4).

## 8. Rollout and rollback

1. Merge 1700c (draft until ready). Deploy applies `00021` (`UBYHOST_SCHEMA_APPLY=go`). Job kind registered but not in the kinds env: dormant.
2. Owner adds `ruian_import` to both kind lists, restarts; first run fills the table (watch `./scripts/logs.sh`, job row). Check `SELECT rows, data_date FROM ruian_import`.
3. Merge 1700d. Route dormant until `/apartments/ruian-suggest` is in `UBYHOST_GO_PATHS` (exact path, before `/apartments/*` per the 1700 note), then reload caddy. Compare with the Python answers for 5 addresses.
4. Rollback of the route: trim the path. Rollback of the data: remove `ruian_import` from the kind lists; the table is harmless and can stay or be dropped by a later migration. Python suggest keeps working against ČÚZK until its route is removed (a later cleanup brief, not part of 1700c/d).

## 9. Open questions for the owner

- Q1 okres: the CSV has none. Options: (a) leave `addr_okres` blank and let the user type it (the field stays editable; the police report needs it, so this is a UX cost); (b) bundle a static obec-code to okres list (about 6,258 rows, generated once from ČÚZK/ČSÚ open data, refreshed by hand yearly, kept in the Go repo); (c) a second monthly import of per-obec UKSH files (heavy). Recommend (b); needs the data source confirmed before 1700c step "okres".
- Q2 Is `ubyhost_app` allowed `CREATE EXTENSION pg_trgm`? If not, the owner runs `CREATE EXTENSION pg_trgm;` once as the `ubyhost` superuser (give a one-line command) before the deploy.
- Q3 Is about 1.2 GB (peak 2.5 GB) extra in Postgres, backups and WAL acceptable? Option to halve: import `č.p.` only and skip `č.ev.`.
- Q4 Confirm the licence text and whether an attribution line is required on a public page.
- Q5 `č.ev.` rows: does Python put the evidence number into `addr_house_no`? Not checked; plan keeps them with `is_evid` and returns the number as `addr_house_no`.
