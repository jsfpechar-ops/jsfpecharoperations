# Personal data breach runbook for a solo operator

Internal document. Not published. Reasoned drafting, not attorney advice.
Replaces `docs/privacy/INCIDENT_RESPONSE.md` once approved (that file has the same structure but no templates).

Print this page or keep it offline. If the server is down, you still need it.

## 0. Two roles, two duties [Dvě role, dvě povinnosti]

| Data affected | UbyHost's role | Who tells the ÚOOÚ | Who tells the people |
|---|---|---|---|
| Guest data (house book, documents, ID photos, guest e-mails, stay-fee records, host invoices to guests) | Processor | Each host, within 72 hours of the host becoming aware (Art. 33(1)). UbyHost tells the host without undue delay (Art. 33(2)) | Each host, if high risk (Art. 34). UbyHost helps |
| Host accounts, logins, UbyHost's own invoices, sign-up and ad consent data, support e-mail | Controller | UbyHost, within 72 hours of becoming aware | UbyHost, if high risk |

A breach of the server usually hits both rows at once. Then do both.

Source: the ÚOOÚ states "Zpracovatel ohlašuje případ příslušnému správci, který činí ohlášení dozorovému úřadu" (uoou.gov.cz, Porušení zabezpečení osobních údajů, opened 4 Oct 2026).

## 1. Detect [Zjištění]

Where a breach shows up:
- App alerts in the admin area: `guest_pin_abuse`, `incident_review` (5 or more guest links rate-limited in 24 hours), `submission_transport`, `submission_rejected`, `mail_failed`, `job_failed`.
- Litestream heartbeat stops (`LITESTREAM_HEARTBEAT_URL`), job heartbeats stop.
- Cloudflare security events (WAF, managed challenges, leaked-credential detections).
- AWS e-mails: Lightsail, SES bounce or complaint spikes, IAM changes, billing jumps, S3 access warnings.
- GitHub secret-scanning alerts (the repository is public).
- A host or guest writes to support@ubyhost.com.
- Your own laptop or phone is lost or stolen, or a password manager alert.

The 72-hour clock starts when you are reasonably sure a breach happened, not at the first odd sign (EDPB Guidelines 9/2022, para 31 [UNVERIFIED paragraph number]). Use a short check (minutes to a few hours) to decide. Write down the time you became sure.

## 2. Open the incident at once [Založit incident]

1. Go to `/admin/incidents` and create an incident even if facts are thin. Fields: detected at, reported by, summary, data categories, affected workspaces, approximate number of people, risk level (`none`, `low`, `high`), notes.
2. If the app is down, write the same fields in a text file and copy them in later. The register is your Art. 33(5) record.
3. Every later step: set the timestamp buttons on the incident (`contained_at`, `controllers_notified_at`, `authority_notified_at`, `subjects_notified_at`, `closed_at`).

## 3. Contain [Omezit dopad]

Do only what fits the incident. Preserve evidence before you change things.

Preserve first (logs rotate at 5 x 10 MB):
- `cd /opt/ubyhost/deploy/lightsail && docker compose logs --since 72h > /root/incident-$(date +%F).log`
- Export relevant `audit` rows (filter by time and owner) and the Cloudflare event log. Save with the incident.

Then contain:

| Situation | Action |
|---|---|
| One host account taken over | `/admin/users`: disable the account (toggle). This also raises `session_version` and logs the user out. Reset the password, re-enrol 2FA, re-enable. |
| A guest link or PIN is out | Host (or you via support mode) rotates the property PIN and the permalink. Old PIN sessions stop at once. |
| Admin account or server compromised | Lightsail: take a snapshot for evidence, then close ports except what is needed, rotate the SSH key. Change the admin password and 2FA. Rotate `UBYHOST_SECRET_KEY` (logs everyone out). If the data keys may have leaked: add a new key first in `UBYHOST_DATA_KEYS`, restart, run `scripts/reencrypt.py --backup ...` then `--check`. Follow `docs/OPERATIONS.md` "If the secret key is lost or rotated". |
| UbyPort web-service passwords may be exposed | Tell each affected host to ask the police for a new web-service password (UbyPort helpline +420 731 670 444, ubyport@pcr.cz, 8:00 to 11:00 working days). Hosts then enter the new password in UbyHost and use "Test connection". |
| S3 bucket or IAM key leaked | Disable the IAM access key, turn on Block Public Access if it was off, check the bucket policy, review CloudTrail if enabled, create a new key for Litestream. |
| Mis-sent e-mail with guest data | Ask the recipient in writing to delete it and confirm. Keep the reply. |
| Secret committed to GitHub | Rotate it first. Then scrub history (`docs/SECURITY.md`, source-control hygiene). |
| Lost laptop with an SSH key or backup identity | Remove its key from the server, rotate the `age` identity, make a new backup. |

