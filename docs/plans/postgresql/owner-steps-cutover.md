# PostgreSQL cutover: owner steps

PostgreSQL runs on the existing Lightsail server as a container with no password and no network interface; only the app and worker reach it through a shared socket (owner decision 2026-10-31). Nothing to buy, create or configure. The app stays on SQLite until step 3.

Wait for the message that briefs 0463 and 0464 are on main (the production deploy after that merge starts the PostgreSQL container by itself), then, on the server, from `/opt/ubyhost/deploy/lightsail`:

1. `./scripts/status.sh` shows a `postgres` container up next to the app.
2. `./scripts/pg-cutover.sh rehearse`. It backs up, copies production data into a throwaway database, checks every table's row count and hash, dumps and restores that copy and checks it again, prints the table, and drops the throwaway databases. Production is untouched. It must end with `REHEARSAL OK`; otherwise paste the output into the chat.
3. Pick a quiet moment (expected downtime: under two minutes at today's data size). `./scripts/pg-cutover.sh cutover`. It stops the app, backs up, transfers, verifies, switches the config and starts the app on PostgreSQL. If any check fails it puts the app back on SQLite by itself and says why. It must end with `CUTOVER OK`.
4. Open the dashboard, one stay, one Doručenka download. The SQLite file and the old `.env` copy stay on the server; `./scripts/pg-cutover.sh rollback` goes back to them.
5. Tomorrow after 03:00 UTC: `./scripts/status.sh` and check that the newest folder in the backup list has both `ubyhost-backup.tar.age` and `ubyhost-pg.dump.age`.
