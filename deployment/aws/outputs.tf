output "backend_image_repository_url" {
  description = "ECR repository URI for the backend image."
  value       = aws_ecr_repository.backend.repository_url
}

output "frontend_image_repository_url" {
  description = "ECR repository URI for the frontend image."
  value       = aws_ecr_repository.frontend.repository_url
}

output "application_log_group_name" {
  description = "CloudWatch log group for application workloads."
  value       = aws_cloudwatch_log_group.application.name
}
