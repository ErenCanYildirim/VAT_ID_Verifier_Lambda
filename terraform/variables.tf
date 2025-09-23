variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "eu-north-1"
}

variable "lambda_function_name" {
  description = "Name of the Lambda function"
  type = string 
  default = "vat-checker-lambda"
}

variable "lambda_source_file" {
  description = "Path to Lambda source file"
  type = string 
  default = "../lambda_package"
}

variable "lambda_environment_variables" {
  description = "Environment variables for Lambda function"
  type = map(string)
  default = {
    "ENVIRONMENT" = "development"
  }
}

variable "api_gateway_name" {
  description = "Name of the API Gateway"
  type = string 
  default = "vat-checker-api"
}

variable "api_key_name" {
  description = "Name of the API key"
  type = string 
  default = "vat-checker-api-key"
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type = number 
  default = 180
}

variable "api_rate_limit" {
  description = "API GW throttle rate limit (req. per sec.)"
  type = number 
  default = 10000
}

variable "api_burst_limit" {
  description = "API GW throttle burst limit"
  type = number 
  default = 200
}

variable "api_quota_limit" {
  description = "API GW quota limit per day"
  type = number
  default = 10000
}

variable "enable_xray_tracing" {
  description = "Enable X-Ray tracing for API GW"
  type = bool 
  default = false
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type = map(string)
  default = {
    Project = "VAT-Checker"
    Environment = "development"
    ManagedBy = "Terraform"
  }
}

#api gw caching
variable "enable_api_caching" {
  description = "Enable caching for API GW stages"
  type = bool
  default = true 
}

variable "api_cache_cluster_size" {
  description = "Size of the cache cluster for API GW"
  type = string
  default = "0.5"

  validation {
    condition = contains(["0.5", "1.6", "6.1", "13.5", "28.4", "58.2", "118", "237"], var.api_cache_cluster_size)
    error_message = "Cache cluster size must be one of: 0.5, 1.6, 6.1, 13.5, 28.4, 58.2, 118, 237."
  }
}