Mark `contained_at`.

## 4. Assess the risk to people [Posoudit riziko pro dotčené osoby]

Answer these and write the answers in the incident notes:
1. Which data? Encrypted fields (document and visa numbers, birth date, street and town, signatures, ID photos) are unreadable without `UBYHOST_DATA_KEYS`. Names, nationality, stay dates and e-mails are not encrypted.
2. Were the keys exposed too? If the server itself was compromised, assume yes.
3. How many people and which hosts? Use the database: count guests per `owner_user_id` in the affected time range.
4. Confidentiality, integrity or availability? Loss of availability for a few hours with a working backup is usually no risk. Exposure of document numbers is.
5. Children involved?
6. Could it lead to identity fraud, financial loss, discrimination or loss of control over data?

Decision table (position, adjust per case):

| Outcome | Risk level in the register | ÚOOÚ | People |
|---|---|---|---|
| Encrypted data only, keys safe; or short outage restored from backup without loss | `none` or `low` | Not required. Record only | No |
| Names, stay dates or e-mails of guests exposed to an outsider | `low` to `high` depending on scale | Required if not unlikely to cause risk. When in doubt, notify | If high |
| Document numbers, ID photos or keys exposed; or many hosts affected | `high` | Required | Required, unless Art. 34(3) applies |
| Host login data exposed (login link token hashes, e-mails) | `low` to `high` | UbyHost notifies if risk | UbyHost tells hosts; end all sessions (rotate `UBYHOST_SECRET_KEY`), invalidate all outstanding login links (delete `login_token` rows), remove passkeys if key material may be compromised, change login e-mail via support flow |

## 5. Notify affected hosts (processor duty) [Oznámit ubytovatelům]

Target: within 24 hours of becoming aware, even if facts are incomplete. Art. 33(2) says "without undue delay"; the hosts need time for their own 72 hours.

1. Open the incident page. Copy the draft from `incidents.controller_notification_draft`: it lists each affected workspace's legal-entity contact e-mail. Nothing is sent automatically.
2. Use the templates below (CS for Czech hosts, EN otherwise). Send each host its own e-mail, not one with all addresses in To. BCC is acceptable only if the content is identical and contains no per-host numbers.
3. Send from support@ubyhost.com. Keep the sent copies.
4. Mark `controllers_notified_at`.
5. Send updates as facts come in (Art. 33(4) allows notification in phases).

### Template CS: first notice to a host

```
Předmět: Důležité: porušení zabezpečení osobních údajů v UbyHost (čl. 33 odst. 2 GDPR)

Dobrý den,

jako zpracovatel údajů vašich hostů vám bez zbytečného odkladu oznamujeme porušení zabezpečení osobních údajů.

Co se stalo: [stručný popis, např. "neoprávněný přístup k serveru dne 4. 10. 2026 mezi 02:10 a 03:40"]
Kdy jsme to zjistili: [datum a čas]
Dotčené údaje: [např. jména, data pobytu, státní občanství; čísla dokladů jsou šifrovaná a klíč (byl / nebyl) dotčen]
Dotčení hosté ve vašem účtu: přibližně [počet], pobyty od [datum] do [datum]
Pravděpodobné důsledky: [např. riziko zneužití totožnosti / nízké riziko]
Co jsme udělali: [např. odpojili jsme server, změnili klíče, odhlásili všechny uživatele]
Co doporučujeme vám:
- posoudit, zda incident ohlásíte Úřadu pro ochranu osobních údajů. Jako správce na to máte 72 hodin od chvíle, kdy jste se o porušení dozvěděli, tedy od přijetí tohoto e-mailu. Formulář: https://uoou.gov.cz/profesional/poruseni-zabezpeceni-osobnich-udaju
- [je-li to relevantní] požádat Policii ČR o nové heslo k webové službě UbyPort (infolinka +420 731 670 444, ubyport@pcr.cz) a zadat ho v UbyHost
- [je-li to relevantní] změnit PIN a odkaz pro hosty u ubytování

Můžeme vám připravit seznam dotčených hostů a text oznámení hostům. Pokud chcete, abychom ohlášení Úřadu podali za vás, pošlete nám plnou moc.

Kontakt pro tento incident: [jméno], support@ubyhost.com, [telefon]
Číslo incidentu: [ID z /admin/incidents]

Další informace vám pošleme nejpozději [datum a čas].

[Jméno], provozovatel UbyHost, IČO [IČO]
```

