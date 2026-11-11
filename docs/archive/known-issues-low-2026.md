# Low-severity known issues archive

Moved from [known-issues](../context/known-issues.md) on 2026-11-11 (compaction). Same table columns.

| ID | Sev/status | Where | Issue | Src |
|---|---|---|---|---|
| K-F07 | Low open HR | routes/guest.py immediate mode | Guest save waits for UbyPort (60 s+) | P A75 |
| K-F08 | Low open | icalsync.py:304 | DTEND ≤ DTSTART stored; those guests never validate | P A31 |
| K-F09 | Low open | routes/admin.py:1927 | Manual send inspects only the first batch | P A36 |
| K-F10 | Low open | routes/admin.py calendar delete | Deleted calendar's future stays stay active and alert | P A34 |
| K-F17 | Low unverified | reporting.py claim TTL; :1683 recover_stale_submissions | Lease may expire in slow batches | P A16, A30 |
| K-F19 | Low open | codelists.py error_severities | Before a successful Refresh only 1/112/150 known | police A1-A2 |
| K-P06 | Low open | routes/stay_fees.py:576 | fee_host_reason_reference unencrypted | P A46 |
| K-S06 | Low open | main.py:167 | CSP script-src allows 'unsafe-inline' | P A42 |
| K-S07 | Low decision | auth.py:498,618 | BOOTSTRAP_ADMIN=0, no accounts: host UI may stay open | P A47 |
| K-S08 | Low unverified | rate_limit.py:79 | No per-account login lockout across addresses | P A44 |
| K-S09 | Low open | deploy-production.yml | GITHUB_TOKEN stays in server's git remote | P A58 |
| K-I02 | Low open | invoices.py:51-63 _parse_decimal | "1.000" parses as 1 | X |
