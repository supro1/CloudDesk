resource "google_artifact_registry_repository" "application" {
  location      = var.region
  repository_id = var.repository_id
  description   = "CloudDesk application container images"
  format        = "DOCKER"

  labels = {
    application = var.project_name
    environment = var.environment
    managed_by  = "terraform"
  }
}
