resource "google_project_service" "network_services" {
  count = var.enable_project_services ? 1 : 0

  project            = var.project_id
  service            = "networkservices.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "agent_registry" {
  count = var.enable_project_services && length(var.agent_registries) > 0 ? 1 : 0

  project            = var.project_id
  service            = "agentregistry.googleapis.com"
  disable_on_destroy = false
}

resource "google_network_services_agent_gateway" "barred" {
  project     = var.project_id
  name        = var.gateway_id
  location    = var.location
  description = "BARRED-Fleet Agent-to-Anywhere egress governance control plane."
  labels      = var.labels
  registries  = var.agent_registries

  google_managed {
    governed_access_path = "AGENT_TO_ANYWHERE"
  }

  deletion_policy = "PREVENT"

  depends_on = [
    google_project_service.network_services,
    google_project_service.agent_registry,
  ]
}

resource "google_project_iam_member" "runtime_networkservices_viewer" {
  count = var.grant_runtime_viewer ? 1 : 0

  project = var.project_id
  role    = "roles/networkservices.viewer"
  member  = "serviceAccount:${var.runtime_service_account}"
}
