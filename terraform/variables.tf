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
  default = 14
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