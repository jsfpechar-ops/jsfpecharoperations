# WP06: Scheduler in its own process, 2 web workers (HIGH RISK)

## Summary
The web container now runs two uvicorn workers with `UBYHOST_ROLE=web`, and these never start the scheduler. A new `worker` container (same image, `UBYHOST_ROLE=worker`, `python -m app.worker`) runs startup checks, takes the existing `DATA_DIR/scheduler.lock`, starts APScheduler and blocks until SIGTERM. It refuses to start (exit 3) while another process holds the lock.

I found a real start-up race and fixed it. `db.init_db()` was not safe when processes start at the same time: a new test with 6 processes failed on the old code with `sqlite3.OperationalError: duplicate column name: totp_last_step`. The same race also hits the one-off settings insert, the first-admin insert and secret-key creation. All of these now run under a cross-process, reentrant `flock` (`db.startup_lock()`, `DATA_DIR/startup.lock`).

Stacked on WP05.

## Files changed
- `App/app/worker.py`: new worker entry point. It touches `DATA_DIR/worker.alive` every 30 s for the compose health check and exits non-zero if the scheduler thread dies.
- `App/app/db.py`: `startup_lock()` (an flock that is reentrant within one process). `init_db()` now runs under it.
- `App/app/main.py`: lifespan takes `startup_lock` around the secret key, `init_db`, bootstrap admin and PIN rotation. It starts the scheduler only for `UBYHOST_ROLE=all` and refuses `worker`.
- `App/app/config.py`: `UBYHOST_ROLE` (`web` default, `worker`, `all`).
- `App/app/scheduler.py`: `start()` returns bool; new `running()`.
- `App/run.sh`, `App/render_start.sh`: default `UBYHOST_ROLE=all` (single process).
- `Dockerfile`: `--workers 2`, comment updated.
- `deploy/lightsail/docker-compose.yml`: `worker` service, `UBYHOST_ROLE: web` on `ubyhost`, memory limits.
- `deploy/lightsail/scripts/deploy.sh`: waits for the worker to report alive, fails if the web log shows `scheduler started`, and rollback restarts both containers.
- `deploy/lightsail/scripts/restore.sh`: also stops and starts the worker.
- `deploy/lightsail/scripts/status.sh`: prints the role and the age of the worker alive file.
- `deploy/lightsail/scripts/preflight.sh`: refuses hosts with less than about 1.7 GB RAM unless `UBYHOST_ALLOW_SMALL_HOST=1`.
- `deploy/lightsail/.env.example`, `docs/ENVIRONMENT.md`, `docs/LIGHTSAIL.md`: docs.
- `App/tests/test_worker.py`, `App/tests/test_startup_concurrency.py`: new tests.

## Tests added
- web role: lifespan does not start the scheduler (with `ENABLE_SCHEDULER=True`); `all` role does; `worker` role refuses to serve HTTP.
- worker `run()` starts the scheduler (jobs `ical`, `submit` and `mail` present), writes the alive file, runs migrations, and stops cleanly.
- worker refuses a second scheduler while the lock is held: tested in-process (exit code 3) and as a real `python -m app.worker` subprocess.
- `python -m app.worker` exits 0 on SIGTERM after `scheduler started`.
- 6 processes run `init_db()` at once on a fresh file, 3 rounds: all succeed and the schema is complete. This failed before the fix.
- 4 web-like processes race the bootstrap admin: exactly one admin.
- `startup_lock` is reentrant; `init_db` blocks while another process holds the lock.

