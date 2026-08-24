variable "project_id" {
  description = "Google Cloud project that owns the BARRED-Fleet Agent Gateway."
  type        = string
  default     = "gem-creation"
}

variable "location" {
  description = "Regional location for the Agent Gateway. Keep aligned with BARRED-Fleet Cloud Run."
  type        = string
  default     = "us-east1"
}

variable "gateway_id" {
  description = "Short Agent Gateway resource name."
  type        = string
  default     = "barred-agent-gateway-v1"
}

variable "runtime_service_account" {
  description = "BARRED-Fleet Cloud Run runtime service account that reads/verifies the gateway."
  type        = string
  default     = "barred-fleet-runtime@gem-creation.iam.gserviceaccount.com"
}

variable "enable_project_services" {
  description = "When true, Terraform enables required Google APIs. Leave false if APIs are managed elsewhere."
  type        = bool
  default     = false
}

variable "grant_runtime_viewer" {
  description = "When true, grants runtime service account Network Services Viewer for gateway verification."
  type        = bool
  default     = true
}

variable "agent_registries" {
  description = "Optional Agent Registry resource URIs governed by this gateway. Leave empty for V1 control-plane verification."
  type        = list(string)
  default     = []
}

variable "labels" {
  description = "Non-authoritative labels to attach to the gateway."
  type        = map(string)
  default = {
    app        = "barred-fleet"
    managed_by = "terraform"
    slice      = "agent-gateway-v1"
  }
}
