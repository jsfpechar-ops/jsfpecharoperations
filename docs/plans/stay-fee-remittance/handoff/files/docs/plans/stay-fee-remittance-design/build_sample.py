"""Regenerate the single Invoice Companion sample PDF with fictional data."""
from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[3] / "App"
sys.path.insert(0, str(APP_DIR))

from app import stay_fee_remittance_pdf


def sample_report() -> dict:
    return {
        "payer_name": "Josef Novák (demo)",
        "payer_seat": "Ukázková 1, 130 00 Praha 3",
        "payer_ico": "00000000",
        "payer_contact": "demo@example.test",
        "vs": "1234567890",
        "recipient_name": "Městská část Praha 3",
        "recipient_address": "Úřad městské části – Odbor ekonomický, oddělení poplatků\n"
                             "Havlíčkovo náměstí 700/9, Praha 3",
        "recipient_contact": "Tel.: 222 116 333 · podatelna@praha3.cz · č. účtu 19-2000781379/0800",
        "payee": "MČ Praha 3",
        "instruction": "Hlášení posílejte datovou schránkou (eqkbt8g), poštou na adresu úřadu, "
                       "e-mailem na podatelna@praha3.cz – ale pouze s připojeným elektronickým "
                       "podpisem – nebo osobně do podatelny na Havlíčkově náměstí 700/9, nejpozději "
                       "do 15 dnů po skončení měsíce.",
        "cadence": "monthly",
        "period_start": "2026-08-01",
        "period_end": "2026-08-31",
        "issued_on": "2026-09-12",
        "rows": [
            {"property_name": "Apartmán Vinohrady", "property_address": "Slezská 12, 130 00 Praha 3",
             "liable_nights": 58, "rate_czk": 50, "amount_czk": 2900},
            {"property_name": "Studio Žižkov", "property_address": "Seifertova 40, 130 00 Praha 3",
             "liable_nights": 25, "rate_czk": 50, "amount_czk": 1250},
        ],
        "liable_nights": 83,
        "exempt_nights": 30,
        "total_czk": 4150,
        "not_charged": [
            {"reason": "Mladší 18 let", "count": 6, "nights": 22},
            {"reason": "Osvobozeno ubytovatelem (důvod v evidenční knize)", "count": 2, "nights": 8},
        ],
        "signature_name": "Josef Novák",
    }


if __name__ == "__main__":
    output = Path(__file__).with_name("sample-invoice-companion.pdf")
    output.write_bytes(stay_fee_remittance_pdf.render(sample_report(), sample=True))
    print(output)
