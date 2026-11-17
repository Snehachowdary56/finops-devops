"""FinOps analysis of cloud cost data.

Works on AWS Cost and Usage Report (CUR)-style rows. The project ships a generator for
SAMPLE data (clearly not a real AWS bill) so it runs without an AWS account.

What it answers:
  * How much are we spending, by service, team and environment?
  * What will this month cost (forecast) and are we over budget?
  * Which days look unusual (cost anomalies)?
  * How much spend is untagged (nobody owns it)?
  * Which resources are idle and could be stopped or downsized (rightsizing)?
"""

from __future__ import annotations

import csv
import math
import random
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

SERVICES = {  # service: (daily base cost in USD, teams that use it)
    "AmazonEC2": (420.0, ["signalling", "platform", "data"]),
    "AmazonRDS": (180.0, ["platform", "data"]),
    "AmazonS3": (65.0, ["data", "platform"]),
    "AWSLambda": (22.0, ["signalling"]),
    "AmazonEKS": (95.0, ["platform"]),
    "AmazonCloudWatch": (30.0, ["platform", "signalling"]),
}
ENVIRONMENTS = {"prod": 0.6, "test": 0.25, "dev": 0.15}


@dataclass(frozen=True)
class CostRow:
    day: date
    service: str
    team: str        # "" means untagged
    environment: str
    cost: float


@dataclass(frozen=True)
class Instance:
    instance_id: str
    team: str
    instance_type: str
    hourly_cost: float
    avg_cpu_pct: float
    max_cpu_pct: float


def generate_costs(days: int = 60, start: date = date(2026, 9, 1), seed: int = 5,
                   anomaly_day: int = 47, untagged_share: float = 0.08) -> list[CostRow]:
    """Sample daily costs with weekly pattern, slow growth, noise, untagged spend and one spike."""
    rng = random.Random(seed)
    rows: list[CostRow] = []
    for d in range(days):
        day = start + timedelta(days=d)
        weekday_factor = 0.8 if day.weekday() >= 5 else 1.0
        growth = 1 + 0.003 * d
        for service, (base, teams) in SERVICES.items():
            spike = 3.2 if (d == anomaly_day and service == "AmazonEC2") else 1.0
            for env, env_share in ENVIRONMENTS.items():
                total = base * env_share * weekday_factor * growth * spike * rng.uniform(0.92, 1.08)
                untagged = total * untagged_share
                per_team = (total - untagged) / len(teams)
                for team in teams:
                    rows.append(CostRow(day, service, team, env, round(per_team, 2)))
                rows.append(CostRow(day, service, "", env, round(untagged, 2)))
    return rows


def generate_instances(seed: int = 9) -> list[Instance]:
    rng = random.Random(seed)
    types = {"m5.xlarge": 0.192, "m5.2xlarge": 0.384, "c5.large": 0.085, "r5.large": 0.126}
    out = []
    for i in range(24):
        t = rng.choice(list(types))
        team = rng.choice(["signalling", "platform", "data"])
        busy = rng.random() > 0.3
        avg = rng.uniform(35, 70) if busy else rng.uniform(1, 6)
        out.append(Instance(f"i-{1000 + i:04d}", team, t, types[t], round(avg, 1), round(min(100, avg * rng.uniform(1.2, 1.8)), 1)))
    return out


def total(rows: list[CostRow]) -> float:
    return round(sum(r.cost for r in rows), 2)


def by_key(rows: list[CostRow], key: str) -> dict[str, float]:
    out: dict[str, float] = defaultdict(float)
    for r in rows:
        out[getattr(r, key) or "untagged"] += r.cost
    return {k: round(v, 2) for k, v in sorted(out.items(), key=lambda kv: -kv[1])}


def daily_totals(rows: list[CostRow]) -> dict[date, float]:
    out: dict[date, float] = defaultdict(float)
    for r in rows:
        out[r.day] += r.cost
    return {d: round(v, 2) for d, v in sorted(out.items())}


def untagged_share(rows: list[CostRow]) -> float:
    t = total(rows)
    return 0.0 if t == 0 else round(sum(r.cost for r in rows if not r.team) / t, 4)


def find_anomalies(rows: list[CostRow], window: int = 14, z_threshold: float = 3.0) -> list[dict]:
    """Days whose total cost is far above the previous `window` days (rolling z-score)."""
    days = list(daily_totals(rows).items())
    found = []
    for i in range(window, len(days)):
        history = [v for _, v in days[i - window:i]]
        mean, sd = statistics.mean(history), statistics.pstdev(history) or 1.0
        z = (days[i][1] - mean) / sd
        if z >= z_threshold:
            found.append({"day": days[i][0].isoformat(), "cost": days[i][1], "expected": round(mean, 2), "z_score": round(z, 1)})
    return found


