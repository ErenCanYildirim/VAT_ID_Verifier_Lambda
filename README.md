# VAT_ID_Verifier_Lambda

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.11-blue.svg)
![AWS Lambda](https://img.shields.io/badge/AWS-Lambda-orange.svg)

A serverless AWS Lambda-based API for validating European VAT numbers using the EU VIES (VAT Information Exchange System) service. Built with Terraform for infrastructure as code. Originally developed for a SaaS-App for industrial companies to verify registering companies.

## Features

    -- **Dual API Support**: SOAP and REST endpoints for VIES validation (REST is sometimes down from the VIES side)
    -- **Serverless Architecture**: AWS Lambda + API GW, KMS encryption, X-Ray and CloudWatch
    -- **IaC**: Complete Terraform configuration provided
    -- **Cost optimization**: API GW caching implemented, add Lambda concurrency configurations on your own

## Prequisites
    - AWS account 
    - Terraform
    - Python 3.11

## Data Flow

Client Request -> API GW (key) -> AWS Lambda Function -> EU VIES service -> Response 

## Prepare Lambda code
Either use the provided build_lambda.sh in scripts or run:
```bash
    mkdir lambda_package
    cp lambda_function.py lambda_package/
    cd lambda_package
    pip install requests==2.31.0 -t lambda_package/
```

## Configure and deploy terraform

Edit terraform.tfvars with own settings. Configure aws credentials via aws-cli.

```bash
    terraform init
    terraform plan
    terraform apply
```

Get the terraform credentials using
```bash terraform output <cred>```
or using the provided extract_terraform_outputs.py in scripts.

## Configure .env file based on .env.example

## Request format
Endpoint POST /check-vat

Headers:
    Content-Type: application/json
    x-api-key: API_KEY

Body:
```json
    {
        "vatNumber": "DE129274202",
        "method": "soap" //optional (soap, rest etc.)
    }
``` 

```bash
curl -X POST "https://your-api-gateway-url.amazonaws.com/prod/check-vat" \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{"vatNumber": "DE129274202", "method": "soap"}'
```

## Response format

Success:

```json
{
  "success": true,
  "data": {
    "countryCode": "DE",
    "vatNumber": "129274202",
    "requestDate": "2024-01-15+01:00",
    "valid": true,
    "name": "EXAMPLE COMPANY GMBH",
    "address": "EXAMPLE STREET 123\n12345 BERLIN"
  },
  "vatNumber": "DE129274202",
  "method": "soap"
}
```

Error:

```json
{
  "error": "VIES Service Error",
  "details": {
    "error": "SOAP Fault",
    "message": "INVALID_INPUT"
  },
  "vatNumber": "DE000000000",
  "method": "soap"
}
```

## Monitoring & Observability & Security

View logs in AWS Console:
    -> Lambda logs
    -> API GW logs

X-Ray traces in AWS X-Ray
    
Features:
    - KMS rotating secrets for encryption at rest