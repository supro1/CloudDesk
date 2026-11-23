variable "location" {
  description = "Azure region for the CloudDesk resources."
  type        = string
  default     = "eastus"
}

variable "project_name" {
  description = "Short project identifier used in resource names."
  type        = string
  default     = "clouddesk"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "dev"
}

variable "resource_group_name" {
  description = "Resource group name; choose a name unique in the subscription."
  type        = string
}

variable "registry_name" {
  description = "Globally unique Azure Container Registry name (letters and numbers only)."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9]{5,50}$", var.registry_name))
    error_message = "registry_name must contain 5-50 letters or numbers."
  }
}

variable "log_retention_days" {
  description = "Log Analytics retention period."
  type        = number
  default     = 30
}
