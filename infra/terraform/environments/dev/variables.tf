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

variable "deploy_demo" {
  description = "Approval gate for M2 Cloud Run services and their supporting API state."
  type        = bool
  default     = false
}

variable "demo_image_uri" {
  description = "Immutable Artifact Registry image URI supplied only after the Approval 2 push."
  type        = string
  default     = ""
  sensitive   = true

  validation {
    condition = (
      var.demo_image_uri == "" ||
      can(regex("^[a-z0-9-]+-docker\\.pkg\\.dev/[^/]+/[^/]+/[^@]+@sha256:[0-9a-f]{64}$", var.demo_image_uri))
    )
    error_message = "demo_image_uri must be empty or an immutable Artifact Registry digest URI."
  }
}

variable "enable_scenarios" {
  description = "Approval gate for bounded request-scoped M3 synthetic scenario behavior."
  type        = bool
  default     = false
}

variable "deploy_knowledge" {
  description = "Approval gate for the M4 Agent Search knowledge resources."
  type        = bool
  default     = false
}

variable "search_location" {
  description = "Agent Search location, intentionally independent from the workload region."
  type        = string
  default     = "global"

  validation {
    condition     = var.search_location == "global"
    error_message = "The M4 MVP Agent Search location must remain global."
  }
}

variable "enable_live_evidence" {
  description = "Approval gate for the M5 investigator read-only evidence role and binding."
  type        = bool
  default     = false
}

variable "investigator_operator_email" {
  description = "Operator allowed to mint short-lived investigator credentials; injected at runtime."
  type        = string
  default     = ""
  sensitive   = true

  validation {
    condition = (
      var.investigator_operator_email == "" ||
      can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.investigator_operator_email))
    )
    error_message = "investigator_operator_email must be empty or a valid email address."
  }

  validation {
    condition     = !var.enable_live_evidence || length(trimspace(var.investigator_operator_email)) > 0
    error_message = "investigator_operator_email is required when live evidence is enabled."
  }
}
