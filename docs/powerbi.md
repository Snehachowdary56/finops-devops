# Build the FinOps dashboard in Power BI Desktop (about 30 minutes)

Power BI Desktop is free and runs on Windows. It reads the CSV files this project makes.

## 1. Make the files

```
cd finops-devops
python -m app.report --out powerbi
```

You get a **star schema** in the `powerbi` folder:

| File | Type | Columns |
|---|---|---|
| fact_cost.csv | fact (one row per day, service, team, environment) | date, service_id, team_id, environment, cost_usd |
| dim_service.csv | dimension | service_id, service |
| dim_team.csv | dimension | team_id, team (includes `untagged`) |
| dim_date.csv | dimension | date, year, month, day, weekday, is_weekend |
| rightsizing.csv | stand-alone table | instance_id, team, type, avg_cpu_pct, action, monthly_saving |

(If you ran `scripts/publish_costs.sh`, the same files are also in S3 under `powerbi/`.)

## 2. Load and relate

1. **Home → Get data → Text/CSV**, load all five files.
2. **Model view**: drag `fact_cost[service_id]` → `dim_service[service_id]`, `fact_cost[team_id]` → `dim_team[team_id]`, `fact_cost[date]` → `dim_date[date]` (all many-to-one, single direction).
3. Right-click `dim_date` → **Mark as date table** → column `date`.

## 3. DAX measures (Home → New measure, paste one at a time)

```DAX
Total Cost = SUM ( fact_cost[cost_usd] )

Budget = 25000

Month To Date = TOTALMTD ( [Total Cost], dim_date[date] )

Avg Daily Cost = AVERAGEX ( VALUES ( dim_date[date] ), [Total Cost] )

Month Forecast =
VAR LastDay = MAX ( fact_cost[date] )
VAR DaysInMonth = DAY ( EOMONTH ( LastDay, 0 ) )
VAR DaysSoFar = DAY ( LastDay )
RETURN [Month To Date] / DaysSoFar * DaysInMonth

Budget Status = IF ( [Month Forecast] > [Budget], "OVER", "OK" )

Untagged % =
DIVIDE (
    CALCULATE ( [Total Cost], dim_team[team] = "untagged" ),
    [Total Cost]
)

Prod Cost % =
DIVIDE ( CALCULATE ( [Total Cost], fact_cost[environment] = "prod" ), [Total Cost] )

Cost vs Previous Month % =
VAR Prev = CALCULATE ( [Total Cost], DATEADD ( dim_date[date], -1, MONTH ) )
RETURN DIVIDE ( [Total Cost] - Prev, Prev )

Potential Saving = SUM ( rightsizing[monthly_saving] )
```

Note: the Python report's forecast uses the same idea (month-to-date pace), so the
numbers should be close to the report: forecast about $27,848 vs budget $25,000 → OVER.

## 4. Visuals (one page)

| Visual | Fields |
|---|---|
| 4 cards | Month To Date, Month Forecast, Budget Status, Untagged % |
| Line chart | X: dim_date[date], Y: Total Cost (the 2026-10-18 spike is the anomaly) |
| Stacked bar | Y: dim_service[service], X: Total Cost, Legend: fact_cost[environment] |
| Donut | Legend: dim_team[team], Values: Total Cost |
| Table | rightsizing: instance_id, type, avg_cpu_pct, action, monthly_saving (+ Potential Saving card) |
| Slicers | dim_date[month], fact_cost[environment] |

Accessibility: give every visual a title and alt text (Format → General → Alt text), and
don't use colour alone for OVER/OK (the card shows the word).

## 5. Save a screenshot

Save as `finops.pbix`, take a screenshot of the page, and add it to the README as
`docs/powerbi-dashboard.png`.
