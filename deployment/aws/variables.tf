variable "region" {
  description = "AWS region for the CloudDesk resources."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short lowercase project identifier."
  type        = string
  default     = "clouddesk"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "dev"
}

variable "log_retention_days" {
  description = "CloudWatch log retention period."
  type        = number
  default     = 30
}
