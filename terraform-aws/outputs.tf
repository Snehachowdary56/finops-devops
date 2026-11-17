output "bucket" {
  value = aws_s3_bucket.reports.bucket
}

output "read_policy_arn" {
  value = aws_iam_policy.read_reports.arn
}

output "alarm_name" {
  value = aws_cloudwatch_metric_alarm.over_budget.alarm_name
}
