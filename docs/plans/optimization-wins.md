# Plan: optimization wins

Status: owner approved the scope on 2026-11-15 ("do it all"). Briefs 1800-1823 are reserved and not written yet. The owner decided D1-D3 on 2026-11-16 (section 9).
Goal: the whole product runs well for 2,000 properties on one 1 vCPU / 2 GB RAM / 40 GB disk server, with no upgrade path.
Depends on [go-full-move](go-full-move.md) and [SQLite retirement](sqlite-retirement.md) for lane A; every other lane can start now.

## 1. Measured baseline

Grafana, 2026-10-16 to 2026-11-15, and three server commands on 2026-11-15. 7 active properties.

| What | Value |
|---|---|
| Host RAM used (avg / p95 / max) | 1761 / 1896 / 2115 MB, no swap |
| Containers, avg MB | ubyhost 467 (max 1263), postgres 116, alloy 107, worker 99, cadvisor 80, litestream 30, caddy 14, ubyhost-go 11, node-exporter 10, walg 6 |
| RAM outside containers | about 800 MB avg, about 1.4 GB at the peak (cause not confirmed; image builds on the server suspected) |
| CPU | all containers about 0.07 core avg; load1 max 4.69 |
| Requests | 0.35/s avg, 1.73/s p95, 10.5/s peak minute; p95 latency 167 ms |
| Request mix (30 days) | 180k 404s, 65k `/`, 28k `/sw.js`, 15k manifest, about 124k app pages |
| Recreates in 30 days | ubyhost 190, worker 164, ubyhost-go 76 |
| Disk | 11.9 GB used of 165 GB |
| `ubyhost-data` volume | 1.34 GB, all of it `backups/` (about 75 copies of 17 MB) |
| `ubyhost-pgdata` volume | 122 MB; the ten largest tables hold about 17 MB |
| Largest tables | guest 6.5 MB for 115 rows (57 KB a row), submission 3.4 MB, job 2.3 MB for 11,476 rows, stay_fee_filing 1.8 MB, platform_invoice 1.3 MB |

Scaled to 2,000 properties (upper bound, the 7 include owner testing): about 19 requests/s avg, about 90/s in busy periods; guest table 11-45 GB a year at today's row size.

## 2. Targets

| Resource | Target on the 2 GB server |
|---|---|
| RAM, steady | 700 MB or less; 1 GB swap as a buffer |
| RAM limits | postgres 600 MB, ubyhost-go 256 MB, alloy 150 MB, caddy 96 MB, walg 256 MB |
| CPU | 0.5 core avg at 2,000 properties; background jobs yield to web requests |
| Disk | system and images 10 GB or less; database growth 4 GB a year or less; local backups 3 copies or fewer |
| Requests reaching Go | static files and scanner paths never do |

## 3. Lane A: memory

| Brief | Work | Done when |
|---|---|---|
| (existing) | Finish the Go move and SQLite retirement: removes `ubyhost`, `worker`, `litestream` | The three containers are gone from the compose file |
| 1800 | Build images in CI, push to a registry, server only pulls. Registry: D2 | `deploy.sh` runs no `docker build`; deploy peak RAM under 1 GB |
| 1801 | Monitoring in one container: Alloy's built-in unix and cadvisor exporters replace `node-exporter` and `cadvisor`; trim scrape list and interval | Two containers removed; the dashboards used in section 1 still fill |
| 1802 | Memory limits from section 2, `GOMEMLIMIT` on `ubyhost-go`, 1 GB swap file step in [LIGHTSAIL](../LIGHTSAIL.md) | Compose defaults match section 2 |
| 1803 | Owner check: `free -m; ps -eo rss,comm --sort=-rss \| head -15` idle and during a deploy, to explain the 800 MB outside containers | Cause written into [known-issues](../context/known-issues.md) |

## 4. Lane B: Caddy takes the cheap requests

| Brief | Work | Done when |
|---|---|---|
| 1804 | Caddy serves `/sw.js`, `/manifest.webmanifest` and `/static/*` from disk with cache headers and compression (service worker: short max-age plus ETag; fingerprinted assets: one year, immutable) | These paths show no requests in `ubyhost_requests_total` |
| 1805 | Caddy answers scanner paths itself (`*.php`, `/wp-*`, `/.env`, `/.git/*`, `/cgi-bin/*` and the top unmatched paths from the metric) with 404 | Unmatched 404s at the app drop by 90% |
| 1806 | Per-IP rate limit for anonymous routes. Caddy has no built-in limiter: do it in the Go middleware (D3) | A 50 requests/s burst from one IP gets 429 after the limit |
| 1807 | Landing page and other public pages: rendered once, kept in memory, `ETag` and `304` | `/` costs no database query |
| 1808 | Caddy request metrics into Alloy, so traffic is measured before the app | Grafana shows requests by status at Caddy |

## 5. Lane C: Go and query efficiency