### Template EN: first notice to a host

```
Subject: Important: personal data breach at UbyHost (Art. 33(2) GDPR)

Hello,

As the processor of your guests' data, we are notifying you without undue delay of a personal data breach.

What happened: [short description, e.g. "unauthorised access to the server on 4 Oct 2026 between 02:10 and 03:40"]
When we became aware: [date and time]
Data affected: [e.g. names, stay dates, nationality; document numbers are encrypted and the key (was / was not) affected]
Guests affected in your account: about [number], stays from [date] to [date]
Likely consequences: [e.g. risk of identity misuse / low risk]
What we have done: [e.g. took the server offline, rotated keys, logged out all users]
What we recommend you do:
- decide whether to notify the Czech Office for Personal Data Protection (ÚOOÚ). As controller you have 72 hours from becoming aware, which is from receiving this e-mail. Form: https://uoou.gov.cz/profesional/poruseni-zabezpeceni-osobnich-udaju
- [if relevant] ask the Czech Police for a new UbyPort web-service password (helpline +420 731 670 444, ubyport@pcr.cz) and enter it in UbyHost
- [if relevant] change the guest PIN and link for your property

We can prepare a list of affected guests and a notice text for them. If you want us to file the ÚOOÚ notification for you, send us a power of attorney.

Contact for this incident: [name], support@ubyhost.com, [phone]
Incident number: [ID from /admin/incidents]

We will send an update by [date and time] at the latest.

[Name], UbyHost operator, IČO [IČO]
```

### Template CS and EN: update or closing notice

```
Předmět: Aktualizace k incidentu [ID] / Update on incident [ID]

Nové informace / New facts: [...]
Upřesněný počet dotčených hostů / Revised number of guests: [...]
Přijatá opatření / Measures taken: [...]
Stav / Status: [uzavřeno / closed | probíhá / ongoing]
```

## 6. Notify the ÚOOÚ [Ohlásit ÚOOÚ]

Who: UbyHost for its own controller data (section 0). For guest data, each host, or UbyHost on the host's behalf with a power of attorney (the form has "Ohlášení nečiní správce", and the ÚOOÚ asks for the power of attorney to be attached).

Deadline: within 72 hours of becoming aware. If later, give the reasons for the delay in the form (section 4 of the form). Partial information is allowed; complete it later with "doplnění ohlášení".

Channel (verified on uoou.gov.cz on 4 Oct 2026):
1. Fill in the online form "Ohlášení porušení zabezpečení osobních údajů dle GDPR" at https://uoou.gov.cz/profesional/poruseni-zabezpeceni-osobnich-udaju. Choose "ohlášení dle čl. 33 GDPR" and "PRVOTNÍ OHLÁŠENÍ". Click "Uložit vyplněné podání k odeslání (PDF)". You can also save a draft as XML.
2. Send the PDF and attachments by one of:
   - datová schránka of the ÚOOÚ: ID `qkbaa2n` (best: counts as signed and gives proof of delivery);
   - e-mail to posta@uoou.gov.cz, but only with a qualified electronic signature (uznávaný elektronický podpis), or followed by the hand-signed form by post or in person. A plain e-mail is an incomplete filing under § 37(4) správní řád and does not count as notification;
   - post to Úřad pro ochranu osobních údajů, Pplk. Sochora 27, 170 00 Praha 7.
3. Phone for questions: +420 234 665 111.
4. Mark `authority_notified_at` and save the delivery receipt in the incident notes.

Datová schránka: as a self-employed person, check you have one and can log in before you ever need it [OWNER TO FILL: ID of your datová schránka]. [UNVERIFIED: whether it was set up automatically for OSVČ in 2023]

NÚKIB: a separate duty applies only to regulated services under zákon 264/2025 Sb. Position: UbyHost is not a regulated service at its size [UNVERIFIED].

### ÚOOÚ notification checklist (matches the sections of the form)

