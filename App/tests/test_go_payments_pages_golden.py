"""go/internal/payments/pages/pages_test.go compares the Go payments pages with
the Python ones through go/internal/payments/pages/testdata/golden.json (brief
1353). A change to routes/payments.py, payment_services.py, payments_consent.py
or one of the payments templates makes the file stale: rerun
scripts/payments_pages_golden.py and port the change to Go."""
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "payments_pages_golden.py"


def test_go_payments_pages_golden_is_current():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
