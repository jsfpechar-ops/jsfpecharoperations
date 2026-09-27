# Vendor evidence file

Evidence that each subprocessor in the register (`/subprocessors`) is backed by
a contractual transfer mechanism (a DPA) and where it runs. **LD-9** fills in
the per-vendor table; this file exists now so the OPS-2 purge below has a
recorded home.

## Legacy plaintext backup purge (OPS-2)

Before OPS-1, every backup snapshot carried the database **and** the Fernet key
in the clear — on the server volume, on Google Drive, on S3, and on any operator
machine. Encrypting new snapshots does not remove those. Run the one-time
checklist in [docs/OPERATIONS.md](../OPERATIONS.md) § "Backup and restore" and
record the result here.

| Location | Purged on | By |
| --- | --- | --- |
| Server volume (`/data/backups`) | not yet | — |
| Google Drive (`UbyHost-backups`) | not yet | — |
| S3 bucket (non-`*.age` objects) | not yet | — |
| Operator machines / external disks | not yet | — |
