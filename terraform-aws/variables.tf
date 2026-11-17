variable "region" {
  description = "AWS region"
  type        = string
  default     = "ca-central-1"
}

variable "use_localstack" {
  description = "Use the LocalStack emulator instead of real AWS"
  type        = bool
  default     = true
}

variable "localstack_url" {
  description = "LocalStack endpoint"
  type        = string
  default     = "http://localhost:4566"
}

variable "bucket_name" {
  description = "S3 bucket for FinOps cost reports"
  type        = string
  default     = "finops-cost-reports"
}

variable "monthly_budget_usd" {
  description = "Alarm when the forecast goes above this amount"
  type        = number
  default     = 25000
}
