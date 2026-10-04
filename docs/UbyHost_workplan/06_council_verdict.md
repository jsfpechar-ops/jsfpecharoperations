# Council verdict: UbyHost launch plan

Method: the llm-council skill. Five advisors (Contrarian, First Principles, Expansionist, Outsider, Executor) answered independently, five anonymous peer reviewers ranked them, and the chairman (the orchestrator) synthesised. The chairman checked advisor claims against the code; corrections are marked "Checked in code".

## Where the council agrees

- The product sells one promise: a host is never fined for a missed police filing. Everything else is secondary.
- Nothing in the original plan made a missed filing loud. All five advisors and all five reviewers flagged this.
- Brand-name Google Ads find nobody at launch, because nobody searches "UbyHost" yet. The first hosts come from Facebook groups and personal onboarding.
- Pricing and payment are missing. Charge from the first host.
- The AI-only legal positions carry risk. Every advisor recommended one paid hour with a Czech lawyer.
- Scale-tuning work (second worker, zstd) does not matter for 10 hosts.

## Where the council clashes

- **Ads and sign-up tracking.** Contrarian, First Principles and Executor said cut the Google and Meta conversion code. The owner wants Meta and Google ads. Resolution: keep the code, ship it switched off, and turn it on only when ads run. It costs nothing while off.
- **Expansion.** The Expansionist wanted property-manager accounts, per-municipality stay-fee filing, partners and Slovakia. Every reviewer called this the biggest blind spot: more scope before the core is proven. Resolution: not now. Price per unit from day one, so property managers fit later without a rebuild. Checked in code: one account can already hold many properties.
- **Policy and Umami before launch.** Two advisors said cut Umami. The Executor said write the privacy policy correctly once, before the first host accepts it. Resolution: keep WP09 before go-live. With no hosts yet, nobody has to re-accept.

## Blind spots the council caught (peer review)

- **UbyPort credentials.** Each host's UbyPort access is a high-value secret held by UbyHost. Checked in code: it is stored Fernet-encrypted, login refusals pause sending, and WP16 separates the encryption key. WP24 adds a terms clause authorising UbyHost to use the credentials only for filing.
- **Breach response.** No runbook existed. Now drafted in `compliance/03_breach_response_runbook.md`. Checked in code: an incident register exists at `/admin/incidents`.
- **DPIA and records of processing.** Needed for identity documents. Drafted in `compliance/01` and `compliance/02`.
- **eTurista.** The state's planned central accommodation register. It is currently planned for 2027, and until then the UbyPort duty stays (businessinfo.cz, muj-pravnik.cz). Keep the UbyPort client isolated so it can be replaced.
- **EU guests are reportable.** One advisor proposed an "EU guest must not be filed" test; that would be wrong. Czech law requires reporting all foreigners, EU citizens included. Checked in code: WP23 tests assert EU guests are reportable.
- **Proof of filing.** Checked in code: UbyPort answers synchronously; "sent" means UbyPort accepted the record, and the Doručenka receipt is stored and downloadable. There is no later police confirmation to reconcile against, so the right control is the at-risk watchdog, not a reconciliation job.
- **Guest form languages.** The guest form exists only in English and Czech. Foreign guests who cannot finish the form cause unfiled stays.

## The recommendation

Launch with a narrow, loud core:

1. Before go-live, merge series 0001 to 0012. This includes the new WP23 filing watchdog (host e-mail when a stay is at risk, an operator digest, and an off-VM heartbeat that turns red when any reportable guest is unfiled within 24 hours of the deadline), the "filed by hand" mark, and WP24 terms texts.
2. WP06 (separate scheduler process and 2 GB) moved after go-live. Production runs one web worker until then.
3. Run one end-to-end filing test against the real UbyPort test environment on staging before the first real host.
4. Price per unit, invoice by hand, from the first host.
5. Acquire the first 10 to 30 hosts personally in Facebook groups (ask each group admin about promotion rules first). Run paid ads on problem keywords, not the brand name, and turn on sign-up tracking only then.
6. Book one hour with a Czech lawyer to read the Terms, DPA and privacy policy 1.6 before the effective date. This was recommended by all five advisors. The owner chose to proceed on the researched positions; the texts are written so that this review is a read-through, not a rewrite.

## The one thing to do first

Set up the filing heartbeat (`UBYHOST_HEARTBEAT_FILING_URL`) so healthchecks.io e-mails you, and run one test filing through staging against the UbyPort test environment.
