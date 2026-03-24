variable "region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-1"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.medium" # 2 vCPU, 4 GB RAM
}

variable "disk_size_gb" {
  description = "Root EBS volume size in GB"
  type        = number
  default     = 30
}

variable "ssh_public_key" {
  description = "SSH public key for the EC2 key pair"
  type        = string
  sensitive   = true
}

variable "ssh_allowed_cidrs" {
  description = "CIDR ranges allowed to SSH into the instance"
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
