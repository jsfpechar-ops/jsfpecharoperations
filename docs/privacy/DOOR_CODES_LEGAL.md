# Door codes (TTLock): legal assessment

Prepared by the orchestrator acting as counsel at the owner's request, 2026-10-08. This is a reasoned recommendation, not an opinion from a licensed Czech lawyer. It is sufficient for the pilot on the owner's own properties; have a data-protection lawyer confirm points 4 and 7 before other hosts use door codes.

Feature: [plan](../plans/ttlock-door-codes.md). Facts: [TTLOCK](../TTLOCK.md).

## 1. Roles

- The host is the controller of guest data, UbyHost its processor (existing DPA).
- For door codes, UbyHost uses its own TTLock developer app and a TTLock user it creates for each host. TTLock (Hangzhou Sciener Intelligent Control Technology Co., Ltd.) therefore processes on UbyHost's instruction: it is UbyHost's **subprocessor** (Art 28(4) GDPR).
- What the host's own TTLock account does (unlock records in the host's app, the host's own codes) is the host's own relationship with TTLock, outside UbyHost's DPA.

## 2. What goes to TTLock

Lock ID, the code's validity window, the code itself (TTLock generates it) and the reference `UH-<number>`. No name, e-mail, phone, nationality or document. For UbyHost these are personal data (they link to a guest's stay). For TTLock alone, guests are not identifiable; the CJEU's recipient-relative view of identifiability (EDPS v SRB, C-413/23 P, 2025) supports that, but this assessment does **not** rely on it and treats the data as personal data.

## 3. Authorisation of the subprocessor

DPA §11 names the authorised subprocessors and has an "only if used" group. Recommended:

1. **Now:** specific authorisation at opt-in. The door-code terms the host accepts on Set up name TTLock as a subprocessor for this feature (terms item 4). Hosts who never set up smart locks send no data to TTLock, so nothing changes for them and no general notice is needed.
2. **At the next DPA revision:** add TTLock to §11 "only if used", with the 30-day notice of DPA §20.
3. The public register lists TTLock as used only for properties with door codes on.

## 4. Transfer outside the EEA

- The endpoint is `euapi.ttlock.com`; its hosting location is not confirmed. Sciener is in China, which has no adequacy decision. Remote access from China counts as a transfer (EDPB Guidelines 05/2021).
- **Basis: the EU Standard Contractual Clauses (2021/914), Module 3 (processor to processor), signed with Sciener or its EU entity**, plus a short transfer impact assessment. The TIA can be brief because the data is minimal, carries no names or contacts, and loses its value when the code expires; the residual risk is state access under Chinese law.
- Art 49(1)(b) (necessary for the guest's accommodation contract) is not a basis for a systematic flow; use it only as a fallback argument during the pilot.
- **Action (owner):** ask TTLock developer support and TTLock Europe for their DPA with SCCs and the hosting location of `euapi.ttlock.com`. Go live for other hosts only once the SCCs are signed. The pilot on the owner's own properties may run meanwhile; the owner is both controller and operator there and accepts the residual risk.

## 5. Information to guests (Art 13)

Every property with door codes on shows an extra paragraph in its guest privacy notice: purpose (access to the accommodation), what TTLock receives, that the code goes to the registration e-mail and the host, encrypted storage and deletion a day after expiry, basis Art 6(1)(b) (accommodation contract), and that the lock records use of the code in the host's TTLock app. Wording: task 0016.

## 6. Legal basis and retention

- Creating and sending the code: Art 6(1)(b), the guest's accommodation contract (the host must let the guest in).
- Retention: PIN wiped one day after the code expires; the door-code row goes with the reservation; the TTLock connection until the host removes it ([RETENTION](RETENTION.md)).

## 7. Host terms (B2B)

- Hosts are businesses, so feature terms accepted at opt-in are valid (versioned, acceptance audited).
- Liability is not limited separately: the door-code terms point to Terms §17, which already keeps liability for intent and gross negligence (§ 2898 of the Civil Code) and for harm to natural rights.
- The terms state the host's own duties: a second way in, keeping the guest link PIN private, and that a never-used code of a cancelled stay may keep working.

## 8. Security (Art 32)

The PIN is encrypted at rest and never stored in plain text in the outbox or the logs. UbyHost never handles the host's TTLock password. Its TTLock user should be shared with Remote unlock off. An endpoint allowlist blocks remote unlock and the super-passcode endpoints. The shared guest link and PIN is disclosed to the host as a residual risk, and the parked booking-code check is the next control.

## 9. Open actions

| # | Action | Owner | Before |
|---|---|---|---|
| 1 | Request a DPA with SCCs and the hosting location from TTLock | owner | other hosts use door codes |
| 2 | Write the one-page TIA from section 4 | orchestrator, once TTLock answers | the same |
| 3 | Add TTLock to DPA §11 "only if used" | next DPA revision | 30 days' notice |
| 4 | Confirm TTLock's developer terms allow use by a multi-host platform | owner | other hosts use door codes |
