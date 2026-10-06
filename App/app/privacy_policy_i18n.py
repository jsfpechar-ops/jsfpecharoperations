"""Privacy Policy strings (EN/CS) — merged into host_i18n.STRINGS."""
from __future__ import annotations

from typing import Dict

PRIVACY_STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "privacy.page_title": "Privacy Policy",
        "privacy.page_lede": (
            "How %(name)s (the UbyHost software operator) processes personal data when you use the hosted service, visit public pages, or interact with us. This policy does not replace the guest privacy notice shown to your guests. That notice names the controller configured for the property, which may differ from its property manager."
        ),
        "privacy.effective": "Effective date: %(date)s. Version %(version)s.",
        "privacy.cookies.table_intro": "The table below lists every cookie and item of local storage the service sets.",
        "cookies.table.name": "Name",
        "cookies.table.party": "Set by",
        "cookies.table.purpose": "Purpose",
        "cookies.table.lifetime": "Lifetime",
        "cookies.party.first": "UbyHost",
        "privacy.operator_title": "Data controller for this policy",
        "privacy.footer_link": "Privacy Policy",
        "privacy.footer_short": "Privacy",
        "privacy.cross_legal": "Legal notice (operator identity)",
        "privacy.cross_terms": "Terms of Service",
        "privacy.cross_guest": "Guest privacy notice (per property link)",
        "privacy.guest_note": (
            "Guests who complete a form via /l/… see a separate notice naming the accommodation "
            "provider's configured controller. Hosts must configure that legal entity with contact "
            "details so the notice is complete; the property manager remains the guest contact for "
            "questions about the stay."
        ),
        "privacy.review_title": "About this policy",
        "privacy.review_body": (
            "This policy explains how UbyHost handles personal data under the GDPR and Czech Act "
            "No. 110/2019 Coll. It is a general policy, not advice for your specific situation; hosts "
            "remain responsible for their own compliance as controllers of guest data."
        ),
        "legal.cross_privacy": "Privacy Policy",
        "terms.cross_privacy": "Privacy Policy",
        "privacy.s01_title": "1. Scope and who should read this",
        "privacy.s01_body": (
            "This Privacy Policy (\"Policy\") describes how %(name)s, identification number (IČO) %(ico)s (the \"Operator\"), processes personal data in connection with the UbyHost web application and related websites (the \"Service\"). It applies to: (a) accommodation providers and their staff who hold a Host account (\"Host Users\"); (b) visitors to public pages such as /login, /legal, /terms, and /privacy; and (c) technical processing of Guest Data on behalf of Hosts as described below. It does not govern the relationship between a Host and their Guests as controller and data subject. That is covered by the guest-facing privacy notice at each property link (/l/{token}/privacy) and by the Host's own policies."
        ),
        "privacy.s02_title": "2. Controller identity and contact",
        "privacy.s02_body": (
            "For Host account data, authentication, billing contact details (if any), support "
            "correspondence, and operational logs relating to the Service, the Operator is the data "
            "controller within the meaning of Regulation (EU) 2016/679 (\"GDPR\") and Act No. "
            "110/2019 Coll., on personal data processing. Identity and address are published on "
            "/legal. The primary e-mail contact for privacy requests relating to the Operator's "
            "processing is support@ubyhost.com; you may also use the postal address on /legal. "
            "The Operator does not provide a guaranteed support hotline "
            "unless published there."
        ),
        "privacy.s03_title": "3. Roles: Operator, Host, and Guest",
        "privacy.s03_body": (
            "For each property, the configured controller legal entity is the data controller for personal data about Guests (names, travel documents, stays, signatures, and related records). The operating property manager is the default controller and remains the practical point of contact for questions about the stay. If the Host selects a different controller, that entity must genuinely determine the purposes and means of processing; changing a label in the Service does not itself transfer legal responsibility. The Operator provides hosted software and processes Guest Data only on the Host's documented instructions to deliver the Service, typically as a data processor under GDPR Article 28. The Operator is not a joint controller with the Host unless expressly agreed in writing. The Operator is controller for its own business data (accounts, security, hosting). Guest Data processing terms are in the Data Processing Agreement at /dpa. Nothing in this Policy transfers statutory duties of accommodation providers or controllers to the Operator."
        ),
        "privacy.s04_title": "4. Categories of Host User data",
        # LAWYER REVIEW
        "privacy.s04_body": (
            "We may process: account identifiers (username, internal user id, login e-mail address); "
            "authentication data (single-use login link token hashes stored for 1 day after expiry, "
            "signed session tokens, optional \"remember me\" duration, time-based one-time password "
            "(TOTP) secrets stored encrypted, passkey public keys with display names and usage dates "
            "and counters, WebAuthn challenge hashes stored for 1 day after expiry); profile and "
            "workspace settings; legal entity names, addresses, and contact e-mails you enter for "
            "guest notices; property and stay metadata; UbyPort or calendar integration credentials "
            "(stored encrypted at rest); audit and activity logs you generate in-app; communications "
            "you send to us; transactional e-mail delivery records (account e-mails such as login "
            "links, invitation, e-mail confirmation, e-mail change notice, and passkey-added notice "
            "are sent on the basis of your account action and are not marketing); and billing or plan "
            "information if fees apply. We do not require Host Users to provide special categories "
            "of data about themselves unless you voluntarily include such information in free-text fields."
        ),
        "privacy.s05_title": "5. Guest Data processed on your instructions",
        "privacy.s05_body": (
            "When Hosts use the Service, we process Guest Data they or their Guests submit: identity "
            "and travel document details, dates of stay, nationality, addresses, signatures, "
            "reservation-claim e-mail addresses, declared party size, optional passport photos or "
            "PDFs uploaded when the property requires them, house book entries, claim links, "
            "incomplete-registration reminders, completion receipts (including a copy to the Host), and "
            "data formatted for transmission toward UbyPort or related police reporting channels "
            "when enabled. Purposes, legal bases, and retention for Guests are determined by the "
            "Host as controller and explained in the guest privacy notice. The Operator implements "
            "technical and organisational measures appropriate to the risk but does not decide why "
            "Guest Data is collected from a GDPR perspective."
        ),
        "privacy.s06_title": "6. Purposes and legal bases (Operator as controller)",
        "privacy.s06_body": (
            "We process Host User data to: provide and secure the Service (contract / legitimate "
            "interest, GDPR Art. 6(1)(b) and (f)); comply with legal obligations (Art. 6(1)(c)); "
            "prevent abuse, fraud, and security incidents (legitimate interest); maintain records "
            "required for accounting or tax if applicable (legal obligation); and improve reliability "
            "using aggregated or pseudonymised diagnostics where possible (legitimate interest). Where "
            "we rely on legitimate interest, we balance our needs against your rights. Where consent "
            "is required by law, we will request it separately. Czech national rules in Act 110/2019 "
            "Coll. apply alongside GDPR."
        ),
        "privacy.s07_title": "7. Cookies and similar technologies",
        "privacy.s07_body": (
            "The Service uses strictly necessary cookies and similar storage: signed session cookies "
            "for Host login (12 hours, or 30 days if \"remember me\" is selected), a form-security "
            "cookie (up to 30 days), and a Host language preference (up to one year). On guest links, "
            "cookies remember PIN verification (up to 7 days), language, confirmed-reservation access, "
            "and forms submitted on that device (up to 60 days). Production traffic to ubyhost.com is "
            "proxied by Cloudflare. "
            "We may use Cloudflare Turnstile on production login and, after repeated failed guest PIN "
            "attempts, on guest PIN pages; custom managed challenges on private paths; and a small "
            "client-side security script that inventories third-party scripts loaded in the browser. "
            "These features may set or read technical identifiers and process connection data (such as "
            "IP address) under Cloudflare's terms and privacy notice; they are not used for advertising. "
            "We do not use third-party analytics or advertising cookies in the application as shipped. "
            "You can control cookies through browser settings; disabling session cookies will prevent "
            "login. Browsers may also honour HTTP Strict Transport Security (HSTS) so this hostname "
            "is opened only over HTTPS for a limited period."
        ),
        # WP09: owner's final wording from 04_legal_positions.md, sections 1, 4
        # and 5. analytics_* and optout_* are shown on /privacy only while
        # Umami is configured; roles_* sits in section 3, own_retention_* in 11.
        "privacy.analytics_title": "Website analytics",
        "privacy.analytics_body": (
            "On our public pages (not in the app) we use Umami Cloud, operated by Umami Software, "
            "Inc., with data stored in the EU, to count visits. Umami does not set cookies and does "
            "not store your IP address. It derives a short-lived anonymous visit identifier from "
            "your IP address, browser type and our website ID, and we see only aggregated "
            "statistics (pages viewed, referring site, browser, device type, country). We do not "
            "combine this data with account data and we do not use it for advertising. Legal "
            "basis: our legitimate interest in understanding how our website is used (Art. 6(1)(f) "
            "GDPR). The exemption under § 89(3) of Act No. 127/2005 Coll. applies because the "
            "measurement serves only anonymous traffic statistics. You can switch measurement off "
            "in your browser here:"
        ),
        "privacy.analytics_dnt": "We also respect your browser's Do Not Track setting.",
        "privacy.optout_lede": (
            "We measure visits to our public pages with Umami, without cookies."
        ),
        "privacy.optout_disable": "Turn off measurement in this browser",
        "privacy.optout_off_note": "Measurement is off in this browser.",
        "privacy.optout_enable": "Turn measurement back on",
        "privacy.own_retention_title": "How long we keep data",
        "privacy.own_retention_body": (
            "Invoices: 10 years from the end of the year of issue (Act No. 235/2004 Coll., § 35). "
            "Account data: while your account is active and 3 years after closure. Sign-up click "
            "identifier from Google Ads: at most 90 days after the click. Consent records: while "
            "your account is active and 3 years after. Backups are overwritten within 30 days."
        ),
        "privacy.roles_title": "Who is responsible",
        "privacy.roles_body": (
            "For your account, invoices, our website statistics and Google Ads measurement, "
            "%(name)s, IČO %(ico)s, %(address)s is the controller. For the data of your guests "
            "(guest book, stay-fee records, reports to the foreign police through UbyPort and any "
            "document photos), you as the accommodation provider are the controller and we "
            "process the data only on your instructions as your processor, under our data "
            "processing agreement. Our subprocessors are listed at /subprocessors. Google Ireland "
            "Ltd. receives the Google Ads click identifier only if you consent, and it processes "
            "this as an independent controller."
        ),
        # Shown only outside production when an UBYHOST_OPERATOR_* value is
        # empty; production refuses to start without them (env_guard).
        "privacy.placeholder_name": "[Company name]",
        "privacy.placeholder_ico": "[xxxxxxxx]",
        "privacy.placeholder_address": "[registered address]",
        "privacy.s08_title": "8. Server logs and security monitoring",
        "privacy.s08_body": (
            "Our infrastructure automatically logs technical data: IP addresses, timestamps, request "
            "paths, user agents, error traces, and security events (e.g. failed logins, rate limits). "
            "Cloudflare, as the DNS/CDN/security proxy for production, may also log or score requests "
            "for DDoS, bot, and leaked-credential protection. We use these logs to operate, debug, and "
            "protect the Service, typically for a limited rolling period unless longer retention is "
            "needed to investigate incidents or comply with law. Logs may contain personal data in "
            "incidental form (e.g. IP address)."
        ),
        "privacy.s09_title": "9. Recipients and subprocessors",
        "privacy.s09_body": (
            "Personal data is accessed by authorised Operator personnel and contractors bound by confidentiality. We use infrastructure subprocessors to host the Service, including Amazon Web Services (AWS Lightsail or comparable hosting in the EEA for production), Render.com (demo hosting), DNS or CDN providers such as Cloudflare (including Turnstile, managed challenges, leaked-credential mitigation, client-side script monitoring, and HSTS when enabled for the production zone), Google Drive and/or Amazon S3 when the Operator configures off-site backups, and a transactional e-mail provider (including Amazon SES when enabled) or support tools. Completion receipts may disclose the guest recipient address to the Host copied on the message. Guest Data may be transmitted to the Czech Police UbyPort systems or related endpoints when a Host enables reporting. That transmission occurs on the Host's instructions as processor. We require subprocessors that process personal data on our behalf to provide appropriate safeguards (GDPR Art. 28). The current register, purposes, possible data and transfer notes are at /subprocessors. Material changes are published there and reflected in this Policy."
        ),
        "privacy.s10_title": "10. International transfers",
        "privacy.s10_body": (
            "We aim to host and process data within the European Economic Area. If a subprocessor "
            "or support tool involves a transfer outside the EEA, we rely on appropriate safeguards "
            "such as Standard Contractual Clauses, adequacy decisions, or other mechanisms permitted "
            "under GDPR Chapter V. Details can be provided on request where required by law."
        ),
        "privacy.s11_title": "11. Retention",
        # LAWYER REVIEW
        "privacy.s11_body": (
            "Host account data is retained while the account is active and for a reasonable period "
            "after termination to allow export, resolve disputes, and comply with law. Login link "
            "token hashes are deleted 1 day after the link expires. WebAuthn challenge hashes are "
            "deleted 1 day after the challenge expires. Passkey records (public key, display name, "
            "dates, counter) are kept until removed by the Host or the account is deleted. Audit "
            "logs are kept for 3 years. Guest Data "
            "retention is controlled by Host settings and legal obligations (including typical "
            "six-year house book rules); the Operator may retain encrypted database and key backups "
            "on the server and, when configured, encrypted off-site copies (for example weekly to "
            "Google Drive and monthly to Amazon S3) for disaster recovery for a limited period before "
            "purging. Completed or terminal e-mail delivery rows are normally "
            "purged after 14 days; claim e-mails remain linked to retained reservations unless the Host "
            "releases the claim. Security logs are kept for short rolling windows unless an incident "
            "requires longer storage. When retention ends, we delete or anonymise data unless "
            "statutory storage applies."
        ),
        "privacy.s12_title": "12. Security",
        # LAWYER REVIEW
        "privacy.s12_body": (
            "We implement measures such as encryption of sensitive credentials and TOTP secrets at "
            "rest, HTTPS in transit (with HSTS on the production hostname), Cloudflare edge "
            "protections (Turnstile on host login and on guest PIN verification after repeated "
            "failures when configured; Bot Fight Mode; client-side script monitoring), access "
            "controls, rate limiting on authentication endpoints, separation of environments, and "
            "regular dependency updates. Login is by single-use e-mail link; Hosts are responsible "
            "for securing access to their login e-mail address. An authenticator app (TOTP) and "
            "passkeys (public key stored; biometric data never leaves the device) are available as "
            "optional additional verification. A change of login e-mail address triggers a notice "
            "to the old address. No method of transmission or storage is 100%% secure; Hosts must "
            "protect their e-mail account, authenticator devices, and passkey-enrolled devices, and "
            "configure guest links carefully. Report suspected security issues to the contact on /legal."
        ),
        "privacy.s13_title": "13. Your rights (Host Users)",
        "privacy.s13_body": (
            "Where the Operator is controller, you may have rights to access, rectification, erasure, "
            "restriction, portability, and objection under GDPR, and to withdraw consent where "
            "processing is consent-based. You may lodge a complaint with the Office for Personal "
            "Data Protection (ÚOOÚ), Pplk. Sochora 27, 170 00 Praha 7, www.uoou.cz. We respond to "
            "requests without undue delay and within statutory deadlines. We may need to verify your "
            "identity. Some rights may be limited where we must retain data by law or for defence of "
            "legal claims."
        ),
        "privacy.s14_title": "14. Guest rights",
        "privacy.s14_body": (
            "Guests should direct access, correction, deletion, and objection requests regarding "
            "their stay data to the controller named in the guest privacy notice for that property. "
            "Operational questions about arrival or accommodation go to the property manager shown "
            "as the stay contact; the two entities may differ. The Operator will assist Controllers "
            "with technical measures to fulfil requests where "
            "feasible and contractually required as processor, but cannot usually decide guest requests "
            "without Host instruction."
        ),
        "privacy.s15_title": "15. Automated decision-making",
        "privacy.s15_body": (
            "The Service does not use solely automated decision-making that produces legal or "
            "similarly significant effects on Host Users or Guests within the meaning of GDPR "
            "Article 22. Validation rules (e.g. required fields, document checks) assist users but "
            "do not replace Host or authority decisions."
        ),
        "privacy.s16_title": "16. Children",
        "privacy.s16_body": (
            "The Service is intended for business use by accommodation providers. Host accounts are "
            "not offered to children. Guest data about minors may be processed when required by "
            "accommodation law on the Host's responsibility as controller."
        ),
        "privacy.s17_title": "17. Marketing",
        "privacy.s17_body": (
            "We do not sell personal data. We may send service-related messages (security, terms or "
            "policy updates, operational notices) to account contacts. We do not send third-party "
            "marketing on behalf of others through the application unless explicitly stated and "
            "lawfully opted in."
        ),
        "privacy.s18_title": "18. Personal data breaches",
        "privacy.s18_body": (
            "If we become aware of a personal data breach affecting data for which we are controller, "
            "we will notify the ÚOOÚ and affected individuals where required by GDPR Articles 33–34. "
            "Where we process Guest Data as processor, we will inform the relevant Host without undue "
            "delay so the Host can meet controller obligations."
        ),
        "privacy.s19_title": "19. Host obligations as controller",
        "privacy.s19_body": (
            "Hosts must provide lawful bases and transparent notices to Guests, respond to data subject "
            "requests, maintain records of processing where required, conduct DPIAs when appropriate, "
            "and ensure instructions to the Operator are lawful. Hosts must not upload unnecessary "
            "special-category data. A Host selecting an alternate controller warrants that the entity "
            "actually controls the processing and that the Host is authorised to provide instructions "
            "on its behalf. Use of passport images should be limited to what law and risk assessment "
            "justify, with clear guest information."
        ),
        "privacy.s20_title": "20. Changes to this Policy",
        "privacy.s20_body": (
            "We may update this Policy for legal, technical, or business reasons. Material changes "
            "will be posted at /privacy with an updated effective date and, where practicable, "
            "communicated through the Service or account contact at least thirty (30) days before "
            "they take effect. Continued use after the effective date constitutes acknowledgement "
            "where permitted by law."
        ),
        "privacy.s21_title": "21. Relationship to Terms of Service",
        "privacy.s21_body": (
            "This Policy supplements the Terms of Service at /terms. In case of conflict regarding "
            "data protection roles, the more specific description of processing in this Policy and "
            "in the guest notice prevails for privacy matters; commercial terms remain in the Terms."
        ),
        "privacy.s22_title": "22. Contact",
        "privacy.s22_body": (
            "For privacy questions about Operator-controlled processing, contact %(name)s, IČO "
            "%(ico)s, at the address on /legal, or by e-mail at support@ubyhost.com. For guest data, "
            "contact the Host entity shown in the relevant guest privacy notice."
        ),
    },
    "cs": {
        "privacy.page_title": "Zásady ochrany osobních údajů",
        "privacy.page_lede": (
            "Jak %(name)s (provozovatel softwaru UbyHost) zpracovává osobní údaje při používání hostované služby, návštěvě veřejných stránek nebo komunikaci s námi. Tyto zásady nenahrazují informaci pro hosty. V ní je uveden správce nastavený pro dané ubytování, který se může lišit od správce objektu."
        ),
        "privacy.effective": "Účinnost od: %(date)s. Verze %(version)s.",
        "privacy.cookies.table_intro": "Tabulka níže uvádí všechny soubory cookie a položky místního úložiště, které služba nastavuje.",
        "cookies.table.name": "Název",
        "cookies.table.party": "Nastavuje",
        "cookies.table.purpose": "Účel",
        "cookies.table.lifetime": "Doba platnosti",
        "cookies.party.first": "UbyHost",
        "privacy.operator_title": "Správce údajů podle těchto zásad",
        "privacy.footer_link": "Zásady ochrany osobních údajů",
        "privacy.footer_short": "Soukromí",
        "privacy.cross_legal": "Právní informace (identita provozovatele)",
        "privacy.cross_terms": "Obchodní podmínky",
        "privacy.cross_guest": "Informace pro hosty (odkaz u každého ubytování)",
        "privacy.guest_note": (
            "Hosté vyplňující formulář na /l/… vidí samostatnou informaci s nastaveným správcem údajů. "
            "Ubytovatelé musí tomuto subjektu doplnit kontaktní údaje; správce objektu zůstává kontaktem "
            "hosta pro otázky k pobytu."
        ),
        "privacy.review_title": "K těmto zásadám",
        "privacy.review_body": (
            "Tyto zásady vysvětlují, jak UbyHost nakládá s osobními údaji podle GDPR a českého zákona "
            "č. 110/2019 Sb. Jde o obecné zásady, nikoli o poradenství pro vaši konkrétní situaci; "
            "odpovědnost za vlastní soulad jako správci údajů hostů nesou ubytovatelé."
        ),
        "legal.cross_privacy": "Zásady ochrany osobních údajů",
        "terms.cross_privacy": "Zásady ochrany osobních údajů",
        "privacy.s01_title": "1. Rozsah a komu je text určen",
        "privacy.s01_body": (
            "Tyto zásady ochrany osobních údajů (\"Zásady\") popisují, jak %(name)s, IČO %(ico)s (\"Provozovatel\"), zpracovává osobní údaje v souvislosti s webovou aplikací UbyHost a souvisejícími stránkami (\"Služba\"). Platí pro: (a) poskytovatele ubytování a jejich pracovníky s účtem (\"Uživatelé účtu\"); (b) návštěvníky veřejných stránek (/login, /legal, /terms, /privacy); (c) technické zpracování údajů hostů na pokyn ubytovatele dle níže. Neupravují vztah ubytovatele a hosta jako správce a subjektu údajů. To řeší informace pro hosty u odkazu (/l/{token}/privacy) a vlastní dokumenty ubytovatele."
        ),
        "privacy.s02_title": "2. Identita správce a kontakt",
        "privacy.s02_body": (
            "Pro údaje účtu ubytovatele, přihlášení, fakturační kontakty (pokud existují), podporu "
            "a provozní logy Služby je Provozovatel správcem ve smyslu nařízení (EU) 2016/679 "
            "(\"GDPR\") a zákona č. 110/2019 Sb. Identita a adresa jsou na /legal. E-mail "
            "support@ubyhost.com slouží pro žádosti o práva; použít lze také poštovní adresu na "
            "/legal. Telefonní linka není garantována, pokud není zveřejněna."
        ),
        "privacy.s03_title": "3. Role: provozovatel, ubytovatel a host",
        "privacy.s03_body": (
            "Správcem údajů hostů (jména, cestovní doklady, pobyty, podpisy aj.) je právnická osoba nastavená pro konkrétní ubytování. Provozovatel/správce ubytování je výchozím správcem údajů a praktickým kontaktem pro otázky k pobytu. Je-li zvolen jiný správce údajů, musí skutečně určovat účely a prostředky zpracování; pouhá změna označení ve Službě právní odpovědnost nepřenáší. Provozovatel UbyHostu poskytuje software a údaje hostů zpracovává jen na dokumentovaný pokyn ubytovatele, obvykle jako zpracovatel dle čl. 28 GDPR. Společná správa s ubytovatelem nenastává, pokud není výslovně písemně sjednána. Provozovatel je správcem vlastních provozních údajů. Podmínky zpracování údajů hostů jsou v DPA na /dpa. Povinnosti ubytovatele podle zákona se na Provozovatele nepřenášejí."
        ),
        "privacy.s04_title": "4. Kategorie údajů uživatelů účtu",
        # LAWYER REVIEW
        "privacy.s04_body": (
            "Můžeme zpracovávat: identifikátory účtu (uživatelské jméno, interní ID, přihlašovací "
            "e-mailová adresa); autentizační údaje (hashe tokenů jednorázových přihlašovacích odkazů "
            "uchovávané 1 den po uplynutí platnosti, podepsané tokeny relace, volitelné „zapamatovat\", "
            "šifrované tajemství TOTP pro dvoufázové ověření, veřejné klíče passkey s názvy a daty "
            "použití a čítači, hashe WebAuthn výzev uchovávané 1 den po uplynutí platnosti); nastavení; "
            "názvy a kontakty právnických osob pro informace hostům; metadata ubytování a pobytů; "
            "přihlašovací údaje k UbyPortu nebo kalendářům (šifrovaně); auditní záznamy; komunikaci "
            "s námi; záznamy o doručení transakčních e-mailů (e-maily k účtu, jako přihlašovací "
            "odkaz, pozvánka, potvrzení e-mailu, oznámení o změně e-mailu a upozornění na přidaný "
            "passkey, jsou odesílány na základě akce v účtu a nejde o marketing); fakturační údaje. "
            "Zvláštní kategorie údajů o ubytovateli nevyžadujeme, pokud je sami nezadáte v textových polích."
        ),
        "privacy.s05_title": "5. Údaje hostů na pokyn ubytovatele",
        "privacy.s05_body": (
            "Při používání Služby zpracováváme údaje, které ubytovatel nebo host zadá: identitu a "
            "doklady, termíny pobytu, státní příslušnost, adresy, podpisy, e-maily k převzetí rezervace, "
            "nahlášený počet hostů, fotografie nebo PDF pasu jen při zapnutí této povinnosti u ubytování, "
            "záznamy domovní knihy, odkazy k převzetí, upozornění na nedokončení, potvrzení o dokončení "
            "(včetně kopie ubytovateli) a data pro přenos do UbyPortu či souvisejících systémů "
            "policie, pokud je funkce zapnuta. Účely, právní základy a dobu uchování pro hosty "
            "určuje ubytovatel jako správce v informaci pro hosty. Provozovatel zajišťuje technická "
            "a organizační opatření, ale ne rozhoduje o účelu zpracování údajů hostů ve smyslu GDPR."
        ),
        "privacy.s06_title": "6. Účely a právní základy (Provozovatel jako správce)",
        "privacy.s06_body": (
            "Údaje uživatelů účtu zpracováváme pro poskytování a zabezpečení Služby (smlouva / "
            "oprávněný zájem, čl. 6 odst. 1 písm. b) a f) GDPR); plnění právních povinností (písm. c)); "
            "prevenci zneužití a incidentů (oprávněný zájem); účetní a daňové povinnosti; zlepšování "
            "spolehlivosti agregovanými diagnostikami. Při oprávněném zájmu vážíme naše potřeby a vaše "
            "práva. Souhlas vyžadujeme jen tam, kde to vyžaduje zákon. Platí i zákon č. 110/2019 Sb."
        ),
        "privacy.s07_title": "7. Cookies a podobné technologie",
        "privacy.s07_body": (
            "Služba používá nezbytné cookies: relaci přihlášení ubytovatele (12 hodin, nebo 30 dní při "
            "volbě „zapamatovat“), ochranu formulářů (nejvýše 30 dní) a jazyk ubytovatele (nejvýše rok). "
            "U hostovských odkazů cookies uchovávají PIN (nejvýše 7 dní), jazyk, přístup k potvrzené "
            "rezervaci a formuláře odeslané z daného zařízení (nejvýše 60 dní). Produkční provoz "
            "ubyhost.com zprostředkovává Cloudflare. Můžeme použít Cloudflare Turnstile na produkčním "
            "přihlášení a po opakovaných neúspěšných pokusech o PIN; vlastní řízené výzvy na neveřejných "
            "cestách; a malý "
            "skript klientské bezpečnosti, který eviduje skripty třetích stran v "
            "prohlížeči. Tyto funkce mohou zpracovávat technické identifikátory a údaje o připojení "
            "(např. IP) podle podmínek Cloudflare; nejde o reklamu. V aplikaci v základní podobě "
            "nepoužíváme reklamní ani analytické cookies třetích stran. Cookies lze omezit v prohlížeči; "
            "bez relačního cookie přihlášení nefunguje. Prohlížeče mohou také dodržovat HTTP Strict "
            "Transport Security (HSTS), takže se tato doména po omezenou dobu otevírá jen přes HTTPS."
        ),
        # WP09: konečné znění provozovatele z 04_legal_positions.md, oddíly 1,
        # 4 a 5. analytics_* a optout_* jen při zapnutém Umami.
        "privacy.analytics_title": "Měření návštěvnosti",
        "privacy.analytics_body": (
            "Na veřejných stránkách webu (ne v aplikaci) používáme nástroj Umami Cloud provozovaný "
            "společností Umami Software, Inc. s ukládáním dat v EU, abychom zjistili počet návštěv. "
            "Umami nepoužívá cookies a neukládá vaši IP adresu. Z IP adresy, typu prohlížeče a "
            "identifikátoru našeho webu vytváří krátkodobý anonymní identifikátor návštěvy a my "
            "vidíme pouze souhrnné statistiky (zobrazené stránky, odkazující web, prohlížeč, typ "
            "zařízení, země). Tato data nespojujeme s údaji z vašeho účtu a nepoužíváme je k "
            "reklamě. Právní základ: náš oprávněný zájem porozumět používání webu (čl. 6 odst. 1 "
            "písm. f) GDPR). Jde o měření nezbytné pro provoz webu ve smyslu § 89 odst. 3 zákona "
            "č. 127/2005 Sb., protože slouží jen k anonymní statistice návštěvnosti. Měření můžete "
            "ve svém prohlížeči vypnout zde:"
        ),
        "privacy.analytics_dnt": "Respektujeme také nastavení Do Not Track ve vašem prohlížeči.",
        "privacy.optout_lede": (
            "Návštěvnost veřejných stránek měříme nástrojem Umami bez cookies."
        ),
        "privacy.optout_disable": "Vypnout měření v tomto prohlížeči",
        "privacy.optout_off_note": "Měření je v tomto prohlížeči vypnuté.",
        "privacy.optout_enable": "Znovu zapnout měření",
        "privacy.own_retention_title": "Jak dlouho údaje uchováváme",
        "privacy.own_retention_body": (
            "Faktury: 10 let od konce roku vystavení (§ 35 zákona č. 235/2004 Sb.). Údaje účtu: po "
            "dobu trvání účtu a 3 roky po jeho zrušení. Identifikátor kliknutí z Google Ads: "
            "nejvýše 90 dní od kliknutí. Záznamy o souhlasech: po dobu trvání účtu a 3 roky poté. "
            "Zálohy se přepisují do 30 dní."
        ),
        "privacy.roles_title": "Kdo odpovídá za zpracování",
        "privacy.roles_body": (
            "Za údaje vašeho účtu, faktury, statistiky návštěvnosti webu a měření reklam Google "
            "Ads je správcem %(name)s, IČO %(ico)s, %(address)s. Za údaje vašich hostů (domovní "
            "kniha, evidence k poplatku z pobytu, hlášení cizinecké policii přes UbyPort a "
            "případné fotografie dokladů) jste správcem vy jako ubytovatel a my je zpracováváme "
            "pouze podle vašich pokynů jako zpracovatel na základě zpracovatelské smlouvy. Seznam "
            "našich subzpracovatelů najdete na /subprocessors. Společnost Google Ireland Ltd. "
            "obdrží identifikátor kliknutí z Google Ads jen s vaším souhlasem a zpracovává jej "
            "jako samostatný správce."
        ),
        "privacy.placeholder_name": "[Obchodní firma]",
        "privacy.placeholder_ico": "[xxxxxxxx]",
        "privacy.placeholder_address": "[sídlo]",
        "privacy.s08_title": "8. Serverové logy a bezpečnost",
        "privacy.s08_body": (
            "Infrastruktura automaticky zaznamenává IP adresy, čas, cesty požadavků, user agent, chyby "
            "a bezpečnostní události (neúspěšná přihlášení, rate limiting). Cloudflare jako DNS/CDN/"
            "bezpečnostní proxy pro produkci může rovněž logovat nebo hodnotit požadavky kvůli DDoS, "
            "botům a únikům přihlašovacích údajů. Logy slouží provozu a ochraně Služby po omezenou dobu, "
            "déle jen při incidentu nebo zákonné povinnosti. Mohou obsahovat osobní údaje (např. IP)."
        ),
        "privacy.s09_title": "9. Příjemci a subzpracovatelé",
        "privacy.s09_body": (
            "Údaje vidí oprávnění pracovníci a smluvní partneři s mlčenlivostí. Hosting zajišťují "
            "subzpracovatelé včetně Amazon Web Services (Lightsail nebo obdobný hosting v EHP pro "
            "produkci), Render.com (ukázkový provoz), DNS/CDN včetně "
            "Cloudflare (včetně Turnstile, řízených výzev, kontroly uniklých přihlašovacích údajů, "
            "monitoringu skriptů na straně klienta a HSTS v produkční zóně), Google Drive a/nebo Amazon S3 při nastavených "
            "off-site zálohách, poskytovatel transakčních e-mailů (včetně Amazon SES po zapnutí) "
            "a případně podpora. Kopie potvrzení o dokončení může ubytovateli zpřístupnit adresu "
            "hosta uvedenou jako příjemce. Údaje hostů mohou být přeneseny do "
            "UbyPort Policie ČR na pokyn ubytovatele jako zpracovatele. Subzpracovatelé musí mít "
            "vhodné záruky (čl. 28 GDPR). Aktuální seznam, účely, možné údaje a informace o předání "
            "jsou na /subprocessors. Podstatné změny zveřejníme tam a promítneme do těchto Zásad."
        ),
        "privacy.s10_title": "10. Přeshraniční přenosy",
        "privacy.s10_body": (
            "Usilujeme o zpracování v EHP. Pokud subzpracovatel přenáší údaje mimo EHP, použijeme "
            "standardní smluvní doložky, rozhodnutí o přiměřenosti nebo jiné prostředky dle kapitoly V "
            "GDPR. Podrobnosti poskytneme na žádost, kde to zákon vyžaduje."
        ),
        "privacy.s11_title": "11. Doba uchování",
        # LAWYER REVIEW
        "privacy.s11_body": (
            "Údaje účtu držíme po dobu aktivního účtu a přiměřeně po ukončení kvůli exportu, sporům "
            "a zákonu. Hashe tokenů přihlašovacích odkazů se mažou 1 den po uplynutí platnosti odkazu. "
            "Hashe WebAuthn výzev se mažou 1 den po uplynutí platnosti výzvy. Záznamy passkey (veřejný "
            "klíč, název, data, čítač) se uchovávají do jejich odebrání Ubytovatelem nebo smazání "
            "účtu. Auditní záznamy se uchovávají 3 roky. Údaje hostů řídí nastavení a povinnosti "
            "ubytovatele (včetně typické šestileté domovní knihy); Provozovatel může uchovávat "
            "šifrované zálohy databáze a klíčů na serveru a při nastavení off-site kopie (např. týdně "
            "na Google Drive a měsíčně na Amazon S3) pro obnovu po havárii po omezenou dobu. "
            "Dokončené či konečné záznamy doručení se běžně mažou po 14 dnech; e-mail k převzetí "
            "zůstává spojen s uchovanou rezervací, pokud ubytovatel převzetí neuvolní. Bezpečnostní "
            "logy po krátkou dobu. Po uplynutí mažeme nebo anonymizujeme, pokud zákon nevyžaduje jinak."
        ),
        "privacy.s12_title": "12. Bezpečnost",
        # LAWYER REVIEW
        "privacy.s12_body": (
            "Používáme šifrování citlivých přihlašovacích údajů a TOTP, HTTPS (s HSTS na produkční "
            "doméně), ochrany Cloudflare na okraji sítě (Turnstile při přihlášení a po opakovaných "
            "neúspěších PIN u hostů, pokud je zapnuto; Bot Fight Mode; monitoring skriptů v "
            "prohlížeči), řízení přístupu, rate limiting přihlášení, oddělení prostředí a aktualizace "
            "závislostí. Přihlášení probíhá jednorázovým e-mailovým odkazem; Ubytovatelé odpovídají "
            "za zabezpečení přístupu ke své přihlašovací e-mailové schránce. Jako volitelné "
            "dodatečné ověření je dostupná autentizační aplikace (TOTP) a passkeys (ukládá se pouze "
            "veřejný klíč; biometrická data nikdy neopustí zařízení). Změna přihlašovacího e-mailu "
            "spustí oznámení na původní adresu. Žádný přenos není stoprocentně bezpečný; Ubytovatelé "
            "musí chránit svou e-mailovou schránku, autentizační aplikaci a zařízení s passkey a "
            "pečlivě sdílet odkazy hostům. Bezpečnostní incidenty hlaste kontaktu na /legal."
        ),
        "privacy.s13_title": "13. Vaše práva (uživatelé účtu)",
        "privacy.s13_body": (
            "Jako správce můžete uplatnit přístup, opravu, výmaz, omezení, přenositelnost a námitku dle "
            "GDPR; odvolat souhlas, kde je základem. Stížnost u Úřadu pro ochranu osobních údajů, "
            "Pplk. Sochora 27, 170 00 Praha 7, www.uoou.cz. Vyřizujeme bez zbytečného odkladu. Můžeme "
            "ověřit totožnost. Práva mohou být omezena zákonem nebo obranou nároků."
        ),
        "privacy.s14_title": "14. Práva hostů",
        "privacy.s14_body": (
            "Hosté žádají o přístup, opravu, výmaz a námitku u správce uvedeného v informaci pro dané "
            "ubytování. Provozní otázky k příjezdu či pobytu patří správci/provozovateli ubytování; "
            "tento kontakt se může od správce údajů lišit. Provozovatel UbyHostu jako zpracovatel "
            "pomůže technicky, pokud je to možné a smluvně "
            "nutné, ale obvykle nerozhoduje bez pokynu ubytovatele."
        ),
        "privacy.s15_title": "15. Automatizované rozhodování",
        "privacy.s15_body": (
            "Služba nepoužívá čistě automatizované rozhodování s právními nebo obdobně významnými "
            "účinky dle čl. 22 GDPR. Validace polí pomáhá uživatelům, nenahrazuje rozhodnutí "
            "ubytovatele nebo úřadů."
        ),
        "privacy.s16_title": "16. Děti",
        "privacy.s16_body": (
            "Služba je určena pro podnikatelské použití ubytovatelů. Účty dětem nenabízíme. Údaje o "
            "nezletilých hostech mohou být zpracovány zákonnou povinností ubytovatele jako správce."
        ),
        "privacy.s17_title": "17. Marketing",
        "privacy.s17_body": (
            "Osobní údaje neprodáváme. Můžeme zasílat provozní zprávy (bezpečnost, změny podmínek či "
            "zásad). Marketing třetích stran přes aplikaci nebez souhlasu neprovádíme."
        ),
        "privacy.s18_title": "18. Porušení zabezpečení údajů",
        "privacy.s18_body": (
            "Při porušení zabezpečení údajů, za která jsme správcem, oznámíme ÚOOÚ a dotčené osoby dle "
            "čl. 33–34 GDPR. U údajů hostů jako zpracovatel bez zbytečného odkladu informujeme "
            "ubytovatele."
        ),
        "privacy.s19_title": "19. Povinnosti ubytovatele jako správce",
        "privacy.s19_body": (
            "Ubytovatel musí hostům sdělit právní základy a informace, vyřizovat žádosti subjektů, vést "
            "záznamy, provádět DPIA kde je třeba a dávat Provozovateli jen zákonné pokyny. Při volbě "
            "jiného správce Ubytovatel potvrzuje, že tento subjekt zpracování skutečně řídí a Ubytovatel "
            "je oprávněn dávat pokyny jeho jménem. Fotografie pasů lze používat jen v nezbytném "
            "rozsahu s jasnou informací pro hosty."
        ),
        "privacy.s20_title": "20. Změny Zásad",
        "privacy.s20_body": (
            "Zásady můžeme měnit. Podstatné změny zveřejníme na /privacy s datem účinnosti a pokud "
            "možno oznámíme ve Službě nejméně třicet (30) dní předem. Pokračující používání po datu "
            "účinnosti znamená seznámení, kde to zákon dovoluje."
        ),
        "privacy.s21_title": "21. Vztah k obchodním podmínkám",
        "privacy.s21_body": (
            "Zásady doplňují obchodní podmínky na /terms. Při rozporu v oblasti ochrany údajů mají "
            "přednost tyto Zásady a informace pro hosty; obchodní ujednání zůstávají v podmínkách."
        ),
        "privacy.s22_title": "22. Kontakt",
        "privacy.s22_body": (
            "Dotazy ke zpracování Provozovatele směřujte na %(name)s, IČO %(ico)s, adresu na /legal "
            "nebo e-mail support@ubyhost.com. K údajům hostů kontaktujte správce v informaci u daného "
            "ubytování."
        ),
    },
}
