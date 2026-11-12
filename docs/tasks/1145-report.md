# 1145 report

Status: done (orchestrator investigation, no executor run).

- Payload fields: `guest_payload` App/app/reporting.py:180-200 and `FILED_FIELDS`; Go go/internal/ubyport/request.go:209-214 fed by collect.go:423-425.
- passport_photos.py:299 writes only `passport_photo_at` (not reported). routes/stay_fees.py:1164 writes `fee_host_*` and does set `updated_at`.
- No other `guest`/`reservation` writer of a reported column skips `updated_at` (dates/status writers in icalsync.py and routes/admin.py all bump it).
- Code changed: none. Test added: none (no behaviour to pin). K-F19 closed.
