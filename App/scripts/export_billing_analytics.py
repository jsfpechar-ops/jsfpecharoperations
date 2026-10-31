#!/usr/bin/env python3
"""Export a bounded, read-only billing analytics snapshot as one JSON file."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import billing, config, db  # noqa: E402

MRR_STATES = {"active", "overdue", "canceling"}
MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
ISSUE_SQL = """SELECT substr(issue_date,1,7) AS month, COUNT(*) AS n,
COALESCE(SUM(total_haler),0) AS h FROM platform_invoice
WHERE voided = 0 AND issue_date >= ? AND issue_date < ?
GROUP BY substr(issue_date,1,7) ORDER BY month"""
PAID_SQL = """SELECT substr(paid_on,1,7) AS month, COUNT(*) AS n,
COALESCE(SUM(total_haler),0) AS h FROM platform_invoice
WHERE voided = 0 AND paid_on IS NOT NULL AND paid_on >= ? AND paid_on < ?
GROUP BY substr(paid_on,1,7) ORDER BY month"""
ACCOUNT_SQL = """SELECT status, plan, billing_interval, apartments_billed,
addon_ttlock, addon_whitelabel, founder, carry_czk, discount_percent
FROM billing_account WHERE plan IS NOT NULL ORDER BY status"""


class PublishedButNotDurableError(RuntimeError):
    """The complete new file is published, but its directory fsync failed."""


def month_bounds(value: str) -> Tuple[date, date]:
    if not MONTH_RE.fullmatch(value):
        raise ValueError(f"invalid month {value!r}; expected YYYY-MM")
    year, month = map(int, value.split("-"))
    start = date(year, month, 1)
    if month == 12:
        after = date(year + 1, 1, 1)
    else:
        after = date(year, month + 1, 1)
    return start, after


def month_range(from_month: str, through_month: str) -> Tuple[date, date]:
    start, _ = month_bounds(from_month)
    through_start, after = month_bounds(through_month)
    if through_start < start:
        raise ValueError("through_month must not precede from_month")
    return start, after


def _db_paths(db_path: Path) -> List[Path]:
    raw = Path(db_path).expanduser()
    resolved = raw.resolve(strict=False)
    paths = [raw, resolved]
    for base in (raw, resolved):
        paths.extend(Path(f"{base}{suffix}") for suffix in ("-wal", "-shm", "-journal"))
    return paths


def validate_output_path(output: Path, db_path: Path) -> Path:
    """Reject the database and journal sidecars, including path aliases."""
    target = Path(output).expanduser().resolve(strict=False)
    for protected in _db_paths(db_path):
        protected_resolved = protected.resolve(strict=False)
        if target == protected_resolved:
            raise ValueError(f"output path conflicts with database file or sidecar: {protected.name}")
        try:
            if target.exists() and protected.exists() and os.path.samefile(target, protected):
                raise ValueError(f"output path aliases database file or sidecar: {protected.name}")
        except OSError:
            # A failed samefile probe is not an alias proof; resolved-path
            # equality above still rejects symlinks and lexical aliases.
            pass
    return target


def extract(from_month: str, through_month: str) -> Dict[str, Any]:
    start, after = month_range(from_month, through_month)
    portfolio: Dict[str, Dict[str, int]] = {}

    with db.readonly_cursor() as cur:
        cur.execute(ACCOUNT_SQL)
        # The first SELECT pins SQLite's read snapshot. Keep both the timestamp
        # and Prague business date tied to this instant.
        snapshot_at = datetime.now(timezone.utc)
        accounts = cur.fetchall()

        for account in accounts:
            status = account["status"]
            aggregate = portfolio.setdefault(status, {
                "plan_account_count": 0,
                "legacy_quote_monthly_czk": 0,
                "legacy_quote_annual_czk": 0,
            })
            aggregate["plan_account_count"] += 1
            if status not in MRR_STATES:
                continue
            quote = billing.quote(
                account["apartments_billed"],
                account["plan"],
                account["billing_interval"],
                ttlock=bool(account["addon_ttlock"]),
                whitelabel=bool(account["addon_whitelabel"]),
                founder=bool(account["founder"]),
                discount_percent=int(account["discount_percent"] or 0),
            )
            net = int(quote["total"]) + int(account["carry_czk"] or 0)
            if account["billing_interval"] == "year":
                monthly = round(net / 12)
                annual = net
            else:
                monthly = net
                annual = monthly * 12
            aggregate["legacy_quote_monthly_czk"] += monthly
            aggregate["legacy_quote_annual_czk"] += annual

        cur.execute(ISSUE_SQL, (start.isoformat(), after.isoformat()))
        invoice_totals = [
            {"month": row["month"], "basis": "issue_date", "currency": "CZK",
             "nonvoid_invoice_count": int(row["n"]), "total_haler": int(row["h"])}
            for row in cur.fetchall()
        ]
        cur.execute(PAID_SQL, (start.isoformat(), after.isoformat()))
        invoice_totals.extend(
            {"month": row["month"], "basis": "paid_on", "currency": "CZK",
             "nonvoid_invoice_count": int(row["n"]), "total_haler": int(row["h"])}
            for row in cur.fetchall()
        )

    snapshot_utc = snapshot_at.astimezone(timezone.utc)
    generated_utc = datetime.now(timezone.utc)
    return {
        "schema_version": 1,
        "source_snapshot_at_utc": snapshot_utc.isoformat(timespec="seconds"),
        "as_of_date_prague": snapshot_utc.astimezone(ZoneInfo("Europe/Prague")).date().isoformat(),
        "generated_at_utc": generated_utc.isoformat(timespec="seconds"),
        "range": {"from_month": from_month, "through_month": through_month},
        "definitions": {
            "portfolio": (
                "Legacy quote portfolio; whole-Kc amounts from billing.quote plus carry; "
                "not VAT-reconciled MRR."
            ),
            "invoice_amount_currency": "CZK per source billing contract; no FX or multi-currency support.",
            "paid_on": (
                "Non-void invoice totals marked paid by paid_on; not cash collections "
                "or payment allocations."
            ),
        },
        "portfolio_quote": [
            {"status": status, **portfolio[status]} for status in sorted(portfolio)
        ],
        "invoice_month_totals": sorted(
            invoice_totals, key=lambda row: (row["month"], row["basis"])
        ),
    }


def _fsync_directory(directory: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    fd = os.open(directory, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def publish(payload: Dict[str, Any], output: Path, db_path: Path) -> None:
    output = validate_output_path(output, db_path)
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        dir=output.parent, prefix=f".{output.name}.", suffix=".tmp"
    )
    temp = Path(temp_name)
    replaced = False
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, output)
        replaced = True
        try:
            _fsync_directory(output.parent)
        except OSError as exc:
            raise PublishedButNotDurableError(
                f"new complete export is published at {output}, but directory fsync failed: {exc}"
            ) from exc
    finally:
        if not replaced:
            try:
                temp.unlink()
            except FileNotFoundError:
                pass


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-month", required=True)
    parser.add_argument("--through-month", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        month_range(args.from_month, args.through_month)
        output = validate_output_path(args.output, config.DB_PATH)
        payload = extract(args.from_month, args.through_month)
        publish(payload, output, config.DB_PATH)
    except PublishedButNotDurableError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"billing export failed before publication: {exc}", file=sys.stderr)
        return 1
    print(f"published billing analytics export: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
