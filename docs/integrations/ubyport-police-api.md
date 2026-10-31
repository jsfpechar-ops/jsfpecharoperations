# Integration: UbyPort (Czech Foreign Police) — SOAP web service

**Purpose:** filing of guest registrations (`ZapisUbytovane`) and reference data
lookups. The critical path for legal compliance. Read first:
[docs/UBYPORT_CORE.md](../UBYPORT_CORE.md) and the `submit_state` table in
[OPERATIONS.md](../OPERATIONS.md#the-submit_state-state-machine).

| Item | Value | Source |
|---|---|---|
| Base URL (test) | `https://ubyport.pcr.cz/ws_uby_test/ws_uby.svc` | `App/app/config.py:135` |
| Base URL (prod) | `https://ubyport.pcr.cz/ws_uby/ws_uby.svc` | `App/app/config.py:136` |
| Base URL (mock) | `UBYHOST_MOCK_URL`, default `http://127.0.0.1:8081/ws_uby/ws_uby.svc` | `App/app/config.py:137` |
| Environment selector | `UBYHOST_UBYPORT_ENV` = `mock` (default) \| `test` \| `prod` | `App/app/config.py:129` |
| Protocol | SOAP 1.1 hand-built XML; namespace `http://UBY.pcr.cz/WS_UBY`; SOAPAction prefix `http://UBY.pcr.cz/WS_UBY/IWS_UBY/` | `App/app/ubyport/soap.py` |
| Methods used | `TestDostupnosti`, `MaximalniDelkaSeznamu`, `DejMiCiselnik` (Staty, UcelyPobytu, Chyby), `ZapisUbytovane` | `App/app/ubyport/client.py:174-246` |
| WS-Addressing header | opt-in, `UBYHOST_SOAP_WSA_HEADER`, default off | `App/app/ubyport/client.py:23-30` |
| Auth | NTLM via `requests_ntlm.HttpNtlmAuth`; username forced to `DOMAIN\user` | `App/app/ubyport/client.py:112-122` |
| NTLM domain | `UBYHOST_UBYPORT_DOMAIN`, default `EXRESORTMV` | `App/app/config.py:141` |
| Credentials source | per-apartment WS username and password, stored **Fernet-encrypted** (`uby_ws_password_enc`) | `App/app/reporting.py:1095`, `App/app/db.py:154` |
| Batch size | `UBYHOST_MAX_BATCH`, default 32 | `App/app/config.py:144` |
| Timeout | `UBYHOST_UBYPORT_TIMEOUT`, default 60 s | `App/app/config.py:146`, `reporting.py:1093-1103` |
| TLS | verify on; redirects disallowed | `App/app/ubyport/client.py:131-138` |
| Sandbox | **Yes**: the `test` environment (`ws_uby_test`). Mock server: `App/mock_ubyport/server.py` (FastAPI, no NTLM check, state in `mock_state.json`) | `config.py:135`, `server.py:261-262` |

## Official references (fetched 2026-10-31; re-check, content can change)

- Overview, published by Policie ČR: https://policie.gov.cz/reditelstvi-sluzby-cizinecke-policie/co-to-je-ubyport — describes UbyPort as the web application for electronic reporting of accommodated foreigners, with the app at https://ubyport.pcr.cz/ubyport, over HTTPS.
- Submission channels: https://policie.gov.cz/reditelstvi-sluzby-cizinecke-policie/jake-jsou-moznosti-zasilani-dat-aplikaci-ubyport — three modules: UbyPortForm (manual web form), UbyPortUpLoad (UNL file), UbyPortWs (web service, "requires the programmer of your system"). UbyHost uses UbyPortWs.
- **Fit question:** the same page recommends the manual form for small accommodation (a few guests a week, no electronic register) and the web service for large facilities (tens to hundreds of guests a week, with an evidence programme). UbyHost targets short-term rental hosts. The owner should confirm that the web-service use is accepted for this profile. See [gap report](../gap-report.md) Q41.
- Technical contract: the code cites two appendices of the UbyPort operating rules: appendix 3 (UNL format, "Popis položek ubytovacího zařízení, cizince a formát UNL souboru") and appendix 5 (web-service description, section 10.5 on checks at first save). See `App/app/validation.py:1-10`. Neither appendix is in the repo or on the public page. See Q42.

## Rate limits
No rate limit is documented in the repo or implemented client-side beyond the
sequential sweep and the batch size. `⚠️ UNKNOWN — needs human input`: the
police service's throttling policy (ask UbyPort / check written
correspondence referenced in `docs/UBYPORT_CORE.md` § "What the police confirmed in writing").

