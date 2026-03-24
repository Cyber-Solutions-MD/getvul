variable "location" {
  description = "Azure region for all resources"
  type        = string
  default     = "westeurope"
}

variable "vm_size" {
  description = "Azure VM size"
  type        = string
  default     = "Standard_B2s" # 2 vCPU, 4 GB RAM
}

variable "disk_size_gb" {
  description = "OS disk size in GB"
  type        = number
  default     = 30
}

variable "admin_username" {
  description = "Admin username for the VM"
  type        = string
  default     = "getvul"
}

variable "ssh_public_key" {
  description = "SSH public key for the admin user"
  type        = string
  sensitive   = true
}

variable "ssh_allowed_cidrs" {
  description = "CIDR ranges allowed to SSH into the VM"
  type        = list(string)
  default     = ["0.0.0.0/0"] # Restrict in production
}

variable "github_repo" {
  description = "GitHub repository (owner/repo)"
  type        = string
  default     = "Cyber-Solutions-MD/getvul"
}

variable "deploy_key" {
  description = "GitHub deploy key (SSH private key) for pulling the repo"
  type        = string
  sensitive   = true
  default     = ""
}
