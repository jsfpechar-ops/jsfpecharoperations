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
        "subprocessors.effective": "Effective date: 19 September 2026. Version 1.0.",
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
        "subprocessors.table_provider": "Provider",
        "subprocessors.table_purpose": "Purpose",
        "subprocessors.table_data": "Potential data",
        "subprocessors.table_location": "Location / transfer note",
        "subprocessors.aws_provider": "Amazon Web Services (AWS)",
        "subprocessors.aws_purpose": (
            "Production hosting on Lightsail; transactional e-mail through SES when enabled; "
            "optional encrypted S3 backups."
        ),
        "subprocessors.aws_data": (
            "Host accounts, property and stay data, Guest Data, encrypted integration credentials, "
            "technical logs; e-mail addresses and message content for SES."
        ),
        "subprocessors.aws_location": (
            "Production is configured for the EU (Frankfurt/eu-central-1). Provider support and "
            "security operations may involve international access subject to the provider DPA and "
            "lawful GDPR Chapter V safeguards where required."
        ),
        "subprocessors.cloudflare_provider": "Cloudflare",
        "subprocessors.cloudflare_purpose": (
            "DNS, CDN/proxy, TLS and edge security, including Turnstile and managed challenges."
        ),
        "subprocessors.cloudflare_data": (
            "IP address, request metadata, security signals, and content transiting the proxy as "
            "necessary to deliver and protect the Service."
        ),
        "subprocessors.cloudflare_location": (
            "Global network. Transfers outside the EEA are covered by the provider's applicable "
            "DPA and lawful safeguards such as adequacy mechanisms or Standard Contractual Clauses."
        ),
        "subprocessors.render_provider": "Render",
        "subprocessors.render_purpose": "Demo hosting.",
        "subprocessors.render_data": "Demo and test data plus technical logs.",
        "subprocessors.render_location": (
            "Conditional; not part of the production Guest Data path."
        ),
        "subprocessors.google_provider": "Google Drive (Google)",
        "subprocessors.google_purpose": "Optional encrypted off-site production backups.",
        "subprocessors.google_data": (
            "Encrypted backup archives that may contain account, property, stay and Guest Data."
        ),
        "subprocessors.google_location": (
            "Conditional; used only when the Operator configures the documented backup job. "
            "Provider DPA and lawful GDPR Chapter V safeguards apply where required."
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
        "subprocessors.effective": "Účinnost od: 19. září 2026. Verze 1.0.",
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
        "subprocessors.table_provider": "Poskytovatel",
        "subprocessors.table_purpose": "Účel",
        "subprocessors.table_data": "Možné údaje",
        "subprocessors.table_location": "Umístění / předání",
        "subprocessors.aws_provider": "Amazon Web Services (AWS)",
        "subprocessors.aws_purpose": (
            "Produkční hosting Lightsail; transakční e-mail přes SES po zapnutí; volitelné "
            "šifrované zálohy S3."
        ),
        "subprocessors.aws_data": (
            "Účty ubytovatelů, údaje o ubytování a pobytech, údaje hostů, šifrované integrační "
            "přihlašovací údaje a technické logy; u SES e-mailové adresy a obsah zpráv."
        ),
        "subprocessors.aws_location": (
            "Produkce je nastavena v EU (Frankfurt/eu-central-1). Podpora a bezpečnostní provoz "
            "poskytovatele mohou zahrnovat mezinárodní přístup podle jeho DPA a zákonných záruk "
            "kapitoly V GDPR, jsou-li nutné."
        ),
        "subprocessors.cloudflare_provider": "Cloudflare",
        "subprocessors.cloudflare_purpose": (
            "DNS, CDN/proxy, TLS a ochrana na hraně sítě včetně Turnstile a řízených výzev."
        ),
        "subprocessors.cloudflare_data": (
            "IP adresa, metadata požadavku, bezpečnostní signály a obsah procházející proxy v rozsahu "
            "nutném pro doručení a ochranu Služby."
        ),
        "subprocessors.cloudflare_location": (
            "Globální síť. Předání mimo EHP se řídí příslušnou DPA poskytovatele a zákonnými zárukami, "
            "například rozhodnutím o odpovídající ochraně nebo standardními smluvními doložkami."
        ),
        "subprocessors.render_provider": "Render",
        "subprocessors.render_purpose": "Ukázkový provoz.",
        "subprocessors.render_data": "Ukázková a testovací data a technické logy.",
        "subprocessors.render_location": (
            "Podmíněné použití; není součástí produkční cesty údajů hostů."
        ),
        "subprocessors.google_provider": "Google Drive (Google)",
        "subprocessors.google_purpose": "Volitelné šifrované zálohy produkce mimo server.",
        "subprocessors.google_data": (
            "Šifrované záložní archivy, které mohou obsahovat účty, ubytování, pobyty a údaje hostů."
        ),
        "subprocessors.google_location": (
            "Podmíněné použití pouze po nastavení dokumentované zálohovací úlohy Provozovatelem. "
            "Použije se DPA poskytovatele a zákonné záruky kapitoly V GDPR, jsou-li nutné."
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