## Retry and failure model (client)
- **No transport-level retry.** One `requests.post` per call, no `Session`, no `urllib3.Retry` (`client.py:131`).
- Exception types (`App/app/ubyport/client.py:33-74`):
  - `UbyportTransportError`: not sent, SOAP fault, 4xx, 3xx.
  - `UbyportOutcomeUnknownError`: timeout after the request was sent, SSL read/EOF, 5xx, unreadable XML, record-count mismatch. **Never auto-resent by the client** (`client.py:45-52`).
  - `UbyportAuthError`: HTTP 401.
  - Only `ConnectTimeout` or `NewConnectionError` count as "definitely not sent".
- App-side retry: the sweep resends an outcome-unknown batch at most once (`App/app/reporting.py:97`, `SUBMISSION_MAX_AUTO_ATTEMPTS = 1`; `_retry_outcome_unknown_batches` at `reporting.py:1878`).
- Login refusals: the sweep skips apartments with an open `ubyport_auth_failed` alert because repeated login attempts risk lockout (`App/app/scheduler.py`; subagent-verified).

## Idempotency
**None at the protocol level.** The app protects against duplicates with the
`submission_claim` lease (`App/app/reporting.py:1330-1377`) and the outcome-unknown
rule above. A duplicate filing is reported by UbyPort as **code 150**
(`App/app/ubyport/errors.py:56`).

## Error codes observed in code
From `App/app/ubyport/errors.py` (severity map at `:56`, accepted if severity
≤ 2 at `:59`; unknown severity treated as refusal at `:55`):

| Code | Severity in code | Meaning as coded |
|---|---|---|
| 1, 112 | 0 (accepted) | accepted variants |
| 150 | 4 (refusal) | duplicate — do not re-file |
| 5–13, 101–111 | per table in `mock_ubyport/server.py` ~60–80 | mock table; real severities `⚠️ UNKNOWN` beyond the map in `errors.py` |

`docs/OPERATIONS.md § UbyPort error codes, and what 112 and 150 really do` is
the authoritative explanation.

## Response handling
- `SubmissionResult` dataclass (`client.py:77-86`); `soap.parse_zapis_response` returns the receipt PDF (`DokumentPotvrzeni`), error PDF, pseudo-stamp, and record errors.
- Receipts are stored as base64 TEXT in `submission.receipt_pdf` / `error_pdf` (`App/app/db.py:287-288`), **not encrypted** at this layer. Submission `request_xml` is encrypted (`db.py:1738`); `response_xml` is plaintext (`db.py:291`).

## Submission state
`submit_state` values are string constants (not an Enum): `pending`, `sent`,
`error`, `blocked`, `not_required` (`App/app/reporting.py:47-52`). A transport
failure leaves the guest `pending` and sets submission state `transport_error`
(`reporting.py` ~1483–1540). `⚠️ UNKNOWN`: whether every transition in
`docs/OPERATIONS.md` matches code (only constants and the transport path were checked).

## Where in code
- Client: `App/app/ubyport/client.py`; SOAP: `App/app/ubyport/soap.py`; errors: `App/app/ubyport/errors.py`.
- Orchestration: `App/app/reporting.py` (`sweep` at `:1993`, `client_for` at `:1093-1103`).
- Watchdog (read-only; never files): `App/app/filing_watchdog.py`.
- Environment guard: `App/app/env_guard.py:95-132` (prod requires `UBYHOST_DEPLOYMENT=production`; prod refused on Render; prod + mock warned).

## Known risks (for the migration)
- The real police service has **not** been characterised in tests; only the mock is exercised. NTLM acceptance, TLS chain, and WS-Addressing necessity are `⚠️ UNKNOWN` until tested against `test`.
- Characterization tests for the SOAP field order and error mapping: `⚠️ UNKNOWN` — check `App/tests/` for `soap` / `ubyport` test files (not enumerated in this pass).

## Official references

- UbyPort official docs: `⚠️ UNKNOWN` (none public; see [REFERENCES](REFERENCES.md)).
