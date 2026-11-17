terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }
}

# Points at LocalStack (a local AWS emulator) by default, so no real AWS account or bill is needed.
# For real AWS: set use_localstack = false and use your normal AWS credentials.
provider "aws" {
  region                      = var.region
  access_key                  = var.use_localstack ? "test" : null
  secret_key                  = var.use_localstack ? "test" : null
  skip_credentials_validation = var.use_localstack
  skip_requesting_account_id  = var.use_localstack
  skip_metadata_api_check     = var.use_localstack
  s3_use_path_style           = var.use_localstack

  dynamic "endpoints" {
    for_each = var.use_localstack ? [var.localstack_url] : []
    content {
      s3         = endpoints.value
      iam        = endpoints.value
      sts        = endpoints.value
      cloudwatch = endpoints.value
    }
  }

  default_tags {
    tags = {
      project    = "finops-monitor"
      team       = "platform"
      managed-by = "terraform"
    }
  }
}
