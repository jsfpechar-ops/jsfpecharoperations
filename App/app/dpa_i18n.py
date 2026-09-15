"""Data Processing Agreement strings (EN/CS) — GDPR Art. 28 — merged into host_i18n."""
from __future__ import annotations

from typing import Dict

DPA_STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "dpa.page_title": "Data Processing Agreement",
        "dpa.page_lede": (
            "GDPR Article 28 agreement between you (the Host, as data controller) and %(name)s "
            "(the Operator, as data processor) for Guest Data processed through UbyHost. "
            "This DPA is incorporated into the Terms of Service; using the Service constitutes "
            "acceptance unless a separate signed agreement expressly replaces it."
        ),
        "dpa.effective": "Effective date: 15 September 2026. Version 1.2.",
        "dpa.operator_title": "Processor (service provider)",
        "dpa.footer_link": "Data Processing Agreement",
        "dpa.footer_short": "DPA",
        "dpa.cross_legal": "Legal notice",
        "dpa.cross_terms": "Terms of Service",
        "dpa.cross_privacy": "Privacy Policy",
        "dpa.incorporation_note": (
            "Enterprise customers may request a countersigned copy for their records; the online "
            "version at /dpa remains the operative text unless a written amendment is executed."
        ),
        "dpa.review_title": "Professional review",
        "dpa.review_body": (
            "This DPA follows common SaaS practice under GDPR and Czech law. It does not replace "
            "your own privacy programme, records of processing, or guest notices. Seek qualified "
            "counsel for high-risk processing or group-wide compliance programmes."
        ),
        "legal.dpa_title": "Guest data processing (DPA)",
        "legal.dpa_body": (
            "When you use the hosted service, the Operator processes guest personal data on your "
            "instructions under a GDPR Article 28 Data Processing Agreement at /dpa. It is "
            "automatically incorporated into the Terms — review it before processing live guest data."
        ),
        "legal.cross_dpa": "Data Processing Agreement",
        "terms.cross_dpa": "Data Processing Agreement",
        "privacy.cross_dpa": "Data Processing Agreement",
        "dpa.s01_title": "1. Binding effect and incorporation",
        "dpa.s01_body": (
            "This Data Processing Agreement (\"DPA\") forms part of the contract between the Host "
            "(\"Controller\") and %(name)s, IČO %(ico)s (\"Processor\"), for the UbyHost service "
            "(\"Service\") described in the Terms of Service at /terms. By creating an account, "
            "logging in, or using the Service, the Controller agrees to this DPA on behalf of itself "
            "and any legal entities it configures in the Service. If the Controller signs a separate "
            "written data processing agreement with the Processor that expressly supersedes this DPA, "
            "that signed agreement prevails to the extent of conflict."
        ),
        "dpa.s02_title": "2. Definitions",
        "dpa.s02_body": (
            "Capitalised terms not defined here have the meaning in the Terms or GDPR. \"Guest Data\" "
            "means personal data relating to Guests processed by the Processor on behalf of the "
            "Controller through the Service. \"Personal Data Breach\" has the meaning in GDPR "
            "Article 4(12). \"Subprocessor\" means a third party engaged by the Processor to process "
            "Guest Data. \"Applicable Data Protection Law\" means GDPR, Act No. 110/2019 Coll., and "
            "other laws binding the Controller or Processor."
        ),
        "dpa.s03_title": "3. Roles of the parties",
        "dpa.s03_body": (
            "For Guest Data, the Controller is the data controller and determines the purposes and "
            "means of processing vis-à-vis Guests. The Processor processes Guest Data only on "
            "documented instructions from the Controller (including configuration in the Service, "
            "submissions to UbyPort when enabled, and support requests) and does not process Guest "
            "Data for its own marketing or unrelated purposes. The Processor is an independent "
            "contractor, not an agent of the Controller for accommodation or regulatory filings."
        ),
        "dpa.s04_title": "4. Subject matter, duration, and nature of processing",
        "dpa.s04_body": (
            "Subject matter: provision of hosted software for house books, guest forms, stay management, "
            "and optional police reporting integrations. Duration: for the term of the Controller's "
            "use of the Service and until Guest Data is deleted or returned per Section 15. Nature "
            "of processing: collection, storage, organisation, retrieval, transmission, encryption "
            "of credentials, display to authorised Controller users, formatting for export, and "
            "transmission toward UbyPort or related endpoints when the Controller enables such features."
        ),
        "dpa.s05_title": "5. Details of processing (Annex summary)",
        "dpa.s05_body": (
            "Categories of data subjects: Guests, and occasionally third parties named on travel "
            "documents. Types of personal data: identity and contact details, nationality, dates "
            "of birth and stay, travel document numbers and types, addresses, signatures, "
            "accommodation metadata, and optional passport photographs or PDFs uploaded for "
            "verification. Special categories: the Service may process document images that could "
            "reveal ethnic origin or health only where the Controller instructs such upload and has "
            "a lawful basis; the Controller is responsible for necessity and proportionality. "
            "Controller personnel data is outside this DPA except where listed in the Privacy Policy."
        ),
        "dpa.s06_title": "6. Controller obligations",
        "dpa.s06_body": (
            "The Controller shall: (a) comply with Applicable Data Protection Law; (b) provide lawful "
            "instructions and ensure a valid legal basis for processing; (c) maintain accurate guest "
            "privacy notices naming the Controller entity and contact; (d) not instruct processing "
            "that violates law; (e) ensure Host Users are authorised and trained; (f) respond to data "
            "subject requests from Guests unless the Processor assists as stated below; (g) notify the "
            "Processor without undue delay if a Guest objects to processing that affects the Service."
        ),
        "dpa.s07_title": "7. Processor obligations",
        "dpa.s07_body": (
            "The Processor shall: process Guest Data only on documented instructions unless required "
            "by EU or Member State law (in which case the Processor informs the Controller unless "
            "prohibited); ensure persons authorised to process Guest Data are bound by confidentiality; "
            "implement appropriate technical and organisational measures per Section 10; engage "
            "Subprocessors per Section 11; assist the Controller as set out in Sections 12–14; and "
            "make available information necessary to demonstrate compliance with Article 28 obligations."
        ),
        "dpa.s08_title": "8. Documented instructions",
        "dpa.s08_body": (
            "Instructions include: this DPA, the Terms, the Privacy Policy, the Controller's in-app "
            "configuration (properties, legal entities, reporting settings), actions taken through "
            "the user interface, and written requests to operator contact on /legal. If the Processor "
            "believes an instruction infringes Applicable Data Protection Law, it will inform the "
            "Controller without undue delay. The Processor may suspend processing of the infringing "
            "instruction where legally required or where continuing would expose the Processor to "
            "substantial risk, after reasonable notice where practicable."
        ),
        "dpa.s09_title": "9. Confidentiality",
        "dpa.s09_body": (
            "The Processor ensures that persons processing Guest Data are subject to confidentiality "
            "obligations (contractual or statutory). The Processor will not disclose Guest Data to "
            "third parties except as permitted in this DPA, the Privacy Policy, or with the Controller's "
            "instructions, or as required by law with notice to the Controller where allowed."
        ),
        "dpa.s10_title": "10. Security measures (Article 32)",
        "dpa.s10_body": (
            "Taking into account the state of the art, costs, and risks, the Processor implements "
            "measures including: access controls and authentication for Host accounts; mandatory "
            "two-factor authentication (TOTP) in production; encryption of sensitive integration "
            "credentials and TOTP secrets at rest; HTTPS for data in transit including HSTS on the "
            "production hostname; Cloudflare Turnstile where configured, plus Bot Fight Mode, "
            "leaked-credential mitigation, and client-side script monitoring on the production zone; "
            "logical separation of customer data; rate limiting on authentication; "
            "backup and recovery procedures (including optional off-site copies to Google Drive and "
            "Amazon S3 when configured by the Operator); restriction of production access to authorised "
            "personnel; and security updates to dependencies. The Controller is responsible for password "
            "strength, device security, recovery codes, and sharing guest links only with intended "
            "recipients. A summary is also in the Privacy Policy."
        ),
        "dpa.s11_title": "11. Subprocessors",
        "dpa.s11_body": (
            "The Controller provides general written authorisation for the Processor to engage "
            "Subprocessors listed or described in the Privacy Policy at /privacy (including "
            "infrastructure hosting such as AWS Lightsail, Render.com, Cloudflare (including Turnstile, "
            "Bot Fight Mode, leaked-credential checks, client-side security, and HSTS), "
            "Google Drive and Amazon S3 for configured backups, and, where used, DNS/CDN or e-mail "
            "providers). The Processor will impose data protection terms on Subprocessors substantially "
            "similar to this DPA. The Processor remains liable to the Controller for Subprocessor "
            "performance to the extent required by Article 28(4). The Processor will inform the "
            "Controller of intended changes to Subprocessors (e.g. by updating the Privacy Policy) and "
            "allow the Controller to object on reasonable data-protection grounds; if unresolved, the "
            "Controller may terminate the affected Service as per the Terms."
        ),
        "dpa.s12_title": "12. Assistance with data subject rights",
        "dpa.s12_body": (
            "Taking into account the nature of processing, the Processor assists the Controller by "
            "appropriate technical measures to fulfil obligations to respond to Guest requests "
            "(access, rectification, erasure, restriction, portability, objection) where feasible and "
            "only on the Controller's instruction. Guests must contact the Controller as named in "
            "the guest privacy notice. The Processor may charge reasonable fees for manifestly "
            "excessive or repetitive requests unless prohibited by law."
        ),
        "dpa.s13_title": "13. DPIA and prior consultation",
        "dpa.s13_body": (
            "Where required under Articles 35–36 GDPR, the Controller conducts data protection impact "
            "assessments and prior consultations. The Processor provides available information about "
            "the Service and security measures upon reasonable written request to assist the Controller."
        ),
        "dpa.s14_title": "14. Personal data breach",
        "dpa.s14_body": (
            "The Processor notifies the Controller without undue delay after becoming aware of a "
            "Personal Data Breach affecting Guest Data, with information available to allow the "
            "Controller to meet Articles 33–34 obligations. Notification may be by e-mail to the "
            "account contact or in-app where practicable. The Processor will cooperate with reasonable "
            "remediation and documentation requests."
        ),
        "dpa.s15_title": "15. Return and deletion of Guest Data",
        "dpa.s15_body": (
            "Upon termination of the Service or on the Controller's documented request, the Processor "
            "will delete or return Guest Data within a reasonable period, except where storage is "
            "required by law or retained in encrypted backups for a limited disaster-recovery window "
            "before automatic purging. Export tools in the Service should be used before termination. "
            "Anonymised or aggregated data that cannot identify individuals may be retained."
        ),
        "dpa.s16_title": "16. Audits and information",
        "dpa.s16_body": (
            "The Processor makes available information necessary to demonstrate compliance with "
            "Article 28 and allows for audits no more than once per twelve (12) months on thirty "
            "(30) days' notice, during business hours, without disrupting other customers, subject "
            "to confidentiality and security restrictions. The Controller bears its own audit costs "
            "unless an audit reveals material non-compliance attributable to the Processor. The "
            "Processor may satisfy audit requests through current certifications or third-party reports "
            "where they cover the Service."
        ),
        "dpa.s17_title": "17. International transfers",
        "dpa.s17_body": (
            "The Processor processes data primarily in the EEA. Where a Subprocessor transfers Guest "
            "Data outside the EEA, the Processor ensures appropriate safeguards under Chapter V GDPR "
            "(including Standard Contractual Clauses or adequacy decisions). Details are in the "
            "Privacy Policy. The Controller authorises such transfers as part of this DPA unless "
            "the Controller objects in writing on valid legal grounds."
        ),
        "dpa.s18_title": "18. Liability",
        "dpa.s18_body": (
            "Liability between the parties for Guest Data processing is governed by the Terms of "
            "Service (including limitations and indemnities). Each party remains liable to data "
            "subjects and supervisory authorities under Applicable Data Protection Law for its own "
            "violations. Nothing in this DPA limits either party's liability where limitation is "
            "not permitted by law."
        ),
        "dpa.s19_title": "19. Processor contact for data protection",
        "dpa.s19_body": (
            "Data protection queries and instructions regarding Guest Data processing should be sent "
            "to %(name)s using contact details on /legal (e-mail if published). The Controller "
            "should include account identification and a clear description of the requested action."
        ),
        "dpa.s20_title": "20. Changes to this DPA",
        "dpa.s20_body": (
            "The Processor may update this DPA to reflect legal, technical, or Subprocessor changes. "
            "Material changes will be posted at /dpa with an updated effective date and, where "
            "practicable, notified at least thirty (30) days before taking effect. Continued use of "
            "the Service after the effective date constitutes acceptance where permitted by law. "
            "The Controller may terminate if it reasonably objects to a material change that "
            "materially weakens protection and no alternative is offered."
        ),
        "dpa.s21_title": "21. Order of precedence",
        "dpa.s21_body": (
            "For Guest Data processing: this DPA prevails over conflicting Terms provisions. The "
            "Privacy Policy describes broader processing (including Controller account data) and "
            "does not limit Processor obligations here. Guest-facing notices are the Controller's "
            "responsibility. Mandatory law prevails over all contractual documents."
        ),
        "dpa.s22_title": "22. Governing law",
        "dpa.s22_body": (
            "This DPA is governed by the laws of the Czech Republic. Courts in Prague have exclusive "
            "jurisdiction for business users as in the Terms, subject to mandatory consumer or data "
            "subject rules that cannot be waived."
        ),
        "dpa.s23_title": "23. Severability",
        "dpa.s23_body": (
            "If a provision of this DPA is invalid, the remainder remains effective. The parties will "
            "replace the invalid provision with a valid one that best reflects the original intent."
        ),
        "dpa.s24_title": "24. Entire agreement on processing",
        "dpa.s24_body": (
            "Together with the Terms and Privacy Policy, this DPA constitutes the complete agreement "
            "on the Processor's processing of Guest Data, superseding prior oral or written "
            "understandings on that subject unless a later signed writing expressly amends it."
        ),
    },
    "cs": {
        "dpa.page_title": "Smlouva o zpracování osobních údajů",
        "dpa.page_lede": (
            "Dohoda podle čl. 28 GDPR mezi vámi (Ubytovatel jako správce) a %(name)s "
            "(Provozovatel jako zpracovatel) o údajích hostů v UbyHostu. DPA je součástí obchodních "
            "podmínek; používáním Služby ji přijímáte, pokud ji nepřepíše samostatná písemná smlouva."
        ),
        "dpa.effective": "Účinnost od: 15. září 2026. Verze 1.2.",
        "dpa.operator_title": "Zpracovatel (poskytovatel služby)",
        "dpa.footer_link": "Smlouva o zpracování údajů (DPA)",
        "dpa.footer_short": "DPA",
        "dpa.cross_legal": "Právní informace",
        "dpa.cross_terms": "Obchodní podmínky",
        "dpa.cross_privacy": "Zásady ochrany osobních údajů",
        "dpa.incorporation_note": (
            "Podnikoví zákazníci mohou požádat o opatřený stejnopis pro evidenci; online verze na "
            "/dpa zůstává účinná, pokud není uzavřena písemná změna."
        ),
        "dpa.review_title": "Odborná kontrola",
        "dpa.review_body": (
            "DPA odpovídá běžné praxi SaaS podle GDPR a českého práva. Nenahrazuje vaše záznamy o "
            "činnostech zpracování ani informace pro hosty. U rizikového zpracování využijte advokáta."
        ),
        "legal.dpa_title": "Zpracování údajů hostů (DPA)",
        "legal.dpa_body": (
            "Při používání hostované služby zpracovává údaje hostů na váš pokyn smlouva podle čl. 28 "
            "GDPR. Je automaticky součástí smlouvy — před ostrým provozem si ji přečtěte na /dpa."
        ),
        "legal.cross_dpa": "Smlouva o zpracování údajů (DPA)",
        "terms.cross_dpa": "Smlouva o zpracování údajů (DPA)",
        "privacy.cross_dpa": "Smlouva o zpracování údajů (DPA)",
        "dpa.s01_title": "1. Závaznost a začlenění",
        "dpa.s01_body": (
            "Tato smlouva o zpracování osobních údajů (\"DPA\") je součástí smlouvy mezi Ubytovatelem "
            "(\"Správce\") a %(name)s, IČO %(ico)s (\"Zpracovatel\"), o službě UbyHost (\"Služba\") "
            "dle podmínek na /terms. Vytvořením účtu, přihlášením nebo používáním Služby Správce "
            "přijímá DPA za sebe i za nastavené právnické osoby. Samostatná písemná DPA mezi stranami "
            "má přednost při rozporu."
        ),
        "dpa.s02_title": "2. Definice",
        "dpa.s02_body": (
            "Velká písmena bez definice mají význam z Podmínek nebo GDPR. \"Údaje hostů\" jsou osobní "
            "údaje hostů zpracované Zpracovatelem pro Správce ve Službě. \"Porušení zabezpečení\" dle "
            "čl. 4 odst. 12 GDPR. \"Subzpracovatel\" je třetí strana pověřená Zpracovatelem. "
            "\"Použitelné právo\" znamená GDPR, zákon č. 110/2019 Sb. a další závazné předpisy."
        ),
        "dpa.s03_title": "3. Role stran",
        "dpa.s03_body": (
            "U údajů hostů je Správce správcem a určuje účely a prostředky vůči hostům. Zpracovatel "
            "zpracovává údaje jen na dokumentovaný pokyn Správce (nastavení ve Službě, UbyPort, podpora) "
            "a ne pro vlastní marketing. Zpracovatel je samostatný dodavatel, ne zástupce Správce "
            "u úřadů."
        ),
        "dpa.s04_title": "4. Předmět, doba a povaha zpracování",
        "dpa.s04_body": (
            "Předmět: hostovaný software pro domovní knihu, formuláře hostů, pobyty a volitelné hlášení "
            "policii. Doba: po dobu používání Služby a do smazání/vrácení dle čl. 15. Povaha: "
            "shromažďování, uložení, uspořádání, vyhledávání, přenos, šifrování přihlašovacích údajů, "
            "zobrazení oprávněným uživatelům, export a přenos do UbyPortu při zapnutí."
        ),
        "dpa.s05_title": "5. Podrobnosti zpracování (shrnutí přílohy)",
        "dpa.s05_body": (
            "Subjekty: hosté a osoby na dokladech. Kategorie údajů: identita, kontakt, státní příslušnost, "
            "data pobytu, cestovní doklady, adresy, podpisy, metadata ubytování, volitelné fotografie/PDF "
            "pasu. Zvláštní kategorie: snímky dokladů mohou odhalit původ či zdraví jen pokud Správce "
            "nahrání pokyne a má právní základ; Správce odpovídá za nezbytnost. Údaje personálu "
            "Správce spadají do Zásad ochrany osobních údajů."
        ),
        "dpa.s06_title": "6. Povinnosti správce",
        "dpa.s06_body": (
            "Správce: dodržuje právo; dává zákonné pokyny a právní titul; udržuje informace pro hosty; "
            "neinstruuje protiprávní zpracování; zajišťuje oprávnění uživatelů; vyřizuje žádosti hostů; "
            "bez zbytečného odkladu informuje Zpracovatele o námitkách hostů dotýkajících se Služby."
        ),
        "dpa.s07_title": "7. Povinnosti zpracovatele",
        "dpa.s07_body": (
            "Zpracovatel: zpracovává jen na pokyn; zajišťuje mlčenlivost; uplatňuje opatření dle čl. 10; "
            "pověřuje subzpracovatele dle čl. 11; pomáhá dle čl. 12–14; poskytuje informace pro "
            "doložení souladu s čl. 28."
        ),
        "dpa.s08_title": "8. Dokumentované pokyny",
        "dpa.s08_body": (
            "Pokyny zahrnují: DPA, Podmínky, Zásady, nastavení ve Službě, akce v UI a písemné žádosti "
            "na kontakt na /legal. Při protiprávním pokynu Zpracovatel informuje Správce a může "
            "zpracování pozastavit, kde to vyžaduje zákon nebo hrozí podstatné riziko."
        ),
        "dpa.s09_title": "9. Mlčenlivost",
        "dpa.s09_body": (
            "Zpracovatel zajišťuje mlčenlivost pověřených osob. Údaje hostů neposkytne třetím stranám "
            "kromě DPA, Zásad, pokynu Správce nebo zákonné povinnosti s oznámením Správci, kde je to "
            "možné."
        ),
        "dpa.s10_title": "10. Bezpečnostní opatření (čl. 32)",
        "dpa.s10_body": (
            "Zpracovatel uplatňuje přiměřená opatření: řízení přístupu, povinné dvoufázové ověření "
            "(TOTP) v produkci, šifrování citlivých údajů a TOTP, HTTPS včetně HSTS na produkční "
            "doméně, Cloudflare Turnstile při nastavení a v produkční zóně také Bot Fight Mode, "
            "kontrolu uniklých přihlašovacích údajů a monitoring skriptů v prohlížeči, oddělení dat "
            "zákazníků, rate limiting přihlášení, zálohy včetně volitelných "
            "off-site kopií (Google Drive, Amazon S3) a omezený přístup do produkce. Správce "
            "odpovídá za hesla, zařízení, obnovovací kódy a sdílení odkazů hostům. Shrnutí je v Zásadách."
        ),
        "dpa.s11_title": "11. Subzpracovatelé",
        "dpa.s11_body": (
            "Správce uděluje obecné povolení k subzpracovatelům uvedeným v Zásadách na /privacy "
            "(včetně AWS Lightsail, Render.com, Cloudflare včetně Turnstile, Bot Fight Mode, kontroly "
            "uniklých údajů, klientské bezpečnosti a HSTS, Google Drive a Amazon S3 "
            "pro nastavené zálohy a případně DNS/CDN či e-mail). Zpracovatel ukládá obdobné povinnosti. "
            "Odpovídá za subzpracovatele dle čl. 28 odst. 4. O změnách informuje (např. aktualizací "
            "Zásad); Správce může vznést oprávněnou námitku a při neřešení ukončit Službu dle Podmínek."
        ),
        "dpa.s12_title": "12. Pomoc s právy subjektů",
        "dpa.s12_body": (
            "Zpracovatel přiměřeně pomůže technicky na pokyn Správce s žádostmi hostů (přístup, oprava, "
            "výmaz, omezení, přenositelnost, námitka), kde je to možné. Hosté kontaktují Správce z "
            "informace u ubytování. Za zjevně nepřiměřené žádosti může být úhrada nákladů, pokud to "
            "zákon dovolí."
        ),
        "dpa.s13_title": "13. DPIA a předchozí konzultace",
        "dpa.s13_body": (
            "Správce provádí DPIA a konzultace dle čl. 35–36. Zpracovatel na rozumnou písemnou žádost "
            "poskytne dostupné informace o Službě a bezpečnosti."
        ),
        "dpa.s14_title": "14. Porušení zabezpečení údajů",
        "dpa.s14_body": (
            "Zpracovatel bez zbytečného odkladu oznámí Správci porušení týkající se údajů hostů s "
            "informacemi pro plnění čl. 33–34. Oznámení e-mailem nebo ve Službě. Rozumná spolupráce "
            "při nápravě."
        ),
        "dpa.s15_title": "15. Vrácení a výmaz údajů hostů",
        "dpa.s15_body": (
            "Po ukončení nebo na pokyn Správce Zpracovatel smaže nebo vrátí údaje v přiměřené lhůtě, "
            "kromě zákonné povinnosti a omezených záloh před vymazáním. Před ukončením použijte export. "
            "Anonymizovaná agregovaná data mohou zůstat."
        ),
        "dpa.s16_title": "16. Audity a informace",
        "dpa.s16_body": (
            "Zpracovatel poskytne informace pro doložení čl. 28 a umožní audit nejvýše jednou za "
            "12 měsíců po 30 dnech, v pracovní době, bez narušení ostatních zákazníků, s mlčenlivostí. "
            "Náklady nese Správce, pokud audit neprokáže podstatné porušení Zpracovatelem. Lze nahradit "
            "certifikacemi či zprávami třetích stran."
        ),
        "dpa.s17_title": "17. Přeshraniční přenosy",
        "dpa.s17_body": (
            "Zpracování primárně v EHP. Při přenosu mimo EHP Zpracovatel zajistí záruky dle kapitoly V "
            "(SCC, rozhodnutí o přiměřenosti). Podrobnosti v Zásadách. Správce přenosy autorizuje, "
            "pokud písemně nevznesl oprávněnou námitku."
        ),
        "dpa.s18_title": "18. Odpovědnost",
        "dpa.s18_body": (
            "Odpovědnost mezi stranami u údajů hostů řídí Obchodní podmínky včetně limitů a "
            "indemnifikace. Každá strana odpovídá subjektům a dozorovým úřadům za vlastní porušení. "
            "Omezení neplatí, kde zákon nedovoluje."
        ),
        "dpa.s19_title": "19. Kontakt pro ochranu údajů",
        "dpa.s19_body": (
            "Dotazy a pokyny ke zpracování údajů hostů směřujte na %(name)s dle /legal (e-mail, pokud "
            "je uveden). Uveďte identifikaci účtu a popis požadavku."
        ),
        "dpa.s20_title": "20. Změny DPA",
        "dpa.s20_body": (
            "Zpracovatel může DPA měnit. Podstatné změny na /dpa s datem účinnosti a pokud možno "
            "30 dní předem. Pokračující používání znamená přijetí, kde zákon dovolí. Správce může "
            "ukončit při oprávněné námitce na podstatné zhoršení ochrany."
        ),
        "dpa.s21_title": "21. Pořadí dokumentů",
        "dpa.s21_body": (
            "U údajů hostů má DPA přednost před rozpornými ustanoveními Podmínek. Zásady popisují "
            "širší zpracování včetně účtu Správce. Informace pro hosty zajišťuje Správce. Kogentní "
            "právo má přednost."
        ),
        "dpa.s22_title": "22. Rozhodné právo",
        "dpa.s22_body": (
            "DPA se řídí právem České republiky. Příslušnost soudů v Praze pro podnikatele jako v "
            "Podmínkách, s výhradou kogentních pravidel."
        ),
        "dpa.s23_title": "23. Oddělitelnost",
        "dpa.s23_body": (
            "Neplatné ustanovení neovlivní zbytek. Strany ho nahradí ustanovením co nejbližším účelu."
        ),
        "dpa.s24_title": "24. Úplná dohoda o zpracování",
        "dpa.s24_body": (
            "Spolu s Podmínkami a Zásadami tvoří DPA úplnou dohodu o zpracování údajů hostů "
            "Zpracovatelem, pokud ji nepřepíše pozdější písemná změna."
        ),
    },
}
