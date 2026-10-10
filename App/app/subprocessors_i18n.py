"""Public subprocessor register strings (EN/CS)."""
from __future__ import annotations

from typing import Dict


SUBPROCESSOR_STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "subprocessors.page_title": "Subprocessor register",
        "subprocessors.page_lede": (
            "The service providers that may process personal data for UbyHost, what they do, "
            "and when they are used. This register forms part of the Data Processing Agreement."
        ),
        "subprocessors.effective": "Effective date: 4 October 2026. Version 1.2.",
        "subprocessors.controller_note_title": "Who appoints these providers",
        "subprocessors.controller_note": (
            "For Guest Data, the accommodation provider or alternate controller configured for the "
            "property is the Controller. The UbyHost Operator is its Processor and appoints the "
            "providers below as Subprocessors. The property's operating manager remains the practical "
            "contact for questions about the stay, but changing that contact does not by itself change "
            "who is legally the Controller."
        ),
        "subprocessors.scope_title": "Current and conditional providers",
        "subprocessors.scope_body": (
            "A provider marked conditional processes data only when the relevant feature is enabled. "
            "Enabled services, account regions, and contractual transfer mechanisms are documented "
            "for the supported deployment paths."
        ),
        "subprocessors.table_provider": "Subprocessor",
        "subprocessors.table_purpose": "Purpose",
        "subprocessors.table_data": "Data",
        "subprocessors.table_location": "Location",
        "subprocessors.table_safeguard": "Transfer safeguard",
        # WP09: rows from 04_legal_positions.md section 5 (owner's decision).
        # Backup rows must not call the off-site copies encrypted until OPS-2
        # ships (LD-4, tests/test_legal_contents.py).
        "subprocessors.aws_lightsail_provider": "Amazon Web Services EMEA SARL (AWS Lightsail)",
        "subprocessors.aws_lightsail_purpose": "Application hosting and database.",
        "subprocessors.aws_lightsail_data": "All app data, including Guest Data.",
        "subprocessors.aws_lightsail_location": "EU, Frankfurt (eu-central-1).",
        "subprocessors.aws_lightsail_safeguard": (
            "AWS GDPR Data Processing Addendum in the AWS Service Terms, Standard Contractual "
            "Clauses."
        ),
        "subprocessors.aws_ses_provider": "Amazon Web Services EMEA SARL (Amazon SES)",
        "subprocessors.aws_ses_purpose": "Sending e-mail.",
        "subprocessors.aws_ses_data": "Recipient address, e-mail content.",
        "subprocessors.aws_ses_location": "eu-central-1 (Frankfurt).",
        "subprocessors.aws_ses_safeguard": "Same as AWS Lightsail.",
        "subprocessors.aws_s3_provider": "Amazon Web Services EMEA SARL (Amazon S3)",
        "subprocessors.aws_s3_purpose": "Off-site backups, later file storage.",
        "subprocessors.aws_s3_data": "Backup archives of all app data, including Guest Data.",
        "subprocessors.aws_s3_location": "eu-central-1 (Frankfurt).",
        "subprocessors.aws_s3_safeguard": "Same as AWS Lightsail.",
        "subprocessors.cloudflare_provider": "Cloudflare, Inc.",
        "subprocessors.cloudflare_purpose": "Turnstile bot protection; optional CDN and proxy.",
        "subprocessors.cloudflare_data": "IP address, browser signals, request metadata.",
        "subprocessors.cloudflare_location": "Global network, US company.",
        "subprocessors.cloudflare_safeguard": (
            "Cloudflare DPA, EU Standard Contractual Clauses, EU-US Data Privacy Framework."
        ),
        "subprocessors.posthog_provider": "PostHog, Inc. (PostHog Cloud EU)",
        "subprocessors.posthog_purpose": (
            "Website statistics on public pages, and host-account product measurement for the operator."
        ),
        "subprocessors.posthog_data": (
            "Public page views and the three click events; for a host account, e-mail, workspace name, "
            "UTM labels, sign-up source and funnel stage. No Guest Data. No advertising click "
            "identifiers."
        ),
        "subprocessors.posthog_location": "EU, Frankfurt. Used only while the operator enables it.",
        "subprocessors.posthog_safeguard": "PostHog DPA.",
        "subprocessors.render_provider": "Render",
        "subprocessors.render_purpose": "Demo hosting.",
        "subprocessors.render_data": "Demo and test data plus technical logs.",
        "subprocessors.render_location": (
            "Conditional; not part of the production Guest Data path."
        ),
        "subprocessors.render_safeguard": (
            "Provider DPA and lawful GDPR Chapter V safeguards where required."
        ),
        "subprocessors.google_provider": "Google Drive (Google)",
        "subprocessors.google_purpose": "Optional off-site production backups.",
        "subprocessors.google_data": (
            "Backup archives that may contain account, property, stay and Guest Data."
        ),
        "subprocessors.google_location": (
            "Conditional; used only when the Operator configures the documented backup job."
        ),
        
        "subprocessors.ttlock_provider": "Hangzhou Sciener Intelligent Control Technology Co., Ltd. (TTLock)",
        "subprocessors.ttlock_purpose": "Only if used: door codes. Creating, changing and deleting timed passcodes on the host's TTLock locks, for properties where the host switched door codes on.",
        "subprocessors.ttlock_data": "Lock ID, the code, its validity times and a reference number. No guest names or contact details.",
        "subprocessors.ttlock_location": "EU API endpoint (euapi.ttlock.com); company based in China.",
        "subprocessors.ttlock_safeguard": "EU Standard Contractual Clauses (2021/914, processor to processor), being concluded with TTLock; until signed, door codes run only on the operator's own properties. Data limited as stated.",
        "subprocessors.google_safeguard": (
            "Provider DPA and lawful GDPR Chapter V safeguards where required."
        ),
        "subprocessors.recipients_title": "Recipients that are not subprocessors",
        "subprocessors.recipient_google_ads": (
            "Google Ireland Ltd. (Google Ads conversion measurement, independent controller, only "
            "with consent)"
        ),
        "subprocessors.recipient_meta_ads": (
            "Meta Platforms Ireland Ltd. (Facebook and Instagram conversion measurement, joint "
            "controller for collection and sending, then independent controller, only with consent)"
        ),
        "subprocessors.recipient_police": (
            "Policie ČR, UbyPort (statutory reporting on the host's behalf)"
        ),
        "subprocessors.recipient_municipality": (
            "The municipality (stay-fee reports, if the host uses that feature)"
        ),
        "subprocessors.change_title": "Changes and objections",
        "subprocessors.change_body": (
            "The Operator will publish intended material changes here and, where practicable, notify "
            "Controller account contacts at least 30 days before a new Subprocessor handles live Guest "
            "Data. Controllers may object on reasonable data-protection grounds during that period. "
            "If the concern cannot be resolved, the Controller may stop using the affected feature or "
            "terminate as provided in the Terms and DPA."
        ),
        "subprocessors.accuracy_title": "Keeping this register current",
        "subprocessors.accuracy_body": (
            "This register describes the supported deployment paths and is kept aligned with the "
            "Operator's actual production accounts, regions, contracts and retention settings."
        ),
        "subprocessors.footer_short": "Subprocessors",
        "subprocessors.footer_link": "Subprocessor register",
    },
    "cs": {
        "subprocessors.page_title": "Seznam dalších zpracovatelů",
        "subprocessors.page_lede": (
            "Poskytovatelé, kteří mohou pro UbyHost zpracovávat osobní údaje, účel jejich zapojení "
            "a podmínky použití. Tento seznam je součástí zpracovatelské smlouvy."
        ),
        "subprocessors.effective": "Účinnost od: 4. října 2026. Verze 1.2.",
        "subprocessors.controller_note_title": "Kdo tyto poskytovatele zapojuje",
        "subprocessors.controller_note": (
            "Správcem údajů hostů je ubytovatel nebo alternativní správce nastavený pro dané "
            "ubytování. Provozovatel UbyHostu je jeho zpracovatelem a zapojuje níže uvedené další "
            "zpracovatele. Provozní správce ubytování zůstává praktickým kontaktem pro otázky k pobytu; "
            "změna kontaktní osoby však sama o sobě nemění, kdo je právně správcem."
        ),
        "subprocessors.scope_title": "Současní a podmínění poskytovatelé",
        "subprocessors.scope_body": (
            "Podmíněný poskytovatel zpracovává údaje jen při zapnutí příslušné funkce. Zapnuté "
            "služby, regiony účtů a smluvní mechanismy předání jsou popsané pro podporované "
            "způsoby nasazení."
        ),
        "subprocessors.table_provider": "Další zpracovatel",
        "subprocessors.table_purpose": "Účel",
        "subprocessors.table_data": "Údaje",
        "subprocessors.table_location": "Umístění",
        "subprocessors.table_safeguard": "Záruky při předání",
        "subprocessors.aws_lightsail_provider": "Amazon Web Services EMEA SARL (AWS Lightsail)",
        "subprocessors.aws_lightsail_purpose": "Hosting aplikace a databáze.",
        "subprocessors.aws_lightsail_data": "Všechna data aplikace včetně údajů hostů.",
        "subprocessors.aws_lightsail_location": "EU, Frankfurt (eu-central-1).",
        "subprocessors.aws_lightsail_safeguard": (
            "Dodatek AWS o zpracování údajů podle GDPR v AWS Service Terms, standardní smluvní "
            "doložky."
        ),
        "subprocessors.aws_ses_provider": "Amazon Web Services EMEA SARL (Amazon SES)",
        "subprocessors.aws_ses_purpose": "Odesílání e-mailů.",
        "subprocessors.aws_ses_data": "Adresa příjemce, obsah e-mailu.",
        "subprocessors.aws_ses_location": "eu-central-1 (Frankfurt).",
        "subprocessors.aws_ses_safeguard": "Stejně jako u AWS Lightsail.",
        "subprocessors.aws_s3_provider": "Amazon Web Services EMEA SARL (Amazon S3)",
        "subprocessors.aws_s3_purpose": "Zálohy mimo server, později ukládání souborů.",
        "subprocessors.aws_s3_data": "Záložní archivy všech dat aplikace včetně údajů hostů.",
        "subprocessors.aws_s3_location": "eu-central-1 (Frankfurt).",
        "subprocessors.aws_s3_safeguard": "Stejně jako u AWS Lightsail.",
        "subprocessors.cloudflare_provider": "Cloudflare, Inc.",
        "subprocessors.cloudflare_purpose": "Ochrana proti botům Turnstile; volitelně CDN a proxy.",
        "subprocessors.cloudflare_data": "IP adresa, signály prohlížeče, metadata požadavků.",
        "subprocessors.cloudflare_location": "Globální síť, americká společnost.",
        "subprocessors.cloudflare_safeguard": (
            "DPA Cloudflare, standardní smluvní doložky EU, rámec EU-US Data Privacy Framework."
        ),
        "subprocessors.posthog_provider": "PostHog, Inc. (PostHog Cloud EU)",
        "subprocessors.posthog_purpose": (
            "Statistiky návštěvnosti na veřejných stránkách a produktové měření účtu hostitele pro "
            "provozovatele."
        ),
        "subprocessors.posthog_data": (
            "Zobrazení veřejných stránek a tři události kliknutí; pro účet hostitele e-mail, název "
            "pracovního prostoru, štítky UTM, zdroj registrace a fáze funnelu. Žádné údaje hostů. "
            "Žádné identifikátory reklamních kliknutí."
        ),
        "subprocessors.posthog_location": "EU, Frankfurt. Používá se, jen pokud jej provozovatel zapne.",
        "subprocessors.posthog_safeguard": "DPA PostHog.",
        "subprocessors.render_provider": "Render",
        "subprocessors.render_purpose": "Ukázkový provoz.",
        "subprocessors.render_data": "Ukázková a testovací data a technické logy.",
        "subprocessors.render_location": (
            "Podmíněné použití; není součástí produkčního zpracování údajů hostů."
        ),
        "subprocessors.render_safeguard": (
            "DPA poskytovatele a zákonné záruky kapitoly V GDPR, jsou-li nutné."
        ),
        "subprocessors.google_provider": "Google Drive (Google)",
        "subprocessors.google_purpose": "Volitelné zálohy produkce mimo server.",
        "subprocessors.google_data": (
            "Záložní archivy, které mohou obsahovat údaje účtů, ubytování, pobytů a hostů."
        ),
        "subprocessors.google_location": (
            "Podmíněné použití pouze po nastavení dokumentované zálohovací úlohy Provozovatelem."
        ),
        "subprocessors.ttlock_provider": "Hangzhou Sciener Intelligent Control Technology Co., Ltd. (TTLock)",
        "subprocessors.ttlock_purpose": "Jen při použití: kódy ke dveřím. Vytváření, změna a mazání časově omezených kódů na zámcích TTLock hostitele, u ubytování, kde hostitel kódy zapnul.",
        "subprocessors.ttlock_data": "ID zámku, kód, doba jeho platnosti a referenční číslo. Žádná jména ani kontakty hostů.",
        "subprocessors.ttlock_location": "Rozhraní API v EU (euapi.ttlock.com); společnost se sídlem v Číně.",
        "subprocessors.ttlock_safeguard": "Standardní smluvní doložky EU (2021/914, zpracovatel zpracovateli), uzavírají se s TTLock; do podpisu běží kódy ke dveřím jen na vlastních ubytováních provozovatele. Rozsah údajů omezen, jak je uvedeno.",
        "subprocessors.google_safeguard": (
            "DPA poskytovatele a zákonné záruky kapitoly V GDPR, jsou-li nutné."
        ),
        "subprocessors.recipients_title": "Příjemci, kteří nejsou dalšími zpracovateli",
        "subprocessors.recipient_google_ads": (
            "Google Ireland Ltd. (měření konverzí Google Ads, samostatný správce, jen se souhlasem)"
        ),
        "subprocessors.recipient_meta_ads": (
            "Meta Platforms Ireland Ltd. (měření konverzí z Facebooku a Instagramu, společný "
            "správce pro shromáždění a odeslání, poté samostatný správce, jen se souhlasem)"
        ),
        "subprocessors.recipient_police": (
            "Policie ČR, UbyPort (zákonné hlášení jménem ubytovatele)"
        ),
        "subprocessors.recipient_municipality": (
            "Obec (hlášení k poplatku z pobytu, pokud ubytovatel tuto funkci používá)"
        ),
        "subprocessors.change_title": "Změny a námitky",
        "subprocessors.change_body": (
            "Provozovatel zde zveřejní zamýšlené podstatné změny a, je-li to prakticky možné, oznámí "
            "je kontaktům Správce nejméně 30 dní před tím, než nový další zpracovatel začne zpracovávat "
            "živé údaje hostů. Správce může v této době vznést odůvodněnou námitku z hlediska ochrany "
            "údajů. Nelze-li ji vyřešit, může přestat používat dotčenou funkci nebo smlouvu ukončit."
        ),
        "subprocessors.accuracy_title": "Aktuálnost seznamu",
        "subprocessors.accuracy_body": (
            "Seznam popisuje podporované způsoby nasazení a je průběžně sladěný se skutečnými "
            "produkčními účty, regiony, smlouvami a dobami uchování Provozovatele."
        ),
        "subprocessors.footer_short": "Další zpracovatelé",
        "subprocessors.footer_link": "Seznam dalších zpracovatelů",
    },
}
