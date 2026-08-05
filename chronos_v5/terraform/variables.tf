variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment (staging/production)"
  type        = string
}

variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
}

variable "oidc_provider_arn" {
  description = "ARN of the OIDC provider for the EKS cluster"
  type        = string
}

variable "namespace" {
  description = "Kubernetes namespace where Chronos runs"
  type        = string
  default     = "production"
}

variable "github_repo" {
  description = "GitHub repository in format 'owner/repo'"
  type        = string
}

variable "api_key" {
  description = "CHRONOS_API_KEY"
  type        = string
  sensitive   = true
}

variable "secret_key" {
  description = "SECRET_KEY (32+ chars)"
  type        = string
  sensitive   = true
}

variable "jwt_secret" {
  description = "JWT_SECRET (32+ chars, different from SECRET_KEY)"
  type        = string
  sensitive   = true
}

variable "nibss_api_key" {
  description = "NIBSS_API_KEY"
  type        = string
  sensitive   = true
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {
    Project   = "Chronos"
    ManagedBy = "Terraform"
  }
}
