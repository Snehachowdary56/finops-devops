"""Command line report: prints the FinOps summary and writes Power BI CSV files.

Run:  python -m app.report  [--budget 25000] [--as-of 2026-10-30] [--out powerbi]
"""

from __future__ import annotations

import argparse
from datetime import date

from app import finops


def main(argv: list[str] | None = None) -> dict:
    p = argparse.ArgumentParser(description="FinOps cloud cost report (sample AWS data)")
    p.add_argument("--budget", type=float, default=25000)
    p.add_argument("--as-of", default="2026-10-30")
    p.add_argument("--out", default="powerbi")
    a = p.parse_args(argv)

    rows, instances = finops.generate_costs(), finops.generate_instances()
    s = finops.summary(rows, instances, a.budget, date.fromisoformat(a.as_of))
    files = finops.export_power_bi(rows, instances, a.out)

    fc = s["forecast"]
    print("\nFinOps cloud cost report (SAMPLE AWS data)\n" + "-" * 44)
    print(f"Total cost (60 days):     ${s['total_cost']:,.2f}")
    print(f"Month {fc['month']} to date:   ${fc['month_to_date']:,.2f}")
    print(f"Month forecast:           ${fc['forecast']:,.2f}  vs budget ${s['budget']:,.0f}  -> {s['budget_status'].upper()}")
    print(f"Untagged spend:           {s['untagged_share']:.1%}")
    print("\nCost by service:")
    for k, v in s["by_service"].items():
        print(f"  {k:<18} ${v:,.2f}")
    print("\nCost anomalies:")
    for an in s["anomalies"] or [{"day": "none"}]:
        print(f"  {an}")
    print(f"\nRightsizing: {len(s['rightsizing'])} idle instances, potential saving ${s['potential_monthly_saving']:,.2f}/month")
    for r in s["rightsizing"][:5]:
        print(f"  {r['instance_id']} {r['type']:<11} avg CPU {r['avg_cpu_pct']:>4}%  {r['action']:<18} ${r['monthly_saving']:,.2f}")
    print("\nPower BI files:")
    for f in files:
        print(f"  {f}")
    return s


if __name__ == "__main__":
    main()
