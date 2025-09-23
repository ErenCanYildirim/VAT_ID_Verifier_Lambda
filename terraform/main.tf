terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir = var.lambda_source_file
  output_path = "${var.lambda_function_name}.zip"
}

resource "aws_kms_key" "lambda_key" {
  description = "KMS key for Lambda function encryption"
  deletion_window_in_days = 7 
  enable_key_rotation = true 

  tags = merge(var.common_tags, {
    Name = "${var.lambda_function_name}-lambda-key"
  })
}

resource "aws_kms_alias" "lambda_key_alias" {
  name = "alias/${var.lambda_function_name}-lambda"
  target_key_id = aws_kms_key.lambda_key.key_id 
}

resource "aws_kms_key" "logs_key" {
  description = "KMS key for CloudWatch logs encryption"
  deletion_window_in_days = 7
  enable_key_rotation = true 

  policy = jsonencode({
    Version ="2012-10-17"
    Statement = [
      {
        Sid = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action = "kms:*"
        Resource = "*"
      }, 
      {
        Sid: "Allow CloudWatch Logs"
        Effect = "Allow"
        Principal = {
          Service = "logs.${var.aws_region}.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
        Condition = {
          ArnEquals = {
            "kms:EncryptionContext:aws:logs:arn" = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${var.lambda_function_name}"
          }
        }
      },
      {
        Sid    = "Allow API Gateway Logs"
        Effect = "Allow"
        Principal = {
          Service = "logs.${var.aws_region}.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
        Condition = {
          ArnEquals = {
            "kms:EncryptionContext:aws:logs:arn" = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/api-gateway/${var.api_gateway_name}"
          }
        }
      }
    ]
  })

  tags = merge(var.common_tags, {
    Name = "${var.lambda_function_name}-logs-key"
  })
}

resource "aws_kms_alias" "logs_key_alias" {
  name = "alias/${var.lambda_function_name}-logs"
  target_key_id = aws_kms_key.logs_key.key_id 
}

#get current AWS account id 
data "aws_caller_identity" "current" {}

resource "aws_iam_role_policy_attachment" "lambda_xray_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
  role       = aws_iam_role.lambda_role.name
}

resource "aws_iam_role" "lambda_role" {
  name = "${var.lambda_function_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = var.common_tags
}

#iam policy for kms access
resource "aws_iam_role_policy" "lambda_kms_policy" {
  name = "${var.lambda_function_name}-kms-policy"
  role = aws_iam_role.lambda_role.id 

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = aws_kms_key.lambda_key.arn 
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.lambda_role.name
}

resource "aws_lambda_function" "vat_checker" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = var.lambda_function_name
  role            = aws_iam_role.lambda_role.arn
  handler         = "lambda_function.lambda_handler"
  runtime         = "python3.11"
  timeout         = 30
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  kms_key_arn = aws_kms_key.lambda_key.arn 

  tracing_config {
    mode = var.enable_xray_tracing ? "Active" : "PassThrough"
  }

  environment {
    variables = var.lambda_environment_variables
  }

  tags = var.common_tags

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_cloudwatch_log_group.lambda_logs,
  ]
}

resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.lambda_function_name}"
  retention_in_days = var.log_retention_days
  kms_key_id = aws_kms_key.logs_key.arn 
  tags              = var.common_tags
}

resource "aws_api_gateway_rest_api" "vat_api" {
  name        = var.api_gateway_name
  description = "VAT Number Checker API"

  tags = var.common_tags
}

resource "aws_api_gateway_resource" "vat_resource" {
  rest_api_id = aws_api_gateway_rest_api.vat_api.id
  parent_id   = aws_api_gateway_rest_api.vat_api.root_resource_id
  path_part   = "check-vat"
}

resource "aws_api_gateway_method" "vat_method" {
  rest_api_id      = aws_api_gateway_rest_api.vat_api.id
  resource_id      = aws_api_gateway_resource.vat_resource.id
  http_method      = "POST"
  authorization    = "NONE"
  api_key_required = true
}

