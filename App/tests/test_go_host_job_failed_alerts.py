"""Go host shells and Python open_alerts share the same job_failed allow-list.

go/internal/hostweb/layout/alerts.go hostJobFailedKeys must match
alerts.HOST_JOB_FAILED_JOBS (comment in App/app/alerts.py).
"""
from __future__ import annotations

import re
from pathlib import Path

from app import alerts

ROOT = Path(__file__).resolve().parents[2]
GO_ALERTS = ROOT / "go/internal/hostweb/layout/alerts.go"


def _go_host_job_dedupe_keys() -> set[str]:
    text = GO_ALERTS.read_text(encoding="utf-8")
    m = re.search(r"hostJobFailedKeys = `(.+)`", text)
    assert m, "hostJobFailedKeys const missing in Go alerts.go"
    return set(re.findall(r"'(job_failed:[^']+)'", m.group(1)))


def test_python_and_go_agree_on_host_visible_job_failed_alerts():
    want = {f"job_failed:{job}" for job in alerts.HOST_JOB_FAILED_JOBS}
    got = _go_host_job_dedupe_keys()
    assert got == want