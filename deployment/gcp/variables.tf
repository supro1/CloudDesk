variable "project_id" {
  description = "Google Cloud project ID."
  type        = string
}

variable "region" {
  description = "Google Cloud region for the image repository."
  type        = string
  default     = "us-central1"
}

variable "repository_id" {
  description = "Artifact Registry repository ID."
  type        = string
  default     = "clouddesk"
}

variable "project_name" {
  description = "Short project identifier."
  type        = string
  default     = "clouddesk"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "dev"
}
