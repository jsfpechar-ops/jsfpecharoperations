# Data protection impact assessment (Article 35 GDPR)

**Status:** input for counsel, following ÚOOU's DPIA methodology. Whether a DPIA
is *mandatory* here is a legal question for counsel (see the review's § 7); this
document is the engineering analysis that feeds it.

## 1. Describe the processing

UbyHost lets accommodation providers collect guest registration data and file it
with the Police of the Czech Republic through UbyPort. The processing, data
categories and recipients are in `ROPA.md`. In scope here:

- **Identity documents.** Travel document and visa numbers are required by
  Act 326/1999 for reportable guests. They are stored Fernet-encrypted
  (`guest.doc_number_enc`, `visa_number_enc`).
- **Optional ID images.** A per-property toggle (`passport_photo_policy`,
  default **off**) lets a host request a passport/ID image or PDF. It is stored
  as a file and deleted on verification, on archive/delete, or by the 30-day
  sweep.
- **Possible children.** Under-15 guests can be entered on a parent's passport
  (`child_in_passport`), and a drawn signature path exists for them. The
  signature's legal effect is unresolved (review § 7.3).
- **Multi-tenant platform.** One deployment holds many controllers' data,
  separated by `owner_user_id` joins in `access.py`.
- **Automated police filing.** The `submit` job files without manual approval
  in `scheduled` mode.
- **Admin impersonation.** A platform admin can read and write inside a host
  workspace (`auth.issue_session(workspace_user_id=…)`), audited since BE-6.
- **Transfers.** Cloudflare's global network and AWS `eu-central-1`; the
  EU–US DPF appeal C-703/25 P is pending (review § 1).

## 2. Necessity and proportionality

| Question | Current position |
|---|---|
| Is each field necessary? | The statutory fields are required by § 101/§ 102; the optional ID image and the signature are **not** required by § 103 (review § 1) and default off |
| Could less data do? | Names and birth dates are still cleartext for search/sort (`docs/archive/FOLLOWUPS.md` W2.2); document numbers are encrypted |
| Transparency | Guest notice and privacy page; acknowledgement version persisted (BE-5) |
| Data-subject rights | Access via registration PDF/house-book CSV; erasure limited by § 101; the DSR register is BE-8 |

## 3. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Unauthorised read of identity documents | Fernet at rest; host-only photo route; access joins; `passport_photo_viewed` and export reads audited (BE-6) |
| Backups leaking documents and key | OPS-1: encrypted with `age`, key held offline, fail-closed in production |
| Indefinite retention | BE-2/3/4 retention job (dry-run by default until G-D4) |
| Logs leaking tokens or IPs | OPS-3: route-template-only access line, rotation, uvicorn access log off |
| Children's data | Under-15 path documented but its legal basis and signature handling need counsel |
| Admin impersonation | Audited with the real actor and impersonator (BE-6); admin role only |
| Cross-border transfer | EU production region; Cloudflare/DPF analysis by counsel |

## 4. Residual risk and prior consultation

- Residual risk after the above: identity-document processing, the optional ID
  images and the children path.
- **Counsel decides** whether the residual risk is high enough to require prior
  consultation with ÚOOU under Art 36, and whether a DPO is needed.
- This document must be reviewed when the passport policy, the retention anchor
  or the transfer position changes.
