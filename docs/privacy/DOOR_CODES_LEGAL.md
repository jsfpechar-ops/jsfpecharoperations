# Door codes (TTLock): legal assessment

Prepared by the orchestrator acting as counsel at the owner's request, 2026-10-08; revised 2026-10-12 after TTLock's answer (§4). The owner approved the revised model (§1) on 2026-10-12. This is a reasoned position, not an opinion from a licensed Czech lawyer; the owner accepts it as the basis for door codes for every host.

Feature: [plan](../plans/ttlock-door-codes.md). Facts: [TTLOCK](../TTLOCK.md).

## 1. Roles: TTLock is the host's own provider

- The host is the controller of guest data, UbyHost its processor (existing DPA).
- **TTLock is the host's lock provider, not a UbyHost subprocessor.** The host bought the lock, holds the TTLock account that owns it, and uses TTLock's cloud under TTLock's own terms, with or without UbyHost. The lock's codes and its unlock records live in that account.
- UbyHost works inside the host's TTLock system as an **authorized admin the host appoints** (plan §8.2): the host shares the lock to a TTLock user UbyHost made for them, and can take that access away at any time. Every code UbyHost makes appears in the host's own TTLock app.
- Art 28(2) and (4) GDPR make a provider a subprocessor when the processor *engages* it to carry out processing on the controller's behalf. UbyHost engages nobody here: the controller chose TTLock, and UbyHost only enters data into the controller's chosen system on the controller's documented instruction, which Art 28(3)(a) expressly allows, including for transfers. EDPB Guidelines 07/2020 describe the same split: the controller decides which processors it uses; a processor disclosing data to a recipient the controller designated does not turn that recipient into its own subprocessor. Software that writes into a customer's own third-party account (calendar, accounting, CRM integrations) is treated this way in common practice.
- UbyHost's own contract with TTLock (developer app, API user) covers only the access channel: a random user name, its password and tokens. No guest data is processed for UbyHost's own purposes.

## 2. What goes to TTLock

Lock ID, the code's validity window, the reference `UH-<number>`, and for the rare custom code (taken period, plan §6) the 7 digits UbyHost chose. A random code's digits are made by TTLock. No name, e-mail, phone, nationality or document. For UbyHost these are personal data (they link to a guest's stay). For TTLock alone guests are not identifiable; the CJEU's recipient-relative view of identifiability (EDPS v SRB, C-413/23 P, 2025) supports that and is a supporting argument only.

## 3. The host's instruction

- The host gives the instruction when they accept the door-code terms and tap Set up (Guide, "Door codes with TTLock", terms item 4). The terms say plainly that TTLock is the host's own provider, that UbyHost sends the data above to it on the host's behalf, and that the host's relationship with TTLock, including any transfer outside the EEA, is the host's.
- **Duty to warn (Art 28(3), last subparagraph).** TTLock has told UbyHost it does not consider itself to meet GDPR standards. UbyHost must pass that on: the terms say so, in one sentence, before the host accepts. A host who reads it and still switches door codes on makes an informed controller's choice.
- TTLock is therefore **not** in the `/subprocessors` register or DPA §11. The register lists it under "Recipients that are not subprocessors", as the host's lock provider, with the data above. DPA §11 needs no change (it never named TTLock).

## 4. Transfer outside the EEA

- TTLock support, 2026-10-12: EU users' data is stored on EU servers in Germany. The company, Hangzhou Sciener Intelligent Control Technology Co., Ltd., is in China, which has no adequacy decision; access from China counts as a transfer (EDPB Guidelines 05/2021). TTLock also said it does not think it meets GDPR standards, so no SCCs are available.
- The transfer, if any, happens inside the host's own relationship with TTLock, which exists independently of UbyHost: the host's own codes, eKeys and unlock records already sit there. UbyHost's part is a transmission to servers in Germany on the controller's instruction, of minimal data that TTLock cannot link to a guest and that loses its value when the code expires.
- Residual risk, accepted by the owner: a supervisory authority could still treat UbyHost's developer app as UbyHost engaging TTLock, and then require a Chapter V basis UbyHost cannot get. The minimal data, the EU storage, the warning to the host and the host's own pre-existing use of TTLock keep the exposure low. If an authority or court takes that view, door codes switch off for other hosts (one setting) until a lock provider with EU safeguards is supported.
- Art 49 derogations are not relied on.

## 5. Information to guests (Art 13)

Every property with door codes on shows an extra paragraph in its guest privacy notice (the host's notice as controller): purpose (access to the accommodation), that TTLock is the host's lock provider, what it receives, that it stores the data in Germany and is based in China, which has no EU adequacy decision (Art 13(1)(f)), that the code goes to the registration e-mail and the host, encrypted storage and deletion a day after expiry, basis Art 6(1)(b) (accommodation contract), and that the lock records use of the code in the host's TTLock app. Wording: [0068](../tasks/0068-ttlock-host-provider-copy.md).

## 6. Legal basis and retention

- Creating and sending the code: Art 6(1)(b), the guest's accommodation contract (the host must let the guest in).
- Retention: PIN wiped one day after the code expires; the door-code row goes with the reservation; the TTLock connection until the host removes it ([RETENTION](RETENTION.md)).

## 7. Host terms (B2B)

- Hosts are businesses, so feature terms accepted at opt-in are valid (versioned, acceptance audited). The 2026-10-12 version carries §1 and §3; a host connected under an older version is asked again only if that host is not the owner (today there is none).
- Liability is not limited separately: the door-code terms point to Terms §17, which already keeps liability for intent and gross negligence (§ 2898 of the Civil Code) and for harm to natural rights.
- The terms state the host's own duties: a second way in, keeping the guest link PIN private, and that a never-used code of a cancelled stay may keep working.

## 8. Security (Art 32)

The PIN is encrypted at rest and never stored in plain text in the outbox or the logs. UbyHost never handles the host's TTLock password. Its TTLock user should be shared with Remote unlock off. An endpoint allowlist blocks remote unlock and the super-passcode endpoints. The shared guest link and PIN is disclosed to the host as a residual risk, and the parked booking-code check is the next control.

## 9. Open actions

| # | Action | Owner | Before |
|---|---|---|---|
| 1 | Ship the copy in [0068](../tasks/0068-ttlock-host-provider-copy.md): terms, register, guest notice | executor | done 2026-10-12 (#372) |
| 2 | Confirm TTLock's developer terms allow use by a multi-host platform | owner | done 2026-10-12: allowed (TTLock support) |
