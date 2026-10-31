# Integration: ARES and the VAT register (ADIS)

Status: **no callers found** (verification pass, 2026-10-31). `App/app/ares.py` and `App/app/vat_register.py` exist. Nothing in `App/app` imports them. The only matches are UI strings in `App/app/host_vi_i18n.py`. Either the code is dead, or it is loaded by a path not found in this pass.

- ARES: `https://ares.gov.cz/...ekonomicke-subjekty/{ico}` with a 4 s timeout and 1 h cache (subagent report; `App/app/ares.py:11`, `:120-126`).
- VAT register: `https://adisrws.mfcr.cz` SOAP, 6 s timeout (`App/app/vat_register.py:18-21`).
- Official references: ARES catalogue https://www.mfcr.cz/assets/attachments/2023-08-01_ARES-Technicka-dokumentace-Katalog-verejnych-sluzeb.pdf ; ADIS: `⚠️ UNKNOWN` (see [REFERENCES](REFERENCES.md)).
- Decision needed: keep or delete. See [gap report](../gap-report.md) Q33.
