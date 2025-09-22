output "api_gateway_url_test" {
  description = "API Gateway URL for test stage"
  value       = "https://${aws_api_gateway_rest_api.vat_api.id}.execute-api.${var.aws_region}.amazonaws.com/test/check-vat"
}

output "api_gateway_url_prod" {
  description = "API Gateway URL for production stage"
  value       = "https://${aws_api_gateway_rest_api.vat_api.id}.execute-api.${var.aws_region}.amazonaws.com/prod/check-vat"
}

output "api_key_id" {
  description = "API Key ID"
  value       = aws_api_gateway_api_key.vat_api_key.id
}

output "api_key_value" {
  description = "API Key Value (sensitive)"
  value       = aws_api_gateway_api_key.vat_api_key.value
  sensitive   = true
}

output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.vat_checker.function_name
}

output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.vat_checker.arn
}

output "api_gateway_id" {
  description = "API Gateway ID"
  value       = aws_api_gateway_rest_api.vat_api.id
}

output "cloudwatch_log_group_lambda" {
  description = "CloudWatch log group for Lambda"
  value       = aws_cloudwatch_log_group.lambda_logs.name
}

output "cloudwatch_log_group_api_gateway" {
  description = "CloudWatch log group for API Gateway"
  value       = aws_cloudwatch_log_group.api_gateway_logs.name
}