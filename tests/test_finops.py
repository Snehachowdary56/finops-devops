from datetime import date

import pytest

from app import finops


@pytest.fixture(scope="module")
def rows():
    return finops.generate_costs()


def test_sample_data_is_complete(rows):
    days = {r.day for r in rows}
    assert len(days) == 60
    assert all(r.cost >= 0 for r in rows)
    finops.sanity_check(rows)


def test_sanity_check_rejects_negative_cost():
    bad = [finops.CostRow(date(2026, 1, 1), "AmazonS3", "data", "prod", -1.0)]
    with pytest.raises(ValueError):
        finops.sanity_check(bad)


def test_breakdowns_add_up_to_total(rows):
    t = finops.total(rows)
    for key in ["service", "team", "environment"]:
        assert sum(finops.by_key(rows, key).values()) == pytest.approx(t, abs=0.5)


def test_ec2_is_largest_service(rows):
    assert next(iter(finops.by_key(rows, "service"))) == "AmazonEC2"


def test_untagged_share_matches_generator(rows):
    assert finops.untagged_share(rows) == pytest.approx(0.08, abs=0.005)


def test_planted_spike_is_the_only_anomaly(rows):
    anomalies = finops.find_anomalies(rows)
    assert [a["day"] for a in anomalies] == ["2026-10-18"]  # day 47 after 2026-09-01


def test_no_anomalies_without_spike():
    clean = finops.generate_costs(anomaly_day=-1)
    assert finops.find_anomalies(clean) == []


def test_forecast_adds_remaining_days(rows):
    fc = finops.month_forecast(rows, date(2026, 10, 30))
    assert fc["days_remaining"] == 1
    assert fc["forecast"] > fc["month_to_date"]


@pytest.mark.parametrize("forecast,budget,expected", [(800, 1000, "ok"), (950, 1000, "warning"), (1200, 1000, "over")])
def test_budget_status(forecast, budget, expected):
    assert finops.budget_status(forecast, budget) == expected


def test_budget_must_be_positive():
    with pytest.raises(ValueError):
        finops.budget_status(100, 0)


def test_rightsizing_only_flags_idle_and_sorts_by_saving():
    insts = [
        finops.Instance("i-1", "data", "m5.xlarge", 0.2, 2.0, 4.0),     # idle -> stop
        finops.Instance("i-2", "data", "m5.xlarge", 0.2, 5.0, 40.0),    # low average, peaks -> downsize
        finops.Instance("i-3", "data", "m5.xlarge", 0.2, 55.0, 90.0),   # busy -> keep
    ]
    recs = finops.rightsizing(insts)
    assert [r["instance_id"] for r in recs] == ["i-1", "i-2"]
    assert recs[0]["action"].startswith("stop") and recs[0]["monthly_saving"] == pytest.approx(146.0)
    assert recs[1]["monthly_saving"] == pytest.approx(73.0)


def test_power_bi_export_is_a_star_schema(rows, tmp_path):
    files = finops.export_power_bi(rows, finops.generate_instances(), tmp_path)
    names = {f.name for f in files}
    assert {"fact_cost.csv", "dim_service.csv", "dim_team.csv", "dim_date.csv", "rightsizing.csv"} <= names
    fact = (tmp_path / "fact_cost.csv").read_text().splitlines()
    assert fact[0] == "date,service_id,team_id,environment,cost_usd"
    assert len(fact) == len(rows) + 1
