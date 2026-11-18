# Autopilot: legal positions

Written 2026-11-17 by the orchestrator at the owner's request, in the format of
[legal positions](../UbyHost_workplan/04_legal_positions.md). Research was done from
public sources on that day. `[UNVERIFIED]` marks a point where the statute text itself
was not opened; the Terms and DPA wording these positions produce goes through the same
lawyer pass as the open legal texts (0005, K-L). Parent: [plan](autopilot-agentic.md).

## Summary

| # | Question | Position | Product change |
|---|---|---|---|
| A1 | May the app file without the host confirming each stay? | Yes. The duty and the liability stay with the host (owner decision 2026-11-17). | Standing instruction per property, recorded acceptance, plain warning, off switch, receipts and failure escalation. |
| A2 | What record is needed when a team member or outside key acts for the host? | A grant record (who, to whom, scope, when, revoked when) plus an actor on every action. The grant is the host's documented instruction to UbyHost. | Grants table, audit actor types, DPA clause, masked document numbers for outside keys by default. |
| A3 | On what basis and under whose name does the app remind guests? | In the host's name, UbyHost as processor. Service message, not marketing. | Fixed neutral templates, cap on reminders, stop on completion, no promotion. |
| A4 | eTurista | Not in force. Draft law, no public interface. UbyPort stays the only filing target for now. | Filing target as an interface; registration-number field; quarterly watch. No build yet. |

## A1. Filing without a per-stay confirmation

### Position
The app may file automatically once the host has given a standing instruction for the
property. The host stays the accommodation provider (ubytovatel) and carries the duty
and any fine. The host must be told this in plain words and must accept it knowingly.

