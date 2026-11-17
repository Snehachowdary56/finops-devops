import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from app import server


@pytest.fixture(scope="module")
def base_url():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def get(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, r.read().decode()


def test_health(base_url):
    assert get(base_url + "/health") == (200, '{"status": "ok"}')


def test_summary_json(base_url):
    status, body = get(base_url + "/api/summary")
    data = json.loads(body)
    assert status == 200
    assert data["budget_status"] in {"ok", "warning", "over"}
    assert data["anomalies"][0]["day"] == "2026-10-18"


def test_metrics_for_prometheus(base_url):
    status, body = get(base_url + "/metrics")
    assert status == 200
    assert 'finops_cost_usd_by_service{service="AmazonEC2"}' in body
    assert "finops_month_forecast_usd" in body
    assert "finops_potential_monthly_saving_usd" in body


def test_budget_comes_from_environment(monkeypatch):
    monkeypatch.setenv("MONTHLY_BUDGET_USD", "1000000")
    assert server.build_summary()["budget_status"] == "ok"


def test_unknown_path_is_404(base_url):
    with pytest.raises(urllib.error.HTTPError) as e:
        get(base_url + "/nope")
    assert e.value.code == 404
