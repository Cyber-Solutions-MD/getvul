variable "project_id" {
  description = "Google Cloud project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "europe-west1"
}

variable "zone" {
  description = "GCP zone"
  type        = string
  default     = "europe-west1-b"
}

variable "app_name" {
  description = "Application name (used for resource naming)"
  type        = string
  default     = "getvul"
}

variable "environment" {
  description = "Environment (production, staging)"
  type        = string
  default     = "production"
}

variable "machine_type" {
  description = "GCE instance type"
  type        = string
  default     = "e2-medium" # 2 vCPU, 4 GB RAM
}

variable "disk_size_gb" {
  description = "Boot disk size in GB"
  type        = number
  default     = 30
}

variable "github_repo" {
  description = "GitHub repository (owner/repo)"
  type        = string
  default     = "Cyber-Solutions-MD/getvul"
}

variable "ssh_user" {
  description = "SSH username for the VM"
  type        = string
  default     = "deploy"
}

variable "ssh_public_key" {
  description = "SSH public key for the deploy user"
  type        = string
}

variable "ssh_allowed_cidrs" {
  description = "CIDR ranges allowed to SSH into the VM"
  type        = list(string)
  default     = ["0.0.0.0/0"] # Restrict in production
}

variable "deploy_key" {
  description = "GitHub deploy key (SSH private key) for pulling the repo"
  type        = string
  sensitive   = true
  default     = ""
}