### Reasoning
- §§ 99 to 102 zákon 326/1999 Sb. put the reporting duty on the accommodation provider: report a foreign guest to the police within 3 working days ([Policie ČR: povinnosti ubytovatele](https://policie.gov.cz/clanek/povinnosti-ubytovatele.aspx), [portal.gov.cz S11847](https://portal.gov.cz/sluzby-vs/registrace-pobytu-ubytovatelem-po-prijezdu-do-ceske-republiky-S11847)). Nothing found requires a human to approve each record. `[UNVERIFIED: statute text of § 102 not opened.]`
- The police expect software to file. Their developer FAQ speaks of "informační systém na straně ubytovatele" using the UbyPort web service with the facility's own login, and sets duties for that system: store data without distortion, confirm receipt or report errors, escalate outages and data errors, lose nothing in an outage ([FAQ pro vývojáře, archived](https://archiv.policie.gov.cz/clanek/faq-pro-vyvojare.aspx)).
- The same page says the duty is the provider's and fines can reach tens of thousands of CZK per unreported person. Software does not move that liability.
- Each facility has its own UbyPort login. The app files with the host's credentials, as the host's tool.
- UbyHost is the host's processor for guest data (position 5). Filing on a standing instruction is processing on documented instructions, Art. 28(3)(a) GDPR.

### What the product must do
- Per property, a standing instruction the host switches on. Text shown at that moment, in the host's language, in substance: "UbyHost will send guest reports to the police for this property without asking you each time. You remain the accommodation provider. You are responsible for what is sent and for reports that are missing or late. UbyHost tells you when a report fails."
- Record the acceptance with document version, time and account (`App/app/acceptance.py` pattern). A changed text makes it pending again; while pending the property drops to "prepare, host files".
- One switch turns it off. Off takes effect for the next filing.
- Every automatic filing writes an audit row with actor `autopilot` and the checks that passed.
- The four police duties above are acceptance criteria of the autopilot: receipt stored, error surfaced, outage escalated, nothing lost.
- The guest's identity: the host remains responsible for checking the travel document. Autopilot files what the guest declared and the app validated. Say so in the same text. `[UNVERIFIED: the exact duty to inspect the document, § 100 to § 103.]`
- Terms: a clause that automatic filing is done on the host's instruction, that the host is the provider under zákon 326/1999 Sb., and a liability limit for wrong data supplied by guest or host.
- Default: new properties start at "prepare, host files". Setup offers "file when clean" as the recommended choice with the text above. Never switched on silently.

## A2. Team members and outside keys

### Position
A host may let other people and software act for them. UbyHost needs a record of each
grant and of each action taken under it. No separate power of attorney is needed for
actions inside the app.

### Reasoning
- The host is the controller for guest data. A team member acts under the controller's authority and only on its instructions (Art. 29 and Art. 32(4) GDPR). The grant in the app is that instruction.
- An API key or a connected AI assistant is a tool the host chose. Its vendor is the host's own recipient, not a UbyHost subprocessor. This is the reasoning of position 7 (push services chosen by the host's browser).
- Art. 5(1)(c) and Art. 25 GDPR (minimisation, by default): an outside tool should not receive passport numbers unless the host asks for that.
- Accountability, Art. 5(2): UbyHost must be able to show who did what under which grant.

### What the product must do
- Grant record: grantor account, grantee (person, key or connected app), scope (properties, read or write, document data yes or no), created, last used, revoked. Kept for the life of the account plus the audit retention period. Add the line in `App/app/retention.py`.
- Every action stores the actor type (host, team member, key, connected app, autopilot, guest) and the grant id.
- Document numbers, visa numbers and photos are masked for keys and connected apps unless the host ticks a separate, plainly worded box when creating the grant. Photos are never returned.
- At grant time, one sentence for outside tools: "Guest data you let this tool read is sent to its provider. You choose the provider and are responsible for that choice."
- UbyPort credentials are never readable through any grant.
- Team member invites go to a named person with their own login. No shared passwords.
- DPA: a clause that the host's instructions include actions by users and keys the host authorised, and that the host answers for whom they authorise. ROPA: a new entry for grants and API access.
- Host can list and revoke grants on one page. Revocation is immediate.

## A3. Reminders to guests

### Position
The app may remind a guest to complete registration. The message is sent in the host's
name. It is a service message, not a commercial communication, so no marketing consent
is needed, provided it carries no promotion.

### Reasoning
- The host must collect the data for the police report and the house book (zákon 326/1999 Sb.) and for the stay-fee book (zákon 565/1990 Sb.). Basis for the host: legal obligation, Art. 6(1)(c) GDPR, and performance of the accommodation contract, Art. 6(1)(b), for the contact itself.
- UbyHost sends as processor (position 5).
- Zákon 480/2004 Sb. covers commercial communications. A message whose only content is "complete your legally required registration for your stay" promotes nothing. `[UNVERIFIED: § 2 definition text not opened.]` Position 2 took the cautious route for host onboarding mail; here caution means no promotional content at all.

### What the product must do
- Sender name: the host or property name, "via UbyHost". Reply-to the host where the host gave one.
- Use only a contact the guest gave or the host entered for that stay. Platform relay addresses are fine.
- Fixed templates in the guest's language. No UbyHost promotion, no links other than the registration link and the guide.
- At most 3 reminders per stay, none at night local time, none after the form is complete or the stay cancelled.
- The first message says why: Czech law requires the host to register guests.
- A link "I cannot complete this" that stops reminders and raises an exception for the host. No general unsubscribe for the first notice; the cap protects the guest.
- No new personal data is stored: reminder count and times per stay only. Add them to the retention line of the stay.
- SMS or WhatsApp would rest on the same basis but need a new vendor and a subprocessor entry. Out of scope until the owner decides the dependency.

## A4. eTurista

### Position
Do not build for eTurista now. Keep the design able to add it as a second filing target
without reworking the first.

### Facts found (2026-11-17)
- It is a planned central register under the Ministry for Regional Development, to be created by an amendment to zákon 159/1999 Sb. It is not in force. Guest evidence, UbyPort reporting and the stay fee continue under current law ([ubytovacka.cz](https://www.ubytovacka.cz/eturista/), [e-turista.cz](https://www.e-turista.cz/); both are private sites, the second carries vendor advertising).
- The bill had not passed the Chamber of Deputies. Dates moved several times: July 2025, then 2026, the ministry spoke of 2027 in August 2026, and the tracker above reports a newer draft with effect from 1 January 2028. None is final ([Finance.cz](https://www.finance.cz/clanky/553173-aplikace-eturista-mela-od-cervence-hlidat-ubytovatele-zatim-vsak-zustava-na-papire/)).
- Intended content: registration of every accommodation unit before first use, a registration number required on online listings, guest records (name, birth date, address, citizenship, document, stay dates, fee or exemption reason), data passed on to the foreign police, the fee administrator and the statistics office ([Chekin overview](https://chekin.com/cs/blog/ubyport-a-e-turista-jak-splnit-povinnosti-evidence-hostu/), vendor source).
- No public technical documentation, interface description or test environment exists yet.
- One source says the reporting deadline would shorten to 24 hours ([muj-pravnik.cz](https://muj-pravnik.cz/co-je-eturista/)). Not confirmed elsewhere.

### What the product must do
- The action layer names a filing target. Today: `ubyport`. The stay-fee remittance is a second target of the same shape. A third can be added.
- Deadlines are computed per target from a rule table, so a 24-hour rule is a data change.
- Property gets a nullable registration-number field when the action layer is built. Not shown in the UI until the law passes.
- The guest record already holds the listed fields; domestic guests would need the same capture as foreign ones. Keep the guest form able to require them per target.
- Owner task every quarter: check the bill's status on psp.cz and mmr.gov.cz. When technical documentation is published, open a plan.
- Public copy may say "we follow eTurista and will support it". It must not say UbyHost is "eTurista ready" before an interface exists.