- [ ] 1. Controller: name, IČO, date of birth (for OSVČ), e-mail, phone, datová schránka, address. Who files (the controller or someone for it, with reason and power of attorney)
- [ ] 2. Contact person (no DPO): name, phone, e-mail
- [ ] 3. Other parties: processor (UbyHost, or for UbyHost's own data: AWS, Cloudflare if involved), with IČO and address
- [ ] 4. Timeline: start, end, time of awareness (dd.mm.yyyy HH:mm); reason if later than 72 hours
- [ ] 5. Cause: external attack, internal attack, system failure, negligence, other; and a short description
- [ ] 6. Effects: confidentiality, integrity, availability
- [ ] 7. Data categories: identification (name, birth date, document number), contact (address, e-mail), other; 7.1 special categories (normally none; ID photos are not biometric data here)
- [ ] 8. Data subjects: customers (guests, hosts), vulnerable persons (children) if any; 8.1 approximate number of people; 8.2 approximate number of records
- [ ] 9. Likely consequences: loss of control, identity theft, fraud, etc., with likelihood and severity
- [ ] 10. Measures before the breach: DPA, internal policies (this runbook, DPIA, records of processing), technical measures (2FA, field encryption, PIN, Turnstile, backups, audit log), hardware and software used (AWS Lightsail, SQLite, FastAPI), encryption
- [ ] 11. Measures after: what was done and when; whether people were or will be informed, or why not (Art. 34(3) reasons); other authorities told (Police ČR if a crime report was filed)
- [ ] 12. Cross-border processing: normally "ne" (Czech hosts, Czech processing). If guests from many countries are affected, the processing is still not cross-border in the Art. 4(23) sense unless the controller has establishments in several states [interpretation]
- [ ] 13. Non-EU establishment: not applicable
- [ ] 14. Further information
- [ ] Attach: copy of the notice to people (if sent), list of measures, power of attorney (if filing for a host)

## 7. Help hosts tell their guests [Pomoc s oznámením hostům]

When the host decides the risk is high:
1. Export the affected guests for each host: house-book CSV for the period, filtered to the affected stays. Send it to the host through a secure route (download from the host's own account, not as an e-mail attachment).
2. The host sends the notice. Guest e-mail addresses are deleted 30 days after the stay, so for older stays the host may have to use the booking platform's messaging or a public notice (Art. 34(3)(c)).
3. If the host asks, UbyHost may send the notice for the host, as an instruction under the DPA. Keep the written instruction.

Template for hosts to send to guests (CS and EN):

```
CS: Vážený hoste, při Vašem pobytu v [ubytování] od [datum] do [datum] jsme o Vás vedli údaje, které vyžaduje zákon (domovní kniha a hlášení cizinecké policii). Dne [datum] došlo u našeho poskytovatele softwaru k [popis]. Mohlo dojít k [vyzrazení jména, data narození, čísla dokladu]. Doporučujeme [sledovat neobvyklé použití Vašeho dokladu, případně požádat o nový doklad]. Přijali jsme tato opatření: [...]. Kontakt: [jméno, e-mail, telefon správce].

EN: Dear guest, during your stay at [property] from [date] to [date] we kept the data the law requires (guest book and report to the foreign police). On [date] our software provider had [description]. Your [name, date of birth, document number] may have been exposed. We recommend [watching for unusual use of your document, or asking for a new one]. We have taken these measures: [...]. Contact: [controller name, e-mail, phone].
```

Mark `subjects_notified_at` when hosts confirm, and note which hosts did not notify and why.

## 8. After the incident [Po incidentu]

1. Write the review in the incident notes: timeline, cause, what data, what was done, what changes. Close the incident (`closed_at`).
2. Fix the cause in code or configuration; reference the incident ID in the commit.
3. Update the DPIA (`02_dpia_identity_documents.md`) if the risk picture changed, and the records of processing if a vendor changed.
4. If many hosts were affected, publish a short notice on the site and send a closing update to all affected hosts.
5. Keep incident records [OWNER TO DECIDE: proposed 5 years after closure]. Note: the current code deletes incident rows only if the whole table is purged by hand; the workspace deletion job does not touch `security_incident`.
6. Once a year, do a 30-minute dry run: pretend the S3 key leaked and walk through sections 2 to 6.

## Sources
- ÚOOÚ, Porušení zabezpečení osobních údajů, with the form: https://uoou.gov.cz/profesional/poruseni-zabezpeceni-osobnich-udaju (opened 4 Oct 2026)
- ÚOOÚ PDF version of the form: https://uoou.gov.cz/media/profesional/ohlaseni-poruseni-zabezpeceni-dle-gdpr-1.pdf (found, not opened)
- Policie ČR, UbyPort contacts: https://policie.gov.cz/reditelstvi-sluzby-cizinecke-policie/informace-pro-ubytovatele (opened 4 Oct 2026)
- EDPB Guidelines 9/2022 on personal data breach notification (not opened this session)
