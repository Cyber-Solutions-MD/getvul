# GetVul Infrastructure
#
# Primary deployment: Google Cloud (see infra/gcp/)
# This file is kept for Terraform CI validation.
#
# Usage:
#   cd infra/gcp
#   terraform init
#   terraform plan -var="project_id=YOUR_PROJECT" -var="ssh_public_key=YOUR_KEY"
#   terraform apply

terraform {
  required_version = ">= 1.7"
}
