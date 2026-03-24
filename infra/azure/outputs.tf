output "vm_ip" {
  description = "Public IP address of the GetVul VM"
  value       = azurerm_public_ip.getvul.ip_address
}

output "vm_name" {
  description = "Name of the Azure VM"
  value       = azurerm_linux_virtual_machine.getvul.name
}

output "resource_group" {
  description = "Name of the Azure resource group"
  value       = azurerm_resource_group.getvul.name
}

output "ssh_command" {
  description = "SSH command to connect to the VM"
  value       = "ssh ${var.admin_username}@${azurerm_public_ip.getvul.ip_address}"
}

output "app_url" {
  description = "Application URL"
  value       = "https://${azurerm_public_ip.getvul.ip_address}"
}
