"""Small web service: health check, JSON cost summary, and Prometheus metrics.

Endpoints
  GET /health        -> {"status": "ok"}          (used by Kubernetes probes)
  GET /api/summary   -> FinOps summary as JSON
  GET /metrics       -> Prometheus metrics (cost by service, forecast, budget, savings)
Settings come from environment variables (set by a Kubernetes ConfigMap):
  MONTHLY_BUDGET_USD, AS_OF_DATE, PORT
"""

from __future__ import annotations

import json
import os
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from prometheus_client import CollectorRegistry, Gauge, generate_latest, CONTENT_TYPE_LATEST

from app import finops


def build_summary() -> dict:
    budget = float(os.environ.get("MONTHLY_BUDGET_USD", "25000"))
    as_of = date.fromisoformat(os.environ.get("AS_OF_DATE", "2026-10-30"))
    rows = finops.generate_costs()
    finops.sanity_check(rows)
    return finops.summary(rows, finops.generate_instances(), budget, as_of)


def metrics_text(s: dict) -> bytes:
    reg = CollectorRegistry()
    by_service = Gauge("finops_cost_usd_by_service", "Total cost in the sample period by service", ["service"], registry=reg)
    for svc, cost in s["by_service"].items():
        by_service.labels(svc).set(cost)
    by_team = Gauge("finops_cost_usd_by_team", "Total cost by owning team", ["team"], registry=reg)
    for team, cost in s["by_team"].items():
        by_team.labels(team).set(cost)
    Gauge("finops_month_forecast_usd", "Forecast cost for the current month", registry=reg).set(s["forecast"]["forecast"])
    Gauge("finops_month_to_date_usd", "Month-to-date cost", registry=reg).set(s["forecast"]["month_to_date"])
    Gauge("finops_monthly_budget_usd", "Monthly budget", registry=reg).set(s["budget"])
    Gauge("finops_untagged_share", "Share of cost with no owning team tag (0-1)", registry=reg).set(s["untagged_share"])
    Gauge("finops_anomaly_days", "Number of days flagged as cost anomalies", registry=reg).set(len(s["anomalies"]))
    Gauge("finops_potential_monthly_saving_usd", "Saving from rightsizing idle instances", registry=reg).set(s["potential_monthly_saving"])
    return generate_latest(reg)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 (http.server naming)
        if self.path == "/health":
            self._send(200, b'{"status": "ok"}', "application/json")
        elif self.path == "/api/summary":
            self._send(200, json.dumps(build_summary(), default=str).encode(), "application/json")
        elif self.path == "/metrics":
            self._send(200, metrics_text(build_summary()), CONTENT_TYPE_LATEST)
        else:
            self._send(404, b'{"error": "not found"}', "application/json")

    def log_message(self, fmt, *args):  # keep container logs short
        pass


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    print(f"finops-monitor listening on :{port}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
