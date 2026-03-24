output "vm_ip" {
  description = "External IP address of the GetVul VM"
  value       = google_compute_address.getvul.address
}

output "vm_name" {
  description = "Name of the GCE instance"
  value       = google_compute_instance.getvul.name
}

output "ssh_command" {
  description = "SSH command to connect to the VM"
  value       = "ssh ${var.ssh_user}@${google_compute_address.getvul.address}"
}

output "app_url" {
  description = "Application URL"
  value       = "https://${google_compute_address.getvul.address}"
}
