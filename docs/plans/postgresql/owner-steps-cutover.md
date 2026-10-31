# PostgreSQL cutover: owner steps

PostgreSQL runs on the existing Lightsail server as a container (owner decision 2026-10-31). Nothing to buy or create in the AWS console. The app stays on SQLite until step 4.

Wait for the message that briefs 0463 and 0464 are on main, then, on the server:

1. Edit `/opt/ubyhost/deploy/lightsail/.env` and add one line with a 32-character password of letters and digits (it only guards the container's closed network port; the app uses a local socket). Save it in Bitwarden.

```
UBYHOST_PG_PASSWORD=...
```

2. `cd /opt/ubyhost && git pull origin main && cd deploy/lightsail && ./scripts/deploy.sh`. This starts the PostgreSQL container next to the app; the app still runs on SQLite.
3. `./scripts/pg-cutover.sh rehearse`. It backs up, copies production data into a throwaway database, checks every table's row count and hash, dumps and restores that copy and checks it again, prints the table, and drops the throwaway databases. Production is untouched. It must end with `REHEARSAL OK`; otherwise paste the output into the chat.
4. Pick a quiet moment (expected downtime: under two minutes at today's data size). `./scripts/pg-cutover.sh cutover`. It stops the app, backs up, transfers, verifies, switches the config and starts the app on PostgreSQL. If any check fails it puts the app back on SQLite by itself and says why. It must end with `CUTOVER OK`.
5. Open the dashboard, one stay, one Doručenka download. The SQLite file and the old `.env` copy stay on the server; `./scripts/pg-cutover.sh rollback` goes back to them.
6. Tomorrow after 03:00 UTC: `./scripts/status.sh` and check that the newest folder in the backup list has both `ubyhost-backup.tar.age` and `ubyhost-pg.dump.age`.
