# GetVul — Google Cloud infrastructure
# Single GCE VM running Docker Compose with auto-update

terraform {
  required_version = ">= 1.7"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# ── Static IP ──

resource "google_compute_address" "getvul" {
  name         = "${var.app_name}-ip"
  address_type = "EXTERNAL"
  region       = var.region
}

# ── Firewall rules ──

resource "google_compute_firewall" "getvul_web" {
  name    = "${var.app_name}-allow-web"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = [var.app_name]
}

resource "google_compute_firewall" "getvul_ssh" {
  name    = "${var.app_name}-allow-ssh"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = var.ssh_allowed_cidrs
  target_tags   = [var.app_name]
}

# ── Service account ──

resource "google_service_account" "getvul" {
  account_id   = var.app_name
  display_name = "GetVul VM service account"
}

# ── GCE VM ──

resource "google_compute_instance" "getvul" {
  name         = "${var.app_name}-vm"
  machine_type = var.machine_type
  zone         = var.zone
  tags         = [var.app_name]

  boot_disk {
    initialize_params {
      image = "projects/cos-cloud/global/images/family/cos-stable"
      size  = var.disk_size_gb
      type  = "pd-ssd"
    }
  }

  network_interface {
    network = "default"
    access_config {
      nat_ip = google_compute_address.getvul.address
    }
  }

  service_account {
    email  = google_service_account.getvul.email
    scopes = ["cloud-platform"]
  }

  metadata = {
    ssh-keys                = "${var.ssh_user}:${var.ssh_public_key}"
    google-logging-enabled  = "true"
    google-monitoring-enabled = "true"
  }

  metadata_startup_script = templatefile("${path.module}/startup.sh", {
    app_name    = var.app_name
    github_repo = var.github_repo
    deploy_key  = var.deploy_key
  })

  labels = {
    app         = var.app_name
    environment = var.environment
    managed_by  = "terraform"
  }
}
