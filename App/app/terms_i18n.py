"""Terms of Service strings (EN/CS) — merged into host_i18n.STRINGS."""
from __future__ import annotations

from typing import Dict

TERMS_STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "terms.page_title": "Terms of Service",
        "terms.page_lede": (
            "Contract between the UbyHost software operator and accommodation providers "
            "who use the service. Please read carefully before using UbyHost."
        ),
        "terms.effective": "Effective date: %(date)s. Version %(version)s.",
        "terms.operator_title": "Service provider",
        "terms.footer_link": "Terms of Service",
        "terms.footer_short": "Terms",
        "terms.cross_legal": "Legal notice (operator identity)",
        "terms.review_title": "About these terms",
        "terms.review_body": (
            "These terms describe the agreement between you and the UbyHost Operator and follow Czech "
            "law. They are general terms for the service, not advice for your specific situation."
        ),
        "legal.cross_terms": "Terms of Service",
        "terms.s01_title": "1. Introduction and acceptance",
        "terms.s01_body": (
            "These Terms of Service (\"Terms\") govern access to and use of the UbyHost web application, "
            "related software, documentation, and hosted infrastructure (collectively, the \"Service\") "
            "operated by %(name)s, identification number (IČO) %(ico)s, a self-employed person "
            "(osoba samostatně výdělečně činná) under the laws of the Czech Republic (the \"Operator\"). "
            "By creating an account, logging in, or otherwise using the Service, you (the \"Host\") "
            "confirm that you have read, understood, and agree to be bound by these Terms and the "
            "Data Processing Agreement at /dpa (which is incorporated by reference for Guest Data). "
            "If you do not agree, you must not use the Service. Where you accept on behalf of a legal entity, "
            "you represent that you have authority to bind that entity. The Service is offered primarily "
            "to accommodation providers and other business users; if you are a consumer within the "
            "meaning of Act No. 634/1992 Coll., as amended (including Act No. 261/2021 Coll.), "
            "mandatory consumer protections apply to the extent they cannot be validly excluded."
        ),
        "terms.s02_title": "2. Definitions",
        "terms.s02_body": (
            "\"Host\" means the natural or legal person that registers for and uses the Service to "
            "manage accommodation. \"Guest\" means a person whose data the Host collects through the "
            "Service. \"Guest Data\" means personal and other data relating to Guests entered or "
            "generated through the Service. \"Legal Entity\" means an entity configured by the Host "
            "as the property's operating manager or Guest Data controller. \"UbyPort\" means the Czech police foreigner reporting system "
            "and related interfaces. \"Account\" means the Host's registered workspace. \"Content\" "
            "means data, text, images, and files submitted by the Host or Guests through the Service."
        ),
        "terms.s03_title": "3. Provider identity",
        "terms.s03_body": (
            "The Service is provided by %(name)s, IČO %(ico)s (the Operator). The Operator is the "
            "provider of the software and hosted environment. For each property, the Host configures "
            "(a) the property manager/operating entity, which is the practical point of contact for "
            "the stay, and (b) the Guest Data controller. The property manager is the default "
            "controller; an alternate entity may be selected only where it genuinely determines the "
            "purposes and means of processing and the Host has authority to bind it. Changing a name "
            "or contact in the Service does not by itself transfer controller responsibility. The "
            "configured controller is responsible under Regulation (EU) 2016/679 (GDPR) and Czech "
            "implementing law. Operator identity and contact are published on /legal."
        ),
        "terms.s04_title": "4. Description of the Service",
        "terms.s04_body": (
            "UbyHost is a software-as-a-service tool that helps accommodation providers maintain house "
            "book records, collect guest details via web forms, manage stays, and prepare or transmit "
            "reports toward UbyPort. Features may change, be added, or removed at the Operator's "
            "discretion. The Service may integrate with third-party systems (including government "
            "systems). The Operator does not provide accommodation, legal, tax, or immigration "
            "advice, and does not act as the Host's agent toward authorities unless explicitly stated."
        ),
        "terms.s05_title": "5. Roles of the parties",
        "terms.s05_body": (
            "The Host is solely responsible for compliance with obligations of an accommodation "
            "provider under Czech law, including Act No. 326/1999 Coll. on residence of foreign "
            "nationals, related decrees, house book rules, and GDPR duties as data controller. "
            "The Operator provides technical infrastructure and processes Guest Data on the "
            "Host's documented instructions to deliver the Service — as a data processor under "
            "GDPR Article 28 pursuant to the Data Processing Agreement at /dpa. Nothing in these "
            "Terms transfers statutory duties of the Host to the Operator. The Operator is not a "
            "joint controller unless expressly agreed in a separate written agreement. The Host "
            "is also solely responsible for the local stay fee (poplatek z pobytu) under Act No. "
            "565/1990 Coll. and the municipal ordinance: for collecting it, keeping the record "
            "book, reporting to the municipality and paying it. Where the Service calculates the "
            "fee or prepares a report, a register or a payment QR code, these are aids for the "
            "Host. The Operator does not file the report or pay the fee. The Host checks the "
            "figures before using them."
        ),
        "terms.s06_title": "6. Account registration and security",
        "terms.s06_body": (
            "The Host must provide accurate registration information and keep it current. Usernames and "
            "passwords are personal or assigned to authorised staff only. The Host is responsible for "
            "all activity under its Account, including actions by employees, contractors, and anyone "
            "who gains access through the Host's credentials or guest links. The Host must use strong "
            "passwords, enable and maintain two-factor authentication when the Service requires it "
            "(including mandatory authenticator-based 2FA on production deployments), safeguard "
            "recovery codes, limit access appropriately, and notify the Operator promptly if "
            "unauthorised access is suspected. The Operator may require password changes, additional "
            "verification, Cloudflare Turnstile, Bot Fight Mode challenges, or leaked-credential "
            "checks on login and guest PIN flows to prevent abuse."
        ),
        "terms.s07_title": "7. Acceptable use",
        "terms.s07_body": (
            "The Host shall not: (a) use the Service for unlawful purposes or submit false, misleading, "
            "or incomplete Guest Data; (b) attempt to gain unauthorised access to the Service, other "
            "accounts, or underlying systems; (c) interfere with or disrupt the Service, including by "
            "automated scraping, denial-of-service, or introducing malware; (d) reverse engineer, "
            "decompile, or create derivative works of the Service except where mandatory law permits; "
            "(e) resell, sublicense, or make the Service available to third parties except as permitted "
            "by the Host's own accommodation operations; (f) use the Service to harass, defame, or "
            "infringe third-party rights; (g) remove proprietary notices; or (h) use demo or test modes "
            "to submit real Guest Data to production police endpoints without proper configuration. "
            "Breach may result in immediate suspension under Section 19."
        ),
        "terms.s08_title": "8. Host obligations and legal compliance",
        "terms.s08_body": (
            "The Host warrants that it holds all licences, registrations, and permissions required to "
            "operate accommodation and to collect and process Guest Data. The Host must: take reasonable "
            "steps to ensure Guest identity and data accuracy, including any document check required by "
            "law or the Host's procedure; understand that configured automatic reporting may transmit "
            "complete records without waiting for an in-app verification step; obtain signatures where required; maintain "
            "paper or other legally required records alongside digital copies; meet reporting deadlines; "
            "present records at inspections; configure Legal Entities, properties, and UbyPort credentials "
            "correctly; and comply with GDPR transparency, retention, and security obligations toward "
            "Guests. The Host is solely liable for fines, claims, or enforcement actions arising from "
            "the Host's failure to comply with accommodation, immigration, or data protection law."
        ),
        "terms.s09_title": "9. Personal data and GDPR",
        "terms.s09_body": (
            "Guest Data is processed to operate the Service on the Host's instructions. The Host, as "
            "controller, determines purposes and means of processing vis-à-vis Guests and must provide "
            "lawful basis, privacy notices, and data subject rights responses. The Operator implements "
            "appropriate technical and organisational measures for the hosted environment but does not "
            "guarantee that the Host's use of the Service satisfies the Host's GDPR obligations. The "
            "Operator may access Guest Data only to provide the Service, ensure security, comply with "
            "law, or as otherwise instructed. The Host shall not instruct processing that violates "
            "applicable law. Details of subprocessors, cookies, retention, and security are described "
            "in these Terms and in the Privacy Policy at /privacy."
        ),
        "terms.s10_title": "10. UbyPort and police reporting",
        "terms.s10_body": (
            "10.1 The duty to report accommodated foreigners to the Police of the Czech Republic "
            "under Act No. 326/1999 Coll. is the Host's. The Service is a technical tool. Where "
            "reporting is enabled, the Service transmits records to UbyPort only on the Host's "
            "instruction, given through the property's reporting setting (manual, immediately "
            "when all declared forms are complete, or after a set delay) or by a send action in "
            "the Service. Each transmission is made with the Host's own UbyPort web-service "
            "access and in the Host's name. The Operator does not act as the Host's "
            "representative or agent toward the police and does not report anything in its own "
            "name. 10.2 The Operator does not guarantee that any submission will be received, "
            "accepted, validated, or deemed compliant by the Police of the Czech Republic, the "
            "Ministry of the Interior, or any authority. Outages, schema changes, credential "
            "issues, network failures, and manual review by authorities are outside the "
            "Operator's control. 10.3 The Host checks the result of every filing in the Service "
            "(status and the police receipt, Doručenka) and keeps proof of reporting. Demo, "
            "sandbox, or test data must not be relied upon as official police records. 10.4 If "
            "the Service shows that a filing was rejected, failed, or has an unknown outcome, or "
            "warns that a deadline is near, or if the Service or UbyPort's web service is "
            "unavailable, the Host files the affected guests itself within the statutory time "
            "limit (currently 3 working days from the start of accommodation), for example "
            "through the UbyPort web application with its own login. Instructions are in the "
            "Service's guide, section \"If UbyHost cannot file in time\". Before sending again "
            "from the Service, the Host checks in the UbyPort web application that the guest is "
            "not already reported, because a second filing counts as a duplicate. After filing "
            "by hand, the Host records this on the stay in the Service (\"I filed this stay by "
            "hand in UbyPort\"), so that the Service does not send those guests again. 10.5 "
            "Notices from the Service about filings are shown in the Service and sent to the "
            "Account e-mail. The Host keeps that e-mail address working and reads these notices."
        ),
        "terms.s10a_title": "10a. UbyPort access credentials",
        "terms.s10a_body": (
            "The Host authorises and mandates the Operator to store the UbyPort web-service user "
            "name and password that the Host enters for a property, and to use them solely to "
            "transmit the Host's reports to UbyPort and to test the connection when the Host "
            "asks. This authorisation and mandate covers only storing and using the credentials "
            "as described here; it does not make the Operator the Host's representative toward "
            "the police (§ 10.1). The Operator stores the password encrypted, does not show it "
            "in the Service, does not use it for any other purpose and does not give it to "
            "anyone except as required by law. The Host may change or delete the credentials in "
            "the Service at any time; reporting from the Service then stops until valid "
            "credentials are entered. The Host requests web-service credentials from the Police "
            "of the Czech Republic and keeps its own login to the UbyPort web application, so "
            "that it can file by hand. If the Host suspects that the credentials have been "
            "misused, it asks the police for new ones and tells the Operator. The Operator tells "
            "the Host without undue delay if it learns that stored credentials may have been "
            "exposed. The authorisation ends when the credentials are deleted or the Account is "
            "closed; the Operator then deletes them."
        ),
        "terms.s11_title": "11. Intellectual property",
        "terms.s11_body": (
            "The Service, including software, design, logos, documentation, and all related intellectual "
            "property rights, is and remains the exclusive property of the Operator and its licensors. "
            "No rights are granted except as expressly set out in these Terms. The Host retains ownership "
            "of Content it uploads, but grants the Operator a worldwide, non-exclusive, royalty-free "
            "licence to host, copy, transmit, display, and process Content solely to provide and improve "
            "the Service, comply with law, and enforce these Terms."
        ),
        "terms.s12_title": "12. Licence to use the Service",
        "terms.s12_body": (
            "Subject to these Terms and payment of applicable fees (if any), the Operator grants the "
            "Host a limited, non-exclusive, non-transferable, revocable licence to access and use the "
            "Service for the Host's internal accommodation operations during the subscription or "
            "authorised period. The licence does not permit use beyond the scope of the Host's own "
            "properties and staff. The Operator may update the Service; material reductions in core "
            "functionality will be communicated where reasonably practicable."
        ),
        "terms.s13_title": "13. Service availability and support",
        "terms.s13_body": (
            "The Service is provided on a best-effort basis. The Operator does not guarantee "
            "uninterrupted or error-free operation, specific uptime percentages, or response "
            "times unless agreed in a separate written SLA. Maintenance, upgrades, and emergency "
            "work may cause temporary unavailability; where possible, the Operator announces "
            "planned downtime in the Service in advance. The Operator is not liable for failures "
            "caused by third-party networks, hosting providers, UbyPort, internet connectivity, "
            "or force majeure. An outage of the Service, of UbyPort or of a provider does not "
            "extend the Host's statutory time limits; in that case the Host follows § 10.4. "
            "Support is provided through channels the Operator makes available from time to "
            "time; no support email is guaranteed unless published on the /legal page."
        ),
        "terms.s14_title": "14. Beta features and demo data",
        "terms.s14_body": (
            "The Service may include beta, preview, or experimental features identified as such. They "
            "are provided as-is and may be modified or withdrawn without notice. Demo or sample data "
            "loaded for training is fictitious or anonymised where possible and is configured not to "
            "trigger real police submissions; the Host must confirm environment settings before live "
            "use. The Host is responsible for distinguishing demo workspaces from production data."
        ),
        "terms.s15_title": "15. Fees and payment",
        "terms.s15_body": (
            "If fees apply to the Host's plan, they are due as stated at signup, in-app, or in a separate "
            "order form. Prices may change on notice for future billing periods. Unless mandatory law "
            "requires otherwise, fees are non-refundable once a billing period has started. Failure to "
            "pay may result in suspension or termination. Taxes (including VAT) are the Host's "
            "responsibility where applicable. If the Service is currently offered without charge, the "
            "Operator may introduce fees on reasonable notice; continued use after the effective date "
            "constitutes acceptance of the new pricing."
        ),
        "terms.s16_title": "16. Disclaimer of warranties",
        "terms.s16_body": (
            "To the maximum extent permitted by applicable law, the Service is provided \"as is\" and "
            "\"as available\" without warranties of any kind, whether express, implied, or statutory, "
            "including warranties of merchantability, fitness for a particular purpose, accuracy, "
            "non-infringement, or that the Service will meet the Host's requirements or regulatory "
            "outcomes. The Operator does not warrant that Guest Data will be preserved indefinitely, "
            "that exports will be accepted by authorities, or that the Service is free from vulnerabilities. "
            "Mandatory statutory rights of consumers (if applicable) remain unaffected."
        ),
        "terms.s17_title": "17. Limitation of liability",
        "terms.s17_body": (
            "17.1 The Operator is not liable for loss of profit, lost business opportunity or "
            "other indirect or consequential damage. 17.2 The Operator's total liability for all "
            "claims arising from the Service or these Terms in any calendar year is limited to "
            "the fees the Host paid to the Operator for the Service in the twelve (12) months "
            "before the claim, and to no less than CZK 10,000. 17.3 The Operator is not liable "
            "for fines or other consequences of a report that was late, missing or wrong, to the "
            "extent the Host did not check the result of the filing or did not file by hand "
            "under § 10.4 after the Service reported a problem or was unavailable. 17.4 "
            "Liability for damage caused intentionally or through gross negligence is never "
            "excluded or limited. Sections 17.1 to 17.3 also do not apply to harm to a person's "
            "natural rights (including life, health and privacy), or where the Host is a "
            "consumer or otherwise a weaker party, because Czech law does not allow such "
            "liability to be excluded or limited in advance (§ 2898 of Act No. 89/2012 Coll., "
            "Civil Code). They do not limit either party's liability to data subjects or "
            "supervisory authorities under the GDPR. 17.5 For business users the parties agree "
            "that these limits are a fair allocation of risk, taking into account the price of "
            "the Service and the Host's duty to check filings."
        ),
        "terms.s18_title": "18. Indemnification",
        "terms.s18_body": (
            "The Host shall indemnify, defend, and hold harmless the Operator, its contractors, and "
            "affiliates from and against all claims, damages, losses, fines, penalties, costs, and "
            "expenses (including reasonable legal fees) arising from: (a) Guest Data or Content submitted "
            "by the Host or Guests; (b) the Host's breach of these Terms or applicable law; (c) the "
            "Host's accommodation operations or regulatory non-compliance; (d) disputes between the Host "
            "and Guests; or (e) misuse of the Service under the Host's Account. The Operator may assume "
            "exclusive defence and control of any matter subject to indemnification; the Host will "
            "cooperate fully."
        ),
        "terms.s19_title": "19. Suspension and termination",
        "terms.s19_body": (
            "The Operator may suspend or terminate access immediately if the Host breaches these Terms, "
            "poses a security risk, fails to pay fees, or if required by law or a competent authority. "
            "The Operator may terminate for convenience on thirty (30) days' notice. The Host may stop "
            "using the Service at any time; export data beforehand where the Service provides export "
            "tools. Upon termination, the licence ends and the Operator may delete Account data after "
            "any applicable retention period, except where law requires longer storage. Provisions that "
            "by nature should survive (including Sections 11, 16–18, 22, and 24) survive termination."
        ),
        "terms.s20_title": "20. Data retention and export",
        "terms.s20_body": (
            "Retention periods for Guest Data follow the Host's legal obligations and in-app settings. "
            "The Host is responsible for timely export, archival, and deletion in line with GDPR and "
            "Czech accommodation law (including typical six-year house book retention). The Operator may "
            "retain backups for a limited period for disaster recovery and then purge them. The Operator "
            "is not obliged to maintain data indefinitely after termination. The Host should maintain "
            "independent backups of critical records."
        ),
        "terms.s21_title": "21. Subcontractors and subprocessors",
        "terms.s21_body": (
            "The Operator may use hosting providers, infrastructure vendors, and other subprocessors to "
            "deliver the Service, provided they are bound by confidentiality and data protection "
            "obligations consistent with these Terms. The Host authorises such subcontracting for "
            "processing Guest Data on the Host's instructions. The Operator remains responsible for "
            "subprocessors' performance to the extent required by GDPR Article 28. The current "
            "provider register, purposes, possible data and transfer notes are published at "
            "/subprocessors and supplemented by the Privacy Policy at /privacy."
        ),
        "terms.s22_title": "22. Changes to these Terms",
        "terms.s22_body": (
            "The Operator may amend these Terms to reflect legal, technical, or business changes. "
            "Material changes will be notified by posting the updated Terms at /terms and, where "
            "practicable, through the Service or Account email on file at least thirty (30) days before "
            "they take effect. The effective date will be shown at the top of the page. Continued use "
            "after the effective date constitutes acceptance. If the Host disagrees, it must stop using "
            "the Service before the effective date and export its data."
        ),
        "terms.s23_title": "23. Force majeure",
        "terms.s23_body": (
            "Neither party is liable for failure or delay due to events beyond reasonable control, "
            "including natural disasters, war, terrorism, labour disputes, government actions, epidemics, "
            "power or internet failures, or outages of UbyPort or third-party services, provided the "
            "affected party uses reasonable efforts to mitigate impact."
        ),
        "terms.s24_title": "24. Governing law and jurisdiction",
        "terms.s24_body": (
            "These Terms are governed by the laws of the Czech Republic, excluding conflict-of-law rules "
            "that would apply another jurisdiction. For business users, the parties irrevocably submit to "
            "the exclusive jurisdiction of the courts of the Czech Republic seated in Prague (Praha). "
            "If the Host is a consumer, mandatory consumer jurisdiction rules under EU and Czech law "
            "apply where they cannot be waived. The United Nations Convention on Contracts for the "
            "International Sale of Goods does not apply."
        ),
        "terms.s25_title": "25. General provisions",
        "terms.s25_body": (
            "These Terms, together with the /legal notice, the Data Processing Agreement at /dpa, the "
            "Privacy Policy at /privacy, and any order form expressly incorporated, constitute the "
            "entire agreement regarding the Service. If any "
            "provision is invalid, the remainder stays in effect and the invalid part is replaced by a "
            "valid provision closest to the intent. Failure to enforce a right is not a waiver. The Host "
            "may not assign these Terms without the Operator's consent; the Operator may assign in "
            "connection with a business transfer. Notices to the Host may be given electronically "
            "through the Service."
        ),
        "terms.s26_title": "26. No legal advice",
        "terms.s26_body": (
            "Information in the Service, documentation, or help content is for general operational "
            "guidance only. It does not constitute legal, immigration, tax, or data protection advice. "
            "The Host must obtain its own professional advice on house books, foreigner reporting, GDPR, "
            "and accommodation regulations. The Operator is not responsible for decisions the Host makes "
            "based on such materials."
        ),
        "terms.s27_title": "27. Contact",
        "terms.s27_body": (
            "Questions about these Terms should be directed to the Operator using contact details on the "
            "/legal page. For Guest Data subject requests, Guests must contact the Host as data controller."
        ),
    },
    "cs": {
        "terms.page_title": "Obchodní podmínky",
        "terms.page_lede": (
            "Smlouva mezi provozovatelem softwaru UbyHost a poskytovateli ubytování, kteří službu "
            "používají. Před použitím UbyHostu si je prosím pečlivě přečtěte."
        ),
        "terms.effective": "Účinnost od: %(date)s. Verze %(version)s.",
        "terms.operator_title": "Poskytovatel služby",
        "terms.footer_link": "Obchodní podmínky",
        "terms.footer_short": "Podmínky",
        "terms.cross_legal": "Právní informace (identita provozovatele)",
        "terms.review_title": "K těmto podmínkám",
        "terms.review_body": (
            "Tyto podmínky popisují smlouvu mezi vámi a provozovatelem UbyHostu a vycházejí z českého "
            "práva. Jde o obecné podmínky služby, nikoli o poradenství pro vaši konkrétní situaci."
        ),
        "legal.cross_terms": "Obchodní podmínky",
        "terms.s01_title": "1. Úvod a přijetí podmínek",
        "terms.s01_body": (
            "Tyto obchodní podmínky (dále jen „Podmínky“) upravují přístup k webové aplikaci UbyHost, "
            "souvisejícímu softwaru, dokumentaci a hostované infrastruktuře (společně „Služba“), kterou "
            "provozuje %(name)s, IČO %(ico)s, osoba samostatně výdělečně činná podle práva České "
            "republiky (dále jen „Provozovatel“). Vytvořením účtu, přihlášením nebo jiným používáním "
            "Služby potvrzujete vy (dále jen „Ubytovatel“), že jste si Podmínky a smlouvu o zpracování "
            "údajů na /dpa (pro Údaje hostů začleněnou odkazem) přečetli, rozumíte jim a souhlasíte "
            "s nimi. Pokud nesouhlasíte, Službu nepoužívejte. Pokud jednáte za právnickou "
            "osobu, prohlašujete, že jste k tomu oprávněni. Služba je určena především poskytovatelům "
            "ubytování a dalším podnikatelům; pokud jste spotřebitelem ve smyslu zákona č. 634/1992 Sb., "
            "ve znění pozdějších předpisů (včetně zákona č. 261/2021 Sb.), platí kogentní ochrana "
            "spotřebitele v rozsahu, v jakém ji nelze platně vyloučit."
        ),
        "terms.s02_title": "2. Vymezení pojmů",
        "terms.s02_body": (
            "„Ubytovatel“ je fyzická nebo právnická osoba, která se registruje a používá Službu pro "
            "správu ubytování. „Host“ je osoba, jejíž údaje Ubytovatel prostřednictvím Služby shromažďuje. "
            "„Údaje hostů“ jsou osobní a jiné údaje o hostech zadané nebo vytvořené ve Službě. "
            "„Právnická osoba“ je entita nastavená Ubytovatelem jako správce objektu nebo správce údajů hostů. "
            "„UbyPort“ je systém hlášení cizinců Policie ČR a související rozhraní. „Účet“ je "
            "registrovaný pracovní prostor Ubytovatele. „Obsah“ jsou data, texty, obrázky a soubory "
            "nahrávané Ubytovatelem nebo hosty."
        ),
        "terms.s03_title": "3. Identita poskytovatele",
        "terms.s03_body": (
            "Službu poskytuje %(name)s, IČO %(ico)s (Provozovatel). Provozovatel je dodavatelem softwaru "
            "a hostovaného prostředí. Ubytovatel pro každé ubytování nastavuje (a) správce/provozovatele "
            "ubytování jako praktický kontakt pro otázky k pobytu a (b) správce Údajů hostů. "
            "Provozovatel ubytování je výchozím správcem; jiný subjekt lze zvolit pouze tehdy, pokud "
            "skutečně určuje účely a prostředky zpracování a Ubytovatel je oprávněn jej zavázat. Pouhá "
            "změna názvu nebo kontaktu ve Službě odpovědnost správce nepřenáší. Nastavený správce "
            "odpovídá podle nařízení (EU) 2016/679 (GDPR) a českých prováděcích předpisů. Identita "
            "a kontakt Provozovatele jsou na /legal."
        ),
        "terms.s04_title": "4. Popis Služby",
        "terms.s04_body": (
            "UbyHost je software jako služba pro vedení domovní knihy, sběr údajů hostů webovými "
            "formuláři, správu pobytů a přípravu či odesílání hlášení směrem k UbyPortu. Funkce se mohou "
            "měnit, přidávat nebo odebírat dle uvážení Provozovatele. Služba může integrovat třetí strany "
            "(včetně státních systémů). Provozovatel neposkytuje ubytování, právní, daňové ani "
            "imigrační poradenství a nejedná jako zástupce Ubytovatele vůči úřadům, ledaže je to "
            "výslovně uvedeno."
        ),
        "terms.s05_title": "5. Role stran",
        "terms.s05_body": (
            "Ubytovatel výhradně odpovídá za plnění povinností poskytovatele ubytování podle "
            "českého práva, včetně zákona č. 326/1999 Sb. o pobytu cizinců, prováděcích "
            "předpisů, pravidel domovní knihy a povinností správce podle GDPR. Provozovatel "
            "poskytuje technickou infrastrukturu a zpracovává Údaje hostů na dokumentovaný pokyn "
            "Ubytovatele jako zpracovatel podle čl. 28 GDPR dle DPA na /dpa. Nic v těchto "
            "Podmínkách nepřenáší zákonné povinnosti Ubytovatele na Provozovatele. Společná "
            "správa údajů nastává jen při výslovné písemné dohodě. Ubytovatel dále výhradně "
            "odpovídá za místní poplatek z pobytu podle zákona č. 565/1990 Sb. a obecně závazné "
            "vyhlášky obce: za jeho vybrání, vedení evidenční knihy, ohlášení obci a odvod. "
            "Pokud Služba poplatek vypočítá nebo připraví hlášení, evidenci či QR kód pro "
            "platbu, jde o pomůcku pro Ubytovatele. Provozovatel hlášení nepodává a poplatek "
            "neodvádí. Ubytovatel údaje před použitím zkontroluje."
        ),
        "terms.s06_title": "6. Registrace účtu a bezpečnost",
        "terms.s06_body": (
            "Ubytovatel uvede pravdivé registrační údaje a udržuje je aktuální. Přihlašovací údaje jsou "
            "osobní nebo přidělené oprávněným osobám. Ubytovatel odpovídá za veškerou činnost pod svým "
            "Účtem, včetně zaměstnanců, dodavatelů a kohokoli, kdo získá přístup přes jeho údaje nebo "
            "odkazy pro hosty. Používejte silná hesla, zapněte a udržujte dvoufázové ověření, pokud "
            "Služba vyžaduje (včetně povinného 2FA přes autentizační aplikaci v produkci), chraňte "
            "obnovovací kódy, omezte přístup a při podezření na zneužití Provozovatele neprodleně "
            "informujte. Provozovatel může vyžadovat změnu hesla, další ověření, Cloudflare "
            "Turnstile, Bot Fight Mode nebo kontrolu uniklých přihlašovacích údajů při přihlášení "
            "a u PIN hostů proti zneužití."
        ),
        "terms.s07_title": "7. Přípustné použití",
        "terms.s07_body": (
            "Ubytovatel nesmí: (a) používat Službu protiprávně nebo zadávat nepravdivé či neúplné Údaje "
            "hostů; (b) se neoprávněně pokoušet o přístup ke Službě, jiným účtům nebo systémům; "
            "(c) narušovat Službu (scraping, DoS, malware); (d) reverzně inženýrovat Službu, ledaže to "
            "vyžaduje kogentní zákon; (e) přeprodávat nebo sublicencovat Službu mimo vlastní provoz "
            "ubytování; (f) porušovat práva třetích osob; (g) odstraňovat označení práv; (h) používat "
            "demo režim pro odeslání skutečných údajů na produkční policejní koncové body bez správné "
            "konfigurace. Porušení může vést k okamžitému pozastavení podle čl. 19."
        ),
        "terms.s08_title": "8. Povinnosti Ubytovatele a právní soulad",
        "terms.s08_body": (
            "Ubytovatel prohlašuje, že má veškerá oprávnění k provozu ubytování a ke zpracování Údajů "
            "hostů. Musí přijmout přiměřené kroky ke správnosti totožnosti a údajů včetně kontroly "
            "dokladu vyžadované zákonem nebo postupem ubytovatele; bere na vědomí, že nastavené "
            "automatické hlášení může odeslat kompletní záznam bez čekání na ověření v aplikaci; "
            "musí zajistit podpisy a vést "
            "listinnou či jinak povinnou evidenci, dodržet lhůty hlášení, předložit záznamy při kontrole, "
            "správně nastavit Právnické osoby, ubytování a přístupy k UbyPortu a plnit transparentnost, "
            "uchovávání a bezpečnost podle GDPR. Za pokuty, nároky a správní postupy z nedodržení "
            "ubytovatelských, imigračních nebo GDPR povinností odpovídá výhradně Ubytovatel."
        ),
        "terms.s09_title": "9. Osobní údaje a GDPR",
        "terms.s09_body": (
            "Údaje hostů se zpracovávají pro provoz Služby na pokyn Ubytovatele. Ubytovatel jako správce "
            "určuje účely a prostředky vůči hostům a zajišťuje právní titul, informace a práva subjektů. "
            "Provozovatel uplatňuje přiměřená technická a organizační opatření, ale nezaručuje, že "
            "použití Služby samo o sobě splní všechny GDPR povinnosti Ubytovatele. K Údajům hostů "
            "přistupuje jen pro poskytování Služby, bezpečnost, zákon nebo dle pokynu. Ubytovatel "
            "neinstruuje protiprávní zpracování. Subzpracovatelé, cookies, doba uchování a bezpečnost "
            "jsou popsány v těchto Podmínkách a v Zásadách ochrany osobních údajů na /privacy."
        ),
        "terms.s10_title": "10. UbyPort a hlášení policii",
        "terms.s10_body": (
            "10.1 Povinnost hlásit ubytování cizinců Policii České republiky podle zákona č. "
            "326/1999 Sb. má Ubytovatel. Služba je technický nástroj. Je-li hlášení zapnuto, "
            "Služba odesílá záznamy do UbyPortu pouze na pokyn Ubytovatele, daný nastavením "
            "hlášení u ubytování (ručně, okamžitě po dokončení všech nahlášených formulářů, nebo "
            "po nastavené prodlevě) nebo odesláním ve Službě. Každé odeslání probíhá s vlastními "
            "přístupovými údaji Ubytovatele k webové službě UbyPort a jménem Ubytovatele. "
            "Provozovatel není vůči policii zástupcem ani zmocněncem Ubytovatele a nic nehlásí "
            "vlastním jménem. 10.2 Provozovatel nezaručuje, že hlášení Policie ČR, Ministerstvo "
            "vnitra ČR ani jiný úřad přijme, ověří nebo uzná za řádné. Výpadky, změny schémat, "
            "problémy s přístupovými údaji, výpadky sítě a ruční kontrola úřady jsou mimo "
            "kontrolu Provozovatele. 10.3 Ubytovatel u každého hlášení ve Službě zkontroluje "
            "výsledek (stav a doručenku Policie ČR) a uchovává doklad o splnění povinnosti. "
            "Demo, testovací nebo vzorová data nelze považovat za oficiální policejní záznamy. "
            "10.4 Pokud Služba ukáže, že hlášení bylo odmítnuto, selhalo nebo má neznámý "
            "výsledek, nebo upozorní na blížící se lhůtu, nebo pokud Služba či webová služba "
            "UbyPort nejsou dostupné, podá Ubytovatel hlášení dotčených hostů sám v zákonné "
            "lhůtě (nyní 3 pracovní dny od začátku ubytování), například ve webové aplikaci "
            "UbyPort se svým přihlášením. Návod je v průvodci ve Službě, v části „Když UbyHost "
            "nestihne hlášení podat“. Před dalším odesláním ze Služby Ubytovatel ve webové "
            "aplikaci UbyPort ověří, že host již nahlášen není, protože druhé odeslání se počítá "
            "jako duplicita. Po ručním podání to Ubytovatel zaznamená u pobytu ve Službě („Tento "
            "pobyt jsem nahlásil(a) ručně v UbyPortu“), aby Služba tyto hosty znovu neodeslala. "
            "10.5 Upozornění Služby k hlášení se zobrazují ve Službě a posílají na e-mail Účtu. "
            "Ubytovatel udržuje tuto adresu funkční a upozornění čte."
        ),
        "terms.s10a_title": "10a. Přístupové údaje k UbyPortu",
        "terms.s10a_body": (
            "Ubytovatel zmocňuje Provozovatele, aby uchovával přihlašovací jméno a heslo k "
            "webové službě UbyPort, které Ubytovatel u ubytování zadá, a používal je výhradně k "
            "odesílání hlášení Ubytovatele do UbyPortu a k ověření spojení na žádost "
            "Ubytovatele. Toto zmocnění se týká jen uchování a použití přístupových údajů podle "
            "tohoto článku; Provozovatel se jím nestává zástupcem Ubytovatele vůči policii (čl. "
            "10.1). Provozovatel heslo uchovává šifrované, ve Službě ho nezobrazuje, nepoužívá "
            "ho k jinému účelu a nikomu ho nepředává, ledaže to vyžaduje zákon. Ubytovatel může "
            "údaje ve Službě kdykoli změnit nebo smazat; hlášení ze Služby se pak zastaví, dokud "
            "nezadá platné údaje. Ubytovatel si přístupové údaje k webové službě vyžádá od "
            "Policie ČR a ponechá si vlastní přihlášení do webové aplikace UbyPort, aby mohl "
            "hlásit ručně. Při podezření na zneužití údajů požádá Ubytovatel policii o nové a "
            "informuje Provozovatele. Provozovatel bez zbytečného odkladu informuje Ubytovatele, "
            "zjistí-li, že uložené údaje mohly být vyzrazeny. Zmocnění končí smazáním údajů nebo "
            "zrušením Účtu; Provozovatel je poté smaže."
        ),
        "terms.s11_title": "11. Duševní vlastnictví",
        "terms.s11_body": (
            "Služba včetně softwaru, designu, log, dokumentace a souvisejících práv duševního vlastnictví "
            "zůstává výhradním vlastnictvím Provozovatele a jeho licencorů. Práva se udělují jen dle "
            "těchto Podmínek. Ubytovatel vlastní nahraný Obsah, ale uděluje Provozovateli nevýhradní "
            "celosvětovou bezúplatnou licenci k hostování, kopírování, přenosu, zobrazení a zpracování "
            "Obsahu výhradně pro poskytování a zlepšování Služby, plnění zákona a vymáhání Podmínek."
        ),
        "terms.s12_title": "12. Licence k používání Služby",
        "terms.s12_body": (
            "Za podmínky těchto Podmínek a úhrady případných poplatků Provozovatel uděluje Ubytovateli "
            "omezenou, nevýhradní, nepřevoditelnou a odvolatelnou licenci k přístupu a používání Služby "
            "pro vlastní provoz ubytování po dobu předplatného či autorizace. Licence nepřesahuje vlastní "
            "ubytování a oprávněné osoby. Provozovatel může Službu aktualizovat; podstatné omezení "
            "základní funkčnosti oznámí, pokud je to rozumně možné."
        ),
        "terms.s13_title": "13. Dostupnost služby a podpora",
        "terms.s13_body": (
            "Služba je poskytována podle možností Provozovatele (best effort). Provozovatel "
            "nezaručuje nepřetržitý provoz bez chyb, konkrétní dostupnost v procentech ani "
            "reakční doby, ledaže je dohodnuto písemně. Údržba, aktualizace a havárie mohou "
            "způsobit výpadky; plánovanou odstávku Provozovatel oznámí ve Službě předem, je-li "
            "to možné. Provozovatel neodpovídá za selhání třetích stran, UbyPortu, sítě či vyšší "
            "moci. Výpadek Služby, UbyPortu nebo dodavatele neprodlužuje zákonné lhůty "
            "Ubytovatele; v takovém případě postupuje Ubytovatel podle čl. 10.4. Podpora probíhá "
            "kanály, které Provozovatel zpřístupní; e-mail podpory není zaručen, pokud není "
            "uveden na /legal."
        ),
        "terms.s14_title": "14. Beta funkce a demo data",
        "terms.s14_body": (
            "Služba může obsahovat beta nebo experimentální funkce označené jako takové. Poskytují se "
            "tak, jak jsou, a mohou být změněny či ukončeny bez předchozího upozornění. Demo data pro "
            "školení jsou smyšlená nebo anonymizovaná a nemají spouštět skutečná policejní hlášení; "
            "Ubytovatel musí před ostrým provozem ověřit nastavení prostředí. Rozlišení demo a produkce "
            "je na Ubytovateli."
        ),
        "terms.s15_title": "15. Poplatky a platby",
        "terms.s15_body": (
            "Pokud se účtují poplatky, splatí se dle údajů při registraci, v aplikaci nebo v objednávce. "
            "Ceny se mohou pro budoucí období změnit s předchozím oznámením. Poplatky jsou nevratné po "
            "zahájení fakturačního období, ledaže kogentní zákon stanoví jinak. Nezaplacení může vést k "
            "pozastavení nebo ukončení. Daně (včetně DPH) nese Ubytovatel. Je-li Služba nyní bezplatná, "
            "Provozovatel může zavést poplatky s přiměřeným předstihem; další používání po účinnosti "
            "znamená souhlas."
        ),
        "terms.s16_title": "16. Vyloučení záruk",
        "terms.s16_body": (
            "V maximálním rozsahu povoleném zákonem je Služba poskytována „tak, jak je“ a „jak je "
            "dostupná“ bez výslovných, odvozených ani zákonných záruk, včetně záruk prodejnosti, "
            "vhodnosti pro určitý účel, přesnosti, neporušení práv třetích osob či že Služba splní "
            "požadavky Ubytovatele nebo regulatorní výsledek. Provozovatel nezaručuje trvalé uchování "
            "Údajů hostů, přijetí exportů úřady ani bezchybnost. Kogentní práva spotřebitele (je-li "
            "uplatnitelné) zůstávají nedotčena."
        ),
        "terms.s17_title": "17. Omezení odpovědnosti",
        "terms.s17_body": (
            "17.1 Provozovatel neodpovídá za ušlý zisk, ztrátu obchodní příležitosti ani jinou "
            "nepřímou či následnou škodu. 17.2 Celková odpovědnost Provozovatele za všechny "
            "nároky ze Služby nebo z těchto Podmínek v jednom kalendářním roce je omezena na "
            "úplatu, kterou Ubytovatel Provozovateli za Službu zaplatil za dvanáct (12) měsíců "
            "před vznikem nároku, nejméně však na 10 000 Kč. 17.3 Provozovatel neodpovídá za "
            "pokuty ani jiné následky opožděného, chybějícího nebo chybného hlášení v rozsahu, v "
            "jakém Ubytovatel nezkontroloval výsledek hlášení nebo nepodal hlášení ručně podle "
            "čl. 10.4 poté, co Služba ohlásila problém nebo nebyla dostupná. 17.4 Odpovědnost za "
            "škodu způsobenou úmyslně nebo z hrubé nedbalosti se nikdy nevylučuje ani neomezuje. "
            "Články 17.1 až 17.3 se nepoužijí ani na újmu na přirozených právech člověka (včetně "
            "života, zdraví a soukromí), ani je-li Ubytovatel spotřebitelem nebo jinak slabší "
            "stranou, protože české právo neumožňuje takovou odpovědnost předem vyloučit ani "
            "omezit (§ 2898 zákona č. 89/2012 Sb., občanský zákoník). Neomezují ani odpovědnost "
            "kterékoli strany vůči subjektům údajů a dozorovým úřadům podle GDPR. 17.5 U "
            "podnikatelů strany souhlasí, že jde o přiměřené rozdělení rizika s ohledem na cenu "
            "Služby a povinnost Ubytovatele kontrolovat hlášení."
        ),
        "terms.s18_title": "18. Náhrada škody (indemnifikace)",
        "terms.s18_body": (
            "Ubytovatel odškodní, bude bránit a chránit Provozovatele, jeho dodavatele a spřízněné osoby "
            "proti veškerým nárokům, škodám, ztrátám, pokutám, sankcím, nákladům a výdajům (včetně "
            "přiměřených právních poplatků) vzniklým z: (a) Údajů hostů nebo Obsahu; (b) porušení "
            "těchto Podmínek nebo práva Ubytovatelem; (c) provozu ubytování nebo regulatorního "
            "nesouladu; (d) sporů mezi Ubytovatelem a hosty; (e) zneužití Služby pod Účtem Ubytovatele. "
            "Provozovatel může převzít výhradní obhajobu; Ubytovatel bude spolupracovat."
        ),
        "terms.s19_title": "19. Pozastavení a ukončení",
        "terms.s19_body": (
            "Provozovatel může přístup okamžitě pozastavit nebo ukončit při porušení Podmínek, "
            "bezpečnostním riziku, nezaplacení nebo na základě zákona či úřadu. Z vlastní vůle může "
            "ukončit s třicetidenním (30) předstihem. Ubytovatel může přestat Službu používat kdykoli; "
            "data si předem exportuje. Po ukončení licence končí a Provozovatel může data smazat po "
            "zákonné či smluvní lhůtě uchovávání. Ustanovení, která mají přetrvat (čl. 11, 16–18, 22 "
            "a 24), zůstávají v platnosti."
        ),
        "terms.s20_title": "20. Uchovávání a export dat",
        "terms.s20_body": (
            "Lhůty uchovávání Údajů hostů vycházejí z právních povinností Ubytovatele a nastavení "
            "v aplikaci. Ubytovatel včas exportuje, archivuje a maže dle GDPR a ubytovatelského práva "
            "(typicky 6 let domovní knihy). Provozovatel může krátkodobě uchovávat zálohy pro obnovu a "
            "poté je smazat. Po ukončení není povinen data uchovávat neomezeně. Ubytovatel si má vést "
            "vlastní zálohy kritických záznamů."
        ),
        "terms.s21_title": "21. Subdodavatelé a subzpracovatelé",
        "terms.s21_body": (
            "Provozovatel může využívat hosting, infrastrukturu a další subzpracovatele za podmínky "
            "mlčenlivosti a ochrany údajů v souladu s těmito Podmínkami. Ubytovatel takové "
            "subdodávání pro zpracování Údajů hostů na svůj pokyn autorizuje. Provozovatel odpovídá za "
            "další zpracovatele v rozsahu čl. 28 GDPR. Aktuální seznam poskytovatelů, účelů, možných "
            "údajů a informací o předání je na /subprocessors a doplňují jej Zásady na /privacy."
        ),
        "terms.s22_title": "22. Změny Podmínek",
        "terms.s22_body": (
            "Provozovatel může Podmínky měnit z právních, technických nebo obchodních důvodů. Podstatné "
            "změny oznámí zveřejněním na /terms a, je-li to možné, ve Službě nebo na e-mail účtu nejméně "
            "třicet (30) dní před účinností. Datum účinnosti je v záhlaví stránky. Další používání po "
            "účinnosti znamená souhlas. Nesouhlasíte-li, před účinností přestaňte Službu používat a data "
            "exportujte."
        ),
        "terms.s23_title": "23. Vyšší moc",
        "terms.s23_body": (
            "Žádná strana neodpovídá za neplnění nebo zpoždění způsobené událostmi mimo rozumnou "
            "kontrolu, včetně přírodních katastrof, války, terorismu, pracovních sporů, zásahů státu, "
            "epidemií, výpadků energie či internetu nebo výpadků UbyPortu a služeb třetích stran, pokud "
            "dotčená strana přiměřeně zmírňuje dopady."
        ),
        "terms.s24_title": "24. Rozhodné právo a příslušnost",
        "terms.s24_body": (
            "Podmínky se řídí právem České republiky s vyloučením kolizních norem vedoucích k jiné "
            "jurisdikci. U podnikatelů se strany podřizují výlučné příslušnosti soudů České republiky se "
            "sídlem v Praze. Je-li Ubytovatel spotřebitelem, platí kogentní pravidla příslušnosti podle "
            "práva EU a ČR, pokud je nelze vyloučit. Úmluva OSN o smlouvách o mezinárodní koupi zboží se "
            "nepoužije."
        ),
        "terms.s25_title": "25. Obecná ustanovení",
        "terms.s25_body": (
            "Tyto Podmínky spolu s informacemi na /legal, DPA na /dpa, Zásadami na /privacy a výslovně "
            "začleněnými objednávkami tvoří úplnou dohodu o Službě. Neplatnost části neovlivní zbytek; "
            "neplatné ustanovení nahradí "
            "účinek co nejbližší záměru. Neuplatnění práva není vzdáním. Ubytovatel nesmí postoupit "
            "Podmínky bez souhlasu Provozovatele; Provozovatel může při převodu podnikání. Oznámení "
            "Ubytovateli lze doručit elektronicky ve Službě."
        ),
        "terms.s26_title": "26. Neposkytování právního poradenství",
        "terms.s26_body": (
            "Informace ve Službě, dokumentaci nebo nápovědě slouží jen pro obecný provoz. Nepředstavují "
            "právní, imigrační, daňové ani GDPR poradenství. Ubytovatel si musí opatřit vlastní odborné "
            "rady k domovní knize, hlášení cizinců a ubytovatelským předpisům. Provozovatel neodpovídá "
            "za rozhodnutí Ubytovatele podle těchto materiálů."
        ),
        "terms.s27_title": "27. Kontakt",
        "terms.s27_body": (
            "Dotazy k Podmínkám směřujte na Provozovatele dle údajů na /legal. Žádosti subjektů údajů "
            "hostů řeší Ubytovatel jako správce."
        ),
    },
}
