# AWS resources for FinOps reporting: a private, encrypted, versioned S3 bucket for the
# Power BI cost files, a least-privilege IAM policy to read them, and a CloudWatch alarm
# that fires when the month forecast is above budget.

resource "aws_s3_bucket" "reports" {
  bucket        = var.bucket_name
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "reports" {
  bucket = aws_s3_bucket.reports.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "reports" {
  bucket                  = aws_s3_bucket.reports.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Least privilege: the reporting (Power BI) user can only list and read this bucket's powerbi/ files.
data "aws_iam_policy_document" "read_reports" {
  statement {
    sid       = "ListReports"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.reports.arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["powerbi/*"]
    }
  }
  statement {
    sid       = "ReadReports"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.reports.arn}/powerbi/*"]
  }
}

resource "aws_iam_policy" "read_reports" {
  name        = "finops-read-cost-reports"
  description = "Read-only access to FinOps Power BI exports"
  policy      = data.aws_iam_policy_document.read_reports.json
}

resource "aws_iam_user" "powerbi" {
  name = "finops-powerbi-reader"
}

resource "aws_iam_user_policy_attachment" "powerbi" {
  user       = aws_iam_user.powerbi.name
  policy_arn = aws_iam_policy.read_reports.arn
}

resource "aws_cloudwatch_metric_alarm" "over_budget" {
  alarm_name          = "finops-forecast-over-budget"
  alarm_description   = "Month cost forecast is above the monthly budget"
  namespace           = "FinOps"
  metric_name         = "MonthForecastUSD"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 1
  threshold           = var.monthly_budget_usd
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
}
