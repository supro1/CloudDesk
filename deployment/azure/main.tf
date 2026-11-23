resource "azurerm_resource_group" "application" {
  name     = var.resource_group_name
  location = var.location
  tags     = local.common_tags
}

resource "azurerm_container_registry" "application" {
  name                = var.registry_name
  resource_group_name = azurerm_resource_group.application.name
  location            = azurerm_resource_group.application.location
  sku                 = "Basic"
  admin_enabled       = false
  tags                = local.common_tags
}

resource "azurerm_log_analytics_workspace" "application" {
  name                = "${var.project_name}-${var.environment}-logs"
  location            = azurerm_resource_group.application.location
  resource_group_name = azurerm_resource_group.application.name
  sku                 = "PerGB2018"
  retention_in_days   = var.log_retention_days
  tags                = local.common_tags
}

locals {
  common_tags = {
    application = var.project_name
    environment = var.environment
    managed_by  = "Terraform"
  }
}
