# Glossary

- **UbyPort**: the Czech foreign police web service where accommodation providers report foreign guests (`ZapisUbytovane` SOAP call). Test and production endpoints exist; `UBYHOST_UBYPORT_ENV` picks one (`mock`, `test`, `prod`).
- **Doručenka**: the PDF receipt UbyPort returns for a filing. It must be stored and downloadable.
- **Filing / submission**: sending guests to UbyPort. Its state lives in `submit_state` ([OPERATIONS](../OPERATIONS.md#the-submit_state-state-machine)).
- **Outcome unknown**: UbyPort didn't answer clearly. It is never auto-retried live (duplicate risk).
- **Codes 112 / 150**: UbyPort error codes. 150 = duplicate, treated as success. See [OPERATIONS](../OPERATIONS.md#ubyport-error-codes-and-what-112-and-150-really-do).
- **House book (domovní/ubytovací kniha)**: the legally required guest register (§ 102 zákon 326/1999 Sb.).
- **Host**: the accommodation provider using UbyHost. **Workspace**: a host's account data.
- **Property / apartment**: a place the host rents.
- **Stay / reservation**: one booking, usually imported from an iCal feed (Airbnb, Booking).
- **Guest link + PIN**: how a guest opens the check-in form. **Claim**: a guest picks their stay and gives email and party size.
- **Poplatek z pobytu (stay fee)**: the municipal tourist fee (§ 3g zákon 565/1990 Sb.). Host-only remittance tool; optional.
- **Plátce / neplátce**: VAT payer or not (affects invoices).
- **IČO / DIČ**: Czech company id / VAT id. The operator's own values live only in the server `.env`.
- **Operator**: the company running UbyHost (`UBYHOST_OPERATOR_*`). **Controller**: the GDPR data controller, i.e. the host's legal entity.
- **Admin preview**: a platform admin opening a host workspace (audited).
- **Council**: a multi-reviewer blind review of a plan. At most one per plan.
- **Orchestrator / executor / brief / report**: see [workflow](workflow.md).
- **K-xx**: a row in [known-issues](known-issues.md). **HR**: HIGH RISK.
