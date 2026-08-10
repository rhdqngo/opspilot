variable "project_id" {
  description = "Existing Google Cloud project ID, injected at runtime."
  type        = string
  sensitive   = true

  validation {
    condition     = length(trimspace(var.project_id)) > 0
    error_message = "project_id must be supplied through TF_VAR_project_id or an ignored tfvars file."
  }
}

variable "billing_account_id" {
  description = "Linked billing account ID, injected at runtime and never committed."
  type        = string
  sensitive   = true

  validation {
    condition     = length(trimspace(var.billing_account_id)) > 0
    error_message = "billing_account_id must be supplied at runtime."
  }
}

variable "budget_notification_email" {
  description = "Budget alert recipient, injected at runtime and stored only in protected state."
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.budget_notification_email))
    error_message = "budget_notification_email must be a valid email address."
  }
}

variable "region" {
  description = "Regional resource location."
  type        = string
  default     = "asia-northeast3"
}

variable "environment" {
  description = "Deployment environment label."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "demo"], var.environment)
    error_message = "environment must be dev or demo."
  }
}
