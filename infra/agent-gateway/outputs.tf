output "agent_gateway_id" {
  description = "Fully qualified Agent Gateway resource name."
  value       = google_network_services_agent_gateway.barred.id
}

output "agent_gateway_short_id" {
  description = "Short Agent Gateway ID for BARRED_AGENT_GATEWAY_ID."
  value       = var.gateway_id
}

output "cloud_run_env_vars" {
  description = "Environment variables for BARRED-Fleet Cloud Run cloud gateway verification mode."
  value = {
    BARRED_AGENT_GATEWAY_MODE        = "cloud_agent_gateway"
    BARRED_AGENT_GATEWAY_PROJECT     = var.project_id
    BARRED_AGENT_GATEWAY_LOCATION    = var.location
    BARRED_AGENT_GATEWAY_ID          = var.gateway_id
    BARRED_AGENT_GATEWAY_POLICY_ID   = google_network_services_agent_gateway.barred.id
    BARRED_AGENT_GATEWAY_AUDIT_ONLY  = "false"
  }
}
