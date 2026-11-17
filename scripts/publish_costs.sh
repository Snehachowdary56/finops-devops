#!/usr/bin/env bash
# Publish FinOps results to AWS with the AWS CLI:
#   1. build the Power BI CSV files
#   2. upload them to the S3 bucket created by terraform-aws/
#   3. send the month forecast to CloudWatch as a custom metric
#   4. show the budget alarm state
# Works against LocalStack by default (AWS_ENDPOINT_URL=http://localhost:4566).
# For real AWS: unset AWS_ENDPOINT_URL and use your normal AWS credentials.
set -euo pipefail

BUCKET="${BUCKET:-finops-cost-reports}"
BUDGET="${MONTHLY_BUDGET_USD:-25000}"
AS_OF="${AS_OF_DATE:-2026-10-30}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-ca-central-1}"
export AWS_ENDPOINT_URL="${AWS_ENDPOINT_URL-http://localhost:4566}"
if [ -n "$AWS_ENDPOINT_URL" ]; then
  export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-test}" AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-test}"
fi

echo "== 1. Build Power BI files"
python -m app.report --budget "$BUDGET" --as-of "$AS_OF" --out powerbi > /dev/null

echo "== 2. Upload to s3://$BUCKET/powerbi/"
aws s3 sync powerbi "s3://$BUCKET/powerbi/" --only-show-errors
aws s3 ls "s3://$BUCKET/powerbi/"

echo "== 3. Send month forecast to CloudWatch (namespace FinOps)"
FORECAST=$(python -c "
from datetime import date
from app import finops
rows = finops.generate_costs()
print(finops.month_forecast(rows, date.fromisoformat('$AS_OF'))['forecast'])")
echo "Forecast: \$$FORECAST  Budget: \$$BUDGET"
aws cloudwatch put-metric-data --namespace FinOps \
  --metric-name MonthForecastUSD --unit None --value "$FORECAST"

echo "== 4. Budget alarm (CloudWatch evaluates it; may show INSUFFICIENT_DATA for the first minute)"
aws cloudwatch describe-alarms --alarm-names finops-forecast-over-budget \
  --query 'MetricAlarms[0].[AlarmName,StateValue,Threshold]' --output text
