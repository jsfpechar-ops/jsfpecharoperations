# Vendor evidence file

Evidence that each subprocessor in the register (`/subprocessors`) is backed by
a contractual transfer mechanism (a DPA), where it runs, and a development-tool
policy. **LD-9.** Record the date and who checked each row; this is an input for
counsel.

## Subprocessors

| Provider | Role | DPA mechanism | Region / account | Checked |
| --- | --- | --- | --- | --- |
| Amazon Web Services | Lightsail hosting, SES mail, optional S3 backups | AWS GDPR DPA, incorporated into the Service Terms | `eu-central-1`; record the Lightsail region and account id here | TODO |
| Cloudflare | DNS, proxy, TLS, Turnstile, WAF, challenges | Customer DPA incorporated into the Self-Serve Subscription Agreement, with SCCs | Global network (a transfer; see the register) | TODO |
| Render | Staging/demo hosting | [render.com/dpa](https://render.com/dpa), DPF-certified | Only used with synthetic data; never real Guest Data | TODO |
| Google Drive | Optional off-site backup | **Workspace/Cloud only** — the Cloud Data Processing Addendum. A consumer account has no processor DPA | Retire unless it is a Workspace account (OPS-2) | TODO |
| Support mailbox (`support@ubyhost.com`) | Support channel | Provider not yet identified | Identify it, sign its DPA, and add it to `/subprocessors` | TODO |

The **Czech Police (UbyPort)** is a statutory recipient, not a subprocessor, and
is listed as such.

## Development tooling

- GitHub and Cursor hold **code only**. No production data, database copies,
  logs or secrets may be placed in a repository, an issue, a prompt, or an AI
  assistant.
- The Cloudflare observability MCP in `.cursor/mcp.json` must not be pointed at
  production logs unless Cloudflare is added as a subprocessor for that
  processing.

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
