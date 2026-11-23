output "container_registry_login_server" {
  description = "ACR login server for publishing container images."
  value       = azurerm_container_registry.application.login_server
}

output "log_analytics_workspace_id" {
  description = "Log Analytics workspace ID for application monitoring."
  value       = azurerm_log_analytics_workspace.application.id
}
