"""0427 prep: PII-free app usage metrics (Prometheus text format).

Covers the two families the app emits, the OPS-3 property (route templates
only, no paths/tokens/queries), and that /metrics answers in text format.
"""

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app
from tests.conftest import login_as

USERNAME = "metrics0427"


def _cleanup():
    owner = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    if not owner:
        return
    user_id = owner["id"]
    db.execute("DELETE FROM login_token WHERE user_account_id = ?", (user_id,))
    db.execute("DELETE FROM legal_acceptance WHERE user_account_id = ?", (user_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


@pytest.fixture
def client():
    db.init_db()
    _cleanup()
    from app import auth

    if not db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        auth.create_account(f"{USERNAME}@example.test", "Metrics Host", username=USERNAME)
    c = TestClient(app)
    login_as(c, USERNAME, url="/login?lang=en", follow_redirects=False)
    try:
        yield c
    finally:
        _cleanup()


def _reset():
    from app import metrics as m

    with m._lock:
        m._requests.clear()
        m._durations.clear()
        m._duration_sums.clear()
        m._duration_counts.clear()


def test_counter_and_histogram_rendering():
    from app import metrics as m

    _reset()
    m.observe_request("GET", "/guide/{item_id}", 200, 0.042)
    m.observe_request("GET", "/guide/{item_id}", 200, 0.042)
    m.observe_request("POST", "/guide/{item_id}", 500, 1.32)
    out = m.render()
    assert 'ubyhost_requests_total{method="GET",route="/guide/{item_id}",status="200"} 2' in out
    assert 'ubyhost_requests_total{method="POST",route="/guide/{item_id}",status="500"} 1' in out
    # Buckets are cumulative; each request counted exactly once.
    assert 'ubyhost_request_duration_seconds_bucket{le="0.05",method="GET",route="/guide/{item_id}"} 2' in out
    assert 'ubyhost_request_duration_seconds_bucket{le="+Inf",method="GET",route="/guide/{item_id}"} 2' in out
    assert 'ubyhost_request_duration_seconds_bucket{le="2.5",method="POST",route="/guide/{item_id}"} 1' in out
    assert 'ubyhost_request_duration_seconds_count{method="POST",route="/guide/{item_id}"} 1' in out


def test_label_values_are_escaped():
    from app import metrics as m

    _reset()
    m.observe_request("GET", '/weird "{route}"', 200, 0.01)
    out = m.render()
    assert 'route="/weird \\"{route}\\""' in out


def test_metrics_endpoint_serves_text_format(client):
    _reset()
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "version=0.0.4" in response.headers["content-type"]
    assert "# TYPE ubyhost_requests_total counter" in response.text


def test_metrics_labels_never_carry_real_paths(client):
    """OPS-3: a request to a token-bearing URL must record the template."""
    _reset()
    client.get("/l/not-a-real-token")
    from app import metrics as m

    out = m.render()
    assert "/l/not-a-real-token" not in out
    assert "route=\"/l/{token}\"" in out
