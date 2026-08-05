
---

### 22. `terraform/main.tf` – **NEW FILE**

```hcl
terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_eks_cluster" "cluster" {
  name = var.cluster_name
}

data "aws_eks_cluster_auth" "cluster" {
  name = var.cluster_name
}

data "aws_caller_identity" "current" {}

resource "aws_secretsmanager_secret" "chronos_secrets" {
  name        = "chronos/${var.environment}"
  description = "Secrets for Chronos ${var.environment}"
  rotation_rules {
    automatically_after_days = 30
  }
  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "chronos_secrets_version" {
  secret_id = aws_secretsmanager_secret.chronos_secrets.id
  secret_string = jsonencode({
    CHRONOS_API_KEY = var.api_key
    SECRET_KEY      = var.secret_key
    JWT_SECRET      = var.jwt_secret
    NIBSS_API_KEY   = var.nibss_api_key
  })
}

resource "aws_iam_policy" "chronos_secrets_policy" {
  name        = "chronos-secrets-policy-${var.environment}"
  description = "Allow reading Chronos secrets from AWS Secrets Manager"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [aws_secretsmanager_secret.chronos_secrets.arn]
      }
    ]
  })
}

module "chronos_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "5.20.0"
  role_name_prefix = "chronos-${var.environment}-"
  attach_custom_policies = true
  custom_policy_arns     = [aws_iam_policy.chronos_secrets_policy.arn]
  oidc_providers = {
    main = {
      provider_arn               = var.oidc_provider_arn
      namespace_service_accounts = ["${var.namespace}:chronos"]
    }
  }
  tags = var.tags
}

resource "aws_iam_role" "gha_secrets_role" {
  name = "chronos-gha-secrets-${var.environment}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/token.actions.githubusercontent.com"
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
          StringLike = {
            "token.actions.githubusercontent.com:sub" = "repo:${var.github_repo}:*"
          }
        }
      }
    ]
  })
  inline_policy {
    name = "secrets-read"
    policy = jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Effect = "Allow"
          Action = [
            "secretsmanager:GetSecretValue",
            "secretsmanager:DescribeSecret"
          ]
          Resource = [aws_secretsmanager_secret.chronos_secrets.arn]
        }
      ]
    })
  }
  tags = var.tags
}