def month_forecast(rows: list[CostRow], as_of: date) -> dict:
    """Month-to-date spend plus a forecast for the rest of the month from the last 7 days' average."""
    daily = daily_totals(rows)
    month_days = {d: v for d, v in daily.items() if d.year == as_of.year and d.month == as_of.month and d <= as_of}
    mtd = round(sum(month_days.values()), 2)
    last7 = [v for d, v in daily.items() if as_of - timedelta(days=6) <= d <= as_of]
    avg = statistics.mean(last7) if last7 else 0.0
    next_month = (as_of.replace(day=28) + timedelta(days=4)).replace(day=1)
    remaining = (next_month - as_of).days - 1
    return {"month": as_of.strftime("%Y-%m"), "month_to_date": mtd, "forecast": round(mtd + avg * remaining, 2),
            "days_remaining": remaining}


def budget_status(forecast: float, budget: float, warn_at: float = 0.9) -> str:
    if budget <= 0:
        raise ValueError("budget must be positive")
    ratio = forecast / budget
    return "over" if ratio > 1 else "warning" if ratio >= warn_at else "ok"


def rightsizing(instances: list[Instance], idle_cpu: float = 10.0, hours_per_month: int = 730) -> list[dict]:
    """Instances that are mostly idle: recommend stopping or moving to a smaller size."""
    recs = []
    for inst in instances:
        if inst.avg_cpu_pct < idle_cpu:
            saving = inst.hourly_cost * hours_per_month * (1.0 if inst.max_cpu_pct < idle_cpu else 0.5)
            action = "stop (idle)" if inst.max_cpu_pct < idle_cpu else "downsize one size"
            recs.append({"instance_id": inst.instance_id, "team": inst.team, "type": inst.instance_type,
                         "avg_cpu_pct": inst.avg_cpu_pct, "action": action, "monthly_saving": round(saving, 2)})
    return sorted(recs, key=lambda r: -r["monthly_saving"])


def summary(rows: list[CostRow], instances: list[Instance], budget: float, as_of: date) -> dict:
    fc = month_forecast(rows, as_of)
    recs = rightsizing(instances)
    return {
        "total_cost": total(rows),
        "by_service": by_key(rows, "service"),
        "by_team": by_key(rows, "team"),
        "by_environment": by_key(rows, "environment"),
        "untagged_share": untagged_share(rows),
        "anomalies": find_anomalies(rows),
        "forecast": fc,
        "budget": budget,
        "budget_status": budget_status(fc["forecast"], budget),
        "rightsizing": recs,
        "potential_monthly_saving": round(sum(r["monthly_saving"] for r in recs), 2),
    }


def export_power_bi(rows: list[CostRow], instances: list[Instance], out_dir: str | Path) -> list[Path]:
    """Star schema for Power BI: one fact table and small dimension tables, joined on keys."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    services = sorted({r.service for r in rows})
    teams = sorted({r.team or "untagged" for r in rows})
    days = sorted({r.day for r in rows})
    files = []

    def write(name, header, data):
        p = out / name
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(data)
        files.append(p)

    write("dim_service.csv", ["service_id", "service"], [[i, s] for i, s in enumerate(services, 1)])
    write("dim_team.csv", ["team_id", "team"], [[i, t] for i, t in enumerate(teams, 1)])
    write("dim_date.csv", ["date", "year", "month", "day", "weekday", "is_weekend"],
          [[d.isoformat(), d.year, d.month, d.day, d.strftime("%a"), d.weekday() >= 5] for d in days])
    sid = {s: i for i, s in enumerate(services, 1)}
    tid = {t: i for i, t in enumerate(teams, 1)}
    write("fact_cost.csv", ["date", "service_id", "team_id", "environment", "cost_usd"],
          [[r.day.isoformat(), sid[r.service], tid[r.team or "untagged"], r.environment, r.cost] for r in rows])
    write("rightsizing.csv", ["instance_id", "team", "type", "avg_cpu_pct", "action", "monthly_saving"],
          [list(r.values()) for r in rightsizing(instances)])
    return files


def sanity_check(rows: list[CostRow]) -> None:
    if any(math.isnan(r.cost) or r.cost < 0 for r in rows):
        raise ValueError("costs must be non-negative numbers")
