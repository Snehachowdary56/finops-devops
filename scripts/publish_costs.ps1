# Windows PowerShell version of publish_costs.sh (same steps, AWS CLI).
# Run from the project folder:  powershell -ExecutionPolicy Bypass -File scripts\publish_costs.ps1
# Uses LocalStack by default. For real AWS: $env:AWS_ENDPOINT_URL = "" and use your AWS credentials.
$ErrorActionPreference = "Stop"

$Bucket = if ($env:BUCKET) { $env:BUCKET } else { "finops-cost-reports" }
$Budget = if ($env:MONTHLY_BUDGET_USD) { $env:MONTHLY_BUDGET_USD } else { "25000" }
$AsOf   = if ($env:AS_OF_DATE) { $env:AS_OF_DATE } else { "2026-10-30" }
if (-not $env:AWS_DEFAULT_REGION) { $env:AWS_DEFAULT_REGION = "ca-central-1" }
if ($null -eq $env:AWS_ENDPOINT_URL) { $env:AWS_ENDPOINT_URL = "http://localhost:4566" }
if ($env:AWS_ENDPOINT_URL) {
  if (-not $env:AWS_ACCESS_KEY_ID) { $env:AWS_ACCESS_KEY_ID = "test" }
  if (-not $env:AWS_SECRET_ACCESS_KEY) { $env:AWS_SECRET_ACCESS_KEY = "test" }
}

Write-Host "== 1. Build Power BI files"
python -m app.report --budget $Budget --as-of $AsOf --out powerbi | Out-Null

Write-Host "== 2. Upload to s3://$Bucket/powerbi/"
aws s3 sync powerbi "s3://$Bucket/powerbi/" --only-show-errors
aws s3 ls "s3://$Bucket/powerbi/"

Write-Host "== 3. Send month forecast to CloudWatch (namespace FinOps)"
$Forecast = python -c "from datetime import date; from app import finops; print(finops.month_forecast(finops.generate_costs(), date.fromisoformat('$AsOf'))['forecast'])"
Write-Host "Forecast: `$$Forecast  Budget: `$$Budget"
aws cloudwatch put-metric-data --namespace FinOps --metric-name MonthForecastUSD --unit None --value $Forecast

Write-Host "== 4. Budget alarm"
aws cloudwatch describe-alarms --alarm-names finops-forecast-over-budget `
  --query "MetricAlarms[0].[AlarmName,StateValue,Threshold]" --output text
