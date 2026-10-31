# PostgreSQL cutover: owner steps

Steps 1–6 can be done now; 7–9 wait for brief 0463 (the `pg-cutover.sh` script) to be on main. The app keeps running on SQLite until step 8.

## A. Create the managed database (about 15 minutes, mostly waiting)

1. Open the Lightsail console, the same region as the UbyHost instance. Left menu: **Databases**, then **Create database**.
2. Pick the instance's region and the **same Availability Zone** as the UbyHost instance (shown on the instance card).
3. Engine: **PostgreSQL**. Version: the newest **16.x or 17.x** offered (not 18).
4. Open **Specify login credentials**: username `ubyhost`, choose a 32-character password of letters and digits only (no symbols, they break the URL). Save it in Bitwarden now.
5. Open **Specify the master database name**: `ubyhost`.
6. Plan: **Standard**, bundle **Micro** (1 GB RAM, 40 GB SSD, about 15 USD per month). Name: `ubyhost-db`. Create. Leave **Public mode** off; the instance reaches it privately.
7. When the status is **Available**, open the database, tab **Connect**, copy the **Endpoint** (ends in `.rds.amazonaws.com`); port is 5432.

## B. Put the URL on the server

8. SSH to the instance and edit `/opt/ubyhost/deploy/lightsail/.env`. Add one line (one line, no spaces), filling in the password and endpoint:

```
UBYHOST_PG_URL=postgresql://ubyhost:PASSWORD@ENDPOINT:5432/ubyhost?sslmode=verify-full&sslrootcert=/certs/rds-global-bundle.pem
```

Nothing changes yet: the app reads `UBYHOST_DATABASE_URL`, not this line.

## C. Rehearse, then cut over (after 0463 is on main)

9. `cd /opt/ubyhost && git pull origin main && cd deploy/lightsail && ./scripts/deploy.sh` (brings the script and the certificate mount; app stays on SQLite).
10. `./scripts/pg-cutover.sh rehearse`. It backs up, copies production data into a throwaway database on the new server, checks every table's row count and hash, prints the table, and drops the throwaway database. Nothing in production changes. If it ends with `REHEARSAL OK`, go on; otherwise paste the output into the chat.
11. Pick a quiet moment (expected downtime: under two minutes at today's data size). `./scripts/pg-cutover.sh cutover`. It stops the app, backs up, transfers, verifies, switches the config and starts the app on PostgreSQL. If any check fails it puts the app back on SQLite by itself and says why.
12. Afterwards: open the dashboard, one stay, one Doručenka download. The SQLite file and the old `.env` copy stay on the server for rollback: `./scripts/pg-cutover.sh rollback`.