## Test commands and results
- `pytest tests/test_worker.py tests/test_startup_concurrency.py`: 12 passed.
- `pytest tests/test_scheduler.py tests/test_retention_job.py tests/test_guest_pin.py tests/test_env_guard.py tests/test_worker.py tests/test_startup_concurrency.py`: 63 passed.
- Whole suite in chunks by file prefix (WP06 tree): a-c 284 passed 2 skipped; d-f 316; g-h 361 passed 5 skipped 1 failed; i-m 267; n-r 422; s 366; t-z 160. The single failure is `test_host_geometry.py::test_the_month_filter_shares_its_page_edges`: Chromium cannot launch in this sandbox. It fails the same way on the unmodified base. Browser e2e tests are skipped here for the same reason.
- `ruff check app tests tools --select E9,F63,F7,F82,F401,F841`: all checks passed. `shellcheck -S error` (CI's command): clean.
- I did not run the full suite in one process (per-call time limit here). Cursor must run it as CI does.

## Deviations from the spec and why
- Third role value `all`. With only `web` and `worker`, the Render staging service and `run.sh` (single process, no worker) would silently lose all background jobs. `all` keeps today's behaviour there. The Docker image default is still `web`.
- Migrations stay in every process but are serialised by an flock, instead of moving to one place. This also covers `python -c "db.init_db()"` in `deploy.sh` and the scripts, and it closes the secret-key and bootstrap-admin races.
- Worker health uses a file heartbeat instead of a tiny HTTP endpoint (no server in the worker).

## Module-level state audit (2 web processes + worker)
- `turnstile.py`: no module state. The fail-open counter is in the database (`rate_limit`). Safe.
- `rate_limit.py`, TOTP replay (`totp_last_step`), sessions (signed cookie + `session_version` in DB), CSRF (signed cookie): no in-memory state. Safe.
- `config._SECRET_KEY`: per-process cache of one key. Creation had a race: one process creates with `O_EXCL` while another reads the empty file and raises. Now under `startup_lock`.
- `db._fernet_cache`, `auth._dummy_password_hash`, `client_ip._TRUSTED_NETWORKS`: derived per process. Safe. At most a duplicate warning log.
- `validation._COUNTRIES_CACHE`, `deadlines._HOLIDAY_CACHE`, `pdf_mark._png` and `routes/invoices._invoice_columns` (lru_cache): read-only or schema-derived after migrations. Safe.
- `scheduler._scheduler` and `_lock_handle`: per process. The flock guarantees one scheduler per volume.
- Request threads and the scheduler thread could already run at the same time before (thread pool + BackgroundScheduler). DB-guarded paths (`claim_sendable`, mail outbox states) are unchanged. Immediate sending on guest save stays in the web process.

## Exact compose and Dockerfile diff
```diff
commit 072bc574e2e945dd556c9e39cb82d047c5411bc6
Author: local <local@example.invalid>
Date:   Sun Oct 4 00:03:40 2026 +0200

    WP06: Scheduler in its own process, 2 web workers

diff --git a/Dockerfile b/Dockerfile
--- a/Dockerfile
+++ b/Dockerfile
@@ -35,5 +35,9 @@ ENTRYPOINT ["docker-entrypoint.sh"]
 # --no-access-log: uvicorn's own access log writes the raw request line, which
 # includes guest permalink tokens and query strings. The app logs one PII-free
 # line per request instead (see app/main.py, OPS-3).
-# One worker: the scheduler runs in-process and SQLite has one writer.
-CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--no-access-log"]
+# Two web workers (WP06). UBYHOST_ROLE defaults to web, so neither starts the
+# scheduler: the background jobs run in a separate container from this image
+# (`python -m app.worker`, UBYHOST_ROLE=worker; see deploy/lightsail). SQLite
+# still has one writer at a time; writers queue on its lock (timeout=30) and
+# the start-up migrations are serialised by an flock (app/db.py startup_lock).
+CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2", "--no-access-log"]
diff --git a/deploy/lightsail/docker-compose.yml b/deploy/lightsail/docker-compose.yml
--- a/deploy/lightsail/docker-compose.yml
+++ b/deploy/lightsail/docker-compose.yml
@@ -18,6 +18,8 @@ services:
     environment:
       UBYHOST_DATA_DIR: /data
       PORT: "8080"
+      # WP06: two uvicorn workers that only serve HTTP; jobs run in `worker`.
+      UBYHOST_ROLE: web
     volumes:
       - ubyhost-data:/data
     expose:
@@ -34,7 +36,9 @@ services:
       timeout: 5s
       retries: 3
       start_period: 25s
-    mem_limit: 768m
+    # 2 GB bundle (WP06): web 896m + worker 448m + litestream 128m + Caddy
+    # leaves about 450 MB for the OS and Docker.
+    mem_limit: 896m
     # OPS-3: bound container logs so they cannot grow without limit. Rotated
     # lines are gone for good; capture anything needed during an incident.
     logging:
@@ -45,6 +49,51 @@ services:
     networks:
       - web
 
+  # WP06: the background scheduler (iCal sync, UbyPort sweep, deadline watch,
+  # mail outbox, photo sweep, retention) in its own process. Same image, env
+  # and volume as the web app; it holds DATA_DIR/scheduler.lock, so a second
+  # scheduler anywhere on this volume refuses to start.
+  worker:
+    image: ubyhost:local
+    pull_policy: never
+    restart: unless-stopped
+    # A UbyPort batch already on the wire must record its answer.
+    stop_grace_period: 90s
+    env_file: .env
+    environment:
+      UBYHOST_DATA_DIR: /data
+      UBYHOST_ROLE: worker
+    command: ["python", "-m", "app.worker"]
+    volumes:
+      - ubyhost-data:/data
+    # No HTTP server: the worker touches /data/worker.alive every 30 s while
+    # its scheduler runs.
+    healthcheck:
+      test:
+        [
+          "CMD",
+          "python",
+          "-c",
+          "import os, sys, time; sys.exit(0 if time.time() - os.path.getmtime('/data/worker.alive') < 120 else 1)",
+        ]
+      interval: 30s
+      timeout: 5s
+      retries: 3
+      start_period: 30s
+    mem_limit: 448m
+    logging:
+      driver: json-file
+      options:
+        max-size: "10m"
+        max-file: "5"
+    # Built and migrated by the web service first; also creates the volume
+    # with the app's ownership on a fresh server.
+    depends_on:
+      ubyhost:
+        condition: service_healthy
+    networks:
+      - web
+
   # WP05: continuous replication of the SQLite database to S3. Runs as the
   # app's uid on the same volume, so it can read the database and write its
   # .ubyhost.db-litestream metadata next to it. Only the variables it needs are
```

## Deploy order
1. Owner moves the server to the 2 GB bundle first (below). Preflight refuses a smaller host.
2. Merge WP05 first (this patch is stacked on it), then run Actions → Deploy production once. `deploy.sh` builds the image, starts `ubyhost` (2 workers), then `worker` and `litestream` after the web health check. It then waits for `/data/worker.alive` and fails if the web log contains `scheduler started`.
3. Check: `./scripts/logs.sh worker` shows `scheduler started` exactly once. `docker compose logs ubyhost | grep -c "scheduler started"` prints 0. `./scripts/status.sh` shows a worker alive age under 60 s.
4. Rollback to a pre-WP06 image: `docker tag ubyhost:previous ubyhost:local && docker compose up -d --no-build ubyhost && docker compose stop worker`. The old image starts the scheduler inside the web container, as before. The old image has no `app.worker`, so a running worker container would crash-loop, which is why it is stopped. `deploy.sh`'s automatic rollback restarts `ubyhost worker`. That is right for every later deploy, but on this first deploy run `docker compose stop worker` by hand after a rollback.

## What Cursor must verify or adapt when applying on the real main
- Hand review of the HIGH RISK hunks: `App/app/main.py` lifespan (diff below), `App/app/db.py` `startup_lock`/`init_db`, `App/app/scheduler.py` `start()`.
- WP14 (thread-local connections) rewrites `db.py`. Keep `init_db` under `startup_lock` when merging both. The flock must not be held while a pooled connection waits on `BEGIN IMMEDIATE` for long.
- Run the full suite in one process, plus `test_guest_browser_e2e.py` with `UBYHOST_REQUIRE_BROWSER=1`.
- Render staging's `startCommand` uses `render_start.sh`, which now exports `UBYHOST_ROLE=all`. Confirm Render does not set `UBYHOST_ROLE` itself.
- Job-failure alerts and the submit heartbeat run unchanged inside the worker (same `scheduler` functions).

```diff
commit 072bc574e2e945dd556c9e39cb82d047c5411bc6
Author: local <local@example.invalid>
Date:   Sun Oct 4 00:03:40 2026 +0200

    WP06: Scheduler in its own process, 2 web workers

diff --git a/App/app/main.py b/App/app/main.py
--- a/App/app/main.py
+++ b/App/app/main.py
@@ -80,15 +80,25 @@ async def lifespan(_app: FastAPI):
     # Explicit startup work, because importing config no longer creates the data
     # directory or writes the signing key to disk.
     config.ensure_data_dir()
-    # Read the key here, where a bad one stops the app from booting. Left lazy,
-    # it raised on the first page that signed a cookie: /healthz answered 200
-    # while /login answered 500, so the deploy's health check passed and the
-    # broken release went live.
-    config.secret_key()
-    db.init_db()
+    if config.ROLE not in ("web", "all"):
+        raise RuntimeError(
+            f"UBYHOST_ROLE={config.ROLE!r} cannot serve HTTP; use web or all "
+            "(the background worker starts with: python -m app.worker)"
+        )
     from PIL import Image
     Image.MAX_IMAGE_PIXELS = 12_000_000  # every image we render is a signature or a QR code
-    bootstrap_password = auth.ensure_bootstrap_admin()
+    # WP06: two web workers and the scheduler worker boot at the same moment.
+    # Key creation, migrations, the first administrator and the PIN rotation
+    # each assume they run alone, so they run one process at a time.
+    with db.startup_lock():
+        # Read the key here, where a bad one stops the app from booting. Left
+        # lazy, it raised on the first page that signed a cookie: /healthz
+        # answered 200 while /login answered 500, so the deploy's health check
+        # passed and the broken release went live.
+        config.secret_key()
+        db.init_db()
+        bootstrap_password = auth.ensure_bootstrap_admin()
+        rotate_weak_permalinks()
     admin_username = auth.normalise_username(config.ADMIN_USERNAME) or "admin"
     if bootstrap_password:
         log.warning(
@@ -101,7 +111,6 @@ async def lifespan(_app: FastAPI):
             "Created the first administrator (%s). Log in using UBYHOST_ADMIN_PASSWORD.",
             admin_username,
         )
-    rotate_weak_permalinks()
     log.info("database ready at %s", config.DB_PATH)
     log.info(
         "deployment=%s ubyport=%s endpoint=%s",
@@ -119,7 +128,10 @@ async def lifespan(_app: FastAPI):
         log.warning(
             "LIVE production reporting is active — submissions go to the real police register."
         )
-    scheduler.start()
+    if config.ROLE == "all":
+        scheduler.start()
+    elif config.ENABLE_SCHEDULER:
+        log.info("role=web: background jobs run in the worker process (python -m app.worker)")
     try:
         yield
     finally:
```

## Manual steps for the owner
1. Move to the 2 GB bundle (Frankfurt). Lightsail → instance → Snapshots → Create snapshot. From the snapshot, Create new instance: same region and zone, bundle 2 GB RAM. Wait until it is running. Networking → detach the static IP from the old instance and attach it to the new one. SSH in, run `cd /opt/ubyhost/deploy/lightsail && ./scripts/status.sh`, open the site and sign in. Update `LIGHTSAIL_KNOWN_HOSTS` in the GitHub `production` environment if the host key changed (`ssh-keyscan <static-ip>`). Keep the old instance stopped for a few days, then delete it and its snapshot.
2. Deploy as above and check the logs show exactly one scheduler.
3. Optional: set `UBYHOST_HEARTBEAT_URL` (WP07) so a dead worker is noticed within 10 minutes.
