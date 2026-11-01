#!/usr/bin/env python3
"""Write the Python oracle for the Go billing port (go/internal/billing).

Dev tool, never run in production. It only prices test inputs: it never reads
.env, config files or the database. Usage: billing_fixtures.py [--out PATH]
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "App"))

from app import billing  # noqa: E402
from app import billing_analytics  # noqa: E402

DEFAULT_OUT = ROOT / "go" / "internal" / "billing" / "testdata" / "quote_fixtures.json"
APARTMENTS = (0, 1, 4, 5, 9, 10, 23)
DISCOUNTS = (0, 1, 15, 50, 100)
MONTHLY_TOTALS = (0, 6, 7, 13, 18, 25, 30, 1194, 1206)


def build():
    quotes = []
    for n, plan, interval, ttlock, whitelabel, founder, discount in itertools.product(
        APARTMENTS, billing.PLANS, billing.INTERVALS, (False, True), (False, True),
        (False, True), DISCOUNTS,
    ):
        expected = billing.quote(
            n, plan, interval, ttlock=ttlock, whitelabel=whitelabel,
            founder=founder, discount_percent=discount,
        )
        quotes.append({
            "apartments": n, "plan": plan, "interval": interval,
            "ttlock": ttlock, "whitelabel": whitelabel, "founder": founder,
            "discount_percent": discount, "expected": expected,
        })
    monthly = [
        {"total": t, "interval": i, "expected": billing_analytics._monthly(t, i)}
        for t, i in itertools.product(MONTHLY_TOTALS, billing.INTERVALS)
    ]
    return {"quote": quotes, "monthly": monthly}, len(quotes) + len(monthly)


def render(data) -> str:
    lines = ["{"]
    for key in ("quote", "monthly"):
        lines.append(f'  "{key}": [')
        items = [json.dumps(item, sort_keys=True) for item in data[key]]
        lines.append(",\n".join(f"    {item}" for item in items))
        lines.append("  ]," if key == "quote" else "  ]")
    lines.append("}")
    return "\n".join(lines) + "\n"


def main() -> None:
    out = DEFAULT_OUT
    if sys.argv[1:2] == ["--out"]:
        out = Path(sys.argv[2])
    data, count = build()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(data), encoding="utf-8")
    print(f"fixtures written: {count}")


if __name__ == "__main__":
    main()