| Brief | Work | Done when |
|---|---|---|
| 1809 | No list query selects the large columns (`signature_png*`, `*_xml*`, `pdf_*`, `payload*`); a test fails on `SELECT *` against those tables | Test in CI |
| 1810 | Query count per page: a test helper counts queries; reservations, apartments, cleaning and the guest lane stay at 5 or fewer | Test in CI |
| 1811 | Index review with `pg_stat_statements` on staging: add missing indexes on property and date, drop indexes with zero scans | One migration; the report lists each change |
| 1812 | Pool: `MaxConns` 10 in Go, `max_connections` 20 in Postgres | Compose and Go config match |
| 1813 | Job concurrency: submit 2, calendar sync 4, photo work 1, all others 1 each; web requests are never queued behind jobs | Config in one place, documented in [ENVIRONMENT](../ENVIRONMENT.md) |
| 1814 | Calendar sync: jitter over the interval, `If-None-Match` and `If-Modified-Since`, skip parsing on `304` or an unchanged body hash, slower cycle for properties with no stay in the next 60 days | Fetches a second stay flat when a burst is simulated |

## 6. Lane D: Postgres

| Brief | Work | Done when |
|---|---|---|
| 1815 | Settings: `shared_buffers` 256 MB, `work_mem` 4 MB, `maintenance_work_mem` 64 MB, `effective_cache_size` 1 GB, `random_page_cost` 1.1, `jit` off, `wal_compression` zstd, `max_wal_size` 512 MB, `default_toast_compression` lz4 | Compose `command:` updated; restore drill still passes |
| 1816 | `job` table: Python already purges finished rows after 7 days (`jobqueue.purge`), and rows grow with job kinds, not properties (found while writing the brief; the 11,476 rows are one week of the every-minute push job). Go has no purge yet: add one in Go (done 7 days, dead 30 days, batches), plus per-table autovacuum settings. Claim already uses `FOR UPDATE SKIP LOCKED` | Go purges on its own; row count stays flat over a week |
| 1817 | `audit` and `alert`: a retention period for each, written in `App/app/retention.py` and [RETENTION](../privacy/RETENTION.md) | Retention job deletes old rows |

## 7. Lane E: disk and data size

Rule 1 applies: nothing here may change what is filed or the evidence of what was filed.

| Brief | Work | Done when |
|---|---|---|
| 1818 | Signature: store a black-and-white image 480 px wide (owner chose 480 over 300 on 2026-11-16 from a sample) as compressed bytes, then encrypt. Format: D1. Old rows are converted by a one-off job | New guest rows are 5 KB or less; the PDF may tint the ink dark blue when drawing |
| 1819 | Submission XML: compress, then encrypt, in a binary column; old rows converted. The decrypted text is byte-identical | Round-trip test on every stored row; table shrinks about 10 times |
| 1820 | PDFs (`stay_fee_filing`, `platform_invoice`): compress, then encrypt; subset fonts when generating. Never regenerate an issued invoice | Round-trip test; average PDF row 30 KB or less |
| 1821 | Local backups: keep the last 3 in `/data/backups`; deploy takes a backup only when a migration is pending; the nightly dump streams to remote storage with no local file once the database passes 1 GB | Volume holds 3 folders |
| 1822 | Docker and logs: prune images and build cache on every deploy, log driver limit 10 MB x 3 files per container, journald 100 MB | `docker system df` reclaimable under 1 GB after a deploy |
| 1823 | Guide photos (`imgproc`, brief 1641): longest side 1600 px, JPEG quality 80, metadata stripped, one size stored, cap per guide, same file stored once; alerts at 70% disk and on WAL spool over 500 MB; ext4 reserved blocks 1% and `noatime` in the new-server steps | Upload test: a 6 MB photo is stored under 400 KB |

## 8. Order

1. Now, independent: 1803, 1805, 1804, 1816, 1821, 1822 (small, no decision needed).
2. Next: 1801, 1802, 1812, 1815, 1808, 1809, 1810.
3. After the routes are on Go: 1806, 1807, 1811, 1813, 1814, 1817.
4. Then: 1800, 1818, 1819, 1820, 1823.
5. Last: measure for 7 days with the section 1 Grafana prompt, compare with section 2, then plan the server move.

## 9. Owner decisions (2026-11-16)

| ID | Decision |
|---|---|
| D1 | The guest signature is stored as a small black-and-white image, on the condition that it stays clearly readable. Brief 1818 includes a side-by-side check of old and new on real-size signatures |
| D2 | CI-built images live in GitHub Container Registry as a private package |
| D3 | Rate limiting is done in the Go middleware; no Caddy plugin |

## 9a. Lane F: guest form isolation

The guest registration form becomes its own program that app changes, app crashes and database outages cannot stop: [plan](guest-form-isolation.md), briefs 1830-1852.

## 10. Not in this plan

- Moving the server. That is a separate plan after step 5.
- Object storage for photos. Only if section 7 is not enough; it is a new monthly cost.
- PgBouncer, read replicas, table partitioning: not needed at this size.
