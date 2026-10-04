# Additions to the host Terms of Service (CS and EN)

For: `App/app/terms_i18n.py` (Terms version 1.5, effective 19 September 2026, published at `/terms`).
Reasoned drafting, not attorney advice.

## 1. What the current terms already say

| Topic asked for | Existing clause | Covered? |
|---|---|---|
| Host is legally responsible for reporting under zákon 326/1999 Sb. | § 5 (host "solely responsible" for duties under Act 326/1999; nothing transfers statutory duties to the Operator); § 8 (host must "meet reporting deadlines", configure UbyPort credentials, is solely liable for fines) | Yes |
| Host is responsible for the stay fee | Not mentioned anywhere. § 5 and § 8 name only 326/1999 Sb., house book rules and GDPR | **No: add** |
| UbyHost is a tool that submits on the host's instruction | § 4 ("does not act as the Host's agent toward authorities unless explicitly stated"); § 10 (transmits "under the Host's configured instructions": manual, immediate, delayed) | Partly. It does not say the filing is made with the host's own UbyPort access and in the host's name. **Add** |
| Host must check filings and file by hand when UbyHost reports a problem or is unavailable | § 10 ("must independently verify submission status, retain proof of reporting, and maintain contingency procedures (including manual filing where required)") | Partly. No trigger, no deadline reminder, no link to the guide. **Make concrete** |
| Limitation of liability, B2B, not excluding intent or gross negligence | § 17 (cap: greater of 12 months' fees or CZK 5,000; exception "where liability cannot be limited under mandatory law (including intentional harm or gross negligence where such limits are impermissible)") | Partly. The wording "where such limits are impermissible" suggests that limiting liability for gross negligence is sometimes allowed. Under § 2898 občanský zákoník it never is. **Reword** |
| Availability best effort | § 13 ("commercially reasonable efforts", no uptime guarantee); § 23 (force majeure includes UbyPort outages) | Yes. Add one sentence that an outage does not move statutory deadlines |
| Host authorises UbyHost to store and use the UbyPort credentials solely for filing | Not covered. § 8 only says the host must configure credentials correctly; DPA § 4 mentions "encryption of credentials" | **No: add** |

§ 2898 zákon 89/2012 Sb., checked on 4 October 2026 (text via pracepropravniky.cz, not the official collection): "Nepřihlíží se k ujednání, které předem vylučuje nebo omezuje povinnost k náhradě újmy způsobené člověku na jeho přirozených právech, anebo způsobené úmyslně nebo z hrubé nedbalosti; nepřihlíží se ani k ujednání, které předem vylučuje nebo omezuje právo slabší strany na náhradu jakékoli újmy." Consequences for the drafting:
- No cap or exclusion can apply to intent, gross negligence or harm to natural rights (life, health, privacy). Say so plainly.
- A cap against a "weaker party" (slabší strana) is disregarded. Consumers are weaker parties; a small host may also argue it is one (§ 433 občanský zákoník [UNVERIFIED, not opened]). Keep the cap modest and tied to fees, so it looks like a fair allocation of risk. [OWNER TO DECIDE: keep CZK 5,000 or raise the floor to CZK 10,000.]

## 2. Proposed changes

Insert as shown. Clause numbers follow the existing structure, so nothing else has to be renumbered. New sub-clauses go into the same i18n keys (`terms.s05_body`, `terms.s10_body`, `terms.s13_body`, `terms.s17_body`) and one new key pair `terms.s10a_title` / `terms.s10a_body`.

### 2.1 § 5 Roles of the parties: add at the end

EN:
> The Host is also solely responsible for the local stay fee (poplatek z pobytu) under Act No. 565/1990 Coll. and the municipal ordinance: for collecting it, keeping the record book, reporting to the municipality and paying it. Where the Service calculates the fee or prepares a report, a register or a payment QR code, these are aids for the Host. The Operator does not file the report or pay the fee. The Host checks the figures before using them.

CS:
> Ubytovatel dále výhradně odpovídá za místní poplatek z pobytu podle zákona č. 565/1990 Sb. a obecně závazné vyhlášky obce: za jeho vybrání, vedení evidenční knihy, ohlášení obci a odvod. Pokud Služba poplatek vypočítá nebo připraví hlášení, evidenci či QR kód pro platbu, jde o pomůcku pro Ubytovatele. Provozovatel hlášení nepodává a poplatek neodvádí. Ubytovatel údaje před použitím zkontroluje.

### 2.2 § 10 UbyPort and police reporting: replace the whole body

Keeps everything in the current § 10 and adds 10.1, 10.3 to 10.5.

EN:
> 10.1 The duty to report accommodated foreigners to the Police of the Czech Republic under Act No. 326/1999 Coll. is the Host's. The Service is a technical tool. Where reporting is enabled, the Service transmits records to UbyPort only on the Host's instruction, given through the property's reporting setting (manual, immediately when all declared forms are complete, or after a set delay) or by a send action in the Service. Each transmission is made with the Host's own UbyPort web-service access and in the Host's name. The Operator does not act as the Host's representative or agent toward the police and does not report anything in its own name.
>
> 10.2 The Operator does not guarantee that any submission will be received, accepted, validated, or deemed compliant by the Police of the Czech Republic, the Ministry of the Interior, or any authority. Outages, schema changes, credential issues, network failures, and manual review by authorities are outside the Operator's control.
>
> 10.3 The Host checks the result of every filing in the Service (status and the police receipt, Doručenka) and keeps proof of reporting. Demo, sandbox, or test data must not be relied upon as official police records.
>
> 10.4 If the Service shows that a filing was rejected, failed, or has an unknown outcome, or warns that a deadline is near, or if the Service or UbyPort's web service is unavailable, the Host files the affected guests itself within the statutory time limit (currently 3 working days from the start of accommodation), for example through the UbyPort web application with its own login. Instructions are in the guide "Filing by hand" at /pruvodce/rucni-hlaseni-ubyport [OWNER TO CONFIRM slug]. Before sending again from the Service, the Host checks in the UbyPort web application that the guest is not already reported, because a second filing counts as a duplicate. The Host tells the Operator through support which guests it filed by hand.
>
> 10.5 Notices from the Service about filings are sent in the Service and to the Account e-mail. The Host keeps that e-mail address working and reads these notices.

CS:
> 10.1 Povinnost hlásit ubytování cizinců Policii České republiky podle zákona č. 326/1999 Sb. má Ubytovatel. Služba je technický nástroj. Je-li hlášení zapnuto, Služba odesílá záznamy do UbyPortu pouze na pokyn Ubytovatele, daný nastavením hlášení u ubytování (ručně, okamžitě po dokončení všech nahlášených formulářů, nebo po nastavené prodlevě) nebo odesláním ve Službě. Každé odeslání probíhá s vlastními přístupovými údaji Ubytovatele k webové službě UbyPort a jménem Ubytovatele. Provozovatel není vůči policii zástupcem ani zmocněncem Ubytovatele a nic nehlásí vlastním jménem.
>
> 10.2 Provozovatel nezaručuje, že hlášení Policie ČR, Ministerstvo vnitra ČR ani jiný úřad přijme, ověří nebo uzná za řádné. Výpadky, změny schémat, problémy s přístupovými údaji, výpadky sítě a ruční kontrola úřady jsou mimo kontrolu Provozovatele.
>
> 10.3 Ubytovatel u každého hlášení ve Službě zkontroluje výsledek (stav a doručenku Policie ČR) a uchovává doklad o splnění povinnosti. Demo, testovací nebo vzorová data nelze považovat za oficiální policejní záznamy.
>
> 10.4 Pokud Služba ukáže, že hlášení bylo odmítnuto, selhalo nebo má neznámý výsledek, nebo upozorní na blížící se lhůtu, nebo pokud Služba či webová služba UbyPort nejsou dostupné, podá Ubytovatel hlášení dotčených hostů sám v zákonné lhůtě (nyní 3 pracovní dny od začátku ubytování), například ve webové aplikaci UbyPort se svým přihlášením. Návod je v průvodci „Ruční hlášení“ na /pruvodce/rucni-hlaseni-ubyport [OWNER TO CONFIRM slug]. Před dalším odesláním ze Služby Ubytovatel ve webové aplikaci UbyPort ověří, že host již nahlášen není, protože druhé odeslání se počítá jako duplicita. Ubytovatel sdělí Provozovateli přes podporu, které hosty nahlásil ručně.
>
> 10.5 Upozornění Služby k hlášení se zobrazují ve Službě a posílají na e-mail Účtu. Ubytovatel udržuje tuto adresu funkční a upozornění čte.

### 2.3 New § 10a UbyPort access credentials (after § 10)

Key: `terms.s10a_title`, `terms.s10a_body`.

EN title: "10a. UbyPort access credentials"
> The Host authorises the Operator to store the UbyPort web-service user name and password that the Host enters for a property, and to use them solely to transmit the Host's reports to UbyPort and to test the connection when the Host asks. The Operator stores the password encrypted, does not show it in the Service, does not use it for any other purpose and does not give it to anyone except as required by law. The Host may change or delete the credentials in the Service at any time; reporting from the Service then stops until valid credentials are entered. The Host requests web-service credentials from the Police of the Czech Republic and keeps its own login to the UbyPort web application, so that it can file by hand. If the Host suspects that the credentials have been misused, it asks the police for new ones and tells the Operator. The Operator tells the Host without undue delay if it learns that stored credentials may have been exposed. The authorisation ends when the credentials are deleted or the Account is closed; the Operator then deletes them.

CS title: "10a. Přístupové údaje k UbyPortu"
> Ubytovatel zmocňuje Provozovatele, aby uchovával přihlašovací jméno a heslo k webové službě UbyPort, které Ubytovatel u ubytování zadá, a používal je výhradně k odesílání hlášení Ubytovatele do UbyPortu a k ověření spojení na žádost Ubytovatele. Provozovatel heslo uchovává šifrované, ve Službě ho nezobrazuje, nepoužívá ho k jinému účelu a nikomu ho nepředává, ledaže to vyžaduje zákon. Ubytovatel může údaje ve Službě kdykoli změnit nebo smazat; hlášení ze Služby se pak zastaví, dokud nezadá platné údaje. Ubytovatel si přístupové údaje k webové službě vyžádá od Policie ČR a ponechá si vlastní přihlášení do webové aplikace UbyPort, aby mohl hlásit ručně. Při podezření na zneužití údajů požádá Ubytovatel policii o nové a informuje Provozovatele. Provozovatel bez zbytečného odkladu informuje Ubytovatele, zjistí-li, že uložené údaje mohly být vyzrazeny. Zmocnění končí smazáním údajů nebo zrušením Účtu; Provozovatel je poté smaže.

Note: "zmocňuje" here means permission to use the credentials, not a power of attorney to act toward the police. § 10.1 says the Operator is not the host's zmocněnec toward the police. If that reads as a contradiction, use "opravňuje" instead of "zmocňuje". [OWNER TO DECIDE; recommendation: "opravňuje"]

Code fact behind this clause: the password is stored in `apartment.uby_ws_password_enc` (MultiFernet), decrypted only to build the SOAP request (`routes/admin.py`, `reporting.py`); the workspace deletion job deletes the `apartment` rows, and with them the credentials.

### 2.4 § 13 Service availability: add at the end

EN:
> An outage of the Service, of UbyPort or of a provider does not extend the Host's statutory time limits. In that case the Host follows § 10.4. Where practicable, the Operator announces planned maintenance in the Service in advance and schedules it outside 8:00 to 20:00 Czech time.

CS:
> Výpadek Služby, UbyPortu nebo dodavatele neprodlužuje zákonné lhůty Ubytovatele. V takovém případě postupuje Ubytovatel podle čl. 10.4. Je-li to možné, oznámí Provozovatel plánovanou údržbu ve Službě předem a provádí ji mimo dobu 8:00 až 20:00 českého času.

[OWNER TO DECIDE: keep the maintenance window promise or delete the last sentence.]

### 2.5 § 17 Limitation of liability: replace the whole body

EN:
> 17.1 The Operator is not liable for loss of profit, lost business opportunity or other indirect or consequential damage.
>
> 17.2 The Operator's total liability for all claims arising from the Service or these Terms in any calendar year is limited to the greater of (a) the fees the Host paid to the Operator for the Service in the twelve (12) months before the event giving rise to the claim, or (b) CZK 5,000.
>
> 17.3 The Operator is not liable for fines or other consequences of a report that was late, missing or wrong, to the extent the Host did not check the result of the filing or did not file by hand under § 10.4 after the Service reported a problem or was unavailable.
>
> 17.4 Sections 17.1 to 17.3 do not apply to damage caused intentionally or through gross negligence, to harm to a person's natural rights (including life, health and privacy), or where the Host is a consumer or otherwise a weaker party, because Czech law does not allow such liability to be excluded or limited in advance (§ 2898 of Act No. 89/2012 Coll., Civil Code). They also do not limit either party's liability to data subjects or supervisory authorities under the GDPR.
>
> 17.5 For business users the parties agree that these limits are a fair allocation of risk, taking into account the price of the Service and the Host's duty to check filings.

CS:
> 17.1 Provozovatel neodpovídá za ušlý zisk, ztrátu obchodní příležitosti ani jinou nepřímou či následnou škodu.
>
> 17.2 Celková odpovědnost Provozovatele za všechny nároky ze Služby nebo z těchto Podmínek v jednom kalendářním roce je omezena na vyšší z částek: (a) úplata, kterou Ubytovatel Provozovateli za Službu zaplatil za dvanáct (12) měsíců před událostí, z níž nárok vznikl, nebo (b) 5 000 Kč.
>
> 17.3 Provozovatel neodpovídá za pokuty ani jiné následky opožděného, chybějícího nebo chybného hlášení v rozsahu, v jakém Ubytovatel nezkontroloval výsledek hlášení nebo nepodal hlášení ručně podle čl. 10.4 poté, co Služba ohlásila problém nebo nebyla dostupná.
>
> 17.4 Články 17.1 až 17.3 se nepoužijí na škodu způsobenou úmyslně nebo z hrubé nedbalosti, na újmu na přirozených právech člověka (včetně života, zdraví a soukromí), ani je-li Ubytovatel spotřebitelem nebo jinak slabší stranou, protože české právo neumožňuje takovou odpovědnost předem vyloučit ani omezit (§ 2898 zákona č. 89/2012 Sb., občanský zákoník). Neomezují ani odpovědnost kterékoli strany vůči subjektům údajů a dozorovým úřadům podle GDPR.
>
> 17.5 U podnikatelů strany souhlasí, že jde o přiměřené rozdělení rizika s ohledem na cenu Služby a povinnost Ubytovatele kontrolovat hlášení.

Changes from the current § 17: drops "incidental, special, punitive" (not Czech categories), drops "loss of data" from the exclusion (losing guest data the host must keep for 6 years is the main risk a host would sue over; excluding it outright invites a § 2898 or unfairness fight), adds the per-year cap wording, adds 17.3, and states § 2898 plainly.

Also check DPA § 18: it refers liability to the Terms and says "Nothing in this DPA limits either party's liability where limitation is not permitted by law." That fits the new § 17.4. No change needed.

## 3. Rollout

1. Bump `terms.effective` to version 1.6 and a date at least 30 days after hosts are told (§ 22: material changes are notified 30 days ahead through the Service or the Account e-mail).
2. Bump `TERMS_VERSION` in `config.py` (env `UBYHOST_TERMS_VERSION`, now "1.5") so hosts accept 1.6 at next login (the acceptance flow in `routes/admin_accounts.py` `/account/accept` records it in `legal_acceptance`).
3. Add the new strings to the tests that check legal copy (`tests/test_legal_contents.py`).
4. Publish `05_manual_filing_fallback.md` as a public guide first, so the § 10.4 link works on the day 1.6 takes effect.