resource "aws_api_gateway_integration" "vat_integration" {
  rest_api_id = aws_api_gateway_rest_api.vat_api.id
  resource_id = aws_api_gateway_resource.vat_resource.id
  http_method = aws_api_gateway_method.vat_method.http_method

  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = aws_lambda_function.vat_checker.invoke_arn
}

resource "aws_lambda_permission" "api_gateway_lambda" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.vat_checker.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.vat_api.execution_arn}/*/*"
}

resource "aws_api_gateway_api_key" "vat_api_key" {
  name        = var.api_key_name
  description = "API Key for VAT Checker Service"
  enabled     = true

  tags = var.common_tags
}

resource "aws_api_gateway_usage_plan" "vat_usage_plan" {
  name        = "${var.api_gateway_name}-usage-plan"
  description = "Usage plan for VAT Checker API"

  api_stages {
    api_id = aws_api_gateway_rest_api.vat_api.id
    stage  = aws_api_gateway_stage.test.stage_name
  }

  api_stages {
    api_id = aws_api_gateway_rest_api.vat_api.id
    stage  = aws_api_gateway_stage.prod.stage_name
  }

  throttle_settings {
    rate_limit  = var.api_rate_limit
    burst_limit = var.api_burst_limit
  }

  quota_settings {
    limit  = var.api_quota_limit
    period = "DAY"
  }

  tags = var.common_tags
}

resource "aws_api_gateway_usage_plan_key" "vat_usage_plan_key" {
  key_id        = aws_api_gateway_api_key.vat_api_key.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.vat_usage_plan.id
}

resource "aws_api_gateway_deployment" "vat_deployment" {
  depends_on = [
    aws_api_gateway_method.vat_method,
    aws_api_gateway_integration.vat_integration,
  ]

  rest_api_id = aws_api_gateway_rest_api.vat_api.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.vat_resource.id,
      aws_api_gateway_method.vat_method.id,
      aws_api_gateway_integration.vat_integration.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "test" {
  deployment_id = aws_api_gateway_deployment.vat_deployment.id
  rest_api_id   = aws_api_gateway_rest_api.vat_api.id
  stage_name    = "test"

  cache_cluster_enabled = var.enable_api_caching
  cache_cluster_size = var.api_cache_cluster_size

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway_logs.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      caller         = "$context.identity.caller"
      user           = "$context.identity.user"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      resourcePath   = "$context.resourcePath"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
    })
  }

  xray_tracing_enabled = var.enable_xray_tracing

  tags = merge(var.common_tags, {
    Environment = "test"
  })
}

resource "aws_api_gateway_stage" "prod" {
  deployment_id = aws_api_gateway_deployment.vat_deployment.id
  rest_api_id   = aws_api_gateway_rest_api.vat_api.id
  stage_name    = "prod"

  cache_cluster_enabled = var.enable_api_caching
  cache_cluster_size = var.api_cache_cluster_size


  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway_logs.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      caller         = "$context.identity.caller"
      user           = "$context.identity.user"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      resourcePath   = "$context.resourcePath"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
    })
  }

  xray_tracing_enabled = var.enable_xray_tracing

  tags = merge(var.common_tags, {
    Environment = "production"
  })
}

resource "aws_cloudwatch_log_group" "api_gateway_logs" {
  name              = "/aws/api-gateway/${var.api_gateway_name}"
  retention_in_days = var.log_retention_days
  kms_key_id = aws_kms_key.logs_key.arn 
  tags              = var.common_tags
}

resource "aws_iam_role" "api_gateway_cloudwatch_role" {
  name = "${var.api_gateway_name}-cloudwatch-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "apigateway.amazonaws.com"
        }
      }
    ]
  })

  tags = var.common_tags
}

resource "aws_iam_role_policy_attachment" "api_gateway_cloudwatch" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
  role       = aws_iam_role.api_gateway_cloudwatch_role.name
}

resource "aws_api_gateway_account" "account" {
  cloudwatch_role_arn = aws_iam_role.api_gateway_cloudwatch_role.arn
}